# Sonic 2 special stage track layouts

How the original game describes its special stage tracks, where that data comes
from, and how this project turns it into a 3D curve. Written so a later session
does not have to rediscover it.

## Source

Sonic Retro's community disassembly of Sonic 2: <https://github.com/sonicretro/s2disasm>

| File there | What it is |
|---|---|
| `misc/Special stage level layouts.nem` | the track layouts for all 7 stages, Nemesis-compressed, 260 bytes |
| `misc/Special stage object location lists.kos` | where rings and bombs sit, Kosinski-compressed. **Not decoded yet.** |
| `misc/Special stage object perspective data.kos` | how objects are placed on screen per track frame. Not needed for a real 3D track. |

Also useful: flamewing's special stage editor, <https://github.com/flamewing/s2ssedit>, whose README states the orientation rules independently.
| `s2.asm` | the annotated source; search `Ani_SpecialStageTrack` and `SSTrack_Orientation` |

A copy of the layout file is kept at `docs/reference/Special stage level layouts.nem`
and `native/nemesis.py` decompresses it:

    python native/nemesis.py "docs/reference/Special stage level layouts.nem" layouts.bin

That file is Sega's data, taken from the disassembly. It is here as reference in
a private repo; it, like the Sonic model under `external/sonic/`, should come out
before this repo is ever made public.

## The track is not 3D

The original track is pre-rendered animation. There is no model, so the data holds
**no measurements at all** -- no turn radius, no slope, no width. What it holds is
a *sequence*: each stage is a list of segments, and each segment is one of five
canned animations.

| Type | Segment | Frames | Made of |
|---|---|---|---|
| 0 | turn, then rise | 24 | 7 turning + 17 rising |
| 1 | turn, then drop | 24 | 7 turning + 17 dropping |
| 2 | turn, then straighten out | 12 | 7 turning + 5 leaving the turn |
| 3 | straight | 16 | 4 straight frames, played 4 times |
| 4 | straight, then enter a turn | 11 | 4 straight + 7 entering the turn |

(From `Ani_SpecialStageTrack` in `s2.asm`.) Because every frame moves the player the
same distance, those frame counts are the segments' real relative lengths.

## Layout format

Decompressed, the file is 384 bytes: seven big-endian words giving each stage's
offset, then one byte per segment.

    bits 0-6   segment type, 0-4
    bit 7      mirror flag ($80): the segment is drawn flipped left-to-right

Every byte in the file is one of the five types, with or without the flag, which is
also the check that a decompressor is working.

### When the mirror flag takes effect

Not immediately. The game only re-reads the flag on frames where the track is drawn
head-on, so that the flip cannot be seen happening; between those frames the track
keeps whatever direction it had. From the `SSTrack_Orientation` code:

| In a... | the flag is read on |
|---|---|
| straight (3), and the straight part of type 4 | straight frame 2 |
| turn-then-rise (0) | rise frame 14 |
| turn-then-drop (1) | drop frame 6 |
| turn-then-straighten (2) | never: it inherits |

So a turn's direction is set by the straight *before* it. `04 02` (enter a turn,
turn, straighten) turns whichever way the `04` said.

**Not in the data:** which way an *unmirrored* turn goes. `gen_s2_track.py` has it as
`UNMIRRORED_TURNS = "right"`, from memory of the game. If stage 1's first turn should
go left, flip that one constant and every stage mirrors correctly.

## All seven stages

| Stage | Segments | Frames | Bytes |
|---|---|---|---|
| 1 | 46 | 679 | `03 03 03 04 02 03 03 03 03 03 03 04 02 03 03 03 03 04 00 02 03 03 04 81 02 03 03 04 02 03 04 02 03 84 02 03 04 02 83 84 02 03 03 03 03 00` |
| 2 | 44 | 731 | `03 03 03 04 02 03 03 04 00 80 00 00 02 03 03 03 03 03 03 03 03 04 01 02 03 83 03 03 03 04 02 03 04 01 00 80 81 02 03 03 03 03 03 03` |
| 3 | 44 | 780 | `03 83 83 84 02 03 03 03 03 03 03 03 03 04 81 80 81 02 03 03 03 04 80 00 01 80 00 81 02 03 03 03 03 84 80 81 01 80 00 02 03 03 03 03` |
| 4 | 56 | 845 | `03 03 03 03 03 04 80 02 03 04 01 02 03 04 02 03 03 03 03 03 04 01 02 83 84 02 03 04 02 83 84 01 02 03 03 03 03 04 02 83 84 80 02 83 84 01 02 83 84 02 03 03 03 03 03 03` |
| 5 | 44 | 740 | `03 03 83 84 02 03 03 03 03 03 04 01 80 81 02 03 03 03 03 03 03 03 04 80 01 02 03 03 03 83 84 00 81 01 80 02 03 03 03 03 03 03 03 03` |
| 6 | 62 | 940 | `03 03 03 04 02 03 03 03 03 04 81 81 81 02 03 03 03 04 02 03 03 03 03 84 00 00 02 03 03 03 03 04 00 81 02 03 03 03 04 02 03 04 02 03 04 02 03 04 02 83 84 02 03 04 02 83 84 02 03 03 03 03` |
| 7 | 74 | 1316 | `03 03 03 04 02 03 03 03 04 81 00 80 00 02 03 83 84 00 02 03 03 03 83 84 81 02 03 03 03 04 80 02 03 03 03 03 03 04 01 01 01 01 01 01 01 80 80 80 02 03 03 03 03 03 03 00 00 00 03 03 03 04 80 02 03 03 03 03 03 04 01 01 01 01` |

Stage 7 runs to the end of the decompressed block, which is padded to whole 32-byte
tiles, so its last few bytes may be padding rather than track.

### Stage 1, segment by segment

| # | Byte | Segment | |
|---|---|---|---|
| 0 | `03` | straight |  |
| 1 | `03` | straight |  |
| 2 | `03` | straight |  |
| 3 | `04` | straight, then enter a turn |  |
| 4 | `02` | turn, then straighten out |  |
| 5 | `03` | straight |  |
| 6 | `03` | straight |  |
| 7 | `03` | straight |  |
| 8 | `03` | straight |  |
| 9 | `03` | straight |  |
| 10 | `03` | straight |  |
| 11 | `04` | straight, then enter a turn |  |
| 12 | `02` | turn, then straighten out |  |
| 13 | `03` | straight |  |
| 14 | `03` | straight |  |
| 15 | `03` | straight |  |
| 16 | `03` | straight |  |
| 17 | `04` | straight, then enter a turn |  |
| 18 | `00` | turn, then rise |  |
| 19 | `02` | turn, then straighten out |  |
| 20 | `03` | straight |  |
| 21 | `03` | straight |  |
| 22 | `04` | straight, then enter a turn |  |
| 23 | `81` | turn, then drop | mirrored |
| 24 | `02` | turn, then straighten out |  |
| 25 | `03` | straight |  |
| 26 | `03` | straight |  |
| 27 | `04` | straight, then enter a turn |  |
| 28 | `02` | turn, then straighten out |  |
| 29 | `03` | straight |  |
| 30 | `04` | straight, then enter a turn |  |
| 31 | `02` | turn, then straighten out |  |
| 32 | `03` | straight |  |
| 33 | `84` | straight, then enter a turn | mirrored |
| 34 | `02` | turn, then straighten out |  |
| 35 | `03` | straight |  |
| 36 | `04` | straight, then enter a turn |  |
| 37 | `02` | turn, then straighten out |  |
| 38 | `83` | straight | mirrored |
| 39 | `84` | straight, then enter a turn | mirrored |
| 40 | `02` | turn, then straighten out |  |
| 41 | `03` | straight |  |
| 42 | `03` | straight |  |
| 43 | `03` | straight |  |
| 44 | `03` | straight |  |
| 45 | `00` | turn, then rise |  |

## How a turn and a hill are paced: the background scroll tables

The layout says *what* each segment is. The only record of *how* a turn or a hill
unfolds frame by frame is the background scroll the game applies on each track frame
(`SSPlaneB_SetHorizOffset` and `SSTrack_SetVscroll`, with the amounts in `off_6DEE`).
Summed over a frame's five ticks:

| | Frames (within the segment) | Amount per frame |
|---|---|---|
| Turn (types 0, 1, 2) | 0-11 | 10, 22, 56 x8, 22, 10 |
| Rise (type 0) | 10-23 | 5, 5, 22, 56 x6, 44, 46, 34, 17, 3 |
| Drop (type 1) | 11-23 | 3, 17, 34, 46, 44, 56 x6, 22, 10 |

Each totals 512, which is a whole number of background wraps -- so the totals are
cosmetic and say nothing about real angles or heights. The **proportions** are what
matter, and `gen_s2_track.py` takes its pacing from them. Two things follow that are
easy to get wrong:

* **All of a turn happens in the twelve frames that begin with the turning frames**,
  ramping in, holding for eight frames, ramping out -- through whatever follows them
  (the start of a rise, a drop, or the exit frames).
* **The "enter a turn" frames of type 4 turn nothing.** On screen they show the bend
  arriving, not the track bending under the player.

### Which of types 0 and 1 goes up

Type 0 is a step **up**, type 1 a step **down**, and each is self-contained: the track
is level again by the end of the segment. This does not rest on the disassembly's
names. `SSCurveOffsets` shifts the player's sprite per track frame, and through a
type 0 it moves them *up* the screen (-10 ... -42) and then *down past neutral*
(+6 ... +18): the ground ahead curving up, then levelling at a crest. Type 1 is the
mirror image.

So stage 1 steps up at segment 18, runs four segments on the higher level, steps back
down at 23, and steps up again on its last segment. The pre-rendered view of the
raised stretch is identical to the flat, which is likely why the stage is remembered
as only having drops.

**But that is not what is built.** The project's owner, who knows the stage far
better than any reading of tables, is clear that special stage 1 never rises and only
drops, and that the drops are sizeable. So `gen_s2_track.py` has a `HILLS` setting and
it is set to `"all_down"`: every type 0 and type 1 is a drop. `"as_data"` builds what
the evidence above points to, `"inverted"` swaps the two. Whichever is chosen, the
pacing of each hill still comes from the game's table. If the question is ever
settled -- by decoding the track art, or by watching the stage with the segment
number on screen -- this is the one constant to change.

(An earlier reading took the one-way vertical background scroll to mean the track
*stays* tilted after a rise. `SSCurveOffsets`' two-phase shape rules that out.)

## Turning it into a curve: `native/gen_s2_track.py`

    blender -b external/halfpipe/HalfPipe_Scene12_curve.blend         --python native/gen_s2_track.py -- external/halfpipe/HalfPipe_Stage1_v3.blend 1

It rewrites the `HP_Track` curve that the pipe, rails and sphere arches are bent
along, and sets all three arrays to the number of sections the stage needs.

**Exact, from the game:** the order of segments, their relative lengths, where the
direction changes, and the frame-by-frame pacing of every turn, rise and drop.

**Chosen, because the game has nothing to say:**

| Constant | Value | Meaning |
|---|---|---|
| frame length | section / 16 | one `straight` segment is exactly one pipe section, so hoops and arches fall on the stage's own rhythm. That every frame covers equal ground is itself an assumption. |
| `TURN_DEG` | 60 | how far one turn turns, in all |
| `CLIMB` | 20 | height of one drop; its steepest frame is then about 60 degrees, a drop you cannot see over |
| `HILLS` | all_down | see above |
| `BANK_DEG` | 0 | lean into turns |
| `UNMIRRORED_TURNS` | right | not in the data; from memory of the game |

### The stage running into itself

A faithful layout can still collide with itself in 3D, because the original never
had geometry to collide. Stage 1 has nine turns one way and three the other, so the
whole stage winds round by six turns' worth.

Built level (`HILLS = "as_data"`, `CLIMB = 10`), that is a hard limit: 45 degrees per
turn stays 126 units clear, 50 degrees comes within 8 -- the late stage runs through
the opening straight.

Built as drops it is not. The stage descends 60 units over its length, so its late
parts pass *under* its early ones:

| per turn | closest the path comes to itself at similar height |
|---|---|
| 45 deg | 117 units |
| **60 deg** | **99 units** |
| 90 deg | 35 units |

The pipe is about 29 units wide with its decks, and its sphere arches stand about 23
above its floor, so parts more than 25 apart in height are counted as clear. The
script prints this figure on every run; check it before trusting a new stage or a
new setting.

Each frame covers the same distance *along* the track, so a steep frame moves less
far forward; without that a drop would stretch the pipe sections bent over it.

## Not done yet

* **Rings and bombs.** The object location file is Kosinski-compressed and undecoded.
  The same "sequence, not geometry" idea should apply: positions along the track and
  around the pipe, which can be placed on the curve.
* **Left or right.** See above; one constant.
* **Stages 2-7** are decoded and will generate, but only stage 1 has been built and
  checked for self-collision.
