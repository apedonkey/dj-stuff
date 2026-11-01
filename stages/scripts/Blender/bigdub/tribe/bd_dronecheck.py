"""bd_dronecheck.py [reel]: checks BIG DUB's drone reel (drone_path.bigdub.txt; the hook's syntax, dumper.cpp
drone_load_path: "fly <secs> <x,y,z> <x,y,z> [look=dj|x,y,z] [fov=deg]", "orbit <secs> [r=] [h=] [deg=] [start=] [fov=]",
world cm) against the Main Stage as built (make_site.sh's out/gen, the crowd's walk_people.json):
  - the hook's limits: at most 40 shots and 8,191 bytes; secs 1-120; r 50-3,000; h -200..2,000; deg +-1,080; fov 10-120;
  - every camera point (each 0.1 s) at least 1.5 m over the ground, 3 m over it where the dancers stand (their heads,
    hands and totems), 0.8 m from every vertex of the set (the stage, its truss and pillars, the stones, the jellyfish
    and flowers) and outside the LED wall's box; and outside every tree's crown (the tree's footprint radius, up to its
    top) or above it.
Exit 1 on any failure. The orbit is taken round the DJ at (0, 90), 170 + h cm up, as the reel's other stages assume.
"""
import json
import math
import os
import sys

import numpy as np
from scipy.spatial import cKDTree

HERE = os.path.dirname(os.path.abspath(__file__))
GEN = os.path.join(HERE, "out", "gen")
REEL = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "drone_path.bigdub.txt")
A = math.radians(12.0)


def to_tribe(P):
    P = np.asarray(P, np.float64)
    x, y = P[..., 0], P[..., 1] - 90.0
    out = P.copy()
    out[..., 0] = x * math.cos(A) - y * math.sin(A)
    out[..., 1] = x * math.sin(A) + y * math.cos(A) + 90.0
    return out


site = json.load(open(os.path.join(GEN, "tribe_site.json")))
G = np.load(os.path.join(GEN, "tribe_ground.npy")).astype(np.float64)
GX0, GY0, GS = site["grid"]["x0"], site["grid"]["y0"], site["grid"]["step"]


def ground(x, y):
    i = int(np.clip(round((x - GX0) / GS), 0, G.shape[1] - 1))
    j = int(np.clip(round((y - GY0) / GS), 0, G.shape[0] - 1))
    return float(G[j, i])


z = np.load(os.path.join(GEN, "meshes", "SM_BdStructures.npz"))
verts = to_tribe(z["V"])
tree = cKDTree(verts)
scr = json.load(open(os.path.join(GEN, "tribe_screen.json")))
people = np.asarray(json.load(open(os.path.join(HERE, "out", "crowd", "walk_people.json"))), np.float64)
ptree = cKDTree(people[:, :2])
gsite = json.load(open(os.path.join(GEN, "site.json")))
trees = []
for name in ("SM_BdTreeHardwood", "SM_BdTreeHemlock"):
    mz = np.load(os.path.join(GEN, "meshes", name + ".npz"))["V"]
    h, r = float(mz[:, 2].max()), float(np.hypot(mz[:, 0], mz[:, 1]).max())
    for x, y, zz, yaw, sx, sy, sz in gsite["instances"][name]:
        p = to_tribe(np.array([x, y, zz]))
        trees.append((p[0], p[1], zz, zz + h * sz, r * max(sx, sy)))
trees = np.asarray(trees)
ttree = cKDTree(trees[:, :2])
RMAX = float(trees[:, 4].max())


def kv(tok, key, default, lo, hi, errs, n):
    for t in tok:
        if t.startswith(key + "="):
            v = float(t.split("=", 1)[1])
            if not lo <= v <= hi:
                errs.append(f"shot {n}: {key}={v:g} outside {lo:g}..{hi:g}")
            return v
    return default


def points(line, n, errs):
    tok = line.split()
    secs = float(tok[1])
    if not 1 <= secs <= 120:
        errs.append(f"shot {n}: {secs:g} s outside 1..120")
    t = np.arange(0.0, secs + 1e-6, 0.1) / secs
    if tok[0] == "fly":
        a = np.array([float(v) for v in tok[2].split(",")])
        b = np.array([float(v) for v in tok[3].split(",")])
        kv(tok, "fov", 90, 10, 120, errs, n)
        return a[None, :] + (b - a)[None, :] * t[:, None]
    r = kv(tok, "r", 260.0, 50, 3000, errs, n)
    h = kv(tok, "h", 30.0, -200, 2000, errs, n)
    deg = kv(tok, "deg", 360.0, -1080, 1080, errs, n)
    st = kv(tok, "start", -90.0, -1080, 1080, errs, n)
    kv(tok, "fov", 90, 10, 120, errs, n)
    ang = np.radians(st + deg * t)
    return np.stack([r * np.cos(ang), 90.0 + r * np.sin(ang), np.full_like(t, 170.0 + h)], 1)


def check_point(p, n, errs):
    x, y, zc = p
    g = ground(x, y)
    if zc < g + 150.0:
        return f"shot {n}: ({x:.0f}, {y:.0f}, {zc:.0f}) only {(zc - g) / 100:.2f} m over the ground"
    if ptree.query_ball_point([x, y], 150.0) and zc < g + 300.0:
        return f"shot {n}: ({x:.0f}, {y:.0f}, {zc:.0f}) among the dancers' heads ({(zc - g) / 100:.2f} m up)"
    d, _ = tree.query(p)
    if d < 80.0:
        return f"shot {n}: ({x:.0f}, {y:.0f}, {zc:.0f}) {d:.0f} cm from the set"
    if scr["x0"] - 50 <= x <= scr["x1"] + 50 and scr["y"] - 60 <= y <= scr["y"] + 60 and zc <= scr["z1"] + 50:
        return f"shot {n}: ({x:.0f}, {y:.0f}, {zc:.0f}) in the LED wall"
    for k in ttree.query_ball_point([x, y], RMAX):
        tx, ty, tz0, ttop, tr = trees[k]
        if math.hypot(x - tx, y - ty) < tr + 50.0 and zc < ttop + 100.0:
            return f"shot {n}: ({x:.0f}, {y:.0f}, {zc:.0f}) in a tree's crown (top {ttop:.0f}, {math.hypot(x - tx, y - ty) / 100:.1f} m off its trunk)"
    return None


def main():
    text = open(REEL).read()
    errs = []
    shots = [ln.strip() for ln in text.splitlines() if ln.strip() and not ln.strip().startswith("#")]
    if len(text.encode()) > 8191:
        errs.append(f"{len(text.encode())} bytes > 8191")
    if len(shots) > 40:
        errs.append(f"{len(shots)} shots > 40")
    total = 0.0
    for n, line in enumerate(shots, 1):
        if line.split()[0] not in ("fly", "orbit"):
            errs.append(f"shot {n}: unknown '{line.split()[0]}'")
            continue
        P = points(line, n, errs)
        total += float(line.split()[1])
        bad = None
        for p in P:
            bad = check_point(p, n, errs)
            if bad:
                break
        print(f"[DRONE] line {n}: {line[:70]}{'...' if len(line) > 70 else ''}  {'FAIL ' + bad if bad else 'ok'}")
        if bad:
            errs.append(bad)
    print(f"[DRONE] {len(shots)} shots, {total:.0f} s, {len(text.encode())} bytes: " + ("PASS" if not errs else "FAIL: " + "; ".join(errs)))
    sys.exit(0 if not errs else 1)


if __name__ == "__main__":
    main()
