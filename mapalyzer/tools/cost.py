import sys
import matplotlib.pyplot as plt


from util import create_up_to_n_ticks, PlotStrings, save_fig, Dbg, Palette
from settings import Settings as st

class Cost:
    def __init__(self, shared_X=None, hue=180):
        self.X = shared_X if shared_X is not None else \
            [i for i in range(st.map.time_size)]
        self.axes = None
        self.tool_palette = Palette(hue=[hue,(hue+180)%360],
                                    lightness=st.plot.pal_lig,
                                    saturation=st.plot.pal_sat,
                                    alpha=st.plot.pal_alp)

        self.read = 0
        self.read_dist = [0] * len(self.X)
        self.write = 0
        self.write_dist = [0] * len(self.X)
        self.last_time = 0

        self.name = 'Main Memory Access'
        self.about = ('Distribution of main memory read and write operations')

        self.ps = PlotStrings(
            title  = 'Cumulative Main Mem. Access',
            xlab   = 'Time',
            ylab   = 'Mem. Access Count',
            suffix = '_plot-04-access-count',
            subtit = 'lower is better')
        return

    def add_access(self, rw):
        """Adds to read or write counter"""
        if rw == 'r':
            self.read += 1
        else:
            self.write += 1
        return

    def commit(self, time):
        # fill possible empty times with previous counts.
        last_read = self.read_dist[self.last_time]
        last_write = self.write_dist[self.last_time]
        for t in range(self.last_time+1, time):
            self.read_dist[t] = last_read
            self.write_dist[t] = last_write

        # add updated counters
        self.read_dist[time] = self.read
        self.write_dist[time] = self.write
        self.last_time = time

    def describe(self, ind=''):
        print(f'{ind}{self.name:{st.plot.ui_name_hpad}}: {self.about}')
        return

    def plot(self, bottom_tool=None):
        # create figure and tool axes
        fig,bottom_axes = plt.subplots(figsize=(st.plot.width, st.plot.height))
        self.axes = fig.add_axes(bottom_axes.get_position())

        # plot map
        if bottom_axes is not None:
            bottom_tool.plot(axes=bottom_axes)

        # set plot limits and draw read and write distributions
        padding = 0.5
        X = [self.X[0]-padding] + self.X + [self.X[-1]+padding]
        distrs = [self.read_dist, self.write_dist]
        max_Y = max(distrs[0][-1], distrs[1][-1])
        self.axes.set_xlim(X[0], X[-1])
        self.axes.set_ylim(0-(max_Y/200), max_Y+(max_Y/200))
        for i,d in enumerate(distrs):
            D = [d[0]] + d + [d[-1]]
            self.axes.fill_between(X, -1, D, step='mid', zorder=2,
                                   color=self.tool_palette[i][0],
                                   facecolor=self.tool_palette[i][1],
                                   linewidth=st.plot.linewidth)

        # finish plot setup
        self.plot_setup_Y(max_Y)
        self.plot_setup_X()
        self.plot_setup_general()

        # save image
        save_fig(fig, self.ps.title, self.ps.suffix)
        return

    def plot_setup_Y(self, max_Y):
        # spine
        #self.axes.spines['left'].set_edgecolor(self.tool_palette.fg)

        # label
        self.axes.set_ylabel(self.ps.ylab) #color=self.tool_palette.fg)

        # ticks
        self.axes.tick_params(axis='y', #colors=self.tool_palette.fg,
                              left=True, labelleft=True,
                              right=False, labelright=False,
                              width=st.plot.grid_main_width)
        y_ticks = create_up_to_n_ticks(range(max_Y+1), base=10,
                                       n=st.plot.max_ytick_count)
        self.axes.set_yticks(y_ticks)

        # grid
        self.axes.grid(axis='y', which='both', color=self.tool_palette.fg,
                       zorder=1,
                       alpha=st.plot.grid_main_alpha,
                       linewidth=st.plot.grid_main_width,
                       linestyle=st.plot.grid_main_style)
        return

    def plot_setup_X(self):
        # X axis label, ticks and grid
        self.axes.set_xlabel(self.ps.xlab)
        self.axes.tick_params(axis='x', bottom=True, top=False, labelbottom=True,
                         rotation=-90, width=st.plot.grid_other_width)
        x_ticks = create_up_to_n_ticks(self.X, base=10, n=st.plot.max_xtick_count)
        self.axes.set_xticks(x_ticks)
        # self.axes.grid(axis='x', which='both',
        #           alpha=0.1, color='k', zorder=1,
        #           linestyle=st.plot.grid_other_style,
        #           linewidth=st.plot.grid_other_width)
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
