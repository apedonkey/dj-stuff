"""v13 export check (2026-10-09): the moving heads' meshes as exported (SM_DinoMoverBeams, SM_DinoMoverHalos,
SM_DinoMoverHeads, SM_DinoLenses). Each must carry UVMap + the five laser layers, every vertex its own fixture's values
(atmosphere.STAGE_MOVES with the pivot z dropped by 1 m; yokes with tilt 0), and the UE material's emulated move must
equal atmosphere.mover_pose_pq for every vertex (post-drop Blender space).
Usage: blender -b --factory-startup --python mover_fbx_check.py -- <out dir>"""
import math
import os
import sys

import bpy
import numpy as np

sys.path.insert(0, r"C:\Users\Chris\TribeUE\TribeXR\Scripts\Blender\grounds")
sys.path.insert(0, r"C:\Users\Chris\TribeUE\TribeXR\Scripts\Blender")
import atmosphere as A  # noqa: E402
from mathutils import Vector  # noqa: E402

out = sys.argv[sys.argv.index("--") + 1]
DROP = 1.0
NAMES = ("UVMap",) + A.LASER_UV
known = np.array([[m[0][0], m[0][1], m[1][0] - DROP] for m in A.STAGE_MOVES])
YAW180 = np.diag([-1.0, -1.0, 1.0])
Z = np.array([0.0, 0.0, 1.0])
fail = []


def rot(axis, angle, pivot, pos):
    closest = pivot + axis * np.sum(axis * (pos - pivot), 1, keepdims=True)
    U = pos - closest
    return closest + U * np.cos(angle)[:, None] + np.cross(axis, U) * np.sin(angle)[:, None] - pos


bpy.ops.wm.read_factory_settings(use_empty=True)
for name in ("SM_DinoMoverBeams", "SM_DinoMoverHalos", "SM_DinoMoverHeads", "SM_DinoLenses"):
    path = os.path.join(out, name + ".fbx")
    if not os.path.exists(path):
        print(f"[CHK] {name}: MISSING")
        fail.append(name + " missing")
        continue
    before = set(bpy.data.objects)
    bpy.ops.import_scene.fbx(filepath=path)
    ob = next(o for o in bpy.data.objects if o not in before and o.type == "MESH")
    me = ob.data
    names = [l.name for l in me.uv_layers]
    L = len(me.loops)
    vidx = np.empty(L, int)
    me.loops.foreach_get("vertex_index", vidx)
    co = np.empty(len(me.vertices) * 3)
    me.vertices.foreach_get("co", co)
    mw = np.array(ob.matrix_world)
    co = (co.reshape(-1, 3) @ mw[:3, :3].T + mw[:3, 3])[vidx]
    uv = {}
    for i, n in enumerate(names):
        a = np.empty(L * 2)
        me.uv_layers[n].data.foreach_get("uv", a)
        uv[i] = a.reshape(-1, 2)
    ok_layers = tuple(names) == NAMES
    piv = np.stack([uv[1][:, 0], uv[1][:, 1], uv[2][:, 0]], 1)
    idx = np.argmin(np.linalg.norm(piv[:, None, :] - known[None], axis=2), 1)
    off = np.linalg.norm(piv - known[idx], axis=1).max()
    tilt0 = np.isclose(uv[3][:, 1], 0.0)
    consistent = all(np.isclose(uv[3][j, 0], A.STAGE_MOVES[idx[j]][2][0])
                     and (tilt0[j] or np.isclose(uv[3][j, 1], A.STAGE_MOVES[idx[j]][2][1]))
                     and np.allclose(uv[4][j], A.STAGE_MOVES[idx[j]][3]) for j in range(L))
    print(f"[CHK] {name}: {len(me.polygons)} faces, layers {'OK' if ok_layers else names}, fixtures {len(set(idx))}/19, "
          f"pivot match {off:.1e} m, values consistent {consistent}, pan-only loops {int(tilt0.sum())}")
    near = np.linalg.norm(co - piv, axis=1).max()                     # a vertex's distance to its own pivot
    lim = {"SM_DinoMoverHeads": 0.6, "SM_DinoLenses": 0.6, "SM_DinoMoverHalos": 1.3}.get(name, 1e9)
    print(f"[CHK]   farthest vertex from its own pivot {near:.2f} m (limit {lim if lim < 1e8 else '-'})")
    if not ok_layers or len(set(idx)) != 19 or off > 1e-3 or not consistent or near > lim:
        fail.append(name + " data")
    # emulate UE (stored V = 1 - v, read back 1 - v) and compare with the Blender pose
    vr = {i: 1.0 - (1.0 - uv[i][:, 1]) for i in uv}
    wp = np.stack([co[:, 0], -co[:, 1], co[:, 2]], 1) * 100.0 @ YAW180.T
    pivot = np.stack([uv[1][:, 0] * 100.0, vr[1] * -100.0, uv[2][:, 0] * 100.0], 1) @ YAW180.T
    yaw = uv[4][:, 0]
    h0 = np.stack([np.sin(np.radians(yaw)), np.cos(np.radians(yaw)), np.zeros(L)], 1) @ YAW180.T
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
            bl = np.array([tuple(A.mover_pose_pq(Vector(c), Vector(known[i]), A.STAGE_MOVES[i][3][0], P, Q,
                                                 uv[3][j, 0], uv[3][j, 1]))
                           for j, (c, i) in enumerate(zip(co, idx))])
            worst = max(worst, np.linalg.norm(ue - bl, axis=1).max())
    print(f"[CHK]   UE emulation vs mover_pose_pq: worst {worst * 100:.3f} cm")
    if worst > 0.05:
        fail.append(name + " pose")
print("[CHK] RESULT " + ("PASS" if not fail else "FAIL " + ", ".join(fail)))
