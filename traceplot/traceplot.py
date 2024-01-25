#!/usr/bin/env python3
import sys # read command line arguments
import os # to clean paths
import csv # handle csv files
import matplotlib.pyplot as plt # draw plots
import matplotlib.patches as mpatches # to manually edit the legend
from matplotlib import colors # to create the colormap

from PIL import Image

options = {"in":None, "out":None, "title":None}
ops_n2v = {'R':0, 'W':1, 'Tc':101, 'Td':102, '?':999}
ops_v2n = {v: k for k, v in ops_n2v.items()}

class Event:
    def __init__(self, time, ev_name, siz, off):
        try:
            if ev_name not in ops_n2v:
                ev_name = '?'
            self.time = time
            self.event = ops_n2v[ev_name]
            self.size = int(siz)
            self.offset = int(off)
        except ValueError:
            print("Incorrect Value given to ThreadEvent()")
        except Exception:
            print("Something went wrong while calling ThreadEvent()")
        return

    def event_name(self):
        return ops_v2n[self.event]

    def __format__(self, format_spec):
        eve_name = ops_v2n[self.event]
        return f"[{self.time},{eve_name:2}({self.event:2}),{self.size:2},{self.offset:4}]"


class SystemTrace:
    def __init__(self, block_size, max_qtime):
        """The system trace is a dictionary with thread ids as keys,
        and an array of 'Events' as values"""
        self.block_size = block_size
        self.max_qtime = max_qtime
        self.thread_count = 0
        self.threads_trace = {}
        return

    def add_event(self, reg:dict):
        """Adds a new event to its corresponding thread trace."""
        qtime = int(reg["time"])
        threadid = int(reg["thread"])
        event = reg["event"]
        size = int(reg["size"])
        offset = int(reg["offset"])

        # If it is not a read/write event, dismiss
        if event != 'R' and event !='W':
            return

        # If there is no knowledge of this thread, then create a trace for it.
        if threadid not in self.threads_trace:
            self.thread_count += 1
            self.threads_trace[threadid] = []

        # add the thread event to that thread's trace.
        eve0 = Event(qtime, event, size, offset)
        self.threads_trace[threadid].append(eve0)

        return

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
        trace_length = self.max_qtime+1
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
            for eve in self.threads_trace[thr_id]:
                # events cover a certain 'size' in the memory block,
                # so repeat the event eve.size times.
                for i in range(eve.size):
                    trace[eve.offset+i][eve.time] = eve.event

            # add this thread_matrix_trace to the list to be returned
            rtn_list.append(thread_trace_matrix)
        return rtn_list

    def __format__(self, format_spec):
        rtn  = f"blk_size:{self.block_size}\n"
        rtn += f"sys_clk :{self.max_qtime}\n\n"
        for tt in self.threads_trace:
            rtn += f"{self.threads_trace[tt]}\n"
        return rtn


def help():
    global options
    opts = "in=input_csv_file [out=output_pdf_file] [title=plot_title]"
    print(f"    USAGE: {os.path.basename(sys.argv[0])} {opts}")
    print("Plots the memory tracing obtained from the mem_trace pintool.")
    return


def parse_args():
    global options
    for arg in sys.argv[1:]:
        eq_idx = arg.find("=")
        arg_name = arg[:eq_idx]
        arg_val = arg[(eq_idx+1):]

        if arg_val == '':
            print(f"ERROR: argument '{arg}' malformed. Expected 'name=value'")
            help()
            exit(1)
        if  arg_name not in options:
            print(f"ERROR: Unknown argument name '{arg_name}'.'")
            help()
            exit(1)
        options[arg_name] = arg_val
    # error if no input file was given.
    if options["in"] == None:
        print(f"ERROR: Input file not given.")
        help()
        exit(1)

    # default output filename
    if options["out"] == None:
        options["out"] = '.'.join(options["in"].split('.')[:-1]) + ".pdf"
    return








def draw_trace(sys_trace, fig_height=20):

    # obtain the matrix form of the trace.
    print("Log to Matrix format...")
    access_matrices = sys_trace.to_matrix_form()
    print("Log to Matrix format: OK")

    # create discrete colormap
    palette = {0 :('#1f77b4','#81beea'), # Steel Blue
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
    x = [x-0.5 for x in range(sys_trace.max_qtime+2)]
    y = [y-0.5 for y in range(sys_trace.block_size+1)]
    print("traceplot: drawing threads:", end="")
    for color_idx,trace_dic in enumerate(access_matrices):
        color_idx = color_idx % len(palette)
        thr_id = trace_dic['id']
        thr_trace = trace_dic['trace']

        # pick a color and its faint variant for R/W ops
        thr_cmap = colors.ListedColormap([x for x in palette[color_idx]])
        thr_norm = colors.BoundaryNorm(color_bounds, thr_cmap.N)

        # draw plot
        print(f" t{thr_id}", end="")
        axe1.pcolor(x, y, thr_trace,
                    cmap=thr_cmap, shading='flat', norm=thr_norm,
                    # edgecolors='#eee', linewidth=0.01,
                    snap=True,
                    rasterized=True)

    # set the figure proportions to match the block_size/trace_length ratio
    print("")
    fig_width = (fig_height*sys_trace.max_qtime)/sys_trace.block_size
    fig.set_size_inches(fig_height,fig_width)
    fig.set_dpi(800)
    fig.set_size_inches(fig_width, fig_height)

    # export image
    print(f"traceplot: exporting {options['out']}...")
    fig.savefig(options["out"], bbox_inches='tight')
    return






def draw_png(sys_trace):
    palette_rgb = {
        0:  (( 31, 119, 180), (129, 190, 234)), # Blue
        1:  ((255, 127,  14), (255, 192, 138)), # Orange
        2:  (( 44, 160,  44), (138, 214, 138)), # Green
        3:  ((214, 39,   40), (239, 169, 169)), # Red
        4:  ((148, 103, 189), (205, 184, 224)), # Purple
        5:  ((140,  86,  75), (205, 169, 162)), # Brown
        6:  ((227, 119, 194), (242, 192, 227)), # Pink
        7:  ((127, 127, 127), (191, 191, 191)), # Gray
        8:  ((188, 189,  34), (235, 235, 142)), # Yellow
        9:  (( 23, 190, 207), (140, 232, 242)), # Cyan
        10: ((250, 200,   0), (255, 230, 128)), # Gold
        11: ((  0, 235, 149), (128, 255, 208))  # Turquoise
    }
    bg_col = (255,255,255,255)

    # Create a nested list with RGBA values
    width, height = sys_trace.max_qtime+1, sys_trace.block_size


    rgba_list = [[bg_col for _ in range(width)] for _ in range(height)]

    for thr_id in sys_trace.threads_trace:
        thr_trace = sys_trace.threads_trace[thr_id]
        thr_color = palette_rgb[thr_id % len(palette_rgb)]
        for eve in thr_trace:
            for i in range(eve.size):
                rgba_list[eve.offset+i][eve.time] = thr_color[eve.event]

    # Flatten the nested list to a 1D list
    flat_rgba_list = [value for row in rgba_list for value in row]

    # Create PIL Image from the flattened list
    image = Image.new("RGBA", (width, height))
    image.putdata(flat_rgba_list)

    # Save the image or display it
    fname = f"plot_{sys_trace.block_size}x{sys_trace.max_qtime+1}_" \
        +f"{sys_trace.thread_count}t"
    print(f"Plot saved in {fname}.png")
    image.save(fname+".png")

    return

def read_trace_log(open_file):
    # search for block-size and max-qtime in the header of the trace file
    line_arr = ['']
    block_size = 0
    max_qtime = 0

    while line_arr[0] != "# DATA":
        line_arr = [x.strip() for x in next(open_file).split(':')]
        if line_arr[0] == "block-size":
            block_size = int(line_arr[1])
        elif line_arr[0] == "max-qtime":
            max_qtime =  int(line_arr[1])

    if block_size == 0 or max_qtime == 0:
        raise Exception(f"The trace file {options['in']} does not contain valid"
                        " values for 'block-size', 'thread-count', or 'max-qtime' in its metadata.")

    # create the system trace
    sys_trace = SystemTrace(block_size, max_qtime)


    # Now read the actual Memory Trace data
    # Open rest of the file in CSV format.
    # the fields in each row are:
    #    time   : the time at which the event happened
    #    thread : the thread performing the event
    #    event  : which event (defined below)
    #    size   : the size of the memory operation (if the event reads/write memory)
    #    offset : the read/write offset from the beginning of the monitored memory block.
    # actions can be
    #    Tc : thread creation
    #    Td : thread destruction
    #    R  : read
    #    W  : write
    #    ?  : unknown event
    csv_reader = csv.DictReader(open_file, delimiter=',')

    # shred merged list into one-list-per-thread.
    for eve in csv_reader:
        sys_trace.add_event(eve)
    return sys_trace


def main():
    global options
    parse_args()

    with open(options["in"], 'r', newline='') as open_file:

        # read log file from mem_trace
        sys_trace = read_trace_log(open_file)

        # draw the memory trace
        #draw_trace(sys_trace, fig_height=20)
        draw_png(sys_trace)

    return


if __name__ == "__main__":
    main()
