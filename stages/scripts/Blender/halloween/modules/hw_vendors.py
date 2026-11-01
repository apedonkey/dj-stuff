"""GRAVEYARD SHIFT grounds module hw_vendors: the vendor lanes on both flanks of the crowd (Blender 4.5, headless).

Layout (kit frame, d = |x| - crowd_half(y), the x-measure past the crowd edge):
  - each flank's units stand with their BACKS on d = 17.6 for y -14..-66, fronts toward the crowd, parallel to the
    slanted crowd edge: everything below 3 m stays in the band d 14..17.6 (3.15 m measured square to the edge);
  - the walkway d 10..14 holds no geometry, only people (queues in front of the units, walkers); the graveyard strip
    (hw_graveyard) is d 3..10, so people keep to d >= 10.9;
  - signs sit on two posts just behind each unit, turned to the DJ, and are staggered in height so that none hides
    another from the booth (sign_layout); everything else behind the backs is empty (the forest starts at d 24).
Units (14): hearse food trucks (BAT BITES, GRAVE DIGGER DOGS, HEX BURGERS, BONE BROTH), coffin-shaped bars (SPIRITS:
a bar with a coffin sign and upright coffin cabinets; COFFIN COFFEE: an upright coffin kiosk with its lid open), the
WITCH'S BREW bar under three witch-hat roofs with a cauldron, witch-hat stalls (BRAINS, SCREAM CREAM, POISON APPLES,
BLOOD BANK, CURSED MERCH), MORGUE LOCKERS (+ CHARGE) and HOLY WATER; on the left the lane ends in 8 outhouses with a
glowing-skull WC light tower. Festoon masts on the units' front line carry orange/purple and warm bulb strings.

Preview aid: HW_PROXY=1 also draws the returned people as grey blocks (the harness does not draw people).
"""
import math
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "grounds"))
from kit import *  # noqa: E402,F401,F403

NAME = "vendors"
BAKE_SIZE = 4096

Y_NEAR, Y_FAR = -14.0, -66.0
D_BACK = 17.6                     # unit backs
D_FRONT = 14.0                    # nothing below 3 m nearer the crowd: the walkway d 10..14 stays clear
D_PEOPLE = 10.9                   # people keep this far out (the graveyard's fence runs along d 10)
SLOPE = 0.55                      # crowd_half grows 0.55 m per m of depth
NRM = math.hypot(1.0, SLOPE)
DEPTH_MAX = (D_BACK - D_FRONT) / NRM          # 3.154 m: the band measured square to the crowd edge
Z = Vector((0.0, 0.0, 1.0))
WARM = (1.0, 0.60, 0.28)          # light colors
WARM_WHITE = (1.0, 0.78, 0.52)
ORANGE_L = (1.0, 0.42, 0.08)
PURPLE_L = (0.52, 0.14, 1.0)
GREEN_L = (0.25, 1.0, 0.30)
RED_L = (1.0, 0.12, 0.06)
LIGHT_SCALE = 1.0
PROXY = os.environ.get("HW_PROXY") == "1"


def log(msg):
    print("[HWVENDORS] " + msg, flush=True)


def dval(side, x, y):
    return side * x - crowd_half(y)


# ------------------------------------------------------------------ output collector
class Out:
    def __init__(self):
        self.lit, self.glow, self.halos = {}, bmesh.new(), bmesh.new()
        self.lights, self.people = [], []
        self.circles, self.rects = [], []      # people keep-outs: (center, r) and (frame, a0, a1, b0, b1)
        self.tally = {}
        self.signs = []                        # deferred sign requests (sign_layout builds them)

    def L(self, key):
        if key not in self.lit:
            self.lit[key] = bmesh.new()
        return self.lit[key]

    def G(self, faces, key):
        glow_faces(self.glow, faces, key)
        return faces

    def count(self):
        return sum(tris(b) for b in self.lit.values()) + tris(self.glow) + tris(self.halos)

    def run(self, part, fn, *args):
        n0 = self.count()
        res = fn(self, *args)
        self.tally[part] = self.tally.get(part, 0) + self.count() - n0
        return res

    def lamp(self, kind, pos, color, power, target=None, size=0.3, deg=60.0):
        self.lights.append(light(f"HwVend{len(self.lights):02d}", kind, pos, color, power * LIGHT_SCALE,
                                 target=target, size=size, spot_deg=deg))

    def block(self, p, r):
        self.circles.append((Vector((p.x, p.y, 0.0)), r))

    def block_rect(self, fr, a0, a1, b0, b1):
        self.rects.append((fr, min(a0, a1), max(a0, a1), min(b0, b1), max(b0, b1)))

    def free(self, p, r=0.3):
        q = Vector((p.x, p.y, 0.0))
        for c, rc in self.circles:
            if (q - c).length < r + rc:
                return False
        for fr, a0, a1, b0, b1 in self.rects:
            v = q - Vector((fr.o.x, fr.o.y, 0.0))
            a, b = v.dot(fr.R), v.dot(fr.F)
            if a0 - r < a < a1 + r and b0 - r < b < b1 + r:
                return False
        return True

    def person(self, p, face, pose="down", force=False):
        """A person at p facing `face`, if the spot is free (people keep 0.3 m from geometry and 0.55 m apart)."""
        side = 1 if p.x > 0 else -1
        if dval(side, p.x, p.y) < D_PEOPLE or (not force and not self.free(p, 0.3)):
            return False
        self.people.append((round(p.x, 2), round(p.y, 2), round(math.atan2(-face[0], face[1]), 3), pose))
        self.block(p, 0.25)
        return True


class Frame:
    """A unit's frame: a = the viewer's right when facing the unit's front, b = out of the front (toward the crowd),
    z = up from the field. Origin = front-center on the field floor."""

    def __init__(self, o, F):
        self.o = Vector((o.x, o.y, GROUND_Z))
        self.F = Vector((F.x, F.y, 0.0)).normalized()
        self.R = Vector((-self.F.y, self.F.x, 0.0))
        self.yaw = math.atan2(self.R.y, self.R.x)

    def p(self, a, b, z=0.0):
        return self.o + self.R * a + self.F * b + Z * z

    def box(self, bm, a0, a1, b0, b1, z0, z1):
        return box(bm, self.p((a0 + a1) / 2, (b0 + b1) / 2, (z0 + z1) / 2), (abs(a1 - a0), abs(b1 - b0), abs(z1 - z0)),
                   yaw=self.yaw)

    def cyl(self, bm, a, b, z0, z1, r, segs=6, r2=None, cap=True):
        return cyl(bm, self.p(a, b, z0), self.p(a, b, z1), r, segs=segs, r2=r2, cap=cap)

    def quad_f(self, bm, a0, a1, b, z0, z1):
        """Upright quad in the plane b, facing +F."""
        return poly(bm, [self.p(a0, b, z0), self.p(a1, b, z0), self.p(a1, b, z1), self.p(a0, b, z1)], self.F)

    def prism(self, bm, prof, b0, b1):
        """Closed prism: convex polygon prof [(a, z), ...] extruded from b0 to b1 (front face at b1)."""
        P = [self.p(a, b0, z) for a, z in prof]
        Q = [self.p(a, b1, z) for a, z in prof]
        ca = sum(a for a, _ in prof) / len(prof)
        cz = sum(z for _, z in prof) / len(prof)
        faces = poly(bm, Q, self.F) + poly(bm, P, -self.F)
        for i in range(len(prof)):
            j = (i + 1) % len(prof)
            hint = self.R * ((prof[i][0] + prof[j][0]) / 2 - ca) + Z * ((prof[i][1] + prof[j][1]) / 2 - cz)
            faces += poly(bm, [P[i], P[j], Q[j], Q[i]], hint)
        return faces


class Lane:
    """One flank: station u (m along the lane from y = Y_NEAR toward the back) and depth d -> field points."""

    def __init__(self, side):
        self.s = side
        self.t = Vector((SLOPE * side / NRM, -1.0 / NRM, 0.0))      # along the lane, toward the back
        self.n_in = Vector((-side / NRM, -SLOPE / NRM, 0.0))        # square to the crowd edge, toward the crowd
        self.p0 = Vector((side * (crowd_half(Y_NEAR) + D_BACK), Y_NEAR, GROUND_Z))

    def point(self, u, d):
        return self.p0 + self.t * u + self.n_in * ((D_BACK - d) / NRM)

    def u_of(self, p):
        return (Vector((p.x, p.y, GROUND_Z)) - self.p0).dot(self.t)

    def length(self):
        return (Y_NEAR - Y_FAR) * NRM


# ------------------------------------------------------------------ geometry helpers (adapted from grounds/vendors.py)
def obox(bm, c, ax, ay, size):
    """Box centered at c with its local x along ax and y along ay (orthogonalized), sizes (sx, sy, sz)."""
    ax = Vector(ax).normalized()
    ay = Vector(ay)
    ay = (ay - ax * ay.dot(ax)).normalized()
    az = ax.cross(ay)
    c = Vector(c)
    m = Matrix(((ax.x, ay.x, az.x, c.x), (ax.y, ay.y, az.y, c.y), (ax.z, ay.z, az.z, c.z), (0.0, 0.0, 0.0, 1.0)))
    res = bmesh.ops.create_cube(bm, size=1.0, matrix=m @ Matrix.Diagonal(Vector(size).to_4d()))
    return list({f for v in res["verts"] for f in v.link_faces})


def poly(bm, pts, hint):
    """One planar face through pts, its normal turned toward `hint` (one-sided materials: the visible side)."""
    f = bm.faces.new([bm.verts.new(Vector(p)) for p in pts])
    f.normal_update()
    if f.normal.dot(Vector(hint)) < 0:
        f.normal_flip()
    return [f]


def slab(bm, pts, thick):
    """Planar polygon pts extruded by the vector `thick`: a closed thin prism."""
    P = [Vector(p) for p in pts]
    Q = [p + thick for p in P]
    c = sum(P, Vector()) / len(P)
    faces = poly(bm, P, -thick) + poly(bm, Q, thick)
    for i in range(len(P)):
        j = (i + 1) % len(P)
        faces += poly(bm, [P[i], P[j], Q[j], Q[i]], (P[i] + P[j]) / 2 - c)
    return faces


def octa(bm, c, r, rz=None):
    """Octahedron bulb (8 tris): reads as a dot from any angle."""
    c, rz = Vector(c), r if rz is None else rz
    v = [bm.verts.new(c + d) for d in (Vector((r, 0, 0)), Vector((-r, 0, 0)), Vector((0, r, 0)), Vector((0, -r, 0)),
                                       Vector((0, 0, rz)), Vector((0, 0, -rz)))]
    faces = []
    for i, j in ((0, 2), (2, 1), (1, 3), (3, 0)):
        faces.append(bm.faces.new((v[i], v[j], v[4])))
        faces.append(bm.faces.new((v[j], v[i], v[5])))
    return faces


def ball(bm, c, r, segs=7, rings=4, scale=(1.0, 1.0, 1.0)):
    """Low-poly UV sphere built in a fixed order (deterministic face order)."""
    c, s = Vector(c), Vector(scale)

    def vert(d):
        return bm.verts.new(c + Vector((d.x * s.x, d.y * s.y, d.z * s.z)) * r)

    top = vert(Vector((0.0, 0.0, 1.0)))
    ring = []
    for i in range(1, rings):
        phi = math.pi * i / rings
        ring.append([vert(Vector((math.sin(phi) * math.cos(2 * math.pi * j / segs),
                                  math.sin(phi) * math.sin(2 * math.pi * j / segs), math.cos(phi))))
                     for j in range(segs)])
    bot = vert(Vector((0.0, 0.0, -1.0)))
    faces = []
    for j in range(segs):
        k = (j + 1) % segs
        faces.append(bm.faces.new((top, ring[0][j], ring[0][k])))
        for a, b in zip(ring, ring[1:]):
            faces.append(bm.faces.new((a[j], b[j], b[k], a[k])))
        faces.append(bm.faces.new((bot, ring[-1][k], ring[-1][j])))
    return faces


def festoon(o, a, b, sag, spacing=0.8, r=0.085, key="bulb_warm", wire="metal_dark"):
    """Festoon between a and b: thin dark wire (lit) + octahedron bulbs (glow). key: one palette key or a tuple of
    keys cycled bulb by bulb."""
    a, b = Vector(a), Vector(b)
    pts = catenary(a, b, sag, n=max(3, int((b - a).length / 2.0)))
    wm = o.L(wire)
    for p, q in zip(pts, pts[1:]):
        cyl(wm, p, q, 0.012, segs=3, cap=False)
    L = sum((q - p).length for p, q in zip(pts, pts[1:]))
    nb = max(2, int(L / spacing))
    keys = (key,) if isinstance(key, str) else key
    fs = {k: [] for k in keys}
    for i in range(1, nb):
        f = i / nb * (len(pts) - 1)
        k = min(int(f), len(pts) - 2)
        fs[keys[i % len(keys)]] += octa(o.glow, pts[k].lerp(pts[k + 1], f - k) - Z * (r * 1.3), r)
    for k, faces in fs.items():
        o.G(faces, k)


def valance(o, fr, a0, a1, b, z_top, key, teeth=0.5, drop=0.26):
    """Fabric strip with pointed teeth across the front at plane b (closed slabs)."""
    bm = o.L(key)
    fr.box(bm, a0, a1, b, b + 0.04, z_top - drop, z_top)
    n = max(2, int((a1 - a0) / teeth))
    w = (a1 - a0) / n
    for i in range(n):
        x0 = a0 + i * w
        slab(bm, [fr.p(x0, b + 0.01, z_top - drop), fr.p(x0 + w, b + 0.01, z_top - drop),
                  fr.p(x0 + w / 2, b + 0.01, z_top - drop - 0.2)], fr.F * 0.02)


def coffin_outline(w, h, head=0.32, shoulder=0.25, feet=0.26):
    """Horizontal coffin (in a sign's plane, u along the width, v up), head to the left: 6 points, convex."""
    return [(-w / 2, -head * h), (-shoulder * w, -h / 2), (w / 2, -feet * h), (w / 2, feet * h), (-shoulder * w, h / 2),
            (-w / 2, head * h)]


def upright_coffin(w, h, foot=0.66, top=0.72, sh=0.70):
    """Upright coffin outline in (a, z) from z=0: foot width foot*w, shoulders w at sh*h, head top*w at h."""
    return [(-foot * w / 2, 0.0), (foot * w / 2, 0.0), (w / 2, sh * h), (top * w / 2, h), (-top * w / 2, h),
            (-w / 2, sh * h)]


def witch_hat(o, fr, a, b, z0, r_brim, r_cone, h, band, rng, lean=None, cloth="canvas_black"):
    """Witch-hat roof: flat octagonal brim at z0, a cone in three bent sections, a glowing hat band at its foot."""
    n = 8
    ring0 = [fr.p(a + r_brim * math.cos(2 * math.pi * (i + 0.5) / n), b + r_brim * math.sin(2 * math.pi * (i + 0.5) / n),
                  z0) for i in range(n)]
    slab(o.L(cloth), ring0, Z * 0.06)
    if lean is None:
        lean = rng.uniform(0, 2 * math.pi)
    dv = fr.R * math.cos(lean) + fr.F * math.sin(lean)
    base = fr.p(a, b, z0 + 0.06)
    c1 = base + Z * (0.42 * h) + dv * (0.05 * h)
    c2 = base + Z * (0.72 * h) + dv * (0.16 * h)
    tip = base + Z * (0.93 * h) + dv * (0.42 * h) - Z * 0.0
    cm = o.L(cloth)
    cyl(cm, base, c1, r_cone, segs=8, cap=False, r2=r_cone * 0.55)
    cyl(cm, c1 - (c1 - base).normalized() * 0.04, c2, r_cone * 0.57, segs=8, cap=False, r2=r_cone * 0.26)
    cone(cm, c2 - (c2 - c1).normalized() * 0.03, tip, r_cone * 0.27, segs=6, cap=False)
    o.G(cyl(o.glow, base, base + Z * 0.16, r_cone * 1.02, segs=8, cap=False, r2=r_cone * 0.985), band)
    return max(tip.z, c2.z) - GROUND_Z


def face_dj(p, f, k=0.9):
    """Blend a facing direction f toward the DJ at the origin (k=1: straight at the DJ)."""
    to = Vector((-p.x, -p.y, 0.0)).normalized()
    v = Vector((f.x, f.y, 0.0)) * (1.0 - k) + to * k
    return v.normalized()


def sign_size(lines, px):
    tw = max(text_width(t, px) for t in lines)
    th = len(lines) * 7 * px + (len(lines) - 1) * 2.5 * px
    return tw + 2.8 * px, th + 2.8 * px


def sign_board(o, req, c, F):
    """Build a sign of request req centered at c facing F: dark board (or a coffin board), LED lines, glowing border."""
    lines, px = req["lines"], req["px"]
    keys = req.get("keys") or [req["key"]] * len(lines)
    F = Vector((F.x, F.y, 0.0)).normalized()
    R = Vector((-F.y, F.x, 0.0))
    bw, bh = req["size"]
    depth = 0.14
    yaw = math.atan2(R.y, R.x)
    tw = max(text_width(t, px) for t in lines)
    th = len(lines) * 7 * px + (len(lines) - 1) * 2.5 * px
    shift = 0.0
    if req.get("shape") == "coffin":
        out = coffin_outline(bw, bh)
        pts = [c + R * u + Z * v - F * (depth / 2) for u, v in out]
        slab(o.L(req.get("board", "wood_dark")), pts, F * depth)
        fs = []
        t_ = px * 0.45
        for (u0, v0), (u1, v1) in zip(out, out[1:] + out[:1]):
            p0 = c + R * u0 + Z * v0 + F * (depth / 2 + 0.012)
            p1 = c + R * u1 + Z * v1 + F * (depth / 2 + 0.012)
            d = p1 - p0
            fs += obox(o.glow, (p0 + p1) / 2, d, F, (d.length + t_, 0.02, t_))
        o.G(fs, req.get("border", "purple"))
        shift = -0.06 * bw
    else:
        box(o.L(req.get("board", "canvas_black")), c, (bw, depth, bh), yaw=yaw)
        if req.get("border"):
            t_ = px * 0.4
            fz = F * (depth / 2 + 0.012)
            fs = []
            for dz in (bh / 2 - t_ / 2, -bh / 2 + t_ / 2):
                fs += box(o.glow, c + fz + Z * dz, (bw, 0.02, t_), yaw=yaw)
            for da in (bw / 2 - t_ / 2, -bw / 2 + t_ / 2):
                fs += box(o.glow, c + fz + R * da, (t_, 0.02, bh - 2 * t_), yaw=yaw)
            o.G(fs, req["border"])
    for i, (t, k) in enumerate(zip(lines, keys)):
        w = text_width(t, px)
        zb = th / 2 - (i + 1) * 7 * px - i * 2.5 * px
        led_text(o.glow, t, c + R * (shift - w / 2) + Z * zb + F * (depth / 2 + 0.02), R, Z, pixel=px, gap=px * 0.2,
                 key=k)


def request_sign(o, fr, lines, px, key, z_min, a=0.0, behind=0.6, **kw):
    """Queue a sign for sign_layout: two posts just behind the unit (at b = b_back - behind), the board's bottom at
    least z_min above the field."""
    lines = [lines] if isinstance(lines, str) else lines
    req = dict(lines=lines, px=px, key=key, fr=fr, a=a + kw.pop("shift", 0.0), behind=behind, z_min=z_min, **kw)
    w, h = sign_size(lines, px)
    if kw.get("shape") == "coffin":
        w, h = w / 0.70, (h - 2.8 * px) * 1.55 + 1.8 * px
    req["size"] = (w, h)
    o.signs.append(req)
    return req


# ------------------------------------------------------------------ sign layout: turned to the DJ, staggered in height
def _ang_box(c, R, bw, bh):
    """Angular box (az0, az1, el0, el1) in degrees of a board centered at c (in-plane right R) seen from DJ_EYE."""
    az, el = [], []
    for su in (-1, 1):
        for sv in (-1, 1):
            p = c + R * (su * bw / 2) + Z * (sv * bh / 2)
            d = p - DJ_EYE
            az.append(math.degrees(math.atan2(d.x, -d.y)))
            el.append(math.degrees(math.atan2(d.z, math.hypot(d.x, d.y))))
    return min(az), max(az), min(el), max(el)


def sign_layout(o):
    """Place every queued sign: center behind its unit, turned straight at the DJ. Per lane, ordered near to far, the
    signs alternate between a low row (bottom 0.3 m over the unit) and a high row (bottom just above the angular top
    of the low signs it overlaps from the booth), so no sign hides another from the DJ. Then build boards + posts."""
    by_lane = {}
    for r in o.signs:
        base = r["fr"].p(r["a"], r["b_back"] - r["behind"])
        r["base"] = base
        by_lane.setdefault(base.x > 0, []).append(r)
    placed = []
    for lane_signs in by_lane.values():
        lane_signs.sort(key=lambda r: (r["base"] - DJ_EYE).length)
        for i, r in enumerate(lane_signs):
            r["row"] = i % 2
        for row in (0, 1):
            for r in [q for q in lane_signs if q["row"] == row]:
                base = r["base"]
                bw, bh = r["size"]
                F = face_dj(base, r["fr"].F, 1.0)
                R = Vector((-F.y, F.x, 0.0))
                dist = math.hypot(base.x, base.y)
                zc = max(GROUND_Z + r["z_min"] + 0.3, DJ_EYE.z + dist * math.tan(math.radians(0.6))) + bh / 2
                a0, a1, _, _ = _ang_box(Vector((base.x, base.y, zc)), R, bw, bh)
                if row == 1:
                    for q in lane_signs:
                        if q["row"] == 0 and not (a1 + 0.2 < q["ang"][0] or a0 - 0.2 > q["ang"][1]):
                            zc = max(zc, DJ_EYE.z + dist * math.tan(math.radians(q["ang"][3] + 0.35)) + bh / 2 + 0.1)
                r["center"] = Vector((base.x, base.y, zc))
                r["ang"] = _ang_box(r["center"], R, bw, bh)
                r["F"], r["R"] = F, R
                placed.append(r)
    for i, r in enumerate(placed):
        hits = [q for q in placed[:i] + placed[i + 1:] if not (r["ang"][1] + 0.1 < q["ang"][0] or
                r["ang"][0] - 0.1 > q["ang"][1] or r["ang"][3] + 0.1 < q["ang"][2] or r["ang"][2] - 0.1 > q["ang"][3])]
        c, (bw, bh), F, R = r["center"], r["size"], r["F"], r["R"]
        sign_board(o, r, c, F)
        for e in (-1, 1):                                  # two posts near the middle, from the field to the board
            q = c + R * (e * min(0.65, bw / 2 - 0.2))
            cyl(o.L("metal_dark"), Vector((q.x, q.y, GROUND_Z)), Vector((q.x, q.y, c.z - bh / 2 + 0.03)), 0.05, segs=5)
            o.block(q, 0.1)
        log(f"sign {' / '.join(r['lines']):24s} px {r['px']:.3f}  board {bw:4.1f} x {bh:3.1f} m  row {r['row']}  bottom "
            f"{c.z - bh / 2 - GROUND_Z:4.1f} m  az {r['ang'][0]:5.1f}..{r['ang'][1]:5.1f}  el {r['ang'][2]:4.1f}.."
            f"{r['ang'][3]:4.1f}" + (f"   OVERLAPS {', '.join(' '.join(q['lines']) for q in hits)}" if hits else ""))


# ------------------------------------------------------------------ light helpers
POOL_GAIN = 1.5


def pool(o, fr, a, b_aim=1.2, power=900.0, deg=95.0, color=WARM, h=5.0, out=2.4):
    """Light pool on the queue: a spot hung high in front of the unit, aimed back at the counter's foot."""
    o.lamp("SPOT", fr.p(a, b_aim + out, h), color, power * POOL_GAIN, target=fr.p(a, b_aim - 0.4, 0.0), size=0.5,
           deg=deg)


def queue(o, fr, a, n, rng, b0=0.6, step=0.74):
    """n people in line in front of a unit (facing it), from b0 outward."""
    for i in range(n):
        p = fr.p(a + rng.uniform(-0.16, 0.16) + 0.2 * math.sin(i * 1.9), b0 + i * step + rng.uniform(-0.06, 0.06))
        f = -fr.F + fr.R * rng.uniform(-0.3, 0.3)
        o.person(p, f, rng.choice(("down", "down", "hips", "one")))


def staff(o, fr, a, b, rng, pose="hips"):
    o.person(fr.p(a + rng.uniform(-0.1, 0.1), b), fr.F, pose, force=True)


# ------------------------------------------------------------------ units (local footprint a in [a0, a1], b in [b0, b1])
def u_hearse(o, fr, rng, s):
    """Hearse food truck: long black body, raked windshield and hood, sloped rear, chrome beltline and landau bar,
    a glowing serving hatch on the crowd side with cooks and a propped flap, glowing roof trim, menu board, roof prop."""
    L, W = s.get("L", 6.8), 2.2
    k = s.get("cab", 1)

    def A(xp):
        return k * (xp - L / 2)

    zb, zw, zt = 0.42, 1.22, 2.72
    body, alu, glass = o.L(s.get("body", "truck_black")), o.L("metal_alu"), o.L("glass_dark")
    xr, xc = 0.5, 5.05                                               # rear slope end, cab front (windshield foot)
    h0, h1 = 1.0, 3.55                                               # hatch (x')
    zh0, zh1 = 1.32, 2.32
    fr.box(body, A(0.0), A(L - 1.05), -W, 0.0, zb, zw)               # lower body
    fr.box(body, A(L - 1.05), A(L), -W + 0.06, -0.06, zb, zw - 0.1)  # hood
    fr.box(body, A(xr), A(xc), -W, -0.9, zw, zt)                     # upper body behind the hatch cavity
    fr.box(body, A(xr), A(xc), -0.9, 0.0, zw, zh0)
    fr.box(body, A(xr), A(xc), -0.9, 0.0, zh1, zt)
    fr.box(body, A(xr), A(h0), -0.9, 0.0, zh0, zh1)
    fr.box(body, A(h1), A(xc), -0.9, 0.0, zh0, zh1)
    fr.prism(body, sorted_ccw([(A(0.0), zw), (A(xr), zw), (A(xr), zt), (A(0.18), zt - 0.3), (A(0.0), zw + 0.95)]),
             -W, 0.0)                                                # sloped, rounded rear
    fr.prism(body, sorted_ccw([(A(xc), zw), (A(xc + 0.72), zw), (A(xc + 0.2), zt), (A(xc), zt)]), -W + 0.03, -0.03)
    wa, wb = Vector((A(xc + 0.68), zw + 0.12)), Vector((A(xc + 0.22), zt - 0.1))   # windshield on the raked face
    e = wb - wa
    nrm = Vector((k * e.y, -k * e.x)).normalized()                  # outward: toward the vehicle's front and up
    off = 0.025
    pts = [fr.p(wa.x + nrm.x * off, bb, wa.y + nrm.y * off) for bb in (-W + 0.2, -0.2)]
    pts += [fr.p(wb.x + nrm.x * off, bb, wb.y + nrm.y * off) for bb in (-0.2, -W + 0.2)]
    poly(glass, pts, fr.R * nrm.x + Z * nrm.y)
    for bb, sgn in ((0.0, 1), (-W, -1)):                             # cab side windows, both sides
        fr.box(glass, A(4.25), A(4.95), bb - 0.02 * sgn, bb + 0.02 * sgn, 1.45, 2.42)
    fr.box(alu, A(0.0), A(L), 0.0, 0.03, zw - 0.06, zw)              # chrome beltline
    fr.box(alu, A(L - 0.01), A(L + 0.04), -W + 0.45, -0.45, zb + 0.12, zw - 0.25)   # grille
    o.G(fr.box(o.glow, A(L), A(L + 0.03), -0.42, -0.12, zw - 0.32, zw - 0.18)
        + fr.box(o.glow, A(L), A(L + 0.03), -W + 0.12, -W + 0.42, zw - 0.32, zw - 0.18), "warm_dim")
    o.G(fr.box(o.glow, A(-0.03), A(0.0), -0.35, -0.12, zw - 0.25, zw - 0.05)
        + fr.box(o.glow, A(-0.03), A(0.0), -W + 0.12, -W + 0.35, zw - 0.25, zw - 0.05), "red_dim")
    lb = [(0.62, 2.42), (0.86, 2.3), (0.7, 2.06), (0.92, 1.9)]       # landau bar (S) on the rear quarter
    for (x0, z0), (x1, z1) in zip(lb, lb[1:]):
        cyl(alu, fr.p(A(x0), 0.03, z0), fr.p(A(x1), 0.03, z1), 0.03, segs=3, cap=False)
    for xw in (1.15, L - 0.82):                                      # wheels, chrome hubcaps on the crowd side
        for bw in (-0.24, -W + 0.24):
            cyl(o.L("rubber"), fr.p(A(xw), bw - 0.13, 0.4), fr.p(A(xw), bw + 0.13, 0.4), 0.4, segs=7)
        cyl(alu, fr.p(A(xw), -0.11, 0.4), fr.p(A(xw), -0.085, 0.4), 0.2, segs=6)
    fr.box(o.L("metal_dark"), A(0.3), A(L - 0.3), -W + 0.35, -0.35, 0.22, zb)
    # the hatch: glowing kitchen, counter shelf, cooks, propped flap, trim
    o.G(fr.quad_f(o.glow, A(h0), A(h1), -0.88, zh0, zh1), s.get("inside", "bulb_warm"))
    fr.box(alu, A(h0), A(h1), -0.9, 0.32, zh0 - 0.05, zh0 + 0.02)
    sil = []                                                         # cooks: head-and-shoulder silhouettes
    for i, (t, dz) in enumerate(((0.27, 0.0), (0.7, -0.12))[:s.get("cooks", 2)]):
        xa = h0 + (h1 - h0) * t + rng.uniform(-0.1, 0.1)
        z0 = zh0 + dz
        sil += fr.box(o.glow, A(xa - 0.24), A(xa + 0.24), -0.74, -0.56, zh0 - 0.05, z0 + 0.42)
        sil += fr.box(o.glow, A(xa - 0.17), A(xa + 0.17), -0.74, -0.56, z0 + 0.42, z0 + 0.5)
        sil += fr.box(o.glow, A(xa - 0.1), A(xa + 0.1), -0.72, -0.58, z0 + 0.5, z0 + 0.76)
        if i == 0 and s.get("cook_hat", True):
            sil += cone(o.glow, fr.p(A(xa), -0.65, z0 + 0.74), fr.p(A(xa + 0.12), -0.65, z0 + 1.02), 0.13, segs=5)
    o.G(sil, "black")
    el = math.radians(rng.uniform(14, 22))
    dflap = fr.F * math.cos(el) + Z * math.sin(el)
    flen = 0.85
    hinge = fr.p(A((h0 + h1) / 2), 0.02, zh1 + 0.04)
    obox(o.L(s.get("flap", "truck_black")), hinge + dflap * (flen / 2) + Z * 0.03, fr.R, dflap,
         (h1 - h0 + 0.2, flen, 0.05))
    for xa in (h0 + 0.06, h1 - 0.06):
        cyl(alu, fr.p(A(xa), 0.03, zh0 + 0.1), fr.p(A(xa), 0.02 + flen * math.cos(el), zh1 + 0.04 + flen * math.sin(el)),
            0.014, segs=3, cap=False)
    tk = s["trim"]
    fs = fr.box(o.glow, A(h0 - 0.07), A(h1 + 0.07), -0.02, 0.035, zh1, zh1 + 0.07)
    fs += fr.box(o.glow, A(h0 - 0.07), A(h0), -0.02, 0.035, zh0, zh1)
    fs += fr.box(o.glow, A(h1), A(h1 + 0.07), -0.02, 0.035, zh0, zh1)
    fs += fr.box(o.glow, A(xr), A(xc), -0.02, 0.035, zt - 0.08, zt - 0.02)
    o.G(fs, tk)
    m0, m1 = h1 + 0.12, 4.12                                         # menu board between the hatch and the cab door
    fr.box(o.L("canvas_black"), A(m0), A(m1), 0.0, 0.04, zh0 + 0.02, zh1 - 0.02)
    o.G(fr.quad_f(o.glow, A(m0 + 0.05), A(m1 - 0.05), 0.05, zh1 - 0.24, zh1 - 0.1), tk)
    fs = []
    for i in range(3):
        z = zh1 - 0.42 - i * 0.18
        w_ = (m1 - m0 - 0.1) * rng.uniform(0.55, 0.9)
        xa0, xa1 = A(m0 + 0.05), A(m0 + 0.05 + w_)
        fs += fr.quad_f(o.glow, min(xa0, xa1), max(xa0, xa1), 0.05, z, z + 0.07)
    o.G(fs, "warm_dim")
    top = zt
    ex = s.get("extra")
    if ex == "coffin":                                               # a coffin on a roof rack
        for xa in (1.3, 3.9):
            fr.box(o.L("metal_dark"), A(xa - 0.04), A(xa + 0.04), -W + 0.2, -0.2, zt, zt + 0.12)
        cw = 0.85
        outline = [(1.0, -0.26), (1.75, -0.42), (4.3, -0.3), (4.3, 0.3), (1.75, 0.42), (1.0, 0.26)]
        pts = [fr.p(A(xa_), -W / 2 + bb * cw, zt + 0.12) for xa_, bb in outline]
        slab(o.L("wood_dark"), pts, Z * 0.42)
        o.G(fr.box(o.glow, A(2.4), A(2.55), -W / 2 - 0.25, -W / 2 + 0.25, zt + 0.545, zt + 0.565)
            + fr.box(o.glow, A(2.0), A(2.95), -W / 2 - 0.04, -W / 2 + 0.04, zt + 0.545, zt + 0.565), tk)
        top = zt + 0.6
    elif ex == "bat":                                                # a bat with spread wings on the roof
        c = fr.p(A(2.4), -W / 2, zt + 0.95)
        wing = []
        for sgn in (-1, 1):
            q = [c, c + fr.R * (sgn * 0.5) + Z * 0.35, c + fr.R * (sgn * 1.0) + Z * 0.55, c + fr.R * (sgn * 1.55) + Z * 0.2,
                 c + fr.R * (sgn * 1.25) - Z * 0.1, c + fr.R * (sgn * 0.95) + Z * 0.02, c + fr.R * (sgn * 0.62) - Z * 0.2,
                 c + fr.R * (sgn * 0.32) - Z * 0.05]
            wing.append(q)
        for q in wing:
            for i in range(1, len(q) - 1):
                slab(o.L("canvas_black"), [q[0], q[i], q[i + 1]], fr.F * 0.04)
        ball(o.L("canvas_black"), c + Z * 0.05, 0.26, 6, 3, (0.8, 0.6, 1.2))
        for sgn in (-1, 1):
            cone(o.L("canvas_black"), c + fr.R * (sgn * 0.1) + Z * 0.25, c + fr.R * (sgn * 0.16) + Z * 0.5, 0.06, segs=4)
        o.G(box(o.glow, c + fr.F * 0.2 + Z * 0.12 + fr.R * 0.07, (0.06, 0.03, 0.04), yaw=fr.yaw)
            + box(o.glow, c + fr.F * 0.2 + Z * 0.12 - fr.R * 0.07, (0.06, 0.03, 0.04), yaw=fr.yaw), "red")
        fr.cyl(o.L("metal_dark"), A(2.4), -W / 2, zt, zt + 0.75, 0.04, segs=4)
        top = zt + 1.55
    elif ex == "hat":                                                # a giant witch hat on the roof
        top = witch_hat(o, fr, A(2.6), -W / 2, zt, 1.0, 0.62, 1.7, tk, rng, lean=math.pi * (0.0 if k > 0 else 1.0))
    elif ex == "pot":                                                # a stock pot with a bone and a chimney
        c = fr.p(A(1.6), -W / 2, zt)
        cyl(o.L("metal_dark"), c, c + Z * 0.75, 0.55, segs=8)
        o.G(cyl(o.glow, c + Z * 0.75, c + Z * 0.77, 0.5, segs=8), "green_dim")
        cyl(o.L("bone"), c + Z * 0.5 + fr.R * 0.15, c + Z * 1.35 + fr.R * 0.35, 0.07, segs=4)
        for e in (-1, 1):
            o.G(octa(o.glow, c + Z * 1.38 + fr.R * (0.35 + e * 0.07), 0.08), "black")
        fr.cyl(o.L("metal_dark"), A(3.8), -W + 0.5, zt, zt + 1.1, 0.1, segs=5)
        top = zt + 1.4
    request_sign(o, fr, s["text"], s["px"], s["key"], top, a=A(2.6), shift=s.get("sign_a", 0.0), b_back=-W, keys=s.get("keys"),
                 border=s.get("border"))
    o.lamp("POINT", fr.p(A((h0 + h1) / 2), 0.5, zh1 - 0.1), WARM_WHITE, s.get("hatch_w", 30), size=0.3)
    pool(o, fr, A((h0 + h1) / 2), b_aim=1.2, power=s.get("pool", 900), color=s.get("pool_col", WARM))
    queue(o, fr, A((h0 + h1) / 2), s.get("q", 4), rng, b0=0.85)
    o.block_rect(fr, A(0.0), A(L), -W, 0.12)
    return {"anchors": [fr.p(A(xr + 0.1), -0.05, zt), fr.p(A(xc - 0.1), -0.05, zt)], "people_b": 0.85}


def sorted_ccw(pts):
    """Order a convex point set counter-clockwise around its centroid (prism profiles mirrored by cab=-1)."""
    cx = sum(p[0] for p in pts) / len(pts)
    cz = sum(p[1] for p in pts) / len(pts)
    return sorted(pts, key=lambda p: math.atan2(p[1] - cz, p[0] - cx))


def counter(o, fr, a0, a1, front_key, led, top="wood"):
    fr.box(o.L(front_key), a0, a1, -0.72, -0.1, 0.0, 1.06)
    fr.box(o.L(top), a0 - 0.05, a1 + 0.05, -0.8, 0.0, 1.06, 1.12)
    if led:
        o.G(fr.box(o.glow, a0, a1, -0.1, -0.06, 0.96, 1.01) + fr.box(o.glow, a0, a1, -0.1, -0.06, 0.12, 0.16), led)


def back_bar(o, fr, a0, a1, b_wall, glow_key, rng):
    """Shelves on the back wall: a glowing panel with bottle silhouettes (black glow) on two shelves."""
    fr.box(o.L("wood_dark"), a0, a1, b_wall, b_wall + 0.45, 0.0, 0.95)
    o.G(fr.quad_f(o.glow, a0 + 0.15, a1 - 0.15, b_wall + 0.02, 1.05, 2.25), glow_key)
    for zsh in (1.32, 1.82):
        fr.box(o.L("wood_dark"), a0 + 0.1, a1 - 0.1, b_wall + 0.02, b_wall + 0.3, zsh - 0.04, zsh)
        a, fs = a0 + 0.25, []
        while a < a1 - 0.35:
            bw_ = rng.uniform(0.08, 0.12)
            fs += fr.quad_f(o.glow, a, a + bw_, b_wall + 0.06, zsh, zsh + rng.uniform(0.2, 0.33))
            a += bw_ + rng.uniform(0.06, 0.26)
        o.G(fs, "black")


def u_witchbar(o, fr, rng, s):
    """WITCH'S BREW: a long bar under three witch-hat roofs with glowing bands, a green-lit back bar, and a big cauldron
    of glowing brew on legs at the stage end."""
    Lb, D = s.get("L", 7.6), 2.75
    h = Lb / 2
    eave = 2.55
    for a in (-h, 0.0, h):
        for b in (-0.12, -D + 0.1):
            fr.cyl(o.L("wood_dark"), a, b, 0.0, eave, 0.07, segs=6)
    fr.box(o.L("wood_dark"), -h - 0.1, h + 0.1, -D, -D + 0.08, 0.0, eave)          # back wall
    for a in (-h, h):
        fr.box(o.L("wood_dark"), a - 0.04, a + 0.04, -D, -1.2, 0.0, eave)
    fr.box(o.L("wood"), -h - 0.15, h + 0.15, -0.2, -0.06, eave - 0.2, eave)          # front beam
    fr.box(o.L("wood"), -h - 0.15, h + 0.15, -D + 0.06, -D + 0.2, eave - 0.2, eave)
    counter(o, fr, -h + 0.25, h - 0.25, "wood_dark", "green")
    back_bar(o, fr, -h + 0.3, h - 0.3, -D + 0.08, s.get("backbar", "green_dim"), rng)
    tops = []
    for i, a in enumerate((-h * 0.66, 0.0, h * 0.66)):
        tops.append(witch_hat(o, fr, a, -D / 2, eave + (0.12 if i == 1 else 0.0), 1.58, 1.12, rng.uniform(2.3, 2.9),
                              ("purple", "orange", "purple")[i], rng))
    festoon(o, fr.p(-h, 0.05, eave - 0.3), fr.p(h, 0.05, eave - 0.3), 0.18, spacing=0.42, r=0.055, key="bulb_warm")
    sgn = s.get("cauldron_side", 1)                                   # the cauldron beyond one end of the bar
    cc = fr.p(sgn * (h + 1.05), -D / 2 + 0.1, 0.0)
    for i in range(3):
        ang = 2 * math.pi * i / 3 + 0.3
        q = cc + Vector((math.cos(ang), math.sin(ang), 0.0)) * 0.55
        cyl(o.L("metal_dark"), q, cc + Vector((math.cos(ang), math.sin(ang), 0.0)) * 0.45 + Z * 0.45, 0.05, segs=4)
    cyl(o.L("metal_dark"), cc + Z * 0.3, cc + Z * 0.62, 0.48, segs=10, r2=0.72)
    cyl(o.L("metal_dark"), cc + Z * 0.62, cc + Z * 1.0, 0.72, segs=10, r2=0.62)
    cyl(o.L("metal_dark"), cc + Z * 1.0, cc + Z * 1.08, 0.66, segs=10, cap=False)
    o.G(cyl(o.glow, cc + Z * 1.0, cc + Z * 1.03, 0.6, segs=10), "green_dim")
    for i in range(5):
        ang = rng.uniform(0, 2 * math.pi)
        rr = rng.uniform(0.1, 0.45)
        o.G(octa(o.glow, cc + Vector((math.cos(ang) * rr, math.sin(ang) * rr, 1.06)), rng.uniform(0.05, 0.1)), "lime")
    fs = []
    for i in range(3):                                                # rising bubbles above the brew
        fs += octa(o.glow, cc + Z * (1.35 + 0.35 * i) + Vector((rng.uniform(-0.2, 0.2), rng.uniform(-0.2, 0.2), 0.0)),
                   0.06 + 0.02 * i)
    o.G(fs, "green_dim")
    o.lamp("POINT", cc + Z * 1.7, GREEN_L, 70, size=0.4)
    o.block(cc, 0.85)
    request_sign(o, fr, s["text"], s["px"], s["key"], max(tops), a=0.0, shift=s.get("sign_a", 0.0), b_back=-D, keys=s.get("keys"),
                 border=s.get("border"))
    o.lamp("POINT", fr.p(0.0, -1.4, eave - 0.45), WARM, 70, size=0.5)
    pool(o, fr, -h * 0.4, b_aim=1.0, power=s.get("pool", 800), color=WARM)
    pool(o, fr, h * 0.45, b_aim=1.0, power=s.get("pool", 800) * 0.8, color=PURPLE_L)
    for i in range(3):
        staff(o, fr, -h * 0.6 + i * h * 0.6, -1.5, rng)
    n = s.get("q", 8)
    for i in range(n):
        a = -h + 0.5 + (Lb - 1.0) * (i + rng.uniform(0.2, 0.8)) / n
        o.person(fr.p(a, 0.5 + rng.uniform(0.0, 0.2) + (0.75 if i % 3 == 1 else 0.0)), -fr.F,
                 rng.choice(("down", "one", "hips")))
    o.block_rect(fr, -h - 0.2, h + 0.2, -D, 0.05)
    return {"anchors": [fr.p(-h - 0.1, -0.1, eave), fr.p(h + 0.1, -0.1, eave)]}


def u_coffinbar(o, fr, rng, s):
    """SPIRITS: a bar whose back wall is a row of upright open coffins (glowing interiors, bottle silhouettes), a flat
    black canopy with a toothed purple valance, and a big coffin-shaped sign."""
    Lb, D = s.get("L", 7.2), 2.8
    h = Lb / 2
    eave = 2.75
    for a in (-h, -h / 3, h / 3, h):
        for b in (-0.1, -D + 0.1):
            fr.cyl(o.L("metal_dark"), a, b, 0.0, eave, 0.05, segs=5)
    fr.box(o.L("canvas_black"), -h - 0.2, h + 0.2, -D - 0.05, 0.25, eave, eave + 0.12)
    valance(o, fr, -h - 0.2, h + 0.2, 0.25, eave + 0.1, "canvas_black", teeth=0.55)
    o.G(fr.box(o.glow, -h - 0.2, h + 0.2, 0.29, 0.32, eave + 0.04, eave + 0.09), s.get("trim", "purple"))
    counter(o, fr, -h + 0.25, h - 0.25, "wood_dark", s.get("led", "purple"))
    n = 5
    cw, ch = 1.05, 2.4
    keys = s.get("coffin_glow", ("red_dim", "purple_dim", "amber", "purple_dim", "red_dim"))
    for i in range(n):
        a = -h + 0.35 + cw / 2 + i * (Lb - 0.7 - cw) / (n - 1)
        prof = [(a + u, z + 0.05) for u, z in upright_coffin(cw, ch)]
        fr.prism(o.L("wood_dark"), prof, -D, -D + 0.42)
        inner = [(a + u * 0.8, 0.05 + 0.12 + z * 0.88) for u, z in upright_coffin(cw, ch)]
        o.G(poly(o.glow, [fr.p(ua, -D + 0.43, zz) for ua, zz in inner], fr.F), keys[i % len(keys)])
        fs = []
        for zsh in (0.75, 1.35):
            x = a - 0.28
            while x < a + 0.22:
                bw_ = rng.uniform(0.07, 0.1)
                fs += fr.quad_f(o.glow, x, x + bw_, -D + 0.45, zsh, zsh + rng.uniform(0.2, 0.3))
                x += bw_ + rng.uniform(0.04, 0.12)
        o.G(fs, "black")
    festoon(o, fr.p(-h, 0.2, eave - 0.15), fr.p(h, 0.2, eave - 0.15), 0.25, spacing=0.45, r=0.055,
            key=("orange", "purple"))
    request_sign(o, fr, s["text"], s["px"], s["key"], eave + 0.15, a=0.0, shift=s.get("sign_a", 0.0), b_back=-D, shape="coffin",
                 border=s.get("border", "purple"), board="wood_dark")
    o.lamp("POINT", fr.p(0.0, -1.5, eave - 0.4), (1.0, 0.35, 0.25), 70, size=0.5)
    pool(o, fr, -h * 0.45, b_aim=1.0, power=s.get("pool", 800), color=WARM)
    pool(o, fr, h * 0.45, b_aim=1.0, power=s.get("pool", 800) * 0.8, color=PURPLE_L)
    for i in range(2):
        staff(o, fr, -h * 0.35 + i * h * 0.7, -1.5, rng)
    nq = s.get("q", 7)
    for i in range(nq):
        a = -h + 0.5 + (Lb - 1.0) * (i + rng.uniform(0.2, 0.8)) / nq
        o.person(fr.p(a, 0.62 + rng.uniform(0.0, 0.2) + (0.75 if i % 3 == 1 else 0.0)), -fr.F,
                 rng.choice(("down", "one", "hips")))
    o.block_rect(fr, -h - 0.2, h + 0.2, -D, 0.32)
    return {"anchors": [fr.p(-h - 0.2, 0.25, eave + 0.05), fr.p(h + 0.2, 0.25, eave + 0.05)]}


def u_stall(o, fr, rng, s):
    """Witch-hat stall: open-front booth (walls, counter with a colored skirt, back table, menu light box), a witch-hat
    roof with a glowing band, a toothed valance, bulbs under the eave; extras per vendor."""
    S, D = s.get("S", 3.4), s.get("D", 2.55)
    h = S / 2
    eave = 2.45
    walls = o.L(s.get("walls", "canvas_black"))
    for a in (-h, h):
        for b in (-0.05, -D + 0.05):
            fr.cyl(o.L("metal_dark"), a, b, 0.0, eave, 0.04, segs=5)
    fr.box(walls, -h, h, -D, -D + 0.05, 0.0, eave)
    for a in (-h, h):
        fr.box(walls, a - 0.025, a + 0.025, -D, -0.6, 0.0, eave)
    fr.box(o.L("wood_dark"), -h - 0.05, h + 0.05, -0.1, 0.0, eave - 0.12, eave)
    top = witch_hat(o, fr, 0.0, -D / 2, eave, min(1.62, D / 2 + 0.45), min(1.1, D / 2 - 0.1), s.get("hat_h", 2.4),
                    s["band"], rng)
    valance(o, fr, -h - 0.05, h + 0.05, 0.02, eave - 0.02, s.get("valance", "canvas_black"), teeth=0.48)
    fr.box(o.L(s.get("skirt", "plastic_orange")), -h + 0.15, h - 0.15, -0.7, -0.15, 0.0, 0.95)
    fr.box(o.L("wood"), -h + 0.1, h - 0.1, -0.78, -0.08, 0.95, 1.0)
    fr.box(o.L("wood_dark"), -h + 0.25, h - 0.25, -D + 0.06, -D + 0.55, 0.0, 0.88)
    o.G(fr.quad_f(o.glow, -h * 0.6, h * 0.6, -D + 0.07, 1.3, 2.0), s.get("menu", "warm_dim"))
    festoon(o, fr.p(-h, 0.08, eave - 0.32), fr.p(h, 0.08, eave - 0.32), 0.14, spacing=0.4, r=0.05,
            key=s.get("bulbs", "bulb_warm"))
    ex = s.get("extra")
    if ex == "lanterns":                                              # paper lanterns along the front
        nl = 4
        for i in range(nl):
            a = -h + (i + 0.5) * S / nl
            fr.cyl(o.L("metal_dark"), a, 0.1, eave - 0.7, eave - 0.3, 0.008, segs=3)
            o.G(ball(o.glow, fr.p(a, 0.1, eave - 0.9), 0.19, 6, 3, (1, 1, 1.2)), "red" if i % 2 else "orange")
    elif ex == "shirts":                                              # merch wall
        cols = ("plastic_orange", "canvas_black", "canvas_green", "bone", "canvas_red", "plastic_orange")
        n = int(S / 0.72)
        for r_ in range(2):
            for i in range(n):
                a = -h + 0.4 + i * (S - 0.8) / max(1, n - 1)
                fr.box(o.L(cols[(i + 2 * r_) % len(cols)]), a - 0.25, a + 0.25, -D + 0.06, -D + 0.1,
                       1.05 + r_ * 0.6, 1.52 + r_ * 0.6)
    elif ex == "bags":                                                # BLOOD BANK: hanging blood bags + an IV stand
        fs = []
        for i in range(6):
            a = -h + 0.45 + i * (S - 0.9) / 5
            fr.cyl(o.L("metal_dark"), a, -D + 0.25, 2.25, 2.4, 0.008, segs=3)
            fs += fr.box(o.glow, a - 0.11, a + 0.11, -D + 0.2, -D + 0.3, 1.8, 2.25)
        o.G(fs, "red_dim")
        fr.box(o.L("metal_dark"), -h + 0.3, h - 0.3, -D + 0.2, -D + 0.3, 2.38, 2.42)
        p = fr.p(h + 0.45, 0.25)
        cyl(o.L("metal_alu"), p, p + Z * 2.0, 0.025, segs=4)
        cyl(o.L("metal_alu"), p + Z * 1.95, p + Z * 1.95 + fr.R * 0.3, 0.02, segs=3)
        o.G(box(o.glow, p + Z * 1.62 + fr.R * 0.28, (0.2, 0.07, 0.3), yaw=fr.yaw), "red")
        o.block(p, 0.3)
    elif ex == "cone":                                                # SCREAM CREAM: a giant screaming ice cream
        p = fr.p(h + 0.55, -0.4)
        cyl(o.L("metal_dark"), p, p + Z * 2.3, 0.04, segs=4)
        cone(o.L("wood"), p + Z * 3.15, p + Z * 2.2, 0.38, segs=7)
        sc = p + Z * 3.45
        ball(o.L("bone"), sc, 0.46, 7, 4)
        to = face_dj(p, fr.F, 0.6)
        rt = Vector((-to.y, to.x, 0.0))
        o.G(box(o.glow, sc + to * 0.43 + Z * 0.08 + rt * 0.14, (0.1, 0.03, 0.17), yaw=math.atan2(rt.y, rt.x))
            + box(o.glow, sc + to * 0.43 + Z * 0.08 - rt * 0.14, (0.1, 0.03, 0.17), yaw=math.atan2(rt.y, rt.x))
            + box(o.glow, sc + to * 0.42 - Z * 0.17, (0.12, 0.03, 0.24), yaw=math.atan2(rt.y, rt.x)), "black")
        top = max(top, 3.95)
        o.block(p, 0.3)
    elif ex == "apple":                                               # POISON APPLES: a glowing apple on a post
        p = fr.p(h + 0.5, -0.45)
        cyl(o.L("metal_dark"), p, p + Z * 2.5, 0.04, segs=4)
        o.G(ball(o.glow, p + Z * 2.95, 0.48, 7, 4, (1.0, 1.0, 0.9)), "green_dim")
        cyl(o.L("wood_dark"), p + Z * 3.3, p + Z * 3.62, 0.04, segs=4)
        slab(o.L("canvas_green"), [p + Z * 3.5, p + Z * 3.62 + fr.R * 0.28, p + Z * 3.46 + fr.R * 0.2], fr.F * 0.02)
        fs = []
        for i in range(9):                                            # candy apples on the counter
            fs += octa(o.glow, fr.p(-h + 0.4 + i * (S - 0.8) / 8, -0.4, 1.12), 0.07)
        o.G(fs, "red_dim")
        top = max(top, 3.7)
        o.block(p, 0.3)
    request_sign(o, fr, s["text"], s["px"], s["key"], top, a=0.0, shift=s.get("sign_a", 0.0), b_back=-D, keys=s.get("keys"),
                 border=s.get("border"))
    o.lamp("POINT", fr.p(0.0, -D * 0.55, eave - 0.4), s.get("inner_col", WARM_WHITE), s.get("inner", 45), size=0.4)
    pool(o, fr, 0.0, b_aim=1.0, power=s.get("pool", 800), color=s.get("pool_col", WARM))
    staff(o, fr, rng.uniform(-h * 0.3, h * 0.3), -1.35, rng)
    queue(o, fr, rng.uniform(-0.35, 0.35), s.get("q", 3), rng, b0=0.62)
    o.block_rect(fr, -h - 0.1, h + 0.1, -D, 0.15)
    return {"anchors": [fr.p(-h - 0.05, 0.0, eave), fr.p(h + 0.05, 0.0, eave)]}


def u_coffee(o, fr, rng, s):
    """COFFIN COFFEE: an upright coffin kiosk (3.4 m) with a serving window, its lid swung open against the side,
    a glowing amber interior with a barista, a counter shelf, and a giant cup on its head."""
    W, H, D = 2.5, 3.4, 2.0
    out = upright_coffin(W, H, foot=0.68, top=0.72, sh=0.68)

    def hw(z):                                                        # half-width of the outline at height z
        zs = 0.68 * H
        if z <= zs:
            return 0.68 * W / 2 + (W / 2 - 0.68 * W / 2) * z / zs
        return W / 2 + (0.72 * W / 2 - W / 2) * (z - zs) / (H - zs)

    wood = o.L(s.get("body", "wood_dark"))
    fr.prism(wood, out, -D, -0.5)                                     # body
    w0, w1, z0, z1 = 0.62, 0.62, 1.0, 2.1                             # window (a -w0..w1, z z0..z1)
    fr.prism(wood, [(-hw(0), 0.0), (hw(0), 0.0), (hw(z0), z0), (-hw(z0), z0)], -0.5, 0.0)
    fr.prism(wood, sorted_ccw([(-hw(z1), z1), (hw(z1), z1), (W / 2, 0.68 * H), (0.72 * W / 2, H), (-0.72 * W / 2, H),
                               (-W / 2, 0.68 * H)]), -0.5, 0.0)
    fr.prism(wood, [(w1, z0), (hw(z0), z0), (hw(z1), z1), (w1, z1)], -0.5, 0.0)
    fr.prism(wood, [(-hw(z0), z0), (-w0, z0), (-w0, z1), (-hw(z1), z1)], -0.5, 0.0)
    o.G(fr.quad_f(o.glow, -w0, w1, -0.5, z0, z1), s.get("inside", "amber"))
    fr.box(o.L("canvas_black"), -0.22, 0.22, -0.45, -0.25, z0 - 0.05, z0 + 0.5)      # barista silhouette
    o.G(octa(o.glow, fr.p(0.0, -0.35, z0 + 0.68), 0.13, 0.15), "black")
    fr.box(o.L("wood"), -w0 - 0.1, w1 + 0.1, -0.05, 0.35, z0 - 0.06, z0)
    fs = []                                                           # glowing outline on the front edges
    for (a0, zz0), (a1, zz1) in zip(out, out[1:] + out[:1]):
        p0, p1 = fr.p(a0, 0.015, zz0), fr.p(a1, 0.015, zz1)
        d = p1 - p0
        fs += obox(o.glow, (p0 + p1) / 2, d, fr.F, (d.length + 0.06, 0.03, 0.06))
    o.G(fs, s.get("trim", "orange"))
    phi = math.radians(166)                                           # the lid, hinged at the right shoulder
    hinge_a = W / 2
    dl = fr.R * (-math.cos(phi)) + fr.F * math.sin(phi)
    lid = [fr.p(hinge_a, 0.04, 0.0) + dl * (W / 2 - u) + Z * z for u, z in out]
    slab(wood, lid, dl.cross(Z).normalized() * 0.09)
    c = fr.p(0.0, -D / 2 - 0.25, H)                                   # the giant cup
    cyl(o.L("bone"), c, c + Z * 0.9, 0.38, segs=8, r2=0.5)
    cyl(o.L("wood_dark"), c + Z * 0.28, c + Z * 0.6, 0.43, segs=8, r2=0.47)
    cyl(o.L("canvas_black"), c + Z * 0.9, c + Z * 1.0, 0.54, segs=8)
    request_sign(o, fr, s["text"], s["px"], s["key"], H + 1.1, a=0.0, shift=s.get("sign_a", 0.0), b_back=-D, keys=s.get("keys"),
                 border=s.get("border"))
    o.lamp("POINT", fr.p(0.0, 0.6, z1), WARM_WHITE, 35, size=0.3)
    pool(o, fr, 0.0, b_aim=1.0, power=s.get("pool", 750), color=s.get("pool_col", ORANGE_L))
    queue(o, fr, 0.0, s.get("q", 4), rng, b0=0.85)
    lid_reach = max(fr.R.dot(q - fr.o) for q in lid)
    o.block_rect(fr, -W / 2, max(W / 2, lid_reach) + 0.1, -D, 0.4)
    return {"anchors": [fr.p(-0.72 * W / 2, -0.25, H), fr.p(0.72 * W / 2, -0.25, H)]}


def u_morgue(o, fr, rng, s):
    """MORGUE LOCKERS: a steel booth with a wall of square morgue-drawer doors (status LEDs), one drawer pulled out with
    a sheeted body, a charging desk with a green screen, a flat canopy; signs MORGUE / LOCKERS + CHARGE."""
    Lm, D, H = s.get("L", 5.6), 2.0, 2.6
    h = Lm / 2
    fr.box(o.L("metal_grey"), -h, h, -D, 0.0, 0.0, H)
    fr.box(o.L("canvas_black"), -h - 0.15, h + 0.15, -D - 0.1, 0.85, H, H + 0.12)
    for a in (-h, h):
        fr.cyl(o.L("metal_dark"), a, 0.78, 0.0, H, 0.04, segs=5)
    cols, rows = 5, 3
    a_l0, a_l1 = -h + 0.2, h - 1.6
    dw, dz = (a_l1 - a_l0) / cols, (2.35 - 0.3) / rows
    dots = {"green_dim": [], "red_dim": [], "lime": []}
    pulled = (2, 0)
    for c in range(cols):
        for r in range(rows):
            a, z = a_l0 + c * dw, 0.3 + r * dz
            if (c, r) == pulled:
                fr.box(o.L("metal_dark"), a + 0.05, a + dw - 0.05, -0.05, 0.0, z + 0.05, z + dz - 0.05)
                continue
            fr.box(o.L("metal_alu"), a + 0.04, a + dw - 0.04, 0.0, 0.04, z + 0.04, z + dz - 0.04)
            kk = rng.choice(("green_dim", "green_dim", "lime", "red_dim"))
            dots[kk] += fr.quad_f(o.glow, a + dw / 2 - 0.05, a + dw / 2 + 0.05, 0.045, z + dz - 0.17, z + dz - 0.09)
    for kk, fs in dots.items():
        o.G(fs, kk)
    a, z = a_l0 + pulled[0] * dw, 0.3 + pulled[1] * dz                # the pulled drawer + sheeted body
    fr.box(o.L("metal_alu"), a + 0.06, a + dw - 0.06, 0.0, 0.78, z + 0.08, z + 0.2)
    fr.box(o.L("bone"), a + 0.14, a + dw - 0.14, 0.05, 0.62, z + 0.2, z + 0.42)
    ball(o.L("bone"), fr.p(a + dw / 2, 0.66, z + 0.36), 0.15, 6, 3)
    a0, a1 = a_l1 + 0.15, h - 0.12                                    # charging desk + screen
    fr.box(o.L("metal_grey"), a0, a1, 0.0, 0.5, 0.0, 1.0)
    o.G(fr.box(o.glow, a0, a1, 0.5, 0.53, 0.9, 0.95), "green")
    o.G(fr.quad_f(o.glow, a0 + 0.12, a1 - 0.12, 0.01, 1.3, 2.15), "green_dim")
    request_sign(o, fr, s["text"], s["px"], s["key"], H + 0.15, a=0.0, shift=s.get("sign_a", 0.0), b_back=-D, keys=s.get("keys"),
                 border=s.get("border"))
    ch = dict(lines=["CHARGE"], px=0.065, key="amber", border="orange", size=sign_size(["CHARGE"], 0.065))
    cc = fr.p(h - 0.1 - ch["size"][0] / 2, 0.8, H + 0.14 + ch["size"][1] / 2)
    sign_board(o, ch, cc, fr.F)
    o.lamp("POINT", fr.p((a0 + a1) / 2, 0.9, H - 0.3), (0.55, 1.0, 0.5), 30, size=0.4)
    pool(o, fr, -h * 0.25, b_aim=1.1, power=s.get("pool", 750), color=s.get("pool_col", GREEN_L))
    queue(o, fr, (a0 + a1) / 2, 3, rng, b0=1.05)
    for i in range(2):
        o.person(fr.p(-h + 0.7 + i * 1.5 + rng.uniform(-0.2, 0.2), 1.1), -fr.F, "down")
    o.block_rect(fr, -h - 0.15, h + 0.15, -D, 0.85)
    return {"anchors": [fr.p(-h - 0.15, 0.8, H + 0.1), fr.p(h + 0.15, 0.8, H + 0.1)]}


def u_water(o, fr, rng, s):
    """HOLY WATER: a stone font (trough with taps, green LED) between two stone pillars with a pointed gable, two
    tanks behind; refill point."""
    Wd, D = 3.6, 2.2
    h = Wd / 2
    st = o.L("stone")
    for a in (-h, h):
        fr.box(st, a - 0.22, a + 0.22, -1.2, -0.75, 0.0, 2.7)
    fr.box(st, -h - 0.3, h + 0.3, -1.25, -0.7, 2.7, 3.0)
    fr.prism(st, [(-h - 0.3, 3.0), (h + 0.3, 3.0), (0.0, 3.9)], -1.2, -0.75)
    o.G(fr.quad_f(o.glow, -0.18, 0.18, -0.74, 3.12, 3.62), "purple_dim")
    fr.box(st, -h + 0.25, h - 0.25, -0.75, -0.15, 0.0, 0.85)
    o.G(fr.box(o.glow, -h + 0.25, h - 0.25, -0.15, -0.11, 0.74, 0.8), "green")
    o.G(poly(o.glow, [fr.p(-h + 0.35, -0.68, 0.86), fr.p(h - 0.35, -0.68, 0.86), fr.p(h - 0.35, -0.22, 0.86),
                      fr.p(-h + 0.35, -0.22, 0.86)], Z), "green_dim")
    for i in range(5):
        a = -h + 0.6 + i * (Wd - 1.2) / 4
        fr.box(o.L("metal_alu"), a - 0.03, a + 0.03, -0.62, -0.52, 0.85, 1.3)
    for a in (-0.95, 0.95):
        c = fr.p(a, -D + 0.62, 0.0)
        cyl(o.L("metal_grey"), c, c + Z * 2.1, 0.6, segs=10)
    request_sign(o, fr, s["text"], s["px"], s["key"], 4.0, a=0.0, shift=s.get("sign_a", 0.0), b_back=-D, keys=s.get("keys"),
                 border=s.get("border"))
    o.lamp("POINT", fr.p(0.0, 0.3, 1.8), GREEN_L, 25, size=0.4)
    pool(o, fr, 0.0, b_aim=0.8, power=s.get("pool", 650), color=s.get("pool_col", PURPLE_L))
    queue(o, fr, -0.9, 2, rng, b0=0.55)
    queue(o, fr, 0.9, 2, rng, b0=0.6)
    o.block_rect(fr, -h - 0.3, h + 0.3, -D, 0.0)
    return {"anchors": [fr.p(-h - 0.3, -1.0, 3.0), fr.p(h + 0.3, -1.0, 3.0)]}


def crescent(cx, cz, r, n=7):
    """Crescent moon (u, z) around (cx, cz), opening to +u: the outer arc and the matching inner arc, point for point
    (callers join them with quads)."""
    outer = [(cx + r * math.cos(t), cz + r * math.sin(t)) for t in
             [math.radians(110 + (250 - 110) * i / n) for i in range(n + 1)]]
    inner = [(cx + 0.35 * r + 0.78 * r * math.cos(t), cz + 0.78 * r * math.sin(t)) for t in
             [math.radians(250 - (250 - 110) * i / n) for i in range(n + 1)]]
    return outer, inner


def u_outhouses(o, lane, u0, rng, n=8):
    """A row of wooden outhouses (crescent moons glowing in the doors) with the skull WC light tower at its stage end.
    Returns the station where the row ends."""
    w, Dd = 1.3, 1.35
    tower_gap = 2.4
    F = lane.n_in
    ut = u0 + tower_gap / 2
    tb = lane.point(ut, D_BACK - 1.2 * NRM)                          # tower base (in the band)
    fr0 = Frame(lane.point(u0 + tower_gap + n * w / 2, D_BACK) + F * Dd, F)
    for i in range(n):
        a = (i + 0.5 - n / 2) * w
        fr0.box(o.L("wood"), a - 0.6, a + 0.6, -Dd, -0.05, 0.0, 2.2)
        rz0 = 2.2
        fr0.prism(o.L("wood_dark"), [(a - 0.68, rz0 + 0.0), (a + 0.68, rz0), (a + 0.68, rz0 + 0.08),
                                     (a - 0.68, rz0 + 0.08)], -Dd - 0.1, 0.1)
        fr0.box(o.L("wood_dark"), a - 0.44, a + 0.44, -0.05, 0.0, 0.08, 2.02)
        outer, inner = crescent(a + 0.05, 1.75, 0.13)
        pts = [fr0.p(u, 0.005, z) for u, z in outer + inner]
        fs = []
        for k in range(len(outer) - 1):
            q = [pts[k], pts[k + 1], pts[len(pts) - 2 - k], pts[len(pts) - 1 - k]]
            fs += poly(o.glow, q, fr0.F)
        o.G(fs, "amber")
        if rng.random() < 0.5:
            o.G(fr0.quad_f(o.glow, a + 0.28, a + 0.36, 0.005, 1.05, 1.13), "red_dim" if rng.random() < 0.5 else
                "green_dim")
    o.block_rect(fr0, -n * w / 2 - 0.1, n * w / 2 + 0.1, -Dd - 0.1, 0.1)
    # the WC light tower: generator trailer, mast, lamp bar aimed at the doors, a glowing skull, the WC sign
    bz = Vector((tb.x, tb.y, GROUND_Z))
    to = F
    side_v = Vector((-to.y, to.x, 0.0))
    yaw_to = math.atan2(side_v.y, side_v.x)
    box(o.L("metal_dark"), bz + Z * 0.62, (1.1, 1.6, 0.8), yaw=yaw_to)
    for e in (-1, 1):
        cyl(o.L("rubber"), bz + side_v * (e * 0.52) + Z * 0.3, bz + side_v * (e * 0.7) + Z * 0.3, 0.3, segs=7)
    mast = 7.4
    cyl(o.L("metal_grey"), bz + Z * 1.0, bz + Z * mast, 0.08, segs=6)
    head = bz + Z * mast
    box(o.L("metal_dark"), head, (1.7, 0.12, 0.12), yaw=yaw_to)
    lamps = []
    for e in (-0.6, 0.0, 0.6):
        lamps += box(o.glow, head + side_v * e - Z * 0.18 + to * 0.1, (0.36, 0.16, 0.22), yaw=yaw_to)
    o.G(lamps, "bulb_warm")
    sk = head + Z * 0.95                                              # the glowing skull on top
    skull = ball(o.glow, sk, 0.62, 8, 5, (0.92, 0.85, 1.0))
    skull += box(o.glow, sk - Z * 0.55 + to * 0.12, (0.6, 0.45, 0.3), yaw=yaw_to)
    o.G(skull, "white_dim")
    fdj = face_dj(sk, to, 0.85)
    rdj = Vector((-fdj.y, fdj.x, 0.0))
    yd = math.atan2(rdj.y, rdj.x)
    o.G(box(o.glow, sk + fdj * 0.5 + rdj * 0.22 + Z * 0.06, (0.24, 0.2, 0.24), yaw=yd)
        + box(o.glow, sk + fdj * 0.5 - rdj * 0.22 + Z * 0.06, (0.24, 0.2, 0.24), yaw=yd)
        + box(o.glow, sk + fdj * 0.55 - Z * 0.18, (0.1, 0.12, 0.14), yaw=yd), "black")
    fs = []
    for i in range(4):
        fs += box(o.glow, sk - Z * 0.5 + fdj * 0.36 + rdj * (-0.21 + i * 0.14), (0.07, 0.06, 0.12), yaw=yd)
    o.G(fs, "black")
    cyl(o.L("metal_dark"), head + Z * 0.06, sk - Z * 0.5, 0.05, segs=4)
    wc = dict(lines=["WC"], px=0.22, key="green", border="purple", size=sign_size(["WC"], 0.22))
    c = bz + Z * 5.0
    sign_board(o, wc, c + fdj * 0.16, fdj)
    sign_board(o, wc, c - fdj * 0.16, -fdj)
    o.lamp("SPOT", head - Z * 0.2 + to * 1.2, WARM_WHITE, 2600, target=fr0.p(0.0, 0.5, 0.6), size=0.5, deg=82)
    o.block(bz, 1.15)
    for i in range(5):                                                # a queue along the row
        o.person(fr0.p((-1.6 + i * 0.78) * (1 if lane.s > 0 else -1) + rng.uniform(-0.12, 0.12),
                       1.05 + (i % 2) * 0.45), -fr0.F, rng.choice(("down", "hips")))
    return u0 + tower_gap + n * w, head


# ------------------------------------------------------------------ the lanes
FOOT = {   # kind -> local footprint (a0, a1, b0) incl. everything below 3 m; b1 (front overhang) per unit below
    "hearse": lambda s: (-s.get("L", 6.8) / 2 - 0.05, s.get("L", 6.8) / 2 + 0.05, -2.2, 0.85),
    "witchbar": lambda s: (-s.get("L", 7.6) / 2 - (2.0 if s.get("cauldron_side", 1) < 0 else 0.2),
                           s.get("L", 7.6) / 2 + (2.0 if s.get("cauldron_side", 1) > 0 else 0.2), -2.75, 0.1),
    "coffinbar": lambda s: (-s.get("L", 7.2) / 2 - 0.25, s.get("L", 7.2) / 2 + 0.25, -2.8, 0.32),
    "stall": lambda s: (-s.get("S", 3.4) / 2 - (0.0 if s.get("extra") not in ("cone", "apple", "bags") else 0.0) - 0.15,
                        s.get("S", 3.4) / 2 + (1.0 if s.get("extra") in ("cone", "apple", "bags") else 0.15),
                        -s.get("D", 2.55), 0.5),
    "coffee": lambda s: (-1.3, 3.8, -2.0, 0.75),
    "morgue": lambda s: (-s.get("L", 5.6) / 2 - 0.2, s.get("L", 5.6) / 2 + 0.2, -2.0, 0.85),
    "water": lambda s: (-2.15, 2.15, -2.2, 0.0),
}
BUILD = {"hearse": u_hearse, "witchbar": u_witchbar, "coffinbar": u_coffinbar, "stall": u_stall, "coffee": u_coffee,
         "morgue": u_morgue, "water": u_water}

LEFT = [   # stage end -> far end; px grows with the distance from the DJ (signs subtend about the same angle)
    dict(kind="witchbar", name="WITCH'S BREW", L=7.6, text=["WITCH'S", "BREW"], px=0.11, key="green",
         keys=["green", "orange"], border="purple", backbar="green_dim", cauldron_side=1, q=8, gap=1.6),
    dict(kind="hearse", name="BAT BITES", L=6.8, cab=-1, trim="purple", inside="bulb_warm", extra="bat",
         text=["BAT", "BITES"], px=0.13, key="orange", border="purple", pool_col=PURPLE_L, gap=1.5),
    dict(kind="stall", name="BRAINS", S=3.4, band="green", skirt="canvas_red", valance="canvas_red", extra="lanterns",
         text=["BRAINS"], px=0.12, key="red", border="amber", menu="warm_dim", pool_col=WARM, gap=1.4),
    dict(kind="hearse", name="GRAVE DIGGER DOGS", L=7.0, cab=1, trim="orange", inside="bulb_warm", extra="coffin",
         text=["GRAVE", "DIGGER", "DOGS"], px=0.12, key="orange", keys=["orange", "orange", "lime"], border="green", gap=1.5),
    dict(kind="stall", name="SCREAM CREAM", S=3.2, band="purple", skirt="bone", valance="canvas_black", extra="cone",
         text=["SCREAM", "CREAM"], px=0.125, key="amber", keys=["red", "amber"], border="purple", menu="warm_dim",
         pool_col=PURPLE_L, inner_col=(0.75, 0.5, 1.0), gap=1.3),
    dict(kind="water", name="HOLY WATER", text=["HOLY", "WATER"], px=0.14, key="green", keys=["amber", "green"],
         border="purple", gap=1.4),
]

RIGHT = [
    dict(kind="coffinbar", name="SPIRITS", L=7.2, text=["SPIRITS"], px=0.12, key="orange", border="purple",
         led="purple", trim="orange", q=7, gap=1.6),
    dict(kind="hearse", name="HEX BURGERS", L=6.8, cab=1, trim="green", inside="bulb_warm", extra="hat",
         text=["HEX", "BURGERS"], px=0.11, key="green", keys=["green", "orange"], border="orange", pool_col=WARM,
         gap=1.5),
    dict(kind="stall", name="POISON APPLES", S=3.3, band="lime", skirt="canvas_green", valance="canvas_black",
         extra="apple", text=["POISON", "APPLES"], px=0.125, key="lime", keys=["lime", "red"], border="green",
         pool_col=GREEN_L, inner_col=(0.6, 1.0, 0.5), gap=2.6, seats=True),
    dict(kind="stall", name="BLOOD BANK", S=3.4, band="red", walls="plastic_white", skirt="canvas_red",
         valance="canvas_red", extra="bags", text=["BLOOD", "BANK"], px=0.14, key="red", border="red", menu="red_dim",
         pool_col=RED_L, inner_col=(1.0, 0.45, 0.4), gap=1.4),
    dict(kind="coffee", name="COFFIN COFFEE", text=["COFFIN", "COFFEE"], px=0.125, key="amber", keys=["orange", "amber"],
         border="orange", trim="orange", gap=1.5),
    dict(kind="hearse", name="BONE BROTH", L=6.6, cab=-1, trim="amber", inside="bulb_warm", extra="pot",
         text=["BONE", "BROTH"], px=0.15, key="amber", border="green", pool_col=ORANGE_L, gap=2.6, seats=True),
    dict(kind="stall", name="CURSED MERCH", S=3.6, band="orange", skirt="canvas_black", valance="plastic_orange",
         extra="shirts", menu="black", text=["CURSED", "MERCH"], px=0.13, key="purple", keys=["purple", "orange"],
         border="orange", pool_col=PURPLE_L, inner_col=(0.8, 0.55, 1.0), gap=1.4),
    dict(kind="morgue", name="MORGUE LOCKERS", L=5.4, text=["MORGUE", "LOCKERS"], px=0.115, key="lime",
         keys=["lime", "green"], border="green", sign_a=1.6, gap=1.0),
]


def place_unit(lane, s, u_start):
    """Frame for unit s whose stage-side footprint end sits at station u_start: parallel to the crowd edge, back on
    d = D_BACK. -> (frame, u_end, foot)."""
    a0, a1, b0, b1 = FOOT[s["kind"]](s)
    if b1 - b0 > DEPTH_MAX + 1e-6:
        log(f"WARNING {s['name']}: depth {b1 - b0:.2f} m > band {DEPTH_MAX:.2f} m")
    F = lane.n_in
    R = Vector((-F.y, F.x, 0.0))
    sgn = R.dot(lane.t)                                               # +1 if +a points toward the back
    e1 = -min(sgn * a0, sgn * a1)
    e2 = max(sgn * a0, sgn * a1)
    uc = u_start + e1
    o = lane.point(uc, D_BACK) - F * b0
    return Frame(o, F), uc + e2, (a0, a1, b0, b1)


def flank(o, side, plan, rng):
    lane = Lane(side)
    u = 0.6
    placed = []
    # fronts sit further back in y than backs (the band slants): a unit 3.1 m deep needs 1.7 m of station at the end
    if side < 0:
        limit = lane.length() - 0.9 - (2.4 + 8 * 1.3)                 # the outhouse row (+ tower) takes the far end
        trailing = plan[-1].get("gap", 1.5)
    else:
        limit = lane.length() - 2.4
        trailing = 0.0
    units = sum(place_unit(lane, s, 0.0)[1] for s in plan)
    gaps = sum(s.get("gap", 1.5) for s in plan[:-1])
    gscale = min(1.0, max(0.3, (limit - u - trailing - units) / gaps))
    if gscale < 1.0:
        log(f"{'LR'[side > 0]} lane: gaps scaled x{gscale:.2f} to fit")
    for i, s in enumerate(plan):
        fr, u_end, foot = place_unit(lane, s, u)
        res = o.run(s["name"], BUILD[s["kind"]], fr, rng, s)
        res["foot"], res["u0"], res["u1"], res["fr"], res["s"] = foot, u, u_end, fr, s
        corners = [fr.p(a, b) for a in foot[:2] for b in foot[2:]]
        dmin = min(dval(side, c.x, c.y) for c in corners)
        dmax = max(dval(side, c.x, c.y) for c in corners)
        ys = [c.y for c in corners]
        log(f"{'LR'[side > 0]} {s['name']:18s} {s['kind']:9s} y {max(ys):6.1f}..{min(ys):6.1f}  d {dmin:5.2f}..{dmax:5.2f}"
            + ("   <-- IN THE WALKWAY" if dmin < D_FRONT - 0.01 else ""))
        placed.append(res)
        u = u_end + s.get("gap", 1.5) * (gscale if i < len(plan) - 1 else 1.0)
    return lane, placed, u


def mast(o, p, h=6.6, lamp_key="amber"):
    cyl(o.L("metal_dark"), p, p + Z * h, 0.065, segs=6)
    box(o.L("metal_dark"), p + Z * 0.05, (0.45, 0.45, 0.1))
    o.G(octa(o.glow, p + Z * (h + 0.16), 0.16, 0.2), lamp_key)
    o.block(p, 0.3)
    return p + Z * (h - 0.2)


def lane_dressing(o, lane, placed, rng, tail_u=None, tail_top=None):
    """Festoon masts on the units' front line (in the gaps), two strands mast to mast (orange/purple + warm), strands
    from each mast to its neighbors' roofs; barrel tables with people in the wide gaps; walkers in the walkway."""
    side = lane.s
    tops, stations = [], []
    us = [placed[0]["u0"] - 0.5]
    for r0, r1 in zip(placed, placed[1:]):
        us.append((r0["u1"] + r1["u0"]) / 2)
    us.append(placed[-1]["u1"] + 0.3 if tail_u is None else tail_u)
    for i, uu in enumerate(us):
        p = lane.point(uu, D_FRONT + 0.45)
        hgt = 4.6 if i == 0 else 6.6
        tops.append(mast(o, p, hgt, "amber" if i % 2 else "orange"))
        stations.append(uu)
        if i % 3 == 1 and i < len(us) - 1:                           # soft fill on the walkway, alternating tints
            o.lamp("SPOT", p + Z * 6.0 + lane.n_in * 1.2, PURPLE_L if (i // 2) % 2 else ORANGE_L, 650,
                   target=lane.point(uu, 11.5), size=0.8, deg=85)
    for a, b in zip(tops, tops[1:]):
        festoon(o, a, b, 0.65, spacing=0.8, r=0.09, key=("orange", "purple"))
        festoon(o, a - Z * 1.3, b - Z * 1.3, 0.45, spacing=0.9, r=0.08, key="bulb_warm")
    for i, p in enumerate(tops):                                      # mast -> neighboring units' roofs
        for k in (i - 1, i):
            if 0 <= k < len(placed):
                anc = min(placed[k]["anchors"], key=lambda q: (q - p).length)
                if (anc - p).length < 9.0:
                    festoon(o, p, anc + Z * 0.05, 0.25 + 0.03 * (anc - p).length, spacing=0.7, r=0.08,
                            key="bulb_warm")
    if tail_top is not None:
        festoon(o, tops[-1], tail_top, 0.6, spacing=0.8, r=0.09, key=("purple", "orange"))
    # barrel tables in the wide gaps (in the band, behind the masts), people around them
    for r0, r1 in zip(placed, placed[1:]):
        if not r0["s"].get("seats"):
            continue
        g0, g1 = r0["u1"], r1["u0"]
        for k, dd in enumerate((15.3, 16.9)):
            uu = (g0 + g1) / 2 + (0.35 if k else -0.35)
            p = lane.point(uu, dd)
            cyl(o.L("wood_dark"), p, p + Z * 1.0, 0.33, segs=8, r2=0.3)
            cyl(o.L("metal_dark"), p + Z * 0.2, p + Z * 0.26, 0.345, segs=8, cap=False)
            cyl(o.L("metal_dark"), p + Z * 0.74, p + Z * 0.8, 0.335, segs=8, cap=False)
            o.G(octa(o.glow, p + Z * 1.1, 0.06, 0.09), "fire")
            o.block(p, 0.38)
            for t in range(3):
                ang = rng.uniform(0, 2 * math.pi)
                q = p + Vector((math.cos(ang), math.sin(ang), 0.0)) * 0.72
                if dval(side, q.x, q.y) < D_BACK + 0.3:
                    o.person(q, p - q, rng.choice(("down", "one", "hips")))
        o.lamp("POINT", lane.point((g0 + g1) / 2, 16.1) + Z * 3.2, WARM, 120, size=0.5)
    # walkers and small groups in the walkway
    u = placed[0]["u0"] + 1.0
    end = us[-1]
    walk = lane.t
    while u < end - 1.0:
        p = lane.point(u, rng.uniform(D_PEOPLE + 0.3, 12.6))
        r = rng.random()
        if r < 0.25:
            ang0 = rng.uniform(0.0, 2.0 * math.pi)
            for t in range(3):
                q = p + Vector((math.cos(ang0 + t * 2.1), math.sin(ang0 + t * 2.1), 0.0)) * 0.55
                o.person(q, p - q, rng.choice(("down", "one", "hips")))
        else:
            v = walk * (1 if r < 0.62 else -1)
            o.person(p, v, "down")
            if rng.random() < 0.45:
                o.person(p + Vector((-v.y, v.x, 0.0)) * 0.6, v, rng.choice(("down", "one")))
        u += rng.uniform(4.0, 6.5)


def build(rng):
    o = Out()
    lanes = []
    for side, plan in ((-1, LEFT), (1, RIGHT)):
        lane, placed, u_next = flank(o, side, plan, rng)
        lanes.append((lane, placed, u_next))
    lane_l, placed_l, u_l = lanes[0]
    u_end_row, tower_head = o.run("outhouses+WC", u_outhouses, lane_l, u_l, rng)
    if u_end_row > lane_l.length() + 0.05:
        log(f"WARNING left lane overruns y {Y_FAR}: ends at station {u_end_row:.1f} > {lane_l.length():.1f}")
    o.run("masts+festoons L", lane_dressing, lane_l, placed_l, rng, u_l + 0.1, tower_head)
    lane_r, placed_r, u_r = lanes[1]
    if placed_r[-1]["u1"] > lane_r.length() + 0.05:
        log(f"WARNING right lane overruns: {placed_r[-1]['u1']:.1f} > {lane_r.length():.1f}")
    o.run("masts+festoons R", lane_dressing, lane_r, placed_r, rng)
    o.run("signs", sign_layout)
    if PROXY:
        for x, y, yaw, pose in o.people:
            p = Vector((x, y, GROUND_Z))
            box(o.L("metal_grey"), p + Z * 0.8, (0.45, 0.28, 1.6), yaw=yaw)
    log("tris: " + ", ".join(f"{k} {v}" for k, v in o.tally.items()) + f"; total {o.count()}")
    log(f"lights {len(o.lights)}, people {len(o.people)}")
    lit = [(bm, key) for key, bm in o.lit.items() if len(bm.faces)]
    return {"lit": lit, "glow": [o.glow], "beams": [], "halos": [o.halos] if len(o.halos.faces) else [],
            "lights": o.lights, "exclude": [], "people": o.people}
