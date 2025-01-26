#!/usr/bin/python3

from sys import stdout # to flush on mid-line

from mapanalyzer.settings import Settings as st
from mapanalyzer.util import command_line_args_parser, MapDataReader, PdataFile
from mapanalyzer.ui import UI
from mapanalyzer.cache import Cache
from mapanalyzer.modules.modules import Modules

def main():
    # parse command line arguments
    args = command_line_args_parser()
    st.set_mode(args)
    st.Plot.from_args(args)
    st.Metrics.from_args(args)

    # In simulation mode, a cache file is optional and at least one map file is
    # mandatory.
    if st.mode == 'simulate' or st.mode == 'sim-plot':
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

    # In plot mode, at least one metric file is mandatory.
    elif st.mode == 'plot':
        pdata_paths = args.input_files
        st.Map.set_path_prefix(pdata_paths)
        if len(pdata_paths) == 0:
            UI.error('In "plot" mode you must at least provide one PDATA '
                     'file.')
        for pdp in pdata_paths:
            # get data from pdata file
            pdp_dict = PdataFile.load(pdp)
            meta_dict = pdp_dict['meta']
            cache_dict = pdp_dict['cache']
            map_dict = pdp_dict['map']
            metrics_dict = pdp_dict['metrics']

            # initialize cache and map configs
            st.Cache.from_dict(cache_dict, file_path=pdp)
            st.Cache.describe()
            st.Map.from_dict(map_dict, file_path=pdp)
            st.Map.describe()
            modules = Modules()
            modules.describe()

            # plot metrics
            modules.plot_from_dict(metrics_dict)
            UI.nl()

    # In aggregate mode, at least one metric
    elif st.mode == 'aggregate':
        metrics_paths = args.input_files
        if len(metrics_paths) == 0:
            UI.error('In "aggregate" mode you must at least provide one metric '
                     'file.')
        # classify metrics by their code. Each code maps to a list of tuples:
        # code -> [(metric_file_path, metric_dict), (...)]
        classified_metrics = {}
        for met_path in metrics_paths:
            full_met_dict = PdataFile.load(met_path)
            met_dict = full_met_dict['metric']
            met_code = met_dict['code']
            if met_code not in classified_metrics:
                classified_metrics[met_code] = []
            classified_metrics[met_code].append(met_dict)
        # Aggregate each metric type
        Modules.aggregate_metrics(classified_metrics)

    # Unknown mode.
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
