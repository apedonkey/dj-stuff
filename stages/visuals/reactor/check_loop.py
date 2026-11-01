"""Pack gate for the REACTOR visuals (from GRAVEYARD SHIFT's) (copied from the Dino pack's check_loop.py and adapted: --bars for the
4-bar sting, safe-area and true-1 m2 info lines). Checks rendered frames or a video against the pack rules,
independent of the scene script (system Python 3 + numpy + Pillow; ffmpeg on PATH for --video).

  python check_loop.py FRAMES_DIR PREFIX --seam FRAME_N.png [--bars 8] [--bpm 140]   a loop's PNG frames + frame N
  python check_loop.py --video FILE.mp4 [--bars 8] [--bpm 140]                      an encoded loop, or the full set
Tempo: 140 BPM half-time by default (env VJ_BPM, VJ_HALFTIME); --straight for 4-on-the-floor.

Rules (the visuals wall is a 23 x 12.94 m screen in a dark VR night scene, and the DJ finds strobing too much):
  brightness  every 1/16-of-the-width block (120 x 120 px at 1080p, the lead's "~1 m2" block) at most 0.65 luma (the
              lead's cap is 0.70; the Dino gate's 0.65 is kept), and no frame brighter than 0.5 on average (no
              full-frame white). Info: the brightest true 1 m2 of this wall (1920 / 23 = 83 px blocks).
  flashes     at most 3 per second in any 1/16 of the frame (WCAG-style: a rise and a fall of >= 0.1 in mean relative
              luminance)
  one-frame   no frame that jumps up and falls most of the way back on the next frame (frame mean or any 1/16 region)
  kick pulse  accent frames (half-time: kick and snare, beats 1 and 3) at most 1.6x as bright as the frames halfway
              between accents
  seam        (loops) frame N rendered by the scene matches frame 0 (PSNR >= 45 dB), and the last -> first step is no
              bigger than the largest step inside the loop (MP4s: 1.1x, frame 0 is a keyframe; steps under 1.0 of
              255 always pass)
Info only: beat sync (accents that are brightness peaks), and the share of bright pixels (luma > 0.4) outside the
middle 90% of the frame (key art belongs inside; colour may bleed to the edges). Exit code 0 = PASS, 1 = FAIL.
"""
import argparse
import math
import os
import subprocess
import sys

import numpy as np
from PIL import Image

W709 = np.array([0.2126, 0.7152, 0.0722], dtype=np.float32)
BLOCK_MAX, MEAN_MAX, FLASH_MAX, KICK_MAX, SEAM_MIN_DB, POP_FLOOR = 0.65, 0.5, 3, 1.6, 45.0, 1.0


def stats(rgb):
    """Per-frame measures from an HxWx3 array of display values."""
    a = rgb.astype(np.float32) / 255
    y = a @ W709                                                   # luma of the display values
    h, w = y.shape
    b = w // 16
    blocks = y[:(h // b) * b, :16 * b].reshape(h // b, b, 16, b).mean(axis=(1, 3))
    b2 = w // 23                                                   # a true 1 m2 of the 23 m wide wall
    m2 = y[:(h // b2) * b2, :23 * b2].reshape(h // b2, b2, 23, b2).mean(axis=(1, 3))
    lin = np.where(a <= 0.04045, a / 12.92, ((a + 0.055) / 1.055) ** 2.4) @ W709   # relative luminance
    h4, w4 = h // 4, w // 4
    quads = lin[:4 * h4, :4 * w4].reshape(4, h4, 4, w4).mean(axis=(1, 3)).ravel()
    bright = y > 0.4
    mh, mw = int(round(h * 0.05)), int(round(w * 0.05))
    n_b = bright.sum()
    n_in = bright[mh:h - mh, mw:w - mw].sum()
    out_share = (n_b - n_in) / n_b if n_b else 0.0
    return y.mean(), blocks.max(), quads, m2.max(), out_share


def flash_peaks(series, step=0.1):
    """Peaks of a zigzag with hysteresis `step`: each is a rise >= step followed by a fall >= step."""
    peaks, mode = [], 0
    lo = hi = ext = series[0]
    i_ext = 0
    for i, v in enumerate(series):
        if mode == 0:
            lo, hi = min(lo, v), max(hi, v)
            if hi - lo >= step:
                mode, ext, i_ext = (1, v, i) if v == hi else (-1, v, i)
        elif mode == 1:
            if v > ext:
                ext, i_ext = v, i
            elif ext - v >= step:
                peaks.append(i_ext)
                mode, ext, i_ext = -1, v, i
        else:
            if v < ext:
                ext, i_ext = v, i
            elif v - ext >= step:
                mode, ext, i_ext = 1, v, i
    return peaks


def worst_flash_rate(series, looped, fps=30):
    """(max flashes in any 1 s window, peak frames) for one region's luminance series."""
    n = len(series)
    if looped:                                                     # unroll so peaks across the seam are counted
        peaks = [p - n for p in flash_peaks(np.concatenate([series] * 3)) if n <= p < 2 * n]
    else:
        peaks = flash_peaks(series)
    marks = np.zeros(n, int)
    marks[peaks] = 1
    if looped:
        marks = np.concatenate([marks, marks[:fps]])
    c = np.concatenate([[0], np.cumsum(marks)])
    return (int((c[fps:] - c[:-fps]).max()) if len(c) > fps else int(marks.sum())), peaks


def spikes(series, rise_min, back=0.6, looped=False):
    """Frames that jump up by >= rise_min and fall back by >= back x that jump on the very next frame."""
    s = np.asarray(series)
    prev, nxt = (np.roll(s, 1), np.roll(s, -1)) if looped else (np.r_[s[0], s[:-1]], np.r_[s[1:], s[-1]])
    up, down = s - prev, s - nxt
    return [int(i) for i in np.nonzero((up >= rise_min) & (down >= back * up))[0]]


def frames_from_pngs(d, prefix, n):
    for f in range(n):
        yield np.asarray(Image.open(f"{d}/{prefix}{f:04d}.png").convert("RGB"))


def frames_from_video(path, w=480, h=270):
    """Decode at reduced size, area-averaged, so block and region means are kept."""
    p = subprocess.Popen(["ffmpeg", "-v", "error", "-i", path, "-vf", f"scale={w}:{h}:flags=area",
                          "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], stdout=subprocess.PIPE)
    size = w * h * 3
    while True:
        buf = p.stdout.read(size)
        if len(buf) < size:
            break
        yield np.frombuffer(buf, np.uint8).reshape(h, w, 3)
    p.wait()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("frames_dir", nargs="?")
    ap.add_argument("prefix", nargs="?")
    ap.add_argument("--seam")
    ap.add_argument("--video")
    ap.add_argument("--bars", type=int, default=int(os.environ.get("VJ_BARS", 8)))
    ap.add_argument("--bpm", type=float, default=float(os.environ.get("VJ_BPM", 140)))
    ap.add_argument("--halftime", action="store_true", default=os.environ.get("VJ_HALFTIME", "1") == "1",
                    help="accents on beats 1 and 3 only (the kick-pulse test and beat-sync report use those)")
    ap.add_argument("--straight", action="store_true", help="accents on every beat")
    a = ap.parse_args()
    if a.straight:
        a.halftime = False
    fps = 30
    fpb = fps * 60.0 / a.bpm
    beats = 4 * a.bars
    loop_n = int(round(beats * fpb))
    beat_f = [math.floor(k * fpb + 0.5) for k in range(0, beats, 2 if a.halftime else 1)]

    src = frames_from_video(a.video) if a.video else frames_from_pngs(a.frames_dir, a.prefix, loop_n)
    L, B, Q, M2, OUT, steps, first, prev = [], [], [], [], [], [], None, None
    for i, im in enumerate(src):
        m, bmax, q, m2, out = stats(im)
        L.append(m)
        B.append(bmax)
        Q.append(q)
        M2.append(m2)
        OUT.append(out)
        cur = im.astype(np.float32)
        if prev is not None:
            steps.append(np.abs(cur - prev).mean())
        if first is None:
            first = cur
        prev = cur
        if a.video and i % 9000 == 8999:
            print(f"  ... {(i + 1) / fps / 60:.0f} min checked", flush=True)
    n = len(L)
    L, B, Q, M2, OUT = np.array(L), np.array(B), np.array(Q), np.array(M2), np.array(OUT)
    looped = n == loop_n                                           # a loop (frames or encoded) wraps around
    fails = []

    def t(f):
        return f"f{f}" if looped else f"{f // fps // 60}:{f // fps % 60:02d}+{f % fps:02d}f"

    print(f"{n} frames ({n / fps:.2f} s){f', a {a.bars}-bar loop' if looped else ''}")
    on_idx = [g for g in range(n) if g % loop_n in beat_f]
    mid_idx = [(g + round(fpb * (1.0 if a.halftime else 0.5))) % n for g in on_idx]   # halfway between accents
    ratio = L[on_idx].mean() / max(L[mid_idx].mean(), 1e-6)
    if looped:
        peaks = [f for f in range(n) if L[f] > L[f - 1] and L[f] >= L[(f + 1) % n]]
        print(f"beat sync (info): {sum(b in peaks for b in beat_f)}/{len(beat_f)} accents are brightness peaks; "
              f"peaks off the grid: {[p for p in peaks if p not in beat_f][:12]}")
    print(f"kick pulse: on-beat {L[on_idx].mean():.3f} vs mid-beat {L[mid_idx].mean():.3f} -> x{ratio:.2f}")
    if ratio > KICK_MAX:
        fails.append(f"kick pulse x{ratio:.2f} > {KICK_MAX}")

    print(f"brightness: brightest 120 px block {B.max():.2f} ({t(int(B.argmax()))}); brightest frame {L.max():.3f} "
          f"({t(int(L.argmax()))}); mean frame {L.mean():.3f}")
    print(f"info: brightest true 1 m2 (83 px) {M2.max():.2f} ({t(int(M2.argmax()))}); bright pixels outside the "
          f"middle 90%: worst {OUT.max():.0%} ({t(int(OUT.argmax()))}), mean {OUT.mean():.0%}")
    over = np.nonzero(B > BLOCK_MAX)[0]
    if len(over):
        fails.append(f"{len(over)} frames have a block over {BLOCK_MAX} (first {t(int(over[0]))})")
    if L.max() > MEAN_MAX:
        fails.append(f"frame {t(int(L.argmax()))} averages {L.max():.2f} > {MEAN_MAX} (full-frame white)")

    rates = [worst_flash_rate(Q[:, r], looped, fps) for r in range(16)]
    r_worst = int(np.argmax([r[0] for r in rates]))
    print(f"flashes: worst 1/16 region has {rates[r_worst][0]} per second (region {r_worst}, "
          f"first flash peaks {[t(p) for p in rates[r_worst][1][:8]]})")
    if rates[r_worst][0] > FLASH_MAX:
        fails.append(f"{rates[r_worst][0]} flashes per second > {FLASH_MAX}")

    sp = spikes(L, 0.04, looped=looped)
    sp_r = sorted({f for r in range(16) for f in spikes(Q[:, r], 0.08, looped=looped)})
    print(f"one-frame hits: {len(sp)} in the frame mean, {len(sp_r)} in regions"
          + (f" (at {[t(f) for f in (sp + sp_r)[:8]]})" if sp or sp_r else ""))
    if sp or sp_r:
        fails.append("one-frame hits")

    if looped:
        wrap = np.abs(first - prev).mean()
        print(f"loop step last->first: {wrap:.2f} (steps inside the loop: median {np.median(steps):.2f}, "
              f"max {np.max(steps):.2f})")
        if wrap > max(np.max(steps) * (1.1 if a.video else 1.02), POP_FLOOR):
            fails.append("the wrap step is the loop's biggest jump (seam pop)")
    if a.seam:
        sf = np.asarray(Image.open(a.seam).convert("RGB"), dtype=np.float32)
        d = np.abs(first - sf)
        mse = (d ** 2).mean()
        psnr = float("inf") if mse == 0 else 10 * np.log10(255 ** 2 / mse)
        print(f"seam: frame {loop_n} vs 0: PSNR {psnr:.1f} dB, max diff {d.max():.0f}")
        if psnr < SEAM_MIN_DB:
            fails.append(f"seam PSNR {psnr:.1f} dB < {SEAM_MIN_DB}")
    elif looped and not a.video:
        fails.append("no --seam frame given")

    print("RESULT: PASS" if not fails else "RESULT: FAIL: " + "; ".join(fails))
    sys.exit(0 if not fails else 1)


if __name__ == "__main__":
    main()
