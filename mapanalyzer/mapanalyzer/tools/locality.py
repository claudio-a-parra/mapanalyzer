import sys
from collections import deque
import matplotlib.pyplot as plt

from mapanalyzer.util import AddrFmt, create_up_to_n_ticks, PlotStrings, save_fig, Palette, hsl2rgb, Dbg
from mapanalyzer.settings import Settings as st


class Locality:
    def __init__(self, shared_X=None, hue=325):
        self.X = shared_X if shared_X is not None else \
            [i for i in range(st.map.time_size)]
        # line and filling colors
        self.tool_palette = Palette(hue=hue,
                                    lightness=st.plot.pal_lig,
                                    saturation=st.plot.pal_sat,
                                    alpha=st.plot.pal_alp)
        self.axes = None
        self.name = 'Locality'
        self.plotcodeLs = 'SLD'
        self.plotcodeLt = 'TLD'
        self.about = ('Spacial locality across Time, and Temporal locality '
                      'across space.')

        ## SPATIAL LOCALITY ACROSS TIME
        # time window chronological access: keeps the temporal order of accesses.
        # (access offset, size)
        self.tw_chro_acc = deque()
        # time window byte counter: keeps one entry per accessed byte, counting
        # repeated accesses to that byte.
        # {byte offset -> number of accesses}
        self.tw_byte_count = {}
        self.tw_byte_count_max = st.cache.cache_size
        # Spatial Locality vector
        self.Ls = [0] * st.map.time_size
        self.psLs = PlotStrings(
            title  = 'SLD across Time',
            xlab   = 'Time [access instr.]',
            ylab   = 'Spacial Locality Degree',
            suffix = '_plot-01-locality-Ls',
            subtit = '')
            # subtit = 'higher is better')

        ## TEMPORAL LOCALITY ACROSS SPACE
        self.space_by_blocks = {} #block->list of block access times
        self.Lt = [0] * st.map.num_blocks
        self.psLt = PlotStrings(
            title  = 'TLD across Space',
            xlab   = 'Temporal Locality Degree',
            ylab   = 'Space [blocks]',
            suffix = '_plot-02-locality-Lt',
            subtit = '')
            # subtit = 'higher is better')
        return

    def add_access(self, access):
        ## SPACIAL LOCALITY ACROSS TIME
        off = access.addr - st.map.start_addr

        # Add access...
        # ...to chronological queue
        self.tw_chro_acc.append((off,access.size))
        # ... to table of bytes
        for b in range(off,off+access.size):
            if b not in self.tw_byte_count:
                self.tw_byte_count[b] = 1
            else:
                self.tw_byte_count[b] += 1

        # keep table of accesses under max by de-queuing from the
        # chronological queue.
        while len(self.tw_byte_count) > self.tw_byte_count_max:
            old_off,old_size = self.tw_chro_acc.popleft()
            # decrement/remove bytes from table of bytes
            for b in range(old_off,old_off+old_size):
                if self.tw_byte_count[b] == 1:
                    del self.tw_byte_count[b]
                else:
                    self.tw_byte_count[b] -= 1

        ## TEMPORAL LOCALITY ACROSS SPACE
        # get the block to which the address belongs
        #block_id = access.addr >> st.cache.bits_off
        blkid_start = access.addr >> st.cache.bits_off
        if blkid_start not in self.space_by_blocks:
            self.space_by_blocks[blkid_start] = []
        self.space_by_blocks[blkid_start].append(access.time)

        # in case the reading fell between blocks, the last bytes will be
        # in the next block.
        blkid_end = (access.addr + access.size -1) >> st.cache.bits_off
        if blkid_end == blkid_start:
            return
        if blkid_end not in self.space_by_blocks:
            self.space_by_blocks[blkid_end] = []
        self.space_by_blocks[blkid_end].append(access.time)


    def commit(self, time):
        """produce the a neighborhood from tw_byte_count's keys and add it
        to Ls"""

        neig = sorted(list(self.tw_byte_count))

        # if only one access, there are no deltas to get, then, Ls[time] = 0
        if len(neig) < 2:
            self.Ls[time] = 0
            return

        # compute differences among neighbors and store them into dist.
        dist = neig # just to reuse memory
        b = st.cache.line_size
        for j,ni,nj in zip(range(len(dist)-1), neig[:-1], neig[1:]):
            dist[j] = (b - min(b, nj-ni)) / (b - 1)
        del dist[-1]

        # get average distance in the neighborhood, and write it in Ls.
        avg_dist = sum(dist) / len(dist)
        self.Ls[time] = avg_dist
        return

    def all_space_window_to_lt(self):
        """for all space windows, compute differences and compose the
        entirety of Lt"""
        # obtain the list of all ACTUALLY used blocks
        used_blocks = list(self.space_by_blocks.keys())
        used_blocks.sort()

        # for each window, get its neighborhood, compute distances and store
        # the average distance in Lt.
        C = st.cache.cache_size
        B = st.cache.line_size
        for ubi in used_blocks: #ubi: used-block ID
            neig = self.space_by_blocks[ubi]
            dist = neig # just to reuse memory
            # if there is only one access, there is no locality to compute.
            if len(neig) < 2:
                self.Lt[ubi] = 0
                continue

            for j,ni,nj in zip(range(len(dist)-1), neig[:-1], neig[1:]):
                #dist[j] = (C - min(C, nj-ni)) / (C-1)
                dist[j] = (C - B*min(nj-ni,C//B)) / (C-B)
            del dist[-1]

            # get average difference in the neighborhood, and write it in Lt.
            avg_dist = sum(dist) / len(dist)
            self.Lt[ubi] = avg_dist
        return

    def describe(self, ind=''):
        print(f'{ind}{self.name:{st.plot.ui_toolname_hpad}}: {self.about}')
        return

    def plotLs_setup_X(self):
        # Data range based on data
        X_padding = 0.005
        # add tails at start/end of X for cosmetic purposes.
        X = [self.X[0]-X_padding] + self.X + [self.X[-1]+X_padding]
        self.axes.set_xlim(X[0], X[-1])

        # Axis details: label, ticks and grid
        self.axes.set_xlabel(self.psLs.xlab)
        self.axes.tick_params(axis='x',
                              top=False, bottom=True,
                              labeltop=False, labelbottom=True,
                              rotation=-90, width=st.plot.grid_other_width)
        x_ticks = create_up_to_n_ticks(self.X, base=10, n=st.plot.max_xtick_count)
        self.axes.set_xticks(x_ticks)
        # self.axes.grid(axis='x', which='both',
        #           alpha=0.1, color='k', zorder=1,
        #           linestyle=st.plot.grid_other_style,
        #           linewidth=st.plot.grid_other_width)
        return X

    def plotLs_setup_Y(self):
        # define Y-axis data range based on data and user input
        Y_min = 0
        Y_max = 1
        if self.plotcodeLs in st.plot.y_ranges:
            Y_min = st.plot.y_ranges[self.plotcodeLs][0]
            Y_max = st.plot.y_ranges[self.plotcodeLs][1]
        Y_padding = (Y_max - Y_min)/200
        self.axes.set_ylim(Y_min-Y_padding, Y_max+Y_padding)
        # add tails at start/end of Y for cosmetic purposes.
        Y_Ls = [self.Ls[0]] + self.Ls + [self.Ls[-1]]

        # Axis details: spine, label, ticks, and grid
        #self.axes.spines['left'].set_edgecolor(self.tool_palette.fg)
        self.axes.set_ylabel(self.psLs.ylab)
        self.axes.tick_params(axis='y',
                              left=True, right=False,
                              labelleft=True, labelright=False,
                              width=st.plot.grid_main_width)
        range_floats = [y/1000 for y in range(int(1000*Y_min), int(1000*Y_max)+1)]
        y_ticks = create_up_to_n_ticks(range_floats, base=10, n=11)
        self.axes.set_yticks(y_ticks)
        self.axes.grid(axis='y',
                       zorder=1,
                       alpha=st.plot.grid_main_alpha,
                       linewidth=st.plot.grid_main_width,
                       linestyle=st.plot.grid_main_style)
        return Y_Ls

    def plotLs_draw_textbox(self):
        # insert text box with average usage
        avg = sum(self.Ls)/len(self.Ls)
        text = f'Avg: {avg:.2f}'
        self.axes.text(0.98, 0.98, text, transform=self.axes.transAxes,
                       ha='right', va='top',
                       bbox=dict(facecolor=st.plot.tbox_bg , edgecolor=st.plot.tbox_border,
                                 boxstyle="square,pad=0.2"),
                       fontdict=dict(family=st.plot.tbox_font, size=st.plot.tbox_font_size),
                       zorder=1000)
        return

    def plot_setup_general(self, ps):
        # background color
        self.axes.patch.set_facecolor(self.tool_palette.bg)
        # setup title
        title_string = f'{ps.title}: {st.plot.prefix}'
        if ps.subtit:
            title_string += f'. ({ps.subtit})'
        self.axes.set_title(title_string, fontsize=10, pad=st.plot.img_title_vpad)
        return

    def plotLs(self, bottom_tool=None):
        # only plot if requested
        if self.plotcodeLs not in st.plot.include:
            return

        # create two set of axes: for the map (bottom) and the tool
        fig,bottom_axes = plt.subplots(figsize=(st.plot.width, st.plot.height))
        self.axes = fig.add_axes(bottom_axes.get_position())

        # plot map
        if bottom_tool is not None:
            bottom_tool.plot(axes=bottom_axes)

        # setup axes and obtain data ranges
        X = self.plotLs_setup_X()
        Y_Ls = self.plotLs_setup_Y()

        # plot the spatial locality
        self.axes.fill_between(X, -1, Y_Ls, step='mid', zorder=2,
                               color=self.tool_palette[0][0],
                               facecolor=self.tool_palette[0][1],
                               linewidth=st.plot.linewidth)
        # finish plot setup
        self.plotLs_draw_textbox()
        self.plot_setup_general(self.psLs)

        # save image
        save_fig(fig, self.plotcodeLs, self.psLs.suffix)
        return

    def plotLt_setup_Y(self, block_sep_color=None):
        # Data range based on data
        Y_padding = 0.5
        num_blocks = st.map.num_blocks
        blocks = list(range(num_blocks))
        # add tails at start/end of X for cosmetic purposes.
        Y = [blocks[0]-Y_padding] + blocks + [blocks[-1]+Y_padding]
        self.axes.set_ylim(Y[0], Y[-1])

        # Axis details: label, ticks and grid
        self.axes.set_ylabel(self.psLt.ylab)
        self.axes.tick_params(axis='y',
                              left=True, right=False,
                              labelleft=True, labelright=False,
                              width=st.plot.grid_other_width)

        y_ticks = create_up_to_n_ticks(blocks, base=2, n=st.plot.max_ytick_count)
        self.axes.set_yticks(y_ticks)
        # self.axes.grid(axis='y', which='both',
        #           alpha=0.1, color='k', zorder=1,
        #           linestyle=st.plot.grid_other_style,
        #           linewidth=st.plot.grid_other_width)

        # block separators
        color = block_sep_color if block_sep_color != None else '#40BF40'
        max_blocks = st.plot.grid_max_blocks
        if num_blocks <= max_blocks:
            X_min,X_max = 0,1
            X_padding = (X_max - X_min)/200
            xmin,xmax = X_min-X_padding,X_max+X_padding
            block_sep_lines = [i-0.5 for i in blocks]
            # dynamic line width
            block_lw = 2*(1 - ((num_blocks-1)/max_blocks))
            self.axes.hlines(y=block_sep_lines, xmin=xmin, xmax=xmax,
                             color=color,
                             linewidth=block_lw, alpha=0.4, zorder=1)
        return Y

    def plotLt_setup_X(self):
        # define Y-axis data range based on data and user input
        X_min = 0
        X_max = 1
        if self.plotcodeLt in st.plot.y_ranges:
            X_min = st.plot.y_ranges[self.plotcodeLt][0]
            X_max = st.plot.y_ranges[self.plotcodeLt][1]
        X_padding = (X_max - X_min)/200
        self.axes.set_xlim(X_min-X_padding, X_max+X_padding)
        # add tails at start/end of X for cosmetic purposes.
        X_Lt = [self.Lt[0]] + self.Lt + [self.Lt[-1]]

        # Axis details: spine, label, ticks, and grid
        #self.axes.spines['bottom'].set_edgecolor(self.tool_palette.fg)
        self.axes.set_xlabel(self.psLt.xlab)
        self.axes.tick_params(axis='x',
                              bottom=True, top=False,
                              labelbottom=True, labeltop=False,
                              rotation=-90, width=st.plot.grid_main_width)
        range_floats = [x/1000 for x in range(int(1000*X_min), int(1000*X_max)+1)]
        x_ticks = create_up_to_n_ticks(range_floats, base=10, n=11)
        self.axes.set_xticks(x_ticks)
        self.axes.grid(axis='x',
                       zorder=1,
                       alpha=st.plot.grid_main_alpha,
                       linewidth=st.plot.grid_main_width,
                       linestyle=st.plot.grid_main_style)
        return X_Lt

    def plotLt_draw_textbox(self):
        # insert text box with average usage
        avg = sum(self.Lt)/len(self.Lt)
        text = f'Avg: {avg:.2f}'
        self.axes.text(0.98, 0.98, text, transform=self.axes.transAxes,
                       ha='right', va='top',
                       bbox=dict(facecolor=st.plot.tbox_bg , edgecolor=st.plot.tbox_border,
                                 boxstyle="square,pad=0.2"),
                       fontdict=dict(family=st.plot.tbox_font, size=st.plot.tbox_font_size),
                       zorder=1000)
        return

    def plotLt(self, bottom_tool=None):
        # only plot if requested
        if self.plotcodeLt not in st.plot.include:
            return

        # create two set of axes: for the map (bottom) and the tool
        fig,bottom_axes = plt.subplots(figsize=(st.plot.width, st.plot.height))
        self.axes = fig.add_axes(bottom_axes.get_position())

        # draw map
        block_sep_color = None
        if bottom_tool is not None:
            bottom_tool.plot(axes=bottom_axes)
            block_sep_color = bottom_tool.tool_palette[0][0]

        # setup axes and obtain data ranges
        Y = self.plotLt_setup_Y(block_sep_color=block_sep_color)
        X_Lt = self.plotLt_setup_X()

        # plot the temporal locality
        self.axes.fill_betweenx(Y, X_Lt, -1, step='mid', zorder=2,
                           color=self.tool_palette[0][0],
                           facecolor=self.tool_palette[0][1],
                           linewidth=st.plot.linewidth)
        self.axes.invert_yaxis()


        # complete plot setup
        self.plotLt_draw_textbox()
        self.plot_setup_general(self.psLt)

        # save image
        save_fig(fig, self.plotcodeLt, self.psLt.suffix)
        return

    def plot(self, bottom_tool=None):
        # finish up computations
        self.all_space_window_to_lt()
        # plot Spacial and Temporal locality tools
        self.plotLs(bottom_tool)
        self.plotLt(bottom_tool)
        return
