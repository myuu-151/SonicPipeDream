"""Bend the half-pipe along a curve, keeping its three objects in step.

    blender -b <scene.blend> --python native/curve_halfpipe.py -- <out.blend>

A Curve modifier places a mesh along the curve by where it sits relative to its
OBJECT'S ORIGIN. The pipe, rails and sphere arches are separate objects, and if
their origins differ, the same curve carries each from a different starting
distance and they part company on the first bend -- the array drift all over
again. So the objects' positions are baked into their meshes first, leaving all
three origins, and the curve's, at the same point.

Then a starter curve, HP_Track, and a Curve modifier on each object after its
array. Edit HP_Track's points to shape the stage; nothing else needs touching.
"""

import math
import sys

import bpy
from mathutils import Matrix, Vector

OUT = sys.argv[sys.argv.index("--") + 1]
NAMES = ("HalfPipeSection.001", "HalfPipeSection.002", "HalfPipeSection.003")

for ob in bpy.data.objects:
    if ob.mode != 'OBJECT':
        bpy.context.view_layer.objects.active = ob
        bpy.ops.object.mode_set(mode='OBJECT')

# --- 1. one shared origin -----------------------------------------------------------
for name in NAMES:
    ob = bpy.data.objects[name]
    if ob.location.length > 1e-9:
        ob.data.transform(Matrix.Translation(ob.location))
        print("baked %-22s offset (%.4f, %.4f, %.4f) into its mesh" % ((name,) + tuple(ob.location)))
        ob.location = (0.0, 0.0, 0.0)

# --- 2. the track -------------------------------------------------------------------
old = bpy.data.objects.get("HP_Track")
if old is not None:
    bpy.data.objects.remove(old, do_unlink=True)
cu = bpy.data.curves.new("HP_Track", 'CURVE')
cu.dimensions = '3D'
cu.resolution_u = 32
# Z-Up keeps the pipe's floor pointing down through turns; banking is then a
# deliberate choice, made with the points' Tilt, rather than something the curve
# does on its own as it winds.
cu.twist_mode = 'Z_UP'
sp = cu.splines.new('BEZIER')
points = [(0, 0, 0), (70, 0, 0), (140, 28, 6), (210, 40, 0), (290, 12, -8)]
sp.bezier_points.add(len(points) - 1)
for bp, co in zip(sp.bezier_points, points):
    bp.co = co
    bp.handle_left_type = bp.handle_right_type = 'AUTO'
track = bpy.data.objects.new("HP_Track", cu)
bpy.context.scene.collection.objects.link(track)

# --- 3. a Curve modifier on each, after its array -----------------------------------
for name in NAMES:
    ob = bpy.data.objects[name]
    for m in [m for m in ob.modifiers if m.type == 'CURVE']:
        ob.modifiers.remove(m)
    mod = ob.modifiers.new("Track", 'CURVE')
    mod.object = track
    mod.deform_axis = 'POS_X'
bpy.context.view_layer.update()

# --- 4. check the bend kept them together -------------------------------------------
def evaluated_points(ob, curve_on):
    for m in ob.modifiers:
        if m.type == 'CURVE':
            m.show_viewport = curve_on
    bpy.context.view_layer.update()
    ev = ob.evaluated_get(bpy.context.evaluated_depsgraph_get())
    me = ev.to_mesh()
    pts = [v.co.copy() for v in me.vertices]
    ev.to_mesh_clear()
    return pts


def groups_by_x(straight, step, first):
    """Vertex indices of each copy, found on the STRAIGHT mesh where x still means
    distance along the pipe; the same indices are valid once it is bent."""
    out = {}
    for i, p in enumerate(straight):
        k = int(round((p.x - first) / step))
        if abs(p.x - (first + k * step)) < 1.6:
            out.setdefault(k, []).append(i)
    return out


pipe, spheres = bpy.data.objects[NAMES[0]], bpy.data.objects[NAMES[2]]
px = [v.co.x for v in pipe.data.vertices]
pitch = max(px) - min(px)
sx = [v.co.x for v in spheres.data.vertices]
arch0 = (min(sx) + max(sx)) * 0.5

p_str, s_str = evaluated_points(pipe, False), evaluated_points(spheres, False)
p_bent, s_bent = evaluated_points(pipe, True), evaluated_points(spheres, True)
# Only the pipe's rim-height points near each hoop, so both centroids sit over
# the centre line and differ only in height.
hoops = groups_by_x(p_str, pitch, arch0)
arches = groups_by_x(s_str, pitch, arch0)

centres = []
for k in sorted(set(hoops) & set(arches)):
    h = sum((p_bent[i] for i in hoops[k]), Vector()) / len(hoops[k])
    a = sum((s_bent[i] for i in arches[k]), Vector()) / len(arches[k])
    centres.append((k, h, a))

worst = 0.0
for n, (k, h, a) in enumerate(centres):
    nxt = centres[min(n + 1, len(centres) - 1)][1]
    prv = centres[max(n - 1, 0)][1]
    tangent = (nxt - prv).normalized()
    along = abs((a - h).dot(tangent))
    worst = max(worst, along)
    print("copy %d: arch is %.4f along the track from its hoop" % (k, along))
print("worst arch-to-hoop slip along the track: %.4f (pitch is %.3f)" % (worst, pitch))

bpy.ops.wm.save_as_mainfile(filepath=OUT)
print("saved", OUT)
