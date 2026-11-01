"""GRAVEYARD SHIFT grounds module HW_PUMPKINS: the pumpkin patch, back right of the field (CONTRACT.md, kit frame).

  Pumpkin King (63, -92)           8.5 m: a giant ribbed jack-o-lantern head (angry eyes, a grin whose mouth is its own
                                   piece for a later jaw cue) under a purple crown with amber jewels, on a red robe with a
                                   leaf collar; one bony hand reaches out, the other holds a crooked staff with a little
                                   lantern; a throne of hay bales behind. Its face looks at the main stage (0, 5).
  Patch (x 41..72, y -79..-97)     ~300 low-poly ribbed pumpkins (24-51 tris each; orange, a few yellow, white and green),
                                   ~80 of them jack-o-lanterns whose glowing faces (fitted onto the facets) look toward the
                                   main field; vines and leaves; two paths and a plaza in front of the King.
  Around                           6 scarecrows (two in the corn, some with glowing eyes, one holding a lantern), hay bale
                                   stacks and round bales, low corn rows along the back and the right (opaque stalks and
                                   leaves, no cards; the front row lit, the rows behind it unlit black silhouettes, which
                                   keeps the bake atlas from drowning in thin islands) with a way in, 4 shepherd's-hook
                                   lanterns; pumpkin stems are black slivers for the same reason.
  People                           ~25: photographing the King, on the paths, at the scarecrows and the corn.
Static; deterministic with the rng passed to build().
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "grounds"))
from kit import *  # noqa: E402,F401,F403

NAME = "pumpkins"
BAKE_SIZE = 2048

# ------------------------------------------------------------------ shared helpers (the same block in hw_pumpkins / hw_crypt)
TAU = 2 * math.pi
UP = Vector((0.0, 0.0, 1.0))
Z0 = GROUND_Z


def yaw_of(d):
    """Yaw about Z that turns +Y onto the horizontal direction d (the people convention, as in landmarks.py)."""
    return math.atan2(-d[0], d[1])


def flat(d):
    v = Vector((d[0], d[1], 0.0))
    return v.normalized() if v.length > 1e-9 else Vector((0.0, 1.0, 0.0))


def toward(p, q):
    return flat((q[0] - p[0], q[1] - p[1]))


def paint(bm, faces, key):
    glow_faces(bm, faces, key)
    return faces


class Parts:
    """The module's meshes and lists, a tris/lights/people tally per part, and a keep-out registry for people."""

    def __init__(self):
        self.lit = {}                                   # LIT key -> bmesh
        self.glow = bmesh.new()
        self.beams, self.halos = bmesh.new(), bmesh.new()
        self.lights, self.exclude, self.people = [], [], []
        self.blocks = []                                # ("c", x, y, r) circles, ("b", x, y, hx, hy, yaw) boxes
        self.wants = []                                 # candidate people (x, y, face, pose), placed at the end
        self.hinged = []                                # (bm, LIT key, pivot, axis, open_deg, delay): CONTRACT.md
        self.tally = {}

    def m(self, key):
        if key not in self.lit:
            self.lit[key] = bmesh.new()
        return self.lit[key]

    def count(self):
        return sum(tris(b) for b in self.lit.values()) + tris(self.glow)

    def run(self, name, fn, *args):
        n0, l0, p0 = self.count(), len(self.lights), len(self.people) + len(self.wants)
        fn(self, *args)
        self.tally[name] = [self.count() - n0, len(self.lights) - l0, len(self.people) + len(self.wants) - p0]

    def add_light(self, *args, **kw):
        self.lights.append(light(*args, **kw))

    def rect(self, pts, pad=1.0):
        xs, ys = [p[0] for p in pts], [p[1] for p in pts]
        self.exclude.append((round(min(xs) - pad, 2), round(min(ys) - pad, 2), round(max(xs) + pad, 2),
                             round(max(ys) + pad, 2)))

    def block(self, c, r):
        self.blocks.append(("c", c[0], c[1], r))

    def block_box(self, c, hx, hy, yaw):
        self.blocks.append(("b", c[0], c[1], hx, hy, yaw))

    def free(self, x, y, pad=0.35):
        for b in self.blocks:
            if b[0] == "c":
                if (x - b[1]) ** 2 + (y - b[2]) ** 2 < (b[3] + pad) ** 2:
                    return False
            else:
                dx, dy = x - b[1], y - b[2]
                c, s = math.cos(b[5]), math.sin(b[5])
                if abs(dx * c + dy * s) < b[3] + pad and abs(-dx * s + dy * c) < b[4] + pad:
                    return False
        return True

    def want(self, p, face, pose):
        self.wants.append((p[0], p[1], flat(face), pose))

    def person(self, x, y, face, pose, min_d=0.8):
        if not self.free(x, y) or any((x - q[0]) ** 2 + (y - q[1]) ** 2 < min_d * min_d for q in self.people):
            return False
        self.people.append((round(x, 3), round(y, 3), round(yaw_of(face), 4), pose))
        return True

    def place_wants(self):
        placed = sum(self.person(x, y, f, pose) for x, y, f, pose in self.wants)
        n = len(self.wants)
        self.wants = []
        return placed, n

    def result(self):
        lit = []
        for key in sorted(self.lit):
            bm = self.lit[key]
            if len(bm.faces):
                lit.append((bm, key))
            else:
                bm.free()
        return {"lit": lit, "glow": [self.glow], "beams": [self.beams] if len(self.beams.faces) else [],
                "halos": [self.halos] if len(self.halos.faces) else [], "lights": self.lights,
                "exclude": self.exclude, "people": self.people, "hinged": self.hinged}


class Frame:
    """A frame on the field: origin o, front f (horizontal unit), r = f turned clockwise (right when FACING f, i.e. the
    left of someone looking at the front); at(l, f, z) = o + r l + f f + up z; kit.box yaw: local X -> r, local Y -> f."""

    def __init__(self, o, front):
        self.o = Vector((o[0], o[1], Z0))
        self.f = flat(front)
        self.r = Vector((self.f.y, -self.f.x, 0.0))
        self.yaw = math.atan2(self.r.y, self.r.x)

    def at(self, l, f=0.0, z=0.0):
        return self.o + self.r * l + self.f * f + UP * z

    def box(self, bm, l, f, z, size, pitch=0.0, roll=0.0):
        return box(bm, self.at(l, f, z), size, yaw=self.yaw, pitch=pitch, roll=roll)


def octa(bm, c, r, rz=None):
    """Octahedron (8 tris): a bulb, a lantern, a wisp."""
    c, rz = Vector(c), r if rz is None else rz
    v = [bm.verts.new(c + Vector(d)) for d in ((r, 0, 0), (0, r, 0), (-r, 0, 0), (0, -r, 0), (0, 0, rz), (0, 0, -rz))]
    faces = []
    for i in range(4):
        a, b = v[i], v[(i + 1) % 4]
        faces += [bm.faces.new((a, b, v[4])), bm.faces.new((b, a, v[5]))]
    return faces


def ball(bm, c, r, segs, rings, scale=(1.0, 1.0, 1.0), rng=None, lump=0.0):
    """Low-poly UV sphere built in a fixed order (kit.sphere's create_uvsphere leaves the face order run-dependent);
    with rng every vertex is pushed in/out by up to `lump` (landmarks.py)."""
    c, s = Vector(c), Vector(scale)

    def vert(d):
        k = rng.uniform(1.0 - lump, 1.0 + lump) if rng else 1.0
        return bm.verts.new(c + Vector((d.x * s.x, d.y * s.y, d.z * s.z)) * (r * k))

    top = vert(Vector((0.0, 0.0, 1.0)))
    ring = []
    for i in range(1, rings):
        phi = math.pi * i / rings
        ring.append([vert(Vector((math.sin(phi) * math.cos(TAU * j / segs), math.sin(phi) * math.sin(TAU * j / segs),
                                  math.cos(phi)))) for j in range(segs)])
    bot = vert(Vector((0.0, 0.0, -1.0)))
    faces = []
    for j in range(segs):
        k = (j + 1) % segs
        faces.append(bm.faces.new((top, ring[0][j], ring[0][k])))
        for a, b in zip(ring, ring[1:]):
            faces.append(bm.faces.new((a[j], b[j], b[k], a[k])))
        faces.append(bm.faces.new((bot, ring[-1][k], ring[-1][j])))
    return faces


def tube(bm, pts, r, segs=4, r1=None):
    """A tube along the polyline pts, radius r (-> r1 at the end; 0 = a pointed tip), rings parallel-transported (no
    twist), open ends. Returns its faces."""
    pts = [Vector(p) for p in pts]
    n = len(pts)
    r1 = r if r1 is None else r1
    side, rings = None, []
    for i, p in enumerate(pts):
        t = (pts[min(i + 1, n - 1)] - pts[max(i - 1, 0)]).normalized()
        if side is not None:
            side = side - t * side.dot(t)
        if side is None or side.length < 1e-6:
            side = t.cross(UP if abs(t.z) < 0.9 else Vector((1.0, 0.0, 0.0)))
        side.normalize()
        up2 = t.cross(side)
        rad = r + (r1 - r) * i / (n - 1)
        if rad < 1e-5:
            rings.append([bm.verts.new(p)])
        else:
            rings.append([bm.verts.new(p + (side * math.cos(TAU * k / segs) + up2 * math.sin(TAU * k / segs)) * rad)
                          for k in range(segs)])
    faces = []
    for a, b in zip(rings, rings[1:]):
        for k in range(segs):
            k2 = (k + 1) % segs
            if len(b) == 1:
                faces.append(bm.faces.new((a[k], a[k2], b[0])))
            elif len(a) == 1:
                faces.append(bm.faces.new((a[0], b[k2], b[k])))
            else:
                faces.append(bm.faces.new((a[k], a[k2], b[k2], b[k])))
    return faces


def vprism(bm, c, z0, z1, r0, r1, segs, phase=0.0, cap0=True, cap1=True):
    """Vertical segs-sided frustum around (c.x, c.y) from z0 (radius r0) to z1 (radius r1; 0 = a pyramid); vertex k at
    angle phase + k TAU/segs (absolute z)."""
    def ring(r, z):
        return [bm.verts.new((c[0] + r * math.cos(phase + TAU * k / segs), c[1] + r * math.sin(phase + TAU * k / segs),
                              z)) for k in range(segs)]
    a = ring(r0, z0)
    faces = []
    if r1 < 1e-6:
        tip = bm.verts.new((c[0], c[1], z1))
        faces += [bm.faces.new((a[k], a[(k + 1) % segs], tip)) for k in range(segs)]
    else:
        b = ring(r1, z1)
        faces += [bm.faces.new((a[k], a[(k + 1) % segs], b[(k + 1) % segs], b[k])) for k in range(segs)]
        if cap1:
            faces.append(bm.faces.new(b))
    if cap0:
        faces.append(bm.faces.new(list(reversed(a))))
    return faces


def extrude(bm, fr, poly, f0, f1):
    """Prism of the (l, z) polygon `poly` (counter-clockwise with l to the right) between f0 and f1 in frame fr."""
    back = [bm.verts.new(fr.at(l, f0, z)) for l, z in poly]
    front = [bm.verts.new(fr.at(l, f1, z)) for l, z in poly]
    faces = [bm.faces.new(back), bm.faces.new(list(reversed(front)))]
    for i in range(len(poly)):
        j = (i + 1) % len(poly)
        faces.append(bm.faces.new((back[i], front[i], front[j], back[j])))
    return faces


def orient_out(faces, center):
    """Turn every face's normal away from `center` (parts built without care for the winding)."""
    c = Vector(center)
    for f in faces:
        f.normal_update()
        if f.normal.dot(f.calc_center_median() - c) < 0:
            f.normal_flip()
    return faces


def festoon(P, a, b, sag, keys, spacing=0.75, r=0.1, wire=0.012):
    """String lights from a to b: an unlit black wire (glow 'black': no bake texels) and octahedron bulbs cycling keys."""
    a, b = Vector(a), Vector(b)
    pts = catenary(a, b, sag, n=max(6, int((b - a).length / 1.6)))
    paint(P.glow, tube(P.glow, pts, wire, segs=3), "black")
    cum = [0.0]
    for p, q in zip(pts, pts[1:]):
        cum.append(cum[-1] + (q - p).length)
    nb, k = max(2, int(cum[-1] / spacing)), 0
    for i in range(1, nb):
        s = cum[-1] * i / nb
        while k < len(pts) - 2 and cum[k + 1] < s:
            k += 1
        p = pts[k].lerp(pts[k + 1], (s - cum[k]) / max(1e-9, cum[k + 1] - cum[k]))
        paint(P.glow, octa(P.glow, p - UP * (r * 1.3), r), keys[i % len(keys)])


def board_text(P, fr, text, px, l_center, f, z_bottom, key):
    """5x7 LED text on the frame's front plane (readable from in front), centred at l_center."""
    w = text_width(text, px)
    led_text(P.glow, text, fr.at(l_center + w / 2, f, z_bottom), -fr.r, UP, pixel=px, gap=px * 0.2, key=key)


def front_quad(P, fr, l, f, z, w, h, key):
    """A glowing w x h rectangle centred at (l, z) on the plane f, facing the frame's front."""
    c, rt = fr.at(l, f, z), -fr.r
    return paint(P.glow, quad(P.glow, c - rt * (w / 2) - UP * (h / 2), c + rt * (w / 2) - UP * (h / 2),
                              c + rt * (w / 2) + UP * (h / 2), c - rt * (w / 2) + UP * (h / 2)), key)


def front_disc(P, fr, l, f, z, r, key, n=10):
    """A glowing disc of radius r centred at (l, z) on the plane f, facing the frame's front."""
    g = P.glow
    c = g.verts.new(fr.at(l, f, z))
    ring = [g.verts.new(fr.at(l + r * math.cos(TAU * k / n), f, z + r * math.sin(TAU * k / n))) for k in range(n)]
    return paint(g, [g.faces.new((c, ring[(k + 1) % n], ring[k])) for k in range(n)], key)



# ------------------------------------------------------------------ the pumpkin patch
PK = Vector((63.0, -92.0, Z0))               # the Pumpkin King
STAGE = (0.0, 5.0)                           # ... looks at the main stage
FIELD = (0.0, -30.0)                         # the main field: fronts turn toward it
WARM, ORANGE, PURPLE, AMBER = (1.0, 0.72, 0.38), (1.0, 0.40, 0.05), (0.55, 0.15, 1.0), (1.0, 0.55, 0.15)
GREEN = (0.15, 1.0, 0.25)
PATHS = [((40.6, -78.6), (60.3, -88.5)), ((40.6, -93.0), (51.0, -91.5)), ((51.0, -91.5), (60.3, -88.5)),
         ((52.2, -91.6), (52.2, -97.9))]
PATH_W = 0.85                                # half width: no pumpkins there
SOUTH_ROWS = (-98.2, -99.2, -100.2, -101.2)  # corn rows along the back (constant y), x 41.2..72.6
EAST_ROWS = (73.6, 74.7, 75.8, 76.9)         # corn rows along the right (constant x), y -80..-101.1
CORN_GAP = (51.0, 53.4)                      # the way into the corn
FACE_TARGETS = ((0.0, 0.0), (-10.0, -25.0), (10.0, -30.0), (0.0, -45.0), (25.0, -40.0), (-20.0, -50.0), (5.0, -15.0))


def king_frame():
    return Frame(PK, toward(PK, STAGE))


def plaza():
    return PK + king_frame().f * 5.2


def seg_dist(p, a, b):
    dx, dy = b[0] - a[0], b[1] - a[1]
    t = max(0.0, min(1.0, ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / (dx * dx + dy * dy)))
    return math.hypot(p[0] - a[0] - t * dx, p[1] - a[1] - t * dy)


def on_path(p, pad=0.0):
    pl = plaza()
    return (any(seg_dist(p, a, b) < PATH_W + pad for a, b in PATHS)
            or math.hypot(p[0] - pl.x, p[1] - pl.y) < 3.2 + pad)


class Gourd:
    """A ribbed pumpkin standing on c: `segs` vertices per profile ring (segs/2 lobes; vertex 0, a lobe peak, points
    along yaw), rings (z/h, radius factor), height h. surface() finds points on its facets, so carved faces fit."""

    def __init__(self, c, r, h, segs, yaw, lobe=0.12, rings=((0.28, 1.0), (0.72, 0.9)), top=0.88, bottom=-0.04,
                 tilt=(0.0, 0.0)):
        self.c, self.r, self.h, self.segs, self.lobe = Vector(c), r, h, segs, lobe
        self.rings, self.top, self.bottom = rings, top, bottom
        self.M = (Matrix.Translation(self.c) @ Matrix.Rotation(yaw, 4, "Z") @ Matrix.Rotation(tilt[0], 4, "X")
                  @ Matrix.Rotation(tilt[1], 4, "Y"))
        self.fwd = (self.M.to_3x3() @ Vector((1.0, 0.0, 0.0))).normalized()

    def lf(self, k):
        return 1.0 if k % 2 == 0 else 1.0 - self.lobe

    def build(self, bm):
        n, M = self.segs, self.M
        bot = bm.verts.new(M @ Vector((0.0, 0.0, self.bottom * self.h)))
        rs = [[bm.verts.new(M @ Vector((rf * self.lf(k) * self.r * math.cos(TAU * k / n),
                                        rf * self.lf(k) * self.r * math.sin(TAU * k / n), zf * self.h)))
               for k in range(n)] for zf, rf in self.rings]
        top = bm.verts.new(M @ Vector((0.0, 0.0, self.top * self.h)))
        faces = []
        for k in range(n):
            k2 = (k + 1) % n
            faces.append(bm.faces.new((bot, rs[0][k2], rs[0][k])))
            for a, b in zip(rs, rs[1:]):
                faces.append(bm.faces.new((a[k], a[k2], b[k2], b[k])))
            faces.append(bm.faces.new((rs[-1][k], rs[-1][k2], top)))
        return faces

    def top_point(self):
        return self.M @ Vector((0.0, 0.0, self.top * self.h))

    def surface(self, theta, zf, lift):
        """World point at local azimuth theta (0 = vertex 0) and height zf*h on the facets (never inside), lifted."""
        n = self.segs
        u = (theta % TAU) / (TAU / n)
        k = int(u) % n
        t = u - int(u)
        lobe = self.lf(k) * (1 - t) + self.lf(k + 1) * t
        prof = [(self.bottom, 0.0)] + list(self.rings) + [(self.top, 0.0)]
        zf = max(prof[0][0], min(prof[-1][0], zf))
        i = min(max(j for j in range(len(prof) - 1) if prof[j][0] <= zf), len(prof) - 2)
        w = (zf - prof[i][0]) / max(1e-9, prof[i + 1][0] - prof[i][0])
        rad = (prof[i][1] * (1 - w) + prof[i + 1][1] * w) * lobe * self.r + lift
        return self.M @ Vector((rad * math.cos(theta), rad * math.sin(theta), zf * self.h))

    def _pt(self, g, u, v, zc, lift):
        return g.verts.new(self.surface(u / (self.r * 0.95), zc + v / self.h, lift))

    def _out(self, faces):
        for f in faces:
            f.normal_update()
            if f.normal.dot(self.fwd) < 0:
                f.normal_flip()
        return faces

    def poly(self, P, pts, zc, lift, key, sub=1):
        """A glowing polygon on the facets: pts (u, v) in meters (u to the viewer's right, v up from height zc*h)."""
        g = P.glow
        if len(pts) == 3 and sub == 1:
            return self._out(paint(g, [g.faces.new([self._pt(g, u, v, zc, lift) for u, v in pts])], key))
        cu, cv = sum(p[0] for p in pts) / len(pts), sum(p[1] for p in pts) / len(pts)
        cen = self._pt(g, cu, cv, zc, lift)
        ring = []
        for i in range(len(pts)):
            a, b = pts[i], pts[(i + 1) % len(pts)]
            for s in range(sub):
                t = s / sub
                ring.append(self._pt(g, a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t, zc, lift))
        return self._out(paint(g, [g.faces.new((cen, ring[j], ring[(j + 1) % len(ring)])) for j in range(len(ring))],
                               key))

    def strip(self, P, top, bot, zc, lift, key):
        g = P.glow
        T = [self._pt(g, u, v, zc, lift) for u, v in top]
        B = [self._pt(g, u, v, zc, lift) for u, v in bot]
        return self._out(paint(g, [g.faces.new((B[i], B[i + 1], T[i + 1], T[i])) for i in range(len(top) - 1)], key))


EYES = {"classic": (((-0.42, 0.06), (-0.12, 0.06), (-0.27, 0.34)), ((0.12, 0.06), (0.42, 0.06), (0.27, 0.34))),
        "angry": (((-0.46, 0.3), (-0.12, 0.1), (-0.42, 0.04)), ((0.46, 0.3), (0.12, 0.1), (0.42, 0.04))),
        "round": (tuple((-0.26 + 0.13 * math.cos(TAU * k / 6), 0.2 + 0.13 * math.sin(TAU * k / 6)) for k in range(6)),
                  tuple((0.26 + 0.13 * math.cos(TAU * k / 6), 0.2 + 0.13 * math.sin(TAU * k / 6)) for k in range(6)))}


def jack_face(P, gd, kind, key):
    """A carved face on a pumpkin's vertex-0 side (units of its radius): eyes, nose, a grin."""
    r = gd.r
    for eye in EYES[kind]:
        gd.poly(P, [(u * r, v * r) for u, v in eye], 0.5, 0.012, key)
    gd.poly(P, [(-0.07 * r, -0.07 * r), (0.07 * r, -0.07 * r), (0.0, 0.05 * r)], 0.5, 0.012, key)
    us = [-0.46 + 0.23 * i for i in range(5)]
    gd.strip(P, [(u * r, (-0.15 + 0.17 * (u / 0.46) ** 2) * r) for u in us],
             [(u * r, (-0.37 + 0.27 * (u / 0.46) ** 2) * r) for u in us], 0.5, 0.012, key)


def pumpkin_king(P, rng):
    KF = king_frame()
    K, F = PK, KF.f
    red, green, bone, g = P.m("canvas_red"), P.m("dino_green"), P.m("bone"), P.glow
    n, ph = 14, rng.uniform(0, TAU)
    rings = [(2.4, -0.02), (1.65, 2.1), (1.05, 3.95)]                              # robe, with folds at the hem
    vs = [[red.verts.new(K + Vector((rr * (0.86 if (i == 0 and k % 2) else 1.0) * math.cos(ph + TAU * k / n),
                                     rr * (0.86 if (i == 0 and k % 2) else 1.0) * math.sin(ph + TAU * k / n), z)))
           for k in range(n)] for i, (rr, z) in enumerate(rings)]
    for a, b in zip(vs, vs[1:]):
        for k in range(n):
            red.faces.new((a[k], a[(k + 1) % n], b[(k + 1) % n], b[k]))
    red.faces.new(vs[-1])
    vprism(P.m("canvas_black"), K, Z0 + 3.9, Z0 + 4.65, 0.75, 0.6, 8, cap0=False)  # neck
    for k in range(10):                                                             # leaf collar
        a = ph + TAU * (k + 0.5) / 10
        rad = Vector((math.cos(a), math.sin(a), 0.0))
        tube(green, [K + rad * 0.85 + UP * 3.95, K + rad * 1.55 + UP * 4.4, K + rad * 2.0 + UP * 4.45], 0.3, segs=3,
             r1=0.0)
    for s, pts in ((1, ((1.0, 0.0, 3.6), (2.05, 0.35, 3.25), (2.45, 0.55, 4.2))),     # sleeves: staff hand raised
                   (-1, ((-1.0, 0.0, 3.6), (-1.95, 0.55, 3.15), (-2.3, 1.3, 3.0)))):  # ... the other reaching out
        tube(red, [KF.at(*q) for q in pts], 0.36, segs=6, r1=0.26)
    ball(bone, KF.at(2.47, 0.58, 4.35), 0.24, 6, 4)                                 # the staff hand
    hand = KF.at(-2.38, 1.5, 3.0)
    ball(bone, hand, 0.24, 6, 4)
    for j, (dl, dz) in enumerate(((-0.25, 0.12), (-0.08, 0.04), (0.08, -0.04), (0.22, -0.14))):   # bony fingers
        d = (F * 1.0 + KF.r * dl + UP * dz).normalized()
        tube(bone, [hand + d * 0.18, hand + d * 0.45 - UP * 0.04, hand + d * 0.62 - UP * 0.14], 0.05, segs=4, r1=0.03)
    tube(P.m("wood_dark"), [KF.at(2.55, 0.6, -0.05), KF.at(2.52, 0.6, 3.0), KF.at(2.5, 0.62, 6.35),
                            KF.at(2.5, 0.92, 6.92), KF.at(2.5, 1.38, 6.95), KF.at(2.5, 1.58, 6.66)], 0.07, segs=5)
    cyl(P.m("metal_dark"), KF.at(2.5, 1.58, 6.66), KF.at(2.5, 1.58, 6.42), 0.015, segs=3, cap=False)
    lantern = Gourd(KF.at(2.5, 1.58, 5.9), 0.3, 0.46, 8, KF.yaw + math.pi / 2, rings=((0.2, 0.86), (0.5, 1.0),
                                                                                       (0.8, 0.84)), top=0.93)
    paint(g, lantern.build(g), "fire")                                              # the staff's little lantern
    head = Gourd(K + UP * 4.45, 2.2, 3.4, 16, math.atan2(F.y, F.x), lobe=0.07, bottom=0.0, top=0.92,
                 rings=((0.1, 0.62), (0.3, 0.93), (0.55, 1.0), (0.8, 0.85)))
    head.build(P.m("plastic_orange"))
    for sgn in (-1, 1):                                                             # angry eyes, nose
        head.poly(P, [(1.45 * sgn, 0.2), (0.4 * sgn, 0.3), (1.35 * sgn, 0.95)], 0.52, 0.06, "bulb_warm", sub=3)
    head.poly(P, [(-0.25, -0.15), (0.25, -0.15), (0.0, 0.22)], 0.52, 0.06, "bulb_warm", sub=2)
    us = [-1.55 + 3.1 * i / 12 for i in range(13)]                                   # the grin: its own piece (jaw cue)
    head.strip(P, [(u, -0.45 + 0.45 * (u / 1.55) ** 2) for u in us], [(u, -1.15 + 0.75 * (u / 1.55) ** 2) for u in us],
               0.52, 0.06, "bulb_warm")
    for u, v, w_, h_ in ((-0.5, -0.56, 0.36, 0.34), (0.5, -0.56, 0.36, 0.34), (0.0, -0.93, 0.34, 0.3)):   # teeth
        p = head.surface(u / (2.2 * 0.95), 0.52 + v / 3.4, 0.1)
        box(P.m("plastic_orange"), p, (0.16, w_, h_), yaw=math.atan2(F.y, F.x) + u / (2.2 * 0.95))
    # The jaw (hinged, CONTRACT.md; the lead, 2026-10-09): the lower face below the grin as a closed shell plate 6 cm
    # proud of the head, over a glowing mouth interior (2.5 cm out). It drops open just before the drop (delay 0.8).
    ju = [-1.45 + 2.9 * i / 10 for i in range(11)]
    jtop = [(u, -1.15 + 0.75 * (u / 1.55) ** 2) for u in ju]                      # the grin's lower edge
    jbot = [(u, -1.62) for u in ju]
    head.strip(P, jtop, jbot, 0.52, 0.025, "fire")                                # the mouth, revealed when open
    jaw = bmesh.new()
    rows = 4

    def jp(u, v, lift):
        return jaw.verts.new(head.surface(u / (head.r * 0.95), 0.52 + v / head.h, lift))
    grids = [[[jp(u, t + (b - t) * j / rows, lift) for (u, t), (_, b) in zip(jtop, jbot)] for j in range(rows + 1)]
             for lift in (0.06, -0.04)]                                           # outer, inner
    nu = len(ju)
    for G_ in grids:
        for j in range(rows):
            for i in range(nu - 1):
                jaw.faces.new((G_[j][i], G_[j][i + 1], G_[j + 1][i + 1], G_[j + 1][i]))
    o_, n_ = grids
    rim = ([(o_[0][i], o_[0][i + 1], n_[0][i + 1], n_[0][i]) for i in range(nu - 1)]
           + [(o_[rows][i], o_[rows][i + 1], n_[rows][i + 1], n_[rows][i]) for i in range(nu - 1)]
           + [(o_[j][0], o_[j + 1][0], n_[j + 1][0], n_[j][0]) for j in range(rows)]
           + [(o_[j][nu - 1], o_[j + 1][nu - 1], n_[j + 1][nu - 1], n_[j][nu - 1]) for j in range(rows)])
    for q in rim:
        jaw.faces.new(q)
    bmesh.ops.recalc_face_normals(jaw, faces=list(jaw.faces))                    # a closed shell: normals outward
    zc_hinge = 0.52 + (-0.4) / head.h                                             # the grin's corners
    pivot = K + UP * (4.45 + zc_hinge * head.h) + F * 0.9
    axis = KF.r
    rise = (Matrix.Rotation(math.radians(28.0), 3, axis) @ Vector(F)).z           # + turn about r lifts the front?
    P.hinged.append((jaw, "plastic_orange", tuple(pivot), tuple(axis), -28.0 if rise > 0 else 28.0, 0.8))
    zc = 4.45 + 3.4 * 0.86                                                          # crown on the head's top
    crown = []
    for dr, inner in ((0.0, False), (-0.025, True)):                               # band: outside and inside
        cv = [g.verts.new(K + Vector(((rr + dr) * math.cos(TAU * k / 10), (rr + dr) * math.sin(TAU * k / 10), z)))
              for rr, z in ((0.98, zc - 0.08), (1.1, zc + 0.42)) for k in range(10)]
        for k in range(10):
            q = (cv[k], cv[(k + 1) % 10], cv[10 + (k + 1) % 10], cv[10 + k])
            crown.append(g.faces.new(tuple(reversed(q)) if inner else q))
    paint(g, crown, "purple")
    for k in range(5):
        a = TAU * k / 5 + math.atan2(F.y, F.x)
        rad = Vector((math.cos(a), math.sin(a), 0.0))
        base = K + rad * 1.06 + UP * (zc + 0.4)
        paint(g, cone(g, base, base + rad * 0.12 + UP * 0.72, 0.17, segs=4), "purple")
        paint(g, octa(g, base + rad * 0.13 + UP * 0.8, 0.11), "amber")
    tube(P.m("dino_brown"), [K + UP * (4.45 + 3.4 * 0.9), K + UP * (zc + 0.45) + F * 0.08, K + UP * (zc + 0.72) + F * 0.3],
         0.28, segs=5, r1=0.16)
    face = head.surface(0.0, 0.52, 0.0)
    P.add_light("PumpKingFace", "SPOT", face + F * 0.5, ORANGE, 1300, target=K + F * 12.0, spot_deg=115, size=0.4)
    side = KF.r
    P.add_light("PumpKingWarm", "SPOT", K + F * 9.0 + side * 4.5 + UP * 0.4, AMBER, 1400, target=K + UP * 5.6,
                spot_deg=34, size=0.3)
    P.add_light("PumpKingRim", "SPOT", K - F * 6.5 - side * 5.0 + UP * 1.0, PURPLE, 3500, target=K + UP * 5.0,
                spot_deg=40, size=0.3)
    P.block(K, 2.45)
    P.block(KF.at(2.55, 0.6), 0.15)
    P.rect([KF.at(l, f) for l in (-3.0, 3.0) for f in (-3.9, 2.0)], pad=0.3)
    for k in range(7):                                                              # photographers
        a = math.atan2(F.y, F.x) + math.radians(-24 + 8 * k + rng.uniform(-3, 3))
        p = K + Vector((math.cos(a), math.sin(a), 0.0)) * rng.uniform(4.9, 6.6)
        P.want(p, K - p, ("one", "up", "down", "hips", "one", "down", "up")[k])


def hay(P, rng):
    KF = king_frame()
    K, F = PK, KF.f
    straw = P.m("canvas_yellow")
    a0 = math.atan2(F.y, F.x)
    for lvl, n, off in ((0, 7, 0.0), (1, 6, 0.5)):                                 # the King's throne
        for j in range(n):
            a = a0 + math.radians(115 + (j + off) * 130 / 6)
            c = K + Vector((math.cos(a), math.sin(a), 0.0)) * 3.45
            box(straw, (c.x, c.y, Z0 + 0.225 + 0.45 * lvl), (1.1, 0.5, 0.45), yaw=a + math.pi / 2)
            if lvl == 0:
                P.block_box(c, 0.6, 0.3, a + math.pi / 2)
    for x, y, yaw in ((47.6, -88.9, 0.35), (58.4, -83.3, -0.4), (44.2, -96.4, 0.1), (66.7, -96.2, 0.0)):   # stacks
        for dx, lvl in ((-0.56, 0), (0.56, 0), (0.0, 1)):
            c = Vector((x + dx * math.cos(yaw), y + dx * math.sin(yaw), 0.0))
            box(straw, (c.x, c.y, Z0 + 0.225 + 0.45 * lvl), (1.1, 0.5, 0.45), yaw=yaw)
        P.block_box((x, y), 1.15, 0.3, yaw)
    for x, y, a in ((71.5, -80.6, 0.4), (71.6, -84.2, 1.2), (70.2, -96.5, 0.2)):   # round bales on their side
        d = Vector((math.cos(a), math.sin(a), 0.0)) * 0.6
        c = Vector((x, y, Z0 + 0.58))
        cyl(straw, c - d, c + d, 0.6, segs=10)
        P.block((x, y), 0.85)


def scarecrow(P, rng, pos, eyes, hat, shirt, lantern=None):
    S = Frame(pos, toward(pos, FIELD))
    wood, straw = P.m("wood"), P.m("canvas_yellow")
    cyl(wood, S.at(0, 0, -0.05), S.at(0, 0, 2.95), 0.055, segs=4, cap=False)       # post and crossbar
    S.box(wood, 0, 0, 2.2, (1.95, 0.07, 0.07))
    cloth = P.m(shirt)
    S.box(cloth, 0, 0.0, 1.9, (0.58, 0.3, 0.72))
    for s in (-1, 1):
        tube(cloth, [S.at(0.28 * s, 0, 2.16), S.at(0.62 * s, 0, 2.12), S.at(0.93 * s, 0.02, 2.05)], 0.12, segs=4,
             r1=0.09)
        tube(straw, [S.at(0.92 * s, 0.02, 2.05), S.at(1.1 * s, 0.04, 1.92)], 0.09, segs=4, r1=0.0)
        tube(P.m("dino_brown"), [S.at(0.13 * s, 0, 1.58), S.at(0.15 * s, 0.03, 1.15), S.at(0.17 * s, 0.05, 0.82)], 0.12,
             segs=4, r1=0.1)
        tube(straw, [S.at(0.17 * s, 0.05, 0.82), S.at(0.19 * s, 0.07, 0.6)], 0.1, segs=4, r1=0.0)
    ball(P.m("bone"), S.at(0, 0.02, 2.62), 0.25, 6, 4, scale=(1.0, 1.0, 1.15))    # burlap head
    if hat == "witch":
        cyl(P.m("canvas_black"), S.at(0, 0.02, 2.86), S.at(0, 0.02, 2.9), 0.46, segs=8)
        tube(P.m("canvas_black"), [S.at(0, 0.02, 2.9), S.at(0.03, 0.0, 3.25), S.at(0.13, -0.08, 3.52)], 0.22, segs=6,
             r1=0.0)
    else:
        cyl(straw, S.at(0, 0.02, 2.84), S.at(0, 0.02, 2.88), 0.48, segs=8)
        cyl(straw, S.at(0, 0.02, 2.88), S.at(0, 0.02, 3.08), 0.22, segs=8, r2=0.19)
    if eyes:
        for s in (-1, 1):
            g = P.glow
            pts = [S.at(0.15 * s, 0.276, 2.65), S.at(0.04 * s, 0.276, 2.65), S.at(0.1 * s, 0.276, 2.75)]
            f = g.faces.new([g.verts.new(q) for q in pts])
            f.normal_update()
            if f.normal.dot(S.f) < 0:
                f.normal_flip()
            paint(g, [f], eyes)
        front_quad(P, S, 0.0, 0.272, 2.52, 0.18, 0.035, eyes)
    if lantern:
        hand = S.at(-1.06, 0.05, 1.9)
        cyl(P.m("metal_dark"), hand, hand - UP * 0.28, 0.01, segs=3, cap=False)
        paint(P.glow, octa(P.glow, hand - UP * 0.42, 0.11, rz=0.16), "fire")
        P.add_light(lantern, "POINT", hand - UP * 0.42 + S.f * 0.25, WARM, 110, size=0.2)
    P.block(S.at(0, 0), 0.55)
    return S


def hook_lantern(P, base, d, name, power):
    base, d = Vector((base[0], base[1], Z0)), flat(d)
    tube(P.m("metal_dark"), [base - UP * 0.05, base + UP * 2.3, base + UP * 2.55 + d * 0.15, base + UP * 2.48 + d * 0.36],
         0.028, segs=4)
    lp = base + d * 0.36 + UP * 2.08
    cyl(P.m("metal_dark"), lp + UP * 0.38, lp + UP * 0.2, 0.012, segs=3, cap=False)
    box(P.m("metal_dark"), lp + UP * 0.19, (0.2, 0.2, 0.05))
    paint(P.glow, octa(P.glow, lp, 0.12, rz=0.17), "fire")
    P.add_light(name, "POINT", lp + d * 0.18, WARM, power, size=0.2)
    P.block(base, 0.12)


def surroundings(P, rng):
    """Scarecrows, shepherd's-hook lanterns along the paths, and the purple washes on the corn."""
    for i, (pos, eyes, hat, shirt, lantern) in enumerate((
            ((46.0, -85.2), "ember", "straw", "canvas_red", None),
            ((56.5, -80.6), None, "witch", "canvas_green", None),
            ((68.6, -82.4), "fire", "witch", "plastic_orange", "PumpScarecrow"),
            ((49.2, -95.3), None, "straw", "dino_brown", None),
            ((75.25, -88.6), "ember", "witch", "canvas_black", None),
            ((54.9, -99.0), "fire", "straw", "canvas_red", None))):
        S = scarecrow(P, rng, pos, eyes, hat, shirt, lantern)
        if i in (0, 2):
            p = S.at(0.7, 1.7)
            P.want(p, S.at(0, 0) - p, "one" if i else "hips")
    for i, (a, b, t, off) in enumerate(((PATHS[0][0], PATHS[0][1], 0.22, 1.25), (PATHS[0][0], PATHS[0][1], 0.68, -1.25),
                                       (PATHS[1][0], PATHS[1][1], 0.45, -1.25), (PATHS[2][0], PATHS[2][1], 0.55, 1.25))):
        d = flat((b[0] - a[0], b[1] - a[1]))
        n = Vector((-d.y, d.x, 0.0))
        p = Vector((a[0], a[1], 0.0)).lerp(Vector((b[0], b[1], 0.0)), t) + n * off
        hook_lantern(P, p, -n if off > 0 else n, f"PumpLantern{i}", 170)
    for name, pos, tgt in (("PumpCornS", (46.5, -94.2), (47.5, -100.0)), ("PumpCornE", (70.4, -89.5), (76.0, -89.0))):
        base = Vector((pos[0], pos[1], Z0))
        d = toward(pos, tgt)
        cyl(P.m("metal_dark"), base, base + UP * 2.3, 0.04, segs=4, cap=False)
        box(P.m("metal_dark"), base + UP * 2.42 + d * 0.06, (0.26, 0.24, 0.3), yaw=math.atan2(d.y, d.x), roll=-0.5)
        P.add_light(name, "SPOT", base + UP * 2.4 + d * 0.3, GREEN, 1500, target=Vector((tgt[0], tgt[1], Z0 + 0.9)),
                    spot_deg=85, size=0.3)
        P.block(pos, 0.3)


def corn(P, rng):
    """Low corn rows: 3-sided stalks with three blade leaves each (opaque, 12 tris). Only the front row of each band is
    lit; the rows behind it are unlit black silhouettes (glow "black": no bake islands; thin 3-sided parts would
    otherwise fill the bake atlas with margins)."""
    wood, dry = P.m("wood"), P.m("dino_brown")
    keep = [(p[1], p[2], 0.75) for p in P.blocks if p[0] == "c" and p[3] < 0.6]    # scarecrow posts in the corn
    rows = [((41.2, y), (72.6, y)) for y in SOUTH_ROWS] + [((x, -79.4), (x, -101.1)) for x in EAST_ROWS]
    n = 0
    fronts = {0, len(SOUTH_ROWS)}
    for ri, ((x0, y0), (x1, y1)) in enumerate(rows):
        lit = ri in fronts
        L = math.hypot(x1 - x0, y1 - y0)
        s = rng.uniform(0.0, 0.3)
        while s < L:
            t = s / L
            x = x0 + (x1 - x0) * t + rng.uniform(-0.1, 0.1)
            y = y0 + (y1 - y0) * t + rng.uniform(-0.1, 0.1)
            s += rng.uniform(0.42, 0.58)
            if (y0 == y1 and CORN_GAP[0] < x < CORN_GAP[1]) or any((x - kx) ** 2 + (y - ky) ** 2 < kr * kr
                                                                    for kx, ky, kr in keep):
                continue
            h = rng.uniform(1.45, 2.05)
            base = Vector((x, y, Z0 - 0.03))
            top = base + Vector((rng.uniform(-0.12, 0.12), rng.uniform(-0.12, 0.12), h))
            parts = tube(wood if lit else P.glow, [base, top], 0.045, segs=3, r1=0.0)
            a = rng.uniform(0, TAU)
            for q in (0.3, 0.52, 0.74):
                a += rng.uniform(1.6, 2.6)
                at = base.lerp(top, q)
                d = Vector((math.cos(a), math.sin(a), 0.0))
                mat = (dry if rng.random() < 0.35 else wood) if lit else P.glow
                parts += tube(mat, [at, at + d * rng.uniform(0.5, 0.7) - UP * rng.uniform(0.0, 0.25)], 0.055, segs=3, r1=0.0)
            if not lit:
                paint(P.glow, parts, "black")
            n += 1
    for x0, x1 in ((41.0, CORN_GAP[0]), (CORN_GAP[1], 72.8)):
        P.block_box(((x0 + x1) / 2, -99.75), (x1 - x0) / 2, 1.9, 0.0)
    P.block_box((75.25, -90.9), 2.05, 11.0, 0.0)
    P.rect([(41.0, -101.8), (72.8, -97.6)], pad=0.2)
    P.rect([(73.2, -101.8), (77.6, -79.6)], pad=0.2)
    for k in range(2):                                                              # at the way into the corn
        P.want((51.7 + 1.0 * k, -96.9 + 0.3 * k), (0.0, -1.0), ("down", "hips")[k])
    return n


def patch(P, rng):
    """~300 pumpkins in clumps (24-51 tris each), ~80 carved and lit facing the main field; vines and leaves."""
    clumps = [(47.0, -82.0, 4.0), (53.5, -93.0, 4.5), (66.0, -85.0, 4.0), (70.0, -92.5, 3.5), (57.5, -81.5, 3.0),
              (45.0, -94.5, 3.0), (61.0, -96.0, 3.0)]
    pumps, grid, CELL = [], {}, 2.0
    for x, y, r in ((44.5, -90.2, 0.95), (64.4, -87.0, 0.85), (69.0, -89.4, 0.8)):  # three giants
        pumps.append((x, y, r))
        grid.setdefault((int(x // CELL), int(y // CELL)), []).append((x, y, r))
    tries = 0
    while len(pumps) < 300 and tries < 40000:
        tries += 1
        x, y = rng.uniform(41.0, 72.6), rng.uniform(-97.2, -78.9)
        dens = 0.22 + sum(math.exp(-((x - cx) ** 2 + (y - cy) ** 2) / (cr * cr)) for cx, cy, cr in clumps)
        if rng.random() > min(1.0, dens):
            continue
        u = rng.random()
        r = rng.uniform(0.17, 0.27) if u < 0.45 else (rng.uniform(0.28, 0.44) if u < 0.86 else rng.uniform(0.45, 0.62))
        if on_path((x, y), r + 0.2) or not P.free(x, y, r + 0.1):
            continue
        gx, gy = int(x // CELL), int(y // CELL)
        if any((x - px) ** 2 + (y - py) ** 2 < (r + pr + 0.08) ** 2 for i in (gx - 1, gx, gx + 1)
               for j in (gy - 1, gy, gy + 1) for px, py, pr in grid.get((i, j), ())):
            continue
        pumps.append((x, y, r))
        grid.setdefault((gx, gy), []).append((x, y, r))
    cands = [i for i, (x, y, r) in enumerate(pumps) if 0.27 <= r < 0.7]
    weights = [1.6 if pumps[i][1] > -90.0 else 1.0 for i in cands]
    jacks = set()
    while len(jacks) < min(80, len(cands)):
        jacks.add(rng.choices(cands, weights=weights)[0])
    mats = ("plastic_orange", "canvas_yellow", "bone", "dino_green")
    keys = ("fire", "fire", "fire", "amber", "amber", "orange", "green")
    lit_pos = []
    for i, (x, y, r) in enumerate(pumps):
        c = (x, y, Z0)
        if i in jacks:
            tx, ty = rng.choice(FACE_TARGETS)
            yaw = math.atan2(ty - y, tx - x) + rng.uniform(-0.35, 0.35)
            gd = Gourd(c, r, 2 * r * rng.uniform(0.7, 0.8), 8, yaw, lobe=0.1, rings=((0.2, 0.86), (0.5, 1.0), (0.8, 0.84)),
                       top=0.93)
            gd.build(P.m("plastic_orange"))
            jack_face(P, gd, rng.choice(("classic", "classic", "angry", "round")), rng.choice(keys))
            lit_pos.append((x, y))
        else:
            segs = 6 if r < 0.27 else (10 if r < 0.45 else 12)
            gd = Gourd(c, r, 2 * r * rng.uniform(0.62, 0.8), segs, rng.uniform(0, TAU), lobe=0.13 if segs > 6 else 0.06,
                       tilt=(rng.uniform(-0.12, 0.12), rng.uniform(-0.12, 0.12)))
            gd.build(P.m(rng.choices(mats, weights=(78, 10, 8, 4))[0]))
        tp = gd.top_point()                                                         # stem: a black sliver (no texels)
        paint(P.glow, tube(P.glow, [tp - UP * 0.02, tp + Vector((rng.uniform(-0.05, 0.05) * r, rng.uniform(-0.05, 0.05) * r,
                                                                 rng.uniform(0.22, 0.38) * r))], 0.11 * r, segs=3, r1=0.0),
              "black")
        P.block((x, y), r)
    best = []                                                                       # two warm glows where they bunch
    for _ in range(2):
        cand = [p for p in lit_pos if all((p[0] - b[0]) ** 2 + (p[1] - b[1]) ** 2 > 81 for b in best)]
        best.append(max(cand, key=lambda p: sum((p[0] - q[0]) ** 2 + (p[1] - q[1]) ** 2 < 9 for q in lit_pos)))
    for i, (x, y) in enumerate(best):
        P.add_light(f"PumpGlow{i}", "POINT", (x, y, Z0 + 0.75), ORANGE, 180, size=0.4)
    green = P.m("dino_green")
    for k in range(30):                                                             # vines and leaves
        x, y, r = pumps[rng.randrange(len(pumps))]
        a = rng.uniform(0, TAU)
        p = Vector((x + math.cos(a) * r, y + math.sin(a) * r, Z0 + 0.035))
        pts = [p]
        for _ in range(5):
            a += rng.uniform(-0.8, 0.8)
            q = pts[-1] + Vector((math.cos(a), math.sin(a), 0.0)) * rng.uniform(0.35, 0.6)
            if on_path(q, 0.45) or not (41.0 < q.x < 72.4 and -97.0 < q.y < -78.7):
                break
            pts.append(q)
        if len(pts) < 3:
            continue
        tube(green, pts, 0.022, segs=3)
        for q in pts:
            P.block((q.x, q.y), 0.22)                                               # nobody stands on the vines
        for q in pts[1::2]:
            lr = rng.uniform(0.16, 0.26)
            la = rng.uniform(0, TAU)
            cen = green.verts.new(q + UP * 0.04)
            ring = [green.verts.new(q + Vector((math.cos(la + TAU * j / 5) * lr, math.sin(la + TAU * j / 5) * lr, 0.0)))
                    for j in range(5)]
            for j in range(5):
                green.faces.new((cen, ring[j], ring[(j + 1) % 5]))
    P.rect([(40.6, -97.6), (72.8, -78.4)], pad=0.2)
    return len(pumps), len(jacks), tries


def walkers(P, rng):
    """Visitors on the paths, alone or in pairs, and a few among the pumpkins."""
    for a, b, ts in ((PATHS[0][0], PATHS[0][1], (0.08, 0.27, 0.45, 0.62, 0.8)), (PATHS[1][0], PATHS[1][1], (0.2, 0.5, 0.8)),
                     (PATHS[2][0], PATHS[2][1], (0.3, 0.7)), (PATHS[3][0], PATHS[3][1], (0.45,))):
        d = flat((b[0] - a[0], b[1] - a[1]))
        n = Vector((-d.y, d.x, 0.0))
        for t in ts:
            p = Vector((a[0], a[1], 0.0)).lerp(Vector((b[0], b[1], 0.0)), t)
            face = d if rng.random() < 0.6 else -d
            P.person(p.x + n.x * 0.35, p.y + n.y * 0.35, face, rng.choice(("down", "hips", "one")))
            if rng.random() < 0.6:
                P.person(p.x - n.x * 0.45, p.y - n.y * 0.45, face, rng.choice(("down", "hips")))
    n, tries = 0, 0
    while n < 4 and tries < 300:
        tries += 1
        x, y = rng.uniform(42.0, 71.0), rng.uniform(-96.0, -80.0)
        if P.person(x, y, toward((x, y), PK), rng.choice(("down", "hips")), min_d=1.2):
            n += 1


def build(rng):
    P = Parts()
    P.run("king", pumpkin_king, rng)
    P.run("hay", hay, rng)
    P.run("surroundings", surroundings, rng)
    P.run("corn", corn, rng)
    P.run("patch", patch, rng)
    placed, wanted = P.place_wants()
    P.run("walkers", walkers, rng)
    print("[HWPUMPKINS] tris/lights/people: " + ", ".join(f"{k} {v[0]}/{v[1]}/{v[2]}" for k, v in P.tally.items())
          + f"; wanted people placed {placed}/{wanted}; total tris {P.count()}, lights {len(P.lights)}, "
            f"people {len(P.people)}", flush=True)
    return P.result()
