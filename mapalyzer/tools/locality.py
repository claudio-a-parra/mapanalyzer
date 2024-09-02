import sys
from collections import deque
import matplotlib.pyplot as plt

from util import AddrFmt, create_up_to_n_ticks, PlotStrings, save_fig, Palette, hsl2rgb, Dbg
from settings import Settings as st


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
        self.about = ('Spacial locality across Time, and Temporal locality '
                      'across space')

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
        self.Ls = [-1] * st.map.time_size
        self.psLs = PlotStrings(
            title  = 'Spacial Locality across Time',
            xlab   = 'Time [accesses]',
            ylab   = 'Degree of Spacial Locality',
            suffix = '_plot-01-locality-Ls',
            subtit = '')
            # subtit = 'higher is better')

        ## TEMPORAL LOCALITY ACROSS SPACE
        self.space_by_blocks = {} #block->list of block access times
        self.Lt = [-1] * st.map.num_blocks
        self.psLt = PlotStrings(
            title  = 'Temporal Locality across Space',
            xlab   = 'Degree of Temporal Locality',
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
        for ubi in used_blocks:
            neig = self.space_by_blocks[ubi]
            dist = neig # just to reuse memory
            # if there is only one access, there is no locality to compute.
            if len(neig) < 2:
                self.Lt[ubi] = -1
                continue

            for j,ni,nj in zip(range(len(dist)-1), neig[:-1], neig[1:]):
                dist[j] = (C - min(C, nj-ni)) / (C-1)
            del dist[-1]

            # get average difference in the neighborhood, and write it in Lt.
            avg_dist = sum(dist) / len(dist)
            self.Lt[ubi] = avg_dist
        return

    def describe(self, ind=''):
        print(f'{ind}{self.name:{st.plot.ui_name_hpad}}: {self.about}')
        return


    def plot(self, bottom_tool=None):
        # finish up computations
        self.all_space_window_to_lt()

        # plot Spacial and Temporal locality tools
        self.plot_Ls(bottom_tool)
        self.plot_Lt(bottom_tool)
        return

    def plot_setup_general(self, ps):
        # background color
        self.axes.patch.set_facecolor(self.tool_palette.bg)
        # setup title
        title_string = f'{ps.title}'
        if ps.subtit:
            title_string += f' ({ps.subtit})'
        title_string += f'\n{st.plot.prefix}'
        self.axes.set_title(title_string, fontsize=10,
                            pad=st.plot.img_title_vpad)
        return


    def plot_Ls(self, bottom_tool=None):
        # create two set of axes: for the map (bottom) and the tool
        fig,bottom_axes = plt.subplots(figsize=(st.plot.width, st.plot.height))
        self.axes = fig.add_axes(bottom_axes.get_position())

        # draw map
        if bottom_tool is not None:
            bottom_tool.plot(axes=bottom_axes)

        # pad X and Y=Ls axes for better visualization
        padding = 0.005
        X = [self.X[0]-padding] + self.X + [self.X[-1]+padding]
        Ls = [self.Ls[0]] + self.Ls + [self.Ls[-1]]

        # set plot limits and draw space locality across time
        self.axes.set_xlim(X[0], X[-1])
        self.axes.set_ylim(0-padding, 1+padding)
        self.axes.fill_between(X, -1, Ls,
                               color=self.tool_palette[0][0],
                               facecolor=self.tool_palette[0][1],
                               linewidth=st.plot.linewidth, step='mid',
                               zorder=2)

        # complete plot setup
        self.axes.set_xticks([])
        self.axes.set_yticks([])
        self.plot_setup_general(self.psLs)
        self.plot_Ls_setup_X()
        self.plot_Ls_setup_Y()
        save_fig(fig, self.psLs.title, self.psLs.suffix)
        return

    def plot_Ls_setup_X(self):
        # X axis label, ticks and grid
        self.axes.set_xlabel(self.psLs.xlab, color='k')
        self.axes.tick_params(axis='x', rotation=-90,
                              bottom=True, labelbottom=True,
                              top=False, labeltop=False,
                              width=st.plot.grid_other_width)
        x_ticks = create_up_to_n_ticks(self.X, base=10,
                                       n=st.plot.max_xtick_count)
        self.axes.set_xticks(x_ticks)
        # self.axes.grid(axis='x', which='both',
        #           alpha=0.1, color='k', zorder=1,
        #           linestyle=st.plot.grid_other_style,
        #           linewidth=st.plot.grid_other_width)
        return

    def plot_Ls_setup_Y(self):
        # spine
        #self.axes.spines['left'].set_edgecolor(self.tool_palette.fg)

        # Y axis label, ticks, and grid
        self.axes.yaxis.set_label_position('left')
        self.axes.set_ylabel(self.psLs.ylab) #, color=self.tool_palette.fg)
        y_ticks = create_up_to_n_ticks([x/10 for x in range(11)], base=10, n=11)
        self.axes.tick_params(axis='y', which='both',
                              left=True, labelleft=True,
                              right=False, labelright=False,
                              width=st.plot.grid_main_width,
                              colors='k') #colors=self.tool_palette.fg)
        self.axes.set_yticks(y_ticks)
        self.axes.grid(axis='y', which='both', color='k',
                       #color=self.tool_palette.fg,
                       zorder=1,
                       alpha=st.plot.grid_main_alpha,
                       linewidth=st.plot.grid_main_width,
                       linestyle=st.plot.grid_main_style)

    def plot_Lt(self, bottom_tool=None):
        # create figure and tool axes
        fig,bottom_axes = plt.subplots(figsize=(st.plot.width, st.plot.height))
        self.axes = fig.add_axes(bottom_axes.get_position())

        # draw map
        if bottom_tool is not None:
            bottom_tool.plot(axes=bottom_axes)
            block_sep_color = bottom_tool.tool_palette[0][0]

        # pad Y and X=Lt axes for better visualization
        padding = 0.005
        Y = [-0.5] + list(range(st.map.num_blocks)) + \
            [st.map.num_blocks -0.5]
        Lt = [self.Lt[0]] + self.Lt + [self.Lt[-1]]

        # set plot limits and draw time locality across space
        self.axes.set_ylim(Y[0], Y[-1])
        self.axes.set_xlim(0-padding, 1+padding)
        self.axes.fill_betweenx(Y, Lt, -1,
                           color=self.tool_palette[0][0],
                           facecolor=self.tool_palette[0][1],
                           linewidth=st.plot.linewidth, step='mid', zorder=2)
        self.axes.invert_yaxis()

        # complete plot setup
        self.axes.set_xticks([])
        self.axes.set_yticks([])
        self.plot_setup_general(self.psLt)
        self.plot_Lt_setup_X()
        self.plot_Lt_setup_Y()
        self.plot_Lt_draw_Y_grid(block_sep_color)
        save_fig(fig, self.psLt.title, self.psLt.suffix)
        return

    def plot_Lt_setup_X(self):
        # spine
        #self.axes.spines['bottom'].set_edgecolor(self.tool_palette.fg)

        # label
        self.axes.set_xlabel(self.psLt.xlab) #, color=self.tool_palette.fg)

        # ticks
        self.axes.tick_params(axis='x', #colors=self.tool_palette.fg,
                              top=False, labeltop=False,
                              bottom=True, labelbottom=True, rotation=-90,
                              width=st.plot.grid_main_width)
        x_ticks = create_up_to_n_ticks([x/10 for x in range(11)], base=10, n=11)
        self.axes.set_xticks(x_ticks)

        # grid
        self.axes.grid(axis='x', which='both', # color=self.tool_palette.fg,
                       zorder=1,
                       alpha=st.plot.grid_main_alpha,
                       linewidth=st.plot.grid_main_width,
                       linestyle=st.plot.grid_main_style)
        return

    def plot_Lt_setup_Y(self):
        self.axes.yaxis.set_label_position('left')
        self.axes.set_ylabel(self.psLt.ylab, color='k')
        list_of_blocks = list(range(st.map.num_blocks))
        y_ticks = create_up_to_n_ticks(list_of_blocks, base=2,
                                       n=st.plot.max_ytick_count)
        self.axes.tick_params(axis='y', which='both',
                              left=True, labelleft=True,
                              right=False, labelright=False,
                              colors='k',
                              width=st.plot.grid_other_width)
        self.axes.set_yticks(y_ticks)
        return

    def plot_Lt_draw_Y_grid(self, color='#40BF40'):
        if st.map.num_blocks > st.plot.grid_max_blocks:
            return
        max_blocks = st.plot.grid_max_blocks
        xmin,xmax = 0-0.5,101-0.5
        block_sep_lines = [i-0.5 for i in range(st.map.num_blocks)]
        block_lw = 2*(1 - ((st.map.num_blocks-1) / max_blocks))
        self.axes.hlines(y=block_sep_lines, xmin=xmin, xmax=xmax,
                         color=color,
                         linewidth=block_lw, alpha=0.4, zorder=1)
        return
