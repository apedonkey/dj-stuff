"""MAJOR TOM (HARVEST MOON, the Thanksgiving stage) from skullbuck's rigged body, built the way scripts/santa_build.py built
the Animatronic Santa: the body is replaced by a procedural spacesuit lofted from the body's radius profiles, weighted
with DATA_TRANSFER from the original (the sleeves by position along the arm), painted into skullbuck's texture atlas.
The hands stay, puffed out into space gloves on their own hand + finger weights; the hips and thighs are one remeshed
surface so the crotch bends on the plain pants' weights. The story: a tom turkey astronaut; his bubble helmet is the
flying head (claudedocs/harvest_moon_plan.md section 8; the concept: harvest/major_tom_concept.py).
Input : breeches.glb (skullbuck with plain pants, from scripts/skullbuck_cargo_pants.py 'plain'), kept at BREECHES below
Output: <out>/majortom.glb       the skin: a white suit (ribbed elbows + knees, belt, chest unit with LEDs, "TOM" name tape,
                                 mission patch, hose connectors), gloves, moon boots with three talons and a spur, a jetpack
                                 and a 17-feather tail fan rigid on Spine2, a metal neck ring weighted to Neck, and the helmet
                                 (ring + glass bubble + turkey head) 100 % Head with DH_C/DH_F/DH_U marker bones for the
                                 detachable-head hook (hook/head.cpp, unchanged)
        <out>/majortom_head.glb  the helmet + head as one STATIC mesh, origin at DH_C, facing glTF +Z (+Y up), own textures
        The glass is its own material (glTF alphaMode BLEND, alpha 0.16, a blue tint): the first see-through material on a
        skin, unverified on the device. --visor builds the fallback into <out>/visor/: an open visor (an opaque back shell
        with a metal frame round the face opening), no glass.
Run   : blender -b --factory-startup --python scripts/majortom_build.py -- <OUTDIR> [--visor]
Blender axes below: the character faces -Y, its left is +X, up is +Z; the Hips bone is at the origin.
"""
import sys, os, math
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import avatar_common
BREECHES = r"C:\Users\Chris\TribeUE\TribeXR\Scripts\Blender\harvest\majortom\breeches.glb"
avatar_common.SRC = BREECHES
from avatar_common import *
import numpy as np
from mathutils import Vector, Matrix, noise
from mathutils.bvhtree import BVHTree
from mathutils.kdtree import KDTree

ARGS = sys.argv[sys.argv.index('--') + 1:]
VISOR = '--visor' in ARGS
OUT = [a for a in ARGS if not a.startswith('--')][0]
if VISOR: OUT = os.path.join(OUT, 'visor')
os.makedirs(OUT, exist_ok=True)
me, arm = load()
assert me.matrix_world == Matrix.Identity(4) and arm.matrix_world == Matrix.Identity(4)
gi = {g.index: g.name for g in me.vertex_groups}
B = lambda n: Vector(arm.data.bones[n].head_local)
for n in ('Hips', 'Spine2', 'Neck', 'Head', 'LeftEye', 'LeftArm', 'LeftForeArm', 'LeftHand', 'LeftUpLeg', 'LeftLeg', 'LeftFoot', 'LeftToeBase'):
    print("BONE", n, [round(x, 3) for x in B(n)])

# ---------------- classify vertices by dominant bone (as santa_build.py) ----------------
def dom(v):
    if not v.groups: return ''
    g = max(v.groups, key=lambda g: g.weight); return gi[g.group]
D = [dom(v) for v in me.data.vertices]
V = np.array([[v.co.x, v.co.y, v.co.z] for v in me.data.vertices])
HEADB = {'Head', 'LeftEye', 'RightEye'}
ARMB = {'LeftArm', 'RightArm', 'LeftForeArm', 'RightForeArm'}
ishand = lambda d: 'Hand' in d
glove_idx = {i for i, d in enumerate(D) if ishand(d) and V[i, 2] <= -0.075}       # the gloves stay (puffed)
bm0 = bmesh.new(); bm0.from_mesh(me.data); bm0.verts.ensure_lookup_table()
belt_idx, pants_idx = set(), set()
for comp in parts_of(bm0):
    zs = [bm0.verts[i].co.z for i in comp]
    if min(zs) > -0.06 and max(zs) < 0.01 and len(comp) < 1500 and not any(ishand(D[i]) for i in comp): belt_idx |= set(comp)   # the breeches' belt + loops
    elif len(comp) > 2000 and sum(1 for i in comp if 'Leg' in D[i] or D[i] == 'Hips') > 0.9 * len(comp): pants_idx = set(comp)   # cargo.py's plain shell
bm0.free()
remove = set(range(len(D))) - glove_idx
print("REMOVE", len(remove), "of", len(D), "| pants shell", len(pants_idx), "| gloves", len(glove_idx))
torso_src = np.array([i for i, d in enumerate(D) if d not in ARMB and not ishand(d) and d not in HEADB and i not in belt_idx and
                      -0.14 <= V[i, 2] <= 0.57 and not ('Shoulder' in d and V[i, 2] > 0.43) and math.hypot(V[i, 0], V[i, 1]) < 0.30])

# ---------------- radius profiles (as santa_build.py) ----------------
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

# ---------------- geometry helpers (santa_build.py's, plus rounded boxes, oriented balls and limb tubes) ----------------
parts = []    # skinned parts, world coordinates
hparts = []   # head parts, head-local coordinates (origin DH_C); copied into `parts` (+C, Head 100 %) and the static head
def add(name, v, f, kinds, smooth=True, w=None, recalc=True, disc=None, wblend=None, wkeep=None, noleg=None, uvv=None, wv=None, noarm=False, wsmooth=0, dest=None):
    """w: rigid {bone: weight}; wv: per-vertex {bone: weight}; neither: DATA_TRANSFER from skullbuck (then noleg / noarm / wkeep / wblend)"""
    if isinstance(kinds, str): kinds = [kinds] * len(f)
    assert len(kinds) == len(f), name
    (parts if dest is None else dest).append(dict(name=name, v=[Vector(p) for p in v], f=[tuple(x) for x in f], k=list(kinds), smooth=smooth,
                                                  w=w, recalc=recalc, disc=disc, wblend=wblend, wkeep=wkeep, noleg=noleg, uvv=uvv, wv=wv, noarm=noarm, wsmooth=wsmooth))
def hadd(name, v, f, kinds, smooth=True, disc=None, recalc=True):
    add(name, v, f, kinds, smooth=smooth, w={'Head': 1.0}, recalc=recalc, disc=disc, dest=hparts)
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
def fan_caps(verts, faces, rows, first=True, last=True, dz0=0.0, dz1=0.0):
    """close a ring loft with a triangle fan at its first and/or last ring (centre pushed by dz along z)"""
    m = len(rows[0]); n = len(rows)
    if first:
        c = sum(rows[0], Vector()) / m + Vector((0, 0, dz0)); verts.append(c); ci = len(verts) - 1
        faces += [(ci, (k + 1) % m, k) for k in range(m)]
    if last:
        c = sum(rows[-1], Vector()) / m + Vector((0, 0, dz1)); verts.append(c); ci = len(verts) - 1
        faces += [(ci, (n - 1) * m + k, (n - 1) * m + (k + 1) % m) for k in range(m)]
    return verts, faces
def sweep(path, prof, normals=None, closed=False, caps=True, scale=None, lump=0.0, lump_f=60.0, seed=0.0, lift=0.0):
    """Extrude the 2D profile prof [(b, n), ...] along path. Frame: n = the given surface normal (else parallel-transported),
    b = tangent x n. scale: per-point factor on the profile; lump: noise on it."""
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
def oriented_ball(c, ax, radii, nu=8, nv=5, amp=0.0, f=1.0, seed=0.0):
    """an ellipsoid with semi-axes radii along the orthonormal axes ax = (a0, a1, a2), optionally lumpy"""
    sv_, sf_ = uvsphere(nu, nv)
    return [c + (ax[0] * (p.x * radii[0]) + ax[1] * (p.y * radii[1]) + ax[2] * (p.z * radii[2])) *
            (1 + amp * noise.noise(p * f + Vector((seed, 0, 0))) if amp else 1.0) for p in sv_], sf_
def rounded_box(c, half, r, n=4, rot=None):
    """a box with every edge rounded to radius r: a subdivided cube (sine-spaced, so the rounds get the vertices) pushed
    onto the rounded shape; rot (3x3) turns it"""
    bmx = bmesh.new(); bmesh.ops.create_cube(bmx, size=2.0)
    bmesh.ops.subdivide_edges(bmx, edges=bmx.edges[:], cuts=n, use_grid_fill=True)
    inner = [h - r for h in half]; vs = []
    for v in bmx.verts:
        p = Vector([math.sin(v.co[i] * math.pi / 2) * half[i] for i in range(3)])
        q = Vector([max(-inner[i], min(inner[i], p[i])) for i in range(3)]); d = p - q
        p = q + d.normalized() * r if d.length > 1e-9 else p
        vs.append(c + (rot @ p if rot is not None else p))
    fs = [tuple(v.index for v in f.verts) for f in bmx.faces]; bmx.free(); return vs, fs
def dense(ctrl, n):
    """Catmull-Rom through ctrl (list of Vector), n points"""
    P = [ctrl[0]] + list(ctrl) + [ctrl[-1]]; out = []
    for i in range(n):
        s = i / (n - 1) * (len(ctrl) - 1); k = min(int(s), len(ctrl) - 2); t = s - k
        p0, p1, p2, p3 = P[k], P[k + 1], P[k + 2], P[k + 3]
        out.append(0.5 * ((2 * p1) + (-p0 + p2) * t + (2 * p0 - 5 * p1 + 4 * p2 - p3) * t * t + (-p0 + 3 * p1 - 3 * p2 + p3) * t * t * t))
    return out
def sexy(hw, hh, n, k):
    """k points of the superellipse |x/hw|^n + |y/hh|^n = 1, CCW from +x"""
    out = []
    for j in range(k):
        a = 2 * math.pi * j / k; c, s = math.cos(a), math.sin(a)
        out.append((hw * math.copysign(abs(c) ** (2 / n), c), hh * math.copysign(abs(s) ** (2 / n), s)))
    return out
def chain_at(chain):
    """arc lengths of the polyline's joints and t -> (centre, tangent); the tangent blends over +-5 cm round each inner
    joint so the rings don't kink there"""
    L = [0.0]
    for a, b in zip(chain, chain[1:]): L.append(L[-1] + (b - a).length)
    Dn = [(b - a).normalized() for a, b in zip(chain, chain[1:])]
    def at(t):
        i = next((j for j in range(len(Dn)) if t <= L[j + 1]), len(Dn) - 1)
        c = chain[i] + Dn[i] * (t - L[i]); tan = Dn[i]
        for j in range(1, len(Dn)):
            if abs(t - L[j]) < 0.05: w = smoothstep(L[j] - 0.05, L[j] + 0.05, t); tan = (Dn[j - 1] * (1 - w) + Dn[j] * w).normalized()
        return c, tan
    return L, at
def chain_project(P, chain, L):
    """each point's arc position along the chain (its nearest segment; the end segments run on past the chain) + its radial vector"""
    bt = np.zeros(len(P)); bd = np.full(len(P), 1e9); R = np.zeros((len(P), 3))
    for i in range(len(chain) - 1):
        a = np.array(chain[i]); ab = np.array(chain[i + 1]) - a; l2 = float(ab @ ab)
        s = np.clip((P - a) @ ab / l2, -np.inf if i == 0 else 0.0, np.inf if i == len(chain) - 2 else 1.0)
        Q = a + np.outer(s, ab); d = np.linalg.norm(P - Q, axis=1); m = d < bd
        bd[m] = d[m]; bt[m] = L[i] + s[m] * math.sqrt(l2); R[m] = (P - Q)[m]
    return bt, R
def limb(chain, src, ts, ref, nb, rad, win=0.02):
    """horseman_build.py's tube() along a jointed chain: a ring at each arc position in ts, its radius profile the max radius
    of the source verts near it (binned round the chain), smoothed along the limb, then rad(t, prof) -> final radii.
    ref: a direction never parallel to the limb (gives each ring's 0 angle). Returns the rings (lists of Vector) + radii."""
    L, at = chain_at(chain); tv, R = chain_project(V[src], chain, L); profs, last = [], None
    def frame(t):
        c, T = at(t); u = (ref - T * ref.dot(T)).normalized(); return c, T, u, T.cross(u)
    for t in ts:
        c, T, u, v = frame(t); m = np.abs(tv - t) < win
        if m.sum() >= 6:
            Rm = R[m]; th = np.arctan2(Rm @ np.array(v), Rm @ np.array(u)); rr = np.linalg.norm(Rm, axis=1)
            prof = np.zeros(nb); b = ((th + math.pi) / (2 * math.pi) * nb).astype(int) % nb
            for q in range(nb):
                mm = rr[b == q]
                if len(mm): prof[q] = mm.max()
            prof = circ_median(fill(prof), 5)
            for _ in range(2): prof = (np.roll(prof, 1) + 2 * prof + np.roll(prof, -1)) / 4
            last = prof
        profs.append(None if last is None else last.copy())
    first = next(p for p in profs if p is not None); profs = [first if p is None else p for p in profs]
    for _ in range(2):
        pr = [p.copy() for p in profs]
        for k in range(1, len(profs) - 1): profs[k] = (pr[k - 1] + 2 * pr[k] + pr[k + 1]) / 4
    rows, radii = [], []
    for t, prof in zip(ts, profs):
        c, T, u, v = frame(t); r = rad(t, prof); radii.append(r)
        rows.append([c + (u * math.cos(ang(k, nb)) + v * math.sin(ang(k, nb))) * r[k] for k in range(nb)])
    return rows, radii, frame
def stations(t0, t1, step, dense_zones=(), fine=0.004):
    """t0..t1 at step, with fine steps inside each (a, b) of dense_zones (the ribbed joints)"""
    ts, t = [], t0
    while t < t1 - 1e-6:
        ts.append(t); inz = any(a - 1e-6 <= t < b - 1e-6 for a, b in dense_zones); nt = t + (fine if inz else step)
        for a, b in dense_zones:
            if t < a - 1e-6 < nt: nt = a                 # land exactly on the start of a ribbed zone
        t = nt
    ts.append(t1); return ts
def rib(t, tc, half, period, amp):
    """four accordion ridges centred on a joint: peaks at +-period/2 and +-3 period/2"""
    d = t - tc
    if abs(d) >= half: return 0.0
    return amp * (0.5 + 0.5 * math.cos(2 * math.pi * (d / period + 0.5))) ** 1.5 * smoothstep(half, half - 0.005, abs(d))

# ---------------- legs: the suit's leg shape per leg (hip to boot, ribbed at the knee); the pants wear its upper part, the
# lofted tube shows from just above the knee down into the boot ----------------
LEG_NB, LEG_PUFF, KNEE_HALF, Z_TUBE = 24, 0.008, 0.032, -0.34
_LA = np.array([ang(k, LEG_NB) for k in range(LEG_NB)])     # ring angles: 0 = +X
leg_line, leg_fit = {}, {}
for side, sx in (('Left', 1.0), ('Right', -1.0)):
    pU, pK, pA = B(side + 'UpLeg'), B(side + 'Leg'), B(side + 'Foot')
    top = pU + (pU - pK).normalized() * 0.060
    L1 = (pK - top).length; L2 = (pA - pK).length
    t_end = L1 + L2 * (pK.z + 0.865) / (pK.z - pA.z)                     # ends at z -0.865, inside the boot's shaft
    src = np.array([i for i in pants_idx if V[i, 0] * sx > 0 and V[i, 2] < 0.02])
    ts = stations(0.0, t_end, 0.024, [(L1 - KNEE_HALF, L1 + KNEE_HALF)])
    def rad(t, prof, L1=L1, sx=sx):
        if t < L1: lo, hi = 0.088, 0.104 - 0.010 * smoothstep(0.10, L1, t)                           # thigh
        else: lo, hi = 0.078, 0.090 - 0.008 * smoothstep(L1, L1 + 0.30, t)                            # shin (straight into the boot)
        trim = 0.016 * np.maximum(0.0, -sx * np.cos(_LA)) ** 1.5 * (1 - smoothstep(L1 - 0.15, L1 - 0.05, t))   # slimmer inside: the
        return np.clip(prof + LEG_PUFF, lo, hi) - trim + rib(t, L1, KNEE_HALF, 0.016, 0.0055)                    # thighs keep a gap
    rows, radii, frame = limb([top, pK, pA], src, ts, Vector((1, 0, 0)), LEG_NB, rad)
    leg_fit[side] = ([top, pK, pA], ts, radii, frame); leg_line[side] = (pK, pA)
    i0 = next(i for i, row in enumerate(rows) if sum(p.z for p in row) / LEG_NB <= Z_TUBE); rows = rows[i0:]; tts = ts[i0:]
    lv, lf = ring_loft(rows)
    lk = ['RIB' if abs(tts[i] - L1) < KNEE_HALF - 1e-6 and abs(tts[i + 1] - L1) < KNEE_HALF - 1e-6 else 'SUIT' for i in range(len(rows) - 1) for _ in range(LEG_NB)]
    lv, lf = fan_caps(lv, lf, rows, dz0=0.006, dz1=-0.006); lk += ['SUIT'] * (2 * LEG_NB)
    add(f"leg_{side}", lv, lf, lk)
    print("LEG", side, "rings", len(rows), "of", len(ts), "| thigh r %.3f knee %.3f shin %.3f" % (float(radii[len(ts) // 4].mean()), float(radii[min(range(len(ts)), key=lambda i: abs(ts[i] - L1))].mean()),
          float(radii[-2].mean())))
def leg_radius(side, t, a):
    """the suit leg's radius at arc position t and ring angle a (bilinear in the fitted rings and bins)"""
    _, ts, radii, _ = leg_fit[side]; i = min(len(ts) - 2, max(0, int(np.searchsorted(ts, t)) - 1)); s = min(1.0, max(0.0, (t - ts[i]) / (ts[i + 1] - ts[i])))
    fk = ((a + math.pi) / (2 * math.pi) * LEG_NB - 0.5) % LEG_NB; k0 = int(math.floor(fk)) % LEG_NB; k1 = (k0 + 1) % LEG_NB; u = fk - math.floor(fk)
    return (radii[i][k0] * (1 - u) + radii[i][k1] * u) * (1 - s) + (radii[i + 1][k0] * (1 - u) + radii[i + 1][k1] * u) * s

# ---------------- the suit's hips + thighs: one remeshed surface, so the crotch bends on the pants' weights ----------------
# A hips loft (round the body, from under the belt to the crotch, on the plain pants' profile + 2.2 cm) and both thighs (the
# suit leg's rings + 4 mm, down past the tube's top) joined, voxel-remeshed into one surface (cargo.py made the plain pants
# the same way), smoothed, decimated, cut clean at the waist and above the knee, then weighted by DATA_TRANSFER. Lofted
# shorts over two leg tubes tore at the crotch in pose_test; the pants shell itself, reshaped, showed jagged creases (both
# 2026-10-17).
Z_PTOP, Z_PCUT, PANTS_PUFF = 0.004, -0.40, 0.022
Pp = V[np.array(sorted(pants_idx))]
hrings, last = [], None
for z in np.linspace(-0.100, Z_PTOP + 0.012, 10):                 # bottom -> top: outward normals
    s = Pp[np.abs(Pp[:, 2] - z) < 0.010]
    if len(s) >= 10: cy = (s[:, 1].min() + s[:, 1].max()) / 2; last = (cy, profile(s, 0.0, cy, k=7, sm=3))   # (the shell ends at -0.004)
    hrings.append((float(z), 0.0, last[0], last[1] + PANTS_PUFF - 0.007 * smoothstep(-0.035, 0.0, z)))      # tucked inside the torso's hem
hrings = smooth_rings(hrings, 2)
hr = [[Vector((cx + r[k] * math.cos(ang(k)), cy + r[k] * math.sin(ang(k)), z)) for k in range(NBIN)] for z, cx, cy, r in hrings]
pv_, pf_ = ring_loft(hr); pv_, pf_ = fan_caps(pv_, pf_, hr, dz0=-0.012)
for side in ('Left', 'Right'):
    chain, ts, radii, frame = leg_fit[side]; rows = []
    for t, r in zip(ts, radii):
        c, T, u, v = frame(t)
        if -0.44 <= c.z <= -0.03: rows.append([c + (u * math.cos(ang(k, LEG_NB)) + v * math.sin(ang(k, LEG_NB))) * (r[k] + 0.004) for k in range(LEG_NB)])
    lv_, lf_ = ring_loft(rows); lv_, lf_ = fan_caps(lv_, lf_, rows); n0 = len(pv_)
    pv_ += lv_; pf_ += [tuple(i + n0 for i in f) for f in lf_]
mp = bpy.data.meshes.new("pants_tmp"); mp.from_pydata([tuple(q) for q in pv_], [], pf_); mp.update()
op = bpy.data.objects.new("pants_tmp", mp); bpy.context.scene.collection.objects.link(op)
bpy.ops.object.select_all(action='DESELECT'); op.select_set(True); bpy.context.view_layer.objects.active = op
for typ, kw in (('REMESH', dict(mode='VOXEL', voxel_size=0.0075)), ('LAPLACIANSMOOTH', dict(lambda_factor=0.5, iterations=5, use_volume_preserve=True)),
                ('DECIMATE', dict(ratio=0.20))):
    md = op.modifiers.new(typ.lower(), typ)
    for k_, v_ in kw.items(): setattr(md, k_, v_)
    bpy.ops.object.modifier_apply(modifier=md.name)
bmc = bmesh.new(); bmc.from_mesh(mp)
for co, no in (((0, 0, Z_PCUT), (0, 0, 1)), ((0, 0, Z_PTOP), (0, 0, -1))):     # clean cuts: above the knee, under the belt
    bmesh.ops.bisect_plane(bmc, geom=bmc.verts[:] + bmc.edges[:] + bmc.faces[:], plane_co=co, plane_no=no, clear_inner=True)
bmc.verts.index_update()
pants_v = [Vector(v.co) for v in bmc.verts]; pants_f = [tuple(v.index for v in f.verts) for f in bmc.faces]; bmc.free()
bpy.data.objects.remove(op); bpy.data.meshes.remove(mp)
NOLEG_PANTS = (-0.090, -0.022)                       # rigid with the hips down to the belt's bottom edge (Santa lesson), then into the legs
add("leg_pants", pants_v, pants_f, 'SUIT', noleg=NOLEG_PANTS, wsmooth=4)   # softer left/right hand-off across the crotch
print("PANTS remeshed: %d verts, %d faces, z %.3f..%.3f" % (len(pants_v), len(pants_f), min(q.z for q in pants_v), max(q.z for q in pants_v)))

# ---------------- suit torso: one loft from behind the belt up to the neck ring ----------------
T_ = V[torso_src]
Z_HEM, Z_TOP = -0.012, 0.462                         # the hem hides behind the belt (its bottom is at -0.021); the pants run up under it
NECK_RT = 0.127                                      # the top ring tucks under the neck ring (outer r 0.137)
def puff_t(z): return 0.028 + 0.007 * math.exp(-((z - 0.30) / 0.10) ** 2)      # suit thickness, a fuller chest
NA, NH_ = B('Neck'), B('Head')
def neck_c(z):                                       # the Neck bone's line at height z
    t = (z - NA.z) / (NH_.z - NA.z); p = NA.lerp(NH_, t); p.z = z; return p
rings, last = [], None
for z in np.linspace(Z_HEM, Z_TOP, 28):
    s = T_[np.abs(T_[:, 2] - z) < 0.012]
    if len(s) >= 10: cy = (s[:, 1].min() + s[:, 1].max()) / 2; last = (cy, profile(s, 0.0, cy, k=9, sm=4))
    cy, r = last; r = r + puff_t(z)
    w = smoothstep(0.40, Z_TOP, z); r = r * (1 - w) + NECK_RT * w; cy = cy * (1 - w) + neck_c(z).y * w
    rings.append((float(z), 0.0, cy, r))
torso_rings = smooth_rings(rings, 6)
TZ = np.array([r[0] for r in torso_rings]); TCY = np.array([r[2] for r in torso_rings]); TRR = np.array([r[3] for r in torso_rings])
def suit_r(a, z):
    """the torso loft's radius and centre y at azimuth a (from +X, CCW) and height z (bilinear in rings and bins)"""
    z = min(max(z, TZ[0]), TZ[-1]); i = min(len(TZ) - 2, max(0, int(np.searchsorted(TZ, z)) - 1)); t = (z - TZ[i]) / (TZ[i + 1] - TZ[i])
    fk = ((a + math.pi) / (2 * math.pi) * NBIN - 0.5) % NBIN; k0 = int(math.floor(fk)) % NBIN; k1 = (k0 + 1) % NBIN; s = fk - math.floor(fk)
    r0 = TRR[i, k0] * (1 - s) + TRR[i, k1] * s; r1 = TRR[i + 1, k0] * (1 - s) + TRR[i + 1, k1] * s
    return r0 * (1 - t) + r1 * t, TCY[i] * (1 - t) + TCY[i + 1] * t
def suit_pt(a, z, dr=0.0):
    r, cy = suit_r(a, z); return Vector(((r + dr) * math.cos(a), cy + (r + dr) * math.sin(a), z))
tv = [Vector((cx + r[k] * math.cos(ang(k)), cy + r[k] * math.sin(ang(k)), z)) for z, cx, cy, r in torso_rings for k in range(NBIN)]
trows = [tv[i * NBIN:(i + 1) * NBIN] for i in range(len(torso_rings))]
tvv, tf = ring_loft(trows)
NOLEG_TORSO = (-0.045, -0.002)                       # no leg weights at the belt line (Santa lesson): the belt is rigid on the hips
add("suit_torso", tvv, tf, 'SUIT', recalc=False, noleg=NOLEG_TORSO, noarm=True)   # no arm weights either: the sleeves turn at their bearings
suit_bvh = BVHTree.FromPolygons(tvv, tf)
print("TORSO rings", len(torso_rings), "z", round(TZ[0], 3), "..", round(TZ[-1], 3), "| half-width at z 0.2: %.3f, front %.3f, back %.3f" % (
      suit_r(0.0, 0.2)[0], suit_r(-math.pi / 2, 0.2)[0], suit_r(math.pi / 2, 0.2)[0]))
pk_out = 0
for p in pants_v:                                    # the pants' top must stay inside the torso where both are (no z-fight behind the belt)
    if Z_HEM < p.z < Z_PTOP:
        a = math.atan2(p.y - suit_r(0, p.z)[1], p.x); r, cy = suit_r(a, p.z)
        if math.hypot(p.x, p.y - cy) > r - 0.002: pk_out += 1
print("CHECK pants verts at or outside the torso above its hem:", pk_out, "(want 0)")

# ---------------- belt (dark webbing) + buckle, on the hips only ----------------
belt_v = tvv + pants_v
belt_bvh_src = BVHTree.FromPolygons(belt_v, tf + [tuple(i + len(tvv) for i in f) for f in pants_f])   # the belt wraps the torso and the pants' top
def surf(c, a, z):                                   # the outermost surface: cast inward from outside
    d = Vector((math.cos(a), math.sin(a), 0)); o = Vector((c[0], c[1], z)) + d * 0.6
    hit = belt_bvh_src.ray_cast(o, -d, 0.6)
    return (hit[0] if hit[0] is not None else o - d * 0.5), d
NBELT = 64; BZ = (-0.020, -0.010, 0.011, 0.042); BZM = (BZ[0] + BZ[-1]) / 2; Vb, Fb = [], []      # a row at the torso's hem
cyb = suit_r(-math.pi / 2, BZM)[1]; BR = len(BZ) + 2
for k in range(NBELT):
    a = -math.pi + k / NBELT * 2 * math.pi
    for zi, z in enumerate((BZ[0] - 0.001,) + BZ + (BZ[-1] + 0.001,)):
        p, d = surf((0, cyb), a, z); Vb.append(p + d * (-0.002 if zi in (0, BR - 1) else 0.009))
for k in range(NBELT):
    k2 = (k + 1) % NBELT
    for zi in range(BR - 1): Fb.append((k * BR + zi, k2 * BR + zi, k2 * BR + zi + 1, k * BR + zi + 1))
belt_bvh = BVHTree.FromPolygons(Vb, Fb); pokes = []
for p in belt_v:
    if not BZ[0] + 0.002 < p.z < BZ[-1] - 0.002: continue
    d = Vector((p.x, p.y - cyb, 0)); L = d.length; hit = belt_bvh.ray_cast(Vector((0, cyb, p.z)), d / L, 1.0)
    if hit[0] is not None and hit[3] < L: pokes.append((round(math.degrees(math.atan2(d.y, d.x))), round(p.z, 3), round((L - hit[3]) * 1000, 1)))
print("CHECK suit verts poking through the belt:", len(pokes), pokes[:8])
WHIP = ('Hips', 'Spine', 'Spine1')
add("belt", Vb, Fb, 'DARK', recalc=False, wkeep=WHIP)
p, d = surf((0, cyb), -math.pi / 2, BZM); pb = p + d * 0.009; up = Vector((0, 0, 1)); tx = up.cross(d).normalized()
BW, BH, BB = 0.066, 0.054, 0.011
for off, w_, h_ in ((up * (BH / 2 - BB / 2), BW, BB), (-up * (BH / 2 - BB / 2), BW, BB), (tx * (BW / 2 - BB / 2), BB, BH), (-tx * (BW / 2 - BB / 2), BB, BH)):
    add("buckle", *box(pb + off, d, w_, h_, 0.008), 'METAL', smooth=False, wkeep=WHIP)
add("buckle_plate", *box(pb, d, BW - 2 * BB + 0.004, BH - 2 * BB + 0.004, 0.004), 'DARKSTEEL', smooth=False, wkeep=WHIP)

# ---------------- chest unit with LEDs, the TOM name tape, hose connectors ----------------
TORSOB = ('Spine', 'Spine1', 'Spine2')
def on_suit(x, z):
    """the suit's front surface point at (x, z) and its outward normal (a ray from inside the torso along -Y)"""
    hit = suit_bvh.ray_cast(Vector((x, 0.0, z)), Vector((0, -1, 0)), 1.0); n = Vector(hit[1])
    return Vector(hit[0]), (n if n.y < 0 else -n)
p, n = on_suit(0.0, 0.272)
rotm = Vector((0, -1, 0)).rotation_difference(n).to_matrix(); tx = rotm @ Vector((1, 0, 0)); up = rotm @ Vector((0, 0, 1))
cu_c = p + n * (0.030 - 0.013)                       # its back 1.3 cm inside the suit
add("chest_unit", *rounded_box(cu_c, (0.098, 0.030, 0.060), 0.013, 4, rotm), 'RIB', wkeep=TORSOB)
front = cu_c + n * 0.030
add("chest_panel", *box(front + up * 0.006, n, 0.170, 0.090, 0.003, up=up), 'PANEL', smooth=False, wkeep=TORSOB)
for k, kind in enumerate(('LED_R', 'LED_G', 'LED_A', 'LED_G')):
    add("chest_led", *rounded_box(front + tx * (-0.060 + 0.040 * k) + up * 0.026 + n * 0.006, (0.009, 0.005, 0.007), 0.0028, 2, rotm), kind, wkeep=TORSOB)
for sg in (-1, 1):
    c0 = front + tx * (0.058 * sg) - up * 0.020 + n * 0.002
    add("chest_knob", *cyl(c0, c0 + n * 0.012, 0.0125, 14), 'METAL', smooth=False, wkeep=TORSOB)
sc_c = front - up * 0.020 + n * 0.003
SCR_W, SCR_H = 0.056, 0.026
sv_, sf_ = box(sc_c, n, SCR_W, SCR_H, 0.002, up=up)
add("chest_screen", sv_, sf_, 'SCREEN', smooth=False, wkeep=TORSOB, uvv=[(0.5 + (q - sc_c).dot(tx) / SCR_W, 0.5 + (q - sc_c).dot(up) / SCR_H) for q in sv_])
TAPE_W, TAPE_H = 0.150, 0.048
p, n = on_suit(0.0, 0.372)
rotm2 = Vector((0, -1, 0)).rotation_difference(n).to_matrix(); tx2 = rotm2 @ Vector((1, 0, 0)); up2 = rotm2 @ Vector((0, 0, 1))
sv_, sf_ = box(p + n * 0.001, n, TAPE_W, TAPE_H, 0.004, up=up2)
add("name_tape", sv_, sf_, 'TAPE', smooth=False, wkeep=TORSOB, uvv=[(0.5 + (q - p).dot(tx2) / TAPE_W, 0.5 + (q - p).dot(up2) / TAPE_H) for q in sv_])
for xh, kind in ((-0.068, 'NAVY'), (0.068, 'RED')):  # the concept's pair: blue on his right, red on his left
    p, n = on_suit(xh, 0.168)
    add("hose_collar", *cyl(p - n * 0.004, p + n * 0.012, 0.025, 16), 'METAL', smooth=False, wkeep=TORSOB)
    add("hose_conn", *cyl(p + n * 0.010, p + n * 0.034, 0.019, 16), kind, smooth=False, wkeep=TORSOB)
    add("hose_cap", *cyl(p + n * 0.033, p + n * 0.037, 0.012, 12), 'DARKSTEEL', smooth=False, wkeep=TORSOB)

# ---------------- gloves: skullbuck's hands puffed out along welded normals (their own hand + finger weights) ----------------
GLOVE_PUFF = 0.0045
bmg = bmesh.new(); bmg.from_mesh(me.data); bmg.verts.ensure_lookup_table(); bmg.normal_update()
vn = {i: Vector() for i in glove_idx}
for f in bmg.faces:
    if all(v.index in glove_idx for v in f.verts):
        nn = f.normal * f.calc_area()
        for v in f.verts: vn[v.index] += nn
bmg.free()
kd = KDTree(len(glove_idx))
for i in glove_idx: kd.insert(me.data.vertices[i].co, i)
kd.balance()
glove_new = {}
for i in glove_idx:                                  # the hand mesh is split at its UV seams: sum the normals of every copy
    co = Vector(me.data.vertices[i].co); nn = Vector()
    for (_, j, _) in kd.find_range(co, 2e-4): nn += vn[j]
    glove_new[i] = co + (nn.normalized() * GLOVE_PUFF if nn.length > 1e-12 else Vector())

# ---------------- sleeves: shoulder dome to wrist, ribbed at the elbow; metal wrist rings over the gloves ----------------
ARM_NB, ELB_HALF = 20, 0.030
sleeve_bvh = {}
for side, sx in (('Left', 1.0), ('Right', -1.0)):
    pA, pE, pW = B(side + 'Arm'), B(side + 'ForeArm'), B(side + 'Hand')
    L1 = (pE - pA).length; L2 = (pW - pE).length; t_end = L1 + L2 - 0.035
    src = np.array([i for i, d in enumerate(D) if (d == side + 'Arm' and V[i, 2] < 0.46) or d == side + 'ForeArm'])
    ts = stations(0.0, t_end, 0.020, [(L1 - ELB_HALF, L1 + ELB_HALF)])
    def rad(t, prof, L1=L1, t_end=t_end):
        hi = 0.077 - 0.006 * smoothstep(0.0, L1, t) - 0.005 * smoothstep(L1, t_end, t); lo = 0.060 if t < L1 else 0.054
        return np.clip(prof + 0.020, lo, hi) + rib(t, L1, ELB_HALF, 0.015, 0.005)
    rows, radii, frame = limb([pA, pE, pW], src, ts, Vector((0, -1, 0)), ARM_NB, rad)
    c0, T0, u0, v0 = frame(0.0); R0 = radii[0]; Rd = float(R0.mean()) * 0.95
    dome = []                                        # santa_build.py's domed shoulder: rings before the first one
    for fr in (0.98, 0.9, 0.75, 0.55, 0.3):
        rr = R0 * math.sqrt(max(0.0, 1 - fr * fr)) + 0.004
        dome.append([c0 - T0 * (Rd * fr) + (u0 * math.cos(ang(k, ARM_NB)) + v0 * math.sin(ang(k, ARM_NB))) * rr[k] for k in range(ARM_NB)])
    allrows = dome + rows; allts = [-Rd * fr for fr in (0.98, 0.9, 0.75, 0.55, 0.3)] + ts
    sv_, sf_ = ring_loft(allrows); sf_.append(tuple(range(ARM_NB))[::-1])
    sk_ = ['RIB' if abs(allts[i] - L1) < ELB_HALF - 1e-6 and abs(allts[i + 1] - L1) < ELB_HALF - 1e-6 else 'SUIT' for i in range(len(allrows) - 1) for _ in range(ARM_NB)] + ['SUIT']
    # weights by position along the arm, not transferred: the dome + upper arm ride the Arm bone (the dome is centred on the
    # shoulder joint, so it turns in place like a suit's bearing) and the ribbed elbow blends into ForeArm. Transferred weights
    # stretched the puffy dome into a bat-wing with the arms up (2026-10-17).
    wv = []
    for t in allts:
        e = smoothstep(L1 - 0.035, L1 + 0.035, t); wd = {k_: w_ for k_, w_ in ((side + 'Arm', 1 - e), (side + 'ForeArm', e)) if w_ > 1e-6}
        wv += [wd] * ARM_NB
    add(f"sleeve_{side}", sv_, sf_, sk_, recalc=False, wv=wv)
    sleeve_bvh[side] = BVHTree.FromPolygons(sv_, sf_)
    cE, TE, _, _ = frame(t_end)
    add(f"sleeve_cap_{side}", [cE] + rows[-1], [(0, 1 + k, 1 + (k + 1) % ARM_NB) for k in range(ARM_NB)], 'DARK', w={side + 'ForeArm': 1.0}, smooth=False)
    # wrist ring: wide enough for the puffed glove's cuff and the sleeve's end
    a = (pW - pE).normalized(); gl = np.array([glove_new[i] for i in glove_idx if (V[i, 0] > 0) == (sx > 0)]); P = gl - np.array(pE); tg = P @ np.array(a)
    m = (tg > L2 - 0.03) & (tg < L2 + 0.02); rq = np.linalg.norm(P[m] - np.outer(tg[m], np.array(a)), axis=1)
    RW = max(float(np.percentile(rq, 98)) + 0.007, float(radii[-1].mean()) + 0.004)
    add(f"wrist_ring_{side}", *annulus(pE + a * (L2 - 0.058), pE + a * (L2 + 0.010), RW - 0.010, RW, 28), 'METAL', smooth=False, w={side + 'ForeArm': 1.0})
    add(f"wrist_lip_{side}", *annulus(pE + a * (L2 - 0.060), pE + a * (L2 - 0.050), RW - 0.010, RW + 0.004, 28), 'RIB', smooth=False, w={side + 'ForeArm': 1.0})
    print("SLEEVE", side, "L1 %.3f L2 %.3f | r shoulder %.3f elbow %.3f wrist %.3f | glove wrist r %.4f ring r %.4f" % (
          L1, L2, float(radii[0].mean()), float(radii[min(range(len(ts)), key=lambda i: abs(ts[i] - L1))].mean()), float(radii[-1].mean()), float(np.percentile(rq, 98)), RW))
# mission patch high on the left sleeve, facing out
pA, pE = B('LeftArm'), B('LeftForeArm'); a = (pE - pA).normalized(); c = pA + a * 0.085
outd = (Vector((1, 0, 0)) - a * a.x).normalized(); hit = sleeve_bvh['Left'].ray_cast(c, outd, 0.3)
pp = Vector(hit[0]); pn = Vector(hit[1]); pn = pn if pn.dot(outd) > 0 else -pn
pv = (-a - pn * (-a).dot(pn)).normalized(); pu = pv.cross(pn)      # v up the arm, u to the viewer's right (seen from his left)
sv_, sf_, sk_, _ = lathe(pp - pn * 0.002, pn, [(0.041, 0.0), (0.041, 0.0045), (0.0, 0.0045)], 28, ['GOLD', 'PATCH'])
add("mission_patch", sv_, sf_, sk_, smooth=False, w={'LeftArm': 1.0}, disc=(pp, pu, pv, 0.041))

# ---------------- moon boots: a rounded foot, a shaft round the shin, ribbed cuff, sole, three talons, a spur ----------------
Y_HEEL, Y_TOE, Z_SOLE = 0.120, -0.198, -0.951
for side, sx in (('Left', 1.0), ('Right', -1.0)):
    cx = 0.118 * sx; ym, hl = (Y_HEEL + Y_TOE) / 2, (Y_HEEL - Y_TOE) / 2
    ys = [Y_HEEL - (Y_HEEL - Y_TOE) * (0.5 - 0.5 * math.cos(math.pi * i / 17)) for i in range(18)]   # denser at both ends
    rows = []
    for y in ys:
        u = min(0.985, abs(y - ym) / hl); f = (1 - u ** 5) ** 0.2
        top = -0.862 - 0.030 * smoothstep(0.0, -0.17, y); zc = (top + Z_SOLE) / 2
        hw = 0.073 * f ** 0.8; hh = (top - Z_SOLE) / 2 * f ** 0.35
        rows.append([Vector((cx + px, y, zc + pz)) for px, pz in sexy(hw, hh, 2.8, 24)])
    bv_, bf_ = ring_loft(rows); bv_, bf_ = fan_caps(bv_, bf_, rows)
    add(f"boot_{side}", bv_, bf_, 'SUIT')
    pK, pA = leg_line[side]
    def legc(z, pK=pK, pA=pA): t = (z - pK.z) / (pA.z - pK.z); q = pK.lerp(pA, t); q.z = z; return q
    srows = [[legc(z) + Vector((math.cos(2 * math.pi * j / 24), math.sin(2 * math.pi * j / 24), 0)) * r for j in range(24)]
             for z, r in ((-0.935, 0.084), (-0.905, 0.087), (-0.865, 0.089), (-0.830, 0.089), (-0.805, 0.090), (-0.786, 0.091))]
    shv, shf = ring_loft(srows); shv, shf = fan_caps(shv, shf, srows, first=True, last=False)
    add(f"boot_shaft_{side}", shv, shf, 'SUIT')
    cc = legc(-0.787)
    add(f"boot_cuff_{side}", *annulus(cc - Vector((0, 0, 0.014)), cc + Vector((0, 0, 0.012)), 0.084, 0.097, 28), 'RIB', smooth=False, w={side + 'Leg': 1.0})
    ol = [Vector((cx + px, ym + py, 0)) for px, py in sexy(0.073 + 0.009, hl + 0.009, 3.2, 32)]
    sole_rows = [[q + Vector((-(q.x - cx) * 0.05, -(q.y - ym) * 0.03, -0.976)) for q in ol], [q + Vector((0, 0, -0.970)) for q in ol], [q + Vector((0, 0, Z_SOLE + 0.001)) for q in ol]]
    slv, slf = ring_loft(sole_rows); slv, slf = fan_caps(slv, slf, sole_rows)
    add(f"boot_sole_{side}", slv, slf, 'SOLE')
    for k, dx in enumerate((-0.040, 0.0, 0.040)):  # the talons fan out a little; the middle one is the longest
        yaw = math.radians(15) * (k - 1) * sx
        dd = Vector((math.sin(yaw), -math.cos(yaw), -0.10)).normalized(); st = Vector((cx + dx * sx, Y_TOE + 0.050, -0.924))
        Lt = 0.090 if k == 1 else 0.078
        path = [st + dd * (Lt * i / 8) for i in range(9)]
        scl = [1.0, 1.0, 1.0, 0.96, 1.06, 0.94, 0.98, 0.92, 0.80]                          # two knuckles
        add(f"talon_{side}", *sweep(path, ellipse(0.022, 0.019, 10), scale=scl), 'SUIT', w={side + 'ToeBase': 1.0})
        tip = path[-1]
        cl = [tip - dd * 0.010 + dd * (0.042 * i / 6) + Vector((0, 0, -0.022 * (i / 6) ** 2)) for i in range(7)]
        add(f"claw_{side}", *sweep(cl, ellipse(0.0155, 0.0135, 8), scale=[1.0, 0.88, 0.72, 0.55, 0.38, 0.22, 0.06]), 'CLAW', w={side + 'ToeBase': 1.0})
    sb = legc(-0.868) + Vector((0, 0.085, 0))       # the spur, off the back of the shaft
    sp = [sb + Vector((0, 0.052 * i / 6, -0.006 * i / 6 + 0.010 * (i / 6) ** 2)) for i in range(7)]
    add(f"spur_{side}", *sweep(sp, ellipse(0.0145, 0.0125, 8), scale=[1.0, 0.88, 0.72, 0.55, 0.38, 0.22, 0.06]), 'CLAW', w={side + 'Foot': 1.0})

# ---------------- jetpack (PLSS) + the tail fan, rigid on Spine2 ----------------
SP2 = {'Spine2': 1.0}
yb = max(suit_pt(a, z).y for z in np.linspace(0.06, 0.44, 12) for a in np.linspace(math.radians(30), math.radians(150), 25) if abs(suit_pt(a, z).x) <= 0.17)
JP_FRONT = yb - 0.012; JP_BACK = JP_FRONT + 0.170; JP_YC = (JP_FRONT + JP_BACK) / 2
add("jetpack", *rounded_box(Vector((0, JP_YC, 0.236)), (0.180, 0.085, 0.191), 0.040, 5), 'SUIT', w=SP2)        # top at 0.427: under the helmet's swing
add("jetpack_top", *rounded_box(Vector((0, JP_BACK - 0.046, 0.452)), (0.140, 0.042, 0.030), 0.016, 3), 'RIB', w=SP2)
add("jetpack_panel", *rounded_box(Vector((0, JP_BACK + 0.004, 0.250)), (0.135, 0.007, 0.130), 0.010, 3), 'METAL', w=SP2)
for sxj in (-1, 1):
    tv_, tf_, tk_, _ = lathe(Vector((0.100 * sxj, JP_YC, 0.046)), Vector((0, 0, -1)),
                             [(0.024, 0.0), (0.026, 0.012), (0.035, 0.040), (0.050, 0.072), (0.053, 0.080), (0.046, 0.080), (0.033, 0.050), (0.022, 0.020), (0.0, 0.016)], 18,
                             ['DARKSTEEL', 'DARKSTEEL', 'DARKSTEEL', 'METAL', 'METAL', 'GLOW', 'GLOW', 'GLOW'])
    add("thruster", tv_, tf_, tk_, w=SP2)
FAN_Y, FAN_Z = JP_BACK + 0.030, -0.060               # the pivot at the rump, behind and under the pack
add("fan_bracket", *rounded_box(Vector((0, JP_BACK - 0.018, -0.005)), (0.050, 0.028, 0.062), 0.014, 3), 'METAL', w=SP2)
add("fan_hub", *cyl(Vector((0, JP_BACK - 0.012, FAN_Z)), Vector((0, FAN_Y + 0.014, FAN_Z)), 0.064, 28), 'METAL', smooth=False, w=SP2)
add("fan_hub_cap", *cyl(Vector((0, FAN_Y + 0.013, FAN_Z)), Vector((0, FAN_Y + 0.019, FAN_Z)), 0.034, 20), 'DARKSTEEL', smooth=False, w=SP2)
# 17 banded feathers. Their outline is graduated (long in the middle for the halo behind the helmet, 0.75 m at the sides,
# cupped forward toward the tips) because head.cpp's ORBIT ring (r 0.9 m round the hips, DH_C + 10 cm, bob +-8 cm) crosses
# the fan's plane ~0.8 m out to each side: the concept's flat 0.92 m semicircle put the helmet 16.5 cm into the feathers
# (fan_study, 2026-10-17); the clearance is checked below.
FAN_N, FAN_TH, FAN_RTOP, FAN_RSIDE, FAN_CUP = 17, 80.0, 1.00, 0.75, 35.0
FAN_C = Vector((0, FAN_Y, FAN_Z)); fan_names = set()
FV = [0, 0.05, 0.12, 0.22, 0.34, 0.47, 0.60, 0.70, 0.77, 0.83, 0.88, 0.92, 0.955, 0.98, 1.0]
for k in range(FAN_N):
    thd = -FAN_TH + 2 * FAN_TH * k / (FAN_N - 1); th = math.radians(thd)
    R = FAN_RTOP - (FAN_RTOP - FAN_RSIDE) * smoothstep(10, 45, abs(thd)); beta = math.radians(FAN_CUP) * smoothstep(25, 75, abs(thd))
    e = Vector((math.sin(th), 0, math.cos(th))); fw = Vector((0, -1, 0)); bx = Vector((math.cos(th), 0, -math.sin(th)))
    NI = 120; line = [FAN_C + e * 0.06]; tans = [e]
    for i in range(1, NI + 1):                       # the centreline bends forward as v^2
        g = beta * ((i - 0.5) / NI) ** 2; tn = e * math.cos(g) + fw * math.sin(g); line.append(line[-1] + tn * (R / NI)); tans.append(tn)
    lay = 0.0035 if k % 2 else -0.0035               # alternate layers so the overlaps don't fight
    fv, ff, fuv = [], [], []
    for v in FV:
        i = min(NI, int(round(v * NI))); c = line[i]; nrm = tans[i].cross(bx).normalized()
        hw = 0.012 + 0.066 * min(1, v / 0.32) ** 0.7
        if v > 0.84: hw *= math.sqrt(max(0.0, 1 - ((v - 0.84) / 0.16) ** 2))
        if v >= 1.0: fv.append(c + nrm * (lay + 0.002)); fuv.append((0.5, 1.0)); continue
        fv += [c - bx * hw + nrm * lay, c + nrm * (lay + 0.004), c + bx * hw + nrm * lay]; fuv += [(0.0, v), (0.5, v), (1.0, v)]
    nr = len(FV) - 1
    for i in range(nr - 1):
        a_ = i * 3; ff += [(a_, a_ + 1, a_ + 4, a_ + 3), (a_ + 1, a_ + 2, a_ + 5, a_ + 4)]
    tip = len(fv) - 1; a_ = (nr - 1) * 3; ff += [(a_, a_ + 1, tip), (a_ + 1, a_ + 2, tip)]
    add(f"feather_{k:02d}", fv, ff, 'FEATHER', w=SP2, recalc=False, uvv=fuv); fan_names.add(f"feather_{k:02d}")

# ---------------- neck ring (Neck 100 %): the suit's metal collar with a dark recessed top; the helmet docks over it ----------------
NC = neck_c(0.466); NECK_TOP = 0.518
nv_, nf_, nk_, _ = lathe(Vector((NC.x, NC.y, 0.0)), Vector((0, 0, 1)),
                         [(0.118, 0.438), (0.133, 0.442), (0.137, 0.450), (0.137, 0.499), (0.142, 0.503), (0.142, 0.514), (0.136, NECK_TOP), (0.124, NECK_TOP),
                          (0.119, NECK_TOP - 0.005), (0.0, NECK_TOP - 0.005)], 40,
                         ['METAL', 'METAL', 'METAL', 'METAL', 'RIB', 'RIB', 'METAL', 'METAL', 'DARK'])
add("neck_ring", nv_, nf_, nk_, w={'Neck': 1.0}, smooth=False)

# ---------------- the helmet + turkey (head-local: origin = DH_C, the bubble's centre) ----------------
# On the neck ring's axis (the band clears it by 1 cm all round), and high enough that the band (bottom 0.510) rides over the
# sleeves' shoulder domes (tops ~0.507 at the band's radius) instead of through them.
C = Vector((0.0, NC.y, 0.670))
RB, HCUT = 0.200, -0.118
# the helmet ring: from the recessed underside (over the suit's neck ring) round the outside, over the top, across the floor
hv_, hf_, hk_, _ = lathe(Vector((0, 0, 0)), Vector((0, 0, 1)),
                         [(0.0, -0.135), (0.152, -0.135), (0.152, -0.160), (0.171, -0.160), (0.176, -0.155), (0.176, -0.145), (0.171, -0.141), (0.172, -0.125),
                          (0.176, -0.121), (0.176, -0.114), (0.169, -0.110), (0.158, -0.110), (0.150, -0.113), (0.064, -0.113), (0.058, -0.118), (0.0, -0.118)], 48,
                         ['UNDER', 'UNDER', 'METAL', 'METAL', 'METAL', 'RIB', 'RIB', 'METAL', 'METAL', 'METAL', 'METAL', 'METAL', 'FLOOR', 'DARK', 'DARK'])
hadd("helmet_ring", hv_, hf_, hk_, smooth=False)
phi0 = math.acos(HCUT / RB); NBU, NLAT = 40, 18      # the bubble: latitude rings from the cut up to the pole
brows = [[Vector((RB * math.sin(ph) * math.cos(2 * math.pi * j / NBU), RB * math.sin(ph) * math.sin(2 * math.pi * j / NBU), RB * math.cos(ph))) for j in range(NBU)]
         for ph in [phi0 * (1 - i / NLAT) for i in range(NLAT)]]
gv_, gf_ = ring_loft(brows); gv_.append(Vector((0, 0, RB))); pole = len(gv_) - 1
gf_ += [((NLAT - 1) * NBU + j, (NLAT - 1) * NBU + (j + 1) % NBU, pole) for j in range(NBU)]
if not VISOR:
    hadd("glass_bubble", gv_, gf_, 'GLASS', recalc=False)
else:
    bmv = bmesh.new()                                # the fallback: the bubble's back as an opaque shell + a metal frame round the opening
    for p in gv_: bmv.verts.new(p)
    bmv.verts.ensure_lookup_table()
    for f in gf_: bmv.faces.new([bmv.verts[i] for i in f])
    Y_OPEN = -0.015
    bmesh.ops.bisect_plane(bmv, geom=bmv.verts[:] + bmv.edges[:] + bmv.faces[:], plane_co=(0, Y_OPEN, 0), plane_no=(0, 1, 0), clear_inner=True)
    bmv.verts.index_update()
    hadd("visor_shell", [Vector(v.co) for v in bmv.verts], [tuple(v.index for v in f.verts) for f in bmv.faces], 'SUIT', recalc=False); bmv.free()
    r0 = math.sqrt(RB * RB - Y_OPEN * Y_OPEN); a0 = math.asin(HCUT / r0)
    fr = [Vector((r0 * math.cos(a), Y_OPEN, r0 * math.sin(a))) for a in np.linspace(a0, math.pi - a0, 40)]
    hadd("visor_frame", *sweep(fr, ellipse(0.009, 0.007, 8), normals=[Vector((q.x, 0, q.z)) for q in fr]), 'METAL')
# the turkey: a red bare neck with caruncles out of a dark feather ruff, a big pale-blue head, black eyes, a short hooked
# ivory beak, a snood over it and a big red wattle (the concept's head, made to fit 1.2 cm inside the glass)
NECKP = dense([Vector((0, 0.012, -0.114)), Vector((0, 0.004, -0.075)), Vector((0, -0.010, -0.035)), Vector((0, -0.022, 0.005))], 9)
hadd("tk_neck", *sweep(NECKP, ellipse(0.036, 0.034, 12), scale=[1.08 - 0.12 * i / 8 for i in range(9)]), 'REDSKIN')
def neck_at(h):
    i = min(range(len(NECKP)), key=lambda j: abs(NECKP[j].z - h)); return NECKP[i], 0.036 * (1.08 - 0.12 * i / 8)
for j, (az, h, r) in enumerate([(-90, -0.088, 0.012), (-62, -0.080, 0.011), (-118, -0.081, 0.011), (-76, -0.058, 0.010), (-104, -0.060, 0.010),
                                (-32, -0.094, 0.010), (-148, -0.094, 0.010), (-90, -0.038, 0.009), (-46, -0.064, 0.009), (-134, -0.066, 0.009)]):
    q, rn = neck_at(h); dr = Vector((math.cos(math.radians(az)), math.sin(math.radians(az)), 0))
    hadd("tk_caruncle", *lumpy_ball(q + dr * (rn * 0.92), r, 8, 6, 0.22, 140.0, j), 'REDSKIN')
for j in range(12):
    az = 2 * math.pi * j / 12 + 0.13; radial = Vector((math.cos(az), math.sin(az), 0)); upz = Vector((0, 0, 1))
    al = (radial * math.cos(math.radians(38)) + upz * math.sin(math.radians(38))).normalized(); aw = upz.cross(radial).normalized()
    hadd("tk_ruff", *oriented_ball(Vector((0, 0.006, -0.103)) + radial * 0.050 + upz * 0.010, (al, aw, al.cross(aw)), (0.034, 0.018, 0.009), 8, 5, 0.15, 60.0, j), 'BRONZE')
HC_, HR_ = Vector((0.0, -0.028, 0.036)), (0.080, 0.098, 0.074)
sv0, hsf = uvsphere(24, 14)
headv = [HC_ + Vector((p.x * HR_[0] * (1 - 0.10 * max(0.0, -p.y)), p.y * HR_[1], p.z * HR_[2] * (1 - 0.08 * max(0.0, -p.y)))) for p in sv0]   # narrower toward the beak
hadd("tk_head", headv, hsf, 'FACE')
head_bvh = BVHTree.FromPolygons(headv, hsf)
for sg in (-1, 1):
    dv = Vector((sg * 0.62, -0.70, 0.36)).normalized(); pe = Vector(head_bvh.ray_cast(HC_, dv, 1.0)[0]); ec = pe - dv * 0.004
    hadd("tk_eye", *lumpy_ball(ec, 0.0135, 12, 8, 0.0, 1.0, 0.0), 'EYE')
    gd = (dv + Vector((0, -0.35, 0.60))).normalized()
    hadd("tk_eye_glint", *lumpy_ball(ec + gd * 0.0126, 0.0033, 6, 4, 0.0, 1.0, 0.0), 'SPARK')
bp = Vector(head_bvh.ray_cast(HC_, Vector((0, -1, -0.15)).normalized(), 1.0)[0])      # where the beak leaves the face
BEAKP = dense([bp + Vector((0, 0.010, 0.002)), bp + Vector((0, -0.018, -0.002)), bp + Vector((0, -0.036, -0.010)), bp + Vector((0, -0.046, -0.024))], 8)
hadd("tk_beak", *sweep(BEAKP, ellipse(0.021, 0.017, 10), scale=[1.0, 0.95, 0.85, 0.70, 0.52, 0.34, 0.18, 0.05]), 'BEAK')
JAWP = dense([bp + Vector((0, 0.008, -0.012)), bp + Vector((0, -0.016, -0.016)), bp + Vector((0, -0.030, -0.020))], 6)
hadd("tk_jaw", *sweep(JAWP, ellipse(0.015, 0.008, 8), scale=[1.0, 0.9, 0.75, 0.55, 0.32, 0.1]), 'BEAK')
SNOODP = dense([bp + Vector((0, 0.022, 0.044)), bp + Vector((0.002, -0.006, 0.030)), bp + Vector((0.016, -0.026, 0.008)), bp + Vector((0.020, -0.034, -0.022)),
                bp + Vector((0.019, -0.030, -0.052)), bp + Vector((0.017, -0.024, -0.078))], 12)
hadd("tk_snood", *sweep(SNOODP, ellipse(0.0095, 0.0085, 8), scale=[1.0 - 0.3 * i / 11 + 0.15 * (i == 11) for i in range(12)], lump=0.15, lump_f=150, seed=3), 'REDSKIN')
hadd("tk_wattle", *oriented_ball(Vector((0, -0.098, -0.052)), (Vector((1, 0, 0)), Vector((0, 1, 0)), Vector((0, 0, 1))), (0.026, 0.030, 0.056), 12, 10, 0.12, 30.0, 7), 'REDSKIN')
hadd("tk_throat", *oriented_ball(Vector((0, -0.062, -0.022)), (Vector((1, 0, 0)), Vector((0, 1, 0)), Vector((0, 0, 1))), (0.040, 0.034, 0.030), 12, 8, 0.10, 40.0, 8), 'REDSKIN')
for hpart in hparts: add(hpart['name'], [p + C for p in hpart['v']], hpart['f'], hpart['k'], smooth=hpart['smooth'], w=hpart['w'],
                         recalc=hpart['recalc'], disc=(hpart['disc'][0] + C,) + tuple(hpart['disc'][1:]) if hpart['disc'] else None)
HEAD_NAMES = {h['name'] for h in hparts}

# ---------------- checks on the raw geometry ----------------
tk = [p for h in hparts if h['name'].startswith('tk_') for p in h['v']]
print("CHECK turkey inside the glass: farthest vertex %.4f m from DH_C, bubble r %.3f -> clearance %.4f m (want >= 0.010)" % (max(p.length for p in tk), RB, RB - max(p.length for p in tk)))
fanpts = np.array([[p.x, p.y, p.z] for q in parts if q['name'] in fan_names for p in q['v']])
def orbit_clearance(s, bob=0.08, ring=0.9, up=0.10):
    """head.cpp's ORBIT in avatar units (world / s): the helmet centre on a circle of r ring/s round the hips at DH_C.z + up/s,
    bobbing +-bob/s. The circle is round the vertical axis, so the nearest path point to a fan point lies in its azimuth:
    distances live in the (rho, z) half-plane. Bubble = sphere RB about DH_C (head.cpp's +-10 deg roll wobble turns it in
    place); helmet ring = band r 0.176, h -0.160..-0.110, reaching up to 0.160 sin 10 deg further sideways when rolled."""
    rho = np.hypot(fanpts[:, 0], fanpts[:, 1]); z = fanpts[:, 2]; rr = ring / s; zlo, zhi = C.z + (up - bob) / s, C.z + (up + bob) / s
    dz = np.maximum(0, np.maximum(zlo - z, z - zhi)); ds = np.hypot(rho - rr, dz) - RB
    dzr = np.maximum(0, np.maximum((zlo - 0.160) - z, z - (zhi - 0.110))); dr = np.hypot(np.maximum(0, np.abs(rho - rr) - (0.176 + 0.160 * math.sin(math.radians(10)))), dzr)
    i = int(np.argmin(np.minimum(ds, dr))); return float(min(ds.min(), dr.min())), fanpts[i]
for s_ in (1.0, 1.006, 1.06):
    cl, at_ = orbit_clearance(s_)
    print("CHECK ORBIT vs tail fan at avatar scale %.3f: clearance %+.3f m (nearest fan point %s)%s" % (s_, cl, [round(x, 3) for x in at_], "" if cl > 0 else "  <-- GRAZES"))
hw_ = [p + C for h in hparts if h['name'] in ('helmet_ring', 'glass_bubble', 'visor_shell') for p in h['v']]
near_parts = [(q['name'], BVHTree.FromPolygons(q['v'], q['f'])) for q in parts if q['name'].startswith(('jetpack', 'feather', 'fan_', 'sleeve_L', 'sleeve_R'))]
def helmet_gap(pitch=0.0, roll=0.0):
    """the helmet tilted about the Head joint (pitch: face up; roll: toward its left), nearest jetpack/fan/sleeve surface"""
    Rm = Matrix.Rotation(math.radians(-pitch), 3, 'X') @ Matrix.Rotation(math.radians(roll), 3, 'Y'); hj = B('Head'); best = (9.0, '')
    for p in hw_:
        q = hj + Rm @ (p - hj)
        for nm, bv in near_parts:
            hit = bv.find_nearest(q, best[0])
            if hit[0] is not None and hit[3] < best[0]: best = (hit[3], nm)
    return "%.3f m (%s)" % best
print("CHECK helmet to jetpack/fan/sleeves: rest", helmet_gap(), "| pitched up 15 deg", helmet_gap(15), "| 25 deg", helmet_gap(25), "| rolled 15 deg", helmet_gap(0, 15))
print("CHECK helmet ring over the neck ring: radial gap %.3f m (band 0.152 - ring 0.142), underside %.3f m above the ring top, band bottom %.3f m below it" % (
      0.152 - 0.142, (C.z - 0.135) - NECK_TOP, NECK_TOP - (C.z - 0.160)))

# ---------------- texture atlas: free cells + painted patches ----------------
def vnoise(u, v, f, seed):
    g = np.random.default_rng(seed).random((f + 2, f + 2))
    x = np.clip(u, 0, 1) * f; y = np.clip(v, 0, 1) * f; x0 = np.floor(x).astype(int); y0 = np.floor(y).astype(int)
    tx_ = x - x0; ty_ = y - y0; tx_ = tx_ * tx_ * (3 - 2 * tx_); ty_ = ty_ * ty_ * (3 - 2 * ty_)
    return (g[y0, x0] * (1 - tx_) + g[y0, x0 + 1] * tx_) * (1 - ty_) + (g[y0 + 1, x0] * (1 - tx_) + g[y0 + 1, x0 + 1] * tx_) * ty_
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
def suit(c, seed):
    def fn(uu, vv):
        sh = uu.shape; n1 = fbm(uu, vv, 6, seed, 3); n2 = vnoise(uu, vv, 90, seed + 5)
        col = np.array(c) * (0.95 + 0.06 * n1 + 0.025 * n2)[..., None]                  # coated nylon: soft mottling + a fine weave
        return np.clip(col, 0, 1), Z3(sh), 0.78 + 0.06 * n1, np.zeros(sh)
    return fn
def metal(c, rough, seed):
    def fn(uu, vv):
        sh = uu.shape; br = vnoise(uu * 0.05, vv, 120, seed)                          # brushed: streaks along u
        return np.clip(np.array(c) * (0.90 + 0.14 * br)[..., None], 0, 1), Z3(sh), rough + 0.06 * (br - 0.5), np.ones(sh)
    return fn
def led(c, glow=0.9):
    def fn(uu, vv):                                                                    # bright even unlit (avatar glow is unverified)
        sh = uu.shape; return np.clip(np.ones(sh + (3,)) * np.array(c), 0, 1), np.ones(sh + (3,)) * np.array(c) * glow, np.full(sh, 0.25), np.zeros(sh)
    return fn
def bronze(c, seed):
    def fn(uu, vv):
        sh = uu.shape; n = fbm(uu, vv, 14, seed, 3); st = 0.5 + 0.5 * np.sin(2 * np.pi * (uu * 60 + 3 * n))
        col = np.array(c) * (0.75 + 0.35 * n + 0.10 * st)[..., None] + np.array((0.05, 0.06, 0.01)) * (st > 0.85)[..., None]   # iridescent glints
        return np.clip(col, 0, 1), Z3(sh), np.full(sh, 0.45), np.full(sh, 0.25)
    return fn
def redskin(c, seed):
    def fn(uu, vv):
        sh = uu.shape; bumps = vnoise(uu, vv, 70, seed); n = fbm(uu, vv, 8, seed + 3, 2)
        col = np.array(c) * (0.82 + 0.22 * n)[..., None] * (1 - 0.22 * (bumps > 0.70))[..., None]     # pebbly
        return np.clip(col, 0, 1), Z3(sh), 0.40 + 0.12 * bumps, np.zeros(sh)
    return fn
def face(c, seed):
    def fn(uu, vv):
        sh = uu.shape; n = fbm(uu, vv, 10, seed, 3); w = np.clip((vnoise(uu, vv, 26, seed + 4) - 0.55) / 0.3, 0, 1)[..., None]
        col = np.array(c) * (0.92 + 0.12 * n)[..., None]; col = col * (1 - 0.35 * w) + np.array((0.92, 0.95, 1.0)) * 0.35 * w   # pale blue, white mottles
        return np.clip(col, 0, 1), Z3(sh), np.full(sh, 0.50), np.zeros(sh)
    return fn
def glow(uu, vv):
    sh = uu.shape; r = np.hypot(uu - 0.5, vv - 0.5)
    return np.ones(sh + (3,)) * np.array((0.70, 0.30, 0.08)), np.ones(sh + (3,)) * np.array((0.95, 0.38, 0.08)) * 0.55, np.full(sh, 0.6), np.zeros(sh)
FONT = {'T': ["#####", "..#..", "..#..", "..#..", "..#..", "..#..", "..#.."],
        'O': [".###.", "#...#", "#...#", "#...#", "#...#", "#...#", ".###."],
        'M': ["#...#", "##.##", "#.#.#", "#.#.#", "#...#", "#...#", "#...#"]}
def tape_tex(uu, vv):
    """navy name tape, "TOM" in white LED dots (the concept's pixel font), a grey hem"""
    sh = uu.shape; col = np.ones(sh + (3,)) * np.array((0.12, 0.17, 0.40)); emi = Z3(sh)
    ph = 0.62 / 7; pw = ph * TAPE_H / TAPE_W; x0 = 0.5 - 17 * pw / 2; y0 = 0.5 - 3.5 * ph
    for li, ch in enumerate("TOM"):
        for row in range(7):
            for c in range(5):
                if FONT[ch][row][c] != '#': continue
                px0 = x0 + (li * 6 + c) * pw; py0 = y0 + (6 - row) * ph
                m = (uu >= px0 + pw * 0.12) & (uu < px0 + pw * 0.88) & (vv >= py0 + ph * 0.12) & (vv < py0 + ph * 0.88)
                col[m] = (0.97, 0.97, 1.0); emi[m] = (0.55, 0.57, 0.62)
    hem = (uu < 0.02) | (uu > 0.98) | (vv < 0.06) | (vv > 0.94); col[hem] = (0.60, 0.61, 0.65)
    return col, emi, np.full(sh, 0.6), np.zeros(sh)
def screen_tex(uu, vv):
    sh = uu.shape; col = np.ones(sh + (3,)) * np.array((0.02, 0.07, 0.06)); emi = Z3(sh)
    wave = np.abs(vv - (0.5 + 0.28 * np.sin(uu * 2 * np.pi * 2.5) * np.exp(-((uu - 0.5) / 0.3) ** 2))) < 0.06
    col[wave] = (0.30, 1.0, 0.45); emi[wave] = (0.20, 0.75, 0.32)
    col[(uu < 0.06) | (uu > 0.94) | (vv < 0.10) | (vv > 0.90)] = (0.12, 0.13, 0.14)
    return col, emi, np.full(sh, 0.15), np.zeros(sh)
def patch_tex(uu, vv):
    """mission patch: navy field, the harvest moon with an orbit round it, stars, a gold rim"""
    x = uu * 2 - 1; y = vv * 2 - 1; r = np.hypot(x, y); sh = uu.shape
    col = np.ones(sh + (3,)) * np.array((0.07, 0.10, 0.32)); ro = np.full(sh, 0.55); mt = np.zeros(sh)
    moon = np.hypot(x - 0.12, y - 0.10) < 0.36; col[moon] = (0.96, 0.78, 0.40)
    col[moon & (np.hypot(x - 0.24, y - 0.22) < 0.08)] = (0.84, 0.64, 0.30); col[moon & (np.hypot(x + 0.02, y - 0.02) < 0.06)] = (0.86, 0.66, 0.31)
    orbit = np.abs(np.hypot(x / 0.80, (y + 0.02 - 0.25 * x) / 0.30) - 1) < 0.05
    col[orbit & ~(moon & (y + 0.02 - 0.25 * x > 0))] = (0.95, 0.96, 1.0)            # passes behind the moon at the top
    for sx_, sy_ in ((-0.50, 0.42), (-0.22, -0.55), (0.56, -0.40), (-0.62, -0.08), (0.48, 0.56)):
        col[(np.abs(x - sx_) + np.abs(y - sy_)) < 0.065] = (1.0, 1.0, 1.0)
    rim = r > 0.84; col[rim] = (0.93, 0.75, 0.33); mt[rim] = 1.0; ro[rim] = 0.3
    return col, Z3(sh), ro, mt
def feather_tex(uu, vv):
    """a wild turkey's tail feather: dark bronze with fine chevron barring and copper glints, a black subterminal bar,
    a buff tip, an ivory quill; u across (0.5 = the quill), v from the base (0) to the tip (1)"""
    sh = uu.shape; u = np.abs(uu - 0.5) * 2
    bars = 0.5 + 0.5 * np.sin(2 * np.pi * (vv * 30 - 0.8 * u)); sheen = fbm(uu, vv, 6, 41, 2)
    col = np.array((0.34, 0.21, 0.11)) * (0.86 + 0.14 * bars)[..., None] * (0.92 + 0.16 * sheen)[..., None]
    col = col + np.array((0.04, 0.02, 0.0)) * (bars > 0.85)[..., None]
    ro = np.full(sh, 0.45); mt = np.full(sh, 0.22)
    down = np.clip((0.12 - vv) / 0.12, 0, 1)[..., None]; col = col * (1 - down) + np.array((0.56, 0.49, 0.42)) * down
    k_bar = np.clip((vv - 0.735) / 0.015, 0, 1) * np.clip((0.855 - vv) / 0.015, 0, 1)
    col = col * (1 - k_bar[..., None]) + np.array((0.07, 0.055, 0.045)) * k_bar[..., None]
    k_tip = np.clip((vv - 0.845) / 0.02, 0, 1)
    col = col * (1 - k_tip[..., None]) + np.array((0.82, 0.68, 0.47)) * (0.94 + 0.08 * sheen)[..., None] * k_tip[..., None]
    ro = ro * (1 - k_tip) + 0.72 * k_tip; mt = mt * (1 - np.maximum(k_tip, k_bar))
    quill = (u < 0.035 * (1 - 0.6 * np.clip((vv - 0.85) / 0.15, 0, 1))) & (vv < 0.985)
    col[quill] = (0.86, 0.81, 0.69); ro[quill] = 0.5; mt[quill] = 0.0
    return np.clip(col, 0, 1), Z3(sh), ro, mt
SPEC = {   # kind: (painter, cells of 16 px, textured = the UVs use the whole patch)
    'SUIT': (suit((0.88, 0.875, 0.85), 1), 12, False),
    'RIB': (flat((0.63, 0.64, 0.67), 0.62, 0.0, 0.06, 2), 6, False),
    'METAL': (metal((0.80, 0.81, 0.83), 0.26, 3), 6, False),
    'DARKSTEEL': (metal((0.26, 0.26, 0.28), 0.40, 4), 3, False),
    'UNDER': (metal((0.32, 0.32, 0.34), 0.45, 5), 3, False),
    'FLOOR': (metal((0.60, 0.61, 0.64), 0.32, 6), 3, False),
    'DARK': (flat((0.10, 0.10, 0.11), 0.80, 0.0, 0.10, 7), 4, False),
    'SOLE': (flat((0.06, 0.06, 0.065), 0.85, 0.0, 0.12, 8), 3, False),
    'PANEL': (flat((0.20, 0.21, 0.23), 0.50, 0.0, 0.05, 9), 3, False),
    'NAVY': (flat((0.14, 0.22, 0.52), 0.40, 0.0, 0.04, 10), 2, False),
    'RED': (flat((0.80, 0.10, 0.08), 0.40, 0.0, 0.04, 11), 2, False),
    'GOLD': (metal((0.93, 0.74, 0.32), 0.28, 12), 2, False),
    'LED_R': (led((1.0, 0.16, 0.10)), 2, False),
    'LED_G': (led((0.25, 1.0, 0.35)), 2, False),
    'LED_A': (led((1.0, 0.66, 0.12)), 2, False),
    'SPARK': (led((1.0, 1.0, 1.0), 0.8), 2, False),
    'GLOW': (glow, 2, False),
    'CLAW': (flat((0.07, 0.065, 0.06), 0.30, 0.0, 0.08, 13), 2, False),
    'SCREEN': (screen_tex, 4, True),
    'TAPE': (tape_tex, 10, True),
    'PATCH': (patch_tex, 8, True),
    'FEATHER': (feather_tex, 32, True),
    'BRONZE': (bronze((0.30, 0.20, 0.11), 14), 4, False),
    'FACE': (face((0.60, 0.72, 0.94), 15), 6, False),
    'REDSKIN': (redskin((0.80, 0.10, 0.10), 16), 6, False),
    'BEAK': (flat((0.84, 0.78, 0.62), 0.45, 0.0, 0.05, 17), 3, False),
    'EYE': (flat((0.012, 0.012, 0.015), 0.06, 0.0, 0.02, 18), 2, False),
}
GLOVE_C = np.array((0.74, 0.75, 0.77))              # light grey suit gloves (the concept's rib grey)
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
        (ax, ay), (bx_, by), (cx_, cy_) = us[0], us[t], us[t + 1]
        x0 = max(0, int(min(ax, bx_, cx_))); x1 = min(G - 1, int(max(ax, bx_, cx_)))
        y0 = max(0, int(min(ay, by, cy_))); y1 = min(G - 1, int(max(ay, by, cy_)))
        den = (by - cy_) * (ax - cx_) + (cx_ - bx_) * (ay - cy_)
        for yy in range(y0, y1 + 1):
            for xx in range(x0, x1 + 1):
                hit = False
                for px_, py_ in ((xx + .5, yy + .5), (xx, yy), (xx + 1, yy), (xx, yy + 1), (xx + 1, yy + 1)):
                    if abs(den) < 1e-12: hit = True; break
                    l1 = ((by - cy_) * (px_ - cx_) + (cx_ - bx_) * (py_ - cy_)) / den
                    l2 = ((cy_ - ay) * (px_ - cx_) + (ax - cx_) * (py_ - cy_)) / den
                    if l1 >= -0.05 and l2 >= -0.05 and l1 + l2 <= 1.05: hit = True; break
                if hit: occ[yy, xx] = True
o2 = occ.copy(); o2[1:, :] |= occ[:-1, :]; o2[:-1, :] |= occ[1:, :]; o2[:, 1:] |= occ[:, :-1]; o2[:, :-1] |= occ[:, 1:]; occ = o2
print("ATLAS free cells", int((~occ).sum()), "of", G * G)
patch = build_atlas(arrs, occ, G)
def uv_mask(tris, H, W, dil):
    m = np.zeros((H, W), bool)
    for (ax, ay), (bx_, by), (cx_, cy_) in tris:
        ax, bx_, cx_, ay, by, cy_ = ax * W, bx_ * W, cx_ * W, ay * H, by * H, cy_ * H
        den = (by - cy_) * (ax - cx_) + (cx_ - bx_) * (ay - cy_)
        if abs(den) < 1e-9: continue
        x0 = max(0, int(min(ax, bx_, cx_)) - 1); x1 = min(W - 1, int(max(ax, bx_, cx_)) + 1)
        y0 = max(0, int(min(ay, by, cy_)) - 1); y1 = min(H - 1, int(max(ay, by, cy_)) + 1)
        yy, xx = np.mgrid[y0:y1 + 1, x0:x1 + 1] + 0.5
        l1 = ((by - cy_) * (xx - cx_) + (cx_ - bx_) * (yy - cy_)) / den; l2 = ((cy_ - ay) * (xx - cx_) + (ax - cx_) * (yy - cy_)) / den
        m[y0:y1 + 1, x0:x1 + 1] |= (l1 >= -0.02) & (l2 >= -0.02) & (l1 + l2 <= 1.02)
    for _ in range(dil):
        m2 = m.copy(); m2[1:] |= m[:-1]; m2[:-1] |= m[1:]; m2[:, 1:] |= m[:, :-1]; m2[:, :-1] |= m[:, 1:]; m = m2
    return m
gtris = []
for f in bm.faces:
    if all(v.index in glove_idx for v in f.verts):
        us = [(l[uvl].uv.x, l[uvl].uv.y) for l in f.loops]; gtris += [(us[0], us[t], us[t + 1]) for t in range(1, len(us) - 1)]
gm = uv_mask(gtris, 2048, 2048, 1)                   # gloves: light grey, keeping the leather's seams as shading
lum = arrs['color'][gm, :3].mean(axis=1); arrs['color'][gm, :3] = np.clip(GLOVE_C[None] * (0.86 + 1.1 * (lum - np.median(lum)))[:, None], 0, 1)
gmo = uv_mask(gtris, 1024, 1024, 1); arrs['orm'][gmo, 1] = 0.72; arrs['orm'][gmo, 2] = 0.0
print("GLOVE texels", int(gm.sum()))
bm.free()
for k, img in imgs.items():
    img.pixels.foreach_set(arrs[k].ravel()); img.update(); img.pack()
em.pixels.foreach_set(arrs['emissive'].ravel()); em.update(); em.pack()
print("PATCHES", {k: [round(t, 4) for t in v] for k, v in patch.items()})

# ---------------- objects, UVs, weights ----------------
def proj(kind, P, part):
    """(uu, vv) in 0..1 inside the kind's patch for world point P"""
    if kind == 'PATCH' and part['disc']:
        c, u, v, r = part['disc']; d = P - c; return 0.5 + d.dot(u) / (2 * r), 0.5 + d.dot(v) / (2 * r)
    return (P.x + 0.5 + 0.5 * P.y) / 1.2, (P.z + 1.0) / 2.1
def make_obj(part, patch, offset=Vector()):
    m = bpy.data.meshes.new(part['name']); m.from_pydata([tuple(p) for p in part['v']], [], part['f']); m.update()
    o = bpy.data.objects.new(part['name'], m); bpy.context.scene.collection.objects.link(o)
    for p_ in m.polygons: p_.use_smooth = part['smooth']
    uv = m.uv_layers.new(name="UVMap")
    for poly in m.polygons:
        kind = part['k'][poly.index]
        if kind not in patch: continue                   # the glass: no texture, its UVs stay 0
        u0, v0, u1, v1 = patch[kind]; textured = SPEC[kind][2]
        for li in poly.loop_indices:
            vi = m.loops[li].vertex_index
            if textured and part['uvv'] is not None: uu, vv = part['uvv'][vi]
            else: uu, vv = proj(kind, m.vertices[vi].co + offset, part)
            uu = min(1, max(0, uu)); vv = min(1, max(0, vv))
            if textured: uv.data[li].uv = (u0 + (u1 - u0) * uu, v0 + (v1 - v0) * vv)
            else: uv.data[li].uv = (u0 + (u1 - u0) * (0.15 + 0.7 * uu), v0 + (v1 - v0) * (0.15 + 0.7 * vv))
    bmx = bmesh.new(); bmx.from_mesh(m)
    if part['recalc']: bmesh.ops.recalc_face_normals(bmx, faces=bmx.faces)
    for e in bmx.edges:                                  # crisp rims on the hardware, soft everywhere else
        if len(e.link_faces) == 2 and e.calc_face_angle(0) > math.radians(50): e.smooth = False
    bmx.to_mesh(m); bmx.free(); m.update()
    return o
matB = me.data.materials[0]
matG = bpy.data.materials.new('MajorTomGlass'); matG.use_nodes = True; bG = matG.node_tree.nodes['Principled BSDF']
bG.inputs['Base Color'].default_value = (0.80, 0.90, 1.0, 1.0); bG.inputs['Alpha'].default_value = 0.16     # -> glTF alphaMode BLEND, alpha 0.16
bG.inputs['Roughness'].default_value = 0.10; bG.inputs['Metallic'].default_value = 0.0
matG.surface_render_method = 'BLENDED'; matG.use_backface_culling = True                                   # single-sided: no in-mesh sort fights
new = []
for part in parts:
    o = make_obj(part, patch); o.data.materials.append(matG if all(k == 'GLASS' for k in part['k']) else matB); new.append(o)
src = me.copy(); src.data = me.data.copy(); src.name = "wsrc"; bpy.context.scene.collection.objects.link(src); src.modifiers.clear()
sbm = bmesh.new(); sbm.from_mesh(src.data); sbm.verts.ensure_lookup_table()
bmesh.ops.delete(sbm, geom=[v for v in sbm.verts if D[v.index] in HEADB], context='VERTS'); sbm.to_mesh(src.data); sbm.free()
for o, part in zip(new, parts):
    bpy.ops.object.select_all(action='DESELECT'); o.select_set(True); bpy.context.view_layer.objects.active = o
    if part['w']:
        for bn, w in part['w'].items():
            vg = o.vertex_groups.new(name=bn); vg.add(list(range(len(o.data.vertices))), w, 'REPLACE')
        continue
    if part['wv']:
        for vi, wd in enumerate(part['wv']):
            for bn, w in wd.items(): (o.vertex_groups.get(bn) or o.vertex_groups.new(name=bn)).add([vi], w, 'REPLACE')
        continue
    md = o.modifiers.new("dt", 'DATA_TRANSFER'); md.object = src; md.use_vert_data = True
    md.data_types_verts = {'VGROUP_WEIGHTS'}; md.vert_mapping = 'POLYINTERP_NEAREST'
    md.layers_vgroup_select_src = 'ALL'; md.layers_vgroup_select_dst = 'NAME'
    bpy.ops.object.datalayout_transfer(modifier="dt"); bpy.ops.object.modifier_apply(modifier="dt")
    # skullbuck's neck verts carry ~20 % Head (Santa lesson): strip it, or the suit's top would half-collapse while the head flies
    for g in [g for g in o.vertex_groups if g.name in HEADB or (part['noarm'] and ('Arm' in g.name or 'Hand' in g.name))]: o.vertex_groups.remove(g)
    if part['wsmooth']:                              # smooth every weight over the mesh's edges (a softer left/right hand-off)
        nv = len(o.data.vertices); Wm = np.zeros((nv, len(o.vertex_groups)))
        for v in o.data.vertices:
            for g in v.groups: Wm[v.index, g.group] = g.weight
        had = Wm > 0; E_ = np.array([e.vertices[:] for e in o.data.edges]); deg = np.maximum(np.bincount(E_.ravel(), minlength=nv), 1)[:, None]
        for _ in range(part['wsmooth']):
            acc = np.zeros_like(Wm); np.add.at(acc, E_[:, 0], Wm[E_[:, 1]]); np.add.at(acc, E_[:, 1], Wm[E_[:, 0]]); Wm = 0.5 * Wm + 0.5 * acc / deg
        for gi_, g in enumerate(o.vertex_groups):
            for vi in range(nv):
                if Wm[vi, gi_] > 1e-4: g.add([vi], float(Wm[vi, gi_]), 'REPLACE')
                elif had[vi, gi_]: g.remove([vi])
    gN = o.vertex_groups.get('Neck') or o.vertex_groups.new(name='Neck'); gS = o.vertex_groups.get('Spine2') or o.vertex_groups.new(name='Spine2')
    for v in o.data.vertices:
        if sum(g.weight for g in v.groups) < 1e-6: (gN if v.co.z > 0.43 else gS).add([v.index], 1.0, 'REPLACE')
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
SPEC_ALL = SPEC; SPEC = {k: SPEC_ALL[k] for k in sorted({k for h in hparts for k in h['k'] if k in SPEC_ALL}, key=list(SPEC_ALL).index)}
hpatch = build_atlas(harrs, np.zeros((HG, HG), bool), HG)
SPEC = SPEC_ALL
def mkimg(name, a, noncolor=False):
    im = bpy.data.images.new(name, a.shape[1], a.shape[0], alpha=False); im.pixels.foreach_set(a.ravel()); im.update(); im.pack()
    if noncolor: im.colorspace_settings.name = 'Non-Color'
    return im
imC = mkimg('majortom_head_color', harrs['color']); imE = mkimg('majortom_head_emissive', harrs['emissive']); imO = mkimg('majortom_head_orm', harrs['orm'], True)
matS = bpy.data.materials.new('MajorTomHead'); matS.use_nodes = True; nt = matS.node_tree; bsdf = nt.nodes['Principled BSDF']
def texnode(im):
    n_ = nt.nodes.new('ShaderNodeTexImage'); n_.image = im; return n_
nt.links.new(texnode(imC).outputs['Color'], bsdf.inputs['Base Color'])
nt.links.new(texnode(imE).outputs['Color'], bsdf.inputs['Emission Color']); bsdf.inputs['Emission Strength'].default_value = 1.0
sep = nt.nodes.new('ShaderNodeSeparateColor'); nt.links.new(texnode(imO).outputs['Color'], sep.inputs['Color'])
nt.links.new(sep.outputs['Green'], bsdf.inputs['Roughness']); nt.links.new(sep.outputs['Blue'], bsdf.inputs['Metallic'])
hobjs = []
for h in hparts:
    o = make_obj(dict(h, disc=(h['disc'][0] + C,) + tuple(h['disc'][1:]) if h['disc'] else None), hpatch, offset=C); hobjs.append(o)
    o.data.materials.append(matG if all(k == 'GLASS' for k in h['k']) else matS)
bpy.ops.object.select_all(action='DESELECT')
for o in hobjs: o.select_set(True)
bpy.context.view_layer.objects.active = hobjs[0]; bpy.ops.object.join(); st = hobjs[0]; st.name = "MajorTomHead_Static"; st.data.name = "MajorTomHead_Static"
print("STATIC HEAD tris", sum(len(p.vertices) - 2 for p in st.data.polygons), "| materials", [m.name for m in st.data.materials])
ntB = matB.node_tree; bB = ntB.nodes['Principled BSDF']     # emissive on the body material too
tEB = ntB.nodes.new('ShaderNodeTexImage'); tEB.image = em; ntB.links.new(tEB.outputs['Color'], bB.inputs['Emission Color']); bB.inputs['Emission Strength'].default_value = 1.0

# ---------------- delete the old body (the gloves stay, puffed), join, DH bones, export ----------------
for i, co in glove_new.items(): me.data.vertices[i].co = co
tri = lambda o: sum(len(p.vertices) - 2 for p in o.data.polygons)
groups = {}
for o, part in zip(new, parts):
    nm = part['name']
    g = 'helmet + turkey' if nm in HEAD_NAMES else 'tail fan' if nm.startswith(('feather', 'fan_')) else 'jetpack' if nm.startswith(('jetpack', 'thruster')) else \
        'boots' if nm.startswith(('boot', 'talon', 'claw', 'spur')) else 'legs' if nm.startswith('leg') else 'sleeves + wrists' if nm.startswith(('sleeve', 'wrist', 'mission')) else \
        'suit torso + kit'
    groups[g] = groups.get(g, 0) + tri(o)
bpy.ops.object.select_all(action='DESELECT'); bpy.context.view_layer.objects.active = me; me.select_set(True)
bpy.ops.object.mode_set(mode='EDIT'); bpy.ops.mesh.select_mode(type='VERT'); bpy.ops.mesh.select_all(action='DESELECT'); bpy.ops.object.mode_set(mode='OBJECT')
for v in me.data.vertices: v.select = v.index in remove
before = len(me.data.vertices)
bpy.ops.object.mode_set(mode='EDIT'); bpy.ops.mesh.delete(type='VERT'); bpy.ops.object.mode_set(mode='OBJECT')
print("DELETED", before - len(me.data.vertices), "expected", len(remove))
groups['gloves (kept, puffed)'] = tri(me)
for o in new: o.select_set(True)
me.select_set(True); bpy.context.view_layer.objects.active = me; bpy.ops.object.join()
glass = [me.data.materials[p.material_index] == matG for p in me.data.polygons]
me.data.materials.clear(); me.data.materials.append(matB)
if any(glass): me.data.materials.append(matG)
for p_, g_ in zip(me.data.polygons, glass): p_.material_index = 1 if g_ else 0
print("TRIS by group", groups)
print("FINAL tris", tri(me), "| materials", [m.name for m in me.data.materials], "| glass tris", sum(len(p.vertices) - 2 for p, g_ in zip(me.data.polygons, glass) if g_))
gidx = {g.name: g.index for g in me.vertex_groups}
hw = [next((g.weight for g in v.groups if g.group == gidx['Head']), 0.0) for v in me.data.vertices]
nw = [next((g.weight for g in v.groups if g.group == gidx['Neck']), 0.0) for v in me.data.vertices]
handg = {gidx[n] for n in gidx if 'Hand' in n}
print("CHECK verts with partial Head weight:", sum(1 for w in hw if 1e-4 < w < 0.9999), "(want 0) | Head 100 %:", sum(1 for w in hw if w >= 0.9999),
      "| Neck 100 %:", sum(1 for w in nw if w >= 0.9999),
      "| with any Hand weight:", sum(1 for v in me.data.vertices if any(g.group in handg and g.weight > 1e-4 for g in v.groups)), "(the gloves:", len(glove_idx), ")")

bpy.ops.object.select_all(action='DESELECT'); arm.select_set(True); bpy.context.view_layer.objects.active = arm
bpy.ops.object.mode_set(mode='EDIT')
eb = arm.data.edit_bones; headb = eb['Head']; inv = arm.matrix_world.inverted()
for name, off in (('DH_C', Vector((0, 0, 0))), ('DH_F', Vector((0, -0.10, 0))), ('DH_U', Vector((0, 0, 0.10)))):
    b = eb.new(name); b.head = inv @ (C + off); b.tail = b.head + Vector((0, 0, 0.02)); b.parent = headb; b.use_connect = False; b.use_deform = False
bpy.ops.object.mode_set(mode='OBJECT')
print("DH bones", {b.name: [round(x, 4) for x in b.head_local] for b in arm.data.bones if b.name.startswith('DH_')})

bpy.ops.object.select_all(action='DESELECT'); me.select_set(True); arm.select_set(True)
bpy.ops.export_scene.gltf(filepath=os.path.join(OUT, "majortom.glb"), export_format='GLB', use_selection=True, export_animations=False)
bpy.ops.object.select_all(action='DESELECT'); st.select_set(True)
bpy.ops.export_scene.gltf(filepath=os.path.join(OUT, "majortom_head.glb"), export_format='GLB', use_selection=True, export_animations=False)
print("EXPORTED", OUT)
