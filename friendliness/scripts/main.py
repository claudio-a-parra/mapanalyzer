#!/usr/bin/env python3
import sys # for command line arguments
import os # for file extension removal
import argparse # to get command line arguments


from address_formatter import log2, AddressFormatter
from instruction_counter import InstrCounter
from instruments import Instruments
from cache import Cache
from map_file_reader import MapFileReader


# Default cache configuration. typical Intel i7 L1d
default_cache_specs = {
    'line': ("Line size [bytes]", 64),
    'asso': ("Associativity [lines]", 8),
    'size': ("Total Cache size [bytes]" , 32768),
    'arch': ("Architecture word size [bits]", 64)}


def get_cache_specs(specs, cache_filename=None):
    file_to_spec_key_map = {
        'line_size_bytes': 'line',
        'associativity': 'asso',
        'cache_size_bytes': 'size',
        'arch_size_bits': 'arch'
    }
    def _complete_cache_specs(specs):
        # missing parameters filled from default specs config
        for key in specs:
            if not type(specs[key]) == int:
                specs[key] = specs[key][1]
        print(f'    line size     : {specs["line"]}\n'
              f'    associativity : {specs["asso"]}\n'
              f'    cache size    : {specs["size"]}\n'
              f'    architecture  : {specs["arch"]}')

    # if no file was given
    if cache_filename == None:
        _complete_cache_specs(specs)
        return

    try:
        with open(cache_filename, 'r') as cache_config_file:
            for line in cache_config_file:
                # skip empty or comment
                if line == '' or line[0] == '#':
                    continue
                key_val_arr = line.split(':')

                # ignore lines not like <name>:<value>
                if len(key_val_arr) != 2:
                    print(f"File {cache_filename}: Invalid line:\n"
                          ">>>>{line}\n"
                          "Ignoring.")
                    continue
                name,val = key_val_arr[0].strip(), key_val_arr[1].strip()

                # ignore weird names
                if name not in file_to_spec_key_map:
                    print(f"File {cache_filename}: Unknown parameter name:\n"
                          f">>>>{line}\n"
                          "Ignoring.")
                    continue

                # potential good 'name:value' found
                key = file_to_spec_key_map[name]
                default_val = specs[key][1]
                try:
                    specs[key] = int(val)
                except ValueError:
                    print(f"Incorrect value in redirected input file:\n"
                          f">>>>{file_user_input}\n"
                          f"Using default value ({default_val}).")
                    specs[key] = int(default_val)
    except FileNotFoundError:
        print(f"[!]    File {cache_filename} does not exist. Using default "
              "configuration.")
    complete_cache_config(specs)


#def run_simulation(cache_specs, map_reader, map_plotter, verb=False):
def run_simulation(map_reader, instruments, cache_system, verb=False):
    ic = instruments.ic

    #instruments = Instruments(ic, cache_specs, map_plotter=mat_plotter,
    #                          verb=verb)
    #af = cache_system.af
    #cache = Cache(cache_specs, instr=instruments)

    _,_,byte = cache_system.af.split(map_reader.base_addr)
    if byte != 0:
        print(f'[!] Warning: Memory block is not cache aligned. First byte at '
              f'offset {byte}.')

    # First Pass
    for access in map_reader:
        ic.counter = access.time
        cache_system.access(access)
        if verb:
            cache_system.dump()
            print()

    # Prepare for second pass
    instruments.disable_all()
    ic.step()
    cache_system.flush()
    ic.reset()
    instruments.prepare_for_second_pass()
    cache_system.reset_clock()

    # Second Pass
    for access in map_reader:
        ic.counter = access.time
        cache_system.access(access)
        if verb:
            cache_system.dump()
            print()
    instruments.disable_all()
    ic.step()
    cache_system.flush()

    return


def command_line_args_parser():
    synopsis = ("MAP Analyzer: A tool to study the cache friendliness of "
                "memory access patterns.")
    cache_conf = ("cache.conf:\n"
                  "  The cache file file must have this format:\n"
                  "\n"
                  "      # Comments start with pound sign\n"
                  "      line_size_bytes  : <value> # default: 16\n"
                  "      associativity    : <value> # default: 2\n"
                  "      cache_size_bytes : <value> # default: 256\n"
                  "      arch_size_bits   : <value> # default: 16")
    note = ("note:\n"
            "  If running with verbose mode on, all addresses, set indices,\n"
            "  line offsets, and tags are in hexadecimal unless explicitly\n"
            "  indicated otherwise. Clocks and other numbers are decimal.")
    signature = ("By Claudio A. Parra. 2024.\n"
                 "parraca@uci.edu")

    parser = argparse.ArgumentParser(
        description=synopsis+'\n\n',
        epilog=cache_conf+'\n\n'+note+'\n\n'+signature,
        formatter_class=argparse.RawTextHelpFormatter)
    #parser = argparse.ArgumentParser(description=__doc__
    # Adding arguments
    parser.add_argument(
        'input_file', metavar='input_file.map', type=str,
        help='Path of the input Memory Access Pattern file.')
    parser.add_argument(
        '-c', '--cache', metavar='cache.conf', dest='cache', type=str,
        default=None,
        help=("File describing the shape of the cache. See "
              "'cache.conf' section."))
    parser.add_argument(
        '-w', '--window', dest='window', type=int, default=None,
        help=("Moving average filter window size for data plotting. "
              "(Default: 5%% of total number of instructions in the "
              "input file.)"))
    parser.add_argument(
        '-px', '--plot-x', dest='px', type=int, default=8,
        help="Width of the plots.")
    parser.add_argument(
        '-py', '--plot-y', dest='py', type=int, default=4,
        help="Height of the plots.")
    parser.add_argument(
        '-f', '--format', dest='format', choices=['png', 'pdf'], default='pdf',
        help='Choose the output format of the plots.')
    def check_res(val):
        min_res = 10
        max_res = 600
        def_res = 150
        val = int(val)
        if min_res < val < max_res:
            return val
        else:
            print(f'[!] Warning: resolution value must be between {min_res} and '
                  f'{max_res}. Using default value {def_res}.')
            return def_res
    parser.add_argument(
        '-r', '--resolution', dest='resolution', type=check_res, default=150,
        help=('Resolution of the Memory Access Pattern plot (value between '
              '10 and 600).'))
    parser.add_argument(
        '-v', '--verbose', dest='verbosity', action="store_true",
        help="Print all the fun stuff.")

    args = parser.parse_args()
    return args

    

def main():
    global default_cache_specs
    cache_specs = default_cache_specs

    # parse command line arguments
    args = command_line_args_parser()

    print(f'Reading Cache Parameters.')
    get_cache_specs(cache_specs, cache_filename=args.cache)

    print(f'Creating MAP Reader, Instruments, and Cache System.')
    map_reader = MapFileReader(args.input_file)
    map_metadata = map_reader.get_metadata()
    instruments = Instruments(cache_specs, map_metadata,
                              args.px, args.py, args.resolution)
    cache_system = Cache(cache_specs, instr=instruments)


    #map_plotter = MapPlotter(metadata, args.px, args.py, args.resolution)
    #ic = InstrCounter()
    #instruments = Instruments(ic, cache_specs,
    #                          map_plotter=mat_plotter)



    print(f'Tracing Memory Access Pattern: {args.input_file}')
    run_simulation(map_reader, instruments, cache_system)
    #instruments = run_simulation(cache_specs, map_reader, map_plotter, verb=args.verbosity)

    # print('Building Instruments Log')
    # instruments.build_log()

    # print(f'Filtering Log')
    # instruments.filter_log(win=args.window)

    print(f'Plotting Results ({args.format})')
    prefix = os.path.basename(os.path.splitext(args.input_file)[0])
    instruments.plot(args.window, prefix, args.format)

    # print('Full (miss, hit):')
    # for i,x in zip(instruments.instruction_ids,instruments.miss.full_events_log):
    #     print(f'{i:3}: {x}')

    # print('Filtered (avg on window):')
    # for i,x in zip(instruments.instruction_ids,instruments.miss.filtered_avg_log):
    #     print(f'{i:3}: {x}')





if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        exit(0)
