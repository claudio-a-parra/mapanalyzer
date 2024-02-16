#!/usr/bin/env python3
import sys
import matplotlib.pyplot as plt
from instr_generic import GenericInstrument

#-------------------------------------------
class Miss(GenericInstrument):
    """
    Definition:
        The proportion of cache misses with respect to all cache requests.
        (misses + hits).

    Captured Events:
        Every time there is a hit or a miss (this is, any cache access) a
        tuple with two counters is created: (miss, hit). Each of these two
        counters has the total cumulative count of all misses and hits.

    Plot interpretation:
        The plot is a line that ranges from 0% to 100% showing the proportion
        of cache misses at that point.
    """
    def __init__(self, instr_counter, verb=False):
        super().__init__(instr_counter, verb=verb)

        self.miss_count = 0
        self.hit_count = 0
        self.zero_counter = (0,0)

        self.plot_name_sufix = '_plot-02-miss'
        self.plot_title      = 'Miss Ratio'
        self.plot_subtitle   = 'lower is better'
        self.plot_y_label    = 'Cache Misses [%]'
        self.plot_color_text = '#0000AA'   # dark blue
        self.plot_color_line = '#0000FFCC' # blue almost opaque
        self.plot_color_fill = '#0000FF44' # blue semi-transparent
        return


    def _pad_events_list(self, new_index):
        while len(self.events) < new_index:
            self.events.append(self.zero_counter)
        return


    def register(self, delta_miss=0, delta_hit=0):
        if not self.enabled:
            return

        # update existing counter, or add a new one.
        event_idx = self.ic.val() # note that ic may skip values.
        if event_idx < len(self.events):
            # if the events[event_idx] exists, then just update it
            m,h = self.events[event_idx]
            self.events[event_idx] = (m+delta_miss, h+delta_hit)
            if event_idx+1 == len(self.events):
                # if we happen to have just edited the last event,
                # then the miss/hit counters need to be updated
                self.miss_count += delta_miss
                self.hit_count += delta_hit
        else:
            # otherwise, pad events with zero counters so that
            # the index of a new append() is event_idx
            self._pad_events_list(event_idx)
            # update counters
            self.miss_count += delta_miss
            self.hit_count += delta_hit
            self.events.append((self.miss_count, self.hit_count))
        return


    def _create_plotting_data(self):
        # create the list of percentages based on the counts in self.events.
        # This is straight forward:
        #    percentage = 100 * misses/(misses+hits)
        for misses,hits in self.events:
            percentage = 100 * misses/(misses+hits)
            self.Y.append(percentage)
        self.events = None # hint GC
        return


    def get_extent(self):
        # fine tune margins to place each quadrilateral of the imshow()
        # right on the tick. So adding a 0.5 margin at each side.
        left_edge = self.X[0] - 0.5
        right_edge = self.X[-1] + 0.5
        bottom_edge = 0 - 0.5
        top_edge = 100 + 0.5 # 100% + a little margin
        extent = (left_edge, right_edge, bottom_edge, top_edge)
        return extent


    def plot(self, axes, basename='miss', extent=None):
        # check if self.X has been filled
        if self.X == None:
            print('[!] Error: Please assign '
                  f'{self.__class__.__name__ }.X before calling plot()')
            sys.exit(1)

        # transform list of events into list of plotable data in self.Y
        self._create_plotting_data()

        # set plot limits
        extent = extent if extent != None else self.get_extent()
        axes.set_xlim(extent[0], extent[1])
        axes.set_ylim(extent[2], extent[3])

        # draw the curve and area below it
        axes.step(self.X, self.Y, color=self.plot_color_line,
                          linewidth=1.2, where='mid', zorder=2)
        axes.fill_between(self.X, -1, self.Y, color='none',
                          facecolor=self.plot_color_fill,
                          linewidth=1.2, step='mid', zorder=1)

        # setup title
        axes.set_title(f'{self.plot_title}: {basename}\n'
                       f'({self.plot_subtitle})')

        # setup Y ticks
        axes.tick_params(axis='y', which='both',
                         left=True, right=False,
                         labelleft=True, labelright=False)
        percentages = list(range(100 + 1)) # from 0 to 100
        y_ticks = self._create_up_to_n_ticks(percentages, base=10, n=5)
        axes.set_yticks(y_ticks)

        # setup Y label
        axes.yaxis.set_label_position('left')
        axes.set_ylabel(self.plot_y_label, color=self.plot_color_text,
                        labelpad=3.5)

        # setup Y grid
        axes.grid(axis='y', which='both', linestyle='-', alpha=0.2,
                  color=self.plot_color_line, linewidth=0.8, zorder=3)

        return
