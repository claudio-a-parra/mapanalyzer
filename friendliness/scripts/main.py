#!/usr/bin/env python3
import sys # for command line arguments
import os # for file extension removal
import argparse # to get command line arguments


from address_formatter import log2, AddressFormatter
from instruments import InstrCounter, Instruments
from cache import Cache
from mem_access_pattern import MemAP


# Default cache configuration. Small for debugging.
cache_specs = {
    'line': ("Line size [bytes]", 16),
    'asso': ("Associativity [lines]", 2),
    'size': ("Total Cache size [bytes]" , 256),
    'arch': ("Architecture word size [bits]", 16)}


def get_cache_specs_from_file(specs, file_name):
    file_to_spec_key_map = {
        'line_size_bytes': 'line',
        'associativity': 'asso',
        'cache_size_bytes': 'size',
        'arch_size_bits': 'arch'
    }
    try:
        with open(file_name, 'r') as cache_config_file:
            for line in cache_config_file:

                if line == '' or line[0] == '#': # skip empty or comment
                    continue
                key_val_arr = line.split(':')

                if len(key_val_arr) != 2: # ignore lines not like <name>:<value>
                    print(f"File {file_name}: Invalid line:\n"
                          ">>>>{line}\n"
                          "Ignoring.")
                    continue
                name,val = key_val_arr[0].strip(), key_val_arr[1].strip()

                if name not in file_to_spec_key_map: # ignore weird names
                    print(f"File {file_name}: Unknown parameter name:\n"
                          f">>>>{line}\n"
                          "Ignoring.")
                    continue
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
        print(f"File {file_name} does not exist. Using default configuration.")



def run_simulation(specs, access_pattern, plots_dims, verb=False):
    # Init Instruction Counter, Instruments, Address Formatter, and Cache
    ic = InstrCounter()
    instr = Instruments(ic, specs, ap=access_pattern,
                        plots_dims=plots_dims, verb=verb)
    af = AddressFormatter(specs)
    cache = Cache(specs, instr=instr)

    # First Pass
    for access in access_pattern:
        ic.counter = access.time
        cache.access(access)
        if verb:
            cache.dump()
            print()

    # Prepare for second pass
    instr.disable_all()
    ic.step()
    cache.flush()
    ic.reset()
    instr.prepare_for_second_pass()
    cache.reset_clock()

    # Second Pass
    for access in access_pattern:
        ic.counter = access.time
        cache.access(access)
        if verb:
            cache.dump()
            print()
    instr.disable_all()
    ic.step()
    cache.flush()

    return instr


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
    signature = ("By Claudio A. Parra.\n"
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
        default="cache.conf",
        help=("File describing the shape of the cache. See "
              "'cache.conf' section."))
    parser.add_argument(
        '-o', '--output', dest='output', type=str, default='',
        help="Prefix of output files (by default the same as input file).")
    parser.add_argument(
        '-w', '--window', dest='window', type=int, default=-1,
        help=("Moving average filter window size for data plotting. "
              "(Default: 5%% of total number of instructions in the "
              "input file.)"))
    parser.add_argument(
        '-px', '--plot-x', dest='px', type=int, default=8,
        help="Width of the plots.")
    parser.add_argument(
        '-py', '--plot-y', dest='py', type=int, default=6,
        help="Height of the plots.")
    parser.add_argument(
        '-v', '--verbose', dest='verbosity', action="store_true",
        help="Print all the fun stuff.")

    args = parser.parse_args()
    return args

    

def main():
    global cache_specs

    args = command_line_args_parser()

    print(f'Reading cache configuration: {args.cache}...')
    get_cache_specs_from_file(cache_specs, args.cache)

    print(f'Running mem. access pattern: {args.input_file}...')
    access_pattern = MemAP(args.input_file)
    instruments = run_simulation(cache_specs, access_pattern,
                                 plots_dims=(args.px, args.py),
                                 verb=args.verbosity)

    print("Building Instruments Log...")
    instruments.build_master_log()

    window = args.window
    if window < 0 or window > access_pattern.event_count:
        if window > access_pattern.event_count:
            print(f'[!] Warning: the given avg window ({window}) is larger '
                  'than the number of events. Using default value.')
        window = max(round(access_pattern.event_count * 0.05), 1)
    print(f'Filtering Log (win={window})...')
    instruments.filter_log(win=window)

    prefix = args.output
    if prefix == '':
        prefix = os.path.basename(os.path.splitext(args.input_file)[0])
    print(f'Plotting Results...')
    # instruments.plot_data(prefix)
    instruments.plot(prefix)

    print('Done.')

        
if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        exit(0)
