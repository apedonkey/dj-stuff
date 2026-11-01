"""Helpers for the REACTOR core-group loops (Cherenkov Pool, Control Rods, Chain Reaction, Meltdown), on top of vjkit.
Blender's Python; import vjkit first (it owns the clock and the CLI).

  accent_ages / accent_signals / accent_wave   the accent light wave: the current AND the previous accent are summed,
                                               so a wave still running out when the next accent lands never cuts off
  hit_env                                      fast-attack, slow-decay event envelope (no one-frame spikes)
  xz / circle2 / arc2 / stroke / text_strokes  2D strokes laid in the XZ plane (neon line work, monoline letters)
  uv_prism                                     an axis-aligned box whose every face carries UVs 0..1
  attr / hazard / caustics / edge_lines        shader pieces (mesh attributes, hazard stripes and chevrons, caustics)
  obj_light_mat / particle_keys                per-object light (Object.color RGB x alpha) and keyed particles
"""
import math

import bmesh
from mathutils import Matrix, Vector

import letters
import vjkit as vj

N_ACC = vj.BEATS // vj.ACC                                        # accents per loop: 16 at half-time, 8 bars


# ------------------------------------------------------------------ music
def acc_frame(k):
    """Frame of accent k (any integer, not wrapped: accent N_ACC is frame FRAMES)."""
    return vj.beat_frame(k * vj.ACC)


def accent_ages(f):
    """(current accent index, frames since it, frames since the previous accent) at frame f (periodic)."""
    ff = f % vj.FRAMES
    k = vj.clock(ff)["acc"]
    return k, ff - acc_frame(k), ff - acc_frame(k - 1)


def cyc(t):
    """A frame offset wrapped to [-FRAMES/2, FRAMES/2): the signed distance to an event on a looping timeline."""
    return (t + vj.FRAMES // 2) % vj.FRAMES - vj.FRAMES // 2


def hit_env(t, decay=8.0):
    """Envelope t frames after a hit (0 before it): about 0.84 on the hit frame, so the light lands on the beat, then
    an exponential decay; the frames after a hit keep most of it (no one-frame spike). Matches accent_wave's shader."""
    if t <= -1.5:
        return 0.0
    x = min((t + 1.5) / 2.0, 1.0)
    return x * x * (3 - 2 * x) * math.exp(-max(t, 0.0) / decay)


def accent_signals(f, amp_fn):
    """Clock values for accent_wave: Age0 / Amp0 / Reach0 of the current accent, Age1 / Amp1 / Reach1 of the previous
    one. amp_fn(k) -> (amplitude, reach in m) of accent k (0..N_ACC-1)."""
    k, a0, a1 = accent_ages(f)
    (m0, r0), (m1, r1) = amp_fn(k), amp_fn((k - 1) % N_ACC)
    return {"Age0": float(a0), "Amp0": m0, "Reach0": r0, "Age1": float(a1), "Amp1": m1, "Reach1": r1}


def accent_wave(s, r, speed, decay=8.0):
    """Shader socket: the accent swell at distance r (m) from its source: for the current and the previous accent,
    amp * exp(-r / reach) * hit_env(age - r / speed). speed in m per frame."""
    out = None
    for age, amp, reach in (("Age0", "Amp0", "Reach0"), ("Age1", "Amp1", "Reach1")):
        t = s.sub(s.c(age), s.mul(r, 1.0 / speed))
        gate = s.smooth(t, -1.5, 0.5)
        dec = s.exp(s.mul(s.math("MAXIMUM", t, 0.0), -1.0 / decay))
        reach = s.exp(s.math("DIVIDE", s.mul(r, -1.0), s.c(reach)))
        term = s.mul(s.c(amp), gate, dec, reach)
        out = term if out is None else s.add(out, term)
    return out


def ramp_between(f, f0, f1, shape=None):
    """0 before frame f0, 1 after f1, eased in between (shape: a function of 0..1, default smoothstep)."""
    if f <= f0:
        return 0.0
    if f >= f1:
        return 1.0
    x = (f - f0) / (f1 - f0)
    return shape(x) if shape else x * x * (3 - 2 * x)


# ------------------------------------------------------------------ 2D strokes in the XZ plane
def xz(pts, y=0.0, scale=1.0, offset=(0.0, 0.0)):
    """2D (x, y) points -> Vectors in the XZ plane at depth y (a camera on -Y looking +Y sees x right, y up)."""
    return [Vector((offset[0] + p[0] * scale, y, offset[1] + p[1] * scale)) for p in pts]


def circle2(r, n=64, cx=0.0, cy=0.0, a0=0.0):
    return [(cx + r * math.cos(a0 + 2 * math.pi * i / n), cy + r * math.sin(a0 + 2 * math.pi * i / n))
            for i in range(n)]


def arc2(r, a0, a1, n=24, cx=0.0, cy=0.0):
    """Points on a circle arc from a0 to a1 degrees (counter-clockwise positive), both ends included."""
    return [(cx + r * math.cos(math.radians(a0 + (a1 - a0) * i / n)),
             cy + r * math.sin(math.radians(a0 + (a1 - a0) * i / n))) for i in range(n + 1)]


def stroke(bm, pts, r, segs=6, closed=False, caps=True):
    """A neon tube of radius r along pts (Vectors)."""
    if len(pts) >= 2:
        vj.tube(bm, pts, lambda u: r, segs=segs, closed=closed, cap0=caps, cap1=caps)


def text_strokes(bm, text, height, y=0.0, offset=(0.0, 0.0), r=0.03, track=0.22, align="center"):
    """Monoline letters (letters.py) as tubes in the XZ plane; offset = where the line's anchor lands."""
    for _, strokes in letters.layout(text, height, track=track, align=align):
        for st in strokes:
            stroke(bm, xz(st, y, 1.0, offset), r, segs=5)


# ------------------------------------------------------------------ meshes
def uv_prism(bm, uvl, x0, x1, y0, y1, z0, z1, top=True, bottom=False):
    """An axis-aligned box; every face gets UVs 0..1 (top and bottom: u along x, v along y; sides: u across the face,
    v up)."""
    c = [Vector(p) for p in ((x0, y0, z0), (x1, y0, z0), (x1, y1, z0), (x0, y1, z0),
                             (x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1))]
    quads = [(0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)]
    if top:
        quads.append((4, 5, 6, 7))
    if bottom:
        quads.append((3, 2, 1, 0))
    for q in quads:
        face = bm.faces.new([bm.verts.new(c[i]) for i in q])
        for lp, uv in zip(face.loops, ((0, 0), (1, 0), (1, 1), (0, 1))):
            lp[uvl].uv = uv
    return bm


def ico_mesh(name, subdiv=1, radius=1.0):
    bm = bmesh.new()
    bmesh.ops.create_icosphere(bm, subdivisions=subdiv, radius=radius)
    return vj.finish_bm(bm, smooth=True, name=name)


# ------------------------------------------------------------------ shader pieces
def attr(s, name):
    """A mesh attribute (e.g. a per-face float written through a bmesh layer) as a shader socket."""
    return s.node("ShaderNodeAttribute", attribute_type="GEOMETRY", attribute_name=name).outputs["Fac"]


def true_nz(s):
    """World-space Z of the true (flat) normal."""
    return s.xyz(s.node("ShaderNodeNewGeometry").outputs["True Normal"])[2]


def hazard(s, u, v, period=0.25, slope=1.0, chevron=False, duty=0.5, soft=0.05):
    """1 on the amber stripes, 0 on the dark ones: diagonal stripes along u + v, or chevrons (v + |u|), with soft
    (anti-aliased) edges."""
    a = s.add(v, s.mul(s.math("ABSOLUTE", u) if chevron else u, slope))
    t = s.math("FRACT", s.mul(a, 1.0 / period))
    return s.mul(s.smooth(t, 0.0, soft), s.inv(s.smooth(t, duty, duty + soft)))


def edge_lines(s, u, v, width=0.06, soft=0.05):
    """1 along the borders of a face's 0..1 UV square (its outline), 0 inside."""
    e = s.math("MINIMUM", s.math("MINIMUM", u, s.inv(u)), s.math("MINIMUM", v, s.inv(v)))
    return s.inv(s.smooth(e, width, width + soft))


def caustics(s, x, y, scale=0.5, speed=0.35, width=0.04, warp=1.1, seed=0.0, octave=True):
    """Pool caustics: thin bright lines (exp falloff from the edges of domain-warped 4D Voronoi cells) plus a finer,
    dimmer octave, patchy in strength, morphing on a circle in (z, w) once per loop (seamless). x, y in metres;
    scale = cells per metre (about); width = the lines' falloff in cell units."""
    cz, cw = s.mul(s.c("LoopCos"), speed), s.mul(s.c("LoopSin"), speed)
    n = s.noise4(s.vec(s.mul(x, scale * 0.45), s.mul(y, scale * 0.45), s.add(cz, seed)), cw, scale=1.0, detail=2.0)
    w = s.mul(s.sub(n, 0.5), warp)

    def layer(sc, sd):
        vor = s.node("ShaderNodeTexVoronoi", voronoi_dimensions="4D", feature="DISTANCE_TO_EDGE")
        s.put(vor.inputs["Vector"], s.vec(s.madd(x, sc, w), s.madd(y, sc, w), s.add(s.mul(cz, 1.6), sd)))
        s.put(vor.inputs["W"], s.mul(cw, 1.6))
        vor.inputs["Scale"].default_value = 1.0
        return s.exp(s.mul(vor.outputs["Distance"], -1.0 / width))

    c = layer(scale, seed)
    if octave:
        c = s.add(s.mul(c, 0.7), s.mul(layer(scale * 1.9, seed + 5.0), 0.3))
    return s.mul(c, s.madd(s.smooth(n, 0.35, 0.65), 0.6, 0.4))


# ------------------------------------------------------------------ per-object light, particles
def obj_light_mat(name, gain, additive=False, soft=0.0, lift=None):
    """Per-object light: colour = Object.color RGB, strength = Object.color alpha x gain (x lift socket builder).
    soft > 0 darkens the silhouette edge (a glowing ball rather than a flat disc)."""
    s = vj.Shader(name)
    col, alpha, _ = s.obj_info()
    st = s.mul(alpha, gain)
    if soft > 0:
        st = s.mul(st, s.math("POWER", s.inv(s.facing()), soft))
    if lift is not None:
        st = s.mul(st, lift(s))
    return s.additive(col, st) if additive else s.emit(col, st)


def particle_keys(ob, frames, state):
    """state(f) -> (location, size, (r, g, b, a)): keys location, uniform scale and Object.color of ob. A particle that
    is dead has size ~0 at both ends of its jump, so neither the jump nor motion blur shows."""
    loc, scl, col = [], [], []
    for f in frames:
        p, sz, c = state(f)
        loc.append((f, tuple(p)))
        scl.append((f, (sz, sz, sz)))
        col.append((f, tuple(c)))
    vj.keyed(ob, "location", loc)
    vj.keyed(ob, "scale", scl)
    vj.keyed(ob, "color", col)


def poisson(rng, n, lo, hi, min_d, tries=40):
    """Up to n points in the box lo..hi (Vectors) with no two closer than min_d (dart throwing)."""
    pts = []
    for _ in range(n * tries):
        if len(pts) >= n:
            break
        p = Vector([rng.uniform(a, b) for a, b in zip(lo, hi)])
        if all((p - q).length >= min_d for q in pts):
            pts.append(p)
    return pts


def rot_z(deg):
    return Matrix.Rotation(math.radians(deg), 4, "Z")
