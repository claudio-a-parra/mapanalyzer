import sys

HPAD = 17
class CacheSpecs:
    # name in file -> name in class
    key_map = {
        'arch_size_bits'  : 'arch',
        'cache_size_bytes': 'cache_size',
        'line_size_bytes' : 'line_size',
        'associativity'   : 'asso',
    }

    def __init__(self, filename=None):
        self.file_path=filename
        self.arch=64
        self.cache_size=32768
        self.line_size=64
        self.asso=8
        self.num_sets = None
        self.bits_set = None
        self.bits_off = None
        self.bits_tag = None

        # terminal UI
        self.ui_cacheparam_hpad = HPAD

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
        return

    def set_derived_values(self):
        if None not in (self.cache_size, self.asso, self.line_size):
            self.num_sets = self.cache_size // (self.asso * self.line_size)

        if None is not self.num_sets:
            self.bits_set = (self.num_sets-1).bit_length()

        if None is not self.line_size:
            self.bits_off = (self.line_size-1).bit_length()

        if None not in (self.arch, self.bits_set, self.bits_off):
            self.bits_tag = self.arch - self.bits_set - self.bits_off

        return

    def __str__(self):
        ret_str = ''
        for i in self.__dict__:
            ret_str += f'{i:11}: {getattr(self, i)}\n'
        return ret_str[:-1]

    def describe(self, ind=''):
        print(f'{ind}{"File":{self.ui_cacheparam_hpad}}: {self.file_path}\n'
              f'{ind}{"Address Size":{self.ui_cacheparam_hpad}}: {self.arch} bits ('
              f'tag:{self.bits_tag} | '
              f'idx:{self.bits_set} | '
              f'off:{self.bits_off})\n'
              f'{ind}{"Cache size":{self.ui_cacheparam_hpad}}: {self.cache_size} bytes\n'
              f'{ind}{"Number of sets":{self.ui_cacheparam_hpad}}: {self.num_sets}\n'
              f'{ind}{"Line size":{self.ui_cacheparam_hpad}}: {self.line_size} bytes\n'
              f'{ind}{"Associativity":{self.ui_cacheparam_hpad}}: {self.asso}-way'
        )
        return


class MapSpecs:
    # headers and name:value pairs.
    # file_name -> (member_name, int_base)
    warning_header = '# WARNING'
    metadata_header = '# METADATA'
    data_header = '# DATA'
    key_map = {
        'start-addr'   : ('start_addr',16),
        'end-addr'     : ('end_addr', 16),
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

        self.ui_mapparam_hpad = HPAD

        # Derived values
        # aligned_start_addr <= start_addr.
        # This value is aligned to the beginning of a block
        self.aligned_start_addr = None
        # the distance (in bytes) between aligned_start_addr and start_addr
        self.left_pad = None
        # the distance (in bytes) between end_addr and aligned_end_addr
        self.right_pad = None
        # end_addr <= aligned_end_addr.
        # This value is aligned to the end of a block
        self.aligned_end_addr = None
        # total number of bytes. Including padding.
        self.num_padded_bytes = None
        # total number of block used by num_padded_bytes.
        self.num_blocks = None
        # the value of the first real tag in the range
        self.first_real_tag = None

        try:
            file = open(self.file_path, 'r')
        except FileNotFoundError:
            print(f"File '{self.file_path}' does not exist.")
            sys.exit(1)


        # Skip to metadata section
        line = file.readline()
        while line.strip() != MapSpecs.metadata_header:
            if line == '':
                print('Error: EOF reached before any metadata.')
                sys.exit(1)
            print(f'    {line.strip()}')
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
                no_comment_line = line.split('#')[0].strip()
                name,val = no_comment_line.split(':')
                name,val = name.strip(),val.strip()
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
        print(f'{ind}{"File":{self.ui_mapparam_hpad}}: {self.file_path}\n'
              f'{ind}{"First Address":{self.ui_mapparam_hpad}}: {hex(self.start_addr)}\n'
              f'{ind}{"Memory Size":{self.ui_mapparam_hpad}}: {self.mem_size} bytes\n'
              f'{ind}{"Maximum Time":{self.ui_mapparam_hpad}}: {self.time_size-1}\n'
              f'{ind}{"Thread Count":{self.ui_mapparam_hpad}}: {self.thread_count}\n'
              f'{ind}{"Event Count":{self.ui_mapparam_hpad}}: {self.event_count}'
        )
        return


class PlotSpecs:
    def __init__(self, width, height, dpi, max_res, format, prefix, include_plots,
                 x_orient, y_ranges, data_X_size, data_Y_size):
        # Image to export
        self.width = width # image width
        self.height = height # image height
        self.dpi = dpi # resolution of the image
        self.format = format # format, usually png or pdf
        self.prefix = prefix # filename prefix
        self.img_border_pad = 0.025 # padding around the image
        self.img_title_vpad = 6 # padding between the plot and its title

        # terminal UI
        self.ui_toolname_hpad = HPAD
        self.ui_plotname_hpad = HPAD

        # Plots to be exported
        self.include = self.init_include_plots(include_plots)

        # Plots Axes
        self.y_ranges = self.init_y_ranges(y_ranges)
        self.max_xtick_count = 11
        self.max_ytick_count = 11
        self.max_map_ytick_count = 11
        self.x_orient = x_orient;

        # Plot Lines (of the curves) [0]:line [1]:area filling
        self.linewidth=0.25
        self.pal_lig=[60,75]
        self.pal_sat=[50,75]
        self.pal_alp=[80,50]

        # Plot grids (matplotlib grids). Used in ticks and plot grids
        # Main axis (either X or Y)
        self.grid_main_width = 0.5
        self.grid_main_style = '-'
        self.grid_main_alpha = 0.2
        # Other axis (either Y or X)
        self.grid_other_width = 0.5
        self.grid_other_style = '--'
        self.grid_other_alpha = 0.2

        # maximum number of bytes or blocks to print the grids in MAP
        self.grid_max_bytes = 128
        self.grid_max_blocks = 48

        # Text boxes
        self.tbox_bg='#FFFFFF88'
        self.tbox_border='#CC000000' # transparent
        self.tbox_font='monospace'
        self.tbox_font_size=9


        # Specific to MAP plot
        self.min_res,self.max_res = self.init_map_resolution(width, height, dpi, max_res)
        self.fade_bytes_alpha=0.1 # fading of bytes out-of-range to complete the block

        # Specific of SIU
        self.dead_line_width = max(0.3,min(3,400*(height/data_Y_size)))

        # Specific of Personality
        self.jump_line_width = max(0.2,min(3,12*(width/data_X_size)))

        return

    def init_map_resolution(self, width, height, dpi, max_res):
        min_res = round(min(0.9*min(width,height)*dpi,210))
        if max_res == 'auto':
            max_res = round(min(0.9*min(width,height)*dpi,2310))
        else:
            try:
                max_res = int(max_res)
            except:
                print(f'Error: max-res must be an integer or \'auto\'')
                exit(1)
        return (min_res,max_res)

    def init_include_plots(self, user_plotcodes_str):
        user_plotcodes = [x.strip() for x in user_plotcodes_str.upper().split(',')]
        including = set(Settings.PLOTCODES.keys())
        if user_plotcodes and 'ALL' not in user_plotcodes:
            including = set()
            for up in user_plotcodes:
                if up in Settings.PLOTCODES:
                    including.add(up)
                else:
                    print(f'Warning: Unknown plotcode "{up}".')
        return including

    def init_y_ranges(self, y_ranges_str):
        user_ranges = [r.strip() for r in y_ranges_str.upper().split(',')]
        ranges = dict()
        if user_ranges and 'FULL' not in user_ranges:
            for ran in user_ranges:
                try:
                    plcod, min_val, max_val = ran.split(':')
                    min_val = float(min_val)
                    max_val = float(max_val)
                except ValueError:
                    print(f'Error: Y-Range with wrong format "{ran}".')
                    exit(1)
                ranges[plcod] = (min_val, max_val)
        return ranges

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
    PLOTCODES = {
        'MAP': 'Graphic MAP',
        'SLD': 'Spatial Locality Degree',
        'TLD': 'Temporal Locality Degree',
        'CMR': 'Cache Miss Ratio',
        'CMMA': 'Cumulative Main Memory Access',
        'CUR': 'Cache Usage Ratio',
        'AD': 'Aliasing Density',
        'SIU': 'Still-in-Use Evictions',
        'BPA': 'Block Personality Adoption'
    }
    verb = False


    @classmethod
    def init_cache(cls, cache_file):
        cls.cache = CacheSpecs(cache_file)
        return

    @classmethod
    def init_map(cls, map_file):
        cls.map = MapSpecs(map_file)

        # compute padding bytes to make the memory chunk block-aligned.
        cls.map.left_pad  = cls.map.start_addr & (cls.cache.line_size-1)
        cls.map.aligned_start_addr = cls.map.start_addr - cls.map.left_pad
        cls.map.right_pad = (cls.cache.line_size-1) - \
            (cls.map.end_addr & (cls.cache.line_size-1))
        cls.map.aligned_end_addr = cls.map.end_addr + cls.map.right_pad
        cls.map.num_padded_bytes = ((cls.map.end_addr+cls.map.right_pad) -
                                    (cls.map.start_addr-cls.map.left_pad) + 1)
        cls.map.num_blocks = cls.map.num_padded_bytes // cls.cache.line_size

        cls.map.first_real_tag = cls.map.start_addr >> (cls.cache.bits_set + cls.cache.bits_off)
        return

    @classmethod
    def init_plot(cls, width, height, dpi, max_res, format, prefix, include_plots,
                  x_orient, y_ranges, data_X_size, data_Y_size):
        cls.plot = PlotSpecs(width, height, dpi, max_res, format, prefix, include_plots,
                             x_orient, y_ranges, data_X_size, data_Y_size)

        return

    @classmethod
    def describe(cls, ind=''):
        ret_str = ''
        my_attrs = ['cache', 'map', 'plot', 'verb']
        for prop in my_attrs:
            print(f'{prop.upper()}')
            getattr(cls, prop).describe(ind='    ')
        return
