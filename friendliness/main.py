#!/usr/bin/env python3
import sys # for command line arguments
import os # for file extension removal

from address_formatter import log2, AddressFormatter
from instruments import InstrCounter, Instruments
from cache import Cache

def get_specs_tty(file_to_spec_key_map, specs_map):
    """if a human is typing, then give them some chances"""
    enough_is_enough = 5
    for k in specs_map:
        description, default_val = specs_map[k]

        for i in range(enough_is_enough):
            user_input = input(f"{description} "
                               f"(default: {default_val}): ")
            # empty line entered. Pick default value
            if user_input == '':
                specs_map[k] = int(default_val)
                break

            try:
                specs_map[k] = int(user_input)
                break
            except ValueError:
                print(f"Incorrect input '{user_input}'")
                specs_map[k] = int(default_val)


def get_specs_redirected_input(file_to_spec_key_map, specs_map):
    """if the user redirected input, then strictly collect values"""
    for i in range(len(file_to_spec_key_map)):
        file_user_input = input()
        key_val_arr = file_user_input.split(':')

        if len(key_val_arr) != 2: # if the line does not look like <key>:<value>
            print(f"Error: Invalid line in redirected input file:\n"
                  f">>>>{file_user_input}\n"
                  "Use:  <name>:<value> format. Where <name> can be:"
                  f"  {list(file_to_spec_key_map.keys())}")
            exit(1)
        name,val = key_val_arr[0].strip(),key_val_arr[1].strip()

        if name not in file_to_spec_key_map: # if the key in unknown
            print(f"Error: Unknown cache parameter name in redirected "
                  "input file:\n"
                  f">>>>{file_user_input}\n"
                  f"Use names:  {list(file_to_spec_key_map.keys())}")
            exit(1)
        key = file_to_spec_key_map[name]
        default_val = specs_map[key][1]
        try:
            specs_map[key] = int(val)
        except ValueError:
            print(f"Incorrect value in redirected input file:\n"
                  f">>>>{file_user_input}\n"
                  f"Using default value ({default_val}).")
            specs_map[key] = int(default_val)


def get_specs_cache_file(file_to_spec_key_map, specs_map, file_name):
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
                default_val = specs_map[key][1]
                try:
                    specs_map[key] = int(val)
                except ValueError:
                    print(f"Incorrect value in redirected input file:\n"
                          f">>>>{file_user_input}\n"
                          f"Using default value ({default_val}).")
                    specs_map[key] = int(default_val)


    except FileNotFoundError:
        print(f"File {file_name} does not exist. Using default configuration.")


def get_cache_specs(specs_map, file_name=None):
    """
    collect the cache specs in a specs_map. The map enters as:
        key -> (Explanation, default_value)
    and exits the function as:
        key -> value
    """

    file_to_spec_key_map = {
        'line_size_bytes': 'line',
        'associativity': 'asso',
        'cache_size_bytes': 'size',
        'arch_size_bits': 'arch'
    }
    if file_name == None:
        if sys.stdin.isatty():
            get_specs_tty(file_to_spec_key_map, specs_map)
        else:
            get_specs_redirected_input(file_to_spec_key_map, specs_map)
    else:
        get_specs_cache_file(file_to_spec_key_map, specs_map, file_name)



def interactive_mode(specs):
    get_cache_specs(specs)

    # Init Instruction Counter, Instruments, Address Formatter, and Cache
    ic = InstrCounter()
    instr = Instruments(ic, specs['line'])
    af = AddressFormatter(specs['arch'], specs['size'], specs['line'], specs['asso'])
    cache = Cache(specs['arch'], specs['size'], specs['line'], specs['asso'],
                  instr=instr)

    # Print Cache info
    cache.describe_cache()

    max_address = hex(2**cache.arch_size_bits - 1)
    print("\n── Interactive Mode ────────────────────")
    print("Input lines with the following format:\n"
          "    <hex address>,<number of bytes to read>\n"
          "The address must start with '0x'. To exit, type 'exit'.\n"
          "The maximum address accepted (defined by the architecture "
          f"word size {cache.arch_size_bits}) is {max_address}.")
    while True:
        try:
            print()
            input_line = input(">>> address,bytes: ")
            if not sys.stdin.isatty():
                print(input_line)
            if input_line == "exit":
                sys.exit(0)
            addr, n_bytes = input_line.split(',')
            addr =  int(addr.strip(), 16)
            n_bytes = int(n_bytes.strip(), 10)
        except ValueError:
            print(f"Invalid input line: '{input_line}'.")
            continue
        bin_addr_parts, hex_addr_parts = af.format_addr(addr)
        print(f"{bin_addr_parts}\n{hex_addr_parts}")
        cache.access(addr, n_bytes)
        cache.dump()
        ic.step()



def batch_mode(fname, specs):
    get_cache_specs(specs, file_name=os.path.splitext(fname)[0]+'.cache')
    print(f'{specs}')
    print('bye')
    exit(0)

    try:
        with open(fname, 'r') as input_file:
            for input_line in input_file:
                input_line = input_line.strip()
                if input_line == "exit":
                    sys.exit(0)
                addr, n_bytes = input_line.split(',')
                try:
                    addr =  int(addr, 16)
                    n_bytes = int(n_bytes, 10)
                except ValueError:
                    print(f"Invalid input line: '{input_line}'.")
                    exit(1)
                hex_addr, bin_addr = af.format_addr(addr)
                print()
                print(hex_addr+"\n"+bin_addr+f"\nbytes: {n_bytes}")

                cache.access(addr, n_bytes)
                cache.dump()
                ic.step()
    except FileNotFoundError:
        print(f"File not found: {fname}")

def print_help():
    print("MAP Analyzer: A tool to study the cache friendliness of "
          "memory access patterns\n"
          "\n"
          "USAGE:\n"
          f"    {sys.argv[0]} [help|<mem_trace_log>]\n"
          "\n"
          "Interactive Mode\n"
          "  If called without arguments, then run in 'interactive mode'. "
          "This mode reads from the standard input lines with the format:\n"
          "    <hex_address>,<n_bytes>\n"
          "where <hex_address> is the address in hexadecimal that is being "
          "read, and <n_bytes> is the amount of bytes read starting from "
          "that address. To exit, instead of following the described "
          "format, enter 'exit'.\n"
          "\n"
          "Batch Mode\n"
          "If called with an input file <mem_trace_log> as argument, then "
          "run in 'batch mode'. This mode uses that file as input. Its "
          "format is the following:\n"
          "\n"
          "    # METADATA\n"
          "    start-addr   : <0x...>\n"
          "    end-addr     : <0x...>\n"
          "    block-size   : <...>\n"
          "    owner-thread : <...>\n"
          "    slice-size   : <...>\n"
          "    thread-count : <...>\n"
          "    event-count  : <...>\n"
          "    max-qtime    : <...>\n"
          "    \n"
          "    # DATA\n"
          "    time,thread,event,size,offset\n"
          "    <tim>,<thr>,<eve>,<siz>,<off>\n"
          "    <...>\n"
          "\n"
          "These files are normally generated by the mem_tracer pin-tool. "
          "For details about the format check the help in mem_tracer.so. "
          "But the analogous for the interactive mode is:\n"
          "    <start-addr>+<off>,<siz>\n"
          "\n"
          "By Claudio Parra. parraca@uci.edu")


def main():
    """
    Instrumentation:
    - v1 : Line usage             : update on eviction
    - v1 : Still-in-use Evictions : update on eviction (two pass)
    - v1 : Aliased Access         : ??? update on line access
    - v1 : Cache Hits             : update on line access
    - .. : TLB trashing           : update on line access
    """

    # Small cache specs for debugging
    cache_specs = {
        'line': ("Line size [bytes]", 16),
        'asso': ("Associativity [lines]", 2),
        'size': ("Total Cache size [bytes]" , 256),
        'arch': ("Architecture word size [bits]", 16)}

    if len(sys.argv) < 2:
        interactive_mode(cache_specs)
    elif sys.argv[1] == 'help':
        print_help()
    else:
        batch_mode(sys.argv[1], cache_specs)


        
if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        exit(0)
