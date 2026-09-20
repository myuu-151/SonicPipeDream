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

EVERY COLOUR IS IN THE VERTICES. One unlit material that shows vertex colour; each mesh has
its colours, and a little shading from a fixed light, baked into its vertices. So the scene
needs no lights, a GameCube could draw it, and a stage's palette is just which set of piece
meshes it uses. (The ring's gold and the bomb's glow are placeholders in the same spirit.)

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
UUID_MAT = UUID_BASE


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


def write_material():
    d = header(TYPE_MATERIALLITE, UUID_MAT, "M_StageVertex")
    d += u32(0)                     # numParameters
    d += u32(0)                     # Unlit
    d += u32(0)                     # Opaque
    d += u32(1)                     # VertexColorMode::Modulate
    d += u32(0)                     # numTextures
    for _ in range(4):
        d += null_ref() + u8(0) + u8(1)
    for _ in range(2):
        d += f32(0) + f32(0) + f32(1) + f32(1)
    d += f32(1) + f32(1) + f32(1) + f32(1)      # colour
    d += f32(1) + f32(0) + f32(0) + f32(0)      # fresnel colour
    d += f32(1.0) + f32(0.0) + f32(0.0) + f32(0.0)   # fresnelPower, emission, wrapLighting, specular
    d += u32(2) + f32(1.0) + f32(0.5) + f32(32.0)    # toonSteps, opacity, maskCutoff, shininess
    d += i32(0)                     # sortPriority
    d += u8(0) + u8(0) + u8(1)      # disableDepthTest, fresnelEnabled, applyFog
    d += u8(0)                      # CullMode::None: the pipe is seen from inside and out
    open(os.path.join(ASSETS, "M_StageVertex.oct"), "wb").write(d)


# --- meshes ---------------------------------------------------------------------------
LIGHT = Vector((0.35, 0.25, 1.0)).normalized()      # in Blender's axes: mostly from above
AMBIENT = 0.62


def to_octave(v):
    return (v[0], v[2], -v[1])


def linear_to_srgb(c):
    return 12.92 * c if c <= 0.0031308 else 1.055 * (c ** (1.0 / 2.4)) - 0.055


def write_mesh(name, index, mesh, colour_of_slot, shine=0.0, scale=1.0):
    """One StaticMesh with vertex colours. colour_of_slot(slot index) -> (r, g, b) sRGB."""
    mesh.calc_loop_triangles()
    corner_normals = [Vector(n.vector) for n in mesh.corner_normals] if hasattr(mesh, "corner_normals") else None
    verts, index_of, idx = [], {}, []
    lo, hi = Vector((1e9,) * 3), Vector((-1e9,) * 3)
    for tri in mesh.loop_triangles:
        base = colour_of_slot(tri.material_index)
        for corner, loop in zip(tri.vertices, tri.loops):
            p = mesh.vertices[corner].co * scale
            n = corner_normals[loop] if (corner_normals and tri.use_smooth) else Vector(tri.normal)
            shade = AMBIENT + (1.0 - AMBIENT) * max(0.0, n.dot(LIGHT))
            glint = shine * max(0.0, n.dot(LIGHT)) ** 12
            rgb = tuple(max(0, min(255, int(round(255 * min(1.0, c * shade + glint))))) for c in base)
            key = (round(p.x, 4), round(p.y, 4), round(p.z, 4), round(n.x, 3), round(n.y, 3), round(n.z, 3), rgb)
            if key not in index_of:
                index_of[key] = len(verts)
                verts.append((to_octave(p), to_octave(n), rgb))
                for k in range(3):
                    lo[k], hi[k] = min(lo[k], to_octave(p)[k]), max(hi[k], to_octave(p)[k])
            idx.append(index_of[key])

    centre = (lo + hi) * 0.5
    radius = max((Vector(v[0]) - centre).length for v in verts)
    d = header(TYPE_STATICMESH, UUID_BASE + 1 + index, name)
    d += u32(len(verts)) + u32(len(idx)) + u32(1)
    d += asset_ref(UUID_MAT, "M_StageVertex")
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
    print("  %-26s %6d verts %6d tris %7.1f KB" % (name, len(verts), len(idx) // 3, len(d) / 1024.0))


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


def main():
    os.makedirs(ASSETS, exist_ok=True)
    name = "Stage%d_seed%d" % (STAGE, GAUNTLET_SEED[STAGE])
    data = json.load(open(os.path.join(STAGES, name + ".json"), encoding="utf-8"))
    palette = stage_palettes.palette(STAGE)

    print("\nmeshes -> %s" % ASSETS)
    write_material()
    pieces = grl.load_pieces()
    for i, (piece, p) in enumerate(pieces.items()):
        slots = [m.name.split(".")[0] if m else "" for m in p["mesh"].materials]
        colours = [palette["materials"].get(n, (1.0, 0.0, 1.0)) for n in slots]
        write_mesh("SM_Piece_%s_P%d" % (piece, STAGE), 16 * STAGE + i, p["mesh"], lambda k, c=colours: c[k])

    def load(blend, mesh):
        with bpy.data.libraries.load(blend) as (src, dst):
            dst.meshes = [n for n in src.meshes if n == mesh]
        return dst.meshes[0]

    ring, bomb = load(RING_BLEND, "Ring"), load(BOMB_BLEND, "Bomb")
    write_mesh("SM_Ring", 200, ring, lambda k: (1.0, 0.78, 0.08), shine=0.55)
    from gen_stage import RAINBOW
    for i, c in enumerate(RAINBOW):
        write_mesh("SM_RingRainbow_%d" % i, 210 + i, ring, lambda k, c=c: c, shine=0.4)
    bomb_colours = [tuple(linear_to_srgb(x) for x in m.diffuse_color[:3]) for m in bomb.materials]
    write_mesh("SM_Bomb", 220, bomb, lambda k: bomb_colours[k], shine=0.25)
    write_mesh("SM_PlayerBall", 221, simple("Ball", lambda bm: bmesh.ops.create_icosphere(bm, subdivisions=3, radius=1.7)),
               lambda k: (0.12, 0.30, 0.95), shine=0.5)
    write_mesh("SM_Emerald", 222, simple("Emerald", octahedron), lambda k: (0.10, 0.85, 0.95), shine=0.6)

    # The track: where each piece goes, and the centre line frame by frame.
    paths = piece_paths()
    chain = ChainPath([paths[n] for n in data["pieces"]])
    piece_list = []
    for piece, (start, origin, path) in zip(data["pieces"], chain.parts):
        q = origin.to_quaternion()
        piece_list.append(dict(mesh="SM_Piece_%s_P%d" % (piece, STAGE), pos=list(to_octave(origin.translation)),
                               quat=[q.x, q.z, -q.y, q.w], first_frame=start / rm.STEP))
    frames = int(math.floor(chain.length / rm.STEP)) + 1
    path_list = []
    for f in range(frames + 1):
        m = chain.frame(min(f * rm.STEP, chain.length))
        path_list.append(list(to_octave(m.translation)) + list(to_octave(m.col[0].xyz)) + list(to_octave(m.col[2].xyz)))

    sections = []
    for sec in data["sections"]:
        sections.append(dict(first_frame=sec["first_frame"], check_frame=sec["check_frame"], last_frame=sec["last_frame"],
                             quota=sec["quota"], asks=sec["asks"], rings=sec["rings"], leads_to=sec["leads_to"],
                             objects=[[o[0], o[1], 1 if o[2] == rm.BOMB else 0] for o in sec["objects"]]))
    arch = data["sections"][0]["ring_check"]["rainbow_arch"]
    table = dict(
        name=name, stage=STAGE, step=rm.STEP, frames=frames,
        pipe_radius=rm.PIPE_RADIUS, hover=rm.HOVER,
        angle_00_side=-1 if rm.ANGLE_00_SIDE == "right" else 1,
        arch=dict(rings=arch["rings"], reach=rm.PIPE_RADIUS + 1.6, from_deg=12.0, ring_scale=arch["ring_scale"],
                  toward_player=0.72, steps_per_second=arch["steps_per_second"]),
        sky=palette["sky"], pieces=piece_list, sections=sections, path=path_list)
    out = os.path.join(PROJ, "Scripts", "StageData%d.lua" % STAGE)
    open(out, "w", encoding="ascii", newline="\n").write(
        "-- Written by native/export_to_octave.py from %s.json. Do not edit by hand.\n"
        "-- path[i] = { px,py,pz, fx,fy,fz, ux,uy,uz } for frame i-1: the floor's centre line, forward, up.\n"
        "-- objects = { frame, angle (256ths from the floor's centre line), 0 ring | 1 bomb }\n"
        "StageData%d = %s\n" % (name, STAGE, lua(table)))
    print("\nstage -> %s (%d pieces, %d frames, %d objects, %.0f KB)" % (
        out, len(piece_list), frames, sum(len(x["objects"]) for x in sections), os.path.getsize(out) / 1024.0))


main()
