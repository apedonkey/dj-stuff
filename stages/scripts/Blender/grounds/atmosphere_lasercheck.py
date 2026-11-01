"""Checks the atmosphere module's sweeping lasers v2 (Blender 4.5, headless, CPU only):

  blender.exe -b --factory-startup --python grounds/atmosphere_lasercheck.py

1. UV contract on the built "lasers" mesh: layers "UVMap", "LaserPivot", "LaserPivotZPhase", "LaserAmp", "LaserCue",
   "LaserFix" in that order; every beam's loops carry its pivot / phase / amplitudes / (group, u) / (x, 0)
   (atmosphere.LASERS), every unit's aperture glow its pivot / (0, 0) / (group, 0) / (x, 1); every beam's apex sits
   LASER_GAP from its unit's aperture, and the aperture on the housing's face (the beams leave the units).
2. Sweep safety over the pattern engine's whole range (dino_materials.laser_show clamps pan P and tilt Q to -1..1, and
   the material turns each beam by pan_amp * P, tilt_amp * Q about its unit's aperture; atmosphere.laser_pose_pq is the
   same math): a 13 x 7 grid of (P, Q) incl. the corners, per beam. Distance to the DJ's head (0, 0, 2.6) and to the
   giant intro's raised head (0, 1.2, 8.0), lowest point vs the crowd floor, clearance to the stage meshes (../out FBX,
   nearest surface along the beam past its own unit), the stage fan over the barrier row and the first flags.
"""
import math
import os
import sys

import bpy
from mathutils import Vector
from mathutils.bvhtree import BVHTree

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import atmosphere as A  # noqa: E402
import kit  # noqa: E402

STAGE_OUT = os.environ.get("DINO_OUT") or os.path.join(os.path.dirname(HERE), "out_v81")   # the live stage's bake
                                                   # (v8.1+; out/ is a stale v6.3 bake); DINO_OUT: another one
DROP = 1.0                                                  # the FBX context is post-drop; the module is pre-drop
HEAD = Vector((0, 0, 2.6))
GIANT_HEAD = Vector((0, 1.2, 8.0))                          # the DJ raised by the giant intro (pre-drop)
SOLID = ("SM_DinoStructure", "SM_DinoRig", "SM_DinoVisualScreen", "SM_DinoScreen", "SM_DinoDeck", "SM_DinoPillars",
         "SM_DinoRiser", "SM_DinoBooth", "SM_DinoBulbs", "SM_DinoEyes", "SM_DinoLenses", "SM_DinoPlants",
         "SM_DinoGroundsStagedeck")
CROWD_STRUCT = ("SM_DinoGroundsInfrastructure",)   # FOH, delay towers, masts, barricades: reported (beams passing them)
CROWD = ("SM_DinoCrowd", "SM_DinoFlags")


def log(msg):
    print("[LASERCHECK] " + msg, flush=True)


# ------------------------------------------------------------------ 1. UV contract
res = A.build(__import__("random").Random(1234))
assert len(res["lasers"]) == 1, len(res["lasers"])
bm = res["lasers"][0]
names = [lay.name for lay in bm.loops.layers.uv]
assert names == ["UVMap", *A.LASER_UV], names
bm.faces.ensure_lookup_table()
n_beams, n_units = len(A.LASERS), len(A.LASER_UNITS)
assert len(bm.faces) == 2 * n_beams + n_units, (len(bm.faces), n_beams, n_units)
lays = [bm.loops.layers.uv[n] for n in A.LASER_UV]
bad = 0


def check(faces, want):
    global bad
    for f in faces:
        for lp in f.loops:
            for lay, w in zip(lays, want):
                got = lp[lay].uv
                if abs(got[0] - w[0]) > 1e-4 or abs(got[1] - w[1]) > 1e-4:
                    bad += 1


for i, b in enumerate(A.LASERS):
    p = b["pivot"]
    check(bm.faces[2 * i:2 * i + 2], ((p.x, p.y), (p.z, b["phase"]), (b["pan"], b["tilt"]), (b["cue"], b["u"]),
                                       (b["x"], 0.0)))
    apex = min((v.co for f in bm.faces[2 * i:2 * i + 2] for v in f.verts), key=lambda c: (c - p).length)
    if abs((apex - p).length - math.hypot(A.LASER_GAP, A.BEAM_W[0] / 2)) > 1e-3:
        bad += 1
for k, un in enumerate(A.LASER_UNITS):
    p = un["pivot"]
    check([bm.faces[2 * n_beams + k]], ((p.x, p.y), (p.z, 0.0), (0.0, 0.0), (un["group"], 0.0), (un["x"], 1.0)))
    face_gap = (p - un["center"]).dot(un["f"]) - A.UNIT_BOX[0] / 2      # aperture vs the housing's front face
    if not 0.0 < face_gap < 0.02:
        bad += 1
groups = {}
for b in A.LASERS:
    groups[b["group"]] = groups.get(b["group"], 0) + 1
log(f"contract: layers {names}; {n_beams} beams + {n_units} aperture glows = {len(bm.faces)} quads, "
    f"{len(bm.verts)} verts; beams per group {dict(sorted(groups.items()))}; mismatches {bad}")
assert bad == 0, bad
quads = {k: sum(len(m.faces) for m in res[k]) for k in ("beams", "lasers", "halos")}
log(f"quads: {quads}; lit tris {sum(kit.tris(m) for m, _ in res['lit'])}, glow tris {kit.tris(res['glow'][0])}")

# ------------------------------------------------------------------ stage + crowd BVH (post-drop -> pre-drop)
bpy.ops.wm.read_factory_settings(use_empty=True)


def load_bvh(names, extra=(), keep=lambda c: True):
    """The meshes of the bake (post-drop, lifted back) plus the faces of `extra` bmeshes (already pre-drop: this
    module's own housings, road cases and trackers) whose centroid passes `keep`."""
    verts, polys = [], []
    for m in extra:
        m.verts.index_update()
        for f in m.faces:
            if not keep(f.calc_center_median()):
                continue
            off = len(verts)
            verts += [v.co.copy() for v in f.verts]
            polys.append(list(range(off, off + len(f.verts))))
    for name in names:
        path = os.path.join(STAGE_OUT, name + ".fbx")
        if not os.path.exists(path):
            continue
        before = set(bpy.data.objects)
        bpy.ops.import_scene.fbx(filepath=path, axis_forward="-Z", axis_up="Y")
        for ob in [o for o in bpy.data.objects if o not in before and o.type == "MESH"]:
            off = len(verts)
            verts += [(ob.matrix_world @ v.co) + Vector((0, 0, DROP)) for v in ob.data.vertices]
            polys += [[off + i for i in p.vertices] for p in ob.data.polygons]
    return BVHTree.FromPolygons(verts, polys), len(polys)


CROWD_Y = -15.0                                            # this module's parts out in the crowd (the delay-tower units)
stage_bvh, n_stage = load_bvh(SOLID, extra=[m for m, _ in res["lit"]], keep=lambda c: c.y > CROWD_Y)
crowd_bvh, n_crowd = load_bvh(CROWD)
infra_bvh, n_infra = load_bvh(CROWD_STRUCT, extra=[m for m, _ in res["lit"]], keep=lambda c: c.y <= CROWD_Y)
log(f"context: {n_stage} stage faces, {n_crowd} crowd faces, {n_infra} crowd-structure faces")


# ------------------------------------------------------------------ 2. sweep over the engine's range
def posed(b, P, Q):
    """Apex and end of beam b at the engine's pan P and tilt Q (-1..1)."""
    p = b["pivot"]
    return [A.laser_pose_pq(q, p, P, Q, b["pan"], b["tilt"])
            for q in (p + b["d"] * A.LASER_GAP, p + b["d"] * b["length"])]


def seg_dist(pt, a, e):
    ab = e - a
    t = max(0.0, min(1.0, (pt - a).dot(ab) / ab.length_squared))
    return (a + ab * t - pt).length, t


def clearance(a, e, step=0.5, skip=1.0):
    """Smallest gap between the beam's edge and a stage surface (m) and the surface point, sampled along the center
    line from `skip` m out (the first meter is the unit's own housing, horn tip or truss)."""
    best, where, L = 9.0, None, (e - a).length
    n = max(2, int(L / step))
    for i in range(n + 1):
        t = i / n
        if t * L < skip:
            continue
        q = a.lerp(e, t)
        hit = stage_bvh.find_nearest(q, 3.0)
        if hit[0] is not None:
            w = A.BEAM_W[0] + (A.BEAM_W[1] - A.BEAM_W[0]) * t
            if hit[3] - w / 2 < best:
                best, where = hit[3] - w / 2, hit[0]
    return best, where


grid = [(pf, tf) for pf in [i / 6 - 1 for i in range(13)] for tf in [j / 3 - 1 for j in range(7)]]
stats = {}
for b in A.LASERS:
    st = stats.setdefault(b["unit"], {"head": 9e9, "giant": 9e9, "floor": 9e9, "clear": 9e9, "reach": 0, "n": 0,
                                      "crowd": 0, "front": 9e9, "flags": 9e9, "where": None, "len": [], "infra": 0})
    st["len"].append(b["length"])
    for P, Q in grid:
        a, e = posed(b, P, Q)
        d, t = seg_dist(HEAD, a, e)
        st["head"] = min(st["head"], d - (A.BEAM_W[0] + (A.BEAM_W[1] - A.BEAM_W[0]) * t) / 2)
        d, t = seg_dist(GIANT_HEAD, a, e)
        st["giant"] = min(st["giant"], d - (A.BEAM_W[0] + (A.BEAM_W[1] - A.BEAM_W[0]) * t) / 2)
        st["floor"] = min(st["floor"], min(a.z, e.z) - A.BEAM_W[1] / 2)
        c, where = clearance(a, e)
        if c < st["clear"]:
            st["clear"], st["where"] = c, where
        st["reach"] += e.z < A.LAND_Z
        st["n"] += 1
        if crowd_bvh.ray_cast(a, (e - a).normalized(), (e - a).length)[0] is not None:
            st["crowd"] += 1
        if infra_bvh.ray_cast(a, (e - a).normalized(), (e - a).length)[0] is not None:
            st["infra"] += 1
        if b["group"] == 0:                                     # fan height over the barrier row and the first flags
            for y, kk in ((-8.25, "front"), (-12.0, "flags")):
                if (a.y - y) * (e.y - y) < 0:
                    z = a.z + (e.z - a.z) * (a.y - y) / (a.y - e.y)
                    st[kk] = min(st[kk], z)

for ui, st in sorted(stats.items()):
    un = A.LASER_UNITS[ui]
    p = un["pivot"]
    extra = f"; fan z at y -8.25 >= {st['front']:.2f}, at y -12 >= {st['flags']:.2f}" if un["group"] == 0 else ""
    log(f"{un['name']:12s} g{un['group']} x {un['x']:.2f} pivot ({p.x:6.2f},{p.y:6.2f},{p.z:5.2f}) {un['n']} beams "
        f"{min(st['len']):.0f}-{max(st['len']):.0f} m: DJ head gap >= {st['head']:.1f} m (giant {st['giant']:.1f}); "
        f"lowest z {st['floor']:.2f} (floor {kit.GROUND_Z}); stage clearance >= {st['clear']:.2f} m; "
        f"ends below head height {st['reach'] / st['n']:.0%}, crowd hit {st['crowd'] / st['n']:.0%}, "
        f"crosses FOH/towers/masts {st['infra'] / st['n']:.0%}{extra}"
        + (f"; closest stage point ({st['where'].x:.1f},{st['where'].y:.1f},{st['where'].z:.1f})"
           if st["where"] is not None and st["clear"] < 0.5 else ""))
worst = {k: min(st[k] for st in stats.values()) for k in ("head", "giant", "floor", "clear")}
log(f"all lasers: DJ head gap >= {worst['head']:.1f} m (raised giant >= {worst['giant']:.1f} m), lowest point z "
    f">= {worst['floor']:.2f} (floor {kit.GROUND_Z}), stage clearance >= {worst['clear']:.2f} m")
ok = worst["head"] > 1.0 and worst["giant"] > 1.0 and worst["floor"] > kit.GROUND_Z + 0.2 and worst["clear"] > 0.05
log("RESULT " + ("PASS" if ok else "FAIL"))
