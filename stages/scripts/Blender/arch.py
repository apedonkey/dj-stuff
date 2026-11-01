"""The Dino Stage arch, v2: the two spine wings, the lintel joining them under the skull's neck, their big horns, back
spikes and bulb string, and the outline of the arch-shaped visual screen. Pure math (mathutils only, no bpy), so
everything that needs the layout imports this one module: dino_stage.build_structure() / build_visual_screen(),
skull_check.py, arch_check.py, grounds/atmosphere.py.

Space: pre-drop meters (the deck top is z = 0), Z up, the DJ at the origin facing -Y (the crowd). side -1 is the
crowd's left (x < 0), +1 the right. Every layout below is computed for the right wing and MIRRORED (x -> -x) for the
left one, so the two wings are true mirror images.

Shape (the user, 2026-10-06: "make the arches bigger ... wider" from the front, "the screen to match that arch shape"):
each wing is a quarter superellipse in the vertical plane y = PLANE_Y, from a foot sunk into the deck at x = BASE_X up
the nearly upright side, over a broad shoulder, to the skull's neck at (END_X, PLANE_Y, END_Z) where
skull.neck_vertebrae() starts. Together the wings make a broad arch (an upside-down U) around the screen.

The skull's two neck columns run forward from the spine ends to the head, so the plane had no bone between them: a
lintel (a short spine piece in the plane, a little lower than the wings' ends) bridges them and closes the arch.

The screen stands in the arch's own plane. Its edge runs 1.5 cm inside the innermost vertex line of the spine and the
lintel, which lies exactly in that plane, so the bone frames the video from every viewpoint (crowd, stream drone, the
DJ turning around) and nothing crosses the screen. The vertebra bumps fade out toward that inner edge (bump_weight).
"""
import math

from mathutils import Matrix, Vector

X, Y, Z = Vector((1, 0, 0)), Vector((0, 1, 0)), Vector((0, 0, 1))

# ------------------------------------------------------------------ the spine
PLANE_Y = 9.0                  # the arch plane (= the screen plane); skull.neck_vertebrae() starts at y 9.0
END_X, END_Z = 2.2, 17.1       # spine end at the skull's neck (skull.py: a = (s * 2.2, 9.0, SPINE_END_Z = 17.1))
BASE_X, BASE_Z = 23.4, -0.8    # the foot, its first ring 0.8 m under the deck top (the deck is x +-25, y -4.5..13.5)
EXP_X, EXP_Z = 0.66, 0.66      # superellipse exponents: x = cos^EXP_X, z = sin^EXP_Z (1 = an ellipse; lower = more
                               # upright sides and broader shoulders)
R_FOOT, R_TOP = 1.25, 0.75     # spine radius at the foot and at the skull (linear along the arc), as v7
BUMPS, BUMP_AMP = 13, 0.38     # vertebra bumps along each wing: radius x (1 + BUMP_AMP * max(0, sin)^4), as v7
RINGS, SEGS = 70, 22           # tube resolution: RINGS + 1 rings of SEGS vertices, as v7


def _profile(n=4000):
    """(arc fraction, x, z) samples of the right wing's center line, from the foot (0) to the skull (1)."""
    pts = []
    for i in range(n + 1):
        th = 0.5 * math.pi * i / n
        x = END_X + (BASE_X - END_X) * max(math.cos(th), 0.0) ** EXP_X
        z = BASE_Z + (END_Z - BASE_Z) * max(math.sin(th), 0.0) ** EXP_Z
        pts.append((x, z))
    acc = [0.0]
    for a, b in zip(pts, pts[1:]):
        acc.append(acc[-1] + math.hypot(b[0] - a[0], b[1] - a[1]))
    return [(s / acc[-1], x, z) for s, (x, z) in zip(acc, pts)], acc[-1]


_PROFILE, SPINE_LENGTH = _profile()


def _xz(t):
    """Center line (x, z) of the right wing at arc fraction t (binary search + linear interpolation)."""
    t = min(max(t, 0.0), 1.0)
    lo, hi = 0, len(_PROFILE) - 1
    while hi - lo > 1:
        mid = (lo + hi) // 2
        if _PROFILE[mid][0] <= t:
            lo = mid
        else:
            hi = mid
    s0, x0, z0 = _PROFILE[lo]
    s1, x1, z1 = _PROFILE[hi]
    f = 0.0 if s1 <= s0 else (t - s0) / (s1 - s0)
    return x0 + (x1 - x0) * f, z0 + (z1 - z0) * f


def mirror(v, side):
    """A point or direction of the right wing, mirrored onto the left one for side -1."""
    return Vector((v.x * side, v.y, v.z))


def mirror_axis(a, side):
    """A rotation axis (an axial vector) of the right wing, mirrored for side -1: (ax, -ay, -az)."""
    return Vector(a) if side > 0 else Vector((a.x, -a.y, -a.z))


def spine_point(side, t):
    """Center of the spine at arc fraction t: 0 = the foot (under the deck), 1 = the skull's neck."""
    x, z = _xz(t)
    return Vector((side * x, PLANE_Y, z))


def spine_tangent(side, t, h=1e-3):
    """Unit tangent toward the skull."""
    a, b = max(t - h, 0.0), min(t + h, 1.0)
    return (spine_point(side, b) - spine_point(side, a)).normalized()


def spine_out(side, t):
    """Unit normal in the arch plane pointing away from the opening (outward on the sides, up over the top)."""
    return mirror(Y.cross(spine_tangent(1, t)).normalized(), side)


def spine_radius(t):
    """Bare radius (no bumps): R_FOOT at the foot to R_TOP at the skull."""
    return R_FOOT + (R_TOP - R_FOOT) * t


def bump(t):
    """Vertebra bump factor at t (0..BUMP_AMP)."""
    return BUMP_AMP * max(0.0, math.sin(t * BUMPS * 2 * math.pi)) ** 4


def bump_weight(phi):
    """How much of the bump a ring vertex at angle phi gets: phi = 0 faces into the opening (the screen edge runs
    there, so no bump), pi/2 faces the crowd, pi faces out. Full bump from 80 degrees on, none within 20."""
    a = abs(math.degrees(math.atan2(math.sin(phi), math.cos(phi))))
    f = min(max((a - 20.0) / 60.0, 0.0), 1.0)
    return f * f * (3 - 2 * f)


def spine_rings(side):
    """RINGS + 1 rings of SEGS vertices each, the spine's exact mesh vertices. Vertex j of a ring points along
    cos(phi) * inward + sin(phi) * (-Y), phi = 2 pi j / SEGS: vertex 0 is the innermost one and lies in the screen
    plane. (inward, -Y, tangent) is right-handed, so spine_faces() faces outward on the right wing; the left wing is
    the mirror image (build it with the faces reversed)."""
    rings = []
    for i in range(RINGS + 1):
        t = i / RINGS
        p, inward = spine_point(1, t), -spine_out(1, t)
        r, b = spine_radius(t), bump(t)
        ring = []
        for j in range(SEGS):
            phi = 2 * math.pi * j / SEGS
            e = inward * math.cos(phi) - Y * math.sin(phi)
            ring.append(mirror(p + e * r * (1 + b * bump_weight(phi)), side))
        rings.append(ring)
    return rings


def spine_faces():
    """Faces of spine_rings() as vertex index tuples (ring i, vertex j -> i * SEGS + j): the quads, then a cap on each
    end (normals outward for the right wing)."""
    faces = []
    for i in range(RINGS):
        for j in range(SEGS):
            j1 = (j + 1) % SEGS
            faces.append((i * SEGS + j, i * SEGS + j1, (i + 1) * SEGS + j1, (i + 1) * SEGS + j))
    faces.append(tuple(reversed(range(SEGS))))
    faces.append(tuple(RINGS * SEGS + j for j in range(SEGS)))
    return faces


def inner_edge(side=1):
    """The spine's innermost vertex line (vertex 0 of every ring), in the screen plane."""
    return [ring[0] for ring in spine_rings(side)]


def _spine_inner_z(x):
    """z of the right wing's innermost vertex line (piecewise linear between rings, x falling toward the skull) at x."""
    pts = inner_edge(1)
    for a, b in zip(pts, pts[1:]):
        if (a.x - x) * (b.x - x) <= 0 and a.x != b.x:
            return a.z + (b.z - a.z) * (x - a.x) / (b.x - a.x)
    raise ValueError(f"the spine's inner edge does not pass x {x}")


# ------------------------------------------------------------------ the lintel under the skull's neck
# Without it the screen's top edge stood free between the neck columns (sky above it from the DJ and the crowd,
# arch_check 2026-10-06), and the neck vertebrae cross the plane below the spine's inner edge (z 16.17 at |x| 2.1).
LINTEL_Z = 16.85               # center height over the middle: inner edge 16.10, under those vertebrae
LINTEL_R = R_TOP               # radius (the spine's at the skull)
LINTEL_X0, LINTEL_X1 = 2.6, 3.4   # level out to |x| X0 (the neck vertebrae cross the plane at |x| 1.45..2.5), then
                                  # rising into the spine: it ends inside it at X1, its inner edge 5 mm under the spine's
LINTEL_XS = (tuple(LINTEL_X1 - (LINTEL_X1 - LINTEL_X0) * i / 4 for i in range(4))
             + tuple(LINTEL_X0 * (1 - i / 8) for i in range(9)))        # ring positions of the right half, X1 .. 0
LINTEL_Z1 = _spine_inner_z(LINTEL_X1) - 0.005 + LINTEL_R                # center height at X1


def lintel_center(x):
    """Center of the lintel at x (either half): LINTEL_Z for |x| <= X0, rising smoothly to LINTEL_Z1 at X1."""
    f = min(max((abs(x) - LINTEL_X0) / (LINTEL_X1 - LINTEL_X0), 0.0), 1.0)
    return Vector((x, PLANE_Y, LINTEL_Z + (LINTEL_Z1 - LINTEL_Z) * f * f * (3 - 2 * f)))


def lintel_bump(x):
    """One vertebra bump at the middle (the spine's spacing and amplitude); the halves meet there, so it is even."""
    p = SPINE_LENGTH / BUMPS
    return BUMP_AMP * math.cos(2 * math.pi * x / p) ** 4 if abs(x) < p / 4 else 0.0


def lintel_rings():
    """The right half of the lintel: a ring of SEGS vertices at each LINTEL_XS position, from X1 (inside the spine) to
    x = 0, where the left half (its mirror image) carries on: that ring lies in the plane x = 0, so both halves share
    it. The rings stand upright (in the planes x = const, not square to the gently rising center line), so vertex 0,
    the lowest, sits right under the center and the inner edge runs monotonic in x. Parameterized like spine_rings
    (vertex j along cos(phi) * inward + sin(phi) * (-Y), inward = -Z here), so lintel_faces() faces outward."""
    rings = []
    for x in LINTEL_XS:
        c, b = lintel_center(x), lintel_bump(x)
        ring = []
        for j in range(SEGS):
            phi = 2 * math.pi * j / SEGS
            e = -Z * math.cos(phi) - Y * math.sin(phi)
            ring.append(c + e * LINTEL_R * (1 + b * bump_weight(phi)))
        rings.append(ring)
    return rings


def lintel_faces():
    """Faces of lintel_rings() (ring i, vertex j -> i * SEGS + j): the quads, then a cap on the outer end (inside the
    spine). The x = 0 end stays open (normals outward for the right half)."""
    faces = []
    for i in range(len(LINTEL_XS) - 1):
        for j in range(SEGS):
            j1 = (j + 1) % SEGS
            faces.append((i * SEGS + j, i * SEGS + j1, (i + 1) * SEGS + j1, (i + 1) * SEGS + j))
    faces.append(tuple(reversed(range(SEGS))))
    return faces


# ------------------------------------------------------------------ horns, spikes, bulbs
def curved_path(base, direction, length, bend_axis, bend_deg, steps):
    """dino_stage.curved_path(): a polyline that turns bend_deg about bend_axis over its length."""
    pts, d, pos = [], direction.normalized(), base.copy()
    rot = Matrix.Rotation(math.radians(bend_deg) / steps, 3, bend_axis.normalized())
    for _ in range(steps + 1):
        pts.append(pos.copy())
        pos = pos + d * (length / steps)
        d = (rot @ d).normalized()
    return pts


HORN_STEPS = 26                # path segments per big horn (dino_stage.horn's default)
HORN_TIP_R = 0.03              # horn radius at its last ring: r(u) = r0 * (1 - u)^0.85 + 0.03
HORN_T = tuple(0.09 + 0.71 * k / 6 for k in range(7))
HORN_LEAN = 24.0               # degrees the horns lean toward the crowd (-Y) as they leave the spine
HORN_SWEEP = 0.22              # initial sweep along the spine toward the skull (fraction of the outward direction),
                               # fading out toward the top


def horn_radius_fn(r0):
    """dino_stage.horn()'s taper."""
    return lambda u: r0 * max(1 - u, 0.0) ** 0.85 + HORN_TIP_R


def horn(side, k):
    """Big horn k (0 = lowest, 6 = next to the skull) of a wing. Grows out of the spine's center line, outward from
    the opening and leaning toward the crowd, and curls toward the skull (about axis = d x tangent).
    Keys: t, base, tangent (spine, toward the skull), d (start direction), length, r0, axis, bend (deg), steps,
    pts (the center line, HORN_STEPS + 1 points), last (= pts[-1]), tip_tangent (dino_stage.tube's last tangent),
    apex (the tip cone's point, 0.11 m past last)."""
    t = HORN_T[k]
    s = math.sin(math.pi * t)
    p, tang, out = spine_point(1, t), spine_tangent(1, t), spine_out(1, t)
    lean = math.tan(math.radians(HORN_LEAN))
    d = (out + tang * HORN_SWEEP * (1 - t) - Y * lean).normalized()
    length = 7.0 + 7.5 * s ** 0.8
    r0 = 1.15 + 0.55 * s
    bend = 40.0 - 18.0 * max(0.0, t - 0.45) / 0.35
    axis = d.cross(tang).normalized()
    pts = curved_path(p, d, length, axis, bend, HORN_STEPS)
    tip_tan = (pts[-1] - pts[-2]).normalized()
    m = lambda v: mirror(v, side)  # noqa: E731
    pts = [m(q) for q in pts]
    return {"side": side, "k": k, "t": t, "base": m(p), "tangent": m(tang), "d": m(d), "length": length, "r0": r0,
            "axis": mirror_axis(axis, side), "bend": bend, "steps": HORN_STEPS, "pts": pts, "last": pts[-1],
            "tip_tangent": m(tip_tan), "apex": pts[-1] + m(tip_tan) * (2 * HORN_TIP_R + 0.05)}


def horns(side):
    return [horn(side, k) for k in range(len(HORN_T))]


def horn_tips(ks=(3, 4, 5, 6)):
    """grounds/atmosphere.py's HORN_TIPS: {(side, k): ((x, y, z) last point, (x, y, z) unit tangent)}, pre-drop. The
    tip cone's point (where the laser head sits) is 0.11 m past the last point along the tangent."""
    out = {}
    for side in (-1, 1):
        for k in ks:
            h = horn(side, k)
            out[(side, k)] = (tuple(h["last"]), tuple(h["tip_tangent"]))
    return out


SPIKE_STEPS = 10
SPIKE_T = tuple([0.035] + [HORN_T[k] + (HORN_T[k + 1] - HORN_T[k]) * f for k in range(6) for f in (1 / 3, 2 / 3)]
                + [0.90])


def spike(side, i):
    """Back spike i (14 per wing, two between each pair of horns, one below the first and one above the last): out
    from the spine and back (+Y), curled 18 degrees toward the skull. Same keys as horn() (no apex)."""
    t = SPIKE_T[i]
    p, tang, out = spine_point(1, t), spine_tangent(1, t), spine_out(1, t)
    d = (out + Y * 0.45 + tang * 0.15).normalized()
    length, r0, bend = 1.6 + 1.6 * t, 0.42, 18.0
    axis = d.cross(tang).normalized()
    pts = [mirror(q, side) for q in curved_path(p, d, length, axis, bend, SPIKE_STEPS)]
    return {"side": side, "i": i, "t": t, "base": mirror(p, side), "d": mirror(d, side), "length": length, "r0": r0,
            "axis": mirror_axis(axis, side), "bend": bend, "steps": SPIKE_STEPS, "pts": pts}


def spikes(side):
    return [spike(side, i) for i in range(len(SPIKE_T))]


BULB_PHI = 55.0                # the bulb string runs along the crowd-facing inner side of the spine (0 = inward)
BULB_R, BULB_GAP = 0.16, 0.08  # bulb radius; gap between the bone's surface and the bulb


def bulbs(side):
    """Centers of the bulb string (every second ring from 2 to 68, 34 per wing), just off the bone's surface on its
    crowd-facing inner side, so from the crowd they trace the screen's edge."""
    phi = math.radians(BULB_PHI)
    out = []
    for i in range(2, RINGS, 2):
        t = i / RINGS
        p, inward = spine_point(1, t), -spine_out(1, t)
        e = inward * math.cos(phi) - Y * math.sin(phi)
        r = spine_radius(t) * (1 + bump(t) * bump_weight(phi))
        out.append(mirror(p + e * (r + BULB_GAP + BULB_R), side))
    return out


# ------------------------------------------------------------------ the arch-shaped visual screen
SCREEN_Y = PLANE_Y             # the screen stands in the arch plane
SCREEN_CLEAR = 0.015           # its edge runs this far inside the bone's innermost vertex line (a sliver at most
                               # this wide can show past the bone's faceted back half from far off: sub-pixel)
SCREEN_BOTTOM = 0.03           # its bottom edge, just over the deck top (z = 0)
VIDEO_ASPECT = 16 / 9


def screen_outline():
    """The screen's outline in the plane y = SCREEN_Y as (x, z) pairs, counter-clockwise as seen from the crowd (-Y),
    starting at the bottom right corner: up the right wing's inner edge, across along the lintel's (level from
    LINTEL_X0 to -LINTEL_X0), down the left wing's, back along the bottom; SCREEN_CLEAR inside the bone throughout.
    The lintel's inner edge runs under the spine's from x LINTEL_X1 inward, so it takes over there."""
    right = []
    for i, q in enumerate(inner_edge(1)):
        inward = -spine_out(1, i / RINGS)
        right.append((q.x + inward.x * SCREEN_CLEAR, q.z + inward.z * SCREEN_CLEAR))
    k = next(i for i, (x, z) in enumerate(right) if z >= SCREEN_BOTTOM)     # cut at the bottom edge
    (x0, z0), (x1, z1) = right[k - 1], right[k]
    corner = (x0 + (x1 - x0) * (SCREEN_BOTTOM - z0) / (z1 - z0), SCREEN_BOTTOM)
    right = [corner] + [q for q in right[k:] if q[0] > LINTEL_X1]
    for x, ring in zip(LINTEL_XS, lintel_rings()):
        if x < LINTEL_X0 - 1e-9:                                         # level from X0 on: the left half's first
            break                                                        # point closes the top edge
        right.append((ring[0].x, ring[0].z - SCREEN_CLEAR))             # its rings stand upright: inward = -Z
    left = [(-x, z) for x, z in reversed(right)]
    return right + left


def video_box(outline=None):
    """(x0, z0, w, h): the smallest 16:9 box enclosing the outline, centered on the outline's bounding box."""
    outline = outline or screen_outline()
    xs, zs = [p[0] for p in outline], [p[1] for p in outline]
    bw, bh = max(xs) - min(xs), max(zs) - min(zs)
    w, h = (bw, bw / VIDEO_ASPECT) if bw / bh >= VIDEO_ASPECT else (bh * VIDEO_ASPECT, bh)
    cx, cz = (max(xs) + min(xs)) / 2, (max(zs) + min(zs)) / 2
    return cx - w / 2, cz - h / 2, w, h


def screen_uv(x, z, box=None):
    """Tribe's back-wall UV layout on the video box (see dino_stage.build_visual_screen): U = 0 at the box's +x edge
    (the viewer's right) to 1 at its -x edge; Blender V = 0 at the box bottom to 0.5 at its top (the FBX import flips
    V, and Tribe's M_VideoBackdrop samples the video at (1 - U, 2 V - 1) in UE terms, so the frame lands upright,
    unmirrored)."""
    x0, z0, w, h = box or video_box()
    return (x0 + w - x) / w, 0.5 * (z - z0) / h
