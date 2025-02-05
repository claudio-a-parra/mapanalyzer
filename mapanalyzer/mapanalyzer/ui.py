from sys import stdout, stderr # to define where to write output
from colorama import Fore, Style # for colored messages
from itertools import zip_longest # to print columns of different lengths

class UI:
    ############################################################
    #### CONSTANT VALUES
    metric_code_hpad = 5 # space needed to print any metric code
    il = 0 # indentation level
    iw = 4 # indentation width
    ind = '' # the actual indentation string

    @classmethod
    def __color_msg(cls, msg='', symb='', indent=True, ind_str='', pre='',
                    msg_color=Fore.RESET, end='\n', out=stdout):
        """Message has some parts:
        .------+-------------------------------------- indentation
        |      |
             [!]WARNING: the message I want to say\n
              |    |              |                +-- end
              |    |              +------------------- message
              |    +---------------------------------- pre-message
              +--------------------------------------- symbol
        """
        # determine indentation string.
        if indent and len(msg) > 0:
            # if a manual indentation string has been given
            if len(ind_str) > 0:
                pass
            else:
                ind_str = cls.ind
        else:
            ind_str = ''

        # make symbol bold
        symb = f'{Style.BRIGHT}{symb}{Style.NORMAL}'

        # add ': ' to pre-message
        if len(msg) > 0 and len(pre) > 0:
            pre = f'{Style.BRIGHT}{pre}{Style.NORMAL}: '

        # Add indentation to all lines of the message
        second_line_ind = ''
        msg_lines = msg.split('\n')
        msg = f'\n{cls.ind}{second_line_ind}'.join(msg_lines)

        # print message
        print(f'{msg_color}{ind_str}{symb}{pre}{msg}{Style.RESET_ALL}',
              file=out, end=end)

        if end != '\n':
            out.flush()
        return

    @classmethod
    def indent_in(cls, title='', left='', right='',
                  bold=True):
        """Increase indentation with a possible title"""
        if title:
            msg_str = f'{Style.BRIGHT}{left}{title}{right}{Style.NORMAL}'
            cls.__color_msg(msg=msg_str, msg_color=f'{Fore.GREEN}', out=stdout)
        cls.il += 1
        cls.ind = ' ' * (cls.il*cls.iw)
        return

    @classmethod
    def indent_out(cls):
        """decrease indentation"""
        cls.il = max(cls.il - 1, 0)
        cls.ind = ' ' * (cls.il*cls.iw)
        return

    @classmethod
    def indent_set(cls, ind=0):
        """set indentation directly"""
        cls.il = max(ind, 0)
        cls.ind = ''
        return

    @classmethod
    def error(cls, msg, symb='', pre='ERROR', do_exit=True, code=1):
        """print an error message to stderr and possibly exit with a
        given code"""
        cls.__color_msg(msg=msg, symb=symb, pre=pre, msg_color=Fore.RED,
                        out=stderr)

        # exit if requested
        if code == 0:
            code = 1
        if do_exit:
            exit(code)
        return

    @classmethod
    def warning(cls, msg, symb='', pre='WARNING'):
        """print a warning message to stderr"""
        cls.__color_msg(msg=msg, symb=symb, pre=pre, msg_color=Fore.YELLOW,
                        out=stderr)
        return

    @classmethod
    def info(cls, msg, symb='', pre='INFO', out='err'):
        """print an informative message to (by default) stderr"""
        if out == 'out':
            out = stdout
        else:
            out = stderr
        cls.__color_msg(msg=msg, symb=symb, pre=pre, msg_color=Fore.CYAN,
                        out=out)
        return

    @classmethod
    def text(cls, msg, indent=True, end='\n', out='out'):
        """print regular text to (by default) stdout and respecting the
        current indentation level."""
        if out == 'out':
            out = stdout
        else:
            out = stderr
        cls.__color_msg(msg=msg, indent=indent, end=end, out=out)
        return

    @classmethod
    def nl(cls, out='out'):
        """print a new line '\n' by default to stdout"""
        if out == 'out':
            out = stdout
        else:
            out = stderr
        cls.__color_msg(out=out)
        return

    @classmethod
    def progress(cls, count, total):
        """print a progress ratio that overwrites the same (current) line"""
        step = max(total // 200, 1)
        if count % step == 0 or count == total:
            cls.__color_msg(msg=f'{(100*count/total):5.1f}% {count:8d}/{total}',
                            ind_str=f'\033[2K\r{cls.ind}', end='', out=stdout)
        return

    @classmethod
    def columns(cls, cols, sep='', cols_width='auto', cols_align='l',
                header=False, get_str=False):
        """Print a table with columns. If cols_width is auto, then
        compute each column width, otherwise, use the values given
        in cols_width (array_like, with one integer per column of cols)"""
        if len(cols) == 0:
            cls.error('UI.columns: Printing empty array.')

        # if auto column width, then compute it. Otherwise, use the given one
        if cols_width == 'auto':
            cols_width = []
            for col in cols:
                col_width = 0
                for text in col:
                    col_width = max(col_width,len(str(text)))
                cols_width.append(col_width)
        else:
            if len(cols_width) != len(cols):
                cls.error(f'UI.columns(): cols_width is not \'auto\'. Then, '
                          f'the number of columns ({len(cols)}) and number of '
                          f'cols_width values {len(cols_width)} is not the '
                          'same.')


        if cols_align == 'l':
            cols_align = 'l' * len(cols)
        elif cols_align == 'r':
            cols_align = ['r' for _ in cols]
        else:
            if len(cols_align) != len(cols):
                cls.error(f'UI.columns(): cols_align is not \'l\' or \'r\'. '
                          f'Then, the number of columns ({len(cols)}) and '
                          f'number of cols_align values {len(cols_align)} '
                          'is not the same.')

        # Create rows
        all_lines = []
        for elems in zip_longest(*cols, fillvalue=''):
            # compose line
            line_elems = []
            for i,el in enumerate(elems):
                if cols_align[i] == 'l':
                    elem = str(el).ljust(cols_width[i])
                elif cols_align[i] == 'r':
                    elem = str(el).rjust(cols_width[i])
                else:
                    cls.error('UI.columns(): Unknown value in '
                              f'cols_align[{i}] = {cols_align[i]}.')

                line_elems.append(elem)
            line_text = sep.join(line_elems)
            all_lines.append(line_text)

        # do we have headers?
        if header:
            all_lines[0] = f'{Style.BRIGHT}{all_lines[0]}{Style.NORMAL}'

        # join lines and print them
        table = '\n'.join(all_lines)

        if not get_str:
            cls.__color_msg(msg=table)

        return table
