#!/usr/bin/env python3
import sys
class MemAccess:
    def __init__(self, time, thread, event, size, addr):
        self.time = time
        self.thread = thread
        self.event = event
        self.size = size
        self.addr = addr
        return


    def __str__(self):
        return (f'tim:{self.time}, thr:{self.thread}, '
                f'eve:{self.event}, addr:{self.addr}, '
                f'siz:{self.size}')


class MemAP:
    def __init__(self, file_path):
        self.file_path = file_path
        self.base_addr = -1
        self.block_size = -1
        self.thread_count = -1
        self.event_count = -1
        self.time_size = -1

        # Open file
        try:
            self.file = open(self.file_path, 'r')
        except FileNotFoundError:
            print(f"File '{self.file_path}' does not exist.")
            sys.exit(1)

        warning_section = '# WARNING'
        metadata_section = '# METADATA'
        data_section = '# DATA'
        line = self.file.readline()

        # Print all Warnings.
        while line.strip() not in (metadata_section,
                                   data_section):
            if line == '':
                print('Error: EOF reached before any data.')
                sys.exit(1)
            line = line.strip()
            if line != '':
                print('[!] '+line)
            line = self.file.readline()

        # Read Metadata
        while line.strip() not in (data_section,):
            if line == '':
                print('Error: EOF reached before any data.')
                sys.exit(1)
            line = line.strip()
            if line == '' or line[0] == '#':
                line = self.file.readline()
                continue
            try:
                name,value = line.split(':')
                name,value = name.strip(),value.strip()
            except:
                print(f"Error: File {self.file_path}: "
                      "Malformed line in Metadata Section:\n"
                      f"    '{line}'")
                sys.exit(1)
            try:
                if name == 'start-addr':
                    self.base_addr = int(value, 16)
                elif name == 'block-size':
                    self.block_size = int(value, 10)
                elif name == 'thread-count':
                    self.thread_count = int(value, 10)
                elif name == 'event-count':
                    self.event_count = int(value, 10)
                elif name == 'max-qtime':
                    self.time_size = int(value, 10) + 1
            except ValueError:
                print(f"Invalid value for '{name}' in "
                      "Metadata Section.\n"
                      f"    {line}")
                sys.exit(1)
            line = self.file.readline()

        if self.base_addr == -1 or \
           self.block_size == -1 or \
           self.thread_count == -1 or \
           self.event_count == -1 or \
           self.time_size == -1:
            print(f'Error: Incomplete Metadata in {self.file_path}')
            sys.exit(1)

        self.rewind()
        return

    def rewind(self):
        if self.file.closed:
            self.file = open(self.file_path, 'r')
        self.file.seek(0)
        # seek the first 50 lines for the '# DATA' section.
        found = False
        data_section = '# DATA'
        for l in range(50):
            line = self.file.readline().strip()
            if line == data_section:
                self.file.readline() # consume columns names line
                found = True
                break
        # Error if section not found
        if not found:
            print(f"Error: Section '{data_section}' not found!!")
            sys.exit(1)
        return

    def __iter__(self):
        self.rewind()
        return self

    def __next__(self):
        line = self.file.readline()
        if line == '': #EOF
            self.file.close()
            raise StopIteration
        line = line.strip()
        try:
            time,thr,ev,size,off = line.split(',')
        except ValueError:
            print('The input line does not have all the fields:\n'
                  f'    {line}')
            sys.exit(1)
        try:
            time = int(time)
            thr = int(thr)
            size = int(size)
            addr = self.base_addr + int(off)
        except:
            print('Error while parsing input line:\n'
                  f'    {line}')
            sys.exit(1)
        if ev in ('Tc','Td'):
            addr = 0
        return MemAccess(time, thr, ev, size, addr)
