#!/usr/bin/env python3
import sys
from instr_generic import GenericInstrument

#-------------------------------------------
class ByteUsageRatio(GenericInstrument):
    """
    - Definition: Ratio measuring valid bytes in cache that were actually
                  accessed vs the total number of valid bytes in the cache.
                  (valid_accessed)/(total_valid)
    - Range     : 0: none of the valid bytes has been accessed. Only achievable
                     by manually fetching blocks to cache. Bad.
                  1: all bytes in cache have been accessed at least once. (Good)
    - Event     : Tuple with two counters: (acc, val), that is, current count
                  for accessed valid bytes in cache, and current total valid
                  bytes in cache.
    - Trigger   : Evictions, Fetches, and Accesses to valid lines:
                  - Evictions: remove (valid) accessed bytes, remove valid
                               bytes.
                  - Fetches: add new valid bytes.
                  - Access (to valid lines): add accessed bytes.
    """
    def __init__(self, instr_counter, line_size_bytes):
        super().__init__(instr_counter)
        self.default_event = (0,0)
        self.last_event_is_default = True
        self.line_size_bytes = line_size_bytes
        self.accessed_bytes = 0
        self.valid_bytes = 0
        self.plot_details = ('_plot-03-unused-bytes-ratio', # file sufix
                             'Unused Valid Bytes', # plot title
                             'less is better', # subtitle
                             'Unused Bytes Ratio', # Y axis name
                             0, 1) # min-max

    def register_delta(self, delta_access, delta_valid):
        """Update the counters:
        - positive delta_access: newly accessed bytes.
        - negative delta_access: bytes that have been accessed are now evicted.
        - positive delta_valid: fetching block.
        - negative delta_valid: evicting block."""
        if not self.enabled:
            return
        # update current counters
        self.accessed_bytes += delta_access
        self.valid_bytes += delta_valid
        if self.verbose:
            print(f"[!] {self.__class__.__name__}: "
                  f"{self.accessed_bytes}/{self.valid_bytes}")

        event = (self.accessed_bytes, self.valid_bytes)
        self.queue_event(event)

    def mix_events(self, base, new):
        """ the new counter just replace the old one, as this is more updated"""
        return new

    def avg_events(self, left, right):
        # If there was no previous summary, construct it.
        if self.last_window_summary == None or left == 0:
            self.last_window_summary = [0,0] # [used, valid]
            counters = self.last_window_summary
            for used,valid in self.full_events_log[left:right+1]:
                counters[0] += used
                counters[1] += valid
        # If there was summary, remove left-1, and add right events
        else:
            counters = self.last_window_summary
            retiring_used, retiring_valid = self.full_events_log[left-1]
            incoming_used, incoming_valid = self.full_events_log[right]
            counters[0] += incoming_used - retiring_used
            counters[1] += incoming_valid - retiring_valid

        tot_used = counters[0]
        tot_valid = counters[1]

        if tot_valid == 0:
            # not having valid bytes is a problem only if there are also
            # used bytes, otherwise the usage can be understood as 0
            if tot_used > 0:
                print(f"Error: {self.__class__.__name__}: Total valid bytes "
                      "is 0 for the given slice, but used bytes is not 0.")
                sys.exit(1)
            else:
                return 0
        return (tot_valid - tot_used) / tot_valid
