"""Turn the UI art in external/ui/ into the textures the special stage's UI uses.

    python native/gen_ui_assets.py        (needs Pillow)

    external/ui/flag.png            -> T_UI_Flag          the chequered flag beside START
                                       T_UI_FlagLeft      and the same, mirrored
    external/ui/startnew2.png       -> T_UI_Start_1..5    START, one texture a letter
    external/ui/sonicringsnew.png   -> T_UI_SonicRings    the SONIC / RINGS label
    external/ui/total_remade.png    -> T_UI_Total         the TOTAL frame (gen_ui_total.py draws it)
    external/ui/emblem_bluenew2.png -> T_UI_Emblem        the winged disc of a passed check
    external/ui/thumbsupnew2.png    -> T_UI_Thumb         the glove that sits on it
                                       T_UI_ThumbDown     the same, thumb down: TOO BAD
                                       T_UI_EmblemRed     and the emblem it sits on then

The art is small pixel art (64, 128 or 256 across) and the window is not, so each picture is
scaled up to about 512 across with hard edges before it is written: the engine then filters a big
picture a little instead of a small one a lot, and the pixels stay pixels.

START is cut into its letters because the letters part company: on screen the word drops in
and then scatters. The letters TOUCH (they share their outlines), so they are separated
properly, each with a whole outline of its own: see split_letters().
"""

import os

from PIL import Image

from gen_s2sky_assets import write_texture

HERE = os.path.dirname(os.path.abspath(__file__))
ART = os.path.abspath(os.path.join(HERE, "..", "external", "ui"))
TEX = os.path.abspath(os.path.join(HERE, "..", "proj", "Assets", "Textures", "UI"))

UUID_UI = 0x51C0FFEE00002000        # + index; clear of the sky's
CLAMP = 0
SCALE = 4

LETTER_CANVAS = (64, 128)           # each letter sits at the top left of one of these


def split_letters(img, count):
    """Cut a word into its letters PROPERLY. The letters of START touch: they share their dark
    outlines. Slicing the picture in vertical strips (the first version) left every letter with
    a sliver of its neighbour stuck to it, which showed the moment they flew apart.

    So: find each letter's bright FACE (the faces do not touch); give every other pixel to the
    face it is nearest to, working outward through the art; then give each letter back the WHOLE
    of any outline it shares, so that on its own it is outlined all the way round. Together the
    letters overlap only in outline, dark on identical dark, and the word is exactly as drawn.
    Returns [(letter image, x, y)] left to right, x and y being where it sits in the word."""
    from collections import deque
    w, h = img.size
    px = img.load()
    opaque = [[px[x, y][3] > 40 for x in range(w)] for y in range(h)]
    bright = [[opaque[y][x] and sum(px[x, y][:3]) > 420 for x in range(w)] for y in range(h)]

    # 1. the faces: connected bright regions, the five biggest
    label = [[0] * w for _ in range(h)]
    sizes = {}
    nxt = 0
    for y0 in range(h):
        for x0 in range(w):
            if bright[y0][x0] and not label[y0][x0]:
                nxt += 1
                todo, n = deque([(x0, y0)]), 0
                label[y0][x0] = nxt
                while todo:
                    x, y = todo.popleft()
                    n += 1
                    for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                        u, v = x + dx, y + dy
                        if 0 <= u < w and 0 <= v < h and bright[v][u] and not label[v][u]:
                            label[v][u] = nxt
                            todo.append((u, v))
                sizes[nxt] = n
    keep = sorted(sorted(sizes, key=sizes.get, reverse=True)[:count],
                  key=lambda k: min(x for y in range(h) for x in range(w) if label[y][x] == k))
    order = {k: i + 1 for i, k in enumerate(keep)}
    owner = [[order.get(label[y][x], 0) for x in range(w)] for y in range(h)]

    # 2. everything else goes to the nearest face, spreading through the opaque art
    todo = deque((x, y) for y in range(h) for x in range(w) if owner[y][x])
    dist = [[0 if owner[y][x] else -1 for x in range(w)] for y in range(h)]
    while todo:
        x, y = todo.popleft()
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1), (1, 1), (1, -1), (-1, 1), (-1, -1)):
            u, v = x + dx, y + dy
            if 0 <= u < w and 0 <= v < h and opaque[v][u] and dist[v][u] < 0:
                dist[v][u] = dist[y][x] + 1
                owner[v][u] = owner[y][x]
                todo.append((u, v))
    # How thick the outline IS: the distance from a face to the art's outer edge, at its usual
    # value. (The furthest any pixel gets from a face is more than that -- corners, the drop shadow
    # -- and reaching that far into a neighbour brought back stray whiskers of ITS outline.)
    edge = sorted(dist[y][x] for y in range(1, h - 1) for x in range(1, w - 1)
                  if dist[y][x] > 0 and not (opaque[y - 1][x] and opaque[y + 1][x] and opaque[y][x - 1] and opaque[y][x + 1]))
    reach = edge[len(edge) // 2]

    out = []
    for k in range(1, count + 1):
        # 3. its own pixels, plus any DARK pixel of a neighbour within an outline's reach of its face
        near = [[False] * w for _ in range(h)]
        todo = deque((x, y, 0) for y in range(h) for x in range(w) if owner[y][x] == k and dist[y][x] == 0)
        seen = set((x, y) for x, y, _ in todo)
        while todo:
            x, y, d = todo.popleft()
            near[y][x] = True
            if d >= reach:
                continue
            for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                u, v = x + dx, y + dy
                if 0 <= u < w and 0 <= v < h and opaque[v][u] and (u, v) not in seen:
                    seen.add((u, v))
                    todo.append((u, v, d + 1))
        letter = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        lp = letter.load()
        for y in range(h):
            for x in range(w):
                mine = owner[y][x] == k
                shared = near[y][x] and owner[y][x] != k and sum(px[x, y][:3]) < 200
                if mine or shared:
                    lp[x, y] = px[x, y]
        box = letter.getbbox()
        out.append((letter.crop(box), box[0], box[1]))
    return out


# Another exporter (the GameCube repo's) runs main() with these changed: no scaling up, and not
# forced to stay uncompressed, so that machine's cook can store the art in 16 bits.
SCALE_ART = True
FORCE_HQ = True


def save(img, index, name, scale=SCALE):
    os.makedirs(TEX, exist_ok=True)
    img = img.convert("RGBA")
    if SCALE_ART:
        img = img.resize((img.width * scale, img.height * scale), Image.NEAREST)
    write_texture(os.path.join(TEX, name + ".oct"), name, UUID_UI + index, img.width, img.height,
                  img.tobytes(), wrap=CLAMP, force_hq=FORCE_HQ)


def hue_to(img, hue):
    """The same picture with every colour's HUE set to `hue` (0-1; 0 is red), its saturation and
    brightness left alone. Swapping red and blue was the first go at a red emblem: it kept the
    green that is in the blue art's highlights, and the result was orange."""
    import colorsys
    out = img.copy()
    px = out.load()
    for y in range(out.height):
        for x in range(out.width):
            r, g, b, a = px[x, y]
            if a == 0:
                continue
            _, s, v = colorsys.rgb_to_hsv(r / 255.0, g / 255.0, b / 255.0)
            r2, g2, b2 = colorsys.hsv_to_rgb(hue, s, v)
            px[x, y] = (int(r2 * 255), int(g2 * 255), int(b2 * 255), a)
    return out


def art(name):
    return Image.open(os.path.join(ART, name + ".png")).convert("RGBA")


def main():
    save(art("flag"), 0, "T_UI_Flag")
    save(art("emblem_bluenew2"), 1, "T_UI_Emblem", scale=2)
    save(art("thumbsupnew2"), 2, "T_UI_Thumb", scale=2)
    # TOO BAD: the same glove turned thumb down, on the same emblem gone red (its red and blue
    # swapped, which keeps every highlight and shadow of the art exactly where it was).
    save(art("thumbsupnew2").transpose(Image.FLIP_TOP_BOTTOM), 11, "T_UI_ThumbDown", scale=2)
    save(hue_to(art("emblem_bluenew2"), 0.985), 12, "T_UI_EmblemRed", scale=2)
    save(art("sonicringsnew"), 3, "T_UI_SonicRings", scale=2)      # 256 across already
    save(art("total_remade"), 4, "T_UI_Total", scale=2)       # drawn by gen_ui_total.py
    start = art("startnew2")
    cuts = []
    for i, (letter_img, x, y) in enumerate(split_letters(start, 5)):
        assert letter_img.width <= LETTER_CANVAS[0] and letter_img.height <= LETTER_CANVAS[1], letter_img.size
        letter = Image.new("RGBA", LETTER_CANVAS, (0, 0, 0, 0))
        letter.paste(letter_img, (0, 0))
        letter.save(os.path.join(ART, "_start_letter_%d.png" % (i + 1)))        # to look at
        save(letter, 5 + i, "T_UI_Start_%d" % (i + 1), scale=2)
        cuts.append((x, y, letter_img.width, letter_img.height))
    # SpecialStageUI.lua puts each letter back at (x, y): keep its START_LETTERS in step with this
    print("START letters (x, y, w, h):", cuts)
    # the flag on the LEFT of the word is the same flag facing the other way. A picture of its
    # own, because mirroring a Quad through its UVs drew it as a thin line.
    save(art("flag").transpose(Image.FLIP_LEFT_RIGHT), 10, "T_UI_FlagLeft")


if __name__ == "__main__":
    main()
