"""PRESS START, for the title screen, in the menus' typeface.

    python native/gen_title_text.py              (needs Pillow)
        -> external/ui/title/press_start.png
           proj/Assets/Intro/T_Title_PressStart.oct

Archivo Black (external/ui/ArchivoBlack-Regular.ttf, as gen_menu_type.py uses), a white face in
the menus' blue outline, drawn at 4x and halved so the outline's edge is smooth. The picture is
a power of two wide and high (the GameCube wants that); Intro.lua draws it at its own size,
centred, and leaves the empty margin off the screen's maths by the numbers below.
"""
import os
import struct

from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, ".."))
TTF = os.path.join(ROOT, "external", "ui", "ArchivoBlack-Regular.ttf")
PNG = os.path.join(ROOT, "external", "ui", "title", "press_start.png")
OCT = os.path.join(ROOT, "proj", "Assets", "Intro", "T_Title_PressStart.oct")

TEXT = "PRESS START"
W, H = 512, 64                  # the texture
CAP = 34                        # capital height in its pixels
OUTLINE = 5
WHITE = (254, 254, 254, 255)
BLUE = (3, 38, 174, 255)
SS = 4
UUID = 0x51C0FFEE00620010

MAGIC, VERSION, TYPE_TEXTURE = 0x4F435421, 13, 0xCDBBDA30


def main():
    font = ImageFont.truetype(TTF, 10 * SS)
    # size the font so a capital is CAP pixels tall
    cap = font.getbbox("H")[3] - font.getbbox("H")[1]
    font = ImageFont.truetype(TTF, int(round(10 * SS * CAP * SS / cap)))
    big = Image.new("RGBA", (W * SS, H * SS), (0, 0, 0, 0))
    d = ImageDraw.Draw(big)
    box = d.textbbox((0, 0), TEXT, font=font, stroke_width=OUTLINE * SS)
    x = (W * SS - (box[2] - box[0])) // 2 - box[0]
    y = (H * SS - (box[3] - box[1])) // 2 - box[1]
    d.text((x, y), TEXT, font=font, fill=WHITE, stroke_width=OUTLINE * SS, stroke_fill=BLUE)
    img = big.resize((W, H), Image.LANCZOS)
    os.makedirs(os.path.dirname(PNG), exist_ok=True)
    img.save(PNG)
    print("text %d x %d of the %d x %d picture" % ((box[2] - box[0]) // SS, (box[3] - box[1]) // SS, W, H))

    name = b"T_Title_PressStart"
    data = struct.pack("<IIIB", MAGIC, VERSION, TYPE_TEXTURE, 0) + struct.pack("<Q", UUID)
    data += struct.pack("<I", len(name)) + name
    data += struct.pack("<IIII", W, H, 1, 1)
    data += struct.pack("<III", 2, 1, 0)                 # RGBA8, linear, clamp
    data += struct.pack("<BBB", 0, 0, 1)                 # no mips, not a render target, sRGB
    data += struct.pack("<BB", 1, 1)                     # uncompressed on console; no step down
    data += img.tobytes()
    os.makedirs(os.path.dirname(OCT), exist_ok=True)
    open(OCT, "wb").write(data)


if __name__ == "__main__":
    main()
