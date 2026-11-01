"""HELLGATE - GRAVEYARD SHIFT VJ loop (drop). 8 bars, seamless, 1920x1080 @ 30 fps; tempo from vjkit
(140 BPM half-time = 411 frames).

A huge wrought-iron cemetery gate between stone pillars crowned with skulls; on the iron arch above it, ABANDON HOPE
in our own letterforms. Each leaf is a riveted iron panel below and spear-tipped bars above, black, rim-lit by the
fire behind.
  Downbeat (frame 0): the gates fly open (eight frames, slamming against their stops) and hellfire rolls out: flame
            clouds billow through the opening toward the camera, the fire behind roars up over the walls.
  Bars 1-5  the fire roars and sways with a wobble (one cycle per bar), embers rise, the camera wobbles and thumps on
            the kick and the snare.
  Bars 6-8  the gates swing shut, the fire sinks to a glow leaking through the seam between the leaves; over the last
            two beats it builds behind the rattling gate into the next burst.
Fire is orange and red, never white (the ramp tops out at a deep orange). Beat hooks: the gates on the downbeat,
wobble per bar, camera thumps and soft fire lifts on the accents.
No strobing: the burst rises over the gate's swing (several frames) and stays up (no flash), puffs fade before the lens,
the fire stays under the block cap.

  blender.exe -b --factory-startup --python hellgate.py -- --frames 0,6,100,330 [--pct 50] [--samples 16]
  blender.exe -b --factory-startup --python hellgate.py -- --all --seam DIR [--out DIR] [--mblur]
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
from vjkit import BLOOD, EMBER, PUMPKIN, TOXIC  # noqa: E402

FIRE_RAMP = [(0.0, (0.0, 0.0, 0.0)), (0.15, (0.1, 0.003, 0.0)), (0.35, (0.5, 0.025, 0.002)),
             (0.6, (0.95, 0.11, 0.007)), (0.82, (1.0, 0.2, 0.014)), (1.0, (1.0, 0.27, 0.024))]
VARIANTS = {
    "inferno": dict(fire=FIRE_RAMP, rim=(1.0, 0.2, 0.012), eyes=(1.0, 0.1, 0.005), fire_gain=0.9),
}
VNAME, V = vj.variant(VARIANTS)
GAIN = float(vj.arg("--gain", 1.0))

CAM = Vector((0.0, -15.0, 2.0))
AIM = Vector((0.0, 0.0, 4.7))
HINGE = 4.0                               # leaves hinge at x = +-4 (an 8 m opening)
OPEN = 100.0                              # degrees
FLOW_T = vj.FRAMES // 3                   # 137 frames: the fire's flow cycle (divides the loop)
B_CLOSE0, B_CLOSE1 = 20, 30               # beats: the gates swing shut over bars 6-8 (until beat 3 of bar 8)


# ------------------------------------------------------------------ choreography
def gate_angle(f):
    """Opening angle (deg) of the leaves: burst open on frame 0 with a slam bounce, shut over bars 6-8, closed (and
    rattling as the fire builds) over the last two beats."""
    f %= vj.FRAMES
    c0, c1 = vj.BEAT_F[B_CLOSE0], vj.BEAT_F[B_CLOSE1]
    if f <= 8:
        u = f / 8.0
        return OPEN * (1.0 - (1.0 - u) ** 3) * (1.0 + 0.05 * math.sin(math.pi * u))
    if f <= 14:
        return OPEN * (1.0 + 0.035 * math.sin(math.pi * (f - 8) / 6.0) * math.exp(-(f - 8) / 4.0))
    if f < c0:
        return OPEN + 1.2 * math.sin(2 * math.pi * vj.beatpos(f) / 4.0)
    if f < c1:
        return OPEN * (1.0 - vj.ease((f - c0) / (c1 - c0))) + 1.2 * math.sin(2 * math.pi * vj.beatpos(f) / 4.0) * \
            (1.0 - (f - c0) / (c1 - c0))
    sw = ((f - c1) / (vj.FRAMES - c1)) ** 2                           # rattling against the latch
    return 1.4 * sw * (0.5 + 0.5 * math.sin(2 * math.pi * f / 3.0))


def fire_level(f):
    """How hard the fire burns: 1 while the gates are open (a surge as they burst), sinking to 0.35 as they shut,
    building to ~0.8 over the last two beats."""
    f %= vj.FRAMES
    c0, c1 = vj.BEAT_F[B_CLOSE0], vj.BEAT_F[B_CLOSE1]
    if f <= 6:
        return 0.85 + 0.3 * vj.ease(f / 6.0)
    if f < c0:
        return 1.0 + 0.15 * math.exp(-(f - 6) / 10.0)
    if f < c1:
        return 1.0 - 0.55 * vj.ease((f - c0) / (c1 - c0))
    return 0.45 + 0.4 * ((f - c1) / (vj.FRAMES - c1)) ** 1.6


def wobble(f):
    """The drop's wobble: one cycle per bar, full in bars 1-5, fading out as the gates shut."""
    b = vj.beatpos(f % vj.FRAMES)
    amt = 1.0 if b < B_CLOSE0 else max(0.0, 1.0 - (b - B_CLOSE0) / 6.0)
    return amt * math.sin(2 * math.pi * b / 4.0), amt


def signals(f):
    c = vj.clock(f)
    p = (f % FLOW_T) / FLOW_T
    w, amt = wobble(f)
    open_frac = gate_angle(f) / OPEN
    s = {"Kick": c["kick"], "Swell": vj.swell(f), "Fire": fire_level(f), "Wob": w, "WobAmt": amt,
         "FlowA": p, "FlowB": (p + 0.5) % 1.0, "FlowW": 1.0 - abs(2.0 * p - 1.0),
         "Closed": max(0.0, 1.0 - min(open_frac, 1.0) * 4.0)}
    s.update(vj.loop_signals(f))
    return s


# ------------------------------------------------------------------ materials
def fire_noise(s, x, z, scale_x, scale_z, rise, seed=0.0):
    """Rising flame noise: two flow layers offset upward and cross-faded (seamless over FLOW_T), swayed by the
    wobble."""
    sway = s.mul(s.c("Wob"), 0.5)
    def layer(flow):
        v = s.vec(s.mul(s.add(x, sway), scale_x), s.mul(s.sub(z, s.mul(s.c(flow), rise)), scale_z), seed)
        return s.noise4(v, s.mul(s.c("LoopSin"), 0.4), scale=1.0, detail=5.0, rough=0.58, distortion=0.25)
    return s.add(s.mul(layer("FlowA"), s.c("FlowW")), s.mul(layer("FlowB"), s.inv(s.c("FlowW"))))


def fire_wall_mat():
    s = vj.Shader("FireWall")
    x, _, z = s.world_pos()
    n = fire_noise(s, x, z, 0.42, 0.17, 9.0)
    n = s.madd(s.sub(n, 0.5), 2.2, 0.5)                               # restore contrast lost in the cross-fade
    height = s.madd(s.c("Fire"), 13.0, 3.0)                           # flames reach ~4 m (embers) .. ~16 m (roar)
    f = s.sub(s.sub(s.mul(n, 1.15), s.math("DIVIDE", z, height)), 0.1)
    heat = s.smooth(f, 0.0, 0.9)
    col = s.ramp(heat, V["fire"])
    lift = s.add(0.85, s.mul(s.c("Kick"), 0.1), s.mul(s.c("Swell"), 0.2))
    return s.emit(col, s.mul(lift, s.math("MINIMUM", s.c("Fire"), 1.1), 0.95 * V["fire_gain"] * GAIN))


def sky_mat():
    """The sky over hell: smoke lit from below by the fire (dark red), black higher up."""
    s = vj.Shader("Sky")
    x, _, z = s.world_pos()
    n = fire_noise(s, x, z, 0.06, 0.08, 6.0, seed=3.0)
    glow = s.mul(s.exp(s.mul(s.math("MAXIMUM", s.sub(z, 6.0), 0.0), -1.0 / 9.0)), s.smooth(n, 0.35, 0.8))
    return s.emit((1.0, 0.05, 0.01), s.mul(glow, s.madd(s.c("Fire"), 0.6, 0.15), 0.3 * GAIN))


def iron_mat():
    """Black iron, rim-lit by the fire behind: the rim follows the fire level."""
    s = vj.Shader("Iron")
    lift = s.mul(s.madd(s.c("Fire"), 0.8, 0.25), s.add(1.0, s.mul(s.c("Kick"), 0.1)))
    return s.emit(V["rim"], s.mul(s.rim((0.5, 0.96)), lift, 1.1 * GAIN))


def stone_mat():
    s = vj.Shader("Stone")
    lift = s.madd(s.c("Fire"), 0.7, 0.2)
    return s.emit(V["rim"], s.mul(s.rim((0.6, 0.97)), lift, 0.5 * GAIN))


def letters_mat():
    """Hot iron letters: a steady ember glow plus the fire's rim."""
    s = vj.Shader("Letters")
    lift = s.madd(s.c("Fire"), 0.7, 0.3)
    return s.emit(V["rim"], s.mul(s.add(s.mul(s.rim((0.4, 0.95)), 0.7), 0.45), s.core(0.6, 1.3), lift, 1.2 * GAIN))


def eyes_mat():
    s = vj.Shader("SkullEyes")
    lift = s.add(s.madd(s.c("Fire"), 0.7, 0.2), s.mul(s.c("Kick"), 0.2), s.mul(s.c("Swell"), 0.4))
    return s.emit(V["eyes"], s.mul(lift, s.core(0.6, 1.4), 1.8 * GAIN))


def crack_mat():
    """Light leaking through the seam between the closed leaves and under the gate."""
    s = vj.Shader("Crack")
    x, _, z = s.obj_coords()
    seam = s.gauss(x, 0.0, 0.07)
    return s.additive((1.0, 0.2, 0.012), s.mul(seam, s.c("Closed"), s.c("Fire"), s.add(1.0, s.mul(s.c("Swell"), 1.0)),
                                              2.6 * GAIN))


def ground_mat():
    """Cobbles in front of the gate lit by the fire from the opening; cracks of glowing ground beyond it."""
    s = vj.Shader("Ground")
    x, y, _ = s.world_pos()
    vor = s.node("ShaderNodeTexVoronoi", feature="DISTANCE_TO_EDGE")
    s.put(vor.inputs["Vector"], s.vec(s.mul(x, 1.3), s.mul(y, 1.3), 0.0))
    stones = s.smooth(vor.outputs["Distance"], 0.03, 0.12)
    lit = s.exp(s.mul(s.add(s.mul(x, x), s.mul(s.math("MAXIMUM", s.mul(y, -1.0), 0.0), 0.0)), -1.0 / 40.0))
    toward = s.exp(s.mul(s.math("MAXIMUM", s.mul(y, -1.0), 0.0), -1.0 / 6.0))
    open_lit = s.inv(s.c("Closed"))
    front = s.mul(stones, lit, toward, s.madd(open_lit, 0.85, 0.15), s.c("Fire"), 0.05)
    beyond = s.mul(s.smooth(y, 0.5, 2.5), s.inv(stones), s.c("Fire"), 0.35)
    return s.emit_sum([(V["rim"], s.mul(front, GAIN)), ((1.0, 0.12, 0.006), s.mul(beyond, GAIN))])


def front_mat():
    """A rolling flame front: a sheet standing on the ground whose flames lick up from its bottom edge (the fire
    wall's flames in the sheet's own coordinates, seeded per sheet). Object color R = flame height (m), A = opacity."""
    s = vj.Shader("FlameFront")
    col, alpha, rnd = s.obj_info()
    hgt, _, _ = s.xyz(col)
    x, _, zc = s.obj_coords()
    z = s.add(zc, 3.5)                                                  # meters above the sheet's bottom edge
    n = fire_noise(s, x, z, 0.5, 0.26, 7.0, seed=s.mul(rnd, 50.0))
    n = s.madd(s.sub(n, 0.5), 2.2, 0.5)
    f = s.sub(s.sub(s.mul(n, 1.1), s.math("DIVIDE", z, s.math("MAXIMUM", hgt, 0.1))), 0.2)
    sides = s.inv(s.smooth(s.math("ABSOLUTE", x), 2.6, 4.2))          # the sheet's ends burn out
    heat = s.mul(s.smooth(f, 0.0, 0.9), sides)
    return s.additive(s.ramp(heat, V["fire"]), s.mul(heat, alpha, 0.6 * GAIN))


def ember_mat():
    s = vj.Shader("Embers")
    _, alpha, _ = s.obj_info()
    return s.additive((1.0, 0.24, 0.02), s.mul(alpha, s.core(0.6, 1.4), s.madd(s.c("Fire"), 0.7, 0.3), 2.0 * GAIN))


# ------------------------------------------------------------------ geometry
def top_z(x):
    """The gate's arched top: 7.4 m at the center, 6.4 m at the hinges."""
    return 6.4 + 1.0 * math.cos(0.5 * math.pi * min(abs(x), HINGE) / HINGE)


def leaf_bms(side):
    """(iron bmesh, panel bmesh) of one leaf in hinge-local coordinates (hinge at the origin, the leaf spans toward
    the center, x in [-side * 4, 0] relative to the hinge)."""
    iron = bmesh.new()
    panel = bmesh.new()
    xs = lambda x: (x - side * HINGE)                                  # world x (closed) -> hinge-local x
    x_in, x_out = side * 0.04, side * (HINGE - 0.04)

    def pts(seq):
        return [Vector((xs(x), 0.0, z)) for x, z in seq]

    r_bar, r_rail = 0.045, 0.06
    g.stroke(iron, pts([(x_in, 0.12), (x_in, top_z(0.0) - 0.15)]), r_rail, segs=6)
    g.stroke(iron, pts([(x_out, 0.12), (x_out, top_z(HINGE) - 0.15)]), r_rail, segs=6)
    for z in (0.15, 3.55, 3.95):
        g.stroke(iron, pts([(x_in, z), (x_out, z)]), r_rail, segs=6, joints=False)
    arc = [(side * HINGE * t, top_z(HINGE * t) - 0.35) for t in [i / 16 for i in range(17)]]
    g.stroke(iron, pts(arc), r_rail, segs=6, joints=False)
    for k in range(12):                                                # bars with spear tips
        x = side * (0.27 + k * 0.315)
        zt = top_z(x) + 0.25
        g.stroke(iron, pts([(x, 3.55), (x, zt)]), r_bar, segs=6, joints=False)
        vj.tube(iron, pts([(x, zt), (x, zt + 0.32)]), lambda u: 0.11 * (1.0 - u) + 0.01 if u > 0.25 else
                0.04 + 0.28 * u, segs=6, tip=True)
        if k < 11:                                                     # scroll rings between the bars
            g.stroke(iron, pts(g.circle2(0.13, 16, x + side * 0.157, 4.5)), 0.022, segs=5, closed=True,
                     joints=False)
    # the riveted panel (solid, black) with a raised border and an emblem
    g.extrude(panel, [(xs(x_in), 0.15), (xs(x_out), 0.15), (xs(x_out), 3.55), (xs(x_in), 3.55)], 0.06, y0=-0.03)
    bx0, bx1 = side * 0.35, side * (HINGE - 0.35)
    g.stroke(iron, pts([(bx0, 0.45), (bx1, 0.45), (bx1, 3.25), (bx0, 3.25)]), 0.035, segs=5, closed=True,
             joints=False)
    cx = side * HINGE / 2
    for rr in (0.75, 0.5):
        g.stroke(iron, pts(g.circle2(rr, 40, cx, 1.85)), 0.035, segs=5, closed=True, joints=False)
    for a in range(8):
        ang = math.radians(45 * a + 22.5)
        g.stroke(iron, pts([(cx + 0.5 * math.cos(ang), 1.85 + 0.5 * math.sin(ang)),
                            (cx + 0.75 * math.cos(ang), 1.85 + 0.75 * math.sin(ang))]), 0.03, segs=5, joints=False)
    for z in (0.3, 3.4):                                               # rivets
        for k in range(9):
            x = side * (0.2 + k * (HINGE - 0.4) / 8)
            bmesh.ops.create_icosphere(iron, subdivisions=1, radius=0.05,
                                       matrix=Matrix.Translation((xs(x), -0.05, z)))
    return iron, panel


def skull_outline(scale):
    """Front silhouette of a skull (local origin at its base): cranium arc, cheekbones, jaw."""
    half = [(0.0, 1.04)]
    for i in range(1, 13):
        a = math.radians(90 - 120 * i / 12)
        half.append((0.42 * math.cos(a), 0.62 + 0.42 * math.sin(a)))
    half += [(0.33, 0.33), (0.25, 0.22), (0.23, 0.06), (0.12, 0.0), (0.0, 0.0)]
    pts = g.mirrored(list(reversed([(x, y) for x, y in half])))
    return [(x * scale, y * scale) for x, y in pts]


def skull_bm(scale=1.0):
    """The skull icon extruded 0.35 m (rim-lit outline); sockets and nose are separate black shapes in front."""
    bm = bmesh.new()
    g.extrude(bm, skull_outline(scale), 0.35 * scale, y0=-0.175 * scale)
    return bm


def sockets_bm(scale=1.0):
    bm = bmesh.new()
    for sx in (-1, 1):
        g.extrude(bm, [(sx * 0.16 * scale + 0.12 * scale * math.cos(a), 0.52 * scale + 0.13 * scale * math.sin(a))
                       for a in [2 * math.pi * i / 20 for i in range(20)]], 0.0, y0=-0.2 * scale, front_only=True)
    g.extrude(bm, [(-0.06 * scale, 0.4 * scale), (0.06 * scale, 0.4 * scale), (0.0, 0.29 * scale)], 0.0,
              y0=-0.2 * scale, front_only=True)
    return bm


def eyes_bm(scale=1.0):
    bm = bmesh.new()
    for sx in (-1, 1):
        bmesh.ops.create_icosphere(bm, subdivisions=2, radius=0.045 * scale,
                                   matrix=Matrix.Translation((sx * 0.16 * scale, -0.23 * scale, 0.5 * scale)))
    return bm


def arch_sign(iron, lett):
    """The iron arch over the gate with ABANDON HOPE between two rails, letters following the arc."""
    R0, cz = 6.2, 3.3                                                  # arc center below, the rails at R0, R0 + 0.62
    for rr in (R0, R0 + 0.62):
        a0 = math.asin(4.45 / rr)
        pts = [Vector((rr * math.sin(a), -0.2, cz + rr * math.cos(a))) for a in
               [-a0 + 2 * a0 * i / 40 for i in range(41)]]
        g.stroke(iron, pts, 0.06, segs=6, joints=False)
    text = "ABANDON HOPE"
    h = 0.4
    width = letters.text_width(text, track=0.28) * h
    rm = R0 + 0.11
    for ch, strokes in letters.layout(text, h, track=0.28):
        for st in strokes:
            pts = []
            for x, y in st:
                a = x / rm                                             # arc length -> angle
                rr = rm + y
                pts.append(Vector((rr * math.sin(a), -0.22, cz + rr * math.cos(a))))
            g.stroke(lett, pts, 0.035, segs=6)
    return width


# ------------------------------------------------------------------ scene
def build():
    scene = vj.reset_scene()
    vj.clock_from(signals)
    ext = vj.EXT

    fire = vj.new_obj("FireWall", vj.quad_bm(44.0, 22.0), fire_wall_mat())
    fire.location = (0.0, 9.0, 10.0)
    sky = vj.new_obj("Sky", vj.quad_bm(140.0, 60.0), sky_mat())
    sky.location = (0.0, 40.0, 25.0)

    iron_m, stone_m = iron_mat(), stone_mat()
    black = vj.black_mat("Panel")
    for side in (-1, 1):
        hinge = vj.new_empty(f"Hinge{side}")
        hinge.location = (side * HINGE, 0.0, 0.0)
        ib, pb = leaf_bms(side)
        vj.new_obj(f"Leaf{side}", ib, iron_m, hinge)
        pan = vj.new_obj(f"Panel{side}", pb, black, hinge)
        vj.keyed(hinge, "rotation_euler", [(f, (0.0, 0.0, math.radians(-side * gate_angle(f)))) for f in ext])  # away from the camera

    st = bmesh.new()
    for side in (-1, 1):                                              # pillars with capstones
        x0, x1 = side * 4.06, side * 5.7
        g.extrude(st, [(x0, 0.0), (x1, 0.0), (x1, 8.1), (x0, 8.1)], 1.6, y0=-0.8)
        g.extrude(st, [(x0 - side * 0.15, 8.1), (x1 + side * 0.15, 8.1), (x1 + side * 0.15, 8.55),
                       (x0 - side * 0.15, 8.55)], 1.9, y0=-0.95)
        g.extrude(st, [(side * 5.7, 0.0), (side * 15.0, 0.0), (side * 15.0, 3.0), (side * 5.7, 3.0)], 0.7, y0=-0.2)
    vj.new_obj("Stone", st, stone_m)
    fence = bmesh.new()
    for side in (-1, 1):                                              # iron spikes along the walls
        for k in range(26):
            x = side * (6.0 + k * 0.35)
            g.stroke(fence, [Vector((x, 0.0, 3.0)), Vector((x, 0.0, 4.1))], 0.03, segs=5, joints=False)
            vj.tube(fence, [Vector((x, 0.0, 4.1)), Vector((x, 0.0, 4.35))], lambda u: 0.07 * (1 - u) + 0.005, segs=5,
                    tip=True)
        g.stroke(fence, [Vector((side * 5.9, 0.0, 3.85)), Vector((side * 15.0, 0.0, 3.85))], 0.03, segs=5,
                 joints=False)
    vj.new_obj("Fence", fence, iron_m)
    iron, lett = bmesh.new(), bmesh.new()
    arch_sign(iron, lett)
    vj.new_obj("ArchIron", iron, iron_m)
    vj.new_obj("ArchLetters", lett, letters_mat())
    sm, em = vj.black_mat("SkullSockets"), eyes_mat()
    for side in (-1, 1):
        sk = vj.new_obj(f"Skull{side}", skull_bm(1.3), iron_m)
        sk.location = (side * 4.88, -0.1, 8.55)
        vj.new_obj(f"Sockets{side}", sockets_bm(1.3), sm).location = sk.location
        vj.new_obj(f"Eyes{side}", eyes_bm(1.3), em).location = sk.location

    crack = vj.new_obj("Crack", vj.quad_bm(0.6, 7.2), crack_mat())
    crack.location = (0.0, 0.12, 3.6)

    ground = vj.new_obj("Ground", vj.quad_bm(60.0, 60.0, axis="Z"), ground_mat())
    ground.location = (0.0, 0.0, 0.0)

    rnd = random.Random(13)
    fm = front_mat()
    spawns = [(0.0, True), (4.0, True)]                                 # the burst: two big fronts
    for k in range(1, B_CLOSE0 // vj.ACC):                              # one on each accent of bars 1-5
        spawns.append((float(vj.BEAT_F[k * vj.ACC]), False))
    for i, (s0, big) in enumerate(spawns):
        life = 34.0 if big else 28.0
        x0 = rnd.uniform(-0.8, 0.8)
        y0, y1 = 3.2, (-3.0 if big else -1.5)
        h0 = 7.0 if big else 4.6
        ob = vj.new_obj(f"Front{i}", vj.quad_bm(9.0, 7.0), fm)
        locs, cols = [], []
        for f in ext:
            age = (f - s0) % vj.FRAMES
            if age < life:
                u = age / life
                y = y0 + (y1 - y0) * (1.0 - (1.0 - u) ** 1.7)
                hgt = h0 * (0.55 + 0.45 * math.sin(math.pi * min(u * 1.6, 1.0))) * (1.0 - 0.6 * u)
                a = min(age / 3.0, 1.0) * (1.0 - u) ** 1.2 * (1.0 if big else 0.75)
            else:
                y, hgt, a = y0, 0.1, 0.0
            locs.append((f, (x0, y, 3.5)))
            cols.append((f, (hgt, 0.0, 0.0, a)))
        vj.keyed(ob, "location", locs)
        vj.keyed(ob, "color", cols)

    emb = ember_mat()
    for i in range(90):
        s0, life = rnd.uniform(0, vj.FRAMES), rnd.uniform(90, 200)
        p0 = Vector((rnd.uniform(-9, 9), rnd.uniform(1.5, 8.0), rnd.uniform(0.2, 2.5)))
        p1 = p0 + Vector((rnd.uniform(-2, 2), rnd.uniform(-9, -3), rnd.uniform(5, 10)))
        bm = bmesh.new()
        bmesh.ops.create_icosphere(bm, subdivisions=1, radius=rnd.uniform(0.025, 0.05))
        ob = vj.new_obj(f"Ember{i}", bm, emb)
        sw = rnd.uniform(0, 6.28)
        locs, cols = [], []
        for f in ext:
            age = (f - s0) % vj.FRAMES
            if age < life:
                u = age / life
                p = p0.lerp(p1, u) + Vector((0.5 * math.sin(age / 11.0 + sw), 0.0, 0.0))
                a = math.sin(math.pi * u) ** 1.2
            else:
                p, a = p0, 0.0
            locs.append((f, tuple(p)))
            cols.append((f, (1.0, 1.0, 1.0, a)))
        vj.keyed(ob, "location", locs)
        vj.keyed(ob, "color", cols)

    cam = vj.camera(scene, lens=26.0, clip=(0.3, 300.0))
    loc, rot, lens = [], [], []
    for f in ext:
        a = 2 * math.pi * f / vj.FRAMES
        w, amt = wobble(f)
        j = vj.jolt(f, decay=3.0, period=5.0) * (0.35 + 0.65 * amt)
        p = CAM + Vector((0.35 * math.sin(a), 0.0, 0.12 * math.sin(2 * a)))
        loc.append((f, tuple(p + Vector((0.0, 0.0, -0.06 * j)))))
        rot.append((f, tuple(vj.look_at(p, AIM + Vector((0.0, 0.0, 0.18 * j)), roll=1.1 * w))))
        burst = math.exp(-(f % vj.FRAMES) / 12.0) if (f % vj.FRAMES) > 2 else (f % vj.FRAMES) / 2.0
        lens.append((f, 26.0 * (1.0 + 0.025 * burst)))
    vj.keyed(cam, "location", loc)
    vj.keyed(cam, "rotation_euler", rot)
    vj.keyed(cam.data, "lens", lens)
    return scene


scene = build()
vj.standard_render(scene)
vj.finish(scene, f"hellgate_{VNAME}")
