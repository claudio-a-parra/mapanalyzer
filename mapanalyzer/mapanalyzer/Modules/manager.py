import sys
import matplotlib.pyplot as plt

from mapanalyzer.settings import Settings as st
from mapanalyzer.util import MetricStrings, PdataFile, PlotFile
from mapanalyzer.ui import UI

from .module_mapplotter import Map
from .module_locality import Locality
from .module_missratio import MissRatio
from .module_memaccess import MemAccess
from .module_usage import CacheUsage
#! from .module_aliasing import Aliasing
#! from .module_eviction import EvictionDuration


class Manager:
    # list of available classes
    available_module_classes = [
        Map,
        Locality,
        MissRatio,
        MemAccess,
        CacheUsage,
        #!Aliasing,
        #!EvictionDuration
    ]

    def __init__(self):
        # List of available modules
        self.map = Map()
        self.locality = Locality()
        self.missratio = MissRatio()
        self.memaccess = MemAccess()
        self.usage = CacheUsage()
        #!self.aliasing = Aliasing()
        #!self.evictdur = EvictDuration()

        self.available_module_instances = [
            self.map,
            self.locality,
            self.missratio,
            self.memaccess,
            self.usage,
            #!self.aliasing,
            #!self.evictdur
        ]

        # inform st.Metrics about the available modules
        st.Metrics.set_available(self.available_module_instances)
        return

    def describe(self):
        enabled_list = ['ENABLED']
        metrics_list = ['METRIC']
        modules_list = ['MODULE']
        descrip_list = ['DESCRIPTION']
        for metric_code,module in st.Metrics.available.items():
            if metric_code in st.Metrics.enabled or \
               metric_code == st.Metrics.bg:
                enabled_list.append('[X]')
            else:
                enabled_list.append('[ ]')
            metrics_list.append(metric_code)
            modules_list.append(module.__class__.__name__)
            descrip_list.append(module.supported_metrics[metric_code].about)
        UI.columns((enabled_list, metrics_list, modules_list, descrip_list),
                   sep='   ', header=True)
        return

    def commit(self, time):
        for mod in self.available_module_instances:
            mod.commit(time)
        return

    def finalize(self):
        for mod in self.available_module_instances:
            mod.finalize()
        return

    def __export_single_pdata(self, metric_code, meta_data, cache_data,
                              map_data, bg_data):
        # find module of this metric and obtain data
        if metric_code not in st.Metrics.available:
            UI.error(
                f'While exporting data for "{metric_code}" metric code. There '
                'is no module that supports this metric code. If such module '
                'actually exists, make sure its ".supported_metrics" '
                f'dictionary contains an entry for "{metric_code}".',
                do_exit=False)
            return
        module = st.Metrics.available[metric_code]
        fg_data = module.export_data(metric_code)

        # prevent from saving the same data in fg and bg
        maybe_bg_data = bg_data
        if st.Metrics.bg == metric_code:
            maybe_bg_data = None

        # construct ready-to-save dictionary
        pdata = {
            'meta'   : meta_data,
            'cache'  : cache_data,
            'map'    : map_data,
            'metrics': {
                'bg' : maybe_bg_data,
                'fg' : fg_data
            }
        }
        PdataFile.save(pdata, metric_code)
        return

    def export_all_pdatas(self):
        # obtain common elements
        meta_data = st.to_dict()
        cache_data = st.Cache.to_dict()
        map_data = st.Map.to_dict()

        # find the method that generates the bg data
        BG_to_dict = None
        if st.Metrics.bg is not None:
            to_dict_fname = f'{st.Metrics.bg}_to_dict'
            try:
                BG_to_dict = getattr(st.Metrics.available[st.Metrics.bg],
                                     to_dict_fname)
            except:
                bg_class_name = st.Metrics.available[st.Metrics.bg].__class__.\
                    __name__
                UI.warning(f'{bg_class_name}.{BG_to_dict}() not implemented.'
                           ' No background data will be saved.')
        bg_data = None
        if BG_to_dict is not None:
            bg_data = BG_to_dict()

        # for each enabled metric, save its pdata
        for metric_code in st.Metrics.enabled:
            self.__export_single_pdata(metric_code, meta_data, cache_data,
                                       map_data, bg_data)
        return

    def __export_single_plot(self, metric_code):
        # find module of this metric code and obtain data
        if metric_code not in st.Metrics.available:
            UI.error(
                f'While exporting plot for "{metric_code}" metric code. There '
                'is no module that supports this metric code. If such module '
                'actually exists, make sure its ".supported_metrics" '
                f'dictionary contains an entry for "{metric_code}".',
                do_exit=False)
            return

        # find the method that generates bg plot. If none, create a simple plot
        # with only one set of axes. Also use a simple plot if fg=bg.
        BG_to_plot = None
        if st.Metrics.bg is not None:
            to_plot_fname = f'{st.Metrics.bg}_to_plot'
            try:
                BG_to_plot = getattr(st.Metrics.available[st.Metrics.bg],
                                     to_plot_fname)
            except:
                bg_class_name = st.Metrics.available[st.Metrics.bg].__class__.\
                    __name__
                UI.warning(f'{bg_class_name}.{BG_to_plot}() not implemented.'
                           ' No background plot will be saved.')
        if BG_to_plot is not None and st.Metrics.bg != metric_code:
            fig,bg_axes = plt.subplots(
                facecolor='white',
                figsize=(st.Plot.width,st.Plot.height))
            fg_axes = fig.add_axes(bg_axes.get_position())
            # draw background plot
            BG_to_plot(bg_axes, bg_mode=True)
        else:
            fig,fg_axes = plt.subplots(
                facecolor='white',
                figsize=(st.Plot.width, st.Plot.height))

        # draw foreground plot
        fg_module = st.Metrics.available[metric_code]
        fg_module.export_plot(metric_code, fg_axes)
        PlotFile.save(fig, metric_code)
        return

    def export_all_plots(self):
        # for each enabled metric, save its plot
        for metric_code in st.Metrics.enabled:
            self.__export_single_plot(metric_code)
        return

    def __import_single_pdata(self, pdata_dict):
        # import fg and bg data:
        keys = ['fg', 'bg']
        for k in keys:
            metric_data = pdata_dict[k]
            if k == 'bg' and metric_data is None:
                continue
            if k == 'fg' and metric_data is None:
                UI.error(f'While improting pdata file. Foreground data is '
                         'empty.\n'
                         f'.metrics.{k} = NULL)')
            metric_code = metric_data['code']

            if metric_code not in st.Metrics.available:
                UI.error(f'While importing pdata file. Metric code '
                         f'"{metric_code}" not supported by any available '
                         'module.\n'
                         f'.metrics.{k}.code = {metric_code}.\n')
            st.Metrics.available[metric_code].import_data(
                metric_code, metric_data)

        return

    def plot_from_dict(self, pdata_dict):
        # import metrics_dicts to their fg and bg modules
        self.__import_single_pdata(pdata_dict)

        # export the plot
        fg_metric_code = pdata_dict['fg']['code']
        self.__export_single_plot(fg_metric_code)
        return

    @classmethod
    def aggregate_same_metric(cls, metric_code, pdata_dicts):
        # remove bg metric from all pdata dicts
        for pd_d in pdata_dicts:
            pd_d['bg'] = None

        # check that the module actually can aggregate the data
        if metric_code not in st.Metrics.available:
            UI.warning(
                f'Cannot aggregate metric "{metric_code}". '
                'Couldn\'t find an available module that supports '
                'aggregation on that code.\n'
                'If you think the metric code is correct, please make '
                'sure the module to which it belongs is registered in\n'
                'Modules.available_module_classes, and that the module '
                'itself registers the metric in its '
                '"supported_aggr_metrics" dictionary.\n'
                f'Ignoring {len(pdata_dicts)} input files with foreground '
                f'code "{metric_code}".')
            return

        # obtain module and pass the list of pdata dictionaries
        AggrModuleClass = st.Metrics.available[metric_code]
        AggrModuleClass.export_aggregated_plot(pdata_dicts)
        return
