"""HAZARD TYPE - REACTOR VJ loop. 8 bars, seamless, 1920x1080 @ 30 fps; tempo from vjkit (140 BPM half-time = 411
frames).

Kinetic type in layers, all of it monoline neon line work (letters.py strokes cut into stencil letters with bridges,
chevrons and stripes as outlines; no full-frame fills).
  Words    one big stencil word per bar on a carousel: each word brakes into place exactly on its bar's downbeat (a
           camera thump a frame later), REACTOR, CORE, CAUTION, CRITICAL, then SCRAM lands the drop.
  Tapes    two hazard-chevron tapes frame the word and ratchet a chevron along on every accent (half-time: the kick
           and the snare), the upper one right, the lower one left.
  Back     rows of small type scroll steadily behind them (one row length per loop).
  Drop     section B (bar 5's downbeat): the type plane tilts into the hit, caution tapes slide in across two corners
           (stripes ratcheting on the accents) and the palette lands on the hit; it all eases back over the last fill.
Variants (palette / camera / density): amber (flat, front on), red (a low three-quarter view: the type in
perspective), blue (a third tape and denser back rows, a slow roll).
No strobing: nothing blinks; every change is a slide, and the brightness only swells into the section hits.

  blender.exe -b --factory-startup --python hazard_type.py -- --variant amber --frames 0,40,206,240 [--pct 50]
  blender.exe -b --factory-startup --python hazard_type.py -- --variant amber --all --seam DIR [--out DIR]
"""
import math
import os
import sys

import bmesh
import bpy
from mathutils import Vector

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import vjkit as vj  # noqa: E402
import letters  # noqa: E402
import rx_science as rx  # noqa: E402
from vjkit import ALARM, AMBER, CHERENKOV, COOLANT, HOT, PLASMA, STEEL, UVP  # noqa: E402

# word colours (A, B); chevrons; rails; back rows; corner tapes; extra tape; camera: (position, aim, lens, roll deg)
VARIANTS = {
    "amber": dict(word=(AMBER, ALARM), chevron=AMBER, rail=STEEL, back=AMBER, corner=ALARM, third=False,
                  word_gain=1.0, cam=((0.0, -22.2, 0.0), (0.0, 0.0, 0.0), 50.0, 0.0)),
    "red": dict(word=(ALARM, HOT), chevron=AMBER, rail=STEEL, back=ALARM, corner=AMBER, third=False,
                word_gain=1.15, cam=((-6.5, -19.5, -4.2), (0.3, 0.0, 0.25), 45.0, 0.0)),
    "blue": dict(word=(CHERENKOV, UVP), chevron=COOLANT, rail=UVP, back=CHERENKOV, corner=PLASMA, third=True,
                 word_gain=1.2, cam=((0.0, -22.2, 0.0), (0.0, 0.0, 0.0), 50.0, 2.5)),
}
VNAME, V = vj.variant(VARIANTS)
GAIN = float(vj.arg("--gain", 1.0))

WORDS = ["REACTOR", "CORE", "CAUTION", "CRITICAL", "SCRAM", "CONTAINMENT", "CRITICAL", "SCRAM"]
SLOT = 18.0                                    # carousel spacing (the frame is 16 units wide at the type plane)
W_MAX, H_MAX = 13.0, 2.4                       # a word's largest width / height (units; 1 unit = 120 px)
TRACK = 0.3
WORD_R = 0.06                                  # stroke radius of the big words
SLIDE = 0.75                                   # beats a word takes to slide in (it arrives on the downbeat)
PITCH = 1.0                                    # chevron spacing
TAPES = [(2.4, 1, 6), (-2.4, -1, 6)] + ([(3.75, 1, 10)] if V["third"] else [])   # (height, direction, drift/loop)
BACK_ROWS = ["REACTOR  CORE 04  CAUTION  ROD 12  CONTAINMENT  SCRAM  CRITICAL  COOLANT  ",
             "SCRAM  CORE TEMP  CRITICAL  REACTOR  CAUTION  CONTAINMENT  ROD 07  "]
TILT = -6.0                                    # degrees the type plane tilts in section B


# ------------------------------------------------------------------ timing
def ramp(b, b0, b1):
    return vj.ease((b - b0) / (b1 - b0))


def b_amount(f):
    """Section B's weight 0..1: in over the fill into bar 5, out over the last fill (0 at the seam)."""
    b = vj.beatpos(f % vj.FRAMES)
    return ramp(b, vj.HALF - 2, vj.HALF) * (1.0 - ramp(b, vj.BEATS - 2, vj.BEATS))


def corner_in(f):
    """The corner tapes: slide in over the beat before bar 5's downbeat, out over the beat before the seam."""
    b = vj.beatpos(f % vj.FRAMES)
    return ramp(b, vj.HALF - SLIDE, vj.HALF) * (1.0 - ramp(b, vj.BEATS - SLIDE, vj.BEATS))


def carousel(f):
    """The word strip's offset at any integer frame (unwrapped: SLOT per bar, BARS * SLOT per loop). Each slide eases
    in and brakes to rest on its bar's downbeat; the last one lands on the seam."""
    n, ff = divmod(f, vj.FRAMES)
    b = vj.beatpos(ff)
    x = 0.0
    for j in range(1, vj.BARS + 1):
        b1 = 4 * j
        if b >= b1:
            x += SLOT
        elif b > b1 - SLIDE:
            x += SLOT * vj.ease((b - (b1 - SLIDE)) / SLIDE)
    return (n * vj.BARS + 0.0) * SLOT + x


def ratchet(f, step, drift, attack=5.0):
    """A tape's offset at any integer frame (unwrapped, so keys never jump): a step per accent, eased out over
    `attack` frames, plus a steady drift per loop. Per loop: accents * step + drift, a whole number of PITCHes."""
    n, ff = divmod(f, vj.FRAMES)
    acc = vj.accent_frames()
    x = n * (len(acc) * step + drift) + drift * ff / vj.FRAMES
    for af, _ in acc:
        t = ff - af
        if t >= attack:
            x += step
        elif t >= 0:
            x += step * (1.0 - (1.0 - t / attack) ** 3)
    return x


def signals(f):
    c = vj.clock(f)
    s = {"Kick": c["kick"], "Swell": vj.swell(f), "Section": vj.section(f), "Bamt": b_amount(f)}
    s.update(vj.loop_signals(f))
    return s


# ------------------------------------------------------------------ materials
def neon_mat(name, cols, base, kick=0.12, swell=0.3):
    s = vj.Shader(name)
    lift = s.add(0.8, s.mul(s.c("Kick"), kick), s.mul(s.c("Swell"), swell))
    col = s.mix(s.c("Section"), *cols) if isinstance(cols[0], tuple) else cols
    return s.emit(col, s.mul(s.core(0.5, 1.35), lift, base * GAIN))


def fill_mat(name, col, base):
    s = vj.Shader(name)
    return s.emit(col, s.mul(s.add(0.8, s.mul(s.c("Kick"), 0.2), s.mul(s.c("Swell"), 0.2)), base * GAIN))


# ------------------------------------------------------------------ geometry (XZ planes; the camera looks +Y)
def strokes_bm(strokes2d, r, y=0.0, bm=None):
    bm = bm or bmesh.new()
    for st in strokes2d:
        rx.stroke(bm, rx.xz(st, y), r, segs=6)
    return bm


def word_strip_bm():
    """The carousel: WORDS (and enough repeats for the slides), centred on x = i * SLOT, middle on z = 0."""
    bm = bmesh.new()
    for i in range(-1, vj.BARS + 2):
        text = WORDS[i % len(WORDS)]
        h = min(H_MAX, W_MAX / letters.text_width(text, track=TRACK))
        strokes = rx.word_strokes(text, h, track=TRACK, gap=0.09, eps=0.04)
        strokes_bm([[(x + i * SLOT, z - h / 2) for x, z in st] for st in strokes], WORD_R * min(1.0, h / 2.0) ** 0.5,
                   bm=bm)
    return bm


def chevrons2d(direction, span, h=0.8, w=0.45, t=0.32):
    out = []
    for i in range(span[0], span[1]):
        pts = rx.chevron(w, h, t)
        if direction < 0:
            pts = [(-x, y) for x, y in pts]
        out.append([(x + i * PITCH, y - h / 2) for x, y in pts])
    return out


def tape(name, z, direction, drift, parent, length):
    """A chevron tape at height z: two rails (static) and chevrons (outlines and a dim fill) that ratchet along."""
    rails = [[(-40.0, z + 0.55), (40.0, z + 0.55)], [(-40.0, z - 0.55), (40.0, z - 0.55)]]
    vj.new_obj(f"{name}Rails", strokes_bm(rails, 0.022, y=0.05), neon_mat(f"{name}Rails", V["rail"], 0.55), parent)
    span = (-14 - length, 14 + 2) if direction > 0 else (-14, 14 + length)
    shapes = chevrons2d(direction, span)
    bm = bmesh.new()
    for pts in shapes:
        rx.stroke(bm, rx.xz([(x, y + z) for x, y in pts + pts[:1]]), 0.024, segs=6)
    lines = vj.new_obj(f"{name}Chevrons", bm, neon_mat(f"{name}Chevrons", V["chevron"], 0.95, kick=0.2), parent)
    bm = bmesh.new()
    for pts in shapes:
        rx.fill(bm, rx.xz([(x, y + z) for x, y in pts], y=0.04))
    fills = vj.new_obj(f"{name}Fill", bm, fill_mat(f"{name}Fill", V["chevron"], 0.09), parent)
    keys = [(f, (direction * ratchet(f, PITCH, drift * PITCH), 0.0, 0.0)) for f in vj.EXT]
    for ob in (lines, fills):
        vj.keyed(ob, "location", keys)


def stripe_tape_bm(length, h=0.9, w=0.5, gap=0.5, slant=0.45):
    """A caution tape along +x (centred on z = 0): rails and slanted stripe outlines (parallelograms) every w + gap."""
    bm = bmesh.new()
    rails = [[(-length, h / 2 + 0.12), (length, h / 2 + 0.12)], [(-length, -h / 2 - 0.12), (length, -h / 2 - 0.12)]]
    strokes_bm(rails, 0.02, bm=bm)
    n = int(length / (w + gap))
    for i in range(-n, n):
        x0 = i * (w + gap)
        pts = [(x0, -h / 2), (x0 + w, -h / 2), (x0 + w + slant, h / 2), (x0 + slant, h / 2)]
        rx.stroke(bm, rx.xz(pts + pts[:1]), 0.022, segs=6)
    return bm


# ------------------------------------------------------------------ scene
def build():
    scene = vj.reset_scene()
    vj.clock_from(signals)
    ext = vj.EXT
    main = vj.new_empty("TypePlane")
    vj.keyed(main, "rotation_euler", [(f, (0.0, math.radians(TILT) * b_amount(f), 0.0)) for f in ext])

    words = vj.new_obj("Words", word_strip_bm(), neon_mat("Words", V["word"], 1.15 * V["word_gain"], kick=0.1,
                                                          swell=0.35), main)
    vj.keyed(words, "location", [(f, (-carousel(f), 0.0, 0.0)) for f in ext])

    for i, (z, direction, drift) in enumerate(TAPES):
        tape(f"Tape{i}", z, direction, drift, main, len(vj.accent_frames()) + drift + 2)

    # back rows: small type, dim, scrolling one row length per loop (alternate directions), farther back; with a
    # third tape on top they all go below
    rows_z = (-5.05, -5.75) if V["third"] else (5.05, -5.05)
    for i, (text, zrow) in enumerate(zip(BACK_ROWS, rows_z)):
        h = 0.42
        width = rx.text_width(text, h, track=0.3) + 0.45 * h + 0.3 * h
        strokes = []
        for rep in range(-2, 3):
            strokes += [[(x + rep * width, z) for x, z in st]
                        for st in rx.word_strokes(text, h, track=0.3, gap=0.09, align="left")]
        ob = vj.new_obj(f"Back{i}", strokes_bm([[(x, z + zrow - h / 2) for x, z in st] for st in strokes], 0.02,
                                               y=8.0), neon_mat(f"Back{i}", V["back"], 0.3, kick=0.0, swell=0.2))
        sgn = 1 if i % 2 == 0 else -1
        vj.keyed(ob, "location", [(f, (-sgn * width * (f / vj.FRAMES) - width / 2, 0.0, 0.0)) for f in ext])

    # section B: caution tapes slide in across two corners (top left, bottom right), stripes ratcheting
    for i, (cx, cz, ang) in enumerate(((-6.6, 3.6, 32.0), (6.6, -3.6, 32.0))):
        holder = vj.new_empty(f"Corner{i}", main)
        holder.location = (cx, -0.4, cz)
        holder.rotation_euler = (0.0, math.radians(-ang), 0.0)
        ob = vj.new_obj(f"CornerTape{i}", stripe_tape_bm(24.0), neon_mat(f"CornerTape{i}", V["corner"], 0.85,
                                                                         kick=0.2), holder)
        out = 3.2 if i == 0 else -3.2                                  # slides along its normal, off the frame
        keys = []
        for f in ext:
            k = corner_in(f)
            keys.append((f, ((1 if i == 0 else -1) * ratchet(f, 1.0, 0.0), 0.0, out * (1.0 - k))))
        vj.keyed(ob, "location", keys)

    pos, aim, lens, roll = V["cam"]
    pos, aim = Vector(pos), Vector(aim)
    cam = vj.camera(scene, lens=lens, clip=(1.0, 200.0))
    loc, rot, lk = [], [], []
    for f in ext:
        a = 2 * math.pi * f / vj.FRAMES
        p = pos + Vector((0.18 * math.sin(a), 0.0, 0.12 * math.sin(2 * a + 0.6) + 0.07 * vj.jolt(f)))
        t = aim + Vector((0.08 * math.sin(a + 0.9), 0.0, 0.05 * math.sin(2 * a)))
        loc.append((f, tuple(p)))
        rot.append((f, tuple(vj.look_at(p, t, roll=roll * math.sin(a + 0.4) + 0.25 * math.sin(2 * a)))))
        lk.append((f, lens * (1.0 + 0.02 * vj.clock(f)["kick"])))
    vj.keyed(cam, "location", loc)
    vj.keyed(cam, "rotation_euler", rot)
    vj.keyed(cam.data, "lens", lk)
    return scene


scene = build()
vj.standard_render(scene)
vj.finish(scene, f"hazard_type_{VNAME}")
