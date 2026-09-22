"""Turn the menu art in external/ui/menu/parts/ into the textures and layout the menu uses.

    python native/gen_menu_assets.py        (needs Pillow)

        -> proj/Assets/Textures/UI/T_Menu_*.oct
           proj/Scripts/MenuLayout.lua      where every piece goes, and how big its texture is

The mockup (external/ui/menu/imaged.png) was cut into pieces by external/ui/menu/split_menu.py,
which also wrote parts/layout.json: each piece's place on the mockup's own 522 x 386 screen.
This reads that, so the menu on screen is the picture that was drawn, at any window size.

Two things are worth knowing about the textures:

  * They are PADDED TO POWERS OF TWO, art at the top left. The engine (and a console's GPU
    especially) wants power-of-two textures, and the art is whatever size it was cut at. The
    padding is transparent, and MenuLayout.lua carries both sizes: Lua draws the whole texture
    into a rectangle scaled by canvas/art, which lands the art exactly where layout.json says
    and leaves the padding off the edge of it.

  * The four menu items each get a GREYED copy as well, T_Menu_Item<n>_Off. Marathon is
    locked until the seventh emerald, and Records and Options are not written yet; a menu that
    lets you walk onto them and does nothing would be worse than one that shows them as shut.

MARATHON replaces the mockup's TIME ATTACK. Its lettering is cut from the other items by
native/gen_menu_marathon.py, which writes parts/item_marathon.png; run that first (this
script does it for you if the file is missing).
"""

import json
import os
import subprocess
import sys

from PIL import Image

from gen_s2sky_assets import write_texture

HERE = os.path.dirname(os.path.abspath(__file__))
PARTS = os.path.abspath(os.path.join(HERE, "..", "external", "ui", "menu", "parts"))
TEX = os.path.abspath(os.path.join(HERE, "..", "proj", "Assets", "Textures", "UI"))
LUA = os.path.abspath(os.path.join(HERE, "..", "proj", "Scripts", "MenuLayout.lua"))

UUID_MENU = 0x51C0FFEE00002200      # + index; clear of the UI's (…2000) and the font's (…2100)

# The menu's items, top to bottom: the art, and the y the mockup put that row at. Marathon
# takes Time Attack's place and its row.
ITEMS = [
    ("main_game", "item_main_game"),
    ("marathon", "item_marathon"),
    ("records", "item_records"),
    ("options", "item_options"),
]

# Resolution comes from the art, not from here. Three ways of enlarging the 1:1 mockup
# pieces in this script were tried and every one looked worse than the GPU's own filtering:
# nearest-neighbour staircased the anti-aliased edges, and two attempts at redrawing the
# shapes larger came out ragged or blurred. What did work was the artist's own 2x drawing of
# the watermark. So: any part may have a bigger drawing beside it, "<part>_2x.png" or
# "<part>_4x.png", and if it does, that is what gets cooked; MenuLayout.lua carries the art's
# real size, so the screen layout does not change. To sharpen a piece, draw it bigger.
BIGGER = ("_4x", "_2x")

# Everything else, as (texture name, part file). Order fixes the UUIDs, so only ever append.
PIECES = [
    ("T_Menu_Panel", "bg_scanlines_full"),
    ("T_Menu_Circles", "bg_circles"),
    ("T_Menu_TitleBanner", "title_banner"),
    ("T_Menu_TitleText", "title_text"),
    ("T_Menu_Watermark", "watermark_text"),
    ("T_Menu_SelectBar", "select_bar"),
    ("T_Menu_Cursor", "cursor_arrow"),
    ("T_Menu_PreviewFrame", "preview_frame"),
    ("T_Menu_Preview", "preview_picture"),
    ("T_Menu_Emerald", "emerald"),
    ("T_Menu_LabelStage", "label_special_stage"),
    ("T_Menu_ButtonA", "button_a"),
    ("T_Menu_ButtonB", "button_b"),
    ("T_Menu_LabelSelect", "label_select"),
    ("T_Menu_LabelBack", "label_back"),
]


# The chaos emeralds, stage by stage, as native/export_emeralds.py assigns them. The menu's
# own emerald art is green; these are that shape in each stage's colour, and a dark one for
# a stage whose emerald is still out there.
EMERALD_HUE = {
    1: (0.60, 1.00), 2: (0.14, 1.00), 3: (0.78, 0.95), 4: (0.33, 1.00),
    5: (0.00, 1.00), 6: (0.52, 0.85), 7: (0.00, 0.00),
}


def pot(n):
    p = 1
    while p < n:
        p *= 2
    return p


def load(part):
    """The part's art -- the biggest drawing of it there is (see BIGGER)."""
    for suffix in BIGGER + ("",):
        path = os.path.join(PARTS, part + suffix + ".png")
        if os.path.exists(path):
            return Image.open(path).convert("RGBA")
    raise IOError("no art for %s" % part)


def greyed(img):
    """A locked item: the colour taken out and the whole thing dimmed, alpha untouched.

    Not simply darkened -- the art is a white face inside a strong blue outline, and dimming
    alone kept the blue, which still read as live. Grey reads as shut.
    """
    out = img.copy()
    px = out.load()
    for y in range(out.height):
        for x in range(out.width):
            r, g, b, a = px[x, y]
            if a == 0:
                continue
            lum = int(0.299 * r + 0.587 * g + 0.114 * b)
            lum = int(46 + lum * 0.55)          # lift the blacks so the outline does not crush
            px[x, y] = (lum, lum, lum, a)
    return out


def recolour(img, hue, sat):
    """The same gem in another colour: hue and saturation set, brightness left alone, so the
    facets and the highlight survive."""
    import colorsys
    out = img.copy()
    px = out.load()
    for y in range(out.height):
        for x in range(out.width):
            r, g, b, a = px[x, y]
            if a == 0:
                continue
            _h, _s, v = colorsys.rgb_to_hsv(r / 255.0, g / 255.0, b / 255.0)
            nr, ng, nb = colorsys.hsv_to_rgb(hue, sat, v)
            px[x, y] = (int(nr * 255), int(ng * 255), int(nb * 255), a)
    return out


def silhouette(img):
    """The gem as a shadow of itself: its shape, filled with the art's own outline blue.
    A stage whose emerald has not been won shows this."""
    out = img.copy()
    px = out.load()
    for y in range(out.height):
        for x in range(out.width):
            a = px[x, y][3]
            if a:
                px[x, y] = (12, 28, 92, a)
    return out


def save(name, img, index):
    """Write one texture, padded to a power of two with the art at the top left.

    The art goes in at the size it was drawn. Scaling it up first was tried, the way
    gen_ui_assets.py does for the HUD -- but the HUD's art is pixel art, with hard edges
    worth keeping, and this art is not: the mockup was drawn anti-aliased, and blowing that
    up with nearest-neighbour turned every smooth edge into a staircase four pixels to a
    step. Jagged is worse than soft.
    """
    canvas = Image.new("RGBA", (pot(img.width), pot(img.height)), (0, 0, 0, 0))
    canvas.alpha_composite(img, (0, 0))
    write_texture(os.path.join(TEX, name + ".oct"), name, UUID_MENU + index,
                  canvas.width, canvas.height, canvas.tobytes(), wrap=0, force_hq=True, quiet=True)
    return canvas.size, img.size


def lua_table(rows, ref_w, ref_h, panel_top):
    out = ["-- Written by native/gen_menu_assets.py. Do not edit: run that instead.",
           "-- Where every piece of the menu goes, on the mockup's own %d x %d screen." % (ref_w, ref_h),
           "--",
           "--     x, y, w, h   where the piece belongs on that screen",
           "--     aw, ah       the art's own size in its texture (the panel is one 8 px column,",
           "--                  stretched across the window, so this is not always w and h)",
           "--     cw, ch       the texture, padded up to a power of two with the art top left",
           "--",
           "-- A piece is drawn by putting the WHOLE texture in a rectangle of",
           "--     (w * k * cw / aw)  x  (h * k * ch / ah)",
           "-- at (x * k, y * k): the art then lands on (x, y, w, h) and the padding falls",
           "-- outside it.",
           "MenuLayout = {",
           "    screen = { w = %d, h = %d }," % (ref_w, ref_h),
           "    panel_top = %d," % panel_top,
           "    parts = {"]
    for name, x, y, w, h, aw, ah, cw, ch in rows:
        out.append("        %s = { x = %d, y = %d, w = %d, h = %d, aw = %d, ah = %d, cw = %d, ch = %d },"
                   % (name, x, y, w, h, aw, ah, cw, ch))
    out.append("    },")
    out.append("    items = { %s }," % ", ".join('"%s"' % n for n, _ in ITEMS))
    out.append("}")
    return "\n".join(out) + "\n"


def main():
    if not os.path.exists(os.path.join(PARTS, "item_marathon.png")):
        subprocess.check_call([sys.executable, os.path.join(HERE, "gen_menu_marathon.py")])

    os.makedirs(TEX, exist_ok=True)
    layout = json.load(open(os.path.join(PARTS, "layout.json")))
    ref_w, ref_h = layout["reference_size"]
    where = {p["name"]: p for p in layout["parts"]}

    rows, index = [], 0
    for name, part in PIECES:
        img = load(part)
        p = where.get(part)
        if part == "bg_scanlines_full":
            # One column of the panel's colours, stretched across the window: the panel is
            # horizontal scanlines, so every row is one colour and nothing is lost widthways.
            x, y, w, h = 0, layout["panel_top"], ref_w, ref_h - layout["panel_top"]
            img = img.crop((0, layout["panel_top"], img.width, img.height))
        else:
            x, y, w, h = p["x"], p["y"], p["w"], p["h"]
        (cw, ch), (aw, ah) = save(name, img, index)
        rows.append((name, x, y, w, h, aw, ah, cw, ch))
        index += 1

    # the items, and a greyed copy of each
    for i, (key, part) in enumerate(ITEMS):
        img = load(part)
        drawn = img
        # Marathon was cut to its own width; it keeps the row Time Attack sat on, and its left
        # edge, so the column of items stays a column.
        p = where.get(part) or where["item_time_attack"]
        x, y = p["x"], p["y"]
        # the row's size on the mockup is the 1:1 drawing's, whatever size the cooked art is
        base = Image.open(os.path.join(PARTS, part + ".png"))
        w, h = base.width, base.height
        (cw, ch), (aw, ah) = save("T_Menu_Item%d" % (i + 1), drawn, index)
        rows.append(("T_Menu_Item%d" % (i + 1), x, y, w, h, aw, ah, cw, ch))
        index += 1
        save("T_Menu_Item%d_Off" % (i + 1), greyed(drawn), index)
        index += 1

    # The stage-select screen: one photograph of each stage (native/make_stage_previews.py)
    # and its emerald, in its own colour, nearly transparent until it has been won. Both sit
    # exactly where the menu's own preview and emerald did.
    prev, emer = where["preview_picture"], where["emerald"]
    gem = load("emerald")
    for stage in range(1, 8):
        shot = "preview_stage%d" % stage
        if os.path.exists(os.path.join(PARTS, shot + ".png")):
            img = load(shot)
            # a photograph: no edges to keep, so it is left at its own size
            (cw, ch), (aw, ah) = save("T_Menu_Preview%d" % stage, img, index)
            rows.append(("T_Menu_Preview%d" % stage, prev["x"], prev["y"], prev["w"], prev["h"],
                         aw, ah, cw, ch))
            index += 1
        hue, sat = EMERALD_HUE[stage]
        img = recolour(gem, hue, sat)
        (cw, ch), (aw, ah) = save("T_Menu_Emerald%d" % stage, img, index)
        rows.append(("T_Menu_Emerald%d" % stage, emer["x"], emer["y"], emer["w"], emer["h"],
                     aw, ah, cw, ch))
        index += 1
    (cw, ch), (aw, ah) = save("T_Menu_EmeraldOff", silhouette(gem), index)
    rows.append(("T_Menu_EmeraldOff", emer["x"], emer["y"], emer["w"], emer["h"],
                 aw, ah, cw, ch))
    index += 1

    open(LUA, "w", newline="\n").write(lua_table(rows, ref_w, ref_h, layout["panel_top"]))
    print("wrote %d textures to %s" % (index, TEX))
    print("wrote %s" % LUA)


if __name__ == "__main__":
    main()
