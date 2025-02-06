import matplotlib.pyplot as plt
from itertools import zip_longest
from collections import deque

from mapanalyzer.settings import Settings as st
from mapanalyzer.util import MetricStrings, Palette, PlotFile
from mapanalyzer.ui import UI
from .base import BaseModule

class ThreadMissRatio:
    def __init__(self):
        self.hit_count = 0
        self.miss_count = 0
        self.miss_ratio = [0] * st.Map.time_size
        return

    def update_counters(self, hm):
        self.hit_count += hm[0]
        self.miss_count += hm[1]

    def commit(self, current_time):
        if self.hit_count + self.miss_count == 0:
           miss_ratio = 0
        else:
            miss_ratio = 100*self.miss_count / (self.hit_count+self.miss_count)
        self.miss_ratio[current_time] = miss_ratio
        return

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
    name = 'Cache Miss Ratio'
    about = 'Thread-wise Cache Miss Ratio on the last memory accesses.'
    hue = 45
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
        self.enabled = (any(m in st.Metrics.enabled
                           for m in self.supported_metrics.keys()) or
                        st.Metrics.bg in self.supported_metrics)
        if not self.enabled:
            return

        # METRIC INTERNAL VARIABLES
        self.thread_miss_ratio = {}
        self.time_window = deque()
        self.time_window_size = st.Cache.cache_size
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
            'code' : 'CMR',
            'thread_miss_ratio' : {t: tms.miss_ratio
                                  for t,tms in self.thread_miss_ratio.items()}
        }

    def dict_to_CMR(self, data):
        try:
            self.thread_miss_ratio = {}
            for t,tmr_list in data['thread_miss_ratio'].items():
                t = int(t)
                tmr_list = [float(i) for i in tmr_list]
                self.thread_miss_ratio[t] = ThreadMissRatio.from_list(tmr_list)
        except:
            class_name = self.__class__.__name__
            UI.error(f'{class_name}.dict_to_CMR(): Malformed data.')
        return

    def CMR_to_plot(self, mpl_axes, bg_mode=False):
        metric_code = 'CMR'
        met_str = self.supported_metrics[metric_code]


        #####################################
        ## CREATE COLOR PALETTE
        # each thread has its color {thr -> color}
        thread_to_color = {thr:'' for thr in self.thread_miss_ratio.keys()}
        pal = Palette(
            hue = len(thread_to_color), h_off=self.hue,
            sat = st.Plot.p_sat,
            lig = st.Plot.p_lig,
            alp = st.Plot.p_alp)
        for i,thr in enumerate(thread_to_color):
            thread_to_color[thr] = pal[i][0][0][0]
        line_width = st.Plot.p_lw


        #####################################
        ## PLOT METRIC
        # each thread's miss ratio
        for thr,thr_mr in self.thread_miss_ratio.items():
            Y = thr_mr.miss_ratio
            X = range(len(Y))
            line_color = thread_to_color[thr]
            mpl_axes.plot(X, Y, zorder=2, color=line_color,
                          linewidth=line_width)


        ###########################################
        ## PLOT VISUALS
        # set plot limits
        X_pad = 0.5
        X_min = 0
        X_max = len(next(iter(self.thread_miss_ratio.values())).miss_ratio)
        real_xlim, real_ylim = self.setup_limits(
            mpl_axes, metric_code, xlims=(X[0],X[-1]), x_pad=X_pad,
            ylims=(0,100), y_pad='auto')

        # set ticks based on the real limits
        self.setup_ticks(mpl_axes, xlims=real_xlim, ylims=real_ylim,
                         bases=(10, 10), bg_mode=bg_mode)

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
                text = ''
                thr_str_len = len(str(num_thrs))
                for thr,thr_mr_obj in self.thread_miss_ratio.items():
                    thr_mr = thr_mr_obj.miss_ratio
                    avg = sum(thr_mr)/len(thr_mr)
                    text += (f'Avg t{str(thr).ljust(thr_str_len)} '
                             f'{metric_code}: {avg:.2f}%\n')
                text = text[:-1]
            self.draw_textbox(mpl_axes, text, metric_code)

        # set labels
        self.setup_labels(mpl_axes, met_str, bg_mode=bg_mode)

        # title and bg color
        self.setup_general(mpl_axes, pal.bg, met_str, bg_mode=bg_mode)
        return

    @classmethod
    def CMR_to_aggregated_plot(cls, pdata_dicts):
        """Given a list of pdata dictionaries, aggregate their
        values in a meaningful manner"""
        # metric info
        metric_code = pdata_dicts[0]['fg']['code']
        met_str = cls.supported_aggr_metrics[metric_code]

        # extract data from dictionaries and create figure
        total_pdatas = len(pdata_dicts)
        all_pdatas_cmr = [m['fg']['thread_miss_ratio'] for m in pdata_dicts]
        fig,mpl_axes = plt.subplots(figsize=(st.Plot.width, st.Plot.height))

        # obtain the set of all threads ever seen across all pdatas.
        thread_ids = set()
        for pdata_cmr in all_pdatas_cmr:
            for thr in pdata_cmr.keys():
                thread_ids.add(int(thr))


        #####################################
        # CREATE PALETTE FOR THREADS {thr -> (indiv, avg)}
        thread_to_color = {thr:('', '') for thr in thread_ids}
        pal = Palette(
            hue = len(thread_to_color), h_off=cls.hue,
            # (individual, average)
            sat = (60, 100),
            lig = (70, 30),
            alp = (10, 100))
        for i,t_id in enumerate(thread_to_color):
            thread_to_color[t_id] = (pal[i][0][0][0], pal[i][1][1][1])
        ind_line_width = st.Plot.p_aggr_ind_lw
        avg_line_width = st.Plot.p_aggr_avg_lw


        #####################################
        # PLOT INDIVIDUAL METRICS
        # for each pdata, plot all threads, each with their own color.
        # Also collect the "last X" of each pdata
        last_Xs = []
        for pdata_cmr in all_pdatas_cmr:
            # all threads have the same cmr length padded with zeroes
            last_X = len(next(iter(pdata_cmr.values())))-1
            last_Xs.append(last_X)
            X = range(last_Xs[-1]+1)
            for thr,thr_cmr in pdata_cmr.items():
                Y = thr_cmr
                thr = int(thr)
                thr_color = thread_to_color[thr][0]
                mpl_axes.plot(X, Y, zorder=4, color=thr_color,
                              linewidth=ind_line_width)


        #####################################
        # PLOT MOVING AVERAGE OF METRICS (FOR EACH THREAD)
        # find range large enough to fit all plots
        X_min,X_max = 0,max(last_Xs)
        super_X = list(range(X_min, X_max+1))

        # collect the cmrs of each thread across all pdatas
        all_threads_cmr = {t:[] for t in thread_ids}
        for pdata_cmr in all_pdatas_cmr:
            for thr,thr_cmr in pdata_cmr.items():
                thr = int(thr)
                # extend this thread's cmr to cover the whole super_X axis
                ext_thr_cmr = [m for _,m in
                               zip_longest(super_X, thr_cmr, fillvalue=None)]
                all_threads_cmr[thr].append(ext_thr_cmr)

        # obtain the average of each thread
        all_threads_cmr_avg = {t:None for t in thread_ids}
        for thr,thr_cmr in all_threads_cmr.items():
            this_thread_all_ith_cmrs = list(zip(*thr_cmr))
            thread_cmr_avg = [0 for _ in super_X]
            for x,ith_cmrs in zip(super_X,this_thread_all_ith_cmrs):
                valid_ys = [y for y in ith_cmrs if y is not None]
                ys_avg = sum(valid_ys) / len(valid_ys)
                thread_cmr_avg[x] = ys_avg
            all_threads_cmr_avg[thr] = thread_cmr_avg

        # plot average of each thread
        for thr,thr_cmr_avg in all_threads_cmr_avg.items():
            thr_color = thread_to_color[thr][1]
            mpl_axes.plot(super_X, thr_cmr_avg, zorder=4,
                          color=thr_color, linewidth=avg_line_width)


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

        # insert text box with average per thread
        text = [f'Executions: {total_pdatas}']
        if st.Plot.aggr_last_x:
            text.append(last_X_text)
        for thr,thr_cmr_avg in all_threads_cmr_avg.items():
            txt = (rf'Avg2 thr{thr} CMR: '
                   f'{sum(thr_cmr_avg)/len(thr_cmr_avg):.2f}%')
            text.append(txt)
        cls.draw_textbox(mpl_axes, text, metric_code)

        # set labels
        cls.setup_labels(mpl_axes, met_str)

        # title and bg color
        cls.setup_general(mpl_axes, pal.bg, met_str)

        PlotFile.save(fig, metric_code, aggr=True)
        return
