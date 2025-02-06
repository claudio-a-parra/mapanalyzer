#!/usr/bin/env python3

from mapanalyzer.settings import Settings as st
from mapanalyzer.util import Palette, MetricStrings, sample_list
from mapanalyzer.ui import UI
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
    supported_metrics = {
        'MET0' : MetricStrings(
            about  = 'Short description of metric.', # to be shown in the tool
            title  = 'The Metric Title', # To be shown in the plot's title
            subtit = 'extra info', # maybe 'higher is better'
            number = '000', # string (number-like) used for sorting filenames
            xlab   = 'X-axis Label',
            ylab   = 'Y-axis Label',
        ),
        'MET1' : MetricStrings(
            about  = 'Description of Another metric.',
            title  = 'Another Metric Title',
            subtit = 'extra info',
            number = '001',
            xlab   = 'X-axis Label',
            ylab   = 'Y-axis Label',
        )
    }

    # If this metric supports aggregation, then specify the details for it.
    supported_aggr_metrics = {
        'MET0' : MetricStrings(
            about  = 'Short description of the aggregated metric',
            title  = 'Aggregation Title',
            subtit = 'extra info',
            number   = '000',
            xlab   = 'Aggregated X-axis Label',
            ylab   = 'Aggregated Y-axis Label',
        )
    }

    @classmethod
    def has_metric(cls, code):
        """Check whether a given code belongs to a metric in this module"""
        return str(code).upper() in cls.metrics

    @classmethod
    def setup_labels(cls, mpl_axes, met_str, bg_mode=False):
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

    @classmethod
    def setup_grid(cls, mpl_axes, axis='both', fn_axis='y', bg_mode=False):
        """setup plot grid for main and secondary axes.
        fn_axis {x,y}        : determines which one is the main (dependent
                               variable) axis.
        axis {both,xy,x,y}   : determines which axis gets to draw a grid.
        """
        # if bg_mode, don't draw anything.
        if bg_mode:
            mpl_axes.grid(False)
            return
        # sanitize axis parameter
        if axis in ('both', 'xy', 'yx'):
            axis = 'xy'
        elif axis not in 'xy':
            UI.error(f'Module.setup_grid(): Incorrect axis=\'{axis}\' '
                     'parameter value')

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
            if ax in axis:
                mpl_axes.grid(axis=ax, which='both', zorder=1, alpha=ga,
                              linestyle=gs, linewidth=gw)
        return

    @classmethod
    def setup_limits(cls, mpl_axes, metric_code, xlims, x_pad, ylims, y_pad,
                     invert_x=False, invert_y=False):
        ax_names = ('x', 'y')
        ax_lmins = (xlims[0], ylims[0])
        ax_lmaxs = (xlims[1], ylims[1])
        ax_pads = (x_pad, y_pad)
        ax_inv = (invert_x, invert_y)
        computed_xy_lims = []
        for ax,lmin,lmax,pad,inv in zip(ax_names, ax_lmins, ax_lmaxs, ax_pads,
                                        ax_inv):
            # obtain ranges for this axis
            ax_ranges = getattr(st.Plot, f'{ax}_ranges')
            if metric_code in ax_ranges:
                lmin = ax_ranges[metric_code][0]
                lmax = ax_ranges[metric_code][1]

            # set limits for this axis
            set_lim = getattr(mpl_axes, f'set_{ax}lim')
            if pad == 'auto':
                pad = (lmax-lmin) / 200
            set_lim(lmin-pad, lmax+pad)

            # decide whether to invert the axis
            if inv:
                invert_axis = getattr(mpl_axes, f'invert_{ax}axis')
                invert_axis()

            # save the computed limits to inform them back to caller
            computed_xy_lims.append((lmin,lmax))
        return computed_xy_lims

    @classmethod
    def setup_ticks(cls, mpl_axes, xlims, ylims, bases, bg_mode=False):
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
            if type(lm[0]) is float or type(lm[1]) is float:
                # create a list of floats
                resolution = 3
                step = 1/(10**resolution)
                rdiff = round(lm[1] - lm[0] + step, resolution)
                list_len = int(rdiff / step)
                full_list = [lm[0]+i*step for i in range(list_len+1)]
            else:
                full_list = range(lm[0], lm[1]+1)

            ticks = sample_list(full_list, base=bs, n=mt)
            set_ticks(ticks)
        return

    @classmethod
    def setup_manual_grid(cls, mpl_axes, axis='both', hlines=None, xlims=None,
                            vlines=None, ylims=None, main_axis='y'):
        if axis == 'both':
            axis = 'xy'
        grid_color = '#BFBFBF60' # apparently the default color

        # If plotting vertical lines (across the X axis)
        if 'x' in axis:
            if not vlines or not ylims:
                UI.error(f'Cannot call __setup_manual_grid() with axis=x, and '
                         'vlines or ylims None.')

            # select 'main' or 'other' style
            if main_axis == 'x':
                sty,wid = st.Plot.grid_style[0],st.Plot.grid_width[0]
            else:
                sty,wid = st.Plot.grid_style[1],st.Plot.grid_width[1]

            mpl_axes.vlines(x=vlines, ymin=ylims[0], ymax=ylims[1],
                            color=grid_color, linestyle=sty, linewidth=wid,
                            zorder=1)


        # If plotting horizontal lines (across the Y axis)
        if 'y' in axis:
            if not hlines or not xlims:
                UI.error(f'Cannot call __setup_manual_grid() with axis=y, and '
                         'hlines or ylims None.')

            # select 'main' or 'other' style
            if main_axis == 'y':
                sty,wid = st.Plot.grid_style[0],st.Plot.grid_width[0]
            else:
                sty,wid = st.Plot.grid_style[1],st.Plot.grid_width[1]

            mpl_axes.hlines(y=hlines, xmin=xlims[0], xmax=xlims[1],
                            color=grid_color, linestyle=sty, linewidth=wid,
                            zorder=1)
        return

    @classmethod
    def setup_general(cls, mpl_axes, bg_color, met_str, bg_mode=False):
        """ setup title and axes background color"""
        # set title only if in foreground mode
        title_string = ''
        if not bg_mode:
            title_string = met_str.title
            if st.Map.ID is not None:
                title_string += f': {st.Map.ID}'
            if met_str.subtit:
                title_string += f' ({met_str.subtit})'

        mpl_axes.set_title(title_string, fontsize=10,
                           pad=st.Plot.img_title_vpad)

        # background color
        mpl_axes.patch.set_facecolor(bg_color)

        # Set the zorder of the spines
        for spine in mpl_axes.spines.values():
            spine.set_zorder(500)

        return

    @classmethod
    def draw_textbox(cls, mpl_axes, text, metric_code):
        # get the offset of the textbox from the user options
        h_off,v_off=0.98, 0.98
        if metric_code in st.Plot.textbox_offsets:
            h_off,v_off = st.Plot.textbox_offsets[metric_code]

        # pick the anchor point of the textbox based on the horizontal
        # and vertical offsets
        if h_off > 0.667:
            hor_anchor = 'right'
        elif h_off < 0.333:
            hor_anchor = 'left'
        else:
            hor_anchor = 'center'
        if v_off > 0.667:
            vert_anchor = 'top'
        elif v_off < 0.333:
            vert_anchor = 'bottom'
        else:
            vert_anchor = 'center'

        # join lines of text
        if type(text) is str:
            text = text.split('\n')
        text_cols = [[], []]
        for line in text:
            line_parts = line.split(':')
            if len(line_parts) != 2:
                l0,l1 = line.strip(),''
            else:
                l0,l1 = line_parts[0].strip(),line_parts[1].strip()
            text_cols[0].append(l0)
            text_cols[1].append(l1)
        text = UI.columns(text_cols, sep=': ', cols_align='lr', get_str=True)

        # draw the text box
        mpl_axes.text(h_off, v_off, text, transform=mpl_axes.transAxes,
                      ha=hor_anchor, va=vert_anchor, zorder=1000,
                      bbox=dict(facecolor=st.Plot.tbox_bg,
                                edgecolor=st.Plot.tbox_border,
                                boxstyle="square,pad=0.2"),
                      fontdict=dict(family=st.Plot.tbox_font,
                                    size=st.Plot.tbox_font_size))
        return

    @classmethod
    def draw_last_Xs(cls, mpl_axes, last_Xs, ylims):
        pal = Palette(
            # (individual, avg)
            hue = (0, 0),
            sat = (0, 50),
            lig = (93, 75),
            alp = (100,100))
        ind_color = pal[0][0][0][0]
        avg_color = pal[1][1][1][1]
        ind_line_width = st.Plot.p_aggr_ind_vlw
        avg_line_width = st.Plot.p_aggr_avg_vlw
        ymax = ylims[0]
        ymin = ylims[1]

        # plot individual last_Xs and average
        mpl_axes.vlines(last_Xs, ymin=ymin, ymax=ymax, colors=ind_color,
                        linestyles='solid', linewidth=ind_line_width,
                        zorder=2)
        last_X_avg = sum(last_Xs)/len(last_Xs)
        mpl_axes.vlines([last_X_avg], ymin=ymin, ymax=ymax,
                        colors=avg_color, linestyles='solid',
                        linewidth=avg_line_width, zorder=3)

        return f'Avg Exec Duration: {last_X_avg:.0f}'

    @classmethod
    def draw_last_Ys(cls, mpl_axes, last_Ys, xlims):
        pal = Palette(
            # (individual, avg)
            hue = (0, 0),
            sat = (0, 50),
            lig = (93, 75),
            alp = (100,100))
        ind_color = pal[0][0][0][0]
        avg_color = pal[1][1][1][1]
        ind_line_width = st.Plot.p_aggr_ind_vlw
        avg_line_width = st.Plot.p_aggr_avg_vlw
        xmax = xlims[0]
        xmin = xlims[1]

        # plot individual last_Ys and average
        mpl_axes.hlines(last_Ys, xmin=xmin, xmax=xmax, colors=ind_color,
                        linestyles='solid', linewidth=ind_line_width,
                        zorder=2)
        last_Y_avg = sum(last_Ys)/len(last_Ys)
        mpl_axes.hlines([last_Y_avg], xmin=xmin, xmax=xmax,
                        colors=avg_color, linestyles='solid',
                        linewidth=avg_line_width, zorder=3)

        return f'Avg Memory Size [blocks]: {last_Y_avg:.0f}'

    def export_plot(self, metric_code, mpl_axes, bg_mode=False):
        fn_name = f'{metric_code}_to_plot'
        try:
            MET_to_plot = getattr(self, fn_name)
        except:
            class_name = self.__class__.__name__
            UI.error(f'While exporting "{metric_code}" metric plot. '
                     f'{class_name}.{fn_name}() is not defined.')
        MET_to_plot(mpl_axes, bg_mode=bg_mode)
        return

    def export_data(self, metric_code):
        fn_name = f'{metric_code}_to_dict'
        try:
            MET_to_dict = getattr(self, fn_name)
        except:
            class_name = self.__class__.__name__
            UI.error(f'While exporting "{metric_code}" metric data. '
                     f'{class_name}.{fn_name}() is not defined.')
        return MET_to_dict()

    def import_data(self, metric_code, data):
        fn_name = f'dict_to_{metric_code}'
        try:
            dict_to_MET = getattr(self, fn_name)
        except:
            class_name = self.__class__.__name__
            UI.error(f'While importing "{metric_code}" metric data. '
                     f'{class_name}.{fn_name}() is not defined.')
        dict_to_MET(data)
        return

    @classmethod
    def export_aggregated_plot(cls, pdata_dicts):
        # find the method that plots the aggregated metrics
        metric_code = pdata_dicts[0]['fg']['code'].upper()
        fn_name = f'{metric_code}_to_aggregated_plot'
        try:
            MET_to_aggregated_plot = getattr(cls, fn_name)
        except:
            class_name = cls.__name__
            UI.error(f'Trying to aggregate "{metric_code}" data. '
                     f'{class_name}.{fn_name}() is not defined.')
        MET_to_aggregated_plot(pdata_dicts)
