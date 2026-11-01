"""GRAVEYARD SHIFT grounds module HW_CARNIVAL: the haunted carnival, back left of the field (CONTRACT.md, kit frame).

  Carousel (-56, -109)             13 m haunted carousel: 24-sided turntable, red/black striped canopy with a frozen bulb
                                   chase on its rounding board and bulb rafters, a skull finial, 14 skeletal bone horses
                                   on poles (glowing eyes), mirror panels on the centre column, warm light inside.
  House of Horrors (-75, -100.5)   14 m spooky-mansion facade turned to the field: turrets, a gable, a giant bone skull
                                   whose mouth is the dark entrance (a tunnel ending in a dim green glow), the marquee
                                   sign HOUSE OF / HORRORS framed in bulbs, bulb outlines, an EXIT door; colour uplights.
  Midway                           ticket booth (TICKETS), fortune-teller wagon (FORTUNES, crystal ball), strongman tower
                                   (lit scale frozen at 14/16, bell, STRONGMAN), POPCORN and CANDY wagons; festoons from
                                   the carousel finial to 6 poles and between the poles (warm, orange, purple bulbs).
  People                           ~60: queues for the carousel and the house, at the stalls and the strongman, strolling.
Everything faces the main field (0, -30). Static; deterministic with the rng passed to build().
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "grounds"))
from kit import *  # noqa: E402,F401,F403

NAME = "carnival"
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
                "exclude": self.exclude, "people": self.people}


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


# ------------------------------------------------------------------ the carnival
CAR = Vector((-56.0, -109.0, Z0))         # carousel centre
HOUSE = (-75.0, -100.5)                   # House of Horrors: facade centre
FIELD = (0.0, -30.0)                      # the main field: fronts turn toward it
WARM = (1.0, 0.72, 0.38)
ORANGE, PURPLE, GREEN = (1.0, 0.40, 0.05), (0.55, 0.15, 1.0), (0.15, 1.0, 0.25)


def house_frame():
    return Frame(HOUSE, toward(HOUSE, (0.0, -25.0)))


def skeleton_horse(P, p, T, s, eye_key, phase):
    """A bone horse skeleton, saddle point p, galloping along T (horizontal unit), scale s."""
    S = Vector((-T.y, T.x, 0.0))
    yw = math.atan2(T.y, T.x)

    def L(x, y, z):
        return p + T * (x * s) + S * (y * s) + UP * (z * s)
    bone = P.m("bone")
    tube(bone, [L(-0.75, 0, 0.0), L(-0.3, 0, 0.08), L(0.2, 0, 0.08), L(0.5, 0, 0.15)], 0.06 * s, segs=4)     # spine
    tube(bone, [L(0.48, 0, 0.13), L(0.7, 0, 0.36), L(0.85, 0, 0.53)], 0.075 * s, segs=4, r1=0.055 * s)       # neck
    tube(bone, [L(0.82, 0, 0.6), L(0.99, 0, 0.53), L(1.26, 0, 0.29)], 0.13 * s, segs=5, r1=0.065 * s)         # skull
    tube(bone, [L(0.9, 0, 0.46), L(1.2, 0, 0.25)], 0.075 * s, segs=4, r1=0.045 * s)                          # jaw
    for y in (-1, 1):
        tube(bone, [L(0.86, 0.05 * y, 0.66), L(0.83, 0.08 * y, 0.81)], 0.035 * s, segs=3, r1=0.0)               # ears
        paint(P.glow, octa(P.glow, L(0.97, 0.11 * y, 0.57), 0.035 * s), eye_key)
    for x, rr in ((-0.25, 0.17), (-0.05, 0.2), (0.15, 0.21), (0.35, 0.18)):                                   # ribs
        zc = 0.06 - rr * 1.1
        tube(bone, [L(x, rr * math.sin(TAU * k / 6), zc + rr * 1.1 * math.cos(TAU * k / 6)) for k in range(7)],
             0.025 * s, segs=3)
    box(bone, L(-0.62, 0, -0.04), (0.28 * s, 0.32 * s, 0.16 * s), yaw=yw)                                     # pelvis
    gal = 0.5 + 0.5 * math.sin(phase)
    legs = (((0.4, 0.11, -0.15), (0.6 + 0.06 * gal, 0.11, -0.42), (0.48 + 0.1 * gal, 0.11, -0.64 - 0.1 * gal)),
            ((0.4, -0.11, -0.15), (0.7, -0.11, -0.45), (0.92, -0.11, -0.66)),
            ((-0.62, 0.11, -0.1), (-0.8, 0.11, -0.5), (-0.66 - 0.06 * gal, 0.11, -0.88)),
            ((-0.62, -0.11, -0.1), (-0.88, -0.11, -0.46), (-1.02, -0.11, -0.8)))
    for leg in legs:
        tube(bone, [L(*q) for q in leg], 0.045 * s, segs=3, r1=0.03 * s)
    tube(bone, [L(-0.75, 0, 0.0), L(-0.95, 0, -0.1), L(-1.05, 0, -0.45)], 0.035 * s, segs=3, r1=0.012 * s)   # tail
    cloth = P.m("canvas_red")
    box(cloth, L(0.0, 0, 0.16), (0.38 * s, 0.34 * s, 0.07 * s), yaw=yw)                                       # saddle
    for y in (-1, 1):
        box(cloth, L(0.0, 0.19 * y, 0.02), (0.36 * s, 0.02 * s, 0.26 * s), yaw=yw)


def carousel(P, rng):
    c = CAR
    z = c.z
    NS, R_DECK, H_DECK = 24, 6.6, 0.75
    R_EAVE, Z_EAVE, Z_APEX, Z_BAND = 7.25, 5.7, 9.3, 4.95
    wood, black, red, g = P.m("wood_dark"), P.m("canvas_black"), P.m("canvas_red"), P.glow
    fz = toward(c, FIELD)
    side = Vector((fz.y, -fz.x, 0.0))
    vprism(P.m("metal_dark"), c, z, z + 0.3, 7.05, 7.05, NS, cap0=False)           # step ring
    vprism(wood, c, z + 0.3, z + H_DECK, R_DECK, R_DECK, NS, cap0=False)            # turntable
    vprism(black, c, z + H_DECK, z + 8.3, 1.25, 1.25, 8, cap0=False)               # centre column, mirror panels
    ap = 1.25 * math.cos(math.pi / 8) + 0.025
    for k in range(8):
        a = TAU * (k + 0.5) / 8
        n = Vector((math.cos(a), math.sin(a), 0.0))
        t = Vector((-n.y, n.x, 0.0))
        p = Vector((c.x, c.y, 0.0)) + n * ap
        for z0p, z1p, key in ((1.55, 3.15, "ember" if k % 2 else "purple_dim"),
                              (3.4, 4.65, "purple_dim" if k % 2 else "ember")):
            paint(g, quad(g, p - t * 0.4 + UP * (z + z0p), p + t * 0.4 + UP * (z + z0p), p + t * 0.4 + UP * (z + z1p),
                          p - t * 0.4 + UP * (z + z1p)), key)

    def rim(r, a, zz):
        return Vector((c.x + r * math.cos(a), c.y + r * math.sin(a), z + zz))
    apex = Vector((c.x, c.y, z + Z_APEX))
    for k in range(NS):                                                             # canopy: red/black stripes
        a0, a1 = TAU * k / NS, TAU * (k + 1) / NS
        bm = red if k % 2 == 0 else black
        bm.faces.new((bm.verts.new(rim(R_EAVE, a0, Z_EAVE)), bm.verts.new(rim(R_EAVE, a1, Z_EAVE)), bm.verts.new(apex)))
        wood.faces.new((wood.verts.new(apex - UP * 0.15), wood.verts.new(rim(R_EAVE - 0.03, a1, Z_EAVE - 0.05)),
                        wood.verts.new(rim(R_EAVE - 0.03, a0, Z_EAVE - 0.05))))     # its underside (the ceiling)
        black.faces.new([black.verts.new(q) for q in (rim(R_EAVE, a0, Z_BAND), rim(R_EAVE, a1, Z_BAND),
                                                      rim(R_EAVE, a1, Z_EAVE), rim(R_EAVE, a0, Z_EAVE))])   # rounding board
        wood.faces.new([wood.verts.new(q) for q in (rim(R_EAVE - 0.06, a1, Z_BAND), rim(R_EAVE - 0.06, a0, Z_BAND),
                                                    rim(R_EAVE - 0.06, a0, Z_EAVE), rim(R_EAVE - 0.06, a1, Z_EAVE))])
        sc = red if k % 2 == 0 else P.m("plastic_orange")                           # scallops, both sides
        mid = rim(R_EAVE * math.cos(math.pi / NS), (a0 + a1) / 2, Z_BAND - 0.42)
        sc.faces.new((sc.verts.new(rim(R_EAVE, a0, Z_BAND)), sc.verts.new(mid), sc.verts.new(rim(R_EAVE, a1, Z_BAND))))
        sc.faces.new((sc.verts.new(rim(R_EAVE - 0.015, a1, Z_BAND)), sc.verts.new(mid - flat(mid - c) * 0.015),
                      sc.verts.new(rim(R_EAVE - 0.015, a0, Z_BAND))))
    for i in range(48):                                                             # frozen chase on the board
        a = TAU * (i + 0.5) / 48
        paint(g, octa(g, rim(R_EAVE + 0.12, a, (Z_BAND + Z_EAVE) / 2), 0.12), ("bulb_warm", "bulb_warm", "ember")[i % 3])
    zc = (Z_EAVE - 0.05) + (Z_APEX - Z_EAVE - 0.1) * (1 - 5.4 / (R_EAVE - 0.03)) - 0.1
    for i in range(24):                                                             # ceiling lights
        paint(g, octa(g, rim(5.4, TAU * (i + 0.25) / 24, zc), 0.08), "bulb_warm")
    for k in range(0, NS, 2):                                                       # bulb rafters on the stripes' seams
        a = TAU * k / NS
        rad = Vector((math.cos(a), math.sin(a), 0.0))
        nrm = (rad * (Z_APEX - Z_EAVE) + UP * R_EAVE).normalized()
        for j in range(9):
            s = (j + 0.6) / 9.6
            q = Vector((c.x, c.y, z + Z_EAVE)) + rad * (R_EAVE * (1 - s)) + UP * ((Z_APEX - Z_EAVE) * s) + nrm * 0.11
            paint(g, octa(g, q, 0.1), "amber" if j % 3 == 2 else "bulb_warm")
    for k in range(12):                                                             # sweeps under the ceiling
        a = TAU * (k + 0.5) / 12
        rad = Vector((math.cos(a), math.sin(a), 0.0))
        box(wood, Vector((c.x, c.y, z + Z_EAVE - 0.14)) + rad * ((1.25 + R_EAVE - 0.08) / 2), (R_EAVE - 1.35, 0.12, 0.2),
            yaw=a)
    cyl(P.m("metal_dark"), apex, apex + UP * 1.1, 0.07, segs=6)                     # finial: a skull on a spike
    sk = apex + UP * 1.55
    ball(P.m("bone"), sk, 0.42, 8, 5, scale=(1.0, 1.0, 1.1))
    for s in (-1, 1):
        paint(g, octa(g, sk + fz * 0.37 + side * (0.15 * s) + UP * 0.06, 0.08), "red")
    eyes = ("red", "green", "red", "amber", "green", "red", "purple")
    i = 0
    for rr, n, ph in ((5.35, 8, TAU / 32), (3.45, 6, 0.27)):                         # poles and skeletal horses
        for k in range(n):
            a = ph + TAU * k / n
            rad = Vector((math.cos(a), math.sin(a), 0.0))
            base = Vector((c.x, c.y, z + H_DECK)) + rad * rr
            ztop = z + Z_EAVE - 0.05 + (Z_APEX - Z_EAVE - 0.1) * (1 - rr / (R_EAVE - 0.03)) - 0.05
            cyl(P.m("metal_alu"), base, Vector((base.x, base.y, ztop)), 0.04, segs=5, cap=False)
            skeleton_horse(P, base + UP * (1.2 + 0.25 * math.sin(2.1 * i + 0.4)), Vector((-rad.y, rad.x, 0.0)), 0.8,
                           eyes[i % len(eyes)], 1.7 * i)
            i += 1
    for s, nm in ((1, "CarnCarouselInA"), (-1, "CarnCarouselInB")):                # warm light inside, two colour washes
        P.add_light(nm, "POINT", Vector((c.x, c.y, z + 5.0)) + fz * (2.6 * s), WARM, 450, size=0.3)
    P.add_light("CarnCarouselAmber", "SPOT", c + fz * 12.5 + side * 5.0 + UP * 0.4, (1.0, 0.55, 0.15), 6000,
                target=c + UP * 6.8, spot_deg=42, size=0.3)
    P.add_light("CarnCarouselPurple", "SPOT", c + fz * 10.0 - side * 9.5 + UP * 0.4, PURPLE, 6500,
                target=c + UP * 6.3, spot_deg=42, size=0.3)
    P.block(c, 7.1)
    P.rect([(c.x - 7.3, c.y - 7.3), (c.x + 7.3, c.y + 7.3)], pad=0.5)
    poses = ("down", "hips", "down", "one", "up", "down", "hips", "down")
    for k in range(8):                                                              # the queue at the entrance
        P.want(c + fz * (7.9 + 0.8 * k) + side * (1.7 + 0.3 * math.sin(k * 1.3)), -fz, poses[k])
    for k in range(10):                                                             # watching the horses go round
        a = math.atan2(fz.y, fz.x) + 0.55 + (TAU - 1.1) * (k + rng.uniform(0.2, 0.8)) / 10
        p = c + Vector((math.cos(a), math.sin(a), 0.0)) * rng.uniform(7.85, 8.6)
        P.want(p, c - p, rng.choice(("down", "hips", "up", "one")))


def house_of_horrors(P, rng):
    H = house_frame()
    dark, black, bone, g = P.m("wood_dark"), P.m("canvas_black"), P.m("bone"), P.glow
    W2, DP, HB, MW, MH = 7.0, 5.0, 7.6, 1.9, 3.5            # half width, shed depth/height, mouth half width/height
    v = [dark.verts.new(H.at(l, f, zz)) for l in (-6.9, 6.9) for f in (-DP, 0.0) for zz in (0.0, HB)]
    shed = [dark.faces.new((v[0], v[4], v[5], v[1])), dark.faces.new((v[0], v[1], v[3], v[2])),   # open at the front
            dark.faces.new((v[4], v[6], v[7], v[5])), dark.faces.new((v[1], v[5], v[7], v[3]))]
    orient_out(shed, H.at(0, -DP / 2, HB / 2))
    w = [dark.verts.new(H.at(l, f, zz)) for l in (-MW, MW) for f in (-3.4, 0.0) for zz in (0.0, MH)]
    tunnel = [dark.faces.new((w[0], w[1], w[3], w[2])), dark.faces.new((w[4], w[6], w[7], w[5])),
              dark.faces.new((w[1], w[5], w[7], w[3]))]
    for f in orient_out(tunnel, H.at(0, -1.7, MH / 2)):
        f.normal_flip()                                     # the tunnel behind the mouth, seen from inside
    front_quad(P, H, 0.0, -3.39, MH / 2, 2 * MW, MH, "black")                     # the dark back of the tunnel
    front_quad(P, H, 0.0, -3.37, 1.15, 1.2, 2.3, "green_dim")                     # ... and a dim green doorway in it
    SIL =[(-W2, 0.0), (-MW, 0.0), (-MW, MH), (MW, MH), (MW, 0.0), (W2, 0.0), (W2, 10.6), (5.3, 10.6), (5.3, 9.1),
           (4.2, 9.1), (0.0, 14.2), (-4.2, 9.1), (-5.3, 9.1), (-5.3, 10.6), (-W2, 10.6)]
    extrude(dark, H, SIL, 0.0, 0.35)                        # the facade
    for s in (-1, 1):                                       # turrets with pointed roofs
        H.box(dark, 6.15 * s, -0.52, 5.3, (1.7, 1.7, 10.6))
        vprism(dark, H.at(6.15 * s, -0.52), Z0 + 10.6, Z0 + 13.9, 1.0 * math.sqrt(2), 0.0, 4,
               phase=H.yaw + math.pi / 4, cap0=False)
        cone(dark, H.at(6.15 * s, -0.52, 13.85), H.at(6.15 * s, -0.52, 14.8), 0.06, segs=4)
    front_disc(P, H, 0.0, 0.37, 12.85, 0.55, "purple")     # gable rose
    # the skull: cranium dome, sockets with red eyes, nose, upper jaw with teeth, jaw bones, lower teeth
    SC, RL, RF, RZ = (0.0, 0.35, 6.2), 3.2, 1.5, 2.3
    pole = bone.verts.new(H.at(SC[0], SC[1] + RF, SC[2]))
    rings = [[bone.verts.new(H.at(SC[0] + RL * math.sin(ph) * math.cos(th), SC[1] + RF * math.cos(ph),
                                  SC[2] + RZ * math.sin(ph) * math.sin(th)))
              for th in [TAU * k / 14 for k in range(14)]] for ph in [math.pi / 2 * i / 5 for i in range(1, 6)]]
    dome = [bone.faces.new((pole, rings[0][k], rings[0][(k + 1) % 14])) for k in range(14)]
    for a, b in zip(rings, rings[1:]):
        dome += [bone.faces.new((a[k], b[k], b[(k + 1) % 14], a[(k + 1) % 14])) for k in range(14)]
    orient_out(dome, H.at(*SC))

    def on_skull(l, zz, lift):
        q = 1 - ((l - SC[0]) / RL) ** 2 - ((zz - SC[2]) / RZ) ** 2
        return H.at(l, SC[1] + RF * math.sqrt(max(q, 0.0)) + lift, zz)

    def blob(pts, lift, key):
        cx, cz = sum(p[0] for p in pts) / len(pts), sum(p[1] for p in pts) / len(pts)
        cen = g.verts.new(on_skull(cx, cz, lift))
        ring = [g.verts.new(on_skull(l, zz, lift)) for l, zz in pts]
        faces = [g.faces.new((cen, ring[k], ring[(k + 1) % len(ring)])) for k in range(len(ring))]
        for f in faces:
            f.normal_update()
            if f.normal.dot(H.f) < 0:
                f.normal_flip()
        return paint(g, faces, key)
    socket = [(-0.75, 0.45), (-0.9, 0.0), (-0.6, -0.6), (0.0, -0.8), (0.55, -0.55), (0.85, -0.1), (0.65, 0.1),
              (0.0, 0.42)]                                  # (toward the nose, up): the inner brow dips (an angry look)
    for s in (-1, 1):
        cl = 1.25 * s
        blob([(cl - s * u, 6.4 + v) for u, v in socket], 0.03, "black")
        blob([(cl - s * (0.12 + du), 6.25 + dv) for du, dv in ((0.2, 0), (0, 0.27), (-0.2, 0), (0, -0.27))], 0.07,
             "red")
    blob([(-0.36, 5.3), (0.36, 5.3), (0.0, 4.55)], 0.03, "black")                     # nose
    for s in (-1, 1):
        ball(bone, H.at(2.25 * s, 0.6, 4.55), 0.55, 8, 4)                           # cheekbones
        tube(bone, [H.at(2.3 * s, 0.85, 4.2), H.at(2.55 * s, 0.95, 2.4), H.at(2.2 * s, 1.0, 0.0)], 0.3, segs=6,
             r1=0.24)                                                               # jaw bones
    extrude(bone, H, [(-1.85, 3.5), (1.85, 3.5), (2.05, 4.35), (-2.05, 4.35)], 0.35, 1.2)   # upper jaw
    for k in range(7):
        H.box(bone, -1.6 + 0.533 * k, 1.0, 3.19, (0.42, 0.28, 0.68))                # upper teeth
    for k in range(5):
        cone(bone, H.at(-1.4 + 0.7 * k, 1.0, 0.0), H.at(-1.4 + 0.7 * k, 1.0, 0.5), 0.17, segs=4)   # lower teeth
    H.box(black, 0.0, 0.62, 10.35, (10.4, 0.18, 3.1))                               # marquee sign
    board_text(P, H, "HOUSE OF", 0.13, 0.0, 0.73, 10.82, "amber")
    board_text(P, H, "HORRORS", 0.22, 0.0, 0.73, 9.05, "red")
    per = [(5.35, 8.62), (-5.35, 8.62), (-5.35, 12.08), (5.35, 12.08), (5.35, 8.62)]
    i = 0
    for (l0, z0), (l1, z1) in zip(per, per[1:]):                                    # bulbs around the sign
        n = int(round(math.hypot(l1 - l0, z1 - z0) / 0.48))
        for k in range(n):
            t = k / n
            paint(g, octa(g, H.at(l0 + (l1 - l0) * t, 0.78, z0 + (z1 - z0) * t), 0.12),
                  ("bulb_warm", "bulb_warm", "bulb_warm", "ember")[i % 4])
            i += 1
    outline = []
    for s in (-1, 1):
        outline += [((W2 + 0.12) * s, 0.42, 0.4), ((W2 + 0.12) * s, 0.42, 10.7)]        # turret edges
        outline += [(7.15 * s, 0.5, 10.75), (6.15 * s, -0.52, 13.95)]                  # turret roof edges
        outline += [(5.15 * s, 0.5, 10.75), (6.15 * s, -0.52, 13.95)]
        outline += [(1.81 * s, 0.42, 12.05), (0.0, 0.42, 14.3)]                        # the gable's tip
    i = 0
    for a, b in zip(outline[0::2], outline[1::2]):
        n = int(round((Vector(b) - Vector(a)).length / 0.6))
        for k in range(n + 1):
            paint(g, octa(g, H.at(*(Vector(a).lerp(Vector(b), k / n))), 0.11), ("orange", "purple")[i % 2])
            i += 1
    front_quad(P, H, 6.15, 0.37, 1.1, 1.1, 2.2, "black")                             # EXIT door on the near turret
    board_text(P, H, "EXIT", 0.055, 6.15, 0.37, 2.4, "red")
    P.add_light("CarnHouseUpL", "SPOT", H.at(-3.2, 8.5, 0.3), PURPLE, 2600, target=H.at(-2.2, 0.3, 7.5), spot_deg=55,
                size=0.3)
    P.add_light("CarnHouseUpR", "SPOT", H.at(3.2, 8.5, 0.3), ORANGE, 2000, target=H.at(2.2, 0.3, 7.5), spot_deg=55,
                size=0.3)
    P.add_light("CarnHouseMouth", "POINT", H.at(0.0, -2.0, 1.8), GREEN, 150, size=0.3)
    P.block_box(H.at(0.0, -2.35), W2 + 0.2, 2.75, H.yaw)
    P.block_box(H.at(0.0, 0.85), 3.4, 0.5, H.yaw)
    P.rect([H.at(l, f) for l in (-W2 - 0.2, W2 + 0.2) for f in (-DP - 0.1, 1.4)], pad=0.5)
    for k in range(11):                                                             # the queue into the mouth
        row, col = divmod(k, 6)
        f = 1.75 + 0.85 * (col if row == 0 else 5 - col)
        P.want(H.at(-0.55 + 1.2 * row + rng.uniform(-0.12, 0.12), f), -H.f, ("down", "hips", "up", "down")[k % 4])
    for k in range(2):                                                              # out of the exit
        P.want(H.at(6.0 + 0.5 * k, 1.4 + 0.9 * k), H.f + H.r * 0.4, "hips" if k else "down")


def ticket_booth(P, rng):
    pos = (-43.0, -104.0)
    B = Frame(pos, toward(pos, FIELD))
    dark, g = P.m("wood_dark"), P.glow
    B.box(P.m("canvas_red"), 0, 0, 1.25, (2.0, 1.8, 2.5))
    vprism(dark, B.at(0, 0), Z0 + 2.5, Z0 + 3.45, 1.3 * math.sqrt(2), 0.0, 4, phase=B.yaw + math.pi / 4)
    front_quad(P, B, 0, 0.92, 1.5, 1.2, 0.8, "warm_dim")
    B.box(dark, 0, 1.05, 1.08, (1.5, 0.32, 0.06))
    B.box(P.m("canvas_black"), 0, 1.36, 2.81, (3.1, 0.1, 0.62))
    board_text(P, B, "TICKETS", 0.062, 0.0, 1.43, 2.6, "amber")
    for sl, sf in ((1, 1), (-1, 1), (-1, -1), (1, -1)):                              # bulbs along the eaves
        a, b = B.at(1.36 * sl, 1.36 * sf, 2.44), B.at(-1.36 * sf, 1.36 * sl, 2.44)
        for k in range(6):
            paint(g, octa(g, a.lerp(b, (k + 0.5) / 6), 0.08), "bulb_warm")
    P.add_light("CarnBooth", "POINT", B.at(0, 2.3, 2.3), WARM, 160, size=0.3)
    P.block_box(B.at(0, 0.1), 1.35, 1.2, B.yaw)
    P.rect([B.at(l, f) for l in (-1.6, 1.6) for f in (-1.4, 1.5)], pad=0.3)
    for k in range(3):
        P.want(B.at(0.25 * (k % 2), 1.85 + 0.8 * k), -B.f, ("down", "hips", "down")[k])


def fortune_wagon(P, rng):
    pos = (-44.0, -117.5)
    W = Frame(pos, toward(pos, FIELD))
    dark, g = P.m("wood_dark"), P.glow
    W.box(P.m("canvas_red"), 0, 0, 1.75, (4.4, 1.9, 1.8))                          # body z 0.85..2.65
    W.box(P.m("wood"), 0, 0, 0.8, (4.6, 2.0, 0.12))                                # chassis
    prof = [(1.12 * math.cos(math.pi * k / 6), 2.62 + 0.9 * math.sin(math.pi * k / 6)) for k in range(7)]
    A = [dark.verts.new(W.at(-2.45, f, zz)) for f, zz in prof]                     # barrel roof
    Bv = [dark.verts.new(W.at(2.45, f, zz)) for f, zz in prof]
    roof = [dark.faces.new((A[k], Bv[k], Bv[k + 1], A[k + 1])) for k in range(6)]
    roof += [dark.faces.new(A), dark.faces.new(list(reversed(Bv)))]
    orient_out(roof, W.at(0, 0, 2.9))
    for l in (-1.45, 1.45):
        for f in (-1.06, 1.06):
            cyl(dark, W.at(l, f - 0.06, 0.58), W.at(l, f + 0.06, 0.58), 0.58, segs=10)
    front_quad(P, W, 1.0, 0.97, 1.7, 0.8, 1.5, "warm_dim")                        # open door, lit inside
    front_quad(P, W, -1.0, 0.97, 1.9, 1.0, 0.65, "purple_dim")                    # window
    W.box(dark, 1.0, 1.25, 0.6, (0.9, 0.35, 0.1))                                   # steps
    W.box(dark, 1.0, 1.55, 0.3, (0.9, 0.35, 0.1))
    W.box(P.m("canvas_black"), 0, 1.06, 3.28, (4.0, 0.08, 0.72))                   # sign on the roof's edge
    board_text(P, W, "FORTUNES", 0.08, 0.0, 1.12, 3.0, "purple")
    cyl(P.m("metal_dark"), W.at(0.35, 0.96, 2.62), W.at(0.35, 1.25, 2.62), 0.02, segs=3)
    paint(g, octa(g, W.at(0.35, 1.25, 2.42), 0.12, rz=0.17), "fire")              # door lantern
    W.box(dark, -1.25, 1.9, 0.4, (0.7, 0.7, 0.8))                                   # table and crystal ball
    paint(g, ball(g, W.at(-1.25, 1.9, 1.0), 0.2, 8, 5), "purple")
    P.add_light("CarnFortuneLamp", "POINT", W.at(0.3, 2.0, 2.3), WARM, 140, size=0.25)
    P.add_light("CarnFortuneBall", "POINT", W.at(-1.25, 2.35, 1.35), PURPLE, 60, size=0.2)
    P.block_box(W.at(0, 0.2), 2.5, 1.35, W.yaw)
    P.block_box(W.at(-1.25, 1.9), 0.4, 0.4, W.yaw)
    P.rect([W.at(l, f) for l in (-2.6, 2.6) for f in (-1.3, 2.4)], pad=0.3)
    for p, pose in ((W.at(-1.25, 2.75), "hips"), (W.at(-0.45, 2.55), "down"), (W.at(1.0, 2.3), "down")):
        P.want(p, W.at(-1.25, 1.9) - p if pose == "hips" else -W.f, pose)


def strongman(P, rng):
    pos = (-40.0, -125.0)
    S = Frame(pos, toward(pos, FIELD))
    dark, g = P.m("wood_dark"), P.glow
    S.box(dark, 0, 0, 0.15, (1.8, 1.8, 0.3))                                        # platform
    S.box(P.m("canvas_red"), 0, 0.45, 0.36, (0.45, 0.45, 0.12))                    # the pad
    S.box(dark, 0, -0.45, 4.55, (0.55, 0.2, 8.5))                                   # tower z 0.3..8.8
    for s in (-1, 1):
        cyl(P.m("metal_dark"), S.at(0.8 * s, -0.8, 0.3), S.at(0.2 * s, -0.5, 3.0), 0.04, segs=4)
    cyl(P.m("metal_dark"), S.at(0, -1.4, 0.0), S.at(0, -0.6, 4.0), 0.04, segs=4)
    keys = ["green"] * 3 + ["lime"] * 3 + ["amber"] * 3 + ["orange"] * 3 + ["red"] * 2 + ["red_dim"] * 2
    for i, key in enumerate(keys):                                                  # the scale, frozen at 14 of 16
        front_quad(P, S, 0.0, -0.33, 1.37 + 0.42 * i, 0.32, 0.34, key)
    S.box(P.m("metal_grey"), 0, -0.3, 1.37 + 0.42 * 13 + 0.26, (0.4, 0.12, 0.1))    # the puck
    cyl(P.m("metal_alu"), S.at(0, -0.45, 8.8), S.at(0, -0.45, 9.25), 0.34, segs=8, r2=0.16)   # bell
    cyl(P.m("metal_dark"), S.at(0, -0.45, 9.25), S.at(0, -0.45, 9.46), 0.05, segs=4, cap=False)
    for k in range(10):
        a = TAU * k / 10
        paint(g, octa(g, S.at(0.5 * math.cos(a), -0.45 + 0.5 * math.sin(a), 8.85), 0.08), ("bulb_warm", "amber")[k % 2])
    S.box(P.m("canvas_black"), 0, -0.45, 9.75, (3.3, 0.1, 0.62))
    board_text(P, S, "STRONGMAN", 0.06, 0.0, -0.38, 9.54, "amber")
    cyl(P.m("wood"), S.at(0.75, 1.25, 0.0), S.at(0.62, 1.0, 0.95), 0.03, segs=4)  # the mallet
    box(P.m("metal_dark"), S.at(0.76, 1.27, 0.08), (0.34, 0.18, 0.16), yaw=S.yaw)
    P.add_light("CarnStrongman", "POINT", S.at(0, 2.0, 2.6), WARM, 150, size=0.3)
    P.block_box(S.at(0, -0.3), 1.0, 1.15, S.yaw)
    P.block(S.at(0.76, 1.27), 0.25)
    P.rect([S.at(l, f) for l in (-1.7, 1.7) for f in (-1.5, 1.0)], pad=0.3)
    P.want(S.at(0, 1.35), -S.f, "one")
    for k, a in enumerate((-0.9, -0.3, 0.45, 1.0)):
        p = S.at(2.4 * math.sin(a), 0.9 + 2.2 * math.cos(a))
        P.want(p, S.at(0, 0.3) - p, ("up", "down", "one", "hips")[k])


def candy_wagon(P, rng, pos, text, text_key, stripes, goods, light_name):
    C = Frame(pos, toward(pos, FIELD))
    dark, g = P.m("wood_dark"), P.glow
    C.box(P.m("wood"), 0, 0, 1.3, (2.8, 1.5, 1.6))                                  # body z 0.5..2.1
    for l in (-1.0, 1.0):
        for f in (-0.8, 0.8):
            cyl(dark, C.at(l, f - 0.05, 0.42), C.at(l, f + 0.05, 0.42), 0.42, segs=8)
    C.box(P.m("canvas_black"), 0, 0.15, 2.85, (3.1, 2.1, 0.1))                      # roof on four posts
    for l in (-1.45, 1.45):
        for f in (-0.85, 1.15):
            cyl(P.m("metal_dark"), C.at(l, f, 2.1), C.at(l, f, 2.8), 0.035, segs=4, cap=False)
    for k in range(6):                                                              # striped awning, both sides
        l0, l1 = -1.55 + 0.5167 * k, -1.55 + 0.5167 * (k + 1)
        bm = P.m(stripes[k % 2])
        q = [C.at(l0, 1.2, 2.8), C.at(l0, 1.85, 2.35), C.at(l1, 1.85, 2.35), C.at(l1, 1.2, 2.8)]
        orient_out([bm.faces.new([bm.verts.new(x) for x in q])], C.at((l0 + l1) / 2, 1.2, 0.0))
        fc = bm.faces.new([bm.verts.new(x - UP * 0.012) for x in reversed(q)])
        fc.normal_update()
        if fc.normal.z > 0:
            fc.normal_flip()
    front_quad(P, C, 0, 0.77, 1.62, 2.0, 0.65, "warm_dim")                         # serving window
    C.box(dark, 0, 0.95, 1.25, (2.2, 0.4, 0.06))                                    # counter
    C.box(P.m("canvas_black"), 0, 0.5, 3.25, (2.8, 0.08, 0.6))
    board_text(P, C, text, 0.065 if len(text) <= 5 else 0.058, 0.0, 0.56, 3.04, text_key)
    if goods == "apples":
        for k in range(6):
            paint(g, octa(g, C.at(-0.8 + 0.32 * k, 0.95, 1.35), 0.065), "red")
    else:
        paint(g, box(g, C.at(0.55, 0.92, 1.52), (0.7, 0.35, 0.45), yaw=C.yaw), "amber")
    P.add_light(light_name, "POINT", C.at(0, 1.75, 2.0), WARM, 130, size=0.25)
    P.block_box(C.at(0, 0.15), 1.65, 1.2, C.yaw)
    P.rect([C.at(l, f) for l in (-1.7, 1.7) for f in (-1.2, 1.9)], pad=0.3)
    for k in range(3):
        P.want(C.at(-0.7 + 0.7 * k, 2.25 + 0.3 * (k % 2)), -C.f, ("down", "hips", "down")[k])


def festoons(P, rng):
    """Poles round the carousel, festoons from its finial to every pole and between the poles, two to the house."""
    c = CAR
    top = Vector((c.x, c.y, Z0 + 9.3 + 1.0))
    poles = []
    for deg in (100, 40, 0, -60, -115, 180):
        a = math.radians(deg)
        p = Vector((c.x + 13.0 * math.cos(a), c.y + 13.0 * math.sin(a), Z0))
        cyl(P.m("metal_dark"), p, p + UP * 5.5, 0.06, segs=4, cap=False)
        paint(P.glow, octa(P.glow, p + UP * 5.62, 0.11), "amber")
        P.block(p, 0.12)
        poles.append(p + UP * 5.4)
    warm, multi = ["bulb_warm"], ["orange", "bulb_warm", "purple", "bulb_warm"]
    for q in poles:
        festoon(P, top, q, 0.5, warm, spacing=0.7, r=0.1)
    for a, b in zip(poles, poles[1:] + poles[:1]):
        festoon(P, a, b, 0.65, multi, spacing=0.8, r=0.1)
    turret = house_frame().at(7.12, 0.45, 9.5)                                      # the near turret's corner
    festoon(P, poles[5], turret, 0.5, multi, spacing=0.8, r=0.1)
    festoon(P, poles[0], turret, 0.7, multi, spacing=0.8, r=0.1)
    for i, (a, b) in enumerate(((poles[0], poles[1]), (poles[2], poles[3]), (poles[4], poles[5]))):
        mid = (a + b) / 2
        P.add_light(f"CarnFill{i}", "POINT", Vector((mid.x, mid.y, Z0 + 4.2)), (1.0, 0.6, 0.25), 300, size=0.4)


def strollers(P, rng):
    """Couples on the midway between the attractions."""
    c = CAR
    n, tries = 0, 0
    while n < 9 and tries < 400:
        tries += 1
        a, r = rng.uniform(0, TAU), rng.uniform(8.8, 16.5)
        p = Vector((c.x + r * math.cos(a), c.y + r * math.sin(a), 0.0))
        ang = rng.uniform(0, TAU)
        q = p + Vector((math.cos(ang), math.sin(ang), 0.0)) * 0.9
        if (p - Vector((-60.0, -110.0, 0.0))).length > 23.0 or not (P.free(p.x, p.y, 0.5) and P.free(q.x, q.y, 0.5)):
            continue
        if P.person(p.x, p.y, q - p, rng.choice(("hips", "down", "one"))):
            P.person(q.x, q.y, p - q, rng.choice(("hips", "down", "up")))
            n += 1


def build(rng):
    P = Parts()
    P.run("carousel", carousel, rng)
    P.run("house", house_of_horrors, rng)
    P.run("booth", ticket_booth, rng)
    P.run("fortune", fortune_wagon, rng)
    P.run("strongman", strongman, rng)
    P.run("popcorn", candy_wagon, rng, tuple(house_frame().at(-6.0, 4.5))[:2], "POPCORN", "amber",
          ("plastic_orange", "canvas_black"), "popcorn", "CarnPopcorn")
    P.run("candy", candy_wagon, rng, (-55.0, -125.5), "CANDY", "purple", ("canvas_red", "canvas_black"), "apples",
          "CarnCandy")
    P.run("festoons", festoons, rng)
    placed, wanted = P.place_wants()
    P.run("strollers", strollers, rng)
    print("[HWCARNIVAL] tris/lights/people: " + ", ".join(f"{k} {v[0]}/{v[1]}/{v[2]}" for k, v in P.tally.items())
          + f"; wanted people placed {placed}/{wanted}; total tris {P.count()}, lights {len(P.lights)}, "
            f"people {len(P.people)}", flush=True)
    return P.result()
