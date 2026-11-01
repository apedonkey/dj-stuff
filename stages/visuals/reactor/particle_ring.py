"""PARTICLE RING - REACTOR VJ loop (Full Power). 8 bars, seamless, 1920x1080 @ 30 fps; tempo from vjkit (140 BPM
half-time = 411 frames).

A fly-through of a tokamak's ring. The camera rides once round the torus per loop, so frame 411 is frame 0 by
construction: the camera is back where it started and every other motion is periodic (the plasma ribbons are helices
that close on themselves after one lap, and they only ever turn by a multiple of their own symmetry).
  Coils    D-shaped field coils stand round the ring with their flat legs toward the torus's centre (the tunnel curves
           left); every other one is a double-rail casing with rungs.
  Plasma   ribbons spiral round the magnetic axis; particle bunches (bright dashes) race along them into the curve.
  Vessel   a faint wire grid between the plasma and the coils: poloidal rings and toroidal rails.
Every accent (half-time: the kick and the snare) brightens the plasma, sends a pulse racing down the ribbons, kicks the
near coils' glow and punches the lens in a little. Bars 1-4 cruise; bar 5's downbeat (section B) powers the ring up:
the camera accelerates through the hit, more ribbons spiral in (they fade in over the fill) and the palette lands on
the hit. After the next downbeat the ring brakes back to a cruise and the extra ribbons fade.
Variants (palette / camera / density): magenta (wide plasma ribbons, the camera on the axis), cyan (thin coolant
ribbons, the camera low and inside), green (laser-thin ribbons, denser coils, a swaying camera).
No strobing: the accents are a swell on the plasma and a lens punch, the near coils fade out before they fill a region.

  blender.exe -b --factory-startup --python particle_ring.py -- --variant magenta --frames 0,103,230 [--pct 50]
  blender.exe -b --factory-startup --python particle_ring.py -- --variant magenta --all --seam DIR [--out DIR]
"""
import math
import os
import sys

import bmesh
import bpy
from mathutils import Matrix, Vector

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import vjkit as vj  # noqa: E402
import rx_science as rx  # noqa: E402
from vjkit import AMBER, CHERENKOV, COOLANT, LASER, PLASMA, UVP, WHITE  # noqa: E402

# plasma / heads / coils / minor coils as (section A, section B) colours; ribbons (always, extra in B), their width
# and brightness; helix turns per lap; coils round the ring; the camera's offset from the axis (u out, v up, m), its
# yaw into the curve and roll sway (deg)
VARIANTS = {
    "magenta": dict(plasma=(PLASMA, PLASMA), head=(1.0, 0.55, 0.85), coil=(CHERENKOV, UVP), minor=(UVP, PLASMA),
                    vessel=UVP, ribbons=(2, 2), width=0.36, plasma_gain=1.0, turns=16, coils=32, cam=(0.0, 0.0),
                    yaw=8.0, roll=3.0),
    "cyan": dict(plasma=(COOLANT, COOLANT), head=(0.75, 1.0, 1.0), coil=(UVP, CHERENKOV), minor=(CHERENKOV, PLASMA),
                 vessel=CHERENKOV, ribbons=(3, 3), width=0.14, plasma_gain=0.75, turns=15, coils=32,
                 cam=(-0.65, -0.75), yaw=11.0, roll=2.0),
    "green": dict(plasma=(LASER, LASER), head=(0.8, 1.0, 0.85), coil=(UVP, AMBER), minor=(CHERENKOV, UVP),
                  vessel=CHERENKOV, ribbons=(2, 2), width=0.11, plasma_gain=0.8, turns=20, coils=48, cam=(0.0, 0.35),
                  yaw=6.0, roll=6.0, coil_gain=(1.0, 0.5)),
}
# coil_gain (A, B) scales the main coils per section: green's amber section-B coils at full gain put a 1 m2 at 0.72
# luma on bar 5's downbeat (cap 0.65) and swung region 2 by up to 0.17 on every accent (3 flashes per second)
VNAME, V = vj.variant(VARIANTS)
GAIN = float(vj.arg("--gain", 1.0))

R = 20.0                                   # the magnetic axis: the torus's major radius (m); one lap = 125.7 m
RHO = 2.0                                  # the ribbons' radius round the axis
VESSEL = 2.45                              # the vessel's minor radius (inside the coils)
D_IN, D_OUT, D_H = -3.1, 3.7, 4.1          # the coils' D: flat leg at u = D_IN, bulge out to u = D_OUT, half height
FADE = 24.0                                # brightness falls off as exp(-distance / FADE)
N_DASH = 40                                # particle bunches round the ring
DASH_RATE = 2.2                            # bunch speed in camera speeds (they race ahead into the curve)
WAVE_RUN, WAVE_W = 70.0, 7.0               # the accent pulse: metres run per accent interval, width
SPEED_SWING = 0.35                         # camera speed: (1 - swing) cruising in bars 1-4, (1 + swing) in bars 5-8
TURNS = V["turns"]
K_MAIN, K_EXTRA = V["ribbons"]
SPIN = 2                                   # the ribbons' apparent turns per loop round the view axis (k * SPIN whole)
LENS = 18.0
PUNCH = 0.03


# ------------------------------------------------------------------ timing
def speed_factor(b):
    """Camera speed (relative) at beat position b: cruising in bars 1-4, accelerating through bar 5's downbeat,
    braking over the first two beats after bar 1's downbeat (b wraps at the seam, so the speed is periodic)."""
    b %= vj.BEATS
    half = vj.HALF
    if b < 2.2:
        s = 1.0 - 2.0 * vj.ease(b / 2.2)
    elif b < half - 0.4:
        s = -1.0
    elif b < half + 1.2:
        s = -1.0 + 2.0 * vj.ease((b - (half - 0.4)) / 1.6)
    else:
        s = 1.0
    return 1.0 + SPEED_SWING * s


def lap_table():
    """G[f]: the share of the lap travelled at frame f (0 at frame 0, exactly 1 at frame FRAMES), trapezoid-integrated
    over 8 sub-steps per frame."""
    g = [0.0]
    for f in range(vj.FRAMES):
        acc = 0.0
        for k in range(8):
            acc += speed_factor(vj.beatpos(f) + (vj.beatpos(f + 1) - vj.beatpos(f)) * (k + 0.5) / 8)
        g.append(g[-1] + acc / 8)
    return [x / g[-1] for x in g]


G_TAB = lap_table()


def lap(f):
    """Laps travelled at any integer frame f (periodic extension: lap(f + FRAMES) = lap(f) + 1)."""
    n, ff = divmod(f, vj.FRAMES)
    return n + G_TAB[ff]


def extra_level(f):
    """The extra ribbons: fade in over the fill into bar 5 (landing on the hit), fade out after bar 1's downbeat."""
    b = vj.beatpos(f % vj.FRAMES)
    if b < 1.5:
        return 1.0 - vj.ease(b / 1.5)
    if b < vj.HALF - 2:
        return 0.0
    if b < vj.HALF:
        return vj.ease((b - (vj.HALF - 2)) / 2.0)
    return 1.0


def signals(f):
    c = vj.clock(f)
    s = {"Kick": c["kick"], "WavePos": c["aph"], "WaveAmp": (1.0 - c["aph"]) ** 1.5, "Swell": vj.swell(f),
         "Section": vj.section(f), "Extra": extra_level(f), "Flow": DASH_RATE * N_DASH * lap(f)}
    s.update(vj.loop_signals(f))
    return s


# ------------------------------------------------------------------ geometry
def torus_point(theta, u, v):
    """Point at toroidal angle theta, offset (u radially out, v up) from the magnetic axis."""
    return Vector(((R + u) * math.cos(theta), (R + u) * math.sin(theta), v))


def d_outline(scale=1.0, n=44):
    """The coil's D in its poloidal plane (u, v): flat leg at D_IN, a half ellipse out to D_OUT, rounded corners."""
    cu = 0.5 * (D_IN + D_OUT)
    pts = []
    for i in range(n + 1):
        a = math.pi / 2 - math.pi * i / n
        pts.append((D_IN + (D_OUT - D_IN) * math.cos(a), D_H * math.sin(a)))
    pts += [(D_IN, -D_H + 2 * D_H * i / 10) for i in range(1, 10)]
    pts = rx.chaikin(pts, 2, closed=True)
    return [(cu + (u - cu) * scale, v * scale) for u, v in pts]


def coils_bm(main):
    bm = bmesh.new()
    nc = V["coils"]
    outer, inner = d_outline(1.0), d_outline(0.86)
    thin = d_outline(0.94)
    for i in range(nc // 2):
        th = 2 * math.pi * (2 * i + (0 if main else 1)) / nc
        if main:
            vj.tube(bm, [torus_point(th, u, v) for u, v in outer], lambda x: 0.1, segs=10, closed=True)
            vj.tube(bm, [torus_point(th, u, v) for u, v in inner], lambda x: 0.045, segs=8, closed=True)
            for j in range(0, len(outer), len(outer) // 14):            # rungs across the casing
                a, b = torus_point(th, *outer[j]), torus_point(th, *inner[j])
                vj.tube(bm, [a, b], lambda x: 0.03, segs=6)
        else:
            vj.tube(bm, [torus_point(th, u, v) for u, v in thin], lambda x: 0.055, segs=8, closed=True)
    return bm


def ribbons_bm(k, phase0):
    """k plasma ribbons, helices of TURNS turns per lap round the axis at radius RHO (each closes on itself): flat
    bands tangent to the helix's cylinder; UV x runs across the band (-1 .. 1)."""
    bm = bmesh.new()
    uvl = bm.loops.layers.uv.new("UVMap")
    n = TURNS * 48
    w = V["width"]
    for j in range(k):
        pts = []
        for i in range(n):
            th = 2 * math.pi * i / n
            ps = TURNS * th + phase0 + 2 * math.pi * j / k
            pts.append((torus_point(th, RHO * math.cos(ps), RHO * math.sin(ps)), torus_point(th, 0.0, 0.0)))
        rows = []
        for i in range(n):
            p, c = pts[i]
            t = (pts[(i + 1) % n][0] - pts[i - 1][0]).normalized()
            side = t.cross((p - c).normalized()).normalized() * (w / 2)
            rows.append((bm.verts.new(p - side), bm.verts.new(p + side)))
        for i in range(n):
            a0, a1 = rows[i]
            b0, b1 = rows[(i + 1) % n]
            face = bm.faces.new((a0, b0, b1, a1))
            for loop, uv in zip(face.loops, ((-1.0, 0.0), (-1.0, 0.0), (1.0, 0.0), (1.0, 0.0))):
                loop[uvl].uv = uv
    return bm


def vessel_bm(nt=288, npol=36):
    bm = bmesh.new()
    rings = []
    for i in range(nt):
        th = 2 * math.pi * i / nt
        rings.append([bm.verts.new(torus_point(th, VESSEL * math.cos(2 * math.pi * j / npol),
                                               VESSEL * math.sin(2 * math.pi * j / npol))) for j in range(npol)])
    for i in range(nt):
        a, b = rings[i], rings[(i + 1) % nt]
        for j in range(npol):
            bm.faces.new((a[j], b[j], b[(j + 1) % npol], a[(j + 1) % npol]))
    return bm


# ------------------------------------------------------------------ materials
def pulse(s):
    """The accent pulse: a band of light running away from the camera down the ring, fading as it goes."""
    return s.mul(s.c("WaveAmp"), s.gauss(s.dist, s.madd(s.c("WavePos"), WAVE_RUN, 3.0), WAVE_W))


def ribbon_mat(name, extra):
    """Additive plasma: soft-edged band, bunches racing along it (world toroidal angle, so they do not ride the
    ribbons' turning), brighter on the accents and the fill, faded near the lens and with distance."""
    s = vj.Shader(name)
    across, _, _ = s.uv()
    prof = s.exp(s.mul(s.mul(across, across), -4.5))
    x, y, _ = s.world_pos()
    th = s.math("ARCTAN2", y, x)
    q = s.math("FRACT", s.sub(s.mul(th, N_DASH / (2 * math.pi)), s.c("Flow")))
    head = s.math("POWER", q, 7.0)                                 # the bunch's head leads (toward +theta)
    d = s.dist
    near = s.smooth(d, 1.6, 6.0)
    lift = s.add(0.75, s.mul(s.c("Kick"), s.falloff(d, 12.0), 0.45), s.mul(pulse(s), 0.75),
                 s.mul(s.c("Swell"), 0.45))
    col = s.mix(s.c("Section"), *V["plasma"])
    col = s.mix(s.mul(head, 0.65), col, V["head"])
    st = s.mul(prof, s.madd(head, 1.2, 0.35), lift, near, s.falloff(d, FADE), 1.5 * V["plasma_gain"] * GAIN)
    if extra:
        st = s.mul(st, s.c("Extra"))
    return s.additive(col, st)


def coil_mat(name, base, cols, gains=None):
    """Neon coil casings. The near fade runs out to 6.5 m: a coil 4.5 m off the lens, lit by a snare's lift and pulse,
    filled the corner's 1 m2 to 0.73 luma (cap 0.65) when the fade ended at 4 m. gains: (A, B) per-section scale."""
    s = vj.Shader(name)
    d = s.dist
    lift = s.add(0.55, s.mul(s.c("Kick"), s.falloff(d, 10.0), 0.3), s.mul(pulse(s), 0.25),
                 s.mul(s.c("Swell"), 0.35))
    if gains:
        lift = s.mul(lift, s.madd(s.c("Section"), gains[1] - gains[0], gains[0]))
    col = s.mix(s.c("Section"), *cols)
    col = s.mix(s.mul(s.smooth(s.core(0.0, 1.0), 0.8, 1.0), 0.3), col, WHITE)   # a white-hot core line
    fade = s.mul(s.falloff(d, FADE), s.smooth(d, 1.5, 6.5))
    return s.emit(col, s.mul(base * GAIN, s.core(), lift, fade))


def vessel_mat():
    """Additive wire grid on the vessel: a poloidal ring midway between each two coils, rails every 30 degrees."""
    s = vj.Shader("Vessel")
    x, y, z = s.world_pos()
    th = s.math("ARCTAN2", y, x)
    ps = s.math("ARCTAN2", z, s.sub(s.length2(x, y), R))
    d = s.dist
    hw = s.madd(d, 0.0011, 0.012)                                  # about a pixel wide at any distance
    nc = V["coils"]
    ring = rx.lines(s, s.madd(th, R, math.pi * R / nc), 2 * math.pi * R / nc, hw)
    rail = rx.lines(s, s.mul(ps, VESSEL), 2 * math.pi * VESSEL / 12, hw)
    g = s.math("MAXIMUM", s.mul(ring, 0.6), rail)
    lift = s.add(0.8, s.mul(s.c("Swell"), 0.3), s.mul(pulse(s), 0.4))
    return s.additive(V["vessel"], s.mul(g, lift, s.falloff(d, 18.0), s.smooth(d, 1.0, 4.0), 0.55 * GAIN))


# ------------------------------------------------------------------ scene
def build():
    scene = vj.reset_scene()
    vj.clock_from(signals)
    ext = vj.EXT

    vj.new_obj("CoilsMain", coils_bm(True), coil_mat("CoilsMain", 1.9, V["coil"], V.get("coil_gain")))
    vj.new_obj("CoilsMinor", coils_bm(False), coil_mat("CoilsMinor", 1.2, V["minor"]))
    vj.new_obj("Vessel", vessel_bm(), vessel_mat())

    # the ribbons turn rigidly about the torus's axis: turning a helix about Z slides it round the minor axis.
    # beta(f) = 2 pi lap(f) (1 - SPIN / TURNS): they keep pace with the camera less SPIN apparent turns per loop; the
    # net turn per loop, 2 pi (TURNS - SPIN) / TURNS, is a whole number of the main set's symmetry 2 pi / (TURNS k)
    main = vj.new_obj("Ribbons", ribbons_bm(K_MAIN, 0.0), ribbon_mat("Ribbons", False))
    extra = vj.new_obj("RibbonsExtra", ribbons_bm(K_EXTRA, math.pi / K_MAIN), ribbon_mat("RibbonsExtra", True))
    keys = [(f, (0.0, 0.0, 2 * math.pi * lap(f) * (1.0 - SPIN / TURNS))) for f in ext]
    for ob in (main, extra):
        vj.keyed(ob, "rotation_euler", keys)

    cam = vj.camera(scene, lens=LENS, clip=(0.1, 400.0))
    u0, v0 = V["cam"]
    loc, rot, lens, prev = [], [], [], None
    for f in ext:
        a = 2 * math.pi * f / vj.FRAMES
        th = 2 * math.pi * lap(f)
        u = u0 + 0.3 * math.sin(a + 0.4)
        v = v0 + 0.22 * math.sin(2 * a + 1.1) + 0.05 * vj.jolt(f)
        p = torus_point(th, u, v)
        yaw = math.radians(V["yaw"])
        fwd = Vector((-math.sin(th + yaw), math.cos(th + yaw), 0.0))  # the tangent, turned into the curve
        q = fwd.to_track_quat("-Z", "Y")
        roll = V["roll"] * math.sin(2 * a + 0.3) + 0.6 * vj.jolt(f, delay=1)
        q = q @ Matrix.Rotation(math.radians(roll), 4, "Z").to_quaternion()
        prev = rx.compat_euler(q, prev)
        loc.append((f, tuple(p)))
        rot.append((f, tuple(prev)))
        lens.append((f, LENS * (1.0 + PUNCH * vj.clock(f)["kick"])))
    vj.keyed(cam, "location", loc)
    vj.keyed(cam, "rotation_euler", rot)
    vj.keyed(cam.data, "lens", lens)
    return scene


scene = build()
vj.standard_render(scene)
vj.finish(scene, f"particle_ring_{VNAME}")
