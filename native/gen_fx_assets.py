"""The little effects: the sparkle a collected ring leaves, and a bomb going off.

    python native/gen_fx_assets.py        (needs Pillow; no Blender)

    -> proj/Assets/Stage/FX/T_Sparkle.oct, M_Sparkle.oct         a four-pointed star, ADDITIVE
                            T_Explosion_0..2.oct, M_Explosion.oct   the bomb going off: external/ui/blowup.png
                            SM_FxQuad.oct, SM_FxQuadBoom.oct        the square they are drawn on

After the original's RING SPARKS and BOMB EXPLOSION sprites. The sparkle is drawn here from shapes;
the explosion is the supplied sprite sheet, cut into its frames. Both are flat squares that the game turns to face the camera every frame
(SpecialStage.lua), so there is no particle system to set up: a sparkle is a StaticMesh3D node.

The square has NO vertex colours and the material is unlit and textured, which is the one
combination that draws the same on every machine (a lit material on a vertex-coloured mesh comes
out unlit on the GameCube). One square a material, because a mesh names its material.
"""

import math
import os

from PIL import Image, ImageDraw, ImageFilter

from gen_s2sky_assets import (TYPE_MATERIALLITE, TYPE_STATICMESH, asset_ref, f32, header, i32, null_ref,
                              u8, u32, write_texture)

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.abspath(os.path.join(HERE, "..", "proj", "Assets", "Stage", "FX"))
LOOK = os.path.abspath(os.path.join(HERE, "..", "external", "fx"))

UUID = 0x51C0FFEE00006000
ADDITIVE, TRANSLUCENT = 3, 2
EXPLOSION_FRAMES = 3


def sparkle(size=64):
    """A four-pointed star with a hot middle, on BLACK: it is added to the picture, so black is
    nothing and the star only ever brightens what is behind it."""
    ss = 4
    n = size * ss
    img = Image.new("RGB", (n, n), (0, 0, 0))
    d = ImageDraw.Draw(img)
    c = n / 2.0
    for reach, thick, colour in ((0.48, 0.045, (255, 224, 96)), (0.30, 0.080, (255, 250, 200))):
        r, t = n * reach, n * thick
        d.polygon([(c, c - r), (c + t, c), (c, c + r), (c - t, c)], fill=colour)         # upright
        d.polygon([(c - r, c), (c, c - t), (c + r, c), (c, c + t)], fill=colour)         # and across
    d.ellipse((c - n * 0.09, c - n * 0.09, c + n * 0.09, c + n * 0.09), fill=(255, 255, 255))
    glow = img.filter(ImageFilter.GaussianBlur(n * 0.03))
    img = Image.blend(img, glow, 0.35).resize((size, size), Image.LANCZOS)
    return img.convert("RGBA")


SHEET = os.path.abspath(os.path.join(HERE, "..", "external", "ui", "blowup.png"))
CELL = 32                           # the sheet is three 32 x 32 cells, a pixel of border round each
CELL_BACKGROUND = (0, 84, 84)       # the teal each cell is drawn on: it becomes clear
FX_SCALE = 4                        # pixel art, scaled up with hard edges so the engine's filtering
                                    # softens a big picture a little and not a small one a lot


def explosion(frame):
    """Frame `frame` of the supplied sheet (external/ui/blowup.png): the fireball, the fireball
    breaking up, the debris. (A drawn one came first and was too simple; this is the real art.)"""
    sheet = Image.open(SHEET).convert("RGBA")
    x = 1 + frame * (CELL + 1)
    cell = sheet.crop((x, 1, x + CELL, 1 + CELL))
    px = cell.load()
    for yy in range(CELL):
        for xx in range(CELL):
            if px[xx, yy][:3] == CELL_BACKGROUND:
                px[xx, yy] = (0, 0, 0, 0)
    return cell.resize((CELL * FX_SCALE, CELL * FX_SCALE), Image.NEAREST)


def material(name, uuid, texture_uuid, texture_name, blend):
    d = header(TYPE_MATERIALLITE, uuid, name)
    d += u32(0) + u32(0) + u32(blend) + u32(0)              # no params; UNLIT; blend; no vertex colour
    d += u32(1)
    d += asset_ref(texture_uuid, texture_name) + u8(0) + u8(1)
    for _ in range(3):
        d += null_ref() + u8(0) + u8(1)
    for _ in range(2):
        d += f32(0) + f32(0) + f32(1) + f32(1)
    d += f32(1) + f32(1) + f32(1) + f32(1)
    d += f32(1) + f32(1) + f32(1) + f32(1)
    d += f32(1.0) + f32(0.0) + f32(0.0) + f32(0.0)
    d += u32(2) + f32(1.0) + f32(0.5) + f32(8.0)
    d += i32(0)
    d += u8(0) + u8(0) + u8(0)                              # depth test on; no fresnel; no fog
    d += u8(0)                                              # no culling: it may be seen from behind
    open(os.path.join(OUT, name + ".oct"), "wb").write(d)


def quad(name, uuid, material_uuid, material_name):
    """One unit square facing the engine's +Z, which is toward a camera that looks down -Z."""
    corners = [(-0.5, -0.5, 0.0, 1.0), (0.5, -0.5, 1.0, 1.0), (0.5, 0.5, 1.0, 0.0), (-0.5, 0.5, 0.0, 0.0)]
    d = header(TYPE_STATICMESH, uuid, name)
    d += u32(4) + u32(6) + u32(1)
    d += asset_ref(material_uuid, material_name)
    d += u8(0) + u8(0)                                      # no collision; no vertex colour
    for x, y, u, v in corners:
        d += f32(x) + f32(y) + f32(0) + f32(u) + f32(v) + f32(0) + f32(0)
        d += f32(0) + f32(0) + f32(1)
    for i in (0, 1, 2, 0, 2, 3):
        d += u32(i)
    d += u8(0) + u32(0)
    d += f32(0) + f32(0) + f32(0) + f32(0.75)
    open(os.path.join(OUT, name + ".oct"), "wb").write(d)


def main():
    os.makedirs(OUT, exist_ok=True)
    os.makedirs(LOOK, exist_ok=True)
    img = sparkle()
    img.save(os.path.join(LOOK, "T_Sparkle.png"))
    write_texture(os.path.join(OUT, "T_Sparkle.oct"), "T_Sparkle", UUID + 1, img.width, img.height,
                  img.tobytes(), wrap=0, quiet=True)
    material("M_Sparkle", UUID + 2, UUID + 1, "T_Sparkle", ADDITIVE)
    quad("SM_FxQuad", UUID + 3, UUID + 2, "M_Sparkle")

    for f in range(EXPLOSION_FRAMES):
        img = explosion(f)
        img.save(os.path.join(LOOK, "T_Explosion_%d.png" % f))
        write_texture(os.path.join(OUT, "T_Explosion_%d.oct" % f), "T_Explosion_%d" % f, UUID + 16 + f,
                      img.width, img.height, img.tobytes(), wrap=0, quiet=True)
    material("M_Explosion", UUID + 4, UUID + 16, "T_Explosion_0", TRANSLUCENT)
    quad("SM_FxQuadBoom", UUID + 5, UUID + 4, "M_Explosion")
    print("wrote the sparkle, %d explosion frames, two materials and two squares -> %s" % (EXPLOSION_FRAMES, OUT))


if __name__ == "__main__":
    main()
