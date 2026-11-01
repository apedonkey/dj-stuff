"""REACTOR walking (plan section 5.3): writes club_collide.txt for hook/club.cpp (world cm), checks it with an offline
walk under the hook's rules (a 10 cm grid flood fill: the host with the gate open, a guest with it shut) and draws a
top-down check image. Plain Python + PIL (no bpy).

    python club_collide.py [out_dir]          (default: ./out_club)

Frame: the club frame (Blender m, club_layout.py) -> Unreal world cm = (-100x, 100y, 100z). The FBX import flips Y and
build_club.py turns the level 180 deg (its log: "screen centre y=-540 cm -> level yaw 180"), so the airlock (club
x -12..-8) is at world X +800..+1200, on the DJ's right.

club_collide.txt, one shape per line (world cm, '#' starts a comment):
  rules  step head knee radius core     cm (core: a person's solid core, see below)
  floor  x0 y0 x1 y1 top bottom name    the walkable top of a solid that reaches down to `bottom`
  box    x0 y0 x1 y1 z0 z1 name         blocks bodies whose height range overlaps z0..z1
  gate   x0 y0 x1 y1 z0 z1 name         a box that, while shut, blocks only moves toward +Y (onto the stage)
  circle x y r z0 z1 name
  person x y r z0 z1 name               a dancer: soft (r = their shoulders), solid only within `core` of the spine
  spot   name x y z yaw                 yaw in degrees, Unreal's convention (0 = +X, 90 = +Y)
The rules (hook/club_collide.h and Map below implement them the same way): the floor under you is the highest floor
rect holding your head's XY whose top is within `step` of the floor you are on; a move with no such floor (a drop or a
climb) is refused. A floor rect whose top is more than `step` above you and whose solid reaches below cur+head is a
wall. Boxes, gates and circles whose z range overlaps cur+knee..cur+head are walls. A wall refuses a move that ends
within `radius` of it AND closer than before (signed distance: deeper inside counts as closer), so you can always back
out of an overlap that room-scale walking made. A person refuses a move only within `core` of their centre (and closer
than before): you walk into the crowd, and the hook slows you near people and steers you round them (that part does not
change what is reachable). A refused move is retried along X only, then along Y only (sliding).
"""
import math
import os
import random
import sys
from collections import deque

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import club_layout as L  # noqa: E402
from club_spots import club_people  # noqa: E402

STEP, HEAD, KNEE, RADIUS = 45.0, 190.0, 25.0, 20.0     # cm: the rules line
PERSON_CORE = 15.0                                      # cm: the solid core round a dancer's spine (the rest is soft)
DANCER_R = 0.25                                         # m: a dancer's shoulders (crowd v3 people are ~0.5 m wide)
GRID = 10.0                                             # cm: the offline walk's grid

FLOORS, BOXES, CIRCLES, PERSONS, SPOTS = [], [], [], [], []


def _rect(x0, x1, y0, y1):
    """club-frame x and y ranges (either order) -> world (X0, Y0, X1, Y1) with X0 <= X1, Y0 <= Y1"""
    xa, xb = sorted((-100.0 * x0, -100.0 * x1))
    ya, yb = sorted((100.0 * y0, 100.0 * y1))
    return xa, ya, xb, yb


def floor(name, x0, x1, y0, y1, top, bottom):
    FLOORS.append((*_rect(x0, x1, y0, y1), 100.0 * top, 100.0 * bottom, name))


def box(name, x0, x1, y0, y1, z0, z1, gate=False):
    BOXES.append((*_rect(x0, x1, y0, y1), 100.0 * z0, 100.0 * z1, name, gate))


def circle(name, x, y, r, z0, z1):
    CIRCLES.append((-100.0 * x, 100.0 * y, 100.0 * r, 100.0 * z0, 100.0 * z1, name))


def person(name, x, y, r, z0, z1):
    PERSONS.append((-100.0 * x, 100.0 * y, 100.0 * r, 100.0 * z0, 100.0 * z1, name))


def spot_world(name, X, Y, Z, yaw):
    SPOTS.append((name, X, Y, Z, yaw))


def build():
    """Every shape, from club_layout.py and the same numbers club_stage.py builds with (its section noted per group).
    'Left' and 'right' are as seen from the dance floor facing the stage: left = club -x = the airlock side."""
    F, C9, SC = L.FLOOR, L.CEIL, L.STAGE_CEIL
    # floors ------------------------------------------------------------------------------------------------------
    floor("hall", -L.HX, L.HX, L.Y_BACK, L.LIP_Y, F, F - 0.2)
    floor("stage", -L.HX, L.HX, L.LIP_Y, L.Y_SCREENWALL - 0.2, 0.0, F)          # deck + wings (the bay is shut)
    floor("corridor", L.EX0, L.EX1, L.Y_BACK - L.EX_DEPTH, L.Y_BACK, F, F - 0.2)
    for sx, side in ((-1, "left"), (1, "right")):
        floor(f"mezz_{side}", sx * L.MZ_X0, sx * L.MZ_X1, L.MZ_Y0, L.MZ_Y1, L.MZ_Z, L.MZ_Z - 0.3)
    rise = (0.0 - F) / L.STAIR_N                                                  # build_stage: the airlock stairs
    for i in range(L.STAIR_N):
        y0 = L.STAIR_Y0 + 0.3 * i
        y1 = L.LIP_Y if i == L.STAIR_N - 1 else y0 + 0.3
        floor(f"airlock_step{i + 1}", L.AIR_X0 + 0.4, L.AIR_X1 - 0.4, y0, y1, F + rise * (i + 1), F)
    n = 20                                                                        # build_mezz: stairs along the walls
    for sx, side in ((-1, "left"), (1, "right")):
        for i in range(n):
            y0 = L.MZ_STAIR_Y0 + 0.3 * i
            y1 = L.MZ_Y0 if i == n - 1 else y0 + 0.3
            floor(f"mezz_{side}_step{i + 1}", sx * 10.6, sx * 11.9, y0, y1, F + (L.MZ_Z - F) * (i + 1) / n, F)
    # the shell (build_hall, build_bar) ---------------------------------------------------------------------------
    for sx, side in ((-1, "left"), (1, "right")):
        box(f"wall_{side}", sx * L.HX, sx * (L.HX + 0.4), L.Y_BACK - 0.4, L.Y_BAY + 0.4, F - 1.0, SC + 1.0)
    box("wall_back_left", -L.HX - 0.4, L.EX0, L.Y_BACK - 0.4, L.Y_BACK, F - 1.0, C9)
    box("wall_back_right", L.EX1, L.HX + 0.4, L.Y_BACK - 0.4, L.Y_BACK, F - 1.0, C9)
    ye = L.Y_BACK - L.EX_DEPTH
    box("corridor_left", L.EX0 - 0.4, L.EX0, ye, L.Y_BACK, F - 1.0, F + L.EX_H)
    box("corridor_right", L.EX1, L.EX1 + 0.4, ye, L.Y_BACK, F - 1.0, F + L.EX_H)
    box("corridor_end", L.EX0 - 0.4, L.EX1 + 0.4, ye - 0.4, ye, F - 1.0, F + L.EX_H)
    box("bay_wall", -L.HX, L.HX, L.Y_SCREENWALL - 0.2, L.Y_SCREENWALL + 0.2, -1.0, SC)   # screen line: bay shut
    for sx, side in ((-1, "left"), (1, "right")):
        for cy in L.COL_Y:
            if sx < 0 and cy > L.AIR_Y0 - 1.0:                                    # none at the airlock
                continue
            top = C9 if cy < L.LIP_Y else SC
            box(f"column_{side}{cy:.0f}", sx * (L.HX - 0.6), sx * L.HX, cy - 0.3, cy + 0.3, F, top)
    # stage, barrier, airlock (build_stage) -----------------------------------------------------------------------
    box("barrier", -L.STAGE_HW - 0.04, L.STAGE_HW + 0.04, L.BARRIER_Y - 0.06, L.BARRIER_Y + 0.06, F, F + 1.1)
    for i in range(9):
        x = -L.STAGE_HW + i * 2
        box(f"barrier_post{i + 1}", x - 0.04, x + 0.04, L.BARRIER_Y - 0.25, L.BARRIER_Y + 0.25, F, F + 1.1)
    box("airlock_wall_left", L.AIR_X0, L.DOOR_X0, L.AIR_Y0 - 0.15, L.AIR_Y0 + 0.15, F, L.LINTEL_TOP)
    box("airlock_wall_right", L.DOOR_X1, L.AIR_X1, L.AIR_Y0 - 0.15, L.AIR_Y0 + 0.15, F, L.LINTEL_TOP)
    box("airlock_glass", L.AIR_X1 - 0.025, L.AIR_X1 + 0.025, L.AIR_Y0, L.AIR_Y1, F, L.LINTEL_TOP)
    box("airlock_door", L.DOOR_X0, L.DOOR_X1, L.AIR_Y0 - 0.26, L.AIR_Y0 + 0.15, F, L.DOOR_TOP, gate=True)
    box("wing_rail", L.STAGE_HW, L.HX, L.LIP_Y, L.LIP_Y + 0.1, 0.0, 1.1)
    T = L.TABLE
    box("console", T["x0"] - 0.06, T["x1"] + 0.06, T["y0"] - 0.06, T["y1"] + 0.06, 0.0, T["top"] + 0.02)
    for sx in (-1, 1):
        circle("rod", sx * L.ROD_X, L.ROD_Y, 0.28, 0.0, 3.75)
    # the bar (build_bar) -----------------------------------------------------------------------------------------
    box("bar_counter", L.BAR_X0 - 0.1, L.BAR_X1 + 0.1, L.BAR_Y - 0.5, L.BAR_Y + 0.5, F, F + 1.15)
    box("back_bar", L.BAR_X0, L.BAR_X1, L.Y_BACK, L.Y_BACK + 0.45, F + 1.25, F + 2.6)
    for k in range(12):
        circle("stool", L.BAR_X0 + 0.5 + k * (L.BAR_X1 - L.BAR_X0 - 1.0) / 11, L.BAR_Y - 0.95, 0.18, F, F + 0.75)
    # mezzanines and the lounge under them (build_mezz) -----------------------------------------------------------
    for sx, side in ((-1, "left"), (1, "right")):
        box(f"mezz_{side}_rail", sx * L.MZ_X0, sx * (L.MZ_X0 + 0.16), L.MZ_Y0, L.MZ_Y1, L.MZ_Z, L.MZ_Z + 1.15)
        box(f"mezz_{side}_front_rail", sx * L.MZ_X0, sx * L.MZ_X1, L.MZ_Y1 - 0.16, L.MZ_Y1, L.MZ_Z, L.MZ_Z + 1.15)
        for y in (-23.5, -19.5, -15.5, -11.5, -8.5):
            box(f"mezz_{side}_support", sx * (L.MZ_X0 + 0.15), sx * (L.MZ_X0 + 0.45), y - 0.15, y + 0.15, F, L.MZ_Z - 0.3)
        circle("laser_pole", sx * 8.4, L.MZ_Y1 - 0.2, 0.06, L.MZ_Z, 4.6)
        for y in (-21.0, -15.0, -9.8):
            box(f"lounge_{side}_sofa", sx * 10.9, sx * 11.875, y - 1.3, y + 1.3, F, F + 0.9)
            box(f"lounge_{side}_table", sx * 9.95, sx * 10.65, y - 0.5, y + 0.5, F, F + 0.45)
    # the crowd (club_spots: the same people the bake places) -----------------------------------------------------
    for x, y, _yaw, _pose, z in club_people(random.Random(11)):
        person("dancer", x, y, DANCER_R, z, z + 1.8)
    # spots -------------------------------------------------------------------------------------------------------
    spot_world("decks", -6.0, 87.0, 0.0, -90.0)                       # PlayerStartDJ (Session 3t), facing the crowd
    spot_world("guest_stage", -6.0, -58.0, 0.0, 90.0)                 # PlayerStartTeacher: where Tribe puts guests
    spot_world("guest_floor", -100.0 * L.DOOR_MID, 100.0 * (L.AIR_Y0 - 1.6), 100.0 * F, 90.0)   # outside the door


def write_txt(path):
    with open(path, "w", encoding="ascii", newline="\n") as f:
        f.write("# REACTOR collision for hook/club.cpp: world cm (club frame (x, y, z) m -> (-100x, 100y, 100z)).\n")
        f.write("# Written by Scripts/Blender/club/club_collide.py from club_layout.py and club_spots.py: do not edit.\n")
        f.write(f"rules {STEP:g} {HEAD:g} {KNEE:g} {RADIUS:g} {PERSON_CORE:g}\n")
        for X0, Y0, X1, Y1, top, bot, name in FLOORS:
            f.write(f"floor {X0:.1f} {Y0:.1f} {X1:.1f} {Y1:.1f} {top:.1f} {bot:.1f} {name}\n")
        for X0, Y0, X1, Y1, z0, z1, name, gate in BOXES:
            f.write(f"{'gate' if gate else 'box'} {X0:.1f} {Y0:.1f} {X1:.1f} {Y1:.1f} {z0:.1f} {z1:.1f} {name}\n")
        for X, Y, r, z0, z1, name in CIRCLES:
            f.write(f"circle {X:.1f} {Y:.1f} {r:.1f} {z0:.1f} {z1:.1f} {name}\n")
        for X, Y, r, z0, z1, name in PERSONS:
            f.write(f"person {X:.1f} {Y:.1f} {r:.1f} {z0:.1f} {z1:.1f} {name}\n")
        for name, X, Y, Z, yaw in SPOTS:
            f.write(f"spot {name} {X:.1f} {Y:.1f} {Z:.1f} {yaw:.1f}\n")


def read_txt(path):
    """Load the shapes back from the file, so the offline walk runs on exactly what the hook reads (0.1 cm rounding),
    and tests/club_collide_test.cpp on the headset can be compared with it state for state."""
    global STEP, HEAD, KNEE, RADIUS, PERSON_CORE
    for lst in (FLOORS, BOXES, CIRCLES, PERSONS, SPOTS):
        lst.clear()
    with open(path, encoding="ascii") as f:
        for line in f:
            t = line.split()
            if not t or t[0].startswith("#"):
                continue
            if t[0] == "rules":
                STEP, HEAD, KNEE, RADIUS = (float(v) for v in t[1:5])
                if len(t) > 5:
                    PERSON_CORE = float(t[5])
            elif t[0] == "floor":
                FLOORS.append((*(float(v) for v in t[1:7]), t[7]))
            elif t[0] in ("box", "gate"):
                BOXES.append((*(float(v) for v in t[1:7]), t[7], t[0] == "gate"))
            elif t[0] == "circle":
                CIRCLES.append((*(float(v) for v in t[1:6]), t[6]))
            elif t[0] == "person":
                PERSONS.append((*(float(v) for v in t[1:6]), t[6]))
            elif t[0] == "spot":
                SPOTS.append((t[1], *(float(v) for v in t[2:6])))
            else:
                raise ValueError(f"club_collide.txt: unknown line {line!r}")


# ---------------------------------------------------------------- the rules, for the offline walk
def sdist_box(x0, y0, x1, y1, x, y):
    """signed distance from (x, y) to the rect: positive outside, minus the depth inside"""
    dx, dy = max(x0 - x, 0.0, x - x1), max(y0 - y, 0.0, y - y1)
    if dx > 0.0 or dy > 0.0:
        return math.hypot(dx, dy)
    return -min(x - x0, x1 - x, y - y0, y1 - y)


class Map:
    """Shapes bucketed on a 1 m grid (each under every bucket its reach touches), the hook's rules on top."""
    B = 100.0

    def __init__(self):
        self.buckets = {}
        for kind, items in (("f", FLOORS), ("b", BOXES), ("c", CIRCLES), ("p", PERSONS)):
            for i, s in enumerate(items):
                if kind in ("c", "p"):
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

    def wall_hit(self, px, py, qx, qy, cur, gate_open):
        """the first wall that refuses the move p -> q (name), or None"""
        lo, hi = cur + KNEE, cur + HEAD
        for kind, i in self.near(qx, qy):
            if kind == "f":
                X0, Y0, X1, Y1, top, bot, name = FLOORS[i]
                if not (top > cur + STEP and bot < cur + HEAD):
                    continue
                dq, dp = sdist_box(X0, Y0, X1, Y1, qx, qy), sdist_box(X0, Y0, X1, Y1, px, py)
            elif kind == "b":
                X0, Y0, X1, Y1, z0, z1, name, gate = BOXES[i]
                if z1 <= lo or z0 >= hi or (gate and (gate_open or qy <= py)):
                    continue
                dq, dp = sdist_box(X0, Y0, X1, Y1, qx, qy), sdist_box(X0, Y0, X1, Y1, px, py)
            elif kind == "c":
                X, Y, r, z0, z1, name = CIRCLES[i]
                if z1 <= lo or z0 >= hi:
                    continue
                dq, dp = math.hypot(qx - X, qy - Y) - r, math.hypot(px - X, py - Y) - r
            else:
                X, Y, _r, z0, z1, name = PERSONS[i]
                if z1 <= lo or z0 >= hi:
                    continue
                dq, dp = math.hypot(qx - X, qy - Y), math.hypot(px - X, py - Y)
                if dq < PERSON_CORE and dq < dp - 0.01:
                    return name
                continue
            if dq < RADIUS and dq < dp - 0.01:
                return name
        return None

    def try_move(self, px, py, qx, qy, cur, gate_open):
        """the new floor if p -> q is allowed, else None"""
        nf = self.floor_at(qx, qy, cur)
        if nf is None or self.wall_hit(px, py, qx, qy, cur, gate_open):
            return None
        return nf


def walk(m, start, gate_open):
    """flood fill on the 10 cm grid from start (X, Y, floor top). Returns (reached states, reverse edges)."""
    sx, sy, sz = start
    s0 = (round(sx / GRID), round(sy / GRID), sz)
    seen, rev, q = {s0}, {}, deque([s0])
    while q:
        ix, iy, cur = st = q.popleft()
        px, py = ix * GRID, iy * GRID
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            nf = m.try_move(px, py, px + dx * GRID, py + dy * GRID, cur, gate_open)
            if nf is None:
                continue
            nx = (ix + dx, iy + dy, nf)
            rev.setdefault(nx, []).append(st)
            if nx not in seen:
                seen.add(nx)
                q.append(nx)
    return s0, seen, rev


def returners(s0, rev):
    """states that can walk back to s0 (reverse flood fill)"""
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
    """The offline walk: True if every check passes. Prints one line per check."""
    ok = True
    spots = {s[0]: s for s in SPOTS}

    def at(name):
        _n, X, Y, Z, _yaw = spots[name]
        return X, Y, Z

    def say(passed, msg):
        nonlocal ok
        ok &= passed
        print(f"  [{'PASS' if passed else 'FAIL'}] {msg}")

    for name in spots:                                                       # every spot stands on a floor, clear
        X, Y, Z = at(name)
        f = m.floor_at(X, Y, Z)
        say(f is not None and abs(f - Z) < 1.0 and m.wall_hit(X, Y + 5.0, X, Y, Z, True) is None,
            f"spot {name} ({X:.0f}, {Y:.0f}) stands on its floor ({f}) and clear of walls")
    # the host: gate open, from the decks
    s0, host, rev = walk(m, at("decks"), True)
    back = returners(s0, rev)
    stuck = host - back
    say(not stuck, f"host: {len(host)} grid states reached from the decks, {len(stuck)} with no way back")
    targets = (("dance floor centre", 0.0, -12.0, L.FLOOR), ("bar, hall side", -2.0, -26.4, L.FLOOR),
               ("bar, stool side", -2.0, -29.4, L.FLOOR), ("back floor", 0.0, -22.0, L.FLOOR),
               ("corridor end", 6.5, -35.2, L.FLOOR), ("left mezzanine", -10.0, -16.0, L.MZ_Z),
               ("right mezzanine", 10.0, -16.0, L.MZ_Z), ("airlock top step", -10.0, -3.15, 0.0),
               ("right wing", 10.0, 2.0, 0.0), ("left wing", -10.0, 2.0, 0.0), ("lounge left", -9.4, -15.0, L.FLOOR),
               ("guest floor spot", L.DOOR_MID, L.AIR_Y0 - 1.6, L.FLOOR))
    for label, x, y, z in targets:
        say(reached_near(host, -100.0 * x, 100.0 * y, 100.0 * z), f"host reaches the {label}")
    # into the crowd (the user, 2026-10-09: "i can barely get in the crowd"): the front row behind the barrier, and
    # nearly all of the dance floor, only the dancers' solid cores excluded
    say(reached_near(host, 0.0, 100.0 * (L.BARRIER_Y - 0.35), 100.0 * L.FLOOR, tol=15.0),
        "host reaches the front row's centre, behind the barrier")
    fx0, fx1, fy0, fy1 = -730.0, 730.0, -1800.0, 100.0 * (L.BARRIER_Y - 0.3)   # the dance floor (world cm)
    cells = [(ix, iy) for ix in range(int(fx0 // GRID), int(fx1 // GRID) + 1) for iy in range(int(fy0 // GRID), int(fy1 // GRID) + 1)]
    free = [c for c in cells if all(math.hypot(c[0] * GRID - p[0], c[1] * GRID - p[1]) >= PERSON_CORE for p in PERSONS)]
    hall_reached = {(ix, iy) for ix, iy, cur in host if abs(cur - 100.0 * L.FLOOR) < 1.0}
    got = sum(1 for c in free if c in hall_reached)
    say(got >= 0.97 * len(free), f"host walks {100.0 * got / len(free):.1f}% of the dance floor outside the dancers' cores "
                                 f"({len(PERSONS)} people)")
    # area per floor kind, reached vs total
    for prefix in ("hall", "stage", "mezz_left", "mezz_right", "corridor"):
        tot = sum((f[2] - f[0]) * (f[3] - f[1]) for f in FLOORS if f[6] == prefix) / 1e4
        top = next(f[4] for f in FLOORS if f[6] == prefix)
        X0, Y0, X1, Y1 = next(f[:4] for f in FLOORS if f[6] == prefix)
        got = sum(1 for ix, iy, cur in host if abs(cur - top) < 1.0 and X0 <= ix * GRID <= X1 and Y0 <= iy * GRID <= Y1)
        print(f"         {prefix:10s} {got * GRID * GRID / 1e4:6.1f} of {tot:6.1f} m2 walkable (head positions)")
    # a guest: gate shut. From the floor the stage stays out of reach; from Tribe's guest spawn the floor is reachable.
    _s, guest, _r = walk(m, at("guest_floor"), False)
    on_stage = [s for s in guest if abs(s[2]) < 1.0 and s[1] * GRID > 100.0 * L.LIP_Y]
    say(not on_stage, f"guest from the floor: {len(guest)} states, {len(on_stage)} on the stage (the gate holds)")
    say(reached_near(guest, -100.0 * L.DOOR_MID, 100.0 * (L.AIR_Y0 + 0.3), 100.0 * L.FLOOR, tol=25.0) is False,
        "guest from the floor never gets inside the airlock (its landing)")
    say(reached_near(host, -100.0 * L.DOOR_MID, 100.0 * (L.AIR_Y0 + 0.3), 100.0 * L.FLOOR, tol=25.0),
        "the host does get onto the airlock's landing")
    _s, out, _r = walk(m, at("guest_stage"), False)
    say(reached_near(out, 0.0, -1200.0, 100.0 * L.FLOOR),
        f"guest from Tribe's stage spawn walks out through the gate ({len(out)} states)")
    return ok, host


# ---------------------------------------------------------------- the check image (plan view: stage up, airlock left)
def draw(path, host):
    from PIL import Image, ImageDraw
    s = 4.0                                                          # cm per pixel
    xmin, xmax, ymin, ymax = -1300.0, 1300.0, -3650.0, 600.0         # club-frame cm (x right, y up)
    W, H = int((xmax - xmin) / s), int((ymax - ymin) / s)
    img = Image.new("RGB", (W, H), (18, 18, 22))
    d = ImageDraw.Draw(img, "RGBA")

    def px(X, Y):                                                    # world cm -> pixel (club x = -X)
        return ((-X) - xmin) / s, (ymax - Y) / s

    def rect(X0, Y0, X1, Y1, fill=None, outline=None):
        (a, b), (c, e) = px(X1, Y1), px(X0, Y0)                      # X flips: world X1 is the left edge
        d.rectangle((min(a, c), min(b, e), max(a, c), max(b, e)), fill=fill, outline=outline)

    def shade(top):
        t = max(0.0, min(1.0, (top + 120.0) / 350.0))
        return (int(45 + 60 * t), int(45 + 90 * t), int(55 + 70 * t), 255)

    for X0, Y0, X1, Y1, top, _b, _n in sorted(FLOORS, key=lambda f: f[4]):
        rect(X0, Y0, X1, Y1, fill=shade(top))
    for ix, iy, cur in host:                                         # where the host's head can go
        x, y = px(ix * GRID, iy * GRID)
        d.point((x, y), fill=(0, 200, 230, 255) if cur > -1.0 else (0, 150, 190, 255))
    for X0, Y0, X1, Y1, z0, z1, _n, gate in BOXES:
        rect(X0, Y0, X1, Y1, fill=(60, 220, 90, 200) if gate else (210, 60, 60, 190))
    for X, Y, r, z0, z1, name in CIRCLES:
        x, y = px(X, Y)
        rr = r / s
        d.ellipse((x - rr, y - rr, x + rr, y + rr), fill=(230, 90, 200, 220))
    for X, Y, r, z0, z1, name in PERSONS:                            # soft: the shoulders outlined, the solid core filled
        x, y = px(X, Y)
        rr, rc = r / s, PERSON_CORE / s
        col = (250, 230, 80, 255) if z0 > 100.0 else (240, 150, 40, 255)   # yellow up on a mezzanine
        d.ellipse((x - rr, y - rr, x + rr, y + rr), outline=col, width=1)
        d.ellipse((x - rc, y - rc, x + rc, y + rc), fill=col)
    for name, X, Y, Z, yaw in SPOTS:
        x, y = px(X, Y)
        d.ellipse((x - 5, y - 5, x + 5, y + 5), outline=(255, 255, 255, 255), width=2)
        a = math.radians(yaw)
        x2, y2 = px(X + 60.0 * math.cos(a), Y + 60.0 * math.sin(a))
        d.line((x, y, x2, y2), fill=(255, 255, 255, 255), width=2)
        d.text((x + 8, y - 6), name, fill=(255, 255, 255, 255))
    d.text((8, 8), "REACTOR walking: stage at the top, airlock on the left (world +X). cyan = where the host's head can go;\n"
                   "red = walls, green = the gate (shut for guests: one way, out), orange = dancers (ring: shoulders, soft; "
                   "dot: solid core), yellow = mezzanine people, pink = rods / stools / poles", fill=(230, 230, 230, 255))
    img.save(path)


def main():
    out = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "out_club")
    os.makedirs(out, exist_ok=True)
    build()
    txt = os.path.join(out, "club_collide.txt")
    write_txt(txt)
    read_txt(txt)
    print(f"club_collide: {len(FLOORS)} floors, {len(BOXES)} boxes (gate incl.), {len(CIRCLES)} circles, "
          f"{len(SPOTS)} spots -> {txt}")
    m = Map()
    ok, host = check(m)
    png = os.path.join(out, "club_collide.png")
    draw(png, host)
    print(f"check image -> {png}")
    print("ALL CHECKS PASS" if ok else "SOME CHECKS FAILED")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
