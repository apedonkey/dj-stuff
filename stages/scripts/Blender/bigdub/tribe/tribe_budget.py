"""tribe_budget.py: BIG DUB (Tribe) in view, the way the game's BIG DUB counts it (gen/bd_site.py estimate_budget: a
104-degree cone from the eye, each mesh at the LOD its bounds' screen size picks on the Quest, nothing past its draw
distance, 8 headings 45 degrees apart), for what the Tribe stage ships: make_site.sh's meshes and instances (no game
crowd, no walking collision) plus the Tribe crowd (SM_BdCrowd 1 section, SM_BdCrowdGlow 1 section, one LOD each, their
bounds from the dancers' feet to 2.5 m over them). Two eyes: the DJ's (170 cm over the deck) and one in the crowd's
middle (165 cm over the ground, 20 m out). Against GRAVEYARD SHIFT's 527,118 triangles, 44 draws, 2 lights.

    PYTHONPATH=<tribe>/gen python -P -B tribe_budget.py
"""
import json
import math
import os

import numpy as np

import bd_site as S

HERE = os.path.dirname(os.path.abspath(__file__))
GEN = os.path.join(HERE, "out", "gen")
CROWD = os.path.join(HERE, "out", "crowd")
LIMIT = (527118, 44)
A = math.radians(12.0)


class Lod:
    def __init__(self, V, F, Mi):
        self.V, self.F, self.M = V, F, Mi

    def arrays(self):
        return self.V, self.F, None, None, self.M


def load_lods(name):
    z = np.load(os.path.join(GEN, "meshes", name + ".npz"))
    out = [Lod(z["V"], z["F"], z["M"])]
    k = 1
    while f"V{k}" in z.files:
        out.append(Lod(z[f"V{k}"], z[f"F{k}"], z[f"M{k}"]))
        k += 1
    return out


def game_xy(x, y):
    y = np.asarray(y, np.float64) - 90.0
    x = np.asarray(x, np.float64)
    return x * math.cos(-A) - y * math.sin(-A), x * math.sin(-A) + y * math.cos(-A) + 90.0


def main():
    site = json.load(open(os.path.join(GEN, "site.json")))
    lods, inst_meshes, screens, cull = {}, {}, {}, {}
    for m in site["meshes"]:
        if m["kind"] == "visual":
            lods[m["name"]] = load_lods(m["name"])
            if m["screen_sizes"]:
                screens[m["name"]] = tuple(m["screen_sizes"])
        elif m["kind"] == "instanced" and not m["name"].startswith("SM_BdCrowd"):
            inst_meshes[m["name"]] = load_lods(m["name"])
            screens[m["name"]] = tuple(m["screen_sizes"])
    inst = {k: v for k, v in site["instances"].items() if k in inst_meshes}
    # the Tribe crowd, in the game's frame (the Tribe frame turned back)
    people = np.asarray(json.load(open(os.path.join(CROWD, "walk_people.json"))), np.float64)
    gx, gy = game_xy(people[:, 0], people[:, 1])
    V = np.concatenate([np.stack([gx, gy, people[:, 2]], 1), np.stack([gx, gy, people[:, 2] + 250.0], 1)])
    meta = json.load(open(os.path.join(CROWD, "T_BdCrowdVAT.json")))
    for name, key in (("SM_BdCrowd", "body"), ("SM_BdCrowdGlow", "glow")):
        n = meta["tris"][key]
        lods[name] = [Lod(V, np.zeros((n, 3), np.int64), np.zeros(n, np.int32))]
    # the eyes: the DJ's, and one in the crowd's middle facing the stage
    dj = np.array([0.0, 90.0, 170.0])
    cx, cy = game_xy(0.0, -2000.0)
    k = int(np.argmin((gx - cx) ** 2 + (gy - cy) ** 2))
    crowd_eye = np.array([float(cx), float(cy), float(people[k, 2]) + 165.0])
    eyes = {}
    for spot, eye, yaw in (("DJ", dj, -102.0), ("crowd", crowd_eye, 78.0)):
        for h in range(8):
            eyes[(spot, h)] = (eye, yaw + 45.0 * h)
    # (the crowd is counted here, not by estimate_budget: its bounding sphere holds the crowd's own eye, and the estimator
    # counts a sphere only if its centre is within 142 degrees of the view, where the renderer draws any mesh whose bounds
    # hold the camera)
    crowd = {n: lods.pop(n) for n in ("SM_BdCrowd", "SM_BdCrowdGlow")}
    res = S.estimate_budget(lods, screens, inst, inst_meshes, cull, eyes)
    for (spot, h), (eye, yaw) in eyes.items():
        fwd = np.array([math.cos(math.radians(yaw)), math.sin(math.radians(yaw))])
        for name, ls in crowd.items():
            c, r = S.bounds(ls[0].V)
            d = max(float(np.linalg.norm(c - eye)), 1.0)
            dirv = (c - eye)[:2]
            ang = math.degrees(math.acos(max(-1.0, min(1.0, float(dirv @ fwd) / max(np.linalg.norm(dirv), 1e-6)))))
            vis = d <= r or ang - math.degrees(math.asin(min(1.0, r / d))) <= S.FOV_DEG / 2
            n = len(ls[0].F)
            res[(spot, h)]["around"][0] += n
            res[(spot, h)]["around"][1] += 1
            if vis:
                res[(spot, h)]["view"][0] += n
                res[(spot, h)]["view"][1] += 1
                res[(spot, h)]["top"] = sorted(res[(spot, h)]["top"] + [(name, n, 1)], key=lambda x: -x[1])
    report = {}
    for spot in ("DJ", "crowd"):
        heads = [res[(spot, h)]["view"] for h in range(8)]
        kt = max(range(8), key=lambda h: heads[h][0])
        kd = max(range(8), key=lambda h: heads[h][1])
        around = res[(spot, 0)]["around"]
        report[spot] = dict(facing=heads[0], heaviest_tris=(heads[kt][0], 45 * kt), most_draws=(heads[kd][1], 45 * kd),
                            around=around, top=res[(spot, 0)]["top"][:8])
        print(f"[BUDGET] from the {spot}'s eye ({'facing the crowd' if spot == 'DJ' else 'facing the stage'}): "
              f"{heads[0][0]:,} tris, {heads[0][1]} draws; heaviest heading {heads[kt][0]:,} tris (+{45 * kt} deg), most "
              f"draws {heads[kd][1]} (+{45 * kd} deg); all around {around[0]:,} tris, {around[1]} draws")
        print(f"[BUDGET]   heaviest in view: {[(n, t) for n, t, s in res[(spot, 0)]['top'][:7]]}")
        ok = heads[kt][0] <= LIMIT[0] and heads[kd][1] <= LIMIT[1]
        print(f"[BUDGET]   {'inside' if ok else 'OVER'} GRAVEYARD SHIFT's {LIMIT[0]:,} tris / {LIMIT[1]} draws from every "
              f"heading; lights: 2 deck lamps (Graveyard: 2)")
    json.dump(report, open(os.path.join(HERE, "out", "budget.json"), "w"), indent=1, default=str)


if __name__ == "__main__":
    main()
