"""Contact sheet + still from an encoded loop (system Python 3 + Pillow, ffmpeg on PATH).

  python contact_sheet.py LOOP.mp4 --title "SPINE TUNNEL" [--bpm 140] [--frames 21,77,...] [--still 240] [--no-arch]

Frames are decoded from the MP4 itself (not the PNG master), so the sheet shows what ships. Default: one frame per
bar, 1.5 beats into the bar (between kick and snare), and the still from bar 5 (58% into the loop). Writes
LOOP_contact.png (4 x 2 grid, labelled with frame and bar.beat) and LOOP_still_fNNN.png (full 1920x1080) next to the
MP4.
The sheet shows the frames as the Dino Stage's arch screen cuts them (scripts/arch_window.json from arch_window.py):
outside the arch window dimmed, its edge in yellow. Key art belongs inside; colour may bleed to the frame edges.
"""
import argparse
import json
import math
import os
import subprocess
import tempfile

import numpy as np
from PIL import Image, ImageDraw, ImageFont

FPB = 14.0625                                                      # frames per beat (set from --bpm in main)
BEAT_F = []


def where(f):
    k = max(i for i in range(32) if BEAT_F[i] <= f)
    return f"bar {k // 4 + 1} beat {k % 4 + 1 + (f - BEAT_F[k]) / (BEAT_F[k + 1] - BEAT_F[k]):.1f}"


ARCH_JSON = os.path.join(os.path.dirname(os.path.abspath(__file__)), "arch_window.json")


def arch_window():
    """The arch screen's visible outline in 1920x1080 frame pixels (from arch_window.py), or None."""
    if not os.path.exists(ARCH_JSON):
        print("no arch_window.json (run arch_window.py with Blender): sheet without the arch overlay")
        return None
    with open(ARCH_JSON) as fh:
        win = json.load(fh)
    if os.path.exists(win["arch_py"]) and os.path.getmtime(win["arch_py"]) > win["arch_py_mtime"] + 1:
        print("WARNING: arch.py changed after arch_window.json was written; re-run arch_window.py")
    return win["outline_px"]


def arch_mask(outline, size):
    s = size[0] / 1920
    mask = Image.new("L", size, 0)
    ImageDraw.Draw(mask).polygon([(x * s, y * s) for x, y in outline], fill=255)
    return mask


def with_arch(im, outline):
    """The frame as the Dino Stage shows it: outside the arch window dimmed to 30%, the window's edge in yellow."""
    s = im.width / 1920
    out = Image.composite(im, Image.eval(im, lambda v: int(v * 0.3)), arch_mask(outline, im.size))
    pts = [(x * s, y * s) for x, y in outline]
    ImageDraw.Draw(out).line(pts + [pts[0]], fill=(255, 220, 0), width=1)
    return out


def bright_outside(ims, outline, luma=0.4):
    """Largest share, over the frames, of bright pixels (display luma > `luma`) that fall outside the arch window:
    a hint for key art the arch cuts off (strong background colour there is fine)."""
    inside = np.asarray(arch_mask(outline, (1920, 1080))) > 0
    worst = (-1.0, None)
    for f, im in ims.items():
        y = np.asarray(im, np.float32) @ np.array([0.2126, 0.7152, 0.0722], np.float32) / 255
        lit = y > luma
        share = (lit & ~inside).sum() / max(lit.sum(), 1)
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
    ap.add_argument("--bpm", type=float, default=140.0)
    ap.add_argument("--frames")
    ap.add_argument("--still", type=int)
    ap.add_argument("--no-arch", action="store_true", help="plain frames, without the arch window overlay")
    a = ap.parse_args()
    outline = None if a.no_arch else arch_window()
    global FPB, BEAT_F
    FPB = 30 * 60.0 / a.bpm
    n = int(round(32 * FPB))
    BEAT_F = [math.floor(k * FPB + 0.5) for k in range(32)] + [n]
    frames = ([int(x) for x in a.frames.split(",")] if a.frames
              else [round(4 * FPB * b + 1.5 * FPB) for b in range(8)])
    if a.still is None:
        a.still = round(0.58 * n)
    base = os.path.splitext(a.mp4)[0]
    with tempfile.TemporaryDirectory() as tmp:
        ims = decode(a.mp4, frames + [a.still], tmp)
    ims[a.still].save(f"{base}_still_f{a.still:03d}.png")

    tw, th, cols, pad, lab, head = 480, 270, 4, 6, 26, 44
    rows = math.ceil(len(frames) / cols)
    sheet = Image.new("RGB", (cols * tw + (cols + 1) * pad, head + rows * (th + lab + pad) + pad), (0, 0, 0))
    d = ImageDraw.Draw(sheet)
    font, big = ImageFont.load_default(size=17), ImageFont.load_default(size=24)
    d.text((pad + 4, 10), f"{a.title}   {a.bpm:g} BPM  |  8 bars = {n} frames = {n / 30:.1f} s  |  1920x1080 30 fps  |  seamless",
           fill=(220, 220, 220), font=big)
    for i, f in enumerate(frames):
        x = pad + (i % cols) * (tw + pad)
        y = head + (i // cols) * (th + lab + pad)
        tile = ims[f].resize((tw, th), Image.LANCZOS)
        sheet.paste(with_arch(tile, outline) if outline else tile, (x, y))
        d.text((x + 2, y + th + 4), f"f{f:03d}  {where(f)}", fill=(170, 170, 170), font=font)
    sheet.save(f"{base}_contact.png")
    print(f"{base}_contact.png  {base}_still_f{a.still:03d}.png")
    if outline:
        share, f = bright_outside(ims, outline)
        print(f"arch window: {share:.0%} of the bright pixels fall outside it (worst sheet frame f{f})")


if __name__ == "__main__":
    main()
