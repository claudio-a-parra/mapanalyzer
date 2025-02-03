#!/usr/bin/python3
from .settings import Settings as st
from .cache import Cache
from .ui import UI
from .util import command_line_args_parser, MapDataReader, PdataFile
from . import Modules

def simulate_mode(args):
    # init cache settings
    cache_fname = args.cachefile if args.cachefile is not None else 'Defaults'
    UI.indent_in(title=f'CACHE PARAMETERS ({cache_fname})')
    st.Cache.from_file(args.cachefile)
    st.Cache.describe()
    UI.indent_out()

    map_paths = args.input_files
    st.Map.set_path_prefix(map_paths)
    if len(map_paths) == 0:
        UI.error('In "simulate" or "sim-plot" mode you must at least '
                 'provide one MAP file.')

    # Run one simulation/export per map file given
    for map_pth in map_paths:
        UI.indent_in(f'SIMULATING MEMORY ACCESS PATTERN ({map_pth})')

        # init map settings
        UI.indent_in(title=f'MAP SETTINGS')
        st.Map.from_file(map_pth)
        st.Map.describe()
        UI.indent_out()

        # init modules
        UI.indent_in(title='MAPANALYZER METRICS')
        module_mngr = Modules.Manager()
        module_mngr.describe()
        UI.indent_out()

        # run simulation
        UI.indent_in('SIMULATING CACHE')
        cache = Cache(modules=module_mngr)
        cache.run_simulation(MapDataReader(map_pth))
        UI.indent_out()

        # export pdatas
        UI.indent_in(title=f'EXPORTING PDATAS (bg: {st.Metrics.bg})')
        module_mngr.export_all_pdatas()
        UI.indent_out()

        # export plots
        if st.mode == 'sim-plot':
            UI.indent_in(title=f'EXPORTING PLOTS (bg: {st.Metrics.bg})')
            module_mngr.export_all_plots()
            UI.indent_out()

        UI.indent_out()
    return

def plot_mode(args):
    pdata_paths = args.input_files
    st.Map.set_path_prefix(pdata_paths)
    if len(pdata_paths) == 0:
        UI.error('In "plot" mode you must at least provide one PDATA file.')

    for pd_path in pdata_paths:
        UI.indent_in(title=f'PLOTTING FROM PDATA ({pd_path})')
        # obtain data from the pdata file
        file_dict = PdataFile.load(pd_path)
        meta_dict = file_dict['meta']
        cache_dict = file_dict['cache']
        map_dict = file_dict['map']
        pdata_dict = file_dict['metrics']
        st.Metrics.from_dict(pdata_dict)

        # if this metric was not requested by the user, skip it.
        metric_code = file_dict['metrics']['fg']['code']
        if metric_code not in st.Metrics.enabled:
            UI.info(f'Skipping not requested metric "{metric_code}"', pre='')
            UI.indent_out()
            continue


        # init cache settings
        UI.indent_in(title=f'CACHE PARAMETERS')
        st.Cache.from_dict(cache_dict)
        st.Cache.describe()
        UI.indent_out()

        # init map settings
        UI.indent_in(title=f'MEMORY ACCESS PATTERN')
        st.Map.from_dict(map_dict, pdata_file_path=pd_path)
        st.Map.describe()
        UI.indent_out()

        # init modules
        UI.indent_in(title='MAPANALYZER METRICS')
        module_mngr = Modules.Manager()
        module_mngr.describe()
        UI.indent_out()

        # convert pdatas into plots
        UI.indent_in(title=f'PLOTTING (bg: {st.Metrics.bg})')
        module_mngr.plot_from_dict(pdata_dict)
        UI.indent_out()

        UI.indent_out()
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

    # inform st.Metrics about the available modules
    st.Metrics.set_available(Modules.Manager.available_module_classes,
                             supp_metrics_name='supported_aggr_metrics')

    # Aggregate all same-code metrics
    for metric_code,pdata_dicts in classified_pdata_dicts.items():
        if metric_code not in st.Metrics.enabled:
            continue
        UI.indent_in(title=f'AGGREGATING {len(pdata_dicts)} x {metric_code}')
        Modules.Manager.aggregate_same_metric(metric_code, pdata_dicts)
        UI.indent_out()
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
    UI.nl()
    exit(0)

def main():
    try:
        mode_dispatcher()
    except KeyboardInterrupt:
        UI.indent_set(ind=0)
        UI.info('Process terminated by user.', symb='!', pre='')
        exit(0)
