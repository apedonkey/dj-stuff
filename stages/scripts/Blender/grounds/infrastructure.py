"""Crowd-area infrastructure of the Dino Stage festival grounds (Blender 4.5, headless).

FOH tower in the middle of the crowd (mixing desks under a roof, follow-spot deck with two spots on the DJ, LED
banners), four delay towers in two rings (line arrays under a bar of moving heads, LED edge strips, DINO panels),
four portable light masts lighting the back of the crowd, LED totems held up in the crowd, and bike-rack barricades
around the FOH and the tower bases.
Pre-drop meters, Z up, DJ at the origin facing -Y; everything stands on the field floor z = GROUND_Z.
"""
from kit import *

NAME = "infrastructure"
BAKE_SIZE = 2048
TOTEMS = True             # False (set before build()): no LED totems, holders or their keep-outs (crowd v2 brings its own)

G = GROUND_Z
EYE_Z = 2.65                                    # DJ eye height (pre-drop): the FOH roof sits here, seen edge-on
DJ_HEAD = Vector((0.0, 0.0, 2.6))               # the follow spots aim here
# delay towers: front ring, and a back ring between the FOH and the front ring as seen from the DJ (13 vs 22 degrees
# off center: at x=+-24 the back towers would hide behind the front ones), inside both stream cameras' frames
TOWERS = ((-17.0, -42.0), (17.0, -42.0), (-15.0, -65.0), (15.0, -65.0))
TOWER_H = 13.5
TOWER_STRIP = "screen_teal"                     # LED edge strips: a dim stage cyan
# light masts: the outer pair in the crowd, the inner pair on its back edge (moved from (+-12, -68), the back ring's spot)
MASTS = (((-30.0, -58.0), (-21.0, -50.0, G), "truck_yellow"), ((30.0, -58.0), (21.0, -50.0, G), "truck_yellow"),
         ((-24.0, -78.0), (-16.0, -69.0, G), "truck_yellow"), ((24.0, -78.0), (16.0, -69.0, G), "truck_yellow"))


# ------------------------------------------------------------------ helpers
class Parts:
    """Output collector: one lit bmesh per LIT key, one glow/beam/halo bmesh, lights, crowd keep-outs, extra people."""

    def __init__(self):
        self.lit, self.glow, self.beams, self.halos = {}, bmesh.new(), bmesh.new(), bmesh.new()
        self.lights, self.exclude, self.people = [], [], []

    def m(self, key):
        if key not in self.lit:
            self.lit[key] = bmesh.new()
        return self.lit[key]

    def count(self):
        return sum(tris(b) for b in self.lit.values()) + tris(self.glow)


def gl(P, faces, key):
    glow_faces(P.glow, faces, key)
    return faces


def tube(bm, a, b, r, segs=4):
    return cyl(bm, a, b, r, segs=segs, cap=False)


class Plane:
    """2D drawing plane: o + r*u + up*v (+ n*w); front normal n = r x up."""

    def __init__(self, o, r, up):
        self.o, self.r, self.up = Vector(o), Vector(r).normalized(), Vector(up).normalized()
        self.n = self.r.cross(self.up).normalized()

    def p(self, u, v, w=0.0):
        return self.o + self.r * u + self.up * v + self.n * w


def frame(yaw=0.0, pitch=0.0):
    """The rotation kit.box applies for (yaw, pitch); a box's local -Y face is its 'front'."""
    return Matrix.Rotation(yaw, 3, "Z") @ Matrix.Rotation(pitch, 3, "X")


def front_plane(c, size, yaw=0.0, pitch=0.0, out=0.006):
    """Drawing plane on the local -Y face of box(c, size, yaw, pitch), facing out of it."""
    R = frame(yaw, pitch)
    return Plane(Vector(c) + R @ Vector((0, -size[1] / 2 - out, 0)), R @ Vector((1, 0, 0)), R @ Vector((0, 0, 1)))


def flat(bm, pl, pts, gap=0.012, both=True):
    """Convex polygon of (u, v) points in plane pl facing pl.n; both: plus a back face `gap` behind it."""
    pts = list(pts)
    if sum(p[0] * q[1] - q[0] * p[1] for p, q in zip(pts, pts[1:] + pts[:1])) < 0:
        pts.reverse()
    faces = [bm.faces.new([bm.verts.new(pl.p(u, v, gap / 2)) for u, v in pts])]
    if both:
        faces.append(bm.faces.new([bm.verts.new(pl.p(u, v, -gap / 2)) for u, v in reversed(pts)]))
    return faces


def fan(bm, pl, c, ring, closed=True, **kw):
    """Star-shaped polygon as a triangle fan around c."""
    pairs = list(zip(ring, ring[1:] + ring[:1])) if closed else list(zip(ring, ring[1:]))
    out = []
    for a, b in pairs:
        out += flat(bm, pl, [c, a, b], **kw)
    return out


def band(bm, pl, outer, inner, closed=True, **kw):
    """Strip between two matching outlines (frame, ring, arc)."""
    out = []
    for i in range(len(outer) if closed else len(outer) - 1):
        j = (i + 1) % len(outer)
        out += flat(bm, pl, [outer[i], outer[j], inner[j], inner[i]], **kw)
    return out


def circle(r, n, c=(0.0, 0.0), a0=0.0, a1=None, ry=None):
    """n points on a circle around c, or on the arc a0..a1 (both ends included)."""
    ry = r if ry is None else ry
    angs = [a0 + 2 * math.pi * i / n for i in range(n)] if a1 is None else [a0 + (a1 - a0) * i / (n - 1) for i in range(n)]
    return [(c[0] + r * math.cos(a), c[1] + ry * math.sin(a)) for a in angs]


def led(bm, pl, text, pixel, key, cu=0.0, cv=0.0, gap=0.012, both=True):
    """Dot-matrix text centered at (cu, cv) of plane pl; both: readable from the back too."""
    tw, th = text_width(text, pixel), 6.8 * pixel
    f = led_text(bm, text, pl.p(cu - tw / 2, cv - th / 2, gap / 2), pl.r, pl.up, pixel=pixel, gap=0.2 * pixel, key=key)
    if both:
        f += led_text(bm, text, pl.p(cu + tw / 2, cv - th / 2, -gap / 2), -pl.r, pl.up, pixel=pixel, gap=0.2 * pixel,
                      key=key)
    return f


DINO_SPRITE = [".....#####", ".....#.###", ".....#####", ".....###..", "#...####..", "##.######.",
               ".#######..", "..#####...", "..#...#...", "..##..##.."]


def sprite(bm, pl, rows, pixel, key, cu=0.0, cv=0.0, mirror=False):
    """Pixel sprite (rows top -> bottom, '#' lit) centered at (cu, cv) of plane pl, one-sided."""
    h, w, s = len(rows), len(rows[0]), pixel * 0.8
    faces = []
    for r, row in enumerate(rows):
        for c, px in enumerate(row):
            if px == "#":
                u, v = cu + ((w - 1 - c) if mirror else c) * pixel - w * pixel / 2, cv + (h / 2 - 1 - r) * pixel
                faces += flat(bm, pl, [(u, v), (u + s, v), (u + s, v + s), (u, v + s)], gap=0, both=False)
    glow_faces(bm, faces, key)
    return faces


def halo_quad(bm, center, size, color, normal):
    """One glow sprite square facing `normal` (kit.halo's UV layout): a soft glow seen from the front, a sliver from
    above, unlike kit.halo's three crossed planes."""
    c, n = Vector(center), Vector(normal).normalized()
    up = Vector((0, 0, 1)) if abs(n.z) < 0.95 else Vector((0, 1, 0))
    b = (up - n * up.dot(n)).normalized() * size / 2
    a = b.cross(n)
    col = BEAM_COLS.index(color)
    u0, u1 = col / len(BEAM_COLS), (col + 1) / len(BEAM_COLS)
    return quad(bm, c - a - b, c + a - b, c + a + b, c - a + b, uvs=[(u0, 0.0), (u1, 0.0), (u1, 1.0), (u0, 1.0)])


def soft_beam(bm, apex, direction, length, w0, w1, color, planes=2, v0=0.0):
    """kit.beam_planes with the quads starting at v0 of the texture's fade: v0 > 0 skips the bright apex, giving a
    thinner-looking, lower-alpha beam that still fades out at its end."""
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


def strip(pts, widths):
    """Left/right outlines of a tapered strip along a 2D centerline (for band()): necks, tails."""
    left, right = [], []
    for i, (p, w) in enumerate(zip(pts, widths)):
        a, b = Vector(pts[max(i - 1, 0)]), Vector(pts[min(i + 1, len(pts) - 1)])
        t = (b - a).normalized()
        n = Vector((-t.y, t.x)) * w
        left.append(tuple(Vector(p) + n))
        right.append(tuple(Vector(p) - n))
    return left, right


def monitor(P, c, size, key, yaw=0.0, pitch=0.0, bezel=0.03, body="metal_dark"):
    """A screen: dark box whose -Y face glows `key` inside a bezel."""
    box(P.m(body), c, size, yaw=yaw, pitch=pitch)
    w, h = size[0] / 2 - bezel, size[2] / 2 - bezel
    return gl(P, flat(P.glow, front_plane(c, size, yaw, pitch), [(-w, -h), (w, -h), (w, h), (-w, h)], gap=0,
                      both=False), key)


def crew(P, x, y, z0, yaw=0.0, h=1.78, reach=0.4, hand=0.55):
    """Crew member in black at (x, y) on a floor at z0, facing yaw (0 = the stage), hands forward (desk, handle)."""
    R = Matrix.Rotation(yaw, 3, "Z")

    def at(lx, ly, lz):
        return Vector((x, y, z0)) + R @ Vector((lx, ly, lz))
    black, skin = P.m("canvas_black"), P.m("wood")
    for s in (-1, 1):
        cyl(black, at(s * 0.1, 0, 0), at(s * 0.11, 0, h * 0.5), 0.075, segs=5)
    box(black, at(0, 0, h * 0.655), (0.44, 0.25, h * 0.31), yaw=yaw)
    sphere(skin, at(0, 0.01, h * 0.905), 0.11, segs=6, rings=4, scale=(1.0, 1.05, 1.2))
    for s in (-1, 1):
        sh, el, hd = at(s * 0.21, 0, h * 0.78), at(s * 0.25, reach * 0.4, h * 0.62), at(s * 0.17, reach, h * hand)
        tube(black, sh, el, 0.05)
        tube(skin, el, hd, 0.04)


def barricade(bm, a, b, h=1.1):
    """Bike-rack crowd barrier between ground points a and b: frame, bars, two flat feet."""
    a, b = Vector((a[0], a[1], G)), Vector((b[0], b[1], G))
    t = (b - a).normalized()
    up = Vector((0, 0, 1))
    pa, pb = a + t * 0.04, b - t * 0.04
    out = []
    for p, q in ((pa + up * 0.1, pa + up * h), (pa + up * h, pb + up * h), (pb + up * h, pb + up * 0.1),
                 (pa + up * 0.2, pb + up * 0.2)):
        out += tube(bm, p, q, 0.022)
    k = max(2, int((b - a).length / 0.4))
    for i in range(1, k):
        p = pa.lerp(pb, i / k)
        out += tube(bm, p + up * 0.2, p + up * h, 0.012, segs=3)
    for p in (pa, pb):
        out += box(bm, p + up * 0.02, (0.06, 0.75, 0.04), yaw=math.atan2(t.y, t.x))
    return out


def barricade_run(bm, p0, p1, unit=2.3):
    p0, p1 = Vector(p0), Vector(p1)
    k = max(1, round((p1 - p0).length / unit))
    out = []
    for i in range(k):
        out += barricade(bm, p0.lerp(p1, i / k), p0.lerp(p1, (i + 1) / k))
    return out


def moving_head(P, base, aim, key, s=1.0):
    """Upright moving head standing on `base`, its head pointing along `aim`, lens glowing `key`.
    Returns (lens center, unit direction)."""
    m = P.m("metal_dark")
    base, d = Vector(base), Vector(aim).normalized()
    yaw = math.atan2(-d.x, d.y)
    side = Vector((math.cos(yaw), math.sin(yaw), 0.0))
    box(m, base + Vector((0, 0, 0.08 * s)), (0.36 * s, 0.3 * s, 0.16 * s), yaw=yaw)
    for sg in (-1, 1):
        box(m, base + side * (0.17 * s * sg) + Vector((0, 0, 0.32 * s)), (0.05 * s, 0.12 * s, 0.36 * s), yaw=yaw)
    hc = base + Vector((0, 0, 0.42 * s))
    cyl(m, hc - d * 0.17 * s, hc + d * 0.19 * s, 0.13 * s, segs=8)
    lens = hc + d * 0.2 * s
    gl(P, cyl(P.glow, lens - d * 0.012, lens + d * 0.012, 0.105 * s, segs=8), key)
    return lens, d


# ------------------------------------------------------------------ FOH (front of house)
FOH_ENCLOSURE = (-4.5, -34.5, 4.5, -27.5)
TOWER_RING = 2.35                                       # half-width of the barricade square around a tower base
KEEP_OUT = 0.75   # crowd keep-out beyond a barricade line or trailer: feet clear, elbows (hands-on-hips) miss the rail


def build_foh(P, rng):
    grey, dark, black = P.m("metal_grey"), P.m("metal_dark"), P.m("canvas_black")
    x0, x1, y0, y1 = -3.5, 3.5, -33.3, -28.7            # lower deck; y1 = front edge (stage side)
    yc, W, D = (y0 + y1) / 2, x1 - x0, y1 - y0
    zd, zr, zu = G + 1.2, EYE_Z, G + 6.5                # deck top, roof top, follow-spot deck top
    # black scrim skirts up to the deck; the front one rises to desk height and hides the desks from the stage
    box(black, (0, y1, (G + zd + 1.0) / 2), (W, 0.05, zd + 1.0 - G))
    box(black, (0, y0, (G + zd) / 2), (W, 0.05, zd - G))
    for x in (x0, x1):
        box(black, (x, yc, (G + zd) / 2), (0.05, D, zd - G))
    box(P.m("wood_dark"), (0, yc, zd - 0.05), (W, D, 0.1))
    # scaffold: slim standards only at the corners and side middles, so the band above the desks stays open
    for x, y in ((x0, y1), (x1, y1), (x0, -31.0), (x1, -31.0), (x0, y0), (x1, y0)):
        tube(grey, (x, y, zd), (x, y, zr - 0.05), 0.04, segs=6)
    for x in (x0, x1):                                  # side guard rails
        for z in (zd + 0.5, zd + 1.0):
            tube(grey, (x, y0, z), (x, y1, z), 0.025)
    for z in (zd + 0.5, zd + 1.0):                      # back guard rail, gap at the stair head
        tube(grey, (x0, y0, z), (0.9, y0, z), 0.025)
        tube(grey, (1.7, y0, z), (x1, y0, z), 0.025)
    # roof: black tarp at the DJ's eye height (seen edge-on), black fascias carrying the LED banners
    ro = 0.3
    box(black, (0, yc, zr - 0.04), (W + 2 * ro, D + 2 * ro, 0.08))
    fy1, fy0 = y1 + ro, y0 - ro
    for x in (x0 - ro, x1 + ro):
        box(black, (x, yc, zr - 0.25), (0.08, D + 2 * ro, 0.5))
    # LED banners on the fascias: "DINO STAGE" between two pixel dinos walking toward it, framed by thin LED strips.
    # The back fascia is shallower so the stream camera behind the crowd sees the desk screens under it.
    for fy, sgn, fh, dino_px, key, edge in ((fy1, -1, 1.0, 0.068, "amber", "warm_dim"),
                                           (fy0, 1, 0.74, 0.058, "cyan", "blue_dim")):
        box(black, (0, fy, zr - fh / 2), (W + 2 * ro, 0.08, fh))
        pl = Plane((0, fy - sgn * 0.042, zr - fh / 2), (sgn, 0, 0), (0, 0, 1))
        led(P.glow, pl, "DINO STAGE", 0.085, key, gap=0, both=False)
        for cu, mir in ((-3.13, False), (3.13, True)):
            sprite(P.glow, pl, DINO_SPRITE, dino_px, key, cu=cu, mirror=mir)
        hw, v = W / 2 + ro - 0.06, fh / 2 - 0.028
        for vv in (v, -v):
            gl(P, flat(P.glow, pl, [(-hw, vv - 0.016), (hw, vv - 0.016), (hw, vv + 0.016), (-hw, vv + 0.016)], gap=0,
                       both=False), edge)
    # front light: four warm profiles on the roof edge, aimed at the DJ (they light the artist for the stream)
    for fx in (-2.9, -1.65, 1.65, 2.9):
        base = Vector((fx, y1 + 0.1, zr))
        box(dark, base + Vector((0, 0, 0.04)), (0.5, 0.3, 0.08))
        lens, d = moving_head(P, base + Vector((0, 0, 0.08)), DJ_HEAD - (base + Vector((0, 0, 0.42))), "bulb_warm",
                              s=0.85)
        halo_quad(P.halos, lens + d * 0.06, 0.95, "amber", d)
    # desks: sound console (left) and lighting console with two external monitors (right), engineers behind
    for cx, w in ((-1.2, 2.5), (1.35, 1.9)):
        box(dark, (cx, -29.45, zd + 0.37), (w, 0.9, 0.74))
        box(dark, (cx, -29.45, zd + 0.8), (w - 0.05, 0.86, 0.1), pitch=0.15)
        for sx in (-0.3, 0.3):                          # gooseneck desk lamps
            lx = cx + sx * w
            tube(dark, (lx, -29.05, zd + 0.9), (lx, -29.3, zd + 1.25), 0.012, segs=3)
            gl(P, sphere(P.glow, (lx, -29.33, zd + 1.24), 0.04, segs=6, rings=3), "bulb_warm")
    monitor(P, (-1.2, -29.08, zd + 1.0), (2.2, 0.1, 0.32), "screen_teal", pitch=0.35)
    for sx, yaw in ((0.95, 0.12), (1.75, -0.12)):
        tube(dark, (sx, -29.05, zd + 0.85), (sx, -29.05, zd + 1.1), 0.02)
        monitor(P, (sx, -29.05, zd + 1.3), (0.62, 0.05, 0.4), "sky", yaw=yaw, pitch=0.12)
    monitor(P, (1.35, -29.12, zd + 0.93), (1.6, 0.08, 0.18), "screen_blue", pitch=0.5)
    for k, (ex, ey) in enumerate(((-1.75, -30.35), (-0.6, -30.4), (1.4, -30.3))):
        crew(P, ex, ey, zd, yaw=rng.uniform(-0.15, 0.15), h=rng.uniform(1.7, 1.86), reach=0.55, hand=0.56)
    # flight cases / racks at the back corners with status LEDs
    for cx, cy, sz in ((x0 + 0.45, -32.6, (0.62, 0.62, 1.05)), (x1 - 0.45, -32.1, (0.62, 0.8, 0.8))):
        c = (cx, cy, zd + sz[2] / 2)
        box(dark, c, sz)
        pl = front_plane(c, sz)
        for k in range(3):
            gl(P, flat(P.glow, pl, [(-0.2, 0.3 - k * 0.12), (-0.12, 0.3 - k * 0.12), (-0.12, 0.34 - k * 0.12),
                                    (-0.2, 0.34 - k * 0.12)], gap=0, both=False), ("green_dim", "red_dim", "blue_dim")[k])
    # follow-spot deck on four legs from the lower deck, braced on the sides and the back, open toward the stage
    ux, uy0, uy1 = 2.0, -33.25, -31.15
    for x in (-ux, ux):
        for y in (uy0, uy1):
            tube(dark, (x, y, zd), (x, y, zu), 0.045, segs=6)
        tube(dark, (x, uy1, zr), (x, uy0, zu - 0.1), 0.03)
        tube(dark, (x, uy0, zr), (x, uy1, zu - 0.1), 0.03)
    tube(dark, (-ux, uy0, zr), (ux, uy0, zu - 0.1), 0.03)
    tube(dark, (ux, uy0, zr), (-ux, uy0, zu - 0.1), 0.03)
    tube(dark, (-ux, uy1, (zr + zu) / 2), (ux, uy1, (zr + zu) / 2), 0.03)
    dx0, dx1, dy0, dy1 = -2.2, 2.2, -33.7, -31.0
    box(grey, (0, (dy0 + dy1) / 2, zu - 0.05), (dx1 - dx0, dy1 - dy0, 0.1))
    corners = [(dx0, dy0), (dx1, dy0), (dx1, dy1), (dx0, dy1)]
    for (ax, ay), (bx, by) in zip(corners, corners[1:] + corners[:1]):
        for z in (zu + 0.55, zu + 1.05):
            tube(dark, (ax, ay, z), (bx, by, z), 0.025)
        box(black, ((ax + bx) / 2, (ay + by) / 2, zu + 0.08), (abs(bx - ax) + 0.03, abs(by - ay) + 0.03, 0.16))
        tube(dark, (ax, ay, zu), (ax, ay, zu + 1.05), 0.03)
    # two follow spots on tripods, aimed at the DJ's head; operators behind them
    for sx in (-0.95, 0.95):
        base = Vector((sx, -31.6, zu))
        body = base + Vector((0, 0, 1.38))
        d = (DJ_HEAD - body).normalized()
        for k in range(3):
            a = 2 * math.pi * k / 3 + 0.5
            tube(dark, base + Vector((0.42 * math.cos(a), 0.42 * math.sin(a), 0)), base + Vector((0, 0, 1.1)), 0.02)
        tube(dark, base + Vector((0, 0, 1.1)), body, 0.035)
        cyl(dark, body - d * 0.75, body + d * 0.55, 0.15, segs=10, r2=0.18)
        lens = body + d * 0.55
        gl(P, cyl(P.glow, lens - d * 0.02, lens + d * 0.015, 0.15, segs=10), "white")
        halo_quad(P.halos, lens + d * 0.1, 1.5, "white", d)
        soft_beam(P.beams, lens + d * 0.04, d, (DJ_HEAD - lens).length - 4.0, 0.2, 0.8, "white", v0=0.5)
        crew(P, sx, -32.6, zu, yaw=rng.uniform(-0.1, 0.1), reach=0.5, hand=0.62)
    # ladder up the back (between the words of the back banner) and stairs to the lower deck
    lx, ly = -0.3, -33.8
    for s in (-0.2, 0.2):
        tube(dark, (lx + s, ly, G), (lx + s, ly, zu + 1.05), 0.025)
    z = G + 0.3
    while z < zu:
        tube(dark, (lx - 0.2, ly, z), (lx + 0.2, ly, z), 0.015, segs=3)
        z += 0.3
    run = math.hypot(2.0, zd - G)
    for y in (-33.42, -34.18):
        box(dark, (2.3, y, (G + zd) / 2), (run, 0.05, 0.22), roll=math.atan2(zd - G, 2.0))
    for k in range(5):
        box(dark, (3.3 - (k + 0.5) * 0.4, -33.8, G + (k + 1) * 0.24 - 0.02), (0.38, 0.78, 0.04))
    tube(grey, (3.3, -34.18, G + 0.95), (1.3, -34.18, zd + 0.95), 0.025)
    tube(grey, (3.3, -34.18, G), (3.3, -34.18, G + 0.95), 0.025)
    # lights: warm desk lamps, cool screen spill on the engineers' faces, a soft work light under the roof,
    # and a dim lamp on the follow-spot deck
    for cx in (-1.2, 1.35):
        P.lights.append(light(f"FOH_Desk{cx:+.0f}", "POINT", (cx, -29.4, zd + 1.25), (1.0, 0.72, 0.45), 22, size=0.05))
    P.lights.append(light("FOH_Screens", "AREA", (0.0, -29.2, zd + 1.05), (0.45, 0.62, 1.0), 45,
                          target=(0.0, -30.6, zd + 1.55), size=3.5))
    P.lights.append(light("FOH_Work", "AREA", (0.0, -30.6, zr - 0.2), (1.0, 0.8, 0.55), 90, target=(0.0, -30.6, zd),
                          size=3.0))
    P.lights.append(light("FOH_Spots", "POINT", (0.0, -32.6, zu + 2.2), (1.0, 0.85, 0.65), 25, size=0.2))
    ex0, ey0, ex1, ey1 = FOH_ENCLOSURE
    P.exclude.append((ex0 - KEEP_OUT, ey0 - KEEP_OUT, ex1 + KEEP_OUT, ey1 + KEEP_OUT))
    P.people += [(3.75, -33.9, math.pi, "hips"), (-3.95, -28.3, -0.4, "down")]


# ------------------------------------------------------------------ delay towers
def build_tower(P, sx, sy, rng):
    grey, dark, black = P.m("metal_grey"), P.m("metal_dark"), P.m("canvas_black")
    out = 1.0 if sx > 0 else -1.0                       # away from the center line
    top, ts, hw = G + TOWER_H, 0.6, 2.6                 # truss top, tower truss size, header bar half-length
    # base plate, four outriggers to concrete ballast
    box(dark, (sx, sy, G + 0.06), (1.3, 1.3, 0.12))
    for k in range(4):
        a = math.pi / 4 + k * math.pi / 2
        c = Vector((math.cos(a), math.sin(a), 0))
        box(dark, Vector((sx, sy, G + 0.1)) + c * 1.05, (1.9, 0.14, 0.16), yaw=a)
        box(P.m("stone"), Vector((sx, sy, G + 0.35)) + c * 1.78, (0.8, 0.8, 0.7), yaw=a)
    truss(grey, (sx, sy, G + 0.12), (sx, sy, top), size=ts, step=0.9)
    box(dark, (sx, sy, top + 0.04), (ts + 0.14, ts + 0.14, 0.08))
    hz0 = top + 0.26                                    # header bar axis (0.35 m truss)
    truss(grey, (sx - hw, sy, hz0), (sx + hw, sy, hz0), size=0.35, step=0.65)
    # LED strips on the four tower edges and under the header bar: the tower reads as a glowing T at night
    e = ts / 2 + 0.04
    for cx, cy in ((-e, -e), (e, -e), (e, e), (-e, e)):
        gl(P, box(P.glow, (sx + cx, sy + cy, (G + 0.6 + top) / 2), (0.05, 0.05, top - G - 0.6)), TOWER_STRIP)
    for cy in (-0.215, 0.215):
        gl(P, box(P.glow, (sx, sy + cy, hz0 - 0.215), (2 * hw, 0.05, 0.05)), TOWER_STRIP)
    # line array on a cantilever toward the back of the crowd (-Y): hoist, bumper, 11 boxes in a J
    ay, zt = sy - 1.35, top - 0.6
    for sg in (-1, 1):
        tube(grey, (sx + sg * ts / 2, sy - ts / 2, zt), (sx + sg * ts / 2, ay - 0.1, zt), 0.035)
    tube(grey, (sx - 0.45, ay, zt), (sx + 0.45, ay, zt), 0.035)
    box(dark, (sx, ay, zt - 0.24), (0.3, 0.3, 0.42))                   # chain hoist hung under the crossbar
    tube(dark, (sx, ay, zt - 0.45), (sx, ay, zt - 0.9), 0.012, segs=3)
    bump = zt - 0.9
    box(dark, (sx, ay, bump - 0.04), (1.35, 0.75, 0.08))
    W, Dd, H = 1.25, 0.6, 0.36
    p0 = Vector((sx, ay - Dd / 2, bump - 0.08))
    for a_deg in (0, 0.5, 1, 1.5, 2, 3, 4, 5, 6.5, 8, 10):
        a = math.radians(a_deg)
        R = Matrix.Rotation(a, 3, "X")
        c = p0 + R @ Vector((0, Dd / 2, -H / 2))
        box(dark, c, (W, Dd, H), pitch=a)
        box(grey, c + R @ Vector((0, -Dd / 2 - 0.006, 0)), (W - 0.08, 0.016, H - 0.07), pitch=a)      # grille
        p0 = p0 + R @ Vector((0, 0, -H))
    # four moving heads on the header bar: the inner two toward the stage sky, the outer two up (one beam) and back
    hz = hz0 + 0.175
    aims = [(out * 7, -5, 40), (-out * 6, 30, 30), (-out * 14, 34, 26), (out * 4, -26, 36)]
    keys = ["uv", "magenta", "magenta", "uv"]
    for i, hx in enumerate((1.95, 0.65, -0.65, -1.95)):
        lens, d = moving_head(P, (sx + out * hx, sy, hz), aims[i], keys[i], s=1.15)
        halo_quad(P.halos, lens + d * 0.08, 1.1, "magenta" if keys[i] == "magenta" else "purple", d)
        if i == 0:                                      # one beam per tower: the sky is the atmosphere module's
            beam_planes(P.beams, lens + d * 0.05, d, 34.0, 0.2, 2.6, "purple", planes=2)
    # DINO LED panels at mid-height: amber toward the stage, cyan toward the back (the FOH banners' colors)
    pz = G + 4.6
    for sgn, key, edge in ((1, "amber", "warm_dim"), (-1, "cyan", "blue_dim")):
        py = sy + sgn * (ts / 2 + 0.12)
        box(black, (sx, py, pz), (2.8, 0.08, 0.9))
        pl = Plane((sx, py + sgn * 0.042, pz), (-sgn, 0, 0), (0, 0, 1))
        sprite(P.glow, pl, DINO_SPRITE, 0.066, key, cu=-0.95)
        led(P.glow, pl, "DINO", 0.075, key, cu=0.42, gap=0, both=False)
        for v in (0.405, -0.405):
            gl(P, flat(P.glow, pl, [(-1.34, v - 0.014), (1.34, v - 0.014), (1.34, v + 0.014), (-1.34, v + 0.014)],
                       gap=0, both=False), edge)
    # uplight can at the base lighting the truss; a magenta wash from the stage side of the top onto the crowd
    can = Vector((sx, sy + 0.95, G + 0.05))
    d = (Vector((sx, sy, top)) - can).normalized()
    cyl(dark, can, can + d * 0.3, 0.13, segs=8)
    gl(P, cyl(P.glow, can + d * 0.3, can + d * 0.315, 0.11, segs=8), "uv")
    tag = f"Tower{sx:+.0f}{sy:+.0f}"
    P.lights.append(light(tag + "_Up", "SPOT", can + d * 0.35, GLOW["purple"], 1200, target=(sx, sy, top),
                          size=0.1, spot_deg=26))
    P.lights.append(light(tag + "_Wash", "SPOT", (sx, sy + 0.5, top - 0.4), GLOW["magenta"], 1400,
                          target=(sx, sy + 3.0, G), size=0.3, spot_deg=80))
    r = TOWER_RING + KEEP_OUT
    P.exclude.append((sx - r, sy - r, sx + r, sy + r))


# ------------------------------------------------------------------ light masts
def build_mast(P, mx, my, target, shell_key, rng):
    yaw = rng.uniform(-math.pi, math.pi)                # trailer heading; the lamp head turns to its target
    R = Matrix.Rotation(yaw, 3, "Z")
    O = Vector((mx, my, G))

    def T(x, y, z):
        return O + R @ Vector((x, y, z))
    shell, dark, grey = P.m(shell_key), P.m("metal_dark"), P.m("metal_grey")
    box(shell, T(0.1, 0, 0.98), (2.3, 1.25, 1.06), yaw=yaw)              # genset canopy
    box(dark, T(0.1, 0, 0.4), (2.5, 1.0, 0.12), yaw=yaw)                 # chassis
    box(dark, T(0.6, 0.63, 1.0), (0.5, 0.02, 0.35), yaw=yaw)             # control panel door
    tube(dark, T(0.3, -0.75, 0.32), T(0.3, 0.75, 0.32), 0.035)          # axle
    for s in (-1, 1):
        cyl(P.m("rubber"), T(0.3, s * 0.68, 0.32), T(0.3, s * 0.9, 0.32), 0.32, segs=10)
        box(shell, T(0.3, s * 0.79, 0.7), (0.8, 0.3, 0.05), yaw=yaw)
        for e in (-1, 1):                                                 # stabiliser jacks on swing-out arms
            tube(dark, T(e * 1.05, s * 0.45, 0.42), T(e * 1.05, s * 0.75, 0.42), 0.03)
            tube(dark, T(e * 1.05, s * 0.72, 0.45), T(e * 1.05, s * 0.72, 0.03), 0.035)
            box(dark, T(e * 1.05, s * 0.72, 0.015), (0.2, 0.2, 0.03), yaw=yaw)
    tube(dark, T(-1.05, 0, 0.42), T(-2.1, 0, 0.36), 0.04, segs=5)        # drawbar
    tube(dark, T(-1.85, 0, 0.38), T(-1.85, 0, 0.12), 0.03)               # jockey wheel
    cyl(P.m("rubber"), T(-1.85, -0.04, 0.09), T(-1.85, 0.04, 0.09), 0.09, segs=6)
    tube(dark, T(0.9, -0.4, 1.5), T(0.9, -0.4, 1.75), 0.04)              # exhaust stack
    # telescoping mast
    mb = T(-0.75, 0, 0)
    for r, z0, z1 in ((0.085, 1.5, 3.9), (0.07, 3.8, 5.95), (0.056, 5.85, 7.8), (0.045, 7.7, 8.7)):
        cyl(grey, mb + Vector((0, 0, z0)), mb + Vector((0, 0, z1)), r, segs=8, cap=False)
        cyl(dark, mb + Vector((0, 0, z1 - 0.1)), mb + Vector((0, 0, z1)), r + 0.018, segs=8)
    # 2 x 2 lamp head facing the target
    top = mb + Vector((0, 0, 8.7))
    f = Vector(target) - top
    dist = f.length
    f.z = 0.0
    f.normalize()
    hyaw = math.atan2(f.x, -f.y)
    tilt = 0.75 * math.asin(min(1.0, (top.z - target[2]) / dist))
    side = Vector((-f.y, f.x, 0.0))
    hc = top + Vector((0, 0, 0.55))
    tube(dark, top, top + Vector((0, 0, 1.0)), 0.04)
    Rl = frame(hyaw, tilt)
    for dz in (-0.24, 0.24):
        tube(dark, hc + side * -0.72 + Vector((0, 0, dz)), hc + side * 0.72 + Vector((0, 0, dz)), 0.03)
        for sg in (-1, 1):
            c = hc + side * (0.4 * sg) + Vector((0, 0, dz)) + f * 0.12
            size = (0.52, 0.2, 0.42)
            box(dark, c, size, yaw=hyaw, pitch=tilt)
            gl(P, flat(P.glow, front_plane(c, size, hyaw, tilt), [(-0.22, -0.17), (0.22, -0.17), (0.22, 0.17),
                                                                   (-0.22, 0.17)], gap=0, both=False), "bulb_white")
    halo_quad(P.halos, hc + f * 0.45, 2.6, "amber", f)
    P.lights.append(light(f"Mast{mx:+.0f}{my:+.0f}", "SPOT", hc + f * 0.4, (1.0, 0.84, 0.62), 2000,
                          target=target, size=0.6, spot_deg=80))
    foot = [T(x, y, 0) for x in (-2.15, 1.4) for y in (-0.95, 0.95)]  # trailer + drawbar, turned with the trailer
    P.exclude.append((min(p.x for p in foot) - KEEP_OUT, min(p.y for p in foot) - KEEP_OUT,
                      max(p.x for p in foot) + KEEP_OUT, max(p.y for p in foot) + KEEP_OUT))


# ------------------------------------------------------------------ LED totems
def totem_ops(kind, key):
    """A totem's glowing shape in unit space (about -0.5..0.5, facing the viewer): [(op, data, key, layer)].
    layer 1 sits in front of layer 0 on both sides."""
    if kind == "triangle":
        outer = [(0.0, 0.62), (-0.54, -0.31), (0.54, -0.31)]
        return [("band", (outer, [(u * 0.66, v * 0.66) for u, v in outer], True), key, 0),
                ("flat", [(u * 0.3, v * 0.3) for u, v in outer], "white", 0)]
    if kind == "ring":
        return [("band", (circle(0.5, 20), circle(0.37, 20), True), key, 0),
                ("fan", ((0, 0), circle(0.16, 10), True), "white", 0)]
    if kind == "star":
        pts = [((0.56 if i % 2 == 0 else 0.23) * math.cos(math.pi / 2 + i * math.pi / 5),
                (0.56 if i % 2 == 0 else 0.23) * math.sin(math.pi / 2 + i * math.pi / 5)) for i in range(10)]
        return [("fan", ((0, 0), pts, True), key, 0)]
    if kind == "trex":                                  # T-rex head in profile, jaws wide open, facing +u
        skull = [(-0.45, 0.02), (0.52, 0.0), (0.58, 0.1), (0.42, 0.2), (0.0, 0.3), (-0.3, 0.32), (-0.48, 0.2)]
        jaw = [(-0.4, -0.06), (0.35, -0.3), (0.4, -0.36), (0.3, -0.42), (-0.1, -0.32), (-0.42, -0.18)]
        cheek = [(-0.47, 0.15), (-0.28, 0.02), (-0.30, -0.10), (-0.42, -0.18), (-0.48, -0.05)]   # closes the hinge
        ops = [("flat", skull, key, 0), ("flat", jaw, key, 0), ("flat", cheek, key, 0),
               ("fan", ((0.08, 0.19), circle(0.05, 8, (0.08, 0.19)), True), "red", 1)]
        for u in (-0.1, 0.05, 0.2, 0.35, 0.48):        # upper teeth hang into the open mouth
            v = 0.02 - 0.02 * (u + 0.45) / 0.97
            ops.append(("flat", [(u - 0.035, v), (u, v - 0.1), (u + 0.035, v)], "white", 0))
        for u in (-0.05, 0.1, 0.25):                    # lower teeth
            v = -0.06 - 0.24 * (u + 0.4) / 0.75
            ops.append(("flat", [(u - 0.03, v), (u + 0.03, v), (u, v + 0.09)], "white", 0))
        return ops
    if kind == "sauropod":                              # long-neck dino, facing +u
        neck = strip([(0.17, 0.04), (0.27, 0.16), (0.34, 0.28), (0.39, 0.40), (0.43, 0.52)],
                     [0.11, 0.085, 0.07, 0.06, 0.05])
        tail = strip([(-0.3, 0.04), (-0.45, 0.0), (-0.58, -0.06), (-0.7, -0.14), (-0.8, -0.2)],
                     [0.09, 0.07, 0.05, 0.03, 0.008])
        ops = [("fan", ((-0.05, 0.0), circle(0.33, 14, (-0.05, 0.0), ry=0.19), True), key, 0),
               ("band", (neck[0], neck[1], False), key, 0), ("band", (tail[0], tail[1], False), key, 0),
               ("fan", ((0.5, 0.56), circle(0.1, 8, (0.5, 0.56), ry=0.06), True), key, 0)]
        for u in (-0.25, -0.12, 0.08, 0.2):
            ops.append(("flat", [(u - 0.045, -0.05), (u + 0.045, -0.05), (u + 0.045, -0.38), (u - 0.045, -0.38)], key, 0))
        return ops
    if kind == "smiley":
        return [("fan", ((0, 0), circle(0.5, 18), True), key, 0),
                ("fan", ((-0.17, 0.14), circle(0.07, 8, (-0.17, 0.14)), True), "black", 1),
                ("fan", ((0.17, 0.14), circle(0.07, 8, (0.17, 0.14)), True), "black", 1),
                ("band", (circle(0.33, 9, a0=math.radians(200), a1=math.radians(340)),
                          circle(0.23, 9, a0=math.radians(200), a1=math.radians(340)), False), "black", 1)]
    if kind == "heart":
        pts = []
        for i in range(20):
            t = 2 * math.pi * i / 20
            pts.append((16 * math.sin(t) ** 3 / 34, (13 * math.cos(t) - 5 * math.cos(2 * t) - 2 * math.cos(3 * t)
                                                     - math.cos(4 * t)) / 34 + 0.05))
        return [("fan", ((0, 0.0), pts, True), key, 0)]
    if kind == "diamond":
        outer = [(0.0, 0.62), (-0.42, 0.0), (0.0, -0.62), (0.42, 0.0)]
        return [("flat", outer, key, 0), ("flat", [(u * 0.38, v * 0.38) for u, v in outer], "white", 1)]
    if kind == "bolt":
        return [("flat", [(-0.12, 0.6), (0.28, 0.6), (0.06, 0.02), (-0.30, 0.02)], key, 0),
                ("flat", [(-0.12, 0.08), (0.34, 0.08), (-0.22, -0.62)], key, 0)]
    if kind == "bone":                                  # cartoon dino bone, tilted
        R = Matrix.Rotation(math.radians(28), 2)

        def rot(pts):
            return [tuple(R @ Vector(p)) for p in pts]
        ops = [("flat", rot([(-0.42, -0.075), (0.42, -0.075), (0.42, 0.075), (-0.42, 0.075)]), key, 0)]
        for cu in (-0.44, 0.44):
            for cv in (-0.09, 0.09):
                c = tuple(R @ Vector((cu, cv)))
                ops.append(("fan", (c, rot(circle(0.115, 10, (cu, cv))), True), key, 0))
        return ops
    if kind == "mushroom":
        return [("fan", ((0, 0.0), circle(0.5, 13, a0=0.0, a1=math.pi, ry=0.42), False), key, 0),
                ("flat", [(-0.12, -0.45), (0.12, -0.45), (0.15, 0.0), (-0.15, 0.0)], "bulb_white", 0),
                ("fan", ((-0.24, 0.14), circle(0.07, 8, (-0.24, 0.14)), True), "white", 1),
                ("fan", ((0.04, 0.27), circle(0.08, 8, (0.04, 0.27)), True), "white", 1),
                ("fan", ((0.28, 0.12), circle(0.06, 8, (0.28, 0.12)), True), "white", 1)]
    if kind == "flower":
        ops = [("fan", (c, circle(0.17, 8, c), True), key, 0)
               for c in circle(0.3, 6, a0=math.pi / 2)]
        return ops + [("fan", ((0, 0), circle(0.16, 10), True), "yellow", 1)]
    # LED word on a black board
    pix = 0.075
    tw, th = text_width(kind, pix), 6.8 * pix
    bw, bh = tw / 2 + 0.09, th / 2 + 0.09
    return [("flat", [(-bw, -bh), (bw, -bh), (bw, bh), (-bw, bh)], "black", 0), ("text", (kind, pix), key, 1)]


def totem_extent(ops):
    """(lowest v, highest v) of a totem shape in unit space."""
    vs = []
    for op, data, key, layer in ops:
        if op == "flat":
            vs += [v for u, v in data]
        elif op == "fan":
            vs += [v for u, v in data[1]]
        elif op == "band":
            vs += [v for u, v in data[0] + data[1]]
        elif op == "text":
            vs += [-3.4 * data[1], 3.4 * data[1]]
    return min(vs), max(vs)


def draw_totem(P, pl, ops, s):
    """Draw unit-space ops into the glow mesh: scaled by s, shifted so the shape's bottom sits on pl's origin.
    Returns the shape's height in meters."""
    lo, hi = totem_extent(ops)
    dv = -lo

    def T(pts):
        return [(u * s, (v + dv) * s) for u, v in pts]
    for op, data, key, layer in ops:
        gap = 0.012 + 0.03 * layer
        if op == "flat":
            gl(P, flat(P.glow, pl, T(data), gap=gap), key)
        elif op == "fan":
            c, ring, closed = data
            gl(P, fan(P.glow, pl, T([c])[0], T(ring), closed=closed, gap=gap), key)
        elif op == "band":
            outer, inner, closed = data
            gl(P, band(P.glow, pl, T(outer), T(inner), closed=closed, gap=gap), key)
        elif op == "text":
            text, pix = data
            led(P.glow, pl, text, pix * s, key, cv=dv * s, gap=gap)
    return (hi - lo) * s


TOTEM_KINDS = [("triangle", "cyan"), ("ring", "magenta"), ("star", "yellow"), ("trex", "lime"), ("smiley", "yellow"),
               ("DROP", "red"), ("BASS", "cyan"), ("heart", "pink"), ("diamond", "sky"), ("bolt", "amber"),
               ("bone", "bulb_white"), ("ROAR", "green"), ("mushroom", "red"), ("flower", "magenta"),
               ("sauropod", "purple"), ("triangle", "lime")]
# spread over the middle and back of the crowd (it reaches y ~ -63); none in the DJ's line to the FOH or behind it
TOTEM_SPOTS = [(-14, -16), (11, -17), (-6, -21), (19, -22), (-21, -26), (9, -27), (-12, -31), (15, -33), (-26, -35),
               (26, -37), (-8, -40), (8, -41), (-29, -46), (-12, -49), (27, -50), (13, -54)]


def build_totems(P, rng):
    kinds = TOTEM_KINDS[:]
    rng.shuffle(kinds)
    pole = P.m("metal_grey")
    for (ax, ay), (kind, key) in zip(TOTEM_SPOTS, kinds):
        px, py = ax + rng.uniform(-1.2, 1.2), ay + rng.uniform(-1.0, 1.0)
        yaw = rng.uniform(-0.35, 0.35)                  # the holder faces the stage
        R = Matrix.Rotation(yaw, 3, "Z")
        hand = Vector((px, py, 0)) + R @ Vector((0.41, 0.08, 0))
        top = G + rng.uniform(3.5, 4.3)
        fy = yaw + rng.uniform(-0.3, 0.3)
        pl = Plane((hand.x, hand.y, top), (-math.cos(fy), -math.sin(fy), 0), (0, 0, 1))
        h = draw_totem(P, pl, totem_ops(kind, key), rng.uniform(0.85, 1.1))
        back = -pl.n * 0.05                            # the pole runs up behind the sign to its middle
        tube(pole, Vector((hand.x, hand.y, G + 1.1)) + back, Vector((hand.x, hand.y, top + h * 0.5)) + back, 0.02)
        P.people.append((px, py, yaw, "one"))
        P.exclude.append((px - 0.55, py - 0.55, px + 0.95, py + 0.6))


# ------------------------------------------------------------------ barricades
def build_barricades(P, rng):
    m = P.m("metal_grey")
    x0, y0, x1, y1 = FOH_ENCLOSURE
    barricade_run(m, (x0, y1), (x1, y1))                # front
    barricade_run(m, (x0, y0), (x0, y1))
    barricade_run(m, (x1, y0), (x1, y1))
    barricade_run(m, (x0, y0), (3.0, y0), unit=2.5)     # back, gate at x 3.0..4.5
    for sx, sy in TOWERS:
        h = TOWER_RING
        c = [(sx - h, sy - h), (sx + h, sy - h), (sx + h, sy + h), (sx - h, sy + h)]
        for a, b in zip(c, c[1:] + c[:1]):
            barricade_run(m, a, b)


# ------------------------------------------------------------------ module entry
def build(rng):
    P = Parts()
    report = {}
    steps = [("foh", build_foh), ("towers", lambda P, r: [build_tower(P, x, y, r) for x, y in TOWERS]),
             ("masts", lambda P, r: [build_mast(P, x, y, t, k, r) for (x, y), t, k in MASTS]),
             ("totems", build_totems), ("barricades", build_barricades)]
    if not TOTEMS:                                      # totems draw from rng last: the rest builds identically
        steps = [s for s in steps if s[0] != "totems"]
    for name, fn in steps:
        n0 = P.count()
        fn(P, rng)
        report[name] = P.count() - n0
    print(f"[INFRA] tris by feature {report}; beams {len(P.beams.faces)} quads; halos {len(P.halos.faces)} quads",
          flush=True)
    return {"lit": [(bm, key) for key, bm in P.lit.items()], "glow": [P.glow], "beams": [P.beams],
            "halos": [P.halos], "lights": P.lights, "exclude": P.exclude, "people": P.people}
