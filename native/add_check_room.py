"""Room after the gauntlet's checks: straights spliced into the seven authored stages.

    blender -b external/halfpipe/TrackPiecesPack.blend --python native/add_check_room.py -- [1-7 ...] [dry]

After a check the thumbs-up keeps the controls for THUMBS_TIME (2.8 s, 42 frames past the arch),
and the ring check zone leaves only 44 frames past it. On five of the stages' checks the next
section opened with bombs 3 frames on: control came back 0.2 s before them. The marathon has had
room there since it was built live (MarathonGen.lua CHECK_LEAD: 24 frames).

The seven stages cannot simply be made again with more room. gen_stage.py deals from one random
stream per stage, and it has changed since they were made (it counts takeable rings now), so the
same seed deals a different stage today: stage 4's second section kept 23 of its 169 objects.
So this edits the stages as they are, in their .json:

  - where a check's next section has a bomb less than ROOM frames after control comes back,
    enough whole straights are put into the piece list where the check zone ends
  - every frame after them moves on by the straights' length: the later checks, arches, rings
    and bombs. The exporter chains the pieces, so the track beyond slides on along the
    straight as one piece; no ring or bomb moves against another
  - the shifted track is tested for running into the track before it, as the generator does
    (gen_random_level.collides), and nothing is written if it would

Run it again and it adds nothing: every gap is already ROOM. The stage's .blend is not changed
and does not show the straights; the .json is what the exporters read.
"""
import json
import math
import os
import sys

import bpy
from mathutils import Matrix

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import gen_random_level as grl
import ring_modules as rm
import ring_solver as rsol
from gen_rings_on_pieces import ChainPath
from gen_stage import GAUNTLET_SEED, piece_paths

STAGES = os.path.abspath(os.path.join(HERE, "..", "external", "stages"))
ROOM = 24                                       # frames from control coming back to the first bomb:
                                                # the marathon's CHECK_LEAD, 1.6 s
CONTROL = rsol.THUMBS_TIME * rsol.SPEED         # frames past the arch when control comes back

args = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
DRY = "dry" in args
WHICH = [int(a) for a in args if a.isdigit()] or list(range(1, 8))


def piece_starts(names, paths):
    return [start / rm.STEP for start, _, _ in ChainPath([paths[n] for n in names]).parts]


def as_frame(value):
    """Keep whole frames whole (the objects' frames are integers in the .json)."""
    return int(round(value)) if abs(value - round(value)) < 1e-6 else value


def shift_section(sec, by, pieces_by, first_too):
    if first_too:
        sec["first_frame"] += by
    sec["check_frame"] += by
    sec["last_frame"] += by
    rc = sec["ring_check"]
    for key in ("first_frame", "check_frame", "last_frame"):
        rc[key] += by
    rc["rainbow_arch"]["frame"] += by
    rc["rainbow_arch"]["piece"] += pieces_by
    sec["objects"] = [[as_frame(o[0] + by)] + o[1:] for o in sec["objects"]]


def collision_after(names, pieces, first):
    """The index of the first piece from `first` on that runs into the track before it, or None."""
    frame, laid = Matrix.Identity(4), []
    for i, name in enumerate(names):
        world = [frame @ p for p in pieces[name]["pts"]]
        if i >= first and grl.collides(world, laid):
            return i
        laid.append(world)
        frame = grl.exit_frame(frame, pieces[name])
    return None


def main():
    paths = piece_paths()
    pieces = grl.load_pieces()
    straight = paths["Straight"].length / rm.STEP       # 8 frames
    for stage in WHICH:
        name = "Stage%d_seed%d" % (stage, GAUNTLET_SEED[stage])
        path = os.path.join(STAGES, name + ".json")
        data = json.load(open(path, encoding="utf-8"))
        names, secs = data["pieces"], data["sections"]
        first_insert, notes = None, []

        for k in range(len(secs) - 1):
            sec, nxt = secs[k], secs[k + 1]
            control = sec["check_frame"] + CONTROL
            bombs = [o[0] for o in nxt["objects"] if o[2] == "bomb"]
            if not bombs:
                continue
            gap = min(bombs) - control
            if gap >= ROOM:
                notes.append("check %d: first bomb %.1f s after control, left alone" % (k + 1, gap / rsol.SPEED))
                continue
            n = int(math.ceil((ROOM - gap) / straight))
            starts = piece_starts(names, paths)
            at = next((i for i, f in enumerate(starts) if abs(f - sec["last_frame"]) < 0.01), None)
            if at is None:
                raise SystemExit("%s: no piece starts where check %d's zone ends (frame %.3f)"
                                 % (name, k + 1, sec["last_frame"]))
            names[at:at] = ["Straight"] * n
            by = n * straight
            for j in range(k + 1, len(secs)):
                shift_section(secs[j], by, n, first_too=(j > k + 1))
            nxt["pieces"] += n
            first_insert = at if first_insert is None else first_insert
            notes.append("check %d: first bomb %.2f s after control -> %d straight%s -> %.2f s"
                         % (k + 1, gap / rsol.SPEED, n, "" if n == 1 else "s", (gap + by) / rsol.SPEED))

        print("\n%s" % name)
        for line in notes:
            print("  " + line)
        if first_insert is None:
            print("  nothing to add")
            continue
        hit = collision_after(names, pieces, first_insert)
        if hit is not None:
            print("  NOT WRITTEN: piece %d (%s) would run into the track before it" % (hit, names[hit]))
            continue
        print("  shifted track clear of itself; %d pieces now" % len(names))
        if not DRY:
            json.dump(data, open(path, "w", encoding="utf-8"))
            print("  written", path)


main()
