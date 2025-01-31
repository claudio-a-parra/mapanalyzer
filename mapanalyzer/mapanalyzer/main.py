#!/usr/bin/python3
from mapanalyzer.settings import Settings as st
from mapanalyzer.cache import Cache
from mapanalyzer.ui import UI
from mapanalyzer.util import command_line_args_parser, MapDataReader, PdataFile
from . import Modules

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

        # initialize modules
        module_mngr = Modules.Manager()
        module_mngr.describe()

        # run simulation
        cache = Cache(modules=module_mngr)
        cache.run_simulation(MapDataReader(map_pth))

        # export pdatas and plots
        module_mngr.export_all_pdatas()
        if st.mode == 'sim-plot':
            module_mngr.export_all_plots()
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
        if file_dict['metrics']['fg']['code'] not in st.Metrics.enabled:
            continue
        meta_dict = file_dict['meta']
        cache_dict = file_dict['cache']
        map_dict = file_dict['map']
        pdata_dict = file_dict['metrics']

        # initialize cache and map configs
        st.Cache.from_dict(cache_dict, pdata_file_path=pd_path)
        st.Cache.describe()
        st.Map.from_dict(map_dict, pdata_file_path=pd_path)
        st.Map.describe()

        # initialize modules
        module_mngr = Modules.Manager()
        module_mngr.describe()

        # convert pdatas into plots
        module_mngr.plot_from_dict(pdata_dict, pdata_path=pd_path)
        UI.nl()

    return

def aggregate_mode(args):
    pdata_paths = args.input_files
    st.Map.set_path_prefix(pdata_paths)
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
    Modules.Manager.aggregate_by_metric(classified_pdata_dicts)
    return

def mode_dispatcher():
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

def main():
    try:
        mode_dispatcher()
    except KeyboardInterrupt:
        UI.indent_set(ind=0)
        UI.info('Process terminated by user.', symb='!', pre='')
        exit(0)
