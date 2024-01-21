#!/usr/bin/env python3

def log2(x):
    return x.bit_length() - 1

class AddressFormatter:
    def __init__(self, specs):
        self.arch_size_bits = int(specs['arch'])
        line_size_bytes = int(specs['line'])
        cache_size_bytes = int(specs['size'])
        associativity = int(specs['asso'])

        self.offset_bits = int(log2(line_size_bytes))
        self.index_bits = int(log2(
            cache_size_bytes//(associativity*line_size_bytes)))
        self.tag_bits = int(
            self.arch_size_bits - self.index_bits - self.offset_bits)

        self.max_tag = 2**self.tag_bits - 1
        self.max_index = 2**self.index_bits - 1
        self.max_offset = 2**self.offset_bits - 1

    def format_addr(self, address):
        tag, index, offset = self.split(address)
        padded_bin = \
            "|T:"  + self.pad(tag,    2, self.max_tag)  +\
            "| I:" + self.pad(index,  2, self.max_index) +\
            "| O:" + self.pad(offset, 2, self.max_offset)+\
            "|"
        padded_hex = \
            "|T:"  + self.pad(tag,    16, self.max_tag)  +\
            "| I:" + self.pad(index,  16, self.max_index) +\
            "| O:" + self.pad(offset, 16, self.max_offset)+\
            "|"
        return ("bin:"+padded_bin, "hex:"+padded_hex)

    def split(self, address):
        # print(f"split: addr:{address}")
        offset_mask = (1 << self.offset_bits) - 1
        offset = address & offset_mask
        index_mask = (1 << self.index_bits) - 1
        index = (address >> self.offset_bits) & index_mask
        tag = address >> (self.index_bits + self.offset_bits)
        # print(f"split: t:{tag} i:{index} o:{offset}")
        return tag, index, offset

    def pad(self, number, base, max_val):
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
