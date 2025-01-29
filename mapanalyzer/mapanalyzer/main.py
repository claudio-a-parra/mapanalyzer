#!/usr/bin/python3

from sys import stdout # to flush on mid-line

from mapanalyzer.settings import Settings as st
from mapanalyzer.util import command_line_args_parser, MapDataReader, PdataFile
from mapanalyzer.ui import UI
from mapanalyzer.cache import Cache
from mapanalyzer.modules.modules import Modules

def simulate_mode(args):
    st.Cache.from_file(args.cachefile)
    st.Cache.describe()
    map_paths = args.input_files
    st.Map.set_path_prefix(map_paths)
    if len(map_paths) == 0:
        UI.error('In "simulate" or "sim-plot" mode you must at least '
                 'provide one MAP file.')
    for map_pth in map_paths:
        st.Map.from_file(map_pth)
        st.Map.describe()
        modules = Modules()
        modules.describe()
        cache = Cache(modules=modules)
        cache.run_simulation(MapDataReader(map_pth))
        modules.export_all_pdatas()
        if st.mode == 'sim-plot':
            modules.export_all_plots()
        UI.nl()

    return

def plot_mode(args):
    pdata_paths = args.input_files
    st.Map.set_path_prefix(pdata_paths)
    if len(pdata_paths) == 0:
        UI.error('In "plot" mode you must at least provide one PDATA file.')

    for pd_path in pdata_paths:
        # get data from pdata file
        file_dict = PdataFile.load(pd_path)
        meta_dict = file_dict['meta']
        cache_dict = file_dict['cache']
        map_dict = file_dict['map']
        pdata_dict = file_dict['metrics']

        # initialize cache and map configs
        st.Cache.from_dict(cache_dict, pdata_file_path=pd_path)
        st.Cache.describe()
        st.Map.from_dict(map_dict, pdata_file_path=pd_path)
        st.Map.describe()

        # set which metrics are enabled based on the fg and bg metric codes
        # on the pdata file
        st.Metrics.from_dict(pdata_dict)

        # initialize modules
        modules = Modules()
        modules.describe()

        # plot pdata
        modules.plot_from_dict(pdata_dict, pdata_path=pd_path)
        UI.nl()

    return

def aggregate_mode(args):
    pdata_paths = args.input_files
    if len(pdata_paths) == 0:
        UI.error('In "aggregate" mode you must at least provide one PDATA '
                 'file.')

    # Classify metrics_dict by the foreground metric code
    classified_pdata_dicts = {}
    for pd_path in pdata_paths:
        file_dict = PdataFile.load(pd_path)
        pdata_dict = file_dict['metrics']
        fg_code = pdata_dict['fg']['code']
        if fg_code not in classified_pdata_dicts:
            classified_pdata_dicts[fg_code] = []
        classified_pdata_dicts[fg_code].append(pdata_dict)

    # Aggregate all same-code metrics
    Modules.aggregate_by_metric(classified_pdata_dicts)
    return

def main():
    # parse command line arguments
    args = command_line_args_parser()
    st.set_mode(args)
    st.Plot.from_args(args)
    st.Metrics.from_args(args)

    if st.mode == 'simulate' or st.mode == 'sim-plot':
        simulate_mode(args)
    elif st.mode == 'plot':
        plot_mode(args)
    elif st.mode == 'aggregate':
        aggregate_mode(args)
    else:
        UI.error(f'Invalid mode "{args.mode}"')

    UI.info('Done!', pre='', out='out')
    exit(0)

def main_wrapper():
    try:
        main()
    except KeyboardInterrupt:
        UI.indent_set(ind=0)
        UI.info('Process terminated by user.', symb='!', pre='')
        exit(0)
