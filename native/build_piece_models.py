"""Put the real half-pipe on every track piece.

    blender -b <TrackPieces.blend> --python native/build_piece_models.py -- \\
        <pipe source.blend> <out.blend>

For each TP_ curve in the pieces file, adds the pipe, the rails and the sphere arches,
repeated for as many sections as the piece is long and bent along that piece's curve.
Safe to run again after reshaping a curve: it only ever replaces the objects it made
(named TPM_...), never the curves.

A piece's model has to fit its curve exactly, from 0 to its length, or pieces laid
end to end would gap or overlap. The source pipe was modelled from x = -8.18, so the
meshes are shifted here to start at 0. That puts the hoop and its sphere arch in the
middle of each section and the rails on the seams between sections; each piece owns
the rail at the END of each of its sections, so none is ever built twice.
"""

import math
import sys

import bpy
from mathutils import Matrix, Vector

args = sys.argv[sys.argv.index("--") + 1:]
SOURCE, OUT = args[0], args[1]

PIPE, RAILS, SPHERES = "HalfPipeSection.001", "HalfPipeSection.002", "HalfPipeSection.003"


def clear_old():
    for ob in [o for o in bpy.data.objects if o.name.startswith("TPM_")]:
        bpy.data.objects.remove(ob, do_unlink=True)
    for me in [m for m in bpy.data.meshes if m.name.startswith("TPM_") and m.users == 0]:
        bpy.data.meshes.remove(me)


def load_source():
    with bpy.data.libraries.load(SOURCE, link=False) as (src, dst):
        dst.objects = [n for n in (PIPE, RAILS, SPHERES) if n in src.objects]
        dst.worlds = [n for n in src.worlds if n == "HP_Sky"]
    return {ob.name: ob for ob in dst.objects}, (dst.worlds[0] if dst.worlds else None)


def span_x(me):
    xs = [v.co.x for v in me.vertices]
    return min(xs), max(xs)


def main():
    clear_old()
    src, world = load_source()

    pipe_me = src[PIPE].data.copy()
    rails_me = src[RAILS].data.copy()
    spheres_me = src[SPHERES].data.copy()
    pipe_me.name, rails_me.name, spheres_me.name = "TPM_Pipe", "TPM_Rails", "TPM_Spheres"

    lo, hi = span_x(pipe_me)
    section = hi - lo
    shift = -lo
    pipe_me.transform(Matrix.Translation((shift, 0.0, 0.0)))
    spheres_me.transform(Matrix.Translation((shift, 0.0, 0.0)))
    # The rails sit between hoops, which is on the seam. Centre them on the END seam.
    r_lo, r_hi = span_x(rails_me)
    rails_me.transform(Matrix.Translation((section - (r_lo + r_hi) * 0.5, 0.0, 0.0)))

    s_lo, s_hi = span_x(spheres_me)
    print("section %.3f; arch centred at %.3f of it; rail centred at %.3f"
          % (section, (s_lo + s_hi) * 0.5, sum(span_x(rails_me)) * 0.5))

    gn = next(m for m in src[RAILS].modifiers if m.type == 'NODES')
    group = gn.node_group
    # Reuse the group from an earlier run rather than keep a fresh copy each time.
    base = group.name.split(".")[0]
    if base != group.name and base in bpy.data.node_groups:
        group = bpy.data.node_groups[base]
    ids = {it.name: it.identifier for it in group.interface.items_tree
           if getattr(it, "in_out", None) == 'INPUT'}
    # Every setting as the source had it; only the count and the step are ours.
    inherited = {k: gn[k] for k in gn.keys() if k in ids.values()}
    offset_method = gn[ids["Offset Method"]]

    coll = bpy.data.collections.get("TrackPieces") or bpy.context.scene.collection

    for curve_ob in sorted((o for o in bpy.data.objects if o.name.startswith("TP_")
                            and o.type == 'CURVE'), key=lambda o: o.name):
        sp = curve_ob.data.splines[0]
        # Length along the curve, in sections.
        length = sp.calc_length()
        count = max(1, int(round(length / section)))
        tag = curve_ob.name[3:]

        def add(name, me):
            ob = bpy.data.objects.new("TPM_%s_%s" % (tag, name), me)
            coll.objects.link(ob)
            # Same origin as the curve, or the Curve modifier starts the mesh part-way
            # along it. Parented so piece and model move as one.
            ob.parent = curve_ob
            ob.matrix_parent_inverse = Matrix.Identity(4)
            return ob

        p = add("Pipe", pipe_me)
        mir = p.modifiers.new("Mirror", 'MIRROR')
        mir.use_axis = (False, True, False)
        mir.use_clip = False
        arr = p.modifiers.new("Array", 'ARRAY')
        arr.count = count
        arr.use_relative_offset = False
        arr.use_constant_offset = True
        arr.constant_offset_displace = (section, 0.0, 0.0)
        arr.use_merge_vertices = True
        arr.merge_threshold = 0.001

        for name, me in (("Rails", rails_me), ("Spheres", spheres_me)):
            ob = add(name, me)
            mod = ob.modifiers.new("Array", 'NODES')
            mod.node_group = group
            for k, v in inherited.items():
                # A new modifier already holds defaults of the right type, and a
                # true/false read back from another file can arrive as 0 or 1.
                if isinstance(mod.get(k), bool):
                    v = bool(v)
                mod[k] = v
            mod[ids["Offset Method"]] = offset_method
            mod[ids["Translation"]] = (section, 0.0, 0.0)
            mod[ids["Count"]] = count

        for ob in (o for o in bpy.data.objects if o.name.startswith("TPM_%s_" % tag)):
            c = ob.modifiers.new("Track", 'CURVE')
            c.object = curve_ob
            c.deform_axis = 'POS_X'

        print("%-20s %.2f long = %d section%s" % (curve_ob.name, length, count, "" if count == 1 else "s"))

    for ob in src.values():
        bpy.data.objects.remove(ob, do_unlink=True)

    # --- check: does each model end where its curve ends? ---------------------------
    bpy.context.view_layer.update()
    dg = bpy.context.evaluated_depsgraph_get()
    print()
    for curve_ob in sorted((o for o in bpy.data.objects if o.name.startswith("TP_")
                            and o.type == 'CURVE'), key=lambda o: o.name):
        tag = curve_ob.name[3:]
        pipe_ob = bpy.data.objects["TPM_%s_Pipe" % tag]
        n_base = len(pipe_ob.data.vertices)
        base_hi = max(v.co.x for v in pipe_ob.data.vertices)
        # The far end of the last section: the vertices that sat at x = section before
        # bending, which after Mirror and Array are the last copy's high-x ring.
        for m in pipe_ob.modifiers:
            if m.type == 'CURVE':
                m.show_viewport = False
        bpy.context.view_layer.update()
        ev = pipe_ob.evaluated_get(bpy.context.evaluated_depsgraph_get())
        me = ev.to_mesh()
        far = max(v.co.x for v in me.vertices)
        idx = [v.index for v in me.vertices if abs(v.co.x - far) < 1e-3]
        ev.to_mesh_clear()
        for m in pipe_ob.modifiers:
            if m.type == 'CURVE':
                m.show_viewport = True
        bpy.context.view_layer.update()
        ev = pipe_ob.evaluated_get(bpy.context.evaluated_depsgraph_get())
        me = ev.to_mesh()
        ring = [me.vertices[i].co for i in idx]
        tris = sum(len(p.vertices) - 2 for p in me.polygons)
        # The rim is 10 above the floor on both sides, so the ring's lowest point is
        # the floor's centre line: compare that with the curve's end.
        floor = min(ring, key=lambda c: c.z)
        ev.to_mesh_clear()
        end = curve_ob.data.splines[0].bezier_points[-1].co
        gap = (Vector((floor.x, floor.y, floor.z)) - end).length
        print("%-20s pipe %5d tris; far end of floor is %.3f from the curve's end"
              % (curve_ob.name, tris, gap))

    if world is not None:
        bpy.context.scene.world = world
    sc = bpy.context.scene
    sc.render.engine = 'BLENDER_EEVEE'
    sc.view_settings.view_transform = 'Standard'
    if "HP_Sun" not in bpy.data.objects:
        for name, energy, colour, rot, angle in (
                ("HP_Sun", 3.2, (1.0, 0.97, 0.90), (28.0, 0.0, -68.0), 8.0),
                ("HP_Fill", 0.7, (0.65, 0.80, 1.0), (50.0, 0.0, 115.0), 30.0)):
            data = bpy.data.lights.new(name, 'SUN')
            data.energy, data.color, data.angle = energy, colour, math.radians(angle)
            ob = bpy.data.objects.new(name, data)
            ob.rotation_euler = tuple(math.radians(d) for d in rot)
            sc.collection.objects.link(ob)

    bpy.ops.wm.save_as_mainfile(filepath=OUT)
    print("saved", OUT)


main()
