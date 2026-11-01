"""Translucent overdraw of GRAVEYARD SHIFT (Blender 4.5, headless). The Dino method (grounds/atmosphere_overdraw.py):
every translucent layer adds the same constant emission, so a pixel counts the layers its ray crosses. Geometry
coverage, not alpha, is what the Quest pays for, so fully transparent texels count too. Numbers per view:
  open      every translucent layer (the Dino measure: 0.57 layers/px from the DJ, 0.25 from the stream camera)
  occluded  only the layers in front of the opaque set (the GPU depth test rejects the rest before shading)
Budget (claudedocs/halloween_stage_plan.md Appendix B): <= 2.5 layers/px from the DJ, fog included. The stock build
ships no bolts, fire, fog or ghosts; --split shows what each mesh adds.

  blender -b --factory-startup --python hw_overdraw.py -- [<FBX dir, default out_hw>] [--views dj,dj_vr,...] [--split]
"""
import glob
import os
import sys

import bpy
import numpy as np
from mathutils import Vector

HERE = os.path.dirname(os.path.abspath(__file__))
ARGS = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
VIEWS = (ARGS[ARGS.index("--views") + 1] if "--views" in ARGS else "dj,dj_vr,dj_back,stream").split(",")
POS = [a for i, a in enumerate(ARGS) if not a.startswith("--") and (i == 0 or ARGS[i - 1] != "--views")]
SRC = POS[0] if POS else os.path.join(HERE, "out_hw")
DJ_HEAD = (0.0, 0.9, 1.7)                                     # hw_stage.DJ_HEAD (final frame)
CAMS = {
    "dj": (DJ_HEAD, (0, -60, -2.5), 16),                      # the DJ looking at the crowd
    "dj_vr": (DJ_HEAD, (0, -60, 1.7), 10),                    # level, about the headset field of view
    "dj_back": (DJ_HEAD, (0, 40, 10), 10),                    # turned round to the cathedral, the screen and lasers
    "stream": ((0, -9, 3.5), (0, 6, 9), 16),                  # hw_stage PREVIEWS: Tribe renders it too while streaming
    "crowd": ((3, -40, -0.8), (0, 8, 11), 20),
}
ANIM_ONLY = ("SM_HwBolts", "SM_HwFire", "SM_HwFog", "SM_HwGhosts")   # build_halloween.ANIM_ONLY
TRANS = ["SM_HwBeams", "SM_HwHalos", "SM_HwLasers", "SM_HwSearch", *ANIM_ONLY]
TRANS += sorted(os.path.splitext(os.path.basename(p))[0]
                for pat in ("SM_HwGBeams*.fbx", "SM_HwGHalos*.fbx") for p in glob.glob(os.path.join(SRC, pat)))
NOT_OCCLUDERS = {"SM_HwHands"}                                # down under the deck most of the show
STEP = 1.0 / 64                                               # emission added per layer

bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
scene.render.engine = "CYCLES"
scene.cycles.samples = 16
scene.cycles.use_denoising = False
scene.cycles.max_bounces = 0
scene.cycles.transparent_max_bounces = 128
scene.render.resolution_x, scene.render.resolution_y = 640, 360
scene.render.image_settings.file_format = "OPEN_EXR"
scene.view_settings.view_transform = "Standard"
scene.render.film_transparent = False
w = bpy.data.worlds.new("Black")
w.use_nodes = True
w.node_tree.nodes["Background"].inputs["Color"].default_value = (0, 0, 0, 1)
scene.world = w


def material(name, layer):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    for n in list(nt.nodes):
        nt.nodes.remove(n)
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    em = nt.nodes.new("ShaderNodeEmission")
    if layer:                                                 # adds STEP and lets the ray through
        em.inputs["Strength"].default_value = STEP
        tr, add = nt.nodes.new("ShaderNodeBsdfTransparent"), nt.nodes.new("ShaderNodeAddShader")
        nt.links.new(em.outputs[0], add.inputs[0])
        nt.links.new(tr.outputs[0], add.inputs[1])
        nt.links.new(add.outputs[0], out.inputs["Surface"])
    else:                                                     # opaque black: the ray stops and adds nothing
        em.inputs["Strength"].default_value = 0.0
        nt.links.new(em.outputs[0], out.inputs["Surface"])
    return m


LAYER, SOLID = material("Layer", True), material("Solid", False)
listed = [l.strip() for l in open(os.path.join(SRC, "manifest.txt")) if l.strip()]
trans_obs, solid_obs = {}, []
for mesh in listed:
    fbx = os.path.join(SRC, mesh + ".fbx")
    if not os.path.exists(fbx) or (mesh not in TRANS and mesh in NOT_OCCLUDERS):
        continue
    before = set(bpy.data.objects)
    bpy.ops.import_scene.fbx(filepath=fbx, axis_forward="-Z", axis_up="Y")
    for ob in [o for o in bpy.data.objects if o not in before and o.type == "MESH"]:
        ob.data.materials.clear()
        ob.data.materials.append(LAYER if mesh in TRANS else SOLID)
        (trans_obs.setdefault(mesh, []) if mesh in TRANS else solid_obs).append(ob)
print(f"[OVERDRAW] {SRC}: {len(trans_obs)} translucent meshes {sorted(trans_obs)}; {len(solid_obs)} opaque objects",
      flush=True)

tmp = os.path.join(os.environ.get("TEMP", HERE), "_hw_overdraw.exr")
cam_obs = {}
for v in VIEWS:
    pos, tgt, lens = CAMS[v]
    cd = bpy.data.cameras.new(v)
    cd.lens, cd.clip_end = lens, 2000
    co = bpy.data.objects.new(v, cd)
    co.location = pos
    co.rotation_euler = (Vector(tgt) - Vector(pos)).to_track_quat("-Z", "Y").to_euler()
    scene.collection.objects.link(co)
    cam_obs[v] = co


def measure(view, trans_on, solid_on):
    for mesh, obs in trans_obs.items():
        for ob in obs:
            ob.hide_render = mesh not in trans_on
    for ob in solid_obs:
        ob.hide_render = not solid_on
    scene.camera = cam_obs[view]
    scene.render.filepath = tmp
    bpy.ops.render.render(write_still=True)
    img = bpy.data.images.load(tmp, check_existing=False)
    px = np.array(img.pixels[:], dtype=np.float32).reshape(-1, 4)[:, 0] / STEP
    bpy.data.images.remove(img)
    return px


def line(tag, px):
    return (f"{tag}: mean {px.mean():.2f} layers/px; >=1 {np.mean(px >= 0.5):.0%}  >=2 {np.mean(px >= 1.5):.0%}  "
            f">=4 {np.mean(px >= 3.5):.0%}  >=8 {np.mean(px >= 7.5):.0%}; max {px.max():.0f}")


STOCK = {m for m in trans_obs if m not in ANIM_ONLY}
for v in VIEWS:
    print("[OVERDRAW] " + line(f"{v} open, animated", measure(v, set(trans_obs), False)), flush=True)
    print("[OVERDRAW] " + line(f"{v} occluded, animated", measure(v, set(trans_obs), True)), flush=True)
    print("[OVERDRAW] " + line(f"{v} occluded, stock", measure(v, STOCK, True)), flush=True)
    if "--split" in ARGS:
        for mesh in sorted(trans_obs):
            px = measure(v, {mesh}, True)
            print(f"[OVERDRAW]   {v} {mesh}: mean {px.mean():.2f}, >=1 {np.mean(px >= 0.5):.0%}", flush=True)
if os.path.exists(tmp):
    os.remove(tmp)
print("[OVERDRAW] done", flush=True)
