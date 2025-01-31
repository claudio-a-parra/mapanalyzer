import sys
from collections import deque
import matplotlib.pyplot as plt

# to serialize and de-serialize ThreadMissRatio
import json

from mapanalyzer.settings import Settings as st
from mapanalyzer.util import MetricStrings, Palette, PlotFile
from mapanalyzer.ui import UI

from .base import BaseModule

class ThreadMissRatio:
    def __init__(self):
        self.hit_count = 0
        self.miss_count = 0
        self.miss_ratio = [-1] * st.Map.time_size
        return

    def update_counters(self, hm):
        self.hit_count += hm[0]
        self.miss_count += hm[1]

    def commit(self, current_time):
        miss_ratio = 100*self.miss_count / (self.hit_count+self.miss_count)
        self.miss_ratio[current_time] = miss_ratio
        return

    def to_dict(self):
        return {'miss_ratio': self.miss_ratio}

    @classmethod
    def from_list(cls, mr_list):
        new_tmr = cls()
        new_tmr.hit_count = 0
        new_tmr.miss_count = 0
        new_tmr.miss_ratio = mr_list
        return new_tmr

    def __str__(self):
        hr_string = ''
        for i,r in enumerate(self.miss_ratio):
            hr_string += f'  {i:>2}: {float(r):>6.2f}\n'
        ret_str = (f'hits       : {self.hit_count}\n'
                   f'misses     : {self.miss_count}\n'
                   'miss_ratio :\n'
                   f'{hr_string}')
        return ret_str

class MissRatio(BaseModule):
    # Module info
    name = 'Cache Miss Ratio'
    about = 'Thread-wise Cache Miss Ratio on the last memory accesses.'
    hue = 0
    palette = Palette.default(hue)

    supported_metrics = {
        'CMR' : MetricStrings(
            about  = ('Thread-wise Cache Miss Ratio on the last memory '
                      'accesses.'),
            title  = 'CMR',
            subtit = 'lower is better',
            number = '02',
            xlab   = 'Time [access instr.]',
            ylab   = 'Cache Miss Ratio [%]',
        )
    }
    supported_aggr_metrics = {
        'CMR' : MetricStrings(
            about  = ('Average cache miss ratio across multiple executions.'),
            title  = 'Aggregated CMR',
            subtit = 'lower is better',
            number = '02',
            xlab   = 'Time [access instr.]',
            ylab   = 'Cache Miss Ratio [%]',
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
        self.thread_miss_ratio = {}
        self.X = [i for i in range(st.Map.time_size)]
        self.time_window = deque()
        self.time_window_size = st.Cache.num_sets*st.Cache.asso
        return

    def probe(self, access, hit_miss):
        """
        hit_miss is a tuple with the hit and miss counters diffs.
        Cache Hit : hit_miss == (1,0)
        Cache Miss: hit_miss == (0,1)
        """
        if not self.enabled:
            return

        # queue event to time_window, and increment the thread's counters
        self.time_window.append((access,hit_miss))
        if access.thread not in self.thread_miss_ratio:
            self.thread_miss_ratio[access.thread] = ThreadMissRatio()
        self.thread_miss_ratio[access.thread].update_counters(hit_miss)

        # dequeue event from time_window, and decrement the thread's counters
        while len(self.time_window) > self.time_window_size:
            old_acc,(old_h,old_m) = self.time_window.popleft()
            self.thread_miss_ratio[old_acc.thread].update_counters(
                (-old_h,-old_m))
        return

    def commit(self, time):
        if not self.enabled:
            return
        # this metric's probe is called on EVERY instruction (as accesses must
        # either be miss or hit), therefore, counters don't miss a single commit
        for thr_mr in self.thread_miss_ratio.values():
            thr_mr.commit(time)

    def finalize(self):
        # no post-simulation computation to be done
        return

    def CMR_to_dict(self):
        return {
            'code': 'CMR',
            'x': self.X,
            'thread_miss_ratio': {t: tms.miss_ratio
                                  for t,tms in self.thread_miss_ratio.items()}
        }

    def dict_to_CMR(self, data):
        # check for malformed (no keys) dict.
        all_keys = ['x', 'thread_miss_ratio']
        if not all(k in data for k in all_keys):
            UI.error(f'While importing CMR. Not all necessary keys are '
                     f'present ({",".join(all_keys)}).')
        self.X = data['x']
        self.thread_miss_ratio = {}
        for t,tmr_list in data['thread_miss_ratio'].items():
            t = int(t)
            tmr_list = [float(i) for i in tmr_list]
            self.thread_miss_ratio[t] = ThreadMissRatio.from_list(tmr_list)
        return

    def CMR_to_plot(self, mpl_axes, bg_mode=False):
        metric_code='CMR'
        met_str = self.supported_metrics[metric_code]

        # pad data series
        X_pad = 0.5
        X = [self.X[0]-X_pad] + self.X + [self.X[-1]+X_pad]

        # create palette for the number of threads found
        self.palette = Palette(
            hue = len(self.thread_miss_ratio),
            sat = st.Plot.p_sat,
            lig = st.Plot.p_lig,
            alp = st.Plot.p_alp)

        # draw miss ratio for each thread
        for thr,thr_mr in self.thread_miss_ratio.items():
            Y = [thr_mr.miss_ratio[0]] + thr_mr.miss_ratio + \
                [thr_mr.miss_ratio[-1]]
            line_color = self.palette[thr][0][0][0]
            face_color = self.palette[thr][1][1][1]
            mpl_axes.fill_between(X, -1, Y, step='mid', zorder=2,
                                  color=line_color, facecolor=face_color,
                                  linewidth=st.Plot.linewidth)

        # set plot limits
        real_xlim, real_ylim = self.setup_limits(
            mpl_axes, metric_code, xlims=(self.X[0],self.X[-1]), x_pad=X_pad,
            ylims=(0,100), y_pad='auto')

        # set ticks based on the real limits
        self.setup_ticks(
            mpl_axes, xlims=real_xlim, ylims=real_ylim,
            bases=(10, 10),
            bg_mode=bg_mode)

        # set grid
        self.setup_grid(mpl_axes, fn_axis='y')

        # insert text box with average usage
        if not bg_mode:
            num_thrs = len(list(self.thread_miss_ratio.keys()))
            if num_thrs == 1:
                thr = list(self.thread_miss_ratio.keys())[0]
                thr_mr = self.thread_miss_ratio[thr].miss_ratio
                avg = sum(thr_mr)/len(thr_mr)
                text = f'Avg: {avg:.2f}%'
            else:
                text = 'Avg:\n'
                thr_str_len = len(str(num_thrs))
                for thr,thr_mr_obj in self.thread_miss_ratio.items():
                    thr_mr = thr_mr_obj.miss_ratio
                    avg = sum(thr_mr)/len(thr_mr)
                    text += f't{str(thr).ljust(thr_str_len)}: {avg:.2f}\n'
                text = text[:-1]
            self.draw_textbox(mpl_axes, text)

        # set labels
        self.setup_labels(mpl_axes, met_str, bg_mode=bg_mode)

        # title and bg color
        self.setup_general(mpl_axes, self.palette.bg, met_str, bg_mode=bg_mode)
        return
