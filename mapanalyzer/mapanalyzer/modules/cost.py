import sys
import matplotlib.pyplot as plt


from mapanalyzer.util import create_up_to_n_ticks, PlotStrings, save_fig, Palette
from mapanalyzer.settings import Settings as st

class Cost:
    def __init__(self, shared_X=None, hue=180):
        self.tool_name = 'Main Mem. Access'
        self.tool_about = ('Distribution of main memory read and write operations.')
        self.ps = PlotStrings(
            title  = 'CMMA',
            code   = 'CMMA',
            xlab   = 'Time [access instr.]',
            ylab   = 'Cumulative Main Memory Access [count]',
            suffix = '_plot-04-access-count',
            subtit = 'lower is better'
        )
        self.enabled = self.ps.code in st.plot.include
        if not self.enabled:
            return

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

        return

    def add_access(self, rw):
        if not self.enabled:
            return
        """Adds to read or write counter"""
        if rw == 'r':
            self.read += 1
        else:
            self.write += 1
        return

    def commit(self, time):
        if not self.enabled:
            return
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
        if not self.enabled:
            return
        print(f'{ind}{self.tool_name:{st.plot.ui_toolname_hpad}}: {self.tool_about}')
        return

    def plot_setup_X(self):
        # Data range based on data
        X_padding = 0.5
        # add tails at start/end of X for cosmetic purposes.
        X = [self.X[0]-X_padding] + self.X + [self.X[-1]+X_padding]
        self.axes.set_xlim(X[0], X[-1])

        # Axis details: label, ticks and grid
        self.axes.set_xlabel(self.ps.xlab)
        rot = -90 if st.plot.x_orient == 'v' else 0
        self.axes.tick_params(axis='x',
                              top=False, bottom=True,
                              labeltop=False, labelbottom=True,
                              rotation=rot, width=st.plot.grid_other_width)
        x_ticks = create_up_to_n_ticks(self.X, base=10, n=st.plot.max_xtick_count)
        self.axes.set_xticks(x_ticks)
        # self.axes.grid(axis='x', which='both',
        #           zorder=1,
        #           alpha=st.plot.grid_main_alpha,
        #           linestyle=st.plot.grid_other_style,
        #           linewidth=st.plot.grid_other_width)
        return X

    def plot_setup_Y(self):
        # Data range based on data and user input
        Y_min = min(self.read_dist[0], self.write_dist[0])
        Y_max = self.read_dist[-1] + self.write_dist[-1]
        if self.ps.code in st.plot.y_ranges:
            Y_min = int(st.plot.y_ranges[self.ps.code][0])
            Y_max = int(st.plot.y_ranges[self.ps.code][1])
        Y_padding = (Y_max - Y_min)/200
        self.axes.set_ylim(Y_min-Y_padding, Y_max+Y_padding)
        # add tails at start/end of Y for cosmetic purposes.
        # Y_rwd starts at write height, that's why we add read+write.
        Y_rwd = [self.read_dist[0]+self.write_dist[0]] \
            + [self.read_dist[i] + self.write_dist[i] for i in range(len(self.read_dist))] \
            + [self.read_dist[-1]+self.write_dist[-1]]
        Y_wd = [self.write_dist[0]] + self.write_dist + [self.write_dist[-1]]

        # Axis details: spine, label, ticks, and grid
        #self.axes.spines['left'].set_edgecolor(self.tool_palette.fg)
        self.axes.set_ylabel(self.ps.ylab)
        self.axes.tick_params(axis='y',
                              left=True, labelleft=True,
                              right=False, labelright=False,
                              width=st.plot.grid_main_width)
        y_ticks = create_up_to_n_ticks(range(Y_min, Y_max+1), base=10,
                                       n=st.plot.max_ytick_count)
        self.axes.set_yticks(y_ticks)
        self.axes.grid(axis='y', which='both', #color=self.tool_palette.fg,
                       zorder=1,
                       alpha=st.plot.grid_main_alpha,
                       linewidth=st.plot.grid_main_width,
                       linestyle=st.plot.grid_main_style)
        return (Y_rwd,Y_wd)

    def draw_textbox(self):
        # insert text box with total number of accesses
        tot_read = self.read_dist[-1]
        tot_write = self.write_dist[-1]
        text = \
            f'mm.R: {tot_read:,}\n'+\
            f'mm.W: {tot_write:,}'
        self.axes.text(0.98, 0.02, text, transform=self.axes.transAxes,
                       ha='right', va='bottom',
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
        if not self.enabled:
            return

        # create two set of axes: for the map (bottom) and the tool
        fig,bottom_axes = plt.subplots(figsize=(st.plot.width, st.plot.height))
        self.axes = fig.add_axes(bottom_axes.get_position())

        # plot map
        if bottom_tool is not None:
            bottom_tool.plot(axes=bottom_axes)

        # Setup axes and obtain data ranges
        X = self.plot_setup_X()
        Y_rwd,Y_wd = self.plot_setup_Y()

        i = 0 # plot read plot (above write plot)
        self.axes.fill_between(X, Y_wd, Y_rwd, step='mid', zorder=2,
                               color=self.tool_palette[i][0],
                               facecolor=self.tool_palette[i][1],
                               linewidth=st.plot.linewidth)

        i = 1 # plot write plot (below read plot)
        self.axes.fill_between(X, -1, Y_wd, step='mid', zorder=2,
                               color=self.tool_palette[i][0],
                               facecolor=self.tool_palette[i][1],
                               linewidth=st.plot.linewidth)

        # finish plot setup
        self.draw_textbox()
        self.plot_setup_general()

        # save image
        save_fig(fig, self.ps.code, self.ps.suffix)
        return
