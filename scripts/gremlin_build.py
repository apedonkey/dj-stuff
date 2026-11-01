"""GREMLIN, the RED EYE character (claudedocs/redeye_plan.md section 8), from skullbuck's rigged body, built the way
scripts/santa_build.py and scripts/horseman_build.py built theirs: the old body is deleted and replaced by procedural
parts lofted from its radius profiles, weighted with DATA_TRANSFER from the original where cloth should follow the body
and rigidly where a part must not stretch (bony limbs with ball joints, the head, the belt, the scarf), painted into a
fresh copy of skullbuck's texture atlas. Only skullbuck's cargo-pants shell survives (with its pockets, flaps, knee
patches and snaps), re-UVed olive and cut off at mid-shin.
The character: the RAF folklore saboteur who lives in the hangar. A wiry grey-green creature in torn olive flight-line
coveralls (GREMLIN name tape, a zip, a chest pocket with a screwdriver, sleeves torn above the elbow, legs rolled to
mid-shin, RED EYE nose art on the back), a tool belt (pouches, a wrench), a red pilot's scarf with its tails thrown back
over the left shoulder, skinny bare arms and shins, three long clawed fingers and a thumb, clawed bare feet; a leather
flying helmet with goggles pushed up, huge bat ears through its slits, angry brows, a hooked nose, a needle grin and big
red slit-pupil eyes.
Input : skins/skullbuck.glb (read only)
Output: <out>/gremlin.glb       the skin. The head is skinned 100 % to Head, with DH_C/DH_F/DH_U marker bones for the
                                detachable-head hook (hook/head.cpp); a brass threaded socket on the neck stump (Neck
                                100 %) sits inside the head while it is on and shows when it flies. The three fingers
                                ride skullbuck's finger bones (the third takes Ring + Pinky, half each), so posed fingers
                                still work with the controllers.
        <out>/gremlin_head.glb  the flying copy of the head: a STATIC mesh, origin at DH_C, facing glTF +Z (+Y up), its
                                own textures, plus what the attached head lacks: a threaded bolt and a hex nut under the
                                neck and a propeller on the helmet's crown (two blades + a see-through blur disc, r 0.17 m,
                                on its own alphaMode BLEND material)
Run   : blender -b --factory-startup --python scripts/gremlin_build.py -- <OUTDIR> [--no-blur]
        --no-blur: the plan's fallback head (the two blades only, all opaque)
Blender axes below: the character faces -Y, its left is +X, up is +Z; the Hips bone is at the origin.
"""
import sys, os, math
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import avatar_common
avatar_common.SRC = os.path.normpath(os.path.join(HERE, '..', 'skins', 'skullbuck.glb'))
from avatar_common import *
import numpy as np
from mathutils import Vector, Matrix, noise
from mathutils.bvhtree import BVHTree

ARGS = sys.argv[sys.argv.index('--') + 1:]
OUT = ARGS[0]
NO_BLUR = '--no-blur' in ARGS
os.makedirs(OUT, exist_ok=True)
me, arm = load()
assert me.matrix_world == Matrix.Identity(4) and arm.matrix_world == Matrix.Identity(4)
gi = {g.index: g.name for g in me.vertex_groups}
B = lambda n: Vector(arm.data.bones[n].head_local)
BT = lambda n: Vector(arm.data.bones[n].tail_local)
for n in ('Hips', 'Spine2', 'Neck', 'Head', 'LeftEye', 'LeftArm', 'LeftForeArm', 'LeftHand', 'LeftLeg', 'LeftFoot', 'LeftToeBase'):
    print("BONE", n, [round(x, 3) for x in B(n)])

# ---------------- classify skullbuck: only the cargo-pants shell and its pads survive ----------------
def dom(v):
    if not v.groups: return ''
    g = max(v.groups, key=lambda g: g.weight); return gi[g.group]
D = [dom(v) for v in me.data.vertices]
V = np.array([[v.co.x, v.co.y, v.co.z] for v in me.data.vertices])
HEADB = {'Head', 'LeftEye', 'RightEye'}
ARMB = {'LeftArm', 'RightArm', 'LeftForeArm', 'RightForeArm'}
LEGB = {'Hips', 'LeftUpLeg', 'RightUpLeg', 'LeftLeg', 'RightLeg'}
ishand = lambda d: 'Hand' in d
bm0 = bmesh.new(); bm0.from_mesh(me.data); bm0.verts.ensure_lookup_table()
comps = parts_of(bm0); bm0.free()
shell = max(comps, key=len)
assert sum(1 for i in shell if D[i] in LEGB) > 0.95 * len(shell) and V[shell, 2].max() < 0.0, "the biggest part is not the pants shell"
Z_CUT = -0.625                                       # the trousers end here (mid-shin), under a rolled cuff
keep_kind, belt_idx = {}, set()                      # surviving vertex -> its paint kind
for comp in comps:
    zs = V[comp, 2]; zl, zh = zs.min(), zs.max()
    if zl > -0.06 and zh < 0.012 and len(comp) < 1500 and not any(ishand(D[i]) for i in comp): belt_idx |= set(comp); continue
    if comp is shell: kind = 'SUIT'
    else:
        legf = sum(1 for i in comp if D[i] in LEGB) / len(comp)
        if not (legf >= 0.9 and len(comp) <= 80 and zh < 0.012 and zl > -0.745 and zh > -0.62 and np.abs(V[comp, 0]).max() < 0.25): continue
        if zl > -0.445 and zh < -0.40: continue      # the thigh straps and their buckles go
        kind = 'BRASS' if len(comp) <= 8 else 'PATCH' if zl < -0.5 else 'SUIT_DARK' if zh - zl < 0.06 else 'SUIT'   # snaps, knee patches, flaps, pockets
    for i in comp: keep_kind[i] = kind
for i in shell:
    if V[i, 2] < Z_CUT: del keep_kind[i]
remove = set(range(len(V))) - set(keep_kind)
print("KEEP", len(keep_kind), "of", len(V), "| kinds", {k: sum(1 for x in keep_kind.values() if x == k) for k in set(keep_kind.values())})
torso_src = np.array([i for i, d in enumerate(D) if d not in ARMB and not ishand(d) and d not in HEADB and i not in belt_idx and
                      -0.10 <= V[i, 2] <= 0.57 and not ('Shoulder' in d and V[i, 2] > 0.43) and math.hypot(V[i, 0], V[i, 1]) < 0.30])

# ---------------- radius profiles (as santa_build.py) ----------------
NBIN = 48
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

# ---------------- geometry helpers (santa_build.py's, plus tube / cone / ell) ----------------
parts = []    # skinned parts, world coordinates
hparts = []   # head parts, head-local coordinates (origin DH_C); copied into `parts` (+C, Head 100 %) and the static head
fparts = []   # the flying copy's extras (bolt, nut, propeller), head-local; static head only
def add(name, v, f, kinds, smooth=True, w=None, recalc=True, frame=None, wblend=None, wkeep=None, noleg=None, dest=None, head=False):
    if isinstance(kinds, str): kinds = [kinds] * len(f)
    assert len(kinds) == len(f), name
    (parts if dest is None else dest).append(dict(name=name, v=[Vector(p) for p in v], f=[tuple(x) for x in f], k=list(kinds), smooth=smooth,
                                                  w=w, recalc=recalc, frame=frame, wblend=wblend, wkeep=wkeep, noleg=noleg, head=head))
def hadd(name, v, f, kinds, smooth=True, frame=None, recalc=True, dest=None):
    add(name, v, f, kinds, smooth=smooth, w={'Head': 1.0}, recalc=recalc, frame=frame, dest=hparts if dest is None else dest, head=True)
def compact(verts, faces):
    used = sorted({i for f in faces for i in f}); remap = {o: n for n, o in enumerate(used)}
    return [verts[i] for i in used], [tuple(remap[i] for i in f) for f in faces]
def uvsphere(nu, nv):
    bmx = bmesh.new(); bmesh.ops.create_uvsphere(bmx, u_segments=nu, v_segments=nv, radius=1.0); bmx.verts.ensure_lookup_table()
    vs = [Vector(v.co) for v in bmx.verts]; fs = [tuple(v.index for v in f.verts) for f in bmx.faces]; bmx.free(); return vs, fs
def ring_loft(rows, cap_start=False, cap_end=False):
    """closed rings of equal length (first -> last); CCW rings going up/along give outward normals"""
    n, m = len(rows), len(rows[0]); verts = [p for row in rows for p in row]; faces = []
    for i in range(n - 1):
        for j in range(m):
            j2 = (j + 1) % m; faces.append((i * m + j, i * m + j2, (i + 1) * m + j2, (i + 1) * m + j))
    if cap_start: faces.append(tuple(range(m))[::-1])
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
def rect(hw, ht): return [(-hw, -ht), (hw, -ht), (hw, ht), (-hw, ht)]
def cyl(p0, p1, r, nseg=12, caps=True):
    a = (p1 - p0).normalized(); u = a.orthogonal().normalized(); v = a.cross(u); verts = []
    for p in (p0, p1):
        for j in range(nseg):
            th = 2 * math.pi * j / nseg; verts.append(p + (u * math.cos(th) + v * math.sin(th)) * r)
    faces = [(j, (j + 1) % nseg, nseg + (j + 1) % nseg, nseg + j) for j in range(nseg)]
    if caps: faces += [tuple(range(nseg))[::-1], tuple(range(nseg, 2 * nseg))]
    return verts, faces
def tube(p0, p1, r0, r1, nseg=8, mid=0.0, squash=1.0, up=None):
    """a closed tapered tube p0 -> p1 with a bulge `mid` at its middle; squash < 1 flattens it along `up`"""
    a = (p1 - p0).normalized()
    if up is None: u = a.orthogonal().normalized()
    else: u = (up - a * up.dot(a)).normalized()
    v = a.cross(u).normalized(); verts = []
    for t, r in ((0.0, r0), (0.5, (r0 + r1) / 2 * (1 + mid)), (1.0, r1)):
        c = p0.lerp(p1, t)
        for j in range(nseg):
            th = 2 * math.pi * j / nseg; verts.append(c + (u * (math.cos(th) * squash) + v * math.sin(th)) * r)
    faces = [(i * nseg + j, i * nseg + (j + 1) % nseg, (i + 1) * nseg + (j + 1) % nseg, (i + 1) * nseg + j) for i in range(2) for j in range(nseg)]
    faces += [tuple(range(nseg))[::-1], tuple(range(2 * nseg, 3 * nseg))]
    return verts, faces
def cone(base, tip, r, nseg=6):
    a = (tip - base).normalized(); u = a.orthogonal().normalized(); v = a.cross(u)
    verts = [base + (u * math.cos(2 * math.pi * j / nseg) + v * math.sin(2 * math.pi * j / nseg)) * r for j in range(nseg)] + [tip]
    return verts, [(j, (j + 1) % nseg, nseg) for j in range(nseg)] + [tuple(range(nseg))[::-1]]
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
def lathe(c, axis, prof, nseg, kinds, u=None):
    """revolve prof [(r, h), ...] around axis through c (h along the axis); kinds[i] for the band prof[i] -> prof[i+1]"""
    axis = axis.normalized(); u = axis.orthogonal().normalized() if u is None else (u - axis * u.dot(axis)).normalized(); v = axis.cross(u)
    verts, idx = [], []
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
def ell(c, rr, nu, nv, lump=0.0, f=3.0, seed=0.0):
    sv_, sf_ = uvsphere(nu, nv)
    return [c + Vector((p.x * rr.x, p.y * rr.y, p.z * rr.z)) * (1 + lump * noise.noise(p * f + Vector((seed, 0, 0)))) for p in sv_], sf_
def dense(ctrl, n):
    """Catmull-Rom through ctrl (list of Vector), n points"""
    P = [ctrl[0]] + list(ctrl) + [ctrl[-1]]; out = []
    for i in range(n):
        s = i / (n - 1) * (len(ctrl) - 1); k = min(int(s), len(ctrl) - 2); t = s - k
        p0, p1, p2, p3 = P[k], P[k + 1], P[k + 2], P[k + 3]
        out.append(0.5 * ((2 * p1) + (-p0 + p2) * t + (2 * p0 - 5 * p1 + 4 * p2 - p3) * t * t + (-p0 + 3 * p1 - 3 * p2 + p3) * t * t * t))
    return out
def merged(names, src):
    vs, fs = [], []
    for q in src:
        if q['name'] in names: fs += [tuple(i + len(vs) for i in f) for f in q['f']]; vs += q['v']
    return vs, fs
def front_hit(bvh, x, z):
    hit = bvh.ray_cast(Vector((x, -0.5, z)), Vector((0, 1, 0)), 1.0)
    n = Vector(hit[1])
    if n.y > 0: n = -n
    return Vector(hit[0]), n
def rot_z(v, a): c, s = math.cos(a), math.sin(a); return Vector((v.x * c - v.y * s, v.x * s + v.y * c, v.z))

# ---------------- coverall torso: one loft from under the belt to the neckline ----------------
T_ = V[torso_src]
Z_HEM, Z_TOP = -0.050, 0.468                         # the hem hides under the tool belt (z -0.058 .. -0.006)
NECKLINE_R = 0.080
NA, NH_ = B('Neck'), B('Head')
def neck_c(z):                                       # the Neck bone's line at height z
    t = (z - NA.z) / (NH_.z - NA.z); p = NA.lerp(NH_, t); p.z = z; return p
rings, last = [], None
for z in np.linspace(Z_HEM, Z_TOP, 31):
    s = T_[np.abs(T_[:, 2] - z) < 0.012]
    if len(s) >= 10: cy = (s[:, 1].min() + s[:, 1].max()) / 2; last = (cy, profile(s, 0.0, cy, k=9, sm=4) + 0.014)
    cy, r = last
    w = smoothstep(0.41, Z_TOP, z)                   # shoulder slope -> neckline
    rings.append((float(z), 0.0, cy * (1 - w) + neck_c(z).y * w, r * (1 - w) + NECKLINE_R * w))
torso_rings = smooth_rings(rings, 8)
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
print("TORSO rings", len(torso_rings), "z", round(TZ[0], 3), "..", round(TZ[-1], 3), "| r front/side at chest",
      round(coat_r(-math.pi / 2, 0.30)[0], 3), round(coat_r(0.0, 0.30)[0], 3))
# the RED EYE nose art is painted on the back's faces in this window (a textured kind, projected from behind)
ART_X, ART_Z0, ART_Z1 = 0.150, 0.130, 0.420
tv = []
for z, cx, cy, r in torso_rings:
    for k in range(NBIN): tv.append(Vector((cx + r[k] * math.cos(ang(k)), cy + r[k] * math.sin(ang(k)), z)))
nR = len(torso_rings); tq, tk = [], []
for i in range(nR - 1):
    for k in range(NBIN):
        a_ = i * NBIN + k; b_ = i * NBIN + (k + 1) % NBIN; tq.append((a_, b_, b_ + NBIN, a_ + NBIN))
        c = sum((tv[j] for j in tq[-1]), Vector()) / 4
        tk.append('NOSEART' if (c.y > 0.02 and abs(c.x) < ART_X + 0.012 and ART_Z0 - 0.01 < c.z < ART_Z1 + 0.01) else 'SUIT')
print("NOSE ART faces", tk.count('NOSEART'))
NOLEG_ALL = (-0.20, -0.19)                           # no thigh weight anywhere on the torso: the belt (rigid Hips) covers its hem
add("coat_torso", tv, tq, tk, recalc=False, noleg=NOLEG_ALL)
# turned-up collar: an open band from just outside the shoulders' slope, flaring up round the neck
crows = []
for z, dr in ((0.446, 0.004), (0.462, 0.008), (0.480, 0.013), (0.496, 0.019), (0.506, 0.024)):
    crows.append([coat_pt(ang(k, 40), min(z, Z_TOP), dr) + Vector((0, 0, z - min(z, Z_TOP) + 0.004 * math.sin(ang(k, 40)) * smoothstep(0.47, 0.51, z)))
                  for k in range(40)])
cv_, cf_ = ring_loft(crows)
add("collar", cv_, cf_, ['SUIT'] * (len(cf_) - 40) + ['SUIT_DARK'] * 40, recalc=False)
add("collar_rim", *sweep(crows[-1] + crows[-1][:1], ellipse(0.0040, 0.0032, 6), normals=[Vector((p.x, p.y - neck_c(p.z).y, 0.6)) for p in crows[-1] + crows[-1][:1]],
                         caps=False), 'SUIT_DARK')
# a dark yoke closing the neckline round the neck: without it you look down past the scarf at the inside of the back (and its art)
top = tv[(nR - 1) * NBIN:]; nc_ = neck_c(Z_TOP - 0.004)
inner = [nc_ + Vector((p.x - nc_.x, p.y - nc_.y, 0)).normalized() * 0.0395 for p in top]
add("neck_yoke", top + inner, [(k, NBIN + k, NBIN + (k + 1) % NBIN, (k + 1) % NBIN) for k in range(NBIN)], 'CAVITY', recalc=False)

# ---------------- coverall details: zip, chest pocket + screwdriver, name tape ----------------
zs_ = np.linspace(0.452, -0.006, 26)
zp = [coat_pt(-math.pi / 2, z) for z in zs_]; zn = [coat_n(-math.pi / 2, z) for z in zs_]
add("zip_tape", *sweep(zp, rect(0.0080, 0.0016), normals=zn, lift=0.0022), 'SUIT_DARK', smooth=False)
add("zip_teeth", *sweep(zp, rect(0.0030, 0.0012), normals=zn, lift=0.0042), 'STEEL', smooth=False)
p, n = coat_pt(-math.pi / 2, 0.405, 0.007), coat_n(-math.pi / 2, 0.405)
add("zip_slider", *box(p, n, 0.013, 0.016, 0.006), 'BRASS', smooth=False)
add("zip_pull", *box(p + n * 0.004 - Vector((0, 0, 0.018)), n, 0.008, 0.024, 0.003), 'BRASS', smooth=False)
def pad(name, a_c, half, z0, z1, h, bulge, nu, nv, kind, frame=False):
    """a raised patch on the torso loft: border sunk 2 mm under the surface, the inside lifted h (+ a bulge)"""
    r_ = coat_r(a_c, (z0 + z1) / 2)[0]; da = half / r_; U, W = nu + 2, nv + 2; Vp = []
    for j in range(W):
        for i in range(U):
            ui = min(max(i - 0.5, 0), nu - 1) / (nu - 1); vj = min(max(j - 0.5, 0), nv - 1) / (nv - 1)
            border = i in (0, U - 1) or j in (0, W - 1)
            Vp.append(coat_pt(a_c - da + 2 * da * ui, z0 + (z1 - z0) * vj, -0.002 if border else h + bulge * math.sin(math.pi * ui) * math.sin(math.pi * vj)))
    Fp = [(j * U + i, j * U + i + 1, (j + 1) * U + i + 1, (j + 1) * U + i) for j in range(W - 1) for i in range(U - 1)]
    fr = None
    if frame:
        c = coat_pt(a_c, (z0 + z1) / 2, h); tu = (coat_pt(a_c + 0.01, (z0 + z1) / 2) - coat_pt(a_c - 0.01, (z0 + z1) / 2)).normalized()
        fr = (c, tu, Vector((0, 0, 1)), half, (z1 - z0) / 2)
    add(name, Vp, Fp, kind, recalc=False, frame=fr)
A_POCKET, A_TAPE = -math.pi / 2 + math.radians(33), -math.pi / 2 - math.radians(33)     # left chest (+X), right chest
pad("chest_pocket", A_POCKET, 0.043, 0.270, 0.352, 0.006, 0.003, 6, 6, 'SUIT')
pad("chest_flap", A_POCKET, 0.046, 0.336, 0.366, 0.010, 0.002, 6, 2, 'SUIT_DARK')
p, n = coat_pt(A_POCKET, 0.351, 0.013), coat_n(A_POCKET, 0.351)
add("pocket_snap", *cyl(p, p + n * 0.004, 0.0045, 8), 'BRASS', smooth=False)
a_sd = A_POCKET + 0.020 / coat_r(A_POCKET, 0.33)[0]   # a screwdriver behind the flap
s0, s1 = coat_pt(a_sd, 0.330, 0.012), coat_pt(a_sd, 0.398, 0.014)
add("screwdriver_handle", *tube(s0, s1, 0.0068, 0.0060, 8), 'SCARF')
add("screwdriver_ferrule", *cyl(s1, s1 + (s1 - s0).normalized() * 0.005, 0.0042, 8), 'STEEL', smooth=False)
add("screwdriver_shaft", *cyl(s1, s1 + (s1 - s0).normalized() * 0.026, 0.0022, 6), 'STEEL')
pad("name_tape", A_TAPE, 0.056, 0.333, 0.360, 0.0028, 0.0, 10, 3, 'NAMETAPE', frame=True)

# ---------------- sleeves torn above the elbow (as santa_build.py's sleeve(), with a ragged end) ----------------
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
    return verts, faces, [tt for tt, _ in rs for _k in range(nb)], rs[-1][1]
NBS = 20
ARM_R = {}                                           # the bare skin's radius at the sleeve's end, per side
for side, sx in (('Left', 1.0), ('Right', -1.0)):
    pA, pE, pW = B(side + 'Arm'), B(side + 'ForeArm'), B(side + 'Hand')
    arm_src = np.array([i for i, d in enumerate(D) if d == side + 'Arm' and V[i, 2] < 0.46])
    L1 = (pE - pA).length; L2 = (pW - pE).length; a1, u1, v1 = frame(pA, pE)
    T_END = L1 - 0.068                               # the sleeve's end: torn ~5 cm above the elbow
    sv_, sf_, st_, last_r = sleeve(pA, pE, arm_src, 0.0, T_END, 0.016, lambda t, L1=L1: 0.066 - 0.010 * t / L1, nb=NBS)
    sk_ = ['SUIT'] * len(sf_)
    base = len(sv_) - NBS; teeth = []                # the ragged hem: a ring of teeth of random length below the last ring
    for k in range(NBS):
        tl = 0.007 + 0.034 * abs(noise.noise(Vector((k * 0.83, sx * 3.1, 0.5)))) * (1.0 if k % 2 else 0.35) + 0.006 * (k % 3 == 0)
        teeth.append(tl)
        sv_.append(pA + a1 * (T_END + tl) + (u1 * math.cos(ang(k, NBS)) + v1 * math.sin(ang(k, NBS))) * last_r[k] * (0.975 - 0.02 * (k % 2)))
        st_.append(T_END + tl)
    for k in range(NBS):
        k2 = (k + 1) % NBS; sf_.append((base + k, base + k2, base + NBS + k2, base + NBS + k)); sk_.append('TORN')
    blend = [smoothstep(T_END - 0.10, T_END - 0.05, t) for t in st_]        # the sleeve's end rides the upper arm only (rigid)
    add(f"sleeve_{side}", sv_, sf_, sk_, recalc=False, wblend=(side + 'Arm', blend))
    ARM_R[side] = 0.0285
    # a dark annulus a little inside the sleeve's end: the shadowed inside, with the skinny arm passing through it
    tcv = T_END - 0.012; outer = [pA + a1 * tcv + (u1 * math.cos(ang(k, NBS)) + v1 * math.sin(ang(k, NBS))) * last_r[k] * 0.955 for k in range(NBS)]
    inner = [pA + a1 * tcv + (u1 * math.cos(ang(k, NBS)) + v1 * math.sin(ang(k, NBS))) * (ARM_R[side] + 0.003) for k in range(NBS)]
    add(f"sleeve_cavity_{side}", outer + inner, [(k, (k + 1) % NBS, NBS + (k + 1) % NBS, NBS + k) for k in range(NBS)], 'CAVITY', w={side + 'Arm': 1.0}, recalc=False)
    print("SLEEVE", side, "L1", round(L1, 3), "L2", round(L2, 3), "end t", round(T_END, 3), "r mean", round(float(last_r.mean()), 4),
          "teeth", round(min(teeth), 3), "..", round(max(teeth), 3))
    # ---------------- bare skinny arm: rigid bones with ball joints (no stretching, no candy-wrapper) ----------------
    WA, WF = {side + 'Arm': 1.0}, {side + 'ForeArm': 1.0}
    add(f"upperarm_{side}", *tube(pA + a1 * (T_END - 0.10), pE, 0.026, 0.0295, 10, mid=0.02), 'SKIN', w=WA)
    add(f"elbow_{side}", *lumpy_ball(pE, 0.0335, 12, 8, 0.07, 45, 3 * sx, scl=(1.0, 1.0, 1.05)), 'SKIN', w=WF)
    a2, u2, v2 = frame(pE, pW)
    frows = []
    for t, r in ((0.0, 0.0295), (0.035, 0.0315), (0.085, 0.0285), (0.15, 0.0250), (0.21, 0.0222), (L2, 0.0210)):
        c = pE + a2 * t; frows.append([c + (u2 * math.cos(ang(k, 12)) * 1.12 + v2 * math.sin(ang(k, 12))) * r for k in range(12)])
    add(f"forearm_{side}", *ring_loft(frows, cap_start=True, cap_end=True), 'SKIN', w=WF)
    add(f"wrist_{side}", *lumpy_ball(pW, 0.0245, 12, 8, 0.06, 50, 5 * sx, scl=(1.15, 1.0, 1.0)), 'SKIN', w=WF)
    for t_, ph, rw in ((0.07, 0.6, 0.0055), (0.13, 2.4, 0.0045), (0.18, 4.1, 0.004)):    # warts
        c = pE + a2 * t_; dd = u2 * math.cos(ph) * 1.12 + v2 * math.sin(ph)
        add(f"forearm_wart_{side}", *lumpy_ball(c + dd * 0.026, rw, 8, 5, 0.1, 200, t_ * 10), 'SKIN', w=WF)

    # ---------------- the hand: a bony palm, three long clawed fingers (index, middle, ring + pinky) and a thumb ----------------
    Jn = lambda nme: [B(f'{side}Hand{nme}1'), B(f'{side}Hand{nme}2'), B(f'{side}Hand{nme}3'), BT(f'{side}Hand{nme}3')]
    IDX, MID, RNG, PNK, THB = Jn('Index'), Jn('Middle'), Jn('Ring'), Jn('Pinky'), Jn('Thumb')
    F3 = [(a_ + b_) / 2 for a_, b_ in zip(RNG, PNK)]         # the merged third finger rides the average of ring and pinky
    Kc = (IDX[0] + MID[0] + F3[0]) / 3
    along = (Kc - pW).normalized(); across = IDX[0] - F3[0]; across = (across - along * across.dot(along)).normalized()
    pn = along.cross(across).normalized()
    palm_dir = pn if pn.x * sx < 0 else -pn          # the palm faces the thigh in the A-pose; fingers curl toward it
    tk_ = (Kc - pW).dot(along); prow = []
    PALM = ((0.0, 0.017, 0.0135), (0.18, 0.0225, 0.0145), (0.45, 0.0285, 0.014), (0.72, 0.032, 0.0125), (0.92, 0.033, 0.0115), (1.0, 0.030, 0.0100))
    for f_, w_, h_ in PALM:
        c = pW + along * (tk_ * f_) + palm_dir * (-0.002)
        prow.append([c + across * (w_ * math.cos(ang(k, 14))) + palm_dir * (h_ * math.sin(ang(k, 14))) for k in range(14)])
    WH = {side + 'Hand': 1.0}
    add(f"palm_{side}", *ring_loft(prow, cap_start=True, cap_end=True), 'SKIN', w=WH)
    def palm_back(f_, x_):                           # a point on the back of the hand at fraction f_ along it, x_ across
        w_ = float(np.interp(f_, [q[0] for q in PALM], [q[1] for q in PALM])); h_ = float(np.interp(f_, [q[0] for q in PALM], [q[2] for q in PALM]))
        return pW + along * (tk_ * f_) + across * x_ - palm_dir * (0.002 + h_ * math.sqrt(max(0.0, 1 - (x_ / w_) ** 2)))
    for kx in (-1, 0, 1):                            # tendons running to the knuckles, just proud of the back of the hand
        add(f"hand_ridge_{side}", *tube(palm_back(0.22, 0.007 * kx), palm_back(0.94, 0.017 * kx), 0.0030, 0.0036, 6), 'SKIN', w=WH)
    def digit(name, js, ws, r0, ext, claw, seed):
        js = list(js); js[3] = js[2] + (js[3] - js[2]) * ext
        rs = [r0, r0 * 0.92, r0 * 0.84, r0 * 0.74]
        for k in range(3):
            add(f"{name}_seg{k + 1}", *tube(js[k], js[k + 1], rs[k], rs[k + 1], 8, mid=0.05), 'SKIN', w=ws[k])
            add(f"{name}_knuckle{k + 1}", *lumpy_ball(js[k], rs[k] + 0.0022, 8, 5, 0.06, 90, seed + k), 'SKIN', w=ws[k])
        d = (js[3] - js[2]).normalized(); cd = (palm_dir - d * palm_dir.dot(d)).normalized()
        path = [js[3] - d * 0.004 + d * (claw * s) + cd * (claw * 0.50 * s * s) for s in np.linspace(0, 1, 6)]
        add(f"{name}_claw", *sweep(path, ellipse(rs[3] * 0.95, rs[3] * 0.80, 6), scale=[max(0.07, (1 - s) ** 0.8) for s in np.linspace(0, 1, 6)]), 'CLAW', w=ws[2])
        return js[3]
    tips = {}
    tips['index'] = digit(f"index_{side}", IDX, [{f'{side}HandIndex{k}': 1.0} for k in (1, 2, 3)], 0.0098, 1.85, 0.028, 11 * sx)
    tips['middle'] = digit(f"middle_{side}", MID, [{f'{side}HandMiddle{k}': 1.0} for k in (1, 2, 3)], 0.0103, 1.85, 0.030, 21 * sx)
    tips['third'] = digit(f"third_{side}", F3, [{f'{side}HandRing{k}': 0.5, f'{side}HandPinky{k}': 0.5} for k in (1, 2, 3)], 0.0110, 1.80, 0.029, 31 * sx)
    add(f"thenar_{side}", *lumpy_ball(THB[0] + palm_dir * 0.003, 0.0150, 10, 7, 0.05, 60, 41 * sx), 'SKIN', w={f'{side}HandThumb1': 1.0})
    tips['thumb'] = digit(f"thumb_{side}", THB, [{f'{side}HandThumb{k}': 1.0} for k in (1, 2, 3)], 0.0105, 1.45, 0.024, 51 * sx)
    print("HAND", side, "palm", round(tk_, 3), "| finger lengths knuckle->claw base", {k: round((v - (IDX[0] if k == 'index' else MID[0] if k == 'middle' else F3[0] if k == 'third' else THB[0])).length, 3) for k, v in tips.items()})

# ---------------- legs: rolled cuffs over the cut pants, a dark inside, skinny shins, clawed bare feet ----------------
shell_kept = np.array([i for i in shell if i in keep_kind])
for side, sx in (('Left', 1.0), ('Right', -1.0)):
    kn, an, tb, tt_ = B(side + 'Leg'), B(side + 'Foot'), B(side + 'ToeBase'), BT(side + 'ToeBase')
    WL, WFt, WT = {side + 'Leg': 1.0}, {side + 'Foot': 1.0}, {side + 'ToeBase': 1.0}
    sl = V[[i for i in shell_kept if V[i, 2] < Z_CUT + 0.030 and V[i, 0] * sx > 0]]
    cxL = (sl[:, 0].min() + sl[:, 0].max()) / 2; cyL = (sl[:, 1].min() + sl[:, 1].max()) / 2
    rL = profile(sl, cxL, cyL, nb=36, k=5, sm=3)
    la = (an - kn).normalized()
    def leg_c(z): return kn + la * ((z - kn.z) / la.z)
    def ring_at(z, rr, c=None):
        c = Vector((cxL, cyL, z)) if c is None else c
        return [Vector((c.x + rr[k] * math.cos(ang(k, 36)), c.y + rr[k] * math.sin(ang(k, 36)), z)) for k in range(36)]
    for zc, dr, prof_, kd in ((Z_CUT - 0.003, 0.0085, ellipse(0.0135, 0.0105, 6), 'SUIT_DARK'), (Z_CUT + 0.019, 0.0060, ellipse(0.0115, 0.0090, 6), 'SUIT')):
        rp = ring_at(zc, rL + dr)[::2]
        add(f"cuff_{side}", *sweep(rp + rp[:1], prof_, normals=[Vector((p.x - cxL, p.y - cyL, 0)) for p in rp + rp[:1]], caps=False,
                                   lump=0.06, lump_f=40, seed=sx + zc), kd, w=WL)
    cs = leg_c(Z_CUT + 0.004)
    add(f"cuff_cavity_{side}", ring_at(Z_CUT + 0.004, rL - 0.003) + ring_at(Z_CUT + 0.004, np.full(36, 0.034), cs),
        [(k, (k + 1) % 36, 36 + (k + 1) % 36, 36 + k) for k in range(36)], 'CAVITY', w=WL, recalc=False)
    print("CUFF", side, "pants r at the cut", round(float(rL.mean()), 4), "centre", round(cxL, 3), round(cyL, 3), "| shin axis there", [round(x, 3) for x in cs])
    # shin: a tapered tube with a calf at the back, from inside the trouser leg down to the ankle ball
    srows = []
    z_top = Z_CUT + 0.045; L_sh = (an - leg_c(z_top)).length
    a_s, u_s, v_s = frame(leg_c(z_top), an)
    for s in np.linspace(0.0, 1.0, 9):
        c = leg_c(z_top).lerp(an, s); r0 = 0.0285 - 0.0085 * s; rb = 0.0085 * math.exp(-((s - 0.22) / 0.22) ** 2)
        row = []
        for k in range(12):
            dd = u_s * math.cos(ang(k, 12)) + v_s * math.sin(ang(k, 12))
            row.append(c + dd * (r0 + rb * max(0.0, dd.y) ** 1.5))
        srows.append(row)
    add(f"shin_{side}", *ring_loft(srows, cap_start=True, cap_end=True), 'SKIN', w=WL)
    for s_, ph, rw in ((0.30, 1.1, 0.005), (0.55, -0.4, 0.0042), (0.70, 2.3, 0.0038), (0.42, 3.6, 0.0045)):
        c = leg_c(z_top).lerp(an, s_); dd = u_s * math.cos(ph) + v_s * math.sin(ph)
        add(f"shin_wart_{side}", *lumpy_ball(c + dd * (0.0285 - 0.0085 * s_), rw, 6, 4, 0.1, 200, s_ * 7 + sx), 'SKIN', w=WL)
    add(f"ankle_{side}", *lumpy_ball(an, 0.0285, 12, 8, 0.06, 40, 7 * sx, scl=(1.05, 1.0, 1.0)), 'SKIN', w=WFt)
    # the foot: heel -> ball, flat sole at z -0.972, rigid on Foot
    SOLE = -0.972; heel = Vector((an.x - 0.002 * sx, an.y + 0.052, SOLE)); fro = Vector((tb.x, tb.y + 0.004, SOLE))
    frows = []
    for s, w_, h_ in ((0.0, 0.010, 0.012), (0.06, 0.019, 0.019), (0.18, 0.025, 0.024), (0.40, 0.029, 0.028), (0.65, 0.033, 0.026), (0.88, 0.036, 0.022), (1.0, 0.034, 0.019)):
        c = heel.lerp(fro, s); c.z = SOLE + h_
        frows.append([c + Vector((w_ * math.cos(ang(k, 12)), 0, h_ * math.sin(ang(k, 12)))) for k in range(12)])
    add(f"foot_{side}", *ring_loft(frows, cap_start=True, cap_end=True), 'SKIN', w=WFt)
    add(f"heel_claw_{side}", *sweep([Vector((heel.x, heel.y - 0.006 + 0.034 * s, SOLE + 0.016 - 0.019 * s * s)) for s in np.linspace(0, 1, 5)],
                                     ellipse(0.0075, 0.0068, 6), scale=[max(0.07, (1 - s) ** 0.8) for s in np.linspace(0, 1, 5)]), 'CLAW', w=WFt)
    add(f"toe_ball_{side}", *lumpy_ball(tb, 0.0255, 12, 8, 0.05, 40, 9 * sx, scl=(1.25, 1.0, 0.95)), 'SKIN', w=WT)
    d0 = (tt_ - tb); d0.z = 0; d0.normalize()
    for yaw, lm in ((-0.40, 0.92), (0.0, 1.12), (0.40, 0.92)):
        d = rot_z(d0, yaw); k1 = tb + d * (0.046 * lm) - Vector((0, 0, 0.004)); tip = k1 + d * (0.040 * lm) - Vector((0, 0, 0.0095))
        add(f"toe_{side}", *tube(tb, k1, 0.0125, 0.0112, 8, mid=0.04), 'SKIN', w=WT)
        add(f"toe_knuckle_{side}", *lumpy_ball(k1, 0.0128, 8, 6, 0.06, 90, yaw * 10 + sx), 'SKIN', w=WT)
        add(f"toe_tip_{side}", *tube(k1, tip, 0.0108, 0.0088, 8, mid=0.03), 'SKIN', w=WT)
        add(f"toe_claw_{side}", *sweep([tip + d * (0.032 * s) - Vector((0, 0, 0.004 + 0.009 * s * s)) for s in np.linspace(0, 1, 6)],
                                        ellipse(0.0080, 0.0070, 6), scale=[max(0.07, (1 - s) ** 0.8) for s in np.linspace(0, 1, 6)]), 'CLAW', w=WT)

# ---------------- tool belt (rigid on Hips): band, buckle, two pouches, a wrench on the left hip ----------------
kv_ = sorted(keep_kind); kmap = {o: n_ for n_, o in enumerate(kv_)}
kf_ = [tuple(kmap[i] for i in p_.vertices) for p_ in me.data.polygons if all(i in keep_kind for i in p_.vertices)]
outer_bvh = BVHTree.FromPolygons([Vector(V[i]) for i in kv_] + tv, kf_ + [tuple(j + len(kv_) for j in q) for q in tq])
def surf_out(a, z, cy=0.0):
    """the outermost surface (torso loft or trousers) at azimuth a, height z, cast from outside in"""
    d = Vector((math.cos(a), math.sin(a), 0)); o = Vector((0, cy, z)) + d * 0.6
    hit = outer_bvh.ray_cast(o, -d, 0.6)
    return (hit[0] if hit[0] is not None else Vector((0, cy, z)) + d * 0.15), d
WHIP = {'Hips': 1.0}
NBELT = 64; BZ = (-0.058, -0.032, -0.006); Vb, Fb = [], []
cyb = coat_r(-math.pi / 2, 0.0)[1]
BR = np.array([max((surf_out(-math.pi + k / NBELT * 2 * math.pi, z, cyb)[0] - Vector((0, cyb, z))).xy.length
                   for z in np.linspace(BZ[0] - 0.006, BZ[2] + 0.006, 9)) for k in range(NBELT)])
BR = circ_median(BR, 3); BR = np.maximum(BR, (np.roll(BR, 1) + 2 * BR + np.roll(BR, -1)) / 4)      # a stiff band: the max of its band, smoothed
for k in range(NBELT):
    a = -math.pi + k / NBELT * 2 * math.pi; d = Vector((math.cos(a), math.sin(a), 0))
    for zi, z in enumerate((BZ[0] - 0.001,) + BZ + (BZ[2] + 0.001,)):
        Vb.append(Vector((0, cyb, z)) + d * (BR[k] + (-0.002 if zi in (0, 4) else 0.0085)))
for k in range(NBELT):
    k2 = (k + 1) % NBELT
    for zi in range(4): Fb.append((k * 5 + zi, k2 * 5 + zi, k2 * 5 + zi + 1, k * 5 + zi + 1))
add("belt", Vb, Fb, 'LEATHER', recalc=False, w=WHIP)
belt_bvh = BVHTree.FromPolygons(Vb, Fb); pokes = []
for name_, vs_ in (("torso", tv), ("trousers", [Vector(V[i]) for i in kv_])):
    for p in vs_:
        if not BZ[0] + 0.002 < p.z < BZ[2] - 0.002: continue
        d = Vector((p.x, p.y - cyb, 0)); L = d.length; hit = belt_bvh.ray_cast(Vector((0, cyb, p.z)), d / L, 1.0)
        if hit[0] is not None and hit[3] < L: pokes.append((name_, round(math.degrees(math.atan2(d.y, d.x))), round(p.z, 3), round((L - hit[3]) * 1000, 1)))
print("CHECK torso/trouser verts poking through the belt:", len(pokes), pokes[:8])
def belt_pt(a, z):
    d = Vector((math.cos(a), math.sin(a), 0)); fk = ((a + math.pi) / (2 * math.pi) * NBELT) % NBELT; k0 = int(fk) % NBELT; t = fk - int(fk)
    return Vector((0, cyb, z)) + d * (BR[k0] * (1 - t) + BR[(k0 + 1) % NBELT] * t + 0.0085), d
p, d = belt_pt(-math.pi / 2, BZ[1]); up = Vector((0, 0, 1)); tx = up.cross(d).normalized()
BW, BH, BB = 0.060, 0.056, 0.010
for off, w_, h_ in ((up * (BH / 2 - BB / 2), BW, BB), (-up * (BH / 2 - BB / 2), BW, BB), (tx * (BW / 2 - BB / 2), BB, BH), (-tx * (BW / 2 - BB / 2), BB, BH)):
    add("buckle", *box(p + off, d, w_, h_, 0.007), 'BRASS', smooth=False, w=WHIP)
add("buckle_prong", *box(p - tx * 0.008, d, 0.030, 0.005, 0.009), 'BRASS', smooth=False, w=WHIP)
for a_p in (-math.pi / 2 + 0.62, -math.pi / 2 - 0.62):     # pouches, front-left and front-right
    p, d = belt_pt(a_p, -0.030)
    add("pouch", *box(p - Vector((0, 0, 0.008)), d, 0.060, 0.064, 0.030), 'LEATHER', w=WHIP)
    add("pouch_flap", *box(p + d * 0.002 + Vector((0, 0, 0.012)), d, 0.064, 0.030, 0.031), 'LEATHER_D', smooth=False, w=WHIP)
    add("pouch_snap", *cyl(p + d * 0.033 + Vector((0, 0, 0.004)), p + d * 0.037 + Vector((0, 0, 0.004)), 0.0045, 8), 'BRASS', smooth=False, w=WHIP)
A_WR = -0.16                                         # the wrench hangs off a loop on the left hip
p_top, d_w = belt_pt(A_WR, -0.020)
pb_, _ = surf_out(A_WR, -0.172, cyb); p_bot = pb_ + d_w * 0.014
ax_w = (p_bot - p_top).normalized()
add("wrench_loop", *box(p_top + d_w * 0.002, d_w, 0.026, 0.040, 0.012, up=-ax_w), 'LEATHER_D', smooth=False, w=WHIP)
h0 = p_top + d_w * 0.005 - ax_w * 0.012; h1 = p_bot + d_w * 0.002
add("wrench_handle", *box(h0.lerp(h1, 0.5), d_w, 0.017, (h1 - h0).length, 0.007, up=-ax_w), 'STEEL', w=WHIP)
for c_, ri, ro in ((h1 + ax_w * 0.014, 0.0105, 0.020), (h0 - ax_w * 0.006, 0.0075, 0.0145)):   # open jaw at the bottom, ring at the top
    av, af = annulus(c_ - d_w * 0.0005, c_ + d_w * 0.0075, ri, ro, 16)
    if ri > 0.01:                                   # cut the jaw open (its mouth points down the handle)
        keep_f = []
        for f in af:
            cc = sum((av[i] for i in f), Vector()) / len(f) - c_; cc = cc - d_w * cc.dot(d_w)
            if cc.normalized().dot(ax_w) < 0.80: keep_f.append(f)
        av, af = compact(av, keep_f)
    add("wrench_end", av, af, 'STEEL', smooth=False, w=WHIP)
print("WRENCH top", [round(x, 3) for x in p_top], "bottom", [round(x, 3) for x in p_bot])

# ---------------- red pilot's scarf (rigid on Spine2): a wrap, a knot, two tails thrown back over the left shoulder ----------------
WS2 = {'Spine2': 1.0}
for zc, rr, hw, ht, sd in ((0.492, 0.0655, 0.0185, 0.0105, 1.0), (0.517, 0.0615, 0.0160, 0.0090, 2.0)):
    path = [neck_c(zc) + Vector((math.cos(ang(k, 24)), math.sin(ang(k, 24)), 0)) * rr for k in range(24)]
    add("scarf_wrap", *sweep(path, ellipse(hw, ht, 8), normals=[Vector((math.cos(ang(k, 24)), math.sin(ang(k, 24)), 0)) for k in range(24)],
                             closed=True, lump=0.10, lump_f=45, seed=sd), 'SCARF', w=WS2)
cl_v, cl_f = merged({"coat_torso", "collar", "collar_rim"}, parts); cl_bvh = BVHTree.FromPolygons(cl_v, cl_f)
def out_n(q):
    """the nearest coverall/collar surface point and its normal, turned outward (away from the neck, or up)"""
    loc, nrm, _, dist = cl_bvh.find_nearest(q)
    radial = Vector((q.x, q.y - neck_c(min(q.z, 0.56)).y, 0)); n_ = Vector(nrm)
    if n_.dot(radial) + 0.5 * n_.z * radial.length < 0: n_ = -n_
    return loc, n_, dist
def push_out(q, clr):
    """move q out along the nearest coverall/collar normal until it is clr clear of it"""
    loc, n_, dist = out_n(q)
    return loc + n_ * clr if (dist < clr or (q - loc).dot(n_) < 0) else q
def over(a_deg, z, dr):                              # a point dr off the coverall along its normal
    a = math.radians(a_deg); q = coat_pt(a, min(z, Z_TOP)) + coat_n(a, min(z, Z_TOP)) * dr; q.z = max(q.z, z); return q
# the knot sits on the collar's front-left, outside it; a fold of scarf comes up out of the wrap and over the collar's rim to it
A_KNOT = -math.pi / 2 + math.radians(28)
r_rim = coat_r(A_KNOT, Z_TOP)[0] + 0.024; cyk = coat_r(A_KNOT, Z_TOP)[1]; dk = Vector((math.cos(A_KNOT), math.sin(A_KNOT), 0))
knot = Vector((0, cyk, 0.486)) + dk * (r_rim + 0.012)
add("scarf_knot", *lumpy_ball(knot, 0.0200, 12, 9, 0.10, 40, 3.0, scl=(0.95, 0.80, 1.15)), 'SCARF', w=WS2)
fold = [neck_c(0.518) + dk * 0.066, Vector((0, cyk, 0.520)) + dk * (r_rim - 0.004), Vector((0, cyk, 0.514)) + dk * (r_rim + 0.010), knot + Vector((0, 0, 0.010))]
add("scarf_fold", *sweep(dense(fold, 7), rect(0.019, 0.0030), normals=[(dk * 0.35 + Vector((0, 0, 1))).normalized()] * 7), 'SCARF', w=WS2)
tail_pts = []
for t_i, (ctrl, hw) in enumerate((([(-40, 0.478, 0.016), (-14, 0.468, 0.016), (10, 0.456, 0.016), (26, 0.434, 0.015), (36, 0.398, 0.014),
                                     (42, 0.352, 0.014), (45, 0.306, 0.014), (46, 0.272, 0.014)], 0.026),
                                   ([(-36, 0.474, 0.022), (-10, 0.462, 0.022), (14, 0.448, 0.022), (32, 0.420, 0.022), (44, 0.382, 0.022),
                                     (50, 0.340, 0.022), (53, 0.302, 0.022)], 0.021))):
    cp = [knot + Vector((0, 0, -0.004))] + [over(a_, z_, dr_) for a_, z_, dr_ in ctrl]
    pts = [push_out(q, 0.0140 + 0.006 * t_i) for q in dense(cp, 22)]
    nn_ = [out_n(q)[1] for q in pts]
    for _ in range(3): nn_ = [(nn_[max(0, i - 1)] + nn_[i] * 2 + nn_[min(len(nn_) - 1, i + 1)]).normalized() for i in range(len(nn_))]
    wv_ = [q + nn_[i] * 0.0022 * math.sin(i * 0.9 + t_i) for i, q in enumerate(pts)]
    add("scarf_tail", *sweep(wv_, rect(hw, 0.0026), normals=nn_, scale=[1.0 - 0.08 * (i / 21) for i in range(22)]), 'SCARF', w=WS2)
    tail_pts += wv_
tail_clear = min(cl_bvh.find_nearest(q)[3] for q in tail_pts)
print("CHECK scarf tails' closest approach to the coverall (want >= 8 mm):", round(tail_clear * 1000, 1), "mm")

# ---------------- neck + the brass threaded socket on its stump (Neck 100 %) ----------------
WN = {'Neck': 1.0}
nrows = [[neck_c(z) + Vector((math.cos(ang(k, 14)), math.sin(ang(k, 14)), 0)) * (0.0375 + 0.002 * math.sin(z * 90)) for k in range(14)]
         for z in np.linspace(0.430, 0.548, 7)]
add("neck_skin", *ring_loft(nrows), 'SKIN', w=WN)
NAX = (NH_ - NA).normalized()
Z_SOCK = 0.542
sv_, sf_, sk_, _ = lathe(neck_c(Z_SOCK), NAX, [(0.0400, 0.000), (0.0470, 0.002), (0.0470, 0.006), (0.0420, 0.007), (0.0420, 0.029), (0.0380, 0.031),
                                               (0.0290, 0.031), (0.0272, 0.029), (0.0272, 0.020), (0.0, 0.020)], 24,
                         ['BRASS'] * 5 + ['BRASS_D', 'BRASS_D', 'CAVITY', 'CAVITY'])     # the top is dark: you look down on it in first person
add("neck_socket", sv_, sf_, sk_, w=WN, smooth=False)
for h in (0.012, 0.018, 0.024):                     # thread ridges
    c = neck_c(Z_SOCK) + NAX * h
    add("socket_thread", *sweep([c + Vector((math.cos(ang(k, 20)) * 0.0428, math.sin(ang(k, 20)) * 0.0428, 0.0)) for k in range(20)],
                                ellipse(0.0017, 0.0017, 4), closed=True), 'BRASS', w=WN)
STUMP = ("neck_socket", "socket_thread")

# ---------------- the head (head-local: origin = DH_C) ----------------
C = Vector((0.0, -0.010, 0.650))                     # DH_C; the eyes sit at the eye bones' height (0.649)
CR_C, CR_R = Vector((0.0, 0.014, -0.010)), Vector((0.098, 0.108, 0.126))       # cranium (deep: its underside closes round the socket)
JW_C, JW_R = Vector((0.0, -0.048, -0.064)), Vector((0.090, 0.074, 0.054))       # the jutting jaw
cv0, cf0 = ell(CR_C, CR_R, 26, 16, 0.010, 3.0, 1.0); hadd("cranium", cv0, cf0, 'FACE')
jv0, jf0 = ell(JW_C, JW_R, 24, 14, 0.010, 3.5, 2.0); hadd("jaw", jv0, jf0, 'FACE')
for sx in (1, -1):
    hadd("cheek", *lumpy_ball(Vector((sx * 0.064, -0.070, -0.022)), 0.026, 14, 9, 0.05, 30, sx, scl=(1.0, 0.85, 0.80)), 'FACE')
face_bvh = BVHTree.FromPolygons(*merged({"cranium", "jaw", "cheek"}, hparts))
# big red eyes with slit pupils (a lathe round each eye's axis, so the iris texture is a clean disc), angry lids
EYE_R = 0.033; EYES = []
for sx in (1, -1):
    E = Vector((sx * 0.046, -0.084, 0.0)); ax = Vector((sx * 0.22, -1.0, 0.04)).normalized()
    prof = [(EYE_R * math.sin(t), -EYE_R * math.cos(t)) for t in np.linspace(0, math.pi, 11)]
    eu = ax.cross(Vector((0, 0, 1))).normalized(); ev = eu.cross(ax).normalized()
    if ev.z < 0: ev = -ev
    evs, efs, eks, _ = lathe(E, ax, prof, 18, ['EYE'] * 10, u=eu)
    hadd("eye", evs, efs, eks, frame=(E, eu, ev, EYE_R, EYE_R)); EYES.append((E, ax))
    # the upper lid: a shell on a slightly bigger sphere above a slanted edge, lower toward the nose (angry)
    LR = EYE_R + 0.0030; cut = lambda xr: 0.007 + 0.42 * sx * xr; lrows = []
    for i, f_ in enumerate(np.linspace(0, 1, 8)):
        row = []
        for xr in np.linspace(-0.94 * LR, 0.94 * LR, 13):
            rho = math.sqrt(max(1e-8, LR * LR - xr * xr)); th0 = math.asin(max(-0.95, min(0.95, cut(xr) / rho))); th = th0 + (math.pi / 2 + 0.35 - th0) * f_ ** 0.9
            row.append(E + Vector((xr, -rho * math.cos(th), rho * math.sin(th))))
        lrows.append(row)
    hadd("lid", *open_loft(lrows), 'FACE', recalc=False)
    hadd("lid_rim", *sweep(lrows[0], ellipse(0.0030, 0.0026, 6), normals=[(p - E) for p in lrows[0]]), 'FACE')
lid_bvh = BVHTree.FromPolygons(*merged({"cranium", "jaw", "cheek", "lid", "lid_rim"}, hparts))
# angry V brows
for sx in (1, -1):
    hp = [front_hit(lid_bvh, sx * x, z) for x, z in ((0.008, 0.028), (0.026, 0.040), (0.046, 0.051), (0.066, 0.058), (0.080, 0.061))]
    pts = dense([q[0] for q in hp], 11); nn = dense([q[1] for q in hp], 11)
    hadd("brow", *sweep(pts, ellipse(0.0100, 0.0075, 8), normals=nn, scale=[0.70 + 0.40 * math.sin(math.pi * (0.25 + 0.75 * i / 10)) for i in range(11)],
                        lift=0.0050, lump=0.10, lump_f=120, seed=sx), 'FACE')
# hooked nose
nctrl = [Vector((0, -0.084, 0.012)), Vector((0, -0.112, 0.003)), Vector((0, -0.134, -0.012)), Vector((0, -0.148, -0.029)), Vector((0, -0.150, -0.043))]
hadd("nose", *sweep(dense(nctrl, 12), ellipse(0.0190, 0.0165, 10), scale=[1.0 - 0.42 * (i / 11) ** 1.1 for i in range(12)], lump=0.04, lump_f=90, seed=5), 'FACE')
hadd("nose_tip", *lumpy_ball(Vector((0, -0.148, -0.048)), 0.0128, 12, 8, 0.05, 80, 6, scl=(1.1, 1.0, 0.95)), 'FACE')
for sx in (1, -1):
    hadd("nostril", *lumpy_ball(Vector((sx * 0.0092, -0.142, -0.056)), 0.0040, 8, 5, 0.0, 1, 0, scl=(1.0, 1.2, 0.7)), 'MOUTH')
# the needle grin: a dark slot round the jaw's front, thin lips, interleaved needle teeth
GX = np.linspace(-0.077, 0.077, 21); gz = lambda x: -0.073 + 3.4 * x * x
hp = [front_hit(face_bvh, x, gz(x)) for x in GX]; gp = [q[0] for q in hp]; gn = [q[1] for q in hp]
gs = [0.55 + 0.45 * math.cos(math.pi / 2 * abs(x) / 0.077) for x in GX]          # the slot narrows toward the corners
hadd("mouth_slot", *sweep(gp, rect(0.0078, 0.0060), normals=gn, scale=gs, lift=-0.0035), 'MOUTH', smooth=False)
def grin_up(i):
    t = (gp[min(20, i + 1)] - gp[max(0, i - 1)]).normalized(); b = t.cross(gn[i]).normalized(); return b if b.z > 0 else -b
for sg, off in ((1, 0.0102), (-1, 0.0100)):
    lp = [gp[i] + grin_up(i) * (sg * off * gs[i]) for i in range(21)]
    hadd("lip", *sweep(lp, ellipse(0.0036, 0.0030, 5), normals=gn, lift=0.0010, scale=[0.6 + 0.4 * gs[i] for i in range(21)]), 'FACE')
for i in range(1, 20):                               # upper needles on every point, lower ones between them
    upv = grin_up(i); h = 0.0078 * gs[i]
    b0 = gp[i] + gn[i] * 0.0028 + upv * (h - 0.0008)
    hadd("tooth", *cone(b0, b0 - upv * (0.0105 * gs[i] + 0.002) + gn[i] * 0.0008, 0.0029 * (0.7 + 0.3 * gs[i]), 5), 'TOOTH', smooth=False)
    if i < 19:
        m_ = (gp[i] + gp[i + 1]) / 2; upm = (upv + grin_up(i + 1)).normalized(); hm = 0.0078 * (gs[i] + gs[i + 1]) / 2; nm = (gn[i] + gn[i + 1]).normalized()
        b1 = m_ + nm * 0.0026 - upm * (hm - 0.0008)
        hadd("tooth", *cone(b1, b1 + upm * (0.0085 * gs[i] + 0.002) + nm * 0.0008, 0.0026 * (0.7 + 0.3 * gs[i]), 5), 'TOOTH', smooth=False)
for (x_, z_), rw in (((0.072, -0.040), 0.0060), ((-0.058, -0.034), 0.0050), ((0.022, -0.106), 0.0045), ((-0.030, 0.050), 0.0040)):   # warts
    p, n = front_hit(face_bvh, x_, z_); hadd("wart", *lumpy_ball(p + n * 0.0015, rw, 8, 5, 0.12, 200, x_ * 50), 'FACE')
# the leather flying helmet: a parametric cap on the cranium, its edge an exact curve (no staircase), with a rolled rim
HO = 0.0090; HR = Vector((CR_R.x + HO, CR_R.y + HO, CR_R.z + HO))
def h_edge(phi):                                     # the cap's edge height (head-local z) by the angle from the front
    d = math.degrees(phi); front = 0.074 + 0.010 * smoothstep(0, 45, d)
    return front + (-0.046 - front) * smoothstep(52, 100, d) + (-0.090 + 0.046) * smoothstep(110, 170, d)
def helm_pt(th, lat, extra=0.0):
    return CR_C + Vector(((HR.x + extra) * math.cos(lat) * math.cos(th), (HR.y + extra) * math.cos(lat) * math.sin(th), (HR.z + extra) * math.sin(lat)))
NU, NVH = 38, 10; hv_, hf_ = [], []
for j in range(NU):
    th = -math.pi + 2 * math.pi * j / NU; phi = phi_front(math.atan2(HR.y * math.sin(th), HR.x * math.cos(th)))
    lat0 = math.asin(max(-0.99, min(0.99, (h_edge(phi) - CR_C.z) / HR.z)))
    for i in range(NVH): hv_.append(helm_pt(th, lat0 + (math.radians(84) - lat0) * (i / (NVH - 1)) ** 0.85))
for j in range(NU):
    j2 = (j + 1) % NU
    for i in range(NVH - 1): hf_.append((j * NVH + i, j2 * NVH + i, j2 * NVH + i + 1, j * NVH + i + 1))
pole = len(hv_); hv_.append(CR_C + Vector((0, 0, HR.z)))
for j in range(NU): hf_.append((j * NVH + NVH - 1, ((j + 1) % NU) * NVH + NVH - 1, pole))
hadd("helmet", hv_, hf_, 'LEATHER')
helm_bvh = BVHTree.FromPolygons(hv_, hf_)
rim = [hv_[j * NVH] for j in range(NU)]
hadd("helmet_rim", *sweep(rim + rim[:1], ellipse(0.0052, 0.0046, 6), normals=[Vector(((p - CR_C).x / HR.x ** 2, (p - CR_C).y / HR.y ** 2, (p - CR_C).z / HR.z ** 2)) for p in rim + rim[:1]],
                          caps=False), 'LEATHER_D')
seam = [helm_pt(-math.pi / 2, l) for l in np.linspace(math.asin((h_edge(0) - CR_C.z) / HR.z), math.radians(89), 9)] + \
       [helm_pt(math.pi / 2, l) for l in np.linspace(math.radians(89), math.asin((h_edge(math.pi) - CR_C.z) / HR.z), 12)][1:]
hadd("helmet_seam", *sweep(seam, ellipse(0.0040, 0.0032, 6), normals=[Vector(((p - CR_C).x / HR.x ** 2, (p - CR_C).y / HR.y ** 2, (p - CR_C).z / HR.z ** 2)) for p in seam], lift=0.0012), 'LEATHER_D')
# goggles pushed up on the helmet: brass cups, red lenses, a bridge, a strap round the back
GOG = []
for sx in (1, -1):
    p, n = front_hit(helm_bvh, sx * 0.044, 0.112)
    gax = (n + Vector((0, -0.35, 0))).normalized(); gu = gax.cross(Vector((0, 0, 1))).normalized()
    gv_, gf_, gk_, _ = lathe(p - gax * 0.004, gax, [(0.0250, 0.0), (0.0290, 0.003), (0.0290, 0.016), (0.0262, 0.0195), (0.0215, 0.0180)], 24, ['BRASS'] * 4, u=gu)
    hadd("goggle_cup", gv_, gf_, gk_, smooth=False)
    lc = p - gax * 0.004; gvv = gu.cross(gax).normalized()
    lv_, lf_, lk_, _ = lathe(lc, gax, [(0.0217, 0.0176), (0.0150, 0.0203), (0.0, 0.0213)], 20, ['GLENS', 'GLENS'], u=gu)
    hadd("goggle_lens", lv_, lf_, lk_, frame=(lc, gu, gvv if gvv.z > 0 else -gvv, 0.0217, 0.0217))
    GOG.append((lc, gax, gu))
(lcL, gaL, guL), (lcR, gaR, guR) = GOG
b0_ = lcL + gaL * 0.010 + Vector((-0.027, 0, 0)); b1_ = lcR + gaR * 0.010 + Vector((0.027, 0, 0))
hadd("goggle_bridge", *tube(b0_, b1_, 0.0042, 0.0042, 8, mid=0.15), 'BRASS')
spts, snrm = [], []
for a_ in np.linspace(-math.pi / 2 + 0.66, -math.pi / 2 - 0.66 + 2 * math.pi, 34):
    d_ = Vector((math.cos(a_), math.sin(a_), 0.0)); o_ = Vector((CR_C.x, CR_C.y, 0.100 - 0.012 * smoothstep(0.5, 1.0, abs(math.sin(a_ / 2 + math.pi / 4))))) + d_ * 0.4
    hit = helm_bvh.ray_cast(o_, -d_, 0.5)
    if hit[0] is not None: spts.append(Vector(hit[0])); snrm.append(Vector(hit[1]))
hadd("goggle_strap", *sweep(spts, rect(0.0095, 0.0022), normals=snrm, lift=0.0024), 'LEATHER_D')
# the chin strap: hanging loose on the left, a stub with its buckle on the right
cs_pts = [Vector((0.101, -0.002, -0.040)), Vector((0.100, -0.014, -0.078)), Vector((0.093, -0.030, -0.116)), Vector((0.084, -0.044, -0.150))]
hadd("chin_strap", *sweep(dense(cs_pts, 8), rect(0.0090, 0.0020), normals=[Vector((1, -0.15, 0))] * 8), 'LEATHER_D')
hadd("chin_buckle", *box(cs_pts[-1] + Vector((0.002, -0.002, -0.004)), Vector((1, -0.15, 0)).normalized(), 0.022, 0.014, 0.004, up=(cs_pts[-1] - cs_pts[-2]).normalized()), 'BRASS', smooth=False)
hadd("chin_stub", *sweep([Vector((-0.101, -0.002, -0.040)), Vector((-0.099, -0.012, -0.064))], rect(0.0090, 0.0020), normals=[Vector((-1, -0.15, 0))] * 2), 'LEATHER_D')
hadd("chin_stub_buckle", *box(Vector((-0.102, -0.014, -0.068)), Vector((-1, -0.15, 0)).normalized(), 0.022, 0.016, 0.004), 'BRASS', smooth=False)
# the bat ears: a cupped membrane (dark red in front, skin behind) on three ribs, through the helmet's slits
EAR_ROOT, EAR_TIP = Vector((0.098, 0.010, 0.040)), Vector((0.310, 0.036, 0.370))     # left ear; tips ~62 cm apart, 37 cm above DH_C
def ear(sx):
    R = Vector((sx * EAR_ROOT.x, EAR_ROOT.y, EAR_ROOT.z)); T = Vector((sx * EAR_TIP.x, EAR_TIP.y, EAR_TIP.z))
    a = (T - R).normalized(); L = (T - R).length
    nf = Vector((0, -1, 0)); nf = (nf - a * nf.dot(a)).normalized()          # the ear's front (its concave side)
    b = a.cross(nf).normalized()
    if b.x * sx < 0: b = -b                                                  # across: toward the trailing (outer, lower) edge
    def w_lead(s): return -(0.016 * max(0.0, 1 - s) ** 1.2 + 0.004 * math.sin(math.pi * max(0.0, s)))
    def w_trail(s):
        s_ = max(0.0, s)
        return (0.020 * (1 - s_) + 0.094 * math.sin(math.pi * min(1.0, s_ / 0.92)) ** 0.9 * (1 - s_) ** 0.30
                - 0.034 * math.exp(-((s_ - 0.62) / 0.06) ** 2))
    def P(s, w):
        lo, hi = w_lead(s), w_trail(s); mid = (lo + hi) / 2; half = max(1e-4, (hi - lo) / 2)
        cup = 0.022 * math.sin(math.pi * max(0.0, min(1.0, s))) ** 0.8 * max(0.0, 1 - ((w - mid) / half) ** 2)
        return R + a * (s * L) + b * w - nf * cup
    NS, NW = 15, 8; ss = [-0.12 + (0.985 + 0.12) * (i / (NS - 1)) ** 0.95 for i in range(NS)]
    rows = []
    for s in ss:
        lo, hi = w_lead(s), w_trail(s); ws = [lo + (hi - lo) * j / (NW - 1) for j in range(NW)]
        th_ = 0.0026 * (1 - 0.5 * max(0.0, s))
        fr_ = [P(s, w) + nf * th_ for w in ws]; bk_ = [P(s, w) - nf * th_ for w in ws[::-1]]
        rows.append(fr_ + bk_)
    m = 2 * NW; ev_, ef_ = ring_loft(rows); ek_ = []
    for i in range(NS - 1):
        for j in range(m): ek_.append('EAR_IN' if j < NW - 1 else 'EAR_OUT')
    tip = len(ev_); ev_.append(T)                    # close the tip with a fan
    for j in range(m): ef_.append((((NS - 1) * m) + j, ((NS - 1) * m) + (j + 1) % m, tip)); ek_.append('EAR_IN' if j < NW - 1 else 'EAR_OUT')
    hadd("ear", ev_, ef_, ek_, recalc=False)
    for sa, sb, wa in ((0.04, 0.985, 0.30), (0.04, 0.42, 1.0), (0.04, 0.80, 1.0)):   # ribs on the back: to the tip and two trailing points
        rp, rn = [], []
        for t in np.linspace(0, 1, 10):
            s = sa + (sb - sa) * t; lo, hi = w_lead(s), w_trail(s); w = lo + (hi - lo) * (0.35 + (wa - 0.35) * t) if wa < 1 else lo + (hi - lo) * (0.35 + 0.63 * t)
            rp.append(P(s, w) - nf * 0.0030); rn.append(-nf)
        hadd("ear_rib", *sweep(rp, ellipse(0.0042, 0.0034, 5), normals=rn, scale=[1.0 - 0.65 * t for t in np.linspace(0, 1, 10)]), 'EAR_OUT')
    # the slit's leather edging where the ear passes through the helmet
    s0 = 0.03; lo, hi = w_lead(s0), w_trail(s0)
    loop = [P(s0, lo + (hi - lo) * j / 7) + nf * 0.0065 for j in range(8)] + [P(s0, hi - (hi - lo) * j / 7) - nf * 0.0065 for j in range(8)]
    hadd("ear_slit", *sweep(loop + loop[:1], ellipse(0.0040, 0.0035, 4), normals=[a] * 17, caps=False), 'LEATHER_D')
    return R, T, a, nf, b
EARS = [ear(1), ear(-1)]
for h in hparts:
    add(h['name'], [p + C for p in h['v']], h['f'], h['k'], smooth=h['smooth'], w=h['w'], recalc=h['recalc'],
        frame=(h['frame'][0] + C,) + tuple(h['frame'][1:]) if h['frame'] else None, head=True)
HEAD_NAMES = {h['name'] for h in hparts}

# ---------------- the flying copy's extras (head-local, static head only): bolt + hex nut, propeller ----------------
NY = neck_c(0.52).y - C.y                            # the neck's axis under the head
add("hex_nut", *cyl(Vector((0, NY, -0.148)), Vector((0, NY, -0.118)), 0.041, 6), 'BRASS', smooth=False, dest=fparts, head=True)
add("nut_washer", *cyl(Vector((0, NY, -0.152)), Vector((0, NY, -0.146)), 0.034, 20), 'STEEL', smooth=False, dest=fparts, head=True)
add("bolt", *cyl(Vector((0, NY, -0.150)), Vector((0, NY, -0.252)), 0.0215, 16), 'STEEL', dest=fparts, head=True)
for k in range(7):
    zt = -0.160 - 0.0125 * k
    add("bolt_thread", *sweep([Vector((math.cos(ang(j, 16)) * 0.0222, NY + math.sin(ang(j, 16)) * 0.0222, zt - 0.003 * j / 16)) for j in range(16)],
                              ellipse(0.0026, 0.0026, 4), closed=True), 'STEEL', dest=fparts, head=True)
bv_, bf_, bk_, _ = lathe(Vector((0, NY, -0.252)), Vector((0, 0, -1)), [(0.0215, 0.0), (0.0170, 0.006), (0.0, 0.007)], 16, ['STEEL', 'STEEL'])
add("bolt_tip", bv_, bf_, bk_, smooth=False, dest=fparts, head=True)
Z_CROWN = CR_C.z + HR.z                              # the helmet's top (head-local)
Z_PROP = Z_CROWN + 0.070; R_DISC = 0.170          # the mast lifts the disc clear of the ears' leading edges
mv_, mf_, mk_, _ = lathe(Vector((0, 0, Z_CROWN - 0.004)), Vector((0, 0, 1)), [(0.0165, 0.0), (0.0165, 0.004), (0.0100, 0.008), (0.0065, 0.010), (0.0065, 0.064)], 12,
                         ['BRASS', 'BRASS', 'BRASS', 'STEEL'])
add("prop_mast", mv_, mf_, mk_, smooth=False, dest=fparts, head=True)
sp_v, sp_f, sp_k, _ = lathe(Vector((0, 0, Z_PROP - 0.009)), Vector((0, 0, 1)), [(0.0175, 0.0), (0.0175, 0.010), (0.0130, 0.022), (0.0060, 0.031), (0.0, 0.034)], 18, ['SPINNER'] * 4)
add("prop_spinner", sp_v, sp_f, sp_k, dest=fparts, head=True)
for bsgn in (1, -1):                                 # two twisted blades along the head's front-back line (clear of the ears)
    bv, bf, bk = [], [], []
    st = np.linspace(0.016, 0.160, 9)
    for i, r_ in enumerate(st):
        s = (r_ - 0.016) / 0.144; tw = math.radians(24 - 14 * s); ch = 0.030 - 0.010 * s + 0.006 * math.sin(math.pi * s); th_ = 0.0022 * (1 - 0.4 * s)
        cdir = Vector((math.cos(tw), 0, math.sin(tw))); tdir = Vector((-math.sin(tw), 0, math.cos(tw)))
        c = Vector((0, bsgn * r_, Z_PROP))
        for e1, e2 in ((-1, -1), (1, -1), (1, 1), (-1, 1)): bv.append(c + cdir * (e1 * ch / 2) * bsgn + tdir * (e2 * th_))
    for i in range(len(st) - 1):
        for j in range(4):
            j2 = (j + 1) % 4; bf.append((i * 4 + j, i * 4 + j2, (i + 1) * 4 + j2, (i + 1) * 4 + j)); bk.append('PROPTIP' if st[i] > 0.128 else 'PROP')
    bf.append((0, 3, 2, 1)); bk.append('PROP'); n4 = (len(st) - 1) * 4; bf.append((n4, n4 + 1, n4 + 2, n4 + 3)); bk.append('PROPTIP')
    add("prop_blade", bv, bf, bk, smooth=False, dest=fparts, head=True)

# ---------------- checks on the raw geometry ----------------
dirs = [Vector((x, y, z)).normalized() for x in (-1, 0, 1) for y in (-1, 0, 1) for z in (-1, 0, 1) if (x, y, z) != (0, 0, 0)]
enc_v, enc_f = merged(HEAD_NAMES | {"neck_skin", "scarf_wrap", "collar", "coat_torso"}, parts)
enc = BVHTree.FromPolygons(enc_v, enc_f)
stump_pts = merged(set(STUMP), parts)[0]
exp_ = [(p, [d for d in dirs if enc.ray_cast(p + d * 1e-4, d, 2.0)[0] is None]) for p in stump_pts]; exp_ = [(p, ds) for p, ds in exp_ if ds]
print("CHECK socket verts visible while the head is on (a ray escapes):", len(exp_), "of", len(stump_pts), "(want 0)",
      [(round(p.z, 4), round(math.degrees(math.atan2(p.y - neck_c(p.z).y, p.x))), [tuple(int(round(c)) for c in ds[0])]) for p, ds in exp_[:6]])
print("STUMP z", round(min(p.z for p in stump_pts), 4), "..", round(max(p.z for p in stump_pts), 4), "| eye bones z", round(B('LeftEye').z, 4))
ear_v = [p for q in hparts if q['name'] == 'ear' for p in q['v']]
xs_ = [p.x for p in ear_v]; zt_ = max(p.z for p in ear_v)
print("EARS tip to tip %.3f m, top %.3f m above DH_C (world z %.3f), root..tip length %.3f" % (max(xs_) - min(xs_), zt_, zt_ + C.z, (EAR_TIP - EAR_ROOT).length))
near = [math.hypot(p.x, p.y) for p in ear_v if abs(p.z - Z_PROP) < 0.012]
print("CHECK ears' closest approach to the propeller axis at the disc's height (disc r %.3f): %.3f m" % (R_DISC, min(near) if near else 9))
blade_v = [p for q in fparts if q['name'] == 'prop_blade' for p in q['v']]
eb = BVHTree.FromPolygons(*merged({"ear"}, hparts))
print("CHECK blades' closest approach to the ears: %.3f m" % min(eb.find_nearest(p)[3] for p in blade_v))

# ---------------- texture atlas: a fresh one, every kind painted into its own patch ----------------
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
def metal(c, rough, seed):
    def fn(uu, vv):
        sh = uu.shape; br = vnoise(uu * 0.05, vv, 120, seed)
        return np.clip(np.array(c) * (0.90 + 0.14 * br)[..., None], 0, 1), Z3(sh), rough + 0.06 * (br - 0.5), np.ones(sh)
    return fn
SUIT_C = np.array((0.355, 0.365, 0.205))
def fabric(c, seed, stains=True, var=0.20):
    def fn(uu, vv):
        sh = uu.shape; col = np.array(c) * (0.88 + var * fbm(uu, vv, 6, seed, 4) + 0.05 * vnoise(uu, vv, 90, seed + 3))[..., None]
        ro = np.full(sh, 0.88)
        if stains:                                   # oil and grease: dark, a little shiny
            m = np.clip((fbm(uu, vv, 6, seed + 9, 3) - 0.68) / 0.06, 0, 1)
            col = col * (1 - 0.30 * m[..., None]); ro = ro - 0.25 * m
            b = np.clip((fbm(uu, vv, 3, seed + 21, 2) - 0.55) / 0.15, 0, 1)[..., None] * 0.18   # sun-bleached patches
            col = col * (1 - b) + np.array((0.55, 0.53, 0.40)) * b
        return np.clip(col, 0, 1), Z3(sh), ro, np.zeros(sh)
    return fn
def torn(uu, vv):
    sh = uu.shape; col = SUIT_C * 0.80 * (0.85 + 0.3 * fbm(uu, vv, 9, 61))[..., None]
    th = vnoise(uu, vv, 48, 62) > 0.74; col[th] = (0.62, 0.58, 0.44)                   # frayed threads
    return np.clip(col, 0, 1), Z3(sh), np.full(sh, 0.92), np.zeros(sh)
SKIN_C = np.array((0.415, 0.485, 0.335))
def skin(seed, veins=False, base=SKIN_C):
    def fn(uu, vv):
        sh = uu.shape; col = np.array(base) * (0.84 + 0.26 * fbm(uu, vv, 5, seed, 4))[..., None]
        sp = np.clip((vnoise(uu, vv, 58, seed + 5) - 0.74) / 0.07, 0, 1)[..., None]         # darker spots
        col = col * (1 - 0.24 * sp)
        ro = 0.52 + 0.12 * fbm(uu, vv, 9, seed + 7)
        if veins:
            vn = np.abs(np.sin(2 * np.pi * (uu * 9 + 1.6 * fbm(uu, vv, 3, seed + 11, 2)))) < 0.10
            col[vn] *= 0.72
        return np.clip(col, 0, 1), Z3(sh), ro, np.zeros(sh)
    return fn
FACE_W, FACE_H, FACE_Z = 0.240, 0.290, -0.010        # the face texture: a front projection over x +-0.12, z -0.155..0.135 (head-local)
def face_tex(uu, vv):
    sh = uu.shape; x = (uu - 0.5) * FACE_W; z = FACE_Z + (vv - 0.5) * FACE_H
    col, _, ro, mt = skin(31)(uu, vv)
    for ex in (-0.046, 0.046):                       # sunken, darker skin round the eyes
        d = np.hypot((x - ex) / 1.15, z - 0.0); col *= (1 - 0.30 * np.exp(-((d - 0.036) / 0.010) ** 2))[..., None]
    mz = np.exp(-((x / 0.060) ** 2 + ((z + 0.066) / 0.034) ** 2))[..., None] * 0.22        # a paler muzzle round the grin
    col = col * (1 - mz) + np.array((0.60, 0.64, 0.46)) * mz
    for sx_ in (-1, 1):                              # frown lines between the brows, crow's feet
        fr = (np.abs(x - sx_ * 0.0055 - 0.004 * np.sin(z * 200)) < 0.0008) & (z > 0.010) & (z < 0.036); col[fr] *= 0.62
        for k in range(3):
            cf = np.abs((z - (0.006 - 0.007 * k)) - 0.25 * (sx_ * x - 0.083)) < 0.0007
            col[cf & (sx_ * x > 0.080) & (sx_ * x < 0.097)] *= 0.66
    col *= (1 - 0.25 * np.exp(-((x / 0.022) ** 2 + ((z + 0.058) / 0.010) ** 2)))[..., None]   # shadow under the nose
    return np.clip(col, 0, 1), Z3(sh), ro, mt
def eye_tex(uu, vv):
    sh = uu.shape; x = uu * 2 - 1; y = vv * 2 - 1; r = np.hypot(x, y)
    g = np.clip(r / 0.66, 0, 1)[..., None]
    col = np.array((1.0, 0.42, 0.12)) * (1 - g) + np.array((0.86, 0.06, 0.03)) * g             # bright red even unlit
    emi = np.array((1.0, 0.16, 0.04)) * (0.45 + 0.55 * np.clip(1 - r / 0.66, 0, 1))[..., None]
    rays = 0.88 + 0.12 * np.cos(np.arctan2(y, x) * 26)[..., None]; col = col * rays
    lim = (r > 0.60) & (r < 0.70); col[lim] = (0.40, 0.0, 0.0); emi[lim] *= 0.4                # limbal ring
    outer = r >= 0.70; col[outer] = (0.55, 0.035, 0.03); emi[outer] = (0.40, 0.02, 0.0)         # all-red "white"
    pw = 0.085 * np.sqrt(np.clip(1 - (y / 0.56) ** 2, 0, 1)); pupil = np.abs(x) < pw
    col[pupil] = (0.01, 0.0, 0.0); emi[pupil] = 0
    gl = np.hypot(x + 0.30, y - 0.34) < 0.11; col[gl] = (1.0, 0.95, 0.9); emi[gl] = (0.9, 0.8, 0.75)
    return np.clip(col, 0, 1), np.clip(emi, 0, 1), np.full(sh, 0.10), np.zeros(sh)
def glens_tex(uu, vv):
    sh = uu.shape; x = uu * 2 - 1; y = vv * 2 - 1; r = np.hypot(x, y)
    col = np.array((0.42, 0.05, 0.035)) * (0.75 + 0.25 * (1 - r))[..., None]; emi = np.array((0.30, 0.03, 0.0)) * np.clip(1 - r, 0, 1)[..., None]
    hl = (np.abs(np.hypot(x + 0.15, y + 0.15) - 0.62) < 0.07) & (y > 0.05); col[hl] = (0.95, 0.75, 0.70)
    return np.clip(col, 0, 1), np.clip(emi, 0, 1), np.full(sh, 0.06), np.zeros(sh)
def leather(c, seed):
    def fn(uu, vv):
        sh = uu.shape; col = np.array(c) * (0.80 + 0.32 * fbm(uu, vv, 6, seed, 4))[..., None]
        cr = np.abs(fbm(uu, vv, 14, seed + 4, 2) - 0.5) < 0.012; col[cr] *= 0.70                 # creases
        wr = np.clip((fbm(uu, vv, 9, seed + 8, 3) - 0.62) / 0.10, 0, 1)[..., None] * 0.35        # rubbed-pale wear
        col = col * (1 - wr) + np.array(c) * 1.55 * wr
        return np.clip(col, 0, 1), Z3(sh), 0.58 + 0.12 * fbm(uu, vv, 7, seed + 2), np.zeros(sh)
    return fn
def scarf(uu, vv):
    sh = uu.shape; f = fbm(uu, vv, 7, 71, 4); col = np.array((0.74, 0.045, 0.045)) * (0.78 + 0.34 * f)[..., None]
    return np.clip(col, 0, 1), Z3(sh), 0.42 + 0.15 * (1 - f), np.zeros(sh)
GLYPH = {'G': [".###.", "#...#", "#....", "#.###", "#...#", "#...#", ".###."], 'R': ["####.", "#...#", "#...#", "####.", "#.#..", "#..#.", "#...#"],
         'E': ["#####", "#....", "#....", "####.", "#....", "#....", "#####"], 'M': ["#...#", "##.##", "#.#.#", "#.#.#", "#...#", "#...#", "#...#"],
         'L': ["#....", "#....", "#....", "#....", "#....", "#....", "#####"], 'I': [".###.", "..#..", "..#..", "..#..", "..#..", "..#..", ".###."],
         'N': ["#...#", "##..#", "#.#.#", "#..##", "#...#", "#...#", "#...#"], 'D': ["####.", "#...#", "#...#", "#...#", "#...#", "#...#", "####."],
         'Y': ["#...#", "#...#", ".#.#.", "..#..", "..#..", "..#..", "..#.."], ' ': ["....."] * 7}
def led_text(x, z, text, x0, z0, pitch):
    """LED dot-matrix text (5x7 glyphs, one column gap) with its top-left dot centre at (x0, z0): (on, off) dot masks"""
    on = np.zeros(x.shape, bool); off = np.zeros(x.shape, bool)
    for ci, ch in enumerate(text):
        for ry, line in enumerate(GLYPH[ch]):
            for rx, c_ in enumerate(line):
                d = np.hypot(x - (x0 + (ci * 6 + rx) * pitch), z - (z0 - ry * pitch)) < pitch * 0.38
                if c_ == '#': on |= d
                else: off |= d
    return on, off
TAPE_W, TAPE_H = 0.112, 0.027
def nametape_tex(uu, vv):
    sh = uu.shape; x = (uu - 0.5) * TAPE_W; z = (vv - 0.5) * TAPE_H
    col = np.array((0.15, 0.16, 0.095)) * (0.9 + 0.2 * fbm(uu, vv, 8, 81))[..., None]
    st = ((np.abs(np.abs(x) - (TAPE_W / 2 - 0.0025)) < 0.0005) | (np.abs(np.abs(z) - (TAPE_H / 2 - 0.0022)) < 0.0005)) & (np.abs((x * 900).astype(int)) % 3 != 0)
    col[st] = (0.40, 0.40, 0.28)                     # stitching round the tape
    pitch = 0.0024; on, off = led_text(x, z, "GREMLIN", -(41 * pitch) / 2 + pitch / 2, 3 * pitch, pitch)
    col[off] = (0.20, 0.21, 0.13); col[on] = (0.93, 0.88, 0.68)
    return np.clip(col, 0, 1), Z3(sh), np.full(sh, 0.85), np.zeros(sh)
def noseart_tex(uu, vv):
    """RED EYE on the back: a slit-pupil eye over LED letters, painted on the coverall and worn"""
    sh = uu.shape; X = (uu - 0.5) * 2 * ART_X; Z = ART_Z0 + vv * (ART_Z1 - ART_Z0)          # X: the viewer's right, seen from behind
    col = SUIT_C * (0.93 + 0.10 * fbm(uu, vv, 6, 91, 4))[..., None]; ro = np.full(sh, 0.88)
    wear = fbm(uu, vv, 22, 92, 3) > 0.73             # paint chipped off here
    ez = 0.322; ew, eh = 0.084, 0.043
    lid_top = ez + eh * np.sqrt(np.clip(1 - (X / ew) ** 2, 0, 1)); lid_bot = ez - 0.85 * eh * np.sqrt(np.clip(1 - (X / ew) ** 2, 0, 1))
    eye = (np.abs(X) < ew) & (Z < lid_top) & (Z > lid_bot)
    outline = (np.abs(X) < ew + 0.006) & (Z < lid_top + 0.006) & (Z > lid_bot - 0.006) & ~eye
    ir = np.hypot(X, Z - ez); pupil = (np.abs(X) < 0.0085 * np.sqrt(np.clip(1 - ((Z - ez) / 0.038) ** 2, 0, 1))) & eye
    paint = np.zeros(sh + (3,)); m = np.zeros(sh, bool)
    paint[outline] = (0.05, 0.03, 0.03); m |= outline
    paint[eye] = (0.80, 0.07, 0.05); m |= eye
    ring = eye & (ir < 0.040) & (ir > 0.034); paint[ring] = (0.45, 0.02, 0.02)
    paint[eye & (ir < 0.034)] = (0.95, 0.30, 0.08)
    paint[pupil] = (0.03, 0.01, 0.01)
    gl = np.hypot(X + 0.014, Z - (ez + 0.014)) < 0.0055; paint[gl & eye] = (0.98, 0.92, 0.80)
    rays = eye & (ir >= 0.040) & (np.abs(np.sin(np.arctan2(Z - ez, X) * 9)) > 0.93); paint[rays] = (0.62, 0.04, 0.03)
    pitch = 0.0062; on, off = led_text(X, Z, "RED EYE", -(41 * pitch) / 2 + pitch / 2, 0.232, pitch)
    paint[on] = (0.93, 0.88, 0.70); m |= on
    m &= ~wear
    col[m] = paint[m]; ro[m] = 0.62
    return np.clip(col, 0, 1), Z3(sh), ro, np.zeros(sh)
SPEC = {   # kind: (painter, cells of 16 px, textured = the UVs use the whole patch)
    'SUIT': (fabric(tuple(SUIT_C), 1), 32, False),
    'SUIT_DARK': (fabric((0.225, 0.235, 0.130), 2, stains=False), 8, False),
    'PATCH': (fabric((0.415, 0.385, 0.235), 3), 8, False),
    'TORN': (torn, 6, False),
    'CAVITY': (flat((0.035, 0.035, 0.030), 0.9), 3, False),
    'SKIN': (skin(4), 24, False),
    'FACE': (face_tex, 40, True),
    'EAR_IN': (skin(41, veins=True, base=(0.42, 0.13, 0.12)), 12, False),
    'EAR_OUT': (skin(42, veins=True), 12, False),
    'EYE': (eye_tex, 12, True),
    'CLAW': (flat((0.065, 0.055, 0.048), 0.22, 0.0, 0.10), 3, False),
    'TOOTH': (flat((0.88, 0.84, 0.66), 0.35, 0.0, 0.05), 3, False),
    'MOUTH': (flat((0.10, 0.014, 0.014), 0.7), 3, False),
    'LEATHER': (leather((0.38, 0.215, 0.105), 5), 12, False),
    'LEATHER_D': (leather((0.19, 0.100, 0.050), 6), 6, False),
    'BRASS': (metal((0.84, 0.64, 0.30), 0.30, 7), 4, False),
    'STEEL': (metal((0.75, 0.75, 0.77), 0.28, 8), 4, False),
    'BRASS_D': (metal((0.36, 0.27, 0.13), 0.55, 10), 3, False),
    'GLENS': (glens_tex, 8, True),
    'SCARF': (scarf, 10, False),
    'NAMETAPE': (nametape_tex, 16, True),
    'NOSEART': (noseart_tex, 48, True),
    'SPINNER': (flat((0.78, 0.06, 0.05), 0.30, 0.0, 0.05), 3, False),
    'PROP': (flat((0.42, 0.20, 0.09), 0.45, 0.0, 0.10), 3, False),
    'PROPTIP': (flat((0.92, 0.92, 0.94), 0.40, 0.0, 0.03), 3, False),
}
TEXTURED_FRAME = {'EYE', 'GLENS', 'NAMETAPE'}
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
for k, img in imgs.items():                          # skullbuck's own paint is all gone with its body: start from black
    arrs[k] = np.zeros((img.size[1], img.size[0], 4), np.float32); arrs[k][:, :, 3] = 1
arrs['normal'][:, :] = (0.5, 0.5, 1.0, 1.0); arrs['orm'][:, :, 0] = 1; arrs['orm'][:, :, 1] = 0.9
em = bpy.data.images.new('final_emissive', 1024, 1024, alpha=False); arrs['emissive'] = np.zeros((1024, 1024, 4), np.float32); arrs['emissive'][:, :, 3] = 1
G = 128
SPEC_ALL = SPEC; SPEC = {k: v for k, v in SPEC_ALL.items() if k not in ('SPINNER', 'PROP', 'PROPTIP')}
patch = build_atlas(arrs, np.zeros((G, G), bool), G)
SPEC = SPEC_ALL
for k, img in imgs.items():
    img.pixels.foreach_set(arrs[k].ravel()); img.update(); img.pack()
em.pixels.foreach_set(arrs['emissive'].ravel()); em.update(); em.pack()
print("PATCHES", {k: [round(t, 4) for t in v] for k, v in patch.items()})

# ---------------- objects, UVs, weights ----------------
def proj(kind, P, part, nrm):
    """(uu, vv) in 0..1 inside the kind's patch for world point P on a face with normal nrm"""
    if kind in TEXTURED_FRAME and part['frame']:
        c, u, v, sx_, sy_ = part['frame']; d = P - c; return 0.5 + d.dot(u) / (2 * sx_), 0.5 + d.dot(v) / (2 * sy_)
    if kind == 'FACE': L = P - C; return 0.5 + L.x / FACE_W, 0.5 + (L.z - FACE_Z) / FACE_H
    if kind == 'NOSEART': return 0.5 - P.x / (2 * ART_X), (P.z - ART_Z0) / (ART_Z1 - ART_Z0)      # read from behind
    Q = (P - C) if part['head'] else P               # elsewhere: a planar projection along the face's main axis
    span, zc = (0.80, 0.12) if part['head'] else (1.90, -0.20)
    ax = max(range(3), key=lambda i: abs(nrm[i]))
    a_, b_ = (Q.y, Q.z - zc) if ax == 0 else (Q.x, Q.z - zc) if ax == 1 else (Q.x, Q.y)
    return 0.5 + a_ / span, 0.5 + b_ / span
def set_uv(m, poly, kinds_of, part, patch, offset):
    kind = kinds_of(poly); u0, v0, u1, v1 = patch[kind]; textured = SPEC[kind][2]
    for li in poly.loop_indices:
        P = m.vertices[m.loops[li].vertex_index].co + offset
        uu, vv = proj(kind, P, part, poly.normal); uu = min(1, max(0, uu)); vv = min(1, max(0, vv))
        m.uv_layers.active.data[li].uv = (u0 + (u1 - u0) * uu, v0 + (v1 - v0) * vv) if textured else \
                                         (u0 + (u1 - u0) * (0.15 + 0.7 * uu), v0 + (v1 - v0) * (0.15 + 0.7 * vv))
def make_obj(part, patch, offset=Vector()):
    m = bpy.data.meshes.new(part['name']); m.from_pydata([tuple(p) for p in part['v']], [], part['f']); m.update()
    o = bpy.data.objects.new(part['name'], m); bpy.context.scene.collection.objects.link(o)
    for p_ in m.polygons: p_.use_smooth = part['smooth']
    m.uv_layers.new(name="UVMap")
    for poly in m.polygons: set_uv(m, poly, lambda pl: part['k'][pl.index], part, patch, offset)
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
bmesh.ops.delete(sbm, geom=[v for v in sbm.verts if D[v.index] in HEADB or v.co.z < -0.64], context='VERTS'); sbm.to_mesh(src.data); sbm.free()
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
    # skullbuck's neckline carries ~40 % Head: without this the collar would half-collapse while the head flies
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

# ---------------- static head (own file, own textures; + the bolt, nut and propeller) ----------------
HG = 64; harrs = {'color': np.zeros((1024, 1024, 4), np.float32), 'emissive': np.zeros((1024, 1024, 4), np.float32), 'orm': np.zeros((1024, 1024, 4), np.float32)}
for k in harrs: harrs[k][:, :, 3] = 1
SPEC = {k: (fn, max(3, int(n * 0.8)) if k == 'FACE' else n, tx) for k, (fn, n, tx) in SPEC_ALL.items() if k in {k for h in hparts + fparts for k in h['k']}}
hpatch = build_atlas(harrs, np.zeros((HG, HG), bool), HG)
SPEC = SPEC_ALL
hobjs = []
for h in hparts + fparts:
    o = make_obj(dict(h, frame=(h['frame'][0] + C,) + tuple(h['frame'][1:]) if h['frame'] else None), hpatch, offset=C); hobjs.append(o)
def mkimg(name, a, noncolor=False):
    im = bpy.data.images.new(name, a.shape[1], a.shape[0], alpha=False); im.pixels.foreach_set(a.ravel()); im.update(); im.pack()
    if noncolor: im.colorspace_settings.name = 'Non-Color'
    return im
imC = mkimg('gremlin_head_color', harrs['color']); imE = mkimg('gremlin_head_emissive', harrs['emissive']); imO = mkimg('gremlin_head_orm', harrs['orm'], True)
matS = bpy.data.materials.new('GremlinHead'); matS.use_nodes = True; nt = matS.node_tree; bsdf = nt.nodes['Principled BSDF']
def texnode(nt_, im):
    n_ = nt_.nodes.new('ShaderNodeTexImage'); n_.image = im; return n_
nt.links.new(texnode(nt, imC).outputs['Color'], bsdf.inputs['Base Color'])
nt.links.new(texnode(nt, imE).outputs['Color'], bsdf.inputs['Emission Color']); bsdf.inputs['Emission Strength'].default_value = 1.0
sep = nt.nodes.new('ShaderNodeSeparateColor'); nt.links.new(texnode(nt, imO).outputs['Color'], sep.inputs['Color'])
nt.links.new(sep.outputs['Green'], bsdf.inputs['Roughness']); nt.links.new(sep.outputs['Blue'], bsdf.inputs['Metallic'])
for o in hobjs: o.data.materials.append(matS)
if not NO_BLUR:
    # the propeller's blur: a thin closed disc (single-sided faces, so either side shows without a two-sided material), faint grey
    # with darker blade streaks near the rim; alpha 0.22 -> alphaMode BLEND (glTFRuntime's Translucent instance, untested on an avatar)
    dv, df = cyl(Vector((0, 0, Z_PROP - 0.0015)), Vector((0, 0, Z_PROP + 0.0015)), R_DISC, 48)
    md_ = bpy.data.meshes.new("prop_blur"); md_.from_pydata([tuple(p) for p in dv], [], df); md_.update()
    ob_ = bpy.data.objects.new("prop_blur", md_); bpy.context.scene.collection.objects.link(ob_)
    uvb = md_.uv_layers.new(name="UVMap")
    for poly in md_.polygons:
        for li in poly.loop_indices:
            p_ = md_.vertices[md_.loops[li].vertex_index].co; uvb.data[li].uv = (0.5 + p_.x / (2 * R_DISC) * 0.98, 0.5 + p_.y / (2 * R_DISC) * 0.98)
    yy, xx = np.mgrid[0:256, 0:256]; rr = np.hypot((xx + 0.5) / 128 - 1, (yy + 0.5) / 128 - 1)
    band = 0.55 + 0.45 * np.clip((rr - 0.2) / 0.75, 0, 1) * (0.75 + 0.25 * np.cos(rr * 60)); bl = np.ones((256, 256, 4), np.float32)
    bl[:, :, :3] = (np.array((0.80, 0.80, 0.84)) * band[..., None]); bl[rr > 0.985, :3] = (0.92, 0.92, 0.95)
    imB = mkimg('prop_blur_color', bl)
    matB_ = bpy.data.materials.new('PropBlur'); matB_.use_nodes = True; ntb = matB_.node_tree; pb_ = ntb.nodes['Principled BSDF']
    ntb.links.new(texnode(ntb, imB).outputs['Color'], pb_.inputs['Base Color'])
    pb_.inputs['Alpha'].default_value = 0.22; pb_.inputs['Roughness'].default_value = 0.5
    matB_.surface_render_method = 'BLENDED'; matB_.use_backface_culling = True
    md_.materials.append(matB_); hobjs.append(ob_)
bpy.ops.object.select_all(action='DESELECT')
for o in hobjs: o.select_set(True)
bpy.context.view_layer.objects.active = hobjs[0]; bpy.ops.object.join(); st = hobjs[0]; st.name = "GremlinHead_Static"; st.data.name = "GremlinHead_Static"
print("STATIC HEAD tris", sum(len(p.vertices) - 2 for p in st.data.polygons), "| materials", [m.name for m in st.data.materials], "| blur disc", not NO_BLUR)
matB = me.data.materials[0]; ntB = matB.node_tree; bB = ntB.nodes['Principled BSDF']     # emissive on the body material too
tEB = ntB.nodes.new('ShaderNodeTexImage'); tEB.image = em; ntB.links.new(tEB.outputs['Color'], bB.inputs['Emission Color']); bB.inputs['Emission Strength'].default_value = 1.0

# ---------------- the surviving trousers: new UVs into this atlas, and no thigh weight under the belt ----------------
for poly in me.data.polygons:
    if all(i in keep_kind for i in poly.vertices):
        set_uv(me.data, poly, lambda pl: keep_kind[pl.vertices[0]], dict(frame=None, head=False), patch, Vector())
gidx = {g.name: g for g in me.vertex_groups}; gH = gidx['Hips']; faded = 0
for i in keep_kind:
    v = me.data.vertices[i]; sv = smoothstep(-0.13, -0.05, v.co.z)
    if sv <= 0: continue
    moved = 0.0
    for g in list(v.groups):
        gname = me.vertex_groups[g.group].name
        if 'Leg' in gname: moved += g.weight * sv; me.vertex_groups[g.group].add([i], g.weight * (1 - sv), 'REPLACE')
    if moved > 0:
        hw_ = next((g.weight for g in v.groups if g.group == gH.index), 0.0); gH.add([i], hw_ + moved, 'REPLACE'); faded += 1
print("TROUSERS: leg weight faded into Hips on", faded, "verts above z -0.13")

# ---------------- delete the old body, join, DH bones, export ----------------
tri = lambda o: sum(len(p.vertices) - 2 for p in o.data.polygons)
groups = {}
for o, part in zip(new, parts):
    nm = part['name']
    g = 'head' if nm in HEAD_NAMES else 'neck + socket' if nm.startswith(('neck', 'socket')) else 'scarf' if nm.startswith('scarf') else \
        'hands' if nm.startswith(('palm', 'hand_ridge', 'index', 'middle', 'third', 'thenar', 'thumb')) else \
        'arms' if nm.startswith(('upperarm', 'elbow', 'forearm', 'wrist')) else \
        'legs + feet' if nm.startswith(('cuff', 'shin', 'ankle', 'foot', 'heel', 'toe')) else \
        'belt + tools' if nm.startswith(('belt', 'buckle', 'pouch', 'wrench')) else 'coveralls + details'
    groups[g] = groups.get(g, 0) + tri(o)
bpy.ops.object.select_all(action='DESELECT'); bpy.context.view_layer.objects.active = me; me.select_set(True)
bpy.ops.object.mode_set(mode='EDIT'); bpy.ops.mesh.select_mode(type='VERT'); bpy.ops.mesh.select_all(action='DESELECT'); bpy.ops.object.mode_set(mode='OBJECT')
for v in me.data.vertices: v.select = v.index in remove
before = len(me.data.vertices)
bpy.ops.object.mode_set(mode='EDIT'); bpy.ops.mesh.delete(type='VERT'); bpy.ops.object.mode_set(mode='OBJECT')
print("DELETED", before - len(me.data.vertices), "expected", len(remove))
groups['kept trousers'] = tri(me)
for o in new: o.select_set(True)
me.select_set(True); bpy.context.view_layer.objects.active = me; bpy.ops.object.join()
while len(me.data.materials) > 1: me.data.materials.pop()
for p_ in me.data.polygons: p_.material_index = 0
bpy.ops.object.vertex_group_limit_total(limit=4); bpy.ops.object.vertex_group_normalize_all(lock_active=False)
print("TRIS by group", groups)
print("FINAL tris", tri(me))
gidx = {g.name: g.index for g in me.vertex_groups}
hw = [next((g.weight for g in v.groups if g.group == gidx['Head']), 0.0) for v in me.data.vertices]
print("CHECK verts with partial Head weight:", sum(1 for w in hw if 1e-4 < w < 0.9999), "(want 0) | Head 100 %:", sum(1 for w in hw if w >= 0.9999),
      "| unweighted:", sum(1 for v in me.data.vertices if sum(g.weight for g in v.groups) < 0.99), "(want 0)")
f3 = [v for v in me.data.vertices if any(me.vertex_groups[g.group].name == 'LeftHandRing2' for g in v.groups)]
print("CHECK merged finger: verts on LeftHandRing2", len(f3), "| their Pinky2 share",
      round(sum(next((g.weight for g in v.groups if me.vertex_groups[g.group].name == 'LeftHandPinky2'), 0) for v in f3) / max(1, len(f3)), 3), "(want 0.5)")

bpy.ops.object.select_all(action='DESELECT'); arm.select_set(True); bpy.context.view_layer.objects.active = arm
bpy.ops.object.mode_set(mode='EDIT')
eb = arm.data.edit_bones; headb = eb['Head']; inv = arm.matrix_world.inverted()
for name, off in (('DH_C', Vector((0, 0, 0))), ('DH_F', Vector((0, -0.10, 0))), ('DH_U', Vector((0, 0, 0.10)))):
    b = eb.new(name); b.head = inv @ (C + off); b.tail = b.head + Vector((0, 0, 0.02)); b.parent = headb; b.use_connect = False; b.use_deform = False
bpy.ops.object.mode_set(mode='OBJECT')
print("DH bones", {b.name: [round(x, 4) for x in b.head_local] for b in arm.data.bones if b.name.startswith('DH_')})

bpy.ops.object.select_all(action='DESELECT'); me.select_set(True); arm.select_set(True)
bpy.ops.export_scene.gltf(filepath=os.path.join(OUT, "gremlin.glb"), export_format='GLB', use_selection=True, export_animations=False)
bpy.ops.object.select_all(action='DESELECT'); st.select_set(True)
bpy.ops.export_scene.gltf(filepath=os.path.join(OUT, "gremlin_head.glb"), export_format='GLB', use_selection=True, export_animations=False)
print("EXPORTED", OUT)
