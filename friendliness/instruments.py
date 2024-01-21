#!/usr/bin/env python3
from collections import deque
import matplotlib.pyplot as plt

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




#-------------------------------------------
class Instruments:
    def __init__(self, instr_counter, specs, verb=False):
        self.num_sets = specs['size']//(specs['asso']*specs['line'])
        self.line_size_bytes = specs['line']
        self.verb = verb
        self.ic = instr_counter
        self.alias = Alias(instr_counter, self.num_sets)
        self.miss_counter = MissCounter(instr_counter)
        self.line_usage = LineUsage(instr_counter, specs['line'])
        self.block_transport = BlockTransport(instr_counter)
        self.set_verbose(verb)
        self.metadata = {
            # (filename, title, unit, min_y, max_y)
            'al':('_plot_01-aliasing', 'Aliasing', 'rate',
                  0, 1),
            'mc':('_plot_02-miss-counter', 'Cache Miss Count', 'count',
                  0, 1),
            'lu':('_plot_03-line-usage', 'Line Usage Ratio', 'rate',
                  0, 1),
            'su':('_plot_04-siu-evictions', 'Still-in-Use Evictions', 'count',
                  0, 1),
            }

        # Each instrument has its own log, where each entry is a tuple:
        #    (instr, value)
        # instr: the instruction that registered some value for that
        #        instrument.
        # value: the registered value corresponding to that instruction.
        #
        # If a given instruction did NOT trigger a given instrument, then
        # the instrument's log just doesn't have an entry for that
        # instruction. So these instrument-logs are 'compressed' to just
        # what is necessary.
        #
        # The master_log expands all individual instrument logs into
        # strictly one entry per instruction, by calling each instrument's
        # 'deque' method. Then, master_log is a dictionary with one array
        # per instrument:
        #     master_log['al'] = [ al_0, al_1, ...., al_(n-1)]
        #     master_log['mc'] = [ mc_0, mc_1, ...., mc_(n-1)]
        #     master_log['lu'] = [ lu_0, lu_1, ...., lu_(n-1)]
        #     master_log['su'] = [ su_0, su_1, ...., su_(n-1)]
        # al: alias counter: Each al_i is a tuple with the set-ids involved
        #                    in evictions for that instruction.
        # mc: miss counter : Each mc_i is an integer with all the cache
        #                    misses produced by that instruction.
        # lu: line usage   : Each lu_i is a tuple with two elements:
        #                    - number of lines evicted
        #                    - total number of bytes used in those lines
        # su: siu evictions: Each su_i is an integer with all the
        #                    still-in-use evictions performed by that
        #                    instruction.
        # n: the total number of instructions. All arrays have n elements.
        self.master_log = {
            'al': [],
            'mc': [],
            'lu': [],
            'su': []
        }
        self.fml = { # filtered master log
            'al': [],
            'mc': [],
            'lu': [],
            'su': []
        }


    def enable_all(self):
        self.alias.enabled = True
        self.miss_counter.enabled = True
        self.line_usage.enabled = True
        self.block_transport.enabled = True


    def disable_all(self):
        self.alias.enabled = False
        self.miss_counter.enabled = False
        self.line_usage.enabled = False
        self.block_transport.enabled = False


    def prepare_for_second_pass(self):
        self.alias.enabled = False
        self.miss_counter.enabled = False
        self.line_usage.enabled = False
        self.block_transport.enabled = True
        self.block_transport.mode = 'evict'


    def set_verbose(self, verb=False):
        self.alias.verbose = verb
        self.miss_counter.verbose = verb
        self.line_usage.verbose = verb
        self.block_transport.verbose = verb


    def build_master_log(self):
        """Compute the master log as an aggregation of all the instruments'
        logs. Check comments in __init__() function"""
        if self.verb:
            print("Master Log:")
        for ic in range(self.ic.val()+1):
            al = self.alias.deque(ic)
            mc = self.miss_counter.deque(ic)
            lu = self.line_usage.deque(ic)
            su = self.block_transport.deque(ic)
            if self.verb:
                print(f"  Instruction: {ic}:\n"
                      f"    alias         : {al}\n"
                      f"    miss_counter  : {mc}\n"
                      f"    line_usage    : {lu}\n"
                      f"    SIU evictions : {su}\n")
            self.master_log['al'].append(al)
            self.master_log['mc'].append(mc)
            self.master_log['lu'].append(lu)
            self.master_log['su'].append(su)
        return


    # BUG
    def avg_window(self, al_arr, mc_arr, lu_arr, su_arr):
        """Given a slice of each component of the master log, compute the
        average for each of them"""

        # Alias --------------------
        #   Range: [0, 1]
        #   - 0: cache misses are equally distributed across sets.
        #   - 1: cache misses are falling all in the same set.
        #   Target: Minimize.
        hist = {}
        # Count frequency of each set
        for tup in al_arr:
            for set_index in tup:
                # create or increment counter for this set
                if set_index not in hist:
                    hist[set_index] = 1
                else:
                    hist[set_index] +=1
        # if no set was registered for the whole array, then there
        # is no aliasing.
        if len(hist) == 0:
            al_avg =  0
        else:
            # if there is only one set in the system, then any miss will
            # land in this set.
            if self.num_sets == 1:
                al_avg = 1
            # otherwise, obtain and normalize the ratio
            raw_ratio = max(hist.values()) / sum(hist.values())
            normalized_ratio = (raw_ratio - (1/self.num_sets)) * \
                (self.num_sets/(self.num_sets-1))
            al_avg = normalized_ratio

        # Miss Counter ---------------------
        #   Range: [0, inf]
        #   - 0: there were no cache misses.
        #   - n: there was a total of n cache misses in this array.
        #   Target: Minimize
        mc_sum = sum(mc_arr)

        # Line Usage -----------------------
        #   Range: [0, 1]
        #   - 0: none of the valid bytes in cache have been accessed.
        #   - 1: all valid bytes in the cache have been accessed.
        #   Target: Maximize
        lu_avg = sum(lu_arr)/len(lu_arr)

        # Still-in-use Evictions ----------
        #   Range: [0, inf]
        #   - 0: there were no SIU evictions.
        #   - n: there was a total of n SIU evictions.
        su_sum = sum(su_arr)

        return (al_avg, mc_sum, lu_avg, su_sum)


    def filter_log(self, win=5):
        if len(self.master_log) == 0:
            raise ValueError("The master log is empty. Cannot filter it.")
        # the length of the inner arrays, not the dict itself.
        n = len(self.master_log[next(iter(self.master_log))])
        if win <= 0 or win > n:
            raise ValueError(f"Invalid window size {win} for master_log of "
                             f"size {n}.")
        self.fml = {
            'al': [0] * (win-1),
            'mc': [0] * (win-1),
            'lu': [0] * (win-1),
            'su': [0] * (win-1),
        }
        for left in range(n - win + 1):
            right = left + win
            al_arr = self.master_log['al'][left:right]
            mc_arr = self.master_log['mc'][left:right]
            lu_arr = self.master_log['lu'][left:right]
            su_arr = self.master_log['su'][left:right]

            avg = self.avg_window(al_arr, mc_arr, lu_arr, su_arr)

            self.fml['al'].append(avg[0])
            self.fml['mc'].append(avg[1])
            self.fml['lu'].append(avg[2])
            self.fml['su'].append(avg[3])


    def plot_data(self, fname, win=5):
        """Return a filtered version of the master log."""
        self.filter_log(win=win)
        # the length of the inner arrays, not the dict itself.
        n = len(self.master_log[next(iter(self.master_log))])

        if self.verb:
            print(f"Filtered Log (win={win})")
            for ic in range(n):
                al = self.fml['al'][ic]
                mc = self.fml['mc'][ic]
                lu = self.fml['lu'][ic]
                su = self.fml['su'][ic]
                print(f"  Instruction: {ic}:\n"
                      f"    f_alias         : {al}\n"
                      f"    f_miss_counter  : {mc}\n"
                      f"    f_line_usage    : {lu}\n"
                      f"    f_SIU evictions : {su}\n")

        x = range(n)
        colors = ['red', 'green', 'blue', 'orange', 'black']
        for i,instrument in enumerate(self.fml):
            y = self.fml[instrument]
            fname_sufix,title,unit,min_y,max_y = self.metadata[instrument]
            col = colors[i%len(colors)]

            fig, ax = plt.subplots(figsize=(8, 6))
            ax.plot(x, y, color=col, linewidth=1.5)
            #ax.step(x, y, color=col, linewidth=1.5, where='post')
            ax.set_title(title+f' (window={win})')
            ax.set_ylim(min_y, max(max_y, max(y)))
            ax.set_ylabel(unit)
            fig.savefig(fname+fname_sufix+'.png', dpi=300,
                        bbox_inches='tight')







#-------------------------------------------
class Alias:
    """Triggered at each Cache miss. Logs which set is the one effecting
    the fetching."""
    def __init__(self, instr_counter, num_sets):
        self.enabled = True
        self.verbose = False
        self.ic = instr_counter
        # Array of nested tuples:
        #    (ic , (s0, s1, ...))
        # ic: instruction counter
        # sn: set index where a miss happened. (A single instruction could
        #     trigger more than a single line eviction.)
        self.log = deque()

    def append(self, index):
        if not self.enabled:
            return
        if self.verbose:
            i = hex(index)[2:]
            print(f"  [!] {self.__class__.__name__}: S{index}")

        self.log_append_increment(self.ic.val(), index)

    def log_append_increment(self, curr_instr, index):
        # append to log, or increment tuple of last log entry.
        if len(self.log) == 0 or self.log[-1][0] != curr_instr:
            self.log.append((curr_instr,(index,)))
        else:
            instr,indices_indices = self.log[-1]
            new_indices_tuple = indices_indices + (index,)
            self.log[-1] = (curr_instr, new_indices_tuple)

    def deque(self, query_instr):
        """If the instruction query_instr triggered cache misses, return
        a tuple with all the sets involved in those misses. Otherwise
        return an empty tuple"""
        if len(self.log) == 0 or self.log[0][0] != query_instr:
            return ()
        _, sets_involved = self.log.popleft()
        return sets_involved







#-------------------------------------------
class MissCounter:
    """Keep track of hits and misses."""
    def __init__(self, instr_counter):
        self.enabled = True
        self.verbose = False
        self.ic = instr_counter
        # Array of tuples:
        #     (ic, cm)
        # ic: instruction counter
        # cm: number of cache misses produced by this instruction
        self.log = deque()

    def append_miss(self):
        if not self.enabled:
            return
        if self.verbose:
            print(f"  [!] {self.__class__.__name__}: MISS")
        self.log_append_increment(self.ic.val())

    def log_append_increment(self, curr_instr):
        # append to log, or increment tuple of last log entry.
        if len(self.log) == 0 or self.log[-1][0] != curr_instr:
            self.log.append((curr_instr,1))
        else:
            instr,count = self.log[-1]
            self.log[-1] = (curr_instr, count+1)

    def deque(self, query_instr):
        """If the instruction query_instr triggered cache misses,
        return the number of cache misses, otherwise return 0"""
        if len(self.log) == 0 or self.log[0][0] != query_instr:
            return 0
        _, cache_misses = self.log.popleft()
        return cache_misses











#-------------------------------------------
class LineUsage:
    """Keep track of the ratio of line usage by the time the line gets
    evicted"""
    def __init__(self, instr_counter, line_size_bytes):
        self.enabled = True
        self.verbose = False
        self.ic = instr_counter
        self.line_size_bytes = line_size_bytes
        self.accessed_bytes = 0
        self.valid_bytes = 0
        self.last_ratio = 0
        # Array of tuples:
        #     (ic, (acc,tot))
        # ic : instruction counter. (log[i][0] < log[i+0][0])
        # acc: number of bytes accessed relative to...
        # tot: the total number of valid bytes in the cache.
        # Each tuple (nl,ac) is a copy of curr_valid_lines and
        # curr_tot_access
        self.log = deque()


    def update(self, delta_access, delta_valid):
        """Update the counters:
        - Number of bytes accessed from the current total of valid bytes.
        - Total number of valid bytes in Cache."""
        if not self.enabled:
            return
        # update counters
        self.accessed_bytes += delta_access
        self.valid_bytes += delta_valid
        if self.verbose:
            print(f"  [!] {self.__class__.__name__}: "
                  f"{self.accessed_bytes}/{self.valid_bytes}")

        # if the log is empty or there is NOT an entry for this
        # instruction, then add a new entry.
        curr_instr = self.ic.val()
        if len(self.log) == 0 or self.log[-1][0] != curr_instr:
            self.log.append((curr_instr,
                             (self.accessed_bytes, self.valid_bytes)))
        else:
            # if there was already an entry for this instruction,
            # disregard the previous (not complete) count and replace
            # it with the updated one.
            self.log[-1] = (curr_instr,
                            (self.accessed_bytes, self.valid_bytes))


    def deque(self, query_instr):
        """Return the ratio accessed_bytes/valid_bytes resulting after
        the execution of query_instr. If this query_instr made no
        changes (it is not in the log), then return the last ratio
        known (which is still valid for query_instr)"""
        if len(self.log) == 0 or self.log[0][0] != query_instr:
            return self.last_ratio
        _,acc_and_valid = self.log.popleft()
        acc,valid = acc_and_valid
        self.last_ratio = 0
        if valid != 0:
            self.last_ratio = acc/valid
        return self.last_ratio







#-------------------------------------------
class BlockTransport:
    """
    Let's define:
    - block         : group of bytes (data)
    - line          : space in Cache to store a block
    - line fetching : bringing a block from RAM.
    - line evicting : writing a block back to RAM.
    - SIU Eviction  : 'still-in-use' Eviction, eviction of a block that will
                      later be fetched back to Cache again.
    This counter works in two passes:
      - First pass: Fetch mode: We count all the times each block was fetched.
        Each fetch is a +1 to the counter of that particular block.
      - Second pass: Evict mode: With each eviction of a given block, we
        decrement its fetch counter. If after decrementing, the counter is NOT
        zero, then we know that the same block will be brought back to cache
        later, so this is a 'still-in-use' eviction.
    """
    def __init__(self, instr_counter):
        self.enabled = True
        self.verbose = False
        self.ic = instr_counter
        self.fetch_counters = {}
        # We run the first pass in fetch mode to fill the fetches-per-block
        # counters. The second pass runs in evict mode to use the previous
        # counters to check for 'still-in-use evictions'
        self.mode = 'fetch'

        # Array of tuples:
        #     (ic, su)
        # ic: instruction counter. (log[i][0] < log[i+1][0])
        # su: still-in-use evictions triggered by this instruction.
        self.log = deque()

    def append_fetch(self, index, tag):
        if not self.enabled or self.mode != 'fetch':
            return
        if (index, tag) in self.fetch_counters:
            self.fetch_counters[(index, tag)] += 1
        else:
            self.fetch_counters[(index, tag)] = 1
        if self.verbose:
            t = hex(tag)[2:]
            i = hex(index)[2:]
            print(f"  [!] {self.__class__.__name__}: "
                  f"fetch(s:{i},tag:{t})={self.fetch_counters[(index, tag)]}")
        return 0

    def append_evict(self, index: int, tag: int):
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
        if (index, tag) in self.fetch_counters:
           self.fetch_counters[(index, tag)] -= 1
        else:
            raise Exception("Trying to register eviction without a previous "
                            "fetch")
        # detect still-in-use eviction: if after the above decrementing the
        # counter is still greater than 0, then we are evicting an
        # 'still-in-use' block.
        fetches = self.fetch_counters[(index, tag)]
        if fetches > 0: # the block is later fetched again.
            if self.verbose:
                print(f" [!] {self.__class__.__name__}: "
                      "still-in-use eviction!")
            self.log_append_increment(self.ic.val())
        elif fetches == 0:
            if self.verbose:
                print(f" [!] {self.__class__.__name__}: "
                      "last eviction")
                # no siu-eviction -> nothing to add to the log.
        else:
            raise Exception(f"There are more evictions than fetches for "
                            f"tag:{hex(tag)}, index:{hex(index)}")
        return

    def log_append_increment(self, curr_instr):
        # append to log, or increment counter of last log entry.
        if len(self.log) == 0 or self.log[-1][0] != curr_instr:
            self.log.append((curr_instr,1))
        else:
            instr,counter = self.log[-1]
            self.log[-1] = (curr_instr,counter+1)

    def deque(self, query_instr):
        """If the instruction query_instr registered a siu-eviction,
        return that count, otherwise return 0
        """
        if len(self.log) == 0 or self.log[0][0] != query_instr:
            return 0
        _, siu_count = self.log.popleft()
        return siu_count
