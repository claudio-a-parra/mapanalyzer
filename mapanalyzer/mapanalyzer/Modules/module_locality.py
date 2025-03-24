from collections import deque
import matplotlib.pyplot as plt
from itertools import zip_longest

from ..settings import Settings as st
from ..util import MetricStrings, Palette, PlotFile
from ..ui import UI
from .base import BaseModule

class Locality(BaseModule):
    hue = 325
    supported_metrics = {
        'SLD' : MetricStrings(
            about  = ('Spatial Locality Degree.'),
            title  = 'SLD',
            subtit = 'higher is better',
            number = '01',
            xlab   = 'Time [access instr.]',
            ylab   = 'Spatial Locality Degree',
        ),
        'TLD' : MetricStrings(
            about  = ('Temporal Locality Degree.'),
            title  = 'TLD',
            subtit = 'higher is better',
            number = '01',
            xlab   = 'Temporal Locality Degree',
            ylab   = 'Space [blocks]',
        )
    }
    supported_aggr_metrics = {
        'SLD' : MetricStrings(
            about  = ('Average Spatial Locality Degree.'),
            title  = 'Aggregated SLD',
            subtit = 'higher is better',
            number = '01',
            xlab   = 'Time [access instr.]',
            ylab   = 'Spatial Locality Degree',
        ),
        'TLD' : MetricStrings(
            about  = ('Average Temporal Locality Degree.'),
            title  = 'Aggregated TLD',
            subtit = 'higher is better',
            number = '01',
            xlab   = 'Temporal Locality Degree',
            ylab   = 'Space [blocks]',
        )
    }

    def __init__(self):
        # enable metric if user requested it or if used as background
        self.enabled = (any(m in st.Metrics.enabled
                           for m in self.supported_metrics.keys()) or
                        st.Metrics.bg in self.supported_metrics)
        if not self.enabled:
            return

        #####################################
        # SPATIAL LOCALITY ACROSS TIME
        # time window chronological access: keeps the temporal order of
        # accesses.
        # (access offset, size)
        self.tw_chro_acc = deque()
        # Time Window byte counter: Each entry has two elements: the byte
        # offset, and the number of accesses to such byte:
        # {byte offset -> number of accesses}
        #
        # The Time Window table has up to <cache_size> entries. When that
        # size is reached, counters are decremented (or removed) based on
        # the rear-popped element from tw_chro_acc.
        self.tw_byte_count = {}
        self.tw_byte_count_max = st.Cache.cache_size
        # Spatial Locality vector: Contains the final SLD metric.
        self.Ls = [0] * st.Map.time_size
        # the time at which the first (full) time window is completed. That is,
        # the moment at which the Time Window Byte Counter table reaches its
        # maximum size and has to be trimmed.
        self.first_full_time_win = 0;

        #####################################
        ## TEMPORAL LOCALITY ACROSS SPACE
        self.space_by_blocks = {} #block->list of block access times
        self.Lt = [0] * st.Map.num_blocks
        return

    def probe(self, time, thread, event, size, addr):
        if not self.enabled:
            return
        ## SPACIAL LOCALITY ACROSS TIME
        off = addr - st.Map.start_addr

        # Add access to:
        # - the chronological queue
        self.tw_chro_acc.append((off,size))
        # - the table of bytes
        for b in range(off,off+size):
            if b not in self.tw_byte_count:
                self.tw_byte_count[b] = 1
            else:
                self.tw_byte_count[b] += 1

        # keep table of accesses under max by de-queuing from the
        # chronological queue.
        while len(self.tw_byte_count) > self.tw_byte_count_max:
            if not self.first_full_time_win:
                self.first_full_time_win = time
            old_off,old_size = self.tw_chro_acc.popleft()
            # decrement/remove bytes from table of bytes
            for b in range(old_off,old_off+old_size):
                if self.tw_byte_count[b] == 1:
                    del self.tw_byte_count[b]
                else:
                    self.tw_byte_count[b] -= 1

        ## TEMPORAL LOCALITY ACROSS SPACE
        # get the block to which the address belongs
        blkid_start = addr >> st.Cache.bits_off
        if blkid_start not in self.space_by_blocks:
            self.space_by_blocks[blkid_start] = []
        self.space_by_blocks[blkid_start].append(time)

        # in case the reading fell between blocks, the last bytes will be
        # in the next block.
        blkid_end = (addr + size -1) >> st.Cache.bits_off
        if blkid_end == blkid_start:
            return
        if blkid_end not in self.space_by_blocks:
            self.space_by_blocks[blkid_end] = []
        self.space_by_blocks[blkid_end].append(time)
        return

    def commit(self, time):
        """produce the a neighborhood from tw_byte_count's keys and add it
        to Ls"""
        if not self.enabled:
            return

        # expensive operation...
        neig = sorted(list(self.tw_byte_count))

        # if only one access, there are no deltas to get, then, Ls[time] = 0
        if len(neig) < 2:
            self.Ls[time] = 0
            return

        # compute differences among neighbors and store them into dist.
        dist = neig # just to reuse memory
        b = st.Cache.line_size
        for j,ni,nj in zip(range(len(dist)-1), neig[:-1], neig[1:]):
            dist[j] = (b - min(b, nj-ni)) / (b - 1)
        del dist[-1]

        # get average distance in the neighborhood, and write it in Ls.
        avg_dist = sum(dist) / len(dist)
        self.Ls[time] = avg_dist
        return

    def finalize(self):
        if not self.enabled:
            return

        self.__all_space_windows_to_lt()
        return

    def __all_space_windows_to_lt(self):
        """for all space windows, compute differences and compose the
        entirety of Lt"""
        # obtain the list of all ACTUALLY used blocks
        used_blocks = list(self.space_by_blocks.keys())
        used_blocks.sort()

        # for each window, get its neighborhood, compute distances and store
        # the average distance in Lt.
        C = st.Cache.cache_size
        B = st.Cache.line_size
        for ubi in used_blocks: #ubi: used-block ID
            neig = self.space_by_blocks[ubi]
            dist = neig # just to reuse memory
            # if there is only one access, there is no locality to compute.
            if len(neig) < 2:
                self.Lt[ubi] = 0
                continue

            for j,ni,nj in zip(range(len(dist)-1), neig[:-1], neig[1:]):
                #dist[j] = (C - min(C, nj-ni)) / (C-1)
                dist[j] = (C - B*min(nj-ni,C//B)) / (C-B)
            del dist[-1]

            # get average difference in the neighborhood, and write it in Lt.
            avg_dist = sum(dist) / len(dist)
            self.Lt[ubi] = avg_dist
        return

    def SLD_to_dict(self):
        return {
            'code' : 'SLD',
            'first_full_time_win' : self.first_full_time_win,
            'Ls' : self.Ls
        }

    def TLD_to_dict(self):
        return {
            'code' : 'TLD',
            'Lt' : self.Lt
        }

    def dict_to_SLD(self, data):
        try:
            self.Ls = data['Ls']
            self.first_full_time_win = data['first_full_time_win']
        except:
            class_name = self.__class__.__name__
            UI.error(f'{class_name}.dict_to_SLD(): Malformed data.')
        return

    def dict_to_TLD(self, data):
        try:
            self.Lt = data['Lt']
        except:
            class_name = self.__class__.__name__
            UI.error(f'{class_name}.dict_to_TLD(): Malformed data.')
        return

    def SLD_to_plot(self, mpl_axes, bg_mode=False):
        metric_code = 'SLD'
        met_str = self.supported_metrics[metric_code]

        # create data series
        X = range(len(self.Ls))
        Y = self.Ls


        #####################################
        ## CREATE COLOR PALETTE
        pal = Palette(hue=[self.hue, self.hue+90],
                      # (line, _)
                      sat=st.Plot.p_sat,
                      lig=st.Plot.p_lig,
                      alp=st.Plot.p_alp)
        line_color = pal[0][0][0][0]
        first_win_color = pal[1][0][0][0]
        line_width = st.Plot.p_lw


        #####################################
        ## PLOT METRIC
        mpl_axes.step(X, Y, where='mid', zorder=2, color=line_color,
                      linewidth=line_width)


        #####################################
        ## PLOT FIRST FULL TIME WINDOW
        mpl_axes.axvline(x=self.first_full_time_win, zorder=1,
                         color=first_win_color, linestyle='--',
                         linewidth=1.5*line_width)


        ###########################################
        ## PLOT VISUALS
        # set plot limits
        X_pad,Y_pad = 0.5,'auto'
        xlims = (X[0],X[-1])
        ylims = (0,1.0)
        real_xlim, real_ylim = self.setup_limits(
            mpl_axes, metric_code, xlims=xlims, x_pad=X_pad,
            ylims=ylims, y_pad=Y_pad)

        # set ticks based on the real limits
        self.setup_ticks(mpl_axes, xlims=real_xlim, ylims=real_ylim,
                         bases=(10, 10), bg_mode=bg_mode)

        # set grid
        self.setup_grid(mpl_axes, fn_axis='y', bg_mode=bg_mode)

        # insert text box with average usage
        if not bg_mode:
            text_list = []
            text_list.append(f'Avg {metric_code}: {sum(Y)/len(Y):.2f}')
            text_list.append(f'First time window: {self.first_full_time_win}')
            text = '\n'.join(text_list)
            self.draw_textbox(mpl_axes, text, metric_code)

        # set labels
        self.setup_labels(mpl_axes, met_str, bg_mode=bg_mode)

        # title and bg color
        self.setup_general(mpl_axes, pal.bg, met_str, bg_mode=bg_mode)
        return

    def TLD_to_plot(self, mpl_axes, bg_mode=False):
        metric_code = 'TLD'
        met_str = self.supported_metrics[metric_code]

        # create data series
        # shift Y so that the step function moves in between values.
        # (hack for rotated step function, as matplotlib does not nicely
        # supports it)
        Y_shifted = ([y-0.5 for y in range(st.Map.num_blocks)] +
                     [st.Map.num_blocks-0.5])
        X = self.Lt + [self.Lt[-1]]


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
        mpl_axes.step(X, Y_shifted, -1, where='pre', zorder=2,
                      color=line_color, linewidth=line_width)


        ###########################################
        ## PLOT VISUALS
        # set plot limits
        X_pad,Y_pad = 'auto',0.5
        xlims = (0,1.0)
        ylims = (0,st.Map.num_blocks-1)
        real_xlim, real_ylim = self.setup_limits(
            mpl_axes, metric_code, xlims=xlims, x_pad=X_pad,
            ylims=ylims, y_pad=Y_pad, invert_y=True)

        # set ticks based on the real limits
        self.setup_ticks(mpl_axes, xlims=real_xlim, ylims=real_ylim,
                         bases=(10, 10), bg_mode=bg_mode)

        # set grid
        if len(Y_shifted) <= st.Plot.grid_max_blocks:
            self.setup_grid(mpl_axes, fn_axis='x', axis='x')
            self.setup_manual_grid(mpl_axes, xlims=xlims, hlines=Y_shifted,
                                   axis='y')
        else:
            self.setup_grid(mpl_axes, fn_axis='x', axis='xy')

        # insert text box with average usage
        if not bg_mode:
            text = f'Avg {metric_code}: {sum(X)/len(X):.2f}'
            self.draw_textbox(mpl_axes, text, metric_code)

        # set labels
        self.setup_labels(mpl_axes, met_str, bg_mode=bg_mode)

        # title and bg color
        self.setup_general(mpl_axes, pal.bg, met_str, bg_mode=bg_mode)
        return

    @classmethod
    def SLD_to_aggregated_plot(cls, pdata_dicts):
        """Given a list of pdata dictionaries, aggregate their
        values in a meaningful manner"""
        # metric info
        metric_code = pdata_dicts[0]['fg']['code']
        met_str = cls.supported_aggr_metrics[metric_code]

        # extract data from dictionaries and create figure
        total_pdatas = len(pdata_dicts)
        all_Y = [m['fg']['Ls'] for m in pdata_dicts]

        # define the figure size for this particular plot
        if metric_code in st.Plot.plots_sizes:
            figsize = st.Plot.plots_sizes[metric_code]
        else:
            figsize = (st.Plot.width, st.Plot.height)
        fig,mpl_axes = plt.subplots(figsize=figsize)


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
            last_X_text = cls.draw_last_Xs(mpl_axes, last_Xs, (-0.5,1.5))


        #####################################
        # SETUP PLOT VISUALS
        # set plot limits
        X_pad,Y_pad = 0.5,'auto'
        xlims = (X_min,X_max)
        ylims = (0,1.0)
        real_xlim, real_ylim = cls.setup_limits(
            mpl_axes, metric_code, xlims=xlims, x_pad=X_pad,
            ylims=ylims, y_pad=Y_pad
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

    @classmethod
    def TLD_to_aggregated_plot(cls, pdata_dicts):
        """Given a list of pdata dictionaries, aggregate their
        values in a meaningful manner"""
        # metric info
        metric_code = pdata_dicts[0]['fg']['code']
        met_str = cls.supported_aggr_metrics[metric_code]

        # extract data from dictionaries and create figure
        total_pdatas = len(pdata_dicts)
        all_X = [m['fg']['Lt'] for m in pdata_dicts]

        # define the figure size for this particular plot
        if metric_code in st.Plot.plots_sizes:
            figsize = st.Plot.plots_sizes[metric_code]
        else:
            figsize = (st.Plot.width, st.Plot.height)
        fig,mpl_axes = plt.subplots(figsize=figsize)


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
        # also collect the last Ys
        last_shifted_Ys = [0] * len(all_X)
        for i,pdata_X in enumerate(all_X):
            Y_shifted = ([y-0.5 for y in range(len(pdata_X))] +
                         [len(pdata_X)-0.5])
            last_shifted_Ys[i] = Y_shifted[-1]
            X = pdata_X + [pdata_X[-1]]
            mpl_axes.step(X, Y_shifted, where='pre', zorder=4, color=ind_color,
                          linewidth=ind_line_width)


        #####################################
        # PLOT MOVING AVERAGE OF METRICS
        # find range large enough to fit all plots
        Y_min = 0
        # unshift the max to generate the range
        Y_max = int(max(last_shifted_Ys) - 0.5)
        super_Y_shifted = [y-0.5 for y in list(range(Y_min, Y_max+1))]
        # get list with packs of all i-th Xs
        all_ith_xs_list = list(zip_longest(*all_X, fillvalue=None))

        # collect all averages
        super_X_avg = [0] * len(super_Y_shifted)
        for i,ith_xs in enumerate(all_ith_xs_list):
            valid_xs = [x for x in ith_xs if x is not None]
            xs_avg = sum(valid_xs) / len(valid_xs)
            super_X_avg[i] = xs_avg

        # extend X and Y so that the last bar is plotted correctly due to
        # matplotlib not being able to handle rotated step functions nicely
        super_Y_shifted.append(super_Y_shifted[-1]+1)
        super_X_avg.append(super_X_avg[-1])
        mpl_axes.step(super_X_avg, super_Y_shifted, where='pre', zorder=6,
                      color=avg_color, linewidth=avg_line_width)


        #####################################
        # PLOT VERT LINE AT LAST X OF EACH METRIC AND AVERAGE
        if st.Plot.aggr_last_x:
            xmin,xmax = -0.2,1.2
            # correct
            last_Ys = [y-0.5 for y in last_shifted_Ys]
            last_Y_text = cls.draw_last_Ys(mpl_axes, last_Ys, (xmin,xmax))


        #####################################
        # SETUP PLOT VISUALS
        # set plot limits
        X_pad,Y_pad = 'auto',0.5
        xlims = (0,1.0)
        ylims = (Y_min,Y_max)
        real_xlim, real_ylim = cls.setup_limits(
            mpl_axes, metric_code, xlims=xlims, x_pad=X_pad,
            ylims=ylims, y_pad=Y_pad, invert_y=True)

        # set ticks based on the real limits
        cls.setup_ticks(mpl_axes, xlims=real_xlim, ylims=real_ylim,
                        bases=(10, 10))

        # set grid
        if len(super_Y_shifted)-1 <= st.Plot.grid_max_blocks:
            cls.setup_grid(mpl_axes, fn_axis='x', axis='x')
            # cls.setup_manual_grid(mpl_axes, xlims=xlims, hlines=super_Y_shifted,
            #                        axis='y')
        else:
            cls.setup_grid(mpl_axes, fn_axis='x', axis='xy')

        # insert text box with average usage
        text = [f'Executions: {total_pdatas}']
        if st.Plot.aggr_last_x:
            text.append(last_Y_text)
        text.append(rf'Avg2 {metric_code}: '
                    f'{sum(super_X_avg)/len(super_X_avg):.2f}%')
        cls.draw_textbox(mpl_axes, text, metric_code)

        # set labels
        cls.setup_labels(mpl_axes, met_str)

        # title and bg color
        cls.setup_general(mpl_axes, pal.bg, met_str)

        PlotFile.save(fig, metric_code, aggr=True)
        return
