"""Lay every ring and bomb module out on a stretch of pipe, to look at.

    blender -b external/halfpipe/TrackPiecesPack.blend \
        --python native/gen_ring_modules.py -- [sheet]

Writes external/ring/RingModules.blend. The pack is read, never written. With `sheet`
it also renders one picture per module into external/ring/preview/, from where the
player would be standing; native/make_ring_sheet.py gathers those onto one page.

The shapes themselves live in native/ring_modules.py, which knows nothing of Blender.
This only stands them up: one lane per module, side by side along Y, each a collection
`RM_<name>` holding an empty of that name at the module's start -- on the floor's centre
line, heading +X, the same joint as a track piece -- with its rings and bombs parented
to it. Every ring shares the one mesh from external/ring/Ring.blend.

There is no bomb model yet. `Bomb_Placeholder` is a dark ball, there to be replaced.
"""

import math
import os
import sys

import bmesh
import bpy
from mathutils import Vector

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import ring_modules as rm

args = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
SHEET = "sheet" in args

RING_BLEND = os.path.abspath(os.path.join(HERE, "..", "external", "ring", "Ring.blend"))
OUT = os.path.abspath(os.path.join(HERE, "..", "external", "ring", "RingModules.blend"))
PREVIEW = os.path.abspath(os.path.join(HERE, "..", "external", "ring", "preview"))

LANE = 60.0                 # between one module's pipe and the next
LEAD_IN = 8                 # frames of bare pipe before a module starts, for the camera
RING_SCALE = 1.0
BOMB_RADIUS = 1.3
TOP_VIEWS = ("Cluster", "TriangleBig", "Zigzag", "Snake", "Spiral", "Slalom")


def bake_straight():
    """The straight piece's pipe, rails and arches as one mesh, origin at its start."""
    curve = bpy.data.objects["TP_Straight"]
    dg = bpy.context.evaluated_depsgraph_get()
    bm = bmesh.new()
    materials = None
    for child in sorted(curve.children, key=lambda o: o.name):
        if child.type != 'MESH':
            continue
        me = bpy.data.meshes.new_from_object(child.evaluated_get(dg))
        me.transform(child.matrix_world)
        if materials is None:
            materials = list(me.materials)
        bm.from_mesh(me)
        bpy.data.meshes.remove(me)
    bmesh.ops.translate(bm, verts=bm.verts, vec=-curve.matrix_world.translation)
    out = bpy.data.meshes.new("PM_Straight")
    bm.to_mesh(out)
    bm.free()
    for m in materials or []:
        out.materials.append(m)
    return out


def load_ring():
    with bpy.data.libraries.load(RING_BLEND) as (src, dst):
        dst.meshes = [n for n in src.meshes if n == "Ring"]
    return dst.meshes[0]


def make_bomb():
    bm = bmesh.new()
    bmesh.ops.create_icosphere(bm, subdivisions=2, radius=BOMB_RADIUS)
    for f in bm.faces:
        f.smooth = True
    me = bpy.data.meshes.new("Bomb_Placeholder")
    bm.to_mesh(me)
    bm.free()
    mat = bpy.data.materials.new("Bomb_Placeholder")
    mat.diffuse_color = (0.02, 0.02, 0.03, 1.0)
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    if bsdf is not None:
        bsdf.inputs["Base Color"].default_value = (0.02, 0.02, 0.03, 1.0)
        bsdf.inputs["Roughness"].default_value = 0.25
    me.materials.append(mat)
    return me


def main():
    pipe = bake_straight()
    ring = load_ring()
    bomb = make_bomb()
    for ob in list(bpy.data.objects):
        bpy.data.objects.remove(ob, do_unlink=True)
    scene = bpy.context.scene

    lanes = {}
    for n, (name, module) in enumerate(rm.MODULES.items()):
        coll = bpy.data.collections.new("RM_" + name)
        scene.collection.children.link(coll)
        y = -n * LANE
        start = LEAD_IN * rm.STEP
        sections = int(math.ceil((LEAD_IN + rm.length(module) + 4) * rm.STEP / rm.SECTION)) + 1
        for s in range(sections):
            p = bpy.data.objects.new("RMPipe_%s_%d" % (name, s), pipe)
            p.location = (s * rm.SECTION, y, 0.0)
            p.hide_select = True
            coll.objects.link(p)

        root = bpy.data.objects.new("RM_" + name, None)
        root.empty_display_type = 'ARROWS'
        root.empty_display_size = 3.0
        root.location = (start, y, 0.0)
        coll.objects.link(root)
        for i, (frame, angle, kind) in enumerate(sorted(module)):
            ob = bpy.data.objects.new("%s_%s_%02d" % (name, kind, i), ring if kind == rm.RING else bomb)
            ob.parent = root
            ob.location = rm.local(frame, angle)
            if kind == rm.RING:
                ob.scale = (RING_SCALE,) * 3
            coll.objects.link(ob)
        lanes[name] = (y, start)

    sun = bpy.data.objects.new("Sun", bpy.data.lights.new("Sun", 'SUN'))
    sun.data.energy = 3.0
    sun.rotation_euler = (math.radians(35), math.radians(-25), 0.0)
    scene.collection.objects.link(sun)
    world = bpy.data.worlds.new("World")
    world.use_nodes = True
    world.node_tree.nodes["Background"].inputs[0].default_value = (0.03, 0.08, 0.20, 1.0)
    world.node_tree.nodes["Background"].inputs[1].default_value = 1.2
    scene.world = world
    scene.view_settings.view_transform = 'Standard'

    cam_data = bpy.data.cameras.new("RM_Camera")
    cam_data.lens, cam_data.clip_end = 18.0, 2000.0
    cam = bpy.data.objects.new("RM_Camera", cam_data)
    scene.collection.objects.link(cam)
    scene.camera = cam

    def aim(name):
        # From a little above head height, looking down the pipe at the module's middle,
        # so its rows read as rows and not as one ring behind another.
        y, start = lanes[name]
        pos = Vector((start - 5.0 * rm.FRAME, y, 9.5))
        target = Vector((start + min(0.5 * rm.length(rm.MODULES[name]), 5.0) * rm.STEP, y, 1.5))
        cam.location = pos
        cam.rotation_euler = (target - pos).to_track_quat('-Z', 'Y').to_euler()

    aim("Cluster")
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=OUT)
    print("\n%d modules, saved %s" % (len(lanes), OUT))

    if SHEET:
        for engine in ('BLENDER_EEVEE', 'BLENDER_EEVEE_NEXT'):
            try:
                scene.render.engine = engine
                break
            except TypeError:
                pass
        scene.render.resolution_x, scene.render.resolution_y = 480, 360
        scene.render.image_settings.file_format = 'PNG'
        os.makedirs(PREVIEW, exist_ok=True)
        for name in lanes:
            aim(name)
            scene.render.filepath = os.path.join(PREVIEW, name + ".png")
            bpy.ops.render.render(write_still=True)
        # and from straight above, which is how spacing is judged
        cam_data.type = 'ORTHO'
        for name in TOP_VIEWS:
            y, start = lanes[name]
            span = rm.length(rm.MODULES[name]) * rm.STEP
            cam_data.ortho_scale = max(span + 16.0, 40.0)
            cam.location = (start + span / 2.0, y, 120.0)
            cam.rotation_euler = (0.0, 0.0, 0.0)
            scene.render.filepath = os.path.join(PREVIEW, "top_" + name + ".png")
            bpy.ops.render.render(write_still=True)
        print("rendered", len(lanes), "previews to", PREVIEW)


main()
