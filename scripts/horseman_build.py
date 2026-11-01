"""Headless Horseman from skullbuck's rigged body.
Input : breeches.glb (skullbuck with plain pants, from cargo.py 'plain')
Output: <out>/horseman.glb  (skin: headless rider in a long coat + a skinned jack-o'-lantern on the Head bone,
                              with DH_C/DH_F/DH_U marker bones for the detachable-head hook)
        <out>/horseman_head.glb (the same pumpkin as a STATIC mesh, origin at its centre, for flying)
"""
import sys, math
sys.path.insert(0, r"C:\Users\Chris\AppData\Local\Temp\claude\sb")
import common
common.SRC = r"C:\Users\Chris\AppData\Local\Temp\claude\sb\breeches.glb"
from common import *
import numpy as np
from mathutils import Vector, Matrix
from mathutils.bvhtree import BVHTree

OUT = sys.argv[sys.argv.index('--') + 1]
me, arm = load(); mw = me.matrix_world
assert mw == Matrix.Identity(4)
gi = {g.index: g.name for g in me.vertex_groups}
B = lambda n: Vector(arm.data.bones[n].head_local)
for n in ('Hips', 'Spine2', 'Neck', 'Head', 'LeftShoulder', 'LeftArm', 'LeftForeArm', 'LeftHand'): print("BONE", n, [round(x, 3) for x in B(n)])

# ---------------- classify vertices by dominant bone ----------------
def dom(v):
    if not v.groups: return ''
    g = max(v.groups, key=lambda g: g.weight); return gi[g.group]
D = [dom(v) for v in me.data.vertices]
V = np.array([[v.co.x, v.co.y, v.co.z] for v in me.data.vertices])
HEADB = {'Head', 'LeftEye', 'RightEye'}
UPPER = HEADB | {'Neck', 'Spine', 'Spine1', 'Spine2', 'LeftShoulder', 'RightShoulder'}
ARMB = {'LeftArm', 'RightArm', 'LeftForeArm', 'RightForeArm'}
ishand = lambda d: 'Hand' in d
remove = {i for i, d in enumerate(D) if d in UPPER or d in ARMB or (V[i, 2] > 0.02 and not ishand(d)) or (ishand(d) and V[i, 2] > -0.075)}
bm0 = bmesh.new(); bm0.from_mesh(me.data); bm0.verts.ensure_lookup_table()
belt_idx = set()
for comp in parts_of(bm0):                      # the breeches' belt/buckle/loops: small parts living only in z -0.06..0
    zs = [bm0.verts[i].co.z for i in comp]
    if min(zs) > -0.06 and max(zs) < 0.0 and len(comp) < 1500 and not any(ishand(D[i]) for i in comp): belt_idx |= set(comp)
remove |= belt_idx
bm0.free()
print("REMOVE", len(remove), "of", len(D))
torso_src = np.array([i for i, d in enumerate(D) if d not in ARMB and not ishand(d) and d not in HEADB and i not in belt_idx and -0.14 <= V[i, 2] <= 0.57 and not ('Shoulder' in d and V[i, 2] > 0.43) and math.hypot(V[i, 0], V[i, 1]) < 0.30] +
                     [i for i, d in enumerate(D) if d in HEADB and V[i, 2] < 0.57 and math.hypot(V[i, 0], V[i, 1] + 0.0) < 0.12])  # + the neck
neck_src = np.array([i for i, d in enumerate(D) if d in HEADB | {'Neck'} and 0.40 < V[i, 2] < 0.57 and math.hypot(V[i, 0], V[i, 1]) < 0.12])
pants_src = np.array([i for i, d in enumerate(D) if ('UpLeg' in d or d == 'Hips') and -0.55 < V[i, 2] < 0.0 and i not in belt_idx])
print("SRC torso", len(torso_src), "neck", len(neck_src), "pants", len(pants_src))

NBIN = 56
def circ_median(r, k=5):
    n = len(r); h = k // 2
    return np.array([np.median([r[(i + j) % n] for j in range(-h, h + 1)]) for i in range(n)])
def fill(r):
    r = r.copy(); n = len(r); idx = np.where(r > 0)[0]
    if len(idx) == 0: return r
    for i in range(n):
        if r[i] <= 0:
            d = sorted((min((i - j) % n, (j - i) % n), j) for j in idx); r[i] = (r[d[0][1]] + r[d[1][1]]) / 2 if len(d) > 1 else r[d[0][1]]
    return r
def profile(pts, cx, cy, nb=NBIN, k=5, sm=2):
    r = np.zeros(nb)
    if len(pts):
        a = np.arctan2(pts[:, 1] - cy, pts[:, 0] - cx); rr = np.hypot(pts[:, 0] - cx, pts[:, 1] - cy)
        b = ((a + math.pi) / (2 * math.pi) * nb).astype(int) % nb
        for q in range(nb):
            m = rr[b == q]
            if len(m): r[q] = m.max()
    r = circ_median(fill(r), k)
    for _ in range(sm): r = (np.roll(r, 1) + 2 * r + np.roll(r, -1)) / 4
    return r
def ang(k, nb=NBIN): return -math.pi + (k + 0.5) / nb * 2 * math.pi
def smoothstep(a, b, x):
    t = min(1, max(0, (x - a) / (b - a))); return t * t * (3 - 2 * t)
def smooth_rings(rings, n=3):
    for _ in range(n):
        rs = [r[3].copy() for r in rings]
        for k in range(1, len(rings) - 1): rings[k] = (rings[k][0], rings[k][1], rings[k][2], (rs[k - 1] + 2 * rs[k] + rs[k + 1]) / 4)
    return rings

parts = []   # (name, verts, faces, kind, smooth, weights)  weights: None = transfer, or {'Bone': w}

def loft(name, rings, nb, kind, cap_bottom=False, cap_top=False, weights=None, partial=None):
    """rings: list of (z, cx, cy, r[nb]) or explicit ring point lists via partial (list of lists of Vector)."""
    verts, faces = [], []
    if partial is None:
        for z, cx, cy, r in rings:
            zz = np.broadcast_to(np.asarray(z, dtype=float), (nb,))      # z may be per-vertex (the open-front cowl)
            for k in range(nb):
                a = ang(k, nb); verts.append((cx + r[k] * math.cos(a), cy + r[k] * math.sin(a), float(zz[k])))
        n = len(rings); closed = True
    else:
        for ring in partial:
            for p in ring: verts.append(tuple(p))
        n = len(partial); nb = len(partial[0]); closed = False
    for i in range(n - 1):
        for k in range(nb - (0 if closed else 1)):
            a = i * nb + k; b = i * nb + (k + 1) % nb
            faces.append((a, b, b + nb, a + nb))
    if cap_bottom: faces.append(tuple(range(nb))[::-1])
    if cap_top: faces.append(tuple(range((n - 1) * nb, n * nb)))
    parts.append((name, verts, faces, kind, True, weights))
    return verts, faces

# ---------------- torso + collar (one loft) ----------------
# Pumpkin placement (used by the collar below and the pumpkin section). 2026-10-10: PC_Z lowered 0.665 -> 0.60 and the
# collar flared into a cowl, after the user: "its basically sitting on top of the collar of the coat. i want it lower so that
# the collar is like halfway up the sides of the pumpkin head. so it looks normal basically". The pumpkin's equator now sits
# ~1.5 cm above the collar top (0.585); the collar rings stay >= 1.2 cm outside the pumpkin's surface so it never pokes through.
PC_Y, PC_Z, PR = -0.01, 0.60, 0.15
def pumpkin_r_at(z):                                   # the squashed sphere's radius at height z (z scale 0.82 up / 0.78 down)
    t = (z - PC_Z) / (PR * (0.82 if z > PC_Z else 0.78))
    return PR * math.sqrt(max(0.0, 1 - t * t))
T = V[torso_src]
Z_HEM, Z_COLLAR0, Z_COLLAR1 = -0.06, 0.50, 0.585
neckpts = V[neck_src]; neck_cy = (neckpts[:, 1].min() + neckpts[:, 1].max()) / 2
neck_r = profile(neckpts, 0.0, neck_cy, k=7, sm=4)
print("NECK r mean", round(float(neck_r.mean()), 3), "cy", round(float(neck_cy), 3))
rings = []
for z in np.arange(Z_HEM, Z_COLLAR0 + 1e-6, 0.015):
    s = T[np.abs(T[:, 2] - z) < 0.012]
    if len(s) < 10: continue
    cy = (s[:, 1].min() + s[:, 1].max()) / 2
    r = profile(s, 0.0, cy) + 0.010
    w = smoothstep(0.43, 0.515, z)                        # shoulder slope → collar
    r = r * (1 - w) + (neck_r + 0.032) * w; cy = cy * (1 - w) + neck_cy * w
    rings.append((z, 0.0, cy, r))
collar_min = []
for z in np.arange(Z_COLLAR0 + 0.01, Z_COLLAR1 + 1e-6, 0.01):
    f = (z - Z_COLLAR0) / (Z_COLLAR1 - Z_COLLAR0)
    r_flare = neck_r + 0.032 + 0.05 * f                # cowl: ~0.165 at the top, hugging the pumpkin's equator (0.15); clamped below
    r_min = pumpkin_r_at(z) + 0.012 + abs(PC_Y - neck_cy)   # never inside the pumpkin at this height
    rings.append((z, 0.0, neck_cy, np.maximum(r_flare, r_min))); collar_min.append(r_min)
rings = smooth_rings(rings, 2)
for i in range(len(collar_min)):                       # re-apply the clearance after smoothing (it pulled rings ~3 mm inward)
    k = len(rings) - len(collar_min) + i; z, cx, cy, r = rings[k]; rings[k] = (z, cx, cy, np.maximum(np.asarray(r), collar_min[i]))
_cl = [float(np.min(np.asarray(rings[-len(collar_min) + i][3]) - collar_min[i])) for i in range(len(collar_min))]
print("COLLAR top r mean", round(float(np.mean(np.asarray(rings[-1][3]))), 3), "clearance to pumpkin min", round(min(_cl), 4), "(want >= 0)")
torso_rings = rings                                     # the tails and the cape key on these scalar-height rings
# 2026-10-11 (v3): the cowl opens at the FRONT so the whole face reads head-on. The user, from the headset: "The front of
# the collar for the face of the pumpkin needs to be exposed - currently the collar is covering the front half of the face"
# (v2's rim at 0.585 all round hid the mouth, which spans z 0.544-0.578 and +-52 deg of azimuth). Each collar ring keeps its
# height and radius at the back and sides (identical to v2 beyond FRONT_FULL from the front) and dips to the collar base
# across the front: z_k = Z_COLLAR0 + (z - Z_COLLAR0) * g, g = smoothstep(FRONT_OPEN, FRONT_FULL, angle from the front);
# the radius is recomputed for the lowered height (flare + pumpkin clearance), so the front rim hugs the neck under the
# pumpkin's chin (r ~0.12 at z ~0.50) instead of flaring 16 cm out. The rim passes the mouth corners (+-52 deg, z ~0.56)
# at z ~0.51 and reaches the equator only behind +-90 deg.
FRONT_OPEN, FRONT_FULL = math.radians(38), math.radians(100)
_A = np.array([ang(k) for k in range(NBIN)])
_PHI = np.abs((_A + math.pi / 2 + math.pi) % (2 * math.pi) - math.pi)          # angle from the front (-Y): 0 front, pi back
_G = np.maximum(np.array([smoothstep(FRONT_OPEN, FRONT_FULL, p) for p in _PHI]), 0.08)   # floor: no zero-height quads
coat_rings = list(rings[:-len(collar_min)])
for i in range(len(collar_min)):
    z, cx, cy, r = rings[-len(collar_min) + i]
    f = (z - Z_COLLAR0) / (Z_COLLAR1 - Z_COLLAR0)
    zk = Z_COLLAR0 + (z - Z_COLLAR0) * _G
    fk = (zk - Z_COLLAR0) / (Z_COLLAR1 - Z_COLLAR0)
    r_min_k = np.array([pumpkin_r_at(float(h)) for h in zk]) + 0.012 + abs(PC_Y - neck_cy)
    r_formula_k = np.maximum(neck_r + 0.032 + 0.05 * fk, r_min_k)
    r_formula_full = np.maximum(neck_r + 0.032 + 0.05 * f, collar_min[i])
    rk = r_formula_k + (np.asarray(r) - r_formula_full) * _G       # at the back/sides exactly the smoothed v2 ring
    coat_rings.append((zk, cx, cy, rk))
_front = [k for k in range(NBIN) if _PHI[k] < FRONT_OPEN]
print("COWL front rim z", round(float(np.mean(coat_rings[-1][0][_front])), 4), "r", round(float(np.mean(coat_rings[-1][3][_front])), 3),
      "| side (phi 90) z", round(float(coat_rings[-1][0][int(np.argmin(np.abs(_PHI - math.pi / 2)))]), 4),
      "| back rim z", round(float(np.max(coat_rings[-1][0])), 4), "r", round(float(np.mean(np.asarray(rings[-1][3]))), 3))
loft("coat_torso", coat_rings, NBIN, 'COAT')
# collar + top of the shoulders get Neck weights set after transfer (see below): verts with z > 0.49

# ---------------- sleeves: tubes along the arm bones ----------------
def frame(p0, p1):
    a = (p1 - p0).normalized()
    u = a.cross(Vector((0, 0, 1)))
    if u.length < 1e-3: u = a.cross(Vector((1, 0, 0)))
    u.normalize(); v = a.cross(u).normalized(); return a, u, v
def tube(name, p0, p1, src_idx, t0, t1, off, cuff=None, nb=24, step=0.015, dome=False):
    a, u, v = frame(p0, p1); L = (p1 - p0).length
    P = V[src_idx] - np.array(p0); t = P @ np.array(a); Q = P - np.outer(t, np.array(a))
    r = np.linalg.norm(Q, axis=1); th = np.arctan2(Q @ np.array(v), Q @ np.array(u))
    rs = []
    for tt in np.arange(t0, t1 + 1e-6, step):
        m = np.abs(t - tt) < 0.02
        if m.sum() < 6: continue
        prof = np.zeros(nb); b = ((th[m] + math.pi) / (2 * math.pi) * nb).astype(int) % nb
        for q in range(nb):
            mm = r[m][b == q]
            if len(mm): prof[q] = mm.max()
        prof = circ_median(fill(prof), 5)
        for _ in range(2): prof = (np.roll(prof, 1) + 2 * prof + np.roll(prof, -1)) / 4
        extra = off
        if cuff: extra += cuff[1] * smoothstep(cuff[0] - 0.02, cuff[0] + 0.01, tt)
        rs.append((tt, prof + extra))
    for _ in range(2):
        pr = [x[1].copy() for x in rs]
        for k in range(1, len(rs) - 1): rs[k] = (rs[k][0], (pr[k - 1] + 2 * pr[k] + pr[k + 1]) / 4)
    if dome:                                    # rounded shoulder: hemisphere rings before the first ring
        R0 = rs[0][1]; Rd = float(R0.mean()) * 0.95
        for frac in (0.35, 0.6, 0.8, 0.93, 1.0):
            rs.insert(0, (rs[0][0] - 0.0, None)) if False else None
        pre = []
        for frac in (0.3, 0.55, 0.75, 0.9, 0.98):
            tt = rs[0][0] - Rd * frac
            pre.append((tt, R0 * math.sqrt(max(0.0, 1 - frac * frac)) + 0.004))
        rs = pre[::-1] + rs
    rings_pts = []
    for tt, prof in rs:
        c = p0 + a * tt
        rings_pts.append([c + (u * math.cos(ang(k, nb)) + v * math.sin(ang(k, nb))) * prof[k] for k in range(nb)])
    # closed tube: build faces manually (partial=... expects open); reuse loft with explicit rings
    verts, faces = [], []
    for ring in rings_pts:
        for p in ring: verts.append(tuple(p))
    n = len(rings_pts)
    for i in range(n - 1):
        for k in range(nb):
            A_ = i * nb + k; B_ = i * nb + (k + 1) % nb
            faces.append((A_, B_, B_ + nb, A_ + nb))
    if dome: faces.append(tuple(range(nb))[::-1])
    parts.append((name, verts, faces, 'COAT', True, None))
    return L
for side in ('Left', 'Right'):
    pS, pA, pF, pH = B(side + 'Shoulder'), B(side + 'Arm'), B(side + 'ForeArm'), B(side + 'Hand')
    arm_src = np.array([i for i, d in enumerate(D) if d == side + 'Arm' and V[i, 2] < 0.46])
    fore_src = np.array([i for i, d in enumerate(D) if d == side + 'ForeArm'])
    L1 = (pF - pA).length; L2 = (pH - pF).length
    tube(f"sleeve_up_{side}", pA, pF, arm_src, 0.0, L1 + 0.03, 0.008, dome=True)
    tube(f"sleeve_lo_{side}", pF, pH, fore_src, -0.03, L2 + 0.02, 0.008, cuff=(L2 - 0.09, 0.017))
    print("ARM", side, "L1", round(L1, 3), "L2", round(L2, 3), "hand z", round(pH.z, 3))

# ---------------- coat tails: two side panels from the waist to the knee ----------------
Pp = V[pants_src]
hem = min(torso_rings, key=lambda r: abs(r[0] + 0.05)); cy_hip = hem[2]; r_top = hem[3] + 0.004
tail_rings = []
for z in np.arange(-0.04, -0.50 - 1e-6, -0.03):
    f = (-0.04 - z) / 0.46
    cyz = cy_hip + 0.01 * f
    s = Pp[np.abs(Pp[:, 2] - z) < 0.016]
    legs_r = profile(s, 0.0, cyz, k=7, sm=3) + 0.018 if len(s) > 20 else np.zeros(NBIN)
    tail_rings.append((z, 0.0, cyz, np.maximum(r_top * (1 + 0.22 * f ** 1.1), legs_r)))
tail_rings = smooth_rings(tail_rings, 1)
tv, tf = [], []
nb = NBIN
for z, cx, cy, r in tail_rings:
    for k in range(nb):
        a = ang(k, nb); tv.append((cx + r[k] * math.cos(a), cy + r[k] * math.sin(a), z))
n = len(tail_rings)
def in_wedge(a):
    fr = abs((a + math.pi / 2 + math.pi) % (2 * math.pi) - math.pi)   # distance from the front (-Y)
    bk = abs((a - math.pi / 2 + math.pi) % (2 * math.pi) - math.pi)   # distance from the back (+Y)
    return fr < math.radians(13) or bk < math.radians(17)
for i in range(n - 1):
    for k in range(nb):
        if in_wedge(ang(k, nb) + math.pi / nb): continue
        a_ = i * nb + k; b_ = i * nb + (k + 1) % nb
        tf.append((a_, b_, b_ + nb, a_ + nb))
parts.append(("coat_tails", tv, tf, 'COAT', True, None))

# ---------------- cape: a curved panel hanging down the back ----------------
cape = []
tr = {round(r[0], 4): r for r in torso_rings}
zs = sorted(tr.keys(), reverse=True)
for z in zs:
    if z < -0.14 or z > 0.445: continue
    _, cx, cy, r = tr[z]
    extra = 0.010 + 0.015 * smoothstep(0.445, 0.38, z) + 0.03 * smoothstep(0.38, -0.14, z)
    half = 50 + 18 * smoothstep(0.445, 0.20, z)              # half-span in degrees: trapezoid, narrow at the top
    ring = []
    for j in range(22):
        a = math.radians(90 - half + 2 * half * j / 21)       # +Y (back) is 90 deg
        k = int((a + math.pi) / (2 * math.pi) * NBIN) % NBIN
        rr = r[k] + extra
        ring.append(Vector((cx + rr * math.cos(a), cy + rr * math.sin(a), z)))
    cape.append(ring)
loft("cape", None, 22, 'CAPE', partial=cape)

# ---------------- neck + stump (Neck-weighted, must not collapse when Head is hidden) ----------------
nk = [(z, 0.0, neck_cy, neck_r + 0.001) for z in np.arange(0.42, 0.565 + 1e-6, 0.012)]
loft("neck", nk, NBIN, 'NECK', weights={'Neck': 1.0})
cap_r = neck_r + 0.001
cv = [(0.0, neck_cy, 0.565)] + [(cap_r[k] * math.cos(ang(k)), neck_cy + cap_r[k] * math.sin(ang(k)), 0.565) for k in range(NBIN)]
cf = [(0, 1 + k, 1 + (k + 1) % NBIN) for k in range(NBIN)]
parts.append(("stump", cv, cf, 'STUMP', False, {'Neck': 1.0}))

# ---------------- pumpkin ----------------
PC = Vector((0.0, PC_Y, PC_Z))                          # PC_Y, PC_Z, PR are set above the torso section (the collar uses them)
def pumpkin_mesh():
    bmp = bmesh.new()
    bmesh.ops.create_uvsphere(bmp, u_segments=48, v_segments=24, radius=1.0)
    for v in bmp.verts:
        x, y, z = v.co; th = math.atan2(y, x)
        groove = (0.5 + 0.5 * math.cos(10 * th)) ** 3
        rs = 1 - 0.09 * groove * (1 - z * z) ** 0.5
        zz = z * (0.82 if z > 0 else 0.78) - 0.07 * math.exp(-((x * x + y * y) / 0.07)) * (1 if z > 0 else 0)
        v.co = Vector((x * rs, y * rs, zz))
    bmp.faces.ensure_lookup_table()
    sphere_faces = list(bmp.faces)
    # stem
    top = max(v.co.z for v in bmp.verts if math.hypot(v.co.x, v.co.y) < 0.05)
    stem = bmesh.ops.create_cone(bmp, cap_ends=True, cap_tris=False, segments=10, radius1=0.17, radius2=0.11, depth=0.36)
    sv = stem['verts']
    for v in sv:
        v.co = Vector((v.co.x + 0.12 * (v.co.z + 0.18) / 0.36, v.co.y, v.co.z + 0.18 + top - 0.02))
    bmp.normal_update()
    return bmp, set(f.index for f in sphere_faces)
bmp, sphere_fidx = pumpkin_mesh()
pv = [tuple(Vector(v.co) * PR) for v in bmp.verts]
pf = [tuple(v.index for v in f.verts) for f in bmp.faces]
is_stem = [f.index not in sphere_fidx for f in bmp.faces]
bmp.free()
parts.append(("pumpkin", [tuple(Vector(p) + PC) for p in pv], pf, 'PUMPKIN', True, {'Head': 1.0}))

# ---------------- buttons (brass) on the coat front ----------------
def make_tmp(verts, faces):
    m = bpy.data.meshes.new("tmp"); m.from_pydata(verts, [], faces); m.update()
    o = bpy.data.objects.new("tmp", m); bpy.context.scene.collection.objects.link(o); return o
tmp = make_tmp(parts[0][1], parts[0][2]); bvh = BVHTree.FromObject(tmp, bpy.context.evaluated_depsgraph_get())
def surf(c, a, z):
    d = Vector((math.cos(a), math.sin(a), 0)); o = Vector((c[0], c[1], z)) + d * 0.005
    hit = bvh.ray_cast(o, d, 0.6)
    return (hit[0] if hit[0] is not None else o + d * 0.1), d
def box(name, centre, d, w, hgt, depth, kind):
    up = Vector((0, 0, 1)); t = up.cross(d).normalized(); Vb = []
    for dz in (-hgt / 2, hgt / 2):
        for dt in (-w / 2, w / 2):
            for dd in (-0.002, depth): Vb.append(tuple(centre + t * dt + d * dd + up * dz))
    F = [(0, 1, 3, 2), (4, 6, 7, 5), (0, 4, 5, 1), (2, 3, 7, 6), (0, 2, 6, 4), (1, 5, 7, 3)]
    parts.append((name, Vb, F, kind, False, None))
for z in (0.07, 0.16, 0.25, 0.34):
    for sgn in (-1, 1):
        cy = tr[min(tr, key=lambda k: abs(k - z))][2]
        p, d = surf((0, cy), -math.pi / 2 + sgn * math.radians(15), z)
        box("button", p, d, 0.026, 0.026, 0.009, 'BRASS')
# waist belt over the coat + brass buckle
NBELT = 72; zr = (-0.046, -0.028, -0.008); Vb, Fb = [], []
cyb = tr[min(tr, key=lambda k: abs(k + 0.028))][2]
for k in range(NBELT):
    a = -math.pi + k / NBELT * 2 * math.pi
    for zi, z in enumerate((zr[0] - 0.001,) + zr + (zr[2] + 0.001,)):
        p, d = surf((0, cyb), a, z)
        Vb.append(tuple(p + d * (-0.002 if zi in (0, 4) else 0.007)))
for k in range(NBELT):
    k2 = (k + 1) % NBELT
    for zi in range(4): Fb.append((k * 5 + zi, k2 * 5 + zi, k2 * 5 + zi + 1, k * 5 + zi + 1))
parts.append(("belt", Vb, Fb, 'LEATHER', True, None))
p, d = surf((0, cyb), -math.pi / 2, -0.027)
box("buckle", p, d, 0.055, 0.046, 0.014, 'BRASS')
box("buckle_bar", p + d * 0.014, d, 0.040, 0.010, 0.005, 'LEATHER')
bpy.data.objects.remove(tmp)

# ---------------- texture atlas: free space + painted patches ----------------
imgs = {k: bpy.data.images['final_' + k] for k in ('color', 'normal', 'orm')}
arrs = {}
for k, img in imgs.items():
    a = np.empty(img.size[0] * img.size[1] * 4, np.float32); img.pixels.foreach_get(a); arrs[k] = a.reshape(img.size[1], img.size[0], 4)
em = bpy.data.images.new('final_emissive', 2048, 2048, alpha=False); arrs['emissive'] = np.zeros((2048, 2048, 4), np.float32); arrs['emissive'][:, :, 3] = 1
bm = bmesh.new(); bm.from_mesh(me.data); bm.verts.ensure_lookup_table(); uvl = bm.loops.layers.uv.active
G = 128; occ = np.zeros((G, G), bool)
for f in bm.faces:
    if any(v.index in remove for v in f.verts): continue
    us = [(l[uvl].uv.x * G, l[uvl].uv.y * G) for l in f.loops]
    for ux, uy in us: occ[min(G - 1, max(0, int(uy))), min(G - 1, max(0, int(ux)))] = True
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
o2 = occ.copy(); o2[1:, :] |= occ[:-1, :]; o2[:-1, :] |= occ[1:, :]; o2[:, 1:] |= occ[:, :-1]; o2[:, :-1] |= occ[:, 1:]; occ = o2
print("ATLAS free cells", int((~occ).sum()), "of", G * G)
def find_free(w, h):
    for y in range(G - h):
        for x in range(G - w):
            if not occ[y:y + h, x:x + w].any():
                occ[y:y + h, x:x + w] = True; return x, y
    raise SystemExit(f"no atlas space {w}x{h}")
rng = np.random.default_rng(11)
SPEC = {  # colour (sRGB), roughness, metallic, cells
    'COAT':   ((0.055, 0.052, 0.06), 0.93, 0.0, 8),
    'NECK':   ((0.05, 0.045, 0.045), 0.95, 0.0, 4),
    'STUMP':  ((0.10, 0.02, 0.01), 0.9, 0.0, 6),
    'BRASS':  ((0.62, 0.46, 0.20), 0.35, 1.0, 4),
    'STEM':   ((0.28, 0.30, 0.12), 0.8, 0.0, 4),
    'CAPE':   ((0.14, 0.02, 0.025), 0.92, 0.0, 6),
    'LEATHER':((0.03, 0.028, 0.028), 0.6, 0.0, 4),
}
patch = {}
def paint_rect(u0, v0, u1, v1, fn):
    """fn(uu, vv) -> (rgb, emissive_rgb, rough, metal) for arrays uu, vv in [0,1]; images may differ in size"""
    cache = {}
    def grid(k):
        H, W = arrs[k].shape[:2]
        X0, Y0, X1, Y1 = int(u0 * W), int(v0 * H), int(u1 * W), int(v1 * H)
        if (H, W) not in cache:
            yy, xx = np.mgrid[Y0:Y1, X0:X1]; uu = (xx + 0.5 - X0) / (X1 - X0); vv = (yy + 0.5 - Y0) / (Y1 - Y0)
            cache[(H, W)] = fn(uu, vv)
        return (X0, Y0, X1, Y1) + cache[(H, W)]
    X0, Y0, X1, Y1, col, emi, ro, mt = grid('color'); arrs['color'][Y0:Y1, X0:X1, :3] = col; arrs['color'][Y0:Y1, X0:X1, 3] = 1
    X0, Y0, X1, Y1, col, emi, ro, mt = grid('emissive'); arrs['emissive'][Y0:Y1, X0:X1, :3] = emi
    X0, Y0, X1, Y1, col, emi, ro, mt = grid('normal'); arrs['normal'][Y0:Y1, X0:X1] = (0.5, 0.5, 1.0, 1.0)
    X0, Y0, X1, Y1, col, emi, ro, mt = grid('orm'); arrs['orm'][Y0:Y1, X0:X1, 0] = 1; arrs['orm'][Y0:Y1, X0:X1, 1] = ro; arrs['orm'][Y0:Y1, X0:X1, 2] = mt; arrs['orm'][Y0:Y1, X0:X1, 3] = 1
for kind, (c, rough, metal, n) in SPEC.items():
    x, y = find_free(n + 2, n + 2); x += 1; y += 1
    u0, v0, u1, v1 = (x - 0.5) / G, (y - 0.5) / G, (x + n + 0.5) / G, (y + n + 0.5) / G
    patch[kind] = ((x + 0.3) / G, (y + 0.3) / G, (x + n - 0.3) / G, (y + n - 0.3) / G)
    def fn(uu, vv, c=c, rough=rough, metal=metal, kind=kind):
        sh = uu.shape; col = np.ones(sh + (3,)) * np.array(c)
        if kind in ('COAT', 'NECK', 'CAPE'): col += rng.normal(0, 0.004, sh + (1,))
        emi = np.zeros(sh + (3,))
        if kind == 'STUMP':   # ember cracks
            cr = (np.sin(uu * 37 + np.sin(vv * 23) * 3) * np.sin(vv * 41 + uu * 7) > 0.75).astype(float)
            col = col * (1 - cr[..., None]) + np.array((0.9, 0.25, 0.05)) * cr[..., None]; emi = np.array((1.0, 0.3, 0.05)) * cr[..., None]
        return np.clip(col, 0, 1), emi, np.full(sh, rough), np.full(sh, metal)
    paint_rect(u0, v0, u1, v1, fn)

# pumpkin equirect texture (u = angle, front at u=0.25; v = 1 top .. 0 bottom); painted for u in [0, 1.06] (seam margin)
def pumpkin_tex(uu, vv):
    u = uu % 1.0
    th = u * 2 * math.pi - math.pi
    groove = (0.5 + 0.5 * np.cos(10 * th)) ** 3
    shade = 1 - 0.38 * groove - 0.15 * (np.abs(vv - 0.5) * 2) ** 2.5
    base = np.array((0.95, 0.40, 0.05)) * shade[..., None] * (1 + rng.normal(0, 0.03, uu.shape + (1,)))
    # face
    def poly(pts):                                               # convex polygon, counter-clockwise in (u,v)
        m = np.ones(uu.shape, bool)
        for (ax, ay), (bx, by) in zip(pts, pts[1:] + pts[:1]):
            m &= ((bx - ax) * (vv - ay) - (by - ay) * (u - ax)) >= 0
        return m
    def eye(s):   # s=-1 left, +1 right: slanted 'angry' quad, apex to the outside
        P = [(0.25 + s * 0.025, 0.555), (0.25 + s * 0.108, 0.545), (0.25 + s * 0.088, 0.648), (0.25 + s * 0.037, 0.60)]
        return poly(P if s > 0 else P[::-1])
    eyes = eye(-1) | eye(1)
    nose = poly([(0.25 - 0.024, 0.468), (0.25 + 0.024, 0.468), (0.25, 0.525)])
    x = (u - 0.25) / 0.145                                           # -1..1 across the mouth
    smile = 0.045 * x * x
    teeth = np.abs((((x + 1) / 2 * 7 * 2) % 2) - 1)                 # triangle wave, 7 teeth
    lo = 0.34 + smile + 0.014 * teeth; hi = 0.44 + smile - 0.032 * teeth
    mouth = (np.abs(x) <= 1) & (vv >= lo) & (vv <= hi)
    face = eyes | nose | mouth
    # rim = dilate(face) - face
    rim = np.zeros_like(face)
    for dy in (-2, -1, 0, 1, 2):
        for dx in (-2, -1, 0, 1, 2):
            rim |= np.roll(np.roll(face, dy, 0), dx, 1)
    rim &= ~face
    col = base.copy()
    col[rim] = (0.35, 0.10, 0.01)
    col[face] = (1.0, 0.78, 0.22)
    emi = np.zeros(uu.shape + (3,)); emi[face] = (1.0, 0.55, 0.10)
    ro = np.full(uu.shape, 0.6); ro[face] = 0.95
    return np.clip(col, 0, 1), emi, ro, np.zeros(uu.shape)
def find_free_try(w, h):
    for y in range(G - h):
        for x in range(G - w):
            if not occ[y:y + h, x:x + w].any():
                occ[y:y + h, x:x + w] = True; return x, y
    return None
for PW, PH in ((64, 30), (56, 26), (48, 22), (40, 19), (34, 16)):
    xy = find_free_try(PW + 2, PH + 2)
    if xy: break
print("PUMPKIN RECT", PW, PH); x, y = xy; x += 1; y += 1
PU0, PV0, PU1, PV1 = (x - 0.5) / G, (y - 0.5) / G, (x + PW + 0.5) / G, (y + PH + 0.5) / G
patch['PUMPKIN'] = ((x + 0.2) / G, (y + 0.2) / G, (x + PW - 0.2) / G, (y + PH - 0.2) / G)
paint_rect(PU0, PV0, PU1, PV1, lambda uu, vv: pumpkin_tex(uu * (PU1 - PU0) / (patch['PUMPKIN'][2] - patch['PUMPKIN'][0]) * 1.06 - 0.03, vv))
for k, img in imgs.items():
    img.pixels.foreach_set(arrs[k].ravel()); img.update(); img.pack()
em.pixels.foreach_set(arrs['emissive'].ravel()); em.update(); em.pack()
print("PATCHES", {k: [round(t, 4) for t in v] for k, v in patch.items()})

# ---------------- build objects, UVs, weights ----------------
def make_obj(name, Vv, F, kind, smooth):
    m = bpy.data.meshes.new(name); m.from_pydata(Vv, [], F); m.update()
    o = bpy.data.objects.new(name, m); bpy.context.scene.collection.objects.link(o); o["kind"] = kind
    for p in m.polygons: p.use_smooth = smooth
    return o
new = []
for name, Vv, F, kind, smooth, wts in parts:
    o = make_obj(name, Vv, F, kind, smooth); o["wts"] = wts or {}
    m = o.data; uv = m.uv_layers.new(name="UVMap")
    if kind == 'PUMPKIN':
        u0, v0, u1, v1 = patch['PUMPKIN']; s0, t0, s1, t1 = patch['STEM']
        for poly in m.polygons:
            if is_stem[poly.index]:
                for li in poly.loop_indices: uv.data[li].uv = ((s0 + s1) / 2, (t0 + t1) / 2)
                continue
            us = []
            for li in poly.loop_indices:
                co = m.vertices[m.loops[li].vertex_index].co - PC
                th = math.atan2(co.y, co.x); r = co.length
                us.append(((th + math.pi) / (2 * math.pi), 1 - math.acos(max(-1, min(1, co.z / r))) / math.pi))
            if max(a for a, b in us) - min(a for a, b in us) > 0.5: us = [(a + 1 if a < 0.5 else a, b) for a, b in us]
            for li, (a, b) in zip(poly.loop_indices, us): uv.data[li].uv = (u0 + (u1 - u0) * (a + 0.03) / 1.06, v0 + (v1 - v0) * b)
    else:
        u0, v0, u1, v1 = patch[kind]
        pu_ = u0 + (u1 - u0) * 0.15; pv_ = v0 + (v1 - v0) * 0.15; su = (u1 - u0) * 0.7; sv = (v1 - v0) * 0.7
        for poly in m.polygons:
            for li in poly.loop_indices:
                co = m.vertices[m.loops[li].vertex_index].co
                uu = min(1, max(0, (co.x + 0.5 + 0.5 * co.y) / 1.2)); vv = min(1, max(0, (co.z + 0.6) / 1.4))
                uv.data[li].uv = (pu_ + su * uu, pv_ + sv * vv)
    m.materials.append(me.data.materials[0]); new.append(o)

# weight source: the original minus head/eyes (so no Head weight can leak into the coat)
src = me.copy(); src.data = me.data.copy(); src.name = "wsrc"; bpy.context.scene.collection.objects.link(src); src.modifiers.clear()
sbm = bmesh.new(); sbm.from_mesh(src.data); sbm.verts.ensure_lookup_table()
bmesh.ops.delete(sbm, geom=[v for v in sbm.verts if D[v.index] in HEADB], context='VERTS'); sbm.to_mesh(src.data); sbm.free()
for o in new:
    bpy.ops.object.select_all(action='DESELECT'); o.select_set(True); bpy.context.view_layer.objects.active = o
    wts = dict(o["wts"])
    if wts:
        for bn, w in wts.items():
            vg = o.vertex_groups.new(name=bn); vg.add(list(range(len(o.data.vertices))), w, 'REPLACE')
        continue
    md = o.modifiers.new("dt", 'DATA_TRANSFER'); md.object = src; md.use_vert_data = True
    md.data_types_verts = {'VGROUP_WEIGHTS'}; md.vert_mapping = 'POLYINTERP_NEAREST'
    md.layers_vgroup_select_src = 'ALL'; md.layers_vgroup_select_dst = 'NAME'
    bpy.ops.object.datalayout_transfer(modifier="dt"); bpy.ops.object.modifier_apply(modifier="dt")
    if o.name == "coat_torso":          # collar: Neck only; shoulder top: blend to Neck
        gN = o.vertex_groups.get('Neck') or o.vertex_groups.new(name='Neck')
        for v in o.data.vertices:
            z = v.co.z
            if z > 0.49:
                for g in o.vertex_groups: g.remove([v.index])
                gN.add([v.index], 1.0, 'REPLACE')
    bpy.ops.object.vertex_group_limit_total(limit=4); bpy.ops.object.vertex_group_normalize_all(lock_active=False)
    bad = sum(1 for v in o.data.vertices if not v.groups or sum(g.weight for g in v.groups) < 0.99)
    if bad: print("UNWEIGHTED", o.name, bad)
bpy.data.objects.remove(src)

# ---------------- static pumpkin head (own file, own textures) ----------------
st = make_obj("Pumpkin_Static", pv, pf, 'PUMPKIN', True)
mS = st.data; uvS = mS.uv_layers.new(name="UVMap")
for poly in mS.polygons:
    if is_stem[poly.index]:
        for li in poly.loop_indices: uvS.data[li].uv = (0.02, 0.98)
        continue
    us = []
    for li in poly.loop_indices:
        co = mS.vertices[mS.loops[li].vertex_index].co; th = math.atan2(co.y, co.x); r = co.length
        us.append(((th + math.pi) / (2 * math.pi), 1 - math.acos(max(-1, min(1, co.z / r))) / math.pi))
    if max(a for a, b in us) - min(a for a, b in us) > 0.5: us = [(a + 1 if a < 0.5 else a, b) for a, b in us]
    for li, (a, b) in zip(poly.loop_indices, us): uvS.data[li].uv = ((a + 0.03) / 1.06, b * 0.94 + 0.03)
HW, HH = 1024, 512
yy, xx = np.mgrid[0:HH, 0:HW]; uu = (xx + 0.5) / HW * 1.06 - 0.03; vv = ((yy + 0.5) / HH - 0.03) / 0.94
col, emi, ro, mt = pumpkin_tex(uu, np.clip(vv, 0, 1))
stem_mask = (yy > HH * 0.96) & (xx < HW * 0.04); col[stem_mask] = SPEC['STEM'][0]; ro[stem_mask] = 0.8; emi[stem_mask] = 0
def mkimg(name, rgb, alpha1=True):
    im = bpy.data.images.new(name, HW, HH, alpha=False); a = np.ones((HH, HW, 4), np.float32); a[:, :, :3] = rgb
    im.pixels.foreach_set(a.ravel()); im.update(); im.pack(); return im
imC = mkimg('pumpkin_color', col); imE = mkimg('pumpkin_emissive', emi)
orm = np.stack([np.ones_like(ro), ro, mt], -1); imO = mkimg('pumpkin_orm', orm); imO.colorspace_settings.name = 'Non-Color'
matS = bpy.data.materials.new('Pumpkin'); matS.use_nodes = True; nt = matS.node_tree; bsdf = nt.nodes['Principled BSDF']
def texnode(im, noncolor=False):
    n = nt.nodes.new('ShaderNodeTexImage'); n.image = im
    if noncolor: im.colorspace_settings.name = 'Non-Color'
    return n
tC = texnode(imC); nt.links.new(tC.outputs['Color'], bsdf.inputs['Base Color'])
tE = texnode(imE); nt.links.new(tE.outputs['Color'], bsdf.inputs['Emission Color']); bsdf.inputs['Emission Strength'].default_value = 1.0
tO = texnode(imO, True); sep = nt.nodes.new('ShaderNodeSeparateColor'); nt.links.new(tO.outputs['Color'], sep.inputs['Color'])
nt.links.new(sep.outputs['Green'], bsdf.inputs['Roughness']); nt.links.new(sep.outputs['Blue'], bsdf.inputs['Metallic'])
mS.materials.append(matS)
# emissive on the body material too
matB = me.data.materials[0]; ntB = matB.node_tree; bB = ntB.nodes['Principled BSDF']
tEB = ntB.nodes.new('ShaderNodeTexImage'); tEB.image = em; ntB.links.new(tEB.outputs['Color'], bB.inputs['Emission Color']); bB.inputs['Emission Strength'].default_value = 1.0

# ---------------- delete the old upper body, join, DH bones, export ----------------
bpy.ops.object.select_all(action='DESELECT'); bpy.context.view_layer.objects.active = me; me.select_set(True)
bpy.ops.object.mode_set(mode='EDIT'); bpy.ops.mesh.select_mode(type='VERT'); bpy.ops.mesh.select_all(action='DESELECT'); bpy.ops.object.mode_set(mode='OBJECT')
for v in me.data.vertices: v.select = v.index in remove
before = len(me.data.vertices)
bpy.ops.object.mode_set(mode='EDIT'); bpy.ops.mesh.delete(type='VERT'); bpy.ops.object.mode_set(mode='OBJECT')
print("DELETED", before - len(me.data.vertices), "expected", len(remove))
for o in new: o.select_set(True)
me.select_set(True); bpy.context.view_layer.objects.active = me; bpy.ops.object.join()
while len(me.data.materials) > 1: me.data.materials.pop()
for p in me.data.polygons: p.material_index = 0
print("FINAL tris", sum(len(p.vertices) - 2 for p in me.data.polygons))

bpy.ops.object.select_all(action='DESELECT'); arm.select_set(True); bpy.context.view_layer.objects.active = arm
bpy.ops.object.mode_set(mode='EDIT')
eb = arm.data.edit_bones; headb = eb['Head']
for name, off in (('DH_C', Vector((0, 0, 0))), ('DH_F', Vector((0, -0.10, 0))), ('DH_U', Vector((0, 0, 0.10)))):
    b = eb.new(name); b.head = PC + off; b.tail = b.head + Vector((0, 0, 0.02)); b.parent = headb; b.use_connect = False; b.use_deform = False
bpy.ops.object.mode_set(mode='OBJECT')

bpy.ops.object.select_all(action='DESELECT'); me.select_set(True); arm.select_set(True)
bpy.ops.export_scene.gltf(filepath=OUT + r"\horseman.glb", export_format='GLB', use_selection=True, export_animations=False)
bpy.ops.object.select_all(action='DESELECT'); st.select_set(True)
bpy.ops.export_scene.gltf(filepath=OUT + r"\horseman_head.glb", export_format='GLB', use_selection=True, export_animations=False)
print("EXPORTED", OUT)
