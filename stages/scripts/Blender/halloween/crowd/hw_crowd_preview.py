# Standalone preview + checks for the GRAVEYARD SHIFT crowd (Blender 4.5, headless; no stage, no bake):
#   D:\Tools\blender-4.5.14-windows-x64\blender.exe -b --factory-startup --python hw_crowd_preview.py --
#       [--grounds hw|dino|none] [--no-render] [--only name,name] [--seed 11]
# Renders need the shared GPU lock (C:\Users\Chris\TribeUE\gpu.lock.d): run_hw_crowd_preview.sh takes and frees it.
# Builds the crowd as hw_stage.py does (keep-outs and extra people from the grounds modules built with seed 1234, crowd
# seed 11) into ./previews ONLY (its own VAT .exr/.json there; never halloween/out_hw), then:
#   * checks the VAT decode (pages, frame-0 offsets, Unreal's 16-bit UVs) against direct skinning,
#   * measures what frame-0 offsets cost body types (a morphed vertex rides the canonical offsets),
#   * checks face winding on every tier superset (no face looks into its own shell; two-sided parts are matched pairs
#     wound opposite; decals face away from the surface they sit on) and on mirrored people,
#   * counts people, costumes, clips, half-time shares, tris per tier and per costume, VAT columns, UV0 island scale,
#   * renders Workbench views: from the DJ (studio and flat albedo), night (albedo x 0.05, glow at full) and show-wash
#     (albedo x 0.3) approximations, front-row close-ups, aerial, side; line-ups of the costumes (near / mid / far tier,
#     front and back, day and night), the accessories and totems, every dance; the costumes at 10 to 60 m.
# The look on the headset comes from the stage bake and the show, not from these.
import importlib
import math
import os
import random
import sys
import time
from collections import Counter

import bpy
import numpy as np
from mathutils import Matrix, Vector
from mathutils.bvhtree import BVHTree

HERE = os.path.dirname(os.path.abspath(__file__))
BL = os.path.dirname(os.path.dirname(HERE))                    # Scripts/Blender
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(BL, "grounds"))
ARGS = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []


def arg(name, default):
    return ARGS[ARGS.index(name) + 1] if name in ARGS else default


GROUNDS = arg("--grounds", "hw")
ONLY = set(arg("--only", "").split(",")) - {""}
SEED = int(arg("--seed", "11"))
PREV = os.path.join(HERE, "previews")
os.makedirs(PREV, exist_ok=True)
bpy.ops.wm.read_factory_settings(use_empty=True)
import hw_crowd as c3  # noqa: E402
scene = bpy.context.scene
DROP = 1.0                                                     # hw_stage lowers the crowd 1 m; the DJ floor stays at 0
LOOP = c3.HW_BPM / 120.0


def log(msg):
    print("[HWPREVIEW] " + msg, flush=True)


# ---------------------------------------------------------------- grounds: keep-outs and extra people
exclude, extra = [], []
if GROUNDS == "dino":
    names, mod_dir = ("vendors", "infrastructure", "landmarks", "atmosphere"), None
elif GROUNDS == "hw":
    mod_dir = os.path.join(os.path.dirname(HERE), "modules")
    names = sorted(f[:-3] for f in os.listdir(mod_dir)
                   if f.startswith("hw_") and f.endswith(".py") and f not in ("hw_example.py", "hw_preview.py"))
    sys.path.insert(0, mod_dir)
else:
    names = ()
loaded = []
for name in names:
    try:
        mod = importlib.import_module(name)
        if not hasattr(mod, "build"):                             # a tool next to the modules (a linter, ...)
            continue
        if hasattr(mod, "TOTEMS"):
            mod.TOTEMS = False
        res = mod.build(random.Random(1234))
        exclude += res.get("exclude", [])
        extra += res.get("people", [])
        loaded.append(f"{name}({len(res.get('people', []))})")
    except Exception as e:  # noqa: BLE001
        log(f"grounds {name} skipped: {e!r}")
for ob in list(bpy.data.objects):                              # grounds builders may leave objects: keep the scene clean
    bpy.data.objects.remove(ob)
log(f"grounds {GROUNDS}: {', '.join(loaded) or 'none'}; {len(exclude)} keep-outs, {len(extra)} extra people")

# ---------------------------------------------------------------- the crowd
t0 = time.time()
crowd, glow, _ = c3.build_crowd2(random.Random(SEED), exclude, extra, out_dir=PREV)
for ob in (crowd, glow):
    ob.data.transform(Matrix.Translation((0, 0, -DROP)))
meta = c3._VAT["meta"]
log(f"built in {time.time() - t0:.1f} s: {meta['people']} people, tris {meta['tris']}, VAT {meta['width']}x"
    f"{meta['height']}, tier columns {meta['tier_vertices']} (16-bit exact below 2048 per page)")
last = c3._LAST
canons = {c.tier: c for c in last["canons"]}
people = last["people"]
assert crowd.name == "SM_HwCrowd" and glow.name == "SM_HwPhones", (crowd.name, glow.name)
for ob in (crowd, glow):
    uvs = [u.name for u in ob.data.uv_layers]
    assert uvs == ["UVMap", "VatIndex", "VatRotScale", "VatScalePhase", "VatRate"], uvs
    assert "Col" in ob.data.color_attributes
for t, (pg, col0) in last["vlay"].items():
    assert col0 + len(canons[t].V) <= 2048, (t, pg, col0, len(canons[t].V))
log("mesh layout: SM_HwCrowd / SM_HwPhones, UV layers UVMap VatIndex VatRotScale VatScalePhase VatRate, Col; every page "
    "under 2048 columns")

# ---------------------------------------------------------------- people, costumes, clips, timing
field = [p for p in people if p["role"] in ("dancer", "carrier")]
cost = Counter(p["costume"] or "raver" for p in people)
log(f"people {len(people)}: field {meta['field_people']} + riders {meta['riders']} + extra {meta['extra_people']}; "
    f"costumed {meta['shares']['costumed_all'] * 100:.1f} % of all, {meta['shares']['costumed_field'] * 100:.1f} % of "
    f"the field; by costume {dict(cost.most_common())}")
for t in ("near", "mid", "far"):
    ct = Counter(p["costume"] or "raver" for p in people if p["tier"] == t)
    log(f"  {t}: {sum(ct.values())} people, {dict(ct.most_common())}")
log(f"half time: {meta['shares']['half_time_beat_clips'] * 100:.0f} % of beat-clip dancers, "
    f"{meta['shares']['half_time_groove_clips'] * 100:.0f} % of groove-clip dancers; clips {meta['clip_counts']}")
for zone, (y0, y1) in (("front", (-12.5, 0)), ("middle", (-32, -12.5)), ("back", (-200, -32))):
    zc = Counter(p["clip"] for p in field if y0 < p["y"] <= y1)
    n = sum(zc.values())
    log(f"  {zone} ({n}): " + ", ".join(f"{k} {v / n * 100:.0f}%" for k, v in zc.most_common(7)))
acc = Counter()
for p in people:
    for q in ("mask_led", "glow_eyes", "bucket", "witch_band", "horns", "ears", "glowstick", "phone", "skull", "ptotem",
              "cutout", "sign", "flag", "far_face", "far_lhand", "far_ttop", "far_hat", "far_pumpkin"):
        acc[q] += q in p["parts"]
log(f"accessories (people wearing / holding): {dict(acc)}")

# ---------------------------------------------------------------- budget: tris per tier and per costume, Unreal vertices
per_tier, per_cost = {}, {}
for p in people:
    c = canons[p["tier"]]
    ok = np.zeros(len(c3.PARTS), dtype=bool)
    ok[[c3.PART[q] for q in p["parts"] if q in c3.PART]] = True
    fm = ok[c.F_part]
    body, glw = int((c.F_len[fm & ~c.F_glow] - 2).sum()), int((c.F_len[fm & c.F_glow] - 2).sum())
    s = per_tier.setdefault(p["tier"], {"people": 0, "body": 0, "glow": 0})
    s["people"] += 1
    s["body"] += body
    s["glow"] += glw
    k = per_cost.setdefault((p["tier"], p["costume"] or "raver"), [0, 0])
    k[0] += 1
    k[1] += body + glw
for t in ("near", "mid", "far"):
    s = per_tier.get(t)
    if s:
        log(f"tier {t}: {s['people']} people, body {s['body']} tris ({s['body'] / s['people']:.0f}/person), glow "
            f"{s['glow']} tris ({s['glow'] / s['people']:.1f}/person)")
        log("   per costume (body+glow tris/person): " + ", ".join(
            f"{cn} {v[1] / v[0]:.0f}" for (tt, cn), v in sorted(per_cost.items()) if tt == t))


def ue_vertices(a, with_uv0=True):
    cols = [a["lvert"][:, None].astype(np.int64)]
    if with_uv0:
        cols.append(np.round(a["uv0"] * (1 << 20)).astype(np.int64))
    cols.append(np.round(a["col"][:, :3] * 4096).astype(np.int64))
    return len(np.unique(np.concatenate(cols, 1), axis=0))


ue = {"body": ue_vertices(last["arrays"]["body"]), "glow": ue_vertices(last["arrays"]["glow"], with_uv0=False)}
log(f"tris total {meta['tris']['body'] + meta['tris']['glow']} (body {meta['tris']['body']}, glow {meta['tris']['glow']});"
    f" Blender vertices {meta['blender_vertices']}, Unreal estimate (UV0 seams + colour borders) {ue}, total "
    f"{ue['body'] + ue['glow']}")

# ---------------------------------------------------------------- UV0: how big the body islands are in each cell
for t in ("near", "mid"):
    c = canons[t]
    fb = np.nonzero(c.F_part == c3.PART["b_torso"])[0]
    loops = np.nonzero(np.isin(c.L_face, fb))[0]
    span = c.L_uv[loops].max(0) - c.L_uv[loops].min(0)
    log(f"UV0 {t}: the torso island spans {span[0]:.3f} x {span[1]:.3f} of a person's cell")

# ---------------------------------------------------------------- check: face winding
GLOWR = c3.GLOW_REGIONS
TWO_SIDED = {"cape", "tutu", "hoop", "flag", "cutout", "collar", "tail_spade", "fan", "ears", "hat_brim", "hair_long"}
BRIMS = {"witch_hat", "hat_bucket", "hat_cowboy"}              # their near-horizontal faces low on the hat (the
BRIM_Z = c3.HC.z + 0.09                                        # brims) are pairs; the crown tops are not


def face_geo(V, polys):
    nrm, ctr = [], []
    for poly in polys:
        P = V[poly]
        n = np.zeros(3)
        for i in range(len(P)):                                # Newell normal
            a, b = P[i], P[(i + 1) % len(P)]
            n += np.array([(a[1] - b[1]) * (a[2] + b[2]), (a[2] - b[2]) * (a[0] + b[0]), (a[0] - b[0]) * (a[1] + b[1])])
        ln = np.linalg.norm(n)
        nrm.append(n / ln if ln > 1e-12 else n)
        ctr.append(P.mean(0))
    return np.array(nrm), np.array(ctr)


def winding_check(c, flip=()):
    """Per part (the superset overlaps parts nobody wears together, so each part is tested on its own faces): A: no
    face sees the back of its own shell along its normal; B: no two-sided pair is wound the same way (a back-face twin
    within 12 mm); C: a decal (a one-face shell with no twin) never faces its own part or the body within 15 mm; D:
    every face of a two-sided part (and of a brim) has a twin facing the other way. flip: faces to reverse first (the
    self-test)."""
    V = c.V
    vl = [tuple(v) for v in V]
    polys = [c.L_vert[c.F_start[f]:c.F_start[f] + c.F_len[f]].tolist() for f in range(len(c.F_len))]
    for f in flip:
        polys[f] = polys[f][::-1]
    parent = list(range(len(V)))

    def find(a):
        while parent[a] != a:
            parent[a] = parent[parent[a]]
            a = parent[a]
        return a
    for poly in polys:
        for v in poly[1:]:
            ra, rb = find(poly[0]), find(v)
            if ra != rb:
                parent[ra] = rb
    shell = [find(poly[0]) for poly in polys]
    nshell = Counter(shell)
    nrm, ctr = face_geo(V, polys)
    part = [c3.PARTS[i] for i in c.F_part]
    isglow = [r in GLOWR for r in c.F_reg]
    by_part = {}
    for f in range(len(polys)):
        by_part.setdefault(part[f], []).append(f)
    body = [f for f in range(len(polys)) if part[f].startswith("b_")]
    near_idx = {f: [] for f in range(len(polys))}               # twins: same part, centre within 15 mm, facing away
    for fs in by_part.values():
        for i, f in enumerate(fs):
            for g_ in fs[i + 1:]:
                if np.linalg.norm(ctr[g_] - ctr[f]) < 0.015 and nrm[g_] @ nrm[f] < -0.9:
                    near_idx[f].append(g_)
                    near_idx[g_].append(f)

    def same_shape(f, g_):
        if len(polys[f]) != len(polys[g_]):
            return False
        A, B = V[polys[f]], V[polys[g_]]
        return max(np.min(np.linalg.norm(B - a, axis=1)) for a in A) < 0.012
    def cast(bvh, fmap, o, n, maxd, skip):
        """The first hit along the ray that is not face `skip` (a non-planar polygon can hit itself)."""
        for _ in range(6):
            loc, nh, k, dist = bvh.ray_cast(o, n, maxd)
            if k is None:
                return None, None, None
            if fmap[k] != skip:
                return nh, fmap[k], dist
            o, maxd = loc + n * 1e-5, maxd - dist
        return None, None, None
    errs = Counter()
    examples = {}
    for pn, fs in by_part.items():
        own = BVHTree.FromPolygons(vl, [polys[f] for f in fs])
        ctx_f = fs + [f for f in body if part[f] != pn]
        ctx = BVHTree.FromPolygons(vl, [polys[f] for f in ctx_f])
        for f in fs:
            n = Vector(nrm[f])
            if n.length < 0.5:
                continue
            o = Vector(ctr[f]) + n * 1e-4
            nh, idx, dist = cast(own, fs, o, n, 2.0, f)
            if idx is not None and nh.dot(n) > 0.0:
                if shell[idx] == shell[f]:
                    errs["A"] += 1
                    examples.setdefault("A", []).append((pn, round(dist, 4)))
                elif dist < 0.012 and isglow[idx] == isglow[f] and same_shape(f, idx):
                    errs["B"] += 1
                    examples.setdefault("B", []).append((pn, round(dist, 4)))
            if nshell[shell[f]] == 1 and not near_idx[f] and not (c.tier == "far" and pn in c3.FAR_BILLBOARDS):
                nh, idx, dist = cast(ctx, ctx_f, o, n, 0.015, f)
                if idx is not None and nh.dot(n) < -0.5:
                    errs["C"] += 1
                    examples.setdefault("C", []).append((pn, part[idx], round(dist, 4)))
    pairs = {}
    for f, poly in enumerate(polys):
        if c.tier == "far" and part[f] in c3.FAR_BILLBOARDS:     # one-sided on purpose (flipped per clip)
            continue
        if part[f] in TWO_SIDED or (part[f] in BRIMS and abs(nrm[f][2]) > 0.6 and ctr[f][2] < BRIM_Z):
            t_ = pairs.setdefault(part[f], [0, 0])
            t_[0] += 1
            t_[1] += bool(near_idx[f])
    for pn, (tot, tw) in pairs.items():
        if tw < tot:
            errs["D"] += tot - tw
            examples.setdefault("D", []).append((pn, tot - tw, tot))
    return errs, examples, pairs


# the ray-cast normal must follow the winding (else the check means nothing): a quad seen from +Z, wound both ways
_q = BVHTree.FromPolygons([(0, 0, 0), (1, 0, 0), (1, 1, 0), (0, 1, 0)], [[0, 1, 2, 3]])
_r = BVHTree.FromPolygons([(0, 0, 0), (1, 0, 0), (1, 1, 0), (0, 1, 0)], [[3, 2, 1, 0]])
assert _q.ray_cast(Vector((0.5, 0.5, 1)), Vector((0, 0, -1)))[1].z > 0.9
assert _r.ray_cast(Vector((0.5, 0.5, 1)), Vector((0, 0, -1)))[1].z < -0.9
all_ok = True
for t in ("near", "mid", "far"):
    errs, ex, pairs = winding_check(canons[t])
    all_ok &= not errs
    log(f"face winding {t}: {sum(errs.values())} problems {dict(errs)} {ex if errs else ''}; two-sided parts "
        f"(faces with a twin / faces): " + ", ".join(f"{k} {v[1]}/{v[0]}" for k, v in sorted(pairs.items())))


def signed_volume(co, lstart, lvert):
    vol = 0.0
    ends = np.append(lstart[1:], len(lvert))
    for s_, e_ in zip(lstart, ends):
        P = co[lvert[s_:e_]]
        for i in range(1, len(P) - 1):
            vol += np.dot(P[0], np.cross(P[i], P[i + 1])) / 6.0
    return vol


vols = {1.0: [], -1.0: []}                                      # mirrored people keep outward faces (assemble reverses)
for m in (1.0, -1.0):
    rng_m = random.Random(5)
    for k in range(6):
        p = c3.make_person(rng_m, 0.0, -30.0, "near", "middle", yaw=0.0, clip="sway", role="extra",
                           force_costume=("raver", "skeleton", "pumpkin", "witch", "devil", "vampire")[k])
        p["mirror"] = m
        arr, _ = c3.assemble([p], last["canons"], last["vlay"])
        b = arr["body"]
        vols[m].append(signed_volume(b["co"] - b["co"].mean(0), b["lstart"], b["lvert"]))
log(f"signed volume of whole people (m^3; > 0 = outward faces): not mirrored {[round(v, 4) for v in vols[1.0]]}, "
    f"mirrored {[round(v, 4) for v in vols[-1.0]]}")
all_ok &= all(v > 0 for v in vols[1.0] + vols[-1.0])
cn = canons["near"]                                             # self-test: reversing known faces must be caught
pick = {}
for f in range(len(cn.F_len)):
    pn, rg = c3.PARTS[cn.F_part[f]], c3.REGIONS[cn.F_reg[f]]
    if pn == "pumpkin" and rg == "pumpkin":
        pick.setdefault("A", f)
    elif pn == "cape":
        pick.setdefault("B", f)
    elif pn == "mask_led":
        pick.setdefault("C", f)
st = {k: dict(winding_check(cn, flip=(f,))[0]) for k, f in pick.items()}
caught = all(st[k].get(k, 0) > 0 for k in pick)
log(f"face winding self-test (one face reversed -> the rule that must fire): {st}: {'caught' if caught else 'MISSED'}")
all_ok &= caught
log("face winding: " + ("OK" if all_ok else "PROBLEMS (see above)"))

# ---------------------------------------------------------------- check: VAT decode vs direct skinning; morph cost
rng = random.Random(3)
cache = {}


def canon_offset(tier, clip, frame):
    key = (tier, clip, frame)
    if key not in cache:
        c = canons[tier]
        cache[key] = c.posed(clip, (frame % c3.FRAMES) / c3.FRAMES) - c.posed(clip, 0.0)
    return cache[key]


for kind, ob in (("body", crowd), ("glow", glow)):
    worst = {"full": 0.0, "half": 0.0}
    ranges = last["arrays"][kind]["ranges"]
    sample = rng.sample(ranges, min(150, len(ranges)))
    base_all = last["arrays"][kind]["co"] + np.array([0.0, 0.0, -DROP])
    vdata_all = c3._POSE[ob.name][1]
    for t in (0.0, 0.37, 2.718, 61.3):
        for i, v0, uniq in sample:
            p = people[i]
            vd0 = vdata_all[v0:v0 + len(uniq)]
            cy, sy = math.cos(p["yaw"]), math.sin(p["yaw"])
            rot = np.array([[cy, -sy, 0], [sy, cy, 0], [0, 0, 1]]) @ np.diag([p["sx"] * p["mirror"], p["sx"], p["sz"]])
            base = base_all[v0:v0 + len(uniq)]
            for mode in ("full", "half"):
                vd = vd0.copy()
                if mode == "half":                              # Unreal's default 16-bit UVs (integers stay exact)
                    vd[:, 2:] = vd[:, 2:].astype(np.float16).astype(np.float64)
                rate, phase = float(vd[0, 6]), float(vd[0, 5])  # timing as the GPU sees it
                ph = (t * rate + phase) % 1.0 * c3.FRAMES
                f0 = int(math.floor(ph))
                a = ph - f0
                off = (1 - a) * canon_offset(p["tier"], p["clip"], f0) + a * canon_offset(p["tier"], p["clip"], f0 + 1)
                expect = base + off[uniq] @ rot.T
                got = base + c3.wpo_blender(vd, t, c3._VAT["tex_half"])
                worst[mode] = max(worst[mode], float(np.abs(got - expect).max()))
    log(f"VAT decode vs direct skinning ({kind}), {len(sample)} people x 4 times: max {worst['full'] * 100:.3f} cm "
        f"(full-precision UVs), {worst['half'] * 100:.3f} cm (16-bit UVs); clip index = page * {len(c3.CLIPS)} + clip, "
        f"pages {meta['pages']}")
morph_err = []
sample = rng.sample(last["arrays"]["body"]["ranges"], min(150, len(last["arrays"]["body"]["ranges"])))
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
    f"{np.percentile(me_, 95) * 100:.2f} cm, max {me_.max() * 100:.2f} cm; largest VAT offset {meta['max_offset_m']:.2f} m")
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


ground = flat_mesh("Ground", [(-110, 10, -2.52), (110, 10, -2.52), (110, -160, -2.52), (-110, -160, -2.52)],
                   (0.025, 0.022, 0.03))
flat_mesh("Deck", [(-25, -4.5, -1.0), (25, -4.5, -1.0), (25, 13.5, -1.0), (-25, 13.5, -1.0)], (0.04, 0.035, 0.05))
for ob in (crowd, glow):
    ob.data.color_attributes.active_color = ob.data.color_attributes["Col"]
scene.render.engine = "BLENDER_WORKBENCH"
scene.view_settings.view_transform = "Standard"
sh = scene.display.shading
sh.color_type, sh.show_backface_culling = "VERTEX", True
w = bpy.data.worlds.new("Night")
w.color = (0.008, 0.006, 0.014)
scene.world = w


def wanted(name):
    return not ONLY or any(name.startswith(o) for o in ONLY)


def render(name, loc, target, lens=35, res=(1920, 1080), light="STUDIO", ortho=None):
    if not wanted(name):
        return
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


class Dim:
    """Scale the albedo of the body objects (night: x 0.05; show wash: x 0.3); the glow objects stay at full."""

    def __init__(self, obs, k):
        self.obs, self.k, self.saved = obs, k, []

    def __enter__(self):
        for ob in self.obs:
            ca = ob.data.color_attributes["Col"]
            buf = np.empty(len(ca.data) * 4, dtype=np.float32)
            ca.data.foreach_get("color", buf)
            self.saved.append(buf)
            dim = buf.reshape(-1, 4).copy()
            dim[:, :3] *= self.k
            ca.data.foreach_set("color", dim.ravel())

    def __exit__(self, *a):
        for ob, buf in zip(self.obs, self.saved):
            ob.data.color_attributes["Col"].data.foreach_set("color", buf)


eye = (0.0, 0.3, 1.6)                                           # the DJ's eye (the DJ floor is z = 0)
close = ((1.5, -6.0, -0.9), (0.5, -10.0, -1.45))
for k, t in enumerate((0.30, 1.13)):
    c3.pose_preview([crowd, glow], t, loop_rate=LOOP)
    render(f"dj_wide_t{k}", eye, (0, -30, -2.0), 16)
    if k == 0:
        render("dj_wide_flat", eye, (0, -30, -2.0), 16, light="FLAT")
        render("dj_front_rows", eye, (0, -11, -1.6), 35)
        render("dj_front_rows_flat", eye, (0, -11, -1.6), 35, light="FLAT")
        render("dj_mid_field", eye, (0, -25, -1.6), 50)
        render("closeup_front_row", *close, 40)
        render("closeup_front_row_flat", *close, 40, light="FLAT")
        render("side_front", (-24, -6.5, -0.6), (0, -14, -1.6), 28)
        render("aerial", (0, 20, 38), (0, -40, -2.5), 22, light="FLAT")
        render("behind_crowd", (0, -75, 6.0), (0, -20, -1.0), 30)
        with Dim([crowd, ground], 0.05):
            render("dark_dj_wide", eye, (0, -30, -2.0), 16, light="FLAT")
            render("dark_front_rows", eye, (0, -11, -1.6), 35, light="FLAT")
            render("dark_mid_field", eye, (0, -25, -1.6), 50, light="FLAT")
            render("dark_closeup", *close, 40, light="FLAT")
        with Dim([crowd], 0.3):
            render("wash_dj_wide", eye, (0, -30, -2.0), 16, light="FLAT")
            render("wash_front_rows", eye, (0, -11, -1.6), 35, light="FLAT")
c3.pose_preview([crowd, glow], None)
for o in (crowd, glow):
    o.hide_render = True


# ---------------------------------------------------------------- line-ups
def make_lineup(name, specs, y0=40.0, t=0.3, spacing=1.45, yaw=0.0, xs=None):
    rng_ = random.Random(7)
    ppl = []
    n = len(specs)
    for k, sp in enumerate(specs):
        x = xs[k] if xs else (k - (n - 1) / 2) * spacing
        yy = sp.get("y", y0)
        for attempt in range(40):                               # re-roll until the wanted options show up
            p = c3.make_person(rng_, 0.0, -30.0, sp.get("tier", "near"), "middle", yaw=sp.get("yaw", yaw),
                               clip=sp.get("clip", "sway"), role="extra", force_costume=sp.get("costume", "raver"))
            if set(sp.get("need", ())) <= p["parts"]:
                break
        p["x"], p["y"] = x, yy
        if sp.get("add"):
            p["parts"] = set(p["parts"]) | set(sp["add"])
        if sp.get("drop"):
            p["parts"] = set(p["parts"]) - set(sp["drop"])
        p["phase"], p["rate"] = 0.0, 1.0
        ppl.append(p)
        if sp.get("rider"):
            p["parts"] -= c3.CARRIER_DROP
            r = c3.make_person(rng_, x, yy - 0.13, p["tier"], "middle", yaw=0.0, clip="ride", role="rider")
            r["sz"] = min(r["sz"], p["sz"])
            r["z"] = p["z"] + 1.48 * p["sz"] + 0.02 - 0.78 * r["sz"]
            r["parts"] = (r["parts"] - {"tutu", "phone", "glowstick"}) | {"pole", "skull"}
            r["phase"], r["rate"] = 0.0, 1.0
            ppl.append(r)
    arrays, _ = c3.assemble(ppl, last["canons"], last["vlay"])
    ob = c3.mesh_from_arrays(name, arrays["body"])
    gl = c3.mesh_from_arrays(name + "_glow", arrays["glow"])
    for o, kind in ((ob, "body"), (gl, "glow")):
        o.data.color_attributes.active_color = o.data.color_attributes["Col"]
        c3._POSE[o.name] = [None, arrays[kind]["vdata"]]
    c3.pose_preview([ob, gl], t, loop_rate=LOOP)
    return ob, gl


def lineup(name, specs, y0=40.0, t=0.3, spacing=1.45, yaw=0.0, night=False, back=False, height=3.0, zc=-0.5):
    if not wanted(name):
        return
    ob, gl = make_lineup(name, specs, y0, t, spacing, yaw)
    width = len(specs) * spacing + 1.0
    cam_y = y0 - 12.0 if back else y0 + 12.0
    res = (2400, int(2400 * height / width))
    if night:
        with Dim([ob], 0.05):
            render(name, (0, cam_y, zc), (0, y0, zc), res=res, ortho=width, light="FLAT")
    else:
        render(name, (0, cam_y, zc), (0, y0, zc), res=res, ortho=width)
    for o in (ob, gl):
        o.hide_render = True


COSTUME_SPECS = [
    {"costume": "skeleton", "clip": "headbang"}, {"costume": "witch", "clip": "claw", "need": ("cape", "witch_band")},
    {"costume": "zombie", "clip": "lurch"}, {"costume": "pumpkin", "clip": "pump"}, {"costume": "ghost", "clip": "wave"},
    {"costume": "devil", "clip": "pump", "need": ("cape", "tail")}, {"costume": "vampire", "clip": "claw",
                                                                      "need": ("cape", "collar")},
    {"costume": "mummy", "clip": "lurch", "need": ("glow_eyes",)}, {"costume": "cat", "clip": "sway", "need": ("tail",)},
    {"costume": "trex", "clip": "jump", "tier": "mid"}]
lineup("lineup_costumes_near", COSTUME_SPECS, spacing=1.7)
lineup("lineup_costumes_near_back", COSTUME_SPECS, spacing=1.7, back=True)
lineup("lineup_costumes_near_night", COSTUME_SPECS, spacing=1.7, night=True)
lineup("lineup_costumes_mid", [dict(sp, tier="mid") for sp in COSTUME_SPECS], spacing=1.7)
lineup("lineup_costumes_far", [dict(sp, tier="far" if sp["costume"] != "trex" else "mid") for sp in COSTUME_SPECS],
       spacing=1.7)
lineup("lineup_costumes_far_night", [dict(sp, tier="far" if sp["costume"] != "trex" else "mid") for sp in COSTUME_SPECS],
       spacing=1.7, night=True)
lineup("lineup_accessories", [
    {"clip": "handsup", "add": {"mask_led"}}, {"clip": "nod", "add": {"bucket"}}, {"clip": "hold", "add": {"pole", "skull"}},
    {"clip": "hold", "add": {"pole", "ptotem"}}, {"clip": "hold", "add": {"pole", "cutout"}},
    {"clip": "hold", "add": {"pole", "sign"}}, {"clip": "jump", "add": {"horns", "necklace", "glowstick"}},
    {"clip": "twostep", "add": {"ears", "lightshoes", "gloves"}}, {"clip": "carry", "rider": True}], spacing=1.8,
    height=6.4, zc=1.2)
lineup("lineup_accessories_night", [
    {"clip": "handsup", "add": {"mask_led"}}, {"clip": "nod", "add": {"bucket"}}, {"clip": "hold", "add": {"pole", "skull"}},
    {"clip": "hold", "add": {"pole", "ptotem"}}, {"clip": "hold", "add": {"pole", "cutout"}},
    {"clip": "hold", "add": {"pole", "sign"}}, {"clip": "jump", "add": {"horns", "necklace", "glowstick"}},
    {"clip": "twostep", "add": {"ears", "lightshoes", "gloves"}}, {"clip": "carry", "rider": True}], spacing=1.8,
    night=True, height=6.4, zc=1.2)
lineup("lineup_ravers", [{"clip": c} for c in ("jump", "pump", "handsup", "sway", "nod", "twostep", "wave", "clap")],
       spacing=1.5)
dances = [c for c in c3.CLIPS if c not in ("carry", "ride")]
lineup("lineup_dances_a", [{"clip": c, "add": {"phone"} if c == "hold" else set()} for c in dances[:8]])
lineup("lineup_dances_b", [{"clip": c, "add": {"hoop"} if c == "flow" else set()} for c in dances[8:]])
for name, tt in (("lineup_claw_lurch_t", 0.0),):                 # the new clips through their loop
    for k, tp in enumerate((0.0, 0.25, 0.5, 0.75)):
        lineup(f"{name}{k}", [{"costume": "zombie", "clip": "lurch"}, {"costume": "witch", "clip": "claw"},
                              {"costume": "skeleton", "clip": "claw"}, {"costume": "mummy", "clip": "lurch"}],
               t=tp / LOOP, spacing=1.8)


# ---------------------------------------------------------------- the costumes at 10 to 60 m from the DJ
def distance_rows(name, night):
    if not wanted(name):
        return
    rows = (("near", -10.0), ("mid", -16.0), ("far", -30.0), ("far", -45.0), ("far", -60.0))
    kinds = ["skeleton", "witch", "zombie", "pumpkin", "ghost", "devil", "vampire", "mummy", "cat", "raver"]
    specs, xs = [], []
    for tier, y in rows:
        for k, cn in enumerate(kinds):
            specs.append({"costume": cn, "tier": tier, "y": y, "clip": "sway", "yaw": 0.0})
            xs.append((k - (len(kinds) - 1) / 2) * (1.2 + 0.035 * -y))
    ob, gl = make_lineup(name, specs, xs=xs)
    for o in (ob, gl):                                           # stand them on the field (z = -2.5 after the drop)
        o.data.transform(Matrix.Translation((0, 0, -DROP)))
    if night:
        with Dim([ob, ground], 0.05):
            render(name, eye, (0, -30, -2.0), 24, light="FLAT")
    else:
        render(name, eye, (0, -30, -2.0), 24)
    for o in (ob, gl):
        o.hide_render = True


distance_rows("distance_rows", False)
distance_rows("distance_rows_night", True)
log("done")
