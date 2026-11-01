"""REACTOR concept blockout: a quick EEVEE render of the club plan (claudedocs/club_venue_plan.md, tribe hack repo) so the
room's layout, scale, palette, rig, lasers, haze and crowd density can be judged before anything is built for real.

Boxes, tubes and spheres only; nothing here is pipeline output. Same frame as the Dino generator: meters, Z up, the DJ at
the origin on Tribe's floor (z=0 is the stage deck) facing -Y, the dance floor at z=-1.2 toward -Y, the core bay behind
the DJ (+Y). The constants below mirror the plan's section 3.

    blender -b --factory-startup --python concept_blockout.py -- --out <dir> [--samples 32] [--views stream,crowd,...]

Views: stream, crowd, dj_view, gate, aerial, bar (the contact sheet) and gate_open (the airlock in its open state).
"""
import math
import os
import random
import sys
import time

import bmesh
import bpy
from mathutils import Vector

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "grounds"))
import kit  # noqa: E402  (box / cyl / cone / sphere / quad / truss / led_text; read-only use of the shared kit)

ARGS = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []


def arg(name, default=None):
    return ARGS[ARGS.index(name) + 1] if name in ARGS and ARGS.index(name) + 1 < len(ARGS) else default


OUT = os.path.abspath(arg("--out", os.path.join(HERE, "concept")))
SAMPLES = int(arg("--samples", "32"))
VIEWS = arg("--views", "stream,crowd,dj_view,gate,aerial,bar,gate_open").split(",")
os.makedirs(OUT, exist_ok=True)
rng = random.Random(55)
T0 = time.time()


def log(msg):
    print(f"[CLUB {time.time() - T0:6.1f}s] {msg}", flush=True)


# ------------------------------------------------------------------ layout (plan section 3)
FLOOR = -1.2                                   # dance floor top; the stage deck (Tribe's floor) is z 0
HX = 12.0                                      # hall interior half-width
Y_BACK, Y_BAY = -30.5, 13.0                    # back wall, core bay back wall
CEIL, STAGE_CEIL = 9.8, 12.8                   # ceiling over the floor / over the stage and the core bay
LIP_Y = -3.0                                   # stage lip and proscenium header line
SCREEN_Y, SCREEN_HW, SCREEN_Z0, SCREEN_Z1 = 5.4, 8.0, 0.5, 9.5
BARRIER_Y = -3.6
MZ_X0, MZ_X1, MZ_Y0, MZ_Y1, MZ_Z = 8.0, 12.0, -24.0, -8.0, 2.3
AIR_X0, AIR_X1, AIR_Y0, AIR_Y1 = -12.0, -8.0, -5.6, LIP_Y      # the airlock vestibule; the stairs are inside
DOOR_X0, DOOR_X1, DOOR_TOP, LINTEL_TOP = -11.2, -9.0, 1.4, 2.4
DOOR_MID = (DOOR_X0 + DOOR_X1) / 2
TRUSS_Y, TRUSS_Z = (-6.0, -12.0, -18.0, -24.0), 8.6
VESSEL, VR, VTOP = Vector((0.0, 9.4, 0.0)), 3.2, 9.6          # core vessel axis, radius, top of the cylinder
BAR_X0, BAR_X1, BAR_Y = -7.0, 3.0, -27.5
EX0, EX1 = 5.0, 8.0                                            # entrance in the back wall

# ------------------------------------------------------------------ scene (the Halloween blockout's setup)
bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
scene.render.engine = "BLENDER_EEVEE_NEXT"
scene.eevee.taa_render_samples = SAMPLES
scene.eevee.use_shadows = False
scene.eevee.use_raytracing = False
scene.eevee.use_gtao = False
scene.render.resolution_x, scene.render.resolution_y = 1600, 900
scene.render.image_settings.file_format = "JPEG"
scene.render.image_settings.quality = 92
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
    """Emission seen through alpha (beams, glass, halos): blended, overlapping."""
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


def M_fog(name, rgb, alpha, scale):
    """Haze sheet: noise-masked translucent emission."""
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


def M_stripes(name, c0, c1, strength=1.0, scale=1.6):
    """Hazard stripes: diagonal bands in object space, self-lit dim so they read in the dark."""
    m, t, out = _mat(name)
    tc = t.nodes.new("ShaderNodeTexCoord")
    w = t.nodes.new("ShaderNodeTexWave")
    w.wave_type, w.bands_direction, w.wave_profile = "BANDS", "DIAGONAL", "SAW"
    w.inputs["Scale"].default_value = scale
    w.inputs["Distortion"].default_value = 0.0
    ramp = t.nodes.new("ShaderNodeValToRGB")
    cr = ramp.color_ramp
    cr.interpolation = "CONSTANT"
    cr.elements[0].position, cr.elements[0].color = 0.0, (*c0, 1)
    cr.elements[1].position, cr.elements[1].color = 0.5, (*c1, 1)
    e = t.nodes.new("ShaderNodeEmission")
    e.inputs["Strength"].default_value = strength
    t.links.new(tc.outputs["Object"], w.inputs["Vector"])
    t.links.new(w.outputs["Fac"], ramp.inputs["Fac"])
    t.links.new(ramp.outputs["Color"], e.inputs["Color"])
    t.links.new(e.outputs[0], out.inputs["Surface"])
    return m


def M_visuals(name):
    """Stand-in for a VJ loop on the screens: black with thin wobbling bands in REACTOR blue, amber and white."""
    m, t, out = _mat(name)
    tc = t.nodes.new("ShaderNodeTexCoord")
    w = t.nodes.new("ShaderNodeTexWave")
    w.inputs["Scale"].default_value = 0.11
    w.inputs["Distortion"].default_value = 5.0
    w.inputs["Detail"].default_value = 3.0
    ramp = t.nodes.new("ShaderNodeValToRGB")
    cr = ramp.color_ramp
    cr.interpolation = "CONSTANT"
    dark = (0.0, 0.006, 0.02, 1)
    cr.elements[0].position, cr.elements[0].color = 0.0, dark
    cr.elements[1].position, cr.elements[1].color = 0.44, (*BLUE, 1)
    for pos, col in ((0.50, dark), (0.70, (*AMBER, 1)), (0.735, dark), (0.90, (*WHITE, 1)), (0.93, dark)):
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
BLUE, AMBER, RED = (0.10, 0.45, 1.0), (1.0, 0.55, 0.05), (1.0, 0.06, 0.03)
GREEN, WHITE = (0.15, 1.0, 0.25), (0.75, 0.85, 1.0)
CONCRETE = M_flat("concrete", (0.05, 0.05, 0.056), 0.9)
CONCRETE_DARK = M_flat("concrete_dark", (0.045, 0.045, 0.05), 0.9)
STEEL = M_flat("steel", (0.035, 0.04, 0.045), 0.45)
FLOORM = M_flat("floor", (0.025, 0.025, 0.028), 0.6)
DECK = M_flat("deck", (0.03, 0.03, 0.035), 0.5)
SOFA = M_flat("sofa", (0.06, 0.02, 0.015), 0.7)
DJ_M = M_flat("dj", (0.25, 0.25, 0.27), 0.6)
FAR = M_emit("far", (0.0, 0.0, 0.0), 0.0)
GLASS = M_glow_alpha("glass", (0.3, 0.55, 1.0), 0.25, 0.10)
HAZARD = M_stripes("hazard", (0.55, 0.28, 0.02), (0.012, 0.012, 0.012), strength=1.0, scale=1.6)
VISUALS = M_visuals("visuals")
GLOW = {k: M_emit("glow_" + k, c, s) for k, (c, s) in {
    "blue": (BLUE, 3.0), "blue_dim": (BLUE, 0.8), "amber": (AMBER, 3.0), "amber_dim": (AMBER, 0.9),
    "red": (RED, 4.0), "green": (GREEN, 3.0), "white": (WHITE, 2.5), "core": ((0.25, 0.6, 1.0), 6.0),
    "laser_green": (GREEN, 5.0), "laser_blue": ((0.2, 0.5, 1.0), 5.0), "beacon_red": (RED, 9.0),
    "beacon_green": (GREEN, 8.0), "bottle_amber": (AMBER, 1.6), "bottle_blue": (BLUE, 1.6),
    "bottle_green": (GREEN, 1.2), "bottle_white": (WHITE, 1.0), "uv": ((0.25, 0.3, 1.0), 2.5),
    "black": ((0.0, 0.0, 0.0), 0.0)}.items()}


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
    """Append src's faces (with material indices) to dst; repeated items are built in their own small bmesh (an op on
    one growing mesh costs O(mesh), the Halloween blockout's lesson)."""
    src.verts.index_update()
    vmap = [dst.verts.new(v.co) for v in src.verts]
    for f in src.faces:
        try:
            dst.faces.new([vmap[v.index] for v in f.verts]).material_index = f.material_index
        except ValueError:
            pass
    src.free()


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


def text_centered(bm, text, center_x, y, z, right, pixel, gap):
    """kit.led_text centred on center_x; right = (1,0,0) faces -Y (toward the crowd), (-1,0,0) faces +Y (the stage)."""
    w = kit.text_width(text, pixel)
    x0 = center_x - w / 2 if right[0] > 0 else center_x + w / 2
    return kit.led_text(bm, text, (x0, y, z), right, (0, 0, 1), pixel=pixel, gap=gap)


def solid(p):
    """What a beam can't pass: the hall's shell, the stage deck, the screen with its frame, the mezzanine decks."""
    x, y, z = p
    if abs(x) >= HX or y <= Y_BACK or y >= Y_BAY or z <= FLOOR:
        return True
    if z >= (CEIL if y < LIP_Y else STAGE_CEIL):
        return True
    if y >= LIP_Y and z <= 0.0:
        return True
    if y >= SCREEN_Y - 0.05 and abs(x) <= SCREEN_HW + 0.6 and z <= SCREEN_Z1 + 0.6:
        return True
    if MZ_X0 <= abs(x) and MZ_Y0 <= y <= MZ_Y1 and MZ_Z - 0.3 <= z <= MZ_Z:
        return True
    return False


def beam_len(o, d, maxlen=70.0, step=0.08):
    """Distance from o along d to the first surface (beams end on surfaces indoors: plan 4.7)."""
    t = 0.3
    while t < maxlen and not solid(o + d * t):
        t += step
    return t


# ------------------------------------------------------------------ hall shell
bm = bmesh.new()
kit.box(bm, (0, (Y_BACK + Y_BAY) / 2, FLOOR - 0.1), (2 * HX + 1, Y_BAY - Y_BACK + 1, 0.2))
new_obj("Floor", bm, [FLOORM])
for name, sx in (("WallL", -1), ("WallR", 1)):
    bm = bmesh.new()
    kit.box(bm, (sx * (HX + 0.2), (Y_BACK + Y_BAY) / 2, (FLOOR + STAGE_CEIL) / 2), (0.4, Y_BAY - Y_BACK, STAGE_CEIL - FLOOR))
    new_obj(name, bm, [CONCRETE])
bm = bmesh.new()                                                                  # back wall, entrance gap x 5..8
kit.box(bm, ((-HX + EX0) / 2, Y_BACK - 0.2, (FLOOR + CEIL) / 2), (EX0 + HX, 0.4, CEIL - FLOOR))
kit.box(bm, ((EX1 + HX) / 2, Y_BACK - 0.2, (FLOOR + CEIL) / 2), (HX - EX1, 0.4, CEIL - FLOOR))
kit.box(bm, ((EX0 + EX1) / 2, Y_BACK - 0.2, (FLOOR + 3.0 + CEIL) / 2), (EX1 - EX0, 0.4, CEIL - FLOOR - 3.0))
new_obj("WallBack", bm, [CONCRETE])
bm = bmesh.new()
kit.box(bm, (0, Y_BAY + 0.2, STAGE_CEIL / 2), (2 * HX, 0.4, STAGE_CEIL))
new_obj("WallBay", bm, [CONCRETE_DARK])
bm = bmesh.new()
kit.box(bm, (0, (Y_BACK + LIP_Y) / 2, CEIL + 0.1), (2 * HX, LIP_Y - Y_BACK, 0.2))
new_obj("Ceiling", bm, [CONCRETE_DARK])
bm = bmesh.new()
kit.box(bm, (0, (LIP_Y + Y_BAY) / 2, STAGE_CEIL + 0.1), (2 * HX, Y_BAY - LIP_Y, 0.2))
new_obj("StageCeiling", bm, [CONCRETE_DARK])
bm = bmesh.new()
kit.box(bm, (0, LIP_Y - 0.2, (CEIL + STAGE_CEIL) / 2), (2 * HX, 0.4, STAGE_CEIL - CEIL))      # proscenium header
new_obj("Header", bm, [CONCRETE])

bm, bg = bmesh.new(), bmesh.new()                                                # columns, ribs, wall pipes; LED lines
COL_Y = (-30.0, -24.0, -18.0, -12.0, -6.0, -3.0)
for sx in (-1, 1):
    for cy in COL_Y:
        if sx < 0 and cy > AIR_Y0 - 1.0:
            continue
        top = CEIL if cy < LIP_Y else STAGE_CEIL
        kit.box(bm, (sx * (HX - 0.3), cy, (FLOOR + top) / 2), (0.6, 0.6, top - FLOOR))
        setmat(kit.box(bg, (sx * (HX - 0.62), cy, (FLOOR + 0.6 + top - 0.4) / 2), (0.04, 0.08, top - 0.4 - FLOOR - 0.6)), 0)
    for pz in (6.4, 7.1):
        kit.cyl(bm, (sx * (HX - 0.35), Y_BACK + 0.5, pz), (sx * (HX - 0.35), SCREEN_Y - 0.5, pz), 0.22, segs=10)
        for by in range(int(Y_BACK + 2), int(SCREEN_Y - 1), 3):
            setmat(kit.cyl(bg, (sx * (HX - 0.35), by, pz), (sx * (HX - 0.35), by + 0.15, pz), 0.235, segs=10), 1)
for cy in COL_Y[1:-1]:
    kit.box(bm, (0, cy, CEIL - 0.25), (2 * HX, 0.4, 0.5))
    setmat(kit.box(bg, (0, cy, CEIL - 0.52), (2 * HX - 1.2, 0.06, 0.04)), 0)
new_obj("Structure", bm, [STEEL])
new_obj("ArchLines", bg, [GLOW["blue_dim"], GLOW["blue"]])
bm = bmesh.new()
kit.box(bm, (0, BARRIER_Y - 0.4, FLOOR + 0.005), (16, 0.5, 0.01))                       # hazard band before the barrier
kit.box(bm, ((AIR_X0 + AIR_X1) / 2, AIR_Y0 - 0.95, FLOOR + 0.005), (4, 1.6, 0.01))    # hazard plate at the airlock
new_obj("FloorHazard", bm, [HAZARD])
log("hall shell")

# ------------------------------------------------------------------ stage, wings, console, DJ, rod columns
bm = bmesh.new()
setmat(kit.box(bm, (0, (LIP_Y + Y_BAY) / 2, -0.6), (2 * HX, Y_BAY - LIP_Y, 1.2)), 0)      # deck + wings + bay floor
setmat(kit.box(bm, (0, LIP_Y + 0.12, 0.004), (16, 0.2, 0.008)), 1)                       # hazard edge on the lip
setmat(kit.box(bm, (-0.05, 0.225, 0.37), (1.8, 0.55, 0.74)), 2)                          # console = Dino TABLE dims
for dx in (-0.55, 0.45):
    setmat(kit.box(bm, (dx, 0.2, 0.78), (0.42, 0.34, 0.08)), 2)                          # decks
setmat(kit.box(bm, (-0.05, 0.2, 0.78), (0.3, 0.3, 0.08)), 2)                             # mixer
for x in (8.2, 9.4, 10.6, 11.8):                                                         # right wing front rail
    setmat(kit.cyl(bm, (x, LIP_Y + 0.05, 0), (x, LIP_Y + 0.05, 1.1), 0.04, segs=5), 2)
setmat(kit.cyl(bm, (8.0, LIP_Y + 0.05, 1.1), (12.0, LIP_Y + 0.05, 1.1), 0.04, segs=5), 2)
setmat(kit.box(bm, (HX - 0.05, 4.0, 1.2), (0.1, 1.4, 2.4)), 3)                          # backstage door
for sx in (-1, 1):                                                                       # rod-column caps
    setmat(kit.cyl(bm, (sx * 3.0, 0.6, 0), (sx * 3.0, 0.6, 0.15), 0.28, segs=12), 2)
    setmat(kit.cyl(bm, (sx * 3.0, 0.6, 3.6), (sx * 3.0, 0.6, 3.75), 0.28, segs=12), 2)
new_obj("Stage", bm, [DECK, HAZARD, STEEL, GLOW["black"]])

bm = bmesh.new()
setmat(kit.box(bm, (0, LIP_Y - 0.02, -0.015), (16, 0.04, 0.03)), 0)                     # lip LED strip
for r in range(3):                                                                       # console switch lights
    for c in range(12):
        setmat(kit.box(bm, (-0.85 + c * 0.145, -0.065, 0.22 + r * 0.16), (0.05, 0.02, 0.05)), 1 + (r * 7 + c * 5) % 3)
setmat(kit.box(bm, (-0.05, -0.065, 0.69), (1.76, 0.02, 0.025)), 0)
setmat(kit.box(bm, (HX - 0.12, 4.0, 2.47), (0.04, 1.6, 0.06)), 1)                       # backstage door frame
for y in (3.24, 4.76):
    setmat(kit.box(bm, (HX - 0.12, y, 1.2), (0.04, 0.06, 2.4)), 1)
w = kit.text_width("CONTROL ROOM", 0.05)
setmat(kit.led_text(bm, "CONTROL ROOM", (HX - 0.14, 4.0 + w / 2, 2.62), (0, -1, 0), (0, 0, 1), pixel=0.05, gap=0.012), 1)
new_obj("StageGlow", bm, [GLOW["blue"], GLOW["amber"], GLOW["red"], GLOW["green"]])

bm, bg = bmesh.new(), bmesh.new()
for sx in (-1, 1):                                                                       # "control rod" light columns
    kit.cyl(bm, (sx * 3.0, 0.6, 0.15), (sx * 3.0, 0.6, 3.6), 0.2, segs=12)
    kit.cyl(bg, (sx * 3.0, 0.6, 0.2), (sx * 3.0, 0.6, 2.5), 0.1, segs=8)
new_obj("RodTubes", bm, [GLASS])
new_obj("RodLight", bg, [GLOW["blue"]])
bm = bmesh.new()
kit.cyl(bm, (-0.1, 0.9, 0), (-0.1, 0.9, 1.45), 0.2, segs=8)
kit.sphere(bm, (-0.1, 0.9, 1.62), 0.13, segs=8, rings=5)
new_obj("DJ", bm, [DJ_M])
log("stage, console, DJ")

# ------------------------------------------------------------------ screens: main (the core window) and the two side screens
bm = bmesh.new()
kit.quad(bm, (SCREEN_HW, SCREEN_Y, SCREEN_Z0), (-SCREEN_HW, SCREEN_Y, SCREEN_Z0),
         (-SCREEN_HW, SCREEN_Y, SCREEN_Z1), (SCREEN_HW, SCREEN_Y, SCREEN_Z1))
new_obj("VisualScreen", bm, [VISUALS])
bm = bmesh.new()
fw = 0.6                                                                                 # hazard-striped window frame
kit.box(bm, (0, SCREEN_Y + 0.1, SCREEN_Z1 + fw / 2), (2 * SCREEN_HW + 2 * fw, 0.3, fw))
kit.box(bm, (0, SCREEN_Y + 0.1, SCREEN_Z0 / 2), (2 * SCREEN_HW + 2 * fw, 0.3, SCREEN_Z0))
for sx in (-1, 1):
    kit.box(bm, (sx * (SCREEN_HW + fw / 2), SCREEN_Y + 0.1, (SCREEN_Z1 + fw) / 2), (fw, 0.3, SCREEN_Z1 + fw))
new_obj("ScreenFrame", bm, [HAZARD])
bm, bf = bmesh.new(), bmesh.new()
for sx in (-1, 1):                                                                       # 16:9, 6 x 3.375 m, angled at the floor
    c = Vector((sx * 9.6, 0.6, 3.7))
    n = Vector((0.0, -12.0, 0.0)) - Vector((c.x, c.y, 0.0))
    n.normalize()
    t = Vector((-n.y, n.x, 0.0))
    up = Vector((0, 0, 1.6875))
    kit.quad(bm, c - t * 3.0 - up, c + t * 3.0 - up, c + t * 3.0 + up, c - t * 3.0 + up)
    kit.box(bf, c - n * 0.12, (6.3, 0.15, 3.6), yaw=math.atan2(t.y, t.x))
new_obj("SideScreens", bm, [VISUALS])
new_obj("SideScreenFrames", bf, [STEEL])
log("screens")

# ------------------------------------------------------------------ the core bay: vessel, rod drives, pipes
bm, bg = bmesh.new(), bmesh.new()
kit.cyl(bm, (VESSEL.x, VESSEL.y, 0), (VESSEL.x, VESSEL.y, VTOP), VR, segs=32)
kit.sphere(bm, (VESSEL.x, VESSEL.y, VTOP), VR, segs=32, rings=12, scale=(1, 1, 0.8))
for z in (1.6, 4.0, 6.4, 8.8):
    setmat(kit.cyl(bg, (VESSEL.x, VESSEL.y, z), (VESSEL.x, VESSEL.y, z + 0.14), VR + 0.05, segs=32), 0)
for dz in (0.8, 1.7, 2.3):
    r = VR * math.sqrt(max(0.0, 1 - (dz / (VR * 0.8)) ** 2))
    setmat(kit.cyl(bg, (VESSEL.x, VESSEL.y, VTOP + dz), (VESSEL.x, VESSEL.y, VTOP + dz + 0.1), r + 0.05, segs=32), 0)
for i in range(9):                                                                       # control-rod drives on the dome
    a = i * 2 * math.pi / 9
    p = (VESSEL.x + 0.7 * math.cos(a), VESSEL.y + 0.7 * math.sin(a))
    kit.cyl(bm, (*p, VTOP + 2.3), (*p, STAGE_CEIL - 0.25), 0.1, segs=6)
for sx in (-1, 1):                                                                       # drive towers with beacons
    kit.box(bm, (sx * 6.6, 10.6, 5.5), (1.3, 1.3, 11.0))
    setmat(kit.cyl(bg, (sx * 6.6, 10.6, 11.0), (sx * 6.6, 10.6, 11.35), 0.16, segs=10), 1)
for z in (2.0, 4.2, 6.4, 8.6, 10.8):                                                     # back-wall pipes, blue bands
    kit.cyl(bm, (-HX + 0.4, Y_BAY - 0.5, z), (HX - 0.4, Y_BAY - 0.5, z), 0.28, segs=10)
    for x in range(-10, 11, 4):
        setmat(kit.cyl(bg, (x, Y_BAY - 0.5, z), (x + 0.15, Y_BAY - 0.5, z), 0.3, segs=10), 0)
new_obj("Core", bm, [STEEL])
bm = bmesh.new()
kit.sphere(bm, (VESSEL.x, VESSEL.y, VTOP), VR + 0.5, segs=32, rings=12, scale=(1, 1, 0.85))
new_obj("CoreAura", bm, [M_glow_alpha("core_aura", (0.2, 0.55, 1.0), 2.0, 0.10)])
new_obj("CoreGlow", bg, [GLOW["core"], GLOW["red"]])
log("core bay")

# ------------------------------------------------------------------ crowd barrier and the airlock (the stage gate)
bm = bmesh.new()
for i in range(9):
    setmat(kit.box(bm, (-8 + i * 2, BARRIER_Y, FLOOR + 0.55), (0.08, 0.5, 1.1)), 0)
setmat(kit.box(bm, (0, BARRIER_Y, FLOOR + 1.08), (16, 0.08, 0.06)), 0)
setmat(kit.box(bm, (0, BARRIER_Y, FLOOR + 0.6), (16, 0.03, 0.9)), 0)
setmat(kit.box(bm, (0, BARRIER_Y - 0.05, FLOOR + 1.12), (16, 0.02, 0.02)), 1)
new_obj("Barrier", bm, [STEEL, GLOW["amber_dim"]])

bm = bmesh.new()
for i in range(7):                                                                       # 7 x 17 cm up to the wing
    y0, top = -5.1 + 0.3 * i, FLOOR + (0.0 - FLOOR) * (i + 1) / 7
    setmat(kit.box(bm, (-10.0, (y0 + LIP_Y) / 2, (FLOOR + top) / 2), (3.2, LIP_Y - y0, top - FLOOR)), 0)
setmat(kit.box(bm, ((AIR_X0 + DOOR_X0) / 2, AIR_Y0, (FLOOR + LINTEL_TOP) / 2), (DOOR_X0 - AIR_X0, 0.3, LINTEL_TOP - FLOOR)), 1)
setmat(kit.box(bm, ((DOOR_X1 + AIR_X1) / 2, AIR_Y0, (FLOOR + LINTEL_TOP) / 2), (AIR_X1 - DOOR_X1, 0.3, LINTEL_TOP - FLOOR)), 1)
setmat(kit.box(bm, ((AIR_X0 + AIR_X1) / 2, AIR_Y0, (DOOR_TOP + LINTEL_TOP) / 2), (AIR_X1 - AIR_X0, 0.3, LINTEL_TOP - DOOR_TOP)), 0)
setmat(kit.box(bm, ((AIR_X0 + AIR_X1) / 2, (AIR_Y0 + AIR_Y1) / 2, LINTEL_TOP + 0.05), (AIR_X1 - AIR_X0, AIR_Y1 - AIR_Y0, 0.1)), 0)
setmat(kit.box(bm, (AIR_X1, (AIR_Y0 + AIR_Y1) / 2, LINTEL_TOP / 2 + FLOOR / 2), (0.1, 0.1, LINTEL_TOP - FLOOR)), 0)
new_obj("Airlock", bm, [STEEL, HAZARD])
bm = bmesh.new()
kit.box(bm, (AIR_X1, (AIR_Y0 + AIR_Y1) / 2, (FLOOR + LINTEL_TOP) / 2), (0.05, AIR_Y1 - AIR_Y0, LINTEL_TOP - FLOOR))
new_obj("AirlockGlass", bm, [GLASS])
bm = bmesh.new()                                                                         # frame glow (open/closed agnostic)
setmat(kit.box(bm, (DOOR_X0 - 0.02, AIR_Y0 - 0.16, (FLOOR + DOOR_TOP) / 2), (0.04, 0.02, DOOR_TOP - FLOOR)), 0)
setmat(kit.box(bm, (DOOR_X1 + 0.02, AIR_Y0 - 0.16, (FLOOR + DOOR_TOP) / 2), (0.04, 0.02, DOOR_TOP - FLOOR)), 0)
setmat(kit.box(bm, (DOOR_MID, AIR_Y0 - 0.16, DOOR_TOP + 0.02), (DOOR_X1 - DOOR_X0 + 0.08, 0.02, 0.04)), 0)
new_obj("AirlockFrameGlow", bm, [GLOW["amber_dim"]])


def door(name, open_):
    bm = bmesh.new()
    half = (DOOR_X1 - DOOR_X0) / 2
    for a, s in ((DOOR_X0, -1), (DOOR_MID, 1)):
        cx = a + half / 2 + (s * (half - 0.15) if open_ else 0.0)
        setmat(kit.box(bm, (cx, AIR_Y0 - 0.21, (FLOOR + DOOR_TOP) / 2), (half - 0.02, 0.1, DOOR_TOP - FLOOR)), 0)
        setmat(kit.box(bm, (cx, AIR_Y0 - 0.265, 0.1), (half - 0.02, 0.01, 0.35)), 1)
    return new_obj(name, bm, [STEEL, HAZARD])


door("DoorClosed", False)
door("DoorOpen", True)
for name, key, glow in (("Red", "beacon_red", RED), ("Green", "beacon_green", GREEN)):
    bm = bmesh.new()
    kit.cyl(bm, (DOOR_MID, AIR_Y0, LINTEL_TOP + 0.1), (DOOR_MID, AIR_Y0, LINTEL_TOP + 0.45), 0.14, segs=12)
    new_obj("Beacon" + name, bm, [GLOW[key]])
    bm = bmesh.new()
    kit.sphere(bm, (DOOR_MID, AIR_Y0, LINTEL_TOP + 0.28), 0.6, segs=12, rings=8)
    new_obj("Beacon" + name + "Halo", bm, [M_glow_alpha("halo_" + name, glow, 1.5, 0.12)])
for name, line2, key2 in (("SignDeny", "DJS ONLY", 1), ("SignOk", "ACCESS GRANTED", 2)):
    bm = bmesh.new()
    xc = (AIR_X0 + AIR_X1) / 2
    setmat(text_centered(bm, "CONTAINMENT", xc, AIR_Y0 - 0.17, 1.98, (1, 0, 0), 0.045, 0.01), 0)
    p2 = 0.06 if key2 == 1 else 0.045
    setmat(text_centered(bm, line2, xc, AIR_Y0 - 0.17, 1.5, (1, 0, 0), p2, 0.012), key2)
    new_obj(name, bm, [GLOW["amber"], GLOW["red"], GLOW["green"]])
log("barrier, airlock")

# ------------------------------------------------------------------ mezzanines, lounge, bar, entrance
bm, bg, bs = bmesh.new(), bmesh.new(), bmesh.new()
for sx in (-1, 1):
    kit.box(bm, (sx * (MZ_X0 + MZ_X1) / 2, (MZ_Y0 + MZ_Y1) / 2, MZ_Z - 0.15), (MZ_X1 - MZ_X0, MZ_Y1 - MZ_Y0, 0.3))
    xi = sx * (MZ_X0 + 0.08)
    n = 10
    for k in range(n + 1):
        y = MZ_Y0 + k * (MZ_Y1 - MZ_Y0) / n
        kit.cyl(bm, (xi, y, MZ_Z), (xi, y, MZ_Z + 1.1), 0.04, segs=5)
    kit.cyl(bm, (xi, MZ_Y0, MZ_Z + 1.1), (xi, MZ_Y1, MZ_Z + 1.1), 0.05, segs=6)
    kit.cyl(bm, (xi, MZ_Y0, MZ_Z + 0.55), (xi, MZ_Y1, MZ_Z + 0.55), 0.03, segs=5)
    kit.cyl(bm, (sx * MZ_X0, MZ_Y1 - 0.08, MZ_Z + 1.1), (sx * MZ_X1, MZ_Y1 - 0.08, MZ_Z + 1.1), 0.05, segs=6)
    for x in (MZ_X0 + 1.3, MZ_X0 + 2.6):
        kit.cyl(bm, (sx * x, MZ_Y1 - 0.08, MZ_Z), (sx * x, MZ_Y1 - 0.08, MZ_Z + 1.1), 0.04, segs=5)
    for y in (-23.5, -19.5, -15.5, -11.5, -8.5):
        kit.box(bm, (sx * (MZ_X0 + 0.3), y, (FLOOR + MZ_Z - 0.3) / 2), (0.3, 0.3, MZ_Z - 0.3 - FLOOR))
    setmat(kit.box(bg, (sx * (MZ_X0 - 0.01), (MZ_Y0 + MZ_Y1) / 2, MZ_Z - 0.08), (0.03, MZ_Y1 - MZ_Y0, 0.06)), 0)
    setmat(kit.box(bg, (sx * (MZ_X0 - 0.01), (MZ_Y0 + MZ_Y1) / 2, MZ_Z - 0.24), (0.03, MZ_Y1 - MZ_Y0, 0.04)), 1)
    for i in range(20):                                                                  # stairs along the wall
        y0, top = -30.0 + 0.3 * i, FLOOR + 0.175 * (i + 1)
        kit.box(bm, (sx * 11.25, (y0 + MZ_Y0) / 2, (FLOOR + top) / 2), (1.3, MZ_Y0 - y0, top - FLOOR))
    kit.cyl(bm, (sx * 10.55, -30.0, FLOOR + 1.0), (sx * 10.55, MZ_Y0, MZ_Z + 1.0), 0.04, segs=5)
    kit.cyl(bm, (sx * 8.4, MZ_Y1 - 0.2, MZ_Z), (sx * 8.4, MZ_Y1 - 0.2, 4.8), 0.06, segs=6)   # side-laser pole
    for y in (-21.0, -15.0, -9.8):                                                       # lounge under the deck
        setmat(kit.box(bs, (sx * 11.35, y, FLOOR + 0.22), (0.9, 2.6, 0.45)), 0)
        setmat(kit.box(bs, (sx * 11.75, y, FLOOR + 0.6), (0.25, 2.6, 0.9)), 0)
        setmat(kit.box(bs, (sx * 10.3, y, FLOOR + 0.22), (0.7, 1.0, 0.45)), 1)
        setmat(kit.sphere(bg, (sx * 10.3, y, FLOOR + 0.55), 0.1, segs=6, rings=4), 1)
new_obj("Mezzanines", bm, [STEEL])
new_obj("Lounge", bs, [SOFA, STEEL])
new_obj("MezzGlow", bg, [GLOW["blue"], GLOW["amber_dim"]])

bm, bg = bmesh.new(), bmesh.new()
xc = (BAR_X0 + BAR_X1) / 2
kit.box(bm, (xc, BAR_Y, FLOOR + 0.55), (BAR_X1 - BAR_X0, 0.8, 1.1))
kit.box(bm, (xc, BAR_Y, FLOOR + 1.12), (BAR_X1 - BAR_X0 + 0.2, 1.0, 0.05))
for k in range(34):                                                                      # coolant tubes on the front
    x = BAR_X0 + 0.15 + k * (BAR_X1 - BAR_X0 - 0.3) / 33
    setmat(kit.cyl(bg, (x, BAR_Y - 0.43, FLOOR + 0.1), (x, BAR_Y - 0.43, FLOOR + 1.0), 0.055, segs=6), k % 2)
for z in (FLOOR + 1.3, FLOOR + 1.9, FLOOR + 2.5):                                        # back bar and bottles
    kit.box(bm, (xc, Y_BACK + 0.25, z), (BAR_X1 - BAR_X0, 0.4, 0.05))
    x = BAR_X0 + 0.2
    while x < BAR_X1 - 0.2:
        setmat(kit.box(bg, (x, Y_BACK + 0.25, z + 0.17), (0.08, 0.08, 0.3)), 2 + rng.randrange(4))
        x += 0.24 + rng.uniform(0, 0.08)
for k in range(12):
    x = BAR_X0 + 0.5 + k * (BAR_X1 - BAR_X0 - 1.0) / 11
    kit.cyl(bm, (x, BAR_Y - 0.95, FLOOR), (x, BAR_Y - 0.95, FLOOR + 0.75), 0.18, segs=8)
bt = bmesh.new()
setmat(text_centered(bt, "COOLANT BAR", xc, Y_BACK + 0.06, FLOOR + 3.2, (-1, 0, 0), 0.07, 0.015), 0)
setmat(text_centered(bt, "REACTOR", xc, Y_BACK + 0.06, FLOOR + 4.0, (-1, 0, 0), 0.15, 0.03), 1)
new_obj("BarSigns", bt, [GLOW["blue"], GLOW["amber"]])
new_obj("Bar", bm, [STEEL])
new_obj("BarGlow", bg, [GLOW["blue"], GLOW["blue_dim"], GLOW["bottle_amber"], GLOW["bottle_blue"],
                        GLOW["bottle_green"], GLOW["bottle_white"], GLOW["amber"]])

bm, bg = bmesh.new(), bmesh.new()                                                        # decontamination corridor
EZ = FLOOR + 3.0
setmat(kit.box(bm, ((EX0 + EX1) / 2, Y_BACK - 2.5, FLOOR - 0.1), (EX1 - EX0 + 0.8, 5.0, 0.2)), 0)
for x in (EX0 - 0.2, EX1 + 0.2):
    setmat(kit.box(bm, (x, Y_BACK - 2.5, (FLOOR + EZ) / 2), (0.4, 5.0, EZ - FLOOR)), 0)
    setmat(kit.box(bg, (x + (0.25 if x < EX0 else -0.25), Y_BACK - 2.5, EZ - 0.3), (0.04, 4.6, 0.05)), 0)
    setmat(kit.box(bg, (x + (0.25 if x < EX0 else -0.25), Y_BACK - 2.5, FLOOR + 0.15), (0.04, 4.6, 0.04)), 0)
setmat(kit.box(bm, ((EX0 + EX1) / 2, Y_BACK - 2.5, EZ + 0.1), (EX1 - EX0 + 0.8, 5.0, 0.2)), 0)
setmat(kit.box(bm, ((EX0 + EX1) / 2, Y_BACK - 5.1, (FLOOR + EZ) / 2), (EX1 - EX0, 0.2, EZ - FLOOR)), 1)
setmat(kit.box(bg, ((EX0 + EX1) / 2, Y_BACK + 0.02, EZ + 0.05), (EX1 - EX0, 0.04, 0.06)), 1)
new_obj("Entrance", bm, [CONCRETE_DARK, FAR])
new_obj("EntranceGlow", bg, [GLOW["uv"], GLOW["amber"]])
log("mezzanines, lounge, bar, entrance")

# ------------------------------------------------------------------ rig: trusses, pixel strips and tiles, heads, beams, lasers
bm, bg = bmesh.new(), bmesh.new()
for i, ty in enumerate(TRUSS_Y):
    kit.truss(bm, (-HX + 0.6, ty, TRUSS_Z), (HX - 0.6, ty, TRUSS_Z), size=0.5, step=1.0)
    setmat(kit.box(bg, (0, ty, TRUSS_Z - 0.28), (2 * HX - 1.4, 0.06, 0.05)), i % 2)
    for x in (-HX + 1.5, HX - 1.5):
        kit.cyl(bm, (x, ty, TRUSS_Z + 0.25), (x, ty, CEIL), 0.02, segs=4)
kit.truss(bm, (-9.5, -1.5, 8.8), (9.5, -1.5, 8.8), size=0.5, step=1.0)                 # front-of-stage: laser bar
setmat(kit.box(bg, (0, -1.5, 8.52), (18.8, 0.06, 0.05)), 0)
kit.truss(bm, (-9.0, 3.0, 10.6), (9.0, 3.0, 10.6), size=0.5, step=1.0)                  # core-bay truss
setmat(kit.box(bg, (0, 3.0, 10.32), (17.8, 0.06, 0.05)), 1)
new_obj("Trusses", bm, [STEEL])
new_obj("PixelStrips", bg, [GLOW["blue"], GLOW["amber"]])
bm = bmesh.new()                       # the name plate on the core window's top bar: a sign on the proscenium header sits
kit.box(bm, (0, SCREEN_Y - 0.04, 9.8), (3.8, 0.04, 0.6))   # above the hall ceiling's sight line, one under the front truss
new_obj("StageSignBoard", bm, [STEEL])                      # would hide the dome
bm = bmesh.new()
setmat(text_centered(bm, "REACTOR", 0.0, SCREEN_Y - 0.07, 9.52, (1, 0, 0), 0.08, 0.016), 0)
new_obj("StageSign", bm, [GLOW["amber"]])

bm = bmesh.new()                                                                         # stage-front pixel fascia (a chase frame)
cols, rows = 40, 3
for c in range(cols):
    for r in range(rows):
        v = 0.5 + 0.5 * math.sin(c * 0.45 + r * 0.9)
        k = 0 if v > 0.75 else (1 if v > 0.45 else (2 if v > 0.2 else 3))
        z = FLOOR + 0.06 + (r + 0.5) * 1.0 / rows
        setmat(kit.box(bm, (-8 + (c + 0.5) * 16 / cols, LIP_Y - 0.03, z), (16 / cols - 0.05, 0.02, 1.0 / rows - 0.05)), k)
new_obj("PixelTiles", bm, [GLOW["blue"], GLOW["amber"], GLOW["blue_dim"], GLOW["black"]])

heads = []                                                                               # (pos, target, color)
for i, ty in enumerate(TRUSS_Y):
    for k, hx in enumerate((-10.0, -6.0, -2.0, 2.0, 6.0, 10.0)):
        col = ("amber", "blue", "white")[(i + k) % 3]
        heads.append(((hx, ty, TRUSS_Z - 0.55), (hx * 1.35 + rng.uniform(-1, 1), ty + (3 if k % 2 else -3), FLOOR), col))
for k in range(8):
    hx = -8.4 + k * 2.4
    heads.append(((hx, 3.0, 10.05), (hx * 1.5, -20 - 4 * (k % 3), FLOOR + 1.5), ("blue", "amber")[k % 2]))
for hx in (-7.5, -5.5, -3.5, 3.5, 5.5, 7.5):                                         # floor heads: up and out, under the
    heads.append(((hx, 4.4, 0.3), (hx * 1.2, -14, CEIL), "white" if abs(hx) > 6 else "blue"))   # side screens' bottom edge
BEAM = {c: M_glow_alpha("beam_" + c, {"amber": AMBER, "blue": BLUE, "white": WHITE}[c], 0.8, 0.018)
        for c in ("amber", "blue", "white")}
BEAM_KEYS = list(BEAM)
bm, bb, bl = bmesh.new(), bmesh.new(), bmesh.new()
for p, tgt, col in heads:
    p = Vector(p)
    d = (Vector(tgt) - p).normalized()
    kit.box(bm, p, (0.4, 0.4, 0.5))
    setmat(kit.sphere(bl, p + d * 0.3, 0.12, segs=8, rings=5), BEAM_KEYS.index(col))
    L = beam_len(p + d * 0.3, d)
    setmat(kit.cyl(bb, p + d * 0.3, p + d * L, 0.08, segs=10, cap=False, r2=0.08 + 0.035 * L), BEAM_KEYS.index(col))
new_obj("Heads", bm, [STEEL])
new_obj("Lenses", bl, [GLOW["amber"], GLOW["blue"], GLOW["white"]])
new_obj("Beams", bb, [BEAM[c] for c in BEAM_KEYS])

lasers = []                                                                              # (origin, direction, key)
for i, x in enumerate((-7.5, -4.5, -1.5, 1.5, 4.5, 7.5)):                                # laser bar: flat fans over the floor
    o = Vector((x, -1.5, 8.35))
    for j in range(7):
        tgt = Vector((x * 0.4 - 9 + 3 * j, Y_BACK, 4.3 + 0.2 * (i % 3)))             # >= MZ_Z + 2.4 over the mezzanines
        lasers.append((o, (tgt - o).normalized(), "laser_green" if i % 2 == 0 else "laser_blue"))
for sx in (-1, 1):                                                                       # side crossfire above the heads
    o = Vector((sx * 8.4, MZ_Y1 - 0.2, 4.8))
    for j in range(3):
        lasers.append((o, (Vector((-sx * HX, -11 - 6 * j, 6.0)) - o).normalized(), "laser_blue"))
for sx in (-1, 1):                                                                       # back wall: up onto the ceiling
    o = Vector((sx * 4.0, Y_BACK + 0.3, 7.2))
    for j in range(4):
        lasers.append((o, (Vector((sx * (1.5 + 2.6 * j), -6.0, CEIL)) - o).normalized(), "laser_green"))
bm, bs = bmesh.new(), bmesh.new()
for o, d, key in lasers:
    L = beam_len(o, d, step=0.05)
    k = 0 if key == "laser_green" else 1
    setmat(kit.cyl(bm, o, o + d * L, 0.03, segs=5, cap=False), k)
    setmat(kit.sphere(bs, o + d * (L - 0.02), 0.09, segs=6, rings=4), k)                # the spot where it lands
new_obj("Lasers", bm, [GLOW["laser_green"], GLOW["laser_blue"]])
new_obj("LaserSpots", bs, [GLOW["laser_green"], GLOW["laser_blue"]])
log(f"rig: {len(heads)} heads, {len(lasers)} laser lines")

# ------------------------------------------------------------------ haze
bm = bmesh.new()
kit.box(bm, (0, (MZ_Y0 + BARRIER_Y) / 2, FLOOR + 3.2), (15.8, BARRIER_Y - MZ_Y0 - 0.4, 0.02))
new_obj("HazeLo", bm, [M_fog("hazeLo", (0.05, 0.065, 0.09), 0.16, 0.12)])
bm = bmesh.new()
kit.box(bm, (0, (Y_BACK + LIP_Y) / 2, FLOOR + 6.0), (2 * HX - 0.4, LIP_Y - Y_BACK - 0.4, 0.02))
new_obj("HazeHi", bm, [M_fog("hazeHi", (0.05, 0.065, 0.09), 0.12, 0.08)])
bm = bmesh.new()
kit.box(bm, (0, (LIP_Y + SCREEN_Y) / 2, 6.5), (2 * HX - 0.4, SCREEN_Y - LIP_Y - 0.3, 0.02))
new_obj("HazeStage", bm, [M_fog("hazeStage", (0.05, 0.075, 0.12), 0.15, 0.1)])

# ------------------------------------------------------------------ crowd (simple people, club clothes and glow)
BODY = [M_flat("c_black", (0.015, 0.015, 0.018)), M_flat("c_navy", (0.02, 0.03, 0.06)), M_flat("c_grey", (0.12, 0.12, 0.13)),
        M_flat("c_olive", (0.05, 0.06, 0.03)), M_flat("c_white", (0.4, 0.4, 0.42)), M_flat("c_amber", (0.35, 0.15, 0.02))]
HEAD = [M_flat("h_skin1", (0.5, 0.33, 0.24)), M_flat("h_skin2", (0.3, 0.18, 0.11)), M_flat("h_skin3", (0.15, 0.09, 0.06))]
STICK = [GLOW["blue"], GLOW["amber"], GLOW["green"], GLOW["white"]]
NB, NH, NS = len(BODY), len(HEAD), len(STICK)
body_w = [40, 18, 12, 8, 6, 4]


def person(dst, x, y, z0, rng, face=(0.0, 1.0)):
    bm = bmesh.new()
    h = rng.uniform(1.55, 1.9)
    b = rng.choices(range(NB), body_w)[0]
    setmat(kit.cyl(bm, (x, y, z0), (x, y, z0 + h - 0.3), 0.21, segs=6), b)
    setmat(kit.sphere(bm, (x, y, z0 + h - 0.12), 0.13, segs=6, rings=4), NB + rng.randrange(NH))
    r = rng.random()
    if r < 0.4:                                                                          # an arm up, maybe a glowstick
        ax = x + rng.choice((-0.28, 0.28))
        setmat(kit.cyl(bm, (ax, y, z0 + h - 0.45), (ax, y, z0 + h + 0.35), 0.045, segs=5), b)
        if rng.random() < 0.6:
            setmat(kit.cyl(bm, (ax, y, z0 + h + 0.3), (ax, y, z0 + h + 0.62), 0.03, segs=5), NB + NH + rng.randrange(NS))
    elif r < 0.5:                                                                        # a phone at the chest
        setmat(kit.box(bm, (x + 0.26 * face[0], y + 0.26 * face[1], z0 + h - 0.55), (0.1, 0.02, 0.16)), NB + NH + 3)
    bm_merge(dst, bm)


CAM_CLEAR = ((1.5, -20.5), (-8.8, -11.0))


def clear_of_cams(x, y):
    return all((x - cx) ** 2 + (y - cy) ** 2 > 1.2 ** 2 for cx, cy in CAM_CLEAR)


bm, n_people = bmesh.new(), 0
y = BARRIER_Y - 0.7
while y > -18.0:                                                                         # dance floor, thinner toward the back
    s = 1.15 + 0.02 * (-y - 4)
    x = -7.4 + rng.uniform(0, 0.4)
    while x < 7.4:
        if rng.random() < (0.93 if y > -12 else 0.7) and clear_of_cams(x, y):
            person(bm, x + rng.uniform(-0.2, 0.2), y + rng.uniform(-0.2, 0.2), FLOOR, rng)
            n_people += 1
        x += s
    y -= s
for sx in (-1, 1):                                                                       # along the mezzanine rails
    yy = MZ_Y1 - 0.8
    while yy > MZ_Y0 + 0.6:
        if rng.random() < 0.75:
            person(bm, sx * (MZ_X0 + 0.6 + rng.uniform(0, 0.5)), yy, MZ_Z, rng, face=(-sx * 0.5, 0.86))
            n_people += 1
        yy -= rng.uniform(0.9, 1.4)
for k in range(12):                                                                      # at the bar, facing it
    if rng.random() < 0.8:
        person(bm, BAR_X0 + 0.4 + k * 0.85 + rng.uniform(-0.1, 0.1), BAR_Y - 1.0 + rng.uniform(-0.15, 0.15), FLOOR, rng,
               face=(0.0, -1.0))
        n_people += 1
for k in range(10):                                                                      # back floor
    x, y = rng.uniform(-7, 7), rng.uniform(-24, -19)
    if clear_of_cams(x, y):
        person(bm, x, y, FLOOR, rng)
        n_people += 1
new_obj("Crowd", bm, BODY + HEAD + STICK)
log(f"crowd: {n_people} people")

# ------------------------------------------------------------------ lights (the show, mid-drop)
for i, ty in enumerate(TRUSS_Y):
    for sx in (-1, 1):
        spot(f"wash_{i}_{sx}", (sx * 5, ty, TRUSS_Z - 0.6), (sx * 3, ty - 2, FLOOR), BLUE if (i + (sx > 0)) % 2 else AMBER, 1200, 60)
spot("stage_wash_L", (-6, -1.5, 8.3), (-2, 2.5, 0), BLUE, 800, 50)
spot("stage_wash_R", (6, -1.5, 8.3), (2, 2.5, 0), AMBER, 700, 50)
point("core", (0, 6.6, 10.8), (0.3, 0.6, 1.0), 6000, 1.5)
point("bay_low", (0, 6.0, 3.0), (0.2, 0.5, 1.0), 1500, 1.0)
point("bar", (xc, Y_BACK + 1.5, 2.2), AMBER, 400, 0.6)
point("bar2", (xc, BAR_Y + 1.5, 2.6), AMBER, 250, 0.6)
for sx in (-1, 1):
    for y in (-21.0, -15.0, -9.8):
        point(f"lounge_{sx}_{y}", (sx * 10.3, y, FLOOR + 0.9), AMBER, 25, 0.2)
point("beacon_red", (DOOR_MID, AIR_Y0 - 0.7, LINTEL_TOP + 0.3), RED, 250, 0.3)
point("beacon_green", (DOOR_MID, AIR_Y0 - 0.7, LINTEL_TOP + 0.3), GREEN, 220, 0.3)
spot("deck_L", (-0.45, 0.4, 1.5), (-0.5, 0.2, 0.78), (1.0, 0.75, 0.5), 60, 38)
spot("deck_R", (0.35, 0.4, 1.5), (0.4, 0.2, 0.78), (1.0, 0.75, 0.5), 60, 20)
spot("follow", (0, Y_BACK + 1.0, 7.5), (-0.1, 0.9, 1.4), (1.0, 0.92, 0.85), 3000, 4, 0.3)
amb = bpy.data.lights.new("ambient", "SUN")
amb.energy, amb.color = 0.02, (0.45, 0.55, 0.9)
aob = bpy.data.objects.new("ambient", amb)
aob.rotation_euler = (Vector((0.3, 1.0, -1.0))).to_track_quat("-Z", "Y").to_euler()
scene.collection.objects.link(aob)
log(f"scene built: {sum(len(o.data.polygons) for o in scene.objects if o.type == 'MESH')} faces")

# ------------------------------------------------------------------ cameras, per-view visibility, renders
CAMS = {
    "stream": ((0, -9.5, 2.2), (0, 4, 5.2), 16),
    "crowd": ((1.5, -20.5, 0.75), (0, 3, 4.0), 18),
    "dj_view": ((-0.1, 0.9, 1.68), (0, -24, 0.0), 16),
    "gate": ((-8.8, -11.0, 0.55), (DOOR_MID, AIR_Y0, 0.9), 18),
    "gate_open": ((-8.8, -11.0, 0.55), (DOOR_MID, AIR_Y0, 0.9), 18),
    "aerial": ((-23, -40, 21), (0, -9, -1), 22),
    "bar": ((3.5, -26.2, 0.9), (0, 3, 3.6), 16),
}
GATE_CLOSED = {"DoorClosed", "BeaconRed", "BeaconRedHalo", "SignDeny", "beacon_red"}
GATE_OPEN = {"DoorOpen", "BeaconGreen", "BeaconGreenHalo", "SignOk", "beacon_green"}
CUTAWAY = {"Ceiling", "StageCeiling", "WallL", "WallBack", "HazeLo", "HazeHi", "HazeStage", "BarSigns"}


def hidden_for(view):
    hide = set(GATE_CLOSED if view == "gate_open" else GATE_OPEN)
    if view == "aerial":
        hide |= CUTAWAY
    if view == "dj_view":
        hide.add("DJ")
    return hide


cam = bpy.data.cameras.new("cam")
cam.clip_end = 3000
cob = bpy.data.objects.new("cam", cam)
scene.collection.objects.link(cob)
scene.camera = cob
for name in VIEWS:
    hide = hidden_for(name)
    for ob in scene.objects:
        ob.hide_render = ob.name in hide
    pos, tgt, lens = CAMS[name]
    cam.lens = lens
    cob.location = pos
    cob.rotation_euler = (Vector(tgt) - Vector(pos)).to_track_quat("-Z", "Y").to_euler()
    scene.render.filepath = os.path.join(OUT, f"club_concept_{name}.jpg")
    t = time.time()
    bpy.ops.render.render(write_still=True)
    log(f"rendered {name} in {time.time() - t:.1f}s -> {scene.render.filepath}")
log("done")
