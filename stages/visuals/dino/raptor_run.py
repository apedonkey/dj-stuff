"""RAPTOR RUN - Dino Stage VJ loop (build). 8 bars, seamless, 1920x1080 @ 30 fps; tempo from vjkit (140 BPM half-time =
411 frames by default; the 128 cut was straight, 450 frames).

A pack of raptor silhouettes, outlined in neon by a rim light, sprints along a glowing horizon over a scrolling
laser-grid floor while the camera tracks them. Every raptor runs one full stride per beat: the near foot plants on the
beat, the far foot on the offbeat, and the IK legs keep planted feet still on the ground. The rims, grid, sky and lasers
lift on the accents (half-time: the kick and the snare). Palm silhouettes scroll past at mid distance and laser fans
sweep up from the horizon behind the pack.
  Bars 1-4: two fans sweep slowly.
  Bar 5: the lead raptor leaps (jaws open), the pack scatters and four fans burst open; bars 6-8 the pack regroups.
  The last two beats of bars 4 and 8 swell into the next downbeat (horizon, lasers and rims ramp up, peak on the hit).
Variants (--variant): green (default), magenta (palette swap), stampede (bigger pack, low front-quarter camera).
No strobing: <= 3 flashes/s, no one-frame hits, no ~1 m2 patch over 0.65 luma, kick pulse <= ~1.6x.
Geometry and look are our own (vjkit tube/horn generators from the stage script).

  blender.exe -b --factory-startup --python raptor_run.py -- --variant green --frames 0,14,225 [--pct 25 --samples 4]
  blender.exe -b --factory-startup --python raptor_run.py -- --variant green --all --seam DIR [--out DIR] [--mblur]
  blender.exe -b --factory-startup --python raptor_run.py -- --variant green --bounds     (screen bounds, no render)
"""
import math
import os
import random
import sys

import bmesh
import bpy
from mathutils import Matrix, Vector

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import vjkit as vj  # noqa: E402
from vjkit import AMBER, CYAN, GREEN, MAGENTA, RED, UV  # noqa: E402

GAIN = float(vj.arg("--gain", 1.0))

TRAVEL = 180.0                            # m per loop: a 5.6 m stride per beat (12 m/s at 128 BPM)
V = TRAVEL / vj.FRAMES                    # ground speed (m per frame)
GRID = 3.0                                # floor grid spacing: TRAVEL / GRID = 60 cells, so the floor matches at the seam
SKY_DIST = 880.0                          # sky card distance in the far rig (which follows the camera)
EXT = list(range(-2, vj.FRAMES + 3))      # transform keys run past both ends for motion blur at the seam

# raptor anatomy at scale 1 (m): hip height, leg segments, stance share of the stride, swing foot lift
HIP_Z, HIP_Y = 1.15, 0.13
L_THIGH, L_SHIN, L_META, L_TOE = 0.66, 0.74, 0.5, 0.32
DUTY, LIFT, BOB = 0.36, 0.4, 0.05
TUCK = (-20.0, -150.0, -70.0, -105.0)     # leap pose: thigh, shin, metatarsus, toe angles (deg from +X, in XZ)

VARIANTS = {                              # palette, camera and pack layout per variant
    "green": dict(rim=GREEN, eye=RED, line=AMBER, glow=MAGENTA, glow_hi=UV, grid=(UV, MAGENTA),
                  lasers=(CYAN, MAGENTA), laser_gain=(0.65, 1.0), cam="side"),
    "magenta": dict(rim=MAGENTA, eye=GREEN, line=CYAN, glow=UV, glow_hi=(0.06, 0.0, 1.0), grid=(UV, CYAN),
                    lasers=(GREEN, AMBER), laser_gain=(0.55, 0.9), cam="side"),
    "stampede": dict(rim=AMBER, eye=CYAN, line=MAGENTA, glow=(1.0, 0.03, 0.12), glow_hi=UV, grid=(MAGENTA, UV),
                     lasers=(CYAN, GREEN), laser_gain=(0.65, 0.55), cam="front"),
}
VARIANT, PAL = vj.variant(VARIANTS)
NAME = f"raptor_run_{VARIANT}"

# camera in pack space (x along the run, relative to the pack's travel): position, yaw (deg; 0 looks along +Y)
CAMS = {
    "side": dict(pos=(0.0, -13.0, 1.0), yaw=0.0, lens=32.0, shift_y=0.06),
    "front": dict(pos=(15.5, -9.5, 0.8), yaw=61.0, lens=26.0, shift_y=0.05),
}
CAM = CAMS[PAL["cam"]]

# pack layout: (lane y, hip x, scale, gait phase (beats), scatter dx, scatter dy, drift phase); row 0 leads and leaps
LAYOUTS = {
    "side": [(-1.2, 2.8, 1.08, 0.00, 0.8, 0.0, 0.0),
             (4.0, -3.4, 1.00, 0.03, 2.2, -2.0, 1.3),
             (-3.6, -1.45, 0.92, 0.06, -1.2, 2.4, 2.1),
             (9.0, 6.0, 0.95, 0.02, -3.0, 1.5, 3.7),
             (13.0, -8.5, 1.00, 0.05, 3.0, -3.0, 5.0)],
    "front": [(-2.0, 4.5, 1.08, 0.00, 1.2, 0.0, 0.0),
              (1.5, 1.5, 1.00, 0.03, 1.5, -1.5, 1.3),
              (-4.5, 0.5, 0.95, 0.06, -1.5, 2.0, 2.1),
              (4.5, 3.0, 0.97, 0.02, -2.0, 1.0, 3.7),
              (0.0, -2.5, 1.02, 0.05, 2.0, -2.0, 5.0),
              (7.5, -0.5, 0.93, 0.04, -1.0, 1.5, 0.7),
              (-6.5, -4.0, 0.98, 0.01, 1.5, 2.5, 2.9),
              (3.5, -6.0, 1.00, 0.07, -2.0, -1.0, 4.4),
              (9.5, -5.0, 0.95, 0.03, 1.0, -1.5, 5.8)],
}
LAYOUT = LAYOUTS[PAL["cam"]]


# ------------------------------------------------------------------ music helpers
SECTION_B = 16                            # first beat of bars 5-8
MORPH = 8


def beatpos_abs(f):
    """Continuous beat count at frame f (any real; +32 per loop), linear between the quantized beat frames."""
    n, r = divmod(f, vj.FRAMES)
    k = max(i for i in range(vj.BEATS) if vj.BEAT_F[i] <= r)
    return vj.BEATS * n + k + (r - vj.BEAT_F[k]) / (vj.BEAT_F[k + 1] - vj.BEAT_F[k])


def frame_at(bp):
    """Inverse of beatpos_abs."""
    n, r = divmod(bp, vj.BEATS)
    k = int(r)
    return vj.FRAMES * n + vj.BEAT_F[k] + (r - k) * (vj.BEAT_F[k + 1] - vj.BEAT_F[k])


def since_hit(f):
    f %= vj.FRAMES
    return f - vj.BEAT_F[SECTION_B] if f >= vj.BEAT_F[SECTION_B] else f


def swell(f):
    """The fill: eases in over the last 2 beats of bars 4 and 8, peaks at 1 on the next downbeat, decays over ~1 beat."""
    c = vj.clock(f)
    if c["bar"] in (3, 7) and c["beat"] >= 2:
        f0, f1 = vj.BEAT_F[4 * c["bar"] + 2], vj.BEAT_F[4 * c["bar"] + 4]
        return ((c["f"] - f0) / (f1 - f0)) ** 2
    return math.exp(-since_hit(f) / vj.FPB)


def section(f):
    """0 = bars 1-4, 1 = bars 5-8; morphs over the last MORPH frames before each hit so the new look lands on it."""
    f %= vj.FRAMES
    nxt = vj.BEAT_F[SECTION_B] if f < vj.BEAT_F[SECTION_B] else vj.FRAMES
    cur = 0.0 if f < vj.BEAT_F[SECTION_B] else 1.0
    x = vj.ease((f - (nxt - MORPH)) / MORPH) if f >= nxt - MORPH else 0.0
    return cur + (1.0 - 2.0 * cur) * x


def scatter(f):
    """Pack scatter on bar 5: out over 2 beats, holds through bar 6, regroups by the end of bar 8."""
    f %= vj.FRAMES
    a, b, c, d = vj.BEAT_F[16], vj.BEAT_F[18], vj.BEAT_F[22], vj.BEAT_F[31]
    if f < a or f >= d:
        return 0.0
    if f < b:
        return vj.ease((f - a) / (b - a))
    if f < c:
        return 1.0
    return 1.0 - vj.ease((f - c) / (d - c))


LEAP0, LEAP1 = vj.BEAT_F[16], vj.BEAT_F[18]       # the lead raptor is airborne for beats 1-2 of bar 5


def leap(f):
    """Lead raptor on bar 5: (hip lift m, tuck weight, pitch deg, jaw deg). Gathers on beat 4 of bar 4."""
    f %= vj.FRAMES
    lift, w, pitch, jaw = 0.0, 0.0, 0.0, 0.0
    g0 = vj.BEAT_F[15]
    if g0 <= f < LEAP0:                                            # the gather: crouch, nose down
        x = vj.ease((f - g0) / (LEAP0 - g0))
        lift, pitch = -0.22 * x, -5.0 * x
    elif LEAP0 <= f <= LEAP1:
        u = (f - LEAP0) / (LEAP1 - LEAP0)
        lift = -0.22 * (1 - vj.ease(u / 0.15)) + 2.0 * 4 * u * (1 - u)
        w = vj.ease(u / 0.22) * (1 - vj.ease((u - 0.78) / 0.22))
        pitch = 13.0 * math.cos(math.pi * u)
        jaw = 30.0 * math.sin(math.pi * u) ** 0.6
    elif LEAP1 < f < LEAP1 + 12:                                   # landing: absorb, then level out
        u = (f - LEAP1) / 12
        lift = -0.2 * math.sin(math.pi * u)
        pitch = -13.0 * (1 - vj.ease(u))
    return lift, w, pitch, jaw


# ------------------------------------------------------------------ keying
def keyed(owner, prop, frame_values, interp="LINEAR"):
    """Key owner.prop at every (frame, value) in one pass per F-curve (fast for many keys)."""
    f0, v0 = frame_values[0]
    setattr(owner, prop, v0)
    owner.keyframe_insert(prop, frame=f0)
    path = owner.path_from_id(prop)
    for fc in vj.fcurves_of(owner.id_data):
        if fc.data_path != path:
            continue
        i = fc.array_index
        kp = fc.keyframe_points
        kp.add(len(frame_values) - 1)
        co = []
        for f, v in frame_values:
            co += [f, v[i] if isinstance(v, (tuple, list, Vector)) else v]
        kp.foreach_set("co", co)
        for p in kp:
            p.interpolation = interp
        fc.update()


# ------------------------------------------------------------------ geometry
def finish_bm(bm):
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    me = bpy.data.meshes.new("m")
    bm.to_mesh(me)
    bm.free()
    me.shade_smooth()
    return me


def mesh_obj(name, me, mat=None, parent=None):
    """Object on (possibly shared) mesh data; its material is linked to the object, so shared meshes can differ."""
    ob = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(ob)
    if mat is not None:
        if not me.materials:
            me.materials.append(mat)
        ob.material_slots[0].link = "OBJECT"
        ob.material_slots[0].material = mat
    ob.parent = parent
    return ob


def sweep(bm, pts, radii, segs=14):
    """Elliptical sections along a polyline in the XZ plane: radii[i] = (vertical, lateral). Closed ends."""
    n = len(pts)
    rings = []
    side = Vector((0, 1, 0))
    for i in range(n):
        t = (pts[min(i + 1, n - 1)] - pts[max(i - 1, 0)]).normalized()
        up = t.cross(side).normalized()
        ru, rs = radii[i]
        rings.append([bm.verts.new(pts[i] + up * (ru * math.sin(2 * math.pi * j / segs))
                                   + side * (rs * math.cos(2 * math.pi * j / segs))) for j in range(segs)])
    for i in range(n - 1):
        a, b = rings[i], rings[i + 1]
        for j in range(segs):
            bm.faces.new((a[j], a[(j + 1) % segs], b[(j + 1) % segs], b[j]))
    for ring, end in ((rings[0], pts[0]), (rings[-1], pts[-1])):
        c = bm.verts.new(end)
        for j in range(segs):
            bm.faces.new((ring[j], ring[(j + 1) % segs], c))


def spline(ctrl, per=6):
    """Catmull-Rom through (point, value...) rows; returns points and the interpolated values."""
    pts = vj.catmull([Vector(p) for p, *_ in ctrl], per=per)
    vals = []
    m = len(ctrl) - 1
    for i in range(len(pts)):
        u = min(i / per, m - 1e-9)
        k, t = int(u), u - int(u)
        vals.append(tuple(a + (b - a) * t for a, b in zip(ctrl[k][1:], ctrl[k + 1][1:])))
    return pts, vals


# body profile at scale 1, origin at the hip: (x, y, z), vertical radius, lateral radius
BODY = [((-2.55, 0, 0.32), 0.02, 0.02), ((-2.0, 0, 0.26), 0.045, 0.04), ((-1.4, 0, 0.18), 0.08, 0.07),
        ((-0.85, 0, 0.12), 0.13, 0.11), ((-0.4, 0, 0.07), 0.2, 0.16), ((0.0, 0, 0.04), 0.27, 0.2),
        ((0.4, 0, 0.0), 0.31, 0.23), ((0.8, 0, -0.02), 0.29, 0.22), ((1.1, 0, 0.06), 0.2, 0.16),
        ((1.28, 0, 0.28), 0.12, 0.1), ((1.38, 0, 0.5), 0.1, 0.085), ((1.5, 0, 0.66), 0.14, 0.1),
        ((1.75, 0, 0.7), 0.12, 0.085), ((2.0, 0, 0.66), 0.075, 0.06), ((2.12, 0, 0.63), 0.03, 0.03)]
JAW_HINGE = Vector((1.5, 0, 0.6))


def body_mesh():
    bm = bmesh.new()
    pts, vals = spline([(p, a, b) for p, a, b in BODY], per=5)
    sweep(bm, pts, vals)
    for s in (-1, 1):                                              # folded arms with two claws each
        arm = vj.catmull([Vector((0.95, 0.14 * s, -0.1)), Vector((1.0, 0.19 * s, -0.36)),
                          Vector((1.22, 0.17 * s, -0.3))], per=4)
        vj.tube(bm, arm, lambda u: 0.05 - 0.02 * u, segs=8)
        for dz in (0.0, -0.04):
            vj.horn(bm, Vector((1.22, 0.17 * s, -0.3 + dz)), Vector((0.6, 0, -0.5)), 0.13, 0.02,
                    Vector((0, 1, 0)), 70, segs=6, steps=6)
    return finish_bm(bm)


def jaw_mesh():
    bm = bmesh.new()
    pts, vals = spline([((0.0, 0, 0.0), 0.05, 0.075), ((0.2, 0, -0.03), 0.045, 0.07),
                        ((0.4, 0, -0.03), 0.03, 0.05), ((0.5, 0, -0.01), 0.015, 0.025)], per=5)
    sweep(bm, pts, vals, segs=10)
    return finish_bm(bm)


def eyes_mesh():
    bm = bmesh.new()
    for s in (-1, 1):
        bmesh.ops.create_icosphere(bm, subdivisions=2, radius=0.04, matrix=Matrix.Translation((1.69, 0.088 * s, 0.75)))
    return finish_bm(bm)


def bone_mesh(length, r0, r1, tip=False, sickle=False):
    """A leg segment along local +X from 0 to length, with a ball joint at its root."""
    bm = bmesh.new()
    pts = [Vector((length * t / 6, 0, 0)) for t in range(7)]
    vj.tube(bm, pts, lambda u: r0 + (r1 - r0) * u, segs=10, tip=tip)
    bmesh.ops.create_icosphere(bm, subdivisions=2, radius=r0 * 1.05)
    if sickle:                                                     # the raised killing claw on the second toe
        vj.horn(bm, Vector((0.05, 0, 0.02)), Vector((0.25, 0, 1.0)), 0.16, 0.03, Vector((0, 1, 0)), -110,
                segs=6, steps=8)
    return finish_bm(bm)


def frond(bm, base, sign, length, rise, droop, width, rng):
    """A palm frond as a flat serrated leaf in the XZ plane (a silhouette)."""
    ctrl = [base, base + Vector((sign * 0.3 * length, rng.uniform(-0.3, 0.3), rise * length)),
            base + Vector((sign * 0.68 * length, rng.uniform(-0.5, 0.5), (rise * 0.6 - droop * 0.2) * length)),
            base + Vector((sign * length, rng.uniform(-0.5, 0.5), -droop * length))]
    pts = vj.catmull(ctrl, per=8)
    left, right = [], []
    n = len(pts)
    for i, p in enumerate(pts):
        t = (pts[min(i + 1, n - 1)] - pts[max(i - 1, 0)]).normalized()
        nrm = Vector((-t.z, 0, t.x)).normalized()
        u = i / (n - 1)
        w = width * (1 - u) ** 0.6 * (1.7 if i % 2 else 0.55) + 0.02
        left.append(bm.verts.new(p + nrm * w * 0.5))
        right.append(bm.verts.new(p - nrm * w))
    for i in range(n - 1):
        bm.faces.new((left[i], left[i + 1], right[i + 1], right[i]))


def palm_bm(rng, height, lean):
    bm = bmesh.new()
    sx = math.sin(lean) * height
    top = Vector((sx * 0.62, 0, height))
    trunk = vj.catmull([Vector((0, 0, -1.0)), Vector((sx * 0.12, 0, height * 0.35)),
                        Vector((sx * 0.38, 0, height * 0.72)), top], per=5)
    vj.tube(bm, trunk, lambda u: 0.45 - 0.2 * u, segs=8)
    for i in range(9):
        sign = -1 if i % 2 else 1
        frond(bm, top, sign, rng.uniform(4.0, 6.2), rng.uniform(0.05, 0.45), rng.uniform(0.15, 0.75),
              rng.uniform(0.7, 1.0), rng)
    return bm


def beam_bm(length=1400.0, r0=1.0, r1=3.2, segs=8):
    bm = bmesh.new()
    vj.tube(bm, [Vector((0, -length * t, 0)) for t in (0.0, 0.5, 1.0)], lambda u: r0 + (r1 - r0) * u, segs=segs)
    return bm


# ------------------------------------------------------------------ materials
def rim_mat(name, color, gain, edge=(0.38, 0.92), kick=0.55):
    """Neon outline: black where the surface faces the camera, glowing in a band along the silhouette edges."""
    s = vj.Shader(name)
    lw = s.node("ShaderNodeLayerWeight")
    lw.inputs["Blend"].default_value = 0.5
    rim = s.smooth(lw.outputs["Facing"], *edge)
    lift = s.add(1.0, s.mul(s.c("Kick"), kick), s.mul(s.c("Swell"), 0.45))
    return s.emit(color, s.mul(rim, gain * GAIN, lift))


def flat_mat(name, color, strength, kick=0.4):
    s = vj.Shader(name)
    return s.emit(color, s.mul(strength * GAIN, s.add(1.0, s.mul(s.c("Kick"), kick))))


def black_mat(name):
    s = vj.Shader(name)
    return s.emit((0.0, 0.0, 0.0), 0.0)


def smooth_s(s, x, lo, hi):
    """smoothstep(lo, hi, x) where the bounds may be sockets too."""
    n = s.node("ShaderNodeMapRange", interpolation_type="SMOOTHSTEP")
    s.put(n.inputs["Value"], x)
    s.put(n.inputs["From Min"], lo)
    s.put(n.inputs["From Max"], hi)
    return n.outputs["Result"]


def grid_mat():
    s = vj.Shader("Grid")
    geo = s.node("ShaderNodeNewGeometry")
    x, y, _ = s.xyz(geo.outputs["Position"])

    def lines(v, spacing, half_w):
        t = s.math("FRACT", s.madd(v, 1.0 / spacing, 0.5))
        dist = s.mul(s.math("ABSOLUTE", s.math("SUBTRACT", t, 0.5)), spacing)
        return s.math("SUBTRACT", 1.0, smooth_s(s, dist, half_w, s.mul(half_w, 2.5)))

    hw = s.mul(s.dist, 0.0028)                                       # constant on-screen line width
    g = s.math("MAXIMUM", lines(x, GRID, hw), lines(y, GRID, hw))
    fade = s.falloff(s.dist, 48.0)
    lift = s.add(0.6, s.mul(s.c("Kick"), 0.5), s.mul(s.c("Swell"), 0.4))
    a, b = PAL["grid"]
    return s.emit(s.mix(s.c("Section"), a, b), s.mul(g, fade, lift, 1.6 * GAIN))


def emit_layers(s, layers):
    """Sum of emission shaders [(color, strength)] into the material output."""
    acc = None
    for col, strength in layers:
        e = s.node("ShaderNodeEmission")
        s.put(e.inputs["Color"], col)
        s.put(e.inputs["Strength"], strength)
        if acc is None:
            acc = e.outputs[0]
        else:
            a = s.node("ShaderNodeAddShader")
            s.nt.links.new(acc, a.inputs[0])
            s.nt.links.new(e.outputs[0], a.inputs[1])
            acc = a.outputs[0]
    s.nt.links.new(acc, s.out.inputs["Surface"])
    return s.mat


def sky_mat():
    """The glowing horizon: a hot line on the horizon, a glow band above it and a few dim stars in the black."""
    s = vj.Shader("Sky")
    tc = s.node("ShaderNodeTexCoord")
    x, _, z = s.xyz(tc.outputs["Object"])
    zp = s.math("MAXIMUM", z, 0.0)
    lift = s.add(1.0, s.mul(s.c("Kick"), 0.32), s.mul(s.c("Swell"), 0.55))
    glow_col = s.mix(s.smooth(zp, 0.0, 120.0), PAL["glow"], PAL["glow_hi"])
    glow = s.mul(s.add(s.mul(s.falloff(zp, 48.0), 0.55), s.mul(s.falloff(zp, 170.0), 0.08)), lift, GAIN)
    line = s.mul(s.gauss(z, 0.6, 1.4), lift, 2.2 * GAIN)
    vor = s.node("ShaderNodeTexVoronoi", feature="F1")
    s.put(vor.inputs["Vector"], s.vec(s.mul(x, 0.05), s.mul(z, 0.05), 0.0))
    vor.inputs["Scale"].default_value = 1.0
    dot = s.math("SUBTRACT", 1.0, s.smooth(vor.outputs["Distance"], 0.04, 0.09))
    star = s.mul(dot, s.smooth(vor.outputs["Color"], 0.72, 0.8), s.smooth(zp, 80.0, 180.0), 0.4 * GAIN)
    return emit_layers(s, [(glow_col, glow), (PAL["line"], line), ((0.75, 0.8, 1.0), star)])


def beam_mat(name, gain):
    """Per-object light (lasers): color = object color RGB, intensity = object color alpha; additive."""
    s = vj.Shader(name)
    oi = s.node("ShaderNodeObjectInfo")
    tc = s.node("ShaderNodeTexCoord")
    _, y, _ = s.xyz(tc.outputs["Object"])
    ay = s.math("ABSOLUTE", y)
    fade = s.mul(s.falloff(ay, 700.0), s.smooth(ay, 0.0, 160.0))  # fades in from the source, dims up into the sky
    return s.additive(oi.outputs["Color"], s.mul(oi.outputs["Alpha"], gain * GAIN, fade))


# ------------------------------------------------------------------ the pack
class Raptor:
    def __init__(self, idx, row):
        self.idx = idx
        self.lane, self.x0, self.sc, self.phase, self.sdx, self.sdy, self.drift = row
        self.lead = idx == 0

    def x(self, f):
        """World x of the hip (any real frame; x(f + FRAMES) = x(f) + TRAVEL)."""
        return (V * f + self.x0 + 0.35 * math.sin(2 * math.pi * f / vj.FRAMES + self.drift)
                + self.sdx * scatter(f))

    def y(self, f):
        return self.lane + 0.3 * math.sin(4 * math.pi * f / vj.FRAMES + 1.7 * self.drift) + self.sdy * scatter(f)

    def leap(self, f):
        return leap(f) if self.lead else (0.0, 0.0, 0.0, 0.0)

    def hip_z(self, f):
        ph = (beatpos_abs(f) + self.phase) % 1.0
        bob = -BOB * math.cos(4 * math.pi * (ph - DUTY / 2))       # lowest at mid-stance of either foot
        return self.sc * (HIP_Z + bob) + self.leap(f)[0]

    def foot(self, f, side):
        """Ball of the foot relative to the hip (dx, z) in the raptor's frame, metatarsus tilt, toe curl (deg)."""
        off = self.phase + 0.5 * side
        bp = beatpos_abs(f) + off
        stride = math.floor(bp)
        u = bp - stride                                            # 0 = touchdown

        def plant(s):                                              # the foot sits under the hip at mid-stance
            return self.x(frame_at(s + DUTY / 2 - off))

        hx = self.x(f)
        if u < DUTY:
            v = u / DUTY
            return (plant(stride) - hx, 0.0), 30.0 - 55.0 * v, 0.0
        v = (u - DUTY) / (1 - DUTY)
        x0, x1 = plant(stride), plant(stride + 1)
        bx = x0 + (x1 - x0) * vj.ease(v)
        bz = LIFT * self.sc * math.sin(math.pi * v ** 0.8)
        if v < 0.6:                                                # the foot folds back, then reaches forward
            theta = -25.0 - 20.0 * math.sin(math.pi * v / 0.6)
        else:
            theta = -25.0 + 55.0 * vj.ease((v - 0.6) / 0.4)
        return (bx - hx, bz), theta, 75.0 * math.sin(math.pi * v) ** 0.7

    def leg_angles(self, f, side):
        """Joint angles (deg, in the XZ plane) of thigh, shin, metatarsus and toe, from IK on the gait targets."""
        sc = self.sc
        lt, ls, lm = L_THIGH * sc, L_SHIN * sc, L_META * sc
        hz = self.hip_z(f)
        (bx, bz), theta, toe = self.foot(f, side)
        th = math.radians(theta)
        ax, az = bx - lm * math.sin(th), bz + lm * math.cos(th)    # ankle: behind the ball when theta > 0
        dx, dz = ax, az - hz
        d = min(max(math.hypot(dx, dz), abs(lt - ls) + 1e-3), lt + ls - 1e-3)
        base = math.atan2(dz, dx)
        a = math.acos((lt * lt + d * d - ls * ls) / (2 * lt * d))
        a1 = min(base + a, math.radians(-25.0))                   # knee forward, never up through the back
        kx, kz = lt * math.cos(a1), hz + lt * math.sin(a1)
        a2 = math.atan2(az - kz, ax - kx)
        a3 = math.atan2(bz - az, bx - ax)
        a4 = -math.radians(toe)
        ang = [math.degrees(v) for v in (a1, a2, a3, a4)]
        ang = [a - 360.0 if a > 90.0 else a for a in ang]          # keep in (-270, 90]: no wrap between frames
        w = self.leap(f)[1]
        return [p + (q - p) * w for p, q in zip(ang, TUCK)]

    def build(self, mats, meshes):
        self.root = vj.new_empty(f"Raptor{self.idx}")
        self.body = mesh_obj(f"R{self.idx}Body", meshes["body"], mats["rim"], self.root)
        self.jaw = mesh_obj(f"R{self.idx}Jaw", meshes["jaw"], mats["rim"], self.body)
        self.jaw.location = JAW_HINGE
        self.eyes = mesh_obj(f"R{self.idx}Eyes", meshes["eyes"], mats["eye"], self.body)
        self.segs = {}
        for side in (0, 1):
            for j, key in enumerate(("thigh", "shin", "meta", "toe")):
                ob = mesh_obj(f"R{self.idx}{key}{side}", meshes[key], mats["rim"], self.root)
                ob.scale = (self.sc, self.sc, self.sc)
                self.segs[side, j] = ob
        self.body.scale = (self.sc, self.sc, self.sc)
        self.parts = [self.body, self.jaw] + list(self.segs.values())

    def animate(self):
        sc = self.sc
        root_loc, root_rot, body_loc, body_rot, jaw_rot = [], [], [], [], []
        seg_loc = {k: [] for k in self.segs}
        seg_rot = {k: [] for k in self.segs}
        for f in EXT:
            x, y = self.x(f), self.y(f)
            vx, vy = self.x(f + 0.5) - self.x(f - 0.5), self.y(f + 0.5) - self.y(f - 0.5)
            root_loc.append((f, (x, y, 0.0)))
            root_rot.append((f, (0.0, 0.0, math.atan2(vy, vx))))
            hz = self.hip_z(f)
            lift, w, lp, jaw = self.leap(f)
            ph = (beatpos_abs(f) + self.phase) % 1.0
            pitch = lp + 1.5 * math.sin(4 * math.pi * (ph - DUTY / 2))
            body_loc.append((f, (0.0, 0.0, hz)))
            body_rot.append((f, (0.0, -math.radians(pitch), 0.0)))
            roar = 14.0 * math.sin(math.pi * scatter(f)) if not self.lead else 0.0
            jaw_rot.append((f, (0.0, math.radians(4.0 + jaw + roar), 0.0)))
            for side in (0, 1):
                yy = (-HIP_Y if side == 0 else HIP_Y) * sc
                px, pz = 0.0, hz
                lens = (L_THIGH * sc, L_SHIN * sc, L_META * sc, L_TOE * sc)
                for j, a in enumerate(self.leg_angles(f, side)):
                    seg_loc[side, j].append((f, (px, yy, pz)))
                    seg_rot[side, j].append((f, (0.0, -math.radians(a), 0.0)))
                    px += lens[j] * math.cos(math.radians(a))
                    pz += lens[j] * math.sin(math.radians(a))
        keyed(self.root, "location", root_loc)
        keyed(self.root, "rotation_euler", root_rot)
        keyed(self.body, "location", body_loc)
        keyed(self.body, "rotation_euler", body_rot)
        keyed(self.jaw, "rotation_euler", jaw_rot)
        for k, ob in self.segs.items():
            keyed(ob, "location", seg_loc[k])
            keyed(ob, "rotation_euler", seg_rot[k])


# ------------------------------------------------------------------ lasers
LASER_X = (-270.0, 270.0, -560.0, 560.0)          # fan sources on the horizon (far-rig space), the outer two burst in
N_BEAMS = 6


def fan_state(i, f):
    """(center deg from vertical, half spread deg, level) of fan i at frame f. Fans 0-1 always run (2-bar sweep in
    bars 1-4, 1-bar sweep in bars 5-8); fans 2-3 join in bars 5-8. All four burst open on the bar-5 hit."""
    c = vj.clock(f)
    sec = section(f)
    sgn = 1 if i % 2 == 0 else -1
    burst = (f % vj.FRAMES) - vj.BEAT_F[SECTION_B]
    opening = 0.35 + 0.65 * vj.ease(burst / 6.0) if burst >= 0 else 0.35
    sweep_a = sgn * 18.0 * math.sin(2 * math.pi * f / (vj.FRAMES / 4) + 0.6 * i)
    sweep_b = sgn * 28.0 * math.sin(2 * math.pi * f / (vj.FRAMES / 8) + 0.6 * i)
    spread_b = 34.0 * opening
    level = 0.8 + 0.22 * c["kick"] + 0.25 * swell(f)
    if i < 2:
        return sweep_a + (sweep_b - sweep_a) * sec, 14.0 + (spread_b - 14.0) * sec, level
    return sweep_b, spread_b, level * sec


def laser_dirs(i, f):
    center, spread, level = fan_state(i, f)
    out = []
    for j in range(N_BEAMS):
        a = math.radians(center + spread * (2 * j / (N_BEAMS - 1) - 1))
        out.append((Vector((math.sin(a), -0.12, math.cos(a))).normalized(), level))
    return out


# ------------------------------------------------------------------ scene
def signals(f):
    c = vj.clock(f)
    return {"Kick": c["kick"], "Swell": swell(f), "Section": section(f)}


def build():
    scene = vj.reset_scene()
    frames = list(range(vj.FRAMES + 1))
    sig = [signals(f) for f in frames]
    vj.build_clock({key: [s[key] for s in sig] for key in sig[0]})

    mats = {"rim": rim_mat("RaptorRim", PAL["rim"], 4.5), "eye": flat_mat("Eye", PAL["eye"], 5.0)}
    meshes = {"body": body_mesh(), "jaw": jaw_mesh(), "eyes": eyes_mesh(),
              "thigh": bone_mesh(L_THIGH, 0.2, 0.085), "shin": bone_mesh(L_SHIN, 0.075, 0.05),
              "meta": bone_mesh(L_META, 0.05, 0.036), "toe": bone_mesh(L_TOE, 0.036, 0.012, tip=True, sickle=True)}
    raptors = [Raptor(i, row) for i, row in enumerate(LAYOUT)]
    for r in raptors:
        r.build(mats, meshes)
        r.animate()

    # floor: world-fixed grid, so it scrolls past as the pack and camera travel
    floor = bmesh.new()
    bmesh.ops.create_grid(floor, x_segments=1, y_segments=1, size=1.0)
    bmesh.ops.scale(floor, vec=(1700, 800, 1), verts=floor.verts)
    bmesh.ops.translate(floor, vec=(TRAVEL / 2 - 500, 760, 0), verts=floor.verts)
    vj.new_obj("GridFloor", floor, grid_mat())

    # palms: a world-fixed silhouette layer, periodic over the loop's travel: copies from -6T to +T, so the stampede's
    # camera (looking back along -x) finds the same far palms on the horizon at frame 0 and at frame N until they pass
    # behind the sky card (with copies only to -2T a palm row 400-550 m out existed at frame N only: seam 42 dB)
    rng = random.Random(11)
    pmat = black_mat("PalmBlack")
    base = [(i * TRAVEL / 9 + rng.uniform(-6, 6), rng.uniform(52, 95), rng.uniform(9, 15), rng.uniform(-0.2, 0.2))
            for i in range(9)]
    for i, (px, py, h, lean) in enumerate(base):
        me = finish_bm(palm_bm(random.Random(100 + i), h, lean))
        for k in range(-6, 2):
            mesh_obj(f"Palm{i}_{k}", me, pmat).location = (px + k * TRAVEL, py, 0)

    # far rig: follows the camera's travel and heading; carries the sky and the laser sources
    rig = vj.new_empty("FarRig")
    cx, cy, _ = CAM["pos"]
    keyed(rig, "location", [(f, (V * f + cx, cy, 0)) for f in (-30, 480)])
    rig.rotation_euler = (0, 0, math.radians(CAM["yaw"]))
    sky = bmesh.new()
    bmesh.ops.create_grid(sky, x_segments=1, y_segments=1, size=1.0)
    bmesh.ops.scale(sky, vec=(1400, 600, 1), verts=sky.verts)
    bmesh.ops.rotate(sky, cent=(0, 0, 0), matrix=Matrix.Rotation(math.radians(90), 3, "X"), verts=sky.verts)
    bmesh.ops.translate(sky, vec=(0, 0, 500), verts=sky.verts)
    vj.new_obj("Sky", sky, sky_mat(), rig).location = (0, SKY_DIST, 0)

    beam = beam_mat("Laser", 3.2)
    for i, lx in enumerate(LASER_X):
        st = {f: laser_dirs(i, f) for f in EXT}
        col, gain = PAL["lasers"][i % 2], PAL["laser_gain"][i % 2]   # the high-luma colors (cyan, green) run dimmer
        for j in range(N_BEAMS):
            ob = vj.new_obj(f"Laser{i}_{j}", beam_bm(), beam, rig)
            ob.location = (lx, SKY_DIST - 40, -2.0)
            ob.rotation_mode = "QUATERNION"
            keyed(ob, "rotation_quaternion", [(f, tuple(st[f][j][0].to_track_quat("-Y", "X"))) for f in EXT])
            keyed(ob, "color", [(f, (*col, gain * st[f][j][1])) for f in range(vj.FRAMES + 1)], interp="CONSTANT")

    # camera: tracks the pack with a gentle periodic sway and a small bump on the kick
    cam_data = bpy.data.cameras.new("Cam")
    cam_data.lens, cam_data.sensor_width, cam_data.sensor_fit = CAM["lens"], 36.0, "HORIZONTAL"
    cam_data.shift_y = CAM["shift_y"]
    cam_data.clip_start, cam_data.clip_end = 0.2, 3000.0
    cam = bpy.data.objects.new("Cam", cam_data)
    scene.collection.objects.link(cam)
    scene.camera = cam
    loc, rot = [], []
    for f in EXT:
        c = vj.clock(f)
        w = 2 * math.pi * f / vj.FRAMES
        loc.append((f, (V * f + cx + 0.4 * math.sin(w), cy + 0.7 * math.sin(w + 1.0), CAM["pos"][2]
                        + 0.05 * math.sin(2 * w) - 0.025 * c["kick"])))
        rot.append((f, (math.radians(90.0 + 0.8 * math.sin(2 * w + 0.4)), math.radians(0.8 * math.sin(w + 2.0)),
                        math.radians(CAM["yaw"] + 1.2 * math.sin(w + 0.3)))))
    keyed(cam, "location", loc)
    keyed(cam, "rotation_euler", rot)
    return scene, cam, raptors


def bounds(scene, cam, raptors):
    """Screen extent of the raptors over the loop (key art must stay inside the middle 90%)."""
    from bpy_extras.object_utils import world_to_camera_view
    lo, hi = [1.0, 1.0], [0.0, 0.0]
    worst = {}
    for f in range(0, vj.FRAMES, 3):
        scene.frame_set(f)
        for r in raptors:
            for ob in r.parts:
                for corner in ob.bound_box:
                    p = world_to_camera_view(scene, cam, ob.matrix_world @ Vector(corner))
                    for a in (0, 1):
                        if p[a] < lo[a]:
                            lo[a] = p[a]
                            worst[("lo", a)] = (f, ob.name)
                        if p[a] > hi[a]:
                            hi[a] = p[a]
                            worst[("hi", a)] = (f, ob.name)
    vj.log(f"bounds x {lo[0]:.3f}..{hi[0]:.3f}  y {lo[1]:.3f}..{hi[1]:.3f}  (keep inside 0.05..0.95); {worst}")


scene, cam, raptors = build()
vj.setup_render(scene, samples=int(vj.arg("--samples", 16)), pct=int(vj.arg("--pct", 100)),
                view=vj.arg("--view", "Standard"), exposure=float(vj.arg("--exposure", 0.0)),
                bloom=tuple(float(x) for x in vj.arg("--bloom", "1.0,0.6,0.4").split(",")), mblur=vj.flag("--mblur"))
if vj.flag("--bounds"):
    bounds(scene, cam, raptors)
vj.finish(scene, NAME)
