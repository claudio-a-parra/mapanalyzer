#!/usr/bin/env python3
import sys
import math # log function
from collections import deque
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker
import matplotlib.colors as mcolors # to create shades of colors from list

from instr_generic import GenericInstrument

#-------------------------------------------
class Alias(GenericInstrument):
    """
    Definition:
        The distribution of sets usage. Y-axis is the list of all sets, and for
        each instruction, every set shows the proportion of fetches they have
        effected.

    Captured Events:
        An event is captured at every cache block fetching.
        Each event is an array of S counters, where S is the total number of
        sets. The counter keeps track of all the fetches effected by that
        cache set.

    Plot Interpretation:
        In every point of time where a cache block fetch is done, all sets
        show their updated proportion of the total number of fetches ever done
        so far.
        If at some point of time no cache block fetch is triggered, then show
        nothing.
        The proportion of cache fetches is shown as boxes that range from
        transparent (0) to opaque (1):
            - 0: this set has attended between 0 to 1/S of the total number of
                 fetches. This is good, a perfect distribution is S sets, each
                 sharing 1/S of the total number of fetches.
            - 1: this set has attended all the fetches.
    """
    def __init__(self, instr_counter, num_sets, verb=False):
        super().__init__(instr_counter, verb=verb)

        self.num_sets = num_sets
        self.last_counter = [0] * num_sets
        self.zero_counter = [0] * num_sets

        self.plot_name_sufix  = '_plot-01-alias'
        self.plot_title       = 'Aliasing'
        self.plot_subtitle    = 'transparent is better'
        self.plot_y_label     = 'Set Index'
        self.plot_color_text  = '#E09200FF' # dark orange
        self.plot_color_boxes = '#ffa500FF' # orange opaque
        self.plot_color_bg    = '#FFFFFF00' # transparent
        return


    def _pad_events_list(self, new_index):
        # Always true: new_index >= len(self.events)
        if len(self.events) != 0:
            # save last real counter
            self.last_counter = self.events[-1]
        while len(self.events) < new_index:
            # and pad with zeroes
            self.events.append(self.zero_counter)
        return


    def register(self, tag, set_index):
        if not self.enabled:
            return
        if self.verb:
            print(f'ALI: fetch t:{tag}, i:{set_index}')
        # update existing counter, or add a new one.
        event_idx = self.ic.val() # note that ic may skip values.
        if event_idx < len(self.events):
            # if the events[event_idx] exists, then just update it
            self.events[event_idx][set_index] += 1
        else:
            # otherwise, pad events with zero counters so that
            # events[event_idx] now exists.
            self._pad_events_list(event_idx)
            # deep copy the last real counter, and update the set's count
            new_event = [x for x in self.last_counter]
            new_event[set_index] += 1
            self.events.append(new_event)
            # update the last non-zero counter
            self.last_counter = new_event
        return

    def _log_mapping(self, x):
        # Apply logarithmic mapping to input values
        return math.log(1 + 9 * x) / math.log(10)


    def _create_plotting_data(self, kind='linear'):
        # self.events cannot be plot right away because of three reasons:
        # 1. There are most likely more time points than alias counters. We
        #    need to pad the list of counters so that it nicely matches the
        #    timeline array.
        # 2. each item is a list of num_sets counters. we need values from
        #    0 to 1 that represents the proportion of usage:
        #      - 0=perfect,
        #      - 1=all fetches in the same set.
        #    This mapping can be 'linear' or 'log' (ln)
        # 3. self.events is a list of columns. imshow() needs a list of rows,
        #    so we need to transpose it.

        # pad self.events to match the length of self.X
        while len(self.events) < len(self.X):
            self.events.append(self.zero_counter)

        # create matrix filled with zeroes, of size transposed(self.events)
        self.Y = [[0] * len(self.events) # each row
                  for _ in range(len(self.events[0]))]

        # place the normalized proportions of self.events[x][y] in
        # self.Y[y][x]
        base_proportion = 1/self.num_sets
        if self.num_sets == 1:
            normal_factor = 1
        else:
            normal_factor = (self.num_sets) / (self.num_sets - 1)
        for instr_idx,counters_arr in enumerate(self.events):
            # if there is nothing to count, keep the zeroes in Y
            all_count = sum(counters_arr)
            if all_count == 0:
                continue
            for set_idx, one_set_raw_count in enumerate(counters_arr):
                linear_ratio = \
                    ((one_set_raw_count / all_count) - base_proportion) \
                    * normal_factor
                # if the raw counter is zero, then the linear_ratio should
                # be zero, not a negative value.
                linear_ratio = max(0,linear_ratio)
                log_ratio = self._log_mapping(linear_ratio)
                val = log_ratio if kind=='log' else linear_ratio
                self.Y[set_idx][instr_idx] = val
        self.events = None # hint GC
        return

    def get_extent(self):
        # fine tune margins to place each quadrilateral of the imshow()
        # right on the tick. So adding a 0.5 margin at each side.
        left_edge = self.X[0] - 0.5
        right_edge = self.X[-1] + 0.5
        bottom_edge = 0 - 0.5
        top_edge = (self.num_sets-1) + 0.5 # I want the max index + margin
        extent = (left_edge, right_edge, bottom_edge, top_edge)
        return extent


    def plot(self, axes, basename='alias', extent=None, kind='log'):
        # check if self.X has been filled
        if self.X == None:
            print('[!] Error: Please assign '
                  f'{self.__class__.__name__ }.X before calling plot()')
            sys.exit(1)

        # create color shade
        colors = [self.plot_color_bg, self.plot_color_boxes]
        shade_cmap = mcolors.LinearSegmentedColormap.from_list(
            'transparency_cmap', colors)

        # transform list of events into list of plotable data in self.Y
        self._create_plotting_data(kind=kind)

        # draw the image and invert Y axis (so lower value is on top)
        extent = extent if extent != None else self.get_extent()
        axes.imshow(self.Y, cmap=shade_cmap, origin='lower', interpolation=None,
                    aspect='auto', extent=extent, zorder=1, vmin=0, vmax=1)
        axes.invert_yaxis()

        # setup title
        axes.set_title(f'{self.plot_title}: {basename}\n'
                       f'({self.plot_subtitle})')

        # setup Y ticks
        axes.tick_params(axis='y', which='both',
                         left=True, right=False,
                         labelleft=True, labelright=False)
        set_indices = list(range(self.num_sets))
        y_ticks = self._create_up_to_n_ticks(set_indices, base=2, n=9)
        axes.set_yticks(y_ticks)

        # setup Y label
        axes.yaxis.set_label_position('left')
        if y_ticks[-1] < 100:
            pad = 10
        if y_ticks[-1] < 10:
            pad = 16
        axes.set_ylabel(self.plot_y_label, color=self.plot_color_text,
                        labelpad=pad)

        # setup Y grid
        axes.grid(axis='y', which='both', linestyle='-', alpha=0.2,
                  color=self.plot_color_boxes, linewidth=0.8, zorder=2)
        return
