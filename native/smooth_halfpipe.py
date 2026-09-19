"""Put a hand-edited half-pipe section back onto one clean round curve.

    blender -b <in.blend> --python native/smooth_halfpipe.py -- <out.blend>

Editing the pipe by hand (cutting shapes into the lanes, sliding vertices) moves
points off the circle a little at a time. This snaps every vertex of the pipe's
inner surface back to the exact radius at the angle it already has, so shapes
cut into the surface keep their outline and only their height is corrected.
It also doubles the edges up the walls, where the facets show most, and makes
the whole surface shade smooth with a hard break only at the rim.
"""

import math
import sys

import bmesh
import bpy

OUT = sys.argv[sys.argv.index("--") + 1]

NAME = "HalfPipeSection.001"
RADIUS = 10.0
AXIS_Z = RADIUS            # the pipe's axis runs along X at this height, y = 0
TOLERANCE = 0.3            # how far off the circle still counts as the surface
MAX_ARC_DEG = 6.0          # cut any cross-pipe edge wider than this

ob = bpy.data.objects[NAME]
# The file may have been saved mid-edit, and a mesh cannot be written to while
# it is in Edit Mode.
bpy.context.view_layer.objects.active = ob
if ob.mode != 'OBJECT':
    bpy.ops.object.mode_set(mode='OBJECT')
me = ob.data
bm = bmesh.new()
bm.from_mesh(me)


def angle_of(v):
    return math.atan2(-v.co.y, AXIS_Z - v.co.z)      # 0 at the floor, 90 deg at the rim


def on_surface(v):
    # The inner surface, and not the deck beyond the rim, which is also at
    # z = RADIUS but further out than the circle reaches.
    r = math.hypot(v.co.y, AXIS_Z - v.co.z)
    return abs(r - RADIUS) < TOLERANCE and abs(v.co.y) <= RADIUS + 1e-4


def snap(v):
    a = angle_of(v)
    v.co.y = -RADIUS * math.sin(a)
    v.co.z = AXIS_Z - RADIUS * math.cos(a)


surface = [v for v in bm.verts if on_surface(v)]
worst = max(abs(math.hypot(v.co.y, AXIS_Z - v.co.z) - RADIUS) for v in surface)
for v in surface:
    snap(v)
print("snapped %d surface verts; the worst was %.3f off the circle" % (len(surface), worst))

# Double the edges wherever a cross-pipe edge spans too much of the arc. Those
# are the edges whose ends share an x, which leaves the lengthwise edges and the
# hand-cut arrow alone.
surf = set(surface)
wide = [e for e in bm.edges
        if e.verts[0] in surf and e.verts[1] in surf
        and abs(e.verts[0].co.x - e.verts[1].co.x) < 1e-4
        and abs(math.degrees(angle_of(e.verts[0]) - angle_of(e.verts[1]))) > MAX_ARC_DEG]
res = bmesh.ops.subdivide_edges(bm, edges=wide, cuts=1, use_grid_fill=True)
new = [g for g in res["geom_inner"] if isinstance(g, bmesh.types.BMVert)]
for v in new:
    snap(v)       # a midpoint of a chord is inside the circle; push it out onto it
print("cut %d wide edges, adding %d verts" % (len(wide), len(new)))

# Smooth everywhere on the surface, hoop band included; flat only on the deck.
surf = set(v for v in bm.verts if on_surface(v))
for f in bm.faces:
    f.smooth = all(v in surf for v in f.verts)
# The rim is a real corner, so stop the smoothing from rounding it over.
for e in bm.edges:
    kinds = set(f.smooth for f in e.link_faces)
    e.smooth = len(kinds) < 2

bm.normal_update()
bm.to_mesh(me)
bm.free()

angs = sorted(set(round(math.degrees(math.atan2(-v.co.y, AXIS_Z - v.co.z)), 2)
                  for v in me.vertices if abs(math.hypot(v.co.y, AXIS_Z - v.co.z) - RADIUS) < 1e-3
                  and abs(v.co.y) <= RADIUS + 1e-4))
gaps = [b - a for a, b in zip(angs, angs[1:])]
off = max(abs(math.hypot(v.co.y, AXIS_Z - v.co.z) - RADIUS) for v in me.vertices
          if abs(math.hypot(v.co.y, AXIS_Z - v.co.z) - RADIUS) < TOLERANCE and abs(v.co.y) <= RADIUS + 1e-4)
print("now: %d verts, %d polys; widest arc step %.2f deg; worst off-circle %.6f"
      % (len(me.vertices), len(me.polygons), max(gaps), off))
print("flat faces left:", sorted(set(me.materials[p.material_index].name
                                     for p in me.polygons if not p.use_smooth)))

bpy.ops.wm.save_as_mainfile(filepath=OUT)
print("saved", OUT)
