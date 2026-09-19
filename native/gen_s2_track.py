"""Shape HP_Track after a real Sonic 2 special stage.

    blender -b <curve scene.blend> --python native/gen_s2_track.py -- <out.blend> [stage 1-7]

WHAT IS EXACT AND WHAT IS NOT

The original track is not 3D. It is pre-rendered animation, assembled from five
segment types, and each stage is a list of them. Those lists are the game's own
data (Sonic Retro's s2disasm, misc/Special stage level layouts.nem, decoded),
and so are the frame counts of each segment. So the ORDER of straights, turns,
rises and drops here, and how long each lasts relative to the others, is the
original's, exactly.

What the original does not contain is any measurement: no turn radius, no slope.
How far a turn turns and how high a rise climbs are choices, made below as plain
constants to be tuned by eye against footage.
"""

import math
import sys

try:
    import bpy
except ImportError:          # imported outside Blender, to scan the path maths
    bpy = None

# The command line is only this script's when it is the one being run; imported for
# its layouts, it must not try to read someone else's arguments.
OUT, STAGE = None, 1
if __name__ == "__main__" and "--" in sys.argv:
    args = sys.argv[sys.argv.index("--") + 1:]
    OUT = args[0] if args else None
    STAGE = int(args[1]) if len(args) > 1 else 1

# --- the game's data -------------------------------------------------------------
# One byte per segment. Low bits are the segment type, $80 is the mirror flag.
LAYOUTS = {
    1: "03 03 03 04 02 03 03 03 03 03 03 04 02 03 03 03 03 04 00 02 03 03 04 81 02 03 03 04 "
       "02 03 04 02 03 84 02 03 04 02 83 84 02 03 03 03 03 00",
    2: "03 03 03 04 02 03 03 04 00 80 00 00 02 03 03 03 03 03 03 03 03 04 01 02 03 83 03 03 "
       "03 04 02 03 04 01 00 80 81 02 03 03 03 03 03 03",
    3: "03 83 83 84 02 03 03 03 03 03 03 03 03 04 81 80 81 02 03 03 03 04 80 00 01 80 00 81 "
       "02 03 03 03 03 84 80 81 01 80 00 02 03 03 03 03",
    4: "03 03 03 03 03 04 80 02 03 04 01 02 03 04 02 03 03 03 03 03 04 01 02 83 84 02 03 04 "
       "02 83 84 01 02 03 03 03 03 04 02 83 84 80 02 83 84 01 02 83 84 02 03 03 03 03 03 03",
    5: "03 03 83 84 02 03 03 03 03 03 04 01 80 81 02 03 03 03 03 03 03 03 04 80 01 02 03 03 "
       "03 83 84 00 81 01 80 02 03 03 03 03 03 03 03 03",
    6: "03 03 03 04 02 03 03 03 03 04 81 81 81 02 03 03 03 04 02 03 03 03 03 84 00 00 02 03 "
       "03 03 03 04 00 81 02 03 03 03 04 02 03 04 02 03 04 02 03 04 02 83 84 02 03 04 02 83 "
       "84 02 03 03 03 03",
    # Stage 7 runs to the end of the decompressed block, which is padded to a whole
    # number of 32-byte tiles, so its last few bytes may be padding rather than track.
    7: "03 03 03 04 02 03 03 03 04 81 00 80 00 02 03 83 84 00 02 03 03 03 83 84 81 02 03 03 "
       "03 04 80 02 03 03 03 03 03 04 01 01 01 01 01 01 01 80 80 80 02 03 03 03 03 03 03 00 "
       "00 00 03 03 03 04 80 02 03 03 03 03 03 04 01 01 01 01",
}

# Each segment type as the animation the game plays for it, frame by frame:
#   T turning   E entering a turn   X leaving a turn
#   S straight  R rising            D dropping
SEGMENTS = {
    0: "T" * 7 + "R" * 17,      # turn, then rise
    1: "T" * 7 + "D" * 17,      # turn, then drop
    2: "T" * 7 + "X" * 5,       # turn, then straighten out
    3: "S" * 16,                # straight
    4: "S" * 4 + "E" * 7,       # straight, then enter a turn
}

# The game only re-reads a segment's mirror flag on particular frames, where the
# track is drawn head-on and a flip cannot be seen; between them the direction is
# whatever it was. From SSTrack_Orientation's handling in s2.asm: straight frame
# 2, rise frame 14, drop frame 6.
def reads_flag(kind, i):
    if kind == 3:
        return i % 4 == 1
    if kind == 4:
        return i == 1
    if kind == 0:
        return i == 7 + 13
    if kind == 1:
        return i == 7 + 5
    return False


# --- the game's own motion profiles ------------------------------------------------
# The game scrolls its background a set amount on each track frame: sideways through
# a turn, vertically through a rise or drop. Those tables (SSPlaneB_SetHorizOffset
# and SSTrack_SetVscroll in s2.asm, summed over a frame's five ticks) are the only
# record of HOW a turn or a hill is paced, so the curve takes its pacing from them.
# Each sums to 512; only the proportions are used.
#
# All of a turn happens in the twelve frames beginning with the turning frames --
# ramp in, eight frames at full rate, ramp out -- whatever follows them (the rest of
# a rise, a drop, or the exit). The "enter a turn" frames of type 4 turn nothing: on
# screen they show the bend arriving, not the track bending under you.
YAW_PROFILE = [10, 22, 56, 56, 56, 56, 56, 56, 56, 56, 22, 10]          # frames 0-11 of types 0, 1, 2
RISE_PROFILE = {10: 5, 11: 5, 12: 22, 13: 56, 14: 56, 15: 56, 16: 56, 17: 56, 18: 56,
                19: 44, 20: 46, 21: 34, 22: 17, 23: 3}                   # frame -> amount, type 0
DROP_PROFILE = {11: 3, 12: 17, 13: 34, 14: 46, 15: 44, 16: 56, 17: 56, 18: 56, 19: 56,
                20: 56, 21: 56, 22: 22, 23: 10}                          # type 1
assert sum(YAW_PROFILE) == sum(RISE_PROFILE.values()) == sum(DROP_PROFILE.values()) == 512

# --- the choices -------------------------------------------------------------------
# The data does not say which way an unmirrored turn goes.
UNMIRRORED_TURNS = "right"

# What the two hill segments do.
#
#   "all_down"  both are drops, so a stage only ever descends. This is how the
#               stage is remembered by the person who knows it best, and it is what
#               is built.
#   "as_data"   type 0 steps up, type 1 steps down. This is what the evidence in
#               the ROM points to (see docs/s2-special-stage-layouts.md): stage 1
#               would step up at segment 18, down at 23, up at 45.
#   "inverted"  type 0 down, type 1 up: stage 1 becomes a dip and a final drop.
#
# Either way the pacing of each hill comes from the game's own table.
HILLS = "all_down"

# How far one turn turns, in all. The original has no such number.
#
# What limits it is the stage running into itself: stage 1 has nine turns one way
# and three the other, so it winds round by six turns' worth in all. On the level,
# 50 degrees was already a collision. With every hill a drop the stage descends 60
# units over its length, so its late parts pass UNDER its early ones and the limit
# goes away: 60 degrees stays 99 units clear, 90 still 35. The script prints how
# close the path comes to itself at similar height; check it after any change.
TURN_DEG = 60.0
# Height of one drop. The steepest frame of the game's profile moves 56/512 of it,
# so 20 puts the steepest part of a drop at about 60 degrees -- a drop you cannot see
# over, as in the original, where 10 was a gentle ramp you could miss.
CLIMB = 20.0
BANK_DEG = 0.0              # lean into turns; 0 keeps the floor level throughout

POINT_EVERY = 2             # one curve point per this many frames


def build_frames(stage):
    frames = []             # (segment type, frame within it, mirrored)
    mirrored = False
    for token in LAYOUTS[stage].split():
        byte = int(token, 16)
        kind, flag = byte & 0x7F, bool(byte & 0x80)
        for i in range(len(SEGMENTS[kind])):
            if reads_flag(kind, i):
                mirrored = flag
            frames.append((kind, i, mirrored))
    return frames


def walk(stage, step, turn_deg=None, climb=None):
    """The stage as a list of (x, y, z, tilt) points, one per frame, plus how
    close the path comes to itself."""
    turn_deg = TURN_DEG if turn_deg is None else turn_deg
    climb = CLIMB if climb is None else climb
    frames = build_frames(stage)

    side = -1.0 if UNMIRRORED_TURNS == "right" else 1.0
    # Signed height change for (type 0, type 1).
    hill = {"all_down": (-1.0, -1.0), "as_data": (1.0, -1.0), "inverted": (-1.0, 1.0)}[HILLS]

    heading = 0.0
    x = y = z = 0.0
    pts = [(x, y, z, 0.0)]
    for kind, i, mirrored in frames:
        yaw = 0.0
        if kind in (0, 1, 2) and i < len(YAW_PROFILE):
            yaw = YAW_PROFILE[i] / 512.0 * side * (-1.0 if mirrored else 1.0)
        dz = 0.0
        if kind == 0:
            dz = hill[0] * climb * RISE_PROFILE.get(i, 0) / 512.0
        elif kind == 1:
            dz = hill[1] * climb * DROP_PROFILE.get(i, 0) / 512.0
        # Every frame covers the same distance ALONG the track, so a steep frame
        # moves less far forward. Without this a drop would stretch the pipe.
        dz = max(-0.97 * step, min(0.97 * step, dz))
        flat = math.sqrt(step * step - dz * dz)

        heading += math.radians(turn_deg) * yaw
        x += flat * math.cos(heading)
        y += flat * math.sin(heading)
        z += dz
        # Bank in proportion to how hard it is turning right now.
        pts.append((x, y, z, -math.radians(BANK_DEG) * yaw * 512.0 / 56.0))

    # Does it ever run back over itself? The original cannot say -- it has no
    # geometry to collide -- so a faithful list can still cross its own path.
    # Parts far apart in height pass over and under, which is fine.
    closest = None
    for a in range(0, len(pts), 3):
        for b in range(a + 60, len(pts), 3):
            if abs(pts[a][2] - pts[b][2]) < 25.0:
                d = math.hypot(pts[a][0] - pts[b][0], pts[a][1] - pts[b][1])
                if closest is None or d < closest[0]:
                    closest = (d, a, b)
    return frames, pts, math.degrees(heading), closest


def main():
    track = bpy.data.objects["HP_Track"]
    pipe = bpy.data.objects["HalfPipeSection.001"]
    xs = [v.co.x for v in pipe.data.vertices]
    pitch = max(xs) - min(xs)
    # One 'straight' segment is 16 frames; make that exactly one pipe section, so
    # hoops and arches fall on the stage's own rhythm.
    step = pitch / 16.0

    frames, pts, net_heading, closest = walk(STAGE, step)
    n = len(frames)
    x, y = pts[-1][0], pts[-1][1]
    height = [p[2] for p in pts]

    cu = track.data
    while cu.splines:
        cu.splines.remove(cu.splines[0])
    sp = cu.splines.new('BEZIER')
    keep = pts[::POINT_EVERY]
    if keep[-1] != pts[-1]:
        keep.append(pts[-1])
    sp.bezier_points.add(len(keep) - 1)
    for bp, (px, py, pz, tilt) in zip(sp.bezier_points, keep):
        bp.co = (px, py, pz)
        bp.tilt = tilt
        bp.handle_left_type = bp.handle_right_type = 'AUTO'
    cu.twist_mode = 'Z_UP'
    cu.resolution_u = 8

    length = n * step
    count = int(math.ceil(length / pitch))
    for ob in bpy.data.objects:
        for m in ob.modifiers:
            if m.type == 'ARRAY':
                m.fit_type = 'FIXED_COUNT'
                m.count = count
            elif m.type == 'NODES' and m.node_group and m.node_group.name == "Array":
                for it in m.node_group.interface.items_tree:
                    if getattr(it, "in_out", None) == 'INPUT' and it.name == "Count":
                        m[it.identifier] = count

    kinds = [int(t, 16) & 0x7F for t in LAYOUTS[STAGE].split()]
    print()
    print("stage %d: %d segments, %d frames" % (STAGE, len(kinds), n))
    print("length %.1f units = %d pipe sections of %.3f" % (length, count, pitch))
    hill = {"all_down": (-1, -1), "as_data": (1, -1), "inverted": (-1, 1)}[HILLS]
    ups = sum(kinds.count(k) for k in (0, 1) if hill[k] > 0)
    downs = sum(kinds.count(k) for k in (0, 1) if hill[k] < 0)
    print("turns %d, rises %d, drops %d  (HILLS = %s)"
          % (sum(1 for k in kinds if k in (0, 1, 2)), ups, downs, HILLS))
    zs = [p[2] for p in pts]
    print("height runs from %.1f to %.1f, starting at 0" % (min(zs), max(zs)))
    print("net heading change %.0f degrees, finishes at (%.0f, %.0f, %.0f)"
          % (net_heading, x, y, height[-1]))
    xs_, ys_ = [p[0] for p in pts], [p[1] for p in pts]
    print("footprint %.0f x %.0f units" % (max(xs_) - min(xs_), max(ys_) - min(ys_)))
    if closest:
        print("closest the path comes to itself: %.1f units (frames %d and %d); "
              "the pipe is about 29 wide" % closest)

    bpy.ops.wm.save_as_mainfile(filepath=OUT)
    print("saved", OUT)


# Only when run as the script, so other scripts can import the layouts from here.
if __name__ == "__main__" and bpy is not None and OUT:
    main()
