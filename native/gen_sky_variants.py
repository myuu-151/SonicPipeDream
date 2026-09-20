#!/usr/bin/env python
"""Seven more skies, each in its own folder, to try against the classic one.

    python native/gen_sky_variants.py            all seven
    python native/gen_sky_variants.py Pastel     just that one

Needs Pillow. A sky here is a full set of textures -- 8 star frames with that sky's
gradient under them, and the 384 medley frames in that sky's diamond colours --
because the colours live in the frames. About 230MB of project files each.

They reuse the classic sky's dome and material; only textures differ, and Sky.lua
swaps between them by its `sky` property (0 is the classic sky, which this script
does not touch). Same starfield, same diamond show, different colours.

A preview of each is written to sky_previews/, outside the project's assets.
"""

import os
import sys

from PIL import Image

import gen_s2sky_assets as sky
import preview_diamond_concepts as pat
import s2sky_medley as medley

HERE = os.path.dirname(os.path.abspath(__file__))
ASSETS = os.path.join(HERE, "..", "proj", "Assets", "Skies")
PREVIEWS = os.path.join(HERE, "..", "sky_previews")

UUID_BASE = 0x51C0FFEE00100000          # + 0x1000 per sky; stars at +0xE00

# name, sky at the horizon, sky at the poles, shadow under a diamond, and the colours
# the diamonds travel through from dim to lit.
#
# Five stops, not two. With two, a whole pattern is "colour A, colour B and a few
# blends between", and however good A and B are there is not much to look at. Each
# ramp is a journey: it moves through hue as well as brightness, and ends near white
# so the brightest diamonds really flare.
#
# The order is the `sky` number in Sky.lua, from 1. Keep it in step with SKY_NAMES there.
SKIES = [
    ("Midnight", (4, 6, 22), (16, 22, 56), (1, 2, 9),
     [(44, 22, 124), (124, 60, 222), (58, 150, 255), (90, 240, 255), (232, 255, 255)]),
    ("Dawn", (255, 192, 150), (150, 200, 245), (190, 124, 118),
     [(196, 66, 112), (246, 118, 92), (255, 178, 88), (255, 230, 128), (255, 251, 214)]),
    ("Pastel", (204, 184, 242), (182, 236, 222), (132, 112, 190),
     [(150, 118, 214), (242, 150, 202), (255, 202, 172), (168, 226, 250), (238, 255, 250)]),
    ("Sunset", (152, 30, 84), (40, 20, 92), (62, 8, 46),
     [(122, 20, 112), (232, 50, 92), (255, 120, 30), (255, 202, 60), (255, 246, 172)]),
    ("Aurora", (0, 42, 46), (5, 20, 42), (0, 15, 19),
     [(20, 92, 124), (30, 202, 142), (162, 242, 90), (255, 122, 222), (204, 164, 255)]),
    ("Inferno", (34, 4, 4), (76, 15, 8), (10, 0, 0),
     [(92, 10, 10), (204, 30, 10), (255, 112, 0), (255, 204, 40), (255, 251, 204)]),
    # Cold in the shadows, warm in the light: still monochrome at a glance, but the
    # ramp crosses from blue-grey to cream rather than just getting brighter.
    ("Noir", (20, 20, 25), (62, 62, 74), (4, 4, 7),
     [(62, 66, 88), (124, 128, 152), (188, 186, 192), (242, 226, 196), (255, 251, 236)]),
]

# Where along a band (0 its middle row, 1 its edge) each colour of a ramp sits, lit end first.
# Spaced as the classic sky's wide stripe is.
ROW_AT = (0.00, 0.32, 0.62, 0.86, 1.00)

LEVELS = 16                 # colour steps, where the classic sky has 8
DRIFT = 0.28                # how far position pulls a diamond's colour; see the painter


def apply(spec):
    """Point both generators at this sky's colours. They read these at draw time."""
    _, horizon, poles, shadow, stops = spec
    sky.SKY_DEEP, sky.SKY_LIFT = horizon, poles
    pat.RAMP_STOPS, pat.SHADOW = stops, shadow
    pat.LEVELS, pat.DRIFT = LEVELS, DRIFT
    # The row gradient, as the classic sky has it, out of this sky's OWN ramp: its brightest
    # colour is the stripe through the middle of each band, and the rows step back down the
    # ramp to its second colour at the band's edge. A dim diamond fades to the first.
    pat.ROW_DIM = stops[0]
    pat.ROW_STOPS = list(zip(ROW_AT, (stops[4], stops[3], stops[2], stops[1], pat.lerp(stops[1], stops[0], 0.35))))


def preview(name, star_px, frames):
    """The sky as the material shows it: stars and gradient, diamonds over them.
    Two moments of the show, side by side."""
    w, h = sky.STAR_TEX_W, sky.STAR_TEX_H
    base = Image.frombytes("RGBA", (w, h), bytes(star_px)).transpose(Image.FLIP_TOP_BOTTOM)
    # One star tile is 180 degrees round and the whole 180 up; the diamond tile is 90
    # round by 45 up, so it repeats twice across this and four times up it.
    out = Image.new("RGB", (w, h // 2 * 1))
    view = base.convert("RGB").resize((w // 2, h // 2), Image.LANCZOS)
    for k, f in enumerate(frames):
        panel = view.copy()
        tile = pat.paint_rgba(pat.medley_frame(f)).resize((w // 4, h // 8), Image.LANCZOS)
        for ty in range(4):
            for tx in range(2):
                panel.paste(tile, (tx * w // 4, ty * h // 8), tile)
        out.paste(panel, (k * w // 2, 0))
    os.makedirs(PREVIEWS, exist_ok=True)
    path = os.path.join(PREVIEWS, "%s.png" % name)
    try:
        out.save(path)
    except OSError:
        # Open in an image viewer, most likely. The preview is a convenience and
        # must not stop the assets being made.
        path = os.path.join(PREVIEWS, "%s_new.png" % name)
        out.save(path)
    return path


def main():
    want = [a.lower() for a in sys.argv[1:]]
    field = sky.star_field()            # seeded: every sky gets the same stars

    for n, spec in enumerate(SKIES):
        name = spec[0]
        if want and name.lower() not in want:
            continue
        apply(spec)
        folder = os.path.join(ASSETS, name)
        os.makedirs(folder, exist_ok=True)
        base = UUID_BASE + n * 0x1000

        keep = None
        for f in range(sky.STAR_FRAMES):
            w, h, px = sky.gen_stars_frame(field, f)
            asset = "T_Sky%s_Stars_%d" % (name, f + 1)
            sky.write_texture(os.path.join(folder, asset + ".oct"), asset, base + 0xE00 + f,
                              w, h, px, wrap=1, quiet=True)
            if f == 2:
                keep = px

        for f in range(medley.FRAMES):
            asset = "T_Sky%s_Medley_%03d" % (name, f + 1)
            sky.write_texture(os.path.join(folder, asset + ".oct"), asset, base + f,
                              medley.TEX_W, medley.TEX_H, medley.frame_pixels(f),
                              wrap=1, quiet=True)

        # A full-coverage moment and a sparse one: ripple, and the bloom.
        shown = preview(name, keep, (6, 5 * 48 + 12))
        print("%-9s sky %d: %d star frames, %d medley frames -> %s"
              % (name, n + 1, sky.STAR_FRAMES, medley.FRAMES, os.path.relpath(shown, HERE)))


if __name__ == "__main__":
    main()
