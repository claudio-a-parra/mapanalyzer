import sys
from collections import deque
import matplotlib.pyplot as plt

from util import AddrFmt, create_up_to_n_ticks, PlotStrings, save_fig
from palette import Palette, hsl2rgb
from settings import Settings as st


class Locality:
    def __init__(self, shared_X=None, hue=325, verb=None):
        self.X = shared_X if shared_X is not None else \
            [i for i in range(st.map.time_size)]
        # line and filling colors
        self.tool_palette = Palette(hue=hue, lightness=[40,90], alpha=[100,75])
        self.axes = None
        self.verb = verb if verb is not None else st.verb
        self.name = 'Locality'
        self.about = ('Spacial locality across Time, and Temporal locality '
                      'across space')

        ## Spacial locality across time
        self.time_window = deque() #of the size of the cache.
        self.time_window_size = st.cache.cache_size
        self.Ls = [-1] * st.map.time_size
        self.psLs = PlotStrings(
            title  = 'Spacial Locality across Time',
            xlab   = 'Time',
            ylab   = 'Degree of Spacial Locality',
            suffix = '_plot-01-locality-Ls',
            subtit = 'higher is better')

        ## Temporal locality across space
        self.space_by_blocks = {} #block->list of block access times
        # Lt size is the total range of blocks in the memory studied
        tag,idx,_ = AddrFmt.split(st.map.start_addr)
        block_first = st.map.start_addr >> st.cache.bits_off
        block_last = (st.map.start_addr+st.map.mem_size-1) >> \
            st.cache.bits_off
        tot_num_blocks = block_last - block_first + 1
        self.Lt = [-1] * tot_num_blocks
        self.psLt = PlotStrings(
            title  = 'Temporal Locality across Space',
            xlab   = 'Degree of Temporal Locality',
            ylab   = 'Space [blocks]',
            suffix = '_plot-02-locality-Lt',
            subtit = 'higher is better')
        return

    def add_access(self, access):
        ## SPACIAL LOCALITY ACROSS TIME
        # append accessed bytes to time_window, and trim back if the window
        # becomes too long
        for offset in range(access.size):
            self.time_window.append(access.addr-st.map.start_addr+offset)
        while len(self.time_window) > self.time_window_size:
            self.time_window.popleft()

        ## TEMPORAL LOCALITY ACROSS SPACE
        # append access times to each memory-block's list
        for offset in range(access.size):
            tag,idx,_ = AddrFmt.split(access.addr+offset)
            if (tag,idx) not in self.space_by_blocks:
                self.space_by_blocks[(tag,idx)] = []
            self.space_by_blocks[(tag,idx)].append(access.time)
        return

    def commit(self, time):
        """compute differences and add a new value to Ls"""
        # obtain a flat window of the last accessed addresses
        flat_time_window = list(self.time_window)

        # if only one access, there is no deltas to compute. assign Ls[t] = -1
        if len(flat_time_window) < 2:
            self.Ls[time] = -1
            return

        # sort by addresses and compute deltas into ls
        flat_time_window.sort()
        ls = flat_time_window # just to reuse memory
        B = st.cache.line_size
        for i,a1,a2 in zip(range(len(ls)-1),
                           flat_time_window[:-1],
                           flat_time_window[1:]):
            ls[i] = (B - min(B, a2-a1)) / B
        del ls[-1]

        # compute average delta of the whole ls array, and write it in Ls.
        avg_ls = 100 * sum(ls) / len(ls)
        self.Ls[time] = avg_ls
        return

    def all_space_window_to_lt(self):
        """for all space windows, compute differences and compose the
        entirety of Lt"""
        # obtain the list of all ACTUALLY used blocks
        used_blocks = list(self.space_by_blocks.keys())
        used_blocks.sort()

        # compute lt for each space_window
        C = st.cache.cache_size
        tag,idx,_ = AddrFmt.split(st.map.start_addr)
        block_first = (tag << st.cache.bits_set) | idx
        for tag,idx in used_blocks:
            # the index of this block in Lt
            blk_idx = ((tag << st.cache.bits_set) | idx) - block_first
            flat_space_window = self.space_by_blocks[(tag,idx)]
            lt = flat_space_window # just to reuse memory
            if len(flat_space_window) < 2:
                self.Lt[blk_idx] = -1
                continue
            for i,t1,t2 in zip(range(len(lt)-1),
                               flat_space_window[:-1],
                               flat_space_window[1:]):
                lt[i] = (C - min(C, t2-t1)) / C
            del lt[-1]

            # compute average delta of the whole lt array, and write it in Lt
            avg_lt = 100 * sum(lt) / len(lt)
            self.Lt[blk_idx] = avg_lt
        return

    def describe(self, ind=''):
        print(f'{ind}{self.name:{st.plot.ui_name_hpad}}: {self.about}')
        return


    def plot(self, top_tool=None):
        # finish up computations
        self.all_space_window_to_lt()

        # plot Spacial and Temporal locality tools
        self.plot_Ls(top_tool)
        self.plot_Lt(top_tool)
        return

    def plot_setup_general(self, ps):
        # background color
        self.axes.patch.set_facecolor(self.tool_palette.bg)
        # setup title
        title_string = f'{ps.title}: {st.plot.prefix}'
        if ps.subtit:
            title_string += f'. ({ps.subtit})'
        self.axes.set_title(title_string, fontsize=10,
                            pad=st.plot.img_title_vpad)
        return


    def plot_Ls(self, top_tool=None):
        # create figure and tool axes
        fig,axes = plt.subplots(figsize=(st.plot.width, st.plot.height))
        self.axes = axes

        # pad X and Y=Ls axes for better visualization
        padding = 0.5
        X = [self.X[0]-padding] + self.X + [self.X[-1]+padding]
        Ls = [self.Ls[0]] + self.Ls + [self.Ls[-1]]

        # set plot limits and draw space locality across time
        self.axes.set_xlim(X[0], X[-1])
        self.axes.set_ylim(0-padding, 100+padding)
        self.axes.fill_between(X, -1, Ls,
                               color=self.tool_palette[0][0],
                               facecolor=self.tool_palette[0][1],
                               linewidth=st.plot.linewidth, step='mid',
                               zorder=2)

        # draw map
        if top_tool is not None:
            map_axes = axes.twinx()
            top_tool.plot(axes=map_axes)
            top_tool.plot_draw_Y_grid()

        # complete plot setup
        axes.set_xticks([])
        axes.set_yticks([])
        self.plot_setup_general(self.psLs)
        self.plot_Ls_setup_X()
        self.plot_Ls_setup_Y()
        save_fig(fig, self.psLs.title, self.psLs.suffix)
        return

    def plot_Ls_setup_X(self):
        # X axis label, ticks and grid
        self.axes.set_xlabel(self.psLs.xlab, color='k')
        self.axes.tick_params(axis='x', rotation=-90,
                         bottom=False, labelbottom=True,
                         top=False, labeltop=False,
                         width=st.plot.grid_other_width)
        x_ticks = create_up_to_n_ticks(self.X, base=10,
                                       n=st.plot.max_xtick_count)
        self.axes.set_xticks(x_ticks)
        self.axes.grid(axis='x', which='both',
                  alpha=0.1, color='k', zorder=1,
                  linestyle=st.plot.grid_other_style,
                  linewidth=st.plot.grid_other_width)

    def plot_Ls_setup_Y(self):
        # Y axis label, ticks, and grid
        self.axes.yaxis.set_label_position('left')
        self.axes.set_ylabel(self.psLs.ylab, color=self.tool_palette.fg)
        percentages = list(range(100 + 1)) # from 0 to 100
        y_ticks = create_up_to_n_ticks(percentages, base=10, n=11)
        self.axes.tick_params(axis='y', which='both',
                              left=True, labelleft=True,
                              right=False, labelright=False,
                              width=st.plot.grid_main_width,
                              colors=self.tool_palette.fg)
        self.axes.set_yticks(y_ticks)
        self.axes.grid(axis='y', which='both',
                       alpha=0.1, color=self.tool_palette.fg, zorder=1,
                       linewidth=st.plot.grid_main_width,
                       linestyle=st.plot.grid_main_style)


    def plot_Lt(self, top_tool=None):
        # create figure and tool axes
        fig,axes = plt.subplots(figsize=(st.plot.width, st.plot.height))
        self.axes = axes

        # pad Y and X=Lt axes for better visualization
        # Y = list of memory blocks. always starting from 0
        padding = 0.5
        Y = [i for i in range(st.map.mem_size >> st.cache.bits_off)]
        Y = [Y[0]-padding] + Y + [Y[-1]+padding]
        Lt = [self.Lt[0]] + self.Lt + [self.Lt[-1]]

        # set plot limits and draw time locality across space
        self.axes.set_ylim(Y[0], Y[-1])
        self.axes.set_xlim(0-padding, 100+padding)
        self.axes.fill_betweenx(Y, Lt, -1,
                           color=self.tool_palette[0][0],
                           facecolor=self.tool_palette[0][1],
                           linewidth=st.plot.linewidth, step='mid', zorder=2)
        self.axes.invert_yaxis()

        # plot map
        if top_tool is not None:
            map_axes = fig.add_axes(axes.get_position(), frameon=False)
            top_tool.plot(axes=map_axes)
            top_tool.plot_draw_Y_grid()

        # complete plot setup
        axes.set_xticks([])
        axes.set_yticks([])
        self.plot_setup_general(self.psLt)
        self.plot_Lt_setup_X()
        self.plot_Lt_setup_Y()
        save_fig(fig, self.psLt.title, self.psLt.suffix)
        return

    def plot_Lt_setup_X(self):
        self.axes.set_xlabel(self.psLt.xlab, color=self.tool_palette.fg)
        percentages = list(range(100 + 1)) # from 0 to 100
        self.axes.tick_params(axis='x', bottom=True, top=False, labelbottom=True,
                              rotation=-90, colors=self.tool_palette.fg,
                              width=st.plot.grid_main_width)
        x_ticks = create_up_to_n_ticks(percentages, base=10, n=11)
        self.axes.set_xticks(x_ticks)
        self.axes.grid(axis='x', which='both',
                       alpha=0.1, color=self.tool_palette.fg, zorder=1,
                       linewidth=st.plot.grid_main_width,
                       linestyle=st.plot.grid_main_style)
        return

    def plot_Lt_setup_Y(self):
        mem_color = hsl2rgb(120,100,30,100)
        self.axes.yaxis.set_label_position('left')
        self.axes.set_ylabel(self.psLt.ylab, color=mem_color)
        list_of_blocks = [i for i in
                          range(st.map.mem_size >> st.cache.bits_off)]
        y_ticks = create_up_to_n_ticks(list_of_blocks, base=10, n=11)
        self.axes.tick_params(axis='y', which='both', left=False, right=False,
                              labelleft=True, labelright=False,
                              colors=mem_color,
                              width=st.plot.grid_other_width)
        self.axes.set_yticks(y_ticks)
        # self.axes.grid(axis='y', which='both',
        #                alpha=0.1, color='k', zorder=1,
        #                linewidth=st.plot.grid_other_width,
        #                linestyle=st.plot.grid_other_style)
        return
