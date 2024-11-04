#!/usr/bin/env python3
import sys
#from collections import deque

class GenericInstrument:
    def __init__(self, instr_counter=None, verb=False):
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
