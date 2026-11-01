"""Animatronic Santa (MIDTOWN, the Christmas stage) from skullbuck's rigged body, built the way scripts/horseman_build.py
built the Headless Horseman: everything above the hips is deleted and replaced by procedural clothes lofted from the
body's radius profiles, weighted with DATA_TRANSFER from the original, painted into skullbuck's texture atlas.
The story: the department store's window-display Santa has walked out through the glass to play the set.
Input : breeches.glb (skullbuck with plain pants, from scripts/skullbuck_cargo_pants.py 'plain'), kept at BREECHES below
Output: <out>/santa.glb       the skin: red velvet coat torn open at the left side over metal ribs, white fur trim, black
                              belt + gold buckle, red trousers, bare metal forearms (elbow servo, pistons), black gloves;
                              the head skinned 100 % to Head with DH_C/DH_F/DH_U marker bones for the detachable-head hook
                              (hook/head.cpp), and a Neck-weighted stump (rubber bellows, coil spring, cut wires, neck post)
                              that sits inside the head while it is on
        <out>/santa_head.glb  the same head as a STATIC mesh, origin at DH_C, facing glTF +Z (+Y up), its own textures
Run   : blender -b --factory-startup --python scripts/santa_build.py -- <OUTDIR>
Blender axes below: the character faces -Y, its left is +X, up is +Z; the Hips bone is at the origin.
"""
import sys, os, math
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import avatar_common
BREECHES = r"C:\Users\Chris\TribeUE\TribeXR\Scripts\Blender\christmas\santa\breeches.glb"
avatar_common.SRC = BREECHES
from avatar_common import *
import numpy as np
from mathutils import Vector, Matrix, noise
from mathutils.bvhtree import BVHTree

OUT = sys.argv[sys.argv.index('--') + 1]
os.makedirs(OUT, exist_ok=True)
me, arm = load()
assert me.matrix_world == Matrix.Identity(4) and arm.matrix_world == Matrix.Identity(4)
gi = {g.index: g.name for g in me.vertex_groups}
B = lambda n: Vector(arm.data.bones[n].head_local)
for n in ('Hips', 'Spine2', 'Neck', 'Head', 'LeftEye', 'LeftArm', 'LeftForeArm', 'LeftHand'): print("BONE", n, [round(x, 3) for x in B(n)])

# ---------------- classify vertices by dominant bone (as horseman_build.py) ----------------
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
belt_idx, pants_idx = set(), set()
for comp in parts_of(bm0):
    zs = [bm0.verts[i].co.z for i in comp]
    if min(zs) > -0.06 and max(zs) < 0.01 and len(comp) < 1500 and not any(ishand(D[i]) for i in comp): belt_idx |= set(comp)   # the breeches' belt + loops (their tops reach z 0.003)
    elif len(comp) > 2000 and sum(1 for i in comp if 'Leg' in D[i] or D[i] == 'Hips') > 0.9 * len(comp): pants_idx = set(comp)   # cargo.py's plain shell
remove |= belt_idx
bm0.free()
glove_idx = {i for i, d in enumerate(D) if i not in remove and ishand(d)}
print("REMOVE", len(remove), "of", len(D), "| pants shell", len(pants_idx), "| gloves", len(glove_idx))
torso_src = np.array([i for i, d in enumerate(D) if d not in ARMB and not ishand(d) and d not in HEADB and i not in belt_idx and
                      -0.14 <= V[i, 2] <= 0.57 and not ('Shoulder' in d and V[i, 2] > 0.43) and math.hypot(V[i, 0], V[i, 1]) < 0.30])
pants_src = np.array([i for i, d in enumerate(D) if ('UpLeg' in d or d == 'Hips') and -0.55 < V[i, 2] < 0.0 and i not in belt_idx])

# ---------------- radius profiles (as horseman_build.py) ----------------
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
def phi_front(a): return abs((a + math.pi / 2 + math.pi) % (2 * math.pi) - math.pi)      # 0 at the front (-Y), pi at the back
def smoothstep(a, b, x):
    t = min(1, max(0, (x - a) / (b - a))); return t * t * (3 - 2 * t)
def smooth_rings(rings, n=3):
    for _ in range(n):
        rs = [r[3].copy() for r in rings]
        for k in range(1, len(rings) - 1): rings[k] = (rings[k][0], rings[k][1], rings[k][2], (rs[k - 1] + 2 * rs[k] + rs[k + 1]) / 4)
    return rings
_A = np.array([ang(k) for k in range(NBIN)])
_PHI = np.array([phi_front(a) for a in _A])

# ---------------- geometry helpers ----------------
parts = []    # skinned parts, world coordinates
hparts = []   # head parts, head-local coordinates (origin DH_C); copied into `parts` (+C, Head 100 %) and the static head
def add(name, v, f, kinds, smooth=True, w=None, recalc=True, disc=None, wblend=None, wkeep=None, noleg=None, dest=None):
    if isinstance(kinds, str): kinds = [kinds] * len(f)
    assert len(kinds) == len(f), name
    (parts if dest is None else dest).append(dict(name=name, v=[Vector(p) for p in v], f=[tuple(x) for x in f], k=list(kinds),
                                                  smooth=smooth, w=w, recalc=recalc, disc=disc, wblend=wblend, wkeep=wkeep, noleg=noleg))
def hadd(name, v, f, kinds, smooth=True, disc=None, recalc=True):
    add(name, v, f, kinds, smooth=smooth, w={'Head': 1.0}, recalc=recalc, disc=disc, dest=hparts)
def compact(verts, faces):
    used = sorted({i for f in faces for i in f}); remap = {o: n for n, o in enumerate(used)}
    return [verts[i] for i in used], [tuple(remap[i] for i in f) for f in faces]
def uvsphere(nu, nv):
    bmx = bmesh.new(); bmesh.ops.create_uvsphere(bmx, u_segments=nu, v_segments=nv, radius=1.0); bmx.verts.ensure_lookup_table()
    vs = [Vector(v.co) for v in bmx.verts]; fs = [tuple(v.index for v in f.verts) for f in bmx.faces]; bmx.free(); return vs, fs
def ring_loft(rows, cap_end=False):
    """closed rings of equal length (first -> last); CCW rings going up/along give outward normals"""
    n, m = len(rows), len(rows[0]); verts = [p for row in rows for p in row]; faces = []
    for i in range(n - 1):
        for j in range(m):
            j2 = (j + 1) % m; faces.append((i * m + j, i * m + j2, (i + 1) * m + j2, (i + 1) * m + j))
    if cap_end: faces.append(tuple(range((n - 1) * m, n * m)))
    return verts, faces
def open_loft(rows):
    """open rows of equal length (bottom -> top), each running CCW seen from above -> outward normals"""
    n, m = len(rows), len(rows[0]); verts = [p for row in rows for p in row]; faces = []
    for i in range(n - 1):
        for j in range(m - 1):
            a_ = i * m + j; faces.append((a_, a_ + 1, a_ + 1 + m, a_ + m))
    return verts, faces
def sweep(path, prof, normals=None, closed=False, caps=True, scale=None, lump=0.0, lump_f=60.0, seed=0.0, lift=0.0):
    """Extrude the 2D profile prof [(b, n), ...] along path. Frame: n = the given surface normal (else parallel-transported),
    b = tangent x n. scale: per-point factor on the profile; lump: noise on it (fur)."""
    n = len(path); T = []
    for i in range(n):
        t = (path[(i + 1) % n] - path[i - 1]) if closed else (path[min(n - 1, i + 1)] - path[max(0, i - 1)])
        T.append(t.normalized())
    if normals is None:
        up = Vector((0, 0, 1)) if abs(T[0].z) < 0.9 else Vector((1, 0, 0))
        nn = (up - T[0] * up.dot(T[0])).normalized(); N = []
        for i in range(n):
            if i: nn = T[i - 1].rotation_difference(T[i]) @ nn
            nn = (nn - T[i] * nn.dot(T[i])).normalized(); N.append(nn)
    else:
        N = [(Vector(q) - T[i] * Vector(q).dot(T[i])).normalized() for i, q in enumerate(normals)]
    verts, m = [], len(prof)
    for i in range(n):
        bb = T[i].cross(N[i]).normalized(); c = path[i] + N[i] * lift; s = 1.0 if scale is None else scale[i]
        for j, (pb, pn) in enumerate(prof):
            l = 1.0 + (lump * noise.noise(Vector((path[i].x * lump_f + j * 1.7, path[i].y * lump_f + seed, path[i].z * lump_f))) if lump else 0.0)
            verts.append(c + (bb * pb + N[i] * pn) * (s * l))
    faces = []
    for i in range(n if closed else n - 1):
        i2 = (i + 1) % n
        for j in range(m):
            j2 = (j + 1) % m; faces.append((i * m + j, i * m + j2, i2 * m + j2, i2 * m + j))
    if caps and not closed:
        faces.append(tuple(range(m))[::-1]); faces.append(tuple(range((n - 1) * m, n * m)))
    return verts, faces
def ellipse(hw, ht, k=8): return [(hw * math.cos(2 * math.pi * j / k), ht * math.sin(2 * math.pi * j / k)) for j in range(k)]
def rect(hw, ht): return [(-hw, -ht), (hw, -ht), (hw, ht), (-hw, ht)]
def cyl(p0, p1, r, nseg=12, caps=True):
    a = (p1 - p0).normalized(); u = a.orthogonal().normalized(); v = a.cross(u); verts = []
    for p in (p0, p1):
        for j in range(nseg):
            th = 2 * math.pi * j / nseg; verts.append(p + (u * math.cos(th) + v * math.sin(th)) * r)
    faces = [(j, (j + 1) % nseg, nseg + (j + 1) % nseg, nseg + j) for j in range(nseg)]
    if caps: faces += [tuple(range(nseg))[::-1], tuple(range(nseg, 2 * nseg))]
    return verts, faces
def annulus(c0, c1, r_in, r_out, nseg):
    """a ring with a rectangular cross-section (closed), axis c0 -> c1"""
    ax = (c1 - c0).normalized(); u = ax.orthogonal().normalized(); v = ax.cross(u); verts = []
    for c, r in ((c0, r_out), (c1, r_out), (c1, r_in), (c0, r_in)):
        for j in range(nseg):
            th = 2 * math.pi * j / nseg; verts.append(c + (u * math.cos(th) + v * math.sin(th)) * r)
    faces = []
    for i in range(4):
        i2 = (i + 1) % 4
        for j in range(nseg):
            j2 = (j + 1) % nseg; faces.append((i * nseg + j, i * nseg + j2, i2 * nseg + j2, i2 * nseg + j))
    return verts, faces
def lathe(c, axis, prof, nseg, kinds):
    """revolve prof [(r, h), ...] around axis through c (h along the axis); kinds[i] for the band prof[i] -> prof[i+1]"""
    axis = axis.normalized(); u = axis.orthogonal().normalized(); v = axis.cross(u); verts, idx = [], []
    for r, h in prof:
        if r < 1e-7: idx.append([len(verts)] * nseg); verts.append(c + axis * h)
        else:
            row = []
            for j in range(nseg):
                th = 2 * math.pi * j / nseg; row.append(len(verts)); verts.append(c + axis * h + (u * math.cos(th) + v * math.sin(th)) * r)
            idx.append(row)
    faces, fk = [], []
    for i in range(len(prof) - 1):
        for j in range(nseg):
            j2 = (j + 1) % nseg; f2 = []
            for q in (idx[i][j], idx[i][j2], idx[i + 1][j2], idx[i + 1][j]):
                if q not in f2: f2.append(q)
            if len(f2) >= 3: faces.append(tuple(f2)); fk.append(kinds[i])
    if prof[0][0] > 1e-7: faces.append(tuple(idx[0])[::-1]); fk.append(kinds[0])
    return verts, faces, fk, (u, v)
def box(centre, d, w, hgt, depth, up=Vector((0, 0, 1))):
    t = up.cross(d).normalized(); Vb = []
    for dz in (-hgt / 2, hgt / 2):
        for dt in (-w / 2, w / 2):
            for dd in (-0.002, depth): Vb.append(centre + t * dt + d * dd + up * dz)
    return Vb, [(0, 1, 3, 2), (4, 6, 7, 5), (0, 4, 5, 1), (2, 3, 7, 6), (0, 2, 6, 4), (1, 5, 7, 3)]
def lumpy_ball(c, r, nu, nv, amp, f, seed, scl=(1, 1, 1)):
    sv_, sf_ = uvsphere(nu, nv)
    return [c + Vector((p.x * scl[0], p.y * scl[1], p.z * scl[2])) * r * (1 + amp * noise.noise(p * f + Vector((seed, 0, 0)))) for p in sv_], sf_
def dense(ctrl, n):
    """Catmull-Rom through ctrl (list of Vector), n points"""
    P = [ctrl[0]] + list(ctrl) + [ctrl[-1]]; out = []
    for i in range(n):
        s = i / (n - 1) * (len(ctrl) - 1); k = min(int(s), len(ctrl) - 2); t = s - k
        p0, p1, p2, p3 = P[k], P[k + 1], P[k + 2], P[k + 3]
        out.append(0.5 * ((2 * p1) + (-p0 + p2) * t + (2 * p0 - 5 * p1 + 4 * p2 - p3) * t * t + (-p0 + 3 * p1 - 3 * p2 + p3) * t * t * t))
    return out

# ---------------- coat torso: one loft from below the belt to the neckline, with a belly ----------------
T_ = V[torso_src]
Z_HEM, Z_TOP = -0.075, 0.495
NECKLINE_R = 0.074                                   # the coat's neck opening (the bellows is r <= 0.057)
BELLY, BELLY_Z, BELLY_W = 0.038, 0.12, 0.13          # a department-store Santa's belly, front only
NA, NH_ = B('Neck'), B('Head')
def neck_c(z):                                       # the Neck bone's line at height z
    t = (z - NA.z) / (NH_.z - NA.z); p = NA.lerp(NH_, t); p.z = z; return p
rings, last = [], None
for z in np.arange(Z_HEM, Z_TOP + 1e-6, 0.019):
    s = T_[np.abs(T_[:, 2] - z) < 0.012]
    if len(s) >= 10: cy = (s[:, 1].min() + s[:, 1].max()) / 2; last = (cy, profile(s, 0.0, cy, k=9, sm=4) + 0.012)
    cy, r = last
    w = smoothstep(0.42, Z_TOP, z)                   # shoulder slope -> neckline
    r = r * (1 - w) + NECKLINE_R * w; cy = cy * (1 - w) + neck_c(z).y * w
    r = r + BELLY * math.exp(-((z - BELLY_Z) / BELLY_W) ** 2) * np.maximum(0.0, np.cos(_PHI)) ** 1.5
    rings.append((float(z), 0.0, cy, r))
RZ_ = np.array([r[0] for r in rings]); RR_ = np.array([r[3] for r in rings])
FRONT_W = np.clip((np.cos(_PHI) - 0.17) / 0.5, 0, 1)          # 1 across the front, 0 beyond ~80 deg
for i in range(len(rings)):                       # a barrel front: fill the dip between skullbuck's chest and the belly
    if RZ_[i] > 0.36: continue
    mx = RR_[(np.abs(RZ_ - RZ_[i]) <= 0.07) & (RZ_ <= 0.40)].max(axis=0)
    rings[i] = (rings[i][0], rings[i][1], rings[i][2], RR_[i] * (1 - FRONT_W) + np.maximum(RR_[i], mx) * FRONT_W)
torso_rings = smooth_rings(rings, 10)
TZ = np.array([r[0] for r in torso_rings]); TCY = np.array([r[2] for r in torso_rings]); TRR = np.array([r[3] for r in torso_rings])
def coat_r(a, z):
    """the torso loft's radius and centre y at azimuth a (from +X, CCW) and height z (bilinear in rings and bins)"""
    z = min(max(z, TZ[0]), TZ[-1]); i = min(len(TZ) - 2, max(0, int(np.searchsorted(TZ, z)) - 1)); t = (z - TZ[i]) / (TZ[i + 1] - TZ[i])
    fk = ((a + math.pi) / (2 * math.pi) * NBIN - 0.5) % NBIN; k0 = int(math.floor(fk)) % NBIN; k1 = (k0 + 1) % NBIN; s = fk - math.floor(fk)
    r0 = TRR[i, k0] * (1 - s) + TRR[i, k1] * s; r1 = TRR[i + 1, k0] * (1 - s) + TRR[i + 1, k1] * s
    return r0 * (1 - t) + r1 * t, TCY[i] * (1 - t) + TCY[i + 1] * t
def coat_pt(a, z, dr=0.0):
    r, cy = coat_r(a, z); return Vector(((r + dr) * math.cos(a), cy + (r + dr) * math.sin(a), z))
def coat_n(a, z):
    e = 1e-3; return (coat_pt(a + e, z) - coat_pt(a - e, z)).cross(coat_pt(a, z + e) - coat_pt(a, z - e)).normalized()
print("TORSO rings", len(torso_rings), "z", round(TZ[0], 3), "..", round(TZ[-1], 3), "| front r at belly", round(coat_r(-math.pi / 2, BELLY_Z)[0], 3))

# the tear: a slanted rip in the coat's front-left (between the fur placket and the left arm) over a dark cavity + ribs.
# Faces whose centre is inside the ragged outline are removed, then the rim verts are snapped onto the outline, so the
# edge follows the rip instead of the grid's staircase.
TEAR_A, TEAR_Z = math.radians(-44), 0.255            # centre: azimuth from +X (the character's left), height
TEAR_U, TEAR_V, TEAR_ROT = 0.058, 0.088, math.radians(24)   # semi-axes across / along the rip (m) and its slant
R_T = coat_r(TEAR_A, TEAR_Z)[0]
def tear_e(a, z):
    da = ((a - TEAR_A + math.pi) % (2 * math.pi) - math.pi) * R_T; dz = z - TEAR_Z; c, s_ = math.cos(TEAR_ROT), math.sin(TEAR_ROT)
    return ((da * c + dz * s_) / TEAR_U) ** 2 + ((-da * s_ + dz * c) / TEAR_V) ** 2
def tear_lvl(a, z):                                  # the outline: a slow wobble plus sharper teeth
    return 1 + 0.30 * noise.noise(Vector((a * 4.0, z * 30.0, 3.7))) + 0.16 * noise.noise(Vector((a * 14.0, z * 95.0, 8.1)))
TEAR_DA = math.hypot(TEAR_U * math.cos(TEAR_ROT), TEAR_V * math.sin(TEAR_ROT)) / R_T      # the rip's half-width as an angle
tv = []
for z, cx, cy, r in torso_rings:
    for k in range(NBIN): tv.append(Vector((cx + r[k] * math.cos(ang(k)), cy + r[k] * math.sin(ang(k)), z)))
nR = len(torso_rings); tq = []
for i in range(nR - 1):
    for k in range(NBIN):
        a_ = i * NBIN + k; b_ = i * NBIN + (k + 1) % NBIN; tq.append((a_, b_, b_ + NBIN, a_ + NBIN))
def fcentre(i, k): return ang(k) + math.pi / NBIN, (TZ[i] + TZ[i + 1]) / 2
hole = {(i, k) for i in range(nR - 1) for k in range(NBIN) if tear_e(*fcentre(i, k)) < tear_lvl(*fcentre(i, k))}
for _ in range(2):                                   # no one-face islands or pinholes in the ragged rim
    for i in range(nR - 1):
        for k in range(NBIN):
            nb_ = [(i + di, (k + dk) % NBIN) for di, dk in ((1, 0), (-1, 0), (0, 1), (0, -1)) if 0 <= i + di < nR - 1]
            nh = sum(1 for q in nb_ if q in hole)
            if (i, k) not in hole and nh >= 3: hole.add((i, k))
            elif (i, k) in hole and nh <= 1: hole.discard((i, k))
hv = {j for (i, k) in hole for j in tq[i * NBIN + k]}
coat_f, coat_k = [], []
for i in range(nR - 1):
    for k in range(NBIN):
        if (i, k) in hole: continue
        edge = any((i + di, (k + dk) % NBIN) in hole for di, dk in ((1, 0), (-1, 0), (0, 1), (0, -1)))
        coat_f.append(tq[i * NBIN + k]); coat_k.append('TORN' if edge else 'COAT')
rim = hv & {j for f in coat_f for j in f}
coat_v = [Vector(p) for p in tv]; moved = []
for j in rim:                                        # snap onto the outline (along the line from the rip's centre), then fray
    i, k = divmod(j, NBIN); a0, z0 = ang(k), TZ[i]; da0 = (a0 - TEAR_A + math.pi) % (2 * math.pi) - math.pi
    f_ = lambda t: tear_e(TEAR_A + da0 * t, TEAR_Z + (z0 - TEAR_Z) * t) - tear_lvl(TEAR_A + da0 * t, TEAR_Z + (z0 - TEAR_Z) * t)
    lo_, hi_ = 0.55, 1.6
    if f_(lo_) < 0 < f_(hi_):
        for _ in range(30):
            m_ = (lo_ + hi_) / 2
            if f_(m_) < 0: lo_ = m_
            else: hi_ = m_
        t = (lo_ + hi_) / 2; dist = math.hypot(da0 * R_T, z0 - TEAR_Z)
        t = 1 + max(-1, min(1, (t - 1) * dist / 0.014)) * 0.014 / dist          # at most 1.4 cm
        a1, z1 = TEAR_A + da0 * t, TEAR_Z + (z0 - TEAR_Z) * t; moved.append(abs(t - 1) * dist)
    else: a1, z1 = a0, z0
    coat_v[j] = coat_pt(a1, z1, 0.003 + 0.004 * abs(noise.noise(Vector((a1 * 30, z1 * 90, 1.3)))))
print("TEAR faces", len(hole), "rim verts", len(rim), "snapped", len(moved), "mean move %.1f mm" % (1000 * sum(moved) / max(1, len(moved))))
NOLEG_COAT, NOLEG_SKIRT = (-0.075, -0.035), (-0.10, -0.04)   # leg weights fade out toward the belt: the skirt hinges there
add("coat_torso", coat_v, coat_f, coat_k, recalc=False, noleg=NOLEG_COAT)
coat_bvh = BVHTree.FromPolygons(coat_v, coat_f)
# cavity: a dark shell 3 cm inside the coat, much bigger than the hole so no line of sight gets past it
cav_f = []
for i in range(nR - 1):
    for k in range(NBIN):
        if tear_e(*fcentre(i, k)) < 3.6: cav_f.append(tq[i * NBIN + k])
cav_v = [coat_pt(ang(j % NBIN), TZ[j // NBIN], -0.030) for j in range(len(tv))]
add("tear_cavity", *compact(cav_v, cav_f), 'CAVITY', recalc=False)
for zr_ in (0.203, 0.238, 0.273, 0.308):              # ribs
    add("tear_rib", *sweep([coat_pt(TEAR_A + s * 1.8 * TEAR_DA, zr_, -0.013) for s in np.linspace(-1, 1, 9)], ellipse(0.0055, 0.0055, 8)), 'STEEL')
for sa, rr_, kd in ((0.80, 0.0075, 'DARKSTEEL'), (-0.90, 0.0065, 'DARKSTEEL')):     # struts behind them
    add("tear_strut", *sweep([coat_pt(TEAR_A + sa * TEAR_DA, z, -0.021) for z in np.linspace(0.14, 0.37, 9)], ellipse(rr_, rr_, 8)), kd)
for ph, kd in ((0.0, 'WIRE_R'), (2.1, 'WIRE_Y')):    # two cables snaking down behind the ribs
    add("tear_cable", *sweep([coat_pt(TEAR_A + (0.45 * TEAR_DA if ph else -0.35 * TEAR_DA) + 0.18 * TEAR_DA * math.sin(z * 38 + ph), z, -0.025)
                              for z in np.linspace(0.13, 0.38, 16)], ellipse(0.0045, 0.0045, 6)), kd)

# ---------------- skirt: the coat below the belt, open at the front (fur on both edges) ----------------
Pp = V[pants_src]
SK_Z0, SK_Z1, NSK = -0.035, -0.225, 44
sk_rows = []
for z in np.linspace(SK_Z1, SK_Z0, 11):              # bottom -> top
    f = (SK_Z0 - z) / (SK_Z0 - SK_Z1)
    g = math.radians(3.5 + 6.0 * f)                  # half-gap at the front, widening to the hem
    s = Pp[np.abs(Pp[:, 2] - z) < 0.016]
    cy0 = coat_r(-math.pi / 2, SK_Z0)[1]
    legs = profile(s, 0.0, cy0, k=7, sm=3) + 0.022 if len(s) > 20 else np.zeros(NBIN)
    row = []
    for j in range(NSK):
        a = -math.pi / 2 + g + (2 * math.pi - 2 * g) * j / (NSK - 1)
        r0, c0 = coat_r(a, SK_Z0)
        fk = ((a + math.pi) / (2 * math.pi) * NBIN - 0.5) % NBIN; k0 = int(fk) % NBIN; t = fk - int(fk)
        rr = max((r0 + 0.005) * (1 + 0.13 * f ** 1.1), legs[k0] * (1 - t) + legs[(k0 + 1) % NBIN] * t)
        row.append(Vector((rr * math.cos(a), c0 + rr * math.sin(a), float(z))))
    sk_rows.append(row)
old = [[Vector(p) for p in row] for row in sk_rows]  # one smoothing pass up the skirt
for i in range(1, len(sk_rows) - 1):
    for j in range(NSK):
        p = (old[i - 1][j] + old[i][j] * 2 + old[i + 1][j]) / 4; p.z = old[i][j].z; sk_rows[i][j] = p
add("skirt", *open_loft(sk_rows), 'COAT', recalc=False, noleg=NOLEG_SKIRT)

# ---------------- belt (wide, black) + square gold buckle ----------------
def surf(c, a, z):
    d = Vector((math.cos(a), math.sin(a), 0)); o = Vector((c[0], c[1], z)) + d * 0.005
    hit = coat_bvh.ray_cast(o, d, 0.6)
    return (hit[0] if hit[0] is not None else o + d * 0.1), d
NBELT = 60; BZ = (-0.036, -0.003, 0.030); Vb, Fb = [], []
cyb = coat_r(-math.pi / 2, BZ[1])[1]
for k in range(NBELT):
    a = -math.pi + k / NBELT * 2 * math.pi
    for zi, z in enumerate((BZ[0] - 0.001,) + BZ + (BZ[2] + 0.001,)):
        p, d = surf((0, cyb), a, z); Vb.append(p + d * (-0.002 if zi in (0, 4) else 0.010))
for k in range(NBELT):
    k2 = (k + 1) % NBELT
    for zi in range(4): Fb.append((k * 5 + zi, k2 * 5 + zi, k2 * 5 + zi + 1, k * 5 + zi + 1))
belt_bvh = BVHTree.FromPolygons(Vb, Fb); pokes = []
for name_, vs_ in (("coat", coat_v), ("skirt", [p for row in sk_rows for p in row])):
    for p in vs_:
        if not BZ[0] + 0.002 < p.z < BZ[2] - 0.002: continue
        d = Vector((p.x, p.y - cyb, 0)); L = d.length; hit = belt_bvh.ray_cast(Vector((0, cyb, p.z)), d / L, 1.0)
        if hit[0] is not None and hit[3] < L: pokes.append((name_, round(math.degrees(math.atan2(d.y, d.x))), round(p.z, 3), round((L - hit[3]) * 1000, 1)))
print("CHECK coat/skirt verts poking through the belt:", len(pokes), pokes[:8])
WHIP = ('Hips', 'Spine', 'Spine1')                  # the belt rides the hips only (leg weights made it sag at the back)
add("belt", Vb, Fb, 'LEATHER', recalc=False, wkeep=WHIP)
p, d = surf((0, cyb), -math.pi / 2, BZ[1]); pb = p + d * 0.010; up = Vector((0, 0, 1)); tx = up.cross(d).normalized()
BW, BH, BB = 0.082, 0.070, 0.0135                    # buckle outer size and bar width
for off, w_, h_ in ((up * (BH / 2 - BB / 2), BW, BB), (-up * (BH / 2 - BB / 2), BW, BB), (tx * (BW / 2 - BB / 2), BB, BH), (-tx * (BW / 2 - BB / 2), BB, BH)):
    add("buckle", *box(pb + off, d, w_, h_, 0.008), 'GOLD', smooth=False, wkeep=WHIP)
add("buckle_prong", *box(pb - tx * 0.012, d, 0.040, 0.006, 0.010), 'GOLD', smooth=False, wkeep=WHIP)
add("buckle_tongue", *box(pb + tx * 0.004, d, BW - 2 * BB + 0.004, BH - 2 * BB + 0.004, 0.003), 'LEATHER', smooth=False, wkeep=WHIP)

# ---------------- fur trim: collar, placket, the skirt's front edges and hem ----------------
NCOL = 32; cpts, cn = [], []
for j in range(NCOL):
    a = -math.pi + 2 * math.pi * j / NCOL; zc = 0.494 - 0.004 * math.sin(a)   # a touch higher at the front, where the beard rests on it
    cpts.append(neck_c(zc) + Vector((math.cos(a), math.sin(a), 0)) * 0.086); cn.append(Vector((math.cos(a), math.sin(a), 0.35)))
add("fur_collar", *sweep(cpts, ellipse(0.019, 0.022, 8), normals=cn, closed=True, lump=0.17, lump_f=55, seed=1), 'FUR')
zs_ = np.linspace(0.470, 0.036, 26)                 # down to just above the belt (its top is 0.030)
add("fur_placket", *sweep([coat_pt(-math.pi / 2, z) for z in zs_], ellipse(0.029, 0.0085, 8), normals=[coat_n(-math.pi / 2, z) for z in zs_],
                          lift=0.006, lump=0.14, lump_f=60, seed=2), 'FUR')
c0 = coat_r(-math.pi / 2, SK_Z0)[1]                 # the skirt's centre line
for side, jj, sg in (('L', 0, 1), ('R', NSK - 1, -1)):
    pts, nn = [], []
    for i in range(len(sk_rows) - 1, -1, -1):        # top -> bottom along the opening's edge, 1 cm in from it
        e = sk_rows[i][jj]; r0 = Vector((e.x, e.y - c0)).length; a = math.atan2(e.y - c0, e.x) + sg * 0.010 / max(0.12, r0)
        pts.append(Vector((r0 * math.cos(a), c0 + r0 * math.sin(a), e.z))); nn.append(Vector((math.cos(a), math.sin(a), 0)))
    pts[0] = pts[0] + Vector((0, 0, -0.004))
    add(f"fur_edge_{side}", *sweep(pts, ellipse(0.0145, 0.0075, 8), normals=nn, lift=0.0055, lump=0.14, lump_f=60, seed=3 + jj), 'FUR', noleg=NOLEG_SKIRT)
hem_pts = [Vector((p.x, p.y, p.z + 0.010)) for p in sk_rows[0]]
hem_n = [Vector((p.x, p.y - c0, 0)).normalized() for p in hem_pts]
add("fur_hem", *sweep(hem_pts, ellipse(0.024, 0.0095, 8), normals=hem_n, lift=0.006, lump=0.14, lump_f=55, seed=7), 'FUR')

# ---------------- sleeves (upper arm only), fur cuffs, and the bare metal forearms ----------------
def frame(p0, p1):
    a = (p1 - p0).normalized(); u = a.cross(Vector((0, 0, 1)))
    if u.length < 1e-3: u = a.cross(Vector((1, 0, 0)))
    u.normalize(); v = a.cross(u).normalized(); return a, u, v
def sleeve(p0, p1, src_idx, t0, t1, off, rmax, nb=20, step=0.02):
    """horseman_build.py's tube(), with the domed shoulder: rings of max-radius profiles along p0 -> p1, capped at rmax(t)"""
    a, u, v = frame(p0, p1)
    P = V[src_idx] - np.array(p0); t = P @ np.array(a); Q = P - np.outer(t, np.array(a))
    r = np.linalg.norm(Q, axis=1); th = np.arctan2(Q @ np.array(v), Q @ np.array(u)); rs = []
    for tt in np.arange(t0, t1 + 1e-6, step):
        m = np.abs(t - tt) < 0.02
        if m.sum() < 6: continue
        prof = np.zeros(nb); b = ((th[m] + math.pi) / (2 * math.pi) * nb).astype(int) % nb
        for q in range(nb):
            mm = r[m][b == q]
            if len(mm): prof[q] = mm.max()
        prof = circ_median(fill(prof), 5)
        for _ in range(2): prof = (np.roll(prof, 1) + 2 * prof + np.roll(prof, -1)) / 4
        rs.append((tt, np.minimum(prof + off, rmax(tt))))
    for _ in range(2):
        pr = [x[1].copy() for x in rs]
        for k in range(1, len(rs) - 1): rs[k] = (rs[k][0], (pr[k - 1] + 2 * pr[k] + pr[k + 1]) / 4)
    if rs[-1][0] < t1 - 1e-4: rs.append((t1, rs[-1][1]))
    R0 = rs[0][1]; Rd = float(R0.mean()) * 0.95
    rs = [(rs[0][0] - Rd * fr, R0 * math.sqrt(max(0.0, 1 - fr * fr)) + 0.004) for fr in (0.98, 0.9, 0.75, 0.55, 0.3)] + rs
    rows = [[p0 + a * tt + (u * math.cos(ang(k, nb)) + v * math.sin(ang(k, nb))) * prof[k] for k in range(nb)] for tt, prof in rs]
    verts, faces = ring_loft(rows); faces.append(tuple(range(nb))[::-1])
    return verts, faces, [tt for tt, _ in rs for _k in range(nb)], rows[-1], rs[-1][1]
for side, sx in (('Left', 1.0), ('Right', -1.0)):
    pA, pE, pW = B(side + 'Arm'), B(side + 'ForeArm'), B(side + 'Hand')
    arm_src = np.array([i for i, d in enumerate(D) if d == side + 'Arm' and V[i, 2] < 0.46])
    L1 = (pE - pA).length; L2 = (pW - pE).length; a1 = (pE - pA).normalized()
    T_END = L1 - 0.040
    sv_, sf_, st_, last_row, last_r = sleeve(pA, pE, arm_src, 0.0, T_END, 0.016, lambda t, L1=L1: 0.066 - 0.012 * t / L1)
    blend = [smoothstep(L1 - 0.12, L1 - 0.08, t) for t in st_]          # the sleeve's end rides the upper arm only (rigid cuff)
    add(f"sleeve_{side}", sv_, sf_, 'COAT', recalc=False, wblend=(side + 'Arm', blend))
    cE = pA + a1 * T_END                                               # dark disc closing the sleeve's end (the cuff hides its rim)
    add(f"sleeve_cap_{side}", [cE] + last_row, [(0, 1 + k, 1 + (k + 1) % len(last_row)) for k in range(len(last_row))], 'CAVITY',
        w={side + 'Arm': 1.0}, smooth=False)
    tc = L1 - 0.060; Rc = float(last_r.mean()) + 0.009
    _, u1, v1 = frame(pA, pE)
    ring = [pA + a1 * tc + (u1 * math.cos(2 * math.pi * j / 20) + v1 * math.sin(2 * math.pi * j / 20)) * Rc for j in range(20)]
    add(f"fur_cuff_{side}", *sweep(ring, ellipse(0.022, 0.015, 8), normals=[p - (pA + a1 * tc) for p in ring], closed=True, lump=0.17, lump_f=55,
                                   seed=11 + sx), 'FUR', w={side + 'Arm': 1.0})
    add(f"humerus_{side}", *cyl(pA + a1 * (L1 - 0.070), pE, 0.0110, 12), 'STEEL', w={side + 'Arm': 1.0})
    # forearm: axle + servo + bearing at the elbow, two rods, two pistons, wires, a closed wrist ring over the glove's cuff
    a = (pW - pE).normalized(); lat = Vector((sx, 0, 0)); out = (lat - a * lat.dot(a)).normalized(); fw = a.cross(out).normalized()
    if fw.y > 0: fw = -fw
    WF = {side + 'ForeArm': 1.0}
    gl = np.array([V[i] for i in glove_idx if (V[i, 0] > 0) == (sx > 0)]); P = gl - np.array(pE); tg = P @ np.array(a)
    m = (tg > L2 - 0.03) & (tg < L2 + 0.02); rq = np.linalg.norm(P[m] - np.outer(tg[m], np.array(a)), axis=1) if m.any() else np.array([0.033])
    RW = float(np.percentile(rq, 98)) + 0.007
    print("FOREARM", side, "L1", round(L1, 3), "L2", round(L2, 3), "glove wrist r", round(RW - 0.007, 4), "ring r", round(RW, 4))
    add(f"elbow_axle_{side}", *cyl(pE - out * 0.026, pE + out * 0.026, 0.0130, 14), 'DARKSTEEL', w=WF, smooth=False)
    add(f"elbow_servo_{side}", *cyl(pE + out * 0.014, pE + out * 0.036, 0.0270, 22), 'STEEL', w=WF, smooth=False)
    add(f"elbow_hub_{side}", *cyl(pE + out * 0.036, pE + out * 0.042, 0.0100, 12), 'BRASS', w=WF, smooth=False)
    add(f"elbow_bearing_{side}", *cyl(pE - out * 0.014, pE - out * 0.029, 0.0200, 18), 'STEEL', w=WF, smooth=False)
    for so in (1, -1):
        add(f"forearm_rod_{side}", *cyl(pE + a * 0.010 + out * (0.0125 * so), pE + a * (L2 - 0.040) + out * (0.0115 * so), 0.0062, 10), 'STEEL', w=WF)
    for off, t0_, tm, r0_ in ((fw * 0.0215, 0.040, 0.150, 0.0105), (-fw * 0.0195, 0.060, 0.150, 0.0090)):
        add(f"piston_body_{side}", *cyl(pE + a * t0_ + off, pE + a * tm + off, r0_, 12), 'DARKSTEEL', w=WF)
        add(f"piston_rod_{side}", *cyl(pE + a * tm + off, pE + a * (L2 - 0.046) + off, r0_ * 0.46, 10), 'STEEL', w=WF)
        for tt in (t0_ - 0.006, L2 - 0.050):
            add(f"piston_eye_{side}", *cyl(pE + a * tt + off - out * 0.007, pE + a * tt + off + out * 0.007, 0.0072, 10), 'BRASS', w=WF, smooth=False)
    for ph, kd, o_ in ((0.0, 'WIRE_R', 0.022), (1.7, 'WIRE_K', 0.017)):
        pts = [pE + a * t + out * (o_ + 0.003 * math.sin(t * 60 + ph)) + fw * (0.006 * math.cos(t * 45 + ph)) for t in np.linspace(0.03, L2 - 0.05, 10)]
        add(f"forearm_wire_{side}", *sweep(pts, ellipse(0.0028, 0.0028, 6)), kd, w=WF)
    add(f"wrist_ring_{side}", *cyl(pE + a * (L2 - 0.050), pE + a * (L2 + 0.012), RW, 20), 'STEEL', w=WF, smooth=False)
    add(f"wrist_band_{side}", *cyl(pE + a * (L2 - 0.052), pE + a * (L2 - 0.044), RW + 0.0022, 20), 'BRASS', w=WF, smooth=False)

# ---------------- neck stump (Neck 100 %): rubber bellows, plate, post, coil spring, cut wires ----------------
NBW = 18; rows = []
for z in np.linspace(0.452, 0.566, 21):
    r = 0.053 - 0.004 * math.cos(2 * math.pi * 5 * (z - 0.452) / 0.114)            # 5 folds, valleys (0.049) at both ends
    c = neck_c(z); rows.append([c + Vector((math.cos(2 * math.pi * j / NBW), math.sin(2 * math.pi * j / NBW), 0)) * r for j in range(NBW)])
WN = {'Neck': 1.0}
add("neck_bellows", *ring_loft(rows), 'RUBBER', w=WN, recalc=False)
pv_, pf_ = cyl(neck_c(0.5660), neck_c(0.5720), 0.0525, 24)          # its top face dark: the user sees it below the eyes
add("neck_plate", pv_, pf_, ['STEEL'] * 25 + ['DARKSTEEL'], w=WN, smooth=False)
add("neck_post", *cyl(neck_c(0.572), neck_c(0.601), 0.0105, 12), 'STEEL', w=WN)
hel = [neck_c(0.5735 + 0.033 * i / 48) + Vector((math.cos(2 * math.pi * 4.5 * i / 48), math.sin(2 * math.pi * 4.5 * i / 48), 0)) * 0.0205 for i in range(49)]
add("neck_spring", *sweep(hel, ellipse(0.0033, 0.0033, 6)), 'STEEL', w=WN)
for a0, kd in ((math.radians(25), 'WIRE_R'), (math.radians(150), 'WIRE_Y'), (math.radians(265), 'WIRE_K')):
    pts = [neck_c(0.5725 + 0.027 * s ** 0.8) + Vector((math.cos(a0 + 0.35 * s), math.sin(a0 + 0.35 * s), 0)) * (0.031 + 0.011 * s) for s in np.linspace(0, 1, 8)]
    wv, wf = sweep(pts, ellipse(0.0029, 0.0029, 6))
    add("neck_wire", wv, wf, [('COPPER' if (fi >= 6 * 6 or fi == len(wf) - 1) else kd) for fi in range(len(wf))], w=WN)
STUMP = ("neck_plate", "neck_post", "neck_spring", "neck_wire")

# ---------------- the head (head-local: origin = DH_C, the skull's centre) ----------------
C = Vector((0.0, 0.005, 0.660))                      # DH_C; the eyes sit at the eye bones' height (0.649)
RX, RY, RZ = 0.080, 0.098, 0.115
def skull_pt(p):
    zt = max(0.0, -p.z)
    return Vector((RX * p.x * (1 - 0.17 * zt ** 1.6), RY * p.y * (1 - 0.05 * max(0.0, -p.y)) * (1 - 0.06 * zt), RZ * p.z))
sv0, sf = uvsphere(28, 16)
skull = [skull_pt(p) for p in sv0]
sk_k = []
for f in sf:
    c = sum((skull[i] for i in f), Vector()) / len(f); phf = abs(math.atan2(c.x, -c.y))
    sk_k.append('SKIN' if (c.y < 0 and phf < math.radians(80) and c.z > -0.095) else 'BEARD')   # pink face, white elsewhere
hadd("skull", skull, sf, sk_k)
skull_bvh = BVHTree.FromPolygons(skull, sf)
def front_hit(bvh, x, z):
    hit = bvh.ray_cast(Vector((x, -0.5, z)), Vector((0, 1, 0)), 1.0)
    n = Vector(hit[1])
    if n.y > 0: n = -n
    return Vector(hit[0]), n
def skull_r(a, z):
    hit = skull_bvh.ray_cast(Vector((0, 0, z)), Vector((math.cos(a), math.sin(a), 0)), 1.0)
    return hit[3] if hit[0] is not None else 0.0
# beard: a closed lumpy ellipsoid over the jaw; above the beard line it sinks under the skin, so the visible edge is
# where the two surfaces cross (no open rims)
BC = Vector((0.0, -0.040, -0.078)); BRX, BRY, BRZ = 0.084, 0.064, 0.090
def beard_line(x): return -0.058 + 0.052 * min(1.0, abs(x) / 0.085) ** 1.4
bv0, bf = uvsphere(26, 16); beard = []
for p in bv0:
    q = Vector((p.x * BRX * (1 - 0.28 * p.z * p.z if p.z < 0 else 1.0), p.y * BRY * (0.5 if p.y > 0 else 1.0), p.z * BRZ)) + BC
    nrm = Vector((p.x / BRX, p.y / (BRY * (0.5 if p.y > 0 else 1.0)), p.z / BRZ)).normalized()
    dm = math.hypot(q.x / 0.040, (q.z + 0.080) / 0.022)
    amp = 0.0045 * (smoothstep(1.2, 2.2, dm) if q.y < -0.05 else 1.0)            # no lumps where the mouth slot sits
    q = q + nrm * amp * noise.noise(q * 70.0)
    q = q - nrm * 0.026 * smoothstep(beard_line(q.x) - 0.004, beard_line(q.x) + 0.014, q.z)
    beard.append(q)
hadd("beard", beard, bf, 'BEARD')
beard_bvh = BVHTree.FromPolygons(beard, bf)
face_bvh = BVHTree.FromPolygons(skull + beard, sf + [tuple(i + len(skull) for i in f) for f in bf])
# hair: white and wavy from under the hat band round the back; it puffs out lower down, curls under at a scalloped
# bottom and thins to nothing at its front edges, where it meets the beard's sides
HA0, HA1, NHC = math.radians(-34), math.radians(214), 34
req = [skull_r(HA0 + (HA1 - HA0) * j / (NHC - 1), -0.005) for j in range(NHC)]
hrows = []
for z in np.linspace(-0.116, 0.034, 9):              # bottom -> top
    row = []
    for j in range(NHC):
        a = HA0 + (HA1 - HA0) * j / (NHC - 1); edge = smoothstep(0.0, 0.16, min(j, NHC - 1 - j) / (NHC - 1))
        r = skull_r(a, z) if z >= -0.005 else req[j] * (1 - 0.22 * ((-0.005 - z) / 0.115) ** 2)        # a bob: in at the bottom
        r += (0.007 + 0.008 * smoothstep(0.03, -0.04, z) - 0.006 * smoothstep(-0.05, -0.10, z) + 0.003 * math.sin(a * 14 + z * 40)) * edge + 0.001
        row.append(Vector((r * math.cos(a), r * math.sin(a), float(z))))
    hrows.append(row)
curl = []
for j in range(NHC):                                  # the curled-under bottom edge, scalloped
    a = HA0 + (HA1 - HA0) * j / (NHC - 1); p = hrows[0][j]; rr = p.xy.length - 0.018
    curl.append(Vector((rr * math.cos(a), rr * math.sin(a), p.z - 0.009 - 0.011 * abs(math.sin(a * 5.5)))))
hrows = [curl] + hrows
hadd("hair", *open_loft(hrows), 'BEARD', recalc=False)
# hat band (fur) and the hat (red velvet, drooping back and to the right) with a pompom
NBD = 24; band_p, band_n = [], []
for j in range(NBD):
    a = -math.pi + 2 * math.pi * j / NBD; zb = 0.045 - 0.010 * math.sin(a)          # front 0.055, back 0.035
    p = Vector((0, 0, zb)) + Vector((math.cos(a), math.sin(a), 0)) * skull_r(a, zb)
    band_p.append(p); band_n.append(Vector((p.x / RX ** 2, p.y / RY ** 2, p.z / RZ ** 2)).normalized())
hadd("hat_band", *sweep(band_p, ellipse(0.019, 0.012, 10), normals=band_n, closed=True, lift=0.011, lump=0.16, lump_f=55, seed=3), 'FUR')
P0 = sum(band_p, Vector()) / NBD
base = [p + n * 0.003 - P0 for p, n in zip(band_p, band_n)]
HP = [P0, P0 + Vector((0, 0.004, 0.100)), P0 + Vector((-0.024, 0.085, 0.150)), P0 + Vector((-0.058, 0.165, 0.085))]
def bez(s): return HP[0] * (1 - s) ** 3 + HP[1] * 3 * s * (1 - s) ** 2 + HP[2] * 3 * s * s * (1 - s) + HP[3] * s ** 3
def bez_d(s): return (HP[1] - HP[0]) * 3 * (1 - s) ** 2 + (HP[2] - HP[1]) * 6 * s * (1 - s) + (HP[3] - HP[2]) * 3 * s * s
t0h = bez_d(0).normalized(); hat_rows = []
for i in range(20):
    s = i / 19; q = t0h.rotation_difference(bez_d(s).normalized()); k = 1 - 0.88 * s ** 1.3      # slow at first: the crown stays inside
    hat_rows.append([bez(s) + (q @ b) * k for b in base])
hadd("hat", *ring_loft(hat_rows, cap_end=True), 'HAT')
hadd("pompom", *lumpy_ball(bez(1) + bez_d(1).normalized() * 0.012, 0.031, 16, 10, 0.12, 9.0, 4.0), 'FUR')
# eyes at the eye bones' height: the right one a sewn-on black button, the left one a red camera lens
eye_z = B('LeftEye').z - C.z
p, n = front_hit(skull_bvh, -0.032, eye_z)
bv_, bf_, bk_, (bu, bvv) = lathe(p - n * 0.002, n, [(0.0165, 0.0), (0.0165, 0.0055), (0.0145, 0.0075), (0.009, 0.0085), (0.0, 0.0088)], 20, ['BUTTON'] * 4)
hadd("eye_button", bv_, bf_, bk_, disc=(p - n * 0.002, bu, bvv, 0.0165))
p, n = front_hit(skull_bvh, 0.032, eye_z)
lv_, lf_, lk_, (lu, lvv) = lathe(p - n * 0.003, n, [(0.0185, 0.0), (0.0185, 0.014), (0.0172, 0.0158), (0.0138, 0.0158), (0.0134, 0.0135),
                                                    (0.0090, 0.0142), (0.0, 0.0146)], 20, ['STEEL', 'STEEL', 'DARKSTEEL', 'DARKSTEEL', 'LENS', 'LENS'])
hadd("eye_lens", lv_, lf_, lk_, disc=(p - n * 0.003, lu, lvv, 0.0134))
# brows, nose, moustache, the frozen slot grin
for sg in (-1, 1):
    hp = [front_hit(skull_bvh, sg * x, z) for x, z in ((0.011, eye_z + 0.027), (0.024, eye_z + 0.033), (0.039, eye_z + 0.034), (0.054, eye_z + 0.029))]
    pts = dense([q[0] for q in hp], 9); nn = dense([q[1] for q in hp], 9)
    hadd("brow", *sweep(pts, ellipse(0.0085, 0.0062, 8), normals=nn, scale=[1.0 - 0.45 * abs(i - 3) / 5 for i in range(9)], lift=0.0045,
                        lump=0.25, lump_f=180, seed=sg), 'BEARD')
p, n = front_hit(skull_bvh, 0.0, -0.030)
hadd("nose", *lumpy_ball(p + n * 0.006, 1.0, 14, 10, 0.0, 1.0, 0.0, scl=(0.0175, 0.016, 0.0165)), 'NOSE')
for sg in (-1, 1):
    hp = [front_hit(face_bvh, sg * x, z) for x, z in ((0.003, -0.047), (0.018, -0.052), (0.034, -0.058), (0.049, -0.061), (0.061, -0.056), (0.069, -0.046))]
    pts = dense([q[0] for q in hp], 13); nn = dense([q[1] for q in hp], 13)
    hadd("moustache", *sweep(pts, ellipse(0.0105, 0.0072, 8), normals=nn, scale=[1.0 - 0.6 * (i / 12) ** 1.3 for i in range(13)], lift=0.0055,
                             lump=0.18, lump_f=200, seed=10 + sg), 'BEARD')
hp = [front_hit(beard_bvh, x, -0.082 + 0.0065 * (x / 0.029) ** 2) for x in np.linspace(-0.029, 0.029, 9)]
hadd("mouth_slot", *sweep([q[0] for q in hp], rect(0.0052, 0.0095), normals=[q[1] for q in hp], lift=-0.0065), 'MOUTH', smooth=False)
# the socket under the head (the bellows goes into it): a steel collar with a dark recessed ceiling
YS = neck_c(0.57).y - C.y
hadd("socket", *annulus(Vector((0, YS, 0.535 - C.z)), Vector((0, YS, 0.620 - C.z)), 0.0605, 0.0675, 28), 'STEEL', smooth=False)
hadd("socket_ceiling", *cyl(Vector((0, YS, 0.539 - C.z)), Vector((0, YS, 0.5415 - C.z)), 0.0606, 28), 'CAVITY', smooth=False)
for hpart in hparts: add(hpart['name'], [p + C for p in hpart['v']], hpart['f'], hpart['k'], smooth=hpart['smooth'], w=hpart['w'],
                         recalc=hpart['recalc'], disc=(hpart['disc'][0] + C,) + tuple(hpart['disc'][1:]) if hpart['disc'] else None)
HEAD_NAMES = {h['name'] for h in hparts}

# ---------------- checks on the raw geometry ----------------
def merged(names, src):
    vs, fs = [], []
    for q in src:
        if q['name'] in names: fs += [tuple(i + len(vs) for i in f) for f in q['f']]; vs += q['v']
    return vs, fs
dirs = [Vector((x, y, z)).normalized() for x in (-1, 0, 1) for y in (-1, 0, 1) for z in (-1, 0, 1) if (x, y, z) != (0, 0, 0)]
crown = [p for p in skull if p.z > 0.045 - 0.010 * math.sin(math.atan2(p.y, p.x)) + 0.020]          # above the band's top edge
hb = BVHTree.FromPolygons(*merged({"hat", "hat_band", "pompom"}, hparts))
seen = sum(1 for p in crown if any(hb.ray_cast(p + d * 1e-4, d, 2.0)[0] is None for d in dirs if d.dot(p.normalized()) > 0.2))
print("CHECK skull crown verts visible past the hat (a ray escapes):", seen, "of", len(crown), "(want 0)")
enc_v, enc_f = merged(HEAD_NAMES | {"neck_bellows", "neck_plate"}, parts)
enc = BVHTree.FromPolygons(enc_v, enc_f)
exposed = 0; stump_pts = merged(set(STUMP), parts)[0]
for p in stump_pts:
    if any(enc.ray_cast(p + d * 1e-4, d, 2.0)[0] is None for d in dirs): exposed += 1
print("CHECK stump verts visible while the head is on (a ray escapes):", exposed, "of", len(stump_pts), "(want 0)")
stump_top = max(p.z for p in stump_pts); print("STUMP top z", round(stump_top, 4), "| eye bones z", round(B('LeftEye').z, 4))

# ---------------- texture atlas: free cells + painted patches ----------------
def vnoise(u, v, f, seed):
    g = np.random.default_rng(seed).random((f + 2, f + 2))
    x = np.clip(u, 0, 1) * f; y = np.clip(v, 0, 1) * f; x0 = np.floor(x).astype(int); y0 = np.floor(y).astype(int)
    tx = x - x0; ty = y - y0; tx = tx * tx * (3 - 2 * tx); ty = ty * ty * (3 - 2 * ty)
    return (g[y0, x0] * (1 - tx) + g[y0, x0 + 1] * tx) * (1 - ty) + (g[y0 + 1, x0] * (1 - tx) + g[y0 + 1, x0 + 1] * tx) * ty
def fbm(u, v, f, seed, octaves=3):
    s, amp, tot = 0.0, 1.0, 0.0
    for o in range(octaves): s = s + amp * vnoise(u, v, f * 2 ** o, seed + o); tot += amp; amp *= 0.5
    return s / tot
Z3 = lambda sh: np.zeros(sh + (3,))
def flat(c, rough, metal=0.0, var=0.04, seed=1):
    def fn(uu, vv):
        sh = uu.shape; col = np.array(c) * (1 + var * 2 * (fbm(uu, vv, 8, seed) - 0.5))[..., None]
        return np.clip(col, 0, 1), Z3(sh), np.full(sh, rough), np.full(sh, metal)
    return fn
def velvet(c, seed):
    def fn(uu, vv):
        sh = uu.shape; pile = fbm(uu, vv, 5, seed, 4); wear = fbm(uu, vv, 11, seed + 50, 3)
        col = np.array(c) * (0.80 + 0.40 * pile)[..., None]
        w = (np.clip((wear - 0.60) / 0.14, 0, 1) * 0.5)[..., None]
        col = col * (1 - w) + np.array((0.56, 0.20, 0.19)) * w                       # rubbed-down pile: paler, a little brown
        return np.clip(col, 0, 1), Z3(sh), 0.84 + 0.10 * w[..., 0], np.zeros(sh)
    return fn
def torn(uu, vv):
    sh = uu.shape; col = np.array((0.46, 0.035, 0.05)) * (0.85 + 0.3 * fbm(uu, vv, 9, 61))[..., None]
    th = vnoise(uu, vv, 40, 62) > 0.78; col[th] = (0.78, 0.66, 0.56)               # loose threads / lining
    return np.clip(col, 0, 1), Z3(sh), np.full(sh, 0.9), np.zeros(sh)
def fur(c, seed):
    def fn(uu, vv):
        sh = uu.shape; col = np.array(c) * (0.80 + 0.14 * fbm(uu, vv, 9, seed) + 0.08 * vnoise(uu, vv, 60, seed + 7))[..., None]
        return np.clip(col, 0, 1), Z3(sh), np.full(sh, 1.0), np.zeros(sh)
    return fn
def beard_tex(c, seed):
    def fn(uu, vv):
        sh = uu.shape; st = 0.5 + 0.5 * np.sin(2 * np.pi * (uu * 46 + 2.5 * fbm(uu, vv, 4, seed, 2)))   # strands
        col = np.array(c) * (0.80 + 0.12 * st + 0.08 * fbm(uu, vv, 24, seed + 3, 2))[..., None]
        return np.clip(col, 0, 1), Z3(sh), np.full(sh, 0.95), np.zeros(sh)
    return fn
def metal(c, rough, seed):
    def fn(uu, vv):
        sh = uu.shape; br = vnoise(uu * 0.05, vv, 120, seed)                          # brushed: streaks along u
        return np.clip(np.array(c) * (0.90 + 0.14 * br)[..., None], 0, 1), Z3(sh), rough + 0.06 * (br - 0.5), np.ones(sh)
    return fn
SKIN_W, SKIN_H = 0.20, 0.24                           # the face texture: a front projection over x +-0.10, z +-0.12 (head-local)
def skin_tex(uu, vv):
    sh = uu.shape; x = (uu - 0.5) * SKIN_W; z = (vv - 0.5) * SKIN_H
    col = np.array((0.97, 0.68, 0.67)) * (0.97 + 0.05 * fbm(uu, vv, 12, 21, 2))[..., None]          # slightly too pink
    ck = np.exp(-(((np.abs(x) - 0.046) / 0.019) ** 2 + ((z + 0.036) / 0.016) ** 2))[..., None] * 0.55
    col = col * (1 - ck) + np.array((0.93, 0.42, 0.46)) * ck                                          # rosy cheeks
    ro = np.full(sh, 0.38); mt = np.zeros(sh)
    SX, ST = 0.060, eye_z + 0.046                                                                     # faceplate seam
    seam = ((np.abs(np.abs(x) - SX) < 0.0009) & (z > -0.075) & (z < ST + 0.0005)) | ((np.abs(z - ST) < 0.0009) & (np.abs(x) < SX + 0.0009))
    col[seam] = (0.40, 0.21, 0.21)
    for ex in (-0.032, 0.032):                                                                        # sockets: a darker rim
        d = np.hypot(x - ex, z - eye_z); col[(d > 0.0165) & (d < 0.0215)] *= 0.80
    for sx_ in (-SX, SX):                                                                             # screws on the seam
        for sz in (ST - 0.009, eye_z - 0.022):
            d = np.hypot(x - sx_, z - sz); m = d < 0.0029
            col[m] = (0.62, 0.62, 0.65); ro[m] = 0.3; mt[m] = 1.0
            col[m & (np.abs((x - sx_) - (z - sz)) < 0.0006)] = (0.12, 0.12, 0.13)
    return np.clip(col, 0, 1), Z3(sh), ro, mt
def button_tex(uu, vv):
    sh = uu.shape; x = uu * 2 - 1; y = vv * 2 - 1; r = np.hypot(x, y)
    col = np.ones(sh + (3,)) * np.array((0.03, 0.03, 0.035)); col[(r > 0.72) & (r < 0.96)] = (0.08, 0.08, 0.09)
    holes = np.zeros(sh, bool)
    for hx in (-0.27, 0.27):
        for hy in (-0.27, 0.27): holes |= np.hypot(x - hx, y - hy) < 0.11
    thread = ((np.abs(x - y) < 0.065) | (np.abs(x + y) < 0.065)) & (r < 0.40) & ~holes
    col[holes] = (0.004, 0.004, 0.004); col[thread] = (0.45, 0.05, 0.05)                              # sewn on with red thread
    return col, Z3(sh), np.full(sh, 0.16), np.zeros(sh)
def lens_tex(uu, vv):
    sh = uu.shape; x = uu * 2 - 1; y = vv * 2 - 1; r = np.hypot(x, y)
    g = np.clip(r / 0.75, 0, 1)[..., None]
    col = np.array((1.0, 0.30, 0.22)) * (1 - g) + np.array((0.85, 0.04, 0.03)) * g                   # bright red even unlit
    emi = np.array((1.0, 0.10, 0.04)) * (0.35 + 0.65 * np.clip(1 - r / 0.8, 0, 1))[..., None]
    ap = (r > 0.36) & (r < 0.44); col[ap] = (0.35, 0.0, 0.0); emi[ap] *= 0.3                          # aperture ring
    out = r > 0.88; col[out] = (0.05, 0.02, 0.02); emi[out] = 0
    gl = np.hypot(x + 0.33, y - 0.33) < 0.13; col[gl] = (1.0, 1.0, 1.0); emi[gl] = (1.0, 0.9, 0.9)    # glint
    return np.clip(col, 0, 1), np.clip(emi, 0, 1), np.full(sh, 0.08), np.zeros(sh)
SPEC = {   # kind: (painter, cells of 16 px, textured = the UVs use the whole patch)
    'COAT': (velvet((0.62, 0.045, 0.065), 1), 12, False),
    'HAT': (velvet((0.68, 0.050, 0.070), 11), 8, False),
    'TORN': (torn, 4, False),
    'CAVITY': (flat((0.05, 0.05, 0.055), 0.7, 0.4), 3, False),
    'FUR': (fur((0.92, 0.90, 0.86), 3), 8, False),
    'BEARD': (beard_tex((0.95, 0.95, 0.93), 4), 10, True),
    'LEATHER': (flat((0.03, 0.028, 0.028), 0.45, 0.0, 0.08), 3, False),
    'GOLD': (metal((0.93, 0.72, 0.30), 0.28, 6), 3, False),
    'STEEL': (metal((0.74, 0.74, 0.76), 0.30, 7), 4, False),
    'DARKSTEEL': (metal((0.30, 0.30, 0.32), 0.42, 8), 3, False),
    'BRASS': (metal((0.80, 0.60, 0.27), 0.33, 9), 3, False),
    'COPPER': (metal((0.88, 0.50, 0.30), 0.30, 10), 2, False),
    'RUBBER': (flat((0.055, 0.055, 0.06), 0.62, 0.0, 0.10), 3, False),
    'WIRE_R': (flat((0.78, 0.07, 0.05), 0.45), 2, False),
    'WIRE_Y': (flat((0.88, 0.68, 0.08), 0.45), 2, False),
    'WIRE_K': (flat((0.03, 0.03, 0.035), 0.5), 2, False),
    'SKIN': (skin_tex, 16, True),
    'NOSE': (flat((0.95, 0.55, 0.55), 0.40, 0.0, 0.03), 3, False),
    'BUTTON': (button_tex, 4, True),
    'LENS': (lens_tex, 6, True),
    'MOUTH': (flat((0.025, 0.012, 0.012), 0.9), 2, False),
}
PANTS_C = np.array((0.52, 0.040, 0.060))            # red trousers: cargo.py's FABRIC patch repainted
def build_atlas(arrs, occ, G):
    """paint every SPEC kind into free G x G cells of arrs (color/emissive/orm[/normal]); returns kind -> UV rect"""
    def find_free(w, h):
        for y in range(G - h):
            for x in range(G - w):
                if not occ[y:y + h, x:x + w].any(): occ[y:y + h, x:x + w] = True; return x, y
        raise SystemExit(f"no atlas space {w}x{h}")
    def paint_rect(u0, v0, u1, v1, fn):
        cache = {}
        def grid(k):
            H, W = arrs[k].shape[:2]; X0, Y0, X1, Y1 = int(u0 * W), int(v0 * H), int(u1 * W), int(v1 * H)
            if (H, W) not in cache:
                yy, xx = np.mgrid[Y0:Y1, X0:X1]; cache[(H, W)] = fn((xx + 0.5 - X0) / (X1 - X0), (yy + 0.5 - Y0) / (Y1 - Y0))
            return (X0, Y0, X1, Y1) + cache[(H, W)]
        X0, Y0, X1, Y1, col, emi, ro, mt = grid('color'); arrs['color'][Y0:Y1, X0:X1, :3] = col; arrs['color'][Y0:Y1, X0:X1, 3] = 1
        X0, Y0, X1, Y1, col, emi, ro, mt = grid('emissive'); arrs['emissive'][Y0:Y1, X0:X1, :3] = emi
        if 'normal' in arrs: X0, Y0, X1, Y1, *_ = grid('normal'); arrs['normal'][Y0:Y1, X0:X1] = (0.5, 0.5, 1.0, 1.0)
        X0, Y0, X1, Y1, col, emi, ro, mt = grid('orm')
        arrs['orm'][Y0:Y1, X0:X1, 0] = 1; arrs['orm'][Y0:Y1, X0:X1, 1] = ro; arrs['orm'][Y0:Y1, X0:X1, 2] = mt; arrs['orm'][Y0:Y1, X0:X1, 3] = 1
    patch = {}
    for kind, (fn, n, textured) in SPEC.items():
        x, y = find_free(n + 2, n + 2); x += 1; y += 1
        u0, v0, u1, v1 = (x - 0.5) / G, (y - 0.5) / G, (x + n + 0.5) / G, (y + n + 0.5) / G
        patch[kind] = ((x + 0.3) / G, (y + 0.3) / G, (x + n - 0.3) / G, (y + n - 0.3) / G)
        if textured:          # the painter's 0..1 must land exactly on the UV rect: paint the rect, then pad the margin
            pu0, pv0, pu1, pv1 = patch[kind]
            paint_rect(u0, v0, u1, v1, lambda uu, vv, fn=fn, pu0=pu0, pv0=pv0, pu1=pu1, pv1=pv1:
                       fn(np.clip(((u0 + uu * (u1 - u0)) - pu0) / (pu1 - pu0), 0, 1), np.clip(((v0 + vv * (v1 - v0)) - pv0) / (pv1 - pv0), 0, 1)))
        else: paint_rect(u0, v0, u1, v1, fn)
    return patch
imgs = {k: bpy.data.images['final_' + k] for k in ('color', 'normal', 'orm')}
arrs = {}
for k, img in imgs.items():
    a_ = np.empty(img.size[0] * img.size[1] * 4, np.float32); img.pixels.foreach_get(a_); arrs[k] = a_.reshape(img.size[1], img.size[0], 4)
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
patch = build_atlas(arrs, occ, G)
def uv_mask(tris, H, W, dil):
    m = np.zeros((H, W), bool)
    for (ax, ay), (bx, by), (cx_, cy_) in tris:
        ax, bx, cx_, ay, by, cy_ = ax * W, bx * W, cx_ * W, ay * H, by * H, cy_ * H
        den = (by - cy_) * (ax - cx_) + (cx_ - bx) * (ay - cy_)
        if abs(den) < 1e-9: continue
        x0 = max(0, int(min(ax, bx, cx_)) - 1); x1 = min(W - 1, int(max(ax, bx, cx_)) + 1)
        y0 = max(0, int(min(ay, by, cy_)) - 1); y1 = min(H - 1, int(max(ay, by, cy_)) + 1)
        yy, xx = np.mgrid[y0:y1 + 1, x0:x1 + 1] + 0.5
        l1 = ((by - cy_) * (xx - cx_) + (cx_ - bx) * (yy - cy_)) / den; l2 = ((cy_ - ay) * (xx - cx_) + (ax - cx_) * (yy - cy_)) / den
        m[y0:y1 + 1, x0:x1 + 1] |= (l1 >= -0.02) & (l2 >= -0.02) & (l1 + l2 <= 1.02)
    for _ in range(dil):
        m2 = m.copy(); m2[1:] |= m[:-1]; m2[:-1] |= m[1:]; m2[:, 1:] |= m[:, :-1]; m2[:, :-1] |= m[:, 1:]; m = m2
    return m
def face_tris(keep):
    out = []
    for f in bm.faces:
        if all(v.index in keep for v in f.verts):
            us = [(l[uvl].uv.x, l[uvl].uv.y) for l in f.loops]; out += [(us[0], us[t], us[t + 1]) for t in range(1, len(us) - 1)]
    return out
pt = face_tris(pants_idx)
for k in ('color', 'orm'):
    H, W = arrs[k].shape[:2]; m = uv_mask(pt, H, W, 2); yy, xx = np.nonzero(m)
    if k == 'color':
        u = (xx - xx.min()) / max(1, xx.max() - xx.min()); v = (yy - yy.min()) / max(1, yy.max() - yy.min())
        arrs['color'][yy, xx, :3] = PANTS_C * (0.84 + 0.30 * fbm(u, v, 6, 77, 3))[:, None]
    else: arrs['orm'][yy, xx, 1] = 0.88; arrs['orm'][yy, xx, 2] = 0.0
print("PANTS texels", int(len(yy)), "(orm)")
gm = uv_mask(face_tris(glove_idx), 2048, 2048, 1); arrs['color'][gm, :3] *= 0.45      # gloves: black
print("GLOVE texels", int(gm.sum()))
bm.free()
for k, img in imgs.items():
    img.pixels.foreach_set(arrs[k].ravel()); img.update(); img.pack()
em.pixels.foreach_set(arrs['emissive'].ravel()); em.update(); em.pack()
print("PATCHES", {k: [round(t, 4) for t in v] for k, v in patch.items()})

# ---------------- objects, UVs, weights ----------------
def proj(kind, P, part):
    """(uu, vv) in 0..1 inside the kind's patch for world point P"""
    if kind == 'SKIN': L = P - C; return 0.5 + L.x / SKIN_W, 0.5 + L.z / SKIN_H
    if kind == 'BEARD': L = P - C; return 0.5 + L.x / 0.24, 0.5 + (L.z + 0.03) / 0.36
    if kind in ('BUTTON', 'LENS') and part['disc']:
        c, u, v, r = part['disc']; d = P - c; return 0.5 + d.dot(u) / (2 * r), 0.5 + d.dot(v) / (2 * r)
    return (P.x + 0.5 + 0.5 * P.y) / 1.2, (P.z + 0.6) / 1.4
def make_obj(part, patch, offset=Vector()):
    m = bpy.data.meshes.new(part['name']); m.from_pydata([tuple(p) for p in part['v']], [], part['f']); m.update()
    o = bpy.data.objects.new(part['name'], m); bpy.context.scene.collection.objects.link(o)
    for p_ in m.polygons: p_.use_smooth = part['smooth']
    uv = m.uv_layers.new(name="UVMap")
    for poly in m.polygons:
        kind = part['k'][poly.index]; u0, v0, u1, v1 = patch[kind]; textured = SPEC[kind][2]
        for li in poly.loop_indices:
            P = m.vertices[m.loops[li].vertex_index].co + offset
            uu, vv = proj(kind, P, part); uu = min(1, max(0, uu)); vv = min(1, max(0, vv))
            if textured: uv.data[li].uv = (u0 + (u1 - u0) * uu, v0 + (v1 - v0) * vv)
            else: uv.data[li].uv = (u0 + (u1 - u0) * (0.15 + 0.7 * uu), v0 + (v1 - v0) * (0.15 + 0.7 * vv))
    bmx = bmesh.new(); bmx.from_mesh(m)
    if part['recalc']: bmesh.ops.recalc_face_normals(bmx, faces=bmx.faces)
    for e in bmx.edges:                                  # crisp rims on the hardware, soft everywhere else
        if len(e.link_faces) == 2 and e.calc_face_angle(0) > math.radians(50): e.smooth = False
    bmx.to_mesh(m); bmx.free(); m.update()
    return o
new = []
for part in parts:
    o = make_obj(part, patch); o.data.materials.append(me.data.materials[0]); new.append(o)
src = me.copy(); src.data = me.data.copy(); src.name = "wsrc"; bpy.context.scene.collection.objects.link(src); src.modifiers.clear()
sbm = bmesh.new(); sbm.from_mesh(src.data); sbm.verts.ensure_lookup_table()
bmesh.ops.delete(sbm, geom=[v for v in sbm.verts if D[v.index] in HEADB], context='VERTS'); sbm.to_mesh(src.data); sbm.free()
for o, part in zip(new, parts):
    bpy.ops.object.select_all(action='DESELECT'); o.select_set(True); bpy.context.view_layer.objects.active = o
    if part['w']:
        for bn, w in part['w'].items():
            vg = o.vertex_groups.new(name=bn); vg.add(list(range(len(o.data.vertices))), w, 'REPLACE')
        continue
    md = o.modifiers.new("dt", 'DATA_TRANSFER'); md.object = src; md.use_vert_data = True
    md.data_types_verts = {'VGROUP_WEIGHTS'}; md.vert_mapping = 'POLYINTERP_NEAREST'
    md.layers_vgroup_select_src = 'ALL'; md.layers_vgroup_select_dst = 'NAME'
    bpy.ops.object.datalayout_transfer(modifier="dt"); bpy.ops.object.modifier_apply(modifier="dt")
    # skullbuck's neck verts carry ~20 % Head: without this the collar + neckline would half-collapse while the head flies
    for gname in HEADB:
        g = o.vertex_groups.get(gname)
        if g: o.vertex_groups.remove(g)
    gN = o.vertex_groups.get('Neck') or o.vertex_groups.new(name='Neck')
    for v in o.data.vertices:
        if sum(g.weight for g in v.groups) < 1e-6: gN.add([v.index], 1.0, 'REPLACE')
    if part['noleg']:                                # no thigh weight at the belt line, blending in below it
        z0, z1 = part['noleg']; legs = [g for g in o.vertex_groups if 'Leg' in g.name or 'Foot' in g.name or 'Toe' in g.name]
        gH = o.vertex_groups.get('Hips') or o.vertex_groups.new(name='Hips')
        for v in o.data.vertices:
            sv = smoothstep(z0, z1, v.co.z)
            if sv <= 0: continue
            for g in legs:
                w = next((x.weight for x in v.groups if x.group == g.index), 0.0)
                if w > 0: g.add([v.index], w * (1 - sv), 'REPLACE')
            if sum(x.weight for x in v.groups) < 1e-6: gH.add([v.index], 1.0, 'REPLACE')
    if part['wkeep']:
        for g in list(o.vertex_groups):
            if g.name not in part['wkeep']: o.vertex_groups.remove(g)
        g0 = o.vertex_groups.get(part['wkeep'][0]) or o.vertex_groups.new(name=part['wkeep'][0])
        for v in o.data.vertices:
            if sum(g.weight for g in v.groups) < 1e-6: g0.add([v.index], 1.0, 'REPLACE')
    bpy.ops.object.vertex_group_limit_total(limit=4); bpy.ops.object.vertex_group_normalize_all(lock_active=False)
    if part['wblend']:
        bn, sl = part['wblend']; gB = o.vertex_groups.get(bn) or o.vertex_groups.new(name=bn)
        for vi, s in enumerate(sl):
            if s <= 0: continue
            old = {o.vertex_groups[g.group].name: g.weight for g in o.data.vertices[vi].groups}
            for gname, w in old.items(): o.vertex_groups[gname].add([vi], w * (1 - s), 'REPLACE')
            gB.add([vi], old.get(bn, 0.0) * (1 - s) + s, 'REPLACE')
        bpy.ops.object.vertex_group_limit_total(limit=4); bpy.ops.object.vertex_group_normalize_all(lock_active=False)
    bad = sum(1 for v in o.data.vertices if not v.groups or sum(g.weight for g in v.groups) < 0.99)
    if bad: print("UNWEIGHTED", o.name, bad)
bpy.data.objects.remove(src)

# ---------------- static head (own file, own textures) ----------------
HG = 64; harrs = {'color': np.zeros((1024, 1024, 4), np.float32), 'emissive': np.zeros((1024, 1024, 4), np.float32), 'orm': np.zeros((1024, 1024, 4), np.float32)}
for k in harrs: harrs[k][:, :, 3] = 1
SPEC_ALL = SPEC; SPEC = {k: SPEC_ALL[k] for k in sorted({k for h in hparts for k in h['k']}, key=list(SPEC_ALL).index)}
hpatch = build_atlas(harrs, np.zeros((HG, HG), bool), HG)
SPEC = SPEC_ALL
hobjs = []
for h in hparts:
    o = make_obj(dict(h, disc=(h['disc'][0] + C,) + tuple(h['disc'][1:]) if h['disc'] else None), hpatch, offset=C); hobjs.append(o)
def mkimg(name, a, noncolor=False):
    im = bpy.data.images.new(name, a.shape[1], a.shape[0], alpha=False); im.pixels.foreach_set(a.ravel()); im.update(); im.pack()
    if noncolor: im.colorspace_settings.name = 'Non-Color'
    return im
imC = mkimg('santa_head_color', harrs['color']); imE = mkimg('santa_head_emissive', harrs['emissive']); imO = mkimg('santa_head_orm', harrs['orm'], True)
matS = bpy.data.materials.new('SantaHead'); matS.use_nodes = True; nt = matS.node_tree; bsdf = nt.nodes['Principled BSDF']
def texnode(im):
    n_ = nt.nodes.new('ShaderNodeTexImage'); n_.image = im; return n_
nt.links.new(texnode(imC).outputs['Color'], bsdf.inputs['Base Color'])
nt.links.new(texnode(imE).outputs['Color'], bsdf.inputs['Emission Color']); bsdf.inputs['Emission Strength'].default_value = 1.0
sep = nt.nodes.new('ShaderNodeSeparateColor'); nt.links.new(texnode(imO).outputs['Color'], sep.inputs['Color'])
nt.links.new(sep.outputs['Green'], bsdf.inputs['Roughness']); nt.links.new(sep.outputs['Blue'], bsdf.inputs['Metallic'])
for o in hobjs: o.data.materials.append(matS)
bpy.ops.object.select_all(action='DESELECT')
for o in hobjs: o.select_set(True)
bpy.context.view_layer.objects.active = hobjs[0]; bpy.ops.object.join(); st = hobjs[0]; st.name = "SantaHead_Static"; st.data.name = "SantaHead_Static"
print("STATIC HEAD tris", sum(len(p.vertices) - 2 for p in st.data.polygons))
matB = me.data.materials[0]; ntB = matB.node_tree; bB = ntB.nodes['Principled BSDF']     # emissive on the body material too
tEB = ntB.nodes.new('ShaderNodeTexImage'); tEB.image = em; ntB.links.new(tEB.outputs['Color'], bB.inputs['Emission Color']); bB.inputs['Emission Strength'].default_value = 1.0

# the trousers' bottoms (inside the boots) pulled 6 mm toward the shin: at a bent knee they poked out of the boot tops
# (the breeches always did; now it is red against black)
for side, sx in (('Left', 1), ('Right', -1)):
    kn, an = B(side + 'Leg'), B(side + 'Foot')
    for i in pants_idx:
        v = me.data.vertices[i]
        if v.co.z > -0.66 or (v.co.x > 0) != (sx > 0): continue
        c = kn.lerp(an, (v.co.z - kn.z) / (an.z - kn.z)); d = Vector((v.co.x - c.x, v.co.y - c.y, 0))
        if d.length > 1e-4: v.co = v.co - d.normalized() * 0.006 * smoothstep(-0.66, -0.70, v.co.z)

# ---------------- delete the old upper body, join, DH bones, export ----------------
tri = lambda o: sum(len(p.vertices) - 2 for p in o.data.polygons)
groups = {}
for o, part in zip(new, parts):
    g = 'head' if part['name'] in HEAD_NAMES else 'neck stump' if part['name'].startswith('neck') else \
        'forearms' if any(part['name'].startswith(s) for s in ('elbow', 'forearm', 'piston', 'wrist', 'humerus')) else 'coat + trim'
    groups[g] = groups.get(g, 0) + tri(o)
bpy.ops.object.select_all(action='DESELECT'); bpy.context.view_layer.objects.active = me; me.select_set(True)
bpy.ops.object.mode_set(mode='EDIT'); bpy.ops.mesh.select_mode(type='VERT'); bpy.ops.mesh.select_all(action='DESELECT'); bpy.ops.object.mode_set(mode='OBJECT')
for v in me.data.vertices: v.select = v.index in remove
before = len(me.data.vertices)
bpy.ops.object.mode_set(mode='EDIT'); bpy.ops.mesh.delete(type='VERT'); bpy.ops.object.mode_set(mode='OBJECT')
print("DELETED", before - len(me.data.vertices), "expected", len(remove))
groups['kept body (legs, boots, gloves)'] = tri(me)
for o in new: o.select_set(True)
me.select_set(True); bpy.context.view_layer.objects.active = me; bpy.ops.object.join()
while len(me.data.materials) > 1: me.data.materials.pop()
for p_ in me.data.polygons: p_.material_index = 0
print("TRIS by group", groups)
print("FINAL tris", tri(me))
gidx = {g.name: g.index for g in me.vertex_groups}
hw = [next((g.weight for g in v.groups if g.group == gidx['Head']), 0.0) for v in me.data.vertices]
handg = {gidx[n] for n in gidx if 'Hand' in n}
print("CHECK verts with partial Head weight:", sum(1 for w in hw if 1e-4 < w < 0.9999), "(want 0) | Head 100 %:", sum(1 for w in hw if w >= 0.9999),
      "| with any Hand weight:", sum(1 for v in me.data.vertices if any(g.group in handg and g.weight > 1e-4 for g in v.groups)), "(= the kept gloves)")

bpy.ops.object.select_all(action='DESELECT'); arm.select_set(True); bpy.context.view_layer.objects.active = arm
bpy.ops.object.mode_set(mode='EDIT')
eb = arm.data.edit_bones; headb = eb['Head']; inv = arm.matrix_world.inverted()
for name, off in (('DH_C', Vector((0, 0, 0))), ('DH_F', Vector((0, -0.10, 0))), ('DH_U', Vector((0, 0, 0.10)))):
    b = eb.new(name); b.head = inv @ (C + off); b.tail = b.head + Vector((0, 0, 0.02)); b.parent = headb; b.use_connect = False; b.use_deform = False
bpy.ops.object.mode_set(mode='OBJECT')
print("DH bones", {b.name: [round(x, 4) for x in b.head_local] for b in arm.data.bones if b.name.startswith('DH_')})

bpy.ops.object.select_all(action='DESELECT'); me.select_set(True); arm.select_set(True)
bpy.ops.export_scene.gltf(filepath=os.path.join(OUT, "santa.glb"), export_format='GLB', use_selection=True, export_animations=False)
bpy.ops.object.select_all(action='DESELECT'); st.select_set(True)
bpy.ops.export_scene.gltf(filepath=os.path.join(OUT, "santa_head.glb"), export_format='GLB', use_selection=True, export_animations=False)
print("EXPORTED", OUT)
