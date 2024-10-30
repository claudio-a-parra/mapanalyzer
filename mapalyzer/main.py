#!/usr/bin/python3

import sys # for command line arguments
import os # for file extension removal
import argparse # to get command line arguments

from map_file_reader import MapFileReader
from settings import Settings as st, CacheSpecs, PlotSpecs
from util import AddrFmt
from cache import Cache
from tools import Tools

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
                  '    # Comments start with pound sign\n'
                  f'   line_size_bytes     : <value> # default: {cs.line_size}\n'
                  f'   associativity       : <value> # default: {cs.asso}\n'
                  f'   cache_size_bytes    : <value> # default: {cs.cache_size}\n'
                  f'   arch_size_bits      : <value> # default: {cs.arch}\n'
                  f'   fetch_time_cost     : <value> # default: {cs.fetch}\n'
                  f'   writeback_time_cost : <value> # default: {cs.write}\n')
    signature = ('By Claudio A. Parra. 2024.\n'
                 'parraca@uci.edu')

    parser = argparse.ArgumentParser(
        description=synopsis+'\n\n',
        epilog=cache_conf+'\n\n'+signature,
        formatter_class=argparse.RawTextHelpFormatter)
    
    # Adding arguments
    parser.add_argument(
        'input_files', metavar='input_file.map', nargs='+', type=str,
        help='Path of the input Memory Access Pattern file.'
    )
    
    parser.add_argument(
        '-c', '--cache', metavar='cache.conf', dest='cache', type=str,
        default=None,
        help='File describing the cache. See "cache.conf" section.'
    )

    parser.add_argument(
        '-px', '--plot-x', dest='px', type=float, default=8,
        help="Width of the plots."
    )
    
    parser.add_argument(
        '-py', '--plot-y', dest='py', type=float, default=4,
        help="Height of the plots."
    )
    
    parser.add_argument(
        '-dpi', '--dpi', dest='dpi', type=int, default=200,
        help='Choose the DPI of the resulting plots.'
    )

    parser.add_argument(
        '-p', '--plots', dest='plots', type=str, default='MLICUAS',
        help="What plots to include. Format: {<plotcode>}\n" +\
        "Plotcodes: M:map, L:locality, I:miss-ratio, C:main-mem-access-count, U:cache-usage, " +\
        "A:aliasing, S:SIU-evictions.\nExample: 'MU'"
    )

    parser.add_argument(
        '-yr', '--y-ranges', dest='y_ranges', type=str, default='', nargs='?',
        help="Set a manual range for the Y-axis. Useful to compare several " +\
        "individually produced plots. Format: {<plotcode>:<min>:<max>,}\n" +\
        "Example: 'C:0:6000,U:20:30'\n"
    )

    parser.add_argument(
        '-f', '--format', dest='format', choices=['png', 'pdf'], default='png',
        help='Choose the output format of the plots.'
    )
    
    def check_res(val):
        min_res = 4
        max_res = 2048
        def_res = 512
        val = int(val)
        if min_res < val < max_res:
            return val
        else:
            print(f'[!] Warning: resolution value must be between {min_res} and '
                  f'{max_res}. Using default value {def_res}.')
            return def_res
    parser.add_argument(
        '-r', '--res', dest='resolution', type=check_res, default=512,
        help=('Maximum resolution of the Memory Access Pattern grid (value '
              'between 4 and 2048).')
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
        st.init_map_derived()
        map_reader = MapFileReader()
        st.map.describe(ind='    ')

        file_prefix = os.path.basename(os.path.splitext(map_filename)[0])
        plot_metadata = PlotSpecs(width=args.px, height=args.py,
                                  res=args.resolution, dpi=args.dpi,
                                  format=args.format, prefix=file_prefix,
                                  include=args.plots, y_ranges=args.y_ranges)
        st.init_plot(plot_metadata=plot_metadata)

        print(f'\nCREATING TOOLS AND MEMORY SYSTEM')
        tools = Tools()
        tools.describe()
        cache = Cache(tools=tools)

        print(f'\nRETRACING MAP ({st.map.event_count} mem. accesses)')
        run_simulation(map_reader, cache)

        print(f'\nPLOTTING ({st.plot.format})')
        tools.plot()

    print('Done')


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        exit(0)
