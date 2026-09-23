# To do

## Marathon: crossfade between zone palettes

Now: at a zone change the pipe colours and the sky **switch** once, half way through the hold,
with the camera on Sonic (`SpecialStage.lua`, `SWITCH_AT`). That stays until this is done.

**Do not** crossfade by drawing a second copy of the pipe over the first. That was tried: two
surfaces in the same place fight over which is in front, and the whole screen strobed. It is a
flashing hazard.

**The way to do it: the colours move into the material.**

1. **Exporter** (`native/export_to_octave.py`, and the GameCube's `export_gc.py`): each pipe
   piece exported once, its faces' UVs pointing into a small **palette texture** (one texel per
   colour slot and checker shade) instead of carrying vertex colours. Today there are seven
   copies of every piece, one per palette.
2. **Palettes**: one tiny texture each. Changing palette changes the texture, not the mesh.
3. **Engine**: a material that blends two textures by a value from 0 to 1. On the PC a line in
   the shader; on the GameCube the TEV blends two textures by a constant natively.
4. **Crossfade**: the pipe material holds the old and new palette textures and the fade value
   runs 0 to 1 over the hold. The pipe is drawn once, so there is nothing to fight.
5. **Sky**: the same idea for the dome (two sets of frames, blended in the material), or a
   separate approach; the dome is one mesh either way.
6. **Check** before anyone watches it: capture the transition frame by frame and measure the
   change between frames -- it must drift smoothly, never jump back and forth.

Also a win: one mesh per piece instead of seven cuts the pipe's memory and disc size.
