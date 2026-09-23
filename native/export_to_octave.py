"""Export a generated stage into the Octave project, so it can be PLAYED.

    blender -b external/halfpipe/TrackPiecesPack.blend \\
        --python native/export_to_octave.py -- [stage 1-7]

Reads external/stages/Stage<N>_seed<S>.json and writes, straight into proj/ as finished
engine assets (the same way gen_s2sky_assets.py writes the sky, no import step):

    proj/Assets/Stage/M_StageVertex.oct          one material for everything below
    proj/Assets/Stage/SM_Piece_<Name>_P<N>.oct   the five track pieces, in stage N's colours
    proj/Assets/Stage/SM_Ring.oct, SM_Bomb.oct, SM_RingRainbow_0..8.oct,
                      SM_PlayerBall.oct, SM_Emerald.oct
    proj/Scripts/StageData<N>.lua                the stage itself, as a Lua table

EVERY COLOUR IS IN THE VERTICES, and a stage's palette is just which set of piece meshes it
uses. What the vertices do NOT carry is the light: the first version baked a little shading
in and drew everything unlit, and it looked flat -- the spheres did not shine as they do in
Blender, because nothing was there to shine. So there are three LIT materials, all showing
vertex colour, and the game adds a sun:
    M_StageMatte   the pipe, its decks, stripes, hoops and rails: UNLIT. Lit, it burned out
                   -- cyan to pure cyan, the brown decks to yellow -- whatever the sun was set
                   to, so the pipe does not take the engine's light at all: a little soft
                   shading from a fixed light is baked into its vertex colours instead, which
                   cannot burn out and looks the same in every scene.
    M_StageGloss   the arch of spheres, and the rings, bombs, Sonic's ball and the emerald: a
                   plain glossy highlight, as the spheres have in Blender. NO FRESNEL -- a rim
                   was tried and the owner did not want it: just glossy.
    M_StageGlow    the rainbow arch: gloss, and lit from within
    (the rings)    take no light either: their gold is PAINTED on, a reflection and all. See gold().
A mesh has one material, so each track piece is two meshes set down at the same place:
SM_Piece_<Name>_P<N> (matte) and SM_Piece_<Name>_Gloss_P<N>.

Blender is Z up, Octave is Y up: a point (x, y, z) goes to (x, z, -y), a rotation, so
nothing is mirrored and no face needs turning. A quaternion's axis goes the same way.

THE STAGE DATA is what native/gen_stage.py wrote, plus the one thing the engine cannot work
out for itself: the track's centre line. `path` has one entry per frame -- where the floor's
centre line is, which way is forward, which way is up -- so the game turns (frame, angle)
into a place exactly as lay() does here, and never needs the pieces' curves.
"""

import json
import math
import os
import struct
import sys

import bmesh
import bpy
from mathutils import Matrix, Vector

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
# THE CHECKS, where the generator's cannot be met. gen_stage.py asks each check for a share of the
# rings its section holds, as if every ring could be taken. native/solve_stages.py found stage 7's
# cannot: the rings at some moments lie further apart round the pipe than he can reach, and the
# best line there is is about 104, 177 and 278 rings (of 147, 191 and 294) where its checks asked
# for 140, 180 and 280. These are what each check newly asks instead -- still close to the best a
# line can do (about 90% of it, with the ordinary steering), so the stage stays very hard. The
# layout is the generator's, unchanged; only the checks' numbers are set here. Rerun the solver
# after changing them.
CHECK_ASKS = {7: (90, 160, 230)}


def check_numbers(stage, secs):
    """(quota, asks) for each check: the running total asked for, and what the check itself asks."""
    asks = CHECK_ASKS.get(stage)
    if asks is None:
        return [(sec["quota"], sec["asks"]) for sec in secs]
    out, total = [], 0
    for a in asks:
        total += a
        out.append((total, a))
    return out


args = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
STAGE = int(args[0]) if args and args[0].isdigit() else 1
sys.argv = sys.argv[:sys.argv.index("--") + 1] if "--" in sys.argv else sys.argv   # gen_stage reads argv too

import gen_random_level as grl
import ring_modules as rm
import stage_palettes
from gen_rings_on_pieces import BOMB_BLEND, RING_BLEND, ChainPath
from gen_stage import GAUNTLET_SEED, piece_paths

PROJ = os.path.abspath(os.path.join(HERE, "..", "proj"))
ASSETS = os.path.join(PROJ, "Assets", "Stage")
STAGES = os.path.abspath(os.path.join(HERE, "..", "external", "stages"))

# --- the .oct container, as gen_s2sky_assets.py writes it (that file needs Pillow, which
# Blender's Python does not have, so the few lines are repeated here) ---------------------
MAGIC, VERSION = 0x4F435421, 13
TYPE_STATICMESH, TYPE_MATERIALLITE = 0xD41D0D1D, 0xA3ED4C6F
UUID_BASE = 0x51C0FFEE00003000          # clear of the sky's and the UI's
# name: (uuid, specular, shininess, fresnel, emission, wrap lighting)
UNLIT = ("M_StageMatte",)
# The baked light comes from STRAIGHT ABOVE, and that is not a matter of taste. The shading is
# baked into each piece in the piece's own space, and the pieces are then turned every which
# way to make a level. Light from one side was tried: a corner's far end faces a different way
# from its start, so its shading did not match the next piece's and every joint showed as a
# hard curved edge across the pipe. "Up" is the one direction every piece agrees on however it
# is turned, so light from above meets itself at every joint. It also suits the shape: the
# floor is bright and the walls darken toward the rims, so the pipe reads as a bowl.
BAKE_LIGHT = Vector((0.0, 0.0, 1.0))
BAKE_AMBIENT = 0.76         # the darkest a face gets: a wall at the rim, facing sideways
BAKE_BRIGHT = 1.16          # the brightest: the floor, facing straight up. Over 1 on purpose --
                            # at 1.0 the pipe was only ever its palette colour or darker, and
                            # read as dull. (0.50-1.0, then 0.64-1.0, were each asked to be lighter.)
MATERIALS = {
    "M_StageMatte": (UUID_BASE + 0x800, 0.00, 8.0, False, 0.0, 0.60),
    "M_StageGloss": (UUID_BASE + 0x801, 0.85, 48.0, False, 0.0, 0.30),
    "M_StageGlow":  (UUID_BASE + 0x802, 0.60, 40.0, False, 0.70, 0.30),
    # Gold, as a metal: the engine multiplies a highlight by the surface's own colour, so a
    # gold ring's highlight IS gold -- which is what metal does, and plastic does not. Metal is
    # little diffuse and a lot of highlight, broad rather than pin-sharp (Blender's roughness
    # about 0.3), with a touch of emission so a ring in shadow is still a ring.
    # The bombs: METAL. What makes a lit surface read as metal and not plastic is a highlight that
    # is strong and fairly broad over a base that is darker than the paint would be (a metal has
    # little diffuse colour: most of what it sends back is reflection). So: three times the gloss
    # material's specular, a lower shininess for a wider hot spot, and the colours darkened below.
    "M_StageMetal": (UUID_BASE + 0x804, 2.40, 26.0, False, 0.0, 0.18),
    "M_StageGold":  (UUID_BASE + 0x803, 2.60, 20.0, False, 0.18, 0.10),
}
GLOSSY_SLOTS = ("HP_Sphere",)               # of the half-pipe's seven materials, only the arch of spheres


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


def write_materials():
    for name, (uuid, specular, shininess, fresnel, emission, wrap) in MATERIALS.items():
        d = header(TYPE_MATERIALLITE, uuid, name)
        d += u32(0)                     # numParameters
        d += u32(0 if name in UNLIT else 1)     # ShadingModel: Unlit, or Lit
        d += u32(0)                     # Opaque
        d += u32(1)                     # VertexColorMode::Modulate
        d += u32(0)                     # numTextures
        for _ in range(4):
            d += null_ref() + u8(0) + u8(1)
        for _ in range(2):
            d += f32(0) + f32(0) + f32(1) + f32(1)
        d += f32(1) + f32(1) + f32(1) + f32(1)          # colour
        d += f32(0.85) + f32(0.92) + f32(1.0) + f32(1)  # fresnel colour: a cool rim, like sky on glass
        d += f32(2.6) + f32(emission) + f32(wrap) + f32(specular)
        d += u32(2) + f32(1.0) + f32(0.5) + f32(shininess)   # toonSteps, opacity, maskCutoff, shininess
        d += i32(0)                     # sortPriority
        d += u8(0) + u8(1 if fresnel else 0) + u8(1)    # disableDepthTest, fresnelEnabled, applyFog
        d += u8(0)                      # CullMode::None: the pipe is seen from inside and out
        open(os.path.join(ASSETS, name + ".oct"), "wb").write(d)


# --- meshes ---------------------------------------------------------------------------
def to_octave(v):
    return (v[0], v[2], -v[1])


def linear_to_srgb(c):
    return 12.92 * c if c <= 0.0031308 else 1.055 * (c ** (1.0 / 2.4)) - 0.055


def write_mesh(name, index, mesh, colour_of_slot, material="M_StageGloss", keep_slot=None, paint=None,
               colour_of_face=None):
    """One StaticMesh with vertex colours. colour_of_slot(slot index) -> (r, g, b) sRGB.
    keep_slot(slot index) -> bool picks which faces go in: how a piece is split in two.
    paint(normal) -> (r, g, b), when given, colours each vertex by which way it faces and
    nothing else: a whole look painted on, for a material that takes no light.
    colour_of_face(polygon index, slot index) -> (r, g, b) or None overrides a face's colour:
    a pattern on the pipe."""
    mesh.calc_loop_triangles()
    corner_normals = [Vector(n.vector) for n in mesh.corner_normals] if hasattr(mesh, "corner_normals") else None
    verts, index_of, idx = [], {}, []
    lo, hi = Vector((1e9,) * 3), Vector((-1e9,) * 3)
    for tri in mesh.loop_triangles:
        if keep_slot is not None and not keep_slot(tri.material_index):
            continue
        base = colour_of_slot(tri.material_index)
        if colour_of_face is not None:
            base = colour_of_face(tri.polygon_index, tri.material_index) or base
        for corner, loop in zip(tri.vertices, tri.loops):
            p = mesh.vertices[corner].co
            n = corner_normals[loop] if (corner_normals and tri.use_smooth) else Vector(tri.normal)
            shade = 1.0
            if material in UNLIT:       # no engine light reaches it, so it carries its own
                shade = BAKE_AMBIENT + (BAKE_BRIGHT - BAKE_AMBIENT) * max(0.0, n.dot(BAKE_LIGHT))
            rgb = tuple(max(0, min(255, int(round(255 * c * shade)))) for c in base)
            if paint is not None:
                rgb = tuple(max(0, min(255, int(round(255 * c)))) for c in paint(n))
            key = (round(p.x, 4), round(p.y, 4), round(p.z, 4), round(n.x, 3), round(n.y, 3), round(n.z, 3), rgb)
            if key not in index_of:
                index_of[key] = len(verts)
                verts.append((to_octave(p), to_octave(n), rgb))
                for k in range(3):
                    lo[k], hi[k] = min(lo[k], to_octave(p)[k]), max(hi[k], to_octave(p)[k])
            idx.append(index_of[key])
    if not verts:
        return False

    centre = (lo + hi) * 0.5
    radius = max((Vector(v[0]) - centre).length for v in verts)
    d = header(TYPE_STATICMESH, UUID_BASE + 1 + index, name)
    d += u32(len(verts)) + u32(len(idx)) + u32(1)
    d += asset_ref(MATERIALS[material][0], material)
    d += u8(0) + u8(1)                                  # no triangle collision; HAS vertex colour
    for p, n, rgb in verts:
        d += f32(p[0]) + f32(p[1]) + f32(p[2]) + f32(0) + f32(0) + f32(0) + f32(0)
        d += f32(n[0]) + f32(n[1]) + f32(n[2])
        d += u32(rgb[0] | (rgb[1] << 8) | (rgb[2] << 16) | (255 << 24))
    for i in idx:
        d += u32(i)
    d += u8(0) + u32(0)                                 # no collision shapes
    d += f32(centre.x) + f32(centre.y) + f32(centre.z) + f32(radius)
    open(os.path.join(ASSETS, name + ".oct"), "wb").write(d)
    print("  %-30s %-13s %6d verts %6d tris %7.1f KB" % (name, material, len(verts), len(idx) // 3, len(d) / 1024.0))
    return True


# --- textured and lit: the bomb -------------------------------------------------------------
# native/texture_bomb.py unwraps the bomb and bakes its metal detail (grain, scratches, worn
# edges, the grooves' shadow) into Bomb_albedo.png. It goes in the game as ONE texture on a lit
# metal material -- the look of M_StageMetal, reading the picture instead of vertex colours.
TYPE_TEXTURE = 0xCDBBDA30
BOMB_TEXTURED = os.path.join(os.path.dirname(BOMB_BLEND), "Bomb_Textured.blend")
BOMB_ALBEDO = os.path.join(os.path.dirname(BOMB_BLEND), "Bomb_albedo.png")
# the texture the game uses: the albedo LIT, its shading, highlights and reflections painted in
BOMB_LIT = os.path.join(os.path.dirname(BOMB_BLEND), "Bomb_lit.png")
# ...so its material is a BASIC lit one: the stage's light over it, and only a faint highlight of
# its own (the shine is in the texture). (specular, shininess, wrap)
BOMB_BASIC_LIT = (0.15, 24.0, 0.30)
UUID_BOMB_TEX, UUID_BOMB_MAT = UUID_BASE + 0x901, UUID_BASE + 0x902


def write_lit_textured(name, index, mesh, png, tex_name, mat_name, look="M_StageMetal", size=None,
                       base=1.0, force_hq=False, basic=None):
    """A mesh with its own UVs, a texture from `png` and a lit material with `look`'s highlight.
    size: square side to scale the texture to (None: as it is). base: how much of the painted
    colour is kept as diffuse (a metal keeps little, as write_mesh's METAL_BASE did)."""
    import numpy as np
    image = bpy.data.images.load(png, check_existing=True)
    w, h = image.size
    px = np.array(image.pixels[:], dtype=np.float32).reshape(h, w, 4)[::-1]      # top row first
    if size is not None and size != w:
        ys, xs = np.arange(size) * h // size, np.arange(size) * w // size
        # a box filter, not nearest: the detail is fine and would sparkle
        step = w // size
        px = px[:size * step, :size * step].reshape(size, step, size, step, 4).mean(axis=(1, 3)) if step > 1 \
            else px[ys][:, xs]
        w = h = size
    px[:, :, :3] *= base
    px[:, :, 3] = 1.0
    pixels = (np.clip(px, 0.0, 1.0) * 255.0 + 0.5).astype(np.uint8).tobytes()
    d = header(TYPE_TEXTURE, UUID_BOMB_TEX, tex_name)
    d += u32(w) + u32(h) + u32(1) + u32(1)
    d += u32(2) + u32(1) + u32(0)                          # RGBA8, LINEAR, clamp
    d += u8(0) + u8(0) + u8(1)                             # no mips, not a render target, sRGB
    d += u8(1 if force_hq else 0) + u8(1)
    d += pixels
    open(os.path.join(ASSETS, tex_name + ".oct"), "wb").write(d)

    _uuid, specular, shininess, _fresnel, emission, wrap = MATERIALS[look]
    if basic is not None:                   # (specular, shininess, wrap), no emission
        (specular, shininess, wrap), emission = basic, 0.0
    d = header(TYPE_MATERIALLITE, UUID_BOMB_MAT, mat_name)
    d += u32(0)                     # numParameters
    d += u32(1)                     # Lit
    d += u32(0)                     # Opaque
    d += u32(0)                     # VertexColorMode::None: the colour is the texture's
    d += u32(1)                     # numTextures
    d += asset_ref(UUID_BOMB_TEX, tex_name) + u8(0) + u8(1)        # uv0, modulate
    for _ in range(3):
        d += null_ref() + u8(0) + u8(1)
    for _ in range(2):
        d += f32(0) + f32(0) + f32(1) + f32(1)
    d += f32(1) + f32(1) + f32(1) + f32(1)
    d += f32(0.85) + f32(0.92) + f32(1.0) + f32(1)
    d += f32(2.6) + f32(emission) + f32(wrap) + f32(specular)
    d += u32(2) + f32(1.0) + f32(0.5) + f32(shininess)
    d += i32(0)
    d += u8(0) + u8(0) + u8(1)
    d += u8(0)
    open(os.path.join(ASSETS, mat_name + ".oct"), "wb").write(d)

    mesh.calc_loop_triangles()
    uv = mesh.uv_layers.active.data
    normals = [Vector(n.vector) for n in mesh.corner_normals]
    verts, index_of, idx = [], {}, []
    lo, hi = Vector((1e9,) * 3), Vector((-1e9,) * 3)
    for tri in mesh.loop_triangles:
        for corner, loop in zip(tri.vertices, tri.loops):
            p = to_octave(mesh.vertices[corner].co)
            n = to_octave(normals[loop] if tri.use_smooth else Vector(tri.normal))
            u, v = uv[loop].uv
            key = (round(p[0], 4), round(p[1], 4), round(p[2], 4), round(n[0], 3), round(n[1], 3), round(n[2], 3),
                   round(u, 5), round(v, 5))
            if key not in index_of:
                index_of[key] = len(verts)
                verts.append((p, n, u, 1.0 - v))                    # the texture's top row is first
                for k in range(3):
                    lo[k], hi[k] = min(lo[k], p[k]), max(hi[k], p[k])
            idx.append(index_of[key])
    centre = (lo + hi) * 0.5
    radius = max((Vector(v[0]) - centre).length for v in verts)
    d = header(TYPE_STATICMESH, UUID_BASE + 1 + index, name)
    d += u32(len(verts)) + u32(len(idx)) + u32(1)
    d += asset_ref(UUID_BOMB_MAT, mat_name)
    d += u8(0) + u8(0)                                  # no triangle collision; NO vertex colour
    for p, n, su, sv in verts:
        d += f32(p[0]) + f32(p[1]) + f32(p[2]) + f32(su) + f32(sv) + f32(0) + f32(0)
        d += f32(n[0]) + f32(n[1]) + f32(n[2])
    for i in idx:
        d += u32(i)
    d += u8(0) + u32(0)
    d += f32(centre.x) + f32(centre.y) + f32(centre.z) + f32(radius)
    open(os.path.join(ASSETS, name + ".oct"), "wb").write(d)
    print("  %-30s %-13s %6d verts %6d tris, texture %d x %d" % (name, mat_name, len(verts), len(idx) // 3, w, h))


# --- gold ---------------------------------------------------------------------------------
# WHY THE RINGS ARE PAINTED, NOT LIT. The engine's simple material has one highlight and
# nothing else, and one highlight is plastic. Metal reads as metal because it REFLECTS: a
# bright sky above, a dark line at the horizon, warm light coming back up off the ground, and
# a hard hotspot. That banding is the whole effect. It cannot be got from the material, but it
# does not need to be: a ring is only ever seen from one side -- from up the track, looking
# down it -- so the reflection can be painted straight onto the ring, each vertex coloured by
# which way it faces, as a matcap does in Blender. The material takes no light at all.
# (So the game must not roll a ring to the pipe under it, or the painted sky rolls with it: it
# keeps the track's own up. A ring looks the same rolled or not; its reflection does not.)
# GOLD_DEEP is the darkest the gold ever gets, and it is still gold: at (0.30, 0.16, 0.01) the
# horizon line and the underside went nearly brown-black and the rings read as dark.
GOLD_DEEP, GOLD, GOLD_PALE, GOLD_HOT = (0.66, 0.40, 0.03), (1.0, 0.70, 0.07), (1.0, 0.92, 0.46), (1.0, 1.0, 0.88)
GOLD_HOTSPOT = Vector((-0.45, 0.32, 0.83)).normalized()     # Blender's axes; -X is toward the player


def mix(a, b, t):
    t = max(0.0, min(1.0, t))
    return tuple(x + (y - x) * t for x, y in zip(a, b))


def smooth(e0, e1, x):
    t = max(0.0, min(1.0, (x - e0) / (e1 - e0)))
    return t * t * (3.0 - 2.0 * t)


def gold(n):
    """The colour of gold facing n: sky, horizon, ground and hotspot, by height of the normal."""
    up = n.z
    if up >= 0.0:
        c = mix(GOLD_DEEP, GOLD, smooth(0.01, 0.14, up))        # the horizon line, thin, then gold
        c = mix(c, GOLD_PALE, smooth(0.45, 0.95, up))           # brightening toward the sky
    else:
        c = mix(GOLD_DEEP, GOLD, smooth(0.03, 0.40, -up) * 0.92)    # light off the ground: warm, nearly as bright
        c = mix(c, GOLD_DEEP, smooth(0.75, 1.0, -up) * 0.30)        # and a little darker right underneath
    c = mix(c, GOLD_HOT, max(0.0, n.dot(GOLD_HOTSPOT)) ** 26)       # the hard hotspot
    return mix(c, GOLD_PALE, 0.35 * (1.0 - abs(n.x)) ** 3)          # a pale edge where it turns away


RING_SPIN_FRAMES = 12       # meshes in half a turn of a ring; the other half looks the same


def torus(bm, around=36, across=16, radius=1.0, tube=0.24, spin=0.0):
    """The ring again (gen_ring.py's size), with a finer tube: the bands need the vertices.
    `spin` turns it about its upright axis, in radians. THE RINGS SPIN BY SWAPPING MESHES: the
    gold is a reflection painted on by which way each vertex faces, so a ring turned by the game
    would carry its sky round with it. Turned HERE, before the paint goes on, the ring turns and
    the reflection stays where it is, which is what a real one does."""
    grid = []
    for i in range(around):
        a = 2.0 * math.pi * i / around
        loop = []
        for j in range(across):
            t = 2.0 * math.pi * j / across
            r = radius + tube * math.cos(t)
            loop.append(bm.verts.new((tube * math.sin(t), r * math.cos(a), r * math.sin(a))))
        grid.append(loop)
    for i in range(around):
        for j in range(across):
            bm.faces.new((grid[i][j], grid[i][(j + 1) % across], grid[(i + 1) % around][(j + 1) % across],
                          grid[(i + 1) % around][j]))
    if spin != 0.0:
        bmesh.ops.rotate(bm, verts=bm.verts, cent=(0.0, 0.0, 0.0), matrix=Matrix.Rotation(spin, 3, "Z"))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)


# --- drop shadows ---------------------------------------------------------------------------
# The original puts a dark blob on the pipe under Sonic and under every ring and bomb, and it is
# most of what tells you how far round the pipe a thing is. Here it is one small mesh, SM_Shadow:
# a disc lying flat (its face is Blender +Z, the engine's +Y: "away from the pipe"), black, solid
# in the middle and fading to nothing at its rim. The fade is in the VERTEX ALPHA, so it needs no
# texture; the material is unlit and translucent and takes its alpha from the vertices.
SHADOW_SEGMENTS = 20
SHADOW_CORE = 0.55                  # out to this share of the radius it is fully dark
SHADOW_ALPHA = 0.50
# THE DISC IS CURVED to fit the pipe. Flat, it touched the pipe in the middle and its left and
# right edges sank under the surface and were cut off -- at Sonic's size; smaller ones (his own,
# mid-jump) were shallow enough to escape. Across the pipe, the surface rises by x*x / 2R from
# where a flat disc would be, so the disc's vertices are lifted by that. The game scales the disc
# sideways but not upward, so the lift is worked out for the BIGGEST shadow (SHADOW_WIDEST, the
# bomb's): smaller ones then ride a hair above the pipe at their edges, which does not show.
SHADOW_WIDEST = 1.35
# ONE disc, and dark. Fainter discs for things high up were tried (a shadow dropped to the floor
# and faded with the drop); the original does neither: a thing up on the wall has a dark shadow
# ON THE WALL beside it, and its sprites for that -- long slanted blobs, thin slivers at the side --
# are what this same disc looks like lying on the wall, seen from down the track.
SHADOW_LEVELS = [(0.60, 0.60)]      # (darkness, the share of the radius that is fully dark)


def write_shadow():
    uuid = UUID_BASE + 0x880
    d = header(TYPE_MATERIALLITE, uuid + 1, "M_StageShadow")
    d += u32(0)                     # numParameters
    d += u32(0)                     # Unlit
    d += u32(2)                     # Translucent
    d += u32(1)                     # VertexColorMode::Modulate: the fade is the vertices' alpha
    d += u32(0)                     # numTextures
    for _ in range(4):
        d += null_ref() + u8(0) + u8(1)
    for _ in range(2):
        d += f32(0) + f32(0) + f32(1) + f32(1)
    d += f32(0) + f32(0) + f32(0) + f32(1)                  # colour: black
    d += f32(1) + f32(1) + f32(1) + f32(1)
    d += f32(1.0) + f32(0.0) + f32(0.0) + f32(0.0)
    d += u32(2) + f32(1.0) + f32(0.5) + f32(8.0)            # toonSteps, opacity, maskCutoff, shininess
    d += i32(0)
    d += u8(0) + u8(0) + u8(0)                              # depth test on, no fresnel, NO FOG on a shadow
    d += u8(0)                                              # no culling
    open(os.path.join(ASSETS, "M_StageShadow.oct"), "wb").write(d)

    for level, (darkness, core) in enumerate(SHADOW_LEVELS):
        write_shadow_disc(uuid, level, darkness, core)


def write_shadow_disc(uuid, level, darkness, core):
    name = "SM_Shadow" if level == 0 else "SM_Shadow_%d" % level
    # vertices: the middle, a ring at `core` (dark), a ring at 1 (clear)
    alpha = int(round(255 * darkness))
    verts = [((0.0, 0.0, 0.0), alpha)]
    for ring, a in ((core, alpha), (1.0, 0)):
        for i in range(SHADOW_SEGMENTS):
            t = 2.0 * math.pi * i / SHADOW_SEGMENTS
            across = ring * math.sin(t) * SHADOW_WIDEST          # Blender Y is across the pipe
            verts.append(((ring * math.cos(t), ring * math.sin(t), across * across / (2.0 * rm.PIPE_RADIUS)), a))
    idx = []
    n = SHADOW_SEGMENTS
    for i in range(n):
        j = (i + 1) % n
        idx += [0, 1 + i, 1 + j]                                        # the dark middle
        idx += [1 + i, 1 + n + i, 1 + n + j, 1 + i, 1 + n + j, 1 + j]   # the fading rim
    d = header(TYPE_STATICMESH, uuid + (0 if level == 0 else 1 + level), name)
    d += u32(len(verts)) + u32(len(idx)) + u32(1)
    d += asset_ref(uuid + 1, "M_StageShadow")
    d += u8(0) + u8(1)
    for p, a in verts:
        o = to_octave(p)
        up = to_octave((0.0, 0.0, 1.0))
        d += f32(o[0]) + f32(o[1]) + f32(o[2]) + f32(0) + f32(0) + f32(0) + f32(0)
        d += f32(up[0]) + f32(up[1]) + f32(up[2])
        d += u32(255 | (255 << 8) | (255 << 16) | (a << 24))
    for i in idx:
        d += u32(i)
    d += u8(0) + u32(0)
    d += f32(0) + f32(0) + f32(0) + f32(1.05)
    open(os.path.join(ASSETS, name + ".oct"), "wb").write(d)
    print("wrote %s.oct (%d triangles, %.0f%% dark)" % (name, len(idx) // 3, darkness * 100))


def simple(name, build):
    bm = bmesh.new()
    build(bm)
    for f in bm.faces:
        f.smooth = True
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    return me


def octahedron(bm):
    v = [bm.verts.new(p) for p in ((2.2, 0, 0), (-2.2, 0, 0), (0, 2.2, 0), (0, -2.2, 0), (0, 0, 3.1), (0, 0, -3.1))]
    for a, b, c in ((0, 2, 4), (2, 1, 4), (1, 3, 4), (3, 0, 4), (2, 0, 5), (1, 2, 5), (3, 1, 5), (0, 3, 5)):
        bm.faces.new((v[a], v[b], v[c]))


# --- the stage ------------------------------------------------------------------------
def lua(value, indent=0):
    pad = " " * indent
    if isinstance(value, dict):
        return "{\n" + "".join("%s  %s = %s,\n" % (pad, k, lua(v, indent + 2)) for k, v in value.items()) + pad + "}"
    if isinstance(value, (list, tuple)):
        if value and all(isinstance(x, (int, float)) for x in value):
            return "{" + ",".join(lua(x) for x in value) + "}"
        return "{\n" + "".join("%s  %s,\n" % (pad, lua(v, indent + 2)) for v in value) + pad + "}"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, float):
        return ("%.4f" % value).rstrip("0").rstrip(".") if value == value else "0"
    if isinstance(value, int):
        return str(value)
    if value is None:
        return "nil"
    return '"%s"' % str(value).replace('"', '\\"')


# --- checkers ------------------------------------------------------------------------------
# The original's first stage has its pipe in a check of two blues; ours has every stage's pipe
# in a check of its own colour and a darker shade of it, by cell (the pipe's faces, slot
# HP_Pipe). A cell is a few faces along the piece by a band round it; the bands are by the
# wall's angle from the floor, the same up both walls, so the mirrored pieces match their sources.
CHECKER_STAGES = {n: 3 for n in range(1, 8)}    # stage -> the palette line's slot for the dark square
                                                # (3: the pipe's mid shade)
CHECK_ALONG = 4.0           # a cell's length along the pipe, about; a section holds a whole number of them
CHECK_BANDS = 4             # cells up each wall from the lane stripe to the rim
LANE_OUT = 19.0             # degrees: where the lane stripe ends and the wall's blue begins (gen_halfpipe.py)


def checkers(number, mesh_name, slots):
    """colour_of_face for a piece mesh in palette `number`, or None when that palette has no check."""
    if number not in CHECKER_STAGES or "HP_Pipe" not in slots:
        return None
    cells = grl.CELLS.get(mesh_name)
    if not cells:
        return None
    pipe_slot = slots.index("HP_Pipe")
    dark = stage_palettes.rgb(stage_palettes.S2_LINE[number].split()[CHECKER_STAGES[number]])
    length = max(c[1] for c in cells if c) * 1.0
    # the section's faces sit between x stations; the last face's middle is short of the end
    length = max(length, 1.0)
    n_along = max(1, int(round((length + CHECK_ALONG * 0.5) / CHECK_ALONG)))
    cell_x = (length + CHECK_ALONG * 0.5) / n_along

    def colour_of_face(poly, slot):
        if slot != pipe_slot:
            return None
        c = cells[poly] if poly < len(cells) else None
        if c is None:
            return None
        copy, x, angle = c
        along = copy * n_along + int(x // cell_x)
        a = abs(angle)
        if a < LANE_OUT:
            band = 0                                        # the floor strip between the stripes
        else:
            band = 1 + min(CHECK_BANDS - 1, int((a - LANE_OUT) / ((90.0 - LANE_OUT) / CHECK_BANDS)))
        return dark if (along + band) % 2 else None

    return colour_of_face


def main():
    os.makedirs(ASSETS, exist_ok=True)
    name = "Stage%d_seed%d" % (STAGE, GAUNTLET_SEED[STAGE])
    data = json.load(open(os.path.join(STAGES, name + ".json"), encoding="utf-8"))
    palette = stage_palettes.palette(STAGE)

    print("\nmeshes -> %s" % ASSETS)
    write_materials()
    for stale in ("M_StageVertex.oct",):
        if os.path.exists(os.path.join(ASSETS, stale)):
            os.remove(os.path.join(ASSETS, stale))
    pieces = grl.load_pieces()
    # The pieces in ALL SEVEN palettes, whichever stage this is: a palette is only a set of
    # meshes, so the game can change colours on the spot by swapping _P1 for _P4. (Keys 1-7
    # do that in the demo, and marathon will after every third check.)
    for number in stage_palettes.S2_LINE:
        colours_of = stage_palettes.palette(number)["materials"]
        for i, (piece, p) in enumerate(pieces.items()):
            slots = [m.name.split(".")[0] if m else "" for m in p["mesh"].materials]
            colours = [colours_of.get(n, (1.0, 0.0, 1.0)) for n in slots]
            glossy = [n in GLOSSY_SLOTS for n in slots]
            checker = checkers(number, p["mesh"].name, slots)
            write_mesh("SM_Piece_%s_P%d" % (piece, number), 16 * number + i, p["mesh"], lambda k, c=colours: c[k],
                       material="M_StageMatte", keep_slot=lambda k, g=glossy: not g[k], colour_of_face=checker)
            write_mesh("SM_Piece_%s_Gloss_P%d" % (piece, number), 16 * number + 8 + i, p["mesh"],
                       lambda k, c=colours: c[k], material="M_StageGloss", keep_slot=lambda k, g=glossy: g[k])

    def load(blend, mesh):
        with bpy.data.libraries.load(blend) as (src, dst):
            dst.meshes = [n for n in src.meshes if n == mesh]
        return dst.meshes[0]

    ring, bomb = load(RING_BLEND, "Ring"), load(BOMB_BLEND, "Bomb")
    write_mesh("SM_Ring", 200, simple("GoldRing", torus), lambda k: GOLD, material="M_StageMatte", paint=gold)
    for i in range(RING_SPIN_FRAMES):
        turned = simple("GoldRing%d" % i, lambda bm, a=math.pi * i / RING_SPIN_FRAMES: torus(bm, spin=a))
        write_mesh("SM_Ring_%02d" % i, 230 + i, turned, lambda k: GOLD, material="M_StageMatte", paint=gold)
    from gen_stage import RAINBOW
    for i, c in enumerate(RAINBOW):
        write_mesh("SM_RingRainbow_%d" % i, 210 + i, ring, lambda k, c=c: c, material="M_StageGlow")
    METAL_BASE = 0.78               # how much of its painted colour a metal keeps as diffuse
    if os.path.exists(BOMB_TEXTURED) and os.path.exists(BOMB_LIT):
        # textured: native/texture_bomb.py's unwrapped bomb, its metal detail and lighting baked in,
        # on a basic lit material
        # external/bomb/1024fix.png is the owner's finished 1024 x 1024 cut of Bomb_lit.png: used when there
        own = os.path.join(os.path.dirname(BOMB_LIT), "1024fix.png")
        write_lit_textured("SM_Bomb", 220, load(BOMB_TEXTURED, "Bomb"), own if os.path.exists(own) else BOMB_LIT,
                           "T_Bomb", "M_Bomb",
                           force_hq=True, basic=BOMB_BASIC_LIT)            # at its full 1024
    else:
        bomb_colours = [tuple(linear_to_srgb(x) for x in m.diffuse_color[:3]) for m in bomb.materials]
        write_mesh("SM_Bomb", 220, bomb, lambda k: tuple(c * METAL_BASE for c in bomb_colours[k]),
                   material="M_StageMetal")
    write_mesh("SM_PlayerBall", 221, simple("Ball", lambda bm: bmesh.ops.create_icosphere(bm, subdivisions=3, radius=1.7)),
               lambda k: (0.12, 0.30, 0.95))
    write_mesh("SM_Emerald", 222, simple("Emerald", octahedron), lambda k: (0.10, 0.85, 0.95))
    write_shadow()

    # The track: where each piece goes, and the centre line frame by frame.
    paths = piece_paths()
    chain = ChainPath([paths[n] for n in data["pieces"]])
    piece_list = []
    for piece, (start, origin, path) in zip(data["pieces"], chain.parts):
        q = origin.to_quaternion()
        piece_list.append(dict(mesh="SM_Piece_%s_P" % piece,             # + the palette's number
                               gloss="SM_Piece_%s_Gloss_P" % piece, pos=list(to_octave(origin.translation)),
                               quat=[q.x, q.z, -q.y, q.w], first_frame=start / rm.STEP))
    frames = int(math.floor(chain.length / rm.STEP)) + 1
    path_list = []
    for f in range(frames + 1):
        m = chain.frame(min(f * rm.STEP, chain.length))
        path_list.append(list(to_octave(m.translation)) + list(to_octave(m.col[0].xyz)) + list(to_octave(m.col[2].xyz)))

    sections = []
    for sec, (quota, asks) in zip(data["sections"], check_numbers(STAGE, data["sections"])):
        sections.append(dict(first_frame=sec["first_frame"], check_frame=sec["check_frame"], last_frame=sec["last_frame"],
                             quota=quota, asks=asks, rings=sec["rings"], leads_to=sec["leads_to"],
                             objects=[[o[0], o[1], 1 if o[2] == rm.BOMB else 0] for o in sec["objects"]]))
    arch = data["sections"][0]["ring_check"]["rainbow_arch"]
    table = dict(
        name=name, stage=STAGE, step=rm.STEP, frames=frames,
        pipe_radius=rm.PIPE_RADIUS, hover=rm.HOVER,
        angle_00_side=-1 if rm.ANGLE_00_SIDE == "right" else 1,
        arch=dict(rings=arch["rings"], reach=rm.PIPE_RADIUS + 1.6, from_deg=12.0, ring_scale=arch["ring_scale"],
                  toward_player=0.72, steps_per_second=arch["steps_per_second"]),
        sky=palette["sky"], palette=STAGE,
        palette_skies=[stage_palettes.palette(n)["sky"] for n in sorted(stage_palettes.S2_LINE)],
        pieces=piece_list, sections=sections, path=path_list)
    out = os.path.join(PROJ, "Scripts", "StageData%d.lua" % STAGE)
    open(out, "w", encoding="ascii", newline="\n").write(
        "-- Written by native/export_to_octave.py from %s.json. Do not edit by hand.\n"
        "-- path[i] = { px,py,pz, fx,fy,fz, ux,uy,uz } for frame i-1: the floor's centre line, forward, up.\n"
        "-- objects = { frame, angle (256ths from the floor's centre line), 0 ring | 1 bomb }\n"
        "StageData%d = %s\n" % (name, STAGE, lua(table)))
    print("\nstage -> %s (%d pieces, %d frames, %d objects, %.0f KB)" % (
        out, len(piece_list), frames, sum(len(x["objects"]) for x in sections), os.path.getsize(out) / 1024.0))


main()
