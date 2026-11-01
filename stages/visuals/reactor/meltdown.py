"""MELTDOWN - REACTOR VJ loop. 8 bars, seamless, 1920x1080 @ 30 fps; tempo from vjkit (140 BPM half-time =
411 frames).

The core has gone critical. A cut-away reactor vessel: the front of its upper shell is cut away, so above the lower
head's hot rim we look into the vessel, where a molten fuel mass (corium) heaves and slumps, orange to white-hot, its
crust plates creeping down the mound (a two-phase flow map, seamless); embers rise and swirl, heat shimmer wavers above
it, the vessel's inner wall glows with its light. Two analog gauges at the frame sides (TEMP, FLUX) push into the red.
Beat hooks: every accent throbs the mass (it heaves) and kicks both needles up (a damped bounce: the FLUX needle jumps
harder); the swell into each 4-bar hit pegs the needles and makes the mass flare, and after the hit they sag back and
climb again.
Variants: ember (the classic orange meltdown), alarm (a red-hot core, rotating alarm beacons washing the vessel wall
red, a CRITICAL sign that breathes on the beat), scram (on bar 5's downbeat five control rods slam into the mass and
everything sinks to deep blue over 8 frames, a fade, not a flash: the needles fall to zero and the embers die; through
the swell into bar 1 the rods pull out and the core reignites, landing hot on the loop's downbeat).
No strobing: the beacons sweep softly and never face the lens; the big hot mass keeps a dark crust (block cap 0.65).

  blender.exe -b --factory-startup --python meltdown.py -- --variant ember --frames 0,206,240 [--pct 25]
  blender.exe -b --factory-startup --python meltdown.py -- --variant scram --all --seam DIR [--mblur]
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
import rx_core as rx  # noqa: E402
from vjkit import ALARM, AMBER, CHERENKOV, EMBER, HOT, STEEL  # noqa: E402

LAVA = [(0.0, (0.0, 0.0, 0.0)), (0.22, (0.1, 0.004, 0.0)), (0.45, (0.55, 0.05, 0.002)), (0.62, EMBER),
        (0.8, AMBER), (1.0, HOT)]
RED_LAVA = [(0.0, (0.0, 0.0, 0.0)), (0.25, (0.12, 0.0, 0.0)), (0.5, (0.6, 0.012, 0.006)), (0.68, ALARM),
            (0.85, EMBER), (1.0, (1.0, 0.4, 0.1))]
COLD = [(0.0, (0.0, 0.0, 0.0)), (0.3, (0.0, 0.01, 0.06)), (0.6, (0.02, 0.12, 0.45)), (0.85, CHERENKOV),
        (1.0, (0.35, 0.65, 1.0))]
# lava ramp, the rim of the lower head, ember colours (hot, cool), needles, wall light, mass brightness
VARIANTS = {
    "ember": dict(lava=LAVA, glow=EMBER, embers=(HOT, EMBER), needle=AMBER, wall=(1.0, 0.25, 0.03), mass=1.0,
                  beacons=False, sign=False, scram=False),
    "alarm": dict(lava=RED_LAVA, glow=ALARM, embers=((1.0, 0.45, 0.15), ALARM), needle=(1.0, 0.18, 0.05),
                  wall=(1.0, 0.06, 0.03), mass=1.15, beacons=True, sign=True, scram=False),
    "scram": dict(lava=LAVA, glow=EMBER, embers=(HOT, EMBER), needle=AMBER, wall=(1.0, 0.25, 0.03), mass=1.0,
                  beacons=False, sign=False, scram=True),
}
VNAME, V = vj.variant(VARIANTS)
GAIN = float(vj.arg("--gain", 1.0))

R_V = 4.0                                 # vessel radius (m); the lower head's rim is at z = 0
HEAD_DEPTH = 2.7                          # the lower head (a squashed hemisphere) reaches z = -HEAD_DEPTH
MASS = (3.75, 3.75, 2.1)                  # corium half-extents (x, y, z): a mound bulging above the rim
FLOW_N, FLOW_L = 3, 0.9                   # flow-map cycles per loop, slide per cycle (m): the crust creeps down
GAUGE_Y, GAUGE_X, GAUGE_Z, GAUGE_R = 0.0, 4.6, 0.45, 0.85   # in the gauge rig (camera space, 6 m out, x0.5)
HUD_D, HUD_SCALE = 6.0, 0.5
SWEEP = (225.0, -45.0)                    # needle angle (deg, ccw from +x) at value 0 and 1
RED_ZONE = 0.75
F_B = vj.BEAT_F[vj.HALF]                  # bar 5's downbeat: the scram
SCRAM_FADE = 8                            # frames for the sink to blue
F_RELIGHT = vj.BEAT_F[vj.BEATS - 2]       # the swell into bar 1: the core reignites
ROD_X = (-2.6, -1.3, 0.0, 1.3, 2.6)
ROD_PARK, ROD_IN = 6.4, -1.2              # scram rods' tip height: parked above the frame / slammed into the mass


# ------------------------------------------------------------------ timeline
def scram(f):
    """0 = hot, 1 = scrammed (deep blue). Only the scram variant: sinks over SCRAM_FADE frames from bar 5's downbeat,
    holds, and reignites through the swell into bar 1 (back to 0 on frame FRAMES = 0)."""
    if not V["scram"]:
        return 0.0
    f %= vj.FRAMES
    if f < F_B:
        return 0.0
    if f < F_RELIGHT:
        return rx.ramp_between(f, F_B, F_B + SCRAM_FADE)
    return 1.0 - rx.ramp_between(f, F_RELIGHT, vj.FRAMES, shape=lambda x: x ** 1.6)


def rods_tip(f):
    """Scram rods' tip height: parked; an accelerating 3-frame fall landing on bar 5's downbeat (a small rebound);
    they pull out through the swell into bar 1."""
    f %= vj.FRAMES
    if F_B - 3 <= f < F_B:
        return ROD_PARK + (ROD_IN - ROD_PARK) * ((f - (F_B - 3)) / 3.0) ** 2
    if F_B <= f < F_RELIGHT:
        t = f - F_B
        return ROD_IN + (0.18 * math.sin(math.pi * t / 7.0) if t < 7 else 0.0)
    if f >= F_RELIGHT:
        return ROD_IN + (ROD_PARK - ROD_IN) * rx.ramp_between(f, F_RELIGHT + 2, vj.FRAMES - 3)
    return ROD_PARK


def section_pos(f):
    """(0..1 through the current 4-bar section, frames since its hit)."""
    f %= vj.FRAMES
    if f < F_B:
        return f / F_B, f
    return (f - F_B) / (vj.FRAMES - F_B), f - F_B


def bounce(f, kick_amp, snare_amp):
    """Damped needle bounce after each accent (periodic): the needle kicks up and rings down."""
    v = 0.0
    for af, amp in vj.accent_frames():
        t = (f - af) % vj.FRAMES
        if t < 30:
            a = kick_amp if amp == 1.0 else snare_amp
            v += a * math.exp(-t / 6.0) * math.sin(math.pi * t / 5.0)
    return v


def needle_value(f, which):
    """Gauge needle 0..1 (red zone from 0.75): climbs through each section, pegged by the swell into the hit, sags
    back after it; accents bounce it. Scram: falls to zero on the scram, sweeps back up through the swell."""
    x, since = section_pos(f)
    base = (0.78, 0.74)[which]
    v = base + (0.94 - base) * x ** 1.5 + (0.97 - base) * math.exp(-since / 6.0) * (1 if since < 60 else 0)
    v += 0.03 * vj.swell(f, decay_beats=0.5)
    v += bounce(f, *((0.035, 0.02), (0.05, 0.04))[which])
    v += 0.006 * math.sin(2 * math.pi * 37 * f / vj.FRAMES + which) + 0.004 * math.sin(2 * math.pi * 53 * f / vj.FRAMES)
    if V["scram"]:
        ff = f % vj.FRAMES
        if F_B <= ff < F_RELIGHT:                               # dropped to the stop, trembling
            t = ff - F_B
            low = 0.03 + 0.004 * math.sin(2 * math.pi * 41 * f / vj.FRAMES)
            v = low + (v - low) * math.exp(-t / 3.5) + (0.03 * math.exp(-(t - 9) / 3.0) if t >= 9 else 0.0)
        elif ff >= F_RELIGHT:
            u = rx.ramp_between(ff, F_RELIGHT, vj.FRAMES, shape=lambda q: q ** 1.4)
            v = 0.03 + (v - 0.03) * u
    return min(max(v, 0.0), 1.02)


def signals(f):
    c = vj.clock(f)
    ph = (FLOW_N * f / vj.FRAMES) % 1.0
    s = {"Kick": c["kick"], "Swell": vj.swell(f, decay_beats=1.2), "Section": vj.section(f), "Scram": scram(f),
         "Flow1": ph, "Flow2": (ph + 0.5) % 1.0, "FlowW": 1.0 - abs(2.0 * ph - 1.0),
         "Rise": (f % vj.FRAMES) / vj.FRAMES, "Beam": (vj.beatpos(f) / 2.0) % 1.0}
    s.update(vj.loop_signals(f))
    return s


# ------------------------------------------------------------------ materials
def heat_mix(s, hot_col, hot_st, cold_ramp_fac, cold_st):
    """(colour, strength) blending the hot look into the scrammed one by the Scram clock value."""
    cold_col = s.ramp(cold_ramp_fac, COLD)
    sc = s.c("Scram")
    return s.mix(sc, hot_col, cold_col), s.add(s.mul(hot_st, s.inv(sc)), s.mul(cold_st, sc))


def mass_mat():
    """Corium: crust plates (warped Voronoi) with glowing cracks and white-hot pools (noise cubed), sliding down the
    mound by a two-phase flow map; a hot silhouette edge; flares with the swell, throbs on the accents."""
    s = vj.Shader("Corium")
    x, y, z = s.obj_coords()

    def layer(ph, w_seed):
        zz = s.add(z, s.mul(s.c(ph), FLOW_L))
        n = s.noise4(s.vec(s.mul(x, 0.6), s.mul(y, 0.6), s.mul(zz, 0.6)), w_seed, scale=1.0, detail=5.0,
                     rough=0.55, distortion=0.5)
        warp = s.mul(s.sub(n, 0.5), 0.8)
        vor = s.node("ShaderNodeTexVoronoi", feature="DISTANCE_TO_EDGE")
        s.put(vor.inputs["Vector"], s.vec(s.madd(x, 0.95, warp), s.madd(y, 0.95, warp), s.madd(zz, 0.95, warp)))
        vor.inputs["Scale"].default_value = 1.0
        crack = s.inv(s.smooth(vor.outputs["Distance"], 0.0, 0.07))
        return s.add(s.mul(crack, 0.62), s.mul(s.math("POWER", n, 3.0), 1.5))

    w = s.c("FlowW")
    heat = s.add(s.mul(layer("Flow1", 0.3), w), s.mul(layer("Flow2", 2.1), s.inv(w)))
    low = s.inv(s.smooth(z, -0.2, 1.8))                               # hotter low down, a cooler crusted top
    rim = s.rim((0.5, 0.95))
    lift = s.add(1.0, s.mul(s.c("Swell"), 0.25), s.mul(s.c("Kick"), 0.07), s.mul(s.c("Section"), 0.08))
    heat = s.mul(s.add(s.mul(heat, s.madd(low, 0.35, 0.75)), s.mul(rim, 0.25)), lift)
    col = s.ramp(s.math("MINIMUM", heat, 1.0), V["lava"])
    st = s.mul(s.madd(heat, 0.7, 0.2), 0.9 * V["mass"] * GAIN)
    cold_lift = s.add(1.0, s.mul(s.c("Kick"), 0.18))
    col, st = heat_mix(s, col, st, s.mul(heat, 0.8), s.mul(heat, cold_lift, 0.35 * GAIN))
    return s.emit(col, st)


def head_mat():
    """The lower head (outside): black steel, a rim-lit silhouette in the glow colour, brighter near its hot rim."""
    s = vj.Shader("LowerHead")
    _, _, z = s.world_pos()
    up = s.smooth(z, -HEAD_DEPTH, 0.0)
    rim = s.rim((0.55, 0.97))
    hot = s.mul(rim, s.madd(up, 0.8, 0.2), s.add(1.0, s.mul(s.c("Swell"), 0.3)), 0.55 * GAIN)
    col, st = heat_mix(s, V["glow"], hot, s.mul(rim, 0.7), s.mul(hot, 0.5))
    return s.emit(col, st)


def lip_mat():
    """The lower head's rim: glowing hot metal (a thick ring), throbbing with the mass."""
    s = vj.Shader("Lip")
    lift = s.add(0.8, s.mul(s.c("Swell"), 0.35), s.mul(s.c("Kick"), 0.1))
    st = s.mul(s.core(0.5, 1.2), lift, 0.7 * GAIN)
    col, st = heat_mix(s, V["glow"], st, 0.7, s.mul(st, 0.5))
    return s.emit(col, st)


def wall_mat():
    """The vessel's inner back wall: steel ring and rib lines, lit by the mass from below (warm, fading up); the
    alarm variant's beacons sweep red light across it."""
    s = vj.Shader("VesselWall")
    x, y, z = s.world_pos()
    ang = s.math("ARCTAN2", x, y)                                   # around the vessel axis
    rib = s.math("FRACT", s.mul(ang, 12.0 / math.pi))
    ribs = s.gauss(s.math("MINIMUM", rib, s.inv(rib)), 0.0, 0.03)
    ring = s.math("FRACT", s.mul(z, 1.0 / 0.9))
    rings = s.gauss(s.math("MINIMUM", ring, s.inv(ring)), 0.0, 0.035)
    lines = s.math("MAXIMUM", ribs, rings)
    lit = s.exp(s.mul(s.math("MAXIMUM", s.sub(z, 0.5), 0.0), -1.0 / 2.6))
    lift = s.add(1.0, s.mul(s.c("Swell"), 0.4), s.mul(s.c("Kick"), 0.08))
    glow = s.mul(lit, lift, s.add(0.05, s.mul(lines, 0.35)), 0.9 * GAIN)
    col, st = heat_mix(s, V["wall"], glow, s.mul(lit, 0.75), s.mul(glow, 0.6))
    terms = [(col, st), (STEEL, s.mul(lines, 0.06 * GAIN))]
    if V["beacons"]:                                                 # two soft red washes sweeping across the wall
        for k, off in enumerate((0.0, 0.5)):
            pos = s.math("SINE", s.mul(s.add(s.c("Beam"), off), 2 * math.pi))      # -1..1 across the wall
            band = s.gauss(s.math("DIVIDE", ang, 1.25), pos, 0.28)
            terms.append((ALARM, s.mul(band, s.inv(s.c("Scram")), s.madd(lit, 0.5, 0.5), 0.32 * GAIN)))
    return s.emit_sum(terms)


def ember_mat():
    s = vj.Shader("Embers")
    col, alpha, _ = s.obj_info()
    return s.emit(col, s.mul(alpha, 2.2 * GAIN))


def shimmer_mat(seed):
    """Heat shimmer: faint wavy vertical streaks of warm light rising off the mass (the pattern lives on a circle in
    z, scrolled one period per loop, so it rises seamlessly), strongest just above the crust."""
    s = vj.Shader(f"Shimmer{seed}")
    x, _, z = s.world_pos()
    per = 6.0
    a = s.mul(s.sub(z, s.mul(s.c("Rise"), per)), 2 * math.pi / per)
    rc = per / (2 * math.pi) * 0.7
    n = s.noise4(s.vec(s.mul(x, 1.3), s.mul(s.math("COSINE", a), rc), s.mul(s.math("SINE", a), rc)),
                 s.madd(s.c("LoopSin"), 0.25, seed), scale=1.0, detail=2.0, distortion=1.2)
    streak = s.smooth(n, 0.55, 0.8)
    zone = s.mul(s.smooth(z, 1.2, 2.2), s.inv(s.smooth(z, 2.6, 5.4)), s.inv(s.smooth(s.math("ABSOLUTE", x), 2.4, 3.6)))
    return s.additive(V["glow"], s.mul(streak, zone, s.inv(s.c("Scram")), s.add(1.0, s.c("Swell")), 0.05 * GAIN))


def dial_mat():
    """Gauge faces: near-black discs (they hide what is behind), a faint warm wash toward the red end."""
    s = vj.Shader("Dial")
    return s.emit((0.06, 0.02, 0.01), s.mul(s.inv(s.c("Scram")), 0.25 * GAIN))


def gauge_line_mat():
    s = vj.Shader("GaugeLines")
    return s.emit(STEEL, s.mul(s.core(0.5, 1.2), 0.55 * GAIN))


def red_zone_mat():
    s = vj.Shader("RedZone")
    lift = s.add(0.75, s.mul(s.c("Swell"), 0.4), s.mul(s.c("Kick"), 0.1))
    return s.emit(ALARM, s.mul(s.core(0.5, 1.3), lift, s.madd(s.c("Scram"), -0.6, 1.0), 1.6 * GAIN))


def needle_mat():
    s = vj.Shader("Needle")
    return s.emit(V["needle"], s.mul(s.core(0.6, 1.3), 1.25 * GAIN))


def rod_mat():
    """Scram rods: black bodies with steel edges, amber chevron bands near the top."""
    s = vj.Shader("ScramRods")
    x, _, z = s.world_pos()
    oz = s.xyz(s.node("ShaderNodeObjectInfo").outputs["Location"])[2]
    xr = s.sub(x, s.mul(s.math("ROUND", s.mul(x, 1.0 / 1.3)), 1.3))
    zr = s.sub(z, s.add(oz, 5.2))
    band = s.mul(s.smooth(zr, 0.0, 0.05), s.inv(s.smooth(zr, 1.0, 1.05)))
    chev = s.mul(rx.hazard(s, xr, zr, period=0.34, slope=1.1, chevron=True, soft=0.07), band)
    edge = s.rim((0.5, 0.95))
    return s.emit_sum([(AMBER, s.mul(chev, s.inv(edge), 0.7 * GAIN)), (STEEL, s.mul(edge, 0.8 * GAIN))])


def beacon_mat():
    """Alarm beacon domes: glow brighter while their beam faces the viewer side (a smooth cos^2, never a flash)."""
    s = vj.Shader("Beacon")
    _, alpha, _ = s.obj_info()                                       # phase offset per beacon
    face = s.math("COSINE", s.mul(s.add(s.c("Beam"), alpha), 2 * math.pi))
    lvl = s.madd(s.mul(s.add(face, 1.0), s.add(face, 1.0)), 0.15, 0.25)
    return s.emit(ALARM, s.mul(lvl, s.core(0.5, 1.3), 1.4 * GAIN))


def sign_mat():
    s = vj.Shader("Sign")
    lvl = s.add(0.55, s.mul(s.c("Kick"), 0.25), s.mul(s.c("Swell"), 0.35))
    return s.emit(ALARM, s.mul(lvl, s.core(0.5, 1.3), 1.5 * GAIN))


# ------------------------------------------------------------------ geometry
def mass_obj(heave):
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=96, v_segments=48, radius=1.0)
    bmesh.ops.scale(bm, vec=MASS, verts=bm.verts)
    for v in bm.verts:                                              # lumps (static)
        p = v.co
        n = 0.12 * math.sin(2.1 * p.x + 1.3) * math.cos(1.7 * p.y + 0.4) + 0.08 * math.sin(3.3 * p.y - 2.0 * p.x)
        v.co = p + p.normalized() * n
    ob = vj.new_obj("Corium", bm, mass_mat())
    ob.data.shade_smooth()
    tex = bpy.data.textures.new("Heave", type="CLOUDS")
    tex.noise_scale = 1.3
    mod = ob.modifiers.new("Heave", "DISPLACE")
    mod.texture = tex
    mod.texture_coords = "OBJECT"
    mod.texture_coords_object = heave
    mod.direction = "NORMAL"
    mod.mid_level = 0.5
    vj.keyed(mod, "strength", [(f, 0.42 + 0.14 * vj.clock(f)["kick"] + 0.1 * vj.swell(f)) for f in vj.EXT])
    return ob


def head_bm():
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=96, v_segments=48, radius=1.0)
    bmesh.ops.delete(bm, geom=[v for v in bm.verts if v.co.z > 0.001], context="VERTS")
    bmesh.ops.scale(bm, vec=(R_V, R_V, HEAD_DEPTH), verts=bm.verts)
    return bm


def wall_bm():
    """The back half of the vessel's upper shell (seen from inside), from the rim up past the frame."""
    bm = bmesh.new()
    n, rows = 48, 12
    grid = []
    for r in range(rows + 1):
        z = 9.0 * r / rows
        grid.append([bm.verts.new((R_V * math.cos(math.pi * i / n), R_V * math.sin(math.pi * i / n), z))
                     for i in range(n + 1)])
    for r in range(rows):
        for i in range(n):
            bm.faces.new((grid[r][i], grid[r][i + 1], grid[r + 1][i + 1], grid[r + 1][i]))
    return bm


def cut_edges_bm():
    """The cut edges of the shell (two vertical lines) and the rim's back half seen inside."""
    bm = bmesh.new()
    for sx in (-1, 1):
        rx.stroke(bm, [Vector((sx * R_V, -0.05, z)) for z in (0.2, 3.0, 6.0, 9.0)], 0.05)
    return bm


def gauge(name, cx, label, which, rig):
    """A gauge facing the camera at (cx, GAUGE_Y, GAUGE_Z) in the rig: a dark face, bezel rings, 0-10 ticks on a
    270 deg sweep, a red zone, numerals 0 / 5 / 10 and a label; returns the needle's pivot (an empty)."""
    y = GAUGE_Y
    off = (cx, GAUGE_Z)
    face = vj.new_obj(f"{name}Face", vj.disc_bm(GAUGE_R, 64), dial_mat(), rig)
    face.location = (cx, y + 0.06, GAUGE_Z)
    lines = bmesh.new()
    rx.stroke(lines, rx.xz(rx.circle2(GAUGE_R, 96), y, 1.0, off), 0.03, segs=6, closed=True)
    rx.stroke(lines, rx.xz(rx.circle2(GAUGE_R - 0.07, 96), y, 1.0, off), 0.012, segs=5, closed=True)
    a0, a1 = SWEEP
    for k in range(51):
        a = math.radians(a0 + (a1 - a0) * k / 50)
        major = k % 5 == 0
        r0 = GAUGE_R - (0.24 if major else 0.17)
        r1 = GAUGE_R - 0.12
        rx.stroke(lines, rx.xz([(r0 * math.cos(a), r0 * math.sin(a)), (r1 * math.cos(a), r1 * math.sin(a))], y, 1.0,
                               off), 0.014 if major else 0.008, segs=4)
    for val, txt in ((0.0, "0"), (0.5, "5"), (1.0, "10")):
        a = math.radians(a0 + (a1 - a0) * val)
        rr = GAUGE_R - 0.38
        rx.text_strokes(lines, txt, 0.13, y, (cx + rr * math.cos(a), GAUGE_Z + rr * math.sin(a) - 0.065), r=0.01,
                        track=0.15)
    rx.text_strokes(lines, label, 0.11, y, (cx, GAUGE_Z - 0.48), r=0.01, track=0.25)
    vj.new_obj(f"{name}Lines", lines, gauge_line_mat(), rig)
    red = bmesh.new()
    rz = rx.arc2(GAUGE_R - 0.19, a0 + (a1 - a0) * RED_ZONE, a1, 20)
    rx.stroke(red, rx.xz(rz, y - 0.01, 1.0, off), 0.035, segs=6)
    vj.new_obj(f"{name}Red", red, red_zone_mat(), rig)
    pivot = vj.new_empty(f"{name}Pivot", rig)
    pivot.location = (cx, y - 0.04, GAUGE_Z)
    nb = bmesh.new()
    vj.tube(nb, [Vector((-0.16, 0, 0)), Vector((0.0, 0, 0)), Vector((GAUGE_R - 0.16, 0, 0))],
            lambda u: 0.034 * (1.0 - u) + 0.006, segs=6)
    bmesh.ops.create_icosphere(nb, subdivisions=2, radius=0.06)
    vj.new_obj(f"{name}Needle", nb, needle_mat(), pivot)
    vj.keyed(pivot, "rotation_euler",
             [(f, (0.0, -math.radians(a0 + (a1 - a0) * needle_value(f, which)), 0.0)) for f in vj.EXT])
    return pivot


def rods_bm():
    bm = bmesh.new()
    for x in ROD_X:
        pts = [Vector((x, 0.0, 0.25 * (1 - math.cos(math.radians(90 * k / 6))))) for k in range(7)]
        rads = [max(0.25 * math.sin(math.radians(90 * k / 6)), 0.004) for k in range(7)]
        pts += [Vector((x, 0.0, 0.25 + 9.0 * k / 4)) for k in range(1, 5)]
        rads += [0.25] * 4
        vj.tube(bm, pts, lambda u, rads=rads: rads[min(int(round(u * (len(rads) - 1))), len(rads) - 1)], segs=16)
    return bm


# ------------------------------------------------------------------ scene
def build():
    scene = vj.reset_scene()
    vj.clock_from(signals)
    ext = vj.EXT
    rng = random.Random(17)

    heave = vj.new_empty("HeaveCoords")                             # the heave texture circles once per loop
    vj.keyed(heave, "location", [(f, (0.9 * math.cos(2 * math.pi * f / vj.FRAMES),
                                      0.6 * math.sin(2 * math.pi * f / vj.FRAMES),
                                      0.5 * math.sin(2 * math.pi * f / vj.FRAMES))) for f in ext])
    mass_obj(heave)
    vj.new_obj("LowerHead", head_bm(), head_mat())
    lip = bmesh.new()
    vj.tube(lip, vj.circle_pts(Vector((0, 0, 0)), R_V, 128, axis="Z"), lambda u: 0.11, segs=10, closed=True)
    vj.new_obj("Lip", lip, lip_mat())
    vj.new_obj("VesselWall", wall_bm(), wall_mat())
    vj.new_obj("CutEdges", cut_edges_bm(), gauge_line_mat())

    for z0, y0, seed in ((0.0, -0.6, 0.0), (0.0, 1.2, 3.0)):         # heat shimmer layers over the mass
        bm = bmesh.new()
        bm.faces.new([bm.verts.new(p) for p in ((-3.8, y0, 1.0), (3.8, y0, 1.0), (3.8, y0, 6.0), (-3.8, y0, 6.0))])
        vj.new_obj(f"Shimmer{int(seed)}", bm, shimmer_mat(seed))

    em = ember_mat()
    me = rx.ico_mesh("Ember", 1)
    hot, cool = V["embers"]
    for i in range(150):
        ob = vj.mesh_obj(f"Ember{i:03d}", me, em)
        born, life = rng.uniform(0, vj.FRAMES), rng.uniform(55, 140)
        a = rng.uniform(0, 2 * math.pi)
        r = 3.0 * math.sqrt(rng.random())
        x0, y0 = r * math.cos(a), r * math.sin(a) * 0.6
        z0 = MASS[2] * math.sqrt(max(1 - (x0 / MASS[0]) ** 2 - (y0 / MASS[1]) ** 2, 0.05)) * 0.85
        vz, sway, sp, ph = rng.uniform(0.022, 0.055), rng.uniform(0.15, 0.6), rng.uniform(30, 70), rng.uniform(0, 6.3)
        drift = rng.uniform(-0.012, 0.012)
        size, lvl = rng.uniform(0.025, 0.06), rng.uniform(0.5, 1.0)

        def state(f, born=born, life=life, x0=x0, y0=y0, z0=z0, vz=vz, sway=sway, sp=sp, ph=ph, drift=drift,
                  size=size, lvl=lvl):
            age = (f - born) % vj.FRAMES
            if age >= life:
                return (x0, y0, z0), 1e-4, (0, 0, 0, 0.0)
            k = age / life
            p = (x0 + drift * age + sway * math.sin(age / sp * 2 * math.pi + ph), y0,
                 z0 + vz * age + 0.0002 * age * age)
            fade = min(age / 6.0, 1.0) * (1.0 - rx.ramp_between(k, 0.55, 1.0)) * (1.0 - scram(f))
            col = tuple(c0 + (c1 - c0) * min(k * 1.4, 1.0) for c0, c1 in zip(hot, cool))
            return p, size * (1.0 - 0.6 * k) * max(fade, 1e-3) ** 0.3, (*col, lvl * fade)
        rx.particle_keys(ob, ext, state)


    if V["scram"]:
        rods = vj.new_obj("ScramRods", rods_bm(), rod_mat())
        vj.keyed(rods, "location", [(f, (0.0, 0.0, rods_tip(f))) for f in ext])
    if V["beacons"]:
        bm_ = beacon_mat()
        for k, sx in enumerate((-1, 1)):
            dome = bmesh.new()
            bmesh.ops.create_uvsphere(dome, u_segments=24, v_segments=12, radius=0.26)
            bmesh.ops.delete(dome, geom=[v for v in dome.verts if v.co.z < -0.001], context="VERTS")
            ob = vj.new_obj(f"Beacon{k}", dome, bm_)
            ob.location = (sx * (R_V + 0.15), -0.3, 3.65)
            ob.color = (1, 1, 1, 0.5 * k)
    if V["sign"]:
        sb = bmesh.new()
        rx.text_strokes(sb, "CRITICAL", 0.45, -1.0, (0.0, 3.45), r=0.032, track=0.24)
        vj.new_obj("Sign", sb, sign_mat())

    cam = vj.camera(scene, lens=32.0, clip=(0.5, 200.0))
    loc, rot = [], []
    for f in ext:
        a = 2 * math.pi * f / vj.FRAMES
        j = vj.jolt(f) * (1.0 + 0.6 * vj.section(f))
        p = Vector((0.4 * math.sin(a), -14.0 + 0.4 * (1 - math.cos(a)), 2.35 + 0.15 * math.sin(2 * a)))
        e = vj.look_at(p, Vector((0.25 * math.sin(a + 1.0), 0.0, 0.95)), roll=0.5 * math.sin(a + 0.3))
        loc.append((f, tuple(p)))
        rot.append((f, (e.x - math.radians(0.3 * j), e.y, e.z)))
    vj.keyed(cam, "location", loc)
    vj.keyed(cam, "rotation_euler", rot)
    rig = vj.new_empty("GaugeRig", cam)                             # the gauges ride with the camera: fixed at the
    rig.location = (0.0, 0.0, -HUD_D)                               # frame sides, inside the safe area
    rig.rotation_euler = (-math.pi / 2, 0.0, 0.0)
    rig.scale = (HUD_SCALE,) * 3
    gauge("GaugeL", -GAUGE_X, "TEMP", 0, rig)
    gauge("GaugeR", GAUGE_X, "FLUX", 1, rig)
    return scene


scene = build()
vj.standard_render(scene)
vj.finish(scene, f"meltdown_{VNAME}")
