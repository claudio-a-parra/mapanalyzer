#!/usr/bin/env python3

class InstrCounter:
    """Instruction Counter"""
    def __init__(self):
        self.counter = 0
    def step(self):
        self.counter += 1
    def set(self, new_val):
        self.counter = new_val
    def val(self):
        return self.counter




class Instruments:
    def __init__(self, instr_counter, line_size_bytes):
        self.alias = Alias(instr_counter)
        self.hit_miss = HitMiss(instr_counter)
        self.line_usage = LineUsage(instr_counter, line_size_bytes)
        self.siu_eviction = SIUEviction(instr_counter)

    def report(self):
        """Report the logs of every instrument"""
        pass
        return


class Alias:
    """Keep track of the access ratio to each Set in the cache"""
    def __init__(self, instr_counter):
        self.enabled = True
        self.ic = instr_counter
        self.log = [] # here is where the measurement is logged
        self.set_counters = {} # counters for each set

    def append(self, index):
        self.log.append((self.ic.val(), index))



class HitMiss:
    """Keep track of hits and misses."""
    def __init__(self, instr_counter):
        self.enabled = True
        self.ic = instr_counter
        self.log = [] # here is where the measurement is logged
        self.HIT = 0
        self.MISS = 1

    def append_hit(self):
        self.log.append((self.ic.val(), self.HIT))

    def append_miss(self):
        self.log.append((self.ic.val(), self.MISS))




class LineUsage:
    """Keep track of the ratio of line usage by the time the line gets
    evicted"""
    def __init__(self, instr_counter, line_size_bytes):
        self.enabled = True
        self.ic = instr_counter
        self.line_size_bytes = line_size_bytes
        self.log = [] # here is where the measurement is logged
        self.updates = 0

    def append(self, accessed):
        """Store the number of bytes actually accessed in the recently
        evicted line"""
        if not self.enabled:
            return
        self.log.append((self.ic.val(), accessed))




class SIUEviction:
    """
    Let's define:
    - block         : group of bytes (data)
    - line          : space in Cache to store a block
    - line fetching : bringing a block from RAM.
    - line evicting : writing a block back to RAM.
    - SIU Eviction  : 'still-in-use' Eviction, eviction of a block that will
                      later be fetched back to Cache again.
    This counter works in two passes:
      - First pass: Fetch mode: We count all the times each block was fetched.
        Each fetch is a +1 to the counter of that particular block.
      - Second pass: Evict mode: With each eviction of a given block, we
        decrement its fetch counter. If after decrementing, the counter is NOT
        zero, then we know that the same block will be brought back to cache
        later, so this is a 'still-in-use' eviction.
    """
    def __init__(self, instr_counter):
        self.enabled = True
        self.ic = instr_counter
        self.log = [] # here is where the measurement is logged
        self.fetch_counters = {}
        self.mode = 'fetch'

    def set_mode(mode):
        """
        We run the first pass in fetch mode to fill the counters. The
        second pass is in evict mode to check for 'still-in-use evictions'
        """
        if not self.enabled:
            return
        if mode in ('fetch', 'evict'):
            self.mode = mode
        else:
            raise ValueError("Value of mode must be 'fetch' or 'evict'")


    def append_fetch(self, index, tag):
        if not self.enabled:
            return
        if self.mode != 'fetch':
            return
        if (index, tag) in self.fetch_counters:
            self.fetch_counters[(index, tag)] += 1
        else:
            self.fetch_counters[(index, tag)] = 1
        return 0


    def append_evict(self, index, tag):
        """
        If in 'evict' mode, then return True if this is a 'still-in-use'
        eviction, False otherwise.
        """
        if not self.enabled:
            return
        if self.mode != 'evict':
            return
        # decrement fetch counter
        if (index, ev_tag) in self.fetch_counters:
           self.fetch_counters[(index, tag)] -= 1
        else:
            raise Exception("Trying to register eviction without a previous fetch")
        # detect still-in-use fetch
        fetches = self.fetch_counters[(index, tag)]
        if fetches > 0:
            return True
            self.log.append((self.ic.val(),1))
        elif fetches == 0:
            self.log.append((self.ic.val(),0))
        else:
            raise Exception(f"There are more evictions than fetches for "
                            "tag:{tag}, index:{index}")
        return 0
