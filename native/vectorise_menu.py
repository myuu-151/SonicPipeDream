"""Trace the menu's cut-out parts into shapes, and draw them again at four times the size.

    python native/vectorise_menu.py            (needs Pillow, numpy)
        -> external/ui/menu/parts/<part>_4x.png      for every part in PARTS below
           external/ui/menu/parts/_vector_check.png  each part: the cut-out, the redraw, both
                                                     as the screen would show them

Why: the menu is drawn at about twice the mockup's size, and a piece cut from the mockup at
1:1 is a small picture the GPU has to magnify, which is a blur. Three ways of enlarging the
pixels in gen_menu_assets.py were tried and every one was worse. What did work was the
watermark, which split_menu.py does not cut out at all: it BUILDS the letters from rounded
rectangles and renders them at 8x, so they can be had at any size. This does the same for
the rest, without measuring every letter by hand.

How: a part is made of a few flat colours -- a white face, a blue outline, a red arrow, the
facets of a gem. Each colour's region is traced: its pixel boundary is followed into a
closed polygon (a staircase, one step a pixel), and the staircase is rounded into a curve by
corner-cutting (Chaikin's subdivision), which is what the anti-aliased original was a
picture of. The curves are filled at 8x the size, the regions painted largest first so the
small ones -- counters, the arrow's tip, a facet's highlight -- land on top, and the whole
thing is halved to 4x, which gives it an edge one new pixel wide.

Shaded parts -- the two button spheres, the orange plates with their row gradient -- are not
made of flat colours, and quantising them to a few would band them. For those only the
SILHOUETTE is traced; the colour inside comes from a smooth resample of the original, which
is right for a gradient. Any bright lettering on them (the A, the B) is traced as well and
laid on top.
"""

import os

import numpy as np
from PIL import Image, ImageDraw

HERE = os.path.dirname(os.path.abspath(__file__))
PARTS_DIR = os.path.abspath(os.path.join(HERE, "..", "external", "ui", "menu", "parts"))

SCALE = 4                   # the output, in multiples of the cut-out
SS = 2                      # drawn at SCALE * SS, then halved: the anti-aliasing
SMOOTH_ROUNDS = 4           # Chaikin passes: 4 turns a pixel staircase into a clean curve
MIN_REGION = 3              # pixels; anything smaller is anti-aliasing debris, not a shape

# What to trace. "flat": every colour is a region. "shaded": silhouette plus bright lettering.
PARTS = {
    "item_main_game": "flat",
    "item_marathon": "flat",
    "item_records": "flat",
    "item_options": "flat",
    "item_time_attack": "flat",
    "title_text": "flat",
    "cursor_arrow": "flat",
    "emerald": "flat",
    "label_special_stage": "flat",
    "label_select": "flat",
    "label_back": "flat",
    "preview_frame": "flat",
    "title_banner": "shaded",
    "select_bar": "shaded",
    "button_a": "shaded",
    "button_b": "shaded",
}


# ------------------------------------------------------------------ colours
def inks_of(a, limit=6, apart=90):
    """The few flat colours a part is made of, most-used first. Colours near a commoner one
    are that one, softened by anti-aliasing, not an ink of their own."""
    opaque = a[..., 3] > 128
    flat = a[..., :3][opaque].astype(int)
    seen = {}
    for c in map(tuple, flat):
        seen[c] = seen.get(c, 0) + 1
    inks = []
    for c, _n in sorted(seen.items(), key=lambda kv: -kv[1]):
        if all(sum(abs(x - y) for x, y in zip(c, have)) > apart for have in inks):
            inks.append(c)
        if len(inks) >= limit:
            break
    return inks


def owner_map(a, inks):
    """Which ink each opaque pixel belongs to (-1 outside)."""
    opaque = a[..., 3] > 128
    dist = np.stack([np.abs(a[..., :3].astype(int) - np.array(ink)).sum(axis=2) for ink in inks])
    own = np.argmin(dist, axis=0)
    own[~opaque] = -1
    return own


# ------------------------------------------------------------------ tracing
def boundaries(mask):
    """Every closed boundary of a binary mask, as a polygon of pixel-corner points.

    Each boundary edge is a unit step between an inside pixel and an outside neighbour,
    directed so the inside is on its left. Chaining edges end to start gives the loops;
    where four edges meet at a corner (two regions touching only diagonally) the leftmost
    turn is taken, which keeps each region's loops separate.
    """
    h, w = mask.shape
    pad = np.zeros((h + 2, w + 2), bool)
    pad[1:-1, 1:-1] = mask
    edges = {}                                  # start point -> [end points]

    def add(p, q):
        edges.setdefault(p, []).append(q)

    ys, xs = np.where(pad)
    for y, x in zip(ys, xs):
        # corners of pixel (x, y) in the padded frame; y grows downward
        if not pad[y - 1, x]: add((x, y), (x + 1, y))              # top edge, left to right
        if not pad[y, x + 1]: add((x + 1, y), (x + 1, y + 1))      # right edge, downward
        if not pad[y + 1, x]: add((x + 1, y + 1), (x, y + 1))      # bottom edge, right to left
        if not pad[y, x - 1]: add((x, y + 1), (x, y))              # left edge, upward

    loops = []
    while edges:
        start = next(iter(edges))
        loop, p, prev = [], start, None
        while True:
            outs = edges.get(p)
            if not outs:
                break
            if len(outs) == 1 or prev is None:
                q = outs.pop(0)
            else:
                # prefer the left turn relative to the direction we arrived by
                dx, dy = p[0] - prev[0], p[1] - prev[1]
                left = (p[0] + dy, p[1] - dx)
                q = outs.pop(outs.index(left)) if left in outs else outs.pop(0)
            if not outs:
                del edges[p]
            loop.append(p)
            prev, p = p, q
            if p == start:
                break
        if len(loop) >= 4:
            loops.append([(x - 1, y - 1) for x, y in loop])      # back to unpadded coordinates
    return loops


def area(poly):
    s = 0.0
    for i in range(len(poly)):
        x0, y0 = poly[i]
        x1, y1 = poly[(i + 1) % len(poly)]
        s += x0 * y1 - x1 * y0
    return s * 0.5


def chaikin(poly, rounds):
    """Corner cutting: each pass replaces every corner with two points a quarter of the way
    along its edges. A pixel staircase becomes the curve it was approximating."""
    pts = [(float(x), float(y)) for x, y in poly]
    for _ in range(rounds):
        out = []
        n = len(pts)
        for i in range(n):
            x0, y0 = pts[i]
            x1, y1 = pts[(i + 1) % n]
            out.append((0.75 * x0 + 0.25 * x1, 0.75 * y0 + 0.25 * y1))
            out.append((0.25 * x0 + 0.75 * x1, 0.25 * y0 + 0.75 * y1))
        pts = out
    return pts


def regions(mask):
    """The connected regions of a mask, each as (size, outer loop, [hole loops])."""
    from collections import deque
    h, w = mask.shape
    label = np.full(mask.shape, -1, int)
    sizes = []
    for y0 in range(h):
        for x0 in range(w):
            if mask[y0, x0] and label[y0, x0] < 0:
                k = len(sizes)
                todo, n = deque([(y0, x0)]), 0
                label[y0, x0] = k
                while todo:
                    y, x = todo.popleft()
                    n += 1
                    for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                        v, u = y + dy, x + dx
                        if 0 <= v < h and 0 <= u < w and mask[v, u] and label[v, u] < 0:
                            label[v, u] = k
                            todo.append((v, u))
                sizes.append(n)
    out = []
    for k, n in enumerate(sizes):
        if n < MIN_REGION:
            continue
        loops = boundaries(label == k)
        outer = [l for l in loops if area(l) > 0]
        holes = [l for l in loops if area(l) < 0]
        out.append((n, outer, holes))
    return out


# ------------------------------------------------------------------ drawing
def render(size, layers):
    """`layers` is [(colour rgb, mask)] painted in order. Each mask is traced, smoothed and
    filled at SCALE * SS, then the picture is halved to SCALE."""
    w, h = size
    k = SCALE * SS
    canvas = Image.new("RGBA", (w * k, h * k), (0, 0, 0, 0))
    for colour, mask in layers:
        cov = Image.new("L", (w * k, h * k), 0)
        d = ImageDraw.Draw(cov)
        for _n, outers, holes in regions(mask):
            for loop in outers:
                d.polygon([(x * k, y * k) for x, y in chaikin(loop, SMOOTH_ROUNDS)], fill=255)
            for loop in holes:
                d.polygon([(x * k, y * k) for x, y in chaikin(loop, SMOOTH_ROUNDS)], fill=0)
        paint = Image.new("RGBA", canvas.size, tuple(int(c) for c in colour) + (255,))
        canvas.paste(paint, (0, 0), cov)
    return canvas.resize((w * SCALE, h * SCALE), Image.BOX)


def render_shaded(a, inks):
    """Silhouette traced; colour resampled; any bright lettering traced on top."""
    h, w = a.shape[:2]
    k = SCALE * SS
    alpha = a[..., 3].astype(float) / 255.0
    pre = np.dstack([a[..., :3] * alpha[..., None], alpha[..., None] * 255.0])
    big = np.asarray(Image.fromarray(np.clip(pre, 0, 255).astype(np.uint8), "RGBA")
                     .resize((w * k, h * k), Image.BICUBIC)).astype(float)
    ab = np.maximum(big[..., 3:4] / 255.0, 1e-4)
    rgb = np.clip(big[..., :3] / ab, 0, 255).astype(np.uint8)

    sil = render((w, h), [((255, 255, 255), a[..., 3] > 128)])
    sil_a = np.asarray(sil.resize((w * k, h * k), Image.BILINEAR))[..., 3]
    out = Image.fromarray(np.dstack([rgb, sil_a]), "RGBA")

    # bright lettering on the shading (the button letters): trace it too
    bright = (a[..., 3] > 128) & (a[..., :3].min(axis=2) > 200)
    if bright.sum() >= MIN_REGION:
        light = tuple(int(v) for v in np.median(a[..., :3][bright], axis=0))
        letters = render((w, h), [(light, bright)]).resize((w * k, h * k), Image.BILINEAR)
        out.alpha_composite(letters)
    return out.resize((w * SCALE, h * SCALE), Image.BOX)


def redraw(part, kind):
    img = Image.open(os.path.join(PARTS_DIR, part + ".png")).convert("RGBA")
    a = np.array(img)
    inks = inks_of(a)
    if kind == "shaded":
        return render_shaded(a, inks)
    own = owner_map(a, inks)
    # largest ink first, so the small regions sit on top of the big ones
    order = sorted(range(len(inks)), key=lambda i: -(own == i).sum())
    return render(img.size, [(inks[i], own == i) for i in order])


# ------------------------------------------------------------------ the check sheet
def as_screen(img, factor):
    """What the GPU would show: the picture drawn at 2x the mockup's size with bilinear
    filtering. A 1:1 cut-out is magnified 2x; a 4x redraw is minified 2x."""
    target = (img.width * 2 // factor, img.height * 2 // factor)
    return img.resize(target, Image.BILINEAR)


def main():
    sheet_rows = []
    for part, kind in PARTS.items():
        src = os.path.join(PARTS_DIR, part + ".png")
        if not os.path.exists(src):
            print("skip %s (no art)" % part)
            continue
        out = redraw(part, kind)
        out.save(os.path.join(PARTS_DIR, part + "_4x.png"))
        print("%-22s %s -> %s" % (part, Image.open(src).size, out.size))
        before = as_screen(Image.open(src).convert("RGBA"), 1)
        after = as_screen(out, SCALE)
        sheet_rows.append((part, before, after))

    yellow = (246, 211, 43, 255)
    W = max(r[1].width for r in sheet_rows) * 2 + 40
    H = sum(max(r[1].height, r[2].height) + 24 for r in sheet_rows) + 10
    sheet = Image.new("RGBA", (W, H), (70, 70, 70, 255))
    d = ImageDraw.Draw(sheet)
    y = 6
    for part, before, after in sheet_rows:
        for col, im in ((0, before), (1, after)):
            x = 10 + col * (W // 2)
            bg = Image.new("RGBA", im.size, yellow)
            bg.alpha_composite(im)
            sheet.alpha_composite(bg, (x, y + 14))
        d.text((10, y), part + "   (left: cut-out, as shown / right: redrawn, as shown)", fill=(230, 230, 230, 255))
        y += max(before.height, after.height) + 24
    sheet.save(os.path.join(PARTS_DIR, "_vector_check.png"))
    print("wrote _vector_check.png")


if __name__ == "__main__":
    main()
