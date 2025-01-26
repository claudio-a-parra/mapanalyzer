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

    metrics = {
        'CUR' : MetricStrings(
            title  = 'CUR',
            subtit = 'higher is better',
            numb   = '01',
            xlab   = 'Time [access instr.]',
            ylab   = 'Cache Usage Rate [%]',
        )
    }
    aggr_metrics = {
        'CUR' : MetricStrings(
            title  = 'Aggregated CUR',
            subtit = 'higher is better',
            numb   = '01',
            xlab   = 'Time [access instr.]',
            ylab   = 'Cache Usage Rate [%]',
        )
    }


    def __init__(self):
        # enable only if metric is included
        self.enabled = any(m in st.Metrics.enabled for m in self.metrics.keys())
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
        class_name = self.__class__.__name__
        my_code = 'MAP'
        curr_fn = f'dict_to_{my_code}'
        data_code = data['code']
        if my_code != data_code:
            UI.error(f'{class_name}.{curr_fn}(): {self.name} module '
                     f'received some unknown "{data_code}" metric data rather '
                     f'than its known "{my_code}" metric data.')

        self.X = data['x']
        self.usage_ratio = data['usage_ratio']
        return

    def CUR_to_plot(self, mpl_axes, bg_mode=False):
        if not self.enabled:
            return

        code = 'CUR'
        met_str = self.metrics[code]

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
            mpl_axes, code=code, xlims=(self.X[0],self.X[-1]), xpad=X_pad,
            ylims=(0,100), ypad='auto'
        )

        # set ticks based on the real limits
        self.setup_ticks(
            mpl_axes, realxlim=real_xlim, realylim=real_ylim,
            tick_bases=(10, 10),
            bg_mode=bg_mode
        )

        # set grid
        self.setup_grid(mpl_axes, fn_axis='y')

        # insert text box with average usage
        text = f'Avg: {sum(self.usage_ratio)/len(self.usage_ratio):.2f}%'
        self.draw_textbox(mpl_axes, text)

        # set labels
        self.setup_labels(mpl_axes, met_str, bg_mode=bg_mode)

        # title and bg color
        self.setup_general(mpl_axes, met_str, bg_mode=bg_mode)
        return

    @classmethod
    def CUR_to_aggregated_plot(cls, metrics_list):
        """Given a list of 'metric' dictionaries, aggregate their
        values in a meaningful manner"""

        code = 'CUR'
        met_str = cls.aggr_metrics

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


        PlotFile.save(fig, met_code=code, met_str=met_str, aggr=True)
        save_aggr(fig, cls.aggr_met_str)
        return
