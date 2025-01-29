import matplotlib.pyplot as plt

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
        # enable only if metric is included
        self.enabled = any(m in st.Metrics.enabled
                           for m in self.supported_metrics.keys())
        if not self.enabled:
            return
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

        metric_code = 'CUR'
        met_str = cls.supported_aggr_metrics[metric_code]

        total_pdatas = len(pdata_dicts)
        all_x = [m['fg']['x'] for m in pdata_dicts]
        all_y = [m['fg']['usage_ratio'] for m in pdata_dicts]

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
        for m in range(total_pdatas):
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

        # set plot limits
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
        # if not bg_mode:
        #     text = f'Avg: {sum(self.usage_ratio)/len(self.usage_ratio):.2f}%'
        #     self.draw_textbox(mpl_axes, text)

        # set labels
        cls.setup_labels(mpl_axes, met_str)

        # title and bg color
        cls.setup_general(mpl_axes, cls.palette.bg, met_str)

        PlotFile.save(fig, metric_code, aggr=True)
        return
