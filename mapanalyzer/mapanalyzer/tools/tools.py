import sys
import matplotlib.pyplot as plt

from mapanalyzer.settings import Settings as st
from mapanalyzer.tools.mapplotter import Map
from mapanalyzer.tools.locality import Locality
from mapanalyzer.tools.hitmiss import HitMiss
from mapanalyzer.tools.cost import Cost
from mapanalyzer.tools.usage import CacheUsage
from mapanalyzer.tools.alias import Aliasing
from mapanalyzer.tools.siue import SIUEviction
from mapanalyzer.tools.personality import Personality

class Tools:
    def __init__(self):
        # Create set of tools with shared X axis (for plots)
        self.map = Map()
        self.locality = Locality(shared_X=self.map.X)
        self.hitmiss = HitMiss(shared_X=self.map.X)
        self.cost = Cost(shared_X=self.map.X)
        self.usage = CacheUsage(shared_X=self.map.X)
        self.aliasing = Aliasing(shared_X=self.map.X)
        self.perso = Personality(shared_X=self.map.X)
        self.siu = SIUEviction(shared_X=self.map.X)

        # list of all tools
        self.tools_list = [self.map, self.locality, self.hitmiss,
                           self.cost, self.usage, self.aliasing, self.perso, self.siu]

        st.plot.ui_name_hpad = max([len(t.tool_name)+1 for t in self.tools_list])
        return

    def describe(self, ind='    '):
        for t in self.tools_list:
            t.describe(ind=ind)

    def commit(self, time):
        for t in self.tools_list:
            t.commit(time)

    def plot(self):
        for t in self.tools_list:
            t.plot(bottom_tool=self.map)
        return
