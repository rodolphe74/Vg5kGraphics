#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
#  quadri.py
#
#  Copyright 2020 rodoc <rodoc@linux.home>
#
#  This program is free software; you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation; either version 2 of the License, or
#  (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with this program; if not, write to the Free Software
#  Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston,
#  MA 02110-1301, USA.
#
#

from PIL import Image
import os
import copy

# https://bisqwit.iki.fi/story/howto/dither/jy/#Appendix%202ThresholdMatrix

# divisor 8
BAYER_2x4 = (
    (0*32, 3*32),
    (4*32, 7*32),
    (2*32, 1*32),
    (6*32, 5*32)
)


BAYER_4x8 = (
    (0*8,  12*8,   3*8,  15),
    (16*8,  28*8,  19*8,  31),
    (8*8,   4*8,  11*8,   7),
    (24*8,  20*8,  27*8,  23),
    (2*8,  14*8,   1*8,  13),
    (18*8,  30*8,  17*8,  29),
    (10*8,   6*8,   9*8,   5),
    (26*8,  22*8,  25*8,  21)
)

VG5K_COLORS = (
    (255,255,255), 
    (0,255,255), 
    (255,0,255), 
    (0, 0, 255), 
    (255,255,0), 
    (0,255,0), 
    (255,0,0), 
    (0,0,0)
)

def get_palette():
    palette = []
    for i in range(len(VG5K_COLORS)):
        palette.append(VG5K_COLORS[i])
    return palette

def linear_space(x):
    x = x / 255
    if x <= 0.04045:
        y = x / 12.92
    else:
        y = ((x+0.055) / 1.055)**2.4
    return int(round(y * 255))

def find_closest_color(c, palette):
    diff = 100000
    closest = 0
    for i in range(0, len(palette)-1, 3):
        d = abs(c[0] - palette[i]) + abs(c[1] - palette[i+1]) + abs(c[2] - palette[i+2])
        # d = ((c[0] - palette[i])**2 + (c[1] - palette[i+1])**2 + (c[2] - palette[i+2])**2)**(0.5)
        if d < diff:
            diff = d
            closest = i
    return closest//3

def ordered_dither(im, bayer, palette):
    palette_data = []
    print(";palette size", len(palette))
    for i in range(0, len(palette)):
        for j in range(0, 3):
            color = palette[i]
            palette_data.append(color[j])
            
    dithered_color = [0, 0, 0]
    img = Image.new('P', (im.width, im.height))
    img.putpalette(palette_data * 32)
    pixels = im.load()
    for x in range(im.width):
        for y in range(im.height):
            c = pixels[x, y]
            if bayer is not None:
                map_value = bayer[y % len(bayer)][x % len(bayer[0])]
                dithered_color[0]  = linear_space(c[0]) + (map_value - 127)
                dithered_color[1]  = linear_space(c[1]) + (map_value - 127)
                dithered_color[2]  = linear_space(c[2]) + (map_value - 127)
                index = find_closest_color(dithered_color, palette_data)
            else:
                # pas de dithering
                index = find_closest_color(c, palette_data)
            img.putpixel((x,y), index)
    return img

def main(args):
    
    if len(sys.argv) <= 2:
        print("")
        print("I need the following arguments:")
        print("  * a picture filename")
        print("  * a gamma correction (eg. 0.8 clearer, 1.2 darker)")
        print("")
        exit()
    
    im = Image.open(sys.argv[1])
    im = im.convert("RGB")

    # gamma ?
    g = float(sys.argv[2])
    print(g)
    im = im.point(lambda x: ((x/255)**g)*255)
    im.save("im_gamma.png")

    im = ordered_dither(im, BAYER_2x4, get_palette())
    im.save("im_ordered.png")


if __name__ == '__main__':
    import sys
    sys.exit(main(sys.argv))