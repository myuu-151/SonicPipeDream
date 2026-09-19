"""The diamond medley as real textures: every frame of the show, in order.

Editor-only for now. 384 frames at 512x256 is far beyond what the GameCube can
hold; this exists to see the full show on the sky before deciding how to fit it.

The frames come from preview_diamond_concepts.medley_frame -- the same function
that drew the preview GIF -- so what is on the sky is exactly what was approved.
Needs Pillow, which the rest of the generator does not.
"""

import preview_diamond_concepts as pat

FRAMES = pat.medley_length()
TEX_W, TEX_H = pat.TILE_W, pat.TILE_H


def frame_name(f):
    return "T_S2Sky_Medley_%03d" % (f + 1)


def frame_pixels(f):
    """RGBA8 bytes with row 0 at the BOTTOM of the band, which is how the dome's
    v runs. The preview paints with row 0 at the top, so it is flipped here."""
    im = pat.paint_rgba(pat.medley_frame(f)).transpose(pat.Image.FLIP_TOP_BOTTOM)

    # The dome parks everything outside the band on texel (0, 0), so that texel
    # has to be empty in every frame or it would be smeared over the whole sky.
    assert im.getpixel((0, 0))[3] == 0, "frame %d: texel (0,0) is not empty" % f
    return im.tobytes()
