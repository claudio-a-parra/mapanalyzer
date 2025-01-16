#!/usr/bin/env python3
import sys
from collections import deque
import matplotlib.pyplot as plt
from matplotlib.colors import ListedColormap

from mapanalyzer.util import create_up_to_n_ticks, PlotStrings, Palette, \
    save_fig, save_json
from mapanalyzer.settings import Settings as st
from itertools import combinations
from math import prod


class Map:
    @staticmethod
    def __sub_resolution_between(native, min_res, max_res):
        """Find a good lower resolution"""
        if native < max_res:
            return native

        def prime_factors(n):
            """Helper function to get prime factors"""
            factors = []
            while n % 2 == 0:
                factors.append(2)
                n //= 2
            for i in range(3, int(n**0.5) + 1, 2):
                while n % i == 0:
                    factors.append(i)
                    n //= i
            if n > 2:
                factors.append(n)
            return factors

        # Get the prime factors of the native resolution
        factors = prime_factors(native)

        # Generate all products of combinations of factors in descending order
        power_set = sorted(
            (prod(ps)
             for r in range(1, len(factors) + 1)
             for ps in combinations(factors, r)),
            reverse=True
        )

        # Find the largest valid resolution within the range
        for r in power_set:
            if min_res <= r < max_res:
                return r

        # If no suitable resolution is found, return max_res as a fallback
        return max_res

    def __init__(self, hue=120):
        # Module info
        self.name = 'Mem Acc Pattern'
        self.about = 'Visual representation of the Memory Access Pattern.'

        # Metric(s) info
        self.ps = PlotStrings(
            title = 'MAP',
            subtit = None,
            code = 'MAP',
            xlab   = 'Time [access instr.]',
            ylab   = 'Space [bytes]',
        )

        self.enabled = True # always enabled
        self.standalone_plot = self.ps.code in st.Plot.include
        self.hue = hue
        self.tool_palette = Palette(hue=hue)
        self.X = [i for i in range(st.Map.time_size)]

        # select the resolution of the map time-space grid.
        # If too large, pick a value under max_res
        map_mat_rows = Map.__sub_resolution_between(
            st.Map.num_padded_bytes,
            st.Plot.min_map_res,
            st.Plot.max_map_res)
        map_mat_cols = Map.__sub_resolution_between(
            st.Map.time_size,
            st.Plot.min_map_res,
            st.Plot.max_map_res)
        # cols: whole memory snapshot at a given instruction time
        # rows: byte (space) state across all instructions
        self.space_time = [[0] * map_mat_cols for _ in range(map_mat_rows)]

        return

    def describe(self, ind=''):
        if not self.standalone_plot:
            return
        nc = f'{self.name} ({self.ps.code})'
        print(f'{ind}{nc:{st.Plot.UI.module_name_hpad}}: '
              f'{self.about}')
        return

    def add_access(self, access):
        """The idea is to take an access happening at (addr, time), and
        map it to (y,x) in self.space_time."""
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
            addr = access.addr - st.Map.aligned_start_addr + offset
            time = access.time

            # out of boundary access attempt
            if addr < st.Map.left_pad or \
               st.Map.aligned_end_addr-st.Map.right_pad < addr:
                print(f'Error: The map file has an access out of boundaries '
                      f'at (time,thread,event,size,offset):\n'
                      f'    {access.time},{access.thread},{access.event},'
                      f'{access.size},{addr-st.Map.left_pad}')
                exit(1)
            # get percentage (from first to last possible address or time)
            max_real_addr = max(1, st.Map.num_padded_bytes - 1)
            max_real_time = max(1, st.Map.time_size - 1)
            propor_addr = addr / max_real_addr
            propor_time = time / max_real_time

            # get maximum value for the mapped address and time
            max_mapped_addr = len(self.space_time) - 1
            max_mapped_time = len(self.space_time[0]) - 1

            # now map addr x time to the access_matrix
            mapped_addr = round(propor_addr * max_mapped_addr)
            mapped_time = round(propor_time * max_mapped_time)

            # store the access in space-time matrix
            self.space_time[mapped_addr][mapped_time] = access_code
        return

    def commit(self, time):
        # this tool does not need to run anything after processing a batch
        # of concurrent accesses.
        return

    def finalize(self):
        # no post-simulation computation to be done
        return

    def export_metrics(self):
        self_dict = self.__to_dict()
        save_json(self_dict, self.ps.code)
        return

    def export_plots(self, bg_module=None):
        if not self.enabled or not self.standalone_plot:
            return
        fig,axes = plt.subplots(figsize=(st.Plot.width, st.Plot.height))

        # Create color maps based on thread and R/W access:
        #  -X : thread (X-1) read
        #   X : thread (X-1) write
        #   0 : no operation.
        # Then, the palette must match the negative and positive values to the
        # read/write colors of the thread.
        thr_count = st.Map.thread_count
        lig_val, sat_val, alp_val = [35,70], [45,75], 96
        thr_palette = Palette(
            hue_count=thr_count,
            lightness=lig_val,
            saturation=sat_val,
            alpha=alp_val)
        read_color = list(reversed(
            [thr_palette[i][0] for i in range(thr_count)]
        ))
        write_color = [thr_palette[i][1] for i in range(thr_count)]
        cmap = ListedColormap(read_color + ['#FFFFFF00'] + write_color)

        # set plot limits
        ymin = 0-0.5
        ymax = st.Map.num_padded_bytes-0.5
        extent = (self.X[0]-0.5, self.X[-1]+0.5, ymin, ymax)

        # draw map
        axes.imshow(self.space_time, cmap=cmap, origin='lower',
                    interpolation='none',
                    aspect='auto', zorder=2, extent=extent,
                    vmin=-thr_count, vmax=thr_count)
        axes.invert_yaxis()

        # complete plot setup
        self.__setup_general(axes)
        self.__setup_X_axis(axes)
        self.__setup_Y_axis(axes)
        self.__draw_X_grid(axes)
        self.__draw_Y_grid(axes)
        self.__fade_padding_bytes(axes)
        save_fig(fig, self.ps.code)
        return

    def bg_plot(self, axes, draw_x_grid=False, draw_y_grid=False):
        """to be called by other modules to superpose their own plots on
        top of MAP"""
        lig_val = [35,70]
        sat_val = [45,75]
        alp_val = 96

        # Create color maps based on thread and R/W access:
        #  -X : thread (X-1) read
        #   X : thread (X-1) write
        #   0 : no operation.
        # Then, the palette must match the negative and positive values to the
        # read/write colors of the thread.
        thr_count = st.Map.thread_count
        thr_palette = Palette(hue_count=thr_count,
                              lightness=lig_val,
                              saturation=sat_val,
                              alpha=alp_val)
        read_color = list(reversed(
            [thr_palette[i][0] for i in range(thr_count)]
        ))
        write_color = [thr_palette[i][1] for i in range(thr_count)]
        cmap = ListedColormap(read_color + ['#FFFFFF00'] + write_color)

        # set plot limits
        ymin = 0-0.5
        ymax = st.Map.num_padded_bytes-0.5
        extent = (self.X[0]-0.5, self.X[-1]+0.5, ymin, ymax)

        # draw map
        axes.imshow(
            self.space_time, cmap=cmap, origin='lower',
            interpolation='none',
            aspect='auto', zorder=2, extent=extent,
            vmin=-thr_count, vmax=thr_count
        )
        axes.invert_yaxis()

        # delete all ticks and make bg solid
        self.__setup_general(axes, clean=True)
        self.__setup_X_axis(axes, clean=True)
        self.__setup_Y_axis(axes, clean=True)
        self.__draw_X_grid(axes, draw=draw_x_grid)
        self.__draw_Y_grid(axes, draw=draw_y_grid)
        self.__fade_padding_bytes(axes)
        return

    def __setup_general(self, axes, clean=False):
        # background and spines colors
        axes.patch.set_facecolor('white')

        if clean:
            axes.set_title('')
            return

        # setup title
        title_string = f'{self.ps.title}: {st.Map.ID}'
        if self.ps.subtit:
            title_string += f' ({self.ps.subtit})'
        axes.set_title(
            title_string, fontsize=10, pad=st.Plot.img_title_vpad
        )

    def __setup_X_axis(self, axes, clean=False):
        if clean:
            axes.set_xlabel('')
            axes.set_xticks([])
            return

        # Axis details: label and ticks
        axes.set_xlabel(self.ps.xlab)
        rot = -90 if st.Plot.x_orient == 'v' else 0
        axes.tick_params(
            axis='x', rotation=rot, width=st.Plot.grid_other_width,
            top=False, labeltop=False, bottom=True, labelbottom=True
        )
        axes.set_xticks(
            create_up_to_n_ticks(self.X, base=10, n=st.Plot.max_xtick_count)
        )
        return

    def __setup_Y_axis(self, axes, clean=False):
        if clean:
            axes.set_ylabel('')
            axes.set_yticks([])
            return

        # Axis details: label and ticks
        axes.set_ylabel(self.ps.ylab)
        axes.tick_params(
            axis='y', width=st.Plot.grid_main_width,
            left=True, labelleft=True, right=False, labelright=False
        )
        axes.set_yticks(
            create_up_to_n_ticks(range(st.Map.num_padded_bytes), base=2,
                                 n=st.Plot.max_ytick_count)
        )
        return

    def __draw_X_grid(self, axes, draw='auto'):
        if draw is False:
            return
        if draw is True or len(self.X)<100:
            ymin,ymax = 0-0.5,st.Map.num_padded_bytes-0.5
            time_sep_lines = [i-0.5 for i in
                              range(self.X[0],self.X[-1]+1)]

            axes.vlines(x=time_sep_lines, ymin=ymin, ymax=ymax,
                        color='k', linewidth=0.33, alpha=0.2, zorder=1)
        return

    def __draw_Y_grid(self, axes, draw='auto', byte_sep='auto',
                      block_sep='auto'):
        if draw is False:
            return
        max_bytes = st.Plot.grid_max_bytes
        max_blocks = st.Plot.grid_max_blocks
        if draw is True:
            byte_sep = True
            block_sep = True
        else:
            if byte_sep == 'auto':
                if st.Map.num_padded_bytes < max_bytes:
                    byte_sep = True
                else:
                    byte_sep = False
            else:
                byte_sep = False
            if block_sep == 'auto':
                if st.Map.num_blocks < max_blocks:
                    block_sep = True
                else:
                    block_sep = False
            else:
                block_sep = False

        xmin,xmax = 0-0.5,st.Map.time_size-0.5
        if byte_sep:
            byte_lw = 0.5*(1 - ((st.Map.num_padded_bytes-1) / max_bytes))
            byte_sep_lines = [i-0.5 for i in range(1,st.Map.num_padded_bytes)]
            axes.hlines(y=byte_sep_lines, xmin=xmin, xmax=xmax,
                        color=self.tool_palette[0][0],
                        linewidth=byte_lw, alpha=0.1, zorder=1)

        if block_sep:
            block_lw = 2*(1 - ((st.Map.num_blocks-1) / max_blocks))
            block_sep_lines = [i*st.Cache.line_size-0.5
                               for i in range(st.Map.num_blocks+1)]
            # if there is only two lines and they are in the border of the plot
            # then don't draw anything.
            if block_sep_lines[-1] != st.Cache.line_size-0.5:
                axes.hlines(y=block_sep_lines, xmin=xmin, xmax=xmax,
                            color=self.tool_palette[0][0],
                            linewidth=block_lw, alpha=0.4, zorder=1)
        return

    def __fade_padding_bytes(self, axes):
        fade_bytes_alpha=st.Plot.fade_bytes_alpha
        xmin,xmax = 0-0.5,st.Map.time_size-0.5
        if st.Map.left_pad > 0:
            X = [xmin, xmax]
            axes.fill_between(
                X, 0-0.5, st.Map.left_pad-0.5,
                facecolor='k', alpha=fade_bytes_alpha,
                zorder=0)
        if st.Map.right_pad > 0:
            X = [xmin, xmax]
            axes.fill_between(
                X,
                st.Map.num_padded_bytes-0.5-st.Map.right_pad,
                st.Map.num_padded_bytes-0.5,
                facecolor='k', alpha=fade_bytes_alpha,
                zorder=0)
        return

    def __to_dict(self):
        data = {
            'timestamp': st.timestamp,
            'map': st.Map.to_dict(),
            'cache': st.Cache.to_dict(),
            'metric': {
                'code': self.ps.code,
                'x': self.X,
                'space_time': self.space_time
            }
        }
        return data
