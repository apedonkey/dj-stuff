"""Big Dub concept blockout: an EEVEE night render of the real Four Quarters Farm terrain with the festival laid out on
it, so the layout, scale, slopes and sightlines can be judged before anything is built for real
(claudedocs/bigdub_stage_plan.md in the tribe hack repo).

Boxes, cones and capsules only; nothing here is pipeline output. Frame: the DEM crop frame from D:/TribeUE/bigdub_geo
(x east, y south, metres) turned into Blender's X east, Y north, Z = elevation - 230 m. Terrain = USGS 1 m LiDAR DEM,
land cover = masks.npz (field / woods / evergreen / water / road), stages and camps placed per the plan's landmark table.

    blender -b --factory-startup --python concept_blockout.py -- --out <dir> [--samples 24] [--views aerial,main_crowd,...]
"""
import json
import math
import os
import random
import sys
import time

import bpy
import numpy as np
from mathutils import Vector

ARGS = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []


def arg(name, default=None):
    return ARGS[ARGS.index(name) + 1] if name in ARGS and ARGS.index(name) + 1 < len(ARGS) else default


HERE = os.path.dirname(os.path.abspath(__file__))
GEO = arg("--geo", "D:/TribeUE/bigdub_geo")
OUT = os.path.abspath(arg("--out", os.path.join(HERE, "concept")))
SAMPLES = int(arg("--samples", "24"))
DAY = "--day" in ARGS                          # daylight pass: sun + sky, daytime palettes, no glow; labels_<view>.json for annotate.py
VIEWS = arg("--views", "aerial,aerial_top,main_stream,main_crowd,pavilion,newcamp,hemlock,bridge").split(",")
os.makedirs(OUT, exist_ok=True)
rng = random.Random(2026)
T0 = time.time()
Z0 = 230.0                                     # world z = elevation - Z0 (the main field sits around z 12..26)


def log(msg):
    print(f"[BIGDUB {time.time() - T0:6.1f}s] {msg}", flush=True)


# ------------------------------------------------------------------ terrain data
DEM = np.load(os.path.join(GEO, "dem_crop.npy")).astype(np.float32)          # [1800, 1600..2000] rows = y south, cols = x east
DEM = np.nan_to_num(DEM, nan=float(np.nanmin(DEM)))
H, W = DEM.shape
MK = np.load(os.path.join(GEO, "masks.npz"))
CLS, MSTEP = MK["cls"], int(MK["step"])        # 2 m cells


def elev(x, y):
    """bilinear elevation (metres above sea level) at crop-frame (x, y)"""
    x = min(max(x, 0.0), W - 1.001); y = min(max(y, 0.0), H - 1.001)
    i, j = int(y), int(x); fy, fx = y - i, x - j
    return float((DEM[i, j] * (1 - fx) + DEM[i, j + 1] * fx) * (1 - fy) + (DEM[i + 1, j] * (1 - fx) + DEM[i + 1, j + 1] * fx) * fy)


def cls_at(x, y):
    return int(CLS[min(int(y) // MSTEP, CLS.shape[0] - 1), min(int(x) // MSTEP, CLS.shape[1] - 1)])


def P(x, y, dz=0.0):
    """crop-frame (x, y) on the ground, dz metres above it -> Blender world"""
    return Vector((x, -y, elev(x, y) - Z0 + dz))


# ------------------------------------------------------------------ layout (the plan's landmark table; crop metres)
# yaw = the direction the stage FACES (the crowd side), degrees, 0 = +x east, 90 = north (-y)
STAGES = {
    "main":     dict(label="MAIN in the STONE CIRCLE (knoll, +-40 m)", x=1210, y=130, yaw=180, deck=(20, 10), led=(14, 6), crowd=2000, spread=(90, 60)),
    "pavilion": dict(label="PAVILION / HiScore (big dark roof)",     x=1072, y=76, yaw=-30, deck=(21, 9), led=(8, 4.5), crowd=450, spread=(35, 35), roof=True),
    "hemlock":  dict(label="HEMLOCK HOLE (beach on the elbow pool)", x=1140, y=570, yaw=60, deck=(12, 7), led=(7, 4), crowd=400, spread=(45, 40)),
    "newcamp":  dict(label="NEW CAMP (south landing, assumed)",      x=1060, y=650, yaw=-150, deck=(12, 7), led=(7, 4), crowd=450, spread=(50, 35)),
}
RING = (1147, 800, 12.0)                       # the Labyrinth: concentric mown rings, 25 m
STONE_CIRCLE = (1180, 130, 30.5, 24.5, -12.0)  # ellipse 200 x 160 ft on the knoll beside Camp Central; position +-40 m
BRIDGE = ((1110, 585), (1110, 640))            # Rainbow Bridge over the west run just downstream of the elbow pool, +-50 m along the run
CAMPS = {                                      # rect (x0, y0, x1, y1), tents per hectare, rv share
    "camp_central": (1020, 50, 1150, 130, 30, 0.0),
    "village_green_parking": (1150, 50, 1280, 100, 10, 0.6),
    "big_bottom": (960, 200, 1250, 520, 50, 0.0),
    "white_pines": (1040, 520, 1200, 590, 50, 0.0),
    "high_meadow": (1300, 330, 1500, 520, 35, 0.2),
    "hilltop": (1000, 700, 1240, 960, 30, 0.4),
    "rv_land": (1000, 1000, 1300, 1230, 20, 0.7),
    "old_forest": (330, 400, 1000, 840, 14, 0.0),
    "new_camp": (600, 900, 935, 1320, 25, 0.3),
    "new_camp_strip": (880, 1010, 930, 1320, 60, 0.0),
}
VENDOR_ROWS = [((1090, 110), (1150, 125)), ((1000, 230), (1120, 230)), ((1060, 540), (1150, 540)), ((895, 1100), (895, 1180))]
CAMPFIRES = [(1120, 110), (1050, 300), (1180, 450), (1120, 560), (1400, 440), (1150, 900), (1180, 1100), (900, 1250), (700, 600), (850, 750), (980, 700)]
SHUTTLE_STOPS = [(1130, 100), (960, 60), (1120, 585), (1150, 840)]

# ------------------------------------------------------------------ scene
bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
scene.render.engine = "BLENDER_EEVEE_NEXT"
scene.eevee.taa_render_samples = SAMPLES
scene.eevee.use_shadows = True
scene.eevee.use_raytracing = False
scene.render.resolution_x, scene.render.resolution_y = 1600, 900
scene.render.image_settings.file_format = "PNG"
scene.view_settings.view_transform = "Standard"
scene.view_settings.look = "None"
world = bpy.data.worlds.new("Day" if DAY else "Night"); scene.world = world; world.use_nodes = True
bg = world.node_tree.nodes["Background"]
bg.inputs[0].default_value = (0.45, 0.60, 0.90, 1.0) if DAY else (0.004, 0.007, 0.02, 1.0); bg.inputs[1].default_value = 0.7 if DAY else 1.0
if DAY: scene.view_settings.view_transform = "AgX"


def _mat(name):
    m = bpy.data.materials.new(name); m.use_nodes = True
    nt = m.node_tree; nt.nodes.clear(); return m, nt


def M_vcol(name, emit=0.0):
    """principled on the Col vertex colour, with the Glow colour attribute as emission"""
    m, nt = _mat(name)
    out = nt.nodes.new("ShaderNodeOutputMaterial"); bsdf = nt.nodes.new("ShaderNodeBsdfPrincipled")
    col = nt.nodes.new("ShaderNodeAttribute"); col.attribute_name = "Col"
    glow = nt.nodes.new("ShaderNodeAttribute"); glow.attribute_name = "Glow"
    bsdf.inputs["Roughness"].default_value = 0.92; bsdf.inputs["Specular IOR Level"].default_value = 0.1
    bsdf.inputs["Emission Strength"].default_value = emit
    nt.links.new(col.outputs["Color"], bsdf.inputs["Base Color"]); nt.links.new(glow.outputs["Color"], bsdf.inputs["Emission Color"])
    nt.links.new(bsdf.outputs[0], out.inputs[0]); return m


def M_emit(name, rgb, strength=1.0):
    m, nt = _mat(name)
    out = nt.nodes.new("ShaderNodeOutputMaterial"); e = nt.nodes.new("ShaderNodeEmission")
    e.inputs[0].default_value = (*rgb, 1.0); e.inputs[1].default_value = strength
    nt.links.new(e.outputs[0], out.inputs[0]); return m


def M_glow(name, rgb, strength, alpha):
    """a see-through emissive (beam cones): emission mixed with transparent, blended render method"""
    m, nt = _mat(name)
    out = nt.nodes.new("ShaderNodeOutputMaterial"); e = nt.nodes.new("ShaderNodeEmission"); t = nt.nodes.new("ShaderNodeBsdfTransparent")
    mix = nt.nodes.new("ShaderNodeMixShader"); mix.inputs[0].default_value = alpha
    e.inputs[0].default_value = (*rgb, 1.0); e.inputs[1].default_value = strength
    nt.links.new(t.outputs[0], mix.inputs[1]); nt.links.new(e.outputs[0], mix.inputs[2]); nt.links.new(mix.outputs[0], out.inputs[0])
    try: m.surface_render_method = "BLENDED"
    except Exception: m.blend_method = "BLEND"
    m.use_backface_culling = False; return m


def M_flat(name, rgb, rough=0.8):
    m, nt = _mat(name)
    out = nt.nodes.new("ShaderNodeOutputMaterial"); b = nt.nodes.new("ShaderNodeBsdfPrincipled")
    b.inputs["Base Color"].default_value = (*rgb, 1.0); b.inputs["Roughness"].default_value = rough
    nt.links.new(b.outputs[0], out.inputs[0]); return m


def M_visuals(name):
    """a VJ-loop stand-in on the LED walls: magenta/cyan diagonal stripes"""
    m, nt = _mat(name)
    out = nt.nodes.new("ShaderNodeOutputMaterial"); e = nt.nodes.new("ShaderNodeEmission")
    tc = nt.nodes.new("ShaderNodeTexCoord"); wave = nt.nodes.new("ShaderNodeTexWave"); ramp = nt.nodes.new("ShaderNodeValToRGB")
    wave.inputs["Scale"].default_value = 4.0; wave.inputs["Distortion"].default_value = 3.0
    ramp.color_ramp.elements[0].color = (1.0, 0.05, 0.6, 1); ramp.color_ramp.elements[1].color = (0.05, 0.8, 1.0, 1)
    nt.links.new(tc.outputs["UV"], wave.inputs["Vector"]); nt.links.new(wave.outputs["Fac"], ramp.inputs[0])
    nt.links.new(ramp.outputs["Color"], e.inputs[0]); e.inputs[1].default_value = 3.0
    nt.links.new(e.outputs[0], out.inputs[0]); return m


MAT_VCOL = M_vcol("Ground", emit=0.0 if DAY else 1.0)
MAT_TREE = M_vcol("Trees", emit=0.0)
MAT_STAGE = M_flat("Stage", (0.04, 0.04, 0.045))
MAT_TRUSS = M_flat("Truss", (0.25, 0.25, 0.27), 0.5)
MAT_LED = M_visuals("LED")
MAT_CROWD = M_vcol("Crowd", emit=0.0 if DAY else 1.0)
MAT_TENT = M_vcol("Tents", emit=0.0 if DAY else 1.0)
MAT_BEAM = M_glow("Beam", (0.6, 0.8, 1.0), 0.8, 0.025)
MAT_LASER = M_emit("Laser", (0.1, 1.0, 0.2), 6.0)
MAT_FIRE = M_emit("Fire", (1.0, 0.45, 0.1), 8.0)
MAT_RAINBOW = [M_emit(f"Rainbow{i}", c, 4.0) for i, c in enumerate([(1, 0, 0), (1, 0.5, 0), (1, 1, 0), (0, 1, 0), (0, 0.3, 1), (0.5, 0, 1)])]
MAT_WATER = M_flat("Water", (0.08, 0.22, 0.45) if DAY else (0.004, 0.012, 0.03), 0.55)
MAT_STONE = M_flat("Stone", (0.35, 0.33, 0.3), 0.9)


def new_mesh_obj(name, verts, faces, mats, col=None, glow=None):
    me = bpy.data.meshes.new(name); me.from_pydata(verts, [], faces); me.update()
    for m in mats: me.materials.append(m)
    if col is not None:
        a = me.color_attributes.new(name="Col", type="FLOAT_COLOR", domain="POINT"); a.data.foreach_set("color", np.asarray(col, np.float32).ravel())
    if glow is not None:
        a = me.color_attributes.new(name="Glow", type="FLOAT_COLOR", domain="POINT"); a.data.foreach_set("color", np.asarray(glow, np.float32).ravel())
    ob = bpy.data.objects.new(name, me); scene.collection.objects.link(ob); return ob


def set_face_mats(ob, mat_index_per_face):
    ob.data.polygons.foreach_set("material_index", np.asarray(mat_index_per_face, np.int32))


# ------------------------------------------------------------------ terrain mesh (4 m grid, vertex colours by land cover)
def build_terrain(step=4):
    ys = np.arange(0, H, step); xs = np.arange(0, W, step)
    gy, gx = np.meshgrid(ys, xs, indexing="ij")
    z = DEM[gy, gx] - Z0
    verts = np.stack([gx.astype(np.float32), -gy.astype(np.float32), z], axis=-1).reshape(-1, 3)
    ny, nx = gy.shape
    i = np.arange(ny - 1)[:, None] * nx + np.arange(nx - 1)[None, :]
    faces = np.stack([i, i + 1, i + nx + 1, i + nx], axis=-1).reshape(-1, 4)
    c = CLS[np.minimum(gy // MSTEP, CLS.shape[0] - 1), np.minimum(gx // MSTEP, CLS.shape[1] - 1)].ravel()
    pal = np.array([[0.42, 0.40, 0.18], [0.10, 0.28, 0.09], [0.05, 0.17, 0.07], [0.08, 0.20, 0.40], [0.55, 0.52, 0.48]] if DAY else
                   [[0.16, 0.15, 0.07], [0.025, 0.05, 0.02], [0.015, 0.035, 0.015], [0.01, 0.025, 0.05], [0.09, 0.09, 0.085]], np.float32)
    glow_pal = np.array([[0, 0, 0], [0, 0, 0], [0, 0, 0], [0.01, 0.03, 0.07], [0, 0, 0]], np.float32)
    # a touch of slope shading baked into the colour so the hillside reads even where the moon is flat
    gzy, gzx = np.gradient(z, step); shade = np.clip(1.0 - 2.5 * np.hypot(gzx, gzy), 0.45, 1.0).ravel()[:, None]
    col = np.concatenate([pal[c] * shade, np.ones((len(c), 1), np.float32)], axis=1)
    glow = np.concatenate([glow_pal[c], np.ones((len(c), 1), np.float32)], axis=1)
    ob = new_mesh_obj("Terrain", verts.tolist(), faces.tolist(), [MAT_VCOL], col, glow)
    ob.data.shade_smooth()
    log(f"terrain {len(verts)} verts {len(faces)} quads")


# ------------------------------------------------------------------ stage clearings: no trees inside the Stone Circle or any crowd fan
def in_clearing(x, y):
    cx, cy, ra, rb, rot = STONE_CIRCLE; a = math.radians(rot)
    ex, ey = x - cx, y - cy; u, v = ex * math.cos(a) + ey * math.sin(a), -ex * math.sin(a) + ey * math.cos(a)
    if (u / (ra + 18)) ** 2 + (v / (rb + 18)) ** 2 <= 1.0: return True
    for s in STAGES.values():
        yaw = math.radians(s["yaw"]); fx, fy = math.cos(yaw), -math.sin(yaw); rx, ry = -fy, fx
        dx, dy = x - s["x"], y - s["y"]; u, v = dx * fx + dy * fy, dx * rx + dy * ry
        depth, half = s["spread"]
        if -14 <= u <= s["deck"][1] + depth + 8 and abs(v) <= half + 8: return True
    return False


# ------------------------------------------------------------------ trees: one merged mesh of cones (evergreen) and crowns (deciduous)
def build_trees(core=(350, 60, 1800, 1550), core_pitch=7.0, far_pitch=16.0):
    V = []; F = []; C = []; n = 0
    def add_tree(x, y, kind):
        nonlocal n
        z = elev(x, y) - Z0
        if kind == 2:                                   # evergreen: trunk + cone
            h = rng.uniform(14, 22); r = rng.uniform(3.0, 4.5); col = (0.05, 0.18, 0.07) if DAY else (0.015, 0.04, 0.015)
            base = n; V.append((x, -y, z)); V.append((x, -y, z + h))
            k = 6
            for a in range(k):
                t = 2 * math.pi * a / k; V.append((x + r * math.cos(t), -y + r * math.sin(t), z + h * 0.25))
            for a in range(k):
                F.append((base + 2 + a, base + 2 + (a + 1) % k, base + 1)); F.append((base + 2 + (a + 1) % k, base + 2 + a, base))
            n += 2 + k; C.extend([col] * (2 + k))
        else:                                           # deciduous: trunk + a lumpy crown (octahedron)
            h = rng.uniform(11, 18); r = rng.uniform(4.0, 6.5); c0 = z + h * 0.45; col = (0.14, 0.34, 0.10) if DAY else (0.03, 0.065, 0.025)
            base = n; pts = [(x, -y, c0 - r * 0.6), (x, -y, z + h), (x + r, -y, c0), (x, -y + r, c0), (x - r, -y, c0), (x, -y - r, c0)]
            V.extend(pts); C.extend([col] * 6)
            for a in range(4):
                p, q = 2 + a, 2 + (a + 1) % 4
                F.append((base + p, base + q, base + 1)); F.append((base + q, base + p, base))
            n += 6
    x0, y0, x1, y1 = core
    for y in np.arange(0, H, far_pitch):
        for x in np.arange(0, W, far_pitch):
            incore = x0 <= x < x1 and y0 <= y < y1
            if incore: continue
            k = cls_at(x, y)
            if k in (1, 2) and rng.random() < 0.9: add_tree(x + rng.uniform(-6, 6), y + rng.uniform(-6, 6), k)
    for y in np.arange(y0, y1, core_pitch):
        for x in np.arange(x0, x1, core_pitch):
            k = cls_at(x, y)
            if k in (1, 2) and rng.random() < 0.85 and not in_clearing(x, y): add_tree(x + rng.uniform(-3, 3), y + rng.uniform(-3, 3), k)
    col = np.concatenate([np.asarray(C, np.float32), np.ones((len(C), 1), np.float32)], axis=1)
    glow = np.zeros((len(C), 4), np.float32); glow[:, 3] = 1
    new_mesh_obj("Trees", V, F, [MAT_TREE], col, glow)
    log(f"trees {len(V) // 7} approx, {len(F)} faces")


# ------------------------------------------------------------------ helpers for boxes etc.
def box(V, F, C, cx, cy, cz, sx, sy, sz, yaw=0.0, col=(0.5, 0.5, 0.5)):
    """axis box centred (cx, cy) at world z cz..cz+sz, turned by yaw about z; appends to V/F/C"""
    base = len(V); ca, sa = math.cos(yaw), math.sin(yaw)
    for dz in (0, sz):
        for dx, dy in ((-sx / 2, -sy / 2), (sx / 2, -sy / 2), (sx / 2, sy / 2), (-sx / 2, sy / 2)):
            V.append((cx + dx * ca - dy * sa, cy + dx * sa + dy * ca, cz + dz)); C.append(col)
    for a, b, c, d in ((0, 1, 2, 3), (4, 7, 6, 5), (0, 4, 5, 1), (1, 5, 6, 2), (2, 6, 7, 3), (3, 7, 4, 0)):
        F.append((base + a, base + b, base + c, base + d))


def capsule_person(V, F, C, x, y, z, col, h=1.75):
    box(V, F, C, x, y, z, 0.45, 0.3, h, rng.uniform(0, math.pi), col)


def finish(name, V, F, C, mat, glowC=None):
    col = np.concatenate([np.asarray(C, np.float32), np.ones((len(C), 1), np.float32)], axis=1)
    glow = np.concatenate([np.asarray(glowC if glowC is not None else C, np.float32) * (0.0 if glowC is None else 1.0), np.ones((len(C), 1), np.float32)], axis=1)
    return new_mesh_obj(name, V, F, [mat], col, glow)


# ------------------------------------------------------------------ stages
def build_stage(key, s):
    x, y, yaw = s["x"], s["y"], math.radians(s["yaw"])
    fx, fy = math.cos(yaw), -math.sin(yaw)               # facing direction in crop frame (x east, y south) -> yaw measured with north = 90
    fx, fy = math.cos(yaw), -math.sin(yaw)
    # in Blender world: X = x, Y = -y, so the facing vector is (fx, -fy) ... keep everything in crop frame then convert
    dw, dd = s["deck"]; lw, lh = s["led"]
    gz = elev(x, y) - Z0
    V = []; F = []; C = []
    # deck (1.5 m high), its back edge at the stage point, extends toward the crowd by dd
    cx, cy = x + fx * dd / 2, y + fy * dd / 2
    bl_yaw = math.atan2(-fy, fx)                           # yaw of the facing vector in Blender's XY
    box(V, F, C, cx, -cy, gz, dd, dw, 1.5, bl_yaw, (0.05, 0.05, 0.055))
    # towers and roof truss
    for side in (-1, 1):
        tx, ty = x + (-fy) * side * (dw / 2 + 1.5), y + fx * side * (dw / 2 + 1.5)
        box(V, F, C, tx, -ty, gz, 1.2, 1.2, 12.0, bl_yaw, (0.25, 0.25, 0.28))
        box(V, F, C, tx + fx * dd, -(ty + fy * dd), gz, 1.2, 1.2, 12.0, bl_yaw, (0.25, 0.25, 0.28))
    box(V, F, C, cx, -cy, gz + 11.2, dd + 2.0, dw + 4.5, 0.8, bl_yaw, (0.25, 0.25, 0.28))
    box(V, F, C, x + fx * (dd + 0.5), -(y + fy * (dd + 0.5)), gz + 11.2, 0.8, dw + 4.5, 0.8, bl_yaw, (0.25, 0.25, 0.28))
    if s.get("roof"):
        box(V, F, C, cx, -cy, gz + 12.0, dd + 4.0, dw + 6.0, 0.6, bl_yaw, (0.2, 0.16, 0.12))
    # DJ + booth at the back centre
    box(V, F, C, x + fx * 2.0, -(y + fy * 2.0), gz + 1.5, 0.8, 2.2, 0.9, bl_yaw, (0.08, 0.08, 0.09))
    capsule_person(V, F, C, x + fx * 1.2, -(y + fy * 1.2), gz + 1.5, (0.9, 0.9, 0.9))
    ob = finish(f"Stage_{key}", V, F, C, MAT_STAGE)
    # LED wall: a quad at the back edge facing the crowd
    lz0 = gz + 2.0
    rx, ry = -fy, fx                                       # right vector in crop frame
    pts = [(x + rx * lw / 2, y + ry * lw / 2), (x - rx * lw / 2, y - ry * lw / 2)]
    Vq = [(pts[0][0], -pts[0][1], lz0), (pts[1][0], -pts[1][1], lz0), (pts[1][0], -pts[1][1], lz0 + lh), (pts[0][0], -pts[0][1], lz0 + lh)]
    me = bpy.data.meshes.new(f"LED_{key}"); me.from_pydata(Vq, [], [(0, 1, 2, 3)]); me.update()
    uv = me.uv_layers.new(name="UVMap")
    for i, u in enumerate(((0, 0), (1, 0), (1, 1), (0, 1))): uv.data[i].uv = u
    me.materials.append(MAT_LED); ob2 = bpy.data.objects.new(f"LED_{key}", me); scene.collection.objects.link(ob2)
    # moving-head beams from the roof truss toward the crowd (emissive cones) + a laser fan
    Vb = []; Fb = []; Cb = []
    for i in range(8):
        t = (i + 0.5) / 8 - 0.5
        ox, oy = x + fx * (dd + 0.5) + rx * t * dw, y + fy * (dd + 0.5) + ry * t * dw
        tx, ty = ox + fx * rng.uniform(25, 60) + rx * rng.uniform(-30, 30), oy + fy * rng.uniform(25, 60) + ry * rng.uniform(-30, 30)
        beam_cone(Vb, Fb, Cb, (ox, -oy, gz + 11.0), (tx, -ty, elev(tx, ty) - Z0 + 1.0), 0.15, 1.4)
    # beam cones left out of the render: EEVEE drew the blended cones as grey wedges; the lasers carry the look here
    Vl = []; Fl = []; Cl = []
    for i in range(9):
        t = (i - 4) / 4
        ox, oy = x + fx * 1.0, y + fy * 1.0
        tx, ty = ox + fx * 80 + rx * t * 45, oy + fy * 80 + ry * t * 45
        beam_cone(Vl, Fl, Cl, (ox, -oy, gz + 11.5), (tx, -ty, elev(tx, ty) - Z0 + 2.5), 0.05, 0.05)
    finish(f"Lasers_{key}", Vl, Fl, Cl, MAT_LASER)
    # spot lamps lighting the crowd field (so the people read)
    for side in (-1, 1):
        lx, ly = x + fx * (dd + 0.5) + rx * side * dw / 3, y + fy * (dd + 0.5) + ry * side * dw / 3
        tx, ty = lx + fx * 30, ly + fy * 30
        spot(f"Wash_{key}{side}", (lx, -ly, gz + 11.0), (tx, -ty, elev(tx, ty) - Z0 + 1.0), (0.5, 0.6, 1.0), 6000, 70)
    # crowd: a fan of people in front, densest near the stage
    Vc = []; Fc = []; Cc = []
    depth, half = s["spread"]
    n = s["crowd"]; placed = 0; tries = 0
    while placed < n and tries < n * 20:
        tries += 1
        d = depth * (rng.random() ** 0.7); w = half * (0.35 + 0.65 * d / depth)
        px, py = x + fx * (dd + 2.0 + d) + rx * rng.uniform(-w, w), y + fy * (dd + 2.0 + d) + ry * rng.uniform(-w, w)
        if cls_at(px, py) == 3: continue                 # the fan is cleared of trees; only water is off limits
        pz = elev(px, py) - Z0
        glow = rng.random() < 0.25
        plain = rng.choice([(0.55, 0.5, 0.45), (0.25, 0.3, 0.55), (0.65, 0.65, 0.65), (0.2, 0.2, 0.22), (0.7, 0.4, 0.3)]) if DAY else (0.08, 0.07, 0.09)
        capsule_person(Vc, Fc, Cc, px, -py, pz, plain if not glow else rng.choice([(0.9, 0.1, 0.9), (0.1, 0.9, 1.0), (1.0, 0.5, 0.1), (0.2, 1.0, 0.3)]))
        placed += 1
    finish(f"Crowd_{key}", Vc, Fc, Cc, MAT_CROWD, glowC=[c if max(c) > 0.3 else (0, 0, 0) for c in Cc])
    log(f"stage {key}: {placed} people")


def beam_cone(V, F, C, a, b, r0, r1, k=6):
    base = len(V); a = Vector(a); b = Vector(b); d = (b - a)
    u = d.cross(Vector((0, 0, 1))); u = u.normalized() if u.length > 1e-6 else Vector((1, 0, 0)); v = d.normalized().cross(u)
    for i in range(k):
        t = 2 * math.pi * i / k; V.append(tuple(a + (u * math.cos(t) + v * math.sin(t)) * r0)); C.append((1, 1, 1))
    for i in range(k):
        t = 2 * math.pi * i / k; V.append(tuple(b + (u * math.cos(t) + v * math.sin(t)) * r1)); C.append((1, 1, 1))
    for i in range(k):
        j = (i + 1) % k; F.append((base + i, base + j, base + k + j, base + k + i))


def spot(name, pos, target, color, energy, angle_deg):
    L = bpy.data.lights.new(name, "SPOT"); L.energy = energy; L.color = color; L.spot_size = math.radians(angle_deg); L.spot_blend = 0.7
    L.shadow_soft_size = 1.0
    ob = bpy.data.objects.new(name, L); scene.collection.objects.link(ob); ob.location = pos
    ob.rotation_euler = (Vector(target) - Vector(pos)).to_track_quat("-Z", "Y").to_euler()


def point(name, pos, color, energy, radius=1.0):
    L = bpy.data.lights.new(name, "POINT"); L.energy = energy; L.color = color; L.shadow_soft_size = radius
    ob = bpy.data.objects.new(name, L); scene.collection.objects.link(ob); ob.location = pos


# ------------------------------------------------------------------ camps, vendors, landmarks
def build_camps():
    V = []; F = []; C = []; G = []
    for name, (x0, y0, x1, y1, per_ha, rv) in CAMPS.items():
        n = int((x1 - x0) * (y1 - y0) / 10000 * per_ha)
        for _ in range(n):
            x, y = rng.uniform(x0, x1), rng.uniform(y0, y1)
            if cls_at(x, y) in (3, 4): continue
            if cls_at(x, y) in (1, 2) and name not in ("hilltop", "old_forest") and rng.random() < 0.8: continue
            z = elev(x, y) - Z0
            if rng.random() < rv:
                box(V, F, C, x, -y, z, 7.5, 2.5, 3.0, rng.uniform(0, math.pi), (0.85, 0.85, 0.82) if DAY else (0.35, 0.35, 0.33)); G.extend([(0.05, 0.03, 0.0)] * 8)
            else:
                lit = rng.random() < 0.35
                c = rng.choice([(0.6, 0.6, 0.65), (0.2, 0.5, 0.2), (0.7, 0.35, 0.15), (0.2, 0.3, 0.65), (0.8, 0.7, 0.2)] if DAY else
                               [(0.12, 0.12, 0.14), (0.05, 0.1, 0.05), (0.12, 0.06, 0.03), (0.04, 0.06, 0.12)])
                box(V, F, C, x, -y, z, 2.6, 2.2, 1.5, rng.uniform(0, math.pi), c)
                G.extend([(0.6, 0.3, 0.05) if lit else (0, 0, 0)] * 8)
            # a camper or two next to it
            if rng.random() < 0.5:
                capsule_person(V, F, C, x + rng.uniform(-2, 2), -(y + rng.uniform(-2, 2)), z, (0.5, 0.45, 0.4) if DAY else (0.08, 0.07, 0.09)); G.extend([(0, 0, 0)] * 8)
    for (a, b) in VENDOR_ROWS:
        n = max(2, int(math.hypot(b[0] - a[0], b[1] - a[1]) / 9))
        for i in range(n):
            t = (i + 0.5) / n; x, y = a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t; z = elev(x, y) - Z0
            yaw = math.atan2(-(b[1] - a[1]), b[0] - a[0])
            box(V, F, C, x, -y, z, 6.0, 3.0, 3.2, yaw, (0.5, 0.45, 0.4)); G.extend([(0.0, 0.0, 0.0)] * 8)
            box(V, F, C, x, -y, z + 3.2, 5.0, 0.3, 0.8, yaw, (1, 1, 1)); G.extend([rng.choice([(1.0, 0.2, 0.6), (0.1, 0.9, 1.0), (1.0, 0.7, 0.1)])] * 8)
    for (x, y) in SHUTTLE_STOPS:
        z = elev(x, y) - Z0; box(V, F, C, x, -y, z, 3.0, 1.5, 2.6, 0, (0.3, 0.3, 0.35)); G.extend([(0.1, 0.4, 1.0)] * 8)
    finish("Camps", V, F, C, MAT_TENT, glowC=G)
    for (x, y) in ([] if DAY else CAMPFIRES):
        point(f"Fire_{x}_{y}", (x, -y, elev(x, y) - Z0 + 0.8), (1.0, 0.45, 0.12), 900, 0.6)
    log("camps built")


def build_landmarks():
    # the Stone Circle: 62 slabs on two-thirds of a 200 x 160 ft ellipse (the open third faces the stage), bare dirt floor
    cx, cy, ra, rb, rot = STONE_CIRCLE; V = []; F = []; C = []
    a = math.radians(rot)
    for i in range(62):
        t = math.radians(60 + 240 * i / 61)          # open third of the ring at t ~ 0 = east, where the stage stands
        ex, ey = ra * math.cos(t), rb * math.sin(t); x, y = cx + ex * math.cos(a) - ey * math.sin(a), cy + ex * math.sin(a) + ey * math.cos(a)
        box(V, F, C, x, -y, elev(x, y) - Z0, rng.uniform(0.8, 2.4), 0.4, rng.uniform(2.0, 4.2), t + a, (0.36, 0.30, 0.24))
    finish("StoneCircle", V, F, C, MAT_STONE)
    # the Rainbow Bridge: a 40 m span in six colour bands, over the creek
    (ax, ay), (bx, by) = BRIDGE; za = elev(ax, ay) - Z0 + 0.5; zb = elev(bx, by) - Z0 + 0.5
    for i in range(6):
        t0, t1 = i / 6, (i + 1) / 6
        V = []; F = []; C = []
        x0, y0, x1, y1 = ax + (bx - ax) * t0, ay + (by - ay) * t0, ax + (bx - ax) * t1, ay + (by - ay) * t1
        z = za + (zb - za) * (t0 + t1) / 2
        box(V, F, C, (x0 + x1) / 2, -(y0 + y1) / 2, max(z, 221.5 - Z0 + 1.0), math.hypot(x1 - x0, y1 - y0) + 0.3, 3.0, 0.3, math.atan2(-(y1 - y0), x1 - x0), (1, 1, 1))
        finish(f"Bridge{i}", V, F, C, MAT_RAINBOW[i])
    # creek water: a ribbon along the OSM centreline, 9 m wide, at the channel elevation
    creek = json.load(open(os.path.join(GEO, "creek_path.json")))["path"]; V = []; F = []; C = []
    pts = [(float(x), float(y)) for x, y, e in creek if 0 < x < W and 0 < y < H]
    for i in range(len(pts) - 1):
        (x0, y0), (x1, y1) = pts[i], pts[i + 1]; dx, dy = x1 - x0, y1 - y0; L = math.hypot(dx, dy)
        if L < 0.5: continue
        nx, ny = -dy / L * 4.5, dx / L * 4.5
        z = min(elev(x0, y0), elev(x1, y1)) - Z0 - 0.2
        base = len(V)
        V.extend([(x0 + nx, -(y0 + ny), z), (x0 - nx, -(y0 - ny), z), (x1 - nx, -(y1 - ny), z), (x1 + nx, -(y1 + ny), z)]); C.extend([(1, 1, 1)] * 4)
        F.append((base, base + 1, base + 2, base + 3))
    finish("Creek", V, F, C, MAT_WATER)
    log("landmarks built")


# ------------------------------------------------------------------ moon and cameras
def build_sky():
    if DAY:                                                # late-afternoon sun from the south-west, 45 deg up
        L = bpy.data.lights.new("Sun", "SUN"); L.energy = 3.5; L.color = (1.0, 0.96, 0.88); L.angle = math.radians(2.0)
        ob = bpy.data.objects.new("Sun", L); scene.collection.objects.link(ob)
        ob.rotation_euler = (math.radians(45), 0, math.radians(-125)); return
    L = bpy.data.lights.new("Moon", "SUN"); L.energy = 0.3; L.color = (0.55, 0.65, 1.0); L.angle = math.radians(1.0)
    ob = bpy.data.objects.new("Moon", L); scene.collection.objects.link(ob)
    ob.rotation_euler = (math.radians(55), 0, math.radians(-150))


def cam(name, pos, target, lens=24):
    c = bpy.data.cameras.new(name); c.lens = lens; c.clip_end = 6000
    ob = bpy.data.objects.new(name, c); scene.collection.objects.link(ob); ob.location = pos
    ob.rotation_euler = (Vector(target) - Vector(pos)).to_track_quat("-Z", "Y").to_euler(); return ob


def stage_view(key, dist_back, height, lens=22, behind=False):
    s = STAGES[key]; yaw = math.radians(s["yaw"]); fx, fy = math.cos(yaw), -math.sin(yaw)
    dd = s["deck"][1]
    if behind:                                             # Tribe's front camera: in front of the DJ, looking back at the DJ and the wall
        px, py = s["x"] + fx * (dd * 0.5 + 2.0), s["y"] + fy * (dd * 0.5 + 2.0); tx, ty = s["x"] + fx * 1.2, s["y"] + fy * 1.2
        return cam(f"cam_{key}_stream", P(px, py, 1.5 + 1.9), P(tx, ty, 1.5 + 1.4), lens)
    px, py = s["x"] + fx * (dd + dist_back), s["y"] + fy * (dd + dist_back)
    return cam(f"cam_{key}", P(px, py, height), P(s["x"], s["y"], 6.0), lens)


CAMS = {}


def build_cams():
    CAMS["aerial"] = cam("cam_aerial", P(1950, 1750, 600), P(1100, 600, 0), 26)
    CAMS["aerial_top"] = cam("cam_aerial_top", P(1050, 680, 1550), P(1050, 680, 0), 28)
    CAMS["core_top"] = cam("cam_core_top", P(1140, 330, 720), P(1140, 330, 0), 28)      # the stage core: tongue, elbow, both creek runs
    CAMS["aerial_main"] = cam("cam_aerial_main", P(1330, 330, 150), P(1180, 120, 20), 28)  # low oblique over the Big Bottom onto the knoll
    CAMS["main_side"] = cam("cam_main_side", P(1095, 215, 48), P(1195, 128, 6), 30)          # over the crowd's left shoulder onto the stage and stones
    CAMS["main_stream"] = stage_view("main", 0, 0, 20, behind=True)
    CAMS["main_crowd"] = stage_view("main", 45, 2.3, 18)
    CAMS["pavilion"] = stage_view("pavilion", 28, 2.3, 18)
    CAMS["newcamp"] = stage_view("newcamp", 30, 2.3, 18)
    CAMS["hemlock"] = stage_view("hemlock", 35, 2.3, 18)
    (ax, ay), (bx, by) = BRIDGE
    CAMS["bridge"] = cam("cam_bridge", P(bx - 20, by + 30, 12.0), P(ax, ay - 40, 4), 24)
    CAMS["stonecircle"] = cam("cam_stonecircle", P(1160, 140, 2.4), P(1210, 130, 6), 24)


# ------------------------------------------------------------------ build + render
build_terrain()
build_trees()
for k, s in STAGES.items(): build_stage(k, s)
build_camps()
build_landmarks()
build_sky()
build_cams()
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(OUT, "bigdub_blockout.blend"))
# labels for annotate.py: (text, crop x, crop y, metres above ground, kind)
LABELS = [("MAIN STAGE (Stone Circle)", 1210, 130, 14, "stage"), ("PAVILION (HiScore)", 1072, 76, 14, "stage"),
          ("HEMLOCK HOLE STAGE", 1140, 570, 12, "stage"), ("NEW CAMP STAGE", 1060, 650, 12, "stage"),
          ("Stone Circle", 1180, 130, 3, "place"), ("Rainbow Bridge", 1110, 612, 3, "place"), ("Labyrinth", 1147, 800, 1, "place"),
          ("Camp Office (farmhouse)", 1084, 1281, 4, "place"), ("PA 26 gate", 743, 1251, 2, "place"), ("Hemlock Hole (pool)", 1210, 555, 0, "place"),
          ("creek", 800, 300, 0, "place"), ("creek", 1430, 600, 0, "place"), ("creek gorge", 960, 900, 0, "place")]
for name, (x0, y0, x1, y1, per_ha, rv) in CAMPS.items():
    if name != "new_camp_strip": LABELS.append((name.replace("_", " ").title(), (x0 + x1) / 2, (y0 + y1) / 2, 2, "camp"))
from bpy_extras.object_utils import world_to_camera_view


def write_labels(v):
    camob = CAMS[v]; rx, ry = scene.render.resolution_x, scene.render.resolution_y; out = []
    for text, x, y, dz, kind in LABELS:
        w = P(x, y, dz); ndc = world_to_camera_view(scene, camob, w)
        out.append(dict(text=text, kind=kind, px=ndc.x * rx, py=(1 - ndc.y) * ry, depth=ndc.z, dist=(w - camob.location).length))
    json.dump(out, open(os.path.join(OUT, f"labels_{v}.json"), "w"), indent=1)


for v in VIEWS:
    if v not in CAMS: log(f"no view {v}"); continue
    scene.camera = CAMS[v]; scene.render.filepath = os.path.join(OUT, f"bigdub_concept_{v}.png")
    t = time.time(); bpy.ops.render.render(write_still=True); write_labels(v); log(f"rendered {v} in {time.time() - t:.1f}s")
log("done")
