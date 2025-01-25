import sys
import matplotlib.pyplot as plt

from mapanalyzer.settings import Settings as st
from mapanalyzer.util import MetricStrings
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

    def __init__(self):
        # Reset Metrics counter
        MetricStrings.counter = 0
        # Create set of modules with shared X axis (for plots)
        self.map = Map()
        #! self.locality = Locality(shared_X=self.map.X)
        #! self.hitmiss = HitMiss(shared_X=self.map.X)
        #! self.cost = Cost(shared_X=self.map.X)
        self.usage = CacheUsage(shared_X=self.map.X)
        #! self.aliasing = Aliasing(shared_X=self.map.X)
        #! self.evicd = EvictionDuration(shared_X=self.map.X)

        # list of all modules
        #! self.modules_list = \
        #!     [self.map, self.locality, self.hitmiss, self.cost, self.usage,
        #!      self.aliasing, self.evicd]

        # list of all modules
        UI.warning('Including only MAP and CUR')
        self.modules_list = [self.map, self.usage]

        # set space needed to print any metric code.
        UI.metric_code_hpad = max(
            [len(k) for k in st.Plot.PLOTCODES.keys()]) + 1
        return

    def describe(self):
        UI.indent_in(title='MAPANALYZER MODULES')
        mods_names = []
        mods_metrics = []
        mods_about = []
        for mod in self.modules_list:
            mods_names.append(mod.name)
            mods_metrics.append(mod.metrics.keys())
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

    def export_metrics(self):
        UI.indent_in(title='EXPORTING METRICS')
        # export all metrics of each module.
        for mod in self.modules_list:
            mod.export_all_metrics(bg_module=self.map, bg_code='MAP')
        UI.indent_out()
        return

    def export_plots(self):
        UI.indent_in(title='EXPORTING PLOTS')
        for mod in self.modules_list:
            mod.export_all_plots(bg_module=self.map, bg_code='MAP')
        UI.indent_out()
        return

    def plot_from_dict(self, metric_dict:dict):
        UI.indent_in(title='PLOTTING METRICS')
        bg_module = self.map
        bg_module.import_metric(metric_dict, bg_mode=True)
        for mod in self.modules_list:
            mod.plot_from_dict(metric_dict, bg_module=bg_module, bg_code='MAP')
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
