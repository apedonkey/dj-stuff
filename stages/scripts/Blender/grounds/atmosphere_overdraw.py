"""Translucent overdraw of a grounds module (Blender 4.5, headless): renders only its "beams", "lasers" (rest pose) and "halos" with every
layer adding the same constant, then prints per view the mean layers per pixel and the share of pixels under at least
1/2/4/8 layers. Geometry coverage, not alpha, is what the GPU pays for, so fully transparent texels count too.

  blender.exe -b --factory-startup --python grounds/atmosphere_overdraw.py -- atmosphere [--views dj,dj_vr,back] [--split]
  (--split also reports each beams/lasers/halos mesh alone)
"""
import importlib
import os
import random
import sys

import bpy
import numpy as np
from mathutils import Matrix, Vector

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
ARGS = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
MODULE = ARGS[0] if ARGS else "atmosphere"
VIEWS = (ARGS[ARGS.index("--views") + 1] if "--views" in ARGS else "dj,dj_vr,back").split(",")
CAMS = {                                                 # post-drop, as in preview.py / atmosphere_preview.py
    "dj": ((0, -0.3, 1.65), (0, -60, -2.5), 16),
    "dj_vr": ((0, -0.3, 1.65), (0, -60, 1.65), 10),
    "back": ((0, -95, 12), (0, 0, 6), 24),
    "overview": ((0, 25, 40), (0, -50, -2.5), 20),
    "drone_crowd": ((0, -20, 12), (0, -80, 0), 20),
}
STEP = 1.0 / 64                                          # emission added per layer

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

m = bpy.data.materials.new("Layer")
m.use_nodes = True
nt = m.node_tree
for n in list(nt.nodes):
    nt.nodes.remove(n)
em, tr, add, out = (nt.nodes.new(t) for t in ("ShaderNodeEmission", "ShaderNodeBsdfTransparent", "ShaderNodeAddShader",
                                               "ShaderNodeOutputMaterial"))
em.inputs["Strength"].default_value = STEP
nt.links.new(em.outputs[0], add.inputs[0])
nt.links.new(tr.outputs[0], add.inputs[1])
nt.links.new(add.outputs[0], out.inputs["Surface"])

res = importlib.import_module(MODULE).build(random.Random(1234))
drop = Matrix.Translation((0, 0, -1.0))
for part in ("beams", "lasers", "halos"):
    for i, bm in enumerate(res.get(part, [])):
        bm.transform(drop)
        me = bpy.data.meshes.new(f"{part}{i}")
        bm.to_mesh(me)
        bm.free()
        me.materials.append(m)
        scene.collection.objects.link(bpy.data.objects.new(f"{part}{i}", me))

tmp = os.path.join(HERE, "out", "_overdraw.exr")
groups = [[o] for o in scene.objects if o.type == "MESH"] if "--split" in ARGS else []
for v, solo in [(v, None) for v in VIEWS] + [(v, g) for v in VIEWS for g in groups]:
    for o in scene.objects:
        if o.type == "MESH":
            o.hide_render = solo is not None and o not in solo
    pos, tgt, lens = CAMS[v]
    cd = bpy.data.cameras.new(v)
    cd.lens, cd.clip_end = lens, 2000
    co = bpy.data.objects.new(v, cd)
    co.location = pos
    co.rotation_euler = (Vector(tgt) - Vector(pos)).to_track_quat("-Z", "Y").to_euler()
    scene.collection.objects.link(co)
    scene.camera = co
    scene.render.filepath = tmp
    bpy.ops.render.render(write_still=True)
    img = bpy.data.images.load(tmp, check_existing=False)
    px = np.array(img.pixels[:], dtype=np.float32).reshape(-1, 4)[:, 0] / STEP
    bpy.data.images.remove(img)
    tag = v if solo is None else f"{v} {solo[0].name}"
    print(f"[OVERDRAW] {tag}: mean {px.mean():.2f} layers/pixel; >=1 {np.mean(px >= 0.5):.0%}  >=2 {np.mean(px >= 1.5):.0%}"
          f"  >=4 {np.mean(px >= 3.5):.0%}  >=8 {np.mean(px >= 7.5):.0%}; max {px.max():.0f}", flush=True)
os.remove(tmp)
