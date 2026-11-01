"""EXTINCTION EVENT - Dino Stage VJ loop (drop). 8 bars, seamless, 1920x1080 @ 30 fps; tempo from vjkit (140 BPM
half-time = 411 frames by default; the 128 cut was straight, 450 frames).

A jungle skyline at night: palms, a long-necked brachiosaurus pair and a smoking volcano in silhouette over a laser-grid
plain. In bars 6-8 a meteor streaks in from the upper left, trailing fire, while the horizon under it warms; it
slams into the jungle horizon on the loop's downbeat (frame 0, so triggering the loop on the drop puts the hit on the
drop). The horizon flares orange (a flare, never a white-out), a shock ring races out across the sky and a shockwave
across the plain toward the camera, a blast dome rises, and the skyline burns red, spreading along the horizon and
dying down through bars 2-5 while embers drift up through bars 1-5.
Everything swells into the impact (the meteor's glow ramps up over its last beat) and decays after it; every accent
(half-time: the kick and the snare) lifts the sky, embers, grid and the meteor's trail a little and thumps the camera.
Variants (--variant): inferno (default), cyan (a cold comet: cyan trail, magenta flare, UV burn), shockwave (closer
camera that the blast knocks back, plus a meteor shower).
No strobing: <= 3 flashes/s, no one-frame hits, no ~1 m2 patch over 0.65 luma, kick pulse <= ~1.6x.

  blender.exe -b --factory-startup --python extinction_event.py -- --variant inferno --frames 0,6,300,440 [--pct 25]
  blender.exe -b --factory-startup --python extinction_event.py -- --variant inferno --all --seam DIR [--mblur]
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
from vjkit import AMBER, CYAN, MAGENTA, UV  # noqa: E402

INFERNO = dict(head=(1.0, 0.8, 0.55), trail_hot=(1.0, 0.4, 0.05), trail_cool=(0.85, 0.04, 0.0),
               flare=(1.0, 0.22, 0.02), burn=(1.0, 0.07, 0.0), sky=UV, sky_low=MAGENTA, grid=MAGENTA,
               ember_hot=(1.0, 0.45, 0.06), ember_cool=(1.0, 0.06, 0.0), ring=AMBER, dome=(1.0, 0.28, 0.03),
               crater=(1.0, 0.3, 0.02))
VARIANTS = {
    "inferno": dict(INFERNO, cam="wide", shower=0),
    "cyan": dict(head=(0.7, 0.92, 1.0), trail_hot=(0.05, 0.6, 1.0), trail_cool=(0.22, 0.0, 1.0),
                 flare=(1.0, 0.06, 0.5), burn=(0.5, 0.0, 1.0), sky=(0.05, 0.0, 0.7), sky_low=UV, grid=CYAN,
                 ember_hot=(0.3, 0.75, 1.0), ember_cool=(0.9, 0.0, 0.6), ring=CYAN, dome=MAGENTA,
                 crater=(1.0, 0.05, 0.45), cam="wide", shower=0),
    "shockwave": dict(INFERNO, sky_low=(1.0, 0.02, 0.25), grid=UV, ring=(1.0, 0.5, 0.08), cam="close", shower=8),
}
VARIANT, PAL = vj.variant(VARIANTS)
NAME = f"extinction_event_{VARIANT}"
GAIN = float(vj.arg("--gain", 1.0))

CAMS = {
    # impact point (x, y) on the ground, jungle depth band, camera height / pitch / lens, knock-back (m), meteor entry
    # (frame pixel x, y and distance m)
    "wide": dict(impact=(420.0, 3200.0), jungle=(430.0, 660.0), cam_z=3.0, pitch=5.0, lens=28.0, push=0.0,
                 start=(430, 300, 5000.0)),
    "close": dict(impact=(240.0, 1700.0), jungle=(260.0, 420.0), cam_z=2.5, pitch=6.5, lens=24.0, push=16.0,
                  start=(420, 300, 3500.0)),
}
CAM = CAMS[PAL["cam"]]
IX, IY = CAM["impact"]
SKY_Y = 6000.0                            # sky card distance
CX = IX * SKY_Y / IY                      # the impact's spot on the sky card (x; the horizon is z = 0)
RING_SPEED = IY / 24.0                    # the ground shockwave reaches the camera 24 frames after the hit
EXT = list(range(-2, vj.FRAMES + 3))

JOLT = 0.3 if vj.HALFTIME else 0.0       # camera pitch jolt on each accent (deg): the drop's weight as motion
F_ARRIVE = vj.BEAT_F[20]                  # bar 6: the meteor enters
PRE = 21                                  # frames of the final swell into the impact
TRAIL_GONE = 10                           # frames after the hit until the trail has burned out
METEOR_R = 28.0
P_IMPACT = Vector((IX, IY, 0.0))


def view_point(px, py, dist):
    """The world point `dist` m from the camera that shows at frame pixel (px, py), for the camera at rest (no sway or
    shake): x right, y down, 1920 x 1080."""
    p = math.radians(CAM["pitch"])
    th = 18.0 / CAM["lens"]                                       # tan of half the horizontal view (36 mm sensor)
    tv = th * 1080 / 1920
    d = (Vector((0.0, math.cos(p), math.sin(p))) + Vector((1.0, 0.0, 0.0)) * (px - 960) / 960 * th
         + Vector((0.0, -math.sin(p), math.cos(p))) * (540 - py) / 540 * tv).normalized()
    return Vector((0.0, 0.0, CAM["cam_z"])) + d * dist


# the meteor enters at a frame pixel inside the Dino Stage's arch window (its upper left), so its whole approach in
# bars 6-8 shows on the arch screen (from the top-left corner it spent bars 6-7 off the screen), and in front of the
# sky card (SKY_Y): starting behind it, the opaque sky hid the meteor until bar 7
P_START = view_point(*CAM["start"])


# ------------------------------------------------------------------ the event's timeline (frame f, periodic)
def ff(f):
    return f % vj.FRAMES


def flare(f):
    """Rises over the last PRE frames (the meteor's glow), peaks on the hit, then decays fast."""
    f = ff(f)
    if f >= vj.FRAMES - PRE:
        return 0.9 * ((f - (vj.FRAMES - PRE)) / PRE) ** 2.2
    return math.exp(-f / 9.0)


def burn(f):
    """The skyline fire: catches within a beat of the hit, holds through bar 2, dies down by bar 6."""
    f = ff(f)
    hold, gone = vj.BEAT_F[8], vj.BEAT_F[20]
    d = 1.0 if f < hold else (1.0 - vj.ease((f - hold) / (gone - hold)) if f < gone else 0.0)
    return (1.0 - math.exp(-f / 6.0)) * d


def spread(f):
    return 400.0 + 5600.0 * (1.0 - math.exp(-ff(f) / 45.0))


def approach(f):
    """0..1 while the meteor is in the sky (bars 6-8), then a short afterglow."""
    f = ff(f)
    if f >= F_ARRIVE:
        return ((f - F_ARRIVE) / (vj.FRAMES - F_ARRIVE)) ** 2
    return math.exp(-f / 12.0)


def sky_ring(f):
    f = ff(f)
    return 2200.0 * (1.0 - math.exp(-f / 8.0)), (math.exp(-f / 9.0) * min(f / 2.0, 1.0) if f < 60 else 0.0)


def ground_ring(f):
    f = ff(f)
    if f > 48:
        return -1000.0, 0.0
    return RING_SPEED * f, math.exp(-f / 30.0) * min(f / 2.0, 1.0)


def meteor_u(f):
    """Path parameter: 0 at its entry (P_START) on bar 6, 1 at the impact (frame FRAMES == 0); None when gone."""
    f = ff(f)
    if f >= F_ARRIVE:
        return ((f - F_ARRIVE) / (vj.FRAMES - F_ARRIVE)) ** 1.7
    if f == 0:
        return 1.0
    return None


def knock(f):
    """Camera knock-back (m, backwards) when the ground shockwave reaches it, easing home over the loop."""
    if CAM["push"] == 0:
        return 0.0
    f = ff(f)
    hit = IY / RING_SPEED
    if f < hit:
        return 0.0
    if f < hit + 10:
        return CAM["push"] * vj.ease((f - hit) / 10.0)
    return CAM["push"] * (1.0 - vj.ease((f - hit - 10) / (vj.FRAMES - hit - 10)))


def shake(f):
    """(pitch, roll) in degrees: a small jolt on the hit and a bigger one when the shockwave passes."""
    f = ff(f)
    out = [0.0, 0.0]
    for t0, amp in ((0.0, 0.3), (IY / RING_SPEED, 0.65)):
        t = f - t0
        if 0 <= t < 30:
            e = math.exp(-t / 4.0) * math.sin(2 * math.pi * t / 5.0)
            out[0] += amp * e
            out[1] += 0.6 * amp * math.exp(-t / 4.0) * math.sin(2 * math.pi * t / 6.3)
    return out


def signals(f):
    c = vj.clock(f)
    sr, sa = sky_ring(f)
    gr, ga = ground_ring(f)
    return {"Kick": c["kick"], "Flare": flare(f), "Burn": burn(f), "Spread": spread(f), "Approach": approach(f),
            "SkyR": sr, "SkyA": sa, "GroundR": gr, "GroundA": ga,
            "LoopCos": math.cos(2 * math.pi * c["loop"]), "LoopSin": math.sin(2 * math.pi * c["loop"])}


# ------------------------------------------------------------------ helpers
def keyed(owner, prop, frame_values, interp="LINEAR"):
    """Key owner.prop at every (frame, value) in one pass per F-curve."""
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


def finish_bm(bm, smooth=True):
    me = bpy.data.meshes.new("m")
    bm.to_mesh(me)
    bm.free()
    if smooth:
        me.shade_smooth()
    return me


def mesh_obj(name, me, mat=None, parent=None, loc=(0, 0, 0)):
    """Object on (possibly shared) mesh data; its material is linked to the object, so shared meshes can differ."""
    ob = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(ob)
    if mat is not None:
        if not me.materials:
            me.materials.append(mat)
        ob.material_slots[0].link = "OBJECT"
        ob.material_slots[0].material = mat
    ob.parent = parent
    ob.location = loc
    return ob


def emit_layers(s, layers):
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


def smooth_s(s, x, lo, hi):
    n = s.node("ShaderNodeMapRange", interpolation_type="SMOOTHSTEP")
    s.put(n.inputs["Value"], x)
    s.put(n.inputs["From Min"], lo)
    s.put(n.inputs["From Max"], hi)
    return n.outputs["Result"]


def length2(s, a, b):
    return s.math("SQRT", s.add(s.mul(a, a), s.mul(b, b)))


# ------------------------------------------------------------------ materials
def black_mat():
    return vj.Shader("Silhouette").emit((0.0, 0.0, 0.0), 0.0)


def sky_mat():
    s = vj.Shader("Sky")
    tc = s.node("ShaderNodeTexCoord")
    x, _, z = s.xyz(tc.outputs["Object"])
    zp = s.math("MAXIMUM", z, 0.0)
    dx = s.math("SUBTRACT", x, CX)
    kick = s.add(1.0, s.mul(s.c("Kick"), 0.26))
    base = s.mul(s.add(s.mul(s.falloff(zp, 380.0), 0.32), s.mul(s.falloff(zp, 1600.0), 0.05)), kick, GAIN)
    base_col = s.mix(s.smooth(zp, 0.0, 700.0), PAL["sky_low"], PAL["sky"])
    r = length2(s, dx, s.mul(zp, 1.25))
    warm = s.mul(s.c("Approach"), s.falloff(r, 1300.0), 0.16)                      # the horizon warms under it
    fl = s.mul(s.c("Flare"), s.exp(s.mul(s.math("DIVIDE", s.mul(r, r), 1150.0 ** 2), -1.0)), 0.62)
    bn = s.mul(s.c("Burn"), s.exp(s.math("DIVIDE", s.math("ABSOLUTE", dx), s.mul(s.c("Spread"), -1.0))),
               s.falloff(zp, 1000.0), kick, 0.85)
    ring = s.mul(s.c("SkyA"), s.gauss(r, s.c("SkyR"), s.madd(s.c("SkyR"), 0.02, 25.0)), 0.6)
    vor = s.node("ShaderNodeTexVoronoi", feature="F1")
    s.put(vor.inputs["Vector"], s.vec(s.mul(x, 1 / 90.0), s.mul(z, 1 / 90.0), 0.0))
    vor.inputs["Scale"].default_value = 1.0
    dot = s.math("SUBTRACT", 1.0, s.smooth(vor.outputs["Distance"], 0.03, 0.08))
    star = s.mul(dot, s.smooth(vor.outputs["Color"], 0.7, 0.78), s.smooth(zp, 500.0, 1100.0),
                 s.math("SUBTRACT", 1.0, s.mul(s.c("Burn"), 0.85)), 0.45 * GAIN)
    return emit_layers(s, [(base_col, base), (PAL["flare"], s.mul(s.add(warm, fl), GAIN)),
                           (PAL["burn"], s.mul(bn, GAIN)), (PAL["ring"], s.mul(ring, GAIN)),
                           ((0.8, 0.85, 1.0), star)])


def ground_mat():
    s = vj.Shader("Ground")
    geo = s.node("ShaderNodeNewGeometry")
    x, y, _ = s.xyz(geo.outputs["Position"])
    spacing = 12.0
    hw = s.mul(s.dist, 0.0022)

    def lines(v):
        t = s.math("FRACT", s.madd(v, 1.0 / spacing, 0.5))
        d = s.mul(s.math("ABSOLUTE", s.math("SUBTRACT", t, 0.5)), spacing)
        return s.math("SUBTRACT", 1.0, smooth_s(s, d, hw, s.mul(hw, 2.5)))

    g = s.mul(s.math("MAXIMUM", lines(x), lines(y)), s.falloff(s.dist, 260.0),
              s.math("SUBTRACT", 1.0, s.smooth(s.dist, CAM["jungle"][0] * 0.8, CAM["jungle"][0])))
    lift = s.add(0.55, s.mul(s.c("Kick"), 0.3), s.mul(s.c("Burn"), 0.25))
    d_imp = length2(s, s.math("SUBTRACT", x, IX), s.math("SUBTRACT", y, IY))
    # the shockwave stays a thin line on screen, also as it sweeps under the camera (a wide band flooded the plain)
    ring = s.mul(s.c("GroundA"), s.gauss(d_imp, s.c("GroundR"), s.madd(s.dist, 0.006, 1.0)))
    near = s.math("SUBTRACT", 1.0, s.smooth(s.dist, 0.0, 6.0))                     # thin out right at the lens
    warm = s.mul(s.smooth(s.dist, 0.3 * CAM["jungle"][0], CAM["jungle"][0]),        # the far plain catches the fire
                 s.add(s.mul(s.c("Flare"), 0.22), s.mul(s.c("Burn"), 0.1)))
    return emit_layers(s, [(PAL["grid"], s.mul(g, lift, 1.4 * GAIN)),
                           (PAL["ring"], s.mul(ring, s.math("SUBTRACT", 1.0, near), 2.4 * GAIN)),
                           (PAL["flare"], s.mul(warm, GAIN))])


def obj_light_mat(name, gain, additive=False, soft=False):
    """Per-object light: color = object color RGB, intensity = object color alpha (x kick lift)."""
    s = vj.Shader(name)
    oi = s.node("ShaderNodeObjectInfo")
    k = s.add(1.0, s.mul(s.c("Kick"), 0.3))
    strength = s.mul(oi.outputs["Alpha"], k, gain * GAIN)
    if soft:
        strength = s.mul(strength, s.math("POWER", s.core(0.0, 1.0), 2.0))
    return s.additive(oi.outputs["Color"], strength) if additive else s.emit(oi.outputs["Color"], strength)


def trail_mat():
    s = vj.Shader("MeteorTrail")
    oi = s.node("ShaderNodeObjectInfo")
    tc = s.node("ShaderNodeTexCoord")
    x, y, z = s.xyz(tc.outputs["Object"])
    u = s.math("MINIMUM", s.math("MAXIMUM", x, 0.0), 1.0)
    nz = s.node("ShaderNodeTexNoise")
    s.put(nz.inputs["Vector"], s.vec(s.mul(u, 7.0), s.madd(s.c("LoopCos"), 1.3, s.mul(y, 0.4)),
                                     s.madd(s.c("LoopSin"), 1.3, s.mul(z, 0.4))))
    nz.inputs["Scale"].default_value = 1.4
    nz.inputs["Detail"].default_value = 3.0
    flicker = s.madd(nz.outputs["Fac"], 0.8, 0.6)
    fall = s.math("POWER", s.math("SUBTRACT", 1.0, u), 1.7)
    soft = s.math("POWER", s.core(0.0, 1.0), 1.5)
    col = s.mix(s.math("POWER", u, 0.6), PAL["trail_hot"], PAL["trail_cool"])
    k = s.add(1.0, s.mul(s.c("Kick"), 0.22))
    return s.additive(col, s.mul(oi.outputs["Alpha"], fall, soft, flicker, k, 3.0 * GAIN))


def dome_mat():
    s = vj.Shader("BlastDome")
    oi = s.node("ShaderNodeObjectInfo")
    lw = s.node("ShaderNodeLayerWeight")
    rim = s.smooth(lw.outputs["Facing"], 0.55, 0.98)
    return s.additive(PAL["dome"], s.mul(oi.outputs["Alpha"], rim, 1.6 * GAIN))


# ------------------------------------------------------------------ geometry
def frond(bm, base, sign, length, rise, droop, width, rng):
    ctrl = [base, base + Vector((sign * 0.3 * length, rng.uniform(-0.3, 0.3) * length * 0.1, rise * length)),
            base + Vector((sign * 0.68 * length, 0, (rise * 0.6 - droop * 0.2) * length)),
            base + Vector((sign * length, 0, -droop * length))]
    pts = vj.catmull(ctrl, per=8)
    left, right = [], []
    n = len(pts)
    for i, p in enumerate(pts):
        t = (pts[min(i + 1, n - 1)] - pts[max(i - 1, 0)]).normalized()
        nrm = Vector((-t.z, 0, t.x)).normalized()
        u = i / (n - 1)
        w = width * (1 - u) ** 0.6 * (1.7 if i % 2 else 0.55) + 0.02 * length
        left.append(bm.verts.new(p + nrm * w * 0.5))
        right.append(bm.verts.new(p - nrm * w))
    for i in range(n - 1):
        bm.faces.new((left[i], left[i + 1], right[i + 1], right[i]))


def palm(bm, at, height, lean, rng):
    sx = math.sin(lean) * height
    top = at + Vector((sx * 0.62, 0, height))
    trunk = vj.catmull([at - Vector((0, 0, 3)), at + Vector((sx * 0.12, 0, height * 0.35)),
                        at + Vector((sx * 0.38, 0, height * 0.72)), top], per=5)
    r = height * 0.025
    vj.tube(bm, trunk, lambda u: r * (1.15 - 0.45 * u), segs=8)
    for i in range(9):
        frond(bm, top, -1 if i % 2 else 1, height * rng.uniform(0.32, 0.48), rng.uniform(0.05, 0.45),
              rng.uniform(0.15, 0.75), height * rng.uniform(0.06, 0.085), rng)


def brachio(bm, at, sc, facing=1):
    """A brachiosaurus in profile (local x forward), standing; sc = 1 is about 19 m to the top of the head."""
    def P(x, z, y=0.0):
        return at + Vector((facing * x * sc, y * sc, z * sc))
    body = vj.catmull([P(-6.5, 6.2), P(-3, 7.4), P(1.5, 8.2), P(5.2, 8.6)], per=6)
    vj.tube(bm, body, lambda u: sc * (1.6 + 1.5 * math.sin(math.pi * min(u * 1.1, 1.0))), segs=12)
    neck = vj.catmull([P(4.6, 8.8), P(7.0, 12.0), P(8.4, 16.0), P(9.2, 18.6)], per=6)
    vj.tube(bm, neck, lambda u: sc * (1.25 - 0.75 * u), segs=10)
    head = vj.catmull([P(8.8, 18.7), P(9.6, 19.1), P(10.6, 18.7)], per=4)
    vj.tube(bm, head, lambda u: sc * (0.62 - 0.25 * u), segs=8)
    tail = vj.catmull([P(-6.0, 6.5), P(-10.0, 5.2), P(-14.0, 3.4), P(-17.5, 2.2)], per=6)
    vj.tube(bm, tail, lambda u: sc * (1.35 * (1 - u) + 0.08), segs=8)
    for x0, side in ((4.2, -1), (4.2, 1), (-4.0, -1), (-4.0, 1)):
        leg = [P(x0, 7.0, 1.0 * side), P(x0 + 0.3, 3.5, 1.1 * side), P(x0 + 0.1, -0.5, 1.1 * side)]
        vj.tube(bm, leg, lambda u: sc * (1.0 - 0.25 * u), segs=8)


def jungle(rng):
    """Silhouette skyline: a canopy curtain, bush blobs and giant palms across the jungle band."""
    y0, y1 = CAM["jungle"]
    half = y1 * 0.75
    bm = bmesh.new()
    xs = [-half + i * (2 * half) / 240 for i in range(241)]
    top = [7 + 3 * math.sin(x / 23) + 2 * math.sin(x / 9.7 + 1) + 1.5 * math.sin(x / 4.1 + 2) for x in xs]
    yc = (y0 + y1) / 2
    low = [bm.verts.new((x, yc, -3.0)) for x in xs]
    high = [bm.verts.new((x, yc, h * y0 / 430.0)) for x, h in zip(xs, top)]
    for i in range(len(xs) - 1):
        bm.faces.new((low[i], low[i + 1], high[i + 1], high[i]))
    for _ in range(90):
        x, y = rng.uniform(-half, half), rng.uniform(y0, y1)
        r = rng.uniform(5.0, 11.0) * y / 430.0
        bmesh.ops.create_icosphere(bm, subdivisions=2, radius=r,
                                   matrix=Matrix.Translation((x, y, rng.uniform(0.0, 0.5) * r)) @
                                   Matrix.Diagonal((1.0, 1.0, rng.uniform(0.6, 1.0), 1.0)))
    for _ in range(26):
        x, y = rng.uniform(-half, half), rng.uniform(y0, y1)
        palm(bm, Vector((x, y, 0.0)), rng.uniform(22.0, 44.0) * y / 430.0, rng.uniform(-0.18, 0.18), rng)
    sc = y0 / 430.0                                              # the pair stands against the bright side of the sky
    brachio(bm, Vector((0.24 * y0, y0 - 110, 0.0)), 1.5 * sc)
    brachio(bm, Vector((0.32 * y0, y0 - 95, 0.0)), 0.8 * sc)
    return finish_bm(bm, smooth=False)


def volcano(rng):
    bm = bmesh.new()
    vx, vy, h, rb, rt = -0.33 * IY, 0.85 * IY, 0.105 * IY, 0.26 * IY, 0.02 * IY
    bmesh.ops.create_cone(bm, cap_ends=False, segments=64, radius1=rb, radius2=rt, depth=h,
                          matrix=Matrix.Translation((vx, vy, h / 2 - 2.0)))
    crater = bmesh.new()
    vj.tube(crater, vj.circle_pts(Vector((vx, vy, h - 2.0)), rt * 0.96, 48, axis="Z"), lambda u: rt * 0.09,
            segs=8, closed=True)
    for a in (-0.35, 0.25):                                       # two lava runnels down the flank
        pts = []
        for i in range(25):
            t = i / 24
            r = rt + (rb * 0.55 - rt) * t
            ang = -math.pi / 2 + a + 0.25 * math.sin(t * 5 + a * 9)
            pts.append(Vector((vx + r * math.cos(ang), vy + r * math.sin(ang), (h - 2.0) * (1 - 0.55 * t))))
        vj.tube(crater, pts, lambda u: rt * 0.05 * (1 - 0.7 * u), segs=6)
    return finish_bm(bm, smooth=False), finish_bm(crater)


# ------------------------------------------------------------------ scene
def build():
    scene = vj.reset_scene()
    frames = list(range(vj.FRAMES + 1))
    sig = [signals(f) for f in frames]
    vj.build_clock({key: [s[key] for s in sig] for key in sig[0]})
    rng = random.Random(23)

    sky = bmesh.new()
    bmesh.ops.create_grid(sky, x_segments=1, y_segments=1, size=1.0)
    bmesh.ops.scale(sky, vec=(7000, 2400, 1), verts=sky.verts)
    bmesh.ops.rotate(sky, cent=(0, 0, 0), matrix=Matrix.Rotation(math.radians(90), 3, "X"), verts=sky.verts)
    bmesh.ops.translate(sky, vec=(0, 0, 2150), verts=sky.verts)
    vj.new_obj("Sky", sky, sky_mat()).location = (0, SKY_Y, 0)

    ground = bmesh.new()
    bmesh.ops.create_grid(ground, x_segments=1, y_segments=1, size=1.0)
    bmesh.ops.scale(ground, vec=(5000, 2950, 1), verts=ground.verts)
    bmesh.ops.translate(ground, vec=(0, 2920, 0), verts=ground.verts)
    vj.new_obj("Ground", ground, ground_mat())

    black = black_mat()
    mesh_obj("Jungle", jungle(rng), black)
    cone, lava = volcano(rng)
    mesh_obj("Volcano", cone, black)
    crater = mesh_obj("Crater", lava, obj_light_mat("Crater", 2.2))
    crater.color = (*PAL["crater"], 1.0)

    # the meteor: an empty flying the path, carrying the head, its halo and the fire trail (scaled to its length)
    rig = vj.new_empty("Meteor")
    rig.rotation_mode = "QUATERNION"
    rig.rotation_quaternion = (P_START - P_IMPACT).normalized().to_track_quat("X", "Z")
    ico = bmesh.new()
    bmesh.ops.create_icosphere(ico, subdivisions=3, radius=1.0)
    m_ball = finish_bm(ico)
    head = mesh_obj("MeteorHead", m_ball, obj_light_mat("MeteorHead", 7.0), rig)
    head.scale = (METEOR_R,) * 3
    halo = mesh_obj("MeteorHalo", m_ball.copy(), obj_light_mat("MeteorHalo", 0.7, additive=True, soft=True), rig)
    halo.scale = (METEOR_R * 2.6,) * 3
    tr = bmesh.new()
    vj.tube(tr, [Vector((t / 20, 0, 0)) for t in range(21)], lambda u: 1.0 + 3.0 * u, segs=16)
    trail = mesh_obj("MeteorTrail", finish_bm(tr), trail_mat(), rig)
    loc, h_col, a_col, t_col, t_scale = [], [], [], [], []
    for f in EXT:
        u = meteor_u(f)
        fl = ff(f)
        if u is None and fl < TRAIL_GONE:                          # just after the hit: the trail burns out in place
            u, fade = 1.0, math.exp(-fl / 3.0) if fl < TRAIL_GONE - 2 else 0.0
        elif u is None:
            u, fade = 0.0, 0.0                                     # parked out of sight until bar 6
        else:
            fade = 1.0
        p = P_START + (P_IMPACT - P_START) * u
        loc.append((f, tuple(p)))
        alive = fade * min(1.0, (u + 0.02) / 0.05)
        head_a = alive * (1.0 - vj.ease((u - 0.965) / 0.035)) if f % vj.FRAMES != 0 else 0.0
        h_col.append((f, (*PAL["head"], head_a)))
        a_col.append((f, (*PAL["flare"], alive * (0.35 + 0.65 * u))))
        t_col.append((f, (1.0, 1.0, 1.0, alive)))
        t_scale.append((f, (1500.0 + 4200.0 * u, METEOR_R, METEOR_R)))
    keyed(rig, "location", loc)
    keyed(head, "color", h_col, interp="CONSTANT")
    keyed(halo, "color", a_col, interp="CONSTANT")
    keyed(trail, "color", t_col, interp="CONSTANT")
    keyed(trail, "scale", t_scale)

    # blast dome over the impact
    uvs = bmesh.new()
    bmesh.ops.create_uvsphere(uvs, u_segments=48, v_segments=24, radius=1.0)
    bmesh.ops.delete(uvs, geom=[v for v in uvs.verts if v.co.z < -0.01], context="VERTS")
    dome = mesh_obj("Dome", finish_bm(uvs), dome_mat(), loc=P_IMPACT)
    keyed(dome, "scale", [(f, (max(1.0, 0.26 * IY * (1 - math.exp(-ff(f) / 12.0))),) * 3) for f in EXT])
    keyed(dome, "color", [(f, (1, 1, 1, math.exp(-ff(f) / 14.0) * min(ff(f) / 3.0, 1.0) if ff(f) < 80 else 0.0))
                          for f in frames], interp="CONSTANT")

    # embers: rise from the burning skyline through bars 1-5
    emat = obj_light_mat("Ember", 6.0)
    y0, y1 = CAM["jungle"]
    for i in range(160):
        e = mesh_obj(f"Ember{i}", m_ball, emat)
        depth = rng.uniform(0.35 * y0, 0.95 * y0)
        x0 = rng.gauss(IX * depth / IY, 0.28 * depth)
        z0 = rng.uniform(4.0, 30.0) * depth / 430.0
        born = rng.uniform(2.0, 110.0) ** 1.0
        life = rng.uniform(140.0, min(260.0, vj.BEAT_F[22] - born))
        vz = rng.uniform(0.22, 0.55) * depth / 430.0
        vx = (rng.uniform(-0.12, 0.12) + 0.08 * math.copysign(1.0, x0 - IX * depth / IY)) * depth / 430.0
        sw, sp, ph = rng.uniform(2.0, 7.0) * depth / 430.0, rng.uniform(40.0, 90.0), rng.uniform(0, 6.28)
        size = rng.uniform(0.35, 0.85) * depth / 430.0
        e.scale = (size,) * 3
        hot = rng.random() < 0.5
        lk, ck = [], []
        for f in EXT:
            t = ff(f) - born
            tt = min(max(t, 0.0), life)
            lk.append((f, (x0 + vx * tt + sw * math.sin(tt / sp * 6.28 + ph), depth,
                           z0 + vz * tt + 0.0009 * tt * tt * depth / 430.0)))
            a = 0.0 if t < 0 or t > life else min(t / 8.0, 1.0) * min((life - t) / 40.0, 1.0)
            k = min(max(t / life, 0.0), 1.0)
            c0, c1 = PAL["ember_hot"], PAL["ember_cool"]
            col = tuple(p + (q - p) * k ** (0.6 if hot else 0.3) for p, q in zip(c0, c1))
            ck.append((f, (*col, a)))
        keyed(e, "location", lk)
        keyed(e, "color", ck, interp="CONSTANT")

    # a meteor shower (shockwave variant): small streaks crossing the sky in bars 2-8, burning out above the skyline
    smat = trail_mat()
    for i in range(PAL["shower"]):
        st = mesh_obj(f"Shower{i}", trail.data, smat)
        t0 = vj.BEAT_F[4 + 3 * i]
        dur = rng.uniform(20, 32)
        a0 = Vector((rng.uniform(-0.5, 0.9) * IY, IY * rng.uniform(1.2, 1.8), IY * rng.uniform(0.25, 0.42)))  # in
        # the arch window: higher starts crossed the sky above the screen's top edge
        d = Vector((rng.uniform(0.25, 0.6), -0.1, -0.35)).normalized() * IY * 0.45
        st.rotation_mode = "QUATERNION"
        st.rotation_quaternion = (-d).normalized().to_track_quat("X", "Z")
        lk, ck, sk = [], [], []
        for f in EXT:
            u = (ff(f) - t0) / dur
            vis = 0.0 if u < 0 or u > 1 else math.sin(math.pi * u) ** 0.7
            lk.append((f, tuple(a0 + d * min(max(u, 0.0), 1.0))))
            ck.append((f, (1, 1, 1, 0.55 * vis)))
            sk.append((f, (IY * 0.08 * (0.2 + 0.8 * min(max(u, 0.0), 1.0) ** 0.5), 6.0, 6.0)))
        keyed(st, "location", lk)
        keyed(st, "color", ck, interp="CONSTANT")
        keyed(st, "scale", sk)

    cam_data = bpy.data.cameras.new("Cam")
    cam_data.lens, cam_data.sensor_width, cam_data.sensor_fit = CAM["lens"], 36.0, "HORIZONTAL"
    cam_data.clip_start, cam_data.clip_end = 0.5, 20000.0
    cam = bpy.data.objects.new("Cam", cam_data)
    scene.collection.objects.link(cam)
    scene.camera = cam
    loc, rot = [], []
    for f in EXT:
        w = 2 * math.pi * f / vj.FRAMES
        p, r = shake(f)
        j = JOLT * vj.jolt(f)                                      # every kick and snare thumps the camera a little
        loc.append((f, (0.8 * math.sin(w), -knock(f), CAM["cam_z"] + 0.2 * math.sin(2 * w) - 0.03 * j)))
        rot.append((f, (math.radians(90.0 + CAM["pitch"] + 0.3 * math.sin(w + 0.5) + p - j), math.radians(r),
                        math.radians(0.6 * math.sin(w + 1.0)))))
    keyed(cam, "location", loc)
    keyed(cam, "rotation_euler", rot)
    return scene


scene = build()
vj.setup_render(scene, samples=int(vj.arg("--samples", 16)), pct=int(vj.arg("--pct", 100)),
                view=vj.arg("--view", "Standard"), exposure=float(vj.arg("--exposure", 0.0)),
                bloom=tuple(float(x) for x in vj.arg("--bloom", "1.0,0.6,0.4").split(",")), mblur=vj.flag("--mblur"))
vj.finish(scene, NAME)
