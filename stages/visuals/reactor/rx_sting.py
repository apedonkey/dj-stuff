"""Helpers for the REACTOR sting and Cold Start (Blender's Python; builds on vjkit, which is not edited from here).

  stroke_tube(bm, pts, r, ...)   a monoline neon tube with round caps and joints whose vertices know where they sit
                                 along the stroke: mesh attributes 'u' (0 at the start cap's back .. 1 at the end
                                 cap's tip, linear in arc length) and 'slen' (the stroke's length incl. caps, m), so a
                                 shader can draw it on, erase it and run a hot head along it
  word_strokes(text, ...)        letters.py strokes laid in the XZ plane (a camera on -Y sees x right, z up)
  fly_in(p)                      accelerate, cruise, brake to rest at 1 (the Dino sting's lock)
  project(cam, lens, p)          frame pixel of a world point for a camera pose (timing events to the screen)
  drift_noise(s, x, z, ...)      wisps drifting a fixed distance per loop, seamless (Giant Halo's crossfade)
"""
import math

import bmesh
from mathutils import Matrix, Vector

import letters
import vjkit as vj


def resample(pts, step):
    """Densify a polyline (Vectors) so no segment is longer than `step`."""
    out = [pts[0].copy()]
    for a, b in zip(pts, pts[1:]):
        n = max(1, int(math.ceil((b - a).length / step)))
        out += [a.lerp(b, i / n) for i in range(1, n + 1)]
    return out


def stroke_layers(bm):
    """The bmesh float layers 'u' and 'slen' (created once per bmesh)."""
    lu = bm.verts.layers.float.get("u") or bm.verts.layers.float.new("u")
    ll = bm.verts.layers.float.get("slen") or bm.verts.layers.float.new("slen")
    return lu, ll


def stroke_tube(bm, pts, r, segs=10, corner_deg=25.0):
    """A neon tube of radius r along pts (Vectors) with sphere caps at both ends and spheres at sharp corners. Every
    vertex gets u in [0, 1] (arc length from the start cap's back, over the whole length incl. both caps) and slen."""
    lu, ll = stroke_layers(bm)
    dense = resample(pts, r * 1.5)
    s = [0.0]
    for a, b in zip(dense, dense[1:]):
        s.append(s[-1] + (b - a).length)
    total = s[-1] + 2 * r

    def u_of(arc):
        return min(1.0, max(0.0, (arc + r) / total))

    bm.verts.ensure_lookup_table()
    n0 = len(bm.verts)
    vj.tube(bm, dense, lambda u: r, segs=segs, cap0=False, cap1=False)
    bm.verts.ensure_lookup_table()
    for i in range(len(dense)):
        for j in range(segs):
            v = bm.verts[n0 + i * segs + j]
            v[lu], v[ll] = u_of(s[i]), total

    def sphere(center, rad, arc_of):
        res = bmesh.ops.create_icosphere(bm, subdivisions=2, radius=rad, matrix=Matrix.Translation(center))
        for v in res["verts"]:
            v[lu], v[ll] = u_of(arc_of(v.co)), total

    t0 = (dense[1] - dense[0]).normalized()
    t1 = (dense[-1] - dense[-2]).normalized()
    sphere(dense[0], r, lambda co: (co - dense[0]).dot(t0))
    sphere(dense[-1], r, lambda co: s[-1] + (co - dense[-1]).dot(t1))
    for i in range(1, len(dense) - 1):                       # sharp corners (the A's apex): a joint sphere
        a, b, c = dense[i - 1], dense[i], dense[i + 1]
        if (b - a).length > 1e-6 and (c - b).length > 1e-6 and (b - a).angle(c - b) > math.radians(corner_deg):
            si = s[i]
            sphere(b, r * 1.01, lambda co, si=si: si)
    return total


def word_strokes(text, height, z_mid=0.0, track=0.22, y=0.0):
    """[(char, [stroke as Vectors in the XZ plane])] of a centered line of text whose letters span z_mid +- height/2."""
    out = []
    for ch, strokes in letters.layout(text, height, track=track):
        out.append((ch, [[Vector((px, y, pz + z_mid - height / 2)) for px, pz in st] for st in strokes]))
    return out


def fly_in(p, pa=0.5, pb=0.9):
    """0..1: accelerate until pa, full speed until pb, brake to rest at 1 (the seam step is never the biggest)."""
    p = min(max(p, 0.0), 1.0)
    vm = 2.0 / (1.0 + pb - pa)
    if p <= pa:
        return vm * p * p / (2 * pa)
    if p <= pb:
        return vm * (pa / 2 + p - pa)
    q = p - pb
    return vm * (pa / 2 + pb - pa + q - q * q / (2 * (1.0 - pb)))


def smoother(x):
    """Smootherstep: zero velocity and acceleration at both ends."""
    x = min(max(x, 0.0), 1.0)
    return x * x * x * (x * (6 * x - 15) + 10)


def project(cam_loc, cam_rot, lens, p, sensor=36.0, w=1920, h=1080):
    """(x, y) frame pixels (y down) of world point p for a camera at cam_loc with rotation cam_rot (Euler), or None
    behind the camera."""
    d = cam_rot.to_matrix().transposed() @ (Vector(p) - Vector(cam_loc))
    if d.z >= -1e-6:
        return None
    f = lens / sensor * w
    return w / 2 + f * d.x / -d.z, h / 2 - f * d.y / -d.z


def drift_noise(s, x, z, scale, drift, seed, detail=4.0, rough=0.6):
    """0..1 noise (centered on 0.5) in plane meters (x, z) drifting `drift` (dx, dz) m per loop, made seamless as a
    variance-preserving crossfade of two copies one drift apart (Giant Halo's smoke). Needs the clock signals LoopT,
    W1 = cos(pi t / 2) and W2 = sin(pi t / 2)."""
    dx, dz = drift

    def at(t):
        return s.vec(s.mul(s.sub(x, s.mul(t, dx)), scale), s.mul(s.sub(z, s.mul(t, dz)), scale), seed)
    n1 = s.noise4(at(s.c("LoopT")), seed * 0.37, scale=1.0, detail=detail, rough=rough)
    n2 = s.noise4(at(s.sub(s.c("LoopT"), 1.0)), seed * 0.37, scale=1.0, detail=detail, rough=rough)
    return s.add(s.mul(s.sub(n1, 0.5), s.c("W1")), s.mul(s.sub(n2, 0.5), s.c("W2")), 0.5)


def drift_signals(f):
    """The clock signals drift_noise needs."""
    t = (f % vj.FRAMES) / vj.FRAMES
    return {"LoopT": t, "W1": math.cos(0.5 * math.pi * t), "W2": math.sin(0.5 * math.pi * t)}


def soft_glow_mat(name, color, gain, power=3.0, lift_key=None, lift_amt=0.0):
    """An additive glow ball (a sphere seen as a soft disc): (1 - facing)^power, no hard rim. Optional lift from a
    clock signal."""
    s = vj.Shader(name)
    k = s.math("POWER", s.inv(s.facing()), power)
    st = s.mul(k, gain)
    if lift_key:
        st = s.mul(st, s.madd(s.c(lift_key), lift_amt, 1.0))
    mat = s.additive(color, st)
    mat.use_backface_culling = True
    return mat
