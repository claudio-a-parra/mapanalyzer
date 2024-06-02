import colorsys

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
    def __init__(self, hue=0, saturation=80, lightness=50, alpha=50,
                 hue_count=1, saturation_count=2, lightness_count=2):
        if hasattr(hue, '__getitem__'):
            hues = hue
        else:
            base = hue
            step = 360/hue_count
            hues = [(round(i*step)+base)%360 for i in range(hue_count)]

        if hasattr(saturation, '__getitem__'):
            sats = saturation
        else:
            step = round(100/(saturation_count+1))
            sats = [i*step for i in range(1, saturation_count+1)]

        if hasattr(lightness, '__getitem__'):
            lights = lightness
        else:
            step = round(100/(lightness_count+1))
            lights = [i*step for i in range(1, lightness_count+1)]

        if hasattr(alpha, '__getitem__'):
            alphas = alpha
        else:
            alphas = [alpha] * len(lights)

        if len(lights) != len(alphas):
            raise ValueError('The array alpha must have the same number of '
                             'items as lightness')
        self.fg = hsl2rgb(hues[0], 100, 30, 100)
        self.bg = hsl2rgb(hues[0], 100, 99, 100)

        self.col = [[hsl2rgb(h,s,l,a) for s,l,a in zip(sats,lights,alphas)] for h in hues]
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
