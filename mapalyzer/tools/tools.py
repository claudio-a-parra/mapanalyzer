import sys
import matplotlib.pyplot as plt

from .ic import InstrCounter
from .mapplotter import Map
from .locality import Locality
from .hit import Hit
from .usage import UnusedBytes
from .alias import Alias
from .siue import SIUEvict

#-------------------------------------------
class Tools:
    def __init__(self, cache_specs, map_metadata, plot_metadata, verb=False):
        self.ic = InstrCounter()
        self.plot_metadata = plot_metadata

        # Create map plotter
        self.map = Map(self.ic, map_metadata, plot_metadata.res, verb=verb)

        # Create other instruments and make them share their
        # X axis (for the plots)
        self.locality = Locality(map_metadata, cache_specs, shared_X=self.map.X,
                                 verb=verb)

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
        self.inst_list = []

    def disable_all(self):
        for tool in self.inst_list:
            tool.enabled = False


    def plot(self):
        name_prefix = self.plot_metadata.prefix
        dpi = self.plot_metadata.dpi
        out_format = self.plot_metadata.format
        fig,map_axes = plt.subplots(
            figsize=(self.plot_metadata.width, self.plot_metadata.height))
        
        # plot MAP only.
        print(f'    Plotting {self.map.plot_title}.')
        self.map.plot(map_axes, basename=name_prefix, title=True)
        filename=f'{name_prefix}{self.map.plot_name_sufix}.{out_format}'
        print(f'        {filename}')
        fig.savefig(filename, dpi=dpi, bbox_inches='tight', pad_inches=0)


        # plot superposition of MAP and other tools
        fig, tool_axes = plt.subplots(
            figsize=(self.plot_metadata.width, self.plot_metadata.height))
        map_axes = tool_axes.twinx()
        tool_axes.set_yticks([])
        for tool in self.inst_list:
            print(f'    Plotting {tool.plot_title}.')
            # plot tool and map
            tool.plot(tool_axes, basename=name_prefix)
            self.map.plot(map_axes)

            # save figure
            filename=f'{name_prefix}{tool.plot_name_sufix}.{out_format}'
            print(f'        {filename}')
            fig.savefig(filename, dpi=dpi, bbox_inches='tight', pad_inches=0)
            map_axes.cla()
            tool_axes.cla()

        return
