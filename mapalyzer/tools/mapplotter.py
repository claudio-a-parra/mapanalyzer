#!/usr/bin/env python3
import sys
from collections import deque
from matplotlib.colors import ListedColormap
from matplotlib.ticker import FuncFormatter #to make a custom tick formatter
import humanize # to convert raw byte count to KiB, MiB...

from .generic import create_up_to_n_ticks

class Map:
    def __init__(self, instr_counter, map_metadata, plot_max_res=2048,
                 verb=False):
        # obtain map file metadata
        self.verb = verb
        self.base_addr = map_metadata.base_addr
        self.mem_size = map_metadata.mem_size
        self.thread_count = map_metadata.thread_count
        self.event_count = map_metadata.event_count
        self.time_size = map_metadata.time_size
        self.X = [i for i in range(self.time_size)]

        # if mem_size or time_size are larger than the max resolution, keep
        # diving them until they fit in a square of plot_max_res^2
        ap_matrix_height = self.mem_size
        ap_matrix_height = self.mem_size if self.mem_size <= plot_max_res else plot_max_res
        ap_matrix_width = self.time_size if self.time_size <= plot_max_res else plot_max_res

        # cols: whole memory snapshot at a given instruction
        # rows: byte state across all instructions
        self.access_matrix = [[0] * ap_matrix_width
                              for _ in range(ap_matrix_height)]

        self.plot_name_sufix = '_plot-00-map'
        self.plot_title = 'Memory Access Pattern'
        self.plot_subtitle = None
        self.plot_y_label = 'Space [bytes]'
        self.plot_x_label = 'Instruction'
        self.plot_min = None
        self.plot_max = None
        self.plot_color_text =  '#009900'
        self.plot_color_palette = [ #    read , write
            #('#4CB24C', '#B24C4C'), #t0: dusty green and red
            ('#00BB00', '#BB0000'), #t1: green, red
            ('#0000BB', '#BB00BB'), #t2: blue , purple
            ]
        self.plot_color_bg =    '#FFFFFF00' # transparent


    def add_access(self, access):
        """The idea is to take an access happening at (addr, time), and
        map it to (y,x) in self.access_matrix."""
        # negative: read access, positive: write access
        # abs value: thread ID + 1 (to leave 0 for no-op)
        access_code = access.thread + 1
        if access.event == 'R':
            access_code *= -1

        # properly register accesses of more than 1 byte.
        for byte in range(access.size):
            # obtain the original coordinates
            addr = access.addr - self.base_addr + byte
            time = access.time

            # get percentage (from first to last possible address or time)
            max_real_addr = self.mem_size - 1
            max_real_time = self.time_size - 1
            propor_addr = addr / max_real_addr
            propor_time = time / max_real_time

            # get maximum value for the mapped address and time
            max_mapped_addr = len(self.access_matrix) - 1
            max_mapped_time = len(self.access_matrix[0]) - 1

            # now map addr x time to the access_matrix
            mapped_addr = round(propor_addr * max_mapped_addr)
            mapped_time = round(propor_time * max_mapped_time)

            if self.verb and byte == 0:
                print(f'map: [{addr},{time}] -> [{mapped_time},{mapped_addr}]')
            # store the access. add 1 so zero values are interpreted as 'empty'
            self.access_matrix[mapped_addr][mapped_time] = access_code


    def plot(self, axes, basename='map', extent=(0,10,0,10), title=False):

        # Memory Access Pattern color-map creation
        # threads_palette = [self.plot_color_read, self.plot_color_write]
        threads_bg = self.plot_color_bg
        #colors_pairs_needed = self.thread_count # two, R and W, colors per thread

        # Access codes:
        #  -X : thread (X-1) read
        #   X : thread (X-1) write
        #   0 : no operation.
        # Then, the palette must match the negative and positive values to the
        # read/write colors of the thread.
        thr_palette = self.plot_color_palette
        thr_bg = self.plot_color_bg
        thr_count = self.thread_count
        if thr_count > len(thr_palette):
            print(f'[!] Warning: The Access Pattern has more threads '
                  'than colors available to plot. Different threads will '
                  'share colors.')
        read_palette = [ thr_palette[i%len(thr_palette)][0]
                         for i in range(thr_count)]
        write_palette = [ thr_palette[i%len(thr_palette)][1]
                          for i in range(thr_count)]
        cmap = ListedColormap(list(reversed(read_palette)) + [thr_bg] +
                              write_palette)

        # plot the trace
        extent = (self.X[0]-0.5, self.X[-1]+0.5, 0-0.5, self.mem_size-0.5)
        axes.imshow(self.access_matrix, cmap=cmap, origin='lower',
                    aspect='auto', zorder=1, extent=extent,
                    vmin=-thr_count, vmax=thr_count)

        # setup title
        if title:
            title_string = f'{self.plot_title}: {basename}'
            if self.plot_subtitle != None:
                title_string += f'\n({self.plot_subtitle})'
            axes.set_title(title_string, fontsize=10)


        # setup X ticks, labels, and grid
        axes.tick_params(axis='x', bottom=True, top=False, labelbottom=True,
                         rotation=90)
        num_ticks = 61 #20 # DEBUG
        x_ticks = create_up_to_n_ticks(self.X, base=10, n=num_ticks)
        axes.set_xticks(x_ticks)
        axes.set_xlabel(self.plot_x_label)
        axes.grid(axis='x', which='both', linestyle='-', alpha=0.1,
                  color='k', linewidth=0.5, zorder=2)

        # setup right Y axis
        axes.tick_params(axis='y', which='both', left=False, right=True,
                         labelleft=False, labelright=True, colors=self.plot_color_text)
        axes.yaxis.set_label_position('right')
        axes.set_ylabel(self.plot_y_label, color=self.plot_color_text,
                        # labelpad=-10)
                        ) # DEBUG
        #y_ticks = [0, self.mem_size-1]
        y_ticks = create_up_to_n_ticks(range(self.mem_size),
                                             base=10, n=num_ticks) # DEBUG
        axes.set_yticks(y_ticks)
        axes.grid(axis='y', which='both', linestyle='-', alpha=0.1,
                  color='k', linewidth=0.5, zorder=2) # DEBUG

        axes.invert_yaxis()
