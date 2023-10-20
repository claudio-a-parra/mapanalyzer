#!/usr/bin/env python3
import sys # read command line arguments
import os # to clean paths
import csv # handle csv files
import matplotlib.pyplot as plt # draw plots
import matplotlib.patches as mpatches # to manually edit the legend
from matplotlib import colors # to create the colormap

options = {"in":None, "out":None, "title":None}

class MemoryAccess:
    action = ''
    size = 0
    offset = 0
    def __init__(self, act, siz, off):
        try:
            self.action = act
            self.size = int(siz)
            self.offset = int(off)
        except ValueError:
            print("Incorrect Value given to MemoryAccess()")
        except Exception:
            print("Something went wrong parsing the input line")
        return

    def __format__(self, format_spec):
        return f"[{self.action},{self.size:2},{self.offset:4}]"

class ThreadTrace:
    clock = None
    thread = None
    times_list = None
    access_list = None

    def __init__(self, clk, thr):
        self.clock = clk
        self.thread = thr
        self.times_list = []
        self.access_list = []
        return

    def add(self, mem_access):
        #if self.thread == 1:
        #   print(f"thr: {self.thread}, clock: {self.clock}, times_list:{self.times_list}")
        self.clock += 1
        self.times_list.append(self.clock)
        self.access_list.append(mem_access)
        #if self.thread == 1:
        #    print(f"thr: {self.thread}, clock: {self.clock}, times_list:{self.times_list}")
        return self.clock

    def __format__(self, format_spec):
        rtn  = f"thread  : {self.thread}\n"
        rtn += f"thr_clk : {self.clock}\n"
        for t,ac in zip(self.times_list,self.access_list):
            rtn += f"t:{t:4}, a:{ac}\n"
        return rtn

class SystemTrace:
    block_size = None
    system_clock = None
    threads_trace = None

    def __init__(self, blksize=0):
        self.block_size = blksize
        self.system_clock = -1
        self.threads_trace = {}
        return


    def add(self, reg:dict):
        thread = int(reg["thread"])
        action = reg["action"]
        size = int(reg["size"])
        offset = int(reg["offset"])

        # if it is thread destruction, don't do anything
        if action == "Td":
            return

        # If there is no knowledge of this thread, then create a trace for it.
        if thread not in self.threads_trace:
            #print(f"{thread} is not in threads_trace")
            self.threads_trace[thread] = ThreadTrace(self.system_clock, thread)

        # if it is thread creation or destruction, there is nothing to add.
        if action == "Tc":
            return

        # at this point, we have a trace for this thread, and we
        # know the action is R or W, so we record it in the thread's trace.
        acc0 = MemoryAccess(action, size, offset)
        #print(f"thr: {thread}, act: {acc0}")
        thread_clock = self.threads_trace[thread].add(acc0)

        # if the thread is the one ahead, then update the system clock.
        if thread_clock > self.system_clock:
            self.system_clock = thread_clock

        return

    def __format__(self, format_spec):
        rtn  = f"blk_size:{self.block_size}\n"
        rtn += f"sys_clk :{self.system_clock}\n\n"
        for tt in self.threads_trace:
            rtn += f"{self.threads_trace[tt]}\n"
        return rtn

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

def draw_trace(mem_trace, fig_height=20):
    global options

    # create a matrix that maps one operations to numbers: 10: no-operation,
    # 20: read access, 30: write access.
    # Extract data
    access_matrix = [
        [10 for x in range(mem_trace.len())]
        for y in range(mem_trace.block_size)]
    for ac in mem_trace.access_list:
        for i in range(ac.size):
            access_matrix[ac.offset+i][ac.time] = 20 if ac.action=='R' else 30

    # create discrete colormap
    cmap = colors.ListedColormap(['white', 'green', 'red'])
    bounds = [0,15,25,35]
    norm = colors.BoundaryNorm(bounds, cmap.N)

    # plot artists
    fig, axe1 = plt.subplots()
    axe1.set_xlabel("Time of Access")
    axe1.set_ylabel("Offset within Memory Block [bytes]")
    axe1.set_yticks([2**x for x in range(3,21)])
    axe1.set_ylim([-0.5,mem_trace.block_size+0.5])
    axe1.invert_yaxis()

    # draw gridlines
    axe1.grid(which='major', axis='both', linestyle='-',
              color='#ddd', linewidth=0.3, zorder=-1)
    axe1.set_axisbelow(True)

    # add legend and title
    legend_cols = {0: 'green', 1: 'red'}
    legend_labels = {0: 'read', 1: 'write'}
    legend_patches =[mpatches.Patch(color=legend_cols[i],label=legend_labels[i])
                     for i in legend_cols]
    axe1.legend(handles=legend_patches, loc='best', borderaxespad=0)
    if options['title'] != None:
        axe1.set_title(options['title'], fontsize=20)

    # draw plot
    axe1.imshow(access_matrix,
                cmap=cmap,
                norm=norm,
                interpolation='none')

    # set the figure proportions to match the block_size/trace_length ratio
    fig_width = (fig_height*mem_trace.len())/mem_trace.block_size
    fig.set_size_inches(fig_height,fig_width)
    fig.set_dpi(300)
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
    i = 0
    for register in csv_reader:
        sys_trace.add(register)
    return sys_trace


def main():
    global options
    parse_args()

    with open(options["in"], 'r', newline='') as open_file:

        # read log file from mem_trace
        trace = read_trace_log(open_file)

        # draw the memory trace as a mesh
        draw_trace(trace, fig_height=20)

    return

if __name__ == "__main__":
    main()
