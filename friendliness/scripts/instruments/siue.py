#!/usr/bin/env python3
import sys
from .generic import GenericInstrument

#-------------------------------------------
class SIUEvict(GenericInstrument):
    """
    Definition:
        The proportion of SIU evictions with respect to the total number of
        evictions. A SIU (still-in-use) eviction is the eviction of a cache
        block that later will be fetched to the cache again.

    Fetch and Evict Counters:
        This instrument works in two passes. In the first pass a dictionary
        of (tag,index) -> (counter) is populated, so that every time a cache
        block is fetched, the counter increments.
        On the second pass, and using the already populated dictionary, every
        block eviction triggers a decrement in its corresponding counter.
        If after the decrement, the counter is still greater than 0, this means
        the block is later brought back to cache again. It is, then, said that
        the current is an eviction of a "still-in-use" block.

    Captured Events:
        Each event is a tuple of two counters: (siu_evicts, tot_evicts). Note
        that tot_evicts includes all siu_evicts. These counters are cumulative.

    Plot interpretation:
        The plot is a line that ranges from 0% to 100% showing the proportion
        of evictions that are SIU.
    """

    def __init__(self, instr_counter, verb=False):
        super().__init__(instr_counter, verb=verb)

        self.fetch_counters = {}
        self.mode = 'fetch' # ['fetch', 'evict']
        #
        self.siu_evict_count = 0
        self.tot_evict_count = 0
        self.zero_counter = (0,0)

        self.plot_name_sufix = '_plot-05-siu'
        self.plot_title      = 'Still-in-Use Block Evictions'
        self.plot_subtitle   = 'lower is better'
        self.plot_y_label    = 'SIU Eviction ratio [%]'
        self.plot_color_text = '#6122AA'   #'#990099'   # dark magenta
        self.plot_color_line = '#7A2AD5AA' #'#AA00AACC' # magenta almost opaque
        self.plot_color_fill = '#7A2AD522' #'#AA00AA44' # magenta semi-transparent


    def _pad_events_list(self, new_index):
        while len(self.events) < new_index:
            self.events.append(self.zero_counter)
        return

    
    def register(self, mode, tag, index):
        if not self.enabled:
            return

        block_id = (tag,index)
        if self.mode == 'fetch' and mode == 'fetch':
            if block_id in self.fetch_counters:
                self.fetch_counters[block_id] += 1
            else:
                self.fetch_counters[block_id] = 1
            if self.verb:
                fetch_count = self.fetch_counters[block_id]
                print(f'SIU: fetch t:{tag}, i:{index}. cnt: {fetch_count}')

        elif self.mode == 'evict' and mode == 'evict':
            if block_id in self.fetch_counters:
                self.fetch_counters[block_id] -= 1
            else:
                print(f'[!] Error: {self.__class__.__name__}.register() Trying '
                      'to register an eviction without a previous fetch. This '
                      'is an impossible situation.')
                sys.exit(1)

            # register events
            # if the counter is greater than one, then this was a SIU eviction
            delta_siu = 1 if self.fetch_counters[block_id] > 0 else 0
            if self.verb:
                t = '. SIU!' if delta_siu > 0 else ''
                t = t if self.mode == 'evict' else ''
                fetch_count = self.fetch_counters[block_id]
                print(f'SIU: evict t:{tag}, i:{index}{t}. cnt:{fetch_count}')
            event_idx = self.ic.val() # note that ic may skip values.
            if event_idx < len(self.events):
                # if the events[event_idx] exists, then just update it
                siu,tot = self.events[event_idx]
                self.events[event_idx] = (siu+delta_siu, tot+1)
                if event_idx+1 == len(self.events):
                    # if we happen to have just edited the last event,
                    # then update the last counters
                    self.siu_evict_count += delta_siu
                    self.tot_evict_count += 1
            else:
                # otherwise, pad events with zero counters so that
                # the index of a new append() is event_idx
                self._pad_events_list(event_idx)
                # update counters
                self.siu_evict_count += delta_siu
                self.tot_evict_count += 1
                self.events.append((self.siu_evict_count, self.tot_evict_count))
        return


    def _create_plotting_data(self):
        # create the list of percentages based on the counts in self.events.
        # This is straight forward:
        #    percentage = 100 * (siu_evicts)/(total_evicts)
        # However, if there are no evictions (those zero fills, and at the
        # beginning), just copy the previous value, as the ratio has not
        # changed.
        previous_percentage = 0
        self._pad_events_list(self.X[-1]+1)

        for siu,tot in self.events:
            if tot == 0:
                percentage = previous_percentage
            else:
                percentage = 100 * (siu)/(tot)
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


    def  plot(self, axes, basename='siu', extent=None):
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
        axes.set_title(f'{self.plot_title}: {basename}\n'
                       f'({self.plot_subtitle})')

        # setup Y ticks
        axes.tick_params(axis='y', which='both',
                         left=True, right=False,
                         labelleft=True, labelright=False)
        percentages = list(range(100 + 1)) # from 0 to 100
        y_ticks = self._create_up_to_n_ticks(percentages, base=10, n=5)
        axes.set_yticks(y_ticks)

        # setup Y label
        axes.yaxis.set_label_position('left')
        axes.set_ylabel(self.plot_y_label, color=self.plot_color_text,
                        labelpad=3.5)

        # setup Y grid
        axes.grid(axis='y', which='both', linestyle='-', alpha=0.2,
                  color=self.plot_color_line, linewidth=0.8, zorder=3)

        return
