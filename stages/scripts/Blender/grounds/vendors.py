"""Festival grounds: the FOOD & DRINK vendor village along both flanks of the crowd (Dino Stage, Blender 4.5).

Each flank is the band |x| = crowd_half(y)+6 .. crowd_half(y)+18 for y = -13 .. -75: a 69 m long, 10.7 m wide strip that
fans out with the crowd. A packer places each flank's units from the stage end back: backs near the band's outer edge,
fronts turned to the crowd and the DJ (the farther back, the more they turn toward the stage), each with a queue apron in
front; gaps shrink if a flank overruns. A trampled-dirt floor (a little lighter than the field) carries the warm light
pools. Festoon masts line the inner edge: a warm strand and a party-colored strand run mast to mast along the lane, more
festoons run mast-to-unit and unit-to-unit, so a canopy of bulbs hangs over the queues. Signs face the DJ and are
staggered in height (s["elev"]) where they would overlap from the booth. The two flanks use different unit lists (no
mirrored copies); the left one ends at the portable-toilet bank, the right one at a light tower.

Preview aid: VENDORS_PROXY=1 also draws the returned people as grey blocks (the harness does not draw people).
"""
import math
import os

from kit import *

NAME = "vendors"
BAKE_SIZE = 4096

Y_NEAR, Y_FAR = -13.0, -75.0
D_BACK = 11.6                      # units' backs this deep into the 12 m band (band depth is measured along x)
Z = Vector((0.0, 0.0, 1.0))
WARM = (1.0, 0.64, 0.36)           # light colors
WARM_WHITE = (1.0, 0.82, 0.62)
COOL = (0.78, 0.86, 1.0)
LIGHT_SCALE = 0.6                  # powers below were set by eye at exposure 1; the bake ships lit albedo x1.8
PROXY = os.environ.get("VENDORS_PROXY") == "1"


def band_d(side, x, y):
    """Depth of (x, y) into this flank's band: 0 at the inner (crowd) edge, 12 at the outer edge."""
    return side * x - crowd_half(y) - 6.0


def log(msg):
    print("[VENDORS] " + msg, flush=True)


# ------------------------------------------------------------------ output collector + unit frame
class Out:
    def __init__(self):
        self.lit, self.glow, self.halos = {}, bmesh.new(), bmesh.new()
        self.lights, self.people, self.blocks = [], [], []

    def L(self, key):
        if key not in self.lit:
            self.lit[key] = bmesh.new()
        return self.lit[key]

    def G(self, faces, key):
        glow_faces(self.glow, faces, key)
        return faces

    def lamp(self, kind, pos, color, power, target=None, size=0.3, deg=45.0):
        self.lights.append(light(f"Vend{len(self.lights):02d}", kind, pos, color, power * LIGHT_SCALE, target=target,
                                 size=size, spot_deg=deg))

    def person(self, p, face, pose="down"):
        self.people.append((round(p.x, 2), round(p.y, 2), round(math.atan2(-face[0], face[1]), 3), pose))

    def block(self, p, r):
        """Mark a prop footprint so free-standing people keep clear of it."""
        self.blocks.append((Vector((p.x, p.y, 0.0)), r))

    def clear(self, p, r=0.45):
        return all((Vector((p.x, p.y, 0.0)) - q).length > r + rq for q, rq in self.blocks)


class Frame:
    """A unit's local frame: a = the viewer's right when facing the unit's front, b = out of the front (toward the
    crowd), z = up from the field. Origin = front-center on the field floor."""

    def __init__(self, x, y, ang):
        self.o = Vector((x, y, GROUND_Z))
        self.F = Vector((math.cos(ang), math.sin(ang), 0.0))
        self.R = Vector((-self.F.y, self.F.x, 0.0))
        self.yaw = math.atan2(self.R.y, self.R.x)

    def p(self, a, b, z=0.0):
        return self.o + self.R * a + self.F * b + Z * z

    def box(self, bm, a0, a1, b0, b1, z0, z1):
        return box(bm, self.p((a0 + a1) / 2, (b0 + b1) / 2, (z0 + z1) / 2), (abs(a1 - a0), abs(b1 - b0), abs(z1 - z0)),
                   yaw=self.yaw)

    def cyl(self, bm, a, b, z0, z1, r, segs=6):
        return cyl(bm, self.p(a, b, z0), self.p(a, b, z1), r, segs=segs)

    def quad_f(self, bm, a0, a1, b, z0, z1):
        """Upright quad in the plane b, facing +F."""
        return poly(bm, [self.p(a0, b, z0), self.p(a1, b, z0), self.p(a1, b, z1), self.p(a0, b, z1)], self.F)


# ------------------------------------------------------------------ geometry helpers (the kit lacks oriented boxes,
# polygons/prisms and cheap bulbs; they live here)
def obox(bm, c, ax, ay, size):
    """Box centered at c with its local x along ax and y along ay (orthogonalized), sizes (sx, sy, sz)."""
    ax = Vector(ax).normalized()
    ay = Vector(ay)
    ay = (ay - ax * ay.dot(ax)).normalized()
    az = ax.cross(ay)
    c = Vector(c)
    m = Matrix(((ax.x, ay.x, az.x, c.x), (ax.y, ay.y, az.y, c.y), (ax.z, ay.z, az.z, c.z), (0.0, 0.0, 0.0, 1.0)))
    res = bmesh.ops.create_cube(bm, size=1.0, matrix=m @ Matrix.Diagonal(Vector(size).to_4d()))
    return list({f for v in res["verts"] for f in v.link_faces})     # exact faces, as kit._op_faces


def poly(bm, pts, hint):
    """One planar face through pts, its normal turned toward `hint` (outward) so bakes land on the visible side."""
    f = bm.faces.new([bm.verts.new(Vector(p)) for p in pts])
    f.normal_update()
    if f.normal.dot(Vector(hint)) < 0:
        f.normal_flip()
    return [f]


def slab(bm, pts, thick):
    """Planar polygon pts extruded by the vector `thick`: a closed thin prism (flags, plates, pennants)."""
    P = [Vector(p) for p in pts]
    Q = [p + thick for p in P]
    c = sum(P, Vector()) / len(P)
    faces = poly(bm, P, -thick) + poly(bm, Q, thick)
    for i in range(len(P)):
        j = (i + 1) % len(P)
        faces += poly(bm, [P[i], P[j], Q[j], Q[i]], (P[i] + P[j]) / 2 - c)
    return faces


def octa(bm, c, r, rz=None):
    """Octahedron bulb: 8 tris (half the kit's sphere bulb), reads as a dot at any angle."""
    c, rz = Vector(c), r if rz is None else rz
    v = [bm.verts.new(c + d) for d in (Vector((r, 0, 0)), Vector((-r, 0, 0)), Vector((0, r, 0)), Vector((0, -r, 0)),
                                       Vector((0, 0, rz)), Vector((0, 0, -rz)))]
    faces = []
    for i, j in ((0, 2), (2, 1), (1, 3), (3, 0)):
        faces.append(bm.faces.new((v[i], v[j], v[4])))
        faces.append(bm.faces.new((v[j], v[i], v[5])))
    return faces


PARTY = ("red", "yellow", "green", "sky", "pink", "orange")


def festoon(o, a, b, sag, spacing=0.8, r=0.085, key="bulb_warm"):
    """Festoon between a and b: thin dark wire (lit) + octahedron bulbs (glow). key: one palette key, or a tuple of
    keys cycled bulb by bulb (party lights)."""
    a, b = Vector(a), Vector(b)
    pts = catenary(a, b, sag, n=max(4, int((b - a).length / 1.5)))
    wire = o.L("metal_dark")
    for p, q in zip(pts, pts[1:]):
        cyl(wire, p, q, 0.012, segs=3, cap=False)
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


def face_dj(p, f, k=0.6):
    """Blend a facing direction f toward the DJ at the origin (k=1: straight at the DJ)."""
    to = Vector((-p.x, -p.y, 0.0)).normalized()
    v = Vector((f.x, f.y, 0.0)) * (1.0 - k) + to * k
    return v.normalized()


def sign_size(lines, px):
    lines = [lines] if isinstance(lines, str) else lines
    tw = max(text_width(t, px) for t in lines)
    th = len(lines) * 7 * px + (len(lines) - 1) * 2.5 * px
    return tw + 2.8 * px, th + 2.8 * px


def sign(o, lines, center, facing, px, key, board="canvas_black", border=None, double=False, depth=0.14):
    """Dot-matrix LED sign (centered lines) on a dark board centered at `center`, facing `facing` (horizontal).
    double: lettering on the back too (reads correctly from behind). Returns (board w, board h, R, F)."""
    lines = [lines] if isinstance(lines, str) else lines
    F = Vector((facing[0], facing[1], 0.0)).normalized()
    R = Vector((-F.y, F.x, 0.0))
    c = Vector(center)
    bw, bh = sign_size(lines, px)
    yaw = math.atan2(R.y, R.x)
    box(o.L(board), c, (bw, depth, bh), yaw=yaw)
    th = bh - 2.8 * px
    for sd in ((1, -1) if double else (1,)):
        Fs, Rs = F * sd, R * sd
        for i, t in enumerate(lines):
            w = text_width(t, px)
            zb = th / 2 - (i + 1) * 7 * px - i * 2.5 * px
            led_text(o.glow, t, c - Rs * (w / 2) + Z * zb + Fs * (depth / 2 + 0.02), Rs, Z, pixel=px, gap=px * 0.2,
                     key=key)
        if border:
            t_ = px * 0.4
            fz = Fs * (depth / 2 + 0.012)
            fs = []
            for dz in (bh / 2 - t_ / 2, -bh / 2 + t_ / 2):
                fs += box(o.glow, c + fz + Z * dz, (bw, 0.02, t_), yaw=yaw)
            for da in (bw / 2 - t_ / 2, -bw / 2 + t_ / 2):
                fs += box(o.glow, c + fz + R * da, (t_, 0.02, bh - 2 * t_), yaw=yaw)
            o.G(fs, border)
    return bw, bh, R, F


def posts(o, c, bh, R, z_base, half, r=0.045, key="metal_dark"):
    """Two posts from world height z_base up to the bottom edge of a sign board centered at c."""
    for s in (-1, 1):
        q = c + R * (s * half)
        cyl(o.L(key), Vector((q.x, q.y, z_base)), Vector((q.x, q.y, c.z - bh / 2 + 0.03)), r, segs=5)


def pool(o, fr, a, b_aim=0.9, power=1400.0, deg=100.0, color=WARM, h=5.2, back=2.6):
    """Warm light pool on the apron: a spot hung high in front of the unit, aimed back at the counter's foot."""
    o.lamp("SPOT", fr.p(a, b_aim + back, h), color, power, target=fr.p(a, b_aim, 0.0), size=0.5, deg=deg)


def queue(o, fr, a, n, rng, b0=0.8, step=0.72):
    for i in range(n):
        p = fr.p(a + rng.uniform(-0.18, 0.18) + 0.22 * math.sin(i * 1.9), b0 + i * step + rng.uniform(-0.08, 0.08))
        f = -fr.F + fr.R * rng.uniform(-0.3, 0.3)
        o.person(p, f, rng.choice(("down", "down", "hips", "one")))


def valance(o, fr, a0, a1, b, eave, key, teeth=True):
    bm = o.L(key)
    fr.box(bm, a0, a1, b, b + 0.04, eave - 0.3, eave + 0.02)
    if teeth:
        n = max(2, int((a1 - a0) / 0.36))
        w = (a1 - a0) / n
        for i in range(n):
            x0 = a0 + i * w
            slab(bm, [fr.p(x0, b + 0.01, eave - 0.3), fr.p(x0 + w, b + 0.01, eave - 0.3),
                      fr.p(x0 + w / 2, b + 0.01, eave - 0.48)], fr.F * 0.02)


def pagoda_roof(bm, fr, h, b_c, eave, peak, inset=0.5, knee=0.2):
    """Concave pyramid (pagoda tent): shallow skirt from the eave to a knee ring, then steep to the peak."""
    corners = [(-h, b_c - h), (h, b_c - h), (h, b_c + h), (-h, b_c + h)]
    zk = eave + knee * (peak - eave)
    E = [fr.p(a, b, eave) for a, b in corners]
    M = [fr.p(a * inset, b_c + (b - b_c) * inset, zk) for a, b in corners]
    T = fr.p(0.0, b_c, peak)
    below = fr.p(0.0, b_c, eave - 1.0)
    faces = []
    for i in range(4):
        j = (i + 1) % 4
        faces += poly(bm, [E[i], E[j], M[j], M[i]], (E[i] + M[j]) / 2 - below)
        faces += poly(bm, [M[i], M[j], T], (M[i] + M[j] + T) / 3 - below)
    return faces


def gable_roof(bm, fr, h, b0, b1, eave, ridge, over=0.12):
    """Ridge roof along a (marquee / frame tent) with gable triangles at both ends."""
    bmid = (b0 + b1) / 2
    FL, FR = fr.p(-h - over, b1 + over, eave), fr.p(h + over, b1 + over, eave)
    BL, BR = fr.p(-h - over, b0 - over, eave), fr.p(h + over, b0 - over, eave)
    RL, RR = fr.p(-h - over, bmid, ridge), fr.p(h + over, bmid, ridge)
    faces = poly(bm, [FL, FR, RR, RL], fr.F + Z) + poly(bm, [BL, BR, RR, RL], -fr.F + Z)
    for s in (-1, 1):
        faces += poly(bm, [fr.p(s * h, b0, eave), fr.p(s * h, b1, eave), fr.p(s * h, bmid, ridge)], fr.R * s)
    return faces


def lift_for(c, bh, elev):
    """Extra height that puts a board centered at c (height bh) at `elev` degrees above the DJ's eye line (kit.DJ_EYE)."""
    if elev is None:
        return 0.0
    r = (Vector((c.x, c.y, 0.0)) - Vector((DJ_EYE.x, DJ_EYE.y, 0.0))).length
    return max(0.0, DJ_EYE.z + r * math.tan(math.radians(elev)) - c.z)


def mount_sign(o, fr, s, base_c, z_base, half_max, k=0.55, post_from=None):
    """Sign of spec s (text/px/key/border) with its bottom edge 0.25 m above z_base (field-relative), centered over
    base_c (local a, b), on two posts (from z_base, or from post_from: 0 = a pylon standing on the field); turned toward
    the DJ by k. s["elev"] raises it to that many degrees above the DJ's eye line (staggers signs that overlap from the
    booth). Signs near the stage are lettered on the back too (the drone/stream view sees them from behind). Returns
    the board's top-center (world)."""
    bw, bh = sign_size(s["text"], s["px"])
    c = fr.p(base_c[0], base_c[1], z_base + 0.25 + bh / 2)
    c.z += lift_for(c, bh, s.get("elev"))
    f = face_dj(c, fr.F, k)
    bw, bh, Rs, Fs = sign(o, s["text"], c, f, s["px"], s["key"], border=s.get("border"),
                          double=s.get("double", c.y > -40.0))
    posts(o, c, bh, Rs, GROUND_Z + (z_base if post_from is None else post_from), min(bw / 2 - 0.25, half_max))
    return c + Z * (bh / 2)


# ------------------------------------------------------------------ furniture
def picnic(o, p, yaw):
    R = Vector((math.cos(yaw), math.sin(yaw), 0.0))
    F = Vector((-R.y, R.x, 0.0))
    W = o.L("wood")
    box(W, p + Z * 0.74, (1.9, 0.75, 0.05), yaw=yaw)
    for s in (-1, 1):
        box(W, p + F * (s * 0.66) + Z * 0.44, (1.9, 0.26, 0.04), yaw=yaw)
        box(o.L("wood_dark"), p + R * (s * 0.72) + Z * 0.36, (0.06, 1.5, 0.72), yaw=yaw)


def binn(o, p, key):
    cyl(o.L(key), p, p + Z * 0.95, 0.32, segs=8)
    cyl(o.L("canvas_black"), p + Z * 0.95, p + Z * 1.02, 0.35, segs=8)


def feather(o, p, face, h, w, key):
    """Feather flag: pole + a tall curved banner facing `face`."""
    f = Vector((face[0], face[1], 0.0)).normalized()
    R = Vector((-f.y, f.x, 0.0))
    cyl(o.L("metal_alu"), p, p + Z * (h + 0.1), 0.022, segs=4)
    pts = [p + Z * 0.55, p + R * (w * 0.5) + Z * 0.55, p + R * (w * 0.85) + Z * (h * 0.45), p + R * w + Z * (h * 0.75),
           p + R * (w * 0.8) + Z * (h * 0.93), p + R * (w * 0.35) + Z * (h + 0.04), p + Z * h]
    slab(o.L(key), pts, f * 0.015)


def high_table(o, p):
    cyl(o.L("metal_dark"), p, p + Z * 1.05, 0.035, segs=4)
    cyl(o.L("metal_dark"), p, p + Z * 0.03, 0.26, segs=8)
    cyl(o.L("wood_dark"), p + Z * 1.05, p + Z * 1.09, 0.36, segs=8)


def umbrella(o, p, r, key, z=2.3):
    cyl(o.L("metal_alu"), p, p + Z * (z + 0.45), 0.025, segs=4)
    cone(o.L(key), p + Z * z, p + Z * (z + 0.55), r, segs=8)


def bale(o, p, yaw):
    box(o.L("bone"), p + Z * 0.21, (1.0, 0.48, 0.42), yaw=yaw)


# ------------------------------------------------------------------ units
def truck_len(s):
    """Overall length: box body + cab and hood, or + drawbar for a cab-less concession trailer."""
    return s["Lb"] + (1.3 if s.get("trailer") else 2.45)


def u_truck(o, fr, rng, s):
    """Box food truck: cab + box body with a glowing serving hatch (kitchen, cooks, steel shelf, propped flap or a
    striped awning), menu board, livery stripe, roofline LED strip, roof sign. trailer=True: a cab-less concession
    trailer on one axle with a drawbar and jack stand."""
    W, Lb = 2.4, s["Lb"]
    Lt = truck_len(s)
    trailer = s.get("trailer", False)
    k = s.get("cab", 1)

    def A(t):
        return t * k

    ab0, ab1 = -Lt / 2, -Lt / 2 + Lb
    zf, zh0, zh1, zt = 0.95, 1.6, 2.7, s.get("zt", 3.35)
    hw = min(3.0, Lb - 1.8)
    h0, h1 = ab0 + 0.4, ab0 + 0.4 + hw
    hc = A((h0 + h1) / 2)
    body = o.L(s["body"])
    fr.box(body, A(ab0), A(ab1), -W, -0.9, zf, zt)                    # shell around the hatch cavity
    fr.box(body, A(ab0), A(ab1), -0.9, 0.0, zf, zh0)
    fr.box(body, A(ab0), A(ab1), -0.9, 0.0, zh1, zt)
    fr.box(body, A(ab0), A(h0), -0.9, 0.0, zh0, zh1)
    fr.box(body, A(h1), A(ab1), -0.9, 0.0, zh0, zh1)
    fr.box(o.L(s["accent"]), A(ab0), A(ab1), 0.0, 0.03, zf + 0.1, zf + 0.42)
    o.G(fr.quad_f(o.glow, A(h0), A(h1), -0.88, zh0, zh1), s.get("inside", "bulb_warm"))
    fr.box(o.L("metal_alu"), A(h0), A(h1), -0.9, 0.42, zh0 - 0.05, zh0 + 0.02)
    for i in range(s.get("cooks", 2)):
        a = h0 + hw * (0.28 + 0.44 * i) + rng.uniform(-0.15, 0.15)
        fr.box(o.L("canvas_black"), A(a - 0.2), A(a + 0.2), -0.72, -0.48, zh0 - 0.05, zh0 + 0.58)
        sphere(o.L("canvas_black"), fr.p(A(a), -0.6, zh0 + 0.74), 0.11, segs=6, rings=4)
    tk = s["trim"]
    fs = fr.box(o.glow, A(h0 - 0.07), A(h1 + 0.07), -0.02, 0.035, zh1, zh1 + 0.07)
    fs += fr.box(o.glow, A(h0 - 0.07), A(h0), -0.02, 0.035, zh0, zh1)
    fs += fr.box(o.glow, A(h1), A(h1 + 0.07), -0.02, 0.035, zh0, zh1)
    fs += fr.box(o.glow, A(ab0), A(ab1), -0.02, 0.035, zt - 0.08, zt - 0.02)
    o.G(fs, tk)
    m0, m1 = h1 + 0.3, ab1 - 0.25                                      # menu board beside the hatch
    if m1 - m0 > 0.55:
        fr.box(o.L("canvas_black"), A(m0), A(m1), 0.0, 0.04, zh0 - 0.1, zh1 + 0.05)
        o.G(fr.quad_f(o.glow, A(m0 + 0.08), A(m1 - 0.08), 0.05, zh1 - 0.22, zh1 - 0.08), tk)
        fs = []
        for i in range(4):
            z = zh1 - 0.42 - i * 0.2
            fs += fr.quad_f(o.glow, A(m0 + 0.1), A(m0 + 0.1 + (m1 - m0 - 0.2) * rng.uniform(0.55, 0.9)), 0.05, z,
                            z + 0.08)
        o.G(fs, "white_dim")
    if s.get("awning"):                                                 # striped fabric awning on two poles
        c1, c2 = s["awning"]
        a0_, a1_ = h0 - 0.45, h1 + 0.45
        top, front = fr.p(0, 0.02, zt - 0.2), fr.p(0, 1.9, 2.45)
        d = (front - top).normalized()
        n = 8
        for i in range(n):
            ac = a0_ + (a1_ - a0_) * (i + 0.5) / n
            c = (fr.p(A(ac), 0.02, zt - 0.2) + fr.p(A(ac), 1.9, 2.45)) / 2
            obox(o.L(c1 if i % 2 == 0 else c2), c, fr.R, d, ((a1_ - a0_) / n + 0.005, (front - top).length, 0.04))
        fr.box(o.L(c1), A(a0_), A(a1_), 1.88, 1.92, 2.17, 2.45)
        for a in (a0_ + 0.05, a1_ - 0.05):
            fr.cyl(o.L("metal_alu"), A(a), 1.9, 0.0, 2.45, 0.03, segs=4)
    else:                                                               # the hatch door propped up as a flap
        el = math.radians(rng.uniform(16, 28))
        d = fr.F * math.cos(el) + Z * math.sin(el)
        flen = zh1 - zh0 + 0.15
        hinge = fr.p(hc, 0.02, zh1 + 0.04)
        obox(o.L(s.get("flap", s["body"])), hinge + d * (flen / 2) + Z * 0.03, fr.R, d, (hw + 0.2, flen, 0.05))
        for a in (h0 + 0.05, h1 - 0.05):
            cyl(o.L("metal_alu"), fr.p(A(a), 0.03, zh0 + 0.1),
                fr.p(A(a), 0.02 + flen * math.cos(el), zh1 + 0.04 + flen * math.sin(el)), 0.015, segs=3, cap=False)
    if trailer:                                                         # drawbar, jack stand, single axle
        fr.box(o.L("metal_dark"), A(ab0 + 0.4), A(ab1 - 0.4), -W + 0.4, -0.4, 0.55, zf)
        fr.box(o.L("metal_dark"), A(ab1), A(ab1 + 1.2), -W / 2 - 0.06, -W / 2 + 0.06, 0.5, 0.62)
        fr.cyl(o.L("metal_dark"), A(ab1 + 1.05), -W / 2, 0.0, 0.55, 0.04, segs=4)
        axles = [(ab0 + ab1) / 2]
    else:
        cab = o.L(s.get("cab_key", s["body"]))                          # cab, hood, glass, bumper
        fr.box(cab, A(ab1 + 0.03), A(ab1 + 1.9), -W + 0.06, -0.06, 0.6, 2.75)
        fr.box(cab, A(ab1 + 1.9), A(ab1 + 2.4), -W + 0.12, -0.12, 0.6, 1.55)
        glass = o.L("glass_dark")
        fr.box(glass, A(ab1 + 0.95), A(ab1 + 1.8), -0.09, -0.03, 1.7, 2.5)
        fr.box(glass, A(ab1 + 0.95), A(ab1 + 1.8), -W + 0.03, -W + 0.09, 1.7, 2.5)
        fr.box(glass, A(ab1 + 1.87), A(ab1 + 1.93), -W + 0.25, -0.25, 1.65, 2.55)
        fr.box(o.L("metal_dark"), A(ab1 + 2.38), A(ab1 + 2.47), -W + 0.05, -0.05, 0.4, 0.85)
        fr.box(o.L("metal_dark"), A(ab0 + 0.25), A(ab1 + 2.3), -W + 0.4, -0.4, 0.3, zf)
        axles = [ab0 + 1.0, ab1 + 1.55] + ([ab0 + 2.05] if Lb > 4.7 else [])
    for aw in axles:
        for bw in (-0.2, -W + 0.2):
            cyl(o.L("rubber"), fr.p(A(aw), bw - 0.14, 0.45), fr.p(A(aw), bw + 0.14, 0.45), 0.45, segs=10)
        cyl(o.L("metal_alu"), fr.p(A(aw), -0.06, 0.45), fr.p(A(aw), -0.035, 0.45), 0.22, segs=6)
    ex = s.get("extra")
    if ex == "oven":                                                    # wood-fired oven: chimney + fire in the hatch
        fr.cyl(o.L("metal_dark"), A(ab0 + 0.6), -W + 0.6, zt, zt + 1.3, 0.12, segs=6)
        cone(o.L("metal_dark"), fr.p(A(ab0 + 0.6), -W + 0.6, zt + 1.3), fr.p(A(ab0 + 0.6), -W + 0.6, zt + 1.55), 0.22,
             segs=6)
        o.G(fr.quad_f(o.glow, A(h1 - 0.95), A(h1 - 0.3), -0.85, zh0 + 0.04, zh0 + 0.42), "fire")
    elif ex == "plates":                                                # stegosaurus plates along the roof
        n = 7
        for i in range(n):
            t = (i + 0.5) / n
            a = ab0 + 0.3 + t * (Lb - 0.6)
            ph = 0.45 + 0.6 * math.sin(math.pi * t)
            pw = 0.22 + 0.2 * math.sin(math.pi * t)
            b = -W / 2 + (0.16 if i % 2 else -0.16)
            o.G(slab(o.glow, [fr.p(A(a - pw), b, zt), fr.p(A(a + pw), b, zt), fr.p(A(a + pw * 0.5), b, zt + ph * 0.72),
                              fr.p(A(a), b, zt + ph), fr.p(A(a - pw * 0.5), b, zt + ph * 0.72)], fr.F * 0.06),
                "green_dim")
    elif ex == "cup":                                                   # giant coffee cup on the roof
        c = fr.p(A(ab0 + 0.75), -W / 2, zt)
        cyl(o.L("plastic_white"), c, c + Z * 0.9, 0.42, segs=10, r2=0.52)
        cyl(o.L("wood"), c + Z * 0.3, c + Z * 0.62, 0.47, segs=10, r2=0.51)
        cyl(o.L("canvas_black"), c + Z * 0.9, c + Z * 1.0, 0.56, segs=10)
    if s.get("pylon"):                                                  # free-standing sign at the apron's edge
        pa, pb = s["pylon"]
        top = mount_sign(o, fr, s, (A(pa), pb), 2.9, 1.6, k=0.8, post_from=0.0)
        o.block(fr.p(A(pa), pb), 0.6)
    else:
        top = mount_sign(o, fr, s, (A((ab0 + ab1) / 2 + s.get("sign_shift", 0.0)), s.get("sign_b", -W / 2)),
                         zt + s.get("lift", 0.1), Lb / 2 - 0.3)
    o.lamp("POINT", fr.p(hc, 0.4, zh1 - 0.1), WARM_WHITE, s.get("hatch_w", 45), size=0.3)
    pool(o, fr, hc, b_aim=1.3, power=s.get("pool", 2100))
    queue(o, fr, hc, s.get("q", 4), rng, b0=0.85)
    return {"anchors": [fr.p(A(ab0 + 0.05), 0.0, zt), fr.p(A(ab1 - 0.05), 0.0, zt)], "top": top,
            "flags": [(A(ab0) - 0.5 * k, 0.7), (A(ab0 + Lt) + 0.5 * k, 0.9)]}


def u_pagoda(o, fr, rng, s):
    """Square peaked (pagoda) tent: open front, counter with a colored skirt, back table and menu light box, valance
    with teeth, bulbs under the front eave, finial pennant; sign on a header frame or on the peak."""
    S = s["S"]
    h = S / 2
    eave = s.get("eave", 2.4)
    peak = s.get("peak", eave + 0.5 * S + 0.35)
    canvas = s.get("canvas", "canvas_white")
    val = s["valance"]
    alu = o.L("metal_alu")
    for a in (-h, h):
        for b in (0.0, -S):
            fr.cyl(alu, a, b, 0.0, eave, 0.04, segs=6)
    fr.box(o.L(s.get("walls", canvas)), -h, h, -S, -S + 0.05, 0.0, eave)
    for a in (-h, h):
        fr.box(o.L(s.get("walls", canvas)), a - 0.025, a + 0.025, -S, -0.55, 0.0, eave)
    if s.get("roof_glow"):                                              # canvas lit from inside: glows like a lantern
        o.G(pagoda_roof(o.glow, fr, h + 0.07, -h, eave, peak), s["roof_glow"])
    else:
        pagoda_roof(o.L(canvas), fr, h + 0.07, -h, eave, peak)
    on_peak = s.get("mount", "header") == "peak"
    if not on_peak:                                                     # finial + pennant
        fr.cyl(alu, 0.0, -h, peak - 0.1, peak + 0.75, 0.025, segs=4)
        slab(o.L(val), [fr.p(0.0, -h, peak + 0.75), fr.p(0.0, -h, peak + 0.42), fr.p(0.7, -h, peak + 0.6)],
             fr.F * 0.02)
    valance(o, fr, -h - 0.08, h + 0.08, 0.08, eave, val)
    fr.box(o.L(s.get("skirt", val)), -h + 0.15, h - 0.15, -0.75, -0.15, 0.0, 0.95)
    fr.box(o.L("wood"), -h + 0.1, h - 0.1, -0.82, -0.08, 0.95, 1.0)
    fr.box(o.L("wood_dark"), -h + 0.25, h - 0.25, -S + 0.06, -S + 0.62, 0.0, 0.88)
    o.G(fr.quad_f(o.glow, -h * 0.62, h * 0.62, -S + 0.07, 1.3, 2.05), s.get("menu", "white_dim"))
    festoon(o, fr.p(-h, 0.12, eave - 0.32), fr.p(h, 0.12, eave - 0.32), 0.16, spacing=0.4, r=0.055)
    ex = s.get("extra")
    if ex == "shirts":                                                  # merch wall: shirts hung on the back wall
        cols = ("canvas_red", "canvas_white", "canvas_blue", "canvas_yellow", "canvas_green", "canvas_white")
        n = int(S / 0.75)
        for r_ in range(2):
            for i in range(n):
                a = -h + 0.4 + i * (S - 0.8) / max(1, n - 1)
                fr.box(o.L(cols[(i + 2 * r_) % len(cols)]), a - 0.26, a + 0.26, -S + 0.06, -S + 0.1,
                       1.05 + r_ * 0.62, 1.55 + r_ * 0.62)
    if ex == "cone":                                                    # giant ice-cream cone (on the peak or a post)
        c = fr.p(0.0, -h, peak + 0.05)
        if on_peak:
            c = fr.p(h + 0.5, 0.35, 2.7)
            fr.cyl(alu, h + 0.5, 0.35, 0.0, 2.75, 0.04, segs=5)
        cone(o.L("wood"), c + Z * 0.95, c, 0.36, segs=8)
        sphere(o.L("plastic_white"), c + Z * 1.2, 0.42, segs=8, rings=5)
    if on_peak:
        top = mount_sign(o, fr, s, (0.0, -h), peak + 0.15, 0.4)
    else:
        top = mount_sign(o, fr, s, (0.0, 0.1), eave - 0.05, h)
    o.lamp("POINT", fr.p(0.0, -h * 0.9, eave - 0.4), WARM_WHITE, s.get("inner", 90), size=0.4)
    pool(o, fr, 0.0, b_aim=1.2, power=s.get("pool", 1800))
    o.person(fr.p(rng.uniform(-h * 0.4, h * 0.4), -1.35), fr.F, "hips")
    queue(o, fr, rng.uniform(-0.4, 0.4), s.get("q", 3), rng, b0=0.75)
    flags = [(-h - 0.6, 0.8)] + ([] if (on_peak and ex == "cone") else [(h + 0.6, 0.8)])
    return {"anchors": [fr.p(0.0, -h, peak - 0.05)], "top": top, "flags": flags}


def u_gable(o, fr, rng, s):
    """Rectangular frame tent with a ridge roof (marquee): open front, counter, valance, bulbs; extras for BBQ
    (barrel smoker + glowing grill + hay bales), NOODLES (red lanterns), MERCH (shirt wall)."""
    Sa, Sb = s["Sa"], s["Sb"]
    h = Sa / 2
    eave = s.get("eave", 2.5)
    ridge = s.get("ridge", eave + 0.45 * Sb + 0.35)
    canvas = s.get("canvas", "canvas_white")
    walls = o.L(s.get("walls", canvas))
    val = s["valance"]
    alu = o.L("metal_alu")
    for a in [-h, h] + ([0.0] if Sa > 4.5 else []):
        for b in (0.0, -Sb):
            fr.cyl(alu, a, b, 0.0, eave, 0.045, segs=6)
    fr.box(walls, -h, h, -Sb, -Sb + 0.05, 0.0, eave)
    for a in (-h, h):
        fr.box(walls, a - 0.025, a + 0.025, -Sb, -0.5, 0.0, eave)
    if s.get("roof_glow"):
        o.G(gable_roof(o.glow, fr, h, -Sb, 0.0, eave, ridge), s["roof_glow"])
    else:
        gable_roof(o.L(canvas), fr, h, -Sb, 0.0, eave, ridge)
    valance(o, fr, -h - 0.12, h + 0.12, 0.12, eave, val)
    fr.box(o.L(s.get("skirt", "wood_dark")), -h + 0.15, h - 0.15, -0.75, -0.15, 0.0, 0.95)
    fr.box(o.L("wood"), -h + 0.1, h - 0.1, -0.82, -0.08, 0.95, 1.0)
    fr.box(o.L("wood_dark"), -h + 0.3, h - 0.3, -Sb + 0.06, -Sb + 0.62, 0.0, 0.88)
    festoon(o, fr.p(-h - 0.1, 0.16, eave - 0.32), fr.p(h + 0.1, 0.16, eave - 0.32), 0.2, spacing=0.42, r=0.055)
    ex = s.get("extra")
    if ex == "lanterns":
        n = int(Sa / 0.9)
        for i in range(n):
            a = -h + (i + 0.5) * Sa / n
            fr.cyl(o.L("metal_dark"), a, 0.16, eave - 0.75, eave - 0.3, 0.008, segs=3)
            o.G(sphere(o.glow, fr.p(a, 0.16, eave - 0.95), 0.2, segs=6, rings=4, scale=(1, 1, 1.15)),
                "red" if i % 3 else "orange")
        o.G(fr.quad_f(o.glow, -h * 0.7, h * 0.7, -Sb + 0.08, 1.3, 2.1), "warm_dim")
    elif ex == "shirts":
        cols = ("canvas_red", "canvas_white", "canvas_blue", "canvas_yellow", "canvas_green", "canvas_white")
        n = int(Sa / 0.8)
        for r_ in range(2):
            for i in range(n):
                a = -h + 0.45 + i * (Sa - 0.9) / max(1, n - 1)
                fr.box(o.L(cols[(i + 2 * r_) % len(cols)]), a - 0.28, a + 0.28, -Sb + 0.06, -Sb + 0.1,
                       1.15 + r_ * 0.75, 1.75 + r_ * 0.75)
    elif ex == "bbq":
        sa, sb = h + 0.05, 1.35                                         # barrel smoker on legs + firebox + stack
        sm = fr.p(sa, sb, 0.95)
        cyl(o.L("metal_dark"), sm - fr.R * 0.7, sm + fr.R * 0.7, 0.42, segs=10)
        fr.box(o.L("metal_dark"), sa + 0.7, sa + 1.15, sb - 0.3, sb + 0.3, 0.45, 1.15)
        fr.cyl(o.L("metal_dark"), sa - 0.55, sb, 1.3, 2.7, 0.08, segs=5)
        for da in (-0.55, 0.55):
            for db in (-0.25, 0.25):
                fr.cyl(o.L("metal_dark"), sa + da, sb + db, 0.0, 0.62, 0.03, segs=3)
        o.G(fr.quad_f(o.glow, sa + 0.73, sa + 1.12, sb + 0.31, 0.55, 0.85), "fire")
        fr.box(o.L("metal_dark"), -h + 0.4, h - 0.4, -1.6, -1.0, 0.0, 0.85)  # grill bench, embers on top
        g = poly(o.glow, [fr.p(-h + 0.5, -1.55, 0.86), fr.p(h - 0.5, -1.55, 0.86), fr.p(h - 0.5, -1.05, 0.86),
                          fr.p(-h + 0.5, -1.05, 0.86)], Z)
        o.G(g, "ember")
        o.lamp("POINT", fr.p(0.0, -1.3, 1.25), (1.0, 0.42, 0.12), 60, size=0.6)
        for i in range(3):
            bale(o, fr.p(-h - 0.4 + i * 1.3, 2.9 + 0.2 * (i % 2), 0.0), fr.yaw + rng.uniform(-0.3, 0.3))
    if s.get("mount", "header") == "ridge":
        top = mount_sign(o, fr, s, (0.0, -Sb / 2), ridge + 0.1, 0.6)
    else:
        top = mount_sign(o, fr, s, (0.0, 0.14), eave - 0.05, h)
    o.lamp("POINT", fr.p(0.0, -Sb * 0.55, eave - 0.4), WARM_WHITE, s.get("inner", 110), size=0.5)
    pool(o, fr, 0.0, b_aim=1.2, power=s.get("pool", 2000), deg=110)
    for i in range(s.get("staff", 1)):
        o.person(fr.p(-h * 0.5 + i * h, -1.3 if ex != "bbq" else -2.2), fr.F, "hips")
    queue(o, fr, rng.uniform(-0.6, 0.6), s.get("q", 4), rng, b0=0.75)
    return {"anchors": [fr.p(-h - 0.1, 0.12, eave), fr.p(h + 0.1, 0.12, eave)], "top": top,
            "flags": [(-h - 0.7, 0.8), (h + 0.7, 0.8)] if ex != "bbq" else [(-h - 0.7, 0.8)]}


def u_bar(o, fr, rng, s):
    """Long bar under a two-peak stretch canopy: deck, counter with LED strips, backlit bottle shelves, bartenders,
    big double-sided sign on the masts, umbrellas + high tables at the ends."""
    L, D = s["L"], 3.3
    h = L / 2
    fr.box(o.L("wood"), -h - 0.7, h + 0.7, -D - 0.25, 1.2, 0.0, 0.16)
    fr.box(o.L("wood_dark"), -h, h, -0.75, -0.08, 0.16, 1.1)
    fr.box(o.L("wood"), -h - 0.06, h + 0.06, -0.82, 0.02, 1.1, 1.16)
    o.G(fr.box(o.glow, -h, h, -0.1, -0.05, 0.98, 1.04) + fr.box(o.glow, -h, h, -0.1, -0.05, 0.22, 0.26), s["led"])
    fr.box(o.L("canvas_black"), -h + 0.2, h - 0.2, -D, -D + 0.3, 0.16, 3.0)
    fr.box(o.L("metal_grey"), -h + 0.3, h - 0.3, -D + 0.3, -D + 0.95, 0.16, 1.0)
    o.G(fr.quad_f(o.glow, -h + 0.5, h - 0.5, -D + 0.32, 1.05, 2.6), s["backbar"])
    for zsh in (1.45, 1.98):
        fr.box(o.L("wood_dark"), -h + 0.5, h - 0.5, -D + 0.3, -D + 0.6, zsh - 0.04, zsh)
        a, fs = -h + 0.6, []
        while a < h - 0.75:
            bw_ = rng.uniform(0.08, 0.12)
            fs += fr.quad_f(o.glow, a, a + bw_, -D + 0.36, zsh, zsh + rng.uniform(0.22, 0.34))
            a += bw_ + rng.uniform(0.05, 0.28)
        o.G(fs, "black")
    # stretch canopy: height field over the deck, two masts, edges pulled down to poles
    a0, a1, b0, b1 = -h - 0.8, h + 0.8, -D - 0.3, 1.6
    na, nb, zm = 9, 5, s.get("mast_z", 5.3)
    masts = ((2, 2), (6, 2))

    def zc(i, j):
        if (i, j) in masts:
            return zm
        base = 3.3 - 0.3 * j / (nb - 1)
        bump = max((zm - base) * math.exp(-1.25 * (((i - mi) / 1.7) ** 2 + ((j - mj) / 1.25) ** 2)) for mi, mj in masts)
        if i in (0, na - 1) or j in (0, nb - 1):
            bump *= 0.2
        return base + bump

    P = [[fr.p(a0 + (a1 - a0) * i / (na - 1), b0 + (b1 - b0) * j / (nb - 1), zc(i, j)) for j in range(nb)]
         for i in range(na)]
    lo, hi = s["canopy"]
    fs_lo, fs_hi = [], []
    to_dj = Vector((-fr.o.x, -fr.o.y, 0.0)).normalized()
    for i in range(na - 1):
        for j in range(nb - 1):
            for tri in ((P[i][j], P[i + 1][j], P[i + 1][j + 1]), (P[i][j], P[i + 1][j + 1], P[i][j + 1])):
                f = poly(o.glow, tri, Z)
                (fs_hi if f[0].normal.dot(to_dj) > 0.12 else fs_lo).extend(f)
                fs_lo.extend(poly(o.glow, [q - Z * 0.02 for q in tri], -Z))   # underside: one-sided materials
    o.G(fs_lo, lo)
    o.G(fs_hi, hi)
    edge = []                                                           # LED rope along the canopy's front and ends
    for path in ([P[i][nb - 1] for i in range(na)], [P[0][j] for j in range(nb)], [P[na - 1][j] for j in range(nb)]):
        for p, q in zip(path, path[1:]):
            edge += cyl(o.glow, p, q, 0.035, segs=4, cap=False)
    o.G(edge, s["led"])
    dark = o.L("metal_dark")
    for i, j in ((0, 0), (4, 0), (8, 0), (0, 4), (4, 4), (8, 4)):
        q = P[i][j]
        cyl(dark, Vector((q.x, q.y, GROUND_Z)), q, 0.05, segs=5)
    for i, j in masts:
        q = P[i][j]
        cyl(dark, Vector((q.x, q.y, GROUND_Z)), q + Z * 3.3, 0.08, segs=6)
    festoon(o, P[0][4] - Z * 0.15 - fr.F * 0.1, P[8][4] - Z * 0.15 - fr.F * 0.1, 0.35, spacing=0.5, r=0.06)
    # big sign between the masts, double-sided for the drone view
    bw, bh = sign_size(s["text"], s["px"])
    mid = (P[2][2] + P[6][2]) / 2
    c = Vector((mid.x, mid.y, mid.z + 0.35 + bh / 2)) + fr.F * 0.2
    sign(o, s["text"], c, fr.F, s["px"], s["key"], border=s.get("border"), double=True)
    for e in (-1, 1):                                                   # high tables + umbrellas at the ends
        p = fr.p(e * (h - 0.4), 2.2)
        high_table(o, p)
        umbrella(o, p, 1.25, s["umbrella"])
        for t in range(2):
            ang = rng.uniform(0, 2 * math.pi)
            q = p + Vector((math.cos(ang), math.sin(ang), 0.0)) * 0.6
            o.person(q, p - q, rng.choice(("down", "one", "hips")))
    o.lamp("POINT", fr.p(0.0, -1.9, 2.7), (1.0, 0.6, 0.3), s.get("inner", 160), size=0.8)
    pool(o, fr, -h * 0.45, b_aim=1.0, power=s.get("pool", 1700), deg=105)
    pool(o, fr, h * 0.45, b_aim=1.0, power=s.get("pool", 1700), deg=105)
    for i in range(3):
        o.person(fr.p(-h * 0.6 + i * h * 0.6 + rng.uniform(-0.4, 0.4), -1.5), fr.F, "hips")
    for i in range(s.get("q", 8)):
        a = -h + 0.6 + (L - 1.2) * (i + rng.uniform(0.2, 0.8)) / s.get("q", 8)
        o.person(fr.p(a, 0.55 + rng.uniform(0, 0.25) + (0.7 if i % 3 == 1 else 0.0)), -fr.F, rng.choice(("down", "one")))
    return {"anchors": [P[0][4], P[8][4]], "top": c + Z * (bh / 2), "flags": []}


def u_container(o, fr, rng, s):
    """20 ft shipping-container bar: long side opened with its flap lifted into an awning, glowing back bar, counter
    LED, roof sign, high tables + umbrellas."""
    L, D, H, z0 = 6.06, 2.44, 2.59, 0.12
    h = L / 2
    col, dark = o.L(s["body"]), o.L("metal_dark")
    fr.box(col, -h, h, -D, -D + 0.08, z0, z0 + H)
    fr.box(col, -h, -h + 0.08, -D, 0.0, z0, z0 + H)
    fr.box(col, h - 0.08, h, -D, 0.0, z0, z0 + H)
    fr.box(col, -h, h, -D, 0.0, z0 + H - 0.1, z0 + H)
    fr.box(col, -h, h, -D, 0.0, 0.0, z0 + 0.12)
    zc = 1.15
    fr.box(col, -h, h, -0.12, 0.0, z0, zc)
    for a in (-h, h):                                                   # corner castings / frame
        for b in (-D, 0.0):
            fr.box(dark, a - 0.07, a + 0.07, b - 0.07, b + 0.07, 0.0, z0 + H)
    fr.box(dark, -h, h, -0.07, 0.07, z0 + H - 0.15, z0 + H)
    for i in range(1, 12):                                              # corrugation on the counter wall
        a = -h + i * L / 12
        fr.box(col, a - 0.06, a + 0.06, 0.0, 0.04, z0 + 0.1, zc - 0.1)
    fr.box(o.L("wood"), -h + 0.1, h - 0.1, -0.5, 0.35, zc, zc + 0.06)
    o.G(fr.box(o.glow, -h + 0.1, h - 0.1, 0.0, 0.04, zc - 0.09, zc - 0.03), s["led"])
    o.G(fr.quad_f(o.glow, -h + 0.2, h - 0.2, -D + 0.1, zc + 0.05, z0 + H - 0.15), s.get("inside", "bulb_warm"))
    for zsh in (1.6, 2.1):
        fr.box(o.L("wood_dark"), -h + 0.2, h - 0.2, -D + 0.08, -D + 0.35, zsh - 0.04, zsh)
        a, fs = -h + 0.3, []
        while a < h - 0.4:
            bw_ = rng.uniform(0.08, 0.11)
            fs += fr.quad_f(o.glow, a, a + bw_, -D + 0.14, zsh, zsh + rng.uniform(0.2, 0.32))
            a += bw_ + rng.uniform(0.05, 0.25)
        o.G(fs, "black")
    el = math.radians(8)
    d = fr.F * math.cos(el) + Z * math.sin(el)
    obox(col, fr.p(0.0, 0.0, z0 + H + 0.02) + d * 1.05, fr.R, d, (L, 2.1, 0.06))
    for a in (-h + 0.25, h - 0.25):
        cyl(o.L("metal_alu"), fr.p(a, 0.05, zc + 0.1), fr.p(a, 2.0, z0 + H + 0.3), 0.02, segs=3, cap=False)
    festoon(o, fr.p(-h, 2.05, z0 + H + 0.2), fr.p(h, 2.05, z0 + H + 0.2), 0.3, spacing=0.45, r=0.055)
    top = mount_sign(o, fr, s, (0.0, -D / 2), z0 + H, h - 0.3)
    for e in (-1, 1):
        p = fr.p(e * (h - 0.5), 3.0)
        high_table(o, p)
        umbrella(o, p, 1.2, s["umbrella"])
        for t in range(2):
            ang = rng.uniform(0, 2 * math.pi)
            q = p + Vector((math.cos(ang), math.sin(ang), 0.0)) * 0.6
            o.person(q, p - q, rng.choice(("down", "one", "hips")))
    o.lamp("POINT", fr.p(0.0, 1.0, 1.9), WARM_WHITE, s.get("inner", 60), size=0.6)
    pool(o, fr, 0.0, b_aim=1.3, power=s.get("pool", 2100), deg=110)
    for i in range(2):
        o.person(fr.p(-1.2 + 2.3 * i, -1.3), fr.F, "hips")
    queue(o, fr, -0.8, 3, rng, b0=0.8)
    queue(o, fr, 1.0, 3, rng, b0=0.85)
    return {"anchors": [fr.p(-h, 2.0, z0 + H + 0.2), fr.p(h, 2.0, z0 + H + 0.2)], "top": top, "flags": []}


def u_lockers(o, fr, rng, s):
    """Lockers + phone charging: a steel booth with a wall of colored locker doors (status LEDs), a charging counter
    with a status screen under a flat canopy, two stacked signs."""
    L, D, H = s["L"], 2.3, 2.55
    h = L / 2
    fr.box(o.L(s["body"]), -h, h, -D, 0.0, 0.0, H)
    fr.box(o.L("canvas_black"), -h - 0.15, h + 0.15, -D - 0.1, 1.4, H, H + 0.12)
    for a in (-h, h):
        fr.cyl(o.L("metal_dark"), a, 1.3, 0.0, H, 0.04, segs=5)
    lw = L - 1.9
    cols, rows = max(3, int(lw / 0.6)), 4
    dw, dz = lw / cols, (2.3 - 0.25) / rows
    doors = s["doors"]
    dots = {"green_dim": [], "red_dim": [], "lime": []}
    for c in range(cols):
        for r in range(rows):
            a, z = -h + 0.2 + c * dw, 0.25 + r * dz
            fr.box(o.L(doors[(c + r) % len(doors)]), a + 0.03, a + dw - 0.03, 0.0, 0.05, z + 0.03, z + dz - 0.03)
            k = rng.choice(("green_dim", "green_dim", "lime", "red_dim"))
            dots[k] += fr.quad_f(o.glow, a + dw - 0.17, a + dw - 0.08, 0.055, z + dz - 0.17, z + dz - 0.09)
    for k, fs in dots.items():
        o.G(fs, k)
    a0, a1 = -h + 0.2 + lw + 0.15, h - 0.12
    fr.box(o.L("metal_grey"), a0, a1, 0.0, 0.55, 0.0, 1.05)
    o.G(fr.box(o.glow, a0, a1, 0.55, 0.59, 0.95, 1.0), "cyan")
    o.G(fr.quad_f(o.glow, a0 + 0.1, a1 - 0.1, 0.01, 1.35, 2.2), "screen_teal")
    sl, sc = s["signs"]
    bw1, bh1 = sign_size(sc["text"], sc["px"])
    bw2, bh2 = sign_size(sl["text"], sl["px"])
    c1 = fr.p(0.0, -D / 2, H + 0.12 + 0.25 + bh1 / 2)
    c1.z += lift_for(c1 + Z * (bh2 / 2 + 0.06), bh1 + bh2, s.get("elev"))
    f = face_dj(c1, fr.F, 0.55)
    bw1, bh1, R1, _ = sign(o, sc["text"], c1, f, sc["px"], sc["key"], border=sc.get("border"))
    c2 = c1 + Z * (bh1 / 2 + 0.12 + bh2 / 2)
    bw2, bh2, R2, _ = sign(o, sl["text"], c2, f, sl["px"], sl["key"], border=sl.get("border"))
    for e in (-1, 1):
        q = c1 + R1 * (e * min(bw1 / 2 - 0.3, h - 0.3))
        cyl(o.L("metal_dark"), Vector((q.x, q.y, GROUND_Z + H + 0.12)), Vector((q.x, q.y, c2.z)), 0.045, segs=5)
    o.lamp("POINT", fr.p((a0 + a1) / 2, 0.9, H - 0.25), COOL, s.get("inner", 70), size=0.4)
    pool(o, fr, -h * 0.3, b_aim=1.2, power=s.get("pool", 1800), color=WARM_WHITE)
    queue(o, fr, (a0 + a1) / 2, 3, rng, b0=0.9)
    for i in range(2):
        o.person(fr.p(-h + 0.6 + i * 1.6 + rng.uniform(-0.2, 0.2), 0.7), -fr.F, "down")
    return {"anchors": [fr.p(-h - 0.1, 1.35, H + 0.1), fr.p(h + 0.1, 1.35, H + 0.1)], "top": c2 + Z * (bh2 / 2),
            "flags": [(-h - 0.6, 0.8)]}


def u_water(o, fr, rng, s):
    """Water refill point: blue canopy on poles over a steel tap trough (cyan LED), two big tanks, tall sign."""
    W_, D_ = 4.0, 2.4
    h = W_ / 2
    fr.box(o.L("canvas_blue"), -h - 0.1, h + 0.1, -D_, 0.25, 2.55, 2.65)
    valance(o, fr, -h - 0.1, h + 0.1, 0.25, 2.62, "canvas_white", teeth=False)
    for a in (-h, h):
        for b in (0.15, -D_ + 0.15):
            fr.cyl(o.L("metal_alu"), a, b, 0.0, 2.55, 0.04, segs=5)
    fr.box(o.L("metal_grey"), -h + 0.3, h - 0.3, -0.75, -0.2, 0.0, 0.9)
    o.G(fr.box(o.glow, -h + 0.3, h - 0.3, -0.2, -0.16, 0.8, 0.86), "cyan")
    for i in range(6):                                                  # tap posts
        a = -h + 0.6 + i * (W_ - 1.2) / 5
        fr.box(o.L("metal_alu"), a - 0.03, a + 0.03, -0.55, -0.45, 0.9, 1.35)
    for a in (-0.95, 0.95):                                             # tanks behind the canopy, pipe to the trough
        c = fr.p(a, -D_ - 0.85, 0.0)
        cyl(o.L("plastic_white"), c, c + Z * 2.3, 0.75, segs=12)
        cyl(o.L("canvas_blue"), c + Z * 2.3, c + Z * 2.4, 0.77, segs=12)
    fr.box(o.L("plastic_white"), -0.1, 0.1, -D_ - 0.2, -0.7, 0.3, 0.45)
    top = mount_sign(o, fr, s, (0.0, -D_ / 2), 2.65, h - 0.2)
    o.lamp("POINT", fr.p(0.0, -0.9, 2.3), COOL, s.get("inner", 70), size=0.5)
    pool(o, fr, 0.0, b_aim=1.2, power=s.get("pool", 1600), color=WARM_WHITE)
    queue(o, fr, -0.9, 2, rng, b0=0.5)
    queue(o, fr, 0.9, 2, rng, b0=0.5)
    return {"anchors": [fr.p(-h - 0.1, 0.25, 2.6), fr.p(h + 0.1, 0.25, 2.6)], "top": top, "flags": [(-h - 0.6, 0.6)]}


def light_tower(o, bz, aim, color, power, deg, mast=7.6):
    """Towable light tower: yellow generator trailer, mast, crossbar with four lamp heads (glow) aimed at `aim`, plus
    the spot that does the lighting. bz: base on the field."""
    to = aim - bz
    to.z = 0.0
    to.normalize()
    side_v = Vector((-to.y, to.x, 0.0))
    yaw_to = math.atan2(side_v.y, side_v.x)
    box(o.L("truck_yellow"), bz + Z * 0.72, (1.1, 1.8, 0.9), yaw=yaw_to)
    for e in (-1, 1):                                                   # trailer wheels
        cyl(o.L("rubber"), bz + side_v * (e * 0.56) + Z * 0.3, bz + side_v * (e * 0.76) + Z * 0.3, 0.3, segs=8)
    cyl(o.L("metal_grey"), bz + Z * 1.1, bz + Z * mast, 0.08, segs=6)
    head = bz + Z * mast
    box(o.L("metal_dark"), head, (2.0, 0.12, 0.12), yaw=yaw_to)
    lamps = []
    for e in (-0.75, -0.25, 0.25, 0.75):
        lamps += box(o.glow, head + side_v * e + Z * 0.22 + to * 0.06, (0.42, 0.06, 0.3), yaw=yaw_to)
    o.G(lamps, "white")
    halo(o.halos, head + Z * 0.22 + to * 0.3, 2.6, color="white")
    o.lamp("SPOT", head + Z * 0.1 + to * 0.3, color, power, target=aim, size=0.6, deg=deg)


def u_toilets(o, side, rng, n=8):
    """Portable-toilet bank across the far end of the flank, doors facing up the lane, under a light tower."""
    y_front = -73.6
    xc = side * (crowd_half(y_front - 0.6) + 6.0 + 6.0)
    fr = Frame(xc, y_front, math.pi / 2)
    w = 1.22
    a0 = -n * w / 2
    for i in range(n):
        a = a0 + (i + 0.5) * w
        fr.box(o.L("plastic_blue"), a - 0.57, a + 0.57, -1.2, 0.0, 0.0, 2.2)
        fr.box(o.L("plastic_white"), a - 0.61, a + 0.61, -1.24, 0.04, 2.2, 2.32)
        fr.box(o.L("canvas_blue"), a - 0.4, a + 0.4, 0.0, 0.03, 0.12, 2.05)
        o.G(fr.quad_f(o.glow, a + 0.12, a + 0.32, 0.035, 1.3, 1.38), "red_dim" if rng.random() < 0.4 else "green_dim")
    inner = a0 if side < 0 else -a0                                     # the row's end nearest the crowd
    out = -1 if side < 0 else 1                                         # a-direction from the row toward the crowd
    fr.box(o.L("plastic_white"), -inner - out * 0.2, -inner - out * 0.8, -0.9, -0.1, 0.0, 1.3)   # hand-wash, far end
    bz = fr.p(inner + out * 0.9, 3.2)
    light_tower(o, bz, fr.p(0.0, 0.4, 0.8), COOL, 2600, 62)
    f = face_dj(bz, fr.F, 0.7)                                          # WC sign on the mast, facing up the lane
    sign(o, "WC", bz + Z * 5.5 + f * 0.16, f, 0.22, "white", border="blue", double=True)
    o.block(bz, 1.3)
    for i in range(5):
        o.person(fr.p(-1.5 + i * 0.75 + rng.uniform(-0.15, 0.15), 1.4 + (i % 2) * 0.5), -fr.F,
                 rng.choice(("down", "hips")))
    return fr


# ------------------------------------------------------------------ the two flanks
FOOT_APRON = 3.0


def footprint(s):
    k, ap = s["kind"], s.get("apron", FOOT_APRON)
    if k == "truck":
        h = truck_len(s) / 2 + 0.15
        return -h, h, -2.5, ap
    if k == "pagoda":
        h = s["S"] / 2 + 0.2
        return -h, h, -s["S"] - 0.15, ap
    if k == "gable":
        h = s["Sa"] / 2 + 0.3
        if s.get("extra") == "bbq":                                     # smoker at the front corner, bales in front
            return -h - 0.6, h + 1.0, -s["Sb"] - 0.25, ap + 0.6
        return -h, h, -s["Sb"] - 0.25, ap
    if k == "bar":
        h = s["L"] / 2 + 0.95
        return -h, h, -3.75, ap
    if k == "container":
        return -3.75, 3.75, -2.6, ap + 0.6
    if k == "lockers":
        h = s["L"] / 2 + 0.3
        return -h - 0.5, h, -2.45, ap
    if k == "water":
        return -2.3, 2.3, -4.05, ap
    raise ValueError(k)


BUILD = {"truck": u_truck, "pagoda": u_pagoda, "gable": u_gable, "bar": u_bar, "container": u_container,
         "lockers": u_lockers, "water": u_water}

LEFT = [   # near (stage) -> far; px grows with distance from the DJ (35 m .. 95 m)
    dict(kind="bar", name="BAR", L=7.6, text="BAR", px=0.27, key="magenta", border="purple", led="magenta",
         backbar="amber", canopy=("purple_dim", "purple_dim"), umbrella="canvas_red", alpha=-4.0, apron=2.6, q=7,
         gap=1.5),
    dict(kind="truck", name="TACOS", Lb=4.5, body="truck_teal", accent="truck_yellow", trim="yellow",
         awning=("canvas_red", "canvas_yellow"), text="TACOS", px=0.17, key="yellow", inside="bulb_warm", cab=-1,
         elev=3.0, gap=1.3),
    dict(kind="gable", name="NOODLES", Sa=5.2, Sb=3.2, canvas="canvas_white", walls="canvas_red", valance="canvas_red",
         roof_glow="warm_dim", extra="lanterns", text="NOODLES", px=0.16, key="red", border="amber", gap=1.4),
    dict(kind="truck", name="PIZZA", Lb=4.6, body="truck_black", accent="truck_red", flap="truck_red", trim="orange",
         extra="oven", text="PIZZA", px=0.2, key="orange", inside="bulb_warm", cab=1, elev=2.8, gap=1.4),
    dict(kind="truck", name="CANDY", Lb=3.4, trailer=True, body="truck_white", accent="canvas_blue",
         flap="canvas_blue", trim="pink", text="CANDY", px=0.18, key="pink", border="sky", inside="bulb_white",
         cooks=1, cab=-1, q=3, apron=2.7, gap=1.3),
    dict(kind="pagoda", name="MERCH", S=4.0, canvas="canvas_white", walls="canvas_black", valance="canvas_black",
         roof_glow="white_dim", skirt="canvas_black", extra="shirts", menu="black", text="MERCH", px=0.21,
         key="white", border="purple", mount="header", inner=130, elev=2.0, gap=1.2),
    dict(kind="water", name="WATER", text="WATER", px=0.22, key="cyan", border="blue", double=True, gap=1.0),
]

RIGHT = [
    dict(kind="gable", name="BBQ", Sa=5.0, Sb=3.4, canvas="canvas_white", walls="canvas_black", valance="canvas_yellow",
         roof_glow="warm_dim", extra="bbq", text="BBQ", px=0.25, key="orange", border="red", mount="ridge", apron=2.7,
         gap=1.3),
    dict(kind="truck", name="DINO DOGS", Lb=4.8, body="truck_red", accent="truck_yellow", flap="truck_yellow",
         trim="yellow", extra="plates", text=["DINO", "DOGS"], px=0.17, key="lime", inside="bulb_white", cab=1,
         lift=0.25, sign_shift=0.4, gap=2.0),
    dict(kind="container", name="BEER", body="truck_teal", led="amber", inside="bulb_warm", text="BEER", px=0.22,
         key="amber", border="orange", umbrella="canvas_white", apron=2.7, gap=1.4),
    dict(kind="lockers", name="LOCKERS", L=5.6, body="metal_grey", doors=("plastic_orange", "plastic_white"),
         signs=(dict(text="LOCKERS", px=0.16, key="green"), dict(text="CHARGE", px=0.16, key="cyan", border="blue")),
         elev=3.4, apron=2.7, gap=1.4),
    dict(kind="truck", name="BURGERS", Lb=5.0, body="truck_yellow", accent="truck_black", flap="truck_black",
         trim="red", text="BURGERS", px=0.17, key="red", border="amber", inside="bulb_white", cab=-1, lift=0.4,
         apron=2.8, gap=1.3),
    dict(kind="pagoda", name="ICE CREAM", S=3.8, canvas="canvas_white", valance="canvas_red", skirt="plastic_white",
         roof_glow="warm_dim", extra="cone", text=["ICE", "CREAM"], px=0.19, key="pink", menu="white_dim",
         mount="peak", apron=2.7, gap=1.3),
    dict(kind="truck", name="COFFEE", Lb=3.6, body="truck_white", accent="wood", flap="wood_dark", trim="amber",
         cab_key="truck_white", extra="cup", text="COFFEE", px=0.2, key="amber", inside="bulb_warm", cab=1,
         pylon=(1.6, 2.3), apron=2.7, gap=1.2),
]


def pack(side, plan, jit, y_end, gscale):
    """Frames for the plan's units from the stage end back: each footprint (incl. its queue apron) starts at the cursor,
    turned toward the stage by alpha, then slid along x so its back sits D_BACK into the band. -> [(fr, ylo, yhi, dmin)]"""
    y, out = Y_NEAR - 0.4, []
    for s, j in zip(plan, jit):
        t = min(1.0, max(0.0, (-y - 13.0) / 62.0))
        alpha = math.radians(s.get("alpha", 4.0 + 10.0 * t) + j)
        ang = math.atan2(math.sin(alpha), -side * math.cos(alpha))
        a_lo, a_hi, b_lo, b_hi = footprint(s)
        f0 = Frame(0.0, 0.0, ang)
        cs = [f0.p(a, b) for a in (a_lo, a_hi) for b in (b_lo, b_hi)]
        y0 = y - max(c.y for c in cs)
        m = max(side * c.x + 0.5 * (y0 + c.y) - 20.0 for c in cs)
        fr = Frame(side * (D_BACK - m), y0, ang)
        wc = [fr.p(a, b) for a in (a_lo, a_hi) for b in (b_lo, b_hi)]
        out.append((fr, min(c.y for c in wc), max(c.y for c in wc), min(band_d(side, c.x, c.y) for c in wc), alpha))
        y = out[-1][1] - s.get("gap", 1.5) * gscale
    return out


def flank(o, side, plan, rng, y_end):
    """Pack (shrinking the gaps if the units overrun y_end), log the layout, build the units."""
    jit = [rng.uniform(-2.5, 2.5) for _ in plan]
    gscale = 1.0
    lay = pack(side, plan, jit, y_end, gscale)
    while lay[-1][1] < y_end and gscale > 0.25:
        gscale -= 0.05
        lay = pack(side, plan, jit, y_end, gscale)
    placed = []
    for s, (fr, ylo, yhi, dmin, alpha) in zip(plan, lay):
        log(f"{'LR'[side > 0]} {s['name']:10s} {s['kind']:9s} y {yhi:6.1f}..{ylo:6.1f}  d {dmin:4.1f}..{D_BACK:4.1f}  "
            f"turn {math.degrees(alpha):4.1f}  gaps x{gscale:.2f}" + ("   <-- PAST THE CROWD EDGE" if dmin < 0 else "")
            + ("   <-- PAST THE FLANK END" if ylo < y_end else ""))
        res = BUILD[s["kind"]](o, fr, rng, s)
        res["foot"] = footprint(s)
        placed.append((s, fr, res, ylo, yhi))
    return placed


def in_units(placed, p, r):
    """Is p within r of any unit's footprint (incl. its queue apron)?"""
    for _, fr, res, _, _ in placed:
        a_lo, a_hi, b_lo, b_hi = res["foot"]
        v = p - fr.o
        a, b = v.dot(fr.R), v.dot(fr.F)
        if a_lo - r < a < a_hi + r and b_lo - r < b < b_hi + r:
            return True
    return False


def lane(o, side, rng, placed, y_end, end_tower=False):
    """Festoon masts on the inner edge (between units), festoons mast-to-mast, mast-to-unit and unit-to-unit, furniture
    in the gaps, feather flags at the unit corners, people walking the lane. end_tower: the last mast is a light tower."""
    ys = [Y_NEAR - 0.6]
    for (_, _, _, ylo, _), (_, _, _, _, yhi) in zip(placed, placed[1:]):
        ys.append((ylo + yhi) / 2)
    ys.append(max(placed[-1][3] - 0.6, y_end))
    poles, out_v = [], Vector((side * 0.894, 0.447, 0.0))             # out_v: across the lane, away from the crowd
    for i, yp in enumerate(ys):
        dp = 0.95 + 0.25 * math.sin(i * 2.1)
        p = Vector((side * (crowd_half(yp) + 6.0 + dp), yp, GROUND_Z))
        if end_tower and i == len(ys) - 1:                              # the lane ends at a light tower
            p = Vector((side * (crowd_half(yp + 1.3) + 6.0 + 1.7), yp + 1.3, GROUND_Z))
            light_tower(o, p, placed[-1][1].p(0.0, 1.2, 0.5), WARM_WHITE, 2400, 70)
            o.block(p, 1.3)
            poles.append(p + Z * 6.95)
            continue
        mh = 7.2 if i else 4.3          # the entrance post stays low: from the booth it stands in front of the 1st sign
        poles.append(p + Z * (mh - 0.25))
        o.block(p, 0.35)
        cyl(o.L("metal_dark"), p, p + Z * mh, 0.07, segs=6)
        box(o.L("metal_dark"), p + Z * 0.05, (0.5, 0.5, 0.1))
        o.G(octa(o.glow, p + Z * (mh + 0.16), 0.17, 0.22), "amber")
        halo(o.halos, p + Z * (mh + 0.16), 1.1, color="amber", planes=2)
        if i % 2 == 1:                                                  # soft lane fill, aimed away from the crowd
            o.lamp("SPOT", p + Z * 6.6 + out_v * 0.3, WARM, 1100, target=p + out_v * 4.5, size=0.8, deg=95)
    for a, b in zip(poles, poles[1:]):                                  # two strands along the lane: warm + party
        festoon(o, a, b, 0.7, spacing=0.75, r=0.095)
        festoon(o, a - Z * 1.5, b - Z * 1.5, 0.45, spacing=0.9, r=0.085, key=PARTY)
    for i, p in enumerate(poles):                                       # mast -> neighboring units
        for k in (i - 1, i):
            if 0 <= k < len(placed):
                anc = min(placed[k][2]["anchors"], key=lambda q: (q - p).length)
                if (anc - p).length < 14.0:
                    festoon(o, p, anc + Z * 0.05, 0.3 + 0.03 * (anc - p).length, spacing=0.7, r=0.09)
    for (_, _, r0, _, _), (_, _, r1, _, _) in zip(placed, placed[1:]):  # unit -> next unit, over the gap
        a, b = min(((p, q) for p in r0["anchors"] for q in r1["anchors"]), key=lambda pq: (pq[0] - pq[1]).length)
        if 1.5 < (a - b).length < 12.0:
            festoon(o, a + Z * 0.05, b + Z * 0.05, 0.3, spacing=0.6, r=0.08)
    # gap furniture: picnic tables where there is room, otherwise a bin
    for k, ((s0, f0, _, ylo, _), (s1, f1, _, _, yhi)) in enumerate(zip(placed, placed[1:])):
        g = ylo - yhi
        yg = (ylo + yhi) / 2
        fwd = (f0.F + f1.F).normalized()
        yaw = math.atan2(fwd.y, fwd.x)
        if g >= 2.0:
            for dd in (5.2, 8.4):
                p = Vector((side * (crowd_half(yg) + 6.0 + dd), yg, GROUND_Z))
                picnic(o, p, yaw)
                o.block(p, 1.0)
                for e in (-1, 1):
                    if rng.random() < 0.6:
                        q = p + Vector((-fwd.y, fwd.x, 0.0)) * (e * 0.95) + fwd * rng.uniform(-0.6, 0.6)
                        o.person(q, p - q, rng.choice(("down", "one", "hips")))
        p = Vector((side * (crowd_half(yg) + 6.0 + 2.2), yg + rng.uniform(-0.3, 0.3), GROUND_Z))
        binn(o, p, ("plastic_orange", "canvas_green", "plastic_blue")[k % 3])
        o.block(p, 0.4)
    # picnic tables on free floor between the units' aprons and the masts
    yaw_l = math.atan2(-0.894, side * 0.447)
    n_t, y = 0, placed[0][4] - 2.0
    while y > y_end + 2.0 and n_t < 4:
        p = Vector((side * (crowd_half(y) + 6.0 + rng.uniform(3.0, 4.6)), y, GROUND_Z))
        if o.clear(p, 1.2) and not in_units(placed, p, 1.1):
            picnic(o, p, yaw_l + rng.uniform(-0.25, 0.25))
            o.block(p, 1.05)
            n_t += 1
            for e in (-1, 1):
                if rng.random() < 0.5:
                    q = p + Vector((side * 0.894, 0.447, 0.0)) * (e * 0.95)
                    o.person(q, p - q, rng.choice(("down", "one", "hips")))
            y -= 6.0
        y -= 1.0
    # feather flags at unit corners
    fcols = ("canvas_red", "canvas_yellow", "canvas_blue", "canvas_green", "truck_teal")   # no white: it clips
    n = 0
    for s, fr, res, _, _ in placed:
        for a, b in res.get("flags", []):
            p = fr.p(a, b)
            if 0.3 < band_d(side, p.x, p.y) < 11.8:
                feather(o, p, face_dj(p, fr.F, 0.5), rng.uniform(3.0, 3.9), rng.uniform(0.6, 0.8), fcols[n % 5])
                o.block(p, 0.5)
                n += 1
    # people in the lane's inner strip: walkers in ones and twos, now and then a group of three chatting
    u_lane = Vector((side * 0.447, -0.894, 0.0))
    y = placed[0][4] - 1.0
    while y > y_end + 1.0:
        p = Vector((side * (crowd_half(y) + 6.0 + rng.uniform(0.7, 2.8)), y, GROUND_Z))
        if o.clear(p, 0.6):
            r = rng.random()
            if r < 0.22:
                ang0 = rng.uniform(0.0, 2.0 * math.pi)
                for t in range(3):
                    q = p + Vector((math.cos(ang0 + t * 2.1), math.sin(ang0 + t * 2.1), 0.0)) * 0.55
                    o.person(q, p - q, rng.choice(("down", "one", "hips")))
            else:
                u = u_lane * (1 if r < 0.6 else -1)
                o.person(p, u, "down")
                if rng.random() < 0.4:
                    o.person(p + Vector((-u.y, u.x, 0.0)) * 0.55, u, rng.choice(("down", "one")))
        y -= rng.uniform(5.5, 8.5)


def lane_floor(o, side, rng, y0=Y_NEAR, y1=Y_FAR):
    """Trampled-dirt floor over the band, a little lighter than the field so the warm light pools read; ragged edges."""
    n = int((y0 - y1) / 2.6)
    rows = []
    for i in range(n + 1):
        y = y0 + (y1 - y0) * i / n + (rng.uniform(-0.4, 0.4) if 0 < i < n else 0.0)
        rows.append([Vector((side * (crowd_half(y) + 6.0 + d), y, GROUND_Z + 0.03))
                     for d in (rng.uniform(0.0, 0.5), 6.0 + rng.uniform(-0.5, 0.5), rng.uniform(11.6, 12.0))])
    bm = o.L("dirt")
    for r0, r1 in zip(rows, rows[1:]):
        for k in range(2):
            poly(bm, [r0[k], r0[k + 1], r1[k + 1], r1[k]], Z)


def build(rng):
    o = Out()
    for side in (-1, 1):
        lane_floor(o, side, rng)
    u_toilets(o, -1, rng)
    for side, plan in ((-1, LEFT), (1, RIGHT)):
        y_end = -70.6 if side < 0 else Y_FAR + 0.3                      # left: the toilet bank holds the far end
        placed = flank(o, side, plan, rng, y_end)
        lane(o, side, rng, placed, y_end, end_tower=side > 0)
    if PROXY:
        for x, y, yaw, pose in o.people:
            p = Vector((x, y, GROUND_Z))
            box(o.L("dino_grey"), p + Z * 0.75, (0.42, 0.26, 1.5), yaw=yaw)
            sphere(o.L("dino_grey"), p + Z * 1.62, 0.12, segs=6, rings=4)
    log(f"lights {len(o.lights)}, people {len(o.people)}")
    lit = [(bm, key) for key, bm in o.lit.items()]
    return {"lit": lit, "glow": [o.glow], "beams": [], "halos": [o.halos], "lights": o.lights, "exclude": [],
            "people": o.people}
