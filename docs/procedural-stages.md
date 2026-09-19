# Procedural stages: how this project builds a special stage

The decision, and why. Read this before touching the track, the rings or the bombs.

## The idea in one line

A stage is not a model. It is a **list**, played back out of two small libraries of
hand-shaped parts: **track pieces** and **object patterns**.

## Why

The original Sonic 2 special stage works this way. Its track is five canned
animations chained by a list of bytes, and its rings and bombs are placement lists
laid over them (see `s2-special-stage-layouts.md`). There was never one continuous
shape.

The first attempt here ignored that and turned stage 1's list into a single long
spline, with the shape of every turn and hill computed from numbers. Every problem
that followed came from that:

| Problem | Why a single spline caused it |
|---|---|
| "The drops are too short" -- three rounds of it | a drop was one constant inside a global curve, instead of a shape someone could look at and fix once |
| The stage ran into itself | only possible when the whole stage exists at once, as one object |
| Is type 0 a rise or a drop? | an argument about what the ROM *means*, standing in for the real question: what should the piece *look like* |
| Turn sharpness capped at 45 degrees | chosen to dodge the self-collision, not because it looked right |

With pieces, the person who knows what a Sonic 2 drop looks like shapes the drop, once,
by eye, and every drop in every stage follows. The data only decides the order.

## The two libraries

### Track pieces -- `external/halfpipe/TrackPieces.blend`

One curve per segment type, matching the game's five:

| Piece | Game type | Original frames | Length here |
|---|---|---|---|
| `TP_Straight` | 3 | 16 | 1 pipe section |
| `TP_StraightToTurn` | 4 | 11 | 1 section |
| `TP_TurnToStraight` | 2 | 12 | 1 section |
| `TP_TurnThenDrop` | 1 | 24 | 3 sections |
| `TP_TurnThenRise` | 0 | 24 | 3 sections |

Lengths are whole pipe sections, which the original's are not (11 and 12 frames
against a straight's 16). That is a deliberate trade: whole sections mean every piece
can also be a self-contained mesh with a hoop and an arch in the right place, which is
what lets the engine build stages at runtime. The rhythm shifts slightly; the modular
build is worth it.

**The joint.** Every piece starts at its own origin, heading +X, level. Where it ends,
and which way it is heading there, is read from the curve itself -- so a piece can be
reshaped freely and will still chain. The one rule: **end level.** A piece may climb or
fall, but its last stretch must be flat, or everything after it inherits the tilt.

**Mirroring.** A left turn is a right turn mirrored, as in the original. Only the
unmirrored pieces are authored.

### Object patterns -- not built yet

Rings and bombs come as patterns, not as loose objects: ring spiral, ring row, ring
arc, bomb wall, alternating ring and bomb. Each takes a few numbers -- how many, where
round the pipe it starts, how much it twists per step, spacing along the track. A
pattern is laid on a piece and rides its curve.

The original's placements are in `misc/Special stage object location lists.kos`
(Kosinski-compressed, **undecoded**). They are raw positions, not patterns, so using
them means either placing them as they are or recognising the spirals and rows in them.

## A stage

    track:   [Straight, Straight, Straight, StraightToTurn, TurnToStraight, ...]
    objects: [(piece 0, RingRow, ...), (piece 2, RingSpiral, ...), ...]

Two sources of lists:

* **Classic** -- the seven original layouts, already decoded. A fixed list each.
* **Generated** -- see below.

`native/chain_track_pieces.py` plays a track list back into one curve, for looking at
a whole stage in Blender. The engine should do the same at runtime, keeping only the
next few pieces alive: cheap enough for a GameCube, and a stage that would cross itself
as one object never shows it, because its far parts do not exist yet.

## Generated stages and the difficulty rulebook

Stages are generated at random, under a difficulty from 1 to 7. "AI difficulty" here
means a **rulebook, not a learned model**: each level is a row of limits the generator
must obey. That is what makes "level 1 can never get too hard" a guarantee and not a
probability.

Limits per level:

* how often turns come, and how many may chain without a straight between them
* how many drops
* which object patterns are allowed at all
* bomb density, and how much warning comes before a bomb
* ring surplus: how many more rings exist than the quota asks for
* running speed

**Every generated stage is checked before it is used.** A checker runs the best
possible line through it and confirms the rings that can actually be collected beat the
quota by the level's margin -- generous at 1, thin at 7. Random placement alone could
ask for 40 rings and offer 35, or put the rings on one wall and force the player to the
other. A stage that fails is rerolled.

**Fairness rules**, taken from how the original behaves: no bomb wall straight after a
blind drop at low levels; always a straight to recover on after a drop; a new pattern
appears alone before it appears in combination.

**Seeds.** The same seed always gives the same stage. That makes a stage retryable and
shareable, makes bugs reproducible, and answers the one real cost of going random: the
original is partly a memory game, learned by replaying. A fixed seed per level gives
memorisable stages; a fresh seed gives endless ones.

**Calibrate from the real game.** The rulebook's numbers should be measured from the
seven original stages -- how turn frequency, drops and length really climb from 1 to
7 -- so that generated level 3 plays like the original's stage 3.

## What is kept from the single-spline work

The spline itself is scaffolding and goes. What it produced stays:

* the decoded layouts for all seven stages, and the mirror-flag rules
* `native/nemesis.py`
* the per-frame pacing tables, useful as a starting shape for a piece
* `native/gen_s2_track.py`, kept as the record of that approach

## Open

* Left or right: which way an unmirrored turn goes is not in the data. `right`, from
  memory of the game.
* Rise or drop: what the ROM suggests and what is built differ; see the layouts doc.
  With pieces this stops mattering -- the generator simply uses the pieces it is told to.
* The object location file is undecoded.
* Where stages are assembled -- Blender, or the engine at runtime -- is not settled.
  Runtime is the more procedural and the lighter.
