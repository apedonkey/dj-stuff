"""Any stage's laser_show export, checked (2026-10-09; first used on Graveyard Shift's SM_HwLasers): the read-back
(UVMap + the five laser layers in order, ranges, the kind split), the UE material's pose against the Blender preview
(atmosphere.laser_pose_pq: the same math laser_show runs, emulated through the FBX import's mirror and V flip and the
level's 180 deg turn), every beam starting at its own pivot, and clearance over the whole +-1 pan/tilt range sampled
along each beam's axis: above raised hands over the field, over the deck (past the unit's own first metres), and away
from the DJ's head. Frame: the stage's final Blender meters (post-drop), as exported.
Usage: blender -b --factory-startup --python laser_fbx_check.py -- <SM_*Lasers.fbx> [field_z deck_z deck_front_y
       dj_x dj_y dj_z]   (defaults: -2.5 -1.0 -4.5 0 0.9 1.7)"""
import math
import sys

import bpy
import numpy as np

sys.path.insert(0, r"C:\Users\Chris\TribeUE\TribeXR\Scripts\Blender\grounds")
sys.path.insert(0, r"C:\Users\Chris\TribeUE\TribeXR\Scripts\Blender")
from atmosphere import laser_pose_pq   # noqa: E402
from mathutils import Vector  # noqa: E402

args = sys.argv[sys.argv.index("--") + 1:]
path = args[0]
FIELD_Z, DECK_Z, DECK_FRONT_Y, DJX, DJY, DJZ = (list(map(float, args[1:7])) + [-2.5, -1.0, -4.5, 0.0, 0.9, 1.7][len(args[1:7]):])
HANDS, DECK_CLEAR, DJ_CLEAR, OWN_UNIT = 2.3, 3.0, 4.9, 3.0
NAMES = ("UVMap", "LaserPivot", "LaserPivotZPhase", "LaserAmp", "LaserCue", "LaserFix")
fail = []

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.fbx(filepath=path)
ob = next(o for o in bpy.context.scene.objects if o.type == "MESH")
me = ob.data
L = len(me.loops)
vidx = np.empty(L, int)
me.loops.foreach_get("vertex_index", vidx)
co = np.empty(len(me.vertices) * 3)
me.vertices.foreach_get("co", co)
mw = np.array(ob.matrix_world)
co = (co.reshape(-1, 3) @ mw[:3, :3].T + mw[:3, 3])[vidx]
names = [l.name for l in me.uv_layers]
uv = {}
for i, n in enumerate(names):
    a = np.empty(L * 2)
    me.uv_layers[n].data.foreach_get("uv", a)
    uv[i] = a.reshape(-1, 2)
print(f"[LCHK] {path}")
print(f"[LCHK] {len(me.polygons)} faces, {L} loops; layers {names} -> {'OK' if tuple(names) == NAMES else 'WRONG ORDER'}")
if tuple(names) != NAMES:
    fail.append("layers")
for i, n in enumerate(names):
    print(f"[LCHK]   {i} {n:17s} u {uv[i][:, 0].min():8.3f} .. {uv[i][:, 0].max():8.3f}   v {uv[i][:, 1].min():8.3f} .. "
          f"{uv[i][:, 1].max():8.3f}")
kind = uv[5][:, 1]
beam = kind < 0.5
print(f"[LCHK] kind: {beam.sum()} beam loops, {(~beam).sum()} aperture loops")

# the UE side (as wpo_emulate.py): local cm = (x, -y, z) * 100, the level turned 180, V stored 1 - v and read back
M = np.diag([-100.0, 100.0, 100.0])
uv_ue = {i: np.stack([a[:, 0], 1.0 - a[:, 1]], 1) for i, a in uv.items()}
vread = {i: 1.0 - uv_ue[i][:, 1] for i in uv_ue}
wp = co @ M.T
pivot_ue = np.stack([uv_ue[1][:, 0] * 100.0, vread[1] * -100.0, uv_ue[2][:, 0] * 100.0], 1) @ np.diag([-1.0, -1.0, 1.0])
amp_p, amp_t = uv_ue[3][:, 0], vread[3]
pivot_b = np.stack([uv[1][:, 0], uv[1][:, 1], uv[2][:, 0]], 1)
Z = np.array([0.0, 0.0, 1.0])


def rot(axis, angle, piv, pos):
    closest = piv + axis * np.sum(axis * (pos - piv), 1, keepdims=True)
    U = pos - closest
    return closest + U * np.cos(angle)[:, None] + np.cross(axis, U) * np.sin(angle)[:, None] - pos


def ue_pose(P, Q):
    pan = P * amp_p * (-1.0 / 360.0)
    r1 = rot(np.broadcast_to(Z, wp.shape), pan * 2 * math.pi, pivot_ue, wp)
    p1 = wp + r1
    v = p1 - pivot_ue + np.array([0.0, -1.0, 0.0])
    ax = np.cross(v, Z)
    ax /= np.maximum(np.linalg.norm(ax, axis=1, keepdims=True), 1e-9)
    r2 = rot(ax, Q * amp_t * (2 * math.pi / 360.0), pivot_ue, p1)
    return (wp + r1 + r2) @ np.linalg.inv(M).T


print(f"[LCHK] pivots: UE path vs raw max diff "
      f"{np.abs(pivot_ue @ np.linalg.inv(M).T - pivot_b).max():.2e} m (the pivot read through the import)")
d_piv = np.linalg.norm(co - pivot_b, axis=1)
print(f"[LCHK] beam loops: distance to own pivot min {d_piv[beam].min():.3f} m, max {d_piv[beam].max():.1f} m")
worst = 0.0
for P in (-1.0, 0.0, 1.0):
    for Q in (-1.0, 0.0, 1.0):
        ue = ue_pose(P, Q)[beam]
        bl = np.array([tuple(laser_pose_pq(c, pv, P, Q, ap, at)) for c, pv, ap, at in
                       zip(co[beam], pivot_b[beam], uv[3][beam, 0], uv[3][beam, 1])])
        worst = max(worst, np.linalg.norm(ue - bl, axis=1).max())
print(f"[LCHK] UE emulation vs laser_pose_pq: worst {worst * 100:.3f} cm over the 3 x 3 extremes")
if worst > 0.5:
    fail.append("pose")

# beams: by (pivot, u); axis = apex (UVMap v ~ 0) to end (v at its max)
key = np.round(np.concatenate([pivot_b, uv[4][:, 1:2]], 1), 4)
ids, inv = np.unique(key[beam], axis=0, return_inverse=True)
inv = inv.ravel()
cb, vb = co[beam], uv[0][beam, 1]
pb, ab = pivot_b[beam], uv[3][beam]
lowest_field, lowest_deck, dj_min, worst_beam = 1e9, 1e9, 1e9, None
for b in range(len(ids)):
    sel = inv == b
    vv = vb[sel]
    apex = cb[sel][vv < vv.min() + 0.01].mean(0)
    end = cb[sel][vv > vv.max() - 0.01].mean(0)
    pv = Vector(pb[sel][0])
    pan_amp, tilt_amp = ab[sel][0]
    for P in np.linspace(-1, 1, 9):
        for Q in np.linspace(-1, 1, 5):
            for t in np.linspace(0.0, 1.0, 81):
                p = np.array(laser_pose_pq(Vector(apex + (end - apex) * t), pv, P, Q, pan_amp, tilt_amp))
                own = np.linalg.norm(p - pb[sel][0]) < OWN_UNIT
                if p[1] < DECK_FRONT_Y - 0.1:
                    lowest_field = min(lowest_field, p[2] - FIELD_Z)
                elif abs(p[0]) < 25 and not own:
                    if p[2] - DECK_Z < lowest_deck:
                        lowest_deck, worst_beam = p[2] - DECK_Z, (tuple(np.round(pb[sel][0], 2)), P, Q)
                dj_min = min(dj_min, float(np.linalg.norm(p - np.array([DJX, DJY, DJZ]))))
print(f"[LCHK] {len(ids)} beams; over the whole +-1 range, sampled along each axis:")
print(f"[LCHK]   lowest point over the field (y < {DECK_FRONT_Y - 0.1}): {lowest_field:.2f} m above it (need >= {HANDS})")
print(f"[LCHK]   lowest point over the deck, past each unit's first {OWN_UNIT:.0f} m: {lowest_deck:.2f} m above it "
      f"(need >= {DECK_CLEAR}){'' if lowest_deck >= DECK_CLEAR else f' at unit {worst_beam[0]}, P {worst_beam[1]:+.2f} Q {worst_beam[2]:+.2f}'}")
print(f"[LCHK]   closest to the DJ's head ({DJX}, {DJY}, {DJZ}): {dj_min:.2f} m (need >= {DJ_CLEAR})")
if lowest_field < HANDS:
    fail.append("field clearance")
if lowest_deck < DECK_CLEAR:
    fail.append("deck clearance")
if dj_min < DJ_CLEAR:
    fail.append("DJ clearance")
print("[LCHK] RESULT " + ("PASS" if not fail else "FAIL " + ", ".join(fail)))
