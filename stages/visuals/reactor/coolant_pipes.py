"""COOLANT PIPES - REACTOR VJ loop. 8 bars, seamless, 1920x1080 @ 30 fps; tempo from vjkit (140 BPM half-time =
411 frames).

A fly-through of the plant's coolant tunnel. Banks of big pipes run along both walls and the ceiling, joined by bolted
twin flanges; a steel support portal (with a clamp round every pipe) passes the camera on every beat; red-wheeled gate
valves sit on the mains, caged lamps on every fourth portal, sight-glass sections in the ceiling lines, and vent stubs
that hiss steam into the tunnel. The Spine Tunnel method: the camera travels 128 m per loop, a whole number of every
spacing, and the tunnel runs on far behind the fade at the end of the view for the whole loop, so frame 411 equals
frame 0.
  Bars 1-4 (A): the pipes in the variant's first colour; pressure waves on the mains (kick) and the wall lines (snare).
  Bars 5-8 (B): the second colour; the ceiling and floor lines carry waves too, the sight glasses glow, the vents
  blast on every snare (the palette morph lands on bar 5's downbeat and back on the loop's).
Beat hooks: on every accent a pressure wave of light races down the pipes away from the camera (it rises behind the
near fade, so it is full on the accent frame, and fades as it runs; the flanges flare as it passes); the vents burst on
the snare; the last two beats of bars 4 and 8 swell into the next phrase; the camera thumps after the accents.
No strobing: the waves are wide and run at ~2 m a frame, nothing within a few metres of the lens is lit, the steam is
faint and fades out before it reaches the lens.

  blender.exe -b --factory-startup --python coolant_pipes.py -- --variant cyan --frames 0,100,300 [--pct 50]
  blender.exe -b --factory-startup --python coolant_pipes.py -- --variant cyan --all --seam DIR [--out DIR] [--mblur]
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
from vjkit import ALARM, AMBER, CHERENKOV, COOLANT, EMBER, HOT, PLASMA, STEEL, UVP  # noqa: E402

# pipe: (A, B) colours; wave: the pressure waves' hot colour; glass: sight glasses and lamps; cam: the camera path;
# wave_gain: how hard the waves light the lines (uv's UV-purple lines are so low in luma that a full-strength, pale wave
# made its accent frames ~2x the frames between: x2.01 at 1.0 with a (1, 0.55, 1) wave).
VARIANTS = {
    "cyan": dict(pipe=(CHERENKOV, COOLANT), wave=(0.6, 0.95, 1.0), glass=COOLANT, steam=(0.55, 0.8, 1.0),
                 lamp=AMBER, cam="center", pipe_gain=1.0),
    "amber": dict(pipe=(AMBER, EMBER), wave=HOT, glass=AMBER, steam=(1.0, 0.7, 0.45), lamp=CHERENKOV,
                  cam="low", pipe_gain=0.9),
    "uv": dict(pipe=(UVP, PLASMA), wave=(0.75, 0.2, 1.0), glass=PLASMA, steam=(0.6, 0.4, 1.0), lamp=COOLANT,
               cam="corkscrew", pipe_gain=1.3, wave_gain=0.55),
}
VNAME, V = vj.variant(VARIANTS)
GAIN = float(vj.arg("--gain", 1.0))

D = 4.0                                  # camera travel per beat (m): one support portal per beat
TRAVEL = vj.BEATS * D                    # 128 m per loop: a whole number of every spacing below
FAR = 175.0                              # the tunnel runs on this far past the loop's end (far beyond the fade)
Y0, Y1 = -16.0, TRAVEL + FAR
FADE = 30.0                              # light falls off as exp(-distance / FADE)
FLANGE_SP = 8.0
WAVE_START, WAVE_SPEED, WAVE_W = 10.0, 2.2, 6.0  # m ahead of the lens on the accent, m per frame, gauss width (m)
FLOW_T = vj.FRAMES // 3                  # the steam's flow cycle (137 frames)
JET_L = 1.9
PIPES = [                                # (x, z, radius, group)
    (-3.7, 1.0, 0.8, "main"), (-3.4, 2.55, 0.42, "mid"), (-3.25, 3.45, 0.28, "mid"),
    (3.8, 1.15, 0.95, "main"), (3.35, 2.95, 0.36, "mid"), (3.2, 3.75, 0.24, "mid"),
    (-1.6, 4.75, 0.45, "ceil"), (-0.35, 4.95, 0.32, "ceil"), (0.95, 4.85, 0.5, "ceil"),
]
RIG = None                               # the empty riding with the camera (rig space = metres ahead of it)


# ------------------------------------------------------------------ music
def wave(f, snare):
    """(position in m ahead of the camera, amplitude) of the latest kick (or snare) pressure wave at frame f: launched
    3 frames before its accent (still behind the near fade), full on the accent, fading as it runs away."""
    for af, amp in vj.accent_frames():
        if (amp < 1.0) != snare:
            continue
        t = (f - af) % vj.FRAMES
        if t > vj.FRAMES - 4:
            t -= vj.FRAMES
        if -3 <= t <= 44:
            env = vj.ease((t + 3) / 3.0) if t < 0 else math.exp(-t / 16.0)
            return WAVE_START + WAVE_SPEED * t, amp * env
    return -60.0, 0.0


def vent(f):
    """The vents: a faint hiss, bursts on the snare (every snare in B, in A only bars 2 and 4), rising over 3 frames."""
    v = 0.18
    for af, amp in vj.accent_frames():
        if amp >= 1.0:
            continue
        k = vj.BEAT_F.index(af)
        if k < vj.HALF and (k // 4) % 2 == 0:
            continue
        t = (f - af) % vj.FRAMES
        if t > vj.FRAMES - 4:
            t -= vj.FRAMES
        if -3 <= t < 0:
            v = max(v, 0.18 + 0.82 * vj.ease((t + 3) / 3.0))
        elif 0 <= t <= 40:
            v = max(v, 0.18 + 0.82 * math.exp(-t / 12.0))
    return v


def signals(f):
    c = vj.clock(f)
    kp, ka = wave(f, False)
    sp, sa = wave(f, True)
    s = {"Kick": c["kick"], "Swell": vj.swell(f), "Section": vj.section(f), "KPos": kp, "KAmp": ka, "SPos": sp,
         "SAmp": sa, "Vent": vent(f)}
    s.update(rx.flow_signals(f, FLOW_T))
    s.update(vj.loop_signals(f))
    return s


# ------------------------------------------------------------------ materials
def rig_y(s):
    tc = s.node("ShaderNodeTexCoord")
    tc.object = RIG
    return s.xyz(tc.outputs["Object"])[1]


def fade(s, near=(2.5, 7.0)):
    return s.mul(s.falloff(s.dist, FADE), s.smooth(s.dist, *near))


def waves(s, k_gain, s_gain):
    """The pressure waves' light at this point: the kick and snare bands (rig-space y), each times its gain (floats or
    sockets)."""
    yr = rig_y(s)
    kw = s.mul(s.c("KAmp"), s.gauss(yr, s.c("KPos"), WAVE_W), k_gain)
    sw = s.mul(s.c("SAmp"), s.gauss(yr, s.c("SPos"), WAVE_W), s_gain)
    gain = V.get("wave_gain", 1.0)
    return s.add(kw, sw) if gain == 1.0 else s.mul(s.add(kw, sw), gain)


def group_gains(s, group):
    sec = s.c("Section")
    return {"main": (1.0, 0.25), "mid": (0.25, 1.0), "ceil": (s.mul(sec, 0.9), s.mul(sec, 0.9)),
            "floor": (s.mul(sec, 0.8), 0.0)}[group]


def pipe_mat(group):
    """Dark pipes drawn as neon lines. A facing-based rim fails on pipes that run along the view (nearly all of their
    surface is at grazing angles, so they glow solid): instead each pipe carries two streaks along its length where its
    outline is seen from the tunnel's axis, and a faint highlight between them (object space, the pipe's axis at the
    origin; object colour R: the heading toward the tunnel's axis, G: the half-angle to the tangent points). A pressure
    wave runs hot along the lines and warms the body a little."""
    s = vj.Shader(f"Pipe_{group}")
    x, _, z = s.obj_coords()
    oc = s.xyz(s.obj_info()[0])
    th = s.mul(s.sub(oc[0], 0.5), 2 * math.pi)
    al = s.mul(oc[1], math.pi)
    phi = s.math("ARCTAN2", z, x)
    width = s.math("MAXIMUM", s.math("DIVIDE", 0.045, s.length2(x, z)), 0.05)    # ~4.5 cm wide whatever the pipe

    def dist(c):
        d = s.math("FRACT", s.add(s.mul(s.sub(phi, c), 1.0 / (2 * math.pi)), 0.5))
        return s.mul(s.math("ABSOLUTE", s.sub(d, 0.5)), 2 * math.pi)

    lines = s.add(s.gauss(dist(s.add(th, al)), 0.0, width), s.gauss(dist(s.sub(th, al)), 0.0, width),
                  s.mul(s.gauss(dist(th), 0.0, s.mul(width, 1.2)), 0.12))
    w = waves(s, *group_gains(s, group))
    col = s.mix(s.c("Section"), V["pipe"][0], V["pipe"][1])
    col = s.mix(s.math("MINIMUM", s.mul(w, 0.7), 0.8), col, V["wave"])
    lit = s.add(s.mul(lines, s.add(0.7, s.mul(s.c("Swell"), 0.35), s.mul(w, 0.9))), s.mul(w, 0.04), 0.004)
    return s.emit(col, s.mul(lit, fade(s), 1.6 * V["pipe_gain"] * GAIN))


def flange_mat():
    """Twin flanges and bolts: hot rings that flare as any wave passes."""
    s = vj.Shader("Flange")
    sec = s.c("Section")
    w = waves(s, s.madd(sec, 0.4, 0.8), s.madd(sec, 0.4, 0.8))
    col = s.mix(s.math("MINIMUM", s.mul(w, 0.6), 0.7), s.mix(sec, V["pipe"][1], V["pipe"][0]), V["wave"])
    lit = s.add(0.4, s.mul(w, 0.8), s.mul(s.c("Swell"), 0.3))
    return s.emit(col, s.mul(lit, s.core(0.4, 1.2), fade(s), 1.0 * V["pipe_gain"] * GAIN))


def steel_mat():
    s = vj.Shader("Steel")
    lift = s.add(0.8, s.mul(s.c("Swell"), 0.25), s.mul(s.c("Kick"), 0.05))
    return s.emit(STEEL, s.mul(s.rim((0.45, 0.93)), lift, fade(s), 1.0 * GAIN))


def wheel_mat():
    s = vj.Shader("Handwheel")
    return s.emit(ALARM, s.mul(s.core(0.5, 1.3), s.add(0.7, s.mul(s.c("Swell"), 0.3)), fade(s), 1.6 * GAIN))


def glass_mat():
    """Sight glasses in the ceiling lines: coolant glowing inside, dim in A, bright in B, churning (4D noise)."""
    s = vj.Shader("SightGlass")
    x, y, z = s.world_pos()
    n = s.noise4(s.vec(s.mul(y, 0.9), s.mul(s.c("LoopCos"), 1.5), s.mul(x, 2.0)), s.mul(s.c("LoopSin"), 1.5),
                 scale=1.0, detail=2.0)
    w = waves(s, 0.6, 0.6)
    lvl = s.add(s.madd(s.c("Section"), 0.45, 0.2), s.mul(w, 0.4), s.mul(s.c("Swell"), 0.2))
    return s.emit(V["glass"], s.mul(lvl, s.madd(n, 0.6, 0.6), s.core(0.5, 1.2), fade(s, (5.0, 12.0)), 0.9 * GAIN))


def lamp_mat():
    s = vj.Shader("Lamp")
    return s.emit(V["lamp"], s.mul(s.core(0.5, 1.3), s.add(0.8, s.mul(s.c("Swell"), 0.2)), fade(s, (3.0, 9.0)),
                                   1.6 * GAIN))


def grate_mat():
    """The walkway: cross bars every metre and two edge lines, faint, fading fast with distance."""
    s = vj.Shader("Grate")
    x, y, _ = s.world_pos()
    t = s.math("FRACT", s.add(y, 0.5))
    bars = s.inv(s.smooth(s.mul(s.math("ABSOLUTE", s.sub(t, 0.5)), 1.0), 0.03, 0.08))
    rails = s.inv(s.smooth(s.math("ABSOLUTE", s.sub(s.math("ABSOLUTE", x), 1.9)), 0.03, 0.08))
    lit = s.math("MAXIMUM", s.mul(bars, 0.5), rails)
    return s.emit(STEEL, s.mul(lit, s.falloff(s.dist, 14.0), s.smooth(s.dist, 2.0, 5.0), 0.5 * GAIN))


def steam_mat():
    """A vent's jet (object space: z along the jet, apex at the vent): additive, soft edges, flow noise streaming out,
    widening and thinning along the jet. Object colour alpha: this vent's level (the keyed hiss / burst)."""
    s = vj.Shader("Steam")
    x, y, z = s.obj_coords()
    n = rx.flow_noise(s, s.add(x, y), z, 2.2, 1.6, 2.4 * JET_L, seed=s.mul(s.obj_info()[2], 13.0))
    along = s.mul(z, 1.0 / JET_L)
    soft = s.math("POWER", s.inv(s.facing()), 1.5)
    level = s.mul(s.c("Vent"), s.madd(s.c("Section"), 0.5, 0.6))
    shape = s.mul(s.smooth(along, 0.0, 0.15), s.inv(s.smooth(along, 0.4, 1.0)))
    return s.additive(V["steam"], s.mul(soft, shape, s.smooth(n, 0.25, 0.75), level, fade(s, (4.0, 9.0)),
                                        0.55 * GAIN))


# ------------------------------------------------------------------ geometry
def periodic(offset, spacing):
    """Every y = offset + k * spacing inside the built span (spacing divides TRAVEL: periodic)."""
    k0 = int(math.ceil((Y0 - offset) / spacing))
    k1 = int(math.floor((Y1 - offset) / spacing))
    return [offset + k * spacing for k in range(k0, k1 + 1)]


def build_tunnel():
    pipes = []                                                         # (x, z, r, group, bmesh about its axis)
    flange, steel, wheel, glass, lamp = bmesh.new(), bmesh.new(), bmesh.new(), bmesh.new(), bmesh.new()
    vents = []
    for i, (x, z, r, g) in enumerate(PIPES):
        pb = bmesh.new()
        rx.cylinder(pb, (0, Y0, 0), (0, Y1, 0), r, segs=40 if r > 0.4 else 28, caps=False)
        pipes.append((x, z, r, g, pb))
        off = (i * 2.7) % FLANGE_SP
        for y in periodic(off, FLANGE_SP):                             # bolted twin flanges
            for dy in (-0.07, 0.07):
                rx.ring(flange, (x, y + dy, z), (0, 1, 0), r + 0.09, 0.055, n=32 if r > 0.4 else 20, segs=6)
            rx.bolt_circle(flange, (x, y, z), (0, 1, 0), r + 0.14, 12 if r > 0.4 else 8, 0.035, 0.3)
        for y in periodic(D * 0.5, D):                                 # a clamp at every portal
            rx.ring(steel, (x, y, z), (0, 1, 0), r + 0.04, 0.035, n=24, segs=5)
        if g == "ceil" and i % 2 == 0:                                 # sight glasses
            for y in periodic(5.0 + i, 16.0):
                rx.cylinder(glass, (x, y, z), (x, y + 1.6, z), r + 0.025, segs=20, caps=False)
    for y in periodic(D * 0.5, D):                                     # support portals, one per beat
        rx.stroke(steel, [Vector((-4.75, y, 0.0)), Vector((-4.75, y, 5.5)), Vector((4.75, y, 5.5)),
                          Vector((4.75, y, 0.0))], 0.1, segs=8)
        rx.cylinder(steel, (-4.75, y, 4.6), (-3.9, y, 5.5), 0.06, segs=6)    # knee braces
        rx.cylinder(steel, (4.75, y, 4.6), (3.9, y, 5.5), 0.06, segs=6)
    for y in periodic(2.0, 4 * D):                                     # caged lamps on every 4th portal, both sides
        for sx in (-1, 1):
            p = Vector((sx * 4.45, y + D * 0.5 + 0.25 * sx, 4.3))
            rx.cylinder(lamp, p - Vector((0, 0, 0.2)), p + Vector((0, 0, 0.2)), 0.12, segs=12)
            for a in range(4):
                q = p + Vector((0.17 * math.cos(a * math.pi / 2), 0.17 * math.sin(a * math.pi / 2), 0))
                rx.cylinder(steel, q - Vector((0, 0, 0.24)), q + Vector((0, 0, 0.24)), 0.015, segs=4)
    for (x, z, r, _), off in ((PIPES[3], 6.0), (PIPES[0], 22.0)):      # gate valves on the mains
        sx = -1 if x > 0 else 1                                       # toward the tunnel's middle
        for y in periodic(off, 32.0):
            c = Vector((x, y, z))
            for dy in (-0.35, 0.35):                                   # the valve body's collars
                rx.ring(flange, c + Vector((0, dy, 0)), (0, 1, 0), r + 0.17, 0.09, n=40, segs=8)
            rx.bolt_circle(flange, c, (0, 1, 0), r + 0.2, 12, 0.05, 0.85)
            d = Vector((sx * 0.55, 0.0, 0.85)).normalized()
            top = c + d * (r + 0.95)
            rx.cylinder(steel, c + d * r, top, 0.07, segs=8)
            rx.ring(wheel, top, d, 0.42, 0.04, n=32, segs=6)
            u, v = rx.frame_of(d)
            for a in range(4):
                e = (u * math.cos(a * math.pi / 2) + v * math.sin(a * math.pi / 2)) * 0.42
                rx.cylinder(wheel, top, top + e, 0.025, segs=5)
    for (x, z, r, _), off in ((PIPES[1], 13.0), (PIPES[4], 29.0), (PIPES[7], 45.0)):   # vents on the wall lines
        sx = -1 if x > 0 else 1
        for y in periodic(off, 32.0):
            d = Vector((sx * 0.8, 0.45, -0.25)) if z < 4.5 else Vector((0.3, 0.45, -0.8))
            d.normalize()
            base = Vector((x, y, z)) + d * r
            rx.cylinder(steel, base - d * 0.05, base + d * 0.3, 0.07, segs=8)
            vents.append((base + d * 0.3, d))
    return pipes, flange, steel, wheel, glass, lamp, vents


def jet_bm():
    """A steam jet in its own space: a cone along +z from the vent (apex at the origin)."""
    bm = bmesh.new()
    rx.cone(bm, (0, 0, 0), (0, 0, 1), JET_L, 0.55, segs=20, rings=8)
    return bm


# ------------------------------------------------------------------ camera
def cam_path(f):
    """(x, z, pitch deg, roll deg): periodic over the loop."""
    a = 2 * math.pi * f / vj.FRAMES
    if V["cam"] == "low":                       # skimming the walkway, looking up the pipe banks
        return 0.35 * math.sin(a), 1.35 + 0.1 * math.sin(2 * a), 4.0, 1.5 * math.sin(2 * a)
    if V["cam"] == "corkscrew":                 # a slow spiral round the tunnel's axis, banking into it
        return 0.85 * math.sin(a), 2.45 + 0.55 * math.cos(a), 0.0, 7.0 * math.sin(a)
    return 0.3 * math.sin(a), 2.35 + 0.12 * math.sin(2 * a + 0.4), 0.0, 2.0 * math.sin(a + 0.5)


# ------------------------------------------------------------------ scene
def build():
    global RIG
    scene = vj.reset_scene()
    vj.clock_from(signals)
    RIG = vj.new_empty("Rig")                                          # rides with the camera along the tunnel
    vj.keyed(RIG, "location", [(f, (0.0, TRAVEL * f / vj.FRAMES, 0.0)) for f in (-30, vj.FRAMES + 30)])

    pipes, flange, steel, wheel, glass, lamp, vents = build_tunnel()
    mats = {}
    cx = sum(cam_path(f)[0] for f in range(vj.FRAMES)) / vj.FRAMES     # the camera's mean line
    cz = sum(cam_path(f)[1] for f in range(vj.FRAMES)) / vj.FRAMES
    for i, (x, z, r, g, bm) in enumerate(pipes):
        if g not in mats:
            mats[g] = pipe_mat(g)
        ob = vj.mesh_obj(f"Pipe{i}_{g}", vj.finish_bm(bm, smooth=True, name=f"PipeMesh{i}"), mats[g])
        ob.location = (x, 0.0, z)
        d = math.hypot(cx - x, cz - z)
        th = math.atan2(cz - z, cx - x)                                 # toward the camera's mean line
        ob.color = (th / (2 * math.pi) + 0.5, math.acos(min(r / d, 1.0)) / math.pi, 0.0, 1.0)
    for name, bm, mat in (("Flanges", flange, flange_mat()), ("Steel", steel, steel_mat()),
                          ("Handwheels", wheel, wheel_mat()), ("SightGlass", glass, glass_mat()),
                          ("Lamps", lamp, lamp_mat())):
        vj.mesh_obj(name, vj.finish_bm(bm, smooth=True, name=name + "Mesh"), mat)
    grate = vj.new_obj("Walkway", vj.quad_bm(4.0, Y1 - Y0, axis="Z"), grate_mat())
    grate.location = (0.0, (Y0 + Y1) / 2, 0.01)

    jet_me = vj.finish_bm(jet_bm(), smooth=True, name="JetMesh")
    m_steam = steam_mat()
    for i, (p, d) in enumerate(vents):
        ob = vj.mesh_obj(f"Jet{i}", jet_me, m_steam)
        ob.location = p
        ob.rotation_mode = "QUATERNION"
        ob.rotation_quaternion = d.to_track_quat("Z", "Y")

    cam = vj.camera(scene, lens=20.0, clip=(0.1, 160.0))   # nothing past 160 m: the far end (at least FAR = 175 m
                                                            # ahead all loop) looks the same on frame 0 and frame 411
    cam.data.shift_y = 0.04 if V["cam"] != "low" else 0.0
    loc, rot = [], []
    for f in vj.EXT:
        x, z, pitch, roll = cam_path(f)
        loc.append((f, (x, TRAVEL * f / vj.FRAMES, z - 0.05 * vj.clock(f)["kick"])))
        rot.append((f, (math.radians(90.0 + pitch + 0.5 * vj.jolt(f)), math.radians(roll), 0.0)))
    vj.keyed(cam, "location", loc)
    vj.keyed(cam, "rotation_euler", rot)
    return scene


scene = build()
vj.standard_render(scene)
vj.finish(scene, f"coolant_pipes_{VNAME}")
