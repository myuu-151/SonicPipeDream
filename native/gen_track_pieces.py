"""Make the five track pieces as starter curves.

    blender -b --python native/gen_track_pieces.py -- <out.blend> [--force]

One Bezier curve per segment type of the Sonic 2 special stage. These are STARTING
shapes, meant to be reshaped by eye in Blender; chain_track_pieces.py reads each
piece's end point and heading from the curve itself, so any reshaping still chains.

It refuses to overwrite an existing file unless --force is given, because the whole
point of that file is the hand edits in it.

The joint every piece must respect: start at the origin heading +X and level, and
END LEVEL. A piece may climb or fall, but its last stretch has to be flat.
"""

import math
import os
import sys

import bpy

args = sys.argv[sys.argv.index("--") + 1:]
OUT = os.path.abspath(args[0])
FORCE = "--force" in args

SECTION = 40.161            # one pipe section; the pieces are whole numbers of these
TURN_DEG = 60.0             # how far a turn piece turns; unmirrored is to the right
DROP = 45.0                 # how far a drop piece falls, over two sections
SAMPLES_PER_SECTION = 8     # curve points per section

# Shown side by side, this far apart, so they can be looked at together. Each
# object's ORIGIN is its start; only the object is moved, never its points.
SPACING = 90.0


def ease(t):
    """Smooth 0 -> 1 with no slope at either end."""
    return t * t * (3.0 - 2.0 * t)


def walk(sections, yaw_at, z_at):
    """Points of a piece `sections` long. yaw_at(u) and z_at(u) give heading (radians)
    and height at u = 0..1 along it. Distance is measured ALONG the curve, so a
    steep stretch travels less far forward and the piece's length stays exact."""
    n = sections * SAMPLES_PER_SECTION * 4          # fine steps; thinned afterwards
    step = sections * SECTION / n
    x = y = 0.0
    pts = [(0.0, 0.0, z_at(0.0))]
    for i in range(n):
        u0, u1 = i / n, (i + 1) / n
        dz = z_at(u1) - z_at(u0)
        dz = max(-0.97 * step, min(0.97 * step, dz))
        flat = math.sqrt(step * step - dz * dz)
        yaw = yaw_at((u0 + u1) * 0.5)
        x += flat * math.cos(yaw)
        y += flat * math.sin(yaw)
        pts.append((x, y, pts[-1][2] + dz))
    # The exit heading goes with the points: the joint is set from it exactly.
    return pts[::4], yaw_at(1.0)


turn = -math.radians(TURN_DEG)                       # negative yaw is a right turn


def turn_then(hill):
    """A turn across the first section, then a hill across the other two."""
    def yaw_at(u):
        return turn * ease(min(1.0, u * 3.0))

    def z_at(u):
        return hill * ease(max(0.0, (u * 3.0 - 1.0) / 2.0))
    return walk(3, yaw_at, z_at)


PIECES = [
    # name, game type, points
    ("TP_Straight", 3, walk(1, lambda u: 0.0, lambda u: 0.0)),
    # In the game these frames only show the bend arriving; nothing turns yet.
    ("TP_StraightToTurn", 4, walk(1, lambda u: 0.0, lambda u: 0.0)),
    ("TP_TurnToStraight", 2, walk(1, lambda u: turn * ease(u), lambda u: 0.0)),
    ("TP_TurnThenDrop", 1, turn_then(-DROP)),
    ("TP_TurnThenRise", 0, turn_then(DROP)),
]


def main():
    if os.path.exists(OUT) and not FORCE:
        raise SystemExit("%s exists; it holds hand edits. Pass --force to replace it." % OUT)

    bpy.ops.wm.read_factory_settings(use_empty=True)
    coll = bpy.data.collections.new("TrackPieces")
    bpy.context.scene.collection.children.link(coll)

    for k, (name, kind, (pts, end_yaw)) in enumerate(PIECES):
        cu = bpy.data.curves.new(name, 'CURVE')
        cu.dimensions = '3D'
        cu.twist_mode = 'Z_UP'
        cu.resolution_u = 12
        sp = cu.splines.new('BEZIER')
        sp.bezier_points.add(len(pts) - 1)
        for bp, co in zip(sp.bezier_points, pts):
            bp.co = co
            bp.handle_left_type = bp.handle_right_type = 'AUTO'
        # Pin the two end handles along the joint, so the piece really does leave
        # heading +X and its end tangent is the clean direction the chainer reads.
        first, last = sp.bezier_points[0], sp.bezier_points[-1]
        for bp, other in ((first, sp.bezier_points[1]), (last, sp.bezier_points[-2])):
            bp.handle_left_type = bp.handle_right_type = 'ALIGNED'
        h = SECTION / SAMPLES_PER_SECTION / 3.0
        first.handle_right = (h, 0.0, first.co.z)
        first.handle_left = (-h, 0.0, first.co.z)
        # And arrives heading exactly where it was told to, dead level. Left to the
        # automatic handle, a drop ended on a 6 degree slope and a 60 degree turn
        # came out at 59 -- small, but it compounds over 46 pieces.
        ex, ey = math.cos(end_yaw) * h, math.sin(end_yaw) * h
        last.handle_left = (last.co.x - ex, last.co.y - ey, last.co.z)
        last.handle_right = (last.co.x + ex, last.co.y + ey, last.co.z)

        ob = bpy.data.objects.new(name, cu)
        ob.location = (0.0, -k * SPACING, 0.0)
        ob["game_type"] = kind
        coll.objects.link(ob)

        end = pts[-1]
        print("%-20s type %d  %2d points  ends at (%7.2f, %7.2f, %6.2f) heading %6.1f deg"
              % (name, kind, len(pts), end[0], end[1], end[2], math.degrees(end_yaw)))

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=OUT)
    print("saved", OUT)


main()
