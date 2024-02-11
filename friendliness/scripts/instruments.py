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
# from instr_miss import Miss
# from instr_usage import Usage
# from instr_siue import SIUEvict


#-------------------------------------------
class Instruments:
    #def __init__(self, instr_counter, cache_specs, map_plotter=None, verb=False):
    def __init__(self, cache_specs, map_metadata, plot_width, plot_height,
                 resolution):
        #self.ic = instr_counter
        #self.num_sets = cache_specs['size']//(cache_specs['asso']*cache_specs['line'])
        #self.line_size_bytes = cache_specs['line']
        #self.verb = verb

        self.ic = InstrCounter()
        self.plot_width = plot_width
        self.plot_height = plot_height

        # Create map plotter and alias, miss, usage, and SIU instruments.
        # Make them share their X axis (for the plots)
        self.map_plotter = MapPlotter(self.ic, map_metadata,
                                      plot_width, plot_height, resolution)

        num_sets = cache_specs['size']//(cache_specs['asso']*\
                                         cache_specs['line'])
        self.alias = Alias(self.ic, num_sets)
        self.alias.X = self.map_plotter.X

        # self.miss = Miss(instr_counter)
        # self.miss.X = self.map_plotter.instruction_ids

        # self.usage = Usage(instr_counter, cache_specs['line'])
        # self.usage.X = self.map_plotter.instruction_ids

        # self.siu = SIUEvict(instr_counter)
        # self.siu.X = self.map_plotter.instruction_ids


    def enable_all(self):
        self.map_plotter.enabled = True
        self.alias.enabled = True
        # self.missr.enabled = True
        # self.usage.enabled = True
        # self.siu.enabled = True


    def disable_all(self):
        self.map_plotter.enabled = False
        self.alias.enabled = False
        # self.miss.enabled = False
        # self.usage.enabled = False
        # self.siu.enabled = False


    def prepare_for_second_pass(self):
        self.map_plotter.enabled = False
        self.alias.enabled = False
        # self.miss.enabled = False
        # self.usage.enabled = False
        # self.siu.enabled = True
        # self.siu.mode = 'evict'


    def set_verbose(self, verb=False):
        self.map_plotter.verbose = verb
        self.alias.verbose = verb
        # self.miss.verbose = verb
        # self.usage.verbose = verb
        # self.siu.verbose = verb


    def plot(self, window, base_name, out_format):
        fig, instrument_axes = plt.subplots(
            figsize=(self.plot_width, self.plot_height))

        map_axes = instrument_axes.twinx()
        map_axes.tick_params(axis='y', which='both', left=False, right=False,
                              labelleft=False, labelright=False)

        # plot alias
        print(f'    Plotting {self.alias.plot_title}.')
        extent = self.alias.plot(instrument_axes, zorder=1, window=window)

        # plot map
        self.map_plotter.plot(map_axes, zorder=3, extent=extent)

        # save figure
        filename=f'{base_name}{self.alias.plot_filename_sufix}.{out_format}'
        print(f'        {filename}')
        fig.savefig(filename, dpi=600, bbox_inches='tight')
        instrument_axes.cla()
        print('DONE SO FAR :)')
        exit(0)


'''
COMMENT START
    def build_log(self):
        self.alias.build_log(self.instruction_ids)
        self.miss.build_log(self.instruction_ids)
        self.usage.build_log(self.instruction_ids)
        self.siu.build_log(self.instruction_ids)


    def filter_log(self, win):
        default_win = 0.05 # window of 5% of the total number of points.
        # sanity check for window size
        ap_tot_events = self.access_pattern.event_count
        auto_win = max(round(ap_tot_events * default_win), 1)
        if win == None:
            win = auto_win
        elif win < 1 or ap_tot_events < win:
            if ap_tot_events < win:
                is_msg = f'larger than the number of events ({ap_tot_events})'
            else:
                is_msg = 'less than one'
            print(f'[!] Warning: the given avg window ({win}) is '
                  f'{is_msg}. Using default value ({auto_win}).')
            win = auto_win

        # filter instruments' logs
        instruments = (self.alias, self.miss, self.usage, self.siu)
        windows = [win, win, 1, win]
        for i,w in zip(instruments,windows):
            print(f'    Filtering {i.plot_details[1]} (w={w})')
            i.filter_log(w)


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
