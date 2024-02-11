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
class Alias(GenericInstrument):
    """
    - Definition : The distribution of sets usage. Y-axis is the list of all
                   sets, and for each instruction, every set shows their "share"
                   of usage.
    - Range      : Each set in a given instruction can have values from 0 to 1.
                   0: this set has not been used so far (not in this instruction
                      or previous ones
                   1: this set has been the only one ever used.
    - Events     : Array of cumulative counters, one for each set.
    - Trigger    : Block fetches.
    """
    def __init__(self, instr_counter, num_sets):
        super().__init__(instr_counter)

        self.num_sets = num_sets

        self.plot_filename_sufix = '_plot-01-alias'
        self.plot_title = 'Aliasing'
        self.plot_subtitle = 'transparent is better'
        self.plot_y_label = 'Set Index'
        self.plot_x_label = 'Instruction'
        self.plot_min = 0
        self.plot_max = 1
        self.plot_color_fg1 = '#ffa500ff' # orange 100% opaque
        self.plot_color_fg2 = '#ffa50066' # orange  40% opaque
        self.plot_color_bg =  '#FFFFFF00' # white    0% opaque, transparent.


    def _fill_events_list(self, next_index):
        # pad self.events such that upon appending a new element, its
        # index becomes next_index. If self.events already has next_index
        # on it, do not touch self.events.
        if len(self.events) < next_index:
            if len(self.events) == 0:
                self.events.append([0]*self.num_sets)
            while len(self.events) < next_index:
                self.events.append(self.events[-1])


    def _new_counter(self, set_index):
        if len(self.events) == 0:
            new_counter = [0] * self.num_sets
        else:
            new_counter = [x for x in self.events[-1]]
        new_counter[set_index] += 1 #register usage.
        return new_counter


    def _update_or_append_event(self, index, subindex):
        # if self.events[index] exists, then update its value,
        # otherwise, append a new counter to self.events
        if index < len(self.events):
            self.events[index][subindex] += 1
        else:
            new_counter = self._new_counter(subindex)
            self.events.append(new_counter)


    def register_set_usage(self, set_index):
        if not self.enabled:
            return
        self._fill_events_list(self.ic.val())
        self._update_or_append_event(self.ic.val(), set_index)


    def _create_plotting_data(self):
        print(f'        Creating Normalized Matrix.')
        # self.events cannot be plot right away because of two reasons:
        # 1. each item is a list of num_sets counters. we need values from
        #    0 to 1 that represents the proportion of usage:
        #      - 0=perfect,
        #      - 1=all fetches in the same set.
        # 2. self.events is a list of columns. imshow() needs a list of rows,
        #    so we need to transpose it.

        # create matrix filled with zeroes, of size transposed(self.events)
        self.Y = [[0] * len(self.events) # each row
                  for _ in range(len(self.events[0]))]

        # place the normalized proportions of self.events[x][y] in
        # self.Y[y][x]
        base_proportion = 1/self.num_sets
        normal_factor = 1 - base_proportion
        for instr_idx,counters_arr in enumerate(self.events):
            # if there is nothing to count, keep the zeroes in Y
            all_count = sum(counters_arr)
            if all_count == 0:
                continue
            for set_idx, raw_count in enumerate(counters_arr):
                self.Y[set_idx][instr_idx] = \
                    max(0,
                        ((raw_count / all_count) - base_proportion) \
                        * normal_factor
                        )
        self.events = None # hint GC

    
    def plot(self, axes, zorder=1, window=1):
        # check if self.X has been filled
        if self.X == None:
            print('[!] Error: Please assign '
                  f'{self.__class__.__name__ }.X before calling '
                  'plot()')
            sys.exit(1)

        # create color shade
        colors = [self.plot_color_bg, self.plot_color_fg1]
        shade_cmap = mcolors.LinearSegmentedColormap.from_list(
            'transparency_cmap', colors)

        # transform list of events into list of plottable data in self.Y
        self._create_plotting_data()

        # fine tune margins to place each quadrilateral of the imshow()
        # right on the tick. So adding a 0.5 margin at each side.
        left_edge = self.X[0] - 0.5
        right_edge = self.X[-1] + 0.5
        bottom_edge = 0 - 0.5
        top_edge = self.num_sets + 0.5
        extent = (left_edge, right_edge, bottom_edge, top_edge)

        # create ticks for X and Y axis.
        x_ticks = self._create_up_to_n_ticks(self.X, base=10, n=20)
        axes.set_xticks(x_ticks)
        set_indices = list(range(self.num_sets))
        y_ticks = self._create_up_to_n_ticks(set_indices, base=2, n=10)
        axes.set_yticks(y_ticks)

        # plot the image.
        axes.imshow(self.Y, cmap=shade_cmap, interpolation=None,
                    aspect='auto', extent=extent, zorder=zorder,
                    vmin=0, vmax=1)

        axes.grid(axis='x', linestyle='-', alpha=0.7,
                  linewidth=0.8, which='both', zorder=zorder+1)
        return extent
