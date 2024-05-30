import sys
from collections import deque
import matplotlib.pyplot as plt

from util import AddrFmt, create_up_to_n_ticks, PlotStrings, save_fig
from palette import Palette
from settings import Settings as st

class SingleThreadLocality:
    def __init__(self, curr_time, verb=None):
        self.verb = verb if verb is not None else st.verb
        # temporal window; time of last access; spacial locality across time
        self.time_window = deque()
        self.time_last_access = curr_time
        self.Ls = [-1] * st.map.time_size

        # block->acc_time; space window (block); temporal locality across space
        self.space_by_blocks = {}
        self.space_window = deque()

        # create Lt based on the total range of blocks in the memory studied
        tag,idx,_ = AddrFmt.split(st.map.start_addr)
        block_first = st.map.start_addr >> st.cache.bits_off
        block_last = (st.map.start_addr+st.map.mem_size-1) >> \
            st.cache.bits_off
        tot_num_blocks = block_last - block_first + 1
        self.Lt = [-1] * tot_num_blocks

    def time_win_to_ls(self):
        """compute the spacial locality (ls) of the current time-window"""
        # do not run if window has been flushed
        if self.time_window is None:
            return
        if self.verb:
            print('SingleThreadLocality.time_win_to_ls():')
            print(f'time_window[{len(self.time_window)}]: {self.time_window}')
        # trim window from left
        ln = len(self.time_window)
        while ln > st.cache.cache_size:
            if self.verb:
                print('time_window.popleft()')
            self.time_window.popleft()
            ln -= 1

        if self.verb:
            print(f'time_window[{len(self.time_window)}]')

        flat_time_win = list(self.time_window)

        # replicate last locality so that new appending index == last access
        # while len(self.Ls) < self.time_last_access:
        #     if self.verb:
        #         print(f'Ls.append(Ls[-1])')
        #     self.Ls.append(self.Ls[-1])

        # if the window only has one element, then locality is undefined, assign -1.
        if len(flat_time_win) < 2:
            self.Ls[self.time_last_access] = -1
            if self.verb:
                print(f'>> Ls[{len(self.Ls)-1}] = {self.Ls[-1]}')
            return

        # compute ls(flat_time_win)=(B-min(B,ds))/B, where ds = addrB - addrA
        flat_time_win.sort()
        ls = flat_time_win # in-place
        B = st.cache.line_size
        for i,addr1,addr2 in zip(range(len(ls)-1),
                                 flat_time_win[:-1],
                                 flat_time_win[1:]):
            ls[i]= (B - min(B, addr2-addr1))/B
            if self.verb:
                print(f'ls[{i}] = {float(ls[i]):04.3f} = ({B} - min({B},{addr2}-{addr1}))/{B}')
        del ls[-1]

        # append avg(ls) to self.Ls
        avg_ls = sum(ls) / len(ls)
        self.Ls[self.time_last_access] = 100*avg_ls # as percentage
        if self.verb:
            print(f'>> Ls[{len(self.Ls)-1}] = {float(avg_ls):04.3f} = {sum(ls)}/{len(ls)}')
        return

        
    def all_sp_win_to_lt(self):
        """compute the temporal locality of all spacial windows (blocks)"""
        # if already called, just return
        if len(self.Lt) > 0:
            return
        # create Lt based on the total range of blocks in the memory studied
        tag,idx,_ = AddrFmt.split(st.map.start_addr)
        # block_first = st.map.start_addr >> st.cache.bits_offset
        block_first = (tag << st.cache.bits_set) | idx
        tag,idx,_ = AddrFmt.split(st.map.start_addr + st.map.mem_size-1)
        block_last = (tag << st.cache.bits_set) | idx
        tot_num_blocks = block_last - block_first + 1
        self.Lt = [-1] * tot_num_blocks

        # obtain the list of all used blocks ids (tag,set_index)
        used_blocks = list(self.space_by_blocks.keys())
        used_blocks.sort()

        # compute lt for each space window (that is, for each block)
        C = st.cache.cache_size
        for tag,idx in used_blocks:
            blk_idx = ((tag << st.cache.bits_set) | idx) - block_first
            flat_space_win = self.space_by_blocks[(tag,idx)]
            lt = flat_space_win # in-place
            if len(flat_space_win) < 2:
                self.Lt[blk_idx] = 0
                continue
            for i,t1,t2 in zip(range(len(lt)-1),
                               flat_space_win[:-1],
                               flat_space_win[1:]):
                lt[i] = (C - min(C, t2-t1)) / C
            del lt[-1]

            # save avg(lt)
            avg_lt = sum(lt) / len(lt)
            self.Lt[blk_idx] = 100 * avg_lt # as percentage
        return


    def flush_time_win(self):
        self.time_win_to_ls()
        self.time_window = None
        return

    
    def add_access(self, access):
        # spacial locality across time
        if access.time > self.time_last_access:
            self.time_win_to_ls()
        for offset in range(access.size):
            self.time_window.append(access.addr-st.map.start_addr+offset)

        # temporal locality across space (for now, just filling)
        for offset in range(access.size):
            tag,idx,_ = AddrFmt.split(access.addr+offset)
            if (tag,idx) not in self.space_by_blocks:
                self.space_by_blocks[(tag,idx)] = []
            self.space_by_blocks[(tag,idx)].append(access.time)

        self.time_last_access = access.time


class Locality:
    def __init__(self, shared_X=None, hue=325, verb=None):
        self.X = shared_X if shared_X is not None else \
            [i for i in range(st.map.time_size)]
        self.hue = hue
        self.verb = verb if verb is not None else st.verb
        self.name = 'Locality'
        self.about = ('Spacial locality across Time, and Temporal locality '
                      'across space')

        ## Spacial locality across time
        self.time_window = deque() #of the size of the cache.
        self.time_last_access = 0
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
        """if this access belongs to a new time, compute ls for current time
        window, and then append the current access to the time_window queue"""

        ## SPACIAL LOCALITY ACROSS TIME
        # if this access has newer time, compute ls for the current window
        if access.time > self.time_last_access:
            self.time_window_to_ls(access.time)
            self.time_last_access = access.time

        # append accessed bytes to time_window
        for offset in range(access.size):
            self.time_window.append(access.addr-st.map.start_addr+offset)

        # trim time_window from back if it is larger than the cache size.
        while len(self.time_window) > st.cache.cache_size:
            self.time_window.popleft()

        ## TEMPORAL LOCALITY ACROSS SPACE
        # for now just append access times to the list of each memory block
        for offset in range(access.size):
            tag,idx,_ = AddrFmt.split(access.addr+offset)
            if (tag,idx) not in self.space_by_blocks:
                self.space_by_blocks[(tag,idx)] = []
            self.space_by_blocks[(tag,idx)].append(access.time)
        return

    def time_window_to_ls(self, curr_time):
        """compute differences and add a new value to Ls"""
        # obtain a flat window of the last accessed addresses
        flat_time_window = list(self.time_window)

        # if only one access, there is no deltas to compute. assign Ls[t] = -1
        if len(flat_time_window) < 2:
            self.Ls[self.time_last_access] = -1
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
        # Replicate that value up to right before the current time
        avg_ls = 100 * sum(ls) / len(ls)
        for t in range(self.time_last_access, curr_time):
            self.Ls[t] = avg_ls
        #self.Ls[self.time_last_access] = avg_ls
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
        self.time_window_to_ls(st.map.time_size)
        self.all_space_window_to_lt()

        # create palette for threads
        pal = Palette(hue=self.hue, lightness=[25,80], alpha=[100,60])

        # plot Spacial and Temporal locality tools
        self.plot_Ls(top_tool, pal)
        self.plot_Lt(top_tool, pal)
        return


    def plot_Ls(self, top_tool, pal):
        # create figure and tool axes
        fig,axes = plt.subplots(figsize=(st.plot.width, st.plot.height))

        # pad X and Y=Ls axes for better visualization
        padding = 0.5
        X = [self.X[0]-padding] + self.X + [self.X[-1]+padding]
        Ls = [self.Ls[0]] + self.Ls + [self.Ls[-1]]

        # draw space locality across time
        axes.fill_between(X, -1, Ls, color=pal[0][0], facecolor=pal[0][1],
                          linewidth=1.2, step='mid', zorder=2)

        # set plot limits
        axes.set_xlim(X[0], X[-1])
        axes.set_ylim(0-padding, 100+padding)

        # Y axis label, ticks, and grid
        axes.yaxis.set_label_position('left')
        axes.set_ylabel(self.psLs.ylab, color=pal.fg, labelpad=3.5)
        percentages = list(range(100 + 1)) # from 0 to 100
        y_ticks = create_up_to_n_ticks(percentages, base=10, n=11)
        axes.tick_params(axis='y', which='both', left=True, right=False,
                         labelleft=True, labelright=False,
                         width=st.plot.grid_main_width, colors=pal.fg)
        axes.set_yticks(y_ticks)
        axes.grid(axis='y', which='both',
                  alpha=0.1, color=pal.fg, zorder=1,
                  linewidth=st.plot.grid_main_width,
                  linestyle=st.plot.grid_main_style)

        # plot map
        map_axes = axes.twinx()
        top_tool.plot(axes=map_axes)

        # X axis label, ticks and grid
        axes.set_xlabel(self.psLs.xlab, color='k', labelpad=3.5)
        axes.tick_params(axis='x', bottom=True, top=False, labelbottom=True,
                         rotation=90, width=st.plot.grid_other_width)
        x_ticks = create_up_to_n_ticks(self.X, base=10,
                                       n=st.plot.max_xtick_count)
        axes.set_xticks(x_ticks)
        axes.grid(axis='x', which='both',
                  alpha=0.1, color='k', zorder=1,
                  linestyle=st.plot.grid_other_style,
                  linewidth=st.plot.grid_other_width)

        # setup title
        title_string = f'{self.psLs.title}: {st.plot.prefix}'
        if self.psLs.subtit:
            title_string += f'. ({self.psLs.subtit})'
        axes.set_title(title_string, fontsize=10, pad=st.plot.img_title_vpad)

        # save image
        save_fig(fig, self.psLs.title, self.psLs.suffix)
        return


    def plot_Lt(self, top_tool, pal):
        # create figure and tool axes
        fig,axes = plt.subplots(figsize=(st.plot.width, st.plot.height))

        # pad Y and X=Lt axes for better visualization
        # Y = list of memory blocks. always starting from 0
        padding = 0.5

        Y = [i for i in range(st.map.mem_size >> st.cache.bits_off)]
        Y = [Y[0]-padding] + Y + [Y[-1]+padding]
        Lt = [self.Lt[0]] + self.Lt + [self.Lt[-1]]

        # draw time locality across space
        axes.fill_betweenx(Y, Lt, -1, color=pal[0][0], facecolor=pal[0][1],
                           linewidth=1.2, step='mid', zorder=2)

        # set plot limits
        axes.set_ylim(Y[0], Y[-1])
        axes.set_xlim(0-padding, 100+padding)

        # Y axis label, ticks, and grid
        axes.yaxis.set_label_position('left')
        axes.set_ylabel(self.psLt.ylab, color='k', labelpad=3.5)
        y_ticks = create_up_to_n_ticks(Y[1:-1], base=10, n=11)
        axes.tick_params(axis='y', which='both', left=True, right=False,
                         labelleft=True, labelright=False,
                         width=st.plot.grid_other_width)
        axes.set_yticks(y_ticks)
        axes.grid(axis='y', which='both',
                  alpha=0.1, color='k', zorder=1,
                  linewidth=st.plot.grid_other_width,
                  linestyle=st.plot.grid_other_style)

        # X axis label, ticks and grid
        axes.set_xlabel(self.psLt.xlab, color=pal.fg, labelpad=3.5)
        percentages = list(range(100 + 1)) # from 0 to 100
        axes.tick_params(axis='x', bottom=True, top=False, labelbottom=True,
                         rotation=-90, colors=pal.fg, width=2)
        x_ticks = create_up_to_n_ticks(percentages, base=10, n=11)
        axes.set_xticks(x_ticks)
        axes.grid(axis='x', which='both',
                   alpha=0.1, color=pal.fg, zorder=1,
                  linewidth=st.plot.grid_main_width,
                  linestyle=st.plot.grid_main_style)

        axes.invert_yaxis()

        # plot map
        map_axes = fig.add_axes(axes.get_position(), frameon=False)
        top_tool.plot(axes=map_axes)

        # setup title
        title_string = f'{self.psLt.title}: {st.plot.prefix}'
        if self.psLt.subtit:
            title_string += f'. ({self.psLt.subtit})'
        axes.set_title(title_string, fontsize=10, pad=st.plot.img_title_vpad)

        # save image
        save_fig(fig, self.psLt.title, self.psLt.suffix)

        return










    # def get_extent(self):
    #     # fine tune margins to place each quadrilateral of the imshow()
    #     # right on the tick. So adding a 0.5 margin at each side.
    #     left_edge = self.X[0] - 0.5
    #     right_edge = self.X[-1] + 0.5
    #     bottom_edge = 0 - 0.5
    #     top_edge = 100 + 0.5 # 100% + a little margin
    #     extent = (left_edge, right_edge, bottom_edge, top_edge)
    #     return extent

    # def other_plot(self, axes, basename='locality', extent=None):
    #     for thread in self.buffer_traces:
    #         self.buffer_traces[thread].create_plotable_data(self.X)

    #     # set plot limits
    #     # extent = extent if extent != None else self.get_extent()
    #     # axes.set_xlim(extent[0], extent[1])
    #     # axes.set_ylim(extent[2], extent[3])

    #     # draw the curve and area below it for each thread
    #     for thread in self.buffer_traces:
    #         Y = self.buffer_traces[thread].Y
    #         # axes.step(self.X, Y, color=self.plot_color_line,
    #         #           linewidth=1.2, where='mid', zorder=2)
    #         # axes.fill_between(self.X, -1, Y, color='none',
    #         #                   facecolor=self.plot_color_fill,
    #         #                   linewidth=1.2, step='mid', zorder=1)

    #     # setup title
    #     # axes.set_title(f'{self.plot_title}: {basename}. '
    #     #                f'({self.plot_subtitle})', fontsize=10)

    #     # setup X ticks, labels, and grid
    #     axes.tick_params(axis='x', bottom=True, top=False, labelbottom=True,
    #                      rotation=90)
    #     x_ticks = create_up_to_n_ticks(self.X, base=10, n=20)
    #     axes.set_xticks(x_ticks)
    #     axes.set_xlabel(self.plot_x_label)
    #     axes.grid(axis='x', which='both', linestyle='-', alpha=0.1,
    #               color='k', linewidth=0.5, zorder=2)

    #     # setup Y ticks, labels, and grid
    #     axes.tick_params(axis='y', which='both', left=True, right=False,
    #                      labelleft=True, labelright=False,
    #                      colors=self.plot_color_text)
    #     percentages = list(range(100 + 1)) # from 0 to 100
    #     y_ticks = create_up_to_n_ticks(percentages, base=10, n=11)
    #     axes.set_yticks(y_ticks)
    #     axes.yaxis.set_label_position('left')
    #     axes.set_ylabel(self.plot_y_label, color=self.plot_color_text,
    #                     labelpad=3.5)
    #     axes.grid(axis='y', which='both', linestyle='-', alpha=0.1,
    #               color=self.plot_color_line, linewidth=0.5, zorder=3)

    #     return









# class BufferedTrace:
#     cache_size = 64*64*512
#     block_size = 64
#     def __init__(self):
#         # buffer with incoming accesses, and total bytes in it
#         self.buffer = deque()
#         self.buffer_bytes = 0
#         # locality of each window.
#         self.locality = []
#         # data ready to plot
#         self.Y = []


#     def add_access(self, access):
#         """Add a memory access to this thread's trace and create
#         a new window if there is enough accesses in the buffer."""
#         # append access to buffer
#         self.buffer.append(access)
#         win_id = access.time
#         self.buffer_bytes += access.size
#         # While there are enough bytes accessed in the buffer, create a window
#         while self.buffer_bytes > BufferedTrace.cache_size:
#             # trim buffer from the left until it fits in the cache
#             oldest_access = self.buffer.popleft()
#             self.buffer_bytes -= oldest_access.size
#         self.locality.append((win_id, self._win_dist_loc()))

#     def _win_dist_loc(self):
#         """Compute the locality value for a window of memory accesses.
#         Bind the value to the last instruction of the window."""
#         # create window of accesses from the access buffer.
#         win_acc = []
#         for acc in self.buffer:
#             for off in range(acc.size):
#                 win_acc.append(acc.addr+off)
#         win_acc = sorted(win_acc)
#         # compute neighbors distances within this window.
#         win_dis = [b-a for a,b in zip(win_acc[:-1],win_acc[1:])]
#         # compute locality based on neighbor distances.
#         loc_val = sum(max(0,
#                           (BufferedTrace.block_size - d) /
#                           (BufferedTrace.block_size * len(win_dis))
#                           )
#                       for d in win_dis
#                       )
#         # return tuple of instruction at the end of the window and locality
#         # value of this window.
#         return loc_val


#     def create_plotable_data(self, X):
#         # fill potential gaps while creating the Y array.
#         # The Y array ranges from 0 to 100.
#         self.Y = [0] * len(X)
#         for instr_id,val in self.locality:
#             self.Y[instr_id] = 100 * val


# class OldLocality(GenericInstrument):
#     def __init__(self, instr_counter, cache_size, block_size, map_metadata,
#                  verb=False):
#         super().__init__(instr_counter, verb=False)
#         BufferedTrace.cache_size = cache_size
#         BufferedTrace.block_size = block_size
        
#         # each thread has its own access trace.
#         self.buffer_traces = {}

#         self.plot_name_sufix  = '_plot-01-locality'
#         self.plot_title       = 'Locality'
#         self.plot_subtitle    = 'higher is better'
#         self.plot_y_label     = 'Degree of locality [%]'
#         self.plot_x_label     = 'Instruction'
#         self.plot_color_text  = '#8B0E57FF' # fuchsia dark
#         self.plot_color_line  = '#A2106588' # fuchsia
#         self.plot_color_fill  = '#A2106511' # Fuchsia semi transparent
#         self.plot_color_bg    = '#FFFFFF00' # transparent

#     def register_access(self, access):
#         if not self.enabled:
#             return
#         if access.thread not in self.buffer_traces:
#             self.buffer_traces[access.thread] = BufferedTrace()
#         self.buffer_traces[access.thread].add_access(access)

#     def get_extent(self):
#         # fine tune margins to place each quadrilateral of the imshow()
#         # right on the tick. So adding a 0.5 margin at each side.
#         left_edge = self.X[0] - 0.5
#         right_edge = self.X[-1] + 0.5
#         bottom_edge = 0 - 0.5
#         top_edge = 100 + 0.5 # 100% + a little margin
#         extent = (left_edge, right_edge, bottom_edge, top_edge)
#         return extent

#     def plot(self, axes, basename='locality', extent=None):
#         for thread in self.buffer_traces:
#             self.buffer_traces[thread].create_plotable_data(self.X)

#         # set plot limits
#         extent = extent if extent != None else self.get_extent()
#         axes.set_xlim(extent[0], extent[1])
#         axes.set_ylim(extent[2], extent[3])

#         # draw the curve and area below it for each thread
#         for thread in self.buffer_traces:
#             Y = self.buffer_traces[thread].Y
#             axes.step(self.X, Y, color=self.plot_color_line,
#                       linewidth=1.2, where='mid', zorder=2)
#             axes.fill_between(self.X, -1, Y, color='none',
#                               facecolor=self.plot_color_fill,
#                               linewidth=1.2, step='mid', zorder=1)

#         # setup title
#         axes.set_title(f'{self.plot_title}: {basename}. '
#                        f'({self.plot_subtitle})', fontsize=10)

#         # setup X ticks, labels, and grid
#         axes.tick_params(axis='x', bottom=True, top=False, labelbottom=True,
#                          rotation=90)
#         x_ticks = create_up_to_n_ticks(self.X, base=10, n=20)
#         axes.set_xticks(x_ticks)
#         axes.set_xlabel(self.plot_x_label)
#         axes.grid(axis='x', which='both', linestyle='-', alpha=0.1,
#                   color='k', linewidth=0.5, zorder=2)

#         # setup Y ticks, labels, and grid
#         axes.tick_params(axis='y', which='both', left=True, right=False,
#                          labelleft=True, labelright=False,
#                          colors=self.plot_color_text)
#         percentages = list(range(100 + 1)) # from 0 to 100
#         y_ticks = create_up_to_n_ticks(percentages, base=10, n=11)
#         axes.set_yticks(y_ticks)
#         axes.yaxis.set_label_position('left')
#         axes.set_ylabel(self.plot_y_label, color=self.plot_color_text,
#                         labelpad=3.5)
#         axes.grid(axis='y', which='both', linestyle='-', alpha=0.1,
#                   color=self.plot_color_line, linewidth=0.5, zorder=3)

#         return
