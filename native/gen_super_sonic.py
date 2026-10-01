"""Super Sonic, made from the rigged Sonic: his quills swept up and his fur gold.

    blender -b external/supersonic/Sonic_Rigged_Anim.blend -P native/gen_super_sonic.py [-- views]
        -> external/supersonic/SuperSonic_Rigged_Anim.blend   the same rig and actions, Super
           external/supersonic/Sonic_11.png                    his fur's colour, now gold
           external/supersonic/views/*.png                     side, front, back (with -- views)

external/supersonic began as a copy of external/sonic. Its blend files point at the pictures next
to them (//Sonic_11.png and the rest), so recolouring the fur's picture here leaves Sonic as he is.

THE QUILLS. In the model they sweep straight back from the head, nearly level. Super Sonic's stand
up and back. Every vertex of the head behind the skull (past QUILL_FROM, in the model's depth) is
turned up about a hinge across the back of the head, the more the further back it is (a smooth
bend, not a fold at the hinge), so the spikes curve up as they go. Nothing in front of QUILL_FROM
moves: the face, the ears and the skull keep their shape.

Model axes: -Y is forward (the way he faces), +Z up; the head runs from y -3.8 (the nose) to 6.0
(the quills' tips) and z 7.2 to 13.4.
"""
import math
import os
import sys

import bpy
from mathutils import Matrix, Vector

HERE = os.path.dirname(os.path.abspath(__file__))
FOLDER = os.path.abspath(os.path.join(HERE, "..", "external", "supersonic"))
OUT = os.path.join(FOLDER, "SuperSonic_Rigged_Anim.blend")

FUR_FROM = (48, 48, 248)            # Sonic_11.png: his blue
FUR_TO = (248, 224, 56)             # Super Sonic's gold

QUILL_FROM = 0.6                    # depth (y) behind which the head bends
HINGE_Z = 10.4                      # the hinge's height, across the back of the skull
QUILL_LIFT = 52.0                   # degrees the furthest point turns up
BEND = 0.8                          # <1: the bend starts sooner behind the hinge


def recolour_fur():
    """Sonic_11.png's blue to gold, in Blender's own copy of it, saved over the file."""
    img = next(im for im in bpy.data.images if im.filepath.endswith("Sonic_11.png"))
    px = list(img.pixels[:])
    src = [c / 255.0 for c in FUR_FROM]
    dst = [c / 255.0 for c in FUR_TO]
    changed = 0
    for i in range(0, len(px), 4):
        if all(abs(px[i + k] - src[k]) < 0.02 for k in range(3)):
            px[i:i + 3] = dst
            changed += 1
    img.pixels[:] = px
    img.filepath_raw = os.path.join(FOLDER, "Sonic_11.png")
    img.file_format = "PNG"
    img.save()
    print("fur: %d of %d texels gold" % (changed, len(px) // 4))


def raise_quills():
    son = bpy.data.objects["Sonic"]
    me = son.data
    gi = son.vertex_groups["Head"].index
    head = [v for v in me.vertices if any(g.group == gi and g.weight > 0.5 for g in v.groups)]
    far = max(v.co.y for v in head)
    moved = 0
    for v in head:
        if v.co.y <= QUILL_FROM:
            continue
        t = min(1.0, (v.co.y - QUILL_FROM) / (far - QUILL_FROM)) ** BEND
        a = math.radians(QUILL_LIFT) * t
        rel = Vector((0.0, v.co.y - QUILL_FROM, v.co.z - HINGE_Z))
        rel = Matrix.Rotation(a, 3, "X") @ rel      # +X turns the back (+y) up (+z)
        v.co.y, v.co.z = QUILL_FROM + rel.y, HINGE_Z + rel.z
        moved += 1
    me.update()
    print("quills: %d of the head's %d vertices turned up, at most %.0f degrees" % (moved, len(head), QUILL_LIFT))


def views():
    sc = bpy.context.scene
    arm = bpy.data.objects["Armature"]
    keep = arm.animation_data.action if arm.animation_data else None
    if arm.animation_data:
        arm.animation_data.action = None
    for pb in arm.pose.bones:
        pb.rotation_quaternion = (1, 0, 0, 0)
        pb.location = (0, 0, 0)
    cam = bpy.data.cameras.new("ViewCam")
    co = bpy.data.objects.new("ViewCam", cam)
    sc.collection.objects.link(co)
    sc.camera = co
    cam.type, cam.ortho_scale = "ORTHO", 15
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
    for name, loc, rot in (("side", (30, 1, 8), (90, 0, 90)), ("front", (0, -30, 8), (90, 0, 0)),
                           ("back", (0, 30, 8), (90, 0, 180)), ("threequarter", (22, -22, 10), (82, 0, 45))):
        co.location = loc
        co.rotation_euler = tuple(math.radians(x) for x in rot)
        sc.render.filepath = os.path.join(out, name + ".png")
        bpy.ops.render.render(write_still=True)
    for o in [co] + lights:                 # not saved with him
        bpy.data.objects.remove(o)
    if keep is not None:
        arm.animation_data.action = keep


def main():
    recolour_fur()
    raise_quills()
    bpy.ops.wm.save_as_mainfile(filepath=OUT)
    print("saved %s" % OUT)
    if "--" in sys.argv and "views" in sys.argv[sys.argv.index("--") + 1:]:
        views()


main()
