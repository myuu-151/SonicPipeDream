"""The safeguard: can every original stage be rebuilt out of the ring modules?

    python native/check_ring_coverage.py            # all seven stages
    python native/check_ring_coverage.py 3          # one stage, leftovers drawn in place

It lays each stage's rings and bombs out end to end, then covers them with modules: any
module, at any frame, at any angle round the pipe, either way round. What no module can
account for is LEFT OVER, and the leftovers are grouped, drawn, and printed as rows ready
to paste into ring_modules.MODULES.

    0 left over  =  every shape the game uses is in the table.

So whether a type is missing is read off the game's data, not off anyone's memory. Run it
again after touching the table. Exit status is the number of objects left over.

A shape that is a RUN (a line, a zigzag, a corkscrew: ring_modules.RUNS) is cut by the
game to whatever length it has room for, so any stretch of a run, three frames or more,
counts as that type. Two places where the original data itself looks like a slip of the
hand are listed in ODDITIES and let through by name.

Single objects do not count as cover: `Bomb` would otherwise explain every bomb in the
game. A lone ring or bomb is only accepted where nothing else of its kind is near it.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ring_modules as rm
import s2_objects as so
from gen_s2_track import LAYOUTS, SEGMENTS

MIN_RUN = 3                 # frames: the shortest stretch of a run that still counts

# (stage, frame, angle of its first object): what it is. Not types; typos in the original.
ODDITIES = {
    (2, 543, 0x58): "a TriangleSmall whose point is 8 off-centre ($58 $68 / $68)",
    (7, 678, 0x40): "a BombCluster with its rows shuffled ($40 / $38 $40 / $48)",
}

NEAR_FRAMES = 2             # objects this close along the track...
NEAR_ANGLE = 24             # ...and this close round the pipe belong to one shape


def around(a, b):
    return min((a - b) % 256, (b - a) % 256)


def flatten(stage):
    """{(frame, angle, kind)} with frames counted from the start of the stage. A list is
    read as its segment starts and placed one segment ahead, so list i lands on segment
    i + 1."""
    lengths = [len(SEGMENTS[int(b, 16) & 0x7F]) for b in LAYOUTS[stage].split()]
    starts = [sum(lengths[:i]) for i in range(len(lengths) + 1)]
    out = set()
    for i, (objs, _) in enumerate(so.stages()[stage - 1]):
        base = starts[min(i + 1, len(starts) - 1)]
        for frame, angle, bomb in objs:
            out.add((base + frame, angle, rm.BOMB if bomb else rm.RING))
    return out


def shapes():
    """Every module with two or more objects, both ways round, biggest first."""
    out = []
    for name, module in rm.MODULES.items():
        if len(module) < 2:
            continue
        for label, m in ((name, module), (name + " (mirrored)", rm.mirrored(module))):
            m = sorted((f, a % 256, k) for f, a, k in m)
            out.append((label, m))
    for name, run in rm.RUNS.items():
        frames = sorted(set(f for f, _, _ in run))
        for label, r in ((name, run), (name + " (mirrored)", rm.mirrored(run))):
            for i in range(len(frames)):
                for j in range(i + MIN_RUN - 1, len(frames)):
                    cut = sorted((f, a % 256, k) for f, a, k in r if frames[i] <= f <= frames[j])
                    out.append(("%s, a run of %d" % (label, j - i + 1), cut))
    out.sort(key=lambda s: -len(s[1]))
    return out


SHAPES = None


def cover(objects):
    """Greedy, biggest module first; a placement must fit entirely on what is still
    uncovered. Returns (placements, leftovers)."""
    left = set(objects)
    placed = []
    global SHAPES
    SHAPES = SHAPES or shapes()
    for label, m in SHAPES:
        f0, a0, k0 = m[0]
        for (f, a, k) in sorted(left):
            if k != k0 or (f, a, k) not in left:
                continue
            want = [(f + mf - f0, (a + ma - a0) % 256, mk) for mf, ma, mk in m]
            if all(w in left for w in want):
                left.difference_update(want)
                placed.append((label, f, a, len(want)))
    # a lone object is fine where it really is alone
    for o in sorted(left):
        if not any(p != o and p[2] == o[2] and abs(p[0] - o[0]) <= NEAR_FRAMES
                   and around(p[1], o[1]) <= NEAR_ANGLE for p in objects):
            left.discard(o)
            placed.append(("single " + o[2], o[0], o[1], 1))
    return placed, left


def groups(left):
    left = set(left)
    out = []
    while left:
        comp = [left.pop()]
        grew = True
        while grew:
            grew = False
            for o in list(left):
                if any(abs(o[0] - c[0]) <= NEAR_FRAMES and around(o[1], c[1]) <= NEAR_ANGLE
                       for c in comp):
                    comp.append(o)
                    left.discard(o)
                    grew = True
        out.append(sorted(comp))
    return sorted(out)


def as_row(group):
    """The group as a module literal, centred on its own middle."""
    f0 = group[0][0]
    ref = group[0][1]
    rel = [((a - ref + 128) % 256) - 128 for _, a, _ in group]
    mid = (min(rel) + max(rel)) // 2
    return "[" + ", ".join("(%d, %d, %s)" % (f - f0, r - mid, "RING" if k == rm.RING else "BOMB")
                           for (f, _, k), r in zip(group, rel)) + "]"


def draw(group):
    f0 = group[0][0]
    rows = {}
    for f, a, k in group:
        rows.setdefault(f - f0, {})[a // 4] = "o" if k == rm.RING else "X"
    lo = min(c for r in rows.values() for c in r)
    hi = max(c for r in rows.values() for c in r)
    for f in sorted(rows):
        print("      %2d  %s" % (f, "".join(rows[f].get(c, " ") for c in range(lo, hi + 1))))


def main():
    only = int(sys.argv[1]) if len(sys.argv) > 1 else None
    total_left = 0
    used = {}
    for stage in ([only] if only else range(1, 8)):
        objects = flatten(stage)
        placed, left = cover(objects)
        total_left += len(left)
        for label, _, _, _ in placed:
            name = label.split(",")[0].replace(" (mirrored)", "")
            used[name] = used.get(name, 0) + 1
        print("stage %d: %3d objects, %3d modules placed, %3d left over"
              % (stage, len(objects), len(placed), len(left)))
        for g in groups(left):
            if (stage, g[0][0], g[0][1]) in ODDITIES:
                print("   let through at frame %d: %s" % (g[0][0], ODDITIES[(stage, g[0][0], g[0][1])]))
                total_left -= len(g)
                continue
            print("   left over at frame %d, angle $%02X: %d objects" % (g[0][0], g[0][1], len(g)))
            draw(g)
            print("      as a module: %s" % as_row(g))
    if not only:
        print("\nused: " + ", ".join("%s x%d" % kv for kv in sorted(used.items(), key=lambda kv: -kv[1])))
        unused = [n for n in rm.MODULES if n not in used and len(rm.MODULES[n]) > 1 and n not in rm.RUNS]
        print("\nnever needed (made of smaller modules the cover found first): " + ", ".join(unused))
    print("\n%d left over" % total_left)
    return total_left


if __name__ == "__main__":
    sys.exit(min(main(), 255))
