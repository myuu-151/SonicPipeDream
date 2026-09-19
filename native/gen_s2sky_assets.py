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
DIAMOND_BANDS = 8          # bands across one diamond's height

# One frame per band, so each frame advances the pattern exactly one band and
# the travel is even. Six frames against eight bands moved 1.3 bands a frame,
# which stutters.
#
# Frames because there is no shader to palette-swap with: every variation costs
# a whole texture. Fewer frames is a coarser flow, not a shorter one.
DIAMOND_FRAMES = DIAMOND_BANDS

SHADOW = (0, 38, 66)

# --- layout ---------------------------------------------------------------
# Clusters around the horizon. A cluster is 5 cells wide, so a cell covers
# (360/DIAMOND_REPEAT)/5 degrees, and the vertical step is derived from that to
# keep cells square. Lower means bigger diamonds.
DIAMOND_REPEAT = 8.0
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
    """Diamond clusters over the dome: each a 1/3/5/3/1 diamond of small
    diamonds with a drop shadow, separated by sky, repeating across and up.

    Tiles horizontally because a tile is exactly one cluster wide, so each
    cluster's outer tips land on the tile edges and meet its neighbours'.
    """
    step_x = size / float(CELLS_ACROSS)

    # Square cells: a cell has to cover as many degrees up as across. One tile
    # spans 360/DIAMOND_REPEAT of azimuth; the texture spans the dome's whole
    # elevation range.
    deg_across = (360.0 / DIAMOND_REPEAT) / CELLS_ACROSS
    step_y = size * (deg_across / (ELEV_MAX - ELEV_MIN))

    hw = (step_x * 0.5) * (1.0 - GAP)
    hh = (step_y * 0.5) * (1.0 - GAP)

    colour = [[None] * size for _ in range(size)]

    # Start high enough that the lowest row of clusters clears the skirt band
    # completely: its bottom cell reaches a further half-cell below its centre,
    # and without that the row came out with its lowest diamond sliced flat.
    first = SKIRT_CLEAR_V * size + CLUSTER_RADIUS * step_y + hh + 2
    n_rows = CLUSTER_ROWS

    for n in range(n_rows):
        cy = first + n * ROW_SPACING * step_y
        cx = size * 0.5 + (ROW_OFFSET * step_x if (n % 2) else 0.0)

        for dj in range(-CLUSTER_RADIUS, CLUSTER_RADIUS + 1):
            for di in range(-CLUSTER_RADIUS, CLUSTER_RADIUS + 1):
                if abs(di) + abs(dj) > CLUSTER_RADIUS:
                    continue

                dcx = cx + di * step_x
                dcy = cy + dj * step_y

                x0 = int(math.floor(dcx - hw))
                x1 = int(math.ceil(dcx + hw))
                y0 = max(0, int(math.floor(dcy - hh)))
                y1 = min(size - 1, int(math.ceil(dcy + hh)))

                for y in range(y0, y1 + 1):
                    for x in range(x0, x1 + 1):
                        if abs(x - dcx) / hw + abs(y - dcy) / hh > 1.0:
                            continue

                        # Where the pixel sits up the diamond: 0 at its bottom
                        # point, 1 at its top.
                        ty = (y - dcy) / (2.0 * hh) + 0.5

                        # Bands down the diamond, travelling toward its bottom
                        # as the frame advances. y climbs toward the zenith, so
                        # adding the phase sends them down the screen.
                        band = (ty + frame / float(DIAMOND_FRAMES)) % 1.0
                        step = int(band * DIAMOND_BANDS) / float(DIAMOND_BANDS - 1)

                        colour[y][x % size] = mixc(DIAMOND_BOTTOM, DIAMOND_TOP,
                                                   min(step, 1.0))

    # Nothing in the bottom band: the dome's skirt samples down there and would
    # draw whatever it found into a streak.
    for y in range(min(int(SKIRT_CLEAR_V * size), size)):
        for x in range(size):
            colour[y][x] = None

    px = bytearray(size * size * 4)

    def put(x, y, c, a):
        o = ((y % size) * size + (x % size)) * 4
        px[o], px[o + 1], px[o + 2], px[o + 3] = c[0], c[1], c[2], a

    # Shadow first, and only where no diamond will land on top of it.
    #
    # Down the screen means toward the horizon, and row 0 IS the horizon -- v
    # climbs to the zenith. So the shadow steps to a lower row, not a higher
    # one; offsetting the other way hung it above the diamond.
    for y in range(size):
        for x in range(size):
            if colour[y][x] is None:
                continue
            sy = y - SHADOW_OFF
            sx = (x + SHADOW_OFF) % size
            if sy >= 0 and colour[sy][sx] is None:
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

            u0 = az * DIAMOND_REPEAT
            u1 = az * STAR_REPEAT

            verts.append((dx * RADIUS, dy * RADIUS, dz * RADIUS,
                          u0, v, u1, v, -dx, -dy, -dz))

    pole_index = len(verts)
    verts.append((0.0, RADIUS, 0.0, 0.0, 1.0, 0.0, 1.0, 0.0, -1.0, 0.0))

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
                      UUID_DIAMONDS + f, w, h, px, wrap=1)

    gen_material(os.path.join(mat, "M_Sky.oct"))
    gen_mesh(os.path.join(mesh, "SM_SkyDome.oct"))


if __name__ == "__main__":
    main()
