import matplotlib.pyplot as plt
from itertools import zip_longest

from mapanalyzer.settings import Settings as st
from mapanalyzer.util import MetricStrings, Palette, PlotFile, sample_list
from mapanalyzer.ui import UI
from .base import BaseModule

class EvictionRoundtrip(BaseModule):
    hue = 135
    supported_metrics = {
        'BPA' : MetricStrings(
            about  = ('The Block-Personality that each Cache Set adopts.'),
            title  = 'Block Personality Adoption',
            subtit = '',
            number = '06',
            xlab   = 'Time [access instr.]',
            ylab   = 'Space [blocks]',
        ),
        'SMRI' : MetricStrings(
            about  = ('The time a block spends in main memory until it is '
                      'fetched back to cache.'),
            title  = 'Short Memory Roundtrip Interval',
            subtit = 'fewer is better',
            number = '07',
            xlab   = 'Time [access instr.]',
            ylab   = 'Space [blocks]',
        ),
        'MRID' : MetricStrings(
            about  = ('Histogram showing the memory roundtrip intervals '
                      'duration distribution.'),
            title  = 'Memory Roundtrip Interval Distribution',
            subtit = 'right-skewed is better',
            number = '08',
            xlab   = 'Rountrip duration [access instr.]',
            ylab   = 'Frequency',
        )
    }
    supported_aggr_metrics = {
        'MRID' : MetricStrings(
            about  = ('Average MRID.'),
            title  = 'Average MRI Distribution',
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
        # This map-of-maps stores the in-cache time duration of each block.
        # Take this map of maps as a compressed table where the block_id is the
        # concatenation of the block-tag and the set-id:
        # so:            ,------ set id
        #                |   ,-- block tag
        #                |   |
        # alive_intervals[3][47] -> [(time_in,t_out), (t_in,t_out), ...]
        #
        # In the example, block_id = '47 concat 3'
        self.alive_intervals = {}
        self.dead_intervals = {}

        # S lists with the personality switch history of each set. Each
        # change is a tuple set_idx -> [(time, old_block, new_block), ...]
        self.personalities = [[] for _ in range(st.Cache.num_sets)]

        # number of sets in the cache.
        self.num_sets = st.Cache.num_sets
        return

    def probe(self, time, set_idx, tag_in, tag_out):
        if not self.enabled:
            return

        # if a block is being fetched...
        if tag_in is not None:
            # Begin registration of in-Cache interval
            if set_idx not in self.alive_intervals:
                self.alive_intervals[set_idx] = {}
            if tag_in not in self.alive_intervals[set_idx]:
                self.alive_intervals[set_idx][tag_in] = []
            self.alive_intervals[set_idx][tag_in].append((time, None))

        # if a block is being evicted...
        if tag_out is not None:
            # Finish registration of in-Cache interval
            if set_idx in self.alive_intervals:
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
        for set_idx in self.alive_intervals.keys():
            for tag in self.alive_intervals[set_idx].keys():
                blk_intervals = self.alive_intervals[set_idx][tag]
                # if the block was alive only once, then there is no dead
                # interval.
                if len(blk_intervals) < 2:
                    continue

                # there is activity to register. Allocate memory
                if set_idx not in self.dead_intervals:
                    self.dead_intervals[set_idx] = {}
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
        plot_alive_intervals = {}
        # for each set that registers activity...
        for set_idx,blocks_intervals in sorted(self.alive_intervals.items()):
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

        plot_dead_intervals = {}
        # for each set that registers activity...
        for set_idx,blocks_intervals in sorted(self.dead_intervals.items()):
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
        sets_personalities = {}
        for set_idx,set_pers in enumerate(self.personalities):
            # three times long because of the 'start, end, None' triplets
            times = [0 for _ in range(len(set_pers)*3)]
            blocks = [0 for _ in range(len(set_pers)*3)]
            for i,(t,blk_old,blk_new) in enumerate(set_pers):
                ii = 3*i
                times[ii],times[ii+1],times[ii+2] = t-1, t, None
                blocks[ii],blocks[ii+1],blocks[ii+2] = blk_old, blk_new, None

            sets_personalities[set_idx] = {
                't' : times,
                'b' : blocks
            }
        self.personalities = sets_personalities
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
            self.alive_intervals = {int(s): dt
                                    for s,dt in data['alive_intervals'].items()}
            self.personalities = {int(s): dt
                                  for s,dt in data['personalities'].items()}
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
        set_to_color = {s:'' for s in range(self.num_sets)}
        pal = Palette(
            hue = len(set_to_color), h_off=self.hue,
            sat = st.Plot.p_sat,
            lig = (50, 0),
            alp = st.Plot.p_alp)
        for i,set_idx in enumerate(set_to_color):
            set_to_color[set_idx] = pal[i][0][0][0]

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
        jump_line_width = max(0.1, plt_w / (4*width_range))
        jump_line_alpha = 1
        jump_line_style = '-'


        #####################################
        ## PLOT METRIC
        mpl_fig = mpl_axes.figure
        plot_types = ('single', 'all')
        # save plots for each independent set, and one for all together
        for plot_type in plot_types:
            all_sets = sorted(self.alive_intervals.keys())
            for set_idx in all_sets:
                set_interv = self.alive_intervals[set_idx]
                set_person = self.personalities[set_idx]
                set_color = set_to_color[set_idx]

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
                if plot_type == 'single' or set_idx == all_sets[-1]:
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
            self.dead_intervals = {int(s): dt
                                   for s,dt in data['dead_intervals'].items()}
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
        set_to_color = {s:'' for s in range(self.num_sets)}
        pal = Palette(
            hue = len(set_to_color), h_off=self.hue,
            sat = (50, 0),
            lig = (50, 0),
            alp = (100, 0))
        for i,set_idx in enumerate(set_to_color):
            set_to_color[set_idx] = pal[i][0][0][0]

        # compute the width of block lines
        plt_w,plt_h = self.get_plot_xy_size(mpl_axes)
        height_range = st.Map.num_blocks
        if metric_code in st.Plot.y_ranges:
            ymin,ymax = st.Plot.y_ranges[metric_code]
            height_range = ymax - ymin
        block_line_width = plt_h / height_range
        block_line_alpha = 0.5
        block_line_style = '-'


        #####################################
        ## PLOT METRIC
        mpl_fig = mpl_axes.figure
        plot_types = ('single', 'all')
        # save plots for each independent set, and one for all together
        for plot_type in plot_types:
            all_sets = sorted(self.dead_intervals.keys())
            all_roundtrips_count = 0 # count of dead segments <= threshold.
            for set_idx in all_sets:
                set_intervs = self.dead_intervals[set_idx]
                blocks = set_intervs['bl']
                t_start = set_intervs['t0']
                t_end = set_intervs['t1']
                set_color = set_to_color[set_idx]
                roundtrips_count = len(blocks)

                # If a maximum threshold was given by the user, then filter
                # the intervals to only plot shorter ones.
                thrshld = st.Plot.roundtrip_threshold
                thrshld_text = '(all)'
                if thrshld is not None:
                    blocks,t_start,t_end = [],[],[]
                    for bl,t0,t1 in zip(set_intervs['bl'], set_intervs['t0'],
                                        set_intervs['t1']):
                        if t1-t0 <= thrshld:
                            blocks.append(bl)
                            t_start.append(t0)
                            t_end.append(t1)
                    roundtrips_count = len(blocks)
                    thrshld_text = rf' ($\leq${thrshld})'
                all_roundtrips_count += roundtrips_count

                # draw the horizontal lines
                mpl_axes.hlines(y=blocks, xmin=t_start, xmax=t_end,
                                color=set_color, linewidth=block_line_width,
                                alpha=block_line_alpha, zorder=2,
                                linestyle=block_line_style)


                ###########################################
                ## PLOT VISUALS
                # visuals for each "single" plot, or after the last of "all"
                if plot_type == 'single' or set_idx == all_sets[-1]:
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

                    # insert text box with total read/write count
                    if not bg_mode:
                        count = all_roundtrips_count
                        if plot_type == 'single':
                            count = roundtrips_count
                        text = (rf'SMRI count{thrshld_text} : {count}')
                        self.draw_textbox(mpl_axes, text, metric_code)

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
            self.dead_intervals = {int(s): dt
                                   for s,dt in data['dead_intervals'].items()}
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
            sat = (50,  90),
            lig = (75,  30),
            alp = (100, 90))
        for s in range(self.num_sets):
            hset_to_color[s] = pal[s][0][0][0]
            mset_to_color[s] = pal[s][1][1][1]

        #####################################
        ## CREATE DATA SERIES
        # obtain dead intervals and medians (per set) and max dead interval
        # (across all sets)
        all_dintervals, med_dintervals, max_dinterval = \
            self.__obtain_intervals(dead_intervals=self.dead_intervals,
                                    num_sets=self.num_sets)

        # define bin edges
        bin_edges = self.__create_bins(max_dinterval, exp=20)

        # map dead intervals and bin edges to a linear scale so the histogram
        # has even columns width
        lin_dintervals, lin_medians, lin_bin_edges, lin_max_bin_idx = \
            self.__linearize_data(all_dintervals, med_dintervals, bin_edges)


        #####################################
        ## PLOT HISTOGRAM AND MEDIANS
        hist_labels = [str(s) for s in range(self.num_sets)]
        counts,_,_ = mpl_axes.hist(
            lin_dintervals, stacked=True, zorder=3, width=0.95,
            bins=lin_bin_edges, label=hist_labels, color=hset_to_color)

        Y_max = max(max(i) if len(i) else 0 for i in counts)
        ylims = (0,Y_max)

        #####################################
        ## PLOT HISTOGRAM AND MEDIANS
        for med_x, med_col in zip(lin_medians, mset_to_color):
            mpl_axes.axvline(x=med_x, color=med_col, linestyle='-',
                             linewidth=3, zorder=4)


        #####################################
        # PLOT VISUALS
        # setup limits and tick-labels
        xlims = (1,max_dinterval)
        self.__setup_hist_limits_and_ticks(
            mpl_axes, metric_code=metric_code, xlims=xlims, ylims=ylims,
            xticks=lin_bin_edges, xticks_labels=bin_edges)

        # insert text box with medians
        text = []
        for s,s_med in enumerate(med_dintervals):
            text.append(f's{s} median {metric_code}: {s_med}')
        '\n'.join(text)
        # set default textbox to upper-right corner
        if metric_code not in st.Plot.textbox_offsets:
            st.Plot.textbox_offsets[metric_code] = (0.98, 0.98)
        self.draw_textbox(mpl_axes, text, metric_code)

        # set labels
        self.setup_labels(mpl_axes, met_str)

        # title and bg color
        self.setup_general(mpl_axes, pal.bg, met_str)

        return

    def __obtain_intervals(self, dead_intervals, num_sets):
        """
        Obtains list of intervals (per set), median (per set), and maximum
        (across all sets)
        """
        # all_dintervals[set] -> [di0:int, di1, di2, ...]
        all_dintervals = [None for _ in range(num_sets)]
        # med_dintervals[set] -> median:int
        med_dintervals = [None for _ in range(num_sets)]
        # longest dead interval across all sets
        max_dinterval = 0
        for set_idx,set_intrvs in sorted(dead_intervals.items()):
            # get plain intervals length for this set
            set_intervs = sorted(
                [t1-t0 for t0,t1 in zip(set_intrvs['t0'],set_intrvs['t1'])])
            all_dintervals[set_idx] = set_intervs

            # get median of this set
            med_idx = len(set_intervs) // 2
            if len(set_intervs) % 2 == 0:
                med = (set_intervs[med_idx] +
                       set_intervs[med_idx+1]) / 2
            else:
                med = set_intervs[med_idx]
            med_dintervals[set_idx] = med

            # update maximum dead interval across all sets
            max_dinterval = max(max_dinterval, set_intervs[-1])

        return all_dintervals, med_dintervals, max_dinterval

    def __create_bins(self, max_value, exp=20):
        """
        Create bins up to 2^exp in "half" exponential fashion:
        0, 1, 2, 3, 4, 6, 8, 12, 16, 24, 32, 48, 64....
        """
        bin_right_edges = [1] * (2 * exp + 1)
        for i in range(1, exp+1):
            bin_right_edges[2*i-1] = 2**i
            bin_right_edges[2*i] = 2**i + 2**(i-1)

        # if the rightmost edge is still too small, then create an extra bin to
        # fit the largest interval
        if bin_right_edges[-1] < max_value:
            bin_right_edges += [max_value+1]

        # add the left edge of the first bin.
        return [0] + bin_right_edges

    def __linearize_data(self, all_dintervals, med_dintervals, bin_edges):
        """
        Bins are of different width. So columns would be narrow on the left,
        and wide on the right. Normalize the histogram by creating a new
        dataset with a linear distribution.
        Map real dead-interval values (from bins of different sizes) to linear
        values (to bins of same width).
        """

        # linear counterpart of the original dataset.
        # linear_all_di[set] -> [ldi0:int, ldi1, ldi2, ...]
        linear_all_dintervals = [[0]*len(set_di) for set_di in all_dintervals]
        # max bin index actually used
        max_bin_idx_used = 0

        for s,set_dinterv in enumerate(all_dintervals):
            # current bin being used
            curr_bin_idx = 0
            # map all original data to the linear dataset
            for i,dint in enumerate(set_dinterv):
                # find the correct bin for this dead interval (dint)
                # (yes, this assumes set_dinterv is sorted, and it is.)
                while dint >= bin_edges[curr_bin_idx]:
                    curr_bin_idx += 1
                # add data-point to linear dataset.
                linear_all_dintervals[s][i] = curr_bin_idx-1

            # update the last actually used bin
            max_bin_idx_used = max(max_bin_idx_used, curr_bin_idx)

        # linear counterpart of original bin_edges
        linear_bin_edges = [i for i in range(len(bin_edges))]


        # map medians to values in the linear scale
        linear_medians = [0 for _ in med_dintervals]
        for s,s_med_di in enumerate(med_dintervals):
            curr_bin_idx = 0
                # find the correct bin for this dead interval (dint)
            while bin_edges[curr_bin_idx] < s_med_di:
                curr_bin_idx += 1
            # integer and fractional parts
            lmed_int = curr_bin_idx - 1
            lmed_frac = (s_med_di - bin_edges[curr_bin_idx-1]) / \
                (bin_edges[curr_bin_idx] - bin_edges[curr_bin_idx-1])
            linear_medians[s] = lmed_int + lmed_frac

        return linear_all_dintervals, linear_medians, linear_bin_edges, \
            max_bin_idx_used

    def __setup_hist_limits_and_ticks(self, mpl_axes, metric_code, xlims, ylims,
                                      xticks, xticks_labels):
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

        return

