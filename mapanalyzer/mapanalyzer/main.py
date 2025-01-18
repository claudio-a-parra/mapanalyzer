#!/usr/bin/python3

from sys import stdout # to flush on mid-line

from mapanalyzer.settings import Settings as st
from mapanalyzer.util import json_to_dict, command_line_args_parser, \
    MapDataReader
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
        stdout.flush()
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
        map_paths = args.input_files
        for map_pth in map_paths:
            st.Map.from_file(map_pth)
            st.Map.describe()
            mdr = MapDataReader(map_pth)
            modules = Modules()
            modules.describe()
            cache = Cache(modules=modules)
            run_simulation(mdr, cache)
            modules.finalize()
            modules.export_metrics()
            if st.mode == 'sim-plot':
                modules.export_plots()

    # In plot mode, at least one metric file is mandatory.
    elif st.mode == 'plot':
        metric_paths = args.input_files
        if len(metric_paths) == 0:
            print('Error: in "plot" mode you must provide at least one'
                  'metric file.')
            exit(1)
        for m_path in metric_paths:
            metric_dict = json_to_dict(m_path)
            st.Cache.from_dict(metric_dict['cache'], file_path=m_path)
            st.Cache.describe()
            st.Map.from_dict(metric_dict['map'], file_path=m_path)
            st.Map.describe()
            modules = Modules()
            modules.describe()
            modules.plot_from_dict(
                metric_dict['metric'], metric_dict['mapplot']
            )

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
