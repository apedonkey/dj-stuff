"""2D-shape helpers shared by the GRAVEYARD SHIFT loop scenes (Blender's Python): strokes laid in a plane, neon tubes
with rounded joints, filled outlines, gears, resampling. Builds on vjkit.tube.
"""
import math

import bmesh
from mathutils import Matrix, Vector

import vjkit as vj


def xz(pts, y=0.0, scale=1.0, offset=(0.0, 0.0)):
    """2D (x, y) points -> Vectors in the XZ plane at depth y (a camera on -Y looking +Y sees x right, y up)."""
    return [Vector((offset[0] + p[0] * scale, y, offset[1] + p[1] * scale)) for p in pts]


def rot2(pts, deg, center=(0.0, 0.0)):
    c, s = math.cos(math.radians(deg)), math.sin(math.radians(deg))
    return [(center[0] + (x - center[0]) * c - (y - center[1]) * s,
             center[1] + (x - center[0]) * s + (y - center[1]) * c) for x, y in pts]


def resample(pts, step):
    """Densify a polyline (Vectors) so no segment is longer than `step` (smooth bends for tubes and deformers)."""
    out = [pts[0].copy()]
    for a, b in zip(pts, pts[1:]):
        n = max(1, int(math.ceil((b - a).length / step)))
        out += [a.lerp(b, i / n) for i in range(1, n + 1)]
    return out


def stroke(bm, pts, r, segs=8, closed=False, joints=True):
    """A neon tube along pts (Vectors) of radius r; spheres at the ends and at sharp corners round the joints."""
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
    """A filled polygon through pts (Vectors, any simple outline, concave allowed): an n-gon, ear-clip triangulated."""
    vs = [bm.verts.new(p) for p in pts]
    f = bm.faces.new(vs)
    bmesh.ops.triangulate(bm, faces=[f], quad_method="BEAUTY", ngon_method="EAR_CLIP")


def mirrored(half):
    """A closed outline from its right half [(x >= 0, y)] listed bottom to top: right side up, left side down."""
    left = [(-x, y) for x, y in reversed(half) if x > 1e-9]
    return list(half) + left


def gear_pts(r_root, r_tip, teeth, top=0.38, base=0.56):
    """A gear outline: `teeth` trapezoid teeth (top/base = shares of the tooth pitch at the tip / root radius)."""
    pts = []
    pitch = 2 * math.pi / teeth
    for i in range(teeth):
        a = i * pitch
        for da, r in ((-base / 2, r_root), (-top / 2, r_tip), (top / 2, r_tip), (base / 2, r_root)):
            pts.append((r * math.cos(a + da * pitch), r * math.sin(a + da * pitch)))
    return pts


def circle2(r, n=64, cx=0.0, cy=0.0, a0=0.0):
    return [(cx + r * math.cos(a0 + 2 * math.pi * i / n), cy + r * math.sin(a0 + 2 * math.pi * i / n))
            for i in range(n)]


def pointed_arch(x0, x1, y_spring, rise, n=10):
    """A gothic pointed arch from (x0, y_spring) up to its apex and down to (x1, y_spring): two circle arcs whose
    centers sit on the springing line (an equilateral arch when rise = 0.866 * span)."""
    span = x1 - x0
    # circle through (x0, ys) and the apex (xm, ys + rise) with its center at (c, ys), c measured from x0
    xm = (x0 + x1) / 2
    c = (span * span / 4 + rise * rise) / span            # radius, center at x0 + c (right arc's center)
    left = []
    for i in range(n + 1):
        t = i / n
        ang = math.pi - t * (math.pi - math.atan2(rise, xm - (x0 + c)))
        left.append((x0 + c + c * math.cos(ang), y_spring + c * math.sin(ang)))
    right = [(2 * xm - x, y) for x, y in reversed(left[:-1])]
    return left + right


def extrude(bm, outline, depth, y0=0.0, front_only=False):
    """A 2D outline [(x, z)] (any simple polygon, either winding) extruded along +Y from y0 to y0 + depth: front face
    (facing -Y, ear-clipped), back face and side walls. Silhouettes with rim-lit edges (the side walls graze the
    camera)."""
    clean = []
    for p in outline:                                                # drop repeated points (zero-length edges)
        if not clean or abs(p[0] - clean[-1][0]) + abs(p[1] - clean[-1][1]) > 1e-6:
            clean.append(p)
    if len(clean) > 1 and abs(clean[0][0] - clean[-1][0]) + abs(clean[0][1] - clean[-1][1]) <= 1e-6:
        clean.pop()
    outline = clean
    n = len(outline)
    area = sum(outline[i][0] * outline[(i + 1) % n][1] - outline[(i + 1) % n][0] * outline[i][1] for i in range(n))
    pts = outline if area > 0 else list(reversed(outline))           # counter-clockwise in (x, z)
    front = [bm.verts.new((x, y0, z)) for x, z in pts]
    f = bm.faces.new(list(reversed(front)))                          # normal toward -Y
    bmesh.ops.triangulate(bm, faces=[f], quad_method="BEAUTY", ngon_method="EAR_CLIP")
    if front_only:
        return
    back = [bm.verts.new((x, y0 + depth, z)) for x, z in pts]
    f = bm.faces.new(back)
    bmesh.ops.triangulate(bm, faces=[f], quad_method="BEAUTY", ngon_method="EAR_CLIP")
    for i in range(n):
        j = (i + 1) % n
        bm.faces.new((front[i], front[j], back[j], back[i]))


def lancet(cx, z0, w, h, n=8):
    """A lancet window outline: a rectangle w wide from z0 up, topped by an equilateral pointed arch (total h)."""
    rise = 0.866 * w
    arch = pointed_arch(cx - w / 2, cx + w / 2, z0 + h - rise, rise, n=n)
    return [(cx - w / 2, z0)] + arch + [(cx + w / 2, z0)]
