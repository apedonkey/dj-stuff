"""Lint every GRAVEYARD SHIFT grounds module together (Blender 4.5 headless, no render, no GPU): the phase-2 gate in
numbers. Builds each module as hw_stage.py does (seed 1234) and reports, per module and across modules:
  - tris per part and lights against CONTRACT.md's budgets; hinged parts against their 3,000-tri budget;
  - geometry standing inside the crowd (|x| < crowd_half(y), y -8.6..-66, higher than 0.5 m over the field) that no
    module's "exclude" rect covers: the crowd generator would put people inside it;
  - geometry over the existing set (deck, barrier, cathedral, towers, nave, the oaks);
  - footprint cells (1 m) where two modules both stand: collisions between helpers' work.

  blender -b --factory-startup --python hw_modlint.py -- [hw_graveyard,hw_vendors,...]
"""
import importlib
import math
import os
import random
import sys

import bpy  # noqa: F401  (bmesh needs Blender)

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "..", "..", "grounds"))
import kit  # noqa: E402

ARGS = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
MODULES = (ARGS[0].split(",") if ARGS else
           ["hw_graveyard", "hw_infrastructure", "hw_vendors", "hw_forest", "hw_carnival", "hw_pumpkins", "hw_crypt"])
BUDGET = {"hw_graveyard": (30000, 30), "hw_infrastructure": (15000, 15), "hw_vendors": (25000, 40),
          "hw_forest": (45000, 25), "hw_carnival": (30000, 25), "hw_pumpkins": (25000, 12), "hw_crypt": (25000, 15)}
G0 = kit.GROUND_Z
SET_BOXES = [("stage deck", -25, -4.5, 25, 14), ("barrier", -31, -7.9, 31, -7.1), ("cathedral", -28, 14, 28, 45),
             ("left oak", -49, -4, -29, 16), ("right oak", 29, -4, 49, 16)]


def in_crowd(x, y, margin=1.0):
    """Inside the crowd by at least `margin` metres (the generator's rows run y -8.6..-66)."""
    return -66.0 + margin <= y <= -8.6 - margin and abs(x) < kit.crowd_half(y) - margin


def cells_of(bm):
    """{(cx, cy): [min z, max z]} over the 1-m cells the faces actually cover: each triangle sampled on a barycentric
    grid at <= 0.5 m spacing (a bounding box would claim the empty corners of long diagonal fences and big tree cards)."""
    out = {}
    for f in bm.faces:
        vs = [v.co for v in f.verts]
        for k in range(1, len(vs) - 1):                               # fan triangulation
            a, b, c = vs[0], vs[k], vs[k + 1]
            n = max(1, math.ceil(max((b - a).length, (c - b).length, (a - c).length) / 0.5))
            for i in range(n + 1):
                for j in range(n + 1 - i):
                    p = a + (b - a) * (i / n) + (c - a) * (j / n)
                    cell = (math.floor(p.x), math.floor(p.y))
                    r = out.get(cell)
                    if r is None:
                        out[cell] = [p.z, p.z]
                    else:
                        r[0], r[1] = min(r[0], p.z), max(r[1], p.z)
    return out


results, owners, all_excl = {}, {}, []
for name in MODULES:
    if not os.path.exists(os.path.join(HERE, name + ".py")):
        print(f"[LINT] {name}: not there yet")
        continue
    try:
        res = importlib.import_module(name).build(random.Random(1234))
    except Exception as e:  # noqa: BLE001
        print(f"[LINT] {name}: BUILD FAILED {e!r}")
        continue
    results[name] = res
    all_excl += [(name, r) for r in res.get("exclude", [])]

for name, res in results.items():
    lit = sum(kit.tris(b) for b, _ in res.get("lit", []))
    glow = sum(kit.tris(b) for b in res.get("glow", []))
    hinged = res.get("hinged", [])
    htris = sum(kit.tris(h[0]) for h in hinged)
    beams = sum(len(b.faces) for b in res.get("beams", []))
    halos = sum(len(b.faces) for b in res.get("halos", []))
    lights = len(res.get("lights", []))
    tb, lb = BUDGET.get(name, (0, 0))
    total = lit + glow + htris
    flags = []
    if tb and total > tb:
        flags.append(f"tris {total} > {tb}")
    if lb and lights > lb:
        flags.append(f"lights {lights} > {lb}")
    if htris > 3000:
        flags.append(f"hinged {htris} tris > 3000")
    for k, h in enumerate(hinged):
        if len(h) < 5 or h[1] not in kit.LIT or not (-180 <= float(h[4]) <= 180):
            flags.append(f"hinged entry {k} malformed")
    parts = [b for b, _ in res.get("lit", [])] + list(res.get("glow", [])) + [h[0] for h in hinged]
    cells, tall = {}, {}
    for b in parts:
        for c, (z0, z1) in cells_of(b).items():
            r = cells.setdefault(c, [z0, z1])
            r[0], r[1] = min(r[0], z0), max(r[1], z1)
    tall = {c: r for c, r in cells.items() if r[1] >= G0 + 0.5}
    excl = [r for _, r in all_excl]
    intrude = [c for c in tall if in_crowd(c[0] + 0.5, c[1] + 0.5)
               and not any(x0 <= c[0] + 0.5 <= x1 and y0 <= c[1] + 0.5 <= y1 for x0, y0, x1, y1 in excl)]
    over_set = {}
    for lbl, x0, y0, x1, y1 in SET_BOXES:
        n = sum(1 for c in tall if x0 <= c[0] + 0.5 <= x1 and y0 <= c[1] + 0.5 <= y1)
        if n:
            over_set[lbl] = n
    if intrude:
        xs = sorted(intrude)
        flags.append(f"{len(intrude)} tall cells inside the crowd without an exclude rect (e.g. {xs[0]}, {xs[len(xs)//2]},"
                     f" {xs[-1]})")
    if over_set:
        flags.append("over the set: " + ", ".join(f"{k} {v} cells" for k, v in over_set.items()))
    xs = [c[0] for c in cells] or [0]
    ys = [c[1] for c in cells] or [0]
    print(f"[LINT] {name}: lit {lit} + glow {glow} + hinged {htris} = {total} tris (budget {tb}); lights {lights} "
          f"({lb}); beams {beams} quads, halos {halos}; exclude {len(res.get('exclude', []))}; people "
          f"{len(res.get('people', []))}; footprint x {min(xs)}..{max(xs)}, y {min(ys)}..{max(ys)}")
    for f in flags:
        print(f"[LINT]   !! {name}: {f}")
    for c, r in tall.items():
        owners.setdefault(c, {})[name] = r

pairs = {}
for c, by in owners.items():                                         # two modules in one cell AND at the same heights
    names = sorted(by)
    for i in range(len(names)):
        for j in range(i + 1, len(names)):
            (a0, a1), (b0, b1) = by[names[i]], by[names[j]]
            if a0 <= b1 and b0 <= a1:
                pairs.setdefault((names[i], names[j]), []).append(c)
for key, cs in sorted(pairs.items(), key=lambda kv: -len(kv[1])):
    cs.sort()
    print(f"[LINT] !! overlap {' + '.join(key)}: {len(cs)} cells where both stand at the same height, e.g. {cs[0]}, "
          f"{cs[len(cs) // 2]}, {cs[-1]}")
print(f"[LINT] done: {len(results)} modules; {sum(len(v) for v in pairs.values())} shared tall cells")
