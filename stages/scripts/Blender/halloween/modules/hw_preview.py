"""Preview one GRAVEYARD SHIFT grounds module in context (Blender 4.5, headless, Cycles on the GPU, no baking).
Adapted from the Dino Stage's ../../grounds/preview.py (same method, Halloween context). Run it through run_preview.sh,
which takes the shared GPU lock:

    bash run_preview.sh hw_graveyard [--views dj_left,overview] [--no-context] [--samples 32] [--res 1280x720] [--raw]
                                     [--open]   (hinged parts swung fully open; default closed, as baked)

- Context = the current Halloween stage exactly as the Quest shows it: ../out_hw/*.fbx (from its manifest) with their
  baked textures, unlit; beams, halos and lasers alpha-blended.
- The module renders as it will ship: "lit" parts lit by the module's own lights, the stage's main bake lights and the
  light of the stage's emitters (at their bake strengths: the camera still sees them at 1), with the lit albedo scaled by
  the bake's exposure (0.9 = Dino's grounds 1.8 x night 0.5: the linear part of 1 - exp(-0.9 x)); "glow" parts unlit on
  the kit palette; "beams"/"halos" alpha-blended. --raw turns the simulation off.
- The module is built in the kit's frame (field at -1.5) and lowered by 1.0 m, as hw_stage.py does.
- Writes out/preview_<module>_<view>.png and prints [HWGROUNDS] stats (tris per part, lights, bounds).
"""
import importlib
import math
import os
import random
import sys
import time

import bpy
from mathutils import Matrix, Vector

HERE = os.path.dirname(os.path.abspath(__file__))
STAGE_OUT = os.path.join(os.path.dirname(HERE), "out_hw")
OUT = os.path.join(HERE, "out")
os.makedirs(OUT, exist_ok=True)
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "..", "..", "grounds"))
import kit  # noqa: E402  (read-only)

STAGE_DROP = 1.0
FIELD_Z, DECK_Z = -2.5, -1.0                      # the final frame (hw_stage.py)
ARGS = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
MODULE = ARGS[0] if ARGS else sys.exit("usage: hw_preview.py -- <module> [options]")


def opt(name, default):
    return ARGS[ARGS.index(name) + 1] if name in ARGS else default


VIEWS = opt("--views", "dj,dj_left,dj_right,overview").split(",")
SAMPLES = int(opt("--samples", "32"))
RES = tuple(int(v) for v in opt("--res", "1280x720").split("x"))
CONTEXT = "--no-context" not in ARGS
FINAL = "--raw" not in ARGS
EXPOSURE = 1.8 * 0.5 if FINAL else 1.0
# camera spots (final frame: Tribe's floor z=0 = the DJ riser; crowd field at z=-2.5)
CAMS = {
    "dj": ((0, -0.3, 1.65), (0, -60, -2.5), 16),
    "dj_left": ((0, -0.3, 1.65), (-45, -30, -1.0), 16),
    "dj_right": ((0, -0.3, 1.65), (45, -30, -1.0), 16),
    "dj_front": ((0, 0.9, 1.7), (0, -40, -1.0), 18),
    "overview": ((0, 25, 45), (0, -55, -2.5), 20),
    "back": ((0, -95, 12), (0, 0, 6), 24),
    "side_left": ((-80, -30, 15), (0, -40, -2), 24),
    "side_right": ((80, -30, 15), (0, -40, -2), 24),
    "crowd": ((3, -40, -0.8), (0, 8, 11), 20),
    "drone_crowd": ((0, -20, 12), (0, -80, 0), 20),
    "carnival": ((-28, -78, 7), (-60, -110, 2), 22),
    "pumpkins": ((32, -62, 6), (60, -90, 0), 22),
    "king": ((50, -72, 4.0), (63, -92, 3.7), 35),                # the Pumpkin King close (his jaw: --open)
    "woods_low": ((-4, 90, -1.8), (10, 112, 1.5), 24),              # the intro woods: inside the loop, low
    "woods_exit": ((-2, 50, 0.5), (-14, 85, 2.0), 24),              # from the clearing behind the nave into the trees
    "woods_top": ((0, 30, 60), (0, 100, -2.5), 24),                 # over the cathedral, looking down on the woods
    "crypt": ((38, -98, 4), (60, -128, 4), 22),
    "aerial": ((-70, -95, 55), (0, -30, 0), 22),
}
# the stage's surfaces (build_halloween.py SURFACES): texture or flat color; "a:" = alpha-blended
STAGE = {
    "SM_HwFacade": "T_HwFacade", "SM_HwFacadeDetail": "T_HwFacadeDetail", "SM_HwDeck": "T_HwDeck", "SM_HwRig": "T_HwRig",
    "SM_HwGlow": "T_HwGlowPal", "SM_DinoVisualScreen": (0.0, 0.0, 0.0), "SM_HwGround": "T_HwGround",
    "SM_HwFarGround": (0.004, 0.004, 0.006), "SM_HwSky": "T_HwSky", "SM_HwMoon": "T_HwMoon",
    "SM_HwBeams": "a:T_HwBeam", "SM_HwHalos": "a:T_HwHalo", "SM_HwLasers": "a:T_HwBeam", "SM_HwSearch": "a:T_HwBeam",
    # v2 (hw_stage.py v2): the cue-lit glass, eyes and lenses, the clock, the bats, the crowd. Left out: the giant hands
    # (down under the deck most of the show; hw_stage hides them from the other bakes), the grounds meshes
    # (SM_HwGrounds*, SM_HwGBeams*, SM_HwGHalos*: they would double the module being previewed) and the effects that
    # only the animated build ships (bolts, fire, fog, ghosts).
    "SM_HwWindows": "T_HwGlowPal", "SM_HwEyes": "T_HwGlowPal", "SM_HwLenses": "T_HwGlowPal",
    "SM_HwClockFace": "T_HwGlowPal", "SM_HwClockHands": "T_HwGlowPal", "SM_HwBats": "T_HwGlowPal",
    "SM_HwCrowd": "T_HwCrowd", "SM_HwPhones": (0.9, 0.55, 0.25),
}
GLOWS = ("SM_HwGlow", "SM_HwWindows", "SM_HwEyes", "SM_HwLenses", "SM_HwClockFace", "SM_HwClockHands")
BAKE_EMIT = {m: 5.0 for m in GLOWS} if FINAL else {}    # hw_stage.py lights its bakes with these at strength 5


def log(msg):
    print("[HWGROUNDS] " + msg, flush=True)


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
w.node_tree.nodes["Background"].inputs["Color"].default_value = (0.012, 0.012, 0.026, 1)
scene.world = w


def emit_mat(name, rgb=None, image=None, strength=1.0, alpha=False, lit_base=None, bake_strength=None):
    """Unlit look: emission of a color or image. alpha=True: alpha-blended (beams/halos). lit_base: also a diffuse
    surface (the ground: baked stage light + the module's light pools). bake_strength: what bounced light sees."""
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
        tex.interpolation = "Closest" if image.size[0] <= 64 else "Linear"
        nt.links.new(tex.outputs["Color"], em.inputs["Color"])
    else:
        em.inputs["Color"].default_value = (*rgb, 1)
    if bake_strength is not None and bake_strength != strength:
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


# ------------------------------------------------------------------ context: the Halloween stage as shipped
if CONTEXT:
    man = os.path.join(STAGE_OUT, "manifest.txt")
    meshes = [l.strip() for l in open(man) if l.strip()] if os.path.exists(man) else list(STAGE)
    n_ctx = 0
    for mesh in meshes:
        src = STAGE.get(mesh)
        fbx = os.path.join(STAGE_OUT, mesh + ".fbx")
        if src is None or not os.path.exists(fbx):
            continue
        before = set(bpy.data.objects)
        bpy.ops.import_scene.fbx(filepath=fbx, axis_forward="-Z", axis_up="Y")
        for ob in [o for o in bpy.data.objects if o not in before and o.type == "MESH"]:
            ob.data.materials.clear()
            if isinstance(src, str):
                alpha = src.startswith("a:")
                img = load_png(os.path.join(STAGE_OUT, src[2:] if alpha else src) + ".png")
                m = emit_mat("C_" + mesh, image=img, alpha=alpha,
                             lit_base=(0.035, 0.04, 0.03) if mesh == "SM_HwGround" else None,
                             bake_strength=BAKE_EMIT.get(mesh))
            else:
                m = emit_mat("C_" + mesh, rgb=src)
            ob.data.materials.append(m)
            n_ctx += 1
    log(f"context: {n_ctx} stage meshes from {STAGE_OUT}")

# ------------------------------------------------------------------ the module (kit frame, lowered by the stage drop)
t0 = time.time()
mod = importlib.import_module(MODULE)
res = mod.build(random.Random(1234))
drop = Matrix.Translation((0, 0, -STAGE_DROP))
pal_path, beam_path, halo_path = (os.path.join(OUT, n) for n in ("T_HwGroundsPal.png", "T_HwGroundsBeam.png",
                                                                  "T_HwGroundsHalo.png"))
kit.write_png(pal_path, kit.tex_palette())
kit.write_png(beam_path, kit.tex_beam())
kit.write_png(halo_path, kit.tex_halo())
stats, allpts = {}, []


def place(name, bm, mat, part):
    bm.transform(drop)
    stats[part] = stats.get(part, 0) + kit.tris(bm)
    vs = list(bm.verts)
    allpts.extend(v.co.copy() for v in vs[::max(1, len(vs) // 400)])
    return obj_from_bm(name, bm, mat)


for i, (bm, key) in enumerate(res.get("lit", [])):
    place(f"lit{i}_{key}", bm, lit_mat(key), "lit")
OPEN = "--open" in ARGS
for i, (bm, key, pivot, axis, open_deg, *_rest) in enumerate(res.get("hinged", [])):   # CONTRACT.md "hinged"
    if OPEN:
        pv = Vector(pivot)
        bm.transform(Matrix.Translation(pv) @ Matrix.Rotation(math.radians(open_deg), 4, Vector(axis).normalized())
                     @ Matrix.Translation(-pv))
    place(f"hinged{i}_{key}", bm, lit_mat(key), "hinged")
pal = emit_mat("Pal", image=load_png(pal_path), bake_strength=5.0 if FINAL else None)
for i, bm in enumerate(res.get("glow", [])):
    place(f"glow{i}", bm, pal, "glow")
beam_m = emit_mat("Beam", image=load_png(beam_path), alpha=True)
for i, bm in enumerate(res.get("beams", [])):
    place(f"beam{i}", bm, beam_m, "beams")
halo_m = emit_mat("Halo", image=load_png(halo_path), alpha=True)
for i, bm in enumerate(res.get("halos", [])):
    place(f"halo{i}", bm, halo_m, "halos")


def stage_light(name, kind, pos, target, color, power, size=1.0, spot_deg=40):
    """The Halloween stage's main bake lights (hw_stage.py stage_lights, final frame: no drop)."""
    ld = bpy.data.lights.new(name, kind)
    ld.color, ld.energy = color, power
    if kind == "SPOT":
        ld.spot_size, ld.spot_blend, ld.shadow_soft_size = math.radians(spot_deg), 0.6, size
    elif kind == "POINT":
        ld.shadow_soft_size = size
    ob = bpy.data.objects.new(name, ld)
    ob.location = pos
    ob.rotation_euler = (Vector(target) - Vector(pos)).to_track_quat("-Z", "Y").to_euler()
    coll.objects.link(ob)


if FINAL:
    ORANGE, PURPLE, GREENISH = (1.0, 0.40, 0.05), (0.40, 0.10, 1.0), (0.3, 0.9, 0.4)
    for sx in (-1, 1):
        stage_light(f"Wash{sx}", "SPOT", (sx * 24, 12.4, 26.5), (sx * 10, -28, FIELD_Z),
                    PURPLE if sx < 0 else GREENISH, 90000 if sx < 0 else 60000, 2.0, 70)
        stage_light(f"UpOak{sx}", "SPOT", (sx * 34, 0, FIELD_Z), (sx * 39, 6, 12), (0.25, 0.9, 0.35), 9000, 0.6, 45)
    stage_light("WashC", "SPOT", (0, 9.8, 16), (0, -16, FIELD_Z), ORANGE, 40000, 1.0, 80)
    stage_light("Follow", "SPOT", (0, -31, 3.5), (0, 0.9, 1.4), (1.0, 0.9, 0.8), 2500, 0.3, 6)
lights = res.get("lights", [])
for spec in lights:
    ob = kit.add_light(spec, coll)
    ob.location.z -= STAGE_DROP
for name, energy, col, d in (("Moon", 0.25, (0.35, 0.65, 1.0), Vector((30, -100, -81))),
                             ("MoonFill", 0.35, (0.45, 0.55, 0.9), Vector((0, 120, -60)))):
    sun = bpy.data.lights.new(name, "SUN")
    sun.color, sun.energy, sun.angle = col, energy, math.radians(8)
    so = bpy.data.objects.new(name, sun)
    so.rotation_euler = d.to_track_quat("-Z", "Y").to_euler()
    coll.objects.link(so)
if allpts:
    lo = Vector((min(p.x for p in allpts), min(p.y for p in allpts), min(p.z for p in allpts)))
    hi = Vector((max(p.x for p in allpts), max(p.y for p in allpts), max(p.z for p in allpts)))
    log(f"module bounds (final frame): x {lo.x:.1f}..{hi.x:.1f}  y {lo.y:.1f}..{hi.y:.1f}  z {lo.z:.1f}..{hi.z:.1f}")
log(f"module '{MODULE}': tris {stats}, total {sum(stats.values())}; lights {len(lights)}; "
    f"exclude {len(res.get('exclude', []))}; people {len(res.get('people', []))}; build {time.time() - t0:.1f} s")

# ------------------------------------------------------------------ renders
for v in VIEWS:
    if v not in CAMS:
        log(f"unknown view {v} (have: {', '.join(CAMS)})")
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
