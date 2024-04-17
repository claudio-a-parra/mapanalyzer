#!/usr/bin/env python3
import sys
from collections import deque
from .generic import GenericInstrument

class BufferedTrace:
    win_size = 64*64*512
    def __init__(self):
        # buffer with incoming elements
        self.buffer = deque()
        # value that represents the logical size of the buffer
        self.buffer_lsize = 0
        # resulting values obtained from each window extracted from the buffer
        self.window_values = []
        # data ready to plot
        self.Y = []

    def add_to_buffer(self, instr_id, miss, hit):
        """Add an element to the buffer. If its logical size is big enough,
        create a window, compute its value, and append it to the window_values
        list."""
        # if this is the continuation of an already existing instruction, then
        # update its value rather than adding a copy.
        continuation = False
        if len(self.buffer) > 0 and self.buffer[-1][0] == instr_id:
            continuation = True
            m,h = self.buffer[-1][1]
            self.buffer[-1] = (instr_id, (miss+m, hit+h))
        else:
            self.buffer.append((instr_id, (miss,hit)))

        self.buffer_lsize += miss+hit
        # While there are enough elements in the buffer
        while self.buffer_lsize > BufferedTrace.win_size:
            # trim buffer from the left until it fits in the window
            _,oldest_miss_hit = self.buffer.popleft()
            self.buffer_lsize -= oldest_miss_hit[0]+oldest_miss_hit[1]
        w_val = (instr_id, self._buffer_to_window_value())

        if continuation:
            self.window_values[-1] = w_val
        else:
            self.window_values.append(w_val)


    def _buffer_to_window_value(self):
        # create a window from the buffer
        win = []
        misses,hits = 0,0
        for _,mh in self.buffer:
            misses += mh[0]
            hits += mh[1]
        return (hits)/(misses+hits)


    def create_plotable_data(self, X):
        # fill potential gaps while creating the Y array.
        # The Y array ranges from 0 to 100.
        self.Y = [0] * len(X)
        for instr_id,val in self.window_values:
            self.Y[instr_id] = 100 * val


#-------------------------------------------
class Hit(GenericInstrument):
    """
    Definition:
        The proportion of cache hits with respect to all cache requests in
        the last window of BufferedTrace.win_size accessed bytes.

    Captured Events:
        Every time there is a hit or a miss (this is, any cache access) a
        tuple with them (miss, hit) is appended to a buffer of up to
        BufferedTrace.win_size elements. After every appendage, compute the
        proportion on the buffer. If the buffer becomes greater than the
        window size, then trim it from the oldest side (FIFO).

    Plot interpretation:
        The plot is a line that ranges from 0% to 100% showing the proportion
        of cache hits in the last win_size memory accesses.
    """
    def __init__(self, instr_counter, cache_size, verb=False):
        super().__init__(instr_counter, verb=verb)
        BufferedTrace.win_size = cache_size

        # each thread has its own hit trace.
        self.buffer_traces = {}

        self.plot_name_sufix = '_plot-02-hit'
        self.plot_title      = 'Hit Ratio'
        self.plot_subtitle   = 'higher is better'
        self.plot_y_label    = 'Cache Hits [%]'
        self.plot_x_label    = 'Instruction'
        self.plot_color_text = '#18419AFF' # darker blue
        self.plot_color_line = '#18419A88' # blue almost opaque
        self.plot_color_fill = '#18419A11' # blue semi-transparent
        return

    def register(self, thread, delta_miss=0, delta_hit=0):
        """Register cache misses or hits on a given thread for a given
        instruction"""
        if not self.enabled:
            return
        if thread not in self.buffer_traces:
            self.buffer_traces[thread] = BufferedTrace()
        self.buffer_traces[thread].add_to_buffer(self.ic.val(), delta_miss, delta_hit)


    def get_extent(self):
        # fine tune margins to place each quadrilateral of the imshow()
        # right on the tick. So adding a 0.5 margin at each side.
        left_edge = self.X[0] - 0.5
        right_edge = self.X[-1] + 0.5
        bottom_edge = 0 - 0.5
        top_edge = 100 + 0.5 # 100% + a little margin
        extent = (left_edge, right_edge, bottom_edge, top_edge)
        return extent


    def plot(self, axes, basename='hit', extent=None):
        for thread in self.buffer_traces:
            self.buffer_traces[thread].create_plotable_data(self.X)

        # set plot limits
        extent = extent if extent != None else self.get_extent()
        axes.set_xlim(extent[0], extent[1])
        axes.set_ylim(extent[2], extent[3])

        # draw the curve and area below it for each thread
        for thread in self.buffer_traces:
            Y = self.buffer_traces[thread].Y
            axes.step(self.X, Y, color=self.plot_color_line,
                      linewidth=1.2, where='mid', zorder=2)
            axes.fill_between(self.X, -1, Y, color='none',
                              facecolor=self.plot_color_fill,
                              linewidth=1.2, step='mid', zorder=1)

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

        # setup Y ticks, labels and grid
        axes.tick_params(axis='y', which='both', left=True, right=False,
                         labelleft=True, labelright=False,
                         colors=self.plot_color_text)
        percentages = list(range(100 + 1)) # from 0 to 100
        y_ticks = self._create_up_to_n_ticks(percentages, base=10, n=11)
        axes.set_yticks(y_ticks)
        axes.yaxis.set_label_position('left')
        axes.set_ylabel(self.plot_y_label, color=self.plot_color_text,
                        labelpad=3.5)
        axes.grid(axis='y', which='both', linestyle='-', alpha=0.1,
                  color=self.plot_color_line, linewidth=0.5, zorder=3)

        return
