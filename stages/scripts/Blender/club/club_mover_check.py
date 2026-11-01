"""v7 export check (2026-10-09; the club's copy of the Dino session's checks/mover_fbx_check.py): the moving heads' meshes
as exported. Each must carry UVMap + the five data layers (club_movers.LASER_UV) and every vertex its own fixture's values
(club_moves.json, written by club_stage.build_rig; yokes: tilt 0); the UE material's emulated move (dm._mover_wpo: the
FBX import's Y flip and V flip, the level's yaw 180) must equal club_movers.mover_pose_pq for every vertex; and no beam,
in any pose of the engine's sweep, may come within CLEAR_M of the DJ's eyes.
Usage: blender -b --factory-startup --python club_mover_check.py -- <out dir>"""
import json
import math
import os
import sys

import bpy
import numpy as np
from mathutils import Vector

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import club_layout as L  # noqa: E402
import club_movers as CM  # noqa: E402

out = sys.argv[sys.argv.index("--") + 1]
MOVES = json.load(open(os.path.join(out, "club_moves.json")))         # [[group, five values]] per fixture
GROUPS = [m[0] for m in MOVES]
VALS = [tuple(tuple(v) for v in m[1]) for m in MOVES]
known = np.array([[v[0][0], v[0][1], v[1][0]] for v in VALS])
NAMES = ("UVMap",) + CM.LASER_UV
YAW180 = np.diag([-1.0, -1.0, 1.0])                                    # build_club: screen at -Y -> level yaw 180
Z = np.array([0.0, 0.0, 1.0])
CLEAR_M = 1.0                                                          # beam edge to the DJ's eyes, any pose
MESHES = {"SM_ClubMoverHeads": (None, 0.6), "SM_ClubLenses": (None, 0.6)}
for g_ in ("Hall", "Bay", "Floor"):
    MESHES["SM_ClubBeams" + g_] = (g_, 45.0)
    MESHES["SM_ClubHalos" + g_] = (g_, 1.3)
fail = []


def rot(axis, angle, pivot, pos):
    closest = pivot + axis * np.sum(axis * (pos - pivot), 1, keepdims=True)
    U = pos - closest
    return closest + U * np.cos(angle)[:, None] + np.cross(axis, U) * np.sin(angle)[:, None] - pos


bpy.ops.wm.read_factory_settings(use_empty=True)
beam_data = {}
for name, (grp, lim) in MESHES.items():
    path = os.path.join(out, name + ".fbx")
    if not os.path.exists(path):
        print(f"[CHK] {name}: MISSING")
        fail.append(name + " missing")
        continue
    before = set(bpy.data.objects)
    bpy.ops.import_scene.fbx(filepath=path)
    ob = next(o for o in bpy.data.objects if o not in before and o.type == "MESH")
    me = ob.data
    names = [lay.name for lay in me.uv_layers]
    nl = len(me.loops)
    vidx = np.empty(nl, int)
    me.loops.foreach_get("vertex_index", vidx)
    co = np.empty(len(me.vertices) * 3)
    me.vertices.foreach_get("co", co)
    mw = np.array(ob.matrix_world)
    co = (co.reshape(-1, 3) @ mw[:3, :3].T + mw[:3, 3])[vidx]
    uv = {}
    for i, n in enumerate(names):
        a = np.empty(nl * 2)
        me.uv_layers[n].data.foreach_get("uv", a)
        uv[i] = a.reshape(-1, 2)
    ok_layers = tuple(names) == NAMES
    if not ok_layers:
        print(f"[CHK] {name}: layers {names}, expected {NAMES}")
        fail.append(name + " layers")
        continue
    piv = np.stack([uv[1][:, 0], uv[1][:, 1], uv[2][:, 0]], 1)
    idx = np.argmin(np.linalg.norm(piv[:, None, :] - known[None], axis=2), 1)
    off = np.linalg.norm(piv - known[idx], axis=1).max()
    want = sorted(i for i, g in enumerate(GROUPS) if grp is None or g == grp)
    got = sorted(set(idx.tolist()))
    tilt0 = np.isclose(uv[3][:, 1], 0.0)
    pan_only_ok = name == "SM_ClubMoverHeads" or not tilt0.any()
    consistent = all(np.isclose(uv[3][j, 0], VALS[idx[j]][2][0])
                     and (tilt0[j] or np.isclose(uv[3][j, 1], VALS[idx[j]][2][1]))
                     and np.allclose(uv[4][j], VALS[idx[j]][3], atol=1e-4)
                     and np.allclose(uv[5][j], VALS[idx[j]][4], atol=1e-4) for j in range(nl))
    near = np.linalg.norm(co - piv, axis=1).max()
    print(f"[CHK] {name}: {len(me.polygons)} faces; fixtures {len(got)}/{len(want)}{'' if got == want else ' WRONG SET'}; "
          f"pivot match {off:.1e} m; values consistent {consistent}; pan-only loops {int(tilt0.sum())}"
          f"{'' if pan_only_ok else ' (NOT ALLOWED here)'}; farthest vertex from its pivot {near:.2f} m (limit {lim})")
    if got != want or off > 1e-3 or not consistent or not pan_only_ok or near > lim:
        fail.append(name + " data")
    # the UE material (stored V = 1 - v, read back as 1 - stored) vs the Blender pose
    vr = {i: 1.0 - (1.0 - uv[i][:, 1]) for i in uv}
    wp = np.stack([co[:, 0], -co[:, 1], co[:, 2]], 1) * 100.0 @ YAW180.T
    pivot = np.stack([uv[1][:, 0] * 100.0, vr[1] * -100.0, uv[2][:, 0] * 100.0], 1) @ YAW180.T
    yaw = uv[4][:, 0]
    h0 = np.stack([np.sin(np.radians(yaw)), np.cos(np.radians(yaw)), np.zeros(nl)], 1) @ YAW180.T
    worst = 0.0
    for P in (-1.0, 0.0, 1.0):
        for Q in (-1.0, 1.0):
            pan = P * uv[3][:, 0] * (-1.0 / 360.0)
            r1 = rot(np.broadcast_to(Z, wp.shape), 2 * math.pi * pan, pivot, wp)
            a = 2 * math.pi * pan
            h = h0 * np.cos(a)[:, None] + np.cross(Z, h0) * np.sin(a)[:, None]
            ax = np.cross(h, Z)
            ax /= np.linalg.norm(ax, axis=1, keepdims=True)
            r2 = rot(ax, 2 * math.pi * Q * vr[3] / 360.0, pivot, wp + r1)
            w = (wp + r1 + r2) @ np.linalg.inv(YAW180).T / 100.0
            ue = np.stack([w[:, 0], -w[:, 1], w[:, 2]], 1)
            bl = np.array([tuple(CM.mover_pose_pq(Vector(c), Vector(known[i]), VALS[i][3][0], P, Q, uv[3][j, 0], uv[3][j, 1]))
                           for j, (c, i) in enumerate(zip(co, idx))])
            worst = max(worst, np.linalg.norm(ue - bl, axis=1).max())
    print(f"[CHK]   UE emulation vs mover_pose_pq: worst {worst * 100:.3f} cm")
    if worst > 0.05:
        fail.append(name + " pose")
    if name.startswith("SM_ClubBeams"):
        beam_data[name] = (co, idx)

# the DJ's eyes: every beam's quads, posed over the whole sweep, stay CLEAR_M away (the beam edge, not its axis)
eye = Vector(L.DJ_EYE)
closest = (1e9, None)
for name, (co, idx) in beam_data.items():
    for i in sorted(set(idx.tolist())):
        pts = co[idx == i]
        (px, py), (pz, _), (pa, ta), (yaw, _), _ = VALS[i]
        pv = Vector((px, py, pz))
        for P, Q in CM.SWEEP:
            posed = np.array([tuple(CM.mover_pose_pq(Vector(c), pv, yaw, P, Q, pa, ta)) for c in pts])
            # the beam's quads: sample them densely (corners + interpolation along each quad's long edges)
            for k in range(0, len(posed) - 3, 4):
                q = posed[k:k + 4]
                for s in np.linspace(0.0, 1.0, 81):
                    for t in np.linspace(0.0, 1.0, 5):
                        a_ = q[0] + (q[3] - q[0]) * s
                        b_ = q[1] + (q[2] - q[1]) * s
                        d_ = np.linalg.norm(a_ + (b_ - a_) * t - np.array(eye))
                        if d_ < closest[0]:
                            closest = (d_, f"{name} fixture {i} pose ({P:+.1f}, {Q:+.1f})")
print(f"[CHK] DJ's eyes {tuple(eye)}: the nearest beam point in any pose is {closest[0]:.2f} m away ({closest[1]}; "
      f"limit {CLEAR_M} m)")
if closest[0] < CLEAR_M:
    fail.append("DJ clearance")
print("[CHK] RESULT " + ("PASS" if not fail else "FAIL " + ", ".join(fail)))
