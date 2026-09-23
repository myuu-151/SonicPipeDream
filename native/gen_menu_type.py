"""Set the menu's words in a real typeface, at four times the mockup's size.

    python native/gen_menu_type.py              (needs Pillow)
        -> external/ui/menu/parts/<part>_4x.png      the eight text pieces
           external/ui/menu/parts/_type_check.png    each word: the mockup's, then the type

The mockup's lettering was drawn, not typeset, and drawing it again as geometry -- see
gen_menu_geometry.py -- got within a few percent of it, which the eye could still tell.
This sets the words in a typeface instead -- Archivo Black (external/ui/ArchivoBlack-
Regular.ttf, SIL Open Font Licence, ArchivoBlack-OFL.txt beside it), chosen off a sheet of
thirty-four candidates (parts/_font_sampler*.png). It is not the mockup pixel for pixel; it
is a typeface, so it is crisp at any size and any word can be set in it later without
surgery. Russo One was the nearest match to the mockup's own lettering and was tried
first; this is the bolder choice.

Each word is drawn with Pillow's stroke -- the outline is exact -- at 8x, then halved to 4x,
on a canvas exactly 4x the mockup's cut-out, with its face where the cut-out's face is, so
the layout on screen does not move. The size is chosen so capitals stand as tall as the
mockup's; a face narrower than the mockup's lettering has its words
stretched sideways up to STRETCH to fill the room the cut-out had, a wider one condensed.
"""

import os

import numpy as np
from PIL import Image, ImageFont, ImageDraw

HERE = os.path.dirname(os.path.abspath(__file__))
PARTS = os.path.abspath(os.path.join(HERE, "..", "external", "ui", "menu", "parts"))
TTF = os.path.abspath(os.path.join(HERE, "..", "external", "ui", "ArchivoBlack-Regular.ttf"))

SS = 8                          # drawn at this many times the mockup, then halved to 4x
STRETCH = 1.12                  # the most a word is widened to fill its cut-out (a wider face is condensed instead)

WHITE = (254, 254, 254)
BLUE = (3, 38, 174)

# part, text, cap height in mockup px, outline width in mockup px, colour (None = white face)
WORDS = [
    ("item_main_game", "Main Game", 21.0, 3.0, None),
    ("item_marathon", "Marathon", 21.0, 3.0, None),
    ("item_records", "Records", 21.0, 3.0, None),
    ("item_options", "Options", 21.0, 3.0, None),
    ("item_extras", "Extras", 21.0, 3.0, None),
    ("item_chao_garden", "Chao Garden", 21.0, 3.0, None),
    ("item_save", "Save", 21.0, 3.0, None),
    ("item_load", "Load", 21.0, 3.0, None),                 # the PC's menu only
    ("item_time_attack", "Time Attack", 21.0, 3.0, None),
    ("title_text", "SONIC PIPE DREAM", 16.0, 2.3, None),
    ("label_select", "Select", 10.0, 0.0, BLUE),
    ("label_back", "Back", 10.0, 0.0, BLUE),
]

# Words the mockup never had, so there is no cut-out to fit them in. Each is set on the row of
# the item named here -- its height, its left edge, its top -- in a cut-out made as wide as the
# word itself, so it is never stretched or squeezed. The 1:1 copy is written as <part>.png too,
# which is what gen_menu_assets.py measures a row by.
NEW_WORDS = {
    "item_extras": "item_records",
    "item_chao_garden": "item_options",
    "item_save": "item_options",
    "item_load": "item_options",
}

_CAP_PER_SIZE = None


def cap_per_size():
    """How tall a capital is per point of font size, for this face."""
    global _CAP_PER_SIZE
    if _CAP_PER_SIZE is None:
        f = ImageFont.truetype(TTF, 200)
        _l, t, _r, b = f.getbbox("H")
        _CAP_PER_SIZE = (b - t) / 200.0
    return _CAP_PER_SIZE


def face_box(a, outlined):
    alpha = a[..., 3] > 120
    if outlined:
        m = alpha & (a[..., :3].min(axis=2) > 150)
    else:
        m = alpha
    ys, xs = np.where(m)
    return xs.min(), ys.min(), xs.max(), ys.max()


def render_word(text, cap, outline, colour):
    """The word by itself, at 8x, generously padded, and where its face is in that picture."""
    size = int(round(cap / cap_per_size() * SS))
    font = ImageFont.truetype(TTF, size)
    stroke = int(round(outline * SS))
    face = colour or WHITE
    bl, bt, br, bb = font.getbbox(text, stroke_width=0)
    pad = stroke + SS
    W, H = (br - bl) + 2 * pad, (bb - bt) + 2 * pad
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.text((pad - bl, pad - bt), text, font=font, fill=face + (255,),
           stroke_width=stroke, stroke_fill=BLUE + (255,))
    return img, face_box(np.array(img), outline > 0)


def cut_out(part, text, cap, outline, colour):
    """The mockup's cut-out for a word -- or, for a new word (NEW_WORDS), one made for it: the
    template item's row and margins, as wide as the word at its natural width."""
    if part not in NEW_WORDS:
        return Image.open(os.path.join(PARTS, part + ".png")).convert("RGBA")
    template = Image.open(os.path.join(PARTS, NEW_WORDS[part] + ".png")).convert("RGBA")
    l, t, r, b = face_box(np.array(template), outline > 0)
    _img, (fl, _ft, fr, _fb) = render_word(text, cap, outline, colour)
    face_w = int(np.ceil((fr - fl + 1) / float(SS)))
    width = l + face_w + (template.width - 1 - r)
    # only its face box matters to set_word: a white face where the template's was
    out = Image.new("RGBA", (width, template.height), (0, 0, 0, 0))
    out.paste((254, 254, 254, 255), (l, t, l + face_w, b + 1))
    return out


def set_word(part, text, cap, outline, colour):
    orig = cut_out(part, text, cap, outline, colour)
    l, t, r, b = face_box(np.array(orig), outline > 0)
    room = r - l + 1

    img, (fl, ft, fr, fb) = render_word(text, cap, outline, colour)
    face_w = (fr - fl + 1) / float(SS)
    stretch = min(STRETCH, room / face_w)
    if abs(stretch - 1.0) > 0.01:
        img = img.resize((int(round(img.width * stretch)), img.height), Image.LANCZOS)
        fl, ft, fr, fb = face_box(np.array(img), outline > 0)

    canvas = Image.new("RGBA", (orig.width * SS, orig.height * SS), (0, 0, 0, 0))
    canvas.alpha_composite(img, (int(round(l * SS - fl)), int(round(t * SS - ft))))
    return canvas, stretch


def main():
    rows = []
    for part, text, cap, outline, colour in WORDS:
        big, stretch = set_word(part, text, cap, outline, colour)
        four = big.resize((big.width // 2, big.height // 2), Image.BOX)
        four.save(os.path.join(PARTS, part + "_4x.png"))
        one = big.resize((big.width // SS, big.height // SS), Image.BOX)
        if part in NEW_WORDS:
            one.save(os.path.join(PARTS, part + ".png"))      # its 1:1 size, for gen_menu_assets.py
        orig = Image.open(os.path.join(PARTS, part + ".png")).convert("RGBA")
        print("%-18s %-18s stretch %.2f -> %s" % (part, text, stretch, four.size))
        rows.append((part, orig, one))

    Z = 4
    W = max(o.width for _p, o, _r in rows) * Z + 20
    H = sum(o.height * Z * 2 + 30 for _p, o, _r in rows) + 10
    sheet = Image.new("RGBA", (W, H), (246, 211, 43, 255))
    d = ImageDraw.Draw(sheet)
    y = 6
    for part, orig, one in rows:
        d.text((10, y), part + "   top: mockup    bottom: the typeface", fill=(0, 0, 0, 255))
        y += 12
        for im in (orig, one):
            big = im.resize((im.width * Z, im.height * Z), Image.NEAREST)
            sheet.alpha_composite(big, (10, y))
            y += big.height + 4
        y += 12
    sheet.save(os.path.join(PARTS, "_type_check.png"))
    print("wrote _type_check.png")


if __name__ == "__main__":
    main()
