import sys
import matplotlib.pyplot as plt


from util import create_up_to_n_ticks, PlotStrings, save_fig, Dbg, Palette, AddrFmt
from settings import Settings as st

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
        self.about = ('Shows blocks that are evicted and fetched again in a short time.')

        self.ps = PlotStrings(
            title  = 'SiU Evictions',
            xlab   = 'Time',
            ylab   = 'Blocks',
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
        print(f'{ind}{self.name:{st.plot.ui_name_hpad}}: {self.about}')
        return


    def plot(self, bottom_tool=None):
        # define set line width based on the number of blocks
        max_blocks = st.plot.grid_max_blocks
        set_lw  = max(0.1, 9*(1 - ((st.map.num_blocks-1) / max_blocks)))
        jump_lw = max(0.1, 2*(1 - ((st.map.num_blocks-1) / max_blocks)))

        # draw all sets together
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
        save_fig(fig, self.ps.title, f'{self.ps.suffix}_all')



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
            save_fig(fig, self.ps.title, f'{self.ps.suffix}_s{s}')

        return

    def plot_setup_Y(self):
        # spine
        #self.axes.spines['left'].set_edgecolor(self.tool_palette.fg)

        # label
        self.axes.set_ylabel(self.ps.ylab) #color=self.tool_palette.fg)

        # ticks
        self.axes.tick_params(axis='y', #,colors=self.tool_palette.fg,
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
                         linewidth=lw, alpha=1, zorder=1)
        return

    def plot_draw_X_grid(self):
        padding = 0.5
        ymin,ymax = 0-padding,st.map.num_blocks-padding
        time_sep_lines = [i-0.5 for i in
                          range(self.X[0],self.X[-1]+1)]

        self.axes.vlines(x=time_sep_lines, ymin=ymin, ymax=ymax,
                         color='k', linewidth=0.33, alpha=0.2, zorder=1)
        return
























    def plot_old(self, bottom_tool=None):
        # create figure and tool axes
        fig,bottom_axes = plt.subplots(figsize=(st.plot.width, st.plot.height))
        axes = map_axes.twinx()
        axes.patch.set_facecolor(self.tool_palette.bg)

        # common plot elements
        padding = 0.5
        X = [-padding] + self.X + [self.X[-1]+padding]

        # draw READ distribution
        distrs = [self.read_dist, self.write_dist]
        for i,d in enumerate(distrs):
            D = [d[0]] + d + [d[-1]]
            axes.fill_between(X, -1, D, step='mid', zorder=2,
                          color=self.tool_palette[i][0],
                          facecolor=self.tool_palette[i][1],
                          linewidth=st.plot.linewidth)


        # Y axis label, ticks, and grid
        axes.yaxis.set_label_position('left')
        axes.set_ylabel(self.ps.ylab, color=self.tool_palette.fg)
        max_Y = max(distrs[0][-1], distrs[1][-1])
        full_y_ticks = list(range(max_Y + 1)) # from 0 to 100
        y_ticks = create_up_to_n_ticks(full_y_ticks, base=10, n=11)
        axes.tick_params(axis='y', which='both', left=True, right=False,
                         labelleft=True, labelright=False,
                         width=st.plot.grid_main_width,
                         colors=self.tool_palette.fg)
        axes.set_yticks(y_ticks)
        axes.grid(axis='y', which='both', color=self.tool_palette.fg,
                  zorder=1,
                  alpha=st.plot.grid_main_alpha,
                  linewidth=st.plot.grid_main_width,
                  linestyle=st.plot.grid_main_style)

        # plot map
        top_tool.plot(axes=map_axes, xlab=True)
        #top_tool.plot_draw_Y_grid()


        # X axis label, ticks and grid
        axes.set_xlabel(self.ps.xlab)
        axes.tick_params(axis='x', bottom=True, top=False, labelbottom=True,
                         rotation=-90, width=st.plot.grid_other_width)
        x_ticks = create_up_to_n_ticks(self.X, base=10, n=st.plot.max_xtick_count)
        axes.set_xticks(x_ticks)
        # axes.grid(axis='x', which='both',
        #           alpha=0.1, color='k', zorder=1,
        #           linestyle=st.plot.grid_other_style,
        #           linewidth=st.plot.grid_other_width)

        # set plot limits
        axes.set_xlim(self.X[0]-padding, self.X[-1]+padding)
        axes.set_ylim(0-(max_Y/200), max_Y+(max_Y/200))

        # setup title
        title_string = f'{self.ps.title}: {st.plot.prefix}'
        if self.ps.subtit:
            title_string += f'. ({self.ps.subtit})'
        axes.set_title(title_string, fontsize=10, pad=st.plot.img_title_vpad)

        # save image
        save_fig(fig, self.ps.title, self.ps.suffix)

        return



















































##!/usr/bin/env python3
# import sys
# import matplotlib.colors as mcolors # to create shades of colors from list
# from collections import deque

# from .generic import GenericInstrument

# #-------------------------------------------
# class SIUEvict(GenericInstrument):
#     """
#     Definition:
#         The proportion of SIU evictions with respect to the total number of
#         evictions. A SIU (still-in-use) eviction is the eviction of a cache
#         block that later will be fetched to the cache again.

#     Fetch and Evict Counters:
#         This instrument works in two passes. In the first pass a dictionary
#         of (tag,index) -> (counter) is populated, so that every time a cache
#         block is fetched, the counter increments.
#         On the second pass, and using the already populated dictionary, every
#         block eviction triggers a decrement in its corresponding counter.
#         If after the decrement, the counter is still greater than 0, this means
#         the block is later brought back to cache again. It is, then, said that
#         the current is an eviction of a "still-in-use" block.

#     Captured Events:
#         Each event is a tuple of two counters: (siu_evicts, tot_evicts). Note
#         that tot_evicts includes all siu_evicts. These counters are cumulative.

#     Plot interpretation:
#         The plot is a line that ranges from 0% to 100% showing the proportion
#         of evictions that are SIU.
#     """

#     def __init__(self, instr_counter, num_sets, asso, alias, verb=False):
#         super().__init__(instr_counter, verb=verb)
#         # last block operations (tag,index) -> queue<(instr_id,operation)>()
#         self.blocks_ops = {}
#         # queue of last block operations to preserve in/out order
#         # of the dictionary above.
#         self.buffer = deque()
#         self.buffer_fetches_count = 0

#         self.buffer_max_size = num_sets * asso
#         self.num_sets = num_sets
#         self.SIUE = []

#         # this is the whole alias tool.
#         self.alias = alias

#         # BEGIN_OLD
#         self.fetch_counters = {}
#         self.mode = 'fetch' # ['fetch', 'evict']
#         self.siu_evict_count = 0
#         self.tot_evict_count = 0
#         self.zero_counter = (0,0)
#         # END_OLD

#         self.plot_name_sufix = '_plot-05-siu'
#         self.plot_title      = 'SIU Evictions'
#         self.plot_subtitle   = 'fewer is better'
#         self.plot_y_label    = 'Set Index'
#         self.plot_x_label    = 'Instruction'
#         self.plot_color_text = '#6122AA'   # dark magenta
#         self.plot_color_dots = '#7A2AD5FF' # magenta opaque
#         self.plot_color_boxes = '#9A4AF5FF' # magenta opaque
#         self.plot_color_bg    = '#FFFFFF00' # transparent

#     def register(self, op, tag, index):
#         if not self.enabled:
#             return

#         block = (tag,index)

#         # append block id to temporally sorted queue
#         self.buffer.append(block)
#         # print(f'b+ {block}: {op} ({self.ic.val()})')
#         if op == 'fetch':
#             self.buffer_fetches_count += 1

#         # trim back of the buffer and block search dictionary
#         # if the buffer is too long.
#         while self.buffer_fetches_count > self.buffer_max_size:
#             old_block = self.buffer.popleft()
#             old_instr_id,old_op = self.blocks_ops[old_block].popleft()
#             # print(f'b- {old_block}: {old_op} ({old_instr_id})')
#             # print(f'        d- {old_block}: {old_op} ({old_instr_id})')
#             if len(self.blocks_ops[old_block]) == 0:
#                 del self.blocks_ops[old_block]
#             if old_op == 'fetch':
#                 self.buffer_fetches_count -= 1

#         # if the current operation is fetch, then check if the same
#         # block was recently evicted. If so, annotate a SIU eviction.
#         if block in self.blocks_ops:
#             if op == 'fetch':
#                 recent_instr_id,recent_op = self.blocks_ops[block][-1]
#                 if recent_op == 'evict':
#                     self.SIUE.append((recent_instr_id,index))
#                     # print(f'SIU: ({recent_instr_id}) -> ({self.ic.val()})')
#         else:
#             self.blocks_ops[block] = deque()
#         # print(f'        d+ {block}: {op} ({self.ic.val()})')
#         self.blocks_ops[block].append((self.ic.val(),op))
#         return


#     def get_extent(self):
#         # fine tune margins to place each quadrilateral of the imshow()
#         # right on the tick. So adding a 0.5 margin at each side.
#         left_edge = self.X[0] - 0.5
#         right_edge = self.X[-1] + 0.5
#         bottom_edge = 0 - 0.5
#         top_edge = (self.num_sets-1) + 0.5 # I want the max index + margin
#         extent = (left_edge, right_edge, bottom_edge, top_edge)
#         return extent


#     def plot(self, axes, basename='siue', extent=None):
#         # draw the image and invert Y axis (so lower value is on top)

#         #self.alias.plot_color_boxes = '#7A2AD588' # magenta almost opaque
#         self.alias.plot(axes)

#         X = [coor[0] for coor in self.SIUE]
#         Y = [coor[1] for coor in self.SIUE]
#         # create plotable image with captured coordinates
#         plotable_img = [[0] * len(self.X) for _ in range(self.num_sets)]
#         for x,y in self.SIUE:
#             plotable_img[y][x] = 1

#         # create color shade
#         colors = [self.plot_color_bg, self.plot_color_boxes]
#         shade_cmap = mcolors.LinearSegmentedColormap.from_list(
#             'transparency_cmap', colors)

#         # draw the image and invert Y axis (so lower value is on top)
#         extent = extent if extent != None else self.get_extent()
#         axes.imshow(plotable_img, cmap=shade_cmap, origin='lower', interpolation=None,
#                     aspect='auto', extent=extent, zorder=1, vmin=0, vmax=1)
#         axes.scatter(X, Y, marker='|', s=512/self.num_sets,
#                      color=self.plot_color_boxes, zorder=1)
#         le,re,be,te = extent
#         axes.set_xlim(le, re)
#         axes.set_ylim(be, te)
#         axes.invert_yaxis()

#         # setup title
#         axes.set_title(f'{self.plot_title}: {basename}. '
#                        f'({self.plot_subtitle})', fontsize=10)

#         # setup X ticks, labels, and grid
#         axes.tick_params(axis='x', bottom=True, top=False, labelbottom=True,
#                          rotation=90)
#         x_ticks = self._create_up_to_n_ticks(self.X, base=10, n=20)
#         axes.set_xticks(x_ticks)
#         axes.set_xlabel(self.plot_x_label)
#         axes.grid(axis='x', which='both', linestyle='-', alpha=0.1,
#                   color='k', linewidth=0.5, zorder=2)

#         # setup Y ticks, labels, and grid
#         axes.tick_params(axis='y', which='both', left=True, right=False,
#                          labelleft=True, labelright=False,
#                          colors=self.plot_color_text)
#         set_indices = list(range(self.num_sets))
#         y_ticks = self._create_up_to_n_ticks(set_indices, base=2, n=9)
#         axes.set_yticks(y_ticks)
#         axes.yaxis.set_label_position('left')
#         if y_ticks[-1] < 100:
#             pad = 10
#         if y_ticks[-1] < 10:
#             pad = 16
#         axes.set_ylabel(self.plot_y_label, color=self.plot_color_text,
#                         labelpad=pad)
#         axes.grid(axis='y', which='both', linestyle='-', alpha=0.1,
#                   color=self.plot_color_dots, linewidth=0.5, zorder=2)
#         return
