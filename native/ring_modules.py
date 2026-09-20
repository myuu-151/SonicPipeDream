"""The ring and bomb modules: the object half of the two libraries.

A module is to rings what a track piece is to the pipe: a small hand-sized shape that a
stage lists by name. Every shape here was read out of the original game's placement
lists (native/s2_objects.py draws them; docs/s2-special-stage-objects.md counts them),
so a stage built from these looks like Sonic 2 without copying any one stage.

No Blender in here, so the generator, the preview and one day the engine exporter can
all import it.

A module is a list of (frame, angle, kind):
    frame   how far along the track, in track frames. 16 frames = one straight piece.
    angle   round the pipe, in the game's 256ths of a circle, RELATIVE to where the
            module is put. Put a module at 0 and it sits on the floor's centre line;
            +-64 are the rims. The game's own byte is this plus $40.
    kind    RING or BOMB
"""

import math

RING = "ring"
BOMB = "bomb"

# --- the pipe, measured from TrackPiecesPack.blend ----------------------------------
SECTION = 40.161            # one straight piece
FRAMES_PER_SECTION = 16     # the original's straight is 16 frames
FRAME = SECTION / FRAMES_PER_SECTION
PIPE_RADIUS = 10.0          # the pipe's axis is this far above the floor's centre line
HOVER = 1.9                 # a ring's centre above the pipe's surface

# Which rim the game's angle $00 is. Not in the data (the same open question as which
# way an unmirrored turn goes); every module is either symmetrical or comes as a pair.
ANGLE_00_SIDE = "right"


def rows(kind, *row_angles, start=0, step=1):
    """One tuple of angles per frame."""
    return [(start + i * step, a, kind) for i, row in enumerate(row_angles) for a in row]


def capsule(kind, pairs):
    """One, then `pairs` rows of two, then one: the game's staple. 1 pair is the small
    diamond; 3 pairs, eight rings, is the commonest ring shape in the game."""
    return rows(kind, (0,), *[(-8, 8)] * pairs, (0,))


def diamond(kind, width, hollow=False):
    """1, 2, .. width .. 2, 1."""
    out = []
    for n in list(range(1, width + 1)) + list(range(width - 1, 0, -1)):
        row = [-8 * (n - 1) + 16 * k for k in range(n)]
        if hollow and n > 2:
            row = [row[0], row[-1]]
        out.append(tuple(row))
    return rows(kind, *out)


def triangle(kind, width):
    """Widest row first, narrowing to one: it funnels the player to its point."""
    return rows(kind, *[tuple(-8 * (n - 1) + 16 * k for k in range(n))
                        for n in range(width, 0, -1)])


def zigzag(kind, frames, first=-4):
    """One a frame, alternating either side of the line."""
    return [(i, first if i % 2 == 0 else -first, kind) for i in range(frames)]


def weave(kind, frames):
    """Two, one, two, one: a double zigzag."""
    return rows(kind, *[(-8, 8) if i % 2 == 0 else (0,) for i in range(frames)])


def line(kind, frames):
    return [(i, 0, kind) for i in range(frames)]


def sweep(kind, out, hold, side=1):
    """Slides across the pipe 4 a frame, holds, slides back. side=-1 goes the other way."""
    path = [4 * i for i in range(out)] + [4 * out] * hold + [4 * i for i in range(out - 1, -1, -1)]
    return [(i, side * a, kind) for i, a in enumerate(path)]


def slant(kind, frames, per_frame=4):
    """A straight diagonal."""
    half = per_frame * (frames - 1) / 2.0
    return [(i, int(round(i * per_frame - half)), kind) for i in range(frames)]


def helix(kind, turns=1):
    """Two strands that cross on the floor and again overhead, all the way round the
    pipe: stage 5's spiral. 16 frames a turn."""
    out = []
    for i in range(16 * turns):
        a = 16 * (i % 16)
        a = a - 256 if a > 128 else a
        out.append((i, a, kind))
        if a % 128:
            out.append((i, -a, kind))
    return out


def corkscrew(kind, frames, per_frame=-8):
    """One strand winding round the pipe: stage 3's bomb spiral, 8 a frame."""
    return [(i, ((i * per_frame + 128) % 256) - 128, kind) for i in range(frames)]


def wall(kind, gap_at=None, gap=0):
    """A ring of sixteen right round the pipe in one frame. `gap` of them are left out,
    centred on `gap_at`: the way through."""
    out = []
    for k in range(16):
        a = ((16 * k + 128) % 256) - 128
        if gap and abs(((a - gap_at + 128) % 256) - 128) <= 8 * (gap - 1):
            continue
        out.append((0, a, kind))
    return out


# Stage 7's ring storm: twenty rings over ten frames, thrown all round the pipe, and
# repeated. Too irregular to make from a rule, so it is kept as the angles themselves.
CONFETTI = [(0, -59, RING), (0, 22, RING), (1, 35, RING), (1, 112, RING), (2, -43, RING),
            (2, 6, RING), (3, 80, RING), (3, -103, RING), (4, 32, RING), (4, 62, RING),
            (5, -9, RING), (5, 64, RING), (6, -51, RING), (6, 40, RING), (7, 128, RING),
            (7, -91, RING), (8, -13, RING), (8, 32, RING), (9, -24, RING), (9, 104, RING)]


MODULES = {
    # --- rings: clusters ------------------------------------------------------------
    "ClusterSmall":    capsule(RING, 1),        #  4   x46 in the game
    "ClusterMedium":   capsule(RING, 2),        #  6   x17
    "Cluster":         capsule(RING, 3),        #  8   x47, the staple
    "ClusterLong":     capsule(RING, 4),        # 10   x9
    "ClusterLonger":   capsule(RING, 6),        # 14   stage 1's centre-line run
    "ClusterBig":      diamond(RING, 3),        #  9   x7
    # --- rings: triangles -----------------------------------------------------------
    "TriangleSmall":   triangle(RING, 2),       #  3   x13
    "Triangle":        triangle(RING, 3),       #  6   x8
    "TriangleBig":     triangle(RING, 4),       # 10   x33
    "TriangleHuge":    triangle(RING, 5),       # 15   stage 4's finale
    # --- rings: rows ----------------------------------------------------------------
    "Zigzag":          zigzag(RING, 8),         #  8   stage 1 is mostly these
    "Weave":           weave(RING, 8),          # 12   x8
    "Line":            line(RING, 5),           #  5
    "LineLong":        line(RING, 10),          # 10
    # --- rings: curves and spirals --------------------------------------------------
    "SweepLeft":       sweep(RING, 6, 4, -1),   # 16   stage 3, in left/right pairs
    "SweepRight":      sweep(RING, 6, 4, +1),   # 16
    "Slant":           slant(RING, 6),          #  6
    "Helix":           helix(RING),             # 30   x5, stage 5: right round the pipe
    "Confetti":        list(CONFETTI),          # 20   stage 7
    # --- bombs ----------------------------------------------------------------------
    "Bomb":            line(BOMB, 1),           #  1   x83
    "BombCluster":     capsule(BOMB, 1),        #  4   x78, the staple
    "BombClusterLong": capsule(BOMB, 2),        #  6   x16
    "BombDiamond":     diamond(BOMB, 3, True),  #  8   hollow
    "BombRow3":        rows(BOMB, (-16, 0, 16)),
    "BombRow5":        rows(BOMB, (-32, -16, 0, 16, 32)),
    "BombChevron":     rows(BOMB, (0,), (-8, 8)),
    "BombWall":        wall(BOMB),              # 16   x20: jump it
    "BombGate":        wall(BOMB, gap_at=0, gap=3),   # 13: the way through is the floor
    "BombCorkscrew":   corkscrew(BOMB, 24),     # 24   stage 3
    "BombSlant":       slant(BOMB, 10),         # 10
}


def length(module):
    """Frames the module takes up."""
    return max(f for f, _, _ in module) + 1


def count(module, kind=RING):
    return sum(1 for _, _, k in module if k == kind)


def span(module):
    """(lowest, highest) angle it reaches. Beyond +-64 it is over the rims, in the air."""
    return min(a for _, a, _ in module), max(a for _, a, _ in module)


def mirrored(module):
    return [(f, -a, k) for f, a, k in module]


def local(frame, angle, at=0.0, hover=HOVER):
    """Where an object sits on a STRAIGHT piece: x along the track from the module's
    start, y across, z up from the floor's centre line. `at` is the angle the module
    was put at. On a bent piece, x is distance along the piece's curve and (y, z) are
    offsets in the curve's own frame there."""
    side = -1.0 if ANGLE_00_SIDE == "right" else 1.0
    t = side * (angle + at) * 2.0 * math.pi / 256.0
    r = PIPE_RADIUS - hover
    return (frame * FRAME, r * math.sin(t), PIPE_RADIUS - r * math.cos(t))


if __name__ == "__main__":
    print("%-16s %5s %6s %6s  %s" % ("module", "rings", "bombs", "frames", "angles"))
    for name, m in MODULES.items():
        print("%-16s %5d %6d %6d  %+d..%+d" % ((name, count(m), count(m, BOMB), length(m)) + span(m)))
        grid = {}
        for f, a, k in m:
            grid.setdefault(f, {})[(a + 128) // 4] = "o" if k == RING else "X"
        lo = min(c for r in grid.values() for c in r)
        hi = max(c for r in grid.values() for c in r)
        for f in sorted(grid):
            print("      %2d  %s" % (f, "".join(grid[f].get(c, " ") for c in range(lo, hi + 1))))
