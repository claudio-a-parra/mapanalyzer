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
        # print(f"split: t:{tag} i:{index} o:{offset}")
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


def log2(x):
    return x.bit_length() - 1


def create_up_to_n_ticks(full_list, base=10, n=10):
    """
    return a list of ticks based on full_list. The idea is to find
    nice numbers (multiples of powers of 10 or 2) and not having
    more than n elements.
    """
    # if two ticks, return the extremes.
    if n == 2:
        return [full_list[0], full_list[-1]]

    # find a label_step such that we print at most n ticks
    tick_step = 1
    tot_ticks = len(full_list)
    factors = [1,2,2.5,5] if base==10 else [1,1.5]
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
    def p(cls, m=''):
        ind = ' ' * Dbg.lv
        if not isinstance(m, str) and hasattr(m, '__getitem__'):
            m_lines = [m.__class__()]
            for l in m:
                m_lines += [f'├{str(l)}']
            m_lines[-1] = f'└{m_lines[-1][1:]}'
        else:
            m_lines = str(m).split('\n')
        for l in m_lines:
            print(f'{ind}{l}')
        return
    @classmethod
    def i(cls):
        Dbg.lv += cls.step
    @classmethod
    def o(cls):
        Dbg.lv -= cls.step
