"""Dino Stage walking (2026-10-09; the user: "id like to incorporate walking too, like in the other chat from reactor.
also i need a path to get into the crowd", then "do everything" for both drawn routes): writes dino_collide.txt for
hook/club.cpp (the club session's walking reads tribemod/<folder>_collide.txt for the stage that's up: "dino" here),
checks it with an offline walk under the hook's rules and draws a top-down check image. The rules and the file format
are the club's (Scripts/Blender/club/club_collide.py, hook/club_collide.h); this file only builds Dino's shapes.

    python dino_collide.py <walk_extract.npz> [out_dir]          (walk_extract.npz from extract.py on the same export)

Frame: the stage export (post-drop Blender m: the riser top 0 = Tribe's floor, the deck -1.0, the field -2.5) -> Unreal
world cm = (-100x, 100y, 100z) (the FBX import mirrors Y, the level turns 180 deg).
Shapes: floors and the crowd barrier are exact numbers from dino_stage.py (the riser and its side stairs, the deck,
WALKWAYS with their stairs, the barrier with a gate in line with each walkway). Walls are extract.py's body-height raster
(what stands between knee and head height above each floor), merged into boxes. Dancers are soft people (the hook keeps at
most 1024: the nearest to the walkways go in, every stage guest too).
"""
import ast
import math
import os
import sys
from collections import deque

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
STAGE = os.path.join(os.path.dirname(HERE), "dino_stage.py")
STEP, HEAD, KNEE, RADIUS, CORE = 45.0, 190.0, 25.0, 20.0, 15.0   # cm: the club's rules line
DANCER_R = 25.0                                                   # cm: a dancer's shoulders (soft)
GRID = 10.0                                                       # cm: the offline walk's grid
MAX_PEOPLE, MAX_BOXES = 4600, 480                                 # the hook (club_collide.h 83ab550e): CC_MAXP 4608,
LIMIT_F, LIMIT_B, LIMIT_P, MAP_BYTES = 128, 512, 4608, 512 * 1024  # CC_MAXB 512, a 512 KB read buffer (club.cpp 971a4293)


def stage_consts():
    """WALKWAYS, STAIR_*, DECK_FRONT_Y, BARRIER_Y, STAGE_DROP straight from dino_stage.py (one source of truth)."""
    want = {"WALKWAYS", "STAIR_RISE", "STAIR_RUN", "STAIR_N", "DECK_FRONT_Y", "BARRIER_Y", "STAGE_DROP"}
    out = {}
    for node in ast.parse(open(STAGE, encoding="utf-8").read()).body:
        if isinstance(node, ast.Assign):
            names = [t.id for t in node.targets if isinstance(t, ast.Name)] or \
                    [e.id for t in node.targets if isinstance(t, ast.Tuple) for e in t.elts]
            if not set(names) & want:
                continue
            val = ast.literal_eval(node.value)
            if len(names) == 1:
                out[names[0]] = val
            else:
                out.update(zip(names, val))
    missing = want - set(out)
    if missing:
        raise SystemExit(f"dino_stage.py lacks {sorted(missing)}")
    return out


K = stage_consts()
FLOORS, BOXES, PERSONS, SPOTS = [], [], [], []


def W(x, y):
    """post-drop Blender m -> world cm (X, Y)"""
    return -100.0 * x, 100.0 * y


def cm(v):
    """world cm as the file states it (0.1 cm): the offline walk must see the hook's numbers, or float seams between
    adjacent treads (-509.99999999999994 vs -510.00000000000006) open gaps the hook doesn't have"""
    return round(v, 1)


def rect(x0, x1, y0, y1):
    xa, xb = sorted((cm(-100.0 * x0), cm(-100.0 * x1)))
    ya, yb = sorted((cm(100.0 * y0), cm(100.0 * y1)))
    return xa, ya, xb, yb


def floor(name, x0, x1, y0, y1, top, bottom):
    FLOORS.append((*rect(x0, x1, y0, y1), cm(100.0 * top), cm(100.0 * bottom), name))


def box(name, x0, x1, y0, y1, z0, z1):
    BOXES.append((*rect(x0, x1, y0, y1), cm(100.0 * z0), cm(100.0 * z1), name, False))


DECK, FIELD = -1.0, -2.5                                          # post-drop floor tops (m)
DECK_BACK_Y = 10.0                   # walking on the deck stops at the big screen's line (y ~10.3): the strip behind it
                                     # stays out (with CC_MAXB 512 the rest of the backstage fits)
BUTTON = (0.0, 1.52, 0.0, 1.10)      # the giant intro's button pedestal behind the DJ (giant.py BUTTON; post-drop x, y,
                                     # floor, cap height m), not in the stage export
START = (0.0, 1.10)                  # the offline walk starts between the decks table and the pedestal
DECKS_SPOT = (0.0, 0.8, 0.0, -90.0)  # "spot decks": where the DJ stands (post-drop x, y, z m; Unreal yaw: facing -Y, the
                                     # crowd). club.cpp takes the floor rect holding it as the stage (here: the riser)
RISER = (-4.5, 4.5, -2.5, 3.0)                                    # x0, x1, y0, y1 (dino_stage build_riser: 9 x 5.5 m)
RISER_STEPS = [(s, k) for s in (-1, 1) for k in range(4)]         # its side stairs: 0.35 m treads, tops -0.2 .. -0.8
FIELD_RECT = (-31.0, 31.0, -96.0, K["DECK_FRONT_Y"])


def riser_step(s, k):
    xa, xb = sorted((s * (4.5 + 0.35 * k), s * (4.85 + 0.35 * k)))
    return xa, xb, 1.1, 2.9, -0.2 * (k + 1)


def pit_steps():
    """(walkway, i, x0, x1, y0, y1, top) for every tread below the deck edge"""
    out = []
    for wname, (g0, g1) in sorted(K["WALKWAYS"].items()):
        for i in range(1, K["STAIR_N"]):
            ya = K["DECK_FRONT_Y"] - K["STAIR_RUN"] * i
            out.append((wname, i, g0, g1, ya, ya + K["STAIR_RUN"], DECK - K["STAIR_RISE"] * i))
    return out


def build_floors_and_barrier():
    floor("riser", *RISER, 0.0, DECK)
    for s, k in RISER_STEPS:
        xa, xb, ya, yb, top = riser_step(s, k)
        floor(f"riser_step_{'L' if s < 0 else 'R'}{k}", xa, xb, ya, yb, top, DECK)
    floor("deck", -25.0, 25.0, K["DECK_FRONT_Y"], DECK_BACK_Y, DECK, FIELD)
    for wname, i, g0, g1, ya, yb, top in pit_steps():
        floor(f"stairs_{wname}{i}", g0, g1, ya, yb, top, FIELD)
    floor("field", *FIELD_RECT, FIELD, FIELD - 0.5)
    gaps = sorted(K["WALKWAYS"].values())                          # the barrier: 1.2 m tall, a gate per walkway
    xs = [-30.0] + [v for g in gaps for v in g] + [30.0]
    by = K["BARRIER_Y"]
    for j, (x0, x1) in enumerate(zip(xs[0::2], xs[1::2])):
        box(f"barrier{j}", x0, x1, by - 0.125, by + 0.125, FIELD, FIELD + 1.2)
    bx, by_, bf, bh = BUTTON
    box("giant_button", bx - 0.18, bx + 0.18, by_ - 0.18, by_ + 0.18, bf + 0.05, bf + bh)
    sx, sy, sz, syaw = DECKS_SPOT
    SPOTS.append(("decks", *W(sx, sy), 100.0 * sz, syaw))
    fx0, fx1, fy0, fy1 = FIELD_RECT                                # the field's edge (nobody walks off the world)
    box("edge_left", fx0 - 0.3, fx0, fy0, fy1, FIELD, FIELD + 2.0)
    box("edge_right", fx1, fx1 + 0.3, fy0, fy1, FIELD, FIELD + 2.0)
    box("edge_back", fx0, fx1, fy0 - 0.3, fy0, FIELD, FIELD + 2.0)


def band_of(xc, yc):
    """which floor a cell centre (post-drop m) stands on for the wall raster: 'riser', 'deck', 'field' or None (stairs)"""
    x0, x1, y0, y1 = RISER
    if x0 <= xc <= x1 and y0 <= yc <= y1:
        return "riser"
    for s, k in RISER_STEPS:
        xa, xb, ya, yb, _ = riser_step(s, k)
        if xa <= xc <= xb and ya <= yc <= yb:
            return None
    if yc >= K["DECK_FRONT_Y"]:
        return "deck" if -25.0 <= xc <= 25.0 and yc <= DECK_BACK_Y + 0.5 else None
    for _w, _i, g0, g1, ya, yb, _t in pit_steps():
        if g0 <= xc <= g1 and ya <= yc <= yb:
            return None
    return "field"


def components(mask):
    """4-connected components of a boolean raster: a list of (iy array, ix array)"""
    lab = np.zeros(mask.shape, int)
    out = []
    ny, nx = mask.shape
    for iy, ix in zip(*np.nonzero(mask)):
        if lab[iy, ix]:
            continue
        n = len(out) + 1
        lab[iy, ix] = n
        st, cells = [(iy, ix)], []
        while st:
            a, b = st.pop()
            cells.append((a, b))
            for da, db in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                p, q = a + da, b + db
                if 0 <= p < ny and 0 <= q < nx and mask[p, q] and not lab[p, q]:
                    lab[p, q] = n
                    st.append((p, q))
        cy, cx = np.array(cells).T
        out.append((cy, cx))
    return out


def cover(cy, cx, fill=0.45, small=25, depth=0):
    """boxes (iy0, iy1, ix0, ix1) covering these cells: their bounding box when it is mostly filled or small, else the
    two halves along the longer side, recursively (a diagonal bone becomes a chain of small boxes, not one big one)"""
    iy0, iy1, ix0, ix1 = cy.min(), cy.max(), cx.min(), cx.max()
    area = (iy1 - iy0 + 1) * (ix1 - ix0 + 1)
    if len(cy) >= fill * area or area <= small or depth > 12:
        return [(iy0, iy1, ix0, ix1)]
    if iy1 - iy0 >= ix1 - ix0:
        mid = (iy0 + iy1) // 2
        lo = cy <= mid
    else:
        mid = (ix0 + ix1) // 2
        lo = cx <= mid
    out = []
    for sel in (lo, ~lo):
        if sel.any():
            out += cover(cy[sel], cx[sel], fill, small, depth + 1)
    return out


def build_walls(ex):
    x0, y0, c = float(ex["x0"]), float(ex["y0"]), float(ex["c"])
    occ = {b: ex["occ_" + b] for b in ("riser", "deck", "field")}
    ny, nx = occ["deck"].shape
    xs = x0 + (np.arange(nx) + 0.5) * c
    ys = y0 + (np.arange(ny) + 0.5) * c
    band = np.empty((ny, nx), dtype=object)
    for iy, yc in enumerate(ys):
        for ix, xc in enumerate(xs):
            band[iy, ix] = band_of(xc, yc)
    zmax = np.full((ny, nx), np.nan)
    base = np.full((ny, nx), np.nan)
    for b, f in (("riser", 0.0), ("deck", DECK), ("field", FIELD)):
        sel = (band == b) & np.isfinite(occ[b])
        zmax[sel] = occ[b][sel]
        base[sel] = f
    wall = np.isfinite(zmax)
    comps = components(wall)
    for fill in (0.6, 0.5, 0.45, 0.4, 0.35):                       # looser until the boxes fit the hook's table
        rects = [r for cy, cx in comps for r in cover(cy, cx, fill)]
        if len(rects) + len(BOXES) <= MAX_BOXES:
            break
    print(f"[MAP] walls: {int(wall.sum())} cells at {c * 100:.0f} cm, {len(comps)} objects -> {len(rects)} boxes "
          f"(fill >= {fill:.2f})")
    for k, (iy0, iy1, ix0, ix1) in enumerate(rects):
        blk = wall[iy0:iy1 + 1, ix0:ix1 + 1]
        z1 = float(np.nanmax(np.where(blk, zmax[iy0:iy1 + 1, ix0:ix1 + 1], np.nan)))
        f = float(np.nanmin(np.where(blk, base[iy0:iy1 + 1, ix0:ix1 + 1], np.nan)))
        box(f"w{k}", x0 + ix0 * c, x0 + (ix1 + 1) * c, y0 + iy0 * c, y0 + (iy1 + 1) * c,
            f + KNEE / 100.0 + 0.01, max(z1, f + KNEE / 100.0 + 0.06))


def build_people(ex):
    P = np.asarray(ex["people"])
    gates = [((g0 + g1) / 2, K["BARRIER_Y"]) for g0, g1 in K["WALKWAYS"].values()]
    on_deck = P[:, 2] > DECK - 0.3
    d = np.min([np.hypot(P[:, 0] - gx, P[:, 1] - gy) for gx, gy in gates], axis=0)
    order = [i for i in np.argsort(d) if not on_deck[i]]
    keep = list(np.where(on_deck)[0]) + order[:MAX_PEOPLE - int(on_deck.sum())]
    for n, i in enumerate(keep):
        x, y, fz = P[i]
        X, Y = W(x, y)
        PERSONS.append((cm(X), cm(Y), DANCER_R, cm(100.0 * fz), cm(100.0 * fz + 180.0), f"p{n}"))
    far = float(np.max(d[keep])) if len(keep) else 0.0
    print(f"[MAP] people: {len(P)} dancers, {int(on_deck.sum())} on the stage; kept {len(keep)} (out to {far:.1f} m "
          f"from a gate)")


# ---------------------------------------------------------------------------- the hook's rules (club_collide.py's Map)
def sdist_box(X0, Y0, X1, Y1, x, y):
    dx, dy = max(X0 - x, 0.0, x - X1), max(Y0 - y, 0.0, y - Y1)
    if dx > 0.0 or dy > 0.0:
        return math.hypot(dx, dy)
    return -min(x - X0, X1 - x, y - Y0, Y1 - y)


class Map:
    B = 100.0

    def __init__(self):
        self.buckets = {}
        for kind, items in (("f", FLOORS), ("b", BOXES), ("p", PERSONS)):
            for i, s in enumerate(items):
                if kind == "p":
                    x0, y0, x1, y1 = s[0] - s[2], s[1] - s[2], s[0] + s[2], s[1] + s[2]
                else:
                    x0, y0, x1, y1 = s[0], s[1], s[2], s[3]
                pad = RADIUS + GRID + 1.0
                for bx in range(int(math.floor((x0 - pad) / self.B)), int(math.floor((x1 + pad) / self.B)) + 1):
                    for by in range(int(math.floor((y0 - pad) / self.B)), int(math.floor((y1 + pad) / self.B)) + 1):
                        self.buckets.setdefault((bx, by), []).append((kind, i))

    def near(self, x, y):
        return self.buckets.get((int(math.floor(x / self.B)), int(math.floor(y / self.B))), ())

    def floor_at(self, x, y, cur):
        best = None
        for kind, i in self.near(x, y):
            if kind != "f":
                continue
            X0, Y0, X1, Y1, top, _bot, _n = FLOORS[i]
            if X0 <= x <= X1 and Y0 <= y <= Y1 and cur - STEP <= top <= cur + STEP and (best is None or top > best):
                best = top
        return best

    def wall_hit(self, px, py, qx, qy, cur):
        lo, hi = cur + KNEE, cur + HEAD
        for kind, i in self.near(qx, qy):
            if kind == "f":
                X0, Y0, X1, Y1, top, bot, name = FLOORS[i]
                if not (top > cur + STEP and bot < cur + HEAD):
                    continue
                dq, dp = sdist_box(X0, Y0, X1, Y1, qx, qy), sdist_box(X0, Y0, X1, Y1, px, py)
            elif kind == "b":
                X0, Y0, X1, Y1, z0, z1, name, _gate = BOXES[i]
                if z1 <= lo or z0 >= hi:
                    continue
                dq, dp = sdist_box(X0, Y0, X1, Y1, qx, qy), sdist_box(X0, Y0, X1, Y1, px, py)
            else:
                X, Y, _r, z0, z1, name = PERSONS[i]
                if z1 <= lo or z0 >= hi:
                    continue
                dq, dp = math.hypot(qx - X, qy - Y), math.hypot(px - X, py - Y)
                if dq < CORE and dq < dp - 0.01:
                    return name
                continue
            if dq < RADIUS and dq < dp - 0.01:
                return name
        return None

    def try_move(self, px, py, qx, qy, cur):
        nf = self.floor_at(qx, qy, cur)
        if nf is None or self.wall_hit(px, py, qx, qy, cur):
            return None
        return nf


def walk(m, start, ylimit):
    """flood fill on the 10 cm grid from start (X, Y, floor top), not past world Y < ylimit (the check's window)"""
    sx, sy, sz = start
    s0 = (round(sx / GRID), round(sy / GRID), sz)
    seen, rev, q = {s0}, {}, deque([s0])
    while q:
        ix, iy, cur = st = q.popleft()
        px, py = ix * GRID, iy * GRID
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            qy = py + dy * GRID
            if qy < ylimit:
                continue
            nf = m.try_move(px, py, px + dx * GRID, qy, cur)
            if nf is None:
                continue
            nx_ = (ix + dx, iy + dy, nf)
            rev.setdefault(nx_, []).append(st)
            if nx_ not in seen:
                seen.add(nx_)
                q.append(nx_)
    return s0, seen, rev


def returners(s0, rev):
    back, q = {s0}, deque([s0])
    while q:
        st = q.popleft()
        for p in rev.get(st, ()):
            if p not in back:
                back.add(p)
                q.append(p)
    return back


def reached_near(states, X, Y, top, tol=30.0):
    return any(abs(ix * GRID - X) <= tol and abs(iy * GRID - Y) <= tol and abs(cur - top) < 1.0 for ix, iy, cur in states)


def check(m):
    ok = True

    def say(passed, msg):
        nonlocal ok
        ok &= bool(passed)
        print(f"[CHECK] {'PASS' if passed else 'FAIL'}  {msg}")
    dj = (*W(*START), 0.0)
    ylimit = 100.0 * -20.0                                         # the walk's window: the stage + 12 m of the crowd
    s0, host, rev = walk(m, dj, ylimit)
    back = returners(s0, rev)
    stuck = host - back
    say(not stuck, f"from the decks: {len(host)} grid states reached, {len(stuck)} with no way back")
    for wname, (g0, g1) in sorted(K["WALKWAYS"].items()):
        xc = (g0 + g1) / 2
        X, Y = W(xc, K["BARRIER_Y"] - 1.5)
        say(reached_near(host, X, Y, 100.0 * FIELD), f"walkway {wname}: through its gate into the crowd "
                                                     f"({xc:.1f}, {K['BARRIER_Y'] - 1.5:.1f})")
        X, Y = W(xc, K["DECK_FRONT_Y"] - K["STAIR_RUN"] * (K["STAIR_N"] - 0.5))
        say(reached_near(host, X, Y, 100.0 * FIELD, tol=40.0), f"walkway {wname}: down its stairs to the pit")
    field = {(ix, iy) for ix, iy, cur in host if abs(cur - 100.0 * FIELD) < 1.0}
    deck = {(ix, iy) for ix, iy, cur in host if abs(cur - 100.0 * DECK) < 1.0}
    print(f"[CHECK] reached: deck {len(deck) * GRID * GRID / 1e4:.0f} m2, crowd field (to y -20) "
          f"{len(field) * GRID * GRID / 1e4:.0f} m2")
    return ok, host


def draw(path, host):
    from PIL import Image, ImageDraw
    xa, xb, ya, yb = -27.0, 27.0, -20.0, 14.0                      # Blender m window, stage right on the image's right
    S = 24                                                         # px per m
    Wd, Hd = int((xb - xa) * S), int((yb - ya) * S)
    img = Image.new("RGB", (Wd, Hd), (18, 18, 22))
    d = ImageDraw.Draw(img, "RGBA")

    def px(X, Y):                                                  # world cm -> pixel (Blender x = -X / 100)
        return (-X / 100.0 - xa) * S, (yb - Y / 100.0) * S

    def rect_(X0, Y0, X1, Y1, fill=None, outline=None):
        a, b = px(X0, Y0), px(X1, Y1)
        d.rectangle([min(a[0], b[0]), min(a[1], b[1]), max(a[0], b[0]), max(a[1], b[1])], fill=fill, outline=outline)
    for X0, Y0, X1, Y1, top, _b, name in sorted(FLOORS, key=lambda f: f[4]):
        g = int(40 + (top + 250.0) / 250.0 * 70)
        rect_(X0, Y0, X1, Y1, fill=(g, g, g + 8))
    for ix, iy, cur in host:
        a = px(ix * GRID, iy * GRID)
        d.rectangle([a[0] - 1, a[1] - 1, a[0] + 1, a[1] + 1], fill=(40, 170, 90, 120))
    for X0, Y0, X1, Y1, z0, z1, name, _g in BOXES:
        rect_(X0, Y0, X1, Y1, fill=(200, 60, 50, 170))
    for X, Y, r, *_ in PERSONS:
        a = px(X, Y)
        d.ellipse([a[0] - 2, a[1] - 2, a[0] + 2, a[1] + 2], fill=(90, 140, 255, 200))
    a = px(*W(0.0, 0.8))
    d.ellipse([a[0] - 6, a[1] - 6, a[0] + 6, a[1] + 6], outline=(255, 255, 255), width=2)
    d.text((a[0] + 9, a[1] - 7), "you (decks)", fill=(255, 255, 255))
    for wname, (g0, g1) in sorted(K["WALKWAYS"].items()):
        b = px(*W((g0 + g1) / 2, K["BARRIER_Y"] - 0.6))
        d.text((b[0] - 18, b[1] + 4), f"walkway {wname}", fill=(255, 220, 90))
    d.text((8, 8), "green = where you can walk (from the decks, to 12 m into the crowd); red = walls; blue = dancers",
           fill=(230, 230, 230))
    img.save(path)


def write(path):
    lines = ["# Dino Stage walking map (Scripts/Blender/dino_walk/dino_collide.py): world cm, the club's format",
             f"rules {STEP:g} {HEAD:g} {KNEE:g} {RADIUS:g} {CORE:g}"]
    for X0, Y0, X1, Y1, top, bot, name in FLOORS:
        lines.append(f"floor {X0:.1f} {Y0:.1f} {X1:.1f} {Y1:.1f} {top:.1f} {bot:.1f} {name}")
    for X0, Y0, X1, Y1, z0, z1, name, _g in BOXES:
        lines.append(f"box {X0:.1f} {Y0:.1f} {X1:.1f} {Y1:.1f} {z0:.1f} {z1:.1f} {name}")
    for X, Y, r, z0, z1, name in PERSONS:
        lines.append(f"person {X:.1f} {Y:.1f} {r:.1f} {z0:.1f} {z1:.1f} {name}")
    for name, X, Y, Z, yaw in SPOTS:
        lines.append(f"spot {name} {X:.1f} {Y:.1f} {Z:.1f} {yaw:.1f}")
    open(path, "w", newline="\n").write("\n".join(lines) + "\n")
    return len(lines)


def main():
    ex = np.load(sys.argv[1], allow_pickle=False)
    out = sys.argv[2] if len(sys.argv) > 2 else os.path.join(HERE, "out")
    os.makedirs(out, exist_ok=True)
    build_floors_and_barrier()
    build_walls(ex)
    build_people(ex)
    print(f"[MAP] {len(FLOORS)} floors, {len(BOXES)} boxes, {len(PERSONS)} people, {len(SPOTS)} spot(s) "
          f"(hook limits {LIMIT_F} / {LIMIT_B} / {LIMIT_P})")
    if len(FLOORS) > LIMIT_F or len(BOXES) > LIMIT_B or len(PERSONS) > LIMIT_P:
        raise SystemExit("over the hook's limits")
    n = write(os.path.join(out, "dino_collide.txt"))
    size = os.path.getsize(os.path.join(out, "dino_collide.txt"))
    print(f"[MAP] file {size} bytes (club.cpp reads up to {MAP_BYTES})")
    if size >= MAP_BYTES:
        raise SystemExit("too big for club.cpp's read buffer")
    ok, host = check(Map())
    draw(os.path.join(out, "dino_collide_check.png"), host)
    print(f"[MAP] wrote {n} lines -> {os.path.join(out, 'dino_collide.txt')}; check {'PASS' if ok else 'FAIL'}")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
