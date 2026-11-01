"""PUMPKIN STOMP - GRAVEYARD SHIFT VJ loop (heavy drop). 8 bars, seamless, 1920x1080 @ 30 fps; tempo from vjkit
(140 BPM half-time = 411 frames).

Giant jack-o'-lanterns slam toward the camera on the kick (beat 1) and the snare (beat 3): each one rushes in out of
the dark, spinning, and stops dead in front of the lens, filling the frame. It squashes, its carved face flares, green
cracks race across the shell from the impact, the camera thumps a frame later; then it is knocked aside and rolls back
into the pumpkin patch, still glowing, while the next one comes in. Every fourth slam (the downbeats of bars 1, 3, 5,
7) is the Pumpkin King: bigger, crowned, with a wider grin.
  Bars 1-4: faces burn orange, cracks glow toxic green.  Bars 5-8: the faces burn green and the cracks orange (the
  morph lands with the King on bar 5's downbeat). The last two beats of bars 4 and 8 swell into the hit.
No strobing: the slammed pumpkin keeps glowing as it rolls away (no dark gap between hits), the flare is soft, the
camera jolt lands a frame after the impact.

  blender.exe -b --factory-startup --python pumpkin_stomp.py -- --frames 0,6,20,40 [--pct 50] [--samples 16]
  blender.exe -b --factory-startup --python pumpkin_stomp.py -- --all --seam DIR [--out DIR] [--mblur]
"""
import math
import os
import random
import sys

import bmesh
import bpy
from mathutils import Euler, Matrix, Vector

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import vjkit as vj  # noqa: E402
import hwgeo as g  # noqa: E402
from vjkit import PUMPKIN, TOXIC, UVP  # noqa: E402

VARIANTS = {
    "patch": dict(face=((1.0, 0.36, 0.05), (0.2, 0.75, 0.02)), crack=((0.15, 1.0, 0.03), (1.0, 0.3, 0.02)),
                  shell=PUMPKIN, crown=(1.0, 0.45, 0.06)),
}
VNAME, V = vj.variant(VARIANTS)
GAIN = float(vj.arg("--gain", 1.0))

CAM = Vector((0.0, 0.0, 1.6))
SLAM = Vector((0.0, 5.2, 1.45))           # where a pumpkin stops (center); the camera looks at it
R_N, R_K = 1.15, 1.5                      # pumpkin radius: normal, King
SQ = 0.82                                 # vertical squash of a pumpkin
ACC_F = vj.FPB * vj.ACC                   # frames between accents (25.7)
N_SLAMS = vj.BEATS // vj.ACC              # 16 per loop
LIFE_AFTER = 4.2                          # accents a pumpkin stays visible after its slam
HOLD = 0.72                               # accents it holds at the slam spot before the next one knocks it aside
AGE0 = 40.0                               # object color R = age (accents) + AGE0


# ------------------------------------------------------------------ music
def signals(f):
    c = vj.clock(f)
    s = {"Kick": c["kick"], "Swell": vj.swell(f), "Section": vj.section(f, morph=6)}
    s.update(vj.loop_signals(f))
    return s


# ------------------------------------------------------------------ pumpkin geometry
def shell_bm(r, seed, king=False):
    """A ribbed pumpkin (10 lobes), squashed, dimpled at the poles; the ribs smooth out on the face side (-Y) so the
    carved face sits on a smooth surface. Plus a curved stem."""
    rnd = random.Random(seed)
    bm = bmesh.new()
    s = bmesh.ops.create_uvsphere(bm, u_segments=56, v_segments=28, radius=1.0)
    for v in s["verts"]:
        x, y, z = v.co
        phi = math.atan2(y, x)
        front = max(0.0, -y / max(math.sqrt(x * x + y * y + z * z), 1e-6))   # 1 facing the camera
        face = vj.ease((front - 0.55) / 0.35)
        lobe = 1.0 - 0.075 * (1.0 - abs(math.cos(5 * phi + 0.3))) ** 2.2 * (1.0 - face)
        pole = 1.0 - 0.18 * max(0.0, abs(z) - 0.75) / 0.25
        v.co = Vector((x * lobe * pole * r, y * lobe * pole * r, z * SQ * r))
    for v in s["verts"]:                                               # top dimple
        if v.co.z > 0.7 * SQ * r and math.hypot(v.co.x, v.co.y) < 0.35 * r:
            v.co.z -= 0.12 * r * (1.0 - math.hypot(v.co.x, v.co.y) / (0.35 * r))
    st = [Vector((0, 0, SQ * r * 0.86)), Vector((0.05 * r, 0.02 * r, SQ * r * 1.05)),
          Vector((0.14 * r, 0.06 * r, SQ * r * 1.2)), Vector((0.26 * r, 0.04 * r, SQ * r * 1.26))]
    vj.tube(bm, st, lambda u: (0.11 - 0.05 * u) * r, segs=8, tip=True)
    return bm


def front_point(x, z, r, lift=1.02):
    """A point of the face plane (x, z in units of r) projected onto the pumpkin's smooth front (the -Y side)."""
    zz = z / SQ
    d = max(1.0 - x * x - zz * zz, 0.02)
    return Vector((x * r, -math.sqrt(d) * r * lift, z * r))


FACE_N = [  # (outline in units of r), facing the camera: x right, z up
    [(-0.56, 0.36), (-0.12, 0.14), (-0.36, 0.06)],                                  # left eye (slanted, evil)
    [(0.56, 0.36), (0.36, 0.06), (0.12, 0.14)],                                     # right eye
    [(-0.08, -0.04), (0.08, -0.04), (0.0, 0.1)],                                    # nose
]


def mouth(w, depth, teeth):
    """A jagged grin: a crescent whose top edge carries square teeth."""
    bot = [(x, -0.14 - depth * (1.0 - (x / w) ** 2)) for x in [w * (-1 + 2 * i / 16) for i in range(17)]]
    top = []
    xs = [w * (1 - 2 * i / 16) for i in range(17)]
    for x in xs:
        zt = -0.14 - 0.42 * depth * (1.0 - (x / w) ** 2)
        tooth = any(abs(x - t) < w * 0.07 for t in teeth)
        top.append((x, zt - (0.12 if tooth else 0.0)))
    pts = bot + top[1:-1]
    return pts


def face_bm(r, king=False):
    """The carved face as glowing patches on the pumpkin's front (UV.x = 0 at a hole's rim .. 1 at its middle, for
    the inner-wall gradient)."""
    shapes = [list(p) for p in FACE_N]
    if king:
        shapes[0] = [(-0.6, 0.42), (-0.1, 0.16), (-0.42, 0.04)]
        shapes[1] = [(0.6, 0.42), (0.42, 0.04), (0.1, 0.16)]
        shapes.append(mouth(0.7, 0.42, (-0.42, -0.14, 0.14, 0.42)))
    else:
        shapes.append(mouth(0.6, 0.36, (-0.22, 0.22)))
    bm = bmesh.new()
    uvl = bm.loops.layers.uv.new("UVMap")
    for shp in shapes:
        cx = sum(p[0] for p in shp) / len(shp)
        cz = sum(p[1] for p in shp) / len(shp)
        n = len(shp)
        rim, mid = [], []
        for x, z in shp:                                              # two rings: the rim and an inset ring
            rim.append(bm.verts.new(front_point(x, z, r)))
            mid.append(bm.verts.new(front_point(cx + (x - cx) * 0.45, cz + (z - cz) * 0.45, r)))
        c = bm.verts.new(front_point(cx, cz, r))
        for i in range(n):
            j = (i + 1) % n
            f1 = bm.faces.new((rim[i], rim[j], mid[j], mid[i]))
            for loop, u in zip(f1.loops, (0.0, 0.0, 0.7, 0.7)):
                loop[uvl].uv = (u, 0.0)
            f2 = bm.faces.new((mid[i], mid[j], c))
            for loop, u in zip(f2.loops, (0.7, 0.7, 1.0)):
                loop[uvl].uv = (u, 0.0)
    return bm


def crack_bm(r, seed, big):
    """Cracks racing out from the impact over the front of the shell: random walks in the face plane projected onto
    the sphere; UV.x = distance along a crack (units of r) for the reveal front."""
    rnd = random.Random(seed)
    bm = bmesh.new()
    uvl = bm.loops.layers.uv.new("UVMap")
    ribbons = []

    def walk(p, d, length, u0, w0, depth):
        pts, us = [p], [u0]
        u = u0
        head = d
        while u - u0 < length:
            a = rnd.gauss(0.0, 0.35)
            c, s_ = math.cos(a), math.sin(a)
            d = (d[0] * c - d[1] * s_, d[0] * s_ + d[1] * c)
            d = (d[0] + head[0] * 0.4, d[1] + head[1] * 0.4)
            ln = math.hypot(*d)
            d = (d[0] / ln, d[1] / ln)
            stp = rnd.uniform(0.03, 0.06)
            p = (p[0] + d[0] * stp, p[1] + d[1] * stp)
            if p[0] ** 2 + (p[1] / SQ) ** 2 > 0.9:
                break
            u += stp
            pts.append(p)
            us.append(u)
            if depth < 2 and rnd.random() < 0.07:
                b = rnd.choice((-1, 1)) * rnd.uniform(0.5, 1.0)
                walk(p, (d[0] * math.cos(b) - d[1] * math.sin(b), d[0] * math.sin(b) + d[1] * math.cos(b)),
                     (length - (u - u0)) * 0.5, u, w0 * 0.7, depth + 1)
        ribbons.append((pts, us, w0))

    n_main = 9 if big else 6
    start = (rnd.uniform(-0.15, 0.15), rnd.uniform(0.15, 0.35))       # the impact point, above the nose
    for i in range(n_main):
        a = 2 * math.pi * (i + rnd.uniform(0.2, 0.8)) / n_main
        walk(start, (math.cos(a), math.sin(a)), rnd.uniform(0.6, 1.1), 0.0, 0.016, 0)
    for pts, us, w0 in ribbons:
        n = len(pts)
        if n < 2:
            continue
        left, right = [], []
        for i, (x, z) in enumerate(pts):
            x2, z2 = pts[min(i + 1, n - 1)]
            x1, z1 = pts[max(i - 1, 0)]
            tx, tz = x2 - x1, z2 - z1
            ln = math.hypot(tx, tz) or 1.0
            nx, nz = -tz / ln, tx / ln
            w = w0 * (1.0 - 0.7 * i / max(n - 1, 1))
            left.append(bm.verts.new(front_point(x + nx * w, z + nz * w, r, 1.035)))
            right.append(bm.verts.new(front_point(x - nx * w, z - nz * w, r, 1.035)))
        for i in range(n - 1):
            f = bm.faces.new((left[i], right[i], right[i + 1], left[i + 1]))
            for loop, (uu, vv) in zip(f.loops, ((us[i], 0.0), (us[i], 1.0), (us[i + 1], 1.0), (us[i + 1], 0.0))):
                loop[uvl].uv = (uu, vv)
    return bm


def crown_bm(r):
    """The King's crown: a ring of jagged spikes around the stem."""
    bm = bmesh.new()
    n = 9
    ring = []
    for i in range(2 * n):
        a = 2 * math.pi * i / (2 * n)
        rr = 0.42 * r
        h = (0.42 if i % 2 == 0 else 0.1) * r
        ring.append(Vector((rr * math.cos(a), rr * math.sin(a), SQ * r * 0.86 + h)))
    g.stroke(bm, ring, 0.035 * r, segs=6, closed=True)
    g.stroke(bm, [Vector((0.42 * r * math.cos(a), 0.42 * r * math.sin(a), SQ * r * 0.86)) for a in
                  [2 * math.pi * i / 36 for i in range(36)]], 0.04 * r, segs=6, closed=True, joints=False)
    for i in range(0, 2 * n, 2):
        bmesh.ops.create_icosphere(bm, subdivisions=1, radius=0.05 * r, matrix=Matrix.Translation(ring[i]))
    return bm


# ------------------------------------------------------------------ materials
def decode_age(s):
    col, alpha, rnd = s.obj_info()
    r, gg, b = s.xyz(col)
    return s.sub(r, AGE0), alpha, rnd


def shell_mat():
    """Dark pumpkin skin with a warm rim; a little light leaks round the face. Alpha = visibility (fades out)."""
    s = vj.Shader("Shell")
    age, alpha, _ = decode_age(s)
    flare = s.mul(s.math("GREATER_THAN", age, -0.02), s.exp(s.mul(s.math("MAXIMUM", age, 0.0), -5.0)))
    lift = s.add(1.0, s.mul(flare, 0.2), s.mul(s.c("Swell"), 0.2))
    rim = s.rim((0.45, 0.95))
    return s.emit_masked(s.math("GREATER_THAN", alpha, 0.01), V["shell"],
                         s.mul(s.add(0.045, s.mul(rim, 0.75)), lift, alpha, GAIN))


def face_mat():
    """The candle-lit holes: brightest deep inside, darker on the inner walls; a slow flicker; a soft flare at the slam;
    orange in section A, green in B (held lower: green is high luma)."""
    s = vj.Shader("Face")
    age, alpha, rnd = decode_age(s)
    u, _, _ = s.uv()
    depth = s.madd(s.smooth(u, 0.0, 1.0), 0.65, 0.35)
    n = s.noise4(s.vec(s.mul(rnd, 31.0), s.c("LoopCos"), s.c("LoopSin")), s.mul(rnd, 7.0), scale=2.5, detail=1.0)
    flick = s.madd(n, 0.3, 0.85)
    flare = s.mul(s.math("GREATER_THAN", age, -0.02), s.exp(s.mul(s.math("MAXIMUM", age, 0.0), -3.5)))
    col = s.mix(s.c("Section"), V["face"][0], V["face"][1])
    green_dim = s.madd(s.c("Section"), -0.3, 1.0)
    lift = s.add(0.8, s.mul(flare, 0.25), s.mul(s.c("Swell"), 0.05))        # lead, 2026-10-09: the gate (blocks
    return s.emit_masked(s.math("GREATER_THAN", alpha, 0.01), col,          # 0.78 > 0.65, accents x2.4 > 1.6)
                         s.mul(depth, flick, lift, green_dim, alpha, 0.6 * GAIN))   # the King's grin filled 0.78


def crack_mat():
    """Cracks revealed from the impact (a front racing out over ~5 frames), hot then cooling, fading with the
    pumpkin."""
    s = vj.Shader("Cracks")
    age, alpha, _ = decode_age(s)
    u, v, _ = s.uv()
    a = s.math("MAXIMUM", age, 0.0)
    front = s.mul(s.inv(s.exp(s.mul(a, -1.0 / 0.17))), 1.25)            # ~0.2 accents to run out
    reveal = s.mul(s.inv(s.smooth(s.sub(u, front), -0.03, 0.03)), s.math("GREATER_THAN", age, 0.0))
    heat = s.add(0.45, s.mul(s.exp(s.mul(a, -2.0)), 0.8))
    across = s.inv(s.math("ABSOLUTE", s.madd(v, 2.0, -1.0)))
    col = s.mix(s.c("Section"), V["crack"][0], V["crack"][1])
    green_dim = s.madd(s.inv(s.c("Section")), -0.25, 1.0)
    return s.emit_masked(s.mul(reveal, s.math("GREATER_THAN", alpha, 0.01)), col,
                         s.mul(reveal, heat, across, alpha, green_dim, 2.2 * GAIN))


def crown_mat():
    s = vj.Shader("Crown")
    age, alpha, _ = decode_age(s)
    return s.emit_masked(s.math("GREATER_THAN", alpha, 0.01), V["crown"],
                         s.mul(s.core(0.5, 1.4), alpha, s.add(1.0, s.mul(s.c("Kick"), 0.2)), 0.55 * GAIN))   # was 1.3: clipped to white at the King's impact (block 0.78)


def patch_mat():
    """Small distant jack-o'-lanterns: dim flickering faces (one emissive blob each)."""
    s = vj.Shader("Patch")
    _, _, rnd = s.obj_info()
    x, y, z = s.world_pos()
    n = s.noise4(s.vec(s.mul(x, 0.3), s.mul(y, 0.3), s.c("LoopCos")), s.c("LoopSin"), scale=2.0, detail=1.0)
    return s.emit((1.0, 0.33, 0.04), s.mul(s.madd(n, 0.5, 0.6), s.falloff(s.dist, 50.0), 0.7 * GAIN))


def ground_mat():
    s = vj.Shader("Ground")
    x, y, _ = s.world_pos()
    n = s.noise4(s.vec(s.mul(x, 0.05), s.mul(y, 0.05), s.c("LoopCos")), s.c("LoopSin"), scale=1.5, detail=3.0)
    mist = s.smooth(n, 0.45, 0.75)
    far = s.smooth(y, 10.0, 60.0)
    return s.emit(UVP, s.mul(mist, far, s.falloff(s.dist, 70.0), 0.05 * GAIN))


def sky_mat():
    s = vj.Shader("Sky")
    _, _, z = s.world_pos()
    band = s.exp(s.mul(s.math("MAXIMUM", z, 0.0), -1.0 / 9.0))
    return s.emit(UVP, s.mul(band, s.add(1.0, s.mul(s.c("Swell"), 0.25)), 0.09 * GAIN))


# ------------------------------------------------------------------ choreography
class Slam:
    def __init__(self, j, rnd):
        self.j = j
        self.king = j % 4 == 0
        self.f0 = vj.BEAT_F[j * vj.ACC] + 1                           # the slam frame: a frame after the beat
        self.r = R_K if self.king else R_N
        side = -1.0 if (j // 1) % 2 == 0 else 1.0
        self.side = side
        self.far = Vector((rnd.uniform(-5, 5), 75.0, rnd.uniform(0.5, 6.0)))
        self.rest = Vector((side * rnd.uniform(5.5, 8.5), rnd.uniform(26.0, 34.0), self.r * SQ - 0.3))
        self.spin = rnd.choice((-1, 1)) * rnd.uniform(1.2, 1.7)       # turns during the approach
        self.tilt = rnd.uniform(-25, 25)

    def state(self, f):
        """(location, rotation euler, scale vec, age in accents, alpha) at frame f (cyclic)."""
        t = (f - self.f0) % vj.FRAMES
        if t > vj.FRAMES - ACC_F:                                      # approaching (the accent before the slam)
            t -= vj.FRAMES
        a = t / ACC_F                                                  # accents since the slam
        slam = SLAM + Vector((0.0, 0.0, (self.r - R_N) * 0.35))
        if a < -1.0 or a > LIFE_AFTER:
            return self.far, Euler((0, 0, 0)), Vector((0.01, 0.01, 0.01)), a, 0.0
        if a <= 0.0:                                                   # rushing in, accelerating, spinning
            u = a + 1.0
            e = u ** 2.4
            p = self.far.lerp(slam, e)
            rot = Euler((math.radians(self.tilt * (1 - e)), 0.0, 2 * math.pi * self.spin * (1 - e)))
            return p, rot, Vector((1, 1, 1)), a, min(u * 2.5, 1.0)
        if t <= 6:                                                     # the slam: squash and settle
            sq = math.exp(-t / 2.2) * math.sin(math.pi * min(t / 2.0, 1.0))
            p = slam + Vector((0.0, 0.25 * math.sin(math.pi * t / 6.0), 0.0))
            return p, Euler((0, 0, 0)), Vector((1 + 0.08 * sq, 1 - 0.04 * sq, 1 - 0.09 * sq)), a, 1.0
        hold = HOLD * ACC_F
        if t <= hold:                                                  # it stays (the frame never empties mid-beat)
            w = (t - 6) / (hold - 6)
            p = slam + Vector((0.0, 0.6 * w, 0.0))                           # continues from the squash's end
            return p, Euler((math.radians(-2.0 * w), 0.0, math.radians(self.side * 3.0 * w))), Vector((1, 1, 1)), a, 1.0
        u = (t - hold) / (LIFE_AFTER * ACC_F - hold)                   # knocked aside as the next one arrives
        e = 1.0 - (1.0 - u) ** 2.2
        slam = slam + Vector((0.0, 0.6, 0.0))
        p = slam.lerp(self.rest, e) + Vector((0.0, 0.0, 0.8 * math.sin(math.pi * min(u * 2.0, 1.0))))
        rot = Euler((math.radians(-2.0 - 33.0 * e), 0.0, math.radians(self.side * (3.0 + 47.0 * e))))   # from the hold's tilt
        fade = 1.0 if u < 0.75 else max(0.0, (1.0 - u) / 0.25)
        return p, rot, Vector((1, 1, 1)), a, (1.0 - 0.55 * e) * fade


def jolt_cam(f, slams):
    """Camera (pitch, roll, drop): a damped thump a frame after each slam, heavier for the King."""
    pitch = roll = drop = 0.0
    for sl in slams:
        t = (f - sl.f0 - 1) % vj.FRAMES
        if t < 22:
            e = math.exp(-t / 3.4) * math.sin(2 * math.pi * t / 5.0)
            k = 1.0 if sl.king else 0.6
            pitch += 0.9 * k * e
            roll += 0.5 * k * e * sl.side
            drop += 0.05 * k * math.exp(-t / 3.4) * math.sin(math.pi * min(t / 2.0, 1.0))
    return pitch, roll, drop


# ------------------------------------------------------------------ scene
def build():
    scene = vj.reset_scene()
    vj.clock_from(signals)
    ext = vj.EXT
    rnd = random.Random(99)

    mats = dict(shell=shell_mat(), face=face_mat(), crack=crack_mat(), crown=crown_mat())
    slams = [Slam(j, rnd) for j in range(N_SLAMS)]
    for sl in slams:
        root = vj.new_empty(f"Pumpkin{sl.j}")
        parts = [vj.new_obj(f"P{sl.j}Shell", shell_bm(sl.r, sl.j, sl.king), mats["shell"], root),
                 vj.new_obj(f"P{sl.j}Face", face_bm(sl.r, sl.king), mats["face"], root),
                 vj.new_obj(f"P{sl.j}Cracks", crack_bm(sl.r, 300 + sl.j, sl.king), mats["crack"], root)]
        if sl.king:
            parts.append(vj.new_obj(f"P{sl.j}Crown", crown_bm(sl.r), mats["crown"], root))
        sts = [(f, sl.state(f)) for f in ext]
        vj.keyed(root, "location", [(f, tuple(st[0])) for f, st in sts])
        vj.keyed(root, "rotation_euler", [(f, tuple(st[1])) for f, st in sts])
        vj.keyed(root, "scale", [(f, tuple(st[2])) for f, st in sts])
        for ob in parts:
            vj.keyed(ob, "color", [(f, (st[3] + AGE0, 0.0, 0.0, st[4])) for f, st in sts])

    pm = patch_mat()
    pb = bmesh.new()
    for _ in range(80):                                                # the patch: small distant lanterns
        x, y = rnd.uniform(-45, 45), rnd.uniform(16, 90)
        bmesh.ops.create_icosphere(pb, subdivisions=1, radius=rnd.uniform(0.12, 0.22),
                                   matrix=Matrix.Translation((x, y, 0.35)))
    vj.new_obj("Patch", pb, pm)
    ground = vj.new_obj("Ground", vj.quad_bm(300.0, 300.0, axis="Z"), ground_mat())
    ground.location = (0.0, 100.0, 0.0)
    sky = vj.new_obj("Sky", vj.quad_bm(600.0, 200.0), sky_mat())
    sky.location = (0.0, 200.0, 60.0)
    sb = bmesh.new()
    for _ in range(150):
        bmesh.ops.create_icosphere(sb, subdivisions=1, radius=rnd.uniform(0.25, 0.5),
                                   matrix=Matrix.Translation((rnd.uniform(-250, 250), 190.0, rnd.uniform(25, 140))))
    st = vj.Shader("Stars")
    vj.new_obj("Stars", sb, st.emit((0.8, 0.8, 1.0), 0.7 * GAIN))

    cam = vj.camera(scene, lens=35.0, clip=(0.2, 600.0))
    loc, rot = [], []
    for f in ext:
        p, r_, d = jolt_cam(f, slams)
        a = 2 * math.pi * f / vj.FRAMES
        pos = CAM + Vector((0.25 * math.sin(a), 0.0, 0.1 * math.sin(2 * a) - d))
        e = vj.look_at(pos, SLAM + Vector((0.0, 0.0, 0.25)), roll=r_)
        e.x += math.radians(p)
        loc.append((f, tuple(pos)))
        rot.append((f, tuple(e)))
    vj.keyed(cam, "location", loc)
    vj.keyed(cam, "rotation_euler", rot)
    return scene


scene = build()
vj.standard_render(scene)
vj.finish(scene, f"pumpkin_stomp_{VNAME}")
