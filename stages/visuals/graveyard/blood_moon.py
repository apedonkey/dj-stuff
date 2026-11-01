"""BLOOD MOON - GRAVEYARD SHIFT VJ loop (outro). 8 bars, seamless, 1920x1080 @ 30 fps; tempo from vjkit
(140 BPM half-time = 411 frames).

A huge blood moon fills the sky behind the cathedral's broken spires: dark maria and craters on a coppery-red disc,
clouds drifting across it (they travel exactly one cloud period per loop, so the drift is seamless), a ring of beads
around it. The cathedral stands in black silhouette, rim-lit by the moon: the left spire intact, the right one snapped,
a dim clock on the gable, faint candle-lit lancet windows. Bats cross the moon in loose flocks; two searchlights behind
the towers sway once per 2 bars.
Beat hooks: on every bar's downbeat a pulse of light runs round the bead ring from the top (both ways, meeting at the
bottom), the snare gives the ring a smaller lift; the moon breathes very softly on the kick and the snare; the last two
beats of bars 4 and 8 swell into the next phrase. Calm: the closing loop of the set.
No strobing: red is low luma, the moon stays under the block cap, the beams are faint.

  blender.exe -b --factory-startup --python blood_moon.py -- --frames 0,100,300 [--pct 50] [--samples 16]
  blender.exe -b --factory-startup --python blood_moon.py -- --all --seam DIR [--out DIR] [--mblur]
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
import bats  # noqa: E402
from vjkit import BLOOD, EMBER, MOONBLUE, PUMPKIN, TOXIC, UVP  # noqa: E402

MOON_RAMP = [(0.0, (0.02, 0.0, 0.0)), (0.35, (0.2, 0.006, 0.002)), (0.62, (0.62, 0.035, 0.008)),
             (0.85, (0.95, 0.09, 0.016)), (1.0, (1.0, 0.16, 0.03))]
VARIANTS = {
    "blood": dict(ramp=MOON_RAMP, rim=(1.0, 0.05, 0.02), beads=PUMPKIN, beams=(UVP, MOONBLUE), n_bats=16),
}
VNAME, V = vj.variant(VARIANTS)
GAIN = float(vj.arg("--gain", 1.0))

CAM = Vector((0.0, -50.0, 14.0))
CATH_Y = 20.0                                     # the facade plane: 70 m from the camera, towers in the lower third
MOON_C = Vector((0.0, 300.0, 75.0))
MOON_R = 75.0
CLOUD_P = 260.0                                   # cloud period across x (m): they drift one period per loop
N_BEADS = 40


# ------------------------------------------------------------------ music
def ring_pulse(f):
    """(position 0..1 of the pulse front from the top down to the bottom, intensity): runs round the ring on each
    bar's downbeat (over 2 beats), a smaller one on the snare."""
    c = vj.clock(f)
    b = c["beatpos"] - 4 * c["bar"]                                   # beats into the bar
    if b < 2.0:
        return b / 2.0, 1.0
    return (b - 2.0) / 2.0, 0.45


def signals(f):
    c = vj.clock(f)
    pos, amp = ring_pulse(f)
    s = {"Kick": c["kick"], "Swell": vj.swell(f, decay_beats=1.5), "RingPos": pos, "RingAmp": amp,
         "Drift": (f % vj.FRAMES) / vj.FRAMES}
    s.update(vj.loop_signals(f))
    return s


# ------------------------------------------------------------------ materials
def moon_mat():
    """Coppery-red disc: maria (low-frequency noise), craters (voronoi rims), a brighter lower-left limb (the eclipse
    light), limb darkening, and dark clouds drifting across it with red-lit edges."""
    s = vj.Shader("Moon")
    x, _, z = s.obj_coords()
    qx, qz = s.mul(x, 1.0 / MOON_R), s.mul(z, 1.0 / MOON_R)
    r = s.length2(qx, qz)
    maria = s.noise4(s.vec(s.mul(qx, 1.4), s.mul(qz, 1.4), 3.1), 0.7, scale=1.6, detail=5.0, rough=0.55)
    maria = s.smooth(maria, 0.42, 0.62)
    vor = s.node("ShaderNodeTexVoronoi", feature="DISTANCE_TO_EDGE")
    s.put(vor.inputs["Vector"], s.vec(s.mul(qx, 5.0), s.mul(qz, 5.0), 0.0))
    vor.inputs["Scale"].default_value = 1.0
    crater = s.inv(s.smooth(vor.outputs["Distance"], 0.0, 0.06))
    side = s.smooth(s.add(s.mul(qx, -0.7), s.mul(qz, -0.7)), -0.9, 0.9)   # brighter toward the lower left
    limb = s.inv(s.smooth(r, 0.75, 1.0))
    heat = s.add(0.38, s.mul(side, 0.42), s.mul(maria, -0.25), s.mul(crater, 0.07), s.mul(limb, 0.12))
    # clouds: noise on a cylinder around x (period CLOUD_P), turned once per loop -> they drift seamlessly
    xw, _, zw = s.world_pos()
    ang = s.mul(s.add(s.mul(xw, 1.0 / CLOUD_P), s.c("Drift")), 2 * math.pi)
    rc = CLOUD_P / (2 * math.pi) * 0.02
    cv = s.vec(s.mul(s.math("COSINE", ang), rc), s.mul(s.math("SINE", ang), rc), s.mul(zw, 0.025))
    cl = s.noise4(cv, s.mul(s.c("LoopSin"), 0.15), scale=1.0, detail=4.0, rough=0.6)
    dens = s.smooth(cl, 0.48, 0.66)
    band = s.gauss(zw, 52.0, 28.0)                                      # a band of cloud across the lower moon
    dens = s.mul(dens, s.madd(band, 0.75, 0.25))
    edge = s.mul(s.gauss(cl, 0.5, 0.035), s.madd(band, 0.7, 0.3))
    lift = s.add(1.0, s.mul(s.c("Kick"), 0.04), s.mul(s.c("Swell"), 0.12))
    col = s.ramp(s.math("MINIMUM", heat, 1.0), V["ramp"])
    body = s.mul(s.inv(s.mul(dens, 0.82)), lift, 0.92 * GAIN)
    return s.emit_sum([(col, body), (V["rim"], s.mul(edge, s.inv(dens), 0.35 * GAIN))])


def halo_mat():
    """A soft red glow around the moon (additive), falling off fast so the sky stays dark."""
    s = vj.Shader("Halo")
    x, _, z = s.obj_coords()
    r = s.mul(s.length2(x, z), 1.0 / MOON_R)
    out = s.smooth(r, 0.98, 1.02)
    glow = s.mul(s.exp(s.mul(s.math("MAXIMUM", s.sub(r, 1.0), 0.0), -9.0)), out)
    lift = s.add(1.0, s.mul(s.c("Swell"), 0.2))
    return s.additive(V["rim"], s.mul(glow, lift, 0.09 * GAIN))


def sky_mat():
    """Near-black purple sky with faint cloud banks and stars (static stars, clouds drifting like the moon's)."""
    s = vj.Shader("Sky")
    xw, _, zw = s.world_pos()
    ang = s.mul(s.add(s.mul(xw, 1.0 / CLOUD_P), s.c("Drift")), 2 * math.pi)
    rc = CLOUD_P / (2 * math.pi) * 0.02
    cl = s.noise4(s.vec(s.mul(s.math("COSINE", ang), rc), s.mul(s.math("SINE", ang), rc), s.mul(zw, 0.022)), 1.7,
                  scale=1.0, detail=4.0, rough=0.6)
    dens = s.smooth(cl, 0.45, 0.7)
    vor = s.node("ShaderNodeTexVoronoi", voronoi_dimensions="2D")
    s.put(vor.inputs["Vector"], s.vec(xw, zw, 0.0))
    vor.inputs["Scale"].default_value = 0.09
    rnd = s.xyz(vor.outputs["Color"])[0]
    star = s.mul(s.inv(s.smooth(vor.outputs["Distance"], 0.0, 0.05)), s.math("GREATER_THAN", rnd, 0.75),
                 s.inv(dens), 0.9 * GAIN)
    return s.emit_sum([(UVP, s.mul(dens, 0.022, GAIN)), ((1.0, 0.1, 0.05), s.mul(dens, 0.01, GAIN)),
                       ((0.8, 0.8, 1.0), star)])


def silhouette_mat():
    """Black stone, rim-lit red by the moon behind it (a thin edge glow), brighter toward the top."""
    s = vj.Shader("Stone")
    _, _, z = s.world_pos()
    up = s.smooth(z, 4.0, 30.0)
    lift = s.add(1.0, s.mul(s.c("Swell"), 0.25), s.mul(s.c("Kick"), 0.05))
    return s.emit(V["rim"], s.mul(s.rim((0.55, 0.97)), s.madd(up, 0.6, 0.4), lift, 1.3 * GAIN))


def window_mat():
    """Lancet windows lit by candles inside: per-window color (object color) and a slow flicker."""
    s = vj.Shader("Windows")
    col, alpha, rnd = s.obj_info()
    n = s.noise4(s.vec(s.mul(rnd, 37.0), s.c("LoopCos"), s.c("LoopSin")), s.mul(rnd, 11.0), scale=2.2, detail=1.0)
    flick = s.madd(s.smooth(n, 0.3, 0.7), 0.35, 0.65)
    x, _, z = s.obj_coords()
    return s.emit(col, s.mul(alpha, flick, s.add(1.0, s.mul(s.c("Swell"), 0.2)), 0.3 * GAIN))


def clock_mat():
    s = vj.Shader("GableClock")
    return s.emit(UVP, s.mul(s.core(0.5, 1.3), s.add(1.0, s.mul(s.c("Kick"), 0.1)), 0.7 * GAIN))


def beads_mat():
    """The bead ring: dim beads, a pulse front running down both sides from the top on every downbeat."""
    s = vj.Shader("Beads")
    x, _, z = s.obj_coords()
    a = s.math("DIVIDE", s.math("ABSOLUTE", s.math("ARCTAN2", x, z)), math.pi)   # 0 at the top, 1 at the bottom
    front = s.gauss(a, s.c("RingPos"), 0.07)
    trail = s.mul(s.math("LESS_THAN", a, s.c("RingPos")),
                  s.exp(s.mul(s.sub(s.c("RingPos"), a), -6.0)))
    level = s.add(0.22, s.mul(s.c("RingAmp"), s.add(s.mul(front, 1.4), s.mul(trail, 0.35))),
                  s.mul(s.c("Swell"), 0.3))
    return s.emit(V["beads"], s.mul(level, s.core(0.6, 1.4), 1.6 * GAIN))


def ring_line_mat():
    s = vj.Shader("RingLine")
    return s.emit(V["rim"], s.mul(s.core(0.5, 1.3), s.add(0.5, s.mul(s.c("Kick"), 0.15), s.mul(s.c("Swell"), 0.3)),
                                  0.5 * GAIN))


def beam_mat():
    """Searchlight beams: additive, color = object color, brightest at the lamp, soft edges."""
    s = vj.Shader("Beam")
    col, alpha, _ = s.obj_info()
    _, _, zl = s.obj_coords()                                           # meters along the beam
    along = s.exp(s.mul(zl, -1.0 / 70.0))
    edge = s.math("POWER", s.inv(s.facing()), 2.0)
    lift = s.add(0.85, s.mul(s.c("Swell"), 0.3))
    return s.additive(col, s.mul(alpha, along, edge, lift, 0.07 * GAIN))


# ------------------------------------------------------------------ the cathedral
def tower_outline(x0, x1, top, spire, broken_seed=None):
    """A tower in 2D: buttressed base, a parapet with corner pinnacles, and a spire (or its snapped stump)."""
    w = x1 - x0
    cx = (x0 + x1) / 2
    pts = [(x0 - 0.9, 0.0), (x0 - 0.9, 6.0), (x0 - 0.4, 7.5), (x0 - 0.4, 12.5), (x0, 13.5), (x0, top)]
    pts += [(x0 - 0.35, top), (x0 - 0.35, top + 1.2), (x0 - 0.1, top + 3.4), (x0 + 0.15, top + 1.2),
            (x0 + 0.5, top + 1.2)]                                     # left pinnacle
    s0, s1 = x0 + 0.9, x1 - 0.9
    if broken_seed is None:
        pts += [(s0, top + 1.2), (cx - 0.25, top + spire - 2.0), (cx, top + spire), (cx + 0.25, top + spire - 2.0),
                (s1, top + 1.2)]
    else:
        rnd = random.Random(broken_seed)
        n = 7
        for i in range(n + 1):
            t = i / n
            x = s0 + (s1 - s0) * t
            full = top + 1.2 + (spire - 1.2) * (1.0 - abs(2 * t - 1.0))
            stump = top + 1.2 + spire * (0.38 + 0.12 * rnd.random()) * (1.0 - 0.6 * abs(2 * t - 1.0))
            pts.append((x, min(full, stump) if 0 < i < n else top + 1.2))
    pts += [(x1 - 0.5, top + 1.2), (x1 - 0.15, top + 1.2), (x1 + 0.1, top + 3.4), (x1 + 0.35, top + 1.2),
            (x1 + 0.35, top)]                                          # right pinnacle
    pts += [(x1, top), (x1, 13.5), (x1 + 0.4, 12.5), (x1 + 0.4, 7.5), (x1 + 0.9, 6.0), (x1 + 0.9, 0.0)]
    return pts


def gable_outline(x0, x1, wall, peak, seed):
    """The nave wall between the towers with broken crenellations and a steep gable topped by a leaning cross."""
    rnd = random.Random(seed)
    pts = [(x0, 0.0), (x0, wall)]
    gx0, gx1 = x0 + 1.2, x1 - 1.2
    x = x0
    while x < gx0 - 0.6:                                               # crenellations (some knocked out)
        h = 0.0 if rnd.random() < 0.3 else 0.8
        pts += [(x, wall + h), (x + 0.5, wall + h), (x + 0.5, wall), (x + 0.9, wall)]
        x += 0.9
    pts += [(gx0, wall), (-0.3, peak), (-0.3, peak + 2.2), (-1.0, peak + 2.1), (-1.0, peak + 2.6), (-0.25, peak + 2.75),
            (-0.15, peak + 3.8), (0.25, peak + 3.75), (0.2, peak + 2.8), (0.95, peak + 2.85), (0.95, peak + 2.35),
            (0.2, peak + 2.3), (0.3, peak), (gx1, wall)]
    x = gx1
    while x < x1 - 0.6:
        h = 0.0 if rnd.random() < 0.3 else 0.8
        pts += [(x + 0.4, wall), (x + 0.4, wall + h), (x + 0.9, wall + h), (x + 0.9, wall)]
        x += 0.9
    pts += [(x1, wall), (x1, 0.0)]
    return pts


def cathedral(stone, win_m):
    bm = bmesh.new()
    g.extrude(bm, tower_outline(-14.5, -8.0, 19.0, 10.5), 0.6, y0=0.0)
    g.extrude(bm, tower_outline(8.0, 14.5, 19.0, 10.5, broken_seed=5), 0.6, y0=0.0)
    g.extrude(bm, gable_outline(-8.0, 8.0, 13.0, 17.5, 3), 0.6, y0=1.0)
    for x in (-18.5, 18.5):                                            # buttress pinnacles beyond the towers
        g.extrude(bm, [(x - 0.9, 0.0), (x + 0.9, 0.0), (x + 0.7, 10.0), (x + 0.35, 10.0), (x, 13.0),
                       (x - 0.35, 10.0), (x - 0.7, 10.0)], 0.6, y0=1.5)
    ob = vj.new_obj("Cathedral", bm, stone)
    ob.location = (0.0, CATH_Y, 0.0)
    rnd = random.Random(12)
    cols = [BLOOD, UVP, (0.1, 0.6, 0.02), PUMPKIN]
    wins = []
    for cx in (-11.25, 11.25):
        for k, (z0, h) in enumerate(((3.0, 4.2), (9.0, 3.6), (14.4, 3.2))):
            for dx in (-1.35, 1.35):
                if rnd.random() < 0.2:
                    continue
                wins.append((g.lancet(cx + dx, z0, 0.62, h), rnd.choice(cols), rnd.uniform(0.5, 1.0)))
    for dx in (-4.5, -2.5, 2.5, 4.5):
        wins.append((g.lancet(dx, 6.5, 0.7, 4.5), rnd.choice(cols), rnd.uniform(0.4, 0.8)))
    for i, (out, col, lvl) in enumerate(wins):
        wb = bmesh.new()
        g.extrude(wb, out, 0.0, y0=-0.08, front_only=True)
        ob = vj.new_obj(f"Window{i}", wb, win_m)
        ob.location = (0.0, CATH_Y + (0.0 if abs(out[0][0]) > 8 else 1.0), 0.0)
        ob.color = (*col, lvl)
    cb = bmesh.new()                                                    # the gable clock at midnight
    g.stroke(cb, g.xz(g.circle2(1.6, 48), 0.9, offset=(0.0, 13.6)), 0.07, segs=6, closed=True, joints=False)
    g.stroke(cb, g.xz(g.circle2(1.35, 48), 0.9, offset=(0.0, 13.6)), 0.035, segs=6, closed=True, joints=False)
    for i in range(12):
        a = math.radians(30 * i)
        p0 = (1.1 * math.sin(a), 13.6 + 1.1 * math.cos(a))
        p1 = (1.3 * math.sin(a), 13.6 + 1.3 * math.cos(a))
        g.stroke(cb, g.xz([p0, p1], 0.9), 0.04, segs=5, joints=False)
    g.stroke(cb, g.xz([(0.0, 13.6), (0.0, 14.75)], 0.88), 0.06, segs=5)
    g.stroke(cb, g.xz([(0.0, 13.6), (0.05, 14.35)], 0.86), 0.08, segs=5)
    vj.new_obj("GableClock", cb, clock_mat()).location = (0.0, CATH_Y, 0.0)


# ------------------------------------------------------------------ bats crossing the moon
class Crosser:
    """A bat crossing the moon right to left once per loop (start frame s, duration T), in a loose flock."""

    def __init__(self, i, rnd, flock):
        start, depth, height = flock
        self.s = (start + rnd.uniform(-10, 10)) % vj.FRAMES
        self.T = rnd.uniform(150, 230)
        self.y = depth + rnd.uniform(-12, 12)
        d = self.y - CAM.y
        half_w = d * 18.0 / 35.0 * 1.15
        self.x0, self.x1 = half_w, -half_w
        zc = CAM.z + (MOON_C.z - CAM.z) * d / (MOON_C.y - CAM.y)        # on the line of sight to the moon's center
        self.z = zc + height * d / 350.0 + rnd.uniform(-5, 5) * d / 200.0
        self.size = rnd.uniform(0.9, 1.25) * d / 26.0
        self.phase = rnd.uniform(-0.15, 0.15)
        self.bob = rnd.uniform(0, 6.28)

    def state(self, f):
        age = (f - self.s) % vj.FRAMES
        fl = bats.flap_angle(f, self.phase, amp=48.0)
        if age >= self.T:
            x = self.x1 if age < self.T + 30 else self.x0
            return Vector((x, self.y, self.z)), bats.heading(Vector((-1, 0, 0))), 0.0001, fl
        u = age / self.T
        x = self.x0 + (self.x1 - self.x0) * u
        z = self.z + 0.03 * self.size * 40 * math.sin(2 * math.pi * u * 1.5 + self.bob)
        vel = Vector((-1.0, 0.0, 0.12 * math.cos(2 * math.pi * u * 1.5 + self.bob)))
        return Vector((x, self.y, z)), bats.heading(vel, bank=6.0 * math.sin(2 * math.pi * u + self.bob)), \
            self.size, fl


# ------------------------------------------------------------------ scene
def build():
    scene = vj.reset_scene()
    vj.clock_from(signals)
    ext = vj.EXT

    moon = vj.new_obj("Moon", vj.disc_bm(MOON_R, 192), moon_mat())
    moon.location = MOON_C
    halo = vj.new_obj("Halo", vj.disc_bm(MOON_R * 1.6, 128), halo_mat())
    halo.location = MOON_C + Vector((0.0, -1.0, 0.0))
    sky = vj.new_obj("Sky", vj.quad_bm(900.0, 520.0), sky_mat())
    sky.location = (0.0, 330.0, 90.0)

    rb = bmesh.new()                                                    # the bead ring around the moon
    for i in range(N_BEADS):
        a = 2 * math.pi * i / N_BEADS
        p = Vector((math.sin(a) * MOON_R * 1.085, 0.0, math.cos(a) * MOON_R * 1.085))
        bmesh.ops.create_icosphere(rb, subdivisions=2, radius=1.25, matrix=Matrix.Translation(p))
    vj.new_obj("Beads", rb, beads_mat()).location = MOON_C + Vector((0.0, -3.0, 0.0))
    vj.new_obj("RingLine", g_ring(MOON_R * 1.085, 0.3), ring_line_mat()).location = MOON_C + Vector((0.0, -2.5, 0.0))

    cathedral(silhouette_mat(), window_mat())

    bm_m = beam_mat()
    for i, (x, col, ph, lvl) in enumerate(((-11.25, V["beams"][0], 0.0, 1.0), (11.25, V["beams"][1], 0.5, 0.55))):
        bb = bmesh.new()
        vj.tube(bb, [Vector((0, 0, 0)), Vector((0, 0, 140.0)), Vector((0, 0, 280.0))], lambda u: 0.4 + 9.0 * u,
                segs=20, cap0=False, cap1=False)
        ob = vj.new_obj(f"Beam{i}", bb, bm_m)
        ob.location = (x, CATH_Y + 3.0, 17.0)
        ob.color = (*col, lvl)
        rot = []
        for f in ext:
            p = 2 * math.pi * (vj.beatpos(f) / 8.0 + ph)                # one swing per 2 bars
            tilt = (-1 if x < 0 else 1) * (14.0 + 16.0 * math.sin(p))
            rot.append((f, (math.radians(-12.0 + 4.0 * math.cos(p)), math.radians(tilt), 0.0)))
        vj.keyed(ob, "rotation_euler", rot)

    rnd = random.Random(23)
    rim = bats.rim_mat("BatRim", gain=0.9, near=(1.0, 2.0), far=(400.0, 500.0))
    meshes = bats.bat_meshes(rim, vj.black_mat("BatBlack"))
    flocks = [(20.0, 75.0, 18.0), (150.0, 40.0, -6.0), (290.0, 115.0, 30.0)]
    crossers = []
    for i in range(V["n_bats"]):
        crossers.append(Crosser(i, rnd, flocks[i % len(flocks)]))
    for i, b in enumerate(crossers):
        body, wl, wr = bats.make_bat(f"Bat{i:02d}", meshes, color=V["rim"])
        bats.key_bat(body, wl, wr, [(f, *b.state(f)) for f in ext])

    cam = vj.camera(scene, lens=35.0, clip=(1.0, 2000.0))
    loc, rot = [], []
    for f in ext:
        a = 2 * math.pi * f / vj.FRAMES
        p = CAM + Vector((2.2 * math.sin(a), 0.0, 0.8 * math.sin(2 * a + 1.0)))
        loc.append((f, tuple(p)))
        rot.append((f, tuple(vj.look_at(p, MOON_C + Vector((0.0, 0.0, -6.0)), roll=0.6 * math.sin(a + 0.5)))))
    vj.keyed(cam, "location", loc)
    vj.keyed(cam, "rotation_euler", rot)
    return scene


def g_ring(radius, r, n=192):
    bm = bmesh.new()
    vj.tube(bm, g.xz(g.circle2(radius, n)), lambda u: r, segs=6, closed=True)
    return bm


scene = build()
vj.standard_render(scene)
vj.finish(scene, f"blood_moon_{VNAME}")
