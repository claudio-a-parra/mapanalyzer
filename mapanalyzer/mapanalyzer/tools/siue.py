import sys
import matplotlib.pyplot as plt


from mapanalyzer.util import create_up_to_n_ticks, PlotStrings, save_fig, Dbg, Palette, AddrFmt
from mapanalyzer.settings import Settings as st

class SIUEviction:
    def __init__(self, shared_X=None, hue=220):
        self.X = shared_X if shared_X is not None else \
            [i for i in range(st.map.time_size)]
        self.tool_palette = Palette(hue=hue,
                                    hue_count=st.cache.num_sets,
                                    lightness=st.plot.pal_lig,
                                    saturation=st.plot.pal_sat,
                                    alpha=st.plot.pal_alp)

        self.base_tag,self.base_set,_ = AddrFmt.split(st.map.aligned_start_addr)
        self.cached_blocks = {}
        self.blocks_lifes = [[] for _ in range(st.cache.num_sets)]
        self.blocks_jumps = [[] for _ in range(st.cache.num_sets)]

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

    def update(self, time, set_idx, tag_in, tag_out):
        if tag_out is not None:
            time_in = self.cached_blocks[(tag_out,set_idx)]
            del self.cached_blocks[(tag_out,set_idx)]
            time_out = time - 1
            blk_out_id = (tag_out << st.cache.bits_set) | set_idx
            self.blocks_lifes[set_idx].append((blk_out_id,time_in,time_out))

        if tag_in is not None:
            self.cached_blocks[(tag_in,set_idx)] = time
            blk_in_id  = (tag_in  << st.cache.bits_set) | set_idx
            if tag_out is not None:
                self.blocks_jumps[set_idx].append((time-1,blk_out_id,blk_in_id))
        return

    def commit(self, time):
        # this tool doesn't need to do anything at the end of each time step.
        return

    def describe(self, ind=''):
        print(f'{ind}{self.name:{st.plot.ui_toolname_hpad}}: {self.about}')
        return


    def plot(self, bottom_tool=None):
        # only plot if requested
        if self.plotcode not in st.plot.include:
            return

        # define set line width based on the number of blocks
        max_blocks = st.plot.grid_max_blocks
        set_lw  = max(0.3, 9*(1 - ((st.map.num_blocks-1) / max_blocks)))
        jump_lw = max(0.1, 3*(1 - ((st.map.num_blocks-1) / max_blocks)))

        # create two set of axes: for the map (bottom) and the tool
        fig,bottom_axes = plt.subplots(figsize=(st.plot.width, st.plot.height))
        bottom_axes.set_xticks([])
        bottom_axes.set_yticks([])
        self.axes = fig.add_axes(bottom_axes.get_position())

        # plot map
        if bottom_tool is not None:
            bottom_tool.plot(axes=bottom_axes)
            block_sep_color = bottom_tool.tool_palette[0][0]
        else:
            block_sep_color = '#40BF40'

        # set plot limits
        padding = 0.5
        self.axes.set_xlim(self.X[0]-padding, self.X[-1]+padding)
        self.axes.set_ylim(0-padding, st.map.num_blocks-padding)

        for s in range(st.cache.num_sets):
            set_color = self.tool_palette[s]

            # draw block lifes
            blocks_lifes = self.blocks_lifes[s]
            set_blocks = [l[0] for l in blocks_lifes]
            set_time_in = [l[1]-0.25 for l in blocks_lifes]
            set_time_out = [l[2]+0.25 for l in blocks_lifes]
            self.axes.hlines(y=set_blocks, xmin=set_time_in, xmax=set_time_out,
                             color=set_color[0], linewidth=set_lw, alpha=1,
                             zorder=2, linestyle='-')

            # draw block jumps
            blocks_jumps = self.blocks_jumps[s]
            set_times = [(j[0]+0.25,j[0]+0.75) for j in blocks_jumps]
            set_block_out = [j[1] for j in blocks_jumps]
            set_block_in = [j[2] for j in blocks_jumps]
            for (t0,t1),b0,b1 in zip(set_times,set_block_out,set_block_in):
                self.axes.plot((t0,t1), (b0,b1),
                               color=set_color[0], linewidth=jump_lw, alpha=1,
                               zorder=2, solid_capstyle='round', linestyle='-')

        # finish plot setup
        self.plot_setup_general(variant=f'All Sets')
        self.plot_setup_X()
        #self.plot_draw_X_grid()
        self.plot_setup_Y()
        self.plot_draw_Y_grid(block_sep_color)

        # save image
        save_fig(fig, f'{self.plotcode} all', f'{self.ps.suffix}_all')



        # draw one plot for each set
        for s in range(st.cache.num_sets):
            # create figure and tool axes
            fig,bottom_axes = plt.subplots(figsize=(st.plot.width, st.plot.height))
            bottom_axes.set_xticks([])
            bottom_axes.set_yticks([])
            self.axes = fig.add_axes(bottom_axes.get_position())

            # plot map
            if bottom_tool is not None:
                bottom_tool.plot(axes=bottom_axes)
                block_sep_color = bottom_tool.tool_palette[0][0]
            else:
                block_sep_color = '#40BF40'

            # set plot limits
            padding = 0.5
            self.axes.set_xlim(self.X[0]-padding, self.X[-1]+padding)
            self.axes.set_ylim(0-padding, st.map.num_blocks-padding)

            set_color = self.tool_palette[s]

            # draw block lifes
            blocks_lifes = self.blocks_lifes[s]
            set_blocks = [l[0] for l in blocks_lifes]
            set_time_in = [l[1]-0.25 for l in blocks_lifes]
            set_time_out = [l[2]+0.25 for l in blocks_lifes]
            self.axes.hlines(y=set_blocks, xmin=set_time_in, xmax=set_time_out,
                             color=set_color[0], linewidth=set_lw, alpha=1,
                             zorder=2, linestyle='-')

            # draw block jumps
            blocks_jumps = self.blocks_jumps[s]
            set_times = [(j[0]+0.25,j[0]+0.75) for j in blocks_jumps]
            set_block_out = [j[1] for j in blocks_jumps]
            set_block_in = [j[2] for j in blocks_jumps]
            for (t0,t1),b0,b1 in zip(set_times,set_block_out,set_block_in):
                self.axes.plot((t0,t1), (b0,b1),
                               color=set_color[0], linewidth=jump_lw, alpha=1,
                               zorder=2, solid_capstyle='round', linestyle='-')

            # finish plot setup
            self.plot_setup_general(variant=f'Set {s:02}')
            self.plot_setup_X()
            #self.plot_draw_X_grid()
            self.plot_setup_Y()
            self.plot_draw_Y_grid(block_sep_color)

            # save image
            save_fig(fig, f'{self.plotcode} s{s}', f'{self.ps.suffix}_s{s}')

        return

    def plot_setup_Y(self):
        #self.axes.spines['left'].set_edgecolor(self.tool_palette.fg)
        self.axes.set_ylabel(self.ps.ylab)
        self.axes.tick_params(axis='y',
                              left=True, labelleft=True,
                              right=False, labelright=False,
                              width=st.plot.grid_main_width)
        y_ticks = create_up_to_n_ticks(range(st.map.num_blocks), base=10,
                                       n=st.plot.max_ytick_count)
        self.axes.set_yticks(y_ticks)

        # direction
        self.axes.invert_yaxis()
        return

    def plot_setup_X(self):
        # X axis label, ticks and grid
        self.axes.set_xlabel(self.ps.xlab)
        self.axes.tick_params(axis='x',
                              bottom=True, labelbottom=True,
                              top=False, labeltop=False,
                              rotation=-90, width=st.plot.grid_other_width)
        x_ticks = create_up_to_n_ticks(self.X, base=10,
                                       n=st.plot.max_xtick_count)
        self.axes.set_xticks(x_ticks)
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

    def plot_draw_Y_grid(self, color):
        max_lines = st.plot.grid_max_blocks
        if st.map.num_blocks > max_lines:
            return
        lw = 2*(1 - ((st.map.num_blocks-1) / max_lines))
        xmin,xmax = self.X[0]-0.5,self.X[-1]+0.5
        block_sep_lines = [i-0.5
                           for i in range(st.map.num_blocks)]
        self.axes.hlines(y=block_sep_lines, xmin=xmin, xmax=xmax,
                         color=color,
                         linewidth=lw, alpha=0.4, zorder=1)
        return

    def plot_draw_X_grid(self):
        padding = 0.5
        ymin,ymax = 0-padding,st.map.num_blocks-padding
        time_sep_lines = [i-0.5 for i in
                          range(self.X[0],self.X[-1]+1)]

        self.axes.vlines(x=time_sep_lines, ymin=ymin, ymax=ymax,
                         color='k', linewidth=0.33, alpha=0.2, zorder=1)
        return
