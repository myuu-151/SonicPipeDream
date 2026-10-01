"""Super Sonic's flight: lying out flat along the way he flies, arms trailing behind him and spread
wide with open hands (Unleashed's), legs straight back, head up to see ahead, and a slow hover.

    blender -b external/supersonic/SuperSonic_Rigged_Anim2.blend -P native/anim_super_fly.py [-- views]
        -> the action "Fly" added to that file (saved in place; FLY_FRAMES + 1 keys, the last the
           first again, so it loops), and with -- views, external/supersonic/views/fly_*.png

Poses are world-space swings per bone, as in anim_sonic.py (+X his span, -Y forward, +Z up; a
positive X swing tips a hanging limb back, and the body, which points up, forward). Only real
joints turn: the root lays him out, the head lifts, the shoulders, elbows and wrists fold the arms,
the hips and knees keep the legs straight, the ankles point the toes.
"""
import math
import os
import sys

import bpy
from mathutils import Matrix, Quaternion

HERE = os.path.dirname(os.path.abspath(__file__))
FOLDER = os.path.abspath(os.path.join(HERE, "..", "external", "supersonic"))

FLY_FRAMES = 48                     # 2 s at 24: one slow rise and fall
LAY = 78.0                          # the whole of him tipped forward from standing
HEAD_UP = -58.0                     # the head lifted back against that, to look ahead
BOB = 0.14                          # rig units up and down, each way
SWAY = 4.0                          # degrees of roll, each way
YAW = 2.5                           # degrees of turn, each way
PITCH = 2.5                         # degrees the nose dips and lifts, each way
DRIFT = 0.08                        # rig units side to side, each way
LAG = 0.9                           # radians the limbs follow the body by (about a seventh of the loop)

# The shoulders' and thumbs' rotations, likewise the owner's (frame 1, later the same day).
ARMS = {
    "L": {"upper": (0.919, 0.172, 0.176, 0.307), "thumb": (0.978, 0.092, 0.181, -0.037)},
    "R": {"upper": (0.938, 0.179, -0.114, -0.273), "thumb": (0.991, -0.03, 0.131, -0.023)},
}
# The legs' rotations (each bone's own quaternion), read off the owner's hand-set frame 1.
LEGS = {
    "L": {"higher": (0.993, 0.063, -0.045, 0.093), "middle": (1.0, 0.026, 0.0, 0.0), "foot": (0.887, 0.461, -0.012, -0.03)},
    "R": {"higher": (0.99, 0.068, -0.031, -0.116), "middle": (1.0, 0.026, 0.0, 0.0), "foot": (0.887, 0.461, 0.012, 0.03)},
}

arm = bpy.data.objects["Armature"]
bones = arm.data.bones
pose = arm.pose
for pb in pose.bones:
    pb.rotation_mode = "QUATERNION"


def set_rot(name, *rots):
    R = Matrix.Identity(3)
    for axis, deg in rots:
        R = Matrix.Rotation(math.radians(deg), 3, axis) @ R
    rest = bones[name].matrix_local.to_3x3()
    pose.bones[name].rotation_quaternion = (rest.inverted() @ R @ rest).to_quaternion()


def clear():
    for pb in pose.bones:
        pb.rotation_quaternion = (1.0, 0.0, 0.0, 0.0)
        pb.location = (0.0, 0.0, 0.0)


def follow(name, q, *rots):
    """Bone `name` at the owner's rotation q, with a small world-space swing on top (as set_rot
    reads its angles)."""
    R = Matrix.Identity(3)
    for axis, deg in rots:
        R = Matrix.Rotation(math.radians(deg), 3, axis) @ R
    rest = bones[name].matrix_local.to_3x3()
    pose.bones[name].rotation_quaternion = (rest.inverted() @ R @ rest).to_quaternion() @ Quaternion(q)


def fly_pose(t):
    ph = 2.0 * math.pi * t
    clear()
    # The hover, both ways about the middle: he rises and falls (BOB), rolls side to side (SWAY)
    # and yaws a little the other way (a lazy figure of eight, the yaw at twice the roll's rate),
    # and the nose dips and lifts with the rise. Every swing is a sine about zero, so each goes as
    # far one way as the other, and the loop closes on itself.
    set_rot("root", ("X", LAY - PITCH * math.sin(ph)), ("Y", SWAY * math.sin(ph)),
            ("Z", YAW * math.sin(2.0 * ph)))
    pose.bones["root"].location = (DRIFT * math.sin(ph), 0.0, BOB * math.cos(ph))
    # THE LIMBS FOLLOW, A BEAT BEHIND, AND AGAINST THE BODY. Each hangs on its joint, so when the
    # body rises the arms and legs lag and trail down a touch, and when it rolls they counter; the
    # head holds its line, so it turns against the roll and the yaw. The lag (LAG) is a slice of the
    # loop, and the far ends (hands, feet) lag more than the near (shoulders, hips).
    late = ph - LAG
    later = ph - 2.0 * LAG
    set_rot("Head", ("X", HEAD_UP + PITCH * 0.6 * math.sin(ph) - 2.0 * math.sin(late)),
            ("Y", -SWAY * 0.6 * math.sin(late)), ("Z", -YAW * 0.7 * math.sin(2.0 * late)))
    set_rot("Body", ("X", 1.5 * math.sin(late)), ("Z", 1.5 * math.sin(2.0 * late)))
    for side, s in (("L", -1.0), ("R", 1.0)):
        # the arms: the shoulder the owner's, swinging with the lag and spreading a touch as they
        # drift out; the elbow and wrist flex a beat later
        follow("%s_upper_arm" % side, ARMS[side]["upper"],
               ("X", 4.0 * math.sin(late)), ("Y", s * -2.5 * math.sin(late)))
        set_rot("%s_middle_arm" % side, ("X", 6.0 + 2.0 * math.sin(later)))
        set_rot("%s_lower_arm" % side, ("X", 8.0 + 3.0 * math.sin(later)))
        set_rot("%s_palm" % side, ("X", -8.0 - 5.0 * math.sin(later)))
        set_rot("%s_finger" % side, ("X", -30.0 - 4.0 * math.sin(later)))
        pose.bones["%s_thumb" % side].rotation_quaternion = ARMS[side]["thumb"]
        # the legs: the owner's pose, swinging with the lag (the rise trails them down, the roll
        # scissors them a little) and the feet flexing a beat later
        follow("%s_higher_leg" % side, LEGS[side]["higher"],
               ("X", -3.0 * math.sin(late)), ("Y", s * 1.5 * math.sin(late)))
        pose.bones["%s_middle_leg" % side].rotation_quaternion = LEGS[side]["middle"]
        follow("%s_foot" % side, LEGS[side]["foot"], ("X", -5.0 * math.sin(later)))


def build():
    old = bpy.data.actions.get("Fly")
    if old is not None:
        bpy.data.actions.remove(old)
    act = bpy.data.actions.new("Fly")
    act.use_fake_user = True
    if arm.animation_data is None:
        arm.animation_data_create()
    arm.animation_data.action = act
    for f in range(FLY_FRAMES + 1):
        fly_pose((f % FLY_FRAMES) / float(FLY_FRAMES))
        for pb in pose.bones:
            pb.keyframe_insert("rotation_quaternion", frame=f + 1)
            pb.keyframe_insert("location", frame=f + 1)
    return act


def views():
    sc = bpy.context.scene
    sc.frame_set(1)
    cam = bpy.data.cameras.new("ViewCam")
    co = bpy.data.objects.new("ViewCam", cam)
    sc.collection.objects.link(co)
    sc.camera = co
    cam.type, cam.ortho_scale = "ORTHO", 18
    lights = []
    for name, ang in (("ViewSun1", (50, 0, 30)), ("ViewSun2", (60, 0, 200))):
        l = bpy.data.lights.new(name, "SUN")
        l.energy = 3
        lo = bpy.data.objects.new(name, l)
        sc.collection.objects.link(lo)
        lo.rotation_euler = tuple(math.radians(x) for x in ang)
        lights.append(lo)
    sc.render.engine = "BLENDER_EEVEE"
    sc.render.resolution_x = sc.render.resolution_y = 500
    out = os.path.join(FOLDER, "views")
    os.makedirs(out, exist_ok=True)
    for name, loc, rot in (("side", (30, -4, 4), (90, 0, 90)), ("front", (0, -30, 4), (90, 0, 0)),
                           ("threequarter", (22, -22, 9), (78, 0, 45)), ("top", (0, -4, 30), (0, 0, 0))):
        co.location = loc
        co.rotation_euler = tuple(math.radians(x) for x in rot)
        sc.render.filepath = os.path.join(out, "fly_" + name + ".png")
        bpy.ops.render.render(write_still=True)
    for o in [co] + lights:
        bpy.data.objects.remove(o)


act = build()
arm.animation_data.action = bpy.data.actions.get("Run") or act      # the file opens as it did
bpy.ops.wm.save_mainfile()
print("Fly: %d keys, saved %s" % (FLY_FRAMES + 1, bpy.data.filepath))
if "--" in sys.argv and "views" in sys.argv[sys.argv.index("--") + 1:]:
    arm.animation_data.action = act
    views()
