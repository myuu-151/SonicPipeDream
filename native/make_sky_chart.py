#!/usr/bin/env python
"""One labelled chart of every sky: its number in Sky.lua, its name, how it looks,
and the colours it is built from. Written to sky_previews/_chart.png.

    python native/make_sky_chart.py
"""

import os

from PIL import Image, ImageDraw, ImageFont

import gen_s2sky_assets as sky
import gen_sky_variants as variants
import preview_diamond_concepts as pat

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "..", "sky_previews", "_chart.png")

PANEL_W, PANEL_H = 420, 210          # one moment of the show
ROW_H = PANEL_H + 24
LABEL_W = 250
SWATCH_W = 190
MARGIN = 14


def font(size, bold=False):
    for name in (("arialbd.ttf" if bold else "arial.ttf"), "segoeui.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            pass
    return ImageFont.load_default()


def panel(star_img, frame):
    """The sky as the material shows it, at one moment of the diamond show."""
    view = star_img.resize((PANEL_W, PANEL_H), Image.LANCZOS)
    tile = pat.paint_rgba(pat.medley_frame(frame)).resize((PANEL_W // 2, PANEL_H // 4), Image.LANCZOS)
    for ty in range(4):
        for tx in range(2):
            view.paste(tile, (tx * PANEL_W // 2, ty * PANEL_H // 4), tile)
    return view


def main():
    field = sky.star_field()

    # The classic sky first, with the colours it has always had, then the variants.
    classic = ("Classic", sky.SKY_DEEP, sky.SKY_LIFT, pat.SHADOW, sky.MEDLEY_STOPS)
    rows = [(0, classic, sky.MEDLEY_LEVELS, sky.MEDLEY_DRIFT)] + [(n + 1, spec, variants.LEVELS, variants.DRIFT)
                                     for n, spec in enumerate(variants.SKIES)]

    width = LABEL_W + PANEL_W * 2 + SWATCH_W + MARGIN * 5
    sheet = Image.new("RGB", (width, ROW_H * len(rows) + 56), (24, 24, 28))
    draw = ImageDraw.Draw(sheet)
    draw.text((MARGIN, 14), "sky =", font=font(20), fill=(150, 150, 160))
    draw.text((LABEL_W + MARGIN * 2, 14), "covering the sky (ripple)", font=font(20), fill=(150, 150, 160))
    draw.text((LABEL_W + PANEL_W + MARGIN * 3, 14), "sparse (bloom)", font=font(20), fill=(150, 150, 160))
    draw.text((LABEL_W + PANEL_W * 2 + MARGIN * 4, 14), "diamonds  /  sky", font=font(20), fill=(150, 150, 160))

    for k, (number, spec, levels, drift) in enumerate(rows):
        name, horizon, poles, shadow, stops = spec
        sky.SKY_DEEP, sky.SKY_LIFT = horizon, poles
        pat.SHADOW, pat.LEVELS, pat.DRIFT = shadow, levels, drift
        if len(stops) == 2:
            pat.RAMP_STOPS, pat.RAMP_LO, pat.RAMP_HI = None, stops[0], stops[1]
        else:
            pat.RAMP_STOPS = stops

        w, h, px = sky.gen_stars_frame(field, 2)
        stars = Image.frombytes("RGBA", (w, h), bytes(px)).transpose(Image.FLIP_TOP_BOTTOM).convert("RGB")
        # The star tile is 180 degrees round; show the middle band of it, where the
        # horizon is, at the panel's 2:1 shape.
        stars = stars.crop((0, h // 4, w, h * 3 // 4))

        y = 48 + k * ROW_H
        draw.text((MARGIN, y + 46), str(number), font=font(72, bold=True), fill=(255, 255, 255))
        draw.text((MARGIN + 62, y + 70), name, font=font(34, bold=True), fill=(255, 255, 255))

        x = LABEL_W + MARGIN * 2
        sheet.paste(panel(stars, 6), (x, y))
        sheet.paste(panel(stars, 5 * 48 + 12), (x + PANEL_W + MARGIN, y))

        # Swatches: the diamond ramp, dim to lit, then the sky, horizon to pole.
        sx = x + PANEL_W * 2 + MARGIN * 2
        step = SWATCH_W // len(stops)
        for i, c in enumerate(stops):
            draw.rectangle((sx + i * step, y + 20, sx + (i + 1) * step - 3, y + 100), fill=tuple(c))
        draw.text((sx, y), "dim  ->  lit", font=font(15), fill=(150, 150, 160))
        for i in range(SWATCH_W):
            t = i / float(SWATCH_W - 1)
            c = tuple(int(round(horizon[j] + (poles[j] - horizon[j]) * t)) for j in range(3))
            draw.line((sx + i, y + 130, sx + i, y + 190), fill=c)
        draw.text((sx, y + 110), "horizon  ->  pole", font=font(15), fill=(150, 150, 160))

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    sheet.save(OUT)
    print("wrote", os.path.abspath(OUT))


if __name__ == "__main__":
    main()
