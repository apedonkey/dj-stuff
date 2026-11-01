"""STOMP - Dino Stage VJ loop (heavy / half-time drop). 8 bars, seamless, 1920x1080 @ 30 fps; tempo from vjkit
(140 BPM half-time = 411 frames by default).

Something huge is walking toward us. Its three-toed feet slam down in front of the camera, which backs away at the
beast's pace, so every print lands big in the foreground and then recedes into the dark as a cooling trail. On each
stomp a neon ghost of the foot drops in from above (the swell into the hit), the print ignites, cracks race out through
the ground, a dust ring rolls outward and the camera shakes. Half-time: a stomp on every accent, the kick (beat 1) and
the snare (beat 3); straight (the 128 grid): every beat. The bar's downbeat is the bigger stomp: a wider print, the
heaviest shake, and cracks that race to the edges of the frame.
  Bars 1-4: a dim laser grid. Bars 5-8: the grid lights up in the second color. The last two beats of bars 4 and 8
  swell into the next downbeat.
Variants (--variant): lava (default), toxic (UV/magenta prints on a cyan grid), gold (gold prints, longer strides, a
low camera close to the ground).
No strobing: <= 3 flashes/s, no one-frame hits, no ~1 m2 patch over 0.65 luma, kick pulse <= ~1.6x.
Each stomp is a few static objects (outline, fill, cracks, dust disc, ghost foot) whose shaders read the stomp's age
from the object color, keyed linearly in time; geometry and look are our own.

  blender.exe -b --factory-startup --python stomp.py -- --variant lava --frames 0,7,56 [--pct 25 --samples 4]
  blender.exe -b --factory-startup --python stomp.py -- --variant lava --all --seam DIR [--out DIR] [--mblur]
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
from vjkit import AMBER, CYAN, GREEN, MAGENTA, RED, UV  # noqa: E402

VARIANTS = {
    # print line hot -> cool, crack hot -> cool, dust, ghost foot, grid (bars 1-4, 5-8), far haze, grid brightness;
    # every: a stomp every N beats on the straight grid (half-time: on every accent); step: m the beast advances per
    # stomp (straight, half-time); cam: height (m), pitch down (deg), lens (mm): lava and toxic look 34 deg down so the
    # big downbeat prints land inside the Dino Stage's arch window (at 32 their toes dipped below its bottom edge)
    "lava": dict(hot=(1.0, 0.4, 0.05), cool=(0.9, 0.02, 0.0), crack_hot=(1.0, 0.24, 0.02), crack_cool=(0.8, 0.0, 0.0),
                 dust=(1.0, 0.32, 0.05), ghost=AMBER, grid=(UV, MAGENTA), haze=(0.45, 0.02, 0.0), grid_gain=0.6,
                 every=1, step=(4.5, 6.5), cam=(7.5, 34.0, 24.0)),
    "toxic": dict(hot=(1.0, 0.1, 0.6), cool=(0.32, 0.0, 1.0), crack_hot=(1.0, 0.0, 0.5), crack_cool=(0.28, 0.0, 0.95),
                  dust=(0.5, 0.18, 1.0), ghost=MAGENTA, grid=(CYAN, GREEN), haze=(0.12, 0.0, 0.45), grid_gain=0.35,
                  every=1, step=(4.5, 6.5), cam=(7.5, 34.0, 24.0)),
    "gold": dict(hot=(1.0, 0.42, 0.045), cool=(1.0, 0.1, 0.0), crack_hot=(1.0, 0.32, 0.03),
                 crack_cool=(0.85, 0.02, 0.0), dust=(1.0, 0.4, 0.06), ghost=(1.0, 0.38, 0.03), grid=(MAGENTA, UV),
                 haze=(0.4, 0.04, 0.0), grid_gain=0.6, every=2, step=(7.0, 7.5), cam=(5.0, 24.0, 22.0)),
}
VARIANT, PAL = vj.variant(VARIANTS)
NAME = f"stomp_{VARIANT}"
GAIN = float(vj.arg("--gain", 1.0))

EVERY = vj.ACC if vj.HALFTIME else PAL["every"]   # half-time: a stomp on the kick and one on the snare
PER_LOOP = vj.BEATS // EVERY              # stomps per loop
STEP = PAL["step"][1 if vj.HALFTIME else 0]
TRAVEL = STEP * PER_LOOP                  # 104 m (120 m gold) half-time: the camera backs away one step per stomp
V = TRAVEL / vj.FRAMES
GRID = 2.0                                # TRAVEL / GRID is whole, so the grid matches at the seam
SIZE_N, SIZE_BIG = (3.2, 4.6) if EVERY == 1 else (3.8, 5.4)   # print length (m)
FOOT_X = 1.7                              # the feet land this far left / right of the track
D_LAND = 9.0                              # a print lands this far ahead of the camera
CAM_Z, PITCH, LENS = PAL["cam"]
_top = PITCH - math.degrees(math.atan(10.125 / LENS))   # the frame's top edge, degrees below the horizon
VIEW = CAM_Z / math.tan(math.radians(_top)) + 20.0 if _top > 3.0 else 200.0   # how far ahead the ground shows (m)
TRAIL = int(math.ceil(VIEW / STEP))       # stomps from the previous loop still in view at its start
UNIT = vj.FPB * EVERY                     # frames per stomp interval: the shaders' age unit, so a print glows through
                                          # the gap to the next stomp the same way at any tempo and grid
AGE0 = 20.0                               # object color R = age + AGE0 (Object.color clamps below 0)
ON_EARLY = 0.25 / UNIT                    # "landed" from a motion-blur sample a quarter frame before the stomp
GHOST_H = 4.0                             # the ghost foot drops from this height over the last GHOST_F frames,
GHOST_TILT = 35.0                         # its sole tilted this far toward the camera at the top (deg), flat on landing
GHOST_F = 8
EXT = list(range(-2, vj.FRAMES + 3))


# ------------------------------------------------------------------ music
SECTION_B = 16
MORPH = 8


def since_hit(f):
    f %= vj.FRAMES
    return f - vj.BEAT_F[SECTION_B] if f >= vj.BEAT_F[SECTION_B] else f


def swell(f):
    """The fill: eases in over the last 2 beats of bars 4 and 8, peaks at 1 on the next downbeat, decays over ~1 beat."""
    c = vj.clock(f)
    if c["bar"] in (3, 7) and c["beat"] >= 2:
        f0, f1 = vj.BEAT_F[4 * c["bar"] + 2], vj.BEAT_F[4 * c["bar"] + 4]
        return ((c["f"] - f0) / (f1 - f0)) ** 2
    return math.exp(-since_hit(f) / vj.FPB)


def section(f):
    f %= vj.FRAMES
    nxt = vj.BEAT_F[SECTION_B] if f < vj.BEAT_F[SECTION_B] else vj.FRAMES
    cur = 0.0 if f < vj.BEAT_F[SECTION_B] else 1.0
    x = vj.ease((f - (nxt - MORPH)) / MORPH) if f >= nxt - MORPH else 0.0
    return cur + (1.0 - 2.0 * cur) * x


def beat_frame(k):
    """Frame of absolute beat k (any integer; 32 beats per loop)."""
    n, kk = divmod(k, vj.BEATS)
    return n * vj.FRAMES + vj.BEAT_F[kk]


class Stomp:
    """Stomp j (absolute; j and j + PER_LOOP are the same stomp one loop apart, TRAVEL further on)."""

    def __init__(self, j):
        self.j = j
        jj = j % PER_LOOP
        rng = random.Random(1000 + jj)
        k = j * EVERY
        self.frame = beat_frame(k)
        self.big = (k % vj.BEATS) % 4 == 0
        self.left = jj % 2 == 0
        self.size = SIZE_BIG if self.big else SIZE_N
        x = -0.45 * FOOT_X if self.big else (-FOOT_X if self.left else FOOT_X)
        self.pos = Vector((x + rng.uniform(-0.25, 0.25), D_LAND - j * STEP + rng.uniform(-0.3, 0.3), 0.0))
        self.rot = math.pi + math.radians(rng.uniform(-7, 7) + (8 if self.left else -8))   # toes toward the camera
        self.seed = jj

    def age(self, f):
        """Age in stomp intervals (0 on landing, 1 when the next stomp lands)."""
        return (f - self.frame) / UNIT


STOMPS = [Stomp(j) for j in range(-TRAIL, PER_LOOP + 1)]


# ------------------------------------------------------------------ footprint shape
TOES = [((0.0, 0.34), (0.0, 0.9), 0.15, 0.05),                   # digit III: base, tip, base / tip radius
        ((-0.05, 0.33), (-0.33, 0.73), 0.135, 0.045),             # digit II
        ((0.05, 0.33), (0.34, 0.71), 0.135, 0.045),               # digit IV
        ((0.0, 0.9), (0.0, 1.02), 0.045, 0.004),                  # claws
        ((-0.33, 0.73), (-0.39, 0.83), 0.04, 0.004),
        ((0.34, 0.71), (0.40, 0.81), 0.04, 0.004)]
HEEL = ((0.0, 0.2), 0.17, 0.15)
CENTER = Vector((0.0, 0.3, 0.0))                                  # rays to sample the outline start here
SHIFT = Vector((0.0, 0.5, 0.0))                                   # geometry is centered on its middle


def smin(a, b, k):
    h = max(k - abs(a - b), 0.0) / k
    return min(a, b) - h * h * k / 4


def print_sdf(x, y):
    (cx, cy), rx, ry = HEEL
    d = (math.hypot(x / rx, (y - cy) / ry) - 1.0) * min(rx, ry)
    for (ax, ay), (bx, by), ra, rb in TOES:
        vx, vy = bx - ax, by - ay
        t = min(max(((x - ax) * vx + (y - ay) * vy) / (vx * vx + vy * vy), 0.0), 1.0)
        dt = math.hypot(x - ax - t * vx, y - ay - t * vy) - (ra + (rb - ra) * t)
        d = smin(d, dt, 0.07)
    return d


def outline_pts(n=360):
    """The print's outline (print units, toes toward +Y), sampled along rays from CENTER (the shape is star-shaped)."""
    pts = []
    for i in range(n):
        a = 2 * math.pi * i / n
        dx, dy = math.cos(a), math.sin(a)
        r = 0.0
        while print_sdf(CENTER.x + r * dx, CENTER.y + r * dy) < 0 and r < 1.5:
            r += 0.004
        lo, hi = max(r - 0.004, 0.0), r
        for _ in range(14):
            mid = (lo + hi) / 2
            lo, hi = (mid, hi) if print_sdf(CENTER.x + mid * dx, CENTER.y + mid * dy) < 0 else (lo, mid)
        pts.append(Vector((CENTER.x + lo * dx, CENTER.y + lo * dy, 0.0)) - SHIFT)
    return pts


OUTLINE = outline_pts()


def finish_bm(bm, smooth=True):
    me = bpy.data.meshes.new("m")
    bm.to_mesh(me)
    bm.free()
    if smooth:
        me.shade_smooth()
    return me


def mesh_obj(name, me, mat=None, parent=None):
    """Object on (possibly shared) mesh data; its material is linked to the object, so shared meshes can differ."""
    ob = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(ob)
    if mat is not None:
        if not me.materials:
            me.materials.append(mat)
        ob.material_slots[0].link = "OBJECT"
        ob.material_slots[0].material = mat
    ob.parent = parent
    return ob


def outline_mesh():
    bm = bmesh.new()
    pts = [p + Vector((0, 0, 0.03)) for p in OUTLINE]
    vj.tube(bm, pts, lambda u: 0.024, segs=8, closed=True)
    return finish_bm(bm)


def fill_mesh():
    bm = bmesh.new()
    c = bm.verts.new(CENTER - SHIFT + Vector((0, 0, 0.012)))
    ring = [bm.verts.new(p + Vector((0, 0, 0.012))) for p in OUTLINE]
    for i in range(len(ring)):
        bm.faces.new((c, ring[i], ring[(i + 1) % len(ring)]))
    return finish_bm(bm, smooth=False)


def disc_mesh(n=72):
    bm = bmesh.new()
    vs = [bm.verts.new((math.cos(2 * math.pi * i / n), math.sin(2 * math.pi * i / n), 0.0)) for i in range(n)]
    bm.faces.new(vs)
    return finish_bm(bm, smooth=False)


def crack_mesh(seed, big):
    """Jagged cracks running out from the outline (print units), as flat ribbons on the ground.
    UV.x = distance along the crack from the print (print units), UV.y = 0..1 across the ribbon."""
    rng = random.Random(5000 + seed)
    bm = bmesh.new()
    uvl = bm.loops.layers.uv.new("UVMap")
    ribbons = []

    def walk(p, d, length, u0, w0, depth):
        pts, us = [p.copy()], [u0]
        u, head = u0, d.copy()
        while u - u0 < length:
            ang = rng.gauss(0.0, 0.32)
            c, s = math.cos(ang), math.sin(ang)
            d = Vector((d.x * c - d.y * s, d.x * s + d.y * c, 0.0))
            d = (d + head * 0.35).normalized()                    # jagged, but keeps its heading
            stp = rng.uniform(0.05, 0.12) * (1.4 if big else 1.0)
            p = p + d * stp
            u += stp
            pts.append(p.copy())
            us.append(u)
            if depth < 2 and rng.random() < (0.06 if big else 0.08) and length - (u - u0) > 0.3:
                b = rng.choice((-1, 1)) * rng.uniform(0.45, 0.95)
                cb, sb = math.cos(b), math.sin(b)
                walk(p, Vector((d.x * cb - d.y * sb, d.x * sb + d.y * cb, 0.0)),
                     (length - (u - u0)) * rng.uniform(0.3, 0.6), u, w0 * 0.7, depth + 1)
        ribbons.append((pts, us, w0))

    n_main = 11 if big else 7
    for i in range(n_main):
        a = 2 * math.pi * (i + rng.uniform(0.15, 0.85)) / n_main
        idx = int(a / (2 * math.pi) * len(OUTLINE)) % len(OUTLINE)
        p = OUTLINE[idx]
        d = (p - (CENTER - SHIFT)).normalized()
        length = rng.uniform(3.6, 5.0) if big else rng.uniform(0.9, 2.0)
        walk(p + d * 0.02, d, length, 0.0, 0.017, 0)

    for pts, us, w0 in ribbons:
        n = len(pts)
        left, right = [], []
        for i, p in enumerate(pts):
            t = (pts[min(i + 1, n - 1)] - pts[max(i - 1, 0)]).normalized()
            nrm = Vector((-t.y, t.x, 0.0))
            w = w0 * (1.0 - 0.75 * i / max(n - 1, 1))
            left.append(bm.verts.new(p + nrm * w + Vector((0, 0, 0.006))))
            right.append(bm.verts.new(p - nrm * w + Vector((0, 0, 0.006))))
        for i in range(n - 1):
            f = bm.faces.new((left[i], right[i], right[i + 1], left[i + 1]))
            for loop, (uu, vv) in zip(f.loops, ((us[i], 0.0), (us[i], 1.0), (us[i + 1], 1.0), (us[i + 1], 0.0))):
                loop[uvl].uv = (uu, vv)
    return finish_bm(bm, smooth=False)


# ------------------------------------------------------------------ materials
def decode(s):
    """(age in beats, big flag, seed) from the object color."""
    oi = s.node("ShaderNodeObjectInfo")
    r, g, b = s.xyz(oi.outputs["Color"])
    return s.math("SUBTRACT", r, AGE0), g, b


def emit_landed(s, on, color, strength):
    """Emission once the stomp has landed (on = 1); before that the surface is fully transparent (dithered discard), so
    prints still to come don't cut dark holes in the ground."""
    e = s.node("ShaderNodeEmission")
    s.put(e.inputs["Color"], color)
    s.put(e.inputs["Strength"], strength)
    mx = s.node("ShaderNodeMixShader")
    s.put(mx.inputs["Fac"], on)
    s.nt.links.new(s.node("ShaderNodeBsdfTransparent").outputs[0], mx.inputs[1])
    s.nt.links.new(e.outputs[0], mx.inputs[2])
    s.nt.links.new(mx.outputs[0], s.out.inputs["Surface"])
    return s.mat


def lift(s, kick, sw):
    return s.add(1.0, s.mul(s.c("Kick"), kick), s.mul(s.c("Swell"), sw))


def cooling(s, a, rate, hot, cool):
    return s.mix(s.math("SUBTRACT", 1.0, s.exp(s.mul(a, -rate))), hot, cool)


def outline_mat():
    s = vj.Shader("PrintLine")
    age, big, _ = decode(s)
    on = s.math("GREATER_THAN", age, -ON_EARLY)   # landed (incl. a motion-blur sample 1/4 frame early)
    a = s.math("MAXIMUM", age, 0.0)
    hit = s.exp(s.mul(a, -5.5))
    heat = s.mul(on, s.add(0.38, s.mul(hit, 0.2)), s.exp(s.mul(a, -1 / 3.4)))   # a short ignition over a long
    # cooling glow: the trail lights the gap to the next stomp, so the hit reads as weight, not a flash
    col = cooling(s, a, 0.8, PAL["hot"], PAL["cool"])
    return emit_landed(s, on, col, s.mul(heat, lift(s, 0.2, 0.22), s.falloff(s.dist, 45.0), s.core(0.5, 1.4),
                                         s.madd(big, -0.2, 1.0), 3.4 * GAIN))


def fill_mat():
    s = vj.Shader("PrintFill")
    age, _, _ = decode(s)
    on = s.math("GREATER_THAN", age, -ON_EARLY)   # landed (incl. a motion-blur sample 1/4 frame early)
    a = s.math("MAXIMUM", age, 0.0)
    tc = s.node("ShaderNodeTexCoord")
    x, y, _ = s.xyz(tc.outputs["Object"])
    r = s.math("SQRT", s.add(s.mul(x, x), s.mul(y, y)))
    edge = s.smooth(r, 0.12, 0.5)                                 # glows toward the rim of the print
    glow = s.mul(on, s.add(0.04, s.mul(s.exp(s.mul(a, -5.5)), 0.07)), s.exp(s.mul(a, -1 / 1.8)),
                 s.madd(edge, 0.6, 0.4))
    col = cooling(s, a, 1.2, PAL["hot"], PAL["cool"])
    return emit_landed(s, on, col, s.mul(glow, s.falloff(s.dist, 45.0), 0.6 * GAIN))


def crack_mat():
    s = vj.Shader("Crack")
    age, big, _ = decode(s)
    on = s.math("GREATER_THAN", age, -ON_EARLY)   # landed (incl. a motion-blur sample 1/4 frame early)
    a = s.math("MAXIMUM", age, 0.0)
    uvn = s.node("ShaderNodeUVMap")
    u, v, _ = s.xyz(uvn.outputs["UV"])
    tc = s.madd(big, 0.26, 0.09)                                  # how fast the crack front races out (intervals)
    lmax = s.madd(big, 3.0, 2.0)
    open0 = s.madd(big, -0.15, 0.35)                              # share already cracked on the impact frame
    grow = s.math("SUBTRACT", 1.0, s.exp(s.math("DIVIDE", s.mul(a, -1.0), tc)))
    front = s.mul(lmax, s.add(open0, s.mul(s.math("SUBTRACT", 1.0, open0), grow)))
    reveal = s.math("SUBTRACT", 1.0, s.smooth(s.math("SUBTRACT", u, front), -0.04, 0.04))
    tip = s.mul(s.gauss(u, front, 0.12), s.math("SUBTRACT", 1.0, s.smooth(a, 0.25, 0.9)))
    across = s.math("SUBTRACT", 1.0, s.math("ABSOLUTE", s.madd(v, 2.0, -1.0)))
    glow = s.add(s.mul(reveal, s.add(0.38, s.mul(s.exp(s.mul(a, -2.5)), 0.38)), s.exp(s.mul(a, -1 / 3.4))),
                 s.mul(tip, 1.0))     # the hot fronts racing off the frame bottom read as one-frame hits at 1.5
    col = cooling(s, a, 1.5, PAL["crack_hot"], PAL["crack_cool"])
    return emit_landed(s, on, col, s.mul(glow, s.math("POWER", across, 1.2), lift(s, 0.3, 0.25),
                                         s.falloff(s.dist, 50.0), s.madd(big, -0.3, 1.0), 2.4 * GAIN))


def dust_mat():
    s = vj.Shader("Dust")
    age, _, seed = decode(s)
    on = s.math("GREATER_THAN", age, -ON_EARLY)   # landed (incl. a motion-blur sample 1/4 frame early)
    a = s.math("MAXIMUM", age, 0.0)
    tc = s.node("ShaderNodeTexCoord")
    x, y, _ = s.xyz(tc.outputs["Object"])
    r = s.math("SQRT", s.add(s.mul(x, x), s.mul(y, y)))
    ring = s.gauss(r, 0.82, s.add(0.06, s.mul(s.math("SUBTRACT", 1.0, s.exp(s.mul(a, -2.0))), 0.07)))
    haze = s.mul(s.math("SUBTRACT", 1.0, s.smooth(r, 0.3, 0.85)), 0.05)
    nz = s.node("ShaderNodeTexNoise")
    s.put(nz.inputs["Vector"], s.vec(s.mul(x, 3.0), s.mul(y, 3.0), s.mul(seed, 7.3)))
    nz.inputs["Scale"].default_value = 1.6
    nz.inputs["Detail"].default_value = 4.0
    grain = s.madd(s.math("SUBTRACT", nz.outputs["Fac"], 0.5), 1.6, 0.8)
    puff = s.smooth(a, 0.0, 2.5 / UNIT)                           # rolls out over 2-3 frames: popping in at full
    dust = s.mul(on, puff, s.exp(s.mul(a, -3.2)), s.add(ring, haze), s.math("MAXIMUM", grain, 0.0))   # size read
    return s.additive(PAL["dust"], s.mul(dust, lift(s, 0.15, 0.2), s.falloff(s.dist, 45.0), 0.28 * GAIN))  # as a hit


def ghost_mat():
    s = vj.Shader("GhostFoot")
    age, _, _ = decode(s)
    rise = s.smooth(age, -GHOST_F / UNIT, 0.0)                    # fades in as it drops and peaks on the impact,
    after = s.exp(s.mul(s.math("MAXIMUM", age, 0.0), -6.0))       # where it lies on the print; then fades with the hit
    return s.additive(PAL["ghost"], s.mul(rise, after, s.core(0.5, 1.4), 0.32 * GAIN))


def ground_mat():
    s = vj.Shader("Ground")
    geo = s.node("ShaderNodeNewGeometry")
    x, y, _ = s.xyz(geo.outputs["Position"])
    hw = s.mul(s.dist, 0.0024)                                    # constant on-screen line width

    def lines(v):
        t = s.math("FRACT", s.madd(v, 1.0 / GRID, 0.5))
        d = s.mul(s.math("ABSOLUTE", s.math("SUBTRACT", t, 0.5)), GRID)
        n = s.node("ShaderNodeMapRange", interpolation_type="SMOOTHSTEP")
        s.put(n.inputs["Value"], d)
        s.put(n.inputs["From Min"], hw)
        s.put(n.inputs["From Max"], s.mul(hw, 2.5))
        return s.math("SUBTRACT", 1.0, n.outputs["Result"])

    g = s.math("MAXIMUM", lines(x), lines(y))
    rc = TRAVEL / (2 * math.pi)                                   # the crackle repeats every TRAVEL along y
    th = s.mul(y, 2 * math.pi / TRAVEL)
    vor = s.node("ShaderNodeTexVoronoi", feature="DISTANCE_TO_EDGE")
    s.put(vor.inputs["Vector"], s.vec(x, s.mul(s.math("COSINE", th), rc), s.mul(s.math("SINE", th), rc)))
    vor.inputs["Scale"].default_value = 0.45
    crackle = s.math("SUBTRACT", 1.0, s.smooth(vor.outputs["Distance"], 0.0, 0.04))
    fade = s.falloff(s.dist, 28.0)
    far = s.mul(s.smooth(s.dist, 22.0, 55.0), s.math("SUBTRACT", 1.0, s.smooth(s.dist, 120.0, 190.0)), 0.06)   # gone
    # before the ground ends (>= VIEW + 30 m ahead): the low camera sees to the horizon, and a visible far edge moved
    lift_g = s.add(0.55, s.mul(s.c("Kick"), 0.16), s.mul(s.c("Swell"), 0.5), s.mul(s.c("Section"), 0.35))   # the
    # stomps carry the hit (shake, ignition); a grid pumping on every accent read as a flash in half-time
    a, b = PAL["grid"]
    grid = s.mul(g, fade, lift_g, PAL["grid_gain"] * GAIN)
    haze = s.mul(s.add(s.mul(crackle, fade, 0.08), far), lift_g, GAIN)
    e1 = s.node("ShaderNodeEmission")
    s.put(e1.inputs["Color"], s.mix(s.c("Section"), a, b))
    s.put(e1.inputs["Strength"], grid)
    e2 = s.node("ShaderNodeEmission")
    s.put(e2.inputs["Color"], PAL["haze"])
    s.put(e2.inputs["Strength"], haze)
    add = s.node("ShaderNodeAddShader")
    s.nt.links.new(e1.outputs[0], add.inputs[0])
    s.nt.links.new(e2.outputs[0], add.inputs[1])
    s.nt.links.new(add.outputs[0], s.out.inputs["Surface"])
    return s.mat


# ------------------------------------------------------------------ keying
def keyed(owner, prop, frame_values, interp="LINEAR"):
    """Key owner.prop at every (frame, value) in one pass per F-curve."""
    f0, v0 = frame_values[0]
    setattr(owner, prop, v0)
    owner.keyframe_insert(prop, frame=f0)
    path = owner.path_from_id(prop)
    for fc in vj.fcurves_of(owner.id_data):
        if fc.data_path != path:
            continue
        i = fc.array_index
        kp = fc.keyframe_points
        kp.add(len(frame_values) - 1)
        co = []
        for f, v in frame_values:
            co += [f, v[i] if isinstance(v, (tuple, list, Vector)) else v]
        kp.foreach_set("co", co)
        for p in kp:
            p.interpolation = interp
        fc.update()


def key_age(ob, st):
    """Object color = (age + AGE0, big, seed, 1), linear in time: the shaders derive everything from it."""
    ends = (-60, vj.FRAMES + 60)
    keyed(ob, "color", [(f, (st.age(f) + AGE0, 1.0 if st.big else 0.0, st.seed / PER_LOOP, 1.0)) for f in ends])


def dust_radius(st, f):
    a = st.age(f)
    if a < 0 or a > 2.5:
        return 0.001
    r0, r1 = (0.9, 2.4) if st.big else (0.75, 1.6)                # from the print's edge outward
    return (r0 + (r1 - r0) * (1 - math.exp(-a * 3.0))) * st.size


def shake(f):
    """Camera (pitch, roll, drop) from the stomps of the last ~20 frames: a damped jolt, bigger on the downbeats."""
    pitch = roll = drop = 0.0
    for st in STOMPS:
        t = f - st.frame - 1                                      # the jolt lands a frame after the impact: on the
        if 0 <= t < 24:                                           # impact frame it threw the freshly lit print across
            # a region edge and straight back (a one-frame hit in the gate)
            e = math.exp(-t / 3.2) * math.sin(2 * math.pi * t / 4.6)
            heavy = 1.0 if st.big else (0.65 if EVERY == 2 else 0.4)   # half-time: the snare stomp hits hard too
            pitch += 0.75 * heavy * e
            roll += 0.45 * heavy * e * (1 if st.left else -1)
            drop += 0.12 * heavy * math.exp(-t / 3.2) * math.sin(math.pi * min(t / 2.3, 1.0))
    return pitch, roll, drop


# ------------------------------------------------------------------ scene
def signals(f):
    c = vj.clock(f)
    return {"Kick": c["kick"], "Swell": swell(f), "Section": section(f)}


def build():
    scene = vj.reset_scene()
    frames = list(range(vj.FRAMES + 1))
    sig = [signals(f) for f in frames]
    vj.build_clock({key: [s[key] for s in sig] for key in sig[0]})

    mats = {"line": outline_mat(), "fill": fill_mat(), "crack": crack_mat(), "dust": dust_mat(), "ghost": ghost_mat()}
    m_line, m_fill, m_disc = outline_mesh(), fill_mesh(), disc_mesh()
    m_cracks = {}
    for st in STOMPS:
        if (st.seed, st.big) not in m_cracks:
            m_cracks[st.seed, st.big] = crack_mesh(st.seed, st.big)
        root = vj.new_empty(f"Stomp{st.j}")
        root.location = st.pos
        root.rotation_euler = (0.0, 0.0, st.rot)
        root.scale = (st.size, st.size, st.size)
        parts = [mesh_obj(f"S{st.j}Line", m_line, mats["line"], root),
                 mesh_obj(f"S{st.j}Fill", m_fill, mats["fill"], root),
                 mesh_obj(f"S{st.j}Cracks", m_cracks[st.seed, st.big], mats["crack"], root)]
        for ob in parts:
            key_age(ob, st)
        dust = mesh_obj(f"S{st.j}Dust", m_disc, mats["dust"])
        dust.location = st.pos + Vector((0, 0, 0.05))
        key_age(dust, st)
        keyed(dust, "scale", [(f, (dust_radius(st, f),) * 3) for f in EXT])
        ghost = mesh_obj(f"S{st.j}Ghost", m_line, mats["ghost"])
        key_age(ghost, st)
        gk = []
        for t in range(-GHOST_F - 2, 2):                         # drops in over the last GHOST_F frames
            u = min(max(-t / GHOST_F, 0.0), 1.2)
            gk.append((st.frame + t, (st.pos.x, st.pos.y, GHOST_H * u * u), st.size * (1.0 + 0.3 * u),
                       (-math.radians(GHOST_TILT) * u, 0.0, st.rot)))   # heel up: the sole faces the camera
        keyed(ghost, "location", [(f, loc) for f, loc, _, _ in gk])
        keyed(ghost, "scale", [(f, (sc,) * 3) for f, _, sc, _ in gk])
        keyed(ghost, "rotation_euler", [(f, rot) for f, _, _, rot in gk])

    ground = bmesh.new()
    bmesh.ops.create_grid(ground, x_segments=1, y_segments=1, size=1.0)
    ahead = VIEW + 30.0                                           # the far edge never shows (the low camera sees
    bmesh.ops.scale(ground, vec=(220, 0.5 * (TRAVEL + 70 + ahead), 1), verts=ground.verts)   # to the horizon)
    bmesh.ops.translate(ground, vec=(0, ahead - 0.5 * (TRAVEL + 70 + ahead), 0), verts=ground.verts)
    vj.new_obj("Ground", ground, ground_mat())

    cam_data = bpy.data.cameras.new("Cam")
    cam_data.lens, cam_data.sensor_width, cam_data.sensor_fit = LENS, 36.0, "HORIZONTAL"
    cam_data.clip_start, cam_data.clip_end = 0.2, 400.0
    cam = bpy.data.objects.new("Cam", cam_data)
    scene.collection.objects.link(cam)
    scene.camera = cam
    loc, rot = [], []
    for f in EXT:
        w = 2 * math.pi * f / vj.FRAMES
        p, r, d = shake(f)
        loc.append((f, (0.5 * math.sin(w), -V * f, CAM_Z + 0.2 * math.sin(2 * w) - d)))
        rot.append((f, (math.radians(90.0 - PITCH - p), math.radians(r), math.radians(1.5 * math.sin(w + 1.0)))))
    keyed(cam, "location", loc)
    keyed(cam, "rotation_euler", rot)
    return scene


scene = build()
vj.setup_render(scene, samples=int(vj.arg("--samples", 16)), pct=int(vj.arg("--pct", 100)),
                view=vj.arg("--view", "Standard"), exposure=float(vj.arg("--exposure", 0.0)),
                bloom=tuple(float(x) for x in vj.arg("--bloom", "1.0,0.6,0.4").split(",")), mblur=vj.flag("--mblur"))
vj.finish(scene, NAME)
