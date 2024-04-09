import sys
from collections import deque
from .generic import GenericInstrument

class AccessTrace:
    cache_size = 64*64*512
    block_size = 64
    def __init__(self):
        # buffer with incoming accesses, and total bytes in it
        self.buffer = deque()
        self.buffer_bytes = 0
        # sliding windows with accessed addresses sorted
        #self.access_windows = []
        # distances between neighboring addresses from windows
        #self.access_distances = []
        # locality of each window.
        self.locality = []


    def add_access(self, access):
        """Add a memory access to this thread's trace and create
        a new window if there is enough accesses in the buffer."""
        # append access to buffer
        self.buffer.append(access)
        self.buffer_bytes += access.size
        # While there are enough bytes accessed in the buffer, create a window
        while self.buffer_bytes >= AccessTrace.cache_size:
            # trim buffer from the left until it fits in the cache
            oldest_access = self.buffer.popleft()
            self.buffer_bytes -= oldest_access.size
            self.locality.append(self._win_dist_loc())
            #self.access_windows.append(self._new_window())

    def _win_dist_loc(self):
        """Compute the locality value for a window of memory accesses.
        Bind the value to the last instruction of the window."""
        # create window of accesses from the access buffer.
        win_acc = []
        win_instr = self.buffer[-1].time
        for acc in self.buffer:
            for off in range(acc.size):
                win_acc.append(acc.addr+off)
        win_acc = sorted(win_acc)
        # compute neighbors distances within this window.
        win_dis = [b-a for a,b in zip(win_acc[:-1],win_acc[1:])]
        # compute locality based on neighbor distances.
        loc_val = sum(max(0,
                          (AccessTrace.block_size - d) /
                          (AccessTrace.block_size * len(win_dis))
                          )
                      for d in win_dis
                      )
        # return tuple of instruction at the end of the window and locality
        # value of this window.
        return (win_instr, loc_val)


    def create_plotable_data(self, X):
        # fill potential gaps while creating the Y array.
        # The Y array ranges from 0 to 100.
        self.Y = [0] * len(X)
        for i,val in self.locality:
            self.Y[i] = 100 * val

class Locality(GenericInstrument):
    def __init__(self, instr_counter, cache_size, block_size, verb=False):
        super().__init__(instr_counter, verb=False)
        self.cache_size = cache_size
        AccessTrace.cache_size = cache_size
        self.block_size = block_size
        AccessTrace.block_size = block_size

        # each thread has its own access trace.
        self.threads_trace = {}

        self.plot_name_sufix  = '_plot-01-locality'
        self.plot_title       = 'Locality'
        self.plot_subtitle    = 'Higher is better'
        self.plot_y_label     = 'Degree of locality [%]'
        self.plot_color_text  = '#606060FF' # dark gray
        self.plot_color_line  = '#A0A0A0FF' # gray
        self.plot_color_fill  = '#A0A0A044' # gray semi-transparent
        self.plot_color_bg    = '#FFFFFF00' # transparent


    def register_access(self, access):
        if not self.enabled:
            return
        if access.thread not in self.threads_trace:
            self.threads_trace[access.thread] = AccessTrace()
        self.threads_trace[access.thread].add_access(access)


    def get_extent(self):
        # fine tune margins to place each quadrilateral of the imshow()
        # right on the tick. So adding a 0.5 margin at each side.
        left_edge = self.X[0] - 0.5
        right_edge = self.X[-1] + 0.5
        bottom_edge = 0 - 0.5
        top_edge = 100 + 0.5 # 100% + a little margin
        extent = (left_edge, right_edge, bottom_edge, top_edge)
        return extent

    def plot(self, axes, basename='locality', extent=None):
        # create last window with whatever remaining accesses in the buffer
        for thr in self.threads_trace:
            tt=self.threads_trace[thr]
            # Compute locality for the remaining instructions in the buffer:
            # 1.  if the buffer has accesses but the locality list is empty,
            #     OR
            # 2.  if the last instruction in the buffer is different from the
            #     last instruction in the locality list.
            if (len(tt.buffer) > 0 and len(tt.locality) == 0) or \
               tt.buffer[-1].time != tt.locality[-1][0]:
                tt.locality.append(tt._win_dist_loc())
            # convert lists of localities into plot-able data
            tt.create_plotable_data(self.X)

        # set plot limits
        extent = extent if extent != None else self.get_extent()
        axes.set_xlim(extent[0], extent[1])
        axes.set_ylim(extent[2], extent[3])

        # draw the curve and area below it for each thread
        for thr in self.threads_trace:
            Y = self.threads_trace[thr].Y
            axes.step(self.X, Y, color=self.plot_color_line,
                      linewidth=1.2, where='mid', zorder=2)
            axes.fill_between(self.X, -1, Y, color='none',
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
