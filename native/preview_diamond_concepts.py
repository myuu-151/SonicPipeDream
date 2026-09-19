#!/usr/bin/env python
"""Concept previews for an animated diamond pattern across the sky.

Not part of the asset build: this only writes GIFs to look at. Every concept
obeys the limits the real texture has to live with, so nothing here is a look
the GameCube cannot actually show:

  * it tiles in both directions (everything is periodic in x and in y), so
    it can be stacked up the whole sphere as well as run round it,
  * it loops (everything is periodic in t),
  * alpha is 1 bit -- a texel is a diamond or it is sky,
  * colour comes from a short quantised ramp, as CMPR blocks would give.

Because alpha is 1 bit there is no transparency crossfade. Patterns hand over
to each other by SIZE instead: the outgoing pattern's diamonds shrink to
nothing while the incoming pattern's grow through them.

Run with a Python that has Pillow.
"""

import math
import os

from PIL import Image, ImageDraw

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "preview_diamonds")

TILE_W, TILE_H = 512, 256       # one repeat of the texture
REPEATS = 2                     # shown side by side, so the seam is visible
CYCLE = 24                      # frames in one turn of any single pattern
FRAME_MS = 70

CELL = 32                       # small lattice pitch; must divide TILE_W
R_FILL = 0.42                   # a full-size diamond's half-width, in cells

SKY_DEEP = (0, 62, 101)
SKY_LIFT = (27, 94, 133)
SHADOW = (0, 38, 66)
RAMP_LO = (0x1B, 0x5E, 0x85)    # the blue the current diamonds start from
RAMP_HI = (0x36, 0xCB, 0x00)    # and the green they end on
LEVELS = 8                      # colour steps, as a quantised texture would have

TAU = 2.0 * math.pi


def lerp(a, b, t):
    return tuple(int(round(a[i] + (b[i] - a[i]) * t)) for i in range(3))


def ramp(level):
    level = max(0.0, min(1.0, level))
    q = round(level * (LEVELS - 1)) / float(LEVELS - 1)
    return lerp(RAMP_LO, RAMP_HI, q)


def smooth(k):
    k = max(0.0, min(1.0, k))
    return k * k * (3.0 - 2.0 * k)


def background():
    """Deep at the equator, paler toward the poles, like the real sky."""
    im = Image.new("RGB", (TILE_W * REPEATS, TILE_H))
    px = im.load()
    for y in range(TILE_H):
        t = abs(y - TILE_H / 2.0) / (TILE_H / 2.0)
        c = lerp(SKY_DEEP, SKY_LIFT, min(1.0, t * 1.4))
        for x in range(TILE_W * REPEATS):
            px[x, y] = c
    return im


def wrap_dx(dx):
    """Shortest horizontal distance on a texture that repeats."""
    dx = dx % TILE_W
    return dx - TILE_W if dx > TILE_W / 2.0 else dx


def wrap_dy(dy):
    """And the same vertically, now that the tile stacks up the sky too."""
    dy = dy % TILE_H
    return dy - TILE_H if dy > TILE_H / 2.0 else dy


def lattice(cell=CELL):
    """Staggered lattice: odd rows sit half a cell across, which is what lets
    small diamonds nest into bigger diamond shapes."""
    row = cell // 2
    for j in range(TILE_H // row):
        off = cell // 2 if (j % 2) else 0
        for i in range(TILE_W // cell):
            yield i, j, i * cell + off + cell // 2, j * row


def hash01(i, j=0):
    v = math.sin(i * 127.1 + j * 311.7) * 43758.5453
    return v - math.floor(v)


# --- patterns -----------------------------------------------------------------
# Each takes t in 0..1 (one turn, looping) and returns a list of diamonds:
#   (cx, cy, half_width, half_height, level)

def ripple(t):
    """Rings of light spreading out from the middle of each repeat."""
    out = []
    r = CELL * R_FILL
    for i, j, cx, cy in lattice():
        d = math.hypot(wrap_dx(cx - TILE_W / 2.0), wrap_dy(cy - TILE_H / 2.0) * 1.6)
        w = 0.5 + 0.5 * math.cos(TAU * (d / 90.0 - t))
        s = r * (0.4 + 0.6 * w)
        out.append((cx, cy, s, s, w))
    return out


def dance(t):
    """Big and small diamonds trading places: as the big lattice swells the
    small one ducks away inside it, then they swap."""
    out = []
    beat = 0.5 + 0.5 * math.sin(TAU * t)
    big = CELL * 4
    rb = big * R_FILL
    for i, j, cx, cy in lattice(big):
        local = 0.5 + 0.5 * math.sin(TAU * (t + cx / TILE_W))
        s = rb * (0.15 + 0.85 * local)
        out.append((cx, cy, s, s, 0.15 + 0.35 * local))
    rs = CELL * R_FILL
    for i, j, cx, cy in lattice():
        local = 0.5 + 0.5 * math.sin(TAU * (t + cx / TILE_W) + math.pi)
        s = rs * (0.1 + 0.9 * local)
        out.append((cx, cy, s, s, 0.55 + 0.45 * local))
    return out


def rings(t):
    """Nested diamond outlines pouring outward from each centre, big ones
    passing through small ones. Outlines are made of small diamonds, so the
    big shape is always 'a diamond built from diamonds'."""
    out = []
    r = CELL * R_FILL
    span = 5.0                                   # lattice steps between rings
    for i, j, cx, cy in lattice():
        m = (abs(wrap_dx(cx - TILE_W / 2.0)) + abs(wrap_dy(cy - TILE_H / 2.0)) * 2.0) / CELL
        u = (m / span - t) % 1.0                 # 0 on a ring, rising behind it
        w = max(0.0, 1.0 - u * 2.4)
        if w <= 0.0:
            continue
        s = r * (0.35 + 0.65 * w)
        out.append((cx, cy, s, s, w))
    return out


def bloom(t):
    """One big diamond that builds itself ring by ring, then folds away."""
    out = []
    r = CELL * R_FILL
    grow = 0.5 - 0.5 * math.cos(TAU * t)
    radius = 0.5 + 6.0 * grow
    for i, j, cx, cy in lattice():
        m = (abs(wrap_dx(cx - TILE_W / 2.0)) + abs(wrap_dy(cy - TILE_H / 2.0)) * 2.0) / CELL
        if m > radius:
            continue
        edge = 1.0 - (radius - m) / max(radius, 1e-6)
        out.append((cx, cy, r, r, 0.25 + 0.75 * edge))
    return out


def flip(t):
    """Every diamond turns over like a card, in a wave round the sky: green on
    one face, blue on the other."""
    out = []
    r = CELL * R_FILL
    for i, j, cx, cy in lattice():
        c = math.cos(TAU * (cx / TILE_W * 2.0 + cy / TILE_H * 1.0 - t))
        out.append((cx, cy, r * max(0.06, abs(c)), r, 1.0 if c > 0.0 else 0.0))
    return out


def comet(t):
    """Diagonal streaks racing round the horizon with fading tails."""
    out = []
    r = CELL * R_FILL
    for i, j, cx, cy in lattice():
        u = (cx / TILE_W * 2.0 + cy / TILE_H - t * 2.0) % 1.0
        w = max(0.0, 1.0 - u * 2.2)
        s = r * (0.3 + 0.7 * w)
        out.append((cx, cy, s, s, w))
    return out


def cascade(t):
    """Columns of diamonds falling at their own pace, like rain on glass."""
    out = []
    r = CELL * R_FILL
    for i, j, cx, cy in lattice():
        col = int(cx // (CELL // 2))
        speed = 1 + int(hash01(col) * 2.0)       # whole turns, so it loops
        head = (t * speed + hash01(col, 7)) % 1.0
        u = (head - cy / float(TILE_H)) % 1.0
        w = max(0.0, 1.0 - u * 3.0)
        if w <= 0.0:
            continue
        s = r * (0.5 + 0.5 * w)
        out.append((cx, cy, s, s, w))
    return out


def zoom(t):
    """The whole lattice breathes between three scales, each size swelling up
    through the one before it."""
    out = []
    for k, cell in enumerate((CELL, CELL * 2, CELL * 4)):
        w = max(0.0, math.cos(TAU * (t - k / 3.0))) ** 1.5
        if w <= 0.01:
            continue
        r = cell * R_FILL * w
        for i, j, cx, cy in lattice(cell):
            out.append((cx, cy, r, r, 0.2 + 0.8 * (k / 2.0)))
    return out


PATTERNS = [
    ("1_ripple", ripple),
    ("2_dance", dance),
    ("3_rings", rings),
    ("4_bloom", bloom),
    ("5_flip", flip),
    ("6_comet", comet),
    ("7_cascade", cascade),
    ("8_zoom", zoom),
]

# The show: which patterns play, in order. Each holds for HOLD frames and then
# hands over to the next across XFADE frames. Both are whole numbers of CYCLE so
# every pattern's own motion stays continuous through the join and the whole
# medley loops cleanly.
MEDLEY = [ripple, dance, rings, zoom, flip, bloom, comet, cascade]
HOLD = CYCLE
XFADE = CYCLE


def diamond(draw, cx, cy, hw, hh, colour):
    if hw < 0.6 or hh < 0.6:
        return
    draw.polygon([(cx, cy - hh), (cx + hw, cy), (cx, cy + hh), (cx - hw, cy)], fill=colour)


def paint(shapes, bg):
    im = bg.copy()
    draw = ImageDraw.Draw(im)
    # Biggest first so small diamonds sit on top of big ones, and every shadow
    # before any diamond so no shadow lands on a neighbour.
    shapes = sorted(shapes, key=lambda s: -s[2])
    for rep in range(-1, REPEATS + 1):
        ox = rep * TILE_W
        for oy in (-TILE_H, 0, TILE_H):
            for cx, cy, hw, hh, _ in shapes:
                diamond(draw, ox + cx + 3, oy + cy + 3, hw, hh, SHADOW)
    for rep in range(-1, REPEATS + 1):
        ox = rep * TILE_W
        for oy in (-TILE_H, 0, TILE_H):
            for cx, cy, hw, hh, level in shapes:
                diamond(draw, ox + cx, oy + cy, hw, hh, ramp(level))
    return im


def paint_rgba(shapes):
    """One tile on transparency, as the real texture wants it: no sky behind,
    and anything crossing the left or right edge drawn again on the far side so
    the tile repeats without a seam, in both directions. Image row 0 is the TOP."""
    im = Image.new("RGBA", (TILE_W, TILE_H), (0, 0, 0, 0))
    draw = ImageDraw.Draw(im)
    shapes = sorted(shapes, key=lambda s: -s[2])
    wraps = [(ox, oy) for ox in (-TILE_W, 0, TILE_W) for oy in (-TILE_H, 0, TILE_H)]
    for cx, cy, hw, hh, _ in shapes:
        for ox, oy in wraps:
            diamond(draw, ox + cx + 3, oy + cy + 3, hw, hh, SHADOW + (255,))
    for cx, cy, hw, hh, level in shapes:
        for ox, oy in wraps:
            diamond(draw, ox + cx, oy + cy, hw, hh, ramp(level) + (255,))
    return im


def medley_length():
    return (HOLD + XFADE) * len(MEDLEY)


def scaled(shapes, k):
    return [(cx, cy, hw * k, hh * k, lv) for cx, cy, hw, hh, lv in shapes]


def medley_frame(f):
    seg = HOLD + XFADE
    idx = (f // seg) % len(MEDLEY)
    local = f % seg
    t = (f % CYCLE) / float(CYCLE)
    a = MEDLEY[idx](t)
    if local < HOLD:
        return a
    k = (local - HOLD) / float(XFADE)
    b = MEDLEY[(idx + 1) % len(MEDLEY)](t)
    # The two fades overlap rather than mirror each other: the incoming pattern
    # is mostly grown before the outgoing one starts to let go. A mirrored fade
    # has both at half size in the middle, which all but empties the sky; this
    # way the middle is the busiest moment, with both patterns on screen
    # passing through each other.
    grow = smooth(k / 0.65)
    shrink = 1.0 - smooth((k - 0.35) / 0.65)
    return scaled(a, shrink) + scaled(b, grow)


def save_gif(frames, path):
    frames[0].save(path, save_all=True, append_images=frames[1:],
                   duration=FRAME_MS, loop=0)
    print("wrote", path)


def main():
    os.makedirs(OUT, exist_ok=True)
    bg = background()

    cols = 4
    sheet = Image.new("RGB", (TILE_W * cols, TILE_H * len(PATTERNS)))
    for row, (name, fn) in enumerate(PATTERNS):
        frames = [paint(fn(f / float(CYCLE)), bg) for f in range(CYCLE)]
        save_gif(frames, os.path.join(OUT, name + ".gif"))
        for k in range(cols):
            fr = frames[k * CYCLE // cols].crop((0, 0, TILE_W, TILE_H))
            sheet.paste(fr, (k * TILE_W, row * TILE_H))
    sheet.save(os.path.join(OUT, "overview.png"))
    print("wrote overview.png")

    total = (HOLD + XFADE) * len(MEDLEY)
    frames = [paint(medley_frame(f), bg) for f in range(total)]
    save_gif(frames, os.path.join(OUT, "0_MEDLEY.gif"))

    # Mid-handover stills, to check the crossfades read as intended.
    seg = HOLD + XFADE
    xs = Image.new("RGB", (TILE_W * 4, TILE_H * 2))
    for n in range(8):
        f = n * seg + HOLD + XFADE // 2
        xs.paste(frames[f].crop((0, 0, TILE_W, TILE_H)), ((n % 4) * TILE_W, (n // 4) * TILE_H))
    xs.save(os.path.join(OUT, "handovers.png"))
    print("wrote handovers.png  (%d medley frames)" % total)


if __name__ == "__main__":
    main()
