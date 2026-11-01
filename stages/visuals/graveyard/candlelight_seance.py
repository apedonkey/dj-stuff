"""CANDLELIGHT SEANCE - GRAVEYARD SHIFT VJ loop (breakdown). 8 bars, seamless, 1920x1080 @ 30 fps; tempo from vjkit
(140 BPM half-time = 411 frames).

A spirit board lies on a black table in a ring of twelve candles, seen from above at a low angle. Its letters, YES/NO,
the digits and GOOD BYE are our own neon stroke letterforms (letters.py), bone white on UV-purple border lines.
  Candles   the flames breathe on the half-time accents (the kick and the snare): a 3-frame swell, a soft decay, a
            slow flicker of their own; a warm halo around each.
  Planchette  glides over the board and spells B-O-O on bar 1 (a letter per beat: it rests on each, then glides to the
            next, arriving on the beat), wanders through bars 2-4, spells R-I-P on bar 5, and drifts back to B for the
            next downbeat. Each letter it rests on swells from bone white to candle orange and fades over a beat.
  Mist      faint purple smoke drifts over the board.
No strobing: the flames breathe (no hits), the letters swell over 4 frames and fade, the camera only sways.

  blender.exe -b --factory-startup --python candlelight_seance.py -- --frames 0,13,26,206,230 [--pct 50]
  blender.exe -b --factory-startup --python candlelight_seance.py -- --all --seam DIR [--out DIR] [--mblur]
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
import letters  # noqa: E402
from vjkit import BONE, EMBER, FLAME, UVP  # noqa: E402

VARIANTS = {
    "candle": dict(line=UVP, letter=(0.78, 0.74, 0.64), chosen=FLAME, flame=FLAME, halo=EMBER),
}
VNAME, V = vj.variant(VARIANTS)
GAIN = float(vj.arg("--gain", 1.0))
LH = 0.72                                        # letter height (m)
# (beat, target): the planchette arrives on these beats; letters spell BOO (bar 1) and RIP (bar 5)
SPELL = [(0, "B"), (1, "O"), (2, "O"), (16, "R"), (17, "I"), (18, "P")]
WANDER = [(5, (-2.6, -0.4)), (9, (2.4, 0.5)), (13, (0.6, -1.9)), (21, (3.2, -0.9)), (25, (-1.8, -1.6)),
          (29, (-3.4, 1.2))]                     # board-local (x, z) rest points between the words


# ------------------------------------------------------------------ the board's layout (board-local x, z; z = up the board)
def arc_slots(chars, cz, radius, a0, a1):
    """[(char, (x, z) of the letter's base centre, rotation in degrees)] along a circle arc (a0 > a1: left to right)."""
    out = []
    for i, ch in enumerate(chars):
        a = math.radians(a0 + (a1 - a0) * i / (len(chars) - 1))
        out.append((ch, (radius * math.cos(a), cz + radius * math.sin(a)), math.degrees(a) - 90.0))
    return out


TOP = arc_slots("ABCDEFGHIJKLM", -8.4, 11.2, 120.0, 60.0)
BOT = arc_slots("NOPQRSTUVWXYZ", -9.9, 11.2, 120.0, 60.0)
SLOTS = {ch: (p, rot) for ch, p, rot in TOP + BOT}


def letter_target(ch):
    """Where the planchette's window centre sits to frame a letter (its middle)."""
    (x, z), rot = SLOTS[ch]
    a = math.radians(rot + 90.0)
    return (x + math.cos(a) * LH * 0.5, z + math.sin(a) * LH * 0.5)


# ------------------------------------------------------------------ choreography
def schedule():
    pts = [(k, letter_target(ch)) for k, ch in SPELL] + list(WANDER)
    pts.sort()
    return pts + [(vj.BEATS + pts[0][0], pts[0][1])]           # back to B for the next downbeat


SCHED = schedule()


def planchette_pos(f):
    """Board-local (x, z) at frame f: rests 30% of each interval on its point, then eases to the next, arriving on
    the next point's beat. The O-O double letter circles once in place (the board's classic double)."""
    b = vj.beatpos(f % vj.FRAMES)
    for (k0, p0), (k1, p1) in zip(SCHED, SCHED[1:]):
        if k0 <= b < k1:
            u = (b - k0) / (k1 - k0)
            m = 0.0 if u < 0.3 else vj.ease((u - 0.3) / 0.7)
            x, z = p0[0] + (p1[0] - p0[0]) * m, p0[1] + (p1[1] - p0[1]) * m
            if p0 == p1:                                         # the same letter twice: a small loop
                a = 2 * math.pi * m
                x, z = x + 0.32 * math.sin(a), z + 0.32 * (1.0 - math.cos(a)) * 0.5
            return x, z
    return SCHED[0][1]


def spell_glow(ch, f):
    """0..1: the letter swells when the planchette arrives on it (4-frame attack), fading over 1.5 beats."""
    v = 0.0
    for k, c in SPELL:
        if c != ch:
            continue
        t = (f - vj.BEAT_F[k]) % vj.FRAMES
        v = max(v, min(1.0, t / 4.0) * math.exp(-t / (1.5 * vj.FPB)) if t < 6 * vj.FPB else 0.0)
    return v


def breath(f):
    """The flames' breath: per accent a 3-frame swell and a soft decay (kick 1.0, snare 0.85), periodic."""
    v = 0.0
    for af, amp in vj.accent_frames():
        t = (f - af) % vj.FRAMES
        if t < 4 * vj.FPB:
            v += amp * min(1.0, t / 3.0) * math.exp(-t / 9.0)
    return v


def signals(f):
    s = {"Breath": breath(f)}
    s.update(vj.loop_signals(f))
    return s


# ------------------------------------------------------------------ materials
def line_mat(col, base):
    s = vj.Shader("Lines")
    lift = s.add(0.85, s.mul(s.c("Breath"), 0.06))
    return s.emit(col, s.mul(lift, s.core(0.5, 1.3), base * GAIN))


def letter_mat():
    """Per-object Object.color: RGB = the letter's colour now, alpha = its brightness."""
    s = vj.Shader("Letters")
    col, alpha, _ = s.obj_info()
    return s.emit(col, s.mul(alpha, s.core(0.5, 1.35), 1.0 * GAIN))


def wax_mat():
    s = vj.Shader("Wax")
    lift = s.add(0.8, s.mul(s.c("Breath"), 0.15))
    return s.emit(BONE, s.mul(lift, s.core(0.35, 1.0), 0.32 * GAIN))


def flame_mat():
    """Per-object alpha = the flame's own flicker x the breath (keyed); a hot core, soft edges, additive."""
    s = vj.Shader("Flame")
    _, alpha, _ = s.obj_info()
    return s.additive(V["flame"], s.mul(alpha, s.core(0.35, 1.6), 1.25 * GAIN))


def halo_mat():
    s = vj.Shader("Halo")
    _, alpha, _ = s.obj_info()
    x, _, z = s.obj_coords()
    r = s.length2(x, z)
    glow = s.exp(s.mul(s.mul(r, r), -1.0 / (0.55 * 0.55)))
    return s.additive(V["halo"], s.mul(glow, alpha, 0.11 * GAIN))


def lens_mat():
    """The planchette's window: a faint warm glow inside the ring (additive), brighter while it rests on a letter."""
    s = vj.Shader("Lens")
    _, alpha, _ = s.obj_info()
    x, _, z = s.obj_coords()
    r = s.length2(x, z)
    glow = s.mul(s.exp(s.mul(s.mul(r, r), -1.0 / (0.3 * 0.3))), s.inv(s.smooth(r, 0.42, 0.5)))
    return s.additive(V["chosen"], s.mul(glow, alpha, 0.16 * GAIN))


def mist_mat():
    s = vj.Shader("Mist")
    x, y, z = s.obj_coords()
    v = s.vec(s.mul(x, 0.13), s.madd(z, 0.15, s.mul(s.c("LoopCos"), 0.4)), s.mul(s.c("LoopSin"), 0.4))
    n = s.noise4(v, s.mul(s.c("LoopSin"), 0.3), scale=1.1, detail=4.0, rough=0.55)
    wisp = s.smooth(n, 0.5, 0.8)
    return s.additive(V["line"], s.mul(wisp, 0.05 * GAIN))


# ------------------------------------------------------------------ geometry (board-local XZ plane; a root lays it flat)
def rounded_rect(w, h, r, n=8):
    pts = []
    for cx, cz, a0 in ((w / 2 - r, h / 2 - r, 0), (-w / 2 + r, h / 2 - r, 90), (-w / 2 + r, -h / 2 + r, 180),
                       (w / 2 - r, -h / 2 + r, 270)):
        pts += [(cx + r * math.cos(math.radians(a0 + 90 * i / n)), cz + r * math.sin(math.radians(a0 + 90 * i / n)))
                for i in range(n + 1)]
    return pts


def board_lines_bm():
    bm = bmesh.new()
    g.stroke(bm, g.xz(rounded_rect(14.4, 9.4, 0.9)), 0.045, segs=8, closed=True, joints=False)
    g.stroke(bm, g.xz(rounded_rect(13.7, 8.7, 0.7)), 0.025, segs=6, closed=True, joints=False)
    for sx in (-1, 1):                                               # a sun (left) and a crescent moon (right)
        cx, cz = sx * 5.9, 3.55
        if sx < 0:
            g.stroke(bm, g.xz(g.circle2(0.42, 32, cx, cz)), 0.03, segs=6, closed=True, joints=False)
            for i in range(10):
                a = 2 * math.pi * i / 10
                g.stroke(bm, g.xz([(cx + 0.58 * math.cos(a), cz + 0.58 * math.sin(a)),
                                   (cx + 0.85 * math.cos(a), cz + 0.85 * math.sin(a))]), 0.022, segs=6)
        else:
            outer = [(cx + 0.6 * math.cos(math.radians(a)), cz + 0.6 * math.sin(math.radians(a)))
                     for a in range(-120, 121, 12)]
            inner = [(cx + 0.28 + 0.45 * math.cos(math.radians(a)), cz + 0.45 * math.sin(math.radians(a)))
                     for a in range(110, -111, -12)]
            g.stroke(bm, g.xz(outer + inner), 0.03, segs=6, closed=True)
    return bm


def text_strokes(text, height, x, z, rot=0.0, track=0.22):
    out = []
    for _, strokes in letters.layout(text, height, track=track):
        for st in strokes:
            out.append(g.rot2([(px + x, pz + z) for px, pz in st], rot, center=(x, z)))
    return out


def letter_bm(strokes, r=0.03):
    bm = bmesh.new()
    for st in strokes:
        g.stroke(bm, g.xz(st), r, segs=6)
    return bm


def planchette_bm():
    """A teardrop pointer around a round window (the window centre at the origin, the point toward +z)."""
    bm = bmesh.new()
    half = [(0.0, -0.95), (0.55, -0.82), (0.88, -0.45), (0.95, 0.0), (0.78, 0.45), (0.42, 0.95), (0.0, 1.45)]
    g.stroke(bm, g.xz(g.mirrored(half)), 0.04, segs=8, closed=True)
    g.stroke(bm, g.xz(g.circle2(0.5, 40)), 0.035, segs=8, closed=True, joints=False)
    for sx in (-1, 1):                                               # its three felt feet as small rings
        g.stroke(bm, g.xz(g.circle2(0.1, 12, sx * 0.62, -0.62)), 0.02, segs=6, closed=True, joints=False)
    g.stroke(bm, g.xz(g.circle2(0.1, 12, 0.0, 1.05)), 0.02, segs=6, closed=True, joints=False)
    return bm


def flame_bm():
    """A teardrop flame standing on its wick at the origin (up = +Z), two crossed cards' worth of volume."""
    bm = bmesh.new()
    prof = [(0.0, 0.0), (0.06, 0.04), (0.09, 0.12), (0.085, 0.22), (0.06, 0.32), (0.03, 0.42), (0.0, 0.5)]
    n = 12
    rings = []
    for r, z in prof:
        rings.append([bm.verts.new((r * math.cos(2 * math.pi * i / n), r * math.sin(2 * math.pi * i / n), z))
                      for i in range(n)])
    for a, b in zip(rings, rings[1:]):
        for i in range(n):
            j = (i + 1) % n
            if a[i] is a[j]:
                continue
            bm.faces.new((a[i], a[j], b[j], b[i]))
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-5)
    return bm


# ------------------------------------------------------------------ scene
def build():
    scene = vj.reset_scene()
    vj.clock_from(signals)
    ext = vj.EXT
    rnd = random.Random(21)
    root = vj.new_empty("Board")
    root.rotation_euler = (math.radians(-90.0), 0.0, 0.0)           # board-local (x, 0, z) -> world (x, z, 0): flat

    vj.new_obj("BoardLines", board_lines_bm(), line_mat(V["line"], 0.55), root)
    lm = letter_mat()
    glyphs = {}
    for ch, (x, z), rot in TOP + BOT:
        ob = vj.new_obj(f"L_{ch}", letter_bm(text_strokes(ch, LH, x, z, rot)), lm, root)
        glyphs[ch] = ob
    for text, x, z, h in (("YES", -4.1, 3.3, 0.62), ("NO", 4.1, 3.3, 0.62), ("1234567890", 0.0, -2.35, 0.55),
                          ("GOOD BYE", 0.0, -3.75, 0.58)):
        ob = vj.new_obj(f"T_{text}", letter_bm(text_strokes(text, h, x, z, 0.0, track=0.3), 0.026), lm, root)
        ob.color = (*V["letter"], 0.5)
    for ch, ob in glyphs.items():
        keys = []
        for f in ext:
            s = spell_glow(ch, f)
            col = tuple(V["letter"][i] + (V["chosen"][i] - V["letter"][i]) * s for i in range(3))
            keys.append((f, (*col, 0.55 + 0.75 * s)))
        vj.keyed(ob, "color", keys)

    pl = vj.new_obj("Planchette", planchette_bm(), line_mat(BONE, 1.15), root)
    lens = vj.new_obj("PlanchetteLens", vj.disc_bm(0.5, 32), lens_mat(), pl)
    lens.location = (0.0, -0.01, 0.0)
    keys_l, keys_r, keys_c = [], [], []
    for f in ext:
        x, z = planchette_pos(f)
        x2, z2 = planchette_pos(f + 3)                                # it turns a little toward where it goes
        yaw = max(-0.35, min(0.35, math.atan2(-(x2 - x), (z2 - z) + 1e-6) * 0.25)) if (x2, z2) != (x, z) else 0.0
        keys_l.append((f, (x, -0.06, z)))                             # the window (its origin) over the letter
        keys_r.append((f, (0.0, yaw, 0.0)))
        rest = max(spell_glow(c, f) for c in "BOPRI")
        keys_c.append((f, (1.0, 1.0, 1.0, 0.35 + 0.65 * rest)))
    vj.keyed(pl, "location", keys_l)
    vj.keyed(pl, "rotation_euler", keys_r)
    vj.keyed(lens, "color", keys_c)

    wm, fm, hm = wax_mat(), flame_mat(), halo_mat()
    flame_me = vj.finish_bm(flame_bm(), name="FlameMesh")
    for i in range(12):
        a = 2 * math.pi * (i + 0.5) / 12
        x, y = 8.3 * math.cos(a), 5.9 * math.sin(a) + 0.3
        h = rnd.uniform(0.7, 1.5)
        bm = bmesh.new()
        vj.tube(bm, [Vector((x, y, 0.0)), Vector((x, y, h))], lambda u: 0.17, segs=14)
        for k in range(3):                                            # wax drips down the side
            da = rnd.uniform(0, 2 * math.pi)
            p0 = Vector((x + 0.17 * math.cos(da), y + 0.17 * math.sin(da), h))
            vj.tube(bm, [p0, p0 - Vector((0, 0, rnd.uniform(0.15, 0.45)))], lambda u: 0.035 * (1 - 0.5 * u), segs=6)
        vj.new_obj(f"Candle{i}", bm, wm)
        fl = vj.mesh_obj(f"Flame{i}", flame_me, fm)
        fl.location = (x, y, h + 0.04)
        halo = vj.new_obj(f"Halo{i}", vj.disc_bm(1.0, 32, axis="Y"), hm)
        halo.location = (x, y - 0.05, h + 0.3)
        ph, sp = rnd.uniform(0, 2 * math.pi), rnd.choice((2, 3))
        keys_s, keys_c, keys_h = [], [], []
        for f in ext:
            b = breath(f)
            fk = 0.9 + 0.1 * math.sin(2 * math.pi * sp * f / vj.FRAMES + ph)   # its own slow flicker (periodic)
            sc = (0.9 + 0.12 * b) * fk
            keys_s.append((f, (sc, sc, (0.85 + 0.35 * b) * fk)))
            keys_c.append((f, (1.0, 1.0, 1.0, (0.75 + 0.3 * b) * fk)))
            keys_h.append((f, (1.0, 1.0, 1.0, (0.7 + 0.35 * b) * fk)))
        vj.keyed(fl, "scale", keys_s)
        vj.keyed(fl, "color", keys_c)
        vj.keyed(halo, "color", keys_h)

    mist = vj.new_obj("Mist", vj.quad_bm(24.0, 16.0), mist_mat())
    mist.rotation_euler = (math.radians(-90.0), 0.0, 0.0)
    mist.location = (0.0, 0.0, 0.6)

    cam = vj.camera(scene, lens=35.0, clip=(0.5, 200.0))
    loc, rot = [], []
    for f in ext:
        a = 2 * math.pi * f / vj.FRAMES
        p = Vector((1.6 * math.sin(a), -14.2 + 0.45 * math.cos(2 * a), 10.85 + 0.3 * math.sin(a + 0.6)))   # the whole board
        loc.append((f, tuple(p)))
        rot.append((f, tuple(vj.look_at(p, (0.0, 0.6, 0.0), roll=0.7 * math.sin(a + 1.1)))))
    vj.keyed(cam, "location", loc)
    vj.keyed(cam, "rotation_euler", rot)
    return scene


scene = build()
vj.standard_render(scene)
vj.finish(scene, f"candlelight_seance_{VNAME}")
