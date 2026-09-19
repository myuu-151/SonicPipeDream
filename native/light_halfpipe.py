"""Set up a lit EEVEE scene around the half-pipe, for looking at in the
viewport's Rendered mode. Nothing is rendered to a file.

    blender -b <pipe.blend> --python native/light_halfpipe.py -- <out.blend>

Adds a camera, two suns, a gradient sky that also fills the shadows, and the
EEVEE and colour settings. It does not touch the meshes or their modifiers.
"""

import math
import sys

import bpy
from mathutils import Vector

OUT_BLEND = sys.argv[sys.argv.index("--") + 1]

sc = bpy.context.scene
for ob in bpy.data.objects:
    if ob.mode != 'OBJECT':
        bpy.context.view_layer.objects.active = ob
        bpy.ops.object.mode_set(mode='OBJECT')

# --- render settings ----------------------------------------------------------
sc.render.engine = 'BLENDER_EEVEE'
sc.render.resolution_x, sc.render.resolution_y = 1280, 720
sc.render.resolution_percentage = 100
sc.render.film_transparent = False

# Standard, not the default AgX/Filmic: those are built to tame real-world
# contrast and they grey out saturated flat colours, which is all this scene is.
sc.view_settings.view_transform = 'Standard'
sc.view_settings.look = 'None'
sc.view_settings.exposure = 0.0
sc.view_settings.gamma = 1.0

ee = sc.eevee
for attr, value in (("taa_render_samples", 64), ("taa_samples", 16),
                    ("use_shadows", True), ("shadow_ray_count", 2), ("shadow_step_count", 6),
                    ("use_raytracing", True), ("use_gtao", True)):
    if hasattr(ee, attr):
        try:
            setattr(ee, attr, value)
        except (TypeError, AttributeError):
            pass

# --- sky: a vertical gradient that doubles as the fill light -------------------
world = bpy.data.worlds.get("HP_Sky") or bpy.data.worlds.new("HP_Sky")
sc.world = world
world.use_nodes = True
nt = world.node_tree
nt.nodes.clear()
geo = nt.nodes.new("ShaderNodeNewGeometry")
sep = nt.nodes.new("ShaderNodeSeparateXYZ")
ramp = nt.nodes.new("ShaderNodeValToRGB")
bg = nt.nodes.new("ShaderNodeBackground")
out = nt.nodes.new("ShaderNodeOutputWorld")
# Incoming is the view direction; its Z runs -1 (straight down) to +1 (up).
maprange = nt.nodes.new("ShaderNodeMapRange")
maprange.inputs["From Min"].default_value = -0.15
maprange.inputs["From Max"].default_value = 0.9
nt.links.new(geo.outputs["Incoming"], sep.inputs[0])
nt.links.new(sep.outputs["Z"], maprange.inputs["Value"])
nt.links.new(maprange.outputs["Result"], ramp.inputs["Fac"])
ramp.color_ramp.elements[0].position = 0.0
ramp.color_ramp.elements[0].color = (0.18, 0.42, 0.72, 1.0)     # pale at the horizon
ramp.color_ramp.elements[1].position = 1.0
ramp.color_ramp.elements[1].color = (0.0, 0.035, 0.13, 1.0)     # deep overhead
nt.links.new(ramp.outputs["Color"], bg.inputs["Color"])
bg.inputs["Strength"].default_value = 1.0
nt.links.new(bg.outputs["Background"], out.inputs["Surface"])

# --- sun ------------------------------------------------------------------------
def add_light(name, kind, energy, colour, rot_deg, angle_deg=None):
    old = bpy.data.objects.get(name)
    if old is not None:
        bpy.data.objects.remove(old, do_unlink=True)
    data = bpy.data.lights.new(name, kind)
    data.energy = energy
    data.color = colour
    if angle_deg is not None:
        data.angle = math.radians(angle_deg)
    ob = bpy.data.objects.new(name, data)
    ob.rotation_euler = tuple(math.radians(d) for d in rot_deg)
    sc.collection.objects.link(ob)
    return ob

# High and a little ahead of the camera, so the light rakes down the pipe and
# the walls shade from bright floor to darker rim the way the reference does.
add_light("HP_Sun", 'SUN', 3.2, (1.0, 0.97, 0.90), (28.0, 0.0, -68.0), angle_deg=8.0)
# A weak cool sun from the other side keeps the shadowed wall from going dead.
add_light("HP_Fill", 'SUN', 0.7, (0.65, 0.80, 1.0), (50.0, 0.0, 115.0), angle_deg=30.0)

# --- materials: the spheres are the only glossy thing in the picture ------------
for mat in bpy.data.materials:
    if not mat.use_nodes:
        continue
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    if bsdf is None:
        continue
    if "Sphere" in mat.name:
        bsdf.inputs["Roughness"].default_value = 0.18
    elif "Rail" in mat.name:
        bsdf.inputs["Roughness"].default_value = 0.45
    else:
        bsdf.inputs["Roughness"].default_value = 0.8

# --- camera: standing in the pipe, looking down it -------------------------------
old = bpy.data.objects.get("HP_Camera")
if old is not None:
    bpy.data.objects.remove(old, do_unlink=True)
cam_data = bpy.data.cameras.new("HP_Camera")
cam_data.lens = 14.0
cam_data.clip_start = 0.1
cam_data.clip_end = 2000.0
cam = bpy.data.objects.new("HP_Camera", cam_data)
sc.collection.objects.link(cam)
pos, target = Vector((3.0, 0.0, 4.2)), Vector((140.0, 0.0, 8.0))
cam.location = pos
cam.rotation_euler = (target - pos).to_track_quat('-Z', 'Y').to_euler()
sc.camera = cam

# Open straight into Rendered mode, so the lighting is what you see first.
views = 0
for screen in bpy.data.screens:
    for area in screen.areas:
        if area.type == 'VIEW_3D':
            for space in area.spaces:
                if space.type == 'VIEW_3D':
                    space.shading.type = 'RENDERED'
                    views += 1
print("3D viewports set to Rendered:", views)

bpy.ops.wm.save_as_mainfile(filepath=OUT_BLEND)
print("saved", OUT_BLEND)
