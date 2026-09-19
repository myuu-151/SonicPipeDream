# Sonic2Special3D

A 3D take on the Sonic 2 special stage, built on the Octave engine.

Currently the sky: a dome carrying a gradient, a twinkling starfield, and a band
of diamond clusters along the horizon.

## Layout

| | |
| --- | --- |
| `proj/` | the Octave project — open `Sonic2Special3D.octp` |
| `proj/Scripts/Sky.lua` | anchors the dome to the camera and runs the twinkle |
| `native/gen_s2sky_assets.py` | generates every sky asset |
| `native/day_backup/` | the original day sky, before it was replaced |
| `s2sky_preview/` | flat renders used to judge the textures |

## The sky assets

`native/gen_s2sky_assets.py` writes the `.oct` files directly and is the only
place the sky is authored — edit the constants at the top and run it again.

| Asset | | |
| --- | --- | --- |
| `T_S2Sky_Gradient` | 16x256 | vertical band, ramped from the horizon up |
| `T_S2Sky_Stars_1..4` | 512x512 | twinkle frames, alpha-masked |
| `T_S2Sky_Diamonds_1..8` | 512x512 | one row of diamond clusters, banded inside |
| `M_Sky`, `SM_SkyDome` | | keep the day sky's names and uuids, so the scene picks them up unchanged |

The knobs worth knowing:

- `DIAMOND_REPEAT` — clusters around the horizon. The only size control; cells
  are kept square by deriving the vertical step from the horizontal one.
- `CLUSTER_ROWS` — rows of clusters up the dome. One: more than one fills the
  sky but reads as wallpaper.
- `CLUSTER_RADIUS` — 2, giving a cluster of 1/3/5/3/1 small diamonds.
- `DIAMOND_BANDS` — bands of the gradient inside each diamond.
  `DIAMOND_FRAMES` follows it, so each frame advances exactly one band.
- `DIAMOND_TOP`, `DIAMOND_BOTTOM` — the gradient, `#1b5e85` into `#36cb00`.
- `STAR_GRID`, `STAR_DROP` — the jittered grid the stars are placed on.
- `STAR_FRAMES`, `STAR_TEX` — frames of the twinkle, and their size.
- `twinklesPerSecond`, `colourShiftsPerSecond` — on the SkyDome node, not in
  the script.

Eight diamond frames and four star frames is about 12MB of RGBA8, which is
nearly all of what the sky costs. There is no shader to palette-swap with, so
every frame of animation is a whole texture. If it needs trimming, drop the
diamond textures to 256 before dropping frames: the bands are broad shapes and
lose little, while fewer frames makes the travel visibly step.

## Things that are easy to get wrong again

**The dome's lowest ring is at -10 degrees.** UV v spans the real elevation
range, `-10..90`, so the skirt has its own texture rows. Mapping it as
`max(0, elev/90)` instead makes every vertex below the horizon share one row,
which is then stretched down the whole skirt. The horizon sits at `v = 0.1`;
`SKIRT_CLEAR_V` keeps the diamonds off the rows beneath it, while the stars run
all the way to the dome's bottom edge — the dome is anchored to the game camera
rather than the viewport one, so in the editor it is routinely seen from
slightly off centre and the skirt shows.

**Stars twinkle by arm length, not brightness.** A dimmed white pixel on this
blue is not a faint star, it is a grey-brown one, and fading the arms turns a
crisp cross into a muddy blob. The brightness steps stay high; what changes is
how far the arms reach.

**The diamonds animate inside, not as a whole.** Filling each with one colour
and changing it per frame is a flicker: every diamond is a flat shape blinking
between colours at once. The bands give the motion somewhere to happen within
the shape.

**Stars sit on a jittered grid, not at random points.** Uniformly random
positions clump, and since the tile repeats around the dome every void repeats
with it -- which reads as one side of the sky being permanently barer than the
other.

**The clusters are deliberately not tessellated.** A 13-cell diamond does tile
the plane exactly, and it was tried: it fills the dome and destroys the effect,
because with no sky between them the clusters stop reading as clusters. The
gaps are what make a big diamond visible.
