"""Model the bomb.

    blender -b --python native/gen_bomb.py -- [render]

Writes external/bomb/Bomb.blend, and with `render` a picture beside it. After the
reference the project's owner gave: a black ball caged by three red ribbed bands, each
between two dark rails; a red bullet-shaped stud on a dark collar wherever two bands
cross (the six poles); a silver pyramid spike in the middle of each of the eight panels
between them.

One mesh, origin at its centre, three material slots. As with the pipe, the colours are
the mesh's own faces -- no textures -- and as with the ring, how they finally look (the
red's glow) is Octave's material's job; the colours here are so it reads in Blender.

It is symmetrical about all three axes, so it can spin about any of them.
"""

import math
import os
import sys

import bmesh
import bpy
from mathutils import Matrix, Vector

HERE = os.path.dirname(os.path.abspath(__file__))
OUT_DIR = os.path.abspath(os.path.join(HERE, "..", "external", "bomb"))
args = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
RENDER = "render" in args

# --- dimensions. The ring is 1.24 to its outer edge; the bomb is a little bigger. -------
CORE = 1.0                  # the black ball
CORE_SEGS, CORE_RINGS = 16, 8

BAND_R = 1.0                # a band's centre line, from the bomb's centre
BAND_TUBE = 0.17            # half its width at a rib
BAND_WAIST = 0.70           # ...and between ribs, as a share of that
BAND_SQUASH = 0.55          # how far it stands off the ball, as a share of its width: a strip, not a tube
RIBS = 28                   # ribs round one band: seven between one stud and the next
BAND_SIDES = 6

RAIL_OFFSET = 0.235         # a rail's distance to either side of its band
RAIL_TUBE = 0.05
RAIL_SEGS, RAIL_SIDES = 28, 3

STUD_COLLAR_R, STUD_COLLAR_H = 0.37, 0.08
STUD_R, STUD_H = 0.29, 0.36          # the red bullet: a dome with a point, not a horn
STUD_SIDES = 10

SPIKE_R, SPIKE_H = 0.30, 0.36        # the silver pyramids: the ball must still read as round
SPIKE_SIDES = 4

COLOURS = {
    "Bomb_Body":  (0.030, 0.025, 0.035),     # ball, rails, collars
    "Bomb_Red":   (0.900, 0.030, 0.090),     # bands and studs
    "Bomb_Spike": (0.860, 0.870, 0.900),     # silver; the metal itself is Octave's material's job
}
SLOTS = list(COLOURS)
BODY, RED, SPIKE = 0, 1, 2


def srgb_to_linear(c):
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def make_material(name, rgb, glow=0.0, metal=0.0):
    mat = bpy.data.materials.new(name)
    lin = tuple(srgb_to_linear(c) for c in rgb) + (1.0,)
    mat.diffuse_color = lin
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    if bsdf is not None:
        bsdf.inputs["Base Color"].default_value = lin
        bsdf.inputs["Roughness"].default_value = 0.22 if metal else 0.35
        bsdf.inputs["Metallic"].default_value = metal
        if glow and "Emission Color" in bsdf.inputs:
            bsdf.inputs["Emission Color"].default_value = lin
            bsdf.inputs["Emission Strength"].default_value = glow
    return mat


def facing(direction):
    """A rotation taking +Z to `direction`."""
    return Vector((0, 0, 1)).rotation_difference(Vector(direction).normalized()).to_matrix().to_4x4()


def quad_strip(bm, loops, slot, smooth, closed=True):
    """Faces between consecutive loops of verts; each loop is itself closed."""
    pairs = list(zip(loops, loops[1:] + ([loops[0]] if closed else [])))
    if not closed:
        pairs = pairs[:len(loops) - 1]
    for a, b in pairs:
        n = len(a)
        for j in range(n):
            f = bm.faces.new((a[j], a[(j + 1) % n], b[(j + 1) % n], b[j]))
            f.material_index = slot
            f.smooth = smooth


def add_ball(bm):
    loops = []
    for i in range(1, CORE_RINGS):
        t = math.pi * i / CORE_RINGS
        loops.append([bm.verts.new((CORE * math.sin(t) * math.cos(2 * math.pi * j / CORE_SEGS),
                                    CORE * math.sin(t) * math.sin(2 * math.pi * j / CORE_SEGS),
                                    CORE * math.cos(t))) for j in range(CORE_SEGS)])
    quad_strip(bm, loops, BODY, True, closed=False)
    for loop, z, flip in ((loops[0], CORE, False), (loops[-1], -CORE, True)):
        tip = bm.verts.new((0, 0, z))
        for j in range(CORE_SEGS):
            a, b = loop[j], loop[(j + 1) % CORE_SEGS]
            f = bm.faces.new((tip, b, a) if flip else (tip, a, b))
            f.material_index = BODY
            f.smooth = True


def add_torus(bm, matrix, major, tube_of, segs, sides, slot, smooth, z=0.0, squash=1.0):
    """A torus in the XY plane, lifted by z, under `matrix`. tube_of(i) is its thickness at
    segment i, which is how a band gets its ribs."""
    loops = []
    for i in range(segs):
        u = 2.0 * math.pi * i / segs
        r = tube_of(i)
        loop = []
        for j in range(sides):
            v = 2.0 * math.pi * j / sides
            d = major + r * squash * math.cos(v)
            loop.append(bm.verts.new(matrix @ Vector((d * math.cos(u), d * math.sin(u), z + r * math.sin(v)))))
        loops.append(loop)
    quad_strip(bm, loops, slot, smooth)


def add_cone(bm, matrix, base, profile, sides, slot, smooth):
    """A spike standing on the ball along +Z under `matrix`. profile is [(radius, height)],
    from its foot to just short of its tip; the last entry's height is the tip's."""
    loops = []
    for radius, height in profile[:-1]:
        loops.append([bm.verts.new(matrix @ Vector((radius * math.cos(2 * math.pi * j / sides + math.pi / sides),
                                                   radius * math.sin(2 * math.pi * j / sides + math.pi / sides),
                                                   base + height))) for j in range(sides)])
    quad_strip(bm, loops, slot, smooth, closed=False)
    tip = bm.verts.new(matrix @ Vector((0, 0, base + profile[-1][1])))
    top = loops[-1]
    for j in range(sides):
        f = bm.faces.new((top[j], top[(j + 1) % sides], tip))
        f.material_index = slot
        f.smooth = smooth


def build():
    bm = bmesh.new()
    add_ball(bm)

    # Three bands, one about each axis, each between two rails.
    ribbed = lambda i: BAND_TUBE * (1.0 if i % 2 == 0 else BAND_WAIST)
    for axis in ((0, 0, 1), (1, 0, 0), (0, 1, 0)):
        m = facing(axis)
        add_torus(bm, m, BAND_R, ribbed, RIBS * 2, BAND_SIDES, RED, True, squash=BAND_SQUASH)
        for side in (-1, 1):
            z = side * RAIL_OFFSET
            rail_r = math.sqrt(max((CORE + RAIL_TUBE * 0.6) ** 2 - z * z, 0.0))
            add_torus(bm, m, rail_r, lambda i: RAIL_TUBE, RAIL_SEGS, RAIL_SIDES, BODY, True, z=z)

    # A stud at each of the six poles, where two bands cross.
    for axis in ((1, 0, 0), (-1, 0, 0), (0, 1, 0), (0, -1, 0), (0, 0, 1), (0, 0, -1)):
        m = facing(axis)
        foot = CORE - 0.06
        add_cone(bm, m, foot, [(STUD_COLLAR_R, 0.0), (STUD_COLLAR_R, STUD_COLLAR_H + 0.12),
                               (STUD_R * 0.9, STUD_COLLAR_H + 0.12), (0, STUD_COLLAR_H + 0.12)],
                 STUD_SIDES, BODY, True)
        add_cone(bm, m, foot + STUD_COLLAR_H,
                 [(STUD_R, 0.0), (STUD_R * 0.94, STUD_H * 0.28), (STUD_R * 0.72, STUD_H * 0.55),
                  (STUD_R * 0.36, STUD_H * 0.78), (0, STUD_H)],
                 STUD_SIDES, RED, True)

    # A pyramid in the middle of each of the eight panels.
    for sx in (-1, 1):
        for sy in (-1, 1):
            for sz in (-1, 1):
                add_cone(bm, facing((sx, sy, sz)), CORE - 0.08, [(SPIKE_R, 0.0), (0, SPIKE_H)],
                         SPIKE_SIDES, SPIKE, False)

    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    me = bpy.data.meshes.new("Bomb")
    bm.to_mesh(me)
    bm.free()
    return me


def main():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    me = build()
    for name in SLOTS:
        me.materials.append(make_material(name, COLOURS[name], glow=0.6 if name == "Bomb_Red" else 0.0,
                                          metal=0.35 if name == "Bomb_Spike" else 0.0))
    ob = bpy.data.objects.new("Bomb", me)
    scene = bpy.context.scene
    scene.collection.objects.link(ob)

    tris = sum(len(p.vertices) - 2 for p in me.polygons)
    reach = max(v.co.length for v in me.vertices)
    print("\nbomb: %d verts, %d tris, reaches %.3f from its centre" % (len(me.vertices), tris, reach))

    sun = bpy.data.objects.new("Sun", bpy.data.lights.new("Sun", 'SUN'))
    sun.data.energy = 3.5
    sun.rotation_euler = (math.radians(50), 0.0, math.radians(-40))
    scene.collection.objects.link(sun)
    fill = bpy.data.objects.new("Fill", bpy.data.lights.new("Fill", 'SUN'))
    fill.data.energy = 1.2
    fill.rotation_euler = (math.radians(110), 0.0, math.radians(140))
    scene.collection.objects.link(fill)
    world = bpy.data.worlds.new("World")
    world.use_nodes = True
    world.node_tree.nodes["Background"].inputs[0].default_value = (0.02, 0.06, 0.14, 1.0)
    scene.world = world
    scene.view_settings.view_transform = 'Standard'

    cam_data = bpy.data.cameras.new("Camera")
    cam_data.lens = 60.0
    cam = bpy.data.objects.new("Camera", cam_data)
    pos = Vector((5.2, -4.6, 3.4))
    cam.location = pos
    cam.rotation_euler = (Vector((0, 0, 0)) - pos).to_track_quat('-Z', 'Y').to_euler()
    scene.collection.objects.link(cam)
    scene.camera = cam

    os.makedirs(OUT_DIR, exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(OUT_DIR, "Bomb.blend"))
    print("saved", os.path.join(OUT_DIR, "Bomb.blend"))

    if RENDER:
        for engine in ('BLENDER_EEVEE', 'BLENDER_EEVEE_NEXT'):
            try:
                scene.render.engine = engine
                break
            except TypeError:
                pass
        scene.render.resolution_x = scene.render.resolution_y = 640
        scene.render.filepath = os.path.join(OUT_DIR, "Bomb_preview.png")
        bpy.ops.render.render(write_still=True)


main()
