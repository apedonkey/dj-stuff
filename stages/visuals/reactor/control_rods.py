"""CONTROL RODS - REACTOR VJ loop. 8 bars, seamless, 1920x1080 @ 30 fps; tempo from vjkit (140 BPM half-time =
411 frames).

A side cut-away of the core: a glowing band of fuel across the lower third, dozens of vertical control rods (black,
neon-edged) hanging into it from the dark upper plenum, each topped by a hazard-chevron cap and a drive shaft. The rods
come in four banks (every fourth rod). The camera tracks slowly sideways, two bank periods per loop, so frame 411
equals frame 0 (everything, the textures too, repeats every bank period).
Beat hooks: section A (bars 1-4): a bank slams down on every kick (an accelerating fall that lands on the beat, a
small rebound, a camera thump, a hot spot at each tip) and another withdraws on every snare; the gaps glow hotter as
rods lift (the fuel under a rod runs cooler). Section B (bars 5-8, the drop): every rod slams in on the kick and half
of them pull out on the snare, like pistons; the camera thumps harder. The fuel swells into each section hit.
Variants: amber (amber fuel, amber chevrons), cyan (a Cherenkov-blue core, coolant-cyan edges, a denser and wider view
from slightly below), red (a red-hot core, red chevrons, a closer, wider-angle view from slightly above).
No strobing: rods are motion, not light; the band's columns change gently (a rod in still lets 40% through).

  blender.exe -b --factory-startup --python control_rods.py -- --variant amber --frames 0,206,240 [--pct 25]
  blender.exe -b --factory-startup --python control_rods.py -- --variant amber --all --seam DIR [--mblur]
"""
import math
import os
import sys

import bmesh
import bpy
from mathutils import Vector

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import vjkit as vj  # noqa: E402
import rx_core as rx  # noqa: E402
from vjkit import ALARM, AMBER, CHERENKOV, COOLANT, EMBER, HOT, STEEL  # noqa: E402

# ramp: fuel heat -> colour (only the hottest specks reach the top stop); rim: rod edges; cap: chevron colour;
# cam: (distance m, lens mm, pitch deg up, height of the view centre m); spacing: rod pitch (m); band: fuel
# brightness
VARIANTS = {
    "amber": dict(ramp=[(0.0, (0.0, 0.0, 0.0)), (0.3, (0.22, 0.02, 0.0)), (0.55, EMBER), (0.8, AMBER), (1.0, HOT)],
                  rim=STEEL, cap=AMBER, plenum=(0.02, 0.1, 0.35), cam=(16.0, 30.0, 0.0, 5.4), spacing=0.72,
                  rod_r=0.15, band=1.0, rim_gain=0.9),
    "cyan": dict(ramp=[(0.0, (0.0, 0.0, 0.0)), (0.3, (0.0, 0.04, 0.22)), (0.55, CHERENKOV), (0.82, (0.2, 0.6, 1.0)),
                       (1.0, (0.6, 0.85, 1.0))],
                 rim=COOLANT, cap=AMBER, plenum=(0.15, 0.04, 0.0), cam=(19.0, 30.0, 4.0, 5.6), spacing=0.6,
                 rod_r=0.13, band=0.95, rim_gain=0.55),
    "red": dict(ramp=[(0.0, (0.0, 0.0, 0.0)), (0.3, (0.22, 0.0, 0.0)), (0.55, ALARM), (0.8, EMBER),
                      (1.0, (1.0, 0.42, 0.1))],
                rim=STEEL, cap=ALARM, plenum=(0.1, 0.02, 0.3), cam=(12.8, 24.0, -3.0, 5.3), spacing=0.8,
                rod_r=0.17, band=1.25, rim_gain=0.9),
}
VNAME, V = vj.variant(VARIANTS)
GAIN = float(vj.arg("--gain", 1.0))

S = V["spacing"]                          # rod pitch: rod i stands at x = i * S, in bank i mod 4
PERIOD = 4 * S                            # the scene repeats every bank period
TRACK = 2 * PERIOD                        # camera travel per loop
TIP_IN, TRAVEL = 0.9, 3.4                 # rod tip height fully inserted (the bottom of the fuel), withdrawal (m)
POISON_L, CAP_L = 4.4, 0.9                # the absorber section, the chevron cap above it
BAND = (0.8, 4.6)                         # the fuel band (z)
COLD = 0.4                                # fuel glow above an inserted rod's tip (share of the hot glow)
SLAM_F, PULL_F = 3, 12                    # frames of a slam (lands on the accent) and of a withdrawal (starts on it)
# (accent, banks, kind): A = one bank in per kick, one out per snare; B = all in on the kick, half out on the snare
EVENTS = [(0, "A", "slam"), (1, "C", "pull"), (2, "B", "slam"), (3, "D", "pull"), (4, "C", "slam"),
          (5, "A", "pull"), (6, "D", "slam"), (7, "B", "pull"),
          (8, "AB", "slam"), (9, "CD", "pull"), (10, "CD", "slam"), (11, "AB", "pull"), (12, "AB", "slam"),
          (13, "CD", "pull"), (14, "CD", "slam"), (15, "AB", "pull")]
BANK_NAMES = "ABCD"


# ------------------------------------------------------------------ choreography
def insertion(b, f):
    """1 = bank b fully inserted, 0 = withdrawn, at frame f. Slams accelerate down over SLAM_F frames and land on the
    accent (then a small rebound); withdrawals start on the accent fast and ease to a stop over PULL_F frames."""
    f %= vj.FRAMES
    best = None
    for k, banks, kind in EVENTS:
        if BANK_NAMES[b] not in banks:
            continue
        start = rx.acc_frame(k) - (SLAM_F if kind == "slam" else 0)
        dt = (f - start) % vj.FRAMES
        if best is None or dt < best[0]:
            best = (dt, kind)
    dt, kind = best
    if kind == "slam":
        if dt < SLAM_F:
            return (dt / SLAM_F) ** 2
        t = dt - SLAM_F
        return 1.0 - (0.07 * math.sin(math.pi * t / 7.0) if t < 7 else 0.0)
    x = min(dt / PULL_F, 1.0)
    return (1.0 - x) ** 3


def impact(b, f):
    """Hot-spot envelope at bank b's tips after each of its slams (lands with the rods)."""
    f %= vj.FRAMES
    v = 0.0
    for k, banks, kind in EVENTS:
        if kind == "slam" and BANK_NAMES[b] in banks:
            v += rx.hit_env(rx.cyc(f - rx.acc_frame(k)), decay=7.0)
    return v


def signals(f):
    s = {"Swell": vj.swell(f, decay_beats=1.0), "Section": vj.section(f)}
    for b in range(4):
        s[f"Tip{b}"] = TIP_IN + (1.0 - insertion(b, f)) * TRAVEL
        s[f"Imp{b}"] = impact(b, f)
    s.update(vj.loop_signals(f))
    return s


# ------------------------------------------------------------------ materials
def by_bank(s, i, prefix):
    """Clock value prefix+bank for rod index i (a socket): bank = i mod 4 (floored, so negative rods work)."""
    b = s.math("FLOORED_MODULO", i, 4.0)
    out = None
    for k in range(4):
        term = s.mul(s.math("COMPARE", b, float(k), 0.1), s.c(f"{prefix}{k}"))
        out = term if out is None else s.add(out, term)
    return out


def band_mat():
    """The fuel band: heat churning in place (noise periodic over the camera's travel: x on a circle), vertical fuel
    pins, brightest mid-band; each rod column runs cooler above that rod's tip (blended across the gap between two
    rods); a hot spot flares at the tips after each slam."""
    s = vj.Shader("Band")
    x, _, z = s.world_pos()
    u = s.mul(x, 1.0 / S)
    i0 = s.math("FLOOR", u)
    i1 = s.add(i0, 1.0)
    w = s.smooth(s.sub(u, i0), 0.0, 1.0)

    def hot(tip):
        return s.inv(s.mul(s.smooth(z, s.sub(tip, 0.35), s.add(tip, 0.15)), 1.0 - COLD))

    h0, h1 = hot(by_bank(s, i0, "Tip")), hot(by_bank(s, i1, "Tip"))
    hf = s.add(h0, s.mul(s.sub(h1, h0), w))
    ang = s.mul(x, 2 * math.pi / TRACK)
    rc = TRACK / (2 * math.pi) * 0.55
    n = s.noise4(s.vec(s.mul(s.math("COSINE", ang), rc), s.mul(s.math("SINE", ang), rc),
                       s.madd(z, 0.8, s.mul(s.c("LoopCos"), 0.3))), s.mul(s.c("LoopSin"), 0.3),
                 scale=1.0, detail=3.0, rough=0.55)
    prof = s.mul(s.smooth(z, BAND[0], BAND[0] + 0.6), s.inv(s.smooth(z, BAND[1] - 0.9, BAND[1])),
                 s.madd(s.gauss(z, 2.3, 1.6), 0.3, 0.7))
    pt = s.math("FRACT", s.mul(x, 4.0 / S))
    pins = s.gauss(s.math("MINIMUM", pt, s.inv(pt)), 0.0, 0.07)
    imp = s.add(s.mul(by_bank(s, i0, "Imp"), s.gauss(w, 0.0, 0.35)),
                s.mul(by_bank(s, i1, "Imp"), s.gauss(w, 1.0, 0.35)))
    imp = s.mul(imp, s.gauss(z, TIP_IN + 0.2, 0.55))
    lift = s.mul(s.add(1.0, s.mul(s.c("Swell"), 0.28)), s.add(1.0, s.mul(s.c("Section"), 0.1)))
    heat = s.mul(prof, s.add(s.madd(s.smooth(n, 0.25, 0.75), 0.42, 0.45), s.mul(pins, 0.12)), hf, lift)
    heat = s.add(heat, s.mul(imp, 0.4))
    heat = s.mul(heat, 0.78 * V["band"])
    col = s.ramp(s.math("MINIMUM", heat, 1.0), V["ramp"])
    return s.emit(col, s.mul(heat, 0.72 * GAIN))


def rod_mat():
    """Absorber sections: black bodies with neon edges (a rim); brighter edges in the drop."""
    s = vj.Shader("Rods")
    lift = s.add(0.85, s.mul(s.c("Section"), 0.15), s.mul(s.c("Swell"), 0.2))
    return s.emit(V["rim"], s.mul(s.rim((0.45, 0.95)), lift, V["rim_gain"] * GAIN))


def cap_mat(b):
    """Chevron caps of bank b: hazard chevrons (pointing up) in a steel rim; they light up a little as it slams."""
    s = vj.Shader(f"Caps{b}")
    x, _, z = s.world_pos()
    oloc = s.xyz(s.node("ShaderNodeObjectInfo").outputs["Location"])[2]
    xr = s.sub(x, s.mul(s.math("ROUND", s.mul(x, 1.0 / S)), S))       # x from the nearest rod's axis
    zr = s.sub(z, s.add(oloc, TIP_IN + POISON_L))                   # z up the cap
    chev = rx.hazard(s, xr, zr, period=0.3, slope=1.1, chevron=True, soft=0.07)
    ends = s.mul(s.smooth(zr, 0.05, 0.12), s.inv(s.smooth(zr, CAP_L - 0.12, CAP_L - 0.05)))
    edge = s.rim((0.5, 0.95))
    lift = s.add(1.0, s.mul(s.c(f"Imp{b}"), 0.5), s.mul(s.c("Swell"), 0.25))
    return s.emit_sum([(V["cap"], s.mul(chev, ends, s.inv(edge), lift, 0.8 * GAIN)),
                       (STEEL, s.mul(s.add(edge, s.inv(ends)), 0.45 * GAIN))])


def shaft_mat():
    s = vj.Shader("Shafts")
    _, _, z = s.world_pos()
    return s.emit(STEEL, s.mul(s.core(0.5, 1.2), s.inv(s.smooth(z, 9.0, 12.5)), 0.28 * GAIN))


def plate_mat():
    """Core plates and the back wall: steel edge lines (world z / x), black bodies."""
    s = vj.Shader("Plates")
    x, _, z = s.world_pos()
    lines = None
    for zl in (BAND[0] - 0.25, BAND[0] - 0.05, BAND[1] + 0.08, BAND[1] + 0.3):
        g = s.gauss(z, zl, 0.022)
        lines = g if lines is None else s.add(lines, g)
    return s.emit(STEEL, s.mul(lines, 0.55 * GAIN))


def backwall_mat():
    """A far wall of the upper plenum (parallax as the camera tracks): a faint steel grid, periodic over the
    track; the lower plenum below the core glows faintly with coolant."""
    s = vj.Shader("BackWall")
    x, _, z = s.world_pos()

    def lines(v, sp, w):
        t = s.math("FRACT", s.mul(v, 1.0 / sp))
        return s.inv(s.smooth(s.mul(s.math("MINIMUM", t, s.inv(t)), sp), w, w * 2.5))

    grid = s.math("MAXIMUM", lines(x, PERIOD / 2, 0.02), lines(z, 1.25, 0.02))
    up = s.smooth(z, BAND[1] + 0.3, BAND[1] + 1.0)
    low = s.inv(s.smooth(z, BAND[0] - 0.6, BAND[0] - 0.2))
    return s.emit_sum([(STEEL, s.mul(grid, s.add(up, low), 0.06 * GAIN)),
                       (V["plenum"], s.mul(low, s.smooth(z, -1.5, BAND[0] - 0.5), 0.5 * GAIN))])


# ------------------------------------------------------------------ geometry
def rod_pts(x, z0, z1, r):
    """Axis points from a rounded nose at z0 up to z1 (with the radius at each point)."""
    pts, rads = [], []
    for k in range(7):                                            # the nose: a quarter circle
        a = math.radians(90.0 * k / 6)
        pts.append(Vector((x, 0.0, z0 + r * (1 - math.cos(a)))))
        rads.append(max(r * math.sin(a), 0.004))
    for k in range(1, 6):
        pts.append(Vector((x, 0.0, z0 + r + (z1 - z0 - r) * k / 5)))
        rads.append(r)
    return pts, rads


def bank_meshes(b, i_lo, i_hi):
    rods, caps, shafts = bmesh.new(), bmesh.new(), bmesh.new()
    r = V["rod_r"]
    for i in range(i_lo, i_hi):
        if i % 4 != b:
            continue
        x = i * S
        pts, rads = rod_pts(x, TIP_IN, TIP_IN + POISON_L, r)
        vj.tube(rods, pts, lambda u, rads=rads: rads[min(int(round(u * (len(rads) - 1))), len(rads) - 1)], segs=14)
        z0 = TIP_IN + POISON_L
        vj.tube(caps, [Vector((x, 0.0, z0 + CAP_L * t / 4)) for t in range(5)], lambda u: r * 1.3, segs=16)
        vj.tube(shafts, [Vector((x, 0.0, z0 + CAP_L)), Vector((x, 0.0, 16.0))], lambda u: 0.035, segs=6)
    return rods, caps, shafts


def box_bm(x0, x1, z0, z1, y):
    bm = bmesh.new()
    bm.faces.new([bm.verts.new(p) for p in ((x0, y, z0), (x1, y, z0), (x1, y, z1), (x0, y, z1))])
    return bm


# ------------------------------------------------------------------ scene
def build():
    scene = vj.reset_scene()
    vj.clock_from(signals)
    ext = vj.EXT
    dist, lens, pitch, zview = V["cam"]
    half_w = dist * 18.0 / lens * 1.6 + 2.0                       # wide enough for the frame plus the track
    x_lo, x_hi = -half_w, TRACK + half_w
    i_lo, i_hi = int(math.floor(x_lo / S)) - 4, int(math.ceil(x_hi / S)) + 4

    vj.new_obj("Band", box_bm(x_lo, x_hi, BAND[0], BAND[1], 0.45), band_mat())
    pm = plate_mat()                                                # the lower and upper core plates (strips)
    vj.new_obj("PlateLow", box_bm(x_lo, x_hi, BAND[0] - 0.3, BAND[0] - 0.02, 0.3), pm)
    vj.new_obj("PlateHigh", box_bm(x_lo, x_hi, BAND[1] + 0.05, BAND[1] + 0.35, 0.3), pm)
    vj.new_obj("BackWall", box_bm(x_lo - 6, x_hi + 6, -3.0, 16.0, 6.0), backwall_mat())
    rm, sm = rod_mat(), shaft_mat()
    for b in range(4):
        rods, caps, shafts = bank_meshes(b, i_lo, i_hi)
        cm = cap_mat(b)
        keys = [(f, (0.0, 0.0, (1.0 - insertion(b, f)) * TRAVEL)) for f in ext]
        for name, bm, mat in ((f"Rods{b}", rods, rm), (f"Caps{b}", caps, cm), (f"Shafts{b}", shafts, sm)):
            ob = vj.new_obj(name, bm, mat)
            vj.keyed(ob, "location", keys)

    cam = vj.camera(scene, lens=lens, clip=(0.5, 100.0))
    zc = zview - dist * math.tan(math.radians(pitch))             # aim the view centre at z = zview
    loc, rot = [], []
    for f in ext:
        a = 2 * math.pi * f / vj.FRAMES
        jk = vj.jolt(f) * (1.0 + 0.8 * vj.section(f))             # the drop thumps harder
        x = TRACK * f / vj.FRAMES
        loc.append((f, (x, -dist + 0.6 * math.sin(a), zc + 0.12 * math.sin(2 * a + 0.5) - 0.05 * jk)))
        rot.append((f, (math.radians(90.0 + pitch + 0.35 * math.sin(a) - 0.3 * jk), math.radians(0.5 * math.sin(a)),
                        0.0)))
    vj.keyed(cam, "location", loc)
    vj.keyed(cam, "rotation_euler", rot)
    return scene


scene = build()
vj.standard_render(scene)
vj.finish(scene, f"control_rods_{VNAME}")
