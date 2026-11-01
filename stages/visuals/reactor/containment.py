"""CONTAINMENT - REACTOR VJ loop. 8 bars, seamless, 1920x1080 @ 30 fps; tempo from vjkit (140 BPM half-time =
411 frames).

The containment wall: a field of hexagonal shield plates with bevelled neon edges, two bands of hazard stripes, and in
the middle a bolted hatch carrying the radiation trefoil inside a ring of stripes. Four rotating warning beacons on the
wall sweep soft cones of light through the air; each beam paints a streak of light across the plates as it turns (one
turn per 2 bars). The camera pushes in slowly through the whole phrase and recoils on the downbeat of bar 1 (the
recoil starts a frame after the hit), so frame 411 equals frame 0.
  Bars 1-4 (A): edges in the variant's first colour; a ring of light runs out across the plates from the trefoil on
  every kick.
  Bars 5-8 (B): the second colour; rings on the kick and the snare, the stripes crawl. *breach*: the plates around the
  hatch crack open in the fill into bar 5 (the cracks spread out from the plates' middles and land on the hit), glow
  hot through B and pulse on the accents; steam jets out of them; over bar 8 they cool and close.
Beat hooks: the rings (cells lighting as the ring passes, a soft rise and fall), the trefoil flaring with each ring,
the push-in and its recoil on the phrase, camera thumps after the accents; the last two beats of bars 4 and 8 swell.
No strobing: the beacons turn slowly and their cones are soft and fade as they swing toward the lens, the rings are
dim and slow (under 1 m a frame), the cracks rise over two beats.

  blender.exe -b --factory-startup --python containment.py -- --variant red --frames 0,100,300 [--pct 50]
  blender.exe -b --factory-startup --python containment.py -- --variant red --all --seam DIR [--out DIR] [--mblur]
"""
import math
import os
import random
import sys

import bmesh
from mathutils import Matrix, Vector

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import vjkit as vj  # noqa: E402
import rx_plant as rx  # noqa: E402
from vjkit import ALARM, AMBER, CHERENKOV, EMBER, HOT, STEEL  # noqa: E402

# edge: (A, B) plate edge colours; beacon: lamps, cones and their light; ripple: the accent rings; trefoil: the symbol.
VARIANTS = {
    "red": dict(edge=(ALARM, EMBER), beacon=ALARM, ripple=EMBER, trefoil=ALARM, edge_gain=1.0, breach=False),
    "amber": dict(edge=(AMBER, (1.0, 0.25, 0.01)), beacon=AMBER, ripple=AMBER, trefoil=AMBER, edge_gain=0.75,
                  breach=False),
    "breach": dict(edge=(CHERENKOV, ALARM), beacon=ALARM, ripple=CHERENKOV, trefoil=AMBER, edge_gain=1.0,
                   breach=True),
}
VNAME, V = vj.variant(VARIANTS)
GAIN = float(vj.arg("--gain", 1.0))

R_HEX, GAP, BEVEL, DEPTH = 1.55, 0.1, 0.12, 0.12   # plate circumradius, gap, bevel width, face depth (m)
X_MAX, Z_MIN, Z_MAX = 34.0, -3.0, 27.0             # the wall's extent
TRE_Z = 12.0                                       # the hatch's / trefoil's centre height (x = 0)
HATCH_R = 6.3
BANDS = (3.15, 21.15)                              # hazard band centre heights (1.5 m tall)
BEACONS = [(-13.5, -1.0, 18.0), (13.5, -1.0, 18.0), (-13.5, -1.0, 6.0), (13.5, -1.0, 6.0)]
PHASES = (0.0, 0.5, 0.25, 0.75)                    # turns: the beacons never point the same way together
CAM_Z, Y_FAR, Y_NEAR = 12.0, -36.0, -29.5          # the push: from 36 m out to 29.5 m, recoil on the phrase
RECOIL = 13                                        # frames of the recoil (starts on frame 1)
RIP_SPEED = 0.9                                    # m per frame the accent rings run out
B_START = vj.BEAT_F[vj.HALF]


# ------------------------------------------------------------------ music
def beacon_angle(f, i):
    """Beam heading (radians, in the wall's XY plane) of beacon i: one turn per 2 bars (4 per loop: seamless)."""
    return 2 * math.pi * (vj.beatpos(f) / 8.0 + PHASES[i])


def toward_cam(i, a):
    """How directly beacon i's beam points at the camera (cosine, horizontal plane)."""
    bx, by, _ = BEACONS[i]
    cx, cy = -bx, Y_NEAR * 0.5 + Y_FAR * 0.5 - by
    return (math.cos(a) * cx + math.sin(a) * cy) / math.hypot(cx, cy)


def ripple(f, snare):
    """(radius m, amplitude) of the latest kick (snare) ring: it leaves the hatch's rim 2 frames before its accent (so it
    reaches the first plates on the accent), runs out at RIP_SPEED and fades."""
    for af, amp in vj.accent_frames():
        if (amp < 1.0) != snare:
            continue
        t = (f - af) % vj.FRAMES
        if t > vj.FRAMES - 3:
            t -= vj.FRAMES
        if -2 <= t <= 48:
            env = vj.ease((t + 2) / 2.0) if t < 0 else math.exp(-t / 26.0)
            return HATCH_R + 0.4 + RIP_SPEED * (t + 2), amp * env
    return -10.0, 0.0


def crack(f):
    """(level, reveal) of the breach: the cracks spread out over the 2-beat fill into bar 5 (landing on the hit), glow
    through B (pulsing on the accents), cool over bar 8 and are gone by the loop's end."""
    if not V["breach"]:
        return 0.0, 0.0
    b = vj.beatpos(f % vj.FRAMES)
    if vj.HALF - 2 <= b < vj.HALF:
        x = (b - (vj.HALF - 2)) / 2.0
        return vj.ease(x) * 0.8, vj.ease(x)
    if vj.HALF <= b < vj.BEATS:
        cool = 1.0 - vj.ease((b - (vj.BEATS - 4)) / 3.6) if b >= vj.BEATS - 4 else 1.0
        return (0.75 + 0.25 * rx.accent_env(f, attack=2.0, decay=8.0)) * cool, 1.0
    return 0.0, 0.0


def stripe_shift(f):
    """The stripes crawl through B by exactly two stripe periods (whole periods: they rest unchanged in A)."""
    f %= vj.FRAMES
    return 0.0 if f < B_START else 2.0 * (f - B_START) / (vj.FRAMES - B_START)


def signals(f):
    c = vj.clock(f)
    kr, ka = ripple(f, False)
    sr, sa = ripple(f, True)
    lvl, rev = crack(f)
    s = {"Kick": c["kick"], "Swell": vj.swell(f), "Section": vj.section(f), "RipKR": kr, "RipKA": ka,
         "RipSR": sr, "RipSA": sa, "AccLift": rx.accent_env(f, attack=2.0, decay=7.0), "Crack": lvl,
         "Reveal": rev, "Stripe": stripe_shift(f)}
    for i in range(len(BEACONS)):
        a = beacon_angle(f, i)
        s[f"B{i}C"], s[f"B{i}S"] = math.cos(a), math.sin(a)
    s.update(rx.flow_signals(f, vj.FRAMES // 3))
    s.update(vj.loop_signals(f))
    return s


# ------------------------------------------------------------------ materials
def beacon_light(s):
    """The four beams' light on the wall at this point: a soft spot around each beam's heading (horizontal), a band
    about the lamp's height, falling off with distance."""
    x, y, z = s.world_pos()
    total = None
    for i, (bx, by, bz) in enumerate(BEACONS):
        vx, vy, vz = s.sub(x, bx), s.sub(y, by), s.sub(z, bz)
        hor = s.math("SQRT", s.add(s.mul(vx, vx), s.mul(vy, vy), 0.01))
        cosd = s.math("DIVIDE", s.add(s.mul(vx, s.c(f"B{i}C")), s.mul(vy, s.c(f"B{i}S"))), hor)
        spot = s.smooth(cosd, 0.78, 1.0)
        vert = s.gauss(s.math("DIVIDE", vz, hor), 0.0, 0.3)
        fall = s.math("DIVIDE", 1.0, s.add(1.0, s.mul(s.add(s.mul(hor, hor), s.mul(vz, vz)), 1.0 / 80.0)))
        term = s.mul(spot, spot, vert, fall)
        total = term if total is None else s.add(total, term)
    return total


def plate_center(s):
    uv = s.node("ShaderNodeUVMap")
    uv.uv_map = "Center"
    return s.xyz(uv.outputs["UV"])[:2]


def rings(s):
    """The accent rings: cells light as a ring passes their centre (kick rings always, snare rings in B)."""
    cx, cz = plate_center(s)
    r = s.length2(cx, s.sub(cz, TRE_Z))
    k = s.mul(s.c("RipKA"), s.gauss(r, s.c("RipKR"), 2.2))
    sn = s.mul(s.c("RipSA"), s.gauss(r, s.c("RipSR"), 2.2), s.c("Section"))
    return s.mul(s.add(k, sn), s.madd(s.c("Section"), 0.5, 0.7))


def edge_col(s):
    return s.mix(s.c("Section"), V["edge"][0], V["edge"][1])


def face_mat():
    """Plate faces: near black (a faint per-plate tint), lit by the beams and the rings."""
    s = vj.Shader("PlateFace")
    cx, cz = plate_center(s)
    wn = s.node("ShaderNodeTexWhiteNoise", noise_dimensions="2D")
    s.put(wn.inputs["Vector"], s.vec(cx, cz, 0.0))
    tint = s.madd(wn.outputs["Value"], 0.008, 0.002)
    lift = s.add(1.0, s.mul(s.c("Swell"), 0.4))
    return s.emit_sum([(edge_col(s), s.mul(tint, lift, GAIN)),
                       (V["beacon"], s.mul(beacon_light(s), 0.11 * GAIN)),
                       (V["ripple"], s.mul(rings(s), 0.07 * GAIN))])


def bevel_mat():
    """The plates' bevels: the neon hex edges; they catch the beams and the rings harder than the faces."""
    s = vj.Shader("PlateBevel")
    lift = s.add(0.6, s.mul(s.c("Swell"), 0.35), s.mul(s.c("Kick"), 0.04))
    return s.emit_sum([(edge_col(s), s.mul(lift, s.madd(s.facing(), 0.4, 0.6), 0.55 * V["edge_gain"] * GAIN)),
                       (V["beacon"], s.mul(beacon_light(s), 0.3 * GAIN)),
                       (V["ripple"], s.mul(rings(s), 0.5 * GAIN))])


def stripes_mat(name, kind):
    """Hazard stripes: amber and black diagonals (kind 'band': along x; 'ring': round the hatch), crawling in B."""
    s = vj.Shader(name)
    x, _, z = s.obj_coords()
    if kind == "band":
        t = s.mul(s.add(x, z), 1.0 / 1.1)
    else:
        t = s.add(s.mul(s.math("ARCTAN2", z, x), 30.0 / (2 * math.pi)), s.mul(s.length2(x, z), 0.9))
    on = s.smooth(s.math("ABSOLUTE", s.sub(s.math("FRACT", s.add(t, s.c("Stripe"))), 0.5)), 0.22, 0.26)
    lift = s.add(0.8, s.mul(s.c("Swell"), 0.3))
    return s.emit_sum([(AMBER, s.mul(on, lift, 0.38 * GAIN)), (V["beacon"], s.mul(beacon_light(s), 0.12 * GAIN))])


def line_mat(name, color, gain, lift_acc=0.0):
    s = vj.Shader(name)
    lift = s.add(0.75, s.mul(s.c("Swell"), 0.3), s.mul(s.c("AccLift"), lift_acc))
    return s.emit(color, s.mul(s.core(0.45, 1.25), lift, gain * GAIN))


def trefoil_mat():
    """The trefoil's fill: dim, flaring as each ring leaves it."""
    s = vj.Shader("TrefoilFill")
    lift = s.add(0.25, s.mul(s.c("AccLift"), s.madd(s.c("Section"), 0.2, 0.25)), s.mul(s.c("Swell"), 0.25))
    return s.emit(V["trefoil"], s.mul(lift, 0.45 * GAIN))


def dark_mat(name):
    s = vj.Shader(name)
    return s.emit_sum([((0.005, 0.005, 0.007), 1.0 * GAIN), (V["beacon"], s.mul(beacon_light(s), 0.08 * GAIN))])


def cone_mat():
    """A beacon's beam in the air: additive, brightest at the lamp, soft at its sides (facing). Object colour alpha:
    keyed down as the beam swings toward the lens."""
    s = vj.Shader("BeamCone")
    x, _, _ = s.obj_coords()
    alpha = s.obj_info()[1]
    along = s.exp(s.mul(x, -1.0 / 6.5))
    soft = s.math("POWER", s.inv(s.facing()), 1.6)
    return s.additive(V["beacon"], s.mul(alpha, along, soft, s.smooth(x, 0.2, 1.2), 0.06 * GAIN))


def lamp_mat():
    """Beacon domes: a soft glow that swells as the beam turns toward the lens (alpha, keyed)."""
    s = vj.Shader("BeaconLamp")
    alpha = s.obj_info()[1]
    return s.emit(V["beacon"], s.mul(s.core(0.6, 1.3), s.madd(alpha, 1.0, 0.35), 1.6 * GAIN))


def crack_mat():
    """Breach cracks: additive (invisible when closed), revealed out from the plate's middle (UV x), hot white core."""
    s = vj.Shader("Crack")
    u = s.uv()[0]
    on = s.inv(s.smooth(u, s.sub(s.c("Reveal"), 0.04), s.add(s.c("Reveal"), 0.001)))
    core = s.core(0.0, 1.0)
    col = s.mix(s.mul(s.smooth(core, 0.4, 1.0), 0.7), EMBER, HOT)
    return s.additive(col, s.mul(on, s.c("Crack"), s.core(0.5, 1.4), 2.6 * GAIN))


def crack_glow_mat():
    """The heat around each crack: a wide, soft ember ribbon (brightest along its middle), revealed with the crack."""
    s = vj.Shader("CrackGlow")
    u = s.uv()[0]
    on = s.inv(s.smooth(u, s.sub(s.c("Reveal"), 0.04), s.add(s.c("Reveal"), 0.001)))
    soft = s.math("POWER", s.core(0.0, 1.0), 2.0)
    return s.additive(EMBER, s.mul(on, s.c("Crack"), soft, 0.55 * GAIN))


def jet_mat():
    """Steam jetting from the cracks (object space: z along the jet): additive flow noise, soft sides."""
    s = vj.Shader("CrackSteam")
    x, y, z = s.obj_coords()
    n = rx.flow_noise(s, s.add(x, y), z, 0.9, 0.7, 12.0, seed=s.mul(s.obj_info()[2], 11.0))
    along = s.mul(z, 1.0 / 5.0)
    soft = s.math("POWER", s.inv(s.facing()), 1.5)
    shape = s.mul(s.smooth(along, 0.0, 0.1), s.inv(s.smooth(along, 0.35, 1.0)))
    level = s.mul(s.c("Crack"), s.add(0.6, s.mul(s.c("AccLift"), 0.5)))
    return s.additive((1.0, 0.72, 0.6), s.mul(soft, shape, s.smooth(n, 0.25, 0.8), level, 0.16 * GAIN))


# ------------------------------------------------------------------ geometry
def plate_centers():
    col_w, row_h = 1.5 * R_HEX, math.sqrt(3) * R_HEX
    out = []
    for i in range(-int(X_MAX / col_w) - 1, int(X_MAX / col_w) + 2):
        cx = i * col_w
        for j in range(-4, 16):
            cz = j * row_h + (row_h / 2 if i % 2 else 0.0)
            if abs(cx) <= X_MAX and Z_MIN <= cz <= Z_MAX and math.hypot(cx, cz - TRE_Z) > HATCH_R + 0.9:
                out.append((cx, cz))
    return out


def plates_bm(centers):
    """Every plate: a bevel ring (material 1) from the outer hexagon on the wall to the inner face (material 0), set
    DEPTH out from the wall. UVMap: local coordinates / R_HEX; Center: the plate's centre (x, z)."""
    bm = bmesh.new()
    uvl, uvc = bm.loops.layers.uv.new("UVMap"), bm.loops.layers.uv.new("Center")
    r_out, r_in = R_HEX - GAP / 2, R_HEX - GAP / 2 - BEVEL
    for cx, cz in centers:
        outer = [bm.verts.new((cx + x, 0.0, cz + z)) for x, z in rx.hexagon(r_out)]
        inner = [bm.verts.new((cx + x, -DEPTH, cz + z)) for x, z in rx.hexagon(r_in)]
        faces = [bm.faces.new(inner)]
        for k in range(6):
            f = bm.faces.new((outer[k], outer[(k + 1) % 6], inner[(k + 1) % 6], inner[k]))
            f.material_index = 1
            faces.append(f)
        for f in faces:
            for loop in f.loops:
                p = loop.vert.co
                loop[uvl].uv = ((p.x - cx) / R_HEX, (p.z - cz) / R_HEX)
                loop[uvc].uv = (cx, cz)
    return bm


def bolts_bm(centers):
    bm = bmesh.new()
    for cx, cz in centers:
        for a in (30, 150, 270):
            p = Vector((cx + 1.08 * math.cos(math.radians(a)), -DEPTH - 0.02, cz + 1.08 * math.sin(math.radians(a))))
            bmesh.ops.create_icosphere(bm, subdivisions=1, radius=0.06, matrix=Matrix.Translation(p))
    return bm


def annulus_bm(r0, r1, y, n=128):
    bm = bmesh.new()
    a = [bm.verts.new((r0 * math.cos(2 * math.pi * i / n), y, r0 * math.sin(2 * math.pi * i / n))) for i in range(n)]
    b = [bm.verts.new((r1 * math.cos(2 * math.pi * i / n), y, r1 * math.sin(2 * math.pi * i / n))) for i in range(n)]
    for i in range(n):
        bm.faces.new((a[i], a[(i + 1) % n], b[(i + 1) % n], b[i]))
    return bm


def trefoil_outlines(rc=1.0):
    """The radiation trefoil (generic symbol): a centre disc of radius rc and three 60-degree blades from 1.5 rc to
    5 rc, one pointing down. 2D outlines (x, z)."""
    disc = rx.circle2(rc, 48)
    blades = []
    for c in (270.0, 30.0, 150.0):
        a0, a1 = math.radians(c - 30.0), math.radians(c + 30.0)
        inner = [(1.5 * rc * math.cos(a0 + (a1 - a0) * i / 16), 1.5 * rc * math.sin(a0 + (a1 - a0) * i / 16))
                 for i in range(17)]
        outer = [(5.0 * rc * math.cos(a1 - (a1 - a0) * i / 32), 5.0 * rc * math.sin(a1 - (a1 - a0) * i / 32))
                 for i in range(33)]
        blades.append(inner + outer)
    return disc, blades


def crack_paths(centers, rng):
    """Breach: for ~11 plates round the hatch, 3 jagged cracks each from near the plate's middle out to its edge (2D
    polylines (x, z)), plus where their steam vents."""
    near = sorted(centers, key=lambda c: abs(math.hypot(c[0], c[1] - TRE_Z) - 9.0) + rng.uniform(0.0, 2.5))[:11]
    paths, vents = [], []
    for cx, cz in near:
        sx, sz = cx + rng.uniform(-0.25, 0.25), cz + rng.uniform(-0.25, 0.25)
        vents.append((sx, sz))
        for b in range(3):
            ang = 2 * math.pi * (b / 3.0 + rng.uniform(-0.1, 0.1))
            p, pts = (sx, sz), [(sx, sz)]
            for _ in range(14):
                ang += rng.uniform(-0.5, 0.5)
                p = (p[0] + 0.2 * math.cos(ang), p[1] + 0.2 * math.sin(ang))
                pts.append(p)
                dx, dz = p[0] - cx, p[1] - cz
                h = max(abs(dz), abs(0.866 * dx + 0.5 * dz), abs(-0.866 * dx + 0.5 * dz)) / (0.866 * R_HEX)
                if h > 0.86:
                    break
            paths.append(pts)
    return paths, vents


def beacon_bm():
    """A beacon in its own space (origin at the lamp): bracket arm back to the wall, base, dome."""
    bm, dome = bmesh.new(), bmesh.new()
    rx.cylinder(bm, (0, 0, -0.45), (0, 1.0, -0.45), 0.08, segs=8)
    rx.cylinder(bm, (0, 0, -0.45), (0, 0, -0.2), 0.32, segs=20)
    s = bmesh.ops.create_uvsphere(dome, u_segments=20, v_segments=10, radius=0.3)
    bmesh.ops.scale(dome, vec=(1.0, 1.0, 1.25), verts=s["verts"])
    return bm, dome


# ------------------------------------------------------------------ camera
def push(f):
    """0 = far, 1 = near: the recoil eases out over RECOIL frames from frame 1, then the push eases in to the end."""
    f %= vj.FRAMES
    if f == 0:
        return 1.0
    if f <= RECOIL:
        x = (f - 1) / (RECOIL - 1)
        return 1.0 - (1.0 - (1.0 - x) ** 3)
    x = (f - RECOIL) / (vj.FRAMES - RECOIL)
    return vj.ease(x) * 0.7 + x * 0.3


# ------------------------------------------------------------------ scene
def build():
    scene = vj.reset_scene()
    vj.clock_from(signals)
    rng = random.Random(31)

    centers = plate_centers()
    me = vj.finish_bm(plates_bm(centers), smooth=False, name="PlatesMesh")
    me.materials.append(face_mat())                                     # slot 0: faces, slot 1: bevels
    me.materials.append(bevel_mat())
    vj.mesh_obj("Plates", me)
    vj.new_obj("PlateBolts", bolts_bm(centers), line_mat("Bolts", STEEL, 0.5))
    back = vj.new_obj("WallBack", vj.quad_bm(2 * X_MAX + 20.0, Z_MAX - Z_MIN + 20.0), vj.black_mat("WallBlack"))
    back.location = (0.0, 0.05, (Z_MIN + Z_MAX) / 2)

    for k, zc in enumerate(BANDS):                                     # hazard bands with neon borders
        band = vj.new_obj(f"Band{k}", vj.quad_bm(2 * X_MAX, 1.5), stripes_mat(f"BandStripes{k}", "band"))
        band.location = (0.0, -DEPTH - 0.08, zc)
        bb = bmesh.new()
        for dz in (-0.78, 0.78):
            rx.stroke(bb, [Vector((-X_MAX, -DEPTH - 0.12, zc + dz)), Vector((X_MAX, -DEPTH - 0.12, zc + dz))], 0.05,
                      segs=6, joints=False)
        vj.new_obj(f"BandEdge{k}", bb, line_mat(f"BandEdge{k}", AMBER, 0.9))

    hatch = vj.new_obj("Hatch", vj.disc_bm(HATCH_R, 128), dark_mat("HatchDark"))
    hatch.location = (0.0, -0.15, TRE_Z)
    ring = vj.new_obj("HatchStripes", annulus_bm(5.4, 6.15, 0.0), stripes_mat("RingStripes", "ring"))
    ring.location = (0.0, -0.22, TRE_Z)
    hb = bmesh.new()
    rx.ring(hb, (0, -0.25, 0), (0, 1, 0), HATCH_R, 0.09, n=128, segs=6)
    rx.ring(hb, (0, -0.25, 0), (0, 1, 0), 5.35, 0.05, n=128, segs=6)
    rx.bolt_circle(hb, (0, -0.25, 0), (0, 1, 0), HATCH_R + 0.3, 24, 0.09, 0.2)
    vj.new_obj("HatchRim", hb, line_mat("HatchRim", V["edge"][0], 1.2, lift_acc=0.3)).location = (0.0, 0.0, TRE_Z)
    disc, blades = trefoil_outlines(1.0)
    tf, tl = bmesh.new(), bmesh.new()
    for outline in [disc] + blades:
        rx.fill(tf, rx.xz(outline, y=-0.3))
        rx.stroke(tl, rx.xz(outline, y=-0.34), 0.07, segs=6, closed=True, joints=False)
    vj.new_obj("TrefoilFill", tf, trefoil_mat()).location = (0.0, 0.0, TRE_Z)
    vj.new_obj("TrefoilLine", tl, line_mat("TrefoilLine", V["trefoil"], 1.5, lift_acc=0.5)).location = (0, 0, TRE_Z)

    arm_bm, dome_bm = beacon_bm()
    arm_me = vj.finish_bm(arm_bm, smooth=True, name="BeaconArm")
    dome_me = vj.finish_bm(dome_bm, smooth=True, name="BeaconDome")
    cone_bm = bmesh.new()
    rx.cone(cone_bm, (0, 0, 0), (1, 0, 0), 15.0, 3.2, segs=32, rings=10)
    cone_me = vj.finish_bm(cone_bm, smooth=True, name="BeamCone")
    m_arm, m_lamp, m_cone = line_mat("BeaconArm", STEEL, 0.6), lamp_mat(), cone_mat()
    for i, p in enumerate(BEACONS):
        vj.mesh_obj(f"BeaconArm{i}", arm_me, m_arm).location = p
        dome = vj.mesh_obj(f"BeaconDome{i}", dome_me, m_lamp)
        dome.location = p
        cone = vj.mesh_obj(f"BeamCone{i}", cone_me, m_cone)
        cone.location = p
        vj.keyed(cone, "rotation_euler", [(f, (0.0, 0.0, beacon_angle(f, i))) for f in vj.EXT])
        keys_c, keys_d = [], []
        for f in range(vj.FRAMES + 1):
            t = toward_cam(i, beacon_angle(f, i))
            keys_c.append((f, (1.0, 1.0, 1.0, 1.0 - 0.9 * vj.ease((t - 0.1) / 0.75))))
            keys_d.append((f, (1.0, 1.0, 1.0, vj.ease((t + 0.3) / 1.3))))
        vj.animate(cone, "color", keys_c)
        vj.animate(dome, "color", keys_d)

    if V["breach"]:
        paths, vents = crack_paths(centers, rng)
        cb = bmesh.new()
        gb = bmesh.new()
        for pts in paths:
            rx.ribbon_uv(cb, rx.xz(pts, y=-DEPTH - 0.03), 0.045, segs=5)
            rx.ribbon_uv(gb, rx.xz(pts, y=-DEPTH - 0.03), 0.17, segs=8)
        vj.new_obj("Cracks", cb, crack_mat())
        vj.new_obj("CrackGlow", gb, crack_glow_mat())
        jet = bmesh.new()
        rx.cone(jet, (0, 0, 0), (0, 0, 1), 5.0, 1.5, segs=24, rings=8)
        jet_me = vj.finish_bm(jet, smooth=True, name="CrackJet")
        m_jet = jet_mat()
        for i, (x, z) in enumerate(vents[::2]):
            d = Vector((rng.uniform(-0.35, 0.35), -1.0, rng.uniform(0.15, 0.45))).normalized()
            ob = vj.mesh_obj(f"CrackJet{i}", jet_me, m_jet)
            ob.location = (x, -DEPTH - 0.05, z)
            ob.rotation_mode = "QUATERNION"
            ob.rotation_quaternion = d.to_track_quat("Z", "Y")

    cam = vj.camera(scene, lens=28.0, clip=(0.5, 300.0))
    loc, rot = [], []
    for f in vj.EXT:
        a = 2 * math.pi * f / vj.FRAMES
        y = Y_FAR + (Y_NEAR - Y_FAR) * push(f)
        loc.append((f, (0.6 * math.sin(a), y, CAM_Z + 0.4 * math.sin(2 * a + 0.7))))
        rot.append((f, tuple(vj.look_at((0.6 * math.sin(a), y, CAM_Z + 0.4 * math.sin(2 * a + 0.7)),
                                        (0.0, 0.0, TRE_Z + 0.25 * vj.jolt(f)), roll=0.8 * math.sin(a + 0.4)))))
    vj.keyed(cam, "location", loc)
    vj.keyed(cam, "rotation_euler", rot)
    return scene


scene = build()
vj.standard_render(scene)
vj.finish(scene, f"containment_{VNAME}")
