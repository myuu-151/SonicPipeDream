"""Draw MARATHON in the menu's own lettering, by cutting it out of the other menu items.

    python native/gen_menu_marathon.py
        -> external/ui/menu/parts/item_marathon.png
           external/ui/menu/parts/_marathon_check.png   (to look at)

The menu mockup (external/ui/menu/imaged.png) was drawn, not typeset, and its lettering is
not NiseSegaSonic or anything else we have -- it has lowercase, which NiseSegaSonic does not.
So MARATHON is built from the letters already in the picture. Every one is there:

    M  Main Game      a  Main Game      r  Records       t  Options
    o  Options        n  Options        h  NOWHERE

There is no h in "Main Game", "Time Attack", "Records" or "Options". It is grafted: the
ascender of k (Time Attack) above the shoulder and legs of n (Options). They agree -- both
stems are 7 px of white at the same left edge, both baselines sit at the same row -- so the
seam falls inside a straight stem and does not show.

Letters are cut at the MIDDLE of the gap between their white faces, never at the edge of the
ink: the blue outlines of neighbours touch, so a cut through the outline would shave one.
Each letter therefore carries half of each gap, and butting the pieces back together
reproduces the spacing of the original word.
"""

import os

import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
PARTS = os.path.abspath(os.path.join(HERE, "..", "external", "ui", "menu", "parts"))
OUT = os.path.join(PARTS, "item_marathon.png")
CHECK = os.path.join(PARTS, "_marathon_check.png")

WORDS = {                           # the item art, and what it says
    "item_main_game": "Main Game",
    "item_time_attack": "Time Attack",
    "item_records": "Records",
    "item_options": "Options",
}

# Where each letter of "Marathon" comes from: (item, index of the letter in that word).
# Indices count letters only, spaces skipped.
SOURCE = {
    "M": ("item_main_game", 0),
    "a": ("item_main_game", 1),
    "r": ("item_records", 4),
    "t": ("item_options", 2),
    "o": ("item_options", 4),
    "n": ("item_options", 5),
    "k": ("item_time_attack", 9),   # only for the h's ascender
}


def face(a):
    """The white face of the lettering: opaque and bright. (The outline is a dark blue.)"""
    return (a[..., 3] > 120) & (a[..., :3].min(axis=2) > 150)


def cut(name):
    """Every letter of one item, as its own RGBA tile, cut at the middles of the gaps."""
    im = Image.open(os.path.join(PARTS, name + ".png")).convert("RGBA")
    a = np.array(im).astype(int)
    cols = face(a).any(axis=0)

    runs, x = [], 0
    while x < len(cols):
        if cols[x]:
            s = x
            while x < len(cols) and cols[x]:
                x += 1
            runs.append((s, x - 1))
        else:
            x += 1

    edges = [0]
    for i in range(len(runs) - 1):
        edges.append((runs[i][1] + runs[i + 1][0] + 1) // 2)
    edges.append(im.width)
    return [im.crop((edges[i], 0, edges[i + 1], im.height)) for i in range(len(runs))], runs


TILES, RUNS = {}, {}
for name in WORDS:
    TILES[name], RUNS[name] = cut(name)


def letter(ch):
    name, i = SOURCE[ch]
    return TILES[name][i]


def baseline(tile):
    """The last row with any white in it: every letter of a line sits on this."""
    rows = np.where(face(np.array(tile).astype(int)).any(axis=1))[0]
    return rows[-1]


def graft_h():
    """k's ascender over n's shoulder: the h the mockup never drew.

    Both letters were drawn on the same line, so their baselines are the same row and no
    shifting up or down is needed -- the rows above n's x-height are simply empty, and the
    ascender goes in them. The seam is a row or two BELOW the x-height, so the two stems
    overlap rather than meet, and n is composited last so its shoulder draws over the join.
    """
    n, k = letter("n"), letter("k")
    fn, fk = face(np.array(n).astype(int)), face(np.array(k).astype(int))

    n_rows, k_rows = np.where(fn.any(axis=1))[0], np.where(fk.any(axis=1))[0]
    assert n_rows[-1] == k_rows[-1], "n and k do not share a baseline: %d vs %d" % (n_rows[-1], k_rows[-1])
    n_top, k_top = n_rows[0], k_rows[0]

    # k's stem, and only the stem: the columns its white fills at the very top. Lower down,
    # the arm joins on the right; the seam is taken above where that begins.
    stem = np.where(fk[k_top + 1])[0]
    arm = next((y for y in range(k_top + 1, k_rows[-1]) if len(np.where(fk[y])[0]) > len(stem) + 1),
               k_rows[-1])
    seam = min(arm, n_top + 2)          # below the x-height, above the arm
    stem_right = stem[-1] + 3           # the stem's white, plus its 2 px of outline

    n_left = np.where(fn[n_rows[-1]])[0][0]     # the left leg, at the baseline
    k_left = stem[0]
    dx = n_left - k_left

    out = Image.new("RGBA", (n.width, n.height), (0, 0, 0, 0))
    out.alpha_composite(k.crop((0, 0, stem_right, seam)), (dx, 0))
    out.alpha_composite(n, (0, 0))

    # n carries its own outline ABOVE the shoulder, and that outline now lies across the
    # stem as a blue band. Lay the stem's white back over it -- the face is a flat white, so
    # a piece of k's stem is indistinguishable from a drawn rectangle.
    # Only the join, not the whole stem: repainting the ascender's top would flatten the
    # anti-aliasing the artist's own letter has there.
    join_top = max(k_top + 1, n_top - 4)
    mask = np.zeros(fk.shape, bool)
    mask[join_top:seam, stem[0]:stem[-1] + 1] = fk[join_top:seam, stem[0]:stem[-1] + 1]
    white = np.array(k).astype(int)[..., :3][fk].max(axis=0)    # this art's face colour
    px = np.zeros(fk.shape + (4,), np.uint8)
    px[mask] = list(white) + [255]
    out.alpha_composite(Image.fromarray(px, "RGBA").crop((0, 0, stem_right, seam)), (dx, 0))
    return out


def compose(word, gap_fix=0):
    tiles = [graft_h() if ch == "h" else letter(ch) for ch in word]
    base = max(baseline(t) for t in tiles)
    height = max(t.height + (base - baseline(t)) for t in tiles)
    width = sum(t.width for t in tiles) + gap_fix * (len(tiles) - 1)
    out = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    x = 0
    for t in tiles:
        out.alpha_composite(t, (x, base - baseline(t)))
        x += t.width + gap_fix
    return out.crop(out.getbbox())


if __name__ == "__main__":
    art = compose("Marathon")
    art.save(OUT)
    print("wrote %s  (%d x %d)" % (OUT, art.width, art.height))

    # A sheet to judge it by: the new word over the ones it was cut from.
    rows = [art] + [Image.open(os.path.join(PARTS, n + ".png")).convert("RGBA") for n in WORDS]
    W = max(im.width for im in rows) + 20
    H = sum(im.height + 14 for im in rows) + 10
    sheet = Image.new("RGBA", (W, H), (246, 211, 43, 255))
    y = 6
    for im in rows:
        sheet.alpha_composite(im, (10, y))
        y += im.height + 14
    sheet.save(CHECK)
    print("wrote %s" % CHECK)
