"""Make the half-pipe's three arrays agree.

    blender -b <scene.blend> --python native/align_halfpipe_arrays.py -- <out.blend>

The pipe, the rails and the sphere arches are separate objects, each with its
own array. Set to a RELATIVE offset, each one steps by a multiple of its own
bounding box, and the three boxes are different sizes, so the spacings differ
and the copies walk apart down the pipe. No relative value fixes that exactly.

This gives all three the same ABSOLUTE step -- the pipe section's length -- and
then slides the decorations so every sphere arch sits on an orange hoop and
every rail sits midway between two hoops.
"""

import sys

import bpy

OUT = sys.argv[sys.argv.index("--") + 1]

PIPE, RAILS, SPHERES = "HalfPipeSection.001", "HalfPipeSection.002", "HalfPipeSection.003"

for ob in bpy.data.objects:
    if ob.mode != 'OBJECT':
        bpy.context.view_layer.objects.active = ob
        bpy.ops.object.mode_set(mode='OBJECT')

pipe = bpy.data.objects[PIPE]
pm = pipe.data
xs = [v.co.x for v in pm.vertices]
pitch = max(xs) - min(xs)

# The cross hoop is the only hoop-coloured band that is SHORT along the pipe;
# the lanes and trim in the same colour run its whole length.
hoop = None
for p in pm.polygons:
    if pm.materials[p.material_index].name != "HP_Hoop":
        continue
    vs = [pm.vertices[i].co for i in p.vertices]
    if all(v.z < 5.0 for v in vs):
        lo, hi = min(v.x for v in vs), max(v.x for v in vs)
        if hoop is None or (hi - lo) < (hoop[1] - hoop[0]):
            hoop = (lo, hi)
hoop_x = pipe.location.x + (hoop[0] + hoop[1]) * 0.5
print("pitch %.4f, hoop at x = %.4f" % (pitch, hoop_x))

# --- the pipe: same step, stated absolutely -------------------------------------
arr = next(m for m in pipe.modifiers if m.type == 'ARRAY')
arr.use_relative_offset = False
arr.use_constant_offset = True
arr.constant_offset_displace = (pitch, 0.0, 0.0)


def socket(mod, name):
    for it in mod.node_group.interface.items_tree:
        if getattr(it, "in_out", None) == 'INPUT' and it.name == name:
            return it.identifier
    raise KeyError(name)


def copy_centres(ob):
    """X centre of every copy the array really produces, from the evaluated mesh."""
    n = len(ob.data.vertices)
    dg = bpy.context.evaluated_depsgraph_get()
    ev = ob.evaluated_get(dg)
    me = ev.to_mesh()
    cx = []
    for k in range(len(me.vertices) // n):
        x = [me.vertices[i].co.x for i in range(k * n, (k + 1) * n)]
        cx.append(ob.location.x + (min(x) + max(x)) * 0.5)
    ev.to_mesh_clear()
    return sorted(cx)


def fix(ob, target_phase, label):
    mod = next(m for m in ob.modifiers if m.type == 'NODES')
    # In absolute mode the modifier steps by its "Translation" input; "Offset" is
    # only the multiplier used by Relative mode, and is left as it was.
    method, step = socket(mod, "Offset Method"), socket(mod, "Translation")
    mod[step] = (pitch, 0.0, 0.0)

    # The menu's stored number is not its position in the list, so find the
    # 'Offset' entry by what it does: the one that spaces the copies by exactly
    # the vector just given.
    chosen = None
    for cand in range(0, 8):
        mod[method] = cand
        ob.update_tag()
        bpy.context.view_layer.update()
        c = copy_centres(ob)
        if len(c) > 1 and all(abs((b - a) - pitch) < 1e-3 for a, b in zip(c, c[1:])):
            chosen = cand
            break
    assert chosen is not None, "%s: no Offset Method value gives an absolute step" % label

    # Slide the object so its copies land on the wanted phase, by the smallest move.
    first = copy_centres(ob)[0]
    err = ((first - target_phase + pitch * 0.5) % pitch) - pitch * 0.5
    ob.location.x -= err
    bpy.context.view_layer.update()
    c = copy_centres(ob)
    print("%s: method value %d, moved %.4f; copies at %s"
          % (label, chosen, -err, ", ".join("%.3f" % v for v in c)))


fix(bpy.data.objects[SPHERES], hoop_x, "spheres")
fix(bpy.data.objects[RAILS], hoop_x + pitch * 0.5, "rails  ")

count = arr.count
print("hoops  : " + ", ".join("%.3f" % (hoop_x + k * pitch) for k in range(count)))
print("between: " + ", ".join("%.3f" % (hoop_x + (k + 0.5) * pitch) for k in range(count)))

bpy.ops.wm.save_as_mainfile(filepath=OUT)
print("saved", OUT)
