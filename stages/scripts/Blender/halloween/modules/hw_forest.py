"""GRAVEYARD SHIFT grounds module hw_forest: the dead-tree ring around the venue (Blender 4.5, headless).

Where (kit frame): the flanks beyond the vendor lanes (|x| >= crowd_half(y) + 24 for y -75..+60, up beside and behind
the cathedral) and the back, around the attractions (y -75..-185). Kept clear: the haunted carnival (circle 33 m at
(-60, -110)), the pumpkin patch, the crypt stage and its crowd, the swamp and the open view over it from the crowd,
the searchlights, the giant oaks and the light masts; no trunk stands in the DJ's or the crowd's line of sight to an
attraction (view cones).

What:
  - ~125 bare dead trees from a recursive (L-system style) branching rule, 10..25 m: gnarled oaks (kinked limbs,
    split into 2-3 at every level, drooping twigs), dead conifer snags (whorls of short drooping branches) and broken
    snags. The uplit stands (12 clusters of 3-4 trees at the forest's inner edge) are LIT: trunk and two branch levels
    baked (kit "bark"), their twigs and every other tree are black glow silhouettes (no bake texels), the Dino trick.
  - hanging lanterns (warm, a few witch-green) in the lit trees and along the inner edge, gibbet cages with skeletons
    (two with a green wisp), crows perched on branch tops (black, the nearest with red eyes).
  - lights: one colored uplight per stand (purple / green / orange / red), warm lantern-glow points in the trees with
    the most lanterns, dim green points in the wisp cages.
No crowd keep-outs (nothing stands in the crowd field) and no people.
"""
import math
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "grounds"))
from kit import *  # noqa: E402,F401,F403

NAME = "forest"
BAKE_SIZE = 2048

TAU = 2.0 * math.pi
UP = Vector((0.0, 0.0, 1.0))
Z0 = GROUND_Z
N_TREES = 130
LIT_KEY = "stone"                 # weathered grey dead wood: takes the uplights' colors cleanly

KEEP_C = [  # (x, y, r): no trunk inside
    (-60.0, -110.0, 33.0),                                  # haunted carnival (centre, radius ~27)
    (32.0, -92.0, 12.0), (-32.0, -92.0, 12.0), (31.0, 24.0, 12.0), (-31.0, 24.0, 12.0),   # searchlights
    (39.0, 6.0, 16.0), (-39.0, 6.0, 16.0),                  # the giant oaks (crowns ~10 m around)
    (24.0, -78.0, 6.0), (-24.0, -78.0, 6.0),                # light masts (hw_infrastructure)
]
KEEP_R = [  # (x0, y0, x1, y1)
    (35.0, -107.0, 83.0, -73.0),                            # pumpkin patch (x 38..80, y -76..-104) + 3 m
    (42.0, -142.0, 78.0, -107.0),                           # the crypt stage and its crowd (x 45..75, y -110..-135)
    (-39.0, -140.0, 39.0, -64.0),                           # the swamp (x -37..37, y -93..-137) + the view over it
    (-36.0, 8.0, 36.0, 52.0),                               # cathedral, towers, nave
]
ATTRACTIONS = [  # (x, y, r): kept in view from the DJ and the crowd's middle
    (-60.0, -110.0, 27.0), (59.0, -90.0, 23.0), (60.0, -124.0, 17.0), (0.0, -115.0, 30.0)]
VIEWERS = [Vector((0.0, 0.0, 0.0)), Vector((0.0, -35.0, 0.0))]

CLUSTERS = [  # uplit stands at the inner edge: (x, y, trees, uplight color, glow key of its lens, power W)
    (-56.0, -4.0, 3, (0.55, 0.15, 1.0), "purple", 9000),
    (-69.0, -33.0, 3, (0.25, 1.0, 0.35), "green", 9000),
    (-87.0, -61.0, 3, (1.0, 0.42, 0.08), "orange", 10000),
    (-104.0, -100.0, 3, (0.55, 0.15, 1.0), "purple", 11000),
    (-62.0, -152.0, 3, (0.25, 1.0, 0.35), "green", 11000),
    (-22.0, -151.0, 3, (1.0, 0.42, 0.08), "orange", 11000),
    (24.0, -152.0, 3, (0.55, 0.15, 1.0), "purple", 11000),
    (62.0, -154.0, 3, (1.0, 0.1, 0.05), "red", 11000),
    (99.0, -100.0, 3, (0.25, 1.0, 0.35), "green", 11000),
    (89.0, -63.0, 3, (0.55, 0.15, 1.0), "purple", 10000),
    (71.0, -35.0, 3, (1.0, 0.42, 0.08), "orange", 9000),
    (56.0, -6.0, 3, (0.25, 1.0, 0.35), "green", 9000),
]
OAK_CLEAR = 12.3                  # the lead's rule: forest trunks + crowns >= 12 m from the giant oaks at (+-39, 6)
HARD_R = [  # no branch, lantern or crow inside these (x0, y0, x1, y1): the stated footprints of the other modules
    (38.0, -104.0, 80.0, -76.0),                            # pumpkin patch
    (45.0, -135.0, 75.0, -110.0),                           # the crypt and its crowd
    (-37.0, -137.0, 37.0, -93.0),                           # the swamp
    (-30.0, 10.0, 30.0, 47.0),                              # cathedral
    (21.0, -81.0, 27.0, -75.0), (-27.0, -81.0, -21.0, -75.0),   # light masts
    (28.5, -4.5, 49.5, 16.5), (-49.5, -4.5, -28.5, 16.5),       # the giant oaks' crowns (hw_modlint's set boxes)
]
SEARCH_BEAMS = [  # hw_stage.py searchlights (base on the field, beam from 1 m up): ((x, y), direction)
    ((-32.0, -92.0), (-0.35, -0.25, 1.0)), ((-32.0, -92.0), (0.15, 0.3, 1.0)),
    ((32.0, -92.0), (0.35, -0.25, 1.0)), ((32.0, -92.0), (-0.15, 0.3, 1.0)),
    ((-31.0, 24.0), (-0.3, 0.2, 1.0)), ((-31.0, 24.0), (-0.05, -0.25, 1.0)),
    ((31.0, 24.0), (0.3, 0.2, 1.0)), ((31.0, 24.0), (0.05, -0.25, 1.0)),
]
LANTERN_KEYS = ["fire"] * 5 + ["amber"] * 3 + ["orange"] + ["green"]


def log(msg):
    print("[HWFOREST] " + msg, flush=True)


# ------------------------------------------------------------------ output collector
class Parts:
    def __init__(self):
        self.lit = {}
        self.glow = bmesh.new()          # lanterns, lenses, eyes, wisps
        self.sil = bmesh.new()           # black silhouettes: far trees, twigs, crows, wires
        self.lights = []
        self.tally = {}

    def L(self, key):
        if key not in self.lit:
            self.lit[key] = bmesh.new()
        return self.lit[key]

    def count(self):
        return sum(tris(b) for b in self.lit.values()) + tris(self.glow) + tris(self.sil)

    def run(self, part, fn, *args):
        n0 = self.count()
        res = fn(self, *args)
        self.tally[part] = self.tally.get(part, 0) + self.count() - n0
        return res

    def lamp(self, kind, pos, color, power, target=None, size=0.5, deg=60.0):
        self.lights.append(light(f"HwForest{len(self.lights):02d}", kind, pos, color, power, target=target, size=size,
                                 spot_deg=deg))


def paint(bm, faces, key):
    glow_faces(bm, faces, key)
    return faces


def octa(bm, c, r, rz=None):
    c, rz = Vector(c), r if rz is None else rz
    v = [bm.verts.new(c + Vector(d)) for d in ((r, 0, 0), (0, r, 0), (-r, 0, 0), (0, -r, 0), (0, 0, rz), (0, 0, -rz))]
    faces = []
    for i in range(4):
        a, b = v[i], v[(i + 1) % 4]
        faces += [bm.faces.new((a, b, v[4])), bm.faces.new((b, a, v[5]))]
    return faces


def ball(bm, c, r, segs=6, rings=3, scale=(1.0, 1.0, 1.0)):
    """Low-poly UV sphere in a fixed vertex order (deterministic)."""
    c, s = Vector(c), Vector(scale)

    def vert(d):
        return bm.verts.new(c + Vector((d.x * s.x, d.y * s.y, d.z * s.z)) * r)

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


def poly(bm, pts, hint):
    f = bm.faces.new([bm.verts.new(Vector(p)) for p in pts])
    f.normal_update()
    if f.normal.dot(Vector(hint)) < 0:
        f.normal_flip()
    return [f]


def slab(bm, pts, thick):
    P = [Vector(p) for p in pts]
    Q = [p + thick for p in P]
    c = sum(P, Vector()) / len(P)
    faces = poly(bm, P, -thick) + poly(bm, Q, thick)
    for i in range(len(P)):
        j = (i + 1) % len(P)
        faces += poly(bm, [P[i], P[j], Q[j], Q[i]], (P[i] + P[j]) / 2 - c)
    return faces


def forbidden(p, pad=0.0):
    """Is p (with a margin pad) inside a volume the crowns must keep out of: the carnival (27 m), the pumpkin patch, the
    crypt, the swamp, the cathedral, the light masts, the vendor lanes and their signs (d < 22.3 for y -12..-68) or a
    searchlight beam (its half-width + 1.5 m)? Also the giant oaks: nothing within OAK_CLEAR of (+-39, 6)."""
    x, y = p.x, p.y
    if (x + 60.0) ** 2 + (y + 110.0) ** 2 < (27.0 + pad) ** 2:
        return True
    for ox in (-39.0, 39.0):
        if (x - ox) ** 2 + (y - 6.0) ** 2 < (OAK_CLEAR + pad) ** 2:
            return True
    for x0, y0, x1, y1 in HARD_R:
        if x0 - pad < x < x1 + pad and y0 - pad < y < y1 + pad:
            return True
    if -68.0 < y < -12.0 and abs(x) - crowd_half(y) < 22.3 + pad:
        return True
    for (bx, by), d in SEARCH_BEAMS:
        c0 = Vector((bx, by, Z0 + 1.0))
        dd = Vector(d).normalized()
        sb = (p - c0).dot(dd)
        if 0.0 < sb < 60.0 and (p - c0 - dd * sb).length < 0.5 + 6.5 * sb / 320.0 + 1.5 + pad:
            return True
    return False


def seg_forbidden(a, b, pad):
    return any(forbidden(a.lerp(b, t), pad) for t in (0.34, 0.67, 1.0))


def rot(v, axis, ang):
    return (Matrix.Rotation(ang, 3, axis) @ v).normalized()


def perp(d, rng):
    """A random unit vector square to d."""
    a = Vector((rng.uniform(-1, 1), rng.uniform(-1, 1), rng.uniform(-1, 1)))
    p = d.cross(a)
    if p.length < 1e-4:
        p = d.cross(Vector((1.0, 0.0, 0.0)))
    return p.normalized()


# ------------------------------------------------------------------ the tree rule
class Tree:
    """One dead tree: a list of branch segments (a, b, r_a, r_b, level), grown by a recursive branching rule (axiom:
    trunk; each branch -> a (kinked) tube + 2-3 children turned 20-50 degrees, 0.62-0.8 as long, thinner)."""

    def __init__(self, x, y, h, style, lit, rng):
        self.base = Vector((x, y, Z0 - 0.15))
        self.h, self.style, self.lit = h, style, lit
        self.segs = []
        self.pruned = 0
        self.max_level = 4 if lit else 3
        r0 = 0.12 + 0.021 * h
        lean = Vector((rng.uniform(-1, 1), rng.uniform(-1, 1), 0.0)) * rng.uniform(0.02, 0.07)
        if style == "snag":
            self.snag(r0, lean, rng)
        elif style == "broken":
            self.broken(r0, lean, rng)
        else:
            self.oak(r0, lean, rng)

    def seg(self, a, b, ra, rb, level):
        self.segs.append((a.copy(), b.copy(), ra, rb, level))

    def oak(self, r0, lean, rng):
        h = self.h
        d = (UP + lean).normalized()
        trunk_len = h * rng.uniform(0.36, 0.46)
        p, r = self.base.copy(), r0
        n = 3
        self.seg(p, p + d * 0.6, r0 * 1.55, r0, 0)                    # root flare
        for i in range(n):                                            # gnarled trunk: three bent pieces
            dd = (d + perp(d, rng) * rng.uniform(0.04, 0.14)).normalized()
            q = p + dd * (trunk_len / n)
            self.seg(p, q, r, r * 0.86, 0)
            p, r = q, r * 0.86
            d = (dd + UP * 0.25).normalized()
        if rng.random() < 0.75:                                       # a low limb, nearly level
            az = rng.uniform(0, TAU)
            dl = Vector((math.cos(az), math.sin(az), rng.uniform(0.15, 0.45))).normalized()
            pl = self.base + (p - self.base) * rng.uniform(0.45, 0.7)
            self.grow(pl, dl, h * rng.uniform(0.18, 0.26), r0 * 0.5, 2, rng, kink=True)
        if rng.random() < 0.5:                                        # a broken stub
            az = rng.uniform(0, TAU)
            ds = Vector((math.cos(az), math.sin(az), rng.uniform(0.0, 0.6))).normalized()
            ps = self.base + (p - self.base) * rng.uniform(0.3, 0.8)
            pe = ps + ds * rng.uniform(0.6, 1.4)
            if not seg_forbidden(ps, pe, r0 * 0.45):
                self.seg(ps, pe, r0 * 0.45, r0 * 0.3, 1)
        n_l = rng.choice((2, 3, 3, 4))
        az0 = rng.uniform(0, TAU)
        for k in range(n_l):
            az = az0 + TAU * k / n_l + rng.uniform(-0.4, 0.4)
            tilt = math.radians(rng.uniform(28, 58))
            dl = Vector((math.sin(tilt) * math.cos(az), math.sin(tilt) * math.sin(az), math.cos(tilt)))
            self.grow(p, dl, h * rng.uniform(0.26, 0.36), r * 0.72, 1, rng, kink=True)

    def grow(self, p, d, L, r, level, rng, kink=False):
        if kink and L > 1.5:
            mid = p + d * (L * 0.5) + perp(d, rng) * (L * rng.uniform(0.06, 0.15))
            tip = p + d * L + perp(d, rng) * (L * rng.uniform(0.0, 0.08))
            if seg_forbidden(p, mid, r) or seg_forbidden(mid, tip, r):
                kink, L = False, L * 0.5
            else:
                self.seg(p, mid, r, r * 0.84, level)
                self.seg(mid, tip, r * 0.84, r * 0.68, level)
                d = (tip - mid).normalized()
        if not kink or L <= 1.5:
            tip = p + d * L
            if seg_forbidden(p, tip, r):
                tip = p + d * (L * 0.5)
                if seg_forbidden(p, tip, r):
                    self.pruned += 1
                    return
                L *= 0.5
            self.seg(p, tip, r, r * 0.68, level)
        if level >= self.max_level:
            return
        n = rng.choices((2, 3), weights=(62, 38))[0]
        az0 = rng.uniform(0, TAU)
        ax0 = perp(d, rng)
        for k in range(n):
            ax = rot(ax0, d, az0 + TAU * k / n + rng.uniform(-0.5, 0.5))
            nd = rot(d, ax, math.radians(rng.uniform(20, 48)))
            if level + 1 >= 3:                                        # twigs droop a little (spooky)
                nd.z -= rng.uniform(0.05, 0.22)
            else:
                nd.z += 0.12
            nd.z = max(nd.z, -0.4)
            nd.normalize()
            self.grow(tip, nd, L * rng.uniform(0.62, 0.8), r * 0.68 * rng.uniform(0.9, 1.05), level + 1, rng,
                      kink=(level + 1 <= 1 and rng.random() < 0.6))

    def snag(self, r0, lean, rng):
        """Dead conifer: a tall tapering trunk with whorls of short drooping branches."""
        h = self.h * 1.05
        d = (UP + lean * 0.5).normalized()
        self.seg(self.base, self.base + d * 0.5, r0 * 1.4, r0 * 0.9, 0)
        n = 4
        p, r = self.base + d * 0.5, r0 * 0.9
        for i in range(n):
            q = p + (d + perp(d, rng) * rng.uniform(0.0, 0.05)).normalized() * ((h - 0.5) / n)
            self.seg(p, q, r, r * 0.72, 0)
            p, r = q, r * 0.72
        z = 0.3 * h
        az = rng.uniform(0, TAU)
        while z < h - 0.8:
            t = z / h
            q = self.base + d * z
            for k in range(3):
                az += 2.1 + rng.uniform(-0.3, 0.3)
                L = h * (0.24 * (1.0 - t) + 0.05) * rng.uniform(0.75, 1.15)
                dd = Vector((math.cos(az), math.sin(az), -rng.uniform(0.1, 0.5))).normalized()
                if rng.random() < 0.18:
                    L *= 0.35                                         # snapped off
                if seg_forbidden(q, q + dd * L, 0.1):
                    self.pruned += 1
                    continue
                self.seg(q, q + dd * L, r0 * 0.16 * (1.0 - t) + 0.025, 0.02, 2)
                if L > 2.2 and self.lit:
                    m = q + dd * (L * 0.6)
                    e_ = m + rot(dd, UP, rng.choice((-0.7, 0.7))) * (L * 0.35)
                    if not seg_forbidden(m, e_, 0.05):
                        self.seg(m, e_, 0.03, 0.015, 3)
            z += rng.uniform(1.1, 1.9)

    def broken(self, r0, lean, rng):
        """Broken snag: a thick trunk snapped at half height, a few stubby limbs."""
        h = self.h * 0.6
        d = (UP + lean * 1.5).normalized()
        self.seg(self.base, self.base + d * 0.6, r0 * 1.7, r0 * 1.15, 0)
        p, r = self.base + d * 0.6, r0 * 1.15
        for i in range(2):
            q = p + (d + perp(d, rng) * 0.1).normalized() * (h / 2)
            self.seg(p, q, r, r * 0.85, 0)
            p, r = q, r * 0.85
        for k in range(rng.choice((2, 3))):
            az = rng.uniform(0, TAU)
            dl = Vector((math.cos(az), math.sin(az), rng.uniform(0.4, 1.0))).normalized()
            pl = self.base + (p - self.base) * rng.uniform(0.55, 0.95)
            self.grow(pl, dl, self.h * rng.uniform(0.14, 0.24), r0 * 0.4, 2, rng)

    def top_z(self):
        return max(max(a.z, b.z) for a, b, _, _, _ in self.segs)

    def build(self, P):
        """Tubes into the lit wood mesh (lit trees: trunk + three branch levels) or the black silhouette mesh."""
        lit_levels = 3 if self.lit else -1
        for a, b, ra, rb, lv in self.segs:
            if lv <= lit_levels:
                sides = 6 if lv == 0 else (5 if lv == 1 else (4 if lv == 2 else 3))
                cyl(P.L(LIT_KEY), a, b, ra, segs=sides, cap=False, r2=rb)
            else:
                sides = 4 if (lv == 0 and (self.lit or self.h > 16)) else 3
                cyl(P.sil, a, b, max(ra, 0.02), segs=sides, cap=False, r2=max(rb, 0.012))

    def perches(self, levels, horiz=0.8):
        """Branch segments fit to hang a lantern from or to perch on: (a, b, r, level), fairly level ones."""
        out = []
        for a, b, ra, rb, lv in self.segs:
            d = b - a
            if lv in levels and d.length > 0.6 and abs(d.normalized().z) < horiz and min(a.z, b.z) > Z0 + 3.0:
                out.append((a, b, (ra + rb) / 2, lv))
        return out


# ------------------------------------------------------------------ where trees may stand
def in_keepout(x, y, pad=0.0):
    for kx, ky, kr in KEEP_C:
        if (x - kx) ** 2 + (y - ky) ** 2 < (kr + pad) ** 2:
            return True
    for x0, y0, x1, y1 in KEEP_R:
        if x0 - pad < x < x1 + pad and y0 - pad < y < y1 + pad:
            return True
    return False


def blocks_view(x, y):
    """Would a trunk at (x, y) stand between a viewer (the DJ, the crowd's middle) and an attraction?"""
    for v in VIEWERS:
        dx, dy = x - v.x, y - v.y
        dist = math.hypot(dx, dy)
        for ax, ay, ar in ATTRACTIONS:
            ex, ey = ax - v.x, ay - v.y
            da = math.hypot(ex, ey)
            if dist >= da:
                continue
            off = abs(math.atan2(dx * ey - dy * ex, dx * ex + dy * ey))
            if off < math.atan2(ar, da) + math.radians(3.0):
                return True
    return False


def near_beam(x, y, clear=7.0):
    """Trunk within `clear` m (horizontal) of a searchlight beam's axis between 6 and 28 m up?"""
    for (bx, by), d in SEARCH_BEAMS:
        dd = Vector(d).normalized()
        for zz in (6.0, 12.0, 18.0, 24.0, 28.0):
            sb = (zz - 1.0) / dd.z
            if math.hypot(x - (bx + dd.x * sb), y - (by + dd.y * sb)) < clear + 6.5 * sb / 320.0:
                return True
    return False


def in_zone(x, y):
    if y > 60.0 or y < -186.0 or abs(x) > 138.0:
        return False
    if near_beam(x, y):
        return False
    if y > -75.0 and abs(x) < crowd_half(min(y, 0.0)) + 24.0:
        return False
    return not in_keepout(x, y) and not blocks_view(x, y)


def edge_depth(x, y):
    """How far (m) a spot lies inside the forest from its venue-side edge (0 = the inner edge, seen best)."""
    e = 1e9
    if y > -80.0:
        e = min(e, max(0.0, abs(x) - crowd_half(min(y, 0.0)) - 24.0) / 1.14)
    for kx, ky, kr in KEEP_C[:1]:
        e = min(e, max(0.0, math.hypot(x - kx, y - ky) - kr))
    for x0, y0, x1, y1 in KEEP_R[:3]:
        dx = max(x0 - x, 0.0, x - x1)
        dy = max(y0 - y, 0.0, y - y1)
        e = min(e, math.hypot(dx, dy))
    return e


def plant(rng):
    """Trees (x, y, h, style, lit): the uplit stands first, then the ring by dart throwing (denser and lower at the
    inner edge, sparser and taller deeper in), up to N_TREES."""
    trees = []
    grid = {}
    CELL = 10.0

    def free(x, y, d):
        gx, gy = int(math.floor(x / CELL)), int(math.floor(y / CELL))
        for i in (gx - 1, gx, gx + 1):
            for j in (gy - 1, gy, gy + 1):
                for tx, ty in grid.get((i, j), ()):
                    if (tx - x) ** 2 + (ty - y) ** 2 < d * d:
                        return False
        return True

    def add(x, y, h, style, lit, cl=-1):
        trees.append(dict(x=x, y=y, h=h, style=style, lit=lit, cluster=cl, e=edge_depth(x, y)))
        grid.setdefault((int(math.floor(x / CELL)), int(math.floor(y / CELL))), []).append((x, y))

    for ci, (cx, cy, n, _, _, _) in enumerate(CLUSTERS):
        k = tries = 0
        while k < n and tries < 400:
            tries += 1
            a, r = rng.uniform(0, TAU), 6.5 * math.sqrt(rng.random())
            x, y = cx + r * math.cos(a), cy + r * math.sin(a)
            if in_zone(x, y) and free(x, y, 4.6):
                add(x, y, rng.uniform(11.0, 16.5), "oak" if rng.random() < 0.85 else "snag", True, ci)
                k += 1
        if k < n:
            log(f"cluster {ci} at ({cx:.0f},{cy:.0f}): only {k}/{n} trees fit")
    def s_base(y):
        return 8.5 if y > 15.0 else (6.8 if y > -75.0 else 10.5)

    def height(e, y):
        h = 10.5 + 0.22 * e + rng.uniform(-1.0, 3.5) + (3.0 if y < -138.0 else 0.0)
        h += 5.0 if rng.random() < 0.07 else 0.0
        return max(10.0, min(25.0, h))

    def style():
        r = rng.random()
        return "oak" if r < 0.8 else ("snag" if r < 0.92 else "broken")

    tries = 0
    while len(trees) < N_TREES and tries < 60000:                     # the inner band, evenly
        tries += 1
        x, y = rng.uniform(-138, 138), rng.uniform(-186, 60)
        if not in_zone(x, y):
            continue
        e = edge_depth(x, y)
        if e > 9.0 or not free(x, y, s_base(y) + rng.uniform(-0.4, 0.4)):
            continue
        add(x, y, height(e, y), style(), False)
    n_inner = len(trees)
    while len(trees) < N_TREES and tries < 200000:                    # deeper rows, sparser, flanks favoured
        tries += 1
        x, y = rng.uniform(-138, 138), rng.uniform(-186, 60)
        if not in_zone(x, y):
            continue
        e = edge_depth(x, y)
        if e <= 9.0 or rng.random() > (0.9 if y > -75.0 else 0.3) * max(0.1, 1.0 - e / 40.0):
            continue
        if not free(x, y, s_base(y) + 0.12 * e + rng.uniform(-0.6, 0.6)):
            continue
        add(x, y, height(e, y), style(), False)
    log(f"stands + inner band {n_inner}, deeper {len(trees) - n_inner}")
    log(f"planted {len(trees)} trees ({sum(t['lit'] for t in trees)} lit) in {tries} tries")
    return trees


# ------------------------------------------------------------------ hangings
def lantern(P, p, length, key, big=False):
    """A lantern on a wire hanging from p (a point under a branch): wire + cap (black), glowing body."""
    top = Vector(p)
    body = top - UP * (length + 0.18)
    cyl(P.sil, top, body + UP * 0.2, 0.012, segs=3, cap=False)
    s = 0.3 if big else 0.26
    cone(P.sil, body + UP * (s * 0.62), body + UP * (s * 0.62 + 0.14), s * 0.62, segs=4, cap=False)
    paint(P.glow, box(P.glow, body, (s, s, s * 1.3)), key)
    return body


def cage(P, top, rng, wisp, lean_dir):
    """Gibbet cage on a chain under a branch: dome, rings, bars, floor, a skeleton slumped inside (one arm through the
    bars); wisp: a dim green glow inside."""
    m = P.L("metal_dark")
    chain = rng.uniform(0.9, 1.6)
    ct = top - UP * chain
    cyl(m, top, ct, 0.025, segs=3, cap=False)
    R, H = 0.42, 1.55
    zr = ct - UP * 0.32
    cone(m, zr, ct, R, segs=8, cap=False)
    cyl(m, zr - UP * 0.06, zr, R * 1.03, segs=8, cap=False)
    cyl(m, zr - UP * (H * 0.55), zr - UP * (H * 0.55 - 0.05), R * 1.03, segs=8, cap=False)
    bot = zr - UP * H
    cyl(m, bot, bot + UP * 0.06, R * 1.03, segs=8, cap=True)
    for k in range(8):
        a = TAU * (k + 0.5) / 8
        off = Vector((math.cos(a), math.sin(a), 0.0)) * R
        cyl(m, bot + off, zr + off, 0.018, segs=3, cap=False)
    bn = P.L("bone")
    sk = bot + UP * 0.62 + lean_dir * 0.08
    ball(bn, sk, 0.12, 6, 3, (0.9, 1.0, 1.1))
    box(bn, bot + UP * 0.32, (0.26, 0.16, 0.34))
    hand0 = bot + UP * 0.45 + lean_dir * 0.2
    cyl(bn, hand0, hand0 + lean_dir * 0.3 - UP * 0.25, 0.025, segs=3, cap=False)
    cyl(bn, hand0 + lean_dir * 0.3 - UP * 0.25, hand0 + lean_dir * 0.38 - UP * 0.55, 0.022, segs=3, cap=False)
    for e in (-1, 1):
        side = Vector((-lean_dir.y, lean_dir.x, 0.0)) * (0.045 * e)
        paint(P.glow, octa(P.glow, sk + lean_dir * 0.1 + side + UP * 0.02, 0.025), "black")
    if wisp:
        paint(P.glow, octa(P.glow, bot + UP * 0.95, 0.12, 0.17), "green_dim")
    return bot


def crow(P, p, facing, rng, eyes=False):
    """A crow perched at p (feet) facing `facing`: body, head, beak, tail; black, optional red eyes."""
    f = Vector((facing.x, facing.y, 0.0)).normalized()
    r = Vector((-f.y, f.x, 0.0))
    s = rng.uniform(0.95, 1.2)
    bm = P.sil
    c = p + UP * (0.15 * s)
    v = [bm.verts.new(c + d) for d in (f * (0.2 * s), -f * (0.2 * s), r * (0.08 * s), -r * (0.08 * s),
                                       UP * (0.09 * s), -UP * (0.07 * s))]
    for a, b in ((0, 2), (2, 1), (1, 3), (3, 0)):
        bm.faces.new((v[a], v[b], v[4]))
        bm.faces.new((v[b], v[a], v[5]))
    hd = c + f * (0.2 * s) + UP * (0.1 * s)
    octa(bm, hd, 0.065 * s, 0.07 * s)
    cone(bm, hd + f * (0.04 * s), hd + f * (0.15 * s) - UP * (0.01 * s), 0.025 * s, segs=3, cap=False)
    slab(bm, [c - f * (0.15 * s) + r * (0.03 * s), c - f * (0.42 * s) + r * (0.07 * s) - UP * (0.06 * s),
              c - f * (0.42 * s) - r * (0.07 * s) - UP * (0.06 * s), c - f * (0.15 * s) - r * (0.03 * s)], UP * 0.02)
    if eyes:
        for e in (-1, 1):
            c_ = hd + f * (0.045 * s) + r * (0.042 * s * e) + UP * (0.012 * s)
            to = (DJ_EYE - c_)
            to = Vector((to.x, to.y, 0.0)).normalized()
            rt = Vector((-to.y, to.x, 0.0)) * 0.014
            paint(P.glow, poly(P.glow, [c_ - rt - UP * 0.012 + to * 0.06, c_ + rt - UP * 0.012 + to * 0.06,
                                        c_ + rt + UP * 0.012 + to * 0.06, c_ - rt + UP * 0.012 + to * 0.06], to), "red")


def point_on(seg, t):
    a, b, r, lv = seg
    return a.lerp(b, t)


# ------------------------------------------------------------------ build
def forest(P, rng, trees):
    built = []
    for t in trees:
        tr = Tree(t["x"], t["y"], t["h"], t["style"], t["lit"], rng)
        tr.build(P)
        built.append((t, tr))
    log(f"branches pruned at the keep-out volumes: {sum(tr.pruned for _, tr in built)}")
    return built


def hang(P, rng, built):
    """Lanterns, cages and crows; lantern-glow lights in the trees with the most lanterns."""
    lan_count = 0
    lit_groups = []
    for t, tr in built:
        if t["lit"]:
            n = rng.randint(2, 4)
        elif t["e"] < 12.0 and rng.random() < 0.4:
            n = rng.randint(1, 2)
        elif rng.random() < 0.05:
            n = 1
        else:
            n = 0
        spots = tr.perches((1, 2, 3) if t["lit"] else (1, 2), horiz=0.8)
        bodies = []
        for k in range(min(n, len(spots))):
            seg = spots[rng.randrange(len(spots))]
            p = point_on(seg, rng.uniform(0.35, 0.9)) - UP * seg[2]
            length = rng.uniform(0.35, 1.3)
            if p.z - length - 0.5 < Z0 + 2.4 or forbidden(p, 0.3):
                continue
            if any((p - q).length < 1.2 for q in bodies):
                continue
            bodies.append(lantern(P, p, length, LANTERN_KEYS[rng.randrange(len(LANTERN_KEYS))], big=not t["lit"]))
        lan_count += len(bodies)
        if t["lit"] and bodies:
            lit_groups.append((len(bodies), t, bodies))
    # warm glow lights in up to 8 lit trees with the most lanterns, one per stand
    lit_groups.sort(key=lambda g: (-g[0], g[1]["e"]))
    used, nl = set(), 0
    for n, t, bodies in lit_groups:
        if nl >= 8 or t["cluster"] in used:
            continue
        c = sum(bodies, Vector()) / len(bodies)
        P.lamp("POINT", c + UP * 0.6, (1.0, 0.5, 0.16), 160.0 + 60.0 * n, size=1.0)
        used.add(t["cluster"])
        nl += 1
    # cages: in lit trees near the venue, from level, strong branches
    cands = sorted([(t, tr) for t, tr in built if t["lit"]], key=lambda b: (b[0]["e"], math.hypot(b[0]["x"], b[0]["y"])))
    n_cage, used_cl = 0, set()
    for t, tr in cands:
        if n_cage >= 5 or t["cluster"] in used_cl:
            continue
        spots = [s for s in tr.perches((1, 2), horiz=0.6) if s[2] > 0.06]
        spots = [s for s in spots if Z0 + 5.0 < point_on(s, 0.6).z < Z0 + 9.5 and not forbidden(point_on(s, 0.6), 0.9)]
        if not spots:
            continue
        seg = spots[rng.randrange(len(spots))]
        top = point_on(seg, 0.6) - UP * seg[2]
        to_v = Vector((-t["x"], -35.0 - t["y"], 0.0)).normalized()
        wisp = n_cage in (0, 3)
        bot = cage(P, top, rng, wisp, to_v)
        if wisp:
            P.lamp("POINT", bot + UP * 1.0, (0.25, 1.0, 0.35), 45.0, size=0.3)
        used_cl.add(t["cluster"])
        n_cage += 1
    # crows on branch tops: lit trees first, then the inner-edge silhouettes against the sky
    n_crow = 0
    order = [b for b in built if b[0]["lit"]] + [b for b in built if not b[0]["lit"] and b[0]["e"] < 10.0]
    for t, tr in order:
        if n_crow >= 42:
            break
        k = rng.choice((0, 1, 1, 2)) if t["lit"] else rng.choice((0, 0, 1))
        spots = tr.perches((1, 2, 3), horiz=0.45)
        for _ in range(min(k, len(spots))):
            seg = spots[rng.randrange(len(spots))]
            p = point_on(seg, rng.uniform(0.3, 0.8)) + UP * (seg[2] * 0.8)
            d = (seg[1] - seg[0])
            face = Vector((-d.y, d.x, 0.0)) * rng.choice((-1, 1)) + Vector((rng.uniform(-0.4, 0.4),
                                                                            rng.uniform(-0.4, 0.4), 0.0))
            if forbidden(p, 0.6):
                continue
            crow(P, p, face, rng, eyes=t["lit"] and math.hypot(t["x"], t["y"]) < 75.0)
            n_crow += 1
    log(f"lanterns {lan_count}, cages {n_cage}, crows {n_crow}, lantern lights {nl}")


def uplights(P, rng, trees):
    for ci, (cx, cy, n, col, key, power) in enumerate(CLUSTERS):
        members = [t for t in trees if t["cluster"] == ci]
        if not members:
            continue
        c = Vector((sum(t["x"] for t in members) / len(members), sum(t["y"] for t in members) / len(members), Z0))
        hm = sum(t["h"] for t in members) / len(members)
        to_v = Vector((-c.x, -35.0 - c.y, 0.0)).normalized()
        p = c + to_v * 7.5
        if any(math.hypot(p.x - t["x"], p.y - t["y"]) < 1.2 for t in trees):
            p = c + to_v * 9.0
        tgt = c + UP * (0.55 * hm) - to_v * 1.0
        fx = Vector((p.x, p.y, Z0))
        aim = (tgt - fx).normalized()
        yaw = math.atan2(aim.y, aim.x)
        box(P.L("metal_dark"), fx + UP * 0.15, (0.45, 0.45, 0.3), yaw=yaw)
        paint(P.glow, box(P.glow, fx + UP * 0.32, (0.32, 0.32, 0.04), yaw=yaw), key)
        P.lamp("SPOT", fx + UP * 0.45, col, power * 0.8, target=tgt, size=0.3, deg=62)


def build(rng):
    P = Parts()
    trees = plant(rng)
    built = P.run("trees", forest, rng, trees)
    P.run("hangings", hang, rng, built)
    P.run("uplights", uplights, rng, trees)
    paint(P.sil, list(P.sil.faces), "black")
    lit_t = sum(tris(b) for b in P.lit.values())
    log("tris: " + ", ".join(f"{k} {v}" for k, v in P.tally.items()) + f"; lit {lit_t}, glow {tris(P.glow)}, "
        f"silhouette {tris(P.sil)}, total {P.count()}; lights {len(P.lights)}")
    xs = [t["x"] for t in trees]
    ys = [t["y"] for t in trees]
    log(f"trunks x {min(xs):.0f}..{max(xs):.0f}, y {min(ys):.0f}..{max(ys):.0f}; heights "
        f"{min(t['h'] for t in trees):.1f}..{max(t['h'] for t in trees):.1f} m; styles "
        + ", ".join(f"{s} {sum(t['style'] == s for t in trees)}" for s in ("oak", "snag", "broken")))
    lit = [(bm, key) for key, bm in P.lit.items() if len(bm.faces)]
    return {"lit": lit, "glow": [P.glow, P.sil], "beams": [], "halos": [], "lights": P.lights, "exclude": [],
            "people": []}
