"""The intro: Sonic pops up from behind the emblem's ribbon, settles with a hand over it and gives
a thumbs up.

    blender -b -P native/gen_intro_anim.py [-- check 60,12] [-- render]
        reads  external/intro/Emblem.blend             the emblem, as finished by hand (only read)
               external/sonic/Sonic_Rigged_Anim.blend  his rig
        -> external/intro/Intro.blend                  the emblem, Sonic and the action IntroPop
           check: those frames, half size, to external/intro/check_####.png
           render: every frame to external/intro/frames/####.png

He has no legs here (nothing of him shows below the ribbon), and anything of him below CUT_Z is
not drawn: that is what lets him rise out from behind the ribbon rather than up the front of the
ring. The ribbon is brought forward RIBBON_FORWARD to give his chest and arms room in front of the
ring.

Poses are world-space swings per bone, as in anim_sonic.py: +X is his span (the thumbs-up arm, R,
is on +X, the right of the screen), -Y is forward (toward the camera), +Z up. A positive X swing
takes a hanging limb backwards; the torso bone points up, so for it a positive X tips it forward.
"""
import math
import os
import sys

import bmesh
import bpy
from mathutils import Matrix, Vector

HERE = os.path.dirname(os.path.abspath(__file__))
INTRO = os.path.abspath(os.path.join(HERE, "..", "external", "intro"))
EMBLEM = os.path.join(INTRO, "Emblem.blend")
SONIC = os.path.abspath(os.path.join(HERE, "..", "external", "sonic", "Sonic_Rigged_Anim.blend"))
OUT = os.path.join(INTRO, "Intro.blend")

ARGS = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []

# ------------------------------------------------------------------ placing him
SCALE = 0.18                        # his head about as wide as the ring's hole
HOME = Vector((-0.08, -0.40, -1.42))  # his feet (were they there), in the final pose
TURN = -8.0                         # his body turned this far (+ toward the thumbs-up side)
RIBBON_FORWARD = 0.55
CUT_Z = -0.50                       # nothing of him shows below this (it is behind the ribbon)
THUMB_SINK = 0.4                    # the thumb seated this far down into the fist (rig units)
LEGS = ("L_higher_leg", "R_higher_leg", "L_middle_leg", "R_middle_leg", "L_lower_leg",
        "R_lower_leg", "L_sock", "R_sock", "L_foot", "R_foot")

# ------------------------------------------------------------------ timing (24 a second)
FPS = 24
F_POP = 10          # he starts up
F_TOP = 16          # the top of the pop, a little above where he settles
F_SET = 24          # settled
F_POSE = 34         # hand on the ribbon, thumb up
F_END = 96
DROP = -1.70        # how far below his place he starts: all of him under CUT_Z
OVERSHOOT = 0.12


def ease_out(t):
    t = max(0.0, min(1.0, t))
    return 1.0 - (1.0 - t) ** 3


def ease_in_out(t):
    t = max(0.0, min(1.0, t))
    return t * t * (3.0 - 2.0 * t)


# ------------------------------------------------------------------ the scene
REPOSE = bool(ARGS) and ARGS[0] == "repose"


def build():
    """The emblem with Sonic in it, from scratch (overwrites any hand edits in Intro.blend)."""
    bpy.ops.wm.open_mainfile(filepath=EMBLEM)
    scene = bpy.context.scene
    bpy.data.objects["Ribbon"].location.y -= RIBBON_FORWARD

    with bpy.data.libraries.load(SONIC, link=False) as (src, dst):
        dst.objects = [n for n in src.objects if n in ("Armature", "Sonic")]
    for ob in dst.objects:
        scene.collection.objects.link(ob)
    arm = bpy.data.objects["Armature"]
    son = bpy.data.objects["Sonic"]
    bones = arm.data.bones
    pose = arm.pose

    # No legs: every vertex mostly carried by a leg bone goes.
    legs = {son.vertex_groups[n].index for n in LEGS}
    bm = bmesh.new()
    bm.from_mesh(son.data)
    dl = bm.verts.layers.deform.active
    kill = []
    for v in bm.verts:
        w = v[dl]
        if w and max(w.items(), key=lambda gw: gw[1])[0] in legs:
            kill.append(v)
    bmesh.ops.delete(bm, geom=kill, context="VERTS")
    bm.to_mesh(son.data)
    bm.free()

    # Nothing of him below CUT_Z: each of his materials goes clear there.
    for m in son.data.materials:
        if m is None:
            continue
        m.use_nodes = True
        nt = m.node_tree
        out = next((n for n in nt.nodes if n.type == "OUTPUT_MATERIAL" and n.is_active_output), None)
        if out is None or not out.inputs["Surface"].links:
            continue
        shader = out.inputs["Surface"].links[0].from_socket
        geo = nt.nodes.new("ShaderNodeNewGeometry")
        sep = nt.nodes.new("ShaderNodeSeparateXYZ")
        above = nt.nodes.new("ShaderNodeMath")
        above.operation = "GREATER_THAN"
        above.inputs[1].default_value = CUT_Z
        clear_ = nt.nodes.new("ShaderNodeBsdfTransparent")
        mix = nt.nodes.new("ShaderNodeMixShader")
        nt.links.new(geo.outputs["Position"], sep.inputs[0])
        nt.links.new(sep.outputs["Z"], above.inputs[0])
        nt.links.new(above.outputs[0], mix.inputs[0])
        nt.links.new(clear_.outputs[0], mix.inputs[1])
        nt.links.new(shader, mix.inputs[2])
        nt.links.new(mix.outputs[0], out.inputs["Surface"])
        if hasattr(m, "surface_render_method"):
            m.surface_render_method = "DITHERED"

    # His textures travel with the file.
    for img in bpy.data.images:
        if img.source == "FILE" and not img.packed_file:
            try:
                img.pack()
            except RuntimeError as e:
                print("could not pack %s: %s" % (img.name, e))

    arm.scale = (SCALE, SCALE, SCALE)
    arm.rotation_mode = "XYZ"
    arm.rotation_euler = (0.0, 0.0, math.radians(TURN))
    for pb in pose.bones:
        pb.rotation_mode = "QUATERNION"


if REPOSE:      # pose again what is in Intro.blend, keeping what was moved there by hand
    bpy.ops.wm.open_mainfile(filepath=OUT)
else:
    build()
scene = bpy.context.scene
arm = bpy.data.objects["Armature"]
son = bpy.data.objects["Sonic"]
ribbon = bpy.data.objects["Ribbon"]
bones = arm.data.bones
pose = arm.pose


# ------------------------------------------------------------------ posing (as anim_sonic.py)
def set_rot(name, *rots):
    pb = pose.bones[name]
    R = Matrix.Identity(3)
    for axis, deg in rots:
        R = Matrix.Rotation(math.radians(deg), 3, axis) @ R
    rest = bones[name].matrix_local.to_3x3()
    pb.rotation_quaternion = (rest.inverted() @ R @ rest).to_quaternion()


def clear():
    for pb in pose.bones:
        pb.rotation_quaternion = (1.0, 0.0, 0.0, 0.0)
        pb.location = (0.0, 0.0, 0.0)
        pb.scale = (1.0, 1.0, 1.0)


def part_verts(name):
    gi = son.vertex_groups[name].index
    return [v.co.copy() for v in son.data.vertices
            if any(g.group == gi and g.weight > 0.5 for g in v.groups)]


def deform(name):
    """Bone `name`'s deformation, armature rest space -> armature posed space."""
    return pose.bones[name].matrix @ bones[name].matrix_local.inverted()


def planted_thumb(side):
    """The thumb's matrix_basis that stands it on top of the fist, pointing straight up, for the
    pose the arm is in now. The thumb is placed outright in rest space (see anim_sonic.py's
    plant_thumb): its base on the top of the fist, its axis turned to what the palm's deformation
    carries to straight up."""
    bpy.context.view_layer.update()
    thumb = part_verts("%s_thumb" % side)
    fist_ = part_verts("%s_palm" % side) + part_verts("%s_finger" % side)
    zs = [v.z for v in thumb]
    base = [v for v in thumb if v.z > max(zs) - 0.1]
    tip = [v for v in thumb if v.z < min(zs) + 0.1]
    base_c = sum(base, Vector()) / len(base)
    axis = (sum(tip, Vector()) / len(tip) - base_c).normalized()

    D = deform("%s_palm" % side)
    posed = [D @ v for v in fist_]
    top = max(p.z for p in posed)
    crown = [p for p in posed if p.z > top - 0.35]
    seat_world = sum(crown, Vector()) / len(crown) - Vector((0, 0, THUMB_SINK))
    target = D.inverted() @ seat_world
    want = (D.to_3x3().inverted() @ Vector((0, 0, 1))).normalized()
    turn = axis.rotation_difference(want).to_matrix().to_4x4()
    place = Matrix.Translation(target) @ turn @ Matrix.Translation(-base_c)
    rest = bones["%s_thumb" % side].matrix_local
    return rest.inverted() @ place @ rest


def lerp(a, b, t):
    return a + (b - a) * t


# ------------------------------------------------------------------ the poses
# Only real joints move: the shoulder points the upper arm (no twist), the elbow bends at one
# joint, the forearm may turn the palm over, the wrist bends toward the palm, the fingers curl.
# The cuff and the arm's middle bone stay as modelled.
SIGN = {"L": -1.0, "R": 1.0}        # L is on -X, R on +X


def set_arm(side, a):
    """a: lift, the upper arm from hanging (0) through level (90) to straight up (180); az, which
    way, 0 forward to 90 out to his side; elbow, its bend, forward; turn, the forearm turning the
    palm over (90: palm down once the forearm is level); flex, the wrist, toward the palm; curl,
    the fingers; roll, the shoulder turning the whole arm about itself (so the elbow can bend up)."""
    s = SIGN[side]
    lift, az = math.radians(a["lift"]), math.radians(a["az"])
    d = Vector((s * math.sin(lift) * math.sin(az), -math.sin(lift) * math.cos(az), -math.cos(lift)))
    rest = bones["%s_upper_arm" % side].matrix_local.to_3x3()
    q = Vector((0, 0, -1)).rotation_difference(d).to_matrix() @ Matrix.Rotation(
        math.radians(-s * a.get("roll", 0.0)), 3, "Z")     # roll: the shoulder turning the arm in
    pose.bones["%s_upper_arm" % side].rotation_quaternion = (rest.inverted() @ q @ rest).to_quaternion()
    set_rot("%s_lower_arm" % side, ("Z", -s * a.get("turn", 0.0)), ("X", -a["elbow"]))
    set_rot("%s_palm" % side, ("Y", s * a.get("flex", 0.0)))
    set_rot("%s_finger" % side, ("Y", s * a.get("curl", 20.0)))
    set_rot("%s_thumb" % side, ("Y", s * a.get("thumb", 25.0)))


def torso(lean=0.0, nod=0.0, look=0.0, tilt=0.0):
    """lean: the body forward; nod: the head down; look: the head turned toward the R (thumb)
    side; tilt: its top toward that side."""
    set_rot("Body", ("X", lean))
    set_rot("Head", ("X", nod), ("Z", look), ("Y", tilt))


def snapshot():
    bpy.context.view_layer.update()
    return {pb.name: (pb.rotation_quaternion.copy(), pb.location.copy()) for pb in pose.bones}


def knuckles(side):
    bpy.context.view_layer.update()
    return arm.matrix_world @ pose.bones["%s_palm" % side].tail


def frange(a, b, step):
    n = int((b - a) / step + 1e-6)
    return [a + step * i for i in range(n + 1)] + ([b] if a + step * n < b - 1e-6 else [])


def solve(side, want, others, ranges):
    """The shoulder's lift and direction and the elbow's bend that bring the knuckles nearest
    `want` (world): a coarse search, then finer around the best. `others`: turn, flex, curl."""
    best = None
    ranges = dict({"roll": (0.0, 0.0)}, **ranges)
    lo = {k: r[0] for k, r in ranges.items()}
    hi = {k: r[1] for k, r in ranges.items()}
    for step in (15.0, 5.0, 1.0):
        for lift in frange(lo["lift"], hi["lift"], step):
            for az in frange(lo["az"], hi["az"], step):
                for elbow in frange(lo["elbow"], hi["elbow"], step):
                    for roll in frange(lo["roll"], hi["roll"], step):
                        a = dict(others, lift=lift, az=az, elbow=elbow, roll=roll)
                        set_arm(side, a)
                        err = (knuckles(side) - want).length
                        if best is None or err < best[0]:
                            best = (err, a)
        b = best[1]
        lo = {k: max(ranges[k][0], b[k] - step) for k in ranges}
        hi = {k: min(ranges[k][1], b[k] + step) for k in ranges}
    err, a = best
    set_arm(side, a)
    print("solve %s: lift %.0f az %.0f elbow %.0f roll %.0f, %.3f from where wanted"
          % (side, a["lift"], a["az"], a["elbow"], a["roll"], err))
    return a


def ribbon_edge(x):
    """The ribbon's front (least y) and top (most z) near x, as drawn (its thickness counted)."""
    dg = bpy.context.evaluated_depsgraph_get()
    ev = ribbon.evaluated_get(dg)
    me = ev.to_mesh()
    vs = [ribbon.matrix_world @ v.co for v in me.vertices]
    vs = [v for v in vs if abs(v.x - x) < 0.05 and v.y < -0.2]
    front, top = min(v.y for v in vs), max(v.z for v in vs)
    ev.to_mesh_clear()
    return front, top


GRIP_X = -0.40                          # where his hand takes the ribbon (world x)
THUMB_AT = Vector((0.60, -0.72, 0.02))  # the thumbs-up fist's knuckles (world)

if arm.animation_data is not None:
    arm.animation_data.action = None
arm.location = HOME
for pb in pose.bones:
    pb.rotation_mode = "QUATERNION"
clear()

POSES = {}      # each key pose, as every bone's rotation


def keep(name, body, L, R, thumb=None):
    clear()
    torso(**body)
    set_arm("L", L)
    set_arm("R", R)
    if thumb is not None:
        pose.bones["R_thumb"].matrix_basis = thumb
    POSES[name] = snapshot()


DOWN = {"lift": 12.0, "az": 80.0, "elbow": 15.0}
keep("low", {}, DOWN, DOWN)
UP = {"lift": 145.0, "az": 75.0, "elbow": 20.0, "curl": 10.0}
keep("pop", {"lean": -6.0, "nod": -10.0}, UP, UP)
FALL = {"lift": 95.0, "az": 85.0, "elbow": 35.0, "curl": 30.0}
keep("fall", {"lean": 2.0, "nod": -2.0}, FALL, FALL)

# The final pose: the left hand over the ribbon's top edge, palm down, fingers hooked over its
# front; the right fist up in front of his shoulder, thumb up; his head turned to it.
FINAL_BODY = {"lean": 6.0, "nod": 4.0, "look": 14.0, "tilt": 10.0}
clear()
torso(**FINAL_BODY)
front, top = ribbon_edge(GRIP_X)
GRIP = solve("L", Vector((GRIP_X, front - 0.05, top + 0.035)),
             {"turn": 90.0, "flex": 15.0, "curl": 95.0, "thumb": 80.0},
             {"lift": (20.0, 110.0), "az": (-30.0, 50.0), "elbow": (0.0, 120.0)})
THUMB = solve("R", THUMB_AT, {"turn": 0.0, "flex": 0.0, "curl": 110.0},
              {"lift": (10.0, 90.0), "az": (0.0, 100.0), "elbow": (50.0, 140.0),
               "roll": (-120.0, 0.0)})
THUMB_BASIS = planted_thumb("R")
keep("final", FINAL_BODY, GRIP, THUMB, THUMB_BASIS)
keep("final_look", dict(FINAL_BODY, look=FINAL_BODY["look"] + 4.0, nod=FINAL_BODY["nod"] - 3.0),
     GRIP, THUMB, THUMB_BASIS)
# on the way: the left hand coming over the ribbon from above, the right fist rising
keep("reach", {"lean": 6.0, "look": 10.0, "tilt": 4.0},
     dict(GRIP, lift=GRIP["lift"] + 18.0, elbow=GRIP["elbow"] + 10.0, curl=40.0),
     dict(THUMB, lift=THUMB["lift"] - 10.0, elbow=THUMB["elbow"] - 40.0, curl=80.0))

# ------------------------------------------------------------------ the keys
# (frame, pose, height above his place); Blender's curves do the in-betweens
KEYS = [
    (1, "low", DROP), (F_POP, "low", DROP),
    (F_TOP, "pop", OVERSHOOT),
    (F_TOP + 4, "fall", -0.02),
    (F_TOP + 7, "fall", 0.0),
    (F_POSE - 6, "reach", 0.0),
    (F_POSE, "final", 0.0),
    (F_POSE + 4, "final_look", 0.0),
    (F_POSE + 30, "final", 0.0),
    (F_END, "final_look", 0.0),
]


def new_action(name):
    old = bpy.data.actions.get(name)
    if old is not None:
        bpy.data.actions.remove(old)
    act = bpy.data.actions.new(name)
    act.use_fake_user = True
    if arm.animation_data is None:
        arm.animation_data_create()
    arm.animation_data.action = act
    return act


act = new_action("IntroPop")
last = {}
for f, name, h in KEYS:
    for pb in pose.bones:
        q, l = POSES[name][pb.name]
        q = q.copy()
        if pb.name in last and last[pb.name].dot(q) < 0.0:    # the short way round
            q.negate()
        last[pb.name] = q
        pb.rotation_quaternion, pb.location = q, l
        pb.keyframe_insert("rotation_quaternion", frame=f)
        pb.keyframe_insert("location", frame=f)
    arm.location = HOME + Vector((0, 0, h))
    arm.keyframe_insert("location", frame=f)

scene.frame_start, scene.frame_end = 1, F_END
scene.render.fps = FPS
bpy.ops.wm.save_as_mainfile(filepath=OUT)
print("saved %s" % OUT)

# ------------------------------------------------------------------ renders
if ARGS and ARGS[0] == "check":
    scene.render.resolution_percentage = 100
    for f in [int(x) for x in ARGS[1].split(",")]:
        scene.frame_set(f)
        scene.render.filepath = os.path.join(INTRO, "check_%04d.png" % f)
        bpy.ops.render.render(write_still=True)
elif ARGS and ARGS[0] == "render":
    scene.render.filepath = os.path.join(INTRO, "frames", "")
    bpy.ops.render.render(animation=True)
