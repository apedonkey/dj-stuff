"""GRAVEYARD SHIFT STING - the Halloween stage's ID (act changes, station ID). 4 bars, seamless, 1920x1080 @ 30 fps;
tempo from vjkit (140 BPM half-time; render it with VJ_BARS=4: 206 frames, 6.87 s).

The words GRAVEYARD / SHIFT in our own stroke letterforms (letters.py), every stroke a neon bone with knobbed ends
(the Dino sting's bones, scripts/sting.py of the Dino pack, re-dressed): bone white on a UV-purple glow.
  Downbeat     the bones have dripped into place: they land with a swell (no flash) and the camera thumps a frame later.
  Beats 1-12   they hold, breathing on the kick and the snare; a highlight sweeps across once per bar; toxic-green slime
               oozes down from the letters' feet and grows over the first bars.
  Beats 13-14  the logo crumbles: the bones loosen and fall away, tumbling, fading as they drop (a soft fade, no cut).
  Beats 15-16  the bones drip back in from above, one after another, braking to rest exactly on the next downbeat.
No strobing: the landing is a swell, the fades are a beat long, the slime is thin lines.

  VJ_BARS=4 blender.exe -b --factory-startup --python sting.py -- --frames 0,30,180,200 [--pct 50] [--samples 16]
  VJ_BARS=4 blender.exe -b --factory-startup --python sting.py -- --all --seam DIR [--out DIR] [--mblur]
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
import letters  # noqa: E402
from vjkit import TOXIC, UVP  # noqa: E402

VARIANTS = {
    "bone": dict(bone=(0.86, 0.82, 0.70), glow=UVP, slime=TOXIC, sweep=(1.0, 0.62, 0.30)),
}
VNAME, V = vj.variant(VARIANTS)
GAIN = float(vj.arg("--gain", 1.0))
R_TOP, R_BOT = 0.085, 0.07                     # bone radius: GRAVEYARD, SHIFT
AIM_Z = 0.15
CAM_D = 16.0
B = vj.BEATS                                   # 16 for the 4-bar sting
CRUMBLE = (B - 4.0, B - 2.5)                   # beats: the logo falls apart
DRIP = 2.0                                     # beats the bones take to drip back in (land on the downbeat)


# ------------------------------------------------------------------ timing
def fly_in(p, pa=0.5, pb=0.9):
    """0..1: accelerate until pa, full speed until pb, brake to rest at 1 (the Dino sting's lock: the seam step is
    never the loop's biggest jump)."""
    vm = 2.0 / (1.0 + pb - pa)
    if p <= pa:
        return vm * p * p / (2 * pa)
    if p <= pb:
        return vm * (pa / 2 + p - pa)
    q = p - pb
    return vm * (pa / 2 + pb - pa + q - q * q / (2 * (1.0 - pb)))


def phase(f):
    """('hold', 0) | ('crumble', u 0..1) | ('gone', 0) | ('drip', u 0..1) at frame f (periodic)."""
    k = (f % vj.FRAMES) / vj.FPB
    if k < CRUMBLE[0]:
        return "hold", 0.0
    if k < CRUMBLE[1]:
        return "crumble", (k - CRUMBLE[0]) / (CRUMBLE[1] - CRUMBLE[0])
    if k < B - DRIP:
        return "gone", 0.0
    return "drip", (k - (B - DRIP)) / DRIP


def swell(f):
    k = (f % vj.FRAMES) / vj.FPB
    if k >= B - DRIP:
        return ((k - (B - DRIP)) / DRIP) ** 2
    return math.exp(-k / 1.5)


def ooze(f):
    """The slime's length 0..1: grows over beats 0.5..7 after the landing, holds, drains away in the crumble."""
    k = (f % vj.FRAMES) / vj.FPB
    if k < 0.5:
        return 0.0
    if k < 7.0:
        return vj.ease((k - 0.5) / 6.5)
    if k < CRUMBLE[0]:
        return 1.0
    if k < CRUMBLE[1]:
        return 1.0 - vj.ease((k - CRUMBLE[0]) / (CRUMBLE[1] - CRUMBLE[0]))
    return 0.0


def slime_level(f, dl):
    """A drip's length 0..1: it grows after the landing (delayed by dl beats), and EVERY drip drains away within
    0.8 beats of the crumble's start (a delayed drain left drips hanging in the air after the bones fell)."""
    k = (f % vj.FRAMES) / vj.FPB
    if k >= CRUMBLE[0]:
        return max(0.0, 1.0 - vj.ease((k - CRUMBLE[0]) / 0.8))
    if k < 0.5 + dl:
        return 0.0
    return vj.ease((k - 0.5 - dl) / 6.5)


def signals(f):
    c = vj.clock(f)
    held = 1.0 if phase(f)[0] == "hold" else 0.0
    bar0 = vj.BEAT_F[4 * c["bar"]]
    bar_u = (c["f"] - bar0) / (vj.BEAT_F[4 * c["bar"] + 4] - bar0)
    s = {"Kick": c["kick"] * held, "Swell": swell(f), "SweepX": -7.5 + 15.0 * bar_u,
         "SweepAmt": held * math.sin(math.pi * bar_u) ** 2}
    s.update(vj.loop_signals(f))
    return s


# ------------------------------------------------------------------ materials
def bone_mat():
    """Bone-white neon with a white-hot core line; per-object Object.color alpha = the bone's fade."""
    s = vj.Shader("Bones")
    _, alpha, _ = s.obj_info()
    x, _, _ = s.world_pos()
    sweep = s.mul(s.gauss(x, s.c("SweepX"), 1.1), s.c("SweepAmt"))
    lift = s.add(0.6, s.mul(s.c("Kick"), 0.2), s.mul(s.c("Swell"), 0.5), s.mul(sweep, 0.55))
    col = s.mix(s.mul(s.smooth(s.core(0.0, 1.0), 0.8, 1.0), 0.35), V["bone"], (1.0, 1.0, 1.0))
    col = s.mix(s.mul(sweep, 0.45), col, V["sweep"])
    return s.emit(col, s.mul(alpha, lift, s.core(), 0.62 * GAIN))


def slime_mat():
    s = vj.Shader("Slime")
    _, alpha, _ = s.obj_info()
    lift = s.add(0.75, s.mul(s.c("Kick"), 0.2))
    return s.emit(V["slime"], s.mul(alpha, lift, s.core(0.5, 1.3), 0.5 * GAIN))


def glow_mat():
    """A soft UV-purple glow behind the logo (additive), lifting with the swell."""
    s = vj.Shader("Backglow")
    x, _, z = s.obj_coords()
    r = s.length2(s.mul(x, 0.55), z)
    glow = s.mul(s.exp(s.mul(s.mul(r, r), -1.0 / (3.2 * 3.2))), s.inv(s.smooth(r, 4.5, 6.0)))
    lift = s.add(0.75, s.mul(s.c("Swell"), 0.4), s.mul(s.c("Kick"), 0.1))
    return s.additive(V["glow"], s.mul(glow, lift, 0.05 * GAIN))


def fog_mat():
    """Low purple ground fog drifting under the logo (4D noise walked round a circle: seamless)."""
    s = vj.Shader("Fog")
    x, _, z = s.obj_coords()
    v = s.vec(s.mul(x, 0.12), s.madd(z, 0.2, s.mul(s.c("LoopCos"), 0.3)), s.mul(s.c("LoopSin"), 0.3))
    n = s.noise4(v, s.mul(s.c("LoopSin"), 0.25), scale=1.2, detail=4.0, rough=0.55)
    wisp = s.smooth(n, 0.48, 0.78)
    low = s.inv(s.smooth(z, -1.0, 1.6))
    return s.additive(V["glow"], s.mul(wisp, low, 0.06 * GAIN))


# ------------------------------------------------------------------ geometry
def bone_bm(pts, r):
    """A neon bone: a tube along the stroke with a knob at each end, centred on its own middle (it tumbles about it)."""
    bm = bmesh.new()
    dense = g.resample(pts, r * 2.0)
    c = sum(dense, Vector()) / len(dense)
    vj.tube(bm, [p - c for p in dense], lambda u: r, segs=10)
    for p in (dense[0], dense[-1]):
        bmesh.ops.create_icosphere(bm, subdivisions=2, radius=r * 1.7, matrix=Matrix.Translation(p - c))
    return bm, c


def word_strokes(text, height, base_z, track):
    out = []
    for _, strokes in letters.layout(text, height, track=track):
        out += [g.xz(st, 0.0, offset=(0.0, base_z)) for st in strokes]
    return out


def slime_bm(length, r):
    """A drip hanging down from its top (the origin): a thin tube narrowing, a drop at the end."""
    bm = bmesh.new()
    pts = [Vector((0.0, 0.0, -length * i / 8)) for i in range(9)]
    vj.tube(bm, pts, lambda u: r * (1.0 - 0.45 * u), segs=8)
    bmesh.ops.create_icosphere(bm, subdivisions=2, radius=r * 1.5, matrix=Matrix.Translation((0.0, 0.0, -length)))
    return bm


# ------------------------------------------------------------------ scene
def build():
    scene = vj.reset_scene()
    vj.clock_from(signals)
    ext = vj.EXT
    rnd = random.Random(13)
    bone_m, slime_m = bone_mat(), slime_mat()
    top = word_strokes("GRAVEYARD", 1.55, 0.35, 0.22)
    bot = word_strokes("SHIFT", 1.25, -1.6, 0.32)
    feet = []                                                        # the letters' feet on the baseline (slime hangs)
    bases = {id(p): 0.35 for p in top}
    bases.update({id(p): -1.6 for p in bot})
    for i, (pts, r) in enumerate([(p, R_TOP) for p in top] + [(p, R_BOT) for p in bot]):
        bm, home = bone_bm(pts, r)
        ob = vj.new_obj(f"Bone{i:02d}", bm, bone_m)
        fall = Vector((rnd.uniform(-1.2, 1.2), rnd.uniform(-1.5, 1.0), -rnd.uniform(4.5, 7.5)))
        rot_c = Vector((rnd.uniform(-1, 1), rnd.uniform(-1, 1), rnd.uniform(-1, 1))) * 2.2
        drop = rnd.uniform(5.5, 9.0)
        lag = rnd.uniform(0.0, 3.5)                                  # frames: a ragged drip, a clean landing
        keys_l, keys_r, keys_c = [], [], []
        for f in ext:
            ph, u = phase(f)
            if ph == "drip":
                u = min(1.0, max(0.0, u - lag * (1.0 - u) / (DRIP * vj.FPB)))   # late ones catch up and land on time
                p = fly_in(u)
                loc = home + Vector((0.0, 0.0, drop * (1.0 - p)))
                rot = Euler(tuple(rot_c * 0.35 * (1.0 - p)))
                a = vj.ease(min(1.0, u / 0.3))
            elif ph == "crumble":
                uu = max(0.0, u - lag / ((CRUMBLE[1] - CRUMBLE[0]) * vj.FPB))
                loc = home + fall * uu * uu
                rot = Euler(tuple(rot_c * uu))
                a = 1.0 - vj.ease(min(1.0, max(0.0, (uu - 0.3) / 0.55)))       # gone before it resets above
            elif ph == "gone":
                loc, rot, a = home + Vector((0.0, 0.0, drop)), Euler(tuple(rot_c * 0.35)), 0.0
            else:
                loc, rot, a = home, Euler((0.0, 0.0, 0.0)), 1.0
            keys_l.append((f, tuple(loc)))
            keys_r.append((f, tuple(rot)))
            keys_c.append((f, (1.0, 1.0, 1.0, a)))
        ob.rotation_mode = "XYZ"
        vj.keyed(ob, "location", keys_l)
        vj.keyed(ob, "rotation_euler", keys_r)
        vj.keyed(ob, "color", keys_c)
        low = min(pts, key=lambda q: q.z)
        if low.z < bases[id(pts)] + 0.08:
            feet.append((low, r))

    feet.sort(key=lambda q: q[0].x)
    picks = feet[::2]                                                # every other foot gets a drip
    for j, (p, r) in enumerate(picks):
        ln = rnd.uniform(0.35, 0.95)
        ob = vj.new_obj(f"Slime{j:02d}", slime_bm(ln, r * 0.55), slime_m)
        ob.location = p + Vector((0.0, -0.02, -r * 0.6))
        dl = rnd.uniform(0.0, 1.5)
        keys_s, keys_c = [], []
        for f in ext:
            o = slime_level(f, dl)
            keys_s.append((f, (1.0, 1.0, max(o, 0.001))))
            keys_c.append((f, (1.0, 1.0, 1.0, min(1.0, o * 3.0))))
        vj.keyed(ob, "scale", keys_s)
        vj.keyed(ob, "color", keys_c)

    glow = vj.new_obj("Backglow", vj.quad_bm(26.0, 12.0), glow_mat())
    glow.location = (0.0, 2.5, AIM_Z)
    fog = vj.new_obj("Fog", vj.quad_bm(30.0, 6.0), fog_mat())
    fog.location = (0.0, -1.0, -2.6)

    cam = vj.camera(scene, lens=40.0, clip=(0.5, 200.0))
    loc, rot = [], []
    for f in ext:
        a = 2 * math.pi * f / vj.FRAMES
        thump = 0.05 * vj.jolt(f, decay=3.0, period=5.0, delay=1) * (1.0 if phase(f)[0] == "hold" else 0.0)
        p = Vector((0.5 * math.sin(a), -CAM_D, AIM_Z + 0.25 * math.sin(2 * a + 0.4) + thump))
        loc.append((f, tuple(p)))
        rot.append((f, tuple(vj.look_at(p, (0.0, 0.0, AIM_Z), roll=0.6 * math.sin(a + 0.9)))))
    vj.keyed(cam, "location", loc)
    vj.keyed(cam, "rotation_euler", rot)
    return scene


scene = build()
vj.standard_render(scene)
vj.finish(scene, f"sting_{VNAME}")
