"""Measure the original seven stages and write the rulebook the stage generator deals from.

    python native/make_ring_rulebook.py        -> native/ring_rulebook.json

Nothing in the rulebook is a guess. For each stage it records:

    quota         the rings needed by the first check, the second, and the third -- the one
                  that leads to the emerald. Cumulative, as the game counts them. Both
                  tables: playing alone, and Sonic and Tails together.
    sections      a stage is three sections, each ending at a check. Per section: how many
                  frames long, how many rings and bombs it holds, and its SURPLUS -- rings on
                  offer over rings that section newly asks for. That is how forgiving it is.
    lead_in       frames of empty track before the first object
    density       objects per 100 frames, by what is under the player: straight, corner, slope
    placements    every module the game put down, as (module, mirrored, which stretch of a
                  run, the angle its first object was put at, what it was put on). The
                  generator draws from THESE, so it inherits what the game uses, how often,
                  where round the pipe, and on what kind of track, all at once.

Sources: the object lists (s2_objects.py), the layouts (gen_s2_track.py), and
SpecialStage_RingReq_Team / _Alone in s2.asm, copied below.
"""

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import check_ring_coverage as cc
import ring_modules as rm
import s2_objects as so
from gen_s2_track import LAYOUTS, SEGMENTS

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ring_rulebook.json")

# s2.asm. Four bytes a stage; the fourth is unused by the game.
QUOTA_TEAM = {1: (40, 80, 140), 2: (50, 100, 140), 3: (60, 110, 160), 4: (40, 100, 150),
              5: (55, 110, 200), 6: (80, 140, 220), 7: (100, 190, 210)}
QUOTA_ALONE = {1: (30, 70, 130), 2: (50, 100, 140), 3: (50, 110, 160), 4: (40, 110, 150),
               5: (50, 90, 160), 6: (80, 140, 210), 7: (100, 150, 190)}

ON = {"S": "straight", "E": "corner", "T": "corner", "X": "corner", "R": "slope", "D": "slope"}


def signed(a):
    return ((a + 128) % 256) - 128


def main():
    book = {"_about": "Measured from Sonic 2 by make_ring_rulebook.py. Do not edit by hand."}
    for stage in range(1, 8):
        lengths = [len(SEGMENTS[int(b, 16) & 0x7F]) for b in LAYOUTS[stage].split()]
        starts = [sum(lengths[:i]) for i in range(len(lengths) + 1)]
        kinds = "".join(SEGMENTS[int(b, 16) & 0x7F] for b in LAYOUTS[stage].split())
        lists = so.stages()[stage - 1]
        checks = [i for i, (_, end) in enumerate(lists) if end in (0xFE, 0xFD)]
        bounds = [0] + [starts[min(i + 1, len(starts) - 1)] for i in checks]

        objects = cc.flatten(stage)
        sections = []
        for k in range(3):
            inside = [o for o in objects if bounds[k] <= o[0] < bounds[k + 1] or (k == 2 and o[0] >= bounds[3])]
            rings = sum(o[2] == rm.RING for o in inside)
            asked = QUOTA_ALONE[stage][k] - (QUOTA_ALONE[stage][k - 1] if k else 0)
            sections.append(dict(frames=bounds[k + 1] - bounds[k], rings=rings,
                                 bombs=len(inside) - rings, asks=asked,
                                 surplus=round(rings / asked, 2)))

        frames_on, objects_on = {}, {}
        for c in kinds[:bounds[3]]:
            frames_on[ON[c]] = frames_on.get(ON[c], 0) + 1
        for f, _, _ in objects:
            on = ON[kinds[min(f, len(kinds) - 1)]]
            objects_on[on] = objects_on.get(on, 0) + 1
        density = {on: round(100.0 * objects_on.get(on, 0) / n, 1) for on, n in frames_on.items()}

        placed, left = cc.cover(objects)
        placements = []
        for label, f, a, n, meta in placed:
            if meta is None:
                meta = dict(name="Bomb" if label.endswith(rm.BOMB) else "Ring", mirrored=False, run=None)
            span = kinds[min(f, len(kinds) - 1):min(f + 8, len(kinds))]
            on = "slope" if set(span) & set("RD") else "corner" if set(span) & set("TEX") else "straight"
            placements.append(dict(module=meta["name"], mirrored=meta["mirrored"], run=meta["run"],
                                   first_at=signed(a - 0x40), on=on, objects=n))

        book[str(stage)] = dict(quota_alone=QUOTA_ALONE[stage], quota_team=QUOTA_TEAM[stage],
                                frames=bounds[3], lead_in=min(o[0] for o in objects),
                                sections=sections, density=density, placements=placements)
        print("stage %d: %4d frames, lead-in %3d | " % (stage, bounds[3], book[str(stage)]["lead_in"])
              + " | ".join("%3d fr %3d rings/%3d asked x%.2f %3d bombs"
                           % (s["frames"], s["rings"], s["asks"], s["surplus"], s["bombs"]) for s in sections)
              + " | density " + " ".join("%s %.0f" % kv for kv in sorted(density.items())))

    json.dump(book, open(OUT, "w", encoding="utf-8"), indent=1)
    print("saved", OUT)


main()
