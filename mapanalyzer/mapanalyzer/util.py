import os, json
import colorsys # to convert from hls to rgb
import matplotlib.pyplot as plt
import argparse # to get command line arguments

from mapanalyzer.settings import Settings as st
from mapanalyzer.ui import UI

class MetricStrings:
    def __init__(self, title='Title', subtit='Subtitle', numb='00', code='COD',
                 xlab='X-axis', ylab='Y-axis'):
        self.title = title
        self.subtit= subtit
        self.code = code
        self.xlab  = xlab
        self.ylab  = ylab
        self.number = numb
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
                UI.error('Hue count cannot be less than 1.')
            step = 360/hue
            hue_list = [(round(i*step)+hue0)%360 for i in range(hue)]

        # determine the list of saturation values
        if hasattr(sat, '__getitem__'):
            sat_list = [max(min(i,100),0) for i in sat]
        else:
            if sat < 1:
                UI.error('Saturation count cannot be less than 1.')
            sat_range = 100 - s_off
            step = round(sat_range/(sat+1))
            sat_list = [sat_off+i*step for i in range(1, sat+1)]

        # determine the list of lightness values
        if hasattr(lig, '__getitem__'):
            lig_list = [max(min(i,100),0) for i in lig]
        else:
            if lig < 1:
                UI.error('Lighting count cannot be less than 1.')
            lig_range = 100 - l_off
            step = round(lig_range/(lig+1))
            lig_list = [lig_off+i*step for i in range(1, lig+1)]

        # determine the list of alpha values
        if hasattr(alp, '__getitem__'):
            alp_list = [max(min(i,100),0) for i in alp]
        else:
            if alp < 1:
                UI.error('Alpha count cannot be less than 1.')
            alp_range = 100 - a_off
            step = round(alp_range/(alp+1))
            alp_list = [alp_off+i*step for i in range(1, alp+1)]

        self.fg = self.__hsl2rgb(hue_list[0], 75,  10, 100)
        self.bg = self.__hsl2rgb(hue_list[0], 100, 100, 90)
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

    """iterates over the map file, reading one record at the time."""
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

def create_up_to_n_ticks(full_list, base=10, n=10):
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
    for i in range(14):
        found = False
        for f in factors:
            f_pow_base = int(f * (base ** i))
            if int(tot_ticks / f_pow_base) <= (n-1):
                tick_step = f_pow_base
                found = True
                break
        if found:
            break

    tick_list = full_list[::tick_step]
    return tick_list

def save_metric(data, metric_strings:MetricStrings):
    code = metric_strings.code
    number = metric_strings.number
    filename=f'{st.Map.ID}.metric_{number}_{code}.json'
    UI.text(f'{code.ljust(UI.metric_code_hpad)}: ', end='')
    with open(filename, 'w') as f:
        json.dump(data, f)
    UI.text(filename, indent=False)
    return

def __save_plot(fig, metric_strings:MetricStrings, type_prefix='plot'):
    code = metric_strings.code
    number = metric_strings.number
    id_prefix = ''
    if st.Map.ID != '':
        id_prefix = f'{st.Map.ID}.'
    filename=f'{id_prefix}{type_prefix}_{number}_{code}.{st.Plot.format}'

    # save file
    UI.text(f'{code.ljust(UI.metric_code_hpad)}: ', end='')
    fig.savefig(filename, dpi=st.Plot.dpi, bbox_inches='tight',
                pad_inches=st.Plot.img_border_pad)
    UI.text(filename, indent=False)
    plt.close(fig)
    return

def save_aggr(fig, metric_strings:MetricStrings):
    __save_plot(fig, metric_strings, type_prefix='aggr')
    return

def save_plot(fig, metric_strings:MetricStrings):
    __save_plot(fig, metric_strings, type_prefix='plot')
    return

def load_json(json_path):
    """open and verify this is a json file"""
    if json_path is None:
        UI.error(f'While reading "{json_path}":\n'
                 'No file path provided.')
    try:
        json_file = open(json_path, 'r')
    except (FileNotFoundError, IOError):
        UI.error(f'While reading "{json_path}":\n'
                 'File does not exist or cannot be read.')
    try:
        j_dict = json.load(json_file)
    except json.JSONDecodeError:
        UI.error(f'While reading "{json_path}":\n'
                 'File does not seem to be a valid JSON file.')
    json_file.close()
    return j_dict

def missing_keys(met_dict):
    """Verify that all first level keys are present"""
    missing_keys = []
    mk_str = ''
    for k in st.metric_keys:
        if k not in met_dict:
            missing_keys.append(k)
    if len(missing_keys) > 0:
        missing_keys = [f' - "{k}"' for k in missing_keys]
        mk_str = '\n'.join(missing_keys)
    return mk_str

def load_metric(metric_path):
    met_dict = load_json(metric_path)
    mk_str = missing_keys(met_dict)
    if len(mk_str) > 0:
        UI.error(f'While reading "{metric_path}:"\n'
                 'File does not seem to be a (complete) metric file. '
                 'Not all first-level keys present. Necessary keys:\n'
                 f'{mk_str}')
    # enable only the metric specified by the file
    st.Plot.include = { met_dict['metric']['code'] }
    return met_dict

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
                '  Run cache simulation with a given configuration and produce '
                'metric and plot results:\n'
                '      mapanalyzer --cache mycache.conf -- myexperiment.map\n'
                '\n'
                '  Plot the results of a previously simulated cache:\n'
                '      mapanalyzer --mode plot -- myexperiment.metric.json\n'
                '\n'
                '  Aggregate three different runs of the same experiment into '
                'a single plot:\n'
                '      mapanalyzer --mode aggregate -- run1.metric.json '
                'run2.metric.json run3.metric.json\n')

    signature = ('By Claudio A. Parra. 2025.\n'
                 'parraca@uci.edu')

    parser = argparse.ArgumentParser(
        description=synopsis+'\n\n',
        epilog=cache_conf+'\n\n'+examples+'\n\n'+signature,
        formatter_class=argparse.RawTextHelpFormatter)

    # Adding arguments
    parser.add_argument(
        metavar='INPUT-FILE', dest='input_files', nargs='+',
        type=str, default=None,
        help=('List of input files. Depending on the analysis '
              '"mode", they are either MAP or METRIC type.')
    )

    parser.add_argument(
        '--mode', metavar='MODE', dest='mode',
        choices=['simulate', 'plot', 'sim-plot', 'aggregate'],
        type=str, default=None,
        help=(
            'Defines the operation mode of the tool:\n'
            'simulate  : Only run the cache simulation. You must provide a\n'
            '            list of MAP files. Generates METRIC files.\n'
            'plot      : Plot already obtained metric data. One plot per\n'
            '            input file. You must provide a list of METRIC files.\n'
            '            Generates PLOT files.\n'
            'sim-plot  : (default) Simulate cache and plot results. Generates\n'
            '            METRIC and PLOT files.\n'
            'aggregate : Plot the aggregation of multiple metric data files,\n'
            '            aggregating the ones of the same kind. You must\n'
            '            provide a list of METRIC files.\n')
    )

    parser.add_argument(
        '-ca', '--cache', metavar='CACHE', dest='cachefile',
        type=str, default=None,
        help='File describing the cache. See "cache.conf" section.'
    )

    parser.add_argument(
        '-pw', '--plot-width', metavar='WIDTH', dest='plot_width',
        type=float, default=None,
        help=("Width of the plots.\n"
              "Format: integer")
    )

    parser.add_argument(
        '-ph', '--plot-height', metavar='HEIGHT', dest='plot_height',
        type=float, default=None,
        help=("Height of the plots.\n"
              "Format: integer")
    )

    parser.add_argument(
        '-dp', '--dpi', metavar='DPI', dest='dpi',
        type=int, default=None,
        help=("Choose the DPI of the resulting plots.\n"
              "Format: integer")
    )

    parser.add_argument(
        '-mr', '--max-res', metavar='MR', dest='max_res',
        type=str, default=None,
        help=("The maximum resolution at which to show MAP.\n"
              "Format: integer | 'auto'")
    )

    parser.add_argument(
        '-pl', '--plots', metavar='PLOTCODES', dest='plotcodes',
        type=str, default=None,
        help=('Plots to obtain:\n'+
              '\n'.join(
                  f'    {code:4} : {defin}'
                  for code, defin in st.Plot.PLOTCODES.items()
              )+'\n'
              '    all  : Include all metrics\n'
              'Format: "all" | PLOTCODE{,PLOTCODE}\n'
              'Example: "MAP,CMR,CUR"')
    )

    parser.add_argument(
        '-xr', '--x-ranges', metavar='XRANGES', dest='x_ranges',
        type=str, default=None,
        help=("Set a manual range for the X-axis. Useful to compare several "
              "individually produced plots.\n"
              "Given that TLD is rotated, XRANGE restrict the Y-axis.\n"
              "Format: 'full' | PLOTCODE:MIN:MAX{,PLOTCODE:MIN:MAX}\n"
              "Example: 'TLD:10:20,CMR:0:310,CMMA:1000:2000'")
    )

    parser.add_argument(
        '-yr', '--y-ranges', metavar='YRANGES', dest='y_ranges',
        type=str, default=None,
        help=("Set a manual range for the Y-axis. Useful to compare several "
              "individually produced plots.\n"
              "Given that TLD is rotated, YRANGE restrict the X-axis.\n"
              "Format: 'full' | PLOTCODE:MIN:MAX{,PLOTCODE:MIN:MAX}\n"
              "Example: 'TLD:0.3:0.7,CMR:20:30,CMMA:0:6000'")
    )

    parser.add_argument(
        '-xo', '--x-tick-ori', metavar='ORI', dest='x_orient',
        choices=['h', 'v'], default=None,
        help=("Orientation of the X-axis tick labels.\n"
              "Format: 'h' | 'v'")
    )

    parser.add_argument(
        '-fr', '--format', metavar='FORMAT', dest='format',
        choices=['png', 'pdf'], default=None,
        help=("Choose the output format of the plots.\n"
              "Format: 'pdf' | 'png'")
    )

    args = parser.parse_args()
    return args
