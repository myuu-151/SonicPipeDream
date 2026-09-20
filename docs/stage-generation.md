# Stage generation: the gauntlet and the marathon

How `native/gen_stage.py` builds a whole special stage -- track, rings, bombs, checks,
splines -- and the rules it is held to. The track half is
[procedural-generation.md](procedural-generation.md); the modules are
[s2-special-stage-objects.md](s2-special-stage-objects.md).

    blender -b external/halfpipe/TrackPiecesPack.blend \
        --python native/gen_stage.py -- <1-7 | marathon [zones]> [seed N] [render]

    python native/make_stage_maps.py external/stages/Stage1_seed1.json     # draw it flat

Writes `external/stages/<name>.blend` (everything, to look at and edit), `<name>.json` (the
same as data, for the engine) and, with `render`, the player's view at the first shape of
the first, middle and last section.

## The two modes

**The gauntlet** is stages 1 to 7, which is what the menu lists: one emerald each. It is
authoritative -- everyone plays the same seven -- so each stage has one fixed seed, in
`GAUNTLET_SEED`. Change a seed and that stage is a different stage for good.

**The marathon** is unlocked in the menu when the seventh emerald is won (the unlock is the
game's business, not this script's). It is **one continuous run with no end**, harder
section by section, with a new random seed every run. A `.blend` cannot be endless, so
`marathon Z` builds the first Z zones to look at; the engine carries on with the same
rules, which are written into the `.json` as `marathon_rules`.

## Sections, checks, zones

Everything is made of **sections**. A section is a stretch of track ending at a **check**,
which asks for a number of rings (cumulative, as the original counts them).

* A gauntlet stage is **three sections at one difficulty**. The third check leads to the
  emerald.
* The marathon is sections without end. They come in threes too -- a **zone** -- and after
  each third check **the palette shifts**: a new sky, new colours on the pipe. *The palettes
  are not made yet.* The shift points exist already: a `PaletteShift_NN` empty in the
  `.blend` and a `palette_seed` in the `.json`, one per zone, so the same run shifts the
  same way every time.

In the `.blend`: a `Level` collection (the pieces, each tagged with its section, and
`Level_Path`), then one collection per section -- `Section01` ... -- holding its own spline
`Section01_Path`, a root empty per module (`S01_M03`, at the module's first frame, with its
rings and bombs parented to it, so a whole shape moves as one), the check (`Check_01`, or
`Emerald`), and `RingsToGo_01` where the "rings to go" call comes, 24 frames before it.

## The guarantee

> A section always holds enough rings to pass its own check, from nothing, and by a margin:
> rings on offer >= rings it newly asks for x its forgiveness.

The generator does not hope for this. It sizes the section for it, fills it, tops it up
with ring-only shapes in the longest gaps, and if it is still short **pads the section with
more track and deals again**; it refuses to write a stage that breaks it (`assert`). It
holds the other way too: rings over the promise are taken back out, so x1.05 does not come
out as x1.4 and quietly stop being stage 7. Every run prints, per section, what was asked,
what is on offer, and the margin promised and met.

## Two rulebooks, kept apart

**Measured** -- `native/ring_rulebook.json`, written by `native/make_ring_rulebook.py` from
the original seven stages. Nothing in it is a guess:

* every module the original put down, with whether it was mirrored, which stretch of a run
  it was, **the angle it was put at**, and **what kind of track it was on** (straight,
  corner, slope). The generator deals from *these*, so it inherits what the game uses, how
  often, where round the pipe and on what, all at once;
* objects per 100 frames by kind of track (the original packs its corners, thins the run-up
  to them); bombs per ring; the original quotas (`SpecialStage_RingReq_*` in `s2.asm`) and
  how forgiving each original section is.

**Designed** -- three curves in `gen_stage.py`, the project owner's. The original's own
wander (its stage 5 is kinder than its stage 2, its quotas climb only 130 to 190, and its
stage 3 offers 55 rings for a check that asks 60), so these are ours:

| Stage | `QUOTA` (three checks) | `FORGIVENESS` | `RING_RATE` | comes out as |
|---|---|---|---|---|
| 1 | 30 / 70 / 130 | x2.2 | 0.34 | 69 pieces, 1,024 frames |
| 2 | 40 / 90 / 170 | x2.0 | 0.38 | 68 pieces, 1,160 frames |
| 3 | 50 / 115 / 210 | x1.8 | 0.41 | 79 pieces, 1,488 frames |
| 4 | 70 / 160 / 290 | x1.6 | 0.45 | 74 pieces, 1,504 frames |
| 5 | 90 / 210 / 380 | x1.4 | 0.49 | 78 pieces, 1,648 frames |
| 6 | 110 / 260 / 480 | x1.2 | 0.52 | 91 pieces, 1,952 frames |
| 7 | 140 / 320 / 600 | x1.05 | 0.56 | 91 pieces, 2,312 frames |

**Length is not set anywhere.** It falls out as quota x forgiveness / ring rate, plus the
room the bombs take. The quota is steep on purpose: steep enough that length still climbs
while forgiveness falls. A low stage is roomy because it forgives a lot; a high one is long
because it asks a lot and spares nothing. (The original stage 1 is 607 frames.) If a curve
is changed, read the printed lengths again: they must still climb.

`QUOTAS = "original"` plays the game's own quotas instead.

### The marathon's difficulty

A number that creeps up with every section: `MARATHON_START` (2.0) plus `MARATHON_RAMP`
(0.5) a section, so a zone is a stage and a half harder than the last. It is read off the
same three curves -- between two stages it is in between them. Past 7 they carry on: what a
check asks keeps climbing without limit (`MARATHON_ASK_STEP`), the ring rate rises to a
ceiling (0.60), and forgiveness falls to a **floor of x1.02**, still over 1.0, so the
guarantee holds at section 500 exactly as at section 1. Past 7 a zone takes its modules
from the original's later stages in rotation (`MARATHON_FLAVOURS`: 6, 7, 3, 5), so the run
changes character: bomb fields, ring storms, corkscrews, helixes.

## Things found out the hard way

* **Steer the corners.** A stage is 70-90 pieces, a marathon preview 224. Left to chance,
  three corners the same way drive the track back into its own start and it boxes itself
  in -- every one of the first forty tries did. `steer()` chooses each corner's direction so
  the track never heads more than a quarter turn from the way it set out: it wanders, but
  never turns back, so on the flat it cannot meet itself. The deck still decides *where*
  the corners are.
* **Deal modules, don't roll them** -- the same lesson as the track. A stage 1 straight has
  three bomb shapes among seventeen; rolled, one stage in ten had no bombs at all. Each kind
  of track has its own shuffled deck of the original's placements, the decks last the whole
  stage (a fresh deck per section is dice again), and the bomb cards are spread through a
  deck rather than left where the shuffle put them.
* **Count rings, cap bombs.** The ring rate gates on rings; a bomb shape costs no
  allowance, so uncapped it is dealt over and over (stage 6 came out with 1,175 bombs to the
  original's 304; one wall is sixteen). Bombs are held to the original stage's own bombs per
  ring.
* A parameter called `names` and a local called `names` in `generate()`: the plan handed in
  was thrown away and a 14-piece level dealt instead. It is `plan_names` now.

## Not done yet

* **The engine side**: doing this at runtime in Octave, with only the next few pieces and
  modules alive. The `.json` is the contract.
* **The palettes** the marathon shifts between: skies (several exist, see `skies.md`) and
  pipe colours.
* **The reachability check**: run the best line through a stage and confirm the rings that
  can actually be *collected* beat the quota. The guarantee above counts rings that exist;
  rings overhead or behind a bomb wall are harder to get than their number says.
* **Carry-over** is ignored on purpose: a section can be passed from nothing. Rings kept
  from earlier sections only make it easier.
* **Speed** is not in here at all; how long 2,312 frames takes to run is the engine's.
