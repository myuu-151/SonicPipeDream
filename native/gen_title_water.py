"""The title's sea: open water under the emblem, out to the horizon, after Sonic Adventure's
Emerald Coast's GameCube beach water -- the way the period games built it: a black-and-white
light map (soft wavy streaks running left-right) ADDED over a plain blue, the colour coming from
the material and the vertex colour, two copies of the map at different scales and drifts swimming
through each other, wobbled by a bump map; deepening with distance to the open sea's blue and a
darker line at the horizon, then into the sky's haze.

    py native/gen_title_water.py          (needs numpy and Pillow; no Blender, no engine)
        -> proj/Assets/Intro/T_WaterBase.oct        8 x 8: the near water's blue, flat
           proj/Assets/Intro/T_WaterLight.oct       256 x 256 RGBA8: the light map x LIGHT_GAIN, ADDED
           proj/Assets/Intro/T_WaterLightDim.oct    256 x 256 RGBA8: the same x LIGHT_DIM_GAIN, ADDED
           proj/Assets/Intro/T_WaterBump.oct        256 x 256 RGBA8: the warp's offsets (G = u, B = v)
           proj/Assets/Intro/M_Water.oct            base + light + dim light + warp (TevMode 8)
           proj/Assets/Intro/M_WaterNoWarp.oct      the same without the warp
           proj/Assets/Intro/SM_WaterBed.oct        a flat disc of radius 890 wearing M_Water
           external/intro/export/<each texture>.png     as written, to look at
           external/intro/export/water_preview.png      the title camera's view, rendered here
           external/intro/export/water_preview_1s.png   ...one second later
           external/intro/export/water_preview.gif      ...two seconds of it moving

THE LIGHT MAP is external/intro/water/T_WaterLight_gpt.png (the owner's: 1024 x 1024 greyscale,
tileable, soft smeared light streaks running left-right on mid grey). Its grey background must not
lift the water's colour, so it is remapped first: its median goes to black, the brightest to white,
then a gamma of LIGHT_GAMMA, so only the streaks add light. Then 256 x 256, uncompressed (Force
High Quality). Any tileable greyscale picture there works, any size; the streaks should run along
the picture's width, which is world X, so they lie flat on the screen. Without one, a stand-in is
computed: light through a wavy surface (a regular grid of rays bent by the slope of a tileable sum
of sine waves, counted where they land, blurred and tone-mapped). T_WaterBump.png there replaces
the bump map the same way.

WaterBed.lua keeps the disc under the camera, at WATER_Y, and scrolls the layers. Intro.lua
spawns it: node:SetStaticMesh(LoadAsset("SM_WaterBed")); node:SetScript("WaterBed").

THE HEIGHT. The sea is at y = -1.6, 0.3 under the emblem's lowest point (-1.3). The title camera's
eye is at y = 0.32 (AIM -0.1, lifted 3 degrees at distance 8), so the sea is 1.92 under it. The
horizon is at eye level whatever the height: 3 degrees above the middle of the screen, behind the
middle of the emblem. The height decides how near the first water is: the bottom of a 16:9 screen
(12.6 degrees down) meets the sea 8.6 units out, just behind the emblem, so the emblem hovers over
open water; a 4:3 screen sees it from 6.8 units. On screen only the height over the tile size
counts, so lower water just looks like smaller streaks.

THE LAYERS. Slot 0, T_WaterBase (Replace -- on GX slot 0 always is), is the near water's blue,
flat. Slot 1, T_WaterLight on UV0 (Add), is the light map at LIGHT_GAIN, TILE_A units a repeat.
Slot 2, T_WaterLightDim on UV1 (Add), is the same map at LIGHT_DIM_GAIN, at the larger TILE_B,
drifting another way (not turned: the streaks stay along X): where the two cross the light goes
whiter, and they swim through each other. Slot 3, T_WaterBump on UV1 (TevMode 8, Warp, strength WARP_STRENGTH in
Emission), bends every lookup by (gb - 0.5) * strength; it drifts with the dim copy, against the
first, so the first copy's web wobbles. M_WaterNoWarp is slots 0-2 alone (an engine without
TevMode 8 also skips slot 3 by itself).

THE DISTANCE. The vertex colour does it: its RGB multiplies the water, white for the first few
units, then to the open sea's blue OPEN_SEA, then to the darker HORIZON_LINE; its alpha (the
material is Translucent) holds 1 to FADE_NEAR and goes to 0 at the rim. Vertex colour can only
darken (a byte of 255 is x1, even with ColorScale 2), and it multiplies AFTER the light is
added, so the near blue lives in T_WaterBase and the vertex colour takes it down from there.
Each ring's RGB is the colour wanted there over the average colour of the water (base plus both
copies' average, which is what the mipmaps show far off). Behind the fading rim is the sky dome's
band below the horizon, the haze colour, so the sea meets the sky through the sky's own haze. The
rings are spaced evenly in log distance.

ALPHA AND THE ADD. Add adds alpha too (GX: APREV + TEXA; the shaders: prev + tex), so the base's
alpha is 255 and the light maps' 0, and the vertex alpha alone decides the fade. The light maps
and the bump are Force High Quality (RGBA8): a texture all alpha 0 would be cooked by this
project's forced CMPR as a cutout and come out black, smooth offsets go blocky in CMPR, and the
streaks should stay clean.

UVs. UV0 = (x, z) / TILE_A and UV1 = (x, z) / TILE_B in the disc's own space. The disc follows the
camera, so WaterBed.lua adds the disc's position / TILE to each offset: the sea stays put in the
world and slides past the emblem with the right parallax as the camera sways. Keep TILE_A, TILE_B
and the drifts in step with WaterBed.lua. At the rim the coordinates reach 890 / TILE_A = 130
repeats; the far water is the mipmaps' average there anyway.

THE GAMECUBE. Three direct textures and one warp; TEV stages: vertex colour, the three layers,
material colour, vertex colour modulate, ColorScale: seven, unlit. All maps mipmapped, about
1 MB together. The disc: about 3900 triangles.
"""
import math
import os
import struct

import numpy as np
from PIL import Image, ImageDraw

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, ".."))
OUT = os.path.join(ROOT, "proj", "Assets", "Intro")
EXPORT = os.path.join(ROOT, "external", "intro", "export")
HANDMADE = os.path.join(ROOT, "external", "intro", "water")
SKY_GRADIENT = os.path.join(ROOT, "proj", "Assets", "Textures", "T_SkyGradient.oct")
SKY_CLOUDS = os.path.join(ROOT, "proj", "Assets", "Textures", "T_Clouds.oct")

MAGIC, VERSION = 0x4F435421, 13
TYPE_TEXTURE, TYPE_STATICMESH, TYPE_MATERIALLITE = 0xCDBBDA30, 0xD41D0D1D, 0xA3ED4C6F
UUID_MAT, UUID_MAT_NOWARP, UUID_MESH = 0x51C0FFEE00630004, 0x51C0FFEE00630005, 0x51C0FFEE00630006
UUID_BASE, UUID_BUMP = 0x51C0FFEE0063000C, 0x51C0FFEE00630008
UUID_LIGHT, UUID_LIGHT_DIM = 0x51C0FFEE0063000F, 0x51C0FFEE00630010
STALE = (["T_Water", "T_WaterGlint", "T_WaterWarp", "T_WaterSheen", "T_WaterWeb", "T_WaterCaustic",
          "T_WaterCausticDim"]
         + ["T_WaterCaustic_%02d" % i for i in range(16)])          # earlier versions' maps, removed

# ------------------------------------------------------------------ where and how fast (keep in step with WaterBed.lua)
WATER_Y = -1.6                  # the sea's surface; 0.3 under the emblem's lowest point
TILE_A = 7.0                    # world units per repeat of T_WaterLight (UV0)
TILE_B = 11.0                   # ...of T_WaterLightDim and T_WaterBump (UV1)
DRIFT_A = (0.04, 0.10)          # the first copy, world units a second (x, z)
DRIFT_B = (-0.14, 0.20)         # the dim copy and the bump: another way
SWELL, SWELL_SECONDS = 0.02, 7.0   # the whole sea rising and falling, gently

# ------------------------------------------------------------------ the title camera (Intro.lua)
AIM = (0.0, -0.10, 0.0)
DISTANCE, VIEW_WIDTH = 8.0, 4.8
SWAY_DEGREES, SWAY_SECONDS, LIFT_DEGREES = 7.0, 9.0, 3.0
EYE_Y = AIM[1] + math.sin(math.radians(LIFT_DEGREES)) * DISTANCE
H_EYE = EYE_Y - WATER_Y         # the eye over the sea: 1.92
EMBLEM = (-2.05, 2.05, -1.3, 1.05)  # x0, x1, y0, y1 at z = 0, outlined in the preview

# ------------------------------------------------------------------ the disc and its colour
RADIUS = 890.0                  # inside the dome (900) even counting the drop to the sea
SEGMENTS = 64
RINGS = 30                      # from 4 units to the rim, evenly in log distance
OPEN_SEA = (0x1e, 0x6c, 0xe4)   # the open sea's blue (reference: #1460d8 to #2a7ef0)
HORIZON_LINE = (0x12, 0x5a, 0xd2)   # a little darker where the sea meets the sky
TINT_KEYS = [(9.0, None), (30.0, OPEN_SEA), (220.0, OPEN_SEA), (420.0, HORIZON_LINE)]
FADE_NEAR = 430.0               # solid to here, then into the haze by the rim

# ------------------------------------------------------------------ the textures
SIZE = 256
BASE = (0x1e, 0x8c, 0xe0)       # the near water: turquoise-blue (T_WaterBase, flat)
LIGHT_MAP = "T_WaterLight_gpt.png"   # in external/intro/water
LIGHT_GAMMA = 1.3               # after the remap (median -> black, brightest -> white)
LIGHT_GAIN = 0.70               # the light map, added: the first copy...
LIGHT_DIM_GAIN = 0.40           # ...and the dim one
WARP_STRENGTH = 0.04            # UV units of bend at full offset (half that each way): Emission
WARP_SLOT = 3
# the stand-in, when there is no light map
RAYS = 768                      # light rays across a tile, each way (3 per texel)
CAUSTIC_WAVES = [               # (kx, ky) whole waves across the tile, m cycles (unused here), amp, phase
    ((4, 1), 1, 1.0, 0.0), ((-2, 5), -1, 0.95, 1.7), ((5, -3), 1, 0.9, 4.1), ((-5, -2), 2, 0.8, 2.6),
    ((1, 6), -1, 0.75, 5.3), ((6, 3), 1, 0.7, 0.9), ((-6, 4), -2, 0.6, 3.3), ((7, -1), 2, 0.55, 1.1),
    ((-3, -7), 1, 0.5, 4.8), ((8, 4), -1, 0.4, 2.2), ((3, -8), 2, 0.35, 0.4), ((-9, 2), -1, 0.3, 3.9)]
FOCUS = 1.9                     # how strongly the surface focuses the light


# ================================================================== .oct writing
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


def write_texture(name, uuid, rgba, hq, srgb=True):
    """rgba: h x w x 4 uint8. Repeat, linear, mipmapped (the engine and the cooker build the
    levels from these texels); hq = Force High Quality (stays RGBA8 on the console)."""
    h, w = rgba.shape[:2]
    mips = int(math.floor(math.log2(max(w, h)))) + 1
    d = header(TYPE_TEXTURE, uuid, name)
    d += u32(w) + u32(h) + u32(mips) + u32(1)               # size, mips, layers
    d += u32(2) + u32(1) + u32(1)                           # RGBA8, Linear, Repeat
    d += u8(1) + u8(0) + u8(1 if srgb else 0)               # mipmapped, render target, sRGB
    d += u8(1 if hq else 0) + u8(1)                         # force high quality, downsample 1
    d += np.ascontiguousarray(rgba, dtype=np.uint8).tobytes()
    open(os.path.join(OUT, name + ".oct"), "wb").write(d)


def gen_material(name, uuid, warp):
    """Unlit, Translucent (the fade is the vertices' alpha), vertex colour Modulate, no fog."""
    slots = [asset_ref(UUID_BASE, "T_WaterBase") + u8(0) + u8(0),             # the blue, Replace
             asset_ref(UUID_LIGHT, "T_WaterLight") + u8(0) + u8(3),           # light, UV0, Add
             asset_ref(UUID_LIGHT_DIM, "T_WaterLightDim") + u8(1) + u8(3),    # dim copy, UV1, Add
             null_ref() + u8(0) + u8(1)]
    if warp:
        slots[WARP_SLOT] = asset_ref(UUID_BUMP, "T_WaterBump") + u8(1) + u8(8)   # UV1, Warp
    d = header(TYPE_MATERIALLITE, uuid, name)
    d += u32(0)                     # numParameters
    d += u32(0)                     # Unlit
    d += u32(2)                     # Translucent
    d += u32(1)                     # VertexColorMode::Modulate: RGB = the distance colour, A = the fade
    d += u32(4 if warp else 3)      # numTextures
    d += b"".join(slots)
    for _ in range(2):
        d += f32(0) + f32(0) + f32(1) + f32(1)      # uv offset, scale (WaterBed.lua drives the offsets)
    d += f32(1) + f32(1) + f32(1) + f32(1)          # colour
    d += f32(1) + f32(0) + f32(0) + f32(0)          # fresnel colour
    # fresnel power, emission, wrap lighting, specular. EMISSION IS THE WARP'S STRENGTH (the engine's
    # Warp mode keeps it there: uv + (byte - 128) / 256 * strength), for the warp material only
    d += f32(1.0) + f32(WARP_STRENGTH if warp else 0.0) + f32(0.0) + f32(0.0)
    d += u32(2) + f32(1.0) + f32(0.5) + f32(32.0)   # toon steps, opacity, mask cutoff, shininess
    d += i32(0)                                     # sort priority
    d += u8(0) + u8(0) + u8(0)                      # depth test on, no fresnel, no fog
    d += u8(0)                                      # no culling
    open(os.path.join(OUT, name + ".oct"), "wb").write(d)


# ================================================================== the disc
def smoothstep(e0, e1, x):
    t = np.clip((x - e0) / (e1 - e0), 0.0, 1.0)
    return t * t * (3.0 - 2.0 * t)


def ring_radii():
    return [0.0, 2.0] + list(np.geomspace(4.0, RADIUS, RINGS))


def fade_alpha(dist):
    """1 nearer than FADE_NEAR, 0 at the rim, smooth in the angle below the horizon."""
    near, far = math.atan2(H_EYE, FADE_NEAR), math.atan2(H_EYE, RADIUS)
    t = np.clip((np.arctan2(H_EYE, np.asarray(dist, dtype=float)) - far) / (near - far), 0.0, 1.0)
    return t * t * (3.0 - 2.0 * t)


def tint(dist, average):
    """The vertices' RGB at each distance: white near, then each key's colour over the water's
    average colour (what the mipmaps show far off), smooth in log distance between the keys."""
    keys = [(d, np.ones(3) if c is None else np.minimum(1.0, np.asarray(c) / 255.0 / average))
            for d, c in TINT_KEYS]
    dist = np.atleast_1d(np.asarray(dist, dtype=float))
    out = np.empty((len(dist), 3))
    ld = np.log(np.maximum(dist, 1e-3))
    for i, x in enumerate(ld):
        if x <= math.log(keys[0][0]):
            out[i] = keys[0][1]
        elif x >= math.log(keys[-1][0]):
            out[i] = keys[-1][1]
        else:
            for (d0, c0), (d1, c1) in zip(keys, keys[1:]):
                if math.log(d0) <= x <= math.log(d1):
                    t = float(smoothstep(math.log(d0), math.log(d1), x))
                    out[i] = c0 * (1 - t) + c1 * t
                    break
    return out


def gen_mesh(average):
    radii = ring_radii()
    alphas = fade_alpha(radii)
    colours = []
    for rgb, a in zip(tint(radii, average), alphas):
        c = [int(round(float(x) * 255.0)) for x in list(rgb) + [a]]
        colours.append(c[0] | (c[1] << 8) | (c[2] << 16) | (c[3] << 24))
    verts = [(0.0, 0.0, colours[0])]
    for r, c in zip(radii[1:], colours[1:]):
        for k in range(SEGMENTS):
            t = 2.0 * math.pi * k / SEGMENTS
            verts.append((r * math.cos(t), r * math.sin(t), c))
    idx = []
    for k in range(SEGMENTS):                                       # the middle: a fan
        idx += [0, 1 + (k + 1) % SEGMENTS, 1 + k]
    for ring in range(len(radii) - 2):
        a0, b0 = 1 + ring * SEGMENTS, 1 + (ring + 1) * SEGMENTS
        for k in range(SEGMENTS):
            k1 = (k + 1) % SEGMENTS
            idx += [a0 + k, a0 + k1, b0 + k, a0 + k1, b0 + k1, b0 + k]
    d = header(TYPE_STATICMESH, UUID_MESH, "SM_WaterBed")
    d += u32(len(verts)) + u32(len(idx)) + u32(2)
    d += asset_ref(UUID_MAT, "M_Water")
    d += u8(0) + u8(1)                                              # no collision; vertex colour
    for x, z, c in verts:
        d += f32(x) + f32(0.0) + f32(z)
        d += f32(x / TILE_A) + f32(z / TILE_A) + f32(x / TILE_B) + f32(z / TILE_B)
        d += f32(0.0) + f32(1.0) + f32(0.0)
        d += u32(c)                                                 # RGB = distance colour, A = fade
    for i in idx:
        d += u32(i)
    d += u8(0) + u32(0)
    d += f32(0) + f32(0) + f32(0) + f32(RADIUS)
    open(os.path.join(OUT, "SM_WaterBed.oct"), "wb").write(d)
    return len(verts), len(idx) // 3


# ================================================================== tileable fields
def spectral_noise(n, kmin, kmax, slope, seed, stretch=1.0):
    """n x n noise that tiles (made in frequency space): wave numbers kmin..kmax across the
    picture, falling off as k^-slope; stretch > 1 makes its features wider than tall."""
    rng = np.random.default_rng(seed)
    f = np.fft.fft2(rng.standard_normal((n, n)))
    k = np.fft.fftfreq(n) * n
    kx, ky = np.meshgrid(k, k)
    kr = np.hypot(kx * stretch, ky)
    band = smoothstep(kmin * 0.6, kmin, kr) * (1.0 - smoothstep(kmax, kmax * 1.5, kr))
    band = band * np.where(kr > 0, np.maximum(kr, 1e-6) ** -slope, 0.0)
    h = np.real(np.fft.ifft2(f * band))
    return (h - h.mean()) / h.std()


def blur(img, sigma):
    """Gaussian blur that wraps round the edges (the picture tiles)."""
    n, m = img.shape[:2]
    fy, fx = np.fft.fftfreq(n)[:, None], np.fft.fftfreq(m)[None, :]
    g = np.exp(-2.0 * (math.pi * sigma) ** 2 * (fx * fx + fy * fy))
    if img.ndim == 3:
        g = g[..., None]
        return np.real(np.fft.ifft2(np.fft.fft2(img, axes=(0, 1)) * g, axes=(0, 1)))
    return np.real(np.fft.ifft2(np.fft.fft2(img) * g))


def to_rgba(rgb, alpha):
    out = np.empty(rgb.shape[:2] + (4,), dtype=np.uint8)
    out[..., :3] = np.clip(np.round(rgb * 255.0), 0, 255)
    out[..., 3] = alpha
    return out


def colour(c):
    return np.asarray(c, dtype=float) / 255.0


# ================================================================== the pictures
def light(phase):
    """The light reaching the floor at one moment of the loop (0..1): RAYS x RAYS rays bent by the
    height field's slope, counted where they land, blurred a touch, at SIZE x SIZE; mean 1."""
    c = (np.arange(RAYS) + 0.5) / RAYS
    x, y = np.meshgrid(c, c)
    gx, gy = np.zeros_like(x), np.zeros_like(x)
    lap = np.zeros_like(x)
    for (kx, ky), m, a, p in CAUSTIC_WAVES:
        arg = 2.0 * math.pi * (kx * x + ky * y + m * phase) + p
        amp = a / (kx * kx + ky * ky)
        gx += amp * kx * np.cos(arg)
        gy += amp * ky * np.cos(arg)
        lap -= amp * (kx * kx + ky * ky) * np.sin(arg)
    # bend so the strongest curvature just focuses: displacement = k * slope
    k = FOCUS / (2.0 * math.pi * np.percentile(np.abs(lap), 99.5))
    lx = np.floor((x + k * gx) * RAYS).astype(int) % RAYS
    ly = np.floor((y + k * gy) * RAYS).astype(int) % RAYS
    hits = np.bincount((ly * RAYS + lx).ravel(), minlength=RAYS * RAYS).reshape(RAYS, RAYS).astype(float)
    hits = blur(hits, 1.4 * RAYS / SIZE)
    ss = RAYS // SIZE
    hits = hits.reshape(SIZE, ss, SIZE, ss).mean(axis=(1, 3))
    return hits / hits.mean()


def make_stand_in():
    """When there is no light map: the light through a wavy surface at one moment, tone-mapped (0..1)."""
    li = light(0.0)
    lo, hi = np.percentile(li, 55), np.percentile(li, 99.6)
    web = np.clip((li - lo) / (hi - lo), 0.0, 1.0)
    return 0.75 * web + 0.25 * blur(web, 2.5)


def light_map():
    """The light's intensity, SIZE x SIZE, 0..1: the owner's map remapped so its background is
    black (median -> 0, its 99.9th percentile -> 1, then LIGHT_GAMMA), or the stand-in."""
    path = os.path.join(HANDMADE, LIGHT_MAP)
    if not os.path.exists(path):
        print("no external/intro/water/%s: using the computed stand-in" % LIGHT_MAP)
        return make_stand_in()
    img = Image.open(path).convert("L")
    if img.size != (SIZE, SIZE):
        img = img.resize((SIZE, SIZE), Image.LANCZOS)
    a = np.asarray(img, dtype=float) / 255.0
    lo, hi = np.median(a), np.percentile(a, 99.9)
    return np.clip((a - lo) / max(hi - lo, 1e-3), 0.0, 1.0) ** LIGHT_GAMMA


def added(intensity, gain):
    """An intensity map as an added texture: grey x gain, alpha 0."""
    return to_rgba(np.repeat((intensity * gain)[..., None], 3, axis=2), 0)


def make_bump():
    """The warp's offsets: the slope of a smooth tileable swell, 0.5 = none. G = across (u),
    B = along (v) -- what the engine's Warp reads, as GX's indirect unit can (it reads A, B and G
    only); R carries u again, A is opaque."""
    h = spectral_noise(SIZE, 4, 14, 1.8, 31, stretch=1.4)
    gx = (np.roll(h, -1, 1) - np.roll(h, 1, 1)) * 0.5
    gy = (np.roll(h, -1, 0) - np.roll(h, 1, 0)) * 0.5
    scale = np.percentile(np.maximum(np.abs(gx), np.abs(gy)), 99.5)
    gx, gy = np.clip(gx / scale, -1, 1), np.clip(gy / scale, -1, 1)
    out = np.empty((SIZE, SIZE, 4), dtype=np.uint8)
    out[..., 0] = out[..., 1] = np.clip(np.round(127.5 + 127.5 * gx), 0, 255)
    out[..., 2] = np.clip(np.round(127.5 + 127.5 * gy), 0, 255)
    out[..., 3] = 255
    return out


def handmade_bump():
    """external/intro/water/T_WaterBump.png if there is one (scaled to SIZE, R copies G), else None."""
    path = os.path.join(HANDMADE, "T_WaterBump.png")
    if not os.path.exists(path):
        return None
    img = Image.open(path).convert("RGBA")
    if img.size != (SIZE, SIZE):
        img = img.resize((SIZE, SIZE), Image.LANCZOS)
    rgba = np.array(img, dtype=np.uint8)
    rgba[..., 3] = 255
    rgba[..., 0] = rgba[..., 1]
    return rgba


def export_png(name, rgba):
    os.makedirs(EXPORT, exist_ok=True)
    Image.fromarray(rgba[..., :3], "RGB").save(os.path.join(EXPORT, name + ".png"))


# ================================================================== the preview
def read_oct_texture(path):
    """An uncooked .oct texture's RGBA8 texels (the last w * h * 4 bytes)."""
    d = open(path, "rb").read()
    n = struct.unpack_from("<I", d, 21)[0]
    w, h = struct.unpack_from("<II", d, 25 + n)
    return np.frombuffer(d[-w * h * 4:], dtype=np.uint8).reshape(h, w, 4)


class Sampler:
    """Bilinear lookups with a box-filtered mip chain and trilinear blending, wrapping or
    clamping, as the GPU samples a mipmapped texture."""

    def __init__(self, rgba, wrap=True):
        self.wrap = wrap
        level = rgba.astype(np.float64) / 255.0
        self.levels = [level]
        while min(level.shape[:2]) > 1 and wrap:
            h, w = level.shape[:2]
            level = level.reshape(h // 2, 2, w // 2, 2, 4).mean(axis=(1, 3))
            self.levels.append(level)

    def bilinear(self, tex, u, v):
        h, w = tex.shape[:2]
        x, y = u * w - 0.5, v * h - 0.5
        x0, y0 = np.floor(x).astype(np.int64), np.floor(y).astype(np.int64)
        fx, fy = (x - x0)[..., None], (y - y0)[..., None]
        if self.wrap:
            xa, xb, ya, yb = x0 % w, (x0 + 1) % w, y0 % h, (y0 + 1) % h
        else:
            xa, xb = np.clip(x0, 0, w - 1), np.clip(x0 + 1, 0, w - 1)
            ya, yb = np.clip(y0, 0, h - 1), np.clip(y0 + 1, 0, h - 1)
        top = tex[ya, xa] * (1 - fx) + tex[ya, xb] * fx
        bottom = tex[yb, xa] * (1 - fx) + tex[yb, xb] * fx
        return top * (1 - fy) + bottom * fy

    def sample(self, u, v, footprint=None):
        """footprint: texels of level 0 per screen pixel (None: level 0)."""
        if footprint is None or len(self.levels) == 1:
            return self.bilinear(self.levels[0], u, v)
        lod = np.clip(np.log2(np.maximum(footprint, 1e-6)), 0, len(self.levels) - 1)
        out = np.zeros(u.shape + (4,))
        lo = np.floor(lod).astype(int)
        frac = (lod - lo)[..., None]
        for level in range(len(self.levels)):
            pick = (lo == level) | (lo + 1 == level)
            if not pick.any():
                continue
            c = self.bilinear(self.levels[level], u[pick], v[pick])
            weight = np.where((lo[pick] == level)[..., None], 1 - frac[pick], frac[pick])
            out[pick] += c * weight
        return out


def footprint(u, v, size):
    """How many texels one pixel spans, from the coordinates' change to the next pixel."""
    du_y, du_x = np.gradient(u)
    dv_y, dv_x = np.gradient(v)
    fx = np.hypot(du_x, dv_x) * size
    fy = np.hypot(du_y, dv_y) * size
    return np.nan_to_num(np.maximum(fx, fy), nan=1e6)


def camera(t, width, height):
    yaw = math.radians(SWAY_DEGREES) * math.sin(t * 2.0 * math.pi / SWAY_SECONDS)
    lift = math.radians(LIFT_DEGREES)
    eye = np.array([AIM[0] + math.sin(yaw) * math.cos(lift) * DISTANCE, EYE_Y,
                    AIM[2] + math.cos(yaw) * math.cos(lift) * DISTANCE])
    fwd = np.array(AIM) - eye
    fwd /= np.linalg.norm(fwd)
    right = np.cross(fwd, [0.0, 1.0, 0.0])
    right /= np.linalg.norm(right)
    up = np.cross(right, fwd)
    aspect = width / height
    tan_half = (VIEW_WIDTH * 0.5) / aspect / DISTANCE
    return eye, fwd, right, up, tan_half, aspect


def render(t, width, height, tex, average):
    eye, fwd, right, up, tan_half, aspect = camera(t, width, height)
    sx = ((np.arange(width) + 0.5) / width * 2.0 - 1.0) * tan_half * aspect
    sy = (1.0 - (np.arange(height) + 0.5) / height * 2.0) * tan_half
    dirs = fwd[None, None, :] + sx[None, :, None] * right[None, None, :] + sy[:, None, None] * up[None, None, :]
    dirs /= np.linalg.norm(dirs, axis=2, keepdims=True)

    # the sky dome (DaySky.lua, gen_day_sky.py): gradient, clouds decal, haze decal
    dy = dirs[..., 1]
    elev = np.degrees(np.arcsin(np.clip(dy, -1, 1)))
    v1 = np.clip(elev / 90.0, 0.0, 1.0)
    grad = tex["gradient"].sample(np.full_like(v1, 0.5), v1)
    wind = 0.02 * t
    wl = math.hypot(1.0, 0.35)
    cdy = np.maximum(dy, math.sin(math.radians(10.0)))
    cu = dirs[..., 0] / cdy * 0.4 + (wind / wl) % 1.0
    cv = dirs[..., 2] / cdy * 0.4 + (wind * 0.35 / wl) % 1.0
    cloud = tex["clouds"].sample(cu, cv, footprint(cu, cv, 512))
    sky = grad[..., :3] * (1 - cloud[..., 3:]) + cloud[..., :3] * cloud[..., 3:]
    sky = sky * (1 - grad[..., 3:]) + grad[..., :3] * grad[..., 3:]

    # the sea (WaterBed.lua): the disc under the eye, its layers locked to the world
    water_y = WATER_Y + SWELL * math.sin(t * 2.0 * math.pi / SWELL_SECONDS)
    node = (eye[0], eye[2])
    hit = dy < -1e-4
    dist = np.where(hit, (water_y - eye[1]) / np.where(hit, dy, -1.0), np.nan)
    lx = eye[0] + dist * dirs[..., 0] - node[0]
    lz = eye[2] + dist * dirs[..., 2] - node[1]
    reach = np.hypot(lx, lz)
    hit &= reach < RADIUS

    def offsets(tile, drift):
        return (node[0] - drift[0] * t) / tile % 1.0, (node[1] - drift[1] * t) / tile % 1.0

    oa, ob = offsets(TILE_A, DRIFT_A), offsets(TILE_B, DRIFT_B)
    ua, va = lx / TILE_A + oa[0], lz / TILE_A + oa[1]
    ub, vb = lx / TILE_B + ob[0], lz / TILE_B + ob[1]
    fa, fb = footprint(ua, va, SIZE), footprint(ub, vb, SIZE)

    m = hit
    bump = tex["bump"].sample(ub[m], vb[m], fb[m])
    du, dv = (bump[:, 1] - 0.5) * WARP_STRENGTH, (bump[:, 2] - 0.5) * WARP_STRENGTH
    c1 = tex["caustic"].sample(ua[m] + du, va[m] + dv, fa[m])
    c2 = tex["dim"].sample(ub[m] + du, vb[m] + dv, fb[m])
    radii = ring_radii()
    ring_tint = tint(radii, average)
    shade = np.stack([np.interp(reach[m], radii, ring_tint[:, i]) for i in range(3)], axis=1)
    sea = np.clip(colour(BASE)[None, :] + c1[:, :3] + c2[:, :3], 0.0, 1.0) * shade
    alpha = np.interp(reach[m], radii, fade_alpha(radii))[:, None]
    out = sky.copy()
    out[m] = sky[m] * (1 - alpha) + sea * alpha

    img = Image.fromarray(np.clip(np.round(out * 255), 0, 255).astype(np.uint8), "RGB")
    # the emblem's outline at z = 0, for scale
    pts = []
    for x, y in ((EMBLEM[0], EMBLEM[2]), (EMBLEM[1], EMBLEM[2]), (EMBLEM[1], EMBLEM[3]), (EMBLEM[0], EMBLEM[3])):
        p = np.array([x, y, 0.0]) - eye
        z = p @ fwd
        pts.append(((p @ right) / z / (tan_half * aspect) * 0.5 * width + 0.5 * width,
                    0.5 * height - (p @ up) / z / tan_half * 0.5 * height))
    ImageDraw.Draw(img).polygon([(round(x), round(y)) for x, y in pts], outline=(255, 220, 64))
    return img


def preview(caustic, dim, bump, average):
    os.makedirs(EXPORT, exist_ok=True)
    tex = {"caustic": Sampler(caustic), "dim": Sampler(dim), "bump": Sampler(bump),
           "gradient": Sampler(read_oct_texture(SKY_GRADIENT), wrap=False),
           "clouds": Sampler(read_oct_texture(SKY_CLOUDS))}
    t0 = 2.0
    render(t0, 1280, 720, tex, average).save(os.path.join(EXPORT, "water_preview.png"))
    render(t0 + 1.0, 1280, 720, tex, average).save(os.path.join(EXPORT, "water_preview_1s.png"))
    shots = [render(t0 + i / 12.0, 640, 360, tex, average) for i in range(24)]
    shots[0].save(os.path.join(EXPORT, "water_preview.gif"), save_all=True, append_images=shots[1:],
                  duration=83, loop=0)


def main():
    os.makedirs(OUT, exist_ok=True)
    for name in STALE:
        path = os.path.join(OUT, name + ".oct")
        if os.path.exists(path):
            os.remove(path)
    intensity = light_map()
    base = to_rgba(np.tile(colour(BASE)[None, None, :], (8, 8, 1)), 255)
    caustic, dim = added(intensity, LIGHT_GAIN), added(intensity, LIGHT_DIM_GAIN)
    bump = handmade_bump()
    bump = make_bump() if bump is None else bump
    write_texture("T_WaterBase", UUID_BASE, base, hq=True)
    write_texture("T_WaterLight", UUID_LIGHT, caustic, hq=True)
    write_texture("T_WaterLightDim", UUID_LIGHT_DIM, dim, hq=True)
    write_texture("T_WaterBump", UUID_BUMP, bump, hq=True, srgb=False)
    for name, rgba in (("T_WaterBase", base), ("T_WaterLight", caustic),
                       ("T_WaterLightDim", dim), ("T_WaterBump", bump)):
        export_png(name, rgba)
    gen_material("M_Water", UUID_MAT, warp=True)
    gen_material("M_WaterNoWarp", UUID_MAT_NOWARP, warp=False)
    average = np.minimum(1.0, colour(BASE) + intensity.mean() * (LIGHT_GAIN + LIGHT_DIM_GAIN))
    nverts, ntris = gen_mesh(average)
    print("T_WaterBase, T_WaterLight, T_WaterLightDim, T_WaterBump, M_Water, M_WaterNoWarp, "
          "SM_WaterBed -> %s" % OUT)
    print("SM_WaterBed: %d vertices, %d triangles; water's average colour %s"
          % (nverts, ntris, np.round(average * 255).astype(int)))
    preview(caustic, dim, bump, average)
    print("preview -> %s" % EXPORT)


if __name__ == "__main__":
    main()
