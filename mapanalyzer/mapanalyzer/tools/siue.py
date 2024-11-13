import sys
import matplotlib.pyplot as plt
from matplotlib.colors import ListedColormap


from mapanalyzer.util import create_up_to_n_ticks, PlotStrings, save_fig, Dbg, Palette, AddrFmt
from mapanalyzer.settings import Settings as st
from mapanalyzer.util import sub_resolution_between

class SIUEviction:
    def __init__(self, shared_X=None, hue=220):
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
        self.blocks_jumps = [[] for _ in range(st.cache.num_sets)]

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

        self.name = 'SiU Evictions'
        self.plotcode = 'SIU'
        self.about = ('Blocks that are evicted and fetched again in a short time.')

        self.ps = PlotStrings(
            title  = 'SIUE',
            xlab   = 'Time [access instr.]',
            ylab   = 'Memory Blocks',
            suffix = '_plot-07-siu-evictions',
            subtit = 'flatter is better')
        return


    # update the block access matrix
    def update_bam(self, set_idx, block, time_in, time_out):
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
        # if a block is evicted, recall its time_in, and register its stay in cache
        if tag_out is not None:
            time_in = self.cached_blocks[(tag_out,set_idx)]
            del self.cached_blocks[(tag_out,set_idx)]
            time_out = time - 1
            blk_out_id = (tag_out << st.cache.bits_set) | set_idx
            self.update_bam(set_idx, blk_out_id, time_in, time_out)

        # if a block is being fetched, store its time_in.
        if tag_in is not None:
            self.cached_blocks[(tag_in,set_idx)] = time
            blk_in_id  = (tag_in  << st.cache.bits_set) | set_idx
            # if also a block was kicked out, then the set experimented a "jump of identity"
            # from one block to another. Register the jump.
            if tag_out is not None:
                self.blocks_jumps[set_idx].append((time-1,blk_out_id,blk_in_id))
        return

    def commit(self, time):
        # this tool doesn't need to do anything at the end of each time step.
        return

    def describe(self, ind=''):
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
        # only plot if requested
        if self.plotcode not in st.plot.include:
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
        self.plot_setup_general(variant='All Sets')


        # colors: [0] : block not alive
        #         [n] : Set-(n-1) makes block alive.
        color_map_list = ['#FFFFFF00'] + [self.tool_palette[i][1] for i in range(st.cache.num_sets)]

        # collect the parameters to plot the jumps of each set.
        jumps_per_set = {}
        for s in range(st.cache.num_sets):
            set_color = self.tool_palette[s]
            blocks_jumps = self.blocks_jumps[s]
            set_times = [0 for _ in blocks_jumps]
            set_block_low = [0 for _ in blocks_jumps]
            set_block_high = [0 for _ in blocks_jumps]
            for i,j in enumerate(blocks_jumps):
                set_times[i] = j[0]+0.5
                if j[1] < j[2]:
                    set_block_low[i] = j[1] - 0.5
                    set_block_high[i] = j[2] + 0.5
                else:
                    set_block_low[i] = j[2] - 0.5
                    set_block_high[i] = j[1] + 0.5
            jumps_per_set[s] = {
                'col': set_color,
                'x': set_times,
                'y0': set_block_low,
                'y1': set_block_high
            }

        # Plot all sets together in one image:
        cmap = ListedColormap(color_map_list) # define color map
        # draw blocks
        self.axes.imshow(self.block_access_matrix, cmap=cmap, origin='lower',
                         aspect='auto', zorder=2, extent=self.mat_extent,
                         vmin=-1, vmax=st.cache.num_sets-1)
        # draw jumps
        for _,js in jumps_per_set.items():
            self.axes.vlines(x=js['x'],
                             ymin=js['y0'],
                             ymax=js['y1'],
                             color=js['col'],
                             linewidth=st.plot.jump_line_width,
                             alpha=1, zorder=2, linestyle='-')
        # save image
        save_fig(fig, f'{self.plotcode} all', f'{self.ps.suffix}-all')

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
            self.plot_setup_general(variant=f'Set {s:02}')

            # set all colors white but this set (which is s+1, coz 0 is blank)
            set_color_map_list = ['#FFFFFF00'] * (len(color_map_list))
            set_color_map_list[s+1] = color_map_list[s+1]
            # define color map
            cmap = ListedColormap(set_color_map_list)

            # draw blocks
            self.axes.imshow(self.block_access_matrix, cmap=cmap, origin='lower',
                         aspect='auto', zorder=2, extent=self.mat_extent,
                         vmin=-1, vmax=st.cache.num_sets-1)
            # draw jumps
            js = jumps_per_set[s]
            self.axes.vlines(x=js['x'],
                             ymin=js['y0'],
                             ymax=js['y1'],
                             color=js['col'],
                             linewidth=st.plot.jump_line_width,
                             alpha=1, zorder=2, linestyle='-')
            # save image
            save_fig(fig, f'{self.plotcode} s{s:02}', f'{self.ps.suffix}-s{s:02}')
        return
