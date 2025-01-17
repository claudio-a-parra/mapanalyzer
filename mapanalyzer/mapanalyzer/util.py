import os, json
import colorsys
import matplotlib.pyplot as plt

from mapanalyzer.settings import Settings as st

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

def save_fig(fig, code):
    filename=f'{st.Map.ID}.{code}_plot.{st.Plot.format}'
    print(f'    {code:{st.UI.metric_code_hpad}}: ', flush=True, end='')
    fig.savefig(filename, dpi=st.Plot.dpi, bbox_inches='tight',
                pad_inches=st.Plot.img_border_pad)
    print(f'{filename}')
    plt.close(fig)
    return

def save_json(data, code):
    filename=f'{st.Map.ID}.{code}_metric.json'
    print(f'    {code:{st.UI.metric_code_hpad}}: ', flush=True, end='')
    with open(filename, 'w') as f:
        json.dump(data, f)
    print(f'{filename}')
    return

def json_to_dict(json_path):
    if json_path is None:
        print('Error while reading json file: '
              'No file path provided.')
        exit(1)
    try:
        jfile = open(json_path, 'r')
    except:
        print(f'Error while reading {json_path}: '
              'File does not exist or cannot be read.')
        exit(1)
    jdict = json.load(jfile)
    jfile.close()
    if not all(key in jdict for key in st.metric_keys):
        print(f'Error while reading {json_path}: '
              'File does not seem to be a (complete) metric file. '
              'Not all first-level keys present.')
        exit(1)

    # enable only the metric specified by the file
    st.Plot.include = { jdict['metric']['code'] }
    return jdict

class PlotStrings:
    def __init__(self, title='Title', subtit='Subtitle', code='COD',
                 xlab='X-axis', ylab='Y-axis'):
        self.title = title
        self.subtit= subtit
        self.code = code
        self.xlab  = xlab
        self.ylab  = ylab

def hsl2rgb(h, s, l, a):
    try:
        h,s,l = float(h),float(s),float(l)
        if (not (0 <= h <= 360)) or \
           (not (0 <= s <= 100)) or \
           (not (0 <= l <= 100)) or \
           (not (0 <= a <= 100)):
            raise ValueError
    except ValueError:
        print('hsl2rgb(): Incorrect value given to either h, s, l, or a')
        exit(1)
    h,s,l,a = h/360.0, s/100.0, l/100.0, a/100.0
    r,g,b = colorsys.hls_to_rgb(h, l, s)
    r,g,b,a = round(r*255), round(g*255), round(b*255), round(a*255)
    return f'#{r:02X}{g:02X}{b:02X}{a:02X}'

class Palette:
    # create hsl palettes.
    # Palette(hue=<val>)
    # creates a single color at hue val.
    # - fg, bg, col
    #
    # Palette(hue=[])
    # creates again a fg and bg based on hue[0], but an array of colors
    # - fg(hue[0]), bg(hue[0]), col[]
    #
    # Palette(hue_count=n)
    # creates n colors
    # - fg(hue[0]), bg(hue[0]), col[n]
    def __init__(self, hue=0, hue_count=1,
                 saturation=[50], sat_count=1,
                 lightness=[50], lig_count=1,
                 alpha=[80], alp_count=1):
        # if hue is an array, then get its values. Otherwise, create an array
        # with hue_count evenly distributed values across the spectrum.
        if hasattr(hue, '__getitem__'):
            hues = [i%360 for i in hue]
        else:
            base = hue%360
            step = 360/hue_count
            hues = [(round(i*step)+base)%360 for i in range(hue_count)]

        # if saturation is an array, get its values.
        if hasattr(saturation, '__getitem__'):
            sats = saturation
        else:
            step = round(100/(saturation+1))
            sats = [i*step for i in range(1, saturation+1)]

        if hasattr(lightness, '__getitem__'):
            lights = lightness
        else:
            step = round(100/(lightness+1))
            lights = [i*step for i in range(1, lightness+1)]

        if hasattr(alpha, '__getitem__'):
            alphas = alpha
        else:
            alphas = [alpha] * len(lights)

        if not (len(sats) == len(lights) == len(alphas)):
            raise ValueError('If saturation, lightness or alpha are arrays, they have to be of the '
                             'same length. Otherwise provide integers')
        self.fg = hsl2rgb(hues[0], 100, 25, 100)
        self.bg = hsl2rgb(hues[0], 100, 100, 70)
        self.col = [
            [hsl2rgb(h,s,l,a) for s,l,a in zip(sats,lights,alphas)]
            for h in hues]
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
