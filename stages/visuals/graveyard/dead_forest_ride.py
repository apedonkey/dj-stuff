"""DEAD FOREST RIDE - GRAVEYARD SHIFT VJ loop (build into drop). 8 bars, seamless, 1920x1080 @ 30 fps; tempo from
vjkit (140 BPM half-time = 411 frames). The Spine Tunnel method: the camera travels a whole number of forest periods
per loop and the geometry runs on behind the far backdrop, so frame 411 equals frame 0.

A ride down a path through an avenue of neon dead trees whose gnarled branches arch overhead into a tunnel. A lantern
hangs from the canopy every 4 m, so one passes the camera per beat, swinging once per bar. The path is a laser grid in
low mist; at the end of the tunnel a pale moon rides with the camera, bats crossing it.
  Bars 1-4: UV-purple trees, an orange grid.  Bars 5-8: the forest turns toxic green, the grid purple (the morph
  lands on bar 5's downbeat and back on the next downbeat). The last two beats of bars 4 and 8 swell into the hit.
Beat hooks: a lantern per beat (motion), on every accent (kick and snare) a light wave runs away down the tunnel and the
lens punches in a little; the lanterns flare softly as the wave passes.
No strobing: the wave is slow and wide, the trees fade with distance, nothing near the lens is bright.

  blender.exe -b --factory-startup --python dead_forest_ride.py -- --frames 0,100,300 [--pct 50] [--samples 16]
  blender.exe -b --factory-startup --python dead_forest_ride.py -- --all --seam DIR [--out DIR] [--mblur]
"""
import math
import os
import random
import sys

import bmesh
import bpy
from mathutils import Matrix, Quaternion, Vector

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import vjkit as vj  # noqa: E402
import hwgeo as g  # noqa: E402
import bats  # noqa: E402
from vjkit import BONE, MOONBLUE, PUMPKIN, TOXIC, UVP  # noqa: E402

VARIANTS = {
    "toxic": dict(trees=(UVP, (0.12, 0.85, 0.02)), grid=(PUMPKIN, UVP), lantern=PUMPKIN, moon=(0.55, 0.62, 0.8)),
}
VNAME, V = vj.variant(VARIANTS)
GAIN = float(vj.arg("--gain", 1.0))

D = 4.0                                   # camera travel per beat (m): a lantern per beat
TRAVEL = vj.BEATS * D                     # 128 m per loop = one forest period
CAM_Z = 2.4
MOON_DIST, MOON_R, MOON_Z = 320.0, 70.0, 34.0
FADE = 34.0                               # trees fade as exp(-distance / FADE)
WAVE = (70.0, 11.0)                       # accent light wave: m travelled per accent, width (m)
PUNCH = 0.03


# ------------------------------------------------------------------ music
def signals(f):
    c = vj.clock(f)
    s = {"Kick": c["kick"], "WavePos": c["aph"], "WaveAmp": (1 - c["aph"]) ** 1.5, "Swell": vj.swell(f),
         "Section": vj.section(f), "BeatPos": c["beatpos"]}
    s.update(vj.loop_signals(f))
    return s


# ------------------------------------------------------------------ trees
def branch(bm, base, direction, length, radius, depth, rng, pull, segs=7):
    """A gnarled branch: a bent polyline tube; children sprout from its outer part (recursive)."""
    n = 6
    pts, d, p = [base.copy()], direction.normalized(), base.copy()
    for i in range(n):
        jitter = Vector((rng.gauss(0, 0.22), rng.gauss(0, 0.22), rng.gauss(0, 0.16)))
        d = (d + jitter + pull * (0.12 + 0.05 * i)).normalized()
        p = p + d * (length / n)
        pts.append(p.copy())
    r0, r1 = radius, radius * 0.55
    vj.tube(bm, pts, lambda u: r0 + (r1 - r0) * u, segs=segs, tip=depth == 0)
    if depth == 0:
        return
    for k in range(rng.choice((2, 2, 3))):
        i = rng.randint(3, n)
        q = pts[i]
        dd = (pts[min(i + 1, n)] - pts[i - 1]).normalized()
        axis = dd.cross(Vector((rng.uniform(-1, 1), rng.uniform(-1, 1), rng.uniform(-1, 1)))).normalized()
        child = (Matrix.Rotation(math.radians(rng.uniform(25, 55)), 3, axis) @ dd)
        branch(bm, q, child, length * rng.uniform(0.5, 0.7), r1 * 0.85, depth - 1, rng, pull, segs=max(segs - 1, 4))


def tree(bm, x, y, height, rng, lean_in=True):
    side = 1.0 if x > 0 else -1.0
    base = Vector((x, y, -0.3))
    trunk_dir = Vector((-side * (0.32 if lean_in else 0.12) + rng.uniform(-0.08, 0.08), rng.uniform(-0.1, 0.1), 1.0))
    n = 7
    pts, d, p = [base.copy()], trunk_dir.normalized(), base.copy()
    for i in range(n):
        d = (d + Vector((rng.gauss(0, 0.1), rng.gauss(0, 0.1), 0.0))).normalized()
        p = p + d * (height / n)
        pts.append(p.copy())
    r0 = rng.uniform(0.17, 0.25)
    vj.tube(bm, pts, lambda u: r0 * (1.0 - 0.6 * u), segs=9, tip=True)
    for k in range(4):                                                # roots
        a = rng.uniform(0, 2 * math.pi)
        rd = Vector((math.cos(a), math.sin(a), -0.35))
        branch(bm, base + Vector((0, 0, 0.5)), rd, rng.uniform(1.0, 1.8), r0 * 0.45, 0, rng, Vector((0, 0, -0.4)),
               segs=5)
    inward = Vector((-side, 0.0, 0.0))
    for k in range(rng.choice((4, 5))):                               # main limbs: most arch over the path
        i = rng.randint(3, n - 1)
        q = pts[i]
        over = k < 3 and lean_in
        dirv = (inward * (1.0 if over else -0.6) + Vector((rng.uniform(-0.4, 0.4), 0.0, rng.uniform(0.5, 1.1))))
        pull = Vector((0.0, 0.0, -0.25)) if over else Vector((0.0, 0.0, 0.05))   # the arching limbs droop
        branch(bm, q, dirv, rng.uniform(3.2, 5.2) if over else rng.uniform(2.0, 3.4), r0 * 0.5, 2, rng, pull)


def forest_period(seed):
    """All trees of one 128 m period (near avenue rows + a dimmer far row), as two bmeshes."""
    rng = random.Random(seed)
    near, far = bmesh.new(), bmesh.new()
    for side in (-1, 1):
        y = rng.uniform(0, 3)
        while y < TRAVEL - 3.0:
            tree(near, side * rng.uniform(3.9, 5.3), y, rng.uniform(7.0, 10.0), rng)
            y += rng.uniform(6.5, 9.5)
        y = rng.uniform(0, 6)
        while y < TRAVEL - 6.0:
            tree(far, side * rng.uniform(8.5, 15.0), y, rng.uniform(6.0, 11.0), rng, lean_in=False)
            y += rng.uniform(6.0, 10.0)
    return near, far


# ------------------------------------------------------------------ materials
def tree_mat(name, base):
    """Rim-lit silhouettes: black wood with neon edges (thin far branches read as single neon lines, near trunks as
    two edge lines around a black body), fading with distance."""
    s = vj.Shader(name)
    d = s.dist
    near = s.mul(s.c("Kick"), s.falloff(d, 20.0))
    wave = s.mul(s.c("WaveAmp"), s.gauss(d, s.madd(s.c("WavePos"), WAVE[0], 9.0), WAVE[1]))
    lift = s.add(0.6, s.mul(near, 0.25), s.mul(wave, 0.45), s.mul(s.c("Swell"), 0.45))
    col = s.mix(s.c("Section"), V["trees"][0], V["trees"][1])
    green_dim = s.madd(s.c("Section"), -0.35, 1.0)
    fade = s.mul(s.falloff(d, FADE), s.smooth(d, 0.8, 3.0))           # nothing glares right at the lens
    edge = s.rim((0.42, 0.93))
    return s.emit(col, s.mul(fade, edge, lift, green_dim, base * GAIN))


def grid_mat():
    s = vj.Shader("PathGrid")
    x, y, _ = s.world_pos()

    def lines(v, spacing, half_w):
        t = s.math("FRACT", s.madd(v, 1.0 / spacing, 0.5))
        dist = s.mul(s.math("ABSOLUTE", s.sub(t, 0.5)), spacing)
        return s.inv(s.smooth(dist, half_w, half_w * 2.5))

    g_ = s.math("MAXIMUM", lines(x, 1.0, 0.03), lines(y, 2.0, 0.03))
    path = s.inv(s.smooth(s.math("ABSOLUTE", x), 1.6, 2.6))           # a 4 m wide path, fading at its edges
    d = s.dist
    wave = s.mul(s.c("WaveAmp"), s.gauss(d, s.madd(s.c("WavePos"), WAVE[0], 9.0), WAVE[1]))
    lift = s.add(0.5, s.mul(wave, 0.35), s.mul(s.c("Swell"), 0.4), s.mul(s.c("Kick"), 0.1))
    col = s.mix(s.c("Section"), V["grid"][0], V["grid"][1])
    return s.emit(col, s.mul(g_, path, s.falloff(d, 30.0), lift, 1.3 * GAIN))


def mist_mat():
    """Low mist along the path: noise periodic over the forest period (y mapped onto a circle), static in the world."""
    s = vj.Shader("Mist")
    x, y, _ = s.world_pos()
    ang = s.mul(y, 2 * math.pi / TRAVEL)
    rc = TRAVEL / (2 * math.pi) * 0.09
    n = s.noise4(s.vec(s.mul(x, 0.09), s.mul(s.math("COSINE", ang), rc), s.mul(s.math("SINE", ang), rc)),
                 s.mul(s.c("LoopSin"), 0.3), scale=1.0, detail=3.0)
    m = s.smooth(n, 0.45, 0.75)
    col = s.mix(s.c("Section"), V["trees"][0], V["trees"][1])
    return s.additive(col, s.mul(m, s.falloff(s.dist, 40.0), s.smooth(s.dist, 2.0, 6.0),
                                 s.madd(s.c("Section"), -0.4, 1.0), 0.05 * GAIN))


def lantern_mat():
    """Lantern frames: pumpkin glow, flaring softly as the accent wave passes."""
    s = vj.Shader("Lantern")
    d = s.dist
    wave = s.mul(s.c("WaveAmp"), s.gauss(d, s.madd(s.c("WavePos"), WAVE[0], 9.0), WAVE[1]))
    lift = s.add(0.75, s.mul(wave, 0.5), s.mul(s.c("Swell"), 0.4))
    return s.emit(V["lantern"], s.mul(lift, s.core(0.5, 1.4), s.falloff(d, 40.0), s.smooth(d, 2.5, 9.0),
                                      1.6 * GAIN))


def flame_mat():
    s = vj.Shader("LanternFlame")
    d = s.dist
    rnd = s.mul(s.node("ShaderNodeObjectInfo").outputs["Object Index"], 0.137)   # per slot (pass index)
    n = s.noise4(s.vec(s.mul(rnd, 50.0), s.mul(s.c("LoopCos"), 3.0), s.mul(s.c("LoopSin"), 3.0)), rnd, scale=2.0)
    flick = s.madd(n, 0.5, 0.75)
    wave = s.mul(s.c("WaveAmp"), s.gauss(d, s.madd(s.c("WavePos"), WAVE[0], 9.0), WAVE[1]))
    lift = s.add(0.8, s.mul(wave, 0.5), s.mul(s.c("Swell"), 0.3))
    return s.emit((1.0, 0.42, 0.06), s.mul(flick, lift, s.falloff(d, 40.0), s.smooth(d, 2.5, 9.0), 1.5 * GAIN))


def moon_mat():
    s = vj.Shader("PaleMoon")
    x, _, z = s.obj_coords()
    qx, qz = s.mul(x, 1.0 / MOON_R), s.mul(z, 1.0 / MOON_R)
    r = s.length2(qx, qz)
    maria = s.smooth(s.noise4(s.vec(s.mul(qx, 1.3), s.mul(qz, 1.3), 1.7), 0.3, scale=1.7, detail=5.0), 0.43, 0.62)
    limb = s.inv(s.smooth(r, 0.8, 1.0))
    lvl = s.add(0.5, s.mul(maria, -0.22), s.mul(limb, 0.1))
    lift = s.add(1.0, s.mul(s.c("Swell"), 0.18), s.mul(s.c("Kick"), 0.04))
    return s.emit(V["moon"], s.mul(lvl, lift, 0.62 * GAIN))


def moon_glow_mat():
    s = vj.Shader("MoonGlow")
    x, _, z = s.obj_coords()
    r = s.mul(s.length2(x, z), 1.0 / MOON_R)
    glow = s.mul(s.exp(s.mul(s.math("MAXIMUM", s.sub(r, 1.0), 0.0), -5.0)), s.smooth(r, 0.98, 1.03))
    return s.additive(MOONBLUE, s.mul(glow, 0.035 * GAIN))


def star_mat():
    s = vj.Shader("Stars")
    x, y, z = s.obj_coords()
    n = s.noise4(s.vec(s.mul(x, 0.03), s.mul(z, 0.03), s.c("LoopCos")), s.c("LoopSin"), scale=3.0)
    return s.emit((0.8, 0.82, 1.0), s.mul(s.madd(s.smooth(n, 0.3, 0.7), 0.6, 0.3), 0.8 * GAIN))


# ------------------------------------------------------------------ lanterns
def lantern_bm():
    """A small iron lantern: a square cage with a pointed cap and a ring, hanging from a chain (local origin = hook)."""
    bm = bmesh.new()
    w, h, top = 0.22, 0.42, -0.9
    corners = [(-w, -w), (w, -w), (w, w), (-w, w)]
    for cx, cy in corners:
        g.stroke(bm, [Vector((cx, cy, top)), Vector((cx, cy, top - h))], 0.013, segs=5, joints=False)
    for z in (top, top - h):
        g.stroke(bm, [Vector((cx, cy, z)) for cx, cy in corners], 0.013, segs=5, closed=True, joints=False)
    for cx, cy in corners:
        g.stroke(bm, [Vector((cx, cy, top)), Vector((0, 0, top + 0.2))], 0.013, segs=5, joints=False)
    g.stroke(bm, [Vector((0, 0, 0)), Vector((0, 0, top + 0.2))], 0.012, segs=4, joints=False)
    return bm


def flame_bm():
    bm = bmesh.new()
    s = bmesh.ops.create_uvsphere(bm, u_segments=10, v_segments=8, radius=1.0)
    bmesh.ops.scale(bm, vec=(0.07, 0.07, 0.13), verts=s["verts"])
    bmesh.ops.translate(bm, vec=(0.0, 0.0, -1.1), verts=s["verts"])
    return bm


# ------------------------------------------------------------------ scene
def cam_path(f):
    """(x, z, roll) of the camera: a gentle periodic weave down the path."""
    a = 2 * math.pi * f / vj.FRAMES
    return 0.55 * math.sin(a), CAM_Z + 0.25 * math.sin(2 * a + 0.6), 2.5 * math.sin(a + 0.4)


def build():
    scene = vj.reset_scene()
    vj.clock_from(signals)
    ext = vj.EXT

    near_bm, far_bm = forest_period(17)
    near_me = vj.finish_bm(near_bm, smooth=True, name="ForestNear")
    far_me = vj.finish_bm(far_bm, smooth=True, name="ForestFar")
    t_near, t_far = tree_mat("TreesNear", 2.4), tree_mat("TreesFar", 1.5)
    n_inst = int(math.ceil((MOON_DIST + 60.0) / TRAVEL)) + 2
    for k in range(-1, n_inst):
        vj.mesh_obj(f"Near{k}", near_me, t_near).location = (0.0, k * TRAVEL, 0.0)
        vj.mesh_obj(f"Far{k}", far_me, t_far).location = (0.0, k * TRAVEL, 0.0)

    floor = bmesh.new()
    bmesh.ops.create_grid(floor, x_segments=1, y_segments=1, size=1.0)
    bmesh.ops.scale(floor, vec=(300.0, 0.5 * TRAVEL * (n_inst + 2), 1.0), verts=floor.verts)
    bmesh.ops.translate(floor, vec=(0.0, 0.5 * TRAVEL * (n_inst + 2) - TRAVEL, 0.0), verts=floor.verts)
    vj.new_obj("Ground", floor, grid_mat())
    mist = bmesh.new()
    bmesh.ops.create_grid(mist, x_segments=1, y_segments=1, size=1.0)
    bmesh.ops.scale(mist, vec=(40.0, 0.5 * TRAVEL * (n_inst + 2), 1.0), verts=mist.verts)
    bmesh.ops.translate(mist, vec=(0.0, 0.5 * TRAVEL * (n_inst + 2) - TRAVEL, 0.45), verts=mist.verts)
    vj.new_obj("Mist", mist, mist_mat())

    lmat, fmat = lantern_mat(), flame_mat()
    l_me = vj.finish_bm(lantern_bm(), smooth=False, name="Lantern")
    f_me = vj.finish_bm(flame_bm(), smooth=True, name="Flame")
    for k in range(-1, n_inst):
        for j in range(vj.BEATS):
            rng = random.Random(500 + j)                               # per slot, the same in every period copy
            y = k * TRAVEL + j * D + 2.0
            hook = vj.new_empty(f"Hook{k}_{j}")
            hook.location = (1.45 * (1 if j % 2 else -1) + rng.uniform(-0.2, 0.2), y, 5.0 + rng.uniform(-0.25, 0.25))
            vj.mesh_obj(f"Lantern{k}_{j}", l_me, lmat, hook)
            fl = vj.mesh_obj(f"Flame{k}_{j}", f_me, fmat, hook)
            fl.pass_index = j
            ph = rng.uniform(0, 2 * math.pi)
            vj.keyed(hook, "rotation_euler", [(f, (math.radians(9.0 * math.sin(2 * math.pi * vj.beatpos(f) / 4 + ph)),
                                                   math.radians(5.0 * math.cos(2 * math.pi * vj.beatpos(f) / 4 + ph)),
                                                   0.0)) for f in range(-2, vj.FRAMES + 3, 1)])

    rig = vj.new_empty("FarRig")                                       # rides with the camera, never rolls
    vj.keyed(rig, "location", [(f, (0.0, TRAVEL * f / vj.FRAMES, 0.0)) for f in (-30, vj.FRAMES + 30)])
    moon = vj.new_obj("Moon", vj.disc_bm(MOON_R, 160), moon_mat(), rig)
    moon.location = (0.0, MOON_DIST, MOON_Z)
    glow = vj.new_obj("MoonGlow", vj.disc_bm(MOON_R * 1.7, 128), moon_glow_mat(), rig)
    glow.location = (0.0, MOON_DIST - 1.0, MOON_Z)
    sb = bmesh.new()
    srng = random.Random(9)
    for _ in range(220):
        x, z = srng.uniform(-420, 420), srng.uniform(5, 260)
        if math.hypot(x, z - MOON_Z) < MOON_R * 1.3:
            continue
        bmesh.ops.create_icosphere(sb, subdivisions=1, radius=srng.uniform(0.35, 0.7),
                                   matrix=Matrix.Translation((x, MOON_DIST + 20.0, z)))
    vj.new_obj("Stars", sb, star_mat(), rig)

    rim = bats.rim_mat("BatRim", gain=0.8, near=(1.0, 2.0), far=(900.0, 1000.0))
    meshes = bats.bat_meshes(rim, vj.black_mat("BatBlack"))
    brng = random.Random(41)
    for i in range(9):                                                 # bats crossing the moon, in rig space
        s0 = (i // 3) * 137.0 + brng.uniform(-12, 12)
        T = brng.uniform(140, 200)
        yb = MOON_DIST - brng.uniform(30, 90)
        half = yb * 18.0 / 24.0 * 0.9
        zb = MOON_Z + brng.uniform(-0.5, 0.5) * MOON_R * (yb / MOON_DIST)
        size = brng.uniform(1.0, 1.3) * yb / 22.0
        ph, bob = brng.uniform(-0.15, 0.15), brng.uniform(0, 6.28)
        body, wl, wr = bats.make_bat(f"Bat{i}", meshes, color=V["lantern"])
        body.parent = rig
        sts = []
        for f in ext:
            age = (f - s0) % vj.FRAMES
            fl = bats.flap_angle(f, ph, amp=48.0)
            dirx = -1.0 if i % 2 else 1.0
            if age >= T:
                x = dirx * half if age < T + 30 else -dirx * half
                sts.append((f, Vector((x, yb, zb)), bats.heading(Vector((dirx, 0, 0))), 0.0001, fl))
                continue
            u = age / T
            x = -dirx * half + 2 * dirx * half * u
            z = zb + 0.04 * yb * math.sin(2 * math.pi * 1.5 * u + bob) * 0.1
            sts.append((f, Vector((x, yb, z)), bats.heading(Vector((dirx, 0.0, 0.0))), size, fl))
        bats.key_bat(body, wl, wr, sts)

    cam = vj.camera(scene, lens=24.0, clip=(0.2, 1500.0))
    cam.data.shift_y = 0.06
    loc, rot, lens = [], [], []
    for f in ext:
        x, z, roll = cam_path(f)
        dip = 0.06 * vj.clock(f)["kick"]
        loc.append((f, (x, TRAVEL * f / vj.FRAMES, z - dip)))
        rot.append((f, (math.radians(90.0 + 2.0), math.radians(roll), 0.0)))
        lens.append((f, 24.0 * (1.0 + PUNCH * vj.clock(f)["kick"])))
    vj.keyed(cam, "location", loc)
    vj.keyed(cam, "rotation_euler", rot)
    vj.keyed(cam.data, "lens", lens)
    return scene


scene = build()
vj.standard_render(scene)
vj.finish(scene, f"dead_forest_ride_{VNAME}")
