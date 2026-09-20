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

# name: sky at the horizon, sky at the poles, diamonds dim, diamonds lit, shadow
#
# The order is the `sky` number in Sky.lua, from 1. Keep it in step with SKY_NAMES there.
SKIES = [
    ("Midnight", (4, 6, 22),       (16, 22, 56),    (96, 62, 205),   (84, 232, 255),  (1, 2, 9)),
    ("Dawn",     (255, 192, 150),  (150, 200, 245), (236, 104, 96),  (255, 226, 120), (196, 132, 112)),
    ("Pastel",   (204, 184, 242),  (182, 236, 222), (255, 168, 212), (168, 216, 255), (150, 132, 204)),
    ("Sunset",   (152, 30, 84),    (40, 20, 92),    (255, 116, 22),  (255, 232, 84),  (70, 10, 50)),
    ("Aurora",   (0, 42, 46),      (5, 20, 42),     (40, 222, 142),  (255, 122, 222), (0, 17, 21)),
    ("Inferno",  (34, 4, 4),       (76, 15, 8),     (206, 32, 12),   (255, 222, 62),  (12, 0, 0)),
    ("Noir",     (20, 20, 25),     (62, 62, 74),    (118, 118, 136), (255, 242, 204), (4, 4, 7)),
]


def apply(spec):
    """Point both generators at this sky's colours. They read these at draw time."""
    _, horizon, poles, dim, lit, shadow = spec
    sky.SKY_DEEP, sky.SKY_LIFT = horizon, poles
    pat.RAMP_LO, pat.RAMP_HI, pat.SHADOW = dim, lit, shadow


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
