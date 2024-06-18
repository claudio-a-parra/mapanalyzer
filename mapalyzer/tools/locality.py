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

        ## Spacial locality across time
        self.time_window = deque() #of the size of the cache.
        self.time_window_curr_size = 0
        self.time_window_max_size = st.cache.cache_size
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
        # tag,idx,_ = AddrFmt.split(st.map.start_addr)
        # block_first = st.map.start_addr >> st.cache.bits_off
        # block_last = (st.map.start_addr+st.map.mem_size-1) >> \
        #     st.cache.bits_off
        # tot_num_blocks = block_last - block_first + 1
        # self.Lt = [-1] * tot_num_blocks

        # Lt size is the total range of blocks in the memory studied
        self.Lt = [-1] * st.map.num_blocks
        self.psLt = PlotStrings(
            title  = 'Temporal Locality across Space',
            xlab   = 'Degree of Temporal Locality',
            ylab   = 'Space [blocks]',
            suffix = '_plot-02-locality-Lt',
            subtit = 'higher is better')
        return

    def add_access(self, access):
        ## SPACIAL LOCALITY ACROSS TIME
        # Append access address to the time window. Trim the access window if
        # it is too long.
        # Use the first byte of access to compute the spacial differences, but
        # count all the bytes in the access to determine the window size.
        mem_offset = access.addr - st.map.start_addr
        self.time_window.append((mem_offset,access.size))
        self.time_window_curr_size += access.size
        while self.time_window_curr_size > self.time_window_max_size:
            old_access = self.time_window.popleft()
            self.time_window_curr_size -= old_access[1]


        ## TEMPORAL LOCALITY ACROSS SPACE
        # Append access times to each memory-block's list.
        # Only register the first byte of the access.

        # block id relative to the beginning of the memory, so the first
        # block is 0
        block_id = access.addr >> st.cache.bits_off
        if block_id not in self.space_by_blocks:
            self.space_by_blocks[block_id] = []
        self.space_by_blocks[block_id].append(access.time)

        return

    def commit(self, time):
        """compute differences and add a new value to Ls"""
        # obtain a flat window of the last accessed addresses
        flat_time_window = [x[0] for x in list(self.time_window)]

        Dbg.p(f'COMMIT')
        # if only one access, there is no deltas to compute. assign Ls[t] = -1
        if len(flat_time_window) < 2:
            Dbg.p(f'flat_time_win_size < 2; return')
            self.Ls[time] = -1
            return

        # sort by addresses and compute deltas into ls
        flat_time_window.sort()
        Dbg.p('flat_time_window:')
        Dbg.p(flat_time_window)
        ls = flat_time_window # just to reuse memory
        B = st.cache.line_size
        for i,a1,a2 in zip(range(len(ls)-1),
                           flat_time_window[:-1],
                           flat_time_window[1:]):
            ls[i] = (B - min(B, a2-a1)) / B
        del ls[-1]
        Dbg.p('ls:')
        Dbg.p(ls)

        # compute average delta of the whole ls array, and write it in Ls.
        avg_ls = 100 * sum(ls) / len(ls)
        Dbg.p(f'avg_ls:{avg_ls}')
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
        for ubi in used_blocks:
            flat_space_window = self.space_by_blocks[ubi]
            lt = flat_space_window # just to reuse memory
            if len(flat_space_window) < 2:
                self.Lt[ubi] = -1
                continue
            for i,t1,t2 in zip(range(len(lt)-1),
                               flat_space_window[:-1],
                               flat_space_window[1:]):
                lt[i] = (C - min(C, t2-t1)) / C
            del lt[-1]

            # compute average delta of the whole lt array, and write it in Lt
            avg_lt = 100 * sum(lt) / len(lt)
            self.Lt[ubi] = avg_lt
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
        title_string = f'{ps.title}: {st.plot.prefix}'
        if ps.subtit:
            title_string += f'. ({ps.subtit})'
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
        percentages = list(range(100 + 1)) # from 0 to 100
        y_ticks = create_up_to_n_ticks(percentages, base=10, n=11)
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
        padding = 0.5
        Y = [-padding] + list(range(st.map.num_blocks)) + \
            [st.map.num_blocks -padding]
        Lt = [self.Lt[0]] + self.Lt + [self.Lt[-1]]

        # set plot limits and draw time locality across space
        self.axes.set_ylim(Y[0], Y[-1])
        self.axes.set_xlim(0-padding, 100+padding)
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
        x_ticks = create_up_to_n_ticks(range(100+1), base=10,
                                       n=st.plot.max_xtick_count)
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
        y_ticks = create_up_to_n_ticks(list_of_blocks, base=10,
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
