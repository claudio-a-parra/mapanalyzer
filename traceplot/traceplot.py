#!/usr/bin/env python3
import sys # read command line arguments
import os # to clean paths
import csv # handle csv files
import matplotlib.pyplot as plt # draw plots
import matplotlib.patches as mpatches # to manually edit the legend
from matplotlib import colors # to create the colormap

options = {"in":None, "out":None, "title":None}
ops_n2v = {'R':1, 'W':2, 'Tc':101, 'Td':102, '?':999}
ops_v2n = {v: k for k, v in ops_n2v.items()}

def help():
    global options
    opts = "in=input_csv_file [out=output_pdf_file] [title=plot_title]"
    print(f"USAGE: {os.path.basename(sys.argv[0])} {opts}")
    print("Plots the memory tracing obtained from the mem_trace pintool.")
    return

def parse_args():
    # get input file name
    global options
    for arg in sys.argv[1:]:
        eq_idx = arg.find("=")
        arg_name = arg[:eq_idx]
        arg_val = arg[(eq_idx+1):]

        if arg_val == '':
            print(f"ERROR: argument '{arg}' malformed. Expected 'name=value'")
            help()
            exit(1)
        if arg_name in options:
            options[arg_name] = arg_val
        else:
            print(f"ERROR: Unknown argument name '{arg_name}'.'")
            help()
            exit(1)

    # error if no input file was given.
    if options["in"] == None:
        print(f"ERROR: Input file not given.")
        help()
        exit(1)

    # default output filename
    if options["out"] == None:
        options["out"] = '.'.join(options["in"].split('.')[:-1]) + ".pdf"
    return


class Clock:
    """Clock object that keeps track of the
    thread or system time position"""
    def __init__(self, clk):
        self.val = clk
        return
    @property
    def val(self):
        return self._val
    @val.setter
    def val(self, v):
        self._val = v
        return
    @val.deleter
    def val(self):
        self._val = None
        return

class ThreadEvent:
    def __init__(self, op_name, siz, off):
        try:
            if op_name not in ops_n2v:
                op_name = '?'

            self.operation = ops_n2v[op_name]
            self.size = int(siz)
            self.offset = int(off)
        except ValueError:
            print("Incorrect Value given to ThreadEvent()")
        except Exception:
            print("Something went wrong while calling ThreadEvent()")
        return

    def op_name(self):
        return ops_v2n[self.operation]

    def __format__(self, format_spec):
        op_name = ops_v2n[self.operation]
        return f"[{op_name:2}({self.operation:2}),{self.size:2},{self.offset:4}]"

class ThreadTrace:
    def __init__(self, clk:Clock, thrid):
        self.sys_clock_ref = clk
        self.threadid = thrid
        self.thr_clock = None
        self.times_list = []
        self.event_list = []
        return

    def set_mark(self, marker):
        # set a marker for later use in the graph.
        # use system_clock + 0.5 here, to signify that this event happened
        # after the last event, but before the next event.
        return

    def add_event(self, event):

        # If the thread was previously destroyed (by an event 'Td'), then the
        # thread clock should currently be None, otherwise the thread was not
        # previously destroyed, and is being created twice.
        if event.op_name() == 'Tc':
            if self.thr_clock == None:
                self.set_mark(event.op_name())
                self.thr_clock = self.sys_clock_ref.val
                return
            else:
                print("---------\n\n\n")
                raise Exception(f"Thread {self.threadid} registered two 'Tc' "
                                +"events not separated by a 'Td' event.")

        # if the action is to destroy the thread, then the thread should
        # reset its clock, so if it ever comes back alive, it shall take
        # the system's clock.
        if event.op_name() == 'Td':
            self.thr_clock = None
            self.set_mark(event.op_name())
            return

        # if the thread was supposedly destroyed, but we receive some event
        # on it different from 'Tc' (catched above), then let's assume a
        # 'Tc' and move on.
        if self.thr_clock == None:
            self.set_mark(event.op_name())
            self.thr_clock = self.sys_clock_ref.val

        # now actually adding the event to the trace
        self.thr_clock += 1
        self.times_list.append(self.thr_clock)
        self.event_list.append(event)

        # if this thread's time is the leading one, then update the system's clock
        if self.thr_clock > self.sys_clock_ref.val:
            self.sys_clock_ref.val = self.thr_clock
        return

    def __format__(self, format_spec):
        rtn  = f"thread  : {self.threadid}\n"
        rtn += f"thr_clk : {self.thr_clock}\n"
        for t,ac in zip(self.times_list,self.event_list):
            rtn += f"t:{t:4}, a:{ac}\n"
        return rtn

class SystemTrace:
    def __init__(self, blksize=0):
        self.block_size = blksize
        self.system_clock = Clock(-1)
        self.threads_trace = {}
        return

    def add_event(self, reg:dict):
        """Adds a new access to its corresponding thread trace."""
        threadid = int(reg["thread"])
        op_name = reg["action"]
        size = int(reg["size"])
        offset = int(reg["offset"])

        # If there is no knowledge of this thread, then create a trace for it.
        if threadid not in self.threads_trace:
            self.threads_trace[threadid] = ThreadTrace(self.system_clock, threadid)

        # add the thread event to that thread's trace.
        eve0 = ThreadEvent(op_name, size, offset)
        self.threads_trace[threadid].add_event(eve0)

        return

    def num_threads(self):
        return len(self.threads_trace)


    def to_matrix_form(self):
        """creates a list of dictionaries {'id','trace'}.
        - id    : the number of the thread
        - trace : a matrix with the size of the whole system trace (Y=block_size,
                  X=system_clock). But it only contains the operations performed
                  by that thread. The operations are:
                    - None if that thread did no operation
                    - 1 if it read data
                    - 2 if it wrote data
        """
        global ops_v2n
        block_size = self.block_size
        # +1 because sys_clock starts at 0 and by the end, it is equal to the last
        # valid index. So trace_length should be +1
        trace_length = self.system_clock.val+1
        rtn_list = []

        # for for each thread, create a 2-elements dictionary with the ID
        # and operations of that thread.
        for thr_id in self.threads_trace:
            # create the dictionary with an empty matrix
            nan = float('nan')
            trace = [[nan for x in range(trace_length)]
                             for y in range(block_size)]
            thread_trace_matrix = {'id':thr_id, 'trace':trace}

            # fill that matrix with the thread's data
            for eve,time in zip(
                    self.threads_trace[thr_id].event_list,
                    self.threads_trace[thr_id].times_list
            ):
                # events cover a certain 'size' in the memory block,
                # so repeat the event eve.size times.
                for i in range(eve.size):
                    trace[eve.offset+i][time] = eve.operation

            # add this thread_matrix_trace to the list to be returned
            rtn_list.append(thread_trace_matrix)
        return rtn_list
    
    def __format__(self, format_spec):
        rtn  = f"blk_size:{self.block_size}\n"
        rtn += f"sys_clk :{self.system_clock.val}\n\n"
        for tt in self.threads_trace:
            rtn += f"{self.threads_trace[tt]}\n"
        return rtn


def draw_trace(sys_trace, fig_height=20):

    # obtain the matrix form of the trace.
    access_matrices = sys_trace.to_matrix_form()


    # create discrete colormap
    palette = {0 :('#1f77b4','#81beea'),
               1 :('#ff7f0e','#ffc08a'),
               2 :('#2ca02c','#8ad68a'),
               3 :('#d62728','#efa9a9'),
               4 :('#9467bd','#cdb8e0'),
               5 :('#8c564b','#cda9a2'),
               6 :('#e377c2','#f2c0e3'),
               7 :('#7f7f7f','#bfbfbf'),
               8 :('#bcbd22','#ebeb8e'),
               9 :('#17becf','#8ce8f2'),
               10:('#fac800','#ffe680'),
               11:('#00eb95','#80ffd0')}


    if len(access_matrices) > len(palette):
        print("Warning! There are more threads than colors.")

    # plot artist
    fig, axe1 = plt.subplots()
    axe1.set_xlabel("Time of Access")
    axe1.set_ylabel("Offset within Memory Block [bytes]")
    axe1.set_yticks([2**x-1 for x in range(3,21)])
    axe1.set_ylim([-0.5,sys_trace.block_size+0.5])
    axe1.invert_yaxis()

    # draw gridlines
    axe1.grid(which='major', axis='both', linestyle='-', color='#ddd',
              linewidth=0.3, zorder=-1)
    axe1.set_axisbelow(True)

    # add legend and title
    legend_cols = {0: '#999', 1: '#ddd'}
    legend_labels = {0: 'Read (dark)', 1: 'Write (light)'}
    legend_patches =[mpatches.Patch(color=legend_cols[i],label=legend_labels[i])
                     for i in legend_cols]
    axe1.legend(handles=legend_patches, loc='best', borderaxespad=0)
    global options
    if options['title'] != None:
        axe1.set_title(options['title'], fontsize=20)

    # bounds such that R=1, and W=2 fit within their values:
    # 0.5 < R < 1.5 < W < 2.5
    color_bounds = [0.5, 1.5, 2.5]

    # quads edges
    x = [x-0.5 for x in range(sys_trace.system_clock.val+2)]
    y = [y-0.5 for y in range(sys_trace.block_size+1)]
    for color_idx,trace_dic in enumerate(access_matrices):
        color_idx = color_idx % len(palette)
        thr_id = trace_dic['id']
        thr_trace = trace_dic['trace']

        # pick a color and its faint variant for R/W ops
        thr_cmap = colors.ListedColormap([x for x in palette[color_idx]])
        thr_norm = colors.BoundaryNorm(color_bounds, thr_cmap.N)

        # draw plot
        axe1.pcolormesh(x, y, thr_trace,
                        cmap=thr_cmap,
                        shading='flat',
                        norm=thr_norm,
                        edgecolors='none',#'#eee',
                        #linewidth=0.01,
                        snap=True,
                        rasterized=False)

    # set the figure proportions to match the block_size/trace_length ratio
    fig_width = (fig_height*sys_trace.system_clock.val)/sys_trace.block_size
    fig.set_size_inches(fig_height,fig_width)
    fig.set_dpi(600)
    fig.set_size_inches(fig_width, fig_height)

    # export image
    print(f"traceplot: exporting {options['out']}...")
    fig.savefig(options["out"], bbox_inches='tight')
    return

def read_trace_log(open_file):
    print(f"traceplot: reading {options['in']}...")

    # search for line with byte size of the block.
    # once it is found, create the system trace with
    # that basic info.
    line_arr = ['']
    while line_arr[0] != "SIZE_BYTES":
        line_arr = [x.strip() for x in next(open_file).split(':')]
    sys_trace = SystemTrace(int(line_arr[1]))

    # search line after which the actual trace data starts in CSV format.
    while line_arr[0] != "TRACE_DATA_START":
        line_arr = [x.strip() for x in next(open_file).split(':')]


    # Now read the actual Memory Trace data
    # Open rest of the file in CSV format.
    # the fields in each row are:
    #    core
    #    action
    #    size
    #    offset
    # actions can be
    #    Tc : thread creation
    #    R : read
    #    W  : write
    #    Td : thread destruction
    csv_reader = csv.DictReader(open_file, delimiter=',')

    # pass one register at the time to the memory_trace object.
    # inside, it will figure out what to do with it.
    for eve in csv_reader:
        sys_trace.add_event(eve)
    return sys_trace


def main():
    global options
    parse_args()

    with open(options["in"], 'r', newline='') as open_file:

        # read log file from mem_trace
        trace = read_trace_log(open_file)

        print(f"Num of Threads: {list(trace.threads_trace.keys())}")
        # draw the memory trace as a mesh
        draw_trace(trace, fig_height=16)

    return

if __name__ == "__main__":
    main()
