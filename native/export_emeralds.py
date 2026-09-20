"""The seven chaos emeralds, from external/Chaos_Emeralds/ into the project. Plain Python + Pillow.

    python native/export_emeralds.py

    -> proj/Assets/Stage/Emeralds/SM_Emerald_<stage 1-7>.oct     the gem, one per stage
                                  M_Emerald_<stage>.oct          its material: unlit, TRANSLUCENT
                                  T_Emerald_<stage>_Ref.oct      what it reflects
                                  T_Emerald_<stage>_Dif.oct      its facets

WHICH EMERALD IS WHICH STAGE follows Sonic 2's order as near as the seven colours allow:
1 blue, 2 yellow, 3 purple (S2's pink), 4 green, 5 red (S2's orange), 6 sky, 7 white.

HOW IT IS SHADED. The models came with two textures each: a facet map (`_dif`: pale faces,
dark edges, laid out by the model's own UVs) and a reflection picture (`_ref`), which the game
they are from wraps round the gem as an environment map. This engine's simple material has no
environment mapping, so the reflection is fixed to the gem instead, the way the gold rings'
is painted on: every vertex gets a SECOND UV from which way its facet faces, as seen from up
the track, and the reflection texture is read through that. The two textures are multiplied.
The game turns the gem to face back down the track, so the reflection faces the player.
The .mtl files name textures that are not in the folder and cross the colours over, so they
are not read: the textures are picked by colour here.
"""

import math
import os

from PIL import Image

from gen_s2sky_assets import (TYPE_MATERIALLITE, TYPE_STATICMESH, asset_ref, f32, header, i32, null_ref,
                              u8, u32, write_texture)

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.abspath(os.path.join(HERE, "..", "external", "Chaos_Emeralds"))
OUT = os.path.abspath(os.path.join(HERE, "..", "proj", "Assets", "Stage", "Emeralds"))

UUID = 0x51C0FFEE00005000           # + 16 * stage + (0 mesh, 1 material, 2 ref, 3 dif). 0x4000 is Sonic: sharing it crashed the game
# stage: (model, reflection texture, facet texture). Yellow came with no facet map: white's is
# colourless enough to serve, the yellow is all in its reflection.
EMERALDS = {
    1: ("BLUE", "b01_ref", "b_dif"), 2: ("YELLOW", "y01_ref", "w_dif"), 3: ("PURPLE", "p01_ref", "p_dif"),
    4: ("GREEN", "g01_ref", "g_dif"), 5: ("RED", "r01_ref", "r_dif"), 6: ("SKY", "bg01_ref", "bg_dif"),
    7: ("WHITE", "w01_ref", "w_dif"),
}
PART = "rdmobj01"                   # the outer shell: the one whose UVs fit the facet map
WIDTH = 3.6                         # how wide the gem is in the game; the model is 10.8
BLEND = 2                           # 0 opaque, 2 translucent
OPACITY = 0.80
BRIGHT = 1.0                        # the two textures multiplied come out dim; lift them
MATCAP_INNER = 0.24                 # and how near the middle (which is black) a facet facing the player reads
LIFT = 40                           # the darkest a facet gets, 0-255: a gem has no black in it
MATCAP_REACH = 0.46                 # how far from the middle of the reflection a sideways facet reads


def read_obj(path):
    vs, vts, tris, part = [], [], [], None
    for line in open(path):
        p = line.split()
        if not p:
            continue
        if p[0] == "v":
            vs.append(tuple(float(x) for x in p[1:4]))
        elif p[0] == "vt":
            vts.append((float(p[1]), float(p[2])))
        elif p[0] == "o":
            part = p[1]
        elif p[0] == "f" and part == PART:
            corners = [tuple(int(i) - 1 for i in c.split("/")[:2]) for c in p[1:]]
            for k in range(1, len(corners) - 1):                     # fan, in case a face is not a triangle
                tris.append((corners[0], corners[k], corners[k + 1]))
    return vs, vts, tris


def texture(stage, slot, name, source):
    img = Image.open(os.path.join(SRC, "event_rock_km_emerald%s.png" % source)).convert("RGB").convert("RGBA")
    write_texture(os.path.join(OUT, name + ".oct"), name, UUID + 16 * stage + slot, img.width, img.height,
                  img.tobytes(), wrap=1, force_hq=True, quiet=True)     # REPEAT: the UVs run well outside 0-1, and
                  # clamped, every facet read the dark pixel at the edge and the gem was black


def material(stage, name, ref, dif):
    d = header(TYPE_MATERIALLITE, UUID + 16 * stage + 1, name)
    d += u32(0)                     # numParameters
    d += u32(0)                     # Unlit: the reflection IS the lighting
    d += u32(BLEND)                 # BlendMode
    d += u32(1)                     # VertexColorMode::Modulate: the reflection is in the vertices
    d += u32(1)                     # numTextures
    d += asset_ref(UUID + 16 * stage + 3, dif) + u8(0) + u8(1)      # the facets, through uv0, modulate
    for _ in range(3):
        d += null_ref() + u8(0) + u8(1)
    for _ in range(2):
        d += f32(0) + f32(0) + f32(1) + f32(1)
    d += f32(BRIGHT) + f32(BRIGHT) + f32(BRIGHT) + f32(1)
    d += f32(1) + f32(0) + f32(0) + f32(0)
    d += f32(1.0) + f32(0.0) + f32(0.0) + f32(0.0)          # fresnelPower, emission, wrapLighting, specular
    d += u32(2) + f32(OPACITY) + f32(0.5) + f32(24.0)       # toon steps, OPACITY, mask cutoff, shininess
    d += i32(0)
    d += u8(0) + u8(0) + u8(1)
    d += u8(0)                      # no culling: the far facets show through the near ones
    open(os.path.join(OUT, name + ".oct"), "wb").write(d)


def mesh(stage, name, mat, vs, vts, tris, ref_img):
    rw, rh = ref_img.size
    rpx = ref_img.load()
    used = [vs[i] for tri in tris for i, _ in tri]
    scale = WIDTH / (max(v[0] for v in used) - min(v[0] for v in used))
    verts, idx = [], []
    for tri in tris:
        a, b, c = (vs[i] for i, _ in tri)
        n = [(b[1] - a[1]) * (c[2] - a[2]) - (b[2] - a[2]) * (c[1] - a[1]),
             (b[2] - a[2]) * (c[0] - a[0]) - (b[0] - a[0]) * (c[2] - a[2]),
             (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])]
        length = math.sqrt(sum(x * x for x in n)) or 1.0
        n = [x / length for x in n]
        # The model is Y up, as the engine is. The game points the gem's X back down the track,
        # so the player looks along X: a facet's reflection is read by how far it leans to the
        # side (Z) and up (Y). Flat facets: one normal, so one reflection point, per face -- but
        # nudged toward each corner, so a facet shows a patch of the reflection and not a dot.
        centre = [sum(vs[i][k] for i, _ in tri) / 3.0 for k in range(3)]
        for vi, ti in tri:
            p = vs[vi]
            lean = [(p[k] - centre[k]) * 0.035 for k in range(3)]
            # The MIDDLE of the reflection picture is black (it is what lies straight behind the
            # viewer), so a facet square to the player would be a hole. Read a ring of the picture
            # instead: never nearer its middle than MATCAP_INNER.
            sx, sy = n[2] + lean[2], n[1] + lean[1]
            far = math.sqrt(sx * sx + sy * sy)
            if far < 1e-4:
                sx, sy, far = 0.0, 1.0, 0.0
            else:
                sx, sy = sx / far, sy / far
            r = MATCAP_INNER + (MATCAP_REACH - MATCAP_INNER) * min(1.0, far)
            mu, mv = 0.5 + r * sx, 0.5 - r * sy
            c = rpx[min(rw - 1, int(mu * rw)), min(rh - 1, int(mv * rh))]
            colour = tuple(min(255, int(LIFT + (255 - LIFT) * (x / 255.0) ** 0.7)) for x in c[:3])
            u, v = vts[ti]
            idx.append(len(verts))
            verts.append(([x * scale for x in p], (u, 1.0 - v), colour, n))
    radius = max(math.sqrt(sum(x * x for x in v[0])) for v in verts)
    d = header(TYPE_STATICMESH, UUID + 16 * stage, name)
    d += u32(len(verts)) + u32(len(idx)) + u32(1)
    d += asset_ref(UUID + 16 * stage + 1, mat)
    d += u8(0) + u8(1)                                      # no triangle collision; HAS vertex colour
    for p, uv0, c, n in verts:
        d += f32(p[0]) + f32(p[1]) + f32(p[2]) + f32(uv0[0]) + f32(uv0[1]) + f32(0) + f32(0)
        d += f32(n[0]) + f32(n[1]) + f32(n[2])
        d += u32(c[0] | (c[1] << 8) | (c[2] << 16) | (255 << 24))
    for i in idx:
        d += u32(i)
    d += u8(0) + u32(0)
    d += f32(0) + f32(0) + f32(0) + f32(radius * 1.2)
    open(os.path.join(OUT, name + ".oct"), "wb").write(d)
    return len(verts), len(idx) // 3


def main():
    os.makedirs(OUT, exist_ok=True)
    for stage, (colour, ref, dif) in EMERALDS.items():
        vs, vts, tris = read_obj(os.path.join(SRC, "ChaosEmerald%s.obj" % colour))
        names = ["%s_Emerald_%d%s" % (kind, stage, tail) for kind, tail in
                 (("SM", ""), ("M", ""), ("T", "_Ref"), ("T", "_Dif"))]
        texture(stage, 2, names[2], ref)
        texture(stage, 3, names[3], dif)
        material(stage, names[1], names[2], names[3])
        ref_img = Image.open(os.path.join(SRC, "event_rock_km_emerald%s.png" % ref)).convert("RGB")
        nv, nt = mesh(stage, names[0], names[1], vs, vts, tris, ref_img)
        print("stage %d: %-6s %d triangles" % (stage, colour.lower(), nt))


if __name__ == "__main__":
    main()
