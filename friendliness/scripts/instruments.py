#!/usr/bin/env python3
import sys
from collections import deque
import matplotlib.pyplot as plt
from matplotlib.colors import ListedColormap

class InstrCounter:
    """Instruction Counter"""
    def __init__(self):
        self.counter = -1

    def step(self):
        self.counter += 1

    def reset(self):
        self.counter = -1

    def val(self):
        return self.counter





class GenericInstrument:
    def __init__(self, instr_counter):
        self.enabled = True
        self.verbose = False
        self.ic = instr_counter
        self.events = deque()
        # event to dequeue from self.events if the queried instruction did not
        # generate events. if self.last_is_default == True, then the default is
        # constantly updated to the last real event.
        self.default_event = None
        self.last_is_default = False
        # log with as much events as instructions, and the filtered log with
        # averages of sliding windows.
        self.full_events_log = []
        self.filtered_avg_log = []
        self.avg_window = -1
        # details for the plots of this instrument.
        self.plot_details = ('_sufix', 'title', 'subtitle', 'y-axis',
                             0, 1) #min and max range
    def mix_events(self, base, new):
        """Return a mixed event based on two events 'base' and 'new'"""
        raise NotImplementedError("Overwrite this method")

    def avg_events(self, events_slice):
        """Given a slice of the full_events_log, compute and return its average"""
        raise NotImplementedError("Overwrite this method")

    def queue_event(self, new_event):
        """Add event related to the current instruction to the events queue. If
        there is already an event for the current instruction, mix both events."""
        ic = self.ic.val()
        if len(self.events) == 0 or self.events[-1][0] != ic:
            self.events.append((ic,new_event))
        else:
            curr_event = self.events[-1][1]
            mixed_event = self.mix_events(curr_event, new_event)
            self.events[-1] = (ic, mixed_event)

    def deque_event(self, query_instr):
        """Return the event produced by query_instr, or default_event."""
        if len(self.events) == 0 or self.events[0][0] != query_instr:
            return self.default_event
        _, curr_event = self.events.popleft()
        # update default event
        if self.last_is_default:
            self.default_event = curr_event
        return curr_event

    def build_log(self, instruction_ids_list):
        """Build this instrument's log with exactly one entry per
        instruction. If a given instruction produced no event, then
        fill the gap with the default event"""
        if self.verbose:
            print(f"{self.__class__.__name__}.full_events_log: ")
        for ic in instruction_ids_list:
            event = self.deque_event(ic)
            if self.verbose:
                print(f"    {event}")
            self.full_events_log.append(event)
        return

    def filter_log(self, win):
        """Compute a moving avg window from self.full_events_log and populate
        self.filtered_avg_log. Use self.avg_slice() to reduce a slice to
        the single value that represents this instrument."""
        n = len(self.full_events_log)
        # check if empty full_events_log or window is too large
        if n == 0:
            print(f"Error: {self.__class__.__name__}: self.full_events_log is empty. "
                  "Cannot filter it.")
            sys.exit(1)
        # check invalid window
        if win <= 0 or n < win:
            print(f"Error: {self.__class__.__name__}: Invalid given window "
                  f"size {win} for self.full_events_log of size {n}.")
            sys.exit(1)
        self.avg_window = win
        # fill the first (win-1) elements with 0, as there are no averages yet.
        self.filtered_avg_log = [0] * (win-1)
        for left in range(n - win+1):
            right = left + win
            raw_slice = self.full_events_log[left:right]
            avg = self.avg_events(raw_slice)
            self.filtered_avg_log.append(avg)



#-------------------------------------------
class AliasRatio(GenericInstrument):
    """
    - Definition : How evenly the different cache sets perform fetches.
    - Range      : 0: all block fetches are evenly performed by all sets. Good
                   1: all block fetches are performed by a single set. Bad.
    - Events     : Tuple of all Set-Indices fetching blocks due to a given
                   instruction. (s0, s1, ... ). the same set may appear several
                   times.
    - Trigger    : Block fetches
    """
    def __init__(self, instr_counter, num_sets):
        super().__init__(instr_counter)
        self.default_event = ()
        self.num_sets = num_sets
        self.plot_details = ('_plot-01-alias-ratio', # file sufix
                             'Aliasing', # plot title
                             'less is better', # subtitle
                             'Aliasing Ratio', # Y axis name
                             0, 1.05) # min-max


    def register_set_usage(self, index):
        if not self.enabled:
            return
        if self.verbose:
            i = hex(index)[2:]
            print(f"  [!] {self.__class__.__name__}: S{i}")
        self.queue_event((index,))

    def mix_events(self, base, new):
        return base + new

    def avg_events(self, events_slice):
        # if there is only one set in the system, then that set will do
        # all fetches
        if self.num_sets == 1:
            return 1
        # Count frequency of each set (create a histogram)
        hist = {}
        for tup in events_slice:
            for set_index in tup:
                # create or increment counter for this set
                if set_index not in hist:
                    hist[set_index] = 1
                else:
                    hist[set_index] +=1
        # if no set was registered for the whole array, then there
        # is no aliasing.
        if len(hist) == 0:
            return 0
        # otherwise, obtain ratio. Range: [1/n, 1]
        raw_ratio = max(hist.values()) / sum(hist.values())
        # and normalize it. Range: [0, 1]
        normalized_ratio = (raw_ratio - (1/self.num_sets)) * \
            (self.num_sets/(self.num_sets-1))
        return normalized_ratio



#-------------------------------------------
class MissRatio(GenericInstrument):
    """
    - Definition : The proportion of Cache misses with respect to all miss or
                   hits (miss/(miss+hit))
    - Range      : 0: no instruction triggers a cache miss. Good.
                   1: all instructions trigger cache misses. Bad.
    - Events     : i-th event is a tuple of two counters: (cm, ch), that is,
                   cache miss count and cache hit count produced by the
                   i-th instruction.
    - Trigger    : Every access to memory (because it will trigger either a
                   miss or a hit). A single instruction may access multiple
                   blocks.
    """
    def __init__(self, instr_counter):
        super().__init__(instr_counter)
        self.default_event = (0,0)
        self.plot_details = ('_plot-02-miss-ratio', # file sufix
                             'Cache Miss Ratio', # plot title
                             'less is better', # subtitle
                             'Cache Miss Ratio', # Y axis name
                             0, 1.05) # min-max

    def register_miss(self):
        if not self.enabled:
            return
        if self.verbose:
            print(f"  [!] {self.__class__.__name__}: MISS")
        self.queue_event((1,0)) # add one miss

    def register_hit(self):
        if not self.enabled:
            return
        if self.verbose:
            print(f"  [!] {self.__class__.__name__}: HIT")
        self.queue_event((0,1)) # add one hit

    def mix_events(self, base, new):
        mc,hc = base
        new_mc,new_hc = new
        return (mc+new_mc, hc+new_hc)

    def avg_events(self, events_slice):
        miss,total = 0,0
        for tup in events_slice:
            miss += tup[0]
            total += tup[0] + tup[1]
        if total == 0:
            print(f"Error: {self.__class__.__name__}: total miss+hit in slice "
                  "is 0. This should be impossible.")
            sys.exit(1)
        return miss/total



#-------------------------------------------
class ByteUsageRatio(GenericInstrument):
    """
    - Definition: Ratio measuring valid bytes in cache that were actually
                  accessed vs the total number of valid bytes in the cache.
                  (valid_accessed)/(total_valid)
    - Range     : 0: none of the valid bytes has been accessed. Only achievable
                     by manually fetching blocks to cache. Bad.
                  1: all bytes in cache have been accessed at least once. (Good)
    - Event     : Tuple with two counters: (acc, val), that is, current count
                  for accessed valid bytes in cache, and current total valid
                  bytes in cache.
    - Trigger   : Evictions, Fetches, and Accesses to valid lines:
                  - Evictions: remove (valid) accessed bytes, remove valid
                               bytes.
                  - Fetches: add new valid bytes.
                  - Access (to valid lines): add accessed bytes.
    """
    def __init__(self, instr_counter, line_size_bytes):
        super().__init__(instr_counter)
        self.default_event = (0,0)
        self.last_is_default = True
        self.line_size_bytes = line_size_bytes
        self.accessed_bytes = 0
        self.valid_bytes = 0
        self.plot_details = ('_plot-03-byte-access-ratio', # file sufix
                             'Ratio of Valid Bytes Accessed', # plot title
                             'more is better', # subtitle
                             'Bytes Access Ratio', # Y axis name
                             0, 1.05) # min-max

    def register_delta(self, delta_access, delta_valid):
        """Update the counters:
        - positive delta_access: newly accessed bytes.
        - negative delta_access: bytes that have been accessed are now evicted.
        - positive delta_valid: fetching block.
        - negative delta_valid: evicting block."""
        if not self.enabled:
            return
        # update current counters
        self.accessed_bytes += delta_access
        self.valid_bytes += delta_valid
        if self.verbose:
            print(f"  [!] {self.__class__.__name__}: "
                  f"{self.accessed_bytes}/{self.valid_bytes}")

        event = (self.accessed_bytes, self.valid_bytes)
        self.queue_event(event)

    def mix_events(self, base, new):
        """ the new counter just replace the old one, as this is more updated"""
        return new

    def avg_events(self, events_slice):
        if len(events_slice) == 0:
            print(f"Error: {self.__class__.__name__}: Slice of size 0")
            sys.exit(1)
        used, valid = list(zip(*events_slice))
        tot_used = sum(used)
        tot_valid = sum(valid)
        if tot_valid == 0:
            # not having valid bytes is a problem if there are also "accessed"
            # bytes.
            if tot_used > 0:
                print(f"Error: {self.__class__.__name__}: Total valid bytes is 0 "
                      "for the given slice.")
                sys.exit(1)
            else:
                return 0
        return tot_used / tot_valid


#-------------------------------------------
class SIURatio(GenericInstrument):
    """
    - Definition: Ratio between number of evictions on blocks that will later
                  be fetched again, vs the total number of evictions done.
    - Range     : 0: every block eviction is final.
                  1: every block evicted by this instruction (or slice) is
                     later fetched back to memory.
    - Event     : tuple with two counters (siu_evictions, total_evictions)
    - Trigger   : In the first pass, only fetches trigger the instrument; but
                  the actual SIU counting happens in the second pass with
                  every eviction.

    This is an special counter, because it needs to pass through the memory
    access pattern two times in order to be computed.
      - First pass: Fetch mode: We count all the times each block was fetched.
        Each fetch is a +1 to the counter of that particular block.
      - Second pass: Evict mode: With each eviction of a given block, we
        decrement its fetch counter. If after decrementing, the counter is NOT
        zero, then we know that the same block will be brought back to cache
        later, so this is a 'still-in-use' eviction.
    """
    def __init__(self, instr_counter):
        super().__init__(instr_counter)
        self.default_event = (0,0)
        # to register the fetches number of fetches performed on each block.
        self.fetch_counters = {}
        # We run the first pass in fetch mode to fill the block's fetch counter.
        # The second pass runs in evict mode to use the previous counters to
        # check for 'still-in-use evictions'
        self.mode = 'fetch'
        self.plot_details = ('_plot-04-siu-eviction-ratio', # file sufix
                             'Ratio of Still-in-Use Block Evictions.', # plot title
                             'less is better', # subtitle
                             '"I\'ll be back" Ratio', # Y axis name
                             0, 1.05) # min-max

    def register_fetch(self, index, tag):
        if not self.enabled or self.mode != 'fetch':
            return
        block_id = (index, tag)
        if block_id in self.fetch_counters:
            self.fetch_counters[block_id] += 1
        else:
            self.fetch_counters[block_id] = 1
        if self.verbose:
            t = hex(tag)[2:]
            i = hex(index)[2:]
            print(f"  [!] {self.__class__.__name__}: "
                  f"fetch(s:{i},tag:{t})={self.fetch_counters[block_id]}")
        return 0

    def register_evict(self, index: int, tag: int):
        """
        Given the first pass, we already know how many times we ever fetch
        each block. Now, in this eviction, check whether the current block
        is later fetched again. If that is the case, add a 'still-in-use'
        eviction to the log.
        """
        if not self.enabled or self.mode != 'evict':
            return
        # for every earlier fetch of a block, there should be an eviction,
        # then, this eviction decrements the fetch counter of this block.
        block_id = (index, tag)
        if block_id in self.fetch_counters:
           self.fetch_counters[block_id] -= 1
        else:
            raise Exception("Trying to register eviction without a previous "
                            "fetch")
        # detect still-in-use eviction: if after the above decrementing the
        # counter is still greater than 0, then we are evicting an
        # 'still-in-use' block.
        resulting_fetches = self.fetch_counters[block_id]
        if resulting_fetches > 0: # the block is later fetched again.
            new_event = (1, 1)
            if self.verbose:
                print(f" [!] {self.__class__.__name__}: "
                      "still-in-use eviction!")
        elif resulting_fetches == 0:
            new_event = (0, 1)
            if self.verbose:
                print(f" [!] {self.__class__.__name__}: "
                      "last eviction")
        else:
            raise Exception(f"There are more evictions than fetches for "
                            f"tag:{hex(tag)}, index:{hex(index)}")

        self.queue_event(new_event)
        return

    def mix_events(self, base, new):
        curr_siu,curr_tot = base
        new_siu,new_tot = new
        return (curr_siu+new_siu, curr_tot+new_tot)

    def avg_events(self, events_slice):
        if len(events_slice) == 0:
            print(f"Error: {self.__class__.__name__}: Slice of size 0")
            sys.exit(1)
        siu, evics = list(zip(*events_slice))
        tot_siu = sum(siu)
        tot_evics = sum(evics)
        if tot_evics == 0:
            if tot_siu > 0:
                print(f"Error: {self.__class__.__name__}: Total evictions is 0 "
                      f"for the given slice, but {tot_siu} evictions are "
                      "reported to be SIU")
                sys.exit(1)
            else:
                # no siu or other evictions means we are just reading from
                # valid caches. That is good -> return 0
                return 0
        return tot_siu / tot_evics



#-------------------------------------------
class Instruments:
    def __init__(self, instr_counter, specs, ap, plots_dims=(8,6), ap_factor=100,
                 verb=False):
        self.num_sets = specs['size']//(specs['asso']*specs['line'])
        self.line_size_bytes = specs['line']
        self.access_pattern = ap
        self.saving_ids = True # save instruction ids only in the first pass
        self.verb = verb
        self.instruction_ids = [] # registry of all instructions ids processed
        self.ic = instr_counter

        # Instruments
        self.alias = AliasRatio(instr_counter, self.num_sets)
        self.miss = MissRatio(instr_counter)
        self.usage = ByteUsageRatio(instr_counter, specs['line'])
        self.siu = SIURatio(instr_counter)

        self.set_verbose(verb)
        self.metadata = {'alias':self.alias.plot_details,
                         'miss':self.miss.plot_details,
                         'usage':self.usage.plot_details,
                         'siu':self.siu.plot_details}

        # Plot sizes
        self.plot_width = plots_dims[0]
        self.plot_height = plots_dims[1]

        # if you handle the matrix [Mem x Time], this shit blows up.
        # So we will map all accesses to a reduced version of that matrix:
        # the access_matrix.
        # That matrix has the size of a plot, but amplified by ap_factor.
        # however, for small [Mem x Time] situations, ap_factor*plot_height
        # may end up being bigger than just the extension of Mem.
        if ap_factor*self.plot_height > self.access_pattern.block_size:
            self.ap_factor = \
                round(self.access_pattern.block_size / self.plot_height)
        else:
            self.ap_factor = ap_factor

        # matrix where to draw the memory access pattern. It's size is not
        # the potentially huge [Mem x Time], but a smaller [cols x rows].
        #   cols = ap_factor*plots_width
        #   rows = ap_factor*plots_height
        # The real coordinates of the memory access pattern are mapped to
        # this space. This matrix populated by self.add_access()
        self.access_matrix = [[0] * self.ap_factor*self.plot_width
                              for _ in range(self.ap_factor*self.plot_height)]

    def enable_all(self):
        self.alias.enabled = True
        self.missr.enabled = True
        self.usage.enabled = True
        self.siu.enabled = True

    def disable_all(self):
        self.alias.enabled = False
        self.miss.enabled = False
        self.usage.enabled = False
        self.siu.enabled = False

    def prepare_for_second_pass(self):
        self.alias.enabled = False
        self.miss.enabled = False
        self.usage.enabled = False
        self.siu.enabled = True
        self.siu.mode = 'evict'
        self.saving_ids = False

    def set_verbose(self, verb=False):
        self.alias.verbose = verb
        self.miss.verbose = verb
        self.usage.verbose = verb
        self.siu.verbose = verb

    def build_log(self):
        self.alias.build_log(self.instruction_ids)
        self.miss.build_log(self.instruction_ids)
        self.usage.build_log(self.instruction_ids)
        self.siu.build_log(self.instruction_ids)

    def filter_log(self, win):
        self.alias.filter_log(win)
        self.miss.filter_log(win)
        self.usage.filter_log(win)
        self.siu.filter_log(win)

    def register_access(self, access):
        """The idea is to take an access happening at (addr, time), and map it
        to (y,x) in self.access_matrix."""
        if self.saving_ids:
            self.instruction_ids.append(access.time) # save instruction id
        for i in range(access.size):
            # obtain the original coordinates
            addr = access.addr - self.access_pattern.base_addr + i
            time = access.time
            # transform to a percentage form [0-1)
            addr = addr / self.access_pattern.block_size
            time = time / self.access_pattern.time_size
            # obtain the size of the access matrix
            acc_addr_size = len(self.access_matrix)
            acc_time_size = len(self.access_matrix[0])
            # now map the coordinate to the access_matrix. -1 so we don't overflow
            addr_acc = round(addr * (acc_addr_size-1))
            time_acc = round(time * (acc_time_size-1))
            # store the value in the matrix. The stored value is the thread
            # number + 1 so empty cells remain 0 and used cells become 1, 2, 3, ...
            self.access_matrix[addr_acc][time_acc] = 1+access.thread

    def plot(self, base_name):
        """Create all instrument plots with the access pattern in the
        background"""
        #### Plot Access Pattern
        # obtain as many different colors as threads in the access pattern.
        colors_needed = self.access_pattern.thread_count
        palette = {
            0 :('#1f77b4','#81beea'), # Steel Blue
            1 :('#ff7f0e','#ffc08a'), # Dark Orange
            2 :('#2ca02c','#8ad68a'), # Dark Green
            3 :('#d62728','#efa9a9'), # Red
            4 :('#9467bd','#cdb8e0'), # Slate Blue
            5 :('#8c564b','#cda9a2'), # Sienna
            6 :('#e377c2','#f2c0e3'), # Orchid Pink
            7 :('#7f7f7f','#bfbfbf'), # Gray
            8 :('#bcbd22','#ebeb8e'), # Olive Green
            9 :('#17becf','#8ce8f2'), # Cyan
            10:('#fac800','#ffe680'), # Yellow
            11:('#00eb95','#80ffd0')} # Turquoise Green
        if colors_needed > len(palette):
            print(f'Warning: The Access Pattern has more threads than colors '
                  'available to plot. Different threads will share colors.')
        cmap = ListedColormap(
            ['#eeeeee'] + [palette[i%len(palette)][0]
                       for i in range(colors_needed)])

        #### Plot instruments
        # Instruments colors and plots
        col_instr = ['red', 'green', 'blue', 'orange', 'black']
        plt_instr = []
        # # the X axis represents time (of the instruction)
        # shared_x = range(self.access_pattern.time_size)
        instruments = (self.alias, self.miss, self.usage, self.siu)
        for color_index,instr in enumerate(instruments):
            sufix,title,subtitle,y_label,min_y,max_y = instr.plot_details
            print(f'    plotting {title}...')
            # get data
            # instr_y = self.fml[instrument]
            instr_y = instr.filtered_avg_log
            #instr_x = range(len(self.fml[instrument]))
            instr_x = self.instruction_ids # range(len(instr_y))
            if len(col_instr) <= color_index:
                print('[!] Warning, there are more instruments than colors '
                'for them.')
            col_i = col_instr[color_index % len(col_instr)]

            max_y = max(max(instr_y), max_y) * 1.02 # 2% margin
            # do the drawings
            plt.imshow(
                self.access_matrix,
                cmap=cmap,
                aspect='auto',
                extent=[instr_x[0]-1, instr_x[-1]+1, 0, max_y]
            )
            # plt.pcolor(self.access_matrix, cmap=cmap,
            #            extent=[min(instr_x), max(instr_x), 0, len(instr_y)])

            plt.ylim(min_y, max_y)
            plt.xlabel('Instruction')
            plt.ylabel(y_label)
            plt.title(base_name+': '+
                      title+f'\n'
                      f'(w={instr.avg_window}, '+subtitle+')')
            plt.step(
                instr_x,
                instr_y,
                color=col_i,
                linewidth=1.5,
                where='post')
            plt.xlim(instr_x[0]-1, instr_x[-1]+1)
            plt.grid(axis='x', linestyle='-', alpha=0.7, linewidth=0.3, which='both')
            plt.savefig(base_name+sufix+'.png', dpi=600,
                        bbox_inches='tight')
            plt.clf()
