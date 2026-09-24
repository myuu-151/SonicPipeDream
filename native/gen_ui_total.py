"""Draw the TOTAL frame in the style of the SONIC / RINGS art: glossy letters with a bright
top edge, a gradient down the face, a darker lip at the bottom and a soft near-black outline.
The word is RINGS' gold and the frame SONIC's blue, so the box belongs with the label.

    python native/gen_ui_total.py   ->  external/ui/total_remade.png   (256 x 256)
                                        external/ui/time_remade.png    the same frame, TIME (a time attack)

The art is the top BOX_H rows of a square texture. It is drawn at SS times the size and
scaled down, which is where the smooth edges and the frame's round corners come from.
gen_ui_assets.py turns it into T_UI_Total. The number goes inside the frame, as Text.
"""

import os

from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.abspath(os.path.join(HERE, "..", "external", "ui", "total_remade.png"))
OUT_TIME = os.path.abspath(os.path.join(HERE, "..", "external", "ui", "time_remade.png"))

W = H = 256
BOX_H = 160                         # rows of the texture the art fills; SpecialStageUI.lua knows this too
SS = 4
FONT = os.path.abspath(os.path.join(HERE, "..", "external", "ui", "NiseSegaSonic.TTF"))   # the UI's font
WORD_W = 150                        # the word is sized to be this wide

# top edge, top of the face, bottom of the face, the lip under it
GOLD = ((253, 253, 199), (253, 234, 9), (253, 175, 2), (185, 73, 1))
BLUE = ((172, 251, 253), (41, 202, 253), (0, 48, 240), (0, 12, 120))
OUTLINE = (8, 10, 14)
FRAME_T, FRAME_R = 11, 22           # the frame's thickness, and the radius of its corners
STROKE = 2                          # outline, in final pixels
EDGE = 3                            # the bright top edge and the dark lip, in final pixels


def shaded(mask, colours, y0, y1):
    """Fill a mask in the label's manner. y0..y1 is the span the gradient runs over."""
    edge, top, bottom, lip = colours
    w, h = mask.size
    face = Image.new("RGB", (w, h))
    fp = face.load()
    for y in range(h):
        t = max(0.0, min(1.0, (y - y0) / float(max(1, y1 - y0))))
        c = tuple(int(a + (b - a) * t * t) for a, b in zip(top, bottom))     # holds the light colour longer
        for x in range(w):
            fp[x, y] = c
    k = EDGE * SS
    hi = ImageChops.subtract(mask, ImageChops.offset(mask, 0, k))            # lit from above: the top edge
    lo = ImageChops.subtract(mask, ImageChops.offset(mask, 0, -k))           # and the lip underneath
    face.paste(Image.new("RGB", (w, h), edge), (0, 0), hi)
    face.paste(Image.new("RGB", (w, h), lip), (0, 0), lo)
    out = face.convert("RGBA")
    out.putalpha(mask)
    return out


def draw(text, out_path):
    """The frame with `text` in its top edge. The letters are sized by TOTAL (WORD_W wide), so
    every word drawn here has the same height; a shorter one leaves a shorter gap in the frame."""
    w, h = W * SS, H * SS
    size = 80 * SS
    while ImageFont.truetype(FONT, size).getlength("TOTAL") > WORD_W * SS:
        size -= SS
    font = ImageFont.truetype(FONT, size)
    word = Image.new("L", (w, h), 0)
    d = ImageDraw.Draw(word)
    box = d.textbbox((0, 0), text, font=font)
    th = d.textbbox((0, 0), "TOTAL", font=font)
    th = th[3] - th[1]
    tw = box[2] - box[0]
    tx, ty = (w - tw) // 2 - box[0], 8 * SS - d.textbbox((0, 0), "TOTAL", font=font)[1]
    d.text((tx, ty), text, font=font, fill=255)
    word_top, word_bottom = 8 * SS, 8 * SS + th

    frame = Image.new("L", (w, h), 0)
    d = ImageDraw.Draw(frame)
    fx0, fx1 = 8 * SS, w - 8 * SS
    fy0, fy1 = (word_top + word_bottom) // 2 - FRAME_T * SS // 2, (BOX_H - 8) * SS
    d.rounded_rectangle((fx0, fy0, fx1, fy1), FRAME_R * SS, fill=255)
    t = FRAME_T * SS
    d.rounded_rectangle((fx0 + t, fy0 + t, fx1 - t, fy1 - t), max(1, FRAME_R * SS - t), fill=0)
    gap = 10 * SS                                                           # open at the top, for the word
    d.rectangle((tx + box[0] - gap, 0, tx + box[2] + gap, fy0 + t + SS), fill=0)
    # round the ends of the top edge where it was cut
    for x in (tx + box[0] - gap, tx + box[2] + gap):
        d.ellipse((x - t // 2, fy0, x + t // 2, fy0 + t), fill=255)

    both = ImageChops.lighter(word, frame)
    grown = both.filter(ImageFilter.MaxFilter(STROKE * SS * 2 + 1))
    grown = ImageChops.lighter(grown, ImageChops.offset(grown, 0, 1 * SS))   # heavier underneath, as the label is
    out = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    out.paste(Image.new("RGBA", (w, h), OUTLINE + (255,)), (0, 0), grown)
    out.alpha_composite(shaded(frame, BLUE, fy0, fy1))
    out.alpha_composite(shaded(word, GOLD, word_top, word_bottom))
    out.resize((W, H), Image.LANCZOS).save(out_path)
    print("wrote", out_path)


def main():
    draw("TOTAL", OUT)
    draw("TIME", OUT_TIME)


if __name__ == "__main__":
    main()
