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
        self.modules_list = \
            [self.map, self.usage]

        # set space needed to print any metric code.
        UI.metric_code_hpad = max(
            [len(k) for k in st.Plot.PLOTCODES.keys()]
        ) + 1
        return

    def describe(self):
        UI.indent_in(title='MAPANALYZER MODULES')
        mods_names = []
        mods_metrics = []
        mods_about = []
        for mod in self.modules_list:
            mods_names.append(mod.name)
            mods_metrics.append(mod.metrics)
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
        for mod in self.modules_list:
            mod.export_metrics(bg_module=self.map)
        UI.indent_out()
        return

    def export_plots(self):
        UI.indent_in(title='EXPORTING PLOTS')
        for mod in self.modules_list:
            mod.export_plots(bg_module=self.map)
        UI.indent_out()
        return

    def plot_from_dict(self, met_dict, map_dict):
        self.map.load_from_dict(map_dict)
        # Give the dictionary to all modules. They will internally decide
        # whether to plot it or not based on their plotcode. Some modules have
        # more than one plotcode, so let the module decide.
        UI.indent_in(title='PLOTTING METRICS')
        for mod in self.modules_list:
            mod.plot_from_dict(met_dict, bg_module=self.map)
        UI.indent_out()
        return

    @classmethod
    def classify_and_aggregate_metrics(cls, mixed_metrics_dicts):
        UI.indent_in(title='AGGREGATING SAME-TYPE METRICS')

        # classify metrics by their code
        classified_metrics = {}
        for met_dict in mixed_metrics_dicts:
            met_code = met_dict['code']
            if met_code not in classified_metrics:
                classified_metrics[met_code] = []
            classified_metrics[met_code].append(met_dict)

        # dispatch a list of "same type" metrics to each registered module
        for c_met_code in classified_metrics:
            if c_met_code not in cls.Aggr_Modules:
                UI.warning(f'Metric "{c_met_code}" is not mapped to any '
                           'aggregate-enabled Module. '
                           f'Ignoring {len(classified_metrics[c_met_code])} '
                           'metric files.')
            else:
                aggr_module = cls.Aggr_Modules[c_met_code]
                same_type_metrics = classified_metrics[c_met_code]
                aggr_module.aggregate_metrics(same_type_metrics)
        UI.indent_out()
        return
