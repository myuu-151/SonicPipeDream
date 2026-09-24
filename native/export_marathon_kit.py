"""Everything the game needs to build a marathon zone itself: proj/Scripts/MarathonKit.lua.

    blender -b external/halfpipe/TrackPiecesPack.blend --python native/export_marathon_kit.py

The marathon is generated IN THE GAME (MarathonGen.lua), a new zone from a new seed while the
last one is played, so no run is ever seen twice. That generator is gen_stage.py's marathon,
ported. What it cannot do in the game is what needs Blender or takes minutes, so this does that
once and writes the result down:

  * the five track pieces' centre lines (gen_stage.piece_paths), in Blender's space, so pieces
    can be laid end to end and the track measured along them;
  * every card a section can be dealt -- the original stages' placements and the library's,
    as gen_stage.build_cards builds each flavour's deck -- with its module's objects, the angle
    it is put at, and HOW MANY RINGS A LINE CAN TAKE FROM IT (ring_solver.py), plain and
    mirrored. The generator adds those up to size a section, as gen_stage.py does; the full
    solver, which takes seconds a section, is left to native/check_marathon_gen.py, which checks
    what the game made against the rule after the fact;
  * the design curves and the track's rules, gen_stage.py's own numbers.
"""

import json
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.argv = [a for a in sys.argv if a != "--"]               # gen_stage reads argv: give it nothing
import gen_random_level as grl                                # noqa: E402
import gen_stage as gs                                        # noqa: E402
import ring_modules as rm                                     # noqa: E402
import ring_solver as rsol                                    # noqa: E402

OUT = os.path.abspath(os.path.join(HERE, "..", "proj", "Scripts", "MarathonKit.lua"))


def lua(value, indent=0):
    pad = " " * indent
    if isinstance(value, dict):
        items = []
        for k, v in value.items():
            key = k if isinstance(k, str) and k.isidentifier() else "[%s]" % (k if isinstance(k, int) else '"%s"' % k)
            items.append("%s  %s = %s,\n" % (pad, key, lua(v, indent + 2)))
        return "{\n" + "".join(items) + pad + "}"
    if isinstance(value, (list, tuple)):
        if value and all(isinstance(x, (int, float)) and not isinstance(x, bool) for x in value):
            return "{" + ",".join(lua(x) for x in value) + "}"
        return "{\n" + "".join("%s  %s,\n" % (pad, lua(v, indent + 2)) for v in value) + pad + "}"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, float):
        return ("%.5f" % value).rstrip("0").rstrip(".") if value == value else "0"
    if isinstance(value, int):
        return str(value)
    if value is None:
        return "nil"
    return '"%s"' % str(value).replace('"', '\\"')


def card_module(p):
    """gen_stage.module_of without its coin: the objects and the angle, before the 50/50 mirror
    the game throws for itself."""
    if p["module"] == "Ring":
        m = [(0, 0, rm.RING)]
    elif p["run"]:
        lo, hi = p["run"]
        m = [(f - lo, a, k) for f, a, k in rm.RUNS[p["module"]] if lo <= f <= hi]
    else:
        m = list(rm.MODULES[p["module"]])
    if p["mirrored"]:
        m = rm.mirrored(m)
    first = min(m, key=lambda o: (o[0], o[1] % 256))
    at = gs.signed(p["first_at"] - first[1])
    return m, at


TAKE = {}


def takeable(m, at):
    key = (tuple(m), at)
    if key not in TAKE:
        objs = [(f, gs.signed(a + at), 1 if k == rm.BOMB else 0) for f, a, k in m]
        TAKE[key] = rsol.best_line(objs, -1.0, rm.length(m) + 1.0, start="any") or 0
    return TAKE[key]


def main():
    rulebook = json.load(open(os.path.join(HERE, "ring_rulebook.json"), encoding="utf-8"))
    modules, module_index = [], {}

    def module_id(m):
        key = tuple(m)
        if key not in module_index:
            flat = []
            for f, a, k in m:
                flat += [f, a, 1 if k == rm.BOMB else 0]
            module_index[key] = len(modules) + 1
            modules.append(dict(len=rm.length(m), rings=sum(k == rm.RING for _, _, k in m),
                                bombs=sum(k == rm.BOMB for _, _, k in m), objs=flat))
        return module_index[key]

    flavours = {}
    for flavour in range(1, 8):
        pool = gs.build_cards(rulebook, flavour)
        book = rulebook[str(flavour)]
        decks = {}
        for on in ("straight", "corner", "slope"):
            cards = []
            for p in pool.get(on, []):
                m, at = card_module(p)
                cards.append(dict(name=p["module"], mod=module_id(m), at=at, t=takeable(m, at),
                                  tm=takeable(rm.mirrored(m), -at), bomb="Bomb" in p["module"]))
            decks[on] = cards
        # top_up's ring-only shapes: gen_stage.top_up's own choice from the same pool
        ringonly = []
        for on in sorted(pool):
            for p in pool[on]:
                if p["module"] == "Ring" or p["objects"] < 4:
                    continue
                m, at = card_module(p)
                if all(k == rm.RING for _, _, k in m):
                    ringonly.append(dict(name=p["module"], mod=module_id(m), at=at, t=takeable(m, at),
                                         tm=takeable(rm.mirrored(m), -at)))
        rings = sum(s["rings"] for s in book["sections"])
        bombs = sum(s["bombs"] for s in book["sections"])
        # each distinct card once, with how many copies the deck holds of it (n)
        def grouped(cards):
            out, where = [], {}
            for c in cards:
                key = (c["name"], c["mod"], c["at"])
                if key in where:
                    out[where[key]]["n"] += 1
                else:
                    where[key] = len(out)
                    out.append(dict(c, n=1))
            return out
        decks = {on: grouped(cards) for on, cards in decks.items()}
        ringonly = grouped(ringonly)
        flavours[flavour] = dict(decks=decks, ringonly=ringonly, density=book["density"],
                                 rings=rings, bombs=bombs)
        print("flavour %d: %s cards, %d ring-only; %d modules, %d solved so far"
              % (flavour, "/".join(str(len(decks[o])) for o in decks), len(ringonly), len(modules), len(TAKE)),
              flush=True)

    small = list(rm.MODULES["ClusterSmall"])
    cluster_small = dict(mod=module_id(small), t={str(a): takeable(small, a) for a in (-48, 0, 48)})

    paths = gs.piece_paths()
    pieces = {}
    for name, path in paths.items():
        pieces[name] = dict(pts=[[p.x, p.y, p.z] for p in path.pts], length=path.length)

    import stage_palettes
    stage7 = json.load(open(os.path.join(HERE, "..", "external", "stages", "Stage7_seed%d.json" % gs.GAUNTLET_SEED[7]),
                            encoding="utf-8"))
    a = stage7["sections"][0]["ring_check"]["rainbow_arch"]
    arch = dict(rings=a["rings"], reach=rm.PIPE_RADIUS + 1.6, from_deg=12.0, ring_scale=a["ring_scale"],
                toward_player=0.72, steps_per_second=a["steps_per_second"])     # as export_to_octave.py's
    palette_skies = [stage_palettes.palette(n)["sky"] for n in sorted(stage_palettes.S2_LINE)]

    kit = dict(
        step=rm.STEP, pipe_radius=rm.PIPE_RADIUS, hover=rm.HOVER,
        angle_00_side=-1 if rm.ANGLE_00_SIDE == "right" else 1,
        share=rsol.TAKEABLE_SHARE,
        arch=arch, palette_skies=palette_skies,
        design=dict(quota={str(k): list(v) for k, v in gs.QUOTA.items()},
                    forgiveness={str(k): v for k, v in gs.FORGIVENESS.items()},
                    ring_rate={str(k): v for k, v in gs.RING_RATE.items()},
                    start=gs.MARATHON_START, ramp=gs.MARATHON_RAMP, ask_step=gs.MARATHON_ASK_STEP,
                    forgiveness_floor=gs.MARATHON_FORGIVENESS_FLOOR,
                    ring_rate_ceiling=gs.MARATHON_RING_RATE_CEILING,
                    flavours=list(gs.MARATHON_FLAVOURS), room=list(gs.MARATHON_ROOM),
                    sections_per_zone=gs.SECTIONS_PER_ZONE),
        rules={str(k): v for k, v in grl.RULES.items()},
        track=dict(check_run_up=gs.CHECK_RUN_UP, check_plays=gs.CHECK_PLAYS, emerald_run_up=gs.EMERALD_RUN_UP,
                   hold_plays=gs.HOLD_PLAYS, arch_frame=gs.ARCH_FRAME, intro_straights=gs.INTRO_STRAIGHTS,
                   zone_lead_in=gs.ZONE_LEAD_IN, lead_in=gs.LEAD_IN, before_corner=gs.BEFORE_CORNER,
                   grid=gs.GRID, clear_flat=grl.CLEAR_FLAT, clear_height=grl.CLEAR_HEIGHT, recent=grl.RECENT,
                   own_weight=gs.OWN_WEIGHT),
        on=gs.ON, pieces=pieces, modules=modules,
        flavours={str(k): v for k, v in flavours.items()},
        cluster_small=cluster_small)
    text = lua(kit)
    # string keys that are numbers ("1") read back as numbers in the game: make them so here
    import re
    text = re.sub(r'\["(-?\d+)"\]', r"[\1]", text)
    open(OUT, "w", encoding="ascii", newline="\n").write(
        "-- Written by native/export_marathon_kit.py. Do not edit by hand: run that.\n"
        "-- What MarathonGen.lua builds a marathon zone from, in the game. Pieces are in Blender's\n"
        "-- space (Z up); modules' objs are flat {frame, angle, bomb (1) or ring (0), ...}.\n"
        "MarathonKit = %s\n" % text)
    print("wrote %s (%.0f KB): %d modules, %d takeable counts" % (OUT, os.path.getsize(OUT) / 1024.0,
                                                                  len(modules), len(TAKE)))


main()
