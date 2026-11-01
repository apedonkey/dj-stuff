"""The REACTOR light show: one 32-bar loop at 140 BPM half-time (54.9 s), as a cue table texture T_ClubCues in the
format Scripts/dino_materials.py reads (cue_level): 32 bars x 16 rows, linear 8-bit, R = level, G = strobe flag,
B = beat-pulse flag (a gentle 0.6..1 envelope on beats 1 and 3). build_club.py gives each mesh its row.

Rows: dino_materials hard-wires two of them, the wash (WASH_ROW = 1: what show_lit multiplies the baked room by) and
the lenses (strobe_tex's default row 10); the rest are the club's own.

Comfort (the user's rules, unchanged since the Dino Stage): no strobes anywhere (G is always 0), the wash never pulses
per beat (it only swells bar by bar), beat pulses only on beams, lenses and the core, at half time (~1.2 per second).
The room stays dark between hits ("i liked how dark it was before"; REACTOR v2: "a little darker").

Plain Python + numpy (no bpy): club_stage.py imports it; `python club_show.py [out_dir]` rewrites T_ClubCues.png alone.
"""
import os
import struct
import sys
import zlib

import numpy as np

CUE_ROWS = {"heads": 0, "wash": 1, "core": 2, "laserbar": 3, "sidelasers": 4, "backlasers": 5, "bayheads": 6,
            "floorheads": 7, "lenses": 10, "always": 13, "beacons": 14}
SHOW_BARS, SHOW_BPM = 32, 140.0
# the loop's sections (bars): intro 0-7, build 8-14, blackout 15, drop 16-23, breakdown 24-27, outro 28-31


def show_program():
    """{row index: [(level, strobe, pulse)] * 32}."""
    P = {r: [(0.0, 0, 0)] * SHOW_BARS for r in CUE_ROWS.values()}

    def put(row, bars, level, pulse=0):
        if row == "wash":
            pulse = 0                                                  # the wash swells per bar, never per beat
        for b in bars:
            P[CUE_ROWS[row]][b] = (min(1.0, level), 0, pulse)          # strobe flag always 0 (comfort)
    put("always", range(32), 1.0)
    put("beacons", range(32), 0.8)
    # the core: glows on its own in the quiet parts, rises through the build, alone again in the blackout bar
    put("core", range(0, 8), 0.6)
    for i, b in enumerate(range(8, 15)):
        put("core", [b], 0.65 + 0.05 * i, pulse=1)
    put("core", [15], 0.4)
    put("core", range(16, 24), 1.0, pulse=1)
    put("core", range(24, 28), 0.85)
    put("core", range(28, 32), 0.7, pulse=1)
    # the wash on the room (show_lit): near black between hits
    put("wash", range(0, 8), 0.12)
    for i, b in enumerate(range(8, 15)):
        put("wash", [b], 0.15 + 0.045 * i)
    put("wash", [15], 0.0)
    put("wash", range(16, 24), 0.55)
    put("wash", range(24, 28), 0.05)
    put("wash", range(28, 32), 0.3)
    # moving heads on the hall trusses, and their lenses
    put("heads", range(0, 8), 0.35)
    put("lenses", range(0, 8), 0.4)
    for i, b in enumerate(range(8, 15)):
        put("heads", [b], 0.5 + 0.07 * i, pulse=1)
        put("lenses", [b], 0.6 + 0.05 * i, pulse=1)
    put("heads", range(16, 24), 1.0, pulse=1)
    put("lenses", range(16, 24), 1.0, pulse=1)
    put("heads", range(24, 28), 0.12)
    put("lenses", range(24, 28), 0.15)
    put("heads", range(28, 31), 0.7, pulse=1)
    put("lenses", range(28, 31), 0.8, pulse=1)
    # the core-bay truss over the crowd joins late in the build; the deck heads swing up from the floor
    put("bayheads", range(11, 15), 0.8)
    put("bayheads", range(16, 24), 1.0)
    put("bayheads", range(28, 32), 0.6)
    put("floorheads", range(0, 8), 0.25)
    put("floorheads", range(8, 15), 0.6)
    put("floorheads", range(16, 24), 1.0, pulse=1)
    put("floorheads", range(24, 28), 0.2)
    put("floorheads", range(28, 32), 0.5)
    # lasers: the bar on the front truss from the intro's second half, the side crossfire and the back wall at the drop
    put("laserbar", range(4, 8), 0.5)
    for i, b in enumerate(range(8, 15)):
        put("laserbar", [b], 0.4 + 0.1 * i)
    put("laserbar", range(16, 24), 1.0)
    put("laserbar", range(24, 28), 0.6)
    put("laserbar", range(28, 32), 0.8)
    put("sidelasers", range(12, 15), 0.8)
    put("sidelasers", range(16, 24), 1.0)
    put("sidelasers", [28, 30], 1.0)
    put("backlasers", range(16, 24), 1.0)
    put("backlasers", [29, 30], 1.0)
    # bar 16 (index 15): blackout but for the core and the beacons (set above)
    for row in ("heads", "lenses", "bayheads", "floorheads", "laserbar", "sidelasers", "backlasers"):
        put(row, [15], 0.0)
    return P


def tex_cues():
    """16 x 32 RGB (rows x bars), linear: R = level, G = strobe flag, B = beat-pulse flag."""
    img = np.zeros((16, SHOW_BARS, 3))
    for row, bars in show_program().items():
        for b, (lv, st, pu) in enumerate(bars):
            img[row, b] = (lv, st, pu)
    return img


def check(img):
    """The comfort rules as assertions (the club's cue check): no strobe flag, no wash pulse, levels within 0..1."""
    assert not img[:, :, 1].any(), "strobe flag set somewhere"
    assert not img[CUE_ROWS["wash"], :, 2].any(), "the wash pulses per beat"
    assert 0.0 <= img.min() and img.max() <= 1.0
    return img


def write_png_linear(path, img):
    """Data texture (RGB, 8 bit), no sRGB curve: build_club imports it with sRGB off, nearest, no mips (copied from
    show.py, which the Dino session owns)."""
    a = (np.clip(img, 0, 1) * 255.0 + 0.5).astype(np.uint8)
    h, w, ch = a.shape
    raw = b"".join(b"\x00" + a[y].tobytes() for y in range(h))

    def chunk(tag, data):
        return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)
    png = b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, {3: 2, 4: 6}[ch], 0, 0, 0))
    png += chunk(b"IDAT", zlib.compress(raw, 6)) + chunk(b"IEND", b"")
    open(path, "wb").write(png)
    print(f"[CLUB] {os.path.basename(path)} {w}x{h} (linear data)", flush=True)


def write_cues(out):
    write_png_linear(os.path.join(out, "T_ClubCues.png"), check(tex_cues()))


if __name__ == "__main__":
    write_cues(sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(os.path.abspath(__file__)), "out_club"))
