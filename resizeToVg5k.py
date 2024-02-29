#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
#  resizeToVg5k.py
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

def main(args):
    
    if len(sys.argv) <= 1:
        print("")
        print("I need the following arguments:")
        print("  * a picture filename")
        print("")
        exit()
    
    im = Image.open(sys.argv[1])
    im = im.convert("RGB")

    width, height = im.size
    new_width, new_height = 0, 0
    new_frame_width, new_frame_height = 0, 0

    print("size", width, height)

    do_resize = False
    ratio_x = 1.0
    ratio_y = 1.0
    new_width = width
    new_height = height

    if width >= 160:
        ratio_x = width / 320
        do_resize = True
    if height >= 250:
        ratio_y = height / 250.0;
        do_resize = True


    if do_resize == True:
        ratio = max(ratio_x, ratio_y);
        print(ratio, ratio_x, ratio_y)
        new_width = width / (ratio * 2)
        new_height = height / ratio



    # resize
    print("vg5k size", new_width, new_height)
    im_resized = im.resize((int(new_width), int(new_height)))
    im_resized.save("im_resized.png")

    # reframe
    gap_width = int(max(0, (160 - new_width) / 2))
    gap_height = int(max(0, (250 - new_height) / 2))
    print("margin", gap_width, gap_height)
    im_reframed = Image.new("RGB", (160, 250))
    im_reframed.paste(im_resized, (0 + gap_width, 0 + gap_height, int(new_width) + gap_width, int(new_height) + gap_height))
    im_reframed.save("im_reframed.png")


if __name__ == '__main__':
    import sys
    sys.exit(main(sys.argv))