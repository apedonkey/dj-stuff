"""Drone reel clearance for GRAVEYARD SHIFT (plan phase 5 gate: "the reel plays through once with no clipping into
geometry"). Blender 4.5 headless, no render:

  blender -b --factory-startup --python hw_dronecheck.py -- <drone_path.txt> [<FBX dir, default out_hw>] [--min 0.5]

Reads the reel (tribemod/drone_path.txt syntax: "fly <s> <x,y,z> <x,y,z> [look=...]" and "orbit <s> [r=cm] [h=cm vs
head] [deg=sweep] [start=deg]", Tribe world cm, the DJ rig at the origin, crowd -Y) and every OPAQUE mesh of the stage
output (translucent beams, lasers, fog, fire, ghosts and bolts are not solid), then samples each segment's camera path:
the closest distance to any surface, and whether the path passes through one (ray cast between samples). FAIL (exit 1)
when a path crosses a surface or comes closer than --min metres. v7 (2026-10-11; the user: in one shot "it's behind a
building"): also the line of sight from each sample to what the shot looks at (look=, the DJ for orbits); FAIL when the
set hides it in more than --hidden (default 10) % of a shot. The crowd hiding it is reported, not failed. Tribe world (X, Y, Z) cm = Blender final frame
(-X, Y, Z) / 100 (our FBX import mirrors Y, the level turns 180 degrees). The giant hands count as raised (worst case).
"""
import math
import os
import re
import sys

import bpy
from mathutils import Vector
from mathutils.bvhtree import BVHTree

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "intro"))
import hw_intro_path as ip  # noqa: E402  (v5: the crypt doors' open pose)
ARGS = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
POS = [a for i, a in enumerate(ARGS) if not a.startswith("--") and (i == 0 or ARGS[i - 1] not in ("--min", "--hidden"))]
if not POS:
    sys.exit("usage: hw_dronecheck.py -- <drone_path.txt> [<FBX dir>] [--min 0.5]")
REEL = POS[0]
SRC = POS[1] if len(POS) > 1 else os.path.join(HERE, "out_hw")
MIN_M = float(ARGS[ARGS.index("--min") + 1]) if "--min" in ARGS else 0.5
HIDDEN_PCT = float(ARGS[ARGS.index("--hidden") + 1]) if "--hidden" in ARGS else 10.0
PEOPLE = {"SM_HwCrowd", "SM_HwPhones"}
NEAR_LOOK = 8.0                                   # m: a hit this close to the look point is what the shot frames
HEAD = Vector((0.06, 0.87, 1.7))                              # PlayerStartDJ (-6, 87) cm, eyes 1.7 m (hw_stage DJ_HEAD)
NOT_SOLID = {"SM_HwBeams", "SM_HwHalos", "SM_HwLasers", "SM_HwSearch", "SM_HwBolts", "SM_HwFire", "SM_HwFog",
             "SM_HwGhosts", "SM_HwSky", "SM_HwFarGround"}      # the sky and far ground are walls the reel never nears


def tribe(cm):
    x, y, z = (float(v) for v in cm.split(","))
    return Vector((-x / 100.0, y / 100.0, z / 100.0))


bpy.ops.wm.read_factory_settings(use_empty=True)
listed = [l.strip() for l in open(os.path.join(SRC, "manifest.txt")) if l.strip()]
verts, polys, owner = [], [], []
for mesh in listed:
    if mesh in NOT_SOLID or mesh.startswith(("SM_HwGBeams", "SM_HwGHalos")):
        continue
    fbx = os.path.join(SRC, mesh + ".fbx")
    if not os.path.exists(fbx):
        continue
    before = set(bpy.data.objects)
    bpy.ops.import_scene.fbx(filepath=fbx, axis_forward="-Z", axis_up="Y")
    for ob in [o for o in bpy.data.objects if o not in before and o.type == "MESH"]:
        mw = ob.matrix_world
        poses = [[mw @ v.co for v in ob.data.vertices]]
        if mesh == "SM_HwGate":                                  # v5: the crypt doors shut and open (intro.door_xy)
            poses.append([Vector((*ip.door_xy(1 if p.x > 0 else -1, p.x, p.y, 1.0), p.z)) for p in poses[0]])
        for pose in poses:
            off = len(verts)
            verts += pose
            for p in ob.data.polygons:
                polys.append([off + i for i in p.vertices])
                owner.append(mesh)
bvh = BVHTree.FromPolygons(verts, polys)
print(f"[DRONE] {len(owner)} solid faces from {len(set(owner))} meshes in {SRC}", flush=True)


def path_points(line):
    """(kind, seconds, [points], look target) for one reel line, Blender final frame."""
    tok = line.split()
    kind, secs = tok[0], float(tok[1])
    kv = dict(t.split("=", 1) for t in tok[2:] if "=" in t)
    look = HEAD if kv.get("look", "dj") == "dj" else tribe(kv["look"])
    if kind == "fly":
        a, b = tribe(tok[2]), tribe(tok[3])
        return kind, secs, [a.lerp(b, i / 400.0) for i in range(401)], look
    kv = dict(t.split("=", 1) for t in tok[2:] if "=" in t)
    r, h = float(kv.get("r", 260)) / 100.0, float(kv.get("h", 0)) / 100.0
    sweep, start = float(kv.get("deg", 360)), float(kv.get("start", -90))
    pts = []
    for i in range(401):
        th = math.radians(start + sweep * i / 400.0)
        pts.append(HEAD + Vector((-r * math.cos(th), r * math.sin(th), h)))   # Tribe (r cos, r sin, h) -> Blender
    return kind, secs, pts, HEAD


fails, total = [], 0.0
for n, raw in enumerate(open(REEL, encoding="utf-8"), 1):
    line = raw.split("#", 1)[0].strip()
    if not re.match(r"^(fly|orbit)\s", line):
        continue
    kind, secs, pts, look = path_points(line)
    total += secs
    near, near_at, near_mesh, cross = 1e9, None, "", None
    hid, by, people = 0, {}, 0
    for i, p in enumerate(pts):
        d = look - p
        q, left = p, d.length - 0.3                     # what stands between the camera and what it looks at
        while left > 0.05:
            hit = bvh.ray_cast(q, d.normalized(), left)
            if hit[0] is None:
                break
            m = owner[hit[2]]
            if (hit[0] - look).length < NEAR_LOOK:      # the framed thing itself (a look point on or behind the screen)
                break
            if m not in PEOPLE:
                hid += 1
                key = f"{m} near {hit[0].x:.0f},{hit[0].y:.0f},{hit[0].z:.0f}"
                by[key] = by.get(key, 0) + 1
                break
            people += 1 if q is p else 0
            left -= (hit[0] - q).length + 0.05
            q = hit[0] + d.normalized() * 0.05
        loc, _, idx, dist = bvh.find_nearest(p)
        if loc is not None and dist < near:
            near, near_at, near_mesh = dist, p, owner[idx]
        if i:
            d = p - pts[i - 1]
            hit = bvh.ray_cast(pts[i - 1], d.normalized(), d.length) if d.length > 1e-6 else (None,)
            if hit[0] is not None and cross is None:
                cross = (owner[hit[2]], hit[0])
    verdict = "ok"
    hid_pct, ppl_pct = 100.0 * hid / len(pts), 100.0 * people / len(pts)
    worst_by = max(by, key=by.get) if by else ""
    if cross:
        verdict = f"FAIL: passes through {cross[0]} at ({cross[1].x:.1f},{cross[1].y:.1f},{cross[1].z:.1f})"
    elif near < MIN_M:
        verdict = f"FAIL: {near:.2f} m from {near_mesh}"
    elif hid_pct > HIDDEN_PCT:
        verdict = f"FAIL: the set hides the view {hid_pct:.0f} % of the shot (mostly {worst_by})"
    if verdict != "ok":
        fails.append(f"line {n}: {verdict}")
    print(f"[DRONE] line {n:>2} {kind:<5} {secs:>4.0f} s: closest {near:6.2f} m ({near_mesh} near "
          f"{near_at.x:.1f},{near_at.y:.1f},{near_at.z:.1f}); view hidden {hid_pct:3.0f} %"
          + (f" ({worst_by})" if by else "") + f", by people {ppl_pct:3.0f} %  {verdict}", flush=True)
print(f"[DRONE] reel {total:.0f} s; minimum allowed {MIN_M:.2f} m", flush=True)
if fails:
    print("[DRONE] FAIL\n" + "\n".join("[DRONE]   " + f for f in fails), flush=True)
    sys.exit(1)
print("[DRONE] PASS: no segment passes through or near the set, and the set never hides a shot's view", flush=True)
