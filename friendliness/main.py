#!/usr/bin/env python3
import sys # for command line arguments
import os # for file extension removal
import argparse # to get command line arguments


from address_formatter import log2, AddressFormatter
from instruments import InstrCounter, Instruments
from cache import Cache


def print_help():
    print("MAP Analyzer: A tool to study the cache friendliness of\n"
          "memory access patterns\n"
          "\n"
          "USAGE:\n"
          f"    {sys.argv[0]} [verbose] [< file.input]\n"
          f"    {sys.argv[0]} help\n"
          "\n"
          "CACHE CONFIG FILE:"
          "  The Analyzer expects a file called 'cache.conf' with the\n"
          "  following format:\n"
          "\n"
          "    line_size_bytes  : <value>\n"
          "    associativity    : <value>\n"
          "    cache_size_bytes : <value>\n"
          "    arch_size_bits   : <value>\n"
          "\n"
          "MODES:\n"
          "  Interactive Mode:\n"
          "    When called without arguments. In this mode, you give\n"
          "    lines with the format:\n"
          "        <hex_address>,<n_bytes>\n"
          "    where <hex_address> is the address in hexadecimal that\n"
          "    is being accessed, and <n_bytes> is the amount of bytes\n"
          "    accessed starting from that address.\n"
          "    To exit, input 'exit'.\n"
          "\n"
          "  Batch Mode:\n"
          "    If you redirect the input with '< file.input', then pretty\n"
          "    much the same applies, but automatically. So the file\n"
          "    should look like this:\n"
          "\n"
          "        # comment\n"
          "        <hex_address>,<n_bytes>\n"
          "        <hex_address>,<n_bytes> # comment\n"
          "        ...\n"
          "        <hex_address> , <n_bytes> # spaces are ok\n"
          "        exit # optional\n"
          "\n"
          "    You could omit the last 'exit' line, or insert comments by\n"
          "    starting the line with '#'. Empty lines are ignored. You\n"
          "    can also put comments at the right of any regular line.\n"
          "\n"
          "NOTE:\n"
          "  All addresses, set indices, line offsets, and line tags are\n"
          "  in hexadecimal unless explicitly indicated otherwise.\n"
          "  Clocks and other numbers are decimal.\n"
          "\n"
          "By Claudio A. Parra.\n"
          "parraca@uci.edu")



def get_input_filename():
    # Check if stdin is connected to a file or being redirected
    if sys.stdin.isatty():
        return ''  # Not redirected
    # Get the file descriptor of stdin
    input_fd = sys.stdin.fileno()
    # Get the file name associated with the file descriptor
    input_filename = ''
    try:
        input_filename = os.readlink(f"/proc/{os.getpid()}/fd/{input_fd}")
    except (OSError, AttributeError):
        pass
    return input_filename


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


def parse_line(input_line, input_history, af, verb=False):
    # If history was given, then add line to it
    if input_history != None:
        input_history.append(input_line)
    # if reading from file, inform the user what's going on
    if not sys.stdin.isatty() and verb:
        print(">>> "+input_line)
    # nothing to do if empty ore just a comment
    if input_line == '' or input_line[0] == '#':
        return None
    # remove trailing comments
    input_line = input_line.split('#')[0].strip()
    # if the user wants to exit
    if input_line == 'exit':
        return 'exit'
    # split line. If redirecting input, and there is an error, treat it
    # as irrecoverable.
    try:
        addr, n_bytes = input_line.split(',')
        addr, n_bytes = addr.strip(), n_bytes.strip()
    except ValueError:
        print(f"ERROR: Invalid input line: '{input_line}'")
        if not sys.stdin.isatty():
            sys.exit(1)
        return None
    # add '0x' to address if it is missing
    if addr[:2] != '0x':
        addr = '0x'+addr
    # parse to integer
    try:
        addr =  int(addr, 16)
        n_bytes = int(n_bytes, 10)
    except ValueError:
        print(f"ERROR: Invalid input line: '{input_line}'.")
        if not sys.stdin.isatty():
            sys.exit(1)
        return None
    # pretty print address
    if verb:
        bin_addr_parts, hex_addr_parts = af.format_addr(addr)
        print(f"{bin_addr_parts}\n{hex_addr_parts}")
    return (addr, n_bytes)



def run_simulation(specs, verb=False):
    # Init Instruction Counter, Instruments, Address Formatter, and Cache
    ic = InstrCounter()
    instr = Instruments(ic, specs, verb=verb)
    af = AddressFormatter(specs)
    cache = Cache(specs, instr=instr)

    # Print Header info
    if verb:
        cache.describe_cache()
        print("\n── Interactive Mode ────────────────────")
        print("Input lines with the following format:\n"
              "    <hex address>,<number of bytes to read>\n"
              "The address must start with '0x'. To exit, type 'exit'.\n"
              "The maximum address accepted (defined by the architecture "
              f"word size {cache.arch_size_bits}) is:\n"
              f"    {hex(2**cache.arch_size_bits - 1)}.")

    # history of user input. Used to do a silent second pass for the
    # instruments that need two passes.
    input_history = []

    # First Pass
    if verb:
        print('\n── FIRST PASS ─────────────────────────')
    while True:
        # get line from human (tty) or from file. Exit if EOF
        if sys.stdin.isatty():
            input_line = input(">>> ")
        else:
            try:
                input_line = input()
            except:
                input_line = 'exit'
        # parse line to decide the action to take
        input_line = parse_line(input_line, input_history, af, verb)
        if input_line == None:
            continue
        if input_line == 'exit':
            break
        addr, n_bytes = input_line
        # move instruction counter perform memory access
        ic.step()
        cache.access(addr, n_bytes)
        if verb:
            cache.dump()
            print()

    # flush cache so that info about last blocks is gathered
    if verb:
        print('Flush Cache')
    ic.step()
    cache.flush()

    # Second Pass (from the recorded history) for instruments that
    # need two passes, like still-in-use evictions.
    if verb:
        print('\n\n── SECOND PASS ─────────────────────────')
    ic.reset() # reset instruction counter
    instr.prepare_for_second_pass() # prepare instruments for second pass.
    cache.reset_clock()
    for input_line in input_history:
        if verb:
            print(f">>> {input_line}")
        # parse line to decide the action to take
        input_line = parse_line(input_line, None, af, verb)
        if input_line == None:
            continue
        elif input_line == 'exit':
            break
        addr, n_bytes = input_line
        # move instruction counter and perform memory access
        ic.step()
        cache.access(addr, n_bytes)
        if verb:
            cache.dump()
            print()

    # flush cache so that info about last blocks is gathered
    if verb:
        print('Flush Cache')
    ic.step()
    cache.flush()

    # return instruments to later plot results.
    return instr



def main():
    # define command line arguments
    args = argparse.ArgumentParser()

    # Default cache configuration. Small for debugging.
    cache_specs = {
        'line': ("Line size [bytes]", 16),
        'asso': ("Associativity [lines]", 2),
        'size': ("Total Cache size [bytes]" , 256),
        'arch': ("Architecture word size [bits]", 16)}

    # define verbosity and print help if requested
    verb = False
    if len(sys.argv) > 1:
        if sys.argv[1] == 'help':
            print_help()
            sys.exit(0)
        if sys.argv[1] == 'verbose':
            verb = True


    print("Reading cache.conf...")
    get_cache_specs_from_file(cache_specs, 'cache.conf')

    print('Running...')
    instruments = run_simulation(cache_specs, verb=verb)

    # build master log with the measurements of all instruments.
    print('Building Log...')
    instruments.build_master_log()
    # plot the data using a sliding window of 3 instructions.
    window = 5000
    print(f'Plotting Results (win={window})...')
    fname = get_input_filename()
    fname,_ = os.path.splitext(fname)
    instruments.plot_data(fname, win=window)
    print('Done.')

        
if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        exit(0)
