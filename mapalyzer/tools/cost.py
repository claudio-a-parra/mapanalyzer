import sys
import matplotlib.pyplot as plt


from util import create_up_to_n_ticks, PlotStrings, save_fig, Dbg, Palette
from settings import Settings as st

class Cost:
    def __init__(self, shared_X=None, hue=180):
        self.X = shared_X if shared_X is not None else \
            [i for i in range(st.map.time_size)]
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
            ylab   = 'Access Count',
            suffix = '_plot-04-access-count',
            subtit = 'flatter is better')
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


    def plot(self, top_tool=None):
        # create figure and tool axes
        fig,map_axes = plt.subplots(figsize=(st.plot.width, st.plot.height))
        axes = map_axes.twinx()
        axes.patch.set_facecolor(self.tool_palette.bg)

        # common plot elements
        padding = 0.5
        X = [-padding] + self.X + [self.X[-1]+padding]

        # draw READ distribution
        distrs = [self.read_dist, self.write_dist]
        for i,d in enumerate(distrs):
            D = [d[0]] + d + [d[-1]]
            axes.fill_between(X, -1, D, step='mid', zorder=2,
                          color=self.tool_palette[i][0],
                          facecolor=self.tool_palette[i][1],
                          linewidth=st.plot.linewidth)


        # Y axis label, ticks, and grid
        axes.yaxis.set_label_position('left')
        axes.set_ylabel(self.ps.ylab, color=self.tool_palette.fg)
        max_Y = max(distrs[0][-1], distrs[1][-1])
        full_y_ticks = list(range(max_Y + 1)) # from 0 to 100
        y_ticks = create_up_to_n_ticks(full_y_ticks, base=10, n=11)
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
        top_tool.plot(axes=map_axes, xlab=True)
        #top_tool.plot_draw_Y_grid()


        # X axis label, ticks and grid
        axes.set_xlabel(self.ps.xlab)
        axes.tick_params(axis='x', bottom=True, top=False, labelbottom=True,
                         rotation=-90, width=st.plot.grid_other_width)
        x_ticks = create_up_to_n_ticks(self.X, base=10, n=st.plot.max_xtick_count)
        axes.set_xticks(x_ticks)
        # axes.grid(axis='x', which='both',
        #           alpha=0.1, color='k', zorder=1,
        #           linestyle=st.plot.grid_other_style,
        #           linewidth=st.plot.grid_other_width)

        # set plot limits
        axes.set_xlim(self.X[0]-padding, self.X[-1]+padding)
        axes.set_ylim(0-(max_Y/200), max_Y+(max_Y/200))

        # setup title
        title_string = f'{self.ps.title}: {st.plot.prefix}'
        if self.ps.subtit:
            title_string += f'. ({self.ps.subtit})'
        axes.set_title(title_string, fontsize=10, pad=st.plot.img_title_vpad)

        # save image
        save_fig(fig, self.ps.title, self.ps.suffix)

        return
