#!/usr/bin/env python3
import sys
from collections import deque
import matplotlib.pyplot as plt
from matplotlib.colors import ListedColormap
from itertools import combinations
from math import prod

from mapanalyzer.util import sample_list, MetricStrings, Palette
from mapanalyzer.modules.base_module import BaseModule
from mapanalyzer.settings import Settings as st
from mapanalyzer.ui import UI

class Map(BaseModule):
    name = 'Mem Acc Pattern'
    about = 'Visual representation of the Memory Access Pattern.'
    hue = 120
    palette = Palette.default(hue)

    metrics = {
        'MAP' :  MetricStrings(
            title = 'MAP',
            subtit = None,
            numb   = '00',
            xlab   = 'Time [access instr.]',
            ylab   = 'Space [bytes]',
        )
    }

    def __init__(self, shared_X=None):
        self.enabled = any(m in st.Metrics.enabled for m in self.metrics.keys())
        if not self.enabled:
            return
        self.X = [i for i in range(st.Map.time_size)]

        # select the resolution of the map time-space grid. If too large, pick
        # a value under max_res
        map_mat_rows = Map.__sub_resolution_between(
            st.Map.num_padded_bytes, st.Plot.min_map_res, st.Plot.max_map_res
        )
        map_mat_cols = Map.__sub_resolution_between(
            st.Map.time_size, st.Plot.min_map_res, st.Plot.max_map_res
        )
        # cols: whole memory snapshot at a given instruction time
        # rows: byte (space) state across all instructions
        self.space_time = [[0] * map_mat_cols for _ in range(map_mat_rows)]
        return

    def probe(self, access):
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
                UI.error(f'The map file has an access out of boundaries '
                         f'at (time,thread,event,size,offset):\n'
                         f'{access.time},{access.thread},{access.event},'
                         f'{access.size},{addr-st.Map.left_pad}')
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

    def MAP_to_dict(self):
        return {
            'code': 'MAP',
            'x': self.X,
            'space_time': self.space_time
        }

    def dict_to_MAP(self, data):
        class_name = self.__class__.__name__
        my_code = 'MAP'
        curr_fn = f'dict_to_{my_code}'
        data_code = data['code']
        if my_code != data_code:
            UI.error(f'{class_name}.{curr_fn}(): {self.name} module '
                     f'received some unknown "{data_code}" metric data rather '
                     f'than its known "{my_code}" metric data.')
        self.X = data['x']
        self.space_time = data['space_time']
        return

    def MAP_to_plot(self, mpl_axes, bg_mode=False):
        if not self.enabled:
            return

        code = 'MAP'
        met_str = self.metrics[code]

        # Create color maps based on thread and R/W access:
        #  -X : thread (X-1) read
        #   X : thread (X-1) write
        #   0 : no operation.
        # Then, the palette must match the negative and positive values to the
        # read/write colors of the thread.
        #lig_val, sat_val, alp_val = [35,70], [45,75], 96
        thr_count = st.Map.thread_count
        thr_palette = Palette(
            hue = th_count,
            sat = [45, 75],
            lig = [35, 70],
            alp = [100]
        )
        read_colors =  [thr_palette[i][0][0][0] for i in range(thr_count)]
        write_colors = [thr_palette[i][1][1][0] for i in range(thr_count)]
        transparent = '#FFFFFF00'
        color_map = ListedColormap(
            list(reversed(read_colors)) + [transparent] + write_colors
        )

        # define and pad the extent of the image
        X_pad = 0.5
        Y_pad = 0.5
        ylims = (0, st.Map.num_padded_bytes - 1)
        xlims = (self.X[0], self.X[-1])
        # (left, right, bottom, top)
        extent = (xlims[0]-X_pad, xlims[1]+X_pad,
                  ylims[0]-Y_pad, ylims[1]+Y_pad)

        # draw the MAP
        mpl_axes.imshow(self.space_time, cmap=color_map, origin='lower',
                        interpolation='none',
                        aspect='auto', zorder=2, extent=extent,
                        vmin=-thr_count, vmax=thr_count)
        mpl_axes.invert_yaxis()


        # set plot limits
        real_xlim, real_ylim = self.setup_limits(
            mpl_axes, code=code, xlims=xlims, xpad=X_pad,
            ylims=ylims, ypad=Y_pad
        )

        # set ticks based on the real limits
        self.setup_ticks(
            mpl_axes, realxlim=real_xlim, realylim=real_ylim,
            tick_bases=(10, 2), # y-axis powers of two
            bg_mode=bg_mode
        )

        # set grid of bytes and blocks (not mpl grids)
        self.setup_grid(mpl_axes)

        # fade bytes used just for block-padding
        self.__fade_padding_bytes(mpl_axes)

        # set labels
        self.setup_labels(mpl_axes, met_str, bg_mode=bg_mode)

        # title and bg color
        self.setup_general(mpl_axes, met_str, bg_mode=bg_mode)
        return

    def MAP_to_bg_plot(self, axes, draw_x_grid=False, draw_y_grid=False):
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

    def setup_grid(self, mpl_axes, draw_x='auto', draw_y='auto',
                   byte_sep='auto'):
        self.__draw_X_grid(mpl_axes, draw=draw_x)
        self.__draw_Y_grid(mpl_axes, draw=draw_y, byte_sep=byte_sep)
        return

    def __draw_X_grid(self, axes, draw='auto'):
        if draw is False:
            return
        if draw is True or len(self.X)<100:
            ymin,ymax = 0-0.5,st.Map.num_padded_bytes-0.5
            time_sep_lines = [i-0.5 for i in
                              range(self.X[0],self.X[-1]+1)]

            axes.vlines(x=time_sep_lines, ymin=ymin, ymax=ymax,
                        color='k', linewidth=0.3333, alpha=0.2, zorder=1)
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
                        color=self.__class__.palette[0][0][0][0],
                        linewidth=byte_lw, alpha=0.1, zorder=1)

        if block_sep:
            block_lw = 2*(1 - ((st.Map.num_blocks-1) / max_blocks))
            block_sep_lines = [i*st.Cache.line_size-0.5
                               for i in range(st.Map.num_blocks+1)]
            # if there is only two lines and they are in the border of the plot
            # then don't draw anything.
            if block_sep_lines[-1] != st.Cache.line_size-0.5:
                axes.hlines(y=block_sep_lines, xmin=xmin, xmax=xmax,
                            color=self.__class__.palette[0][0][0][0],
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
