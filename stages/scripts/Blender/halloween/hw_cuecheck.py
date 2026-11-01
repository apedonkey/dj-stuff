"""Comfort check for GRAVEYARD SHIFT's animated show (claudedocs/halloween_stage_plan.md 7.7; the user's rules of
2026-10-06: no strobes, at most 3 flashes per second anywhere, no one-frame hits, no full-frame white, on-beat at most
~1.6x mid-beat). Plain Python + numpy, no Blender:

    python hw_cuecheck.py [<Blender output dir, default out_hw>]        exit 1 if any rule FAILS

It reads what SHIPS (the cue table T_HwCues.png, the sky T_HwSky.png, hw_groups.json from that folder) and models,
frame by frame at 72 Hz over the 32-bar loop, what every animated material emits. The formulas mirror
Scripts/hw_materials.py (cue_level with its attack ramp, cue_level_smooth, strike_env, macro, show_lit, cue_tex,
beams_material, laser_sweep, lightning_sky, bolts, fog_sheet, fire_card, vat_crowd); the constants they use are READ
from that file, and the check stops if one it relies on has moved (the model would be stale).

Per output (normalised to its own peak over the loop):
  flashes  a flash = a rise and a fall, each >= 20% of the peak (hysteresis); the busiest 1-s window counts, <= 3
  attack   every strictly rising run that climbs >= 20% of the peak takes >= 3 frames (its 5-95% rise time / 0.9),
           and no single frame rises by >= 35% of the peak (a 3-frame attack climbs <= 1/3 a frame): a one-frame hit
Plus: the beat pulse's on-beat / mid-beat ratio <= 1.6, no strobe flags, the wash row never pulses, the sky's display
luma at a full strike in the storm's peak <= 35% (plan 7.3), fire <= 0.5 bursts per second. The storm is modelled at
its 16-minute peak (macro = 1), the worst case.

v3 (2026-10-09): the set's floors (build_halloween.py), the crowd's floor and the fog's lighting (hw_materials.py) are
read from their sources. The lasers run on the Dino's engine (dino_materials.laser_show): modelled here as each group's
level from T_HwLaserCues (show.py's table: steps at the bar line, no ramp) x the engine's strongest beat pulse (0.2 + 0.8
x a per-beat decay). Thin lines, as on the Dino Stage: they are held to <= 3 flashes/s, and their steps and beat pulses
are reported but exempt from the attack and one-frame rules (the Dino's engine, unchanged). Drum-hit flashes come from
the songs' hit maps (at most one hit per beat: <= 2.3/s at 140 BPM) and are not modelled.
"""
import json
import math
import os
import re
import struct
import sys
import zlib

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import hw_show  # noqa: E402  (plain Python: the row map and the tempo)

SRC = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "out_hw")
MATS_PY = os.path.join(HERE, "..", "..", "hw_materials.py")
FPS = 72.0
FLASH_H = 0.20            # a transition is a move of >= 20% of the output's peak
MIN_ATTACK_FRAMES = 3


# ---------------------------------------------------------------- the materials' constants, read from their source
_src = open(MATS_PY, encoding="utf-8").read()


def _num(pattern, what):
    m = re.search(pattern, _src, re.M)
    if not m:
        sys.exit(f"[CUECHECK] STALE MODEL: {what} not found in hw_materials.py ({pattern}); update hw_cuecheck.py")
    return float(m.group(1))


ATTACK_S = _num(r"^ATTACK_S = ([0-9.]+)", "ATTACK_S")
STRIKE_BUMP = _num(r"^STRIKE_BUMP = ([0-9.]+)", "STRIKE_BUMP")
SKY_GAIN = _num(r"def lightning_sky\(name, folder, default_tex, cues, gain=([0-9.]+)\)", "lightning_sky gain")
BEAMS_LO = _num(r"lvl = g\.mul\(g\.wave01\(ph, ([0-9.]+), 1\.0\), cue_level\(g, cues, g\.param\(\"CueRow\"", "beam breath")
FIRE_LO = _num(r"lick = g\.wave01\(g\.add\(g\.time\(6\.0\), g\.mul\(g\.world\(\"x\"\), k=0\.01\)\), ([0-9.]+), 1\.0\)", "fire lick")
GLOW_LO = _num(r"lvl = g\.wave01\(show_time\(g, HALF_HZ\), ([0-9.]+), 1\.0\)", "crowd glow breath")
CROWD_FLOOR = _num(r"show_light\(g, cues, floor=([0-9.]+), sweep=1\.0\)", "crowd floor")
# v7: lit = level x (1 - lit_floor) + lit_floor, lit_floor passed by build_halloween.py (the material's default else)
_fog = re.search(r"lit = g\.add\(g\.mul\(cue_level\(g, cues, g\.const\(WASH_ROW\)\), k=1\.0 - lit_floor\), k=lit_floor\)", _src)
_fog_def = re.search(r"def fog_sheet\(.*?lit_floor=([0-9.]+)\)", _src)
if not (_fog and _fog_def):
    sys.exit("[CUECHECK] STALE MODEL: the fog's lighting not found in hw_materials.py; update hw_cuecheck.py")
_bh = open(os.path.join(HERE, "..", "..", "build_halloween.py"), encoding="utf-8").read()
_fog_call = re.search(r"hm\.fog_sheet\(.*?lit_floor=([0-9.]+)\)", _bh, re.S)
FOG_0 = float(_fog_call.group(1) if _fog_call else _fog_def.group(1))
FOG_K = 1.0 - FOG_0
_bsrc = open(os.path.join(HERE, "..", "..", "build_halloween.py"), encoding="utf-8").read()


def _floor(sm, tex):
    m = re.search(r'\("%s", "%s", ([0-9.]+)\)' % (sm, tex), _bsrc)
    if not m:
        sys.exit(f"[CUECHECK] STALE MODEL: {sm}'s floor not found in build_halloween.py; update hw_cuecheck.py")
    return float(m.group(1))


SET_FLOOR, DECK_FLOOR = _floor("SM_HwFacade", "T_HwFacade"), _floor("SM_HwDeck", "T_HwDeck")
for needle in ("env = g.add(g.mul(g.mul(g.mul(inv, inv), patt), k=0.4), k=0.6)",   # 0.6 + 0.4 (1 - ph)^2 x the ramp
               "patt = g.sat(g.mul(ph, k=1.0 / (HALF_HZ * ATTACK_S)))",
               "g.link(g.mul(lvl, strike_env(g)), op, \"B\")",                     # bolts: opacity = storm x strike
               "att = g.sat(g.mul(d, k=1.0 / 0.05))", "dec = g.sat(g.add(g.mul(d, k=-1.0 / 0.45), k=1.0 + 0.05 / 0.45))",
               "bx = g.sat(g.mul(g.add(fb, k=-0.85), k=1.0 / 0.15))", "BEAT_HZ = 140.0 / 60.0", "MACRO_S = 960.0",
               "prv = g.frac(g.mul(g.add(bar, k=31.0), k=1.0 / 32.0))",
               "puf = g.lerp(_ch(g, psmp, \"B\"), _ch(g, smp, \"B\"), ramp)"):
    if needle not in _src:
        sys.exit(f"[CUECHECK] STALE MODEL: hw_materials.py no longer has `{needle}`; update hw_cuecheck.py")
BEAT_HZ = hw_show.SHOW_BPM / 60.0
HALF_HZ = BEAT_HZ / 2
BAR_S = 4.0 / BEAT_HZ
LOOP_S = hw_show.SHOW_BARS * BAR_S
R = hw_show.CUE_ROWS


# ---------------------------------------------------------------- what ships
def read_png(path):
    """8-bit RGB/RGBA PNG with filter-0 rows (what hw_stage.write_png and hw_show.write_png_linear write)."""
    data = open(path, "rb").read()
    if data[:8] != b"\x89PNG\r\n\x1a\n":
        raise ValueError(path + ": not a PNG")
    pos, idat, hdr = 8, b"", None
    while pos < len(data):
        n, tag = struct.unpack(">I4s", data[pos:pos + 8])
        body = data[pos + 8:pos + 8 + n]
        pos += 12 + n
        if tag == b"IHDR":
            hdr = struct.unpack(">IIBBBBB", body)
        elif tag == b"IDAT":
            idat += body
        elif tag == b"IEND":
            break
    w, h, depth, ctype = hdr[0], hdr[1], hdr[2], hdr[3]
    if depth != 8 or ctype not in (2, 6):
        raise ValueError(f"{path}: bit depth {depth}, colour type {ctype} (expected 8-bit RGB/RGBA)")
    ch = 3 if ctype == 2 else 4
    raw = np.frombuffer(zlib.decompress(idat), np.uint8).reshape(h, 1 + w * ch)
    if raw[:, 0].any():
        raise ValueError(path + ": filtered rows (our writers use filter 0 only)")
    return raw[:, 1:].reshape(h, w, ch).astype(np.float64) / 255.0


CUES = read_png(os.path.join(SRC, "T_HwCues.png"))            # [row, bar, (level, strobe, pulse)]
GROUPS = json.load(open(os.path.join(SRC, "hw_groups.json"))) if os.path.exists(os.path.join(SRC, "hw_groups.json")) else {}
t = np.arange(0.0, LOOP_S, 1.0 / FPS)
barf = (t / LOOP_S % 1.0) * hw_show.SHOW_BARS
bar = np.floor(barf).astype(int)
fb = barf - bar


def wave01(x, lo, hi):
    return (hi + lo) / 2 + (hi - lo) / 2 * np.sin(2 * math.pi * x)


def cue_level(row):
    cur, prv = CUES[row, bar % 32], CUES[row, (bar - 1) % 32]
    ramp = np.clip(fb * BAR_S / ATTACK_S, 0.0, 1.0)
    lvl = prv[:, 0] + (cur[:, 0] - prv[:, 0]) * ramp
    puf = prv[:, 2] + (cur[:, 2] - prv[:, 2]) * ramp                 # the pulse flag ramps with the level
    strobe = 1.0 + cur[:, 1] * (wave01(2.0 * t, 0.4, 1.0) - 1.0)
    ph = (t * HALF_HZ) % 1.0
    patt = np.clip(ph / (HALF_HZ * ATTACK_S), 0.0, 1.0)
    pulse = 1.0 + puf * ((0.6 + 0.4 * (1.0 - ph) ** 2 * patt) - 1.0)
    return lvl * strobe * pulse


def cue_level_smooth(row):
    a, b = CUES[row, bar % 32, 0], CUES[row, (bar + 1) % 32, 0]
    bx = np.clip((fb - 0.85) / 0.15, 0.0, 1.0)
    return a + (b - a) * bx * bx * (3.0 - 2.0 * bx)


def strike_env():
    d = (fb - 0.5) * BAR_S
    return np.clip(d / 0.05, 0.0, 1.0) * np.clip(-d / 0.45 + 1.0 + 0.05 / 0.45, 0.0, 1.0)


STORM = cue_level(R["storm"]) * 1.0                           # x (0.4 + 0.6 macro) at the macro peak = 1
STRIKE = STORM * strike_env()


def show_lit(floor):
    return floor + (1.0 - floor) * cue_level(R["wash"]) + STRIKE_BUMP * STRIKE


def cue_tex(row, floor, flick=0.0):
    a = wave01(2.3 * t, 0.0, 1.0)
    return (floor + (1.0 - floor) * cue_level(row)) * (1.0 - flick * (1.0 - a))


OUTPUTS = {                                                   # name: (signal, large area?)
    "set (facade, rig: show_lit)": (show_lit(SET_FLOOR), True),
    "deck (show_lit)": (show_lit(DECK_FLOOR), True),
    "crowd bodies (show_light, sweep)": (CROWD_FLOOR + (1.0 - CROWD_FLOOR) * cue_level(R["wash"])
                                         * wave01(0.35 * t, 0.35, 1.0), True),
    "sky (lightning_sky)": (1.0 + SKY_GAIN * STRIKE, True),
    "fog (fog_sheet)": (np.clip(cue_level_smooth(R["fog"]) * 0.9, 0, 1) * (FOG_0 + FOG_K * cue_level(R["wash"])), True),
    "windows (cue_tex)": (cue_tex(R["windows"], 0.15, 0.15), False),
    "eyes (cue_tex)": (cue_tex(R["eyes"], 0.10), False),
    "lenses (cue_tex)": (cue_tex(R["lenses"], 0.06), False),
    "beams (stage row)": (wave01(BEAT_HZ / 4 * t, BEAMS_LO, 1.0) * cue_level(R["stage"]), False),
    "searchlights": (wave01(BEAT_HZ / 4 * t, BEAMS_LO, 1.0) * cue_level(R["search"]), False),
    "halos (lenses row)": (wave01(BEAT_HZ / 4 * t, BEAMS_LO, 1.0) * cue_level(R["lenses"]), False),
    "bolts": (np.clip(STRIKE, 0, 1), False),
    "fire jets": (cue_level_smooth(R["fire"]) * wave01(6.0 * t, FIRE_LO, 1.0), False),
    "crowd glow (phones)": (wave01(HALF_HZ * t, GLOW_LO, 1.0), False),
}
LASER_FAMILIES = ("fan (portal)", "horns 1", "horns 2", "horns 3", "horns 4", "towers (pinnacles)", "lip (deck)",
                  "mouth (back skulls)", "delay (front skulls)")
_lc_path = os.path.join(SRC, "T_HwLaserCues.png")
if not os.path.exists(_lc_path):
    sys.exit("[CUECHECK] no T_HwLaserCues.png in " + SRC + " (hw_stage.py v3 writes it)")
LASER_CUES = read_png(_lc_path)                                     # show.py tex_cues: 16 rows x 32 bars
EXEMPT = set()
_benv = (1.0 - ((t * 32.0 / LOOP_S * 4.0) % 1.0)) ** 2              # the engine's per-beat decay (its "pulse")
for grp, fam in enumerate(LASER_FAMILIES):
    crow = grp + 3 + (3 if grp > 4 else 0) + (1 if grp > 6 else 0)  # laser_show: rows 3-7, 11, 12, 14, 15
    name = f"lasers {grp} {fam} (Dino engine)"
    OUTPUTS[name] = (LASER_CUES[crow, bar % 32, 0] * (0.2 + 0.8 * _benv), False)
    EXEMPT.add(name)
for mesh, row in sorted(GROUPS.items()):
    OUTPUTS[f"{mesh} (row {row})"] = (wave01(BEAT_HZ / 4 * t, BEAMS_LO, 1.0) * cue_level(int(row)), False)


def transitions(x):
    """Hysteresis turning points: consecutive confirmed extremes that differ by >= FLASH_H, as moves
    [(start index, end index, +1 rise / -1 fall)]."""
    pts, lo_i, hi_i, d, ext = [], 0, 0, 0, 0
    for i in range(1, len(x)):
        if d == 0:                                                    # direction not known yet
            lo_i = i if x[i] < x[lo_i] else lo_i
            hi_i = i if x[i] > x[hi_i] else hi_i
            if x[hi_i] - x[lo_i] >= FLASH_H:
                if hi_i > lo_i:
                    pts.append(lo_i)
                    d, ext = 1, hi_i
                else:
                    pts.append(hi_i)
                    d, ext = -1, lo_i
        elif d == 1:                                                  # rising: track the high point
            if x[i] >= x[ext]:
                ext = i
            elif x[ext] - x[i] >= FLASH_H:
                pts.append(ext)
                d, ext = -1, i
        else:                                                         # falling: track the low point
            if x[i] <= x[ext]:
                ext = i
            elif x[i] - x[ext] >= FLASH_H:
                pts.append(ext)
                d, ext = 1, i
    return [(a, b, 1 if x[b] > x[a] else -1) for a, b in zip(pts, pts[1:])]


MAX_FRAME_JUMP = 0.35     # a 3-frame linear attack climbs <= 1/3 of its range per frame: more in one frame is a hit


def attack_frames(seg):
    """Equivalent linear attack of a strictly rising segment, in frames: its 5% -> 95% rise time / 0.9 (interpolated).
    A hard step reads 1 frame; the 60 ms cue ramp ~4.3; the 50 ms lightning attack ~3.6."""
    lo, m = seg[0], seg[-1] - seg[0]

    def cross(level):
        k = int(np.nonzero(seg >= level)[0][0])
        return 0.0 if k == 0 else (k - 1) + (level - seg[k - 1]) / (seg[k] - seg[k - 1])
    return (cross(lo + 0.95 * m) - cross(lo + 0.05 * m)) / 0.9


def analyse(x):
    """(flashes per second in the busiest 1-s window, the quickest attack in frames among rises >= FLASH_H, how many
    such rises, the biggest single-frame rise as a share of the peak)."""
    peak = float(x.max())
    if peak <= 1e-9:
        return 0.0, None, 0, 0.0
    x = x / peak
    n = len(x)
    x2 = np.concatenate([x, x])                                       # the loop wraps: see moves across its end
    times = np.array(sorted(b / FPS for a, b, _ in transitions(x2) if a < n))
    busiest = max((int(((times >= s) & (times < s + 1.0)).sum()) for s in times), default=0)
    d = np.diff(x2)
    worst, nr, i = None, 0, 0
    while i < n:                                                      # every strictly rising run (holds split them)
        if d[i] <= 1e-7:
            i += 1
            continue
        j = i
        while j < len(d) and d[j] > 1e-7:
            j += 1
        if x2[j] - x2[i] >= FLASH_H:
            nr += 1
            a = attack_frames(x2[i:j + 1])
            worst = a if worst is None else min(worst, a)
        i = j
    return busiest / 2.0, worst, nr, float(d[:n].max())


fails, rows = [], []
for name, (x, big) in OUTPUTS.items():
    fl, att, nr, jump = analyse(x)
    bad = []
    if fl > 3.0:
        bad.append(f"{fl:.1f} flashes/s")
    if name not in EXEMPT and att is not None and att < MIN_ATTACK_FRAMES:
        bad.append(f"a rise in {att:.1f} frames")
    if name not in EXEMPT and jump >= MAX_FRAME_JUMP:
        bad.append(f"a {jump:.0%} jump in one frame")
    rows.append((name, fl, att, nr, jump, "FAIL: " + ", ".join(bad) if bad else
                 ("ok (steps exempt: the Dino's engine)" if name in EXEMPT else "ok")))
    fails += [f"{name}: {b}" for b in bad]
w = max(len(r[0]) for r in rows)
print(f"[CUECHECK] {SRC}: 32 bars at {hw_show.SHOW_BPM:.0f} BPM = {LOOP_S:.1f} s at {FPS:.0f} Hz; attack ramp "
      f"{ATTACK_S * 1000:.0f} ms ({ATTACK_S * FPS:.1f} frames); storm modelled at its peak")
print(f"[CUECHECK] {'output'.ljust(w)}  flashes/s (busiest 1 s)  rises >= 20%  quickest attack  max 1-frame rise  verdict")
for name, fl, att, nr, jump, verdict in rows:
    print(f"[CUECHECK] {name.ljust(w)}  {fl:>23.1f}  {nr:>12d}  {('-' if att is None else f'{att:.1f} frames'):>15}  "
          f"{jump:>16.0%}  {verdict}")

# rules on the table itself
strobes = int((CUES[:, :, 1] > 0.5).sum())
wash_pulses = int((CUES[R["wash"], :, 2] > 0.5).sum())
ratio = 1.0 / (0.6 + 0.4 * 0.5 ** 2)                                  # on-beat (ph 0) over mid-beat (ph 0.5)
fire_rises = analyse(cue_level_smooth(R["fire"]))[2] / LOOP_S
print(f"[CUECHECK] strobe flags {strobes}; wash-row beat pulses {wash_pulses}; beat pulse on/mid {ratio:.2f}x; "
      f"fire bursts {fire_rises:.2f}/s")
if strobes:
    fails.append(f"{strobes} strobe flags in the table")
if wash_pulses:
    fails.append(f"the wash row pulses on {wash_pulses} bars")
if ratio > 1.6:
    fails.append(f"beat pulse {ratio:.2f}x > 1.6x")
if fire_rises > 0.5:
    fails.append(f"fire {fire_rises:.2f} bursts/s > 0.5")

# the sky at a full strike (display luma of the shipped texture x the material's gain)
sky_path = os.path.join(SRC, "T_HwSky.png")
if os.path.exists(sky_path):
    sky = read_png(sky_path)[..., :3]
    lin = np.where(sky <= 0.04045, sky / 12.92, ((sky + 0.055) / 1.055) ** 2.4)
    peak = 1.0 + SKY_GAIN * float(STRIKE.max())
    for label, k in (("at rest", 1.0), ("at a full strike", peak)):
        v = np.clip(lin * k, 0.0, 1.0)
        enc = np.where(v <= 0.0031308, v * 12.92, 1.055 * v ** (1 / 2.4) - 0.055)
        luma = enc @ np.array([0.2126, 0.7152, 0.0722])
        print(f"[CUECHECK] sky {label} (x{k:.2f}): display luma mean {luma.mean():.1%}, p95 {np.percentile(luma, 95):.1%}, "
              f"max {luma.max():.1%}")
    if luma.mean() > 0.35:
        fails.append(f"sky luma {luma.mean():.1%} > 35% at a full strike")
else:
    print("[CUECHECK] no T_HwSky.png: sky luma not checked")

if fails:
    print("[CUECHECK] FAIL\n" + "\n".join("[CUECHECK]   " + f for f in fails))
    sys.exit(1)
print("[CUECHECK] PASS: no strobes, <= 3 flashes/s everywhere, every rise >= 3 frames (the Dino laser engine's steps "
      "exempt), pulses <= 1.6x, sky <= 35%")
