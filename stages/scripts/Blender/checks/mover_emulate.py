"""Check the v13 mover material's WPO against atmosphere.mover_pose_pq (2026-10-09), on the moving heads' beams and lens
glows as atmosphere.build() makes them. UE side, emulated: dino_stage's drop (geometry and pivot z), the FBX import
(mesh local cm = (x, -y, z) * 100, V stored as 1 - v), the level actor's yaw 180 (local -> world for positions and
directions), the material (vread, pan about world Z, the rigid tilt axis from the rest yaw through the transform,
MOVER_AXIS_HLSL, RotateAboutAxis as in Common.ush). Also: every vertex of a fixture carries its fixture's values, and
the beams' clearance over the crowd / DJ across the whole range.
Usage: blender -b --factory-startup --python mover_emulate.py"""
import math
import random
import sys

import bpy  # noqa: F401
import numpy as np

sys.path.insert(0, r"C:\Users\Chris\TribeUE\TribeXR\Scripts\Blender\grounds")
sys.path.insert(0, r"C:\Users\Chris\TribeUE\TribeXR\Scripts\Blender")
import atmosphere as A  # noqa: E402
from mathutils import Vector  # noqa: E402

DROP = 1.0
res = A.build(random.Random(5))
fail = []


def loops_of(bm):
    lays = [bm.loops.layers.uv.get(n) for n in ("UVMap",) + A.LASER_UV]
    co, uv = [], {i: [] for i in range(6)}
    for f in bm.faces:
        for lp in f.loops:
            co.append(tuple(lp.vert.co))
            for i, lay in enumerate(lays):
                uv[i].append(tuple(lp[lay].uv))
    return np.array(co), {i: np.array(v) for i, v in uv.items()}


def rotate_about_axis(axis, angle, pivot, pos):
    closest = pivot + axis * np.sum(axis * (pos - pivot), 1, keepdims=True)
    U = pos - closest
    V = np.cross(axis, U)
    return closest + U * np.cos(angle)[:, None] + V * np.sin(angle)[:, None] - pos


YAW180 = np.diag([-1.0, -1.0, 1.0])
for key in ("movers", "mover_halos"):
    co_b, uv = loops_of(res[key][0])                                  # Blender, pre-drop
    print(f"[MOV] {key}: {len(co_b)} loops, layers {[len(uv[i]) for i in range(6)]}")
    # dino_stage: geometry and pivot z drop by DROP (bm_merge_layers zdrop)
    co_d = co_b - np.array([0, 0, DROP])
    uv[2] = uv[2] - np.array([DROP, 0])
    # the data each loop carries must be its fixture's (STAGE_MOVES): match by pivot
    piv = np.stack([uv[1][:, 0], uv[1][:, 1], uv[2][:, 0] + DROP], 1)
    known = np.array([[m[0][0], m[0][1], m[1][0]] for m in A.STAGE_MOVES])
    idx = np.argmin(np.linalg.norm(piv[:, None, :] - known[None], axis=2), 1)
    off = np.linalg.norm(piv - known[idx], axis=1).max()
    same = all(np.allclose(uv[3][j], A.STAGE_MOVES[idx[j]][2]) and np.allclose(uv[4][j], A.STAGE_MOVES[idx[j]][3])
               for j in range(len(idx)))
    print(f"[MOV]   fixtures by pivot: {len(set(idx))}/19 seen, pivot match {off:.1e} m, amps/yaw/u consistent: {same}")
    if len(set(idx)) != 19 or off > 1e-4 or not same:
        fail.append(key + " data")
    # UE storage + reads
    uv_ue = {i: np.stack([a[:, 0], 1.0 - a[:, 1]], 1) for i, a in uv.items()}
    vread = {i: 1.0 - uv_ue[i][:, 1] for i in uv_ue}
    local = np.stack([co_d[:, 0], -co_d[:, 1], co_d[:, 2]], 1) * 100.0
    wp = local @ YAW180.T
    pl = np.stack([uv_ue[1][:, 0] * 100.0, vread[1] * -100.0, uv_ue[2][:, 0] * 100.0], 1)
    pivot = pl @ YAW180.T
    yaw = uv_ue[4][:, 0]
    hl = np.stack([np.sin(np.radians(yaw)), np.cos(np.radians(yaw)), np.zeros_like(yaw)], 1)
    h0 = hl @ YAW180.T                                                 # TransformVector local -> world
    h0 /= np.linalg.norm(h0, axis=1, keepdims=True)
    Z = np.array([0.0, 0.0, 1.0])

    def ue(P, Q):
        pan = P * uv_ue[3][:, 0] * (-1.0 / 360.0)
        r1 = rotate_about_axis(np.broadcast_to(Z, wp.shape), pan * 2 * math.pi, pivot, wp)
        p1 = wp + r1
        a = 2 * math.pi * pan
        h = h0 * np.cos(a)[:, None] + np.cross(Z, h0) * np.sin(a)[:, None]
        ax = np.cross(h, Z)
        ax /= np.maximum(np.linalg.norm(ax, axis=1, keepdims=True), 1e-6)
        tilt = Q * vread[3] * (1.0 / 360.0)
        r2 = rotate_about_axis(ax, tilt * 2 * math.pi, pivot, p1)
        w = wp + r1 + r2
        loc = w @ np.linalg.inv(YAW180).T / 100.0
        return np.stack([loc[:, 0], -loc[:, 1], loc[:, 2]], 1) + np.array([0, 0, DROP])   # Blender, pre-drop

    worst = 0.0
    for P in (-1.0, -0.5, 0.0, 0.5, 1.0):
        for Q in (-1.0, 0.0, 1.0):
            bl = np.array([tuple(A.mover_pose_pq(Vector(c), Vector(known[i]), A.STAGE_MOVES[i][3][0], P, Q,
                                                 *A.STAGE_MOVES[i][2])) for c, i in zip(co_b, idx)])
            err = np.linalg.norm(ue(P, Q) - bl, axis=1)
            worst = max(worst, err.max())
            if key == "movers" and (P, Q) in ((1.0, 1.0), (-1.0, -1.0)):
                moved = np.linalg.norm(bl - co_b, axis=1)
                print(f"[MOV]   P {P:+.0f} Q {Q:+.0f}: beam vertices move up to {moved.max():.1f} m, "
                      f"UE emulation off by max {err.max() * 100:.3f} cm")
    print(f"[MOV]   worst difference over the P/Q grid {worst * 100:.3f} cm")
    if worst > 0.01:
        fail.append(key + " pose")

# clearance: every stage beam over the whole range stays above raised hands in the crowd and clear of the DJ
co_b, uv = loops_of(res["movers"][0])
piv = np.stack([uv[1][:, 0], uv[1][:, 1], uv[2][:, 0]], 1)
known = np.array([[m[0][0], m[0][1], m[1][0]] for m in A.STAGE_MOVES])
idx = np.argmin(np.linalg.norm(piv[:, None, :] - known[None], axis=2), 1)
low, dj = 1e9, 1e9
DJ = np.array([0.0, 0.8, 2.6])
for P in np.linspace(-1, 1, 9):
    for Q in np.linspace(-1, 1, 5):
        for i in range(19):
            sel = np.where(idx == i)[0]
            m = A.STAGE_MOVES[i]
            pts = np.array([tuple(A.mover_pose_pq(Vector(co_b[j]), Vector(known[i]), m[3][0], P, Q, *m[2])) for j in sel])
            # the beam's axis from its lens, sampled every 0.25 m: over the crowd (past the barrier) and to the DJ
            c, d = Vector(A.STAGE_AIMS[i][0]), Vector(A.STAGE_AIMS[i][1])
            for t in np.linspace(0, 60, 241):
                p = np.array(A.mover_pose_pq(c + d * t, Vector(known[i]), m[3][0], P, Q, *m[2]))
                if p[1] < -7.5:
                    low = min(low, p[2] - A.GROUND_Z)
                dj = min(dj, np.linalg.norm(p - DJ))
print(f"[MOV] clearance: lowest beam point over the crowd {low:.2f} m above the field (raised hands ~2.3 m); "
      f"closest beam axis to the DJ's eyes {dj:.2f} m")
if low < 2.3:
    fail.append("crowd clearance")
if dj < 2.0:
    fail.append("DJ clearance")
print("[MOV] RESULT " + ("PASS" if not fail else "FAIL " + ", ".join(fail)))
