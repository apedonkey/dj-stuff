"""Helpers for the REACTOR plant loops (Cooling Towers, Turbine Hall, Coolant Pipes, Containment), Blender's Python on
top of vjkit: 2D outlines and strokes laid in a plane, straight tubes, rings and bolt circles, hexagons, seamless
rising-flow noise for steam, accent envelopes with a soft attack, jagged power-arc polylines, and periodic copies of
event objects for travelling loops. The 2D helpers follow the Halloween pack's hwgeo.py (re-written here, not imported:
the packs stay separate).
"""
import math

import bmesh
from mathutils import Matrix, Vector

import vjkit as vj


# ------------------------------------------------------------------ 2D shapes laid in a plane
def xz(pts, y=0.0, scale=1.0, offset=(0.0, 0.0)):
    """2D (x, y) points -> Vectors in the XZ plane at depth y (a camera on -Y looking +Y sees x right, y up)."""
    return [Vector((offset[0] + p[0] * scale, y, offset[1] + p[1] * scale)) for p in pts]


def circle2(r, n=64, cx=0.0, cy=0.0, a0=0.0):
    return [(cx + r * math.cos(a0 + 2 * math.pi * i / n), cy + r * math.sin(a0 + 2 * math.pi * i / n))
            for i in range(n)]


def hexagon(r, cx=0.0, cy=0.0, a0=0.0):
    """The 6 corners of a regular hexagon of circumradius r (a0 = 0: corners on +-x, flat top and bottom)."""
    return circle2(r, 6, cx, cy, a0)


def resample(pts, step):
    """Densify a polyline (Vectors) so no segment is longer than `step`."""
    out = [pts[0].copy()]
    for a, b in zip(pts, pts[1:]):
        n = max(1, int(math.ceil((b - a).length / step)))
        out += [a.lerp(b, i / n) for i in range(1, n + 1)]
    return out


def stroke(bm, pts, r, segs=8, closed=False, joints=True):
    """A neon tube along pts (Vectors) of radius r; small spheres round the ends and the sharp corners."""
    if len(pts) < 2:
        return
    vj.tube(bm, pts, lambda u: r, segs=segs, closed=closed, cap0=not joints, cap1=not joints)
    if not joints:
        return
    knots = [] if closed else [pts[0], pts[-1]]
    n = len(pts)
    for i in range(n if closed else n - 1):
        if not closed and i == 0:
            continue
        a, b, c = pts[i - 1], pts[i], pts[(i + 1) % n]
        if (b - a).length > 1e-6 and (c - b).length > 1e-6 and (b - a).angle(c - b) > math.radians(25):
            knots.append(b)
    for p in knots:
        bmesh.ops.create_icosphere(bm, subdivisions=1, radius=r * 1.02, matrix=Matrix.Translation(p))


def fill(bm, pts):
    """A filled polygon through pts (Vectors, any simple outline): an n-gon, ear-clip triangulated."""
    vs = [bm.verts.new(p) for p in pts]
    f = bm.faces.new(vs)
    bmesh.ops.triangulate(bm, faces=[f], quad_method="BEAUTY", ngon_method="EAR_CLIP")


def extrude(bm, outline, depth, y0=0.0, front_only=False):
    """A 2D outline [(x, z)] extruded along +Y from y0 to y0 + depth: front face (facing -Y), back face, side walls."""
    clean = []
    for p in outline:
        if not clean or abs(p[0] - clean[-1][0]) + abs(p[1] - clean[-1][1]) > 1e-6:
            clean.append(p)
    if len(clean) > 1 and abs(clean[0][0] - clean[-1][0]) + abs(clean[0][1] - clean[-1][1]) <= 1e-6:
        clean.pop()
    n = len(clean)
    area = sum(clean[i][0] * clean[(i + 1) % n][1] - clean[(i + 1) % n][0] * clean[i][1] for i in range(n))
    pts = clean if area > 0 else list(reversed(clean))
    front = [bm.verts.new((x, y0, z)) for x, z in pts]
    f = bm.faces.new(list(reversed(front)))
    bmesh.ops.triangulate(bm, faces=[f], quad_method="BEAUTY", ngon_method="EAR_CLIP")
    if front_only:
        return
    back = [bm.verts.new((x, y0 + depth, z)) for x, z in pts]
    f = bm.faces.new(back)
    bmesh.ops.triangulate(bm, faces=[f], quad_method="BEAUTY", ngon_method="EAR_CLIP")
    for i in range(n):
        j = (i + 1) % n
        bm.faces.new((front[i], front[j], back[j], back[i]))


# ------------------------------------------------------------------ 3D parts
def frame_of(normal):
    """Two unit vectors spanning the plane normal to `normal`."""
    nrm = Vector(normal).normalized()
    ref = Vector((0, 0, 1)) if abs(nrm.z) < 0.9 else Vector((1, 0, 0))
    u = nrm.cross(ref).normalized()
    return u, nrm.cross(u).normalized()


def ring_pts(center, normal, radius, n, phase=0.0):
    """n points on a circle of `radius` around `center` in the plane normal to `normal`."""
    u, v = frame_of(normal)
    c = Vector(center)
    return [c + (u * math.cos(phase + 2 * math.pi * i / n) + v * math.sin(phase + 2 * math.pi * i / n)) * radius
            for i in range(n)]


def cylinder(bm, p0, p1, r, segs=12, caps=True):
    vj.tube(bm, [Vector(p0), Vector(p1)], lambda u: r, segs=segs, cap0=caps, cap1=caps)


def ring(bm, center, normal, radius, r, n=48, segs=6):
    """A torus (flange lip, shroud, clamp) of tube radius r around `center` in the plane normal to `normal`."""
    vj.tube(bm, ring_pts(center, normal, radius, n), lambda u: r, segs=segs, closed=True)


def bolt_circle(bm, center, normal, radius, n, r, length, segs=6, phase=0.0):
    """n short bolt heads (cylinders along `normal`) on a circle."""
    nrm = Vector(normal).normalized()
    for p in ring_pts(center, normal, radius, n, phase):
        cylinder(bm, p - nrm * (length / 2), p + nrm * (length / 2), r, segs=segs)


def cone(bm, apex, direction, length, r1, segs=24, rings=6):
    """An open cone from `apex` (radius ~0) along `direction` to radius r1 (beams)."""
    d = Vector(direction).normalized()
    pts = [Vector(apex) + d * (length * i / rings) for i in range(rings + 1)]
    vj.tube(bm, pts, lambda u: 0.02 + r1 * u, segs=segs, cap0=False, cap1=False)


# ------------------------------------------------------------------ music
def flow_signals(f, period):
    """FlowA / FlowB / FlowW: two flow phases half a cycle apart and their cross-fade weight (period divides FRAMES)."""
    p = (f % period) / period
    return {"FlowA": p, "FlowB": (p + 0.5) % 1.0, "FlowW": 1.0 - abs(2.0 * p - 1.0)}


def flow_noise(s, x, z, sx, sz, rise, seed=0.0, detail=4.0, rough=0.55, distortion=0.2, contrast=1.6):
    """Noise that streams toward +z seamlessly: two layers, each shifted `rise` (in z units) per flow cycle, cross-faded
    so neither layer's jump back shows (needs FlowA/FlowB/FlowW and LoopSin in the clock). A 0..1 Fac with some of the
    contrast the cross-fade loses restored. x, z: sockets or floats; seed: a socket or float."""
    def layer(flow):
        v = s.vec(s.mul(x, sx), s.mul(s.sub(z, s.mul(s.c(flow), rise)), sz), seed)
        return s.noise4(v, s.mul(s.c("LoopSin"), 0.3), scale=1.0, detail=detail, rough=rough, distortion=distortion)
    n = s.add(s.mul(layer("FlowA"), s.c("FlowW")), s.mul(layer("FlowB"), s.inv(s.c("FlowW"))))
    return s.math("MAXIMUM", s.math("MINIMUM", s.madd(s.sub(n, 0.5), contrast, 0.5), 1.0), 0.0)


def accent_env(f, attack=2.0, decay=6.0, kick_only=False, snare_only=False):
    """Light keyed to the accents with a soft attack: rises over `attack` frames INTO each accent frame (the peak lands
    on it; no one-frame hit) and decays exp(-t / decay). Kick 1.0, snare 0.85. Periodic over the loop."""
    v = 0.0
    for af, amp in vj.accent_frames():
        snare = amp < 1.0
        if (kick_only and snare) or (snare_only and not snare):
            continue
        t = (f - af) % vj.FRAMES
        if t > vj.FRAMES / 2:
            t -= vj.FRAMES
        if -attack <= t < 0:
            v = max(v, amp * vj.ease((t + attack) / attack))
        elif t >= 0:
            v = max(v, amp * math.exp(-t / decay))
    return v


def bar_pulse(u):
    """The steam's breath through a bar (u = 0..1 from the downbeat): swells over the bar's last beat into the
    downbeat (1.0 there), then eases away. Matches the shader's traveling version (pulse_shader)."""
    up = vj.ease((u - 0.75) / 0.25) if u > 0.75 else 0.0
    return math.exp(-4.5 * u) + up * up


def pulse_shader(s, u):
    """bar_pulse() as shader nodes on a 0..1 socket (fract'ed by the caller)."""
    up = s.smooth(u, 0.75, 1.0)
    return s.add(s.exp(s.mul(u, -4.5)), s.mul(up, up))


# ------------------------------------------------------------------ arcs and events
def arc_path(p0, p1, rng, lift=None, jag=0.12, levels=5):
    """A jagged power arc from p0 to p1: midpoint displacement (the first kick `jag` x the span, halving per level),
    then bowed by `lift` (a Vector) at the middle (a parabola). A list of Vectors."""
    pts = [Vector(p0), Vector(p1)]
    amp = jag * (pts[1] - pts[0]).length
    for _ in range(levels):
        new = [pts[0]]
        for a, b in zip(pts, pts[1:]):
            d = (b - a).normalized()
            r = Vector((rng.uniform(-1, 1), rng.uniform(-1, 1), rng.uniform(-1, 1)))
            r -= d * r.dot(d)
            new += [(a + b) / 2 + r * amp, b]
        pts = new
        amp *= 0.5
    if lift is not None:
        n = len(pts) - 1
        pts = [p + Vector(lift) * (4.0 * (i / n) * (1.0 - i / n)) for i, p in enumerate(pts)]
    return pts


def ribbon_uv(bm, pts, r, segs=6, u_range=(0.0, 1.0), uv_y=0.0):
    """A tube along pts whose UV x runs u_range[0]..u_range[1] along it (reveals that grow along an arc or a crack; a
    fork gets a constant u: where it branches off); UV y = uv_y (a per-ribbon value, e.g. its index)."""
    uvl = bm.loops.layers.uv.get("UVMap") or bm.loops.layers.uv.new("UVMap")
    v0, f0 = len(bm.verts), len(bm.faces)
    vj.tube(bm, pts, lambda u: r, segs=segs, cap0=False, cap1=False)   # rings of `segs` verts, in order
    bm.verts.index_update()
    bm.faces.ensure_lookup_table()
    n = len(pts) - 1
    u0, u1 = u_range
    for i in range(f0, len(bm.faces)):
        for loop in bm.faces[i].loops:
            loop[uvl].uv = (u0 + (u1 - u0) * ((loop.vert.index - v0) // segs) / n, uv_y)
