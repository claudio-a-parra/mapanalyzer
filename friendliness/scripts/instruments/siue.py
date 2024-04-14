#!/usr/bin/env python3
import sys
from collections import deque

from .generic import GenericInstrument

class BufferedTrace:
    win_size = 64*8 # number of sets
    def __init__(self):
        # buffer with incoming elements
        self.buffer = deque()
        # value that represents the logical size of the buffer
        self.buffer_lsize = 0
        # resulting values obtained from each window extracted from the buffer
        self.window_values = []


    def add_to_buffer(self, instr_id, set_index):
        """Add an element to the buffer. If its logical size is big enough,
        create a window, compute its value, and append it to the window_values
        list."""
        self.buffer.append(set_index)
        self.buffer_lsize += 1
        # While there are enough elements in the buffer
        while self.buffer_lsize > BufferedTrace.win_size:
            # trim buffer from the left until it fits in the window
            self.buffer.popleft()
            self.buffer_lsize -= 1
        # Create window with the buffer
        self.window_values.append((instr_id,self._buffer_to_window_value()))

    def search_buffer(self, key):
        mode = 'fetch'
        return mode

    def _buffer_to_window_value(self):
        """create a window value from the buffer"""
        # the win_size is the number of sets in the cache.
        win = [0] * BufferedTrace.win_size
        for set_idx in self.buffer:
            win[set_idx] += 1
        return win


    def create_plotable_data(self, X, Y):
        # fill potential gaps while creating the Y array.
        # The Y array ranges from 0 to 100.
        Y = [[0] * BufferedTrace.win_size ] * len(X)
        for instr_id,val in self.window_values:
            self.Y[instr_id] = val


#-------------------------------------------
class SIUEvict(GenericInstrument):
    """
    Definition:
        The proportion of SIU evictions with respect to the total number of
        evictions. A SIU (still-in-use) eviction is the eviction of a cache
        block that later will be fetched to the cache again.

    Fetch and Evict Counters:
        This instrument works in two passes. In the first pass a dictionary
        of (tag,index) -> (counter) is populated, so that every time a cache
        block is fetched, the counter increments.
        On the second pass, and using the already populated dictionary, every
        block eviction triggers a decrement in its corresponding counter.
        If after the decrement, the counter is still greater than 0, this means
        the block is later brought back to cache again. It is, then, said that
        the current is an eviction of a "still-in-use" block.

    Captured Events:
        Each event is a tuple of two counters: (siu_evicts, tot_evicts). Note
        that tot_evicts includes all siu_evicts. These counters are cumulative.

    Plot interpretation:
        The plot is a line that ranges from 0% to 100% showing the proportion
        of evictions that are SIU.
    """

    def __init__(self, instr_counter, num_sets, verb=False):
        super().__init__(instr_counter, verb=verb)

        # last block operations (tag,index) -> queue<(instr_id,operation)>()
        self.blocks_ops = {}
        # queue of last block operations to preserve in/out order
        # of the dictionary above.
        self.buffer = deque()

        self.buffer_max_size = num_sets
        self.num_sets = num_sets
        self.sparse_Y = []


        # BEGIN_OLD
        self.fetch_counters = {}
        self.mode = 'fetch' # ['fetch', 'evict']
        self.siu_evict_count = 0
        self.tot_evict_count = 0
        self.zero_counter = (0,0)
        # END_OLD

        self.plot_name_sufix = '_plot-05-siu'
        self.plot_title      = 'Still-in-Use Block Evictions'
        self.plot_subtitle   = 'less points is better'
        self.plot_y_label    = 'SIU Eviction ratio [%]'
        self.plot_color_text = '#6122AA'   # dark magenta
        self.plot_color_dots = '#7A2AD5AA' # magenta almost opaque
        #self.plot_color_fill = '#7A2AD522' # magenta semi-transparent


    def register(self, op, tag, index):
        if not self.enabled:
            return

        block = (tag,index)

        if block in self.blocks_ops:
            if op == 'fetch':
                last_instr_id,last_op = self.blocks_ops[block][-1]
                if last_op == 'evict':
                    self.Y.append((last_instr_id,index))
        else:
            self.blocks_ops[block] = deque()
        self.blocks_ops[block].append((self.ic.val(),op))

        self.buffer.append(block)
        if len(self.buffer) > self.buffer_max_size:
            old_block = self.buffer.popleft()
            self.blocks_ops[old_block].popleft()
            if len(self.blocks_ops[old_block]) == 0:
                del self.blocks_ops[old_block]
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


    def plot(self, axes, basename='siue', extent=None):
        # draw the image and invert Y axis (so lower value is on top)
        X = [coor[0] for coor in self.Y]
        Y = [coor[1] for coor in self.Y]
        axes.scatter(X, Y, marker='s', s=8,
                     color=self.plot_color_dots, edgecolor='none',
                     zorder=1)
        # set plot limits
        le,re,be,te = extent if extent != None else self.get_extent()
        axes.set_xlim(le, re)
        axes.set_ylim(be, te)
        axes.invert_yaxis()

        # setup title
        axes.set_title(f'{self.plot_title}: {basename}\n'
                       f'({self.plot_subtitle})')

        # setup Y ticks
        axes.tick_params(axis='y', which='both', left=True, right=False,
                         labelleft=True, labelright=False,
                         colors=self.plot_color_text)
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
        axes.grid(axis='y', which='both', linestyle='-', alpha=0.1,
                  color=self.plot_color_dots, linewidth=0.5, zorder=2)
        return
