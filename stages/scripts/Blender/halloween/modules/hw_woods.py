"""GRAVEYARD SHIFT grounds module hw_woods: the woods behind the cathedral for the stream intro (Blender 4.5, headless).

The user, 2026-10-10: before the stream the Headless Horseman rides "through the woods to the stage ... eventually the
trees clear up and we get to the back of the stage". The ride's path is ../intro/hw_intro_path.py (a loop through the
woods, then the exit to the back of the ruined nave at y 48.5); this module plants the woods around it.

Where (kit frame; x/y as the final frame): x -60..60, y 60..155, behind the ruined nave (x +-15, y 15..45). The trees
stand back from the trail (7 m on the loop's inside, where the stream camera rides on the rider's left; 3.5 m outside)
and thin out before the clearing behind the nave ("the trees clear up"). Nothing here is seen from the crowd: the
facade (27 m) and the towers hide trees of at most 17 m this far back.

v2 (the user: "Gonna have to make WAY more trees for the cutscene. We're riding through the middle of a spooky
forest"): ~400 trees, trunks 4 m apart right up to the trail on both sides, the inside of the loop as dense as the rest
(only the camera's lane kept clear), branches arching over the trail above 7 m; the trees thin out only on the way out
to the clearing. OWN_GLOW: the silhouettes and lanterns ship in their own mesh (SM_HwGroundsGlowWoods), so the mod can
hide the whole wood outside the intro (it is only ever seen by the intro's camera).

What: dead trees with hw_forest's Tree (read only: its branching rule; branches are kept out of the trail and the
camera lane by wrapping hw_forest.forbidden during this build only), lit ones near the trail (bark baked), black
silhouettes behind; the dirt trail; the woods floor (the baked ground plane ends at y 60); hanging lanterns along the
trail and green will-o'-wisps (glow + their lights), a cold moon shaft over the clearing. No crowd, no people.
"""
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "grounds"))
sys.path.insert(0, os.path.join(HERE, "..", "intro"))
from kit import *  # noqa: E402,F401,F403
import hw_forest as forest  # noqa: E402  (read only: Tree, Parts, paint)
import hw_intro_path as ride  # noqa: E402

NAME = "woods"
BAKE_SIZE = 1024                # its bark is near-black moonlit dead wood (2048 baked to a mean of ~0): 1024 saves 4.5 MB
OWN_GLOW = True                 # hw_stage.py: this module's glow/silhouette parts ship as SM_HwGroundsGlowWoods
Z0 = GROUND_Z
X0, X1, Y0, Y1 = -60.0, 60.0, 60.0, 155.0
N_TRY = 12000
TRAIL_W = 4.0


def _trail():
    (loop, _), (ex, _) = ride.path()
    return loop, ex


LOOP, EXIT = _trail()
LOOP_C = (sum(p[0] for p in LOOP) / len(LOOP), sum(p[1] for p in LOOP) / len(LOOP))


def _dist(pts, x, y):
    return min(math.hypot(x - px, y - py) for px, py in pts[::4])


def _inside_loop(x, y):
    """Ray-cast point-in-polygon on the loop."""
    inside = False
    n = len(LOOP)
    for i in range(n):
        (ax, ay), (bx, by) = LOOP[i], LOOP[(i + 1) % n]
        if (ay > y) != (by > y) and x < ax + (y - ay) * (bx - ax) / (by - ay):
            inside = not inside
    return inside


def trail_clear(x, y, z=None):
    """Too close to the trail (or in the camera's lane on the loop's inside) for a trunk; with z, for a branch below
    7 m (the rider's head is at 2.6 m, the lantern camera rides 0.5..2 m up)."""
    d_loop, d_exit = _dist(LOOP, x, y), _dist(EXIT, x, y)
    if z is not None and z > Z0 + 7.0:
        return False
    clear = ride.TREE_CLEAR_IN if _inside_loop(x, y) else ride.TREE_CLEAR_OUT
    return d_loop < clear or d_exit < ride.TREE_CLEAR_OUT + 1.0


def plant(rng):
    trees = []
    for _ in range(N_TRY):
        x, y = rng.uniform(X0, X1), rng.uniform(Y0, Y1)
        if trail_clear(x, y):
            continue
        if y < 72.0 and rng.random() < 0.75:                     # the trees thin out toward the clearing
            continue
        if y < 66.0:                                              # the clearing behind the nave
            continue
        if any(math.hypot(x - t["x"], y - t["y"]) < 4.0 for t in trees):
            continue
        near = min(_dist(LOOP, x, y), _dist(EXIT, x, y))
        style = rng.choices(("oak", "snag", "broken"), (0.6, 0.3, 0.1))[0]
        trees.append({"x": x, "y": y, "h": rng.uniform(10.0, 19.0), "style": style, "lit": near < 10.0})
        if len(trees) >= 420:
            break
    return trees


def _ribbon(bm, pts, w, z, closed):
    """A flat strip along pts, w wide, z above the kit ground."""
    n = len(pts)
    rows = []
    for i in range(n):
        a, b = pts[max(i - 1, 0)], pts[min(i + 1, n - 1)]
        if closed:
            a, b = pts[(i - 1) % n], pts[(i + 1) % n]
        dx, dy = b[0] - a[0], b[1] - a[1]
        d = math.hypot(dx, dy) or 1.0
        nx, ny = -dy / d, dx / d
        rows.append((bm.verts.new((pts[i][0] + nx * w / 2, pts[i][1] + ny * w / 2, Z0 + z)),
                     bm.verts.new((pts[i][0] - nx * w / 2, pts[i][1] - ny * w / 2, Z0 + z))))
    faces = []
    for i in range(n - (0 if closed else 1)):
        r0, r1 = rows[i], rows[(i + 1) % n]
        faces.append(bm.faces.new((r0[0], r0[1], r1[1], r1[0])))
    return faces


def build(rng):
    P = forest.Parts()
    orig = forest.forbidden

    def forbidden(p, pad=0.0):                                     # the forest's rule + the trail and the camera lane
        return orig(p, pad) or trail_clear(p.x, p.y, p.z)
    forest.forbidden = forbidden
    try:
        trees = plant(rng)
        for t in trees:
            forest.Tree(t["x"], t["y"], t["h"], t["style"], t["lit"], rng).build(P)
    finally:
        forest.forbidden = orig
    forest.paint(P.sil, list(P.sil.faces), "black")
    trail = bmesh.new()                                             # the dirt trail over the woods floor
    _ribbon(trail, LOOP[::3], TRAIL_W, 0.03, True)
    _ribbon(trail, EXIT[::3], TRAIL_W, 0.03, False)
    floor = bmesh.new()                                             # the woods floor (the ground plane ends at y 60)
    quad(floor, (X0 - 15, Y0, Z0), (X1 + 15, Y0, Z0), (X1 + 15, Y1 + 20, Z0), (X0 - 15, Y1 + 20, Z0))
    # lanterns hung over the trail's outer edge (warm pools the rider gallops through) and green wisps in the glade
    lights, glow = [], P.glow
    for i, k in enumerate(range(0, len(LOOP), max(1, len(LOOP) // 7))):
        x, y = LOOP[k]
        cx, cy = LOOP_C
        d = math.hypot(x - cx, y - cy) or 1.0
        lx, ly = x + (x - cx) / d * 3.2, y + (y - cy) / d * 3.2     # 3.2 m outside the centre line
        post_top = Z0 + 3.2
        cyl(P.L("wood_dark"), (lx, ly, Z0), (lx, ly, post_top), 0.07, segs=5)
        cyl(P.L("wood_dark"), (lx, ly, post_top - 0.1), (lx - (x - cx) / d * 0.6, ly - (y - cy) / d * 0.6, post_top - 0.1),
            0.04, segs=4)
        hx, hy = lx - (x - cx) / d * 0.6, ly - (y - cy) / d * 0.6
        glow_faces(glow, box(glow, (hx, hy, post_top - 0.45), (0.16, 0.16, 0.24)), "bulb_warm")
        lights.append(light(f"HwWoods{len(lights):02d}", "POINT", (hx, hy, post_top - 0.45), (1.0, 0.62, 0.28), 140.0,
                            size=0.2))
    for i, (wx, wy) in enumerate(((-8.0, 105.0), (12.0, 118.0), (2.0, 96.0), (-14.0, 121.0))):
        glow_faces(glow, sphere(glow, (wx, wy, Z0 + 1.4 + 0.3 * i % 2), 0.12, segs=6, rings=4), "lime")
        lights.append(light(f"HwWoods{len(lights):02d}", "POINT", (wx, wy, Z0 + 1.5), (0.3, 1.0, 0.35), 45.0, size=0.2))
    lights.append(light(f"HwWoods{len(lights):02d}", "SPOT", (-4.0, 58.0, Z0 + 22.0), (0.45, 0.55, 1.0), 2500.0,
                        target=(-3.0, 56.0, Z0), size=2.0, spot_deg=40.0))   # the moon shaft over the clearing
    lit = [(bm, key) for key, bm in P.lit.items() if len(bm.faces)] + [(trail, "dirt"), (floor, "grass")]
    log_trees = len(trees)
    print(f"[HW woods] {log_trees} trees ({sum(t['lit'] for t in trees)} lit), heights "
          f"{min(t['h'] for t in trees):.1f}..{max(t['h'] for t in trees):.1f} m; lit tris "
          f"{sum(tris(b) for b, _ in lit)}, glow {tris(glow)}, silhouettes {tris(P.sil)}; lights {len(lights)}",
          flush=True)
    return {"lit": lit, "glow": [glow, P.sil], "beams": [], "halos": [], "lights": lights, "exclude": [], "people": []}
