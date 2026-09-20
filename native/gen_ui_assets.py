"""Draw the PLACEHOLDER art for the special stage's UI and write it into the project.

    python native/gen_ui_assets.py        (needs Pillow)

    -> proj/Assets/Textures/UI/T_UI_Flag.oct      the chequered flag beside START
       proj/Assets/Textures/UI/T_UI_Emblem.oct    the thumbs-up emblem shown on a passed check
       external/ui/*.png                          the same pictures, to look at

Placeholders, meant to be replaced: everything is drawn from shapes here so the UI has
something to move about. The words themselves (SONIC, RINGS, TOTAL, START, COOL !) are Text
widgets in SpecialStageUI.lua, in the engine's own font, so they need no art at all yet.

The pictures are after the original's: a black and white chequered flag on a short pole,
waving (the cloth flat-shaded along its wave, the pole and its ball shaded round); and a
white-gloved thumbs up on a blue disc with wings. Swap a .oct for real art with the same
name and the script picks it up unchanged.
"""

import math
import os

from PIL import Image, ImageDraw

from gen_s2sky_assets import write_texture

HERE = os.path.dirname(os.path.abspath(__file__))
TEX = os.path.abspath(os.path.join(HERE, "..", "proj", "Assets", "Textures", "UI"))
LOOK = os.path.abspath(os.path.join(HERE, "..", "external", "ui"))

UUID_UI = 0x51C0FFEE00002000        # + index; clear of the sky's
CLAMP = 0


def pole_and_ball(w, h, ss=4):
    """The flagpole and the ball on top of it, SHADED so they read as round: the pole a metal
    cylinder (dark at the edges, a bright strip where the light catches it, a soft reflected
    edge on the far side), the ball a gold sphere with its own hotspot and a dark underside.
    Drawn at `ss` times the size, pixel by pixel, and scaled down, so the edges are smooth.
    The cloth is not touched: it was liked as it was."""
    W, H = w * ss, h * ss
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    px = layer.load()
    light = (-0.45, -0.55, 0.70)                          # from the upper left, toward the viewer
    ln = math.sqrt(sum(c * c for c in light))
    light = tuple(c / ln for c in light)

    def shade(nx, ny, nz, base, gloss, hot):
        diffuse = max(0.0, nx * light[0] + ny * light[1] + nz * light[2])
        # the half vector between the light and the eye, which looks straight down +z
        hx, hy, hz = light[0], light[1], light[2] + 1.0
        hl = math.sqrt(hx * hx + hy * hy + hz * hz)
        spec = max(0.0, (nx * hx + ny * hy + nz * hz) / hl) ** gloss
        rim = (1.0 - nz) ** 3 * 0.20                      # a little light coming round the far edge
        k = 0.30 + 0.78 * diffuse + rim
        return tuple(max(0, min(255, int(255 * min(1.0, c * k + hot * spec)))) for c in base)

    # the pole: a cylinder, so its normal only turns from side to side
    cx, half = 28.0 * ss, 7.0 * ss
    top, bottom = 16 * ss, (h - 5) * ss
    for y in range(top, bottom):
        for x in range(int(cx - half), int(cx + half) + 1):
            t = (x + 0.5 - cx) / half
            if abs(t) >= 1.0:
                continue
            nz = math.sqrt(1.0 - t * t)
            r, g, b = shade(t, 0.0, nz, (0.80, 0.82, 0.88), 40.0, 0.85)
            shadow = 0.62 if y < top + 9 * ss else 1.0    # the ball's shadow down the top of the pole
            px[x, y] = (int(r * shadow), int(g * shadow), int(b * shadow), 255)
    # a rounded foot, so it does not end in a sawn-off edge
    for y in range(bottom, bottom + 3 * ss):
        k = 1.0 - (y - bottom) / (3.0 * ss)
        for x in range(int(cx - half * k), int(cx + half * k) + 1):
            t = (x + 0.5 - cx) / half
            r, g, b = shade(t, 0.5, math.sqrt(max(0.0, 1.0 - t * t)) * 0.8, (0.62, 0.64, 0.70), 30.0, 0.4)
            px[x, y] = (r, g, b, 255)

    # the ball: a sphere
    bx, by, rad = 28.0 * ss, 13.0 * ss, 12.5 * ss
    for y in range(int(by - rad), int(by + rad) + 1):
        for x in range(int(bx - rad), int(bx + rad) + 1):
            dx, dy = (x + 0.5 - bx) / rad, (y + 0.5 - by) / rad
            d2 = dx * dx + dy * dy
            if d2 >= 1.0:
                continue
            r, g, b = shade(dx, dy, math.sqrt(1.0 - d2), (1.0, 0.76, 0.10), 34.0, 0.95)
            px[x, y] = (r, g, b, 255)
    return layer.resize((w, h), Image.LANCZOS)


def flag(w=256, h=192):
    """Chequered, waving: the squares ride a sine, and the cloth is shaded along it."""
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    px = img.load()
    cols, rows = 7, 5
    x0, x1, y0, y1 = 34, w - 8, 18, h - 46
    for x in range(x0, x1):
        u = (x - x0) / float(x1 - x0)
        lift = math.sin(u * math.pi * 1.6) * 14.0 * u
        shade = 0.78 + 0.22 * math.cos(u * math.pi * 1.6)
        for y in range(y0, y1):
            yy = y - lift
            if not (y0 <= yy < y1):
                continue
            v = (yy - y0) / float(y1 - y0)
            white = (int(u * cols) + int(v * rows)) % 2 == 0
            c = int((245 if white else 28) * shade)
            px[x, y] = (c, c, c, 255)
    img.alpha_composite(pole_and_ball(w, h))
    return img


def emblem(size=256):
    """A blue disc with wings, and a white glove giving the thumbs up, red cuff and all."""
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    c = size // 2
    blue, dark, light = (30, 80, 220, 255), (12, 30, 110, 255), (90, 150, 255, 255)
    for side in (-1, 1):                                  # wings: three feathers a side
        for i, (reach, drop) in enumerate(((118, -34), (112, 2), (96, 34))):
            tip = (c + side * reach, c + drop)
            d.polygon([(c + side * 38, c + drop - 22), tip, (c + side * 38, c + drop + 18)],
                      fill=blue if i % 2 == 0 else light, outline=dark)
    d.ellipse((c - 74, c - 74, c + 74, c + 74), fill=blue, outline=dark, width=5)
    d.ellipse((c - 60, c - 60, c + 60, c + 60), outline=light, width=3)
    white, line, red = (250, 250, 250, 255), (70, 70, 90, 255), (220, 40, 40, 255)
    d.rounded_rectangle((c + 22, c + 4, c + 52, c + 44), 8, fill=red, outline=(110, 10, 10, 255), width=3)   # cuff
    d.rounded_rectangle((c - 50, c - 6, c + 30, c + 50), 20, fill=white, outline=line, width=4)              # fist
    for k in range(3):                                                                                       # fingers
        y = c + 6 + k * 14
        d.line((c - 46, y + 8, c - 8, y + 8), fill=line, width=3)
    d.rounded_rectangle((c - 14, c - 62, c + 16, c + 10), 15, fill=white, outline=line, width=4)             # thumb
    d.rectangle((c - 10, c - 6, c + 12, c + 12), fill=white)
    return img


def save(img, index, name):
    os.makedirs(TEX, exist_ok=True)
    os.makedirs(LOOK, exist_ok=True)
    img.save(os.path.join(LOOK, name + ".png"))
    write_texture(os.path.join(TEX, name + ".oct"), name, UUID_UI + index, img.width, img.height,
                  img.tobytes(), wrap=CLAMP, force_hq=True)


if __name__ == "__main__":
    save(flag(), 0, "T_UI_Flag")
    save(emblem(), 1, "T_UI_Emblem")
