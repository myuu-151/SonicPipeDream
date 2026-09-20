# Sonic 2 special stage rings and bombs

Where the original game keeps its rings and bombs, what shapes it makes out of them, and
how this project turns those shapes into **ring modules**. The companion to
[s2-special-stage-layouts.md](s2-special-stage-layouts.md), which does the same for the track.

## Source

`misc/Special stage object location lists.kos` in Sonic Retro's s2disasm, Kosinski-compressed,
3,216 bytes. A copy is kept at `docs/reference/` (Sega's data: it comes out before this repo
is ever public, like the layouts file).

    python native/kosinski.py "docs/reference/Special stage object location lists.kos" objects.bin
    python native/s2_objects.py        # a summary of all seven stages
    python native/s2_objects.py 5      # stage 5 drawn as maps, a row per track frame

## Format

Decompressed it is 6,880 bytes: seven big-endian words giving each stage's offset, then a
list per track segment, read by `SSObjectsManager` in `s2.asm` each time a new segment starts.

    byte 1   bits 0-5   how far into the segment, in track frames
             bit 6      set = bomb, clear = ring
    byte 2              angle round the pipe, 256ths of a circle

A byte with bit 7 set ends the segment's list:

| Byte | Meaning |
|---|---|
| `FF` | end of the segment, nothing more |
| `FE` | end, and this is a checkpoint |
| `FD` | end, and this is the emerald: nothing is read after it |
| `FC` | end, and show the "rings to go" message |

Every stage has exactly two checkpoints and an emerald, each preceded a few segments earlier
by an `FC`. The lists stop at the emerald, so they cover a few segments fewer than the track
layout has (stage 1: 42 of 46).

**Angle `$40` is the floor's centre line.** Everything in the data is symmetrical about it:
the commonest ring shape is `40 / 38 48 / 38 48 / 38 48 / 40`. `$00` and `$80` are the two
rims, and `$80`-`$FF` is the half of the circle above the pipe -- the game does put rings and
bombs there, where only a jump, or speed round the wall, reaches them.

**Not in the data:** which rim `$00` is. `ring_modules.py` has `ANGLE_00_SIDE = "right"`. Every
module is either symmetrical or comes as a left/right pair, so nothing depends on it yet.

**Spacing.** One frame along the track is a straight piece / 16 = 2.51 units here. The game's
grid round the pipe is 8 (11.25 degrees) between neighbours in staggered rows, 16 within a row.

## What the seven stages hold

| Stage | Segments | Rings | Bombs |
|---|---|---|---|
| 1 | 42 | 206 | 16 |
| 2 | 40 | 260 | 80 |
| 3 | 42 | 205 | 286 |
| 4 | 52 | 252 | 142 |
| 5 | 41 | 403 | 44 |
| 6 | 59 | 342 | 304 |
| 7 | 50 | 492 | 225 |

Bombs do not climb evenly: 3 and 6 are the bomb stages, 5 and 7 the ring feasts.

## The safeguard -- `native/check_ring_coverage.py`

    python native/check_ring_coverage.py        # exit status 0 = nothing is missing

Whether a type is missing is not a matter of anyone's memory. This script lays all seven
original stages out end to end and **rebuilds them out of the modules**: any module, at any
frame, at any angle, either way round. Whatever no module accounts for is *left over*, and
is drawn and printed as a row ready to paste into `MODULES`.

As it stands: **3,250 objects, 0 left over.** Run it after any change to the table.

Three rules keep it honest:

* **Singles are not cover.** `Bomb` would otherwise explain every bomb in the game. A lone
  ring or bomb only passes where nothing else of its kind is near it.
* **Runs.** A line, a zigzag, a weave, a wave, a sweep, a helix, a corkscrew: the game cuts
  these to whatever length it has room for (corkscrews of 16, 23 and 24; hooks of 13 and
  15). The *type* is the run, so `ring_modules.RUNS` holds each at full length and any
  stretch of three frames or more counts. The named modules are the cuts worth naming.
* **Oddities.** Two places where the original data looks like a slip of the hand -- a
  `TriangleSmall` with its point 8 off-centre in stage 2, a `BombCluster` with its rows
  shuffled in stage 7 -- are let through by name in `ODDITIES`, not made into types.

The first run of it found 209 objects the hand-made table had missed, which is the argument
for having it: other corkscrew lengths, the second phase of the wave, gapped small and long
clusters, a wrongly spaced `BombClusterTight` (6 apart, not 8), a ring missing from
`HookToWall`, and a mis-transcribed `Confetti` whose two halves differ by one unit.

The other half of the safeguard is that the original placements themselves are kept
(`s2_objects.stages()`), so a classic stage can always be laid exactly as the game has it,
modules or no modules.

## The vocabulary

Grouping touching objects into shapes and counting them across all seven stages gives a small
vocabulary, used over and over. This is what the modules are made from. (`x` = times used;
exact for the clusters and triangles, near enough for the rows and spirals, which the
grouping splits differently depending on their spacing.)

| Shape | Objects | x | Module |
|---|---|---|---|
| 1, 2, 1 | 4 rings | 46 | `ClusterSmall` |
| 1, 2, 2, 1 | 6 | 17 | `ClusterMedium` |
| 1, 2, 2, 2, 1 | 8 | 47 | `Cluster` -- the staple |
| 1, 2 x4, 1 | 10 | 9 | `ClusterLong` |
| 1, 2 x5 .. x7, 1 | 12, 14, 16 | 5 | `ClusterLong12`, `ClusterLonger`, `ClusterLongest` |
| 1, 2, 3, 2, 1 | 9 | 7 | `ClusterBig` |
| small clusters every 4 frames, stepping 16 across | 12, 24 | 2 | `ClusterStairs` -- stage 2 |
| 2, 1 | 3 | 13 | `TriangleSmall` |
| 3, 2, 1 | 6 | 8 | `Triangle` |
| 4, 3, 2, 1 | 10 | 33 | `TriangleBig` |
| 5, 4, 3, 2, 1 | 15 | 1 | `TriangleHuge` -- stage 4's last shape |
| 1, 2, 5 | 8 | 1 | `Arrowhead` -- stage 4 |
| one a frame, alternating 8 apart | 8 | ~25 | `Zigzag` -- most of stage 1 |
| 2, 1, 2, 1 ... | 9, 12 | 13 | `WeaveShort`, `Weave` |
| a straight line down the floor | 3-10 | 5 | `Line`, `LineLong` |
| a line with every other frame empty | 5 | 1 | `LineDotted` -- stage 4 |
| three abreast, 8 apart | 3 | 2 | `Row3` |
| slides across 4 a frame, holds, slides back | 13-16 | 6 | `SweepLeft`, `SweepRight` -- stage 3, in pairs |
| slides across and stays there | 13-15 | 4 | `HookLeft`, `HookRight` -- stage 3 |
| one strand swinging side to side, 8 a frame | 15, 16 | 2 | `Wave` -- stage 6 |
| a straight diagonal | 6 | 2 | `Slant` |
| two strands crossing, right round the pipe | 30 | 5 | `Helix` -- stage 5 |
| half of that: floor to overhead, or back | 16 | 2 | `HelixUp`, `HelixDown` |
| two strands out to the rims and back | 17 | 1 | `HelixBounce` -- leads into stage 5's helix |
| 2 a frame thrown all round the pipe, 20 frames | 40 | 6 | `Confetti` -- stage 7 |
| one bomb | 1 | 83 | `Bomb` |
| 1, 2, 1 of bombs | 4 | 78 | `BombCluster` -- the staple |
| 1, 2, 2, 1 | 6 | 16 | `BombClusterLong` |
| 1, 2, 2 (hollow), 2, 1 | 8 | 3 | `BombDiamond` |
| 3 or 5 abreast | 3, 5 | 7 | `BombRow3`, `BombRow5` |
| 1, 2 | 3 | 5 | `BombChevron` |
| sixteen right round the pipe in one frame | 16 | 20 | `BombWall` -- jump it |
| the same with a gap of 3 or 4 | 13, 12 | 5 | `BombGate`, `BombGateWide` |
| one strand winding round, 8 a frame | 16-24 | 5 | `BombCorkscrew` -- stage 3 |
| the same at 16 a frame: right round in one straight | 16 | 1 | `BombSpiral` |
| a diagonal of bombs | 10 | 2 | `BombSlant` |
| two diagonals closing on the centre | 20 | 1 | `BombFunnel` -- stage 3 |

### Rings and bombs together

The game also pairs shapes in one segment often enough that the pairs are modules too:

| Module | What it is | From |
|---|---|---|
| `Slalom` | a `Wave` of rings winding round two `BombCluster`s | stage 6 |
| `LineInCorkscrew` | a `LineLong` down the floor while a `BombCorkscrew` passes overhead | stage 3 |
| `HookToWallLeft`, `-Right` | a hook of rings that leads up the wall and into a `BombWall` | stage 3 |
| `WeaveByBombs` | a `Weave` on one wall, single bombs down the centre line | stage 4 |
| `GateAndTriangle` | a `BombGateWide`, then a `TriangleBig` off to one side of the gap | stage 4 |

| `WallThenCluster` | a `BombWall` with a `Cluster` two frames behind it: jump, and land in rings | stages 3, 6 |
| `ChevronSlantLeft`, `-Right` | a `BombChevron`, then a `Slant` of rings leading away from it | stage 3 |
| `TwinBombsAndCluster` | `BombTwin` on the walls, a `Cluster` between them | stage 1's one hazard |
| `Gauntlet` | a long cluster down the floor with `BombTwin` closing in beside it | stage 3 |
| `SwapWalls`, `SwapWallsMedium` | rings on one wall and bombs on the other, then they change places | stages 6, 7 |
| `SwapThree` | bomb, ring, bomb abreast; then ring, bomb, ring | stage 6 |
| `ClusterByBombs` | clusters on alternate walls, single bombs down the centre every 4 frames | most of early stage 7 |

### Arrangements

A second pass, reading all 135 distinct segments by eye rather than trusting the matcher,
showed that much of what makes a stage look like Sonic 2 is not a new shape but the same
shape **placed more than once**. These are modules too:

| Module | What it is | From |
|---|---|---|
| `TwinClusterSmall`, `BombTwin` | the same small cluster on both walls at once (`$10` and `$70`); `BombTwin` is used 12 times | all stages |
| `BombTwinNear` | the same, closer in (`$20` and `$60`) | stage 6 |
| `TwinOverhead` | a pair up over the pipe (`$A0` and `$E0`): only a jump reaches them | stage 2 |
| `ClusterCascade` | floor, then both walls, then overhead, 4 frames apart | stage 2 |
| `TwinTriangleRims` | a `TriangleBig` on each rim | stage 5 |
| `ClusterStairsLong` | six small clusters stepping right across the pipe | stage 2 |
| `TriangleTrain`, `TriangleSnake` | `TriangleSmall` every 4 frames; straight, or snaking out to the wall and back | stage 2 |
| `TriangleWeave` | three `Triangle`s 8 frames apart, alternating sides | stage 1 |
| `BombTrain`, `BombDots` | bomb clusters every 8 frames; single bombs every 4 | stages 2, 4, 7 |
| `ClusterSmallGapped`, `ClusterGapped`, `ClusterLong12Gapped`, `ClusterSparse` | a `Cluster` with a frame left empty after its first ring, or between every row | stages 3, 6, 7 |
| `BombClusterTight` | stage 2's own bomb cluster, `40 / 3A 46 / 40`: 6 apart, not 8 | stage 2 |
| `DottedArrow` | dotted line, two rows of three, one: stage 4's opening shape | stage 4 |

`twin(module, apart)`, `train(shape, angles, every)` and `put(module, frame, angle)` build
these, and modules add with `+`, so a new arrangement is one line. 79 modules in all.

What is deliberately *not* a module: a shape simply put somewhere else (a `TriangleBig` on
a wall, or overhead as in stage 5), which is the `at` angle's job when a level is laid; other
lengths of `Line`, `Hook` and `ClusterLong`; and one skewed bomb cluster in stage 7 that
looks like a slip in the original data.

Things worth knowing when laying them:

* **Triangles point away from the player**: the wide row comes first and they narrow to one,
  funnelling the player to the point.
* **Where they are put.** Clusters sit at `$40` (centre) or on the walls at `$10/$18/$20` and
  `$60/$68/$70`. Bomb clusters also sit *on the rims* (`$00`, `$80`), to punish running wide.
* **Rings and bombs share a segment.** The classic: a `Line` of rings down the centre with a
  `BombCorkscrew` winding round it; a `BombGate` with a `TriangleBig` just behind the gap.
* **Rhythm.** Shapes start at frame 0 or 8 of a segment, three triangles to a 24-frame
  segment at 0, 8, 16. A straight takes one `Cluster` or one `Zigzag`, seldom more.

## The modules -- `native/ring_modules.py`

Pure Python, no Blender. A module is a list of `(frame, angle, kind)` with the angle
**relative to where the module is put**: put `Cluster` at 0 and it is on the centre line, at
-40 and it is on one wall. Shapes come from small rules (`capsule`, `diamond`, `triangle`,
`zigzag`, `weave`, `sweep`, `helix`, `corkscrew`, `wall`), so a new size is one line in the
`MODULES` table. `local(frame, angle, at)` gives an object's place on a straight piece; on a
bent piece the same numbers are distance along the piece's curve and offsets in the curve's
frame.

    python native/ring_modules.py      # every module drawn as text, with its counts

**Chosen, because the game has nothing to say:** `HOVER = 1.9`, a ring's centre above the
pipe's surface; ring size, which is `gen_ring.py`'s; and `RING_SCALE` in the preview. At
scale 1.0 two rings 8 apart nearly touch; past about 1.25 they overlap.

## Looking at them -- `native/gen_ring_modules.py`

    blender -b external/halfpipe/TrackPiecesPack.blend \
        --python native/gen_ring_modules.py -- sheet
    python native/make_ring_sheet.py

Writes `external/ring/RingModules.blend`: one lane of pipe per module, a collection
`RM_<name>` each, with an empty at the module's start (floor centre line, heading +X -- the
same joint as a track piece) and the rings parented to it, all sharing the one `Ring` mesh.
`sheet` also renders every module; the second command gathers them into
`external/ring/RingModules_sheet.png`.

There is no bomb model yet: `Bomb_Placeholder` is a dark ball.

## Not done yet

* **Laying modules on a level.** `gen_random_level.py` still deals track only. Next: deal
  modules onto pieces from their own rulebook columns (which modules a difficulty may use,
  bomb share, ring surplus over the quota), riding `Level_Path`.
* **Calibrating that rulebook** from the table above and the per-stage counts.
* **Classic stages.** The original placements can be played back as they are -- they are
  raw positions, and `s2_objects.stages()` already returns them.
* **A bomb model**, and the engine side.
