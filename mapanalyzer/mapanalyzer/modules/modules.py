import sys
import matplotlib.pyplot as plt

from mapanalyzer.settings import Settings as st
from mapanalyzer.util import MetricStrings, PdataFile, PlotFile
from mapanalyzer.modules.mapplotter import Map
#! from mapanalyzer.modules.locality import Locality
#! from mapanalyzer.modules.hitmiss import HitMiss
#! from mapanalyzer.modules.cost import Cost
from mapanalyzer.modules.usage import CacheUsage
#! from mapanalyzer.modules.alias import Aliasing
#! from mapanalyzer.modules.eviction import EvictionDuration
from mapanalyzer.ui import UI

class Modules:
    # list of available classes
    available_module_classes = [
        Map,
        #Locality,
        #HitMiss,
        #Cost,
        CacheUsage,
        #Aliasing,
        #EvictionDuration
    ]

    def __init__(self):
        # List of available modules
        self.map = Map()
        self.usage = CacheUsage()
        self.available_module_instances = [
            self.map,
            self.usage
        ]

        # inform st.Metrics about the available modules
        st.Metrics.set_available(self.available_module_instances)

        # If a background metric (let's say "BG") was defined, search its
        # module for the methods BG_to_dict() and BG_to_plot().
        self.BG_to_dict = None
        self.BG_to_plot = None

        if st.Metrics.bg is not None:
            to_dict_fname = f'{st.Metrics.bg}_to_dict'
            to_plot_fname = f'{st.Metrics.bg}_to_plot'
            try:
                self.BG_to_dict = getattr(st.Metrics.available[st.Metrics.bg],
                                          to_dict_fname)
            except:
                bg_class_name = st.Metrics.available[st.Metrics.bg].__class__.\
                    __name__
                UI.warning(f'Module {bg_class_name} seems to support the '
                           f'metric {st.Metrics.bg}:\n'
                           f'    (\'{st.Metrics.bg}\' in '
                           f'{bg_class_name}.metrics == True)\n'
                           f'But it does not implement the {to_dict_fname} '
                           'method. No background PDATA will be saved.')
            try:
                self.BG_to_plot = getattr(st.Metrics.available[st.Metrics.bg],
                                          to_plot_fname)
            except:
                bg_class_name = st.Metrics.available[st.Metrics.bg].__class__.\
                    __name__
                UI.warning(f'Module {bg_class_name} seems to support the '
                           f'"{st.Metrics.bg}" metric:\n'
                           f'    (\'{st.Metrics.bg}\' in '
                           f'{bg_class_name}.metrics == True)\n'
                           f'But it does not implement the {to_plot_fname} '
                           'method. No background PLOTS will be drawn.')
        return

    def describe(self):
        UI.indent_in(title='MAPANALYZER METRICS')
        metrics_list = ['METRIC']
        modules_list = ['MODULE']
        descrip_list = ['DESCRIPTION']
        for metric_code,module in st.Metrics.available.items():
            metrics_list.append(metric_code)
            modules_list.append(module.__class__.__name__)
            descrip_list.append(module.supported_metrics[metric_code].about)
        UI.columns((metrics_list, modules_list, descrip_list), sep='   ',
                   header=True)
        UI.indent_out()
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
                f'Cannot export data from metric "{metric_code}". Couldn\'t '
                'find an available module that supports such code.\n'
                f'If you think the metric code is correct, please make sure '
                'the module to which it belongs is registered in '
                'Modules.available_module_classes and '
                'Modules.available_module_instances', do_exit=False)
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
        UI.indent_in(title='EXPORTING PDATAS')

        # obtain common elements
        meta_data = st.to_dict()
        cache_data = st.Cache.to_dict()
        map_data = st.Map.to_dict()

        # If a background module was found, get its data
        bg_data = None
        if self.BG_to_dict is not None:
            bg_data = self.BG_to_dict()

        # for each enabled metric, save its pdata
        for metric_code in st.Metrics.enabled:
            self.__export_single_pdata(metric_code, meta_data, cache_data,
                                       map_data, bg_data)

        UI.indent_out()
        return

    def __export_single_plot(self, metric_code):
        # find module of this metric code and obtain data
        if metric_code not in st.Metrics.available:
            UI.error(
                f'Cannot export plot from metric "{metric_code}". Couldn\'t '
                'find an available module that supports that code.\n'
                'If you think the metric code is correct, please make '
                'sure the module to which it belongs is registered in '
                'Modules.available_module_instances, and that the module '
                'itself registers the metric in its '
                '"supported_aggr_metrics" dictionary.', do_exit=False)
            return
        module = st.Metrics.available[metric_code]

        # If there is a background plotter, then create two sets of axes
        if self.BG_to_plot is not None:
            fig,bg_axes = plt.subplots(
                facecolor='white',
                figsize=(st.Plot.width,st.Plot.height))
            fg_axes = fig.add_axes(bg_axes.get_position())
            # draw background plot
            self.BG_to_plot(bg_axes, bg_mode=True)
        else:
            fig,fg_axes = plt.subplots(
                facecolor='white',
                figsize=(st.Plot.width, st.Plot.height))

        # draw foreground plot
        module.export_plot(metric_code, fg_axes)
        PlotFile.save(fig, metric_code)
        return

    def export_all_plots(self):
        UI.indent_in(title='EXPORTING PLOTS')

        # for each enabled metric, save its plot
        for metric_code in st.Metrics.enabled:
            self.__export_single_plot(metric_code)

        UI.indent_out()
        return

    def __import_single_pdata(self, pdata_dict, pdata_path):
        # import fg and bg data:
        keys = ['fg', 'bg']
        for k in keys:
            metric_data = pdata_dict[k]
            if k == 'bg' and metric_data is None:
                continue
            if k == 'fg' and metric_data is None:
                UI.error(f'Importing {pdata_path}. Foreground data is empty. '
                         '(json_file.metrics.fg == NULL)')
            metric_code = metric_data['code']
            if metric_code not in st.Metrics.available:
                UI.error(f'Metric code "{metric_code}" not supported by '
                         'available modules.\n'
                         f'{pdata_path}.metrics.{k}.code == {metric_code}.\n')
            st.Metrics.available[metric_code].import_data(
                metric_code, metric_data)
        return

    def plot_from_dict(self, pdata_dict, pdata_path):
        UI.indent_in(title='PLOTTING METRICS')

        # import metrics_dict to module
        self.__import_single_pdata(pdata_dict, pdata_path)

        # export the plot
        fg_metric_code = pdata_dict['fg']['code']
        self.__export_single_plot(fg_metric_code)

        UI.indent_out()
        return

    @classmethod
    def aggregate_by_metric(cls, classified_pdata_dicts):
        UI.indent_in(title='AGGREGATING SAME-CODE METRICS')

        # inform st.Metrics about the available modules
        st.Metrics.set_available(cls.available_module_classes,
                                 supp_metrics_name='supported_aggr_metrics')

        # One aggregation per foreground metric code
        for metric_code, pdata_dicts in classified_pdata_dicts.items():
            # remove bg metric from all pdata dicts, and inform st.Metrics of
            # the user enabled metrics (all dicts have the same, so we just
            # pick) the first one
            for pd_d in pdata_dicts:
                pd_d['bg'] = None
            st.Metrics.from_dict(pdata_dicts[0])

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
                continue

            # obtain module and pass the list of pdata dictionaries
            AggrModuleClass = st.Metrics.available[metric_code]
            AggrModuleClass.export_aggregated_plot(pdata_dicts)
        UI.indent_out()
        return
