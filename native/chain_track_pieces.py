"""Play a list of track pieces back into one curve.

    blender -b <curve scene.blend> --python native/chain_track_pieces.py -- \\
        <pieces.blend> <out.blend> [stage 1-7]

Reads the five piece curves from pieces.blend AS THEY ARE NOW -- hand edits and all --
and lays them end to end in the order the game's data gives, mirrored where the data
says, into HP_Track. Each piece's end point and heading are measured from its curve,
so a piece can be reshaped freely and still chains.

This is the look-at-a-whole-stage tool. The engine should do the same at runtime with
only the next few pieces alive.
"""

import math
import sys

import bpy
from mathutils import Matrix, Vector
from mathutils.geometry import interpolate_bezier

sys.path.insert(0, bpy.path.abspath("//") or ".")
args = sys.argv[sys.argv.index("--") + 1:]
PIECES_BLEND, OUT = args[0], args[1]
STAGE = int(args[2]) if len(args) > 2 else 1

import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from gen_s2_track import LAYOUTS          # the game's data; nothing else is used from it

NAMES = {0: "TP_TurnThenRise", 1: "TP_TurnThenDrop", 2: "TP_TurnToStraight",
         3: "TP_Straight", 4: "TP_StraightToTurn"}

# Every hill piece becomes this one, or None to use rises and drops as the data has
# them. See docs/s2-special-stage-layouts.md for why this is "drop".
ALL_HILLS_ARE = "TP_TurnThenDrop"

SAMPLES = 6                 # points taken between each pair of a piece's control points


def load_pieces():
    with bpy.data.libraries.load(PIECES_BLEND, link=False) as (src, dst):
        dst.objects = [n for n in src.objects if n.startswith("TP_")]
    pieces = {}
    for ob in dst.objects:
        sp = ob.data.splines[0]
        bps = sp.bezier_points
        pts = [bps[0].co.copy()]
        for a, b in zip(bps, bps[1:]):
            seg = interpolate_bezier(a.co, a.handle_right, b.handle_left, b.co, SAMPLES + 1)
            pts += [p.copy() for p in seg[1:]]
        # The exit joint: where the piece ends and which way it is heading there. Only
        # the heading is kept -- the joint is level by definition, and a piece that
        # ends on a slope is reported rather than allowed to tilt the rest of the stage.
        tangent = (bps[-1].co - bps[-1].handle_left).normalized()
        slope = math.degrees(math.asin(max(-1.0, min(1.0, tangent.z))))
        yaw = math.atan2(tangent.y, tangent.x)
        length = sum((q - p).length for p, q in zip(pts, pts[1:]))
        pieces[ob.name] = {"pts": pts, "end": pts[-1].copy(), "yaw": yaw,
                           "slope": slope, "length": length}
    return pieces


def piece_list(stage):
    """(piece name, mirrored) for every segment, following the game's rule for when
    a segment's mirror flag takes effect: a straight or an enter-turn sets the
    direction at once; a hill turns the way it inherited and sets the direction for
    what follows; a turn-to-straight only inherits."""
    out = []
    mirrored = False
    for token in LAYOUTS[stage].split():
        byte = int(token, 16)
        kind, flag = byte & 0x7F, bool(byte & 0x80)
        if kind in (3, 4):
            mirrored = flag
        name = NAMES[kind]
        if kind in (0, 1) and ALL_HILLS_ARE:
            name = ALL_HILLS_ARE
        out.append((name, mirrored))
        if kind in (0, 1):
            mirrored = flag
    return out


def main():
    pieces = load_pieces()
    for name, p in sorted(pieces.items()):
        warn = "   <-- does not end level" if abs(p["slope"]) > 1.0 else ""
        print("%-20s length %7.2f  ends (%7.2f, %7.2f, %7.2f)  turns %6.1f deg  end slope %5.1f%s"
              % (name, p["length"], p["end"].x, p["end"].y, p["end"].z,
                 math.degrees(p["yaw"]), p["slope"], warn))

    frame = Matrix.Identity(4)
    pts = []
    total = 0.0
    for name, mirrored in piece_list(STAGE):
        p = pieces[name]
        side = -1.0 if mirrored else 1.0
        local = [Vector((q.x, side * q.y, q.z)) for q in p["pts"]]
        world = [frame @ q for q in local]
        pts += world if not pts else world[1:]
        end = Vector((p["end"].x, side * p["end"].y, p["end"].z))
        frame = frame @ Matrix.Translation(end) @ Matrix.Rotation(side * p["yaw"], 4, 'Z')
        total += p["length"]

    track = bpy.data.objects["HP_Track"]
    cu = track.data
    while cu.splines:
        cu.splines.remove(cu.splines[0])
    sp = cu.splines.new('BEZIER')
    keep = pts[::2] + ([pts[-1]] if (len(pts) - 1) % 2 else [])
    sp.bezier_points.add(len(keep) - 1)
    for bp, co in zip(sp.bezier_points, keep):
        bp.co = co
        bp.handle_left_type = bp.handle_right_type = 'AUTO'
    cu.twist_mode = 'Z_UP'
    cu.resolution_u = 6

    pipe = bpy.data.objects["HalfPipeSection.001"]
    xs = [v.co.x for v in pipe.data.vertices]
    pitch = max(xs) - min(xs)
    count = int(math.ceil(total / pitch))
    for ob in bpy.data.objects:
        for m in ob.modifiers:
            if m.type == 'ARRAY':
                m.fit_type = 'FIXED_COUNT'
                m.count = count
            elif m.type == 'NODES' and m.node_group and m.node_group.name == "Array":
                for it in m.node_group.interface.items_tree:
                    if getattr(it, "in_out", None) == 'INPUT' and it.name == "Count":
                        m[it.identifier] = count

    closest = None
    for a in range(0, len(pts), 4):
        for b in range(a + 80, len(pts), 4):
            if abs(pts[a].z - pts[b].z) < 25.0:
                d = math.hypot(pts[a].x - pts[b].x, pts[a].y - pts[b].y)
                if closest is None or d < closest:
                    closest = d

    seq = piece_list(STAGE)
    print("\nstage %d: %d pieces, %.1f units = %d pipe sections" % (STAGE, len(seq), total, count))
    print("mirrored pieces: %d" % sum(1 for _, m in seq if m))
    zs = [p.z for p in pts]
    print("height runs from %.1f to %.1f" % (min(zs), max(zs)))
    print("closest the path comes to itself at similar height: %s"
          % ("%.1f units" % closest if closest is not None else "never"))

    bpy.ops.wm.save_as_mainfile(filepath=OUT)
    print("saved", OUT)


main()
