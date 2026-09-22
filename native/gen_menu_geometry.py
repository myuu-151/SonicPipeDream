"""Build the menu's pieces as GEOMETRY, and draw them at four times the mockup's size.

    python native/gen_menu_geometry.py          (needs Pillow, numpy)
        -> external/ui/menu/parts/<part>_4x.png        one per piece below
           external/ui/menu/parts/_geometry_check.png  each piece: the mockup's, the redraw

The menu is shown at about twice the mockup's size, so a piece cut from the mockup is a
small picture the GPU has to magnify, and that is a blur. Enlarging the pixels was tried
three ways and every one was worse. What worked was the watermark, which split_menu.py does
not cut out at all: it builds the letters from rounded rectangles and renders them at 8x.
This does the same for everything else.

THE FONT. Every letter the menu uses is a union of rounded rectangles, cut by rectangular
counters, with three that need a polygon (A, M, k). Measured off the mockup: cap height 21,
x-height 17, stems 7 wide, outer corners rounded about 2.5, counters about 1. The blue
outline is 2 wide. Glyphs are defined once at that size and scaled for the smaller uses:
the title (caps 16 high) and the two button legends (10 high, blue, no outline).

THE OUTLINE is exact, not a blur: each primitive is drawn again grown by the outline width
-- a rounded rectangle by a bigger rounded rectangle, a polygon by the polygon plus its
edges stroked and its corners discs, a counter by a smaller counter. That is the Minkowski
sum with a disc, which is what an outline is.

THE REST: the two orange plates from their measured polygons and row colours (the banner
with its yellow bands and stripes, the bar with its yellow line and blue underline); the
button spheres as a radial gradient with a highlight and the letter from the font; the gem
from its silhouette and facets; the arrow; the picture frame.

Every piece is drawn on a canvas exactly 4x the size of the mockup's cut-out, in the same
place within it, so gen_menu_assets.py can use the bigger drawing and MenuLayout.lua does
not move anything.
"""

import os

import numpy as np
from PIL import Image, ImageDraw

HERE = os.path.dirname(os.path.abspath(__file__))
PARTS = os.path.abspath(os.path.join(HERE, "..", "external", "ui", "menu", "parts"))

SS = 8                      # drawn at this many times the mockup, then halved to 4x
OUT_SCALE = 4

WHITE = (254, 254, 254)
BLUE = (3, 38, 174)         # the lettering's outline, and the labels
RED = (239, 1, 4)           # the cursor

CAP, XH, STEM = 21.0, 17.0, 7.0
R, RC = 2.5, 1.0            # outer corners; counters
OUTLINE = 3.0             # measured: 3 px of solid blue outside the face


# ------------------------------------------------------------------ a mask of primitives
class Shape:
    """A list of fills and holes, drawable at any scale, optionally GROWN by a margin --
    which is how the outline is made."""

    def __init__(self):
        self.ops = []

    def rr(self, x0, y0, x1, y1, r=R, corners=(1, 1, 1, 1), hole=False):
        self.ops.append(("rr", (x0, y0, x1, y1, r, corners), hole))
        return self

    def poly(self, pts, hole=False):
        self.ops.append(("poly", list(pts), hole))
        return self

    def ellipse(self, x0, y0, x1, y1, hole=False):
        self.ops.append(("el", (x0, y0, x1, y1), hole))
        return self

    def moved(self, dx, dy, scale=1.0, xscale=1.0):
        """The same shape, scaled (and condensed sideways by xscale) and moved."""
        sx, sy = scale * xscale, scale
        s = Shape()
        for kind, arg, hole in self.ops:
            if kind == "rr":
                x0, y0, x1, y1, r, c = arg
                s.ops.append(("rr", (x0 * sx + dx, y0 * sy + dy, x1 * sx + dx, y1 * sy + dy,
                                     r * min(sx, sy), c), hole))
            elif kind == "poly":
                s.ops.append(("poly", [(x * sx + dx, y * sy + dy) for x, y in arg], hole))
            else:
                x0, y0, x1, y1 = arg
                s.ops.append(("el", (x0 * sx + dx, y0 * sy + dy, x1 * sx + dx, y1 * sy + dy), hole))
        return s

    def draw(self, canvas, k, grow=0.0):
        """Paint onto an 'L' canvas at scale k, every fill grown by `grow` (mockup px) and
        every hole shrunk by it."""
        d = ImageDraw.Draw(canvas)
        for kind, arg, hole in self.ops:
            g = -grow if hole else grow
            fill = 0 if hole else 255
            if kind == "rr":
                x0, y0, x1, y1, r, c = arg
                x0, y0, x1, y1 = x0 - g, y0 - g, x1 + g, y1 + g
                if x1 <= x0 or y1 <= y0:
                    continue
                # a corner can be no rounder than half the shorter side: a grown dot
                # (the i's) would otherwise ask for a radius bigger than the box
                box = (x0 * k, y0 * k, x1 * k, y1 * k)
                rad = int(min((r + g) * k, (box[2] - box[0]) / 2.0 - 1, (box[3] - box[1]) / 2.0 - 1))
                if rad < 1:
                    d.rectangle(box, fill=fill)
                else:
                    d.rounded_rectangle(box, radius=rad, fill=fill, corners=tuple(bool(v) for v in c))
            elif kind == "el":
                x0, y0, x1, y1 = arg
                d.ellipse(((x0 - g) * k, (y0 - g) * k, (x1 + g) * k, (y1 + g) * k), fill=fill)
            else:
                pts = [(x * k, y * k) for x, y in arg]
                d.polygon(pts, fill=fill)
                if grow > 0.0:
                    # the polygon grown by a disc: its edges stroked, its corners discs.
                    # For a hole that means the hole SHRINKS, so the stroke is painted in.
                    w = grow * k
                    edge_fill = 255 if not hole else 255
                    n = len(pts)
                    for i in range(n):
                        d.line([pts[i], pts[(i + 1) % n]], fill=edge_fill, width=int(round(2 * w)))
                        x, y = pts[i]
                        d.ellipse((x - w, y - w, x + w, y + w), fill=edge_fill)
                    if hole:
                        pass
        return canvas


# ------------------------------------------------------------------ the font
# Each glyph: (advance width of its face, top of its face below the cap line, Shape).
# Coordinates are the face's own, x from its left edge, y from its top.
def _glyphs():
    g = {}

    def add(ch, w, top, shape):
        g[ch] = (float(w), float(top), shape)

    # ---- lowercase, x-height 17, top = CAP - XH = 4
    xt = CAP - XH
    add("a", 18, xt, Shape()
        .rr(0, 6, 18, 17, R)                 # bowl and stem body
        .rr(1, 0, 18, 4.5, R, (1, 1, 0, 0))  # the arch over the top
        .rr(11, 0, 18, 17, R, (0, 1, 1, 0))  # the stem
        .rr(6, 10, 11, 12, RC, hole=True))
    add("c", 16, xt, Shape()
        .rr(0, 0, 16, 16, R)
        .rr(7, 4, 18, 11, RC, (1, 0, 0, 1), hole=True))
    add("d", 18, 0, Shape()
        .rr(0, 5, 18, 21, R)
        .rr(11, 0, 18, 21, R, (1, 1, 0, 0))
        .rr(7, 9, 11, 16, RC, hole=True))
    add("e", 18, xt, Shape()
        .rr(0, 0, 18, 17, R)
        .rr(7, 4, 11.5, 6, RC, hole=True)
        .rr(7, 10, 20, 12, RC, (1, 0, 0, 1), hole=True))
    add("h", 19, 0, Shape()
        .rr(0, 0, 7, 21, R, (1, 1, 0, 0))
        .rr(0, 4, 19, 21, R, (0, 1, 0, 0))
        .rr(7, 9, 12, 21, RC, (1, 1, 0, 0), hole=True))
    add("i", 7, 0, Shape()
        .rr(0, 0, 7, 3, R)
        .rr(0, 5, 7, 22, R))
    add("k", 19, 0, Shape()
        .rr(0, 0, 7, 21, R)
        .poly([(11, 5), (19, 5), (19, 6.5), (13.5, 11), (7, 11), (7, 9.5)])      # the arm
        .rr(7, 9, 14, 16, RC)                                                   # the knee
        .poly([(7, 14), (15, 14), (19, 18.5), (19, 21), (11, 21), (7, 17)]))    # the leg
    add("l", 7, 0, Shape().rr(0, 0, 7, 21, R))
    add("m", 25, xt, Shape()
        .rr(0, 0, 25, 17, R)
        .rr(7, 5, 9, 17, RC, (1, 1, 0, 0), hole=True)
        .rr(15, 5, 18, 17, RC, (1, 1, 0, 0), hole=True))
    add("n", 19, xt, Shape()
        .rr(0, 0, 19, 17, R)
        .rr(7, 5, 12, 17, RC, (1, 1, 0, 0), hole=True))
    add("o", 18, xt, Shape()
        .rr(0, 0, 18, 16, R)
        .rr(7, 4, 11, 12, 1.5, hole=True))
    add("p", 18, xt, Shape()
        .rr(0, 0, 18, 16, R)
        .rr(0, 0, 7, 21, R, (0, 0, 1, 1))
        .rr(7, 4, 11, 11, RC, hole=True))
    add("r", 12, xt, Shape()
        .rr(0, 0, 7, 16, R, (0, 0, 1, 1))
        .rr(0, 0, 12, 5, R, (1, 1, 1, 0)))
    add("s", 17, xt, Shape()
        .rr(0, 0, 17, 4, R, (1, 1, 1, 0))
        .rr(0, 2, 7, 7, RC, (0, 0, 0, 1))
        .rr(0, 6, 17, 10, R, (0, 1, 0, 1))
        .rr(11, 9, 17, 13, RC, (0, 1, 0, 0))
        .rr(1, 12, 17, 16, R, (0, 1, 1, 1)))
    add("t", 13, 0, Shape()
        .rr(2, 0, 9, 21, R, (1, 1, 0, 1))
        .rr(0, 5, 13, 9, RC)
        .rr(2, 16, 13, 21, R, (0, 0, 1, 1)))

    # ---- capitals, cap height 21, top 0
    add("A", 21, 0, Shape()
        .poly([(5, 0), (16, 0), (21, 21), (0, 21)])
        .poly([(9.5, 6), (11.5, 6), (12, 12), (9, 12)], hole=True)
        .poly([(7, 17), (13, 17), (14, 21), (7, 21)], hole=True))
    add("B", 19, 0, Shape()
        .rr(0, 0, 18, 11, 4.0, (0, 1, 1, 0))
        .rr(0, 10, 19, 21, 4.0, (0, 1, 1, 0))
        .rr(0, 0, 7, 21, R, (1, 0, 0, 1))
        .rr(7, 4, 12, 7, RC, hole=True)
        .rr(7, 14, 13, 17, RC, hole=True))
    add("C", 21, 0, Shape()
        .rr(0, 0, 21, 21, 3.0)
        .rr(8, 5, 23, 16, RC, (1, 0, 0, 1), hole=True))
    add("D", 21, 0, Shape()
        .rr(0, 0, 21, 21, 4.0, (0, 1, 1, 0))
        .rr(7, 5, 14, 16, RC, hole=True))
    add("E", 19, 0, Shape()
        .rr(0, 0, 19, 21, R)
        .rr(7, 5, 21, 8, RC, (1, 0, 0, 1), hole=True)
        .rr(7, 13, 21, 16, RC, (1, 0, 0, 1), hole=True))
    add("G", 22, 0, Shape()
        .rr(0, 0, 22, 22, 3.5)
        .rr(8, 5, 24, 8, RC, (1, 0, 0, 1), hole=True)
        .rr(8, 8, 11.5, 13, RC, hole=True)
        .rr(8, 13, 15, 16, RC, hole=True))
    add("I", 7, 0, Shape().rr(0, 0, 7, 21, R))
    add("M", 29, 0, Shape()
        .rr(0, 0, 29, 22, 1.5)
        .poly([(11, 0), (17, 0), (14.5, 10)], hole=True)
        .poly([(20, 12), (21, 12), (21, 22), (18, 22)], hole=True)
        .poly([(8, 14), (9, 14), (11, 22), (7, 22)], hole=True))
    add("N", 21, 0, Shape()
        .rr(0, 0, 7, 21, R, (1, 0, 0, 1))
        .rr(14, 0, 21, 21, R, (0, 1, 1, 0))
        .poly([(0, 0), (9, 0), (21, 17), (21, 21), (12, 21), (0, 4)]))
    add("O", 22, 0, Shape()
        .rr(0, 0, 22, 21, 3.0)
        .rr(7, 5, 14, 16, 1.5, hole=True))
    add("P", 19, 0, Shape()
        .rr(0, 0, 19, 14, 4.0, (0, 1, 1, 0))
        .rr(0, 0, 7, 21, R, (1, 0, 0, 1))
        .rr(7, 5, 12.5, 9, RC, hole=True))
    add("R", 19, 0, Shape()
        .rr(0, 0, 19, 15, 4.0, (0, 1, 1, 0))
        .rr(0, 0, 7, 21, R, (1, 0, 0, 1))
        .rr(10, 14, 19, 21, R, (0, 0, 1, 0))
        .rr(7, 5, 12, 9, RC, hole=True))
    add("S", 20, 0, Shape()
        .rr(0, 0, 20, 5, R, (1, 1, 1, 0))
        .rr(0, 3, 7.5, 9, RC, (0, 0, 0, 1))
        .rr(0, 8, 20, 13, R, (0, 1, 0, 1))
        .rr(12.5, 12, 20, 17, RC, (0, 1, 0, 0))
        .rr(1, 16, 20, 21, R, (0, 1, 1, 1)))
    add("T", 19, 0, Shape()
        .rr(0, 0, 19, 5, R)
        .rr(6, 5, 13, 21, R, (0, 0, 1, 1)))
    return g


GLYPHS = _glyphs()

# daylight between faces: the mockup's own, measured. Not one number: r, d and p overhang
AFTER = {"r": 2.0, "d": 2.0, "p": 2.0, "A": 4.0}
GAP, SPACE = 3.0, 12.0


def layout(text, scale=1.0, xscale=1.0):
    """[(char, x of face left, y of face top)] at `scale`, cap line at 0, condensed by xscale."""
    out, x = [], 0.0
    for ch in text:
        if ch == " ":
            x += SPACE * scale * xscale
            continue
        w, top, _ = GLYPHS[ch]
        out.append((ch, x, top * scale))
        x += (w + AFTER.get(ch, GAP)) * scale * xscale
    return out


def text_width(text, scale=1.0, xscale=1.0):
    placed = layout(text, scale, xscale)
    return max(x + GLYPHS[ch][0] * scale * xscale for ch, x, _t in placed)


def render_text(text, scale=1.0, outline=OUTLINE, face=WHITE, ink=BLUE, canvas=None, at=(0, 0), xscale=1.0):
    """Text drawn at 8x into an RGBA image. `canvas` is (w, h) in mockup px; `at` is where
    the cap-line/left-edge origin of the text goes, in mockup px."""
    placed = layout(text, scale, xscale)
    if canvas is None:
        canvas = (text_width(text, scale, xscale) + 2 * outline + 1, CAP * scale + 5 * scale + 2 * outline + 1)
        at = (outline + 0.5, outline + 0.5)
    W, H = int(round(canvas[0] * SS)), int(round(canvas[1] * SS))
    layers = [(ink, outline)] if outline > 0 else []
    layers.append((face, 0.0))
    out = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    for colour, grow in layers:
        mask = Image.new("L", (W, H), 0)
        for ch, x, top in placed:
            GLYPHS[ch][2].moved(at[0] + x, at[1] + top, scale, xscale).draw(mask, SS, grow)
        out.paste(Image.new("RGBA", (W, H), colour + (255,)), (0, 0), mask)
    return out


# ------------------------------------------------------------------ the other pieces
def draw_shape(size, shape, colour, grow=0.0, into=None):
    W, H = int(round(size[0] * SS)), int(round(size[1] * SS))
    out = into if into is not None else Image.new("RGBA", (W, H), (0, 0, 0, 0))
    mask = Image.new("L", (W, H), 0)
    shape.draw(mask, SS, grow)
    out.paste(Image.new("RGBA", (W, H), colour + (255,)), (0, 0), mask)
    return out


def cursor():                                  # 15 x 24: a red triangle, tip to the right
    return draw_shape((15, 24), Shape().poly([(0.5, 0.5), (14.5, 12), (0.5, 23.5)]), RED)


def frame():                                   # 173 x 151: a blue border, 4 wide
    s = Shape().rr(0, 0, 172, 151, 2.0).rr(4, 4, 168.5, 147, 1.0, hole=True)
    return draw_shape((173, 151), s, (14, 45, 159))


def banner():                                  # 323 x 35: the title's orange plate
    size = (323, 35)
    W, H = size[0] * SS, size[1] * SS
    out = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    plate = Shape().poly([(0, 0.6), (297.3, 0.6), (322.6, 35), (0, 35)])
    mask = plate.draw(Image.new("L", (W, H), 0), SS)
    # rows: yellow bands top and bottom, orange between
    rows = np.zeros((H, 3), float)
    for y in range(H):
        my = y / float(SS)
        rows[y] = (252, 225, 73) if my < 3.5 else (252, 227, 69) if my >= 31 else (242, 137, 18)
    rgb = np.broadcast_to(rows[:, None, :], (H, W, 3)).astype(np.uint8)
    out = Image.fromarray(np.dstack([rgb, np.asarray(mask)]), "RGBA")
    # the four yellow stripes at the left
    stripes = Shape()
    for y0 in (8, 13, 19, 25):
        stripes.rr(0, y0, 23.5, y0 + 2, 0.5)
    draw_shape(size, stripes, (253, 218, 67), into=out)
    return out


def bar():                                     # 288 x 45: the highlight plate
    size = (288, 45)
    W, H = size[0] * SS, size[1] * SS
    plate = Shape().poly([(0.3, 0.6), (287.2, 0.6), (269.8, 44.4), (0.3, 44.4)])
    mask = np.asarray(plate.draw(Image.new("L", (W, H), 0), SS))
    rows = np.zeros((H, 3), float)
    for y in range(H):
        my = y / float(SS)
        rows[y] = (247, 155, 7) if my < 39 else (251, 200, 43) if my < 41 else (4, 45, 173)
    rgb = np.broadcast_to(rows[:, None, :], (H, W, 3)).astype(np.uint8)
    return Image.fromarray(np.dstack([rgb, mask]), "RGBA")


def button(letter, size, centre, radius, rim, mid, glint, letter_scale, letter_at):
    W, H = size[0] * SS, size[1] * SS
    yy, xx = np.mgrid[0:H, 0:W]
    cx, cy = centre[0] * SS, centre[1] * SS
    d = np.sqrt((xx - cx) ** 2 + (yy - cy) ** 2) / (radius * SS)
    t = np.clip(d, 0, 1) ** 1.6
    rgb = np.array(mid, float) * (1 - t[..., None]) + np.array(rim, float) * t[..., None]
    # a soft highlight up and to the left
    hx, hy = cx - 0.22 * radius * SS, cy - 0.38 * radius * SS
    h = np.exp(-(((xx - hx) ** 2 + (yy - hy) ** 2) / (2 * (0.30 * radius * SS) ** 2)))
    rgb = rgb * (1 - 0.85 * h[..., None]) + np.array(glint, float) * (0.85 * h[..., None])
    alpha = np.clip((1.0 - d) * radius * SS, 0, 1) * 255       # a one-pixel soft rim
    out = Image.fromarray(np.dstack([np.clip(rgb, 0, 255).astype(np.uint8), alpha.astype(np.uint8)]), "RGBA")
    text = render_text(letter, letter_scale, outline=0.0, face=WHITE, canvas=size, at=letter_at)
    out.alpha_composite(text)
    return out


def gem():                                     # 30 x 24, green: recoloured per stage later
    size = (30, 24)
    sil = [(8, 1), (22, 1), (29, 7), (29, 9), (15.5, 23.5), (1, 9), (1, 7)]
    out = draw_shape(size, Shape().poly(sil), (2, 70, 24), grow=0.8)          # outline
    draw_shape(size, Shape().poly(sil), (2, 135, 44), into=out)                # body
    draw_shape(size, Shape().poly([(1, 9), (15.5, 9), (15.5, 23.5)]), (2, 98, 30), into=out)
    draw_shape(size, Shape().poly([(15.5, 9), (29, 9), (15.5, 23.5)]), (2, 120, 38), into=out)
    draw_shape(size, Shape().poly([(8, 1), (15, 1), (12, 9), (1, 9), (1, 7)]), (5, 169, 68), into=out)
    draw_shape(size, Shape().poly([(16, 1), (22, 1), (29, 7), (29, 9), (20, 9)]), (3, 150, 52), into=out)
    draw_shape(size, Shape().poly([(4, 5), (11, 5), (9, 9), (2, 9)]), (80, 204, 120), into=out)
    draw_shape(size, Shape().ellipse(4.5, 6, 7.5, 8.5), (179, 242, 188), into=out)
    return out


# ------------------------------------------------------------------ fitting the words
def face_box(img):
    a = np.array(img.convert("RGBA")).astype(int)
    f = (a[..., 3] > 120) & (a[..., :3].min(axis=2) > 150)
    ys, xs = np.where(f)
    return xs.min(), ys.min(), xs.max(), ys.max()


def word_part(part, text, scale=1.0, outline=OUTLINE, face=WHITE, ink=BLUE):
    """The word drawn on a canvas 4x the mockup's cut-out, its face where the cut-out's is.

    The mockup did not draw its words to one width -- the m of Main Game is 25 wide and
    the m of Time Attack 22 -- so a word set in the one font can run a little wider than
    its cut-out. It is condensed just enough to fit, which is a few percent at most and
    does not show; the labels, which the mockup drew in a narrower cut, condense more.
    """
    orig = Image.open(os.path.join(PARTS, part + ".png")).convert("RGBA")
    a = np.array(orig)
    if outline > 0:
        l, t, r, _b = face_box(orig)
    else:
        ys, xs = np.where(a[..., 3] > 100)
        l, t, r = xs.min(), ys.min(), xs.max()
    room = float(r - l + 1)
    xscale = min(1.0, room / text_width(text, scale))
    placed = layout(text, scale, xscale)
    top_of_face = min(top for _c, _x, top in placed)
    at = (float(l), float(t) - top_of_face)
    return render_text(text, scale, outline, face, ink, canvas=orig.size, at=at, xscale=xscale)



# ------------------------------------------------------------------ fitting to the mockup
# A glyph designed from a mask by eye is within a pixel; the eye sees that pixel. The
# watermark looks 1:1 because split_menu.py tuned its letters until the render matched the
# mockup NUMERICALLY, and the same is done here, automatically: every number in a glyph's
# shape is nudged, and a nudge is kept if the 1x render of the shape matches the letter's
# coverage in the mockup better. Each letter is fitted where it stands in its own word, so
# the spacing is the mockup's too.

def coverage(a, face=True):
    """Per-pixel coverage, 0..1, of the face (bright inside the outline) or of the ink."""
    alpha = a[..., 3].astype(float) / 255.0
    if not face:
        return alpha
    lum = a[..., :3].min(axis=2).astype(float)
    return alpha * np.clip((lum - 40.0) / (250.0 - 40.0), 0.0, 1.0)


def render_1x(shape, size, grow=0.0):
    W, H = size[0] * SS, size[1] * SS
    m = shape.draw(Image.new("L", (W, H), 0), SS, grow)
    return np.asarray(m.resize(size, Image.BOX)).astype(float) / 255.0


def _params(shape):
    """Every tunable number in a shape, as (op index, path) so it can be set back."""
    out = []
    for i, (kind, arg, _hole) in enumerate(shape.ops):
        if kind == "rr":
            out += [(i, j) for j in range(5)]            # x0 y0 x1 y1 r
        elif kind == "el":
            out += [(i, j) for j in range(4)]
        else:
            out += [(i, (j, k)) for j in range(len(arg)) for k in range(2)]
    return out


def _get(shape, i, path):
    kind, arg, hole = shape.ops[i]
    if kind == "poly":
        return arg[path[0]][path[1]]
    return arg[path]


def _set(shape, i, path, value):
    kind, arg, hole = shape.ops[i]
    if kind == "poly":
        pt = list(arg[path[0]])
        pt[path[1]] = value
        arg[path[0]] = tuple(pt)
    else:
        arg = list(arg)
        arg[path] = value
        shape.ops[i] = (kind, tuple(arg), hole)


def fit(shape, target, size, grow=0.0, rounds=(1.0, 0.5, 0.25)):
    """Coordinate descent on the shape's numbers against `target` coverage (an array the
    size of `size`). Returns the mean error at the end."""
    def err():
        return np.abs(render_1x(shape, size, grow) - target).mean()
    best = err()
    for step in rounds:
        improved = True
        while improved:
            improved = False
            for i, path in _params(shape):
                v0 = _get(shape, i, path)
                for dv in (step, -step):
                    _set(shape, i, path, v0 + dv)
                    e = err()
                    if e < best - 1e-6:
                        best, v0, improved = e, v0 + dv, True
                    else:
                        _set(shape, i, path, v0)
    return best


def runs_of(cols):
    out, x = [], 0
    while x < len(cols):
        if cols[x]:
            s = x
            while x < len(cols) and cols[x]:
                x += 1
            out.append((s, x - 1))
        else:
            x += 1
    return out


def fitted_word(part, text, scale=1.0, outline=OUTLINE, face=WHITE, ink=BLUE):
    """The word rebuilt letter by letter where the mockup drew each letter, every letter's
    geometry fitted to the mockup's, on a canvas 4x the cut-out."""
    orig = Image.open(os.path.join(PARTS, part + ".png")).convert("RGBA")
    a = np.array(orig)
    outlined = outline > 0
    cov = coverage(a, face=outlined)
    hard = cov > 0.5
    letters = [ch for ch in text if ch != " "]
    runs = runs_of(hard.any(axis=0))
    if len(runs) != len(letters):
        raise ValueError("%s: %d letter runs for %d letters" % (part, len(runs), len(letters)))

    W, H = orig.size
    shapes, errs = [], []
    for ch, (x0, x1) in zip(letters, runs):
        rows = np.where(hard[:, x0:x1 + 1].any(axis=1))[0]
        top = rows[0]
        w, gtop, base = GLYPHS[ch]
        # the glyph, scaled, put where the mockup's letter is; then its width matched to the
        # letter's, since the mockup's widths vary from word to word
        xs = (x1 - x0 + 1) / float(w * scale)
        shape = base.moved(float(x0), float(top), scale, xs)
        # fit against this letter's neighbourhood only
        m = 3
        bx0, by0 = max(0, x0 - m), max(0, top - m)
        bx1, by1 = min(W, x1 + 1 + m), min(H, rows[-1] + 1 + m)
        local = shape.moved(-bx0, -by0)
        e = fit(local, cov[by0:by1, bx0:bx1], (bx1 - bx0, by1 - by0))
        shapes.append(local.moved(bx0, by0))
        errs.append(e)

    # everything together, with the outline width fitted to the ink as a last step
    whole = Shape()
    for sh in shapes:
        whole.ops += sh.ops
    grow = outline
    if outlined:
        ink_cov = coverage(a, face=False)
        best = None
        for g in (outline - 1.0, outline - 0.5, outline - 0.25, outline, outline + 0.25, outline + 0.5):
            if g <= 0:
                continue
            e = np.abs(render_1x(whole, (W, H), g) - ink_cov).mean()
            if best is None or e < best[0]:
                best = (e, g)
        grow = best[1]

    out = Image.new("RGBA", (W * SS, H * SS), (0, 0, 0, 0))
    layers = [(ink, grow)] if outlined else []
    layers.append((face, 0.0))
    for colour, g in layers:
        mask = whole.draw(Image.new("L", (W * SS, H * SS), 0), SS, g)
        out.paste(Image.new("RGBA", (W * SS, H * SS), colour + (255,)), (0, 0), mask)
    print("  %-18s letters fitted, mean face error per letter %.3f  outline %.2f"
          % (part, sum(errs) / len(errs), grow))
    return out


def build_all():
    made = {}
    made["item_main_game"] = fitted_word("item_main_game", "Main Game")
    made["item_marathon"] = fitted_word("item_marathon", "Marathon")
    made["item_records"] = fitted_word("item_records", "Records")
    made["item_options"] = fitted_word("item_options", "Options")
    made["item_time_attack"] = fitted_word("item_time_attack", "Time Attack")
    made["title_text"] = fitted_word("title_text", "SONIC PIPE DREAM", scale=16.0 / CAP, outline=2.3)
    # The labels are 12 px tall and their letters touch, so they cannot be fitted letter by
    # letter; set plainly and condensed to fit, which at that size is all the eye can tell.
    made["label_select"] = word_part("label_select", "Select", scale=10.0 / CAP, outline=0.0, face=BLUE)
    made["label_back"] = word_part("label_back", "Back", scale=10.0 / CAP, outline=0.0, face=BLUE)
    made["cursor_arrow"] = cursor()
    made["preview_frame"] = frame()
    made["title_banner"] = banner()
    made["select_bar"] = bar()
    made["button_a"] = button("A", (26, 27), (12.7, 13.2), 12.0, (36, 79, 24), (61, 139, 63),
                              (211, 219, 212), 10.0 / CAP, (9.0, 8.0))
    made["button_b"] = button("B", (25, 27), (12.2, 13.2), 12.0, (114, 19, 13), (217, 53, 57),
                              (229, 200, 202), 13.0 / CAP, (5.5, 5.0))
    made["emerald"] = gem()
    return made


def main():
    made = build_all()
    rows = []
    for part, big in made.items():
        four = big.resize((big.width // 2, big.height // 2), Image.BOX)
        four.save(os.path.join(PARTS, part + "_4x.png"))
        one = big.resize((big.width // SS, big.height // SS), Image.BOX)
        orig = Image.open(os.path.join(PARTS, part + ".png")).convert("RGBA")
        err = ""
        if orig.size == one.size:
            a, b = np.array(orig)[..., 3].astype(float) / 255, np.array(one)[..., 3].astype(float) / 255
            err = "  mean alpha error %.3f" % np.abs(a - b).mean()
        print("%-18s %s -> 4x %s%s" % (part, orig.size, four.size, err))
        rows.append((part, orig, one))

    # the check: the mockup's piece over the redraw, both at 4x nearest, on the menu yellow
    Z = 4
    W = max(o.width for _p, o, _r in rows) * Z + 20
    H = sum((o.height * Z * 2 + 30) for _p, o, _r in rows) + 10
    sheet = Image.new("RGBA", (W, H), (246, 211, 43, 255))
    d = ImageDraw.Draw(sheet)
    y = 6
    for part, orig, one in rows:
        d.text((10, y), part + "   top: mockup    bottom: geometry", fill=(0, 0, 0, 255))
        for im in (orig, one):
            y += 12 if im is orig else 0
            big = im.resize((im.width * Z, im.height * Z), Image.NEAREST)
            sheet.alpha_composite(big, (10, y))
            y += big.height + 4
        y += 12
    sheet.save(os.path.join(PARTS, "_geometry_check.png"))
    print("wrote _geometry_check.png")


if __name__ == "__main__":
    main()
