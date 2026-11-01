"""The Dino Stage light show: one 32-bar loop at 140 BPM (54.9 s; was 128 until the user's "mostly heavy dubstep"), as a cue table texture (T_DinoCues: 32 bars x 16 rows,
linear 8-bit data: R = level, G = strobe flag, B = beat-pulse flag). The animated materials (Scripts/dino_materials.py
cue_level / show_light) read it by row; build_dino.py assigns rows per mesh.

The user (2026-10-05): "for the lights and lasers, they shouldnt be on all the time" and "the crowd is dark because its
dark outside. Its a nighttime set. The stage would also be dark except for the dj and the visuals, lazrs, lights ect".
So beams/lasers follow their rows, and the set + crowd are lit only by the "wash" row: near black between hits, flashing
on beats and strobes, fully lit on the drop.

Plain Python + numpy (no bpy): dino_stage.py imports it, and `python show.py [out_dir]` rewrites T_DinoCues.png alone.
"""
import os
import struct
import sys
import zlib

import numpy as np

CUE_ROWS = {"stage": 0, "wash": 1, "sky": 2, "fan": 3, "horn6": 4, "horn5": 5, "horn4": 6, "horn3": 7, "infra": 8,
            "stage2": 9, "lenses": 10, "towers": 11, "lip": 12, "always": 13, "mouth": 14, "delay": 15}   # v10: the
            # tunnel under the T. rex's chin (mouth) and the delay towers' units in the crowd (delay)   # towers / lip: the laser units added
                                                                                 # 2026-10-08 (rows 11/12 held v8.2's
                                                                                 # pattern weights, now in T_DinoLaserLib)
SHOW_BARS, SHOW_BPM = 32, 140.0


def show_program():
    """{row: [(level, strobe, pulse)] * 32}. Intro (bars 1-8) sky + soft beams; build (9-15) beams pulse, lasers come in
    one by one, strobes; bar 16 BLACKOUT; drop (17-24) everything, strobe bursts; breakdown (25-28) near dark;
    outro (29-32) laser pairs alternate, strobe out."""
    P = {r: [(0.0, 0, 0)] * SHOW_BARS for r in CUE_ROWS.values()}

    def put(row, bars, level, strobe=0, pulse=0):
        # Comfort (the user, 2026-10-06: "the flashing lights above me onto the stage are a bit too much for me"):
        # no strobes anywhere, and the set/crowd wash never flashes per beat; it only swells bar by bar.
        strobe = 0
        # Keep the darkness the user liked ("i liked how dark it was before"): a beat pulse averaged 0.5 (0.25 + 0.75/3)
        # of a bar's level; the wash lost its pulse and the gentle pulse averages 0.73, so scale those bars to match.
        if pulse and row == "wash":
            level *= 0.5
        elif pulse and row in ("stage", "lenses"):
            level *= 0.68
        if row == "wash":
            pulse = 0
        for b in bars:
            P[CUE_ROWS[row]][b] = (level, strobe, pulse)
    put("always", range(32), 1.0)
    put("sky", range(32), 0.85)
    # the laser units on the towers and the stage front (2026-10-08): the towers sweep softly from bar 5 of the intro,
    # the stage front joins through the build, everything fires on the drop, the towers hold the breakdown
    put("towers", range(4, 8), 0.5)
    put("towers", range(10, 15), 0.8)
    for i, b in enumerate(range(8, 15)):
        put("lip", [b], 0.4 + 0.1 * i)
    put("towers", range(16, 24), 1.0)
    put("lip", range(16, 24), 1.0)
    put("towers", range(24, 28), 0.6)
    put("towers", range(28, 32), 0.8)
    put("lip", range(28, 32), 0.7)
    # v10: the tunnel joins late in the build and fires on the drop; the delay towers sweep over the crowd from the intro
    put("mouth", range(12, 15), 0.6)
    put("mouth", range(16, 24), 1.0)
    put("mouth", range(24, 28), 0.35)
    put("mouth", range(28, 32), 0.6)
    put("delay", range(4, 8), 0.4)
    put("delay", range(10, 15), 0.7)
    put("delay", range(16, 24), 1.0)
    put("delay", range(24, 28), 0.5)
    put("delay", range(28, 32), 0.7)
    put("stage2", range(32), 0.8, pulse=1)
    put("infra", range(32), 0.7)                                       # follow spots stay on the DJ
    # intro
    put("stage", range(0, 8), 0.35)
    put("lenses", range(0, 8), 0.4)
    put("wash", range(0, 8), 0.12)
    # build
    for i, b in enumerate(range(8, 15)):
        put("stage", [b], 0.5 + 0.07 * i, pulse=1)
        put("lenses", [b], 0.6 + 0.05 * i, pulse=1)
        put("wash", [b], 0.25 + 0.05 * i, pulse=1)
    put("stage", [12, 13, 14], 0.95, strobe=1)
    put("wash", [13, 14], 0.8, strobe=1)
    put("fan", [11, 12, 13, 14], 1.0)
    put("horn6", [13, 14], 1.0)
    put("horn5", [14], 1.0)
    # bar 16 (index 15): blackout except a dim sky
    put("sky", [15], 0.25)
    put("infra", [15], 0.0)
    # drop
    for row in ("stage", "lenses", "wash"):
        put(row, range(16, 24), 1.0, pulse=1)
    for row in ("fan", "horn6", "horn5", "horn4", "horn3"):
        put(row, range(16, 24), 1.0)
    put("stage", [20, 21], 1.0, strobe=1)
    put("wash", [20, 21], 1.0, strobe=1)
    put("infra", range(16, 24), 1.0, pulse=1)
    put("sky", range(16, 24), 1.0)
    # breakdown
    put("stage", range(24, 28), 0.12)
    put("lenses", range(24, 28), 0.15)
    put("wash", range(24, 28), 0.05)
    put("fan", range(24, 28), 0.5)
    put("sky", range(24, 28), 0.5)
    # outro: laser pairs alternate, strobe out
    put("stage", range(28, 31), 0.7, pulse=1)
    put("lenses", range(28, 31), 0.8, pulse=1)
    put("wash", range(28, 31), 0.55, pulse=1)
    put("horn6", [28, 30], 1.0)
    put("horn4", [28, 30], 1.0)
    put("horn5", [29, 30], 1.0)
    put("horn3", [29, 30], 1.0)
    for row in ("stage", "lenses", "fan", "horn6", "horn5", "horn4", "horn3", "towers", "lip", "mouth", "delay", "wash"):
        put(row, [31], 1.0, strobe=1)
    return P


def tex_cues():
    """32 x 16 RGB, linear: R = level, G = strobe flag, B = beat-pulse flag (rows = CUE_ROWS)."""
    img = np.zeros((16, SHOW_BARS, 3))
    for row, bars in show_program().items():
        for b, (lv, st, pu) in enumerate(bars):
            img[row, b] = (lv, st, pu)
    return img


# ------------------------------------------------------------------ the laser show v2 (2026-10-08)
# The user: "the lazers need to be coming from the actual lazer things on the stage ... upgrade the quality", "we need
# more patterns too. way more", and for colors "Full RGB / rainbow chases". v8.2's seven hard-wired patterns (weights in
# cue rows 11, 12, 14) become a parametric engine: dino_materials.laser_show() evaluates, per laser vertex, the motion
# pattern and the color scheme of this bar (crossfading into the next bar's over its last 15%), looked up in two data
# textures:
#   T_DinoLaserProg  32 bars x 8 variants, RGBA8: R = pattern id, G = color id, B = level, A = 0. The mod picks a
#                    variant per song (MPC LaserVariant); the free show moves to the next variant every 32 bars.
#   T_DinoLaserLib   11 texels x 64 rows, RGBA8: row r = pattern r's motion (texels 0-7: its hit reactions in 6, its
#                    bass reactions in 7) and color scheme r (texels 8-10, with its hit reactions in 10).
# Motion, per laser: pan P and tilt Q in -1..1 of its unit's amplitudes and a visibility V. u = the beam's place in its
# unit's fan (-1..1), x = the unit's place across the rig (0 = the crowd's left .. 1), side = -1 / +1 (x < / >= 0.5),
# b = show time in bars:
#   P = pO + pA w(pF b + pPi u + pPj x + pSide [side > 0], pSh) + fA u (0.5 + 0.5 sin(2 pi fF b)), times
#       lerp(1, side, pMir) (pMir 1: the right side mirrors the left);  Q = qO + qA w(qF b + qPi u + qPj x + qLag, qSh);
#       both clamped to -1..1;  w(a, sh) = sign(s) |s|^(1 - 0.8 sh) with s = sin(2 pi a): sh 0 = sine, 1 = near square
#   V = [frac(cF b + cPi u + cPj x) < cDuty] (soft edge) x (1 - pulse + pulse (1 - beat phase)^2) x [group in mask]
# Color: H = frac(h0 + hF b' + hPi u + hPj x + hSide [side > 0]), b' = b held per beat when hStep; RGB = the hue,
# washed toward white by 1 - sat, flashing white at each beat by flash.
# Hits (v10, the hook replays songs/<key>.hits: MPC HitMajor / HitMinor decaying envelopes, HitCount, DropBoom):
#   V x lerp(1, (1 - hFlash / 2) + hFlash (0.5 + HitMajor + 0.4 HitMinor), HitsOn): dim between hits, flash on them;
#   Q += hTilt HitMajor (pop), P += (hFan u + hMir side) HitMajor (fan burst, mirrored swing); hue += hHit HitCount (a
#   step per major hit), white flash hWhite HitMajor. DropBoom (the drop's first moment) opens every fan and flashes white.
# Comfort (the user, 2026-10-06, about flashing above the stage): no chase or color step faster than the beat (4 a bar);
# the hit maps hold at most one hit per beat.
# Bass (v11, the hook replays songs/<key>.bass: MPC Bass, the track's bass level 0..1 every 100 ms):
#   P += bFan u Bass, Q += bTilt Bass, V x (1 + bVis Bass), and the unit's level >= bLvl Bass x ShowLevel.
LIB_ROWS, LIB_TEXELS, PROG_VARIANTS = 64, 11, 8
MOTION = ("pO", "pA", "pF", "pSh", "pPi", "pPj", "pMir", "pSide", "fA", "fF", "qO", "qA", "qF", "qSh", "qPi", "qPj",
          "qLag", "cF", "cDuty", "cPi", "cPj", "pulse", "mask", "spare", "hFlash", "hTilt", "hFan", "hMir",
          "bFan", "bTilt", "bVis", "bLvl")
COLOR = ("h0", "hF", "hPi", "hPj", "hSide", "hStep", "sat", "flash", "hHit", "hWhite", "cspare1", "cspare2")
ENC = {"pO": "signed", "pA": "unit", "pF": "freq", "pSh": "unit", "pPi": "signed", "pPj": "wide", "pMir": "unit",
       "pSide": "turn", "fA": "signed", "fF": "freq", "qO": "signed", "qA": "unit", "qF": "freq", "qSh": "unit",
       "qPi": "signed", "qPj": "wide", "qLag": "turn", "cF": "freq", "cDuty": "unit", "cPi": "signed", "cPj": "wide",
       "pulse": "unit", "mask": "bits", "spare": "unit",
       "h0": "turn", "hF": "wide", "hPi": "signed", "hPj": "wide", "hSide": "turn", "hStep": "unit", "sat": "unit",
       "flash": "unit", "hFlash": "unit", "hTilt": "signed", "hFan": "signed", "hMir": "signed", "hHit": "turn",
       "hWhite": "unit", "cspare1": "unit", "cspare2": "unit", "bFan": "signed", "bTilt": "signed", "bVis": "unit",
       "bLvl": "unit"}
# mask bits by family (the material maps group -> family): fan (group 0), horns (1-4), towers (5), lip (6), mouth (7),
# delay (8); mask 0 = all
GROUP_BITS = {"fan": 1, "horns": 2, "towers": 4, "lip": 8, "mouth": 16, "delay": 32}
POOL_HITS = {"calm": dict(hFlash=.25, bFan=.1, bVis=.2, bLvl=.35),       # each pool's hit and bass reactions
             "build": dict(hFlash=.45, hFan=.15, bFan=.2, bTilt=.1, bVis=.3, bLvl=.5),   # (the patterns override)
             "hold": dict(),
             "drop": dict(hFlash=.9, hFan=.3, bFan=.3, bTilt=.15, bVis=.5, bLvl=.8),
             "outro": dict(hFlash=.35, bFan=.15, bVis=.3, bLvl=.5)}
MOTION_DEFAULT = {k: 0.0 for k in MOTION} | {"cDuty": 1.0}
COLOR_DEFAULT = {k: 0.0 for k in COLOR} | {"sat": 1.0}


def _byte(kind, v):
    """One parameter as the byte the material decodes (byte / 255 back): signed -1..1, wide -2..2, freq = cycles per
    bar in 1/16 steps (0..15.9), turn = 0..1 in 1/256 steps, unit 0..1, bits = an integer bit mask."""
    if kind == "signed":
        b = round((v + 1.0) / 2.0 * 255.0)
    elif kind == "wide":
        b = round((v + 2.0) / 4.0 * 255.0)
    elif kind == "freq":
        b = round(v * 16.0)
    elif kind == "turn":
        b = round((v % 1.0) * 256.0) % 256
    elif kind == "bits":
        b = int(v)
    else:
        b = round(v * 255.0)
    assert 0 <= b <= 255, (kind, v, b)
    return b


# (pool, name, params). Frequencies are cycles per bar (1 bar = 1.71 s at 140): 2 = the half-time kick and snare,
# 4 = every beat. Pools: calm (intro, breakdown), build (ordered by rising energy), hold (the blackout bar), drop, outro.
_M = GROUP_BITS
PATTERNS = (
    ("calm", "slow_sweep", dict(pA=.8, pF=.125, pPj=.5, qA=.3, qF=.0625, qLag=.25)),
    ("calm", "wave_roll", dict(pA=.4, pF=.25, pPj=1.5, qA=.6, qF=.25, qPj=1.5, qLag=.25)),
    ("calm", "breathing_fan", dict(fA=.9, fF=.125, qO=.2, qA=.2, qF=.0625)),
    ("calm", "tunnel", dict(pA=.7, pF=.25, qA=.7, qF=.25, qLag=.25, pPi=.5, qPi=.5)),
    ("calm", "liquid_sky", dict(qO=.65, qA=.15, qF=.5, qPj=1.0, pA=.3, pF=.0625, fA=.5, fF=.0625)),
    ("calm", "mirror_drift", dict(pA=.6, pF=.125, pMir=1, qA=.3, qF=.125, qLag=.25)),
    ("calm", "slow_scissor", dict(pA=.8, pF=.125, pMir=1, qO=.1)),
    ("calm", "ripple_down", dict(qA=.6, qF=.25, qPj=2.0, qPi=.25, pA=.2, pF=.0625)),
    ("calm", "searchlights", dict(pA=1.0, pF=.0625, pPj=1.0, qA=.4, qF=.125, qLag=.3, pSh=.2)),
    ("calm", "drift_chase", dict(pA=.5, pF=.125, cF=.5, cDuty=.6, cPj=1.0)),
    ("calm", "static_spread", dict(fA=.6, qO=-.1)),
    ("calm", "sky_cone", dict(qO=.5, pA=.5, pF=.125, qA=.4, qF=.125, qLag=.25, pPi=.5, qPi=.5)),
    ("calm", "sheet_flat", dict(fA=.8, qO=.55, qA=.1, qF=.125)),             # a ceiling of light over the heads
    ("calm", "bass_breath", dict(fA=.2, bFan=.6, bVis=.5, bLvl=.5, pA=.3, pF=.125)),   # slow, opening with the bass
    ("calm", "tunnel_breathe", dict(pA=.6, qA=.6, pF=.125, qF=.125, qLag=.25, pPi=.5, qPi=.5, fA=.6, fF=.25)),
    ("build", "build_sweep", dict(pA=.7, pF=.5, pPj=.5, qO=.1, qA=.3, qF=.5, qLag=.25)),
    ("build", "delay_sweep", dict(mask=_M["delay"] | _M["towers"], pA=.9, pF=.5, pPj=.5, qA=.3, qF=.5)),
    ("build", "build_chase", dict(cF=1.0, cDuty=.5, cPj=1.0, pA=.3, pF=.25)),
    ("build", "build_wave", dict(pA=.5, pF=1.0, pPj=1.0, qA=.5, qF=1.0, qPj=1.0, qLag=.25)),
    ("build", "riser_tilt", dict(qO=.6, qA=.3, qF=1.0, pA=.4, pF=.5)),
    ("build", "sheet_rise", dict(fA=1.0, qO=.3, qA=.6, qF=.5, qSh=.3)),      # an open plane rising and falling
    ("build", "build_crossfire", dict(pA=.8, pF=.5, pMir=1, cF=1.0, cDuty=.7)),
    ("build", "flicker_fan", dict(fA=.8, fF=1.0, cF=2.0, cDuty=.6)),
    ("build", "zoom_tunnel", dict(pA=.8, pF=1.0, qA=.8, qF=1.0, qLag=.25, pPi=.5, qPi=.5)),
    ("build", "beam_chase", dict(cF=2.0, cDuty=.4, cPi=.5, pA=.4, pF=.5)),
    ("build", "unit_chase", dict(cF=4.0, cDuty=.35, cPj=2.0, qO=.2)),
    ("build", "lift_off", dict(qO=.8, qA=.2, qF=2.0, fA=.7, fF=1.0, pulse=.4)),
    ("hold", "hold", dict()),
    ("hold", "hold_up", dict(qO=.8)),
    ("drop", "crossfire", dict(pA=1.0, pF=1.0, pMir=1, qA=.2, qF=2.0, hMir=.3)),
    ("drop", "crossfire_fast", dict(pA=1.0, pF=2.0, pMir=1, qA=.3, qF=2.0, qLag=.25)),
    ("drop", "bounce", dict(pA=.4, pF=.5, qO=-.2, qA=.8, qF=2.0, qSh=.8, qLag=.25, hTilt=.4)),
    ("drop", "figure8", dict(pA=.8, pF=.5, qA=.5, qF=1.0, pPi=.1)),
    ("drop", "zigzag", dict(pA=.9, pF=1.0, pSh=.9, qA=.4, qF=2.0, qSh=.9, hMir=.25)),
    ("drop", "fan_burst", dict(fA=1.0, fF=2.0, pulse=.6, qO=.1, hFan=.8)),
    ("drop", "beat_chase", dict(cF=4.0, cDuty=.5, cPj=1.0, pulse=.5, pA=.3, pF=.5)),
    ("drop", "scatter", dict(pA=.8, pF=1.0, pPi=.7, pPj=1.3, qA=.6, qF=1.0, qPi=.6, qPj=1.1)),
    ("drop", "spin_cone", dict(pA=.8, pF=1.0, qA=.8, qF=1.0, qLag=.25, pPi=.5, qPi=.5, pulse=.3)),
    ("drop", "double_cross", dict(pA=1.0, pF=1.0, pMir=1, pPj=.5, cF=2.0, cDuty=.7)),
    ("drop", "headbang", dict(qA=1.0, qF=2.0, qSh=.7, pA=.2, pF=.5, hTilt=-.5)),
    ("drop", "lip_blades", dict(mask=_M["lip"] | _M["fan"], pA=1.0, pF=1.0, pMir=1, qA=.3, qF=2.0)),
    ("drop", "horn_scissors", dict(mask=_M["horns"], pA=1.0, pF=1.0, pMir=1, qA=.4, qF=1.0)),
    ("drop", "tower_x", dict(mask=_M["towers"] | _M["horns"], pA=1.0, pF=.5, pMir=1, qA=.5, qF=1.0)),
    ("drop", "wave_rider", dict(pA=.5, pF=1.0, pPj=2.0, qA=.6, qF=1.0, qPj=2.0, qLag=.25, pulse=.4)),
    ("drop", "slam", dict(qO=-.4, qA=.6, qF=.5, qSh=1.0, fA=.8, fF=.5, pulse=.8, hTilt=-.6)),
    ("drop", "rotor", dict(pA=1.0, pF=2.0, pPi=1.0, qA=.3, qF=1.0, hFan=.5)),
    ("drop", "chase_sweep", dict(pA=.9, pF=1.0, pPj=1.0, cF=4.0, cDuty=.5, cPj=-1.0)),
    ("drop", "strafe", dict(pA=1.0, pF=.5, pSh=.8, pPj=.25, qA=.3, qF=2.0, pulse=.5, hMir=.4)),
    ("drop", "net", dict(pA=.6, pF=.5, qA=.6, qF=.5, pPi=.8, qPi=-.8, qLag=.25)),
    ("drop", "sheet_slam", dict(fA=1.0, qA=.8, qF=2.0, qSh=.9, hTilt=-.4)),  # the plane slams on the half-time hits
    ("drop", "bass_pump", dict(fA=.3, bFan=.9, bTilt=.35, bVis=.7, pA=.3, pF=.5, qA=.2, qF=1.0)),   # fans breathe the bass
    ("drop", "bass_scan", dict(pA=.8, pF=1.0, pMir=1, bTilt=.5, bVis=.6, qO=-.2)),    # scissors that lift with the bass
    ("drop", "tunnel_spin", dict(pA=.9, qA=.9, pF=2.0, qF=2.0, qLag=.25, pPi=.5, qPi=.5, hFan=.4)),
    ("drop", "mouth_tunnel", dict(mask=_M["mouth"] | _M["delay"] | _M["horns"], pA=.8, qA=.8, pF=1.0, qF=1.0,
                                  qLag=.25, pPi=.5, qPi=.5)),
    ("drop", "crowd_net", dict(mask=_M["delay"] | _M["towers"] | _M["lip"], pA=.7, pF=.5, pMir=1, pPj=1.0, qA=.4,
                               qF=1.0, hMir=.3)),
    ("outro", "outro_drift", dict(pA=.6, pF=.125, pPj=.5, cF=.5, cDuty=.7, qA=.2, qF=.125)),
    ("outro", "outro_pairs", dict(cF=1.0, cDuty=.5, cPj=2.0, pA=.5, pF=.25)),
    ("outro", "farewell_fan", dict(fA=.8, fF=.25, qO=.3, qA=.2, qF=.125)),
    ("outro", "outro_tunnel", dict(pA=.5, pF=.25, qA=.5, qF=.25, qLag=.25, pPi=.5, qPi=.5, cF=1.0, cDuty=.75, cPj=1.0)),
    ("outro", "outro_sheet", dict(fA=.9, qO=.4, qA=.2, qF=.25)),
)
# (pools, name, params): every scheme is full RGB, as the user picked ("Full RGB / rainbow chases")
COLORS = (
    (("calm", "build", "drop", "outro"), "units_roll", dict(hF=.25, hPj=1.0)),           # a rainbow across the rig, rolling
    (("calm",), "beams_rainbow", dict(hPi=.5, hF=.125, hPj=.25)),                        # a rainbow inside each fan
    (("calm", "outro"), "rig_cycle", dict(hF=.125)),                                    # the whole rig one color, cycling
    (("build", "drop"), "beat_steps", dict(hStep=1, hF=.667, hWhite=.3)),                           # a new color every beat
    (("calm",), "split_sides", dict(hSide=.5, hF=.125)),                                 # opposite colors left / right
    (("build", "drop"), "fast_roll", dict(hF=1.0, hPj=1.0, hPi=.25, hWhite=.25)),
    (("drop",), "rainbow_flash", dict(hF=.25, hPj=1.0, flash=.6, hWhite=.6)),                       # white hits on the beat
    (("build", "drop"), "rgb_steps", dict(hStep=1, hF=1.333, hPj=.333, hWhite=.3)),                 # red / green / blue per beat
    (("calm", "outro"), "pastel_roll", dict(sat=.6, hF=.25, hPj=1.0)),
    (("build", "drop"), "reverse_roll", dict(hF=-.5, hPj=1.0)),
    (("calm",), "magenta_cyan", dict(h0=.83, hSide=.33, hF=.03)),
    (("calm", "outro"), "rainbow_static", dict(hPj=1.0)),
    (("calm", "build"), "spectrum_sweep", dict(hF=.5, hPj=-1.0, hPi=.3)),
    (("build", "drop"), "hit_steps", dict(hHit=1 / 6, hPj=.5, hWhite=.35)),   # 60 deg on each major hit
    (("drop",), "hit_rainbow", dict(hHit=.08, hPj=1.0, hF=.1, hWhite=.4)),   # a rainbow that jolts on the hits
    (("drop",), "flash_steps", dict(hStep=1, hF=.667, flash=.5, hPj=.5, hWhite=.5)),
)
# the 32-bar loop's sections: (first bar, bars, pattern pool, bars per pattern, color pool, bars per color)
LASER_SECTIONS = ((0, 8, "calm", 2, "calm", 4), (8, 7, "build", 2, "build", 4), (15, 1, "hold", 1, "build", 1),
                  (16, 8, "drop", 2, "drop", 4), (24, 4, "calm", 2, "calm", 4), (28, 4, "outro", 2, "outro", 4))


# v12 laser scenes: which groups may fire in each bar (T_DinoLaserProg alpha; 0 = all). A pattern with its own mask
# keeps it. The drop opens with everything (with the drop boom), then three-group scenes take turns every two bars, each
# group in half of them, starting at a different scene per variant (per song); the quieter sections light the groups
# their cue rows bring in, a few at a time (the user: "a bit much having them all on at the same time").
_G = GROUP_BITS
DROP_SCENES = (_G["horns"] | _G["lip"] | _G["mouth"], _G["towers"] | _G["fan"] | _G["delay"],
               _G["horns"] | _G["delay"] | _G["fan"], _G["towers"] | _G["lip"] | _G["mouth"],
               _G["horns"] | _G["towers"] | _G["lip"], _G["fan"] | _G["mouth"] | _G["delay"])


def bar_groups(v, b):
    """The groups that may fire in bar b (0-31) of variant v, as a bit mask (0 = all)."""
    G = _G
    if b < 4:                                                          # intro: the bass breathes the fan and the lip
        return G["fan"] | G["lip"]
    if b < 8:
        return G["towers"] | G["delay"]
    if b < 15:                                                         # build: the groups its cue rows bring in
        return (G["lip"], G["lip"], G["lip"] | G["towers"] | G["delay"], G["lip"] | G["towers"] | G["delay"] | G["fan"],
                G["lip"] | G["towers"] | G["fan"] | G["mouth"], 0, 0)[b - 8]
    if b == 15 or b == 16:                                             # the hold (dark), then the drop: everything
        return 0
    if b < 24:                                                         # the drop: scenes, two bars each
        return DROP_SCENES[(v + (b - 16) // 2) % len(DROP_SCENES)]   # bar 17 alone, then with the pattern pairs
    if b < 28:                                                         # breakdown
        return (G["fan"] | G["mouth"]) if b < 26 else (G["towers"] | G["delay"])
    if b < 30:                                                         # outro
        return G["horns"] | G["lip"] | G["mouth"]
    return (G["towers"] | G["delay"] | G["horns"]) if b == 30 else 0


def laser_program():
    """[variant][bar] = (pattern id, color id, level, groups). Each pool is dealt from one fixed shuffle, so the 8 variants
    between them use every pattern; the build's picks are sorted by the pool's energy order (it rises)."""
    rng = np.random.default_rng(20261008)
    pat_ids = {name: i for i, (_, name, _) in enumerate(PATTERNS)}
    col_ids = {name: i for i, (_, name, _) in enumerate(COLORS)}
    decks = {}

    def deal(kind, pool, n, items):
        key = (kind, pool)
        if key not in decks or len(decks[key]) < n:
            names = [nm for pl, nm, _ in items if (pool in pl if kind == "col" else pl == pool)]
            decks[key] = list(decks.get(key, [])) + [names[i] for i in rng.permutation(len(names))]
        out, deck = [], decks[key]
        while len(out) < n:                                            # no repeat inside one section
            pick = next((i for i, nm in enumerate(deck) if nm not in out), 0)
            out.append(deck.pop(pick))
            if not deck:
                names = [nm for pl, nm, _ in items if (pool in pl if kind == "col" else pl == pool)]
                deck.extend(names[i] for i in rng.permutation(len(names)))
        return out
    prog = []
    for v in range(PROG_VARIANTS):
        bars = [None] * SHOW_BARS
        for first, n, ppool, pblock, cpool, cblock in LASER_SECTIONS:
            pats = deal("pat", ppool, -(-n // pblock), PATTERNS)
            if ppool == "build":
                order = [nm for pl, nm, _ in PATTERNS if pl == "build"]
                pats.sort(key=order.index)
            cols = deal("col", cpool, -(-n // cblock), COLORS)
            for k in range(n):
                bars[first + k] = (pat_ids[pats[k // pblock]], col_ids[cols[k // cblock]], 1.0, bar_groups(v, first + k))
        prog.append(bars)
    return prog


def tex_laser_lib():
    """LIB_ROWS x LIB_TEXELS RGBA, linear: row r = pattern r (texels 0-7) and color scheme r (texels 8-10), as bytes."""
    assert len(PATTERNS) <= LIB_ROWS and len(COLORS) <= LIB_ROWS
    img = np.zeros((LIB_ROWS, LIB_TEXELS, 4))
    for r, (pool, name, params) in enumerate(PATTERNS):
        assert set(params) <= set(MOTION), (name, set(params) - set(MOTION))
        vals = [_byte(ENC[k], (MOTION_DEFAULT | POOL_HITS[pool] | params)[k]) for k in MOTION]
        img[r, 0:8] = np.array(vals, float).reshape(8, 4) / 255.0
    for r, (_, name, params) in enumerate(COLORS):
        assert set(params) <= set(COLOR), (name, set(params) - set(COLOR))
        vals = [_byte(ENC[k], (COLOR_DEFAULT | params)[k]) for k in COLOR]
        img[r, 8:11] = np.array(vals, float).reshape(3, 4) / 255.0
    return img


def tex_laser_prog():
    """PROG_VARIANTS x 32 RGBA, linear: R = pattern id, G = color id, B = level, A = the bar's groups (v12; ids and
    masks as bytes)."""
    img = np.zeros((PROG_VARIANTS, SHOW_BARS, 4))
    for v, bars in enumerate(laser_program()):
        for b, (p, c, lv, grp) in enumerate(bars):
            img[v, b] = (p / 255.0, c / 255.0, lv, grp / 255.0)
    return img


def write_png_linear(path, img):
    """Data texture (RGB or RGBA, 8 bit): no sRGB curve (build_dino imports it with sRGB off, nearest, no mips,
    uncompressed)."""
    a = (np.clip(img, 0, 1) * 255.0 + 0.5).astype(np.uint8)
    h, w, ch = a.shape
    raw = b"".join(b"\x00" + a[y].tobytes() for y in range(h))

    def chunk(tag, data):
        return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)
    png = b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, {3: 2, 4: 6}[ch], 0, 0, 0))
    png += chunk(b"IDAT", zlib.compress(raw, 6)) + chunk(b"IEND", b"")
    open(path, "wb").write(png)
    print(f"[SHOW] {os.path.basename(path)} {w}x{h} (linear data)", flush=True)


def write_all(out):
    """Every show texture: the cue table and the laser program + library."""
    write_png_linear(os.path.join(out, "T_DinoCues.png"), tex_cues())
    write_png_linear(os.path.join(out, "T_DinoLaserProg.png"), tex_laser_prog())
    write_png_linear(os.path.join(out, "T_DinoLaserLib.png"), tex_laser_lib())


if __name__ == "__main__":
    write_all(sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(os.path.abspath(__file__)), "out"))
