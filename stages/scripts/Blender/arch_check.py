"""Checks for the v2 arch and its arch-shaped visual screen (arch.py), on a build's FBX output (Blender 4.5, headless):

  set DINO_OUT=...\\out_arch & blender.exe -b --factory-startup --python arch_check.py

Prints [ARCHCHECK] lines:
1. the screen: tris, plane, facing; its UV0 against the rules (the smallest 16:9 box around the outline, centered on
   its bounding box; U 0 at the box's +x edge to 1 at its -x edge; Blender V 0 at the box bottom to 0.5 at its top;
   every vertex inside the box) and the share of the video frame's height that lands on the screen;
2. nothing crosses the screen: BVH overlap of the screen with every other mesh of the build (solid and translucent),
   plus the closest geometry inside the outline within 0.5 m of the screen plane;
3. the moon, its frame rings and bulb ring stay covered by the screen as seen from the crowd and the preview views;
4. the fit from each preview view: rays aimed just outside the screen's edge (past its SCREEN_CLEAR band, +1..20 cm,
   every 25 cm along the edge, not only at the outline's vertices) must land on the bone or the deck right behind it,
   not on the sky or the stage far behind (a see-through gap between bone and video);
5. what the arch's bone touches in the build (props, plants, grounds);
6. the two wings and the lintel's halves are exact mirror images (arch.py layouts), and the horn-tip table for
   grounds/atmosphere.py;
7. the giant intro's column (giant.py: the robe's hem ellipse around (0, 1.68), 1.4 x 1.0 m, from the riser top up to
   8 m above it) holds nothing of the build, and the screen stands behind the robe (y > 2.7).
The FBX files are post-drop; everything is moved back up by STAGE_DROP and reported pre-drop.
"""
import math
import os
import sys

import bpy
from mathutils import Vector
from mathutils.bvhtree import BVHTree
from mathutils.kdtree import KDTree

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import arch  # noqa: E402

STAGE_OUT = os.environ.get("DINO_OUT") or os.path.join(HERE, "out")
DROP = 1.0
BACKGROUND = ("SM_DinoSky", "SM_DinoFarGround", "SM_DinoGround", "SM_DinoCrowd", "SM_DinoPhones", "SM_DinoFlags")
VIEWS = {   # pre-drop eye points: the lead's crowd center, the preview cameras, off-center crowd
    "crowd center (0,-35,2.7)": (0, -35, 2.7), "stream drone (0,-95,13)": (0, -95, 13),
    "mid-crowd (0,-24,3)": (0, -24, 3.0), "front rows (0,-8.6,0.3)": (0, -8.6, 0.3),
    "DJ (0,0.9,2.6)": (0, 0.9, 2.6), "crowd left (-18,-30,1)": (-18, -30, 1.0),
    "crowd right (18,-30,1)": (18, -30, 1.0),
}


def log(msg):
    print("[ARCHCHECK] " + msg, flush=True)


bpy.ops.wm.read_factory_settings(use_empty=True)
manifest = os.path.join(STAGE_OUT, "manifest.txt")
names = [n.strip() for n in open(manifest) if n.strip()] if os.path.exists(manifest) else []
meshes = {}                                                           # name -> (verts, polys), pre-drop
uvs, normals, layers = [], [], []                                     # the screen's loops (position, uv), face normals
for name in names:
    if name in ("SM_DinoCrowd", "SM_DinoPhones"):                    # far out in the field, and big
        continue
    path = os.path.join(STAGE_OUT, name + ".fbx")
    if not os.path.exists(path):
        continue
    before = set(bpy.data.objects)
    bpy.ops.import_scene.fbx(filepath=path, axis_forward="-Z", axis_up="Y")
    verts, polys = [], []
    for ob in [o for o in bpy.data.objects if o not in before and o.type == "MESH"]:
        off = len(verts)
        verts += [(ob.matrix_world @ v.co) + Vector((0, 0, DROP)) for v in ob.data.vertices]
        polys += [[off + i for i in p.vertices] for p in ob.data.polygons]
        if name == "SM_DinoVisualScreen":
            lay = ob.data.uv_layers[0]
            uvs = [(ob.matrix_world @ ob.data.vertices[ob.data.loops[li].vertex_index].co + Vector((0, 0, DROP)),
                    tuple(lay.data[li].uv)) for li in range(len(ob.data.loops))]
            normals = [(ob.matrix_world.to_3x3() @ p.normal).normalized() for p in ob.data.polygons]
            layers = [lay_.name for lay_ in ob.data.uv_layers]
    meshes[name] = (verts, polys)
log(f"build {STAGE_OUT}: {len(meshes)} meshes loaded (crowd and phones skipped)")

# ------------------------------------------------------------------ 1. the screen and its UVs
sv, sp = meshes["SM_DinoVisualScreen"]
ys = [v.y for v in sv]
outline = arch.screen_outline()
ox, oz = [p[0] for p in outline], [p[1] for p in outline]
log(f"screen: {len(sp)} tris, {len(sv)} verts, plane y {min(ys):.3f}..{max(ys):.3f} (arch.SCREEN_Y {arch.SCREEN_Y}), "
    f"faces -Y: {sum(n.y < -0.999 for n in normals)}/{len(normals)}; UV layers {layers}")
log(f"screen outline: x {min(ox):.2f}..{max(ox):.2f} (width {max(ox) - min(ox):.2f}), z {min(oz):.2f}..{max(oz):.2f} "
    f"(height {max(oz) - min(oz):.2f}) pre-drop")
xs, zs = [v.x for v in sv], [v.z for v in sv]
bw, bh = max(xs) - min(xs), max(zs) - min(zs)
w, h = (bw, bw * 9 / 16) if bw / bh >= 16 / 9 else (bh * 16 / 9, bh)
x0, z0 = (max(xs) + min(xs)) / 2 - w / 2, (max(zs) + min(zs)) / 2 - h / 2
worst, inside = 0.0, 0
for co, (u, v) in uvs:
    worst = max(worst, abs(u - (x0 + w - co.x) / w), abs(v - 0.5 * (co.z - z0) / h))
    inside += -1e-5 <= u <= 1 + 1e-5 and -1e-5 <= v <= 0.5 + 1e-5
us, vs_ = [uv[0] for _, uv in uvs], [uv[1] for _, uv in uvs]
log(f"video box (from the mesh): x {x0:.2f}..{x0 + w:.2f}, z {z0:.2f}..{z0 + h:.2f} ({w:.2f} x {h:.2f} m, "
    f"{w / h:.4f}:1); arch.video_box {tuple(round(c, 2) for c in arch.video_box())}")
log(f"UV0: max error vs the rules {worst:.2e}; loops inside the box {inside}/{len(uvs)}; "
    f"U {min(us):.4f}..{max(us):.4f} (U 0 at x {max(xs):.2f} = the box's +x edge), V {min(vs_):.4f}..{max(vs_):.4f}")
log(f"the frame on the screen: {bw / w:.0%} of its width, {bh / h:.0%} of its height (rows "
    f"{(1 - (z0 + h - max(zs)) / h - bh / h):.0%}..{1 - (z0 + h - max(zs)) / h:.0%} from the bottom)")

# ------------------------------------------------------------------ 2. nothing crosses the screen
scr_bvh = BVHTree.FromPolygons(sv, sp)
bvhs = {n: BVHTree.FromPolygons(v, p) for n, (v, p) in meshes.items() if n != "SM_DinoVisualScreen" and p}


def where(verts, polys, idx):
    """Bounding box of the listed triangles."""
    pts = [verts[i] for j in idx for i in polys[j]]
    return (f"x {min(p.x for p in pts):.1f}..{max(p.x for p in pts):.1f} y {min(p.y for p in pts):.1f}.."
            f"{max(p.y for p in pts):.1f} z {min(p.z for p in pts):.1f}..{max(p.z for p in pts):.1f}")


def clusters(verts, polys, idx, gap=2.0):
    """Split triangle indices into groups whose centers lie within `gap` m of each other (single linkage)."""
    cen = {j: sum((verts[i] for i in polys[j]), Vector()) / len(polys[j]) for j in set(idx)}
    groups = []
    for j, c in cen.items():
        hit = [g for g in groups if any((cen[k] - c).length < gap for k in g)]
        merged = [j] + [k for g in hit for k in g]
        groups = [g for g in groups if g not in hit] + [merged]
    return groups


cross = []
for n, b in bvhs.items():
    pairs = scr_bvh.overlap(b)
    if pairs:
        v, p = meshes[n]
        for g in clusters(v, p, [j for _, j in pairs]):
            cross.append(f"{n} {len(g)} tris at {where(v, p, g)}")
log("crossing the screen: " + ("; ".join(cross) if cross else "nothing"))


def inside_outline(x, z, poly=outline):
    c = False
    for (xa, za), (xb, zb) in zip(poly, poly[1:] + poly[:1]):
        if (za > z) != (zb > z) and x < xa + (z - za) * (xb - xa) / (zb - za):
            c = not c
    return c


near = []
for n, (verts, _) in meshes.items():
    if n == "SM_DinoVisualScreen" or n in BACKGROUND:
        continue
    best = None
    for v in verts:
        dy = v.y - arch.SCREEN_Y
        if abs(dy) < 0.5 and inside_outline(v.x, v.z):
            if best is None or abs(dy) < abs(best[0]):
                best = (dy, v)
    if best:
        near.append((abs(best[0]), n, best))
for _, n, (dy, v) in sorted(near)[:8]:
    log(f"  inside the outline within 0.5 m of the screen: {n} at ({v.x:.2f}, {v.y:.2f}, {v.z:.2f}), "
        f"{abs(dy):.2f} m {'behind' if dy > 0 else 'in front'}")

# ------------------------------------------------------------------ 3. the moon stays covered
moon = [v for v in meshes["SM_DinoScreen"][0]]
moon += [v for v in meshes["SM_DinoStructure"][0] if v.y > 10.4 and abs(v.x) < 6.5 and v.z < 14.5]   # frame rings
moon += [v for v in meshes["SM_DinoBulbs"][0] if v.y > 10.2]                                          # bulb ring
for vname, eye in VIEWS.items():
    eye = Vector(eye)
    hit = 0
    for p in moon:
        f = (arch.SCREEN_Y - eye.y) / (p.y - eye.y)
        q = eye + (p - eye) * f
        hit += inside_outline(q.x, q.z)
    log(f"moon + rings + ring bulbs covered from {vname}: {hit}/{len(moon)} vertices")

# ------------------------------------------------------------------ 4. the fit from each view (see-through gaps)
occluders = {n: b for n, b in bvhs.items() if n not in BACKGROUND}


def first_hit(o, d, dist):
    best = (None, dist)
    for n, b in occluders.items():
        loc, _, _, t = b.ray_cast(o, d, best[1])
        if loc is not None and t < best[1]:
            best = (n, t)
    return best


corners = [Vector((x, arch.SCREEN_Y, z)) for x, z in outline]
edge_pts = []                                                         # (point, outward normal): the outline's vertices
for i, a in enumerate(corners):                                       # and every <= 25 cm along each edge
    b = corners[(i + 1) % len(corners)]
    n_v = (b - corners[i - 1])
    edge_pts.append((a, Vector((n_v.z, 0, -n_v.x)).normalized()))     # outward in the plane (CCW outline seen from -Y)
    n_e = Vector(((b - a).z, 0, -(b - a).x)).normalized()
    steps = int((b - a).length / 0.25)
    edge_pts += [(a.lerp(b, k / (steps + 1)), n_e) for k in range(1, steps + 1)]
for vname, eye in VIEWS.items():
    eye = Vector(eye)
    gaps, total, worst = 0, 0, []
    for q, nout in edge_pts:
        for delta in (arch.SCREEN_CLEAR + 0.01, arch.SCREEN_CLEAR + 0.03, 0.10, 0.20):   # past the clearance band
            target = q + nout * delta
            d = (target - eye).normalized()
            reach = (target - eye).length
            name, t = first_hit(eye, d, reach + 40.0)
            total += 1
            if name is None or t > reach + 3.0:                       # nothing, or something far behind the plane
                gaps += 1
                worst.append((delta, q, name))
    examples = ", ".join(f"({q.x:.1f},{q.z:.1f}) +{dl * 100:.0f}cm"
                         for dl, q, _ in sorted(worst, key=lambda w: -w[0])[:4])
    log(f"fit from {vname}: {gaps}/{total} rays just outside the screen edge see past the bone"
        + (f" (e.g. {examples})" if gaps else ""))

# ------------------------------------------------------------------ 5. what the arch's bone touches
st = bvhs["SM_DinoStructure"]
touch = []
for n, b in bvhs.items():
    if n in ("SM_DinoStructure", "SM_DinoEyes") or n in BACKGROUND:
        continue
    pairs = st.overlap(b)
    if pairs:
        v, p = meshes["SM_DinoStructure"]
        for g in clusters(v, p, [i for i, _ in pairs]):
            touch.append(f"{n}: bone {len(g)} tris at {where(v, p, g)}")
log("SM_DinoStructure (arch, skull, moon frame, deck decor) touches: " + ("; ".join(touch) if touch else "nothing"))

# ------------------------------------------------------------------ 6. mirror images + the horn-tip table
err = 0.0
for a, b in zip(arch.spine_rings(1), arch.spine_rings(-1)):
    err = max(err, max((arch.mirror(p, -1) - q).length for p, q in zip(a, b)))
for k in range(len(arch.HORN_T)):
    hr, hl = arch.horn(1, k), arch.horn(-1, k)
    err = max(err, max((arch.mirror(p, -1) - q).length for p, q in zip(hr["pts"], hl["pts"])))
    err = max(err, (arch.mirror_axis(hr["axis"], -1) - hl["axis"]).length)
for i in range(len(arch.SPIKE_T)):
    sr, sl = arch.spike(1, i)["pts"], arch.spike(-1, i)["pts"]
    err = max(err, max((arch.mirror(p, -1) - q).length for p, q in zip(sr, sl)))
log(f"mirror: left wing vs mirrored right wing (spine rings, horn paths + curl axes, spikes): max error {err:.1e} m")
sv_ = meshes["SM_DinoStructure"][0]
kd = KDTree(len(sv_))
for i, v in enumerate(sv_):
    kd.insert(v, i)
kd.balance()
lr = arch.lintel_rings()
seam = max((arch.mirror(p, -1) - p).length for p in lr[-1])          # the ring both halves share (x = 0)
built = max(kd.find(arch.mirror(p, s))[2] for ring in lr for p in ring for s in (1, -1))
log(f"lintel: rings at |x| {', '.join(f'{x:.2f}' for x in arch.LINTEL_XS)}; center z {arch.LINTEL_Z} (inner edge "
    f"{arch.LINTEL_Z - arch.LINTEL_R:.2f}) out to |x| {arch.LINTEL_X0}, rising to {arch.LINTEL_Z1:.3f} at "
    f"{arch.LINTEL_X1} (inside the spine); shared ring at x 0 mirror error {seam:.1e} m; both halves in "
    f"SM_DinoStructure: farthest ring vertex {built:.1e} m from a mesh vertex")
def half_width(z):
    """x of the right wing's center line at height z."""
    return min((abs(arch.spine_point(1, i / 4000).z - z), arch.spine_point(1, i / 4000).x) for i in range(4001))[1]


log(f"arch spine: length {arch.SPINE_LENGTH:.2f} m per wing, foot at x +-{arch.BASE_X} (center), end at "
    f"(+-{arch.END_X}, {arch.PLANE_Y}, {arch.END_Z}); half-width of the center line at z 9: {half_width(9.0):.2f} m, "
    f"at z 15.6: {half_width(15.6):.2f} m")
for (side, k), (last, tan) in sorted(arch.horn_tips().items(), key=lambda kv: (-kv[0][1], kv[0][0])):
    apex = Vector(last) + Vector(tan) * 0.11
    log(f"horn tip {'L' if side < 0 else 'R'}{k}: last ({last[0]:.2f}, {last[1]:.2f}, {last[2]:.2f}) tangent "
        f"({tan[0]:.3f}, {tan[1]:.3f}, {tan[2]:.3f}) apex ({apex.x:.2f}, {apex.y:.2f}, {apex.z:.2f})"
        f"{'' if apex.y < arch.SCREEN_Y else '  BEHIND THE SCREEN PLANE'}")

# ------------------------------------------------------------------ 7. the giant intro's column stays clear
GIANT = {"cx": 0.0, "cy": 1.68, "ax": 1.4, "by": 1.0, "z0": DROP + 0.05, "z1": DROP + 8.0}   # giant.py HEM, pre-drop z
ring = [Vector((GIANT["cx"] + GIANT["ax"] * math.cos(2 * math.pi * i / 48),
                GIANT["cy"] + GIANT["by"] * math.sin(2 * math.pi * i / 48), 0.0)) for i in range(48)]
cv = [p + Vector((0, 0, GIANT["z0"])) for p in ring] + [p + Vector((0, 0, GIANT["z1"])) for p in ring]
cp = [[i, (i + 1) % 48, 48 + (i + 1) % 48, 48 + i] for i in range(48)] + [list(range(48)), list(range(48, 96))]
col_bvh = BVHTree.FromPolygons(cv, cp)


def in_column(v):
    return (GIANT["z0"] <= v.z <= GIANT["z1"]
            and ((v.x - GIANT["cx"]) / GIANT["ax"]) ** 2 + ((v.y - GIANT["cy"]) / GIANT["by"]) ** 2 <= 1.0)


inside = []
for n, (v, p) in meshes.items():
    if n in BACKGROUND:
        continue
    k = sum(in_column(q) for q in v)
    crossing = len(col_bvh.overlap(bvhs[n])) if n in bvhs else 0
    if k or crossing:
        inside.append(f"{n}: {k} vertices inside, {crossing} tris crossing its wall")
log(f"giant column (hem ellipse ({GIANT['cx']}, {GIANT['cy']}) {GIANT['ax']} x {GIANT['by']} m, pre-drop z "
    f"{GIANT['z0']:.2f}..{GIANT['z1']:.2f}): " + ("; ".join(inside) if inside else "nothing of the build in it"))
log(f"screen plane y {min(ys):.2f} vs the robe's back edge y {GIANT['cy'] + GIANT['by']:.2f}: "
    f"{min(ys) - GIANT['cy'] - GIANT['by']:.2f} m behind it")
