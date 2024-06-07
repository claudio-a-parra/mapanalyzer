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
        self.tool_palette = Palette(hue=hue,
                                    lightness=st.plot.pal_lig,
                                    saturation=st.plot.pal_sat,
                                    alpha=st.plot.pal_alp)

        self.time_window = deque()
        self.time_window_size = st.cache.num_sets*st.cache.asso
        self.thr_traces = {}

        self.name = 'Miss Ratio'
        self.about = ('Thread-wise Cache Miss Ratio on the last memory '
                      'accesses.')

        self.ps = PlotStrings(
            title  = 'Miss Ratio',
            xlab   = 'Time',
            ylab   = 'Cache Miss Ratio',
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
        print(f'{ind}{self.name:{st.plot.ui_name_hpad}}: {self.about}')
        return


    def plot(self, top_tool=None):
        threads = list(self.thr_traces.keys())
        threads.sort()
        thr_num = len(threads)
        if thr_num < 1:
            raise ValueError('HitMiss registered no activity!')

        # create color palettes
        thr_pal = Palette(hue_count=thr_num,
                          lightness=st.plot.pal_lig,
                          saturation=st.plot.pal_sat,
                          alpha=st.plot.pal_alp)

        # create figure and tool axes
        fig,map_axes = plt.subplots(figsize=(st.plot.width, st.plot.height))
        axes = map_axes.twinx()
        axes.patch.set_facecolor(self.tool_palette.bg)

        # draw one plot for each thread.
        padding = 0.5
        X = [-padding] + self.X + [self.X[-1]+padding]
        for thr_idx in threads:
            thr = self.thr_traces[thr_idx]
            # Draw spacial locality across time
            miss_ratio = [thr.miss_ratio[0]] + thr.miss_ratio + [thr.miss_ratio[-1]]
            axes.fill_between(X, -1, miss_ratio, color=thr_pal[thr_idx][0],
                              facecolor=thr_pal[thr_idx][1],
                              linewidth=st.plot.linewidth, step='mid', zorder=2)

        # set plot limits
        axes.set_xlim(self.X[0]-padding, self.X[-1]+padding)
        axes.set_ylim(0-padding, 100+padding)

        # Y axis label, ticks, and grid
        axes.yaxis.set_label_position('left')
        axes.set_ylabel(self.ps.ylab, color=self.tool_palette.fg)
        percentages = list(range(100 + 1)) # from 0 to 100
        y_ticks = create_up_to_n_ticks(percentages, base=10, n=11)
        axes.tick_params(axis='y', which='both', left=True, right=False,
                         labelleft=True, labelright=False,
                         width=st.plot.grid_main_width,
                         colors=self.tool_palette.fg)
        axes.set_yticks(y_ticks)
        axes.grid(axis='y', which='both', color=self.tool_palette.fg,
                  zorder=1,
                  alpha=st.plot.grid_main_alpha,
                  linewidth=st.plot.grid_main_width,
                  linestyle=st.plot.grid_main_style)

        # plot map
        #map_axes = axes.twinx()
        top_tool.plot(axes=map_axes, xlab=True)
        #top_tool.plot_draw_Y_grid()


        # X axis ticks and grid
        axes.tick_params(axis='x', bottom=True, top=False, labelbottom=True,
                         rotation=-90, width=st.plot.grid_other_width)
        x_ticks = create_up_to_n_ticks(self.X, base=10, n=st.plot.max_xtick_count)
        axes.set_xticks(x_ticks)
        # axes.grid(axis='x', which='both',
        #           alpha=0.1, color='k', zorder=1,
        #           linestyle=st.plot.grid_other_style,
        #           linewidth=st.plot.grid_other_width)

        # setup title
        title_string = f'{self.ps.title}: {st.plot.prefix}'
        if self.ps.subtit:
            title_string += f'. ({self.ps.subtit})'
        axes.set_title(title_string, fontsize=10, pad=st.plot.img_title_vpad)

        # save image
        save_fig(fig, self.ps.title, self.ps.suffix)

        return

