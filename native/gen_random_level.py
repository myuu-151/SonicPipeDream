"""Generate a level from the modular track pieces, the way the game will at runtime.

    blender -b <TrackPiecesPack.blend> --python native/gen_random_level.py -- \\
        <out.blend> [difficulty 1-7] [seed]

Nothing here bends a long pipe along a path. Each piece is baked once into a single
self-contained mesh, and a level is those meshes set down end to end, each with one
rigid transform -- exactly what the engine will do, with only the next few alive.

THE PIECES ARE MODULAR, so three authored shapes give five:

    Straight
    Corner right             as authored
    Corner left              the same piece mirrored
    Drop                     as authored
    Rise                     the drop's curve turned upside down, with the pipe bent along it

and an S-bend is nothing more than a left corner followed by a right one.

The same seed and difficulty always give the same level.
"""

import math
import random
import sys

import bmesh
import bpy
from mathutils import Matrix, Vector
from mathutils.geometry import interpolate_bezier

# The command line is only this script's when it is the one being run; gen_stage.py
# imports it for its pieces, its deck and its collision check.
args = sys.argv[sys.argv.index("--") + 1:] if __name__ == "__main__" and "--" in sys.argv else []
OUT = args[0] if args else None
DIFFICULTY = int(args[1]) if len(args) > 1 else 3
SEED = int(args[2]) if len(args) > 2 else 1

# --- the difficulty rulebook --------------------------------------------------------
# A row of limits per level, not a learned model: that is what makes "level 1 can
# never get too hard" a guarantee. Rings and bombs will add their own columns.
#
#   pieces     how long the level is
#   turn       the SHARE of pieces that are corners (dealt, not rolled: see plan())
#   snake      chance that a corner is dealt as an S-bend (left-right or right-left)
#   hill       the share that are drops or rises; always at least one
#   rise       of the hills, the chance that one goes up
#   rest       straights forced after a hill, to recover on
#   chain      most corners allowed back to back (an S-bend counts as two)
RULES = {
    1: dict(pieces=14, turn=0.25, snake=0.00, hill=0.08, rise=0.0, rest=2, chain=1),
    2: dict(pieces=16, turn=0.32, snake=0.10, hill=0.10, rise=0.2, rest=2, chain=1),
    3: dict(pieces=18, turn=0.40, snake=0.20, hill=0.12, rise=0.3, rest=1, chain=2),
    4: dict(pieces=20, turn=0.46, snake=0.30, hill=0.14, rise=0.4, rest=1, chain=2),
    5: dict(pieces=22, turn=0.52, snake=0.40, hill=0.16, rise=0.4, rest=1, chain=3),
    6: dict(pieces=24, turn=0.58, snake=0.50, hill=0.18, rise=0.5, rest=1, chain=3),
    7: dict(pieces=28, turn=0.64, snake=0.60, hill=0.20, rise=0.5, rest=0, chain=4),
}

# How near the track may come to a part of itself laid earlier. The pipe is about 29
# wide with its decks; parts far enough apart in height pass over and under.
CLEAR_FLAT = 45.0
CLEAR_HEIGHT = 35.0
RECENT = 3                  # the last few pieces are neighbours, not collisions

SAMPLES = 6


# ---------------------------------------------------------------- reading the pack --
def curve_points(ob):
    bps = ob.data.splines[0].bezier_points
    pts = [bps[0].co.copy()]
    for a, b in zip(bps, bps[1:]):
        seg = interpolate_bezier(a.co, a.handle_right, b.handle_left, b.co, SAMPLES + 1)
        pts += [p.copy() for p in seg[1:]]
    tangent = (bps[-1].co - bps[-1].handle_left).normalized()
    return pts, math.atan2(tangent.y, tangent.x)


# Where each face of a baked piece came from, for painting a pattern on the pipe after it has
# been bent: CELLS[mesh name][polygon index] = (copy, x, angle) -- which repeat of the section
# along the piece, and the face's middle in the STRAIGHT section: x along it, and degrees round
# the pipe from the floor (0) to the rims (+-90). None for a face that is not a repeat of a
# section (a rail cap, a sphere). The mirrored variants share their source's list: the
# patterns painted from it are symmetric about the floor.
CELLS = {}
PIPE_RADIUS = 10.0          # the section's: floor at z = 0, axis at z = PIPE_RADIUS


def bake(curve_ob, name):
    """The piece's pipe, rails and arches, modifiers applied, as ONE mesh in the
    piece's own space: origin at its start, heading +X."""
    dg = bpy.context.evaluated_depsgraph_get()
    bm = bmesh.new()
    materials = None
    cells = []
    for child in sorted(curve_ob.children, key=lambda o: o.name):
        if child.type != 'MESH':
            continue
        me = bpy.data.meshes.new_from_object(child.evaluated_get(dg))
        if materials is None:
            materials = list(me.materials)
        # An Array keeps the section's faces in order, copy after copy, and a Curve only moves
        # them: face p of the result is face p % n of the section, in copy p // n.
        base = child.data
        n = len(base.polygons)
        if n and len(me.polygons) % n == 0:
            here = []
            for poly in base.polygons:
                c = poly.center
                here.append((c.x, math.degrees(math.atan2(c.y, PIPE_RADIUS - c.z))))
            for p in range(len(me.polygons)):
                cells.append((p // n,) + here[p % n])
        else:
            cells.extend([None] * len(me.polygons))
        bm.from_mesh(me)
        bpy.data.meshes.remove(me)
    out = bpy.data.meshes.new(name)
    bm.to_mesh(out)
    bm.free()
    for m in materials or []:
        out.materials.append(m)
    CELLS[name] = cells
    return out


def variant(mesh, name, matrix, flip):
    """A copy of a baked piece under a fixed transform. A mirror turns the faces
    inside out, so they are turned back: every variant is then an ordinary mesh that
    needs nothing but a rigid transform to place, in Blender or in the engine."""
    me = mesh.copy()
    me.name = name
    me.transform(matrix)
    if flip:
        me.flip_normals()
    me.update()
    CELLS[name] = CELLS.get(mesh.name)
    return me


def make_rise(drop):
    """The rise as a piece of its own: the drop's curve turned upside down, and the same pipe,
    rails and arches bent along it.

    It used to be the baked drop turned round and travelled backwards, which is the same
    SHAPE -- and wrong in everything that has a direction. The floor's arrows pointed at the
    player instead of away, and each section's rail was at its near end instead of its far
    one. No turning or mirroring of that mesh can fix it: the markings are part of it, and
    they point down the drop. So the rise is built the way every piece is built, forwards.

    Made here, in memory; the pack file is read, never written."""
    curve = drop.data.copy()
    curve.name = "TP_Rise"
    # Mirrored as ONE transform, never point by point. The first version negated z on each
    # point's co and two handles in turn, and between those assignments Blender re-derives
    # the automatic handles -- so the "mirror" came out kinked, three times the drop's
    # length, and the curve modifier squeezed the pipe onto it: the rise's last stretch
    # pinched to a wedge with its rails and deck through it. Curve.transform moves points
    # and handles together and leaves the length exactly the drop's.
    curve.transform(Matrix.Diagonal((1.0, 1.0, -1.0, 1.0)))
    rise = drop.copy()
    rise.data = curve
    rise.name = "TP_Rise"
    bpy.context.scene.collection.objects.link(rise)
    for child in drop.children:
        model = child.copy()                          # the same mesh, its own modifiers
        model.name = child.name.replace("LongDrop", "Rise")
        bpy.context.scene.collection.objects.link(model)
        model.parent = rise
        model.matrix_parent_inverse = child.matrix_parent_inverse.copy()
        for mod in model.modifiers:
            if mod.type == 'CURVE' and mod.object == drop:
                mod.object = rise
    bpy.context.view_layer.update()
    return rise


def load_pieces():
    raw = {}
    for ob in bpy.data.objects:
        if ob.type == 'CURVE' and ob.name.startswith("TP_"):
            pts, yaw = curve_points(ob)
            raw[ob.name] = (ob, pts, yaw)

    mirror = Matrix.Scale(-1.0, 4, (0.0, 1.0, 0.0))
    pieces = {}

    ob, pts, yaw = raw["TP_Straight"]
    pieces["Straight"] = dict(mesh=bake(ob, "PM_Straight"), pts=pts, yaw=yaw)

    ob, pts, yaw = raw["TP_Corner"]
    right = bake(ob, "PM_CornerRight")
    pieces["CornerRight"] = dict(mesh=right, pts=pts, yaw=yaw)
    pieces["CornerLeft"] = dict(mesh=variant(right, "PM_CornerLeft", mirror, True),
                                pts=[mirror @ p for p in pts], yaw=-yaw)

    ob, pts, yaw = raw["TP_LongDrop"]
    drop = bake(ob, "PM_Drop")
    pieces["Drop"] = dict(mesh=drop, pts=pts, yaw=yaw)
    # The rise is a piece of its own, built forwards: see make_rise().
    rise = make_rise(ob)
    rise_pts, rise_yaw = curve_points(rise)
    pieces["Rise"] = dict(mesh=bake(rise, "PM_Rise"), pts=rise_pts, yaw=rise_yaw)

    for p in pieces.values():
        p["end"] = p["pts"][-1].copy()
        p["length"] = sum((b - a).length for a, b in zip(p["pts"], p["pts"][1:]))
    return pieces


# --------------------------------------------------------------------- generating --
def exit_frame(frame, piece):
    return frame @ Matrix.Translation(piece["end"]) @ Matrix.Rotation(piece["yaw"], 4, 'Z')


def collides(world_pts, laid):
    """Does this piece run into anything laid before its recent neighbours?"""
    for earlier in laid[:-RECENT] if len(laid) > RECENT else []:
        for a in world_pts[::3]:
            for b in earlier[::3]:
                if abs(a.z - b.z) < CLEAR_HEIGHT and math.hypot(a.x - b.x, a.y - b.y) < CLEAR_FLAT:
                    return True
    return False


def plan(rules, rng):
    """The level as a list of piece names, before anything is laid.

    Dealt from a deck, not rolled piece by piece. Independent dice only meet the
    rulebook on average: one seed at difficulty 3 rolled high nine times running and
    gave fifteen straights out of eighteen, and the same luck the other way is how an
    easy level turns hard. So the mix is fixed first -- this many corners, this many
    hills, the rest straights -- and only the ARRANGEMENT is random.
    """
    n = rules["pieces"]
    hills = max(1, round(rules["hill"] * n))
    corners = round(rules["turn"] * n)

    # Events: single corners, S-bends (a corner and its opposite), hills.
    events = []
    left = corners
    while left > 0:
        first = rng.choice(["CornerLeft", "CornerRight"])
        if left >= 2 and rules["chain"] >= 2 and rng.random() < rules["snake"]:
            other = "CornerRight" if first == "CornerLeft" else "CornerLeft"
            events.append([first, other])
            left -= 2
        else:
            events.append([first])
            left -= 1
    for _ in range(hills):
        events.append(["Rise" if rng.random() < rules["rise"] else "Drop"])
    rng.shuffle(events)

    # The straights every rule DEMANDS, then the spare ones scattered at random.
    # gap[i] is the run of straights before event i; gap[-1] closes the level.
    gap = [0] * (len(events) + 1)
    gap[0] = 2                                   # every level opens on straights
    chain = 0
    for i, ev in enumerate(events):
        is_corner = ev[0].startswith("Corner")
        if is_corner and chain + len(ev) > rules["chain"]:
            gap[i] = max(gap[i], 1)              # break up a run of corners
            chain = 0
        chain = chain + len(ev) if is_corner else 0
        if not is_corner:
            gap[i + 1] = max(gap[i + 1], rules["rest"])      # recover after a hill
    gap[-1] = max(gap[-1], 1)                    # and end on a straight

    used = sum(len(ev) for ev in events) + sum(gap)
    for _ in range(max(0, n - used)):
        gap[rng.randrange(len(gap))] += 1

    names = []
    for i, ev in enumerate(events):
        names += ["Straight"] * gap[i] + ev
    return names + ["Straight"] * gap[-1]


def generate(pieces, rules, rng, plan_names=None):
    """Lay the plan -- this level's own, or a list of piece names handed in. A piece that would run into the level is swapped for the nearest
    thing that fits -- the other corner, a drop to pass underneath, a straight -- and
    the swap is reported, since it changes the mix the plan promised."""
    frame = Matrix.Identity(4)
    laid_pts, names, frames, swaps = [], [], [], []

    for want in (plan_names or plan(rules, rng)):
        options = [want]
        if want.startswith("Corner"):
            options += ["CornerRight" if want == "CornerLeft" else "CornerLeft", "Drop", "Straight"]
        elif want == "Straight":
            options += ["Drop", "CornerLeft", "CornerRight"]
        else:
            options += ["Drop", "Straight", "CornerLeft", "CornerRight"]

        for name in dict.fromkeys(options):
            world = [frame @ p for p in pieces[name]["pts"]]
            if collides(world, laid_pts):
                continue
            if name != want:
                swaps.append("piece %d: %s -> %s" % (len(names), want, name))
            names.append(name)
            frames.append(frame.copy())
            laid_pts.append(world)
            frame = exit_frame(frame, pieces[name])
            break
        else:
            print("boxed in after %d pieces; ending the level here" % len(names))
            break
    return names, frames, laid_pts, swaps


# ------------------------------------------------------------------------ building --
def build_scene(pieces, names, frames, laid_pts):
    keep = {p["mesh"].name for p in pieces.values()}
    for ob in [o for o in bpy.data.objects if o.type in ('MESH', 'CURVE')]:
        bpy.data.objects.remove(ob, do_unlink=True)

    coll = bpy.data.collections.new("Level")
    bpy.context.scene.collection.children.link(coll)
    for i, (name, frame) in enumerate(zip(names, frames)):
        ob = bpy.data.objects.new("L%02d_%s" % (i, name), pieces[name]["mesh"])
        ob.matrix_world = frame
        coll.objects.link(ob)

    # The centre line, for reference and for whatever follows the track later.
    cu = bpy.data.curves.new("Level_Path", 'CURVE')
    cu.dimensions = '3D'
    sp = cu.splines.new('POLY')
    flat = [p for world in laid_pts for p in world]
    sp.points.add(len(flat) - 1)
    for pt, co in zip(sp.points, flat):
        pt.co = (co.x, co.y, co.z, 1.0)
    path = bpy.data.objects.new("Level_Path", cu)
    path.hide_render = True
    coll.objects.link(path)

    cam_data = bpy.data.cameras.new("Level_Camera")
    cam_data.lens, cam_data.clip_end = 14.0, 5000.0
    cam = bpy.data.objects.new("Level_Camera", cam_data)
    pos, target = Vector((3.0, 0.0, 4.2)), Vector((140.0, 0.0, 8.0))
    cam.location = pos
    cam.rotation_euler = (target - pos).to_track_quat('-Z', 'Y').to_euler()
    bpy.context.scene.collection.objects.link(cam)
    bpy.context.scene.camera = cam
    return keep


def main():
    rules = RULES[DIFFICULTY]
    rng = random.Random("%d/%d" % (DIFFICULTY, SEED))
    pieces = load_pieces()

    print()
    for name, p in pieces.items():
        tris = sum(len(f.vertices) - 2 for f in p["mesh"].polygons)
        print("%-12s %7.2f long, %5d tris, ends (%7.2f %7.2f %7.2f) turning %6.1f deg"
              % (name, p["length"], tris, p["end"].x, p["end"].y, p["end"].z,
                 math.degrees(p["yaw"])))

    names, frames, laid_pts, swaps = generate(pieces, rules, rng)
    build_scene(pieces, names, frames, laid_pts)

    zs = [p.z for world in laid_pts for p in world]
    total = sum(pieces[n]["length"] for n in names)
    tris = sum(sum(len(f.vertices) - 2 for f in pieces[n]["mesh"].polygons) for n in names)
    print("\ndifficulty %d, seed %d: %d pieces, %.0f units, %d tris if all drawn at once"
          % (DIFFICULTY, SEED, len(names), total, tris))
    print("  " + " ".join({"Straight": "S", "CornerLeft": "L", "CornerRight": "R",
                           "Drop": "D", "Rise": "U"}[n] for n in names))
    print("  height runs %.0f to %.0f" % (min(zs), max(zs)))
    for line in swaps:
        print("  swapped to avoid the level running into itself -- " + line)
    counts = {n: names.count(n) for n in pieces}
    print("  " + ", ".join("%s %d" % (k, v) for k, v in counts.items() if v))

    bpy.ops.wm.save_as_mainfile(filepath=OUT)
    print("saved", OUT)


if __name__ == "__main__":
    main()
