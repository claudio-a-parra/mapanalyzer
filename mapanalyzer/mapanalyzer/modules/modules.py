import sys
import matplotlib.pyplot as plt

from mapanalyzer.settings import Settings as st
from mapanalyzer.modules.mapplotter import Map
# from mapanalyzer.modules.locality import Locality
# from mapanalyzer.modules.hitmiss import HitMiss
# from mapanalyzer.modules.cost import Cost
from mapanalyzer.modules.usage import CacheUsage
# from mapanalyzer.modules.alias import Aliasing
# from mapanalyzer.modules.eviction import EvictionDuration

class Modules:
    def __init__(self):
        # Create set of modules with shared X axis (for plots)
        self.map = Map()
        # self.locality = Locality(shared_X=self.map.X)
        # self.hitmiss = HitMiss(shared_X=self.map.X)
        # self.cost = Cost(shared_X=self.map.X)
        self.usage = CacheUsage(shared_X=self.map.X)
        # self.aliasing = Aliasing(shared_X=self.map.X)
        # self.evicd = EvictionDuration(shared_X=self.map.X)

        # list of all modules
        # self.modules_list = \
        #     [self.map, self.locality, self.hitmiss, self.cost, self.usage,
        #      self.aliasing, self.evicd]

        # list of all modules
        print('[!] Including only MAP and CUR')
        self.modules_list = \
            [self.map, self.usage]

        # set the space needed to print the widest module name
        st.Plot.ui_modulename_hpad = \
            max([len(m.name)+1 for m in self.modules_list])
        return

    def describe(self, ind='    '):
        for mod in self.modules_list:
            mod.describe(ind=ind)
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
        for mod in self.modules_list:
            mod.export_metrics()

    def export_plots(self):
        for mod in self.modules_list:
            mod.export_plots(bg_module=self.map)
        return

    def plot_from_dict(self, plot_dict):
        # Give the dictionary to all modules. They will internally decide
        # whether to plot it or not based on their plotcode. Some modules have
        # more than one plotcode, so let the module decide.
        for mod in self.modules_list:
            mod.plot_from_dict(plot_dict)
        return
