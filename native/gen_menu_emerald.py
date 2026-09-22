"""The stage-select emerald, from the big drawing in external/ui/menu/parts/emerald2.png.

    python native/gen_menu_emerald.py
        -> external/ui/menu/parts/emerald_4x.png     the gem, keyed off its black ground,
                                                     at four times the mockup's 30 x 24 slot

gen_menu_assets.py prefers the _4x drawing, recolours it for each stage as before, and
makes the silhouette that stands in for an emerald not yet won.

The drawing is the gem on solid black, with no alpha. Black is keyed out by brightness: the
gem's darkest facet is well clear of black, so a short ramp just above black gives a clean,
lightly anti-aliased edge. It is then trimmed to the gem's own extent and resampled to
the slot, keeping its proportions (the slot is 30 x 24 and the gem is drawn 5:4, which is
the same shape, so nothing is squashed).
"""

import os

import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
PARTS = os.path.abspath(os.path.join(HERE, "..", "external", "ui", "menu", "parts"))
SRC = os.path.join(PARTS, "emerald2.png")
OUT = os.path.join(PARTS, "emerald_4x.png")

SLOT = (30, 24)                 # the mockup's emerald, from layout.json
SCALE = 4


def main():
    a = np.array(Image.open(SRC).convert("RGB")).astype(float)
    bright = a.max(axis=2)
    alpha = np.clip((bright - 6.0) / 30.0, 0.0, 1.0)         # black -> 0, the gem -> 1
    ys, xs = np.where(alpha > 0.5)
    box = (xs.min(), ys.min(), xs.max() + 1, ys.max() + 1)
    rgba = np.dstack([a, alpha * 255.0]).astype(np.uint8)
    gem = Image.fromarray(rgba, "RGBA").crop(box)

    # fit inside the slot at 4x, centred, proportions kept
    W, H = SLOT[0] * SCALE, SLOT[1] * SCALE
    k = min(W / float(gem.width), H / float(gem.height))
    small = gem.resize((max(1, int(round(gem.width * k))), max(1, int(round(gem.height * k)))), Image.LANCZOS)
    out = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    out.alpha_composite(small, ((W - small.width) // 2, (H - small.height) // 2))
    out.save(OUT)
    print("emerald2 %s -> gem %s -> %s at %s" % (a.shape[1::-1], gem.size, os.path.basename(OUT), out.size))


if __name__ == "__main__":
    main()
