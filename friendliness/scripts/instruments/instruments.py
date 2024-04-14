import sys
import matplotlib.pyplot as plt

from .ic import InstrCounter
from .mapplotter import Map
from .locality import Locality
from .miss import Miss
from .usage import UnusedBytes
from .alias import Alias
from .siue import SIUEvict

#-------------------------------------------
class Instruments:
    def __init__(self, cache_specs, map_metadata, plot_width, plot_height,
                 resolution, verb=False):
        self.ic = InstrCounter()
        self.plot_width = plot_width
        self.plot_height = plot_height

        # Create map plotter
        self.map = Map(self.ic, map_metadata, plot_width, plot_height,
                       resolution, verb=verb)

        # Create other instruments: (alias, miss, usage, and SIU) and
        # make them share their X axis (for the plots)
        self.locality = Locality(self.ic, cache_specs['size'],
                                 cache_specs['line'])
        self.locality.X = self.map.X

        self.miss = Miss(self.ic, cache_specs['size'], verb=verb)
        self.miss.X = self.map.X

        self.usage = UnusedBytes(self.ic, verb=verb)
        self.usage.X = self.map.X


        num_sets = cache_specs['size']//(cache_specs['asso']*\
                                         cache_specs['line'])

        self.alias = Alias(self.ic, num_sets, verb=verb)
        self.alias.X = self.map.X

        self.siu = SIUEvict(self.ic, num_sets, verb=verb)
        self.siu.X = self.map.X

        # list of all instruments for easy access.
        self.inst_list = [self.locality, self.miss, self.usage, self.alias,
                          self.siu]

    def disable_all(self):
        for tool in self.inst_list:
            tool.enabled = False


    def plot(self, window, basename, out_format, dpi=800):
        fig, map_axes = plt.subplots(
            figsize=(self.plot_width, self.plot_height))
        instr_axes = map_axes.twinx()
        instr_axes.set_yticks([])
        # plot MAP only.
        print(f'    Plotting {self.map.plot_title}.')
        self.map.plot(map_axes, basename=basename, title=True)
        filename=f'{basename}{self.map.plot_name_sufix}.{out_format}'
        print(f'        {filename}')
        fig.savefig(filename, dpi=dpi, bbox_inches='tight')
        map_axes.cla()

        # plot superposition of MAP and instrument.
        for instr in self.inst_list:
            print(f'    Plotting {instr.plot_title}.')
            # plot map
            self.map.plot(map_axes)
            # plot instrument
            instr.plot(instr_axes, basename=basename)

            # save figure
            filename=f'{basename}{instr.plot_name_sufix}.{out_format}'
            print(f'        {filename}')
            fig.savefig(filename, dpi=dpi, bbox_inches='tight')
            map_axes.cla()
            instr_axes.cla()

        return
