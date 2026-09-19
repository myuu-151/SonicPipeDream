"""Model one straight section of the special-stage half-pipe.

Run inside Blender:
    blender -b --python native/gen_halfpipe.py

One section only, and straight: it is meant to be repeated with an Array
modifier and bent with a Curve modifier, so the stage's turns and hills come
from the curve, not from this mesh.

Everything is geometry with flat-colour materials -- no textures. The hoop band
and the lane stripes are not painted on; they are the pipe's own faces, given a
different material, which is why the pipe's grid has edges exactly where those
details start and stop.

Built along +X from x = 0 to x = LENGTH, origin at x = 0, and nothing pokes
outside that range, so an Array with a relative offset of 1.0 on X tiles it
without gaps or overlap. The floor of the pipe sits at z = 0.
"""

import math
import os

import bmesh
import bpy

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "..", "external", "halfpipe", "HalfPipe_Section.blend")

# --- dimensions -------------------------------------------------------------
LENGTH = 24.0          # one section, along X
RADIUS = 10.0          # the pipe's inside radius
DECK_W = 4.5           # the flat ledge along each rim
DECK_DROP = 1.2        # a short outer wall under the ledge, so it has thickness

# Along-X subdivision. The Curve modifier can only bend at edges, so the section
# needs cross-cuts even where no detail asks for one.
MAX_STEP = 2.0

# The hoop: an orange band across the inside of the pipe, under the sphere arch.
HOOP_X = LENGTH * 0.5
HOOP_W = 0.9

# Lane stripes on the floor, as angles round the pipe from straight down.
LANE_IN = 5.0
LANE_OUT = 19.0
# The paler patch inset in each stripe.
PATCH_IN = 8.0
PATCH_OUT = 16.0
PATCH_X0 = LENGTH * 0.08
PATCH_X1 = LENGTH * 0.36

ARC_STEP = 10.0        # degrees between the pipe's lengthwise edges elsewhere

# Rails: capsules lying along the outer part of each deck, with gaps between
# one section's rail and the next.
RAIL_R = 0.85
RAIL_LEN = LENGTH * 0.62           # overall, caps included
RAIL_Y = RADIUS + DECK_W * 0.62
RAIL_SIDES = 12
RAIL_CAP_RINGS = 4

# The arch of spheres over the pipe.
SPHERE_R = 1.25
ARCH_R = RADIUS + 1.6              # from the pipe's axis
ARCH_COUNT = 9
ARCH_FROM = 12.0                   # degrees up from the rim, first sphere
SPHERE_SEGS = 12
SPHERE_RINGS = 8

# --- flat colours, sampled from the reference --------------------------------
COLOURS = {
    "Pipe":   (0.000, 0.400, 1.000),
    "Deck":   (0.720, 0.470, 0.000),
    "Hoop":   (0.900, 0.600, 0.050),
    "Lane":   (1.000, 0.780, 0.000),
    "Patch":  (1.000, 0.900, 0.350),
    "Rail":   (1.000, 0.930, 0.000),
    "Sphere": (1.000, 0.520, 0.050),
}
SLOTS = list(COLOURS)


def srgb_to_linear(c):
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def make_material(name, rgb):
    mat = bpy.data.materials.new(name)
    lin = tuple(srgb_to_linear(c) for c in rgb) + (1.0,)
    mat.diffuse_color = lin                      # what the viewport's solid mode shows
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    if bsdf is not None:
        bsdf.inputs["Base Color"].default_value = lin
        bsdf.inputs["Roughness"].default_value = 0.25 if name == "Sphere" else 0.7
    return mat


def stations(breaks, lo, hi, max_step):
    """Sorted cut positions: every requested break, then enough extra cuts that
    no gap is wider than max_step."""
    pts = sorted(set([lo, hi] + [b for b in breaks if lo < b < hi]))
    out = [pts[0]]
    for a, b in zip(pts, pts[1:]):
        n = max(1, int(math.ceil((b - a) / max_step - 1e-9)))
        for k in range(1, n + 1):
            out.append(a + (b - a) * k / n)
    return out


def build_pipe(bm):
    xs = stations([HOOP_X - HOOP_W * 0.5, HOOP_X + HOOP_W * 0.5, PATCH_X0, PATCH_X1],
                  0.0, LENGTH, MAX_STEP)
    arc_breaks = []
    for a in (LANE_IN, LANE_OUT, PATCH_IN, PATCH_OUT):
        arc_breaks += [a, -a]
    angles = stations(arc_breaks, -90.0, 90.0, ARC_STEP)

    # Cross-section, left rim to right rim through the floor, then the decks.
    #   (y, z, kind) where kind says what the strip ENDING at this point is.
    profile = [(-(RADIUS + DECK_W), RADIUS - DECK_DROP, None),
               (-(RADIUS + DECK_W), RADIUS, "wall"),
               (-RADIUS, RADIUS, "deck")]
    for a in angles[1:]:
        r = math.radians(a)
        profile.append((RADIUS * math.sin(r), RADIUS - RADIUS * math.cos(r), ("arc", a)))
    profile += [(RADIUS + DECK_W, RADIUS, "deck"),
                (RADIUS + DECK_W, RADIUS - DECK_DROP, "wall")]

    grid = [[bm.verts.new((x, y, z)) for (y, z, _) in profile] for x in xs]

    for i in range(len(xs) - 1):
        xm = (xs[i] + xs[i + 1]) * 0.5
        for j in range(1, len(profile)):
            kind = profile[j][2]
            if kind in ("deck", "wall"):
                slot = "Deck"
            else:
                # Decide by the middle of the face, so an edge sitting exactly on
                # a boundary cannot fall on the wrong side of it.
                a_mid = abs((angles[j - 3] + angles[j - 2]) * 0.5)
                in_hoop = abs(xm - HOOP_X) < HOOP_W * 0.5
                if in_hoop:
                    slot = "Hoop"
                elif PATCH_IN < a_mid < PATCH_OUT and PATCH_X0 < xm < PATCH_X1:
                    slot = "Patch"
                elif LANE_IN < a_mid < LANE_OUT:
                    slot = "Lane"
                else:
                    slot = "Pipe"
            # Wound so the normals face into the pipe and up off the decks.
            f = bm.faces.new((grid[i][j - 1], grid[i + 1][j - 1], grid[i + 1][j], grid[i][j]))
            f.material_index = SLOTS.index(slot)
            f.smooth = kind not in ("deck", "wall")


def build_sphere(bm, centre, radius, slot):
    cx, cy, cz = centre
    rings = []
    for r in range(1, SPHERE_RINGS):
        phi = math.pi * r / SPHERE_RINGS
        ring = []
        for s in range(SPHERE_SEGS):
            th = 2.0 * math.pi * s / SPHERE_SEGS
            ring.append(bm.verts.new((cx + radius * math.sin(phi) * math.cos(th),
                                      cy + radius * math.sin(phi) * math.sin(th),
                                      cz + radius * math.cos(phi))))
        rings.append(ring)
    top = bm.verts.new((cx, cy, cz + radius))
    bot = bm.verts.new((cx, cy, cz - radius))
    idx = SLOTS.index(slot)

    def face(vs):
        f = bm.faces.new(vs)
        f.material_index = idx
        f.smooth = True

    for s in range(SPHERE_SEGS):
        n = (s + 1) % SPHERE_SEGS
        face((top, rings[0][s], rings[0][n]))
        for r in range(len(rings) - 1):
            face((rings[r][s], rings[r + 1][s], rings[r + 1][n], rings[r][n]))
        face((rings[-1][s], bot, rings[-1][n]))


def build_rail(bm, y, z):
    """A capsule along X: a tube with a hemisphere on each end."""
    x0 = (LENGTH - RAIL_LEN) * 0.5 + RAIL_R
    x1 = (LENGTH + RAIL_LEN) * 0.5 - RAIL_R
    idx = SLOTS.index("Rail")

    # Rings from the tip of one cap to the tip of the other.
    rings = []
    for k in range(1, RAIL_CAP_RINGS + 1):                      # near cap, tip inward
        a = (math.pi * 0.5) * k / RAIL_CAP_RINGS
        rings.append((x0 - RAIL_R * math.cos(a), RAIL_R * math.sin(a)))
    body = stations([], x0, x1, MAX_STEP)
    for x in body[1:]:
        rings.append((x, RAIL_R))
    for k in range(RAIL_CAP_RINGS - 1, 0, -1):                  # far cap
        a = (math.pi * 0.5) * k / RAIL_CAP_RINGS
        rings.append((x1 + RAIL_R * math.cos(a), RAIL_R * math.sin(a)))

    loops = []
    for x, r in rings:
        loops.append([bm.verts.new((x, y + r * math.cos(2.0 * math.pi * s / RAIL_SIDES),
                                    z + r * math.sin(2.0 * math.pi * s / RAIL_SIDES)))
                      for s in range(RAIL_SIDES)])
    tip0 = bm.verts.new((x0 - RAIL_R, y, z))
    tip1 = bm.verts.new((x1 + RAIL_R, y, z))

    def face(vs):
        f = bm.faces.new(vs)
        f.material_index = idx
        f.smooth = True

    for s in range(RAIL_SIDES):
        n = (s + 1) % RAIL_SIDES
        face((tip0, loops[0][n], loops[0][s]))
        for k in range(len(loops) - 1):
            face((loops[k][s], loops[k][n], loops[k + 1][n], loops[k + 1][s]))
        face((loops[-1][s], loops[-1][n], tip1))


def main():
    bpy.ops.wm.read_factory_settings(use_empty=True)

    mats = [make_material("HP_" + n, COLOURS[n]) for n in SLOTS]

    bm = bmesh.new()
    build_pipe(bm)
    for side in (-1.0, 1.0):
        build_rail(bm, side * RAIL_Y, RADIUS + RAIL_R)
    for k in range(ARCH_COUNT):
        deg = ARCH_FROM + (180.0 - 2.0 * ARCH_FROM) * k / (ARCH_COUNT - 1)
        r = math.radians(deg)
        build_sphere(bm, (HOOP_X, ARCH_R * math.cos(r), RADIUS + ARCH_R * math.sin(r)),
                     SPHERE_R, "Sphere")
    bm.normal_update()

    me = bpy.data.meshes.new("HalfPipeSection")
    bm.to_mesh(me)
    bm.free()
    for m in mats:
        me.materials.append(m)

    ob = bpy.data.objects.new("HalfPipeSection", me)
    bpy.context.scene.collection.objects.link(ob)

    xs = [v.co.x for v in me.vertices]
    tris = sum(len(p.vertices) - 2 for p in me.polygons)
    print("\nsection: %d verts, %d tris" % (len(me.vertices), tris))
    print("x range %.3f .. %.3f (must be exactly 0 .. %.1f to tile)" % (min(xs), max(xs), LENGTH))
    used = {}
    for p in me.polygons:
        used[SLOTS[p.material_index]] = used.get(SLOTS[p.material_index], 0) + 1
    print("faces per colour:", used)

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=os.path.abspath(OUT))
    print("saved", os.path.abspath(OUT))


if __name__ == "__main__":
    main()
