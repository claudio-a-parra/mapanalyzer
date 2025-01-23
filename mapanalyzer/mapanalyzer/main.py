#!/usr/bin/python3

from sys import stdout # to flush on mid-line

from mapanalyzer.settings import Settings as st
from mapanalyzer.util import command_line_args_parser, load_metric, \
    MapDataReader
from mapanalyzer.ui import UI
from mapanalyzer.cache import Cache
from mapanalyzer.modules.modules import Modules

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
            modules.finalize()
            modules.export_metrics()
            if st.mode == 'sim-plot':
                modules.export_plots()

    # In plot mode, at least one metric file is mandatory.
    elif st.mode == 'plot':
        metrics_paths = args.input_files
        st.Map.set_path_prefix(metrics_paths)
        if len(metrics_paths) == 0:
            UI.error('In "plot" mode you must at least provide one metric '
                     'file.')
        for m_path in metrics_paths:
            metric_dict = load_metric(m_path)
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
        metrics_paths = args.input_files
        if len(metrics_paths) == 0:
            UI.error('In "aggregate" mode you must at least provide one metric '
                     'file.')

        # classify metrics by their code. Each code maps to a list of tuples:
        # code -> [(metric_file_path, metric_dict), (...)]
        classified_metrics = {}
        for met_path in metrics_paths:
            full_met_dict = load_metric(met_path)
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
        exit(0)
