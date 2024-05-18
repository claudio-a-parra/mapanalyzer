#!/usr/bin/env python3
import sys
from .generic import GenericInstrument

#-------------------------------------------
class UnusedBytes(GenericInstrument):
    """
    Definition:
        The proportion of valid UNUSED bytes in cache with respect to all the
        valid bytes in cache.

    Captured Events:
        Each event is a tuple with two counters: (accessed, valid). Note that
        all accessed bytes are also be valid. These counters are cumulative
        and represent the total count in the whole execution so far.
        Every cache access may contribute bytes "accessed for the first time",
        every fetch brings new valid bytes, and every eviction removes valid
        bytes.

    Plot interpretation:
        The plot is a line that ranges from 0% to 100% showing the proportion
        of bytes that are in cache but HAVE NOT BEEN ACCESSED to that point.
    """

    def __init__(self, instr_counter, verb=False):
        super().__init__(instr_counter, verb=verb)

        self.access_count = 0
        self.valid_count = 0
        self.zero_counter = (0,0)

        self.plot_name_sufix = '_plot-03-usage'
        self.plot_title      = 'Usage Ratio'
        self.plot_subtitle   = 'higher is better'
        self.plot_y_label    = 'Used bytes [%]'
        self.plot_x_label    = 'Instruction'
        self.plot_color_text = '#006B62FF'   # dark turquoise
        self.plot_color_line = '#00CCBA88' # turquoise almost opaque
        self.plot_color_fill = '#00CCBA11' # turquoise semi-transparent
        return


    def _pad_events_list(self, new_index):
        if len(self.events) != 0:
            while len(self.events) < new_index:
                self.events.append(self.events[-1])
        return


    def register(self, delta_access=0, delta_valid=0):
        # positive delta_access: newly accessed bytes.
        # negative delta_access: bytes that have been accessed are now evicted.
        # positive delta_valid: fetching block.
        # negative delta_valid: evicting block.
        if not self.enabled:
            return

        # update existing counter, or add a new one.
        event_idx = self.ic.val() # note that ic may skip values.
        if event_idx < len(self.events):
            # if the events[event_idx] exists, then just update it
            access,valid = self.events[event_idx]
            self.events[event_idx] = (access+delta_access, valid+delta_valid)
            if event_idx+1 == len(self.events):
                # if we happen to have just edited the last event,
                # then the access/valid counters need to be updated
                self.access_count += delta_access
                self.valid_count += delta_valid
        else:
            # otherwise, pad events with the last counter so that
            # the index of a new append() is event_idx
            self._pad_events_list(event_idx)
            # update counters
            self.access_count += delta_access
            self.valid_count += delta_valid
            self.events.append((self.access_count, self.valid_count))
        return


    def _create_plotting_data(self):
        # create the list of percentages based on the counts in self.events.
        # This is straight forward:
        #    percentage = 100 * (valid-access)/(valid)

        self._pad_events_list(self.X[-1]+1)
        for access,valid in self.events:
            if valid == 0:
                percentage = 0
            else:
                percentage = 100 * (access)/(valid)
            self.Y.append(percentage)
        self.events = None # hint GC
        return


    def get_extent(self):
        # fine tune margins to place each quadrilateral of the imshow()
        # right on the tick. So adding a 0.5 margin at each side.
        left_edge = self.X[0] - 0.5
        right_edge = self.X[-1] + 0.5
        bottom_edge = 0 - 0.5
        top_edge = 100 + 0.5 # 100% + a little margin
        extent = (left_edge, right_edge, bottom_edge, top_edge)
        return extent


    def plot(self, axes, basename='miss', extent=None):
        # check if self.X has been filled
        if self.X == None:
            print('[!] Error: Please assign '
                  f'{self.__class__.__name__}.X before calling plot()')
            sys.exit(1)

        # transform list of events into list of plotable data in self.Y
        self._create_plotting_data()

        # set plot limits
        extent = extent if extent != None else self.get_extent()
        axes.set_xlim(extent[0], extent[1])
        axes.set_ylim(extent[2], extent[3])

        # draw the curve and area below it
        axes.step(self.X, self.Y, color=self.plot_color_line,
                          linewidth=1.2, where='mid', zorder=2)
        axes.fill_between(self.X, -1, self.Y, color='none',
                          facecolor=self.plot_color_fill,
                          linewidth=1.2, step='mid', zorder=1)

        # setup title
        axes.set_title(f'{self.plot_title}: {basename}. '
                       f'({self.plot_subtitle})', fontsize=10)

        # setup X ticks, labels, and grid
        axes.tick_params(axis='x', bottom=True, top=False, labelbottom=True,
                         rotation=90)
        x_ticks = self._create_up_to_n_ticks(self.X, base=10, n=20)
        axes.set_xticks(x_ticks)
        axes.set_xlabel(self.plot_x_label)
        axes.grid(axis='x', which='both', linestyle='-', alpha=0.1,
                  color='k', linewidth=0.5, zorder=2)

        # setup Y ticks, labels, and grid
        axes.tick_params(axis='y', which='both', left=True, right=False,
                         labelleft=True, labelright=False,
                         colors=self.plot_color_text)
        percentages = list(range(100 + 1)) # from 0 to 100
        y_ticks = self._create_up_to_n_ticks(percentages, base=10, n=11)
        axes.set_yticks(y_ticks)
        axes.yaxis.set_label_position('left')
        axes.set_ylabel(self.plot_y_label, color=self.plot_color_text,
                        labelpad=3.5)
        axes.grid(axis='y', which='both', linestyle='-', alpha=0.1,
                  color=self.plot_color_line, linewidth=0.5, zorder=3)

        return
