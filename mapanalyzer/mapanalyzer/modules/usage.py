import matplotlib.pyplot as plt


from mapanalyzer.util import create_up_to_n_ticks, MetricStrings, Palette, \
    save_plot, save_metric, save_aggr
from mapanalyzer.settings import Settings as st
from mapanalyzer.ui import UI

class CacheUsage:
    # Module info
    name = 'Cache Usage Rate'
    about = 'Percentage of valid bytes in cache that are used before eviction'
    metrics = ['CUR']
    hue = 120
    palette = Palette(
        hue=(hue, hue),
        sat=st.Plot.p_sat,
        lig=st.Plot.p_lig,
        alp=st.Plot.p_alp)
    # Metric(s) info
    met_str = MetricStrings(
        title  = 'CUR',
        subtit = 'higher is better',
        numb   = '01',
        code   = 'CUR',
        xlab   = 'Time [access instr.]',
        ylab   = 'Cache Usage Rate [%]'
    )
    # Aggregated Metric info
    aggr_met_str = MetricStrings(
        title  = 'Aggregated CUR',
        subtit = 'higher is better',
        numb   = '01',
        code   = 'CUR_aggr',
        xlab   = 'Time [access instr.]',
        ylab   = 'Cache Usage Rate [%]'
    )

    def __init__(self, shared_X=None):
        self.enabled = self.met_str.code in st.Plot.include
        if not self.enabled:
            return

        if shared_X is not None:
            self.X = shared_X
        else:
            self.X = [i for i in range(st.Map.time_size)]

        self.accessed_bytes = 0
        self.valid_bytes = 0
        self.usage_ratio = [-1] * len(self.X)
        return

    def probe(self, delta_access=0, delta_valid=0):
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

    def finalize(self):
        # no post-simulation computation to be done
        return

    def __to_dict(self):
        return {
            'code': self.met_str.code,
            'x': self.X,
            'usage_ratio': self.usage_ratio
        }

    def export_metrics(self, bg_module):
        data = st.to_dict()
        data['metric'] = self.__to_dict()
        data['mapplot'] = bg_module.to_dict()
        save_metric(data, self.met_str)
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

        # padded data series
        X_pad = 0.5
        X = [self.X[0]-X_pad] + self.X + [self.X[-1]+X_pad]
        Y = [self.usage_ratio[0]] + self.usage_ratio + [self.usage_ratio[-1]]

        # plot the usage rate
        fg_axes.fill_between(
            X, -1, Y, step='mid', zorder=2,
            color=self.palette[0][0][0][0],
            facecolor=self.palette[1][1][1][1],
            linewidth=st.Plot.linewidth
        )

        # Plot setup
        self.__setup_general(fg_axes, self.palette.bg, self.met_str)
        self.__setup_axes(axes, self.met_str.code, fn_axis='y',
                          xlims=(self.X[0],self.X[-1]), xpad=X_pad,
                          ylims=(0,100), ypad='auto', tick_bases=(10, 10),
                          grid=True)

        # insert text box with average usage
        text = f'Avg: {sum(self.usage_ratio)/len(self.usage_ratio):.2f}%'
        self.__draw_textbox(fg_axes, text)

        # save figure
        save_plot(fig, self.met_str)
        return

    def load_from_dict(self, data):
        """Load data from dictionary"""
        if data['code'] != self.met_str.code:
            return
        self.X = data['x']
        self.usage_ratio = data['usage_ratio']
        return

    def plot_from_dict(self, data, bg_module=None):
        self.load_from_dict(data)
        self.export_plots(bg_module=bg_module)
        return

    @classmethod
    def __setup_axes(cls, mpl_axes, code, fn_axis, xlims, xpad, ylims, ypad,
                     tick_bases, grid=False):
        cls.__setup_labels(mpl_axes)
        if grid:
            cls.__setup_grid(mpl_axes, fn_axis=fn_axis)
        comp_lims = cls.__setup_limits(mpl_axes, code, xlims, xpad, ylims, ypad)
        cls.__setup_ticks(mpl_axes, comp_lims[0], comp_lims[1], tick_bases)
        return

    @classmethod
    def __setup_labels(cls, mpl_axes):
        """setup axes labels"""
        ax_names = ('x', 'y')
        ax_labels = (cls.met_str.xlab, cls.met_str.ylab)

        # set label
        for ax,lb in zip(ax_names, ax_labels):
            # set label
            set_label = getattr(mpl_axes, f'set_{ax}label')
            set_label(lb)
        return

    @classmethod
    def __setup_grid(cls, mpl_axes, fn_axis='y'):
        """setup grid"""
        ax_names = ('x', 'y')
        # Values associated to either the independent or function axes.
        # If the function axis is X, then reverse axes meanings.
        ax_grd_a = st.Plot.grid_alpha
        ax_grd_s = st.Plot.grid_style
        ax_grd_w = st.Plot.grid_width
        if fn_axis == 'x':
            ax_grd_a = ax_grd_a[::-1]
            ax_grd_s = ax_grd_s[::-1]
            ax_grd_w = ax_grd_w[::-1]

        # set grid
        for ax,ga,gs,gw in zip(ax_names, ax_grd_a, ax_grd_s, ax_grd_w):
            mpl_axes.grid(axis=ax, which='both', zorder=1, alpha=ga,
                          linestyle=gs, linewidth=gw)
        return

    @classmethod
    def __setup_limits(cls, mpl_axes, code, xlims, x_pad, ylims, y_pad):
        ax_names = ('x', 'y')
        ax_lmins = (xlims[0], ylims[0])
        ax_lmaxs = (xlims[1], ylims[1])
        ax_pads = (x_pad, y_pad)
        computed_lims = []
        for ax,lmin,lmax,pad in zip(ax_names, ax_lmins, ax_lmaxs, ax_pads):
            ax_ranges = getattr(st.Plot, f'{ax}_ranges')
            if code in ax_ranges:
                lmin = int(ax_ranges[code][0])
                lmax = int(ax_ranges[code][1])
            set_lim = getattr(mpl_axes, f'set_{ax}lim')
            if pad == 'auto':
                pad = (lmax-lmin) / 200
            set_lim(lmin-pad, lmax+pad)
            computed_lims.append((lmin,lmax))
        return computed_lims

    @classmethod
    def __setup_ticks(cls, mpl_axes, xlims, ylims, bases):
        ax_names = ('x', 'y')
        ax_rotat = (-90 if st.Plot.x_orient == 'v' else 0, 0)
        ax_width = st.Plot.grid_width
        ax_lims = (xlims, ylims)
        ax_bases = bases
        ax_mtick = st.Plot.ticks_max_count
        # set ticks
        for ax,rt,wd,lm,bs,mt in zip(ax_names, ax_rotat, ax_width, ax_lims,
                                     ax_bases, ax_mtick):
            mpl_axes.tick_params(axis=ax, rotation=rt, width=wd)
            set_ticks = getattr(mpl_axes, f'set_{ax}ticks')
            ticks = create_up_to_n_ticks(range(lm[0], lm[1]+1), base=bs, n=mt)
            set_ticks(ticks)

    @classmethod
    def __setup_general(cls, mpl_axes, bg_color, met_str):
        # background color
        mpl_axes.patch.set_facecolor(bg_color)

        # setup title
        title_string = met_str.title
        if st.Map.ID is not None:
            title_string += f': {st.Map.ID}'
        if met_str.subtit:
            title_string += f' ({cls.met_str.subtit})'
        mpl_axes.set_title(title_string, fontsize=10,
                           pad=st.Plot.img_title_vpad)
        return

    @classmethod
    def __draw_textbox(cls, mpl_axes, text, ha='right', va='top'):
        mpl_axes.text(0.98, 0.98, text, transform=mpl_axes.transAxes,
                      ha=ha, va=va, zorder=1000,
                      bbox=dict(facecolor=st.Plot.tbox_bg,
                                edgecolor=st.Plot.tbox_border,
                                boxstyle="square,pad=0.2"),
                      fontdict=dict(family=st.Plot.tbox_font,
                                    size=st.Plot.tbox_font_size))
        return

    @classmethod
    def export_aggregated_plots(cls, metrics_list):
        """Given a list of 'metric' dictionaries, aggregate their
        values in a meaningful manner"""
        num_mets = len(metrics_list)
        all_x = [m['x'] for m in metrics_list]
        all_y = [m['usage_ratio'] for m in metrics_list]

        fig,mpl_axes = plt.subplots(figsize=(st.Plot.width, st.Plot.height))

        # plot the individual usage rates
        palette = Palette(
            hue = (cls.hue, cls.hue),
            sat = (st.Plot.p_sat[0], 50),
            lig = (st.Plot.p_lig[0], 60),
            alp = (100, 80)
        )
        avg_color = palette[0][0][0][0]
        avg_width = 2
        one_color = palette[1][1][1][1]
        one_width = 0.5
        for m in range(num_mets):
            met_x = all_x[m]
            met_y = all_y[m]
            mpl_axes.step(
                met_x, met_y, where='mid', zorder=2,
                color=one_color, linewidth=one_width
            )

        # find range large enough to fit all plots
        X_min = min(m[0] for m in all_x)
        X_max = max(m[-1] for m in all_x)

        # Plot setup
        X_pad = 0.5
        cls.__setup_general(mpl_axes, 'white', cls.aggr_met_str)
        cls.__setup_axes(mpl_axes, cls.met_str.code, fn_axis='y',
                         xlims=(X_min, X_max), xpad=X_pad,
                         ylims=(0,100), ypad='auto', tick_bases=(10, 10),
                         grid=True)


        save_aggr(fig, cls.aggr_met_str)
        return
