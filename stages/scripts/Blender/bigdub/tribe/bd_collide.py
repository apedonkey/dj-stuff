"""bd_collide.py: BIG DUB's walking map for Tribe XR: tribemod/bigdub_collide.txt (the club's format, hook/club_collide.h;
the hook walks any stage with tribemod/<folder>_collide.txt, the folder lowercased: "bigdub"). The writer's format, caps
and rules line are HARVEST MOON's (Scripts/Blender/harvest/intro/hm_collide.py).

The Stone Circle stands on the knoll's sloping ground and the hook's floors are flat, axis-aligned rectangles (128 at
most), so the ground is a terrace map: the ring's inside and a band 1.10 x its ellipse (about 2.5-3 m past the stones,
the game's "walk round the ring") are cut into rectangles, each split where its ground varies most, until the floor
budget is spent; each rectangle's top is the middle of its ground's range, so feet stay within the reported error of the
drawn ground (the hook eases the height between floors). The rest:
- floors: the Main Stage's deck (Tribe's floor, z 0: the DJ starts on it) and its two back stairs (tribe_site.json);
- boxes: the stage's walls from the game's generator (barrier sections, truss legs, PA, LED pillars, the FOH, the stairs'
  rails, the booth = Tribe's own table) and Tribe's LED wall;
- circles: each standing stone as a chain of circles along its broad face, the flags' poles, and the trunks of the
  trees just outside the band;
- persons: the 1,502 dancers (tribe/out/crowd/walk_people.json), soft with a 15 cm core, as on the other stages;
- spot: decks (the DJ's place).
Off every floor the hook refuses the move (no fall), so the band's edge and the deck's edge are walls by themselves.
The hook refuses the WHOLE map on one bad line or a cap overrun, so the caps are checked here, then a walk check floods a
20 cm grid from the DJ with the hook's rules and must reach the crowd's front, the middle, the Flame Stone's end and the
band all round the ring.

    PYTHONPATH=<tribe>/gen python -P -B bd_collide.py [out.txt]      (exit 1 if a cap or the walk check fails)
Frame: the Tribe frame, world cm (tribe_post.py).
"""
import json
import math
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
GEN = os.path.join(HERE, "out", "gen")
CROWD = os.path.join(HERE, "out", "crowd")
STEP, HEAD, KNEE, RADIUS, CORE = 45.0, 190.0, 25.0, 20.0, 15.0     # cm: the rules line every stage uses
CAPS = {"floor": 128, "box": 512, "circle": 512, "person": 4608, "spot": 8}   # club_collide.h
BAND = 1.10                        # the walkable ground: inside this x the stones' ellipse
FLOOR_BUDGET = 124                 # of the hook's 128: 4 left for later
DANCER_R = 25.0                    # cm: a dancer's shoulders
TRUNK_R = 45.0                     # cm: a tree trunk near the band
DECK = None                        # the deck's rectangle (set from tribe_site.json)
FLOORS, BOXES, CIRCLES, SPOTS, PERSONS = [], [], [], [], []


def log(msg):
    print(f"[COLLIDE] {msg}", flush=True)


site = json.load(open(os.path.join(GEN, "tribe_site.json")))
G = np.load(os.path.join(GEN, "tribe_ground.npy")).astype(np.float64)
GX0, GY0, GS = site["grid"]["x0"], site["grid"]["y0"], site["grid"]["step"]
R = site["ring"]


def ring_r(x, y):
    return np.hypot(np.asarray(x) / R["rb"], (np.asarray(y) - R["cy"]) / R["ra"])


def ground_at(x, y):
    i = np.clip(np.round((np.asarray(x) - GX0) / GS).astype(int), 0, G.shape[1] - 1)
    j = np.clip(np.round((np.asarray(y) - GY0) / GS).astype(int), 0, G.shape[0] - 1)
    return G[j, i]


def bbox(poly):
    P = np.asarray(poly, np.float64)
    return P[:, 0].min(), P[:, 1].min(), P[:, 0].max(), P[:, 1].max()


# ---- the stage: deck, stairs, walls -------------------------------------------------------------------------------------
stage_rects = []
for k, (poly, bot, top) in enumerate(site["Main"]["floors"]):
    x0, y0, x1, y1 = bbox(poly)
    name = "deck" if k == 0 else f"stair_{k}"
    FLOORS.append((name, x0, y0, x1, y1, top, bot))
    stage_rects.append((x0, y0, x1, y1))
    if k == 0:
        DECK = (x0, y0, x1, y1)
for k, (poly, z0, z1) in enumerate(site["Main"]["walls"]):
    x0, y0, x1, y1 = bbox(poly)
    BOXES.append((x0, y0, x1, y1, z0, z1, f"stage_{k}"))
scr = json.load(open(os.path.join(GEN, "tribe_screen.json")))
BOXES.append((scr["x0"], scr["y"] - 15.0, scr["x1"], scr["y"] + 15.0, 0.0, scr["z1"], "led_wall"))
# the stones: a chain of circles along each one's broad face
for k, (poly, z0, z1) in enumerate(site["stones"]["walls"]):
    P = np.asarray(poly, np.float64)
    c = P.mean(0)
    d = P - c
    # the stone's own axes: its longest corner-to-corner direction projected, by PCA of the corners
    w, v = np.linalg.eigh(d.T @ d)
    ax = v[:, 1]
    proj = d @ ax
    perp = d @ v[:, 0]
    half_len, half_th = (proj.max() - proj.min()) / 2.0, max((perp.max() - perp.min()) / 2.0, 15.0)
    n = max(1, int(math.ceil(half_len / half_th)))
    for t in np.linspace(-(half_len - half_th), half_len - half_th, n) if n > 1 else [0.0]:
        q = c + ax * t
        CIRCLES.append((q[0], q[1], half_th + 5.0, z0, z1, f"stone_{k}"))
for k, (poly, z0, z1) in enumerate(site["decor"]["walls"]):
    x0, y0, x1, y1 = bbox(poly)
    CIRCLES.append(((x0 + x1) / 2, (y0 + y1) / 2, max(x1 - x0, y1 - y0) / 2 + 5.0, z0, z1, f"flag_{k}"))
# trees just outside the band (the game keeps them 3.5 m past the stones; the band's rectangles overhang a little)
gsite = json.load(open(os.path.join(GEN, "site.json")))
a = math.radians(12.0)
for name in ("SM_BdTreeHardwood", "SM_BdTreeHemlock"):
    for x, y, z, yaw, sx, sy, sz in gsite["instances"][name]:
        tx = x * math.cos(a) - (y - 90.0) * math.sin(a)
        ty = x * math.sin(a) + (y - 90.0) * math.cos(a) + 90.0
        rr = float(ring_r(tx, ty))
        if rr < BAND + 0.25:
            CIRCLES.append((tx, ty, TRUNK_R * max(sx, 0.8), z - 50.0, z + 900.0, "trunk"))

# ---- the ground: an adaptive cover of the ring and its band ------------------------------------------------------------
xs = GX0 + GS * np.arange(G.shape[1])
ys = GY0 + GS * np.arange(G.shape[0])
XX, YY = np.meshgrid(xs, ys)
region = ring_r(XX, YY) <= BAND
for x0, y0, x1, y1 in stage_rects:                # the deck and the stairs have their own floors
    region &= ~((XX >= x0 - 1) & (XX <= x1 + 1) & (YY >= y0 - 1) & (YY <= y1 + 1))
J, I = np.nonzero(region)


class Cell:
    def __init__(self, j0, j1, i0, i1):
        m = region[j0:j1, i0:i1]
        jj, ii = np.nonzero(m)
        self.ok = len(jj) > 0
        if not self.ok:
            return
        self.j0, self.j1, self.i0, self.i1 = j0 + jj.min(), j0 + jj.max() + 1, i0 + ii.min(), i0 + ii.max() + 1
        z = G[self.j0:self.j1, self.i0:self.i1][region[self.j0:self.j1, self.i0:self.i1]]
        self.zmin, self.zmax = float(z.min()), float(z.max())
        self.err = (self.zmax - self.zmin) / 2.0

    def split(self):
        """The cut (either axis, at 1/8..7/8 of the cell) that leaves the smaller of the two halves' worst errors: on the
        knoll's one-way slopes that cuts along the contours, where a middle cut across them would not help."""
        best = None
        for axis in (0, 1):
            lo, hi = (self.j0, self.j1) if axis == 0 else (self.i0, self.i1)
            if hi - lo < 2:
                continue
            for f in range(1, 8):
                m = lo + max(1, min(hi - lo - 1, round((hi - lo) * f / 8)))
                a_, b_ = ((Cell(self.j0, m, self.i0, self.i1), Cell(m, self.j1, self.i0, self.i1)) if axis == 0 else
                          (Cell(self.j0, self.j1, self.i0, m), Cell(self.j0, self.j1, m, self.i1)))
                score = max(c.err for c in (a_, b_) if c.ok) if (a_.ok or b_.ok) else 0.0
                if best is None or score < best[0]:
                    best = (score, a_, b_)
        return best[1], best[2]


budget = FLOOR_BUDGET - len(FLOORS)
cells = [Cell(J.min(), J.max() + 1, I.min(), I.max() + 1)]
while len(cells) < budget:
    k = max(range(len(cells)), key=lambda q: cells[q].err)
    if cells[k].err < 4.0:
        break
    a_, b_ = cells.pop(k).split()
    new = [c for c in (a_, b_) if c.ok]
    if len(cells) + len(new) > budget:
        cells.append(a_ if a_.ok else b_)
        break
    cells += new
err_max = max(c.err for c in cells)
for k, c in enumerate(sorted(cells, key=lambda c: (c.j0, c.i0))):
    x0, x1 = GX0 + GS * c.i0 - GS / 2, GX0 + GS * (c.i1 - 1) + GS / 2
    y0, y1 = GY0 + GS * c.j0 - GS / 2, GY0 + GS * (c.j1 - 1) + GS / 2
    FLOORS.append((f"ground_{k}", x0, y0, x1, y1, round((c.zmin + c.zmax) / 2.0, 1), round(c.zmin - 120.0, 1)))
log(f"ground: {len(cells)} terrace floors over the ring and its band ({region.sum() * GS * GS / 1e4:.0f} m2); a foot "
    f"stands at most {err_max:.0f} cm off the drawn ground (mean "
    f"{np.mean([c.err for c in cells]):.0f} cm)")

# ---- the dancers ----------------------------------------------------------------------------------------------------------
people = json.load(open(os.path.join(CROWD, "walk_people.json")))
for x, y, z in people:
    PERSONS.append((x, y, DANCER_R, z, z + 180.0))
SPOTS.append(("decks", 0.0, 90.0, 0.0, -90.0))


# ---- the walk check ---------------------------------------------------------------------------------------------------------
def floor_at(x, y, z):
    """club_collide.h cc_floor_at: the highest floor top within +-STEP of z under (x, y); None if none."""
    best = None
    for n, x0, y0, x1, y1, top, bot in FLOORS:
        if x0 <= x <= x1 and y0 <= y <= y1 and abs(top - z) <= STEP and (best is None or top > best):
            best = top
    return best


def blocked(x, y, z):
    lo, hi = z + KNEE, z + HEAD
    for x0, y0, x1, y1, z0, z1, n in BOXES:
        if z1 > lo and z0 < hi and x0 - RADIUS < x < x1 + RADIUS and y0 - RADIUS < y < y1 + RADIUS:
            return True
    for cx, cy, r, z0, z1, n in CIRCLES:
        if z1 > lo and z0 < hi and (x - cx) ** 2 + (y - cy) ** 2 < (r + RADIUS) ** 2:
            return True
    return False


def walk_check(grid=20.0):
    from collections import deque
    start = (0.0, 90.0, 0.0)
    seen = {(0, 90 // 20): 0.0}
    q = deque([(0, int(round(90 / grid)), 0.0)])
    seen = {(0, int(round(90 / grid))): 0.0}
    while q:
        i, j, z = q.popleft()
        for di, dj in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            ni, nj = i + di, j + dj
            if (ni, nj) in seen:
                continue
            x, y = ni * grid, nj * grid
            f = floor_at(x, y, z)
            if f is None or blocked(x, y, f):
                continue
            seen[(ni, nj)] = f
            q.append((ni, nj, f))
    pts = {(k[0] * grid, k[1] * grid) for k in seen}

    def reached_near(x, y, r=150.0):
        return any((px - x) ** 2 + (py - y) ** 2 < r * r for px, py in pts)
    goals = {"the crowd's front (8 m out)": (0.0, -800.0), "the ring's middle": (0.0, R["cy"]),
             "the Flame Stone's end": (0.0, R["cy"] - R["ra"] * 0.85),
             "behind the stage, past the stones": (0.0, R["cy"] + R["ra"] * 1.05)}
    for t in range(0, 360, 30):
        goals[f"the band outside the stones at {t} deg"] = (R["rb"] * 1.05 * math.cos(math.radians(t)),
                                                            R["cy"] + R["ra"] * 1.05 * math.sin(math.radians(t)))
    missing = [n for n, (x, y) in goals.items() if not reached_near(x, y)]
    area = len(pts) * grid * grid / 1e4
    return not missing, missing, area, len(pts)


def write(out):
    lines = ["# BIG DUB (Main Stage) walking map (Scripts/Blender/bigdub/tribe/bd_collide.py): world cm, the club's format",
             f"rules {STEP:g} {HEAD:g} {KNEE:g} {RADIUS:g} {CORE:g}"]
    lines += [f"floor {a:.1f} {b:.1f} {c:.1f} {d:.1f} {t:.1f} {u:.1f} {n}" for n, a, b, c, d, t, u in FLOORS]
    lines += [f"box {a:.1f} {b:.1f} {c:.1f} {d:.1f} {z0:.1f} {z1:.1f} {n}" for a, b, c, d, z0, z1, n in BOXES]
    lines += [f"circle {x:.1f} {y:.1f} {r:.1f} {z0:.1f} {z1:.1f} {n}" for x, y, r, z0, z1, n in CIRCLES]
    lines += [f"person {x:.1f} {y:.1f} {r:.1f} {z0:.1f} {z1:.1f} dancer" for x, y, r, z0, z1 in PERSONS]
    lines += [f"spot {n} {x:.1f} {y:.1f} {z:.1f} {yaw:.1f}" for n, x, y, z, yaw in SPOTS]
    text = "\n".join(lines) + "\n"
    counts = {"floor": len(FLOORS), "box": len(BOXES), "circle": len(CIRCLES), "person": len(PERSONS), "spot": len(SPOTS)}
    over = {k: v for k, v in counts.items() if v > CAPS[k]}
    longest = max(len(ln) for ln in lines)
    size = len(text.encode("ascii"))
    if over or longest > 255 or size >= 512 * 1024:
        log(f"FAIL caps {over}, longest line {longest}, {size} bytes")
        return False
    with open(out, "w", newline="\n") as f:
        f.write(text)
    log(f"{out}: {counts}, {size:,} bytes, longest line {longest} chars")
    return True


if __name__ == "__main__":
    out = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "out", "bigdub_collide.txt")
    ok = write(out)
    good, missing, area, n = walk_check()
    log(("PASS" if good else "FAIL") + f": from the DJ the walker reaches {area:.0f} m2 ({n} grid points)"
        + (f"; missing {missing}" if missing else "; the crowd's front, the middle, the Flame Stone's end, behind the stage "
           "and the band all round the ring"))
    sys.exit(0 if ok and good else 1)
