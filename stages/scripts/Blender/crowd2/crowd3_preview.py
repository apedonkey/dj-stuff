# Standalone preview + checks for Crowd V3 (Blender 4.5, headless; no stage, no bake):
#   D:\Tools\blender-4.5.14-windows-x64\blender.exe -b --factory-startup --python crowd3_preview.py -- [--no-grounds] [--no-render]
# Builds the crowd like dino_stage does (grounds keep-outs / extra people, seed 11) into ./previews_v3 (its own VAT
# .exr/.json: never Scripts/Blender/out), then:
#   * checks the VAT decode (pages, frame-0 offsets, Unreal's 16-bit UVs) against direct skinning,
#   * measures what frame-0 offsets cost body types (a morphed vertex rides the canonical offsets),
#   * counts tris per tier and estimates Unreal's vertex count (splits at UV0 seams and colour borders),
#   * renders Workbench views from the DJ's eye (studio + flat albedo), a dark "night" approximation (albedo x 0.05,
#     glow at full), front-row close-ups, and line-ups of every dance and of the costumes / accessories.
# The look on the headset comes from the stage bake, not from these.
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
PREV = os.path.join(HERE, "previews_v3")
os.makedirs(PREV, exist_ok=True)
bpy.ops.wm.read_factory_settings(use_empty=True)
import crowd3 as c3  # noqa: E402
scene = bpy.context.scene
DROP = 1.0                                                     # dino_stage lowers the crowd 1 m; the DJ floor stays at 0


def log(msg):
    print("[PREVIEW3] " + msg, flush=True)


exclude, extra = [], []
if "--no-grounds" not in ARGS:                                 # the real keep-outs / extra people (dino_stage's seeds)
    import importlib
    for name in ("vendors", "infrastructure", "landmarks", "atmosphere"):
        try:
            mod = importlib.import_module(name)
            if hasattr(mod, "TOTEMS"):
                mod.TOTEMS = False
            res = mod.build(random.Random(1234))
            exclude += res.get("exclude", [])
            extra += res.get("people", [])
        except Exception as e:  # noqa: BLE001
            log(f"grounds {name} skipped: {e!r}")
    for ob in list(bpy.data.objects):                          # grounds builders may leave objects: keep the scene clean
        bpy.data.objects.remove(ob)
t0 = time.time()
crowd, glow, _ = c3.build_crowd2(random.Random(11), exclude, extra, out_dir=PREV)
for ob in (crowd, glow):
    ob.data.transform(__import__("mathutils").Matrix.Translation((0, 0, -DROP)))
meta = c3._VAT["meta"]
log(f"built in {time.time() - t0:.1f} s: {meta['people']} people, tris {meta['tris']}, VAT {meta['width']}x{meta['height']}")
last = c3._LAST
canons = {c.tier: c for c in last["canons"]}
people = last["people"]

# ---------------------------------------------------------------- budget: tris per tier, Unreal vertex estimate
per_tier = {}
for p in people:
    c = canons[p["tier"]]
    ok = np.zeros(len(c3.PARTS), dtype=bool)
    ok[[c3.PART[q] for q in p["parts"] if q in c3.PART]] = True
    fm = ok[c.F_part]
    s = per_tier.setdefault(p["tier"], {"people": 0, "body": 0, "glow": 0})
    s["people"] += 1
    s["body"] += int((c.F_len[fm & ~c.F_glow] - 2).sum())
    s["glow"] += int((c.F_len[fm & c.F_glow] - 2).sum())
for t, s in per_tier.items():
    log(f"tier {t}: {s['people']} people, body {s['body']} tris ({s['body'] / s['people']:.0f}/person), "
        f"glow {s['glow']} tris")


def ue_vertices(a, with_uv0=True):
    cols = [a["lvert"][:, None].astype(np.int64)]
    if with_uv0:
        cols.append(np.round(a["uv0"] * (1 << 20)).astype(np.int64))
    cols.append(np.round(a["col"][:, :3] * 4096).astype(np.int64))
    return len(np.unique(np.concatenate(cols, 1), axis=0))


ue = {"body": ue_vertices(last["arrays"]["body"]), "glow": ue_vertices(last["arrays"]["glow"], with_uv0=False)}
log(f"Blender vertices {meta['blender_vertices']}, Unreal estimate (UV0 seams + colour borders) {ue}, total "
    f"{ue['body'] + ue['glow']}; tris total {meta['tris']['body'] + meta['tris']['glow']}")

# ---------------------------------------------------------------- check: VAT decode vs direct skinning; morph cost
rng = random.Random(3)
cache = {}


def canon_offset(tier, clip, frame):
    key = (tier, clip, frame)
    if key not in cache:
        c = canons[tier]
        cache[key] = c.posed(clip, (frame % c3.FRAMES) / c3.FRAMES) - c.posed(clip, 0.0)
    return cache[key]


worst = {"full": 0.0, "half": 0.0}
ranges = last["arrays"]["body"]["ranges"]
sample = rng.sample(ranges, min(150, len(ranges)))
base_all = last["arrays"]["body"]["co"] + np.array([0.0, 0.0, -DROP])
vdata_all = c3._POSE[crowd.name][1]
for t in (0.0, 0.37, 2.718, 61.3):
    for i, v0, uniq in sample:
        p = people[i]
        vd0 = vdata_all[v0:v0 + len(uniq)]
        cy, sy = math.cos(p["yaw"]), math.sin(p["yaw"])
        rot = np.array([[cy, -sy, 0], [sy, cy, 0], [0, 0, 1]]) @ np.diag([p["sx"] * p["mirror"], p["sx"], p["sz"]])
        base = base_all[v0:v0 + len(uniq)]
        for mode in ("full", "half"):
            vd = vd0.copy()
            if mode == "half":                                  # Unreal's default 16-bit UVs (integers stay exact)
                vd[:, 2:] = vd[:, 2:].astype(np.float16).astype(np.float64)
            rate, phase = float(vd[0, 6]), float(vd[0, 5])     # timing as the GPU sees it
            ph = (t * rate + phase) % 1.0 * c3.FRAMES
            f0 = int(math.floor(ph))
            a = ph - f0
            off = (1 - a) * canon_offset(p["tier"], p["clip"], f0) + a * canon_offset(p["tier"], p["clip"], f0 + 1)
            expect = base + off[uniq] @ rot.T
            got = base + c3.wpo_blender(vd, t, c3._VAT["tex_half"])
            worst[mode] = max(worst[mode], float(np.abs(got - expect).max()))
log(f"VAT decode vs direct skinning, {len(sample)} people x 4 times: max {worst['full'] * 100:.3f} cm (full-precision "
    f"UVs), {worst['half'] * 100:.3f} cm (16-bit UVs); clip index = page * {len(c3.CLIPS)} + clip, pages {meta['pages']}")
morph_err = []
for i, v0, uniq in sample:                                     # ideal skinning of the morphed body vs base + offsets
    p = people[i]
    c = canons[p["tier"]]
    X = c.V[uniq].copy()
    for mk, mv in p["morph"].items():
        X += mv * c.morph[mk][uniq]
    b0 = c.lbs(X, uniq, c3.pose_arrays(p["clip"], 0.0))
    e = 0.0
    for f in range(0, c3.FRAMES, 2):
        ideal = c.lbs(X, uniq, c3.pose_arrays(p["clip"], f / c3.FRAMES))
        e = max(e, float(np.abs(ideal - (b0 + canon_offset(p["tier"], p["clip"], f)[uniq])).max()) * p["sz"])
    morph_err.append(e)
me_ = np.array(morph_err)
log(f"frame-0 offsets on morphed bodies (vs exact skinning): median {np.median(me_) * 100:.2f} cm, 95% "
    f"{np.percentile(me_, 95) * 100:.2f} cm, max {me_.max() * 100:.2f} cm")
if "--no-render" in ARGS:
    log("done (no renders)")
    sys.exit(0)

# ---------------------------------------------------------------- scene for renders
def flat_mesh(name, verts, color):
    me = bpy.data.meshes.new(name)
    me.from_pydata(verts, [], [(0, 1, 2, 3)])
    ca = me.color_attributes.new("Col", "FLOAT_COLOR", "CORNER")
    for d in ca.data:
        d.color = (*color, 1.0)
    ob = bpy.data.objects.new(name, me)
    scene.collection.objects.link(ob)
    return ob


flat_mesh("Ground", [(-90, 10, -2.52), (90, 10, -2.52), (90, -100, -2.52), (-90, -100, -2.52)], (0.03, 0.03, 0.035))
flat_mesh("Deck", [(-25, -4.5, -1.0), (25, -4.5, -1.0), (25, 13.5, -1.0), (-25, 13.5, -1.0)], (0.05, 0.05, 0.06))
for ob in (crowd, glow):
    ob.data.color_attributes.active_color = ob.data.color_attributes["Col"]
scene.render.engine = "BLENDER_WORKBENCH"
scene.view_settings.view_transform = "Standard"
sh = scene.display.shading
sh.color_type, sh.show_backface_culling = "VERTEX", True
w = bpy.data.worlds.new("Night")
w.color = (0.01, 0.01, 0.018)
scene.world = w


def render(name, loc, target, lens=35, res=(1920, 1080), light="STUDIO", ortho=None):
    sh.light = light
    cd = bpy.data.cameras.new(name)
    cd.lens, cd.clip_end = lens, 500
    if ortho:
        cd.type, cd.ortho_scale = "ORTHO", ortho
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
close = ((1.5, -6.0, -0.9), (0.5, -10.0, -1.45))
for k, t in enumerate((0.30, 1.13)):
    c3.pose_preview([crowd, glow], t, loop_rate=128.0 / 120.0)
    render(f"dj_wide_t{k}", eye, (0, -30, -2.0), 16)
    if k == 0:
        render("dj_wide_flat", eye, (0, -30, -2.0), 16, light="FLAT")
        render("dj_front_rows", eye, (0, -11, -1.6), 35)
        render("dj_front_rows_flat", eye, (0, -11, -1.6), 35, light="FLAT")
        render("closeup_front_row", *close, 40)
        render("closeup_front_row_flat", *close, 40, light="FLAT")
        render("side_front", (-24, -6.5, -0.6), (0, -14, -1.6), 28)
        render("aerial", (0, 20, 38), (0, -40, -2.5), 22, light="FLAT")
        ca = crowd.data.color_attributes["Col"]                 # night approximation: albedo x 0.05, glow full
        buf = np.empty(len(ca.data) * 4, dtype=np.float32)
        ca.data.foreach_get("color", buf)
        dim = buf.reshape(-1, 4).copy()
        dim[:, :3] *= 0.05
        ca.data.foreach_set("color", dim.ravel())
        render("dark_dj_wide", eye, (0, -30, -2.0), 16, light="FLAT")
        render("dark_closeup", *close, 40, light="FLAT")
        ca.data.foreach_set("color", buf)
c3.pose_preview([crowd, glow], None)


# ---------------------------------------------------------------- line-ups: every dance, the costumes / accessories
def lineup(name, specs, y0, t=0.3, spacing=1.45):
    rng_ = random.Random(7)
    ppl = []
    n = len(specs)
    for k, sp in enumerate(specs):
        x = (k - (n - 1) / 2) * spacing
        p = c3.make_person(rng_, 0.0, -30.0, sp.get("tier", "near"), "middle", yaw=0.0, clip=sp.get("clip", "sway"),
                           role="extra", force_costume=sp.get("costume"))
        p["x"], p["y"] = x, y0
        if sp.get("add"):
            p["parts"] = set(p["parts"]) | set(sp["add"])
        if sp.get("drop"):
            p["parts"] = set(p["parts"]) - set(sp["drop"])
        if sp.get("hand_black"):
            p["col"]["hand"] = (0.012, 0.012, 0.014)
        p["phase"], p["rate"] = 0.0, 1.0
        ppl.append(p)
        if sp.get("rider"):
            p["parts"] -= c3.CARRIER_DROP
            r = c3.make_person(rng_, x, y0 - 0.13, p["tier"], "middle", yaw=0.0, clip="ride", role="rider")
            r["sz"] = min(r["sz"], p["sz"])
            r["z"] = p["z"] + 1.48 * p["sz"] + 0.02 - 0.78 * r["sz"]
            r["parts"] = (r["parts"] - {"tutu", "phone", "glowstick"}) | {"pole", "flag"}
            r["phase"], r["rate"] = 0.0, 1.0
            ppl.append(r)
    arrays, _ = c3.assemble(ppl, last["canons"], last["vlay"])
    ob = c3.mesh_from_arrays(name, arrays["body"])
    gl = c3.mesh_from_arrays(name + "_glow", arrays["glow"])
    for o, kind in ((ob, "body"), (gl, "glow")):
        o.data.color_attributes.active_color = o.data.color_attributes["Col"]
        c3._POSE[o.name] = [None, arrays[kind]["vdata"]]
    c3.pose_preview([ob, gl], t, loop_rate=128.0 / 120.0)
    width = n * spacing + 1.0
    render(name, (0, y0 + 12.0, -0.55), (0, y0, -0.55), res=(2400, int(2400 * 2.9 / width)), ortho=width)
    for o in (ob, gl):
        o.hide_render = True


for o in (crowd, glow):
    o.hide_render = True
dances = [c for c in c3.CLIPS if c not in ("carry", "ride")]
lineup("lineup_dances_a", [{"clip": c, "add": {"phone"} if c == "hold" else set()} for c in dances[:8]], 40.0)
lineup("lineup_dances_b", [{"clip": c, "add": {"hoop"} if c == "flow" else set()} for c in dances[8:]], 40.0)
lineup("lineup_looks_a", [
    {"costume": "onesie", "clip": "jump"}, {"costume": "alien", "clip": "wave"},
    {"costume": "trex", "tier": "mid", "clip": "pump"}, {"clip": "carry", "rider": True},
    {"clip": "flow", "add": {"hoop"}}, {"clip": "flow", "add": {"poi"}}, {"clip": "flow", "add": {"staff"}},
    {"clip": "flow", "add": {"fan"}}], 40.0, spacing=1.7)
lineup("lineup_looks_b", [
    {"clip": "handsup", "add": {"gloves", "lightshoes", "necklace", "horns"}, "hand_black": True},
    {"clip": "heart", "add": {"tutu", "crown"}}, {"clip": "pump", "add": {"hat_cowboy", "cape"}},
    {"clip": "sway", "add": {"hat_bucket", "warmers", "pack"}}, {"clip": "nod", "add": {"hat_dome", "hat_brim", "goggles"}},
    {"clip": "twostep", "add": {"ears", "hair_long"}},
    {"clip": "jump", "tier": "mid"}, {"clip": "jump", "tier": "far"}], 40.0, spacing=1.6)
log("done")
