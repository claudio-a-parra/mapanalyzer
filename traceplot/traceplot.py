#!/usr/bin/env python3

import sys # read command line arguments
import csv # handle csv files
import matplotlib.pyplot as plt # draw plots
import matplotlib.patches as mpatches # to manually edit the legend
from matplotlib import colors # to create the colormap

in_csv=None
out_pdf=None

class MemAccess:
    coreid = 0
    time = 0
    action = ''
    size = 0
    offset = 0
    def __init__(self, raw_dict):
        try:
            self.coreid = int(raw_dict["core"])
            self.time = raw_dict["time"]
            self.action = raw_dict["action"]
            self.size = int(raw_dict["size"])
            self.offset = int(raw_dict["offset"])
        except ValueError:
            print("Incorrect Value")
        except Exception:
            print("Something went wrong parsing the input line")
        return

    def __repr__(self):
        return f"{self.coreid}, {self.action}, {self.size}, {self.offset}"

class MemTrace:
    block_size = 0
    access_list = []
    def __init__(self, blsize=0):
        self.block_size = blsize
        return

    def append(self, new_access):
        self.access_list.append(new_access)
        return

    def len(self):
        return len(self.access_list)

    def __repr__(self):
        rtn = f"Block size: {self.block_size}\n"
        rtn += "coreID, W, Size, Offset\n"
        for ac in self.access_list:
            rtn += f"{ac[0]}: {ac[1]!r}\n"
        return rtn

def help():
    print(f"USAGE: {sys.argv[0]} <input.csv>")
    print("Plots the memory tracing obtained from the tracechunk tool.")
    return

def parse_args():
    # get input file name
    global in_csv
    if len(sys.argv) < 2:
        print(f"ERROR: {sys.argv[0]} expects the csv input file as argument\n")
        help()
        exit(1)
    in_csv = sys.argv[1];
    return

def draw_trace_old(mem_trace, fig_width=80, marker_size=6, marker_ratio=1):
    fig, axe1 = plt.subplots()
    axe1.set_ylabel("Offset within Memory Block [bytes]")
    axe1.invert_yaxis()
    axe1.set_xlabel("Time of Access")
    # force x and y axis limits and to use integers
    axe1.set_xlim([-2,mem_trace.len()])
    axe1.xaxis.get_major_locator().set_params(integer=True)
    axe1.yaxis.get_major_locator().set_params(integer=True)

    # creates custom marker
    marker_width = 5
    marker_height = marker_width * marker_ratio
    access_marker = mpath.Path(
        [[-marker_width,marker_height],
        [marker_width,marker_height],
        [marker_width,-marker_height],
        [-marker_width,-marker_height],
        [-marker_width,marker_height]],
        closed=True)


    # create two pairs of arrays: each pair is the X,Y coordenates of all
    # reads and writes to memory.
    read_x,read_y = [],[]
    write_x,write_y = [],[]
    for ac in mem_trace.access_list:
        if ac.action=='R':
            for i in range(ac.size):
                read_x.append(ac.time)
                read_y.append(ac.offset+i)
        else:
            for i in range(ac.size):
                write_x.append(ac.time)
                write_y.append(ac.offset+i)
    # plot all reads and all writes
    axe1.scatter(read_x, read_y, marker=access_marker, label="Read", color='g', s=marker_size)
    axe1.scatter(write_x, write_y, marker=access_marker, label="Write", color='r', s=marker_size)

    # set the figure proportions to match the block_size/trace_length ratio
    ratio = mem_trace.block_size / mem_trace.len()
    fig_height = fig_width * ratio
    fig.set_size_inches(fig_width,fig_height)
    fig.set_dpi(300)

    # legend_without_duplicate_labels(axe1)
    axe1.legend(loc='best')
    axe1.grid(visible=True, which='both', markevery=8)
    fig.savefig('mem_trace_plot.pdf', dpi=300, bbox_inches='tight')
    return

def draw_trace(mem_trace, fig_height=20):

    # create a matrix that maps one operations to numbers:
    #   10: no-operation
    #   20: read access
    #   30: write access

    # extract data
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

    # add legend
    legend_cols = {0: 'green', 1: 'red'}
    legend_labels = {0: 'read', 1: 'write'}
    legend_patches =[mpatches.Patch(color=legend_cols[i],label=legend_labels[i])
                     for i in legend_cols]
    axe1.legend(handles=legend_patches, loc='best', borderaxespad=0)

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
    print("traceplot: exporting pdf...")
    fig.savefig('mem_trace_plot.pdf', bbox_inches='tight')
    return

def main():
    parse_args()
    mem_trace = MemTrace()
    with open(in_csv, 'r', newline='') as open_file:

        # Drop 1st and 2nd lines with the start and end address.
        # Capture the size of the block at the end of the 3rd line
        # Drop the 4th line (empty)
        next(open_file)
        next(open_file)
        mem_trace.block_size = int(next(open_file).split(' ')[-1])
        next(open_file)

        # Open rest of the file in CSV format.
        csv_reader = csv.DictReader(open_file, delimiter=',')

        # Each access is stored in a MemAccess object, which is
        # appened to the whole trace
        print(f"traceplot: reading {in_csv}...")
        i = 0
        for reg in csv_reader:
            reg["time"]=i
            mem_trace.append(MemAccess(reg))
            i += 1

        # draw the memory trace as a mesh
        print(f"traceplot: plotting...")
        draw_trace(mem_trace, fig_height=20)

    return

if __name__ == "__main__":
    main()
