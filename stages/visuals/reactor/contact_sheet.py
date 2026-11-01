"""Contact sheet + still from an encoded loop (system Python 3 + Pillow, ffmpeg on PATH). Copied from the Dino pack and
adapted: the Reactor screen is a plain 16:9 rectangle (16 x 9 m, the core's viewing window, filled edge to edge),
so the sheet marks the middle-90% safe area (key art inside) instead of the Dino arch window; --bars for the sting.

  python contact_sheet.py LOOP.mp4 --title "WITCHING HOUR" [--bars 8] [--bpm 140] [--frames 21,77,...] [--still 240]

Frames are decoded from the MP4 itself (not the PNG master), so the sheet shows what ships. Default: one frame per bar
(8 bars: 1.5 beats into each bar, between kick and snare; 4 bars: two per bar, on the kick and 1.5 beats in), and the
still from 58% into the loop. Writes LOOP_contact.png (4 x 2 grid, labelled with frame and bar.beat; the safe area as
a thin dotted frame) and LOOP_still_fNNN.png (full 1920x1080) next to the MP4, or into --out-dir.
"""
import argparse
import math
import os
import subprocess
import tempfile

import numpy as np
from PIL import Image, ImageDraw, ImageFont

BEAT_F = []


def where(f):
    k = max(i for i in range(len(BEAT_F) - 1) if BEAT_F[i] <= f)
    return f"bar {k // 4 + 1} beat {k % 4 + 1 + (f - BEAT_F[k]) / (BEAT_F[k + 1] - BEAT_F[k]):.1f}"


def safe_box(w, h):
    return (0.05 * w, 0.05 * h, 0.95 * w, 0.95 * h)


def with_safe(im):
    """The frame with the middle-90% safe area drawn as a thin dotted yellow frame."""
    out = im.copy()
    d = ImageDraw.Draw(out)
    x0, y0, x1, y1 = safe_box(*im.size)
    step = 6
    for x in range(int(x0), int(x1), step * 2):
        d.line([(x, y0), (min(x + step, x1), y0)], fill=(255, 220, 0))
        d.line([(x, y1), (min(x + step, x1), y1)], fill=(255, 220, 0))
    for y in range(int(y0), int(y1), step * 2):
        d.line([(x0, y), (x0, min(y + step, y1))], fill=(255, 220, 0))
        d.line([(x1, y), (x1, min(y + step, y1))], fill=(255, 220, 0))
    return out


def bright_outside(ims, luma=0.4):
    """Largest share, over the frames, of bright pixels (display luma > `luma`) outside the middle 90%."""
    worst = (-1.0, None)
    for f, im in ims.items():
        y = np.asarray(im, np.float32) @ np.array([0.2126, 0.7152, 0.0722], np.float32) / 255
        h, w = y.shape
        lit = y > luma
        mh, mw = int(round(h * 0.05)), int(round(w * 0.05))
        inside = lit[mh:h - mh, mw:w - mw].sum()
        share = (lit.sum() - inside) / max(lit.sum(), 1)
        worst = max(worst, (share, f))
    return worst


def decode(mp4, frames, out_dir):
    """{frame: image}; the select filter emits frames in stream order, so map them back by sorted frame number."""
    want = sorted(set(frames))
    sel = "+".join(r"eq(n\,%d)" % f for f in want)
    subprocess.run(["ffmpeg", "-v", "error", "-i", mp4, "-vf", f"select='{sel}'", "-fps_mode", "passthrough",
                    os.path.join(out_dir, "x%03d.png")], check=True)
    return {f: Image.open(os.path.join(out_dir, f"x{i + 1:03d}.png")).convert("RGB") for i, f in enumerate(want)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("mp4")
    ap.add_argument("--title", default="")
    ap.add_argument("--bars", type=int, default=8)
    ap.add_argument("--bpm", type=float, default=140.0)
    ap.add_argument("--frames")
    ap.add_argument("--still", type=int)
    ap.add_argument("--out-dir", help="write the sheet and still here instead of next to the MP4")
    a = ap.parse_args()
    global BEAT_F
    fpb = 30 * 60.0 / a.bpm
    beats = 4 * a.bars
    n = int(round(beats * fpb))
    BEAT_F = [math.floor(k * fpb + 0.5) for k in range(beats)] + [n]
    if a.frames:
        frames = [int(x) for x in a.frames.split(",")]
    elif a.bars >= 8:
        frames = [round(4 * fpb * b + 1.5 * fpb) for b in range(8)]
    else:
        frames = [round(4 * fpb * b + o * fpb) for b in range(a.bars) for o in (0.15, 1.5)][:8]
    if a.still is None:
        a.still = round(0.58 * n)
    stem = os.path.splitext(os.path.basename(a.mp4))[0]
    base = os.path.join(a.out_dir, stem) if a.out_dir else os.path.splitext(a.mp4)[0]
    if a.out_dir:
        os.makedirs(a.out_dir, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        ims = decode(a.mp4, frames + [a.still], tmp)
    ims[a.still].save(f"{base}_still_f{a.still:03d}.png")

    tw, th, cols, pad, lab, head = 480, 270, 4, 6, 26, 44
    rows = math.ceil(len(frames) / cols)
    sheet = Image.new("RGB", (cols * tw + (cols + 1) * pad, head + rows * (th + lab + pad) + pad), (0, 0, 0))
    d = ImageDraw.Draw(sheet)
    font, big = ImageFont.load_default(size=17), ImageFont.load_default(size=24)
    d.text((pad + 4, 10), f"{a.title}   {a.bpm:g} BPM half-time  |  {a.bars} bars = {n} frames = {n / 30:.2f} s  |  "
                          f"1920x1080 30 fps  |  seamless", fill=(220, 220, 220), font=big)
    for i, f in enumerate(frames):
        x = pad + (i % cols) * (tw + pad)
        y = head + (i // cols) * (th + lab + pad)
        sheet.paste(with_safe(ims[f].resize((tw, th), Image.LANCZOS)), (x, y))
        d.text((x + 2, y + th + 4), f"f{f:03d}  {where(f)}", fill=(170, 170, 170), font=font)
    sheet.save(f"{base}_contact.png")
    print(f"{base}_contact.png  {base}_still_f{a.still:03d}.png")
    share, f = bright_outside(ims)
    print(f"safe area: {share:.0%} of the bright pixels fall outside the middle 90% (worst sheet frame f{f})")


if __name__ == "__main__":
    main()
