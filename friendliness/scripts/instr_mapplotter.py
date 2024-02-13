#!/usr/bin/env python3
import sys
from collections import deque
from matplotlib.colors import ListedColormap

from instr_generic import GenericInstrument

class MapPlotter(GenericInstrument):
    def __init__(self, instr_counter, mfmd, plot_w, plot_h, plot_max_res=600):
        super().__init__(instr_counter)
        # obtain mem_ap file metadata
        self.base_addr = mfmd[0]
        self.block_size = mfmd[1]
        self.thread_count = mfmd[2]
        self.event_count = mfmd[3]
        self.time_size = mfmd[4]

        self.plot_width = plot_w
        self.plow_height = plot_h

        # if block_size or time_size are larger than the max resolution, keep
        # cutting them in half until they fit in a square of plot_max_res^2
        ap_matrix_height = self.block_size
        i=0
        while ap_matrix_height > plot_max_res:
            ap_matrix_height = self.block_size // (2**i)
            i += 1

        ap_matrix_width = self.time_size
        i=0
        while ap_matrix_width > plot_max_res:
            ap_matrix_width = self.time_size // (2**i)
            i += 1

        # cols: whole memory snapshot at a given instruction
        # rows: byte state across all instructions
        self.access_matrix = [[0] * ap_matrix_width
                              for _ in range(ap_matrix_height)]

        self.plot_filename_sufix = '_plot-00-map'
        self.plot_title = 'Memory Access Pattern'
        self.plot_subtitle = None
        self.plot_y_label = 'Memory Space'
        self.plot_x_label = 'Time'
        self.plot_min = None
        self.plot_max = None
        self.plot_color_text =   '#888888'
        self.plot_color_first =  '#CCCCCC' # opaque gray. '#DB000044'
        self.plot_color_second = '#EEEEEE'
        self.plot_color_bg =     '#FFFFFF00' # transparent


    def register_access(self, access):
        """The idea is to take an access happening at (addr, time), and
        map it to (y,x) in self.access_matrix."""
        if not self.enabled:
            return
        if len(self.X) == 0:
            for i in range(access.time):
                self.X.append(i)
        self.X.append(access.time) # save instruction id
        for i in range(access.size):
            # obtain the original coordinates
            addr = access.addr - self.base_addr + i
            time = access.time

            # get percentage (from first to last possible address or time)
            max_real_addr = self.block_size - 1
            max_real_time = self.time_size - 1
            propor_addr = addr / max_real_addr
            propor_time = time / max_real_time

            # get maximum value for the mapped address and time
            max_mapped_addr = len(self.access_matrix) - 1
            max_mapped_time = len(self.access_matrix[0]) - 1

            # now map addr x time to the access_matrix
            mapped_addr = round(propor_addr * max_mapped_addr)
            mapped_time = round(propor_time * max_mapped_time)

            # store the access. add 1 so zero values are interpreted as 'empty'
            self.access_matrix[mapped_addr][mapped_time] = access.thread + 1


    def plot(self, axes, zorder=1, extent=[0,10,0,10]):
        # Memory Access Pattern color-map creation
        threads_palette = [self.plot_color_first]
        threads_bg = self.plot_color_bg
        colors_needed = self.thread_count # one color per thread
        if colors_needed > len(threads_palette):
            print(f'[!] Warning: The Access Pattern has more threads '
                  'than colors available to plot. Different threads will '
                  'share colors.')
        cmap = ListedColormap([threads_bg] +
                              [threads_palette[i%len(threads_palette)]
                               for i in range(colors_needed)])
        # no Y axis for this plot
        axes.tick_params(axis='y', which='both', left=False, right=True,
                         labelleft=False, labelright=True)
        # plot the trace
        axes.imshow(self.access_matrix, cmap=cmap, origin='lower', aspect='auto',
                    zorder=zorder)

        # setup X axis
        x_ticks = self._create_up_to_n_ticks(self.X, base=10, n=20)
        axes.set_xticks(x_ticks)
        axes.set_xlabel(self.plot_x_label)

        # setup right Y axis
        axes.tick_params(axis='y', which='both', left=False, right=True,
                         labelleft=False, labelright=True)
        axes.yaxis.set_label_position('right')
        axes.set_ylabel(self.plot_y_label, color=self.plot_color_text, labelpad=-18)
        y_ticks = [0, self.block_size]
        axes.set_yticks(y_ticks)
        axes.invert_yaxis()
