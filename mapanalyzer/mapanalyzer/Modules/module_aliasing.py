from collections import deque
import matplotlib.pyplot as plt
from itertools import zip_longest
import matplotlib.colors as mcolors # to create shades of colors from list

from mapanalyzer.settings import Settings as st
from mapanalyzer.util import MetricStrings, Palette, PlotFile
from mapanalyzer.ui import UI
from .base import BaseModule

class Aliasing(BaseModule):
    hue = 220
    supported_metrics = {
        'AD' : MetricStrings(
            about  = ('Proportion in which each set fetches blocks during '
                      'execution.') ,
            title  = 'Aliasing Density',
            subtit = 'transparent is better',
            number = '05',
            xlab   = 'Time [access instr.]',
            ylab   = 'Cache Sets',
        )
    }
    supported_aggr_metrics = {
        'AD' : MetricStrings(
            about  = ('Average proportion in which each set fetches blocks '
                      'during execution.') ,
            title  = 'Cache Set Load Imbalance',
            subtit = 'transparent is better',
            number = '05',
            xlab   = 'Fetch Number',
            ylab   = 'Cache Sets',
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
        # window of last fetches
        self.time_window = deque()
        self.time_window_max_size = st.Cache.asso * st.Cache.num_sets
        self.sets_counters = [0] * st.Cache.num_sets
        self.sets_aliasing = [[0] * st.Map.time_size
                             for _ in range(st.Cache.num_sets)]
        return

    def probe(self, set_index, access_time):
        """Update the Set counters"""
        if not self.enabled:
            return

        # append access to queue
        self.time_window.append((set_index,access_time))
        self.sets_counters[set_index] += 1

        # trim queue to fit max_size
        while len(self.time_window) > self.time_window_max_size:
            old_set_idx,_ = self.time_window.popleft()
            self.sets_counters[old_set_idx] -= 1
        return

    def commit(self, time):
        if not self.enabled:
            return

        # if the difference between the "most busy" and the "least busy" set
        # is just one fetch, this is not proof of imbalance, we may be doing
        # a perfect round robin. So, only account for aliasing when the
        # difference is at least 2.
        if max(self.sets_counters) - min(self.sets_counters) < 2:
            return

        curr_time = self.time_window[-1][1]
        tot_fetch = sum(self.sets_counters)
        for s in range(st.Cache.num_sets):
            self.sets_aliasing[s][curr_time] = self.sets_counters[s] / tot_fetch
        return

    def finalize(self):
        # no post-simulation computation to be done
        return

    def AD_to_dict(self):
        return {
            'code' : 'AD',
            'set_aliasing' : self.sets_aliasing
        }

    def dict_to_AD(self, data):
        try:
            self.sets_aliasing = data['set_aliasing']
        except:
            class_name = self.__class__.__name__
            UI.error(f'{class_name}.dict_to_AD(): Malformed data.')

        return

    def AD_to_plot(self, mpl_axes, bg_mode=False):
        metric_code = 'AD'
        met_str = self.supported_metrics[metric_code]

        # create data series
        X = range(st.Map.time_size)
        Y = self.sets_aliasing


        #####################################
        ## CREATE COLOR PALETTE
        pal = Palette(hue=(self.hue,),
                      sat=st.Plot.p_sat,
                      lig=st.Plot.p_lig,
                      alp=(0,100))
        line_width = st.Plot.p_lw
        shade_cmap = mcolors.LinearSegmentedColormap.from_list(
            'transparency_cmap', (pal[0][0][0][0],pal[0][0][0][1]))


        #####################################
        ## PLOT METRIC
        # for each set, plot a "band" with its colored shades
        X_pad,Y_pad = 0.5,0.5
        for s in range(st.Cache.num_sets):
            # define the extension of this set's band:
            # - all horizontal (time) span.
            # - just one unit in the vertical (sets) span.
            set_ext = (0-X_pad, st.Map.time_size-1+X_pad,
                       s-Y_pad, s+Y_pad)
            set_ali = [self.sets_aliasing[s]]
            mpl_axes.imshow(set_ali, cmap=shade_cmap, origin='lower',
                            interpolation='none', aspect='auto',
                            extent=set_ext, zorder=1, vmin=0, vmax=1)


        ###########################################
        ## OBTAIN AVERAGE LOAD IMBALANCE
        imbal = [0] * st.Map.time_size
        i = 0
        for ith_dist in zip(*self.sets_aliasing):
            if sum(ith_dist) > 0.001: # anything above 0 should do it
                imbal[i] = max(ith_dist) - min(ith_dist)
                i += 1
        imbal = imbal[:i]
        if i > 0:
            imbal_avg = 100*sum(imbal)/len(imbal)
        else:
            imbal_avg = 0
        imbal_txt = f'Average load imbalance: {imbal_avg:.2f}%'


        ###########################################
        ## PLOT VISUALS
        # set plot limits
        xlims = (0, st.Map.time_size-1)
        ylims = (0, st.Cache.num_sets-1)
        real_xlim, real_ylim = self.setup_limits(
            mpl_axes, metric_code, xlims=xlims, x_pad=X_pad,
            ylims=ylims, y_pad=Y_pad, invert_y=True
        )

        # set ticks based on the real limits
        self.setup_ticks(
            mpl_axes, xlims=real_xlim, ylims=real_ylim,
            bases=(10, 2), # y-axis powers of two
            bg_mode=bg_mode
        )

        # set grid of bytes and blocks (not mpl grids)
        if st.Cache.num_sets < st.Plot.grid_max_sets and not bg_mode:
            sets_separators = [s+0.5 for s in range(st.Cache.num_sets-1)]
            self.setup_manual_grid(mpl_axes, axis='y', fn_axis='y',
                                   hlines=sets_separators,
                                   xlims=(xlims[0]-X_pad,xlims[1]+X_pad),
                                   grid_color='#40BF40CC', zorder=10)
        else:
            self.setup_grid(mpl_axes, bg_mode=bg_mode)

        # insert text box with average load imbalance
        if not bg_mode:
            self.draw_textbox(mpl_axes, imbal_txt, metric_code)

        # set labels
        self.setup_labels(mpl_axes, met_str, bg_mode=bg_mode)

        # title and bg color
        self.setup_general(mpl_axes, pal.bg, met_str, bg_mode=bg_mode)
        return

    @classmethod
    def AD_to_aggregated_plot(cls, pdata_dicts):
        """Given a list of pdata dictionaries, aggregate their
        values in a meaningful manner"""
        # metric info
        metric_code = pdata_dicts[0]['fg']['code']
        met_str = cls.supported_aggr_metrics[metric_code]

        # extract data from dictionaries and create figure
        # three-level list: (pdata, set, time)
        all_pdatas = [pd['fg']['set_aliasing'] for pd in pdata_dicts]
        num_pdatas = len(all_pdatas)
        fig,mpl_axes = plt.subplots(figsize=(st.Plot.width, st.Plot.height))

        # make sure all pdatas have the same number of sets
        all_num_sets = [0] * num_pdatas
        for i, s_ali in enumerate(all_pdatas):
            all_num_sets[i] = len(s_ali)
        all_num_sets = set(all_num_sets)
        if len(all_num_sets) > 1:
            UI.error(f'Aliasing.AD_to_aggregated_plot(): Attempting to '
                     'aggregate aliasing pdata files with different number '
                     f'of sets ({str(all_num_sets)} number of sets).')
        num_sets = all_num_sets.pop()


        #####################################
        # CREATE COLOR PALETTE
        pal = Palette(hue=(cls.hue,),
                      sat = st.Plot.p_sat,
                      lig = st.Plot.p_lig,
                      alp = (0, 100))
        line_width = st.Plot.p_lw
        shade_cmap = mcolors.LinearSegmentedColormap.from_list(
            'transparency_cmap', (pal[0][0][0][0],pal[0][0][0][1]))


        #####################################
        # CREATE DATA SERIES

        # enter each pdata, and sort the aliasings such that at time t,
        # set_0 becomes the idlest, and set_S-1 the busiest.
        # save them in a compressed list all_short_pdatas
        all_compressed_pdatas = [[[] for _ in sets]
                                 for sets in all_pdatas]
        tth_alis = [0] * num_sets
        for p,pdat in enumerate(all_pdatas):
            for t in range(len(pdat[0])):
                # collect the t-th alias of each set <s>, ...
                for s in range(num_sets):
                    tth_alis[s] = pdat[s][t]

                # if there is no fetches at this time, skip it.
                if sum(tth_alis) < 0.00001: # comparing float to "zero"
                    continue

                # Otherwise, sort alias degrees (idle first, bussy last), and
                # write their values to the compressed list
                tth_alis.sort()
                for s in range(num_sets):
                    all_compressed_pdatas[p][s].append(tth_alis[s])

        # find the last time across all compressed pdatas
        last_times = [len(pdat[0])-1 for pdat in all_compressed_pdatas]
        time_size = max(last_times) + 1


        # Create list for averages: <num_sets> tier-sets and <time_size> time
        # slots.
        avg_tier_aliasing = [[0] * time_size for _ in range(num_sets)]

        # traverse all_pdatas, taking the s-th set across all pdatas at the
        # time, remember that sets now represent an idle-to-busy ranking.
        for s,sth_sets in enumerate(zip(*all_compressed_pdatas)):
            # In the <s>-tier level of business, get the average for each point
            # of time <t>
            for t,tth_alis in enumerate(zip_longest(*sth_sets, fillvalue=None)):
                valid_tth_alis = [a for a in tth_alis if a is not None]
                avg = sum(valid_tth_alis)/len(valid_tth_alis)
                avg_tier_aliasing[s][t] = avg


        #####################################
        # PLOT SET-TIERS
        # for each set-tier, plot a "band" with its colored shades
        X_pad,Y_pad = 0.5,0.5
        for s in range(num_sets):
            # define the extension of this set's band:
            # - all horizontal (time) span.
            # - just one unit in the vertical (set-tiers) span.
            set_tier_ext = (0-X_pad, time_size-1+X_pad,
                            s-Y_pad, s+Y_pad)
            set_tier_ali = [avg_tier_aliasing[s]]
            mpl_axes.imshow(set_tier_ali, cmap=shade_cmap, origin='lower',
                            interpolation='none', aspect='auto',
                            extent=set_tier_ext, zorder=1, vmin=0, vmax=1)


        ###########################################
        ## OBTAIN AVERAGE LOAD IMBALANCE
        imbal = [0] * time_size
        i = 0
        for ith_alis in zip(*avg_tier_aliasing):
            if sum(ith_alis) > 0.00000001: # anything above 0 should do it
                imbal[i] = ith_alis[-1] - ith_alis[0]
                i += 1
        imbal = imbal[:i]
        if i > 0:
            imbal_avg = 100*sum(imbal)/len(imbal)
        else:
            imbal_avg = 0
        imbal_text = f'Avg load imbalance: {imbal_avg:.2f}%'


        #####################################
        # PLOT VERT LINE AT LAST X OF EACH METRIC AND AVERAGE
        xlims = (0,time_size-1)
        ylims = (0,num_sets-1)
        if st.Plot.aggr_last_x:
            last_X_text = cls.draw_last_Xs(
                mpl_axes, last_times, ylims=(ylims[0]-Y_pad,ylims[1]+Y_pad),
                pre_text='Avg number of fetches')


        #####################################
        # SETUP PLOT VISUALS
        # set plot limits
        real_xlim, real_ylim = cls.setup_limits(
            mpl_axes, metric_code, xlims=xlims, x_pad=X_pad, ylims=ylims,
            y_pad=Y_pad, invert_y=True)

        # set ticks based on the real limits
        cls.setup_ticks(mpl_axes, xlims=real_xlim, ylims=real_ylim,
                        bases=(10, 2))

        # overwrite Y ticks with "idle" and "busy"
        text_ticks = ['' for _ in range(num_sets)]
        text_ticks[0] = 'idlest'
        text_ticks[-1] = 'busiest'
        mpl_axes.set_yticklabels(text_ticks)
        mpl_axes.tick_params(axis='y', rotation=90)

        # set grid
        if num_sets < st.Plot.grid_max_sets:
            sets_separators = [s+0.5 for s in range(num_sets-1)]
            cls.setup_manual_grid(mpl_axes, axis='y', fn_axis='y',
                                  hlines=sets_separators,
                                  xlims=(xlims[0]-X_pad,xlims[1]+X_pad),
                                  grid_color='#40BF40CC', zorder=2)
        else:
            axis = 'y' if st.Plot.aggr_last_x else 'xy'
            cls.setup_grid(mpl_axes, axis=axis, fn_axis='y')

        # insert text box with average imbalance
        text = [f'Executions: {num_pdatas}']
        if st.Plot.aggr_last_x:
            text.append(last_X_text)
        text.append(imbal_text)
        cls.draw_textbox(mpl_axes, text, metric_code)

        # set labels
        cls.setup_labels(mpl_axes, met_str)

        # title and bg color
        cls.setup_general(mpl_axes, pal.bg, met_str)

        PlotFile.save(fig, metric_code, aggr=True)
        return
