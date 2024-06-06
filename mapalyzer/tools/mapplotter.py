#!/usr/bin/env python3
import sys
from collections import deque
import matplotlib.pyplot as plt
from matplotlib.colors import ListedColormap
from matplotlib.ticker import FuncFormatter #to make a custom tick formatter
import humanize # to convert raw byte count to KiB, MiB...

from util import create_up_to_n_ticks, PlotStrings, save_fig, Palette, Dbg
from settings import Settings as st

class Map:
    def __init__(self, hue=120):
        self.tool_palette = Palette(hue=hue)
        self.X = [i for i in range(st.map.time_size)]
        self.axes = None

        # set the matrix size of at most res^2
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

        # register accesses of size more than 1 byte
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

            # just show the first byte of the block
            if offset == 0:
                Dbg.p(f'map: [{addr},{time}] -> [{mapped_time},{mapped_addr}]')
            # store the access in space-time matrix
            self.access_matrix[mapped_addr][mapped_time] = access_code
        return

    def commit(self, time):
        # this tool does not need to run anything after processing a batch
        # of concurrent accesses.
        return


    def plot(self, top_tool=None, axes=None, xlab=False):
        # define values for standalone and secondary plot cases
        if axes is None:
            standalone = True
            lig_val = [35,70]
            sat_val = [45,75]
            alp_val = 100
            fig,axes = plt.subplots(figsize=(st.plot.width, st.plot.height))
        else:
            standalone = False
            lig_val = [30,65]
            sat_val = [45,75]
            alp_val = 25

        thr_count = st.map.thread_count
        self.axes = axes

        # Create color maps based on thread and R/W access:
        #  -X : thread (X-1) read
        #   X : thread (X-1) write
        #   0 : no operation.
        # Then, the palette must match the negative and positive values to the
        # read/write colors of the thread.
        thr_palette = Palette(hue_count=thr_count,
                              lightness=lig_val,
                              saturation=sat_val,
                              alpha=alp_val)
        rcol = list(reversed([thr_palette[i][0] for i in range(thr_count)]))
        wcol = [thr_palette[i][1] for i in range(thr_count)]
        cmap = ListedColormap(rcol + ['#FFFFFF00'] + wcol)

        # set plot limits and draw the MAP
        extent = (self.X[0]-0.5, self.X[-1]+0.5, 0-0.5, st.map.mem_size-0.5)
        self.axes.imshow(self.access_matrix, cmap=cmap, origin='lower',
                    aspect='auto', zorder=0, extent=extent,
                    vmin=-thr_count, vmax=thr_count)
        self.axes.invert_yaxis()

        # complete plot setup
        self.axes.set_xticks([])
        self.axes.set_yticks([])
        if standalone:
            self.plot_setup_general()
            self.plot_setup_X_axis(xlab=True, grid=True)
            self.plot_setup_Y_axis()
            save_fig(fig, self.ps.title, self.ps.suffix)
        else:
            self.plot_setup_X_axis(xlab=xlab)
        return

    def plot_setup_general(self):
        # background color
        self.axes.patch.set_facecolor(self.tool_palette.bg)
        # setup title
        title_string = f'{self.ps.title}: {st.plot.prefix}'
        if self.ps.subtit:
            title_string += f'. ({self.ps.subtit})'
        self.axes.set_title(title_string, fontsize=10,
                       pad=st.plot.img_title_vpad)

    def plot_setup_X_axis(self, xlab=False, grid=False):
        if xlab == False:
            return
        # label
        self.axes.set_xlabel(self.ps.xlab)
        # ticks
        self.axes.tick_params(axis='x', rotation=-90,
                         bottom=True, labelbottom=True,
                         top=False, labeltop=False)
        x_ticks = create_up_to_n_ticks(self.X, base=10,
                                       n=st.plot.max_xtick_count)
        self.axes.set_xticks(x_ticks)
        if grid:
            self.plot_draw_X_grid()
        return

    def plot_draw_X_grid(self):
        ymax = st.map.mem_size-0.5
        time_sep_lines = [i-0.5 for i in
                          range(self.X[0],self.X[-1]+1)]
        self.axes.vlines(x=time_sep_lines, ymin=-0.5, ymax=ymax,
                         color='k', linewidth=0.33, alpha=0.2, zorder=1)
        return

    def plot_setup_Y_axis(self):
        # label
        #self.axes.yaxis.set_label_position('right')
        self.axes.set_ylabel(self.ps.ylab, color=self.tool_palette.fg)
        # ticks
        self.axes.tick_params(axis='y', colors=self.tool_palette.fg,
                              left=True, labelleft=True,
                              right=False, labelright=False)
        y_ticks = create_up_to_n_ticks(range(st.map.mem_size), base=2,
                                       n=st.plot.max_map_ytick_count)
        self.axes.set_yticks(y_ticks)

        bs = False if st.map.mem_size > 64 else True
        self.plot_draw_Y_grid(byte_sep=bs)
        return

    def plot_draw_Y_grid(self, byte_sep=False):
        if byte_sep:
            byte_sep_lines = [i-0.5 for i in range(1,st.map.mem_size)]
            self.axes.hlines(y=byte_sep_lines, xmin=-0.5, xmax=st.map.time_size-0.5,
                             color=self.tool_palette.fg,
                             linewidth=0.33, alpha=0.2, zorder=1)
        block_sep_lines = [i-0.5 for i in
                           range(0, st.map.mem_size+1, st.cache.line_size)]
        self.axes.hlines(y=block_sep_lines, xmin=-0.5, xmax=st.map.time_size-0.5,
                         color=self.tool_palette.fg,
                         linestyle='-',
                         linewidth=1, alpha=0.3, zorder=1)
