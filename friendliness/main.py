#!/usr/bin/env python3
import sys
from address_formatter import log2, AddressFormatter
from instruments import InstrCounter, Instruments
from cache import Cache


def main():
    """
    Instrumentation:
    - v1 : Line usage             : update on eviction
    - v1 : Still-in-use Evictions : update on eviction (two pass)
    - v1 : Aliased Access         : ??? update on line access
    - v1 : Cache Hits             : update on line access
    - .. : TLB trashing           : update on line access
    """
    # define interaction mode
    print("MAP Analyzer: A tool to study the cache friendliness of a Memory Access Pattern.")


    # small specs for debugging
    arch_size_bits   = 5 + 3 + 2
    cache_size_bytes = 64
    line_size_bytes  = 4
    associativity    = 2

    # initialize instruments and cache
    ic = InstrCounter()
    instr = Instruments(ic, line_size_bytes)
    cache = Cache(arch_size_bits=arch_size_bits,
                  cache_size_bytes=cache_size_bytes,
                  line_size_bytes=line_size_bytes,
                  associativity=associativity,
                  instr=instr)
    af = AddressFormatter(arch_size_bits, cache_size_bytes,
                          line_size_bytes, associativity)

    # go to interaction mode
    if len(sys.argv) < 2:
        print("(interactive mode)")
        interactive_mode(ic, cache, af)
    else:
        print("(batch mode)")
        batch_mode(sys.argv[1], ic, cache, af)

def interactive_mode(ic, cache, af):
    print("Input lines with the following format:\n"
          "    <hex address>,<number of bytes>\n"
          "Make sure the hex addresses start with '0x'.\n"
          "To exit type 'exit'.")
    while True:
        try:
            print()
            input_line = input("addr,bytes: ")
            if input_line == "exit":
                sys.exit(0)
            addr, n_bytes = input_line.split(',')
            addr =  int(addr.strip(), 16)
            n_bytes = int(n_bytes.strip(), 10)
        except ValueError:
            print(f"Invalid input line: '{input_line}'.")
            exit(1)
        hex_addr, bin_addr = af.format_addr(addr)
        print(hex_addr+"\n"+bin_addr)
        cache.access(addr, n_bytes)
        cache.dump()
        ic.step()

def batch_mode(fname, ic, cache, af):
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







        
if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        exit(0)
