from collections import deque

from mapanalyzer.settings import Settings as st
from mapanalyzer.ui import UI

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
    def __init__(self, modules=None):
        if modules is None:
            raise ValueError('modules object cannot be None')
        self.modules = modules
        self.blocks_in_cache = {}
        self.sets = [Set(st.Cache.asso) for _ in range(st.Cache.num_sets)]
        UI.warning('Commenting some modules. Marked with "#!".', pre='TODO')
        return

    def __accesses(self, concurrent_access):
        common_time = concurrent_access[0].time
        for a in concurrent_access:
            self.__single_access(a)
        self.modules.commit(common_time)

        return

    def __single_access(self, access):
        """ Access 'n bytes' starting from address 'addr'. If this requires to
        access multiple cache lines, then generate multiple accesses."""
        # Access object:
        # - addr  : address of access
        # - size  : the number of bytes accessed
        # - event : read or write event {'R', 'W'}
        # - thread: the thread accessing data
        # - time  : the timestamp of the instruction.
        addr = access.addr - st.Map.aligned_start_addr
        n_bytes = access.size
        self.modules.map.probe(access=access)

        # check correct bit_length
        if addr.bit_length() > st.Cache.arch:
            raise ValueError(f'Error: Access issued to address '
                             f'larger ({addr.bit_length()} bits) than '
                             f'the architecture defined for this cache '
                             f'({st.Cache.arch} bits).')

        # access the potentially many lines
        while n_bytes > 0:
            v_tag, set_index, offset = st.AddrFmt.split(addr)
            # TODO: implement TLB and physical addresses
            p_tag = v_tag

            # handle multi-line accesses
            if n_bytes > (st.Cache.line_size - offset):
                this_block_n_bytes = st.Cache.line_size - offset
            else:
                this_block_n_bytes = n_bytes

            self.modules.locality.probe(access.time, access.thread,
                                        access.event, this_block_n_bytes, addr)

            # access this_block
            writing = (access.event == 'W')
            if (p_tag,set_index) not in self.blocks_in_cache:
                # MISS
                self.modules.missratio.probe(access, (0,1)) # miss++

                # fetch block from main memory
                fetched_block = Block(st.Cache.line_size, tag=p_tag,
                                            dirty=writing)
                #!self.modules.aliasing.fetch(set_index, access.time)
                self.modules.memaccess.probe('r') # read

                # add fetched block to the cache
                self.blocks_in_cache[(p_tag,set_index)] = fetched_block
                self.modules.usage.probe(delta_valid=st.Cache.line_size)

                # handle potentially evicted block
                evicted_block = self.sets[set_index].push_block(fetched_block)
                tag_out = None if evicted_block is None else evicted_block.tag
                #!self.modules.evicd.update(access.time, set_index, p_tag, tag_out)
                if evicted_block is not None:
                    # EVICTION
                    del self.blocks_in_cache[(evicted_block.tag,set_index)]
                    self.modules.usage.probe(
                        delta_access=-evicted_block.count_accessed(),
                        delta_valid=-st.Cache.line_size)
                    if evicted_block.dirty:
                        # WRITE DIRTY BLOCK
                        self.modules.memaccess.probe('w') # write
                    else:
                        # DROP CLEAN BLOCK
                        pass
                resident_block = fetched_block
            else:
                # HIT
                resident_block = self.blocks_in_cache[(p_tag,set_index)]
                self.modules.missratio.probe(access, (1,0)) # hit++
                self.sets[set_index].touch_block(resident_block)

            # mark accessed bytes
            old_ab = resident_block.count_accessed()
            resident_block.access(offset, this_block_n_bytes, write=writing)
            new_ab = resident_block.count_accessed()
            self.modules.usage.probe(delta_access=new_ab-old_ab)

            # update address and reminding bytes to continue accessing memory
            addr += this_block_n_bytes
            n_bytes -= this_block_n_bytes
        return

    def __flush(self):
        """evict all cache lines"""
        for set_idx in range(st.Cache.num_sets):
            s = self.sets[set_idx]
            evicted_block = s.pop_lru_block()
            tag_out = None if evicted_block is None else evicted_block.tag
            while evicted_block is not None:
                tag_out = evicted_block.tag
                #!self.modules.evicd.update(st.Map.time_size, set_idx, None,
                #!                          tag_out)

                # It doesn't make much sense to register usage on flush
                # self.modules.usage.probe(
                #     delta_access=-evicted_block.count_accessed(),
                #     delta_valid=st.Cache.line_size)


                if evicted_block.dirty:
                    self.modules.memaccess.probe('w')
                    pass #!
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

    def run_simulation(self, map_data_reader):
        """Run the simulation sending concurrent accesses to the cache
        in batches. At the end, flush the cache and send a last commit
        to the cache."""
        # check cache alignment of the allocated memory
        _,_,byte = st.AddrFmt.split(st.Map.start_addr)
        if byte != 0:
            UI.info(f'Allocated memory is not cache aligned, first '
                    f'address is {byte} bytes into a cache line.')

        # send batches with concurrent accesses to the cache.
        tot_eve = st.Map.event_count
        eve_count = -1
        concurrent_acc = []
        for record in map_data_reader:
            eve_count += 1
            # collect all accesses happening at the same time mark
            if len(concurrent_acc) == 0 or concurrent_acc[-1].time == record.time:
                concurrent_acc.append(record)
                continue
            self.__accesses(concurrent_acc) # send all accesses from time t-1
            UI.progress(eve_count, tot_eve)
            concurrent_acc = [record] # save first access of time t

        # send the remaining accesses to the cache
        eve_count += 1
        self.__accesses(concurrent_acc)
        UI.progress(eve_count, tot_eve)
        UI.nl()
        # flush cache and commit for modules that care about eviction
        self.__flush()
        self.modules.commit(st.Map.time_size-1)

        # signal to all modules that the simulation has finished
        self.modules.finalize()
        return
