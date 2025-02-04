from collections import deque
import matplotlib.pyplot as plt
from itertools import zip_longest

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
            'code' : 'CMR',
            'x' : self.X,
            'thread_miss_ratio' : {t: tms.miss_ratio
                                  for t,tms in self.thread_miss_ratio.items()}
        }

    def dict_to_CMR(self, data):
        try:
            self.X = data['x']
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

        # pad data series
        X_pad = 0.5
        X = [self.X[0]-X_pad] + self.X + [self.X[-1]+X_pad]


        #####################################
        # CREATE PALETTE FOR THREADS
        thread_to_color = {}
        for thr_id in self.thread_miss_ratio.keys():
            thread_to_color[int(thr_id)] = ''
        pal = Palette(
            hue = len(thread_to_color),
            sat = st.Plot.p_sat,
            lig = st.Plot.p_lig,
            alp = st.Plot.p_alp)
        for i,t_id in enumerate(thread_to_color):
            thread_to_color[t_id] = (pal[i][0][0][0],pal[i][1][1][1])


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
            line_color,face_color = thread_to_color[thr]
            mpl_axes.fill_between(X, -1, Y, step='mid', zorder=2,
                                  color=line_color, facecolor=face_color,
                                  linewidth=st.Plot.linewidth)

        # set plot limits
        real_xlim, real_ylim = self.setup_limits(
            mpl_axes, metric_code, xlims=(self.X[0],self.X[-1]), x_pad=X_pad,
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
                    text += f'Avg t{str(thr).ljust(thr_str_len)} CMR: {avg:.2f}%\n'
                text = text[:-1]
            self.draw_textbox(mpl_axes, text)

        # set labels
        self.setup_labels(mpl_axes, met_str, bg_mode=bg_mode)

        # title and bg color
        self.setup_general(mpl_axes, self.palette.bg, met_str, bg_mode=bg_mode)
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
        all_pdatas_X = [m['fg']['x'] for m in pdata_dicts]
        all_pdatas_cmr = [m['fg']['thread_miss_ratio'] for m in pdata_dicts]
        fig,mpl_axes = plt.subplots(figsize=(st.Plot.width, st.Plot.height))

        # obtain the set of all threads ever seen across all pdatas.
        thread_ids = set()
        for pdata_cmr in all_pdatas_cmr:
            for thr in pdata_cmr.keys():
                thread_ids.add(int(thr))


        #####################################
        # CREATE PALETTE FOR THREADS
        thread_to_color = {thr:'' for thr in thread_ids}
        pal = Palette(
            hue = len(thread_to_color),
            # (individual, average)
            sat = (60, 100),
            lig = (70, 20),
            alp = (10, 100))
        for i,t_id in enumerate(thread_to_color):
            thread_to_color[t_id] = (pal[i][0][0][0], pal[i][1][1][1])
        one_width = 0.5
        avg_width = 1.5


        #####################################
        # PLOT INDIVIDUAL METRICS
        # for each pdata, plot all threads, each with their own color
        for pdata_X,pdata_cmr in zip(all_pdatas_X, all_pdatas_cmr):
            for thr,thr_cmr in pdata_cmr.items():
                thr = int(thr)
                thr_color = thread_to_color[thr][0]
                mpl_axes.plot(pdata_X, thr_cmr, zorder=4,
                          color=thr_color, linewidth=one_width)


        #####################################
        # PLOT MOVING AVERAGE OF METRICS (FOR EACH THREAD)
        # find range large enough to fit all plots
        X_min = min(m[0] for m in all_pdatas_X)
        X_max = max(m[-1] for m in all_pdatas_X) - X_min
        full_X = list(range(X_min, X_max+1))

        # collect the cmrs of each thread across all pdatas
        all_threads_cmr = {t:[] for t in thread_ids}
        for pdata_cmr in all_pdatas_cmr:
            for thr,thr_cmr in pdata_cmr.items():
                thr = int(thr)
                # extend this thread's cmr to cover the whole full_X axis
                ext_thr_cmr = [m for _,m in
                               zip_longest(full_X, thr_cmr, fillvalue=None)]
                all_threads_cmr[thr].append(ext_thr_cmr)

        # obtain the average of each thread
        all_threads_cmr_avg = {t:None for t in thread_ids}
        for thr,thr_cmr in all_threads_cmr.items():
            this_thread_all_ith_cmrs = list(zip(*thr_cmr))
            thread_cmr_avg = [0 for _ in full_X]
            for x,ith_cmrs in zip(full_X,this_thread_all_ith_cmrs):
                valid_ys = [y for y in ith_cmrs if y is not None]
                ys_avg = sum(valid_ys) / len(valid_ys)
                thread_cmr_avg[x] = ys_avg
            all_threads_cmr_avg[thr] = thread_cmr_avg

        # plot average of each thread
        for thr,thr_cmr_avg in all_threads_cmr_avg.items():
            thr_color = thread_to_color[thr][1]
            mpl_axes.plot(full_X, thr_cmr_avg, zorder=4,
                          color=thr_color, linewidth=avg_width)


        #####################################
        # PLOT VERT LINE AT LAST X OF EACH METRIC AND AVERAGE
        if st.Plot.aggr_last_x:
            pal = Palette(
                # (individual, avg)
                hue = (0, 0),
                sat = (0, 50),
                lig = (93, 75),
                alp = (100,100))
            one_color = pal[0][0][0][0]
            one_width = 0.5
            avg_color = pal[1][1][1][1]
            avg_width = 1.25
            last_Xs = [x[-1] for x in all_pdatas_X]
            ymax = 120
            ymin = -20
            mpl_axes.vlines(last_Xs, ymin=ymin, ymax=ymax, colors=one_color,
                            linestyles='solid', linewidth=one_width,
                            zorder=2)

            # plot avg across all last-X
            last_X_avg = sum(last_Xs)/len(last_Xs)
            mpl_axes.vlines([last_X_avg], ymin=ymin, ymax=ymax, colors=avg_color,
                            linestyles='solid', linewidth=avg_width,
                            zorder=3)
            last_X_text = f'Avg Execution duration: {last_X_avg:.0f}'


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
            txt = (rf'Avg$^{2}$ thr{thr} CMR: '
                   f'{sum(thr_cmr_avg)/len(thr_cmr_avg):.2f}%')
            text.append(txt)
        text = '\n'.join(text)
        cls.draw_textbox(mpl_axes, text, metric_code)

        # set labels
        cls.setup_labels(mpl_axes, met_str)

        # title and bg color
        cls.setup_general(mpl_axes, cls.palette.bg, met_str)

        PlotFile.save(fig, metric_code, aggr=True)
        return
