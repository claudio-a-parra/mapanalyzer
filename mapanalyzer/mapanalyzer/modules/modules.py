import sys
import matplotlib.pyplot as plt

from mapanalyzer.settings import Settings as st
from mapanalyzer.util import MetricStrings, PdataFile
from mapanalyzer.modules.mapplotter import Map
#! from mapanalyzer.modules.locality import Locality
#! from mapanalyzer.modules.hitmiss import HitMiss
#! from mapanalyzer.modules.cost import Cost
from mapanalyzer.modules.usage import CacheUsage
#! from mapanalyzer.modules.alias import Aliasing
#! from mapanalyzer.modules.eviction import EvictionDuration
from mapanalyzer.ui import UI

class Modules:
    # Match each metric code to its responsible Module
    Aggr_Modules = {
        # 'MAP': Map, # Map does NOT aggregate data (so far)
        'CUR': CacheUsage,
    }

    def __init__(self, bg_metric='MAP'):
        # Create set of modules with shared X axis (for plots)
        self.map = Map()
        #! self.locality = Locality(shared_X=self.map.X)
        #! self.hitmiss = HitMiss(shared_X=self.map.X)
        #! self.cost = Cost(shared_X=self.map.X)
        self.usage = CacheUsage()
        #! self.aliasing = Aliasing(shared_X=self.map.X)
        #! self.evicd = EvictionDuration(shared_X=self.map.X)

        # list of all modules
        #! self.modules_list = \
        #!     [self.map, self.locality, self.hitmiss, self.cost, self.usage,
        #!      self.aliasing, self.evicd]

        # list of all modules
        UI.warning('Including only MAP and CUR')
        self.modules_list = [self.map, self.usage]

        # Find the first module that supports this metric, and set it
        # as the background module and metric respectively
        self.bg_metric = bg_metric
        self.bg_module = None
        if bg_metric != None:
            # find a module that has this metric
            for mod in self.modules_list:
                if mod.has_metric(bg_metric):
                    self.bg_module = mod
                    self.bg_metric = bg_metric
                    break

        # Find the function within the background module that will export the
        # PDATA. If the metric is 'MOD', then the function should be
        # 'MOD_to_dict'
        self.BG_to_dict = None # function to generate the bg_pdata
        if None not in (self.bg_module, self.bg_metric):
            fn_name = f'{self.bg_metric}_to_dict'
            try:
                self.BG_to_dict = getattr(self.bg_module, fn_name)
            except:
                try:
                    module_name = self.bg_module.name
                except:
                    UI.warning(f'The given background module doesn\'t have a '
                               'name!')
                    module_name = '?????'
                UI.warning(f'The given background module "{module_name}" '
                           f'has not defined the function "{fn_name}". '
                           'Not saving background metric data.')

        return

    def describe(self):
        UI.indent_in(title='MAPANALYZER MODULES')
        mods_names = []
        mods_metrics = []
        mods_about = []
        for mod in self.modules_list:
            mods_names.append(mod.name)
            mods_metrics.append(', '.join(mod.metrics.keys()))
            mods_about.append(mod.about)
        UI.columns((mods_names, mods_metrics, mods_about), sep=' : ')
        UI.indent_out()
        return

    def commit(self, time):
        for mod in self.modules_list:
            mod.commit(time)
        return

    def finalize(self):
        for mod in self.modules_list:
            mod.finalize()
        return

    def export_all_pdatas(self):
        UI.indent_in(title='EXPORTING PDATAS')
        # obtain common elements
        meta_data = st.to_dict()
        cache_data = st.Cache.to_dict()
        map_data = st.Map.to_dict()
        bg_data = self.BG_to_dict()
        # for each enabled metric, save its pdata
        for met_code in st.Metrics.enabled:
            met_code_exported = False
            for mod in self.modules_list:
                if mod.has_metric(met_code):
                    fg_data = mod.export_metric(met_code)
                    # avoid saving the same fg and bg
                    saving_bg_data = bg_data
                    if (mod,met_code) == (self.bg_module,self.bg_metric):
                        saving_bg_data = None

                    # construct ready-to-save dictionary
                    pdata = {
                        'meta'   : meta_data,
                        'cache'  : cache_data,
                        'map'    : map_data,
                        'metrics': {
                            'bg' : saving_bg_data,
                            'fg' : fg_data
                        }
                    }
                    met_str = mod.metrics[met_code]
                    PdataFile.save(pdata, met_code, met_str)
                    met_code_exported = True
            if not met_code_exported:
                UI.error(f'The user-enabled metric "{met_code}" didn\'t find a '
                         'suitable metric to plot it. Make sure your modules '
                         'are correctly registered.')
        UI.indent_out()
        return

    def export_all_plots(self):
        UI.indent_in(title='EXPORTING PLOTS')
        for met in st.Metrics.enabled:
            for mod in self.modules_list:
                if mod.has_metric(met):
                    mod.export_plot(code=met, )
            mod.export_all_plots(bg_module=self.bg_module,
                                 bg_code=self.bg_metric)
        UI.indent_out()
        return

    def plot_from_dict(self, metrics_dict:dict):
        UI.indent_in(title='PLOTTING METRICS')
        bg_module = self.map
        bg_module.import_metric(metric_dict, bg_mode=True)
        for mod in self.modules_list:
            mod.plot_from_dict(metric_dict, bg_module=bg_module, bg_code='MAP')
            # [!] remember to enable only the metrics that come in the file
            # st.Plot.include = { met_dict['metric']['code'] }
        UI.indent_out()
        return

    @classmethod
    def aggregate_metrics(cls, metrics_dicts:dict):
        UI.indent_in(title='AGGREGATING SAME-CODE METRICS')
        UI.warning('DRAFT IMPLEMENTATION')

        codes_list = sorted(metrics_dicts.keys())

        for code in codes_list:
            same_code_metrics = metrics_dicts[code]
            # check that the metric code is known
            if code not in cls.Aggr_Modules:
                UI.warning(f'Metric "{code}" is not mapped to any '
                           'aggregate-enabled Module. '
                           f'Ignoring {len(same_code_metrics)} '
                           'metric files.')
            else:
                aggr_module = cls.Aggr_Modules[code]
                aggr_module.export_aggregated_plots(same_code_metrics)
        UI.indent_out()
        return
