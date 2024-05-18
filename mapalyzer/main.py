#!/usr/bin/env python3
import sys # for command line arguments
import os # for file extension removal
import argparse # to get command line arguments

from map_file_reader import MapFileReader
from address_formatter import log2, AddrFmt
from cache import Cache
from tools import Tools


class MemSpecs:
    def __init__(self, arch=64, cache_size=32768, line_size=64, asso=8,
                 fetch=1, write=2):
        # Default typical Intel i7 L1d
        self.arch = arch
        self.cache_size = cache_size
        self.line_size = line_size
        self.asso = asso
        self.fetch_cost = fetch
        self.write_cost = write
        self.set_derived_values()    
        return

    def set_derived_values(self):
        self.num_sets = self.cache_size // (self.asso * self.line_size)
        self.bits_set = log2(self.num_sets)
        self.bits_off = log2(self.line_size)
        self.bits_tag = self.arch - self.bits_set - self.bits_off
        return
    
    def set_value(self, name, val):
        key_map = {
            'arch_size_bits'  : 'arch',
            'cache_size_bytes': 'cache_size',
            'line_size_bytes' : 'line_size',
            'associativity'   : 'asso',
            'fetch_cost'      : 'fetch_cost',
            'writeback_cost'  : 'write_cost',
        }
        if name not in key_map:
            print(f'[!] Invalid name {name}. Ignoring line.')
            return
        try:
            int_val = int(val)
        except ValueError as e:
            print(f'[!] Invalid value ({val}) given to name "{name}". '
                  'It must be integer. Ignoring.')
            return
        setattr(self, key_map[name], int_val)
        self.set_derived_values()
        return

    def describe(self, ind=''):
        print(f'{ind}Address size         : {self.arch} bits ('
              f'tag:{self.bits_tag} | '
              f'idx:{self.bits_set} | '
              f'off:{self.bits_off})\n'
              f'{ind}Cache size           : {self.cache_size} bytes\n'
              f'{ind}Number of sets       : {self.num_sets}\n'
              f'{ind}Line size            : {self.line_size} bytes\n'
              f'{ind}Associativity        : {self.asso}-way\n'
              f'{ind}Main Mem. Fetch cost : {self.fetch_cost} units\n'
              f'{ind}Main Mem. Write cost : {self.write_cost} units'
              )
        return

class PlotMetadata:
    def __init__(self, width, height, resolution, dpi, format, prefix):
        self.width = width
        self.height = height
        self.res = resolution
        self.dpi = dpi
        self.format = format
        self.prefix = prefix
        return

def get_cache_specs(cache_filename=None):
    specs = MemSpecs()
    
    # if no file was given
    if cache_filename == None:
        return specs

    try:
        with open(cache_filename, 'r') as cache_config_file:
            for line in cache_config_file:
                # skip empty or comment
                if line == '' or line[0] == '#':
                    continue
                # get rid of trailing comments
                content_comment = line.split('#')
                line = content_comment[0]

                # parse <name>:<value>
                key_val_arr = line.split(':')

                # ignore lines not like <name>:<value>
                if len(key_val_arr) != 2:
                    print(f'[!] File {cache_filename}: Invalid line, ignoring:\n'
                          '    >>>>{line}')
                    continue
                name,val = key_val_arr[0].strip(), key_val_arr[1].strip()
                specs.set_value(name, val)
    except FileNotFoundError:
        print(f"[!] File {cache_filename} does not exist. Using default "
              "configuration.")
    return specs


def run_simulation(map_reader, cache, tools):
    ic = tools.ic
    _,_,byte = AddrFmt.split(map_reader.base_addr)
    if byte != 0:
        print(f'[!] Warning: Memory block is not cache aligned. '
              f'First byte is {byte} bytes into the cache line.')

    tot_instr = map_reader.time_size-1
    for access in map_reader:
        ic.counter = access.time
        # print progress
        print('\033[2K\r    '
              f'{(100*access.time/tot_instr):5.1f}% '
              f'{access.time:8d}/{tot_instr}'
              ,end='')
        sys.stdout.flush()
        # perform memory access
        cache.access(access)
    print()
    tools.disable_all()
    ic.step()
    cache.flush()
    return


def command_line_args_parser():
    ms = MemSpecs()
    synopsis = ('MAPalyzer, a tool to study the cache friendliness of '
                'memory access patterns.')
    cache_conf = ('cache.conf:\n'
                  '  The cache file file must have this format:\n'
                  '\n'
                  '    # Comments start with pound sign\n'
                  f'   line_size_bytes     : <value> # default: {ms.line_size}\n'
                  f'   associativity       : <value> # default: {ms.asso}\n'
                  f'   cache_size_bytes    : <value> # default: {ms.cache_size}\n'
                  f'   arch_size_bits      : <value> # default: {ms.arch}\n'
                  f'   fetch_time_cost     : <value> # default: {ms.fetch_cost}\n'
                  f'   writeback_time_cost : <value> # default: {ms.write_cost}\n')
    signature = ('By Claudio A. Parra. 2024.\n'
                 'parraca@uci.edu')

    parser = argparse.ArgumentParser(
        description=synopsis+'\n\n',
        epilog=cache_conf+'\n\n'+signature,
        formatter_class=argparse.RawTextHelpFormatter)
    
    # Adding arguments
    parser.add_argument(
        'input_file', metavar='input_file.map', type=str,
        help='Path of the input Memory Access Pattern file.'
    )
    
    parser.add_argument(
        '-c', '--cache', metavar='cache.conf', dest='cache', type=str,
        default=None,
        help='File describing the cache. See "cache.conf" section.'
    )
    
    parser.add_argument(
        '-px', '--plot-x', dest='px', type=float, default=8,
        help="Width of the plots."
    )
    
    parser.add_argument(
        '-py', '--plot-y', dest='py', type=float, default=4,
        help="Height of the plots."
    )
    
    parser.add_argument(
        '-dpi', '--dpi', dest='dpi', type=int, default=300,
        help='Choose the DPI of the resulting plots.'
    )
    
    parser.add_argument(
        '-f', '--format', dest='format', choices=['png', 'pdf'], default='png',
        help='Choose the output format of the plots.'
    )
    
    def check_res(val):
        min_res = 4
        max_res = 2048
        def_res = 512
        val = int(val)
        if min_res < val < max_res:
            return val
        else:
            print(f'[!] Warning: resolution value must be between {min_res} and '
                  f'{max_res}. Using default value {def_res}.')
            return def_res
    parser.add_argument(
        '-r', '--resolution', dest='resolution', type=check_res, default=512,
        help=('Maximum resolution of the Memory Access Pattern grid (value '
              'between 4 and 2048).')
    )

    args = parser.parse_args()
    return args

    

def main():
    args = command_line_args_parser()

    print(f'Reading cache parameters: {args.cache}')
    cache_specs = get_cache_specs(cache_filename=args.cache)
    AddrFmt.init(cache_specs)
    
    plot_metadata = PlotMetadata(
        args.px, args.py, args.resolution, args.dpi, args.format,
        os.path.basename(os.path.splitext(args.input_file)[0])
    )
    
    print(f'Creating MAP Reader, Memory System, and Tools.')
    map_reader = MapFileReader(args.input_file)
    map_metadata = map_reader.get_metadata()
    tools = Tools(cache_specs, map_metadata, plot_metadata)
    cache = Cache(cache_specs, tools=tools)
    cache.describe_cache()
    
    print(f'Tracing Memory Access Pattern: {args.input_file}')
    run_simulation(map_reader, cache, tools)

    print(f'Plotting Results ({plot_metadata.format})')
    tools.plot()

    print('Done')



if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        exit(0)
