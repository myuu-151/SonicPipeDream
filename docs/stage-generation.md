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
  each third check **the palette shifts**: a new sky, new colours on the pipe (see Colours,
  below). Each shift has a `PaletteShift_NN` empty in the `.blend` and a `palette_seed` in
  the `.json`, so the same run shifts the same way every time.

In the `.blend`: a `Level` collection (the pieces, each tagged with its section, and
`Level_Path`), then one collection per section -- `Section01` ... -- holding its own spline
`Section01_Path`, a root empty per module (`S01_M03`, at the module's first frame, with its
rings and bombs parented to it, so a whole shape moves as one), the check (`Check_01`, or
`Emerald`), and the ring check's other markers, below.

## The intro, the ring check, the ending

Three stretches of plain straight track that the deck does not deal; they are laid on
purpose, and nothing is ever put on them.

**The intro** and **the ending** are each **as long as a ring check** -- the owner's rule --
and are worked out from `CHECK_LENGTH` in the code, so the three cannot drift apart:
lengthen the check and they follow. The intro is 8 straights (64 frames, about 320 units)
laid before anything the deck deals, so a stage never starts on a bend, and nothing is put
on it. (The original opens on three straight segments and about 80 empty frames.)

**The ring check.** Measured from the original: every one of its checks sits on a run of
three or four straights, its rings and bombs stop 15-20 frames short, and then there is
**nothing at all for about 48 frames** (36 to 63). That empty run is not padding -- it is
where the check *plays*: the logo drops in at the top of the screen, the count is taken,
and on a pass the camera swings round to Sonic and he gives the thumbs up (`RunThumbsUp`)
before the next section starts. So every section ends in a **ring check zone**:
`CHECK_RUN_UP` (2) straights, the check, then `CHECK_PLAYS` (6) straights -- 64 frames, about
320 units. Lengthen `CHECK_PLAYS` if the real sequence needs longer; it is one number.

The script only keeps the room and marks it. The logo, the camera and the animation are
the engine's. In the `.blend`, per section:

| Object | What it marks |
|---|---|
| `L045_RingCheck02` ... | the zone's pieces, tagged `ring_check` |
| `Check_02` (or `Emerald`) | where the count is taken |
| `CheckLogo_02` | above the pipe there: where the logo belongs |
| `CheckPass_02` | the end of the zone: the pass plays from the check to here |
| `RingsToGo_02` | the "rings to go" call, 64 frames before the check |

and in the `.json` each section has `ring_check` with its first, check and last frame.

**The ending.** The pipe does not stop at the emerald. The emerald gets a longer approach
(`EMERALD_RUN_UP`, 3 straights; the original's is 24-39 frames) and the track runs straight
on past it for a check's length, 8 more, named `L..._Ending`, so a stage ends on track and
not on a sawn-off pipe. The original's layouts carry about four more segments than their
object lists for the same reason.

## Colours -- `native/stage_palettes.py`

**Every stage has its own pipe colour**, and they are the original's. `art/palettes/Special
Stage 1.bin` ... `7.bin` in the disassembly are 32 bytes each: sixteen Mega Drive colours,
loaded as the fourth palette line over a main palette all seven stages share. Decoded, the
line has the same plain structure in every stage:

| Slots | What | |
|---|---|---|
| 1, 3, 6 | the pipe's own colour: light, mid, dark | differs per stage |
| 2, 4, 5 | the trim colour (stripes, hoops): light, mid, dark | differs per stage |
| 7 - F | yellows, greys, white: rings and text | the same in all seven |

so a stage's look is two colours, three shades each:

| Stage | Pipe | Trim | Sky (ours) |
|---|---|---|---|
| 1 | cyan `00B6DB` | orange | 0 Classic |
| 2 | magenta `DB0092` | deep orange | 4 Sunset |
| 3 | red-orange `DB4900` | orange | 6 Inferno |
| 4 | cream `DBDBB6` | orange | 2 Dawn |
| 5 | orange `FF9200` | **green** `00FF49` | 5 Aurora |
| 6 | green `6DB600` | orange | 3 Pastel |
| 7 | grey `929292` | lavender `B6B6DB` | 7 Noir |

**What is ours.** The original's pipe is a flat drawing in those six shades; ours is a lit
3D model with seven materials, so which slot colours which material is a choice -- `ROLES`:
the pipe takes slot 1, the floor stripes slot 2, the hoop and the arch of spheres slot 4,
the decks slot 5, the rails the shared yellow, and the paler patch in each stripe is the
stripe colour lifted toward white. All three shades of both colours are in the `.json`
(`pipe_shades`, `trim_shades`) in case the engine wants to band the pipe as the original
does. **The sky is ours entirely** -- the original's is a black starfield in every stage --
so `SKY` pairs each stage with the one of the project's eight skies (`skies.md`) that sits
best behind its pipe. It is only *named* in the stage files: the skies are Octave's
textures, not Blender's. Midnight (1) is left over. Both tables are to be changed by eye.

**How a stage is recoloured.** The five baked piece meshes are shared by every piece in a
level, so the colour cannot live on the mesh. Each piece's material slots are switched to
belong to the *object* and pointed at that palette's copy of the material (`HP_Pipe_S2`
...): one set of copies per palette, however many pieces wear it. That is also how **the
marathon changes colour zone by zone inside one file**: each zone draws one of the seven
at random, never the same twice running, and the pieces after a `PaletteShift_NN` wear
the next. Each section in the `.json` carries its `palette`, and `palettes` holds all seven.

## Variety

The first version dealt a stage only what the original stage of the same number put down,
and that is very little: **stage 1 has six kinds of shape**, stage 5 has eight and
twenty-five of its forty-one are the same big triangle, and **29 of the 93 modules could
never come up at all** -- the single spiral and the snake line among them -- because the
original never placed them on their own. The owner noticed before any count did. Now:

* **Tier.** Every module has one: the first original stage it appears in, which is the
  original's own order of teaching shapes. A stage may use every tier up to its own, and a
  few cards of the *next* tier as a taste of what is coming.
* **Weight.** The stage's own placements count three times, so it keeps its character;
  earlier stages' and the next tier's once.
* **Damping.** A shape the original used *n* times gets about sqrt(*n*) cards, not *n*.
  Stage 5 is still the big-triangle stage; it is no longer only that.
* **Library.** Modules the original never placed on their own get a tier by hand
  (`LIBRARY_TIER`) and are put where the original puts things: the floor, or up either wall.

Stage 1 went from 6 kinds of shape to 19, and the count climbs with the stages to 59 in stage 7. Every run prints the kinds it used, and they are
in the `.json` as `kinds`.

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

| Stage | `QUOTA` (three checks) | `FORGIVENESS` | `RING_RATE` | comes out as | kinds of shape |
|---|---|---|---|---|---|
| 1 | 30 / 70 / 130 | x2.2 | 0.34 | 105 pieces, 1,368 frames | 19 |
| 2 | 40 / 90 / 170 | x2.0 | 0.38 | 103 pieces, 1,456 frames | 27 |
| 3 | 50 / 115 / 210 | x1.8 | 0.41 | 111 pieces, 1,784 frames | 42 |
| 4 | 70 / 160 / 290 | x1.6 | 0.45 | 106 pieces, 1,760 frames | 41 |
| 5 | 90 / 210 / 380 | x1.4 | 0.49 | 110 pieces, 1,904 frames | 36 |
| 6 | 110 / 260 / 480 | x1.2 | 0.52 | 123 pieces, 2,208 frames | 45 |
| 7 | 140 / 320 / 600 | x1.05 | 0.56 | 123 pieces, 2,568 frames | 59 |

**Length is not set anywhere.** It falls out as quota x forgiveness / ring rate, plus the
room the bombs take. The quota is steep on purpose: steep enough that length still climbs
while forgiveness falls. A low stage is roomy because it forgives a lot; a high one is long
because it asks a lot and spares nothing. (The original stage 1 is 607 frames. About 200 frames of each of ours is intro, ring checks and ending.) If a curve
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
* **The skies at a palette shift** are named per palette but switching them is the
  engine's: set `sky` on the SkyDome (`skies.md`). Only the seven original palettes exist;
  a marathon that should never repeat a look will want more, made to the same two-colour,
  three-shade pattern.
* **The reachability check**: run the best line through a stage and confirm the rings that
  can actually be *collected* beat the quota. The guarantee above counts rings that exist;
  rings overhead or behind a bomb wall are harder to get than their number says.
* **Carry-over** is ignored on purpose: a section can be passed from nothing. Rings kept
  from earlier sections only make it easier.
* **Speed** is not in here at all; how long 2,312 frames takes to run is the engine's.
