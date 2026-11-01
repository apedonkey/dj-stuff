"""GRAVEYARD SHIFT grounds module GRAVEYARD: the two graveyard strips beside the crowd (Blender 4.5, headless).

Both sides of the crowd, |x| from crowd_half(y)+3 to crowd_half(y)+10, y -10..-70 (kit frame, field z = GROUND_Z):
  - ~400 tombstones on a grid cut by the strip's diagonal edges: slabs (round, pointed, pediment, chamfered, broken),
    crosses, celtic crosses, obelisks, chest tombs and ledgers, small markers; tilted and sunk at random
  - 6 praying angels and big crosses as hero stones, each with a green or purple uplight
  - 4 gothic mausoleums (y -25 and -50) with their doors toward the crowd: iron gates, a dim green glow inside, a
    purple uplight on the facade; at y -50 a closed coffin stands in the glowing doorway
  - 20 coffins: upright at the mausoleums, open and empty (dim green inside) beside the open graves, scattered ones
    closed (some with candles on the lid) or open with a skeleton on a dim red glowing lining
  - 6 open graves: a mounded dirt rim around a green-glowing pit, skeletal arms reaching out, a dirt heap, a shovel
  - a low wrought-iron fence on each strip's outer edge: pickets, rails, stone pillars at the ends, fire lanterns
  - candle clusters (four with a light), candles left at a few stones, ~20 ghoul "people" between the stones
The stones face the crowd, turned TURN toward the stage, so the DJ sees their fronts. Lit materials are dark; the
light comes from the module's lights (uplights, the mausoleum doors, the graves, lanterns, candles).
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "grounds"))
from kit import *  # noqa: E402,F401,F403

NAME = "graveyard"
BAKE_SIZE = 4096                 # ~1,800 small islands (stones, pickets): 2048 leaves them a few texels each

G = GROUND_Z
D_IN, D_OUT = 3.0, 10.0          # the strip: |x| from crowd_half(y) + D_IN to + D_OUT
Y_FRONT, Y_BACK = -10.0, -70.0
TURN = 0.2                       # stones face (-side, TURN): toward the crowd, turned ~11 degrees toward the stage
UP = Vector((0.0, 0.0, 1.0))
DJ = Vector((0.0, 0.9, 2.7))     # the DJ's head (kit frame)
SIDES = (1, -1)

C_GREEN = (0.15, 1.0, 0.25)      # light colors (kit.GLOW green / purple / fire-ish)
C_PURPLE = (0.55, 0.15, 1.0)
C_FIRE = (1.0, 0.42, 0.10)
C_CANDLE = (1.0, 0.55, 0.20)

# light powers (W, Blender units), tuned by hw_preview.py renders (exposure 0.9)
P_DOOR, P_FACADE, P_GRAVE, P_HERO, P_LANTERN, P_CANDLE = 45.0, 260.0, 40.0, 280.0, 80.0, 18.0

# per side: open graves (y, d); hero stones (y, d, kind, uplight color); candle clusters with a light (y, d)
PLAN = {
    1: {"graves": ((-19.0, 6.3), (-42.5, 5.4), (-64.0, 6.3)),
        "heroes": ((-13.5, 5.1, "angel", "purple"), (-36.0, 7.4, "celtic", "green"), (-58.0, 5.3, "angel", "green")),
        "candles": ((-12.0, 3.9), (-31.0, 4.0))},
    -1: {"graves": ((-13.0, 5.5), (-34.0, 6.2), (-57.5, 5.4)),
         "heroes": ((-18.5, 7.3, "angel", "green"), (-41.0, 5.1, "celtic", "purple"), (-63.5, 6.6, "angel", "purple")),
         "candles": ((-21.5, 3.9), (-44.5, 4.0))},
}
MAUS_Y = (-25.0, -50.0)
MAUS_D = 6.1                     # mausoleum center depth past the crowd edge
MAUS_W, MAUS_DP, MAUS_H, MAUS_PL = 3.4, 4.0, 3.0, 0.35   # body width, depth, wall height, plinth height


# ------------------------------------------------------------------ output collector
class Parts:
    """One lit bmesh per LIT key, one glow/beam/halo bmesh, lights, keep-outs, people, footprints, tris per feature."""

    def __init__(self):
        self.lit, self.glow, self.beams, self.halos = {}, bmesh.new(), bmesh.new(), bmesh.new()
        self.lights, self.exclude, self.people = [], [], []
        self.obst = []                                  # (x, y, r) footprints: nothing else is placed inside them
        self.rects = []                                 # (cx, cy, ux, uy, hx, hy): oriented footprints (u = local x)
        self.hinged = []                                # [bm, key, pivot, axis, open_deg, delay] (CONTRACT.md)
        self.tally, self.counts = {}, {}

    def m(self, key):
        if key not in self.lit:
            self.lit[key] = bmesh.new()
        return self.lit[key]

    def count(self):
        return sum(tris(b) for b in self.lit.values()) + tris(self.glow) + sum(tris(h[0]) for h in self.hinged)

    def run(self, name, fn, *args):
        n0 = self.count()
        fn(self, *args)
        self.tally[name] = self.tally.get(name, 0) + self.count() - n0

    def free(self, x, y, r):
        """True if a disc (x, y, r) misses every footprint."""
        for ox, oy, orr in self.obst:
            if (x - ox) ** 2 + (y - oy) ** 2 < (r + orr) ** 2:
                return False
        for cx, cy, ux, uy, hx, hy in self.rects:
            dx, dy = x - cx, y - cy
            qa, qb = max(abs(dx * ux + dy * uy) - hx, 0.0), max(abs(dy * ux - dx * uy) - hy, 0.0)
            if qa * qa + qb * qb < r * r:
                return False
        return True

    def take(self, x, y, r):
        self.obst.append((x, y, r))

    def take_rect(self, M, x0, y0, x1, y1, pad=0.1):
        """Footprint: the local rectangle x0..x1, y0..y1 of frame M (plus pad)."""
        c = M @ Vector(((x0 + x1) / 2, (y0 + y1) / 2, 0.0))
        u = M.to_3x3() @ Vector((1.0, 0.0, 0.0))
        u.z = 0.0
        u.normalize()
        self.rects.append((c.x, c.y, u.x, u.y, abs(x1 - x0) / 2 + pad, abs(y1 - y0) / 2 + pad))

    def lamp(self, name, kind, pos, color, power, **kw):
        self.lights.append(light(name, kind, tuple(pos), color, power, **kw))

    def n(self, what, k=1):
        self.counts[what] = self.counts.get(what, 0) + k


def gl(P, faces, key):
    glow_faces(P.glow, faces, key)
    return faces


# ------------------------------------------------------------------ strip frame
def strip_pt(s, y, d, z=G):
    """The point d meters past the crowd edge at depth y on side s (+1 right, -1 left)."""
    return Vector((s * (crowd_half(y) + d), y, z))


def strip_d(s, x, y):
    return s * x - crowd_half(y)


def face_dir(s):
    return Vector((-s, TURN, 0.0)).normalized()


def yaw_box(f):
    """Yaw that turns a block's local -Y (its front) onto the horizontal direction f."""
    return math.atan2(f[0], -f[1])


def yaw_person(f):
    """Yaw that turns +Y (a person's front) onto f (the crowd's convention)."""
    return math.atan2(-f[0], f[1])


def M_at(x, y, z, yaw=0.0, pitch=0.0, roll=0.0):
    return (Matrix.Translation((x, y, z)) @ Matrix.Rotation(yaw, 4, "Z") @ Matrix.Rotation(pitch, 4, "X")
            @ Matrix.Rotation(roll, 4, "Y"))


def T(x, y, z):
    return Matrix.Translation((x, y, z))


# ------------------------------------------------------------------ primitives (verts/faces only: no bmesh.ops, whose
# cost grows with the mesh; every solid's faces point outward, the bottom on the ground is left out where hidden)
_CUBE = {"-z": (0, 2, 3, 1), "+z": (4, 5, 7, 6), "-y": (0, 1, 5, 4), "+y": (2, 6, 7, 3), "-x": (0, 4, 6, 2),
         "+x": (1, 3, 7, 5)}


def block(bm, M, z0, z1, hx, hy, tx=None, ty=None, cx=0.0, cy=0.0, skip=("-z",)):
    """Box (or frustum: top half sizes tx, ty) from local z0 to z1 centered at (cx, cy) in frame M."""
    tx = hx if tx is None else tx
    ty = hy if ty is None else ty
    vs = [bm.verts.new(M @ Vector((cx + (sx if i else -sx), cy + (sy if j else -sy), z)))
          for z, sx, sy in ((z0, hx, hy), (z1, tx, ty)) for j in (0, 1) for i in (0, 1)]
    return [bm.faces.new([vs[k] for k in idx]) for name, idx in _CUBE.items() if name not in skip]


def pyramid(bm, M, z0, z1, hx, hy, cx=0.0, cy=0.0):
    b = [bm.verts.new(M @ Vector((cx + sx * hx, cy + sy * hy, z0))) for sx, sy in ((-1, -1), (1, -1), (1, 1), (-1, 1))]
    t = bm.verts.new(M @ Vector((cx, cy, z1)))
    return [bm.faces.new((b[i], b[(i + 1) % 4], t)) for i in range(4)]


def _ccw(pts):
    return pts if sum(p[0] * q[1] - q[0] * p[1] for p, q in zip(pts, pts[1:] + pts[:1])) > 0 else pts[::-1]


def prism_y(bm, M, pts, depth, cy=0.0, bottom=False):
    """Closed prism: outline pts [(x, z)] in the local XZ plane, from local y = cy - depth/2 (the front, facing -Y) to
    cy + depth/2. The side face along the outline's lowest edge (on the ground) is left out unless bottom."""
    pts = _ccw(list(pts))
    f = [bm.verts.new(M @ Vector((u, cy - depth / 2, v))) for u, v in pts]
    b = [bm.verts.new(M @ Vector((u, cy + depth / 2, v))) for u, v in pts]
    faces = [bm.faces.new(f), bm.faces.new(b[::-1])]
    vmin = min(v for _, v in pts) + 1e-6
    for i in range(len(pts)):
        j = (i + 1) % len(pts)
        if bottom or pts[i][1] > vmin or pts[j][1] > vmin:
            faces.append(bm.faces.new((f[i], b[i], b[j], f[j])))
    return faces


def prism_z(bm, M, pts, z0, z1, top=True, bottom=False):
    """Prism of an outline pts [(x, y)] in the local XY plane, from local z0 to z1."""
    pts = _ccw(list(pts))
    lo = [bm.verts.new(M @ Vector((x, y, z0))) for x, y in pts]
    hi = [bm.verts.new(M @ Vector((x, y, z1))) for x, y in pts]
    faces = [bm.faces.new(hi)] if top else []
    if bottom:
        faces.append(bm.faces.new(lo[::-1]))
    for i in range(len(pts)):
        j = (i + 1) % len(pts)
        faces.append(bm.faces.new((lo[i], lo[j], hi[j], hi[i])))
    return faces


def tray_z(bm, M, outer, inner, z0, z1, zf):
    """Walls of an open box between two matching outlines (outside z0..z1, inside zf..z1, a rim on top). Returns the
    walls and the inner outline's floor verts (the caller makes the floor in the mesh it belongs to)."""
    outer, inner = _ccw(list(outer)), _ccw(list(inner))
    ol = [bm.verts.new(M @ Vector((x, y, z0))) for x, y in outer]
    oh = [bm.verts.new(M @ Vector((x, y, z1))) for x, y in outer]
    il = [bm.verts.new(M @ Vector((x, y, zf))) for x, y in inner]
    ih = [bm.verts.new(M @ Vector((x, y, z1))) for x, y in inner]
    faces = []
    for i in range(len(outer)):
        j = (i + 1) % len(outer)
        faces += [bm.faces.new((ol[i], ol[j], oh[j], oh[i])), bm.faces.new((il[i], ih[i], ih[j], il[j])),
                  bm.faces.new((oh[i], oh[j], ih[j], ih[i]))]
    return faces, [M @ Vector((x, y, zf)) for x, y in inner]


def floor_face(bm, pts):
    """One polygon through world points pts (counter-clockwise seen from above: facing up)."""
    return [bm.faces.new([bm.verts.new(p) for p in pts])]


def ring_y(bm, M, cx, cz, r_out, r_in, depth, segs=8, cy=0.0):
    """Flat ring (a celtic cross's wheel, a window frame) in the local XZ plane, `depth` thick along local Y."""
    angs = [2 * math.pi * (i + 0.5) / segs for i in range(segs)]

    def V(r, a, y):
        return bm.verts.new(M @ Vector((cx + r * math.cos(a), y, cz + r * math.sin(a))))
    fo, fi = [V(r_out, a, cy - depth / 2) for a in angs], [V(r_in, a, cy - depth / 2) for a in angs]
    bo, bi = [V(r_out, a, cy + depth / 2) for a in angs], [V(r_in, a, cy + depth / 2) for a in angs]
    faces = []
    for i in range(segs):
        j = (i + 1) % segs
        faces += [bm.faces.new((fi[i], fo[i], fo[j], fi[j])), bm.faces.new((bi[j], bo[j], bo[i], bi[i])),
                  bm.faces.new((fo[i], bo[i], bo[j], fo[j])), bm.faces.new((fi[j], bi[j], bi[i], fi[i]))]
    return faces


def _basis(d):
    z = d.normalized()
    x = z.orthogonal().normalized()
    return x, z.cross(x)


def tube(bm, a, b, r, segs=4, r2=None, caps=False):
    """Open (or capped) n-sided tube from a to b, radius r (r2 at b)."""
    a, b = Vector(a), Vector(b)
    if (b - a).length < 1e-6:
        return []
    x, y = _basis(b - a)
    r2 = r if r2 is None else r2
    angs = [2 * math.pi * i / segs for i in range(segs)]
    ra = [bm.verts.new(a + (x * math.cos(t) + y * math.sin(t)) * r) for t in angs]
    rb = [bm.verts.new(b + (x * math.cos(t) + y * math.sin(t)) * r2) for t in angs]
    faces = [bm.faces.new((ra[i], ra[(i + 1) % segs], rb[(i + 1) % segs], rb[i])) for i in range(segs)]
    if caps:
        faces += [bm.faces.new(rb), bm.faces.new(ra[::-1])]
    return faces


def spike(bm, a, b, r, segs=4, cap=False):
    """Cone from a base circle at a (radius r) to the tip b."""
    a, b = Vector(a), Vector(b)
    x, y = _basis(b - a)
    ring = [bm.verts.new(a + (x * math.cos(t) + y * math.sin(t)) * r) for t in
            (2 * math.pi * i / segs for i in range(segs))]
    tip = bm.verts.new(b)
    faces = [bm.faces.new((ring[i], ring[(i + 1) % segs], tip)) for i in range(segs)]
    if cap:
        faces.append(bm.faces.new(ring[::-1]))
    return faces


def ball(bm, M, c, r, segs=6, rings=4, scale=(1.0, 1.0, 1.0)):
    """Low UV sphere in frame M: triangle fans at the poles, quads between."""
    m = M @ Matrix.Translation(c) @ Matrix.Diagonal(Vector(scale).to_4d())
    angs = [2 * math.pi * i / segs for i in range(segs)]
    top, bot = bm.verts.new(m @ Vector((0, 0, r))), bm.verts.new(m @ Vector((0, 0, -r)))
    rows = []
    for k in range(1, rings):
        ph = math.pi * k / rings
        rows.append([bm.verts.new(m @ Vector((r * math.sin(ph) * math.cos(t), r * math.sin(ph) * math.sin(t),
                                              r * math.cos(ph)))) for t in angs])
    faces = []
    for i in range(segs):
        j = (i + 1) % segs
        faces.append(bm.faces.new((top, rows[0][i], rows[0][j])))
        for k in range(len(rows) - 1):
            faces.append(bm.faces.new((rows[k][i], rows[k + 1][i], rows[k + 1][j], rows[k][j])))
        faces.append(bm.faces.new((bot, rows[-1][j], rows[-1][i])))
    return faces


def disc(bm, c, n, r, segs=6):
    """Flat n-gon at c facing n."""
    c = Vector(c)
    a, b = _basis(Vector(n))
    return [bm.faces.new([bm.verts.new(c + (a * math.cos(t) + b * math.sin(t)) * r)
                          for t in (2 * math.pi * i / segs for i in range(segs))])]


class Plane:
    """2D drawing plane: o + r*u + up*v; front normal n = r x up."""

    def __init__(self, o, r, up):
        self.o, self.r, self.up = Vector(o), Vector(r).normalized(), Vector(up).normalized()
        self.n = self.r.cross(self.up).normalized()

    def p(self, u, v, w=0.0):
        return self.o + self.r * u + self.up * v + self.n * w


def flat(bm, pl, pts, w=0.0):
    """One polygon of (u, v) points in plane pl, facing pl.n."""
    pts = _ccw(list(pts))
    return [bm.faces.new([bm.verts.new(pl.p(u, v, w)) for u, v in pts])]


# ------------------------------------------------------------------ tombstones
STONE_KEYS = ("stone", "stone", "stone", "stone", "stone", "dino_grey", "dino_grey", "metal_grey")


def lean(rng, strong=0.12):
    """Pitch (forward/back) and roll (sideways) of an old stone: most a little, some a lot."""
    if rng.random() < strong:
        return rng.choice((-1, 1)) * rng.uniform(0.22, 0.4), rng.uniform(-0.14, 0.14)
    return rng.gauss(0, 0.055), rng.gauss(0, 0.04)


def slab_outline(kind, w, h, rng):
    hw = w / 2
    if kind == "round":
        b = h - hw
        return [(-hw, 0.0), (hw, 0.0)] + [(hw * math.cos(math.pi * i / 6), b + hw * math.sin(math.pi * i / 6))
                                          for i in range(7)]
    if kind == "pointed":
        b = h - 0.75 * w
        return [(-hw, 0.0), (hw, 0.0), (hw, b), (hw * 0.72, b + 0.45 * w), (0.0, h), (-hw * 0.72, b + 0.45 * w),
                (-hw, b)]
    if kind == "pediment":
        return [(-hw, 0.0), (hw, 0.0), (hw, h - 0.3 * w), (0.0, h), (-hw, h - 0.3 * w)]
    if kind == "chamfer":
        c = 0.2 * w
        return [(-hw, 0.0), (hw, 0.0), (hw, h - c), (hw - c, h), (-hw + c, h), (-hw, h - c)]
    # broken: a jagged diagonal break
    return [(-hw, 0.0), (hw, 0.0), (hw, h * rng.uniform(0.35, 0.55)), (hw * rng.uniform(-0.3, 0.3),
            h * rng.uniform(0.55, 0.75)), (-hw, h * rng.uniform(0.75, 0.95))]


def slab(P, x, y, f, rng, small=False):
    """Headstone: a profiled slab, 40% on a base block; leaning, sunk so no edge floats. Returns its footprint radius."""
    if small:
        w, h, t = rng.uniform(0.24, 0.36), rng.uniform(0.22, 0.42), rng.uniform(0.06, 0.09)
        kind = rng.choice(("round", "chamfer", "round", "pediment"))
    else:
        w, h, t = rng.uniform(0.4, 0.66), rng.uniform(0.6, 1.25), rng.uniform(0.1, 0.16)
        h = max(h, w * 0.95)
        kind = rng.choices(("round", "pointed", "pediment", "chamfer", "broken"), weights=(38, 17, 15, 20, 10))[0]
    yaw = yaw_box(f) + rng.gauss(0, 0.16)
    pitch, roll = lean(rng, 0.0 if small else 0.12)
    m = P.m(rng.choice(STONE_KEYS))
    z = G
    if not small and rng.random() < 0.4:                # a base block; the slab stands up straight on it
        bh = rng.uniform(0.12, 0.2)
        block(m, M_at(x, y, G - 0.04, yaw, pitch * 0.3, roll * 0.3), 0.0, bh + 0.04, w / 2 + 0.09, t / 2 + 0.11)
        z, pitch, roll = G + bh - 0.03, pitch * 0.3, roll * 0.3
    sink = 0.05 + abs(math.sin(pitch)) * t + abs(math.sin(roll)) * w * 0.5
    prism_y(m, M_at(x, y, z - sink, yaw, pitch, roll), slab_outline(kind, w, h + sink, rng), t)
    if kind == "broken" and rng.random() < 0.7:         # the broken-off top lies in front of it
        pw, ph = w * rng.uniform(0.5, 0.8), rng.uniform(0.25, 0.4)
        fx, fy = x + f.x * rng.uniform(0.35, 0.55), y + f.y * rng.uniform(0.35, 0.55)
        prism_y(m, M_at(fx, fy, G + t * 0.5 - 0.02, yaw + rng.uniform(-0.6, 0.6), math.pi / 2 - rng.uniform(0, 0.15),
                        rng.uniform(-0.1, 0.1)), slab_outline("round", pw, ph, rng), t, cy=0.0, bottom=True)
    return max(w * 0.5, 0.2) + 0.03


def cross(P, x, y, f, rng, big=False):
    h = rng.uniform(2.1, 2.6) if big else rng.uniform(0.95, 1.7)
    a = 0.09 if big else rng.uniform(0.05, 0.075)        # half thickness of the arms
    yaw = yaw_box(f) + rng.gauss(0, 0.2)
    pitch, roll = lean(rng, 0.1)
    m = P.m(rng.choice(STONE_KEYS))
    z0 = 0.0
    if big or rng.random() < 0.6:                       # stepped base
        M0 = M_at(x, y, G, yaw)
        block(m, M0, -0.04, 0.16, 0.27 + a, 0.2 + a)
        block(m, M0, 0.16, 0.3, 0.17 + a, 0.12 + a)
        z0, pitch, roll = 0.3, pitch * 0.25, roll * 0.25
    sink = 0.05 + abs(math.sin(pitch)) * a * 2 + abs(math.sin(roll)) * a * 2
    M = M_at(x, y, G + z0 - sink, yaw, pitch, roll)
    hh = h - z0 + sink
    block(m, M, 0.0, hh, a, a)
    bz = hh * 0.73
    block(m, M, bz - a, bz + a, h * 0.24 + 0.05, a, skip=())
    return 0.42 if big else 0.3


def celtic(P, x, y, f, rng, big=False):
    h = 2.7 if big else rng.uniform(1.5, 2.1)
    k = h / 1.8
    yaw = yaw_box(f) + rng.gauss(0, 0.12)
    pitch, roll = lean(rng, 0.05)
    m = P.m("dino_grey" if big else rng.choice(STONE_KEYS))
    M0 = M_at(x, y, G, yaw)
    block(m, M0, -0.04, 0.34 * k, 0.27 * k, 0.17 * k, tx=0.22 * k, ty=0.14 * k)          # tapered base
    pitch, roll = pitch * 0.4, roll * 0.4
    M = M_at(x, y, G + 0.3 * k, yaw, pitch, roll)
    hh = h - 0.3 * k
    block(m, M, 0.0, hh, 0.085 * k, 0.06 * k, tx=0.07 * k, ty=0.055 * k)                 # shaft
    cz, a = hh * 0.77, 0.07 * k
    block(m, M, cz - a, cz + a, 0.27 * k, 0.055 * k, skip=())                              # arms
    ring_y(m, M, 0.0, cz, 0.215 * k, 0.165 * k, 0.085 * k, segs=8)                         # the wheel
    return 0.5 if big else 0.36


def obelisk(P, x, y, f, rng, big=False):
    h = rng.uniform(3.3, 3.8) if big else rng.uniform(1.9, 3.0)
    yaw = yaw_box(f) + rng.uniform(-0.3, 0.3)
    m = P.m(rng.choice(("stone", "dino_grey", "dino_grey")))
    M = M_at(x, y, G - 0.03, yaw, rng.gauss(0, 0.02), rng.gauss(0, 0.02))
    block(m, M, 0.0, 0.3, 0.38, 0.38)                                                    # plinth
    block(m, M, 0.3, 0.85, 0.27, 0.27)                                                   # die
    block(m, M, 0.85, 0.95, 0.31, 0.31, skip=())                                        # cap
    s0 = 0.17 + 0.02 * (h - 2.0)
    block(m, M, 0.95, h - 0.3, s0, s0, tx=s0 * 0.62, ty=s0 * 0.62, skip=("-z", "+z"))   # shaft
    pyramid(m, M, h - 0.3, h, s0 * 0.62, s0 * 0.62)
    return 0.52


def chest_tomb(P, x, y, f, rng):
    """A chest tomb (or a ledger slab with a small headstone) lying along f. Footprint: three discs."""
    along = rng.random() < 0.6
    yaw = yaw_box(f) + (0.0 if along else math.pi / 2) + rng.gauss(0, 0.05)
    m = P.m(rng.choice(STONE_KEYS))
    M = M_at(x, y, G - 0.02, yaw, rng.gauss(0, 0.012), rng.gauss(0, 0.012))
    if rng.random() < 0.55:
        block(m, M, 0.0, 0.14, 0.52, 1.07)                                               # base slab
        block(m, M, 0.14, 0.64, 0.42, 0.96, tx=0.4, ty=0.94)                             # chest
        lid_yaw = rng.choice((0.0, 0.0, rng.uniform(-0.18, 0.18)))                        # some lids pushed askew
        block(m, M @ Matrix.Rotation(lid_yaw, 4, "Z"), 0.64, 0.74, 0.49, 1.03, skip=())
    else:
        block(m, M_at(x, y, G - 0.06, yaw, rng.uniform(-0.04, 0.04), rng.uniform(-0.05, 0.05)), 0.0, 0.17, 0.45, 0.98)
        if rng.random() < 0.6:                                                           # a cross in relief
            block(m, M, 0.15, 0.2, 0.05, 0.6, cy=0.1)
            block(m, M, 0.15, 0.2, 0.26, 0.05, cy=0.3)
        prism_y(m, M @ T(0.0, 1.05, -0.04), slab_outline("round", 0.62, 0.75, rng), 0.12)
    return M


def angel(P, x, y, f, rng):
    """A praying angel on a pedestal (2.4 m), wings swept back and up past its bowed head."""
    yaw = yaw_box(f) + rng.gauss(0, 0.08)
    M = M_at(x, y, G, yaw)
    m = P.m("dino_grey")
    block(m, M, -0.04, 0.22, 0.46, 0.46)                                                 # step
    block(m, M, 0.22, 0.95, 0.32, 0.32)                                                  # pedestal
    block(m, M, 0.95, 1.05, 0.36, 0.36, skip=())                                         # pedestal cap
    block(m, M, 1.05, 1.95, 0.25, 0.19, tx=0.15, ty=0.11)                                # robe
    block(m, M, 1.93, 2.17, 0.17, 0.11, tx=0.12, ty=0.08)                                # chest + shoulders
    ball(m, M, (0.0, -0.05, 2.29), 0.105, 6, 4, (0.95, 1.0, 1.15))                       # bowed head
    block(m, M, 1.97, 2.13, 0.04, 0.035, cy=-0.16, skip=())                              # praying hands
    for sx in (-1, 1):
        tube(m, M @ Vector((sx * 0.14, -0.02, 2.1)), M @ Vector((sx * 0.025, -0.15, 2.04)), 0.032, 4)
    wing = [(0.0, 0.0), (0.12, -0.42), (0.32, -0.25), (0.48, 0.18), (0.42, 0.62), (0.16, 0.5)]
    for sx in (-1, 1):
        prism_y(m, M @ T(sx * 0.08, 0.12, 1.98) @ Matrix.Rotation(sx * 0.55, 4, "Z"), [(sx * u, v) for u, v in wing],
                0.045, bottom=True)
    return 0.62


# ------------------------------------------------------------------ small props
def lantern(P, base, s=1.0, key="fire"):
    """An iron lantern standing on `base`: a glowing core between four corner bars under a pyramid roof.
    Returns the core's center."""
    iron = P.m("metal_dark")
    M = M_at(base.x, base.y, base.z)
    block(iron, M, 0.0, 0.04 * s, 0.11 * s, 0.11 * s, skip=())
    gl(P, block(P.glow, M, 0.04 * s, 0.3 * s, 0.072 * s, 0.072 * s), key)
    for sx, sy in ((-1, -1), (1, -1), (1, 1), (-1, 1)):
        tube(iron, M @ Vector((sx * 0.09 * s, sy * 0.09 * s, 0.04 * s)), M @ Vector((sx * 0.09 * s, sy * 0.09 * s,
                                                                                     0.3 * s)), 0.012 * s, 3)
    block(iron, M, 0.3 * s, 0.33 * s, 0.13 * s, 0.13 * s, skip=())
    pyramid(iron, M, 0.33 * s, 0.47 * s, 0.11 * s, 0.11 * s)
    return M @ Vector((0.0, 0.0, 0.17 * s))


def candles(P, c, n, rng, spread=0.32, tag=None, on=None):
    """A cluster of n wax candles around c (on the ground, or on a surface at height `on`); tag: one light."""
    z0 = G if on is None else on
    for _ in range(n):
        x, y = c.x + rng.uniform(-spread, spread), c.y + rng.uniform(-spread, spread)
        h, r = rng.uniform(0.1, 0.32), rng.uniform(0.022, 0.04)
        tube(P.m("bone"), (x, y, z0 - 0.01), (x, y, z0 + h), r, segs=5, caps=True)
        gl(P, spike(P.glow, (x, y, z0 + h + 0.005), (x, y, z0 + h + 0.075), r * 0.75, segs=3), "amber")
    P.n("candles", n)
    if tag:
        P.lamp(tag, "POINT", (c.x, c.y, z0 + 0.4), C_CANDLE, P_CANDLE, size=0.3)
        halo(P.halos, (c.x, c.y, z0 + 0.25), 0.9, "amber", planes=1)


def uplight(P, pos, target, key, power, tag, deg=40.0):
    """A ground can (metal) with a glowing lens and a SPOT on the target."""
    pos, target = Vector(pos), Vector(target)
    d = (target - pos).normalized()
    tube(P.m("metal_dark"), pos - d * 0.05, pos + d * 0.16, 0.085, segs=6)
    lens = pos + d * 0.16
    gl(P, disc(P.glow, lens, d, 0.07, 6), key)
    P.lamp(tag, "SPOT", lens + d * 0.04, C_GREEN if key == "green" else C_PURPLE, power, target=target, size=0.1,
           spot_deg=deg)
    P.n("uplights")


COFFIN = [(-0.16, -1.0), (0.16, -1.0), (0.31, 0.45), (0.21, 1.0), (-0.21, 1.0), (-0.31, 0.45)]
CH = 0.42


def scaled(pts, sx, sy):
    return [(x * sx, y * sy) for x, y in pts]


def hinged_lid(P, M, deg=None):
    """The lid as a hinged part (CONTRACT.md "Hinged parts"), modelled closed, 2 mm over the rim. It turns about its
    long shoulder-to-foot edge on the side away from the DJ (the open lid stands behind what it reveals); the sign of
    open_deg is worked out so a positive right-hand turn about the axis lifts the free edge off the coffin."""
    lid = scaled(COFFIN, 1.06, 1.03)
    R3 = M.to_3x3()
    hs = -1.0 if (R3 @ Vector((1.0, 0.0, 0.0))).dot(DJ - M @ Vector((0.0, 0.0, CH))) > 0 else 1.0   # hinge side
    z = CH + 0.002
    foot, shoulder = M @ Vector((hs * lid[1][0], lid[1][1], z)), M @ Vector((hs * lid[2][0], lid[2][1], z))
    bm = bmesh.new()
    prism_z(bm, M, lid, z, z + 0.06, top=True, bottom=True)
    axis = (shoulder - foot).normalized()
    lift = R3 @ Vector((0.0, 0.0, 1.0))                                    # the lid's outward normal
    turn = 1.0 if axis.cross(M @ Vector((0.0, -0.1, z)) - foot).dot(lift) > 0 else -1.0
    deg = 100.0 + 3.0 * (len(P.hinged) % 5) if deg is None else deg
    P.hinged.append([bm, "wood_dark", tuple(foot), tuple(axis), turn * deg, None])   # delay set in build()


def coffin(P, M, kind, rng, lid_deg=None):
    """A hexagonal coffin lying along local Y (head +Y), bottom at local z 0. kind: closed (its lid swings open at the
    drop: CONTRACT.md hinged parts; inside, a faint green glow), glow (open, empty, a dim green glow inside), skel
    (open, a skeleton on a dim red glowing lining). Open coffins' lids are placed by the caller."""
    wd = P.m("wood_dark")
    _, fl = tray_z(wd, M, COFFIN, scaled(COFFIN, 0.82, 0.94), 0.0, CH, 0.06)
    if kind == "closed":
        gl(P, floor_face(P.glow, fl), "green_dim")
        hinged_lid(P, M, lid_deg)
        P.n("coffins")
        P.n("coffins_hinged")
        return
    if kind == "glow":
        gl(P, floor_face(P.glow, fl), "green_dim")
    else:
        gl(P, floor_face(P.glow, fl), "red_dim")                                         # lit lining (glows red)
        if kind == "skel":
            b = P.m("bone")
            ball(b, M, (0.0, 0.7, 0.17), 0.1, 6, 4, (0.85, 1.1, 0.8))                    # skull
            tube(b, M @ Vector((0.0, 0.58, 0.12)), M @ Vector((0.0, -0.15, 0.11)), 0.02, 3)
            for k in range(3):                                                           # ribs
                block(b, M, 0.1, 0.15, 0.13 - 0.015 * k, 0.018, cy=0.45 - 0.1 * k, skip=())
            for sx in (-1, 1):                                                           # legs
                tube(b, M @ Vector((sx * 0.06, -0.18, 0.1)), M @ Vector((sx * 0.08, -0.88, 0.1)), 0.022, 3)
    P.n("coffins")
    P.n("coffins_open")


def coffin_lid(P, M):
    prism_z(P.m("wood_dark"), M, scaled(COFFIN, 1.06, 1.03), 0.0, 0.06, top=True, bottom=True)


def upright(M, lean_back=0.1, z=0.0):
    """Frame that stands a coffin (lying along local Y, bottom z 0) on its foot: the lid side faces local -Y."""
    th = math.pi / 2 - lean_back
    return M @ T(0.0, 0.0, z + math.sin(th) * 1.0 + 0.02) @ Matrix.Rotation(th, 4, "X")


def bone_arm(b, base, d1, d2, curls):
    """A skeletal arm (into bmesh b) out of a pit: upper arm along d1, forearm along d2, a clawing hand
    whose four fingers curl by `curls`."""
    d1, d2 = Vector(d1).normalized(), Vector(d2).normalized()
    e = base + d1 * 0.34
    w = e + d2 * 0.29
    tube(b, base, e, 0.038, 4)
    tube(b, e, w, 0.03, 4)
    side = d2.cross(UP)
    side = side.normalized() if side.length > 1e-3 else Vector((1.0, 0.0, 0.0))
    palm = w + d2 * 0.08
    tube(b, w, palm, 0.032, 4, r2=0.04)
    curl = d2.cross(side).normalized()
    for k in range(4):
        o = palm + side * ((k - 1.5) * 0.022)
        tip = o + (d2 + side * (k - 1.5) * 0.35).normalized() * 0.085 + curl * curls[k]
        tube(b, o, tip, 0.012, 3)
    tube(b, w + side * 0.03, w + (side + d2).normalized() * 0.08, 0.013, 3)


# ------------------------------------------------------------------ features
def mausoleum(P, s, y, rng, k):
    """A gothic mausoleum facing the crowd: plinth and steps, walls with corner pilasters, a steep slate gable with a
    round window, a pointed doorway glowing dim green inside iron gates, lanterns, lancet side windows, a cross."""
    f = face_dir(s)
    yaw = yaw_box(f)
    c = strip_pt(s, y, MAUS_D)
    M = M_at(c.x, c.y, G, yaw)
    R3 = M.to_3x3()
    W, D, H, PL = MAUS_W, MAUS_DP, MAUS_H, MAUS_PL
    st, tr, ir = P.m("stone"), P.m("dino_grey"), P.m("metal_dark")
    yf = -D / 2
    block(tr, M, -0.05, PL, W / 2 + 0.35, D / 2 + 0.35)                                 # plinth
    for i, z1 in enumerate((0.24, 0.12)):                                                # steps
        block(tr, M, -0.05, z1, 0.95 + 0.1 * i, 0.19, cy=yf - 0.35 - 0.19 - 0.38 * i)
    block(st, M, PL, PL + H, W / 2, D / 2)                                               # walls
    for sx in (-1, 1):
        for sy in (-1, 1):
            block(tr, M, PL, PL + H, 0.21, 0.21, cx=sx * W / 2, cy=sy * D / 2)            # corner pilasters
    zc = PL + H
    block(tr, M, zc, zc + 0.24, W / 2 + 0.3, D / 2 + 0.3, skip=())                       # cornice
    zr = zc + 0.24
    prism_y(ir, M @ T(0, 0, zr), [(-W / 2 - 0.42, 0.0), (W / 2 + 0.42, 0.0), (0.0, 1.4)], D + 0.84, bottom=True)
    yg = -(D + 0.84) / 2
    gz = zr + 0.52
    gl(P, disc(P.glow, M @ Vector((0.0, yg - 0.01, gz)), R3 @ Vector((0, -1, 0)), 0.26, 8), "purple_dim")
    ring_y(tr, M, 0.0, gz, 0.37, 0.25, 0.12, segs=8, cy=yg - 0.04)                       # round window frame
    for sx in (-1, 1):                                                                   # gable edge copings
        tube(tr, M @ Vector((sx * (W / 2 + 0.42), yg - 0.06, zr + 0.02)), M @ Vector((0.0, yg - 0.06, zr + 1.42)),
             0.07, 4)
    ya = yg + 0.12                                                                       # cross on the apex
    block(tr, M, zr + 1.3, zr + 2.1, 0.05, 0.05, cy=ya, skip=())
    block(tr, M, zr + 1.72, zr + 1.84, 0.24, 0.05, cy=ya, skip=())
    # doorway: the lit interior (glow), a stone frame with a pointed hood, a name tablet
    door = [(-0.6, PL), (0.6, PL), (0.6, PL + 1.65), (0.42, PL + 2.1), (0.0, PL + 2.42), (-0.42, PL + 2.1),
            (-0.6, PL + 1.65)]
    pl = Plane(M @ Vector((0.0, yf - 0.012, 0.0)), R3 @ Vector((1, 0, 0)), R3 @ Vector((0, 0, 1)))
    gl(P, flat(P.glow, pl, door), "green_dim")
    for sx in (-1, 1):
        block(tr, M, PL, PL + 1.72, 0.12, 0.17, cx=sx * 0.74, cy=yf - 0.1)
        tube(tr, M @ Vector((sx * 0.74, yf - 0.12, PL + 1.66)), M @ Vector((0.0, yf - 0.12, PL + 2.64)), 0.12, 4)
    block(tr, M, PL + 2.72, PL + 2.97, 0.58, 0.05, cy=yf - 0.05, skip=())
    # iron gates: at y -25 the left leaf swung open; at y -50 both open around a coffin standing in the doorway
    both = k == 1
    for sx in (-1, 1):
        ang = rng.uniform(1.3, 1.5) if both else (rng.uniform(1.1, 1.35) if sx < 0 else rng.uniform(0.0, 0.12))
        hinge = Vector((sx * 0.6, yf - 0.05, PL))
        d = Vector((-sx * math.cos(ang), -math.sin(ang), 0.0))
        for i in range(5):
            p = hinge + d * (0.06 + 0.12 * i)
            tube(ir, M @ p, M @ (p + Vector((0, 0, 2.0))), 0.014, 3)
            spike(ir, M @ (p + Vector((0, 0, 2.0))), M @ (p + Vector((0, 0, 2.12))), 0.025, 3)
        for z in (0.12, 1.0, 1.92):
            tube(ir, M @ (hinge + Vector((0, 0, z))), M @ (hinge + d * 0.6 + Vector((0, 0, z))), 0.016, 3)
    if both:                                                                             # the coffin in the doorway
        coffin(P, upright(M @ T(0.04, yf - 0.06, 0.0) @ Matrix.Rotation(0.12, 4, "Z"), 0.06, PL), "closed", rng,
               lid_deg=100.0)                                                    # its lid swings out at the drop
    else:                                                                                # an open coffin beside it
        sx = -s                                                                          # on the stage side
        coffin(P, upright(M @ T(sx * 1.45, yf - 0.55, 0.0) @ Matrix.Rotation(-sx * 0.35, 4, "Z"), 0.13), "skel", rng)
    # door lanterns hanging from wall brackets
    for sx in (-1, 1):
        arm_end = M @ Vector((sx * 1.12, yf - 0.32, PL + 2.25))
        tube(ir, M @ Vector((sx * 1.12, yf, PL + 2.25)), arm_end, 0.018, 3)
        tube(ir, arm_end, arm_end - Vector((0, 0, 0.17)), 0.008, 3)
        lantern(P, arm_end - Vector((0, 0, 0.17 + 0.4)), s=0.85)
    # lancet windows in the side walls (one glows purple, one red), sills and hoods
    for sx in (-1, 1):
        o = M @ Vector((sx * (W / 2 + 0.012), 0.25, 0.0))
        pls = Plane(o, R3 @ Vector((0, sx, 0)), R3 @ Vector((0, 0, 1)))
        gl(P, flat(P.glow, pls, [(-0.24, PL + 1.0), (0.24, PL + 1.0), (0.24, PL + 2.0), (0.0, PL + 2.4),
                                  (-0.24, PL + 2.0)]), "purple_dim" if sx * s < 0 else "red_dim")
        block(tr, M, PL + 0.86, PL + 1.0, 0.1, 0.4, cx=sx * (W / 2 + 0.06), cy=0.25, skip=())
        for su in (-1, 1):
            tube(tr, M @ Vector((sx * (W / 2 + 0.06), 0.25 + su * 0.34, PL + 1.98)),
                 M @ Vector((sx * (W / 2 + 0.06), 0.25, PL + 2.58)), 0.07, 4)
    # light: green from the doorway; a purple uplight on the facade from beside the steps
    tag = f"GyMaus{'R' if s > 0 else 'L'}{k}"
    P.lamp(tag + "_Door", "POINT", M @ Vector((0.0, yf - 0.75, PL + 1.1)), C_GREEN, P_DOOR, size=0.4)
    halo(P.halos, M @ Vector((0.0, yf - 0.4, PL + 1.25)), 2.8, "green", planes=1)
    sx = s                                                                               # the far (back) side
    uplight(P, M @ Vector((sx * 1.55, yf - 0.95, 0.08)), M @ Vector((-sx * 0.2, yf, zr + 0.6)), "purple", P_FACADE,
            tag + "_Up", deg=50)
    # footprint, keep-out
    pts = [M @ Vector((u, v, 0.0)) for u in (-W / 2 - 0.36, W / 2 + 0.36) for v in (yf - 1.15, D / 2 + 0.36)]
    P.take_rect(M, -W / 2 - 0.36, yf - 1.15, W / 2 + 0.36, D / 2 + 0.36, pad=0.15)
    P.exclude.append((round(min(p.x for p in pts) - 0.75, 2), round(min(p.y for p in pts) - 0.75, 2),
                      round(max(p.x for p in pts) + 0.75, 2), round(max(p.y for p in pts) + 0.75, 2)))
    P.n("mausoleums")


def open_grave(P, s, y, d, rng, k):
    """An open grave along f: a mounded dirt rim around a green-glowing pit with skeletal arms reaching out, a dirt
    heap with a shovel, the headstone at the head end, the empty coffin pulled out beside it with its lid."""
    f = face_dir(s)
    yaw = yaw_box(f)
    c = strip_pt(s, y, d)
    M = M_at(c.x, c.y, G, yaw)
    hw, hl, t = 0.5, 1.02, 0.34
    dirt = P.m("dirt")
    for sy in (-1, 1):
        block(dirt, M, -0.03, 0.2, hw + t, t / 2, tx=hw + t - 0.08, ty=t / 2 - 0.1, cy=sy * (hl + t / 2))
    for sx in (-1, 1):
        block(dirt, M, -0.03, 0.2, t / 2, hl, tx=t / 2 - 0.1, ty=hl, cx=sx * (hw + t / 2))
    gl(P, quad(P.glow, M @ Vector((-hw, -hl, 0.012)), M @ Vector((hw, -hl, 0.012)), M @ Vector((hw, hl, 0.012)),
               M @ Vector((-hw, hl, 0.012))), "green_dim")
    side = rng.choice((-1, 1))
    ball(dirt, M, (side * (hw + t + 0.62), 0.1, -0.06), 0.5, 7, 4, (1.25, 2.1, 0.8))      # dirt heap
    hp = M @ Vector((side * (hw + t + 0.62), -0.25, 0.25))                                 # shovel in the heap
    top = hp + Vector(((rng.uniform(-0.3, 0.3)), rng.uniform(-0.3, 0.3), 1.0))
    tube(P.m("wood"), hp, top, 0.022, 4)
    tube(P.m("wood"), top - (top - hp).normalized() * 0.02 + Vector((0.09, 0, 0)), top + Vector((-0.09, 0, 0)),
         0.018, 3)
    blade = hp - (top - hp).normalized() * 0.18
    tube(P.m("metal_grey"), blade, hp, 0.09, 4, r2=0.07)
    # the headstone at the head end (+Y local, the outer end), leaning back
    m = P.m(rng.choice(STONE_KEYS))
    prism_y(m, M @ T(0.0, hl + t + 0.12, -0.08) @ Matrix.Rotation(-0.2, 4, "X"),
            slab_outline(rng.choice(("round", "pointed")), 0.66, 1.08, rng), 0.14)
    # arms
    n = rng.choice((2, 3, 3))
    spots = [(-0.22, -0.45), (0.2, 0.05), (-0.1, 0.55)][:n]
    for i, (ax, ay) in enumerate(spots):
        base = M @ Vector((ax, ay, -0.25))
        if i == 0:                                       # grasping the foot rim
            d1 = M.to_3x3() @ Vector((0.05, -0.55, 1.0))
            d2 = M.to_3x3() @ Vector((rng.uniform(-0.2, 0.2), -1.0, 0.15))
        else:                                            # reaching up
            d1 = M.to_3x3() @ Vector((rng.uniform(-0.3, 0.3), rng.uniform(-0.3, 0.3), 1.0))
            d2 = M.to_3x3() @ Vector((rng.uniform(-0.45, 0.45), rng.uniform(-0.45, 0.45), 1.0))
        bone_arm(P.m("bone"), base, d1, d2, [rng.uniform(0.0, 0.03) for _ in range(4)])
    P.n("arms", n)
    if k == 0:                       # the two front graves: one more arm lies in the pit and swings up at the drop
        R3 = M.to_3x3()
        arm, sh = bmesh.new(), M @ Vector((0.34, -0.9, 0.06))
        bone_arm(arm, sh, R3 @ Vector((0.0, 1.0, 0.08)), R3 @ Vector((-0.1, 1.0, 0.22)), (0.01, 0.025, 0.015, 0.03))
        axis = R3 @ Vector((1.0, 0.0, 0.0))
        turn = 1.0 if axis.cross(M @ Vector((0.32, -0.4, 0.12)) - sh).dot(UP) > 0 else -1.0
        P.hinged.append([arm, "bone", tuple(sh), tuple(axis), turn * 100.0, 0.7 if s > 0 else 0.8])
        P.n("arms_hinged")
    # the coffin pulled out beside the pit (other side from the heap), open and empty, its lid against it
    cm = M @ T(-side * (hw + t + 0.55), -0.15, 0.0) @ Matrix.Rotation(rng.uniform(-0.25, 0.25), 4, "Z")
    coffin(P, cm, "glow", rng)
    coffin_lid(P, cm @ T(-side * 0.74, 0.1, 0.1) @ Matrix.Rotation(-side * 0.35, 4, "Y"))      # propped toward it
    # light, halo, footprint
    P.lamp(f"GyGrave{'R' if s > 0 else 'L'}{k}", "POINT", M @ Vector((0.0, 0.0, 0.45)), C_GREEN, P_GRAVE, size=0.4)
    halo(P.halos, M @ Vector((0.0, 0.0, 0.6)), 2.0, "green", planes=1)
    P.take_rect(M, -hw - t, -hl - t, hw + t, hl + t + 0.3)                                # pit, rim, headstone
    P.take_rect(M, side * (hw + t), -1.0, side * (hw + t + 1.3), 1.2, pad=0.2)            # heap and shovel
    P.take_rect(M, -side * (hw + t + 0.1), -1.2, -side * (hw + t + 1.65), 1.0)            # coffin and its lid
    P.n("graves")


def hero(P, s, y, d, kind, key, rng, k):
    f = face_dir(s)
    p = strip_pt(s, y, d)
    if kind == "angel":
        r = angel(P, p.x, p.y, f, rng)
        aim_z = G + 1.85
    elif kind == "celtic":
        r = celtic(P, p.x, p.y, f, rng, big=True)
        aim_z = G + 1.9
    else:
        r = obelisk(P, p.x, p.y, f, rng, big=True)
        aim_z = G + 2.2
    P.take(p.x, p.y, r)
    side = Vector((f.y, -f.x, 0.0)) * rng.choice((-1, 1))
    can = p + f * 1.35 + side * 0.45 + Vector((0, 0, 0.08))
    uplight(P, can, Vector((p.x, p.y, aim_z)), key, P_HERO, f"GyHero{'R' if s > 0 else 'L'}{k}", deg=62)
    P.take(can.x, can.y, 0.25)
    P.n("heroes")


def scattered_coffins(P, s, n, rng):
    """Coffins in the gaps: closed (lids hinged; some with candles at the head), open with a skeleton (lid beside)."""
    placed, tries = 0, 0
    kinds = ["closed", "closed", "skel", "closed", "skel"]
    while placed < n and tries < 400:
        tries += 1
        y, d = rng.uniform(Y_BACK + 2.5, Y_FRONT - 2.5), rng.uniform(D_IN + 1.3, D_OUT - 1.4)
        p = strip_pt(s, y, d)
        if not P.free(p.x, p.y, 1.1):
            continue
        yaw = rng.uniform(-math.pi, math.pi)
        M = M_at(p.x, p.y, G - 0.02, yaw, rng.gauss(0, 0.03), rng.gauss(0, 0.03))
        kind = kinds[placed % len(kinds)]
        coffin(P, M, kind, rng)
        if kind == "skel":
            sx = rng.choice((-1, 1))
            coffin_lid(P, M @ T(sx * 0.68, 0.0, 0.0) @ Matrix.Rotation(rng.uniform(-0.25, 0.25), 4, "Z"))
            P.take_rect(M, min(0.0, sx) * 1.1 - 0.36, -1.1, max(0.0, sx) * 1.1 + 0.36, 1.1)
        else:
            if rng.random() < 0.5:                      # candles at its head, on the ground: nothing rides the lid
                c = M @ Vector((0.0, 1.2, 0.0))
                candles(P, c, 3, rng, spread=0.1)
                P.take(c.x, c.y, 0.22)
            P.take_rect(M, -0.36, -1.06, 0.36, 1.06)
        placed += 1


def chests(P, s, n, rng):
    placed, tries = 0, 0
    while placed < n and tries < 400:
        tries += 1
        y, d = rng.uniform(Y_BACK + 1.6, Y_FRONT - 1.6), rng.uniform(D_IN + 1.1, D_OUT - 1.3)
        p = strip_pt(s, y, d)
        if not P.free(p.x, p.y, 1.2):
            continue
        P.take_rect(chest_tomb(P, p.x, p.y, face_dir(s), rng), -0.52, -1.07, 0.52, 1.18)
        placed += 1
        P.n("chest_tombs")


def ghoul_spots(P, s, n, rng):
    """Reserve n spots between the stones for ghoul people (the crowd mesh draws them; facing the stage, roughly)."""
    placed, tries = 0, 0
    while placed < n and tries < 800:
        tries += 1
        y, d = rng.uniform(Y_BACK + 1.5, Y_FRONT - 1.5), rng.uniform(D_IN + 0.7, D_OUT - 1.0)
        p = strip_pt(s, y, d)
        if not P.free(p.x, p.y, 0.5):
            continue
        to = (DJ - p)
        to.z = 0.0
        yaw = yaw_person(to.normalized()) + rng.uniform(-0.6, 0.6)
        pose = rng.choices(("down", "up", "one", "hips"), weights=(45, 30, 15, 10))[0]
        P.people.append((round(p.x, 2), round(p.y, 2), round(yaw, 3), pose))
        P.take(p.x, p.y, 0.6)
        placed += 1


def stone_field(P, s, rng):
    """The grid of stones: rows across the facing direction, cut by the strip's diagonal edges, with jitter, gaps
    and a mix of kinds; every footprint checked against what is already there."""
    f = face_dir(s)
    w = Vector((-f.y, f.x, 0.0))
    if w.y > 0:
        w = -w
    o = strip_pt(s, Y_FRONT, D_IN)
    du, dw = 1.05, 0.92
    kinds = ("slab", "cross", "obelisk", "celtic", "small")
    weights = (58, 16, 6, 5, 15)
    for i in range(-2, 42):
        for j in range(-14, 74):
            if rng.random() < 0.05:                     # irregular gaps
                continue
            p = o - f * (i * du + rng.uniform(-0.12, 0.12)) + w * (j * dw + rng.uniform(-0.1, 0.1))
            d = strip_d(s, p.x, p.y)
            if not (D_IN + 0.3 <= d <= D_OUT - 0.55 and Y_BACK + 0.5 <= p.y <= Y_FRONT - 0.5):
                continue
            kind = rng.choices(kinds, weights=weights)[0]
            r = {"slab": 0.27, "cross": 0.25, "obelisk": 0.45, "celtic": 0.35, "small": 0.18}[kind]
            if not P.free(p.x, p.y, r):
                if kind in ("obelisk", "celtic") and P.free(p.x, p.y, 0.27):
                    kind, r = "slab", 0.27
                else:
                    continue
            if kind == "slab":
                r = slab(P, p.x, p.y, f, rng)
            elif kind == "small":
                r = slab(P, p.x, p.y, f, rng, small=True)
            elif kind == "cross":
                r = cross(P, p.x, p.y, f, rng)
            elif kind == "obelisk":
                r = obelisk(P, p.x, p.y, f, rng)
            else:
                r = celtic(P, p.x, p.y, f, rng)
            P.take(p.x, p.y, r)
            P.n("stones")
            P.n("stone_" + kind)
            if kind in ("slab", "cross") and rng.random() < 0.05:   # a few candles left at the stone (glow only)
                c = p + f * rng.uniform(0.3, 0.38)
                if P.free(c.x, c.y, 0.15):
                    candles(P, c, rng.randint(2, 4), rng, spread=0.1)
                    P.take(c.x, c.y, 0.15)


def gap_fill(P, s, rng, tries=230):
    """Squeeze small stones into the gaps the grid left beside the big features (old cemeteries fill every gap)."""
    f = face_dir(s)
    for _ in range(tries):
        y, d = rng.uniform(Y_BACK + 0.5, Y_FRONT - 0.5), rng.uniform(D_IN + 0.3, D_OUT - 0.55)
        p = strip_pt(s, y, d)
        kind = rng.choices(("small", "slab", "cross"), weights=(55, 30, 15))[0]
        if not P.free(p.x, p.y, {"small": 0.18, "slab": 0.27, "cross": 0.25}[kind]):
            continue
        if kind == "cross":
            r = cross(P, p.x, p.y, f, rng)
        else:
            r = slab(P, p.x, p.y, f, rng, small=kind == "small")
        P.take(p.x, p.y, r)
        P.n("stones")
        P.n("stone_fill_" + kind)


def fence(P, s, rng):
    """Low wrought-iron fence on the strip's outer edge: pickets with spear tips, two rails, iron posts, stone pillars
    at the ends, lantern posts (every fourth); lights in three of them."""
    a, b = strip_pt(s, Y_FRONT - 0.3, D_OUT - 0.3), strip_pt(s, Y_BACK + 0.3, D_OUT - 0.3)
    L = (b - a).length
    t = (b - a) / L
    iron = P.m("metal_dark")
    yaw = math.atan2(t.y, t.x)
    n_bays = round(L / 3.42)
    posts = []
    for k in range(n_bays + 1):
        p = a.lerp(b, k / n_bays)
        Mp = M_at(p.x, p.y, G, yaw)
        posts.append(p)
        if k in (0, n_bays):
            block(P.m("stone"), Mp, -0.03, 1.5, 0.22, 0.22)
            block(P.m("stone"), Mp, 1.5, 1.6, 0.27, 0.27, skip=())
            pyramid(P.m("stone"), Mp, 1.6, 1.9, 0.22, 0.22)
            continue
        if k % 4 == 2:                                   # lantern post
            block(iron, Mp, -0.02, 2.15, 0.05, 0.05)
            core = lantern(P, p + Vector((0, 0, 2.15)))
            halo(P.halos, core, 0.95, "amber", planes=1)
            if k in (2, 10, 18):
                P.lamp(f"GyLantern{'R' if s > 0 else 'L'}{k:02d}", "POINT", core, C_FIRE, P_LANTERN, size=0.12)
            P.n("lanterns")
        else:
            block(iron, Mp, -0.02, 1.28, 0.042, 0.042)
            pyramid(iron, Mp, 1.28, 1.4, 0.06, 0.06)
    for z in (0.16, 0.9):
        tube(iron, a + Vector((0, 0, z)), b + Vector((0, 0, z)), 0.018, 4)
    n_p = int(L / 0.42)
    for i in range(1, n_p):
        p = a + t * (i * L / n_p)
        if min((p - q).length for q in posts) < 0.16:
            continue
        tube(iron, p + Vector((0, 0, -0.02)), p + Vector((0, 0, 1.0)), 0.016, 3)
        spike(iron, p + Vector((0, 0, 1.0)), p + Vector((0, 0, 1.13)), 0.032, 3)
        P.n("pickets")


def front_candles(P, s, rng):
    """Candle clusters with a light (in front of stones near the crowd edge), and a few unlit ones on the graves."""
    for k, (y, d) in enumerate(PLAN[s]["candles"]):
        c = strip_pt(s, y, d)
        candles(P, c, 7, rng, spread=0.35, tag=f"GyCandle{'R' if s > 0 else 'L'}{k}")
        P.take(c.x, c.y, 0.5)


def keep_out(P, s):
    """Keep-out rectangles over the whole strip, as a staircase of 5 m steps: each one starts past the crowd's edge
    (the crowd reaches crowd_half + ~0.6 m) and ends past the fence."""
    for k in range(12):
        y_hi = Y_FRONT - 5.0 * k
        y_lo = y_hi - 5.0
        x_in, x_out = crowd_half(y_hi) + 2.85, crowd_half(y_lo) + D_OUT + 0.6
        if s > 0:
            P.exclude.append((round(x_in, 2), y_lo, round(x_out, 2), y_hi))
        else:
            P.exclude.append((round(-x_out, 2), y_lo, round(-x_in, 2), y_hi))


# ------------------------------------------------------------------ module entry
def build(rng):
    P = Parts()
    for s in SIDES:
        for k, y in enumerate(MAUS_Y):
            P.run("mausoleums", mausoleum, s, y, rng, k)
    for s in SIDES:
        for k, (y, d) in enumerate(PLAN[s]["graves"]):
            P.run("graves", open_grave, s, y, d, rng, k)
    for s in SIDES:
        for k, (y, d, kind, key) in enumerate(PLAN[s]["heroes"]):
            P.run("heroes", hero, s, y, d, kind, key, rng, k)
        P.run("candles", front_candles, s, rng)
    for s in SIDES:
        P.run("coffins", scattered_coffins, s, 5, rng)
        P.run("chest_tombs", chests, s, 7, rng)
        P.run("ghouls", ghoul_spots, s, 10, rng)
    for s in SIDES:
        P.run("stones", stone_field, s, rng)
        P.run("stones", gap_fill, s, rng)
        P.run("fence", fence, s, rng)
        keep_out(P, s)
    print(f"[GRAVEYARD] tris by feature {P.tally}; counts {P.counts}; lights {len(P.lights)}; people {len(P.people)}; "
          f"beams {len(P.beams.faces)} quads; halos {len(P.halos.faces)} quads", flush=True)
    lids = sorted((h for h in P.hinged if h[5] is None), key=lambda h: (Vector(h[2]) - DJ).length)
    for i, h in enumerate(lids):                         # the lids creak open from the stage outward over 0..0.6
        h[5] = round(0.6 * i / max(1, len(lids) - 1), 3)
    print(f"[GRAVEYARD] hinged: {len(P.hinged)} parts, {sum(tris(h[0]) for h in P.hinged)} tris", flush=True)
    lit = []
    for key, bm in P.lit.items():
        if len(bm.faces):
            lit.append((bm, key))
        else:
            bm.free()
    return {"lit": lit, "glow": [P.glow], "beams": [P.beams], "halos": [P.halos], "lights": P.lights,
            "exclude": P.exclude, "people": P.people, "hinged": [tuple(h) for h in P.hinged]}
