import sys
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors # to create shades of colors from list
from collections import deque

from util import create_up_to_n_ticks, PlotStrings, save_fig, Dbg, Palette
from settings import Settings as st

class Aliasing:
    def __init__(self, shared_X=None, hue=220):
        self.i = 0
        self.X = shared_X if shared_X is not None else \
            [i for i in range(st.map.time_size)]
        self.tool_palette = Palette(hue=[hue],
                                    lightness=st.plot.pal_lig,
                                    saturation=st.plot.pal_sat,
                                    alpha=st.plot.pal_alp)

        self.time_window = deque()
        self.time_window_max_size = st.cache.asso * st.cache.num_sets
        self.set_counters = [0] * st.cache.num_sets
        self.aliasing = [[0] * len(self.X) for _ in range(st.cache.num_sets)]

        self.name = 'Cache Aliasing'
        self.about = ('Proportion in which each set fetches blocks during execution')

        self.ps = PlotStrings(
            title  = 'Cache Aliasing',
            xlab   = 'Time',
            ylab   = 'Cache Sets',
            suffix = '_plot-06-aliasing',
            subtit = 'transparent is better')
        return

    def fetch(self, set_index, access_time):
        """Update the Set counters"""
        # append access to queue
        self.time_window.append((set_index,access_time))
        self.set_counters[set_index] += 1

        # trim queue to fit max_size
        while len(self.time_window) > self.time_window_max_size:
            old_set_idx,old_time = self.time_window.popleft()
            self.set_counters[old_set_idx] -= 1
        return

    def commit(self, time):
        curr_time = self.time_window[-1][1]
        tot_fetch = sum(self.set_counters)
        for i in range(st.cache.num_sets):
            self.aliasing[i][curr_time] = self.set_counters[i] / tot_fetch
        return

    def describe(self, ind=''):
        print(f'{ind}{self.name:{st.plot.ui_name_hpad}}: {self.about}')
        return


    def plot(self, bottom_tool=None):
        # create figure and tool axes
        fig,bottom_axes = plt.subplots(figsize=(st.plot.width, st.plot.height))
        bottom_axes.set_xticks([])
        bottom_axes.set_yticks([])
        self.axes = fig.add_axes(bottom_axes.get_position())

        # plot map
        # if bottom_tool is not None:
        #     bottom_tool.plot(axes=bottom_axes)

        # create color shade from transparent (0) to solid (1)
        colors = ['#FFFFFF00', self.tool_palette[0][0]]
        shade_cmap = mcolors.LinearSegmentedColormap.from_list(
            'transparency_cmap', colors)

        # set image extent and draw aliasing
        padding = 0.5
        ext = (self.X[0]-padding, self.X[-1]+padding,
               0-padding, st.cache.num_sets-padding)
        self.axes.set_xlim(ext[0], ext[1])
        self.axes.set_ylim(ext[2], ext[3])
        self.axes.imshow(self.aliasing, cmap=shade_cmap, origin='lower',
                         interpolation=None, aspect='auto', extent=ext,
                         zorder=1, vmin=0, vmax=1)

        # finish plot setup
        self.plot_setup_general()
        self.plot_setup_X()
        self.plot_setup_Y()

        # save image
        save_fig(fig, self.ps.title, self.ps.suffix)
        return

    def plot_setup_Y(self):
        # spine
        #self.axes.spines['left'].set_edgecolor(self.tool_palette.fg)

        # label
        self.axes.set_ylabel(self.ps.ylab) #color=self.tool_palette.fg)

        # ticks
        self.axes.tick_params(axis='y', #colors=self.tool_palette.fg,
                              left=True, labelleft=True,
                              right=False, labelright=False,
                              width=st.plot.grid_main_width)
        y_ticks = create_up_to_n_ticks(range(st.cache.num_sets), base=10,
                                       n=st.plot.max_ytick_count)
        self.axes.set_yticks(y_ticks)

        # direction
        self.axes.invert_yaxis()

        # grid
        self.plot_draw_Y_grid()
        return

    def plot_setup_X(self):
        # X axis label, ticks and grid
        self.axes.set_xlabel(self.ps.xlab)
        self.axes.tick_params(axis='x',
                              bottom=True, labelbottom=True,
                              top=False, labeltop=False,
                              rotation=-90, width=st.plot.grid_other_width)
        x_ticks = create_up_to_n_ticks(self.X, base=10,
                                       n=st.plot.max_xtick_count)
        self.axes.set_xticks(x_ticks)
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

    def plot_draw_Y_grid(self, color='#40BF40'):
        xmin,xmax = 0-0.5,st.map.time_size-0.5
        max_sets = 64 #st.plot.grid_max_blocks
        block_lw = 2*(1 - ((st.cache.num_sets-1) / max_sets))
        block_sep_lines = [i-0.5 for i in range(st.cache.num_sets)]
        self.axes.hlines(y=block_sep_lines, xmin=xmin, xmax=xmax,
                         color=color,
                         linewidth=block_lw, alpha=0.4, zorder=2)
        return
