import sys, os, json

HPAD = 17

class Settings:
    mode = 'sim-plot'

    @classmethod
    def set_mode(cls, args):
        if args.mode is not None:
            cls.mode = args.mode
        return

    @classmethod
    def describe(cls, ind=''):
        print('SETTINGS')
        ret_str = ''
        my_attrs = ['Plot', 'Cache', 'Map']
        for prop in my_attrs:
            print(f'{prop.upper()}')
            getattr(cls, prop).describe(ind='    ')
        return

    class Cache:
        ############################################################
        #### CONSTANT VALUES
        # name in file -> name in class
        key_map = {
            'arch_size_bits'  : 'arch',
            'cache_size_bytes': 'cache_size',
            'line_size_bytes' : 'line_size',
            'associativity'   : 'asso',
        }
        # terminal UI
        ui_cacheparam_hpad = HPAD

        ############################################################
        #### BASIC VALUES
        file_path = None
        arch = 64
        cache_size = 32768
        line_size = 64
        asso = 8

        initialized = False

        ############################################################
        #### DERIVED VALUES
        num_sets = None
        bits_set = None
        bits_off = None
        bits_tag = None

        @classmethod
        def from_file(cls, filename=None):
            # if no file, compute derived values from default basics
            if filename is None:
                print('[!] No cache file given. Using default '
                      'configuration.')
            elif not os.path.isfile(filename):
                print(f'[!] File {filename} does not exist. Using default '
                      'configuration.')

            # If cache file exists, then use it.
            else:
                with open(filename, 'r') as cache_config_file:
                    name_vals = {}
                    for line in cache_config_file:
                        # skip empty or comment
                        if line == '' or line[0] == '#':
                            continue
                        # get rid of trailing comments
                        content_comment = line.split('#')
                        line = content_comment[0]

                        # parse <name>:<value>
                        key_val_arr = [x.strip() for x in line.split(':')]

                        # ignore lines not like <name>:<value>
                        if len(key_val_arr) != 2:
                            print(f'[!] {filename}: Ignoring invalid line\n'
                                  f'    >>>>{line}')
                            continue
                        name,val = key_val_arr[0], key_val_arr[1]

                        # ignore invalid property names
                        if name not in cls.key_map:
                            print(f'[!] Invalid property. Ignoring it:\n'
                                  f'    >>>>{line}')
                            continue

                        # ignore invalid values
                        try:
                            val = int(val)
                        except Exception:
                            print(f'[!] Invalid value. Ignoring it:\n'
                                  f'    >>>>{line}')
                            continue

                        name_vals[name] = val

                    # error if cache file was given but it is incomplete.
                    if len(cls.key_map) != len(name_vals):
                        print(f'[!] Cache file given does not have all '
                              'necessary properties.\n'
                              '    See mapanalyzer --help.')
                        exit(1)

                    # apply values
                    cls.file_path = filename
                    for key,val in name_vals.items():
                        setattr(cls, cls.key_map[key], val)

            # compute derived values and address formatter
            cls.__init_derived_values()
            cls.initialized = True
            Settings.AddrFmt.init()
            return

        @classmethod
        def from_dict(cls, cache_dict):
            # load data from the cache section of the metric file
            cls.__dict_to_basics(cache_dict)

            # compute derived values
            cls.__init_derived_values()
            cls.initialized = True
            Settings.AddrFmt.init()
            return

        @classmethod
        def __init_derived_values(cls):
            cls.num_sets = cls.cache_size // (cls.asso * cls.line_size)
            cls.bits_set = (cls.num_sets-1).bit_length()
            cls.bits_off = (cls.line_size-1).bit_length()
            cls.bits_tag = cls.arch - cls.bits_set - cls.bits_off
            return

        @classmethod
        def __dict_to_basics(cls, cache_dict):
            cls.line_size = cache_dict['line_size_bytes']
            cls.asso = cache_dict['associativity']
            cls.cache_size = cache_dict['cache_size_bytes']
            cls.arch = cache_dict['arch_size_bits']
            return

        @classmethod
        def basics_to_dict(cls):
            if not cls.initialized:
                raise Exception("Cache not initialized. Cannot export.")
            return {
                'line_size_bytes': cls.line_size,
                'associativity': cls.asso,
                'cache_size_bytes': cls.cache_size,
                'arch_size_bits': cls.arch
            }

        @classmethod
        def __str__(cls):
            ret_str = ''
            for i in cls.__dict__:
                ret_str += f'{i:11}: {getattr(cls, i)}\n'
            return ret_str[:-1]

        @classmethod
        def describe(cls, ind=''):
            i = '    '
            if cls.file_path is None:
                fname = ' (Default values)'
            else:
                fname = f' ({cls.file_path})'
            print(f'{ind}CACHE PARAMETERS{fname}')
            print(f'{ind}{i}{"Address Size":{cls.ui_cacheparam_hpad}}: '
                  f'{cls.arch} bits ('
                  f'tag:{cls.bits_tag} | '
                  f'idx:{cls.bits_set} | '
                  f'off:{cls.bits_off})\n'
                  f'{ind}{i}{"Cache size":{cls.ui_cacheparam_hpad}}: '
                  f'{cls.cache_size} bytes\n'
                  f'{ind}{i}{"Number of sets":{cls.ui_cacheparam_hpad}}:'
                  f' {cls.num_sets}\n'
                  f'{ind}{i}{"Line size":{cls.ui_cacheparam_hpad}}: '
                  f'{cls.line_size} bytes\n'
                  f'{ind}{i}{"Associativity":{cls.ui_cacheparam_hpad}}: '
                  f'{cls.asso}-way'
            )
            return


    class AddrFmt:
        ############################################################
        #### BASIC VALUES
        bits_tag = None
        bits_set = None
        bits_off = None
        max_tag = None
        max_index = None
        max_offset = None

        @classmethod
        def init(cls):
            """Initialize values based on the Cache config.
            This function should only be called by the cache after being
            initialized itself."""
            if not Settings.Cache.initialized:
                raise Exception('Cannot init AddrFmt if Cache is not '
                                'initialized')
            cls.bits_tag = Settings.Cache.bits_tag
            cls.bits_set = Settings.Cache.bits_set
            cls.bits_off = Settings.Cache.bits_off
            cls.max_tag = 2**cls.bits_tag - 1
            cls.max_index = 2**cls.bits_set - 1
            cls.max_offset = 2**cls.bits_off - 1

        @classmethod
        def bin(cls, address):
            """Shows the split binary form of an address"""
            tag, index, offset = cls.split(address)
            padded_bin = \
                "|T:"  + cls.__pad(tag,    2, cls.max_tag)  +\
                "| I:" + cls.__pad(index,  2, cls.max_index) +\
                "| O:" + cls.__pad(offset, 2, cls.max_offset)+\
                "|"
            return padded_bin

        @classmethod
        def hex(cls, address):
            """Shows the split hexadecimal form of an address"""
            tag, index, offset = cls.split(address)
            padded_hex = \
                "|T:"  + cls.__pad(tag,    16, cls.max_tag)  +\
                "| I:" + cls.__pad(index,  16, cls.max_index) +\
                "| O:" + cls.__pad(offset, 16, cls.max_offset)+\
                "|"
            return padded_hex

        @classmethod
        def split(cls, address):
            """Splits an address into its tag, index, and offset parts."""
            # print(f"split: addr:{address}")
            offset_mask = (1 << cls.bits_off) - 1
            offset = address & offset_mask
            index_mask = (1 << cls.bits_set) - 1
            index = (address >> cls.bits_off) & index_mask
            tag = address >> (cls.bits_set + cls.bits_off)
            return tag, index, offset

        @classmethod
        def __pad(cls, number, base, max_val):
            """pad numbers so that they occupy the length of max_val
            in a given numeric base"""
            group_width = 4
            if base == 2:
                conv_number = bin(number)[2:]
                max_num_width = max_val.bit_length()
                group_digits = 4
            elif base == 16:
                conv_number = hex(number)[2:]
                max_num_width = (max_val.bit_length() + 3) // 4
                group_digits = 1
            else:
                raise ValueError("Unexpected base. use either 2 or 16")
            padded_conv_number = conv_number.zfill(max_num_width)
            rev_pcn = padded_conv_number[::-1]
            rev_ret = ""
            for i in range(0, len(padded_conv_number), group_digits):
                r_digits = rev_pcn[i:i+group_digits]
                r_digits = r_digits.ljust(group_width)
                rev_ret += r_digits + " "

                #digits = padded_conv_number[i:i+group_digits]
                #digits = digits.rjust(group_width)
                #ret += " " + digits
            return rev_ret[::-1][1:]

        @classmethod
        def describe(cls, ind=''):
            i = '    '
            print(f'{ind}ADDR FORMATTER')
            print(
                f'{ind}{i}max_tag    :{cls.max_tag}\n'
                f'{ind}{i}bits_tag   :{cls.bits_tag}\n'
                f'{ind}{i}max_index  :{cls.max_index}\n'
                f'{ind}{i}bits_set   :{cls.bits_set}\n'
                f'{ind}{i}max_offset :{cls.max_offset}\n'
                f'{ind}{i}bits_off   :{cls.bits_off}'
            )
            return


    class Plot:
        ############################################################
        #### CONSTANT VALUES
        PLOTCODES = {
            'MAP': 'Graphic MAP',
            'SLD': 'Spatial Locality Degree',
            'TLD': 'Temporal Locality Degree',
            'CMR': 'Cache Miss Ratio',
            'CMMA': 'Cumulative Main Memory Access',
            'CUR': 'Cache Usage Ratio',
            'AD': 'Aliasing Density',
            'ED': 'Eviction Duration',
            'BPA': 'Block Personality Adoption',
            'EDH': 'Eviction Duration Histogram',
        }

        ############################################################
        #### BASIC VALUES
        # Image to export
        width = 8 # image width
        height = 4 # image height
        dpi = 200 # resolution of the image
        format = 'png' # format, usually png or pdf
        img_border_pad = 0.025 # padding around the image
        img_title_vpad = 6 # padding between the plot and its title

        # terminal UI
        ui_modulename_hpad = HPAD
        ui_plotname_hpad = HPAD

        # Plots Axes
        max_xtick_count = 11
        max_ytick_count = 11
        max_map_ytick_count = 11
        x_orient = 'v'

        # Plot Lines (of the curves) [0]:line [1]:area filling
        linewidth = 0.25
        pal_lig = [60,75]
        pal_sat = [50,75]
        pal_alp = [80,50]

        # Visual aids (matplotlib grids and ticks)
        # Dependent axis (normally Y)
        grid_main_width = 0.6
        grid_main_style = '-'
        grid_main_alpha = 0.2
        # Independent axis (normally X)
        grid_other_width = 0.4
        grid_other_style = '--'
        grid_other_alpha = 0.2

        # MAP plot
        # maximum number of bytes or blocks at which to still show the MAP grids
        grid_max_bytes = 128
        grid_max_blocks = 48

        # Text boxes
        tbox_bg = '#FFFFFF88'
        tbox_border = '#CC000000' # transparent
        tbox_font = 'monospace'
        tbox_font_size = 9

        # Specific to MAP plot
        fade_bytes_alpha = 0.1 # fading of bytes out-of-range to complete the block

        initialized = False

        ############################################################
        # DERIVED VALUES
        # Plots to be exported
        include = 'all'

        # Plots Axes
        x_ranges = 'full'
        y_ranges = 'full'

        # Specific to MAP plot
        min_map_res,max_map_res = 1, 'auto'
        #
        # Specific of Personality
        jump_line_width = 1


        @classmethod
        def from_args(cls, args):
            # assign only if new value is not None
            def assg_val(current, new):
                return new if new is not None else current

            # set all settings from the arguments
            cls.width = assg_val(cls.width, args.plot_width)
            cls.height = assg_val(cls.height, args.plot_height)
            cls.dpi = assg_val(cls.dpi, args.dpi)
            cls.max_res = assg_val(cls.max_res, args.max_res) # overwritten by __init_derived_values()
            cls.format = assg_val(cls.format, args.format)
            cls.include = assg_val(cls.include, args.plotcodes)
            cls.x_orient = assg_val(cls.x_orient, args.x_orient)
            cls.x_ranges = assg_val(cls.x_ranges, args.x_ranges)
            cls.y_ranges = assg_val(cls.y_ranges, args.y_ranges)

            cls.__init_derived_values()
            cls.initialized = True
            return

        @classmethod
        def __init_derived_values(cls):
            cls.include = cls.__init_include_plots(cls.include)
            cls.x_ranges = cls.__init_ranges(cls.x_ranges)
            cls.y_ranges = cls.__init_ranges(cls.y_ranges)
            cls.min_res,cls.max_res = cls.__init_map_resolution(
                cls.width, cls.height, cls.dpi, cls.max_res)
            print('[!] Hardcoded jump_line_width')
            cls.jump_line_width = 1 #max(0.2,min(3,12*(width/data_X_size)))
            return

        @classmethod
        def __init_include_plots(cls, user_plotcodes_str):
            user_plotcodes = [x.strip() for x in user_plotcodes_str.upper().split(',')]
            including = set(cls.PLOTCODES.keys())
            if user_plotcodes and 'ALL' not in user_plotcodes:
                including = set()
                for up in user_plotcodes:
                    if up in cls.PLOTCODES:
                        including.add(up)
                    else:
                        print(f'Warning: Unknown plotcode "{up}".')
            return including

        @classmethod
        def __init_ranges(cls, ranges_str):
            user_ranges = [r.strip() for r in ranges_str.upper().split(',')]
            ranges = dict()
            if user_ranges and 'FULL' not in user_ranges:
                for ran in user_ranges:
                    try:
                        plcode, min_val, max_val = ran.split(':')
                        min_val = float(min_val)
                        max_val = float(max_val)
                    except ValueError:
                        print(f'Error: Range with wrong format "{ran}".')
                        exit(1)
                    if min_val >= max_val:
                        print(f'Error: Range min:{min_val} >= max:{max_val}.')
                        exit(1)
                    if plcode not in cls.PLOTCODES:
                        print(f'Error: Invalid plotcode "{plcode}"')
                        exit(1)

                    ranges[plcode] = (min_val, max_val)
            return ranges

        @classmethod
        def __init_map_resolution(cls, width, height, dpi, max_res):
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

        @classmethod
        def __str__(cls):
            ret_str = ''
            my_attrs = [
                'width', 'height', 'dpi', 'format', 'img_border_pad',
                'img_title_vpad', 'ui_modulename_hpad', 'ui_plotname_hpad',
                'max_xtick_count', 'max_ytick_count', 'max_map_ytick_count',
                'x_orient', 'linewidth', 'pal_lig', 'pal_sat', 'pal_alp',
                'grid_main_width', 'grid_main_style', 'grid_main_alpha',
                'grid_other_width', 'grid_other_style', 'grid_other_alpha',
                'grid_max_bytes', 'grid_max_blocks', 'tbox_bg', 'tbox_border',
                'tbox_font', 'tbox_font_size', 'fade_bytes_alpha', 'include',
                'x_ranges', 'y_ranges', 'min_res', 'max_res', 'jump_line_width',
                'initialized'
            ]
            for prop in my_attrs:
                val = getattr(cls, prop)
                if type(val) == str:
                    val = f'\'{val}\''
                ret_str += f'{prop:7}: {val}\n'
            return ret_str[:-1]

        @classmethod
        def describe(cls, ind=''):
            i = '    '
            cls_str = cls.__str__()
            cls_str = cls_str.split('\n')
            print(f'{ind}PLOT OPTIONS')
            for line in cls_str:
                print(f'{ind}{i}{line}')
            return


    class Map:
        ############################################################
        #### CONSTANT VALUES
        # headers and name:value pairs.
        warning_header = '# WARNING'
        metadata_header = '# METADATA'
        data_header = '# DATA'
        # file_name -> (member_name, int_base)
        key_map = {
            'start-addr'   : ('start_addr',16),
            'end-addr'     : ('end_addr', 16),
            'block-size'   : ('mem_size',10),
            'thread-count' : ('thread_count',10),
            'event-count'  : ('event_count',10),
            'max-time'     : ('time_size',10), # this one is adapted
        }
        ui_mapparam_hpad = HPAD

        ############################################################
        #### BASIC VALUES
        file_path = None
        start_addr = None
        end_addr = None
        mem_size = None
        thread_count = None
        event_count = None
        time_size = None

        initialized = False

        ############################################################
        #### DERIVED VALUES
        prefix = None # unique name derived from file_path
        # aligned_start_addr <= start_addr.
        # This value is aligned to the beginning of a block
        aligned_start_addr = None
        # the distance (in bytes) between aligned_start_addr and start_addr
        left_pad = None
        # the distance (in bytes) between end_addr and aligned_end_addr
        right_pad = None
        # end_addr <= aligned_end_addr.
        # This value is aligned to the end of a block
        aligned_end_addr = None
        # total number of bytes. Including padding.
        num_padded_bytes = None
        # total number of block used by num_padded_bytes.
        num_blocks = None
        # the value of the first real tag in the range
        first_real_tag = None

        @classmethod
        def from_file(cls, map_filepath):
            if map_filepath is None:
                print('You must specify a map file.')
                exit(1)
            cls.file_path = map_filepath
            try:
                file = open(cls.file_path, 'r')
            except:
                print(f'Error while reading {cls.file_path}: '
                      'File does not exist or cannot be read.')
                exit(1)


            # Skip to metadata section
            line = file.readline()
            while line.strip() != cls.metadata_header:
                if line == '':
                    print(f'Error while reading {cls.file_path}: '
                          'EOF reached before any metadata.')
                    exit(1)
                print(f'    {line.strip()}')
                line = file.readline()

            # Read Metadata
            while line.strip() not in (cls.warning_header,
                                       cls.data_header):
                if line == '':
                    print(f'Error while reading {cls.file_path}: '
                          'EOF reached before any data.')
                    exit(1)
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
                    print(f'Error while reading {cls.file_path}: '
                          'Malformed line in Metadata Section:\n'
                          f'>>>>{line}')
                    exit(1)
                # check for recognized pair
                if name in cls.key_map:
                    try:
                        int_val = int(val, cls.key_map[name][1])
                    except ValueError:
                        print(f'Error while reading {cls.file_path}: '
                              f'Invalid value for in Metadata Section.\n'
                              f'>>>>{line}')
                        exit(1)
                    setattr(cls, cls.key_map[name][0], int_val)

                # get next line
                line = file.readline()

            # if any value is missing, error.
            if None in (cls.start_addr, cls.end_addr, cls.mem_size,
                        cls.thread_count, cls.event_count, cls.time_size):
                print(f'Error while reading {cls.file_path}: '
                      f'Incomplete Metadata.\n'
                      'Data needed:\n')
                for d in cls.key_map:
                    print(f'    {d}')
                exit(1)

            # error if start_addr, mem_size and end_addr are incoherent.
            if cls.end_addr - cls.start_addr + 1 != cls.mem_size:
                print(f'Error while reading {cls.file_path}: '
                      'The start/end addresses and size are inconsistent:\n'
                      f'    {hex(cls.end_addr)} - {hex(cls.start_addr)} + 1 '
                      f'!= {cls.mem_size}')
                exit(1)

            # convert max-time index (what comes in the file) to time_size
            cls.time_size +=1

            file.close()
            cls.__init_derived_values()
            return

        @classmethod
        def from_dict(cls, map_dict):
            # load data from the map section of the metric file
            cls.__dict_to_basics(map_dict)

            # compute derived values
            cls.__init_derived_values()
            cls.initialized = True
            return

        @classmethod
        def __init_derived_values(cls):
            # the/path/to/mapfile.map --> the_path_to_mapfile
            basename = os.path.splitext(cls.file_path)[0]
            path_elements = os.path.normalpath(basename).split(os.sep)
            cls.prefix = '_'.join(path_elements)

            # compute padding bytes to make the memory chunk block-aligned.
            if not Settings.Cache.initialized:
                raise Exception('Cache settings must be initialized '
                                'before MAP settings, as the memory padding '
                                'depends on cache settings values.')
            cls.left_pad  = cls.start_addr & (Settings.Cache.line_size-1)
            cls.aligned_start_addr = cls.start_addr - cls.left_pad
            cls.right_pad = (Settings.Cache.line_size-1) - \
                (cls.end_addr & (Settings.Cache.line_size-1))
            cls.aligned_end_addr = cls.end_addr + cls.right_pad
            cls.num_padded_bytes = (cls.end_addr+cls.right_pad) - \
                (cls.start_addr - cls.left_pad + 1)
            cls.num_blocks = cls.num_padded_bytes // Settings.Cache.line_size
            cls.first_real_tag = cls.start_addr >> \
                (Settings.Cache.bits_set + Settings.Cache.bits_off)

        @classmethod
        def __dict_to_basics(cls, map_dict):
            cls.file_path = map_dict['file_path']
            cls.start_addr = map_dict['start_addr']
            cls.end_addr = map_dict['end_addr']
            cls.mem_size = map_dict['mem_size']
            cls.thread_count = map_dict['thread_count']
            cls.event_count = map_dict['event_count']
            cls.time_size = map_dict['time_size']
            return

        @classmethod
        def basics_to_dict(cls):
            if not cls.initialized:
                raise Exception("Map not initialized. Cannot export.")
            return {
                "file_path": cls.file_path,
                "start_addr": cls.start_addr,
                "end_addr": cls.end_addr,
                "mem_size": cls.mem_size,
                "thread_count": cls.thread_count,
                "event_count": cls.event_count,
                "time_size": cls.time_size,
            }

        @classmethod
        def __str__(cls):
            ret_str = ''
            for prop in cls.__dict__:
                if getattr(cls, prop) is not None:
                    ret_str += f'{prop:19}= {getattr(cls, prop)}\n'
            return ret_str[:-1]

        @classmethod
        def describe(cls, ind=''):
            i = '    '
            if cls.file_path is None:
                fname = ' (No MAP file)'
            else:
                fname = f' ({cls.file_path})'
            print(f'{ind}MEMORY ACCESS PATTERN{fname}')
            print(f'{ind}{i}{"First Address":{cls.ui_mapparam_hpad}}: '
                  f'{hex(cls.start_addr)}\n'
                  f'{ind}{i}{"Memory Size":{cls.ui_mapparam_hpad}}: '
                  f'{cls.mem_size} bytes\n'
                  f'{ind}{i}{"Maximum Time":{cls.ui_mapparam_hpad}}: '
                  f'{cls.time_size-1}\n'
                  f'{ind}{i}{"Thread Count":{cls.ui_mapparam_hpad}}: '
                  f'{cls.thread_count}\n'
                  f'{ind}{i}{"Event Count":{cls.ui_mapparam_hpad}}: '
                  f'{cls.event_count}'
            )
            return
