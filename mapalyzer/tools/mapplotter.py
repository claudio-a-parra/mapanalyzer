#!/usr/bin/env python3
import sys
from collections import deque
import matplotlib.pyplot as plt
from matplotlib.colors import ListedColormap
from matplotlib.ticker import FuncFormatter #to make a custom tick formatter
import humanize # to convert raw byte count to KiB, MiB...

from util import create_up_to_n_ticks, PlotStrings, save_fig
from settings import Settings as st
from palette import Palette

class Map:
    def __init__(self, hue=120, verb=None):
        self.hue = hue
        if verb is None:
            self.verb = st.verb
        self.X = [i for i in range(st.map.time_size)]

        # if mem_size or time_size are larger than the max resolution, keep
        # diving them until they fit in a square of st.plot.res^2
        ap_matrix_height = st.map.mem_size if st.map.mem_size <= st.plot.res \
            else st.plot.res
        ap_matrix_width = st.map.time_size if st.map.time_size <= st.plot.res \
            else st.plot.res

        # cols: whole memory snapshot at a given instruction
        # rows: byte state across all instructions
        self.access_matrix = [[0] * ap_matrix_width
                              for _ in range(ap_matrix_height)]

        self.name = 'Memory Access Pattern'
        self.about = 'Visual representation of the Memory Access Pattern'
        self.ps = PlotStrings(
            title = self.name,
            xlab   = 'Time',
            ylab   = 'Space [bytes]',
            suffix = '_plot-00-map',
            subtit = None)
        return

    def describe(self, ind=''):
        print(f'{ind}{self.name:{st.plot.ui_name_hpad}}: {self.about}')
        return

    def add_access(self, access):
        """The idea is to take an access happening at (addr, time), and
        map it to (y,x) in self.access_matrix."""
        # negative: read access, positive: write access
        # abs value: thread ID + 1 (to leave 0 for no-op)
        access_code = access.thread + 1
        if access.event == 'R':
            access_code *= -1

        # properly register accesses of more than 1 byte
        for offset in range(access.size):
            # obtain the original coordinates
            addr = access.addr - st.map.start_addr + offset
            time = access.time

            # get percentage (from first to last possible address or time)
            max_real_addr = st.map.mem_size - 1
            max_real_time = st.map.time_size - 1
            propor_addr = addr / max_real_addr
            propor_time = time / max_real_time

            # get maximum value for the mapped address and time
            max_mapped_addr = len(self.access_matrix) - 1
            max_mapped_time = len(self.access_matrix[0]) - 1

            # now map addr x time to the access_matrix
            mapped_addr = round(propor_addr * max_mapped_addr)
            mapped_time = round(propor_time * max_mapped_time)

            if self.verb and offset == 0:
                print(f'map: [{addr},{time}] -> [{mapped_time},{mapped_addr}]')
            # store the access. add 1 so zero values are interpreted as 'empty'
            self.access_matrix[mapped_addr][mapped_time] = access_code


    def plot(self, top_tool=None, axes=None):
        # generate color palette
        thr_count = st.map.thread_count

        if axes is None:
            standalone = True
            draw_alpha = 80
            fig,axes = plt.subplots(figsize=(st.plot.width, st.plot.height))
        else:
            standalone = False
            draw_alpha = 40

        thr_palette = Palette(lightness_count=2, hue_count=thr_count,
                              alpha=draw_alpha)
        tool_palette = Palette(hue=self.hue)
        # Access codes:
        #  -X : thread (X-1) read
        #   X : thread (X-1) write
        #   0 : no operation.
        # Then, the palette must match the negative and positive values to the
        # read/write colors of the thread.
        read_palette =  [thr_palette[i][0] for i in range(thr_count)]
        write_palette = [thr_palette[i][1] for i in range(thr_count)]
        cmap = ListedColormap(list(reversed(read_palette)) +
                              [thr_palette.bg] + write_palette)

        # plot the trace
        extent = (self.X[0]-0.5, self.X[-1]+0.5, 0-0.5, st.map.mem_size-0.5)
        axes.imshow(self.access_matrix, cmap=cmap, origin='lower',
                    aspect='auto', zorder=2, extent=extent,
                    vmin=-thr_count, vmax=thr_count)


        if standalone:
            # setup title
            title_string = f'{self.ps.title}: {st.plot.prefix}'
            if self.ps.subtit:
                title_string += f'. ({self.ps.subtit})'
            axes.set_title(title_string, fontsize=10,
                           pad=st.plot.img_title_vpad)
            # X axis label, ticks and grid
            axes.set_xlabel(self.ps.xlab)
            axes.tick_params(axis='x', bottom=True, top=False, labelbottom=True,
                             rotation=90, width=st.plot.grid_other_width)
            x_ticks = create_up_to_n_ticks(self.X, base=10,
                                           n=st.plot.max_xtick_count)
            axes.set_xticks(x_ticks)
            axes.grid(axis='x', which='both', linestyle=st.plot.grid_other_style,
                      alpha=0.1, color='k', linewidth=st.plot.grid_other_width,
                      zorder=1)

            # Y axis grid
            axes.grid(axis='y', which='both', linestyle='-', alpha=0.1,
                      color=tool_palette.fg, linewidth=st.plot.grid_main_width,
                      zorder=1)
            ticks_width = st.plot.grid_main_width
        else:
            # X and Y axis ticks empty
            axes.set_xticks([])
            axes.set_yticks([])
            ticks_width = st.plot.grid_other_width

        # Y axis label and ticks
        axes.yaxis.set_label_position('right')
        axes.set_ylabel(self.ps.ylab, color=tool_palette.fg) # labelpad=-10)
        axes.tick_params(axis='y', which='both', left=False, right=True,
                         labelleft=False, labelright=True,
                         colors=tool_palette.fg,
                         width=ticks_width)
        y_ticks = create_up_to_n_ticks(range(st.map.mem_size), base=10,
                                       n=st.plot.max_map_ytick_count)
        axes.set_yticks(y_ticks)
        axes.invert_yaxis()

        if standalone:
            save_fig(fig, self.ps.title, self.ps.suffix)
