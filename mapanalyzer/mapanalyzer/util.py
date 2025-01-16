import os, json
import colorsys
import matplotlib.pyplot as plt
from itertools import combinations
from math import prod

from mapanalyzer.settings import Settings as st

def create_up_to_n_ticks(full_list, base=10, n=10):
    """
    return a list of ticks based on full_list. The idea is to find
    nice numbers (multiples of powers of 10 or 2) and not having
    more than n elements.
    """
    # if two ticks, return the extremes.
    if n == 2:
        return [full_list[0], full_list[-1]]

    if n == len(full_list):
        return full_list

    # find a label_step such that we print at most n ticks
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

def save_fig(fig, plotcode, plot_name_suffix):
    filename=f'{st.plot.prefix}{plot_name_suffix}.{st.plot.format}'
    print(f'    {plotcode:{st.plot.ui_plotname_hpad}}: ', flush=True, end='')
    fig.savefig(filename, dpi=st.plot.dpi, bbox_inches='tight',
                pad_inches=st.plot.img_border_pad)
    print(f'{filename}')
    plt.close(fig)
    return

def save_json(data, plotcode, plot_name_suffix):
    filename=f'{st.plot.prefix}{plot_name_suffix}.json'
    print(f'    {plotcode:{st.plot.ui_plotname_hpad}}: ', flush=True, end='')
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
        return jdict

class PlotStrings:
    def __init__(self, title='Title', code='PLT', xlab='X', ylab='Y',
                 suffix='__plot', subtit='Subtitle'):
        self.title = title
        self.code = code
        self.xlab  = xlab
        self.ylab  = ylab
        self.suffix= suffix
        self.subtit= subtit

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

def prime_factors(n):
    """Helper function to get prime factors"""
    factors = []
    while n % 2 == 0:
        factors.append(2)
        n //= 2
    for i in range(3, int(n**0.5) + 1, 2):
        while n % i == 0:
            factors.append(i)
            n //= i
    if n > 2:
        factors.append(n)
    return factors

def sub_resolution_between(native, min_res, max_res):
    """Find a good lower resolution"""
    if native < max_res:
        return native

    # Get the prime factors of the native resolution
    factors = prime_factors(native)

    # Generate all products of combinations of factors in descending order
    power_set = sorted(
        (prod(ps) for r in range(1, len(factors) + 1) for ps in combinations(factors, r)),
        reverse=True
    )

    # Find the largest valid resolution within the range
    for r in power_set:
        if min_res <= r < max_res:
            return r

    # If no suitable resolution is found, return max_res as a fallback
    return max_res
