import sys
import matplotlib.pyplot as plt
from matplotlib.colors import ListedColormap
import numpy as np


from mapanalyzer.util import create_up_to_n_ticks, PlotStrings, save_fig, Palette, AddrFmt
from mapanalyzer.settings import Settings as st
from mapanalyzer.util import sub_resolution_between

class EvictionDuration:
    def __init__(self, shared_X=None, hue=220):
        self.tool_name = 'Eviction Duration'
        self.tool_about = ('Detects blocks that are evicted and fetched back in a short time.')

        self.ps_e = PlotStrings(
            title  = 'ED',
            code = 'ED',
            xlab   = 'Time [access instr.]',
            ylab   = 'Memory Blocks',
            suffix = '_plot-07-eviction-duration',
            subtit = 'longer is better'
        )
        self.ps_p = PlotStrings(
            title  = 'BPA',
            code   = 'BPA',
            xlab   = 'Time [access instr.]',
            ylab   = 'Memory Blocks',
            suffix = '_plot-08-personality',
            subtit = ''
        )
        self.ps_h = PlotStrings(
            title  = 'EDH',
            code = 'EDH',
            xlab   = 'Time to Re-Fetch [access instr.]',
            ylab   = 'Frequency',
            suffix = '_plot-09-eviction-duration-hist',
            subtit = 'right-skewed is better'
        )
        self.enabled = self.ps_e.code in st.plot.include or \
            self.ps_h.code in st.plot.include or \
            self.ps_p.code in st.plot.include
        if not self.enabled:
            return

        self.X = shared_X if shared_X is not None else \
            [i for i in range(st.map.time_size)]
        self.hue = hue
        self.tool_palette = Palette(hue=hue,
                                    hue_count=st.cache.num_sets,
                                    # [main bars, alive blocks, average time-to-refetch]
                                    lightness= [60, 75, 50],
                                    saturation=[50, 75, 90],
                                    alpha=     [90, 30, 100])


        # This map-of-maps stores the in-RAM and in-cache time duration of each block.
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
        self.alive_intervals = {}

        # S lists with the personality change history of each set. Each change is a tuple
        # set_idx -> [(time, old_block, new_block), ...]
        self.sets_personalities = [[] for _ in range(st.cache.num_sets)]

        return

    def update(self, time, set_idx, tag_in, tag_out):
        if not self.enabled:
            return

        # if a block is being evicted...
        if tag_out is not None:
            # Finish registration of in-Cache duration
            if set_idx in self.alive_intervals:
                if tag_out in self.alive_intervals[set_idx]:
                    fetch_time = self.alive_intervals[set_idx][tag_out][-1][0]
                    evict_time = time - 1
                    self.alive_intervals[set_idx][tag_out][-1] = (fetch_time,evict_time)

            # Begin registration of in-RAM duration
            if set_idx not in self.dead_intervals:
                self.dead_intervals[set_idx] = {}
            if tag_out not in self.dead_intervals[set_idx]:
                self.dead_intervals[set_idx][tag_out] = []
            self.dead_intervals[set_idx][tag_out].append((time-1, None))

        # if a block is being fetched...
        if tag_in is not None:
            # Begin registration of in-Cache duration
            if set_idx not in self.alive_intervals:
                self.alive_intervals[set_idx] = {}
            if tag_in not in self.alive_intervals[set_idx]:
                self.alive_intervals[set_idx][tag_in] = []
            self.alive_intervals[set_idx][tag_in].append((time-1, None))

            # Finish registration of in-RAM duration
            if set_idx in self.dead_intervals:
                if tag_in in self.dead_intervals[set_idx]:
                    evict_time = self.dead_intervals[set_idx][tag_in][-1][0]
                    refetch_time = time - 1
                    self.dead_intervals[set_idx][tag_in][-1] = (evict_time,refetch_time)

        # if one block is evicted and the other fetched...
        if tag_in is not None and tag_out is not None:
            # register change of personality
            block_in_id = (tag_in  << st.cache.bits_set) | set_idx
            block_out_id = (tag_out  << st.cache.bits_set) | set_idx
            self.sets_personalities[set_idx].append((time-1,block_out_id,block_in_id))

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

    def plot_setup_X(self, ps):
        # Data range based on data
        X_padding = 0.5
        # add tails at start/end of X for cosmetic purposes
        self.axes.set_xlim(self.X[0]-X_padding, self.X[-1]+X_padding)

        # Axis details: label, ticks and grid
        self.axes.set_xlabel(ps.xlab)
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

    def plot_setup_Y(self, ps):
        # define Y-axis data based on data and user input
        Y_min = 0
        Y_max = st.map.num_blocks-1
        if ps.code in st.plot.y_ranges:
            Y_min = int(st.plot.y_ranges[ps.code][0])
            Y_max = int(st.plot.y_ranges[ps.code][1])
        Y_padding = 0.5
        self.axes.set_ylim(Y_min-Y_padding, Y_max+Y_padding)

        # Axis details: label, ticks, and grid
        self.axes.set_ylabel(ps.ylab)
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
        self.axes.patch.set_facecolor(Palette(hue=self.hue).bg)

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

        # collect the parameters to plot the dead_intervals of each block.
        dead_intervals_per_set = {}
        dead_palette = Palette(hue=self.hue, hue_count=st.cache.num_sets,
                               lightness=[60], saturation=[50], alpha=[90])
        for s in range(st.cache.num_sets):
            if s in self.dead_intervals:
                s_color = dead_palette[s][0]
                s_dead_intervals = self.dead_intervals[s]
                s_all_block_ids,s_all_evictions,s_all_fetches = [],[],[]
                s_all_idx = 0

                # iterate over all the (tag,t_ram_in_out) pairs under this set.
                for s_tag, s_tag_evictfetch_list in sorted(s_dead_intervals.items()):
                    # iterate over every (out,in) pair in the history of a single tag
                    for (s_t_evict_time,s_t_fetch_time) in s_tag_evictfetch_list:
                        if s_t_fetch_time == None:
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

        # collect the parameters to plot the alive_intervals of each block.
        alive_intervals_per_set = {}
        alive_palette = Palette(hue=self.hue, hue_count=st.cache.num_sets,
                                lightness=[75], saturation=[75], alpha=[30])
        for s in range(st.cache.num_sets):
            if s in self.alive_intervals:
                s_color = alive_palette[s][0]
                s_alive_intervals = self.alive_intervals[s]
                s_all_block_ids,s_all_fetches,s_all_evictions = [],[],[]
                s_all_idx = 0

                # iterate over all the (tag,t_cache_in_out) pairs under this set.
                for s_tag, s_tag_fetchevict_list in sorted(s_alive_intervals.items()):
                    # iterate over every (in,out) pair in the history of a single tag
                    for (s_t_fetch_time,s_t_evict_time) in s_tag_fetchevict_list:
                        if s_t_evict_time == None:
                            continue
                        s_all_block_ids.append((s_tag << st.cache.bits_set) | s)
                        s_all_fetches.append(s_t_fetch_time+0.5)
                        s_all_evictions.append(s_t_evict_time+0.5)

                alive_intervals_per_set[s] = {
                    'y': s_all_block_ids,
                    'x0': s_all_fetches,
                    'x1': s_all_evictions,
                    'col': s_color
                }

        # collect the parameters to plot the jumps of each set.
        personalities_per_set = {} # set_idx -> plot parameters for all the jumps made by that set on its blocks
        perso_palette = Palette(hue=self.hue, hue_count=st.cache.num_sets,
                                #lightness=[80], saturation=[75], alpha=[30])
                                lightness=[60], saturation=[50], alpha=[90])
        for s in range(st.cache.num_sets):
            set_color = perso_palette[s][0]
            set_personalities = self.sets_personalities[s]
            set_times = [0 for _ in range(len(set_personalities)*3)] # start, end, None
            set_blocks = [0 for _ in range(len(set_personalities)*3)]
            for i,p in enumerate(set_personalities):
                ii = 3*i
                if p[1] < p[2]:
                    top = p[2]# - 0.5
                    bottom = p[1]#  + 0.5
                    t0 = p[0]
                    t1 = p[0] + 1
                else:
                    top = p[1]# - 0.5
                    bottom = p[2]# + 0.5
                    t0 = p[0] + 1
                    t1 = p[0]
                set_times[ii], set_times[ii+1], set_times[ii+2] = t0, t1, None
                set_blocks[ii], set_blocks[ii+1], set_blocks[ii+2] = bottom, top, None
            personalities_per_set[s] = {
                't': set_times,
                'b': set_blocks,
                'col': set_color
            }

        all_dead_intervals = None # to be filled late by the plots

        if self.ps_e.code in st.plot.include:
            ##############################################################
            # PLOT THE EVICTION DURATION OF ALL SETS IN ONE IMAGE
            # create two set of axes: for the map (bottom) and the tool
            fig,bottom_axes = plt.subplots(figsize=(st.plot.width, st.plot.height))
            self.axes = fig.add_axes(bottom_axes.get_position())

            # plot map
            if bottom_tool is not None:
                bottom_tool.plot(axes=bottom_axes)

            # setup axes
            self.plot_setup_X(self.ps_e)
            self.plot_setup_Y(self.ps_e)
            self.plot_setup_general(title=self.ps_e.title,
                                    variant=f'All Sets',
                                    subtit=self.ps_e.subtit)

            # draw all alive_intervals
            plt_w,plt_h = self.get_plot_xy_size(fig)
            alive_linewidth = round(plt_h / st.map.num_blocks, 4)
            for s,ai in sorted(alive_intervals_per_set.items()):
                self.axes.hlines(y=ai['y'], color=ai['col'],
                                 xmin=ai['x0'], xmax=ai['x1'],
                                 linewidth=alive_linewidth,
                                 alpha=0.5, zorder=2, linestyle='-')

            # draw all dead_intervals
            dead_linewidth = round(max(0.5, alive_linewidth / 5), 4)
            for s,di in sorted(dead_intervals_per_set.items()):
                self.axes.hlines(y=di['y'], color=di['col'],
                                 xmin=di['x0'], xmax=di['x1'],
                                 linewidth=dead_linewidth,
                                 alpha=1, zorder=2, linestyle='-')

            # save image
            save_fig(fig, f'{self.ps_e.title} all', f'{self.ps_e.suffix}-all')


            ##############################################################
            # PLOT THE EVICTION DURATION OF EACH SET IN A DIFFERENT IMAGE
            all_dead_intervals = [[] for _ in range(st.cache.num_sets)]
            for s in range(st.cache.num_sets):
                # create two set of axes: for the map (bottom) and the tool
                fig,bottom_axes = plt.subplots(figsize=(st.plot.width, st.plot.height))
                self.axes = fig.add_axes(bottom_axes.get_position())

                # plot map
                if bottom_tool is not None:
                    bottom_tool.plot(axes=bottom_axes)

                # setup axes
                self.plot_setup_X(self.ps_e)
                self.plot_setup_Y(self.ps_e)
                self.plot_setup_general(title=self.ps_e.title,
                                        variant=f'S{s}',
                                        subtit=self.ps_e.subtit)

                # draw dead intervals
                if s in dead_intervals_per_set:
                    di = dead_intervals_per_set[s]
                    self.axes.hlines(y=di['y'], color=di['col'],
                                     xmin=di['x0'], xmax=di['x1'],
                                     linewidth=dead_linewidth,
                                     alpha=1, zorder=2, linestyle='-')
                    # compute intervals for histogram
                    all_dead_intervals[s].extend([f-e for e,f in zip(di['x0'], di['x1'])])

                # draw alive intervals
                if s in alive_intervals_per_set:
                    ai = alive_intervals_per_set[s]
                    self.axes.hlines(y=ai['y'], color=ai['col'],
                                 xmin=ai['x0'], xmax=ai['x1'],
                                 linewidth=alive_linewidth,
                                 alpha=0.5, zorder=2, linestyle='-')

                # save image
                save_fig(fig, f'{self.ps_e.title} s{s:02}', f'{self.ps_e.suffix}-s{s:02}')



        if self.ps_p.code in st.plot.include:
            ##############################################################
            # PLOT PERSONALITY CHANGES OF ALL SETS IN ONE IMAGE
            # create two set of axes: for the map (bottom) and the tool
            fig,bottom_axes = plt.subplots(figsize=(st.plot.width, st.plot.height))
            self.axes = fig.add_axes(bottom_axes.get_position())

            # plot map
            if bottom_tool is not None:
                bottom_tool.plot(axes=bottom_axes)

            # setup axes
            self.plot_setup_X(self.ps_p)
            self.plot_setup_Y(self.ps_p)
            self.plot_setup_general(title=self.ps_p.title,
                                    variant=f'All Sets {st.cache.asso}-way',
                                    subtit=self.ps_p.subtit)

            # set lines width based on plot height
            plt_w,plt_h = self.get_plot_xy_size(fig)
            alive_linewidth = round(plt_h / st.map.num_blocks, 4)
            # 0.5 <= jump_linewidth <= alive_lw/6
            jump_linewidth = round(max(0.5, plt_w / (st.map.time_size)),4)
            jump_linewidth = min(alive_linewidth/6, jump_linewidth)

            # draw all alive_intervals
            for s,ai in sorted(alive_intervals_per_set.items()):
                self.axes.hlines(y=ai['y'], color=ai['col'],
                                 xmin=ai['x0'], xmax=ai['x1'],
                                 linewidth=alive_linewidth,
                                 alpha=0.5, zorder=2, linestyle='-')

            # draw jumps
            for s,ps in sorted(personalities_per_set.items()):
                self.axes.plot(ps['t'], ps['b'],
                               color=ps['col'],
                               linewidth=jump_linewidth,
                               alpha=1, zorder=2, linestyle='-',
                               solid_capstyle='round')

            # save image
            save_fig(fig, f'{self.ps_p.title} all', f'{self.ps_p.suffix}-all')



            ##############################################################
            # PLOT PERSONALITY CHANGES OF EACH SET IN A DIFFERENT IMAGE
            for s in range(st.cache.num_sets):
                # create two set of axes: for the map (bottom) and the tool
                fig,bottom_axes = plt.subplots(figsize=(st.plot.width, st.plot.height))
                self.axes = fig.add_axes(bottom_axes.get_position())

                # plot map
                if bottom_tool is not None:
                    bottom_tool.plot(axes=bottom_axes)

                # setup axes
                self.plot_setup_X(self.ps_p)
                self.plot_setup_Y(self.ps_p)
                self.plot_setup_general(title=self.ps_p.title,
                                        variant=f'S{s} {st.cache.asso}-way',
                                        subtit=self.ps_p.subtit)

                # draw alive intervals
                if s in alive_intervals_per_set:
                    ai = alive_intervals_per_set[s]
                    self.axes.hlines(y=ai['y'], color=ai['col'],
                                 xmin=ai['x0'], xmax=ai['x1'],
                                 linewidth=alive_linewidth,
                                 alpha=0.5, zorder=2, linestyle='-')

                # draw jumps
                if s in personalities_per_set:
                    ps = personalities_per_set[s]
                    self.axes.plot(ps['t'], ps['b'],
                                   color=ps['col'],
                                   linewidth=jump_linewidth,
                                   alpha=1, zorder=2, linestyle='-',
                                   solid_capstyle='round')

                # save image
                save_fig(fig, f'{self.ps_p.title} s{s:02}', f'{self.ps_p.suffix}-s{s:02}')



        if self.ps_h.code in st.plot.include:
            ##############################################################
            # PLOT HISTOGRAM OF ALL EVICTION DURATION OF ALL SETS IN ONE IMAGE
            # create a set of axes for the histogram
            fig,self.axes = plt.subplots(figsize=(st.plot.width, st.plot.height))

            # define the labels and colors for each set in the histogram
            hist_labels = [str(s) for s in range(st.cache.num_sets)]
            hist_palette = Palette(self.hue, hue_count=st.cache.num_sets,
                                   lightness=[60], saturation=[50], alpha=[90])
            hist_colors = [s_col[0] for s_col in hist_palette]
            # hist_colors = [hist_palette[i][0] for i in range(st.cache.num_sets)]

            # Prepare data for histogram plotting:
            if all_dead_intervals is None:
                # compute intervals for histogram
                all_dead_intervals = [[] for _ in range(st.cache.num_sets)]
                for s in range(st.cache.num_sets):
                    if s in dead_intervals_per_set:
                        di = dead_intervals_per_set[s]
                        all_dead_intervals[s].extend([f-e for e,f in zip(di['x0'], di['x1'])])
            # this value +1 is the right edge of the rightmost bin.
            max_dead_interval = 0
            # array with the avg dead_interval per Set.
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
            avg_hist_palette = Palette(self.hue, hue_count=st.cache.num_sets,
                                   lightness=[50], saturation=[90], alpha=[100])
            avg_hist_colors = [s_col[0] for s_col in avg_hist_palette]
            avg_linewidth = max(1.5,self.get_plot_xy_size(fig)[0]/(20*(max_bin_idx_used+1)))
            for l_s_avg,s_avg_col in zip(lin_avg_dead_intervals, avg_hist_colors):
                self.axes.axvline(x=l_s_avg, color='#000000CC', linestyle='solid',
                                  linewidth=avg_linewidth+0.5, zorder=3)
                self.axes.axvline(x=l_s_avg, color=s_avg_col, linestyle='solid',
                                  linewidth=avg_linewidth, zorder=3)

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

    def get_plot_xy_size(self, fig):
        # Obtain lines widths
        pos = self.axes.get_position()
        # Get the figure size in inches
        fig_width, fig_height = fig.get_size_inches()
        # Convert to plotting area size in inches
        plot_width_pts = pos.width * fig_width * 72
        plot_height_pts = pos.height * fig_height * 72
        return (plot_width_pts, plot_height_pts)

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
