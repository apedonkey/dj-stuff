"""Check the v12 laser material's WPO against the Blender preview, on the exported mesh (2026-10-09).
UE side, emulated: the FBX import (mesh local cm = (x, -y, z) * 100, V stored as 1 - v), the level actor's yaw 180,
the material reading V back as 1 - v, and UE's RotateAboutAxis (Common.ush) for pan then tilt exactly as laser_show
wires it. Blender side: atmosphere.laser_pose_pq. Both poses are compared in Blender meters for a grid of (P, Q).
Usage: blender -b --factory-startup --python wpo_emulate.py -- <SM_DinoLasers.fbx>"""
import math
import os
import sys

import bpy
import numpy as np

sys.path.insert(0, r"C:\Users\Chris\TribeUE\TribeXR\Scripts\Blender\grounds")
sys.path.insert(0, r"C:\Users\Chris\TribeUE\TribeXR\Scripts\Blender")
from atmosphere import laser_pose_pq   # noqa: E402

path = sys.argv[sys.argv.index("--") + 1]
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.fbx(filepath=path)
ob = next(o for o in bpy.context.scene.objects if o.type == "MESH")
me = ob.data
mw = np.array(ob.matrix_world)
L = len(me.loops)
vidx = np.empty(L, int)
me.loops.foreach_get("vertex_index", vidx)
co = np.empty(len(me.vertices) * 3)
me.vertices.foreach_get("co", co)
co = co.reshape(-1, 3) @ mw[:3, :3].T + mw[:3, 3]
co = co[vidx]                                                    # per loop, Blender world meters
uv = {}
for i, layer in enumerate(me.uv_layers):
    a = np.empty(L * 2)
    layer.data.foreach_get("uv", a)
    uv[i] = a.reshape(-1, 2)
beam = uv[5][:, 1] < 0.5
print(f"[EMU] {L} loops, {beam.sum()} beam loops; object matrix identity: {np.allclose(mw, np.eye(4))}")

# ---- the UE side
M = np.diag([-100.0, 100.0, 100.0])          # Blender m -> UE world cm: local (x, -y, z)*100, then the actor's yaw 180
uv_ue = {i: np.stack([a[:, 0], 1.0 - a[:, 1]], 1) for i, a in uv.items()}   # what Unreal stores


def vread(c):
    return 1.0 - uv_ue[c][:, 1]


def rotate_about_axis(axis, angle, pivot, pos):                   # UE Common.ush RotateAboutAxis -> offset
    closest = pivot + axis * np.sum(axis * (pos - pivot), 1, keepdims=True)
    U = pos - closest
    V = np.cross(axis, U)
    R = U * np.cos(angle)[:, None] + V * np.sin(angle)[:, None]
    return closest + R - pos


wp = co @ M.T
pl = np.stack([uv_ue[1][:, 0] * 100.0, vread(1) * -100.0, uv_ue[2][:, 0] * 100.0], 1)   # pivot, mesh local cm
yaw = np.diag([-1.0, -1.0, 1.0])
pivot = pl @ yaw.T                                                   # TransformPosition local -> world
amp_p, amp_t = uv_ue[3][:, 0], vread(3)
Z = np.array([0.0, 0.0, 1.0])


def ue_pose(P, Q):
    pan = P * amp_p * (-1.0 / 360.0)
    r1 = rotate_about_axis(np.broadcast_to(Z, wp.shape), pan * 2 * math.pi, pivot, wp)
    p1 = wp + r1
    v = p1 - pivot + np.array([0.0, -1.0, 0.0])
    ax = np.cross(v, Z)
    ax /= np.linalg.norm(ax, axis=1, keepdims=True)
    tilt = Q * amp_t * (1.0 / 360.0)
    r2 = rotate_about_axis(ax, tilt * 2 * math.pi, pivot, p1)
    return (wp + r1 + r2) @ np.linalg.inv(M).T                      # back to Blender meters


# ---- sanity: the pivots sit at their beams (apex vertices close to the pivot)
piv_b = pivot @ np.linalg.inv(M).T
d = np.linalg.norm(co - piv_b, axis=1)
print(f"[EMU] beam loops: distance to own pivot min {d[beam].min():.3f} m, median {np.median(d[beam]):.2f} m")
print(f"[EMU] pivot (UE path) vs pivot (raw UVs) max diff "
      f"{np.abs(piv_b - np.stack([uv[1][:, 0], uv[1][:, 1], uv[2][:, 0]], 1)).max():.2e} m")

worst = 0.0
for P in (-1.0, -0.5, 0.0, 0.5, 1.0):
    for Q in (-1.0, 0.0, 1.0):
        ue = ue_pose(P, Q)[beam]
        bl = np.array([tuple(laser_pose_pq(c, (px, py, pz), P, Q, ap, at))
                       for c, px, py, pz, ap, at in zip(co[beam], uv[1][beam, 0], uv[1][beam, 1], uv[2][beam, 0],
                                                         uv[3][beam, 0], uv[3][beam, 1])])
        err = np.linalg.norm(ue - bl, axis=1)
        moved = np.linalg.norm(bl - co[beam], axis=1)
        worst = max(worst, err.max())
        print(f"[EMU] P {P:+.1f} Q {Q:+.1f}: Blender preview moves beam vertices up to {moved.max():6.2f} m; "
              f"UE emulation differs by max {err.max() * 100:6.2f} cm (median {np.median(err) * 100:.3f} cm)")
print(f"[EMU] RESULT worst difference {worst * 100:.2f} cm -> {'PASS' if worst < 0.05 else 'CHECK'}")
