# Standalone preview + checks for Crowd V2 (Blender 4.5, headless; no stage, no bake):
#   D:\Tools\blender-4.5.14-windows-x64\blender.exe -b --factory-startup --python crowd2_preview.py -- [--grounds] [--t 0.3 1.1]
# Builds the crowd (optionally with the real grounds keep-outs and extra people), checks the VAT decode against direct
# skinning, poses the crowd from the VAT through the material math, and renders Workbench views (albedo colours, studio
# light) from the DJ's eye into ./previews. The look on the headset comes from the stage bake, not from these.
import math
import os
import random
import sys
import time

import bpy
import numpy as np
from mathutils import Vector

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "grounds"))
ARGS = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
TIMES = [float(a) for a in ARGS[ARGS.index("--t") + 1:]] if "--t" in ARGS else [0.30, 1.13]
PREV = os.path.join(HERE, "previews")
os.makedirs(PREV, exist_ok=True)
bpy.ops.wm.read_factory_settings(use_empty=True)
import crowd2 as c2  # noqa: E402
scene = bpy.context.scene
DROP = 1.0                                                     # dino_stage lowers the crowd 1 m; the DJ floor stays at 0


def log(msg):
    print("[PREVIEW] " + msg, flush=True)


exclude, extra = [], []
if "--grounds" in ARGS:                                        # the real keep-outs / extra people (dino_stage's seed)
    import importlib
    for name in ("vendors", "infrastructure", "landmarks", "atmosphere"):
        try:
            res = importlib.import_module(name).build(random.Random(1234))
            exclude += res.get("exclude", [])
            extra += res.get("people", [])
        except Exception as e:  # noqa: BLE001
            log(f"grounds {name} skipped: {e!r}")
t0 = time.time()
crowd, glow, _ = c2.build_crowd2(random.Random(11), exclude, extra, out_dir=PREV, half_fn=c2.crowd_half_v2)
for ob in (crowd, glow):
    ob.data.transform(__import__("mathutils").Matrix.Translation((0, 0, -DROP)))
meta = c2._VAT["meta"]
log(f"built in {time.time() - t0:.1f} s: {meta['people']} people, tris {meta['tris']}, tiers {meta['tiers']}")

# ---------------------------------------------------------------- check: VAT decode (UE-like half UVs) vs skinning
last = c2._LAST
canons = {c.tier: c for c in last["canons"]}
rng = random.Random(3)
cache = {}


def canon_offset(tier, clip, frame):
    key = (tier, clip, frame)
    if key not in cache:
        c = canons[tier]
        cache[key] = c.posed(clip, (frame % c2.FRAMES) / c2.FRAMES) - c.V
    return cache[key]


worst = {"full": 0.0, "half": 0.0}
sample = rng.sample(last["arrays"]["body"]["ranges"], 90)
rest_all = last["arrays"]["body"]["co"] + np.array([0.0, 0.0, -DROP])
vdata_all = c2._POSE[crowd.name][1]
for t in (0.0, 0.37, 2.718, 61.3):
    for i, v0, uniq in sample:
        p = last["people"][i]
        c = canons[p["tier"]]
        vd0 = vdata_all[v0:v0 + len(uniq)]
        cy, sy = math.cos(p["yaw"]), math.sin(p["yaw"])
        rot = np.array([[cy, -sy, 0], [sy, cy, 0], [0, 0, 1]]) @ np.diag([p["sx"] * p["mirror"], p["sx"], p["sz"]])
        for mode in ("full", "half"):
            vd = vd0.copy()
            if mode == "half":                                  # Unreal's default 16-bit UVs (integers stay exact)
                vd[:, 2:] = vd[:, 2:].astype(np.float16).astype(np.float64)
            rate, phase = float(vd[0, 6]), float(vd[0, 5])     # timing as the GPU sees it (a 16-bit rate is a
            ph = (t * rate + phase) % 1.0 * c2.FRAMES           # slightly different rate, not a shape error)
            f0 = int(math.floor(ph))
            a = ph - f0
            off = (1 - a) * canon_offset(p["tier"], p["clip"], f0) + a * canon_offset(p["tier"], p["clip"], f0 + 1)
            expect = (c.V[uniq] + off[uniq]) @ rot.T + np.array([p["x"], p["y"], c2.GROUND_Z - DROP])
            got = rest_all[v0:v0 + len(uniq)] + c2.wpo_blender(vd, t, c2._VAT["tex_half"])
            worst[mode] = max(worst[mode], float(np.abs(got - expect).max()))
log(f"VAT decode vs direct skinning, 90 people x 4 times: max {worst['full'] * 100:.3f} cm (full-precision UVs), "
    f"{worst['half'] * 100:.3f} cm (16-bit UVs)")

# ---------------------------------------------------------------- renders
me = bpy.data.meshes.new("Ground")
me.from_pydata([(-90, 10, -2.52), (90, 10, -2.52), (90, -100, -2.52), (-90, -100, -2.52)], [], [(0, 1, 2, 3)])
gr = bpy.data.objects.new("Ground", me)
scene.collection.objects.link(gr)
me2 = bpy.data.meshes.new("Deck")                               # the stage deck + barrier for scale
me2.from_pydata([(-25, -4.5, -1.0), (25, -4.5, -1.0), (25, 13.5, -1.0), (-25, 13.5, -1.0)], [], [(0, 1, 2, 3)])
scene.collection.objects.link(bpy.data.objects.new("Deck", me2))
for ob in (crowd, glow):
    ob.data.color_attributes.active_color = ob.data.color_attributes["Col"]
scene.render.engine = "BLENDER_WORKBENCH"
sh = scene.display.shading
sh.light, sh.color_type, sh.show_backface_culling = "STUDIO", "VERTEX", True
w = bpy.data.worlds.new("Night")
w.color = (0.01, 0.01, 0.018)
scene.world = w


def render(name, loc, target, lens, res=(1920, 1080)):
    cd = bpy.data.cameras.new(name)
    cd.lens, cd.clip_end = lens, 500
    cam = bpy.data.objects.new(name, cd)
    cam.location = loc
    cam.rotation_euler = (Vector(target) - Vector(loc)).to_track_quat("-Z", "Y").to_euler()
    scene.collection.objects.link(cam)
    scene.camera = cam
    scene.render.resolution_x, scene.render.resolution_y = res
    scene.render.filepath = os.path.join(PREV, name + ".png")
    bpy.ops.render.render(write_still=True)
    log("render " + scene.render.filepath)


eye = (0.0, 0.3, 1.6)                                           # the DJ's eye (the DJ floor is z = 0)
for k, t in enumerate(TIMES):
    c2.pose_preview([crowd, glow], t, loop_rate=128.0 / 120.0)
    render(f"dj_wide_t{k}", eye, (0, -30, -2.0), 16)
    render(f"dj_front_rows_t{k}", eye, (0, -11, -1.6), 35)
render("dj_left", eye, (-30, -18, -2.0), 22)
render("closeup_front_row", (1.5, -6.0, -0.9), (0.5, -10.0, -1.45), 40)
render("side_front", (-24, -6.5, -0.6), (0, -14, -1.6), 28)
render("aerial", (0, 20, 38), (0, -40, -2.5), 22)
c2.pose_preview([crowd, glow], None)
render("rest_front_rows", eye, (0, -11, -1.6), 35)
log("done")
