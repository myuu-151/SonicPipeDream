"""Turn the UI art in external/ui/ into the textures the special stage's UI uses.

    python native/gen_ui_assets.py        (needs Pillow)

    external/ui/flag.png            -> T_UI_Flag          the chequered flag beside START
                                       T_UI_FlagLeft      and the same, mirrored
    external/ui/startnew2.png       -> T_UI_Start_1..5    START, one texture a letter
    external/ui/sonicringsnew.png   -> T_UI_SonicRings    the SONIC / RINGS label
    external/ui/total_remade.png    -> T_UI_Total         the TOTAL frame (gen_ui_total.py draws it)
    external/ui/emblem_bluenew2.png -> T_UI_Emblem        the winged disc of a passed check
    external/ui/thumbsupnew2.png    -> T_UI_Thumb         the glove that sits on it

The art is small pixel art (64, 128 or 256 across) and the window is not, so each picture is
scaled up to about 512 across with hard edges before it is written: the engine then filters a big
picture a little instead of a small one a lot, and the pixels stay pixels.

START is cut into its letters because the letters part company: on screen the word drops in
whole and then scatters, S and T to the left, R and T to the right, the A straight up. The
letters share their outlines, so each cut keeps the outline column either side of it.
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

# START's letters in startnew2.png: (first column, one past the last). Found by looking for
# the columns with no white in them, which are the outlines between letters. SpecialStageUI.lua
# has the same numbers, to put the letters back where they came from.
START_CUTS = [(0, 57), (54, 100), (97, 151), (148, 203), (199, 256)]
LETTER_CANVAS = (64, 128)           # each letter sits at the left of one of these


def save(img, index, name, scale=SCALE):
    os.makedirs(TEX, exist_ok=True)
    img = img.convert("RGBA")
    img = img.resize((img.width * scale, img.height * scale), Image.NEAREST)
    write_texture(os.path.join(TEX, name + ".oct"), name, UUID_UI + index, img.width, img.height,
                  img.tobytes(), wrap=CLAMP, force_hq=True)


def art(name):
    return Image.open(os.path.join(ART, name + ".png")).convert("RGBA")


if __name__ == "__main__":
    save(art("flag"), 0, "T_UI_Flag")
    save(art("emblem_bluenew2"), 1, "T_UI_Emblem", scale=2)
    save(art("thumbsupnew2"), 2, "T_UI_Thumb", scale=2)
    save(art("sonicringsnew"), 3, "T_UI_SonicRings", scale=2)      # 256 across already
    save(art("total_remade"), 4, "T_UI_Total", scale=2)       # drawn by gen_ui_total.py
    start = art("startnew2")
    for i, (x0, x1) in enumerate(START_CUTS):
        letter = Image.new("RGBA", LETTER_CANVAS, (0, 0, 0, 0))
        letter.paste(start.crop((x0, 0, x1, start.height)), (0, 0))
        save(letter, 5 + i, "T_UI_Start_%d" % (i + 1), scale=2)
    # the flag on the LEFT of the word is the same flag facing the other way. A picture of its
    # own, because mirroring a Quad through its UVs drew it as a thin line.
    save(art("flag").transpose(Image.FLIP_LEFT_RIGHT), 10, "T_UI_FlagLeft")
