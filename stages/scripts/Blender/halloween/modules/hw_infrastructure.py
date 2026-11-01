"""GRAVEYARD SHIFT grounds module INFRASTRUCTURE: front of house, delay towers and light masts in the crowd
(Blender 4.5, headless).

  FOH mausoleum (0, -31)        an open gothic loggia of stone, 8 x 4 m on a 1.2 m podium: corner piers with pinnacles,
                                pointed arches over the desk bays, a front parapet that hides the desks from the stage, a
                                stone roof at the DJ's eye height (seen edge-on) carrying the LED banners: GRAVEYARD SHIFT
                                in a dripping 5x7 font, orange toward the stage and green toward the crowd behind it.
                                Sound and lighting desks with hooded engineers, a roof platform with two follow spots
                                aimed at the DJ's head (white soft beams), torch sconces, an iron plot fence with a gate.
  Crypt towers (+-17, -42),     delay towers: a stone plinth with glowing niches, a tapering iron lattice to 14 m with
  (+-15, -65)                   purple LED strips on its legs, a skull with red eyes on the top platform facing the stage,
                                a purple sky beam, a line array toward the back of the crowd; purple uplight and wash.
  Lantern masts (+-30, -58),    gothic iron lamp posts on stone bases, three hanging lanterns each, an amber wash on the
  (+-24, -78)                   back of the crowd.
Pre-drop meters, Z up, the DJ at the origin facing -Y; everything stands on the field floor z = GROUND_Z.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "grounds"))
from kit import *  # noqa: E402,F401,F403
import kit as _kit  # noqa: E402  (read-only: the 5x7 font for the drips)

NAME = "infrastructure"
BAKE_SIZE = 2048

G = GROUND_Z
EYE_Z = 2.65                                     # DJ eye height (pre-drop): the FOH roof top sits here, seen edge-on
DJ_HEAD = Vector((0.0, 0.9, 2.7))                # the follow spots aim here (hw_stage DJ_HEAD, pre-drop)
UP = Vector((0.0, 0.0, 1.0))
I4 = Matrix.Identity(4)
KEEP_OUT = 0.75                                  # crowd keep-out beyond a fence line or a plinth

FOH_Y = -31.0
FOH_FENCE = (-5.2, -34.8, 5.2, -27.6)            # the iron plot fence around the FOH (gate at the back right)
TOWERS = ((-17.0, -42.0), (17.0, -42.0), (-15.0, -65.0), (15.0, -65.0))
TOWER_TOP = G + 12.6                             # platform under the skull (skull top ~14.1 m above the field)
MASTS = (((-30.0, -58.0), (-21.0, -50.0, G)), ((30.0, -58.0), (21.0, -50.0, G)),
         ((-24.0, -78.0), (-16.0, -69.0, G)), ((24.0, -78.0), (16.0, -69.0, G)))

C_PURPLE = (0.55, 0.15, 1.0)
C_WARM = (1.0, 0.72, 0.45)
C_AMBER = (1.0, 0.62, 0.30)
P_TOWER_UP, P_TOWER_WASH, P_MAST = 900.0, 1100.0, 2800.0


# ------------------------------------------------------------------ output collector
class Parts:
    def __init__(self):
        self.lit, self.glow, self.beams, self.halos = {}, bmesh.new(), bmesh.new(), bmesh.new()
        self.lights, self.exclude, self.people = [], [], []
        self.tally = {}

    def m(self, key):
        if key not in self.lit:
            self.lit[key] = bmesh.new()
        return self.lit[key]

    def count(self):
        return sum(tris(b) for b in self.lit.values()) + tris(self.glow)

    def run(self, name, fn, *args):
        n0 = self.count()
        fn(self, *args)
        self.tally[name] = self.tally.get(name, 0) + self.count() - n0

    def lamp(self, name, kind, pos, color, power, **kw):
        self.lights.append(light(name, kind, tuple(pos), color, power, **kw))


def gl(P, faces, key):
    glow_faces(P.glow, faces, key)
    return faces


def M_at(x, y, z, yaw=0.0, pitch=0.0, roll=0.0):
    return (Matrix.Translation((x, y, z)) @ Matrix.Rotation(yaw, 4, "Z") @ Matrix.Rotation(pitch, 4, "X")
            @ Matrix.Rotation(roll, 4, "Y"))


def T(x, y, z):
    return Matrix.Translation((x, y, z))


# ------------------------------------------------------------------ primitives (verts/faces only, normals outward;
# the same set as hw_graveyard.py, copied so each module stands alone)
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


def _basis(d):
    z = d.normalized()
    x = z.orthogonal().normalized()
    return x, z.cross(x)


def tube(bm, a, b, r, segs=4, r2=None, caps=False):
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
    pts = _ccw(list(pts))
    return [bm.faces.new([bm.verts.new(pl.p(u, v, w)) for u, v in pts])]


def halo_quad(bm, center, size, color, normal):
    """One glow sprite square facing `normal` (kit.halo's UV layout)."""
    c, n = Vector(center), Vector(normal).normalized()
    up = Vector((0, 0, 1)) if abs(n.z) < 0.95 else Vector((0, 1, 0))
    b = (up - n * up.dot(n)).normalized() * size / 2
    a = b.cross(n)
    col = BEAM_COLS.index(color)
    u0, u1 = col / len(BEAM_COLS), (col + 1) / len(BEAM_COLS)
    return quad(bm, c - a - b, c + a - b, c + a + b, c - a + b, uvs=[(u0, 0.0), (u1, 0.0), (u1, 1.0), (u0, 1.0)])


def soft_beam(bm, apex, direction, length, w0, w1, color, planes=2, v0=0.0):
    """kit.beam_planes starting at v0 of the texture's fade (v0 > 0 skips the bright apex: a softer beam)."""
    apex, d = Vector(apex), Vector(direction).normalized()
    s0 = d.cross(Vector((0, 0, 1)) if abs(d.z) < 0.95 else Vector((1, 0, 0))).normalized()
    col = BEAM_COLS.index(color)
    u0, u1 = (col + 0.02) / len(BEAM_COLS), (col + 0.98) / len(BEAM_COLS)
    end = apex + d * length
    faces = []
    for k in range(planes):
        s = (Matrix.Rotation(math.pi * k / planes, 3, d) @ s0).normalized()
        faces += quad(bm, apex - s * w0 / 2, apex + s * w0 / 2, end + s * w1 / 2, end - s * w1 / 2,
                      uvs=[(u0, v0), (u1, v0), (u1, 1.0), (u0, 1.0)])
    return faces


# ------------------------------------------------------------------ shared props
NO_DRIP = set("S$")                              # a drip under S reads as a dollar sign


def drip_text(P, pl, text, pixel, key, rng, cu=0.0, cv=0.0, drip=0.38):
    """kit.led_text centered at (cu, cv) of plane pl, plus drips: 1-3 shrinking pixels hanging under some of the
    letters' bottom pixels (the plan's dripping banner font). The letters themselves stay the plain 5x7 font."""
    tw, th = text_width(text, pixel), 7 * pixel
    o = pl.p(cu - tw / 2, cv - th / 2)
    led_text(P.glow, text, o, pl.r, pl.up, pixel=pixel, gap=0.2 * pixel, key=key)
    s = pixel * 0.8
    faces = []
    for ci, ch in enumerate(text.upper()):
        bottom = _kit._FONT.get(ch, _kit._FONT[" "])[6]
        if ch in NO_DRIP:
            continue
        for c, px in enumerate(bottom):
            if px != "#" or rng.random() > drip:
                continue
            for k in range(1, rng.choice((1, 1, 2, 2, 3)) + 1):
                w = s * (1.0 - 0.2 * k)
                u0 = (ci * 6 + c) * pixel + (s - w) / 2
                v0 = -k * pixel + (s - w) * 0.6
                a = o + pl.r * u0 + pl.up * v0
                faces += quad(P.glow, a, a + pl.r * w, a + pl.r * w + pl.up * w, a + pl.up * w)
    gl(P, faces, key)


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


def hooded(P, x, y, z0, yaw=0.0, h=1.8, reach=0.45, hand=0.56):
    """A crew member in a hooded black robe on a floor at z0, facing yaw (0 = the stage, +Y), hands forward."""
    M = M_at(x, y, z0, yaw)
    k = h / 1.8
    robe = P.m("canvas_black")
    block(robe, M, 0.0, 1.4 * k, 0.27 * k, 0.2 * k, tx=0.2 * k, ty=0.13 * k)              # robe
    block(robe, M, 1.36 * k, 1.5 * k, 0.22 * k, 0.14 * k, skip=())                        # shoulders
    ball(robe, M, (0.0, 0.0, 1.62 * k), 0.13 * k, 6, 4, (1.0, 1.05, 1.22))               # hood
    spike(robe, M @ Vector((0.0, -0.05 * k, 1.66 * k)), M @ Vector((0.0, -0.2 * k, 1.9 * k)), 0.09 * k, 4)
    for sx in (-1, 1):
        sh, hd = M @ Vector((sx * 0.21 * k, 0.0, 1.42 * k)), M @ Vector((sx * 0.16 * k, reach, hand * h))
        el = M @ Vector((sx * 0.25 * k, reach * 0.4, 1.12 * k))
        tube(robe, sh, el, 0.06 * k, 4)
        tube(robe, el, hd, 0.055 * k, 4, r2=0.045 * k)


def iron_fence(P, a, b, h=1.05, step=0.36, posts=(True, True)):
    """Wrought-iron fence run from ground point a to b: pickets with spear tips, two rails, posts at the ends flagged
    in `posts` (a corner gets one post, not one per run)."""
    iron = P.m("metal_dark")
    a, b = Vector((a[0], a[1], G)), Vector((b[0], b[1], G))
    L = (b - a).length
    t = (b - a) / L
    for z in (0.14, h - 0.12):
        tube(iron, a + UP * z, b + UP * z, 0.018, 4)
    n = max(2, int(L / step))
    for i in range(1, n):
        p = a + t * (i * L / n)
        tube(iron, p - UP * 0.02, p + UP * h, 0.015, 3)
        spike(iron, p + UP * h, p + UP * (h + 0.12), 0.03, 3)
    yaw = math.atan2(t.y, t.x)
    for p, on in zip((a, b), posts):
        if on:
            block(iron, M_at(p.x, p.y, G, yaw), -0.02, h + 0.15, 0.045, 0.045)
            pyramid(iron, M_at(p.x, p.y, G, yaw), h + 0.15, h + 0.3, 0.065, 0.065)


# ------------------------------------------------------------------ FOH mausoleum
def foh(P, rng):
    st, gr, dark, black = P.m("metal_dark"), P.m("dino_grey"), P.m("metal_dark"), P.m("canvas_black")   # st: granite
    y0, y1, yc = FOH_Y - 2.0, FOH_Y + 2.0, FOH_Y          # body y -33..-29 (y1 = the stage side)
    zd, zr = G + 1.2, EYE_Z                               # deck top, roof top
    # podium, base course, front parapet (hides the desks from the stage), side parapets
    block(st, I4, G - 0.03, zd, 4.0, 2.0, cy=yc)
    block(gr, I4, G - 0.03, G + 0.35, 4.12, 2.12, cy=yc)
    block(st, I4, zd, 0.7, 3.95, 0.15, cy=y1 - 0.15)
    block(gr, I4, 0.7, 0.8, 4.02, 0.21, cy=y1 - 0.15, skip=())
    for sx in (-1, 1):
        block(st, I4, zd, 0.7, 0.13, 1.7, cx=sx * 3.85, cy=yc - 0.3)
    fy_p = y1 + 0.012                                     # the parapet front: a blind arcade, a carved skull
    for i in range(8):
        if i in (3, 4):
            continue
        xc = -3.15 + 0.9 * i
        for su in (-1, 1):
            tube(gr, (xc + su * 0.3, fy_p, G + 0.45), (xc + su * 0.3, fy_p, 0.25), 0.045, 4)
            tube(gr, (xc + su * 0.3, fy_p, 0.23), (xc, fy_p, 0.55), 0.045, 4)
    skull(P, M_at(0.0, y1 + 0.18, zd + 0.05) @ Matrix.Rotation(math.pi, 4, "Z"), 0.55, "red_dim")   # above heads
    # corner piers (pinnacles above the roof), middle piers, pointed arches over the bays (front and back)
    for sx in (-1, 1):
        for py in (y1 - 0.25, y0 + 0.25):
            block(gr, I4, G - 0.03, zr - 0.25, 0.35, 0.35, cx=sx * 3.75, cy=py)
            block(gr, I4, zr, zr + 0.22, 0.24, 0.24, cx=sx * 4.18, cy=py + (0.17 if py > yc else -0.17))
            pyramid(gr, I4, zr + 0.22, zr + 1.25, 0.19, 0.19, cx=sx * 4.18, cy=py + (0.17 if py > yc else -0.17))
        for py, zb in ((y1 - 0.15, 0.7), (y0 + 0.15, zd)):
            block(gr, I4, zb, zr - 0.25, 0.17, 0.17, cx=sx * 1.33, cy=py)
    for py in (y1 - 0.15, y0 + 0.15):
        for xa, xb in ((-3.4, -1.5), (-1.16, 1.16), (1.5, 3.4)):
            xm = (xa + xb) / 2
            tube(gr, (xa, py, 1.22), (xm, py, 1.72), 0.07, 4)
            tube(gr, (xb, py, 1.22), (xm, py, 1.72), 0.07, 4)
    # stone roof at the DJ's eye height; the banners on its front and back edges
    block(gr, I4, zr - 0.25, zr, 4.4, 2.4, cy=yc, skip=())
    for sgn, key, edge in ((1, "orange", "ember"), (-1, "green", "green_dim")):
        fy = yc + sgn * 2.44
        block(black, I4, 1.7, zr + 0.01, 4.42, 0.04, cy=fy)
        pl = Plane((0.0, fy + sgn * 0.042, (1.7 + zr) / 2), (-sgn, 0, 0), (0, 0, 1))
        drip_text(P, pl, "GRAVEYARD SHIFT", 0.085, key, rng, cv=0.13)
        for v in (0.43, -0.45):
            gl(P, flat(P.glow, pl, [(-4.36, v - 0.012), (4.36, v - 0.012), (4.36, v + 0.012), (-4.36, v + 0.012)]),
               edge)
    # torch sconces on the front corner piers (glow only: the stage washes light the front)
    for sx in (-1, 1):
        wall = Vector((sx * 3.75, y1 + 0.1, 1.15))
        tube(dark, wall, wall + Vector((0, 0.28, 0.1)), 0.025, 3)
        cup = wall + Vector((0, 0.3, 0.12))
        tube(dark, cup - UP * 0.06, cup + UP * 0.06, 0.05, 5, r2=0.08)
        gl(P, spike(P.glow, cup + UP * 0.05, cup + UP * 0.36, 0.07, 4), "fire")
        halo(P.halos, cup + UP * 0.22, 0.9, "amber", planes=1)
    # desks: sound console (left), lighting console (right) with two monitors; hooded engineers behind them
    dy = y1 - 0.75
    for cx, w in ((-1.25, 2.4), (1.35, 1.9)):
        block(dark, I4, zd, zd + 0.74, w / 2, 0.45, cx=cx, cy=dy)
        block(dark, M_at(cx, dy, zd + 0.74, 0.0, 0.15), 0.0, 0.08, w / 2 - 0.03, 0.43, skip=())
        for sx in (-0.3, 0.3):                                        # gooseneck lamps
            lx = cx + sx * w
            tube(dark, (lx, dy + 0.4, zd + 0.85), (lx, dy + 0.15, zd + 1.2), 0.012, 3)
            gl(P, ball(P.glow, I4, (lx, dy + 0.12, zd + 1.19), 0.04, 6, 3), "bulb_warm")
    gl(P, flat(P.glow, Plane((-1.25, dy + 0.3, zd + 0.98), (1, 0, 0), (0, 0.4, 1)),
               [(-1.05, -0.07), (1.05, -0.07), (1.05, 0.07), (-1.05, 0.07)]), "ember")    # meter bridge
    block(dark, I4, zd + 0.84, zd + 1.12, 1.12, 0.05, cx=-1.25, cy=dy + 0.33)
    for mx, yaw in ((0.95, 0.12), (1.75, -0.12)):                    # lighting desk monitors
        tube(dark, (mx, dy + 0.35, zd + 0.85), (mx, dy + 0.35, zd + 1.1), 0.02, 4)
        Mm = M_at(mx, dy + 0.35, zd + 1.3, yaw, 0.12)
        block(dark, Mm, -0.2, 0.2, 0.31, 0.025, skip=())
        gl(P, flat(P.glow, Plane(Mm @ Vector((0.0, -0.03, 0.0)), Mm.to_3x3() @ Vector((1, 0, 0)),
                                 Mm.to_3x3() @ Vector((0, 0, 1))), [(-0.28, -0.17), (0.28, -0.17), (0.28, 0.17),
                                                                     (-0.28, 0.17)]), "purple_dim")
    for ex, ey in ((-1.8, dy - 0.95), (-0.65, dy - 1.0), (1.4, dy - 0.95)):
        hooded(P, ex, ey, zd, rng.uniform(-0.15, 0.15), h=rng.uniform(1.72, 1.86), reach=0.5)
    # flight cases with status LEDs at the back corners
    for cx, sz in ((-3.2, (0.6, 0.6, 1.0)), (3.2, (0.6, 0.8, 0.8))):
        block(dark, I4, zd, zd + sz[2], sz[0] / 2, sz[1] / 2, cx=cx, cy=y0 + 0.8)
        for k, key in enumerate(("green_dim", "red_dim", "amber")):
            gl(P, flat(P.glow, Plane((cx, y0 + 0.8 + sz[1] / 2 + 0.006, zd + sz[2] - 0.15 - 0.1 * k), (-1, 0, 0),
                                     (0, 0, 1)), [(-0.05, -0.02), (0.05, -0.02), (0.05, 0.02), (-0.05, 0.02)]), key)
    # roof platform (back half of the roof) with two follow spots on tripods and their hooded operators
    zp = zr + 0.4
    py0, py1 = y0 + 0.0, y0 + 2.2
    pyc = (py0 + py1) / 2
    for x in (-2.1, 2.1):
        for y in (py0 + 0.1, py1 - 0.1):
            tube(dark, (x, y, zr), (x, y, zp), 0.04, 4)
            tube(dark, (x, y, zp), (x, y, zp + 1.05), 0.03, 4)
    block(dark, I4, zp - 0.1, zp, 2.2, 1.1, cy=pyc, skip=())
    for z in (zp + 0.55, zp + 1.05):
        tube(dark, (-2.1, py0 + 0.1, z), (2.1, py0 + 0.1, z), 0.022, 4)
        for x in (-2.1, 2.1):
            tube(dark, (x, py0 + 0.1, z), (x, py1 - 0.1, z), 0.022, 4)
    for sx in (-0.95, 0.95):
        base = Vector((sx, py1 - 0.45, zp))
        body = base + Vector((0, 0, 1.38))
        d = (DJ_HEAD - body).normalized()
        for k in range(3):
            a = 2 * math.pi * k / 3 + 0.5
            tube(dark, base + Vector((0.42 * math.cos(a), 0.42 * math.sin(a), 0)), base + Vector((0, 0, 1.1)), 0.02,
                 3)
        tube(dark, base + Vector((0, 0, 1.1)), body, 0.035, 4)
        tube(dark, body - d * 0.75, body + d * 0.55, 0.15, 8, r2=0.18, caps=True)
        lens = body + d * 0.56
        gl(P, disc(P.glow, lens, d, 0.155, 8), "bulb_warm")
        halo_quad(P.halos, lens + d * 0.1, 1.5, "white", d)
        soft_beam(P.beams, lens + d * 0.04, d, (DJ_HEAD - lens).length - 4.0, 0.2, 0.8, "white", v0=0.5)
        hooded(P, sx, py1 - 1.4, zp, rng.uniform(-0.1, 0.1), reach=0.55, hand=0.66)
    # ladder up the back to the platform, stairs to the deck at the back right
    for sx in (-0.22, 0.22):
        tube(dark, (sx, y0 - 0.45, G), (sx, y0 - 0.45, zp + 1.05), 0.025, 4)
    z = G + 0.3
    while z < zp:
        tube(dark, (-0.22, y0 - 0.45, z), (0.22, y0 - 0.45, z), 0.015, 3)
        z += 0.3
    for k in range(4):
        block(gr, I4, G - 0.03, G + (k + 1) * 0.3, 0.55, 0.19, cx=3.0, cy=y0 - 1.33 + 0.38 * k)
    # the iron plot fence around it, a gate in front of the stairs
    x0, f0, x1, f1 = FOH_FENCE
    iron_fence(P, (x0, f1), (x1, f1), posts=(True, True))
    iron_fence(P, (x0, f0), (x0, f1), posts=(True, False))
    iron_fence(P, (x1, f0), (x1, f1), posts=(True, False))
    iron_fence(P, (x0, f0), (2.2, f0), posts=(False, True))
    iron_fence(P, (3.8, f0), (x1, f0), posts=(True, False))
    # lights: warm desk lamps, a purple screen glow on the engineers, a lamp on the platform
    P.lamp("InfFOH_Desk", "POINT", (0.0, dy - 0.1, zd + 1.25), C_WARM, 30, size=0.3)
    P.lamp("InfFOH_Screens", "AREA", (0.3, dy + 0.2, zd + 1.05), (0.6, 0.35, 1.0), 40, target=(0.3, dy - 1.0, zd + 1.5),
           size=3.0)
    P.lamp("InfFOH_Platform", "POINT", (0.0, py1 - 1.0, zp + 2.3), C_WARM, 25, size=0.2)
    P.exclude.append((x0 - KEEP_OUT, f0 - KEEP_OUT, x1 + KEEP_OUT, f1 + KEEP_OUT))
    P.people += [(3.0, f0 - 0.45, math.pi, "hips"), (-5.65, f1 + 0.45, -0.35, "down")]


# ------------------------------------------------------------------ crypt towers
def skull(P, M, s=1.0, eyes="red"):
    """A big skull facing local -Y, its base at local z 0: cranium, face, jaw, teeth, glowing eye sockets."""
    b = P.m("bone")
    ball(b, M, (0.0, 0.05 * s, 0.78 * s), 0.55 * s, 8, 6, (0.95, 1.1, 0.92))           # cranium
    block(b, M, 0.24 * s, 0.66 * s, 0.37 * s, 0.22 * s, tx=0.41 * s, ty=0.24 * s, cy=-0.38 * s)   # face
    block(b, M, 0.0, 0.25 * s, 0.31 * s, 0.22 * s, tx=0.35 * s, ty=0.24 * s, cy=-0.3 * s)  # jaw
    for i in range(6):                                                                   # teeth
        u = (i - 2.5) * 0.1 * s
        block(b, M, 0.2 * s, 0.31 * s, 0.04 * s, 0.03 * s, cx=u, cy=-0.6 * s, skip=())
    R3 = M.to_3x3()
    fwd = R3 @ Vector((0, -1, 0))
    for sx in (-1, 1):
        gl(P, disc(P.glow, M @ Vector((sx * 0.19 * s, -0.635 * s, 0.5 * s)), fwd, 0.12 * s, 8), eyes)
    gl(P, flat(P.glow, Plane(M @ Vector((0.0, -0.635 * s, 0.0)), R3 @ Vector((1, 0, 0)), R3 @ Vector((0, 0, 1))),
               [(-0.06 * s, 0.32 * s), (0.06 * s, 0.32 * s), (0.0, 0.43 * s)]), "black")      # nose
    return M @ Vector((0.0, -0.64 * s, 0.5 * s))


def tower(P, sx, sy, rng, k):
    st, gr, ir = P.m("stone"), P.m("dino_grey"), P.m("metal_dark")
    out = 1.0 if sx > 0 else -1.0
    M = M_at(sx, sy, G)
    z0, z1 = 2.5, TOWER_TOP - G                                      # local heights of the iron frame
    block(gr, M, -0.03, 0.4, 1.22, 1.22)                             # base course
    block(st, M, 0.4, 2.3, 1.1, 1.1)                                 # plinth
    block(gr, M, 2.3, 2.5, 1.18, 1.18, skip=())                      # cornice
    for sgn in (1, -1):                                              # glowing pointed niches, stage and crowd sides
        pl = Plane(M @ Vector((0.0, sgn * 1.112, 0.0)), (-sgn, 0, 0), (0, 0, 1))
        gl(P, flat(P.glow, pl, [(-0.3, 0.7), (0.3, 0.7), (0.3, 1.5), (0.0, 1.88), (-0.3, 1.5)]), "purple_dim")
        for su in (-1, 1):
            tube(gr, pl.p(su * 0.42, 0.62, 0.05), pl.p(su * 0.42, 1.5, 0.05), 0.07, 4)
            tube(gr, pl.p(su * 0.42, 1.48, 0.05), pl.p(0.0, 2.02, 0.05), 0.07, 4)

    def half(z):
        return 0.8 + (0.42 - 0.8) * (z - z0) / (z1 - z0)
    corners = ((-1, -1), (1, -1), (1, 1), (-1, 1))
    for cx, cy in corners:
        tube(ir, M @ Vector((cx * half(z0), cy * half(z0), z0)), M @ Vector((cx * half(z1), cy * half(z1), z1)), 0.06, 4)
        gl(P, tube(P.glow, M @ Vector((cx * (half(z0) + 0.08), cy * (half(z0) + 0.08), z0 + 0.2)),
                   M @ Vector((cx * (half(z1) + 0.08), cy * (half(z1) + 0.08), z1 - 0.2)), 0.026, 4), "purple")
    levels = [z0 + (z1 - z0) * i / 5 for i in range(6)]
    for i, z in enumerate(levels):
        h = half(z)
        for (ax, ay), (bx, by) in zip(corners, corners[1:] + corners[:1]):
            tube(ir, M @ Vector((ax * h, ay * h, z)), M @ Vector((bx * h, by * h, z)), 0.035, 3)
            if i < 5:
                za, hb = levels[i + 1], half(levels[i + 1])
                tube(ir, M @ Vector((ax * h, ay * h, z)), M @ Vector((bx * hb, by * hb, za)), 0.024, 3)
                tube(ir, M @ Vector((bx * h, by * h, z)), M @ Vector((ax * hb, ay * hb, za)), 0.024, 3)
    # top platform, a crown of iron spikes, the skull facing the stage
    block(ir, M, z1, z1 + 0.14, 0.85, 0.85, skip=())
    for cx, cy in corners:
        spike(ir, M @ Vector((cx * 0.76, cy * 0.76, z1 + 0.14)), M @ Vector((cx * 0.88, cy * 0.88, z1 + 1.15)), 0.065, 4)
    eye = skull(P, M @ T(0.0, -0.05, z1 + 0.14) @ Matrix.Rotation(math.pi, 4, "Z"), 1.3, "red")
    halo_quad(P.halos, eye + Vector((0, 0.2, 0)), 1.4, "red", (0, 1, 0))
    # sky beam from a fixture behind the skull
    fx = M @ Vector((0.0, -0.68, z1 + 0.14))
    d = Vector((out * 0.22, -0.18, 1.0)).normalized()
    block(ir, M_at(fx.x, fx.y, fx.z), 0.0, 0.16, 0.16, 0.14)
    tube(ir, fx + UP * 0.16, fx + UP * 0.16 + d * 0.32, 0.1, 6, caps=True)
    lens = fx + UP * 0.16 + d * 0.33
    gl(P, disc(P.glow, lens, d, 0.085, 6), "purple")
    beam_planes(P.beams, lens + d * 0.05, d, 42.0, 0.2, 3.0, "purple", planes=2)
    # line array on a cantilever toward the back of the crowd (-Y)
    zt = z1 - 0.9
    hh = half(zt)
    ay = -hh - 1.15
    for su in (-1, 1):
        tube(ir, M @ Vector((su * hh, -hh, zt)), M @ Vector((su * 0.45, ay - 0.1, zt)), 0.035, 4)
    tube(ir, M @ Vector((-0.45, ay, zt)), M @ Vector((0.45, ay, zt)), 0.035, 4)
    block(ir, M, zt - 0.42, zt - 0.05, 0.14, 0.14, cy=ay, skip=())                     # hoist
    tube(ir, M @ Vector((0.0, ay, zt - 0.42)), M @ Vector((0.0, ay, zt - 0.8)), 0.012, 3)
    bump = zt - 0.8
    block(ir, M, bump - 0.08, bump, 0.65, 0.36, cy=ay, skip=())
    W, Dd, H = 1.2, 0.58, 0.36
    p0 = M @ Vector((0.0, ay - Dd / 2, bump - 0.08))                # front-top edge; the J curls back underneath
    R3 = M.to_3x3()
    for a_deg in (0, 1, 2, 3.5, 5, 7, 9.5, 12):
        a = math.radians(a_deg)
        Ra = Matrix.Rotation(a, 3, "X")
        c = p0 + R3 @ Ra @ Vector((0.0, Dd / 2, -H / 2))
        Mb = Matrix.Translation(c) @ (R3 @ Ra).to_4x4()
        block(ir, Mb, -H / 2, H / 2, W / 2, Dd / 2, skip=())
        block(gr, Mb, -H / 2 + 0.035, H / 2 - 0.035, W / 2 - 0.04, 0.008, cy=-Dd / 2 - 0.006, skip=())   # grille
        p0 = p0 + R3 @ Ra @ Vector((0.0, 0.0, -H))
    # lights: a purple uplight from the stage side onto the tower and skull, a purple wash onto the crowd
    can = M @ Vector((0.0, 1.75, 0.05))
    tgt = M @ Vector((0.0, 0.0, z1 + 0.9))
    dd = (tgt - can).normalized()
    tube(ir, can - dd * 0.05, can + dd * 0.22, 0.13, 8)
    gl(P, disc(P.glow, can + dd * 0.22, dd, 0.11, 8), "purple")
    tag = f"InfTower{'R' if sx > 0 else 'L'}{0 if sy > -50 else 1}"
    P.lamp(tag + "_Up", "SPOT", can + dd * 0.28, C_PURPLE, P_TOWER_UP, target=tgt, size=0.1, spot_deg=24)
    P.lamp(tag + "_Wash", "SPOT", M @ Vector((0.0, 0.75, z1 - 0.3)), C_PURPLE, P_TOWER_WASH,
           target=M @ Vector((0.0, 4.0, 0.0)), size=0.3, spot_deg=80)
    # keep-out over the whole footprint (base course, uplight can, the line array overhead) plus KEEP_OUT: the crowd
    # lint counts anything 0.5 m over the field, overhead or not
    P.exclude.append((sx - 1.22 - KEEP_OUT, sy - 1.97 - KEEP_OUT, sx + 1.22 + KEEP_OUT, sy + 1.9 + KEEP_OUT))
    if sy > -50:                                                     # a fan at the front towers' base, inside the rect
        P.people.append((round(sx - out * 1.6, 2), round(sy + 1.2, 2), round(-out * 0.25, 3), "up"))


# ------------------------------------------------------------------ lantern masts
def mast(P, mx, my, target, rng, k):
    st, gr, ir = P.m("stone"), P.m("dino_grey"), P.m("metal_dark")
    M = M_at(mx, my, G)
    block(st, M, -0.03, 1.1, 0.5, 0.5, tx=0.42, ty=0.42)
    block(gr, M, 1.1, 1.22, 0.47, 0.47, skip=())
    tube(ir, (mx, my, G + 1.22), (mx, my, G + 8.7), 0.13, 6, r2=0.075)
    for z in (3.6, 6.2):
        tube(ir, (mx, my, G + z), (mx, my, G + z + 0.18), 0.17, 6, caps=True)
    spike(ir, (mx, my, G + 8.7), (mx, my, G + 9.7), 0.09, 6)
    f = Vector((target[0] - mx, target[1] - my, 0.0)).normalized()
    top = Vector((mx, my, G + 8.4))
    front, back = top + f * 1.5, top - f * 0.9
    tube(ir, back, front, 0.045, 4)
    tube(ir, top - UP * 0.9, top + f * 1.05, 0.03, 4)                # brace under the arm
    tube(ir, top - UP * 0.7, top - f * 0.6, 0.03, 4)
    cores = []
    for p in (front, top + f * 0.75, back):
        tube(ir, p, p - UP * 0.3, 0.008, 3)
        cores.append(lantern(P, p - UP * (0.3 + 0.47 * 2.0), s=2.0, key="amber"))
    halo(P.halos, cores[0], 2.2, "amber", planes=1)
    P.lamp(f"InfMast{'R' if mx > 0 else 'L'}{0 if my > -70 else 1}", "SPOT", cores[1] + f * 0.3 - UP * 0.3, C_AMBER,
           P_MAST, target=target, size=0.6, spot_deg=85)
    pts = [(mx + sx * 0.5, my + sy * 0.5) for sx in (-1, 1) for sy in (-1, 1)]        # stone base
    for p in (front, top + f * 0.75, back):                                             # the lanterns on the arm
        pts += [(p.x + sx * 0.28, p.y + sy * 0.28) for sx in (-1, 1) for sy in (-1, 1)]
    P.exclude.append((round(min(q[0] for q in pts) - KEEP_OUT, 2), round(min(q[1] for q in pts) - KEEP_OUT, 2),
                      round(max(q[0] for q in pts) + KEEP_OUT, 2), round(max(q[1] for q in pts) + KEEP_OUT, 2)))


# ------------------------------------------------------------------ module entry
def build(rng):
    P = Parts()
    P.run("foh", foh, rng)
    for k, (x, y) in enumerate(TOWERS):
        P.run("towers", tower, x, y, rng, k)
    for k, ((x, y), t) in enumerate(MASTS):
        P.run("masts", mast, x, y, t, rng, k)
    print(f"[INFRA] tris by feature {P.tally}; lights {len(P.lights)}; people {len(P.people)}; "
          f"beams {len(P.beams.faces)} quads; halos {len(P.halos.faces)} quads", flush=True)
    lit = []
    for key, bm in P.lit.items():
        if len(bm.faces):
            lit.append((bm, key))
        else:
            bm.free()
    return {"lit": lit, "glow": [P.glow], "beams": [P.beams], "halos": [P.halos], "lights": P.lights,
            "exclude": P.exclude, "people": P.people}
