"""TURBINE HALL - REACTOR VJ loop. 8 bars, seamless, 1920x1080 @ 30 fps; tempo from vjkit (140 BPM half-time =
411 frames).

The camera tracks along the plant's turbine hall at the height of the machines. In the far wall a row of giant
turbine rotors spins behind static stator struts, each in a riveted shroud and a steel housing with its unit number;
on top of the housings, between the units, insulator stacks carry toroidal terminals. The blades are drawn as their
own motion blur (a bright leading edge with a fading trail, turning about 8 degrees a frame), so the spin reads the
same with or without render motion blur. The camera moves exactly four bays per loop (the bays repeat), and the
rotation adds up to whole blade pitches, so frame 411 equals frame 0. A power meter (a strip chart in the lower left,
POWER) scrolls with the music: its line steps up on every accent, redlines in the fill and drops on the section hit.
  Bars 1-4 (A): the rotors in the variant's first colour, one power arc per accent.
  Bars 5-8 (B): the second colour, the rotors spin faster, two arcs per accent.
Beat hooks: on every accent (kick and snare) a thin power arc leaps between two terminals over the unit in view (it
grows across in two frames, peaks on the accent and dies away); on the section hits three arcs fire at once as the
meter discharges; the rotors surge a little on the kick; the camera thumps after the accents.
No strobing: the arcs are lines (never fills), their light rises over two frames and decays over several; the rotors'
pattern turns smoothly at under a quarter of a blade pitch per frame.

  blender.exe -b --factory-startup --python turbine_hall.py -- --variant amber --frames 0,100,300 [--pct 50]
  blender.exe -b --factory-startup --python turbine_hall.py -- --variant amber --all --seam DIR [--out DIR] [--mblur]
"""
import math
import os
import random
import sys

import bmesh
from mathutils import Matrix, Vector

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import vjkit as vj  # noqa: E402
import letters  # noqa: E402
import rx_plant as rx  # noqa: E402
from vjkit import ALARM, AMBER, CHERENKOV, COOLANT, EMBER, LASER, STEEL, UVP  # noqa: E402

# rotor: (A, B) blade colours and their gain (green is high luma); arc: the power arcs; chart: the meter line.
VARIANTS = {
    "amber": dict(rotor=(AMBER, EMBER), rotor_gain=1.0, rim=(STEEL, AMBER), arc=COOLANT, chart=LASER),
    "blue": dict(rotor=(CHERENKOV, UVP), rotor_gain=1.4, rim=(STEEL, CHERENKOV), arc=(0.55, 0.85, 1.0), chart=AMBER),
    "green": dict(rotor=(LASER, COOLANT), rotor_gain=0.55, rim=(STEEL, (0.05, 0.6, 0.25)), arc=(0.6, 1.0, 0.72),
                  chart=AMBER),
}
VNAME, V = vj.variant(VARIANTS)
GAIN = float(vj.arg("--gain", 1.0))

S = 16.0                                   # bay spacing along the hall (m): one unit per bay
BAYS = 4                                   # bays the camera passes per loop (a unit every 2 bars)
TRAVEL = BAYS * S
WALL_Y = 26.0                              # the rotor faces' plane
ROTOR_Z = 8.5                              # rotor axis height
R_B = 5.6                                  # blade tip radius (the shroud sits just outside)
N_BLADES = 9
TWIST = 0.35                               # blade sweep from hub to tip (pitches)
TERM_Z = 17.4                              # terminal electrodes' height
CAM_Z, YAW, LENS, SHIFT = 10.5, 15.0, 20.0, 0.0
HUD_D = 1.0                                # the meter's distance in front of the lens (camera space)


# ------------------------------------------------------------------ music
def rotor_turns():
    """Blade-pitch position per frame 0..FRAMES: ~0.2 pitch a frame in A, ~0.24 in B (eased across the fills), a small
    surge on the kick; scaled so the loop adds up to a whole number of pitches (seamless)."""
    sp = []
    for f in range(vj.FRAMES):
        c = vj.clock(f)
        sp.append((0.2 + 0.04 * vj.section(f, morph=24)) * (1.0 + 0.12 * c["kick"]))
    total = sum(sp)
    k = round(total) / total
    acc, out = 0.0, [0.0]
    for v in sp:
        acc += v * k
        out.append(acc)
    return out


TURNS = rotor_turns()


def meter(f):
    """The power meter (0..1 of the chart's height): steps up on each accent of a section (eased over 5 frames) to the
    redline, swells over it in the fill, and drops back (6 frames) on the section hit."""
    c = vj.clock(f)
    per = vj.HALF // vj.ACC                                           # accents per section
    a = c["acc"] % per
    t = c["f"] - vj.BEAT_F[c["acc"] * vj.ACC]
    jitter = 0.008 * math.sin(2 * math.pi * 13 * f / vj.FRAMES) + 0.006 * math.sin(2 * math.pi * 31 * f / vj.FRAMES + 1)
    if a == 0:
        return 0.965 - 0.845 * vj.ease(t / 6.0) + jitter
    return 0.12 + 0.115 * (a - 1) + 0.115 * vj.ease(t / 5.0) + 0.04 * vj.swell(f) + jitter


def signals(f):
    c = vj.clock(f)
    s = {"Kick": c["kick"], "Swell": vj.swell(f), "Section": vj.section(f), "Rot": TURNS[f % vj.FRAMES] % 1.0,
         "AccLift": rx.accent_env(f, attack=2.0, decay=5.0)}
    s.update(vj.loop_signals(f))
    return s


# ------------------------------------------------------------------ materials
def fade(s, length=40.0):
    return s.mul(s.falloff(s.dist, length), s.smooth(s.dist, 2.0, 6.0))


def blades_mat():
    """The spinning blade disc as its own motion blur: per blade a bright leading edge and a trail fading behind it,
    swept back toward the tips; the pattern turns with Rot (blade pitches, wrapped). Object colour R: the unit's
    phase offset."""
    s = vj.Shader("Blades")
    x, _, z = s.obj_coords()
    off = s.xyz(s.obj_info()[0])[0]
    r = s.mul(s.length2(x, z), 1.0 / R_B)
    sp = s.add(s.mul(s.math("ARCTAN2", z, x), N_BLADES / (2 * math.pi)), s.mul(r, TWIST), off)
    u = s.math("FRACT", s.sub(sp, s.c("Rot")))                          # 1 = the leading edge
    blade = s.exp(s.mul(s.inv(u), -1.0 / 0.15))
    edge = s.smooth(u, 0.9, 0.995)
    rings = s.add(s.gauss(r, 0.55, 0.012), s.gauss(r, 0.82, 0.01))
    span = s.mul(s.smooth(r, 0.24, 0.32), s.inv(s.smooth(r, 0.985, 1.0)))
    level = s.add(s.mul(s.add(s.mul(blade, 0.42), s.mul(edge, 0.5)), s.madd(s.mul(r, r), 0.65, 0.35)), 0.035,
                  s.mul(rings, 0.25))
    lift = s.add(0.85, s.mul(s.c("Kick"), 0.1), s.mul(s.c("Swell"), 0.25))
    col = s.mix(s.c("Section"), V["rotor"][0], V["rotor"][1])
    return s.emit(col, s.mul(level, span, lift, fade(s), 1.5 * V["rotor_gain"] * GAIN))


def hub_mat():
    """The spinner: rim-lit, with 9 stripes turning with the blades."""
    s = vj.Shader("Hub")
    x, _, z = s.obj_coords()
    u = s.math("FRACT", s.sub(s.mul(s.math("ARCTAN2", z, x), N_BLADES / (2 * math.pi)), s.c("Rot")))
    stripe = s.gauss(u, 0.5, 0.12)
    col = s.mix(s.c("Section"), V["rotor"][0], V["rotor"][1])
    return s.emit(col, s.mul(s.add(s.mul(s.rim((0.4, 0.95)), 0.8), s.mul(stripe, 0.35)), fade(s),
                             1.4 * V["rotor_gain"] * GAIN))


def shroud_mat():
    """The shroud rings and bolts: hot neon tubes in the rotor colour."""
    s = vj.Shader("Shroud")
    col = s.mix(s.c("Section"), V["rotor"][0], V["rotor"][1])
    lift = s.add(0.75, s.mul(s.c("AccLift"), 0.2), s.mul(s.c("Swell"), 0.3))
    return s.emit(col, s.mul(s.core(0.4, 1.3), lift, fade(s), 1.6 * V["rotor_gain"] * GAIN))


def steel_mat(name, gain):
    """Housings, struts, columns, stacks, the crane girder: rim-lit steel, tinted toward the section colour."""
    s = vj.Shader(name)
    col = s.mix(s.c("Section"), V["rim"][0], V["rim"][1])
    lift = s.add(0.8, s.mul(s.c("Swell"), 0.25))
    return s.emit(col, s.mul(s.rim((0.4, 0.93)), lift, fade(s), gain * GAIN))


def term_mat():
    """Terminal electrodes: dim tori that glow up with every accent (the arcs land on them)."""
    s = vj.Shader("Terminal")
    lift = s.add(0.35, s.mul(s.c("AccLift"), 0.55), s.mul(s.c("Swell"), 0.3))
    return s.emit(V["arc"], s.mul(s.core(0.4, 1.3), lift, fade(s), 1.2 * GAIN))


def floor_mat():
    """The hall floor: faint plate seams (every 3 m along the hall's width, every 4 m along it), fading with distance."""
    s = vj.Shader("Floor")
    x, y, _ = s.world_pos()

    def lines(v, spacing):
        t = s.math("FRACT", s.madd(v, 1.0 / spacing, 0.5))
        return s.inv(s.smooth(s.mul(s.math("ABSOLUTE", s.sub(t, 0.5)), spacing), 0.03, 0.09))

    g = s.math("MAXIMUM", lines(x, 4.0), lines(y, 3.0))
    return s.emit(STEEL, s.mul(g, fade(s), s.smooth(y, 6.0, 12.0), 0.35 * GAIN))


def digit_mat():
    s = vj.Shader("UnitDigits")
    return s.emit(V["rim"][1], s.mul(s.core(0.5, 1.2), fade(s), 0.9 * GAIN))


def arc_mat():
    """A power arc: additive (nothing to occlude when off). Object colour: R = reveal (how far it has leapt across,
    UV x = 0..1 along it), G = seed, A = intensity. A crawl of brightness runs along it; a hot white core."""
    s = vj.Shader("Arc")
    col, alpha, _ = s.obj_info()
    reveal, seed, _ = s.xyz(col)
    u = s.uv()[0]
    on = s.inv(s.smooth(u, s.sub(reveal, 0.03), s.add(reveal, 0.001)))
    crawl = s.noise4(s.vec(s.madd(u, 7.0, s.mul(s.c("LoopCos"), 3.0)), s.mul(seed, 9.0), 0.0),
                     s.mul(s.c("LoopSin"), 3.0), scale=1.0, detail=2.0)
    core = s.core(0.0, 1.0)
    c = s.mix(s.mul(s.smooth(core, 0.5, 1.0), 0.6), V["arc"], (1.0, 1.0, 1.0))
    return s.additive(c, s.mul(alpha, on, s.madd(crawl, 0.9, 0.55), s.core(0.5, 1.4), fade(s, 60.0), 6.0 * GAIN))


def hud_mat(name, color, gain, masked=False, panel=None):
    """Meter graphics (camera space, additive). masked: shown only inside the chart window (panel space x), so the
    scrolling line appears at the left edge and ends at the pen."""
    s = vj.Shader(name)
    k = gain * GAIN
    if masked:
        tc = s.node("ShaderNodeTexCoord")
        tc.object = panel
        x = s.xyz(tc.outputs["Object"])[0]
        k = s.mul(s.smooth(x, CHART[0], CHART[0] + 0.04), s.inv(s.smooth(x, CHART[1] - 0.001, CHART[1] + 0.003)), k)
    return s.additive(color, s.mul(s.add(0.85, s.mul(s.c("Swell"), 0.2)), k))


# ------------------------------------------------------------------ geometry
def unit_bm():
    """One unit around its rotor axis (origin on the axis at the rotor face, x along the hall, -y toward the hall):
    housing frame and stator struts (steel), shroud rings and bolts, terminal stack at the bay's left edge."""
    steel, shroud, term = bmesh.new(), bmesh.new(), bmesh.new()
    w, z0, z1 = 7.4, -7.0, 6.6                                          # housing half-width, bottom, top
    corners = [Vector((-w, 0.3, z0)), Vector((w, 0.3, z0)), Vector((w, 0.3, z1)), Vector((-w, 0.3, z1))]
    rx.stroke(steel, corners, 0.2, segs=8, closed=True, joints=False)
    for cz in (z0 + 1.2, z1 - 1.2):                                      # rivet rows along the housing
        for i in range(13):
            p = Vector((-w + 0.9 + i * (2 * w - 1.8) / 12, 0.1, cz))
            bmesh.ops.create_icosphere(steel, subdivisions=1, radius=0.09, matrix=Matrix.Translation(p))
    for a in (45, 135, 225, 315):                                        # stator struts in front of the blades
        d = Vector((math.cos(math.radians(a)), 0.0, math.sin(math.radians(a))))
        rx.cylinder(steel, d * 1.5 + Vector((0, -0.6, 0)), d * 6.0 + Vector((0, -0.6, 0)), 0.13, segs=8)
    rx.ring(shroud, (0, 0, 0), (0, 1, 0), R_B + 0.5, 0.32, n=96, segs=8)
    rx.ring(shroud, (0, -0.25, 0), (0, 1, 0), R_B + 1.3, 0.12, n=96, segs=6)
    rx.bolt_circle(shroud, (0, -0.3, 0), (0, 1, 0), R_B + 0.95, 24, 0.09, 0.2)
    tx = -S / 2                                                          # the terminal stack between units
    rx.cylinder(steel, (tx, -1.4, z1), (tx, -1.4, TERM_Z - ROTOR_Z - 0.4), 0.18, segs=8)
    for i in range(7):
        zz = z1 + 0.35 + i * 0.25
        rx.cylinder(steel, (tx, -1.4, zz), (tx, -1.4, zz + 0.05), 0.48, segs=16)
    rx.ring(term, (tx, -1.4, TERM_Z - ROTOR_Z), (0, 0, 1), 0.72, 0.26, n=32, segs=10)
    rx.cylinder(steel, (tx, 0.3, z1), (tx, -1.4, z1), 0.12, segs=6)       # the stack's bracket
    return steel, shroud, term


def hub_bm():
    bm = bmesh.new()
    prof = [Vector((0, 0.3 - 2.0 * t, 0)) for t in (0.0, 0.25, 0.5, 0.7, 0.85, 0.95, 1.0)]
    vj.tube(bm, prof, lambda u: 1.45 * math.sqrt(max(1.0 - u * u, 0.0)) + 0.02, segs=36, cap0=True, cap1=False)
    return bm


def hall_bm():
    """Per bay: a column (at the bay's left edge, in the wall) and a length of the crane girder above the units."""
    bm = bmesh.new()
    rx.cylinder(bm, (-S / 2, WALL_Y + 0.6, 0.0), (-S / 2, WALL_Y + 0.6, 22.0), 0.3, segs=10)
    rx.cylinder(bm, (-S / 2, WALL_Y - 1.0, 20.2), (S / 2, WALL_Y - 1.0, 20.2), 0.35, segs=10, caps=False)
    rx.cylinder(bm, (-S / 2, WALL_Y - 1.0, 19.4), (S / 2, WALL_Y - 1.0, 19.4), 0.12, segs=6, caps=False)
    for i in range(8):                                                   # girder web
        xa, xb = -S / 2 + i * S / 8, -S / 2 + (i + 1) * S / 8
        za, zb = (20.2, 19.4) if i % 2 == 0 else (19.4, 20.2)
        rx.cylinder(bm, (xa, WALL_Y - 1.0, za), (xb, WALL_Y - 1.0, zb), 0.07, segs=5, caps=False)
    return bm


def digit_bm(ch, height=1.5):
    bm = bmesh.new()
    for _, strokes in letters.layout(ch, height, align="left"):
        for st in strokes:
            rx.stroke(bm, rx.resample([Vector((x, 0.0, y)) for x, y in st], 0.15), 0.06, segs=6)
    return bm


# ------------------------------------------------------------------ the meter (camera space)
HALF_W = 18.0 / LENS * HUD_D                     # half the frame's width at HUD_D
HALF_H = HALF_W * 9.0 / 16.0
CY = SHIFT * 2 * HALF_W                          # the frame's centre (shift)
CHART = (-0.66 * HALF_W, -0.08 * HALF_W)         # x range of the chart window (camera space at HUD_D)
CH_Y0, CH_H = CY - 0.88 * HALF_H, 0.2 * HALF_H   # its baseline and height
SPEED = (CHART[1] - CHART[0]) / (vj.HALF * vj.FPB)   # the line scrolls one section across the window


def hud(cam):
    r = 0.0016 * HUD_D
    panel = vj.new_empty("MeterPanel", cam)
    panel.location = (0.0, 0.0, -HUD_D)
    grid = bmesh.new()
    for v in (0.0, 0.5, 1.0):
        rx.stroke(grid, [Vector((CHART[0], CH_Y0 + v * CH_H, 0)), Vector((CHART[1], CH_Y0 + v * CH_H, 0))],
                  r * (0.8 if v == 0.0 else 0.5), segs=6, joints=False)
    rx.stroke(grid, [Vector((CHART[0], CH_Y0, 0)), Vector((CHART[0], CH_Y0 + CH_H, 0))], r * 0.6, segs=6)
    vj.new_obj("MeterGrid", grid, hud_mat("MeterGrid", V["chart"], 0.35), panel)
    red = bmesh.new()
    rx.stroke(red, [Vector((CHART[0], CH_Y0 + 0.92 * CH_H, 0)), Vector((CHART[1], CH_Y0 + 0.92 * CH_H, 0))],
              r * 0.6, segs=6, joints=False)
    vj.new_obj("MeterRedline", red, hud_mat("MeterRedline", ALARM, 0.8), panel)
    lab = bmesh.new()
    th = 0.11 * CH_H * 1.6
    for _, strokes in letters.layout("POWER", th, align="left"):
        for st in strokes:
            rx.stroke(lab, [Vector((CHART[0] + x, CH_Y0 + CH_H + 0.35 * th + y, 0)) for x, y in st], r * 0.7, segs=6)
    vj.new_obj("MeterLabel", lab, hud_mat("MeterLabel", V["chart"], 0.9), panel)

    line = bmesh.new()                                                  # the data, over a loop and a window either
    t0, t1 = -int(vj.HALF * vj.FPB) - 6, vj.FRAMES + 6                   # side, x = t * SPEED in its own space
    pts = [Vector((t * SPEED, CH_Y0 + meter(t) * CH_H, 0.0)) for t in range(t0, t1 + 1)]
    rx.stroke(line, pts, r, segs=6, joints=False)
    for b in range(-vj.BARS, 2 * vj.BARS + 1):                          # bar ticks on the baseline
        x = vj.beat_frame(4 * b) * SPEED
        rx.stroke(line, [Vector((x, CH_Y0, 0)), Vector((x, CH_Y0 + 0.12 * CH_H, 0))], r * 0.6, segs=6,
                  joints=False)
    ob = vj.new_obj("MeterLine", line, hud_mat("MeterLine", V["chart"], 1.6, masked=True, panel=panel), panel)
    vj.keyed(ob, "location", [(f, (CHART[1] - f * SPEED, 0.0, 0.0)) for f in (-30, vj.FRAMES + 30)])
    pen = bmesh.new()
    bmesh.ops.create_icosphere(pen, subdivisions=2, radius=r * 2.6)
    ob = vj.new_obj("MeterPen", pen, hud_mat("MeterPen", V["chart"], 2.5), panel)
    vj.animate(ob, "location", [(f, (CHART[1], CH_Y0 + meter(f) * CH_H, 0.0)) for f in vj.EXT], interp="LINEAR")


# ------------------------------------------------------------------ arcs
def arc_plan():
    """[(accent frame, first bay, number of bays)]: an arc over the unit in view per accent (the snare's one bay
    further on), two in B, three on each section hit."""
    out = []
    for j, (af, amp) in enumerate(vj.accent_frames()):
        xc = TRAVEL * af / vj.FRAMES + WALL_Y * math.tan(math.radians(YAW))   # the view's centre on the wall
        k = int(round((xc - S / 2) / S)) + (1 if amp < 1.0 else 0)
        hit = af in (0, vj.BEAT_F[vj.HALF])
        n = 3 if hit else (2 if af >= vj.BEAT_F[vj.HALF] else 1)
        out.append((af, k - (1 if hit else 0), n))
    return out


def arc_state(f, af):
    """(reveal, intensity) of an arc fired on accent frame af: it leaps across over 2 frames into the accent, then
    dies away over ~12 frames."""
    t = (f - af) % vj.FRAMES
    if t > vj.FRAMES - 3:
        t -= vj.FRAMES
    if t < -2 or t > 18:
        return 0.0, 0.0
    if t <= 0:
        return (t + 3) / 3.0, (0.55, 0.8, 1.0)[t + 2]
    return 1.0, math.exp(-t / 4.0)


def build_arcs():
    mat = arc_mat()
    rng = random.Random(77)
    y, z = WALL_Y - 1.4, TERM_Z
    for i, (af, k0, n) in enumerate(arc_plan()):
        for m in range(n):
            k = k0 + m
            bm = bmesh.new()
            p0, p1 = Vector((k * S + 0.75, y, z)), Vector(((k + 1) * S - 0.75, y, z))
            pts = rx.arc_path(p0, p1, rng, lift=Vector((0, -0.9, rng.uniform(1.1, 1.9))), jag=0.07, levels=6)
            rx.ribbon_uv(bm, pts, 0.035, segs=6)
            for branch in range(2):                                     # two short forks off the main path
                j = rng.randint(len(pts) // 5, 4 * len(pts) // 5)
                tip = pts[j] + Vector((rng.uniform(-1.2, 1.2), rng.uniform(-0.6, 0.2), rng.uniform(-1.6, -0.4)))
                fork = rx.arc_path(pts[j], tip, rng, jag=0.15, levels=3)
                uj = j / (len(pts) - 1)
                rx.ribbon_uv(bm, fork, 0.02, segs=5, u_range=(uj, uj))     # shows once the arc passes its root
            me = vj.finish_bm(bm, smooth=True, name=f"ArcMesh{i}_{m}")
            seed = rng.uniform(0.0, 1.0)
            keys = []
            for f in range(vj.FRAMES + 1):
                rv, it = arc_state(f, af)
                keys.append((f, (rv, seed, 0.0, it)))
            for c in (-1, 0, 1):                                         # copies a loop either side: the seam
                ob = vj.mesh_obj(f"Arc{i}_{m}_{c}", me, mat)
                ob.location = (c * TRAVEL, 0.0, 0.0)
                vj.animate(ob, "color", keys)


# ------------------------------------------------------------------ scene
def build():
    scene = vj.reset_scene()
    vj.clock_from(signals)

    steel_bm, shroud_bm, term_bm = unit_bm()
    steel_me = vj.finish_bm(steel_bm, smooth=True, name="UnitSteel")
    shroud_me = vj.finish_bm(shroud_bm, smooth=True, name="UnitShroud")
    term_me = vj.finish_bm(term_bm, smooth=True, name="UnitTerminal")
    blades_me = vj.finish_bm(vj.disc_bm(R_B + 0.3, 128), smooth=False, name="BladeDisc")
    hub_me = vj.finish_bm(hub_bm(), smooth=True, name="HubMesh")
    hall_me = vj.finish_bm(hall_bm(), smooth=True, name="HallMesh")
    digits = [vj.finish_bm(digit_bm(str(i + 1)), smooth=True, name=f"Digit{i}") for i in range(BAYS)]
    m_steel, m_hall = steel_mat("Steel", 1.2), steel_mat("HallSteel", 0.9)
    m_blades, m_hub, m_shroud, m_term, m_digit = blades_mat(), hub_mat(), shroud_mat(), term_mat(), digit_mat()
    lo, hi = -3, BAYS + 4                                                # bays in view over the loop (+ margin)
    for k in range(lo, hi):
        slot = k % BAYS                                                  # per slot: the same in every period
        x = k * S + S / 2
        root = vj.new_empty(f"Unit{k}")
        root.location = (x, WALL_Y, ROTOR_Z)
        vj.mesh_obj(f"UnitSteel{k}", steel_me, m_steel, root)
        vj.mesh_obj(f"UnitShroud{k}", shroud_me, m_shroud, root)
        vj.mesh_obj(f"UnitTerminal{k}", term_me, m_term, root)
        bl = vj.mesh_obj(f"UnitBlades{k}", blades_me, m_blades, root)
        bl.location = (0.0, 0.45, 0.0)
        bl.color = (0.27 * slot, 0.0, 0.0, 1.0)
        vj.mesh_obj(f"UnitHub{k}", hub_me, m_hub, root)
        dg = vj.mesh_obj(f"UnitDigit{k}", digits[slot], m_digit, root)
        dg.location = (-6.6, -0.2, 4.3)
        vj.mesh_obj(f"Hall{k}", hall_me, m_hall).location = (x, 0.0, 0.0)
    wall = vj.new_obj("Wall", vj.quad_bm(TRAVEL * 3 + 200.0, 60.0), vj.black_mat("WallBlack"))
    wall.location = (TRAVEL / 2, WALL_Y + 1.2, 10.0)
    floor = vj.new_obj("Floor", vj.quad_bm(TRAVEL * 3 + 200.0, 60.0, axis="Z"), floor_mat())
    floor.location = (TRAVEL / 2, 0.0, 0.0)
    build_arcs()

    cam = vj.camera(scene, lens=LENS, clip=(0.3, 400.0))
    cam.data.shift_y = SHIFT
    loc, rot = [], []
    for f in vj.EXT:
        a = 2 * math.pi * f / vj.FRAMES
        loc.append((f, (TRAVEL * f / vj.FRAMES, 0.4 * math.sin(a), CAM_Z + 0.3 * math.sin(2 * a + 0.5))))
        pitch = 0.4 * math.sin(a + 1.0) + 0.45 * vj.jolt(f)
        rot.append((f, (math.radians(90.0 + pitch), math.radians(0.6 * math.sin(a + 0.3)),
                        math.radians(-YAW - 2.0 * math.sin(a)))))
    vj.keyed(cam, "location", loc)
    vj.keyed(cam, "rotation_euler", rot)
    hud(cam)
    return scene


scene = build()
vj.standard_render(scene)
vj.finish(scene, f"turbine_hall_{VNAME}")
