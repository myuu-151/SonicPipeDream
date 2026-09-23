"""Texture the bomb: metal detail, baked into one picture.

    blender -b external/bomb/Bomb.blend --python native/texture_bomb.py -- [render]

Reads the bomb gen_bomb.py made (external/bomb/Bomb.blend, left as it is) and writes

    external/bomb/Bomb_albedo.png       the bomb's colours with their detail, 1024 x 1024
    external/bomb/Bomb_lit.png          the same, LIT: its shading, highlights and metal reflections baked in
    external/bomb/Bomb_Textured.blend   the bomb unwrapped, showing Bomb_lit.png as it is (flat)
    external/bomb/Bomb_Textured_preview.png   (with `render`)

The detail is procedural, made in Blender's shader nodes and BAKED -- the game has one texture,
not a shader:

    Bomb_Body   the black ball, rails and collars: gunmetal, a fine brushed grain, faint
                scratches catching the light, lighter where edges wear
    Bomb_Red    the bands and studs: red paint over steel, a slight orange-peel mottle, and
                the paint rubbed through to bare metal on the sharpest edges
    Bomb_Spike  the silver pyramids: brushed steel, the grain running up to the point

Ambient occlusion is baked in too, so the grooves between the ribs and round the collars read
as grooves in the game, where the light is simple.

export_to_octave.py uses Bomb_Textured.blend and the texture when they are there.
"""

import math
import os
import sys

import bmesh
import bpy

HERE = os.path.dirname(os.path.abspath(__file__))
OUT_DIR = os.path.abspath(os.path.join(HERE, "..", "external", "bomb"))
args = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
RENDER = "render" in args

SIZE = 1024
SAMPLES = 64                    # for the ambient occlusion; the rest is exact
MARGIN = 6                      # pixels bled past each island, for filtering and mipmaps. Less than the
                                # gap between islands (ISLAND_GAP): at 8 against a 6 pixel gap, the grey
                                # rails bled into the red islands packed beside and inside them
ISLAND_GAP = 16.0 / SIZE        # the gap left between islands when they are packed


# ---------------------------------------------------------------- nodes
def node(tree, kind, x, y, **inputs):
    n = tree.nodes.new(kind)
    n.location = (x, y)
    for key, value in inputs.items():
        n.inputs[key].default_value = value
    return n


def link(tree, a, out, b, inp):
    tree.links.new(a.outputs[out], b.inputs[inp])


def mix(tree, x, y, a, b, factor, blend="MIX"):
    m = node(tree, "ShaderNodeMix", x, y)
    m.data_type = "RGBA"
    m.blend_type = blend
    tree.links.new(factor, m.inputs[0])
    for socket, value in ((6, a), (7, b)):
        if isinstance(value, tuple):
            m.inputs[socket].default_value = value
        else:
            tree.links.new(value, m.inputs[socket])
    return m.outputs[2]


def ramp(tree, x, y, src, stops):
    r = node(tree, "ShaderNodeValToRGB", x, y)
    els = r.color_ramp.elements
    els[0].position, els[0].color = stops[0]
    els[1].position, els[1].color = stops[-1]
    for pos, colour in stops[1:-1]:
        e = els.new(pos)
        e.color = colour
    tree.links.new(src, r.inputs[0])
    return r.outputs[0]


def grain(tree, x, y, coords, stretch, scale, detail=8.0):
    """Noise stretched along one axis: brushed metal."""
    mapping = node(tree, "ShaderNodeMapping", x - 200, y)
    mapping.inputs["Scale"].default_value = stretch
    tree.links.new(coords, mapping.inputs[0])
    noise = node(tree, "ShaderNodeTexNoise", x, y, Scale=scale, Detail=detail, Roughness=0.6)
    tree.links.new(mapping.outputs[0], noise.inputs[0])
    return noise.outputs["Fac"]


def build(material, kind):
    """The bake material: its Emission is the finished albedo."""
    material.use_nodes = True
    tree = material.node_tree
    tree.nodes.clear()
    out = node(tree, "ShaderNodeOutputMaterial", 1400, 0)
    emit = node(tree, "ShaderNodeEmission", 1200, 0, Strength=1.0)
    link(tree, emit, 0, out, 0)

    coord = node(tree, "ShaderNodeTexCoord", -1200, 0)
    obj = coord.outputs["Object"]
    geo = node(tree, "ShaderNodeNewGeometry", -1200, -300)
    ao = node(tree, "ShaderNodeAmbientOcclusion", -1200, -500)
    ao.samples = 32
    ao.inputs["Distance"].default_value = 0.35

    # wear: the sharpest edges (pointiness above its middle), broken up by noise
    edge = ramp(tree, -800, -300, geo.outputs["Pointiness"],
                [(0.50, (0, 0, 0, 1)), (0.56, (1, 1, 1, 1))])
    speck = node(tree, "ShaderNodeTexNoise", -1000, -700, Scale=24.0, Detail=6.0, Roughness=0.7)
    tree.links.new(obj, speck.inputs[0])
    speck_mask = ramp(tree, -800, -700, speck.outputs["Fac"], [(0.45, (0, 0, 0, 1)), (0.62, (1, 1, 1, 1))])
    wear = mix(tree, -600, -450, (0, 0, 0, 1), edge, speck_mask, "MULTIPLY")

    # scratches: thin bright lines from a stretched Voronoi's cell edges
    vmap = node(tree, "ShaderNodeMapping", -1000, 300)
    vmap.inputs["Scale"].default_value = (1.0, 7.0, 1.0)
    vmap.inputs["Rotation"].default_value = (0.4, 0.9, 0.2)
    tree.links.new(obj, vmap.inputs[0])
    vor = node(tree, "ShaderNodeTexVoronoi", -800, 300, Scale=9.0)
    vor.feature = "DISTANCE_TO_EDGE"
    tree.links.new(vmap.outputs[0], vor.inputs[0])
    scratch = ramp(tree, -600, 300, vor.outputs["Distance"], [(0.0, (1, 1, 1, 1)), (0.035, (0, 0, 0, 1))])
    scratch_patch = node(tree, "ShaderNodeTexNoise", -800, 520, Scale=3.0, Detail=2.0)
    tree.links.new(obj, scratch_patch.inputs[0])
    patch = ramp(tree, -600, 520, scratch_patch.outputs["Fac"], [(0.5, (0, 0, 0, 1)), (0.65, (1, 1, 1, 1))])
    scratches = mix(tree, -400, 400, (0, 0, 0, 1), scratch, patch, "MULTIPLY")

    if kind == "Bomb_Body":
        # gunmetal: blue-black with a fine brushed grain round the ball
        g = grain(tree, -800, 0, obj, (1.0, 1.0, 30.0), 14.0)
        base = ramp(tree, -600, 0, g, [(0.3, (0.008, 0.008, 0.011, 1)), (0.7, (0.030, 0.031, 0.040, 1))])
        c = mix(tree, -200, 100, base, (0.05, 0.052, 0.06, 1), scratches, "MIX")
        c = mix(tree, 0, 0, c, (0.06, 0.062, 0.07, 1), wear, "MIX")        # (grey here outlined every edge)
    elif kind == "Bomb_Red":
        # red paint over steel: a slight mottle, rubbed through on the sharpest edges
        g = node(tree, "ShaderNodeTexNoise", -800, 0, Scale=40.0, Detail=4.0, Roughness=0.5)
        tree.links.new(obj, g.inputs[0])
        base = ramp(tree, -600, 0, g.outputs["Fac"], [(0.35, (0.74, 0.024, 0.068, 1)), (0.65, (0.82, 0.032, 0.080, 1))])
        c = mix(tree, -200, 100, base, (0.95, 0.30, 0.32, 1), scratches, "MIX")
        steel = ramp(tree, -400, -200, speck.outputs["Fac"], [(0.3, (0.45, 0.46, 0.49, 1)), (0.7, (0.62, 0.63, 0.66, 1))])
        c = mix(tree, 0, 0, c, steel, wear, "MIX")
    else:
        # brushed steel, the grain running up to the point (the spikes stand along their own normals;
        # object Z stretched brushes the ones at the poles, X and Y the others, near enough)
        g = grain(tree, -800, 0, obj, (40.0, 40.0, 1.0), 6.0, detail=10.0)
        g2 = grain(tree, -800, -150, obj, (1.0, 1.0, 40.0), 6.0, detail=10.0)
        both = mix(tree, -600, -60, g, g2, node(tree, "ShaderNodeValue", -800, -260).outputs[0], "MIX")
        base = ramp(tree, -400, 0, both, [(0.3, (0.56, 0.58, 0.62, 1)), (0.7, (0.80, 0.81, 0.85, 1))])
        c = mix(tree, -200, 100, base, (0.93, 0.94, 0.97, 1), scratches, "MIX")

    # ambient occlusion: the grooves go deep and dark (to 8%), reaching well into them
    occl = ramp(tree, 600, -300, ao.outputs["AO"], [(0.0, (0.08, 0.08, 0.08, 1)), (0.9, (1, 1, 1, 1))])
    c = mix(tree, 900, 0, c, occl, node(tree, "ShaderNodeValue", 700, -500).outputs[0], "MULTIPLY")
    tree.links.new(c, emit.inputs["Color"])
    # the Value nodes above default to 0; the spike's grain blend and the AO blend want 0.5 and 1
    for n in tree.nodes:
        if n.type == "VALUE":
            n.outputs[0].default_value = 0.5 if n.location.y == -260 else 1.0


def view_material(material, kind, image):
    """For looking at in Blender: metal, reading the baked texture."""
    tree = material.node_tree
    tree.nodes.clear()
    out = node(tree, "ShaderNodeOutputMaterial", 600, 0)
    bsdf = node(tree, "ShaderNodeBsdfPrincipled", 300, 0)
    tex = tree.nodes.new("ShaderNodeTexImage")
    tex.location = (0, 0)
    tex.image = image
    link(tree, tex, 0, bsdf, "Base Color")
    link(tree, bsdf, 0, out, 0)
    metal, rough = {"Bomb_Body": (0.85, 0.38), "Bomb_Red": (0.35, 0.30), "Bomb_Spike": (1.0, 0.26)}[kind]
    bsdf.inputs["Metallic"].default_value = metal
    bsdf.inputs["Roughness"].default_value = rough


# ---------------------------------------------------------------- the lighting, painted
# The texture carries its own lighting -- shading, a specular highlight, and a sky reflected in
# the metal. Blender's own lighting bake cannot do this: it views every point straight down its
# normal, so a highlight, which depends on where the viewer is, comes out as flat bright tops. So
# the lighting is painted, point by point, the way the gold rings' reflection is.
#
# EVERY SIDE IS LIT ALIKE: each point as seen from a camera straight in front of its own side (and
# a little above), with the sun above and behind that camera. Painted for one camera only -- from
# behind, down the track -- the sides that camera never sees had no highlights at all; and a bomb
# on the pipe's wall is turned, so its "behind" is not the camera's anyway. Round the bomb it is
# all the same, so the four mirrored quarters of the texture (see unwrap) agree too.
VIEW_UP = 0.45                          # the camera's rise, for one step out in front of the side
SUN_OUT, SUN_UP = 0.40, 0.92            # the sun: this far out toward the camera, this far up
AMBIENT, DIFFUSE = 0.30, 0.85
# per part: highlight colour, sharpness, reflection colour (what the metal reflects the sky with)
FINISH = {
    "Bomb_Body":  ((0.80, 0.84, 0.95), 350.0, (0.04, 0.042, 0.05)),   # gunmetal: black, with a crisp highlight
                                                                       # line (at sharpness 60 the round panels
                                                                       # went a broad grey)
    "Bomb_Red":   ((0.90, 0.85, 0.85), 220.0, (0.05, 0.03, 0.035)),   # red paint, clear-coated: a small white
                                                                       # glint; broader, with more sky, it washed
                                                                       # the whole band out pink
    "Bomb_Spike": ((1.00, 1.00, 1.00), 40.0, (0.70, 0.72, 0.78)),     # polished steel
}


def vec(tree, x, y, v):
    n = node(tree, "ShaderNodeCombineXYZ", x, y)
    n.inputs[0].default_value, n.inputs[1].default_value, n.inputs[2].default_value = v
    return n.outputs[0]


def vmath(tree, x, y, op, a, b=None):
    n = node(tree, "ShaderNodeVectorMath", x, y)
    n.operation = op
    tree.links.new(a, n.inputs[0])
    if b is not None:
        tree.links.new(b, n.inputs[1])
    return n.outputs["Value"] if op in ("DOT_PRODUCT", "LENGTH", "DISTANCE") else n.outputs["Vector"]


def math_node(tree, x, y, op, a, b=None, value=None):
    n = node(tree, "ShaderNodeMath", x, y)
    n.operation = op
    if isinstance(a, float):
        n.inputs[0].default_value = a
    else:
        tree.links.new(a, n.inputs[0])
    if b is not None:
        tree.links.new(b, n.inputs[1])
    elif value is not None:
        n.inputs[1].default_value = value
    return n.outputs[0]


def painted_material(material, kind, albedo):
    """Emission: the albedo, lit as it would be from in front of each side."""
    from mathutils import Vector
    tree = material.node_tree
    tree.nodes.clear()
    out = node(tree, "ShaderNodeOutputMaterial", 1800, 0)
    emit = node(tree, "ShaderNodeEmission", 1600, 0, Strength=1.0)
    link(tree, emit, 0, out, 0)
    tex = tree.nodes.new("ShaderNodeTexImage")
    tex.location = (-200, 400)
    tex.image = albedo
    base = tex.outputs["Color"]

    # the normal, and the side it faces: the normal laid flat (a point facing straight up or down
    # has no side, and gets the camera overhead)
    coord = node(tree, "ShaderNodeTexCoord", -1600, 0)
    n = vmath(tree, -1400, 0, "NORMALIZE", coord.outputs["Normal"])
    sep = node(tree, "ShaderNodeSeparateXYZ", -1400, -150)
    tree.links.new(n, sep.inputs[0])
    flat = node(tree, "ShaderNodeCombineXYZ", -1200, -150)
    tree.links.new(sep.outputs["X"], flat.inputs[0])
    tree.links.new(sep.outputs["Y"], flat.inputs[1])
    side = vmath(tree, -1000, -150, "NORMALIZE", flat.outputs[0])

    def toward(out, up, x, y):
        """normalize(side * out + up * Z)"""
        scaled = node(tree, "ShaderNodeVectorMath", x - 200, y)
        scaled.operation = "SCALE"
        tree.links.new(side, scaled.inputs[0])
        scaled.inputs[3].default_value = out
        added = vmath(tree, x - 100, y, "ADD", scaled.outputs["Vector"], vec(tree, x - 200, y - 100, (0.0, 0.0, up)))
        return vmath(tree, x, y, "NORMALIZE", added)

    v_view = toward(1.0, VIEW_UP, -700, -200)
    v_sun = toward(SUN_OUT, SUN_UP, -700, -350)
    v_half = vmath(tree, -600, -450, "NORMALIZE", vmath(tree, -650, -450, "ADD", v_view, v_sun))

    # diffuse
    ndl = math_node(tree, -400, -200, "MAXIMUM", vmath(tree, -500, -200, "DOT_PRODUCT", n, v_sun), value=0.0)
    light = math_node(tree, -200, -200, "MULTIPLY_ADD", ndl, value=DIFFUSE)
    light.node.inputs[2].default_value = AMBIENT
    lit = mix(tree, 0, 200, base, (1, 1, 1, 1), node(tree, "ShaderNodeValue", -200, 100).outputs[0], "MIX")
    lit_n = node(tree, "ShaderNodeMix", 200, 200)
    lit_n.data_type = "RGBA"
    lit_n.blend_type = "MULTIPLY"
    lit_n.inputs[0].default_value = 1.0
    tree.links.new(base, lit_n.inputs[6])
    grey = node(tree, "ShaderNodeCombineColor", 0, -100)
    for k in range(3):
        tree.links.new(light, grey.inputs[k])
    tree.links.new(grey.outputs[0], lit_n.inputs[7])
    colour = lit_n.outputs[2]

    spec_colour, sharp, refl_colour = FINISH[kind]

    # THE HIGHLIGHT, from four cameras round the bomb -- in front, behind, left, right, each a little
    # above with the sun above and behind it -- the brightest of the four. A camera per point (as
    # the shading has) lit every band's crest along its whole length: the one glint a band had
    # from one camera became a stripe. Four fixed cameras give each band its glint where it faces
    # one of them, on every side.
    from mathutils import Vector
    # (And a second, lower ring of them, every 45 degrees: from the first ring alone the highlight
    # only found faces tilted up, and the band round the middle, whose crest faces straight out,
    # had none.)
    spec = None
    # The upper ring: four, in front, behind and to the sides. The lower: four more in the gaps
    # between them, at half strength -- eight of each, both full, was too much glitter.
    rings = [(VIEW_UP, SUN_OUT, SUN_UP, 0.0, 1.0), (0.05, 1.0, 0.35, 45.0, 0.5)]   # rise; sun out, up; turn; weight
    cams = []
    for rise, out_, up_, turn, weight in rings:
        for a in range(4):
            ang = math.radians(90.0 * a + turn)
            cams.append((math.cos(ang), math.sin(ang), rise, out_, up_, weight))
    for k, (dx, dy, rise, out_, up_, weight) in enumerate(cams):
        v_k = Vector((dx, dy, rise)).normalized()
        l_k = Vector((dx * out_, dy * out_, up_)).normalized()
        h_k = vec(tree, -700, -500 - 60 * k, tuple((v_k + l_k).normalized()))
        ndh = math_node(tree, -500, -500 - 60 * k, "MAXIMUM", vmath(tree, -600, -500 - 60 * k, "DOT_PRODUCT", n, h_k), value=0.0)
        one = math_node(tree, -450, -500 - 60 * k, "POWER", ndh, value=sharp)
        one = math_node(tree, -400, -500 - 60 * k, "MULTIPLY", one, value=weight)
        spec = one if spec is None else math_node(tree, -300, -500 - 60 * k, "MAXIMUM", spec, one)
    spec_rgb = node(tree, "ShaderNodeMix", 0, -500)
    spec_rgb.data_type = "RGBA"
    spec_rgb.blend_type = "MULTIPLY"
    spec_rgb.inputs[0].default_value = 1.0
    spec_rgb.inputs[6].default_value = spec_colour + (1.0,)
    sg = node(tree, "ShaderNodeCombineColor", -100, -650)
    for k in range(3):
        tree.links.new(spec, sg.inputs[k])
    tree.links.new(sg.outputs[0], spec_rgb.inputs[7])

    # the sky, reflected: bright above a dark horizon, and more of it at a glancing angle.
    # A point facing AWAY from the camera is never seen from it, and reflecting the view off it
    # sent the reflection up through the surface into the bright sky: every face that pointed down
    # came out white. Those reflect as if seen head on instead (the reflection is the normal), so a
    # face that points down reflects the dark ground.
    flip_view = node(tree, "ShaderNodeVectorMath", -600, -800)
    flip_view.operation = "SCALE"
    tree.links.new(v_view, flip_view.inputs[0])
    flip_view.inputs[3].default_value = -1.0
    neg_view = flip_view.outputs["Vector"]
    r = vmath(tree, -400, -800, "REFLECT", neg_view, n)
    facing = vmath(tree, -500, -1150, "DOT_PRODUCT", n, v_view)
    away = math_node(tree, -300, -1150, "MULTIPLY", facing, value=-4.0)
    away_n = node(tree, "ShaderNodeClamp", -100, -1150)
    tree.links.new(away, away_n.inputs[0])
    r_mix = node(tree, "ShaderNodeMix", -250, -900)
    r_mix.data_type = "VECTOR"
    tree.links.new(away_n.outputs[0], r_mix.inputs[0])
    tree.links.new(r, r_mix.inputs[4])
    tree.links.new(n, r_mix.inputs[5])
    r = r_mix.outputs[1]
    rz = node(tree, "ShaderNodeSeparateXYZ", -200, -800)
    tree.links.new(r, rz.inputs[0])
    up = node(tree, "ShaderNodeMapRange", 0, -800)
    up.inputs["From Min"].default_value, up.inputs["From Max"].default_value = -1.0, 1.0
    tree.links.new(rz.outputs["Z"], up.inputs["Value"])
    sky = ramp(tree, 200, -800, up.outputs["Result"],
               [(0.0, (0.05, 0.04, 0.035, 1)), (0.47, (0.015, 0.015, 0.02, 1)),
                (0.53, (0.55, 0.62, 0.80, 1)), (1.0, (1.0, 1.0, 1.0, 1))])
    ndv = math_node(tree, -400, -1000, "MAXIMUM", vmath(tree, -500, -1000, "DOT_PRODUCT", n, v_view), value=0.0)
    fres = math_node(tree, -200, -1000, "POWER", math_node(tree, -300, -1000, "SUBTRACT", 1.0, ndv), value=2.0)
    fres = math_node(tree, 0, -1000, "MULTIPLY_ADD", fres, value=0.7)
    fres.node.inputs[2].default_value = 0.3
    refl = node(tree, "ShaderNodeMix", 400, -800)
    refl.data_type = "RGBA"
    refl.blend_type = "MULTIPLY"
    refl.inputs[0].default_value = 1.0
    tree.links.new(sky, refl.inputs[6])
    refl.inputs[7].default_value = refl_colour + (1.0,)
    refl_f = node(tree, "ShaderNodeMix", 600, -800)
    refl_f.data_type = "RGBA"
    refl_f.blend_type = "MULTIPLY"
    refl_f.inputs[0].default_value = 1.0
    tree.links.new(refl.outputs[2], refl_f.inputs[6])
    fg = node(tree, "ShaderNodeCombineColor", 400, -1000)
    for k in range(3):
        tree.links.new(fres, fg.inputs[k])
    tree.links.new(fg.outputs[0], refl_f.inputs[7])

    # The shine is OCCLUDED too: the albedo carries the grooves' shadow, but a highlight or a
    # reflection added on top of it lit the grooves straight back up.
    # ...and the whole of it, reaching well into the gaps: where the rails, bands and collars sit on
    # the gunmetal ball the grooves go properly dark against the sheen round them.
    ao = node(tree, "ShaderNodeAmbientOcclusion", 400, -1300)
    ao.samples = 16
    ao.inputs["Distance"].default_value = 0.7
    occl = ramp(tree, 600, -1300, ao.outputs["AO"], [(0.0, (0.0, 0.0, 0.0, 1)), (0.35, (0.25, 0.25, 0.25, 1)),
                                                     (0.95, (1, 1, 1, 1))])
    shine = mix(tree, 700, -600, refl_f.outputs[2], spec_rgb.outputs[2], node(tree, "ShaderNodeValue", 600, -500).outputs[0], "ADD")
    total = mix(tree, 900, 0, colour, shine, node(tree, "ShaderNodeValue", 800, 100).outputs[0], "ADD")
    total = mix(tree, 1100, 0, total, occl, node(tree, "ShaderNodeValue", 1000, 100).outputs[0], "MULTIPLY")
    tree.links.new(total, emit.inputs["Color"])
    for v in tree.nodes:
        if v.type == "VALUE":
            v.outputs[0].default_value = 1.0


def flat_material(material, image):
    """For looking at in Blender: the lit texture exactly as it is, no light added."""
    tree = material.node_tree
    tree.nodes.clear()
    out = node(tree, "ShaderNodeOutputMaterial", 600, 0)
    emit = node(tree, "ShaderNodeEmission", 300, 0, Strength=1.0)
    tex = tree.nodes.new("ShaderNodeTexImage")
    tex.location = (0, 0)
    tex.image = image
    link(tree, tex, 0, emit, "Color")
    link(tree, emit, 0, out, 0)


# ---------------------------------------------------------------- the unwrap
# THE BOMB IS UNWRAPPED A QUARTER AT A TIME. It is symmetrical about X and about Y, so only the
# quarter where both are positive has space of its own in the texture; the other three quarters
# use the same UVs, mirrored. Four times the detail for the same texture -- the first unwrap
# (Smart UV Project over the whole bomb, as it came) spent 18% of the texture on 244 islands and
# looked soft. Z (up) is not mirrored, so light from above is right on every quarter.
EPS = 1e-4


def unwrap(bomb):
    me = bomb.data
    bm = bmesh.new()
    bm.from_mesh(me)
    bm.faces.ensure_lookup_table()

    def key(points):
        return tuple(sorted((round(p[0], 4), round(p[1], 4), round(p[2], 4)) for p in points))

    canonical, twins = {}, []
    for f in bm.faces:
        c = f.calc_center_median()
        sx = -1.0 if c.x < -EPS else 1.0
        sy = -1.0 if c.y < -EPS else 1.0
        if sx > 0 and sy > 0:
            canonical[key([v.co for v in f.verts])] = f.index
            f.select = True
        else:
            twins.append((f.index, sx, sy))
            f.select = False
    bm.to_mesh(me)
    bm.free()

    # the quarter: unwrapped, then packed to fill the whole texture
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_mode(type="FACE")
    bpy.ops.uv.smart_project(angle_limit=math.radians(66.0), island_margin=ISLAND_GAP, area_weight=0.0,
                             correct_aspect=True, scale_to_bounds=False)
    bpy.ops.uv.select_all(action="SELECT")
    bpy.ops.uv.average_islands_scale()
    bpy.ops.uv.pack_islands(rotate=True, margin=ISLAND_GAP, shape_method="CONCAVE")
    bpy.ops.object.mode_set(mode="OBJECT")

    # the other three quarters: each face takes the UVs of its mirror image in the first
    bm = bmesh.new()
    bm.from_mesh(me)
    bm.faces.ensure_lookup_table()
    uv = bm.loops.layers.uv.active
    missed = 0
    for index, sx, sy in twins:
        f = bm.faces[index]
        mirrored = [(v.co.x * sx, v.co.y * sy, v.co.z) for v in f.verts]
        g_index = canonical.get(key(mirrored))
        if g_index is None:
            missed += 1
            continue
        g = bm.faces[g_index]
        by_pos = {(round(l.vert.co.x, 4), round(l.vert.co.y, 4), round(l.vert.co.z, 4)): l[uv].uv.copy() for l in g.loops}
        for l in f.loops:
            m = (round(l.vert.co.x * sx, 4), round(l.vert.co.y * sy, 4), round(l.vert.co.z, 4))
            l[uv].uv = by_pos[m]
    bm.to_mesh(me)
    bm.free()
    print("unwrap: %d faces in the quarter, %d mirrored onto it, %d without a mirror image"
          % (len(canonical), len(twins) - missed, missed))


def main():
    bomb = bpy.data.objects["Bomb"]
    for o in bpy.context.view_layer.objects:
        o.select_set(False)
    bpy.context.view_layer.objects.active = bomb
    bomb.select_set(True)

    unwrap(bomb)

    image = bpy.data.images.new("Bomb_albedo", SIZE, SIZE, alpha=False)
    image.colorspace_settings.name = "sRGB"
    for material in bomb.data.materials:
        build(material, material.name.split(".")[0])
        tex = material.node_tree.nodes.new("ShaderNodeTexImage")
        tex.image = image
        material.node_tree.nodes.active = tex            # the bake writes into the active image node

    scene = bpy.context.scene
    scene.render.engine = "CYCLES"
    scene.cycles.device = "CPU"
    scene.cycles.samples = SAMPLES
    scene.render.bake.margin = MARGIN
    bpy.ops.object.bake(type="EMIT", margin=MARGIN)

    path = os.path.join(OUT_DIR, "Bomb_albedo.png")
    image.filepath_raw = path
    image.file_format = "PNG"
    image.save()
    print("wrote %s" % path)

    # the second bake: the metal, lit (painted: see painted_material)
    image.filepath = path
    lit = bpy.data.images.new("Bomb_lit", SIZE, SIZE, alpha=False)
    lit.colorspace_settings.name = "sRGB"
    for material in bomb.data.materials:
        painted_material(material, material.name.split(".")[0], image)
        tex = material.node_tree.nodes.new("ShaderNodeTexImage")
        tex.image = lit
        material.node_tree.nodes.active = tex
    scene.cycles.samples = 64                   # the lighting is arithmetic; the samples are for the occlusion
    bpy.ops.object.bake(type="EMIT", margin=MARGIN)
    lit_path = os.path.join(OUT_DIR, "Bomb_lit.png")
    lit.filepath_raw = lit_path
    lit.file_format = "PNG"
    lit.save()
    lit.filepath = lit_path
    print("wrote %s" % lit_path)

    for material in bomb.data.materials:
        flat_material(material, lit)
    blend = os.path.join(OUT_DIR, "Bomb_Textured.blend")
    bpy.ops.wm.save_as_mainfile(filepath=blend, copy=True)
    print("wrote %s" % blend)

    if RENDER:
        scene.cycles.samples = 64
        scene.render.resolution_x = scene.render.resolution_y = 640
        scene.render.filepath = os.path.join(OUT_DIR, "Bomb_Textured_preview.png")
        bpy.ops.render.render(write_still=True)
        print("wrote %s" % scene.render.filepath)


main()
