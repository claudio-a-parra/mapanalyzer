import sys
from collections import deque

from util import AddrFmt, create_up_to_n_ticks
from settings import Settings as st

class SingleThreadLocality:
    def __init__(self, curr_time):
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
        # trim window from left
        print('tm_win_to_ls()')
        while len(self.time_window) > st.cache.cache_size:
            self.time_window.popleft()
        flat_time_win = list(self.time_window)
        
        # if the window only has one element, then locality is zero.
        if len(flat_time_win) < 2:
            while len(self.Ls) < self.time_last_access:
                self.Ls.append(0)
            self.Ls.append(0)
            print(f'Ls[{len(self.Ls)-1}] = {self.Ls[-1]}')
            return

        # compute ls(flat_time_win)=(B-min(B,ds))/B, where ds = addrB - addrA
        flat_time_win.sort()
        ls = flat_time_win # in-place
        B = st.cache.line_size
        for i,addr1,addr2 in zip(range(len(ls)-1),
                                 flat_time_win[:-1],
                                 flat_time_win[1:]):
            ls[i]= (B - min(B, addr2-addr1))/B
            print(f'ls[{i}] = {float(ls[i]):04.3f} = ({B} - min({B},{addr2}-{addr1}))/{B}')
        del ls[-1]

        # append avg(ls) to self.Ls
        avg_ls = sum(ls) / len(ls)
        while len(self.Ls) < self.time_last_access:
            self.Ls.append(0)
        self.Ls.append(avg_ls)
        print(f'Ls[{len(self.Ls)-1}] = {float(avg_ls):04.3f} = {sum(ls)}/{len(ls)}')
        return

        
    def all_sp_win_to_lt(self):
        """compute the temporal locality of all spacial windows (blocks)"""

        # create Lt based on the total range of blocks in the memory studied
        tag,idx,_ = AddrFmt.split(st.map.start_addr)
        block_first = (tag << st.cache.bits_set) | idx
        tag,idx,_ = AddrFmt.split(st.map.start_addr + st.map.mem_size-1)
        block_last = (tag << st.cache.bits_set) | idx
        tot_num_blocks = block_last - block_first + 1
        self.Lt = [0] * tot_num_blocks

        # obtain the list of all used blocks ids (tag,set_index)
        used_blocks = list(self.space_by_blocks.keys())
        used_blocks.sort()

        # for i,(tag,idx) in zip(range(len(used_blocks)),used_blocks):
        #     used_blocks[i] = (tag << st.cache.bits_set) | idx

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
            self.Lt[blk_idx] = avg_lt
    
    def add_access(self, access):
        # spacial locality across time
        if access.time > self.time_last_access:
            self.tm_win_to_ls()
        for offset in range(access.size):
            self.time_window.append(access.addr+offset)

        # temporal locality across space (for now, just filling)
        for offset in range(access.size):
            tag,idx,_ = AddrFmt.split(access.addr+offset)
            if (tag,idx) not in self.space_by_blocks:
                self.space_by_blocks[(tag,idx)] = []
            self.space_by_blocks[(tag,idx)].append(access.time)

        self.time_last_access = access.time

class Locality:
    def __init__(self, shared_X=None):
        if shared_X is None:
            self.X = [i for i in range(st.map.time_size)]
        else:
            self.x = shared_X

        # each thread has its own locality.
        self.thr_traces = {}

        self.plot_name_sufix  = '_plot-01-locality'
        self.plot_title       = 'Locality'
        self.about            = 'Temporal and Spacial locality'
        self.plot_subtitle    = 'higher is better'
        self.plot_y_label     = 'Degree of locality [%]'
        self.plot_x_label     = 'Instruction'
        self.plot_color_text  = '#8B0E57FF' # fuchsia dark
        self.plot_color_line  = '#A2106588' # fuchsia
        self.plot_color_fill  = '#A2106511' # Fuchsia semi transparent
        self.plot_color_bg    = '#FFFFFF00' # transparent

    def describe(self, ind=''):
        print(f'{ind}{self.plot_title}: {self.about}')
        return

    def add_access(self, access):
        print()
        print()
        print(f'Access: {access}')
        if access.thread not in self.thr_traces:
            self.thr_traces[access.thread] = SingleThreadLocality(access.time)
        self.thr_traces[access.thread].add_access(access)

    def plot(self, axes, basename='locality'):
        for thr_idx in self.thr_traces:
            thr = self.thr_traces[thr_idx]
            thr.all_sp_win_to_lt()
            print(f'thr {thr_idx}:\n')
            print(f'Ls:')
            for l in thr.Ls:
                print(f'    {float(l):04.3f}')
            print(f'Lt:')
            for l in thr.Lt:
                print(f'    {float(l):04.3f}')
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

    # def plot(self, axes, basename='locality', extent=None):
    #     for thread in self.buffer_traces:
    #         self.buffer_traces[thread].create_plotable_data(self.X)

    #     # set plot limits
    #     extent = extent if extent != None else self.get_extent()
    #     axes.set_xlim(extent[0], extent[1])
    #     axes.set_ylim(extent[2], extent[3])

    #     # draw the curve and area below it for each thread
    #     for thread in self.buffer_traces:
    #         Y = self.buffer_traces[thread].Y
    #         axes.step(self.X, Y, color=self.plot_color_line,
    #                   linewidth=1.2, where='mid', zorder=2)
    #         axes.fill_between(self.X, -1, Y, color='none',
    #                           facecolor=self.plot_color_fill,
    #                           linewidth=1.2, step='mid', zorder=1)

    #     # setup title
    #     axes.set_title(f'{self.plot_title}: {basename}. '
    #                    f'({self.plot_subtitle})', fontsize=10)

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
