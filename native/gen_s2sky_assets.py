#!/usr/bin/env python
"""Sonic 2 special-stage sky: Octave .oct assets.

  T_S2Sky_Gradient.oct   16x256  repeat  vertical band, row 0 = horizon
  T_S2Sky_Stars.oct     256x256  repeat  twinkles, alpha-masked
  T_S2Sky_Diamonds.oct  256x256  repeat  ONE big diamond built from small
                                         diamonds with a drop shadow, tiling
                                         left to right so its points meet its
                                         neighbours'
  M_Sky.oct             same name/uuid as the day sky, so the scene picks it up
  SM_SkyDome.oct        UV0 = (azimuth x diamond repeat, elevation)
                        UV1 = (azimuth x star repeat,    elevation)

Two azimuth repeats because the diamonds want to run side by side around the
horizon while the starfield wants a different, coarser repeat -- sharing one
channel would lock them together and make the star pattern repeat with the
diamonds.

The gradient rides on UV1 as well: it is constant across u, so whatever the
azimuth does to it does not matter.

Palette sampled from the reference screenshot.
"""

import math
import os
import random
import struct

OUT = r"C:\Users\NoSig\Documents\testproj\Sonic2Special3D\proj\Assets"

MAGIC = 0x4F435421
VERSION = 13
TYPE_TEXTURE = 0xCDBBDA30
TYPE_STATICMESH = 0xD41D0D1D
TYPE_MATERIALLITE = 0xA3ED4C6F

UUID_GRAD = 0x51C0FFEE00000010
UUID_MAT = 0x51C0FFEE00000003       # kept: the scene's material
UUID_MESH = 0x51C0FFEE00000004      # kept: the scene's dome
UUID_STARS = 0x51C0FFEE00000020     # + frame index; kept clear of the diamonds
UUID_DIAMONDS = 0x51C0FFEE00000030   # + frame index; clear of the star frames

# --- sampled from the reference -------------------------------------------
SKY_DEEP = (0, 62, 101)
SKY_LIFT = (27, 94, 133)

# The diamonds are a vertical gradient: blue at the top of a cluster running
# down into green at the bottom.
DIAMOND_TOP = (0x1B, 0x5E, 0x85)
DIAMOND_BOTTOM = (0x36, 0xCB, 0x00)

# Each diamond is banded inside rather than filled with one colour, and the
# bands travel downward through it.
#
# Filling a whole diamond with a single colour and changing it per frame only
# makes the sky flicker: every diamond is one flat shape switching between
# colours at once. Bands give the motion somewhere to happen inside the shape,
# so what reads is movement rather than blinking.
DIAMOND_BANDS = 32         # steps the gradient is quantised into

# The animation is a wave travelling down the gradient, not the gradient itself
# sliding.
#
# Sliding it meant the value wrapped: it climbed to the top of the ramp and
# jumped straight back to the bottom, so a hard line of blue-against-green cut
# across the cluster and marched down it. A wave modulates the ramp instead --
# the gradient stays put, blue at the top into green at the bottom, and only
# the ripple moves, so there is nothing to wrap and no seam.
DIAMOND_WAVES = 2.0        # wave cycles across the cluster's height
DIAMOND_WAVE_AMP = 0.16    # how far the wave pushes the gradient

# Frames have to divide the band count, so each one advances the pattern by a
# whole number of bands and the travel is even. Eight into sixteen is two bands
# a frame; six against eight was 1.3 and stuttered.
#
# It does NOT have to be one frame per band, which is what keeps the band count
# free to rise: there is no shader to palette-swap with, so every frame is a
# whole texture, and sixteen of them would be 16MB for the diamonds alone.
DIAMOND_FRAMES = 8
assert DIAMOND_BANDS % DIAMOND_FRAMES == 0, "frames must divide bands evenly"

SHADOW = (0, 38, 66)

# --- layout ---------------------------------------------------------------
# One cluster in the sky, and the texture covers only the cluster.
#
# Spanning the whole 360 degrees with it was the obvious way to stop it tiling
# and it threw away eight ninths of the resolution: 512 pixels across a full
# circle is 1.4 per degree, where the tiling version had 11. The cluster came
# out blocky.
#
# So UV0 maps the cluster's patch of sky onto the whole texture instead, and
# the texture is sampled with Clamp -- outside the patch the edge pixels are
# transparent, so nothing repeats and nothing else is drawn. The 512 pixels all
# go on the cluster.
# Width and height separately, so the cluster can be stretched across without
# growing taller. The texture stays square; the difference between these two is
# what makes the diamonds wider than they are tall.
CLUSTER_DEG_W = 62.0       # how wide the cluster is, in degrees of azimuth
CLUSTER_DEG_H = 56.0       # how tall, in degrees of elevation
CLUSTER_AZ = 180.0         # where it sits around the horizon
CLUSTER_ELEV = 20.0        # and how high

# A margin of empty texture, so clamping outside the patch gives transparency.
CLUSTER_MARGIN = 0.04
STAR_REPEAT = 4.0          # starfield tiles around the horizon

# The twinkle is frames of the star texture, swapped by Sky.lua.
#
# Stars stay at 256 while the diamonds are 512: a star is a pixel or two and
# gains nothing from more, and these are paid for once per frame of animation.
# Four frames at 256 is 1MB; four at 512 would be 4MB for no visible gain.
STAR_FRAMES = 4

# 512 as well. At 256 a sparkle was about seven pixels across at its largest,
# which is not enough room for a core, a tapering arm and corners -- the detail
# had nowhere to go. Four frames at 512 is 4MB rather than 1MB; that is the
# cost of the twinkle being frames.
STAR_TEX = 512
STAR_SCALE = STAR_TEX // 256

# 512, not 256. One diamond tile covers an eighth of the dome and one star tile
# a third, so these are magnified a long way on screen and 256 read as soft.
# Everything drawn into them is sized from SCALE, so the artwork keeps its
# proportions rather than getting finer as the texture grows.
TEX = 512
SCALE = TEX // 256

# The cluster has to stay clear of v = 0.
#
# The dome's lowest ring is at -10 degrees and v is clamped at 0, so every
# vertex from there up to the horizon samples the texture's bottom row. Anything
# sitting in that row gets smeared down the whole skirt -- which is what the
# stretched diamonds along the bottom were.
# The cluster is sized so its diamonds come out square, and then repeated up
# the dome to fill it -- rather than one cluster stretched from the horizon to
# the zenith, which made every diamond far taller than it was wide.
#
# One cluster spans 360/DIAMOND_REPEAT degrees of azimuth across 5 cells, so a
# cell is 12 degrees wide at 6 around. Matching that vertically wants a cluster
# 60 degrees tall, which is 0.60 in v, so HALF_H is 0.30.
HALF_W = TEX // 2          # half the tile: points land on the tile edges
HALF_H = int(0.30 * TEX)

# Rows below this are forced empty, so nothing can reach the clamped row even
# if the numbers above are changed later.
SKIRT_CLEAR_V = 0.12
SHADOW_OFF = 3 * SCALE
# Rows of 1, 3, 5, 3, 1 -- every cell with |i| + |j| <= RADIUS, which is a
# diamond of diamonds, 13 of them.
CLUSTER_RADIUS = 2         # renamed: the dome's own RADIUS is defined below
GAP = 0.13                 # fraction of a cell left empty, so each one reads


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


def mixc(a, b, t):
    return tuple(int(round(a[i] + (b[i] - a[i]) * t)) for i in range(3))


def write_texture(path, name, uuid, w, h, pixels, wrap, srgb=True):
    d = header(TYPE_TEXTURE, uuid, name)
    d += u32(w) + u32(h) + u32(1) + u32(1)
    d += u32(2) + u32(1) + u32(wrap)             # RGBA8, Linear, wrap
    d += u8(0) + u8(0) + u8(1 if srgb else 0)
    d += u8(0) + u8(1)
    assert len(pixels) == w * h * 4, (len(pixels), w * h * 4)
    d += bytes(pixels)
    with open(path, "wb") as f:
        f.write(d)
    print("wrote %s (%d bytes)" % (os.path.basename(path), len(d)))


# ------------------------------------------------------------------ pixels
def gen_gradient(w=16, h=256):
    """Row 0 is the lowest ring of the dome, row h-1 the zenith.

    The ramp is anchored to the horizon rather than to the bottom of the
    texture, because the horizon is no longer at row 0 -- the skirt below it
    has its own rows now.
    """
    px = bytearray()

    for row in range(h):
        v = row / (h - 1.0)

        if v <= HORIZON_V:
            # Below the horizon. Nothing of the sky is meant to show here, but
            # it must not be a different colour from the horizon either, or the
            # join reads as a hard line.
            c = SKY_LIFT
        else:
            k = (v - HORIZON_V) / 0.50
            c = SKY_DEEP if k >= 1.0 else mixc(SKY_LIFT, SKY_DEEP, smoothstep(0.0, 1.0, k))

        px += bytes((c[0], c[1], c[2], 255)) * w

    return w, h, px


# Stars per side of the jittered grid. 20 gives 400 cells, less the ones
# dropped, so roughly 370 stars.
STAR_GRID = 20
STAR_DROP = 0.08


def star_field(seed=20992, size=STAR_TEX):
    """The star positions, chosen once so every frame twinkles the same stars.

    Placed one per cell of a grid, jittered inside it, rather than at uniformly
    random points.

    Uniform random positions clump: over a few hundred stars some patches come
    out crowded and others empty, and since this tile repeats four times around
    the dome every void repeats with it -- which showed up as one side of the
    sky being noticeably barer than the other. A jittered grid keeps them
    evenly spread and still looks scattered rather than laid out.

    Cells are dropped at random so the grid never shows through as rows.
    """
    rng = random.Random(seed)
    field = []

    cell = size / float(STAR_GRID)

    for gy in range(STAR_GRID):
        for gx in range(STAR_GRID):
            if rng.random() < STAR_DROP:
                continue

            x = int((gx + rng.random()) * cell) % size
            y = int((gy + rng.random()) * cell) % size

            roll = rng.random()

            # Mostly small. A sky of nothing but big sparkles reads as glitter.
            if roll < 0.40:
                arms = 0        # a plain point of light
            elif roll < 0.74:
                arms = 1
            elif roll < 0.93:
                arms = 2
            else:
                arms = 3        # the few big ones

            field.append({
                "x": x,
                "y": y,
                "arms": arms,
                "phase": rng.random(),
            })

    return field


def gen_stars_frame(field, frame, frames=STAR_FRAMES, size=STAR_TEX):
    """One frame of the twinkle.

    A sparkle is a white core, four arms stepping down in brightness toward
    their tips, and diagonals filling the corners so it reads as a star rather
    than a plus sign. Arm length and corner reach scale with STAR_SCALE, so the
    shape keeps its proportions at any texture size.

    The steps stay bright on purpose. An earlier version faded the arms smoothly
    toward nothing, and a dimmed white pixel on this blue is not a faint star,
    it is a grey-brown one -- the whole field went muddy. The twinkle is the
    arms changing length, not the star changing brightness.
    """
    px = bytearray(size * size * 4)

    def put(x, y, v, b=0):
        o = ((y % size) * size + (x % size)) * 4
        if v <= px[o]:
            return                      # brightest wins; stars must not erase each other
        px[o] = v
        px[o + 1] = v
        px[o + 2] = min(255, v + b)     # a touch of blue toward the tips
        px[o + 3] = 255

    # Brightness down the length of an arm, sampled by how far along it is.
    ARM = (250, 240, 226, 206, 180, 150)

    for st in field:
        t = ((frame / float(frames)) + st["phase"]) % 1.0
        pulse = 0.5 + 0.5 * math.cos(2.0 * math.pi * t)

        x, y = st["x"], st["y"]

        span = st["arms"] * STAR_SCALE          # full arm length at its peak
        reach = int(round(span * pulse))

        # Core: a single pixel for the small ones, a solid block for the big.
        core = max(1, (st["arms"] * STAR_SCALE) // 3)
        for oy in range(core):
            for ox in range(core):
                put(x + ox - core // 2, y + oy - core // 2, 255)

        for k in range(1, reach + 1):
            step = int((k - 1) * len(ARM) / float(max(span, 1)))
            v = ARM[min(step, len(ARM) - 1)]
            for dx, dy in ((k, 0), (-k, 0), (0, k), (0, -k)):
                put(x + dx, y + dy, v, b=16)

        # The corners, which are what turn a plus into a star. Only once the
        # arms are more than half out.
        if st["arms"] >= 2 and reach > span * 0.5:
            cr = max(1, reach // 3)
            for k in range(1, cr + 1):
                v = 170 - 30 * (k - 1)
                if v < 60:
                    break
                for dx, dy in ((k, k), (k, -k), (-k, k), (-k, -k)):
                    put(x + dx, y + dy, v, b=36)

        # A fainter shoulder between arm and corner, on the largest only.
        if st["arms"] >= 3 and reach > span * 0.7:
            k = max(1, reach // 3)
            for dx, dy in ((2 * k, k), (k, 2 * k), (-2 * k, k), (-k, 2 * k),
                           (2 * k, -k), (k, -2 * k), (-2 * k, -k), (-k, -2 * k)):
                put(x + dx, y + dy, 96, b=44)

    return size, size, px


# One cluster per tile across, and clusters repeated up the dome.
#
# They are deliberately NOT tessellated. A 13-cell diamond does tile the plane
# exactly -- every cell belonging to a cluster, none left over -- and that was
# tried: it fills the dome and destroys the whole point, because with no sky
# between them the clusters stop reading as clusters and it becomes a field of
# loose diamonds. The gaps are what make a big diamond visible.
CELLS_ACROSS = 5           # one cluster wide

# One row, sitting on the horizon. Stacking them up the dome filled it but read
# as wallpaper; a single band with open starfield above it is both closer to
# the reference and the thing that looked right.
CLUSTER_ROWS = 1
ROW_SPACING = 5            # cells between rows, if there is ever more than one
ROW_OFFSET = 2             # cells that alternate rows are shifted by


def gen_diamonds(frame=0, size=TEX):
    """The cluster, drawn to fill the texture.

    The texture IS the cluster's patch of sky, so this is drawn in cluster
    space: 5 cells across and 5 down, square, centred, with a small transparent
    margin for Clamp to sample outside the patch.
    """
    usable = size * (1.0 - 2.0 * CLUSTER_MARGIN)
    step = usable / float(2 * CLUSTER_RADIUS + 1)

    hw = (step * 0.5) * (1.0 - GAP)
    hh = hw

    cx = cy = size * 0.5

    colour = [[None] * size for _ in range(size)]

    # Top to bottom of the cluster, for the gradient to run across.
    cluster_span = 2.0 * (CLUSTER_RADIUS * step + hh)

    for dj in range(-CLUSTER_RADIUS, CLUSTER_RADIUS + 1):
        for di in range(-CLUSTER_RADIUS, CLUSTER_RADIUS + 1):
            if abs(di) + abs(dj) > CLUSTER_RADIUS:
                continue

            dcx = cx + di * step
            dcy = cy + dj * step

            x0 = max(0, int(math.floor(dcx - hw)))
            x1 = min(size - 1, int(math.ceil(dcx + hw)))
            y0 = max(0, int(math.floor(dcy - hh)))
            y1 = min(size - 1, int(math.ceil(dcy + hh)))

            for y in range(y0, y1 + 1):
                for x in range(x0, x1 + 1):
                    if abs(x - dcx) / hw + abs(y - dcy) / hh > 1.0:
                        continue

                    # Where the pixel sits up the CLUSTER, not up its own
                    # diamond: one gradient runs through the whole group, so a
                    # band crosses several diamonds. Per-diamond, the ramp
                    # restarted in every cell and the cluster read as a set of
                    # separately shaded pieces rather than one shape being lit.
                    ty = (y - cy) / cluster_span + 0.5

                    wave = math.sin(2.0 * math.pi *
                                    (ty * DIAMOND_WAVES +
                                     frame / float(DIAMOND_FRAMES)))
                    shade = min(1.0, max(0.0, ty + DIAMOND_WAVE_AMP * wave))

                    step_i = int(shade * (DIAMOND_BANDS - 1)) / float(DIAMOND_BANDS - 1)

                    colour[y][x] = mixc(DIAMOND_BOTTOM, DIAMOND_TOP, step_i)

    px = bytearray(size * size * 4)

    def put(x, y, c, a):
        if not (0 <= x < size and 0 <= y < size):
            return
        o = (y * size + x) * 4
        px[o], px[o + 1], px[o + 2], px[o + 3] = c[0], c[1], c[2], a

    # Shadow first, and only where no diamond will land on top of it.
    #
    # Down the screen means toward the horizon, and v climbs to the zenith, so
    # the shadow steps to a lower row.
    for y in range(size):
        for x in range(size):
            if colour[y][x] is None:
                continue
            sy = y - SHADOW_OFF
            sx = x + SHADOW_OFF
            if 0 <= sy < size and 0 <= sx < size and colour[sy][sx] is None:
                put(sx, sy, SHADOW, 255)

    for y in range(size):
        for x in range(size):
            c = colour[y][x]
            if c is not None:
                put(x, y, c, 255)

    return size, size, px


# ---------------------------------------------------------------- material
def gen_material(path):
    d = header(TYPE_MATERIALLITE, UUID_MAT, "M_Sky")
    d += u32(0)                     # numParameters
    d += u32(0)                     # Unlit
    d += u32(0)                     # Opaque
    d += u32(1)                     # VertexColorMode::Modulate
    d += u32(3)                     # numTextures
    # 0: gradient on uv1, Replace -- constant across u, so the repeat is moot
    d += asset_ref(UUID_GRAD, "T_S2Sky_Gradient") + u8(1) + u8(0)
    # 1: stars on uv1, Decal
    d += asset_ref(UUID_STARS, "T_S2Sky_Stars_1") + u8(1) + u8(2)
    # 2: diamonds on uv0, Decal -- last, so the cluster sits over the stars
    d += asset_ref(UUID_DIAMONDS, "T_S2Sky_Diamonds_1") + u8(0) + u8(2)
    d += null_ref() + u8(0) + u8(1)
    for _ in range(2):
        d += f32(0) + f32(0) + f32(1) + f32(1)
    d += f32(1) + f32(1) + f32(1) + f32(1)
    d += f32(1) + f32(0) + f32(0) + f32(0)
    d += f32(1.0)       # fresnelPower
    d += f32(0.0)       # emission
    d += f32(0.0)       # wrapLighting
    d += f32(0.0)       # specular
    d += u32(2)         # toonSteps
    d += f32(1.0)       # opacity
    d += f32(0.5)       # maskCutoff
    d += f32(32.0)      # shininess
    d += i32(0)         # sortPriority
    d += u8(0)          # disableDepthTest
    d += u8(0)          # fresnelEnabled
    d += u8(0)          # applyFog: off for sky
    d += u8(0)          # CullMode::None
    with open(path, "wb") as f:
        f.write(d)
    print("wrote %s (%d bytes)" % (os.path.basename(path), len(d)))


# -------------------------------------------------------------------- mesh
RADIUS = 900.0
SEGMENTS = 64      # doubled: the diamonds show faceting at 32
ELEVATIONS = [-10.0, 0.0, 4.0, 9.0, 15.0, 22.0, 30.0, 40.0, 52.0, 66.0, 80.0]

# The whole dome gets texture, skirt included.
#
# v used to be max(0, elev/90), so every vertex from the lowest ring at -10
# degrees up to the horizon shared v = 0 and sampled one row of the texture,
# stretched down the entire skirt. Clearing that row only changed what was
# smeared; the stretch was the mapping. Spanning the real elevation range
# instead gives the skirt its own rows and there is nothing left to stretch.
ELEV_MIN = ELEVATIONS[0]
ELEV_MAX = 90.0


def elev_to_v(elev):
    return (elev - ELEV_MIN) / (ELEV_MAX - ELEV_MIN)


# Where the horizon now sits in texture space.
HORIZON_V = (0.0 - ELEV_MIN) / (ELEV_MAX - ELEV_MIN)


def gen_mesh(path):
    verts = []
    for elev in ELEVATIONS:
        er = math.radians(elev)
        cy, sy_ = math.cos(er), math.sin(er)
        v = elev_to_v(elev)

        for seg in range(SEGMENTS + 1):     # seam column duplicated
            az = seg / SEGMENTS
            ar = az * 2.0 * math.pi
            dx = math.cos(ar) * cy
            dz = math.sin(ar) * cy
            dy = sy_

            # UV0 maps the cluster's patch of sky across the whole texture.
            #
            # az runs 0..1 over the ring and is NOT wrapped back, so u0 climbs
            # monotonically from about -2.1 to 3.1 and crosses 0..1 exactly
            # once -- where the cluster is. Wrapping the azimuth into
            # [-180,180] instead would make u0 jump at the seam, and the
            # triangle spanning that jump would sweep the whole texture across
            # itself and draw a smeared second cluster there.
            u0 = ((az * 360.0) - CLUSTER_AZ) / CLUSTER_DEG_W + 0.5
            v0 = (elev - CLUSTER_ELEV) / CLUSTER_DEG_H + 0.5

            u1 = az * STAR_REPEAT

            verts.append((dx * RADIUS, dy * RADIUS, dz * RADIUS,
                          u0, v0, u1, v, -dx, -dy, -dz))

    pole_index = len(verts)
    # The pole. Its UV0 is pushed well outside the cluster patch so the cap
    # samples the transparent margin rather than stretching the cluster to it.
    pole_v0 = (90.0 - CLUSTER_ELEV) / CLUSTER_DEG_H + 0.5
    verts.append((0.0, RADIUS, 0.0, 0.5, pole_v0, 0.0, 1.0, 0.0, -1.0, 0.0))

    idx = []
    cols = SEGMENTS + 1
    for ring in range(len(ELEVATIONS) - 1):
        for seg_i in range(SEGMENTS):
            a = ring * cols + seg_i
            b = a + 1
            c = a + cols
            dd = c + 1
            idx += [a, b, c, b, dd, c]     # inward-facing

    top = (len(ELEVATIONS) - 1) * cols
    for seg_i in range(SEGMENTS):
        idx += [top + seg_i, top + seg_i + 1, pole_index]

    d = header(TYPE_STATICMESH, UUID_MESH, "SM_SkyDome")
    d += u32(len(verts)) + u32(len(idx)) + u32(2)
    d += asset_ref(UUID_MAT, "M_Sky")
    d += u8(0) + u8(0)
    for v in verts:
        d += b"".join(f32(c) for c in v)
    for ii in idx:
        d += u32(ii)
    d += u8(0)
    d += u32(0)
    d += f32(0) + f32(0) + f32(0) + f32(0)
    with open(path, "wb") as f:
        f.write(d)
    print("wrote %s (%d verts, %d indices, %d bytes)"
          % (os.path.basename(path), len(verts), len(idx), len(d)))


def main():
    tex = os.path.join(OUT, "Textures")
    mat = os.path.join(OUT, "Materials")
    mesh = os.path.join(OUT, "Meshes")
    for p in (tex, mat, mesh):
        os.makedirs(p, exist_ok=True)

    w, h, px = gen_gradient()
    write_texture(os.path.join(tex, "T_S2Sky_Gradient.oct"), "T_S2Sky_Gradient",
                  UUID_GRAD, w, h, px, wrap=1)

    field = star_field()
    for f in range(STAR_FRAMES):
        w, h, px = gen_stars_frame(field, f)
        name = "T_S2Sky_Stars_%d" % (f + 1)
        write_texture(os.path.join(tex, name + ".oct"), name,
                      UUID_STARS + f, w, h, px, wrap=1)

    for f in range(DIAMOND_FRAMES):
        w, h, px = gen_diamonds(f)
        name = "T_S2Sky_Diamonds_%d" % (f + 1)
        write_texture(os.path.join(tex, name + ".oct"), name,
                      UUID_DIAMONDS + f, w, h, px, wrap=0)      # Clamp

    gen_material(os.path.join(mat, "M_Sky.oct"))
    gen_mesh(os.path.join(mesh, "SM_SkyDome.oct"))


if __name__ == "__main__":
    main()
