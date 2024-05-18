#!/usr/bin/env python3

def log2(x):
    return x.bit_length() - 1

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
    def format_addr(cls, address):
        tag, index, offset = cls.split(address)
        padded_bin = \
            "|T:"  + cls.pad(tag,    2, cls.max_tag)  +\
            "| I:" + cls.pad(index,  2, cls.max_index) +\
            "| O:" + cls.pad(offset, 2, cls.max_offset)+\
            "|"
        padded_hex = \
            "|T:"  + cls.pad(tag,    16, cls.max_tag)  +\
            "| I:" + cls.pad(index,  16, cls.max_index) +\
            "| O:" + cls.pad(offset, 16, cls.max_offset)+\
            "|"
        return ("bin:"+padded_bin, "hex:"+padded_hex)

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
