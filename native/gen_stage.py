"""Generate a special stage: track, rings, bombs, its checks, and its splines.

    blender -b external/halfpipe/TrackPiecesPack.blend \\
        --python native/gen_stage.py -- <1-7 | marathon [zones]> [seed N] [render]

    1-7          THE GAUNTLET: the seven emerald stages, which is what the menu lists.
                 Authoritative: each has its own fixed seed (GAUNTLET_SEED); leave it off.
    marathon Z   THE MARATHON, which the menu unlocks when the seventh emerald is won (the
                 unlock is the game's business, not this script's). One continuous run with
                 no end, harder section by section, a new random seed every run. A .blend
                 cannot be endless, so this builds the first Z zones (default 3) to look
                 at; the ENGINE keeps going with the same rules, which are in the .json.

    -> external/stages/<name>.blend   everything, to look at and to edit
       external/stages/<name>.json    the same as data, for the engine
       (python native/make_stage_maps.py external/stages/<name>.json draws it flat)

EVERYTHING IS MADE OF SECTIONS. A section is a stretch of track that ends at a CHECK, which
asks for a number of rings, and the check has its own empty run of straights to play out on
(see THE RING CHECK below). A gauntlet stage is three sections at one difficulty, and its
third check leads to the emerald. The marathon is sections without end, each a little
harder than the last; they come in threes too -- a ZONE -- and after each third check the
PALETTE SHIFTS: a new sky, new colours on the pipe. The pipe colours are the original's
seven (stage_palettes.py): a gauntlet stage wears its own, a marathon zone draws one at
random, never the same twice running. The SKY is only named here -- which of the project's
skies goes with the palette -- since the skies are Octave's textures, not Blender's.

THE GUARANTEE. A section always holds enough rings to pass its own check, from nothing,
and by a margin: rings on offer >= rings it newly asks for x its forgiveness. The generator
does not hope for this; it pads the section with more track until it is true, and refuses
to write a stage where it is not. It holds the other way too: spare rings over the promise
are taken back out, so a tight section stays tight. Low difficulties are generous and
roomy; high ones ask for far more and leave next to nothing spare, so they run LONGER.

Two rulebooks, kept apart on purpose:
    measured   native/ring_rulebook.json, from the original stages: which modules a stage
               uses, how often, where round the pipe, on what kind of track, how many
               bombs to a ring. Nothing in it is a guess.
    designed   QUOTA, FORGIVENESS and RING_RATE, below. The original's own wander (its
               stage 5 is kinder than its stage 2, and its quotas hardly rise); the
               project's owner wants stages that tighten and lengthen steadily.

The track is dealt and laid by gen_random_level.py (deck, not dice; never runs into
itself); the objects are laid by gen_rings_on_pieces.py's ChainPath and lay(), along the
LEVEL, so a module may start on one piece and finish on the next.
"""

import json
import math
import os
import random
import sys

import bmesh
import bpy
from mathutils import Matrix, Vector

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import gen_random_level as grl
import ring_modules as rm
import stage_palettes
from gen_rings_on_pieces import BOMB_BLEND, RING_BLEND, ChainPath, PiecePath, lay

args = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
MARATHON = "marathon" in args
SEED = int(args[args.index("seed") + 1]) if "seed" in args else None
nums = [int(a) for i, a in enumerate(args) if a.isdigit() and (i == 0 or args[i - 1] != "seed")]
STAGE = None if MARATHON else (nums[0] if nums else 1)
ZONES = (nums[0] if nums else 3) if MARATHON else 1
RENDER = "render" in args
OUT_DIR = os.path.abspath(os.path.join(HERE, "..", "external", "stages"))

# --- designed ---------------------------------------------------------------------------
# Three curves, the project owner's, and they are meant to be read together:
#
#   QUOTA        what a stage's three checks ask for, cumulative; the third leads to the
#                emerald. STEEP: stage 7 asks for more than four times what stage 1 does.
#                (The original's barely climb, 130 to 190, and are kept in the rulebook as
#                "quota_alone" / "quota_team"; set QUOTAS = "original" to play those.)
#   FORGIVENESS  rings on offer in a section, as a multiple of what its check newly asks.
#                2.2: miss more than half and still pass. 1.05: miss one in twenty and fail.
#   RING_RATE    rings per frame of track. The original's wanders (stage 3 is 0.27, stage 5
#                0.58); this rises steadily, so later stages come at you faster.
#
# LENGTH is not set anywhere: it falls out as quota x forgiveness / ring rate, plus whatever
# room the bombs take. The quota is steep enough that length still climbs while forgiveness
# falls -- a high stage is long because it asks a lot, a low one is roomy because it
# forgives a lot. The length is printed; check it after changing a curve.
QUOTA = {1: (30, 70, 130), 2: (40, 90, 170), 3: (50, 115, 210), 4: (70, 160, 290),
         5: (90, 210, 380), 6: (110, 260, 480), 7: (140, 320, 600)}
FORGIVENESS = {1: 2.2, 2: 2.0, 3: 1.8, 4: 1.6, 5: 1.4, 6: 1.2, 7: 1.05}
RING_RATE = {1: 0.34, 2: 0.38, 3: 0.41, 4: 0.45, 5: 0.49, 6: 0.52, 7: 0.56}
QUOTAS = "designed"         # or "original": the game's own, playing alone

# THE GAUNTLET is authoritative -- everyone plays the same seven -- so each stage has one
# seed, written down here. Change one and that stage is a different stage for good.
GAUNTLET_SEED = {1: 1, 2: 1, 3: 1, 4: 1, 5: 1, 6: 1, 7: 1}

# THE MARATHON. Its difficulty is a number that creeps up with every section, read off the
# same three curves: between two stages it is in between them, and past 7 the curves carry
# on -- asks keep climbing without limit, the ring rate rises to a ceiling, forgiveness
# falls to a floor that is still over 1.0, so the guarantee holds at section 500 as at 1.
MARATHON_START = 2.0                    # the difficulty of its first section
MARATHON_RAMP = 0.5                     # added per section: a zone is a stage and a half harder
MARATHON_ASK_STEP = 27                  # past 7, rings a check newly asks for, per difficulty
MARATHON_FORGIVENESS_FLOOR = 1.02
MARATHON_RING_RATE_CEILING = 0.60
MARATHON_FLAVOURS = (6, 7, 3, 5)        # past 7, whose modules a zone draws on, in rotation:
                                        # bomb fields, ring storms, corkscrews, helixes
SECTIONS_PER_ZONE = 3                   # the palette shifts after every third check
MARATHON_ROOM = (1.0, 1.45)             # ALWAYS UNIQUE has to mean more than a new shuffle. The
                                        # deck deals a fixed mix and a section is sized to its
                                        # rings, so every run's first zone came out the same
                                        # length with the same pieces in a new order. Each
                                        # marathon section is now given this much room, drawn
                                        # afresh: tight and busy, or long and open. The ring
                                        # promise is kept either way -- it is trimmed to.


def between(table, d):
    lo = max(1, min(6, int(math.floor(d))))
    t = max(0.0, min(1.0, d - lo))
    return table[lo] * (1.0 - t) + table[lo + 1] * t


def section_design(d, zone=0):
    """What a section of difficulty d is: what its check newly asks, how forgiving it is,
    how fast its rings come, whose modules it draws on, and the track's own rules."""
    over = max(0.0, d - 7.0)
    asks = between({k: v[2] / 3.0 for k, v in QUOTA.items()}, d) + MARATHON_ASK_STEP * over
    return dict(
        difficulty=round(d, 2),
        asks=int(round(asks / 5.0)) * 5,
        forgiveness=round(max(MARATHON_FORGIVENESS_FLOOR, between(FORGIVENESS, d) - 0.015 * over), 3),
        ring_rate=round(min(MARATHON_RING_RATE_CEILING, between(RING_RATE, d) + 0.01 * over), 3),
        flavour=(max(1, min(7, int(round(d)))) if d <= 7.0
                 else MARATHON_FLAVOURS[zone % len(MARATHON_FLAVOURS)]),
        rules=grl.RULES[max(1, min(7, int(round(d))))])


def designs(book_of):
    """One design per section of what is being built, with what its check leads to."""
    if not MARATHON:
        quota = QUOTA[STAGE] if QUOTAS == "designed" else tuple(book_of(STAGE)["quota_alone"])
        out = []
        for k in range(3):
            d = section_design(float(STAGE))
            d["asks"] = quota[k] - (quota[k - 1] if k else 0)
            d["leads_to"] = "EMERALD" if k == 2 else "section %d" % (k + 2)
            out.append(d)
        return out
    out = []
    for s in range(ZONES * SECTIONS_PER_ZONE):
        d = section_design(MARATHON_START + MARATHON_RAMP * s, zone=s // SECTIONS_PER_ZONE)
        d["leads_to"] = "PALETTE SHIFT" if (s + 1) % SECTIONS_PER_ZONE == 0 else "on"
        out.append(d)
    return out


if SEED is None:
    # A MARATHON RUN IS ALWAYS UNIQUE -- the owner's rule. Every run takes a fresh seed from
    # the system's own randomness, out of 2**62 of them, so no run is ever played twice and
    # no zone is ever seen twice. (The seed only ends up in the file's name so that a preview
    # can be found again; it is not a feature of the game. In the engine: seed from the
    # clock or the hardware, the same way, and never show it.)
    SEED = random.SystemRandom().randrange(1, 2 ** 62) if MARATHON else GAUNTLET_SEED[STAGE]
NAME = "Marathon_seed%d" % SEED if MARATHON else "Stage%d_seed%d" % (STAGE, SEED)

# THE RING CHECK is its own stretch of track, as it is in the original: every one of the
# original's checks sits on a run of three or four straights, with its rings and bombs
# stopping 15-20 frames short of it and nothing at all for about 48 frames after (measured:
# 36 to 63). That empty run is not padding. It is where the check PLAYS: the logo drops in
# at the top of the screen, the count is taken, and on a pass the camera swings round to
# Sonic and he gives the thumbs up (RunThumbsUp) before the next section starts. So each
# section ends in a RING CHECK ZONE of straights with nothing on them, and the check itself
# comes a little way into it. All the script does is keep the room and mark it:
#     Check_NN / Emerald   where the count is taken
#     CheckLogo_NN         above the pipe there, where the logo belongs
#     CheckPass_NN         the end of the zone: the pass plays from Check to here
# The logo, the camera and the animation are the engine's.
CHECK_RUN_UP = 2            # straights of bare track before the check's piece: he runs
                            # straight for a bit first, as in the original (20 frames to the arch)
CHECK_PLAYS = 6             # the check's piece and those after it: 44 frames past the arch,
                            # for the logo, the camera and the thumbs up
# THE RAINBOW ARCH IS THE CHECK. As in the original, Sonic runs straight for a bit with
# nothing on the track -- the run-up -- and then passes under one arch that is different from
# every other: each sphere on it wears a ring, and the rings cycle through the colours of the
# rainbow. THE COUNT IS TAKEN THE INSTANT HE PASSES IT. It is seen nowhere else, so there is
# no mistaking it. The check's marker (Check_NN, "the dummy") stands exactly under it: they
# are the same place, and `check_frame` in the .json is the frame of the arch.
#   A ring is the size of its sphere and sits on the sphere's front face, toward the player,
#   like a rim -- the owner's own placement, read back from a ring he moved by hand in
#   Stage1_seed1.blend (scale 1.029, 0.72 back along the track).
#   Here: nine rings, each its own colour, so the arch reads as a rainbow standing still.
#   The CYCLING is the engine's: each ring steps through RAINBOW, one place on from its
#   neighbour, RAINBOW_STEPS_PER_SECOND times a second. Both are in the .json.
# The arch itself is gen_halfpipe.py's: nine spheres, 1.6 outside the pipe, from 12 degrees
# above one rim over the top to 12 above the other, half way along the section.
ARCH_COUNT, ARCH_FROM_DEG, ARCH_OUT, SPHERE_R = 9, 12.0, 1.6, 1.25
RAINBOW_RING_SCALE = 1.03   # the ring's outer edge meets the sphere's (1.28 against 1.25)
RAINBOW_RING_TOWARD_PLAYER = 0.72   # back along the track from the sphere's centre
ARCH_FRAME = 4.0            # the arch is half way along its straight, and a straight is 8 frames
RAINBOW = ((1.00, 0.10, 0.10), (1.00, 0.50, 0.00), (1.00, 0.90, 0.00), (0.30, 0.90, 0.10),
           (0.00, 0.80, 0.70), (0.10, 0.50, 1.00), (0.35, 0.25, 1.00), (0.75, 0.20, 0.95),
           (1.00, 0.25, 0.65))
RAINBOW_STEPS_PER_SECOND = 8.0

CHECK_LENGTH = CHECK_RUN_UP + CHECK_PLAYS        # 8 straights, 64 frames, about 320 units

# THE INTRO and THE ENDING are each as long as a ring check, by the owner's rule, and are
# worked out from it so the three can never drift apart. Lengthen the check and they follow.
#   intro    a stage opens on this many straights with nothing on them, laid before anything
#            the deck deals, so however the track is dealt it never starts on a bend. (The
#            original opens on three straight segments and about 80 empty frames.)
#   ending   the pipe does not stop at the emerald: it runs straight on past it for a check's
#            length, so the stage ends on track and not on a sawn-off pipe. (The original's
#            layouts carry four more segments than their object lists.)
INTRO_STRAIGHTS = CHECK_LENGTH
EMERALD_RUN_UP = 3          # the original gives the emerald a longer approach (24-39 frames)
EMERALD_PLAYS = CHECK_LENGTH

# THE HOLD. After a marathon zone's third check the camera zooms in on Sonic, thumbs up,
# running on plain straight pipe -- and he KEEPS running on it, the same straight laid under
# him again and again, for as long as the next zone takes to build. Then the zoom lets go
# and the run resumes. So building a zone never has a deadline, and the wait reads as a
# victory lap, not a loading screen. It works because of three things this script keeps true:
#   * a zone ENDS on the ring check's long empty straights and BEGINS on straights, so the
#     held straight is the same track as both its neighbours and there is no join to see;
#   * a zone ends HEADING THE WAY IT BEGAN (even_corners), so the track just carries on;
#   * a zone is built FROM NOTHING BUT (the run's seed, the zone's number) -- build_part()
#     takes no random stream, no decks and no position from the zone before. The engine can
#     throw the old zone away, move everything back to the origin (a run is tens of
#     thousands of units long; this is where to shed them) and build the next from its key.
# The zoom also hides the palette shift. The preview .blend sets the zones down end to end
# only so they can be looked at together; in the game there is never more than one.
ZONE_LEAD_IN = 16           # frames before a later zone's first shape: the run has resumed

# Frames (ring_modules.STEP apart) kept empty, so nothing is sprung on the player:
LEAD_IN = INTRO_STRAIGHTS * 8           # at the very start: the whole intro (a straight is 8 frames)
BEFORE_CORNER = 4           # no shape STARTS just before a corner: the original leaves
                            # the run-up to a turn nearly empty, so the turn can be seen
RINGS_TO_GO = 64            # the "rings to go" call, this many frames before its check
                            # (the original's comes two to five segments ahead)
GRID = 4                    # shapes start on a beat, as the original's do (0 or 8)

ON = {"Straight": "straight", "CornerLeft": "corner", "CornerRight": "corner",
      "Drop": "slope", "Rise": "slope"}
LETTER = {"Straight": "S", "CornerLeft": "L", "CornerRight": "R", "Drop": "D", "Rise": "U"}


def signed(a):
    return ((a + 128) % 256) - 128


# ---------------------------------------------------------------------------- decks --
# VARIETY. The first version dealt a stage only what the original stage of the same number
# put down, and that is very little: stage 1 has six kinds of shape, stage 5 has eight and
# twenty-five of its forty-one are the same big triangle, and 29 of the 93 modules -- the
# single spiral and the snake line among them -- could never come up at all, because the
# original never used them on their own. So a stage's deck is now built like this:
#
#   TIER     every module has one: the first original stage it appears in. That is the
#            original's own order of teaching shapes. A stage may use every tier up to its
#            own, and a few cards of the NEXT tier, as a taste of what is coming.
#   WEIGHT   the stage's own placements count most, so it keeps its character; earlier
#            stages' less; the next tier's least.
#   DAMPING  a shape the original used n times gets about sqrt(n) cards, not n. Stage 5 is
#            still the big-triangle stage; it is no longer only that.
#   LIBRARY  modules the original never placed on their own get a tier by hand, below, and
#            are put where the original puts things: the floor, or up either wall.
OWN_WEIGHT, EARLIER_WEIGHT, NEXT_WEIGHT, LIBRARY_WEIGHT = 3, 1, 1, 2

LIBRARY_TIER = {
    "TriangleWeave": 1, "TwinBombsAndCluster": 1, "Row3": 1, "Slant": 1, "LineDotted": 1,
    "TriangleSnake": 2, "TwinOverhead": 2, "Row4Wide": 2, "Snake": 2, "Across": 2,
    "Spiral": 3, "SpiralSlow": 3, "LineInCorkscrew": 3, "BombSlant": 3,
    "Row5": 4, "Row5Wide": 4, "RowWeaveByBombs": 4,
    "HelixUp": 5, "HelixDown": 5, "HelixBounce": 5, "RowAcross": 5, "SpiralLong": 5, "SnakeLong": 5,
    "Slalom": 6, "SnakeWide": 6,
    "BombDotsLong": 7,
}
CENTRED = ("Spiral", "SpiralSlow", "SpiralLong", "HelixUp", "HelixDown", "HelixBounce", "RowAcross",
           "Snake", "SnakeLong", "SnakeWide", "Across", "Slalom", "LineInCorkscrew", "TwinOverhead",
           "TwinBombsAndCluster", "BombDotsLong", "RowWeaveByBombs")
WALL_ANGLES = (0, 0, -32, 32, -40, 40, -48, 48)      # where the original puts a small shape


def build_cards(rulebook, flavour):
    """{kind of track: [card, ...]} for a section that takes its flavour from this original
    stage. A card is a rulebook placement, or one made up for a library module."""
    first_seen = {}
    for st in range(1, 8):
        for pl in rulebook[str(st)]["placements"]:
            first_seen.setdefault(pl["module"], st)

    cards = {"straight": [], "corner": [], "slope": []}
    for st in range(1, min(7, flavour + 1) + 1):
        weight = OWN_WEIGHT if st == flavour else NEXT_WEIGHT if st > flavour else EARLIER_WEIGHT
        groups = {}
        for pl in rulebook[str(st)]["placements"]:
            if st > flavour and first_seen[pl["module"]] != st:
                continue                              # of the next stage, only what is NEW in it
            groups.setdefault((pl["module"], pl["on"]), []).append(pl)
        for (module, on), same in sorted(groups.items()):
            keep = int(math.ceil(math.sqrt(len(same)))) * weight
            for i in range(keep):
                cards[on].append(same[i % len(same)])

    for module, tier in sorted(LIBRARY_TIER.items()):
        if tier > flavour + 1:
            continue
        m = rm.MODULES[module]
        first = min(m, key=lambda o: (o[0], o[1] % 256))
        for on in cards:
            for i in range(LIBRARY_WEIGHT if tier <= flavour else 1):
                at = 0 if module in CENTRED else WALL_ANGLES[(i * 3 + tier + len(module)) % len(WALL_ANGLES)]
                cards[on].append(dict(module=module, mirrored=False, run=None, on=on,
                                      first_at=signed(first[1] + at), objects=len(m)))
    return cards


# ------------------------------------------------------------------------- modules --
def module_of(p, rng):
    """A rulebook placement as (objects, angle to put it at). Half the time it is flipped
    left for right, shape and position both: the original is even-handed, and it doubles
    what a small stage's list can give."""
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
    at = signed(p["first_at"] - first[1])
    if rng.random() < 0.5:
        m, at = rm.mirrored(m), -at
    return m, at


# --------------------------------------------------------------------------- track --
def piece_paths():
    """A fine centre line for each of the five pieces, made the way load_pieces() makes
    the pieces themselves: the left corner mirrored, the rise the drop turned upside down."""
    fine = {n: PiecePath(bpy.data.objects[n]).pts for n in ("TP_Straight", "TP_Corner", "TP_LongDrop")}
    mirror = Matrix.Scale(-1.0, 4, (0.0, 1.0, 0.0))
    return {
        "Straight":    PiecePath(pts=fine["TP_Straight"]),
        "CornerRight": PiecePath(pts=fine["TP_Corner"]),
        "CornerLeft":  PiecePath(pts=[mirror @ p for p in fine["TP_Corner"]]),
        "Drop":        PiecePath(pts=fine["TP_LongDrop"]),
        "Rise":        PiecePath(pts=[Vector((p.x, p.y, -p.z)) for p in fine["TP_LongDrop"]]),
    }


def frames_of(name, paths):
    return paths[name].length / rm.STEP


def plan_section(rules, rng, need_frames, paths, extra):
    """A section's pieces: dealt from the deck, and made long enough to hold what it has
    to hold. `extra` lengthens it further, when a first try came up short of rings."""
    n = rules["pieces"] + extra
    while True:
        names = grl.plan(dict(rules, pieces=n), rng)
        if sum(frames_of(p, paths) for p in names) >= need_frames:
            return names
        n += 2


def even_corners(names):
    """A marathon zone ends heading the way it began. steer() only ever lets the track go a
    quarter turn out and then back, so that is simply an even number of corners: an odd one
    out is dealt as a straight instead. It is what lets the hold's straight pipe, and then
    the next zone, carry straight on from wherever this one stopped."""
    corners = [i for i, n in enumerate(names) if n.startswith("Corner")]
    if len(corners) % 2:
        names = list(names)
        names[corners[-1]] = "Straight"
    return names


def steer(names, rng):
    """Choose which way each corner turns, so the track never heads more than a quarter
    turn away from the way it set out. A stage is sixty-odd pieces and a marathon far
    more; left to chance, three corners the same way drive it back into its own start, and
    it boxes itself in. Held to this, it can wander left and right but never turn back, so
    on the flat it cannot meet itself at all. The deck still decides WHERE the corners are."""
    heading, out = 0, []
    for n in names:
        if n.startswith("Corner"):
            turn = rng.choice([t for t in (-1, 1) if abs(heading + t) <= 1])
            heading += turn
            n = "CornerLeft" if turn > 0 else "CornerRight"
        out.append(n)
    return out


# ------------------------------------------------------------------------- objects --
def fill(window, pieces_at, book, rate, rng, decks, pool):
    """Lay modules along one section. Returns [(objects, first frame, angle put at)].

    Walks the section beat by beat. On each beat it looks at what is under the player --
    straight, corner, slope -- and lays a module only while that kind of track is below
    the section's ring rate; the module itself is dealt from what the original put on
    that kind of track in the stage this section takes its flavour from."""
    f0, f1 = window
    everything = [c for on in sorted(pool) for c in pool[on]]

    # DEALT, NOT ROLLED, for the reason the track is: a stage 1 straight has three bomb
    # shapes in seventeen, and rolled independently one stage in ten came out with no bombs
    # at all. Each kind of track has its own shuffled deck of the original's placements,
    # gone through to the bottom before it is shuffled again. The decks last the whole
    # STAGE, not one section -- a section draws only a few cards of each kind, and a fresh
    # deck each time is dice again -- and the bomb cards are spread through a deck, one to
    # each equal share of it, not left wherever the shuffle put them.
    def deal(on):
        key = (book["stage"], on)
        if not decks.get(key):
            cards = list(pool.get(on) or everything)
            rng.shuffle(cards)
            loud = [c for c in cards if "Bomb" in c["module"]]
            quiet = [c for c in cards if c not in loud]
            share = len(cards) / float(len(loud)) if loud else 0
            for i, c in enumerate(loud):
                quiet.insert(min(len(quiet), int(i * share + rng.random() * share)), c)
            decks[key] = quiet[::-1]                  # dealt from the end
        return decks[key].pop()

    def on_at(frame):
        for start, end, name in pieces_at:
            if start <= frame < end:
                return ON[name]
        return "straight"

    def corner_ahead(frame):
        return any(name.startswith("Corner") and 0 < start - frame <= BEFORE_CORNER
                   for start, end, name in pieces_at)

    laid, seen, put, bombs = [], {}, {}, 0
    s2_rings = sum(s["rings"] for s in book["sections"])
    bombs_per_ring = sum(s["bombs"] for s in book["sections"]) / float(s2_rings)
    mean = sum(book["density"].values()) / float(len(book["density"]))
    f = f0
    while f < f1:
        on = on_at(f)
        seen[on] = seen.get(on, 0) + GRID
        # The section's ring rate, leaning the way the original leans between kinds of
        # track (its corners are its densest part). Rings are what is counted: a bomb
        # shape does not use up the allowance, so a stage whose list is half bombs gets
        # its bombs ON TOP of its rings, and runs longer for it.
        lean = book["density"].get(on, mean) / mean
        if corner_ahead(f) or put.get(on, 0) / float(seen[on]) >= rate * lean:
            f += GRID
            continue
        # Bombs are held to the original stage's own ratio of bombs to rings. Without
        # this a bomb shape, costing no ring allowance, is dealt again and again: stage 6
        # came out with 1,175 bombs against the original's 304. One wall is sixteen.
        for _ in range(12):
            card = deal(on)
            m, at = module_of(card, rng)
            new_bombs = sum(k == rm.BOMB for _, _, k in m)
            if not new_bombs or bombs + new_bombs <= 8 + bombs_per_ring * sum(put.values()):
                break
        else:
            f += GRID
            continue
        length = rm.length(m)
        if f + length > f1:
            f += GRID
            continue
        bombs += new_bombs
        laid.append((m, f, at))
        USED[card["module"]] = USED.get(card["module"], 0) + 1
        put[on] = put.get(on, 0) + sum(k == rm.RING for _, _, k in m)
        step = length + rng.choice((2, 4, 4, 6))
        seen[on] = seen.get(on, 0) + step - GRID
        f += int(math.ceil(step / GRID)) * GRID
    return laid


def top_up(laid, window, pool, target, rng):
    """Short of the target? Put ring-only shapes into the longest empty stretches."""
    f0, f1 = window
    ring_only = [p for on in sorted(pool) for p in pool[on] if p["module"] != "Ring" and p["objects"] >= 4]
    ring_only = [p for p in ring_only if all(k == rm.RING for _, _, k in module_of(p, random.Random(0))[0])]
    for _ in range(200):
        if rings_in(laid) >= target or not ring_only:
            break
        taken = sorted((f, f + rm.length(m)) for m, f, _ in laid)
        gaps, cursor = [], f0
        for a, b in taken + [(f1, f1)]:
            if a - cursor >= 8:
                gaps.append((a - cursor, cursor))
            cursor = max(cursor, b)
        if not gaps:
            break
        size, start = max(gaps)
        m, at = module_of(rng.choice(ring_only), rng)
        if rm.length(m) + 4 > size:
            m, at = list(rm.MODULES["ClusterSmall"]), rng.choice((-48, 0, 48))
            if rm.length(m) + 4 > size:
                break
        laid.append((m, start + 2 + (size - rm.length(m) - 4) // 2 // 2 * 2, at))
    return laid


def trim(laid, target, rng):
    """Over the promise? Take ring-only shapes away until it is met as nearly as whole
    shapes allow, never going under. The promise cuts both ways: x1.05 that comes out as
    x1.4 is not stage 7 any more. Bombs and mixed shapes are left where they are."""
    laid = list(laid)
    while True:
        spare = rings_in(laid) - target
        loose = [x for x in laid if all(k == rm.RING for _, _, k in x[0]) and len(x[0]) <= spare]
        if not loose:
            return laid
        laid.remove(rng.choice(loose))


USED = {}                   # module -> times laid, for the report; reset each try


def rings_in(laid):
    return sum(k == rm.RING for m, _, _ in laid for _, _, k in m)


def bombs_in(laid):
    return sum(k == rm.BOMB for m, _, _ in laid for _, _, k in m)


# ------------------------------------------------------------------------- building --
def srgb_to_linear(c):
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def recolour(pieces_in_order, palette_of_piece):
    """Give every piece the colours of the palette it belongs to.

    Every stage has its own pipe colour, from the original (stage_palettes.py). The five
    baked meshes are shared by every piece in the level, so the colour cannot live on the
    mesh: each piece's material slots are switched to belong to the OBJECT, and pointed at
    that palette's copy of the material. One set of copies per palette, however many pieces
    use it -- which is also how a marathon changes colour zone by zone in one file."""
    made = {}
    for ob, stage in zip(pieces_in_order, palette_of_piece):
        colours = stage_palettes.palette(stage)["materials"]
        for slot in ob.material_slots:
            base = slot.material
            if base is None or base.name.split(".")[0] not in colours:
                continue
            name = base.name.split(".")[0]
            key = (stage, name)
            if key not in made:
                mat = base.copy()
                mat.name = "%s_S%d" % (name, stage)
                lin = tuple(srgb_to_linear(c) for c in colours[name]) + (1.0,)
                mat.diffuse_color = lin
                bsdf = mat.node_tree.nodes.get("Principled BSDF") if mat.node_tree else None
                if bsdf is not None:
                    bsdf.inputs["Base Color"].default_value = lin
                made[key] = mat
            slot.link = 'OBJECT'
            slot.material = made[key]


def rainbow_arch(origin, ring_mesh, tag, coll):
    """Rings round the spheres of the arch over one straight piece set down at `origin`."""
    made = []
    reach = rm.PIPE_RADIUS + ARCH_OUT
    for i in range(ARCH_COUNT):
        t = math.radians(ARCH_FROM_DEG + (180.0 - 2.0 * ARCH_FROM_DEG) * i / (ARCH_COUNT - 1))
        name = "CheckRainbow_%d" % i
        mat = bpy.data.materials.get(name)
        if mat is None:
            mat = bpy.data.materials.new(name)
            lin = tuple(srgb_to_linear(c) for c in RAINBOW[i % len(RAINBOW)]) + (1.0,)
            mat.diffuse_color = lin
            mat.use_nodes = True
            bsdf = mat.node_tree.nodes.get("Principled BSDF")
            if bsdf is not None:
                bsdf.inputs["Base Color"].default_value = lin
                if "Emission Color" in bsdf.inputs:
                    bsdf.inputs["Emission Color"].default_value = lin
                    bsdf.inputs["Emission Strength"].default_value = 1.5
        ob = bpy.data.objects.new("%s_Rainbow_%d" % (tag, i), ring_mesh)
        ob.matrix_basis = (origin @ Matrix.Translation((rm.SECTION * 0.5 - RAINBOW_RING_TOWARD_PLAYER,
                                                        reach * math.cos(t),
                                                        rm.PIPE_RADIUS + reach * math.sin(t)))
                           @ Matrix.Scale(RAINBOW_RING_SCALE, 4))
        coll.objects.link(ob)
        # the mesh is every ring's, so the colour goes on the object, as the pipe's does
        ob.material_slots[0].link = 'OBJECT'
        ob.material_slots[0].material = mat
        ob["rainbow_index"] = i
        made.append(ob)
    return made


def octahedron(name, size, colour):
    bm = bmesh.new()
    v = [bm.verts.new(p) for p in ((size, 0, 0), (-size, 0, 0), (0, size, 0), (0, -size, 0),
                                   (0, 0, size * 1.4), (0, 0, -size * 1.4))]
    for a, b, c in ((0, 2, 4), (2, 1, 4), (1, 3, 4), (3, 0, 4), (2, 0, 5), (1, 2, 5), (3, 1, 5), (0, 3, 5)):
        bm.faces.new((v[a], v[b], v[c]))
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    mat = bpy.data.materials.new(name)
    mat.diffuse_color = colour
    me.materials.append(mat)
    return me


def spline(name, chain, d0, d1, coll):
    cu = bpy.data.curves.new(name, 'CURVE')
    cu.dimensions = '3D'
    sp = cu.splines.new('POLY')
    n = max(2, int((d1 - d0) / 4.0))
    sp.points.add(n - 1)
    for i, pt in enumerate(sp.points):
        co = chain.frame(d0 + (d1 - d0) * i / (n - 1)).translation
        pt.co = (co.x, co.y, co.z, 1.0)
    ob = bpy.data.objects.new(name, cu)
    ob.hide_render = True
    coll.objects.link(ob)
    return ob


def main():
    rulebook = json.load(open(os.path.join(HERE, "ring_rulebook.json"), encoding="utf-8"))

    def book_of(stage):
        return dict(rulebook[str(stage)], stage=stage)

    plan = designs(book_of)
    count = len(plan)
    for d in plan:
        d["target"] = int(math.ceil(d["asks"] * d["forgiveness"]))
        book = book_of(d["flavour"])
        bomb_share = 1.0 - sum(s["rings"] for s in book["sections"]) / float(
            sum(s["rings"] + s["bombs"] for s in book["sections"]))
        d["per_frame"] = d["ring_rate"] * (1.0 - 0.5 * bomb_share)     # bombs take room too
    pieces = grl.load_pieces()
    paths = piece_paths()
    pools = {}

    def build_part(part, key, first):
        """Build some sections as ONE piece of track, at the origin, from nothing but `key`.
        Returns everything about it in its own frames and its own space. Nothing is carried
        in from outside: not the random stream, not the decks, not where the last part ended.
        That is what lets the engine build a marathon zone on the fly -- see THE HOLD."""
        extra = [0] * len(part)
        lead = LEAD_IN if first else ZONE_LEAD_IN
        for attempt in range(60):
            rng = random.Random("%s/%d" % (key, attempt))
            names, cuts, zones = ["Straight"] * (INTRO_STRAIGHTS if first else 0), [], []
            for k, d in enumerate(part):
                room = rng.uniform(*MARATHON_ROOM) if MARATHON else 1.05
                need = d["target"] / d["per_frame"] * room + (lead if k == 0 else 0)
                names += plan_section(d["rules"], rng, need, paths, extra[k])
                emerald = d["leads_to"] == "EMERALD"
                run_up, plays = (EMERALD_RUN_UP, EMERALD_PLAYS) if emerald else (CHECK_RUN_UP, CHECK_PLAYS)
                zones.append((len(names), len(names) + run_up))  # first piece of the zone, piece of the check
                names += ["Straight"] * (run_up + plays)         # THE RING CHECK ZONE
                cuts.append(len(names))
            if MARATHON:
                names = even_corners(names)
            names = steer(names, rng)
            laid_names, origins, laid_pts, swaps = grl.generate(pieces, part[0]["rules"], rng, plan_names=names)
            if len(laid_names) < len(names):
                print("  %s try %d: boxed itself in, dealing again" % (key, attempt + 1))
                continue

            # where each piece sits, in frames from the start of this part
            pieces_at, f = [], 0.0
            for n in laid_names:
                pieces_at.append((f, f + frames_of(n, paths), n))
                f += frames_of(n, paths)
            ends = [pieces_at[c - 1][1] for c in cuts]
            starts = [0.0] + ends[:-1]
            zone_first = [pieces_at[z][0] for z, _ in zones]
            check_at = [pieces_at[c][0] + ARCH_FRAME for _, c in zones]       # under the rainbow arch

            sections, short, decks = [], None, {}
            USED.clear()
            for k, d in enumerate(part):
                window = (int(math.ceil(starts[k])) + (lead if k == 0 else 0), int(zone_first[k]))
                book = book_of(d["flavour"])
                pool = pools.setdefault(d["flavour"], build_cards(rulebook, d["flavour"]))
                laid = fill(window, pieces_at, book, d["ring_rate"], rng, decks, pool)
                laid = trim(top_up(laid, window, pool, d["target"], rng), d["target"], rng)
                sections.append(laid)
                if rings_in(laid) < d["target"] and short is None:
                    short = k
            if short is None:
                break
            print("  %s try %d: section %d offers %d rings of the %d promised; padding it"
                  % (key, attempt + 1, short + 1, rings_in(sections[short]), part[short]["target"]))
            extra[short] += 2                         # pad that section, and deal again
        else:
            raise SystemExit("could not build %s to its guarantee in 60 tries" % key)
        return dict(names=laid_names, origins=origins, pts=laid_pts, swaps=swaps, cuts=cuts, zones=zones,
                    starts=starts, ends=ends, zone_first=zone_first, check_at=check_at,
                    sections=sections, used=dict(USED), extra=extra, tries=attempt + 1, key=key)

    # A gauntlet stage is one part. A marathon is a part per zone, each built on its own and
    # then set down where the last one ended -- in the game the last one is gone by then.
    if MARATHON:
        parts = [build_part(plan[z * SECTIONS_PER_ZONE:(z + 1) * SECTIONS_PER_ZONE],
                            "%d/zone%d" % (SEED, z), first=(z == 0)) for z in range(ZONES)]
    else:
        parts = [build_part(plan, NAME, first=True)]

    laid_names, origins, laid_pts, swaps, cuts, zones = [], [], [], [], [], []
    starts, ends, zone_first, check_at, sections, extra = [], [], [], [], [], []
    used_all, tries, zone_info = {}, 0, []
    here, frame0 = Matrix.Identity(4), 0.0
    for z, part in enumerate(parts):
        n0 = len(laid_names)
        zone_info.append(dict(index=z, key=part["key"], first_piece=n0, pieces=len(part["names"]),
                              first_frame=frame0, last_frame=frame0 + part["ends"][-1]))
        laid_names += part["names"]
        origins += [here @ o for o in part["origins"]]
        laid_pts += [[here @ pt for pt in world] for world in part["pts"]]
        swaps += part["swaps"]
        cuts += [n0 + c for c in part["cuts"]]
        zones += [(n0 + a, n0 + c) for a, c in part["zones"]]
        starts += [frame0 + v for v in part["starts"]]
        ends += [frame0 + v for v in part["ends"]]
        zone_first += [frame0 + v for v in part["zone_first"]]
        check_at += [frame0 + v for v in part["check_at"]]
        sections += [[(m, first + int(round(frame0)), at) for m, first, at in laid] for laid in part["sections"]]
        extra += part["extra"]
        tries += part["tries"]
        for k, v in part["used"].items():
            used_all[k] = used_all.get(k, 0) + v
        local = ChainPath([paths[n] for n in part["names"]], part["origins"])
        here = here @ local.frame(local.length)
        frame0 += part["ends"][-1]
    USED.clear()
    USED.update(used_all)
    attempt = tries - 1
    rng = random.Random(NAME + "/shifts")

    # ---- the guarantee, checked rather than assumed --------------------------------
    for k, d in enumerate(plan):
        assert rings_in(sections[k]) >= d["target"] >= d["asks"], "section %d breaks the guarantee" % (k + 1)

    # ---- the scene -----------------------------------------------------------------
    grl.build_scene(pieces, laid_names, origins, laid_pts)
    chain = ChainPath([paths[n] for n in laid_names], origins)
    scene = bpy.context.scene
    meshes = {}
    for kind, blend, mesh in ((rm.RING, RING_BLEND, "Ring"), (rm.BOMB, BOMB_BLEND, "Bomb")):
        with bpy.data.libraries.load(blend) as (src, dst):
            dst.meshes = [n for n in src.meshes if n == mesh]
        meshes[kind] = dst.meshes[0]
    gem = octahedron("Emerald", 2.2, (0.10, 0.85, 0.95, 1.0))

    # ---- colours: a gauntlet stage wears its own; a marathon changes at each palette shift
    zone_palette = []
    for z in range((count + SECTIONS_PER_ZONE - 1) // SECTIONS_PER_ZONE):
        if not MARATHON:
            zone_palette.append(STAGE)
        else:
            pick = random.Random("%d/zone%d/palette" % (SEED, z)).randrange(1, 8)
            if zone_palette and pick == zone_palette[-1]:
                pick = pick % 7 + 1                   # never the same look twice running
            zone_palette.append(pick)

    level = bpy.data.collections["Level"]
    level_pieces = sorted((o for o in level.objects if o.type == 'MESH'),
                          key=lambda o: int(o.name[1:].split("_")[0]))     # in track order
    section_of_piece = [sum(i >= c for c in cuts[:-1]) for i in range(len(level_pieces))]
    recolour(level_pieces, [zone_palette[k // SECTIONS_PER_ZONE] for k in section_of_piece])

    for i, ob in enumerate(level_pieces):
        k = sum(i >= c for c in cuts[:-1])
        ob["section"] = k + 1
        if i < INTRO_STRAIGHTS:
            ob["intro"] = True
            ob.name = "L%03d_Intro" % i
        elif i >= zones[k][0]:
            ob["ring_check"] = k + 1
            ending = plan[k]["leads_to"] == "EMERALD" and i > zones[k][1]
            ob.name = ("L%03d_Ending" % i) if ending else "L%03d_RingCheck%02d" % (i, k + 1)

    data = dict(name=NAME, mode="marathon" if MARATHON else "gauntlet", stage=STAGE, seed=SEED,
                step=rm.STEP, pieces=laid_names, sections=[],
                palettes={str(st): stage_palettes.palette(st) for st in range(1, 8)})
    if MARATHON:
        # What the engine needs to carry the run on past the last section built here.
        data["marathon_rules"] = dict(
            start=MARATHON_START, ramp=MARATHON_RAMP, ask_step=MARATHON_ASK_STEP,
            forgiveness_floor=MARATHON_FORGIVENESS_FLOOR, ring_rate_ceiling=MARATHON_RING_RATE_CEILING,
            flavours=list(MARATHON_FLAVOURS), sections_per_zone=SECTIONS_PER_ZONE,
            quota_thirds={k: round(v[2] / 3.0, 1) for k, v in QUOTA.items()},
            forgiveness=FORGIVENESS, ring_rate=RING_RATE)

    asked_so_far = 0
    for k, d in enumerate(plan):
        asked_so_far += d["asks"]
        coll = bpy.data.collections.new("Section%02d" % (k + 1))
        scene.collection.children.link(coll)
        spline("Section%02d_Path" % (k + 1), chain, starts[k] * rm.STEP, ends[k] * rm.STEP, coll)

        objects = []
        for j, (m, first, at) in enumerate(sorted(sections[k], key=lambda x: x[1])):
            root_m = chain.frame(first * rm.STEP)
            root = bpy.data.objects.new("S%02d_M%02d" % (k + 1, j), None)
            root.empty_display_type, root.empty_display_size = 'ARROWS', 2.0
            root.matrix_basis = root_m
            root["first_frame"], root["at"] = first, at
            coll.objects.link(root)
            for i, (mat, kind) in enumerate(lay(m, chain, first, at)):
                ob = bpy.data.objects.new("S%02d_M%02d_%s_%02d" % (k + 1, j, kind, i), meshes[kind])
                ob.parent = root
                ob.matrix_basis = root_m.inverted() @ mat
                coll.objects.link(ob)
            objects += [[first + f, signed(a + at), kind] for f, a, kind in m]

        emerald = d["leads_to"] == "EMERALD"
        check = bpy.data.objects.new("Emerald" if emerald else "Check_%02d" % (k + 1), gem if emerald else None)
        check.matrix_basis = chain.frame(check_at[k] * rm.STEP) @ Matrix.Translation((0, 0, rm.PIPE_RADIUS * 0.6))
        if not emerald:
            check.empty_display_type, check.empty_display_size = 'CIRCLE', rm.PIPE_RADIUS
            check.rotation_euler.rotate_axis('Y', math.pi / 2)
        check["quota"], check["leads_to"] = asked_so_far, d["leads_to"]
        coll.objects.link(check)
        call = bpy.data.objects.new("RingsToGo_%02d" % (k + 1), None)
        call.empty_display_type, call.empty_display_size = 'PLAIN_AXES', 4.0
        call.matrix_basis = chain.frame((check_at[k] - RINGS_TO_GO) * rm.STEP)
        coll.objects.link(call)
        logo = bpy.data.objects.new("CheckLogo_%02d" % (k + 1), None)
        logo.empty_display_type, logo.empty_display_size = 'CUBE', 3.0
        logo.matrix_basis = chain.frame(check_at[k] * rm.STEP) @ Matrix.Translation((0, 0, rm.PIPE_RADIUS * 2.4))
        coll.objects.link(logo)
        done = bpy.data.objects.new("CheckPass_%02d" % (k + 1), None)
        done.empty_display_type, done.empty_display_size = 'SINGLE_ARROW', 6.0
        done.matrix_basis = chain.frame(ends[k] * rm.STEP)
        done["plays"] = "logo at the top; count; on a pass the camera turns to Sonic, RunThumbsUp"
        coll.objects.link(done)
        rainbow_arch(origins[zones[k][1]], meshes[rm.RING], "Check_%02d" % (k + 1), coll)

        palette_seed = None
        if d["leads_to"] == "PALETTE SHIFT":
            # The hook for what is not made yet: a new sky and new pipe colours from here
            # on. The seed is this zone's, so the same run shifts the same way every time.
            palette_seed = rng.randrange(1, 1000000)
            shift = bpy.data.objects.new("PaletteShift_%02d" % ((k + 1) // SECTIONS_PER_ZONE), None)
            shift.empty_display_type, shift.empty_display_size = 'SPHERE', rm.PIPE_RADIUS * 1.5
            shift.matrix_basis = chain.frame(ends[k] * rm.STEP)       # as the pass finishes
            shift["palette_seed"] = palette_seed
            shift["hold"] = "zoom on Sonic, RunThumbsUp, on looping straight pipe until the next zone is built"
            coll.objects.link(shift)

        rings, bombs = rings_in(sections[k]), bombs_in(sections[k])
        data["sections"].append(dict(
            first_frame=starts[k], check_frame=check_at[k], last_frame=ends[k],
            ring_check=dict(first_frame=zone_first[k], check_frame=check_at[k], last_frame=ends[k],
                            rainbow_arch=dict(piece=zones[k][1], frame=check_at[k], rings=ARCH_COUNT,
                                              ring_scale=RAINBOW_RING_SCALE, colours=[list(c) for c in RAINBOW],
                                              cycles=True, steps_per_second=RAINBOW_STEPS_PER_SECOND),
                            run_up_frames=check_at[k] - zone_first[k], plays_frames=ends[k] - check_at[k]),
            pieces=cuts[k] - (cuts[k - 1] if k else 0),
            difficulty=d["difficulty"], flavour=d["flavour"], forgiveness=d["forgiveness"],
            ring_rate=d["ring_rate"], quota=asked_so_far, asks=d["asks"], rings=rings, bombs=bombs,
            margin=round(rings / float(d["asks"]), 2), leads_to=d["leads_to"],
            palette=zone_palette[k // SECTIONS_PER_ZONE],
            palette_seed=palette_seed,
            hold=(dict(piece="Straight", animation="RunThumbsUp", camera="zoom to Sonic",
                       until="the next zone is built", then="palette shift; resume")
                  if d["leads_to"] == "PALETTE SHIFT" else None),
            objects=sorted(objects)))
    scene["quota"] = [s["quota"] for s in data["sections"]]
    if MARATHON:
        for z, info in enumerate(zone_info):
            info["palette"] = zone_palette[z]
        data["zones"] = zone_info

    # ---- say what was made ---------------------------------------------------------
    print("\n%s: %d pieces, %.0f frames, %.0f units" % (NAME, len(laid_names), ends[-1], ends[-1] * rm.STEP))
    for k, s in enumerate(data["sections"]):
        a, b = (cuts[k - 1] if k else 0), cuts[k]
        print("  section %2d  difficulty %4.1f  %2d pieces %4.0f frames  %s"
              % (k + 1, s["difficulty"], b - a, s["last_frame"] - s["first_frame"],
                 " ".join(LETTER[n] for n in laid_names[a:b])))
        print("              check: %4d rings%s | newly asks %3d | on offer %3d rings (x%.2f, promised x%.2f), %3d bombs"
              % (s["quota"], "" if s["leads_to"] in ("on",) or s["leads_to"].startswith("section") else " -> " + s["leads_to"],
                 s["asks"], s["rings"], s["margin"], s["forgiveness"], s["bombs"]))
    print("  colours: " + ", ".join("%s%s (sky %s)" % (
        "zone %d " % (z + 1) if MARATHON else "", stage_palettes.NAMES[pal], stage_palettes.SKY[pal][1])
        for z, pal in enumerate(zone_palette)))
    print("  %d kinds of shape: %s" % (len(USED), ", ".join(
        "%s x%d" % kv for kv in sorted(USED.items(), key=lambda kv: -kv[1]))))
    data["kinds"] = dict(USED)
    print("  padded %s pieces beyond the deck to keep the promise; %d tries" % (extra, attempt + 1))
    for line in swaps:
        print("  swapped to avoid the level running into itself -- " + line)

    os.makedirs(OUT_DIR, exist_ok=True)
    json.dump(data, open(os.path.join(OUT_DIR, NAME + ".json"), "w", encoding="utf-8"))
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(OUT_DIR, NAME + ".blend"))
    print("saved", os.path.join(OUT_DIR, NAME + ".blend"))

    if RENDER:
        for engine in ('BLENDER_EEVEE', 'BLENDER_EEVEE_NEXT'):
            try:
                scene.render.engine = engine
                break
            except TypeError:
                pass
        sun = bpy.data.objects.new("Sun", bpy.data.lights.new("Sun", 'SUN'))
        sun.data.energy = 3.0
        sun.rotation_euler = (math.radians(30), math.radians(-20), 0.0)
        scene.collection.objects.link(sun)
        cam = scene.camera
        # from where the player stands, at the first shape of the first, middle and last section
        cam.data.type, cam.data.lens = 'PERSP', 16.0
        scene.render.resolution_x, scene.render.resolution_y = 960, 600
        # the rainbow arch, from the run-in to the first ring check
        here = chain.frame((check_at[0] - 10) * rm.STEP)
        ahead = chain.frame(check_at[0] * rm.STEP)
        pos = here @ Vector((0.0, 0.0, 7.5))
        cam.location = pos
        cam.rotation_euler = (ahead @ Vector((0.0, 0.0, 12.0)) - pos).to_track_quat('-Z', 'Y').to_euler()
        scene.render.filepath = os.path.join(OUT_DIR, "%s_ringcheck.png" % NAME)
        bpy.ops.render.render(write_still=True)

        for k in sorted(set((0, count // 2, count - 1))):
            first = min(f for _, f, _ in sections[k])
            here = chain.frame((first - 7) * rm.STEP)
            ahead = chain.frame((first + 6) * rm.STEP)
            pos = here @ Vector((0.0, 0.0, 8.5))
            cam.location = pos
            cam.rotation_euler = (ahead @ Vector((0.0, 0.0, 4.0)) - pos).to_track_quat('-Z', 'Y').to_euler()
            scene.render.filepath = os.path.join(OUT_DIR, "%s_section%02d.png" % (NAME, k + 1))
            bpy.ops.render.render(write_still=True)


# Only when run as the script: export_to_octave.py imports this for piece_paths().
if __name__ == "__main__":
    main()
