"""GRAVEYARD SHIFT concept blockout: a quick EEVEE render of the Halloween stage plan (claudedocs/halloween_stage_plan.md)
so the layout, scale, palette, glows, lasers, fog and crowd density can be judged before anything is built for real.

Boxes, tubes and spheres only; nothing here is pipeline output. Same frame as the Dino generator after its stage drop:
meters, Z up, the DJ at the origin on Tribe's floor (z=0) facing -Y, the crowd toward -Y on the field at z=-1.5, the
stage deck top at z=-1, the cathedral behind the DJ (+Y). Cameras match dino_stage.render_preview's positions.

    blender -b --factory-startup --python concept_blockout.py -- --out <dir> [--samples 32] [--views stream,dj_back,...]
"""
import math
import os
import random
import sys
import time

import bmesh
import bpy
from mathutils import Matrix, Vector

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "grounds"))
import kit  # noqa: E402  (box / cyl / cone / sphere / quad / truss / led_text; read-only use of the shared kit)

ARGS = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []


def arg(name, default=None):
    return ARGS[ARGS.index(name) + 1] if name in ARGS and ARGS.index(name) + 1 < len(ARGS) else default


OUT = os.path.abspath(arg("--out", os.path.join(HERE, "concept")))
SAMPLES = int(arg("--samples", "32"))
VIEWS = arg("--views", "stream,dj_back,crowd,facade,venue,dj_left").split(",")
os.makedirs(OUT, exist_ok=True)
rng = random.Random(31)
T0 = time.time()


def log(msg):
    print(f"[HW {time.time() - T0:6.1f}s] {msg}", flush=True)


def crowd_half(y):
    return 20 + 0.55 * (-y)


# ------------------------------------------------------------------ scene
bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
scene.render.engine = "BLENDER_EEVEE_NEXT"
scene.eevee.taa_render_samples = SAMPLES
scene.eevee.use_shadows = False
scene.eevee.use_raytracing = False
scene.eevee.use_gtao = False
scene.render.resolution_x, scene.render.resolution_y = 1600, 900
scene.render.image_settings.file_format = "PNG"
scene.view_settings.view_transform = "Standard"          # AgX turns neon pastel (VJ-loop lesson)
scene.view_settings.exposure = 0.4
scene.use_nodes = True
nt = scene.node_tree
nt.nodes.clear()
_rl = nt.nodes.new("CompositorNodeRLayers")
_g = nt.nodes.new("CompositorNodeGlare")
_g.glare_type, _g.quality = "BLOOM", "HIGH"
_g.inputs["Threshold"].default_value = 1.0
_g.inputs["Smoothness"].default_value = 0.3
_g.inputs["Strength"].default_value = 0.5
_g.inputs["Size"].default_value = 0.35
_comp = nt.nodes.new("CompositorNodeComposite")
nt.links.new(_rl.outputs["Image"], _g.inputs["Image"])
nt.links.new(_g.outputs["Image"], _comp.inputs["Image"])
scene.render.use_compositing = True
world = bpy.data.worlds.new("Night")
world.use_nodes = True
world.node_tree.nodes["Background"].inputs["Color"].default_value = (0.0, 0.0, 0.0, 1)
scene.world = world


# ------------------------------------------------------------------ materials
def _mat(name):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    m.node_tree.nodes.clear()
    return m, m.node_tree, m.node_tree.nodes.new("ShaderNodeOutputMaterial")


def M_flat(name, rgb, rough=0.8):
    m, t, out = _mat(name)
    p = t.nodes.new("ShaderNodeBsdfPrincipled")
    p.inputs["Base Color"].default_value = (*rgb, 1)
    p.inputs["Roughness"].default_value = rough
    t.links.new(p.outputs[0], out.inputs["Surface"])
    return m


def M_emit(name, rgb, strength=1.0):
    m, t, out = _mat(name)
    e = t.nodes.new("ShaderNodeEmission")
    e.inputs["Color"].default_value = (*rgb, 1)
    e.inputs["Strength"].default_value = strength
    t.links.new(e.outputs[0], out.inputs["Surface"])
    return m


def M_glow_alpha(name, rgb, strength, alpha):
    """Emission seen through alpha (beams, fire, ghosts): blended, overlapping."""
    m, t, out = _mat(name)
    e = t.nodes.new("ShaderNodeEmission")
    e.inputs["Color"].default_value = (*rgb, 1)
    e.inputs["Strength"].default_value = strength
    tr = t.nodes.new("ShaderNodeBsdfTransparent")
    mix = t.nodes.new("ShaderNodeMixShader")
    mix.inputs["Fac"].default_value = alpha
    t.links.new(tr.outputs[0], mix.inputs[1])
    t.links.new(e.outputs[0], mix.inputs[2])
    t.links.new(mix.outputs[0], out.inputs["Surface"])
    m.surface_render_method = "BLENDED"
    m.use_transparency_overlap = True
    m.use_backface_culling = False
    return m


def M_noise_emit(name, c0, c1, scale, strength=1.0, detail=4.0):
    """Emissive noise between two colors in object space (sky clouds, moon crust, visuals)."""
    m, t, out = _mat(name)
    tc = t.nodes.new("ShaderNodeTexCoord")
    n = t.nodes.new("ShaderNodeTexNoise")
    n.inputs["Scale"].default_value = scale
    n.inputs["Detail"].default_value = detail
    ramp = t.nodes.new("ShaderNodeValToRGB")
    ramp.color_ramp.elements[0].color = (*c0, 1)
    ramp.color_ramp.elements[1].color = (*c1, 1)
    ramp.color_ramp.elements[0].position = 0.35
    ramp.color_ramp.elements[1].position = 0.7
    e = t.nodes.new("ShaderNodeEmission")
    e.inputs["Strength"].default_value = strength
    t.links.new(tc.outputs["Object"], n.inputs["Vector"])
    t.links.new(n.outputs["Fac"], ramp.inputs["Fac"])
    t.links.new(ramp.outputs["Color"], e.inputs["Color"])
    t.links.new(e.outputs[0], out.inputs["Surface"])
    return m


def M_fog(name, rgb=(0.13, 0.11, 0.17), alpha=0.55, scale=0.08):
    m, t, out = _mat(name)
    tc = t.nodes.new("ShaderNodeTexCoord")
    n = t.nodes.new("ShaderNodeTexNoise")
    n.inputs["Scale"].default_value = scale
    n.inputs["Detail"].default_value = 5.0
    n.inputs["Roughness"].default_value = 0.65
    ramp = t.nodes.new("ShaderNodeValToRGB")
    ramp.color_ramp.elements[0].position = 0.42
    ramp.color_ramp.elements[1].position = 0.72
    mul = t.nodes.new("ShaderNodeMath")
    mul.operation = "MULTIPLY"
    mul.inputs[1].default_value = alpha
    e = t.nodes.new("ShaderNodeEmission")
    e.inputs["Color"].default_value = (*rgb, 1)
    e.inputs["Strength"].default_value = 1.0
    tr = t.nodes.new("ShaderNodeBsdfTransparent")
    mix = t.nodes.new("ShaderNodeMixShader")
    t.links.new(tc.outputs["Object"], n.inputs["Vector"])
    t.links.new(n.outputs["Fac"], ramp.inputs["Fac"])
    t.links.new(ramp.outputs["Color"], mul.inputs[0])
    t.links.new(mul.outputs[0], mix.inputs["Fac"])
    t.links.new(tr.outputs[0], mix.inputs[1])
    t.links.new(e.outputs[0], mix.inputs[2])
    t.links.new(mix.outputs[0], out.inputs["Surface"])
    m.surface_render_method = "BLENDED"
    m.use_transparency_overlap = True
    m.use_backface_culling = False
    return m


def M_visuals(name):
    """Stand-in for a VJ loop on the wall: black with thin wobbling neon bands (orange, green, purple), low average luma."""
    m, t, out = _mat(name)
    tc = t.nodes.new("ShaderNodeTexCoord")
    w = t.nodes.new("ShaderNodeTexWave")
    w.inputs["Scale"].default_value = 0.11
    w.inputs["Distortion"].default_value = 5.0
    w.inputs["Detail"].default_value = 3.0
    ramp = t.nodes.new("ShaderNodeValToRGB")
    cr = ramp.color_ramp
    cr.interpolation = "CONSTANT"
    cr.elements[0].position, cr.elements[0].color = 0.0, (0.01, 0.0, 0.02, 1)
    cr.elements[1].position, cr.elements[1].color = 0.44, (1.0, 0.40, 0.05, 1)
    for pos, col in ((0.50, (0.01, 0.0, 0.02, 1)), (0.70, (0.15, 1.0, 0.25, 1)), (0.735, (0.01, 0.0, 0.02, 1)),
                     (0.90, (0.40, 0.10, 1.0, 1)), (0.94, (0.01, 0.0, 0.02, 1))):
        e = cr.elements.new(pos)
        e.color = col
    em = t.nodes.new("ShaderNodeEmission")
    em.inputs["Strength"].default_value = 1.4
    t.links.new(tc.outputs["Object"], w.inputs["Vector"])
    t.links.new(w.outputs["Fac"], ramp.inputs["Fac"])
    t.links.new(ramp.outputs["Color"], em.inputs["Color"])
    t.links.new(em.outputs[0], out.inputs["Surface"])
    return m


# palette (plan section 2)
ORANGE, PURPLE, GREEN, RED = (1.0, 0.40, 0.05), (0.40, 0.10, 1.0), (0.15, 1.0, 0.25), (1.0, 0.08, 0.05)
AMBER, BONE, MOONBLUE, CANDLE = (1.0, 0.60, 0.12), (0.40, 0.40, 0.42), (0.35, 0.65, 1.0), (1.0, 0.55, 0.2)
STONE = M_flat("stone", (0.17, 0.17, 0.19), 0.85)
STONE_DARK = M_flat("stone_dark", (0.08, 0.08, 0.09), 0.9)
IRON = M_flat("iron", (0.03, 0.03, 0.035), 0.6)
BARK = M_flat("bark", (0.05, 0.035, 0.02), 0.9)
DECK = M_flat("deck", (0.025, 0.025, 0.03), 0.6)
GROUND = M_flat("ground", (0.035, 0.04, 0.03), 0.95)
FAR = M_flat("far", (0.004, 0.004, 0.006), 1.0)
WATER = M_flat("water", (0.008, 0.01, 0.03), 0.12)
PUMPKIN = M_emit("pumpkin_skin", (0.30, 0.08, 0.012), 1.0)      # self-lit dim: the patch is beyond the stage lights
GLOW = {k: M_emit("glow_" + k, c, s) for k, (c, s) in {
    "orange": (ORANGE, 3.0), "purple": (PURPLE, 3.0), "green": (GREEN, 2.5), "red": (RED, 3.0), "amber": (AMBER, 2.5),
    "bone": (BONE, 1.0), "candle": (CANDLE, 4.0), "laser_red": (RED, 7.0), "laser_green": (GREEN, 6.0),
    "wisp": ((0.4, 1.0, 0.5), 6.0), "lantern": ((1.0, 0.5, 0.15), 2.0), "window_red": ((1.0, 0.12, 0.05), 2.2),
    "window_purple": ((0.5, 0.15, 1.0), 2.2), "window_green": ((0.2, 1.0, 0.3), 1.8), "window_amber": (AMBER, 2.0),
    "eyes": (RED, 8.0), "black": ((0.0, 0.0, 0.0), 0.0), "marquee": ((1.0, 0.75, 0.35), 3.0),
    "ledwall": ((0.45, 0.12, 0.9), 1.2), "banner": (ORANGE, 2.5)}.items()}


def new_obj(name, bm, mats):
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    for m in mats:
        me.materials.append(m)
    ob = bpy.data.objects.new(name, me)
    scene.collection.objects.link(ob)
    return ob


def setmat(faces, idx):
    for f in faces:
        f.material_index = idx
    return faces


def bm_merge(dst, src):
    """Append src's faces (with material indices) to dst. bmesh.ops cost O(whole mesh) per call, so repeated items
    (people, trees) are built in their own small bmesh and merged, instead of thousands of ops on one growing mesh."""
    src.verts.index_update()
    vmap = [dst.verts.new(v.co) for v in src.verts]
    for f in src.faces:
        try:
            dst.faces.new([vmap[v.index] for v in f.verts]).material_index = f.material_index
        except ValueError:
            pass
    src.free()


def prism(bm, center, w, d, h):
    """Pitched roof: a triangle in XZ (base w, height h) extruded along Y by d; base at center.z."""
    cx, cy, cz = center
    v = [bm.verts.new(p) for p in ((cx - w / 2, cy - d / 2, cz), (cx + w / 2, cy - d / 2, cz), (cx, cy - d / 2, cz + h),
                                   (cx - w / 2, cy + d / 2, cz), (cx + w / 2, cy + d / 2, cz), (cx, cy + d / 2, cz + h))]
    return [bm.faces.new(f) for f in ((v[0], v[1], v[2]), (v[5], v[4], v[3]), (v[0], v[2], v[5], v[3]),
                                      (v[1], v[4], v[5], v[2]), (v[0], v[3], v[4], v[1]))]


def spot(name, pos, target, color, energy, angle_deg, blend=0.6):
    L = bpy.data.lights.new(name, "SPOT")
    L.color, L.energy, L.spot_size, L.spot_blend = color, energy, math.radians(angle_deg), blend
    L.shadow_soft_size = 1.0
    ob = bpy.data.objects.new(name, L)
    ob.location = pos
    ob.rotation_euler = (Vector(target) - Vector(pos)).to_track_quat("-Z", "Y").to_euler()
    scene.collection.objects.link(ob)
    return ob


def point(name, pos, color, energy, radius=0.5):
    L = bpy.data.lights.new(name, "POINT")
    L.color, L.energy, L.shadow_soft_size = color, energy, radius
    ob = bpy.data.objects.new(name, L)
    ob.location = pos
    scene.collection.objects.link(ob)
    return ob


def pointed_arch(w, zs, n=14):
    """Outline of a pointed (drop) arch of half-width w springing at height zs: list of (x, z) from left to right.
    Two arcs of radius 1.25w centred at (+-0.25w, zs); apex at zs + 1.2247w."""
    R, c = 1.25 * w, 0.25 * w
    pts = []
    for i in range(n + 1):                      # left arc: from (-w, zs) up to the apex
        a0 = math.atan2(0.0, -w - c)            # pi
        a1 = math.atan2(math.sqrt(R * R - c * c), -c)
        a = a0 + (a1 - a0) * i / n
        pts.append((c + R * math.cos(a), zs + R * math.sin(a)))
    for i in range(1, n + 1):                   # right arc, mirrored
        x, z = pts[n - i]
        pts.append((-x, z))
    return pts


# ------------------------------------------------------------------ ground, sky, moon, bats
bm = bmesh.new()
setmat(kit.box(bm, (0, -50, -1.5 - 0.05), (300, 300, 0.1)), 0)                       # the field
setmat(kit.box(bm, (0, -50, -1.5 - 0.3), (1400, 1400, 0.1)), 1)                      # far black ground
setmat(kit.box(bm, (0, -112, -1.5 + 0.01), (130, 36, 0.02)), 2)                      # the swamp (back center)
new_obj("Ground", bm, [GROUND, FAR, WATER])

bm = bmesh.new()
kit.sphere(bm, (0, 0, 0), 480, segs=48, rings=24)
bmesh.ops.reverse_faces(bm, faces=bm.faces[:])
new_obj("Sky", bm, [M_noise_emit("sky", (0.002, 0.0015, 0.006), (0.03, 0.02, 0.055), 0.012, 1.0, 6.0)])

MOON = Vector((-30, 100, 80))      # high and off-axis: clears the gable from the field and the stream cameras; the DJ
bm = bmesh.new()                   # never sees it over the facade (26 m gable at 14 m = 62 degrees up), the drone does
kit.cyl(bm, MOON + Vector((0, 0.3, 0)), MOON - Vector((0, 0.3, 0)), 14.0, segs=48)   # blood moon disc facing -Y
new_obj("Moon", bm, [M_noise_emit("moon", (0.95, 0.25, 0.06), (0.30, 0.05, 0.015), 0.25, 1.3, 5.0)])

bm = bmesh.new()
for i in range(150):                                                                 # bats: silhouettes on the moon
    c = MOON + Vector((rng.uniform(-12, 12), rng.uniform(-14, -6), rng.uniform(-11, 12)))
    yaw = rng.uniform(0, math.pi)
    kit.box(bm, c, (0.45, 0.04, 0.12), yaw=yaw)
    kit.box(bm, c + Vector((0.3 * math.cos(yaw), 0.3 * math.sin(yaw), 0.08)), (0.35, 0.03, 0.05), yaw=yaw, roll=0.6)
    kit.box(bm, c - Vector((0.3 * math.cos(yaw), 0.3 * math.sin(yaw), -0.08)), (0.35, 0.03, 0.05), yaw=yaw, roll=-0.6)
new_obj("Bats", bm, [GLOW["black"]])
log("ground, sky, moon, bats")

# ------------------------------------------------------------------ the cathedral
bm = bmesh.new()
F = []                                                                               # stone faces
for sx in (-1, 1):
    cx = 24 * sx
    F += kit.box(bm, (cx, 18, 17), (8, 8, 36))                                       # tower z -1..35
    for k in range(6):                                                               # crenellations
        for side in (-1, 1):
            F += kit.box(bm, (cx + (k - 2.5) * 1.4, 18 + side * 3.6, 35.6), (0.8, 0.8, 1.2))
            F += kit.box(bm, (cx + side * 3.6, 18 + (k - 2.5) * 1.4, 35.6), (0.8, 0.8, 1.2))
    for k in range(3):                                                               # string courses
        F += kit.box(bm, (cx, 18, 2 + 11 * k), (8.6, 8.6, 0.5))
    F += kit.box(bm, (cx, 13.3, 16), (9.5, 1.6, 0.5))                                # balconies (rig)
    F += kit.box(bm, (cx, 13.3, 26), (9.5, 1.6, 0.5))
    for (bx, by) in ((cx - 3.6, 14.4), (cx + 3.6, 14.4), (cx - 3.6, 21.6), (cx + 3.6, 21.6)):   # pinnacles
        F += kit.cone(bm, (bx, by, 35), (bx, by, 39.5), 0.7, segs=6)
if True:                                                                             # spires: left whole, right snapped
    F += kit.cone(bm, (-24, 18, 35), (-24, 18, 46), 3.6, segs=8)
    F += kit.cyl(bm, (24, 18, 35), (24, 18, 39.5), 3.6, segs=8, r2=2.2)
    for k in range(5):
        a = k * 2 * math.pi / 5
        F += kit.box(bm, (24 + 1.6 * math.cos(a), 18 + 1.6 * math.sin(a), 40 + rng.uniform(0, 1.5)), (1.0, 1.0, 1.8),
                     yaw=a, pitch=rng.uniform(-0.3, 0.3))
F += kit.box(bm, (0, 14.5, 10), (40, 1.0, 22))                                       # nave wall z -1..21
F += prism(bm, (0, 14.5, 21), 40, 1.0, 5)                                            # gable to z 26
F += kit.box(bm, (0, 30, 6), (30, 30, 0.1))                                          # roofless nave footprint (aerial)
for sx in (-1, 1):
    F += kit.box(bm, (sx * 14.5, 30, 5), (1.0, 30, 12))                              # nave side walls
    for k in range(4):                                                               # flying buttress fins
        F += kit.box(bm, (sx * (17.5 + 0.0 * k), 12.6 + 0.7 * k, 2 + 4 * k), (1.0, 1.4, 4 + 2 * k), pitch=-0.35)
# portal: 4 tube orders stepping forward and outward, pointed arches springing at z 7
for k in range(4):
    y, w = 14.0 - 1.1 * k, 12.5 + 1.0 * k
    pts = pointed_arch(w, 7.0)
    r = 0.45 + 0.05 * k
    for (x0, z0), (x1, z1) in zip(pts[:-1], pts[1:]):
        F += kit.cyl(bm, (x0, y, z0), (x1, y, z1), r, segs=8, cap=False)
    for sx in (-1, 1):
        F += kit.cyl(bm, (sx * w, y, -1), (sx * w, y, 7.0), r, segs=8)               # jambs
        F += kit.box(bm, (sx * (w + 0.9), y, 3), (1.8, 1.0, 8))                      # jamb blocks
# clock on the gable
F += kit.cyl(bm, (0, 14.1, 20), (0, 13.75, 20), 3.3, segs=36)
# gargoyles: tower corners
G = []
for sx in (-1, 1):
    for gx in (20, 28):
        for gy in (14, 22):
            b = Vector((sx * gx, gy, 35.6))
            F += kit.box(bm, b + Vector((0, 0, 0.8)), (1.2, 1.4, 1.6))
            F += kit.cone(bm, b + Vector((0, -0.9 if gy == 14 else 0.9, 1.3)), b + Vector((0, -2.0 if gy == 14 else 2.0, 1.1)), 0.5, segs=6)
            F += kit.box(bm, b + Vector((-0.9, 0, 1.6)), (1.4, 0.15, 0.8), roll=0.7)
            F += kit.box(bm, b + Vector((0.9, 0, 1.6)), (1.4, 0.15, 0.8), roll=-0.7)
new_obj("Cathedral", bm, [STONE])
# windows (glow) on the towers' front and inner faces, 3 tiers
bm = bmesh.new()
wmats = [GLOW["window_red"], GLOW["window_purple"], GLOW["window_green"], GLOW["window_amber"]]
for sx in (-1, 1):
    cx = 24 * sx
    for tier, z in enumerate((5.0, 14.0, 23.0)):
        for wx in (-2.2, 2.2):
            k = rng.randrange(4)
            setmat(kit.box(bm, (cx + wx, 13.92, z), (1.4, 0.1, 3.6)), k)
            setmat(kit.cone(bm, (cx + wx, 13.92, z + 1.8), (cx + wx, 13.92, z + 2.9), 0.7, segs=4), k)
        for wy in (16.0, 20.0):
            k = rng.randrange(4)
            setmat(kit.box(bm, (sx * 19.92, wy, z), (0.1, 1.4, 3.6)), k)
            setmat(kit.cone(bm, (sx * 19.92, wy, z + 1.8), (sx * 19.92, wy, z + 2.9), 0.7, segs=4), k)
new_obj("Windows", bm, wmats)
# clock face: dotted rim, 12 marks, hands at 11:58, dim red face glow
bm = bmesh.new()
for i in range(36):
    a = i * 2 * math.pi / 36
    setmat(kit.box(bm, (3.1 * math.cos(a), 13.7, 20 + 3.1 * math.sin(a)), (0.18, 0.1, 0.18)), 0)
for i in range(12):
    a = i * 2 * math.pi / 12
    setmat(kit.box(bm, (2.6 * math.cos(a), 13.7, 20 + 2.6 * math.sin(a)), (0.3, 0.1, 0.3)), 0)
setmat(kit.box(bm, (0, 13.65, 20.9), (0.22, 0.1, 1.9)), 1)                           # hour hand: 12
setmat(kit.box(bm, (-0.25, 13.6, 21.3), (0.14, 0.1, 2.7), roll=0.1), 1)              # minute hand: 11:58
setmat(kit.cyl(bm, (0, 13.74, 20), (0, 13.72, 20), 3.0, segs=36), 2)
new_obj("Clock", bm, [GLOW["amber"], GLOW["eyes"], M_emit("clockface", (0.12, 0.01, 0.005), 1.0)])
log("cathedral")

# ------------------------------------------------------------------ screen, deck, riser, booth, DJ, lip
bm = bmesh.new()
kit.quad(bm, (11.5, 10.3, -0.27), (-11.5, 10.3, -0.27), (-11.5, 10.3, 12.67), (11.5, 10.3, 12.67))
new_obj("VisualScreen", bm, [M_visuals("visuals")])

bm = bmesh.new()
setmat(kit.box(bm, (0, 4.5, -1.25), (50, 18, 0.5)), 0)                               # deck top z -1
setmat(kit.box(bm, (0, 0.3, -0.5), (3.2, 2.4, 1.0)), 1)                              # riser top z 0 (Tribe floor)
setmat(kit.box(bm, (-0.05, 0.225, 0.37), (1.8, 0.55, 0.74)), 2)                      # booth = TABLE dims
for dx in (-0.55, 0.45):
    setmat(kit.box(bm, (dx, 0.2, 0.78), (0.42, 0.34, 0.08)), 2)                      # decks
setmat(kit.box(bm, (-0.05, 0.2, 0.78), (0.3, 0.3, 0.08)), 2)                         # mixer
for sx in (-1, 1):                                                                   # gargoyles flanking the riser
    setmat(kit.box(bm, (sx * 2.6, 0.3, 0.6), (0.7, 0.7, 1.2)), 0)
    setmat(kit.cone(bm, (sx * 2.6, -0.1, 1.3), (sx * 2.6, -0.9, 1.1), 0.3, segs=6), 0)
setmat(kit.cyl(bm, (-0.1, 0.9, 0), (-0.1, 0.9, 1.45), 0.2, segs=8), 3)               # DJ placeholder
setmat(kit.sphere(bm, (-0.1, 0.9, 1.62), 0.13, segs=8, rings=5), 3)
# iron fence barrier at y=-7.5 with spikes
setmat(kit.box(bm, (0, -7.5, -0.3), (62, 0.08, 0.08)), 0)
setmat(kit.box(bm, (0, -7.5, -0.9), (62, 0.08, 0.08)), 0)
for i in range(32):
    x = -31 + i * 2
    setmat(kit.cyl(bm, (x, -7.5, -1.5), (x, -7.5, 0.0), 0.05, segs=5), 0)
    setmat(kit.cone(bm, (x, -7.5, 0.0), (x, -7.5, 0.35), 0.08, segs=5), 0)
# portal truss with heads underneath
setmat(kit.truss(bm, (-14, 10.5, 16.5), (14, 10.5, 16.5), size=0.6, step=1.2), 0)
new_obj("Deck", bm, [IRON, STONE_DARK, DECK, M_flat("dj", (0.25, 0.25, 0.27), 0.6)])

bm = bmesh.new()
for sx in (-1, 1):                                                                   # booth edge strip, gargoyle eyes
    setmat(kit.box(bm, (sx * 2.6 - 0.12, -0.3, 1.0), (0.1, 0.05, 0.1)), 1)
    setmat(kit.box(bm, (sx * 2.6 + 0.12, -0.3, 1.0), (0.1, 0.05, 0.1)), 1)
setmat(kit.box(bm, (-0.05, -0.06, 0.73), (1.84, 0.04, 0.04)), 0)
for (cx, cy) in ((-1.5, -0.8), (1.5, -0.8), (-1.5, 1.3), (1.5, 1.3)):               # candle clusters on the riser
    for j in range(5):
        a = j * 1.26
        setmat(kit.cyl(bm, (cx + 0.18 * math.cos(a), cy + 0.18 * math.sin(a), 0), (cx + 0.18 * math.cos(a), cy + 0.18 * math.sin(a), 0.15 + 0.05 * j), 0.03, segs=5), 2)
for i in range(11):                                                                  # lanterns on the barrier posts
    x = -30 + i * 6
    setmat(kit.sphere(bm, (x, -7.5, 0.55), 0.17, segs=6, rings=4), 3)
for i in range(7):                                                                   # lanterns hanging from the truss
    x = -12 + i * 4
    setmat(kit.cyl(bm, (x, 10.5, 16.2), (x, 10.5, 12.5), 0.03, segs=4), 4)
    setmat(kit.box(bm, (x, 10.5, 12.2), (0.4, 0.4, 0.55)), 3)
new_obj("DeckGlow", bm, [GLOW["orange"], GLOW["eyes"], GLOW["candle"], GLOW["lantern"], IRON])
# flame jets along the lip (drop moment)
bm = bmesh.new()
for x in (-18, -12, -6, 6, 12, 18):
    kit.cone(bm, (x, -4, -1.0), (x, -4, 1.6 + rng.uniform(-0.3, 0.5)), 0.55, segs=8)
    kit.cone(bm, (x, -4, -1.0), (x, -4, 0.9), 0.3, segs=8)
new_obj("Flames", bm, [M_glow_alpha("flame", (1.0, 0.32, 0.03), 2.5, 0.55)])
log("deck, riser, booth, barrier, flames")

# ------------------------------------------------------------------ rig: heads, beams, lasers, searchlights
heads = []                                                                           # (pos, target, color)
balc_targets = [(-38, -22), (-26, -40), (-12, -55), (4, -30), (-4, -30), (12, -55), (26, -40), (38, -22)]
for sx in (-1, 1):
    for z in (16.4, 26.4):
        for k in range(4):
            hx = 24 * sx + (k - 1.5) * 2.2
            tx, ty = balc_targets[k + (4 if sx > 0 else 0)]
            heads.append(((hx, 12.4, z + 0.4), (tx * (1 if z < 20 else 0.7), ty, -1.5), [ORANGE, PURPLE, GREEN, AMBER][(k + int(z)) % 4]))
for k in range(6):
    x = -12.5 + k * 5
    heads.append(((x, 10.5, 15.9), (x * 1.8, -18 - 4 * (k % 3), -1.5), [ORANGE, PURPLE][k % 2]))
bm = bmesh.new()
for p, t, c in heads:
    kit.box(bm, p, (0.45, 0.45, 0.5))
new_obj("Heads", bm, [IRON])
bmats, bm = [], bmesh.new()
for i, (p, t, c) in enumerate(heads):
    d = (Vector(t) - Vector(p)).normalized()
    setmat(kit.cyl(bm, Vector(p) + d * 0.6, Vector(p) + d * 75, 0.2, segs=10, cap=False, r2=1.8), i)
    bmats.append(M_glow_alpha(f"beam{i}", c, 0.9, 0.035))
new_obj("Beams", bm, bmats)
# gargoyle laser fans (red, green) from the tower-front mouths; portal fan red
bm = bmesh.new()
fans = [((-20, 13.4, 36.4), "laser_red"), ((-28, 13.4, 36.4), "laser_green"), ((20, 13.4, 36.4), "laser_green"),
        ((28, 13.4, 36.4), "laser_red"), ((0, 11, 21.5), "laser_red")]
for o, key in fans:                                                                  # 7 lines each, skimming over the crowd
    o = Vector(o)
    base = (Vector((o.x * 0.3, -78, 2.0)) - o)
    n = 7
    for i in range(n):
        ang = math.radians(-22 + 44 * i / (n - 1))
        d = (Matrix.Rotation(ang, 4, "Z") @ base).normalized()
        setmat(kit.cyl(bm, o, o + d * 150, 0.05, segs=5, cap=False), 0 if key == "laser_red" else 1)
new_obj("Lasers", bm, [GLOW["laser_red"], GLOW["laser_green"]])
# searchlights: 4 units, 2 beams each, crossing up and out
bm = bmesh.new()
for (ux, uy) in ((-32, -92), (32, -92), (-30, 22), (30, 22)):
    for d in (Vector((0.35 * (1 if ux > 0 else -1), -0.25, 1)), Vector((-0.15 * (1 if ux > 0 else -1), 0.3, 1))):
        d.normalize()
        kit.cyl(bm, Vector((ux, uy, -1.5)), Vector((ux, uy, -1.5)) + d * 320, 0.5, segs=10, cap=False, r2=7)
new_obj("Searchlights", bm, [M_glow_alpha("search", (0.65, 0.5, 1.0), 0.8, 0.03)])
log("rig, beams, lasers, searchlights")

# ------------------------------------------------------------------ fog sheets
bm = bmesh.new()
kit.box(bm, (0, -40, -1.25), (112, 68, 0.02))
new_obj("FogA", bm, [M_fog("fogA", alpha=0.5, scale=0.07)])
bm = bmesh.new()
kit.box(bm, (0, -38, -0.9), (108, 64, 0.02))
new_obj("FogB", bm, [M_fog("fogB", (0.12, 0.09, 0.16), alpha=0.35, scale=0.11)])
bm = bmesh.new()
kit.box(bm, (0, 2.5, -0.75), (50, 14, 0.02))
new_obj("FogDeck", bm, [M_fog("fogDeck", (0.09, 0.07, 0.12), alpha=0.4, scale=0.25)])

# ------------------------------------------------------------------ crowd (simple people, Halloween mix)
BODY = [M_flat("c_black", (0.015, 0.015, 0.018)), M_flat("c_purple", (0.05, 0.02, 0.09)), M_flat("c_green", (0.02, 0.07, 0.03)),
        M_flat("c_bone", (0.5, 0.48, 0.42)), M_flat("c_orange", (0.5, 0.14, 0.02)), M_flat("c_red", (0.35, 0.03, 0.03)),
        M_flat("c_grey", (0.22, 0.22, 0.26))]
HEAD = [M_flat("h_skin1", (0.5, 0.33, 0.24)), M_flat("h_skin2", (0.3, 0.18, 0.11)), M_flat("h_pumpkin", (0.6, 0.18, 0.02)),
        M_flat("h_bone", (0.55, 0.53, 0.48)), M_flat("h_green", (0.2, 0.35, 0.15))]
STICK = [GLOW["orange"], GLOW["purple"], GLOW["green"], GLOW["red"]]
CROWD_MATS = BODY + HEAD + STICK + [IRON]
NB, NH, NS = len(BODY), len(HEAD), len(STICK)
body_w = [50, 12, 8, 9, 6, 8, 3]


def person(dst, x, y, z0, rng, face_dir=1):
    bm = bmesh.new()
    _person(bm, x, y, z0, rng, face_dir)
    bm_merge(dst, bm)


def _person(bm, x, y, z0, rng, face_dir=1):
    h = rng.uniform(1.55, 1.9)
    b = rng.choices(range(NB), body_w)[0]
    if b == 6:                                                                       # ghost: a sheet, no head
        setmat(kit.cone(bm, (x, y, z0 + h), (x, y, z0 + 0.2), 0.35, segs=7), NB + 3 if rng.random() < 0.2 else 6)
        return
    setmat(kit.cyl(bm, (x, y, z0), (x, y, z0 + h - 0.3), 0.21, segs=6), b)
    hd = 3 if b == 3 else (2 if rng.random() < 0.06 else (4 if rng.random() < 0.05 else rng.randrange(2)))
    setmat(kit.sphere(bm, (x, y, z0 + h - 0.12), 0.13, segs=6, rings=4), NB + hd)
    if rng.random() < 0.12:                                                          # witch hat
        setmat(kit.cone(bm, (x, y, z0 + h), (x, y, z0 + h + 0.6), 0.28, segs=6), 0)
        setmat(kit.cyl(bm, (x, y, z0 + h - 0.02), (x, y, z0 + h + 0.03), 0.42, segs=8), 0)
    r = rng.random()
    if r < 0.38:                                                                     # an arm up, maybe a glow stick
        ax = x + rng.choice((-0.28, 0.28))
        setmat(kit.cyl(bm, (ax, y, z0 + h - 0.45), (ax, y, z0 + h + 0.35), 0.045, segs=5), b)
        if rng.random() < 0.7:
            setmat(kit.cyl(bm, (ax, y, z0 + h + 0.3), (ax, y, z0 + h + 0.62), 0.03, segs=5), NB + NH + rng.randrange(NS))
    elif r < 0.5:                                                                    # phone / bucket glow at chest
        setmat(kit.box(bm, (x, y - 0.26 * face_dir, z0 + h - 0.55), (0.1, 0.02, 0.16)), NB + NH + rng.randrange(NS))


EXCL = [(-4.5, -33.5, 4.5, -28.5), (-18.5, -43.5, -15.5, -40.5), (15.5, -43.5, 18.5, -40.5),
        (-16.5, -66.5, -13.5, -63.5), (13.5, -66.5, 16.5, -63.5)]
bm = bmesh.new()
y, n_people = -8.6, 0
while y > -63:
    s = 0.78 + 0.013 * (-y)
    hw = crowd_half(y) * (1 if y > -55 else (1 - (-55 - y) / 16))                   # the last rows feather out
    x = -hw + rng.uniform(0, s)
    while x < hw:
        if not any(x0 <= x <= x1 and y0 <= y <= y1 for x0, y0, x1, y1 in EXCL) and rng.random() < 0.93:
            person(bm, x + rng.uniform(-0.15, 0.15), y + rng.uniform(-0.2, 0.2), -1.5, rng)
            n_people += 1
        x += s
    y -= s * 1.05
for i in range(100):                                                                 # THE CRYPT's own crowd
    person(bm, rng.uniform(50, 70), rng.uniform(-122, -112), -1.5, rng, face_dir=-1)
    n_people += 1
for i in range(20):                                                                  # ghouls between the stones
    sx = rng.choice((-1, 1))
    yy = rng.uniform(-60, -12)
    person(bm, sx * (crowd_half(yy) + rng.uniform(3, 13)), yy, -1.5, rng)
new_obj("Crowd", bm, CROWD_MATS)
log(f"crowd: {n_people} people")

# ------------------------------------------------------------------ graveyard strips, mausoleums, totems
bm = bmesh.new()
for i in range(420):
    sx = rng.choice((-1, 1))
    yy = rng.uniform(-70, -10)
    x = sx * (crowd_half(yy) + rng.uniform(3, 14))
    r = rng.random()
    if r < 0.72:
        setmat(kit.box(bm, (x, yy, -1.5 + 0.45), (0.65, 0.16, 0.9), yaw=rng.uniform(-0.4, 0.4), roll=rng.uniform(-0.18, 0.18)), 0)
    elif r < 0.9:
        setmat(kit.box(bm, (x, yy, -1.5 + 1.1), (0.5, 0.5, 2.2), yaw=rng.uniform(-0.3, 0.3)), 0)
        setmat(kit.cone(bm, (x, yy, -1.5 + 2.2), (x, yy, -1.5 + 2.8), 0.3, segs=4), 0)
    else:
        setmat(kit.box(bm, (x, yy, -1.5 + 0.9), (0.18, 0.18, 1.8)), 0)
        setmat(kit.box(bm, (x, yy, -1.5 + 1.35), (0.9, 0.18, 0.18)), 0)
for sx in (-1, 1):                                                                   # mausoleums housing delay stacks
    for yy in (-25, -50):
        x = sx * (crowd_half(yy) + 8.5)
        setmat(kit.box(bm, (x, yy, -1.5 + 2.25), (6, 6, 4.5)), 0)
        setmat(prism(bm, (x, yy, -1.5 + 4.5), 6.4, 6.6, 1.8), 0)
        setmat(kit.box(bm, (x - sx * 3.02, yy, -1.5 + 1.3), (0.1, 1.4, 2.6)), 1)     # green door glow, facing the crowd
        for k in range(4):
            setmat(kit.cyl(bm, (x - sx * 3.6, yy - 2.2 + k * 1.45, -1.5), (x - sx * 3.6, yy - 2.2 + k * 1.45, -1.5 + 3.2), 0.18, segs=6), 0)
# totems held up in the crowd: skull / pumpkin heads on poles with glow
for i in range(70):
    yy = rng.uniform(-60, -12)
    x = rng.uniform(-crowd_half(yy) * 0.95, crowd_half(yy) * 0.95)
    if any(x0 <= x <= x1 and y0 <= yy <= y1 for x0, y0, x1, y1 in EXCL):
        continue
    setmat(kit.cyl(bm, (x, yy, -0.8), (x, yy, 1.6), 0.03, segs=4), 0)
    setmat(kit.sphere(bm, (x, yy, 1.78), 0.22, segs=6, rings=4), 1 if rng.random() < 0.5 else 2)
new_obj("Graveyard", bm, [STONE, GLOW["window_green"], GLOW["orange"]])
for sx in (-1, 1):
    for yy in (-18, -36, -56):
        point(f"grave_{sx}_{yy}", (sx * (crowd_half(yy) + 7), yy, -0.3), rng.choice([GREEN, PURPLE]), 900, 0.6)
log("graveyard")


# ------------------------------------------------------------------ dead forest (L-system tubes) + lanterns
def tree(bm, base, d, L, r, depth, rng, tips):
    tip = base + d * L
    kit.cyl(bm, base, tip, r, segs=6, cap=False, r2=r * 0.6)
    if depth == 0:
        tips.append(tip)
        return
    for k in range(rng.choice((2, 2, 3))):
        axis = d.cross(Vector((rng.uniform(-1, 1), rng.uniform(-1, 1), rng.uniform(-0.2, 0.6)))).normalized()
        nd = (Matrix.Rotation(rng.uniform(0.35, 0.8), 4, axis) @ d).normalized()
        nd.z = max(nd.z, -0.1)
        tree(bm, tip, nd.normalized(), L * rng.uniform(0.6, 0.78), r * 0.62, depth - 1, rng, tips)


bm_t, bm_l, tips_near = bmesh.new(), bmesh.new(), []
sites = [(sx * (crowd_half(yy) + 26 + rng.uniform(0, 10)), yy) for yy in range(-15, -80, -8) for sx in (-1, 1)]
sites += [(x + rng.uniform(-3, 3), rng.uniform(-100, -78)) for x in range(-84, 85, 9)]
sites += [(rng.uniform(-130, 130), rng.uniform(-150, -100)) for _ in range(28)]
for (x, yy) in sites:
    tips = []
    h = rng.uniform(7, 11)
    tb = bmesh.new()
    tree(tb, Vector((x, yy, -1.5)), Vector((rng.uniform(-0.1, 0.1), rng.uniform(-0.1, 0.1), 1)).normalized(), h, 0.45, 3, rng, tips)
    bm_merge(bm_t, tb)
    if yy > -40:
        for t in rng.sample(tips, min(3, len(tips))):
            kit.cyl(bm_l, t, t - Vector((0, 0, 0.8)), 0.02, segs=4)
            kit.box(bm_l, t - Vector((0, 0, 1.05)), (0.35, 0.35, 0.5))
for sx in (-1, 1):                                                                   # two giant dead oaks by the towers
    tips = []
    tb = bmesh.new()
    tree(tb, Vector((sx * 36, 6, -1.5)), Vector((sx * 0.08, 0.05, 1)).normalized(), 13, 1.3, 4, rng, tips)
    bm_merge(bm_t, tb)
    for t in rng.sample(tips, 10):
        kit.cyl(bm_l, t, t - Vector((0, 0, 1.2)), 0.03, segs=4)
        kit.box(bm_l, t - Vector((0, 0, 1.5)), (0.5, 0.5, 0.7))
new_obj("Forest", bm_t, [BARK])
new_obj("Lanterns", bm_l, [GLOW["lantern"]])
log("forest")

# ------------------------------------------------------------------ pumpkin patch, Pumpkin King, scarecrows
bm = bmesh.new()
for i in range(230):
    x, yy = rng.uniform(44, 76), rng.uniform(-101, -79)
    r = rng.uniform(0.3, 0.5)
    pb = bmesh.new()
    setmat(kit.sphere(pb, (x, yy, -1.5 + r * 0.8), r, segs=8, rings=5, scale=(1, 1, 0.8)), 0)
    if rng.random() < 0.35:
        setmat(kit.box(pb, (x, yy + r * 0.92, -1.5 + r * 0.9), (r * 0.7, 0.05, r * 0.45)), 1)
    bm_merge(bm, pb)
kx, ky = 60, -92
setmat(kit.sphere(bm, (kx, ky, -1.5 + 3.4), 4.0, segs=14, rings=8, scale=(1, 1, 0.85)), 0)
setmat(kit.cyl(bm, (kx, ky, -1.5 + 6.6), (kx, ky, -1.5 + 8.2), 0.5, segs=6, r2=0.3), 2)
setmat(kit.box(bm, (kx - 1.3, ky + 3.75, -1.5 + 4.4), (1.3, 0.1, 1.0), roll=0.4), 1)  # eyes, mouth (toward the DJ)
setmat(kit.box(bm, (kx + 1.3, ky + 3.75, -1.5 + 4.4), (1.3, 0.1, 1.0), roll=-0.4), 1)
for k in range(5):
    setmat(kit.box(bm, (kx - 2.0 + k * 1.0, ky + 3.85, -1.5 + 2.4 + (0.35 if k % 2 else 0)), (0.8, 0.1, 0.8), roll=0.78), 1)
for i in range(6):
    x, yy = rng.uniform(46, 74), rng.uniform(-100, -80)
    setmat(kit.cyl(bm, (x, yy, -1.5), (x, yy, -1.5 + 3.0), 0.08, segs=5), 2)
    setmat(kit.box(bm, (x, yy, -1.5 + 2.3), (1.8, 0.1, 0.1)), 2)
    setmat(kit.sphere(bm, (x, yy, -1.5 + 3.2), 0.3, segs=6, rings=4), 0)
new_obj("Pumpkins", bm, [PUMPKIN, GLOW["orange"], BARK])
log("pumpkins")

# ------------------------------------------------------------------ haunted carnival (back-left) and THE CRYPT (back-right)
bm = bmesh.new()
cx, cy = -60, -110
setmat(kit.cyl(bm, (cx, cy, -1.5), (cx, cy, -0.9), 6.5, segs=16), 0)                # carousel platform
setmat(kit.cone(bm, (cx, cy, 4.2), (cx, cy, 8.5), 7.2, segs=16), 0)                  # roof
for k in range(8):
    a = k * math.pi / 4
    px, py = cx + 4.6 * math.cos(a), cy + 4.6 * math.sin(a)
    setmat(kit.cyl(bm, (px, py, -0.9), (px, py, 4.3), 0.08, segs=5), 0)
    setmat(kit.box(bm, (px, py, 0.4), (0.4, 1.4, 1.0), yaw=a), 1)                    # skeletal horses
for k in range(28):
    a = k * 2 * math.pi / 28
    setmat(kit.sphere(bm, (cx + 7.1 * math.cos(a), cy + 7.1 * math.sin(a), 4.3), 0.16, segs=5, rings=3), 2 if k % 2 else 3)
hx, hy = -72, -100                                                                   # HOUSE OF HORRORS facade
setmat(kit.box(bm, (hx, hy, -1.5 + 4.5), (14, 2.5, 9)), 0)
setmat(kit.box(bm, (hx, hy + 1.3, -1.5 + 9.1), (14.4, 0.2, 0.3)), 3)
setmat(kit.box(bm, (hx - 7.1, hy + 1.3, -1.5 + 4.5), (0.3, 0.2, 9)), 3)
setmat(kit.box(bm, (hx + 7.1, hy + 1.3, -1.5 + 4.5), (0.3, 0.2, 9)), 3)
setmat(kit.box(bm, (hx, hy + 1.35, -1.5 + 7.5), (10, 0.1, 1.2)), 2)                  # marquee sign
setmat(kit.box(bm, (hx, hy + 1.3, -1.5 + 1.6), (2.6, 0.1, 3.2)), 4)                  # the dark mouth, green glow
for (wx, wy) in ((-48, -118), (-52, -126)):                                          # wagons, ticket booth
    setmat(kit.box(bm, (wx, wy, -1.5 + 1.5), (5, 2.5, 3)), 0)
    setmat(kit.box(bm, (wx, wy + 1.4, -1.5 + 3.1), (5.2, 0.4, 0.2)), 3)
setmat(kit.box(bm, (-44, -108, -1.5 + 1.3), (2, 2, 2.6)), 0)
setmat(kit.box(bm, (-44, -106.95, -1.5 + 1.6), (1.2, 0.1, 0.8)), 2)
# THE CRYPT second stage
qx, qy = 60, -128
setmat(kit.box(bm, (qx, qy, -1.5 + 3), (12, 6, 6)), 0)
setmat(prism(bm, (qx, qy, -1.5 + 6), 12.4, 6.4, 2.0), 0)
setmat(kit.box(bm, (qx, qy + 3.05, -1.5 + 3.4), (10, 0.1, 5)), 5)                    # LED wall, facing +Y
for sx in (-1, 1):
    setmat(kit.box(bm, (qx + sx * 7.5, qy + 2, -1.5 + 2.5), (1.6, 1.6, 5)), 0)
    setmat(kit.box(bm, (qx + sx * 7.5, qy + 2.85, -1.5 + 2.5), (0.2, 0.05, 4.6)), 3)
new_obj("Carnival", bm, [STONE_DARK, M_flat("skel", (0.5, 0.48, 0.44)), GLOW["marquee"], GLOW["purple"], GLOW["window_green"], GLOW["ledwall"]])
bm = bmesh.new()
kit.cyl(bm, (qx - 7.5, qy + 2, 1.5), (qx - 7.5 - 8, qy + 2 + 30, 90), 0.4, segs=8, cap=False, r2=3.5)
kit.cyl(bm, (qx + 7.5, qy + 2, 1.5), (qx + 7.5 + 8, qy + 2 + 30, 90), 0.4, segs=8, cap=False, r2=3.5)
new_obj("CryptBeams", bm, [M_glow_alpha("cryptbeam", PURPLE, 0.8, 0.07)])
point("carnival1", (cx, cy, 3), PURPLE, 2500, 1.0)
point("carnival2", (hx, hy + 4, 3), ORANGE, 2000, 1.0)
point("crypt", (qx, qy + 6, 2), PURPLE, 2500, 1.0)
# will-o-wisps over the swamp
bm = bmesh.new()
for i in range(60):
    kit.sphere(bm, (rng.uniform(-60, 60), rng.uniform(-128, -98), -1.5 + rng.uniform(0.4, 2.2)), 0.14, segs=5, rings=3)
new_obj("Wisps", bm, [GLOW["wisp"]])
log("carnival, crypt, swamp")

# ------------------------------------------------------------------ vendors, FOH, speaker towers, masts, ghosts
bm = bmesh.new()
vmats = [STONE_DARK, GLOW["orange"], GLOW["purple"], GLOW["window_green"], GLOW["marquee"]]
for sx in (-1, 1):
    for k, yy in enumerate(range(-16, -66, -8)):
        x = sx * (crowd_half(yy) + 16.1)
        setmat(kit.box(bm, (x, yy, -1.5 + 1.5), (3, 6, 3)), 0)
        setmat(kit.box(bm, (x - sx * 1.6, yy, -1.5 + 3.0), (0.3, 6.2, 0.25)), 1 + (k % 3))          # awning strip
        setmat(kit.box(bm, (x - sx * 1.52, yy, -1.5 + 1.7), (0.05, 2.4, 1.0)), 4)                   # service window
        for j in range(3):                                                                           # festoon mast
            setmat(kit.cyl(bm, (x - sx * 4, yy - 3 + j * 3, -1.5), (x - sx * 4, yy - 3 + j * 3, -1.5 + 4.5), 0.06, segs=4), 0)
for sx in (-1, 1):                                                                   # outhouses with a skull WC tower
    for j in range(8):
        setmat(kit.box(bm, (sx * (crowd_half(-70) + 16), -70 + j * 1.4, -1.5 + 1.1), (1.2, 1.2, 2.2)), 0)
    setmat(kit.cyl(bm, (sx * (crowd_half(-70) + 16), -58.5, -1.5), (sx * (crowd_half(-70) + 16), -58.5, -1.5 + 7), 0.1, segs=4), 0)
    setmat(kit.sphere(bm, (sx * (crowd_half(-70) + 16), -58.5, -1.5 + 7.3), 0.45, segs=8, rings=5), 3)
# FOH mausoleum with the GRAVEYARD SHIFT banner facing the DJ
setmat(kit.box(bm, (0, -31, -1.5 + 1.6), (8, 4, 3.2)), 0)
setmat(prism(bm, (0, -31, -1.5 + 3.2), 8.4, 4.4, 1.5), 0)
for sx in (-1, 1):                                                                   # follow spots on the FOH roof
    setmat(kit.box(bm, (sx * 2.5, -31, -1.5 + 4.9), (0.5, 0.7, 0.5)), 0)
    setmat(kit.cyl(bm, (sx * 2.5, -31, -1.5 + 4.5), (sx * 2.5, -31, -1.5 + 3.8), 0.08, segs=5), 0)
pw = 0.085
banner = kit.led_text(bm, "GRAVEYARD SHIFT", (kit.text_width("GRAVEYARD SHIFT", pw) / 2, -28.9, -1.5 + 3.4), (-1, 0, 0), (0, 0, 1), pixel=pw, gap=0.02)
setmat(banner, 1)
# crypt speaker towers in the crowd (purple strips + beams)
for (tx, ty) in ((-17, -42), (17, -42), (-15, -65), (15, -65)):
    for k in range(5):
        setmat(kit.box(bm, (tx, ty, -1.5 + 1 + 2 * k), (2, 2, 1.9)), 0)
    setmat(kit.box(bm, (tx, ty + 1.02, -1.5 + 5), (0.2, 0.05, 9.5)), 2)
    setmat(kit.box(bm, (tx, ty + 1.02, -1.5 + 9.3), (1.6, 0.05, 0.8)), 1)           # name panel
# light masts
for (mx, my) in ((-30, -58), (30, -58), (-24, -78), (24, -78)):
    setmat(kit.cyl(bm, (mx, my, -1.5), (mx, my, -1.5 + 14), 0.15, segs=6), 0)
    setmat(kit.box(bm, (mx, my, -1.5 + 14.2), (1.6, 1.6, 0.6)), 0)
new_obj("Infra", bm, vmats)
bm = bmesh.new()
for (tx, ty) in ((-17, -42), (17, -42), (-15, -65), (15, -65)):
    kit.cyl(bm, (tx, ty, 8.5), (tx + tx * 0.3, ty + 6, 100), 0.6, segs=8, cap=False, r2=4.0)
new_obj("TowerBeams", bm, [M_glow_alpha("towerbeam", PURPLE, 0.8, 0.04)])
bm = bmesh.new()
for i in range(6):                                                                   # ghosts over the graveyard strips
    sx = rng.choice((-1, 1))
    yy = rng.uniform(-55, -14)
    x = sx * (crowd_half(yy) + rng.uniform(4, 12))
    kit.box(bm, (x, yy, rng.uniform(3, 8)), (2.4, 0.2, 3.8), yaw=rng.uniform(0, 3.14), pitch=rng.uniform(-0.3, 0.3))
new_obj("Ghosts", bm, [M_glow_alpha("ghost", (0.55, 1.0, 0.65), 0.5, 0.28)])
log("vendors, FOH, towers, ghosts")

# ------------------------------------------------------------------ lights (the show, mid-drop)
spot("up_nave_L", (-9, 12.5, -1), (-6, 14.5, 18), ORANGE, 16000, 55)
spot("up_nave_R", (9, 12.5, -1), (6, 14.5, 18), ORANGE, 16000, 55)
spot("up_tower_L", (-26, 11.5, -1), (-24, 16, 26), PURPLE, 26000, 40)
spot("up_tower_R", (26, 11.5, -1), (24, 16, 26), PURPLE, 26000, 40)
fill = bpy.data.lights.new("moonfill", "SUN")                                       # cold sky bounce from the crowd side
fill.energy, fill.color = 0.35, (0.45, 0.55, 0.9)
fob = bpy.data.objects.new("moonfill", fill)
fob.rotation_euler = (Vector((0, 120, -60))).to_track_quat("-Z", "Y").to_euler()
scene.collection.objects.link(fob)
spot("wash_L", (-24, 12.4, 26.5), (-10, -28, -1.5), PURPLE, 90000, 70)
spot("wash_R", (24, 12.4, 26.5), (10, -28, -1.5), (0.3, 0.9, 0.4), 60000, 70)
spot("wash_C", (0, 10.5, 16), (0, -16, -1.5), ORANGE, 40000, 80)
spot("deck_L", (-0.45, 0.4, 1.5), (-0.5, 0.2, 0.78), (1.0, 0.75, 0.5), 60, 38)
spot("deck_R", (0.35, 0.4, 1.5), (0.4, 0.2, 0.78), (1.0, 0.75, 0.5), 60, 20)
spot("follow", (0, -31, 3.5), (0, 0.9, 1.4), (1.0, 0.9, 0.8), 2500, 6, 0.3)
spot("patch", (60, -90, 12), (60, -90, -1.5), ORANGE, 6000, 70)
moon = bpy.data.lights.new("moon", "SUN")
moon.energy, moon.color = 0.25, MOONBLUE
mob = bpy.data.objects.new("moon", moon)
mob.rotation_euler = (-MOON).to_track_quat("-Z", "Y").to_euler()
scene.collection.objects.link(mob)
log(f"scene built: {sum(len(o.data.polygons) for o in scene.objects if o.type == 'MESH')} faces")

# ------------------------------------------------------------------ cameras and renders (Dino preview positions)
CAMS = {
    "stream": ((0, -9, 3.5), (0, 6, 9), 16),
    "dj_back": ((0, -1.0, 1.7), (0, 10, 13), 16),
    "crowd": ((3, -50, 5.0), (0, 8, 12), 20),
    "facade": ((0, -55, 6.0), (0, 12, 18), 24),
    "venue": ((-80, -125, 62), (0, -25, 8), 24),
    "dj_left": ((0, -0.3, 1.65), (-45, -30, -1.0), 16),
    "dj_right": ((0, -0.3, 1.65), (45, -30, -1.0), 16),
    "back": ((0, -95, 12), (0, 0, 6), 24),
}
cam = bpy.data.cameras.new("cam")
cam.clip_end = 3000
cob = bpy.data.objects.new("cam", cam)
scene.collection.objects.link(cob)
scene.camera = cob
for name in VIEWS:
    pos, tgt, lens = CAMS[name]
    cam.lens = lens
    cob.location = pos
    cob.rotation_euler = (Vector(tgt) - Vector(pos)).to_track_quat("-Z", "Y").to_euler()
    scene.render.filepath = os.path.join(OUT, f"hw_concept_{name}.png")
    t = time.time()
    bpy.ops.render.render(write_still=True)
    log(f"rendered {name} in {time.time() - t:.1f}s -> {scene.render.filepath}")
log("done")
