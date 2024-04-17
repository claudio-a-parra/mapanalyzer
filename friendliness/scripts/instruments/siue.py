#!/usr/bin/env python3
import sys
import matplotlib.colors as mcolors # to create shades of colors from list
from collections import deque

from .generic import GenericInstrument

#-------------------------------------------
class SIUEvict(GenericInstrument):
    """
    Definition:
        The proportion of SIU evictions with respect to the total number of
        evictions. A SIU (still-in-use) eviction is the eviction of a cache
        block that later will be fetched to the cache again.

    Fetch and Evict Counters:
        This instrument works in two passes. In the first pass a dictionary
        of (tag,index) -> (counter) is populated, so that every time a cache
        block is fetched, the counter increments.
        On the second pass, and using the already populated dictionary, every
        block eviction triggers a decrement in its corresponding counter.
        If after the decrement, the counter is still greater than 0, this means
        the block is later brought back to cache again. It is, then, said that
        the current is an eviction of a "still-in-use" block.

    Captured Events:
        Each event is a tuple of two counters: (siu_evicts, tot_evicts). Note
        that tot_evicts includes all siu_evicts. These counters are cumulative.

    Plot interpretation:
        The plot is a line that ranges from 0% to 100% showing the proportion
        of evictions that are SIU.
    """

    def __init__(self, instr_counter, num_sets, asso, alias, verb=False):
        super().__init__(instr_counter, verb=verb)
        # last block operations (tag,index) -> queue<(instr_id,operation)>()
        self.blocks_ops = {}
        # queue of last block operations to preserve in/out order
        # of the dictionary above.
        self.buffer = deque()
        self.buffer_fetches_count = 0

        self.buffer_max_size = num_sets * asso
        self.num_sets = num_sets
        self.SIUE = []

        # this is the whole alias tool.
        self.alias = alias

        # BEGIN_OLD
        self.fetch_counters = {}
        self.mode = 'fetch' # ['fetch', 'evict']
        self.siu_evict_count = 0
        self.tot_evict_count = 0
        self.zero_counter = (0,0)
        # END_OLD

        self.plot_name_sufix = '_plot-05-siu'
        self.plot_title      = 'Still-in-Use Block Evictions'
        self.plot_subtitle   = 'lower count is better'
        self.plot_y_label    = 'Set Index'
        self.plot_x_label    = 'Instruction'
        self.plot_color_text = '#6122AA'   # dark magenta
        self.plot_color_dots = '#7A2AD5FF' # magenta opaque
        self.plot_color_boxes = '#9A4AF5FF' # magenta opaque
        self.plot_color_bg    = '#FFFFFF00' # transparent

    def register(self, op, tag, index):
        if not self.enabled:
            return

        block = (tag,index)

        # append block id to temporally sorted queue
        self.buffer.append(block)
        # print(f'b+ {block}: {op} ({self.ic.val()})')
        if op == 'fetch':
            self.buffer_fetches_count += 1

        # trim back of the buffer and block search dictionary
        # if the buffer is too long.
        while self.buffer_fetches_count > self.buffer_max_size:
            old_block = self.buffer.popleft()
            old_instr_id,old_op = self.blocks_ops[old_block].popleft()
            # print(f'b- {old_block}: {old_op} ({old_instr_id})')
            # print(f'        d- {old_block}: {old_op} ({old_instr_id})')
            if len(self.blocks_ops[old_block]) == 0:
                del self.blocks_ops[old_block]
            if old_op == 'fetch':
                self.buffer_fetches_count -= 1

        # if the current operation is fetch, then check if the same
        # block was recently evicted. If so, annotate a SIU eviction.
        if block in self.blocks_ops:
            if op == 'fetch':
                recent_instr_id,recent_op = self.blocks_ops[block][-1]
                if recent_op == 'evict':
                    self.SIUE.append((recent_instr_id,index))
                    # print(f'SIU: ({recent_instr_id}) -> ({self.ic.val()})')
        else:
            self.blocks_ops[block] = deque()
        # print(f'        d+ {block}: {op} ({self.ic.val()})')
        self.blocks_ops[block].append((self.ic.val(),op))
        return


    def get_extent(self):
        # fine tune margins to place each quadrilateral of the imshow()
        # right on the tick. So adding a 0.5 margin at each side.
        left_edge = self.X[0] - 0.5
        right_edge = self.X[-1] + 0.5
        bottom_edge = 0 - 0.5
        top_edge = (self.num_sets-1) + 0.5 # I want the max index + margin
        extent = (left_edge, right_edge, bottom_edge, top_edge)
        return extent


    def plot(self, axes, basename='siue', extent=None):
        # draw the image and invert Y axis (so lower value is on top)

        #self.alias.plot_color_boxes = '#7A2AD588' # magenta almost opaque
        self.alias.plot(axes)

        X = [coor[0] for coor in self.SIUE]
        Y = [coor[1] for coor in self.SIUE]
        # create plotable image with captured coordenates
        plotable_img = [[0] * len(self.X) for _ in range(self.num_sets)]
        for x,y in self.SIUE:
            plotable_img[y][x] = 1

        # create color shade
        colors = [self.plot_color_bg, self.plot_color_boxes]
        shade_cmap = mcolors.LinearSegmentedColormap.from_list(
            'transparency_cmap', colors)

        # draw the image and invert Y axis (so lower value is on top)
        extent = extent if extent != None else self.get_extent()
        axes.imshow(plotable_img, cmap=shade_cmap, origin='lower', interpolation=None,
                    aspect='auto', extent=extent, zorder=1, vmin=0, vmax=1)
        axes.scatter(X, Y, marker='|', s=512/self.num_sets,
                     color=self.plot_color_boxes, zorder=1)
        le,re,be,te = extent
        axes.set_xlim(le, re)
        axes.set_ylim(be, te)
        axes.invert_yaxis()

        # setup title
        axes.set_title(f'{self.plot_title}: {basename}. '
                       f'({self.plot_subtitle})', fontsize=10)

        # setup X ticks, labels, and grid
        axes.tick_params(axis='x', bottom=True, top=False, labelbottom=True,
                         rotation=90)
        x_ticks = self._create_up_to_n_ticks(self.X, base=10, n=20)
        axes.set_xticks(x_ticks)
        axes.set_xlabel(self.plot_x_label)
        axes.grid(axis='x', which='both', linestyle='-', alpha=0.1,
                  color='k', linewidth=0.5, zorder=2)

        # setup Y ticks, labels, and grid
        axes.tick_params(axis='y', which='both', left=True, right=False,
                         labelleft=True, labelright=False,
                         colors=self.plot_color_text)
        set_indices = list(range(self.num_sets))
        y_ticks = self._create_up_to_n_ticks(set_indices, base=2, n=9)
        axes.set_yticks(y_ticks)
        axes.yaxis.set_label_position('left')
        if y_ticks[-1] < 100:
            pad = 10
        if y_ticks[-1] < 10:
            pad = 16
        axes.set_ylabel(self.plot_y_label, color=self.plot_color_text,
                        labelpad=pad)
        axes.grid(axis='y', which='both', linestyle='-', alpha=0.1,
                  color=self.plot_color_dots, linewidth=0.5, zorder=2)
        return
