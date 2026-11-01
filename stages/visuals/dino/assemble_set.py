"""Assemble the hour-long set from the finished loops (system Python 3 + numpy; ffmpeg on PATH).

  python assemble_set.py --plan [--intro-bars 96]             print the timeline only
  python assemble_set.py --out "../deliver/Dino Visuals - Full Set.mp4" [--intro-bars 96] [--minutes 60]

Timeline (140 BPM: 60:00 = 2100 bars): six acts of 352 bars (10:03; the last takes what is left) with an intensity arc
(Awakening, The Hunt, Impact, Primeval, Stampede, Afterglow). The set opens with Giant Halo for the giant intro:
96 bars (2:44.6) by default, the user's choice (2026-10-07): in the opener, SVDDEN DEATH - PRELUDE I, the DJ rises at
1:09 and lands at 2:46, so the Halo covers the rise and the 2-bar crossfade into the sting ends just before the
landing (--intro-bars changes it; a multiple of 16). Every act opens with 16 bars of the sting, then loop segments of
32 or 48 bars, so every boundary is a 16-bar
phrase; the last segment is a Lava Moon cut (the outro) and runs to the end. Loops are picked by energy for the act;
none plays twice within 10 minutes, the same concept never plays twice in a row, and the least-used loops go first so
every loop gets used. Crossfades last 2 bars and end exactly on the boundary: the incoming loop is pre-rolled so its
own swell leads into the phrase and its frame 0 lands on it. The set fades in from black over the first 2 bars and out
over the last 2. Blending happens in Y'CbCr (no color conversion); one x264 pass at ~6 Mbps.
Loops: renders/<concept>/<concept>_<variant>_<bpm>bpm_8bars_1080p30.mp4.
"""
import argparse
import glob
import math
import os
import random
import re
import subprocess
import sys
import time

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
W, H, FPS = 1920, 1080, 30
YSZ, CSZ = W * H, (W // 2) * (H // 2)
FRAME_BYTES = YSZ + 2 * CSZ                                       # yuv420p
# concept -> (display name, energy 1 calm .. 3 peak); variants may override the energy
CONCEPTS = {
    "fossil_scan": ("Fossil Scan", 1), "amber_dna": ("Amber DNA", 1), "lava_moon": ("Lava Moon", 1),
    "primeval_jungle": ("Primeval Jungle", 1), "raptor_run": ("Raptor Run", 2), "spine_tunnel": ("Spine Tunnel", 2),
    "stomp": ("Stomp", 3), "extinction_event": ("Extinction Event", 3), "sting": ("Stage Sting", 0),
    "giant_halo": ("Giant Halo", 0),
}
ENERGY = {("spine_tunnel", "amber"): 3, ("raptor_run", "stampede"): 3}
ACTS = [("Awakening", {1}), ("The Hunt", {1, 2}), ("Impact", {2, 3}), ("Primeval", {1}), ("Stampede", {2, 3}),
        ("Afterglow", {1, 2})]
ACT_BARS, INTRO_BARS, STING_BARS, XF_BARS, RECUR_MIN = 352, 96, 16, 2, 10.0
SPECIAL = ("sting", "giant_halo")                                  # placed by the plan, not picked from the pool
OUTRO = "lava_moon"                                                # the set ends on one of these


class Loop:
    def __init__(self, path, concept, variant):
        self.path, self.concept, self.variant = path, concept, variant
        self.name = f"{CONCEPTS[concept][0]} ({variant})"
        self.energy = ENERGY.get((concept, variant), CONCEPTS[concept][1])


def catalog(bpm):
    loops = []
    for path in sorted(glob.glob(os.path.join(ROOT, "renders", "*", f"*_{bpm}bpm_8bars_1080p30.mp4"))):
        concept = os.path.basename(os.path.dirname(path))
        m = re.fullmatch(rf"{concept}_(\w+?)_{bpm}bpm_8bars_1080p30\.mp4", os.path.basename(path))
        if concept in CONCEPTS and m:
            loops.append(Loop(path, concept, m.group(1)))
    return loops


def plan(loops, bpm, minutes, seed=7, intro_bars=INTRO_BARS):
    """[(start_bar, bars, loop, act)] covering the set; asserts the pack's sequencing rules. intro_bars: Giant Halo's
    opening (a whole number of 16-bar phrases, so the sting and every boundary after it stay on the phrase)."""
    assert intro_bars % 16 == 0 and intro_bars + STING_BARS < ACT_BARS, f"intro of {intro_bars} bars"
    rng = random.Random(seed)
    bar_s = 4 * 60.0 / bpm
    stings = sorted([lp for lp in loops if lp.concept == "sting"], key=lambda lp: lp.variant)
    intro = [lp for lp in loops if lp.concept == "giant_halo"]
    pool = [lp for lp in loops if lp.concept not in SPECIAL]
    rng.shuffle(pool)
    uses = {lp.path: [] for lp in pool}
    segs, bar, total = [], 0, int(round(minutes * 60 / bar_s))
    n_acts = max(1, min(len(ACTS), round(total / ACT_BARS)))       # 6 at 140 BPM: the last act gets 340 bars
    for a, (act, energies) in enumerate(ACTS[:n_acts]):
        act_end = total if a == n_acts - 1 else (a + 1) * ACT_BARS
        if a == 0 and intro:
            segs.append((bar, intro_bars, intro[0], act))
            bar += intro_bars
        if stings:
            segs.append((bar, STING_BARS, stings[a % len(stings)], act))
            bar += STING_BARS
        lengths = []
        while bar + sum(lengths) < act_end:
            left = act_end - bar - sum(lengths)
            if left in (48, 80):
                lengths.append(48)
            elif left < 64 and act_end == total:                    # the set's last segment runs to the end
                lengths.append(left)
            else:
                lengths.append(min(32, left))
        prev = segs[-1][2] if segs else None
        for i, n in enumerate(lengths):
            t = bar * bar_s / 60
            last = bar + n == total
            before_last = act_end == total and i == len(lengths) - 2   # keep the outro concept free for the end

            def allowed(lp):
                return ((prev is None or lp.concept != prev.concept) and all(t - u >= RECUR_MIN for u in uses[lp.path])
                        and not (before_last and lp.concept == OUTRO))
            ok = [lp for lp in pool if allowed(lp) and (lp.concept == OUTRO if last else lp.energy in energies)]
            if not ok:                                              # relax the energy match before the recurrence rule
                ok = [lp for lp in pool if allowed(lp)]
            recent = {sg[2].concept for sg in segs[-3:]}             # spread concepts, not just variants
            lp = min(ok, key=lambda x: (len(uses[x.path]), x.concept in recent,
                                        uses[x.path][-1] if uses[x.path] else -1e9))
            uses[lp.path].append(t)
            segs.append((bar, n, lp, act))
            bar += n
            prev = lp
    unused = [lp.name for lp in pool if not uses[lp.path]]
    assert not unused, f"loops never used: {unused}"
    assert bar == total, f"plan covers {bar} of {total} bars"
    for (b0, n0, l0, _), (b1, _, l1, _) in zip(segs, segs[1:]):
        assert b0 + n0 == b1 and l0.path != l1.path and b1 % 16 == 0
    return segs


def reader(path, skip):
    """Decoded yuv420p frames of a loop, looping forever, starting `skip` frames in."""
    p = subprocess.Popen(["ffmpeg", "-v", "error", "-stream_loop", "-1", "-i", path, "-f", "rawvideo",
                          "-pix_fmt", "yuv420p", "-"], stdout=subprocess.PIPE, bufsize=FRAME_BYTES * 4)
    for _ in range(skip):
        p.stdout.read(FRAME_BYTES)
    return p


def frame(p):
    buf = p.stdout.read(FRAME_BYTES)
    assert len(buf) == FRAME_BYTES, "decoder ended early"
    return np.frombuffer(buf, np.uint8)


def to_black(f, a):
    """Fade a yuv420p frame toward video black (Y 16, Cb/Cr 128) by factor a in [0, 1]."""
    g = f.astype(np.int16)
    g[:YSZ] = 16 + ((g[:YSZ] - 16) * a)
    g[YSZ:] = 128 + ((g[YSZ:] - 128) * a)
    return g.astype(np.uint8)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out")
    ap.add_argument("--plan", action="store_true")
    ap.add_argument("--minutes", type=float, default=60.0)
    ap.add_argument("--intro-bars", type=int, default=INTRO_BARS,
                    help="Giant Halo's opening in bars (multiple of 16; default 96 = 2:44.6 at 140 BPM)")
    ap.add_argument("--bpm", type=int, default=140)
    ap.add_argument("--preset", default="medium")
    ap.add_argument("--bitrate", default="6M")
    a = ap.parse_args()
    fpb = FPS * 60.0 / a.bpm
    bar_f = 4 * fpb
    loop_n = int(round(32 * fpb))
    loops = catalog(a.bpm)
    segs = plan(loops, a.bpm, a.minutes, intro_bars=a.intro_bars)
    total = int(round(segs[-1][0] * bar_f + segs[-1][1] * bar_f))
    xf = int(XF_BARS * bar_f)
    lines = []
    for b, n, lp, act in segs:
        s = b * bar_f / FPS
        lines.append(f"{int(s // 60):02d}:{s % 60:05.2f}  {act:<10} {n:>3} bars  {lp.name}")
    print(f"{len(loops)} loops, {len(segs)} segments, {total} frames ({total / FPS / 60:.2f} min)")
    print("\n".join(lines))
    if a.plan or not a.out:
        return
    with open(os.path.splitext(a.out)[0] + " - timeline.txt", "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")

    sys.exit(render_set(segs, a.out, a.bpm, a.preset, a.bitrate))


def render_set(segs, out, bpm, preset="medium", bitrate="6M"):
    """Decode, crossfade and encode the timeline; returns the encoder's exit code."""
    fpb = FPS * 60.0 / bpm
    bar_f = 4 * fpb
    loop_n = int(round(32 * fpb))
    total = int(round((segs[-1][0] + segs[-1][1]) * bar_f))
    xf = int(XF_BARS * bar_f)
    enc = subprocess.Popen(
        ["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "yuv420p", "-s", f"{W}x{H}", "-r", str(FPS),
         "-color_range", "tv", "-colorspace", "bt709", "-color_primaries", "bt709", "-color_trc", "bt709",
         "-i", "-", "-c:v", "libx264", "-preset", preset, "-profile:v", "high", "-level", "4.0",
         "-b:v", bitrate, "-maxrate", "8M", "-bufsize", "12M", "-g", "60", "-pix_fmt", "yuv420p",
         "-color_range", "tv", "-colorspace", "bt709", "-color_primaries", "bt709", "-color_trc", "bt709",
         "-movflags", "+faststart", "-an", out], stdin=subprocess.PIPE)
    starts = [int(round(b * bar_f)) for b, _, _, _ in segs] + [total]
    cur = reader(segs[0][2].path, 0)
    nxt, si, t0 = None, 0, time.time()
    for g in range(total):
        nb = starts[si + 1]
        if si + 1 < len(segs) and g == nb - xf:                    # pre-roll the next loop so frame 0 lands on nb
            nxt = reader(segs[si + 1][2].path, (loop_n - xf % loop_n) % loop_n)
        if g == nb:
            cur.kill()
            cur, nxt, si = nxt, None, si + 1
            nb = starts[si + 1]
        f = frame(cur)
        if nxt is not None:
            w = (g - (nb - xf) + 1) / (xf + 1)
            w = w * w * (3 - 2 * w)
            f = (f.astype(np.float32) * (1 - w) + frame(nxt).astype(np.float32) * w + 0.5).astype(np.uint8)
        if g < xf:
            f = to_black(f, (g + 1) / (xf + 1))
        elif g >= total - xf:
            f = to_black(f, (total - g) / (xf + 1))
        enc.stdin.write(f.tobytes())
        if g % 9000 == 8999:
            el = time.time() - t0
            print(f"  {(g + 1) / FPS / 60:.0f} min encoded, {(g + 1) / el:.1f} fps, "
                  f"eta {(total - g - 1) / ((g + 1) / el) / 60:.0f} min", flush=True)
    cur.kill()
    enc.stdin.close()
    enc.wait()
    print(f"done: {out}, {total} frames in {(time.time() - t0) / 60:.1f} min ({total / (time.time() - t0):.1f} fps)")
    return enc.returncode


if __name__ == "__main__":
    main()
