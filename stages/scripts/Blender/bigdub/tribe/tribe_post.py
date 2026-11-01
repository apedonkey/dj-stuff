"""tribe_post.py: the Tribe-only changes to the Main Stage's generated meshes (tribe/out/gen/meshes, bd_site.py's copy),
run after bd_site.py and before bd_blender.py:

  1. the LED wall's quad comes out of SM_BdStructures' Screen section: Tribe's own visuals screen (SM_DinoVisualScreen,
     made by build_bigdub.py with Tribe's UVs) takes its place, so the user's VJ loops play on it;
  2. the Tribe frame: Tribe's DJ stands at (0, 90) facing -Y; the game's Main Stage DJ stands at (0, 90) facing yaw -102.
     Every actor in the Tribe level carries one transform, a turn of +12 degrees about the DJ's point (no mesh is
     re-authored, so the materials can turn world positions back into the game's frame and read its light map);
  3. a report: what of SM_BdStructures stands inside Tribe's spectator box (it must stay clear above the floor).

    PYTHONPATH=<tribe>/gen python -P -B tribe_post.py
Writes out/gen/tribe_screen.json (the wall's corners in the Tribe frame) and logs [TRIBE] lines.
"""
import json
import math
import os

import numpy as np

import bd_mesh as M

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "out", "gen")
YAW = 12.0                        # the Tribe frame = the game's frame turned this far about the DJ's point
DJ = np.array([0.0, 90.0, 0.0])   # the DJ's floor point, the same in both frames
SPECTATOR_BOX = ((-250.0, 250.0), (-221.0, 279.0), (-6.0, 494.0))   # Tribe's SpectatorBoundingBox, world cm
RING_CENTRE = (-343.1, -1523.9)   # the Stone Circle's centre, the game's frame (site.json "ring" center_world)
WATER_KEEP_M = 250.0


def to_tribe(P):
    a = math.radians(YAW)
    c, s = math.cos(a), math.sin(a)
    q = np.asarray(P, np.float64) - DJ
    return np.stack([q[..., 0] * c - q[..., 1] * s, q[..., 0] * s + q[..., 1] * c, q[..., 2]], -1) + DJ


def log(msg):
    print(f"[TRIBE] {msg}", flush=True)


def main():
    path = os.path.join(OUT, "meshes", "SM_BdStructures.npz")
    z = dict(np.load(path))
    V, F, Mi = z["V"], z["F"], z["M"]
    mats = [str(m) for m in z["materials"]]
    screen = mats.index("Screen")
    # the wall: the widest Screen quad (12 x 6.75 m; the pillars' faces are 1.3 m wide)
    sel = np.where(Mi == screen)[0]
    P = to_tribe(V[F[sel]])                       # (n, 3, 3)
    width = P[..., 0].max(1) - P[..., 0].min(1)
    wall = sel[width > 1000.0]
    if len(wall) != 2:
        raise SystemExit(f"[TRIBE] expected the LED wall's 2 triangles, found {len(wall)}")
    W = to_tribe(V[F[wall]].reshape(-1, 3))
    lo, hi = W.min(0), W.max(0)
    info = dict(x0=round(float(lo[0]), 2), x1=round(float(hi[0]), 2), y=round(float(lo[1]), 2), z0=round(float(lo[2]), 2),
                z1=round(float(hi[2]), 2), note="Tribe frame, world cm: the LED wall's quad, facing -Y (the crowd)")
    if hi[1] - lo[1] > 1.0:
        raise SystemExit(f"[TRIBE] the wall isn't square to the Tribe frame: y {lo[1]:.1f}..{hi[1]:.1f}")
    keep = np.ones(len(F), bool)
    keep[wall] = False
    # the spectator box: report every triangle with a corner inside it above the deck's top
    T = to_tribe(V[F[keep]])
    (bx0, bx1), (by0, by1), (bz0, bz1) = SPECTATOR_BOX
    inside = ((T[..., 0] > bx0) & (T[..., 0] < bx1) & (T[..., 1] > by0) & (T[..., 1] < by1) & (T[..., 2] > 5.0)
              & (T[..., 2] < bz1)).any(1)
    log(f"spectator box: {int(inside.sum())} structure triangles reach inside it above the floor"
        + (f" (z {T[inside][..., 2].min():.0f}..{T[inside][..., 2].max():.0f}, y {T[inside][..., 1].min():.0f}.."
           f"{T[inside][..., 1].max():.0f}, x {T[inside][..., 0].min():.0f}..{T[inside][..., 0].max():.0f}): the game's "
           f"booth table, where Tribe's own rig stands; taken out" if inside.any() else ""))
    keep[np.where(keep)[0][inside]] = False
    F2 = F[keep]
    used = np.unique(F2)
    remap = np.full(len(V), -1, np.int64)
    remap[used] = np.arange(len(used))
    out = dict(V=V[used], F=remap[F2].astype(np.int32), C=z["C"][used], UV=z["UV"][used], X=z["X"][:, used],
               M=Mi[keep], materials=z["materials"])
    M.save_npz(path, out)
    with open(os.path.join(OUT, "tribe_screen.json"), "w") as f:
        json.dump(info, f, indent=1)
    log(f"LED wall out of SM_BdStructures ({len(F)} -> {len(F2)} triangles); Tribe's screen goes at {info}")
    # Tribe's screen: the wall's own two triangles (their winding faces the crowd), in the Tribe frame (its actor stands
    # untransformed), with Tribe's backdrop UVs: U = 0.5 - x / w, V = 1 - 0.5 (z - bottom) / h as Unreal stores them
    # (bd_blender.py writes v flipped and Unreal flips it back); M_VideoBackdrop samples (1 - U, 2 V - 1)
    Wv = to_tribe(V[F[wall]].reshape(-1, 3))
    w, h = hi[0] - lo[0], hi[2] - lo[2]
    uv = np.stack([0.5 - Wv[:, 0] / w, 1.0 - 0.5 * (Wv[:, 2] - lo[2]) / h], 1).astype(np.float32)
    scr = dict(V=Wv.astype(np.float32), F=np.arange(6, dtype=np.int32).reshape(2, 3),
               C=np.ones((6, 4), np.float32), UV=uv, X=np.zeros((M.AUX_UVS, 6, 2), np.float32),
               M=np.zeros(2, np.int32), materials=np.array(["Screen"]))
    M.save_npz(os.path.join(OUT, "meshes", "SM_DinoVisualScreen.npz"), scr)
    log(f"SM_DinoVisualScreen: {w:.0f} x {h:.0f} cm at y {lo[1]:.0f}, UV U {uv[:, 0].min():.2f}..{uv[:, 0].max():.2f} "
        f"V {uv[:, 1].min():.2f}..{uv[:, 1].max():.2f}")
    # the creek: only its reaches within WATER_KEEP_M of the ring (the nearest is 80 m off, under the trees); the rest of
    # its 3 km is never in sight from the ring and cost 12k triangles in the heaviest headings
    wp = os.path.join(OUT, "meshes", "SM_BdWater.npz")
    zw = dict(np.load(wp))
    cen = zw["V"][zw["F"]].mean(1)
    keepw = np.hypot(cen[:, 0] - RING_CENTRE[0], cen[:, 1] - RING_CENTRE[1]) < WATER_KEEP_M * 100.0
    Fw = zw["F"][keepw]
    usedw = np.unique(Fw)
    rw = np.full(len(zw["V"]), -1, np.int64)
    rw[usedw] = np.arange(len(usedw))
    M.save_npz(wp, dict(V=zw["V"][usedw], F=rw[Fw].astype(np.int32), C=zw["C"][usedw], UV=zw["UV"][usedw],
                        X=zw["X"][:, usedw], M=zw["M"][keepw], materials=zw["materials"]))
    log(f"SM_BdWater: {len(zw['F'])} -> {len(Fw)} triangles (within {WATER_KEEP_M:.0f} m of the ring)")


if __name__ == "__main__":
    main()
