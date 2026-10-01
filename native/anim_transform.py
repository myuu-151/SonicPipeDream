"""The transformation, as Sonic 2's: he curls in, then bursts out into a stretched pose -- arms
flung out to the sides and angled down, fists clenched, legs apart, chest up, facing out -- and holds it, straining, with a
tremble, as the light takes him. The game plays it on the blue Sonic and swaps him for the gold
one at the burst (BURST_FRAME), where the pose is the same on both.

    blender -b <rig>.blend -P native/anim_transform.py [-- views]
        -> the action "Transform" added to that file (saved in place; TRANSFORM_FRAMES keys),
           and with -- views, external/supersonic/views/transform_*.png

Run it on both external/sonic/Sonic_Rigged_Anim.blend and
external/supersonic/SuperSonic_Rigged_Anim2.blend: the same rig, the same keys.

Poses are world-space swings per bone, as in anim_sonic.py (+X his span, -Y forward, +Z up; a
positive X swing tips a hanging limb back, and the body, which points up, forward).
"""
import math
import os
import sys

import bpy
from mathutils import Matrix

HERE = os.path.dirname(os.path.abspath(__file__))
VIEWS = os.path.abspath(os.path.join(HERE, "..", "external", "supersonic", "views"))

FPS = 24
CURL_FRAME = 7                      # curled in by here (from standing)
BURST_FRAME = 11                    # ...and flung out by here: the flash, and the swap of model
TRANSFORM_FRAMES = 36               # held, trembling, to the end (1.5 s)
RISE = 0.6                          # rig units he lifts as he bursts out
TREMBLE = 1.2                       # degrees of shake while he strains
TREMBLE_HZ = 9.0

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


def smooth(t):
    t = max(0.0, min(1.0, t))
    return t * t * (3.0 - 2.0 * t)


def lerp(a, b, t):
    return a + (b - a) * t


# The two poses, as numbers: curled in, and flung out. Blended between by `k` (0 curled, 1 out).
def apply(k, tremble=0.0):
    clear()
    tr = tremble
    # the body: hunched forward curled, arched back and chest up flung out
    set_rot("Body", ("X", lerp(28.0, -5.0, k) + tr), ("Z", 0.4 * tr))
    set_rot("Head", ("X", lerp(22.0, 2.0, k) - 0.6 * tr))      # facing straight out
    set_rot("hips", ("X", lerp(-10.0, 4.0, k)))
    pose.bones["root"].location = (0.0, 0.0, lerp(-0.5, RISE, k))
    for side, s in (("L", -1.0), ("R", 1.0)):
        # arms: wrapped in across the chest curled; flung straight out to the sides and a little
        # back when out, the hands open and spread
        # (Sonic 2's: the arms out to the sides and angled DOWN, about 55 degrees from hanging)
        set_rot("%s_upper_arm" % side, ("X", lerp(-70.0, 4.0, k) + 0.8 * tr),
                ("Y", s * lerp(-20.0, -58.0, k)))
        set_rot("%s_middle_arm" % side, ("X", lerp(-35.0, 0.0, k)))
        set_rot("%s_lower_arm" % side, ("X", lerp(-45.0, -4.0, k)))
        # the hands fists throughout (the fingers curled to the palm, the thumb over them)
        set_rot("%s_palm" % side, ("Y", s * lerp(0.0, 12.0, k)))
        set_rot("%s_finger" % side, ("Y", s * 110.0))
        set_rot("%s_thumb" % side, ("Y", s * 25.0))
        # legs: drawn up curled; apart and straight, toes down, when out
        set_rot("%s_higher_leg" % side, ("X", lerp(-55.0, 4.0, k)), ("Y", s * lerp(-6.0, -14.0, k)))
        set_rot("%s_middle_leg" % side, ("X", lerp(30.0, 2.0, k)))
        set_rot("%s_lower_leg" % side, ("X", lerp(30.0, 2.0, k)))
        set_rot("%s_foot" % side, ("X", lerp(-10.0, 30.0, k)))


def build():
    old = bpy.data.actions.get("Transform")
    if old is not None:
        bpy.data.actions.remove(old)
    act = bpy.data.actions.new("Transform")
    act.use_fake_user = True
    if arm.animation_data is None:
        arm.animation_data_create()
    arm.animation_data.action = act
    for f in range(1, TRANSFORM_FRAMES + 1):
        if f <= CURL_FRAME:
            k = lerp(0.45, 0.0, smooth((f - 1) / float(CURL_FRAME - 1)))      # standing-ish in, to curled
            tr = 0.0
        elif f <= BURST_FRAME:
            k = smooth((f - CURL_FRAME) / float(BURST_FRAME - CURL_FRAME))      # the burst
            tr = 0.0
        else:
            k = 1.0
            t = (f - BURST_FRAME) / float(FPS)
            tr = TREMBLE * math.sin(2.0 * math.pi * TREMBLE_HZ * t) * (1.0 if f < TRANSFORM_FRAMES - 4 else 0.3)
        apply(k, tr)
        for pb in pose.bones:
            pb.keyframe_insert("rotation_quaternion", frame=f)
            pb.keyframe_insert("location", frame=f)
    return act


def views():
    sc = bpy.context.scene
    cam = bpy.data.cameras.new("ViewCam")
    co = bpy.data.objects.new("ViewCam", cam)
    sc.collection.objects.link(co)
    sc.camera = co
    cam.type, cam.ortho_scale = "ORTHO", 20
    lights = []
    for name, ang in (("ViewSun1", (50, 0, 30)), ("ViewSun2", (60, 0, 200))):
        l = bpy.data.lights.new(name, "SUN")
        l.energy = 3
        lo = bpy.data.objects.new(name, l)
        sc.collection.objects.link(lo)
        lo.rotation_euler = tuple(math.radians(x) for x in ang)
        lights.append(lo)
    sc.render.engine = "BLENDER_EEVEE"
    sc.render.resolution_x = sc.render.resolution_y = 400
    os.makedirs(VIEWS, exist_ok=True)
    co.location, co.rotation_euler = (0, -30, 7), (math.pi / 2, 0, 0)
    for f in (1, CURL_FRAME, 9, BURST_FRAME, 20):
        sc.frame_set(f)
        sc.render.filepath = os.path.join(VIEWS, "transform_%02d.png" % f)
        bpy.ops.render.render(write_still=True)
    for o in [co] + lights:
        bpy.data.objects.remove(o)


act = build()
arm.animation_data.action = bpy.data.actions.get("Run") or act
bpy.ops.wm.save_mainfile()
print("Transform: %d keys, saved %s" % (TRANSFORM_FRAMES, bpy.data.filepath))
if "--" in sys.argv and "views" in sys.argv[sys.argv.index("--") + 1:]:
    arm.animation_data.action = act
    views()
