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
stems are 7 px of white at the same left edge, both baselines sit on the same row -- so the
seam falls inside a straight stem and does not show.

Neighbouring letters SHARE their blue outline, so a letter cannot be cut out with a straight
slice: the first version cut at the middle of each gap, which left every letter half of its
neighbour's outline and made the joins lumpy where letters from different words met. This
uses gen_ui_assets.split_letters, written for the same problem in START: each letter comes
away with a whole outline of its own. They are then set down with the spacing the mockup
uses between its own letters -- 3 px of daylight between faces -- and their outlines overlap
again, blue on identical blue, as they do in the words they came from.
"""

import os

import numpy as np
from PIL import Image

from gen_ui_assets import split_letters

HERE = os.path.dirname(os.path.abspath(__file__))
PARTS = os.path.abspath(os.path.join(HERE, "..", "external", "ui", "menu", "parts"))
OUT = os.path.join(PARTS, "item_marathon.png")
CHECK = os.path.join(PARTS, "_marathon_check.png")

GAP = 3                             # px of daylight between faces, where the art does not say

# Whether to level the letters' heights. The mockup's words are not drawn to one ruler, so
# the r (from Records) is a pixel shorter than its neighbours and the M a pixel taller. That
# can be evened out -- but only by RESAMPLING those two letters, and rescaling 4 px of
# outline by 16/17 cannot land on whole pixels, so their stroke comes out a pixel thin or
# thick in places. Every other letter is untouched either way.
#   True  -> heights even, two letters with a slightly wobbly stroke
#   False -> every letter exactly as drawn, the r a pixel short
MATCH_HEIGHTS = False

WORDS = {                           # the item art, and the letters in it (spaces have no face)
    "item_main_game": "MainGame",
    "item_time_attack": "TimeAttack",
    "item_records": "Records",
    "item_options": "Options",
}

# Where each letter of "Marathon" comes from: (item, index of the letter in that word).
SOURCE = {
    "M": ("item_main_game", 0),
    "a": ("item_main_game", 1),
    "r": ("item_records", 4),
    "t": ("item_options", 2),
    "o": ("item_options", 4),
    "n": ("item_options", 5),
    "k": ("item_time_attack", 9),   # only for the h's ascender
}

_CACHE = {}


def face(img):
    """The white face of the lettering, as a mask. (The outline is a dark blue.)"""
    a = np.array(img.convert("RGBA")).astype(int)
    return (a[..., 3] > 120) & (a[..., :3].min(axis=2) > 150)


def face_box(img):
    """(left, top, right, bottom) of the face inside a letter tile, inclusive."""
    f = face(img)
    ys, xs = np.where(f.any(axis=1))[0], np.where(f.any(axis=0))[0]
    return xs[0], ys[0], xs[-1], ys[-1]


def cut(name):
    """[(tile, x, y)] for one item: each letter with a whole outline, and where it sat."""
    if name not in _CACHE:
        img = Image.open(os.path.join(PARTS, name + ".png")).convert("RGBA")
        _CACHE[name] = split_letters(img, len(WORDS[name]))
    return _CACHE[name]


def letters(name):
    return [tile for tile, _x, _y in cut(name)]


def origins(name):
    return [x for _tile, x, _y in cut(name)]


def letter(ch):
    name, i = SOURCE[ch]
    return letters(name)[i]


def graft_h():
    """k's ascender over n's shoulder: the h the mockup never drew."""
    n, k = letter("n"), letter("k")
    fn, fk = face(n), face(k)
    nl, nt, _nr, nb = face_box(n)
    kl, kt, _kr, kb = face_box(k)

    # Line the two stems up: same left edge, same baseline.
    dx, dy = nl - kl, nb - kb

    # k's stem, and only the stem: the columns its face fills at the very top. Lower down the
    # arm joins on the right, and the seam is taken above that.
    stem = np.where(fk[kt + 1])[0]
    arm = next((y for y in range(kt + 1, kb) if len(np.where(fk[y])[0]) > len(stem) + 1), kb)
    seam = min(arm, (nt - dy) + 2)          # below n's x-height, above k's arm
    stem_right = stem[-1] + 4               # the stem's face, and its outline

    lift = max(0, -dy + kt - nt)            # room above n for the ascender
    out = Image.new("RGBA", (n.width, n.height + lift), (0, 0, 0, 0))
    out.alpha_composite(k.crop((0, 0, stem_right, seam)), (dx, dy + lift))
    out.alpha_composite(n, (0, lift))

    # n carries its own outline ABOVE the shoulder, and that outline now lies across the stem
    # as a blue band. Lay the stem's face back over it -- only at the join, since repainting
    # the whole stem would flatten the anti-aliasing on the ascender's top.
    join_top = max(kt + 1, (nt - dy) - 4)
    mask = np.zeros(fk.shape, bool)
    mask[join_top:seam, stem[0]:stem[-1] + 1] = fk[join_top:seam, stem[0]:stem[-1] + 1]
    white = np.array(k).astype(int)[..., :3][fk].max(axis=0)
    px = np.zeros(fk.shape + (4,), np.uint8)
    px[mask] = list(white) + [255]
    out.alpha_composite(Image.fromarray(px, "RGBA").crop((0, 0, stem_right, seam)), (dx, dy + lift))
    return out


def match_xheight(tiles, word):
    """Put every letter on the same two rulers: one x-height, one for the tall ones.

    The mockup's four words were not drawn to one: the x-height letters of "Records" are
    16 px tall and those of "Main Game" and "Options" are 17, and Main Game's capital M is
    22 where the ascenders of the other words are 21. Marathon takes letters from all of
    them, so its r came out a pixel short -- sitting on the baseline with its top below its
    neighbours', which reads as dropped -- and its M a pixel proud.

    "Records" has both a capital and an ascender, R and d, and draws them the same height,
    so the tall letters here are levelled too.

    A pixel in sixteen, resampled: it does not show.
    """
    heights = [face_box(t)[3] - face_box(t)[1] + 1 for t in tiles]
    big = max(heights)
    groups = ([h for h in heights if h >= big * 0.9], [h for h in heights if h < big * 0.9])
    targets = [max(set(g), key=g.count) if g else None for g in groups]

    out = []
    for t, h in zip(tiles, heights):
        target = targets[0] if h >= big * 0.9 else targets[1]
        if target is None or h == target:
            out.append(t)
            continue
        # Resample properly, never nearest-neighbour. Nearest was the first try and it is
        # what made the stroke look botched: stretching 16 rows to 17 by DUPLICATING one of
        # them doubles whatever row it lands on, so the outline goes 3 px thick in one place
        # and the letter reads as damaged. The art is anti-aliased already, so resampling it
        # is the right tool -- it spreads the extra row across the letter instead.
        #
        # Scaling the TILE by the face's ratio overshoots -- the tile is the face plus its
        # outline, and the outline scales too. Try the heights either side of the estimate
        # and take the one whose FACE comes out the size asked for.
        guess = int(round(t.height * float(target) / h))
        best = None
        for th in range(guess - 2, guess + 3):
            if th < 1:
                continue
            got = t.resize((t.width, th), Image.LANCZOS)
            b = face_box(got)
            err = abs((b[3] - b[1] + 1) - target)
            if best is None or err < best[0]:
                best = (err, got)
        out.append(best[1])
    return out






def row_edges(mask):
    """Per row, the leftmost and rightmost face pixel (or None for an empty row)."""
    out = []
    for y in range(mask.shape[0]):
        xs = np.where(mask[y])[0]
        out.append((xs[0], xs[-1]) if len(xs) else None)
    return out


def kerning():
    """How much daylight the artist left after each letter, measured off the drawn words.

    Not one number for every pair: r overhangs to the right at the top, and in "Records"
    the d after it is set 7 px clear, where the other pairs are 2 to 4. Spacing every pair
    the same crowded the r badly -- its arm nearly touched the a that follows it.
    """
    after = {}
    for name, word in WORDS.items():
        tiles = letters(name)
        boxes = [face_box(t) for t in tiles]
        base = [b[3] for b in boxes]
        ox = origins(name)              # where each letter sat in the word it came from
        for i in range(len(tiles) - 1):
            a, b = np.array(face(tiles[i])), np.array(face(tiles[i + 1]))
            ea, eb = row_edges(a), row_edges(b)
            # line the two up on their baselines, and on the x the word put them at
            dy = base[i] - base[i + 1]
            dx = ox[i + 1] - ox[i]
            gaps = []
            for y in range(len(ea)):
                yy = y - dy
                if ea[y] is None or yy < 0 or yy >= len(eb) or eb[yy] is None:
                    continue
                gaps.append((eb[yy][0] + dx) - ea[y][1] - 1)
            if gaps and min(gaps) < 10:         # 10 and over is a word space, not a letter gap
                after.setdefault(word[i], []).append(min(gaps))
    return {ch: int(round(sorted(v)[len(v) // 2])) for ch, v in after.items()}


def compose(word):
    """The letters set down left to right on one baseline, each as close to the last as the
    art allows: the narrowest row-by-row daylight between two faces is what is held to, not
    the distance between their bounding boxes. Boxes were the first try, and they put the
    letter after r three pixels from the TIP OF ITS ARM, which is nothing at all lower down.
    Their outlines overlap, which is how the drawn words are made."""
    tiles = [graft_h() if ch == "h" else letter(ch) for ch in word]
    if MATCH_HEIGHTS:
        tiles = match_xheight(tiles, word)
    boxes = [face_box(t) for t in tiles]
    kern = kerning()

    baseline = max(b[3] for b in boxes)
    height = max(t.height + (baseline - b[3]) for t, b in zip(tiles, boxes))
    edges = [row_edges(face(t)) for t in tiles]

    # Every letter sits on the baseline, so a row of the word is (row in tile) + its lift.
    lifts = [baseline - b[3] for b in boxes]
    xs = [0]
    far = {}                                    # row of the word -> rightmost face pixel so far
    for y, e in enumerate(edges[0]):
        if e is not None:
            far[y + lifts[0]] = e[1] + xs[0]
    far_col = boxes[0][2]                       # rightmost face pixel of the word so far, any row
    for i in range(1, len(tiles)):
        want = kern.get(word[i - 1], GAP)
        # Two rules, and the looser wins. Row by row, so a letter may tuck under an
        # overhang; and column-wise, because r's arm reaches out diagonally and the row
        # rule alone let the next letter come within a pixel of its tip, which the word it
        # was cut from does not do.
        need = far_col + 1 + want - boxes[i][0]
        for y, e in enumerate(edges[i]):
            if e is None:
                continue
            row = y + lifts[i]
            if row in far:
                need = max(need, far[row] + 1 + want - e[0])
        xs.append(need)
        for y, e in enumerate(edges[i]):
            if e is not None:
                row = y + lifts[i]
                far[row] = max(far.get(row, -1), e[1] + need)
        far_col = max(far_col, boxes[i][2] + need)

    # A tile starts to the left of its face by the width of its outline, so shift the line
    # so nothing falls off the left of the picture.
    shift = -min(xs)
    xs = [x + shift for x in xs]
    width = max(x + t.width for x, t in zip(xs, tiles))

    # Each letter is laid down AS DRAWN -- its face, its blue outline and the soft graded
    # edge the two have. Drawing a fresh outline round the faces instead was tried, to make
    # one even stroke: it came out thin, flat and hard-cornered beside the words it sits
    # with, because the artist's edge fades over a pixel or two and a dilated mask does not.
    # Evenness is not worth that; it is fixed in match_xheight instead, which is where the
    # unevenness came from.
    #
    # Letters are UNIONED, one over the next, the way they were drawn.
    #
    # Taking the greater alpha instead was tried and it punched holes in the outline: where
    # two letters meet, each brings its own anti-aliased edge, and two edges of half alpha
    # keep half alpha under a max -- so the yellow behind showed through the seam as a notch.
    # Compositing adds them up to solid. It cannot muddy the colour either, because what
    # overlaps is the same blue: split_letters hands every letter the WHOLE of an outline it
    # shares with its neighbour, so the two agree about what is there.
    out = np.zeros((height, width, 4), float)
    for t, b, x in zip(tiles, boxes, xs):
        y = baseline - b[3]
        src = np.array(t).astype(float)
        dst = out[y:y + t.height, x:x + t.width]
        sa = src[..., 3:4] / 255.0
        da = dst[..., 3:4] / 255.0
        oa = sa + da * (1.0 - sa)
        safe = np.where(oa > 0.0, oa, 1.0)
        dst[..., :3] = (src[..., :3] * sa + dst[..., :3] * da * (1.0 - sa)) / safe
        dst[..., 3:4] = oa * 255.0
    out = np.clip(out + 0.5, 0, 255).astype(np.uint8)
    close_seams(out)
    smooth_joins(out)
    img = Image.fromarray(out, "RGBA")
    return img.crop(img.getbbox())


def close_seams(px):
    """Fill the pinholes the joins leave.

    Even unioned, two letters can fail to meet: each was cropped to its own ink, and where
    the kerning sets them a little further apart than the word they were cut from did, a
    sliver of nothing is left between their outlines. It is one pixel wide and you would not
    find it on a drawing -- but the menu draws this on a bright orange bar, and the bar came
    through the gap. Anything enclosed by solid ink on all four sides and not solid itself
    is such a hole, and is filled with the outline's own blue.

    The letters' counters -- the hole in an o, an a, an e -- are NOT caught by this: the
    mockup was cut from a flattened picture, so they are opaque background, not transparency,
    and the drawn words measure zero holes by this same test.
    """
    solid = px[..., 3] > 250
    h, w = solid.shape
    between_x = np.zeros_like(solid)
    for y in range(h):
        xs = np.where(solid[y])[0]
        if len(xs) > 1:
            between_x[y, xs[0]:xs[-1] + 1] = True
    between_y = np.zeros_like(solid)
    for x in range(w):
        ys = np.where(solid[:, x])[0]
        if len(ys) > 1:
            between_y[ys[0]:ys[-1] + 1, x] = True
    holes = between_x & between_y & ~solid
    px[holes] = [3, 38, 174, 255]           # the outline blue, straight off the mockup


def _shift(mask, dy, dx):
    out = np.zeros_like(mask)
    h, w = mask.shape
    ys0, ys1 = max(0, dy), min(h, h + dy)
    xs0, xs1 = max(0, dx), min(w, w + dx)
    out[ys0:ys1, xs0:xs1] = mask[ys0 - dy:ys1 - dy, xs0 - dx:xs1 - dx]
    return out


OFFSETS = [(dy, dx) for dy in (-1, 0, 1) for dx in (-1, 0, 1)]


def smooth_joins(px):
    """Fill the nicks where two letters' outlines meet at different angles.

    Letters drawn side by side in one word share a single continuous outer contour. These
    are cut from four different words, so where one letter's outline ends and the next one's
    begins the two outer edges need not line up, and the step between them reads as a wedge
    of background bitten out of the letter -- on the a after the r, most of all.

    A morphological closing (grow, then shrink by the same amount) fills any concavity
    narrower than what it grows by and leaves every other edge exactly where it was. Only
    the pixels it ADDS are painted, in the outline's blue; nothing is ever taken away.
    """
    solid = px[..., 3] > 128
    grown = np.zeros_like(solid)
    for dy, dx in OFFSETS:
        grown |= _shift(solid, dy, dx)
    shrunk = np.ones_like(grown)
    for dy, dx in OFFSETS:
        shrunk &= _shift(grown, dy, dx)
    px[shrunk & ~solid] = [3, 38, 174, 255]


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
