#!/usr/bin/env python3
from address_formatter import log2, AddressFormatter

class Line:
    def __init__(self, line_size_bytes, tag=None, last_time_used=0):
        self.tag = tag # line tag
        self.accessed_bytes = [False] * line_size_bytes # accessed bytes
        self.last_time_used = last_time_used # last time the line was used

    def access(self, offset, n_bytes, clock):
        """access n bytes in this line starting from offset."""
        # Raise an exception if attempting to access bytes passed the end
        # of the cache line
        if offset + n_bytes > len(self.accessed_bytes):
            raise ValueError("trying to access more bytes than the ones "
                             "contained in a cache line")
            exit(1)
        # Mark bytes as accessed and timestamp
        if n_bytes > 0:
            self.accessed_bytes[offset:offset+n_bytes] = [True] * n_bytes
            self.last_time_used = clock

    def count_accessed(self):
        return self.accessed_bytes.count(True)




class Set:
    def __init__(self, associativity, line_size_bytes, set_index, instr=None):
        self.associativity = int(associativity)
        self.line_size_bytes = int(line_size_bytes)
        self.set_index = int(set_index)
        self.lines = [Line(line_size_bytes) for i in range(associativity)]
        self.instr=instr # instruments

    def access(self, tag, offset, n_bytes, clock):
        """Find the Line in this Set that contains a given tag, and access
        n bytes from it. Handle cache misses."""
        self.instr.alias.append(self.set_index)
        # find line
        index, line = None, None
        for i,l in enumerate(self.lines):
            if l.tag == tag:
                index,line = i,l
                break;
        # handle miss/hit
        if line != None:
            # cache hit
            self.instr.hit_miss.append_hit()
        else:
            # cache miss
            self.instr.hit_miss.append_miss()
            line = self.lru_line()
            self.evict(line)
            self.fetch(line, tag)
        # access data in line
        line.access(offset, n_bytes, clock)

    def lru_line(self):
        """return the least recently used line"""
        oldest_line = self.lines[0]
        for l in self.lines[1:]:
            if l.last_time_used < oldest_line.last_time_used:
               oldest_line = l
        return oldest_line

    def evict(self, line):
        if line.tag == None:
            return
        self.instr.siu_eviction.append_evict(self.set_index, line.tag)
        accessed_count = line.count_accessed()
        self.instr.line_usage.append(accessed_count)
        # reset access and tag
        line.accessed_bytes = [False] * len(line.accessed_bytes)
        line.tag = None
        return

    def fetch(self, line, tag):
        self.instr.siu_eviction.append_fetch(self.set_index, tag)
        line.tag = tag
        return

    def flush(self):
        for l in self.lines:
            self.evict(l)




class Cache:
    def __init__(self, arch_size_bits, cache_size_bytes,
                 line_size_bytes, associativity, instr=None):
        self.arch_size_bits = int(arch_size_bits)
        self.cache_size_bytes = int(cache_size_bytes)
        self.line_size_bytes = int(line_size_bytes)
        self.associativity = int(associativity)
        self.clock = 0
        self.instr = instr # instruments
        self.af = AddressFormatter(arch_size_bits, cache_size_bytes,
                                   line_size_bytes, associativity)
        # compute the number of bits needed for byte addressing in the line,
        # set selection, and line-tag
        self.offset_bits = log2(self.line_size_bytes)
        self.num_sets = self.cache_size_bytes//(self.associativity*self.line_size_bytes)
        self.index_bits = log2(self.num_sets)
        self.tag_bits = self.arch_size_bits - self.index_bits - self.offset_bits

        self.sets = [Set(self.associativity, self.line_size_bytes,
                         set_index=i, instr=self.instr)
                     for i in range(self.num_sets)] # the array of sets

    def access(self, addr, n_bytes):
        """
        Access 'n bytes' starting from address 'addr'. If this requires to access
        multiple cache lines, then generate multiple accesses.
        """
        # the potentially many lines are all accessed at the same time
        self.clock += 1
        if addr.bit_length() > self.arch_size_bits:
            raise ValueError("Access issued to address beyond architecture word size")
            exit(1)
        while n_bytes > 0:
            v_tag, index, offset = self.af.split(addr)
            # v_tag, index, offset = self.decompose_addr(addr)
            p_tag = v_tag

            # handle multi-line accesses
            if n_bytes > (self.line_size_bytes - offset):
                this_line_n_bytes = self.line_size_bytes - offset
            else:
                this_line_n_bytes = n_bytes

            # access this single line
            self.sets[index].access(p_tag, offset, this_line_n_bytes, self.clock)

            # update address and reminding bytes to read for a potential new loop
            addr += this_line_n_bytes
            n_bytes -= this_line_n_bytes

    def flush(self):
        """evict all cache lines"""
        for s in self.sets:
            s.flush()

    def describe_cache(self):
        print("── Cache Configuration ─────────────────")
        print(f"Address size  : {self.arch_size_bits} bits")
        print(f"Cache size    : {self.cache_size_bytes} bytes")
        print(f"Number of sets: {self.num_sets}")
        print(f"Associativity : {self.associativity} lines")
        print(f"Line size     : {self.line_size_bytes} bytes")
        print(f"Tag size      : {self.tag_bits} bits")
        print("── Instruments ─────────────────────────")
        print("Line Usage     : Percentage of cache line used.")
        print("SIU Evictions  : Still-in-use Evictions.")
        print("Alias Access   : Cache Aliasing detection.")
        print("Cache hits     : Cache hit ratio.")
        print("TLB trashing   : *TODO* work in progress.")
        print("False sharing  : *TODO* major work.")

    def dump(self, show_last=True):
        """print a representation of all cache sets and their content"""

        # invalid, valid, accessed, and 'right-now-accessing' bytes
        # For copy/paste: ░ ▒ ▓ █ ← ⇐ ─
        inv_b, val_b, acc_b, now_b = ' ', '░', '▒', '█'

        set_label_width = len(str(self.num_sets))
        line_label_width = len(str(self.associativity))
        padding = (self.tag_bits + 3) // 4

        # for each set
        for i,s in enumerate(self.sets):
            set_label = f"s{str(i).zfill(set_label_width)} "
            no_set_label = ' ' * len(set_label)
            # for each line in the set (line zero on the right)
            for j,l in enumerate(s.lines):
                used = l.last_time_used
                hl = now_b if used == self.clock and show_last else acc_b
                arr = ' <───' if hl == now_b else ''
                line_label = f'l{str(j).zfill(line_label_width)} '
                if l.tag == None:
                    line_tag_label = ' ' * padding
                    line_data_label = inv_b * len(l.accessed_bytes)
                else:
                    line_tag_label = hex(l.tag)[2:].zfill(padding)
                    line_data_label =  ''.join(
                        [hl if b else val_b for b in l.accessed_bytes])
                print(f"{set_label}{line_label}{line_data_label} "
                      f"tag:{line_tag_label} acc:{used}{arr}")
                set_label = no_set_label
            print()
