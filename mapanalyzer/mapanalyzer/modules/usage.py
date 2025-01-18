import matplotlib.pyplot as plt


from mapanalyzer.util import create_up_to_n_ticks, MetricStrings, Palette, \
    save_fig, save_json
from mapanalyzer.settings import Settings as st

class CacheUsage:
    def __init__(self, shared_X=None, hue=120):
        # Module info
        self.name = 'Cache Usage Rate'
        self.about = ('Percentage of valid bytes in cache that are used '
                           'before eviction.')
        # Metric(s) info
        self.ps = MetricStrings(
            title  = 'CUR',
            subtit = 'higher is better',
            code   = 'CUR',
            xlab   = 'Time [access instr.]',
            ylab   = 'Cache Usage Rate [%]'
        )

        self.enabled = self.ps.code in st.Plot.include
        if not self.enabled:
            return

        if shared_X is not None:
            self.X = shared_X
        else:
            self.X = [i for i in range(st.Map.time_size)]

        self.hue = hue
        self.palette = Palette(
            hue=[hue],
            lightness=st.Plot.pal_lig,
            saturation=st.Plot.pal_sat,
            alpha=st.Plot.pal_alp)

        self.accessed_bytes = 0
        self.valid_bytes = 0
        self.usage_ratio = [-1] * len(self.X)
        return

    def update(self, delta_access=0, delta_valid=0):
        """Update counters by deltas"""
        if not self.enabled:
            return
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
        nc = f'{self.name} ({self.ps.code})'
        print(f'{ind}{nc:{st.UI.module_name_hpad}}: '
              f'{self.about}')
        return

    def finalize(self):
        # no post-simulation computation to be done
        return

    def export_metrics(self, bg_module):
        self_dict = self.__to_dict()
        self_dict['mapplot'] = bg_module.to_dict()['metric']
        save_json(self_dict, self.ps)
        return

    def export_plots(self, bg_module=None):
        if not self.enabled:
            return
        # If there is a background plot module, create two sets of axes
        if bg_module is not None:
            # create two set of axes: bg: MAP. fg: this module's metrics
            fig,bg_axes = plt.subplots(figsize=(st.Plot.width, st.Plot.height))
            fg_axes = fig.add_axes(bg_axes.get_position())
            bg_module.bg_plot(axes=bg_axes)
        else:
            fig,fg_axes = plt.subplots(figsize=(st.Plot.width, st.Plot.height))

        # setup X and Y axes and add tails to the X and Y arrays
        # for cosmetic purposes (because of the step function)
        X_padding = self.__setup_X_axis(fg_axes)
        Y_padding = self.__setup_Y_axis(fg_axes)
        X = [self.X[0]-X_padding] + self.X + [self.X[-1]+X_padding]
        Y = [self.usage_ratio[0]] + self.usage_ratio + [self.usage_ratio[-1]]

        # plot the usage rate
        fg_axes.fill_between(
            X, -1, Y, step='mid', zorder=2,
            color=self.palette[0][0],
            facecolor=self.palette[0][1],
            linewidth=st.Plot.linewidth
        )

        # finish plot setup
        self.__setup_general(fg_axes)
        self.__draw_textbox(fg_axes)

        # save figure
        save_fig(fig, self.ps)
        return

    def __setup_X_axis(self, axes):
        # define X-axis data range based on data and user input
        X_min = self.X[0]
        X_max = self.X[-1]
        if self.ps.code in st.Plot.x_ranges:
            X_min = int(st.Plot.x_ranges[self.ps.code][0])
            X_max = int(st.Plot.x_ranges[self.ps.code][1])
        X_padding = 0.5
        axes.set_xlim(X_min-X_padding, X_max+X_padding)

        # Axis details: label, ticks and grid
        axes.set_xlabel(self.ps.xlab)
        rot = -90 if st.Plot.x_orient == 'v' else 0
        axes.tick_params(
            axis='x', rotation=rot, width=st.Plot.grid_other_width,
            top=False, labeltop=False, bottom=True, labelbottom=True
        )
        axes.set_xticks(
            create_up_to_n_ticks(self.X, base=10, n=st.Plot.max_xtick_count)
        )
        axes.grid(
            axis='x', which='both',
            zorder=1,
            alpha=st.Plot.grid_other_alpha,
            linewidth=st.Plot.grid_other_width,
            linestyle=st.Plot.grid_other_style
        )
        return X_padding

    def __setup_Y_axis(self, axes):
        # define Y-axis data range based on data and user input
        Y_min = 0
        Y_max = 100
        if self.ps.code in st.Plot.y_ranges:
            Y_min = int(st.Plot.y_ranges[self.ps.code][0])
            Y_max = int(st.Plot.y_ranges[self.ps.code][1])
        Y_padding = (Y_max - Y_min) / 200
        axes.set_ylim(Y_min-Y_padding, Y_max+Y_padding)

        # Axis details: label, ticks, and grid
        axes.set_ylabel(self.ps.ylab)
        axes.tick_params(
            axis='y', width=st.Plot.grid_main_width,
            left=True, labelleft=True, right=False, labelright=False
        )
        axes.set_yticks(
            create_up_to_n_ticks(range(Y_min, Y_max+1), base=10,
                                 n=st.Plot.max_ytick_count)
        )
        axes.grid(
            axis='y', which='both',
            zorder=1,
            alpha=st.Plot.grid_main_alpha,
            linewidth=st.Plot.grid_main_width,
            linestyle=st.Plot.grid_main_style
        )
        return Y_padding

    def __draw_textbox(self, axes):
        # insert text box with average usage
        avg = sum(self.usage_ratio)/len(self.usage_ratio)
        text = f'Avg: {avg:.2f}%'
        axes.text(
            0.98, 0.98, text, transform=axes.transAxes,
            ha='right', va='top',
            bbox=dict(facecolor=st.Plot.tbox_bg,
                      edgecolor=st.Plot.tbox_border,
                      boxstyle="square,pad=0.2"),
            fontdict=dict(family=st.Plot.tbox_font,
                          size=st.Plot.tbox_font_size),
            zorder=1000
        )
        return

    def __setup_general(self, axes):
        # background color
        axes.patch.set_facecolor(self.palette.bg)

        # setup title
        title_string = f'{self.ps.title}: {st.Map.ID}'
        if self.ps.subtit:
            title_string += f' ({self.ps.subtit})'
        axes.set_title(
            title_string, fontsize=10, pad=st.Plot.img_title_vpad
        )
        return

    def __to_dict(self):
        data = {
            'timestamp': st.timestamp,
            'map': st.Map.to_dict(),
            'cache': st.Cache.to_dict(),
            'metric': {
                'code': self.ps.code,
                'x': self.X,
                'usage_ratio': self.usage_ratio
            }
        }
        return data

    def load_from_dict(self, data):
        """Load data from dictionary"""
        if data['code'] != self.ps.code:
            return
        self.X = data['x']
        self.usage_ratio = data['usage_ratio']
        return

    def plot_from_dict(self, data, bg_module=None):
        self.load_from_dict(data)
        self.export_plots(bg_module=bg_module)
        return
