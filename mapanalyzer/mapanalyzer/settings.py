import os
from datetime import datetime
from itertools import zip_longest

from mapanalyzer.ui import UI

class Settings:
    mode = 'sim-plot'
    timestamp = datetime.now().strftime('%Y-%m-%d_%H:%M:%S')
    # used to check enabled codes and to create help message
    ALL_METRIC_CODES = {
        'MAP'  : 'Memory Access Pattern Visualization',
        'SLD'  : 'Spatial Locality Degree',
        'TLD'  : 'Temporal Locality Degree',
        'CMR'  : 'Cache Miss Rate',
        'CMMA' : 'Cumulative Main Memory Access',
        'CUR'  : 'Cache Usage Rate',
        'AD'   : 'Aliasing Density',
        'BPA'  : 'Block Personality Adoption',
        'SMRI' : 'Short Memory Roundtrip Intervals',
        'MRID' : 'Memory Roundtrip Intervals Distribution'
    }

    @classmethod
    def set_mode(cls, args):
        if args.mode is not None:
            cls.mode = args.mode
        return

    @classmethod
    def to_dict(cls):
        data = {
            'timestamp': cls.timestamp
        }
        return data

    @classmethod
    def describe(cls, ind=''):
        UI.indent_in('SETTINGS')
        my_attrs = ['Plot', 'Cache', 'Map']
        for attr in my_attrs:
            getattr(cls, attr).describe()
        UI.indent_out()
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

        ############################################################
        #### BASIC VALUES
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
                pass
                #UI.info('No cache file given. Using default configuration.')
            elif not os.path.isfile(filename):
                UI.error(f'While reading "{filename}":\n'
                         'File does not exist or cannot be read.')

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
                            UI.warning(f'Ignoring invalid line:\n'
                                       f'>>> {line}')
                            continue
                        name,val = key_val_arr[0], key_val_arr[1]

                        # ignore invalid property names
                        if name not in cls.key_map:
                            UI.warning(f'Ignoring invalid property:\n'
                                       f'>>> {line}')
                            continue

                        # ignore invalid values
                        try:
                            val = int(val)
                        except Exception:
                            UI.warning(f'Ignoring invalid value:\n'
                                       f'>>> {line}')
                            continue

                        name_vals[name] = val

                    # error if cache file was given but it is incomplete.
                    if len(cls.key_map) != len(name_vals):
                        UI.error('Cache file given does not have all '
                                 'necessary properties.\n'
                                 'See mapanalyzer --help.')

                    # apply values
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
        def to_dict(cls):
            if not cls.initialized:
                UI.error('Cache.to_dict: Cache not initialized, cannot export.')
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
        def describe(cls):
            names = [
                'Address Size',
                'Cache Size',
                'Number of Sets',
                'Line Size',
                'Associativity'
            ]
            vals = [
                f'{cls.arch} bits ('
                  f'tag:{cls.bits_tag} | '
                  f'idx:{cls.bits_set} | '
                  f'off:{cls.bits_off})',
                f'{cls.cache_size} bytes',
                f'{cls.num_sets}',
                f'{cls.line_size} bytes',
                f'{cls.asso}-way'
            ]
            UI.columns((names, vals), sep=' : ')
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
        def describe(cls):
            UI.indent_in(title='ADDR FORMATTER')
            names = ['max_tag', 'bits_tag', 'max_index', 'bits_set',
                     'max_offset', 'bits_off']
            vals = [cls.max_tag, cls.bits_tag, cls.max_index, cls.bits_set,
                    cls.max_offset, cls.bits_off]
            UI.columns((names, vals), sep=' : ')
            UI.indent_out()
            return


    class Metrics:
        ############################################################
        # DERIVED VALUES
        # Metrics *enabled by the user*. Initialized to set of metric codes.
        enabled = None
        enabled_user = None
        enabled_explicit = False

        # Metrics *available in the tool*. All the metrics with some module
        # supporting them. Check comments on Settings.Metrics.set_available()
        # {code -> either module instance or module class}
        available = None

        # code of the background metric.
        bg = None
        bg_user_set = None

        initialized = False

        @classmethod
        def from_args(cls, args):
            # initialize each argument
            cls.__init_enabled(args.met_codes)

            cls.bg = cls.__init_bg(args.bg_metric,
                                   list(Settings.ALL_METRIC_CODES.keys()),
                                   'MAP')
            cls.bg_user_set = args.bg_metric
            cls.initialized = True
            return

        @classmethod
        def from_dict(cls, pdata_dict):
            # set values from the dictionary
            cls.enabled = {pdata_dict['fg']['code']}

            # get pdata bg metric (if any)
            pdata_bg = None
            if pdata_dict['bg'] is not None:
                pdata_bg = pdata_dict['bg']['code']

            # use the pdata bg unless user explicitly has set bg
            user_bg = pdata_bg
            if cls.bg_user_set:
                user_bg = cls.bg

            cls.bg = cls.__init_bg(user_bg, [pdata_bg], None)
            cls.initialized = True
            return

        @classmethod
        def __init_enabled(cls, fg_codes):
            all_codes = {m.upper() for m in Settings.ALL_METRIC_CODES.keys()}
            # if user said nothing
            if fg_codes is None:
                cls.enabled_user = all_codes
                cls.enabled = all_codes
                cls.enabled_explicit = False

            # if user said 'all'
            elif fg_codes.upper() == 'ALL':
                cls.enabled_user = all_codes
                cls.enabled = all_codes
                cls.enabled_explicit = True

            # if user gave an explicit list:
            else:
                user_codes = {m.strip().upper() for m in fg_codes.split(',')}
                cls.enabled_user = user_codes
                cls.enabled = user_codes
                cls.enabled_explicit = True
            return

        @classmethod
        def __init_bg(cls, bg_code, bg_options, fallback_code):
            # If omitted or explicitly asked for 'none', set to None.
            if bg_code is None or bg_code.upper() == 'NONE':
                return None

            # if not omitted, check that it exists in the options
            bg_code = bg_code.upper()
            if bg_code in bg_options:
                return bg_code

            # if it doesn't exist in the options, use fallback
            opts = ', '.join([str(o) for o in bg_options])
            UI.warning(f'Background metric "{bg_code}" not available. '
                       f'Only "{opts}" metrics are available. Setting bg metric '
                       f'to "{str(fallback_code)}"')
            if fallback_code is None or fallback_code in bg_options:
                return fallback_code

            UI.error(f'Fallback background metric "{str(fallback_code)}" not '
                     'available.')
            return

        @classmethod
        def set_available(cls, available_modules,
                          supp_metrics_name='supported_metrics'):
            """
            - If the tool is in simulation or plot mode, then at least one
              instance of Modules is created. Modules.__init__() calls this
              method with a list of module instances.
              Also, supp_metrics_name=='supported_metrics', so that metrics are
              searched in mod.supported_metrics.keys() (metrics that support
              normal plotting).

            - If the tool is in aggregate mode, then the class method
              Modules.aggregate_and_plot() is called, which in turn calls this
              method with a list of module Classes.
              Also, supp_metrics_name=='supported_aggr_metrics', so that metrics
              are searched in mod.supported_aggr_metric.keys() (metrics that
              supports aggreagation plotting).

            Metrics.available is sorted by the metric number, so that traversing
            it 'makes sense' to the user.
            """

            num_met_mod = []
            for module in available_modules:
                # obtain the dictionary in which the metrics are keys.
                try:
                    supp_metrics_dict = getattr(module, supp_metrics_name)
                except:
                    if type(module) == type(type):
                        mod_name = module.__name__
                    else:
                        mod_name = module.__class__.__name__
                    UI.error(f'It seems that module {mod_name} has not '
                             f'defined the dictionary {supp_metrics_name} in '
                             'which to search for its supported metrics.')

                # add metrics' number, code, and module (instance or class)
                for sup_met_code,sup_met_str in supp_metrics_dict.items():
                    num_met_mod.append(
                        (sup_met_str.number, sup_met_code, module)
                    )

            # sort by metric number and extract key,value for the dictionary
            num_met_mod.sort()
            _, sup_met_codes, sup_modules = zip(*num_met_mod)

            # check that there are no duplicated metric codes
            if len(sup_met_codes) != len(set(sup_met_codes)):
                repeated = ''
                idx = 0
                for i,(smc,uniq) in enumerate(
                        zip_longest(sup_met_codes, set(sup_met_codes))):
                    if smc != uniq:
                        repeated = smc
                        idx = i
                        break
                sup_module = sup_modules[idx]
                sup_module_other = sup_modules[idx-1]
                if type(sup_module) == type(type):
                    sup_module_name = sup_module.__name__
                    sup_module_name_other = sup_module_other.__name__
                else:
                    sup_module_name = sup_module.__class__.__name__
                    sup_module_name_other = sup_module_other.__class__.__name__
                UI.error(
                    f'The metric code "{repeated}" is not unique across all '
                    'modules.\n'
                    f'  {sup_module_name}.{supp_metrics_name}[\'{repeated}\']\n'
                    f'  {sup_module_name_other}.{supp_metrics_name}'
                    f'[\'{repeated}\']')

            # create the {code -> module} dictionary
            cls.available = {met:mod
                             for met,mod in zip(sup_met_codes, sup_modules)}

            # given that we are here already, let's sort cls.enabled too
            sorted_enabled = []
            for sup_met in sup_met_codes:
                if sup_met in cls.enabled:
                    sorted_enabled.append(sup_met)
            cls.enabled = sorted_enabled

            return

        @classmethod
        def describe(cls):
            attrs = ['enabled', 'available', 'bg', 'bg_user_set', 'initialized']
            vals = [getattr(cls, at) for at in attrs]
            UI.indent_in(title='METRICS SETTINGS')
            UI.columns((attrs, vals), sep=' : ')
            UI.indent_out()
            return


    class Map:
        ############################################################
        #### CONSTANT VALUES
        # headers
        header_error = '# ERROR'
        header_warning = '# WARNING'
        header_metadata = '# METADATA'
        header_data = '# DATA'

        # find headers in these top lines (or until header_data is found)
        header_lines = 100

        # name-in-file : (value, integer_base)
        key_map = {
            'start-addr'   : ('start_addr',16),
            'end-addr'     : ('end_addr', 16),
            'block-size'   : ('mem_size',10),
            'owner-thread' : ('owner_thread',10),
            'slice-size'   : ('slice_size',10),
            'thread-count' : ('thread_count',10),
            'event-count'  : ('event_count',10),
            'max-time'     : ('time_size',10), # this one is adapted
        }

        ############################################################
        #### BASIC VALUES
        file_path = None
        start_addr = None
        end_addr = None
        mem_size = None
        owner_thread = None
        slice_size = None
        thread_count = None
        event_count = None
        time_size = None

        initialized = False
        initd_from_dict = False

        ############################################################
        #### DERIVED VALUES
        # common prefix of list of file paths that can be discarded.
        path_prefix = None
        # unique name derived from file_path and cls.path_prefix
        ID = ''
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
            # check for file existence.
            if map_filepath is None:
                UI.error('You must specify a MAP file.')
            cls.file_path = map_filepath
            try:
                file = open(cls.file_path, 'r')
            except:
                UI.error(f'While reading MAP file "{cls.file_path}":\n'
                         'File does not exist or cannot be read.')

            # Collect lines from the different sections
            unknown = '__#__Unknown Section__#__'
            sections = {
                unknown: [],
                cls.header_error: [],
                cls.header_warning: [],
                cls.header_metadata: [],
                cls.header_data: [],
            }
            current_section = unknown
            while True:
                line = file.readline()

                # EOF or data section found
                if line == '' or line.strip() == cls.header_data:
                    break

                # if new section found, start storing lines on its array
                line = line.strip()
                if line != unknown and line in sections:
                    current_section = line
                    continue

                # skip empty and comment lines
                if line == '' or line[0] == '#':
                    continue

                # store line in its section's array
                sections[current_section].append(line)
            file.close()

            # If there are error or warning sections, print them.
            if len(sections[cls.header_error]) != 0 or \
               len(sections[cls.header_warning]) != 0:

                # If there are errors, show them and stop
                if len(sections[cls.header_error]) != 0:
                    e_str = []
                    for l in sections[cls.header_error]:
                        e_str.append(f'>>> {l}')
                    e_str = '\n'.join(e_str)
                    UI.error(f'While reading MAP file "{cls.file_path}":\n'
                             'File reports ERRORS:\n'
                             f'{e_str}')

                # If there are warnings, show them and continue
                if len(sections[cls.header_warning]) != 0:
                    w_str = []
                    for l in sections[cls.header_warning]:
                        w_str.append(f'>>> {l}')
                    w_str = '\n'.join(w_str)
                    UI.warning(f'While reading MAP file "{cls.file_path}":\n'
                               'File reports WARNINGS:\n'
                               f'{w_str}')

            # If there is no metadata section, that is also
            # a non-recoverable error
            if len(sections[cls.header_metadata]) == 0:
                UI.error(f'While reading MAP file "{cls.file_path}":\n'
                         'File does not have a METADATA section.\n'
                         'Is this a valid MAP file?')

            # Read Metadata
            for line in sections[cls.header_metadata]:
                # parse 'name: val' lines
                try:
                    no_comment_line = line.split('#')[0].strip()
                    name,val = no_comment_line.split(':')
                    name,val = name.strip(),val.strip()
                except:
                    UI.error(f'While reading MAP file "{cls.file_path}":\n'
                             'Malformed line in METADATA Section.\n'
                             f'>>> {line}')

                # check if it is a recognized pair (known name and
                # correct integer parsing)
                if name in cls.key_map:
                    try:
                        int_val = int(val, cls.key_map[name][1])
                    except ValueError:
                        UI.error(f'While reading MAP file "{cls.file_path}":\n'
                                 f'Invalid value in METADATA section.\n'
                                 f'>>> {line}')

                    # accepting and storing the value
                    setattr(cls, cls.key_map[name][0], int_val)
                else:
                    UI.warning(f'While reading MAP file "{cls.file_path}":\n'
                               'Unrecognized METADATA parameter name.\n'
                               f'>>> {line}')

            # if any value is missing, error.
            missing = []
            for name in cls.key_map:
                if getattr(cls, cls.key_map[name][0]) is None:
                    missing.append(name)
            if len(missing) != 0:
                m_str = []
                for m in missing:
                    m_str.append(f' - {m}')
                m_str = '\n'.join(m_str)
                UI.error(f'While reading MAP file "{cls.file_path}":\n'
                         f'Incomplete METADATA section. Missing data:\n'
                         f'{m_str}')

            # error if start_addr, mem_size and end_addr are incoherent.
            if cls.end_addr - cls.start_addr + 1 != cls.mem_size:
                UI.error(f'While reading MAP file "{cls.file_path}":\n'
                         'The (start,end,size) parameters are inconsistent:\n'
                         f'{hex(cls.end_addr)} - {hex(cls.start_addr)} + 1 '
                         f'!= {cls.mem_size}')

            # convert max-time index (what comes in the file) to time_size
            cls.time_size +=1

            # compute derived values
            cls.initd_from_dict = False
            cls.__init_derived_values()
            cls.initialized = True
            return

        @classmethod
        def from_dict(cls, map_dict, pdata_file_path=None):
            # load data from the map section of the metric file
            cls.__dict_to_basics(map_dict)
            cls.file_path = pdata_file_path

            # compute derived values
            cls.initd_from_dict = True
            cls.__init_derived_values()
            cls.initialized = True
            return

        @classmethod
        def set_path_prefix(cls, input_files_paths):
            """If only one file was given, then, use the directory name:
            If multiple files were given, then, use the common path.
            Temporarily set the cls.ID based on the common prefix of the paths
            (without their dirnames). If cls.from_dict or cls.from_file are
            later called, they update the ID based on that particular file"""
            if len(input_files_paths) == 0:
                UI.error('No input files were given.')
            elif len(input_files_paths) == 1:
                cls.path_prefix = os.path.dirname(input_files_paths[0])
            else:
                cls.path_prefix = os.path.commonpath(input_files_paths)

            # set temporary ID based on the difference between the common path
            # among all paths (of a given character length) and the common
            # prefix among them (at least as long as the common path)
            common_prefix = os.path.commonprefix(input_files_paths)
            basename = os.path.relpath(common_prefix, cls.path_prefix)

            # keep removing awkward characters from end or beginning until
            # the id is nice :)
            unwanted = '/\\ _-~\t'
            almost_id = os.path.splitext(basename)[0].strip(unwanted)
            almost_id_new = almost_id.strip(unwanted)
            while almost_id != almost_id_new:
                almost_id = almost_id_new
                almost_id_new = almost_id.strip(unwanted)
            # avoid hidden files
            while almost_id[0] == '.':
                almost_id = almost_id[1:]
            # avoid ending with dash
            while almost_id[-1] == '-':
                almost_id = almost_id[:-1]
            cls.ID = almost_id
            return

        @classmethod
        def __generate_id(cls):
            """
            Determine a unique ID based on cls.file_path minus the stored
            cls.path_prefix.
            """
            relative_path = os.path.relpath(cls.file_path, cls.path_prefix)
            basename, _ = os.path.splitext(relative_path)

            # if initialized from dictionary, then that dictionary came from
            # a pdata file. Those files by default have an extra dot in their
            # filename, and the string after that is metric-related, so discard
            # it.
            if cls.initd_from_dict:
                orig_map_prefix, _ = os.path.splitext(basename)
            else:
                orig_map_prefix = basename
            path_elements = os.path.normpath(orig_map_prefix).split(os.sep)
            map_id = '_'.join(path_elements)

            return map_id

        @classmethod
        def __init_derived_values(cls):
            """Compute derived values from the basic ones"""
            cls.ID = cls.__generate_id()
            cls.__init_mem_padding()

        @classmethod
        def __init_mem_padding(cls):
            # compute padding bytes to make the memory chunk block-aligned.
            if not Settings.Cache.initialized:
                UI.error('Cache settings must be initialized before MAP '
                         'settings, as the memory padding depends on the cache '
                         'settings values.')
            cls.left_pad  = cls.start_addr & (Settings.Cache.line_size-1)
            cls.aligned_start_addr = cls.start_addr - cls.left_pad
            cls.right_pad = (Settings.Cache.line_size-1) - \
                (cls.end_addr & (Settings.Cache.line_size-1))
            cls.aligned_end_addr = cls.end_addr + cls.right_pad
            # cls.num_padded_bytes = (cls.end_addr+cls.right_pad) - \
            #     (cls.start_addr - cls.left_pad + 1)
            cls.num_padded_bytes = (cls.end_addr+cls.right_pad) - \
                (cls.start_addr - cls.left_pad) + 1
            cls.num_blocks = cls.num_padded_bytes // Settings.Cache.line_size
            cls.first_real_tag = cls.start_addr >> \
                (Settings.Cache.bits_set + Settings.Cache.bits_off)
            return

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
        def to_dict(cls):
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
        def describe(cls, dbg=False):
            if not dbg:
                names = ['First Address', 'Memory Size', 'Maximum Time',
                         'Thread Count', 'Event Count']
                vals = [f'0x{cls.start_addr:X}', f'{cls.mem_size} bytes',
                        cls.time_size-1, cls.thread_count, cls.event_count]
            else:
                names = ['file_path', 'start_addr', 'end_addr', 'mem_size',
                         'owner_thread', 'slice_size', 'thread_count',
                         'event_count', 'time_size', 'initialized',
                         'initd_from_dict', 'path_prefix', 'ID',
                         'aligned_start_addr', 'left_pad', 'right_pad',
                         'aligned_end_addr', 'num_padded_bytes',
                         'num_blocks', 'first_real_tag']
                vals = [getattr(cls,n) for n in names]
            UI.columns((names, vals), sep=' : ')
            return


    class Plot:
        ############################################################
        #### BASIC VALUES
        # Image to export
        width = 8 # image width
        height = 4 # image height
        dpi = 200 # resolution of the image
        format = 'png' # format, usually png or pdf
        img_border_pad = 0.025 # padding around the image
        img_title_vpad = 6 # padding between the plot and its title

        # Ticks (independent_variable, function_variable)
        ticks_max_count = (11, 11)
        max_xtick_count = 11
        max_ytick_count = 11
        max_map_ytick_count = 11

        x_orient = 'v'

        # line widths for simple and aggregated plots. Individual and average
        # for the curves, or the vertical lines
        p_lw = 1.25
        p_aggr_ind_lw = 0.5
        p_aggr_avg_lw = 1.25
        p_aggr_ind_vlw = 0.5
        p_aggr_avg_vlw = 1.25

        # default color values
        p_hue = (0,0)
        p_sat = (50,75)
        p_lig = (60,75)
        p_alp = (80,50)

        # grids (independent_variable, function_variable)
        grid_width = (0.4 , 0.6)
        grid_style = ('--', '-')
        grid_alpha = (0.2 , 0.2)

        # MAP plot
        # maximum number of bytes or blocks at which to still show the MAP grids
        grid_max_bytes = 128
        grid_max_blocks = 48
        grid_max_sets = 32

        # Text boxes
        tbox_bg = '#FFFFFFCC'
        tbox_border = '#CC000000' # transparent
        tbox_font = 'monospace'
        tbox_font_size = 9

        # In MAP plot, fade bytes used to cache-align the block
        fade_bytes_alpha = 0.1

        # draw vertical lines denoting the executions ends in aggregation mode
        aggr_last_x = True

        # draw individual plots for sets in BPA and SMRI?
        plot_indiv_sets = True

        ############################################################
        # DERIVED VALUES
        initialized = False

        # Axes ranges to show in the different plots
        x_ranges = 'full'
        y_ranges = 'full'

        # textbox horizontal and vertical offsets, {CODE -> (horiz,vert)}
        textbox_offsets = 'default'

        # Specific to MAP plot.
        # min_map_res is only used if the native resolution is too large (above
        # this maximum), and by trying to find a "nice" lower resolution, the
        # only found is too low (below this minimum).
        # If that is the case, then max_map_res is used.
        #
        # This is a derived value because sensible values is derived from the
        # width, height, and dpi given.
        min_map_res,max_map_res = 1, 'auto'

        # Specific to SMRI.
        # draw segments of up to this length. If 'all', draw them all.
        roundtrip_threshold = 'all'


        @classmethod
        def from_args(cls, args):
            # assign only if new value is not None
            def assg_val(current, new):
                return new if new is not None else current

            # set all settings from the arguments
            cls.width = assg_val(cls.width, args.plot_width)
            cls.height = assg_val(cls.height, args.plot_height)
            cls.dpi = assg_val(cls.dpi, args.dpi)
            # overwritten by __init_derived_values()
            cls.max_map_res = assg_val(cls.max_map_res, args.max_res)
            cls.format = assg_val(cls.format, args.format)
            cls.x_orient = assg_val(cls.x_orient, args.x_orient)
            cls.x_ranges = assg_val(cls.x_ranges, args.x_ranges)
            cls.y_ranges = assg_val(cls.y_ranges, args.y_ranges)
            cls.textbox_offsets = assg_val(cls.textbox_offsets,
                                           args.textbox_offsets)
            cls.aggr_last_x = assg_val(cls.aggr_last_x, args.aggr_last_x)
            cls.plot_indiv_sets = assg_val(cls.plot_indiv_sets,
                                           args.plot_indiv_sets)
            cls.roundtrip_threshold = assg_val(cls.roundtrip_threshold,
                                               args.rt_threshld)

            cls.__init_derived_values()
            cls.initialized = True
            return

        @classmethod
        def __init_derived_values(cls):
            cls.x_ranges = cls.__init_ranges(cls.x_ranges)
            cls.y_ranges = cls.__init_ranges(cls.y_ranges)
            cls.textbox_offsets = cls.__init_textbox_offsets()
            cls.min_map_res,cls.max_map_res = cls.__init_map_resolution(
                cls.width, cls.height, cls.dpi, cls.max_map_res)
            if cls.roundtrip_threshold != 'all':
                try:
                    cls.roundtrip_threshold = int(cls.roundtrip_threshold)
                except:
                    UI.error(f'Argument "-st/--short-roundtrip-threshold" '
                             'expects an integer or "all".')
            return

        @classmethod
        def __init_ranges(cls, ranges_str):
            user_ranges = [r.strip() for r in ranges_str.upper().split(',')]
            ranges = dict()
            if user_ranges and 'FULL' not in user_ranges:
                for ran in user_ranges:
                    try:
                        met_code, min_val, max_val = ran.split(':')
                        if '.' in min_val:
                            min_val = float(min_val)
                        else:
                            min_val = int(min_val)
                        if '.' in max_val:
                            max_val = float(max_val)
                        else:
                            max_val = int(max_val)
                    except ValueError:
                        UI.error(f'Plot Range with wrong format "{ran}".')
                    if min_val >= max_val:
                        UI.error(f'Plot Range min:{min_val} >= max:{max_val}.')
                    if met_code not in Settings.ALL_METRIC_CODES.keys():
                        UI.error(f'Invalid metric code "{met_code}".')

                    ranges[met_code] = (min_val, max_val)
            return ranges

        @classmethod
        def __init_textbox_offsets(cls):
            user_tboff = cls.textbox_offsets
            if user_tboff is None or user_tboff == 'default':
                return {}
            user_tb_off = str(user_tboff)
            user_offsets = [o.strip() for o in user_tboff.split(',')]
            offsets = {}
            for off in user_offsets:
                try:
                    met_code, hor_val, ver_val = off.split(':')
                    hor_val = float(hor_val)
                    ver_val = float(ver_val)
                except ValueError:
                    UI.error(f'Textbox Offsets with wrong format "{off}".')
                if hor_val < 0 or hor_val > 1:
                    UI.error(f'Horizontal textbox offset value out of range '
                             '(0,1).')
                if ver_val < 0 or ver_val > 1:
                    UI.error(f'Vertical textbox offset value out of range '
                             '(0,1).')
                if met_code not in Settings.ALL_METRIC_CODES.keys():
                    UI.error(f'Invalid metric code "{met_code}".')

                offsets[met_code] = (hor_val, ver_val)
            return offsets

        @classmethod
        def __init_map_resolution(cls, width, height, dpi, max_res):
            # guess the number of pixels in the smallest width or height
            # of the plot area. Pick the smallest between that and the
            # minimum
            min_res = round(min(0.9*min(width,height)*dpi,210))
            if max_res == 'auto':
                max_res = round(min(0.9*min(width,height)*dpi,2310))
            else:
                try:
                    max_res = int(max_res)
                except:
                    UI.error(f'Error: max-res must be an integer or "auto".')
            return (min_res,max_res)

        @classmethod
        def describe(cls):
            attrs = [
                'width', 'height', 'dpi', 'format', 'img_border_pad',
                'img_title_vpad',
                'max_xtick_count', 'max_ytick_count', 'max_map_ytick_count',
                'x_orient', 'linewidth', 'pal_lig', 'pal_sat', 'pal_alp',
                'grid_width', 'grid_style', 'grid_alpha',
                'grid_max_bytes', 'grid_max_blocks', 'tbox_bg', 'tbox_border',
                'tbox_font', 'tbox_font_size', 'fade_bytes_alpha',
                'x_ranges', 'y_ranges', 'min_map_res', 'max_map_res',
                'initialized'
            ]
            vals = [getattr(cls, at) for at in attrs]
            UI.indent_in(title='PLOTS SETTINGS')
            UI.columns((attrs, vals), sep=' : ')
            UI.indent_out()
            return
