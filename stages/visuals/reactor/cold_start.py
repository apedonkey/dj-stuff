"""COLD START - the REACTOR set's opener (it plays for the set's first 64 bars). 8 bars, seamless, 1920x1080 @ 30 fps;
tempo from vjkit (140 BPM half-time: 411 frames, 13.70 s).

Through the core window: two banks of control rods hang from the drive bridge into the core, which glows Cherenkov
blue under steam; two amber warning beacons hang under the bridge. One breath per loop, so the waking cycles:
  Bars 1-6   the hall wakes. The rods withdraw a notch at a time, the front bank one step after each kick and the back
             bank after each snare (weight from motion, not light); blue light columns rise out of the opened channels,
             the core glow and the steam build, the bridge's indicator lamps count up, and the beacons spin up and
             brighten (soft sweeping cones that fade before they turn to the camera: never strobes).
  Bar 7      the peak lands on its downbeat (a swell, no flash).
  Bars 7-8   the hall exhales: the rods glide back in, the light settles, the lamps go out one by one and the beacons
             slow: the loop's start.
Static camera with a slight breathing push-in that steps with the rods. Variants: blue.

  blender.exe -b --factory-startup --python cold_start.py -- --variant blue --frames 0,150,309,380 [--pct 50]
"""
import math
import os
import sys

import bmesh
from mathutils import Vector

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import vjkit as vj  # noqa: E402
import rx_sting as rx  # noqa: E402
from vjkit import AMBER, CHERENKOV, COOLANT, STEEL  # noqa: E402

VARIANTS = {
    "blue": dict(core=CHERENKOV, hot=(0.32, 0.7, 1.0), beacon=AMBER, lamp=AMBER, stripe=AMBER, steel=STEEL,
                 rim=COOLANT),
}
VNAME, V = vj.variant(VARIANTS)
GAIN = float(vj.arg("--gain", 1.0))

LENS, CAM, PUSH = 30.0, Vector((0.0, -24.0, 3.8)), 0.8       # static camera looking +Y; push-in at the peak (m)
FRONT = [(-8.0, -1.0), (-4.0, -1.0), (0.0, -1.0), (4.0, -1.0), (8.0, -1.0)]   # the kick bank (x, y)
BACK = [(-6.0, 2.0), (-2.0, 2.0), (2.0, 2.0), (6.0, 2.0)]                       # the snare bank
RODS = [(0, x, y) for x, y in FRONT] + [(1, x, y) for x, y in BACK]
ROD_R, ROD_LEN, TRAVEL, STEPS = 0.34, 14.0, 6.0, 6           # m, m, m (tip z 0 -> 6), notches per bank
STEP_B, STAGGER_B = 0.75, 0.05                               # beats a notch takes; centre-out lag per 4 m
PEAK = 24                                                    # the peak: bar 7's downbeat (beat 24)
BRIDGE_Z, BRIDGE_Y0, BRIDGE_Y1 = 9.2, -2.4, 3.5              # the drive bridge's underside and depth
BEACONS = [Vector((-9.0, -2.9, 8.7)), Vector((9.0, -2.9, 8.7))]
REVS, CONE_LEN, CONE_TILT = 5, 16.0, 30.0                    # beacon laps per loop; cone length (m), tilt down
N_LAMPS = 2 * STEPS                                          # one indicator lamp per notch


# ------------------------------------------------------------------ timing (frames; all periodic over the loop)
def bank_accents(bank):
    """Beats a bank steps on: the kicks (front, 0) or the snares (back, 1) of bars 1-6."""
    return [(0 if bank == 0 else 2) + 4 * j for j in range(STEPS)]


def rod_w(f, bank, x):
    """A rod's withdrawal 0..1: a notch per accent of its bank (a frame after the accent, centre-out), then one smooth
    glide back in from the peak to the loop's end."""
    f %= vj.FRAMES
    fp = vj.BEAT_F[PEAK]
    if f >= fp:
        return 1.0 - rx.smoother((f - fp) / (vj.FRAMES - fp))
    lag = 1.0 + STAGGER_B * vj.FPB * abs(x) / 4.0
    return sum(vj.ease((f - vj.BEAT_F[k] - lag) / (STEP_B * vj.FPB)) for k in bank_accents(bank)) / STEPS


def wake(f):
    """The hall's state 0..1: the mean rod withdrawal."""
    return sum(rod_w(f, b, x) for b, x, _ in RODS) / len(RODS)


def peak_swell(f):
    """Rises over the two beats before the peak, peaks on it, decays over ~1.5 beats."""
    f %= vj.FRAMES
    f0, f1 = vj.BEAT_F[PEAK - 2], vj.BEAT_F[PEAK]
    if f0 <= f < f1:
        return ((f - f0) / (f1 - f0)) ** 2
    return math.exp(-(f - f1) / (1.5 * vj.FPB)) if f >= f1 else 0.0


def breath(f):
    """A few percent of half-time breath into each accent (Giant Halo's: smooth rise, slow fall)."""
    c = vj.clock(f)
    amp = 0.85 if c["snare"] else 1.0
    nxt = 0.85 if vj.HALFTIME and ((c["acc"] + 1) * vj.ACC) % 4 == 2 else 1.0
    return max(amp * math.exp(-2.5 * c["aph"]), nxt * vj.ease((c["aph"] - 0.75) / 0.25))


def power(f):
    """The core's light: dim at the loop's start, full at the peak."""
    return 0.26 + 0.74 * wake(f) + 0.10 * peak_swell(f) + 0.03 * breath(f)


def lamp_on(f, j):
    """Indicator lamp j lights a frame after the j-th notch; in the exhale they go out one by one, last lit first."""
    f %= vj.FRAMES
    on = vj.ease((f - vj.BEAT_F[2 * j] - 1) / 4.0)
    f_off = (PEAK + 1.0 + 0.5 * (N_LAMPS - 1 - j)) * vj.FPB
    return min(on, 1.0 - vj.ease((f - f_off) / 6.0))


def beacon_angle_fn():
    """Unwrapped azimuth (rad) of the left beacon at any frame: its speed follows the wake (0.3 .. 1.0 of the top
    speed), REVS laps per loop exactly (seamless)."""
    om = [0.3 + 0.7 * wake(f) for f in range(vj.FRAMES)]
    cum = [0.0]
    for o in om:
        cum.append(cum[-1] + o)
    top = max(om) / cum[-1] * REVS * vj.FPB                         # laps per beat at the top speed
    vj.log(f"beacons: {REVS} laps per loop, top speed {top:.3f} laps/beat (one per {1 / top:.1f} beats)")
    assert top <= 0.5, "beacons faster than one lap per 2 beats"

    def ang(f):
        n, ff = divmod(f, vj.FRAMES)
        return 0.35 + 2 * math.pi * REVS * (n + cum[ff] / cum[-1])
    return ang


def signals(f):
    s = {"Power": power(f), "Wake": wake(f)}
    s.update(vj.loop_signals(f))
    s.update(rx.drift_signals(f))
    return s


# ------------------------------------------------------------------ materials
def rod_mat():
    """A black rod with a dim steel outline; its lower end catches the core's light from below."""
    s = vj.Shader("Rod")
    _, _, zl = s.obj_coords()                                          # m up from the rod's tip
    under = s.mul(s.falloff(s.math("MAXIMUM", zl, 0.0), 1.4), s.c("Power"))
    rim = s.rim()
    col = s.mix(s.math("MINIMUM", s.mul(under, 2.0), 1.0), V["steel"], V["core"])
    return s.emit(col, s.add(s.mul(rim, 0.2), s.mul(under, s.madd(rim, 0.9, 0.1))))


def band_mat():
    """The rods' amber tip bands."""
    s = vj.Shader("RodBand")
    return s.emit(V["stripe"], s.mul(s.madd(s.c("Power"), 0.5, 0.5), s.core(0.5, 1.2), 0.55 * GAIN))


def column_mat():
    """The light rising out of an opened channel (additive), from the core up to the rod's tip; Object.color alpha =
    how open the channel is. The mesh is a unit-high cylinder scaled to the gap."""
    s = vj.Shader("Column")
    _, alpha, _ = s.obj_info()
    _, _, zl = s.obj_coords()                                          # 0 at the core .. 1 at the rod's tip
    grad = s.falloff(s.math("MAXIMUM", zl, 0.0), 0.75)
    vol = s.math("POWER", s.inv(s.facing()), 1.5)
    col = s.mix(s.mul(grad, 0.7), V["core"], V["hot"])
    mat = s.additive(col, s.mul(alpha, grad, vol, s.c("Power"), 0.8 * GAIN))
    mat.use_backface_culling = True
    return mat


def pool_mat():
    """The opened channel's light pooling on the core top (additive disc)."""
    s = vj.Shader("Pool")
    _, alpha, _ = s.obj_info()
    x, y, _ = s.obj_coords()
    g = s.gauss(s.length2(x, y), 0.0, 0.6)
    return s.additive(V["hot"], s.mul(alpha, g, s.c("Power"), 0.5 * GAIN))


def core_top_mat():
    """The core's top: a grid of glowing channel heads (1 m pitch, the rods' channels on it) in a round core, fading
    with depth; each head a little different."""
    s = vj.Shader("CoreTop")
    x, y, _ = s.world_pos()

    def to_line(v):                                                    # distance to the nearest whole meter
        return s.math("ABSOLUTE", s.sub(s.math("FRACT", s.add(v, 0.5)), 0.5))
    head = s.mul(s.inv(s.smooth(to_line(x), 0.24, 0.3)), s.inv(s.smooth(to_line(y), 0.24, 0.3)))
    disk = s.inv(s.smooth(s.length2(x, s.sub(y, 3.5)), 10.5, 13.5))
    depth = s.falloff(s.add(y, 3.0), 16.0)
    wn = s.node("ShaderNodeTexWhiteNoise", noise_dimensions="3D")
    s.put(wn.inputs["Vector"], s.vec(s.math("FLOOR", s.add(x, 0.5)), s.math("FLOOR", s.add(y, 0.5)), 0.0))
    level = s.add(s.mul(head, s.madd(wn.outputs["Value"], 0.35, 0.65)), 0.05)
    return s.emit(V["core"], s.mul(level, disk, depth, s.c("Power"), 0.45 * GAIN))


def backdrop_mat():
    """The Cherenkov glow rising behind the rods from the core (additive), through slowly rising haze."""
    s = vj.Shader("Cherenkov")
    x, _, z = s.obj_coords()                                           # plane meters, z = 0 at the core's top
    rise = s.falloff(s.math("MAXIMUM", z, 0.0), 3.4)
    wide = s.gauss(x, 0.0, 11.0)
    haze = s.madd(s.smooth(rx.drift_noise(s, x, z, 0.12, (0.5, 4.0), 3.0), 0.3, 0.75), 0.35, 0.8)
    return s.additive(V["core"], s.mul(rise, wide, haze, s.c("Power"), 0.2 * GAIN))


def steam_mat(name, seed, gain, z_lo):
    """Steam wisps rising (additive card; world x, z), densest just above the core (z_lo) and thinning upward, lit
    from below by the core and thicker as the hall wakes."""
    s = vj.Shader(name)
    x, _, z = s.world_pos()
    n1 = rx.drift_noise(s, x, z, 0.16, (0.6, 3.4), seed)
    n2 = rx.drift_noise(s, x, z, 0.33, (-0.9, 4.6), seed + 4.1)
    wisp = s.smooth(s.add(s.mul(n1, 0.65), s.mul(n2, 0.35)), 0.5, 0.76)
    band = s.mul(s.smooth(z, z_lo - 1.5, z_lo + 0.5), s.falloff(s.math("MAXIMUM", s.sub(z, z_lo + 0.5), 0.0), 3.0))
    thick = s.madd(s.c("Wake"), 0.5, 0.5)
    return s.additive(V["core"], s.mul(wisp, band, thick, s.c("Power"), gain * GAIN))


def cone_mat():
    """A beacon's beam (additive): brightest at the lamp, soft edges, catching drifting wisps; Object.color alpha =
    its level (the wake, faded as it turns toward the camera)."""
    s = vj.Shader("Beam")
    _, alpha, _ = s.obj_info()
    xl, _, _ = s.obj_coords()                                          # m along the beam
    along = s.falloff(s.math("MAXIMUM", xl, 0.0), 6.5)
    edge = s.math("POWER", s.inv(s.facing()), 2.0)
    x, y, z = s.world_pos()
    n = s.noise4(s.vec(s.mul(x, 0.25), s.mul(y, 0.25), s.add(s.mul(z, 0.25), s.mul(s.c("LoopCos"), 0.6))),
                 s.mul(s.c("LoopSin"), 0.6), scale=1.0, detail=3.0)
    wisp = s.madd(s.smooth(n, 0.3, 0.72), 0.6, 0.4)
    mat = s.additive(V["beacon"], s.mul(alpha, along, edge, wisp, 0.16 * GAIN))
    mat.use_backface_culling = True
    return mat


def lamp_mat():
    """The beacon's glass: amber, a little hotter on its reflector's two sides (it turns with the beams, softly);
    Object.color alpha = its level."""
    s = vj.Shader("BeaconLamp")
    _, alpha, _ = s.obj_info()
    xl, _, _ = s.obj_coords()
    hot = s.math("POWER", s.math("MINIMUM", s.math("ABSOLUTE", s.math("DIVIDE", xl, 0.38)), 1.0), 3.0)
    return s.emit(V["beacon"], s.mul(alpha, s.madd(hot, 0.35, 0.75), s.core(0.6, 1.3), 1.4 * GAIN))


def indicator_mat():
    s = vj.Shader("Indicator")
    _, alpha, _ = s.obj_info()
    return s.emit(V["lamp"], s.mul(s.madd(alpha, 1.5, 0.08), s.core(0.5, 1.3), GAIN))


def stripe_mat():
    """Hazard stripes along the bridge's front (opaque, part of its face)."""
    s = vj.Shader("Hazard")
    x, _, z = s.world_pos()
    t = s.math("FRACT", s.mul(s.add(x, z), 1.0 / 0.7))
    st = s.mul(s.smooth(t, 0.04, 0.1), s.inv(s.smooth(t, 0.5, 0.56)))
    return s.emit(V["stripe"], s.mul(st, s.madd(s.c("Wake"), 0.3, 0.7), 0.42 * GAIN))


def line_mat(name, col, gain, key="Power", lo=0.5):
    """Thin additive structure lines (truss, the core's rim)."""
    s = vj.Shader(name)
    mat = s.additive(col, s.mul(s.core(0.5, 1.2), s.madd(s.c(key), 1.0 - lo, lo), gain * GAIN))
    mat.use_backface_culling = True
    return mat


# ------------------------------------------------------------------ geometry
def box_bm(x0, x1, y0, y1, z0, z1):
    bm = bmesh.new()
    vs = [bm.verts.new((x, y, z)) for x in (x0, x1) for y in (y0, y1) for z in (z0, z1)]
    for f in ((0, 1, 3, 2), (4, 6, 7, 5), (0, 4, 5, 1), (2, 3, 7, 6), (0, 2, 6, 4), (1, 5, 7, 3)):
        bm.faces.new([vs[i] for i in f])
    return bm


def cyl_bm(r, h, segs=24, z0=0.0):
    bm = bmesh.new()
    vj.tube(bm, [Vector((0, 0, z0)), Vector((0, 0, z0 + h))], lambda u: r, segs=segs)
    return bm


def ring_bm(r, z, tube_r, n=32):
    bm = bmesh.new()
    vj.tube(bm, vj.circle_pts(Vector((0, 0, z)), r, n, axis="Z"), lambda u: tube_r, segs=6, closed=True)
    return bm


def cone_bm():
    """A beam along local +X from the lamp: open cone, 0.1 m at the lamp to 2.2 m at its end."""
    bm = bmesh.new()
    vj.tube(bm, [Vector((CONE_LEN * i / 8, 0, 0)) for i in range(9)], lambda u: 0.1 + 2.1 * u, segs=28,
            cap0=False, cap1=False)
    return bm


def truss_bm():
    """The bridge face's truss: a chord above the hazard band and zigzag diagonals running up out of the frame."""
    bm = bmesh.new()
    y, z0, z1, pitch = BRIDGE_Y0 - 0.03, BRIDGE_Z + 0.44, BRIDGE_Z + 2.6, 2.4
    vj.tube(bm, [Vector((-22.0, y, z0)), Vector((22.0, y, z0))], lambda u: 0.035, segs=6)
    x = -21.6
    while x < 21.6:
        vj.tube(bm, [Vector((x, y, z0)), Vector((x + pitch / 2, y, z1))], lambda u: 0.03, segs=6)
        vj.tube(bm, [Vector((x + pitch / 2, y, z1)), Vector((x + pitch, y, z0))], lambda u: 0.03, segs=6)
        x += pitch
    return bm


# ------------------------------------------------------------------ scene
def build():
    scene = vj.reset_scene()
    vj.clock_from(signals)
    ext = vj.EXT
    black = vj.black_mat()

    # the core: its glowing top, its black front face with a thin rim, the Cherenkov glow behind
    top = vj.new_obj("CoreTop", vj.quad_bm(40.0, 13.0, axis="Z"), core_top_mat())
    top.location = (0.0, 3.5, 0.0)
    front = vj.new_obj("CoreFront", vj.quad_bm(40.0, 10.0), black)
    front.location = (0.0, -3.0, -5.0)
    rim = bmesh.new()
    vj.tube(rim, [Vector((-20.0, -3.02, 0.0)), Vector((20.0, -3.02, 0.0))], lambda u: 0.045, segs=8)
    vj.new_obj("CoreRim", rim, line_mat("CoreRim", V["rim"], 0.45))
    back = vj.new_obj("Cherenkov", vj.quad_bm(64.0, 30.0), backdrop_mat())
    back.location = (0.0, 10.0, 0.0)
    for name, y, w, h, zc, seed, gain, z_lo in (("SteamBack", 4.5, 36.0, 20.0, 4.0, 11.0, 0.06, 0.3),
                                               ("SteamFront", -9.0, 24.0, 14.0, 3.8, 5.0, 0.09, 1.2)):
        ob = vj.new_obj(name, vj.quad_bm(w, h), steam_mat(name, seed, gain, z_lo))
        ob.location = (0.0, y, zc)

    # the drive bridge: a deep black gantry the rods hang from, hazard stripes and a truss on its face, indicator lamps
    vj.new_obj("Bridge", box_bm(-24.0, 24.0, BRIDGE_Y0, BRIDGE_Y1, BRIDGE_Z, 16.0), black)
    stripes = vj.new_obj("Hazard", vj.quad_bm(48.0, 0.4), stripe_mat())
    stripes.location = (0.0, BRIDGE_Y0 - 0.02, BRIDGE_Z + 0.2)
    vj.new_obj("Truss", truss_bm(), line_mat("Truss", V["steel"], 0.5, key="Wake", lo=0.6))
    ind_m = indicator_mat()
    for j in range(N_LAMPS):
        bm = bmesh.new()
        bmesh.ops.create_uvsphere(bm, u_segments=16, v_segments=8, radius=0.13)
        ob = vj.new_obj(f"Lamp{j:02d}", bm, ind_m)
        ob.data.shade_smooth()
        ob.location = (-6.6 + 1.2 * j, BRIDGE_Y0 - 0.1, BRIDGE_Z + 0.75)
        vj.keyed(ob, "color", [(f, (1.0, 1.0, 1.0, lamp_on(f, j))) for f in ext])

    # the rods, their tip bands, the light columns and pools under them
    rod_m, band_m, col_m, pool_m = rod_mat(), band_mat(), column_mat(), pool_mat()
    rod_me = vj.finish_bm(cyl_bm(ROD_R, ROD_LEN), name="RodMesh")
    for i, (bank, x, y) in enumerate(RODS):
        rod = vj.mesh_obj(f"Rod{i}", rod_me, rod_m)
        rod.location = (x, y, 0.0)
        for zb in (0.3, 0.62):
            vj.new_obj(f"Rod{i}Band{zb}", ring_bm(ROD_R + 0.012, zb, 0.05), band_m, parent=rod)
        col = vj.new_obj(f"Column{i}", cyl_bm(ROD_R + 0.02, 1.0), col_m)
        col.data.shade_smooth()
        col.location = (x, y, 0.0)
        pool = vj.new_obj(f"Pool{i}", vj.disc_bm(1.5, n=48, axis="Z"), pool_m)
        pool.location = (x, y, 0.015)
        ws = [(f, rod_w(f, bank, x)) for f in ext]
        vj.keyed(rod, "location", [(f, (x, y, TRAVEL * w)) for f, w in ws])
        vj.keyed(col, "scale", [(f, (1.0, 1.0, max(TRAVEL * w, 0.001))) for f, w in ws])
        vj.keyed(col, "color", [(f, (1.0, 1.0, 1.0, min(1.0, 6.0 * w))) for f, w in ws])
        vj.keyed(pool, "color", [(f, (1.0, 1.0, 1.0, min(1.0, 6.0 * w))) for f, w in ws])

    # the beacons: a mount, a dark cage over amber glass, two beams turning with it
    ang = beacon_angle_fn()
    lamp_m, cone_m = lamp_mat(), cone_mat()
    cone_me = vj.finish_bm(cone_bm(), smooth=True, name="ConeMesh")
    for b, pos in enumerate(BEACONS):
        mirror = b == 1                                                 # the right beacon turns the other way
        mount = vj.new_obj(f"Mount{b}", box_bm(-0.12, 0.12, -0.12, 0.12, 0.0, BRIDGE_Z - pos.z), black)
        mount.location = pos
        cap = bmesh.new()
        bmesh.ops.create_cone(cap, cap_ends=True, segments=24, radius1=0.46, radius2=0.3, depth=0.22)
        vj.new_obj(f"Cap{b}", cap, black).location = pos + Vector((0, 0, 0.4))
        bm = bmesh.new()
        bmesh.ops.create_uvsphere(bm, u_segments=32, v_segments=16, radius=0.38)
        lamp = vj.new_obj(f"Beacon{b}", bm, lamp_m)
        lamp.data.shade_smooth()
        lamp.location = pos
        cage = bmesh.new()
        for k in range(6):
            a = 2 * math.pi * (k + 0.5) / 6
            d = Vector((math.cos(a), math.sin(a), 0.0))
            vj.tube(cage, [d * 0.3 + Vector((0, 0, -0.3)), d * 0.41, d * 0.3 + Vector((0, 0, 0.3))],
                    lambda u: 0.025, segs=6)
        vj.new_obj(f"Cage{b}", cage, black, parent=lamp)
        psi = [(f, (math.pi - ang(f)) if mirror else ang(f)) for f in ext]
        vj.keyed(lamp, "rotation_euler", [(f, (0.0, 0.0, a)) for f, a in psi])
        vj.keyed(lamp, "color", [(f, (1.0, 1.0, 1.0, 0.35 + 0.65 * wake(f))) for f in ext])
        for c, off in enumerate((0.0, math.pi)):
            cone = vj.mesh_obj(f"Beam{b}{c}", cone_me, cone_m)
            cone.location = pos
            keys_r, keys_c = [], []
            for f, a in psi:
                az = a + off
                face = vj.ease((math.sin(az) + 0.5) / 0.7)              # fades out as it turns to the camera
                keys_r.append((f, (0.0, math.radians(CONE_TILT), az)))
                keys_c.append((f, (1.0, 1.0, 1.0, face * (0.25 + 0.75 * wake(f)))))
            vj.keyed(cone, "rotation_euler", keys_r)
            vj.keyed(cone, "color", keys_c)

    cam = vj.camera(scene, lens=LENS, clip=(0.5, 300.0))
    rot = (math.radians(90.0), 0.0, 0.0)
    keys = []
    for f in ext:
        rise = 1.0 if f % vj.FRAMES < vj.BEAT_F[PEAK] else 0.0
        keys.append((f, tuple(CAM + Vector((0.0, PUSH * rx.smoother(wake(f)), 0.025 * vj.jolt(f) * rise)))))
    vj.keyed(cam, "location", keys)
    cam.rotation_euler = rot
    return scene


scene = build()
vj.standard_render(scene)
vj.finish(scene, f"cold_start_{VNAME}")
