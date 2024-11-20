import sys
import matplotlib.pyplot as plt


from mapanalyzer.util import create_up_to_n_ticks, PlotStrings, save_fig, Dbg, Palette
from mapanalyzer.settings import Settings as st

class CacheUsage:
    def __init__(self, shared_X=None, hue=120):
        self.tool_name = 'Cache Usage Rate'
        self.tool_about = ('Percentage of valid bytes in cache that are used before eviction.')
        self.ps = PlotStrings(
            title  = 'CUR',
            code   = 'CUR',
            xlab   = 'Time [access instr.]',
            ylab   = 'Cache Usage Rate [%]',
            suffix = '_plot-05-usage',
            subtit = 'higher is better'
        )
        self.enabled = self.ps.code in st.plot.include
        if not self.enabled:
            return

        self.X = shared_X if shared_X is not None else \
            [i for i in range(st.map.time_size)]

        self.tool_palette = Palette(hue=[hue],
                                    lightness=st.plot.pal_lig,
                                    saturation=st.plot.pal_sat,
                                    alpha=st.plot.pal_alp)

        self.accessed_bytes = 0
        self.valid_bytes = 0
        self.usage_ratio = [-1] * len(self.X)
        return

    def update(self, delta_access=0, delta_valid=0):
        if not self.enabled:
            return
        """Update counters by deltas"""
        self.accessed_bytes += delta_access
        self.valid_bytes += delta_valid
        return

    def commit(self, time):
        if not self.enabled:
            return
        self.usage_ratio[time] = 100 * self.accessed_bytes / self.valid_bytes

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
        #           alpha=0.1, color='k', zorder=1,
        #           linestyle=st.plot.grid_other_style,
        #           linewidth=st.plot.grid_other_width)
        return X

    def plot_setup_Y(self):
        # define Y-axis data range based on data and user input
        Y_min = 0
        Y_max = 100
        if self.ps.code in st.plot.y_ranges:
            Y_min = int(st.plot.y_ranges[self.ps.code][0])
            Y_max = int(st.plot.y_ranges[self.ps.code][1])
        Y_padding = (Y_max - Y_min)/200
        self.axes.set_ylim(Y_min-Y_padding, Y_max+Y_padding)
        # add tails at start/end of Y for cosmetic purposes.
        Y_usage = [self.usage_ratio[0]] + self.usage_ratio + [self.usage_ratio[-1]]

        # Axis details: label, ticks, and grid
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
        return Y_usage

    def draw_textbox(self):
        # insert text box with average usage
        avg = sum(self.usage_ratio)/len(self.usage_ratio)
        text = f'Avg: {avg:.2f}%'
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
        if not self.enabled:
            return

        # create two set of axes: for the map (bottom) and the tool
        fig,bottom_axes = plt.subplots(figsize=(st.plot.width, st.plot.height))
        self.axes = fig.add_axes(bottom_axes.get_position())

        # plot map
        if bottom_axes is not None:
            bottom_tool.plot(axes=bottom_axes)

        # setup axes and obtain data ranges
        X = self.plot_setup_X()
        Y_usage = self.plot_setup_Y()

        # plot the usage rate
        self.axes.fill_between(X, -1, Y_usage, step='mid', zorder=2,
                               color=self.tool_palette[0][0],
                               facecolor=self.tool_palette[0][1],
                               linewidth=st.plot.linewidth)
        # finish plot setup
        self.draw_textbox()
        self.plot_setup_general()

        # save image
        save_fig(fig, self.ps.code, self.ps.suffix)
        return
