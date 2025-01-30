import matplotlib.pyplot as plt
from itertools import zip_longest

from mapanalyzer.modules.base_module import BaseModule
from mapanalyzer.util import MetricStrings, Palette, PlotFile
from mapanalyzer.settings import Settings as st
from mapanalyzer.ui import UI

class CacheUsage(BaseModule):
    # Module info
    name = 'Cache Usage Rate'
    about = 'Percentage of valid bytes in cache that are used before eviction'
    hue = 120
    palette = Palette.default(hue)

    supported_metrics = {
        'CUR' : MetricStrings(
            about  = ('Percentage of valid bytes in the cache that are used '
                      'before eviction.'),
            title  = 'Cache Usage Ratio',
            subtit = 'higher is better',
            number = '01',
            xlab   = 'Time [access instr.]',
            ylab   = 'Cache Usage Rate [%]',
        )
    }
    supported_aggr_metrics = {
        'CUR' : MetricStrings(
            about  = ('Average of the percentage of valid bytes in the cache '
                      'that are used before eviction.'),
            title  = 'Aggregated CUR',
            subtit = 'higher is better',
            number = '01',
            xlab   = 'Time [access instr.]',
            ylab   = 'Cache Usage Rate [%]',
        )
    }


    def __init__(self):
        # enable metric if user requested it or if used as background
        self.enabled = any(m in st.Metrics.enabled
                           for m in self.supported_metrics.keys())
        self.enabled = self.enabled or st.Metrics.bg in self.supported_metrics
        if not self.enabled:
            return

        # METRIC INTERNAL VARIABLES
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

    def CUR_to_dict(self):
        return {
            'code': 'CUR',
            'x': self.X,
            'usage_ratio': self.usage_ratio
        }

    def dict_to_CUR(self, data):
        # check for malformed (no keys) dict.
        all_keys = ['x', 'usage_ratio']
        if not all(k in data for k in all_keys):
            UI.error(f'While importing CUR. Not all necessary keys are '
                     f'present ({",".join(all_keys)}).')
        self.X = data['x']
        self.usage_ratio = data['usage_ratio']
        return

    def CUR_to_plot(self, mpl_axes, bg_mode=False):
        if not self.enabled:
            return

        metric_code = 'CUR'
        met_str = self.supported_metrics[metric_code]

        # pad data series
        X_pad = 0.5
        X = [self.X[0]-X_pad] + self.X + [self.X[-1]+X_pad]
        Y = [self.usage_ratio[0]] + self.usage_ratio + [self.usage_ratio[-1]]

        # plot the usage rate
        mpl_axes.fill_between(
            X, -1, Y, step='mid', zorder=2,
            color=self.palette[0][0][0][0],
            facecolor=self.palette[1][1][1][1],
            linewidth=st.Plot.linewidth
        )

        # set plot limits
        real_xlim, real_ylim = self.setup_limits(
            mpl_axes, metric_code, xlims=(self.X[0],self.X[-1]), x_pad=X_pad,
            ylims=(0,100), y_pad='auto'
        )

        # set ticks based on the real limits
        self.setup_ticks(
            mpl_axes, xlims=real_xlim, ylims=real_ylim,
            bases=(10, 10),
            bg_mode=bg_mode
        )

        # set grid
        self.setup_grid(mpl_axes, fn_axis='y')

        # insert text box with average usage
        if not bg_mode:
            text = f'Avg: {sum(self.usage_ratio)/len(self.usage_ratio):.2f}%'
            self.draw_textbox(mpl_axes, text)

        # set labels
        self.setup_labels(mpl_axes, met_str, bg_mode=bg_mode)

        # title and bg color
        self.setup_general(mpl_axes, self.palette.bg, met_str, bg_mode=bg_mode)
        return

    @classmethod
    def CUR_to_aggregated_plot(cls, pdata_dicts):
        """Given a list of 'metric' dictionaries, aggregate their
        values in a meaningful manner"""
        # metric info
        metric_code = 'CUR'
        met_str = cls.supported_aggr_metrics[metric_code]

        # extract data from dictionaries and create figure
        total_pdatas = len(pdata_dicts)
        all_X = [m['fg']['x'] for m in pdata_dicts]
        all_Y = [m['fg']['usage_ratio'] for m in pdata_dicts]
        fig,mpl_axes = plt.subplots(figsize=(st.Plot.width, st.Plot.height))


        #####################################
        # PLOT INDIVIDUAL METRICS AND THEIR AVERAGE
        pal = Palette(
            hue = (cls.hue, cls.hue),
            sat = (100, 60),
            lig = (20, 70),
            alp = (100,60))
        avg_color = pal[0][0][0][0]
        avg_width = 1.5
        one_color = pal[1][1][1][1]
        one_width = 0.5

        for met_idx in range(total_pdatas):
            met_x = all_X[met_idx]
            met_y = all_Y[met_idx]
            mpl_axes.step(met_x, met_y, where='mid', zorder=4,
                          color=one_color, linewidth=one_width)

        # find range large enough to fit all plots
        X_min = min(m[0] for m in all_X)
        X_max = max(m[-1] for m in all_X)
        X = list(range(X_min, X_max+1))

        # PLOT MOVING AVERAGE OF METRICS
        all_ith_ys_list = list(zip_longest(*all_Y, fillvalue=None))
        Y_average = [0] * len(X)
        for x,ith_ys in zip(X,all_ith_ys_list):
            valid_ys = [y for y in ith_ys if y is not None]
            ys_avg = sum(valid_ys) / len(valid_ys)
            Y_average[x] = ys_avg

        # plot black shadow to popup the avg line
        # mpl_axes.step(X, Y_average, where='mid', zorder=5,
        #               color='#000000', linewidth=avg_width*1.5)

        mpl_axes.step(X, Y_average, where='mid', zorder=6,
                      color=avg_color, linewidth=avg_width)


        #####################################
        # PLOT LAST X OF EACH METRIC AND AVERAGE
        if st.Plot.aggr_last_x:
            pal = Palette(
                hue = (0, cls.hue),
                sat = (50, 50),
                lig = (85, 93),
                alp = (100,100))
            avg_color = pal[0][0][0][0]
            avg_width = 0.75
            one_color = pal[1][1][1][1]
            one_width = 0.5
            last_Xs = sorted([x[-1] for x in all_X])
            mpl_axes.vlines(last_Xs, ymin=0, ymax=100, colors=one_color,
                            linestyles='solid', linewidth=one_width,
                            zorder=2)

            # PLOT AVG OF LAST X
            last_X_avg = sum(last_Xs)/len(last_Xs)
            mpl_axes.vlines([last_X_avg], ymin=0, ymax=100, colors=avg_color,
                            linestyles='solid', linewidth=avg_width,
                            zorder=3)



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
        cls.setup_grid(mpl_axes, fn_axis='y')

        # insert text box with average usage
        text = (f'Avg: {sum(Y_average)/len(Y_average):.2f}%\n'
                f'{total_pdatas} executions')
        cls.draw_textbox(mpl_axes, text)

        # set labels
        cls.setup_labels(mpl_axes, met_str)

        # title and bg color
        cls.setup_general(mpl_axes, cls.palette.bg, met_str)

        PlotFile.save(fig, metric_code, aggr=True)
        return
