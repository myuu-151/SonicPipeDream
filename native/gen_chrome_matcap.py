"""The wings' chrome: the owner's chrome ball (external/ui/envmap18.png) as the wings' sphere map, or,
without it, a sphere map of the title's own world, as a chrome ball would mirror it.

    python native/gen_chrome_matcap.py
        -> proj/Assets/Intro/T_IntroWings.oct          the matcap (M_IntroWings maps it, UV map 2)
           external/intro/export/IntroWingsMatcap.png  to look at

A matcap made of a chrome ball in Blender's studio (a soft grey gradient) put plain grey on the
wings: metal looks like metal because it mirrors something with hard edges in it. So this is the
ball worked out directly: for every point of the picture, the ball's normal there, the ray from
the camera bounced off it, and what that ray would meet in the title's world --
    above the horizon, the day sky: pale at the horizon, deepening upward (T_SkyGradient's ramp),
        a few soft cloud bands, and the sun, high on the left, a hot white spot;
    the horizon itself, a thin bright line, and right under it the sea, cyan at its edge and
        deep blue below (the water bed's colours), with a darker band near the bottom;
and the whole a little toward silver (chrome is not a perfect mirror), with the rim of the ball,
where the rays graze, brightening as metal does. The engine maps it by the way each point of the
wing faces the camera, so the horizon line runs across every feather and moves as the camera does.
"""
import math
import os
import struct

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, ".."))
OCT = os.path.join(ROOT, "proj", "Assets", "Intro", "T_IntroWings.oct")
PNG = os.path.join(ROOT, "external", "intro", "export", "IntroWingsMatcap.png")
# The owner's own chrome ball (made in Photoshop): used when it is there, in place of the one
# worked out below. Any size, on any plain background; the ball is found and cropped to.
SOURCE = os.path.join(ROOT, "external", "ui", "envmap18.png")
SOURCE_SIZE = 128

SIZE = 256
UUID = 0x51C0FFEE00600000                    # export_intro.py's: the wings' texture
MAGIC, VERSION, TYPE_TEXTURE = 0x4F435421, 13, 0xCDBBDA30

SKY_HORIZON = np.array([168, 204, 242]) / 255.0      # T_SkyGradient's bottom row
SKY_ZENITH = np.array([46, 96, 214]) / 255.0         # ...and a little deeper than its top
SEA_EDGE = np.array([95, 195, 245]) / 255.0          # the water bed at the horizon
SEA_DEEP = np.array([8, 70, 190]) / 255.0
SEA_DARK = np.array([4, 30, 95]) / 255.0
SUN_DIR = np.array([-0.45, 0.62, 0.64])              # up and to the left, toward the camera
SILVER = 0.82                                        # of the mirror; the rest a neutral silver
SILVER_GREY = np.array([0.80, 0.82, 0.86])
HORIZON_LINE = 0.035                                 # how thick the bright line is (in r.y)


def matcap(size=SIZE):
    c = (np.arange(size) + 0.5) / size * 2.0 - 1.0
    x, y = np.meshgrid(c, -c)                       # y up; the picture's top row first
    rr = x * x + y * y
    inside = rr <= 1.0
    z = np.sqrt(np.clip(1.0 - rr, 0.0, 1.0))
    n = np.stack([x, y, z], -1)                     # toward the camera is +z
    v = np.array([0.0, 0.0, -1.0])                  # the camera looks down -z
    r = v - 2.0 * (n @ v)[..., None] * n            # bounced
    ry = r[..., 1]

    up = np.clip(ry, 0.0, 1.0)[..., None]
    sky = SKY_HORIZON + (SKY_ZENITH - SKY_HORIZON) * (up ** 0.6)
    band = 0.5 + 0.5 * np.sin(ry * 38.0 + r[..., 0] * 3.0)        # soft cloud bands, low in the sky
    sky = sky + (np.clip(band, 0, 1) ** 6 * np.exp(-ry * 6.0) * 0.35)[..., None]
    down = np.clip(-ry, 0.0, 1.0)[..., None]
    sea = SEA_EDGE + (SEA_DEEP - SEA_EDGE) * np.clip(down * 3.0, 0, 1)
    sea = sea + (SEA_DARK - sea) * np.clip((down - 0.45) * 2.0, 0, 1)
    col = np.where((ry >= 0.0)[..., None], sky, sea)
    line = np.exp(-(ry / HORIZON_LINE) ** 2)[..., None]               # the horizon, bright
    col = col + (1.0 - col) * line * 0.85
    sun = np.clip(r @ (SUN_DIR / np.linalg.norm(SUN_DIR)), 0.0, 1.0)
    col = col + (sun ** 60 * 2.0 + sun ** 8 * 0.25)[..., None]        # the sun, and its glow

    col = SILVER * col + (1.0 - SILVER) * SILVER_GREY
    fres = (1.0 - z) ** 3                                              # grazing: brighter
    col = col + (1.0 - col) * fres[..., None] * 0.35
    col = np.clip(col, 0.0, 1.0)

    # outside the ball, its edge colour carried out (a matcap is never read there, but filtering is)
    edge = np.clip(np.sqrt(rr), 1e-6, None)
    ex, ey = x / edge * 0.995, y / edge * 0.995
    ix = np.clip(((ex + 1.0) * 0.5 * size).astype(int), 0, size - 1)
    iy = np.clip(((1.0 - (ey + 1.0) * 0.5) * size).astype(int), 0, size - 1)
    col = np.where(inside[..., None], col, col[iy, ix])
    return col


def from_picture(path, size):
    """The ball in a picture: cropped to it (whatever is not the background), scaled, and its edge
    colour carried out past the circle so no background shows where a matcap's edge is filtered."""
    from PIL import Image
    im = Image.open(path).convert("RGB")
    a = np.asarray(im).astype(np.float32) / 255.0
    bg = a[0, 0]
    ball = np.abs(a - bg).max(-1) > 0.06
    ys, xs = np.nonzero(ball)
    cx, cy = (xs.min() + xs.max() + 1) * 0.5, (ys.min() + ys.max() + 1) * 0.5
    half = max(xs.max() + 1 - xs.min(), ys.max() + 1 - ys.min()) * 0.5
    box = (int(round(cx - half)), int(round(cy - half)), int(round(cx + half)), int(round(cy + half)))
    col = np.asarray(im.crop(box).resize((size, size), Image.LANCZOS)).astype(np.float32) / 255.0
    c = (np.arange(size) + 0.5) / size * 2.0 - 1.0
    x, y = np.meshgrid(c, -c)
    rr = np.sqrt(x * x + y * y)
    edge = np.clip(rr, 1e-6, None)
    inner = 0.93                        # the outermost ring of the picture is the ball's antialiased edge
    ex, ey = x / edge * inner, y / edge * inner
    ix = np.clip(((ex + 1.0) * 0.5 * size).astype(int), 0, size - 1)
    iy = np.clip(((1.0 - (ey + 1.0) * 0.5) * size).astype(int), 0, size - 1)
    return np.where((rr <= inner)[..., None], col, col[iy, ix])


def main():
    if os.path.exists(SOURCE):
        col = from_picture(SOURCE, SOURCE_SIZE)
        print("from %s" % SOURCE)
    else:
        col = matcap()
    rgba = np.concatenate([col, np.ones(col.shape[:2] + (1,))], -1)
    px = (rgba * 255.0 + 0.5).astype(np.uint8)
    try:
        from PIL import Image
        os.makedirs(os.path.dirname(PNG), exist_ok=True)
        Image.fromarray(px, "RGBA").save(PNG)
    except ImportError:
        pass
    name = b"T_IntroWings"
    d = struct.pack("<IIIB", MAGIC, VERSION, TYPE_TEXTURE, 0) + struct.pack("<Q", UUID)
    d += struct.pack("<I", len(name)) + name
    size = col.shape[0]
    d += struct.pack("<IIII", size, size, 1, 1) + struct.pack("<III", 2, 1, 0)   # RGBA8, linear, clamp
    d += struct.pack("<BBB", 0, 0, 1) + struct.pack("<BB", 1, 1)               # uncompressed on console
    d += px.tobytes()
    open(OCT, "wb").write(d)
    print("T_IntroWings: %d x %d chrome matcap" % (size, size))


if __name__ == "__main__":
    main()
