"""Gather the module previews onto one page: external/ring/RingModules_sheet.png.

    python native/make_ring_sheet.py        (after gen_ring_modules.py -- sheet)
"""

import os
import sys

from PIL import Image, ImageDraw

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import ring_modules as rm

SRC = os.path.join(HERE, "..", "external", "ring", "preview")
OUT = os.path.join(HERE, "..", "external", "ring", "RingModules_sheet.png")
COLS, W, H, LABEL = 7, 256, 192, 20

names = list(rm.MODULES)
rows = (len(names) + COLS - 1) // COLS
sheet = Image.new("RGB", (COLS * W, rows * (H + LABEL)), (16, 18, 28))
draw = ImageDraw.Draw(sheet)
for i, name in enumerate(names):
    x, y = (i % COLS) * W, (i // COLS) * (H + LABEL)
    sheet.paste(Image.open(os.path.join(SRC, name + ".png")).convert("RGB").resize((W, H)), (x, y + LABEL))
    m = rm.MODULES[name]
    r, b = rm.count(m), rm.count(m, rm.BOMB)
    what = " + ".join(t for t in ("%d rings" % r if r else "", "%d bombs" % b if b else "") if t)
    draw.text((x + 6, y + 5), "%s  %s" % (name, what), fill=(255, 225, 120))
sheet.save(OUT)
print("saved", os.path.abspath(OUT))
