#!/usr/bin/env python3
import sys
from collections import deque
from matplotlib.colors import ListedColormap

from instr_generic import GenericInstrument

class MapPlotter(GenericInstrument):
    def __init__(self, instr_counter, mfmd, plot_w, plot_h, plot_res=150):
        super().__init__(instr_counter)
        # obtain mem_ap file metadata
        self.base_addr = mfmd[0]
        self.block_size = mfmd[1]
        self.thread_count = mfmd[2]
        self.event_count = mfmd[3]
        self.time_size = mfmd[4]

        self.plot_width = plot_w
        self.plow_height = plot_h

        # adjust the matrix where the access pattern will be drawn to
        # the smallest between its own value or plot*resolution. The
        # idea is to not blow out the memory with a huge matrix.
        ap_matrix_height = self.block_size
        if plot_res*plot_h < self.block_size:
            ap_matrix_height = plot_res * plot_h
        ap_matrix_width = self.time_size
        if plot_res*plot_w < self.time_size:
            ap_matrix_width = plot_res * plot_w
        # cols: whole memory snapshot at a given instruction
        # rows: byte state across all instructions
        self.access_matrix = \
            [[0] * ap_matrix_width for _ in range(ap_matrix_height)]

        self.plot_filename_sufix = '_plot-00-map'
        self.plot_title = 'Memory Access Pattern'
        self.plot_subtitle = None
        self.plot_y_label = 'Memory Addresses (space)'
        self.plot_x_label = 'Instruction (time)'
        self.plot_min = None
        self.plot_max = None
        self.plot_color_fg1 = '#db000088' # dark red
        self.plot_color_fg2 = None
        self.plot_color_bg =  '#FFFFFF44' # pretty transparent white


    def register_access(self, access):
        """The idea is to take an access happening at (addr, time), and
        map it to (y,x) in self.access_matrix."""
        if not self.enabled:
            return
        self.X.append(access.time) # save instruction id
        for i in range(access.size):
            # obtain the original coordinates
            addr = access.addr - self.base_addr + i
            time = access.time
            # transform to a percentage form [0-1)
            addr = addr / self.block_size
            time = time / self.time_size
            # obtain the size of the access matrix
            acc_addr_size = len(self.access_matrix)
            acc_time_size = len(self.access_matrix[0])
            # now map the coordinate to the access_matrix. -1 so we
            # don't overflow
            addr_acc = round(addr * (acc_addr_size-1))
            time_acc = round(time * (acc_time_size-1))
            # store the value in the matrix. The stored value is
            # the thread number + 1 so empty cells remain 0 and used cells
            # become 1, 2, 3, ...
            self.access_matrix[addr_acc][time_acc] = access.thread + 1


    def plot(self, axes, zorder=1, extent=[0,10,0,10]):
        # Memory Access Pattern color-map creation
        threads_palette = ['#db000088'] # dark red
        threads_bg = '#FFFFFF44' # last two digits is transparency
        colors_needed = self.thread_count # one color per thread
        if colors_needed > len(threads_palette):
            print(f'[!] Warning: The Access Pattern has more threads '
                  'than colors available to plot. Different threads will '
                  'share colors.')
        cmap = ListedColormap([threads_bg] +
                              [threads_palette[i%len(threads_palette)]
                               for i in range(colors_needed)])
        axes.imshow(self.access_matrix, cmap=cmap, aspect='auto', extent=extent,
                    zorder=zorder)
