# Procedural generation: how a level gets made

How `native/gen_random_level.py` turns three hand-shaped track pieces, a difficulty and
a seed into a level. For *why* the project works this way at all, read
[procedural-stages.md](procedural-stages.md) first; this is the how.

## Run it

    blender -b external/halfpipe/TrackPiecesPack.blend \
        --python native/gen_random_level.py -- <out.blend> [difficulty 1-7] [seed]

    # difficulty 3, seed 1
    ... -- external/halfpipe/RandomLevel_d3_seed1.blend 3 1

The same difficulty and seed always give the same level. It prints the level as a
string, which is the quickest way to see what it made:

    S straight   L corner left   R corner right   D drop   U rise

| Level | Layout |
|---|---|
| difficulty 1, seed 1 | `S S R S R S L S L S D S S S` |
| difficulty 3, seed 1 | `S S U S R L S L D S R S R S S L R S` |
| difficulty 3, seed 2 | `S S L S L R D S L S L S S D S R L S` |
| difficulty 7, seed 1 | `S S R L R D R L R L U L R R L S L R D R U D U L R L L S` |

## 1. The pieces: three shapes, five pieces

`TrackPiecesPack.blend` holds three authored pieces. Each is a curve (`TP_...`) with the
real half-pipe on it (`TPM_..._Pipe`, `_Rails`, `_Spheres`), bent along that curve.

| Authored | Length | What it is |
|---|---|---|
| `TP_Straight` | 1 section (40.161) | straight and level |
| `TP_Corner` | 3 sections | half a section straight, 90 degrees across two sections, half a section straight |
| `TP_LongDrop` | 6 sections | a chute: tips over, holds 50 degrees, settles, flat run-off; falls 132 |

Because the pieces are modular, those three give the generator five:

| Piece | How it is made |
|---|---|
| Straight | as authored |
| CornerRight | as authored |
| CornerLeft | CornerRight mirrored, with its faces turned back the right way |
| Drop | as authored |
| Rise | the drop's curve turned upside down, with the pipe bent along it afresh |

An S-bend is not a piece. It is a left corner followed by a right one.

**The joint** is what makes any piece follow any other: a piece starts at its origin
heading +X and level, and **ends level**. Where it ends and which way it then heads are
measured from the curve, so reshaping a piece in Blender needs no change here.

## 2. Baking

Each piece is baked **once** into a single self-contained mesh: pipe, rails and arches
joined, with the Mirror, Array and Curve modifiers applied (`PM_Straight`,
`PM_CornerRight`, `PM_CornerLeft`, `PM_Drop`, `PM_Rise`). A level is then nothing but
those meshes set down end to end, **one rigid transform each**.

That is deliberate. It is exactly what the engine will do at runtime, with only the next
few pieces alive -- so what is looked at in Blender is what will run, and a level costs
five meshes however long it is.

## 3. The deck: dealt, not rolled

The obvious generator rolls a die for every piece. It was built that way first, and it
is wrong: independent rolls only meet the rulebook *on average*. Difficulty 3, seed 1
rolled high nine times running and produced **fifteen straights out of eighteen**. The
same luck the other way is how an easy level turns hard.

So a level is **dealt from a deck**:

1. **Fix the mix.** From the difficulty's row: so many corners, so many hills, the rest
   straights. Difficulty 3 is always 7 corners, 2 hills, 9 straights.
2. **Make the events.** Corners are dealt singly or, by the row's `snake` chance, in
   opposite pairs as S-bends. Hills are drops or, by `rise`, rises. Shuffle them.
3. **Place the straights the rules demand:** two to open the level, a `rest` after every
   hill, one to break up any run of corners longer than `chain`, one to close.
4. **Scatter the straights left over** into the gaps at random.

Every level has exactly its difficulty's mix; only the *arrangement* is random. That is
what makes "level 1 can never get too hard" a guarantee rather than a likelihood.

## 4. The rulebook

"AI difficulty" is this table, not a learned model. A row is a set of limits.

| Difficulty | pieces | turn | snake | hill | rise | rest | chain |
|---|---|---|---|---|---|---|---|
| 1 | 14 | 0.25 | 0.00 | 0.08 | 0.0 | 2 | 1 |
| 2 | 16 | 0.32 | 0.10 | 0.10 | 0.2 | 2 | 1 |
| 3 | 18 | 0.40 | 0.20 | 0.12 | 0.3 | 1 | 2 |
| 4 | 20 | 0.46 | 0.30 | 0.14 | 0.4 | 1 | 2 |
| 5 | 22 | 0.52 | 0.40 | 0.16 | 0.4 | 1 | 3 |
| 6 | 24 | 0.58 | 0.50 | 0.18 | 0.5 | 1 | 3 |
| 7 | 28 | 0.64 | 0.60 | 0.20 | 0.5 | 0 | 4 |

* **pieces** -- how long the level is
* **turn** -- the share of pieces that are corners
* **snake** -- the chance a corner is dealt as an S-bend
* **hill** -- the share that are drops or rises; always at least one
* **rise** -- of the hills, the chance one goes up. Level 1 never climbs.
* **rest** -- straights forced after a hill, to recover on
* **chain** -- most corners allowed back to back; an S-bend counts as two

These numbers are a first guess. They should be measured from the seven original stages
(already decoded, see [s2-special-stage-layouts.md](s2-special-stage-layouts.md)) so that
generated level 3 plays like the original's stage 3.

## 5. Not running into itself

Four 90 degree corners the same way on the level is a closed square, so a generated
track can drive into its own start. As each piece is laid, points along it are tested
against everything laid earlier (the last three pieces are neighbours, not collisions).
Coming within **45 units** of an earlier part at a height within **35** counts as a hit;
the pipe is about 29 wide, and parts further apart in height pass over and under.

A piece that would hit is swapped for the nearest thing that fits, tried in order:

| Wanted | Tried instead |
|---|---|
| a corner | the other corner, a drop (to pass underneath), a straight |
| a straight | a drop, either corner |
| a hill | a drop, a straight, either corner |

Every swap is printed, because it changes the mix the deck promised. If nothing fits,
the level ends there and says so. None of the four example levels needed a swap.

Drops earn their keep here: a drop puts the track 132 lower, where it can cross under
itself, so descending is what buys a level more turning.

## 6. What it writes

A new `.blend` with a `Level` collection: one object per piece (`L00_Straight`,
`L01_CornerLeft`, ...) all sharing the five baked meshes; `Level_Path`, the centre line
as a curve, for whatever has to follow the track; and a camera standing in the pipe at
the start. The pack file is read, never written.

## Known rough edges

* **The rise used to be the baked drop travelled backwards**, which is the same shape and
  wrong in everything that has a direction: the floor's arrows pointed at the player, and
  each section's rail was at its near end. No turning or mirroring of that mesh can fix it --
  the markings are part of it. `make_rise()` now turns the drop's *curve* upside down and
  bends the pipe along it like any other piece, in memory (the pack is never written).
* **Triangles.** A straight is 3,536 and a drop 21,216, most of it the sphere arches at
  864 each. Fine on Windows; the first thing to thin for a GameCube.
* **One corner angle.** 90 degrees only. A gentler corner is one more shape in the pack
  and a line in the generator.

## Next

1. **Rings and bombs** as patterns laid on pieces: spiral, row, arc, bomb wall, with
   their own columns in the rulebook (which patterns a level may use, bomb density,
   ring surplus over the quota).
2. **The reachability check:** run the best line through a generated level and confirm
   the rings that can be collected beat the quota by the level's margin; reroll if not.
3. **Calibrate the rulebook** from the original stages.
4. **The engine side:** the same deal-and-lay at runtime in Octave, from the five baked
   meshes, keeping only the next few pieces alive.
