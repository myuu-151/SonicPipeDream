"""Make the five track pieces as starter curves.

    blender -b --python native/gen_track_pieces.py -- <out.blend> [--force]

One Bezier curve per segment type of the Sonic 2 special stage. These are STARTING
shapes, meant to be reshaped by eye in Blender; chain_track_pieces.py reads each
piece's end point and heading from the curve itself, so any reshaping still chains.

    ... -- <out.blend> --redo TP_StraightDrop     remake just the named pieces

It is ADDITIVE. If the file already exists it is opened, and only the pieces missing
from it are added; a piece that is already there is never touched, because the whole
point of that file is the hand edits in it. --force starts the file again from nothing.

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
# --redo TP_Name [TP_Name ...]: throw those pieces away and make them again. For when
# a starter shape was wrong; it does discard any hand edits to the pieces named.
REDO = [a for a in args[args.index("--redo") + 1:] if a.startswith("TP_")] if "--redo" in args else []

SECTION = 40.161            # one pipe section; the pieces are whole numbers of these
TURN_DEG = 60.0             # how far a turn piece turns; unmirrored is to the right
DROP = 45.0                 # how far a drop piece falls, over two sections
CORNER_DEG = 90.0           # the stand-alone corner piece
CHUTE_DEG = 50.0            # the slope the long drop holds
CHUTE_SECTIONS = 6          # its whole length: tip, slope, settle, run-off
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


def walk_pitch(sections, yaw_at, pitch_at):
    """As walk(), but shaped by the slope itself: pitch_at(u) is the angle below (or
    above) level, in radians, at u = 0..1. That is the natural way to describe a
    chute, which holds one slope for a long way; a height curve can only ever be
    curving."""
    n = sections * SAMPLES_PER_SECTION * 4
    step = sections * SECTION / n
    x = y = z = 0.0
    pts = [(0.0, 0.0, 0.0)]
    for i in range(n):
        u = (i + 0.5) / n
        pitch, yaw = pitch_at(u), yaw_at(u)
        flat = step * math.cos(pitch)
        x += flat * math.cos(yaw)
        y += flat * math.sin(yaw)
        z += step * math.sin(pitch)
        pts.append((x, y, z))
    return pts[::4], yaw_at(1.0)


turn = -math.radians(TURN_DEG)                       # negative yaw is a right turn


def turn_then(hill):
    """A turn across the first section, then a hill across the other two."""
    def yaw_at(u):
        return turn * ease(min(1.0, u * 3.0))

    def z_at(u):
        return hill * ease(max(0.0, (u * 3.0 - 1.0) / 2.0))
    return walk(3, yaw_at, z_at)


def straight_drop():
    """Straight ahead and down, no turn. The ease is flat at both ends already, so
    the fall can use the whole two sections: squeezed into less, its steepest part
    passed what a step along the curve can cover and the drop came up short."""
    return walk(2, lambda u: 0.0, lambda u: -DROP * ease(u))


def long_drop():
    """A chute. Tips over across the first section, holds a steady slope for three,
    levels out across the next, and finishes with a flat run-off, so whatever comes
    after it starts on the level."""
    slope = -math.radians(CHUTE_DEG)
    total = float(CHUTE_SECTIONS)
    tip, settle, runoff = 1.0 / total, 1.0 / total, 0.75 / total

    def pitch_at(u):
        if u < tip:
            return slope * ease(u / tip)
        if u < 1.0 - settle - runoff:
            return slope
        if u < 1.0 - runoff:
            return slope * (1.0 - ease((u - (1.0 - settle - runoff)) / settle))
        return 0.0
    return walk_pitch(CHUTE_SECTIONS, lambda u: 0.0, pitch_at)


def corner():
    """A corner that stands on its own between two straights: half a section
    straight, a quarter turn across two sections, half a section straight. The lead
    in and out are what let it butt cleanly against a straight at either end."""
    quarter = -math.radians(CORNER_DEG)

    def yaw_at(u):
        return quarter * ease(max(0.0, min(1.0, (u * 3.0 - 0.5) / 2.0)))
    return walk(3, yaw_at, lambda u: 0.0)


PIECES = [
    # name, game type (-1: not one of the game's five, for generated stages only), points
    ("TP_Straight", 3, walk(1, lambda u: 0.0, lambda u: 0.0)),
    # In the game these frames only show the bend arriving; nothing turns yet.
    ("TP_StraightToTurn", 4, walk(1, lambda u: 0.0, lambda u: 0.0)),
    ("TP_TurnToStraight", 2, walk(1, lambda u: turn * ease(u), lambda u: 0.0)),
    ("TP_TurnThenDrop", 1, turn_then(-DROP)),
    ("TP_TurnThenRise", 0, turn_then(DROP)),
    ("TP_StraightDrop", -1, straight_drop()),
    ("TP_Corner", -1, corner()),
    ("TP_LongDrop", -1, long_drop()),
]


def main():
    if os.path.exists(OUT) and not FORCE:
        bpy.ops.wm.open_mainfile(filepath=OUT)
        coll = bpy.data.collections.get("TrackPieces")
    else:
        bpy.ops.wm.read_factory_settings(use_empty=True)
        coll = None
    if coll is None:
        coll = bpy.data.collections.new("TrackPieces")
        bpy.context.scene.collection.children.link(coll)

    for name in REDO:
        # Its model objects are its children; they go too, and are rebuilt afterwards.
        for ob in [o for o in bpy.data.objects if o.name == name or
                   (o.parent is not None and o.parent.name == name)]:
            bpy.data.objects.remove(ob, do_unlink=True)

    for k, (name, kind, (pts, end_yaw)) in enumerate(PIECES):
        if name in bpy.data.objects:
            print("%-20s already there; left alone" % name)
            continue
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
