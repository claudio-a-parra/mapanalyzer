from collections import deque

from mapanalyzer.util import AddrFmt, Dbg
from mapanalyzer.settings import Settings as st
from mapanalyzer.map_file_reader import MemAccess

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
        # Access object:
        # - addr  : address of access
        # - size  : the number of bytes accessed
        # - event : read or write event {'R', 'W'}
        # - thread: the thread accessing data
        # - time  : the timestamp of the instruction.
        addr = access.addr - st.map.aligned_start_addr
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
            writing = (access.event == 'W')
            if (p_tag,set_index) not in self.blocks_in_cache:
                # MISS
                self.tools.hitmiss.add_hm(access, (0,1)) # miss++

                # fetch block from main memory
                fetched_block = Block(st.cache.line_size, tag=p_tag,
                                            dirty=writing)
                self.tools.aliasing.fetch(set_index, access.time)
                self.tools.cost.add_access('r') # read

                # add fetched block to the cache
                self.blocks_in_cache[(p_tag,set_index)] = fetched_block
                self.tools.usage.update(delta_valid=st.cache.line_size)

                # handle potentially evicted block
                evicted_block = self.sets[set_index].push_block(fetched_block)
                tag_out = None if evicted_block is None else evicted_block.tag
                self.tools.siu.update(access.time, set_index, p_tag, tag_out)
                if evicted_block is not None:
                    # EVICTION
                    del self.blocks_in_cache[(evicted_block.tag,set_index)]
                    self.tools.usage.update(
                        delta_access=-evicted_block.count_accessed(),
                        delta_valid=-st.cache.line_size)
                    if evicted_block.dirty:
                        # WRITE DIRTY BLOCK
                        self.tools.cost.add_access('w') # write
                    else:
                        # DROP CLEAN BLOCK
                        pass
                resident_block = fetched_block
            else:
                # HIT
                resident_block = self.blocks_in_cache[(p_tag,set_index)]
                self.tools.hitmiss.add_hm(access, (1,0)) # hit++
                self.sets[set_index].touch_block(resident_block)

            # mark accessed bytes
            old_ab = resident_block.count_accessed()
            resident_block.access(offset, this_block_n_bytes, write=writing)
            new_ab = resident_block.count_accessed()
            self.tools.usage.update(delta_access=new_ab-old_ab)

            # update address and reminding bytes to read for a potential new loop
            addr += this_block_n_bytes
            n_bytes -= this_block_n_bytes
        return

    def flush(self):
        """evict all cache lines"""
        for set_idx in range(st.cache.num_sets):
            s = self.sets[set_idx]
            evicted_block = s.pop_lru_block()
            tag_out = None if evicted_block is None else evicted_block.tag
            while evicted_block is not None:
                tag_out = evicted_block.tag
                self.tools.siu.update(st.map.time_size, set_idx, None, tag_out)
                #self.tools.usage.update()
                if evicted_block.dirty:
                    self.tools.cost.add_access('w')
                evicted_block = s.pop_lru_block() # get next evicted block
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
