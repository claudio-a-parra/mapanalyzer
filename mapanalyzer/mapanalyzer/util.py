import sys, os, json
import colorsys # to convert from hls to rgb
import matplotlib.pyplot as plt
import argparse # to get command line arguments
from jsonschema import validate, ValidationError # to validate pdata files
from .settings import Settings as st
from .ui import UI

class MetricStrings:
    def __init__(self, about='About this metric', title='Title',
                 subtit='Subtitle', number='00', xlab='X-axis', ylab='Y-axis'):
        self.about = about
        self.title = title
        self.subtit= subtit
        self.number = number
        self.xlab  = xlab
        self.ylab  = ylab
        return

class Palette:
    """
    Create HSLA palettes, a tensor of 4 dimensions, where the first dimension
    is hue, the second is saturation, third is Light, and fourth is alpha.

    h, s, l, a     : Either explicit list of values, or integers specifying the
                     length of lists automatically created for each parameter.
                     These lists create a number of elements equally spaced
                     across the spectrum of the parameter.
                     If a list is given, wrap h values around 360, and s,l,a
                     values are clipped from 0 to 100.
    {h,s,l,a}_off  : If an integer is given to a parameter X, then use its
                     'X_off' to determine the first value of the automatic list.
                     In the case of h, the automatic list wraps around.
                     In the case of s,l,a, the list is composed with the range
                     from {s,l,a}_off to 100.

    Ranges:
        hue: 0-359
        saturation: 0-100
        lightness: 0-100
        alpha: 0-100

    Example:
        p = Palette(h=3, s=(50,60), l=(10), a=(100,100), h0=60)
        p == \
        [ # three hues, the first one is 60
            [ # two saturations
                [ # one lightness
                 ['#RGBA'], ['#WXYZ'] # two alphas
                ],
                [...]
            ],
            [],
            []
        ]
        p[0][0][0][1] == '#WXYZ'
    """

    @staticmethod
    def default(hue):
        return Palette(
            hue=(hue,hue),
            sat=st.Plot.p_sat,
            lig=st.Plot.p_lig,
            alp=st.Plot.p_alp
        )

    @staticmethod
    def from_hsla(hsla_tuple):
        return Palette.__hsl2rgb(hsla_tuple[0], hsla_tuple[1],
                                 hsla_tuple[2], hsla_tuple[3])

    @staticmethod
    def __hsl2rgb(h, s, l, a):
        try:
            h,s,l = float(h),float(s),float(l)
            if (not (0 <= h <= 360)) or \
               (not (0 <= s <= 100)) or \
               (not (0 <= l <= 100)) or \
               (not (0 <= a <= 100)):
                raise ValueError
        except ValueError:
            UI.error('Palette.__hsl2rgb(): Incorrect value given to either '
                     'h, s, l, or a')
        h,s,l,a = h/360.0, s/100.0, l/100.0, a/100.0
        r,g,b = colorsys.hls_to_rgb(h, l, s)
        r,g,b,a = round(r*255), round(g*255), round(b*255), round(a*255)
        return f'#{r:02X}{g:02X}{b:02X}{a:02X}'

    # general foreground and background
    fg = __hsl2rgb(0, 0, 0, 100)
    bg = __hsl2rgb(0, 0, 100, 100)

    def __init__(self, hue=1, sat=1, lig=1, alp=1,
                 h_off=0, s_off=0, l_off=0, a_off=0):
        # determine the list of hue values
        if hasattr(hue, '__getitem__'):
            hue_list = [i%360 for i in hue]
        else:
            if hue < 1:
                UI.error('Hue count (hue=) cannot be less than 1.')
            step = 360/hue
            hue_list = [(round(i*step)+h_off)%360 for i in range(hue)]

        # determine the list of saturation values
        if hasattr(sat, '__getitem__'):
            sat_list = [max(min(i,100),0) for i in sat]
        else:
            if sat < 1:
                UI.error('Saturation count (sat=) cannot be less than 1.')
            sat_range = 100 - s_off
            step = round(sat_range/(sat+1))
            sat_list = [sat_off+i*step for i in range(1, sat+1)]

        # determine the list of lightness values
        if hasattr(lig, '__getitem__'):
            lig_list = [max(min(i,100),0) for i in lig]
        else:
            if lig < 1:
                UI.error('Lighting count (lig=) cannot be less than 1.')
            lig_range = 100 - l_off
            step = round(lig_range/(lig+1))
            lig_list = [l_off+i*step for i in range(1, lig+1)]

        # determine the list of alpha values
        if hasattr(alp, '__getitem__'):
            alp_list = [max(min(i,100),0) for i in alp]
        else:
            if alp < 1:
                UI.error('Alpha count (alp=) cannot be less than 1.')
            alp_range = 100 - a_off
            step = round(alp_range/(alp+1))
            alp_list = [a_off+i*step for i in range(1, alp+1)]

        self.fg = self.__hsl2rgb(hue_list[0], 75,  10, 100)
        self.bg = self.__hsl2rgb(hue_list[0], 100, 100, 60)
        self.col = [[[[self.__hsl2rgb(h,s,l,a)
                       for a in alp_list ]
                      for l in lig_list]
                     for s in sat_list]
                    for h in hue_list]
        return

    def __str__(self):
        ret = ''
        ret +=f'fg    : {self.fg}\n'
        ret +=f'bg    : {self.bg}\n'
        ret +=f'col   :[\n'
        for c in self.col:
            ret += f'         {c},\n'
        ret += '       ]'
        return ret

    def __getitem__(self, idx):
        return self.col[idx]

    def __len__(self):
        return len(self.col)

class MapDataReader:
    """iterates over the map file, reading one record at the time."""
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
                UI.error('Incorrect values to create __MemRecord:\n'
                      f'time  : {time}\n'
                      f'thread: {thread}\n'
                      f'event : {event}\n'
                      f'size  : {size}\n'
                      f'addr  : {addr}')
            return

        def __str__(self):
            return (f'tim:{self.time}, thr:{self.thread}, '
                    f'eve:{self.event}, addr:{self.addr}, '
                    f'siz:{self.size}')

    def __init__(self, map_filepath):
        self.file_path = map_filepath

        # Open file
        self.file = None
        try:
            self.file = open(self.file_path, 'r')
        except FileNotFoundError:
            UI.error(f'While reading "{self.file_path}":\n'
                     'File does not exist or cannot be read.')
        return

    def __go_to_section(self, header):
        if self.file.closed:
            self.file = open(self.file_path, 'r')
        self.file.seek(0)

        while True:
            line = self.file.readline()

            # EOF found
            if line == '':
                UI.error(f'While reading {self.file_path}: '
                         f'File has no section "{header}".')

            # check if at header
            line = line.strip()
            if line == header:
                break
        return

    def __iter__(self):
        self.__go_to_section(st.Map.header_data)
        # consume the first line after the header, which
        # contains the columns names.
        self.file.readline()
        return self

    def __next__(self):
        line = ''
        # read lines until a useful one appears
        while True:
            line = self.file.readline()
            # EOF found
            if line == '':
                self.file.close()
                raise StopIteration

            line = line.strip()

            # ignore empty or comment lines
            if line == '' or line[0] == '#':
                continue

            # remove trailing comments
            line = line.split('#')[0].strip()
            break

        try:
            time,thr,ev,size,off = line.split(',')
        except:
            UI.error(f'While reading "{self.file_path}":\n'
                     'Incorrect number of fields:\n'
                     f'>>> {line}')
        try:
            off = int(off)
        except:
            UI.error(f'While reading {self.file_path}: '
                     'Incorrect value for offset:\n'
                     f'>>> {off}')
            exit(1)

        # Transform the (relative) offset to (absolute) address.
        # I was probably drunk when I thought this... I am pretty sure
        # I am adding and subtracting the same shit somewhere else...
        addr = st.Map.aligned_start_addr + st.Map.left_pad + off
        return self.__Record(time, thr, ev, size, addr)

class PdataFile:
    fmt_name = 'pdata'
    ext = 'json'
    schema = {
        'type' : 'object',
        'properties' : {
            'meta'    : {'type' : 'object'},
            'map'     : {'type' : 'object'},
            'cache'   : {'type' : 'object'},
            'metrics' : {
                'type' : 'object',
                'properties' : {
                    'bg' : {
                        'type' : ['object', 'null'],
                        'properties' : {
                            'code' : {'type' : 'string'}
                        },
                        'required' : ['code']
                    },
                    'fg' : {
                        'type' : 'object',
                        'properties' : {
                            'code' : {'type' : 'string'}
                        },
                        'required' : ['code']
                    }
                },
                'required' : ['fg']
            }
        },
        'required' : ['meta', 'map', 'cache', 'metrics']
    }

    @classmethod
    def save(cls, data:dict, metric_code):
        # obtain metrics strings
        met_str = st.Metrics.available[metric_code].\
            supported_metrics[metric_code]

        # number for consistent sorting of output files
        number = met_str.number

        # map ID computed from the input map file(s)
        prefix = f'{st.Map.ID}.' if st.Map.ID else ''

        # file extension
        ext = cls.ext

        # assembly the final file name
        filename = f'{prefix}{cls.fmt_name}_{number}_{metric_code}.{cls.ext}'

        UI.text(f'{metric_code.ljust(UI.metric_code_hpad)}: ', end='')

        # Verify data is a correctly formed pdata dictionary
        try:
            validate(instance=data, schema=cls.schema)
        except ValidationError as e:
            module = st.Metrics.available[metric_code]
            module_name = module.__class__.__name__
            UI.nl()
            UI.error('The data being saved constitutes a malformed '
                     f'{cls.fmt_name} file:\n'
                     f'{e}\n'
                     f'Please check that {module_name}.{metric_code}_to_dict() '
                     'stores the correct data with at least a key \'code\' '
                     'mapping to the metric\'s code string.')

        # save file
        try:
            with open(filename, 'w') as f:
                json.dump(data, f)
        except Exception as e:
            UI.nl()
            UI.error(f'While trying to save {filename}.\n\n'
                     f'{e}')
        UI.text(filename, indent=False)
        return

    @classmethod
    def load(cls, filepath):
        if filepath is None:
            UI.error(f'While reading pdata file. No file path provided.')
        try:
            open_file = open(filepath, 'r')
        except (FileNotFoundError, IOError):
            UI.error(f'While reading "{filepath}". File does not exist or '
                     'cannot be read.')
        try:
            file_dict = json.load(open_file)
        except json.JSONDecodeError:
            UI.error(f'While reading "{filepath}". File does not seem to '
                     f'be a valid {cls.ext} file.')
        open_file.close()

        # Verify this is a valid pdata file
        try:
            validate(instance=file_dict, schema=cls.schema)
        except ValidationError as e:
            UI.error(f'While reading "{filepath}". This seems to be a '
                     f'malformed {cls.fmt_name} file:\n'
                     f'{e}')

        return file_dict

class PlotFile:
    fmt_plot = 'plot'
    fmt_aggr = 'aggr'

    @classmethod
    def save(cls, mpl_fig, metric_code, aggr=False, variant=''):
        # set different components based on normal vs aggregation mode
        if aggr:
            fmt_name = cls.fmt_aggr
            met_str = st.Metrics.available[metric_code].\
                supported_aggr_metrics[metric_code]
        else:
            fmt_name = cls.fmt_plot
            met_str = st.Metrics.available[metric_code].\
                supported_metrics[metric_code]

        # number for consistent sorting of output files
        number = met_str.number

        # if there is a map ID, computed from the map file(s) given, use it
        prefix = f'{st.Map.ID}.' if st.Map.ID else ''

        # image format (extension)
        ext = st.Plot.format

        # assembly the final file name
        filename = f'{prefix}{fmt_name}_{number}_{metric_code}{variant}.{ext}'

        # print UI message and actually save figure
        UI.text(f'{metric_code.ljust(UI.metric_code_hpad)}: ', end='')
        try:
            mpl_fig.savefig(filename, dpi=st.Plot.dpi, bbox_inches='tight',
                            pad_inches=st.Plot.img_border_pad)
            plt.close(mpl_fig)
        except Exception as e:
            UI.nl()
            UI.error(f'While trying to save {filename}:\n\n'
                     f'{e}')
        UI.text(filename, indent=False)
        return

def sample_list(full_list, base=10, n=10, include_last=False):
    """
    return a list of ticks based on full_list. The idea is to find
    nice numbers (multiples of powers of 10 or 2) and not having
    more than n elements.
    """
    if full_list is None or len(full_list) == 0 or n == 0:
        return []

    # if two ticks, return the extremes.
    if n == 2:
        return [full_list[0], full_list[-1]]

    if n >= len(full_list):
        return full_list

    # find a tick_step such that we print at most n ticks
    tick_step = 1
    tot_ticks = len(full_list)
    factors = [1,2,2.5,5] if base==10 else [1]
    for i in range(1000):
        found = False
        for f in factors:
            f_pow_base = int(f * (base ** i))
            if int(tot_ticks / f_pow_base) <= (n-1):
                tick_step = f_pow_base
                found = True
                break
        if found:
            break

    tick_list = list(full_list[::tick_step])

    # include last element of the list
    if include_last:
        if full_list[-1] - tick_list[-1] > tick_step/2:
            tick_list.append(full_list[-1])
        else:
            tick_list[-1] = full_list[-1]


    return tick_list

def command_line_args_parser():
    synopsis = ('MAP Analyzer, a tool to study the cache friendliness of '
                'memory access patterns.')
    cache_conf = ('cache.conf\n'
                  '  The cache file file must have this format:\n'
                  '\n'
                  f'   # Comments start with pound sign\n'
                  f'   line_size_bytes     : <value> # default: '
                  f'{st.Cache.line_size}\n'
                  f'   associativity       : <value> # default: '
                  f'{st.Cache.asso}\n'
                  f'   cache_size_bytes    : <value> # default: '
                  f'{st.Cache.cache_size}\n'
                  f'   arch_size_bits      : <value> # default: '
                  f'{st.Cache.arch}\n')

    examples = ('examples:\n'
                '  Run cache simulation with a given configuration and \n'
                '  produce metric and plot results:\n'
                '      mapanalyzer --mode simulate --cache mycache.conf -- '
                'myexperiment.map\n'
                '\n'
                '  Plot the results of a previously simulated cache:\n'
                '      mapanalyzer --mode plot -- myexperiment.json\n'
                '\n'
                '  Aggregate three different runs of the same experiment into\n'
                '  a single plot:\n'
                '      mapanalyzer --mode aggregate -- A.json B.json C.json\n'
                '\n'
                '  Run your own script in mapanalyzer runtime environment:\n'
                '      mapanalyzer --mode widget --script my_widget.py '
                '--widgetArg 123 -- widget_input.txt')

    signature = ('By Claudio A. Parra.\n'
                 '2025.\n'
                 'parraca@uci.edu')

    parser = argparse.ArgumentParser(
        description=synopsis+'\n\n',
        epilog=cache_conf+'\n\n'+examples+'\n\n'+signature,
        formatter_class=argparse.RawTextHelpFormatter)

    # Adding arguments
    parser.add_argument(
        '--mode', metavar='MODE', dest='mode',
        choices=['simulate', 'plot', 'sim-plot', 'aggregate', 'widget'],
        type=str, default='sim-plot',
        help=(
            'Defines the operation mode of the tool:\n'
            'simulate  : Only run the cache simulation.\n'
            '              Input : list of MAP files.\n'
            '              Output: PDATA files.\n'
            'plot      : Only plot already obtained metric data (PDATA).\n'
            '              Input : list of PDATA files.\n'
            '              Output: PLOT files. One plot per input PDATA file.\n'
            'sim-plot  : (default) Simulate cache and plot results.\n'
            '              Input : list of MAP files.\n'
            '              Output: PDATA and PLOT files.\n'
            'aggregate : Plot the aggregation of multiple metric data files,\n'
            '            aggregating the ones of the same kind.\n'
            '              Input : list of PDATA files.\n'
            '              Output: Aggregated PLOT files.\n'
            'widget    : Run custom script using the tool\'s runtime.\n'
            '            Experimental, you shouldn\'t need to use this.')
    )

    # Add script name
    parser.add_argument(
        '--script', metavar='SCRIPT', dest='script',
        type=str, default=None,
        help='Python file with the widget (used only in widget mode).'
    )

    parser.add_argument(
        '-ca', '--cache', metavar='CACHE', dest='cachefile',
        type=str, default=None,
        help='File describing the cache. See "cache.conf" section.'
    )

    parser.add_argument(
        '-pw', '--plot-width', metavar='WIDTH', dest='plot_width',
        type=float, default=None,
        help=('Default width of the plots.\n'
              'Format: <integer>')
    )

    parser.add_argument(
        '-ph', '--plot-height', metavar='HEIGHT', dest='plot_height',
        type=float, default=None,
        help=('Default height of the plots.\n'
              'Format: <integer>')
    )

    parser.add_argument(
        '-dp', '--dpi', metavar='DPI', dest='dpi',
        type=int, default=None,
        help=('Choose the DPI of the resulting plots.\n'
              'Format: <integer>')
    )

    parser.add_argument(
        '-mr', '--max-res', metavar='MR', dest='max_res',
        type=str, default=None,
        help=('The maximum resolution at which to show MAP.\n'
              'Format: auto | <integer>')
    )

    parser.add_argument(
        '-mc', '--metrics', metavar='CODES', dest='met_codes',
        type=str, default=None,
        help=('Metrics to enable:\n'+
              '\n'.join(
                  f'    {code.ljust(UI.metric_code_hpad)} : {defin}'
                  for code, defin in st.ALL_METRIC_CODES.items()
              )+'\n'
              '    all  : Include all metrics\n'
              'Format : all | <CODE>{,<CODE>}\n'
              'Example: MAP,CMR,CUR')
    )

    parser.add_argument(
        '-bm', '--background-metric', metavar='BG', dest='bg_metric',
        type=str, default=None,
        help=('Metric to use in the background plot.\n'
              'Format : none | <CODE>\n'
              "Example: MAP")
    )

    parser.add_argument(
        '-Lx', '--no-plot-last-x', dest='aggr_last_x',
        action='store_false',
        help=('If set, do not include vertical lines (and an extra average\n'
              'line) to denote the end of each execution contained in each\n'
              'PDATA file during aggregation mode.\n')
    )

    parser.add_argument(
        '-xr', '--x-ranges', metavar='XRANGES', dest='x_ranges',
        type=str, default=None,
        help=('Set a manual range for the X-axis. Useful to compare several\n'
              'individually produced plots.\n'
              'Format : full | <CODE>:<MIN>:<MAX>{,<CODE>:<MIN>:<MAX>}\n'
              '         Were <MIN> and <MAX> are numbers.\n'
              'Example: TLD:10:20,CMR:0:310,CMMA:1000:2000')
    )

    parser.add_argument(
        '-yr', '--y-ranges', metavar='YRANGES', dest='y_ranges',
        type=str, default=None,
        help=('Set a manual range for the Y-axis. Useful to compare several\n'
              'individually produced plots.\n'
              'Format : full | <CODE>:<MIN>:<MAX>{,<CODE>:<MIN>:<MAX>}\n'
              '         Were <MIN> and <MAX> are numbers.\n'
              'Example: TLD:0.3:0.7,CMR:20:30,CMMA:0:6000')
    )

    parser.add_argument(
        '-ps', '--plots-sizes', metavar='SIZES', dest='plots_sizes',
        type=str, default=None,
        help=('Set the width and height of individual plots. If not set, '
              '-pw and -ph are used.\n'
              'Format : default | <CODE>:<WIDTH>:<HEIGHT>{,<CODE>:<WIDTH>:<HEIGHT>}\n'
              'Example: CUR:5:3.5,CMMA:8:4')
    )

    parser.add_argument(
        '-xo', '--x-tick-ori', metavar='ORI', dest='x_orient',
        choices=['h', 'v'], default=None,
        help=('Orientation of the X-axis tick labels.\n'
              'Format: h | v')
    )

    parser.add_argument(
        '-Is', '--no-plot-individual-sets', dest='plot_indiv_sets',
        action='store_false',
        help=('If set, do not plot individual sets in BPA and SMRI.')
    )

    parser.add_argument(
        '-st', '--short-roundtrip-threshold', metavar='SRT', dest='rt_threshld',
        type=str, default=None,
        help=('Draw short memory roundtrip intervals (SMRI) of up to this '
              'length.\n'
              'Format: all | <integer>')
    )

    parser.add_argument(
        '-to', '--textbox-offsets', metavar='OFFSETS', dest='textbox_offsets',
        type=str, default=None,
        help=('Set the horizontal and vertical offset for text boxes in the\n'
              'plots. The range goes from 0 to 1 (left to right and bottom to\n'
              'top).\n'
              'Format : default | <CODE>:<HORIZ>:<VERT>{,<CODE>:<HORIZ>:<VERT>}\n'
              '         Were 0 < HORIZ,VERT < 1.\n'
              'Example: CUR:0.02:0.98,CMMA:0.9:0.9')
    )

    parser.add_argument(
        '-fr', '--format', metavar='FORMAT', dest='format',
        choices=['png', 'pdf'], default=None,
        help=('Choose the output format of the plots.\n'
              'Format: pdf | png')
    )

    # split before and after '--'
    if '--' in sys.argv:
        sep_index = sys.argv.index('--')
        before_double_dash = sys.argv[1:sep_index]
        after_double_dash = sys.argv[sep_index + 1:]
    else:
        before_double_dash = sys.argv[1:]
        after_double_dash = None

    # parse arguments before '--'
    known_args, other_args = parser.parse_known_args(before_double_dash)

    # and add things after '--' as input files
    known_args.input_files = after_double_dash

    # add argument for help message
    parser.add_argument(
        '--', metavar='INPUT-FILE', dest='input_files', nargs='+',
        type=str, default=None,
        help=('List of input files. Depending on the analysis "mode".')
    )

    return (known_args, other_args)

def median(full_list:list):
    med_idx = len(full_list) // 2
    if len(full_list) % 2 == 0:
        med = (full_list[med_idx-1] + full_list[med_idx]) / 2
    else:
        med = full_list[med_idx]
    return med
