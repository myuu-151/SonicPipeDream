"""Author the actions on the rigged Sonic.

Poses are written as world-space swings per bone and converted into the bone's
own space, so the numbers below read as "swing this limb forwards 40 degrees"
rather than as opaque local Eulers.

World axes: +X is the model's left/right span, -Y is forward (the way he faces),
+Z is up. A positive rotation about X swings a downward-pointing limb backwards.
"""

import math
import os

import bpy
from mathutils import Matrix, Vector

OUT = os.environ["S2S_ANIM_OUT"]

arm = bpy.data.objects['Armature']
bones = arm.data.bones
pose = arm.pose

for pb in pose.bones:
    pb.rotation_mode = 'QUATERNION'

AXIS = {'X': 'X', 'Y': 'Y', 'Z': 'Z'}

# Bones whose position is animated as well as their rotation.
LOC_KEYED = {'root', 'L_thumb', 'R_thumb'}


def set_rot(name, *rots):
    """Apply world-space rotations to a bone, in order."""
    pb = pose.bones[name]
    R = Matrix.Identity(3)
    for axis, deg in rots:
        R = Matrix.Rotation(math.radians(deg), 3, AXIS[axis]) @ R
    rest = bones[name].matrix_local.to_3x3()
    pb.rotation_quaternion = (rest.inverted() @ R @ rest).to_quaternion()


def clear():
    for pb in pose.bones:
        pb.rotation_quaternion = (1.0, 0.0, 0.0, 0.0)
        pb.location = (0.0, 0.0, 0.0)


def key(frame):
    for pb in pose.bones:
        pb.keyframe_insert('rotation_quaternion', frame=frame)
        if pb.name in LOC_KEYED:
            pb.keyframe_insert('location', frame=frame)


def new_action(name):
    # Replace rather than accumulate Run.001, Run.002 on every rebuild.
    old = bpy.data.actions.get(name)
    if old is not None:
        bpy.data.actions.remove(old)
    act = bpy.data.actions.new(name)
    act.use_fake_user = True
    if arm.animation_data is None:
        arm.animation_data_create()
    arm.animation_data.action = act
    return act


def iter_fcurves(act):
    """Blender 5's slotted actions hold curves under layers/strips/channelbags;
    older files expose them directly on the action."""
    if hasattr(act, 'fcurves'):
        for fc in act.fcurves:
            yield fc
        return
    for layer in act.layers:
        for strip in layer.strips:
            for cb in strip.channelbags:
                for fc in cb.fcurves:
                    yield fc


def smooth(act, interp='BEZIER'):
    n = 0
    for fc in iter_fcurves(act):
        n += 1
        for kp in fc.keyframe_points:
            kp.interpolation = interp
    return n


def clamp01(v):
    return max(0.0, min(1.0, v))


# ---------------------------------------------------------------- run cycle --

RUN_FRAMES = 16          # frame RUN_FRAMES+1 repeats frame 1 so the loop is clean


def run_lower_body(t, look_side=None):
    """Legs, hips and lean for the classic full-speed run. t is 0..1."""
    ph = 2.0 * math.pi * t

    # The torso does real work, as in the Sonic 2 special stage: the shoulders
    # twist hard with every arm drive and he leans sideways into the thrust.
    # sin(ph) = +1 is the right leg reaching, so the left arm is driving: the
    # left shoulder comes forward (+Z twist) and he tips that way (-Y roll).
    drive = math.sin(ph)
    # The torso bone points UP, so a positive X rotation tips it forward (-Y):
    # the opposite sign to the hanging limbs.
    set_rot('Body', ('X', 16.0), ('Z', 24.0 * drive), ('Y', -9.0 * drive))
    # The head gives back most of the twist so he keeps facing down the track,
    # but keeps a little sway so it is not gyro-stabilised.
    # For the thumbs-up he cocks his head over towards the thumb and glances
    # that way. +X is the 'R' side: a positive Z turn faces him towards it and a
    # positive Y roll tips the top of the head towards it.
    look = 0.0 if look_side is None else (1.0 if look_side == 'R' else -1.0)
    set_rot('Head', ('X', -12.0),
            ('Z', -17.0 * drive + 20.0 * look),
            ('Y', 5.0 * drive + 13.0 * look))

    set_rot('hips', ('Z', -7.0 * math.sin(ph)))
    pose.bones['root'].location = (0.0, 0.0, 0.18 * math.cos(2.0 * ph) - 0.2)

    for side, off in (('R', 0.0), ('L', 0.5)):
        p = ph + 2.0 * math.pi * off

        # Thigh: forward reach at p = 90 degrees, full push-back at 270.
        thigh = -62.0 * math.sin(p)
        # The knee folds while the leg travels forward (the recovery), and is
        # nearly straight for the reach and the push.
        recover = max(0.0, math.cos(p))
        knee = 10.0 + 100.0 * recover ** 1.5

        set_rot('%s_higher_leg' % side, ('X', thigh))
        set_rot('%s_middle_leg' % side, ('X', knee * 0.6))
        set_rot('%s_lower_leg' % side, ('X', knee * 0.4))
        set_rot('%s_sock' % side, ('X', 0.0))

        # The shoe is only flattened while the leg is out in front, for the
        # reach and the landing. Through the push-off and the recovery it rides
        # with the shin instead, so the heel kicks up and the sole faces the
        # camera behind him. Holding it level all the way round is what made
        # him look like he was skating.
        shin = thigh + knee
        planted = max(0.0, math.sin(p)) ** 0.8
        # Extra toe-point as he leaves the ground, easing off through recovery.
        point = 22.0 * max(0.0, -math.sin(p)) + 10.0 * max(0.0, math.cos(p))
        # On the kick-out the toe arches up past level, peaking at full reach,
        # so he lands heel-first rather than flat-footed.
        arch = 34.56 * max(0.0, math.sin(p)) ** 2
        set_rot('%s_foot' % side, ('X', -shin * 0.75 * planted + point - arch))


def fist(side, curl=95.0):
    """Close the hand. Palms face the body, so fingers curl about the forward
    axis, towards the midline."""
    sign = 1.0 if side == 'R' else -1.0
    set_rot('%s_finger' % side, ('Y', sign * curl))
    set_rot('%s_thumb' % side, ('Y', sign * 25.0))


def run_arm(side, t, phase_offset):
    """Sprinter's arm pump, as in the Sonic 2 special stage: elbow locked at
    about a right angle, the whole arm driving from the shoulder opposite the
    same-side leg, fist closed."""
    s = math.sin(2.0 * math.pi * t + phase_offset)
    out = 1.0 if side == 'R' else -1.0

    # s = +1 is this arm fully forward. The arms are carried wide: elbows
    # flared out from the body, fists swinging past the hips well clear of it,
    # flaring a little wider still on the backswing.
    swing = -36.0 * s
    flare = 40.0 + 8.0 * max(0.0, -s)
    # The torso's forward lean carries the arms back with it, so the swing is
    # centred well forward of the torso to keep the hands in front of him.
    set_rot('%s_upper_arm' % side, ('X', -18.0 + swing), ('Y', out * -flare))

    # Most of the bend sits at the lower joint so it reads as one elbow.
    elbow = -68.0 - 10.0 * s
    set_rot('%s_middle_arm' % side, ('X', elbow * 0.3))
    set_rot('%s_lower_arm' % side, ('X', elbow * 0.7))
    set_rot('%s_handcuff' % side, ('X', 0.0))
    set_rot('%s_palm' % side, ('X', 0.0))
    fist(side, 115.0)


def part_verts(name):
    ob = bpy.data.objects['Sonic']
    gi = ob.vertex_groups[name].index
    return [v.co.copy() for v in ob.data.vertices if any(g.group == gi for g in v.groups)]


def plant_thumb(side, arm_world_deg):
    """Stand the thumb on top of the fist, pointing straight up.

    Swinging the thumb about its own rest position does not work: at rest it
    hangs in front of and inboard from the palm, on a slant, so a plain rotation
    carries it off the hand and leaves it leaning. Instead the thumb is placed
    outright, in the palm's rest space: its base ring goes onto the palm's
    thumb-side edge, and its real axis (base centre to tip centre) is turned to
    the direction that ends up vertical once the arm is raised.
    """
    thumb = part_verts('%s_thumb' % side)
    palm = part_verts('%s_palm' % side)

    zs = [v.z for v in thumb]
    z_hi, z_lo = max(zs), min(zs)
    base = [v for v in thumb if v.z > z_hi - 0.1]
    tip = [v for v in thumb if v.z < z_lo + 0.1]
    base_c = sum(base, Vector()) / len(base)
    tip_c = sum(tip, Vector()) / len(tip)
    axis = (tip_c - base_c).normalized()

    # The palm's front edge (-Y at rest) becomes the top of the fist when the
    # arm is level. Seat the base just inside it, midway along the palm.
    px = [v.x for v in palm]
    pz = [v.z for v in palm]
    target = Vector(((min(px) + max(px)) * 0.5,
                     min(v.y for v in palm) + 0.18,
                     (min(pz) + max(pz)) * 0.5))

    # The arm sits arm_world_deg from hanging, so a thumb that should end at
    # 180 (straight up) needs the remainder here, measured in rest space.
    ang = math.radians(-180.0 - arm_world_deg)
    want = Vector((0.0, math.sin(ang), -math.cos(ang)))
    turn = axis.rotation_difference(want).to_matrix().to_4x4()

    place = Matrix.Translation(target) @ turn @ Matrix.Translation(-base_c)
    rest = bones['%s_thumb' % side].matrix_local
    pose.bones['%s_thumb' % side].matrix_basis = rest.inverted() @ place @ rest


def thumbs_up_arm(side, t):
    """Arm thrust out forward and a little to the side, fist closed, thumb up.
    It has to go forward rather than up: the head is wider than the shoulders,
    so a raised arm would disappear inside it."""
    ph = 2.0 * math.pi * t
    bob = 4.0 * math.sin(2.0 * ph)
    out = 38.0 if side == 'R' else -38.0
    # The shoulders twist 24 degrees each way and would sweep this arm across
    # his face. Give most of that back so the thumbs-up holds its place, keeping
    # a little so it still moves with him.
    out -= 0.75 * 24.0 * math.sin(ph)

    # The torso leans 16 forward, which carries the arm back by as much, so
    # -100 here lands at about -84 in the world: just under level.
    set_rot('%s_upper_arm' % side, ('X', -100.0 + bob), ('Z', out))
    set_rot('%s_middle_arm' % side, ('X', -6.0))
    set_rot('%s_lower_arm' % side, ('X', -4.0))
    set_rot('%s_handcuff' % side, ('X', 0.0))
    set_rot('%s_palm' % side, ('X', 0.0))
    fist(side, 110.0)
    # Torso lean (16) + upper arm (-100) + the two small elbow bends (-10).
    plant_thumb(side, 16.0 - 100.0 - 10.0)


def build_run(name, thumbs_up_side=None):
    act = new_action(name)
    for f in range(RUN_FRAMES + 1):
        t = (f % RUN_FRAMES) / float(RUN_FRAMES)
        clear()
        run_lower_body(t, look_side=thumbs_up_side)
        for side, off in (('R', math.pi), ('L', 0.0)):  # arm opposes its own leg
            if side == thumbs_up_side:
                thumbs_up_arm(side, t)
            else:
                run_arm(side, t, off)
        key(f + 1)
    smooth(act)
    return act


# -------------------------------------------------------------------- idle --

IDLE_FRAMES = 48


def build_idle():
    act = new_action('Idle')
    for f in range(IDLE_FRAMES + 1):
        t = (f % IDLE_FRAMES) / float(IDLE_FRAMES)
        ph = 2.0 * math.pi * t
        clear()

        breathe = 2.5 * math.sin(ph)
        set_rot('Body', ('X', 5.0 - breathe))
        set_rot('Head', ('X', -3.0 + breathe), ('Z', 7.0 * math.sin(ph * 0.5)))
        set_rot('hips', ('X', 0.0))
        pose.bones['root'].location = (0.0, 0.0, 0.06 * math.sin(ph))

        for side in ('L', 'R'):
            sign = -1.0 if side == 'R' else 1.0
            set_rot('%s_upper_arm' % side, ('X', 4.0 + breathe), ('Y', sign * 6.0))
            set_rot('%s_middle_arm' % side, ('X', -8.0))
            set_rot('%s_palm' % side, ('X', -6.0))
            set_rot('%s_finger' % side, ('X', -30.0))
            set_rot('%s_thumb' % side, ('X', -20.0))
            set_rot('%s_higher_leg' % side, ('X', -1.0))
        key(f + 1)
    smooth(act)
    return act


built = [
    build_idle(),
    build_run('Run'),
    build_run('RunThumbsUp', thumbs_up_side='R'),
]

clear()
arm.animation_data.action = bpy.data.actions['Run']
bpy.context.scene.frame_start = 1
bpy.context.scene.frame_end = RUN_FRAMES + 1

print("\nactions:")
for a in built:
    r = a.frame_range
    print("  %-14s frames %.0f..%.0f  fcurves %d"
          % (a.name, r[0], r[1], sum(1 for _ in iter_fcurves(a))))

bpy.ops.wm.save_as_mainfile(filepath=OUT)
print("saved %s" % OUT)
