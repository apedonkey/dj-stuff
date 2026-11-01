"""CHAIN REACTION - REACTOR VJ loop. 8 bars, seamless, 1920x1080 @ 30 fps; tempo from vjkit (140 BPM half-time =
411 frames).

Nuclei (clusters of neon-rimmed nucleons, two tones) drift in the dark. A neutron (a bright dot with a trail) hits one
4 frames before an accent; the nucleus stretches, glows, and splits ON the accent into two hot fragments that fly apart
and cool, with a soft flash and 2-3 new neutrons. Those hit more nuclei on the next accent: a branching cascade.
  Section A (bars 1-4): two small cascades, one from the left (accents 1-4), one from the right (accents 5-8).
  Section B (bars 5-8, the drop): one cascade from the centre, 1 -> 3 -> 9 -> 18 fissions on bars 5-6's accents, its
  last neutrons bursting outward to fill the frame; a few stragglers split in bar 7; everything has faded by bar 8,
  where the next root neutron flies in through the swell (it splits on the loop's downbeat, frame 0 = frame 411).
Split nuclei re-form (fade back in) about 4 bars later, so the field is full again a loop on. The camera drifts in
through the drop and back out; the drop's accents thump it a little.
Variants: cyan (cyan/blue nuclei, hot orange fragments), amber (amber/ember nuclei, white-hot neutrons), magenta
(plasma/UV nuclei, cyan neutrons).
No strobing: flashes land on the accent and decay over ~5 frames (no one-frame hits); 18 small flashes spread over the
frame stay far under the region flash threshold.

  blender.exe -b --factory-startup --python chain_reaction.py -- --variant cyan --frames 0,206,283 [--pct 25]
  blender.exe -b --factory-startup --python chain_reaction.py -- --variant cyan --all --seam DIR [--mblur]
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
import rx_core as rx  # noqa: E402
from vjkit import AMBER, CHERENKOV, COOLANT, EMBER, HOT, PLASMA, UVP  # noqa: E402

# nucleons (two tones), their dim fill; neutron head and trail; fragments hot -> cool; the fission flash
VARIANTS = {
    "cyan": dict(nuc=(COOLANT, CHERENKOV), fill=(0.02, 0.1, 0.3), head=(0.75, 0.95, 1.0), trail=COOLANT,
                 frag=(HOT, (1.0, 0.25, 0.02)), flash=CHERENKOV, rim=0.85, seed=11),
    "amber": dict(nuc=(AMBER, EMBER), fill=(0.25, 0.04, 0.0), head=(1.0, 0.88, 0.7), trail=AMBER,
                  frag=(HOT, EMBER), flash=(1.0, 0.3, 0.03), rim=0.8, seed=23),
    "magenta": dict(nuc=(PLASMA, UVP), fill=(0.15, 0.0, 0.3), head=(0.7, 0.95, 1.0), trail=COOLANT,
                    frag=((1.0, 0.55, 0.9), PLASMA), flash=PLASMA, rim=1.2, seed=37),
}
VNAME, V = vj.variant(VARIANTS)
GAIN = float(vj.arg("--gain", 1.0))

LENS = 30.0
TAN_H = 18.0 / LENS                       # tan of half the horizontal view; vertical: x 9/16
DEPTH = (9.0, 30.0)                       # the field's depth range (m in front of the camera)
N_NUCLEI = 100
R_NUC = 0.42                              # nucleus radius (m)
WOBBLE = 4                                # frames between a neutron's arrival and the split (on the accent)
FRAG_LIFE, HALO_LIFE = 48, 20             # frames a fragment / a flash lasts
REFORM = (215, 255)                       # frames after its split when a nucleus fades back in
TRAIL_LAG = 7                             # the trail spans the path of the last TRAIL_LAG frames
ESC_SPEED, ESC_LIFE = 0.3, 26             # escaping neutrons: m per frame, frames
# cascades: (root accent, fissions per generation, aim in the frame (x, y from -1..1), outward spread)
CASCADES = [(0, [1, 2, 4, 2], (-0.42, 0.12)),
            (4, [1, 2, 4, 2], (0.45, -0.18)),
            (8, [1, 3, 9, 18, 3], (0.0, 0.0))]
DIST = (1.8, 6.8)                         # a neutron's flight: nearest and farthest target (m)
SAFE = 0.8                                # splits land inside this share of the frame (the key art)
MIN_SPLIT = 11.5                          # and at least this far from the lens (a near split filled 120 px blocks)


# ------------------------------------------------------------------ the field
class Nucleus:
    def __init__(self, i, base, rng):
        self.i, self.base = i, base
        self.amp = Vector((rng.uniform(0.15, 0.5), rng.uniform(0.1, 0.4), rng.uniform(0.15, 0.45)))
        self.ph = [rng.uniform(0, 2 * math.pi) for _ in range(3)]
        self.split = None                                       # frame of its split (an accent) or None
        self.axis = Vector((rng.gauss(0, 1), rng.gauss(0, 0.4), rng.gauss(0, 1))).normalized()
        self.mesh = rng.randrange(3)
        self.size = rng.uniform(0.85, 1.15)

    def pos(self, f):
        """Slow drift: a small closed loop once per loop (seamless)."""
        a = 2 * math.pi * f / vj.FRAMES
        return self.base + Vector((self.amp.x * math.sin(a + self.ph[0]), self.amp.y * math.sin(a + self.ph[1]),
                                   self.amp.z * math.cos(a + self.ph[2])))


def cam_pos(f):
    """The camera drifts on a small loop and moves in through the drop (seamless)."""
    a = 2 * math.pi * f / vj.FRAMES
    return Vector((0.9 * math.sin(a), 1.25 * (1 - math.cos(a)), 0.5 * math.sin(2 * a)))


def in_view(p, margin=0.92, f=None):
    """Frame coordinates (-1..1, scaled by 1/margin) of a point seen from the camera at frame f (at rest at the
    origin if f is None), looking +Y (None if behind)."""
    q = p - cam_pos(f) if f is not None else p
    if q.y <= 0.1:
        return None
    return q.x / (q.y * TAN_H) / margin, q.z / (q.y * TAN_H * 9 / 16) / margin


def make_field(rng):
    pts = []
    while len(pts) < N_NUCLEI:
        y = DEPTH[0] + (DEPTH[1] - DEPTH[0]) * rng.random() ** 0.6     # more volume (and nuclei) further out
        x = rng.uniform(-1, 1) * y * TAN_H * 0.95
        z = rng.uniform(-1, 1) * y * TAN_H * 9 / 16 * 0.92
        p = Vector((x, y, z))
        if all((p - q).length > 2.1 for q in pts):
            pts.append(p)
    return [Nucleus(i, p, rng) for i, p in enumerate(pts)]


def plan(nuclei, rng):
    """Assign splits, flights (from, to, launch frame, arrival frame) and escapes (from, direction, launch frame)."""
    flights, escapes = [], []
    for root_acc, counts, aim in CASCADES:
        free = [n for n in nuclei if n.split is None]
        t_root = rx.acc_frame(root_acc)
        far = [n for n in free if (n.pos(t_root) - cam_pos(t_root)).y >= MIN_SPLIT + 2.0]
        root = min(far, key=lambda n: (Vector(in_view(n.base)) - Vector(aim)).length + 0.04 * abs(n.base.y - 17.0))
        root.split = t_root
        src = root.pos(t_root - 26) + Vector((rng.uniform(-5, 5), rng.uniform(-2, 3), rng.uniform(-3, 3)))
        flights.append((None, root, t_root - 26, t_root - WOBBLE, src))      # the root's neutron flies in
        frontier = [root]
        for g, count in enumerate(counts[1:], start=1):
            t = rx.acc_frame(root_acc + g)
            base_n, extra = divmod(count, len(frontier))
            new = []
            for pi, p in enumerate(frontier):
                want = base_n + (1 if pi < extra else 0)
                pp = p.pos(p.split)
                out = (pp - root.pos(root.split))
                cands = []
                for q in nuclei:
                    if q.split is not None:
                        continue
                    d = (q.pos(t - WOBBLE) - pp)
                    if not DIST[0] <= d.length <= DIST[1]:
                        continue
                    fv = in_view(q.pos(t), SAFE, t)                   # the split stays in the safe area
                    if fv is None or abs(fv[0]) > 1.0 or abs(fv[1]) > 1.0:
                        continue
                    if (q.pos(t) - cam_pos(t)).y < MIN_SPLIT:
                        continue
                    score = d.length - (2.0 * out.normalized().dot(d.normalized()) if out.length > 0.5 else 0.0)
                    cands.append((score, q))
                cands.sort(key=lambda c: c[0])
                for _, q in cands[:want]:
                    q.split = t
                    flights.append((p, q, p.split, t - WOBBLE, None))
                    new.append(q)
                n_esc = max(0, 2 + rng.randrange(2) - min(want, len(cands)))     # 2-3 neutrons per split
                for _ in range(n_esc):
                    escapes.append((p, escape_dir(pp, root.pos(root.split), rng), p.split))
            frontier = new or frontier
        for p in frontier:                                     # the last generation: its neutrons all escape
            if p.split == rx.acc_frame(root_acc + len(counts) - 1):
                for _ in range(2 + rng.randrange(2)):
                    escapes.append((p, escape_dir(p.pos(p.split), root.pos(root.split), rng), p.split))
    return flights, escapes


def escape_dir(p, root, rng):
    """Outward from the cascade's root, mostly sideways (never much toward the lens)."""
    d = (p - root)
    d = d.normalized() if d.length > 0.5 else Vector((rng.uniform(-1, 1), 0.0, rng.uniform(-1, 1))).normalized()
    d = (d + Vector((rng.gauss(0, 0.5), rng.gauss(0, 0.3), rng.gauss(0, 0.5)))).normalized()
    d.y = max(d.y, -0.15)
    return d.normalized()


# ------------------------------------------------------------------ materials
def nucleus_mat():
    """Nucleons: rim-lit spheres in two tones (per-face attribute kind), a dim fill, fading with distance; Object.color
    alpha = glow (1 at rest, up to 1.5 while a nucleus stretches before its split, 0 while gone)."""
    s = vj.Shader("Nuclei")
    _, alpha, _ = s.obj_info()
    kind = rx.attr(s, "kind")
    col = s.mix(kind, V["nuc"][0], V["nuc"][1])
    lift = s.mul(s.add(1.0, s.mul(s.c("Swell"), 0.4)), s.madd(s.falloff(s.dist, 14.0), 1.25, 0.16))
    rim = s.rim((0.42, 0.92))
    return s.emit_sum([(col, s.mul(rim, alpha, lift, V["rim"] * GAIN)),
                       (V["fill"], s.mul(s.inv(rim), alpha, lift, 0.6 * GAIN))])


def fragment_mat():
    """Fission fragments: glowing hot balls (colour and level from Object.color), brighter in the middle (at most
    ~0.85: at 2.1 they clipped to white and, under the flash, filled whole 1 m2 blocks)."""
    s = vj.Shader("Fragments")
    col, alpha, _ = s.obj_info()
    return s.emit(col, s.mul(alpha, s.madd(s.inv(s.facing()), 0.6, 0.3), 1.25 * GAIN))


def head_mat():
    s = vj.Shader("NeutronHead")
    col, alpha, _ = s.obj_info()
    return s.emit(col, s.mul(alpha, 2.8 * GAIN))


def trail_mat():
    """Neutron trail: additive, brightest at the head (local x = 0), fading to the tail (x = -1), soft edges."""
    s = vj.Shader("NeutronTrail")
    col, alpha, _ = s.obj_info()
    x, _, _ = s.obj_coords()
    along = s.math("POWER", s.math("MAXIMUM", s.add(x, 1.0), 0.0), 2.0)
    soft = s.math("POWER", s.inv(s.facing()), 1.5)
    return s.additive(col, s.mul(alpha, along, soft, 3.0 * GAIN))


def halo_mat():
    """The fission flash: an expanding shell, bright at its silhouette and empty in the middle, so it never stacks on
    the hot fragments (a soft ball there clipped to white). Object.color alpha = its envelope."""
    s = vj.Shader("Flash")
    col, alpha, _ = s.obj_info()
    shell = s.math("POWER", s.facing(), 2.5)
    return s.additive(col, s.mul(alpha, shell, 1.2 * GAIN))


def dust_mat():
    s = vj.Shader("Dust")
    x, y, z = s.obj_coords()
    tw = s.noise4(s.vec(s.mul(x, 0.2), s.mul(z, 0.2), s.c("LoopCos")), s.c("LoopSin"), scale=2.0)
    return s.emit(V["nuc"][1], s.mul(s.madd(s.smooth(tw, 0.3, 0.7), 0.6, 0.3), 0.35 * GAIN))


# ------------------------------------------------------------------ meshes
def cluster_bm(rng, n, radius):
    """A ball of n nucleons (r 0.13 each, packed inside `radius`), per-face attribute kind 0/1 (proton/neutron)."""
    bm = bmesh.new()
    kl = bm.faces.layers.float.new("kind")
    pts = [Vector((0, 0, 0))]
    for _ in range(4000):                                         # dart throwing inside the ball
        if len(pts) >= n:
            break
        p = Vector((rng.uniform(-1, 1), rng.uniform(-1, 1), rng.uniform(-1, 1))) * radius
        if p.length <= radius and all((p - q).length >= 0.17 for q in pts):
            pts.append(p)
    for k, p in enumerate(pts):
        before = set(bm.faces)
        bmesh.ops.create_icosphere(bm, subdivisions=2, radius=0.13, matrix=Matrix.Translation(p))
        for face in set(bm.faces) - before:
            face[kl] = float(k % 2)
    return bm


def trail_bm():
    bm = bmesh.new()
    vj.tube(bm, [Vector((-t / 6, 0, 0)) for t in range(7)], lambda u: 0.045 * (1 - u) + 0.008, segs=8)
    return bm


# ------------------------------------------------------------------ keyed states
def age_of(f, t0):
    """Frames since event frame t0 on the looping timeline, in [0, FRAMES)."""
    return (f - t0) % vj.FRAMES


def nucleus_state(n, f):
    """(location, rotation quaternion, scale vector, colour) of nucleus n at frame f."""
    p = n.pos(f)
    q = n.axis.to_track_quat("X", "Z")
    sz = n.size
    if n.split is None:
        return p, q, (sz, sz, sz), (1, 1, 1, 1.0)
    age = age_of(f, n.split)
    if age >= vj.FRAMES - WOBBLE:                               # stretching toward the split, glowing hotter
        x = (age - (vj.FRAMES - WOBBLE) + 1) / WOBBLE
        return p, q, (sz * (1 + 0.5 * x * x), sz * (1 - 0.15 * x), sz * (1 - 0.15 * x)), (1, 1, 1, 1.0 + 0.5 * x)
    if age < REFORM[0]:
        return p, q, (1e-4,) * 3, (1, 1, 1, 0.0)
    if age < REFORM[1]:
        x = rx.ramp_between(age, REFORM[0], REFORM[1])
        s = sz * (0.4 + 0.6 * x)
        return p, q, (s, s, s), (1, 1, 1, x)
    return p, q, (sz, sz, sz), (1, 1, 1, 1.0)


def fragment_state(n, side, f):
    p0 = n.pos(f)
    age = age_of(f, n.split)
    if age >= FRAG_LIFE:
        return p0, 1e-4, (0, 0, 0, 0.0)
    d = 1.4 * (1 - math.exp(-age / 9.0))
    p = p0 + n.axis * (side * (0.25 + d))
    k = age / FRAG_LIFE
    hot, cool = V["frag"]
    col = tuple(a + (b - a) * min(k * 1.6, 1.0) for a, b in zip(hot, cool))
    alpha = (1.0 - rx.ramp_between(age, 8, FRAG_LIFE)) * (1.0 if age > 0 else 0.9)
    return p, n.size * 0.62 * (1.0 - 0.3 * k), (*col, alpha)


def halo_state(n, f):
    p = n.pos(n.split)
    t = rx.cyc(f - n.split)
    e = rx.hit_env(t, decay=5.0)
    if t < -2 or t > HALO_LIFE:
        return p, 1e-4, (0, 0, 0, 0.0)
    return p, 0.6 + 1.0 * (1 - math.exp(-max(t, 0) / 3.0)), (*V["flash"], e)   # starts outside the fragments


def flight_state(fl, f):
    """(head location, head size, head colour, trail location, rotation, trail length, trail colour)."""
    src, dst, t0, t1, src_pt = fl
    p0 = src.pos(t0) if src is not None else src_pt
    p1 = dst.pos(t1)
    dur = t1 - t0
    t = age_of(f, t0)

    def at(tt):
        return p0 + (p1 - p0) * min(max(tt / dur, 0.0), 1.0)

    q = (p1 - p0).normalized().to_track_quat("X", "Z")
    if t > dur + TRAIL_LAG:
        return p1, 1e-4, (0, 0, 0, 0), p1, q, 1e-4, (0, 0, 0, 0)
    head = at(t)
    tail = at(t - TRAIL_LAG)
    length = max((head - tail).length, 1e-4)
    on = 1.0 if t <= dur else 0.0
    fade_in = min((t + 1) / 3.0, 1.0)
    return (head, 0.07 * on + 1e-4, (*V["head"], on), head, q, length,
            (*V["trail"], fade_in * (1.0 if t <= dur else 1.0 - (t - dur) / (TRAIL_LAG + 1))))


def escape_state(es, f):
    src, d, t0 = es
    p0 = src.pos(t0)
    t = age_of(f, t0)
    q = d.to_track_quat("X", "Z")
    if t > ESC_LIFE:
        return p0, 1e-4, (0, 0, 0, 0), p0, q, 1e-4, (0, 0, 0, 0)
    head = p0 + d * (ESC_SPEED * t)
    length = max(ESC_SPEED * min(t, TRAIL_LAG), 1e-4)
    fade = (1.0 - rx.ramp_between(t, 10, ESC_LIFE)) * min((t + 1) / 3.0, 1.0)
    return head, 0.07 * fade + 1e-4, (*V["head"], fade), head, q, length, (*V["trail"], fade)


def signals(f):
    s = {"Swell": vj.swell(f, decay_beats=1.5)}
    s.update(vj.loop_signals(f))
    return s


# ------------------------------------------------------------------ scene
def key_neutron(name, state_fn, meshes, mats, ext):
    head = vj.mesh_obj(f"{name}H", meshes[0], mats[0])
    trail = vj.mesh_obj(f"{name}T", meshes[1], mats[1])
    trail.rotation_mode = "QUATERNION"
    hl, hs, hc, tl, tr, ts, tc = [], [], [], [], [], [], []
    for f in ext:
        h, hsz, hcol, tloc, q, tlen, tcol = state_fn(f)
        hl.append((f, tuple(h)))
        hs.append((f, (hsz,) * 3))
        hc.append((f, tuple(hcol)))
        tl.append((f, tuple(tloc)))
        tr.append((f, tuple(q)))
        ts.append((f, (tlen, 1.0 if tlen > 1e-3 else 1e-4, 1.0 if tlen > 1e-3 else 1e-4)))
        tc.append((f, tuple(tcol)))
    vj.keyed(head, "location", hl)
    vj.keyed(head, "scale", hs)
    vj.keyed(head, "color", hc)
    vj.keyed(trail, "location", tl)
    vj.keyed(trail, "rotation_quaternion", tr)
    vj.keyed(trail, "scale", ts)
    vj.keyed(trail, "color", tc)


def build():
    scene = vj.reset_scene()
    vj.clock_from(signals)
    ext = vj.EXT
    rng = random.Random(V["seed"])
    nuclei = make_field(rng)
    flights, escapes = plan(nuclei, rng)
    n_split = sum(1 for n in nuclei if n.split is not None)
    vj.log(f"chain: {n_split} fissions, {len(flights)} neutron hits, {len(escapes)} escaping neutrons")

    nm = nucleus_mat()
    meshes = [vj.finish_bm(cluster_bm(random.Random(100 + k), 15, 0.36), name=f"Nucleus{k}") for k in range(3)]
    frag_meshes = [vj.finish_bm(cluster_bm(random.Random(200 + k), 7, 0.25), name=f"Frag{k}") for k in range(2)]
    fm, hm = fragment_mat(), halo_mat()
    ball = rx.ico_mesh("Ball", 2)
    shell = rx.ico_mesh("Shell", 4)                               # the flash rings: a smooth silhouette (on the
                                                                  # neutron heads' sphere they showed polygons)
    for n in nuclei:
        ob = vj.mesh_obj(f"Nucleus{n.i:03d}", meshes[n.mesh], nm)
        ob.rotation_mode = "QUATERNION"
        st = [nucleus_state(n, f) for f in ext]
        vj.keyed(ob, "location", [(f, tuple(s[0])) for f, s in zip(ext, st)])
        vj.keyed(ob, "rotation_quaternion", [(f, tuple(s[1])) for f, s in zip(ext, st)])
        vj.keyed(ob, "scale", [(f, s[2]) for f, s in zip(ext, st)])
        vj.keyed(ob, "color", [(f, s[3]) for f, s in zip(ext, st)])
        if n.split is None:
            continue
        for side in (-1, 1):
            fr = vj.mesh_obj(f"Frag{n.i:03d}{'ab'[side > 0]}", frag_meshes[side > 0], fm)
            rx.particle_keys(fr, ext, lambda f, n=n, side=side: fragment_state(n, side, f))
        ha = vj.mesh_obj(f"Flash{n.i:03d}", shell, hm)
        rx.particle_keys(ha, ext, lambda f, n=n: halo_state(n, f))

    hmesh, tmesh = ball, vj.finish_bm(trail_bm(), name="Trail")
    hmat, tmat = head_mat(), trail_mat()
    for i, fl in enumerate(flights):
        key_neutron(f"N{i:03d}", lambda f, fl=fl: flight_state(fl, f), (hmesh, tmesh), (hmat, tmat), ext)
    for i, es in enumerate(escapes):
        key_neutron(f"E{i:03d}", lambda f, es=es: escape_state(es, f), (hmesh, tmesh), (hmat, tmat), ext)

    db = bmesh.new()                                              # far dust: depth behind the field
    drng = random.Random(5)
    for _ in range(260):
        y = drng.uniform(38.0, 75.0)
        p = Vector((drng.uniform(-1, 1) * y * TAN_H, y, drng.uniform(-1, 1) * y * TAN_H * 9 / 16))
        bmesh.ops.create_icosphere(db, subdivisions=1, radius=drng.uniform(0.05, 0.12), matrix=Matrix.Translation(p))
    vj.new_obj("Dust", db, dust_mat())

    cam = vj.camera(scene, lens=LENS, clip=(0.5, 300.0))
    loc, rot = [], []
    for f in ext:
        a = 2 * math.pi * f / vj.FRAMES
        j = vj.jolt(f) * vj.section(f)                            # the drop's accents thump the camera
        p = cam_pos(f)
        look = Vector((0.6 * math.sin(a + 0.8), 20.0, 0.4 * math.sin(2 * a + 1.3)))
        e = vj.look_at(p, look, roll=1.2 * math.sin(a + 0.4))
        loc.append((f, tuple(p)))
        rot.append((f, (e.x + math.radians(0.35 * j), e.y, e.z)))
    vj.keyed(cam, "location", loc)
    vj.keyed(cam, "rotation_euler", rot)
    return scene


scene = build()
vj.standard_render(scene)
vj.finish(scene, f"chain_reaction_{VNAME}")
