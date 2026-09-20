"""Lay ring modules on the bent track pieces, to prove a module needs no corner or slope
variant of its own: it is the same list of (frame, angle), and the piece's curve bends it.

    blender -b external/halfpipe/TrackPiecesPack.blend \
        --python native/gen_rings_on_pieces.py -- [render]

Writes external/ring/RingsOnPieces.blend (the pack is read, never written), and with
`render` two pictures beside it.

`PiecePath` and `lay()` are the part that lasts: the level generator lays modules the same
way. A module's frame becomes distance along the piece's centre line; its angle becomes a
place on the circle round the pipe's axis, in the curve's OWN frame at that distance -- so
on a corner the shape turns with the pipe, and on a drop it tips over with it.
"""

import math
import os
import sys

import bmesh
import bpy
from mathutils import Matrix, Vector
from mathutils.geometry import interpolate_bezier

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import ring_modules as rm

args = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
RENDER = "render" in args
RING_BLEND = os.path.abspath(os.path.join(HERE, "..", "external", "ring", "Ring.blend"))
OUT_DIR = os.path.abspath(os.path.join(HERE, "..", "external", "ring"))

# What goes on what: (module, first frame, angle it is put at). Chosen to be what the
# original favours there: clusters and a snake round a corner, big triangles and a spiral
# down a drop.
DEMO = {
    "TP_Corner":   [("Cluster", 1, 0), ("Snake", 7, 0)],
    "TP_LongDrop": [("TriangleBig", 2, -32), ("TriangleBig", 10, 32), ("TriangleBig", 18, -32),
                    ("Spiral", 26, 0)],
}


class PiecePath:
    """A piece's centre line, measured by distance along it."""

    def __init__(self, curve_ob, samples=24):
        bps = curve_ob.data.splines[0].bezier_points
        pts = [bps[0].co.copy()]
        for a, b in zip(bps, bps[1:]):
            pts += [p.copy() for p in interpolate_bezier(a.co, a.handle_right, b.handle_left,
                                                         b.co, samples + 1)[1:]]
        self.pts = pts
        self.dist = [0.0]
        for p, q in zip(pts, pts[1:]):
            self.dist.append(self.dist[-1] + (q - p).length)
        self.length = self.dist[-1]

    def frame(self, s):
        """4x4 at distance s: X along the track, Y across, Z up out of the floor. No bank."""
        s = max(0.0, min(s, self.length))
        i = max(j for j, d in enumerate(self.dist) if d <= s)
        i = min(i, len(self.pts) - 2)
        seg = self.dist[i + 1] - self.dist[i]
        t = (s - self.dist[i]) / seg if seg else 0.0
        pos = self.pts[i].lerp(self.pts[i + 1], t)
        a, b = self.pts[max(i - 1, 0)], self.pts[min(i + 2, len(self.pts) - 1)]
        x = (b - a).normalized()
        z = (Vector((0, 0, 1)) - x * x.z).normalized()
        y = z.cross(x)
        m = Matrix((x, y, z)).transposed().to_4x4()
        m.translation = pos
        return m


def lay(module, path, first_frame=0, at=0.0):
    """[(matrix, kind)]: where each of the module's objects sits on this piece."""
    out = []
    for frame, angle, kind in module:
        x, y, z = rm.local(frame + first_frame, angle, at)
        if x > path.length:
            continue                      # ran off the end: the next piece's business
        out.append((path.frame(x) @ Matrix.Translation((0.0, y, z)), kind))
    return out


def bake(curve):
    dg = bpy.context.evaluated_depsgraph_get()
    bm = bmesh.new()
    materials = None
    for child in sorted(curve.children, key=lambda o: o.name):
        if child.type != 'MESH':
            continue
        me = bpy.data.meshes.new_from_object(child.evaluated_get(dg))
        me.transform(curve.matrix_world.inverted() @ child.matrix_world)
        materials = materials or list(me.materials)
        bm.from_mesh(me)
        bpy.data.meshes.remove(me)
    out = bpy.data.meshes.new("PM_" + curve.name[3:])
    bm.to_mesh(out)
    bm.free()
    for m in materials or []:
        out.materials.append(m)
    return out


def main():
    pieces = {name: (bake(bpy.data.objects[name]), PiecePath(bpy.data.objects[name])) for name in DEMO}
    with bpy.data.libraries.load(RING_BLEND) as (src, dst):
        dst.meshes = [n for n in src.meshes if n == "Ring"]
    ring = dst.meshes[0]
    for ob in list(bpy.data.objects):
        bpy.data.objects.remove(ob, do_unlink=True)
    scene = bpy.context.scene

    origins = {}
    for n, (name, (mesh, path)) in enumerate(pieces.items()):
        origin = Matrix.Translation((0.0, -n * 400.0, 0.0))
        origins[name] = (origin, path)
        piece = bpy.data.objects.new(name[3:], mesh)
        piece.matrix_world = origin
        scene.collection.objects.link(piece)
        for module, first, at in DEMO[name]:
            for i, (m, kind) in enumerate(lay(rm.MODULES[module], path, first, at)):
                ob = bpy.data.objects.new("%s_%s_%02d" % (name[3:], module, i), ring)
                ob.matrix_world = origin @ m
                scene.collection.objects.link(ob)
        print("%-12s %7.2f long = %4.1f frames of rings" % (name, path.length, path.length / rm.STEP))

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
    cam_data = bpy.data.cameras.new("Camera")
    cam_data.lens, cam_data.clip_end = 22.0, 3000.0
    cam = bpy.data.objects.new("Camera", cam_data)
    scene.collection.objects.link(cam)
    scene.camera = cam

    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(OUT_DIR, "RingsOnPieces.blend"))

    if RENDER:
        for engine in ('BLENDER_EEVEE', 'BLENDER_EEVEE_NEXT'):
            try:
                scene.render.engine = engine
                break
            except TypeError:
                pass
        scene.render.resolution_x, scene.render.resolution_y = 1100, 700
        views = {
            # looking down onto the corner from above and behind its start
            "TP_Corner":   (Vector((-45.0, 40.0, 75.0)), 0.45),
            # from beside and above, looking down into the chute
            "TP_LongDrop": (Vector((150.0, 95.0, 25.0)), 0.5),
        }
        for name, (offset, along) in views.items():
            origin, path = origins[name]
            target = origin @ path.frame(path.length * along).translation
            pos = origin @ offset
            cam.location = pos
            cam.rotation_euler = (target - pos).to_track_quat('-Z', 'Y').to_euler()
            scene.render.filepath = os.path.join(OUT_DIR, "RingsOn_%s.png" % name[3:])
            bpy.ops.render.render(write_still=True)


main()
