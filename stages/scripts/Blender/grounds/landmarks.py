"""Festival-grounds module LANDMARKS: the backdrop beyond the inner festival field (Blender 4.5, headless).

  Ferris wheel (-48, -105)       30 m wheel, axle 17.5 m, plane turned to the DJ; LED spokes in a frozen chase, rim
                                 bulbs, 18 glowing gondolas, A-frame legs, ticket booth with an LED sign, colored pools.
  Second stage (+55, -120)       arched roof, LED wall, PA, beams; faces NNE so the DJ sees it three-quarters over its
                                 own crowd (people); washes from the roof and a backlight from its FOH.
  Statues                        brachiosaurus (+82, -56; 19.5 m), T. rex on a rock (-76, -40; 13 m), triceratops
                                 (+66, -14; 7 m): metaball bodies decimated to 3-5k tris, colored uplights, glowing eyes.
  Tree line                      a forest ring around the field and behind the stage. Trees outside this module's light
                                 cones are black unlit silhouettes (glow "black": no bake texels); lit ones are foliage.
  Camping field (y -138..-182)   tents (some glowing from inside), lanterns, fairy lights, campfires, beacon poles.
  Hills                          two rings of low black ridges at 330-460 m (inside the 480 m sky sphere).
"""
from kit import *
from mathutils import Quaternion

NAME = "landmarks"
BAKE_SIZE = 4096
TAU = 2 * math.pi
UP = Vector((0.0, 0.0, 1.0))
Z0 = GROUND_Z


class Parts:
    """This module's meshes and lists, plus a tris tally per landmark."""

    def __init__(self):
        self.lit = {}                                   # LIT key -> bmesh
        self.glow = bmesh.new()                         # light sources
        self.sil = bmesh.new()                          # black silhouettes (far trees, hills)
        self.beams, self.halos = bmesh.new(), bmesh.new()
        self.lights, self.exclude, self.people = [], [], []
        self.keepout = []                               # (x, y, r): no trees here
        self.tally = {}

    def m(self, key):
        if key not in self.lit:
            self.lit[key] = bmesh.new()
        return self.lit[key]

    def count(self):
        return sum(tris(b) for b in self.lit.values()) + tris(self.glow) + tris(self.sil)

    def run(self, name, fn, *args):
        n0 = self.count()
        fn(self, *args)
        self.tally[name] = self.count() - n0

    def add_light(self, *args, **kw):
        self.lights.append(light(*args, **kw))

    def rect(self, pts, pad=1.0):
        xs, ys = [p[0] for p in pts], [p[1] for p in pts]
        self.exclude.append((min(xs) - pad, min(ys) - pad, max(xs) + pad, max(ys) + pad))

    def result(self):
        lit = []
        for key, bm in self.lit.items():
            if len(bm.faces):
                lit.append((bm, key))
            else:
                bm.free()
        return {"lit": lit, "glow": [self.glow, self.sil], "beams": [self.beams], "halos": [self.halos],
                "lights": self.lights, "exclude": self.exclude, "people": self.people}


# ------------------------------------------------------------------ small helpers
def yaw_of(d):
    """Yaw about Z that turns +Y onto the horizontal direction d (the people convention)."""
    return math.atan2(-d[0], d[1])


def qx(deg):
    return Quaternion((1.0, 0.0, 0.0), math.radians(deg))


def paint(bm, faces, key):
    glow_faces(bm, faces, key)
    return faces


def octa(bm, c, r, rz=None):
    """Octahedron (8 tris): a bulb or lantern."""
    c, rz = Vector(c), r if rz is None else rz
    v = [bm.verts.new(c + Vector(d)) for d in ((r, 0, 0), (0, r, 0), (-r, 0, 0), (0, -r, 0), (0, 0, rz), (0, 0, -rz))]
    faces = []
    for i in range(4):
        a, b = v[i], v[(i + 1) % 4]
        faces += [bm.faces.new((a, b, v[4])), bm.faces.new((b, a, v[5]))]
    return faces


def tetra(bm, c, r):
    """Tetrahedron (4 tris): a far fairy-light bulb."""
    c = Vector(c)
    v = [bm.verts.new(c + Vector(d) * r) for d in ((0, 0, 1), (0.943, 0, -0.333), (-0.471, 0.816, -0.333),
                                                   (-0.471, -0.816, -0.333))]
    return [bm.faces.new(f) for f in ((v[0], v[1], v[2]), (v[0], v[2], v[3]), (v[0], v[3], v[1]), (v[1], v[3], v[2]))]


def ball(bm, c, r, segs, rings, scale=(1.0, 1.0, 1.0), rng=None, lump=0.0):
    """Low-poly UV sphere built in a fixed order (kit.sphere's create_uvsphere welds its poles and leaves the face
    order run-dependent); with rng, every vertex is pushed in/out by up to `lump` for an organic outline."""
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


def rod(bm, pts, r, segs=4):
    """Tube along a polyline."""
    out = []
    for p, q in zip(pts, pts[1:]):
        out += cyl(bm, p, q, r, segs=segs, cap=False)
    return out


def merge(dst, src, mat=None):
    """Append bmesh src (optionally transformed) into dst, keeping smooth flags; frees src."""
    if mat is not None:
        src.transform(mat)
    vmap = {v: dst.verts.new(v.co) for v in src.verts}
    for f in src.faces:
        try:
            dst.faces.new([vmap[v] for v in f.verts]).smooth = f.smooth
        except ValueError:
            pass
    src.free()


def spline(ctrl, per=12):
    """Catmull-Rom curve through the control points."""
    P = [Vector(c) for c in ctrl]
    P = [2 * P[0] - P[1]] + P + [2 * P[-1] - P[-2]]
    out = []
    for i in range(1, len(P) - 2):
        p0, p1, p2, p3 = P[i - 1:i + 3]
        for k in range(per):
            t = k / per
            out.append(0.5 * (2 * p1 + (p2 - p0) * t + (2 * p0 - 5 * p1 + 4 * p2 - p3) * t * t
                              + (3 * p1 - p0 - 3 * p2 + p3) * t ** 3))
    out.append(P[-2].copy())
    return out


class Blob:
    """Metaball sculpture (stiffness 2, threshold 0.6); sizes are surface sizes. Measured in Blender 4.5: an isolated
    element's surface lies at 0.575 x its radius; balls spaced 0.7 rho with radius rho / 0.65 make a tube of radius rho."""

    def __init__(self):
        self.els = []

    def ball(self, co, r):
        self.els.append(("BALL", Vector(co), r / 0.575, None, None))

    def ell(self, co, half, rot=None):
        self.els.append(("ELLIPSOID", Vector(co), 1.0, [h / 0.575 for h in half], rot))

    def chain(self, ctrl, r0, r1, ease=1.0):
        """Smooth tube through ctrl, radius r0 -> r1."""
        pts = spline(ctrl)
        cum = [0.0]
        for a, b in zip(pts, pts[1:]):
            cum.append(cum[-1] + (b - a).length)
        total, s, k = cum[-1], 0.0, 0
        while True:
            u = min(s / total, 1.0)
            while k < len(pts) - 2 and cum[k + 1] < s:
                k += 1
            seg = cum[k + 1] - cum[k]
            p = pts[k].lerp(pts[k + 1], 0.0 if seg < 1e-9 else min(1.0, (s - cum[k]) / seg))
            r = r0 + (r1 - r0) * u ** ease
            self.els.append(("BALL", p, r / 0.65, None, None))
            if s >= total:
                break
            s = min(total, s + 0.7 * r)

    def mesh(self, name, res, target):
        """Polygonize, decimate to about `target` tris; returns a smooth-shaded bmesh (temporary data removed)."""
        sc = bpy.context.scene
        mb = bpy.data.metaballs.new(name)
        mb.resolution = mb.render_resolution = res
        mb.threshold = 0.6
        ob = bpy.data.objects.new(name, mb)
        sc.collection.objects.link(ob)
        for kind, co, rad, size, rot in self.els:
            e = mb.elements.new(type=kind)
            e.co, e.radius, e.stiffness = co, rad, 2.0
            if size:
                e.size_x, e.size_y, e.size_z = size
            if rot is not None:
                e.rotation = rot
        bpy.context.view_layer.update()
        me = bpy.data.meshes.new_from_object(ob.evaluated_get(bpy.context.evaluated_depsgraph_get()))
        bpy.data.objects.remove(ob, do_unlink=True)
        bpy.data.metaballs.remove(mb)
        n = sum(len(p.vertices) - 2 for p in me.polygons)
        if n > target:
            tmp = bpy.data.objects.new(name + "Dec", me)
            sc.collection.objects.link(tmp)
            tmp.modifiers.new("Dec", "DECIMATE").ratio = target / n
            bpy.context.view_layer.update()
            me2 = bpy.data.meshes.new_from_object(tmp.evaluated_get(bpy.context.evaluated_depsgraph_get()))
            bpy.data.objects.remove(tmp, do_unlink=True)
            bpy.data.meshes.remove(me)
            me = me2
        bm = bmesh.new()
        bm.from_mesh(me)
        bpy.data.meshes.remove(me)
        for f in bm.faces:
            f.smooth = True
        return bm


def ground_pt(M, x, y, h):
    """World point on the field h meters up, under the statue-local point (x, y)."""
    p = M @ Vector((x, y, 0.0))
    return Vector((p.x, p.y, Z0 + h))


# ------------------------------------------------------------------ Ferris wheel
def ferris_wheel(P, rng):
    G = Vector((-48.0, -105.0, Z0))                       # wheel center on the ground
    n = Vector((0.3, 1.0, 0.0)).normalized()             # wheel-plane normal, toward the DJ
    u = Vector((n.y, -n.x, 0.0))                          # in-plane horizontal
    yw = math.atan2(u.y, u.x)                             # box yaw: local X -> u, local Y -> n
    H, R, RI, NG, NR = 17.5, 15.0, 13.9, 18, 54
    C = G + UP * H
    truss, hub, glow = P.m("metal_grey"), P.m("metal_dark"), P.glow       # mid-grey truss: the LEDs draw the wheel

    def W(r, th, w=0.0):
        return C + u * (r * math.cos(th)) + UP * (r * math.sin(th)) + n * w

    gth = [-math.pi / 2 + TAU * g / NG for g in range(NG)]          # gondola and spoke angles, one at the bottom
    for w in (-1.3, 1.3):
        outer = [W(R, TAU * i / NR, w) for i in range(NR + 1)]
        inner = [W(RI, TAU * i / NR, w) for i in range(NR + 1)]
        rod(truss, outer, 0.14)
        rod(truss, inner, 0.09)
        for i in range(NR):                                           # lacing between the rings
            a, b = (outer[i], inner[i + 1]) if i % 2 == 0 else (inner[i], outer[i + 1])
            cyl(truss, a, b, 0.05, segs=3, cap=False)
        for th in gth:
            cyl(truss, W(1.0, th, w * 0.85), W(RI, th, w), 0.12, segs=4, cap=False)
    for th in gth:
        cyl(truss, W(R, th, -1.3), W(R, th, 1.3), 0.08, segs=4, cap=False)       # gondola axles
    cyl(hub, C - n * 1.7, C + n * 1.7, 1.0, segs=10)                              # hub
    cyl(hub, C - n * 3.1, C + n * 3.1, 0.3, segs=6)                               # axle

    # light: LED spokes in a frozen chase (spiral), bulbs on the rim, an LED inner ring, a glowing hub
    chase = ["magenta", "cyan", "purple", "pink"]
    wf = 1.48
    for g, th in enumerate(gth):
        for j in range(6):
            r0 = 1.7 + (RI - 2.0) * j / 6
            paint(glow, cyl(glow, W(r0, th, wf), W(r0 + (RI - 2.0) / 6 - 0.45, th, wf), 0.12, segs=3, cap=False),
                  chase[(g + j) % len(chase)])
    for i in range(72):
        paint(glow, octa(glow, W(R + 0.3, TAU * i / 72, wf), 0.24), "white" if i % 6 == 0 else "bulb_warm")
    paint(glow, rod(glow, [W(RI, TAU * i / NR, wf) for i in range(NR + 1)], 0.1, segs=3), "sky")
    paint(glow, cyl(glow, C + n * 1.72, C + n * 1.86, 0.85, segs=12), "amber")

    tubs = ["canvas_red", "canvas_blue", "canvas_yellow", "canvas_green"]
    wins = ["amber", "pink", "sky"]
    for g, th in enumerate(gth):                                       # gondolas hang plumb from the rim
        pv = W(R, th)
        cyl(hub, pv, pv - UP * 0.55, 0.05, segs=3, cap=False)
        box(truss, pv - UP * 0.62, (1.8, 2.0, 0.16), yaw=yw)
        paint(glow, box(glow, pv - UP * 1.02, (1.46, 1.66, 0.62), yaw=yw), wins[g % len(wins)])
        box(P.m(tubs[g % len(tubs)]), pv - UP * 1.75, (1.6, 1.8, 0.85), yaw=yw)

    for s in (-1, 1):                                                  # A-frames on both sides of the wheel
        top = C + n * (2.7 * s)
        feet = [G + u * (8.8 * k) + n * (3.9 * s) for k in (-1, 1)]
        for ft in feet:
            cyl(truss, top, ft, 0.3, segs=6, cap=False)
            box(P.m("stone"), ft + UP * 0.25, (1.3, 1.3, 0.5), yaw=yw)
        cyl(truss, top.lerp(feet[0], 0.62), top.lerp(feet[1], 0.62), 0.15, segs=4, cap=False)
    box(hub, G + UP * 0.125, (6.0, 4.6, 0.25), yaw=yw)                # boarding platform

    B = G + n * 8.0 + u * 6.0                                          # ticket booth, sign facing the DJ
    box(P.m("truck_red"), B + UP * 1.2, (2.8, 2.0, 2.4), yaw=yw)
    box(truss, B + UP * 2.5, (3.3, 2.6, 0.18), yaw=yw)
    wc = B + n * 1.01 + UP * 1.3                                       # window (viewer's right = -u)
    paint(glow, quad(glow, wc + u * 0.9 - UP * 0.4, wc - u * 0.9 - UP * 0.4, wc - u * 0.9 + UP * 0.4,
                     wc + u * 0.9 + UP * 0.4), "warm_dim")
    box(P.m("canvas_black"), B + UP * 3.35 + n * 0.6, (5.8, 0.12, 1.3), yaw=yw)
    txt, px = "TICKETS", 0.14
    led_text(glow, txt, B + UP * (3.35 - 3.5 * px) + n * 0.67 + u * (text_width(txt, px) / 2), -u, UP,
             pixel=px, key="amber")

    P.add_light("FerrisUpL", "SPOT", G + n * 12 - u * 8 + UP * 0.6, (1.0, 0.15, 0.7), 13000, target=C - u * 5,
                spot_deg=55, size=0.3)
    P.add_light("FerrisUpR", "SPOT", G + n * 12 + u * 8 + UP * 0.6, (0.15, 0.75, 1.0), 13000, target=C + u * 5,
                spot_deg=55, size=0.3)
    P.add_light("FerrisPool", "SPOT", C + n * 5 - UP * 5, (0.55, 0.15, 1.0), 9000, target=G + n * 8, spot_deg=80)
    P.add_light("FerrisBooth", "POINT", B + n * 2.6 + UP * 2.2, (1.0, 0.7, 0.4), 150, size=0.3)

    for k in range(8):                                                 # a queue for the ride
        p = G + n * (3.4 + 0.85 * k) + u * (2.0 + rng.uniform(-0.25, 0.25))
        P.people.append((p.x, p.y, yaw_of(-n), rng.choice(("down", "down", "hips", "one"))))
    P.rect([G + u * 10 + n * 5, G - u * 10 - n * 5, B + n * 2 + u * 2, G - u * 10 + n * 5, G + u * 10 - n * 5])
    P.keepout.append((G.x, G.y, 21.0))


# ------------------------------------------------------------------ second stage
def second_stage(P, rng):
    S = Vector((55.0, -120.0, Z0))
    F = Vector((0.27, 0.963, 0.0)).normalized()          # the stage faces its crowd (F); the DJ sees it 3/4
    Lr = Vector((F.y, -F.x, 0.0))
    ys = math.atan2(Lr.y, Lr.x)                          # box yaw: local X -> Lr, local Y -> F
    WD, DP, DH, RH = 16.0, 10.0, 1.5, 11.5               # deck width, depth, height; roof frame height
    dark, black, white, glow = P.m("metal_dark"), P.m("canvas_black"), P.m("canvas_white"), P.glow

    def at(l, f, z):
        return S + Lr * l + F * f + UP * z

    box(black, at(0, 0, DH / 2), (WD, DP, DH), yaw=ys)                                    # deck
    for sl in (-1, 1):
        for sf in (-1, 1):
            box(dark, at(sl * (WD / 2 + 0.3), sf * (DP / 2 - 0.3), RH / 2), (0.55, 0.55, RH), yaw=ys)
        box(dark, at(sl * (WD / 2 + 0.3), 0, RH + 0.3), (0.6, DP, 0.6), yaw=ys)
        box(dark, at(sl * (WD / 2 + 1.1), DP / 2 - 0.4, RH + 0.3), (1.6, 0.3, 0.3), yaw=ys)  # PA outrigger
    for sf in (-1, 1):
        box(dark, at(0, sf * (DP / 2 - 0.3), RH + 0.3), (WD + 1.2, 0.6, 0.6), yaw=ys)
    arch = [(-(WD / 2 + 0.6) * math.cos(math.pi * i / 8), RH + 0.6 + 2.8 * math.sin(math.pi * i / 8)) for i in range(9)]
    for (l0, z0), (l1, z1) in zip(arch, arch[1:]):                     # barrel roof: closed panels (both sides bake)
        box(white, at((l0 + l1) / 2, 0, (z0 + z1) / 2), (math.hypot(l1 - l0, z1 - z0) + 0.06, DP + 1.0, 0.14),
            yaw=ys, roll=-math.atan2(z1 - z0, l1 - l0))
    box(black, at(0, -DP / 2 + 0.25, (DH + RH) / 2), (WD, 0.3, RH - DH), yaw=ys)         # back scrim

    right = -Lr                                                        # LED wall: blocky equalizer
    cols, rows, sw, sh = 16, 8, 12.8, 6.0
    bw, bh = sw / cols, sh / rows
    org = at(0, -DP / 2 + 0.45, DH + 0.9) - right * (sw / 2)
    ramp = ["cyan", "cyan", "sky", "blue", "purple", "purple", "magenta", "pink"]
    for c in range(cols):
        top = int(round(2 + 5.5 * (0.5 + 0.5 * math.sin(c * 0.85 + 0.6)) * rng.uniform(0.75, 1.0)))
        for r in range(rows):
            key = ramp[r] if r < top else ("white" if r == top else "blue_dim")
            o = org + right * (c * bw + 0.04) + UP * (r * bh + 0.04)
            paint(glow, quad(glow, o, o + right * (bw - 0.08), o + right * (bw - 0.08) + UP * (bh - 0.08),
                             o + UP * (bh - 0.08)), key)
    paint(glow, rod(glow, [at(l, DP / 2 + 0.55, z) for l, z in arch], 0.11, segs=3), "purple")
    for i in range(7):                                                 # fixtures on the front truss
        p = at(-6.0 + 2.0 * i, DP / 2 - 0.3, RH - 0.45)
        paint(glow, box(glow, p, (0.42, 0.42, 0.5), yaw=ys), "white")
        halo(P.halos, p + F * 0.3 - UP * 0.1, 1.6, color="white")
        if i in (1, 2, 4, 5):                                          # a few beams, a gentle fan
            k = (i - 3) / 2.0
            beam_planes(P.beams, p, Lr * (0.2 * k) + F * 0.22 + UP, 38, 0.25, 3.0,
                        color="cyan" if abs(k) > 0.75 else "magenta")
    for i in range(6):
        paint(glow, box(glow, at(-6.0 + 2.4 * i, DP / 2 - 0.5, DH + 0.18), (0.35, 0.3, 0.3), yaw=ys),
              "magenta" if i % 2 else "cyan")
    for sl in (-1, 1):                                                 # PA: hung line arrays + ground subs
        for k in range(8):
            box(dark, at(sl * (WD / 2 + 1.7), DP / 2 - 0.4 + 0.03 * k, RH - 0.7 - 0.46 * k), (1.05, 0.8, 0.42),
                yaw=ys, pitch=math.radians(2.5 * k))
        for k in range(2):
            box(dark, at(sl * (WD / 2 - 0.8 - 1.3 * k), DP / 2 + 0.9, 0.45), (1.2, 0.9, 0.9), yaw=ys)
    box(P.m("metal_grey"), at(0, DP / 2 + 2.3, 0.6), (WD + 2, 0.12, 1.2), yaw=ys)          # barrier
    fo = at(0, 26, 0)                                                  # FOH tent
    box(black, fo + UP * 0.6, (3.4, 2.4, 1.2), yaw=ys)
    box(white, fo + UP * 2.7, (4.2, 3.4, 0.14), yaw=ys)
    for sl in (-1, 1):
        for sf in (-1, 1):
            q = fo + Lr * (1.9 * sl) + F * (1.5 * sf)
            cyl(dark, q, q + UP * 2.65, 0.05, segs=3, cap=False)

    P.add_light("Stage2WashL", "SPOT", at(-5.5, DP / 2 + 0.2, RH - 0.8), (1.0, 0.15, 0.75), 9000,
                target=at(-2, 13, 0), spot_deg=65)
    P.add_light("Stage2WashR", "SPOT", at(5.5, DP / 2 + 0.2, RH - 0.8), (0.15, 0.7, 1.0), 9000,
                target=at(2, 13, 0), spot_deg=65)
    P.add_light("Stage2Roof", "SPOT", at(0, DP / 2 - 0.4, DH + 0.3), (0.6, 0.2, 1.0), 6000,
                target=at(0, -1.0, RH + 2.0), spot_deg=100)
    P.add_light("Stage2Deck", "SPOT", at(0, 0.5, RH - 1.0), (1.0, 0.55, 0.2), 4000, target=at(0, 0.5, DH),
                spot_deg=75)
    P.add_light("Stage2Back", "SPOT", fo - F * 2.5 + UP * 4.0, (0.35, 0.45, 1.0), 6000, target=at(0, 9, 0.5),
                spot_deg=55)                                           # in front of the FOH tent, not over it

    crowd = []                                                         # its own crowd, facing the stage
    tries = 0
    while len(crowd) < 110 and tries < 6000:
        tries += 1
        f = 5.4 + 17.0 * rng.random() ** 1.4
        half = 6.5 + 0.35 * (f - 5.0)
        l = rng.uniform(-half, half)
        p = at(l, f, 0)
        if any((p.x - q[0]) ** 2 + (p.y - q[1]) ** 2 < 0.8 for q in crowd):
            continue
        d = at(l * 0.4, DP / 2, 0) - p
        crowd.append((p.x, p.y, yaw_of(d), rng.choices(("up", "one", "down", "hips"), weights=(4, 3, 2, 1))[0]))
    P.people += crowd
    P.rect([at(-WD / 2 - 3, -DP / 2 - 1, 0), at(WD / 2 + 3, -DP / 2 - 1, 0), at(-14, 28, 0), at(14, 28, 0)])
    P.keepout += [(S.x, S.y, 16.0), (at(0, 14, 0).x, at(0, 14, 0).y, 15.0), (fo.x, fo.y, 7.0)]


# ------------------------------------------------------------------ dinosaur statues
def brachiosaurus(P, rng):
    pos = Vector((82.0, -56.0, Z0))                       # its tail stays just outside the DJ's straight-ahead view
    f = Vector((0.6, 0.8, 0.0)).normalized()             # walks toward the stage side, broadside to the DJ (local -X)
    M = Matrix.Translation(pos) @ Matrix.Rotation(yaw_of(f), 4, "Z")
    b = Blob()
    b.ell((0, 2.6, 9.0), (2.3, 3.0, 2.5))                                    # chest (high: sloping back)
    b.ell((0, -0.6, 8.2), (2.6, 3.5, 2.4))                                   # belly
    b.ell((0, -3.9, 7.8), (2.2, 2.5, 2.1))                                   # hips
    for s in (-1, 1):
        b.ell((s * 1.55, 3.2, 8.4), (1.1, 1.6, 1.9))                         # shoulders
        b.ell((s * 1.6, -3.9, 7.0), (1.2, 1.8, 2.1))                         # thighs
        b.chain([(s * 1.85, 3.4, 7.6), (s * 1.95, 3.75, 4.0), (s * 1.95, 3.45, 0.6)], 1.0, 0.78)
        b.chain([(s * 1.85, -4.0, 6.6), (s * 1.95, -3.3, 3.4), (s * 2.0, -4.0, 0.6)], 1.15, 0.85)
        b.ell((s * 1.95, 3.7, 0.38), (0.85, 1.0, 0.42))                      # feet
        b.ell((s * 2.0, -3.75, 0.38), (0.9, 1.1, 0.42))
    neck = [(0, 4.4, 10.0), (0, 6.4, 12.9), (-0.5, 7.6, 15.6), (-1.4, 8.2, 17.7), (-2.4, 8.4, 19.0)]
    b.chain(neck, 2.05, 0.7, ease=0.7)                                        # rises steeply, head turned to the DJ
    hd = Vector((-0.75, 0.6, -0.28)).normalized()
    hc = Vector(neck[-1]) + hd * 0.95 + UP * 0.2
    b.ell(hc, (0.64, 1.3, 0.64), rot=Vector((0, 1, 0)).rotation_difference(hd))
    b.ball(hc - hd * 0.3 + UP * 0.52, 0.46)                                  # nasal crest
    b.chain([(0, -5.6, 8.2), (0.4, -8.6, 7.0), (1.8, -11.6, 5.2), (3.8, -13.9, 3.4), (5.8, -15.3, 2.0)], 1.6, 0.18,
            ease=0.9)                                                         # tail curls away from the DJ
    merge(P.m("dino_grey"), b.mesh("LMBrachioMB", 0.32, 5000), M)
    side = hd.cross(UP).normalized()
    for s in (-1, 1):
        paint(P.glow, octa(P.glow, M @ (hc + hd * 0.35 + side * (0.62 * s) + UP * 0.22), 0.26), "amber")
    for nm, lp, tg, col, pw, deg in (
            ("BrachioGreen", (-13, 3), (0, 1.5, 8.5), (0.15, 1.0, 0.3), 24000, 50),
            ("BrachioPurple", (-10, 14), (-1.5, 8, 16), (0.55, 0.05, 1.0), 21000, 32),
            ("BrachioRim", (9, 7), (0, 3, 12), (0.5, 0.02, 1.0), 13000, 45)):        # from behind: a rim on the back
        P.add_light(nm, "SPOT", ground_pt(M, lp[0], lp[1], 0.6), col, pw, target=M @ Vector(tg), spot_deg=deg)
    P.keepout.append((pos.x - f.x * 4, pos.y - f.y * 4, 20.0))
    P.rect([M @ Vector(p) for p in ((-4, 12, 0), (4, 12, 0), (-4, -18, 0), (4, -18, 0))])


def trex(P, rng):
    pos = Vector((-76.0, -40.0, Z0))
    f = Vector((0.9, -0.43, 0.0)).normalized()            # 3/4 to the DJ; roars at the back of the crowd
    sc, rock = 1.1, 1.2
    M = Matrix.Translation(pos + UP * rock) @ Matrix.Rotation(yaw_of(f), 4, "Z") @ Matrix.Scale(sc, 4)
    neck_base = Vector((0, 4.4, 7.7))
    tgt = M.inverted() @ Vector((-6.0, -32.0, Z0 + 2.0))
    turn = max(-0.6, min(0.6, yaw_of(tgt - neck_base)))
    T = Matrix.Translation(neck_base) @ Matrix.Rotation(turn, 4, "Z") @ Matrix.Translation(-neck_base)
    Hm = T @ Matrix.Translation((0, 6.45, 9.75)) @ Matrix.Rotation(math.radians(14), 4, "X")   # head frame
    Hq = Hm.to_quaternion()
    b = Blob()

    def head_ell(co, half, deg=0.0):
        b.ell(Hm @ Vector(co), half, rot=Hq @ qx(deg))

    b.ell((0, 0.0, 6.2), (1.3, 1.9, 1.45))                                    # pelvis
    b.ell((0, 2.2, 6.45), (1.45, 2.3, 1.75), rot=qx(12))                      # belly
    b.ell((0, 3.9, 7.2), (1.15, 1.4, 1.45), rot=qx(25))                       # chest
    b.chain([(0, 4.3, 7.6), (0, 4.9, 8.5), T @ Vector((0, 5.3, 9.2))], 1.0, 0.8)
    head_ell((0, 0, 0), (0.76, 1.55, 0.74))                                    # skull, raised: roaring
    head_ell((0, 1.3, 0.12), (0.56, 0.85, 0.44))                               # upper snout
    hinge = Vector((0, -0.95, -0.35))
    head_ell(hinge + Matrix.Rotation(math.radians(-32), 3, "X") @ Vector((0, 1.35, -0.22)), (0.6, 1.4, 0.3), -32)
    for s in (-1, 1):
        head_ell((s * 0.5, -0.55, -0.25), (0.36, 0.6, 0.5))                    # cheeks
        b.ball(Hm @ Vector((s * 0.42, -0.45, 0.62)), 0.26)                      # brow knobs
        b.chain([(s * 0.95, 4.05, 6.5), (s * 1.12, 4.65, 5.9), (s * 1.02, 5.2, 6.05)], 0.3, 0.19)   # little arms
        b.ell((s * 1.15, 0.35 * s, 5.0), (0.88, 1.45, 1.9), rot=qx(12 * s))  # thighs (+X leg steps forward)
        b.chain([(s * 1.2, 0.95 + 0.7 * s, 3.6), (s * 1.25, -0.2 + 0.7 * s, 1.1)], 0.62, 0.42)
        b.chain([(s * 1.25, -0.2 + 0.7 * s, 1.1), (s * 1.3, 0.55 + 0.7 * s, 0.3)], 0.4, 0.33)
        b.ell((s * 1.3, 1.0 + 0.7 * s, 0.24), (0.55, 0.95, 0.25))            # feet
    b.chain([(0, -1.4, 6.3), (0, -4.4, 6.2), (0.5, -7.5, 5.7), (1.4, -10.4, 4.9), (2.4, -13.0, 4.2)], 1.28, 0.12)
    merge(P.m("dino_brown"), b.mesh("LMTrexMB", 0.24, 4500), M)
    for s in (-1, 1):
        paint(P.glow, octa(P.glow, M @ (Hm @ Vector((s * 0.62, -0.45, 0.32))), 0.24), "red")
    stone = P.m("stone")                                             # the rock it stands on
    rc = pos + f * 0.4
    cyl(stone, rc, rc + UP * rock, 4.8, segs=9, r2=4.2)
    for k in range(4):
        a = TAU * k / 4 + rng.uniform(-0.4, 0.4)
        ball(stone, rc + Vector((math.cos(a), math.sin(a), 0)) * rng.uniform(3.9, 4.7) + UP * 0.3,
             rng.uniform(0.9, 1.4), 6, 4, scale=(1.2, 1.0, 0.7))
    for nm, lp, tg, col, pw, deg in (
            ("TrexAmber", (-8, 8), (0, 5.5, 8.5), (1.0, 0.55, 0.12), 14000, 40),
            ("TrexRed", (-10, -2), (0, 0, 5.5), (1.0, 0.08, 0.25), 13000, 45),
            ("TrexRim", (6, 9), (0, 5, 8), (0.55, 0.05, 1.0), 11000, 32)):
        P.add_light(nm, "SPOT", ground_pt(M, lp[0], lp[1], 0.6), col, pw, target=M @ Vector(tg), spot_deg=deg)
    P.keepout.append((pos.x - f.x * 3, pos.y - f.y * 3, 17.0))
    P.rect([M @ Vector(p) for p in ((-5, 9, 0), (5, 9, 0), (-5, -14, 0), (5, -14, 0))])


def triceratops(P, rng):
    pos = Vector((66.0, -14.0, Z0))
    f = Vector((-0.7, -0.7, 0.0)).normalized()            # heads for the crowd; the DJ sees its right flank
    sc = 1.25
    M = Matrix.Translation(pos) @ Matrix.Rotation(yaw_of(f), 4, "Z") @ Matrix.Scale(sc, 4)
    b = Blob()
    b.ell((0, 0, 3.3), (1.9, 3.4, 1.85))                                      # barrel body
    b.ell((0, -0.7, 4.05), (1.45, 2.2, 1.25))                                 # hump over the hips
    b.ell((0, 3.5, 3.55), (1.2, 1.1, 1.15))                                   # neck
    b.ell((0, 5.0, 3.05), (0.85, 1.5, 0.9), rot=qx(-25))                     # skull, nose down
    b.ell((0, 6.35, 2.45), (0.45, 0.6, 0.5), rot=qx(-35))                    # beak
    b.ell((0, 4.25, 4.6), (2.1, 0.3, 1.75), rot=qx(35))                      # frill, tilted back
    for s in (-1, 1):
        b.chain([(s * 1.35, 2.3, 3.0), (s * 1.45, 2.65, 1.4), (s * 1.5, 2.4, 0.4)], 0.72, 0.58)
        b.chain([(s * 1.35, -2.0, 3.2), (s * 1.45, -2.35, 1.5), (s * 1.45, -2.0, 0.4)], 0.92, 0.62)
        b.ell((s * 1.5, 2.55, 0.25), (0.65, 0.75, 0.28))
        b.ell((s * 1.45, -1.85, 0.25), (0.75, 0.85, 0.28))
    b.chain([(0, -3.2, 3.4), (0, -5.0, 2.7), (0.4, -6.8, 1.7), (0.9, -8.1, 1.0)], 1.0, 0.15)
    merge(P.m("dino_grey"), b.mesh("LMTrikeMB", 0.24, 3000), M)
    bone = P.m("bone")
    for s in (-1, 1):                                                 # horns
        cone(bone, M @ Vector((s * 0.5, 5.0, 3.85)), M @ Vector((s * 0.75, 7.3, 4.9)), 0.22 * sc, segs=6)
    cone(bone, M @ Vector((0, 6.0, 3.05)), M @ Vector((0, 6.45, 3.75)), 0.16 * sc, segs=5)
    Rf = Matrix.Rotation(math.radians(35), 3, "X")
    fc = Vector((0, 4.25, 4.6))
    for k in range(7):                                                # spikes around the frill
        a = math.radians(-75 + 25 * k)
        rim = Vector((2.0 * math.sin(a), 0.0, 1.7 * math.cos(a)))
        out = Vector((math.sin(a), 0.0, math.cos(a)))
        cone(bone, M @ (fc + Rf @ (rim * 0.95)), M @ (fc + Rf @ (rim * 0.95 + out * 0.6)), 0.17 * sc, segs=4)
    R25 = Matrix.Rotation(math.radians(-25), 3, "X")
    for s in (-1, 1):
        paint(P.glow, octa(P.glow, M @ (Vector((0, 5.0, 3.05)) + R25 @ Vector((s * 0.72, -0.35, 0.38))), 0.2),
              "yellow")
    for nm, lp, tg, col, pw, deg in (
            ("TrikePurple", (9, 5), (0, 2.5, 3.5), (0.55, 0.05, 1.0), 10000, 45),
            ("TrikeAmber", (8, -6), (0, -1.5, 3.0), (1.0, 0.55, 0.15), 8500, 45)):
        P.add_light(nm, "SPOT", ground_pt(M, lp[0], lp[1], 0.6), col, pw, target=M @ Vector(tg), spot_deg=deg)
    P.keepout.append((pos.x, pos.y, 13.0))
    P.rect([M @ Vector(p) for p in ((-3, 8, 0), (3, 8, 0), (-3, -9, 0), (3, -9, 0))])


# ------------------------------------------------------------------ camping field
def tent(bm, kind, x, y, yaw, rng):
    R = Matrix.Translation((x, y, Z0 - 0.08)) @ Matrix.Rotation(yaw, 4, "Z")

    def V(a, b, c):
        return bm.verts.new(R @ Vector((a, b, c)))

    F = bm.faces.new
    if kind == "dome":
        r, h = rng.uniform(1.1, 1.6), rng.uniform(1.15, 1.5)
        base = [V(r * math.cos(TAU * i / 6), 0.85 * r * math.sin(TAU * i / 6), 0) for i in range(6)]
        mid = [V(0.72 * r * math.cos(TAU * i / 6), 0.6 * r * math.sin(TAU * i / 6), 0.62 * h) for i in range(6)]
        top = V(0, 0, h)
        faces = []
        for i in range(6):
            j = (i + 1) % 6
            faces += [F((base[i], base[j], mid[j], mid[i])), F((mid[i], mid[j], top))]
        return faces
    if kind == "aframe":
        a, w, h = rng.uniform(1.0, 1.3), rng.uniform(0.75, 0.95), rng.uniform(1.0, 1.3)
        b1, b2, b3, b4 = V(-a, w, 0), V(a, w, 0), V(a, -w, 0), V(-a, -w, 0)
        r1, r2 = V(-a, 0, h), V(a, 0, h)
        return [F((b1, r1, r2, b2)), F((b3, r2, r1, b4)), F((b3, b2, r2)), F((b1, b4, r1))]
    if kind == "tunnel":
        a, w, h = 2.0, 1.3, rng.uniform(1.4, 1.7)
        prof = [(-w * math.cos(math.pi * k / 4), h * math.sin(math.pi * k / 4)) for k in range(5)]
        e0 = [V(-a, py, pz) for py, pz in prof]
        e1 = [V(a, py, pz) for py, pz in prof]
        faces = [F((e0[k], e1[k], e1[k + 1], e0[k + 1])) for k in range(4)]
        return faces + [F(list(reversed(e1))), F(e0)]
    # gazebo: four legs and a pyramid roof (closed: top + underside)
    s, eave, apex = 1.6, 2.3, 2.9
    corners = [V(s * cx, s * cy, eave) for cx, cy in ((1, 1), (-1, 1), (-1, -1), (1, -1))]
    tip = V(0, 0, apex)
    faces = [F((corners[i], corners[(i + 1) % 4], tip)) for i in range(4)] + [F(list(reversed(corners)))]
    for cx, cy in ((1, 1), (-1, 1), (-1, -1), (1, -1)):
        p = R @ Vector((1.45 * cx, 1.45 * cy, 0.0))
        faces += cyl(bm, p, p + UP * eave, 0.05, segs=3, cap=False)
    return faces


def festoon(P, a, b, sag, keys, spacing=1.3, r=0.15):
    """Fairy lights: a thin wire (lit) with tetrahedron bulbs (glow) cycling through keys."""
    pts = catenary(a, b, sag, n=6)
    rod(P.m("metal_dark"), pts, 0.012, segs=3)
    L = sum((q - p).length for p, q in zip(pts, pts[1:]))
    nb = max(2, int(L / spacing))
    for i in range(1, nb):
        t = i / nb * (len(pts) - 1)
        k = min(int(t), len(pts) - 2)
        paint(P.glow, tetra(P.glow, pts[k].lerp(pts[k + 1], t - k) - UP * (r * 1.3), r), keys[i % len(keys)])


def camping(P, rng):
    X0, X1, Y0, Y1 = -58.0, 58.0, -182.0, -138.0
    fires = [(-40.0, -149.0), (-3.0, -171.0), (33.0, -147.0), (46.0, -173.0), (-33.0, -175.0)]
    beacons = [((-20.0, -158.0), "lime", "green", (0.4, 1.0, 0.15)),
               ((20.0, -162.0), "magenta", "magenta", (1.0, 0.15, 0.7)),
               ((-52.0, -160.0), "cyan", "cyan", (0.1, 0.8, 1.0)),
               ((52.0, -160.0), "yellow", "amber", (1.0, 0.8, 0.15))]

    def on_path(x, y, pad):                       # main path y=-160, cross paths x=+-20
        return abs(y + 160.0) < 2.2 + pad or abs(x + 20.0) < 1.8 + pad or abs(x - 20.0) < 1.8 + pad

    tents, tries = [], 0
    while len(tents) < 165 and tries < 20000:
        tries += 1
        x, y = rng.uniform(X0, X1), rng.uniform(Y0, Y1)
        kind = rng.choices(("dome", "aframe", "tunnel", "gazebo"), weights=(60, 22, 12, 6))[0]
        rad = {"dome": 1.5, "aframe": 1.4, "tunnel": 2.3, "gazebo": 2.2}[kind]
        if on_path(x, y, rad - 0.6):
            continue
        if any((x - fx) ** 2 + (y - fy) ** 2 < (3.4 + rad) ** 2 for fx, fy in fires):
            continue
        if any((x - bx) ** 2 + (y - by) ** 2 < (1.0 + rad) ** 2 for (bx, by), _, _, _ in beacons):
            continue
        if any((x - tx) ** 2 + (y - ty) ** 2 < (rad + tr + 0.5) ** 2 for tx, ty, tr, _ in tents):
            continue
        tents.append((x, y, rad, kind))
    canvas = (("canvas_blue", "blue_dim"), ("canvas_green", "green_dim"), ("canvas_red", "red_dim"),
              ("canvas_white", "warm_dim"), ("canvas_yellow", "warm_dim"), ("plastic_orange", "warm_dim"),
              ("canvas_black", "purple_dim"))
    for x, y, rad, kind in tents:
        key, gkey = rng.choices(canvas, weights=(20, 18, 13, 18, 10, 12, 9))[0]
        lit_inside = kind != "gazebo" and rng.random() < 0.11
        bm = P.glow if lit_inside else P.m("canvas_white" if kind == "gazebo" else key)
        faces = tent(bm, kind, x, y, rng.uniform(0, TAU), rng)
        if lit_inside:
            paint(P.glow, faces, gkey)
        if kind == "gazebo":
            paint(P.glow, octa(P.glow, (x, y, Z0 + 1.95), 0.25), "bulb_warm")

    lantern_keys = ["bulb_warm"] * 5 + ["amber"] * 2 + ["pink", "cyan", "lime", "purple"]
    for i in range(50):
        x, y, rad, kind = rng.choice(tents)
        a = rng.uniform(0, TAU)
        p = Vector((x + math.cos(a) * (rad + 0.5), y + math.sin(a) * (rad + 0.5), Z0))
        h = rng.uniform(0.3, 0.6) if rng.random() < 0.6 else 2.0
        if h > 1.0:
            cyl(P.m("metal_dark"), p, p + UP * h, 0.03, segs=3, cap=False)
        paint(P.glow, octa(P.glow, p + UP * h, rng.uniform(0.2, 0.3)), rng.choice(lantern_keys))

    warm, multi = ["bulb_warm"], ["pink", "bulb_warm", "cyan", "bulb_warm", "lime", "bulb_warm", "purple"]
    poles = [Vector((x, -157.3, Z0)) for x in (-56, -44, -32, -14, -2, 10, 28, 40, 52)]
    for p in poles:
        cyl(P.m("metal_dark"), p, p + UP * 3.8, 0.05, segs=3, cap=False)
    for i, (p, q) in enumerate(zip(poles, poles[1:])):
        festoon(P, p + UP * 3.7, q + UP * 3.7, 0.55, multi if i % 2 else warm)
    for x in (-20.0, 20.0):                                            # strings along the cross paths
        a, b = Vector((x + 1.6, -140.0, Z0)), Vector((x + 1.6, -156.0, Z0))
        for p in (a, b):
            cyl(P.m("metal_dark"), p, p + UP * 3.8, 0.05, segs=3, cap=False)
        festoon(P, a + UP * 3.7, b + UP * 3.7, 0.6, warm if x < 0 else multi)

    for i, (fx, fy) in enumerate(fires):                               # campfires with people around them
        c = Vector((fx, fy, Z0))
        cyl(P.m("stone"), c - UP * 0.05, c + UP * 0.22, 1.05, segs=8, cap=False)
        for k in range(2):
            a = rng.uniform(0, math.pi)
            d = Vector((math.cos(a), math.sin(a), 0.0)) * 0.7
            cyl(P.m("wood_dark"), c - d + UP * 0.15, c + d + UP * 0.25, 0.1, segs=4)
        paint(P.glow, cyl(P.glow, c + UP * 0.02, c + UP * 0.12, 0.8, segs=8), "ember")
        for k in range(3):
            a = TAU * k / 3 + rng.uniform(-0.3, 0.3)
            off = Vector((math.cos(a), math.sin(a), 0.0)) * 0.22
            paint(P.glow, cone(P.glow, c + off + UP * 0.1, c + off * 0.3 + UP * rng.uniform(1.0, 1.5), 0.32, segs=4),
                  "fire")
        paint(P.glow, cone(P.glow, c + UP * 0.1, c + UP * 0.75, 0.28, segs=4), "yellow")
        halo(P.halos, c + UP * 0.9, 4.0, color="amber")
        P.add_light(f"Campfire{i}", "POINT", c + UP * 1.8, (1.0, 0.5, 0.18), 500, size=0.4)   # above the flames
        n = rng.randint(3, 5)
        for k in range(n):
            a = TAU * k / n + rng.uniform(-0.3, 0.3)
            p = c + Vector((math.cos(a), math.sin(a), 0.0)) * rng.uniform(2.2, 2.8)
            P.people.append((p.x, p.y, yaw_of(c - p), rng.choice(("down", "down", "hips", "one"))))

    flags = ("canvas_red", "canvas_blue", "canvas_yellow", "canvas_green")
    for i, ((bx, by), key, hcol, col) in enumerate(beacons):          # meeting-point poles with a colored lamp
        p = Vector((bx, by, Z0))
        cyl(P.m("metal_dark"), p, p + UP * 9.0, 0.07, segs=4, cap=False)
        box(P.m(flags[i % len(flags)]), p + UP * 6.0 + Vector((0.85, 0.0, 0.0)), (1.6, 0.06, 1.0))
        paint(P.glow, octa(P.glow, p + UP * 9.35, 0.45, rz=0.6), key)
        halo(P.halos, p + UP * 9.35, 2.6, color=hcol)
        P.add_light(f"Beacon{i}", "POINT", p + UP * 8.4 + Vector((0.0, 0.35, 0.0)), col, 1400, size=0.3)  # under the lamp
    P.rect([(X0, Y0), (X1, Y1)])


# ------------------------------------------------------------------ distant hills
def hills(P, rng):
    bm = P.sil
    for r0, dep, hb, ha, n in ((330.0, 40.0, 9.0, 22.0, 120), (418.0, 30.0, 16.0, 30.0, 150)):
        ph = [rng.uniform(0, TAU) for _ in range(4)]
        base, ridge = [], []
        for i in range(n):
            th = TAU * i / n
            shape = sum(a * (0.5 + 0.5 * math.sin(fq * th + p)) for a, fq, p in zip((0.45, 0.3, 0.2, 0.1), (2, 3, 5, 9), ph))
            h = hb + ha * shape ** 1.6 + rng.uniform(-1.2, 1.2)
            r = r0 + rng.uniform(-6.0, 6.0)
            base.append(bm.verts.new((r * math.cos(th), r * math.sin(th), Z0 - 0.3)))
            ridge.append(bm.verts.new(((r + dep) * math.cos(th), (r + dep) * math.sin(th), Z0 + h)))
        faces = [bm.faces.new((base[(i + 1) % n], base[i], ridge[i], ridge[(i + 1) % n])) for i in range(n)]
        paint(bm, faces, "black")


# ------------------------------------------------------------------ tree line
CLUSTERS = [  # uplit stands at the forest edge: (x, y, radius, trees, light color; saturated so dark-green leaves
    (-82.0, -131.0, 11.0, 9, (0.5, 0.02, 1.0)),       # still read in the light's color) - behind the Ferris wheel
    (93.0, -140.0, 11.0, 8, (0.03, 1.0, 0.55)),       # right of the second stage
    (-110.0, -8.0, 10.0, 8, (0.1, 1.0, 0.2)),         # left side, level with the stage front
    (112.0, -40.0, 10.0, 8, (0.05, 0.25, 1.0)),       # beside the brachiosaurus's head (not behind the statue)
    (2.0, -204.0, 13.0, 10, (1.0, 0.03, 0.6)),        # behind the camping field, dead ahead of the DJ
    (-62.0, 57.0, 11.0, 8, (0.5, 0.02, 1.0)),         # behind the stage (stream view)
    (64.0, 57.0, 11.0, 8, (0.05, 0.3, 1.0)),
]


def cluster_lights(P):
    for i, (cx, cy, cr, _, col) in enumerate(CLUSTERS):
        c = Vector((cx, cy, Z0))
        d = Vector((-cx, -40.0 - cy, 0.0)).normalized()                     # toward the field center
        p = c + d * (cr + 10.0) + UP * 0.5
        P.add_light(f"TreeUp{i}", "SPOT", p, col, 30000, target=c + UP * 9.0, spot_deg=70)
        P.keepout.append((p.x, p.y, 4.0))                                    # no tree on top of the lamp


def tree_zone(x, y):
    """Where the forest grows: a ring around (0, -40), deeper behind the crowd, closer behind the stage."""
    dy = y + 40.0
    r = math.hypot(x, dy)
    s = dy / max(r, 1e-6)
    if not (100.0 - 14.0 * max(0.0, s) ** 2 <= r <= 170.0 + 45.0 * max(0.0, -s) ** 1.5):
        return False
    return not (20.0 < y < 47.0 and abs(x) < 36.0)                          # backstage is not ours


def in_light(P, x, y, h):
    """Inside one of this module's spot cones and bright enough to show in the bake."""
    p = Vector((x, y, Z0 + 0.5 * h))
    for L in P.lights:
        if L["kind"] != "SPOT":
            continue
        d = p - Vector(L["pos"])
        dist = d.length
        axis = (Vector(L["target"]) - Vector(L["pos"])).normalized()
        if dist > 1e-3 and d.dot(axis) / dist > math.cos(math.radians(L["spot_deg"] / 2 + 4)) \
                and L["power"] / (4 * math.pi * dist * dist) > 2.0:
            return True
    return False


def crown(bm, c, r, rng, segs, rings, squash=0.92):
    """Lumpy leaf crown: a low-poly sphere with every vertex pushed in or out (an organic silhouette)."""
    return ball(bm, c, r * 0.98, segs, rings, (1.0, 1.0, squash), rng, 0.22)


def build_tree(P, x, y, h, kind, lit, rng, lanterns=None):
    """A pine (stacked cones) or a broadleaf (lumpy crowns on a trunk); lanterns: glow key to hang lights in it."""
    if lit:
        fol, bark, segs = P.m("foliage_pine" if kind == "pine" else "foliage"), P.m("bark"), 6
    else:
        fol = bark = P.sil
        segs = 5
    base = Vector((x, y, Z0))
    lean = Vector((rng.uniform(-1, 1), rng.uniform(-1, 1), 0.0)) * (0.025 * h)
    faces, spots = [], []                                              # spots: where lanterns can hang
    if kind == "pine":
        w = rng.uniform(0.85, 1.2)
        tiers = (((0.08, 0.58, 0.215), (0.32, 0.80, 0.16), (0.55, 1.0, 0.105)) if rng.random() < 0.7
                 else ((0.1, 0.66, 0.2), (0.44, 1.0, 0.13)))
        for b, t, r in tiers:
            faces += cone(fol, base + lean * b + UP * (b * h), base + lean * t + UP * (t * h), r * h * w, segs=segs,
                          cap=False)
            spots.append((base + lean * b + UP * (b * h), (t - b) * h, r * h * w))
        if lit:
            cyl(bark, base - UP * 0.1, base + UP * (0.15 * h), 0.014 * h, segs=4, cap=False)
    else:
        cr = 0.34 * h * rng.uniform(0.85, 1.12)
        c = base + lean * 0.7 + UP * (h - cr * 0.88)
        faces += cyl(bark, base - UP * 0.1, c - UP * (0.3 * cr), 0.017 * h, segs=4 if lit else 3, cap=False)
        faces += crown(fol, c, cr, rng, 7, 4)
        a = rng.uniform(0, TAU)
        for k in range(2 if lit else (1 if rng.random() < 0.55 else 0)):   # side lobes: a wider, lower crown
            off = Vector((math.cos(a + k * 2.4), math.sin(a + k * 2.4), 0.0)) * (cr * 0.62)
            faces += crown(fol, c + off - UP * (cr * 0.45), cr * 0.72, rng, 6, 3)
        spots.append((c, 0.0, cr))
    if not lit:
        paint(P.sil, faces, "black")
    if lanterns:
        for _ in range(rng.randint(7, 10)):
            a = rng.uniform(0, TAU)
            p0, height, r = rng.choice(spots)
            if height > 0:                                             # on a pine tier's cone surface
                q = rng.uniform(0.1, 0.65)
                p = p0 + UP * (q * height) + Vector((math.cos(a), math.sin(a), 0.0)) * (r * (1 - q) + 0.15)
            else:                                                      # on the broadleaf crown
                d = Vector((math.cos(a), math.sin(a), rng.uniform(-0.4, 0.6))).normalized()
                p = p0 + d * (r * 1.02)
            paint(P.glow, octa(P.glow, p, 0.32), lanterns)


def forest(P, rng):
    trees, grid, CELL = [], {}, 8.0

    def free(x, y, d):
        gx, gy = int(x // CELL), int(y // CELL)
        for i in (gx - 1, gx, gx + 1):
            for j in (gy - 1, gy, gy + 1):
                for tx, ty in grid.get((i, j), ()):
                    if (tx - x) ** 2 + (ty - y) ** 2 < d * d:
                        return False
        return True

    def ok(x, y):
        if not tree_zone(x, y) or (-66.0 < x < 66.0 and -191.0 < y < -129.0):      # camping field
            return False
        return all((x - kx) ** 2 + (y - ky) ** 2 >= kr * kr for kx, ky, kr in P.keepout)

    def plant(x, y, h, kind, lit):
        trees.append((x, y, h, kind, lit))
        grid.setdefault((int(x // CELL), int(y // CELL)), []).append((x, y))

    for cx, cy, cr, cn, _ in CLUSTERS:                                 # the uplit stands first
        k = tries = 0
        while k < cn and tries < 500:
            tries += 1
            a, r = rng.uniform(0, TAU), cr * math.sqrt(rng.random())
            x, y = cx + r * math.cos(a), cy + r * math.sin(a)
            if ok(x, y) and free(x, y, 4.2):
                plant(x, y, rng.uniform(12.0, 19.0), "pine" if rng.random() < 0.7 else "broad", True)
                k += 1
    clumps = []                                                        # density blobs: clumps and clearings
    while len(clumps) < 46:
        x, y = rng.uniform(-215, 215), rng.uniform(-260, 135)
        if ok(x, y):
            clumps.append((x, y, rng.uniform(14, 34), rng.uniform(0.5, 1.0), rng.random() < 0.62))
    tries = 0
    while len(trees) < 440 and tries < 80000:
        tries += 1
        x, y = rng.uniform(-215, 215), rng.uniform(-260, 135)
        if not ok(x, y):
            continue
        dens, pine_w = 0.16, 0.0
        for bx, by, br, bw, bp in clumps:
            g = bw * math.exp(-((x - bx) ** 2 + (y - by) ** 2) / (br * br))
            dens += g
            pine_w += g if bp else -g
        if rng.random() > min(dens, 1.0) or not free(x, y, rng.uniform(4.8, 6.8)):
            continue
        kind = "pine" if rng.random() < 0.7 + 0.25 * math.tanh(pine_w) else "broad"
        h = rng.uniform(10.5, 18.0) + 0.03 * max(0.0, math.hypot(x, y + 40.0) - 120.0)
        h += 7.0 if rng.random() < 0.07 else (3.5 if rng.random() < 0.12 else 0.0)      # a few giants break the line
        h = min(28.0, h * (1.1 if kind == "pine" else 1.0))
        plant(x, y, h, kind, False)
    trees = [(x, y, h, kind, lit or in_light(P, x, y, h)) for x, y, h, kind, lit in trees]
    edge = [i for i, (x, y, h, kind, lit) in enumerate(trees)          # dark trees on the inner forest edge
            if not lit and math.hypot(x, y + 40.0) < 128.0]
    hung = set(rng.sample(edge, min(16, len(edge))))
    for i, (x, y, h, kind, lit) in enumerate(trees):
        build_tree(P, x, y, h, kind, lit, rng, lanterns=rng.choice(("bulb_warm", "bulb_warm", "amber", "pink"))
                   if i in hung else None)
    print(f"[LANDMARKS] trees {len(trees)} ({sum(t[4] for t in trees)} lit, {len(hung)} with lanterns), "
          f"forest tries {tries}", flush=True)


# ------------------------------------------------------------------ module entry
def build(rng):
    P = Parts()
    P.keepout += [(32.0, -92.0, 9.0), (-32.0, -92.0, 9.0), (30.0, 22.0, 9.0), (-30.0, 22.0, 9.0)]   # sky trackers
    P.run("ferris", ferris_wheel, rng)
    P.run("stage2", second_stage, rng)
    P.run("brachio", brachiosaurus, rng)
    P.run("trex", trex, rng)
    P.run("trike", triceratops, rng)
    P.run("camping", camping, rng)
    P.run("hills", hills, rng)
    cluster_lights(P)
    P.run("trees", forest, rng)
    print("[LANDMARKS] tris: " + ", ".join(f"{k} {v}" for k, v in P.tally.items())
          + f"; lights {len(P.lights)}; people {len(P.people)}", flush=True)
    return P.result()
