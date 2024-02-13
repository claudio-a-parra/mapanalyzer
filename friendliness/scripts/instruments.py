#!/usr/bin/env python3
import sys
from collections import deque
import matplotlib as mpl
# increase memory for big plots. Bruh...
mpl.rcParams['agg.path.chunksize'] = 10000000000000
import matplotlib.pyplot as plt
from matplotlib.colors import ListedColormap

from instruction_counter import InstrCounter
from instr_mapplotter import MapPlotter
from instr_alias import Alias
from instr_miss import Miss
from instr_usage import UnusedBytes
# from instr_siue import SIUEvict


#-------------------------------------------
class Instruments:
    #def __init__(self, instr_counter, cache_specs, map=None, verb=False):
    def __init__(self, cache_specs, map_metadata, plot_width, plot_height,
                 resolution):
        self.ic = InstrCounter()
        self.plot_width = plot_width
        self.plot_height = plot_height

        # Create map plotter and other instruments: (alias, miss, usage,
        # and SIU). Make them share their X axis (for the plots)
        self.map = MapPlotter(self.ic, map_metadata, plot_width,
                                      plot_height, resolution)

        num_sets = cache_specs['size']//(cache_specs['asso']*\
                                         cache_specs['line'])

        self.alias = Alias(self.ic, num_sets)
        self.alias.X = self.map.X

        self.miss = Miss(self.ic)
        self.miss.X = self.map.X

        self.usage = UnusedBytes(self.ic)
        self.usage.X = self.map.X

        # self.siu = SIUEvict(instr_counter)
        # self.siu.X = self.map.instruction_ids
        self.inst_list = [self.alias, self.miss, self.usage] #, self.siu]


    def enable_all(self):
        self.map.enabled = True
        for i in self.inst_list:
            i.enabled = True


    def disable_all(self):
        self.map.enabled = False
        for i in self.inst_list:
            i.enabled = False


    def prepare_for_second_pass(self):
        self.disable_all()
        #self.siu.enabled = True
        #self.siu.mode = 'evict'


    def set_verbose(self, verb=False):
        self.map.enabled = verb
        for i in self.inst_list:
            i.enabled = verb


    def plot(self, window, basename, out_format):
        fig, map_axes = plt.subplots(
            figsize=(self.plot_width, self.plot_height))
        instr_axes = map_axes.twinx()

        for instr in self.inst_list:
            print(f'    Plotting {instr.plot_title}.')
            extent = instr.get_extent()
            self.map.plot(map_axes, extent=extent)
            instr.plot(instr_axes, basename=basename)

            # save alias
            filename=f'{basename}{instr.plot_name_sufix}.{out_format}'
            print(f'        {filename}')
            fig.savefig(filename, dpi=600, bbox_inches='tight')
            instr_axes.cla()

        exit(0)


'''
COMMENT START
    def plot_old(self, window, base_name, out_format):
        """Create all instrument plots with the access pattern in the
        background"""

        # Memory Access Pattern color-map creation
        # ON inst_mapplotter.py
        # threads_palette = ['#db000088'] # dark red
        # threads_bg = '#FFFFFF44' # last two digits is transparency
        # colors_needed = self.access_pattern.thread_count # one color per thread
        # if colors_needed > len(threads_palette):
        #     print(f'[!] Warning: The Access Pattern has more threads '
        #           'than colors available to plot. Different threads will '
        #           'share colors.')
        # cmap = ListedColormap([threads_bg] +
        #                       [threads_palette[i%len(threads_palette)]
        #                        for i in range(colors_needed)])

        # Instruments and their colors
        instruments = (self.alias, self.miss, self.usage, self.siu)
        col_instr = [('#ffa500ff','#ffa50066'), # orange ((100%, 40%) opaque)
                     ('#0000ffff','#0000ff66'), # blue
                     ('#008080ff','#00808066'), # teal
                     ('#ff00ffff','#ff00ff66'), # magenta
                     ('#000000ff','#00000066'), # black
                     ('#008000ff','#00800066'), # green
                     ]
        if len(col_instr) < len(instruments):
            print('[!] Warning: Less colors than instruments. Different '
                  'instruments will share colors.')

        # Down-Sample if there are too many data points (Matplotlib limitation)
        max_data_len = 4000
        max_data_len = 800000
        if max_data_len < len(self.instruction_ids):
            print('[!] Warning: Too many data points. Down-sampling to '
                  f'~ {max_data_len}.')
            step = len(self.instruction_ids) // max_data_len
            self.instruction_ids = self.instruction_ids[::step]
            for inst in instruments:
                inst.filtered_avg_log = inst.filtered_avg_log[::step]




        #### Plot instruments
        # Create instruments layer (axes)
        fig, instr_layer = plt.subplots(figsize=(self.plot_width, self.plot_height))

        # get shared x values, and x limits
        instr_x = self.instruction_ids
        min_x,max_x = instr_x[0]-1, instr_x[-1]+1


        # find a label_step such that we print at most `max_ticks` ticks
        max_ticks = 20
        tick_step, tot_ticks = 1, len(instr_x)
        for i in range(13):
            found = False
            for n in [1,2,5,8]:
                n_pow_ten = n * (10 ** i)
                if tot_ticks // n_pow_ten < max_ticks:
                    tick_step = n_pow_ten
                    found = True
                    break
            if found:
                break
        x_ticks_list = instr_x[::tick_step]

        # create mem access pattern layer and draw it
        map_layer = instr_layer.twinx()
        # plot memory access pattern
        map_layer.tick_params(axis='y', which='both', left=False, right=False,
                              labelleft=False, labelright=False)

        for color_index,instr in enumerate(instruments):
            sufix,title,subtitle,y_label,min_y,max_y = instr.plot_details
            print(f'    Plotting {title}...')

            # get instrument data and set Y label
            instr_y = instr.filtered_avg_log

            # get instrument color
            col_line = col_instr[color_index % len(col_instr)][0]
            col_fill = col_instr[color_index % len(col_instr)][1]

            # set title
            instr_layer.set_title(f'{title} ({subtitle})\n'
                                  f'{base_name}, w={instr.window_size}')

            # set X limits, label, and ticks
            instr_layer.set_xlim(min_x, max_x)
            instr_layer.set_xlabel('Instruction')
            instr_layer.set_xticks(x_ticks_list)

            # set Y limits and label
            max_y = max(max(instr_y), max_y)
            y_margin = (max_y - min_y) * 0.01 # 1% margin
            min_y,max_y = min_y-y_margin, max_y+y_margin
            instr_layer.set_ylim(min_y, max_y)
            instr_layer.set_ylabel(y_label)

            # plot instrument
            extent=(min_x, max_x+1, min_y, max_y)
            instr.plot(instr_layer, x=instr_x, y=instr_y,
                       col_line=col_line, col_fill=col_fill,
                       zorder=1, extent=extent)

            map_layer.imshow(self.access_matrix, cmap=cmap, aspect='auto',
                             extent=extent, zorder=3)

            # make sure the grid is above the plot itself
            instr_layer.grid(axis='x', linestyle='-', alpha=0.7,
                             linewidth=0.8, which='both', zorder=4)

            # save figure and reset the plot
            filename=f'{base_name}{sufix}.{out_format}'
            print(f'        {filename}')
            fig.savefig(filename, dpi=900, bbox_inches='tight')
            instr_layer.cla()
COMMENT END
'''
