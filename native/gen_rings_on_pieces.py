"""Lay ring and bomb modules along real track pieces -- straight, corner, drop -- to prove a
module needs no corner or slope variant of its own: it is the same list of (frame, angle),
and the track's curve bends it.

    blender -b external/halfpipe/TrackPiecesPack.blend \
        --python native/gen_rings_on_pieces.py -- [render]

Writes external/ring/RingsOnPieces.blend (the pack is read, never written), and with
`render` four pictures beside it. It also CHECKS: every module is laid on every piece and
on the whole run, and each object's distance from the pipe's axis is measured.

`PiecePath`, `ChainPath` and `lay()` are the part that lasts: the level generator lays
modules the same way. A module's frame becomes distance along the centre line; its angle
becomes a place on the circle round the pipe's axis, in the curve's OWN frame at that
distance -- so on a corner the shape turns with the pipe, and on a drop it tips over with
it. Rings or bombs or both: lay() does not care what kind an object is.
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
BOMB_BLEND = os.path.abspath(os.path.join(HERE, "..", "external", "bomb", "Bomb.blend"))
OUT_DIR = os.path.abspath(os.path.join(HERE, "..", "external", "ring"))

# A short run of track, and what is laid along it: (module, first frame, angle it is put
# at). Frames count from the start of the RUN, not of a piece, so a module may start on one
# piece and finish on the next. Rings and bombs together, several modules abreast, and
# long modules across joints are all here on purpose: it is what this file is for.
RUN = ["TP_Straight", "TP_Corner", "TP_Straight", "TP_LongDrop", "TP_Straight"]
DEMO = [
    ("TwinBombsAndCluster", 1, 0),      # short straight: rings and bombs abreast
    ("Slalom", 9, 0),                   # into the corner: a mixed module, bending
    ("SwapWalls", 24, 0),               # out of the corner, across the joint
    ("BombGate", 38, 0),                # short straight: a wall with a gap...
    ("TriangleBig", 40, 0),             # ...and rings through it: two modules on one piece
    ("LineInCorkscrew", 46, 0),         # over the lip and down the drop
    ("TriangleBig", 72, -32), ("BombCluster", 72, 32),   # on the slope, abreast
    ("Snake", 80, 0),                   # down the slope, round the bottom, onto the flat
]


class PiecePath:
    """A piece's centre line, measured by distance along it."""

    def __init__(self, curve_ob=None, samples=24, pts=None):
        """From a curve object, or from points already in the piece's own space (which is
        how a mirrored corner or a drop travelled backwards gets its path)."""
        if pts is None:
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


class ChainPath:
    """Pieces end to end, measured by distance from the start of the first: what lets a
    module begin on one piece and finish on the next. Each piece starts where the last one
    ended, heading the way it was heading -- the same joint the level generator uses."""

    def __init__(self, paths, origins=None):
        """`origins`, when given, are where a level generator already put each piece."""
        self.parts = []                   # (start distance, origin matrix, path)
        origin, start = Matrix.Identity(4), 0.0
        for i, path in enumerate(paths):
            if origins is not None:
                origin = origins[i]
            self.parts.append((start, origin.copy(), path))
            origin = origin @ path.frame(path.length)
            start += path.length
        self.length = start

    def frame(self, s):
        s = max(0.0, min(s, self.length))
        start, origin, path = [p for p in self.parts if p[0] <= s][-1]
        return origin @ path.frame(s - start)


def lay(module, path, first_frame=0, at=0.0):
    """[(matrix, kind)]: where each of the module's objects sits. `path` is a PiecePath or
    a ChainPath. Anything past the end of the path is dropped."""
    out = []
    for frame, angle, kind in module:
        x, y, z = rm.local(frame + first_frame, angle, at)
        if x > path.length:
            continue
        out.append((path.frame(x) @ Matrix.Translation((0.0, y, z))
                    @ Matrix.Rotation(rm.roll(angle, at), 4, 'X'), kind))
    return out


def check(paths):
    """Every module on every piece, and on the whole run: does each object sit where it
    should -- the right distance from the pipe's axis, in the curve's own frame?"""
    want = rm.PIPE_RADIUS - rm.HOVER
    worst, count = 0.0, 0
    targets = dict(paths)
    targets["the whole run"] = ChainPath([paths[n] for n in RUN])
    for where, path in targets.items():
        cut = []
        for name, module in rm.MODULES.items():
            placed = lay(module, path, 1, 0)
            if len(placed) < len(module):
                cut.append(name)
            kept = [o for o in module if rm.local(o[0] + 1, o[1])[0] <= path.length]
            for (m, kind), (frame, angle, _) in zip(placed, kept):
                f = path.frame(rm.local(frame + 1, angle)[0])
                axis = f @ Vector((0.0, 0.0, rm.PIPE_RADIUS))
                worst = max(worst, abs((m.translation - axis).length - want))
                count += 1
        print("%-14s %5.1f frames long: %2d of %d modules fit whole%s"
              % (where, path.length / rm.STEP, len(rm.MODULES) - len(cut), len(rm.MODULES),
                 "" if not cut else "; too long for it alone: " + ", ".join(cut[:5])
                 + (" ..." if len(cut) > 5 else "")))
    print("%d objects laid; the furthest any sits from the pipe's circle: %.6f" % (count, worst))


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
    names = sorted(set(RUN))
    baked = {n: bake(bpy.data.objects[n]) for n in names}
    paths = {n: PiecePath(bpy.data.objects[n]) for n in names}
    meshes = {}
    for kind, blend, mesh in ((rm.RING, RING_BLEND, "Ring"), (rm.BOMB, BOMB_BLEND, "Bomb")):
        with bpy.data.libraries.load(blend) as (src, dst):
            dst.meshes = [n for n in src.meshes if n == mesh]
        meshes[kind] = dst.meshes[0]
    for ob in list(bpy.data.objects):
        bpy.data.objects.remove(ob, do_unlink=True)
    scene = bpy.context.scene

    print()
    check(paths)

    chain = ChainPath([paths[n] for n in RUN])
    for i, (name, (start, origin, _)) in enumerate(zip(RUN, chain.parts)):
        piece = bpy.data.objects.new("R%02d_%s" % (i, name[3:]), baked[name])
        piece.matrix_world = origin
        scene.collection.objects.link(piece)
    for module, first, at in DEMO:
        for i, (m, kind) in enumerate(lay(rm.MODULES[module], chain, first, at)):
            ob = bpy.data.objects.new("%s_%s_%02d" % (module, kind, i), meshes[kind])
            ob.matrix_world = m
            scene.collection.objects.link(ob)
    print("the run: %s = %.1f frames" % (" ".join(n[3:] for n in RUN), chain.length / rm.STEP))

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
    cam_data.lens, cam_data.clip_end = 20.0, 3000.0
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
        # (looking at this far along the run, from this offset in that spot's own frame)
        views = {
            "1_straight_and_corner": (0.14, Vector((-70.0, 30.0, 60.0))),
            "2_gate_and_lip":        (0.38, Vector((-60.0, 0.0, 38.0))),
            "3_down_the_drop":       (0.70, Vector((-75.0, 0.0, 32.0))),
            "4_bottom":              (0.90, Vector((-80.0, 10.0, 45.0))),
        }
        for name, (along, offset) in views.items():
            f = chain.frame(chain.length * along)
            pos = f @ offset
            cam.location = pos
            cam.rotation_euler = (f.translation + Vector((0, 0, 4.0)) - pos).to_track_quat('-Z', 'Y').to_euler()
            scene.render.filepath = os.path.join(OUT_DIR, "RingsOnRun_%s.png" % name)
            bpy.ops.render.render(write_still=True)


if __name__ == "__main__":
    main()
