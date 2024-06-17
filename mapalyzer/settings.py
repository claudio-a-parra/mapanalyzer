import sys

def log2(x):
    return x.bit_length() - 1


class CacheSpecs:
    # name in file -> name in class
    key_map = {
        'arch_size_bits'  : 'arch',
        'cache_size_bytes': 'cache_size',
        'line_size_bytes' : 'line_size',
        'associativity'   : 'asso',
        'fetch_cost'      : 'fetch',
        'writeback_cost'  : 'write',
    }

    def __init__(self, filename=None):
        self.file_path=filename
        self.arch=64
        self.cache_size=32768
        self.line_size=64
        self.asso=8
        self.fetch=1
        self.write=2
        self.num_sets = None
        self.bits_set = None
        self.bits_off = None
        self.bits_tag = None
        if filename is None:
            self.set_derived_values()
            return

        try:
            with open(filename, 'r') as cache_config_file:
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
                        print(f'[!] File {filename}: Invalid line, ignoring:\n'
                              '    >>>>{line}')
                        continue
                    name,val = key_val_arr[0].strip(), key_val_arr[1].strip()
                    self.set_value(name, val)
        except FileNotFoundError:
            print(f"[!] File {filename} does not exist. Using default "
                  "configuration.")
        self.set_derived_values()
        return

    def set_derived_values(self):
        if None not in (self.cache_size, self.asso, self.line_size):
            self.num_sets = self.cache_size // (self.asso * self.line_size)

        if None is not self.num_sets:
            self.bits_set = log2(self.num_sets)

        if None is not self.line_size:
            self.bits_off = log2(self.line_size)

        if None not in (self.arch, self.bits_set, self.bits_off):
            self.bits_tag = self.arch - self.bits_set - self.bits_off
        return

    def set_value(self, name, val):
        if name not in CacheSpecs.key_map:
            print(f'[!] Invalid name {name}. Ignoring line.')
            return
        try:
            int_val = int(val)
        except ValueError as e:
            print(f'[!] Invalid value ({val}) given to name "{name}". '
                  'It must be integer. Ignoring.')
            return
        setattr(self, CacheSpecs.key_map[name], int_val)
        self.set_derived_values()
        return

    def __str__(self):
        ret_str = ''
        for i in self.__dict__:
            ret_str += f'{i:11}: {getattr(self, i)}\n'
        return ret_str[:-1]

    def describe(self, ind=''):
        print(f'{ind}File                 : {self.file_path}\n'
              f'{ind}Address size         : {self.arch} bits ('
              f'tag:{self.bits_tag} | '
              f'idx:{self.bits_set} | '
              f'off:{self.bits_off})\n'
              f'{ind}Cache size           : {self.cache_size} bytes\n'
              f'{ind}Number of sets       : {self.num_sets}\n'
              f'{ind}Line size            : {self.line_size} bytes\n'
              f'{ind}Associativity        : {self.asso}-way\n'
              f'{ind}Main Mem. Fetch cost : {self.fetch} units\n'
              f'{ind}Main Mem. Write cost : {self.write} units'
        )
        return


class MapSpecs:
    # headers and name:value pairs.
    # file_name -> (member_name, int_base)
    warning_header = '# WARNING'
    metadata_header = '# METADATA'
    data_header = '# DATA'
    key_map = {
        'start-addr'   : ('start_addr',10),
        'end-addr'     : ('end_addr', 10),
        'thread-count' : ('thread_count',10),
        'event-count'  : ('event_count',10),
        'block-size'   : ('mem_size',10),
        'max-time'     : ('time_size',10), # this one is adapted
    }

    def __init__(self, map_filepath):
        if map_filepath is None:
            print(f"You must specify a map file.")
            sys.exit(1)

        self.file_path = map_filepath
        self.start_addr = None
        self.end_addr = None
        self.mem_size = None
        self.time_size = None
        self.thread_count = None
        self.event_count = None

        # Derived values
        # the closest beginning of block at the left of start_addr
        self.aligned_start_addr = None
        # the distance between aligned_start_addr and start_addr
        self.left_pad = None
        # the distance between end_addr and aligned_end_addr
        self.right_pad = None
        # the closest end of block at the right of end_addr
        self.aligned_end_addr = None
        # number of bytes included the ones used to complete the blocks at start and end.
        self.num_padded_bytes = None
        # number of blocks used by num_padded_bytes
        self.num_blocks = None

        try:
            file = open(self.file_path, 'r')
        except FileNotFoundError:
            print(f"File '{self.file_path}' does not exist.")
            sys.exit(1)


        # Skip to metadata section
        line = file.readline()
        while line.strip() != MapSpecs.metadata_header:
            print(f'line: |{line}|')
            if line == '':
                print('Error: EOF reached before any metadata.')
                sys.exit(1)
            line = file.readline()

        # Read Metadata
        while line.strip() not in (MapSpecs.warning_header, MapSpecs.data_header):
            if line == '':
                print('Error: EOF reached before any data.')
                sys.exit(1)
            # skip empty lines or comments
            line = line.strip()
            if line == '' or line[0] == '#':
                line = file.readline()
                continue
            # parse name:val
            try:
                name,val = line.split(':')
                name,val = name.strip(),val.strip()
                val = val.split('#')[0].strip()
            except:
                print(f"Error: File {self.file_path}: "
                      "Malformed line in Metadata Section:\n"
                      f">>>>'{line}'")
                sys.exit(1)
            # check for recognized pair
            if name in MapSpecs.key_map:
                try:
                    int_val = int(val, MapSpecs.key_map[name][1])
                except ValueError:
                    print(f"Invalid value for '{name}' in "
                          "Metadata Section.\n"
                          f">>>>{line}")
                    sys.exit(1)
                setattr(self, MapSpecs.key_map[name][0], int_val)

            # get next line
            line = file.readline()

        # if any value is missing, error.
        if None in (self.start_addr, self.end_addr, self.mem_size, self.thread_count,
                    self.event_count, self.time_size):
            print(f'Error: Incomplete Metadata in {self.file_path}.')
            print(self)
            sys.exit(1)

        # error if start_addr, mem_size and end_addr are incoherent.
        if self.end_addr - self.start_addr + 1 != self.mem_size:
            print(f'Error: The size, start and end address of the memory '
                  f'declared is incoherent in {self.file_path}.')
            print(self)
            sys.exit(1)

        # convert max-time index (what comes in the file) to time_size
        self.time_size +=1

        file.close()
        return

    def __str__(self):
        ret_str = ''
        for prop in self.__dict__:
            if getattr(self, prop) is not None:
                ret_str += f'{prop:19}= {getattr(self, prop)}\n'
        return ret_str[:-1]

    def describe(self, ind=''):
        print(f'{ind}File          : {self.file_path}\n'
              f'{ind}First Address : {hex(self.start_addr)}\n'
              f'{ind}Memory size   : {self.mem_size} bytes\n'
              f'{ind}Maximum time  : {self.time_size-1}\n'
              f'{ind}Thread count  : {self.thread_count}\n'
              f'{ind}Events count  : {self.event_count}'
        )
        return


class PlotSpecs:
    def __init__(self, width=8, height=4, res=1000, dpi=200, format='png', prefix='exp'):
        self.width = width
        self.height = height
        self.res = res
        self.dpi = 600 #dpi
        print(f'[!] DBG: dpi hardcoded to {self.dpi}')
        self.format = format
        self.prefix = prefix
        self.max_xtick_count = 20
        self.max_ytick_count = 11
        self.max_map_ytick_count = 11
        self.img_border_pad = 0.05
        self.img_title_vpad = 6
        self.ui_title_hpad = 31
        self.ui_name_hpad = 23

        # plot line settings
        self.linewidth=1.2
        self.pal_lig=[60,75]
        self.pal_sat=[50,75]
        self.pal_alp=[100,30]

        # plot grids settings
        self.grid_main_width = 0.5
        self.grid_main_style = '-'
        self.grid_main_alpha = 0.2
        self.grid_other_width = 0.5
        self.grid_other_style = '--'
        self.grid_other_alpha = 0
        self.grid_max_bytes = 96
        self.grid_max_blocks = 48

        self.fade_bytes_alpha=0.1
        return

    def __str__(self):
        ret_str = ''
        for prop in self.__dict__:
            ret_str += f'{prop:7}: {getattr(self, prop)}\n'
        return ret_str[:-1]

    def describe(self, ind=''):
        self_str = str(self)
        self_str = self_str.split('\n')
        for line in self_str:
            print(f'{ind}{line}')
        return


class Settings:
    cache:CacheSpecs = None
    map:MapSpecs = None
    plot:PlotSpecs = None
    verb = False


    @classmethod
    def init_cache(cls, cache_file):
        cls.cache = CacheSpecs(cache_file)
        return

    @classmethod
    def init_map(cls, map_file):
        cls.map = MapSpecs(map_file)
        return

    @classmethod
    def init_map_derived(cls):
        # compute the shift of addresses to align to blocks.
        cls.map.left_pad  = cls.map.start_addr & (cls.cache.line_size-1)
        cls.map.aligned_start_addr = cls.map.start_addr - cls.map.left_pad
        cls.map.right_pad = (cls.cache.line_size-1) - \
            (cls.map.end_addr & (cls.cache.line_size-1))
        cls.map.aligned_end_addr = cls.map.end_addr + cls.map.right_pad
        cls.map.num_padded_bytes = ((cls.map.end_addr+cls.map.right_pad) -
                                    (cls.map.start_addr-cls.map.left_pad) + 1)
        cls.map.num_blocks = cls.map.num_padded_bytes // cls.cache.line_size
        # print(cls.map)
        # exit(0)
        return

    @classmethod
    def init_plot(cls, plot_metadata):
        cls.plot = plot_metadata
        return

    @classmethod
    def describe(cls, ind=''):
        ret_str = ''
        my_attrs = ['cache', 'map', 'plot', 'verb']
        for prop in my_attrs:
            print(f'{prop.upper()}')
            getattr(cls, prop).describe(ind='    ')
        return
