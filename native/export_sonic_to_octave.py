"""Export Sonic into the Octave project, animated, as ONE MESH PER FRAME.

    blender -b external/sonic/Sonic_Rigged_Anim.blend --python native/export_sonic_to_octave.py

    -> proj/Assets/Sonic/T_Sonic.oct                  his ten little textures, in one
       proj/Assets/Sonic/M_Sonic.oct
       proj/Assets/Sonic/SM_Sonic_Run_00..15.oct       the run cycle, a mesh a frame
       proj/Assets/Sonic/SM_Sonic_Thumbs_00..15.oct    running with the thumbs up
       proj/Assets/Sonic/SM_Sonic_Idle_00.oct          standing

WHY A MESH PER FRAME. The engine has skinned meshes, and Sonic has a rig; the obvious export
is bones and keys. But this project animates by swapping frames everywhere else -- the sky is
384 textures, the rainbow arch is nine meshes changing places -- for the reason the sky's own
notes give: it is the one method with nothing to get wrong, and a GameCube can afford it.
Sonic is 683 polygons and his run is 16 frames, so the whole cycle is a few hundred KB, where
a skinned export would mean matching the engine's bone spaces, key spaces and root transform
blind. SpecialStage.lua shows frame (time x 24) mod 16, which is exactly what Blender plays.

Each frame is the rig posed by its action and the mesh read back from Blender AS BLENDER
DEFORMS IT, so what runs in the game is what was animated, hand finishing and all.

His ten textures (the biggest is 48 x 24) are packed into one 256 x 256 sheet, each blown up
to a 64 x 64 cell and sampled without filtering, so they stay as crisp as the originals and
one material serves the lot. A face's UVs are wrapped into 0-1 and moved into its cell.

Exported facing +X with his feet at the origin and Z up (then to Octave's axes like
everything else), about SONIC_HEIGHT tall, so the game can stand him on the pipe directly.
"""

import math
import os
import struct
import sys

import bpy
import numpy as np
from mathutils import Matrix, Vector

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.abspath(os.path.join(HERE, "..", "proj", "Assets", "Sonic"))

SONIC_HEIGHT = 4.6          # world units, standing. The pipe is 10 in radius; a ring is 2.5 across.
CELL, SHEET = 64, 256       # the texture sheet: 4 x 4 cells
ANIMATIONS = (("Run", "Run", None), ("Thumbs", "RunThumbsUp", None), ("Idle", "Idle", 1))

MAGIC, VERSION = 0x4F435421, 13
TYPE_TEXTURE, TYPE_STATICMESH, TYPE_MATERIALLITE = 0xCDBBDA30, 0xD41D0D1D, 0xA3ED4C6F
UUID_BASE = 0x51C0FFEE00004000
UUID_TEX, UUID_MAT = UUID_BASE, UUID_BASE + 1


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


def to_octave(v):
    return (v[0], v[2], -v[1])


# ---------------------------------------------------------------------------- textures
def build_sheet(mesh):
    """One sheet for every image the mesh's materials use. Returns {material slot: (cx, cy)}."""
    sheet = np.zeros((SHEET, SHEET, 4), dtype=np.float32)
    sheet[:, :, 3] = 1.0
    cell_of_image, cell_of_slot = {}, {}
    for slot, mat in enumerate(mesh.materials):
        image = None
        if mat and mat.node_tree:
            for node in mat.node_tree.nodes:
                if node.type == 'TEX_IMAGE' and node.image:
                    image = node.image
                    break
        key = image.name if image else "(none)"
        if key not in cell_of_image:
            n = len(cell_of_image)
            cx, cy = n % (SHEET // CELL), n // (SHEET // CELL)
            cell_of_image[key] = (cx, cy)
            if image is not None and image.size[0] > 0:
                w, h = image.size
                px = np.array(image.pixels[:], dtype=np.float32).reshape(h, w, 4)[::-1]      # top row first
                ys = (np.arange(CELL) * h // CELL)
                xs = (np.arange(CELL) * w // CELL)
                sheet[cy * CELL:(cy + 1) * CELL, cx * CELL:(cx + 1) * CELL] = px[ys][:, xs]  # nearest
            else:
                sheet[cy * CELL:(cy + 1) * CELL, cx * CELL:(cx + 1) * CELL] = (0.8, 0.8, 0.8, 1.0)
        cell_of_slot[slot] = cell_of_image[key]
    sheet[:, :, 3] = 1.0                                   # opaque: he has no cut-outs
    pixels = (np.clip(sheet, 0.0, 1.0) * 255.0 + 0.5).astype(np.uint8).tobytes()
    d = header(TYPE_TEXTURE, UUID_TEX, "T_Sonic")
    d += u32(SHEET) + u32(SHEET) + u32(1) + u32(1)
    d += u32(2) + u32(0) + u32(0)                          # RGBA8, NEAREST, clamp
    d += u8(0) + u8(0) + u8(1)                             # no mips, not a render target, sRGB
    d += u8(1) + u8(1)                                     # keep it uncompressed on console; no step down
    d += pixels
    open(os.path.join(OUT, "T_Sonic.oct"), "wb").write(d)
    print("  T_Sonic: %d images in a %d x %d sheet" % (len(cell_of_image), SHEET, SHEET))
    return cell_of_slot


def write_material():
    d = header(TYPE_MATERIALLITE, UUID_MAT, "M_Sonic")
    d += u32(0)                     # numParameters
    d += u32(1)                     # Lit: he is a character, he should sit in the stage's light
    d += u32(0)                     # Opaque
    d += u32(0)                     # VertexColorMode::None
    d += u32(1)                     # numTextures
    d += asset_ref(UUID_TEX, "T_Sonic") + u8(0) + u8(1)     # uv0, modulate
    for _ in range(3):
        d += null_ref() + u8(0) + u8(1)
    for _ in range(2):
        d += f32(0) + f32(0) + f32(1) + f32(1)
    d += f32(1) + f32(1) + f32(1) + f32(1)
    d += f32(1) + f32(0) + f32(0) + f32(0)
    d += f32(1.0) + f32(0.0) + f32(0.45) + f32(0.15)        # fresnelPower, emission, wrapLighting, specular
    d += u32(2) + f32(1.0) + f32(0.5) + f32(24.0)
    d += i32(0)
    d += u8(0) + u8(0) + u8(1)
    d += u8(0)                      # no culling: the model has single-sided bits
    open(os.path.join(OUT, "M_Sonic.oct"), "wb").write(d)


# ------------------------------------------------------------------------------ meshes
def write_frame(name, index, mesh, world, cell_of_slot, fix):
    mesh.calc_loop_triangles()
    uv = mesh.uv_layers.active.data if mesh.uv_layers.active else None
    normals = [Vector(n.vector) for n in mesh.corner_normals]
    rot = (fix @ world).to_3x3()
    verts, index_of, idx = [], {}, []
    inset = 0.5 / SHEET
    for tri in mesh.loop_triangles:
        cx, cy = cell_of_slot.get(tri.material_index, (0, 0))
        # A face whose UVs lie outside 0-1 is moved back as a WHOLE, by whole numbers, so its
        # three corners stay the same distance apart. Wrapping each corner on its own (u % 1)
        # was the first version, and it turns an exact 1.0 into 0.0: his shoes are mapped 0 to 1
        # edge to edge, so every shoe face collapsed onto one column of its texture, which is
        # red, and the white strap and the buckle were gone.
        tri_uv = [tuple(uv[loop].uv) if uv else (0.0, 0.0) for loop in tri.loops]
        shift_u = math.floor(min(t[0] for t in tri_uv) + 1e-6)
        shift_v = math.floor(min(t[1] for t in tri_uv) + 1e-6)
        for (corner, loop), (u, v) in zip(zip(tri.vertices, tri.loops), tri_uv):
            p = fix @ (world @ mesh.vertices[corner].co)
            n = (rot @ (normals[loop] if tri.use_smooth else Vector(tri.normal))).normalized()
            u, v = u - shift_u, v - shift_v
            su = (cx + min(max(u, 0.0), 1.0)) * CELL / SHEET
            sv = (cy + (1.0 - min(max(v, 0.0), 1.0))) * CELL / SHEET         # the sheet's top row is first
            su = min(max(su, cx * CELL / SHEET + inset), (cx + 1) * CELL / SHEET - inset)
            sv = min(max(sv, cy * CELL / SHEET + inset), (cy + 1) * CELL / SHEET - inset)
            key = (round(p.x, 4), round(p.y, 4), round(p.z, 4), round(n.x, 3), round(n.y, 3), round(n.z, 3),
                   round(su, 5), round(sv, 5))
            if key not in index_of:
                index_of[key] = len(verts)
                verts.append((to_octave(p), to_octave(n), su, sv))
            idx.append(index_of[key])

    pts = [Vector(v[0]) for v in verts]
    lo = Vector((min(p.x for p in pts), min(p.y for p in pts), min(p.z for p in pts)))
    hi = Vector((max(p.x for p in pts), max(p.y for p in pts), max(p.z for p in pts)))
    centre = (lo + hi) * 0.5
    d = header(TYPE_STATICMESH, UUID_BASE + 16 + index, name)
    d += u32(len(verts)) + u32(len(idx)) + u32(1)
    d += asset_ref(UUID_MAT, "M_Sonic")
    d += u8(0) + u8(0)                                      # no triangle collision; no vertex colour
    for p, n, su, sv in verts:
        d += f32(p[0]) + f32(p[1]) + f32(p[2]) + f32(su) + f32(sv) + f32(0) + f32(0)
        d += f32(n[0]) + f32(n[1]) + f32(n[2])
    for i in idx:
        d += u32(i)
    d += u8(0) + u32(0)
    d += f32(centre.x) + f32(centre.y) + f32(centre.z) + f32(max((p - centre).length for p in pts) * 1.2)
    open(os.path.join(OUT, name + ".oct"), "wb").write(d)
    return len(verts), len(idx) // 3


def main():
    os.makedirs(OUT, exist_ok=True)
    scene = bpy.context.scene
    body = bpy.data.objects["Sonic"]
    rig = bpy.data.objects["Armature"]
    print("\nSonic -> %s" % OUT)
    cell_of_slot = build_sheet(body.data)
    write_material()

    def pose(action_name, frame):
        action = bpy.data.actions[action_name]
        rig.animation_data.action = action
        if hasattr(rig.animation_data, "action_slot") and len(getattr(action, "slots", [])):
            rig.animation_data.action_slot = action.slots[0]
        scene.frame_set(int(frame))
        dg = bpy.context.evaluated_depsgraph_get()
        shown = body.evaluated_get(dg)
        return shown.to_mesh(), shown.matrix_world.copy(), shown

    # Which way he faces, and how big he is, from him standing. Sonic_06 and Sonic_07 are his
    # SHOES (not, as first assumed, his eyes -- which is how the shoe bug went unseen): his
    # toes are in front of the middle of him, where his quills are behind it.
    mesh, world, shown = pose("Idle", 1)
    pts = [world @ v.co for v in mesh.vertices]
    lo = Vector((min(p.x for p in pts), min(p.y for p in pts), min(p.z for p in pts)))
    hi = Vector((max(p.x for p in pts), max(p.y for p in pts), max(p.z for p in pts)))
    eye_slots = [i for i, m in enumerate(body.data.materials) if m and m.name in ("Sonic_06", "Sonic_07")]
    eyes = [world @ mesh.vertices[v].co for poly in mesh.polygons if poly.material_index in eye_slots for v in poly.vertices]
    middle = (lo + hi) * 0.5
    front = (sum(eyes, Vector()) / len(eyes) - middle) if eyes else Vector((0, -1, 0))
    front.z = 0.0
    yaw = math.atan2(front.y, front.x)
    scale = SONIC_HEIGHT / (hi.z - lo.z)
    fix = (Matrix.Scale(scale, 4) @ Matrix.Rotation(-yaw, 4, 'Z')
           @ Matrix.Translation((-middle.x, -middle.y, -lo.z)))
    print("  standing %.2f tall, facing %.0f degrees from +X; scaled x%.3f to %.1f" % (
        hi.z - lo.z, math.degrees(yaw), scale, SONIC_HEIGHT))
    shown.to_mesh_clear()

    index = 0
    for short, action_name, only in ANIMATIONS:
        action = bpy.data.actions[action_name]
        first, last = int(action.frame_range[0]), int(action.frame_range[1])
        frames = [only] if only else list(range(first, last))      # the last frame IS the first, again
        for k, frame in enumerate(frames):
            mesh, world, shown = pose(action_name, frame)
            nv, nt = write_frame("SM_Sonic_%s_%02d" % (short, k), index, mesh, world, cell_of_slot, fix)
            shown.to_mesh_clear()
            index += 1
        print("  %-7s %2d frames (%s %d-%d), %d verts %d tris each" % (short, len(frames), action_name, first, last, nv, nt))


main()
