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
| 1, 2 x5 .. x7, 1 | 12-16 | 4 | `ClusterLonger` (14) |
| 1, 2, 3, 2, 1 | 9 | 7 | `ClusterBig` |
| 2, 1 | 3 | 13 | `TriangleSmall` |
| 3, 2, 1 | 6 | 8 | `Triangle` |
| 4, 3, 2, 1 | 10 | 33 | `TriangleBig` |
| 5, 4, 3, 2, 1 | 15 | 1 | `TriangleHuge` -- stage 4's last shape |
| one a frame, alternating 8 apart | 8 | ~25 | `Zigzag` -- most of stage 1 |
| 2, 1, 2, 1 ... | 9, 12 | 13 | `Weave` |
| a straight line down the floor | 3-10 | 4 | `Line`, `LineLong` |
| slides across 4 a frame, holds, slides back | 13-16 | 6 | `SweepLeft`, `SweepRight` -- stage 3, in pairs |
| a straight diagonal | 6 | 2 | `Slant` |
| two strands crossing, right round the pipe | 30 | 5 | `Helix` -- stage 5 |
| 2 a frame thrown all round the pipe, 10-frame repeat | 20 | 6 | `Confetti` -- stage 7 |
| one bomb | 1 | 83 | `Bomb` |
| 1, 2, 1 of bombs | 4 | 78 | `BombCluster` -- the staple |
| 1, 2, 2, 1 | 6 | 16 | `BombClusterLong` |
| 1, 2, 2 (hollow), 2, 1 | 8 | 3 | `BombDiamond` |
| 3 or 5 abreast | 3, 5 | 7 | `BombRow3`, `BombRow5` |
| 1, 2 | 3 | 5 | `BombChevron` |
| sixteen right round the pipe in one frame | 16 | 20 | `BombWall` -- jump it |
| the same with a gap | 12, 13 | 5 | `BombGate` |
| one strand winding round, 8 a frame | 16-24 | 5 | `BombCorkscrew` -- stage 3 |
| a diagonal of bombs | 10 | 2 | `BombSlant` |

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
