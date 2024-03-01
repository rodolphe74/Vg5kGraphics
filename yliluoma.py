#!python
# -*- mode: python; Encoding: utf-8; coding: utf-8 -*-
# Last updated: <2022/07/13 01:32:08 +0900>
"""
Yliluoma's ordered dithering algorithm 1, 2, 3 and adobe like

Arbitrary-palette positional dithering algorithm
https://bisqwit.iki.fi/story/howto/dither/jy/

Usage:
    py ThisScript.py -i INPUT.png -o OUTPUT.png [-m num] [-d num] [-c] [-p PALETTE]

-m num, --mode num : 0-5
                     0=1a, 1=1ba, 2=1bb,
                     3=faster,
                     4=tri-tone,
                     5=algorithm 2,
                     6=algorithm 2 gamma correct,
                     7=algorithm 3
                     8=adobe like pattern dither

-d num, --dither num : 2 or 4 or 8 (Dither 2x2, 4x4, 8x8)
-c, --ciede2000 : enable CIEDE2000 (mode 6 and 7)
-p PALETTE, --palette PALETTE : Palette file (.png or .gpl)

Windows10 x64 21H2 + Python 3.9.13 64bit
"""

import os
import sys
from PIL import Image
from tqdm import tqdm
import argparse
import copy
import math
import re

gamma = 2.2  # Gamma correction we use.

dithermaps = {
    2: [
        [0, 2],
        [3, 1]
    ],
    4: [
        [0, 8, 2, 10],
        [12, 4, 14, 6],
        [3, 11, 1, 9],
        [15, 7, 13, 5]
    ],
    8: [
        [0, 48, 12, 60, 3, 51, 15, 63],
        [32, 16, 44, 28, 35, 19, 47, 31],
        [8, 56, 4, 52, 11, 59, 7, 55],
        [40, 24, 36, 20, 43, 27, 39, 23],
        [2, 50, 14, 62, 1, 49, 13, 61],
        [34, 18, 46, 30, 33, 17, 45, 29],
        [10, 58, 6, 54, 9, 57, 5, 53],
        [42, 26, 38, 22, 41, 25, 37, 21]
    ]
}

# pal = [
#     0x080000, 0x201A0B, 0x432817, 0x492910,
#     0x234309, 0x5D4F1E, 0x9C6B20, 0xA9220F,
#     0x2B347C, 0x2B7409, 0xD0CA40, 0xE8A077,
#     0x6A94AB, 0xD5C4B3, 0xFCE76E, 0xFCFAE2
# ]
#
# def pal2rgb():
#     lst = []
#     for v in pal:
#         r, g, b = (v >> 16), ((v >> 8) & 0x0ff), (v & 0x0ff)
#         lst.append((r, g, b))
#     return lst

pal = [
    # (r, g, b)
    (8, 0, 0), (32, 26, 11), (67, 40, 23), (73, 41, 16),
    (35, 67, 9), (93, 79, 30), (156, 107, 32), (169, 34, 15),
    (43, 52, 124), (43, 116, 9), (208, 202, 64), (232, 160, 119),
    (106, 148, 171), (213, 196, 179), (252, 231, 110), (252, 250, 226)
]

# CIE C illuminant
illum = [
    0.488718, 0.176204, 0.000000,
    0.310680, 0.812985, 0.0102048,
    0.200602, 0.0108109, 0.989795
]


class Palette:
    """ Palette class. """

    def __init__(self, filename):
        _, ext = os.path.splitext(filename)
        if ext == ".gpl":
            # GIMP palette file
            self.get_palette_from_gpl(filename)
        elif ext == ".png" or ext == ".gif":
            self.get_palette_from_image(filename)
        else:
            print("Error: Unsupported file = %s" % filename)
            sys.exit()

    def get_palette_from_gpl(self, filename):
        """ Get palette data from GIMP palette file (.gpl) """
        with open(filename) as f:
            data = f.read()
        lst = data.splitlines()

        self.colors = []
        self.palette = []
        for s in lst:
            if re.match(r"^\s*#", s):
                continue
            if re.match("^GIMP Palette", s):
                continue
            m = re.match(r"^Name:\s*(.+)$", s)
            if m:
                # print("Palette name: %s" % m.groups()[0])
                continue
            if re.match(r"^Columns", s):
                continue
            m = re.match(r"^\s*(\d+)\s+(\d+)\s+(\d+)", s)
            if m:
                r, g, b = m.groups()
                r = int(r)
                g = int(g)
                b = int(b)
                self.palette.append((r, g, b))

    def get_palette_from_image(self, filename):
        """ Get palette data from image. """
        im = Image.open(filename)
        w, h = im.size

        # print("# im.mode = %s" % im.mode)
        # print("%d x %d" % im.size)

        self.colors = []
        self.palette = []

        if im.mode == "P":
            # index color image
            cols = im.getcolors()
            p = im.getpalette()

            if p is None:
                print("Error: Not found palette.")
                sys.exit()

            for cnt, i in cols:
                r, g, b = p[i * 3], p[i * 3 + 1], p[i * 3 + 2]
                self.palette.append((r, g, b))
                self.colors.append((cnt, (r, g, b)))

        elif im.mode == "RGB":
            # RGB image
            rgb_count = {}
            src = im.load()
            for y in range(h):
                for x in range(w):
                    col = src[x, y]
                    if col in rgb_count:
                        rgb_count[col] += 1
                    else:
                        rgb_count[col] = 1
            self.palette = list(rgb_count.keys())

            for c in self.palette:
                cnt = rgb_count[c]
                self.colors.append((cnt, c))

        else:
            print("Error: Unsupported image mode = %s" % im.mode)
            sys.exit()

    def count(self):
        return sorted(self.colors, key=lambda x: x[0], reverse=True)


def gamma_correct(v):
    return pow(v, gamma)


def gamma_uncorrect(v):
    return pow(v, 1.0 / gamma)


class LabItem:
    """ CIE L*a*b* color value with C and h added. """

    def __init__(self, r, g, b, divide):
        self.set(r / divide, g / divide, b / divide)

    def set(self, r, g, b):
        xx = illum[0] * r + illum[3] * g + illum[6] * b
        yy = illum[1] * r + illum[4] * g + illum[7] * b
        zz = illum[2] * r + illum[5] * g + illum[8] * b
        x = xx / (illum[0] + illum[1] + illum[2])
        y = yy / (illum[3] + illum[4] + illum[5])
        z = zz / (illum[6] + illum[7] + illum[8])

        threshold1 = (6 * 6 * 6.0) / (29 * 29 * 29.0)
        threshold2 = (29 * 29.0) / (6 * 6 * 3.0)

        x1 = pow(x, 1.0 / 3.0) if x > threshold1 else ((threshold2 * x) + (4 / 29.0))
        y1 = pow(y, 1.0 / 3.0) if y > threshold1 else ((threshold2 * y) + (4 / 29.0))
        z1 = pow(z, 1.0 / 3.0) if z > threshold1 else ((threshold2 * z) + (4 / 29.0))

        self.lum = (29 * 4) * y1 - (4 * 4)
        self.a = 500 * (x1 - y1)
        self.b = 200 * (y1 - z1)

        ct = self.a * self.a + self.b + self.b
        # ct = self.a * self.a + self.b * self.b
        if ct < 0:
            ct = 0
        self.c = math.sqrt(ct)
        self.h = math.atan2(self.b, self.a)


def color_compare(r1, g1, b1, r2, g2, b2):
    """ Compare the difference of two RGB values. """
    r = (r1 - r2) / 255.0
    g = (g1 - g2) / 255.0
    b = (b1 - b2) / 255.0
    return r * r + g * g + b * b


def color_compare_ccir601(r1, g1, b1, r2, g2, b2):
    """
    Compare the difference of two RGB values.
    weigh by CCIR 601 luminosity.
    """
    luma1 = (r1 * 299 + g1 * 587 + b1 * 114) / (255.0 * 1000.0)
    luma2 = (r2 * 299 + g2 * 587 + b2 * 114) / (255.0 * 1000.0)
    lumad = luma1 - luma2
    r = (r1 - r2) / 255.0
    g = (g1 - g2) / 255.0
    b = (b1 - b2) / 255.0
    return (r * r * 0.299 + g * g * 0.587 + b * b * 0.114) * 0.75 + lumad * lumad


def color_compare_ciede2000(lab1, lab2):
    """
    From the paper "The CIEDE2000 Color-Difference Formula: Implementation Notes,
    Supplementary Test Data, and Mathematical Observations",
    by Gaurav Sharma, Wencheng Wu and Edul N. Dalal,
    Color Res. Appl., vol. 30, no. 1, pp. 21-30, Feb. 2005.
    Return the CIEDE2000 Delta E color difference measure squared, for two Lab values
    """

    # Compute Cromanance and Hue angles
    cab = 0.5 * (lab1.c + lab2.c)
    cab7 = pow(cab, 7.0)
    g = 0.5 * (1.0 - math.sqrt(cab7 / (cab7 + 6103515625.0)))
    a1 = (1.0 + g) * lab1.a
    a2 = (1.0 + g) * lab2.a
    c1 = math.sqrt(a1 * a1 + lab1.b * lab1.b)
    c2 = math.sqrt(a2 * a2 + lab2.b * lab2.b)

    if c1 < 1e-9:
        h1 = 0.0
    else:
        h1 = math.degrees(math.atan2(lab1.b, a1))
        if h1 < 0.0:
            h1 += 360.0

    if c2 < 1e-9:
        h2 = 0.0
    else:
        h2 = math.degrees(math.atan2(lab2.b, a2))
        if h2 < 0.0:
            h2 += 360.0

    # Compute delta L, C and H
    dl = lab2.lum - lab1.lum
    dc = c2 - c1

    if c1 < 1e-9 or c2 < 1e-9:
        dhh = 0.0
    else:
        dhh = h2 - h1
        if dhh > 180.0:
            dhh -= 360.0
        elif dhh < -180.0:
            dhh += 360.0
    dh = 2.0 * math.sqrt(c1 * c2) * math.sin(math.radians(0.5 * dhh))

    lum = 0.5 * (lab1.lum + lab2.lum)
    c = 0.5 * (c1 + c2)
    if c1 < 1e-9 or c2 < 1e-9:
        h = h1 + h2
    else:
        h = h1 + h2
        if abs(h1 - h2) > 180.0:
            if h < 360.0:
                h += 360.0
            elif h >= 360.0:
                h -= 360.0
        h *= 0.5

    t = 1.0 \
        - 0.17 * math.cos(math.radians(h - 30.0)) \
        + 0.24 * math.cos(math.radians(2.0 * h)) \
        + 0.32 * math.cos(math.radians(3.0 * h + 6.0)) \
        - 0.2 * math.cos(math.radians(4.0 * h - 63.0))

    hh = (h - 275.0) / 25.0
    ddeg = 30.0 * math.exp(-hh * hh)
    c7 = pow(c, 7.0)
    rc = 2.0 * math.sqrt(c7 / (c7 + 6103515625.0))
    l50sq = (lum - 50.0) * (lum - 50.0)
    sl = 1.0 + (0.015 * l50sq) / math.sqrt(20.0 + l50sq)
    sc = 1.0 + 0.045 * c
    sh = 1.0 + 0.015 * c * t
    rt = -math.sin(math.radians(2 * ddeg)) * rc
    dlsq = dl / sl
    dcsq = dc / sc
    dhsq = dh / sh

    return dlsq * dlsq + dcsq * dcsq + dhsq * dhsq + rt * dcsq * dhsq


def evaluate_mixing_error(r, g, b, r0, g0, b0, r1, g1, b1, r2, g2, b2, ratio, mode):
    """
    Args:
        r, g, b int: Desired color
        r0, g0, b0 int: Mathematical mix product
        r1, g1, b1 int: Mix component 1
        r2, g2, b2 int: Mix component 2
        ratio float: Mixing ratio
        mode int: 0=1a, 1=1ba, 2=1bb, 3=1c, 4=1d
    """
    if mode == 0:
        # 0: 1a
        return color_compare(r, g, b, r0, g0, b0)
    elif mode == 1:
        # 1: 1ba
        cc0 = color_compare(r, g, b, r0, g0, b0)
        cc1 = color_compare(r1, g1, b1, r2, g2, b2)
        return cc0 + cc1 * 0.1
    else:
        # 2, 3, 4: use CCIR 601
        cc0 = color_compare_ccir601(r, g, b, r0, g0, b0)
        cc1 = color_compare_ccir601(r1, g1, b1, r2, g2, b2)
        return cc0 + cc1 * 0.1 * (abs(ratio - 0.5) + 0.5)


def devise_best_mixing_plan(col, mode, d_range, pal):
    r, g, b = col
    r_colors = [0, 0]
    r_ratio = 0.5
    least_penalty = 1e99

    # Loop through every unique combination of two colors from the palette,
    # and through each possible way to mix those two colors.
    # They can be mixed in exactly 64 ways, when the threshold matrix is 8x8.

    len_pal = len(pal)
    for index1 in range(len_pal):
        for index2 in range(index1, len_pal, 1):
            for ratio in range(d_range):
                if index1 == index2 and ratio != 0:
                    break

                # Determine the two component colors
                r1, g1, b1 = pal[index1]
                r2, g2, b2 = pal[index2]

                # Determine what mixing them in this proportion will produce
                r0 = r1 + ratio * (r2 - r1) // d_range
                g0 = g1 + ratio * (g2 - g1) // d_range
                b0 = b1 + ratio * (b2 - b1) // d_range

                # Determine how well that matches what we want to accomplish
                penalty = evaluate_mixing_error(r, g, b,
                                                r0, g0, b0,
                                                r1, g1, b1,
                                                r2, g2, b2,
                                                ratio / d_range, mode)

                if penalty < least_penalty:
                    # Keep the result that has the smallest error
                    least_penalty = penalty
                    r_colors[0] = index1
                    r_colors[1] = index2
                    r_ratio = ratio / d_range

    return (r_colors, r_ratio)


def devise_best_mixing_plan_fast(col, mode, d_range, pal):
    r, g, b = col
    r_colors = [0, 0]
    r_ratio = 0.5
    least_penalty = 1e99

    len_pal = len(pal)
    for index1 in range(len_pal):
        for index2 in range(index1, len_pal, 1):
            # Determine the two component colors
            color1 = pal[index1]
            color2 = pal[index2]
            r1, g1, b1 = color1
            r2, g2, b2 = color2
            ratio = d_range / 2
            if color1 != color2:
                # Determine the ratio of mixing for each channel.
                # solve(r1 + ratio*(r2-r1)/64 = r, ratio)
                # Take a weighed average of these three ratios according to the
                # perceived luminosity of each channel (according to CCIR 601).

                if r2 != r1:
                    rr = (299 * d_range * int(r - r1) / int(r2 - r1))
                    rd = 299
                else:
                    rr = 0
                    rd = 0

                if g2 != g1:
                    gg = (587 * d_range * int(g - g1) / int(g2 - g1))
                    gd = 587
                else:
                    gg = 0
                    gd = 0

                if b2 != b1:
                    bb = (114 * d_range * int(b - b1) / int(b2 - b1))
                    bd = 114
                else:
                    bb = 0
                    bd = 0

                ratio = (rr + gg + bb) / (rd + gd + bd)
                if ratio < 0:
                    ratio = 0
                elif ratio > (d_range - 1):
                    ratio = d_range - 1

            # Determine what mixing them in this proportion will produce
            r0 = r1 + ratio * int(r2 - r1) / d_range
            g0 = g1 + ratio * int(g2 - g1) / d_range
            b0 = b1 + ratio * int(b2 - b1) / d_range

            penalty = evaluate_mixing_error(
                r, g, b, r0, g0, b0, r1, g1, b1, r2, g2, b2, ratio / d_range, 2)

            if penalty < least_penalty:
                least_penalty = penalty
                r_colors[0] = index1
                r_colors[1] = index2
                r_ratio = ratio / d_range

    return (r_colors, r_ratio)


def devise_best_mixing_plan_tritone(col, mode, d_range, pal):
    r, g, b = col
    r_colors = [0, 0, 0, 0]
    r_ratio = 0.5
    least_penalty = 1e99

    len_pal = len(pal)
    for index1 in range(len_pal):
        for index2 in range(index1, len_pal, 1):
            # Determine the two component colors
            color1 = pal[index1]
            color2 = pal[index2]
            r1, g1, b1 = color1
            r2, g2, b2 = color2
            ratio = d_range / 2
            if color1 != color2:
                # Determine the ratio of mixing for each channel.
                # solve(r1 + ratio*(r2-r1)/64 = r, ratio)
                # Take a weighed average of these three ratios according to the
                # perceived luminosity of each channel (according to CCIR 601).

                if r2 != r1:
                    rr = (299 * d_range * int(r - r1) / int(r2 - r1))
                    rd = 299
                else:
                    rr = 0
                    rd = 0

                if g2 != g1:
                    gg = (587 * d_range * int(g - g1) / int(g2 - g1))
                    gd = 587
                else:
                    gg = 0
                    gd = 0

                if b2 != b1:
                    bb = (114 * d_range * int(b - b1) / int(b2 - b1))
                    bd = 114
                else:
                    bb = 0
                    bd = 0

                ratio = (rr + gg + bb) / (rd + gd + bd)
                if ratio < 0:
                    ratio = 0
                elif ratio > (d_range - 1):
                    ratio = d_range - 1

            # Determine what mixing them in this proportion will produce
            r0 = r1 + ratio * int(r2 - r1) / d_range
            g0 = g1 + ratio * int(g2 - g1) / d_range
            b0 = b1 + ratio * int(b2 - b1) / d_range

            penalty = evaluate_mixing_error(
                r, g, b, r0, g0, b0, r1, g1, b1, r2, g2, b2, ratio / d_range, 2)

            if penalty < least_penalty:
                least_penalty = penalty
                r_colors[0] = index1
                r_colors[1] = index2
                r_ratio = ratio / d_range

            if index1 != index2:
                for index3 in range(len_pal):
                    if index3 == index2 or index3 == index1:
                        continue

                    # 50% index3, 25% index2, 25% index1
                    color3 = pal[index3]
                    r3, g3, b3 = color3
                    r0 = (r1 + r2 + r3 * 2.0) / 4.0
                    g0 = (g1 + g2 + g3 * 2.0) / 4.0
                    b0 = (b1 + b2 + b3 * 2.0) / 4.0

                    cc0 = color_compare_ccir601(r, g, b, r0, g0, b0)
                    cc1 = color_compare_ccir601(r1, g1, b1, r2, g2, b2)

                    cc2 = color_compare_ccir601(
                        (r1 + r2) / 2, (g1 + g2) / 2, (b1 + b2) / 2, r3, g3, b3)

                    # original
                    # cc2 = color_compare_ccir601(
                    #     (r1 + g1) / 2, (g1 + g2) / 2, (b1 + b2) / 2, r3, g3, b3)

                    penalty = cc0 + cc1 * 0.025 + cc2 * 0.025
                    if penalty < least_penalty:
                        least_penalty = penalty
                        r_colors[0] = index3  # (0,0) index3 occurs twice
                        r_colors[1] = index1  # (0,1)
                        r_colors[2] = index2  # (1,0)
                        r_colors[3] = index3  # (1,1)
                        r_ratio = 4.0

    return (r_colors, r_ratio)


def devise_best_mixing_plan2(src, n_colors, luma, pal):
    r_colors = [0] * n_colors
    proportion_total = 0
    so_far = [0] * 3

    while proportion_total < n_colors:
        chosen_amount = 1
        chosen = 0
        max_test_count = max([1, proportion_total])

        least_penalty = -1
        for index in range(n_colors):
            sum = copy.copy(so_far)
            add = copy.copy(list(pal[index]))

            p = 1
            while p <= max_test_count:
                for c in range(3):
                    sum[c] += add[c]
                for c in range(3):
                    add[c] += add[c]
                t = proportion_total + p
                test = [sum[0] / t, sum[1] / t, sum[2] / t]
                penalty = color_compare_ccir601(src[0], src[1], src[2],
                                                test[0], test[1], test[2])
                if penalty < least_penalty or least_penalty < 0:
                    least_penalty = penalty
                    chosen = index
                    chosen_amount = p
                p *= 2

        for i in range(chosen_amount):
            if proportion_total >= n_colors:
                break
            r_colors[proportion_total] = chosen
            proportion_total += 1

        for c in range(3):
            so_far[c] += (pal[chosen][c] * chosen_amount)

    # Sort the colors according to luminance
    # std::sort(result.colors, result.colors + MixingPlan::n_colors, PaletteCompareLuma);

    cols = sorted(r_colors, key=lambda x: luma[x])
    return cols


def devise_best_mixing_plan2g(src, n_colors, limit, luma, pal_g, meta, ciede2000, pal):
    r, g, b = src

    # Input color in RGB
    input_rgb = [r, g, b]

    # Input color in CIE L*a*b*
    inputlab = LabItem(r, g, b, 255.0)

    # Tally so far (gamma-corrected)
    so_far = [0] * 3

    r_colors = []

    while len(r_colors) < limit:
        chosen_amount = 1
        chosen = 0

        if len(r_colors) == 0:
            max_test_count = 1
        else:
            max_test_count = len(r_colors)

        least_penalty = -1
        for index in range(n_colors):
            # col = pal[index]
            sum = [so_far[0], so_far[1], so_far[2]]
            add = [pal_g[index][0], pal_g[index][1], pal_g[index][2]]

            p = 1
            while p <= max_test_count:
                for c in range(3):
                    sum[c] += add[c]
                for c in range(3):
                    add[c] += add[c]
                t = len(r_colors) + p

                test = [
                    gamma_uncorrect(sum[0] / t),
                    gamma_uncorrect(sum[1] / t),
                    gamma_uncorrect(sum[2] / t)
                ]

                if ciede2000:
                    test_lab = LabItem(test[0], test[1], test[2], 1.0)
                    penalty = color_compare_ciede2000(test_lab, inputlab)
                else:
                    penalty = color_compare_ccir601(
                        input_rgb[0], input_rgb[1], input_rgb[2],
                        test[0] * 255.0, test[1] * 255.0, test[2] * 255.0
                    )

                if penalty < least_penalty or least_penalty < 0:
                    least_penalty = penalty
                    chosen = index
                    chosen_amount = p

                p *= 2

        # Append "chosen_amount" times "chosen" to the color list
        # result.resize(result.size() + chosen_amount, chosen);
        cnt = len(r_colors) + chosen_amount
        while len(r_colors) < cnt:
            r_colors.append(chosen)

        for c in range(3):
            so_far[c] += (pal_g[chosen][c] * chosen_amount)

    # Sort the colors according to luminance
    # std::sort(result.begin(), result.end(), PaletteCompareLuma);
    cols = sorted(r_colors, key=lambda x: luma[x])
    return cols


def devise_best_mixing_plan3(src, n_colors, limit, luma, pal_g, meta, ciede2000, pal):
    r, g, b = src

    # Input color in RGB
    input_rgb = [r, g, b]

    # Input color in CIE L*a*b*
    inputlab = LabItem(r, g, b, 255.0)

    solution = {}

    # The penalty of our currently "best" solution.
    current_penalty = -1

    # First, find the closest color to the input color. It is our seed.
    if True:
        chosen = 0
        for index in range(n_colors):
            cr, cg, cb = pal[index]
            if ciede2000:
                test_lab = LabItem(cr, cg, cb, 255.0)
                penalty = color_compare_ciede2000(inputlab, test_lab)
            else:
                penalty = color_compare_ccir601(
                    input_rgb[0], input_rgb[1], input_rgb[2],
                    cr, cg, cb
                )
            if penalty < current_penalty or current_penalty < 0:
                current_penalty = penalty
                chosen = index
        solution[chosen] = limit

    dbllimit = 1.0 / limit
    while current_penalty != 0.0:
        # Find out if there is a region in Solution that
        # can be split in two for benefit.
        best_penalty = current_penalty
        best_splitfrom = 0xffffffff
        best_split_to = [0, 0]

        for split_color, split_count in solution.items():

            # if split_count <= 1:
            #     continue

            # Tally the other colors
            sum = [0, 0, 0]
            for col, cnt in solution.items():
                if col == split_color:
                    continue

                sum[0] += pal_g[col][0] * cnt * dbllimit
                sum[1] += pal_g[col][1] * cnt * dbllimit
                sum[2] += pal_g[col][2] * cnt * dbllimit

            portion1 = (split_count / 2.0) * dbllimit
            portion2 = (split_count - split_count / 2.0) * dbllimit

            for a in range(n_colors):
                # if(a != split_color && Solution.find(a) != Solution.end()) continue;

                firstb = 0
                if portion1 == portion2:
                    firstb = a + 1

                for b in range(firstb, n_colors, 1):
                    if a == b:
                        continue

                    # if(b != split_color && Solution.find(b) != Solution.end()) continue;

                    lumadiff = luma[a] - luma[b]
                    if lumadiff < 0:
                        lumadiff = -lumadiff
                    if lumadiff > 80000:
                        continue

                    test = [
                        gamma_uncorrect(sum[0] + pal_g[a][0] * portion1 + pal_g[b][0] * portion2),
                        gamma_uncorrect(sum[1] + pal_g[a][1] * portion1 + pal_g[b][1] * portion2),
                        gamma_uncorrect(sum[2] + pal_g[a][2] * portion1 + pal_g[b][2] * portion2)
                    ]

                    # Figure out if this split is better than what we had

                    if ciede2000:
                        test_lab = LabItem(test[0], test[1], test[2], 1)
                        penalty = color_compare_ciede2000(inputlab, test_lab)
                    else:
                        penalty = color_compare_ccir601(
                            input_rgb[0], input_rgb[1], input_rgb[2],
                            test[0] * 255, test[1] * 255, test[2] * 255
                        )

                    if penalty < best_penalty:
                        best_penalty = penalty
                        best_splitfrom = split_color
                        best_split_to[0] = a
                        best_split_to[1] = b

                    if portion2 == 0:
                        break

        if best_penalty == current_penalty:
            break  # No better solution was found.

        split_count = solution[best_splitfrom]
        split1 = split_count / 2.0
        split2 = split_count - split1

        del solution[best_splitfrom]

        if split1 > 0:
            if best_split_to[0] in solution.keys():
                solution[best_split_to[0]] += split1
            else:
                solution[best_split_to[0]] = split1
        if split2 > 0:
            if best_split_to[1] in solution.keys():
                solution[best_split_to[1]] += split2
            else:
                solution[best_split_to[1]] = split2

        current_penalty = best_penalty

    # Sequence the solution.
    r_colors = []
    for col, cnt in solution.items():
        size = len(r_colors) + cnt
        while len(r_colors) < size:
            r_colors.append(col)

    # Sort the colors according to luminance
    # std::sort(result.begin(), result.end(), PaletteCompareLuma);
    cols = sorted(r_colors, key=lambda x: luma[x])
    return cols


def devise_best_mixing_plan4(srccol, n_colors, limit, luma, d_range, pal):
    r_colors = [0] * d_range
    src = list(srccol)
    lx = 0.09   # Error multiplier
    e = [0, 0, 0]   # Error accumulator

    for c in range(d_range):
        # Current temporary value
        t = [
            int(src[0] + e[0] * lx),
            int(src[1] + e[1] * lx),
            int(src[2] + e[2] * lx)
        ]

        # Clamp it in the allowed RGB range
        if t[0] < 0:
            t[0] = 0
        elif t[0] > 255:
            t[0] = 255
        if t[1] < 0:
            t[1] = 0
        elif t[1] > 255:
            t[1] = 255
        if t[2] < 0:
            t[2] = 0
        elif t[2] > 255:
            t[2] = 255

        # Find the closest color from the palette
        least_penalty = 1e99
        chosen = c % n_colors

        for index in range(n_colors):
            pc = list(pal[index])
            penalty = color_compare_ccir601(pc[0], pc[1], pc[2], t[0], t[1], t[2])
            if penalty < least_penalty:
                least_penalty = penalty
                chosen = index

        # Add it to candidates and update the error
        r_colors[c] = chosen
        pc = list(pal[chosen])
        e[0] += src[0] - pc[0]
        e[1] += src[1] - pc[1]
        e[2] += src[2] - pc[2]

    # Sort the colors according to luminance
    # std::sort(result.colors, result.colors + 64, PaletteCompareLuma);
    cols = sorted(r_colors, key=lambda x: luma[x])
    return cols


def convert_dither(srcim, mode, dither, ciede2000, pal):
    w, h = srcim.size
    im = Image.new("RGB", (w, h))
    src = srcim.load()
    dst = im.load()

    dmap = dithermaps[dither]
    dh = len(dmap)
    dw = len(dmap[0])
    d_range = dw * dh  # dither level range

    if 0 <= mode <= 4:
        # algorithm 1
        mix_plan = {
            0: devise_best_mixing_plan,
            1: devise_best_mixing_plan,
            2: devise_best_mixing_plan,
            3: devise_best_mixing_plan_fast,
            4: devise_best_mixing_plan_tritone,
        }

        for y in tqdm(range(h), ascii=True):
            for x in range(w):
                cols, ratio = mix_plan[mode](src[x, y], mode, d_range, pal)
                if mode == 4 and ratio == 4.0:
                    # Tri-tone or quad-tone dithering
                    dst[x, y] = pal[cols[(y % 2) * 2 + (x % 2)]]
                else:
                    if (dmap[y % dh][x % dw] / d_range) < ratio:
                        dst[x, y] = pal[cols[1]]
                    else:
                        dst[x, y] = pal[cols[0]]
        return im

    # get palette length
    n_colors = len(pal)

    # Luminance for each palette entry,
    # to be initialized as soon as the program begins
    luma = [(r * 299 + g * 587 + b * 114) for r, g, b in pal]

    if mode == 5:
        # algorithm 2
        for y in tqdm(range(h), ascii=True):
            for x in range(w):
                cols = devise_best_mixing_plan2(src[x, y], n_colors, luma, pal)
                map_value = int(dmap[y % dh][x % dw] * n_colors // d_range)
                dst[x, y] = pal[cols[map_value]]

        return im

    if mode == 6 or mode == 7:
        # algorithm 2 gamma correct / algorithm 3
        pal_g = []
        meta = []
        for r, g, b in pal:
            gr = gamma_correct(r / 255.0)
            gg = gamma_correct(g / 255.0)
            gb = gamma_correct(b / 255.0)
            pal_g.append([gr, gg, gb])
            meta.append(LabItem(r, g, b, 255.0))

        mix_plan = {
            6: devise_best_mixing_plan2g,
            7: devise_best_mixing_plan3
        }

        for y in tqdm(range(h), ascii=True):
            for x in range(w):
                cols = mix_plan[mode](src[x, y],
                                      n_colors, n_colors,
                                      luma, pal_g, meta,
                                      ciede2000, pal)
                map_value = int(dmap[y % dh][x % dw] * len(cols) // d_range)
                dst[x, y] = pal[cols[map_value]]

        return im

    if mode == 8:
        # adobe like pattern dither
        for y in tqdm(range(h), ascii=True):
            for x in range(w):
                cols = devise_best_mixing_plan4(src[x, y],
                                                n_colors, n_colors,
                                                luma, d_range, pal)
                map_value = dmap[y % dh][x % dw]
                dst[x, y] = pal[cols[map_value]]

    return im


def main():
    parser = argparse.ArgumentParser(description="Yliluoma ordered dithering 1, 2, 3, 4")
    parser.add_argument("-i", "--input", required=True, help="Input png filename")
    parser.add_argument("-o", "--output", required=True, help="Output png filename")
    parser.add_argument("-p", "--palette", help="Palette file (.png or .gpl)")
    parser.add_argument("-d", "--dither", type=int, default=8,
                        help="Dither type 2,4,8 (2x2,4x4,8x8). default: 8")
    parser.add_argument("-m", "--mode", type=int, default=3,
                        help="job kind 0 - 8. default: 3")
    parser.add_argument("-c", "--ciede2000", action="store_true",
                        help="Enable CIEDE2000 (mode 6 only")
    args = parser.parse_args()

    if args.mode < 0 or args.mode > 8:
        print("Error: Unknown mode = %d" % args.mode)
        sys.exit()

    if args.dither not in [2, 4, 8]:
        print("Error: Unknown dither = %d" % args.dither)
        sys.exit()

    if args.palette is not None:
        # load palette file
        # print("Palette file : %s" % args.palette)
        p = Palette(args.palette)
        palette = p.palette
    else:
        # print("Palette file is None")
        palette = pal

    srcim = Image.open(args.input)
    im = convert_dither(srcim, args.mode, args.dither, args.ciede2000, palette)
    im.save(args.output)


if __name__ == '__main__':
    main()
