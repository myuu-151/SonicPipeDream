"""Render a contact sheet of an action so the poses can actually be looked at.

Blender's bundled Python has no imaging library, so the tiles are composited
through bpy.data.images directly.
"""

import math
import os

import bpy
import mathutils

OUT = os.environ["S2S_SHEET_OUT"]
ACTION = os.environ.get("S2S_ACTION", "Run")
FRAMES = [int(f) for f in os.environ.get("S2S_FRAMES", "1,3,5,7,9,11,13,15").split(",")]
VIEW = os.environ.get("S2S_VIEW", "side")

TILE_W, TILE_H = 260, 360

arm = bpy.data.objects['Armature']
if ACTION == "REST":
    arm.animation_data.action = None
    for pb in arm.pose.bones:
        pb.rotation_quaternion = (1.0, 0.0, 0.0, 0.0)
        pb.location = (0.0, 0.0, 0.0)
else:
    arm.animation_data.action = bpy.data.actions[ACTION]
    # Blender 5 needs the slot chosen explicitly or the action drives nothing.
    slots = bpy.data.actions[ACTION].slots
    if slots:
        arm.animation_data.action_slot = slots[0]

scene = bpy.context.scene
scene.render.engine = 'BLENDER_WORKBENCH'
scene.render.resolution_x = TILE_W
scene.render.resolution_y = TILE_H
scene.render.resolution_percentage = 100
scene.render.image_settings.file_format = 'PNG'
scene.display.shading.light = 'STUDIO'
scene.display.shading.color_type = 'RANDOM'
scene.display.shading.show_cavity = True

cam_data = bpy.data.cameras.new("SheetCam")
cam_data.type = 'ORTHO'
cam_data.ortho_scale = float(os.environ.get('S2S_SCALE', '20.0'))
cam = bpy.data.objects.new("SheetCam", cam_data)
scene.collection.objects.link(cam)
scene.camera = cam

# Optional close-up: S2S_FOCUS names a bone to centre on at the first frame.
CENTRE = mathutils.Vector((0.0, 0.0, 6.5))
FOCUS = os.environ.get('S2S_FOCUS')
if FOCUS:
    scene.frame_set(FRAMES[0])
    CENTRE = arm.matrix_world @ arm.pose.bones[FOCUS].head.copy()
DIRS = {
    # name: (azimuth from -Y in degrees)
    'front': 0.0,
    'side': 90.0,
    'quarter': 42.0,
    'back': 180.0,
    'backq': 205.0,
}
az = math.radians(DIRS[VIEW])
offset = mathutils.Vector((math.sin(az) * 40.0, -math.cos(az) * 40.0, 0.0 if FOCUS else 4.0))
cam.location = CENTRE + offset
direction = (CENTRE - cam.location).normalized()
cam.rotation_euler = direction.to_track_quat('-Z', 'Y').to_euler()

tmp = os.path.join(os.path.dirname(OUT), "_tile")
tiles = []
for f in FRAMES:
    scene.frame_set(f)
    scene.render.filepath = "%s_%02d.png" % (tmp, f)
    bpy.ops.render.render(write_still=True)
    tiles.append(scene.render.filepath)

cols = len(tiles)
sheet = bpy.data.images.new("sheet", TILE_W * cols, TILE_H)
buf = [0.0] * (TILE_W * cols * TILE_H * 4)

for i, path in enumerate(tiles):
    img = bpy.data.images.load(path)
    px = list(img.pixels)
    for y in range(TILE_H):
        src = y * TILE_W * 4
        dst = (y * TILE_W * cols + i * TILE_W) * 4
        buf[dst:dst + TILE_W * 4] = px[src:src + TILE_W * 4]
    bpy.data.images.remove(img)

sheet.pixels = buf
sheet.filepath_raw = OUT
sheet.file_format = 'PNG'
sheet.save()

for path in tiles:
    os.remove(path)

print("wrote %s  (%s, %s, frames %s)" % (OUT, ACTION, VIEW, FRAMES))
