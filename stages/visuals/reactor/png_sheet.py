"""Look-dev sheet from rendered PNG frames (system Python 3 + Pillow).

  python png_sheet.py FRAMES_DIR PREFIX OUT.png [--bars 8] [--bpm 140] [--frames a,b,c] [--cols 4] [--tile 480]

Default frames: one per bar 1.5 beats in, plus each bar's downbeat for the first two bars. Tiles carry frame and
bar.beat labels and the middle-90% safe area (dotted).
"""
import argparse
import math
import os

from PIL import Image, ImageDraw, ImageFont

from contact_sheet import with_safe


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("frames_dir")
    ap.add_argument("prefix")
    ap.add_argument("out")
    ap.add_argument("--bars", type=int, default=8)
    ap.add_argument("--bpm", type=float, default=140.0)
    ap.add_argument("--frames")
    ap.add_argument("--cols", type=int, default=4)
    ap.add_argument("--tile", type=int, default=480)
    a = ap.parse_args()
    fpb = 30 * 60.0 / a.bpm
    beats = 4 * a.bars
    n = int(round(beats * fpb))
    beat_f = [math.floor(k * fpb + 0.5) for k in range(beats)] + [n]
    if a.frames:
        frames = [int(x) for x in a.frames.split(",")]
    else:
        frames = sorted({round(4 * fpb * b + 1.5 * fpb) for b in range(a.bars)} | {0, beat_f[2], beat_f[4]})
    frames = [f for f in frames if os.path.exists(os.path.join(a.frames_dir, f"{a.prefix}{f:04d}.png"))]
    tw = a.tile
    th = tw * 9 // 16
    pad, lab = 4, 18
    rows = math.ceil(len(frames) / a.cols)
    sheet = Image.new("RGB", (a.cols * tw + (a.cols + 1) * pad, rows * (th + lab + pad) + pad), (0, 0, 0))
    d = ImageDraw.Draw(sheet)
    font = ImageFont.load_default(size=13)
    for i, f in enumerate(frames):
        im = Image.open(os.path.join(a.frames_dir, f"{a.prefix}{f:04d}.png")).convert("RGB").resize((tw, th))
        x = pad + (i % a.cols) * (tw + pad)
        y = pad + (i // a.cols) * (th + lab + pad)
        sheet.paste(with_safe(im), (x, y))
        k = max(j for j in range(beats) if beat_f[j] <= f % n)
        ph = (f % n - beat_f[k]) / (beat_f[k + 1] - beat_f[k])
        d.text((x + 2, y + th + 2), f"f{f}  bar {k // 4 + 1} beat {k % 4 + 1 + ph:.1f}", fill=(170, 170, 170),
               font=font)
    sheet.save(a.out)
    print(a.out)


if __name__ == "__main__":
    main()
