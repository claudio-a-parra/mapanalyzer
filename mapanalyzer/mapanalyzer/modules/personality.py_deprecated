import sys
import matplotlib.pyplot as plt
from matplotlib.colors import ListedColormap


from mapanalyzer.util import create_up_to_n_ticks, PlotStrings, save_fig, Palette, AddrFmt
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
        self.enabled = self.ps.code in st.plot.include
        if not self.enabled:
            return

        self.X = shared_X if shared_X is not None else \
            [i for i in range(st.map.time_size)]

        self.tool_palette = Palette(hue=hue,
                                    hue_count=st.cache.num_sets,
                                    lightness=st.plot.pal_lig,
                                    saturation=st.plot.pal_sat,
                                    alpha=[85,75])#st.plot.pal_alp)

        # map with the currently cached blocks and the time they were cached.
        # tag -> time_in
        self.cached_blocks = {}

        # list of S list. Each list corresponds to the jumps history of one set. Each element
        # is a tuple (time_out, block_id_out, block_id_in)
        self.sets_personalities = [[] for _ in range(st.cache.num_sets)]

        # block access matrix. rows: blocks. cols: time.
        map_mat_rows = sub_resolution_between(st.map.num_padded_bytes,
                                              st.plot.min_res, st.plot.max_res)
        map_mat_cols = sub_resolution_between(st.map.time_size,
                                              st.plot.min_res, st.plot.max_res)
        # if possible, reduce resolution to obtain one row per block. If no clean
        # division, then the resolution was badly reduced from the original memory size.
        # Not terrible, but if not possible, it doesn't look pretty.
        if map_mat_rows % st.cache.line_size == 0:
            map_mat_rows = map_mat_rows // st.cache.line_size

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

        # if a block is being fetched...
        if tag_in is not None:
            # register its time_in in the cached_blocks.
            self.cached_blocks[(tag_in,set_idx)] = time

        # if a block is evicted while the other is fetched...
        if tag_in is not None and tag_out is not None:
            # then the cache-set is "changing personality"
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

    def plot_setup_general(self, variant=''):
        # background color
        self.axes.patch.set_facecolor(self.tool_palette.bg)
        # setup title
        if variant != '':
            variant = f'. {variant}'
        title_string = f'{self.ps.title}{variant}: {st.plot.prefix}'
        if self.ps.subtit:
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


        # colors: [0] : block not alive
        #         [n] : Set-(n-1) makes block alive.
        color_map_list = ['#FFFFFF00'] + [self.tool_palette[i][1] for i in range(st.cache.num_sets)]

        # collect the parameters to plot the jumps of each set.
        personalities_per_set = {} # set_idx -> plot parameters for all the jumps made by that set on its blocks
        for s in range(st.cache.num_sets):
            set_color = self.tool_palette[s][0]
            set_personalities = self.sets_personalities[s]
            set_times = [0 for _ in range(len(set_personalities)*3)]
            set_blocks = [0 for _ in range(len(set_personalities)*3)]
            for i,p in enumerate(set_personalities):
                ii = 3*i
                set_times[ii], set_times[ii+1], set_times[ii+2] = p[0], p[0]+1, None
                set_blocks[ii], set_blocks[ii+1], set_blocks[ii+2] = p[1], p[2], None
            personalities_per_set[s] = {
                't': set_times,
                'b': set_blocks,
                'col': set_color
            }


        # Plot all sets together in one image:
        cmap = ListedColormap(color_map_list) # define color map
        # draw blocks
        self.axes.imshow(self.block_access_matrix, cmap=cmap, origin='lower',
                         interpolation='none',
                         aspect='auto', zorder=2, extent=self.mat_extent,
                         vmin=-1, vmax=st.cache.num_sets-1)
        # draw time jumps
        for s,ps in sorted(personalities_per_set.items()):
            self.axes.plot(ps['t'], ps['b'],
                             color=ps['col'],
                             linewidth=st.plot.jump_line_width,
                             alpha=1, zorder=2, linestyle='-')
            # save image
        save_fig(fig, f'{self.ps.code} all', f'{self.ps.suffix}-all')

        # Plot one set in a different image
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
            # draw jumps
            ps = personalities_per_set[s]
            self.axes.plot(ps['t'], ps['b'],
                             color=ps['col'],
                             linewidth=st.plot.jump_line_width,
                             alpha=1, zorder=2, linestyle='-')
            # save image
            save_fig(fig, f'{self.ps.code} s{s:02}', f'{self.ps.suffix}-s{s:02}')
        return
