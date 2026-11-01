"""WITCHING HOUR - GRAVEYARD SHIFT VJ loop (intro). 8 bars, seamless, 1920x1080 @ 30 fps; tempo from vjkit
(140 BPM half-time = 411 frames).

The cathedral's gable clock as a neon gothic face on black: our own Roman numerals, a minute track, tracery, gears
turning behind the open face, a slowly turning rose window and faint stars. The loop is the last half minute before
midnight, forever:
  Bar 1     the strike's afterglow: the face cools from blood red back to UV purple while the hands rewind (the second
            hand sweeps back from XII to the 31-second mark, the minute hand back to 11:59): the witching hour repeats.
  Bars 2-8  the second hand ticks one mark per beat (29 ticks), an orange trail fills the minute track behind it toward
            XII, the gears tick with it, the rose window and the mist slowly build.
  Bar 8     the last two beats swell into the strike: the face and the trail morph to blood red and brighten, the
            outer ring charges red; on the downbeat (frame 0) the second and minute hands land on XII together and a
            red toll ring rolls out from the face.
Beat hooks: the second hand per beat (motion), a soft breath of the face on the kick and the snare, the strike on the
loop's downbeat (start the loop on a phrase and midnight lands on the drop of the phrase).
No strobing: thin lines only, the strike is a 2-beat swell, nothing flashes.

  blender.exe -b --factory-startup --python witching_hour.py -- --frames 0,60,300 [--pct 50] [--samples 16]
  blender.exe -b --factory-startup --python witching_hour.py -- --all --seam DIR [--out DIR] [--mblur]
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
import hwgeo as g  # noqa: E402
import letters  # noqa: E402
from vjkit import BLOOD, BONE, PUMPKIN, UVP  # noqa: E402

VARIANTS = {
    "purple": dict(face=UVP, numerals=BONE, trail=PUMPKIN, gear=PUMPKIN, strike=BLOOD),
}
VNAME, V = vj.variant(VARIANTS)
GAIN = float(vj.arg("--gain", 1.0))

R = 4.0                                   # clock radius (m); the camera frames it at ~420 px radius
CAM_D = 25.4
TICKS = 29                                # second-hand ticks per loop: beats 4..32 (bar 2's downbeat .. the strike)
SEC_START = 360.0 - 6.0 * TICKS           # 186 deg: the 31-second mark, where the rewind lands
REWIND = (0.5, 3.5)                       # beats of bar 1 over which the hands sweep back
MIN_AT = 354.0                            # minute hand at 11:59 (degrees clockwise from XII)


# ------------------------------------------------------------------ choreography
def tick_ease(t):
    """0 -> 1 over ~2 frames with an 8% overshoot that settles by frame 4 (a clock's escapement)."""
    if t <= 0:
        return 0.0
    return 1.0 - math.exp(-t / 0.8) * math.cos(t * 1.6)


def sec_angle(f):
    """Second hand (degrees clockwise from XII) at frame f; 360 on the strike (frame 0 == FRAMES)."""
    f %= vj.FRAMES
    r0, r1 = vj.FPB * REWIND[0], vj.FPB * REWIND[1]
    ring = 6.0 * (tick_ease(f + 1) - 1.0) if f < r0 else 0.0     # the strike tick's overshoot settling
    if f < r0:
        return 360.0 + ring
    if f < r1:
        return 360.0 - (360.0 - SEC_START) * vj.ease((f - r0) / (r1 - r0))
    th = SEC_START
    for k in range(4, 4 + TICKS):                                   # beats 4..32; the tick starts a frame early
        start = vj.beat_frame(k) - 1
        if f >= start:
            th = SEC_START + 6.0 * (k - 4) + 6.0 * tick_ease(f - start)
    return th


def min_angle(f):
    f %= vj.FRAMES
    r0, r1 = vj.FPB * REWIND[0], vj.FPB * REWIND[1]
    if f < r0:
        return 360.0
    if f < r1:
        return 360.0 - (360.0 - MIN_AT) * vj.ease((f - r0) / (r1 - r0))
    start = vj.FRAMES - 1                                             # the strike tick, a frame early
    return MIN_AT + 6.0 * tick_ease(f - start) if f >= start else MIN_AT


def strike(f):
    """The swell into midnight: eases in over the last 2 beats of bar 8, 1 on the downbeat, decays over ~1.5 beats."""
    f %= vj.FRAMES
    f0 = vj.BEAT_F[vj.BEATS - 2]
    if f >= f0:
        return ((f - f0) / (vj.FRAMES - f0)) ** 2
    return math.exp(-f / (1.5 * vj.FPB))


def rise(f):
    """Slow build over bars 5-8 (0 -> 1), falling back over bar 1 after the strike."""
    b = vj.clock(f)["beatpos"]
    if b >= vj.HALF:
        return vj.ease((b - vj.HALF) / (vj.BEATS - vj.HALF))
    if b < 4:
        return 1.0 - vj.ease(b / 4.0)
    return 0.0


def signals(f):
    c = vj.clock(f)
    s = {"Kick": c["kick"], "Strike": strike(f), "Build": rise(f), "Sec": sec_angle(f)}
    s.update(vj.loop_signals(f))
    return s


# ------------------------------------------------------------------ materials
def face_mat(name, col, base, kick=0.12, strike_gain=0.6):
    s = vj.Shader(name)
    c = s.mix(s.c("Strike"), col, V["strike"])
    lift = s.add(1.0, s.mul(s.c("Kick"), kick), s.mul(s.c("Strike"), strike_gain))
    return s.emit(c, s.mul(lift, s.core(0.5, 1.4), base * GAIN))


def ticks_mat():
    """The minute track: dim purple ticks; the ones the second hand has passed since the 31-second mark glow orange
    (the countdown trail), the newest brightest; all morph red with the strike."""
    s = vj.Shader("Ticks")
    a, lit = trail_angle(s)
    head = s.mul(lit, s.gauss(a, s.c("Sec"), 4.0))
    col = s.mix(lit, V["face"], V["trail"])
    col = s.mix(s.c("Strike"), col, V["strike"])
    level = s.add(0.55, s.mul(lit, 1.1), s.mul(head, 0.9), s.mul(s.c("Kick"), 0.2), s.mul(s.c("Strike"), 0.7))
    return s.emit(col, s.mul(level, s.core(0.5, 1.4), 1.5 * GAIN))


def trail_angle(s):
    """(angle of this point, clockwise from XII, in 90..450 with XII = 360; lit = 1 behind the second hand)."""
    x, _, z = s.obj_coords()
    a = s.math("DEGREES", s.math("ARCTAN2", x, z))
    a = s.add(a, s.mul(s.math("LESS_THAN", a, 90.0), 360.0))
    lit = s.mul(s.math("GREATER_THAN", a, SEC_START - 2.0), s.math("LESS_THAN", a, s.add(s.c("Sec"), 3.0)))
    return a, lit


def numerals_mat():
    """Bone-white numerals; each one the second hand passes lights orange (VII, VIII ... XII on the strike)."""
    s = vj.Shader("Numerals")
    _, lit = trail_angle(s)
    col = s.mix(lit, V["numerals"], V["trail"])
    col = s.mix(s.c("Strike"), col, V["strike"])
    level = s.add(1.0, s.mul(lit, 0.45), s.mul(s.c("Kick"), 0.22), s.mul(s.c("Strike"), 0.6))
    return s.emit(col, s.mul(level, s.core(0.5, 1.4), 1.2 * GAIN))


def additive_mat(name, gain):
    """Per-object light: color = object color RGB, intensity = object color alpha."""
    s = vj.Shader(name)
    col, alpha, _ = s.obj_info()
    return s.additive(col, s.mul(alpha, s.core(0.6, 1.3), gain * GAIN))


def rose_mat():
    s = vj.Shader("Rose")
    c = s.mix(s.c("Strike"), V["face"], V["strike"])
    lift = s.add(0.55, s.mul(s.c("Build"), 0.45), s.mul(s.c("Strike"), 0.5), s.mul(s.c("Kick"), 0.06))
    return s.emit(c, s.mul(lift, s.core(0.5, 1.3), 0.55 * GAIN))


def gear_mat():
    s = vj.Shader("Gears")
    lift = s.add(0.6, s.mul(s.c("Build"), 0.4), s.mul(s.c("Strike"), 0.4))
    return s.emit(V["gear"], s.mul(lift, s.core(0.5, 1.3), 0.36 * GAIN))


def glow_mat():
    """A soft purple backlight behind the face (additive), lifting with the build and the strike."""
    s = vj.Shader("Backglow")
    x, _, z = s.obj_coords()
    r = s.length2(x, z)
    glow = s.mul(s.exp(s.mul(s.mul(r, r), -1.0 / (6.5 * 6.5))), s.inv(s.smooth(r, 7.0, 9.0)))
    c = s.mix(s.c("Strike"), V["face"], V["strike"])
    lift = s.add(0.7, s.mul(s.c("Build"), 0.35), s.mul(s.c("Strike"), 0.5))
    return s.additive(c, s.mul(glow, lift, 0.045 * GAIN))


def mist_mat():
    """Faint purple mist drifting in front of the clock: 4D noise walked round a circle over the loop (seamless)."""
    s = vj.Shader("Mist")
    x, _, z = s.obj_coords()
    v = s.vec(s.mul(x, 0.11), s.madd(z, 0.16, s.mul(s.c("LoopCos"), 0.35)), s.mul(s.c("LoopSin"), 0.35))
    n = s.noise4(v, s.mul(s.c("LoopSin"), 0.3), scale=1.3, detail=4.0, rough=0.55)
    wisp = s.smooth(n, 0.5, 0.78)
    low = s.inv(s.smooth(z, -2.0, 6.0))                              # thicker low down
    lift = s.add(0.6, s.mul(s.c("Build"), 0.5))
    return s.additive(V["face"], s.mul(wisp, s.madd(low, 0.7, 0.3), lift, 0.08 * GAIN))


def star_mat():
    s = vj.Shader("Stars")
    x, y, z = s.world_pos()
    n = s.noise4(s.vec(s.add(s.mul(x, 0.05), s.c("LoopCos")), s.mul(z, 0.05), s.c("LoopSin")), s.mul(y, 0.01),
                 scale=3.0)
    tw = s.smooth(n, 0.3, 0.7)
    return s.emit((0.8, 0.82, 1.0), s.mul(s.madd(tw, 0.7, 0.25), 0.9 * GAIN))


# ------------------------------------------------------------------ geometry
def strokes_bm(strokes2d, r, y=0.0, segs=8):
    bm = bmesh.new()
    for st in strokes2d:
        g.stroke(bm, g.xz(st, y), r, segs=segs)
    return bm


def ring_bm(radius, r, y=0.0, n=160, segs=8):
    bm = bmesh.new()
    vj.tube(bm, g.xz(g.circle2(radius, n), y), lambda u: r, segs=segs, closed=True)
    return bm


def face_geometry():
    """(rings + tracery + spokes, numerals, minute track) strokes in the clock plane (2D, meters)."""
    lines = []
    lines.append((g.circle2(R, 160), 0.05, True))
    lines.append((g.circle2(R * 0.955, 160), 0.028, True))
    lines.append((g.circle2(R * 0.44, 96), 0.03, True))
    lines.append((g.circle2(R * 0.12, 40), 0.03, True))
    for i in range(12):                                             # gothic tracery: a pointed arch per hour sector
        hw = R * 0.445 * math.sin(math.radians(14.0))               # fits its 30-degree sector
        arch = g.pointed_arch(-hw, hw, 0.0, 0.8, n=8)
        arch = [(x, y + R * 0.445) for x, y in arch]
        lines.append((g.rot2(arch, -30 * i - 15), 0.026, False))
        spoke = [(0.0, R * 0.13), (0.0, R * 0.44)]
        lines.append((g.rot2(spoke, -30 * i), 0.018, False))
        foil = g.circle2(0.13, 20, 0.0, R * 0.545)                   # a small circle in each arch
        lines.append((g.rot2(foil, -30 * i - 15), 0.02, True))
    numerals = []
    for i, num in enumerate(letters.ROMAN):
        h = 0.52
        st = letters.roman(num, h)
        st = [[(x, y - h / 2 + R * 0.74) for x, y in s_] for s_ in st]   # radial: tops toward the rim
        numerals += [g.rot2(s_, -30 * i) for s_ in st]
    ticks = []
    for i in range(60):
        big = i % 5 == 0
        t = [(0.0, R * (0.86 if big else 0.885)), (0.0, R * 0.935)]
        ticks.append((g.rot2(t, -6 * i), 0.034 if big else 0.02))
    return lines, numerals, ticks


def hand_outline(kind):
    """Closed outline of a hand (2D, pointing up the +y axis from the pivot at the origin)."""
    if kind == "hour":
        half = [(0.0, -0.5), (0.13, -0.42), (0.06, -0.24), (0.1, -0.08), (0.075, 0.12), (0.06, 1.0),
                (0.16, 1.12), (0.28, 1.36), (0.25, 1.58), (0.13, 1.66), (0.05, 1.7), (0.09, 1.86), (0.0, 2.15)]
    else:
        half = [(0.0, -0.72), (0.1, -0.62), (0.05, -0.3), (0.08, -0.08), (0.06, 0.2), (0.045, 2.32),
                (0.15, 2.46), (0.045, 2.6), (0.17, 2.78), (0.0, 3.32)]
    return g.mirrored(half)


def hand_objects(name, kind, y, line_mat, fill_mat):
    """An empty at the pivot (rotate it about Y) with the hand's neon outline and black fill as children."""
    root = vj.new_empty(name)
    root.location = (0.0, y, 0.0)
    out = hand_outline(kind)
    bm = bmesh.new()
    g.stroke(bm, g.xz(out), 0.032, segs=8, closed=True)
    if kind == "minute":
        g.stroke(bm, g.xz(g.circle2(0.15, 24, 0.0, 2.46)), 0.026, segs=8, closed=True)
    vj.new_obj(name + "Line", bm, line_mat, root)
    bm = bmesh.new()
    g.fill(bm, g.xz(out, 0.03))
    vj.new_obj(name + "Fill", bm, fill_mat, root)
    return root


def second_hand(name, y, mat):
    root = vj.new_empty(name)
    root.location = (0.0, y, 0.0)
    bm = bmesh.new()
    g.stroke(bm, g.xz([(0.0, -0.92), (0.0, 3.68)]), 0.026, segs=8)
    g.stroke(bm, g.xz(g.circle2(0.14, 24, 0.0, -0.66)), 0.026, segs=8, closed=True)
    g.stroke(bm, g.xz(g.circle2(0.1, 20)), 0.026, segs=8, closed=True)
    vj.new_obj(name + "Line", bm, mat, root)
    return root


def gear_bm(r_root, r_tip, teeth, spokes, hub=0.22, r=0.03):
    bm = bmesh.new()
    g.stroke(bm, g.xz(g.gear_pts(r_root, r_tip, teeth)), r, segs=6, closed=True, joints=False)
    g.stroke(bm, g.xz(g.circle2(r_root * 0.8, 64)), r * 0.8, segs=6, closed=True, joints=False)
    g.stroke(bm, g.xz(g.circle2(hub, 24)), r, segs=6, closed=True, joints=False)
    for i in range(spokes):
        a = 2 * math.pi * i / spokes
        p0 = (hub * math.cos(a), hub * math.sin(a))
        p1 = (r_root * 0.8 * math.cos(a), r_root * 0.8 * math.sin(a))
        g.stroke(bm, g.xz([p0, p1]), r * 0.8, segs=6, joints=False)
    return bm


def rose_bm():
    """The rose window behind the clock: an inner circle, 12 lancet petals, small circles between them, an outer
    circle. 12-fold, so turning it 30 degrees per loop is seamless."""
    bm = bmesh.new()
    r_in, r_out = 5.0, 7.6
    for rad, rr in ((r_in, 0.04), (r_out, 0.05), (r_out + 0.35, 0.03)):
        g.stroke(bm, g.xz(g.circle2(rad, 192)), rr, segs=6, closed=True, joints=False)
    for i in range(12):
        half_w = r_in * math.sin(math.radians(11.5))
        petal = g.pointed_arch(-half_w, half_w, 0.0, (r_out - r_in) * 0.85, n=10)
        petal = [(x, y + r_in * math.cos(math.radians(11.5))) for x, y in petal]
        g.stroke(bm, g.xz(g.rot2(petal, 30 * i)), 0.035, segs=6)
        circ = g.circle2(0.42, 24, 0.0, r_out - 0.62)
        g.stroke(bm, g.xz(g.rot2(circ, 30 * i + 15)), 0.03, segs=6, closed=True, joints=False)
    return bm


GEARS = [  # center (x, z), root, tip radius, teeth, spokes, ratio to the second hand
    ((1.55, -1.05), 1.25, 1.42, 28, 6, -0.30),
    ((-1.65, 0.95), 1.0, 1.15, 22, 5, 0.38),
    ((0.6, 2.05), 0.6, 0.72, 14, 4, -0.75),
    ((-0.75, -2.2), 0.75, 0.88, 16, 5, 0.6),
    ((2.55, 1.35), 0.5, 0.6, 12, 4, 0.9),
]


# ------------------------------------------------------------------ scene
def build():
    scene = vj.reset_scene()
    vj.clock_from(signals)
    ext = vj.EXT

    lines, numerals, ticks = face_geometry()
    bm = bmesh.new()
    for pts, r, closed in lines:
        g.stroke(bm, g.xz(pts), r, segs=8, closed=closed, joints=not closed)
    vj.new_obj("FaceLines", bm, face_mat("Face", V["face"], 1.6, kick=0.25))
    vj.new_obj("Numerals", strokes_bm(numerals, 0.034), numerals_mat())
    bm = bmesh.new()
    for pts, r in ticks:
        g.stroke(bm, g.xz(pts), r, segs=6)
    vj.new_obj("Ticks", bm, ticks_mat())

    black = vj.black_mat()
    hand_line = face_mat("HandLine", V["numerals"], 1.35, kick=0.1, strike_gain=0.4)
    hour = hand_objects("HourHand", "hour", -0.25, hand_line, black)
    minute = hand_objects("MinuteHand", "minute", -0.38, hand_line, black)
    sec_m = vj.Shader("SecondHand")
    sec_m = sec_m.emit(V["strike"], sec_m.mul(sec_m.add(1.0, sec_m.mul(sec_m.c("Strike"), 0.5)),
                                              sec_m.core(0.5, 1.4), 2.4 * GAIN))
    second = second_hand("SecondHand", -0.5, sec_m)
    cap = vj.new_obj("PivotCap", vj.disc_bm(0.12, 24), black)
    cap.location = (0.0, -0.56, 0.0)
    vj.keyed(second, "rotation_euler", [(f, (0.0, math.radians(sec_angle(f)), 0.0)) for f in ext])
    vj.keyed(minute, "rotation_euler", [(f, (0.0, math.radians(min_angle(f)), 0.0)) for f in ext])
    vj.keyed(hour, "rotation_euler", [(f, (0.0, math.radians(359.5 + (min_angle(f) - MIN_AT) / 12.0), 0.0))
                                      for f in ext])

    gm = gear_mat()
    for i, ((cx, cz), r0, r1, teeth, spokes, ratio) in enumerate(GEARS):
        ob = vj.new_obj(f"Gear{i}", gear_bm(r0, r1, teeth, spokes), gm)
        ob.location = (cx, 1.3, cz)
        phase = 360.0 / teeth * 0.37 * i
        vj.keyed(ob, "rotation_euler", [(f, (0.0, math.radians(phase + ratio * (sec_angle(f) - 360.0)), 0.0))
                                        for f in ext])

    rose = vj.new_obj("Rose", rose_bm(), rose_mat())
    rose.location = (0.0, 3.2, 0.0)
    vj.keyed(rose, "rotation_euler", [(f, (0.0, math.radians(-30.0 * f / vj.FRAMES), 0.0)) for f in (-30, vj.FRAMES + 30)])

    glow = vj.new_obj("Backglow", vj.quad_bm(22.0, 22.0), glow_mat())
    glow.location = (0.0, 6.0, 0.0)
    mist = vj.new_obj("Mist", vj.quad_bm(24.0, 14.0), mist_mat())
    mist.location = (0.0, -3.0, 0.0)

    rnd = random.Random(7)
    bm = bmesh.new()
    for _ in range(170):
        x, z = rnd.uniform(-36, 36), rnd.uniform(-20, 20)
        if math.hypot(x / 1.0, z / 1.0) < 16.0:                         # none behind the clock face itself
            continue
        bmesh.ops.create_icosphere(bm, subdivisions=1, radius=rnd.uniform(0.05, 0.11),
                                   matrix=Matrix.Translation((x, 62.0, z)))
    vj.new_obj("Stars", bm, star_mat())

    toll = vj.new_obj("TollRing", ring_bm(R, 0.06), additive_mat("Toll", 2.2))
    toll.location = (0.0, -0.15, 0.0)
    toll_keys, toll_scale = [], []
    for f in ext:
        t = f % vj.FRAMES
        if t < 2.0 * vj.FPB:                                       # rolls out after the strike
            u = t / (2.0 * vj.FPB)
            sc = 1.0 + 1.5 * (1.0 - (1.0 - u) ** 2.6)
            a = math.exp(-t / 5.5)
        else:                                                      # charging on the rim during the swell
            sc, a = 1.0, strike(f) if t >= vj.BEAT_F[vj.BEATS - 2] else 0.0
        toll_keys.append((f, (*V["strike"], a)))
        toll_scale.append((f, (sc, 1.0, sc)))
    vj.keyed(toll, "color", toll_keys)
    vj.keyed(toll, "scale", toll_scale)

    cam = vj.camera(scene, lens=50.0, clip=(0.5, 300.0))
    loc, rot, lens = [], [], []
    for f in ext:
        a = 2 * math.pi * f / vj.FRAMES
        p = Vector((0.8 * math.sin(a), -CAM_D, 0.4 * math.sin(2 * a + 0.7)))
        loc.append((f, tuple(p)))
        rot.append((f, tuple(vj.look_at(p, (0.0, 0.0, 0.05), roll=0.8 * math.sin(a + 1.3)))))
        lens.append((f, 50.0 * (1.0 + 0.005 * vj.clock(f)["kick"] + 0.02 * strike(f))))
    vj.keyed(cam, "location", loc)
    vj.keyed(cam, "rotation_euler", rot)
    vj.keyed(cam.data, "lens", lens)
    return scene


scene = build()
vj.standard_render(scene)
vj.finish(scene, f"witching_hour_{VNAME}")
