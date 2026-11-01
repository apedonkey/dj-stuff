import sys, math
sys.path.insert(0, r"C:\Users\Chris\AppData\Local\Temp\claude\sb")
from common import *
import numpy as np
from mathutils.bvhtree import BVHTree

A = sys.argv[sys.argv.index('--') + 1:]
OUT = A[0]
DETAILS = not (len(A) > 1 and A[1] == 'plain')      # 'plain' = breeches: shell + belt only
import common
if len(A) > 2: common.SRC = A[2]
me, arm = load()
print("ME_MW_IDENTITY", me.matrix_world == me.matrix_world.Identity(4))
mw = me.matrix_world
col = sampler([i for i in bpy.data.images if 'color' in i.name][0])

# ---------------- classify parts ----------------
bm = bmesh.new(); bm.from_mesh(me.data); bm.verts.ensure_lookup_table(); uvl = bm.loops.layers.uv.active
P = lambda i: mw @ bm.verts[i].co
pants, caps, torso_low, boots = [], [], [], []
for comp in parts_of(bm):
    co = [P(i) for i in comp]
    zl = min(c.z for c in co); zh = max(c.z for c in co)
    xl = min(c.x for c in co); xh = max(c.x for c in co)
    cx = (xl + xh) / 2
    fs = {f for i in comp for f in bm.verts[i].link_faces}
    cs = [col(l[uvl].uv) for f in fs for l in f.loops]
    avg = sum(sum(c) for c in cs) / len(cs) / 3
    if zl > -0.785 and zh < -0.735 and abs(cx) < 0.2 and len(comp) >= 100:
        caps.append(comp)
    elif 0.2 <= avg <= 0.5 and abs(cx) < 0.25 and zh <= 0.12 and zl >= -0.8:
        pants.append(comp)
    elif abs(cx) < 0.24 and zl < 0.05 and zh > -0.2 and xh < 0.26 and xl > -0.26 and avg < 0.2:
        torso_low.append(comp)
    elif zh < -0.55 and abs(cx) < 0.22:
        boots.append(comp)
print("CLASS pants", len(pants), sum(len(c) for c in pants), "caps", len(caps), "torso_low", len(torso_low), "boots", len(boots))

pants_pts = [P(i) for c in pants for i in c]
torso_pts = [p for c in torso_low for i in c for p in [P(i)] if p.z < 0.01 and abs(p.x) < 0.24]
boot_pts = [P(i) for c in boots for i in c]
env = pants_pts + torso_pts
E = np.array([[p.x, p.y, p.z] for p in env])
B = np.array([[p.x, p.y, p.z] for p in boot_pts])

# crotch: highest z where pants points leave a gap around x=0
Pp = np.array([[p.x, p.y, p.z] for p in pants_pts])
crotch = None
for z in np.arange(-0.45, 0.05, 0.005):
    s = Pp[np.abs(Pp[:, 2] - z) < 0.006]
    if len(s) and np.any(np.abs(s[:, 0]) < 0.012):
        crotch = z; break
print("CROTCH", crotch)

WAIST = 0.004
NB = 40

def circ_median(r, k=5):
    n = len(r); h = k // 2
    return np.array([np.median([r[(i + j) % n] for j in range(-h, h + 1)]) for i in range(n)])

def fill(r):
    r = r.copy(); n = len(r); idx = np.where(r > 0)[0]
    if len(idx) == 0: return r
    for i in range(n):
        if r[i] <= 0:
            d = [(min((i - j) % n, (j - i) % n), j) for j in idx]; d.sort(); r[i] = (r[d[0][1]] + r[d[1][1]]) / 2 if len(d) > 1 else r[d[0][1]]
    return r

def profile(pts, cx, cy, nb=NB):
    r = np.zeros(nb)
    if len(pts):
        a = np.arctan2(pts[:, 1] - cy, pts[:, 0] - cx); rr = np.hypot(pts[:, 0] - cx, pts[:, 1] - cy)
        b = ((a + math.pi) / (2 * math.pi) * nb).astype(int) % nb
        for k in range(nb):
            m = rr[b == k]
            if len(m): r[k] = m.max()
    r = circ_median(fill(r), 7)
    for _ in range(2): r = (np.roll(r, 1) + 2 * r + np.roll(r, -1)) / 4
    return r

def ang(k, nb=NB): return -math.pi + (k + 0.5) / nb * 2 * math.pi

def smoothstep(a, b, x):
    t = min(1, max(0, (x - a) / (b - a))); return t * t * (3 - 2 * t)

# ---------------- leg profiles ----------------
ZB = -0.745
legs = {}
for side in (1, -1):
    zs = np.arange(ZB, crotch + 0.075, 0.015)
    rings = []
    for z in zs:
        s = E[(np.abs(E[:, 2] - z) < 0.012) & (E[:, 0] * side > 0)]
        if len(s) < 8: continue
        cx = (s[:, 0].min() + s[:, 0].max()) / 2; cy = (s[:, 1].min() + s[:, 1].max()) / 2
        rings.append([z, cx, cy, profile(s, cx, cy)])
    # smooth along z
    for k in range(1, len(rings) - 1):
        for j in (1, 2): rings[k][j] = (rings[k - 1][j] + 2 * rings[k][j] + rings[k + 1][j]) / 4
    for _ in range(3):
        sm = [r[3].copy() for r in rings]
        for k in range(1, len(rings) - 1): rings[k][3] = (sm[k - 1] + 2 * sm[k] + sm[k + 1]) / 4
    # boot rim profile
    zr = -0.665
    c0 = min(rings, key=lambda r: abs(r[0] - zr))
    sb = B[(B[:, 2] > -0.70) & (B[:, 2] < -0.63) & (B[:, 0] * side > 0)]
    boot_r = profile(sb, c0[1], c0[2]) if len(sb) > 8 else None
    print("BOOTRIM", side, None if boot_r is None else round(float(boot_r.mean()), 3), "leg@rim", round(float(c0[3].mean()), 3))
    out = []
    for z, cx, cy, r in rings:
        off = 0.010 + 0.006 * smoothstep(-0.45, -0.2, z)          # roomier thigh
        rr = r + off
        if boot_r is not None:
            w = smoothstep(-0.66, -0.595, z)
            inside = np.minimum(rr, boot_r - 0.007)
            rr = inside * (1 - w) + rr * w + 0.013 * math.sin(math.pi * w)   # blousing over the boot
        out.append((z, cx, cy, rr))
    legs[side] = out

# ---------------- hip profile ----------------
hip = []
for z in np.arange(crotch - 0.005, WAIST + 0.0001, 0.01):
    s = E[np.abs(E[:, 2] - z) < 0.01]
    cy = (s[:, 1].min() + s[:, 1].max()) / 2
    r = profile(s, 0.0, cy, 56)
    off = 0.007 if z < -0.03 else 0.005
    hip.append((z, 0.0, cy, r + off))
for _ in range(3):
    hs = [h[3].copy() for h in hip]
    for k in range(1, len(hip) - 1): hip[k] = (hip[k][0], 0.0, hip[k][2], (hs[k - 1] + 2 * hs[k] + hs[k + 1]) / 4)

def loft(name, rings, nb):
    verts, faces = [], []
    for z, cx, cy, r in rings:
        for k in range(nb):
            a = ang(k, nb); verts.append((cx + r[k] * math.cos(a), cy + r[k] * math.sin(a), z))
    n = len(rings)
    for i in range(n - 1):
        for k in range(nb):
            a = i * nb + k; b = i * nb + (k + 1) % nb
            faces.append((a, b, b + nb, a + nb))
    faces.append(tuple(range(nb))[::-1]); faces.append(tuple(range((n - 1) * nb, n * nb)))
    m = bpy.data.meshes.new(name); m.from_pydata(verts, [], faces); m.update()
    o = bpy.data.objects.new(name, m); bpy.context.scene.collection.objects.link(o); return o

objs = [loft("legL", legs[1], NB), loft("legR", legs[-1], NB), loft("hip", hip, 56)]
bpy.ops.object.select_all(action='DESELECT')
for o in objs: o.select_set(True)
bpy.context.view_layer.objects.active = objs[0]; bpy.ops.object.join()
shell = bpy.context.active_object; shell.name = "Pants"
rm = shell.modifiers.new("rm", 'REMESH'); rm.mode = 'VOXEL'; rm.voxel_size = 0.0055
bpy.ops.object.modifier_apply(modifier="rm")
# open waist + ankles
sb_ = bmesh.new(); sb_.from_mesh(shell.data)
bmesh.ops.delete(sb_, geom=[v for v in sb_.verts if v.co.z > WAIST - 0.003 or v.co.z < ZB + 0.004], context='VERTS')
sb_.to_mesh(shell.data); sb_.free()
sm = shell.modifiers.new("sm", 'LAPLACIANSMOOTH'); sm.lambda_factor = 0.5; sm.iterations = 6; sm.use_volume_preserve = True
bpy.ops.object.modifier_apply(modifier="sm")
dc = shell.modifiers.new("dc", 'DECIMATE'); dc.ratio = min(1.0, 9000 / max(1, len(shell.data.polygons) * 2))
bpy.ops.object.modifier_apply(modifier="dc")
bpy.ops.object.mode_set(mode='EDIT'); bpy.ops.mesh.select_all(action='SELECT'); bpy.ops.mesh.normals_make_consistent(inside=False); bpy.ops.object.mode_set(mode='OBJECT')
for p in shell.data.polygons: p.use_smooth = True
print("SHELL tris", sum(len(p.vertices) - 2 for p in shell.data.polygons))

dg = bpy.context.evaluated_depsgraph_get()
bvh = BVHTree.FromObject(shell, dg)

def leg_center(side, z):
    L = legs[side]
    if z <= L[0][0]: return L[0][1], L[0][2]
    for a, b in zip(L, L[1:]):
        if a[0] <= z <= b[0]:
            t = (z - a[0]) / (b[0] - a[0]); return a[1] + t * (b[1] - a[1]), a[2] + t * (b[2] - a[2])
    return L[-1][1], L[-1][2]

def hip_center(z):
    return 0.0, min(hip, key=lambda h: abs(h[0] - z))[2]

def surf(c, a, z):
    d = Vector((math.cos(a), math.sin(a), 0))
    o = Vector((c[0], c[1], z)) + d * 0.005
    hit = bvh.ray_cast(o, d, 0.5)      # from inside the leg/pelvis outwards: first hit is this leg, never the other one
    if hit[0] is None: return Vector((c[0], c[1], z)) + d * 0.1, d
    return hit[0], d

# ---------------- detail geometry ----------------
parts = []   # (name, verts, faces, kind, smooth)

def pad(name, centre_fn, a0, a1, z0, z1, h, bulge, nu, nv, kind, inset=0.003, open_bottom=False):
    """Raised pad conforming to the pants: border ring sits just under the surface, inner grid at height h(+bulge)."""
    V, F = [], []
    U = nu + 2; W = nv + 2
    for j in range(W):
        for i in range(U):
            ui = min(max(i - 0.5, 0), nu - 1) / (nu - 1); vj = min(max(j - 0.5, 0), nv - 1) / (nv - 1)
            a = a0 + (a1 - a0) * ui; z = z0 + (z1 - z0) * vj
            p, d = surf(centre_fn(z), a, z)
            border = i in (0, U - 1) or j in (0, W - 1)
            if border and not (open_bottom and j == 0):
                hh = -inset
            else:
                hh = h + bulge * math.sin(math.pi * ui) * math.sin(math.pi * vj)
            V.append(tuple(p + d * hh))
    for j in range(W - 1):
        for i in range(U - 1):
            a = j * U + i; F.append((a, a + 1, a + 1 + U, a + U))
    parts.append((name, V, F, kind, True))

def box(name, centre, d, z, w, hgt, depth, kind):
    up = Vector((0, 0, 1)); t = up.cross(d).normalized()
    V = []
    for dz in (-hgt / 2, hgt / 2):
        for dt in (-w / 2, w / 2):
            for dd in (-0.002, depth):
                V.append(tuple(centre + t * dt + d * dd + up * dz))
    F = [(0, 1, 3, 2), (4, 6, 7, 5), (0, 4, 5, 1), (2, 3, 7, 6), (0, 2, 6, 4), (1, 5, 7, 3)]
    parts.append((name, V, F, kind, False))

for side in ((1, -1) if DETAILS else ()):
    out_a = 0.0 if side == 1 else math.pi          # outer thigh direction (+x for the left leg)
    cf = lambda z, s=side: leg_center(s, z)
    rr = float(np.mean(legs[side][len(legs[side]) // 2][3]))
    da = 0.060 / max(rr, 0.05)
    # cargo pocket + flap + snap
    pad(f"pocket{side}", cf, out_a - da, out_a + da, -0.40, -0.215, 0.010, 0.008, 6, 7, 'FABRIC')
    pad(f"flap{side}", cf, out_a - da * 1.1, out_a + da * 1.1, -0.235, -0.188, 0.022, 0.003, 6, 3, 'FABRIC', inset=0.0)
    p, d = surf(cf(-0.226), out_a, -0.226)
    box(f"snap{side}", p, d, -0.226, 0.013, 0.010, 0.027, 'METAL')
    # knee panel (front of leg = -Y)
    ka = -math.pi / 2; dk = 0.065 / max(rr, 0.05)
    pad(f"knee{side}", cf, ka - dk, ka + dk, -0.56, -0.41, 0.004, 0.003, 6, 6, 'PANEL')
    # back patch pocket with flap (back = +Y), offset towards each cheek
    ba = math.pi / 2 - side * 0.42; dbk = 0.055 / 0.17
    pad(f"bpocket{side}", hip_center, ba - dbk, ba + dbk, -0.165, -0.075, 0.006, 0.004, 6, 5, 'FABRIC')
    pad(f"bflap{side}", hip_center, ba - dbk * 1.08, ba + dbk * 1.08, -0.09, -0.062, 0.012, 0.002, 6, 2, 'FABRIC', inset=0.0)

# belt: band around the waist, buckle at the front, loops
NBELT = 72; zr = (-0.047, -0.0275, -0.008)
V, F = [], []
for k in range(NBELT):
    a = -math.pi + k / NBELT * 2 * math.pi
    for zi, z in enumerate((zr[0] - 0.001,) + zr + (zr[2] + 0.001,)):
        p, d = surf(hip_center(z), a, z)
        V.append(tuple(p + d * (-0.002 if zi in (0, 4) else 0.006)))
for k in range(NBELT):
    k2 = (k + 1) % NBELT
    for zi in range(4): F.append((k * 5 + zi, k2 * 5 + zi, k2 * 5 + zi + 1, k * 5 + zi + 1))
parts.append(("belt", V, F, 'WEBBING', True))
p, d = surf(hip_center(-0.0275), -math.pi / 2, -0.0275)
box("buckle", p, d, -0.0275, 0.060, 0.048, 0.016, 'METAL')
box("buckle_bar", p + d * 0.016, d, -0.0275, 0.044, 0.010, 0.006, 'WEBBING')
for a in (-math.pi / 2 - 0.75, -math.pi / 2 + 0.75, 0.0, math.pi, math.pi / 2 - 0.35, math.pi / 2 + 0.35):
    p, d = surf(hip_center(-0.026), a, -0.026)
    box("loop", p, d, -0.026, 0.013, 0.058, 0.010, 'FABRIC')
# a strap around each thigh under the pocket
for side in ((1, -1) if DETAILS else ()):
    cf = lambda z, s=side: leg_center(s, z)
    V, F = [], []
    N = 48
    for k in range(N):
        a = -math.pi + k / N * 2 * math.pi
        for zi, z in enumerate((-0.437, -0.435, -0.413, -0.411)):
            p, d = surf(cf(z), a, z)
            V.append(tuple(p + d * (-0.002 if zi in (0, 3) else 0.005)))
    for k in range(N):
        k2 = (k + 1) % N
        for zi in range(3): F.append((k * 4 + zi, k2 * 4 + zi, k2 * 4 + zi + 1, k * 4 + zi + 1))
    parts.append((f"strap{side}", V, F, 'WEBBING', True))
    out_a = 0.0 if side == 1 else math.pi
    p, d = surf(cf(-0.424), out_a, -0.424)
    box(f"strapbuckle{side}", p, d, -0.424, 0.030, 0.030, 0.012, 'METAL')

# ---------------- texture atlas: find free space and paint patches ----------------
imgs = {k: bpy.data.images['final_' + k] for k in ('color', 'normal', 'orm')}
remove = set(i for c in pants + caps for i in c)
G = 128; occ = np.zeros((G, G), bool)
for f in bm.faces:
    if any(v.index in remove for v in f.verts): continue
    us = [(l[uvl].uv.x * G, l[uvl].uv.y * G) for l in f.loops]
    for ux, uy in us: occ[min(G - 1, max(0, int(uy))), min(G - 1, max(0, int(ux)))] = True   # tiny/degenerate tris
    for t in range(1, len(us) - 1):
        (ax, ay), (bx, by), (cx_, cy_) = us[0], us[t], us[t + 1]
        x0 = max(0, int(min(ax, bx, cx_))); x1 = min(G - 1, int(max(ax, bx, cx_)))
        y0 = max(0, int(min(ay, by, cy_))); y1 = min(G - 1, int(max(ay, by, cy_)))
        den = (by - cy_) * (ax - cx_) + (cx_ - bx) * (ay - cy_)
        for yy in range(y0, y1 + 1):
            for xx in range(x0, x1 + 1):
                hit = False
                for px_, py_ in ((xx + .5, yy + .5), (xx, yy), (xx + 1, yy), (xx, yy + 1), (xx + 1, yy + 1)):
                    if abs(den) < 1e-12: hit = True; break
                    l1 = ((by - cy_) * (px_ - cx_) + (cx_ - bx) * (py_ - cy_)) / den
                    l2 = ((cy_ - ay) * (px_ - cx_) + (ax - cx_) * (py_ - cy_)) / den
                    if l1 >= -0.05 and l2 >= -0.05 and l1 + l2 <= 1.05: hit = True; break
                if hit: occ[yy, xx] = True
# also any cell containing a vertex, then dilate by one cell for mip/bleed safety
o2 = occ.copy()
o2[1:, :] |= occ[:-1, :]; o2[:-1, :] |= occ[1:, :]; o2[:, 1:] |= occ[:, :-1]; o2[:, :-1] |= occ[:, 1:]
occ = o2
def find_free(n):
    for y in range(G - n):
        for x in range(G - n):
            if not occ[y:y + n, x:x + n].any():
                occ[y:y + n, x:x + n] = True; return x, y
    return None
SPEC = {  # srgb colour, roughness, metallic, cells(16px)
    'FABRIC': ((0.115, 0.115, 0.12), 0.92, 0.0, 6),
    'PANEL': ((0.085, 0.085, 0.09), 0.92, 0.0, 4),
    'WEBBING': ((0.04, 0.04, 0.045), 0.78, 0.0, 4),
    'METAL': ((0.62, 0.62, 0.64), 0.30, 1.0, 4),
}
print("ATLAS free cells", int((~occ).sum()), "of", G * G)
rng = np.random.default_rng(7)
arrs = {}
for k, img in imgs.items():
    a = np.empty(img.size[0] * img.size[1] * 4, np.float32); img.pixels.foreach_get(a); arrs[k] = a.reshape(img.size[1], img.size[0], 4)
patch = {}
for kind, (c, rough, metal, n) in SPEC.items():
    xy = find_free(n + 2)
    assert xy, "no atlas space for " + kind
    x, y = xy[0] + 1, xy[1] + 1
    u0, v0, u1, v1 = x / G, y / G, (x + n) / G, (y + n) / G
    patch[kind] = (u0, v0, u1, v1)
    for k, a in arrs.items():
        H, W = a.shape[:2]
        X0, Y0, X1, Y1 = int(u0 * W) - 2, int(v0 * H) - 2, int(u1 * W) + 2, int(v1 * H) + 2
        if k == 'color':
            noise = rng.normal(0, 0.004, (Y1 - Y0, X1 - X0, 1)) if kind in ('FABRIC', 'PANEL') else 0
            a[Y0:Y1, X0:X1, :3] = np.clip(np.array(c) + noise, 0, 1); a[Y0:Y1, X0:X1, 3] = 1
        elif k == 'normal':
            a[Y0:Y1, X0:X1] = (0.5, 0.5, 1.0, 1.0)
        else:
            a[Y0:Y1, X0:X1] = (1.0, rough, metal, 1.0)
    print("PATCH", kind, [round(t, 4) for t in patch[kind]])
for k, img in imgs.items():
    img.pixels.foreach_set(arrs[k].ravel()); img.update(); img.pack()

# ---------------- build objects, UVs, weights ----------------
def make_obj(name, V, F, kind, smooth):
    m = bpy.data.meshes.new(name); m.from_pydata(V, [], F); m.update()
    o = bpy.data.objects.new(name, m); bpy.context.scene.collection.objects.link(o)
    o["kind"] = kind
    for p in m.polygons: p.use_smooth = smooth
    return o
new = [make_obj(*p) for p in parts]
shell["kind"] = 'FABRIC'; new.append(shell)
for o in new:
    m = o.data
    while m.uv_layers: m.uv_layers.remove(m.uv_layers[0])
    uv = m.uv_layers.new(name="UVMap")
    u0, v0, u1, v1 = patch[o["kind"]]
    pu = u0 + (u1 - u0) * 0.15; pv = v0 + (v1 - v0) * 0.15; su = (u1 - u0) * 0.7; sv = (v1 - v0) * 0.7
    for poly in m.polygons:
        for li in poly.loop_indices:
            co = m.vertices[m.loops[li].vertex_index].co
            uu = min(1, max(0, (co.x + 0.3 + 0.5 * co.y) / 0.9)); vv = min(1, max(0, (co.z + 0.8) / 0.85))
            uv.data[li].uv = (pu + su * uu, pv + sv * vv)
    m.materials.append(me.data.materials[0])

# weight source: original pants + lower torso + boots (no hands)
src = me.copy(); src.data = me.data.copy(); src.name = "wsrc"; bpy.context.scene.collection.objects.link(src)
src.modifiers.clear()
keep = set(i for c in pants + caps + torso_low + boots for i in c)
sbm = bmesh.new(); sbm.from_mesh(src.data); sbm.verts.ensure_lookup_table()
bmesh.ops.delete(sbm, geom=[v for v in sbm.verts if v.index not in keep], context='VERTS'); sbm.to_mesh(src.data); sbm.free()
for o in new:
    bpy.ops.object.select_all(action='DESELECT'); o.select_set(True); bpy.context.view_layer.objects.active = o
    md = o.modifiers.new("dt", 'DATA_TRANSFER'); md.object = src; md.use_vert_data = True
    md.data_types_verts = {'VGROUP_WEIGHTS'}; md.vert_mapping = 'POLYINTERP_NEAREST'
    md.layers_vgroup_select_src = 'ALL'; md.layers_vgroup_select_dst = 'NAME'
    bpy.ops.object.datalayout_transfer(modifier="dt")
    bpy.ops.object.modifier_apply(modifier="dt")
    bpy.ops.object.vertex_group_limit_total(limit=4)
    bpy.ops.object.vertex_group_normalize_all(lock_active=False)
    unweighted = sum(1 for v in o.data.vertices if not v.groups or sum(g.weight for g in v.groups) < 0.99)
    if unweighted: print("UNWEIGHTED", o.name, unweighted)
bpy.data.objects.remove(src)

# ---------------- remove old pants, join, export ----------------
bpy.ops.object.select_all(action='DESELECT'); bpy.context.view_layer.objects.active = me; me.select_set(True)
bpy.ops.object.mode_set(mode='EDIT'); bpy.ops.mesh.select_mode(type='VERT'); bpy.ops.mesh.select_all(action='DESELECT')
bpy.ops.object.mode_set(mode='OBJECT')
for v in me.data.vertices: v.select = v.index in remove
before = len(me.data.vertices)
bpy.ops.object.mode_set(mode='EDIT'); bpy.ops.mesh.delete(type='VERT'); bpy.ops.object.mode_set(mode='OBJECT')
print("DELETED", before - len(me.data.vertices), "expected", len(remove))
for o in new: o.select_set(True)
me.select_set(True); bpy.context.view_layer.objects.active = me
bpy.ops.object.join()
print("FINAL tris", sum(len(p.vertices) - 2 for p in me.data.polygons), "uv layers", [u.name for u in me.data.uv_layers], "mats", len(me.data.materials))
# keep a single material slot
while len(me.data.materials) > 1: me.data.materials.pop()
for p in me.data.polygons: p.material_index = 0
bpy.ops.object.select_all(action='DESELECT'); me.select_set(True); arm.select_set(True)
bpy.ops.export_scene.gltf(filepath=OUT, export_format='GLB', use_selection=True, export_animations=False)
print("EXPORTED", OUT)
