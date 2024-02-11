#!/usr/bin/env python3
import sys
import random # DEBUG
from collections import deque
import matplotlib as mpl
# increase memory for big plots. Bruh...
mpl.rcParams['agg.path.chunksize'] = 10000000000000
import matplotlib.pyplot as plt
from matplotlib.colors import ListedColormap
import matplotlib.colors as mcolors # to create shades of colors from list

from instr_generic import GenericInstrument

#-------------------------------------------
class SIURatio(GenericInstrument):
    """
    - Definition: Ratio between number of evictions on blocks that will later
                  be fetched again, vs the total number of evictions done.
    - Range     : 0: every block eviction is final.
                  1: every block evicted by this instruction (or slice) is
                     later fetched back to memory.
    - Event     : tuple with two counters (siu_evictions, total_evictions)
    - Trigger   : In the first pass, only fetches trigger the instrument; but
                  the actual SIU counting happens in the second pass with
                  every eviction.

    This is an special counter, because it needs to pass through the memory
    access pattern two times in order to be computed.
      - First pass: Fetch mode: We count all the times each block was fetched.
        Each fetch is a +1 to the counter of that particular block.
      - Second pass: Evict mode: With each eviction of a given block, we
        decrement its fetch counter. If after decrementing, the counter is NOT
        zero, then we know that the same block will be brought back to cache
        later, so this is a 'still-in-use' eviction.
    """
    def __init__(self, instr_counter):
        super().__init__(instr_counter)
        self.default_event = (0,0)
        # to register the fetches number of fetches performed on each block.
        self.fetch_counters = {}
        # We run the first pass in fetch mode to fill the block's fetch counter.
        # The second pass runs in evict mode to use the previous counters to
        # check for 'still-in-use evictions'
        self.mode = 'fetch'
        self.plot_details = ('_plot-04-siu-eviction-ratio', # file sufix
                             'Still-in-Use Block Eviction', # plot title
                             'less is better', # subtitle
                             '"I\'ll be back" Ratio', # Y axis name
                             0, 1) # min-max

    def register_fetch(self, index, tag):
        if not self.enabled or self.mode != 'fetch':
            return
        block_id = (index, tag)
        if block_id in self.fetch_counters:
            self.fetch_counters[block_id] += 1
        else:
            self.fetch_counters[block_id] = 1
        if self.verbose:
            t = hex(tag)[2:]
            i = hex(index)[2:]
            print(f"[!] {self.__class__.__name__}: "
                  f"fetch(s:{i},tag:{t})={self.fetch_counters[block_id]}")
        return 0

    def register_evict(self, index: int, tag: int):
        """
        Given the first pass, we already know how many times we ever fetch
        each block. Now, in this eviction, check whether the current block
        is later fetched again. If that is the case, add a 'still-in-use'
        eviction to the log.
        """
        if not self.enabled or self.mode != 'evict':
            return
        # for every earlier fetch of a block, there should be an eviction,
        # then, this eviction decrements the fetch counter of this block.
        block_id = (index, tag)
        if block_id in self.fetch_counters:
           self.fetch_counters[block_id] -= 1
        else:
            raise Exception("Trying to register eviction without a previous "
                            "fetch")
        # detect still-in-use eviction: if after the above decrementing the
        # counter is still greater than 0, then we are evicting an
        # 'still-in-use' block.
        resulting_fetches = self.fetch_counters[block_id]
        if resulting_fetches > 0: # the block is later fetched again.
            new_event = (1, 1)
            if self.verbose:
                print(f"[!] {self.__class__.__name__}: "
                      "still-in-use eviction!")
        elif resulting_fetches == 0:
            new_event = (0, 1)
            if self.verbose:
                print(f"[!] {self.__class__.__name__}: "
                      "last eviction")
        else:
            raise Exception(f"There are more evictions than fetches for "
                            f"tag:{hex(tag)}, index:{hex(index)}")

        self.queue_event(new_event)
        return

    def mix_events(self, base, new):
        curr_siu,curr_tot = base
        new_siu,new_tot = new
        return (curr_siu+new_siu, curr_tot+new_tot)

    def avg_events(self, left, right):
        # If there was no previous summary, construct it.
        if self.last_window_summary == None or left == 0:
            self.last_window_summary = [0,0] # [siu_evic, tot_evic]
            counters = self.last_window_summary
            for siu,tot in self.full_events_log[left:right+1]:
                counters[0] += siu
                counters[1] += tot

        else: # if there was a summary, just update the counters
            counters = self.last_window_summary
            retiring_siu, retiring_tot = self.full_events_log[left-1]
            incoming_siu, incoming_tot = self.full_events_log[right]
            counters[0] += incoming_siu - retiring_siu
            counters[1] += incoming_tot - retiring_tot

        # Now, having the counters of this window, construct the average
        # of the window.
        window_siu,window_tot = self.last_window_summary
        if window_tot == 0:
            if window_siu > 0:
                print(f"Error: {self.__class__.__name__}: Total evictions is 0 "
                      f"for the given slice, but {window_siu} evictions are "
                      "reported to be SIU")
                sys.exit(1)
            else:
                # no siu or other evictions means we are just reading from
                # valid caches. That is good -> return 0
                return 0
        return window_siu / window_tot

