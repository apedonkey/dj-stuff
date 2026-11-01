"""THRILLER YARD - GRAVEYARD SHIFT VJ loop (build). 8 bars, seamless, 1920x1080 @ 30 fps; tempo from vjkit
(140 BPM half-time = 411 frames).

A graveyard at night from a low camera: rows of tombstone silhouettes rim-lit in UV purple against a purple horizon
glow, low fog between them. Zombies claw their way out of the ground, ONE ROW PER BAR, from the farthest row (bar 1)
to the nearest (bar 8): the build comes toward you. They are black silhouettes with toxic-green rims and glowing eyes;
each rises over a beat on its bar's downbeat, sways, and on every snare (beat 3, half-time) the forearms claw forward
(the jolt lands a frame after the snare: motion carries the hit, not light). In the last two beats of bar 8 the yard
swells and every zombie ducks back into its grave, so the next downbeat starts the build again.
No strobing: the rims are thin lines, the eyes fade up with the rise, the swell is a two-beat crescendo.

  blender.exe -b --factory-startup --python thriller_yard.py -- --frames 0,60,206,350,400 [--pct 50] [--samples 16]
  blender.exe -b --factory-startup --python thriller_yard.py -- --all --seam DIR [--out DIR] [--mblur]
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
from vjkit import TOXIC, UVP  # noqa: E402

VARIANTS = {
    "uv": dict(stone=UVP, zombie=(0.30, 1.0, 0.10), eyes=TOXIC, sky=UVP),
}
VNAME, V = vj.variant(VARIANTS)
GAIN = float(vj.arg("--gain", 1.0))
ROWS_Y = [24.0, 20.5, 17.5, 14.8, 12.3, 10.0, 8.0, 6.2]          # zombie rows: bar 1 (far) .. bar 8 (near)
STONES_Y = [33.0, 22.2, 16.2, 11.2]                               # between the rows; none in front of the nearest
SINK = 2.0                                                        # beats: everyone ducks back before the downbeat


# ------------------------------------------------------------------ choreography
def rise(row, f):
    """0 = buried .. 1 = up, for the row that rises on bar `row` (0-based); periodic."""
    b = vj.beatpos(f % vj.FRAMES)
    start = 4.0 * row
    if b >= vj.BEATS - SINK:                                      # the fill: everyone goes down
        u = (b - (vj.BEATS - SINK)) / SINK
        return 1.0 - vj.ease(u) if b >= start else 0.0
    if b < start:
        return 0.0
    u = min(1.0, (b - start) / 1.0)                               # up over one beat, a small overshoot settles
    return vj.ease(u) + 0.08 * math.sin(math.pi * u) * (1.0 - u)


def claw(f, delay=1):
    """The forearms' claw on each snare (half-time beat 3): a 3-frame snap forward, then a slow return; periodic."""
    v = 0.0
    for k in range(2, vj.BEATS, 4):
        t = (f - vj.BEAT_F[k] - delay) % vj.FRAMES
        if t < 2.5 * vj.FPB:
            v = max(v, min(1.0, t / 3.0) * math.exp(-t / 14.0))
    return v


def fill(f):
    b = vj.beatpos(f % vj.FRAMES)
    if b >= vj.BEATS - SINK:
        return ((b - (vj.BEATS - SINK)) / SINK) ** 2
    return math.exp(-b / 1.2)


def signals(f):
    c = vj.clock(f)
    s = {"Kick": c["kick"], "Fill": fill(f)}
    s.update(vj.loop_signals(f))
    return s


# ------------------------------------------------------------------ materials
def rim_mat(name, col, base, kick=0.05):
    """A black silhouette with a neon rim (the facing-ratio outline)."""
    s = vj.Shader(name)
    lift = s.add(0.85, s.mul(s.c("Kick"), kick), s.mul(s.c("Fill"), 0.2))
    return s.emit(col, s.mul(s.rim(), lift, base * GAIN))


def eye_mat():
    s = vj.Shader("Eyes")
    _, alpha, _ = s.obj_info()
    lift = s.add(0.85, s.mul(s.c("Kick"), 0.15))
    return s.emit(V["eyes"], s.mul(alpha, lift, s.core(0.6, 1.3), 1.1 * GAIN))


def sky_mat():
    """The horizon glow: UV purple low on the sky, fading up to black; a little brighter in the fill."""
    s = vj.Shader("Sky")
    _, _, z = s.obj_coords()
    h = s.exp(s.mul(s.math("MAXIMUM", s.add(z, 1.0), 0.0), -1.0 / 7.0))
    lift = s.add(0.9, s.mul(s.c("Fill"), 0.25))
    return s.emit(V["sky"], s.mul(h, lift, 0.16 * GAIN))


def moon_mat():
    s = vj.Shader("Moon")
    x, _, z = s.obj_coords()
    n = s.noise4(s.vec(s.mul(x, 0.4), s.mul(z, 0.4), 0.0), 0.0, scale=1.6, detail=3.0)      # craters (static)
    return s.emit((0.62, 0.6, 0.66), s.mul(s.madd(n, 0.35, 0.7), 0.42 * GAIN))


def moon_halo_mat():
    s = vj.Shader("MoonHalo")
    x, _, z = s.obj_coords()
    r = s.length2(x, z)
    return s.additive(V["sky"], s.mul(s.exp(s.mul(s.mul(r, r), -1.0 / 49.0)), 0.06 * GAIN))


def fog_mat():
    s = vj.Shader("Fog")
    x, _, z = s.obj_coords()
    v = s.vec(s.mul(x, 0.09), s.madd(z, 0.25, s.mul(s.c("LoopCos"), 0.35)), s.mul(s.c("LoopSin"), 0.35))
    n = s.noise4(v, s.mul(s.c("LoopSin"), 0.3), scale=1.3, detail=4.0, rough=0.55)
    wisp = s.smooth(n, 0.45, 0.78)
    low = s.inv(s.smooth(z, -0.6, 1.4))
    return s.additive(V["sky"], s.mul(wisp, low, 0.07 * GAIN))


# ------------------------------------------------------------------ geometry
def stone_outline(kind, w, h):
    if kind == "round":
        top = [(w / 2 * math.cos(math.radians(a)), h - w / 2 + w / 2 * math.sin(math.radians(a))) for a in range(0, 181, 15)]
        return [(w / 2, 0.0)] + top + [(-w / 2, 0.0)]
    if kind == "cross":
        a, t = w * 0.5, w * 0.16
        return [(t, 0.0), (t, h * 0.62), (a, h * 0.62), (a, h * 0.78), (t, h * 0.78), (t, h), (-t, h), (-t, h * 0.78),
                (-a, h * 0.78), (-a, h * 0.62), (-t, h * 0.62), (-t, 0.0)]
    if kind == "gothic":
        return g.lancet(0.0, 0.0, w, h, n=6)
    return [(w / 2, 0.0), (w / 2, h * 0.9), (w * 0.3, h), (-w * 0.3, h), (-w / 2, h * 0.9), (-w / 2, 0.0)]


def stone_bm(rnd):
    bm = bmesh.new()
    kind = rnd.choice(("round", "round", "cross", "gothic", "slab"))
    w, h = rnd.uniform(0.6, 1.0), rnd.uniform(0.9, 1.6) * (1.25 if kind == "cross" else 1.0)
    g.extrude(bm, stone_outline(kind, w, h), 0.2, y0=-0.1)
    tilt = Matrix.Rotation(math.radians(rnd.uniform(-9, 9)), 4, "Y") @ Matrix.Rotation(math.radians(rnd.uniform(-6, 6)), 4, "X")
    bmesh.ops.transform(bm, matrix=tilt, verts=bm.verts)
    return bm


def arm_upper_bm(length, r):
    bm = bmesh.new()
    vj.tube(bm, [Vector((0, 0, 0)), Vector((0, 0, length))], lambda u: r * (1.0 - 0.15 * u), segs=8)
    return bm


def forearm_bm(length, r):
    """Forearm up +Z from the elbow, a bony hand with four clawed fingers and a thumb at its end."""
    bm = bmesh.new()
    vj.tube(bm, [Vector((0, 0, 0)), Vector((0, 0, length))], lambda u: r * (1.0 - 0.3 * u), segs=8)
    w = Vector((0, 0, length))
    bmesh.ops.create_icosphere(bm, subdivisions=1, radius=r * 1.25, matrix=Matrix.Translation(w))
    for i, dx in enumerate((-1.5, -0.5, 0.5, 1.5)):
        base = w + Vector((dx * r * 0.7, 0.0, r * 0.8))
        mid = base + Vector((dx * r * 0.25, -r * 0.5, r * 2.6))
        tip = mid + Vector((0.0, -r * 1.4, r * 0.6))                # hooked toward the camera: claws
        vj.tube(bm, [base, mid, tip], lambda u: r * 0.32 * (1.0 - 0.6 * u), segs=5)
    vj.tube(bm, [w + Vector((r * 1.3, 0, 0)), w + Vector((r * 2.4, -r * 0.6, r * 1.2))],
            lambda u: r * 0.3 * (1.0 - 0.5 * u), segs=5)
    return bm


def body_bm(rnd):
    """Head, neck and shoulders, a torso running down into the ground (origin at the neck's base)."""
    bm = bmesh.new()
    head_r = rnd.uniform(0.27, 0.33)
    tilt = rnd.uniform(-0.12, 0.12)
    head_c = Vector((tilt, -0.02, 0.18 + head_r))
    bmesh.ops.create_uvsphere(bm, u_segments=12, v_segments=8, radius=head_r,
                              matrix=Matrix.Translation(head_c) @ Matrix.Diagonal((1.0, 0.95, 1.15, 1.0)))
    vj.tube(bm, [Vector((0, 0, -0.05)), Vector((tilt * 0.5, 0, 0.24))], lambda u: 0.11, segs=8)
    vj.tube(bm, [Vector((-0.42, 0, -0.08)), Vector((0, 0, 0.02)), Vector((0.42, 0, -0.08))], lambda u: 0.13, segs=8)
    vj.tube(bm, [Vector((0, 0, -0.05)), Vector((0, 0.03, -1.9))], lambda u: 0.3 + 0.05 * u, segs=10)
    return bm, head_c, head_r


# ------------------------------------------------------------------ scene
def build():
    scene = vj.reset_scene()
    vj.clock_from(signals)
    ext = vj.EXT
    rnd = random.Random(31)
    black = vj.black_mat()

    ground = vj.new_obj("Ground", vj.quad_bm(200.0, 200.0, axis="Z"), black)      # hides the buried zombies
    ground.location = (0.0, 40.0, 0.0)
    sky = vj.new_obj("Sky", vj.quad_bm(220.0, 60.0), sky_mat())
    sky.location = (0.0, 95.0, 20.0)
    moon = vj.new_obj("Moon", vj.disc_bm(4.5, 64), moon_mat())          # a focal point in the sky
    moon.location = (-24.0, 92.0, 15.0)
    halo = vj.new_obj("MoonHalo", vj.quad_bm(26.0, 26.0), moon_halo_mat())
    halo.location = (-24.0, 93.0, 15.0)

    stone_m = rim_mat("Stones", V["stone"], 0.7)
    for y in STONES_Y:
        n = int(5 + y * 0.35)
        half = 2.5 + y * 0.62
        for i in range(n):
            x = -half + 2 * half * (i + rnd.uniform(0.2, 0.8)) / n
            ob = vj.new_obj(f"Stone_{y:.0f}_{i}", stone_bm(rnd), stone_m)
            ob.location = (x, y + rnd.uniform(-0.4, 0.4), -0.05)
            ob.rotation_euler = (0.0, 0.0, math.radians(rnd.uniform(-14, 14)))

    zom_m = rim_mat("Zombies", V["zombie"], 0.55, kick=0.08)
    eye_m = eye_mat()
    eye_me = vj.finish_bm(_eye_bm(), name="EyeMesh")
    for row, y in enumerate(ROWS_Y):
        n = 4 + (len(ROWS_Y) - row) // 2
        half = 2.0 + y * 0.5
        xs = sorted(-half + 2 * half * (i + rnd.uniform(0.25, 0.75)) / n for i in range(n))
        for i, x in enumerate(xs):
            root = vj.new_empty(f"Z{row}_{i}")
            yaw = rnd.uniform(-0.35, 0.35)
            up = rnd.uniform(0.55, 1.15)                                # how far out of the ground (top of torso)
            bm, head_c, head_r = body_bm(rnd)
            vj.new_obj(f"Z{row}_{i}_Body", bm, zom_m, root)
            for sx in (-1, 1):                                        # eyes
                e = vj.mesh_obj(f"Z{row}_{i}_Eye{sx}", eye_me, eye_m, root)
                e.location = head_c + Vector((sx * head_r * 0.36, -head_r * 0.92, head_r * 0.12))
                e.scale = (head_r * 0.33,) * 3
            arms = []
            for sx in (-1, 1):
                sh = vj.new_empty(f"Z{row}_{i}_Sh{sx}", root)
                sh.location = (sx * 0.42, 0.0, -0.08)
                sh.rotation_euler = (math.radians(rnd.uniform(5, 25)), math.radians(sx * rnd.uniform(18, 38)), 0.0)  # reach toward the camera
                ua = rnd.uniform(0.55, 0.7)
                vj.new_obj(f"Z{row}_{i}_Ua{sx}", arm_upper_bm(ua, 0.075), zom_m, sh)
                el = vj.new_empty(f"Z{row}_{i}_El{sx}", sh)
                el.location = (0.0, 0.0, ua)
                vj.new_obj(f"Z{row}_{i}_Fa{sx}", forearm_bm(rnd.uniform(0.5, 0.62), 0.065), zom_m, el)
                arms.append((el, rnd.uniform(-5, 12)))
            ph, sway = rnd.uniform(0, 2 * math.pi), rnd.uniform(3.0, 7.0)
            lag = rnd.uniform(0.0, 4.0)                                # frames: a ragged rise within the row
            keys_l, keys_r, keys_e = [], [], []
            for f in ext:
                r_ = rise(row, f - lag)
                z = -2.3 + (2.3 + up - 0.45) * r_                          # the neck base: buried .. up - 0.45
                keys_l.append((f, (x, y, z)))
                a = 2 * math.pi * f / vj.FRAMES
                keys_r.append((f, (math.radians(sway * 0.4 * math.sin(2 * a + ph)),
                                   math.radians(sway * math.sin(a * 2 + ph + 1.0)), yaw)))
                keys_e.append((f, (1.0, 1.0, 1.0, vj.ease(r_))))
            root.location = (x, y, -2.3)
            vj.keyed(root, "location", keys_l)
            vj.keyed(root, "rotation_euler", keys_r)
            for e in [o for o in root.children if "_Eye" in o.name]:
                vj.keyed(e, "color", keys_e)
            for el, rest in arms:
                vj.keyed(el, "rotation_euler", [(f, (math.radians(rest + 42.0 * claw(f, 1 + int(lag / 2)) * rise(row, f)),
                                                     0.0, 0.0)) for f in ext])

    fog = vj.new_obj("Fog", vj.quad_bm(80.0, 4.0), fog_mat())
    fog.location = (0.0, 12.0, 0.6)
    fog2 = vj.new_obj("Fog2", vj.quad_bm(110.0, 5.0), fog_mat())
    fog2.location = (0.0, 26.0, 0.9)

    cam = vj.camera(scene, lens=32.0, clip=(0.3, 400.0))
    loc, rot = [], []
    for f in ext:
        a = 2 * math.pi * f / vj.FRAMES
        thump = 0.06 * vj.jolt(f, decay=3.0, period=5.0, delay=1)
        p = Vector((0.9 * math.sin(a), -3.0 + 0.25 * math.sin(2 * a), 2.2 + 0.12 * math.sin(a + 0.7) + thump))
        loc.append((f, tuple(p)))                                     # higher, tilted 6 deg down: the yard fills the
        rot.append((f, tuple(vj.look_at(p, (0.25 * math.sin(a + 0.4), 30.0, -1.3), roll=0.5 * math.sin(a + 1.3)))))
    vj.keyed(cam, "location", loc)
    vj.keyed(cam, "rotation_euler", rot)
    return scene


def _eye_bm():
    bm = bmesh.new()
    bmesh.ops.create_icosphere(bm, subdivisions=2, radius=1.0)
    return bm


scene = build()
vj.standard_render(scene)
vj.finish(scene, f"thriller_yard_{VNAME}")
