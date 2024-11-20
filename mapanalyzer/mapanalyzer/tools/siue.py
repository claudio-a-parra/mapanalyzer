import sys
import matplotlib.pyplot as plt
from matplotlib.colors import ListedColormap
import numpy as np


from mapanalyzer.util import create_up_to_n_ticks, PlotStrings, save_fig, Dbg, Palette, AddrFmt
from mapanalyzer.settings import Settings as st
from mapanalyzer.util import sub_resolution_between

class SIUEviction:
    def __init__(self, shared_X=None, hue=220):
        self.tool_name = 'SIU Evictions'
        self.tool_about = ('Detects blocks that are evicted and fetched back in a short time.')

        self.ps = PlotStrings(
            title  = 'SIUE',
            code = 'SIUE',
            xlab   = 'Time [access instr.]',
            ylab   = 'Memory Blocks',
            suffix = '_plot-07-siu-evictions',
            subtit = 'longer is better'
        )
        self.ps_h = PlotStrings(
            title  = 'SIUE-H',
            code = 'SIUE-H',
            xlab   = 'Time to Re-Fetch [access instr.]',
            ylab   = 'Frequency',
            suffix = '_plot-07-siu-evictions-hist',
            subtit = 'right-skewed is better'
        )
        self.enabled = self.ps.code in st.plot.include or self.ps_h.code in st.plot.include
        if not self.enabled:
            return

        self.X = shared_X if shared_X is not None else \
            [i for i in range(st.map.time_size)]

        self.tool_palette = Palette(hue=hue,
                                    hue_count=st.cache.num_sets,
                                    # [main bars, alive blocks, average time-to-refetch]
                                    lightness= [60, 75, 50],
                                    saturation=[50, 75, 90],
                                    alpha=     [90, 30, 100])

        # map with the currently cached blocks and the time they were cached.
        # Used to recollect time_in when a block is evicted, so the interval of time it
        # spent in cache can be reconstructed.
        # tag -> time_in
        self.cached_blocks = {}

        # This map-of-maps stores the in-RAM time of each block.
        # Take this map of maps as a compressed table where the block_id is the concatenation of
        # the block-tag and the set-id:
        # so:
        #                   ,------ set id
        #                   |   ,-- block tag
        #                   |   |
        #    dead_intervals[3][47] -> [(time_out,time_in), (time_out,time_in), ...]
        #
        # In the example, block_id = '47 concat 3'
        self.dead_intervals = {}

        # block access matrix. rows: blocks. cols: time.
        map_mat_rows = sub_resolution_between(st.map.num_padded_bytes // st.cache.line_size,
                                              st.plot.min_res, st.plot.max_res)
        map_mat_cols = sub_resolution_between(st.map.time_size,
                                              st.plot.min_res, st.plot.max_res)

        # matrix of blocks at all times. -1 means block not alive.
        self.block_access_matrix = [[-1] * map_mat_cols for _ in range(map_mat_rows)]
        # to setup the size of the matrix on the plot
        self.mat_extent = [0,0,0,0]

        return


    # update the block access matrix
    def update_bam(self, set_idx, tag, time_in, time_out):
        block = (tag << st.cache.bits_set) | set_idx
        # map the block to the X-axis of the block_access_matrix
        # (of potentially smaller resolution)
        max_real_block = max(1, st.map.num_blocks - 1)
        proportional_block = block / max_real_block
        max_mapped_block = len(self.block_access_matrix) - 1
        mapped_block = round(proportional_block * max_mapped_block)

        # map both, time_in and _out to the Y-axis of the block_access_matrix
        # (of potentially smaller resolution)
        max_real_time = st.map.time_size - 1
        proportional_time_in = time_in / max_real_time
        proportional_time_out = time_out / max_real_time
        max_mapped_time = len(self.block_access_matrix[0]) - 1
        mapped_time_in = round(proportional_time_in * max_mapped_time)
        mapped_time_out = round(proportional_time_out * max_mapped_time)

        # store the time-alive of the block in the block_access_matrix
        for mt in range(mapped_time_in, mapped_time_out+1):
            self.block_access_matrix[mapped_block][mt] = set_idx
        return

    def update(self, time, set_idx, tag_in, tag_out):
        if not self.enabled:
            return
        # if a block is being evicted...
        if tag_out is not None:
            # recall its time_in, and register its living time in the Block Access Matrix (bam)
            time_in = self.cached_blocks[(tag_out,set_idx)]
            del self.cached_blocks[(tag_out,set_idx)] # block not in cache anymore
            time_out = time - 1
            self.update_bam(set_idx, tag_out, time_in, time_out)

            # A block is dying! register the beginning of its in-RAM time.
            # If this set/tag has not been involved so far, create a map/list for it
            if set_idx not in self.dead_intervals:
                self.dead_intervals[set_idx] = {}
            if tag_out not in self.dead_intervals[set_idx]:
                self.dead_intervals[set_idx][tag_out] = []

            # now register this block's  time of death (with a -1 placeholder for its future rebirth
            # on a potential upcoming fetch)
            self.dead_intervals[set_idx][tag_out].append((time_out,-1))

        # if a block is being fetched...
        if tag_in is not None:
            # register its time_in in the cached_blocks.
            self.cached_blocks[(tag_in,set_idx)] = time

            # a block is coming to life! this may be the revival of a dead block, if so,
            # update its rebirth time
            if set_idx in self.dead_intervals:
                if tag_in in self.dead_intervals[set_idx]:
                    block_death_time = self.dead_intervals[set_idx][tag_in][-1][0]
                    block_rebirth_time = time-1
                    self.dead_intervals[set_idx][tag_in][-1] = (block_death_time, block_rebirth_time)
            # else:
            #     the block has never been evicted before, this is just its first fetch.
        return

    def commit(self, time):
        if not self.enabled:
            return
        # this tool doesn't need to do anything at the end of each time step.
        return

    def describe(self, ind=''):
        if not self.enabled:
            return
        print(f'{ind}{self.tool_name:{st.plot.ui_toolname_hpad}}: {self.tool_about}')
        return

    def plot_setup_X(self):
        # Data range based on data
        X_padding = 0.5
        # add tails at start/end of X for cosmetic purposes
        self.axes.set_xlim(self.X[0]-X_padding, self.X[-1]+X_padding)
        # set the left/right (0,1) locations of the block_access_matrix in the plot
        self.mat_extent[0],self.mat_extent[1] = self.X[0]-X_padding, self.X[-1]+X_padding

        # Axis details: label, ticks and grid
        self.axes.set_xlabel(self.ps.xlab)
        rot = -90 if st.plot.x_orient == 'v' else 0
        self.axes.tick_params(axis='x',
                              top=False, bottom=True,
                              labeltop=False, labelbottom=True,
                              rotation=rot, width=st.plot.grid_other_width)
        x_ticks = create_up_to_n_ticks(self.X, base=10,
                                       n=st.plot.max_xtick_count)
        self.axes.set_xticks(x_ticks)
        # self.axes.grid(axis='x', which='both',
        #           zorder=1,
        #           alpha=st.plot.grid_main_alpha,
        #           linestyle=st.plot.grid_other_style,
        #           linewidth=st.plot.grid_other_width)
        return

    def plot_setup_Y(self):
        # define Y-axis data based on data and user input
        Y_min = 0
        Y_max = st.map.num_blocks-1
        if self.ps.code in st.plot.y_ranges:
            Y_min = int(st.plot.y_ranges[self.ps.code][0])
            Y_max = int(st.plot.y_ranges[self.ps.code][1])
        Y_padding = 0.5
        self.axes.set_ylim(Y_min-Y_padding, Y_max+Y_padding)
        # set the bottom/top (2,3) locations of the block_access_matrix in the plot
        self.mat_extent[2],self.mat_extent[3] = Y_min-Y_padding, Y_max+Y_padding

        # Axis details: label, ticks, and grid
        self.axes.set_ylabel(self.ps.ylab)
        self.axes.tick_params(axis='y',
                              left=True, right=False,
                              labelleft=True, labelright=False,
                              width=st.plot.grid_main_width)
        y_ticks = create_up_to_n_ticks(range(Y_min,Y_max+1), base=10,
                                       n=st.plot.max_ytick_count)
        self.axes.set_yticks(y_ticks)
        # self.axes.grid(axis='y', which='both',
        #                zorder=1,
        #                alpha=st.plot.grid_main_alpha,
        #                linewidth=st.plot.grid_main_width,
        #                linestyle=st.plot.grid_main_style)
        # invert Y axis direction
        self.axes.invert_yaxis()
        return

    def plot_setup_general(self, title=None, variant=None, subtit=None):
        # background color
        self.axes.patch.set_facecolor(self.tool_palette.bg)

        # setup title bits
        title_string = st.plot.prefix
        if title:
            title_string = f'{title}: {title_string}'
        if variant:
            title_string = f'{title_string}. {variant}'
        if subtit:
            title_string = f'{title_string}. ({subtit})'

        self.axes.set_title(title_string, fontsize=10, pad=st.plot.img_title_vpad)
        return

    def plot(self, bottom_tool=None):
        if not self.enabled:
            return

        # create two set of axes: for the map (bottom) and the tool
        fig,bottom_axes = plt.subplots(figsize=(st.plot.width, st.plot.height))
        self.axes = fig.add_axes(bottom_axes.get_position())

        # plot map
        if bottom_tool is not None:
            bottom_tool.plot(axes=bottom_axes)

        # setup axes
        self.plot_setup_X()
        self.plot_setup_Y()
        self.plot_setup_general(title=self.ps.title,
                                variant=f'All Sets {st.cache.asso}-way',
                                subtit=self.ps.subtit)

        # set_idx -> plot parameters for all the dead intervals of blocks in this set.
        dead_intervals_per_set = {}

        # collect the parameters to plot the dead_intervals of each block.
        for s in range(st.cache.num_sets):
            if s in self.dead_intervals:
                s_color = self.tool_palette[s][0]
                s_dead_intervals = self.dead_intervals[s]
                s_all_block_ids = []
                s_all_evictions = []
                s_all_fetches = []
                s_all_idx = 0

                # iterate over all the (tag,t_dead_in_out) pairs under this set.
                for s_tag, s_tag_evictfetch_list in sorted(s_dead_intervals.items()):
                    # iterate over every (out,in) pair in the history of a single tag
                    for (s_t_evict_time,s_t_fetch_time) in s_tag_evictfetch_list:
                        if s_t_fetch_time == -1:
                            continue
                        s_all_block_ids.append((s_tag << st.cache.bits_set) | s)
                        s_all_evictions.append(s_t_evict_time+0.5)
                        s_all_fetches.append(s_t_fetch_time+0.5)

                dead_intervals_per_set[s] = {
                    'y': s_all_block_ids,
                    'x0': s_all_evictions,
                    'x1': s_all_fetches,
                    'col': s_color
                }



        ##############################################################
        # PLOT SIU EVICTIONS OF ALL SETS IN ONE IMAGE
        # [0] : block not alive
        # [n] : Set-(n-1) makes block alive.
        color_map_list = ['#FFFFFF00'] + [self.tool_palette[i][1] for i in range(st.cache.num_sets)]
        # define color map
        cmap = ListedColormap(color_map_list)

        # draw all blocks
        self.axes.imshow(self.block_access_matrix, cmap=cmap, origin='lower',
                         interpolation='none',
                         aspect='auto', zorder=2, extent=self.mat_extent,
                         vmin=-1, vmax=st.cache.num_sets-1)
        # draw all dead_intervals
        for s,di in sorted(dead_intervals_per_set.items()):
            self.axes.hlines(y=di['y'], color=di['col'],
                             xmin=di['x0'], xmax=di['x1'],
                             linewidth=st.plot.dead_line_width,
                             alpha=1, zorder=2, linestyle='-')
        # save image
        save_fig(fig, f'{self.ps.title} all', f'{self.ps.suffix}-all')



        ##############################################################
        # PLOT SIU EVICTIONS OF EACH SET IN A DIFFERENT IMAGE
        #
        # List with S sub-lists.
        # Each sub-list is all the intervals of dead blocks that corresponds to that set.
        # This list is used for the histogram.
        all_dead_intervals = [[] for _ in range(st.cache.num_sets)]
        for s in range(st.cache.num_sets):
            # create two set of axes: for the map (bottom) and the tool
            fig,bottom_axes = plt.subplots(figsize=(st.plot.width, st.plot.height))
            self.axes = fig.add_axes(bottom_axes.get_position())

            # plot map
            if bottom_tool is not None:
                bottom_tool.plot(axes=bottom_axes)

            # setup axes
            self.plot_setup_X()
            self.plot_setup_Y()
            self.plot_setup_general(title=self.ps.title,
                                    variant=f'S{s} {st.cache.asso}-way',
                                    subtit=self.ps.subtit)

            # set all colors white but this set (which is s+1, coz 0 is blank)
            set_color_map_list = ['#FFFFFF00'] * (len(color_map_list))
            set_color_map_list[s+1] = color_map_list[s+1]
            # define color map
            cmap = ListedColormap(set_color_map_list)

            # draw blocks
            self.axes.imshow(self.block_access_matrix, cmap=cmap, origin='lower',
                             interpolation='none',
                             aspect='auto', zorder=2, extent=self.mat_extent,
                             vmin=-1, vmax=st.cache.num_sets-1)

            # draw dead intervals
            if s in dead_intervals_per_set:
                di = dead_intervals_per_set[s]
                self.axes.hlines(y=di['y'], color=di['col'],
                                 xmin=di['x0'], xmax=di['x1'],
                                 linewidth=st.plot.dead_line_width,
                                 alpha=1, zorder=2, linestyle='-')
                # compute intervals for histogram
                all_dead_intervals[s].extend([f-e for e,f in zip(di['x0'], di['x1'])])

            # save image
            save_fig(fig, f'{self.ps.title} s{s:02}', f'{self.ps.suffix}-s{s:02}')


        ##############################################################
        # PLOT HISTOGRAM OF SIU EVICTIONS OF ALL SETS IN ONE IMAGE
        # create a set of axes for the histogram
        fig,self.axes = plt.subplots(figsize=(st.plot.width, st.plot.height))

        # define the labels and colors for each set in the histogram
        hist_labels = [str(s) for s in range(st.cache.num_sets)]
        hist_colors = [self.tool_palette[i][0] for i in range(st.cache.num_sets)]

        # Prepare data for histogram plotting:
        #   max_dead_interval : this value +1 is the right edge of the rightmost bin.
        #   avg_dead_interval : array with the avg dead_interval per Set.
        max_dead_interval = 0
        avg_dead_intervals = [0 for _ in range(st.cache.num_sets)]
        for i,set_d_intr in enumerate(all_dead_intervals):
            if len(set_d_intr) > 0:
                avg_dead_intervals[i] = sum(set_d_intr)/len(set_d_intr)
                max_dead_this_set = max(set_d_intr)
                if max_dead_interval < max_dead_this_set:
                    max_dead_interval = max_dead_this_set

        # Create bins for histogram plotting (bin_edges)
        #   Create bins up to 2^b in "half" exponential fashion:
        #   0, 1, 2, 3, 4, 6, 8, 12, 16, 24, 32, 48, 64....
        b = 20
        bin_right_edges = [1] * (2*b+1)
        for i in range(1,b+1):
            bin_right_edges[2*i-1] = 2**i
            bin_right_edges[2*i] = 2**i + 2**(i-1)

        #   If the max_dead_interval is greater than 2^14+2^13, then create a last
        #   bin at the end so that all the info is contained in some bin.
        if bin_right_edges[-1] < max_dead_interval:
            bin_right_edges += [max_dead_interval+1]
        bin_edges = [0] + bin_right_edges


        # [!] Bins are of different width. So columns would be narrow on the left, and wide
        # on the right. Normalize the histogram by creating a new dataset with a linear
        # distribution.
        # Map real dead_time values (from bins of different sizes) to linear values (to bins
        # of same width)
        for s in all_dead_intervals:
            s.sort()
        lin_all_dead_intervals = [[0] * len(sdi) for sdi in all_dead_intervals]
        max_bin_idx_used = 0
        for s,sdi in enumerate(all_dead_intervals):
            bin_idx = 0
            for sdi_idx,d in enumerate(sdi):
                while d >= bin_edges[bin_idx]:
                    bin_idx += 1
                lin_all_dead_intervals[s][sdi_idx] = bin_idx-1
            # determine the last used bin to trim the right side of the histogram
            if bin_idx > max_bin_idx_used:
                max_bin_idx_used = bin_idx

        # Define the linear edges used by the histogram
        lin_bin_edges = [i for i in range(len(bin_edges))]

        # Plot histogram
        counts, _, _ = self.axes.hist(lin_all_dead_intervals, stacked=True, zorder=3,
                                      width=0.975, # leave gap between bars
                                      bins=lin_bin_edges,
                                      label=hist_labels,
                                      color=hist_colors)

        # map averages to linear values within each bin.
        lin_avg_dead_intervals = [0 for _ in avg_dead_intervals]
        for s,s_avg_di in enumerate(avg_dead_intervals):
            be_idx = 0
            while bin_edges[be_idx] < s_avg_di:
                be_idx += 1
            s_lin_avg_int = be_idx - 1
            s_lin_ang_frac = (s_avg_di - bin_edges[be_idx-1])/(bin_edges[be_idx] - bin_edges[be_idx-1])
            lin_avg_dead_intervals[s] = s_lin_avg_int + s_lin_ang_frac

        # Plot averages
        avg_hist_colors = [self.tool_palette[i][2] for i in range(st.cache.num_sets)]
        for l_s_avg,s_avg_col in zip(lin_avg_dead_intervals, avg_hist_colors):
            self.axes.axvline(x=l_s_avg, color='#000000CC', linestyle='solid', linewidth=1.5, zorder=3)
            self.axes.axvline(x=l_s_avg, color=s_avg_col, linestyle='solid', linewidth=1, zorder=3)

        # configure axes
        self.plot_setup_axes_for_hist(
            y_auto_max=max(max(i) if len(i) else 0 for i in counts),
            x_max_bin_edge=max_bin_idx_used,
            x_ticks=lin_bin_edges,
            x_ticks_labels=bin_edges

        )
        self.plot_setup_general(title=self.ps_h.title,
                                subtit=self.ps_h.subtit)

        # save image
        save_fig(fig, self.ps_h.title, self.ps_h.suffix)
        return


    def plot_setup_axes_for_hist(self, y_auto_max, x_max_bin_edge, x_ticks, x_ticks_labels):
        # bring spines to top:
        for spine in self.axes.spines.values():
            spine.set_zorder(4)

        # X-AXIS
        X_min = 1
        X_max = x_ticks[x_max_bin_edge] #round(x_ticks[-1])
        if self.ps_h.code in st.plot.x_ranges:
            # pick the index corresponding to the greatest
            # minX that is <= given_min
            given_min = int(st.plot.x_ranges[self.ps_h.code][0])
            for minX_idx,minX in zip(x_ticks,x_ticks_labels):
                if minX <= given_min:
                    X_min = minX_idx
                else:
                    break
            # pick the index corresponding to the smallest
            # maxX that is >= given_max
            given_max = int(st.plot.x_ranges[self.ps_h.code][1])
            for maxX_idx,maxX in reversed(list(zip(x_ticks,x_ticks_labels))):
                if maxX >= given_max:
                    X_max = maxX_idx
                else:
                    break

        # X_min must be >= 1
        if X_min < 1:
            X_min = 1
        # make sure there is at least a dummy range
        if X_min == X_max:
            X_max = X_min + 1
        X_padding = (X_max-X_min)/200
        self.axes.set_xlim(X_min-X_padding, X_max+X_padding)

        # Axis details: label, ticks, and grid
        self.axes.set_xticks(x_ticks[X_min:X_max+1])
        self.axes.set_xticklabels(x_ticks_labels[X_min:X_max+1])
        self.axes.set_xlabel(self.ps_h.xlab)
        rot = -90 if st.plot.x_orient == 'v' else 0
        self.axes.tick_params(axis='x',
                              bottom=True, top=False,
                              labelbottom=True, labeltop=False,
                              rotation=rot, width=st.plot.grid_main_width)

        # Y-AXIS
        Y_min = 0
        Y_max = round(y_auto_max)
        if self.ps_h.code in st.plot.y_ranges:
            Y_min = int(st.plot.y_ranges[self.ps_h.code][0])
            Y_max = int(st.plot.y_ranges[self.ps_h.code][1])

        if Y_min == Y_max:
            Y_max = Y_min + 1
        Y_padding = (Y_max-Y_min)/200
        self.axes.set_ylim(Y_min-Y_padding, Y_max+5*Y_padding) # extra room on top

        # Axis details: label, ticks, and grid
        self.axes.set_ylabel(self.ps_h.ylab)
        self.axes.tick_params(axis='y',
                              left=True, right=False,
                              labelleft=True, labelright=False,
                              width=st.plot.grid_main_width)
        y_ticks = create_up_to_n_ticks(range(Y_min,round(Y_max+5*Y_padding)+1), base=10,
                                       n=st.plot.max_ytick_count)
        self.axes.set_yticks(y_ticks)
        self.axes.grid(axis='y', which='both',
                       zorder=1,
                       alpha=st.plot.grid_main_alpha,
                       linewidth=st.plot.grid_main_width,
                       linestyle=st.plot.grid_main_style)
        return
