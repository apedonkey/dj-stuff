"""Stage dressing around the DJ (Blender 4.5, headless): the Dino Stage's deck and DJ riser as a headliner's stage.

Side-fill stacks flanking the booth, CO2 cryo jets and flame projectors along the deck front and on the riser corners,
road cases with stencils and LED accents, cable snakes and ramps, floor fixtures (moving heads, blinders), a VJ table
with a laptop and a lighting desk on the left wing, an SFX/backline corner on the right wing, and Jurassic dressing tied
to the bones: fossil fragments, amber-crystal lamps, volcanic rocks with glowing cracks. Stage guests dance on the wings
(GUESTS). Emissive accents are soft and static (the user finds flashing too much).

Pre-drop meters, Z up, DJ at the origin facing -Y. The deck top is z=0 (x +-25, y -4.5..13.5); the DJ riser
(x +-4.5, y -2.5..3.0) tops out at z=1.0 (Tribe's floor after the 1 m drop). Kept clear: the DJ (x +-2.5, y -0.6..2.6
on the riser), the walk from there down the stairs (riser x 2.5..4.5, y 1.1..3.0; deck x 4.5..7, y 1.1..2.9), the
existing props (dino_stage.py), |x| > 18 (the arch) and the screen line (y ~10.3). Things at the deck's front edge stay
under the DJ's sightline to the front rows.
"""
import kit as _kit
from kit import *

NAME = "stagedeck"
BAKE_SIZE = 2048
GUESTS = True             # False (set before build()): no stage guests (they need crowd3's optional floor-z extension)

RISER_Z = 1.0                                   # riser top (pre-drop)
DJ = Vector((0.0, 0.8, 2.6))                    # the DJ's eyes (pre-drop)


# ------------------------------------------------------------------ helpers
class Parts:
    """Output collector: one lit bmesh per LIT key, the glow and halo bmeshes, lights, extra people."""

    def __init__(self):
        self.lit, self.glow, self.halos = {}, bmesh.new(), bmesh.new()
        self.lights, self.people = [], []

    def m(self, key):
        if key not in self.lit:
            self.lit[key] = bmesh.new()
        return self.lit[key]

    def count(self):
        return sum(tris(b) for b in self.lit.values()) + tris(self.glow)


def gl(P, faces, key):
    glow_faces(P.glow, faces, key)
    return faces


def tube(bm, a, b, r, segs=6):
    return cyl(bm, a, b, r, segs=segs, cap=False)


def frame(yaw=0.0, pitch=0.0):
    """The rotation kit.box applies for (yaw, pitch); a box's local -Y face is its 'front'."""
    return Matrix.Rotation(yaw, 3, "Z") @ Matrix.Rotation(pitch, 3, "X")


def facing(frm, to):
    """Yaw that turns a local -Y front at `frm` toward `to` (horizontally)."""
    return math.atan2(to[0] - frm[0], -(to[1] - frm[1]))


class Plane:
    """2D drawing plane: o + r*u + up*v (+ n*w); front normal n = r x up."""

    def __init__(self, o, r, up):
        self.o, self.r, self.up = Vector(o), Vector(r).normalized(), Vector(up).normalized()
        self.n = self.r.cross(self.up).normalized()

    def p(self, u, v, w=0.0):
        return self.o + self.r * u + self.up * v + self.n * w


def front_plane(c, size, yaw=0.0, pitch=0.0, out=0.005):
    """Drawing plane on the local -Y face of box(c, size, yaw, pitch), facing out of it."""
    R = frame(yaw, pitch)
    return Plane(Vector(c) + R @ Vector((0, -size[1] / 2 - out, 0)), R @ Vector((1, 0, 0)), R @ Vector((0, 0, 1)))


def flat(bm, pl, pts, w=0.0):
    """One-sided convex polygon of (u, v) points in plane pl, facing pl.n."""
    pts = list(pts)
    if sum(p[0] * q[1] - q[0] * p[1] for p, q in zip(pts, pts[1:] + pts[:1])) < 0:
        pts.reverse()
    return [bm.faces.new([bm.verts.new(pl.p(u, v, w)) for u, v in pts])]


def rect(bm, pl, u0, v0, u1, v1, w=0.0):
    return flat(bm, pl, [(u0, v0), (u1, v0), (u1, v1), (u0, v1)], w)


def disc(bm, pl, cu, cv, r, n=12, w=0.0):
    return flat(bm, pl, [(cu + r * math.cos(2 * math.pi * k / n), cv + r * math.sin(2 * math.pi * k / n)) for k in range(n)],
                w)


def stencil(bm, pl, text, pixel, cu=0.0, cv=0.0):
    """5x7 dot-matrix lettering centered at (cu, cv) of plane pl: painted (a lit mesh) or LEDs (the glow mesh)."""
    tw, s = text_width(text, pixel), pixel * 0.82
    faces = []
    for ci, ch in enumerate(text.upper()):
        for r, row in enumerate(_kit._FONT.get(ch, _kit._FONT[" "])):
            for c, px in enumerate(row):
                if px == "#":
                    u, v = cu - tw / 2 + (ci * 6 + c) * pixel, cv - 3.5 * pixel + (6 - r) * pixel
                    faces += rect(bm, pl, u, v, u + s, v + s)
    return faces


def smooth_path(pts, step=0.3):
    """Catmull-Rom through the waypoints, resampled about every `step` meters."""
    q = [Vector(p) for p in pts]
    q = [q[0]] + q + [q[-1]]
    out = []
    for i in range(1, len(q) - 2):
        p0, p1, p2, p3 = q[i - 1], q[i], q[i + 1], q[i + 2]
        n = max(2, int((p2 - p1).length / step))
        for k in range(n):
            t = k / n
            out.append(0.5 * (2 * p1 + (p2 - p0) * t + (2 * p0 - 5 * p1 + 4 * p2 - p3) * t * t
                              + (3 * p1 - p0 - 3 * p2 + p3) * t * t * t))
    out.append(q[-2])
    return out


def sweep(bm, pts, radii, segs=6):
    """Open tube through points with a radius per point (parallel-transported rings)."""
    pts = [Vector(p) for p in pts]
    n = len(pts)
    t_prev = (pts[1] - pts[0]).normalized()
    nrm = t_prev.cross(Vector((0, 0, 1)) if abs(t_prev.z) < 0.9 else Vector((1, 0, 0))).normalized()
    rings = []
    for i, p in enumerate(pts):
        t = (pts[min(i + 1, n - 1)] - pts[max(i - 1, 0)]).normalized()
        axis = t_prev.cross(t)
        if axis.length > 1e-6:
            nrm = Matrix.Rotation(t_prev.angle(t), 3, axis.normalized()) @ nrm
        t_prev = t
        b = t.cross(nrm).normalized()
        nn = b.cross(t).normalized()
        rings.append([bm.verts.new(p + (nn * math.cos(2 * math.pi * k / segs) + b * math.sin(2 * math.pi * k / segs))
                                   * radii[i]) for k in range(segs)])
    faces = []
    for r0, r1 in zip(rings, rings[1:]):
        for k in range(segs):
            k1 = (k + 1) % segs
            faces.append(bm.faces.new((r0[k], r0[k1], r1[k1], r1[k])))
    return faces


def hose(P, pts, r=0.016, step=0.12):
    path = smooth_path(pts, step)
    sweep(P.m("rubber"), path, [r] * len(path), segs=5)


def moving_head(P, base, aim, key, s=1.0):
    """Floor moving head standing on `base`, its head along `aim`, lens glowing `key`. Returns (lens, direction)."""
    m = P.m("metal_dark")
    base, d = Vector(base), Vector(aim).normalized()
    yaw = math.atan2(-d.x, d.y)
    side = Vector((math.cos(yaw), math.sin(yaw), 0.0))
    box(m, base + Vector((0, 0, 0.08 * s)), (0.38 * s, 0.32 * s, 0.16 * s), yaw=yaw)
    for sg in (-1, 1):
        box(m, base + side * (0.18 * s * sg) + Vector((0, 0, 0.33 * s)), (0.05 * s, 0.13 * s, 0.36 * s), yaw=yaw)
    hc = base + Vector((0, 0, 0.43 * s))
    cyl(m, hc - d * 0.18 * s, hc + d * 0.2 * s, 0.135 * s, segs=12)
    lens = hc + d * 0.205 * s
    gl(P, cyl(P.glow, lens - d * 0.01, lens + d * 0.01, 0.11 * s, segs=12), key)
    return lens, d


# ------------------------------------------------------------------ speakers, effects, fixtures
def cabinet(P, c, size, yaw, pitch=0.0, horn=False, badge=True):
    """Speaker cabinet: black box, a black grille recessed in a thin grey frame, an optional horn slot above it, a small
    lit badge."""
    blk, dark, gry = P.m("truck_black"), P.m("metal_dark"), P.m("metal_grey")
    R = frame(yaw, pitch)
    w, d, h = size
    box(blk, c, size, yaw=yaw, pitch=pitch)
    hz = 0.15 if horn else 0.0
    gw, gh = w - 0.07, h - 0.07 - hz
    gc = c + R @ Vector((0, -d / 2 - 0.003, -hz / 2))
    box(dark, gc, (gw, 0.008, gh), yaw=yaw, pitch=pitch)
    for s in (-1, 1):
        box(gry, gc + R @ Vector((s * gw / 2, -0.003, 0)), (0.014, 0.01, gh), yaw=yaw, pitch=pitch)
        box(gry, gc + R @ Vector((0, -0.003, s * gh / 2)), (gw + 0.014, 0.01, 0.014), yaw=yaw, pitch=pitch)
    if horn:
        hc = c + R @ Vector((0, -d / 2 - 0.003, h / 2 - 0.035 - hz / 2))
        box(dark, hc, (w * 0.64, 0.01, hz - 0.03), yaw=yaw, pitch=pitch)
        box(gry, hc + R @ Vector((0, -0.004, 0)), (w * 0.64 + 0.014, 0.008, 0.012), yaw=yaw, pitch=pitch)
    if badge:
        pl = front_plane(c, size, yaw, pitch, out=0.012)
        gl(P, rect(P.glow, pl, gw / 2 - 0.17, -h / 2 + 0.06, gw / 2 - 0.05, -h / 2 + 0.082), "white_dim")


def side_fill(P, base, face_to):
    """Side-fill stack on the riser: a sub and two two-way tops splayed up at the DJ's head. Returns where its cable
    leaves the back."""
    base = Vector(base)
    yaw = facing(base, face_to)
    R = frame(yaw)
    sw, sd, sh = 0.84, 0.9, 0.62
    c = base + Vector((0, 0, sh / 2))
    cabinet(P, c, (sw, sd, sh), yaw, badge=False)
    gl(P, rect(P.glow, front_plane(c, (sw, sd, sh), yaw, out=0.012), sw / 2 - 0.1, -sh / 2 + 0.012, sw / 2 - 0.075,
               -sh / 2 + 0.028), "blue_dim")                                                       # power LED
    tw, td, th = 0.72, 0.5, 0.4
    z = base.z + sh + 0.01
    for k, extra in enumerate((0.0, 0.07)):                                                       # the upper splays down
        tc = Vector((base.x, base.y, z + th / 2)) + R @ Vector((0, 0.05, 0))
        tilt = -math.atan2(DJ.z - tc.z, (DJ - tc).xy.length) + extra                              # aimed at the head
        cabinet(P, tc, (tw, td, th), yaw, tilt, horn=True, badge=(k == 0))
        z += th + 0.015
    return base + R @ Vector((0, sd / 2 + 0.02, 0.04))


def co2_jet(P, base, aim, supply):
    """CO2 cryo jet: floor plate, post and yoke, a barrel aimed along `aim` with a soft cool nozzle ring and a status
    LED, and its supply hose through the waypoints `supply`."""
    base, d = Vector(base), Vector(aim).normalized()
    dark, gry = P.m("metal_dark"), P.m("metal_grey")
    box(dark, base + Vector((0, 0, 0.02)), (0.34, 0.34, 0.04))
    cyl(gry, base + Vector((0, 0, 0.04)), base + Vector((0, 0, 0.3)), 0.032, segs=8)
    yaw = math.atan2(-d.x, d.y)
    side = Vector((math.cos(yaw), math.sin(yaw), 0.0))
    for sg in (-1, 1):
        box(gry, base + side * 0.095 * sg + Vector((0, 0, 0.37)), (0.025, 0.06, 0.16), yaw=yaw)
    hc = base + Vector((0, 0, 0.4))
    cyl(dark, hc - d * 0.2, hc + d * 0.2, 0.07, segs=14)
    cyl(gry, hc + d * 0.2, hc + d * 0.3, 0.045, segs=12, r2=0.03)
    gl(P, cyl(P.glow, hc + d * 0.3, hc + d * 0.315, 0.034, segs=12), "screen_teal")
    gl(P, cyl(P.glow, hc - d * 0.05 + side * 0.07, hc - d * 0.03 + side * 0.07, 0.012, segs=6), "green_dim")
    hose(P, [hc - d * 0.2] + [Vector(p) for p in supply], 0.018)


def flame_unit(P, base, yaw, fuel):
    """Flame projector: a steel box with a top nozzle and deflector, a soft ember pilot at the tip, armed/ready LEDs,
    carry handles; its fuel line through `fuel`."""
    base = Vector(base)
    R = frame(yaw)
    gry, dark = P.m("metal_grey"), P.m("metal_dark")
    size = (0.46, 0.46, 0.34)
    c = base + Vector((0, 0, size[2] / 2))
    box(gry, c, size, yaw=yaw)
    box(dark, c + Vector((0, 0, size[2] / 2 + 0.012)), (0.42, 0.42, 0.024), yaw=yaw)
    top = base + Vector((0, 0, size[2] + 0.024))
    cyl(dark, top, top + Vector((0, 0, 0.2)), 0.048, segs=12, r2=0.036)
    cyl(gry, top + Vector((0, 0, 0.17)), top + Vector((0, 0, 0.19)), 0.07, segs=12)
    gl(P, cyl(P.glow, top + Vector((0, 0, 0.2)), top + Vector((0, 0, 0.215)), 0.026, segs=10), "ember")
    pl = front_plane(c, size, yaw)
    gl(P, disc(P.glow, pl, -0.12, 0.08, 0.016, 8), "amber")
    gl(P, disc(P.glow, pl, -0.06, 0.08, 0.016, 8), "red_dim")
    for su in (-1, 1):
        box(dark, c + R @ Vector((su * (size[0] / 2 + 0.02), 0, 0.08)), (0.03, 0.2, 0.03), yaw=yaw)
    hose(P, [base + R @ Vector((0, size[1] / 2, 0.06))] + [Vector(p) for p in fuel])


def blinder(P, base, aim):
    """Two-lite audience blinder on a floor yoke, its warm lamps softly lit."""
    base, d = Vector(base), Vector(aim).normalized()
    yaw, tilt = math.atan2(d.x, -d.y), -math.asin(max(-1.0, min(1.0, d.z)))
    dark, gry = P.m("metal_dark"), P.m("metal_grey")
    box(dark, base + Vector((0, 0, 0.02)), (0.44, 0.3, 0.04), yaw=yaw)
    R = frame(yaw)
    for sg in (-1, 1):
        box(gry, base + R @ Vector((sg * 0.34, 0, 0.18)), (0.03, 0.06, 0.32), yaw=yaw)
    size = (0.62, 0.24, 0.31)
    c = base + Vector((0, 0, 0.32))
    box(dark, c, size, yaw=yaw, pitch=tilt)
    pl = front_plane(c, size, yaw, tilt)
    for su in (-0.15, 0.15):
        gl(P, disc(P.glow, pl, su, 0.0, 0.12, 14), "black")
        gl(P, disc(P.glow, pl, su, 0.0, 0.085, 14, w=0.004), "warm_dim")


# ------------------------------------------------------------------ cases, racks, cables
def flight_case(P, base, size, yaw=0.0, label=None, accent=None, wheels=False):
    """Road case: black body, aluminium edges and ball corners, recessed handles, a painted stencil on the front, an
    optional LED strip along the front bottom edge. Returns the top center."""
    base = Vector(base)
    blk, alu, gry = P.m("truck_black"), P.m("metal_alu"), P.m("metal_grey")
    R = frame(yaw)
    w, d, h = size
    z0 = base.z
    if wheels:
        for sx in (-1, 1):
            for sy in (-1, 1):
                p = base + R @ Vector((sx * (w / 2 - 0.08), sy * (d / 2 - 0.08), 0))
                box(gry, p + Vector((0, 0, 0.085)), (0.06, 0.06, 0.03), yaw=yaw)
                cyl(P.m("rubber"), p + R @ Vector((-0.02, 0, 0.045)), p + R @ Vector((0.02, 0, 0.045)), 0.045, segs=8)
        z0 += 0.1
    c = Vector((base.x, base.y, z0 + h / 2))
    box(blk, c, size, yaw=yaw)
    e = 0.028
    for sx in (-1, 1):
        for sy in (-1, 1):
            box(alu, c + R @ Vector((sx * w / 2, sy * d / 2, 0)), (e, e, h + 0.004), yaw=yaw)
    for sz in (-1, 1):
        for sy in (-1, 1):
            box(alu, c + R @ Vector((0, sy * d / 2, sz * h / 2)), (w + 0.004, e, e), yaw=yaw)
        for sx in (-1, 1):
            box(alu, c + R @ Vector((sx * w / 2, 0, sz * h / 2)), (e, d + 0.004, e), yaw=yaw)
            for sy in (-1, 1):
                box(alu, c + R @ Vector((sx * w / 2, sy * d / 2, sz * h / 2)), (0.055, 0.055, 0.055), yaw=yaw)
    for sx in (-1, 1):                                                   # recessed handles on the ends
        box(alu, c + R @ Vector((sx * (w / 2 + 0.004), 0, h * 0.18)), (0.01, 0.2, 0.09), yaw=yaw)
    pl = front_plane(c, size, yaw, out=0.004)
    if label:
        px = min(0.045, (w - 0.16) / (len(label) * 6), (h - 0.14) / 7)
        stencil(P.m("plastic_white"), pl, label, px, 0.0, 0.04)
    if accent:
        gl(P, rect(P.glow, pl, -w / 2 + 0.05, -h / 2 + 0.04, w / 2 - 0.05, -h / 2 + 0.065, w=0.002), accent)
    return c + Vector((0, 0, h / 2))


def case_stack(P, rng, base, specs, yaw=0.0):
    """Cases stacked on each other (spec: size, label, accent), each a little turned; the bottom one on casters."""
    p = Vector(base)
    for k, (size, label, accent) in enumerate(specs):
        top = flight_case(P, p, size, yaw + rng.uniform(-0.06, 0.06), label, accent, wheels=(k == 0))
        p = Vector((p.x + rng.uniform(-0.04, 0.04), p.y + rng.uniform(-0.04, 0.04), top.z))


def amp_rack(P, base, yaw, label, h=1.15, units=7):
    """Rack case with its front lid off: amplifiers with a row of soft status LEDs each (nothing blinks)."""
    base = Vector(base)
    dark = P.m("metal_dark")
    w, d = 0.62, 0.62
    flight_case(P, base, (w, d, h), yaw)
    c = base + Vector((0, 0, h / 2))
    R = frame(yaw)
    uh = (h - 0.2) / units
    for k in range(units):
        uc = c + R @ Vector((0, -d / 2 - 0.006, h / 2 - 0.14 - uh * (k + 0.5)))
        box(dark, uc, (w - 0.1, 0.012, uh - 0.02), yaw=yaw)
        pl = Plane(uc + R @ Vector((0, -0.008, 0)), R @ Vector((1, 0, 0)), Vector((0, 0, 1)))
        for i, key in enumerate(("blue_dim", "green_dim", "green_dim", "amber" if k % 3 == 0 else "green_dim")):
            u = -0.2 + i * 0.035
            gl(P, rect(P.glow, pl, u, -0.012, u + 0.018, 0.006), key)
        gl(P, rect(P.glow, pl, 0.12, -0.02, 0.22, -0.012), "screen_blue")
    stencil(P.m("plastic_white"), front_plane(c, (w, d, h), yaw, out=0.014), label, 0.022, 0.0, h / 2 - 0.07)


def snake(P, waypoints, r=0.034, buddy=0.014):
    """Multicore cable lying through the waypoints (Catmull-Rom), with a thinner cable alongside. Returns its path."""
    pts = smooth_path(waypoints, 0.32)
    sweep(P.m("rubber"), pts, [r] * len(pts), segs=6)
    if buddy:
        side = []
        for i, p in enumerate(pts):
            t = (pts[min(i + 1, len(pts) - 1)] - pts[max(i - 1, 0)]).normalized()
            s = t.cross(Vector((0, 0, 1)))
            side.append(p + (s.normalized() * 0.075 if s.length > 1e-6 else Vector()) - Vector((0, 0, r - buddy)))
        sweep(P.m("rubber"), side, [buddy] * len(side), segs=4)
    return pts


def cable_ramp(P, path, at, n=2):
    """Cable protector segments over a snake where people cross: yellow lids on black ramps, along the cable."""
    i = min(range(len(path)), key=lambda k: (path[k].xy - Vector(at).xy).length)
    t = path[min(i + 1, len(path) - 1)] - path[max(i - 1, 0)]
    t.z = 0
    t.normalize()
    yaw = math.atan2(-t.x, t.y)                                         # the segment's local Y runs along the cable
    for k in range(n):
        c = Vector((path[i].x, path[i].y, 0.0)) + t * 0.91 * (k - (n - 1) / 2)
        box(P.m("rubber"), c + Vector((0, 0, 0.02)), (0.52, 0.9, 0.04), yaw=yaw)
        box(P.m("truck_yellow"), c + Vector((0, 0, 0.055)), (0.2, 0.88, 0.03), yaw=yaw)
        for sg in (-1, 1):
            box(P.m("rubber"), c + frame(yaw) @ Vector((sg * 0.18, 0, 0.045)), (0.16, 0.9, 0.02), yaw=yaw,
                roll=-sg * 0.32)


def record_bag(P, base, yaw):
    """The DJ's record bag, leaning back a little: boxy body, a flap with a buckle and a red patch, a shoulder strap
    over the top that drops to the floor."""
    base = Vector(base)
    bag, tilt = P.m("canvas_black"), 0.1
    R = frame(yaw, -tilt)
    w, d, h = 0.44, 0.19, 0.38
    c = base + Vector((0, 0, h / 2 + 0.01)) + R @ Vector((0, 0.02, 0))
    box(bag, c, (w, d, h), yaw=yaw, pitch=-tilt)
    box(bag, c + R @ Vector((0, -0.012, h / 2 - 0.06)), (w + 0.012, d + 0.03, 0.14), yaw=yaw, pitch=-tilt)  # flap
    box(P.m("metal_grey"), c + R @ Vector((0, -d / 2 - 0.03, h / 2 - 0.12)), (0.05, 0.012, 0.035), yaw=yaw,
        pitch=-tilt)                                                                               # buckle
    box(P.m("canvas_red"), c + R @ Vector((-0.12, -d / 2 - 0.027, h / 2 - 0.06)), (0.09, 0.006, 0.05), yaw=yaw,
        pitch=-tilt)                                                                               # patch
    strap = [c + R @ Vector((-w / 2 - 0.01, 0, -0.05)), c + R @ Vector((-w / 2 - 0.02, 0, h / 2 + 0.04)),
             c + R @ Vector((0, 0.02, h / 2 + 0.07)), c + R @ Vector((w / 2 + 0.02, 0, h / 2 + 0.03)),
             c + R @ Vector((w / 2 + 0.05, -0.05, 0.0)), base + R @ Vector((w / 2 + 0.16, -0.18, 0.012))]
    pts = smooth_path(strap, 0.05)
    sweep(bag, pts, [0.013] * len(pts), 4)


def led_batten(P, c, length, face_to, cells=10):
    """A low LED batten on a floor bracket, its lens cells tilted up toward `face_to` (soft warm, static)."""
    c = Vector(c)
    yaw = facing(c, face_to)
    tilt = -0.55                                                       # lenses up and toward the target
    size = (length, 0.1, 0.09)
    hc = c + Vector((0, 0, 0.09))
    for s in (-1, 1):
        box(P.m("metal_dark"), c + frame(yaw) @ Vector((s * (length / 2 - 0.08), 0, 0.04)), (0.03, 0.08, 0.08),
            yaw=yaw)
    box(P.m("metal_dark"), hc, size, yaw=yaw, pitch=tilt)
    pl = front_plane(hc, size, yaw, tilt, out=0.003)
    step = (length - 0.08) / cells
    for k in range(cells):
        u = -length / 2 + 0.04 + step * (k + 0.5)
        gl(P, disc(P.glow, pl, u, 0.0, step * 0.32, 8), "warm_dim")


def water_case(P, base, yaw):
    """A small case with a towel and a few water bottles on it."""
    top = flight_case(P, base, (0.52, 0.4, 0.42), yaw)
    R = frame(yaw)
    box(P.m("canvas_white"), top + R @ Vector((0.1, 0, 0.012)), (0.26, 0.34, 0.024), yaw=yaw + 0.2)
    for k in range(5):
        b = top + R @ Vector((-0.17 + (k % 3) * 0.07, -0.08 + (k // 3) * 0.08, 0))
        cyl(P.m("plastic_blue"), b, b + Vector((0, 0, 0.21)), 0.033, segs=8)
        cyl(P.m("plastic_white"), b + Vector((0, 0, 0.21)), b + Vector((0, 0, 0.235)), 0.016, segs=6)


def deck_hatch(P, c):
    """A small cable hatch in the deck where lines go under the stage."""
    box(P.m("metal_dark"), Vector(c) + Vector((0, 0, 0.012)), (0.34, 0.26, 0.024))


# ------------------------------------------------------------------ the VJ table and the SFX corner
def vj_table(P, c):
    """Folding table along X, the VJ on its -Y side facing the big screen (+Y): a laptop, a compact lighting desk with
    two screens, a touch monitor, a gooseneck lamp, a rack case under it, black skirts at the back and the ends."""
    c = Vector(c)
    blk, dark, gry = P.m("truck_black"), P.m("metal_dark"), P.m("metal_grey")
    w, d, h = 1.7, 0.72, 0.76
    box(blk, c + Vector((0, 0, h - 0.02)), (w, d, 0.04))
    for sx in (-1, 1):
        for sy in (-1, 1):
            tube(gry, c + Vector((sx * (w / 2 - 0.06), sy * (d / 2 - 0.06), 0)),
                 c + Vector((sx * (w / 2 - 0.06), sy * (d / 2 - 0.06), h - 0.04)), 0.018)
    sk = P.m("canvas_black")
    box(sk, c + Vector((0, d / 2 - 0.01, h / 2)), (w, 0.012, h - 0.06))
    for sx in (-1, 1):
        box(sk, c + Vector((sx * (w / 2 - 0.01), 0, h / 2)), (0.012, d, h - 0.06))
    flight_case(P, c + Vector((-0.35, 0.05, 0)), (0.6, 0.5, 0.5), 0.0, "VJ")
    top = c.z + h
    # laptop: base and screen tilted back, facing the VJ (-Y)
    lb = Vector((c.x - 0.45, c.y - 0.08, top + 0.01))
    box(dark, lb, (0.36, 0.25, 0.02))
    sc, ss, tilt = lb + Vector((0, 0.13, 0.11)), (0.36, 0.012, 0.23), -0.26
    box(dark, sc, ss, pitch=tilt)
    pl = front_plane(sc, ss, 0.0, tilt)
    gl(P, rect(P.glow, pl, -0.16, -0.095, 0.16, 0.095), "screen_blue")
    for k, key in enumerate(("purple_dim", "screen_teal", "purple_dim")):
        gl(P, rect(P.glow, pl, -0.14 + k * 0.1, -0.07, -0.06 + k * 0.1, 0.02, w=0.002), key)
    # lighting desk: a tilted body with fader caps, two screens at its back
    dc, ds = Vector((c.x + 0.25, c.y - 0.06, top + 0.06)), (0.72, 0.42, 0.08)
    box(dark, dc, ds, pitch=0.14)
    for su in (-0.17, 0.17):
        mc, ms = dc + Vector((su, 0.2, 0.15)), (0.3, 0.03, 0.2)
        box(dark, mc, ms, pitch=-0.35)
        gl(P, rect(P.glow, front_plane(mc, ms, 0.0, -0.35), -0.13, -0.085, 0.13, 0.085), "screen_teal")
    Rd = frame(0.0, 0.14)
    fpl = Plane(dc + Rd @ Vector((0, 0, 0.042)), Vector((1, 0, 0)), Rd @ Vector((0, 1, 0)))
    for k in range(8):
        u = -0.3 + k * 0.08
        gl(P, rect(P.glow, fpl, u, -0.12, u + 0.025, -0.1), "amber" if k % 4 == 0 else "white_dim")
    # touch monitor on a short stand at the right end, turned to the VJ
    tm, tms = Vector((c.x + 0.72, c.y + 0.12, top + 0.32)), (0.46, 0.03, 0.29)
    tyaw = facing(tm, (c.x, c.y - 0.75))
    tube(gry, Vector((tm.x, tm.y, top)), tm, 0.02)
    box(dark, tm, tms, yaw=tyaw, pitch=-0.1)
    gl(P, rect(P.glow, front_plane(tm, tms, tyaw, -0.1), -0.21, -0.13, 0.21, 0.13), "sky")
    # gooseneck lamp with a warm head over the desk
    lp = Vector((c.x - 0.1, c.y + 0.3, top))
    tube(dark, lp, lp + Vector((0, -0.05, 0.3)), 0.01, segs=5)
    tube(dark, lp + Vector((0, -0.05, 0.3)), lp + Vector((0, -0.2, 0.36)), 0.01, segs=5)
    gl(P, sphere(P.glow, lp + Vector((0, -0.22, 0.35)), 0.03, segs=8, rings=4), "bulb_warm")
    P.lights.append(light("Deck_VJLamp", "POINT", lp + Vector((0, -0.22, 0.3)), (1.0, 0.75, 0.45), 14, size=0.05))


def co2_bottles(P, c, yaw, n=5):
    """A row of CO2 bottles chained to a rail, hoses from their valves into a manifold. Returns the manifold's end."""
    c = Vector(c)
    R = frame(yaw)
    dark, gry, wht = P.m("metal_dark"), P.m("metal_grey"), P.m("plastic_white")
    span = (n - 1) * 0.3
    for sg in (-1, 1):                                                   # rail frame behind the bottles
        tube(gry, c + R @ Vector((sg * (span / 2 + 0.25), 0.2, 0)), c + R @ Vector((sg * (span / 2 + 0.25), 0.2, 1.1)),
             0.025)
    for z in (0.45, 0.85):
        tube(gry, c + R @ Vector((-span / 2 - 0.25, 0.2, z)), c + R @ Vector((span / 2 + 0.25, 0.2, z)), 0.02)
    man = c + R @ Vector((0, 0.24, 1.05))
    box(gry, man, (span + 0.2, 0.08, 0.08), yaw=yaw)
    for k in range(n):
        b = c + R @ Vector((-span / 2 + k * 0.3, 0, 0))
        cyl(dark, b, b + Vector((0, 0, 0.92)), 0.105, segs=12)
        cyl(dark, b + Vector((0, 0, 0.92)), b + Vector((0, 0, 1.0)), 0.105, segs=12, r2=0.045)
        cyl(wht, b + Vector((0, 0, 0.78)), b + Vector((0, 0, 0.86)), 0.108, segs=12, cap=False)
        cyl(gry, b + Vector((0, 0, 1.0)), b + Vector((0, 0, 1.08)), 0.03, segs=8)
        v = b + Vector((0, 0, 1.08))
        hose(P, [v, v + Vector((0, 0, 0.1)), man + R @ Vector((-span / 2 + k * 0.3, -0.05, 0.0))], 0.012, 0.06)
    return man + R @ Vector((-span / 2 - 0.1, 0, 0))


def sfx_control(P, base, yaw):
    """SFX control case: a flight case with a control top: e-stop, armed key, status LEDs."""
    top = flight_case(P, base, (0.7, 0.5, 0.82), yaw, "SFX", "red_dim")
    R = frame(yaw)
    panel = top + Vector((0, 0, 0.012))
    box(P.m("metal_dark"), panel, (0.6, 0.4, 0.024), yaw=yaw)
    pl = Plane(panel + Vector((0, 0, 0.013)), R @ Vector((1, 0, 0)), R @ Vector((0, 1, 0)))
    gl(P, cyl(P.glow, panel + R @ Vector((0.18, -0.05, 0.012)), panel + R @ Vector((0.18, -0.05, 0.06)), 0.045, segs=12),
       "red")
    for k in range(4):
        gl(P, disc(P.glow, pl, -0.22 + k * 0.07, 0.1, 0.016, 8), "green_dim")
    gl(P, disc(P.glow, pl, -0.05, -0.08, 0.02, 8), "amber")


# ------------------------------------------------------------------ jurassic dressing
class Rock:
    """A lumpy boulder: radius(dir) = R * (1 + a few smooth waves), squashed by `scale`, its bottom flattened on z0."""

    def __init__(self, rng, c, R, scale=(1.3, 1.0, 0.8), z0=0.0, waves=7, amp=0.2):
        self.c, self.R, self.s, self.z0 = Vector(c), R, Vector(scale), z0
        self.w = [(Vector((rng.gauss(0, 1), rng.gauss(0, 1), rng.gauss(0, 1))).normalized() * rng.uniform(1.6, 3.8),
                   rng.uniform(0, 2 * math.pi), amp * rng.uniform(0.5, 1.0) / math.sqrt(waves)) for _ in range(waves)]

    def point(self, u, lift=0.0):
        u = Vector(u).normalized()
        r = self.R * (1 + sum(a * math.sin(f.dot(u) + ph) for f, ph, a in self.w)) + lift
        p = self.c + Vector((u.x * self.s.x, u.y * self.s.y, u.z * self.s.z)) * r
        p.z = max(p.z, self.z0 + (0.004 if lift else 0.0))
        return p

    def mesh(self, bm, subdiv=2):
        ret = bmesh.ops.create_icosphere(bm, subdivisions=subdiv, radius=1.0)
        for v in ret["verts"]:
            v.co = self.point(v.co)
        return list({f for v in ret["verts"] for f in v.link_faces})


def crack_walk(rng, u, n, step=0.1, wander=0.28):
    """A crack's path on the unit sphere: a walk that keeps its heading with a little wander (no loops)."""
    heading = Vector((rng.gauss(0, 1), rng.gauss(0, 1), rng.gauss(0, 1)))
    pts = []
    for i in range(n):
        pts.append(u.copy())
        tdir = (heading - u * heading.dot(u)).normalized()
        heading = (tdir + Vector((rng.gauss(0, wander), rng.gauss(0, wander), rng.gauss(0, wander)))).normalized()
        u = (u + tdir * step).normalized()
    return pts


def lava_rock(P, rng, c, R, scale=(1.35, 1.0, 0.85), cracks=7):
    """Basalt boulder with glowing lava cracks (an ember band with a fire core) that branch, mostly on the side facing
    the DJ; a low orange light for the glow on the deck around it."""
    rock = Rock(rng, c, R, scale, z0=0.0)
    rock.mesh(P.m("metal_dark"), subdiv=3)
    look = (DJ - rock.c).normalized()
    paths = []
    for k in range(cracks):
        u = (look + Vector((rng.uniform(-0.9, 0.9), rng.uniform(-0.9, 0.9), rng.uniform(-0.2, 0.9)))).normalized()
        main = crack_walk(rng, u, rng.randint(7, 12))
        paths.append((main, 1.0))
        if rng.random() < 0.6:                                         # a thinner branch off its middle
            paths.append((crack_walk(rng, main[len(main) // 2], rng.randint(3, 6)), 0.6))
    for pts, wk in paths:
        for key, wdt, lift in (("ember", 0.034, 0.01), ("fire", 0.013, 0.016)):
            for i, (a, b) in enumerate(zip(pts, pts[1:])):
                taper = wk * (1.0 - 0.6 * i / max(1, len(pts) - 2))
                pa, pb = rock.point(a, lift), rock.point(b, lift)
                s = (pb - pa).cross((rock.point((a + b) / 2) - rock.c).normalized())
                if s.length < 1e-6:
                    continue
                s = s.normalized() * wdt * taper / 2
                gl(P, quad(P.glow, pa - s, pa + s, pb + s, pb - s), key)
    P.lights.append(light(f"Deck_Lava{c[0]:+.0f}{c[1]:+.0f}", "POINT", rock.c + look * R * 1.4 + Vector((0, 0, 0.1)),
                          (1.0, 0.32, 0.06), 40 * R, size=0.3))


def amber_cluster(P, rng, c, n=5, h=0.75):
    """Amber crystals growing from a dark rock: faceted glowing prisms with pointed tips, a soft halo, a warm light."""
    c = Vector(c)
    Rock(rng, c + Vector((0, 0, 0.05)), 0.26, (1.3, 1.1, 0.7), z0=c.z).mesh(P.m("metal_dark"))
    for k in range(n):
        d = Vector((rng.uniform(-0.5, 0.5), rng.uniform(-0.5, 0.5), 1.0)).normalized()
        L, r = h * rng.uniform(0.5, 1.0), rng.uniform(0.05, 0.1)
        a = c + Vector((rng.uniform(-0.12, 0.12), rng.uniform(-0.12, 0.12), 0.08))
        key = ("amber", "orange", "amber", "bulb_warm", "amber", "orange")[k % 6]
        gl(P, cyl(P.glow, a, a + d * L * 0.78, r, segs=6, cap=False), key)
        gl(P, cyl(P.glow, a + d * L * 0.78, a + d * L, r, segs=6, cap=False, r2=0.004), key)
    halo(P.halos, c + Vector((0, 0, h * 0.55)), 1.3, "amber", planes=1)
    P.lights.append(light(f"Deck_Amber{c.x:+.0f}{c.y:+.0f}", "POINT", c + Vector((0, 0, h * 0.6)), (1.0, 0.58, 0.14),
                          35, size=0.2))


def amber_lamp(P, rng, base, h=2.1):
    """Lamp post: a curved bone rising from a knob, three bone claws cupping a glowing amber globe."""
    base = Vector(base)
    bone = P.m("bone")
    lean = Vector((rng.uniform(-0.12, 0.12), rng.uniform(-0.12, 0.12), 0))
    pts = smooth_path([base, base + Vector((0, 0, h * 0.4)) + lean * 0.3, base + Vector((0, 0, h * 0.8)) + lean,
                       base + Vector((0, 0, h)) + lean * 1.3], 0.15)
    sweep(bone, pts, [0.075 - 0.035 * i / (len(pts) - 1) for i in range(len(pts))], segs=8)
    sphere(bone, base + Vector((0, 0, 0.08)), 0.15, segs=10, rings=6, scale=(1.0, 1.0, 0.6))
    g = base + Vector((0, 0, h + 0.17)) + lean * 1.3
    gl(P, sphere(P.glow, g, 0.16, segs=12, rings=8), "amber")
    for k in range(3):
        a = 2 * math.pi * k / 3 + 0.4
        o = Vector((math.cos(a), math.sin(a), 0))
        cp = smooth_path([g - Vector((0, 0, 0.17)), g + o * 0.2 - Vector((0, 0, 0.06)), g + o * 0.16 + Vector((0, 0, 0.12)),
                          g + o * 0.06 + Vector((0, 0, 0.2))], 0.05)
        sweep(bone, cp, [0.028 - 0.022 * i / (len(cp) - 1) for i in range(len(cp))], segs=5)
    halo(P.halos, g, 1.1, "amber", planes=1)
    P.lights.append(light(f"Deck_Lamp{base.x:+.0f}{base.y:+.0f}", "POINT", g, (1.0, 0.62, 0.22), 45, size=0.15))


def vertebra(P, c, yaw, s=1.0):
    """A big dinosaur vertebra lying on the deck: centrum, neural arch, spine, transverse processes."""
    bone = P.m("bone")
    R = Matrix.Rotation(yaw, 3, "Z")

    def at(x, y, z):
        return Vector(c) + R @ (Vector((x, y, z)) * s)
    cyl(bone, at(0, -0.17, 0.21), at(0, 0.17, 0.21), 0.2 * s, segs=14)
    for sy in (-0.17, 0.17):
        cyl(bone, at(0, sy, 0.21), at(0, sy * 1.12, 0.21), 0.21 * s, segs=14, r2=0.17 * s)
    box(bone, at(0, -0.02, 0.43), (0.24 * s, 0.16 * s, 0.14 * s), yaw=yaw)
    cyl(bone, at(0, -0.04, 0.45), at(0, 0.06, 1.0), 0.07 * s, segs=6, r2=0.025 * s)
    for sx in (-1, 1):
        cyl(bone, at(sx * 0.1, 0, 0.43), at(sx * 0.5, 0.05, 0.55), 0.055 * s, segs=6, r2=0.02 * s)
        sphere(bone, at(sx * 0.07, -0.12, 0.5), 0.045 * s, segs=6, rings=4)


def femur(P, a, b, s=1.0):
    """A long thigh bone lying from a to b: shaft, ball head, knobby condyles."""
    bone = P.m("bone")
    a, b = Vector(a), Vector(b)
    d = (b - a).normalized()
    side = d.cross(Vector((0, 0, 1))).normalized()
    cyl(bone, a + d * 0.12, b - d * 0.12, 0.065 * s, segs=10)
    sphere(bone, a + side * 0.06 + Vector((0, 0, 0.03)), 0.11 * s, segs=10, rings=6)
    sphere(bone, a - side * 0.05 + d * 0.06, 0.085 * s, segs=8, rings=5)
    for sg in (-1, 1):
        sphere(bone, b + side * 0.06 * sg, 0.09 * s, segs=10, rings=6)


def claw(P, base, yaw, L=0.75):
    """A raptor claw lying on its side: a tapered horn curling over."""
    R = Matrix.Rotation(yaw, 3, "Z")
    pts, radii = [], []
    for i in range(13):
        t = i / 12
        a = t * math.radians(120)
        pts.append(Vector(base) + R @ Vector((L * 0.62 * math.sin(a), 0, 0.1 + L * 0.42 * (1 - math.cos(a)) * 0.75)))
        radii.append(0.1 * (1 - t) ** 0.9 + 0.006)
    sweep(P.m("bone"), pts, radii, segs=8)


def rib(P, c, yaw, L=1.6):
    """A loose rib arching over the deck (like the stage's own)."""
    d = Vector((math.cos(yaw), math.sin(yaw), 0))
    pts = [Vector(c) + d * L * (t - 0.5) + Vector((0, 0, 0.08 + 0.55 * math.sin(math.pi * t))) for t in
           [i / 12 for i in range(13)]]
    sweep(P.m("bone"), pts, [0.07 * (1 - 0.55 * i / 12) + 0.015 for i in range(13)], segs=7)


# ------------------------------------------------------------------ layout
def build_riser(P, rng):
    """On the riser (z=1): side-fills facing the DJ, CO2 jets on the front corners; cables over the riser edges."""
    for sx in (-1, 1):
        out = side_fill(P, (sx * 3.6, 0.25, RISER_Z), (0.0, 0.8))
        # over the riser's side edge, then in front of the stair walk (y < 1.1) to the VJ table / the amp racks
        run = [(7.1, 1.1), (7.15, 2.3), (7.05, 2.75)] if sx > 0 else [(-7.3, 1.0), (-7.35, 1.95)]
        snake(P, [out, Vector((sx * 4.3, 0.72, RISER_Z + 0.032)), Vector((sx * 4.5, 0.66, RISER_Z + 0.032)),
                  Vector((sx * 4.57, 0.62, RISER_Z - 0.1)), Vector((sx * 4.6, 0.56, 0.45)), Vector((sx * 4.64, 0.5, 0.034)),
                  Vector((sx * 5.4, 0.62, 0.034)), Vector((sx * 6.6, 0.8, 0.034))]
              + [Vector((x, y, 0.034)) for x, y in run], r=0.03)
        jet = Vector((sx * 4.15, -2.15, RISER_Z))
        co2_jet(P, jet, (sx * 0.25, -0.45, 1.0),
                [jet + Vector((0, 0.12, 0.06)), Vector((sx * 4.42, -2.2, RISER_Z + 0.02)),
                 Vector((sx * 4.53, -2.22, RISER_Z + 0.02)), Vector((sx * 4.58, -2.25, 0.85)),
                 Vector((sx * 4.61, -2.28, 0.45)), Vector((sx * 4.64, -2.3, 0.02)), Vector((sx * 4.75, -2.05, 0.02))])
    record_bag(P, (3.5, -0.62, RISER_Z), facing((3.5, -0.62), (0.0, 0.8)))      # the DJ's own stuff, beside the zone
    water_case(P, (-3.5, -0.75, RISER_Z), facing((-3.5, -0.75), (0.0, 0.8)))
    for sx in (-1, 1):                                                  # low LED battens on the riser lip, up at the DJ
        led_batten(P, (sx * 1.55, -2.32, RISER_Z), 1.0, (0.0, 0.8))


def build_front(P, rng):
    """Deck front edge (z=0), between the existing deck-lip heads: two flame projectors and a CO2 jet, kept low; their
    lines run back under the wedge monitors."""
    for x, wx in ((-2.5, -2.3), (3.5, 2.6)):
        flame_unit(P, (x, -4.12, 0.0), 0.0, [Vector((x + 0.05, -3.7, 0.02)), Vector((wx, -3.35, 0.02)),
                                             Vector((wx, -3.1, 0.02))])
    jet = Vector((0.5, -4.08, 0.0))
    co2_jet(P, jet, (0.0, -0.4, 1.0), [jet + Vector((0, 0.15, 0.05)), Vector((0.9, -3.65, 0.02)),
                                       Vector((2.15, -3.25, 0.02))])


def build_back(P, rng):
    """Behind the riser: two floor moving heads aimed up past the screen, a DINO case, the snakes off the riser."""
    for sx in (-1, 1):                                                  # set back so the DJ sees them over the riser edge
        moving_head(P, (sx * 1.6, 4.1, 0.0), (sx * 0.15, 0.3, 1.0), "purple_dim", s=1.1)
    flight_case(P, (0.0, 4.6, 0.0), (1.05, 0.56, 0.62), 0.0, "DINO", "screen_teal", wheels=True)
    paths = {}
    drop = [(0.0, 2.9, RISER_Z + 0.034), (0.0, 3.01, RISER_Z + 0.034), (0.02, 3.07, RISER_Z - 0.12),
            (0.04, 3.1, 0.45), (0.06, 3.12, 0.04)]                   # over the riser's back edge
    for name, x0, pts in (("left", 0.35, [(1.0, 3.35), (2.6, 3.5), (4.6, 3.55), (6.1, 3.6), (6.85, 3.25)]),
                          ("right", -0.35, [(-1.0, 3.35), (-2.6, 3.45), (-4.6, 3.5), (-6.4, 3.3), (-7.3, 2.75)]),
                          ("back", 0.0, [(0.85, 3.4), (0.95, 4.6), (0.5, 6.5), (0.9, 7.9), (1.2, 8.6)])):   # ends in front of the arch screen (y 9.0)
        sgn = 1.0 if x0 >= 0 else -1.0
        paths[name] = snake(P, [Vector((x0 + sgn * dx, y, z)) for dx, y, z in drop]
                            + [Vector((x, y, 0.034)) for x, y in pts])
    cable_ramp(P, paths["left"], (5.4, 3.58), n=2)
    cable_ramp(P, paths["right"], (-5.4, 3.48), n=2)


def build_left(P, rng):
    """Left wing (+X): the VJ table, case stacks, an amber lamp, a lava-rock and fossil corner, a blinder, a floor head."""
    vj_table(P, (7.8, 3.05, 0.0))
    amber_lamp(P, rng, (5.3, 4.3, 0.0))
    case_stack(P, rng, (8.75, 5.3, 0.0), [((1.2, 0.62, 0.72), "LX", "purple_dim"), ((1.0, 0.55, 0.5), "FX", None)])
    case_stack(P, rng, (7.2, 5.8, 0.0), [((0.8, 0.6, 0.62), "MON", None)], yaw=0.3)
    lava_rock(P, rng, (11.3, 1.6, 0.0), 0.85, cracks=9)
    amber_cluster(P, rng, (10.15, 3.4, 0.0), n=6, h=0.8)
    vertebra(P, (12.8, -0.35, 0.0), 0.9, s=0.95)
    femur(P, (10.4, 4.6, 0.08), (11.8, 5.0, 0.08))
    blinder(P, (8.45, -0.85, 0.0), (-0.15, -1.0, 0.45))
    moving_head(P, (12.9, 3.4, 0.0), (0.2, 0.25, 1.0), "blue_dim", s=1.1)
    case_stack(P, rng, (14.3, 3.9, 0.0), [((1.2, 0.65, 0.8), "BACKLINE", "warm_dim"), ((1.2, 0.65, 0.6), "ROAR", None)],
               yaw=-0.2)


def build_right(P, rng):
    """Right wing (-X): the SFX/backline corner (CO2 bottles, SFX control, amp racks), an amber lamp, lava rocks,
    amber crystals and fossils, a blinder, a floor head."""
    man = co2_bottles(P, (-7.45, 4.75, 0.0), 0.0, n=5)
    hatch = Vector((-8.4, 3.25, 0.0))
    deck_hatch(P, hatch)
    snake(P, [man, man + Vector((-0.2, 0.05, -0.5)), Vector((man.x - 0.25, man.y + 0.05, 0.03)),
              Vector((-8.3, 3.9, 0.03)), hatch + Vector((0, 0.05, 0.02))], r=0.022, buddy=0)
    sfx_control(P, (-9.1, 3.75, 0.0), facing((-9.1, 3.75), (0.0, 0.8)))
    for x, label in ((-7.6, "AUDIO"), (-8.3, "AMP")):
        amp_rack(P, (x, 2.3, 0.0), facing((x, 2.3), (0.0, 0.8)), label)
    amber_lamp(P, rng, (-5.3, 4.3, 0.0))
    lava_rock(P, rng, (-11.1, 2.3, 0.0), 1.0, cracks=11)
    lava_rock(P, rng, (-12.4, 0.5, 0.0), 0.5, cracks=5)
    amber_cluster(P, rng, (-9.2, 1.15, 0.0), n=5, h=0.7)
    claw(P, (-10.6, 4.4, 0.0), 2.3)
    rib(P, (-11.8, 4.2, 0.0), 1.2)
    vertebra(P, (-13.2, 2.6, 0.0), -0.4, s=1.1)
    blinder(P, (-8.45, -0.85, 0.0), (0.15, -1.0, 0.45))
    moving_head(P, (-12.9, 3.6, 0.0), (-0.2, 0.25, 1.0), "blue_dim", s=1.1)
    case_stack(P, rng, (-14.3, 4.1, 0.0), [((1.2, 0.65, 0.8), "DINO", "screen_teal"), ((0.9, 0.6, 0.55), "CDJ", None)],
               yaw=0.25)


def build_guests(P, rng):
    """Stage guests on the wings (crowd3 people standing on the deck: the 5th value is their floor z, pre-drop)."""
    for x, y, pose in ((6.45, -0.05, "up"), (7.75, 0.75, "one"), (11.7, -0.9, "up"),
                       (-6.6, 0.35, "up"), (-7.85, -0.45, "one"), (-11.4, -0.8, "down")):
        yaw = math.pi + rng.uniform(-0.5, 0.5) if rng.random() < 0.6 else math.atan2(x, 0.8 - y)
        P.people.append((x, y, yaw, pose, 0.0))
    P.people.append((7.8, 2.3, 0.0, "hips", 0.0))                       # the VJ at the table, facing the screen


# ------------------------------------------------------------------ module entry
def build(rng):
    P = Parts()
    report = {}
    steps = [("riser", build_riser), ("front", build_front), ("back", build_back), ("left", build_left),
             ("right", build_right)]
    if GUESTS:
        steps.append(("guests", build_guests))
    for name, fn in steps:
        n0 = P.count()
        fn(P, rng)
        report[name] = P.count() - n0
    print(f"[STAGEDECK] tris by area {report}; halos {len(P.halos.faces)} quads", flush=True)
    return {"lit": [(bm, key) for key, bm in P.lit.items()], "glow": [P.glow], "beams": [], "halos": [P.halos],
            "lights": P.lights, "exclude": [], "people": P.people}
