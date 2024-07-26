import colorsys
import matplotlib.pyplot as plt
from settings import Settings as st

class AddrFmt:
    sp = None
    max_tag = None
    max_index = None
    max_offset = None

    @classmethod
    def init(cls, specs):
        AddrFmt.sp = specs
        AddrFmt.max_tag = 2**cls.sp.bits_tag - 1
        AddrFmt.max_index = 2**cls.sp.bits_set - 1
        AddrFmt.max_offset = 2**cls.sp.bits_off - 1

    @classmethod
    def bin(cls, address):
        tag, index, offset = cls.split(address)
        padded_bin = \
            "|T:"  + cls.pad(tag,    2, cls.max_tag)  +\
            "| I:" + cls.pad(index,  2, cls.max_index) +\
            "| O:" + cls.pad(offset, 2, cls.max_offset)+\
            "|"
        return padded_bin

    @classmethod
    def hex(cls, address):
        tag, index, offset = cls.split(address)
        padded_hex = \
            "|T:"  + cls.pad(tag,    16, cls.max_tag)  +\
            "| I:" + cls.pad(index,  16, cls.max_index) +\
            "| O:" + cls.pad(offset, 16, cls.max_offset)+\
            "|"
        return padded_hex

    @classmethod
    def split(cls, address):
        # print(f"split: addr:{address}")
        offset_mask = (1 << cls.sp.bits_off) - 1
        offset = address & offset_mask
        index_mask = (1 << cls.sp.bits_set) - 1
        index = (address >> cls.sp.bits_off) & index_mask
        tag = address >> (cls.sp.bits_set + cls.sp.bits_off)
        return tag, index, offset

    @classmethod
    def pad(cls, number, base, max_val):
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


def save_fig(fig, plot_title, plot_name_suffix):
    filename=f'{st.plot.prefix}{plot_name_suffix}.{st.plot.format}'
    print(f'    {plot_title:{st.plot.ui_title_hpad}}: {filename}')
    fig.savefig(filename, dpi=st.plot.dpi, bbox_inches='tight',
                pad_inches=st.plot.img_border_pad)
    plt.close(fig)
    return


class PlotStrings:
    def __init__(self, title='Title', xlab='X', ylab='Y', suffix='__plot',
                 subtit='Subtitle'):
        self.title = title
        self.xlab  = xlab
        self.ylab  = ylab
        self.suffix= suffix
        self.subtit= subtit


class Dbg:
    lv = 0
    step = 4

    @classmethod
    def P(cls, m='', ind=''):
        lines = Dbg.s(m=m)
        print(f'{ind}{lines}', end='')
        return

    @classmethod
    def p(cls, m=''):
        if st.verb:
            lines = Dbg.s(m=m)
            print(f'{lines}', end='')
        return

    @classmethod
    def s(cls, m=''):
        ind = ' ' * Dbg.lv
        if not isinstance(m, str) and hasattr(m, '__getitem__'):
            m_lines = [str(m.__class__)]
            for l in m:
                m_lines += [f' ├ {str(l)}']
            m_lines[-1] = f' └ {m_lines[-1][3:]}'
        else:
            m_lines = str(m).split('\n')

        # add indentation
        ret_val = ''
        for l in m_lines:
            if l == '' or l == '\n':
                continue
            ret_val += f'{ind}{l}\n'
        return ret_val

    @classmethod
    def i(cls):
        Dbg.lv += cls.step

    @classmethod
    def o(cls):
        Dbg.lv -= cls.step


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
    def __init__(self, hue=0, hue_count=1, saturation=[50], lightness=[50],
                 alpha=[80]):
        if hasattr(hue, '__getitem__'):
            hues = [i%360 for i in hue]
        else:
            base = hue%360
            step = 360/hue_count
            hues = [(round(i*step)+base)%360 for i in range(hue_count)]

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
