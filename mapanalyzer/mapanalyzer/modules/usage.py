import matplotlib.pyplot as plt


from mapanalyzer.util import create_up_to_n_ticks, PlotStrings, Palette, \
    save_fig, save_json
from mapanalyzer.settings import Settings as st

class CacheUsage:
    def __init__(self, shared_X=None, hue=120):
        self.name = 'Cache Usage Rate'
        self.about = ('Percentage of valid bytes in cache that are used '
                           'before eviction.')
        self.ps = PlotStrings(
            title  = 'CUR',
            code   = 'CUR',
            xlab   = 'Time [access instr.]',
            ylab   = 'Cache Usage Rate [%]',
            suffix = '_plot-05-usage',
            subtit = 'higher is better'
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
        print(f'{ind}{self.name:{st.plot.ui_modulename_hpad}}: '
              f'{self.about}')
        return

    def finalize(self):
        # no post-simulation computation to be done
        return

    def export_metrics(self):
        # export plotcode, X, and Y to json file
        raise Exception('[!!] NOT IMPLEMENTED')

    def setup_X_axis(self):
        # define X-axis data range based on data and user input
        X_min = self.X[0]
        X_max = self.X[-1]
        if self.ps.code in st.Plot.x_ranges:
            X_min = int(st.Plot.x_ranges[self.ps.code][0])
            X_max = int(st.Plot.x_ranges[self.ps.code][1])
        X_padding = (X_max - X_min) / 200
        self.axes.set_xlim(X_min-X_padding, X_max+X_padding)

        # Axis details: label, ticks and grid
        self.axes.set_xlabel(self.ps.xlab)
        rot = -90 if st.Plot.x_orient == 'v' else 0
        self.axes.tick_params(axis='x',
                              top=False, bottom=True,
                              labeltop=False, labelbottom=True,
                              rotation=rot, width=st.Plot.grid_other_width)
        x_ticks = create_up_to_n_ticks(self.X, base=10,
                                       n=st.Plot.max_xtick_count)
        self.axes.set_xticks(x_ticks)
        self.axes.grid(axis='x', which='both',
                       zorder=1,
                       alpha=st.Plot.grid_other_alpha,
                       linewidth=st.Plot.grid_other_width,
                       linestyle=st.Plot.grid_other_style)
        return X_padding

    def setup_Y_axis(self):
        # define Y-axis data range based on data and user input
        Y_min = 0
        Y_max = 100
        if self.ps.code in st.Plot.y_ranges:
            Y_min = int(st.Plot.y_ranges[self.ps.code][0])
            Y_max = int(st.Plot.y_ranges[self.ps.code][1])
        Y_padding = (Y_max - Y_min) / 200
        self.axes.set_ylim(Y_min-Y_padding, Y_max+Y_padding)

        # Axis details: label, ticks, and grid
        self.axes.set_ylabel(self.ps.ylab)
        self.axes.tick_params(axis='y',
                              left=True, right=False,
                              labelleft=True, labelright=False,
                              width=st.Plot.grid_main_width)
        y_ticks = create_up_to_n_ticks(range(Y_min, Y_max+1), base=10,
                                       n=st.Plot.max_ytick_count)
        self.axes.set_yticks(y_ticks)
        self.axes.grid(axis='y', which='both',
                       zorder=1,
                       alpha=st.Plot.grid_main_alpha,
                       linewidth=st.Plot.grid_main_width,
                       linestyle=st.Plot.grid_main_style)
        return Y_padding

    def draw_textbox(self):
        # insert text box with average usage
        avg = sum(self.usage_ratio)/len(self.usage_ratio)
        text = f'Avg: {avg:.2f}%'
        self.axes.text(
            0.98, 0.98, text, transform=self.axes.transAxes,
            ha='right', va='top',
            bbox=dict(facecolor=st.Plot.tbox_bg,
                      edgecolor=st.Plot.tbox_border,
                      boxstyle="square,pad=0.2"),
            fontdict=dict(family=st.Plot.tbox_font,
                          size=st.Plot.tbox_font_size),
            zorder=1000)
        return

    def setup_general(self):
        # background color
        self.axes.patch.set_facecolor(self.palette.bg)

        # setup title
        title_string = f'{self.ps.title}: {st.Map.prefix}'
        if self.ps.subtit:
            title_string += f'. ({self.ps.subtit})'
        self.axes.set_title(title_string, fontsize=10,
                            pad=st.Plot.img_title_vpad)
        return

    def plot(self, bottom_tool=None):
        if not self.enabled:
            return

        # create two set of axes: for the map (bottom) and the tool
        fig,bottom_axes = plt.subplots(figsize=(st.Plot.width, st.Plot.height))
        self.axes = fig.add_axes(bottom_axes.get_position())

        # plot map
        if bottom_tool is not None:
            bottom_tool.plot(axes=bottom_axes)

        # setup X and Y axes and add tails to the X and Y arrays
        # for cosmetic purposes (because of the step function)
        X_padding = self.setup_X_axis()
        Y_padding = self.setup_Y_axis()
        X = [self.X[0]-X_padding] + self.X + [self.X[-1]+X_padding]
        Y = [self.usage_ratio[0]] + self.usage_ratio + [self.usage_ratio[-1]]


        # plot the usage rate
        self.axes.fill_between(X, -1, Y, step='mid', zorder=2,
                               color=self.palette[0][0],
                               facecolor=self.palette[0][1],
                               linewidth=st.Plot.linewidth)
        # finish plot setup
        self.draw_textbox()
        self.plot_setup_general()

        # save data and image
        save_json(self.to_json(), self.ps.code, self.ps.suffix)
        save_fig(fig, self.ps.code, self.ps.suffix)
        return

    def to_json(self):
        data = {
            "plotcode": self.ps.code, # to check validity
            "map": st.map.to_jdict(),
            "cache": st.cache.to_jdict(),
            "data_series": [
                {
                    "label": "usage_ratio", # data to export
                    "x": self.X,
                    "y": self.usage_ratio
                }
            ]
        }
        return data

    def from_json(self, jdict):
        # import
        return

    def from_json(self, json_in):
        import_from_json(json_path=json_in)
        slef.plot(bottom_tool=bottom_tool)
        return

    def aggregate_plots(self, jdicts):

        return
