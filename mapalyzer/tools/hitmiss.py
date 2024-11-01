import sys
from collections import deque
import matplotlib.pyplot as plt


from util import create_up_to_n_ticks, PlotStrings, save_fig, Dbg, Palette
from settings import Settings as st


class ThreadHitMiss:
    def __init__(self):
        self.hit_count = 0
        self.miss_count = 0
        self.time_last_increment = 0
        self.miss_ratio = [-1] * st.map.time_size
        return

    def update_counters(self, hm, current_time):
        self.hit_count += hm[0]
        self.miss_count += hm[1]
        if hm[0]+hm[1] > 0:
            self.time_last_increment = current_time

    def counters_to_ratio(self, current_time):
        # compute miss ratio with current counters and save it
        miss_ratio = 100*self.miss_count/\
            (self.hit_count+self.miss_count)
        self.miss_ratio[current_time] = miss_ratio
        return

    def __str__(self):
        hr_string = ''
        for i,r in enumerate(self.miss_ratio):
            hr_string += f'  {i:>2}: {float(r):>6.2f}\n'
        ret_str = (f'h  :{self.hit_count} '
                   f'm  :{self.miss_count}\n'
                   f'tli:{self.time_last_increment}\n'
                   f'{hr_string}')
        return ret_str

class HitMiss:
    def __init__(self, shared_X=None, hue=0):
        self.X = shared_X if shared_X is not None else \
            [i for i in range(st.map.time_size)]
        self.axes = None
        self.tool_palette = Palette(hue=hue,
                                    lightness=st.plot.pal_lig,
                                    saturation=st.plot.pal_sat,
                                    alpha=st.plot.pal_alp)

        self.time_window = deque()
        self.time_window_size = st.cache.num_sets*st.cache.asso
        self.thr_traces = {}

        self.name = 'Miss Ratio'
        self.plotcode = 'CMR'
        self.about = ('Thread-wise Cache Miss Ratio on the last memory '
                      'accesses.')

        self.ps = PlotStrings(
            title  = 'CMR',
            xlab   = 'Time [access instr.]',
            ylab   = 'Cache Miss Ratio [%]',
            suffix = '_plot-03-miss-ratio',
            subtit = 'lower is better')
        return

    def add_hm(self, access, hm):
        """hm is a tuple with the hit and miss counters diffs.
        Cache Hit : (1,0)
        Cache Miss: (0,1)"""

        # queue event to time_window, and increment the thread's counters
        self.time_window.append((access,hm))
        if access.thread not in self.thr_traces:
            self.thr_traces[access.thread] = ThreadHitMiss()
        self.thr_traces[access.thread].update_counters(hm, access.time)

        # dequeue event from time_window, and decrement the thread's counters
        while len(self.time_window) > self.time_window_size:
            old_acc,(old_h,old_m) = self.time_window.popleft()
            self.thr_traces[old_acc.thread].update_counters(
                (-old_h,-old_m), access.time)
        return

    def commit(self, time):
        for t in self.thr_traces.keys():
            thr = self.thr_traces[t]
            if thr.time_last_increment == time:
                thr.counters_to_ratio(time)

    def describe(self, ind=''):
        print(f'{ind}{self.name:{st.plot.ui_toolname_hpad}}: {self.about}')
        return

    def plot_setup_X(self):
        # Data range based on data
        X_padding = 0.5
        # add tails at start/end of X for cosmetic purposes.
        X = [self.X[0]-X_padding] + self.X + [self.X[-1]+X_padding]
        self.axes.set_xlim(X[0], X[-1])

        # Axis details: label, ticks and grid
        self.axes.set_xlabel(self.ps.xlab)
        self.axes.tick_params(axis='x',
                              top=False, bottom=True,
                              labeltop=False, labelbottom=True,
                              rotation=-90, width=st.plot.grid_other_width)
        x_ticks = create_up_to_n_ticks(self.X, base=10, n=st.plot.max_xtick_count)
        self.axes.set_xticks(x_ticks)
        # self.axes.grid(axis='x', which='both',
        #           alpha=0.1, color='k', zorder=1,
        #           linestyle=st.plot.grid_other_style,
        #           linewidth=st.plot.grid_other_width)
        return X

    def plot_setup_Y(self):
        # define Y-axis data range based on data and user input
        Y_min = 0
        Y_max = 100
        if self.plotcode in st.plot.y_ranges:
            Y_min = int(st.plot.y_ranges[self.plotcode][0])
            Y_max = int(st.plot.y_ranges[self.plotcode][1])
        Y_padding = (Y_max - Y_min)/200
        self.axes.set_ylim(Y_min-Y_padding, Y_max+Y_padding)

        # obtain list of threads
        threads = sorted(list(self.thr_traces.keys()))
        thr_count = len(threads)
        if thr_count < 1:
            raise ValueError('HitMiss registered no activity!')

        # create color palettes for threads
        thr_pallete = Palette(hue_count=thr_count,
                              lightness=st.plot.pal_lig,
                              saturation=st.plot.pal_sat,
                              alpha=st.plot.pal_alp)

        # obtain data of each thread
        Y_thr_miss_ratios = []
        for t in threads:
            thr = self.thr_traces[t]
            # add tails at start/end of Y for cosmetic purposes.
            Y_thr_miss_ratios.append(
                [thr.miss_ratio[0]] + thr.miss_ratio + [thr.miss_ratio[-1]])

        # Axis details: spine, label, ticks, and grid
        #self.axes.spines['left'].set_edgecolor(self.tool_palette.fg)
        self.axes.set_ylabel(self.ps.ylab)
        self.axes.tick_params(axis='y',
                              left=True, right=False,
                              labelleft=True, labelright=False,
                              width=st.plot.grid_main_width)
        y_ticks = create_up_to_n_ticks(range(Y_min, Y_max+1), base=10,
                                       n=st.plot.max_ytick_count)
        self.axes.set_yticks(y_ticks)
        self.axes.grid(axis='y', which='both',
                       zorder=1,
                       alpha=st.plot.grid_main_alpha,
                       linewidth=st.plot.grid_main_width,
                       linestyle=st.plot.grid_main_style)
        return (thr_pallete,Y_thr_miss_ratios)

    def draw_textbox(self):
        # insert text box with average miss ratio per thread
        threads = sorted(list(self.thr_traces.keys()))
        text = ''
        for t in threads:
            thr = self.thr_traces[t]
            tot_ops = len(thr.miss_ratio)
            avg = sum(thr.miss_ratio)/tot_ops
            text += f't{t}: {avg:.2f}% of {tot_ops:,} ops.\n'
        self.axes.text(0.98, 0.98, text, transform=self.axes.transAxes,
                       ha='right', va='top',
                       bbox=dict(facecolor=st.plot.tbox_bg , edgecolor=st.plot.tbox_border,
                                 boxstyle="square,pad=0.2"),
                       fontdict=dict(family=st.plot.tbox_font, size=st.plot.tbox_font_size),
                       zorder=1000)
        return

    def plot_setup_general(self):
        # background color
        self.axes.patch.set_facecolor(self.tool_palette.bg)
        # setup title
        title_string = f'{self.ps.title}: {st.plot.prefix}'
        if self.ps.subtit:
            title_string += f'. ({self.ps.subtit})'
        self.axes.set_title(title_string, fontsize=10, pad=st.plot.img_title_vpad)
        return

    def plot(self, bottom_tool=None):
        # only plot if requested
        if self.plotcode not in st.plot.include:
            return

        # create two set of axes: for the map (bottom) and the tool
        fig,bottom_axes = plt.subplots(figsize=(st.plot.width, st.plot.height))
        self.axes = fig.add_axes(bottom_axes.get_position())

        # plot map
        if bottom_axes is not None:
            bottom_tool.plot(axes=bottom_axes)

        # setup axes and obtain data ranges
        X = self.plot_setup_X()
        thr_pal,Y_thr_miss_ratios = self.plot_setup_Y()

        # draw miss ratio for each thread
        for t,Y_tmr in enumerate(Y_thr_miss_ratios):
            self.axes.fill_between(X, -1, Y_tmr, step='mid', zorder=2,
                                   color=thr_pal[t][0],
                                   facecolor=thr_pal[t][1],
                                   linewidth=st.plot.linewidth)

        # finish plot setup
        self.draw_textbox()
        self.plot_setup_general()

        # save image
        save_fig(fig, self.plotcode, self.ps.suffix)
        return
