"""BAT SWARM - GRAVEYARD SHIFT VJ loop (build). 8 bars, seamless, 1920x1080 @ 30 fps; tempo from vjkit
(140 BPM half-time = 411 frames).

A cave mouth in a black cliff: a jagged opening with stalactite teeth, and behind it a glowing throat of rock rings
receding into fire. Bats pour out of the throat toward the camera: neon-rimmed silhouettes, wings beating on the 8th
notes, fanning out and rushing past the lens. The swarm thickens through the loop and its densest wave washes over the
camera on the downbeat (the build lands on the phrase); bar 1 thins out and the build starts again.
  Bars 1-4: the throat burns ember orange.  Bars 5-8: it turns toxic green (the morph lands on bar 5's downbeat) and
  turns back to orange into the next downbeat. The last two beats of bars 4 and 8 swell into the hit.
Beat hooks: flaps on the 8ths (motion), the throat breathes softly on the kick and the snare, camera thumps on the
accents grow with the build. Embers drift out of the cave.
No strobing: the bats are dark with thin rims (faded out near the lens), the throat glow stays under the block cap.

  blender.exe -b --factory-startup --python bat_swarm.py -- --frames 0,100,300 [--pct 50] [--samples 16]
  blender.exe -b --factory-startup --python bat_swarm.py -- --all --seam DIR [--out DIR] [--mblur]
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
from vjkit import EMBER, PUMPKIN, TOXIC, UVP  # noqa: E402

VARIANTS = {
    "ember": dict(throat=(EMBER, (0.1, 0.62, 0.02)), core=(PUMPKIN, (0.32, 1.0, 0.06)), rim=UVP, n_bats=300),
}
VNAME, V = vj.variant(VARIANTS)
GAIN = float(vj.arg("--gain", 1.0))

CAM = Vector((0.0, -2.0, 0.3))
AIM = Vector((0.5, 40.0, 0.9))
# throat layers: depth y, hole radii (x, z), hole center (x, z), edge glow
LAYERS = [(40.0, 10.5, 7.5, 0.0, 0.0, 0.35), (46.0, 8.6, 6.2, 1.4, 0.8, 0.42), (53.0, 7.2, 5.2, 3.0, 1.8, 0.5),
          (61.0, 6.0, 4.4, 4.6, 2.8, 0.6), (70.0, 5.0, 3.7, 6.0, 3.6, 0.7), (80.0, 4.2, 3.1, 7.0, 4.2, 0.8)]
CORE_Y = 95.0
CORE_XZ = (7.6, 4.6)
DEEP = Vector((6.0, 72.0, 3.6))                 # bats appear inside the 5th ring and fly out through the mouth


# ------------------------------------------------------------------ music
def build_level(f):
    """The build: rises from bar 2 to the downbeat (0.0 -> 1.0, eased), falls back over bar 1."""
    b = vj.beatpos(f % vj.FRAMES)
    if b < 4:
        return 1.0 - vj.ease(b / 4.0)
    return ((b - 4) / (vj.BEATS - 4)) ** 1.3


def signals(f):
    c = vj.clock(f)
    s = {"Kick": c["kick"], "Swell": vj.swell(f), "Section": vj.section(f), "Build": build_level(f)}
    s.update(vj.loop_signals(f))
    return s


# ------------------------------------------------------------------ geometry
def hole_fn(seed):
    """Radius factor around a hole: rough rock, many octaves (amplitude ~1/j), irregular rather than flower-like."""
    rnd = random.Random(seed)
    terms = [(j, rnd.uniform(0.3, 1.0) * 0.16 / j ** 0.85, rnd.uniform(0, 2 * math.pi)) for j in range(2, 29)]
    return lambda th: 1.0 + sum(a * math.sin(j * th + p) for j, a, p in terms)


def hole_pt(rx, rz, cx, cz, r, th):
    """A point on a hole's edge: the bottom half is flatter (a cave floor)."""
    sn = math.sin(th)
    return Vector((cx + rx * r(th) * math.cos(th), 0.0, cz + rz * r(th) * (sn if sn > 0 else 0.7 * sn)))


def card_bm(rx, rz, cx, cz, seed, n=180, outer=90.0):
    """A black card with a jagged elliptical hole; UV.x = meters from the hole's edge (for the edge glow)."""
    r = hole_fn(seed)
    bm = bmesh.new()
    uvl = bm.loops.layers.uv.new("UVMap")
    rings, us = [], [0.0, 0.5, 1.6, 4.5, outer]
    for k, du in enumerate(us):
        ring = []
        for i in range(n):
            th = 2 * math.pi * i / n
            e = hole_pt(rx, rz, cx, cz, r, th)
            d = Vector((math.cos(th) * rz, 0.0, math.sin(th) * rx)).normalized()   # roughly outward
            ring.append(bm.verts.new(e + d * du))
        rings.append(ring)
    for k in range(len(us) - 1):
        for i in range(n):
            a, b = rings[k][i], rings[k][(i + 1) % n]
            c, d = rings[k + 1][(i + 1) % n], rings[k + 1][i]
            f = bm.faces.new((a, d, c, b))
            for loop, u in zip(f.loops, (us[k], us[k + 1], us[k + 1], us[k])):
                loop[uvl].uv = (u, 0.0)
    return bm, r


def teeth_bm(rx, rz, cx, cz, r, seed):
    """Stalactites hanging from the top of the mouth and stalagmites from its floor (cones in the card plane)."""
    rnd = random.Random(seed)
    bm = bmesh.new()
    for top, angles in ((True, (48, 58, 67, 76, 86, 95, 104, 113, 123, 133)), (False, (238, 251, 266, 282, 297))):
        for a in angles:
            th = math.radians(a + rnd.uniform(-3, 3))
            e = hole_pt(rx, rz, cx, cz, r, th) + Vector((0.0, -0.4, 0.0))
            ln = rnd.uniform(1.8, 4.2) if top else rnd.uniform(1.0, 2.4)
            base = e + Vector((0.0, 0.0, 0.6 if top else -0.6))
            tip = base + Vector((rnd.uniform(-0.3, 0.3), rnd.uniform(-0.2, 0.2), -ln if top else ln))
            pts = [base.lerp(tip, t) for t in (0.0, 0.35, 0.7, 1.0)]
            r0 = rnd.uniform(0.5, 0.95)
            vj.tube(bm, pts, lambda u, r0=r0: r0 * (1.0 - u) ** 1.2 + 0.02, segs=10, tip=True)
    for a in (55, 71, 82, 99, 111, 127):                               # hanging roots, swaying in the draught
        th = math.radians(a + rnd.uniform(-4, 4))
        e = hole_pt(rx, rz, cx, cz, r, th) + Vector((0.0, -0.8, 0.5))
        ln = rnd.uniform(3.0, 6.0)
        ph = rnd.uniform(0, 6.28)
        pts = [e + Vector((0.35 * math.sin(3.0 * t + ph) * t, -0.3 * t, -ln * t)) for t in [i / 14 for i in range(15)]]
        r0 = rnd.uniform(0.07, 0.13)
        vj.tube(bm, pts, lambda u, r0=r0: r0 * (1.0 - 0.8 * u), segs=6, tip=True)
    return bm


# ------------------------------------------------------------------ materials
def throat_color(s, depth_t):
    """Ember (outer) -> pumpkin (deep) in section A, dark green -> toxic in section B."""
    a = s.mix(depth_t, V["throat"][0], V["core"][0])
    b = s.mix(depth_t, V["throat"][1], V["core"][1])
    return s.mix(s.c("Section"), a, b)


def card_mat(k):
    s = vj.Shader(f"Card{k}")
    u, _, _ = s.uv()
    depth_t = k / (len(LAYERS) - 1)
    x, _, z = s.world_pos()
    rock = s.noise4(s.vec(s.mul(x, 0.55), s.mul(z, 0.55), float(k)), 0.0, scale=1.4, detail=6.0, rough=0.7)
    rock = s.smooth(rock, 0.38, 0.72)
    edge = s.add(s.mul(s.exp(s.mul(u, -1.0 / 0.22)), s.madd(rock, 0.6, 0.4)),
                 s.mul(s.exp(s.mul(u, -1.0 / 1.8)), rock, 0.45))
    lift = s.add(0.75, s.mul(s.c("Build"), 0.25), s.mul(s.c("Kick"), 0.15), s.mul(s.c("Swell"), 0.35))
    green_dim = s.madd(s.c("Section"), -0.35, 1.0)                     # green is high luma: hold it lower
    terms = [(throat_color(s, depth_t), s.mul(edge, lift, green_dim, LAYERS[k][5] * 1.7 * GAIN))]
    if k == 0:                                                         # the cliff: faint moonlit rock
        x, _, z = s.world_pos()
        n = s.noise4(s.vec(s.mul(x, 0.18), s.mul(z, 0.18), s.c("LoopCos")), s.c("LoopSin"), scale=1.5, detail=6.0,
                     rough=0.65)
        ridge = s.smooth(n, 0.52, 0.7)
        spill = s.exp(s.mul(u, -1.0 / 6.0))
        terms.append((UVP, s.mul(ridge, s.add(0.012, s.mul(spill, 0.03)), GAIN)))
        terms.append((throat_color(s, 0.0), s.mul(spill, ridge, lift, green_dim, 0.06 * GAIN)))
    return s.emit_sum(terms)


def haze_mat(k):
    s = vj.Shader(f"Haze{k}")
    depth_t = k / (len(LAYERS) - 1)
    lift = s.add(0.7, s.mul(s.c("Build"), 0.3), s.mul(s.c("Kick"), 0.18), s.mul(s.c("Swell"), 0.4))
    green_dim = s.madd(s.c("Section"), -0.4, 1.0)
    x, _, z = s.obj_coords()
    n = s.noise4(s.vec(s.mul(x, 0.35), s.mul(z, 0.35), s.mul(s.c("LoopCos"), 0.8)), s.mul(s.c("LoopSin"), 0.8),
                 scale=1.2, detail=3.0)
    wisp = s.madd(s.smooth(n, 0.35, 0.75), 0.6, 0.4)
    return s.additive(throat_color(s, depth_t), s.mul(lift, green_dim, wisp, (0.05 + 0.03 * k) * GAIN))


def core_mat():
    s = vj.Shader("Core")
    x, _, z = s.obj_coords()
    r = s.length2(x, z)
    heat = s.exp(s.mul(s.mul(r, r), -1.0 / (3.2 * 3.2)))
    lift = s.add(0.7, s.mul(s.c("Build"), 0.3), s.mul(s.c("Kick"), 0.2), s.mul(s.c("Swell"), 0.35))
    green_dim = s.madd(s.c("Section"), -0.45, 1.0)
    col = s.mix(s.smooth(heat, 0.2, 0.9), throat_color(s, 0.6), throat_color(s, 1.0))
    return s.emit(col, s.mul(s.add(0.05, s.mul(heat, 0.48)), lift, green_dim, GAIN))


def teeth_mat():
    s = vj.Shader("Teeth")
    lift = s.add(0.8, s.mul(s.c("Kick"), 0.15), s.mul(s.c("Swell"), 0.3))
    return s.emit(throat_color(s, 0.3), s.mul(s.rim((0.45, 0.95)), lift, s.madd(s.c("Section"), -0.35, 1.0),
                                              1.6 * GAIN))


def ember_mat():
    s = vj.Shader("Embers")
    col, alpha, _ = s.obj_info()
    return s.additive(throat_color(s, 0.8), s.mul(alpha, s.core(0.6, 1.4), 2.2 * GAIN))


# ------------------------------------------------------------------ the swarm
def arrival_times(n, rnd):
    """Arrival frames at the camera with density rising through the loop and peaking on the downbeat."""
    grid = [0.25 + 1.6 * build_level(f) ** 1.6 for f in range(vj.FRAMES)]
    cdf, acc = [], 0.0
    for w in grid:
        acc += w
        cdf.append(acc)
    out = []
    for i in range(n):
        x = (i + rnd.random()) / n * acc
        lo = 0
        while cdf[lo] < x:
            lo += 1
        out.append(lo + rnd.random())
    return out


class Bat:
    def __init__(self, i, arrive, rnd):
        self.T = rnd.uniform(70.0, 115.0)                              # frames from inside the throat past the lens
        self.s = (arrive - self.T) % vj.FRAMES
        self.p0 = DEEP + Vector((rnd.uniform(-2.2, 2.2), rnd.uniform(-2, 2), rnd.uniform(-1.4, 1.4)))
        ang = rnd.uniform(0, 2 * math.pi)
        mx, mz = rnd.uniform(-0.75, 0.75), rnd.uniform(-0.7, 0.7)
        self.p1 = Vector((LAYERS[0][1] * mx, 40.0, LAYERS[0][4] + LAYERS[0][2] * mz * (1.0 if mz > 0 else 0.7)))
        rho = rnd.uniform(2.6, 9.0)
        self.p2 = Vector((CAM.x + 1.45 * rho * math.cos(ang), CAM.y - 6.0, CAM.z + 0.85 * rho * math.sin(ang)))
        self.ctrl = 2 * self.p1 - 0.5 * (self.p0 + self.p2)
        self.size = rnd.uniform(0.85, 1.35)
        self.phase = rnd.uniform(-0.12, 0.12)
        self.weave = (rnd.uniform(0, 2 * math.pi), rnd.uniform(22.0, 34.0), rnd.uniform(0.3, 0.7))

    def pos(self, u):
        return (1 - u) ** 2 * self.p0 + 2 * (1 - u) * u * self.ctrl + u * u * self.p2

    def state(self, f):
        """(location, rotation, scale, flap) at frame f; hidden (scale 0) outside its flight."""
        age = (f - self.s) % vj.FRAMES
        fl = bats.flap_angle(f, self.phase)
        if age >= self.T:                                              # waiting: parked behind the camera, or at the
            park = self.p2 if age < self.T + 40 else self.p0          # deep start just before its spawn
            return park, bats.heading(self.p2 - self.p0), 0.0001, fl
        u = age / self.T
        ph, per, amp = self.weave
        side = Vector((math.cos(ph), 0.0, math.sin(ph)))
        wob = side * amp * math.sin(2 * math.pi * age / per + ph)
        bob = Vector((0.0, 0.0, 0.1 * math.sin(2 * math.pi * (2 * vj.beatpos(f) + self.phase))))   # lift per stroke
        loc = self.pos(u) + wob * min(u * 3.0, 1.0) + bob
        vel = self.pos(min(u + 0.01, 1.0)) - self.pos(max(u - 0.01, 0.0))
        bank = 18.0 * math.cos(2 * math.pi * age / per + ph)
        grow = min(age / 4.0, 1.0)                                     # appears over 4 frames, deep in the throat
        return loc, bats.heading(vel, bank=bank), self.size * grow, fl


# ------------------------------------------------------------------ scene
def build():
    scene = vj.reset_scene()
    vj.clock_from(signals)
    ext = vj.EXT

    for k, (y, rx, rz, cx, cz, _) in enumerate(LAYERS):
        bm, rfn = card_bm(rx, rz, cx, cz, 40 + k)
        card = vj.new_obj(f"Card{k}", bm, card_mat(k))
        card.location = (0.0, y, 0.0)
        hz = vj.new_obj(f"Haze{k}", vj.disc_bm(1.0, 64), haze_mat(k))
        hz.location = (cx, y + 0.6, cz)
        hz.scale = (rx * 1.15, 1.0, rz * 1.15)
        if k == 0:
            vj.new_obj("Teeth", teeth_bm(rx, rz, cx, cz, rfn, 9), teeth_mat()).location = (0.0, y, 0.0)
    core = vj.new_obj("Core", vj.disc_bm(9.0, 96), core_mat())
    core.location = (CORE_XZ[0], CORE_Y, CORE_XZ[1])

    rnd = random.Random(31)
    rim = bats.rim_mat("BatRim", gain=1.5, near=(2.0, 6.5), far=(70.0, 110.0), kick=0.15)
    meshes = bats.bat_meshes(rim, vj.black_mat("BatBlack"))
    swarm = [Bat(i, t, rnd) for i, t in enumerate(arrival_times(V["n_bats"], rnd))]
    for i, b in enumerate(swarm):
        body, wl, wr = bats.make_bat(f"Bat{i:03d}", meshes, color=V["rim"])
        bats.key_bat(body, wl, wr, [(f, *b.state(f)) for f in ext])

    em = ember_mat()
    for i in range(70):                                               # embers drifting out of the cave
        s0, life = rnd.uniform(0, vj.FRAMES), rnd.uniform(160, 300)
        p0 = DEEP + Vector((rnd.uniform(-3, 3), rnd.uniform(-30, 0), rnd.uniform(-2, 2)))
        p1 = Vector((rnd.uniform(-14, 14), rnd.uniform(4, 16), rnd.uniform(-6, 9)))
        bm = bmesh.new()
        bmesh.ops.create_icosphere(bm, subdivisions=1, radius=rnd.uniform(0.05, 0.1))
        ob = vj.new_obj(f"Ember{i}", bm, em)
        wob = rnd.uniform(0, 6.28)
        locs, cols = [], []
        for f in ext:
            age = (f - s0) % vj.FRAMES
            if age < life:
                u = age / life
                p = p0.lerp(p1, u) + Vector((0.6 * math.sin(age / 17.0 + wob), 0.0, 0.5 * math.sin(age / 23.0 + wob)))
                a = math.sin(math.pi * u) ** 1.5
            else:
                p, a = (p1 if age < life + 30 else p0), 0.0
            locs.append((f, tuple(p)))
            cols.append((f, (1.0, 1.0, 1.0, a)))
        vj.keyed(ob, "location", locs)
        vj.keyed(ob, "color", cols)

    cam = vj.camera(scene, lens=30.0, clip=(0.3, 400.0))
    loc, rot = [], []
    for f in ext:
        a = 2 * math.pi * f / vj.FRAMES
        p = CAM + Vector((0.5 * math.sin(a), 0.0, 0.25 * math.sin(2 * a + 0.4)))
        j = vj.jolt(f, decay=3.0, period=5.0) * (0.25 + 0.75 * build_level(f))
        rot.append((f, tuple(vj.look_at(p, AIM + Vector((0.0, 0.0, 0.55 * j))))))
        loc.append((f, tuple(p + Vector((0.0, 0.0, -0.05 * j)))))
    vj.keyed(cam, "location", loc)
    vj.keyed(cam, "rotation_euler", rot)
    return scene


scene = build()
vj.standard_render(scene)
vj.finish(scene, f"bat_swarm_{VNAME}")
