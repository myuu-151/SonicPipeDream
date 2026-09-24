"""The little effects: the sparkle a collected ring leaves, and a bomb going off.

    python native/gen_fx_assets.py        (needs Pillow; no Blender)

    -> proj/Assets/Stage/FX/T_Sparkle.oct, M_Sparkle.oct         a four-pointed star, ADDITIVE
                            T_Explosion_0..2.oct, M_Explosion.oct   the bomb going off: external/ui/blowup.png
                            SM_FxQuad.oct, SM_FxQuadBoom.oct        the square they are drawn on
                            T_Razor, M_Razor, SM_FxQuadRazor        the spin dash's rev: a sharp shard, ADDITIVE
                            T_Puff, M_Puff, SM_FxQuadPuff           ...its cloud puffs, left behind
                            M_Trace, SM_FxTrace                     ...and the blue tube traced behind the ball

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


def razor(size=64):
    """A spark thrown off the spin dash's rev: a long thin shard, pointed at both ends, white in the
    middle and blue to the tips, on BLACK (added, as the sparkle is). Drawn across, so a square
    stretched along its X is a long streak."""
    ss = 4
    n = size * ss
    img = Image.new("RGB", (n, n), (0, 0, 0))
    d = ImageDraw.Draw(img)
    c = n / 2.0
    for reach, thick, colour in ((0.49, 0.10, (90, 170, 255)), (0.36, 0.055, (200, 235, 255)), (0.20, 0.03, (255, 255, 255))):
        r, t = n * reach, n * thick
        d.polygon([(c - r, c), (c, c - t), (c + r, c), (c, c + t)], fill=colour)
    glow = img.filter(ImageFilter.GaussianBlur(n * 0.02))
    img = Image.blend(img, glow, 0.4).resize((size, size), Image.LANCZOS)
    return img.convert("RGBA")


def puff(size=96):
    """A cloud puff, as Lost World's spin dash leaves: a few round lumps of white, a little blue in
    the underside, soft at the edge, clear round it (TRANSLUCENT)."""
    ss = 4
    n = size * ss
    mask = Image.new("L", (n, n), 0)
    d = ImageDraw.Draw(mask)
    for cx, cy, r in ((0.50, 0.55, 0.30), (0.30, 0.60, 0.20), (0.70, 0.60, 0.21), (0.40, 0.38, 0.19), (0.62, 0.40, 0.17)):
        d.ellipse(((cx - r) * n, (cy - r) * n, (cx + r) * n, (cy + r) * n), fill=255)
    mask = mask.filter(ImageFilter.GaussianBlur(n * 0.012))
    img = Image.new("RGBA", (n, n))
    px, mp = img.load(), mask.load()
    for y in range(n):
        k = max(0.0, (y / float(n) - 0.45) / 0.45)            # the lower half shades toward blue
        col = (int(255 - 40 * k), int(255 - 25 * k), 255)
        for x in range(n):
            a = mp[x, y]
            if a:
                px[x, y] = col + (a,)
    return img.resize((size, size), Image.LANCZOS)


def trail(size=8):
    """The traced tube's colour: a deep see-through blue, as the spin dash's trail in Sonic Adventure
    (TRANSLUCENT). Only its near wall is drawn (the back culled), so it is one even layer with no
    lines where lengths join or walls cross; the game fades each length toward the tail."""
    return Image.new("RGBA", (size, size), (30, 75, 235, 175))


# THE TRACE: one tube, its rings laid along the ball's path by the game every frame
# (StaticMesh:SetVertexData), so it is one piece -- no joins, no lines -- and fades smoothly by its
# vertices' alpha. Its first rings are a dome over the ball. Keep in step with SpecialStage.lua.
TRACE_RINGS, TRACE_SIDES = 24, 10


def trace_material(name, uuid):
    """Unlit, see-through, coloured by its vertices, only its near side drawn."""
    d = header(TYPE_MATERIALLITE, uuid, name)
    d += u32(0) + u32(0) + u32(TRANSLUCENT) + u32(1)        # no params; UNLIT; translucent; vertex colour
    d += u32(0)                                             # no textures
    for _ in range(4):
        d += null_ref() + u8(0) + u8(1)
    for _ in range(2):
        d += f32(0) + f32(0) + f32(1) + f32(1)
    d += f32(1) + f32(1) + f32(1) + f32(1)
    d += f32(1) + f32(1) + f32(1) + f32(1)
    d += f32(1.0) + f32(0.0) + f32(0.0) + f32(0.0)
    d += u32(2) + f32(1.0) + f32(0.5) + f32(8.0)
    d += i32(0)
    d += u8(0) + u8(0) + u8(0)
    d += u8(1)                                              # cull the back: one even layer
    open(os.path.join(OUT, name + ".oct"), "wb").write(d)


def trace_mesh(name, uuid, material_uuid, material_name):
    """TRACE_RINGS rings of TRACE_SIDES + 1 vertices (the seam twice), joined ring to ring; laid out
    here as a straight tube along +X only so the file has a shape -- the game moves every vertex."""
    import math as m
    n = TRACE_SIDES + 1
    d = header(TYPE_STATICMESH, uuid, name)
    d += u32(TRACE_RINGS * n) + u32((TRACE_RINGS - 1) * TRACE_SIDES * 6) + u32(1)
    d += asset_ref(material_uuid, material_name)
    d += u8(0) + u8(1)                                      # no collision; vertex colour
    for r in range(TRACE_RINGS):
        for k in range(n):
            a = 2.0 * m.pi * k / TRACE_SIDES
            d += f32(float(r)) + f32(0.5 * m.cos(a)) + f32(0.5 * m.sin(a)) + f32(0) + f32(0) + f32(0) + f32(0)
            d += f32(0) + f32(m.cos(a)) + f32(m.sin(a))
            d += u32(0xFFFFFFFF)
    for r in range(TRACE_RINGS - 1):
        for k in range(TRACE_SIDES):
            a, b, c, e = r * n + k, r * n + k + 1, (r + 1) * n + k + 1, (r + 1) * n + k
            for i in (a, b, c, a, c, e):
                d += u32(i)
    d += u8(0) + u32(0)
    d += f32(TRACE_RINGS * 0.5) + f32(0) + f32(0) + f32(TRACE_RINGS * 0.6)
    open(os.path.join(OUT, name + ".oct"), "wb").write(d)


def cap(name, uuid, material_uuid, material_name, sides=12, rings=5):
    """The tube's front: half a sphere of radius 0.5 bulging toward +X, open at the back where the
    tube joins it. It sits over the ball, so the ball is inside the head of its own trail."""
    import math as m
    verts, idx = [], []
    for r in range(rings + 1):
        lat = (m.pi / 2.0) * r / rings                     # 0 at the rim, up to the tip
        x, rad = 0.5 * m.sin(lat), 0.5 * m.cos(lat)
        for k in range(sides + 1):
            a = 2.0 * m.pi * k / sides
            y, z = rad * m.cos(a), rad * m.sin(a)
            verts.append((x, y, z, k / float(sides), r / float(rings), m.sin(lat), m.cos(lat) * m.cos(a), m.cos(lat) * m.sin(a)))
    n = sides + 1
    for r in range(rings):
        for k in range(sides):
            a, b, c, d = r * n + k, r * n + k + 1, (r + 1) * n + k + 1, (r + 1) * n + k
            idx += [a, b, c, a, c, d]
    write_mesh(name, uuid, material_uuid, material_name, verts, idx, (0.25, 0.0, 0.0, 0.56))


def write_mesh(name, uuid, material_uuid, material_name, verts, idx, bounds):
    dd = header(TYPE_STATICMESH, uuid, name)
    dd += u32(len(verts)) + u32(len(idx)) + u32(1)
    dd += asset_ref(material_uuid, material_name)
    dd += u8(0) + u8(0)                                  # no collision; no vertex colour
    for x, y, z, u, v, nx, ny, nz in verts:
        dd += f32(x) + f32(y) + f32(z) + f32(u) + f32(v) + f32(0) + f32(0)
        dd += f32(nx) + f32(ny) + f32(nz)
    for i in idx:
        dd += u32(i)
    dd += u8(0) + u32(0)
    dd += f32(bounds[0]) + f32(bounds[1]) + f32(bounds[2]) + f32(bounds[3])
    open(os.path.join(OUT, name + ".oct"), "wb").write(dd)


def tube(name, uuid, material_uuid, material_name, sides=12):
    """An open cylinder along +X from 0 to 1, radius 0.5: a length of the traced tube. The game
    lays one from each point the ball passed to the next and scales it to fit."""
    import math as m
    verts, idx = [], []
    for ring in (0, 1):
        for k in range(sides + 1):                       # the seam's column twice, for its UVs
            a = 2.0 * m.pi * k / sides
            y, z = 0.5 * m.cos(a), 0.5 * m.sin(a)
            verts.append((float(ring), y, z, k / float(sides), float(ring), 0.0, m.cos(a), m.sin(a)))
    n = sides + 1
    for k in range(sides):
        a, b, c, d = k, k + 1, n + k + 1, n + k
        idx += [a, b, c, a, c, d]
    write_mesh(name, uuid, material_uuid, material_name, verts, idx, (0.5, 0.0, 0.0, 0.75))


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


def material(name, uuid, texture_uuid, texture_name, blend, cull=0):
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
    d += u8(cull)                                           # 0 no culling (seen from behind too); 1 the back
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

    # the spin dash's: the rev's shards, the puffs it leaves, the streak behind the ball
    trace_material("M_Trace", UUID + 25)
    trace_mesh("SM_FxTrace", UUID + 26, UUID + 25, "M_Trace")
    for base, img, blend, n in (("Razor", razor(), ADDITIVE, 6), ("Puff", puff(), TRANSLUCENT, 9)):
        img.save(os.path.join(LOOK, "T_%s.png" % base))
        # (the see-through ones kept out of the GameCube's CMPR: its alpha is one bit, and the tube's
        # 36% blue came out entirely clear -- the tube was there and drew nothing)
        write_texture(os.path.join(OUT, "T_%s.oct" % base), "T_%s" % base, UUID + n, img.width, img.height,
                      img.tobytes(), wrap=0, quiet=True, force_hq=(base in ("Trail", "Puff")))
        material("M_%s" % base, UUID + n + 1, UUID + n, "T_%s" % base, blend, cull=(1 if base == "Trail" else 0))
        if (base == "Trail"):
            tube("SM_FxTube", UUID + n + 2, UUID + n + 1, "M_%s" % base)
            cap("SM_FxTubeCap", UUID + 24, UUID + n + 1, "M_%s" % base)
        else:
            quad("SM_FxQuad%s" % base, UUID + n + 2, UUID + n + 1, "M_%s" % base)
    print("wrote the sparkle, %d explosion frames, the spin dash's shard, puff and streak -> %s" % (EXPLOSION_FRAMES, OUT))


if __name__ == "__main__":
    main()
