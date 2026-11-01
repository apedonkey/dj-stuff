"""GEIGER SCOPE - REACTOR VJ loop. 8 bars, seamless, 1920x1080 @ 30 fps; tempo from vjkit (140 BPM half-time = 411
frames).

A retro CRT oscilloscope on a black instrument panel, all of it our own line work: a bulging phosphor face (a slight
barrel curve) with scanlines and a 10 x 8 graticule, a rate meter, knobs and labels in our monoline letters.
  Traces   every accent (half-time: the kick and the snare) triggers a sweep: the beam writes a decay click, a spike
           that rings out, on the accent itself, then the baseline with a few small background clicks. The phosphor
           holds each trace and lets it fade, so the last sweep still glows behind the new one.
  Meter    the rate meter's needle kicks up with every click and sinks back; the count LED blinks with them.
  Trefoil  section B: decay sparks flicker up over bar 4, then on bar 5's downbeat they fly together into the
           radiation trefoil, a blade per accent and the centre last; the full symbol swells in on bar 7's downbeat,
           holds, and decays apart over bar 8, gone before the seam.
Variants (palette / camera / density): green (P1 phosphor, front view), amber (dual trace: the clicks and their
counter's staircase, a three-quarter view), cyan (storage-scope persistence, close up, a denser trefoil).
No strobing: the clicks are thin lines, the halo and LED swell over two frames, every fade is a beat or more.

  blender.exe -b --factory-startup --python geiger_scope.py -- --variant green --frames 0,103,320 [--pct 50]
  blender.exe -b --factory-startup --python geiger_scope.py -- --variant green --all --seam DIR [--out DIR]
"""
import math
import os
import random
import sys

import bmesh
import bpy
from mathutils import Vector

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import vjkit as vj  # noqa: E402
import rx_science as rx  # noqa: E402
from vjkit import ALARM, AMBER, COOLANT, LASER, STEEL, WHITE  # noqa: E402

# phosphor colour and gain (equal-looking brightness across hues), the trace's persistence (frames), dual trace, the
# trefoil's particle density, the camera (position, aim, lens mm)
VARIANTS = {
    "green": dict(phos=LASER, phos_gain=0.85, led=AMBER, persist=9.0, dual=False, density=1.0,
                  cam=((0.95, -9.0, 0.0), (0.95, 0.0, 0.0), 35.0)),
    "amber": dict(phos=AMBER, phos_gain=1.15, led=LASER, persist=12.0, dual=True, density=1.0,
                  cam=((-2.3, -8.5, 0.75), (0.85, 0.0, -0.05), 35.0)),
    "cyan": dict(phos=COOLANT, phos_gain=0.9, led=AMBER, persist=26.0, dual=False, density=1.5,
                 cam=((0.0, -7.0, 0.0), (0.0, 0.0, 0.0), 35.0)),
}
VNAME, V = vj.variant(VARIANTS)
GAIN = float(vj.arg("--gain", 1.0))
PG = V["phos_gain"] * GAIN

DIV = 0.5                                      # one graticule division (m): 10 x 8 divisions
GW, GH = 10 * DIV, 8 * DIV                     # the graticule
SW, SH, SR = 5.5, 4.5, 0.45                    # the glass: a rounded rectangle
BULGE = 0.45                                   # the face bulges toward the viewer by this much at its centre
C2 = (SW / 2) ** 2 + (SH / 2) ** 2
X_LEFT, X_TRIG = -GW / 2, -GW / 2 + DIV        # the sweep starts at the left edge; the trigger is one division in
SWEEP_F = 1.55 * vj.FPB                        # frames for the beam to cross the graticule
VEL = GW / SWEEP_F                             # beam speed (m per frame)
PRE = (X_TRIG - X_LEFT) / VEL                  # the beam starts this many frames early: the spike lands on the accent
LIFT = 0.012                                   # traces float this far in front of the glass
RISE = 0.035                                   # a click's rise (m of sweep): a near-vertical spike
NOISE = [(0.018, 3.1), (0.012, 7.3), (0.007, 13.7)]   # the baseline's grass: (amplitude m, cycles per m)
Z1, A1 = (-1.35, 0.75) if V["dual"] else (-0.9, 1.0)  # channel 1's baseline and spike scale
Z2 = 0.55                                      # channel 2's (the counter staircase) baseline
TREF_C, TREF_R0 = (0.0, 0.15), 0.3             # the trefoil: centre and disc radius (blades out to 5 r0)
PANEL_Y = -0.12                                # the panel's line work, just in front of the glass's rim


def b2f(b):
    """Frame of beat position b (fractional beats allowed), within the loop's grid."""
    k = int(math.floor(b))
    return vj.BEAT_F[k] + (b - k) * (vj.BEAT_F[k + 1] - vj.BEAT_F[k])


# ------------------------------------------------------------------ the face
def bulge_y(x, z):
    return -BULGE * max(0.0, 1.0 - (x * x + z * z) / C2)


def scr(x, z, lift=LIFT):
    """A point on the phosphor face (x right, z up), lifted toward the viewer."""
    return Vector((x, bulge_y(x, z) - lift, z))


def screen_bm(nx=132, nz=108):
    bm = bmesh.new()
    rows = [[bm.verts.new(scr(-SW / 2 + SW * i / nx, -SH / 2 + SH * j / nz, 0.0)) for i in range(nx + 1)]
            for j in range(nz + 1)]
    for j in range(nz):
        for i in range(nx):
            bm.faces.new((rows[j][i], rows[j][i + 1], rows[j + 1][i + 1], rows[j + 1][i]))
    return bm


# ------------------------------------------------------------------ timing
def ramp(b, b0, b1):
    return vj.ease((b - b0) / (b1 - b0))


def b_amount(f):
    """Section B's weight 0..1: in over the fill into bar 5, out over the last two beats (0 at the seam)."""
    b = vj.beatpos(f % vj.FRAMES)
    return ramp(b, vj.HALF - 2, vj.HALF) * (1.0 - ramp(b, vj.BEATS - 2, vj.BEATS))


def tref_level(f):
    """The trefoil's outline: swells in over the beat before bar 7, holds, decays apart from beat 28."""
    b = vj.beatpos(f % vj.FRAMES)
    return ramp(b, 23.0, 24.0) * (1.0 - ramp(b, 28.0, 29.5))


def accent_env(f, attack, decay):
    """Sum over the accents of amp * (2-frame-ish attack) * exp decay: a click response, periodic."""
    v = 0.0
    for af, amp in vj.accent_frames():
        t = (f - af) % vj.FRAMES
        if t < 8 * decay:
            v += amp * min(1.0, (t + 1) / (attack + 1)) * math.exp(-t / decay)
    return v


def meter_level(f):
    """The rate meter: the needle kicks up with each click (a little overshoot) and sinks back; higher in B."""
    v = 0.28 + 0.16 * b_amount(f)
    for af, amp in vj.accent_frames():
        t = (f - af - 1) % vj.FRAMES
        if t < 60:
            v += 0.3 * amp * (1.0 - math.exp(-t / 1.6)) * math.exp(-t / 16.0) * (1.0 + 0.12 * math.sin(t / 2.2))
    return min(v, 1.0)


def signals(f):
    c = vj.clock(f)
    s = {"F": float(f), "Kick": c["kick"], "Click": accent_env(f, 1.0, 6.0), "Swell": vj.swell(f),
         "Bamt": b_amount(f), "Tref": tref_level(f), "TraceGain": 1.0 - 0.3 * b_amount(f)}
    s.update(vj.loop_signals(f))
    return s


# ------------------------------------------------------------------ the traces
def pulse_shape(xp, tau, lam):
    """A click as the scope draws it: a near-vertical rise over RISE, then a ringing decay."""
    if xp < -RISE:
        return 0.0
    if xp < 0.0:
        return vj.ease((xp + RISE) / RISE)
    return math.exp(-xp / tau) * math.cos(2 * math.pi * xp / lam)


def make_sweeps():
    rnd = random.Random(29)
    out = []
    for k in range(0, vj.BEATS, vj.ACC):
        kick = k % 4 == 0 or not vj.HALFTIME
        clicks = sorted((rnd.uniform(X_TRIG + 1.1, GW / 2 - 0.2), rnd.uniform(0.12, 0.55))
                        for _ in range(rnd.choice((1, 2, 2, 3))))
        out.append(dict(start=vj.BEAT_F[k] - PRE, amp=(2.35 if kick else 2.0) * rnd.uniform(0.92, 1.05),
                        clicks=clicks, ph=[rnd.uniform(0, 2 * math.pi) for _ in NOISE]))
    return out


def ch1_z(x, sw):
    z = Z1 + A1 * sw["amp"] * pulse_shape(x - X_TRIG, 0.5, 1.15)
    for xc, a in sw["clicks"]:
        z += A1 * a * pulse_shape(x - xc, 0.15, 0.42)
    return z + sum(n * math.sin(2 * math.pi * fr * x + p) for (n, fr), p in zip(NOISE, sw["ph"]))


def ch2_z(x, sw):
    """Channel 2: the counter's staircase, a step up per click (it resets with each sweep)."""
    z = Z2
    for xc, a in [(X_TRIG, 0.42 * sw["amp"] / 2.2)] + [(xc, 0.3 * a) for xc, a in sw["clicks"]]:
        z += a * vj.ease((x - xc + RISE) / RISE)
    return z + 0.4 * sum(n * math.sin(2 * math.pi * fr * x + p + 1.0) for (n, fr), p in zip(NOISE, sw["ph"]))


def trace_bm(sw, zfun):
    xs = {round(X_LEFT + i * 0.012, 6) for i in range(int(round(GW / 0.012)) + 1)}
    for xp in [X_TRIG] + [c[0] for c in sw["clicks"]]:
        xs.update(xp - RISE + RISE * i / 8 for i in range(9))
    xs = sorted(x for x in xs if X_LEFT <= x <= GW / 2)
    bm = bmesh.new()
    rx.stroke(bm, [scr(x, zfun(x, sw)) for x in xs], 0.011, segs=6)
    return bm


# ------------------------------------------------------------------ the trefoil's particles
def particle_plan():
    """[(target (x, z), group, order 0..1)]: the outline of each blade and the centre disc, sampled evenly."""
    outlines = rx.trefoil(TREF_R0)
    n_blade, n_disc = int(round(50 * V["density"])), int(round(24 * V["density"]))
    plan = []
    for g, outline in enumerate(outlines[1:]):                 # blades: bottom, upper right, upper left
        pts = rx.sample_outline(outline, n_blade)
        plan += [((TREF_C[0] + x, TREF_C[1] + z), g, i / n_blade) for i, (x, z) in enumerate(pts)]
    pts = rx.sample_outline(outlines[0], n_disc)
    plan += [((TREF_C[0] + x, TREF_C[1] + z), 3, i / n_disc) for i, (x, z) in enumerate(pts)]
    return plan


def particle_track(rnd, target, group, order):
    """Per frame (frame -> ((x, z), alpha)) for one particle over the loop."""
    tx, tz = target
    sx, sz = rnd.uniform(-GW / 2 + 0.1, GW / 2 - 0.1), rnd.uniform(-GH / 2 + 0.1, GH / 2 - 0.1)
    vx, vz = rnd.uniform(-0.06, 0.06), rnd.uniform(-0.06, 0.06)            # drift (m per beat)
    t_app = b2f(rnd.uniform(12.3, vj.HALF - 0.4))
    t_go = vj.BEAT_F[vj.HALF + 2 * group] + 4.0 * order                     # a blade assembles in a sweep
    fly = 1.1 * vj.FPB
    t_off = b2f(28.0 + rnd.uniform(0.0, 1.6))
    away = rnd.uniform(0.45, 0.95)
    dx, dz = tx - TREF_C[0], tz - TREF_C[1]
    dl = math.hypot(dx, dz) or 1.0
    ang = rnd.uniform(-0.5, 0.5)
    ox, oz = (dx * math.cos(ang) - dz * math.sin(ang)) / dl, (dx * math.sin(ang) + dz * math.cos(ang)) / dl
    bow = rnd.uniform(-0.35, 0.35)
    tw = rnd.uniform(0, 2 * math.pi)
    track = {}
    for f in vj.EXT:
        ff = f % vj.FRAMES
        if ff < t_app or ff >= t_off + vj.FPB:
            track[f] = ((sx, sz), 0.0)
            continue
        wx, wz = sx + vx * (ff - t_app) / vj.FPB, sz + vz * (ff - t_app) / vj.FPB
        if ff < t_go:                                                       # a decay spark, waiting
            a = min(1.0, (ff - t_app) / 3.0) * (0.55 + 0.2 * math.sin(tw + ff * 0.45))
            track[f] = ((wx, wz), a)
            continue
        if ff < t_go + fly:                                                 # flying home (eased out)
            u = (ff - t_go) / fly
            e = 1.0 - (1.0 - u) ** 3
            px, pz = wx + (tx - wx) * e, wz + (tz - wz) * e
            nx, nz = -(tz - wz), tx - wx
            nl = math.hypot(nx, nz) or 1.0
            s = bow * math.sin(math.pi * e)
            track[f] = ((px + nx / nl * s, pz + nz / nl * s), 1.0)
            continue
        if ff < t_off:                                                      # in place (embers under the outline)
            j = 0.012 * math.sin(tw + ff * 0.7)
            track[f] = ((tx + j, tz - j), 0.9 - 0.6 * tref_level(ff))
            continue
        u = (ff - t_off) / vj.FPB                                           # decaying apart
        e = u * u
        track[f] = ((tx + ox * away * e, tz + oz * away * e), (1.0 - vj.ease(u)) * 0.95)
    return track


# ------------------------------------------------------------------ materials
def screen_mat():
    """The phosphor face: a faint glow (vignetted), the graticule, a halo where each click lands, scanlines; the
    glass is a rounded rectangle (outside it, black)."""
    s = vj.Shader("Screen")
    x, _, z = s.obj_coords()
    ax, az = s.math("ABSOLUTE", x), s.math("ABSOLUTE", z)
    qx, qz = s.sub(ax, SW / 2 - SR), s.sub(az, SH / 2 - SR)
    outside = s.length2(s.math("MAXIMUM", qx, 0.0), s.math("MAXIMUM", qz, 0.0))
    sdf = s.sub(s.add(outside, s.math("MINIMUM", s.math("MAXIMUM", qx, qz), 0.0)), SR)
    glass = s.inv(s.smooth(sdf, -0.05, 0.0))
    inside = s.mul(s.inv(s.smooth(ax, GW / 2 + 0.004, GW / 2 + 0.03)),
                   s.inv(s.smooth(az, GH / 2 + 0.004, GH / 2 + 0.03)))
    grid = s.math("MAXIMUM", rx.lines(s, x, DIV, 0.006), rx.lines(s, z, DIV, 0.006))
    ticks = s.math("MAXIMUM", s.mul(rx.lines(s, x, DIV / 5, 0.005), s.inv(s.smooth(az, 0.035, 0.06))),
                   s.mul(rx.lines(s, z, DIV / 5, 0.005), s.inv(s.smooth(ax, 0.035, 0.06))))
    grat = s.mul(s.math("MAXIMUM", grid, ticks), inside)
    vign = s.inv(s.mul(s.add(s.mul(x, x), s.mul(z, z)), 0.045))
    base = s.mul(vign, s.add(0.010, s.mul(s.c("Swell"), 0.005), s.mul(s.c("Bamt"), 0.004)))
    hx = s.mul(s.sub(x, X_TRIG), 1.0 / 0.35)
    hz = s.mul(s.sub(z, Z1 + 0.5 * A1 * 2.2), 1.0 / (0.55 * A1 * 2.2))
    halo = s.mul(s.exp(s.mul(s.add(s.mul(hx, hx), s.mul(hz, hz)), -1.0)), s.c("Click"), 0.06)
    scan = s.madd(s.math("COSINE", s.mul(z, 2 * math.pi / 0.036)), 0.16, 0.84)
    level = s.mul(s.add(s.mul(grat, 0.11), base, halo), scan, glass)
    return s.emit(V["phos"], s.mul(level, 1.25 * PG))


def trace_mat(name, gain):
    """Per-object Object.color R = the sweep's start frame + 16. The beam writes the trace from the left at VEL; each
    point glows hottest as the beam writes it and fades with the phosphor's persistence; points the beam has not
    reached yet are not drawn (fully transparent)."""
    s = vj.Shader(name)
    col, _, _ = s.obj_info()
    start = s.sub(s.xyz(col)[0], 16.0)
    age = s.math("MODULO", s.add(s.sub(s.c("F"), start), 2.0 * vj.FRAMES), float(vj.FRAMES))
    x, _, _ = s.obj_coords()
    beam = s.madd(age, VEL, X_LEFT)
    drawn = s.inv(s.smooth(x, s.sub(beam, 0.012), s.add(beam, 0.012)))
    since = s.math("MAXIMUM", s.sub(age, s.mul(s.sub(x, X_LEFT), 1.0 / VEL)), 0.0)
    persist = s.exp(s.mul(since, -1.0 / V["persist"]))
    spot = s.exp(s.mul(s.mul(since, since), -0.5))
    lvl = s.mul(drawn, s.add(s.mul(persist, 0.9), s.mul(spot, 1.0)), s.c("TraceGain"))
    c = s.mix(s.mul(spot, 0.45), V["phos"], WHITE)
    return s.additive(c, s.mul(lvl, s.core(0.55, 1.3), gain * PG))


def particle_mat():
    s = vj.Shader("Sparks")
    _, alpha, _ = s.obj_info()
    c = s.mix(0.3, V["phos"], WHITE)
    return s.additive(c, s.mul(alpha, s.add(1.0, s.mul(s.c("Kick"), 0.3)), 1.5 * PG))


def tref_mat():
    s = vj.Shader("Trefoil")
    lift = s.add(0.85, s.mul(s.c("Kick"), 0.3))
    c = s.mix(0.2, V["phos"], WHITE)
    return s.additive(c, s.mul(s.c("Tref"), lift, s.core(0.55, 1.3), 1.3 * PG))


def line_mat(name, col, strength):
    s = vj.Shader(name)
    return s.emit(col, s.mul(s.core(0.5, 1.3), strength * GAIN))


def led_mat():
    s = vj.Shader("Led")
    return s.emit(V["led"], s.mul(s.add(0.35, s.mul(s.c("Click"), 1.4)), 1.6 * GAIN))


# ------------------------------------------------------------------ the panel
def strokes_bm(strokes2d, r, y=PANEL_Y, closed=False):
    bm = bmesh.new()
    for st in strokes2d:
        rx.stroke(bm, rx.xz(st, y), r, segs=6, closed=closed, joints=not closed)
    return bm


def text2d(text, h, cx, cz, track=0.25):
    return [[(x + cx, y + cz - h / 2) for x, y in st] for st in rx.word_strokes(text, h, track=track, gap=0)]


def knob2d(cx, cz, ang):
    out = [rx.circle2(0.26, 48, cx, cz), rx.circle2(0.17, 40, cx, cz)]
    a = math.radians(90 - ang)
    out.append([(cx + 0.05 * math.cos(a), cz + 0.05 * math.sin(a)), (cx + 0.15 * math.cos(a), cz + 0.15 * math.sin(a))])
    for i in range(11):
        t = math.radians(90 + 135 - 27 * i)
        out.append([(cx + 0.31 * math.cos(t), cz + 0.31 * math.sin(t)),
                    (cx + 0.36 * math.cos(t), cz + 0.36 * math.sin(t))])
    return out


MET_C, MET_R = (4.2, 1.05), 0.75               # the rate meter's pivot and scale radius


def build_panel():
    closed = [rx.rounded_rect(SW + 0.25, SH + 0.25, SR + 0.1), rx.rounded_rect(SW + 0.55, SH + 0.55, SR + 0.25),
              rx.rounded_rect(1.85, 1.3, 0.12, cx=MET_C[0], cy=MET_C[1] + 0.42)]
    vj.new_obj("Bezel", strokes_bm(closed, 0.014, closed=True), line_mat("Bezel", STEEL, 0.55))
    ls = [[(3.12, -2.45), (3.12, 2.45)]]
    ls += [rx.arc2(MET_C[0], MET_C[1], MET_R, 40, 140, 30)]
    for i in range(11):
        t = math.radians(140 - 10 * i)
        r1 = MET_R + (0.13 if i % 5 == 0 else 0.08)
        ls.append([(MET_C[0] + MET_R * math.cos(t), MET_C[1] + MET_R * math.sin(t)),
                   (MET_C[0] + r1 * math.cos(t), MET_C[1] + r1 * math.sin(t))])
    for cx, cz, ang, label, lz in ((3.7, 0.05, -40, "TIME", -0.42), (4.7, 0.05, 25, "VOLTS", -0.42),
                                   (4.2, -1.05, 60, "TRIG", -1.52)):
        ls += knob2d(cx, cz, ang)
        ls += text2d(label, 0.13, cx, lz)
    ls += text2d("RATE", 0.12, MET_C[0], MET_C[1] + 0.33)
    vj.new_obj("Panel", strokes_bm(ls, 0.011), line_mat("Panel", STEEL, 0.42))
    vj.new_obj("RedZone", strokes_bm([rx.arc2(MET_C[0], MET_C[1], MET_R + 0.045, 40, 56, 8)], 0.022),
               line_mat("RedZone", ALARM, 0.9))
    led = vj.new_obj("Led", vj.disc_bm(0.065, 24), led_mat())
    led.location = (3.5, PANEL_Y, -1.95)
    vj.new_obj("LedRing", strokes_bm([rx.circle2(0.1, 32, 3.5, -1.95)], 0.01, closed=True),
               line_mat("LedRing", STEEL, 0.42))
    needle = vj.new_obj("Needle", strokes_bm([[(0.0, -0.08), (0.0, MET_R + 0.05)]], 0.012, y=0.0),
                        line_mat("Needle", (0.9, 0.92, 0.95), 0.75))
    needle.location = (MET_C[0], PANEL_Y - 0.02, MET_C[1])
    vj.keyed(needle, "rotation_euler", [(f, (0.0, math.radians(-50.0 + 100.0 * meter_level(f)), 0.0))
                                        for f in vj.EXT])


# ------------------------------------------------------------------ scene
def build():
    scene = vj.reset_scene()
    vj.clock_from(signals)
    rnd = random.Random(7)
    vj.new_obj("Screen", screen_bm(), screen_mat())

    tm = trace_mat("Trace", 1.15)
    sweeps = make_sweeps()
    for k, sw in enumerate(sweeps):
        ob = vj.new_obj(f"Trace{k:02d}", trace_bm(sw, ch1_z), tm)
        ob.color = (sw["start"] + 16.0, 0.0, 0.0, 1.0)
    if V["dual"]:
        tm2 = trace_mat("Trace2", 0.8)
        for k, sw in enumerate(sweeps):
            ob = vj.new_obj(f"TraceB{k:02d}", trace_bm(sw, ch2_z), tm2)
            ob.color = (sw["start"] + 16.0, 0.0, 0.0, 1.0)

    bm = bmesh.new()
    for outline in rx.trefoil(TREF_R0):
        pts = rx.resample(rx.xz([(TREF_C[0] + x, TREF_C[1] + z) for x, z in outline + outline[:1]]), 0.03)
        rx.stroke(bm, [scr(p.x, p.z, LIFT * 1.5) for p in pts], 0.018, segs=6)
    vj.new_obj("Trefoil", bm, tref_mat())

    pm = particle_mat()
    dot = vj.finish_bm(vj.disc_bm(0.028, 10), smooth=False, name="Spark")
    for i, (target, group, order) in enumerate(particle_plan()):
        ob = vj.mesh_obj(f"Spark{i:03d}", dot, pm)
        tr = particle_track(rnd, target, group, order)
        vj.keyed(ob, "location", [(f, tuple(scr(*tr[f][0], lift=LIFT * 2))) for f in vj.EXT])
        vj.keyed(ob, "color", [(f, (1.0, 1.0, 1.0, tr[f][1])) for f in vj.EXT])

    build_panel()

    pos, aim, lens = V["cam"]
    pos, aim = Vector(pos), Vector(aim)
    cam = vj.camera(scene, lens=lens, clip=(0.5, 100.0))
    loc, rot = [], []
    for f in vj.EXT:
        a = 2 * math.pi * f / vj.FRAMES
        push = (aim - pos).normalized() * (0.45 * b_amount(f))
        p = pos + Vector((0.12 * math.sin(a), 0.0, 0.07 * math.sin(2 * a + 0.5) + 0.03 * vj.jolt(f))) + push
        t = aim + Vector((0.05 * math.sin(a + 1.0), 0.0, 0.03 * math.sin(2 * a)))
        loc.append((f, tuple(p)))
        rot.append((f, tuple(vj.look_at(p, t, roll=0.3 * math.sin(a + 0.7)))))
    vj.keyed(cam, "location", loc)
    vj.keyed(cam, "rotation_euler", rot)
    return scene


scene = build()
vj.standard_render(scene)
vj.finish(scene, f"geiger_scope_{VNAME}")
