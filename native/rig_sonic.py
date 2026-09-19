"""Build an armature for the split Sonic and bind each part rigidly to one bone.

The model is already separated into one object per body part, so every vertex
belongs to exactly one bone at weight 1.0. That makes the bind exact: no weight
painting, no falloff, and no vertex ever blends between bones.

Bones are placed from each part's own bounds rather than hardcoded numbers, so
the rig still lands correctly if the mesh moves.
"""

import os

import bpy
import mathutils

OUT = os.environ["S2S_RIG_OUT"]

Vec = mathutils.Vector

# Limb parts hang downwards, so a bone runs from the top of its part to the
# bottom. Feet are the exception and point forwards, at -Y.
#   name: (parent, connected)
SPEC = {
    'Body': ('hips', True),
    'Head': ('Body', True),
}
for s in ('L', 'R'):
    SPEC['%s_upper_arm' % s] = ('Body', False)
    SPEC['%s_middle_arm' % s] = ('%s_upper_arm' % s, True)
    SPEC['%s_lower_arm' % s] = ('%s_middle_arm' % s, True)
    SPEC['%s_handcuff' % s] = ('%s_lower_arm' % s, True)
    SPEC['%s_palm' % s] = ('%s_handcuff' % s, True)
    SPEC['%s_finger' % s] = ('%s_palm' % s, True)
    SPEC['%s_thumb' % s] = ('%s_palm' % s, False)

    SPEC['%s_higher_leg' % s] = ('hips', False)
    SPEC['%s_middle_leg' % s] = ('%s_higher_leg' % s, True)
    SPEC['%s_lower_leg' % s] = ('%s_middle_leg' % s, True)
    SPEC['%s_sock' % s] = ('%s_lower_leg' % s, True)
    SPEC['%s_foot' % s] = ('%s_sock' % s, False)

meshes = [o for o in bpy.data.objects if o.type == 'MESH']
missing = sorted(set(SPEC) - {o.name for o in meshes})
extra = sorted({o.name for o in meshes} - set(SPEC))
if missing or extra:
    raise SystemExit("part names do not match: missing %s, unexpected %s" % (missing, extra))

# --- 1. Bake the object transforms so local space equals world space. ---
bpy.ops.object.select_all(action='DESELECT')
for ob in meshes:
    ob.select_set(True)
bpy.context.view_layer.objects.active = meshes[0]
bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)

bounds = {}
for ob in meshes:
    cos = [ob.matrix_world @ v.co for v in ob.data.vertices]
    bounds[ob.name] = {
        'cos': cos,
        'cx': sum(c.x for c in cos) / len(cos),
        'cy': sum(c.y for c in cos) / len(cos),
        'z0': min(c.z for c in cos),
        'z1': max(c.z for c in cos),
    }


def slab_centre(cos, key, top, frac=0.35):
    """Centroid of the extreme slice of a part, so a bone aims at the end of the
    geometry rather than at its overall middle."""
    vals = [key(c) for c in cos]
    lo, hi = min(vals), max(vals)
    span = hi - lo
    if span < 1e-6:
        sel = cos
    elif top:
        sel = [c for c in cos if key(c) >= hi - span * frac]
    else:
        sel = [c for c in cos if key(c) <= lo + span * frac]
    n = len(sel)
    return Vec((sum(c.x for c in sel) / n,
                sum(c.y for c in sel) / n,
                sum(c.z for c in sel) / n))


def limb_head_tail(name):
    b = bounds[name]
    if name.endswith('_foot'):
        # Ankle at the back, toe forward: head above the heel, tail at the toe.
        head = slab_centre(b['cos'], lambda c: c.z, top=True)
        tail = slab_centre(b['cos'], lambda c: c.y, top=False)
        head.z = b['z1']
        tail.z = b['z0'] + (b['z1'] - b['z0']) * 0.25
        return head, tail
    return Vec((b['cx'], b['cy'], b['z1'])), Vec((b['cx'], b['cy'], b['z0']))


# The torso bone stops at the neck, which is where the head geometry starts.
neck_z = bounds['Head']['z0']
hip_z = min(bounds['L_higher_leg']['z1'], bounds['R_higher_leg']['z1'])
body_cy = bounds['Body']['cy']
head_y = bounds['Head']['cy'] * 0.3

EXPLICIT = {
    'root': (Vec((0.0, 0.0, 0.0)), Vec((0.0, 0.0, hip_z * 0.3)), None, False),
    'hips': (Vec((0.0, body_cy, hip_z)), Vec((0.0, body_cy, hip_z + 0.8)), 'root', False),
    'Body': (Vec((0.0, body_cy, hip_z + 0.8)), Vec((0.0, head_y, neck_z)), 'hips', True),
    'Head': (Vec((0.0, head_y, neck_z)), Vec((0.0, head_y, neck_z + 3.8)), 'Body', True),
}

# --- 2. One vertex group per part, every vertex in it at weight 1.0. ---
for ob in meshes:
    vg = ob.vertex_groups.new(name=ob.name)
    vg.add(list(range(len(ob.data.vertices))), 1.0, 'REPLACE')

# --- 3. Armature. ---
arm_data = bpy.data.armatures.new("SonicArmature")
arm = bpy.data.objects.new("Armature", arm_data)
bpy.context.scene.collection.objects.link(arm)

bpy.ops.object.select_all(action='DESELECT')
bpy.context.view_layer.objects.active = arm
arm.select_set(True)
bpy.ops.object.mode_set(mode='EDIT')

eb = arm_data.edit_bones
order = ['root', 'hips', 'Body', 'Head'] + [n for n in SPEC if n not in ('Body', 'Head')]
created = {}
for name in order:
    if name in EXPLICIT:
        head, tail, parent, connect = EXPLICIT[name]
    else:
        head, tail = limb_head_tail(name)
        parent, connect = SPEC[name]
    b = eb.new(name)
    b.head, b.tail = head, tail
    if parent:
        b.parent = created[parent]
        # Only connect where the joint really is shared, or Blender moves the head.
        b.use_connect = bool(connect) and (b.parent.tail - head).length < 1e-4
    created[name] = b

bpy.ops.object.mode_set(mode='OBJECT')

# --- 4. Join the parts into one skinned mesh, then bind. ---
bpy.ops.object.select_all(action='DESELECT')
body = bpy.data.objects['Body']
for ob in meshes:
    ob.select_set(True)
bpy.context.view_layer.objects.active = body
bpy.ops.object.join()
body.name = "Sonic"
body.data.name = "Sonic"

body.parent = arm
body.matrix_parent_inverse = arm.matrix_world.inverted()
mod = body.modifiers.new("Armature", 'ARMATURE')
mod.object = arm

# --- 5. Check the bind before saving. ---
groups = {g.index: g.name for g in body.vertex_groups}
bad = 0
for v in body.data.vertices:
    gs = [(groups[g.group], g.weight) for g in v.groups if g.weight > 0.0]
    if len(gs) != 1 or abs(gs[0][1] - 1.0) > 1e-4 or gs[0][0] not in created:
        bad += 1

print("\nbones: %d" % len(arm_data.bones))
print("verts: %d, tris: %d"
      % (len(body.data.vertices),
         sum(max(len(p.vertices) - 2, 0) for p in body.data.polygons)))
print("verts not bound to exactly one real bone at weight 1.0: %d" % bad)
print("materials: %d" % len(body.data.materials))

print("\n%-16s %-16s %-5s %-22s %s" % ("bone", "parent", "conn", "head", "tail"))
for b in arm_data.bones:
    print("%-16s %-16s %-5s (%5.2f,%5.2f,%5.2f) (%5.2f,%5.2f,%5.2f)"
          % (b.name, b.parent.name if b.parent else "-", b.use_connect,
             b.head_local.x, b.head_local.y, b.head_local.z,
             b.tail_local.x, b.tail_local.y, b.tail_local.z))

bpy.ops.wm.save_as_mainfile(filepath=OUT)
print("\nsaved %s" % OUT)
