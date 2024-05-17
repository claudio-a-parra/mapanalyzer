#!/usr/bin/env python3
from address_formatter import log2, AddressFormatter

class Line:
    def __init__(self, line_size_bytes, tag=None, last_time_used=0):
        self.tag = tag # line tag
        self.accessed_bytes = [False] * line_size_bytes # accessed bytes
        self.last_time_used = last_time_used # last time the line was used
        # the last (offset,n_bytes) of accessed bytes. Used to highlight
        # the last access.
        self.last_accessed_bytes = (0, 0)
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
            self.last_accessed_bytes = (offset, n_bytes)
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

    def access(self, thr, instr_id, tag, offset, n_bytes, clock):
        """Find the Line in this Set that contains a given tag, and access
        n bytes from it. Handle cache misses. Error if trying to access
        bytes outside of the selected line"""
        # find line
        index, line = None, None
        for i,l in enumerate(self.lines):
            if l.tag == tag:
                index,line = i,l
                break;

        # Handle a possible cache miss.
        if line == None: # cache miss
            self.instr.hit.register(thr, delta_miss=1)
            line = self.lru_line()
            self.evict(line)
            self.fetch(line, tag)
        else: # cache hit
            self.instr.hit.register(thr, delta_hit=1)

        # Now the cache line is valid. Access data, but pay attention to
        # how many bytes are freshly accessed, as these will count towards
        # byte usage.
        before_access = line.count_accessed()
        line.access(offset, n_bytes, clock)
        after_access = line.count_accessed()
        if after_access > before_access:
            new_access = after_access - before_access
            self.instr.usage.register(delta_access=new_access)

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
        self.instr.siu.register('evict', line.tag, self.set_index)
        # these bytes are leaving the cache, so they are negative
        self.instr.usage.register(delta_access=-line.count_accessed(),
                                  delta_valid=-self.line_size_bytes)
        # imagine that here you write the block back to memory...
        # and now reset the line's access count and tag
        line.accessed_bytes = [False] * len(line.accessed_bytes)
        line.tag = None
        line.last_time_used = 0
        return

    def fetch(self, line, tag):
        self.instr.siu.register('fetch', tag, self.set_index)
        self.instr.alias.register(tag, self.set_index)
        self.instr.usage.register(delta_valid=self.line_size_bytes)
        # imagine that here you bring the data... and now you mark the tag
        line.tag = tag
        return

    def flush(self):
        for l in self.lines:
            self.evict(l)




class Cache:
    def __init__(self, specs, instr=None):
        # arch_size_bits, cache_size_bytes,line_size_bytes, associativity
        self.arch_size_bits = int(specs['arch'])
        self.cache_size_bytes = int(specs['size'])
        self.line_size_bytes = int(specs['line'])
        self.associativity = int(specs['asso'])

        self.clock = 0 # used for least recently used policy
        self.instr = instr # instruments
        self.af = AddressFormatter(specs)
        # compute the number of bits needed for byte addressing in the line,
        # set selection, and line-tag
        self.offset_bits = log2(self.line_size_bytes)
        self.num_sets = self.cache_size_bytes// \
            (self.associativity*self.line_size_bytes)
        self.index_bits = log2(self.num_sets)
        self.tag_bits = self.arch_size_bits - self.index_bits - self.offset_bits

        self.sets = [Set(self.associativity, self.line_size_bytes,
                         set_index=i, instr=self.instr)
                     for i in range(self.num_sets)] # the array of sets

    def access(self, access):
        """
        Access 'n bytes' starting from address 'addr'. If this requires to
        access multiple cache lines, then generate multiple accesses.
        """
        # ignore Thread creation and destroying
        if access.event in ('Tc', 'Td'):
            return

        # Access object:
        # - addr  : address of access
        # - size  : the number of bytes accessed
        # - event : read or write event {'R', 'W'}
        # - thread: the thread accessing data
        # - time  : the timestamp of the instruction.
        addr = access.addr
        n_bytes = access.size
        self.instr.map.register_access(access)
        self.instr.locality.register_access(access)

        # the potentially many lines are all accessed at the same time (cache.clock)
        self.clock += 1
        if addr.bit_length() > self.arch_size_bits:
            raise ValueError("Error: Access issued to address larger than"
                             " the one defined for this cache.")
            exit(1)
        while n_bytes > 0:
            v_tag, index, offset = self.af.split(addr)
            # TODO: implement TLB and physical addresses
            p_tag = v_tag

            # handle multi-line accesses
            if n_bytes > (self.line_size_bytes - offset):
                this_line_n_bytes = self.line_size_bytes - offset
            else:
                this_line_n_bytes = n_bytes

            # access this single line
            self.sets[index].access(access.thread, access.time,
                                    p_tag, offset, this_line_n_bytes, self.clock)

            # update address and reminding bytes to read for a potential new loop
            addr += this_line_n_bytes
            n_bytes -= this_line_n_bytes

    def flush(self):
        """evict all cache lines"""
        for s in self.sets:
            s.flush()

    def reset_clock(self):
        self.clock = 0

    def describe_cache(self):
        print(f"    Address size  : {self.arch_size_bits} bits")
        print(f"    Cache size    : {self.cache_size_bytes} bytes")
        print(f"    Number of sets: {self.num_sets}")
        print(f"    Associativity : {self.associativity} lines")
        print(f"    Line size     : {self.line_size_bytes} bytes")
        print(f"    Tag size      : {self.tag_bits} bits")


    def dump(self, show_last=True):
        """print a representation of all cache sets and their content"""

        # invalid, valid, accessed, and 'right-now-accessing' bytes
        # For copy/paste: ░ ▒ ▓ █ ← ⇐ ─
        inv_b, val_b, acc_b, now_b = ' ', '░', '▒', '█'

        set_label_width = len(hex(self.num_sets)[2:])
        line_label_width = len(hex(self.associativity)[2:])
        padding = (self.tag_bits + 3) // 4

        # for each set in the cache
        for i,s in enumerate(self.sets):
            i_hex = hex(i)[2:]
            set_label = f"s{i_hex.zfill(set_label_width)} "
            no_set_label = ' ' * len(set_label)
            # for each line in the set
            for j,l in enumerate(s.lines):
                j_hex = hex(j)[2:]
                last_access = l.last_time_used

                # create line label (lX)
                line_label = f'l{j_hex.zfill(line_label_width)} '

                arrow = ''
                if l.tag == None: # if it is an invalid line:
                    tag_label = ' ' * padding
                    data = inv_b * self.line_size_bytes
                else: # if this is a valid line
                    tag_label = hex(l.tag)[2:].zfill(padding)
                    line = [acc_b if b else val_b
                            for b in l.accessed_bytes]
                    # if this line was just accessed, highlight it
                    if last_access == self.clock and show_last:
                        arrow = ' <───'
                        lo,lb = l.last_accessed_bytes
                        line[lo:lo+lb] = now_b * lb
                    data = ''.join(line)
                # print line
                print(f"{set_label}{line_label}{data} "
                      f"tag:{tag_label} acc:{last_access}{arrow}")
                # invisible set label for next lines in the same set
                set_label = no_set_label
            # skip one line for the next set
            if i+1 < self.num_sets:
                print()
