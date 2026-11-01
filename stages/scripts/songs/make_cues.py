"""Light scripts for every scanned song (scan_library.py features -> Songs/cues/<key>.txt), in the mod's song.txt
format, so the Dino Stage's show follows each track's sections: intro, build, a dark gap where the track has one, drop,
breakdown, outro. The cue times sit on the measured hits (the 0.1 s frame of the steepest rise), not on a guessed grid.

A hand-tuned script in Songs/overrides/<file name>.txt (e.g. the opener with its lift) replaces the generated one.
The mod finds a track's script by key = FNV-1a 64 of the track's file name, lower-cased (hook song_key()).

    python -P make_cues.py                      all scanned tracks -> Songs/cues
    python -P make_cues.py --show NAME          print the sections of tracks whose name contains NAME
    python -P make_cues.py --local FILE.mp3     analyse a file on this PC and print its sections (no output files)
"""
import argparse
import importlib.util
import json
import os
import shutil

import numpy as np

ROOT = r"C:\Users\Chris\TribeUE\Songs"
HERE = os.path.dirname(os.path.abspath(__file__))
FR = 10.0                                             # feature frames per second (scan_library bands_db)


def hook_name(name):
    """The file name as the hook reads it from the deck (read_fstring: each UTF-16 unit < 0x80 kept, others '?')."""
    u = name.encode("utf-16-le")
    return "".join(chr(c) if c < 0x80 else "?" for c in (u[i] | (u[i + 1] << 8) for i in range(0, len(u), 2)))


def song_key(name):
    """FNV-1a 64 over hook_name(name) with ASCII letters lower-cased, as 16 hex digits; the hook computes the same."""
    h = 0xCBF29CE484222325
    for ch in hook_name(name):
        b = ord(ch)
        if 65 <= b <= 90:
            b += 32
        h = ((h ^ b) * 0x100000001B3) & 0xFFFFFFFFFFFFFFFF
    return f"{h:016x}"


def smooth(x, sec):
    n = max(1, int(round(sec * FR)))
    k = np.ones(n) / n
    pad = np.pad(x, (n // 2, n - 1 - n // 2), mode="edge")
    return np.convolve(pad, k, mode="valid")


def estimate_bpm(onset, beats):
    """The track's tempo. librosa's own estimate is quantised (136 / 143.55 near 140), so: a coarse tempo from the
    beat track's median interval (folded into 100-175 BPM), refined at the 16-beat lag of the onset envelope's
    autocorrelation (a local peak within +-4 %, parabolic interpolation). Within 0.35 BPM of a whole number it snaps."""
    fps = 22050 / 512
    if len(beats) < 16:
        return 140.0
    ib = np.diff(beats)
    ib = ib[(ib > 0.25) & (ib < 1.2)]
    if len(ib) < 8:
        return 140.0
    raw = 60.0 / np.median(ib)
    cands = [raw * m * 2.0 ** k for m in (1.0, 1.5, 0.75) for k in range(-3, 4)]
    cands = [c for c in cands if 100 <= c < 176]                       # x2 folding, or 3:2 when it locked on triplets
    plain =[c for c in cands if abs(c / raw - round(c / raw)) < 1e-6 or abs(raw / c - round(raw / c)) < 1e-6]
    bpm = plain[0] if plain else min(cands, key=lambda c: abs(c - 145)) if cands else 140.0
    if onset is not None and len(onset) > fps * 30:
        o = onset.astype(np.float64)
        o = o - o.mean()
        lag0 = 16 * 60.0 * fps / bpm
        w0, w1 = int(lag0 * 0.96), int(lag0 * 1.04) + 2
        if w1 + 1 < len(o):
            ac = np.array([np.dot(o[:-k], o[k:]) for k in range(w0 - 1, w1 + 2)])
            pk = [i for i in range(1, len(ac) - 1) if ac[i] >= ac[i - 1] and ac[i] >= ac[i + 1]]
            if pk:
                i = max(pk, key=lambda j: ac[j])
                y0, y1, y2 = ac[i - 1], ac[i], ac[i + 1]
                den = y0 - 2 * y1 + y2
                kf = (w0 - 1 + i) + (0.5 * (y0 - y2) / den if den != 0 else 0.0)
                bpm = 60.0 * fps * 16 / kf
    r = round(bpm)
    return float(r) if abs(bpm - r) < 0.35 else round(bpm, 2)


def sections(bands_db, beats, dur, onset=None):
    """([(t, look)], bpm) for one track, or None when it has under 20 s of sound."""
    E = bands_db.astype(np.float64)
    P = 10 ** (E / 10)
    L = 10 * np.log10(P.sum(axis=0) + 1e-12)                          # loudness
    S = E[0]                                                           # sub 30-100 Hz
    n = len(L)
    top = np.percentile(L, 99)
    alive = L > top - 40                                               # not silence
    if alive.sum() < FR * 20:
        return None
    Ls, Ss = smooth(L, 2.0), smooth(S, 2.0)
    Lref, Sref = np.percentile(Ls[alive], 97), np.percentile(Ss[alive], 97)
    bpm = estimate_bpm(onset, beats)
    bar = 240.0 / bpm

    def hit(t_frame, back=2.0, fwd=1.0):
        """Where a section really starts near t_frame: the first strong rise of the mix (plus a quarter of the sub's: the
        bass may land a beat later) that STAYS up for a second. A stutter build's hits are cut by the next short gap,
        which shows at 0.1 s as a dip of 12-50 dB (PRELUDE I: drop 2 lands at 199.7 s after gaps at 197.8, 198.7, 199.5)."""
        a, b = max(1, int(t_frame - back * FR)), min(n - 4, int(t_frame + fwd * FR))
        if b <= a:
            return int(t_frame)
        jump = (L[a + 3:b + 3] - L[a:b]) + 0.25 * np.maximum(S[a + 3:b + 3] - S[a:b], 0)
        if jump.max() <= 0:
            return int(t_frame)

        def impact(k):                                                 # the frame inside that 0.3 s rise that jumps most
            i = a + k
            return i + 1 + int(np.argmax(L[i + 1:i + 4] - L[i:i + 3]))
        thr = min(10.0, 0.5 * jump.max())                             # a deep stutter gap must not hide a 17 dB drop
        for k in range(len(jump)):
            if jump[k] < thr:
                continue
            h = impact(k)
            w = L[h:h + int(FR)]
            if len(w) and np.median(w) - w.min() < 10 and w.mean() > Lref - 6:
                return h
        return impact(int(np.argmax(jump)))

    # 1) frame labels: drop (near the loud ceiling, sub near its ceiling), gap (silence), else "rest"
    raw = (Ls > Lref - 4.0) & (Ss > Sref - 8.0) & alive
    drop = (smooth(raw.astype(float), 5.0) >= 0.5) & alive             # majority over 5 s: a drop's dips don't split it
    lab = np.where(~alive, 2, np.where(drop, 1, 0))                     # 0 rest, 1 drop, 2 gap
    for _ in range(3):                                                 # runs under 6 s (not gaps) join a neighbour
        runs = np.flatnonzero(np.diff(np.r_[-1, lab, -1]))
        for s0, e0 in zip(runs[:-1], runs[1:]):
            if lab[s0] != 2 and e0 - s0 < 6 * FR:
                left = lab[s0 - 1] if s0 > 0 else None
                right = lab[e0] if e0 < n else None
                if left == 2 and right == 2 and e0 - s0 < 0.5 * FR:          # a blip between two gaps: one stutter gap
                    fill = 2
                else:
                    k0 = int(np.searchsorted(runs, s0))                     # this run's index in runs
                    ls = (s0 - runs[k0 - 1]) if left not in (None, 2) and k0 > 0 else -1
                    rs = (runs[k0 + 2] - e0) if right not in (None, 2) and k0 + 2 < len(runs) else -1
                    fill = left if ls >= rs and ls >= 0 else right if rs >= 0 else lab[s0]   # the longer neighbour
                lab[s0:e0] = fill
    runs = np.flatnonzero(np.diff(np.r_[-1, lab, -1]))
    segs = [(int(s0), int(e0), int(lab[s0])) for s0, e0 in zip(runs[:-1], runs[1:])]
    # 2) boundaries: run starts (a drop at its real hit), plus level moves of > 6 dB (4 s either side) in long rests
    lv = Ls + 0.5 * Ss
    bounds = []
    for s0, e0, v in segs:
        if v == 1:
            bounds.append((hit(s0), "drop"))
        elif v == 2:
            if e0 - s0 >= 0.4 * FR:                                    # a blink under 0.4 s is no blackout
                bounds.append((s0, "gap"))
        else:
            bounds.append((s0, "rest"))
            i = s0 + int(8 * FR)
            while i < e0 - int(8 * FR):
                before, after = lv[i - int(4 * FR):i].mean(), lv[i:i + int(4 * FR)].mean()
                if abs(after - before) > 6.0:
                    bounds.append((hit(i, back=3.0, fwd=1.0) if after > before else i, "rest"))
                    i += int(8 * FR)
                else:
                    i += int(FR // 2)
    bounds.sort()
    drops = [f for f, k in bounds if k == "drop"]
    first_drop = drops[0] if drops else n
    # 3) labels from each section's own average level
    cues = []
    for idx, (f0, kind) in enumerate(bounds):
        f1 = bounds[idx + 1][0] if idx + 1 < len(bounds) else n
        if kind == "drop":
            g = f0 - 1                                                 # a breath (>= 0.4 s of near-silence) before the hit
            while g > f0 - 3 * FR and g > 0 and L[g] < top - 30:
                g -= 1
            if f0 - g >= 0.4 * FR:
                cues.append(((g + 1) / FR, "dark"))
            cues.append((f0 / FR, "drop"))
        elif kind == "gap":
            cues.append((f0 / FR, "dark"))
        else:
            seg = slice(f0, max(f0 + 1, f1))
            quiet = Ss[seg].mean() < Sref - 20.0 or Ls[seg].mean() < Lref - 12.0
            look = "intro" if f0 < first_drop else ("breakdown" if quiet else "outro")
            cues.append((f0 / FR, look))
    cues.sort()
    # 4) builds: the section right before a drop becomes the build if it began within 16 bars of the hit (and after the
    #    track's first 8 bars); otherwise a build starts 8 bars before the hit
    out = []
    for t, look in cues:
        if look == "drop":
            prev = [i for i, c in enumerate(out) if c[1] != "dark"]
            if prev:
                j = prev[-1]
                pt, pl = out[j]
                tb = max(pt + 4.0, t - 8 * bar)
                if pl in ("intro", "outro", "breakdown") and t - pt <= 16 * bar and pt > 8 * bar:
                    out[j] = (pt, "build")
                elif pl != "build" and t - tb >= 4.0:
                    out.append((round(tb, 2), "build"))
        out.append((round(t, 2), look))
    out.sort()
    final = []
    for t, look in out:                                                # merge repeats and near-duplicates
        if final and final[-1][1] == look:
            continue
        if final and t - final[-1][0] < 1.0 and look != "drop" and final[-1][1] != "dark":
            continue                                                   # (a breath then the section: both stay)
        final.append((round(t, 2), look))
    end = round(dur - 0.5, 2)
    final = [c for c in final if c[0] < end - 0.5]                     # nothing after the hand-back to the show
    if len(final) > 1 and final[0][1] == "dark" and final[1][0] - final[0][0] < 1.0:
        final.pop(0)                                                   # a blink of silence at the very start
    if final and final[0][0] < 0.5:
        final[0] = (0.0, final[0][1])
    if not final or final[0][0] > 0.05:
        final.insert(0, (0.0, "dark" if L[: int(FR)].max() < top - 40 else "intro"))
    final.append((end, "show"))                                        # back to the free-running show
    return final, bpm


GRID_MIN_CONF = 1.7   # a grid is written only when its comb peak is this many times the median off-tempo score (2026-10-08:
                      # median 3.4 over the library; under 1.7 = DJ mixes with tempo changes, likely 2:3 tempo misreads)


def fit_grid(onset, bpm0, anchor=None):
    """(bpm, t0): the beat grid that best fits the whole track's onsets. Tribe's own grid can be off (2026-10-08: 142.38
    BPM for a 140 track; a first beat at 0.000 s that sits 40-70 ms before the hits on 5 of 9 tracks).
    Comb fit: the mean onset strength on the grid's beats, tempo within +-2.5 % of bpm0 (0.02 BPM steps, then 0.002),
    phase in 5 ms steps. A whole-number BPM scoring within 99.5 % of the best wins (DJ tracks sit on whole numbers).
    t0 = anchor (the first drop's hit, s) moved onto the grid, so beat 1 of a bar is the drop's beat; else the best phase.
    Returns (bpm, t0, conf): conf = the best score / the median score over the coarse tempo range."""
    fps = 22050 / 512
    o = onset.astype(np.float64)
    o = np.maximum(o - np.median(o), 0)
    n = len(o)
    if n < fps * 20 or bpm0 <= 0:
        return bpm0, 0.0, 0.0
    t_end = n / fps
    xs = np.arange(n) / fps

    def score(bpm, step):
        """(best mean onset on the beats, its phase) over phases 0 .. one beat in `step` s."""
        spb = 60.0 / bpm
        ph = np.arange(0.0, spb, step)
        beats = np.arange(0.0, t_end - spb - 0.05, spb)
        v = np.interp((beats[None, :] + ph[:, None]).ravel(), xs, o).reshape(len(ph), -1).mean(axis=1)
        i = int(np.argmax(v))
        return float(v[i]), float(ph[i])

    coarse = np.arange(bpm0 * 0.975, bpm0 * 1.025, 0.02)
    res = [(score(b, 0.01), b) for b in coarse]
    (_, _), b0 = max(res, key=lambda r: r[0][0])
    med = float(np.median([r[0][0] for r in res]))
    fine = np.arange(b0 - 0.03, b0 + 0.0301, 0.002)
    res = [(score(b, 0.005), b) for b in fine]
    (vb, phb), bb = max(res, key=lambda r: r[0][0])
    r = round(bb)
    if abs(r - bb) < 0.6:                                              # a whole number nearly as good: take it
        vr, phr = score(float(r), 0.005)
        if vr >= 0.995 * vb:
            bb, phb = float(r), phr
    spb = 60.0 / bb
    t0 = phb + round((anchor - phb) / spb) * spb if anchor is not None else phb   # the drop's beat, on the grid
    return round(float(bb), 3), round(float(t0), 4), (vb / med if med > 0 else 0.0)


def grid_line(gb, g0, conf):
    """The script's grid= line, or nothing when the fit is too weak (the hook then uses Tribe's grid)."""
    return f"grid={gb:g} {g0:g}\n" if conf >= GRID_MIN_CONF else ""


HIT_MINOR, HIT_MAJOR = 0.65, 0.85   # a 16th is a hit at this share of its bar's strongest onset (major: a big flash)
HIT_QUIET = 0.25                    # bars whose strongest onset is under this share of the song's loud level: no hits


def hit_map(onset, grid, dur):
    """[(t, major, intensity 0..1)]: the drum accents of a track for the lights. The onset peak near every 16th of the
    grid (-30 .. +50 ms); per bar, a 16th reaching HIT_MINOR of the bar's strongest is a hit (HIT_MAJOR: major), at most
    one per beat (the strongest: comfort, nothing flashes faster than the beat); t = the peak itself; intensity = the
    peak against the song's 95th-percentile 16th. Quiet bars (intros, breakdowns) give none."""
    fps = 22050 / 512
    o = onset.astype(np.float64)
    gb, g0 = grid
    s16 = 60.0 / gb / 4
    k = np.arange(int(np.ceil(-g0 / s16)), int(np.floor((dur - g0) / s16)) + 1)
    if len(k) < 64:
        return []
    c = np.round((g0 + k * s16) * fps).astype(int)
    win = np.clip(c[:, None] + np.arange(-1, 3)[None, :], 0, len(o) - 1)    # -23 .. +46 ms around each 16th
    vals = o[win]
    peak = vals.max(axis=1)
    at = win[np.arange(len(win)), vals.argmax(axis=1)] / fps
    loud = np.percentile(peak, 95) + 1e-9
    out = []
    bar = np.floor(k / 16).astype(int)
    for b in np.unique(bar):
        idx = np.where(bar == b)[0]
        m = peak[idx].max()
        if m < HIT_QUIET * loud:
            continue
        for beat in range(4):
            sl = idx[(k[idx] % 16) // 4 == beat]
            if len(sl) == 0:
                continue
            j = sl[np.argmax(peak[sl])]
            if peak[j] >= HIT_MINOR * m:
                out.append((float(at[j]), bool(peak[j] >= HIT_MAJOR * m), float(min(1.0, peak[j] / loud))))
    return out


def write_hits(path, hits):
    """songs/<key>.hits for the hook: little-endian uint32 per hit, (ms << 8) | (major << 7) | intensity (0..127)."""
    a = np.array([(int(round(t * 1000)) << 8) | (int(mj) << 7) | int(round(it * 127)) for t, mj, it in hits
                  if 0 <= t * 1000 < (1 << 24)], dtype="<u4")
    a.tofile(path)
    return len(a)


def hits_job(job):
    """One song's hit map (a worker): (key, npz path, grid, duration) -> (key, hits)."""
    key, npz, grid, dur = job
    return key, hit_map(np.load(npz)["onset"], grid, dur)


def main_hits():
    """Every script with a grid line gets songs/<key>.hits from its grid and the scanned onsets (parallel)."""
    from multiprocessing import Pool
    names = json.load(open(os.path.join(ROOT, "cues", "_names.json"), encoding="utf-8"))
    by = {}
    for line in open(os.path.join(ROOT, "index.jsonl"), encoding="utf-8"):
        try:
            e = json.loads(line)
        except ValueError:
            continue
        if e.get("status") == "ok":
            by.setdefault(e["path"].rsplit("/", 1)[-1], e)
    jobs = []
    for f in sorted(os.listdir(os.path.join(ROOT, "cues"))):
        if not f.endswith(".txt"):
            continue
        kv = dict(ln.split("=", 1) for ln in open(os.path.join(ROOT, "cues", f), encoding="utf-8").read().splitlines()
                  if "=" in ln)
        e = by.get(names.get(f[:-4], ""))
        if "grid" not in kv or not e:
            continue
        gb, g0 = map(float, kv["grid"].split())
        jobs.append((f[:-4], os.path.join(ROOT, "features", e["id"] + ".npz"), (gb, g0), e["duration"]))
    with Pool(5) as pool:
        res = pool.map(hits_job, jobs, chunksize=8)
    total = majors = 0
    for key, hits in res:
        total += write_hits(os.path.join(ROOT, "cues", key + ".hits"), hits)
        majors += sum(1 for h in hits if h[1])
    print(f"[HITS] {len(res)} hit maps, {total} hits ({majors} major) -> {os.path.join(ROOT, 'cues')}")


def bass_map(bands_db):
    """The bass level per 100 ms frame, 0..1: sub + low band energy (dB), from the song's quiet floor (its 15th
    percentile of the sounding frames) to its loud bass (99th), raised to 1.3 so only real bass reads high."""
    E = bands_db.astype(np.float64)
    b = 10 * np.log10(10 ** (E[0] / 10) + 10 ** (E[1] / 10))
    total = 10 * np.log10((10 ** (E / 10)).sum(axis=0) + 1e-12)
    sounding = total > np.percentile(total, 99) - 40
    if sounding.sum() < 50:
        return np.zeros(len(b))
    lo, hi = np.percentile(b[sounding], 15), np.percentile(b[sounding], 99)
    return np.clip((b - lo) / max(hi - lo, 1.0), 0.0, 1.0) ** 1.3


def bass_job(job):
    key, npz = job
    return key, bass_map(np.load(npz)["bands_db"])


def main_bass():
    """Every script gets songs/<key>.bass: one byte (0..255) per 100 ms of its bass level (parallel)."""
    from multiprocessing import Pool
    names = json.load(open(os.path.join(ROOT, "cues", "_names.json"), encoding="utf-8"))
    by = {}
    for line in open(os.path.join(ROOT, "index.jsonl"), encoding="utf-8"):
        try:
            e = json.loads(line)
        except ValueError:
            continue
        if e.get("status") == "ok":
            by.setdefault(e["path"].rsplit("/", 1)[-1], e)
    jobs = []
    for f in sorted(os.listdir(os.path.join(ROOT, "cues"))):
        e = by.get(names.get(f[:-4], "")) if f.endswith(".txt") else None
        if e:
            jobs.append((f[:-4], os.path.join(ROOT, "features", e["id"] + ".npz")))
    with Pool(5) as pool:
        res = pool.map(bass_job, jobs, chunksize=8)
    frames = 0
    for key, b in res:
        np.round(b * 255).astype(np.uint8).tofile(os.path.join(ROOT, "cues", key + ".bass"))
        frames += len(b)
    print(f"[BASS] {len(res)} bass maps, {frames / 36000:.1f} h of audio -> {os.path.join(ROOT, 'cues')}")


def load_scanner():
    spec = importlib.util.spec_from_file_location("scan_library", os.path.join(HERE, "scan_library.py"))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def fmt(cues):
    return " ".join(f"{t:g}:{look}" for t, look in cues)


def mmss(t):
    return f"{int(t // 60)}:{t % 60:05.2f}"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--show")
    ap.add_argument("--local")
    ap.add_argument("--hits", action="store_true")
    ap.add_argument("--bass", action="store_true")
    args = ap.parse_args()
    if args.hits:
        main_hits()
        return
    if args.bass:
        main_bass()
        return
    if args.local:
        arrays, dur, _ = load_scanner().extract(args.local)
        res = sections(arrays["bands_db"], arrays["beats"], dur, arrays["onset"])
        cues, bpm = res if res else ([], 140.0)
        print(f"{os.path.basename(args.local)}: {dur:.1f} s, {bpm} BPM")
        for t, look in cues:
            print(f"  {mmss(t)}  {look}")
        return
    entries = {}
    for line in open(os.path.join(ROOT, "index.jsonl"), encoding="utf-8"):
        try:
            e = json.loads(line)
        except ValueError:
            continue
        entries[e["path"]] = e
    out_dir = os.path.join(ROOT, "cues")
    os.makedirs(out_dir, exist_ok=True)
    ov_dir = os.path.join(ROOT, "overrides")
    overrides = {f.lower(): os.path.join(ov_dir, f) for f in os.listdir(ov_dir)} if os.path.isdir(ov_dir) else {}
    made = skipped = over = 0
    names = {}
    for path, e in sorted(entries.items()):
        if e.get("status") != "ok":
            continue
        name = path.rsplit("/", 1)[-1]
        if args.show and args.show.lower() not in name.lower():
            continue
        key = song_key(name)
        if name.lower() + ".txt" in overrides:
            if not args.show:
                txt = open(overrides[name.lower() + ".txt"], encoding="utf-8").read()
                if "grid=" not in txt:
                    kv = dict(ln.split("=", 1) for ln in txt.splitlines() if "=" in ln)
                    obpm = float(kv.get("bpm", "140"))
                    odrops = [float(c.split(":")[0]) for c in kv.get("cues", "").split() if c.endswith((":drop", ":top"))]
                    zo = np.load(os.path.join(ROOT, "features", e["id"] + ".npz"))
                    gl = grid_line(*fit_grid(zo["onset"], obpm, odrops[0] if odrops else None))
                    txt = txt.replace("bpm=" + kv["bpm"] + "\n", "bpm=" + kv["bpm"] + "\n" + gl, 1) \
                        if "bpm" in kv else gl + txt
                with open(os.path.join(out_dir, key + ".txt"), "w", encoding="utf-8", newline="\n") as f:
                    f.write(txt)
            over += 1
            names[key] = name
            continue
        z = np.load(os.path.join(ROOT, "features", e["id"] + ".npz"))
        res = sections(z["bands_db"], z["beats"], e["duration"], z["onset"])
        if not res:
            skipped += 1
            continue
        cues, bpm = res
        if args.show:
            drops = [t for t, look in cues if look in ("drop", "top")]
            gb, g0, gc = fit_grid(z["onset"], bpm, drops[0] if drops else None)
            print(f"{name}: {e['duration']:.1f} s, {bpm} BPM, grid {gb} BPM from {g0} s (conf {gc:.2f}"
                  f"{'' if gc >= GRID_MIN_CONF else ', too weak: not written'}), "
                  f"{sum(1 for c in cues if c[1] == 'drop')} drop(s)")
            for t, look in cues:
                print(f"  {mmss(t)}  {look}")
            continue
        drops = [t for t, look in cues if look in ("drop", "top")]
        gl = grid_line(*fit_grid(z["onset"], bpm, drops[0] if drops else None))
        body = f"match={hook_name(name)}\nbpm={bpm:g}\n{gl}cues={fmt(cues)}\n"
        while (len(body.encode("utf-8")) > 1100 or len(cues) > 46) and len(cues) > 2:
            cues = cues[:-2] + cues[-1:]                               # the hook reads <= 1150 bytes / 48 cues: trim the tail
            body = f"match={hook_name(name)}\nbpm={bpm:g}\n{gl}cues={fmt(cues)}\n"
        with open(os.path.join(out_dir, key + ".txt"), "w", encoding="utf-8", newline="\n") as f:
            f.write(body)
        names[key] = name
        made += 1
    if not args.show:
        with open(os.path.join(out_dir, "_names.json"), "w", encoding="utf-8") as f:
            json.dump(names, f, ensure_ascii=False, indent=0)
        print(f"[CUES] {made} generated, {over} hand-tuned, {skipped} skipped (too short / silent) -> {out_dir}")


if __name__ == "__main__":
    main()
