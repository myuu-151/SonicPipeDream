#!/usr/bin/env python
# Generates Octave .oct assets for a windward-style sky dome:
#   T_SkyGradient.oct  (8x256 RGBA8, clamp)  RGB=horizon->zenith ramp, A=horizon haze fade
#   T_Clouds.oct       (512x512 RGBA8, repeat) tileable two-tone FBM clouds, A=coverage mask
#   M_Sky.oct          (MaterialLite: gradient Replace + clouds Decal + haze Decal, unlit, no fog)
#   SM_SkyDome.oct     (hemisphere + skirt, inward, 2 UV channels, radius 900)
# Formats per Octave asset version 13 (little-endian, verified against shipped assets).

import math
import struct
import os

OUT = r"C:\Users\NoSig\Documents\testproj\Assets"

MAGIC = 0x4F435421
VERSION = 13
TYPE_TEXTURE = 0xCDBBDA30
TYPE_STATICMESH = 0xD41D0D1D
TYPE_MATERIALLITE = 0xA3ED4C6F

# fixed arbitrary non-zero uuids
UUID_GRAD = 0x51C0FFEE00000001
UUID_CLOUD = 0x51C0FFEE00000002
UUID_MAT = 0x51C0FFEE00000003
UUID_MESH = 0x51C0FFEE00000004


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


def smoothstep(e0, e1, x):
    t = max(0.0, min(1.0, (x - e0) / (e1 - e0)))
    return t * t * (3.0 - 2.0 * t)


def mix(a, b, t):
    return a + (b - a) * t


# ---------------------------------------------------------------- textures

def write_texture(path, name, uuid, w, h, pixels, wrap, srgb=True):
    # pixels: bytearray of w*h*4 RGBA
    data = header(TYPE_TEXTURE, uuid, name)
    data += u32(w) + u32(h) + u32(1) + u32(1)      # w, h, mips=1, layers=1
    data += u32(2) + u32(1) + u32(wrap)            # RGBA8, Linear, wrap
    data += u8(0) + u8(0) + u8(1 if srgb else 0)   # mipmapped, renderTarget, srgb
    data += u8(0) + u8(1)                          # forceHighQuality, lqDownsampleFactor
    assert len(pixels) == w * h * 4
    data += bytes(pixels)
    with open(path, "wb") as f:
        f.write(data)
    print("wrote %s (%d bytes)" % (path, len(data)))


ZENITH = (0.22, 0.42, 0.86)
HORIZON = (0.66, 0.80, 0.95)


def gen_gradient():
    w, h = 8, 256
    px = bytearray()
    for row in range(h):
        v = row / (h - 1.0)          # 0 = horizon, 1 = zenith
        elev = v * math.pi * 0.5
        diry = math.sin(elev)
        t = pow(max(diry, 0.0), 0.55)
        r = mix(HORIZON[0], ZENITH[0], t)
        g = mix(HORIZON[1], ZENITH[1], t)
        b = mix(HORIZON[2], ZENITH[2], t)
        haze = 1.0 - smoothstep(0.175, 0.34, diry)   # horizon fade (widened to hide clamp streaks)
        rowbytes = bytes((int(r * 255), int(g * 255), int(b * 255), int(haze * 255))) * w
        px += rowbytes
    return w, h, px


# tileable value-noise FBM (periodic lattice, integer base frequency)

def hash2(ix, iy, period, seed):
    # deterministic integer hash on wrapped lattice
    ix %= period
    iy %= period
    n = (ix * 374761393 + iy * 668265263 + seed * 2246822519) & 0xFFFFFFFF
    n = (n ^ (n >> 13)) & 0xFFFFFFFF
    n = (n * 1274126177) & 0xFFFFFFFF
    n = (n ^ (n >> 16)) & 0xFFFFFFFF
    return n / 4294967295.0


def vnoise(x, y, period, seed):
    ix, iy = math.floor(x), math.floor(y)
    fx, fy = x - ix, y - iy
    ux = fx * fx * (3.0 - 2.0 * fx)
    uy = fy * fy * (3.0 - 2.0 * fy)
    ix, iy = int(ix), int(iy)
    a = hash2(ix, iy, period, seed)
    b = hash2(ix + 1, iy, period, seed)
    c = hash2(ix, iy + 1, period, seed)
    d = hash2(ix + 1, iy + 1, period, seed)
    return mix(mix(a, b, ux), mix(c, d, ux), uy)


def fbm(x, y, base_period, seed):
    v, amp = 0.0, 0.5
    freq = 1
    for octave in range(5):
        p = base_period * freq
        v += amp * vnoise(x * freq, y * freq, p, seed + octave * 101)
        freq *= 2
        amp *= 0.5
    return v


BASE = 4            # noise cells per texture tile
COVERAGE = 0.52
SUN = (0.45, -0.60)  # xz, matches windward uSunDir.xz


def gen_clouds():
    size = 512
    sl = math.hypot(SUN[0], SUN[1])
    sx, sy = SUN[0] / sl * 0.35, SUN[1] / sl * 0.35
    lit = (1.0, 1.0, 1.0)
    shadow = (0.62, 0.70, 0.85)
    px = bytearray(size * size * 4)
    for j in range(size):
        y = j / size * BASE
        for i in range(size):
            x = i / size * BASE
            # domain warp at half frequency; lattice period BASE//2 keeps the
            # half-frequency field seamless over one texture tile
            wx = fbm(x * 0.5 + 13.7, y * 0.5 + 13.7, BASE // 2, 7) - 0.5
            wy = fbm(x * 0.5 - 7.2, y * 0.5 - 7.2, BASE // 2, 23) - 0.5
            pxx = x + wx * 1.4
            pyy = y + wy * 1.4
            f = fbm(pxx, pyy, BASE, 42)
            mask = smoothstep(COVERAGE, COVERAGE + 0.10, f)
            f2 = fbm(pxx + sx, pyy + sy, BASE, 42)
            shade = smoothstep(COVERAGE + 0.02, COVERAGE + 0.18, f2)
            r = mix(shadow[0], lit[0], shade)
            g = mix(shadow[1], lit[1], shade)
            b = mix(shadow[2], lit[2], shade)
            o = (j * size + i) * 4
            px[o] = int(r * 255)
            px[o + 1] = int(g * 255)
            px[o + 2] = int(b * 255)
            px[o + 3] = int(mask * 255)
    return size, size, px


# ---------------------------------------------------------------- material

def gen_material(path):
    d = header(TYPE_MATERIALLITE, UUID_MAT, "M_Sky")
    d += u32(0)                     # Material::numParameters
    d += u32(0)                     # ShadingModel::Unlit
    d += u32(0)                     # BlendMode::Opaque
    d += u32(1)                     # VertexColorMode::Modulate (mesh has no vcolor)
    d += u32(3)                     # numTextures
    # slot 0: gradient, uv1, Replace
    d += asset_ref(UUID_GRAD, "T_SkyGradient") + u8(1) + u8(0)
    # slot 1: clouds, uv0, Decal
    d += asset_ref(UUID_CLOUD, "T_Clouds") + u8(0) + u8(2)
    # slot 2: gradient again, uv1, Decal (haze over clouds near horizon)
    d += asset_ref(UUID_GRAD, "T_SkyGradient") + u8(1) + u8(2)
    # slot 3: unused
    d += null_ref() + u8(0) + u8(1)
    # uv offsets/scales
    for _ in range(2):
        d += f32(0) + f32(0) + f32(1) + f32(1)
    d += f32(1) + f32(1) + f32(1) + f32(1)       # color
    d += f32(1) + f32(0) + f32(0) + f32(0)       # fresnel color
    d += f32(1.0)                                # fresnelPower
    d += f32(0.0)                                # emission
    d += f32(0.0)                                # wrapLighting
    d += f32(0.0)                                # specular
    d += u32(2)                                  # toonSteps
    d += f32(1.0)                                # opacity
    d += f32(0.5)                                # maskCutoff
    d += f32(32.0)                               # shininess
    d += i32(0)                                  # sortPriority
    d += u8(0)                                   # disableDepthTest
    d += u8(0)                                   # fresnelEnabled
    d += u8(0)                                   # applyFog: OFF for sky
    d += u8(0)                                   # CullMode::None
    with open(path, "wb") as f:
        f.write(d)
    print("wrote %s (%d bytes)" % (path, len(d)))


# ---------------------------------------------------------------- dome mesh

RADIUS = 900.0
SEGMENTS = 32
ELEVATIONS = [-80.0, -50.0, -25.0, -10.0, 0.0, 4.0, 9.0, 15.0, 22.0, 30.0, 40.0, 52.0, 66.0, 80.0]  # + pole
PLANE_SCALE = 1.6 / 4.0     # windward 1.6, texture holds 4 noise cells per tile
MIN_DIRY = math.sin(math.radians(10.0))


def dome_uvs(dirx, diry, dirz, elev_deg):
    dy = max(diry, MIN_DIRY)
    u0 = dirx / dy * PLANE_SCALE
    v0 = dirz / dy * PLANE_SCALE
    v1 = max(0.0, min(1.0, elev_deg / 90.0))
    return u0, v0, 0.5, v1


def gen_mesh(path):
    verts = []   # (px,py,pz, u0,v0, u1,v1, nx,ny,nz)
    for elev in ELEVATIONS:
        er = math.radians(elev)
        cy, sy_ = math.cos(er), math.sin(er)
        for seg in range(SEGMENTS + 1):     # duplicate seam column for clean UVs
            az = seg / SEGMENTS * 2.0 * math.pi
            dx = math.cos(az) * cy
            dz = math.sin(az) * cy
            dy = sy_
            u0, v0, u1, v1 = dome_uvs(dx, dy, dz, elev)
            verts.append((dx * RADIUS, dy * RADIUS, dz * RADIUS,
                          u0, v0, u1, v1, -dx, -dy, -dz))
    # pole
    pole_index = len(verts)
    verts.append((0.0, RADIUS, 0.0, 0.0, 0.0, 0.5, 1.0, 0.0, -1.0, 0.0))

    idx = []
    cols = SEGMENTS + 1
    for ring in range(len(ELEVATIONS) - 1):
        for seg_i in range(SEGMENTS):
            a = ring * cols + seg_i
            b = a + 1
            c = a + cols
            dd = c + 1
            # inward-facing winding (viewed from center)
            idx += [a, b, c, b, dd, c]
    top = (len(ELEVATIONS) - 1) * cols
    for seg_i in range(SEGMENTS):
        idx += [top + seg_i, top + seg_i + 1, pole_index]

    d = header(TYPE_STATICMESH, UUID_MESH, "SM_SkyDome")
    d += u32(len(verts)) + u32(len(idx)) + u32(2)
    d += asset_ref(UUID_MAT, "M_Sky")
    d += u8(0)          # generateTriangleCollisionMesh
    d += u8(0)          # hasVertexColor
    for v in verts:
        d += b"".join(f32(c) for c in v)
    for ii in idx:
        d += u32(ii)
    d += u8(0)          # compound
    d += u32(0)         # numCollisionShapes
    d += f32(0) + f32(0) + f32(0) + f32(0)   # bounds (recomputed on load)
    with open(path, "wb") as f:
        f.write(d)
    print("wrote %s (%d verts, %d indices, %d bytes)" % (path, len(verts), len(idx), len(d)))


def main():
    tex_dir = os.path.join(OUT, "Textures")
    mat_dir = os.path.join(OUT, "Materials")
    mesh_dir = os.path.join(OUT, "Meshes")
    for p in (tex_dir, mat_dir, mesh_dir):
        os.makedirs(p, exist_ok=True)

    w, h, px = gen_gradient()
    write_texture(os.path.join(tex_dir, "T_SkyGradient.oct"), "T_SkyGradient",
                  UUID_GRAD, w, h, px, wrap=0)   # Clamp
    w, h, px = gen_clouds()
    write_texture(os.path.join(tex_dir, "T_Clouds.oct"), "T_Clouds",
                  UUID_CLOUD, w, h, px, wrap=1)  # Repeat
    gen_material(os.path.join(mat_dir, "M_Sky.oct"))
    gen_mesh(os.path.join(mesh_dir, "SM_SkyDome.oct"))


if __name__ == "__main__":
    main()
