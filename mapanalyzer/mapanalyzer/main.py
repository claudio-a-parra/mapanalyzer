#!/usr/bin/python3

import sys # for command line arguments
import os # for file extension removal
import argparse # to get command line arguments

from mapanalyzer.map_file_reader import MapFileReader
from mapanalyzer.settings import Settings as st, CacheSpecs, PlotSpecs
from mapanalyzer.util import AddrFmt
from mapanalyzer.cache import Cache
from mapanalyzer.tools.tools import Tools

def run_simulation(map_reader, cache, progress=True):
    _,_,byte = AddrFmt.split(st.map.start_addr)
    if byte != 0:
        print(f'    Allocated memory is not cache aligned. '
              f'First address is {byte} bytes into a cache line.')

    def print_progress(count, total):
        print('\033[2K\r    '
              f'{(100*count/total):5.1f}% '
              f'{count:8d}/{total}'
              ,end='')
        sys.stdout.flush()
        return

    tot_eve = st.map.event_count
    eve_count = -1
    concurrent_acc = []
    for access in map_reader:
        eve_count += 1
        # collect all accesses happening at the same time mark
        if len(concurrent_acc) == 0 or \
           concurrent_acc[-1].time == access.time:
            concurrent_acc.append(access)
            continue

        # process all memory accesses at time t-1
        cache.multi_access(concurrent_acc)

        # print progress
        if progress:
            print_progress(eve_count, tot_eve)

        # add first access of time t
        concurrent_acc = [access]

    # process all memory accesses at time t
    eve_count += 1
    cache.multi_access(concurrent_acc)
    if progress:
        print_progress(eve_count, tot_eve)
        print()

    cache.flush()
    cache.tools.commit(st.map.time_size-1)
    return

def command_line_args_parser():
    cs = CacheSpecs()
    synopsis = ('MAPalyzer, a tool to study the cache friendliness of '
                'memory access patterns.')
    cache_conf = ('cache.conf:\n'
                  '  The cache file file must have this format:\n'
                  '\n'
                  f'   # Comments start with pound sign\n'
                  f'   line_size_bytes     : <value> # default: {cs.line_size}\n'
                  f'   associativity       : <value> # default: {cs.asso}\n'
                  f'   cache_size_bytes    : <value> # default: {cs.cache_size}\n'
                  f'   arch_size_bits      : <value> # default: {cs.arch}\n')
    signature = ('By Claudio A. Parra. 2024.\n'
                 'parraca@uci.edu')

    parser = argparse.ArgumentParser(
        description=synopsis+'\n\n',
        epilog=cache_conf+'\n\n'+signature,
        formatter_class=argparse.RawTextHelpFormatter)
    
    # Adding arguments
    parser.add_argument(
        'input_files', metavar='MAPFILE', nargs='+', type=str,
        help='Memory Access Pattern file.'
    )
    
    parser.add_argument(
        '-ca', '--cache', metavar='CACHE', dest='cache', type=str,
        default=None,
        help='File describing the cache. See "cache.conf" section.'
    )

    parser.add_argument(
        '-pw', '--plot-width', metavar='WIDTH', dest='plot_width', type=float, default=8,
        help="Width of the plots."
    )
    
    parser.add_argument(
        '-ph', '--plot-height', metavar='HEIGHT', dest='plot_height', type=float, default=4,
        help="Height of the plots."
    )
    
    parser.add_argument(
        '-dp', '--dpi', metavar='DPI', dest='dpi', type=int, default=200,
        help='Choose the DPI of the resulting plots.'
    )

    parser.add_argument(
        '-mr', '--max-res', metavar='MR', dest='max_res', type=str, default='auto',
        help='The maximum resolution at which to show MAP.'
    )

    parser.add_argument(
        '-pl', '--plots', metavar='PLOTCODES', dest='plotcodes', type=str, default='all',
        help=("Plots to obtain:\n"+
              "\n".join(f"    {code:4} : {defin}" for code, defin in st.PLOTCODES.items())+"\n"+
              "Format: 'all' | PLOTCODE{,PLOTCODE}\n"
              "Example: 'MAP,CMR,CUR'")
    )

    parser.add_argument(
        '-yr', '--y-ranges', metavar='YRANGES', dest='y_ranges', type=str, default='',
        help=("Set a manual range for the Y-axis. Useful to compare several "
              "individually produced plots.\n"
              "Given that TLD is rotated, YRANGE actually restrict the X axis."
              "Format: 'full' | PLOTCODE:MIN:MAX{,PLOTCODE:MIN:MAX}\n"
              "Example: 'TLD:0.3:0.7,CMR:20:30,CMMA:0:6000'")
    )

    parser.add_argument(
        '-xo', '--x-tick-ori', metavar='ORI', dest='x_orient', choices=['h', 'v'], default='v',
        help="Orientation of the X-axis tick labels."
    )

    parser.add_argument(
        '-hb', '--hist-bins', metavar='HB', dest='hist_bins', type=str, default='auto',
        help='The number of bins to use in SIU histogram.'
    )

    parser.add_argument(
        '-hm', '--hist-max', metavar='HM', dest='hist_max', type=str, default='auto',
        help='Maximum X-value to show in the SIU histogram'
    )

    parser.add_argument(
        '-fr', '--format', metavar='FORMAT', dest='format', choices=['png', 'pdf'], default='png',
        help=("Choose the output format of the plots.\n"
              "Format: 'pdf' | 'png'")
    )

    args = parser.parse_args()
    return args

def main():
    args = command_line_args_parser()
    print(f'CACHE PARAMETERS')
    st.init_cache(args.cache)
    AddrFmt.init(st.cache)
    st.cache.describe(ind='    ')

    for map_filename in args.input_files:
        print(f'\nMEMORY ACCESS PATTERN')
        st.init_map(map_filename)
        map_reader = MapFileReader()
        st.map.describe(ind='    ')

        print(f'\nCREATING TOOLS AND MEMORY SYSTEM')
        st.init_plot(
            width = args.plot_width,
            height = args.plot_height,
            dpi = args.dpi,
            max_res = args.max_res,
            format = args.format,
            prefix = os.path.basename(os.path.splitext(map_filename)[0]),
            include_plots = args.plotcodes,
            x_orient = args.x_orient,
            y_ranges = args.y_ranges,
            data_X_size = st.map.time_size,
            data_Y_size = st.map.num_padded_bytes,
            hist_bins = args.hist_bins,
            hist_max = args.hist_max
        )
        tools = Tools()
        tools.describe()
        cache = Cache(tools=tools)

        print(f'\nRETRACING MAP')
        run_simulation(map_reader, cache)

        print(f'\nPLOTTING')
        tools.plot()

    print('Done')


def main_wrapper():
    try:
        main()
    except KeyboardInterrupt:
        exit(0)
