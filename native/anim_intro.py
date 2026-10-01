"""Key the intro's animation onto the pose made by hand in Intro.blend.

    blender -b external/intro/Intro.blend -P native/anim_intro.py

The final pose is the owner's: the action "IntroFinalPose" (kept with a fake user), taken the
first time from what IntroPop holds at frame 1. The animation around it:

    1 .. F_POP      hidden below the ribbon, arms hanging
    F_POP .. F_TOP  pops up, a little past his place, flinging his arms up
    .. F_SET        drops back and settles
    F_REACH         the left hand just above the ribbon, the thumb coming up
    F_POSE          the hand down on the ribbon: the pose (the eye slides into its new place)
    F_POSE + 4      a small nod, then he holds it to F_END

It is not keyed all at once: his body leads and his head and arms follow a few frames behind
(LAG), so they drag up with the pop and swing into the pose after him. The in-betweens are
Blender's curves.

The eye that was moved by hand is a shape key, "EyeFix": at 0 it is where the model had it
(read once from ORIGINAL), at 1 where it was put. Only that eye moves; the rest of the head stays
as it is in the file.
"""
import math
import os
import sys

import bpy
from mathutils import Matrix, Quaternion, Vector

HERE = os.path.dirname(os.path.abspath(__file__))
ORIGINAL = os.path.abspath(os.path.join(HERE, "..", "external", "intro", "Intro_edited.blend"))

F_POP, F_TOP, F_SET = 10, 16, 24
F_REACH, F_POSE, F_END = 28, 35, 96
DROP = -1.70            # how far below his place he starts: all of him hidden
OVERSHOOT = 0.12
REACH_LIFT = 8.0       # the left arm this much higher before the hand comes down on the ribbon
NOD = 4.0
THUMB_LIFT = 30.0      # the thumbs-up arm comes down into place, already bent, from this much higher
LAG = {"Head": 1, "arms": 2}    # frames behind the body
EYE_FROM, EYE_TO = F_SET, F_POSE

scene = bpy.context.scene
arm = bpy.data.objects["Armature"]
son = bpy.data.objects["Sonic"]
pose = arm.pose
bones = arm.data.bones


def fcurves(act):
    if hasattr(act, "fcurves"):
        return list(act.fcurves)
    return [fc for l in act.layers for s in l.strips for cb in s.channelbags for fc in cb.fcurves]


# ------------------------------------------------------------------ his place
# Where he stands in the pose: what IntroPop has him at, at the pose (else where he is now).
HOME = arm.location.copy()
old = bpy.data.actions.get("IntroPop")
if old is not None:
    for fc in fcurves(old):
        if fc.data_path == "location":
            HOME[fc.array_index] = fc.evaluate(F_POSE + 20)

# ------------------------------------------------------------------ the pose, kept
final_act = bpy.data.actions.get("IntroFinalPose")
if final_act is None:
    final_act = arm.animation_data.action.copy()
    final_act.name = "IntroFinalPose"
    final_act.use_fake_user = True
arm.animation_data.action = final_act
scene.frame_set(1)
for pb in pose.bones:
    pb.rotation_mode = "QUATERNION"
FINAL = {pb.name: (pb.rotation_quaternion.copy(), pb.location.copy()) for pb in pose.bones}
# corrected by hand afterwards (frame95_r_finger.blend): the thumbs-up hand's fingers
FINAL["R_finger"] = (Quaternion((0.9520414471626282, -0.06109372153878212, -0.03060094825923443,
                                 -0.2982417345046997)), Vector())
REST ={pb.name: (Quaternion(), Vector()) for pb in pose.bones}

# The body's twist mirrored, so his stomach faces the other way; the head and arms keep the
# directions they were given (the body is their parent, so they are turned back by as much).
MIRROR_BODY = True


def world_rest(name, q):
    rest = bones[name].matrix_local.to_3x3()
    return rest @ q.to_matrix() @ rest.inverted()


def from_world_rest(name, w):
    rest = bones[name].matrix_local.to_3x3()
    return (rest.inverted() @ w @ rest).to_quaternion()


if MIRROR_BODY:
    M = Matrix(((-1, 0, 0), (0, 1, 0), (0, 0, 1)))
    w_old = world_rest("Body", FINAL["Body"][0])
    w_new = M @ w_old @ M
    FINAL["Body"] = (from_world_rest("Body", w_new), FINAL["Body"][1])
    for child in ("Head", "L_upper_arm", "R_upper_arm"):
        w_child = w_new.inverted() @ w_old @ world_rest(child, FINAL[child][0])
        FINAL[child] = (from_world_rest(child, w_child), FINAL[child][1])


# ------------------------------------------------------------------ the thumb arm, rebuilt
# The pose puts the thumb hand where it belongs by bending the wrist about 130 degrees (and the
# cuff another 60), which no wrist does: it looks right standing still, but nothing can move into
# it like an arm. So the arm is worked out again with real joints only -- the shoulder free, one
# elbow hinge, the forearm turning at the cuff, the wrist bending within a wrist's reach -- to put
# the palm exactly where the pose has it. The fist and thumb are the pose's own, untouched.
REBUILD_THUMB_ARM = True
LIMITS = {          # degrees: (least, most)
    "elbow": (0.0, 150.0),      # the forearm bending forward
    "twist": (-110.0, 110.0),   # the forearm turning the hand over
    "flex": (-75.0, 75.0),      # the wrist, toward the palm and back
    "dev": (-30.0, 30.0),       # the wrist, side to side
}


def basis(q, l):
    return Matrix.Translation(l) @ q.to_matrix().to_4x4()


def posed(p, upto):
    """Armature-space matrices of `upto` and its parents for the pose p (as Blender works them)."""
    out = {}
    chain = []
    b = bones[upto]
    while b is not None:
        chain.append(b)
        b = b.parent
    for b in reversed(chain):
        q, l = p[b.name]
        if b.parent is None:
            out[b.name] = b.matrix_local @ basis(q, l)
        else:
            out[b.name] = (out[b.parent.name] @ b.parent.matrix_local.inverted() @ b.matrix_local
                           @ basis(q, l))
    return out


def rest_rot(name, R):
    rest = bones[name].matrix_local.to_3x3()
    return (rest.inverted() @ R @ rest).to_quaternion()


def arm_from(x):
    """x: the upper arm's turn (a rotation vector, 3 numbers) and elbow, twist, flex, dev."""
    rv = Vector(x[0:3])
    up = Matrix.Rotation(rv.length, 3, rv.normalized()) if rv.length > 1e-9 else Matrix.Identity(3)
    elbow, twist, flex, dev = x[3:7]
    r = lambda a, d: Matrix.Rotation(math.radians(d), 3, a)
    return {
        "R_upper_arm": rest_rot("R_upper_arm", up),
        "R_middle_arm": Quaternion(),
        "R_lower_arm": rest_rot("R_lower_arm", r("X", -elbow)),
        "R_handcuff": rest_rot("R_handcuff", r("Z", -twist)),
        "R_palm": rest_rot("R_palm", r("X", dev) @ r("Y", flex)),
    }


def rebuild_thumb_arm(final):
    want = posed(final, "R_palm")["R_palm"]
    marks = [Vector((0, 0, 0)), Vector((0, 1, 0)), Vector((0.5, 0, 0)), Vector((0, 0, 0.5))]
    goal = [want @ m for m in marks]
    names = ("elbow", "twist", "flex", "dev")

    def cost(x):
        p = dict(final)
        for n, q in arm_from(x).items():
            p[n] = (q, Vector())
        got = posed(p, "R_palm")["R_palm"]
        err = sum((got @ m - g).length_squared for m, g in zip(marks, goal))
        for v, n in zip(x[3:7], names):          # outside a joint's reach costs a great deal
            lo, hi = LIMITS[n]
            err += 0.05 * (max(0.0, lo - v) + max(0.0, v - hi)) ** 2
        return err

    def nelder_mead(x0, step, iters=4000):
        n = len(x0)
        pts = [list(x0)] + [[x0[j] + (step[j] if i == j else 0.0) for j in range(n)] for i in range(n)]
        vals = [cost(p) for p in pts]
        for _ in range(iters):
            order = sorted(range(n + 1), key=lambda i: vals[i])
            pts, vals = [pts[i] for i in order], [vals[i] for i in order]
            c = [sum(p[j] for p in pts[:-1]) / n for j in range(n)]
            xr = [c[j] + (c[j] - pts[-1][j]) for j in range(n)]
            fr = cost(xr)
            if fr < vals[0]:
                xe = [c[j] + 2 * (c[j] - pts[-1][j]) for j in range(n)]
                fe = cost(xe)
                pts[-1], vals[-1] = (xe, fe) if fe < fr else (xr, fr)
            elif fr < vals[-2]:
                pts[-1], vals[-1] = xr, fr
            else:
                xc = [c[j] + 0.5 * (pts[-1][j] - c[j]) for j in range(n)]
                fc = cost(xc)
                if fc < vals[-1]:
                    pts[-1], vals[-1] = xc, fc
                else:
                    pts = [pts[0]] + [[pts[0][j] + 0.5 * (p[j] - pts[0][j]) for j in range(n)] for p in pts[1:]]
                    vals = [vals[0]] + [cost(p) for p in pts[1:]]
            if max(vals) - min(vals) < 1e-12:
                break
        i = min(range(n + 1), key=lambda k: vals[k])
        return pts[i], vals[i]

    # Many arms put the hand there (the elbow can swing round the line from shoulder to wrist).
    # Of those that do, take the one that turns the hand least from how it hangs: the smallest
    # forearm turn and wrist bend, so coming into the pose it turns the short, natural way.
    import random
    rnd = random.Random(1)
    sols = []
    for k in range(60):
        x0 = [rnd.uniform(-2.5, 2.5) for _ in range(3)] + [rnd.uniform(*LIMITS[n]) for n in names]
        x, v = nelder_mead(x0, [0.5, 0.5, 0.5, 30.0, 40.0, 30.0, 10.0])
        sols.append((x, v))
    exact = [(x, v) for x, v in sols if v < 1e-6] or [min(sols, key=lambda s: s[1])]
    turn = lambda x: x[4] ** 2 + x[5] ** 2 + x[6] ** 2
    seen = set()
    for x, v in sorted(exact, key=lambda s: turn(s[0])):
        key = tuple(int(round(c / 10.0)) for c in x[3:7])
        if key not in seen:
            seen.add(key)
            print("  a way: elbow %4.0f  forearm turn %5.0f  wrist %4.0f / %4.0f" % tuple(x[3:7]))
    # of those, the one with the elbow lowest: it hangs down and the arm bends like an arm
    def elbow_z(x):
        p = dict(final)
        for n, q in arm_from(x).items():
            p[n] = (q, Vector())
        return posed(p, "R_lower_arm")["R_lower_arm"].translation.z
    x, v = min(exact, key=lambda s: elbow_z(s[0]))
    print("thumb arm rebuilt: elbow %.0f, forearm turn %.0f, wrist %.0f / %.0f, off by %.4f"
          % (x[3], x[4], x[5], x[6], v ** 0.5))
    out = dict(final)
    for n, q in arm_from(x).items():
        out[n] = (q, Vector())
    return out


FINAL_AS_POSED = dict(FINAL)
if REBUILD_THUMB_ARM:
    FINAL = rebuild_thumb_arm(FINAL)

if "--" in sys.argv and "still" in sys.argv[sys.argv.index("--") + 1:]:
    # the pose as it was made and as rebuilt, side by side; nothing is saved
    arm.animation_data.action = None
    arm.location = HOME
    out_dir = sys.argv[-1]
    for tag, p in (("posed", FINAL_AS_POSED), ("rebuilt", FINAL)):
        for pb in pose.bones:
            pb.rotation_quaternion, pb.location = p[pb.name][0].copy(), p[pb.name][1].copy()
        bpy.context.view_layer.update()
        scene.render.filepath = os.path.join(out_dir, "still_%s.png" % tag)
        bpy.ops.render.render(write_still=True)
    raise SystemExit(0)

if "--" in sys.argv and "posefile" in sys.argv[sys.argv.index("--") + 1:]:
    # the rebuilt pose alone, keyed at frame 1, in a file of its own beside Intro.blend
    act = bpy.data.actions.new("IntroFinalPoseRebuilt")
    act.use_fake_user = True
    arm.animation_data.action = act
    arm.location = HOME
    for pb in pose.bones:
        pb.rotation_quaternion, pb.location = FINAL[pb.name][0].copy(), FINAL[pb.name][1].copy()
        pb.keyframe_insert("rotation_quaternion", frame=1)
        pb.keyframe_insert("location", frame=1)
    arm.keyframe_insert("location", frame=1)
    scene.frame_set(1)
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(os.path.dirname(bpy.data.filepath),
                                                      "Intro_rebuilt_pose.blend"), copy=True)
    raise SystemExit(0)


def mix(a, b, t):
    return {n: (a[n][0].slerp(b[n][0], t), a[n][1].lerp(b[n][1], t)) for n in a}


def rot(name, *rots):
    """A bone's rotation from swings about the world's axes as it lies at rest (anim_sonic's
    set_rot): +X swings a hanging limb back, -X forward; for the arms, Z then turns it about the
    vertical, out to his side."""
    R = Matrix.Identity(3)
    for axis, deg in rots:
        R = Matrix.Rotation(math.radians(deg), 3, axis) @ R
    rest = bones[name].matrix_local.to_3x3()
    return (rest.inverted() @ R @ rest).to_quaternion()


def turned(p, name, axis, deg):
    """p with bone `name` turned a further `deg` about `axis` (as rot() reads it)."""
    q, l = p[name]
    out = dict(p)
    out[name] = (rot(name, (axis, deg)) @ q, l)
    return out


def with_rots(p, rots):
    out = dict(p)
    for name, r in rots.items():
        out[name] = (rot(name, *r), Vector())
    return out


def arms(lift, out, elbow, curl):
    """Both arms the same: swung forward and up by `lift` (150 is up beside his head), turned
    `out` to the side, the elbow bent, the fingers curled."""
    r = {}
    for side, s in (("L", -1.0), ("R", 1.0)):
        r[side + "_upper_arm"] = (("X", -lift), ("Z", s * out))
        r[side + "_middle_arm"] = (("X", -elbow * 0.3),)
        r[side + "_lower_arm"] = (("X", -elbow * 0.7),)
        r[side + "_finger"] = (("Y", s * curl),)
        r[side + "_thumb"] = (("Y", s * 25.0),)
    return r


HIDDEN = with_rots(REST, arms(20.0, 10.0, 10.0, 20.0))
POP = with_rots(REST, dict(arms(150.0, 30.0, 20.0, 20.0), Head=(("X", -14.0),)))     # arms flung up
REACH = turned(FINAL, "L_upper_arm", "X", -REACH_LIFT)       # the hand held up over the ribbon
REACH = turned(REACH, "R_upper_arm", "X", -THUMB_LIFT)       # the thumb arm already bent, higher
NODDED = turned(FINAL, "Head", "X", NOD)
# After the pop both arms come down round the outside, bent, never across his face: the thumb
# arm takes its bend with its upper arm out to the side, then comes in bent into place.
def put(p):
    for pb in pose.bones:
        pb.rotation_quaternion, pb.location = p[pb.name][0].copy(), p[pb.name][1].copy()
    bpy.context.view_layer.update()


R_ARM = [n for n in FINAL if n.startswith("R_") and not any(w in n for w in ("leg", "foot", "sock"))]
SIDE = with_rots(POP, arms(110.0, 80.0, 50.0, 40.0))       # both arms out to the side, bent
put(SIDE)
up_dir = pose.bones["R_upper_arm"].matrix.col[1].to_3d().normalized()
HIGH = dict(POP)
for name in R_ARM:
    HIGH[name] = FINAL[name]
put(HIGH)
ub = pose.bones["R_upper_arm"]
m = ub.matrix.copy()
turn = m.col[1].to_3d().normalized().rotation_difference(up_dir).to_matrix()
ub.matrix = Matrix.Translation(m.translation) @ (turn @ m.to_3x3()).to_4x4()
bpy.context.view_layer.update()
HIGH["R_upper_arm"] = (ub.rotation_quaternion.copy(), ub.location.copy())
# and the other arm comes down round the outside, not across his face
for name, r in arms(110.0, 80.0, 50.0, 40.0).items():
    if name.startswith("L_"):
        HIGH[name] = (rot(name, *r), Vector())

# The hands are open at the pop. As the arm comes round the wrist takes its angle in the pose, the
# hand still open; then the fingers close into the fist and the thumb comes up. Nothing turns at
# the end: the hand only closes.
HANDS = {side + n for side in ("L_", "R_") for n in ("handcuff", "palm", "finger", "thumb")}
WRISTS = {side + n for side in ("L_", "R_") for n in ("handcuff", "palm")}

KEYS = [            # (frame, pose, height above his place)
    (1, HIDDEN, DROP), (F_POP, HIDDEN, DROP),
    (F_TOP, POP, OVERSHOOT),
    (F_SET - 4, HIGH, -0.03),
    (F_REACH, REACH, 0.0),
    (F_POSE, FINAL, 0.0),
    (F_POSE + 4, NODDED, 0.0),
    (F_POSE + 11, FINAL, 0.0),
    (F_END, FINAL, 0.0),
]


def lag(name):
    if name == "Head":
        return LAG["Head"]
    if name[:2] in ("L_", "R_") and "leg" not in name and "foot" not in name and "sock" not in name:
        return LAG["arms"]
    return 0


# ------------------------------------------------------------------ the in-betweens
# Every frame is keyed, worked out here: through each key pose on a smooth curve that keeps its
# speed (a key is passed through, not stopped at), stopping only where a pose is held. Rotations
# are blended as rotations (normalised), not channel by channel.
def hermite(ts, vs, t):
    """The value at t of the curve through (ts[k], vs[k]): cubic between keys, each key's slope
    from its neighbours (none at the ends or where it is held). vs: lists of floats."""
    n = len(ts)
    if t <= ts[0]:
        return list(vs[0])
    if t >= ts[-1]:
        return list(vs[-1])
    k = max(i for i in range(n - 1) if ts[i] <= t)

    def slope(i):
        if i == 0 or i == n - 1 or vs[i] == vs[i - 1] or vs[i] == vs[i + 1]:
            return [0.0] * len(vs[i])
        return [(b - a) / (ts[i + 1] - ts[i - 1]) for a, b in zip(vs[i - 1], vs[i + 1])]

    h = ts[k + 1] - ts[k]
    u = (t - ts[k]) / h
    h00, h10 = 2 * u ** 3 - 3 * u ** 2 + 1, u ** 3 - 2 * u ** 2 + u
    h01, h11 = -2 * u ** 3 + 3 * u ** 2, u ** 3 - u ** 2
    m0, m1 = slope(k), slope(k + 1)
    return [h00 * a + h10 * h * ma + h01 * b + h11 * h * mb
            for a, b, ma, mb in zip(vs[k], vs[k + 1], m0, m1)]


if old is not None:
    bpy.data.actions.remove(old)
act = bpy.data.actions.new("IntroPop")
act.use_fake_user = True
arm.animation_data.action = act

tracks = {}
for pb in pose.bones:
    ts, qs, ls, prev = [], [], [], None
    for i, (f, p, h) in enumerate(KEYS):
        if pb.name in HANDS:
            if p is HIGH:                   # coming round: the wrist set, the fingers still open
                p = FINAL if pb.name in WRISTS else POP
        q, l = p[pb.name]
        q = q.copy()
        if prev is not None and prev.dot(q) < 0.0:          # the short way round
            q.negate()
        prev = q
        # the first two and the last keys stay put; between, the head and arms come after the body
        ts.append(f if i in (0, 1, len(KEYS) - 1) else f + lag(pb.name))
        qs.append(list(q))
        ls.append(list(l))
    tracks[pb.name] = (ts, qs, ls)
hts = [f for f, _, _ in KEYS]
hvs = [[h] for _, _, h in KEYS]

for f in range(1, F_END + 1):
    for pb in pose.bones:
        ts, qs, ls = tracks[pb.name]
        pb.rotation_quaternion = Quaternion(hermite(ts, qs, f)).normalized()
        pb.location = Vector(hermite(ts, ls, f))
        pb.keyframe_insert("rotation_quaternion", frame=f)
        pb.keyframe_insert("location", frame=f)
    arm.location = HOME + Vector((0, 0, hermite(hts, hvs, f)[0]))
    arm.keyframe_insert("location", frame=f)
for fc in fcurves(act):
    for kp in fc.keyframe_points:
        kp.interpolation = "LINEAR"

# ------------------------------------------------------------------ the eye
mesh = son.data
if mesh.shape_keys is None or "EyeFix" not in mesh.shape_keys.key_blocks:
    with bpy.data.libraries.load(ORIGINAL, link=False) as (src, dst):
        dst.meshes = [n for n in src.meshes if n == mesh.name or n.startswith("Sonic")][:1]
    orig = dst.meshes[0]
    assert len(orig.vertices) == len(mesh.vertices), "the original mesh does not match"
    deltas = [mesh.vertices[i].co - orig.vertices[i].co for i in range(len(mesh.vertices))]
    # the head as a whole was nudged too; only what moved apart from that is the eye
    counts = {}
    for d in deltas:
        k = tuple(round(c, 3) for c in d)
        counts[k] = counts.get(k, 0) + 1
    common = Vector(max(counts, key=counts.get))
    eye = [i for i, d in enumerate(deltas) if (d - common).length > 1e-3 and d.length > 1e-3]
    basis = son.shape_key_add(name="Basis", from_mix=False)
    fix = son.shape_key_add(name="EyeFix", from_mix=False)
    for i in eye:                       # the basis has the eye where the model had it
        basis.data[i].co = orig.vertices[i].co + common
        mesh.vertices[i].co = basis.data[i].co
    bpy.data.meshes.remove(orig)
    print("EyeFix: %d vertices of the eye" % len(eye))
fix = mesh.shape_keys.key_blocks["EyeFix"]
mesh.shape_keys.animation_data_clear()
for f, v in ((1, 0.0), (EYE_FROM, 0.0), (EYE_TO, 1.0), (F_END, 1.0)):
    fix.value = v
    fix.keyframe_insert("value", frame=f)

scene.frame_start, scene.frame_end = 1, F_END
scene.frame_set(F_POSE + 20)
bpy.ops.wm.save_mainfile()
print("keyed IntroPop: %d keys, the pose at %d, home %s" % (len(KEYS), F_POSE, tuple(round(v, 3) for v in HOME)))
