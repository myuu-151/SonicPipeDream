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


def capsule(kind, pairs, gapped=False):
    """One, then `pairs` rows of two, then one: the game's staple. 1 pair is the small
    diamond; 3 pairs, eight rings, is the commonest ring shape in the game. `gapped`
    leaves a frame empty after the first one, as the game sometimes does."""
    return rows(kind, (0,), *([()] if gapped else []), *[(-8, 8)] * pairs, (0,))


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


def hook(kind, out, hold, side=1):
    """Slides across 4 a frame and stays there: a sweep that never comes back."""
    return [(i, side * 4 * min(i, out), kind) for i in range(out + hold)]


def wave(kind, reach=32, per_frame=8):
    """One strand swinging out to one side, back through the middle, out to the other
    and half way home: stage 6's slalom line. 16 frames at the game's 32 and 8."""
    n = reach // per_frame
    path = ([per_frame * i for i in range(n + 1)] + [reach]
            + [reach - per_frame * i for i in range(1, 2 * n + 1)]
            + [-reach + per_frame * i for i in range(1, n - 1)])
    return [(i, a, kind) for i, a in enumerate(path)]


def bounce(kind):
    """Two strands run out to the rims, wait a frame, and come back to meet on the
    floor: how stage 5 leads into its helix."""
    out = [16, 32, 48, 64, 64, 48, 32, 16]
    return [(i, s * a, kind) for i, a in enumerate(out) for s in (-1, 1)]


def funnel(kind, frames=10, wide=48, per_frame=4):
    """Two walls closing in on the centre line."""
    return [(i, s * (wide - per_frame * i), kind) for i in range(frames) for s in (-1, 1)]


def stairs(shape, steps, every=4, across=-16):
    """The same shape again and again, stepping across the pipe."""
    return [(f + n * every, a + n * across, k) for n in range(steps) for f, a, k in shape]


def dotted(kind, count, every=2):
    return [(i * every, 0, kind) for i in range(count)]


def put(module, frame=0, angle=0):
    """The module moved along and round, for building one module out of others."""
    return [(f + frame, ((a + angle + 128) % 256) - 128, k) for f, a, k in module]


def twin(module, apart=48):
    """The same shape on both walls at once. 48 is the game's usual ($10 and $70);
    64 is the rims, 96 is up over the pipe where only a jump reaches."""
    return put(module, 0, -apart) + put(module, 0, apart)


def train(shape, angles, every=4):
    """The same shape again and again, at the angles given."""
    return [o for n, a in enumerate(angles) for o in put(shape, n * every, a)]


# Stage 7's ring storm: forty rings over twenty frames, two a frame, thrown all round
# the pipe. Too irregular to make from a rule, so it is kept as the angles themselves.
# Its second ten frames repeat the first, but for two rings a single unit out; that is
# the game's, and check_ring_coverage.py would notice if it were tidied away.
_STORM = [(-59, 22), (35, 112), (6, -43), (-103, 80), (62, 32), (64, -9), (-51, 40),
          (-91, -128), (32, -13), (-24, 104),
          (-59, 22), (35, 112), (5, -42), (-103, 80), (62, 32), (64, -9), (-51, 40),
          (-91, -128), (32, -13), (-24, 104)]
CONFETTI = [(f, a, RING) for f, pair in enumerate(_STORM) for a in pair]


MODULES = {
    # --- rings: clusters ------------------------------------------------------------
    "ClusterSmall":    capsule(RING, 1),        #  4   x46 in the game
    "ClusterMedium":   capsule(RING, 2),        #  6   x17
    "Cluster":         capsule(RING, 3),        #  8   x47, the staple
    "ClusterLong":     capsule(RING, 4),        # 10   x9
    "ClusterLong12":   capsule(RING, 5),        # 12   x3
    "ClusterLonger":   capsule(RING, 6),        # 14   stage 1's centre-line run
    "ClusterLongest":  capsule(RING, 7),        # 16   stage 2
    "ClusterBig":      diamond(RING, 3),        #  9   x7
    "ClusterStairs":   stairs(capsule(RING, 1), 3),   # 12   stage 2: small ones stepping across
    "ClusterStairsLong": train(capsule(RING, 1), (48, 48, 32, 16, 0, -16)),   # 24   stage 2
    "ClusterSmallGapped": capsule(RING, 1, True),  #  4   stage 3
    "ClusterGapped":   capsule(RING, 3, True),  #  8   x5: a beat's rest
    "ClusterLong12Gapped": capsule(RING, 5, True),   # 12   stage 7
    "ClusterSparse":   rows(RING, (0,), (-8, 8), (), (-8, 8), (), (-8, 8), (0,)),   # 8   stage 6
    # --- rings: the same shape in two places ----------------------------------------
    "TwinClusterSmall": twin(capsule(RING, 1)),        #  8   both walls at once
    "TwinOverhead":    twin(capsule(RING, 1), 96),     #  8   up over the pipe: jump for them
    "ClusterCascade":  (put(capsule(RING, 1), 0) + put(twin(capsule(RING, 1)), 4)
                        + put(twin(capsule(RING, 1), 96), 8)),   # 20   stage 2: floor, walls, overhead
    "TwinTriangleRims": twin(triangle(RING, 4), 64),   # 20   stage 5: one on each rim
    # --- rings: triangles -----------------------------------------------------------
    "TriangleSmall":   triangle(RING, 2),       #  3   x13
    "Triangle":        triangle(RING, 3),       #  6   x8
    "TriangleBig":     triangle(RING, 4),       # 10   x33
    "TriangleHuge":    triangle(RING, 5),       # 15   stage 4's finale
    "TriangleTrain":   train(triangle(RING, 2), (0, 0, 0)),              #  9   stage 2
    "TriangleSnake":   train(triangle(RING, 2), (0, 16, 32, 48, 32, 16)),   # 18   stage 2
    "TriangleWeave":   train(triangle(RING, 3), (-16, 16, -16), 8),      # 18   stage 1
    "Arrowhead":       rows(RING, (0,), (-8, 8), (-16, -8, 0, 8, 16)),   # 8   stage 4
    # --- rings: rows ----------------------------------------------------------------
    "Zigzag":          zigzag(RING, 8),         #  8   stage 1 is mostly these
    "Weave":           weave(RING, 8),          # 12   x8
    "Line":            line(RING, 5),           #  5
    "WeaveShort":      weave(RING, 6),          #  9   x5
    "LineLong":        line(RING, 10),          # 10
    "LineDotted":      dotted(RING, 5),         #  5   every other frame; stage 4
    "DottedArrow":     (dotted(RING, 5) + put(rows(RING, (-8, 0, 8)), 10)
                        + put(rows(RING, (-8, 0, 8)), 12) + [(14, 0, RING)]),   # 12   stage 4's opener
    "Row3":            rows(RING, (-8, 0, 8)),  #  3   abreast
    # --- rings: curves and spirals --------------------------------------------------
    "SweepLeft":       sweep(RING, 6, 4, -1),   # 16   stage 3, in left/right pairs
    "SweepRight":      sweep(RING, 6, 4, +1),   # 16
    "HookLeft":        hook(RING, 11, 4, -1),   # 15   a sweep that stays out; stage 3
    "HookRight":       hook(RING, 11, 4, +1),   # 15
    "Wave":            wave(RING),              # 16   stage 6
    "Slant":           slant(RING, 6),          #  6
    "Helix":           helix(RING),             # 30   x5, stage 5: right round the pipe
    "HelixUp":         [o for o in helix(RING) if o[0] <= 8],    # 16   floor to overhead
    "HelixDown":       put([o for o in helix(RING) if o[0] >= 8], -8) + [(8, 0, RING)],   # 16
    "HelixBounce":     bounce(RING),            # 16   out to the rims and back
    "Confetti":        list(CONFETTI),          # 40   stage 7
    # --- bombs ----------------------------------------------------------------------
    "Bomb":            line(BOMB, 1),           #  1   x83
    "BombCluster":     capsule(BOMB, 1),        #  4   x78, the staple
    "BombClusterLong": capsule(BOMB, 2),        #  6   x16
    "BombClusterTight": rows(BOMB, (0,), (-6, 6), (0,)),   # 4   stage 2's own: 6 apart, not 8
    "BombTrain":       train(capsule(BOMB, 1), (0, 0, 0), 8),    # 12   stage 2
    "BombDots":        dotted(BOMB, 3, 4),      #  3   down the centre line, every 4 frames
    "BombTwin":        twin(capsule(BOMB, 1)),  #  8   x12: both walls, the floor is the way through
    "BombTwinNear":    twin(capsule(BOMB, 1), 32),   # 8   stage 6
    "BombDiamond":     diamond(BOMB, 3, True),  #  8   hollow
    "BombRow3":        rows(BOMB, (-16, 0, 16)),
    "BombRow5":        rows(BOMB, (-32, -16, 0, 16, 32)),
    "BombChevron":     rows(BOMB, (0,), (-8, 8)),
    "BombWall":        wall(BOMB),              # 16   x20: jump it
    "BombGate":        wall(BOMB, gap_at=0, gap=3),   # 13: the way through is the floor
    "BombGateWide":    wall(BOMB, gap_at=-8, gap=4),  # 12
    "BombSpiral":      corkscrew(BOMB, 16, -16),      # 16   right round in one straight
    "BombFunnel":      funnel(BOMB),            # 20   stage 3: two walls closing in
    "BombCorkscrew":   corkscrew(BOMB, 24),     # 24   stage 3
    "BombSlant":       slant(BOMB, 10),         # 10
    # --- rings and bombs together, as the game pairs them ---------------------------
    "Slalom":          wave(RING) + put(capsule(BOMB, 1), 3) + put(capsule(BOMB, 1), 12),
    "LineInCorkscrew": put(corkscrew(BOMB, 24), 0, -64) + put(line(RING, 10), 11),
    "HookToWallLeft":  hook(RING, 8, 4, -1) + [(12, -28, RING)] + put(wall(BOMB), 13),
    "HookToWallRight": hook(RING, 8, 4, +1) + [(12, 28, RING)] + put(wall(BOMB), 13),
    "WeaveByBombs":    put(weave(RING, 8), 0, -32) + put(dotted(BOMB, 3, 4), 0),
    "GateAndTriangle": wall(BOMB, gap_at=-8, gap=4) + put(triangle(RING, 4), 6, 32),
    "WallThenCluster": wall(BOMB) + put(capsule(RING, 3), 2),      # jump it and land in rings
    "ChevronSlantLeft":  rows(BOMB, (0,), (-8, 8)) + put(slant(RING, 6, -4), 4, -14),
    "ChevronSlantRight": rows(BOMB, (0,), (-8, 8)) + put(slant(RING, 6), 4, 14),
    "TwinBombsAndCluster": twin(capsule(BOMB, 1)) + put(capsule(RING, 3), 0),   # stage 1's one hazard
    "Gauntlet":        (put(capsule(RING, 5), 0) + put(twin(capsule(BOMB, 1)), 4)),   # stage 3
    # One wall is rings and the other bombs, and then they change places.
    "SwapWalls":       (put(capsule(BOMB, 1), 0, -40) + put(capsule(RING, 3), 0, 40)
                        + put(capsule(RING, 3), 8, -40) + put(capsule(BOMB, 1), 8, 40)),   # stage 6
    "SwapWallsMedium": (put(capsule(BOMB, 2), 0, -40) + put(capsule(RING, 2), 0, 40)
                        + put(capsule(RING, 2), 8, -40) + put(capsule(BOMB, 2), 8, 40)),   # stage 7
    "SwapThree":       (twin(capsule(BOMB, 1), 40) + put(capsule(RING, 1), 0)
                        + put(twin(capsule(RING, 1), 40), 8) + put(capsule(BOMB, 1), 8)),  # stage 6
    # Clusters on alternate walls, single bombs down the centre line between them.
    "ClusterByBombs":  (put(capsule(RING, 3), 0, -40) + put(capsule(RING, 3), 12, 40)
                        + [(f, 0, BOMB) for f in (0, 4, 8, 12, 16, 20)]),   # stage 7
}


# Shapes that are a run: the game cuts them to whatever length the segment has room for,
# so the TYPE is the run and any stretch of it counts. Each is given here at full length;
# the named modules above are the cuts worth having by name. check_ring_coverage.py
# accepts any stretch of three frames or more.
RUNS = {
    "Line":          line(RING, 24),
    "LineDotted":    dotted(RING, 12),
    "Zigzag":        zigzag(RING, 24),
    "Weave":         weave(RING, 24),
    "Wave":          wave(RING) + [(16 + f, a - 8, k) for f, a, k in wave(RING)[:15]],   # stage 6 runs two on end
    "Sweep":         sweep(RING, 11, 4),
    "Slant":         slant(RING, 16),
    "Helix":         helix(RING, 2),
    "BombDots":      dotted(BOMB, 8, 4),
    "BombCorkscrew": corkscrew(BOMB, 32),
    "BombSpiral":    corkscrew(BOMB, 16, -16),
    "BombSlant":     slant(BOMB, 16),
    "BombFunnel":    funnel(BOMB, 12, 56),
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
