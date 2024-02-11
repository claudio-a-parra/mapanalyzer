#!/usr/bin/env python3
import sys
from instr_generic import GenericInstrument

#-------------------------------------------
class MissRatio(GenericInstrument):
    """
    - Definition : The proportion of Cache misses with respect to all miss or
                   hits (miss/(miss+hit))
    - Range      : 0: no instruction triggers a cache miss. Good.
                   1: all instructions trigger cache misses. Bad.
    - Events     : i-th event is a tuple of two counters: (cm, ch), that is,
                   cache miss count and cache hit count produced by the
                   i-th instruction.
    - Trigger    : Every access to memory (because it will trigger either a
                   miss or a hit). A single instruction may access multiple
                   blocks.
    """
    def __init__(self, instr_counter):
        super().__init__(instr_counter)
        self.default_event = (0,0)
        self.plot_details = ('_plot-02-miss-ratio', # file sufix
                             'Cache Miss', # plot title
                             'less is better', # subtitle
                             'Cache Miss Ratio', # Y axis name
                             0, 1) # min-max

    def register_miss(self):
        if not self.enabled:
            return
        if self.verbose:
            print(f"[!] {self.__class__.__name__}: MISS")
        self.queue_event((1,0)) # add one miss

    def register_hit(self):
        if not self.enabled:
            return
        if self.verbose:
            print(f"[!] {self.__class__.__name__}: HIT")
        self.queue_event((0,1)) # add one hit

    def mix_events(self, base, new):
        mc,hc = base
        new_mc,new_hc = new
        return (mc+new_mc, hc+new_hc)

    def avg_events(self, left, right):
        # If there was no previous summary, construct it.
        if self.last_window_summary == None or left == 0:
            self.last_window_summary = [0,0] # [misses, hits]
            counters = self.last_window_summary
            for miss,hit in self.full_events_log[left:right+1]:
                counters[0] += miss
                counters[1] += hit

        else: # if there was a summary, just update the counters
            counters = self.last_window_summary
            retiring_miss, retiring_hit = self.full_events_log[left-1]
            incoming_miss, incoming_hit = self.full_events_log[right]
            counters[0] += incoming_miss - retiring_miss
            counters[1] += incoming_hit - retiring_hit

        # Now, having the counters of this window, construct the average
        # of the window.
        window_miss,window_hit = self.last_window_summary
        if window_miss + window_hit == 0:
            print(f"Error: {self.__class__.__name__}: total miss+hit in slice "
                  "is 0. This should be impossible.")
            sys.exit(1)
        return window_miss / (window_miss + window_hit)

