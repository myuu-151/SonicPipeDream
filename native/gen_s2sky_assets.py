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

# The dome's elevation range. Declared up here because sizes elsewhere are
# derived from it -- how many pixels a degree gets, and therefore how big a
# star should be drawn.
ELEV_MIN = -90.0
ELEV_MAX = 90.0

# --- sampled from the reference -------------------------------------------
SKY_DEEP = (0, 62, 101)
SKY_LIFT = (27, 94, 133)

# How far from the horizon the sky takes to reach its deepest, in degrees.
GRADIENT_RAMP_DEG = 50.0

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

# The gradient is mirrored -- blue into green and back into blue -- and slides
# downward through the cluster.
#
# Mirroring is what lets it slide at all. A plain blue-to-green ramp does not
# meet itself at the ends, so sliding it wrapped: the value climbed to the top
# and dropped straight back to the bottom, putting a hard line of blue against
# green across the cluster that marched down with it. A mirrored ramp arrives
# back where it started, so it slides continuously and the green band simply
# travels from the top of the cluster to the bottom.

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
CLUSTER_DEG_W = 56.0       # how wide the cluster is, in degrees of azimuth
CLUSTER_DEG_H = 56.0       # how tall, in degrees of elevation
# How many clusters go around the horizon, spaced apart.
#
# The tile is 360/CLUSTER_COUNT degrees wide and the cluster takes CLUSTER_DEG_W
# of it; the rest is the gap. It has to divide 360 exactly or the wrap lands
# mid-cluster.
CLUSTER_COUNT = 5
# Centred on the horizon, which is the sphere's equator -- the band sits
# across the middle rather than up in the top half.
CLUSTER_ELEV = 5.0

# The elevation band the texture covers, a little taller than the cluster.
#
# It used to span the dome's whole -10..90, which put 44 per cent of the
# texture's height on empty sky the cluster never reaches -- resolution spent
# on nothing. Covering only the band the cluster occupies, and clamping v at
# the vertices so it never leaves 0..1, gives all of it to the diamonds.
# The margin is what clamping samples outside the band, so it must be empty.
CLUSTER_V_MARGIN = 5.0

# A margin of empty texture, so clamping outside the patch gives transparency.
CLUSTER_MARGIN = 0.04
# Two around, so one tile spans 180 degrees of azimuth -- the same 180 the
# sphere spans vertically. A square tile, which is what lets the texture be
# square without stretching the sprites.
STAR_REPEAT = 2.0

# One copy up the sphere, NOT two.
#
# Tiling vertically doubled the stars' pixels per degree for free, and broke
# the sky: UV1 carries the gradient as well as the stars, so scaling its v for
# the star tiling scaled the gradient with it and the gradient wrapped twice up
# the dome. Two layers on one channel cannot have different mappings.
#
# The sharpness comes from resolution instead.
STAR_V_REPEAT = 1.0

# The twinkle is frames of the star texture, swapped by Sky.lua.
#
# Stars stay at 256 while the diamonds are 512: a star is a pixel or two and
# gains nothing from more, and these are paid for once per frame of animation.
# Four frames at 256 is 1MB; four at 512 would be 4MB for no visible gain.
# Sixteen.
#
# Worth having now that the arm tips fade in fractionally: before that the arm
# length was whole pixels, so a six pixel arm had seven states and extra frames
# only repeated the same jumps. With fractional tips every frame is a distinct
# state, so the count is what the smoothness actually costs.
#
# Sixteen frames at 512 is 16MB of RGBA8, which is most of what the sky costs
# in the editor. On a GameCube these would cook to CMPR -- an eighth of that,
# 2MB -- and stars suit it: they are white on transparent, which is exactly the
# one bit of alpha CMPR carries.
STAR_FRAMES = 8

# 512 as well. At 256 a sparkle was about seven pixels across at its largest,
# which is not enough room for a core, a tapering arm and corners -- the detail
# had nowhere to go. Four frames at 512 is 4MB rather than 1MB; that is the
# cost of the twinkle being frames.
# 1024 now that the sphere is closed: the texture spans 180 degrees of
# elevation rather than 100, so at 512 it had dropped from 5.1 pixels per
# degree to 2.8.
# 512, with the texture tiled twice up the sphere.
#
# The sprite is hand-tuned at two pixels a step, and that is the look that was
# signed off -- so the job is to give it the pixels per degree it was drawn
# against, not the most possible. The hemisphere gave it 512 over 100 degrees,
# 5.1 per degree; a closed sphere spans 180, so one copy at 512 would be 2.8
# and the sprite would be drawn at half the density it expects. Two copies
# bring it back to 5.7.
# Not square, because the tile it covers is not square.
#
# One tile spans 360/STAR_REPEAT degrees across and the sphere's whole 180 up.
# A square texture over that gives twice as many pixels per degree across as up
# -- so a star drawn as a round shape in pixels comes out stretched 2:1 on the
# dome. Sizing the texture to the tile's own proportions makes a pixel cover
# the same angle either way, which is what keeps the sprite round.
STAR_TEX_W = 1024
STAR_TEX_H = 1024
STAR_TEX = STAR_TEX_W                      # kept for the sprite's own maths

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


def write_texture(path, name, uuid, w, h, pixels, wrap, srgb=True, force_hq=False):
    """force_hq exempts a texture from the project's low-quality cook.

    On GameCube the project cooks textures to CMPR, which is block compression
    with one bit of alpha. Stars and diamonds suit it -- both are solid colour
    on transparency -- but a smooth gradient does not: 4x4 blocks of a slow ramp
    band badly, and this one is 16x256, so keeping it uncompressed costs 16KB.
    """
    d = header(TYPE_TEXTURE, uuid, name)
    d += u32(w) + u32(h) + u32(1) + u32(1)
    d += u32(2) + u32(1) + u32(wrap)             # RGBA8, Linear, wrap
    d += u8(0) + u8(0) + u8(1 if srgb else 0)
    d += u8(1 if force_hq else 0) + u8(1)
    assert len(pixels) == w * h * 4, (len(pixels), w * h * 4)
    d += bytes(pixels)
    with open(path, "wb") as f:
        f.write(d)
    print("wrote %s (%d bytes)" % (os.path.basename(path), len(d)))


# ------------------------------------------------------------------ pixels
def gen_gradient(w=256, h=256):
    """Row 0 is the lowest ring of the dome, row h-1 the zenith.

    The ramp is anchored to the horizon rather than to the bottom of the
    texture, because the horizon is no longer at row 0 -- the skirt below it
    has its own rows now.
    """
    px = bytearray()

    for row in range(h):
        v = row / (h - 1.0)

        # The ramp is mirrored about the horizon: pale there, deepening toward
        # both the zenith and the nadir. The sphere is closed now, so below the
        # horizon is as visible as above it and holding one flat colour down
        # there would read as a lid.
        #
        # Measured in degrees of elevation, not as a fraction of the texture.
        # It was half the texture's height, which was 50 degrees while the dome
        # was a hemisphere and silently became 90 when the sphere closed -- so
        # the darkening took nearly twice as far to arrive and the sky stayed
        # pale where it used to be deep.
        elev = ELEV_MIN + v * (ELEV_MAX - ELEV_MIN)
        k = abs(elev) / GRADIENT_RAMP_DEG
        c = SKY_DEEP if k >= 1.0 else mixc(SKY_LIFT, SKY_DEEP, smoothstep(0.0, 1.0, k))

        px += bytes((c[0], c[1], c[2], 255)) * w

    return w, h, px


# Stars per side of the jittered grid. 20 gives 400 cells, less the ones
# dropped, so roughly 370 stars.
# Cells across and up. Twice as many up, because the tile is twice as tall as
# it is wide -- an even grid on an uneven tile bunches the stars in one axis.
#
# The pair also has to track the tile's area or the density moves under you:
# dropping the vertical tiling doubled that area, and leaving the grid alone
# halved the density.
STAR_GRID_X = 53
STAR_GRID_Y = 53
STAR_DROP = 0.08


# Sprite size, worked out from how many pixels a degree gets rather than from
# the texture's size.
#
# It used to be STAR_TEX // 256, which quietly meant "bigger texture, bigger
# stars" -- fine while the texture always covered the same sky, wrong the
# moment the span changed. Tied to pixels per degree, a star keeps its apparent
# size whatever the resolution or the span.
# Two pixels a step, fixed rather than derived.
#
# The sprite is built out of whole pixels -- a core, arm steps, corner dots --
# and only holds its shape at the size it was tuned at. Deriving this from the
# resolution is what gave it a fat square core and speckled corners at five.
STAR_SCALE = 2
STAR_PX_PER_DEG = STAR_TEX / ((ELEV_MAX - ELEV_MIN) / STAR_V_REPEAT)


def star_field(seed=20992):
    """The star positions, chosen once so every frame twinkles the same stars.

    Placed one per cell of a jittered grid rather than at uniformly random
    points. Random positions clump: over a few hundred stars some patches come
    out crowded and others empty, and since the tile repeats around the dome
    every void repeats with it -- which showed up as one side of the sky being
    noticeably barer than the other.

    Cells are dropped at random so the grid never shows through as rows.
    """
    rng = random.Random(seed)
    field = []

    cell_w = STAR_TEX_W / float(STAR_GRID_X)
    cell_h = STAR_TEX_H / float(STAR_GRID_Y)

    for gy in range(STAR_GRID_Y):
        for gx in range(STAR_GRID_X):
            if rng.random() < STAR_DROP:
                continue

            x = int((gx + rng.random()) * cell_w) % STAR_TEX_W
            y = int((gy + rng.random()) * cell_h) % STAR_TEX_H

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


def gen_stars_frame(field, frame, frames=STAR_FRAMES, w=STAR_TEX_W, h=STAR_TEX_H):
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
    px = bytearray(w * h * 4)

    # The sky gradient is painted in as the background, so this layer is opaque.
    #
    # It used to be its own texture on its own tev stage. That cost a stage and,
    # worse, made this layer a cutout -- and cutouts cannot be trusted on this
    # hardware, because gxtexconv's CMPR throws alpha away. Baking the two
    # together makes the layer solid, which CMPR handles perfectly, and drops
    # the material from three textures to two.
    #
    # They combine cleanly because the gradient varies only with elevation and
    # this texture's v IS elevation; its horizontal tiling does not disturb it.
    for y in range(h):
        elev = ELEV_MIN + (y / float(h - 1)) * (ELEV_MAX - ELEV_MIN)
        k = abs(elev) / GRADIENT_RAMP_DEG
        c = SKY_DEEP if k >= 1.0 else mixc(SKY_LIFT, SKY_DEEP, smoothstep(0.0, 1.0, k))

        row = bytes((c[0], c[1], c[2], 255)) * w
        px[y * w * 4:(y + 1) * w * 4] = row

    def put(x, y, v, b=0):
        o = ((y % h) * w + (x % w)) * 4
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

        # Fractional, so an arm can be part way into its next pixel.
        #
        # Rounding it meant the arm only ever had a whole number of pixels, and
        # at six long that is seven states the twinkle can be in -- so a star
        # jumped two pixels at a time and more frames simply repeated the same
        # jumps. The tip pixel is now faded in by how far the arm has grown
        # into it, which is what makes the glint smooth rather than stepped.
        exact = span * pulse
        reach = int(exact)
        frac = exact - reach

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

        # The tip, part way in. Held well above nothing even at its faintest --
        # a dim white pixel on this blue is a grey-brown one, and a whole
        # field of half-lit tips is what turned the stars muddy before.
        if reach < span and frac > 0.12:
            step = int(reach * len(ARM) / float(max(span, 1)))
            v = int(ARM[min(step, len(ARM) - 1)] * (0.45 + 0.55 * frac))
            k = reach + 1
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

    return w, h, px


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
    """One cluster in a tile, with sky either side of it.

    The tile is 360/CLUSTER_COUNT degrees across and the texture spans the
    dome's whole elevation range, so the cluster is placed at its own size and
    height within that and the rest is left transparent -- the gap between
    clusters is simply the empty part of the tile.
    """
    tile_deg = 360.0 / CLUSTER_COUNT
    span = 2 * CLUSTER_RADIUS + 1

    step_x = size * (CLUSTER_DEG_W / tile_deg) / float(span)
    step_y = size * (CLUSTER_DEG_H / (V_HI - V_LO)) / float(span)

    hw = (step_x * 0.5) * (1.0 - GAP)
    hh = (step_y * 0.5) * (1.0 - GAP)

    cx = size * 0.5
    cy = ((CLUSTER_ELEV - V_LO) / (V_HI - V_LO)) * (size - 1)

    colour = [[None] * size for _ in range(size)]

    # Top to bottom of the cluster, for the gradient to run across.
    cluster_span = 2.0 * (CLUSTER_RADIUS * step_y + hh)

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

                    # Where the pixel sits up the CLUSTER, not up its own
                    # diamond: one gradient runs through the whole group, so a
                    # band crosses several diamonds. Per-diamond, the ramp
                    # restarted in every cell and the cluster read as a set of
                    # separately shaded pieces rather than one shape being lit.
                    ty = (y - cy) / cluster_span + 0.5

                    # ty is 0 at the bottom of the cluster and 1 at the top, so
                    # adding the phase sends the pattern downward.
                    g = (ty + frame / float(DIAMOND_FRAMES)) % 1.0

                    # Mirrored: blue at both ends of the cycle, green in the
                    # middle, so the ends meet and the slide has no seam.
                    shade = 1.0 - abs(2.0 * g - 1.0)

                    step_i = int(shade * (DIAMOND_BANDS - 1)) / float(DIAMOND_BANDS - 1)

                    colour[y][x % size] = mixc(DIAMOND_TOP, DIAMOND_BOTTOM, step_i)

    px = bytearray(size * size * 4)

    def put(x, y, c, a):
        o = ((y % size) * size + (x % size)) * 4
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
    d += u32(2)                     # numTextures
    # 0: the sky -- gradient with the starfield painted into it, so it is
    #    opaque and can stay compressed. Replace, being the base.
    d += asset_ref(UUID_STARS, "T_S2Sky_Stars_1") + u8(0) + u8(0)
    # 1: diamonds on uv1, Decal. This one genuinely needs alpha, so it cooks to
    #    RGB5A3 rather than CMPR.
    d += asset_ref(UUID_DIAMONDS, "T_S2Sky_Diamonds_1") + u8(1) + u8(2)
    d += null_ref() + u8(0) + u8(1)
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
# The elevation band the diamond texture covers.
V_LO = CLUSTER_ELEV - CLUSTER_DEG_H * 0.5 - CLUSTER_V_MARGIN
V_HI = CLUSTER_ELEV + CLUSTER_DEG_H * 0.5 + CLUSTER_V_MARGIN

RADIUS = 900.0
SEGMENTS = 64      # doubled: the diamonds show faceting at 32
# A full sphere, not a hemisphere with a short skirt.
#
# It used to stop at -10 degrees, so everything below that was simply not
# drawn -- the black half. Rings now run from -80 up to 80 with a cap at each
# pole, and the ring spacing is mirrored about the horizon so the bottom is as
# finely divided as the top.
ELEVATIONS = [-80.0, -66.0, -52.0, -40.0, -30.0, -22.0, -15.0, -9.0, -4.0,
              0.0, 4.0, 9.0, 15.0, 22.0, 30.0, 40.0, 52.0, 66.0, 80.0]

# The whole dome gets texture, skirt included.
#
# v used to be max(0, elev/90), so every vertex from the lowest ring at -10
# degrees up to the horizon shared v = 0 and sampled one row of the texture,
# stretched down the entire skirt. Clearing that row only changed what was
# smeared; the stretch was the mapping. Spanning the real elevation range
# instead gives the skirt its own rows and there is nothing left to stretch.
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

            # UV0 tiles horizontally, one cluster per tile, and covers only
            # the cluster's band of elevation vertically.
            #
            # v is clamped here, at the vertex, so it never leaves 0..1 and the
            # texture's Repeat can only ever act on u. Without that the texture
            # would wrap vertically and draw the cluster again above and below
            # itself. Vertices outside the band all sit on 0 or 1, which are
            # the empty margin rows, so nothing is smeared by the clamp.
            # UV0 is the sky: the gradient and the starfield share it, which
            # they can because the gradient is constant across u.
            u0 = az * STAR_REPEAT
            v0 = v

            # UV1 is the diamond band, clamped so the texture's Repeat can only
            # ever act across, never up.
            u1 = az * CLUSTER_COUNT
            v1 = min(1.0, max(0.0, (elev - V_LO) / (V_HI - V_LO)))

            verts.append((dx * RADIUS, dy * RADIUS, dz * RADIUS,
                          u0, v0, u1, v1, -dx, -dy, -dz))

    # A pole vertex per segment, not one shared by the whole fan.
    #
    # A single pole vertex has to carry one u, and the ring below it carries u
    # running the whole way round -- so every triangle in the cap interpolated
    # from that segment's u down to the pole's, sweeping the entire texture
    # across itself. That is the smearing at the top and bottom of the sky.
    # Giving each fan triangle its own pole vertex, holding the u of the
    # segment it belongs to, keeps u constant across the triangle.
    north_first = len(verts)
    for seg in range(SEGMENTS):
        az = (seg + 0.5) / SEGMENTS
        verts.append((0.0, RADIUS, 0.0,
                      az * STAR_REPEAT, 1.0,
                      az * CLUSTER_COUNT, 1.0,
                      0.0, -1.0, 0.0))

    south_first = len(verts)
    for seg in range(SEGMENTS):
        az = (seg + 0.5) / SEGMENTS
        verts.append((0.0, -RADIUS, 0.0,
                      az * STAR_REPEAT, 0.0,
                      az * CLUSTER_COUNT, 0.0,
                      0.0, 1.0, 0.0))

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
        idx += [top + seg_i, top + seg_i + 1, north_first + seg_i]

    # The cap under the lowest ring. The material culls nothing, so the winding
    # here only decides which way the normals point, not whether it is drawn.
    for seg_i in range(SEGMENTS):
        idx += [seg_i + 1, seg_i, south_first + seg_i]

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
                      UUID_DIAMONDS + f, w, h, px, wrap=1)      # Repeat

    gen_material(os.path.join(mat, "M_Sky.oct"))
    gen_mesh(os.path.join(mesh, "SM_SkyDome.oct"))


if __name__ == "__main__":
    main()
