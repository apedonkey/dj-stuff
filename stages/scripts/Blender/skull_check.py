"""Fit checks for the v2 arch skull (skull.py); re-run after changing the skull, the arch, the screen or the lasers.

  D:\\Tools\\blender-4.5.14-windows-x64\\blender.exe -b --factory-startup --python skull_check.py

Prints [SKULLCHECK] lines: tris (budget 14k + eyes); bounds; the lowest point in front of the visual screen (x -8..8,
y < arch.SCREEN_Y; keep above ~12); every horn laser of grounds/atmosphere.py swept over its full cycle against the
skull and its glow (beam axis plus 0.2 m offsets, 500 samples each; expect 0 contacts); how deep the arch's horns and
back spikes (arch.py) run into the skull; the laser / smoke port positions.
"""
import importlib
import os
import sys

import bpy
from mathutils import Vector
from mathutils.bvhtree import BVHTree

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "grounds"))
bpy.ops.wm.read_factory_settings(use_empty=True)
import arch  # noqa: E402
import skull  # noqa: E402


def log(msg):
    print("[SKULLCHECK] " + msg, flush=True)


sk, eyes = skull.build_skull_v2()
tris = sum(len(f.verts) - 2 for f in sk.faces)
log(f"tris: skull {tris} (budget 14000), eyes {sum(len(f.verts) - 2 for f in eyes.faces)}")
vs = [v.co.copy() for v in sk.verts]
lo = Vector((min(v.x for v in vs), min(v.y for v in vs), min(v.z for v in vs)))
hi = Vector((max(v.x for v in vs), max(v.y for v in vs), max(v.z for v in vs)))
log("bounds (pre-drop): x %.2f..%.2f  y %.2f..%.2f  z %.2f..%.2f" % (lo.x, hi.x, lo.y, hi.y, lo.z, hi.z))
log("lowest point in front of the visual screen (|x| < 8, y < %.1f): z %.2f (keep above ~12)"
    % (arch.SCREEN_Y, min(v.z for v in vs if abs(v.x) < 8.0 and v.y < arch.SCREEN_Y)))

both = sk.copy()                                                     # bone + glow
for f in eyes.faces:
    both.faces.new([both.verts.new(v.co) for v in f.verts])
bvh = BVHTree.FromBMesh(both)
atm = importlib.import_module("atmosphere")
heads = {i: f"{'L' if h['side'] < 0 else 'R'}{h['k']}" for i, h in enumerate(atm.HORN_HEADS)}
contacts = {}
for L in atm.LASERS:
    piv, end0 = Vector(L["pivot"]), Vector(L["pivot"]) + Vector(L["d"]) * L["length"]
    for k in range(500):
        end = atm.laser_pose(end0, piv, L["phase"], L["pan"], L["tilt"], 10.0 * k / 500)
        d = end - piv
        ln = d.length
        d.normalize()
        side = d.cross(Vector((0, 0, 1))).normalized()
        up = side.cross(d).normalized()
        for off in (Vector(), side * 0.2, -side * 0.2, up * 0.2, -up * 0.2):
            if bvh.ray_cast(piv + d * atm.LASER_GAP + off, d, ln - atm.LASER_GAP)[0] is not None:
                name = heads.get(L["head"], "stage fan")
                contacts[name] = contacts.get(name, 0) + 1
                break
log(f"lasers: {len(atm.LASERS)} beams x 500 sweep samples; contacts with the skull: "
    f"{sum(contacts.values())} {contacts if contacts else ''}")

near = 0                                                             # the arch's horns and back spikes (arch.py)
for spec in [h for s in (-1, 1) for h in arch.horns(s)] + [p for s in (-1, 1) for p in arch.spikes(s)]:
    pts, rfn, n = spec["pts"], arch.horn_radius_fn(spec["r0"]), spec["steps"]
    kind, idx = ("horn", spec["k"]) if "k" in spec else ("spike", spec["i"])
    name = f"{kind} {'L' if spec['side'] < 0 else 'R'}{idx}"
    head, neck, gap = [], [], 9e9                                    # neck: y > 6.2, where it meets the spine ends
    for v in vs:
        best = None
        for i in range(n):
            a, b = pts[i], pts[i + 1]
            ab = b - a
            u = max(0.0, min(1.0, (v - a).dot(ab) / ab.length_squared))
            dist = (v - (a + ab * u)).length - rfn((i + u) / n)
            best = dist if best is None or dist < best else best
        if best < 0:
            (neck if v.y > 6.2 else head).append(-best)
        gap = min(gap, best)
    if head or neck:
        log(f"{name}: head {len(head)} vertices inside (deepest {max(head, default=0):.2f} m; expect 0), "
            f"neck/spine-end junction {len(neck)} (deepest {max(neck, default=0):.2f} m; bone meets bone there)")
    elif gap < 1.0:
        near += 1
        log(f"{name}: clear of the skull by {gap:.2f} m")
log(f"arch: {2 * len(arch.HORN_T)} horns + {2 * len(arch.SPIKE_T)} back spikes checked against the skull; {near} pass "
    f"within 1 m (listed above with any that touch it), the rest further")
log("ports (pre-drop): " + ", ".join(f"{k} ({p.x:.2f}, {p.y:.2f}, {p.z:.2f})" for k, p in skull.ports().items()))
