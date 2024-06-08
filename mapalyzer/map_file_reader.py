import sys

from settings import Settings as st

class MemAccess:
    """One register from the map file."""
    def __init__(self, time, thread, event, size, addr):
        # all members are integers.
        try:
            self.time = int(time)
            self.thread = int(thread)
            self.event = event
            self.size = int(size)
            self.addr = int(addr)
        except:
            print('Incorrect values to create MemAccess:\n'
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


class MapFileReader:
    """iterates over the map file, reading one register at the time."""
    def __init__(self):
        # Open file
        try:
            self.file = open(st.map.file_path, 'r')
        except FileNotFoundError:
            print(f"File '{self.file_path}' does not exist.")
            sys.exit(1)

        # Print all Warnings.
        line = self.file.readline()
        while line.strip() not in (st.map.metadata_header, st.map.data_header):
            if line == '':
                print('Error: EOF reached before any data.')
                sys.exit(1)
            line = line.strip()
            if line != '':
                print('    [!] '+line)
            line = self.file.readline()

        self.go_to_section(st.map.data_header)
        return


    def go_to_section(self, header):
        if self.file.closed:
            self.file = open(self.file_path, 'r')
        self.file.seek(0)
        # seek the first 50 lines for the '# DATA' section.
        found = False
        for l in range(50):
            line = self.file.readline().strip()
            if line == header:
                found = True
                break
        # Error if section not found
        if not found:
            print(f"Error: Section '{header}' not found!!")
            sys.exit(1)
        return

    def __iter__(self):
        self.go_to_section(st.map.data_header)
        self.file.readline() # consume columns names line

        return self

    def __next__(self):
        line = ''
        # ignore empty lines or comment lines
        while True:
            line = self.file.readline()
            if line == '': #EOF
                self.file.close()
                raise StopIteration
            line = line.strip()
            if line == '':
                continue
            if line[0] == '#':
                continue
            if '#' in line:
                line = line.split('#')[0].strip()
            break

        line = line.strip()
        try:
            time,thr,ev,size,off = line.split(',')
        except ValueError:
            print('The input line does not have all the correct number of '
                  'fields:\n'
                  f'    {line}')
            sys.exit(1)
        try:
            off = int(off)
        except:
            print('Incorrect value for offset:\n'
                  f'    {off}')
            sys.exit(1)
        addr = st.map.aligned_start_addr + st.map.left_pad + off
        return MemAccess(time, thr, ev, size, addr)
