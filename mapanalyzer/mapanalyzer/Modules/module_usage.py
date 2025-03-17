import matplotlib.pyplot as plt
from itertools import zip_longest

from ..settings import Settings as st
from ..util import MetricStrings, Palette, PlotFile
from ..ui import UI
from .base import BaseModule

class CacheUsage(BaseModule):
    hue = 120
    supported_metrics = {
        'CUR' : MetricStrings(
            about  = ('Percentage of valid bytes in the cache that are used '
                      'before eviction.'),
            title  = 'CUR',
            subtit = 'higher is better',
            number = '04',
            xlab   = 'Time [access instr.]',
            ylab   = 'Cache Usage Ratio [%]',
        )
    }
    supported_aggr_metrics = {
        'CUR' : MetricStrings(
            about  = ('Average of the percentage of valid bytes in the cache '
                      'that are used before eviction.'),
            title  = 'Aggregated CUR',
            subtit = 'higher is better',
            number = '04',
            xlab   = 'Time [access instr.]',
            ylab   = 'Cache Usage Ratio [%]',
        )
    }

    def __init__(self):
        # enable metric if user requested it or if used as background
        self.enabled = (any(m in st.Metrics.enabled
                           for m in self.supported_metrics.keys()) or
                        st.Metrics.bg in self.supported_metrics)
        if not self.enabled:
            return

        # METRIC INTERNAL VARIABLES
        self.accessed_bytes = 0
        self.valid_bytes = 0
        self.usage_ratio = [-1] * st.Map.time_size
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

    def CUR_to_dict(self):
        return {
            'code' : 'CUR',
            'usage_ratio' : self.usage_ratio
        }

    def dict_to_CUR(self, data):
        try:
            self.usage_ratio = data['usage_ratio']
        except:
            class_name = self.__class__.__name__
            UI.error(f'{class_name}.dict_to_CUR(): Malformed data.')
        return

    def CUR_to_plot(self, mpl_axes, bg_mode=False):
        metric_code = 'CUR'
        met_str = self.supported_metrics[metric_code]

        # create data series
        X = range(st.Map.time_size)
        Y = self.usage_ratio


        #####################################
        ## CREATE COLOR PALETTE
        pal = Palette(hue=[self.hue],
                      # (line, _)
                      sat=st.Plot.p_sat,
                      lig=st.Plot.p_lig,
                      alp=st.Plot.p_alp)
        line_color = pal[0][0][0][0]
        line_width = st.Plot.p_lw


        #####################################
        ## PLOT METRIC
        mpl_axes.step(X, Y, where='mid', zorder=2, color=line_color, linewidth=line_width)


        ###########################################
        ## PLOT VISUALS
        # set plot limits
        X_pad = 0.5
        real_xlim, real_ylim = self.setup_limits(
            mpl_axes, metric_code, xlims=(X[0],X[-1]), x_pad=X_pad,
            ylims=(0,100), y_pad='auto')

        # set ticks based on the real limits
        self.setup_ticks(mpl_axes, xlims=real_xlim, ylims=real_ylim,
                         bases=(10, 10), bg_mode=bg_mode)

        # set grid
        self.setup_grid(mpl_axes, fn_axis='y', bg_mode=bg_mode)

        # insert text box with average usage
        if not bg_mode:
            text = ('Avg Usage: '
                    f'{sum(self.usage_ratio)/len(self.usage_ratio):.2f}%')
            self.draw_textbox(mpl_axes, text, metric_code)

        # set labels
        self.setup_labels(mpl_axes, met_str, bg_mode=bg_mode)

        # title and bg color
        self.setup_general(mpl_axes, pal.bg, met_str, bg_mode=bg_mode)
        return

    @classmethod
    def CUR_to_aggregated_plot(cls, pdata_dicts):
        """Given a list of pdata dictionaries, aggregate their
        values in a meaningful manner"""
        # metric info
        metric_code = pdata_dicts[0]['fg']['code']
        met_str = cls.supported_aggr_metrics[metric_code]

        # extract data from dictionaries and create figure
        total_pdatas = len(pdata_dicts)
        all_Y = [m['fg']['usage_ratio'] for m in pdata_dicts]
        fig,mpl_axes = plt.subplots(figsize=(st.Plot.width, st.Plot.height))


        #####################################
        # CREATE COLOR PALETTE
        pal = Palette(
            hue = (cls.hue, cls.hue),
            # (individual, average)
            sat = (60, 100),
            lig = (70,  30),
            alp = (10, 100))
        ind_color = pal[0][0][0][0]
        avg_color = pal[1][1][1][1]
        ind_line_width = st.Plot.p_aggr_ind_lw
        avg_line_width = st.Plot.p_aggr_avg_lw


        #####################################
        # PLOT INDIVIDUAL METRICS
        # also collect the last Xs
        last_Xs = []
        for pdata_Y in all_Y:
            X = range(len(pdata_Y))
            last_Xs.append(len(pdata_Y)-1)
            Y = pdata_Y
            mpl_axes.step(X, Y, where='mid', zorder=4, color=ind_color,
                          linewidth=ind_line_width)


        #####################################
        # PLOT MOVING AVERAGE OF METRICS
        # find range large enough to fit all plots
        X_min = 0
        X_max = max(last_Xs)
        super_X = list(range(X_min, X_max+1))

        all_ith_ys_list = list(zip_longest(*all_Y, fillvalue=None))
        Y_avg = [0] * len(super_X)
        for x,ith_ys in zip(super_X,all_ith_ys_list):
            valid_ys = [y for y in ith_ys if y is not None]
            ys_avg = sum(valid_ys) / len(valid_ys)
            Y_avg[x] = ys_avg
        mpl_axes.step(super_X, Y_avg, where='mid', zorder=6, color=avg_color,
                      linewidth=avg_line_width)


        #####################################
        # PLOT VERT LINE AT LAST X OF EACH METRIC AND AVERAGE
        if st.Plot.aggr_last_x:
            last_X_text = cls.draw_last_Xs(mpl_axes, last_Xs, (-20,120))


        #####################################
        # SETUP PLOT VISUALS
        # set plot limits
        X_pad = 0.5
        real_xlim, real_ylim = cls.setup_limits(
            mpl_axes, metric_code, xlims=(X_min,X_max), x_pad=X_pad,
            ylims=(0,100), y_pad='auto'
        )

        # set ticks based on the real limits
        cls.setup_ticks(
            mpl_axes, xlims=real_xlim, ylims=real_ylim,
            bases=(10, 10)
        )

        # set grid
        axis = 'y' if st.Plot.aggr_last_x else 'xy'
        cls.setup_grid(mpl_axes, axis=axis, fn_axis='y')

        # insert text box with average usage
        text = [f'Executions: {total_pdatas}']
        if st.Plot.aggr_last_x:
            text.append(last_X_text)
        text.append(rf'Avg2 {metric_code}: {sum(Y_avg)/len(Y_avg):.2f}%')
        cls.draw_textbox(mpl_axes, text, metric_code)

        # set labels
        cls.setup_labels(mpl_axes, met_str)

        # title and bg color
        cls.setup_general(mpl_axes, pal.bg, met_str)

        PlotFile.save(fig, metric_code, aggr=True)
        return
