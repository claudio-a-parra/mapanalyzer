import sys
import matplotlib.pyplot as plt

from settings import Settings as st
from .mapplotter import Map
from .locality import Locality
from .hitmiss import HitMiss
from .usage import UnusedBytes
from .alias import Alias
from .siue import SIUEvict

class Tools:
    def __init__(self):
        # Create set of tools with shared X axis (for plots)
        self.map = Map()
        self.locality = Locality(shared_X=self.map.X)
        self.hitmiss = HitMiss(shared_X=self.map.X)
        #self.usage = UnusedBytes(shared_X=self.map.X)
        #self.alias = Alias(shared_X=self.map.X)
        #self.siu = SIUEvict(shared_X=self.map.X)

        # list of all tools
        self.tools_list = [self.map, self.locality, self.hitmiss]
        st.plot.ui_name_hpad = max([len(t.name)+1 for t in self.tools_list])
        return

    def describe(self, ind='    '):
        for t in self.tools_list:
            t.describe(ind=ind)

    def commit(self, time):
        for t in self.tools_list:
            t.commit(time)

    def plot(self):
        for t in self.tools_list:
            t.plot(top_tool=self.map)
        return
