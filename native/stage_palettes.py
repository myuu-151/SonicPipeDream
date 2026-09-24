"""The seven stages' colours, from the original, and which part of our pipe gets which.

    python native/stage_palettes.py        # print every stage's colours

No Blender in here. gen_stage.py recolours a stage's pipe from this, and writes the same
table into the stage's .json for the engine.

WHERE THEY COME FROM. art/palettes/Special Stage 1.bin ... 7.bin in Sonic Retro's s2disasm:
32 bytes each, sixteen Mega Drive colours (a word apiece, 0000BBB0GGG0RRR0), loaded as the
fourth palette line on top of a main palette all seven stages share. Decoded, the line has
a plain structure, the same in every stage:

    slot 1, 3, 6    the pipe's own colour: light, mid, dark
    slot 2, 4, 5    the trim colour (stripes, hoops): light, mid, dark
    slot 7 - F      the same in all seven: yellows, greys, white -- rings and text

so a stage's look is two colours in three shades each:

    1 cyan / orange      2 magenta / deep orange   3 red-orange / orange   4 cream / orange
    5 orange / GREEN     6 green / orange          7 grey / lavender

OURS NOW, 4 AND 5 (the owner's choice, 2026-09-24). Stage 4 is ROSE: the original 4's line with every
colour's channels turned round, (r, g, b) -> (full, b, g) -- found by accident, when the GameCube
wrote a palette's colours in the wrong byte order, and kept. Stage 5 is the original 4 (cream); the
original 5 (orange and green) is gone.

WHAT IS OURS. The original's pipe is a flat drawing in those six shades; ours is a lit 3D
model with seven materials, so which slot colours which material is a choice (ROLES). The
sky is ours entirely -- the original's is a black starfield in every stage -- so SKY pairs
each stage with the one of the project's eight skies (docs/skies.md) that sits best behind
its pipe. Both are one table each, to be changed by eye.
"""

# The fourth palette line of each stage, slots 0-F, as decoded.
S2_LINE = {
    1: "000000 00B6DB FFB624 0092B6 DB9224 B66D24 006D92 FFFF00 929292 494949 FFFFFF FFFF00 929200 494900 490000 FFFFFF",
    2: "000000 DB0092 FF9200 B6006D DB6D00 B64900 920049 FFFF00 929292 494949 FFFFFF FFFF00 929200 494900 490000 FFFFFF",
    3: "000000 DB4900 FFB624 B62400 DB9224 B66D24 922400 FFFF00 929292 494949 FFFFFF FFFF00 929200 494900 490000 FFFFFF",
    4: None,                # ROSE: the cream line below, turned round (see _rose)
    5: "000000 DBDBB6 FFB624 B6B692 DB9224 B66D24 92926D FFFF00 929292 494949 FFFFFF FFFF00 929200 494900 490000 FFFFFF",
    6: "000000 6DB600 FFB624 499200 DB9224 B66D24 496D00 FFFF00 929292 494949 FFFFFF FFFF00 929200 494900 490000 FFFFFF",
    7: "000000 929292 B6B6DB 6D6D6D 9292B6 6D6D92 494949 FFFF00 929292 494949 FFFFFF FFFF00 929200 494900 490000 FFFFFF",
}



def _rose(line):
    """Every colour but slot 0 (unused) as the GameCube showed it: red full, green and blue swapped."""
    out = []
    for i, c in enumerate(line.split()):
        out.append(c if i == 0 else "FF" + c[4:6] + c[2:4])
    return " ".join(out)


S2_LINE[4] = _rose(S2_LINE[5])

NAMES = {1: "Cyan", 2: "Magenta", 3: "Ember", 4: "Rose", 5: "Cream", 6: "Green", 7: "Steel"}

# Our material <- the original's slot. The half-pipe's materials are gen_halfpipe.py's.
ROLES = {
    "HP_Pipe":   1,         # the pipe itself: the stage's own colour, at its lightest
    "HP_Lane":   2,         # the stripes down the floor: the trim, light
    "HP_Hoop":   4,         # the band across the pipe under each arch: the trim, mid
    "HP_Sphere": 4,         # the arch of spheres: the trim, mid
    "HP_Deck":   5,         # the ledges along the rims: the trim, dark
    "HP_Rail":   7,         # the rails: the yellow every stage shares
}
PATCH_LIFT = 0.40           # HP_Patch, the paler inset in a stripe: the lane colour, this far to white

# THE RAILS AND THE SPHERE ARCH, OURS (the owner's ask, 2026-09-24). From the line, every stage's
# rails were the one yellow all seven share, and four stages' spheres the same orange (their trim
# is). So each stage has its own here, to go with its colours: stage -> (rails, spheres). Stage 1
# keeps the original's; Rose keeps what its turned-round line gives.
ACCENTS = {
    1: ("FFFF00", "DB9224"),     # Cyan: the original's yellow rails and orange spheres
    2: ("FFDB49", "DB6D00"),     # Magenta: gold rails, deep-orange spheres
    3: ("FF2400", "FFDB00"),     # Ember: red-hot rails, yellow-gold spheres
    4: ("FF00FF", "FF2492"),     # Rose
    5: ("B692FF", "49DBB6"),     # Cream, under the Aurora: lavender rails, aurora-teal spheres
    6: ("DBFF6D", "B649FF"),     # Green, under the Pastel sky: lime rails, violet spheres
    7: ("92DBFF", "B6B6FF"),     # Steel, under Midnight: ice-blue rails, periwinkle spheres
}

# Which of the project's skies (docs/skies.md) goes behind each stage. OURS: see above.
SKY = {1: (0, "Classic"), 2: (4, "Sunset"), 3: (6, "Inferno"), 4: (2, "Dawn"),
       5: (5, "Aurora"), 6: (3, "Pastel"), 7: (1, "Midnight")}


def rgb(hex6):
    return tuple(int(hex6[i:i + 2], 16) / 255.0 for i in (0, 2, 4))


def palette(stage):
    """{name, stage, sky, sky_name, materials: {material: (r, g, b) sRGB 0-1}, line: [hex]}"""
    line = S2_LINE[stage].split()
    mats = {name: rgb(line[slot]) for name, slot in ROLES.items()}
    if stage in ACCENTS:
        mats["HP_Rail"], mats["HP_Sphere"] = rgb(ACCENTS[stage][0]), rgb(ACCENTS[stage][1])
    lane = mats["HP_Lane"]
    mats["HP_Patch"] = tuple(c + (1.0 - c) * PATCH_LIFT for c in lane)
    return dict(stage=stage, name=NAMES[stage], sky=SKY[stage][0], sky_name=SKY[stage][1],
                materials=mats, line=line,
                pipe_shades=[line[1], line[3], line[6]], trim_shades=[line[2], line[4], line[5]])


if __name__ == "__main__":
    for st in range(1, 8):
        p = palette(st)
        print("stage %d  %-17s sky %d %-8s pipe %s  trim %s" % (
            st, p["name"], p["sky"], p["sky_name"], "/".join(p["pipe_shades"]), "/".join(p["trim_shades"])))
