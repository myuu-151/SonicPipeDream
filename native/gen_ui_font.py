"""Make the UI's font, F_SonicUI, out of external/ui/NiseSegaSonic.TTF.

    python native/gen_ui_font.py   ->  proj/Assets/Textures/UI/F_SonicUI.oct
                                       external/ui/F_SonicUI_atlas.png      (to look at)

The engine's Text widget draws whatever is in the font's texture, times the text's colour.
So the look is BAKED into the glyphs here, as the rest of the UI art has it: a face running
from white down to a cool grey, a near-black outline, and a drop shadow down and to the right.
White text shows exactly that; yellow text keeps the outline and shadow and tints the face.

A font asset is a table of glyph rectangles (in pixels of its texture) and the texture itself,
embedded. Only ASCII 32-126 is drawn by the engine, one entry each, in order.
"""

import os
import struct

from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont

import gen_s2sky_assets as sky

HERE = os.path.dirname(os.path.abspath(__file__))
TTF = os.path.abspath(os.path.join(HERE, "..", "external", "ui", "NiseSegaSonic.TTF"))
OUT = os.path.abspath(os.path.join(HERE, "..", "proj", "Assets", "Textures", "UI", "F_SonicUI.oct"))
LOOK = os.path.abspath(os.path.join(HERE, "..", "external", "ui", "F_SonicUI_atlas.png"))

TYPE_FONT = 0x0022B1B4
UUID_FONT, UUID_FONT_TEX = 0x51C0FFEE00002100, 0x51C0FFEE00002101
SIZE = 56                           # the size the glyphs are drawn at; SetTextSize scales from it
ATLAS_W, ATLAS_H = 1024, 512
OUTLINE = 2                         # pixels of outline round a glyph
SHADOW = (3, 4)                     # the drop shadow: right, down
SHADOW_ALPHA = 150
PAD = OUTLINE + 2
FACE_TOP, FACE_BOTTOM = (255, 255, 255), (178, 196, 235)
INK = (8, 10, 22)
ONLY = None                         # a string: draw just these glyphs (a smaller atlas); None draws them all


def glyph(font, ch, ascent, descent):
    """(tile, origin x, origin y, advance): the tile is the styled glyph with room round it."""
    l, t, r, b = font.getbbox(ch, anchor="ls")
    advance = font.getlength(ch)
    if r <= l or b <= t:
        return None, 0.0, 0.0, advance
    w, h = (r - l) + 2 * PAD + SHADOW[0], (b - t) + 2 * PAD + SHADOW[1]
    mask = Image.new("L", (w, h), 0)
    ImageDraw.Draw(mask).text((PAD - l, PAD - t), ch, font=font, fill=255, anchor="ls")
    grown = mask.filter(ImageFilter.MaxFilter(2 * OUTLINE + 1))
    tile = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    shadow = ImageChops.offset(grown, SHADOW[0], SHADOW[1]).point(lambda a: a * SHADOW_ALPHA // 255)
    tile.paste(Image.new("RGBA", (w, h), (0, 0, 0, 255)), (0, 0), shadow)
    tile.paste(Image.new("RGBA", (w, h), INK + (255,)), (0, 0), grown)
    face = Image.new("RGBA", (w, h))
    fp = face.load()
    for y in range(h):
        # shade by height above the BASELINE, so every glyph in a line shades alike
        k = max(0.0, min(1.0, ((y - PAD + t) + ascent) / float(ascent + descent)))
        c = tuple(int(a + (b2 - a) * k) for a, b2 in zip(FACE_TOP, FACE_BOTTOM)) + (255,)
        for x in range(w):
            fp[x, y] = c
    tile.paste(face, (0, 0), mask)
    return tile, float(PAD - l), float(PAD - t), advance


def main():
    font = ImageFont.truetype(TTF, SIZE)
    ascent, descent = font.getmetrics()
    atlas = Image.new("RGBA", (ATLAS_W, ATLAS_H), (255, 255, 255, 0))
    chars, x, y, row_h = [], 1, 1, 0
    for code in range(32, 127):
        if ONLY is not None and chr(code) not in ONLY and chr(code) != " ":
            chars.append((code, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, font.getlength(chr(code))))
            continue
        tile, ox, oy, advance = glyph(font, chr(code), ascent, descent)
        if tile is None:
            chars.append((code, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, advance))
            continue
        if x + tile.width + 1 > ATLAS_W:
            x, y, row_h = 1, y + row_h + 1, 0
        assert y + tile.height < ATLAS_H, "atlas too small"
        atlas.paste(tile, (x, y))
        # a little more than the bare advance, for the outline either side
        chars.append((code, float(x), float(y), float(tile.width), float(tile.height), ox, oy, advance + OUTLINE))
        x, row_h = x + tile.width + 1, max(row_h, tile.height)
    atlas.save(LOOK)

    # the texture, exactly as write_texture writes one, embedded rather than on its own
    tex = sky.header(sky.TYPE_TEXTURE, UUID_FONT_TEX, "FontTexture")
    tex += sky.u32(ATLAS_W) + sky.u32(ATLAS_H) + sky.u32(1) + sky.u32(1)
    tex += sky.u32(2) + sky.u32(1) + sky.u32(0)                 # RGBA8, linear, clamp
    tex += sky.u8(0) + sky.u8(0) + sky.u8(1) + sky.u8(1) + sky.u8(1)
    tex += atlas.tobytes()

    d = sky.header(TYPE_FONT, UUID_FONT, "F_SonicUI")
    d += struct.pack("<iiif", SIZE, ATLAS_W, ATLAS_H, 0.0)
    d += sky.u8(0) + sky.u8(0) + sky.u8(1)                      # bold, italic, ttf (= texture embedded)
    d += sky.u8(1) + sky.u8(0) + sky.u8(0)                      # linear, clamp, no mips
    d += struct.pack("<i", len(chars))
    for c in chars:
        d += struct.pack("<i7f", *c)
    d += sky.u8(1) + tex
    d += sky.u32(0)                                             # the editor looks for TTF bytes here; none
    open(OUT, "wb").write(d)
    print("wrote %s (%d glyphs, %d bytes)" % (os.path.basename(OUT), len(chars), len(d)))


if __name__ == "__main__":
    main()
