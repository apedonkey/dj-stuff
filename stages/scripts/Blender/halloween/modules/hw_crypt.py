"""GRAVEYARD SHIFT grounds module HW_CRYPT: THE CRYPT second stage and the swamp (CONTRACT.md, kit frame).

  THE CRYPT (60, -128), facing +Y  a stone mausoleum temple as a stage: podium deck, four columns, entablature with a red
                                   THE CRYPT sign on its frieze, a pediment with a winged skull (green eyes) and fire
                                   braziers, a pitched roof; inside, an LED wall with a purple pixel skull (green eyes); a
                                   front truss on two towers with six fixtures and purple beams (four into the sky, two
                                   over the crowd), two speaker stacks with purple strips, fire torches, a sarcophagus DJ
                                   booth, a crowd barrier and an FOH block with the back light.
  Its crowd                        100 people at y -112..-122 facing the stage.
  The swamp (x -34..34, y -97..-135)  a dark water plane (lit, glass_dark) with a mud bank and two mud islands, dead reed
                                   clumps with cattails, seven snags with gnarled arching roots, cypress knees and root
                                   arches, 60 will-o-wisps (green, lime, white) just above the water, a few with halos,
                                   and five green lights where they gather.
Static; deterministic with the rng passed to build().
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "grounds"))
from kit import *  # noqa: E402,F401,F403

NAME = "crypt"
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



# ------------------------------------------------------------------ THE CRYPT and the swamp
CRYPT = (60.0, -128.0)                      # stage centre on the field; it faces +Y (its crowd, the main stage area)
SWAMP_C, SWAMP_R = (0.0, -116.0), (28.0, 14.5)
WARM, AMBER, FIRE = (1.0, 0.72, 0.38), (1.0, 0.55, 0.15), (1.0, 0.45, 0.1)
PURPLE, UV, GREEN = (0.55, 0.15, 1.0), (0.40, 0.10, 1.0), (0.15, 1.0, 0.25)
SKULL = ("....########....", "..############..", ".##############.", "################", "################",
         "###gggg##gggg###", "##ggggg##ggggg##", "##ggggg##ggggg##", "###ggg####ggg###", "#######nn#######",
         ".######nn######.", "..############..", "...#.#.##.#.#...", "...##########...", "....########....")


def crypt_frame():
    return Frame(CRYPT, (0.0, 1.0))


def signed_area(poly):
    return sum(poly[i][0] * poly[(i + 1) % len(poly)][1] - poly[(i + 1) % len(poly)][0] * poly[i][1]
               for i in range(len(poly))) / 2


def flame(P, base, h, r):
    """A static fire: an outer fire cone, an amber core and two side tongues (glow)."""
    g = P.glow
    paint(g, cone(g, base, base + UP * h, r, segs=5), "fire")
    paint(g, cone(g, base + UP * 0.02, base + UP * (h * 0.7), r * 0.55, segs=4), "amber")
    for dx, dy in ((0.6, 0.2), (-0.5, -0.3)):
        paint(g, cone(g, base + Vector((dx * r * 0.6, dy * r * 0.6, 0.0)), base + Vector((dx * r, dy * r, h * 0.62)),
                      r * 0.4, segs=4), "fire")


def crypt(P, rng):
    C = crypt_frame()
    stone, dark, g = P.m("stone"), P.m("metal_dark"), P.glow
    C.box(stone, 0, -0.5, 0.7, (18.0, 8.0, 1.4))                                    # podium: the stage deck
    C.box(stone, 0, -5.0, 5.9, (19.6, 1.0, 11.8))                                   # back wall
    for s in (-1, 1):
        C.box(stone, 9.4 * s, -1.45, 5.9, (0.8, 7.1, 11.8))                         # side walls
    for l in (-7.6, -4.6, 4.6, 7.6):                                               # four columns
        c = C.at(l, 2.6)
        C.box(stone, l, 2.6, 1.575, (1.3, 1.3, 0.35))
        vprism(stone, c, Z0 + 1.75, Z0 + 8.65, 0.5, 0.44, 12, cap0=False, cap1=False)
        vprism(stone, c, Z0 + 8.65, Z0 + 9.0, 0.45, 0.64, 12, cap0=False)
        C.box(stone, l, 2.6, 9.2, (1.4, 1.4, 0.4))
    C.box(stone, 0, 2.6, 9.8, (19.6, 1.6, 0.8))                                     # architrave
    C.box(stone, 0, 2.55, 10.9, (19.4, 1.5, 1.4))                                   # frieze
    C.box(stone, 0, 2.6, 11.78, (20.4, 2.0, 0.36))                                  # cornice
    board_text(P, C, "THE CRYPT", 0.17, 0.0, 3.32, 10.32, "red")
    extrude(stone, C, [(-10.2, 11.96), (10.2, 11.96), (0.0, 15.3)], 1.7, 3.3)        # pediment
    roof = []
    for s in (-1, 1):                                                               # pitched roof behind it
        q = [C.at(10.2 * s, 1.75, 11.96), C.at(10.2 * s, -5.6, 11.96), C.at(0, -5.6, 15.3), C.at(0, 1.75, 15.3)]
        roof.append(dark.faces.new([dark.verts.new(p) for p in q]))
    roof.append(dark.faces.new([dark.verts.new(p) for p in (C.at(-10.2, -5.6, 11.96), C.at(10.2, -5.6, 11.96),
                                                            C.at(0, -5.6, 15.3))]))
    orient_out(roof, C.at(0, -2.0, 11.0))
    ball(P.m("bone"), C.at(0, 3.25, 13.15), 0.72, 10, 6, scale=(1.0, 0.45, 1.05))   # winged skull in the tympanum
    for s in (-1, 1):
        front_disc(P, C, 0.27 * s, 3.58, 13.25, 0.16, "green", n=8)
        wing = [(s * l, z) for l, z in ((0.6, 13.3), (1.4, 13.75), (2.4, 13.95), (3.4, 13.85), (3.0, 13.45),
                                        (3.3, 13.25), (2.7, 12.95), (2.9, 12.7), (2.1, 12.6), (1.2, 12.85))]
        extrude(P.m("bone"), C, wing if signed_area(wing) > 0 else wing[::-1], 3.3, 3.42)
    for i, (l, z) in enumerate(((-9.9, 11.96), (9.9, 11.96), (0.0, 15.3))):         # fire braziers on the corners
        b = C.at(l, 2.6, z)
        vprism(dark, b, b.z, b.z + 0.35, 0.18, 0.12, 6)
        vprism(dark, b, b.z + 0.35, b.z + 0.65, 0.2, 0.5, 8, cap0=False)
        flame(P, b + UP * 0.6, 1.1 if i < 2 else 1.3, 0.36)
    for s, nm in ((-1, "CryptFireL"), (1, "CryptFireR")):
        P.add_light(nm, "POINT", C.at(9.9 * s, 3.3, 13.0), FIRE, 380, size=0.4)
    C.box(P.m("canvas_black"), 0, -4.38, 5.0, (8.4, 0.1, 5.9))                      # LED wall: a purple pixel skull
    cols, rows, cell = 22, 16, 0.35
    for cc in range(cols):
        for rr in range(rows):
            br, bc = rows - 1 - rr, cc - 3
            ch = SKULL[br][bc] if 0 <= br < len(SKULL) and 0 <= bc < len(SKULL[0]) else "."
            if ch == "#":
                key = "purple"
            elif ch == "g":
                key = "green"
            elif ch == "n":
                key = "black"
            else:
                key = "uv" if rng.random() < 0.03 else "black"
            front_quad(P, C, 3.85 - (cc + 0.5) * cell, -4.31, 2.2 + (rr + 0.5) * cell, cell - 0.05, cell - 0.05, key)
    for s in (-1, 1):                                                               # truss towers and the front truss
        truss(dark, C.at(9.3 * s, 4.15, 0.0), C.at(9.3 * s, 4.15, 8.7), size=0.4, step=1.0)
    truss(dark, C.at(-9.5, 4.15, 8.5), C.at(9.5, 4.15, 8.5), size=0.4, step=1.0)
    lens = ("uv", "purple", "white", "white", "purple", "uv")
    for i, l in enumerate((-6.5, -3.9, -1.3, 1.3, 3.9, 6.5)):
        C.box(dark, l, 4.15, 8.18, (0.3, 0.3, 0.16))
        C.box(dark, l, 4.2, 7.82, (0.36, 0.4, 0.44))
        paint(g, box(g, C.at(l, 4.3, 7.58), (0.24, 0.24, 0.05), yaw=C.yaw), lens[i])
    for l, ang in ((-6.5, -0.42), (-3.9, -0.16), (3.9, 0.16), (6.5, 0.42)):         # beams into the sky
        apex = C.at(l, 4.35, 7.5)
        beam_planes(P.beams, apex, C.r * math.sin(ang) + C.f * 0.22 + UP * math.cos(ang), 42.0, 0.25, 4.0,
                    color="purple")
        halo(P.halos, apex, 1.4, color="purple")
    for l, s in ((-1.3, 1), (1.3, -1)):                                             # two crossing over the crowd
        beam_planes(P.beams, C.at(l, 4.35, 7.5), C.r * (0.38 * s) + C.f * 0.9 + UP * 0.48, 24.0, 0.25, 3.0,
                    color="purple")
    for s in (-1, 1):                                                               # speaker stacks
        l = 11.0 * s
        for k in range(2):
            C.box(dark, l, 3.0, 0.5 + 1.0 * k, (1.3, 1.1, 0.98))
        for k in range(4):
            C.box(dark, l, 3.0, 2.28 + 0.56 * k, (1.3, 1.0, 0.54))
        for e in (-1, 1):
            front_quad(P, C, l + 0.6 * e, 3.57, 2.15, 0.06, 4.1, "purple")
        P.block_box(C.at(l, 3.0), 0.7, 0.6, C.yaw)
    for s, nm in ((-1, "CryptTorchL"), (1, "CryptTorchR")):                         # torches on the deck's corners
        b = C.at(8.55 * s, 3.1, 1.4)
        vprism(stone, b, b.z, b.z + 1.8, 0.22, 0.16, 6, cap0=False)
        vprism(dark, b, b.z + 1.8, b.z + 2.05, 0.16, 0.36, 8, cap0=False)
        flame(P, b + UP * 2.0, 0.8, 0.27)
        P.add_light(nm, "POINT", b + UP * 3.1 + C.f * 0.3, FIRE, 220, size=0.3)
    C.box(stone, 0, 1.5, 1.95, (3.2, 1.1, 1.1))                                     # sarcophagus DJ booth
    C.box(stone, 0, 1.5, 2.56, (3.4, 1.25, 0.12))
    paint(g, box(g, C.at(-0.55, 1.35, 2.65), (0.4, 0.28, 0.05), yaw=C.yaw), "white_dim")
    for l, key in ((0.55, "purple_dim"), (1.1, "purple_dim")):
        paint(g, box(g, C.at(l, 1.45, 2.64), (0.42, 0.4, 0.04), yaw=C.yaw), key)
    front_quad(P, C, 0.0, 2.07, 2.0, 2.6, 0.08, "purple")
    grey = P.m("metal_grey")                                                        # crowd barrier
    for k in range(11):
        cyl(grey, C.at(-10.0 + 2.0 * k, 5.6, 0.0), C.at(-10.0 + 2.0 * k, 5.6, 1.1), 0.035, segs=4, cap=False)
    C.box(grey, 0, 5.6, 1.06, (20.1, 0.06, 0.08))
    C.box(grey, 0, 5.6, 0.55, (20.1, 0.04, 0.05))
    C.box(stone, 3.0, 19.2, 0.6, (2.6, 1.6, 1.2))                                   # FOH tomb with the back light
    cyl(dark, C.at(3.0, 18.7, 1.2), C.at(3.0, 18.7, 4.2), 0.06, segs=4, cap=False)
    C.box(dark, 3.0, 18.55, 4.25, (0.3, 0.4, 0.3), pitch=-0.4)
    P.add_light("CryptWashL", "SPOT", C.at(-4.0, 4.4, 8.15), PURPLE, 6000, target=C.at(-3.0, 11.0, 0.0), spot_deg=62,
                size=0.4)
    P.add_light("CryptWashR", "SPOT", C.at(4.0, 4.4, 8.15), UV, 6000, target=C.at(3.0, 11.0, 0.0), spot_deg=62, size=0.4)
    P.add_light("CryptDeck", "SPOT", C.at(0.0, 4.4, 8.15), AMBER, 2200, target=C.at(0.0, 1.0, 1.4), spot_deg=55,
                size=0.3)
    P.add_light("CryptUpL", "SPOT", C.at(-6.0, 4.9, 0.3), PURPLE, 5500, target=C.at(-3.0, 3.0, 11.5), spot_deg=36,
                size=0.3)
    P.add_light("CryptUpR", "SPOT", C.at(6.0, 4.9, 0.3), GREEN, 4500, target=C.at(3.0, 3.0, 11.5), spot_deg=36, size=0.3)
    P.add_light("CryptBack", "SPOT", C.at(3.0, 18.4, 4.15), PURPLE, 2500, target=C.at(0.0, 3.0, 3.0), spot_deg=50,
                size=0.4)
    P.block_box(C.at(0, -1.0), 10.0, 4.6, C.yaw)
    P.block_box(C.at(0, 5.6), 10.3, 0.12, C.yaw)
    P.block_box(C.at(3.0, 19.2), 1.4, 0.9, C.yaw)
    for s in (-1, 1):
        P.block(C.at(9.3 * s, 4.15), 0.35)
    P.rect([C.at(l, f) for l in (-12.0, 12.0) for f in (-5.8, 6.0)], pad=0.3)
    n, tries = 0, 0                                                                 # its crowd, facing the booth
    while n < 100 and tries < 8000:
        tries += 1
        f = 6.3 + 9.5 * rng.random() ** 1.25
        half = 9.0 + 0.4 * (f - 6.0)
        l = rng.uniform(-half, half)
        p = C.at(l, f)
        pose = rng.choices(("up", "one", "down", "hips"), weights=(4, 3, 2, 1))[0]
        if P.person(p.x, p.y, C.at(l * 0.35, 1.5) - p, pose, min_d=0.85):
            n += 1
    P.rect([C.at(l, f) for l in (-13.5, 13.5) for f in (6.0, 20.2)], pad=0.3)


def swamp_edge(th, grow, ph):
    k = 1.0 + 0.08 * math.sin(3 * th + ph[0]) + 0.05 * math.sin(5 * th + ph[1]) + 0.03 * math.sin(7 * th + ph[2])
    return Vector((SWAMP_C[0] + (SWAMP_R[0] * k + grow) * math.cos(th),
                   SWAMP_C[1] + (SWAMP_R[1] * k + grow) * math.sin(th), 0.0)), k


def in_water(x, y, ph, margin=0.0):
    u, v = (x - SWAMP_C[0]) / SWAMP_R[0], (y - SWAMP_C[1]) / SWAMP_R[1]
    th = math.atan2(v, u)
    k = swamp_edge(th, 0.0, ph)[1]
    return math.hypot(u, v) < k - margin / SWAMP_R[1]


def snag(P, rng, base, h, zw):
    """A dead broken trunk standing in the water with stubs, a jagged top and gnarled arching roots."""
    bark = P.m("bark")
    b = Vector(base)
    lean = Vector((rng.uniform(-0.12, 0.12), rng.uniform(-0.12, 0.12), 0.0))
    top = b + lean * h + UP * h
    r0 = 0.06 * h + 0.14
    tube(bark, [b - UP * 0.1, b + (lean * 0.35 + UP * 0.35) * h, b + (lean * 0.7 + UP * 0.7) * h, top], r0, segs=6,
         r1=r0 * 0.5)
    for k in range(3):                                                              # the snapped, jagged top
        a = rng.uniform(0, TAU)
        o = Vector((math.cos(a), math.sin(a), 0.0)) * (r0 * 0.25)
        tube(bark, [top + o - UP * 0.15, top + o * 2.2 + UP * rng.uniform(0.25, 0.75)], r0 * 0.3, segs=4, r1=0.0)
    for k in range(rng.randint(2, 3)):
        at = b.lerp(top, rng.uniform(0.45, 0.85))
        a = rng.uniform(0, TAU)
        d = Vector((math.cos(a), math.sin(a), rng.uniform(0.2, 0.7))).normalized()
        L = rng.uniform(0.8, 1.8)
        tube(bark, [at, at + d * (L * 0.6), at + d * L + Vector((0.0, 0.0, rng.uniform(-0.3, 0.3)))], 0.1, segs=4, r1=0.02)
    nr = rng.randint(5, 7)
    a0 = rng.uniform(0, TAU)
    for k in range(nr):
        a = a0 + TAU * k / nr + rng.uniform(-0.3, 0.3)
        d = Vector((math.cos(a), math.sin(a), 0.0))
        s = b + UP * rng.uniform(0.15, 0.45) + d * (r0 * 0.6)
        L = rng.uniform(1.2, 2.1)
        tube(bark, [s, s + d * (0.3 * L) + UP * 0.22, s + d * (0.65 * L) + UP * 0.1, b + d * L - UP * 0.2], 0.17,
             segs=4, r1=0.06)
    knees = []
    for k in range(rng.randint(3, 6)):
        a, r = rng.uniform(0, TAU), rng.uniform(1.0, 3.2)
        p = Vector((b.x + math.cos(a) * r, b.y + math.sin(a) * r, zw - 0.05))
        tube(bark, [p, p + UP * rng.uniform(0.3, 0.75) + Vector((rng.uniform(-0.08, 0.08), rng.uniform(-0.08, 0.08), 0))],
             rng.uniform(0.09, 0.15), segs=5, r1=0.0)
        knees.append(p)
    return knees


def swamp(P, rng):
    ph = [rng.uniform(0, TAU) for _ in range(3)]
    N = 64
    zw = Z0 + 0.045                                                                 # the water level
    water = P.m("glass_dark")
    cen = water.verts.new((SWAMP_C[0], SWAMP_C[1], zw))
    ring = [water.verts.new(swamp_edge(TAU * i / N, 0.3, ph)[0] + UP * zw) for i in range(N)]
    for i in range(N):
        water.faces.new((cen, ring[i], ring[(i + 1) % N]))
    dirt = P.m("dirt")                                                              # the mud bank around it
    prof = [(0.0, 0.075), (0.65, 0.03), (1.6, -0.06)]
    rows = [[dirt.verts.new(swamp_edge(TAU * i / N, gr, ph)[0] + UP * (Z0 + dz)) for i in range(N)] for gr, dz in prof]
    for a, b in zip(rows, rows[1:]):
        for i in range(N):
            f = dirt.faces.new((a[i], b[i], b[(i + 1) % N], a[(i + 1) % N]))
            f.normal_update()
            if f.normal.z < 0:
                f.normal_flip()
    for ix, iy, ir in ((-12.0, -112.0, 2.4), (9.0, -121.0, 1.8)):                  # two mud islands
        vprism(dirt, (ix, iy), Z0 - 0.02, Z0 + 0.3, ir, ir * 0.55, 10, cap0=False)
    bases = [Vector((-12.0, -112.0, Z0 + 0.3)), Vector((9.0, -121.0, Z0 + 0.3))]
    for th, gr in ((0.35, -3.2), (1.3, -2.6), (2.2, -3.0), (3.4, -3.5), (4.4, -2.8), (5.3, -4.5), (2.8, -6.0),
                   (0.9, -7.5)):
        bases.append(swamp_edge(th, gr, ph)[0] + UP * zw)
    knees = []
    for i, b in enumerate(bases):                                                   # snags with gnarled roots
        knees += snag(P, rng, b, rng.uniform(2.2, 4.8) if i != 3 else 5.6, zw)
    bark = P.m("bark")
    k = 0
    while k < 14:                                                                   # root arches out of the water
        x, y = rng.uniform(-26, 26), rng.uniform(-130, -102)
        if not in_water(x, y, ph, 1.5):
            continue
        a = rng.uniform(0, TAU)
        d = Vector((math.cos(a), math.sin(a), 0.0))
        L, hh = rng.uniform(1.8, 3.2), rng.uniform(0.5, 1.0)
        p0 = Vector((x, y, zw - 0.15))
        tube(bark, [p0 + d * (L * t) + UP * (hh * math.sin(math.pi * t)) for t in (0.0, 0.2, 0.45, 0.7, 1.0)], 0.15,
             segs=4, r1=0.07)
        k += 1
    brown, dark = P.m("dino_brown"), P.m("wood_dark")
    for c in range(78):                                                             # dead reeds: shore and shallows
        th = TAU * (c % 48 + rng.uniform(0.15, 0.85)) / 48
        cc = swamp_edge(th, rng.uniform(-1.6, 0.25) if c < 48 else rng.uniform(-6.5, -2.0), ph)[0]
        for j in range(rng.randint(7, 11)):
            off = Vector((rng.uniform(-0.45, 0.45), rng.uniform(-0.45, 0.45), 0.0))
            h = rng.uniform(0.7, 1.9)
            lean = off * 0.4 + Vector((rng.uniform(-0.1, 0.1), rng.uniform(-0.1, 0.1), 0.0))
            base = cc + off + UP * (Z0 - 0.02)
            top = base + lean * h + UP * h
            mat = brown if rng.random() < 0.6 else dark
            if rng.random() < 0.2:                                                  # snapped and bent over
                knee = base.lerp(top, 0.6)
                dd = lean.normalized() if lean.length > 1e-3 else Vector((1.0, 0.0, 0.0))
                tube(mat, [base, knee, knee + dd * 0.5 - UP * 0.25], 0.025, segs=3, r1=0.0)
            else:
                tube(mat, [base, top], 0.025, segs=3, r1=0.0)
                if rng.random() < 0.3:                                              # a cattail
                    q = base.lerp(top, 0.82)
                    tube(dark, [q, q + (top - base).normalized() * 0.22], 0.04, segs=4)
    g = P.glow
    clusters = [(-18.0, -110.0), (-6.0, -122.0), (5.0, -108.0), (15.0, -116.0), (22.0, -124.0), (-24.0, -121.0)]
    for i, (x, y) in enumerate(clusters[:5]):
        P.add_light(f"SwampWisp{i}", "POINT", (x, y, zw + 1.0), GREEN, 260, size=0.4)
    n, halos = 0, 0
    while n < 60:                                                                   # will-o-wisps
        if n < 48:
            cx, cy = clusters[n % len(clusters)]
            x, y = rng.gauss(cx, 2.2), rng.gauss(cy, 1.6)
        else:
            x, y = rng.uniform(-26, 26), rng.uniform(-130, -102)
        if not in_water(x, y, ph, 1.2):
            continue
        p = Vector((x, y, zw + rng.uniform(0.3, 1.7)))
        r = rng.uniform(0.05, 0.12)
        paint(g, octa(g, p, r), rng.choices(("green", "lime", "bulb_white", "green_dim"), weights=(58, 20, 10, 12))[0])
        if r > 0.1 and halos < 8:
            halo(P.halos, p, 0.9, color="green")
            halos += 1
        n += 1
    P.rect([(SWAMP_C[0] - SWAMP_R[0] * 1.17 - 1.6, SWAMP_C[1] - SWAMP_R[1] * 1.17 - 1.6),
            (SWAMP_C[0] + SWAMP_R[0] * 1.17 + 1.6, SWAMP_C[1] + SWAMP_R[1] * 1.17 + 1.6)], pad=0.0)


def build(rng):
    P = Parts()
    P.run("crypt", crypt, rng)
    P.run("swamp", swamp, rng)
    print("[HWCRYPT] tris/lights/people: " + ", ".join(f"{k} {v[0]}/{v[1]}/{v[2]}" for k, v in P.tally.items())
          + f"; total tris {P.count()}, lights {len(P.lights)}, people {len(P.people)}, beam quads "
            f"{len(P.beams.faces)}, halo quads {len(P.halos.faces)}", flush=True)
    return P.result()
