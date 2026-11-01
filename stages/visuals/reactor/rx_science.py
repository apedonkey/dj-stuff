"""Helpers for the REACTOR pack's science loops (Particle Ring, Geiger Scope, Isotope Lattice, Hazard Type), Blender's
Python. Neon strokes laid in a plane (after the Halloween pack's hwgeo.py, which is not imported from here), stencil
bridges for letters.py strokes, the radiation trefoil and hazard chevrons as outlines, corner rounding, and shader line
patterns. Builds on vjkit, which it does not edit.
"""
import math

import bmesh
from mathutils import Matrix, Vector

import letters
import vjkit as vj


# ------------------------------------------------------------------ 2D outlines (x right, y up)
def circle2(r, n=64, cx=0.0, cy=0.0, a0=0.0):
    return [(cx + r * math.cos(a0 + 2 * math.pi * i / n), cy + r * math.sin(a0 + 2 * math.pi * i / n))
            for i in range(n)]


def arc2(cx, cy, r, a0, a1, n):
    """n + 1 points on a circle arc from a0 to a1 (degrees, counter-clockwise positive)."""
    return [(cx + r * math.cos(math.radians(a0 + (a1 - a0) * i / n)),
             cy + r * math.sin(math.radians(a0 + (a1 - a0) * i / n))) for i in range(n + 1)]


def rounded_rect(w, h, r, n=8, cx=0.0, cy=0.0):
    pts = []
    for qx, qy, a0 in ((w / 2 - r, h / 2 - r, 0), (-w / 2 + r, h / 2 - r, 90), (-w / 2 + r, -h / 2 + r, 180),
                       (w / 2 - r, -h / 2 + r, 270)):
        pts += [(cx + qx + r * math.cos(math.radians(a0 + 90 * i / n)),
                 cy + qy + r * math.sin(math.radians(a0 + 90 * i / n))) for i in range(n + 1)]
    return pts


def chaikin(pts, iterations=2, closed=True):
    """Corner cutting: rounds the corners of a polyline [(x, y)] (each pass replaces an edge by its 1/4 and 3/4
    points)."""
    for _ in range(iterations):
        out = []
        n = len(pts)
        for i in range(n if closed else n - 1):
            a, b = pts[i], pts[(i + 1) % n]
            out.append((0.75 * a[0] + 0.25 * b[0], 0.75 * a[1] + 0.25 * b[1]))
            out.append((0.25 * a[0] + 0.75 * b[0], 0.25 * a[1] + 0.75 * b[1]))
        pts = out if closed else [pts[0]] + out + [pts[-1]]
    return pts


def trefoil(r0, n=24):
    """The radiation trefoil (the generic warning symbol) as closed outlines [(x, y)], centred on the origin: the
    centre disc (radius r0) and three blades from 1.5 r0 to 5 r0, 60 degrees wide, one pointing down."""
    out = [circle2(r0, 2 * n)]
    for c in (270.0, 30.0, 150.0):
        outer = arc2(0.0, 0.0, 5.0 * r0, c - 30.0, c + 30.0, n)
        inner = arc2(0.0, 0.0, 1.5 * r0, c + 30.0, c - 30.0, max(4, n // 3))
        out.append(outer + inner)
    return out


def chevron(w, h, t):
    """A hazard chevron pointing +x (a thick '>'): w deep, h tall, t thick along x (closed outline)."""
    return [(0.0, 0.0), (t, 0.0), (t + w, h / 2), (t, h), (0.0, h), (w, h / 2)]


def polyline_length(pts, closed=False):
    n = len(pts)
    return sum(math.dist(pts[i], pts[(i + 1) % n]) for i in range(n if closed else n - 1))


def sample_outline(pts, count, closed=True, offset=0.0):
    """`count` points spaced evenly along a polyline (offset: a share of the spacing to start at)."""
    n = len(pts)
    segs = [(pts[i], pts[(i + 1) % n]) for i in range(n if closed else n - 1)]
    total = sum(math.dist(a, b) for a, b in segs)
    step = total / (count if closed else max(count - 1, 1))
    out, acc, k = [], 0.0, 0
    for a, b in segs:
        d = math.dist(a, b)
        while k < count and (offset + k) * step <= acc + d + 1e-9:
            u = ((offset + k) * step - acc) / d if d > 0 else 0.0
            out.append((a[0] + (b[0] - a[0]) * u, a[1] + (b[1] - a[1]) * u))
            k += 1
        acc += d
    while len(out) < count:
        out.append(pts[-1] if not closed else pts[0])
    return out


# ------------------------------------------------------------------ stencil letters
def _seg_dist(p, a, b):
    ax, ay = b[0] - a[0], b[1] - a[1]
    l2 = ax * ax + ay * ay
    t = 0.0 if l2 == 0 else max(0.0, min(1.0, ((p[0] - a[0]) * ax + (p[1] - a[1]) * ay) / l2))
    return math.hypot(a[0] + ax * t - p[0], a[1] + ay * t - p[1])


def _trim_start(pts, length):
    if length <= 0:
        return list(pts)
    acc = 0.0
    for i in range(len(pts) - 1):
        a, b = pts[i], pts[i + 1]
        d = math.dist(a, b)
        if acc + d > length:
            u = (length - acc) / d
            return [(a[0] + (b[0] - a[0]) * u, a[1] + (b[1] - a[1]) * u)] + list(pts[i + 1:])
        acc += d
    return []


def trim(pts, l0, l1):
    """The polyline shortened by l0 at its start and l1 at its end ([] if nothing is left)."""
    out = _trim_start(pts, l0)
    if len(out) < 2:
        return []
    out = list(reversed(_trim_start(list(reversed(out)), l1)))
    return out if len(out) >= 2 else []


def stencil(strokes, gap, eps):
    """Stencil bridges for one glyph's monoline strokes (2D): where a stroke's end meets another stroke's end both
    pull back by gap/2; where it runs into another stroke's side it pulls back by gap. The bowls of O, D, R and the
    arms of E, T, K float free of their stems like a sprayed stencil's."""
    cuts = []
    for i, s in enumerate(strokes):
        cut = [0.0, 0.0]
        for e, p in ((0, s[0]), (1, s[-1])):
            other_ends = [q for j, t in enumerate(strokes) if j != i for q in (t[0], t[-1])]
            if len(s) > 2:
                other_ends.append(s[-1] if e == 0 else s[0])          # a closed loop meets itself
            if any(math.dist(p, q) < eps for q in other_ends):
                cut[e] = gap / 2
                continue
            sides = []
            for j, t in enumerate(strokes):
                if j == i:
                    continue
                sides += list(zip(t, t[1:]))
            if any(_seg_dist(p, a, b) < eps for a, b in sides):
                cut[e] = gap
        cuts.append(cut)
    out = []
    for s, (c0, c1) in zip(strokes, cuts):
        t = trim(s, c0, c1)
        if t:
            out.append(t)
    return out


def word_strokes(text, height, track=0.22, gap=0.09, eps=0.04, align="center"):
    """2D strokes (world units, baseline y = 0) of a line of stencil text in our letterforms (letters.py)."""
    out = []
    for _, strokes in letters.layout(text, height, track=track, align=align):
        out += stencil(strokes, gap * height, eps * height) if gap else strokes
    return out


def text_width(text, height, track=0.22):
    return letters.text_width(text, track=track) * height


# ------------------------------------------------------------------ 3D strokes
def xz(pts, y=0.0, scale=1.0, offset=(0.0, 0.0)):
    """2D (x, y) points -> Vectors in the XZ plane at depth y (a camera on -Y looking +Y sees x right, y up)."""
    return [Vector((offset[0] + p[0] * scale, y, offset[1] + p[1] * scale)) for p in pts]


def resample(pts, step):
    """Densify a polyline (Vectors) so no segment is longer than `step`."""
    out = [pts[0].copy()]
    for a, b in zip(pts, pts[1:]):
        n = max(1, int(math.ceil((b - a).length / step)))
        out += [a.lerp(b, i / n) for i in range(1, n + 1)]
    return out


def stroke(bm, pts, r, segs=8, closed=False, joints=True):
    """A neon tube along pts (Vectors) of radius r; spheres round its ends and its sharp corners."""
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
    """A filled polygon through pts (Vectors, a simple outline, concave allowed), ear-clip triangulated."""
    vs = [bm.verts.new(p) for p in pts]
    f = bm.faces.new(vs)
    bmesh.ops.triangulate(bm, faces=[f], quad_method="BEAUTY", ngon_method="EAR_CLIP")


# ------------------------------------------------------------------ shader patterns
def lines(s, v, spacing, half_w, soft=2.2):
    """1 on lines every `spacing` along v (half width half_w, a float or a socket), 0 between, soft edged."""
    t = s.math("FRACT", s.madd(v, 1.0 / spacing, 0.5))
    dist = s.mul(s.math("ABSOLUTE", s.sub(t, 0.5)), spacing)
    return s.inv(s.smooth(dist, half_w, s.mul(half_w, soft)))


def compat_euler(q, prev):
    """Euler of quaternion q kept continuous with the previous key (no 360-degree jumps between keys)."""
    return q.to_euler("XYZ", prev) if prev is not None else q.to_euler("XYZ")
