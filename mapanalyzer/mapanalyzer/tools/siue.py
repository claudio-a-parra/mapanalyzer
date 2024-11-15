import sys
import matplotlib.pyplot as plt
from matplotlib.colors import ListedColormap


from mapanalyzer.util import create_up_to_n_ticks, PlotStrings, save_fig, Dbg, Palette, AddrFmt
from mapanalyzer.settings import Settings as st
from mapanalyzer.util import sub_resolution_between

class SIUEviction:
    def __init__(self, shared_X=None, hue=220):
        self.name = 'SIU Evictions'
        self.plotcode = 'SIU'
        self.enabled = self.plotcode in st.plot.include
        if not self.enabled:
            return
        self.about = ('Detects blocks that are evicted and fetched back in a short time.')

        self.ps = PlotStrings(
            title  = 'SIU',
            xlab   = 'Time [access instr.]',
            ylab   = 'Memory Blocks',
            suffix = '_plot-07-siu-evictions',
            subtit = 'longer is better')

        self.X = shared_X if shared_X is not None else \
            [i for i in range(st.map.time_size)]

        self.tool_palette = Palette(hue=hue,
                                    hue_count=st.cache.num_sets,
                                    lightness=st.plot.pal_lig,
                                    saturation=st.plot.pal_sat,
                                    alpha=[100,20])#st.plot.pal_alp)

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
        print(f'{ind}{self.name:{st.plot.ui_toolname_hpad}}: {self.about}')
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
        if self.plotcode in st.plot.y_ranges:
            Y_min = int(st.plot.y_ranges[self.plotcode][0])
            Y_max = int(st.plot.y_ranges[self.plotcode][1])
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

    def plot_setup_general(self, variant='', subtit=None):
        # background color
        self.axes.patch.set_facecolor(self.tool_palette.bg)
        # setup title
        if variant != '':
            variant = f'. {variant}'
        title_string = f'{self.ps.title}{variant}: {st.plot.prefix}'
        if subtit:
            title_string += f'. ({subtit})'
        elif self.ps.subtit:
            title_string += f'. ({self.ps.subtit})'
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
        self.plot_setup_general(variant=f'All Sets {st.cache.asso}-way')

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
        save_fig(fig, f'{self.plotcode} all', f'{self.ps.suffix}-all')

        # list with S sub-lists.
        # Each sub-list is all the intervals of dead blocks that corresponds to that set.
        # This list is used for the histogram.
        all_dead_intervals = [[] for _ in range(st.cache.num_sets)]


        # PLOT SIU EVICTIONS OF EACH SET IN A DIFFERENT IMAGE
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
            self.plot_setup_general(variant=f'S{s} {st.cache.asso}-way')

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
            save_fig(fig, f'{self.plotcode} s{s:02}', f'{self.ps.suffix}-s{s:02}')


        # PLOT HISTOGRAM OF SIU EVICTIONS OF ALL SETS IN ONE IMAGE
        # create a set of axes for the histogram
        fig,self.axes = plt.subplots(figsize=(st.plot.width, st.plot.height))
        hist_labels = [str(s) for s in range(st.cache.num_sets)]
        hist_colors = [self.tool_palette[i][0] for i in range(st.cache.num_sets)]
        counts, bin_edges, patches = self.axes.hist(all_dead_intervals,
                                                    stacked=True, zorder=3,
                                                    bins=st.plot.hist_bins,
                                                    label=hist_labels, color=hist_colors)
        # configure axes
        max_count = max(sum(counts))
        self.plot_setup_axes_for_hist(max_count, bin_edges[-1])
        self.plot_setup_general(variant=f'Time to re-fetch', subtit='Right-skewed is better')

        # save image
        save_fig(fig, f'{self.plotcode} hist', f'{self.ps.suffix}-hist')
        return


    def plot_setup_axes_for_hist(self, max_count, max_bin):
        # X-AXIS
        X_min = 1
        X_max = round(max_bin+0.5)
        if st.plot.hist_max != 'auto':
            X_max = st.plot.hist_max
        X_padding = 0.5
        self.axes.set_xlim(X_min-X_padding, X_max+X_padding)

        # Axis details: label, ticks, and grid
        self.axes.set_xlabel('Time to re-fetch')
        self.axes.tick_params(axis='x',
                              bottom=True, top=False,
                              labelbottom=True, labeltop=False,
                              width=st.plot.grid_main_width)
        x_ticks = create_up_to_n_ticks(range(X_min, X_max+1), base=10,
                                       n=st.plot.max_xtick_count)
        self.axes.set_xticks(x_ticks)

        # Y-AXIS
        Y_min = 0
        Y_max = round(max_count+0.5)
        Y_padding = 0.5
        self.axes.set_ylim(Y_min-Y_padding, Y_max+Y_padding)

        # Axis details: label, ticks, and grid
        self.axes.set_ylabel('Frequency')
        self.axes.tick_params(axis='y',
                              left=True, right=False,
                              labelleft=True, labelright=False,
                              width=st.plot.grid_main_width)
        y_ticks = create_up_to_n_ticks(range(Y_min,Y_max+1), base=10,
                                       n=st.plot.max_ytick_count)
        self.axes.set_yticks(y_ticks)
        self.axes.grid(axis='y', which='both',
                       zorder=1,
                       alpha=st.plot.grid_main_alpha,
                       linewidth=st.plot.grid_main_width,
                       linestyle=st.plot.grid_main_style)
        return
