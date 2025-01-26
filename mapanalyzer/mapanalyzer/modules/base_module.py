#!/usr/bin/env python3

from mapanalyzer.settings import Settings as st
from mapanalyzer.util import Palette, MetricStrings
"""This is the base mapanalyzer module upon which other modules are created.
This class is intended to be inherited from other mapanalyzer modules."""


class BaseModule:
    enabled = True
    name = 'Module Name'
    about = 'Short description of What the module does.'
    hue = 0 # base color of this module
    palette = Palette.default(hue) # color palette

    # Details about all the metrics supported by this module.
    # It could be one, or more.
    metrics = {
        'MET0' : MetricStrings(
            title  = 'The Metric Title', # To be shown in the plot's title
            subtit = 'extra info', # maybe 'higher is better'
            numb   = '000', # string (number-like) used for sorting filenames
            xlab   = 'X-axis Label',
            ylab   = 'Y-axis Label',
        ),
        'MET1' : MetricStrings(
            title  = 'Another Metric Title',
            subtit = 'extra info',
            numb   = '001',
            xlab   = 'X-axis Label',
            ylab   = 'Y-axis Label',
        )
    }

    # If this metric supports aggregation, then specify the details for it.
    aggr_metrics = {
        'MET0' : MetricStrings(
            title  = 'Aggregation Title',
            subtit = 'extra info',
            numb   = '000',
            xlab   = 'Aggregated X-axis Label',
            ylab   = 'Aggregated Y-axis Label',
        )
    }

    def has_metric(self, code):
        """Check whether a given code belongs to a metric in this module"""
        return code in self.metrics

    def setup_labels(self, mpl_axes, met_str, bg_mode=False):
        """setup axes labels"""
        ax_names = ('x', 'y')
        if bg_mode:
            ax_labels = ('', '')
        else:
            ax_labels = (met_str.xlab, met_str.ylab)

        # set label
        for ax,lb in zip(ax_names, ax_labels):
            # set label
            set_label = getattr(mpl_axes, f'set_{ax}label')
            set_label(lb)
        return

    def setup_grid(self, mpl_axes, fn_axis='y'):
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

        # set grid in x and y
        for ax,ga,gs,gw in zip(ax_names, ax_grd_a, ax_grd_s, ax_grd_w):
            mpl_axes.grid(axis=ax, which='both', zorder=1, alpha=ga,
                          linestyle=gs, linewidth=gw)
        return

    def setup_limits(self, mpl_axes, code, xlims, x_pad, ylims, y_pad):
        ax_names = ('x', 'y')
        ax_lmins = (xlims[0], ylims[0])
        ax_lmaxs = (xlims[1], ylims[1])
        ax_pads = (x_pad, y_pad)
        computed_xy_lims = []
        for ax,lmin,lmax,pad in zip(ax_names, ax_lmins, ax_lmaxs, ax_pads):
            ax_ranges = getattr(st.Plot, f'{ax}_ranges')
            if code in ax_ranges:
                lmin = int(ax_ranges[code][0])
                lmax = int(ax_ranges[code][1])
            set_lim = getattr(mpl_axes, f'set_{ax}lim')
            if pad == 'auto':
                pad = (lmax-lmin) / 200
            set_lim(lmin-pad, lmax+pad)
            computed_xy_lims.append((lmin,lmax))
        return computed_xy_lims

    def setup_ticks(self, mpl_axes, xlims, ylims, bases, bg_mode=False):
        if bg_mode:
            mpl_axes.set_xticks([])
            mpl_axes.set_yticks([])
            return
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

    def setup_general(self, mpl_axes, met_str, bg_mode=False):
        """ setup title and axes background color"""
        if bg_mode:
            mpl_axes.set_title('')
            mpl_axes.patch.set_facecolor(self.palette.bg)
            return
        title_string = met_str.title
        if st.Map.ID is not None:
            title_string += f': {st.Map.ID}'
        if met_str.subtit:
            title_string += f' ({met_str.subtit})'
        mpl_axes.set_title(title_string, fontsize=10,
                           pad=st.Plot.img_title_vpad)

        # background color
        mpl_axes.patch.set_facecolor(self.palette.bg)

        return

    def draw_textbox(self, mpl_axes, text, ha='right', va='top'):
        mpl_axes.text(0.98, 0.98, text, transform=mpl_axes.transAxes,
                      ha=ha, va=va, zorder=1000,
                      bbox=dict(facecolor=st.Plot.tbox_bg,
                                edgecolor=st.Plot.tbox_border,
                                boxstyle="square,pad=0.2"),
                      fontdict=dict(family=st.Plot.tbox_font,
                                    size=st.Plot.tbox_font_size))
        return

    def TRANSITION_export_plot(self, code, bg_to_plot=None, bg_module=None, bg_code=None):
        # if the function bg_to_plot was not directly given, then find out
        # whether bg_module has it
        if bg_to_plot is None:
            if None not in (bg_module, bg_code):
                bg_fn_name = f'{bg_code}_to_plot'
                try:
                    bg_to_plot = getattr(bg_module, bg_fn_name)
                except:
                    try:
                        module_name = bg_module.name
                    except:
                        UI.warning(f'Background module given doesn\'t have a '
                                   'name.')
                        module_name = bg_module.__class__.__name__
                    UI.warning(f'The given background module "{module_name}" '
                               f'has not defined the function "{bg_fn_name}". '
                               'Background plot will not be drawn.')
            else:
                UI.warning(f'Neither the background plotter function, or the '
                           'module and code of where to find it was given. '
                           'Background plot will not be drawn.')

        # if there is a bg_to_plot function, then create two sets of axes for
        # the background and foreground plots.
        if bg_to_plot is not None:
            fig,bg_axes = plt.subplots(
                facecolor='white',
                figsize=(st.Plot.width,st.Plot.height)
            )
            fg_axes = fig.add_axes(bg_axes.get_position())
            bg_to_plot(bg_axes, bg_mode=True)
        else:
            fig,fg_axes = plt.subplots(
                facecolor='white',
                figsize=(st.Plot.width, st.Plot.height)
            )

        # find the method that plots this specific metric
        fn_name = f'{code}_to_plot'
        try:
            metric_to_plot = getattr(self, fn_name)
        except:
            UI.error(f'{self.name} module has not defined the function '
                     f'"{fn_name}".')
        metric_to_plot(fg_axes)

        # save plot to figure file
        save_plot(fig, self.metrics[code])

        return

    def export_metric(self, code):
        class_name = self.__class__.__name__
        fn_name = f'{code}_to_dict'
        try:
            MET_to_dict = getattr(self, fn_name)
        except:
            UI.error('While exporting metric results. '
                     f'{class_name}.{fn_name}() is not defined.')

        return MET_to_dict()

    def import_metric(self, metric_dict, bg_mode=False):
        mode = 'bg' if bg_mode else 'fg'
        # get the function that imports this metric
        met_code = data[mode]['code']
        fn_name = f'dict_to_{met_code}'
        try:
            dict_to_metric = getattr(self, fn_name)
        except:
            UI.error(f'{module_name} module has not defined the function '
                     f'"{fn_name}".')
        dict_to_metric(data)

    @classmethod
    def export_aggregated_plot(cls, code, metrics_list):
        # find the method that plots the aggregated metrics
        fn_name = f'{code}_to_aggregated_plot'
        try:
            metric_to_aggregated_plot = getattr(cls, fn_name)
        except:
            UI.error(f'{self.name} module has not defined the function '
                     f'"{fn_name}".')
        metric_to_aggregated_plot(metrics_list)


# DEPRECATED

    def plot_from_dict(self, data, bg_module=None, bg_code=None):
        self.import_metric(data)
        code = data['fg']['code']
        self.export_plot(code, bg_module=bg_module, bg_code=bg_code)

    def DEPRECATED_export_all_plots(self, bg_to_plot=None, bg_module=None, bg_code=None):
        if not self.enabled:
            return

        # if the function bg_to_plot was not directly given, then find out
        # whether bg_module has it
        if bg_to_plot is None:
            if None not in (bg_module, bg_code):
                bg_fn_name = f'{bg_code}_to_bg_plot'
                try:
                    bg_to_plot = getattr(bg_module, bg_fn_name)
                except:
                    try:
                        module_name = bg_module.name
                    except:
                        UI.warning(f'Background module given doesn\'t have a '
                                   'name.')
                        module_name = bg_module.__class__.__name__
                    UI.warning(f'The given background module "{module_name}" '
                               f'has not defined the function "{bg_fn_name}". '
                               'Background plot will not be drawn.')
            else:
                UI.warning(f'Neither the background plotter function, or the '
                           'module and code of where to find it was given. '
                           'Background plot will not be drawn.')
        # for each metric in this module, save a figure
        for met, met_str in self.metrics:
            # if this metric is not included by the user, then skip its plot
            if met not in st.Plot.include:
                continue
            self.export_plot(code, bg_to_plot=bg_to_plot)

        return

    def DEPRECATED_export_all_pdats(self, bg_module=None, bg_code=None):
        if not self.enabled:
            return

        # find the background module to export its metric to a dictionary.
        bg_data = None
        if None not in (bg_module, bg_code):
            bg_fn_name = f'{bg_code}_to_dict'
            try:
                bg_to_dict = getattr(bg_module, bg_fn_name)
                # collect the data corresponding to the metric in the bg module
                bg_data = bg_to_dict()
            except:
                try:
                    module_name = bg_module.name
                except:
                    UI.warning(f'Background module given doesn\'t have a name.')
                    module_name = '?????'
                UI.warning(f'Background module "{module_name}" has not defined '
                           f'the function "{bg_fn_name}". '
                           'Not saving background metric data.')


        # for each metric in this module, save a metric file
        for code, met_str in self.metrics:
            # if this metric is not included by the user, then skip its metric
            if code not in st.Plot.include:
                continue

            # if this module and the background module are the same, and if
            # this module's code is the same as the bg code, then let's avoid
            # double storing the same info in fg and bg:
            if self == bg_module and code == bg_code:
                actual_bg_data = None
            else:
                actual_bg_data = bg_data

            self.export_metric(code, bg_data=actual_bg_data)
        return
