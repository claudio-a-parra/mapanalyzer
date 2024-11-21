import sys
import matplotlib.pyplot as plt
from matplotlib.colors import ListedColormap
import numpy as np


from mapanalyzer.util import create_up_to_n_ticks, PlotStrings, save_fig, Dbg, Palette, AddrFmt
from mapanalyzer.settings import Settings as st
from mapanalyzer.util import sub_resolution_between

class Personality:
    def __init__(self, shared_X=None, hue=220):
        self.tool_name = 'Block Pers Adopt'
        self.tool_about = ('Trace of Block Personality Adoption by the lines of each set.')
        self.ps = PlotStrings(
            title  = 'BPA',
            code   = 'BPA',
            xlab   = 'Time [access instr.]',
            ylab   = 'Memory Blocks',
            suffix = '_plot-08-personality',
            subtit = ''
        )
        self.hue = hue

        self.enabled = self.ps.code in st.plot.include
        if not self.enabled:
            return

        self.X = shared_X if shared_X is not None else \
            [i for i in range(st.map.time_size)]

        # This map-of-maps stores the in-cache time duration of each block.
        # Take this map of maps as a compressed table where the block_id is the concatenation of
        # the block-tag and the set-id:
        # so:
        #                    ,------ set id
        #                    |   ,-- block tag
        #                    |   |
        #    alive_intervals[3][47] -> [(fetch_time, evict_time), ...]
        #
        # In the example, block_id = '47 concat 3'
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

        # if a block is being fetched...
        if tag_in is not None:
            # Begin registration of in-Cache duration
            if set_idx not in self.alive_intervals:
                self.alive_intervals[set_idx] = {}
            if tag_in not in self.alive_intervals[set_idx]:
                self.alive_intervals[set_idx][tag_in] = []
            self.alive_intervals[set_idx][tag_in].append((time-1, None))

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

    def plot_setup_X(self):
        # Data range based on data
        X_padding = 0.5
        # add tails at start/end of X for cosmetic purposes
        self.axes.set_xlim(self.X[0]-X_padding, self.X[-1]+X_padding)

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

        # create two set of axes: for the map (bottom) and the tool
        fig,bottom_axes = plt.subplots(figsize=(st.plot.width, st.plot.height))
        self.axes = fig.add_axes(bottom_axes.get_position())

        # plot map
        if bottom_tool is not None:
            bottom_tool.plot(axes=bottom_axes)

        # setup axes
        self.plot_setup_X()
        self.plot_setup_Y()
        self.plot_setup_general(title=self.ps.title, variant=f'All Sets {st.cache.asso}-way',
                                subtit=self.ps.subtit)

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
                                lightness=[80], saturation=[75], alpha=[30])
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


        ##############################################################
        # PLOT PERSONALITY CHANGES OF ALL SETS IN ONE IMAGE
        # set lines width based on plot height
        plt_w,plt_h = self.get_plot_xy_size(fig)
        alive_linewidth = round(plt_h / st.map.num_blocks, 4)
        jump_linewidth = round(max(0.5, plt_w / (st.map.time_size)), 4)
        jump_linewidth = min(alive_linewidth/2, jump_linewidth)

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
        save_fig(fig, f'{self.ps.title} all', f'{self.ps.suffix}-all')


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
            self.plot_setup_X()
            self.plot_setup_Y()
            self.plot_setup_general(title=self.ps.title,
                                    variant=f'S{s} {st.cache.asso}-way',
                                    subtit=self.ps.subtit)

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
            save_fig(fig, f'{self.ps.title} s{s:02}', f'{self.ps.suffix}-s{s:02}')

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
