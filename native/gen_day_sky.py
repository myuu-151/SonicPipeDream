"""The title's sky: the Day pack of OctaveSimpleSkies (testproj/SkyboxDay), as its own assets.

    python native/gen_day_sky.py
        -> proj/Assets/Intro/T_DaySkyGradient, T_DayClouds   the pack's two, kept uncompressed
           proj/Assets/Intro/M_DaySky.oct        gradient + clouds + horizon haze, unlit, no fog
           proj/Assets/Intro/SM_DaySkyDome.oct   the pack's dome, wearing M_DaySky

The game already has the pack's two textures (T_SkyGradient, T_Clouds), copied here under names of
the title's own (see copy_texture), but its M_Sky and SM_SkyDome were taken over for the special stage's sky, whose Sky.lua
paints M_Sky's slots with star frames as it goes. So the title gets the pack's material and dome
again under names of its own, and DaySky.lua (the pack's Sky.lua, renamed) scrolls its clouds.
The material and the dome are written exactly as the pack's gen_sky_assets.py writes them.
"""
import math
import os
import struct

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.abspath(os.path.join(HERE, "..", "proj", "Assets", "Intro"))

MAGIC, VERSION = 0x4F435421, 13
TYPE_STATICMESH, TYPE_MATERIALLITE = 0xD41D0D1D, 0xA3ED4C6F
GAME_TEXTURES = os.path.abspath(os.path.join(HERE, "..", "proj", "Assets", "Textures"))
UUID_GRAD, UUID_CLOUD = 0x51C0FFEE00620003, 0x51C0FFEE00620004     # T_DaySkyGradient, T_DayClouds
UUID_MAT, UUID_MESH = 0x51C0FFEE00620001, 0x51C0FFEE00620002


def u8(v): return struct.pack("<B", v)
def u32(v): return struct.pack("<I", v & 0xFFFFFFFF)
def i32(v): return struct.pack("<i", v)
def u64(v): return struct.pack("<Q", v)
def f32(v): return struct.pack("<f", v)


def s(v):
    b = v.encode("ascii")
    return u32(len(b)) + b


def header(type_id, uuid, name):
    return u32(MAGIC) + u32(VERSION) + u32(type_id) + u8(0) + u64(uuid) + s(name)


def asset_ref(uuid, name):
    return u8(1) + u64(uuid) + s(name)


def null_ref():
    return u8(1) + u64(0) + s("")


def gen_material(path):
    d = header(TYPE_MATERIALLITE, UUID_MAT, "M_DaySky")
    d += u32(0)                     # numParameters
    d += u32(0)                     # Unlit
    d += u32(0)                     # Opaque
    d += u32(1)                     # VertexColorMode::Modulate (the dome has none)
    d += u32(3)                     # numTextures
    d += asset_ref(UUID_GRAD, "T_DaySkyGradient") + u8(1) + u8(0)  # gradient, uv1, Replace
    d += asset_ref(UUID_CLOUD, "T_DayClouds") + u8(0) + u8(2)      # clouds, uv0, Decal
    d += asset_ref(UUID_GRAD, "T_DaySkyGradient") + u8(1) + u8(2)  # haze over the clouds, uv1, Decal
    d += null_ref() + u8(0) + u8(1)
    for _ in range(2):
        d += f32(0) + f32(0) + f32(1) + f32(1)
    d += f32(1) + f32(1) + f32(1) + f32(1)
    d += f32(1) + f32(0) + f32(0) + f32(0)
    d += f32(1.0) + f32(0.0) + f32(0.0) + f32(0.0)
    d += u32(2) + f32(1.0) + f32(0.5) + f32(32.0)
    d += i32(0)
    d += u8(0) + u8(0) + u8(0)      # depth test on, no fresnel, no fog
    d += u8(0)                      # no culling
    open(path, "wb").write(d)


RADIUS = 900.0
# The clouds' coordinates are x/y and z/y of the direction (a flat cloud ceiling), which a triangle
# can only follow in straight lines: near the horizon, where they change fastest, big triangles bent
# the clouds, and as they scrolled the bends rolled through them like ripples. So the dome is finer
# there than the pack's (32 round, rings every few degrees low down).
SEGMENTS = 96
ELEVATIONS = [-10.0, 0.0, 1.0, 2.0, 3.0, 4.0, 5.0, 6.5, 8.0, 10.0, 12.0, 14.5, 17.0, 20.0, 24.0, 28.0, 33.0,
              40.0, 48.0, 58.0, 70.0, 82.0]  # + the pole
PLANE_SCALE = 1.6 / 4.0


# THE TITLE LOOKS ALMOST LEVEL: the top of its screen is only some 10 degrees up, where the pack's
# dome is still all horizon haze and no clouds. So here the gradient -- and the haze it carries --
# runs its whole course in the lowest ELEV_SPAN degrees instead of all 90, and the clouds' plane
# reaches down to 4 degrees (MIN_DIRY): the haze sits on the sea's horizon and the clouds come down into view.
ELEV_SPAN = 30.0
MIN_DIRY = math.sin(math.radians(4.0))


def dome_uvs(dirx, diry, dirz, elev_deg):
    dy = max(diry, MIN_DIRY)
    return dirx / dy * PLANE_SCALE, dirz / dy * PLANE_SCALE, 0.5, max(0.0, min(1.0, elev_deg / ELEV_SPAN))


def gen_mesh(path):
    verts = []
    for elev in ELEVATIONS:
        er = math.radians(elev)
        cy, sy = math.cos(er), math.sin(er)
        for seg in range(SEGMENTS + 1):
            az = seg / SEGMENTS * 2.0 * math.pi
            dx, dz, dy = math.cos(az) * cy, math.sin(az) * cy, sy
            u0, v0, u1, v1 = dome_uvs(dx, dy, dz, elev)
            verts.append((dx * RADIUS, dy * RADIUS, dz * RADIUS, u0, v0, u1, v1, -dx, -dy, -dz))
    pole = len(verts)
    verts.append((0.0, RADIUS, 0.0, 0.0, 0.0, 0.5, 1.0, 0.0, -1.0, 0.0))
    idx, cols = [], SEGMENTS + 1
    for ring in range(len(ELEVATIONS) - 1):
        for i in range(SEGMENTS):
            a = ring * cols + i
            idx += [a, a + 1, a + cols, a + 1, a + cols + 1, a + cols]
    top = (len(ELEVATIONS) - 1) * cols
    for i in range(SEGMENTS):
        idx += [top + i, top + i + 1, pole]
    d = header(TYPE_STATICMESH, UUID_MESH, "SM_DaySkyDome")
    d += u32(len(verts)) + u32(len(idx)) + u32(2)
    d += asset_ref(UUID_MAT, "M_DaySky")
    d += u8(0) + u8(0)
    for v in verts:
        d += b"".join(f32(c) for c in v)
    for i in idx:
        d += u32(i)
    d += u8(0) + u32(0)
    d += f32(0) + f32(0) + f32(0) + f32(0)
    open(path, "wb").write(d)


def copy_texture(src, name, uuid):
    """One of the pack's textures (the game has them) under a name of the title's own, marked to stay
    uncompressed on the console. Their alpha carries the haze and the clouds' edges, and the cooked
    CMPR keeps one bit of it -- and makes every clear texel BLACK: the sky above the haze came out
    black once the title's gradient reached up into it."""
    d = open(os.path.join(GAME_TEXTURES, src + ".oct"), "rb").read()
    n = struct.unpack_from("<I", d, 21)[0]
    body = bytearray(d[25 + n:])
    body[28 + 3] = 1                    # (after the 7 words and mips, render target, sRGB) high quality
    out = header(0xCDBBDA30, uuid, name) + bytes(body)
    open(os.path.join(OUT, name + ".oct"), "wb").write(out)


def main():
    os.makedirs(OUT, exist_ok=True)
    copy_texture("T_SkyGradient", "T_DaySkyGradient", UUID_GRAD)
    copy_texture("T_Clouds", "T_DayClouds", UUID_CLOUD)
    gen_material(os.path.join(OUT, "M_DaySky.oct"))
    gen_mesh(os.path.join(OUT, "SM_DaySkyDome.oct"))
    print("M_DaySky, SM_DaySkyDome -> %s" % OUT)


if __name__ == "__main__":
    main()
