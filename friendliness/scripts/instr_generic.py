#!/usr/bin/env python3
import sys
#from collections import deque

class GenericInstrument:
    def __init__(self, instr_counter, verb=False):
        self.enabled = True
        self.verb = verb
        self.ic = instr_counter
        self.events = []
        self.X = []
        self.Y = []

        self.plot_filename_sufix = '_filename-sufix'
        self.plot_title = 'Title'
        self.plot_subtitle = 'Subtitle'
        self.plot_y_label = 'Y label'
        self.plot_x_label = 'X label'
        self.plot_min = 0
        self.plot_max = 1
        self.plot_color_fg1 = '#000000FF' # black 100% opaque
        self.plot_color_fg2 = '#00000066' # black  40% opaque
        self.plot_color_bg =  '#FFFFFF00' # white   0% opaque, transparent.


    def _create_up_to_n_ticks(self, full_list, base=10, n=10):
        """
        return a list of ticks based on full_list. The idea is to find
        nice numbers (multiples of powers of 10 or 2) and not having
        more than n elements.
        """
        # find a label_step such that we print at most n ticks
        tick_step = 1
        tot_ticks = len(full_list)
        factors = [1,2,2.5,5] if base==10 else [1,1.5]
        for i in range(14):
            found = False
            for f in factors:
                f_pow_base = int(f * (base ** i))
                if int(tot_ticks / f_pow_base) <= (n-1):
                    tick_step = f_pow_base
                    found = True
                    break
            if found:
                break
        tick_list = full_list[::tick_step]
        # print(f'full_list: {full_list}')
        # print(f'ticks    : {tick_list}')
        return tick_list
