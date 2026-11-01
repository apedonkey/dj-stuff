"""Preview the v2 arch and its arch-shaped screen in a build (Blender 4.5, headless, Cycles GPU), as the Quest shows it:

  set DINO_OUT=...\\out_arch & blender.exe -b --factory-startup --python arch_preview.py --
        [--views a,b] [--res 1280x720] [--samples 24] [--frame <png>] [--no-lasers]

Every mesh of the build (DINO_OUT/manifest.txt) is shown unlit with its baked texture or flat glow color (dino_stage's
own final preview), the beams and halos alpha-blended. The visual screen shows a real video frame the way Tribe's
M_VideoBackdrop maps it: the frame sampled at image (u, v) = (1 - U, 2 V) of the screen's UV0. SM_DinoLasers (the
horn heads on arch.horn_tips(), the stage fan) shows in its rest pose; --no-lasers leaves it out.
Writes DINO_OUT/arch_preview/<view>.png.
"""
import os
import sys
import time

import bpy
from mathutils import Vector

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.environ.get("DINO_OUT") or os.path.join(HERE, "out")
PREVIEW = os.path.join(OUT, "arch_preview")
os.makedirs(PREVIEW, exist_ok=True)
ARGS = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []


def opt(name, default):
    return ARGS[ARGS.index(name) + 1] if name in ARGS else default


FRAME = opt("--frame", r"C:\Users\Chris\TribeUE\Visuals\renders\spine_tunnel"
                       r"\spine_tunnel_128bpm_8bars_1080p30_nostrobe_still_f262.png")
RES = tuple(int(v) for v in opt("--res", "1280x720").split("x"))
SAMPLES = int(opt("--samples", "24"))
CAMS = {   # post-drop world (Tribe's floor z = 0 = the DJ riser; the crowd floor is z -2.5): position, target, lens
    "stream_drone": ((0, -95, 12), (0, 0, 6), 24),                   # the stream camera, 95 m out
    "mid_crowd": ((0, -24, 0.8), (0, 9, 7.5), 18),                   # in front of the FOH tower, over the heads
    "front_rows": ((1.5, -9.5, -0.7), (0, 9, 9.5), 14),              # at the barrier, eye height, looking up
    "dj_back": ((0, 0.9, 1.6), (0, 9, 7.0), 14),                     # the DJ turned around (VR-wide lens)
    "overview": ((-42, -58, 30), (0, 4, 5), 24),                     # front-left, high
    "q34": ((-30, -26, 5), (0, 6, 9), 24),                           # front-left, low
}
VIEWS = opt("--views", ",".join(CAMS)).split(",")
FLAT = {"SM_DinoBulbs": (1.0, 0.75, 0.4), "SM_DinoEyes": (1.0, 0.06, 0.02), "SM_DinoGlow": (0.2, 0.9, 1.0),
        "SM_DinoPillars": (0.2, 0.9, 1.0), "SM_DinoFarGround": (0.004, 0.004, 0.006)}
TEX = {"SM_DinoScreen": "T_DinoMoon", "SM_DinoLenses": "T_DinoLens", "SM_DinoGroundsGlow": "T_DinoGroundsPal",
       "SM_DinoFlags": "T_DinoFlags"}


def log(msg):
    print("[ARCHPREVIEW] " + msg, flush=True)


bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
coll = scene.collection
scene.render.engine = "CYCLES"
prefs = bpy.context.preferences.addons["cycles"].preferences
for dev_type in ("OPTIX", "CUDA"):
    try:
        prefs.compute_device_type = dev_type
        prefs.get_devices()
        if [d for d in prefs.devices if d.type == dev_type]:
            for d in prefs.devices:
                d.use = d.type == dev_type
            scene.cycles.device = "GPU"
            break
    except Exception:
        pass
scene.cycles.samples = SAMPLES
scene.cycles.use_denoising = True
scene.cycles.max_bounces = 2
scene.cycles.transparent_max_bounces = 24
scene.render.resolution_x, scene.render.resolution_y = RES
scene.view_settings.view_transform = "Standard"
world = bpy.data.worlds.new("Black")
world.use_nodes = True
world.node_tree.nodes["Background"].inputs["Color"].default_value = (0, 0, 0, 1)
scene.world = world


def image(path):
    img = bpy.data.images.load(path, check_existing=True)
    img.alpha_mode = "STRAIGHT"
    return img


def unlit(name, src=None, alpha=False, attr=None, video=False):
    """Emission of a texture (src = png path), a flat color (src = rgb) or a color attribute; alpha: blended by the
    texture's alpha; video: the texture sampled at (1 - U, 2 V) (Tribe's video mapping), black outside."""
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    em = nt.nodes.new("ShaderNodeEmission")
    tex = None
    if attr:
        at = nt.nodes.new("ShaderNodeAttribute")
        at.attribute_name = attr
        nt.links.new(at.outputs["Color"], em.inputs["Color"])
    elif isinstance(src, str):
        tex = nt.nodes.new("ShaderNodeTexImage")
        tex.image = image(src)
        nt.links.new(tex.outputs["Color"], em.inputs["Color"])
        if video:
            uv = nt.nodes.new("ShaderNodeUVMap")
            sep = nt.nodes.new("ShaderNodeSeparateXYZ")
            u = nt.nodes.new("ShaderNodeMath")
            u.operation = "SUBTRACT"
            u.inputs[0].default_value = 1.0
            v = nt.nodes.new("ShaderNodeMath")
            v.operation = "MULTIPLY"
            v.inputs[1].default_value = 2.0
            comb = nt.nodes.new("ShaderNodeCombineXYZ")
            nt.links.new(uv.outputs["UV"], sep.inputs[0])
            nt.links.new(sep.outputs[0], u.inputs[1])
            nt.links.new(sep.outputs[1], v.inputs[0])
            nt.links.new(u.outputs[0], comb.inputs[0])
            nt.links.new(v.outputs[0], comb.inputs[1])
            nt.links.new(comb.outputs[0], tex.inputs["Vector"])
            tex.extension = "CLIP"
    else:
        em.inputs["Color"].default_value = (*src, 1)
    shader = em.outputs["Emission"]
    if alpha and tex is not None:
        tr = nt.nodes.new("ShaderNodeBsdfTransparent")
        mix = nt.nodes.new("ShaderNodeMixShader")
        nt.links.new(tex.outputs["Alpha"], mix.inputs["Fac"])
        nt.links.new(tr.outputs["BSDF"], mix.inputs[1])
        nt.links.new(shader, mix.inputs[2])
        shader = mix.outputs["Shader"]
    nt.links.new(shader, out.inputs["Surface"])
    return m


t0 = time.time()
names = [n.strip() for n in open(os.path.join(OUT, "manifest.txt")) if n.strip()]
shown = 0
for name in names:
    if name == "SM_DinoLasers" and "--no-lasers" in ARGS:
        continue
    path = os.path.join(OUT, name + ".fbx")
    if not os.path.exists(path):
        continue
    before = set(bpy.data.objects)
    bpy.ops.import_scene.fbx(filepath=path, axis_forward="-Z", axis_up="Y")
    for ob in [o for o in bpy.data.objects if o not in before]:
        if ob.type != "MESH":
            bpy.data.objects.remove(ob)
            continue
        ob.data.materials.clear()
        if name == "SM_DinoVisualScreen":
            mat = unlit("Video", FRAME, video=True)
        elif name.startswith(("SM_DinoBeams", "SM_DinoLasers")):
            mat = unlit("A" + name, os.path.join(OUT, "T_DinoBeam.png"), alpha=True)
        elif name.startswith("SM_DinoHalos"):
            mat = unlit("A" + name, os.path.join(OUT, "T_DinoHalo.png"), alpha=True)
        elif name == "SM_DinoPhones":
            has_col = "Col" in ob.data.color_attributes
            mat = unlit("Phones", attr="Col") if has_col else unlit("Phones", (0.85, 0.9, 1.0))
        elif name in FLAT:
            mat = unlit("F" + name, FLAT[name])
        else:
            tex = TEX.get(name, "T_" + name[3:])
            mat = unlit("P" + name, os.path.join(OUT, tex + ".png"))
        ob.data.materials.append(mat)
        shown += 1
log(f"{shown} meshes from {OUT} ({time.time() - t0:.0f} s); the screen shows {os.path.basename(FRAME)}")

cam_data = bpy.data.cameras.new("Cam")
cam_data.clip_end = 2000
cam = bpy.data.objects.new("Cam", cam_data)
coll.objects.link(cam)
scene.camera = cam
for v in VIEWS:
    pos, tgt, lens = CAMS[v]
    cam.location = pos
    cam.rotation_euler = (Vector(tgt) - Vector(pos)).to_track_quat("-Z", "Y").to_euler()
    cam_data.lens = lens
    scene.render.filepath = os.path.join(PREVIEW, v + ".png")
    t1 = time.time()
    bpy.ops.render.render(write_still=True)
    log(f"{v}: {scene.render.filepath} ({time.time() - t1:.0f} s)")
