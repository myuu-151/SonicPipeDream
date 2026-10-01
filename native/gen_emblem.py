"""The winged ring emblem, built in Blender: a yellow band with blue rims, green and blue studs, a
pair of silver wings and a red-and-white ribbon across the front.

    blender -b -P native/gen_emblem.py
        -> external/intro/Emblem.blend           the model, materials and a camera
           external/intro/emblem_preview.png     a render of it, to set beside the reference

Everything is made from simple shapes so it can be changed by number: the ring's radii, how many
feathers and how long, the ribbon's sweep. Units: the ring's outer radius is 1. X right, Z up, the
emblem facing -Y (toward the camera).
"""
import math
import os

import bmesh
import bpy
from mathutils import Matrix, Vector

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.abspath(os.path.join(HERE, "..", "external", "intro"))

# ------------------------------------------------------------------ sizes
RING_IN, RING_OUT, RING_DEPTH = 0.66, 0.90, 0.16     # the yellow band
RIM_OUT, RIM_IN, RIM_THICK = 0.96, 0.62, 0.07        # the blue rims' centres and tube radius
STUD_R = 0.78                                         # the studs' circle
FEATHERS = 5
RIBBON_Z, RIBBON_W = -0.38, 0.36                      # the ribbon's middle height and width


def clear():
    bpy.ops.wm.read_factory_settings(use_empty=True)


def material(name, colour, metallic=0.0, roughness=0.3, coat=0.5):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    bsdf = m.node_tree.nodes.get("Principled BSDF")
    bsdf.inputs["Base Color"].default_value = (*colour, 1.0)
    bsdf.inputs["Metallic"].default_value = metallic
    bsdf.inputs["Roughness"].default_value = roughness
    for key in ("Coat Weight", "Clearcoat"):
        if key in bsdf.inputs:
            bsdf.inputs[key].default_value = coat
            break
    return m


def obj_from_bmesh(name, bm, mat, smooth=True, subsurf=0):
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    ob = bpy.data.objects.new(name, me)
    bpy.context.collection.objects.link(ob)
    if mat is not None:
        if isinstance(mat, (list, tuple)):
            for m in mat:
                me.materials.append(m)
        else:
            me.materials.append(mat)
    for p in me.polygons:
        p.use_smooth = smooth
    if subsurf:
        mod = ob.modifiers.new("Subsurf", "SUBSURF")
        mod.levels = subsurf
        mod.render_levels = subsurf
    return ob


def loft(sections, closed_section=True, cap=True):
    """A bmesh lofted through `sections`: lists of Vectors, all the same length, in order."""
    bm = bmesh.new()
    rows = [[bm.verts.new(v) for v in s] for s in sections]
    n = len(sections[0])
    for a, b in zip(rows, rows[1:]):
        for i in range(n if closed_section else n - 1):
            j = (i + 1) % n
            bm.faces.new((a[i], a[j], b[j], b[i]))
    if cap and closed_section:
        bm.faces.new(list(reversed(rows[0])))
        bm.faces.new(rows[-1])
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    return bm


def round_rect(w, h, r, steps=4):
    """A rounded rectangle in its own (u, v): w wide, h high, corners of radius r."""
    pts = []
    for cx, cy, a0 in ((w / 2 - r, h / 2 - r, 0), (-w / 2 + r, h / 2 - r, 90),
                       (-w / 2 + r, -h / 2 + r, 180), (w / 2 - r, -h / 2 + r, 270)):
        for k in range(steps + 1):
            a = math.radians(a0 + 90.0 * k / steps)
            pts.append((cx + r * math.cos(a), cy + r * math.sin(a)))
    return pts


# ------------------------------------------------------------------ the ring
def ring(mats):
    """The yellow band: a flat annulus, its edges rounded, facing -Y."""
    segs = 96
    prof = round_rect(RING_OUT - RING_IN, RING_DEPTH, 0.03)      # (radial, depth)
    sections = []
    for k in range(segs + 1):
        a = 2 * math.pi * k / segs
        c, s = math.cos(a), math.sin(a)
        mid = (RING_IN + RING_OUT) / 2
        sections.append([Vector(((mid + u) * c, v, (mid + u) * s)) for u, v in prof])
    bm = loft(sections, cap=False)
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-5)
    obj_from_bmesh("Ring", bm, mats["yellow"])


def torus(name, major, minor, mat, y=0.0):
    bm = bmesh.new()
    bmesh.ops.create_circle(bm, segments=24, radius=minor)
    # sweep the small circle round the big one
    segs = 96
    prof = [Vector((minor * math.cos(2 * math.pi * i / 24), minor * math.sin(2 * math.pi * i / 24))) for i in range(24)]
    bm.free()
    sections = []
    for k in range(segs + 1):
        a = 2 * math.pi * k / segs
        c, s = math.cos(a), math.sin(a)
        sections.append([Vector(((major + p.x) * c, y + p.y, (major + p.x) * s)) for p in prof])
    bm = loft(sections, cap=False)
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-5)
    return obj_from_bmesh(name, bm, mat)


def studs(mats):
    """Twelve round the band, every 30 degrees from the top: a blue pyramid, then a green ball."""
    for k in range(12):
        a = math.radians(90 - 30 * k)
        c, s = math.cos(a), math.sin(a)
        at = Vector((STUD_R * c, -RING_DEPTH / 2, STUD_R * s))
        if k % 2 == 0:
            # a three-sided pyramid, flat on the band, pointing out from the middle
            bm = bmesh.new()
            out = Vector((c, 0, s))
            side = Vector((-s, 0, c))
            size = 0.09
            tip = at + out * size * 1.15 + Vector((0, -0.05, 0))
            base = [at - out * size * 0.6 + side * size, at - out * size * 0.6 - side * size, at + out * size * 1.15]
            bv = [bm.verts.new(v) for v in base]
            tv = bm.verts.new(at + Vector((0, -0.07, 0)) + out * size * 0.15)
            bm.faces.new(bv)
            for i in range(3):
                bm.faces.new((bv[i], bv[(i + 1) % 3], tv))
            bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
            obj_from_bmesh("Pyramid%d" % k, bm, mats["navy"], smooth=False)
        else:
            bm = bmesh.new()
            bmesh.ops.create_uvsphere(bm, u_segments=20, v_segments=12, radius=0.045)
            bmesh.ops.translate(bm, verts=bm.verts, vec=at + Vector((0, -0.01, 0)))
            obj_from_bmesh("Stud%d" % k, bm, mats["green"])


# ------------------------------------------------------------------ the wings
def feather(side, i, mats):
    """Feather i of a wing (0 the top), on `side` (+1 right, -1 left): a broad, thick blade from
    behind the ring sweeping out, overlapping the one below like a shingle, its tip swept up and
    cut at a slant; each lower one a little shorter and further back."""
    t = i / (FEATHERS - 1)
    root_x = 0.62 + 0.06 * t
    length = 1.32 - 0.50 * t
    z_mid = 0.60 - 0.235 * i
    h0 = 0.25
    depth = 0.15
    steps = 24
    sections = []
    for k in range(steps + 1):
        u = k / steps
        x = root_x + length * u
        rise = 0.16 * u * u                     # the blade curls up toward its tip
        top = z_mid + h0 / 2 + rise
        bottom = z_mid - h0 / 2 + rise + 0.13 * u ** 3      # the tip cut at a slant, up and out
        h = max(top - bottom, 0.04)
        y = 0.05 + 0.045 * i                    # each lower feather further back: shingles
        prof = round_rect(depth, h, min(0.06, h / 2.2), steps=6)
        sections.append([Vector((side * x, y + pu, (top + bottom) / 2 + pv)) for pu, pv in prof])
    bm = loft(sections)
    return obj_from_bmesh("Feather%s%d" % ("R" if side > 0 else "L", i), bm, mats["silver"], subsurf=2)


def wings(mats):
    for side in (1, -1):
        for i in range(FEATHERS):
            feather(side, i, mats)


# ------------------------------------------------------------------ the ribbon
def ribbon_band(name, path, width, mats, notch=0.0, ups=None):
    """A ribbon along `path` (Vectors), `width` across, three stripes: red, white, red. `ups` gives the
    direction across it at each point (Z if not given). With `notch`, both ends are cut in a V that
    deep."""
    bm = bmesh.new()
    stripes = (0.0, 0.28, 0.5, 0.72, 1.0)
    ups = ups or [Vector((0, 0, 1))] * len(path)
    arc = [0.0]                                # each point's distance along the path
    for a, b in zip(path, path[1:]):
        arc.append(arc[-1] + (b - a).length)
    total = arc[-1]

    def at(s):
        """The point and the across direction at distance `s` along the path."""
        s = min(max(s, 0.0), total)
        k = max(0, min(len(path) - 2, next((i for i in range(len(arc) - 1) if arc[i + 1] >= s), len(arc) - 2)))
        t = (s - arc[k]) / max(arc[k + 1] - arc[k], 1e-9)
        return path[k].lerp(path[k + 1], t), ups[k].lerp(ups[k + 1], t).normalized()

    # The V: each stripe ends `v` short of the tip, the middle most. The cut is spread over the
    # first and last SPREAD of the strip, so no row passes the one before it.
    SPREAD = min(0.6, total / 3)
    rows = []
    for k in range(len(path)):
        s = arc[k]
        row = []
        for f in stripes:
            v = notch * (1.0 - abs(f - 0.5) * 2.0)
            sf = s
            if s < SPREAD:
                sf = s + v * (1.0 - s / SPREAD)
            elif s > total - SPREAD:
                sf = s - v * (1.0 - (total - s) / SPREAD)
            p, up = at(sf)
            row.append(bm.verts.new(p + up * ((f - 0.5) * width)))
        rows.append(row)
    for a, b in zip(rows, rows[1:]):
        for s_ in range(4):
            f = bm.faces.new((a[s_], a[s_ + 1], b[s_ + 1], b[s_]))
            f.material_index = 1 if s_ in (1, 2) else 0
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    ob = obj_from_bmesh(name, bm, [mats["red"], mats["white"]])
    mod = ob.modifiers.new("Thick", "SOLIDIFY")
    mod.thickness = 0.025
    return ob


def ribbon(mats):
    """One strip, tip to tip: the left tail runs in behind the ring's front, folds twice (a Z fold,
    the outer fold showing at the middle's end) and comes out across the front, then folds the same
    way on the right and runs out to the right tail. Both tips are cut in a V."""
    MID_X, IN_X = 1.20, 0.98                   # the outer (seen) fold and the inner (hidden) one
    R = 0.035                                  # the folds' radius
    Y_TAIL, Y_MID = -0.10, -0.24               # the tail's depth, the middle's at its ends
    Z_TAIL = RIBBON_Z - 0.06                   # the tail's height where it meets the fold
    Z_UP = Vector((0, 0, 1))
    pts, ups = [], []

    # The tails bend down in one smooth curve, a little as they leave the fold and more toward the
    # tip: SLOPE at the fold, BEND more by the tip.
    SLOPE, BEND = 0.06, 0.14
    TAIL_LEN = 2.0 - IN_X

    def tail_z(w):                             # w: 0 at the fold, 1 at the tip
        return Z_TAIL - SLOPE * w - BEND * w * w

    def tail_up(side, w):                      # across the tail, square to it as it bends down
        slope = (tail_z(w - 0.01) - tail_z(w + 0.01)) / (0.02 * TAIL_LEN)
        return Vector((side * slope, 0, 1)).normalized()

    def fold(side, cx, cy, start, z0, z1, n=12):
        """Half a turn round (cx, cy), from the angle `start`, with the height going z0 -> z1."""
        for k in range(1, n + 1):
            a = start + side * math.pi * k / n
            pts.append(Vector((cx + R * math.cos(a), cy + R * math.sin(a), z0 + (z1 - z0) * k / n)))
            ups.append(Z_UP)

    # the left tail: from its tip in to the hidden fold, bending down toward the tip
    for k in range(41):
        u = k / 40
        w = 1 - u                              # 0 at the fold, 1 at the tip
        pts.append(Vector((-2.0 + TAIL_LEN * u, -0.05 + (Y_TAIL + 0.05) * u, tail_z(w))))
        ups.append(tail_up(-1, w))
    z_f = (Z_TAIL + RIBBON_Z) / 2
    fold(-1, -IN_X, Y_TAIL - R, math.pi / 2, Z_TAIL, z_f)          # round its right, now going left
    for k in range(1, 8):                                            # back along, between the folds
        pts.append(Vector((-IN_X - (MID_X - IN_X) * k / 8, Y_TAIL - 2 * R, z_f)))
        ups.append(Z_UP)
    fold(1, -MID_X, Y_TAIL - 3 * R, math.pi / 2, z_f, RIBBON_Z)     # round its left, now going right
    # the middle: across the front of the ring, arched up and bowed toward the camera
    for k in range(1, 48):
        u = k / 48 * 2 - 1
        pts.append(Vector((MID_X * u, Y_MID - 0.20 * (1 - u * u), RIBBON_Z + 0.08 * (1 - u * u))))
        ups.append(Z_UP)
    # and the right side, the left's mirror, run backwards
    left = len(pts) - 47
    for k in range(left - 1, -1, -1):
        p = pts[k]
        pts.append(Vector((-p.x, p.y, p.z)))
        ups.append(Vector((-ups[k].x, ups[k].y, ups[k].z)))
    ribbon_band("Ribbon", pts, RIBBON_W * 0.9, mats, notch=0.16, ups=ups)


# ------------------------------------------------------------------ scene
def scene():
    world = bpy.data.worlds.new("World")
    bpy.context.scene.world = world
    world.use_nodes = True
    # A STUDIO FOR THE METAL TO MIRROR, seen only in reflections: bright overhead, a soft horizon,
    # dark below. The camera itself sees black (Light Path: Is Camera Ray).
    nt = world.node_tree
    bg = nt.nodes.get("Background")
    out = nt.nodes.get("World Output")
    coord = nt.nodes.new("ShaderNodeTexCoord")
    sep = nt.nodes.new("ShaderNodeSeparateXYZ")
    ramp = nt.nodes.new("ShaderNodeValToRGB")
    ramp.color_ramp.elements[0].position = 0.35
    ramp.color_ramp.elements[0].color = (0.02, 0.02, 0.03, 1.0)
    ramp.color_ramp.elements[1].position = 0.75
    ramp.color_ramp.elements[1].color = (1.0, 1.0, 1.0, 1.0)
    mid = ramp.color_ramp.elements.new(0.52)
    mid.color = (0.35, 0.37, 0.42, 1.0)
    remap = nt.nodes.new("ShaderNodeMapRange")              # z -1..1 -> 0..1
    remap.inputs["From Min"].default_value = -1.0
    nt.links.new(coord.outputs["Generated"], sep.inputs[0])
    nt.links.new(sep.outputs["Z"], remap.inputs["Value"])
    nt.links.new(remap.outputs["Result"], ramp.inputs["Fac"])
    nt.links.new(ramp.outputs["Color"], bg.inputs["Color"])
    bg.inputs["Strength"].default_value = 0.6
    black = nt.nodes.new("ShaderNodeBackground")
    black.inputs["Color"].default_value = (0.0, 0.0, 0.0, 1.0)
    path = nt.nodes.new("ShaderNodeLightPath")
    mix = nt.nodes.new("ShaderNodeMixShader")
    nt.links.new(path.outputs["Is Camera Ray"], mix.inputs["Fac"])
    nt.links.new(bg.outputs["Background"], mix.inputs[1])
    nt.links.new(black.outputs["Background"], mix.inputs[2])
    nt.links.new(mix.outputs["Shader"], out.inputs["Surface"])
    # lights: a key from the upper left front, a fill, and a rim from above
    for name, loc, energy in (("Key", (-3, -5, 4), 900), ("Fill", (4, -4, 1), 350), ("Top", (0, 1, 6), 400)):
        ld = bpy.data.lights.new(name, "AREA")
        ld.energy = energy
        ld.size = 3.0
        lo = bpy.data.objects.new(name, ld)
        lo.location = loc
        lo.rotation_euler = (Vector(loc) * -1).to_track_quat("-Z", "Y").to_euler()
        bpy.context.collection.objects.link(lo)
    cam = bpy.data.cameras.new("Camera")
    cam.type = "ORTHO"
    cam.ortho_scale = 4.4
    co = bpy.data.objects.new("Camera", cam)
    co.location = (0, -8, 0.0)
    co.rotation_euler = (math.radians(90), 0, 0)
    bpy.context.collection.objects.link(co)
    bpy.context.scene.camera = co
    r = bpy.context.scene.render
    for engine in ("BLENDER_EEVEE_NEXT", "BLENDER_EEVEE"):
        try:
            r.engine = engine
            break
        except TypeError:
            continue
    r.resolution_x, r.resolution_y = 1736, 858
    bpy.context.scene.view_settings.view_transform = "Standard"
    r.film_transparent = False


def main():
    clear()
    mats = {
        "yellow": material("Yellow", (1.0, 0.72, 0.0), roughness=0.22),
        "blue": material("Blue", (0.0, 0.12, 0.75), roughness=0.18),
        "navy": material("Navy", (0.02, 0.02, 0.35), roughness=0.2),
        "green": material("Green", (0.0, 0.45, 0.03), roughness=0.12),
        # chrome: a metal, mirroring the studio round it (scene(): the camera still sees black)
        "silver": material("Silver", (0.92, 0.93, 0.96), metallic=1.0, roughness=0.1, coat=0.0),
        "red": material("Red", (0.8, 0.0, 0.01), roughness=0.22),
        "white": material("White", (0.95, 0.95, 0.95), roughness=0.3),
    }
    ring(mats)
    torus("RimOuter", RIM_OUT, RIM_THICK, mats["blue"], y=-0.02)
    torus("RimInner", RIM_IN, RIM_THICK * 0.9, mats["blue"], y=-0.02)
    studs(mats)
    wings(mats)
    ribbon(mats)
    scene()
    os.makedirs(OUT, exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(OUT, "Emblem.blend"))
    bpy.context.scene.render.filepath = os.path.join(OUT, "emblem_preview.png")
    bpy.ops.render.render(write_still=True)


main()
