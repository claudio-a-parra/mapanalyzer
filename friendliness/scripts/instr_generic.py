#!/usr/bin/env python3
import sys
#from collections import deque

class GenericInstrument:
    def __init__(self, instr_counter):
        self.enabled = True
        self.ic = instr_counter
        self.events = []
        self.X = []
        self.Y = []

        self.plot_filename_sufix = '_filename-sufix'
        self.plot_title = 'Title'
        self.plot_subtitle = 'Subtitle'
        self.plot_y_label = 'Y label'
        self.plot_x_label = 'X label'
        self.plot_min = 0
        self.plot_max = 1
        self.plot_color_fg1 = '#000000FF' # black 100% opaque
        self.plot_color_fg2 = '#00000066' # black  40% opaque
        self.plot_color_bg =  '#FFFFFF00' # white   0% opaque, transparent.


        #
        # self.events = deque()
        # # details for the plots of this instrument.
        # self.plot_details = ('_sufix', 'title', 'subtitle', 'y-axis',
        #                      0, 1) #min and max range



    def _create_up_to_n_ticks(self, full_list, base=10, n=10):
        """
        return a list of ticks based on full_list. The idea is to find
        nice numbers (multiples of powers of 10 or 2) and not having
        more than n elements.
        """
        # find a label_step such that we print at most n ticks
        tick_step = 1
        tot_ticks = len(full_list)
        factors = [1,2,5] if base==10 else [1,1.5]
        for i in range(14):
            found = False
            for n in factors:
                n_pow_base = int(n * (base ** i))
                if tot_ticks // n_pow_base < n:
                    tick_step = n_pow_base
                    found = True
                    break
            if found:
                break
        return full_list[::tick_step]


''' COMMENT START


        # event to dequeue from self.events if the queried instruction did not
        # generate events. if self.last_event_is_default == True, then the default is
        # constantly updated to the last real event.
        ##self.default_event = None
        ##self.last_event_is_default = False
        # log with as much events as instructions, and the filtered log with
        # averages of sliding windows.
        ##self.full_events_log = []
        ##self.filtered_avg_log = []
        ##self.window_size = -1
        # this is the aggregated value of 'window' elements of the log. Used
        # in the filter process to quickly update the moving average.
        ##self.last_window_summary = None












    def mix_events(self, base, new):
        """Return a mixed event based on two events 'base' and 'new'"""
        raise NotImplementedError("Overwrite this method")

    def avg_events(self, left, right):
        """Consider the slice self.full_events_log[left:right], and the compact
        counter self.last_window_summary. If the latter is None, then compute
        it from the slice. Otherwise, just subtract self.full_event_log[left-1]
        and add self.full_event_log[right-1] to the summary. Once the summary
        is computed, get the average and return it."""
        raise NotImplementedError("Overwrite this method")

    def queue_event(self, new_event):
        """Add event related to the current instruction to the events queue. If
        there is already an event for the current instruction, mix both events."""
        ic = self.ic.val()
        if len(self.events) == 0 or self.events[-1][0] != ic:
            self.events.append((ic,new_event))
        else:
            curr_event = self.events[-1][1]
            mixed_event = self.mix_events(curr_event, new_event)
            self.events[-1] = (ic, mixed_event)

    def deque_event(self, query_instr):
        """Return the event produced by query_instr, or default_event."""
        if len(self.events) == 0 or self.events[0][0] != query_instr:
            return self.default_event
        _, curr_event = self.events.popleft()
        # update default event
        if self.last_event_is_default:
            self.default_event = curr_event
        return curr_event

    def build_log(self, instruction_ids_list):
        """Build this instrument's log with exactly one entry per
        instruction. If a given instruction produced no event, then
        fill the gap with the default event"""
        if self.verbose:
            print(f"{self.__class__.__name__}.full_events_log: ")
        for ic in instruction_ids_list:
            event = self.deque_event(ic)
            if self.verbose:
                print(f"    {event}")
            self.full_events_log.append(event)
        return

    def filter_log(self, win):
        """Compute a moving avg window from self.full_events_log and populate
        self.filtered_avg_log. Use self.avg_slice() to reduce a slice to
        the single value that represents this instrument."""
        n = len(self.full_events_log)
        # check if empty full_events_log or window is too large
        if n == 0:
            print(f"Error: {self.__class__.__name__}: self.full_events_log is empty. "
                  "Cannot filter it.")
            sys.exit(1)
        # check invalid window
        if win <= 0 or n < win:
            print(f"Error: {self.__class__.__name__}: Invalid given window "
                  f"size {win} for self.full_events_log of size {n}.")
            sys.exit(1)
        self.window_size = win
        # fill the first (win-1) elements with 0, as there are no averages yet.
        self.filtered_avg_log = [0] * (win-1)

        # left and right are valid indices. They are both accessed, so they
        # must be in range.
        for left in range(n - win + 1):
            right = left + win - 1
            #raw_slice = self.full_events_log[left:right]
            # avg = self.avg_events(raw_slice)
            avg = self.avg_events(left, right)
            self.filtered_avg_log.append(avg)

    def plot(self, axes, X=None, Y=None, col_line='black', zorder=1,
             extent=None):
        if X==None or Y==None:
            print(f'[!] Error: array X or Y cannot be None.')
            sys.exit(1)
        # TODO: set owns Y-limits

        # Plot its data
        axes.bar(X, Y, color=col_line, width=1, zorder=zorder)
        axes.axhline(y=0, color=col_line, linestyle='-', linewidth=1,
                     zorder=zorder+1)
        return

COMMENT END '''
