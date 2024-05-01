#!/usr/bin/env python3
import sys
import math # log function
from collections import deque
import matplotlib.colors as mcolors # to create shades of colors from list

from .generic import GenericInstrument

class BufferedTrace:
    win_size = 64*8 # number of sets
    num_sets = 1
    def __init__(self):
        # buffer with incoming elements
        self.buffer = deque()
        # resulting values obtained from each window extracted from the buffer
        self.window_values = []


    def add_to_buffer(self, instr_id, set_index):
        """Add an element to the buffer. If its logical size is big enough,
        create a window, compute its value, and append it to the window_values
        list."""
        self.buffer.append(set_index)
        # While there are enough elements in the buffer
        while len(self.buffer) > BufferedTrace.win_size:
            # trim buffer from the left until it fits in the window
            self.buffer.popleft()
        # Create window with the buffer
        self.window_values.append((instr_id,self._buffer_to_window_value()))


    def _buffer_to_window_value(self):
        """create a window value from the buffer"""
        # the win_size is the number of sets in the cache.
        win = [0] * BufferedTrace.num_sets
        for set_idx in self.buffer:
            win[set_idx] += 1
        return win


    def create_plotable_data(self, X, Y):
        # fill potential gaps while creating the Y array.
        # The Y array ranges from 0 to 100.
        Y = [[0] * BufferedTrace.num_sets ] * len(X)
        for instr_id,val in self.window_values:
            self.Y[instr_id] = val

#-------------------------------------------
class Alias(GenericInstrument):
    """
    Definition:
        The distribution of sets usage. Y-axis is the list of all sets, and for
        each instruction that triggers a fetch, every set shows the proportion
        of fetches they have effected in the window of last BufferedTrace.win_size
        fetches.

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
    def __init__(self, instr_counter, num_sets, asso, verb=False):
        super().__init__(instr_counter, verb=verb)
        BufferedTrace.win_size = num_sets * asso
        BufferedTrace.num_sets = num_sets
        self.num_sets = num_sets

        # there is one alias trace for the whole cache, not
        # one per thread.
        self.buffer_trace = BufferedTrace()

        self.plot_name_sufix  = '_plot-04-alias'
        self.plot_title       = 'Aliasing'
        self.plot_subtitle    = 'uniform is better'
        self.plot_y_label     = 'Set Index'
        self.plot_x_label     = 'Instruction'
        self.plot_color_text  = '#B87800FF' # dark orange
        self.plot_color_boxes = '#ef9500F8' # almost opaque orange
        self.plot_color_bg    = '#FFFFFF00' # transparent
        return


    def register(self, tag, set_index):
        if not self.enabled:
            return
        if self.verb:
            print(f'ALI: fetch t:{tag}, i:{set_index}')
        self.buffer_trace.add_to_buffer(self.ic.val(), set_index)
        return


    def _log_mapping(self, x):
        # Apply logarithmic mapping to input values
        return math.log(1 + 9 * x) / math.log(10)


    def _create_plotting_data(self, kind='linear'):
        # self.buffer_trace.window_values cannot be plot right away because
        # of three reasons:
        # 1. There are most likely more time points than alias counters. We
        #    need to pad the list of counters so that it nicely matches the
        #    timeline array.
        # 2. each item is a list of num_sets counters. we need values from
        #    0 to 1 that represents the proportion of usage:
        #      - 0=perfect,
        #      - 1=all fetches in the same set.
        #    This mapping can be 'linear' or 'log' (ln)
        # 3. The matrix self.buffer_trace.window_values is a list of columns.
        #    But imshow() needs a list of rows, so we need to transpose it.

        # fill gaps to match the instructions in self.X
        transp_Y = [[0] * self.num_sets] * len(self.X)
        for instr_id,val in self.buffer_trace.window_values:
            transp_Y[instr_id] = val


        # create matrix filled with zeroes, of size transposed(transp_Y)
        self.Y = [[0] * len(transp_Y) # each row
                  for _ in range(len(transp_Y[0]))]

        # place the normalized proportions of transp_Y[x][y] in self.Y[y][x]
        for instr_idx,counters_arr in enumerate(transp_Y):
            # if there is nothing to count, keep the zeroes in Y
            all_count = sum(counters_arr)
            if all_count == 0:
                continue

            for set_idx, one_set_raw_count in enumerate(counters_arr):
                linear_ratio = one_set_raw_count / all_count
                log_ratio = self._log_mapping(linear_ratio)
                val = log_ratio if kind=='log' else linear_ratio
                self.Y[set_idx][instr_idx] = val
        transp_Y = None # hint GC
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
        axes.set_title(f'{self.plot_title}: {basename}. '
                       f'({self.plot_subtitle})', fontsize=10)

        # setup X ticks, labels, and grid
        axes.tick_params(axis='x', bottom=True, top=False, labelbottom=True,
                         rotation=90)
        x_ticks = self._create_up_to_n_ticks(self.X, base=10, n=20)
        axes.set_xticks(x_ticks)
        axes.set_xlabel(self.plot_x_label)
        axes.grid(axis='x', which='both', linestyle='-', alpha=0.1,
                  color='k', linewidth=0.5, zorder=2)

        # setup Y ticks, labels, and grid
        axes.tick_params(axis='y', which='both', left=True, right=False,
                         labelleft=True, labelright=False,
                         colors=self.plot_color_text)
        set_indices = list(range(self.num_sets))
        y_ticks = self._create_up_to_n_ticks(set_indices, base=2, n=9)
        axes.set_yticks(y_ticks)
        axes.yaxis.set_label_position('left')
        # pad y axis so it aligns with the percentages of the other plots
        if y_ticks[-1] < 100:
            pad = 10
        if y_ticks[-1] < 10:
            pad = 16
        axes.set_ylabel(self.plot_y_label, color=self.plot_color_text,
                        labelpad=pad)
        axes.grid(axis='y', which='both', linestyle='-', alpha=0.1,
                  color=self.plot_color_boxes, linewidth=0.5, zorder=2)
        return
