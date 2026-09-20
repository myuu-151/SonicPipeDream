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

**The model on each piece.** `native/build_piece_models.py` puts the real half-pipe on
every piece: pipe, rails and sphere arches (`TPM_<piece>_Pipe`, `_Rails`, `_Spheres`),
repeated once per section and bent along that piece's curve. Run it again after
reshaping a curve; it replaces only the objects it made, never the curves.

A piece's model has to span its curve exactly, 0 to its length, or chained pieces gap
or overlap. The pipe was modelled from x = -8.18, so the meshes are shifted to start at
0. That puts the hoop and its arch in the middle of each section and the rails on the
seams; **each piece owns the rail at the end of each of its sections**, so none is built
twice. The script checks the fit and prints how far each pipe's far end lands from its
curve's end (0.03 units at worst).

### The working set: three shapes, five pieces -- `TrackPiecesPack.blend`

The pieces are modular, and that is worth more than it sounds. The pack that is
actually used holds three authored shapes -- `TP_Straight`, `TP_Corner` (90 degrees,
with a straight lead in and out) and `TP_LongDrop` (a chute: tips over, holds 50
degrees, settles, flat run-off) -- and they give five pieces:

| Piece | How |
|---|---|
| Straight | as authored |
| Corner right | as authored |
| Corner left | the same piece mirrored |
| Drop | as authored |
| Rise | the drop piece travelled backwards |

An S-bend is just a left corner followed by a right one. The five game-typed pieces in
`TrackPieces.blend` are only needed to play back the original layouts.

### Object patterns -- `native/ring_modules.py`

**Built** as 77 ring and bomb modules taken from the original's own vocabulary; see
[s2-special-stage-objects.md](s2-special-stage-objects.md). Not yet laid on levels. The
paragraphs below are the plan they were built to.

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

## The generator -- `native/gen_random_level.py`

    blender -b external/halfpipe/TrackPiecesPack.blend \
        --python native/gen_random_level.py -- <out.blend> [difficulty 1-7] [seed]

Track only, so far. It bakes each piece once into a single self-contained mesh (pipe,
rails and arches joined, modifiers applied; the mirrored corner has its faces turned
back the right way) and sets those down end to end with one rigid transform each --
which is exactly what the engine will do at runtime.

**It deals from a deck; it does not roll dice.** Rolling each piece independently only
meets the rulebook on average: one seed at difficulty 3 rolled high nine times running
and produced fifteen straights out of eighteen, and the same luck the other way is how
an easy level turns hard. So the mix is fixed first -- this many corners, this many
hills, the rest straights -- then the straights the rules demand are placed (two to
open, a rest after each hill, a break in any run of corners past the limit, one to
close), and only what is left is scattered at random.

**It will not build a level that runs into itself.** A piece that would come within 45
units of an earlier part of the track at a similar height is swapped for the nearest
thing that fits -- the other corner, a drop to pass underneath, a straight -- and the
swap is printed, since it changes the mix the deck promised.

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
* Where stages are assembled -- Blender, or the engine at runtime -- is not settled.
  Runtime is the more procedural and the lighter.
