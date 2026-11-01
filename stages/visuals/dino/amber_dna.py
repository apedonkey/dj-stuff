"""AMBER DNA - Dino Stage VJ loop (intro / breakdown). 8 bars, seamless, 1920x1080 @ 30 fps; tempo from vjkit (140 BPM
half-time = 411 frames by default).

A double helix of amber beads with cyan rungs turns slowly in hanging amber dust. Its screw turn makes the strand
flow toward the camera (one full turn per loop, eased a little after each accent). Each accent (half-time: the kick and
the snare; straight: every beat) lights the next rung like a step sequencer: bars 1-4 walk away from the camera, bars
5-8 walk back (a ping-pong scan). Every bar a spark comes down the strand out of the dark and lands on the next
downbeat as it passes the camera, its trail fading after the hit.
The last two beats of bars 4 and 8 swell softly into the downbeat.
No strobing: at most 3 flashes per second, no one-frame hits, no full-frame white, no ~1 m2 patch of the 16 x 9 m wall
over 0.65 luma. Geometry and look are our own (the tube generator comes from the stage script via vjkit).

Variants (--variant):
  gold     amber beads, cyan rungs, amber dust; the strand crosses the frame from the lower left into the distance
  magenta  the same shot in magenta beads, laser-green rungs and UV dust
  vortex   gold, seen straight down the helix's axis: a slowly turning spiral tunnel (light sculpture, no occlusion)

  blender.exe -b --factory-startup --python amber_dna.py -- --variant gold --frames 0,14,225 [--pct 25] [--samples 4]
  blender.exe -b --factory-startup --python amber_dna.py -- --variant gold --all --out DIR
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
from vjkit import AMBER, CYAN, GREEN, MAGENTA, UV  # noqa: E402

GOLD = dict(bead=AMBER, line=(1.0, 0.42, 0.05), rung=CYAN, hot=(0.55, 0.88, 1.0), spark=(1.0, 0.7, 0.36),
            dust=(1.0, 0.4, 0.05))                     # linear emission colors
VARIANTS = {                                           # view: "side" (the strand crosses the frame) or "axis"
    "gold": dict(GOLD, view="side"),
    "magenta": dict(view="side", bead=MAGENTA, line=(0.55, 0.0, 1.0), rung=GREEN, hot=(0.6, 1.0, 0.55),
                    spark=(1.0, 0.5, 0.92), dust=(0.42, 0.04, 1.0)),
    "vortex": dict(GOLD, view="axis"),
}
VARIANT, PAL = vj.variant(VARIANTS)
VORTEX = PAL["view"] == "axis"
GAIN = float(vj.arg("--gain", 0.3 if VORTEX else 1.0))  # global emission multiplier; the vortex's light adds up

# helix, in its own frame: axis = +Z, the camera end at low z (strand A angle = rung index * TWIST)
R = 1.0                                   # backbone radius (m)
PER_TURN = 10                             # rungs per turn
TWIST = 2 * math.pi / PER_TURN
RISE = 0.42                               # axial rise per rung: a 4.2 m pitch
GROOVE = math.radians(150)                # strand B trails strand A: the major and minor grooves of real DNA
N0, N1 = (-12, 150) if VORTEX else (-30, 120)   # rung range: the strand runs on past both ends of the frame
TURN = 10                                 # rungs turned per loop (one full turn): seamless for any integer
BEAD_R, LINE_R, RUNG_R = 0.13, 0.034, 0.03

# step sequencer: a step per accent (16 per half straight, 8 half-time), SEQ_STRIDE rungs apart, from rung SEQ_I0
# into the distance (and back in bars 5-8); a lit rung fades over SEQ_TAU accents (1.4 beats)
N_ACC = vj.BEATS // vj.ACC
SEQ_I0, SEQ_STRIDE, SEQ_TAU = (14 if VORTEX else 17), 3 * vj.ACC, 1.4 / vj.ACC
# spark: lands on each downbeat at SPARK_NEAR (where the strand leaves the frame), coming from SPARK_FAR (in the fog).
# Seen down the axis (vortex) a spark lights a whole ring of beads: landing 7.5 m from the lens it filled 1 m2 blocks
# at 0.87 and then shot past the camera (one-frame hits), so there it lands 13 m out, at 60% strength
SPARK_NEAR, SPARK_FAR = (10.0, 48.0) if VORTEX else (4.2, 40.0)
SPARK_GAIN = 0.6 if VORTEX else 1.0
SPARK_W, SPARK_TRAIL = 0.5, 2.6           # head width (wider than a bead step: no flicker), trail length (m)
FOG_NEAR, FOG_LEN = (float(x) for x in vj.arg("--fog", "5.0,7.0" if VORTEX else "10.0,14.0").split(","))
NEAR_FADE = tuple(float(x) for x in vj.arg("--nearfade", "2.5,7.0" if VORTEX else "2.0,4.5").split(","))
# emission falls off as exp(-(d - FOG_NEAR) / FOG_LEN) with camera distance d and fades in over NEAR_FADE
KICK = 0.2                                # on-beat lift of the helix (soft: a breakdown loop)


# ------------------------------------------------------------------ music
def ratchet(f):
    """Rungs turned at frame f (any integer, unwrapped): TURN per loop, eased forward a little after each accent."""
    c = vj.clock(f)
    m, x = 0.35, (1.0 - math.exp(-4.0 * c["aph"])) / (1.0 - math.exp(-4.0))
    beats = vj.BEATS * math.floor(f / vj.FRAMES) + vj.ACC * (c["acc"] + (1 - m) * c["aph"] + m * x)
    return TURN * beats / vj.BEATS


def swell(f):
    """The fill: eases in over the last 2 beats of bars 4 and 8, peaks on the next downbeat, decays over ~1.5 beats."""
    c = vj.clock(f)
    if c["bar"] in (3, 7) and c["beat"] >= 2:
        f0, f1 = vj.BEAT_F[4 * c["bar"] + 2], vj.BEAT_F[4 * c["bar"] + 4]
        return ((c["f"] - f0) / (f1 - f0)) ** 2
    since = c["f"] - (vj.BEAT_F[16] if c["f"] >= vj.BEAT_F[16] else 0)
    return math.exp(-since / (1.5 * vj.FPB))


def spark(f):
    """(z, amplitude) of the incoming spark and of the one that landed on this bar's downbeat. The incoming one
    leaves the fog on a downbeat and runs down the strand at constant speed, reaching SPARK_NEAR on the next downbeat
    (perspective makes it rush in at the end); the landed one runs on past the camera end, its trail fading."""
    c = vj.clock(f)
    f0, f1 = vj.BEAT_F[4 * c["bar"]], vj.BEAT_F[4 * c["bar"] + 4]
    t = c["f"] - f0
    u = t / (f1 - f0)
    speed = (SPARK_FAR - SPARK_NEAR) / (f1 - f0)
    z_in = SPARK_FAR - (SPARK_FAR - SPARK_NEAR) * u
    a_in = vj.ease(u / 0.3)
    z_out = SPARK_NEAR - speed * t
    a_out = math.exp(-t / (0.45 * vj.FPB))
    return z_in, a_in, z_out, a_out


def signals(f):
    c = vj.clock(f)
    zi, ai, zo, ao = spark(f)
    return {"Kick": c["kick"], "AccPos": c["acc"] + c["aph"], "Swell": swell(f), "Loop": c["loop"],
            "SparkZ": zi, "SparkA": ai, "AfterZ": zo, "AfterA": ao}


# ------------------------------------------------------------------ geometry
def strand_pt(i, phase=0.0):
    a = i * TWIST + phase
    return Vector((R * math.cos(a), R * math.sin(a), i * RISE))


def build_helix():
    beads, lines, rungs = bmesh.new(), bmesh.new(), bmesh.new()
    for i in range(N0, N1 + 1):
        a, b = strand_pt(i), strand_pt(i, GROOVE)
        for p in (a, b):
            bmesh.ops.create_icosphere(beads, subdivisions=2, radius=BEAD_R, matrix=Matrix.Translation(p))
        vj.tube(rungs, [a, a.lerp(b, 0.5), b], lambda u: RUNG_R, segs=8)
    steps = (N1 - N0) * 6
    for phase in (0.0, GROOVE):
        pts = [strand_pt(N0 + (N1 - N0) * s / steps, phase) for s in range(steps + 1)]
        vj.tube(lines, pts, lambda u: LINE_R, segs=8)
    return beads, lines, rungs


def build_dust(groups=24, per=46, seed=7):
    """Dust specks in the helix frame, in groups that each float on their own slow loop. A per-speck random value
    ('rnd', a mesh attribute) sets its brightness and twinkle phase."""
    rng = random.Random(seed)
    out = []
    for g in range(groups):
        bm = bmesh.new()
        layer = bm.verts.layers.float.new("rnd")
        for _ in range(per):
            if VORTEX:                     # a sleeve around the helix, out to the frame edges
                a, r = rng.uniform(0, 2 * math.pi), math.sqrt(rng.uniform(0.25, 1.0)) * 6.0
                p = Vector((r * math.cos(a), r * math.sin(a), rng.uniform(-1.0, 50.0)))
            else:
                p = Vector((rng.uniform(-6.5, 6.5), rng.uniform(-4.5, 4.5), rng.uniform(-6.0, 52.0)))
            rad = 0.02 + 0.03 * rng.random() ** 3
            res = bmesh.ops.create_icosphere(bm, subdivisions=2, radius=rad, matrix=Matrix.Translation(p))
            v = rng.random()
            for vert in res["verts"]:
                vert[layer] = v
        orbit = (rng.uniform(0.15, 0.45), rng.uniform(0.1, 0.35), rng.uniform(0.2, 0.6),
                 rng.uniform(0, 2 * math.pi), rng.uniform(0, 2 * math.pi), rng.choice((1, 2)))
        out.append((bm, orbit))
    return out


# ------------------------------------------------------------------ materials
def axial(s):
    tc = s.node("ShaderNodeTexCoord")
    return s.xyz(tc.outputs["Object"])[2]


def fog(s):
    d = s.dist
    far = s.math("MINIMUM", s.exp(s.mul(s.math("SUBTRACT", d, FOG_NEAR), -1.0 / FOG_LEN)), 1.0)
    return s.mul(far, s.smooth(d, NEAR_FADE[0], NEAR_FADE[1]))


def spark_term(s, z, zkey, akey):
    """Head plus trail of a spark at axial position zkey: the trail lies behind it (larger z, where it came from)."""
    dz = s.math("SUBTRACT", z, s.c(zkey))
    head = s.gauss(dz, 0.0, SPARK_W)
    trail = s.mul(s.falloff(s.math("MAXIMUM", dz, 0.0), SPARK_TRAIL), s.smooth(dz, -0.3, 0.0))
    return s.mul(s.c(akey), s.add(head, s.mul(trail, 0.35)))


def sparks(s, z):
    return s.mul(s.add(spark_term(s, z, "SparkZ", "SparkA"), spark_term(s, z, "AfterZ", "AfterA")), SPARK_GAIN)


def seq_term(s, z):
    """1 on the rung the step sequencer lit this accent, decaying over SEQ_TAU accents. Step j (0 .. N_ACC/2 - 1)
    lights on accent j (bars 1-4, walking away) and on accent N_ACC - 1 - j (bars 5-8, walking back)."""
    j = s.mul(s.math("SUBTRACT", s.math("ROUND", s.mul(z, 1.0 / RISE)), SEQ_I0), 1.0 / SEQ_STRIDE)
    on = s.mul(s.math("COMPARE", j, s.math("ROUND", j), 0.01),
               s.math("GREATER_THAN", j, -0.5), s.math("LESS_THAN", j, N_ACC / 2 - 0.5))
    age_a = s.math("FLOORED_MODULO", s.math("SUBTRACT", s.c("AccPos"), j), N_ACC)
    age_b = s.math("FLOORED_MODULO", s.add(s.math("SUBTRACT", s.c("AccPos"), N_ACC - 1.0), j), N_ACC)
    age = s.math("MINIMUM", age_a, age_b)
    return s.mul(on, s.falloff(age, SEQ_TAU))


def finish_mat(s, color, strength):
    return s.additive(color, strength) if VORTEX else s.emit(color, strength)


def bead_mat():
    s = vj.Shader("Beads")
    z = axial(s)
    sp, seq = sparks(s, z), seq_term(s, z)
    lift = s.add(1.0, s.mul(s.c("Kick"), KICK), s.mul(s.c("Swell"), 0.3))
    body = s.mul(1.1 * GAIN, s.core(0.3, 1.25), lift)
    level = s.add(body, s.mul(seq, 0.9 * GAIN), s.mul(sp, 2.0 * GAIN))
    col = s.mix(s.math("MINIMUM", s.mul(sp, 1.5), 1.0), PAL["bead"], PAL["spark"])
    return finish_mat(s, col, s.mul(level, fog(s)))


def line_mat():
    s = vj.Shader("Backbone")
    z = axial(s)
    sp = sparks(s, z)
    lift = s.add(1.0, s.mul(s.c("Kick"), KICK), s.mul(s.c("Swell"), 0.3))
    level = s.add(s.mul(1.1 * GAIN, s.core(0.4, 1.3), lift), s.mul(sp, 3.0 * GAIN))
    col = s.mix(s.math("MINIMUM", s.mul(sp, 1.5), 1.0), PAL["line"], PAL["spark"])
    return finish_mat(s, col, s.mul(level, fog(s)))


def rung_mat():
    s = vj.Shader("Rungs")
    z = axial(s)
    seq, sp = seq_term(s, z), sparks(s, z)
    lift = s.add(1.0, s.mul(s.c("Kick"), KICK), s.mul(s.c("Swell"), 0.6))
    level = s.add(s.mul(0.3 * GAIN, lift), s.mul(seq, 4.0 * GAIN), s.mul(sp, 1.2 * GAIN))
    col = s.mix(s.mul(s.math("SQRT", seq), 0.7), PAL["rung"], PAL["hot"])
    return finish_mat(s, col, s.mul(level, s.core(0.5, 1.4), fog(s)))


def dust_mat():
    s = vj.Shader("Dust")
    rnd = s.node("ShaderNodeAttribute", attribute_name="rnd").outputs["Fac"]
    tw = s.madd(s.math("SINE", s.mul(s.madd(s.c("Loop"), 2.0, rnd), 2 * math.pi)), 0.4, 0.6)   # 2 twinkles a loop
    bright = s.madd(s.math("FRACT", s.mul(rnd, 7.31)), 0.8, 0.2)
    lift = s.add(1.0, s.mul(s.c("Swell"), 0.45))
    return finish_mat(s, PAL["dust"], s.mul(1.3 * GAIN, tw, bright, lift, s.core(0.3, 1.2), fog(s)))


# ------------------------------------------------------------------ scene
def look_at(pos, target):
    return (target - pos).to_track_quat("-Z", "Y")


def camera_keys(frames, dna):
    """World (location, rotation) per frame: a slow float that closes on itself every loop."""
    keys = []
    for f in frames:
        L = f / vj.FRAMES
        if VORTEX:                             # just off the axis, circling it slowly
            local = Vector((0.22 * math.cos(2 * math.pi * L), 0.16 * math.sin(2 * math.pi * L), -3.0))
            tgt = Vector((0.0, 0.0, 30.0))
            pos, tgt = dna.matrix_world @ local, dna.matrix_world @ tgt
        else:
            pos = Vector((0.45 * math.sin(2 * math.pi * L), 0.5 * math.sin(4 * math.pi * L + 0.6),
                          0.28 * math.cos(2 * math.pi * L)))
            tgt = Vector((0.6, 14.0, 0.0))
        keys.append((f, pos, look_at(pos, tgt)))
    return keys


def build():
    scene = vj.reset_scene()
    frames = list(range(vj.FRAMES + 1))                            # keys through 450 (== 0) for the seam check
    ext = list(range(-2, vj.FRAMES + 3))
    sig = [signals(f) for f in frames]
    vj.build_clock({key: [s[key] for s in sig] for key in sig[0]})

    dna = vj.new_empty("DNA")                                      # helix frame: local +Z runs into the distance
    if VORTEX:
        dna.location = (0.0, 0.0, 0.0)
        dna.rotation_euler = (math.radians(-90.0), 0.0, 0.0)       # local +Z -> world +Y
    else:
        mid, axis = Vector((0.0, 14.0, -0.1)), Vector((0.55, 0.83, 0.04)).normalized()
        near, far = mid - 9.0 * axis, mid + 30.0 * axis               # crosses the frame, receding to the right
        dna.location = near
        dna.rotation_mode = "QUATERNION"
        dna.rotation_quaternion = (far - near).normalized().to_track_quat("Z", "Y")
    bpy.context.view_layer.update()

    spin = vj.new_empty("Spin", dna)                               # the screw turn: flows toward the camera
    vj.animate(spin, "rotation_euler", [(f, (0.0, 0.0, TWIST * ratchet(f))) for f in ext], interp="LINEAR")
    beads, lines, rungs = build_helix()
    vj.new_obj("Beads", beads, bead_mat(), spin)
    vj.new_obj("Backbone", lines, line_mat(), spin)
    vj.new_obj("Rungs", rungs, rung_mat(), spin)

    dmat = dust_mat()
    for g, (bm, (ax, ay, az, p1, p2, m)) in enumerate(build_dust()):
        ob = vj.new_obj(f"Dust{g}", bm, dmat, dna)
        vj.animate(ob, "location", [(f, (ax * math.sin(2 * math.pi * f / vj.FRAMES + p1),
                                         ay * math.cos(2 * math.pi * m * f / vj.FRAMES + p2),
                                         az * math.sin(2 * math.pi * f / vj.FRAMES + p2))) for f in ext],
                   interp="LINEAR")

    cam_data = bpy.data.cameras.new("Cam")
    cam_data.lens, cam_data.sensor_width, cam_data.sensor_fit = 50.0 if VORTEX else 35.0, 36.0, "HORIZONTAL"
    cam_data.clip_start, cam_data.clip_end = 0.1, 500.0
    cam = bpy.data.objects.new("Cam", cam_data)
    scene.collection.objects.link(cam)
    scene.camera = cam
    cam.rotation_mode = "QUATERNION"
    keys = camera_keys(ext, dna)
    vj.animate(cam, "location", [(f, tuple(p)) for f, p, _ in keys], interp="LINEAR")
    vj.animate(cam, "rotation_quaternion", [(f, tuple(q)) for f, _, q in keys], interp="LINEAR")
    return scene


scene = build()
vj.setup_render(scene, samples=int(vj.arg("--samples", 16)), pct=int(vj.arg("--pct", 100)),
                view=vj.arg("--view", "Standard"), exposure=float(vj.arg("--exposure", 0.0)),
                bloom=tuple(float(x) for x in vj.arg("--bloom", "1.0,0.6,0.4").split(",")), mblur=vj.flag("--mblur"))
vj.finish(scene, "amber_dna_" + VARIANT)
