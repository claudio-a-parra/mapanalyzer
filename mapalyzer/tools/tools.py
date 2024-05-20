import sys
import matplotlib.pyplot as plt

from settings import Settings as st
from .mapplotter import Map
from .locality import Locality
from .hit import Hit
from .usage import UnusedBytes
from .alias import Alias
from .siue import SIUEvict

class Tools:
    def __init__(self):
        # Create map plotter
        self.map = Map()

        # Create other instruments and make them share their
        # X axis (for the plots)
        self.locality = Locality(shared_X=self.map.X)

        # self.hit = Hit(self.ic, cache_specs.cache_size, verb=verb)
        # self.hit.X = self.map.X

        # self.usage = UnusedBytes(self.ic, verb=verb)
        # self.usage.X = self.map.X


        # num_sets = cache_specs['size']//(cache_specs['asso']*\
        #                                  cache_specs['line'])

        # self.alias = Alias(self.ic, cache_specs.num_sets, cache_specs.asso,
        #                    verb=verb)
        # self.alias.X = self.map.X

        # self.siu = SIUEvict(self.ic, cache_specs.num_sets, cache_specs.asso,
        #                     self.alias, verb=verb)
        # self.siu.X = self.map.X

        # # list of all instruments for easy access.
        # self.inst_list = [self.locality, self.hit, self.usage, self.alias,
        #                   self.siu]
        self.tools_list = [self.locality]
        return

    def plot(self):
        title_padding=24
        fig,map_axes = plt.subplots(
            figsize=(st.plot.width, st.plot.height))
        
        # plot MAP only.
        filename=f'{st.plot.prefix}{self.map.plot_name_sufix}.{st.plot.format}'
        print(f'    {self.map.plot_title:{title_padding}} : {filename}')
        self.map.plot(map_axes, basename=st.plot.prefix, title=True)
        fig.savefig(filename, dpi=st.plot.dpi, bbox_inches='tight', pad_inches=0)


        # plot superposition of MAP and other tools
        fig, tool_axes = plt.subplots(
            figsize=(st.plot.width, st.plot.height))
        map_axes = tool_axes.twinx()
        tool_axes.set_yticks([])
        for tool in self.tools_list:
            filename=f'{st.plot.prefix}{tool.plot_name_sufix}.{st.plot.format}'
            print(f'    {tool.plot_title:{title_padding}} : {filename}')

            # plot tool and map
            tool.plot(tool_axes, basename=st.plot.prefix)
            self.map.plot(map_axes)

            # save figure
            fig.savefig(filename, dpi=st.plot.dpi, bbox_inches='tight', pad_inches=0)
            map_axes.cla()
            tool_axes.cla()
        return

    def describe(self, ind='    '):
        for tool in self.tools_list:
            tool.describe(ind=ind)
