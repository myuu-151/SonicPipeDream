"""Draw each original stage's rings and bombs unrolled flat, with the modules named on it.

    python native/make_stage_maps.py          -> docs/stage-maps/stage1.png ... stage7.png

The second safeguard. check_ring_coverage.py proves every object is accounted for; it
cannot prove the modules are the shapes a PLAYER sees (it once explained a 48-ring spiral
as three helixes and called it done). So this draws the real stages to be looked at: find
anything on these pictures that has no name of its own, and that is a missing type.

Across is the track, one column a frame, wrapped into rows of 160 frames. Up and down is
the angle round the pipe: the floor's centre line through the middle of each band, the two
rims as lines, and the shaded part is up over the pipe where only a jump reaches.
    yellow ring = ring      white cross on dark = bomb      (no red or green anywhere)
Every module the cover placed is boxed and named at its first object.
"""

import os
import sys

from PIL import Image, ImageDraw

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import check_ring_coverage as cc
import ring_modules as rm
from gen_s2_track import LAYOUTS, SEGMENTS

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "docs", "stage-maps")

PER_ROW = 160               # frames across one band
FX = 11                     # pixels a frame
AY = 1.5                    # pixels per 256th of a circle
BAND = int(256 * AY)
GAP = 46
LEFT = 40

BG, SHADE, GRID = (14, 18, 34), (26, 32, 56), (60, 70, 105)
RING, BOMB_FILL, BOMB_X = (255, 214, 40), (8, 8, 12), (255, 255, 255)
LABEL, BOX = (150, 205, 255), (90, 130, 200)


def y_of(angle):
    """$40 (the floor) in the middle of the band, $C0 (overhead) at its top and bottom."""
    return int(((angle - 0x40 + 128) % 256) * AY)


def main():
    os.makedirs(OUT, exist_ok=True)
    for stage in range(1, 8):
        objects = cc.flatten(stage)
        placed, _ = cc.cover(objects)
        lengths = [len(SEGMENTS[int(b, 16) & 0x7F]) for b in LAYOUTS[stage].split()]
        total = sum(lengths)
        bands = (total + PER_ROW - 1) // PER_ROW
        img = Image.new("RGB", (LEFT + PER_ROW * FX + 20, bands * (BAND + GAP) + 30), BG)
        d = ImageDraw.Draw(img)
        d.text((8, 6), "Sonic 2 special stage %d: %d rings, %d bombs" % (
            stage, sum(o[2] == rm.RING for o in objects), sum(o[2] == rm.BOMB for o in objects)), fill=LABEL)

        def at(frame, angle):
            band, col = divmod(frame, PER_ROW)
            return LEFT + col * FX + FX // 2, 30 + band * (BAND + GAP) + y_of(angle)

        for b in range(bands):
            top = 30 + b * (BAND + GAP)
            x1 = LEFT + PER_ROW * FX
            d.rectangle((LEFT, top, x1, top + y_of(0x80)), fill=SHADE)               # overhead
            d.rectangle((LEFT, top + y_of(0x00), x1, top + BAND), fill=SHADE)
            for ang, name in ((0x80, "rim"), (0x40, "floor"), (0x00, "rim")):
                d.line((LEFT, top + y_of(ang), x1, top + y_of(ang)), fill=GRID)
                d.text((2, top + y_of(ang) - 5), name, fill=GRID)
        start = 0
        for i, n in enumerate(lengths):                                            # segments
            x, y = at(start, 0xC0)
            d.line((x - FX // 2, y, x - FX // 2, y + BAND), fill=GRID)
            d.text((x - FX // 2 + 2, y + BAND + 1), str(i), fill=GRID)
            start += n

        for f, a, k in sorted(objects):
            x, y = at(f, a)
            if k == rm.RING:
                d.ellipse((x - 4, y - 4, x + 4, y + 4), outline=RING, width=2)
            else:
                d.rectangle((x - 4, y - 4, x + 4, y + 4), fill=BOMB_FILL, outline=BOMB_X)
                d.line((x - 3, y - 3, x + 3, y + 3), fill=BOMB_X)
                d.line((x - 3, y + 3, x + 3, y - 3), fill=BOMB_X)
        for label, f, a, n in placed:
            if n < 2:
                continue
            x, y = at(f, a)
            d.text((x - 4, y - 17), label.split(",")[0].replace(" (mirrored)", ""), fill=LABEL)

        path = os.path.join(OUT, "stage%d.png" % stage)
        img.save(path)
        print("saved", os.path.abspath(path), img.size)


main()
