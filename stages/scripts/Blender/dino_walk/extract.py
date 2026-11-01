"""Dino Stage walking map, step 1 (Blender, headless): what stands in the way at body height, and where the dancers are,
from a stage export (out_vN, post-drop Blender meters: the riser top is z 0 = Tribe's floor, the deck -1.0, the field -2.5).
Writes walk_extract.npz for dino_collide.py:
  occ_<band>  per 10 cm cell over x X0..X1, y Y0..Y1: the highest surface sample inside that band's body range above its
              floor (NaN = nothing), for the bands riser (floor 0), deck (-1.0) and field (-2.5)
  people      (n, 3): every dancer's (x, y, feet z), from SM_DinoCrowd (a dancer = the loops sharing its UV2/UV3 values,
              crowd2's per-dancer scale/yaw/mirror/phase)
Light shafts, lasers, halos, the deck mesh (its deck, barrier and stairs are exact numbers in dino_collide.py) and the
ground are left out. Usage: blender -b --factory-startup --python extract.py -- <out dir> <dest npz>"""
import os
import sys

import bpy
import numpy as np

src, dst = sys.argv[sys.argv.index("--") + 1:][:2]
WALLS = ["SM_DinoRig", "SM_DinoMoverHeads", "SM_DinoLenses", "SM_DinoStructure", "SM_DinoRiser", "SM_DinoBooth",
         "SM_DinoPillars", "SM_DinoPlants", "SM_DinoLED", "SM_DinoVisualScreen", "SM_DinoGlow", "SM_DinoGroundsGlow",
         "SM_DinoGroundsStagedeck", "SM_DinoGroundsAtmosphere", "SM_DinoGroundsInfrastructure",
         "SM_DinoGroundsLandmarks", "SM_DinoGroundsVendors"]
X0, X1, Y0, Y1, C = -32.0, 32.0, -97.0, 14.0, 0.10
KNEE, HEAD = 0.25, 1.90
BANDS = {"riser": 0.0, "deck": -1.0, "field": -2.5}
nx, ny = int(round((X1 - X0) / C)), int(round((Y1 - Y0) / C))
occ = {b: np.full((ny, nx), np.nan) for b in BANDS}


def load(name):
    path = os.path.join(src, name + ".fbx")
    if not os.path.exists(path):
        return []
    before = set(bpy.data.objects)
    bpy.ops.import_scene.fbx(filepath=path)
    return [o for o in bpy.data.objects if o not in before and o.type == "MESH"]


def world_tris(ob):
    me = ob.data
    me.calc_loop_triangles()
    co = np.empty(len(me.vertices) * 3)
    me.vertices.foreach_get("co", co)
    mw = np.array(ob.matrix_world)
    co = co.reshape(-1, 3) @ mw[:3, :3].T + mw[:3, 3]
    tri = np.empty(len(me.loop_triangles) * 3, int)
    me.loop_triangles.foreach_get("vertices", tri)
    return co[tri.reshape(-1, 3)]


bpy.ops.wm.read_factory_settings(use_empty=True)
for name in WALLS:
    obs = load(name)
    ntri = 0
    for ob in obs:
        T = world_tris(ob)
        inside = ((T[:, :, 0].max(1) >= X0) & (T[:, :, 0].min(1) <= X1) & (T[:, :, 1].max(1) >= Y0)
                  & (T[:, :, 1].min(1) <= Y1) & (T[:, :, 2].min(1) <= max(BANDS.values()) + HEAD))
        T = T[inside]
        ntri += len(T)
        ext = np.maximum(np.maximum(np.ptp(T[:, :, 0], 1), np.ptp(T[:, :, 1], 1)), np.ptp(T[:, :, 2], 1))
        nseg = np.clip(np.ceil(ext / (C * 0.6)).astype(int), 1, 600)
        for n in np.unique(nseg):
            sel = T[nseg == n]
            a = np.linspace(0, 1, n + 1)
            u, v = np.meshgrid(a, a)
            m = (u + v) <= 1.0
            u, v = u[m], v[m]
            for chunk in range(0, len(sel), max(1, 400000 // max(1, len(u)))):
                S = sel[chunk:chunk + max(1, 400000 // max(1, len(u)))]
                P = (S[:, None, 0, :] * (1 - u - v)[None, :, None] + S[:, None, 1, :] * u[None, :, None]
                     + S[:, None, 2, :] * v[None, :, None]).reshape(-1, 3)
                ix = np.floor((P[:, 0] - X0) / C).astype(int)
                iy = np.floor((P[:, 1] - Y0) / C).astype(int)
                ok = (ix >= 0) & (ix < nx) & (iy >= 0) & (iy < ny)
                ix, iy, z = ix[ok], iy[ok], P[ok, 2]
                for b, f in BANDS.items():
                    inb = (z > f + KNEE) & (z < f + HEAD)
                    if not inb.any():
                        continue
                    o = occ[b]
                    cur = np.nan_to_num(o[iy[inb], ix[inb]], nan=-1e9)
                    zz = z[inb]
                    order = np.argsort(zz)                              # ascending: the last write per cell is its max
                    o[iy[inb][order], ix[inb][order]] = np.maximum(cur[order], zz[order])
    print(f"[WALK] {name}: {len(obs)} object(s), {ntri} triangles in the window")

people = np.zeros((0, 3))
for ob in load("SM_DinoCrowd"):
    me = ob.data
    L = len(me.loops)
    vidx = np.empty(L, int)
    me.loops.foreach_get("vertex_index", vidx)
    co = np.empty(len(me.vertices) * 3)
    me.vertices.foreach_get("co", co)
    mw = np.array(ob.matrix_world)
    co = (co.reshape(-1, 3) @ mw[:3, :3].T + mw[:3, 3])[vidx]
    keys = []
    for i in (2, 3):                                                   # UV2 (scale cos yaw, scale sin yaw), UV3 (mirror
        a = np.empty(L * 2)                                            # scale, phase): one value set per dancer
        me.uv_layers[i].data.foreach_get("uv", a)
        keys.append(np.round(a.reshape(-1, 2), 4))
    key = np.concatenate(keys, 1)
    _, inv = np.unique(key, axis=0, return_inverse=True)
    inv = inv.ravel()
    n = inv.max() + 1
    cnt = np.bincount(inv, minlength=n)
    cx = np.bincount(inv, co[:, 0], n) / cnt
    cy = np.bincount(inv, co[:, 1], n) / cnt
    fz = np.full(n, np.inf)
    np.minimum.at(fz, inv, co[:, 2])
    people = np.concatenate([people, np.stack([cx, cy, fz], 1)])
    print(f"[WALK] SM_DinoCrowd: {L} loops -> {n} dancers (loops each: min {cnt.min()}, median {int(np.median(cnt))})")
np.savez_compressed(dst, x0=X0, y0=Y0, c=C, people=people, **{"occ_" + b: o for b, o in occ.items()})
print(f"[WALK] grid {nx} x {ny}; cells in the way: " + ", ".join(f"{b} {np.isfinite(o).sum()}" for b, o in occ.items()))
