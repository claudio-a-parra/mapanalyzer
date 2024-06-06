from collections import deque

from util import AddrFmt, Dbg
from settings import Settings as st
from map_file_reader import MemAccess

class Block:
    def __init__(self, block_size, tag=None, dirty=False):
        self.tag = tag
        self.dirty = dirty
        self.bytes = [False] * block_size # accessed bytes
        
    def access(self, offset, n_bytes, write=False):
        """access n bytes in this block starting from offset."""
        # Raise an exception if attempting to access bytes passed the end
        # of the block
        if offset + n_bytes > len(self.bytes):
            raise ValueError("trying to access more bytes than the ones "
                             "contained in a cache block")
            exit(1)
        # Mark bytes as accessed
        if n_bytes > 0:
            self.bytes[offset:offset+n_bytes] = [True] * n_bytes
            if write:
                self.dirty = True

    def count_accessed(self):
        return self.bytes.count(True)

    def __repr__(self):
        by = ''
        for b in self.bytes:
            by += 'X' if b else '_'
        d = "x" if self.dirty else "_"
        return f'{by}|{d}'


class Set:
    def __init__(self, associativity):
        self.associativity = int(associativity)
        self.lines = deque()

    def push_block(self, block) -> Block:
        """push a block to this set. If the set is full, return the evicting
        block, otherwise return None"""
        self.lines.appendleft(block)
        if len(self.lines) <= self.associativity:
            return None
        return self.lines.pop()

    def touch_block(self, block):
        """bring some block in the set to the beginning of the queue,
        making it the "most recently used" one."""
        self.lines.remove(block)
        self.lines.appendleft(block)
        return

    def pop_lru_block(self):
        """remove the least recently used block, or None if set is empty"""
        if len(self.lines) == 0:
            return None
        return self.lines.pop()
    

class Cache:
    def __init__(self, tools=None):
        if tools is None:
            raise ValueError('tools cannot be None')
        self.tools = tools
        self.blocks_in_cache = {}
        self.sets = [Set(st.cache.asso) for _ in range(st.cache.num_sets)]
        return

    def multi_access(self, concurrent_access):
        Dbg.i()
        common_time = concurrent_access[0].time
        Dbg.p()
        Dbg.p(f'TIME: {common_time}')
        Dbg.p(concurrent_access)
        for a in concurrent_access:
            self.access(a)
        self.tools.commit(common_time)
        Dbg.o()

        return

    def access(self, access):
        """ Access 'n bytes' starting from address 'addr'. If this requires to
        access multiple cache lines, then generate multiple accesses."""
        Dbg.i()
        # Access object:
        # - addr  : address of access
        # - size  : the number of bytes accessed
        # - event : read or write event {'R', 'W'}
        # - thread: the thread accessing data
        # - time  : the timestamp of the instruction.
        Dbg.p(f'\n\n\nCACHE.access({access})')
        addr = access.addr
        n_bytes = access.size
        self.tools.map.add_access(access)

        # check correct bit_length
        if addr.bit_length() > st.cache.arch:
            raise ValueError("Error: Access issued to address larger than"
                             " the one defined for this cache.")
            exit(1)


        # access the potentially many lines
        while n_bytes > 0:
            v_tag, set_index, offset = AddrFmt.split(addr)
            # TODO: implement TLB and physical addresses
            p_tag = v_tag

            # handle multi-line accesses
            if n_bytes > (st.cache.line_size - offset):
                this_block_n_bytes = st.cache.line_size - offset
            else:
                this_block_n_bytes = n_bytes

            block_access = MemAccess(access.time,
                                     access.thread,
                                     access.event,
                                     this_block_n_bytes,
                                     addr)
            self.tools.locality.add_access(block_access)
            # access this_block
            Dbg.p(f'Querying block ({p_tag},{set_index}).')
            Dbg.p(self)
            writing = (access.event == 'W')
            if (p_tag,set_index) not in self.blocks_in_cache:
                # Cache Miss: fetch block from main memory
                Dbg.p(f'Block ({p_tag},{set_index}) MISS.')
                self.tools.hitmiss.add_hm(access, (0,1)) # miss++

                # fetch block from main memory...
                fetched_block = Block(st.cache.line_size, tag=p_tag,
                                            dirty=writing)
                #self.tools.alias.fetch(access)
                #self.tools.siue.fetch(access)

                # ... and add it to the cache
                self.blocks_in_cache[(p_tag,set_index)] = fetched_block
                self.tools.cost.add_access('r') # read
                self.tools.usage.update(delta_valid=st.cache.line_size)

                # handle potentially evicted block
                evicted_block = self.sets[set_index].push_block(fetched_block)
                if evicted_block is not None:
                    del self.blocks_in_cache[(evicted_block.tag,set_index)]
                    Dbg.p(f'Block ({evicted_block.tag},{set_index}) '
                          f'[{evicted_block}] EVICTED.')
                    self.tools.usage.update(
                        delta_access=-evicted_block.count_accessed(),
                        delta_valid=-st.cache.line_size)

                    if evicted_block.dirty:
                        Dbg.p(f'WRITE (t:{access.time}): {evicted_block}')
                        self.tools.cost.add_access('w') # write
                    else:
                        Dbg.p(f'DROP (t:{access.time}): {evicted_block}')

                resident_block = fetched_block

                Dbg.p(f'READ: {access}')

            else:
                Dbg.p(f'Block ({p_tag},{set_index}) HIT.')
                resident_block = self.blocks_in_cache[(p_tag,set_index)]
                self.sets[set_index].touch_block(resident_block)
                self.tools.hitmiss.add_hm(access, (1,0)) # hit++

            # mark accessed bytes
            old_ab = resident_block.count_accessed()
            resident_block.access(offset, this_block_n_bytes, write=writing)
            new_ab = resident_block.count_accessed()
            self.tools.usage.update(delta_access=new_ab-old_ab)

            # update address and reminding bytes to read for a potential new loop
            addr += this_block_n_bytes
            n_bytes -= this_block_n_bytes

        Dbg.o()
        return

    def flush(self):
        """evict all cache lines"""
        for s in self.sets:
            evicted_block = s.pop_lru_block()
            while evicted_block != None:
                pass
                #self.tools.usage.update()
                if evicted_block.dirty:
                    pass
                    #self.tools.ram.write()
                evicted_block = s.pop_lru_block()
        return

    def __repr__(self):
        keys = list(self.blocks_in_cache.keys())
        keys.sort()
        ret  = '+--Cache--------------\n'
        ret += '| tag,set -->  blk|d\n'
        for k in keys:
            blk_id = f'{k[0]:3},{k[1]:3}'
            ret += f'| {blk_id:>6} --> {self.blocks_in_cache[k]}\n'
        ret += '+---------------------'
        return ret


    # def dump(self, show_last=True):
    #     """print a representation of all cache sets and their content"""

    #     # invalid, valid, accessed, and 'right-now-accessing' bytes
    #     # For copy/paste: ░ ▒ ▓ █ ← ⇐ ─
    #     inv_b, val_b, acc_b, now_b = ' ', '░', '▒', '█'

    #     set_label_width = len(hex(self.sp.num_sets)[2:])
    #     line_label_width = len(hex(self.sp.asso)[2:])
    #     padding = (self.tag_bits + 3) // 4

    #     # for each set in the cache
    #     for i,s in enumerate(self.sets):
    #         i_hex = hex(i)[2:]
    #         set_label = f"s{i_hex.zfill(set_label_width)} "
    #         no_set_label = ' ' * len(set_label)
    #         # for each line in the set
    #         for j,l in enumerate(s.lines):
    #             j_hex = hex(j)[2:]
    #             last_access = l.last_time_used

    #             # create line label (lX)
    #             line_label = f'l{j_hex.zfill(line_label_width)} '

    #             arrow = ''
    #             if l.tag == None: # if it is an invalid line:
    #                 tag_label = ' ' * padding
    #                 data = inv_b * self.line_size_bytes
    #             else: # if this is a valid line
    #                 tag_label = hex(l.tag)[2:].zfill(padding)
    #                 line = [acc_b if b else val_b
    #                         for b in l.accessed_bytes]
    #                 # if this line was just accessed, highlight it
    #                 if last_access == self.clock and show_last:
    #                     arrow = ' <───'
    #                     lo,lb = l.last_access
    #                     line[lo:lo+lb] = now_b * lb
    #                 data = ''.join(line)
    #             # print line
    #             print(f"{set_label}{line_label}{data} "
    #                   f"tag:{tag_label} acc:{last_access}{arrow}")
    #             # invisible set label for next lines in the same set
    #             set_label = no_set_label
    #         # skip one line for the next set
    #         if i+1 < self.sp.num_sets:
    #             print()









# class Line:   
    # def access(self, thr, instr_id, tag, offset, n_bytes):
    #     """Find the Line in this Set that contains a given tag, and access
    #     n bytes from it. Handle cache misses. Error if trying to access
    #     bytes outside of the selected line"""
    #     # find line
    #     index, line = None, None
    #     for i,l in enumerate(self.lines):
    #         if l.tag == tag:
    #             index,line = i,l
    #             break;

    #     # Handle a possible cache miss.
    #     if line == None: # cache miss
    #         self.instr.hit.register(thr, delta_miss=1)
    #         line = self.lru_line()
    #         self.evict(line)
    #         self.fetch(line, tag)
    #     else: # cache hit
    #         self.instr.hit.register(thr, delta_hit=1)

    #     # Now the cache line is valid. Access data, but pay attention to
    #     # how many bytes are freshly accessed, as these will count towards
    #     # byte usage.
    #     before_access = line.count_accessed()
    #     line.access(offset, n_bytes, clock)
    #     after_access = line.count_accessed()
    #     if after_access > before_access:
    #         new_access = after_access - before_access
    #         self.instr.usage.register(delta_access=new_access)

    # def lru_line(self):
    #     """return the least recently used line"""
    #     oldest_line = self.lines[0]
    #     for l in self.lines[1:]:
    #         if l.last_time_used < oldest_line.last_time_used:
    #            oldest_line = l
    #     return oldest_line

    # def evict(self, line):
    #     if line.tag == None:
    #         return
    #     self.instr.siu.register('evict', line.tag, self.set_index)
    #     # these bytes are leaving the cache, so they are negative
    #     self.instr.usage.register(delta_access=-line.count_accessed(),
    #                               delta_valid=-self.line_size_bytes)
    #     # imagine that here you write the block back to memory...
    #     # and now reset the line's access count and tag
    #     line.accessed_bytes = [False] * len(line.accessed_bytes)
    #     line.tag = None
    #     line.last_time_used = 0
    #     return

    # def fetch(self, line, tag):
    #     self.instr.siu.register('fetch', tag, self.set_index)
    #     self.instr.alias.register(tag, self.set_index)
    #     self.instr.usage.register(delta_valid=self.line_size_bytes)
    #     # imagine that here you bring the data... and now you mark the tag
    #     line.tag = tag
    #     return

    # def flush(self):
    #     for l in self.lines:
    #         self.evict(l)


