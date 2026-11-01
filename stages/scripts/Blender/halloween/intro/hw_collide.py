"""GRAVEYARD SHIFT walking map for the stream intro: tribemod/halloween_collide.txt (the club's format, hook/club_collide.h;
the hook walks any of our stages that has tribemod/<folder>_collide.txt, the folder lowercased: "halloween").

The user walks out of the backstage crypt through the gate under the screen, across the deck, up the riser's side stairs
(Dino's riser: the same numbers) to the decks. Walkable: the riser and its stairs, the deck in front of the gate, the
crypt. Walls: the crypt, the gate's pillars, the button's pedestal, the booth, the riser's gargoyles, rails on the riser's
front and back edges and round the deck, and (v5) the two crypt doors standing open on the deck (open is their pose when
no intro runs; the map is static, so shut doors are not walls). Spots: decks (Tribe's DJ spot) and backstage (where the
intro waits).
Then an offline walk under the rules line checks the route backstage -> decks.
v7 (the user, 2026-10-11: "is there a pathway into the crowd?", then free roam: "walk through the figures"): stairs off
the deck front's middle (hw_deckprops), a gateway in the iron barrier, and the whole crowd field walkable (its rows:
the pit, then bands out to the crowd's half-width, back to y -66), walled round the grounds' keep-outs (hw_stage writes
them to <stage out>/walk_field.json: the tombs, the graveyard strips, the FOH plot) and the deck dressing. The walk
check also needs decks -> the crowd's middle and back.

    python hw_collide.py [out.txt] [stage out dir, default ../out_hw]

Frame: hw_stage.py's final Blender frame (m) -> world cm = (-100x, 100y, 100z).

    python hw_collide.py [out.txt]
"""
import math
import os
import sys
from collections import deque

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import hw_intro_path as ip  # noqa: E402
sys.path.insert(0, os.path.join(HERE, ".."))
import hw_deckprops as dp  # noqa: E402  (v7: the deck dressing and the stairs)
import json  # noqa: E402

STEP, HEAD, KNEE, RADIUS, CORE = 45.0, 190.0, 25.0, 20.0, 15.0     # cm: the club's and Dino's rules line
DECK, RISER = -1.0, 0.0
FLOORS, BOXES, SPOTS, PERSONS = [], [], [], []
DANCER_R = 0.25                                                    # m: Reactor's (club_collide.py): a dancer's shoulders


def X(x):
    return -100.0 * x


def floor(name, x0, y0, x1, y1, top, bot):
    """Blender m rectangle -> world cm floor (x0 < x1 after the mirror)."""
    a, b = sorted((X(x0), X(x1)))
    FLOORS.append((name, a, 100 * y0, b, 100 * y1, 100 * top, 100 * bot))


def box(name, x0, y0, x1, y1, z0, z1):
    a, b = sorted((X(x0), X(x1)))
    BOXES.append((name, a, 100 * y0, b, 100 * y1, 100 * z0, 100 * z1))


def build():
    floor("riser", -4.5, -2.5, 4.5, 3.0, RISER, DECK)
    for side, sx in (("L", -1.0), ("R", 1.0)):                     # Dino's side stairs: 4 steps of 20 cm, 35 cm deep
        for k in range(4):
            x_in, x_out = sx * (4.5 + 0.35 * k), sx * (4.5 + 0.35 * (k + 1))
            floor(f"riser_step_{side}{k}", min(x_in, x_out), 1.1, max(x_in, x_out), 2.9, -0.2 * (k + 1), DECK)
    floor("deck", -25.0, -4.5, 25.0, ip.GATE_Y, DECK, -2.5)
    floor("crypt", -2.27, ip.GATE_Y, 2.27, 10.08, DECK, -2.5)
    for sx in (-1, 1):
        box(f"crypt_wall_{sx:+d}", sx * 2.275, ip.GATE_Y, sx * 2.6, 10.3, DECK, 2.9)
        box(f"gate_pillar_{sx:+d}", sx * ip.GATE_X, ip.GATE_Y, sx * (ip.GATE_X + 0.7), ip.GATE_Y + 0.7, DECK, 3.4)
        box(f"gargoyle_{sx:+d}", sx * 3.2, 0.2, sx * 4.0, 1.0, RISER, 1.4)
        box(f"deck_side_{sx:+d}", sx * 25.0, -4.5, sx * 25.3, ip.GATE_Y, DECK, 0.0)
        for k in range(4):                                         # the deck in front of the gate ends at the crypt
            pass
    box("crypt_back", -2.6, 10.08, 2.6, 10.3, DECK, 2.9)
    box("gate_line_L", -25.0, ip.GATE_Y, -2.6, ip.GATE_Y + 0.1, DECK, 2.0)   # behind the gate line: off limits
    box("gate_line_R", 2.6, ip.GATE_Y, 25.0, ip.GATE_Y + 0.1, DECK, 2.0)
    bx, by, bz = ip.BUTTON
    box("button_pedestal", bx - 0.18, by - 0.18, bx + 0.18, by + 0.18, DECK, bz)
    for sx in (-1, 1):                                             # v5: the doors open (ip.door_xy), as their footprint's box
        corners = [ip.door_xy(sx, sx * x, y, 1.0) for x in (0.006, ip.GATE_X) for y in (ip.GATE_Y - 0.045,
                                                                                      ip.GATE_Y + ip.DOOR_T + 0.035)]
        xs, ys = [c[0] for c in corners], [c[1] for c in corners]
        box(f"door_open_{sx:+d}", min(xs), min(ys), max(xs), max(ys), DECK, ip.GATE_TOP)
    box("booth", -0.95, -0.05, 0.85, 0.5, RISER, 0.74)
    box("riser_front", -4.5, -2.6, 4.5, -2.5, RISER, 1.0)
    box("riser_back", -4.5, 3.0, 4.5, 3.1, RISER, 1.0)
    for sx in (-1, 1):                                             # v7: the deck's front edge, open at the stairs
        box(f"deck_front_{sx:+d}", sx * dp.STAIR_HALF_W, -4.6, sx * 25.0, -4.5, DECK, 0.0)
    for x in (-15.0, -9.0, -3.0, 3.0, 9.0, 15.0):                  # the deck-front laser posts
        box(f"laser_post_{x:+.0f}", x - 0.25, -4.5, x + 0.25, -4.0, DECK, 0.45)
    for x in (-18.0, -12.0, -6.0, 6.0, 12.0, 18.0):                # the flame jets' bases
        box(f"flame_base_{x:+.0f}", x - 0.25, -4.25, x + 0.25, -3.75, DECK, -0.75)
    for sx in (-1, 1):                                             # the skull piles beside the riser
        box(f"skulls_{sx:+d}", sx * 5.4, -3.8, sx * 6.6, -2.8, DECK, -0.3)
    free_roam()
    SPOTS.append(("decks", 0.0, 90.0, 0.0, -90.0))
    sx, sy, sz, _ = ip.BACKSTAGE
    SPOTS.append(("backstage", X(sx), 100 * sy, 100 * sz, -90.0))


FIELD_SRC = os.path.join(HERE, "..", "out_hw")
CHECK_SPOTS = (("crowd_middle", 8.0, -20.0), ("crowd_back", -6.0, -55.0))   # Blender m: the walk check's extra goals


def free_roam():
    """v7: the stairs, the pit, the crowd field (bands), the barrier with its gateway, the keep-outs, the dressing."""
    wf = json.load(open(os.path.join(FIELD_SRC, "walk_field.json")))
    fz, by, yb = wf["field_z"], wf["barrier_y"], wf["y_back"]
    h0, h1 = wf["half"]
    for k, (ya, yb_, top) in enumerate(dp.stair_steps()):
        floor(f"stair_{k}", -dp.STAIR_HALF_W, yb_, dp.STAIR_HALF_W, ya, top, fz)
    for sx in (-1, 1):
        box(f"stair_rail_{sx:+d}", sx * dp.STAIR_HALF_W, dp.STAIR_Y0 - dp.STAIR_N * dp.STAIR_D, sx * (dp.STAIR_HALF_W + 0.1),
            dp.STAIR_Y0, fz, DECK + 0.9)
    floor("pit", -25.0, by, 25.0, -4.5, fz, fz - 0.5)              # deck front to the barrier
    y, k = by, 0
    while y > yb:                                                 # the crowd field: 4 m bands, each at its near half
        y1 = max(y - 4.0, yb)
        half = h0 + h1 * (-y)
        floor(f"field_{k}", -half, y1, half, y, fz, fz - 0.5)
        y, k = y1, k + 1
    for sx in (-1, 1):                                            # the barrier, open at the gateway
        box(f"barrier_{sx:+d}", sx * dp.BARRIER_GAP, by - 0.05, sx * 31.0, by + 0.05, fz, fz + 1.5)
    for i, (x0, y0, x1, y1) in enumerate(wf["exclude"]):          # the grounds' keep-outs (tombs, strips, FOH plot)
        box(f"keepout_{i}", x0, y0, x1, y1, fz, fz + 3.0)
    pp = os.path.join(FIELD_SRC, "walk_people.json")              # the dancers: soft, a 15 cm solid core (rules)
    if os.path.exists(pp):
        for x, y, dz in json.load(open(pp)):
            z0 = fz + 1.0 + dz                                        # the crowd's ground is the kit's -1.5 (dz: riders)
            PERSONS.append((X(x), 100 * y, 100 * DANCER_R, 100 * z0, 100 * (z0 + 1.8)))
    for i, (kind, x, y, size, sx) in enumerate(dp.PROPS):         # the deck dressing
        x0, y0, x1, y1, h = dp.footprint(kind, x, y, size)
        box(f"{kind}_{i}", x0, y0, x1, y1, DECK, DECK + h)


def write(out):
    lines = ["# GRAVEYARD SHIFT walking map (Scripts/Blender/halloween/intro/hw_collide.py): world cm, the club's format",
             f"rules {STEP:g} {HEAD:g} {KNEE:g} {RADIUS:g} {CORE:g}"]
    lines += [f"floor {a:.1f} {b:.1f} {c:.1f} {d:.1f} {t:.1f} {u:.1f} {n}" for n, a, b, c, d, t, u in FLOORS]
    lines += [f"box {a:.1f} {b:.1f} {c:.1f} {d:.1f} {z0:.1f} {z1:.1f} {n}" for n, a, b, c, d, z0, z1 in BOXES]
    lines += [f"person {x:.1f} {y:.1f} {r:.1f} {z0:.1f} {z1:.1f} dancer" for x, y, r, z0, z1 in PERSONS]
    lines += [f"spot {n} {x:.1f} {y:.1f} {z:.1f} {yaw:.1f}" for n, x, y, z, yaw in SPOTS]
    open(out, "w").write("\n".join(lines) + "\n")
    return len(lines)


def walk_check(grid=10.0):
    """BFS on a 10 cm grid: a cell stands on the highest floor under it; the body (floor + KNEE .. floor + HEAD) must
    keep RADIUS from every box; a move may climb or drop at most STEP. backstage -> decks must connect."""
    xs = [f[1] for f in FLOORS] + [f[3] for f in FLOORS]
    ys = [f[2] for f in FLOORS] + [f[4] for f in FLOORS]
    x0, x1, y0, y1 = min(xs), max(xs), min(ys), max(ys)
    nx, ny = int((x1 - x0) / grid) + 1, int((y1 - y0) / grid) + 1

    def floor_at(x, y):
        tops = [f[5] for f in FLOORS if f[1] <= x <= f[3] and f[2] <= y <= f[4]]
        return max(tops) if tops else None

    def free(x, y, z):
        for n, a, b, c, d, z0, z1 in BOXES:
            if z1 <= z + KNEE or z0 >= z + HEAD:
                continue
            dx = max(a - x, 0.0, x - c)
            dy = max(b - y, 0.0, y - d)
            if math.hypot(dx, dy) < RADIUS:
                return False
        return True
    cache = {}

    def cell(i, j):
        if (i, j) not in cache:
            x, y = x0 + i * grid, y0 + j * grid
            z = floor_at(x, y)
            cache[(i, j)] = z if z is not None and free(x, y, z) else None
        return cache[(i, j)]
    s = {n: (int((x - x0) / grid), int((y - y0) / grid)) for n, x, y, z, yaw in SPOTS}
    s.update({n: (int((X(x) - x0) / grid), int((100 * y - y0) / grid)) for n, x, y in CHECK_SPOTS})
    start, goal = s["backstage"], s["decks"]
    if cell(*start) is None or cell(*goal) is None:
        return False, f"a spot stands on no free floor (backstage {cell(*start)}, decks {cell(*goal)})"
    seen, q = {start}, deque([start])
    while q:
        i, j = q.popleft()
        for di, dj in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            k = (i + di, j + dj)
            if k in seen or not (0 <= k[0] < nx and 0 <= k[1] < ny):
                continue
            z0, z1 = cell(i, j), cell(*k)
            if z1 is None or abs(z1 - z0) > STEP:
                continue
            seen.add(k)
            q.append(k)
    missing = [n for n in ("decks",) + tuple(c[0] for c in CHECK_SPOTS) if s[n] not in seen]
    area = len(seen) * (grid / 100.0) ** 2
    if missing:
        return False, f"no route from backstage to {', '.join(missing)} ({area:.0f} m2 reachable)"
    return True, f"backstage reaches the decks and the crowd ({', '.join(c[0] for c in CHECK_SPOTS)}); {area:.0f} m2 walkable"


if __name__ == "__main__":
    if len(sys.argv) > 2:
        FIELD_SRC = sys.argv[2]
    build()
    out = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "halloween_collide.txt")
    n = write(out)
    ok, why = walk_check()
    print(f"{out}: {n} lines ({len(FLOORS)} floors, {len(BOXES)} boxes, {len(PERSONS)} dancers, {len(SPOTS)} spots); walk: "
          f"{'OK' if ok else 'FAIL'}, {why}")
    sys.exit(0 if ok else 1)
