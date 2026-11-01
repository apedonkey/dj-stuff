"""GRAVEYARD SHIFT light show: one 32-bar loop at 140 BPM half-time (54.9 s), as a cue table texture T_HwCues (32 bars x
32 rows (18 used), linear 8-bit data: R = level, G = strobe flag (always 0 here), B = beat-pulse flag). The animated materials
(Scripts/hw_materials.py cue_level / cue_level_smooth) read it by row; build_halloween.py assigns rows per mesh.

Same format and rules as the Dino Stage's show.py (copied, not imported: the Dino session owns that file), with the
comfort rules the user set on 2026-10-06 ("the flashing lights above me onto the stage are a bit too much for me"):
no strobes anywhere; the set/crowd wash never pulses per beat, it only swells bar by bar; beat pulses are gentle
(0.6..1.0 on beats 1 and 3, half-time). Lightning (row "storm") strikes at most once per bar with a >= 3-frame attack
(the materials shape it); fire bursts last a bar with 2-bar gaps.

Plain Python + numpy (no bpy): hw_stage.py imports it, and `python hw_show.py [out_dir]` rewrites T_HwCues.png alone.
"""
import os
import struct
import sys
import zlib

import numpy as np

CUE_ROWS = {"stage": 0, "wash": 1, "search": 2, "portal": 3, "garg_l_in": 4, "garg_l_out": 5, "garg_r_in": 6,
            "garg_r_out": 7, "infra": 8, "crypt": 9, "lenses": 10, "windows": 11, "storm": 12, "always": 13, "fire": 14,
            "eyes": 15, "hands": 16, "fog": 17}
CUE_TEX_ROWS = 32                                                # hw_materials.CUE_ROWS_N
SHOW_BARS, SHOW_BPM = 32, 140.0
LASER_GROUPS = {"portal": 0, "garg_l_in": 1, "garg_l_out": 2, "garg_r_in": 3, "garg_r_out": 4}   # UV LaserCue: row = 3 + g


def show_program():
    """{row: [(level, strobe, pulse)] * 32}. Intro (bars 1-8): windows and candles, the heads low, no lasers;
    build (9-15): heads up, searchlights wake, the gargoyle fans join one by one, distant lightning; bar 16 BLACKOUT
    (only the eyes, the clock and the moon; one close strike); drop (17-24): everything, lightning every 2 bars, flame
    bursts; breakdown (25-28): windows and fog; outro (29-32): the fans alternate sides and fade."""
    P = {r: [(0.0, 0, 0)] * SHOW_BARS for r in CUE_ROWS.values()}

    def put(row, bars, level, pulse=0):
        if row == "wash":                                            # comfort: the wash only swells bar by bar
            pulse = 0
        elif pulse and row in ("stage", "lenses"):                   # keep a pulsing bar's average near a steady one
            level *= 0.85
        for b in bars:
            P[CUE_ROWS[row]][b] = (level, 0, pulse)
    put("always", range(32), 1.0)
    put("crypt", range(32), 0.8, pulse=1)                            # the second stage runs its own party
    put("infra", range(32), 0.7)                                     # follow spots stay on the DJ
    # intro
    put("stage", range(0, 8), 0.3)
    put("lenses", range(0, 8), 0.35)
    put("wash", range(0, 8), 0.12)
    put("windows", range(0, 8), 0.45)
    put("search", range(0, 8), 0.4)
    put("eyes", range(0, 8), 0.4)
    # build
    for i, b in enumerate(range(8, 15)):
        put("stage", [b], 0.5 + 0.07 * i, pulse=1)
        put("lenses", [b], 0.6 + 0.05 * i, pulse=1)
        put("wash", [b], 0.25 + 0.05 * i)
        put("windows", [b], 0.6 + 0.03 * i)
        put("search", [b], 0.6 + 0.05 * i)
        put("eyes", [b], 0.6)
    put("garg_l_in", [10, 11, 12, 13, 14], 1.0)
    put("garg_r_in", [11, 12, 13, 14], 1.0)
    put("garg_l_out", [12, 13, 14], 1.0)
    put("garg_r_out", [13, 14], 1.0)
    put("portal", [14], 1.0)
    put("storm", [11], 0.5)
    put("storm", [13], 0.7)
    # bar 16 (index 15): blackout; the eyes glare, one close strike
    put("windows", [15], 0.15)
    put("search", [15], 0.15)
    put("lenses", [15], 0.05)
    put("wash", [15], 0.03)
    put("infra", [15], 0.0)
    put("eyes", [15], 1.0)
    put("storm", [15], 1.0)
    # drop
    for row in ("stage", "lenses"):
        put(row, range(16, 24), 1.0, pulse=1)
    put("wash", range(16, 24), 0.9)
    for row in ("windows", "search", "portal", "garg_l_in", "garg_l_out", "garg_r_in", "garg_r_out", "eyes"):
        put(row, range(16, 24), 1.0)
    put("infra", range(16, 24), 1.0, pulse=1)
    put("storm", [16, 18, 20, 22], 0.8)
    put("fire", [16, 19, 22], 1.0)
    # breakdown
    put("stage", range(24, 28), 0.1)
    put("lenses", range(24, 28), 0.12)
    put("wash", range(24, 28), 0.05)
    put("windows", range(24, 28), 0.7)
    put("search", range(24, 28), 0.4)
    put("portal", range(24, 28), 0.4)
    put("eyes", range(24, 28), 0.5)
    # outro: the fans alternate sides, searchlights fade, the last strikes
    put("stage", range(28, 32), 0.7, pulse=1)
    put("lenses", range(28, 32), 0.8, pulse=1)
    put("wash", range(28, 32), 0.5)
    put("windows", range(28, 32), 0.6)
    for i, b in enumerate(range(28, 32)):
        put("search", [b], 0.8 - 0.15 * i)
    put("garg_l_in", [28, 30], 1.0)
    put("garg_l_out", [28, 30], 1.0)
    put("garg_r_in", [29, 31], 1.0)
    put("garg_r_out", [29, 31], 1.0)
    put("eyes", range(28, 32), 0.6)
    put("storm", [28], 0.4)
    put("storm", [30], 0.2)
    # the giant skeletal hands (cue_level_smooth glides between bars): rise through the build, up for the blackout and
    # the drop, sink in the breakdown
    for i, b in enumerate(range(8, 15)):
        put("hands", [b], 0.12 + 0.12 * i)
    put("hands", range(15, 24), 1.0)
    put("hands", [24], 0.5)
    put("hands", [25], 0.15)
    # ground fog (smooth): low in the intro, thick in the blackout and the breakdown
    put("fog", range(0, 8), 0.45)
    put("fog", range(8, 15), 0.55)
    put("fog", [15], 0.9)
    put("fog", range(16, 24), 0.6)
    put("fog", range(24, 28), 1.0)
    put("fog", range(28, 32), 0.6)
    return P


def tex_cues():
    """32 x 32 RGB, linear: R = level, G = strobe flag, B = beat-pulse flag (rows = CUE_ROWS; unused rows stay 0)."""
    img = np.zeros((CUE_TEX_ROWS, SHOW_BARS, 3))
    for row, bars in show_program().items():
        for b, (lv, st, pu) in enumerate(bars):
            img[row, b] = (lv, st, pu)
    return img


def write_png_linear(path, img):
    """Data texture: no sRGB curve (build_halloween imports it with sRGB off, nearest, no mips, uncompressed)."""
    a = (np.clip(img, 0, 1) * 255.0 + 0.5).astype(np.uint8)
    h, w, _ = a.shape
    raw = b"".join(b"\x00" + a[y].tobytes() for y in range(h))

    def chunk(tag, data):
        return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)
    png = b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0))
    png += chunk(b"IDAT", zlib.compress(raw, 6)) + chunk(b"IEND", b"")
    open(path, "wb").write(png)
    print(f"[SHOW] {os.path.basename(path)} {w}x{h} (linear data)", flush=True)


def comfort_report():
    """Flashes per second from the table alone: a bar-to-bar jump of > 0.5 in a light row counts as a flash (the
    materials ramp them); pulses are soft (0.6..1.0) and do not count. Prints the worst rows."""
    beat_s = 60.0 / SHOW_BPM
    bar_s = 4 * beat_s
    P = show_program()
    worst = []
    for name, row in CUE_ROWS.items():
        lv = [P[row][b][0] for b in range(SHOW_BARS)]
        jumps = sum(1 for b in range(SHOW_BARS) if lv[b] - lv[b - 1] > 0.5)
        worst.append((jumps / (SHOW_BARS * bar_s), name, jumps))
    worst.sort(reverse=True)
    print(f"[SHOW] {SHOW_BARS} bars at {SHOW_BPM:.0f} BPM = {SHOW_BARS * bar_s:.1f} s; strobe flags: "
          f"{sum(P[r][b][1] for r in P for b in range(SHOW_BARS))}; big jumps per second (worst rows): "
          + ", ".join(f"{n} {f:.3f}/s ({j})" for f, n, j in worst[:4]))


if __name__ == "__main__":
    out = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(os.path.abspath(__file__)), "out_hw")
    os.makedirs(out, exist_ok=True)
    write_png_linear(os.path.join(out, "T_HwCues.png"), tex_cues())
    comfort_report()
