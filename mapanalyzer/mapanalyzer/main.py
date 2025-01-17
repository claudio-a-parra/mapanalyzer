#!/usr/bin/python3

import sys # for command line arguments
import argparse # to get command line arguments

from mapanalyzer.map_data_reader import MapDataReader
from mapanalyzer.settings import Settings as st
from mapanalyzer.util import json_to_dict
from mapanalyzer.cache import Cache
from mapanalyzer.modules.modules import Modules

def run_simulation(map_data_reader, cache):
    """Run the simulation sending concurrent accesses to the cache
    in batches. At the end, flush the cache and send a last commit
    to the cache."""
    print(f'\nTRACING MAP')
    # check cache alignment of the allocated memory
    _,_,byte = st.AddrFmt.split(st.Map.start_addr)
    if byte != 0:
        print(f'    Allocated memory is not cache aligned. '
              f'First address is {byte} bytes into a cache line.')

    def print_progress(count, total):
        """helper function to print the simulation progress"""
        print(f'\033[2K\r    '
              f'{(100*count/total):5.1f}% {count:8d}/{total}'
              ,end='')
        sys.stdout.flush()
        return

    # send batches with concurrent accesses to the cache.
    tot_eve = st.Map.event_count
    eve_count = -1
    concurrent_acc = []
    for record in map_data_reader:
        eve_count += 1
        # collect all accesses happening at the same time mark
        if len(concurrent_acc) == 0 or concurrent_acc[-1].time == record.time:
            concurrent_acc.append(record)
            continue
        cache.accesses(concurrent_acc) # send all accesses from time t-1
        print_progress(eve_count, tot_eve)
        concurrent_acc = [record] # save first access of time t

    # send the remaining accesses to the cache
    eve_count += 1
    cache.accesses(concurrent_acc)
    print_progress(eve_count, tot_eve)
    print()

    # flush cache and commit for modules that care about eviction
    cache.flush()
    cache.modules.commit(st.Map.time_size-1)
    return


def command_line_args_parser():
    synopsis = ('MAPalyzer, a tool to study the cache friendliness of '
                'memory access patterns.')
    cache_conf = ('cache.conf:\n'
                  '  The cache file file must have this format:\n'
                  '\n'
                  f'   # Comments start with pound sign\n'
                  f'   line_size_bytes     : <value> # default: '
                  f' {st.Cache.line_size}\n'
                  f'   associativity       : <value> # default: '
                  f'{st.Cache.asso}\n'
                  f'   cache_size_bytes    : <value> # default: '
                  f'{st.Cache.cache_size}\n'
                  f'   arch_size_bits      : <value> # default: '
                  f'{st.Cache.arch}\n')

    examples = ('Examples:\n'
                '  mapanalyzer -- mapfile.map\n'
                '  mapanalyzer --mode plot -- plotdata.metric\n')

    signature = ('By Claudio A. Parra. 2024.\n'
                 'parraca@uci.edu')

    parser = argparse.ArgumentParser(
        description=synopsis+'\n\n',
        epilog=cache_conf+'\n\n'+examples+'\n\n'+signature,
        formatter_class=argparse.RawTextHelpFormatter)
    
    # Adding arguments
    parser.add_argument(
        metavar='INPUT-FILES', dest='input_files',
        type=str, default=None,
        help=('Comma-separated list of input files. Depending on the analysis '
              '"mode", they are either "map" or "metrics".\n'
              'Format: path/to/file.map{,path/to/another.map}\n'
              '        path/to/file.metrics{,path/to/another.metrics}')
    )
    
    parser.add_argument(
        '-ca', '--cache', metavar='CACHE', dest='cachefile',
        type=str, default=None,
        help='File describing the cache. See "cache.conf" section.'
    )

    parser.add_argument(
        '--mode', metavar='MODE', dest='mode',
        choices=['simulate', 'plot', 'sim-plot', 'aggregate'],
        type=str, default=None,
        help=('Defines the operation mode of the tool:\n'
              '    simulate  : Only run the cache simulation.\n'
              '                You must provide a list of MAP files.\n'
              '                Generates METRIC files.'
              '    plot      : Plot already obtained metric data. One plot\n'
              '                per input file.\n'
              '                You must provide a list of METRIC files.\n'
              '                Generates PLOT files.'
              '    sim-plot  : Simulate cache and plot (default).\n'
              '                Generates METRIC and PLOT files.'
              '    aggregate : Plot the aggregation of multiple metric data\n'
              '                files, aggregating the ones of the same kind.\n'
              '                You must provide a list of METRIC files.\n'
              )
    )

    parser.add_argument(
        '-pw', '--plot-width', metavar='WIDTH', dest='plot_width',
        type=float, default=None,
        help=("Width of the plots.\n"
              "Format: integer")
    )
    
    parser.add_argument(
        '-ph', '--plot-height', metavar='HEIGHT', dest='plot_height',
        type=float, default=None,
        help=("Height of the plots.\n"
              "Format: integer")
    )
    
    parser.add_argument(
        '-dp', '--dpi', metavar='DPI', dest='dpi',
        type=int, default=None,
        help=("Choose the DPI of the resulting plots.\n"
              "Format: integer")
    )

    parser.add_argument(
        '-mr', '--max-res', metavar='MR', dest='max_res',
        type=str, default=None,
        help=("The maximum resolution at which to show MAP.\n"
              "Format: integer | 'auto'")
    )

    parser.add_argument(
        '-pl', '--plots', metavar='PLOTCODES', dest='plotcodes',
        type=str, default=None,
        help=('Plots to obtain:\n'+
              '\n'.join(
                  f'    {code:4} : {defin}'
                  for code, defin in st.Plot.PLOTCODES.items()
              )+'\n'
              '    all  : Include all metrics\n'
              'Format: "all" | PLOTCODE{,PLOTCODE}\n'
              'Example: "MAP,CMR,CUR"')
    )

    parser.add_argument(
        '-xr', '--x-ranges', metavar='XRANGES', dest='x_ranges',
        type=str, default=None,
        help=("Set a manual range for the X-axis. Useful to compare several "
              "individually produced plots.\n"
              "Given that TLD is rotated, XRANGE restrict the Y-axis.\n"
              "Format: 'full' | PLOTCODE:MIN:MAX{,PLOTCODE:MIN:MAX}\n"
              "Example: 'TLD:10:20,CMR:0:310,CMMA:1000:2000'")
    )

    parser.add_argument(
        '-yr', '--y-ranges', metavar='YRANGES', dest='y_ranges',
        type=str, default=None,
        help=("Set a manual range for the Y-axis. Useful to compare several "
              "individually produced plots.\n"
              "Given that TLD is rotated, YRANGE restrict the X-axis.\n"
              "Format: 'full' | PLOTCODE:MIN:MAX{,PLOTCODE:MIN:MAX}\n"
              "Example: 'TLD:0.3:0.7,CMR:20:30,CMMA:0:6000'")
    )

    parser.add_argument(
        '-xo', '--x-tick-ori', metavar='ORI', dest='x_orient',
        choices=['h', 'v'], default=None,
        help=("Orientation of the X-axis tick labels.\n"
              "Format: 'h' | 'v'")
    )

    parser.add_argument(
        '-fr', '--format', metavar='FORMAT', dest='format',
        choices=['png', 'pdf'], default=None,
        help=("Choose the output format of the plots.\n"
              "Format: 'pdf' | 'png'")
    )

    args = parser.parse_args()
    return args

def main():
    # parse command line arguments
    args = command_line_args_parser()
    st.set_mode(args)
    st.Plot.from_args(args)

    # In simulation mode, a cache file is optional and at least one map file is
    # mandatory.
    if st.mode == 'simulate' or st.mode == 'sim-plot':
        st.Cache.from_file(args.cachefile)
        st.Cache.describe()
        map_paths = [x.strip() for x in args.input_files.split(',')]
        for map_pth in map_paths:
            st.Map.from_file(map_pth)
            st.Map.describe()
            mdr = MapDataReader(map_pth)
            modules = Modules()
            cache = Cache(modules=modules)
            run_simulation(mdr, cache)
            modules.finalize()
            modules.export_metrics()
            if st.mode == 'sim-plot':
                modules.export_plots()

    # In plot mode, at least one metric file is mandatory.
    elif st.mode == 'plot':
        met_paths = [x.strip() for x in args.input_files.split(',')]
        if len(met_paths) == 0:
            print('Error: in "plot" mode you must provide at least one'
                  'metric file.')
            exit(1)
        for met_pth in met_paths:
            met_dict = json_to_dict(met_pth)
            st.Cache.from_dict(met_dict['cache'], file_path=met_pth)
            st.Cache.describe()
            st.Map.from_dict(met_dict['map'], file_path=met_pth)
            st.Map.describe()
            modules = Modules()
            modules.plot_from_dict(met_dict['metric'], met_dict['mapplot'])

    # In aggregate mode, at least one metric
    elif st.mode == 'aggregate':
        raise Exception('[!!] NOT IMPLEMENTED')

    # Unknown mode.
    else:
        raise ValueError(f'Invalid mode "{args.mode}".')

    print('Done')
    exit(0)


def main_wrapper():
    try:
        main()
    except KeyboardInterrupt:
        exit(0)
