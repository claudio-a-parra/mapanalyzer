import sys
from collections import deque
import matplotlib.pyplot as plt

from util import AddrFmt, create_up_to_n_ticks, PlotStrings, save_fig
from palette import Palette
from settings import Settings as st

class SingleThreadLocality:
    def __init__(self, curr_time, verb=False):
        self.verb = verb
        # temporal window; time of last access; spacial locality across time
        self.time_window = deque()
        self.time_last_access = curr_time
        self.Ls = []

        # block->acc_time; space window (block); temporal locality across space
        self.space_by_blocks = {}
        self.space_window = deque()
        self.Lt = []
        
    def tm_win_to_ls(self):
        """compute the spacial locality (ls) of the current time-window"""
        # do not run if window has been flushed
        if self.time_window is None:
            return
        if self.verb:
            print('SingleThreadLocality.tm_win_to_ls():')
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
        while len(self.Ls) < self.time_last_access:
            if self.verb:
                print(f'Ls.append(Ls[-1])')
            self.Ls.append(self.Ls[-1])

        # if the window only has one element, then locality is undefined, assign -1.
        if len(flat_time_win) < 2:
            self.Ls.append(-1)
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
        self.Ls.append(100*avg_ls) # as percentage
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

            # append avg(lt)
            avg_lt = sum(lt) / len(lt)
            self.Lt[blk_idx] = 100 * avg_lt # as percentage
        return


    def flush_time_win(self):
        self.tm_win_to_ls()
        self.time_window = None
        return

    
    def add_access(self, access):
        # spacial locality across time
        if access.time > self.time_last_access:
            self.tm_win_to_ls()
        for offset in range(access.size):
            self.time_window.append(access.addr+offset-st.map.start_addr)

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

        # each thread has its own locality.
        self.thr_traces = {}

        self.name = 'Locality'
        self.about = ('Spacial locality across Time, and Temporal locality '
                      'across space')
        self.Ls = PlotStrings(
            title  = 'Spacial Locality across Time',
            xlab   = 'Time',
            ylab   = 'Degree of Spacial Locality',
            suffix = '_plot-01-locality-Ls',
            subtit = 'higher is better')
        self.Lt = PlotStrings(
            title  = 'Temporal Locality across Space',
            xlab   = 'Degree of Temporal Locality',
            ylab   = 'Space [blocks]',
            suffix = '_plot-02-locality-Lt',
            subtit = 'higher is better')

        self.Lst = PlotStrings(
            title  = 'Space-Time Locality',
            xlab   = 'Space [blocks]',
            ylab   = 'Time',
            suffix = '_plot-03-locality-Lst',
            subtit  = 'higher is better')
        return


    def add_access(self, access):
        if self.verb:
            print()
            print()
            print(f'Locality.add_access({access})')
        if access.thread not in self.thr_traces:
            self.thr_traces[access.thread] = \
                SingleThreadLocality(access.time, self.verb)
        self.thr_traces[access.thread].add_access(access)
        return


    def describe(self, ind=''):
        print(f'{ind}{self.name:{st.plot.ui_name_hpad}}: {self.about}')
        return


    def plot_Ls(self, top_tool, pal):
        # create figure and tool axes
        fig,axes = plt.subplots(figsize=(st.plot.width, st.plot.height))
        threads = list(self.thr_traces.keys())
        threads.sort()

        padding = 0.5
        X = [-padding] + self.X + [self.X[-1]+padding]
        for thr_idx,thr_id in enumerate(threads):
            thr = self.thr_traces[thr_idx]

            # Draw spacial locality across time
            Ls = [thr.Ls[0]] + thr.Ls + [thr.Ls[-1]]
            # axes.step(X, Ls,
            #           color=pal[thr_idx][0],
            #           linewidth=1.2, where='mid', zorder=2)
            axes.fill_between(X, -1, Ls, color=pal[thr_idx][0],
                              facecolor=pal[thr_idx][1],
                              linewidth=1.2, step='mid', zorder=2)

        # set plot limits
        axes.set_xlim(self.X[0]-padding, self.X[-1]+padding)
        axes.set_ylim(0-padding, 100+padding)

        # Y axis label, ticks, and grid
        axes.yaxis.set_label_position('left')
        axes.set_ylabel(self.Ls.ylab, color=pal.fg, labelpad=3.5)
        percentages = list(range(100 + 1)) # from 0 to 100
        y_ticks = create_up_to_n_ticks(percentages, base=10, n=11)
        axes.tick_params(axis='y', which='both', left=True, right=False,
                         labelleft=True, labelright=False, width=3,
                         colors=pal.fg)
        axes.set_yticks(y_ticks)
        axes.grid(axis='y', which='both', linestyle='-', alpha=0.1,
                  color=pal.fg, linewidth=3, zorder=1)

        # plot map
        map_axes = axes.twinx()
        top_tool.plot(axes=map_axes)

        # X axis label, ticks and grid
        axes.set_xlabel(self.Ls.xlab, color='k', labelpad=3.5)
        axes.tick_params(axis='x', bottom=True, top=False, labelbottom=True,
                         rotation=90, width=0.33)
        x_ticks = create_up_to_n_ticks(self.X, base=10, n=st.plot.max_xtick_count)
        axes.set_xticks(x_ticks)
        axes.grid(axis='x', which='both', linestyle='-', alpha=0.1,
                  color='k', linewidth=0.33, zorder=1)

        # setup title
        title_string = f'{self.Ls.title}: {st.plot.prefix}'
        if self.Ls.subtit:
            title_string += f'. ({self.Ls.subtit})'
        axes.set_title(title_string, fontsize=10, pad=st.plot.img_title_vpad)

        # save image
        save_fig(fig, self.Ls.title, self.Ls.suffix)

        return


    def plot_Lt(self, top_tool, pal):
        # create figure and tool axes
        fig,axes = plt.subplots(figsize=(st.plot.width, st.plot.height))
        threads = list(self.thr_traces.keys())
        threads.sort()

        padding = 0.5
        #mem_blocks = [i for i,_ in enumerate(self.thr_traces[0].Lt)]
        block_last_off = (st.map.mem_size) >> st.cache.bits_off
        mem_blocks = [i for i in range(block_last_off)]
        for thr_idx,thr_id in enumerate(threads):
            thr = self.thr_traces[thr_idx]

            # Draw temporal locality across space
            Lt = [thr.Lt[i] for i in mem_blocks]
            mem_blocks = [mem_blocks[0]-padding] +\
                mem_blocks +\
                [mem_blocks[-1]+padding]
            Lt = [Lt[0]] + Lt + [Lt[-1]]
            floor = [-1 for _ in mem_blocks]
            # axes.step(block_loc, mem_blocks,
            #           color=pal[thr_idx][0],
            #           linewidth=1.2, where='mid', zorder=2, marker='.')
            # axes.plot(block_loc, mem_blocks,
            #           color=pal[thr_idx][0],
            #           linewidth=1.2, zorder=2, marker='o')

            axes.fill_betweenx(mem_blocks, Lt, floor,
                               color=pal[thr_idx][0],
                               facecolor=pal[thr_idx][1],
                               linewidth=1.2, step='mid', zorder=2)

        # set plot limits
        axes.set_xlim(0-padding, 100+padding)
        axes.set_ylim(mem_blocks[0], mem_blocks[-1])

        # setup title
        title_string = f'{self.Lt.title}: {st.plot.prefix}'
        if self.Lt.subtit:
            title_string += f'. ({self.Lt.subtit})'
        axes.set_title(title_string, fontsize=10, pad=st.plot.img_title_vpad)

        # Y axis label, ticks, and grid
        axes.yaxis.set_label_position('left')
        axes.set_ylabel(self.Lt.ylab, color='k', labelpad=3.5)
        y_ticks = create_up_to_n_ticks(mem_blocks[1:-1], base=10, n=11)
        axes.tick_params(axis='y', which='both', left=True, right=False,
                         labelleft=True, labelright=False, width=0.33)
        axes.set_yticks(y_ticks)
        axes.grid(axis='y', which='both', linestyle='-', alpha=0.1,
                  color='k', linewidth=0.33, zorder=1)

        # X axis label, ticks and grid
        axes.set_xlabel(self.Lt.xlab, color=pal.fg, labelpad=3.5)
        percentages = list(range(100 + 1)) # from 0 to 100
        axes.tick_params(axis='x', bottom=True, top=False, labelbottom=True,
                         rotation=-90, colors=pal.fg, width=2)
        x_ticks = create_up_to_n_ticks(percentages, base=10, n=11)
        axes.set_xticks(x_ticks)
        axes.grid(axis='x', which='both', linestyle='-', alpha=0.1,
                  color=pal.fg, linewidth=3, zorder=1)

        axes.invert_yaxis()

        # plot map
        map_axes = fig.add_axes(axes.get_position(), frameon=False)
        top_tool.plot(axes=map_axes)

        # save image
        save_fig(fig, self.Lt.title, self.Lt.suffix)

        return


    def plot_Lst(self, top_tool, pal):
        # I AM HERE
        pass


    def plot(self, top_tool=None):
        # finish up computations
        threads = list(self.thr_traces.keys())
        threads.sort()
        for thr_idx in threads:
            thr = self.thr_traces[thr_idx]
            thr.flush_time_win()
            thr.all_sp_win_to_lt()

        # create palette for threads
        pal = Palette(hue=self.hue, lightness=[25,80], hue_count=len(threads),
                      alpha=80)

        self.plot_Ls(top_tool, pal)
        self.plot_Lt(top_tool, pal)
        self.plot_Lst(top_tool, pal)

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
