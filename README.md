# Sonic2Special3D

A 3D take on the Sonic 2 special stage, built on the Octave engine.

Currently the sky: a dome carrying a gradient, a twinkling starfield, and a band
of diamond clusters along the horizon.

## Layout

| | |
| --- | --- |
| `proj/` | the Octave project — open `SkyboxDay.octp` |
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
| `T_S2Sky_Diamonds` | 512x512 | one row of diamond clusters |
| `M_Sky`, `SM_SkyDome` | | keep the day sky's names and uuids, so the scene picks them up unchanged |

The knobs worth knowing:

- `DIAMOND_REPEAT` — clusters around the horizon. The only size control; cells
  are kept square by deriving the vertical step from the horizontal one.
- `CLUSTER_ROWS` — rows of clusters up the dome. One: more than one fills the
  sky but reads as wallpaper.
- `CLUSTER_RADIUS` — 2, giving a cluster of 1/3/5/3/1 small diamonds.
- `STAR_FRAMES`, `STAR_TEX` — frames of the twinkle, and their size. Four at
  512 is 4MB, which is most of what the sky costs.
- `twinklesPerSecond` — on the SkyDome node, not in the script.

## Two things that are easy to get wrong again

**The dome's lowest ring is at -10 degrees.** UV v spans the real elevation
range, `-10..90`, so the skirt has its own texture rows. Mapping it as
`max(0, elev/90)` instead makes every vertex below the horizon share one row,
which is then stretched down the whole skirt. The horizon sits at `v = 0.1`, and
`SKIRT_CLEAR_V` keeps content off the rows beneath it.

**Stars twinkle by arm length, not brightness.** A dimmed white pixel on this
blue is not a faint star, it is a grey-brown one, and fading the arms turns a
crisp cross into a muddy blob. The brightness steps stay high; what changes is
how far the arms reach.
