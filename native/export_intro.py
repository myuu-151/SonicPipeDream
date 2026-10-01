"""Export the intro (the emblem and Sonic popping up behind its ribbon) into the Octave project.

    blender -b external/intro/Intro.blend --python native/export_intro.py

    -> proj/Assets/Intro/T_IntroWings, T_IntroRing, T_IntroRibbon     the emblem's three textures
       proj/Assets/Intro/M_IntroWings, M_IntroRing, M_IntroRibbon     unlit, one texture each
       proj/Assets/Intro/SM_IntroWings, SM_IntroRing, SM_IntroRibbon  the emblem, in three pieces
       proj/Assets/Intro/SM_SonicIntro_00..95                        Sonic, a mesh a frame
       external/intro/export/*.png                                   the renders the textures came from

Intro.blend is only read, never saved.

THE EMBLEM. Its look is Blender's -- chrome wings mirroring a studio, glossy plastic. The ring
(with its rims and studs) and the ribbon are each rendered alone, straight on, and that picture
is laid back onto its own mesh from the front: every vertex takes the point of the picture in
front of it. The wings are chrome for real: a matcap (see CHROME). Seen from the front it is the render; turned a little, as the title's camera does, the
shapes are real and move against each other, and the highlights ride on them. The pictures'
empty edges are filled outward with the nearest colour, so nothing dark creeps in at a seam.

SONIC. As export_sonic_to_octave.py does it: the rig posed by IntroPop, frame by frame, the mesh
read back as Blender deforms it (the eye's shape key included), on the same texture sheet and
material (T_Sonic, M_Sonic: checked, and the run stops if they would differ). In Blender he is
drawn only above CUT_Z, which is how he rises out from behind the ribbon; here every triangle is
cut at that height instead, and what is below it is not exported.

Both stay where they are in Blender (no scaling), turned to Octave's axes as everything else is:
the emblem's middle is the origin, the camera looks at it from +Z.
"""
import math
import os
import struct

import bpy
import numpy as np
from mathutils import Vector

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, ".."))
OUT = os.path.join(ROOT, "proj", "Assets", "Intro")
RENDERS = os.path.join(ROOT, "external", "intro", "export")
SONIC_SHEET = os.path.join(ROOT, "proj", "Assets", "Sonic", "T_Sonic.oct")

ACTION = "IntroPop"
CUT_Z = -0.50               # Blender world height below which Sonic is not drawn (as in Intro.blend)
SHEET, CELL = 256, 64       # T_Sonic, as export_sonic_to_octave.py makes it

# piece: (objects, texture width in pixels). Its height follows the piece's shape. The wings are
# chrome: not a picture of them but a MATCAP -- a chrome ball in the same studio -- that the engine
# maps by which way each point faces the camera (MaterialLite UV map 2), so they mirror as it moves.
CHROME = {"Wings"}
MATCAP = 256
CHROME_FLOOR = 0.45      # the darkest the matcap goes (0 black, 1 white)
UV_ENVIRONMENT = 2
PIECES = {
    "Wings": (lambda n: n.startswith("Feather"), 512),
    "Ring": (lambda n: n in ("Ring", "RimInner", "RimOuter") or n.startswith("Stud") or n.startswith("Pyramid"), 256),
    "Ribbon": (lambda n: n == "Ribbon", 512),
}
MARGIN = 0.03               # around each piece in its picture

MAGIC, VERSION = 0x4F435421, 13
TYPE_TEXTURE, TYPE_STATICMESH, TYPE_MATERIALLITE = 0xCDBBDA30, 0xD41D0D1D, 0xA3ED4C6F
UUID_PIECE = 0x51C0FFEE00600000          # + 16 * piece: texture, material, mesh
UUID_SONIC = 0x51C0FFEE00610000          # + frame
UUID_SONIC_TEX, UUID_SONIC_MAT = 0x51C0FFEE00004000, 0x51C0FFEE00004001   # T_Sonic, M_Sonic


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


def write(name, data):
    open(os.path.join(OUT, name + ".oct"), "wb").write(data)


# ------------------------------------------------------------------ writers
def write_texture(name, uuid, pixels_rgba8, w, h, linear=True):
    d = header(TYPE_TEXTURE, uuid, name)
    d += u32(w) + u32(h) + u32(1) + u32(1)
    d += u32(2) + u32(1 if linear else 0) + u32(0)          # RGBA8, filter, clamp
    d += u8(0) + u8(0) + u8(1)                              # no mips, not a render target, sRGB
    d += u8(1) + u8(1)                                      # uncompressed on console; no step down
    d += pixels_rgba8
    write(name, d)


def write_material(name, uuid, tex_name, tex_uuid, lit=False, uv_map=0):
    d = header(TYPE_MATERIALLITE, uuid, name)
    d += u32(0)                     # numParameters
    d += u32(1 if lit else 0)       # shading model: Unlit / Lit
    d += u32(0)                     # Opaque
    d += u32(0)                     # VertexColorMode::None
    d += u32(1)                     # numTextures
    d += asset_ref(tex_uuid, tex_name) + u8(uv_map) + u8(1)     # slot 0: its UVs, Modulate
    for _ in range(3):
        d += null_ref() + u8(0) + u8(1)
    for _ in range(2):
        d += f32(0) + f32(0) + f32(1) + f32(1)
    d += f32(1) + f32(1) + f32(1) + f32(1)
    d += f32(1) + f32(0) + f32(0) + f32(0)
    d += f32(1.0) + f32(0.0) + f32(0.45) + f32(0.15)
    d += u32(2) + f32(1.0) + f32(0.5) + f32(24.0)
    d += i32(0)
    d += u8(0) + u8(0) + u8(1)
    d += u8(0)                      # no culling
    write(name, d)


def write_mesh(name, uuid, mat_name, mat_uuid, verts, idx):
    """verts: (position, normal, u, v) in Blender's axes."""
    pts = [Vector(to_octave(p)) for p, _, _, _ in verts]
    lo = Vector((min(p.x for p in pts), min(p.y for p in pts), min(p.z for p in pts)))
    hi = Vector((max(p.x for p in pts), max(p.y for p in pts), max(p.z for p in pts)))
    centre = (lo + hi) * 0.5
    d = header(TYPE_STATICMESH, uuid, name)
    d += u32(len(verts)) + u32(len(idx)) + u32(1)
    d += asset_ref(mat_uuid, mat_name)
    d += u8(0) + u8(0)                                      # no triangle collision; no vertex colour
    for p, n, su, sv in verts:
        p, n = to_octave(p), to_octave(n)
        d += f32(p[0]) + f32(p[1]) + f32(p[2]) + f32(su) + f32(sv) + f32(0) + f32(0)
        d += f32(n[0]) + f32(n[1]) + f32(n[2])
    for i in idx:
        d += u32(i)
    d += u8(0) + u32(0)
    d += f32(centre.x) + f32(centre.y) + f32(centre.z) + f32(max((p - centre).length for p in pts) * 1.2)
    write(name, d)


class Builder:
    """Triangles in, shared vertices out."""
    def __init__(self):
        self.verts, self.idx, self.index_of = [], [], {}

    def add(self, p, n, su, sv):
        key = (round(p.x, 4), round(p.y, 4), round(p.z, 4), round(n.x, 3), round(n.y, 3), round(n.z, 3),
               round(su, 5), round(sv, 5))
        if key not in self.index_of:
            self.index_of[key] = len(self.verts)
            self.verts.append((p.copy(), n.copy(), su, sv))
        self.idx.append(self.index_of[key])


# ------------------------------------------------------------------ the emblem
def bounds(objs, dg):
    lo, hi = Vector((1e9, 1e9, 1e9)), Vector((-1e9, -1e9, -1e9))
    for ob in objs:
        ev = ob.evaluated_get(dg)
        me = ev.to_mesh()
        for v in me.vertices:
            p = ev.matrix_world @ v.co
            lo = Vector(map(min, lo, p))
            hi = Vector(map(max, hi, p))
        ev.to_mesh_clear()
    return lo, hi


def fill_edges(px):
    """Spread the colour of the drawn pixels into the empty ones round them (alpha stays)."""
    rgb, a = px[:, :, :3].copy(), px[:, :, 3]
    known = a > 0.5
    rgb[~known] = 0.0
    for _ in range(64):
        if known.all():
            break
        acc = np.zeros_like(rgb)
        cnt = np.zeros(known.shape, dtype=np.float32)
        for dy in (-1, 0, 1):
            for dx in (-1, 0, 1):
                if dx == 0 and dy == 0:
                    continue
                k = np.roll(np.roll(known, dy, 0), dx, 1)
                c = np.roll(np.roll(rgb, dy, 0), dx, 1)
                acc += c * k[:, :, None]
                cnt += k
        grow = (~known) & (cnt > 0)
        rgb[grow] = acc[grow] / cnt[grow][:, None]
        known = known | grow
    out = px.copy()
    out[:, :, :3] = np.where(px[:, :, 3:4] > 0.5, px[:, :, :3], rgb)
    out[:, :, 3] = 1.0
    return out


def render_matcap(scene, path, material):
    """A chrome ball (the wings' own material) in the scene's studio, straight on, edge to edge."""
    bpy.ops.mesh.primitive_uv_sphere_add(segments=96, ring_count=48, radius=1.0, location=(0.0, 0.0, 40.0))
    ball = bpy.context.active_object
    bpy.ops.object.shade_smooth()
    ball.data.materials.append(material)
    shown = {o.name: o.hide_render for o in scene.objects}
    for o in scene.objects:
        if o.type in ("MESH", "ARMATURE"):
            o.hide_render = o is not ball
    cam = scene.camera
    keep = (cam.location.copy(), cam.rotation_euler.copy(), cam.data.type, cam.data.ortho_scale,
            scene.render.resolution_x, scene.render.resolution_y, scene.render.resolution_percentage,
            scene.render.film_transparent, scene.render.filepath)
    cam.location = (0.0, -30.0, 40.0)
    cam.rotation_euler = (math.pi / 2, 0.0, 0.0)
    cam.data.type, cam.data.ortho_scale = "ORTHO", 2.0
    scene.render.resolution_x = scene.render.resolution_y = MATCAP
    scene.render.resolution_percentage = 100
    scene.render.film_transparent = True
    scene.render.filepath = path
    bpy.ops.render.render(write_still=True)
    (cam.location, cam.rotation_euler, cam.data.type, cam.data.ortho_scale, scene.render.resolution_x,
     scene.render.resolution_y, scene.render.resolution_percentage, scene.render.film_transparent,
     scene.render.filepath) = keep
    for o in scene.objects:
        if o.name in shown:
            o.hide_render = shown[o.name]
    bpy.data.objects.remove(ball, do_unlink=True)


def render_piece(scene, objs, path, cx, cz, span_x, span_z, width, height):
    """The piece alone, straight on, filling the picture."""
    shown = {o.name: o.hide_render for o in scene.objects}
    for o in scene.objects:
        if o.type in ("MESH", "ARMATURE"):
            o.hide_render = not (o in objs)
    cam = scene.camera
    keep = (cam.location.copy(), cam.rotation_euler.copy(), cam.data.type, cam.data.ortho_scale,
            scene.render.resolution_x, scene.render.resolution_y, scene.render.resolution_percentage,
            scene.render.film_transparent, scene.render.filepath)
    cam.location = (cx, -30.0, cz)
    cam.rotation_euler = (math.pi / 2, 0.0, 0.0)
    cam.data.type = "ORTHO"
    cam.data.ortho_scale = span_x if width >= height else span_z
    scene.render.resolution_x, scene.render.resolution_y = width, height
    scene.render.resolution_percentage = 100
    scene.render.film_transparent = True
    scene.render.filepath = path
    bpy.ops.render.render(write_still=True)
    (cam.location, cam.rotation_euler, cam.data.type, cam.data.ortho_scale, scene.render.resolution_x,
     scene.render.resolution_y, scene.render.resolution_percentage, scene.render.film_transparent,
     scene.render.filepath) = keep
    for o in scene.objects:
        o.hide_render = shown[o.name]



def export_piece(index, piece, test, width, scene, dg):
    objs = [o for o in scene.objects if o.type == "MESH" and test(o.name)]
    for o in objs:                      # the game's mesh unsubdivided (Blender keeps it for its picture)
        for m in o.modifiers:
            if m.type == "SUBSURF":
                m.levels = 0
    dg = bpy.context.evaluated_depsgraph_get()
    dg.update()
    lo, hi = bounds(objs, dg)
    span_x = (hi.x - lo.x) * (1 + 2 * MARGIN)
    span_z = (hi.z - lo.z) * (1 + 2 * MARGIN)
    height = 4
    while height < width * span_z / span_x:
        height *= 2
    span_z = span_x * height / width                    # square pixels: the picture's height is the piece's, or more
    cx, cz = (lo.x + hi.x) * 0.5, (lo.z + hi.z) * 0.5
    x0, z1 = cx - span_x * 0.5, cz + span_z * 0.5

    chrome = piece in CHROME
    if chrome:
        width = height = MATCAP
        path = os.path.join(RENDERS, "Intro%sMatcap.png" % piece)
        render_matcap(scene, path, objs[0].active_material)
    else:
        path = os.path.join(RENDERS, "Intro%s.png" % piece)
        render_piece(scene, objs, path, cx, cz, span_x, span_z, width, height)

    img = bpy.data.images.load(path)
    px = np.array(img.pixels[:], dtype=np.float32).reshape(height, width, 4)[::-1]     # top row first
    bpy.data.images.remove(img)
    px = fill_edges(px)
    if chrome:
        # The studio's floor mirrors nearly black in the lower half of the ball, and the feathers'
        # undersides face it: on the screen that read as shading. Lifted, the chrome stays bright
        # all over, its highlights where they were.
        px[:, :, :3] = CHROME_FLOOR + (1.0 - CHROME_FLOOR) * px[:, :, :3]
    rgba = (np.clip(px, 0.0, 1.0) * 255.0 + 0.5).astype(np.uint8).tobytes()

    base = UUID_PIECE + 16 * index
    tex, mat, mesh = "T_Intro" + piece, "M_Intro" + piece, "SM_Intro" + piece
    write_texture(tex, base, rgba, width, height)
    write_material(mat, base + 1, tex, base, uv_map=UV_ENVIRONMENT if chrome else 0)

    # the mesh: every corner takes the point of the picture in front of it (unused by the chrome,
    # whose picture is placed by the engine)
    b = Builder()
    for ob in objs:
        ev = ob.evaluated_get(dg)
        me = ev.to_mesh()
        me.calc_loop_triangles()
        normals = [Vector(n.vector) for n in me.corner_normals]
        rot = ev.matrix_world.to_3x3()
        for tri in me.loop_triangles:
            for corner, loop in zip(tri.vertices, tri.loops):
                p = ev.matrix_world @ me.vertices[corner].co
                n = (rot @ (normals[loop] if tri.use_smooth else Vector(tri.normal))).normalized()
                b.add(p, n, (p.x - x0) / span_x, (z1 - p.z) / span_z)
        ev.to_mesh_clear()
    write_mesh(mesh, base + 2, mat, base + 1, b.verts, b.idx)
    print("  %-7s %d objects, %d verts %d tris, %d x %d texture" % (piece, len(objs), len(b.verts), len(b.idx) // 3, width, height))


# ------------------------------------------------------------------ Sonic
def sonic_cells(body):
    """Which cell of T_Sonic each material slot uses, worked out as export_sonic_to_octave.py
    does, and checked against the sheet it wrote: the frames must land on the same pictures."""
    sheet = np.zeros((SHEET, SHEET, 4), dtype=np.float32)
    cell_of_image, cell_of_slot = {}, {}
    for slot, mat in enumerate(body.data.materials):
        image = None
        if mat and mat.node_tree:
            for node in mat.node_tree.nodes:
                if node.type == "TEX_IMAGE" and node.image:
                    image = node.image
                    break
        key = image.name if image else "(none)"
        if key not in cell_of_image:
            n = len(cell_of_image)
            cx, cy = n % (SHEET // CELL), n // (SHEET // CELL)
            cell_of_image[key] = (cx, cy)
            if image is not None and image.size[0] > 0:
                w, h = image.size
                px = np.array(image.pixels[:], dtype=np.float32).reshape(h, w, 4)[::-1]
                ys = (np.arange(CELL) * h // CELL)
                xs = (np.arange(CELL) * w // CELL)
                sheet[cy * CELL:(cy + 1) * CELL, cx * CELL:(cx + 1) * CELL] = px[ys][:, xs]
            else:
                sheet[cy * CELL:(cy + 1) * CELL, cx * CELL:(cx + 1) * CELL] = (0.8, 0.8, 0.8, 1.0)
        cell_of_slot[slot] = cell_of_image[key]
    sheet[:, :, 3] = 1.0
    mine = (np.clip(sheet, 0.0, 1.0) * 255.0 + 0.5).astype(np.uint8).tobytes()
    theirs = open(SONIC_SHEET, "rb").read()[-len(mine):]
    if mine != theirs:
        raise SystemExit("Intro.blend's Sonic does not lay out T_Sonic as the game's Sonic does")
    return cell_of_slot


def clip_up(corners):
    """The part of a triangle at or above CUT_Z, as a fan of triangles. corners: (p, n, u, v)."""
    out = []
    for i in range(len(corners)):
        a, b = corners[i], corners[(i + 1) % len(corners)]
        da, db = a[0].z - CUT_Z, b[0].z - CUT_Z
        if da >= 0.0:
            out.append(a)
        if (da >= 0.0) != (db >= 0.0):
            t = da / (da - db)
            out.append((a[0].lerp(b[0], t), a[1].lerp(b[1], t).normalized(),
                        a[2] + (b[2] - a[2]) * t, a[3] + (b[3] - a[3]) * t))
    return [(out[0], out[k], out[k + 1]) for k in range(1, len(out) - 1)]


def export_sonic(scene, cells):
    body, rig = bpy.data.objects["Sonic"], bpy.data.objects["Armature"]
    action = bpy.data.actions[ACTION]
    rig.animation_data.action = action
    if hasattr(rig.animation_data, "action_slot") and len(getattr(action, "slots", [])):
        rig.animation_data.action_slot = action.slots[0]
    inset = 0.5 / SHEET
    first, last = scene.frame_start, scene.frame_end
    for k, frame in enumerate(range(first, last + 1)):
        scene.frame_set(frame)
        dg = bpy.context.evaluated_depsgraph_get()
        ev = body.evaluated_get(dg)
        me = ev.to_mesh()
        me.calc_loop_triangles()
        uv = me.uv_layers.active.data if me.uv_layers.active else None
        normals = [Vector(n.vector) for n in me.corner_normals]
        world = ev.matrix_world
        rot = world.to_3x3()
        b = Builder()
        for tri in me.loop_triangles:
            cx, cy = cells.get(tri.material_index, (0, 0))
            tri_uv = [tuple(uv[loop].uv) if uv else (0.0, 0.0) for loop in tri.loops]
            shift_u = math.floor(min(t[0] for t in tri_uv) + 1e-6)
            shift_v = math.floor(min(t[1] for t in tri_uv) + 1e-6)
            corners = []
            for (corner, loop), (u, v) in zip(zip(tri.vertices, tri.loops), tri_uv):
                p = world @ me.vertices[corner].co
                n = (rot @ (normals[loop] if tri.use_smooth else Vector(tri.normal))).normalized()
                u, v = u - shift_u, v - shift_v
                su = (cx + min(max(u, 0.0), 1.0)) * CELL / SHEET
                sv = (cy + (1.0 - min(max(v, 0.0), 1.0))) * CELL / SHEET
                su = min(max(su, cx * CELL / SHEET + inset), (cx + 1) * CELL / SHEET - inset)
                sv = min(max(sv, cy * CELL / SHEET + inset), (cy + 1) * CELL / SHEET - inset)
                corners.append((p, n, su, sv))
            for t in clip_up(corners):
                for c in t:
                    b.add(*c)
        ev.to_mesh_clear()
        name = "SM_SonicIntro_%02d" % k
        if not b.verts:                     # all of him below the ribbon: one tiny triangle, out of sight
            p = Vector((0.0, 0.5, CUT_Z - 1.0))
            for _ in range(3):
                b.add(p, Vector((0, -1, 0)), 0.0, 0.0)
        write_mesh(name, UUID_SONIC + k, "M_Sonic", UUID_SONIC_MAT, b.verts, b.idx)
    print("  Sonic   %d frames (%s %d-%d)" % (last - first + 1, ACTION, first, last))


def main():
    os.makedirs(OUT, exist_ok=True)
    os.makedirs(RENDERS, exist_ok=True)
    scene = bpy.context.scene
    print("\nIntro -> %s" % OUT)
    scene.frame_set(scene.frame_end)
    dg = bpy.context.evaluated_depsgraph_get()
    for i, (piece, (test, width)) in enumerate(PIECES.items()):
        export_piece(i, piece, test, width, scene, dg)
    if os.environ.get("INTRO_ONLY_EMBLEM") is None:        # (set it to leave Sonic's frames as they are)
        export_sonic(scene, sonic_cells(bpy.data.objects["Sonic"]))


main()
