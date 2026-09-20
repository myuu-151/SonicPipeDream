"""Model the gold ring.

    blender -b --python native/gen_ring.py

Writes external/ring/Ring.blend. A torus standing upright with its hole facing along X,
which is the way the track runs, so a ring laid on the track faces the player. Origin
at its centre, so it spins in place about Z.

One mesh, ONE material slot. How the ring looks -- the gold, the shine -- is made in
Octave, with its own material (specular, fresnel); the colour here is only a
placeholder so the ring is not grey in Blender. It was briefly banded into three
painted-on materials to fake a highlight, which is the engine's job, not the mesh's.
"""

import math
import os

import bmesh
import bpy

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.abspath(os.path.join(HERE, "..", "external", "ring", "Ring.blend"))

RADIUS = 1.0               # centre of the ring to the centre of its tube
TUBE = 0.24                # the tube's own radius; classic rings are chunky
AROUND = 24                # segments round the ring
ACROSS = 10                # segments round the tube

COLOURS = {
    "Ring_Gold": (1.000, 0.760, 0.050),      # placeholder; the real material is Octave's
}
SLOTS = list(COLOURS)


def srgb_to_linear(c):
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def make_material(name, rgb):
    mat = bpy.data.materials.new(name)
    lin = tuple(srgb_to_linear(c) for c in rgb) + (1.0,)
    mat.diffuse_color = lin
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    if bsdf is not None:
        bsdf.inputs["Base Color"].default_value = lin
        bsdf.inputs["Metallic"].default_value = 0.0
        bsdf.inputs["Roughness"].default_value = 0.4
    return mat


def main():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    mats = [make_material(n, COLOURS[n]) for n in SLOTS]

    bm = bmesh.new()
    # The ring lies in the YZ plane, so its axis -- the way the hole faces -- is X.
    grid = []
    for i in range(AROUND):
        a = 2.0 * math.pi * i / AROUND
        loop = []
        for j in range(ACROSS):
            t = 2.0 * math.pi * j / ACROSS
            r = RADIUS + TUBE * math.cos(t)
            loop.append(bm.verts.new((TUBE * math.sin(t), r * math.cos(a), r * math.sin(a))))
        grid.append(loop)

    for i in range(AROUND):
        ni = (i + 1) % AROUND
        for j in range(ACROSS):
            nj = (j + 1) % ACROSS
            f = bm.faces.new((grid[i][j], grid[i][nj], grid[ni][nj], grid[ni][j]))
            f.smooth = True
            f.material_index = 0

    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    me = bpy.data.meshes.new("Ring")
    bm.to_mesh(me)
    bm.free()
    for m in mats:
        me.materials.append(m)

    ob = bpy.data.objects.new("Ring", me)
    bpy.context.scene.collection.objects.link(ob)

    used = {}
    for p in me.polygons:
        used[SLOTS[p.material_index]] = used.get(SLOTS[p.material_index], 0) + 1
    xs = [v.co.x for v in me.vertices]
    rs = [math.hypot(v.co.y, v.co.z) for v in me.vertices]
    print("\nring: %d verts, %d tris" % (len(me.vertices), sum(len(p.vertices) - 2 for p in me.polygons)))
    print("outer radius %.3f, hole radius %.3f, thickness along X %.3f"
          % (max(rs), min(rs), max(xs) - min(xs)))
    print("faces per colour:", used)

    # A light and a sky, so Rendered mode shows it as it should look.
    sun = bpy.data.objects.new("Sun", bpy.data.lights.new("Sun", 'SUN'))
    sun.data.energy = 3.0
    sun.rotation_euler = (math.radians(50), 0.0, math.radians(-40))
    bpy.context.scene.collection.objects.link(sun)
    world = bpy.data.worlds.new("World")
    world.use_nodes = True
    world.node_tree.nodes["Background"].inputs[0].default_value = (0.02, 0.06, 0.14, 1.0)
    bpy.context.scene.world = world
    bpy.context.scene.view_settings.view_transform = 'Standard'

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=OUT)
    print("saved", OUT)


main()
