"""CHERENKOV POOL - REACTOR VJ loop. 8 bars, seamless, 1920x1080 @ 30 fps; tempo from vjkit (140 BPM half-time =
411 frames).

Looking down a deep square pool into a reactor core: a round grid of fuel assemblies, each a square of rod ends seen
end-on, glowing Cherenkov blue in the water between the rods and in the gaps between the assemblies, under slow
caustics. Blue light hangs in the water above the core. The core turns a quarter turn per loop (it is 4-fold symmetric,
so frame 411 equals frame 0); motes rise past the lens and the tiled pool walls scroll up, so the camera seems to sink
slowly toward the core.
Beat hooks: on every accent a swell of glow runs out from the centre of the core to its edge and on into the water and
up the walls; the kick is bigger and reaches further than the snare.
Section B (bars 5-8): the four control-rod banks withdraw one per accent (their hazard caps rise toward the lens and
the assemblies under them flare up in a cross / diagonal / ring pattern), hold through bar 7, and slam back in on
bar 8's kick (the camera thumps); the swell into each section hit fills the water.
Variants: blue (Cherenkov blue, amber caps), uv (ultraviolet, magenta caps, a tilted view), deep (darker teal water,
bigger and stronger caustics, a dimmer core seen from higher up).
No strobing: the accent swell lands in one frame and decays over eight; the brightest block stays under 0.65.

  blender.exe -b --factory-startup --python cherenkov_pool.py -- --variant blue --frames 0,206,240 [--pct 25]
  blender.exe -b --factory-startup --python cherenkov_pool.py -- --variant blue --all --seam DIR [--mblur]
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
import rx_core as rx  # noqa: E402
from vjkit import AMBER, CHERENKOV, PLASMA, STEEL, UVP  # noqa: E402

# glow / pale (the wave's hot tint) / cap stripes / caustic light / wall lines / motes; gain scales the core and the
# water glow (uv purple has little luma, so it runs hotter); caus = caustic strength on the core, floor and walls;
# rods = rod ends per assembly side; cam = height above the core (m), lens (mm), tilt toward +Y (deg)
VARIANTS = {
    "blue": dict(glow=CHERENKOV, pale=(0.32, 0.68, 1.0), cap=AMBER, caustic=(0.5, 0.75, 1.0),
                 wall=(0.22, 0.36, 0.55), mote=(0.55, 0.8, 1.0), gain=1.0, cards=0.6, caus=(0.10, 0.12, 0.05),
                 caus_scale=0.75, rods=5, cam=(19.0, 28.0, 0.0), n_motes=120),
    "uv": dict(glow=UVP, pale=(0.55, 0.3, 1.0), cap=PLASMA, caustic=(0.6, 0.45, 1.0), wall=(0.32, 0.22, 0.6),
               mote=(0.75, 0.6, 1.0), gain=2.3, cards=1.1, caus=(0.14, 0.16, 0.07), caus_scale=0.75, rods=5,
               cam=(17.0, 27.0, 18.0), n_motes=120),
    "deep": dict(glow=(0.03, 0.30, 0.85), pale=(0.25, 0.62, 1.0), cap=AMBER, caustic=(0.42, 0.78, 1.0),
                 wall=(0.18, 0.32, 0.5), mote=(0.5, 0.8, 1.0), gain=0.62, cards=0.4, caus=(0.2, 0.26, 0.16),
                 caus_scale=0.45, rods=4, cam=(25.0, 28.0, 0.0), n_motes=170),
}
VNAME, V = vj.variant(VARIANTS)
GAIN = float(vj.arg("--gain", 1.0)) * V["gain"]

PITCH, FACE = 1.0, 0.92                   # assembly pitch and top-face width (m): 8 cm of glowing water between them
CORE_R2 = 31.0                            # assembly (i, j) is in the core if (|i|+.5)^2 + (|j|+.5)^2 <= CORE_R2: 73
CORE_R = 5.5
PX, PY = 8.6, 6.3                         # pool half-widths (m); the core (radius 5.52) turns inside
Z_FLOOR, Z_RIM = -0.4, 12.0               # the core plate under the assemblies, the pool's rim
BASE = 0.42                               # gap glow at the core's centre
WAVE_K, SWELL_K = 0.55, 0.35              # accent swell and section swell on the glow
BANK_IN, BANK_OUT = 0.3, 1.4              # control assemblies' glow with their rods in / withdrawn
LIFT = 4.0                                # rod withdrawal (m)
CAP_W = 0.46                              # control rod (square, m)
WAVE_SPEED = 0.75                         # m per frame: the core's edge 7 frames after the accent, the walls 11
# the four banks (4-fold symmetric): the centre cross, the diagonals, the outer cross, the outer ring
BANKS = {1: [(0, 0), (0, 2), (2, 0), (0, -2), (-2, 0)],
         2: [(2, 2), (-2, 2), (-2, -2), (2, -2)],
         3: [(0, 4), (4, 0), (0, -4), (-4, 0)],
         4: [(4, 2), (2, 4), (-2, 4), (-4, 2), (-4, -2), (-2, -4), (2, -4), (4, -2)]}
F_SLAM = rx.acc_frame(14)                 # bar 8's kick: every rod slams back in (lands on this frame)


# ------------------------------------------------------------------ music
def accent_amp(k):
    """(amplitude, reach m) of accent k: the kick bigger and wider than the snare; the drop (section B) a bit more."""
    kick = k % 2 == 0
    return (1.0 if kick else 0.6) * (1.12 if k >= rx.N_ACC // 2 else 1.0), (12.0 if kick else 4.5)


def bank_out(b, f):
    """Withdrawal 0 (in) .. 1 (out) of bank b at frame f. Section A: each bank breathes up a little on its accent.
    Section B: bank b withdraws on accent 7 + b over 10 frames, holds, and every bank slams in on bar 8's kick (an
    accelerating 3-frame fall landing on the accent, then a small rebound)."""
    f %= vj.FRAMES
    out = 0.0
    for k in range(rx.N_ACC // 2):                                 # the A breathing lift
        if k % 4 == b - 1:
            t = f - rx.acc_frame(k)
            if 0 <= t < 40:
                out += 0.1 * (1.0 - math.exp(-t / 2.5)) * math.exp(-t / 10.0)
    fw = rx.acc_frame(7 + b)
    if fw <= f < F_SLAM - 3:
        out = rx.ramp_between(f, fw, fw + 10)
    elif F_SLAM - 3 <= f < F_SLAM:
        out = 1.0 - ((f - (F_SLAM - 3)) / 3.0) ** 2
    elif F_SLAM <= f < F_SLAM + 7:
        out = 0.06 * math.sin(math.pi * (f - F_SLAM) / 7.0)
    return out


def signals(f):
    c = vj.clock(f)
    s = rx.accent_signals(f, accent_amp)
    s.update({"Swell": vj.swell(f, decay_beats=1.2), "Scroll": 2.0 * 1.2 * c["loop"]})
    for b in BANKS:
        s[f"Out{b}"] = bank_out(b, f)
    s.update(vj.loop_signals(f))
    return s


# ------------------------------------------------------------------ materials
def radius(s, x, y):
    return s.length2(x, y)


def glow_level(s, r, wave, profile=True):
    """Shared glow law: BASE x radial flux profile x (1 + accent swell) x (1 + section swell) x GAIN."""
    lvl = s.mul(s.add(1.0, s.mul(wave, WAVE_K)), s.add(1.0, s.mul(s.c("Swell"), SWELL_K)), BASE * GAIN)
    if profile:
        prof = s.math("MAXIMUM", s.inv(s.mul(s.mul(r, r), 0.45 / CORE_R ** 2)), 0.35)
        lvl = s.mul(lvl, prof)
    return lvl


def core_mat():
    """The assemblies' top faces (one mesh; per-face attributes bank and rnd): dark rod ends with a faint steel rim,
    Cherenkov glow in the water between them, the steel can around each assembly, caustics in world space."""
    s = vj.Shader("Core")
    u, v, _ = s.uv()
    x, y, _ = s.obj_coords()
    xw, yw, _ = s.world_pos()
    r = radius(s, x, y)
    n = V["rods"]
    cu = s.sub(s.math("FRACT", s.mul(u, n)), 0.5)
    cv = s.sub(s.math("FRACT", s.mul(v, n)), 0.5)
    d = s.length2(cu, cv)
    gap = s.smooth(d, 0.31, 0.39)                                    # 0 on a rod end, 1 in the water
    ring = s.gauss(d, 0.335, 0.035)
    can = rx.edge_lines(s, u, v, width=0.012, soft=0.03)
    bank = rx.attr(s, "bank")
    bankf = 1.0
    for b in BANKS:
        on = s.math("COMPARE", bank, float(b), 0.1)
        bankf = s.add(bankf, s.mul(on, s.madd(s.c(f"Out{b}"), BANK_OUT - BANK_IN, BANK_IN - 1.0)))
    wave = rx.accent_wave(s, r, WAVE_SPEED)
    rnd = s.madd(rx.attr(s, "rnd"), 0.3, 0.85)
    lvl = s.mul(glow_level(s, r, wave), bankf, rnd)
    col = s.mix(s.math("MINIMUM", s.mul(wave, 0.3), 0.35), V["glow"], V["pale"])
    caus = rx.caustics(s, xw, yw, scale=V["caus_scale"])
    return s.emit_sum([(col, s.mul(lvl, gap)), (STEEL, s.add(s.mul(ring, 0.1), s.mul(can, 0.16))),
                       (V["caustic"], s.mul(caus, V["caus"][0]))])


def floor_mat():
    """The core plate and the pool floor: strong glow under the core (it shows in the gaps between the assemblies as
    a glowing grid), a dim falloff outside it, caustics."""
    s = vj.Shader("Floor")
    x, y, _ = s.world_pos()
    r = radius(s, x, y)
    wave = rx.accent_wave(s, r, WAVE_SPEED)
    under = s.inv(s.smooth(r, CORE_R - 0.2, CORE_R + 0.8))
    out = s.mul(s.exp(s.mul(s.math("MAXIMUM", s.sub(r, CORE_R), 0.0), -1.0 / 2.2)), s.inv(under), 0.12)
    lvl = s.mul(glow_level(s, r, wave), s.add(s.mul(under, 1.5), out))
    caus = rx.caustics(s, x, y, scale=V["caus_scale"], seed=3.0)
    return s.emit_sum([(V["glow"], lvl), (V["caustic"], s.mul(caus, V["caus"][1]))])


def wall_mat():
    """Tiled pool walls: steel grout lines scrolling up two tiles per loop (the sink), lit blue from below by the
    core, the accent wave climbing them, caustics near the bottom."""
    s = vj.Shader("Walls")
    x, y, z = s.world_pos()
    h = s.sub(z, Z_FLOOR)
    tile = 1.2

    def lines(coord):
        t = s.math("FRACT", s.mul(coord, 1.0 / tile))
        dd = s.mul(s.math("MINIMUM", t, s.inv(t)), tile)
        return s.inv(s.smooth(dd, 0.02, 0.05))

    grid = s.math("MAXIMUM", lines(s.sub(z, s.c("Scroll"))), lines(s.add(x, y)))
    lit = s.exp(s.mul(h, -1.0 / 4.5))
    r = s.add(radius(s, x, y), s.mul(h, 0.6))                        # the wave climbs the wall a little behind
    wave = rx.accent_wave(s, r, WAVE_SPEED)
    glow = s.mul(lit, s.add(1.0, s.mul(wave, 0.7), s.mul(s.c("Swell"), 0.5)), 0.07 * GAIN)
    caus = rx.caustics(s, s.add(x, y), z, scale=V["caus_scale"], seed=7.0)
    return s.emit_sum([(V["wall"], s.mul(grid, s.madd(lit, 0.45, 0.05))), (V["glow"], glow),
                       (V["caustic"], s.mul(caus, lit, V["caus"][2]))])


def card_mat(z):
    """One layer of the blue light hanging in the water: additive, gaussian around the core's axis (wider higher up),
    churning slowly, swelling with the accents."""
    s = vj.Shader(f"Water{z:.1f}")
    x, y, _ = s.world_pos()
    r = radius(s, x, y)
    sig = 2.7 + 0.35 * z
    fall = s.exp(s.mul(s.mul(r, r), -1.0 / sig ** 2))
    churn = s.noise4(s.vec(s.mul(x, 0.16), s.mul(y, 0.16), s.madd(s.c("LoopCos"), 0.4, z * 0.37)),
                     s.mul(s.c("LoopSin"), 0.4), scale=1.0, detail=2.0)
    churn = s.madd(s.smooth(churn, 0.3, 0.7), 0.6, 0.7)
    wave = rx.accent_wave(s, s.add(r, z * 0.5), WAVE_SPEED)
    lvl = s.mul(fall, churn, s.add(1.0, s.mul(wave, 0.7)), s.add(1.0, s.mul(s.c("Swell"), 0.5)),
                0.055 * math.exp(-z / 4.5) * V["cards"] * float(vj.arg("--gain", 1.0)))
    return s.additive(V["glow"], lvl)


def cap_mat():
    """Control rods: the cap (top face) carries hazard stripes as concentric diamonds (4-fold symmetric like the
    core, which turns a quarter turn per loop: diagonal stripes broke the seam) in a steel frame; the long body below
    it is black with steel edge lines (it shows as the rod rises toward the lens)."""
    s = vj.Shader("RodCap")
    u, v, _ = s.uv()
    top = s.smooth(rx.true_nz(s), 0.5, 0.9)
    stripes = rx.hazard(s, s.math("ABSOLUTE", s.sub(u, 0.5)), s.math("ABSOLUTE", s.sub(v, 0.5)), period=0.19,
                        soft=0.06)
    frame = rx.edge_lines(s, u, v, width=0.07, soft=0.05)
    side = s.inv(s.smooth(s.math("MINIMUM", u, s.inv(u)), 0.05, 0.12))   # the body's long edges
    lift = s.add(1.0, s.mul(s.c("Swell"), 0.25))
    cap = s.mul(top, s.inv(frame), stripes, lift, 0.85)
    steel = s.add(s.mul(top, frame, 0.35), s.mul(s.inv(top), side, 0.3))
    return s.emit_sum([(V["cap"], cap), (STEEL, steel)])


def mote_mat():
    s = vj.Shader("Motes")
    col, alpha, _ = s.obj_info()
    return s.emit(col, s.mul(alpha, 1.0))


# ------------------------------------------------------------------ geometry
def canonical(i, j):
    """The representative of (i, j) under quarter turns (so per-assembly variation keeps the 4-fold symmetry)."""
    for _ in range(4):
        if (i > 0 and j >= 0) or (i == 0 and j == 0):
            return i, j
        i, j = -j, i
    return i, j


def core_bm():
    bm = bmesh.new()
    uvl = bm.loops.layers.uv.new("UVMap")
    lb = bm.faces.layers.float.new("bank")
    lr = bm.faces.layers.float.new("rnd")
    bank_of = {p: b for b, ps in BANKS.items() for p in ps}
    h = FACE / 2
    for i in range(-6, 7):
        for j in range(-6, 7):
            if (abs(i) + 0.5) ** 2 + (abs(j) + 0.5) ** 2 > CORE_R2:
                continue
            cx, cy = i * PITCH, j * PITCH
            vs = [bm.verts.new((cx + dx, cy + dy, 0.0)) for dx, dy in ((-h, -h), (h, -h), (h, h), (-h, h))]
            face = bm.faces.new(vs)
            for lp, uv in zip(face.loops, ((0, 0), (1, 0), (1, 1), (0, 1))):
                lp[uvl].uv = uv
            face[lb] = float(bank_of.get((i, j), 0))
            face[lr] = random.Random(hash(canonical(i, j)) & 0xFFFF).random()
    return bm


def rods_bm(cells):
    bm = bmesh.new()
    uvl = bm.loops.layers.uv.new("UVMap")
    w = CAP_W / 2
    for i, j in cells:
        rx.uv_prism(bm, uvl, i * PITCH - w, i * PITCH + w, j * PITCH - w, j * PITCH + w, -7.0, 0.18)
    return bm


def quad(name, corners, mat):
    bm = bmesh.new()
    bm.faces.new([bm.verts.new(c) for c in corners])
    return vj.new_obj(name, bm, mat)


# ------------------------------------------------------------------ scene
def build():
    scene = vj.reset_scene()
    vj.clock_from(signals)
    ext = vj.EXT
    rng = random.Random(7)

    rig = vj.new_empty("CoreRig")                                   # the core turns a quarter turn per loop
    vj.keyed(rig, "rotation_euler", [(f, (0.0, 0.0, 0.5 * math.pi * f / vj.FRAMES)) for f in ext])
    vj.new_obj("Core", core_bm(), core_mat(), rig)
    cm = cap_mat()
    for b, cells in BANKS.items():
        ob = vj.new_obj(f"Rods{b}", rods_bm(cells), cm, rig)
        vj.keyed(ob, "location", [(f, (0.0, 0.0, LIFT * bank_out(b, f))) for f in ext])

    quad("Floor", [(-PX, -PY, Z_FLOOR), (PX, -PY, Z_FLOOR), (PX, PY, Z_FLOOR), (-PX, PY, Z_FLOOR)], floor_mat())
    wm = wall_mat()
    quad("WallE", [(PX, -PY, Z_FLOOR), (PX, PY, Z_FLOOR), (PX, PY, Z_RIM), (PX, -PY, Z_RIM)], wm)
    quad("WallW", [(-PX, PY, Z_FLOOR), (-PX, -PY, Z_FLOOR), (-PX, -PY, Z_RIM), (-PX, PY, Z_RIM)], wm)
    quad("WallN", [(PX, PY, Z_FLOOR), (-PX, PY, Z_FLOOR), (-PX, PY, Z_RIM), (PX, PY, Z_RIM)], wm)
    quad("WallS", [(-PX, -PY, Z_FLOOR), (PX, -PY, Z_FLOOR), (PX, -PY, Z_RIM), (-PX, -PY, Z_RIM)], wm)

    for z in (0.35, 1.0, 2.0, 3.4, 5.2, 7.5):                       # the glow hanging in the water above the core
        card = vj.new_obj(f"Water{z:.1f}", vj.disc_bm(9.5, 96, axis="Z"), card_mat(z))
        card.location = (0.0, 0.0, z)

    h_cam, lens, tilt = V["cam"]
    top = h_cam - 5.0                                               # motes rise from the core to 5 m below the lens
    mm, me = mote_mat(), rx.ico_mesh("Mote", 1)
    for i in range(V["n_motes"]):
        ob = vj.mesh_obj(f"Mote{i:03d}", me, mm)
        x0, y0 = rng.uniform(-PX + 0.5, PX - 0.5), rng.uniform(-PY + 0.5, PY - 0.5)
        ph, size, lvl = rng.random(), rng.uniform(0.022, 0.05), rng.uniform(0.35, 1.0)
        sw, sph = rng.uniform(0.1, 0.35), rng.uniform(0, 2 * math.pi)

        def state(f, x0=x0, y0=y0, ph=ph, size=size, lvl=lvl, sw=sw, sph=sph):
            u = (ph + f / vj.FRAMES) % 1.0                           # one rise per loop
            fade = rx.ramp_between(u, 0.0, 0.15) * (1.0 - rx.ramp_between(u, 0.7, 0.97))
            a = 2 * math.pi * f / vj.FRAMES + sph
            p = (x0 + sw * math.sin(a), y0 + sw * math.cos(2 * a), 0.5 + (top - 0.5) * u)
            return p, size * max(fade, 1e-4) ** 0.5, (*V["mote"], lvl * fade)
        rx.particle_keys(ob, ext, state)

    cam = vj.camera(scene, lens=lens, clip=(0.1, 200.0))
    back = h_cam * math.tan(math.radians(tilt))
    loc, rot = [], []
    for f in ext:
        a = 2 * math.pi * f / vj.FRAMES
        j = 0.12 * vj.jolt(f) + 0.35 * jolt_at(f, F_SLAM)
        loc.append((f, (0.35 * math.sin(a), -back + 0.25 * math.sin(2 * a), h_cam - j)))
        rot.append((f, (math.radians(tilt + 0.6 * math.sin(a + 1.0)), math.radians(0.5 * math.sin(a)),
                        math.radians(0.8 * math.sin(a + 2.0)))))
    vj.keyed(cam, "location", loc)
    vj.keyed(cam, "rotation_euler", rot)
    return scene


def jolt_at(f, f0, decay=3.0, period=5.0, delay=1):
    """A single damped jolt after frame f0 (cyclic), like vj.jolt's per-accent one."""
    t = (f - f0 - delay) % vj.FRAMES
    return math.exp(-t / decay) * math.sin(2 * math.pi * t / period) if t < 6 * decay else 0.0


scene = build()
vj.standard_render(scene)
vj.finish(scene, f"cherenkov_pool_{VNAME}")
