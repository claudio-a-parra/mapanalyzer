#!/usr/bin/env python3
import sys
from collections import deque
import matplotlib.pyplot as plt
from matplotlib.colors import ListedColormap

from mapanalyzer.util import create_up_to_n_ticks, PlotStrings, save_fig, Palette, Dbg
from mapanalyzer.settings import Settings as st
from mapanalyzer.util import sub_resolution_between

class Map:
    def __init__(self, hue=120):
        self.tool_name = 'M. A. Pattern'
        self.tool_about = 'Visual representation of the Memory Access Pattern.'
        self.ps = PlotStrings(
            title = 'MAP',
            code = 'MAP',
            xlab   = 'Time [access instr.]',
            ylab   = 'Space [bytes]',
            suffix = '_plot-00-map',
            subtit = None
        )

        self.enabled = True # always enabled
        self.standalone_plot = self.ps.code in st.plot.include

        self.tool_palette = Palette(hue=hue)
        self.X = [i for i in range(st.map.time_size)]
        self.axes = None

        # select the resolution of the map grid. If too large, pick a value
        # under max_res
        map_mat_rows = sub_resolution_between(st.map.num_padded_bytes,
                                              st.plot.min_res, st.plot.max_res)
        map_mat_cols = sub_resolution_between(st.map.time_size,
                                              st.plot.min_res, st.plot.max_res)
        # cols: whole memory snapshot at a given instruction
        # rows: byte state across all instructions
        self.access_matrix = [[0] * map_mat_cols for _ in range(map_mat_rows)]

        return

    def describe(self, ind=''):
        if not self.standalone_plot:
            return
        print(f'{ind}{self.tool_name:{st.plot.ui_toolname_hpad}}: {self.tool_about}')
        return

    def add_access(self, access):
        """The idea is to take an access happening at (addr, time), and
        map it to (y,x) in self.access_matrix."""
        if not self.enabled:
            return
        # negative: read access, positive: write access
        # abs value: thread ID + 1 (to leave 0 for no-op)
        access_code = access.thread + 1
        if access.event == 'R':
            access_code *= -1

        # register accesses of size more than 1 byte
        for offset in range(access.size):
            # obtain the original coordinates
            addr = access.addr - st.map.aligned_start_addr + offset
            time = access.time

            # out of boundary access attempt
            if addr < st.map.left_pad or \
               st.map.aligned_end_addr-st.map.right_pad < addr:
                print(f'Error: The map file has an access out of boundaries '
                      f'at (time,thread,event,size,offset):\n'
                      f'    {access.time},{access.thread},{access.event},'
                      f'{access.size},{addr-st.map.left_pad}')
                exit(1)
            # get percentage (from first to last possible address or time)
            max_real_addr = st.map.num_padded_bytes - 1
            max_real_time = st.map.time_size - 1
            propor_addr = addr / max_real_addr
            propor_time = time / max_real_time

            # get maximum value for the mapped address and time
            max_mapped_addr = len(self.access_matrix) - 1
            max_mapped_time = len(self.access_matrix[0]) - 1

            # now map addr x time to the access_matrix
            mapped_addr = round(propor_addr * max_mapped_addr)
            mapped_time = round(propor_time * max_mapped_time)

            # store the access in space-time matrix
            self.access_matrix[mapped_addr][mapped_time] = access_code
        return

    def commit(self, time):
        if not self.enabled:
            return
        # this tool does not need to run anything after processing a batch
        # of concurrent accesses.
        return


    def plot(self, bottom_tool=None, axes=None, draw_X_grid=False, draw_Y_grid=False):
        if not self.enabled:
            return
        # define values for standalone and auxiliary-plot cases
        if axes is None:
            # only plot if requested
            if not self.standalone_plot:
                return
            standalone = True
            lig_val = [35,70]
            sat_val = [45,75]
            alp_val = 96
            fig,axes = plt.subplots(figsize=(st.plot.width, st.plot.height))
            fig.patch.set_facecolor('white')
        else:
            standalone = False
            lig_val = [35,70]
            sat_val = [45,75]
            alp_val = 96
        self.axes = axes

        # Create color maps based on thread and R/W access:
        #  -X : thread (X-1) read
        #   X : thread (X-1) write
        #   0 : no operation.
        # Then, the palette must match the negative and positive values to the
        # read/write colors of the thread.
        thr_count = st.map.thread_count
        thr_palette = Palette(hue_count=thr_count, lightness=lig_val,
                              saturation=sat_val, alpha=alp_val)
        read_color = list(reversed([thr_palette[i][0] for i in range(thr_count)]))
        write_color = [thr_palette[i][1] for i in range(thr_count)]
        cmap = ListedColormap(read_color + ['#FFFFFF00'] + write_color)

        # set plot limits and draw the MAP
        ymin,ymax = 0-0.5,st.map.num_padded_bytes-0.5
        extent = (self.X[0]-0.5, self.X[-1]+0.5, ymin, ymax)
        self.axes.imshow(self.access_matrix, cmap=cmap, origin='lower',
                         interpolation='none',
                         aspect='auto', zorder=2, extent=extent,
                         vmin=-thr_count, vmax=thr_count)
        self.axes.invert_yaxis()

        # complete plot setup
        if standalone:
            self.plot_fade_padding_bytes()
            self.plot_setup_general()
            self.plot_setup_X_axis()
            self.plot_draw_X_grid(draw_X_grid)
            self.plot_setup_Y_axis()
            self.plot_draw_Y_grid(draw_Y_grid)
            save_fig(fig, self.ps.code , self.ps.suffix)
        else:
            self.axes.set_xticks([])
            self.axes.set_yticks([])
            self.axes.patch.set_facecolor('white')
            self.plot_fade_padding_bytes()
            self.plot_draw_X_grid(draw_X_grid)
            self.plot_draw_Y_grid(draw_Y_grid)
        return

    def plot_setup_general(self):
        # background and spines colors
        self.axes.patch.set_facecolor('white')

        # setup title
        title_string = f'{self.ps.title}: {st.plot.prefix}'
        if self.ps.subtit:
            title_string += f'. ({self.ps.subtit})'
        self.axes.set_title(title_string, fontsize=10,
                       pad=st.plot.img_title_vpad)

    def plot_setup_X_axis(self):
        # spine
        self.axes.spines['bottom'].set_edgecolor('k')
        # label
        self.axes.set_xlabel(self.ps.xlab, color='k')
        # ticks
        rot = -90 if st.plot.x_orient == 'v' else 0
        self.axes.tick_params(axis='x', colors='k',
                              rotation=rot,
                              bottom=True, labelbottom=True,
                              top=False, labeltop=False)
        x_ticks = create_up_to_n_ticks(self.X, base=10,
                                       n=st.plot.max_xtick_count)
        self.axes.set_xticks(x_ticks)
        return

    def plot_setup_Y_axis(self):
        # spine
        #self.axes.spines['left'].set_edgecolor(self.tool_palette.fg)

        # label
        self.axes.set_ylabel(self.ps.ylab) #, color=self.tool_palette.fg)

        # ticks
        self.axes.tick_params(axis='y', #colors=self.tool_palette.fg,
                              left=True, labelleft=True,
                              right=False, labelright=False,
                              width=st.plot.grid_main_width)
        y_ticks = create_up_to_n_ticks(range(st.map.num_padded_bytes), base=2,
                                       n=st.plot.max_map_ytick_count)
        self.axes.set_yticks(y_ticks)

        # grid
        self.plot_draw_Y_grid()
        return

    def plot_draw_X_grid(self, draw='auto'):
        if draw is False:
            return
        if draw is True or len(self.X)<100:
            ymin,ymax = 0-0.5,st.map.num_padded_bytes-0.5
            time_sep_lines = [i-0.5 for i in
                              range(self.X[0],self.X[-1]+1)]

            self.axes.vlines(x=time_sep_lines, ymin=ymin, ymax=ymax,
                             color='k', linewidth=0.33, alpha=0.2, zorder=1)
        return

    def plot_draw_Y_grid(self, draw='auto', byte_sep='auto', block_sep='auto'):
        if draw is False:
            return
        max_bytes = st.plot.grid_max_bytes
        max_blocks = st.plot.grid_max_blocks
        if draw is True:
            byte_sep = True
            block_sep = True
        else:
            if byte_sep == 'auto':
                if st.map.num_padded_bytes < max_bytes:
                    byte_sep = True
                else:
                    byte_sep = False
            else:
                byte_sep = False
            if block_sep == 'auto':
                if st.map.num_blocks < max_blocks:
                    block_sep = True
                else:
                    block_sep = False
            else:
                block_sep = False

        xmin,xmax = 0-0.5,st.map.time_size-0.5
        if byte_sep:
            byte_lw = 0.5*(1 - ((st.map.num_padded_bytes-1) / max_bytes))
            byte_sep_lines = [i-0.5 for i in range(1,st.map.num_padded_bytes)]
            self.axes.hlines(y=byte_sep_lines, xmin=xmin, xmax=xmax,
                             color=self.tool_palette[0][0],
                             linewidth=byte_lw, alpha=0.1, zorder=1)

        if block_sep:
            block_lw = 2*(1 - ((st.map.num_blocks-1) / max_blocks))
            block_sep_lines = [i*st.cache.line_size-0.5
                               for i in range(st.map.num_blocks+1)]
            # if there is only two lines and they are in the border of the plot
            # then don't draw anything.
            if block_sep_lines[-1] != st.cache.line_size-0.5:
                self.axes.hlines(y=block_sep_lines, xmin=xmin, xmax=xmax,
                                 color=self.tool_palette[0][0],
                                 linewidth=block_lw, alpha=0.4, zorder=1)
        return

    def plot_fade_padding_bytes(self):
        fade_bytes_alpha=st.plot.fade_bytes_alpha
        xmin,xmax = 0-0.5,st.map.time_size-0.5
        if st.map.left_pad > 0:
            X = [xmin, xmax]
            self.axes.fill_between(X, 0-0.5, st.map.left_pad-0.5,
                                   facecolor='k', alpha=fade_bytes_alpha,
                                   zorder=0)
        if st.map.right_pad > 0:
            X = [xmin, xmax]
            self.axes.fill_between(X,
                                   st.map.num_padded_bytes-0.5-st.map.right_pad,
                                   st.map.num_padded_bytes-0.5,
                                   facecolor='k', alpha=fade_bytes_alpha,
                                   zorder=0)
        return
