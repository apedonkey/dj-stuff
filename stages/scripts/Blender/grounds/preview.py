"""Preview one festival-grounds module in context (Blender 4.5, headless, Cycles on the GPU, no baking).

  D:\\Tools\\blender-4.5.14-windows-x64\\blender.exe -b --factory-startup --python grounds/preview.py -- <module>
        [--views dj,dj_left,dj_right,overview,back,side_left,side_right,drone_crowd] [--no-context]
        [--samples 32] [--res 1280x720]

- Context = the current Dino Stage exactly as the Quest shows it: ../out/SM_Dino*.fbx with their baked textures, unlit.
  (Run from anywhere; paths are relative to this file.)
- The module's parts render as they will ship: "lit" parts lit by the module's own lights (+ light from the stage's
  emissive surfaces), "glow" parts unlit with the palette, "beams"/"halos" alpha-blended. The ground near the module
  shows the stage's baked light plus the module's light pools.
- Final-look simulation (default; --raw turns it off), by the infra agent: the stage's own bake lights are added,
  the stage's emitters and the grounds palette light their surroundings at their bake strengths (the camera still sees
  them at 1), and lit albedo is scaled by the bake exposure (x1.8, the linear part of 1-exp(-1.8x)). Without it, lit
  parts render far darker than they ship.
- Writes grounds/out/preview_<module>_<view>.png and prints [GROUNDS] stats (tris per part, lights, bounds).
"""
import importlib
import math
import os
import random
import sys
import time

import bmesh
import bpy
from mathutils import Matrix, Vector

HERE = os.path.dirname(os.path.abspath(__file__))
STAGE_OUT = os.path.join(os.path.dirname(HERE), "out")
OUT = os.path.join(HERE, "out")
os.makedirs(OUT, exist_ok=True)
sys.path.insert(0, HERE)
import kit  # noqa: E402

STAGE_DROP = 1.0
ARGS = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
MODULE = ARGS[0] if ARGS else sys.exit("usage: preview.py -- <module> [options]")


def opt(name, default):
    return ARGS[ARGS.index(name) + 1] if name in ARGS else default


VIEWS = opt("--views", "dj,dj_left,dj_right,back,overview").split(",")
SAMPLES = int(opt("--samples", "32"))
RES = tuple(int(v) for v in opt("--res", "1280x720").split("x"))
CONTEXT = "--no-context" not in ARGS
FINAL = "--raw" not in ARGS
EXPOSURE = 1.8 * 0.5 if FINAL else 1.0           # the bake's 1.8 x dino_stage.NIGHT (0.5, the night pass)
BAKE_EMIT = {"SM_DinoLED": 2.5, "SM_DinoScreen": 4.0, "SM_DinoBulbs": 6.0, "SM_DinoPhones": 4.0, "SM_DinoEyes": 6.0,
             "SM_DinoLenses": 8.0, "SM_DinoBooth": 3.0, "SM_DinoGlow": 6.0, "SM_DinoPillars": 6.0} if FINAL else {}

# camera spots (post-drop world: Tribe's floor z=0 = the DJ riser; crowd field at z=-2.5)
CAMS = {
    "dj": ((0, -0.3, 1.65), (0, -60, -2.5), 16),
    "dj_left": ((0, -0.3, 1.65), (-45, -30, -1.0), 16),
    "dj_right": ((0, -0.3, 1.65), (45, -30, -1.0), 16),
    "overview": ((0, 25, 40), (0, -50, -2.5), 20),
    "back": ((0, -95, 12), (0, 0, 6), 24),
    "side_left": ((-75, -30, 15), (0, -40, -2), 24),
    "side_right": ((75, -30, 15), (0, -40, -2), 24),
    "drone_crowd": ((0, -20, 12), (0, -80, 0), 20),
    # on the stage (stagedeck): the DJ's eyes (dino_stage.py's dj_front/dj_back/stream), turning to the wings or right
    # round at eye level (dj_turn), and a fan in the first row; dj_lookleft looks to the DJ's left (+X), dj_lookright
    # to the DJ's right (-X)
    "dj_front": ((0, 0.9, 1.7), (0, -40, -1.0), 18),
    "dj_back": ((0, -1.0, 1.7), (0, 10, 13), 16),
    "dj_turn": ((0, 1.0, 1.7), (0, 8, -1.2), 18),
    "dj_lookleft": ((0, 0.9, 1.7), (12, -1.5, -0.6), 18),
    "dj_lookright": ((0, 0.9, 1.7), (-12, -1.5, -0.6), 18),
    "stream": ((0, -9, 3.5), (0, 6, 9), 16),
    "front_rows": ((1.5, -8.9, -0.7), (0, 2, 0.8), 22),
}

# stage surfaces (same mapping as Scripts/build_dino.py SURFACES): texture or flat color, shown unlit
STAGE = {
    "SM_DinoStructure": "T_DinoStructure", "SM_DinoDeck": "T_DinoDeck", "SM_DinoGround": "T_DinoGround",
    "SM_DinoCrowd": "T_DinoCrowd", "SM_DinoLED": "T_DinoLED", "SM_DinoScreen": "T_DinoMoon", "SM_DinoSky": "T_DinoSky",
    "SM_DinoBulbs": (1.0, 0.78, 0.45), "SM_DinoPhones": (0.85, 0.9, 1.0), "SM_DinoEyes": (1.0, 0.06, 0.02),
    "SM_DinoFarGround": (0.008, 0.008, 0.011), "SM_DinoRig": "T_DinoRig", "SM_DinoLenses": "T_DinoLens",
    "SM_DinoBooth": "T_DinoBooth", "SM_DinoRiser": "T_DinoRiser", "SM_DinoGlow": (0.2, 0.9, 1.0),
    "SM_DinoPillars": (0.2, 0.9, 1.0), "SM_DinoPlants": "T_DinoPlants", "SM_DinoFlags": "T_DinoFlags",
}


def log(msg):
    print("[GROUNDS] " + msg, flush=True)


bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
coll = scene.collection
scene.render.engine = "CYCLES"
prefs = bpy.context.preferences.addons["cycles"].preferences
for dev_type in ("OPTIX", "CUDA"):
    try:
        prefs.compute_device_type = dev_type
        prefs.get_devices()
        gpus = [d for d in prefs.devices if d.type == dev_type]
        if gpus:
            for d in prefs.devices:
                d.use = d.type == dev_type
            scene.cycles.device = "GPU"
            break
    except Exception:
        pass
scene.cycles.samples = SAMPLES
scene.cycles.use_denoising = True
scene.cycles.denoiser = "OPENIMAGEDENOISE"
scene.cycles.max_bounces = 3
scene.cycles.transparent_max_bounces = 16
scene.render.resolution_x, scene.render.resolution_y = RES
scene.view_settings.view_transform = "Standard"
w = bpy.data.worlds.new("Night")
w.use_nodes = True
w.node_tree.nodes["Background"].inputs["Color"].default_value = (0.02, 0.022, 0.045, 1)
scene.world = w


def emit_mat(name, rgb=None, image=None, strength=1.0, alpha=False, lit_base=None, bake_strength=None):
    """Unlit look: emission of a color or image. alpha=True: alpha-blended (beams/halos).
    lit_base: also a diffuse surface of that albedo (the ground: baked stage light + the module's light pools)."""
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    for n in list(nt.nodes):
        nt.nodes.remove(n)
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    em = nt.nodes.new("ShaderNodeEmission")
    em.inputs["Strength"].default_value = strength
    tex = None
    if image is not None:
        tex = nt.nodes.new("ShaderNodeTexImage")
        tex.image = image
        tex.interpolation = "Linear"
        nt.links.new(tex.outputs["Color"], em.inputs["Color"])
    else:
        em.inputs["Color"].default_value = (*rgb, 1)
    if bake_strength is not None and bake_strength != strength:   # camera sees `strength`, bounced light the bake's
        lp = nt.nodes.new("ShaderNodeLightPath")
        ma = nt.nodes.new("ShaderNodeMath")
        ma.operation = "MULTIPLY_ADD"
        nt.links.new(lp.outputs["Is Camera Ray"], ma.inputs[0])
        ma.inputs[1].default_value = strength - bake_strength
        ma.inputs[2].default_value = bake_strength
        nt.links.new(ma.outputs[0], em.inputs["Strength"])
    shader = em.outputs["Emission"]
    if lit_base is not None:
        d = nt.nodes.new("ShaderNodeBsdfDiffuse")
        d.inputs["Color"].default_value = (*lit_base, 1)
        add = nt.nodes.new("ShaderNodeAddShader")
        nt.links.new(shader, add.inputs[0])
        nt.links.new(d.outputs["BSDF"], add.inputs[1])
        shader = add.outputs["Shader"]
    if alpha and tex is not None:
        tr = nt.nodes.new("ShaderNodeBsdfTransparent")
        mix = nt.nodes.new("ShaderNodeMixShader")
        nt.links.new(tex.outputs["Alpha"], mix.inputs["Fac"])
        nt.links.new(tr.outputs["BSDF"], mix.inputs[1])
        nt.links.new(shader, mix.inputs[2])
        shader = mix.outputs["Shader"]
        m.blend_method = "BLEND" if hasattr(m, "blend_method") else None
    nt.links.new(shader, out.inputs["Surface"])
    return m


def lit_mat(key):
    rgb, rough = kit.LIT[key]
    m = bpy.data.materials.get("LIT_" + key)
    if m:
        return m
    m = bpy.data.materials.new("LIT_" + key)
    m.use_nodes = True
    nt = m.node_tree
    nt.nodes.remove(nt.nodes["Principled BSDF"])                         # the bake is DIFFUSE: no speculars ship
    d = nt.nodes.new("ShaderNodeBsdfDiffuse")
    d.inputs["Color"].default_value = (*(c * EXPOSURE for c in rgb), 1)
    nt.links.new(d.outputs["BSDF"], nt.nodes["Material Output"].inputs["Surface"])
    return m


def load_png(path):
    img = bpy.data.images.load(path, check_existing=True)
    img.colorspace_settings.name = "sRGB"
    img.alpha_mode = "STRAIGHT"
    return img


def obj_from_bm(name, bm, mat):
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    ob = bpy.data.objects.new(name, me)
    coll.objects.link(ob)
    me.materials.append(mat)
    return ob


# ------------------------------------------------------------------ context: the stage as shipped
if CONTEXT:
    n_ctx = 0
    for mesh, src in STAGE.items():
        fbx = os.path.join(STAGE_OUT, mesh + ".fbx")
        if not os.path.exists(fbx):
            continue
        before = set(bpy.data.objects)
        bpy.ops.import_scene.fbx(filepath=fbx, axis_forward="-Z", axis_up="Y")
        for ob in [o for o in bpy.data.objects if o not in before and o.type == "MESH"]:
            ob.data.materials.clear()
            if isinstance(src, str):
                img = load_png(os.path.join(STAGE_OUT, src + ".png"))
                m = emit_mat("C_" + mesh, image=img, lit_base=(0.045, 0.045, 0.05) if mesh == "SM_DinoGround" else None,
                             bake_strength=BAKE_EMIT.get(mesh))
            else:
                m = emit_mat("C_" + mesh, rgb=src, bake_strength=BAKE_EMIT.get(mesh))
            ob.data.materials.append(m)
            n_ctx += 1
    log(f"context: {n_ctx} stage meshes from {STAGE_OUT}")
    st = bpy.data.objects.get("SM_DinoStructure")
    if st:
        bb = [st.matrix_world @ Vector(c) for c in st.bound_box]
        log("context check: structure z %.1f..%.1f m (expect about -1.7..29.3)" % (min(v.z for v in bb), max(v.z for v in bb)))

# ------------------------------------------------------------------ the module
t0 = time.time()
mod = importlib.import_module(MODULE)
res = mod.build(random.Random(1234))
drop = Matrix.Translation((0, 0, -STAGE_DROP))
pal_path = os.path.join(OUT, "T_DinoGroundsPal.png")
kit.write_png(pal_path, kit.tex_palette())
beam_path, halo_path = os.path.join(OUT, "T_DinoBeam.png"), os.path.join(OUT, "T_DinoHalo.png")
kit.write_png(beam_path, kit.tex_beam())
kit.write_png(halo_path, kit.tex_halo())
stats = {}
allpts = []


def place(name, bm, mat, part):
    bm.transform(drop)
    stats[part] = stats.get(part, 0) + kit.tris(bm)
    vs = list(bm.verts)
    allpts.extend(v.co.copy() for v in vs[::max(1, len(vs) // 400)])
    return obj_from_bm(name, bm, mat)


for i, (bm, key) in enumerate(res.get("lit", [])):
    place(f"lit{i}_{key}", bm, lit_mat(key), "lit")
pal = emit_mat("Pal", image=load_png(pal_path), bake_strength=5.0 if FINAL else None)
for i, bm in enumerate(res.get("glow", [])):
    place(f"glow{i}", bm, pal, "glow")
beam_m = emit_mat("Beam", image=load_png(beam_path), alpha=True)
for i, bm in enumerate(res.get("beams", [])):
    place(f"beam{i}", bm, beam_m, "beams")
halo_m = emit_mat("Halo", image=load_png(halo_path), alpha=True)
for i, bm in enumerate(res.get("halos", [])):
    place(f"halo{i}", bm, halo_m, "halos")
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from skull import SKULL_LIGHTS  # noqa: E402

def stage_light(name, kind, pos, target, color, power, size=1.0, spot_deg=40):
    """The stage's own bake lights (copied from ../dino_stage.py stage_lights(), minus the horn uplights)."""
    ld = bpy.data.lights.new(name, kind)
    ld.color, ld.energy = color, power
    if kind == "AREA":
        ld.shape, ld.size = "DISK", size
    if kind == "SPOT":
        ld.spot_size, ld.spot_blend, ld.shadow_soft_size = math.radians(spot_deg), 0.6, size
    ob = bpy.data.objects.new(name, ld)
    ob.location = pos
    ob.rotation_euler = (Vector(target) - Vector(pos)).to_track_quat("-Z", "Y").to_euler()
    ob.location.z -= STAGE_DROP
    coll.objects.link(ob)


if FINAL:
    for side in (-1, 1):
        stage_light(f"Blue{side}", "SPOT", (side * 16, 6, 34), (side * 8, 2, 8), (0.22, 0.4, 1.0), 70000, size=2, spot_deg=70)
        for k, col in enumerate(((1.0, 0.15, 0.6), (0.2, 0.4, 1.0), (1.0, 0.55, 0.1))):
            stage_light(f"Pool{side}{k}", "SPOT", (side * (6 + 7 * k), -3, 14), (side * (8 + 10 * k), -28 - 9 * k, -1.5),
                        col, 120000, size=0.5, spot_deg=16)
        for k in range(4):
            stage_light(f"Wash{side}{k}", "SPOT", (side * (3 + 6 * k), -4.0, 2.5), (side * (4 + 8 * k), -16, -0.5),
                        (0.75, 0.8, 1.0), 1100, size=0.4, spot_deg=45)
    stage_light("Front", "AREA", (0, -45, 14), (0, 6, 10), (0.3, 0.4, 1.0), 1400, size=30)       # night set (2026-10-05)
    stage_light("CrowdGlow", "AREA", (0, -8, 9), (0, -45, 0), (1.0, 0.5, 0.35), 3200, size=25)
    for side, col in ((-1, (1.0, 0.3, 0.8)), (1, (0.3, 0.5, 1.0))):
        stage_light(f"SideFill{side}", "AREA", (side * 30, -10, 6), (side * -8, -40, 0), col, 1800, size=15)
    for name, kind, pos, target, color, power, size, spot in SKULL_LIGHTS:   # dino_stage.py: the v2 head's lights
        stage_light(name, kind, pos, target, color, power, size=size, spot_deg=spot)
lights = res.get("lights", [])
for spec in lights:
    ob = kit.add_light(spec, coll)
    ob.location.z -= STAGE_DROP
sun = bpy.data.lights.new("Moon", "SUN")
sun.color, sun.energy, sun.angle = (0.5, 0.6, 1.0), 0.25, math.radians(10)
so = bpy.data.objects.new("Moon", sun)
so.rotation_euler = (math.radians(35), math.radians(-25), math.radians(20))
coll.objects.link(so)
if allpts:
    lo = Vector((min(p.x for p in allpts), min(p.y for p in allpts), min(p.z for p in allpts)))
    hi = Vector((max(p.x for p in allpts), max(p.y for p in allpts), max(p.z for p in allpts)))
    log(f"module bounds (post-drop): x {lo.x:.1f}..{hi.x:.1f}  y {lo.y:.1f}..{hi.y:.1f}  z {lo.z:.1f}..{hi.z:.1f}")
log(f"module '{MODULE}': tris {stats}, total {sum(stats.values())}; lights {len(lights)}; "
    f"exclude {len(res.get('exclude', []))}; people {len(res.get('people', []))}; build {time.time() - t0:.1f} s")

# ------------------------------------------------------------------ renders
for v in VIEWS:
    if v not in CAMS:
        log(f"unknown view {v}")
        continue
    pos, tgt, lens = CAMS[v]
    cd = bpy.data.cameras.new(v)
    cd.lens, cd.clip_end = lens, 2000
    co = bpy.data.objects.new(v, cd)
    co.location = pos
    co.rotation_euler = (Vector(tgt) - Vector(pos)).to_track_quat("-Z", "Y").to_euler()
    coll.objects.link(co)
    scene.camera = co
    path = os.path.join(OUT, f"preview_{MODULE}_{v}.png")
    scene.render.filepath = path
    t1 = time.time()
    bpy.ops.render.render(write_still=True)
    log(f"render {v}: {path} ({time.time() - t1:.0f} s)")
log("done")
