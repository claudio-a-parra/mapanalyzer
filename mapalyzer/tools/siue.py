import sys
import matplotlib.pyplot as plt


from util import create_up_to_n_ticks, PlotStrings, save_fig, Dbg, Palette
from settings import Settings as st

class SIUEviction:
    def __init__(self, shared_X=None, hue=230):
        # BUG: INCOMPLETE...
        self.X = shared_X if shared_X is not None else \
            [i for i in range(st.map.time_size)]
        self.tool_palette = Palette(hue=[hue,(hue+180)%360],
                                    lightness=st.plot.pal_lig,
                                    saturation=st.plot.pal_sat,
                                    alpha=st.plot.pal_alp)

        self.read = 0
        self.read_dist = [0] * len(self.X)
        self.write = 0
        self.write_dist = [0] * len(self.X)
        self.last_time = 0

        self.name = 'Main Memory Access'
        self.about = ('Distribution of main memory read and write operations')

        self.ps = PlotStrings(
            title  = 'Cumulative Main Mem. Access',
            xlab   = 'Time',
            ylab   = 'Access Count',
            suffix = '_plot-04-access-count',
            subtit = 'flatter is better')
        return

    def add_access(self, rw):
        """Adds to read or write counter"""
        if rw == 'r':
            self.read += 1
        else:
            self.write += 1
        return

    def commit(self, time):
        # fill possible empty times with previous counts.
        last_read = self.read_dist[self.last_time]
        last_write = self.write_dist[self.last_time]
        for t in range(self.last_time+1, time):
            self.read_dist[t] = last_read
            self.write_dist[t] = last_write

        # add updated counters
        self.read_dist[time] = self.read
        self.write_dist[time] = self.write
        self.last_time = time

    def describe(self, ind=''):
        print(f'{ind}{self.name:{st.plot.ui_name_hpad}}: {self.about}')
        return


    def plot(self, top_tool=None):
        # create figure and tool axes
        fig,map_axes = plt.subplots(figsize=(st.plot.width, st.plot.height))
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
