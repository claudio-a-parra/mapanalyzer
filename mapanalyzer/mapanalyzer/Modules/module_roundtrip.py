import matplotlib.pyplot as plt
from itertools import zip_longest
import math

from ..settings import Settings as st
from ..util import MetricStrings, Palette, PlotFile, sample_list, \
    median
from ..ui import UI
from .base import BaseModule

class EvictionRoundtrip(BaseModule):
    hue = 135
    supported_metrics = {
        'BPA' : MetricStrings(
            about  = ('The Block-Personality that each Cache Set adopts.'),
            title  = 'BPA',
            subtit = '',
            number = '06',
            xlab   = 'Time [access instr.]',
            ylab   = 'Space [blocks]',
        ),
        'SMRI' : MetricStrings(
            about  = ('The time a block spends in main memory until it is '
                      'fetched back to cache.'),
            title  = 'SMRI',
            subtit = 'fewer is better',
            number = '07',
            xlab   = 'Time [access instr.]',
            ylab   = 'Space [blocks]',
        ),
        'MRID' : MetricStrings(
            about  = ('Histogram showing the memory roundtrip intervals '
                      'duration distribution.'),
            title  = 'MRID',
            subtit = 'right-skewed is better',
            number = '08',
            xlab   = 'Rountrip duration [access instr.]',
            ylab   = 'Frequency',
        )
    }
    supported_aggr_metrics = {
        'MRID' : MetricStrings(
            about  = ('Median MRID.'),
            title  = 'Median MRI Distribution',
            subtit = 'right-skewed is better',
            number = '08',
            xlab   = 'Rountrip duration [access instr.]',
            ylab   = 'Frequency',
        )
    }


    def __init__(self):
        self.enabled = (any(m in st.Metrics.enabled
                           for m in self.supported_metrics.keys()) or
                        st.Metrics.bg in self.supported_metrics)
        if not self.enabled:
            return

        # METRIC INTERNAL VARIABLES
        # number of sets in the cache.
        self.num_sets = st.Cache.num_sets

        # This table-of-dicts stores the in-cache time duration of each block.
        # The block_id is the concatenation of the block-tag and the set-id.
        # So, assuming 3bits set size:
        # block_id 35 = b1000011 =  b1000 concat b011 = tag:9, set:3
        #                 +------ set id
        #                 |  +-- block tag
        #                 |  |
        # alive_intervals[3][9] -> [(time_in,t_out), (t_in,t_out), ...]
        self.alive_intervals = [{} for _ in range(self.num_sets)]
        self.dead_intervals = [{} for _ in range(self.num_sets)]

        # S lists with the personality switch history of each set. Each
        # change is a tuple set_idx -> [(time, old_block, new_block), ...]
        self.personalities = [[] for _ in range(self.num_sets)]

        return

    def probe(self, time, set_idx, tag_in, tag_out):
        if not self.enabled:
            return

        # if a block is being fetched...
        if tag_in is not None:
            # Begin registration of in-Cache interval
            if tag_in not in self.alive_intervals[set_idx]:
                self.alive_intervals[set_idx][tag_in] = []
            self.alive_intervals[set_idx][tag_in].append((time, None))

        # if a block is being evicted...
        if tag_out is not None:
            # Finish registration of in-Cache interval
            if tag_out in self.alive_intervals[set_idx]:
                fetch_time = self.alive_intervals[set_idx][tag_out][-1][0]
                evict_time = time
                self.alive_intervals[set_idx][tag_out][-1] = \
                    (fetch_time,evict_time)


        # if one block is evicted and the other fetched...
        if tag_in is not None and tag_out is not None:
            # the set is changing personality
            block_in_id = (tag_in  << st.Cache.bits_set) | set_idx
            block_out_id = (tag_out  << st.Cache.bits_set) | set_idx
            self.personalities[set_idx].append(
                (time,block_out_id,block_in_id))
        return

    def commit(self, time):
        if not self.enabled:
            return
        # this tool doesn't need to do anything at the end of each time step.
        return

    def finalize(self):
        """
        Three things are done here:
        (1) Derive dead intervals.
        (2) Transform alive and dead intervals to plot-friendly format.
        (3) Transform set_personalities to plot-friendly format.
        """
        if not self.enabled:
            return


        # (1) Derive self.dead_intervals from self.alive_intervals.
        # dead_intervals is the time in between alive_intervals.
        # Also, while we traverse alive intervals, let's fix the end-time of
        # alive intervals (None -> st.Map.time_size-1)
        for set_idx,set_intervals in enumerate(self.alive_intervals):
            for tag,blk_intervals in set_intervals.items():
                # if the block was alive only once, then there is no dead
                # interval.
                if len(blk_intervals) < 2:
                    continue

                # there is activity to register. Allocate memory
                if tag not in self.dead_intervals[set_idx]:
                    self.dead_intervals[set_idx][tag] = []

                #take pairs of alive intervals to compute dead intervals
                for i,(aliv_bef,aliv_aft) in enumerate(zip(
                        blk_intervals[:-1],blk_intervals[1:])):
                    self.dead_intervals[set_idx][tag].append(
                        (aliv_bef[1],aliv_aft[0]))

                # let's fix the end_time of the last alive time interval.
                # This, though, should have been taken care by Cache.flush()
                last_in,last_out = self.alive_intervals[set_idx][tag][-1]
                if last_out is None:
                    self.alive_intervals[set_idx][tag][-1] = (
                        last_in, st.Map.time_size-1)


        # (2) Transform self.dead/alive_intervals to a plot-friendly format.
        # self.dead/alive_intervals is indexed by (set,tag), and each element is
        # a list of the (start time,end time) alive time (horizontal line):
        #
        # self.alive_intervals[<set>][<tag>] -> [(t0,t1), (t0,t1), ...]
        #                     ^^^^^^^^^^^^^^
        #                            `----- block id
        #
        # Here we transform it so that for each set, three lists of the same
        # length is created:
        # - block id (Y coordinate)
        # - start time (left X coordinate)
        # - end time (right X coordinate)
        #
        # self.alive_intervals[<set>] -> {'bl':[], 't0': [], 't1': []}
        #
        # This format is suitable for matplotlib to efficiently plot the
        # horizontal lines. The just created dead_intervals is also transformed
        # to this format.
        plot_alive_intervals = [{} for _ in range(self.num_sets)]
        # for each set that registers activity...
        for set_idx,blocks_intervals in enumerate(self.alive_intervals):
            # create equal-length lists
            blk_ids,fetch_times,evict_times = [], [], []
            # for each tag that registers activity...
            for tag,evicts_fetches in sorted(blocks_intervals.items()):
                for t_in,t_out in evicts_fetches:
                    blk_ids.append((tag << st.Cache.bits_set) | set_idx)
                    fetch_times.append(t_in-0.5)
                    evict_times.append(t_out-0.5)
            plot_alive_intervals[set_idx] = {
                'bl' : blk_ids,
                't0' : fetch_times,
                't1' : evict_times
            }
        self.alive_intervals = plot_alive_intervals

        plot_dead_intervals = [{} for _ in range(self.num_sets)]
        # for each set that registers activity...
        for set_idx,blocks_intervals in enumerate(self.dead_intervals):
            # create equal-length lists
            blk_ids,evict_times,fetch_times = [], [], []
            # for each tag that registers activity...
            for tag,fetches_evicts in sorted(blocks_intervals.items()):
                for t_out,t_in in fetches_evicts:
                    blk_ids.append((tag << st.Cache.bits_set) | set_idx)
                    evict_times.append(t_out-0.5)
                    fetch_times.append(t_in-0.5)
            plot_dead_intervals[set_idx] = {
                'bl' : blk_ids,
                't0' : evict_times,
                't1' : fetch_times
            }
        # self.dead_intervals[<set>] -> {'bl':[], 't0': [], 't1': []}
        self.dead_intervals = plot_dead_intervals


        # (3) Transform self.personalities to a plot-friendly format.
        # self.personalities is also set-indexed, where each element is
        # a tuple (switch time, block0 (from), block1 (to))

        # self.personalities[<set>] -> [(t,b0,b1), (t,b0,b1), ...]

        # Here we transform that so that we can plot a bunch of diagonal lines.
        # This is a weird format of matplotlib where two list are needed:
        # one with time-coordinates (X), and other with block_coordinates (Y).
        # But the arrays have <None> separators:

        # self.personalities[<set>] -> {
        #     't' : [t0, t1, None, t0, t1, None, ..., ..., None, ...],
        #     'b' : [b0, b1, None, b0, b1, None, ..., ..., None, ...]
        # }
        plot_personalities = [{} for _ in range(self.num_sets)]
        for set_idx,perso in enumerate(self.personalities):
            # three times long because of the 'start, end, None' triplets
            times = [0 for _ in range(len(perso)*3)]
            blocks = [0 for _ in range(len(perso)*3)]
            for i,(t,blk_old,blk_new) in enumerate(perso):
                ii = 3*i
                times[ii],times[ii+1],times[ii+2] = t-1, t, None
                blocks[ii],blocks[ii+1],blocks[ii+2] = blk_old, blk_new, None

            plot_personalities[set_idx] = {
                't' : times,
                'b' : blocks
            }
        self.personalities = plot_personalities
        return


    def BPA_to_dict(self):
        return {
            'code' : 'BPA',
            'alive_intervals' : self.alive_intervals,
            'personalities' : self.personalities,
            'num_sets' : self.num_sets
        }

    def dict_to_BPA(self, data):
        try:
            self.alive_intervals = data['alive_intervals']
            self.personalities = data['personalities']
            self.num_sets = int(data['num_sets'])
        except:
            class_name = self.__class__.__name__
            UI.error(f'{class_name}.dict_to_BPA(): Malformed data.')
        return

    def BPA_to_plot(self, mpl_axes, bg_mode=False):
        metric_code = 'BPA'
        met_str = self.supported_metrics[metric_code]


        #####################################
        ## CREATE COLOR PALETTE
        # each set has its color {set -> color}
        set_to_color = [''] * self.num_sets
        pal = Palette(
            hue = len(set_to_color), h_off=self.hue,
            # blocks, _
            sat = ( 50, 0),
            lig = ( 75, 0),
            alp = (100, 0))
        for s in range(self.num_sets):
            set_to_color[s] = pal[s][0][0][0]

        plt_w,plt_h = self.get_plot_xy_size(mpl_axes)
        height_range = st.Map.num_blocks
        if metric_code in st.Plot.y_ranges:
            ymin,ymax = st.Plot.y_ranges[metric_code]
            height_range = ymax - ymin
        block_line_width = plt_h / height_range
        block_line_alpha = 0.5
        block_line_style = '-'

        width_range = st.Map.time_size
        if metric_code in st.Plot.x_ranges:
            xmin,xmax = st.Plot.x_ranges[metric_code]
            width_range = xmax - xmin
        jump_line_width = min(max(0.1, plt_w / (3*width_range)),5)
        jump_line_alpha = 1
        jump_line_style = '-'


        #####################################
        ## PLOT METRIC
        mpl_fig = mpl_axes.figure
        if st.Plot.plot_indiv_sets:
            plot_types = ('single', 'all')
        else:
            plot_types = ('all')
        # save plots for each independent set, and one for all together
        for plot_type in plot_types:
            for set_idx,(set_interv,set_person,set_color) in enumerate(zip(
                    self.alive_intervals, self.personalities, set_to_color)):
                mpl_axes.hlines(y=set_interv['bl'], xmin=set_interv['t0'],
                                xmax=set_interv['t1'],
                                color=set_color, linewidth=block_line_width,
                                alpha=block_line_alpha, zorder=2,
                                linestyle=block_line_style)

                mpl_axes.plot(set_person['t'], set_person['b'],
                              color=set_color, linewidth=jump_line_width,
                              alpha=jump_line_alpha, zorder=3,
                              linestyle=jump_line_style, solid_capstyle='round')

                # visuals for each "single" plot, or after the last of "all"
                if plot_type == 'single' or set_idx == self.num_sets-1:
                    ###########################################
                    ## PLOT VISUALS
                    # set plot limits
                    X_pad,Y_pad = 0.5,0.5
                    X_min,X_max = 0,st.Map.time_size-1
                    Y_min,Y_max = 0,st.Map.num_blocks-1
                    xlims = (X_min, X_max)
                    ylims = (Y_min, Y_max)
                    real_xlim, real_ylim = self.setup_limits(
                        mpl_axes, metric_code, xlims=xlims, x_pad=X_pad,
                        ylims=ylims, y_pad=Y_pad, invert_y=True)

                    # set ticks based on the real limits
                    self.setup_ticks(mpl_axes, xlims=real_xlim, ylims=real_ylim,
                                     bases=(10, 10), bg_mode=bg_mode)

                    # set grid
                    self.setup_grid(mpl_axes, fn_axis='y', bg_mode=bg_mode)

                    # set labels
                    self.setup_labels(mpl_axes, met_str, bg_mode=bg_mode)

                    # title and bg color
                    variant = ''
                    if plot_type == 'single':
                        variant = f's{set_idx:02d}'
                    self.setup_general(mpl_axes, pal.bg, met_str,
                                       variant=variant,
                                       bg_mode=bg_mode)

                    # save if single mode
                    if plot_type == 'single':
                        PlotFile.save(mpl_fig, metric_code,
                                      variant=f'_s{set_idx:02d}')
                        # reset axes
                        mpl_axes.clear()
                        mpl_fig.canvas.draw()
        return


    def SMRI_to_dict(self):
        return {
            'code' : 'SMRI',
            'dead_intervals' : self.dead_intervals,
            'num_sets' : self.num_sets
        }

    def dict_to_SMRI(self, data):
        try:
            self.dead_intervals = data['dead_intervals']
            self.num_sets = int(data['num_sets'])
        except:
            class_name = self.__class__.__name__
            UI.error(f'{class_name}.dict_to_SMRI(): Malformed data.')
        return

    def SMRI_to_plot(self, mpl_axes, bg_mode=False):
        metric_code = 'SMRI'
        met_str = self.supported_metrics[metric_code]


        #####################################
        ## CREATE COLOR PALETTE
        # each set has its color {set -> color}
        set_to_color = [''] * self.num_sets
        pal = Palette(
            hue = len(set_to_color), h_off=self.hue,
            sat = ( 25, 0),
            lig = ( 50, 0),
            alp = (100, 0))
        for s in range(self.num_sets):
            set_to_color[s] = pal[s][0][0][0]

        # compute the width of block lines
        plt_w,plt_h = self.get_plot_xy_size(mpl_axes)
        height_range = st.Map.num_blocks
        if metric_code in st.Plot.y_ranges:
            ymin,ymax = st.Plot.y_ranges[metric_code]
            height_range = ymax - ymin
        block_line_width = max(0.3, plt_h / height_range)
        block_line_alpha = 0.5
        block_line_style = '-'


        #####################################
        ## PLOT METRIC
        mpl_fig = mpl_axes.figure
        X_pad,Y_pad = 0.5,0.5
        X_min,X_max = 0,st.Map.time_size-1
        Y_min,Y_max = 0,st.Map.num_blocks-1
        xlims = (X_min, X_max)
        ylims = (Y_min, Y_max)
        if st.Plot.plot_indiv_sets:
            plot_types = ('single', 'all')
        else:
            plot_types = ('all')
        no_data_in_all_sets = sum(
            len(siv['bl']) for siv in self.dead_intervals) == 0
        # save plots for each independent set, and one for all together
        for plot_type in plot_types:
            all_roundtrips_count = 0 # count of dead segments <= threshold.
            for set_idx,(set_intervs,set_color) in enumerate(zip(
                    self.dead_intervals, set_to_color)):
                blocks = set_intervs['bl']
                no_data_in_this_set = len(blocks) == 0
                t_start = set_intervs['t0']
                t_end = set_intervs['t1']
                roundtrips_count = len(blocks)


                # If a maximum threshold was given by the user, then filter
                # the intervals to only plot shorter ones.
                thrshld = st.Plot.roundtrip_threshold
                thrshld_text = '(all)'
                if thrshld != 'all':
                    blocks,t_start,t_end = [],[],[]
                    for bl,t0,t1 in zip(set_intervs['bl'], set_intervs['t0'],
                                        set_intervs['t1']):
                        if int(t1-t0) <= thrshld:
                            blocks.append(bl)
                            t_start.append(t0)
                            t_end.append(t1)
                    roundtrips_count = len(blocks)
                    thrshld_text = rf' ($\leq${thrshld})'
                all_roundtrips_count += roundtrips_count

                mpl_axes.hlines(y=blocks, xmin=t_start, xmax=t_end,
                                color=set_color, linewidth=block_line_width,
                                alpha=block_line_alpha, zorder=2,
                                linestyle=block_line_style)


                ###########################################
                ## PLOT VISUALS
                # visuals for each "single" plot, or after the last of "all"
                if plot_type == 'single' or set_idx == self.num_sets-1:
                    # set plot limits
                    real_xlim, real_ylim = self.setup_limits(
                        mpl_axes, metric_code, xlims=xlims, x_pad=X_pad,
                        ylims=ylims, y_pad=Y_pad, invert_y=True)

                    # set ticks based on the real limits
                    self.setup_ticks(mpl_axes, xlims=real_xlim, ylims=real_ylim,
                                     bases=(10, 10), bg_mode=bg_mode)

                    # set grid
                    self.setup_grid(mpl_axes, fn_axis='y', bg_mode=bg_mode)

                    # insert text box with total read/write count
                    if not bg_mode:
                        count = all_roundtrips_count
                        if plot_type == 'single':
                            count = roundtrips_count
                        text = (rf'{metric_code} count{thrshld_text} : {count}')

                        # If there is no data to plot, show a "NO DATA" message
                        off = (None, None)
                        if (plot_type == 'single' and no_data_in_this_set) or \
                           (plot_type == 'all' and no_data_in_all_sets):
                            text = f'{metric_code}: NO DATA'
                            off = (0.5,0.5)
                        self.draw_textbox(mpl_axes, text, metric_code, off=off)

                    # set labels
                    self.setup_labels(mpl_axes, met_str, bg_mode=bg_mode)

                    # title and bg color
                    variant = ''
                    if plot_type == 'single':
                        variant = f's{set_idx:02d}'
                    self.setup_general(mpl_axes, pal.bg, met_str,
                                       variant=variant,
                                       bg_mode=bg_mode)

                    # save if single mode
                    if plot_type == 'single':
                        PlotFile.save(mpl_fig, metric_code,
                                      variant=f'_s{set_idx:02d}')
                        # reset axes
                        mpl_axes.clear()
                        mpl_fig.canvas.draw()
        return


    def MRID_to_dict(self):
        return {
            'code' : 'MRID',
            'dead_intervals' : self.dead_intervals,
            'num_sets' : self.num_sets
        }

    def dict_to_MRID(self, data):
        try:
            self.dead_intervals = data['dead_intervals']
            self.num_sets = int(data['num_sets'])
        except:
            class_name = self.__class__.__name__
            UI.error(f'{class_name}.dict_to_MRID(): Malformed data.')
        return

    def MRID_to_plot(self, mpl_axes, bg_mode=False):
        metric_code = 'MRID'
        met_str = self.supported_metrics[metric_code]


        #####################################
        ## CREATE COLOR PALETTE
        # each set has its color set_to_color[set] -> color:str
        # for histogram and medians
        hset_to_color = ['' for _ in range(self.num_sets)]
        mset_to_color = ['' for _ in range(self.num_sets)]
        pal = Palette(
            hue = self.num_sets, h_off=self.hue,
            # bars, medians (vertical lines)
            sat = (50,  90),
            lig = (75,  35),
            alp = (100, 90))
        for s in range(self.num_sets):
            hset_to_color[s] = pal[s][0][0][0]
            mset_to_color[s] = pal[s][1][1][1]

        #####################################
        ## CREATE DATA SERIES
        # obtain dead intervals and medians (per set) and max dead interval
        # (across all sets)
        intervs, medians, range_intervs = \
            self.__obtain_intervals(interv_marks=self.dead_intervals)

        if all(m is None for m in medians):
            self.draw_textbox(mpl_axes, f'{metric_code}: NO DATA', metric_code,
                              off=(0.5,0.5))
            return

        # define bin edges
        global_max_interv = max(ri[1] for ri in range_intervs if ri is not None)
        bin_edges = self.__create_bins(max_value=global_max_interv)
        lin_bin_edges = [i for i in range(len(bin_edges))]

        # map dead intervals and bin edges to a linear scale so the histogram
        # has even columns width
        lin_intervs, lin_medians = self.__linearize_data(intervs, medians,
                                                         bin_edges)


        #####################################
        ## PLOT HISTOGRAM
        hist_labels = [f's{s}' for s in range(self.num_sets)]
        counts,_,_ = mpl_axes.hist(lin_intervs, bins=lin_bin_edges,
                                   label=hist_labels, color=hset_to_color,
                                   stacked=True, zorder=3, width=0.95)


        #####################################
        ## PLOT MEDIANS
        for med_x, med_col in zip(lin_medians, mset_to_color):
            if med_x is None:
                continue
            mpl_axes.axvline(x=med_x, color=med_col, linestyle='-',
                             linewidth=3, zorder=4)


        #####################################
        # PLOT VISUALS
        # setup limits and tick-labels
        Y_max = int(max(max(i) if len(i) else 0 for i in counts))
        ylims = (0,max(Y_max,1))
        xlims = (1,max(1,global_max_interv))
        lin_xmax = self.__setup_hist_limits_and_ticks(
            mpl_axes, metric_code=metric_code, xlims=xlims, ylims=ylims,
            xticks=lin_bin_edges, xticks_labels=bin_edges)

        # insert text box with medians
        if all(di is None for di in medians):
            self.draw_textbox(mpl_axes, f'{metric_code}: NO DATA', metric_code,
                              off=(0.5,0.5))
        else:
            # compose the text to display in the textbox. One line per set
            text_lines = []
            for s,s_med in enumerate(medians):
                if s_med is not None:
                    text_lines.append(f's{s} median MRI: {s_med:.1f}')

            # if too many lines, trim the list
            max_sets = 16
            if len(text_lines) > max_sets:
                text_lines = text_lines[:((max_sets+1)//2)] + ['...'] + \
                    text_lines[-(max_sets//2):]

            # if the user did not specify where to put the textbox, provide
            # a default value.
            if metric_code not in st.Plot.textbox_offsets:
                # try to be a smart-ass and place the textbox in a place where
                # it doesn't bother: look at where the avg of medians is, and
                # avoid that area.
                h_offset = 0.98
                lin_real_medians = [m for m in lin_medians if m is not None]
                if len(lin_real_medians) > 0:
                    avg_lin_medians = sum(lin_real_medians) / \
                        len(lin_real_medians)
                    peak_hist = avg_lin_medians / lin_xmax
                    h_offset = 0.02 if peak_hist > 0.5 else 0.98
                st.Plot.textbox_offsets[metric_code] = (h_offset, 0.98)

            # draw the text
            self.draw_textbox(mpl_axes, text_lines, metric_code)

        # set labels
        self.setup_labels(mpl_axes, met_str)

        # title and bg color
        # 'white' because there is no possible bg plot for this boy
        self.setup_general(mpl_axes, 'white', met_str)

        return

    @classmethod
    def __obtain_intervals(cls, interv_marks:list):
        """
        Obtains list of intervals (per set), median (per set), and maximum
        (across all sets).
        """
        num_sets = len(interv_marks)
        # all_intervals[set] -> [di0:int, di1, di2, ...]
        all_intervals = [None for _ in range(num_sets)]
        # med_intervals[set] -> median:int
        med_intervals = [None for _ in range(num_sets)]
        # range_intervals[set] -> (min:int, max:int)
        range_intervals = [None for _ in range(num_sets)]
        for set_idx,marks in enumerate(interv_marks):
            # transform marks to a plain list of lengths for this set
            set_intervs = sorted(
                [int(t1-t0) for t0,t1 in zip(marks['t0'],marks['t1'])])

            all_intervals[set_idx] = set_intervs

            # get median dead interval (if there are any items)
            if len(set_intervs) == 0:
                continue
            med_intervals[set_idx] = median(set_intervs)

            # get the range
            range_intervals[set_idx] = (set_intervs[0], set_intervs[-1])

        return all_intervals, med_intervals, range_intervals

    @classmethod
    def __create_bins(cls, exp=30, max_value=None):
        """
        Create bins up to 2^exp in "half" exponential fashion
        """
        bin_right_edges = [1] * (2 * exp + 1)
        for i,e in enumerate([i/2 for i in range(1, 2*exp+2)]):
            bin_right_edges[i] = round(2**e)

        # if the created rightmost edge is still too small to fit the max value,
        # then create an extra bin to fit the largest interval
        if max_value is not None and bin_right_edges[-1] < max_value:
            bin_right_edges += [int(max_value+1)]
        # else:
        #     curr_idx = 0
        #     for right_edge in bin_right_edges:
        #         curr_idx += 1
        #         if max_value < right_edge:
        #             break
        #     bin_right_edges = bin_right_edges[:curr_idx]

        # add the left edge of the first bin.
        return [0] + bin_right_edges

    @classmethod
    def __linearize_data(cls, intervs, medians, bin_edges):
        """
        Bins are of different width. So columns would be narrow on the left,
        and wide on the right. Normalize the histogram by creating a new
        dataset with a linear distribution.
        Map real dead-interval values (from bins of different sizes) to linear
        values (to bins of same width).
        """

        # linear counterpart of the original dataset.
        # linear_intervs[set] -> [li0:int, li1, li2, ...]
        linear_intervs = [[0]*len(set_di)
                                 if set_di is not None else []
                                 for set_di in intervs]

        for s,set_dinterv in enumerate(intervs):
            if set_dinterv is None:
                continue
            # current bin being used
            curr_bin_idx = 0
            # map all original data to the linear dataset
            for i,dint in enumerate(set_dinterv):
                # find the correct bin for this dead interval (dint)
                # (yes, this assumes set_dinterv is sorted, and it is.)
                while dint >= bin_edges[curr_bin_idx]:
                    curr_bin_idx += 1
                # add data-point to linear dataset.
                linear_intervs[s][i] = curr_bin_idx-1

        linear_medians = [None for _ in medians]
        for set_idx,set_median in enumerate(medians):
            if set_median is None:
                continue
            linear_medians[set_idx] = 2*math.log2(set_median)

        return linear_intervs, linear_medians

    @classmethod
    def __setup_hist_limits_and_ticks(cls, mpl_axes, metric_code, xlims, ylims,
                                      xticks, xticks_labels):
        """
        Setup X and Y axes limits, ticks and labels. The X axis is a bit
        tricky because it has linear (0, 1, 2...) ticks, but it shows the
        exponential scale (the tick "labels").
        Returns the linear x_max value.
        """
        #####################################
        ## SET X-AXIS LIMITS AND TICK LABELS
        # find the tick index (what matplotlib sees) based on what the user
        # gave (relative to xtick_lables)
        xmin = xlims[0]
        xmax = xlims[1]
        if metric_code in st.Plot.x_ranges:
            xmin,xmax = st.Plot.x_ranges[metric_code]
            xmin = max(1,xmin)
            xmax = max(xmin,xmax)

        # find the first tick (bin_edge) that is just at the left of
        # the given xmin
        curr_label_idx = 0
        while xticks_labels[curr_label_idx] <= xmin:
            curr_label_idx += 1
        xmin_idx = curr_label_idx - 1

        # find the first tick (bin_edge) that is just at the right of
        # the given xmax
        curr_label_idx = 0
        while xticks_labels[curr_label_idx] <= xmax:
            curr_label_idx += 1
        xmax_idx = curr_label_idx

        # Set axis parameters: ticks, tick-labels, and limits
        mpl_axes.set_xticks(xticks[xmin_idx:xmax_idx+1])
        mpl_axes.set_xticklabels(xticks_labels[xmin_idx:xmax_idx+1])
        mpl_axes.tick_params(axis='x', rotation=-90)
        xpad = (xmax_idx - xmin_idx) / 100
        mpl_axes.set_xlim(xmin_idx-xpad, xmax_idx+xpad)


        #####################################
        ## SET Y-AXIS LIMITS AND TICK LABELS
        ymin = ylims[0]
        ymax = ylims[1]
        if metric_code in st.Plot.y_ranges:
            ymin,ymax = st.Plot.y_ranges[metric_code]
            ymin = max(0,ymin)
            ymax = max(ymin,ymax)
            top_ypad = (ymax-ymin) / 100
            bot_ypad = top_ypad
        else:
            top_ypad = (ymax-ymin) / 10
            bot_ypad = 0

        # create list of ticks
        y_tick_count = st.Plot.ticks_max_count[1]
        y_tick_list = list(range(ymin,int(ymax+1+top_ypad)))
        y_tick_labels = sample_list(y_tick_list, n=y_tick_count, base=10)

        # Set axis parameters: ticks and limits
        mpl_axes.set_yticks(y_tick_labels)
        mpl_axes.set_ylim(ymin-bot_ypad, ymax+top_ypad)
        alp = st.Plot.grid_alpha[1]
        sty = st.Plot.grid_style[1]
        wid = st.Plot.grid_width[1]
        mpl_axes.grid(axis='y', which='both', zorder=10, alpha=alp,
                              linestyle=sty, linewidth=wid)
        return xmax_idx

    @classmethod
    def MRID_to_aggregated_plot(cls, all_pdata_dicts):
        """
        Aggregate the multiple dictionaries.
        Basically create a huge pool of interval lengths, separate them in bins,
        and pick the median of each bin and use that to create the histogram.
        Also, each bin will show a vertical I-shaped bar showing the full range
        of that bin across all instances.
        """
        # metric info
        metric_code = all_pdata_dicts[0]['fg']['code']
        met_str = cls.supported_aggr_metrics[metric_code]

        # extract data from dictionaries
        all_interv_marks = [pd['fg']['dead_intervals']
                            for pd in all_pdata_dicts]
        num_pdatas = len(all_interv_marks)

        # define the figure size for this particular plot
        if metric_code in st.Plot.plots_sizes:
            figsize = st.Plot.plots_sizes[metric_code]
        else:
            figsize = (st.Plot.width, st.Plot.height)
        fig,mpl_axes = plt.subplots(figsize=figsize)

        # obtain intervals and stats for each pdata_mark
        pdatas_intervs = []
        pdatas_medians = []
        pdatas_ranges = []
        global_max_interv = 0
        for pdata_marks in all_interv_marks:
            # flatten marks so that there is only one "dummy" set that merges
            # all the actual sets in this pdata_marks
            merged_t0 = []
            merged_t1 = []
            for set_marks in pdata_marks:
                merged_t0.extend(set_marks['t0'])
                merged_t1.extend(set_marks['t1'])

            merged_marks = [{'bl':None, 't0':merged_t0, 't1':merged_t1}]
            intervs, medians, ranges = cls.__obtain_intervals(merged_marks)
            pdatas_intervs.append(intervs)
            pdatas_medians.append(medians)
            pdatas_ranges.append(ranges)
            if ranges[0] is not None:
                global_max_interv = max(global_max_interv,ranges[0][1])

        # define bin edges
        bin_edges = cls.__create_bins(max_value=global_max_interv)
        lin_bin_edges = [i for i in range(len(bin_edges))]

        # obtain the linear index that corresponds to the global_max_interv
        global_max_lin_idx = 0
        for i,right_edge in enumerate(bin_edges):
            if global_max_interv < right_edge:
                global_max_lin_idx = i
                break

        # map intervals to linear scale
        pdatas_lin_intervs = []
        pdatas_lin_medians = []
        for intvs,med,ran in zip(pdatas_intervs,pdatas_medians,pdatas_ranges):
            lin_intvs,lin_med = cls.__linearize_data(intvs, med,
                                                            bin_edges)
            pdatas_lin_intervs.append(lin_intvs)
            pdatas_lin_medians.append(lin_med)

        # bin count distribution. to get intra-bin stats. One sub-list per bin
        # b_c_d = [[b0cnt:int, b1cnt, b2cnt...], [b0cnt, b1cnt...], ...]
        bin_count_distr = [[0]*(len(bin_edges)-1) for _ in pdatas_intervs]
        for i,(intv,med) in enumerate(zip(pdatas_lin_intervs,
                                          pdatas_lin_medians)):
            for l_idx in intv[0]:
                bin_count_distr[i][l_idx] += 1

        # Find the median of each bin
        bin_medians = [0] * (len(bin_edges)-1)
        bin_ranges = [None for _ in range(len(bin_edges)-1)]
        for n,nth_bin_counters in enumerate(zip(*bin_count_distr)):
            bin_medians[n] = median(nth_bin_counters)
            bin_ranges[n] = (min(nth_bin_counters), max(nth_bin_counters))


        #####################################
        ## PLOT HISTOGRAM
        # Plot the damn histogram (a bar plot actually, coz medians can be
        # decimals)
        X = [x-0.5 for x in lin_bin_edges[2:global_max_lin_idx+1]]
        X_labels = bin_edges[2:global_max_lin_idx+1]
        Y = bin_medians[1:global_max_lin_idx]

        bar_color = Palette.from_hsla((cls.hue+60,50,75,100))
        mpl_axes.bar(x=X, height=Y, width=0.95, zorder=3, color=bar_color)



        #####################################
        ## PLOT RANGES
        # make a 'I-shaped' range line in each histogram bin to show the range
        # of the instances that lead to this median-bin.
        Xran = [x-0.5 for x in lin_bin_edges[2:global_max_lin_idx+1]]
        Ymin = [y[0] for y in bin_ranges[1:global_max_lin_idx]]
        Ymax = [y[1] for y in bin_ranges[1:global_max_lin_idx]]
        range_color = '#888888'
        mpl_axes.vlines(x=Xran, ymin=Ymin, ymax=Ymax,
                        color=range_color, linewidth=1,
                        zorder=4,linestyle='solid')
        mpl_axes.scatter(x=Xran, y=Ymin, zorder=4, s=25, marker='_',
                         color=range_color)
        mpl_axes.scatter(x=Xran, y=Ymax, zorder=4, s=25, marker='_',
                         color=range_color)


        #####################################
        # SETUP PLOT VISUALS
        # set plot limits
        xlims = (1, max(1,global_max_interv))
        if len(Ymax) == 0:
            ymax = 1
        else:
            ymax = max(Ymax)
        ylims = (0, ymax)
        pads = ('auto', 'auto')
        cls.__setup_hist_limits_and_ticks(
            mpl_axes, metric_code=metric_code, xlims=xlims, ylims=ylims,
            xticks=lin_bin_edges, xticks_labels=bin_edges)

        # insert text box with average imbalance
        text = [f'Executions: {num_pdatas}']
        cls.draw_textbox(mpl_axes, text, metric_code)

        # set labels
        cls.setup_labels(mpl_axes, met_str)

        # title and bg color
        # 'white' because there is no possible bg plot for this boy
        cls.setup_general(mpl_axes, 'white', met_str)

        PlotFile.save(fig, metric_code, aggr=True)

        return
