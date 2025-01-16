import sys

from mapanalyzer.settings import Settings as st

class __Record:
    """One record from the map file."""
    def __init__(self, time, thread, event, size, addr):
        # almost all members are integers.
        try:
            self.time = int(time)
            self.thread = int(thread)
            self.event = event
            self.size = int(size)
            self.addr = int(addr)
        except:
            print('Incorrect values to create __MemRecord:\n'
                  f'    time  : {time}\n'
                  f'    thread: {thread}\n'
                  f'    event : {event}\n'
                  f'    size  : {size}\n'
                  f'    addr  : {addr}')
            sys.exit(1)
        return

    def __str__(self):
        return (f'tim:{self.time}, thr:{self.thread}, '
                f'eve:{self.event}, addr:{self.addr}, '
                f'siz:{self.size}')


class MapDataReader:
    """iterates over the map file, reading one record at the time."""
    def __init__(self, map_file_path):
        self.file_path = map_file_path
        self.file = None

        # Open file
        try:
            self.file = open(self.file_path, 'r')
        except FileNotFoundError:
            print(f"File '{self.file_path}' does not exist.")
            sys.exit(1)

        # Print all Errors and Warnings (these sections are always before
        # metadata and data)
        line = self.file.readline()
        while line.strip() not in (st.Map.metadata_header, st.Map.data_header):
            # end of file
            if line == '':
                print('Error: EOF reached before any data.')
                sys.exit(1)
            line = line.strip()
            if line != '':
                print('[!] '+line)
            line = self.file.readline()

        self.__go_to_section(st.Map.data_header)
        return


    def __go_to_section(self, header):
        if self.file.closed:
            self.file = open(self.file_path, 'r')
        self.file.seek(0)
        # seek the first 50 lines for the given section.
        found = False
        lines_to_search = 50
        for l in range(lines_to_search):
            line = self.file.readline().strip()
            if line == header:
                found = True
                break
        # Error if section not found
        if not found:
            print(f'Error: Section "{header}" not found in the first '
                  f'{lines_to_search} lines of {self.file_path}!!')
            sys.exit(1)
        return

    def __iter__(self):
        self.__go_to_section(st.Map.data_header)
        # consume the first line after the header, which
        # contains the columns names.
        self.file.readline()
        return self

    def __next__(self):
        line = ''
        # read lines until a useful one appears
        while True:
            line = self.file.readline()
            # found EOF
            if line == '':
                self.file.close()
                raise StopIteration

            line = line.strip()
            # empty line
            if line == '':
                continue
            # comment line
            if line[0] == '#':
                continue
            # remove trailing comment
            if '#' in line:
                line = line.split('#')[0].strip()
            break

        line = line.strip()
        try:
            time,thr,ev,size,off = line.split(',')
        except:
            print('The input line does not have the correct number of '
                  'fields:\n'
                  f'>>>> {line}')
            sys.exit(1)
        try:
            off = int(off)
        except:
            print('Incorrect value for offset:\n'
                  f'    {off}')
            sys.exit(1)

        # Transform the (relative) offset to (absolute) address.
        # I was probably drunk when I thought this... I am pretty sure
        # I am adding and subtracting the same shit somewhere else...
        addr = st.Map.aligned_start_addr + st.Map.left_pad + off
        return __Record(time, thr, ev, size, addr)
