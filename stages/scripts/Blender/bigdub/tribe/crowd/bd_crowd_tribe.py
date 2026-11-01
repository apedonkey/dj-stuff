"""bd_crowd_tribe.py: BIG DUB's crowd for Tribe XR: the Tribe crowd v3 (HARVEST MOON's crowd/hm_crowd.py, copied here
as hm_crowd.py with its totems made festival ones) filling the Stone Circle in front of the Main Stage's barrier, each
dancer standing on the knoll's real ground. Blender 4.5, headless:

    blender -b --factory-startup --python-exit-code 1 --python bd_crowd_tribe.py -- [--target N] [--fast]

Inputs (make_site.sh): out/gen/tribe_site.json (the ring, the barrier, the FOH, the pillars and the flags in the Tribe frame)
and out/gen/tribe_ground.npy (the ground's z, Tribe frame cm). Outputs in out/crowd:
  SM_BdCrowd.fbx, SM_BdCrowdGlow.fbx   the bodies and the glowing bits (glowsticks, phones...), VAT data in UV1..UV5
  T_BdCrowdVAT.exr / .json             the dances (hm_crowd's VAT: 17 clips, 2048 x 1024 RGBA16F)
  T_BdCrowd.png                        the bodies' colour, baked on UV0 (albedo x a soft light from the stage's side; the
                                       material multiplies in BIG DUB's stage light, so the crowd takes the show's colours)
  walk_people.json                     every dancer's feet, Tribe frame cm, for the walking map's person lines
  crowd.log                            the [BDC] lines

Frames: hm_crowd builds in its kit's Blender frame (metres, the DJ at the origin, the crowd toward -Y); the FBX import
flips Y and build_bigdub.py stands the crowd's actor at yaw 180 (HARVEST MOON's convention), so a dancer at Blender
(x, y, z) stands at Tribe (-100 x, 100 y, 100 z). The ring is symmetric in x; the ground is not, so it is read at -x.
The rng-stream rule (claudedocs/christmas_stage_notes.md): the ground heights are an rng-free pass after the last draw.
"""
import json
import math
import os
import random
import sys
import time

import bpy
import numpy as np

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import hm_crowd as cm  # noqa: E402  (the copy in this folder)

TRIBE = os.path.normpath(os.path.join(HERE, ".."))
GEN = os.path.join(TRIBE, "out", "gen")
OUT = os.environ.get("BD_CROWD_OUT", os.path.join(TRIBE, "out", "crowd"))
ARGS = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
TARGET = int(ARGS[ARGS.index("--target") + 1]) if "--target" in ARGS else 1500
FAST = "--fast" in ARGS
SINK_M = 0.03                 # feet this far into the ground (the VRDJ crowd sinks 2 cm)
INNER = 0.93                  # the crowd stays inside this share of the stones' ellipse (the stones stand on 1.0)
TIERS = (("near", 10.0), ("mid", 16.0), ("far", 1e9))   # by distance from the DJ: 899 / 263 / 23 tris a dancer (v3)


def log(msg):
    print(f"[BDC {time.time() - T0:6.1f}s] {msg}", flush=True)


T0 = time.time()
site = json.load(open(os.path.join(GEN, "tribe_site.json")))
G = np.load(os.path.join(GEN, "tribe_ground.npy")).astype(np.float64)
GX0, GY0, GSTEP = site["grid"]["x0"], site["grid"]["y0"], site["grid"]["step"]
ring = site["ring"]
CX, CY = -ring["cx"] / 100.0, ring["cy"] / 100.0          # Blender metres (x mirrored; the ring is centred on x = 0)
RX, RY = ring["rb"] / 100.0, ring["ra"] / 100.0           # the ellipse's half-axes: across (x) and along (y)


def ground_z_cm(x_ue, y_ue):
    """The ground's z (Tribe frame cm) at Tribe (x, y) cm, bilinear on the 25 cm grid."""
    fx, fy = (x_ue - GX0) / GSTEP, (y_ue - GY0) / GSTEP
    i, j = int(math.floor(fx)), int(math.floor(fy))
    i = min(max(i, 0), G.shape[1] - 2)
    j = min(max(j, 0), G.shape[0] - 2)
    ax, ay = min(max(fx - i, 0.0), 1.0), min(max(fy - j, 0.0), 1.0)
    return float(G[j, i] * (1 - ax) * (1 - ay) + G[j, i + 1] * ax * (1 - ay) + G[j + 1, i] * (1 - ax) * ay
                 + G[j + 1, i + 1] * ax * ay)


# ---- the field: the ring in front of the barrier ------------------------------------------------------------------------
walls = site["Main"]["walls"]
barrier = [w for w in walls if (max(p[1] for p in w[0]) - min(p[1] for p in w[0])) < 20.0      # the crowd barrier:
           and -900.0 < min(p[1] for p in w[0]) < -400.0]                                         # 1 m steel sections
BARRIER_Y = min(min(p[1] for p in w[0]) for w in barrier) / 100.0     # its crowd-side face (m)
EDGE = cm.EDGE


def ell(x, y):
    return math.hypot(x / RX, (y - CY) / RY)


def ring_half(y):
    dy = (y - CY) / (RY * INNER)
    return RX * INNER * math.sqrt(1.0 - dy * dy) - EDGE if abs(dy) < 1.0 else -1.0


def in_field(x, y):
    return y <= cm.Y_MAX and ell(x, y) <= INNER - EDGE / RX


def edge_dist(x, y):
    """How far (m, roughly) a point is inside the crowd's ellipse: hm_crowd thins the crowd over the last FEATHER m."""
    return (INNER - ell(x, y)) * min(RX, RY)


cm.Y_MAX = BARRIER_Y - 0.40              # a low hand in "pump" reaches 0.48 m forward: keep it off the barrier's rail
cm.Y_FRONT = cm.Y_MAX - 0.20
cm.Y_BACK = CY - RY * INNER + EDGE
cm.FLOW_Y = cm.Y_MAX - 0.8
cm.FEATHER = 4.0
cm.field_half = ring_half
cm.in_field = in_field
cm.corn_dist = edge_dist
cm.under_beam = lambda x, y: False
cm.BEAM_C, cm.BEAM_R = (0.0, -1.0e6), 0.0
cm.TIERS = TIERS
# the FOH tent and its desks (Tribe x -270..270 cm, y -3618..-3202 cm) with room round it, in Blender metres
foh = [w for w in walls if min(p[1] for p in w[0]) < -3000.0 and min(p[1] for p in w[0]) > -3700.0]
fx0 = min(min(p[0] for p in w[0]) for w in foh) / 100.0 - 1.2
fx1 = max(max(p[0] for p in w[0]) for w in foh) / 100.0 + 1.2
fy0 = min(min(p[1] for p in w[0]) for w in foh) / 100.0 - 1.2
fy1 = max(max(p[1] for p in w[0]) for w in foh) / 100.0 + 1.2
cm.FOH_EXCLUDE = (-fx1, fy0, -fx0, fy1)
# the LED pillars out in the crowd, the flags round the ring (the decor's walls) and anything else standing in the ring
exclude = []
for w in walls + site["decor"]["walls"]:
    P = np.asarray(w[0], np.float64) / 100.0
    if P[:, 1].max() < BARRIER_Y and w not in foh and w not in barrier:
        pad = 0.9 if (np.ptp(P[:, 0]) > 1.0 or np.ptp(P[:, 1]) > 0.5) else 0.6
        exclude.append((-P[:, 0].max() - pad, P[:, 1].min() - pad, -P[:, 0].min() + pad, P[:, 1].max() + pad))
# the festival's crowd: no Thanksgiving costumes or winter hats; festival glow colours
cm.COSTUMES = {"alien": 0.55, "foil": 0.45}
cm.COSTUME_RATE = 0.05
cm.HAT_W = {None: 0.50, "cap": 0.26, "straw": 0.09, "foil": 0.05, "alien": 0.04, "beanie": 0.06}
cm.GLOW_COLS.update(cyan=(0.10, 0.85, 1.0), pink=(1.0, 0.18, 0.55), violet=(0.55, 0.20, 1.0))   # (green, gold, white
cm.GLOWS = [cm.GLOW_COLS[k] for k in ("cyan", "pink", "green", "violet")]                          # stay: named inside)
cm.GLOW_W = (0.30, 0.30, 0.22, 0.18)
log(f"ring centre ({-CX:.2f}, {CY:.2f}) m, half-axes {RX} x {RY} m (crowd inside {INNER}); barrier face y {BARRIER_Y:.2f} m; "
    f"FOH keep-out {tuple(round(v, 2) for v in cm.FOH_EXCLUDE)}; {len(exclude)} more keep-outs; target {TARGET}")

# ---- every dancer on the ground: an rng-free pass after build_people's last draw ----------------------------------------
_build_people = cm.build_people
GROUND_LOG = {}


def build_people_on_ground(rng, pts, extra, half_fn, tiers):
    people, roles = _build_people(rng, pts, extra, half_fn, tiers)
    zs = []
    for p in people:
        gz = ground_z_cm(-100.0 * p["x"], 100.0 * p["y"]) / 100.0
        p["z"] += gz - cm.GROUND_Z - SINK_M
        zs.append(gz)
    GROUND_LOG.update(n=len(zs), zmin=min(zs), zmax=max(zs))
    return people, roles


cm.build_people = build_people_on_ground

# ---- build -------------------------------------------------------------------------------------------------------------
os.makedirs(OUT, exist_ok=True)
for ob in list(bpy.data.objects):
    bpy.data.objects.remove(ob, do_unlink=True)
crowd, glow, _ = cm.build_crowd2(random.Random(11), exclude=exclude, extra=(), out_dir=OUT, target=TARGET,
                                 half_fn=ring_half, tiers=TIERS, vat_name="T_BdCrowdVAT")
log(f"ground under the dancers: z {GROUND_LOG['zmin']:.2f}..{GROUND_LOG['zmax']:.2f} m (Tribe frame; the DJ's floor is 0)")
crowd.name = crowd.data.name = "SM_BdCrowd"
glow.name = glow.data.name = "SM_BdCrowdGlow"
people = cm._LAST["people"]
tiers = {}
for p in people:
    tiers[p["tier"]] = tiers.get(p["tier"], 0) + 1
with open(os.path.join(OUT, "walk_people.json"), "w") as f:
    json.dump([[round(-100.0 * p["x"], 1), round(100.0 * p["y"], 1), round(100.0 * (cm.GROUND_Z + p["z"]), 1)] for p in people], f)
log(f"people {len(people)} by tier {tiers}; walk_people.json written")


def tris(ob):
    return sum(len(p.vertices) - 2 for p in ob.data.polygons)


# ---- the bodies' colour, baked on UV0 -----------------------------------------------------------------------------------
def bake_colour(ob, name, size, samples):
    mat = bpy.data.materials.new(name + "_bake")
    mat.use_nodes = True
    nt = mat.node_tree
    bsdf = nt.nodes["Principled BSDF"]
    attr = nt.nodes.new("ShaderNodeVertexColor")
    attr.layer_name = "Col"
    nt.links.new(attr.outputs["Color"], bsdf.inputs["Base Color"])
    bsdf.inputs["Roughness"].default_value = 0.85
    ob.data.materials.clear()
    ob.data.materials.append(mat)
    img = bpy.data.images.new(name, size, size, alpha=False, float_buffer=True)
    tx = nt.nodes.new("ShaderNodeTexImage")
    tx.image = img
    for n in nt.nodes:
        n.select = False
    tx.select = True
    nt.nodes.active = tx
    sc = bpy.context.scene
    sc.render.engine = "CYCLES"
    sc.cycles.samples = samples
    sc.cycles.device = "CPU"
    world = bpy.data.worlds.new("bake_world")
    world.use_nodes = True
    world.node_tree.nodes["Background"].inputs["Color"].default_value = (1.0, 1.0, 1.0, 1.0)
    world.node_tree.nodes["Background"].inputs["Strength"].default_value = 0.42     # the ambient share
    sc.world = world
    sun = bpy.data.lights.new("stage_key", "SUN")
    sun.energy = math.pi * 0.62                                  # a surface facing the stage: albedo x (0.42 + 0.62)
    sun.angle = math.radians(40.0)
    sun.cycles.cast_shadow = False                               # no dancer shadows the next one: the show lights them all
    so = bpy.data.objects.new("stage_key", sun)
    sc.collection.objects.link(so)
    # from the stage (Blender +Y), 35 degrees up: the light travels toward -Y and down
    so.rotation_euler = (math.radians(55.0), 0.0, math.radians(180.0))
    bpy.ops.object.select_all(action="DESELECT")
    ob.select_set(True)
    bpy.context.view_layer.objects.active = ob
    t = time.time()
    bpy.ops.object.bake(type="DIFFUSE", pass_filter={"DIRECT", "INDIRECT", "COLOR"}, margin=2, use_clear=True)
    px = np.empty(size * size * 4, dtype=np.float32)
    img.pixels.foreach_get(px)
    lin = px.reshape(size, size, 4)[:, :, :3]
    if lin.max() <= 0.0:
        raise RuntimeError(f"the bake of {ob.name} came out all black")
    srgb = np.where(lin <= 0.0031308, lin * 12.92, 1.055 * np.power(np.clip(lin, 0.0031308, None), 1 / 2.4) - 0.055)
    out = np.clip(srgb, 0.0, 1.0)
    rgba = np.concatenate([out, np.ones(out.shape[:2] + (1,), np.float32)], -1)
    img2 = bpy.data.images.new(name + "_png", size, size, alpha=True)
    img2.pixels.foreach_set(rgba.ravel())
    img2.filepath_raw = os.path.join(OUT, name + ".png")
    img2.file_format = "PNG"
    img2.save()
    log(f"baked {ob.name} -> {name}.png {size} px {samples} spp in {time.time() - t:.0f} s: linear mean {lin.mean():.4f}, "
        f"p99 {np.percentile(lin, 99):.3f}")


bake_colour(crowd, "T_BdCrowd", 1024 if FAST else 2048, 8 if FAST else 64)


def export_fbx(ob):
    """HARVEST MOON's export (hm_stage.export_fbx), so build_bigdub.py imports it as build_harvest.py does."""
    bpy.ops.object.select_all(action="DESELECT")
    ob.select_set(True)
    bpy.context.view_layer.objects.active = ob
    path = os.path.join(OUT, ob.name + ".fbx")
    bpy.ops.export_scene.fbx(filepath=path, use_selection=True, object_types={"MESH"}, apply_unit_scale=True,
                             apply_scale_options="FBX_SCALE_UNITS", axis_forward="-Z", axis_up="Y",
                             mesh_smooth_type="FACE", add_leaf_bones=False, bake_anim=False)
    log(f"fbx {os.path.basename(path)}: {len(ob.data.polygons)} faces, {tris(ob)} tris")


export_fbx(crowd)
export_fbx(glow)
meta = json.load(open(os.path.join(OUT, "T_BdCrowdVAT.json")))
log(f"done: {len(people)} people, tris bodies {tris(crowd)}, glow {tris(glow)}; VAT {meta['width']} x {meta['height']}, "
    f"uv channels {len(meta['uv_channels'])}, hat swaps {meta['hat_swaps']}, costumes {meta['costumes']}, hats {meta['hats']}")
