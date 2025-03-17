import matplotlib.pyplot as plt
from itertools import zip_longest

from ..settings import Settings as st
from ..util import MetricStrings, Palette, PlotFile
from ..ui import UI
from .base import BaseModule

class MemAccess(BaseModule):
    hue = 180
    supported_metrics = {
        'CMMA' : MetricStrings(
            about  = ('Cumulative distribution of main memory read/write '
                      'operations.'),
            title  = 'CMMA',
            subtit = 'lower is better',
            number = '03',
            xlab   = 'Time [access instr.]',
            ylab   = 'Cache Blocks Accessed in Main Memory [count]',
        )
    }
    supported_aggr_metrics = {
        'CMMA' : MetricStrings(
            about  = ('Average of cumulative main memory access.'),
            title  = 'Aggregated CMMA',
            subtit = 'lower is better',
            number = '03',
            xlab   = 'Time [access instr.]',
            ylab   = 'Cache Blocks Accessed in Main Memory [count]',
        )
    }

    def __init__(self, shared_X=None, hue=180):
        # enable metric if user requested it or if used as background
        self.enabled = (any(m in st.Metrics.enabled
                           for m in self.supported_metrics.keys()) or
                        st.Metrics.bg in self.supported_metrics)
        if not self.enabled:
            return

        # METRIC INTERNAL VARIABLES
        self.read = 0
        self.read_dist = [0 for _ in range(st.Map.time_size)]
        self.write = 0
        self.write_dist = [0 for _ in range(st.Map.time_size)]
        self.last_time = 0
        return

    def probe(self, rw):
        """Adds to read or write counter"""
        if not self.enabled:
            return
        if rw == 'r':
            self.read += 1
        else:
            self.write += 1
        return

    def commit(self, time):
        if not self.enabled:
            return
        # fill possible empty times with previous counts.
        last_read = self.read_dist[self.last_time]
        last_write = self.write_dist[self.last_time]
        for t in range(self.last_time+1, time):
            self.read_dist[t] = last_read
            self.write_dist[t] = last_write

        # add updated counters
        self.read_dist[time] = self.read
        self.write_dist[time] = self.write
        self.last_time = time

    def finalize(self):
        # no post-simulation computation to be done
        return

    def CMMA_to_dict(self):
        return {
            'code' : 'CMMA',
            'read_dist' : self.read_dist,
            'write_dist' : self.write_dist,
            'mem_size' : st.Map.mem_size,
            'line_size' : st.Cache.line_size
        }

    def dict_to_CMMA(self, data):
        try:
            self.read_dist = data['read_dist']
            self.write_dist = data['write_dist']
        except:
            class_name = self.__class__.__name__
            UI.error(f'{class_name}.dict_to_CMMA(): Malformed data.')
        return

    def CMMA_to_plot(self, mpl_axes, bg_mode=False):
        metric_code = 'CMMA'
        met_str = self.supported_metrics[metric_code]

        # create data series
        X = [i for i in range(st.Map.time_size)]
        Y_r = self.read_dist
        Y_w = self.write_dist


        #####################################
        ## CREATE COLOR PALETTE
        # two colors (for read and write), starting from self.hue
        pal = Palette(hue=2, h_off=self.hue,
                      # (line, _)
                      sat=st.Plot.p_sat,
                      lig=st.Plot.p_lig,
                      alp=st.Plot.p_alp)
        read_color = pal[0][0][0][0]
        write_color = pal[1][0][0][0]
        line_width = st.Plot.p_lw


        #####################################
        ## PLOT METRIC
        # plot read and write
        mpl_axes.step(X, Y_r, where='mid', zorder=3, color=read_color,
                      linewidth=line_width, label='Read Access')
        mpl_axes.step(X, Y_w, where='mid', zorder=3, color=write_color,
                      linewidth=line_width, label='Write Access')


        #####################################
        ## PLOT MEMORY SEGMENT SIZE
        # horizontal line with the size of the observed memory segment.
        # This size is in "blocks", as that is what this metric counts.
        mem_size = (st.Map.mem_size + st.Cache.line_size - 1) // \
            st.Cache.line_size
        mem_size_color = Palette.from_hsla((120,50,75,100))
        mem_size_line_width = st.Plot.p_lw
        mpl_axes.axhline(y=mem_size, color=mem_size_color, zorder=2,
                         linestyle='solid', linewidth=mem_size_line_width,
                         label='Memory Size')


        ###########################################
        ## PLOT VISUALS
        # set plot limits
        X_pad = 0.5
        Y_max = max(max(Y_r), max(Y_w))
        real_xlim, real_ylim = self.setup_limits(
            mpl_axes, metric_code, xlims=(X[0],X[-1]), x_pad=X_pad,
            ylims=(0,Y_max), y_pad='auto')

        # set ticks based on the real limits
        self.setup_ticks(mpl_axes, xlims=real_xlim, ylims=real_ylim,
                         bases=(10, 10), bg_mode=bg_mode)

        # set grid
        self.setup_grid(mpl_axes, fn_axis='y', bg_mode=bg_mode)

        # insert text box with total read/write count
        if not bg_mode:
            text = (f'Total Read : {self.read_dist[-1]}\n'
                    f'Total Write: {self.write_dist[-1]}\n'
                    f'Memory Size [blocks]: {mem_size}')
            # this plot always has lines in the top-right corner,
            # so if user did not specify anything, let's put it in
            # the top-left corner.
            if metric_code not in st.Plot.textbox_offsets:
                st.Plot.textbox_offsets[metric_code] = (0.02, 0.98)
            self.draw_textbox(mpl_axes, text, metric_code)

        # set labels
        self.setup_labels(mpl_axes, met_str, bg_mode=bg_mode)

        # title and bg color
        self.setup_general(mpl_axes, pal.bg, met_str, bg_mode=bg_mode)
        return

    @classmethod
    def CMMA_to_aggregated_plot(cls, pdata_dicts):
        """Given a list of pdata dictionaries, aggregate their
        values in a meaningful manner"""
        # metric info
        metric_code = pdata_dicts[0]['fg']['code']
        met_str = cls.supported_aggr_metrics[metric_code]

        # extract data from dictionaries and create figure
        total_pdatas = len(pdata_dicts)
        all_read = [m['fg']['read_dist'] for m in pdata_dicts]
        all_write = [m['fg']['write_dist'] for m in pdata_dicts]
        all_mem_size = [m['fg']['mem_size'] for m in pdata_dicts]
        all_line_size = [m['fg']['line_size'] for m in pdata_dicts]
        fig,mpl_axes = plt.subplots(figsize=(st.Plot.width, st.Plot.height))


        #####################################
        # CREATE COLOR PALETTE
        pal = Palette(
            # two colors (read and write) starting from cls.hue
            hue = 2, h_off=cls.hue,
            # (individual, average)
            sat = (60, 100),
            lig = (70,  30),
            alp = (10, 100))
        read_ind_color = pal[0][0][0][0]
        read_avg_color = pal[0][1][1][1]
        write_ind_color = pal[1][0][0][0]
        write_avg_color = pal[1][1][1][1]
        ind_line_width = st.Plot.p_aggr_ind_lw
        avg_line_width = st.Plot.p_aggr_avg_lw


        #####################################
        # PLOT INDIVIDUAL METRICS
        R_max,W_max = 0,0
        X_min,X_max = 0,0
        for pdata_r,pdata_w in zip(all_read,all_write):
            W = pdata_w
            R = pdata_r
            X = [i for i in range(len(pdata_r))]
            mpl_axes.step(X, W, where='mid', zorder=4, color=write_ind_color,
                          linewidth=ind_line_width)
            mpl_axes.step(X, R, where='mid', zorder=4, color=read_ind_color,
                          linewidth=ind_line_width)
            R_max = max(R[-1], R_max)
            W_max = max(W[-1], W_max)
            X_max = max(X[-1], X_max)


        #####################################
        # PLOT MOVING AVERAGE OF METRICS
        # create a range large enough to fit all pdatas
        super_X = list(range(X_min, X_max+1))
        # obtain all i-th operations
        all_ith_reads = list(zip_longest(*all_read, fillvalue=None))
        all_ith_writes = list(zip_longest(*all_write, fillvalue=None))
        R_avg = [0] * len(super_X)
        W_avg = [0] * len(super_X)

        # compute average read and write accesses
        for sx,ith_reads,ith_writes in zip(super_X,all_ith_reads,
                                           all_ith_writes):
            valid_r = [r for r in ith_reads if r is not None]
            r_avg = sum(valid_r) / len(valid_r)
            R_avg[sx] = r_avg

            valid_w = [w for w in ith_writes if w is not None]
            w_avg = sum(valid_w) / len(valid_w)
            W_avg[sx] = w_avg

        # plot average read and write
        mpl_axes.step(super_X, R_avg, where='mid', zorder=6,
                      color=read_avg_color, linewidth=avg_line_width,
                      label='Average Read Access')
        mpl_axes.step(super_X, W_avg, where='mid', zorder=6,
                      color=write_avg_color, linewidth=avg_line_width,
                      label='Average Write Access')


        #####################################
        # AVERAGE MEMORY SIZE
        # plot horizontal line with the size of the observed memory segment.
        # This size is in "blocks", as that is what this metric counts.
        all_mem_size_in_blocks = [mz//cl for mz,cl in
                                  zip(all_mem_size,all_line_size)]
        avg_mem_size = sum(all_mem_size_in_blocks)/len(all_mem_size_in_blocks)
        mem_size_color = Palette.from_hsla((120,50,75,100))
        mem_size_line_width = st.Plot.p_aggr_avg_lw
        mpl_axes.axhline(y=avg_mem_size, color=mem_size_color, zorder=3,
                         linestyle='solid', linewidth=mem_size_line_width,
                         label='Average Memory Block Size')
        avg_mem_size_text = f'Avg Memory size [blocks]: {avg_mem_size:.0f}'


        #####################################
        # PLOT VERT LINE AT LAST X OF EACH METRIC AND AVERAGE
        if st.Plot.aggr_last_x:
            last_Xs = [len(r)-1 for r in all_read]
            ymax = max(R_max,W_max)*1.2
            ymin = 0 - max(R_max,W_max)*0.2
            last_X_text = cls.draw_last_Xs(mpl_axes, last_Xs, (ymin,ymax))


        #####################################
        # PLOT VISUALS
        # set plot limits
        X_pad,Y_pad = 0.5,'auto'
        xlims = (X_min,X_max)
        ylims = (0,max(R_max, W_max))
        real_xlim, real_ylim = cls.setup_limits(
            mpl_axes, metric_code, xlims=xlims, x_pad=X_pad, ylims=ylims,
            y_pad=Y_pad)

        # set ticks based on the real limits
        cls.setup_ticks(mpl_axes, xlims=real_xlim, ylims=real_ylim,
                        bases=(10, 10))

        # set grid
        axis = 'y' if st.Plot.aggr_last_x else 'xy'
        cls.setup_grid(mpl_axes, axis=axis, fn_axis='y')

        # insert text box with average usage
        text = [f'Executions: {total_pdatas}']
        if st.Plot.aggr_last_x:
            text.append(last_X_text)
        text.append(f'Max Avg Total Read Access : {max(R_avg):.0f}')
        text.append(f'Max Avg Total Write Access: {max(W_avg):.0f}')
        text.append(avg_mem_size_text)
        cls.draw_textbox(mpl_axes, text, metric_code)

        # set labels
        cls.setup_labels(mpl_axes, met_str)

        # title and bg color
        cls.setup_general(mpl_axes, pal.bg, met_str)

        PlotFile.save(fig, metric_code, aggr=True)
        return
