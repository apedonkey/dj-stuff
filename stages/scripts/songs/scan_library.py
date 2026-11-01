"""Scan the user's music on the Quest for the song-synced light show. The user (2026-10-06): "is it possible to do
lasers for any song??", "my songs are on the oculus itself", "there is a SHIT TON of songs", "ok start the scan".

Every audio file under /sdcard/Music on the headset is pulled into a private temp folder, measured, and deleted again;
only compact features stay (Songs/features/<id>.npz), so the light scripts can be regenerated and tuned without pulling
6.5 GB again. Songs/index.jsonl records every track (append-only; the last line per path wins). Re-running skips the
tracks already scanned and redoes any whose size or date changed, so it doubles as "scan the new songs".

Features, from 22050 Hz mono:
- bands_db  (5, N) float16: energy in dB every 0.1 s; bands sub 30-100, low 100-250, mid 250-2k, high 2k-8k, air 8k+ Hz
- onset     (M,) float16: librosa onset strength, 43 Hz frames (hop 512)
- beats     (K,) float32: librosa beat times in s (prior 140 BPM); tempo in the index
Long files are processed in 60 s chunks, so memory stays bounded for hour-long recordings.

Run (from anywhere; -P keeps the data folder off sys.path):
    python -P scan_library.py [--workers 3] [--limit N]
"""
import argparse
import hashlib
import json
import os
import shutil
import subprocess
import time
from concurrent.futures import ProcessPoolExecutor, as_completed

ADB = r"C:\Users\Chris\OneDrive\Desktop\tribe hack\tools\platform-tools\adb.exe"
SERIAL = "2G0YC1ZF96072F"
ROOT = r"C:\Users\Chris\TribeUE\Songs"
REMOTE = "/sdcard/Music"
EXTS = (".mp3", ".wav", ".flac", ".m4a", ".aif", ".aiff", ".ogg")
SR, HOP, NFFT = 22050, 512, 2048
BANDS = ((30, 100), (100, 250), (250, 2000), (2000, 8000), (8000, 11025))
CHUNK_S = 60.0


def adb(*args):
    return subprocess.run([ADB, "-s", SERIAL, *args], capture_output=True)


def list_remote():
    r = adb("shell", f"find {REMOTE} -type f -exec stat -c '%s|%Y|%n' {{}} +")
    files = []
    for line in r.stdout.decode("utf-8", "replace").splitlines():
        parts = line.strip().split("|", 2)
        if len(parts) == 3 and parts[2].lower().endswith(EXTS):
            files.append({"path": parts[2], "size": int(parts[0]), "mtime": int(parts[1])})
    return files


def load_mono(path):
    import librosa
    import numpy as np
    import soundfile as sf
    try:
        y, sr = sf.read(path, dtype="float32", always_2d=True)
        y = y.mean(axis=1)
        if sr != SR:
            y = librosa.resample(y, orig_sr=sr, target_sr=SR, res_type="soxr_hq")
    except Exception:                                                    # m4a & co: audioread
        try:
            y, _ = librosa.load(path, sr=SR, mono=True)
        except Exception:                                                # no audioread backend: ffmpeg's CLI decodes it
            ff = shutil.which("ffmpeg") or os.path.expandvars(r"%LOCALAPPDATA%\Microsoft\WinGet\Links\ffmpeg.exe")
            r = subprocess.run([ff, "-v", "error", "-i", path, "-f", "f32le", "-ac", "1", "-ar", str(SR), "-"],
                               capture_output=True)
            if r.returncode != 0 or not r.stdout:
                raise RuntimeError("ffmpeg could not decode it: " + r.stderr.decode("utf-8", "replace")[-200:])
            y = np.frombuffer(r.stdout, dtype=np.float32)
    return np.ascontiguousarray(y, dtype=np.float32)


def extract(path):
    import librosa
    import numpy as np
    y = load_mono(path)
    dur = len(y) / SR
    f = librosa.fft_frequencies(sr=SR, n_fft=NFFT)
    masks = [(f >= lo) & (f < hi) for lo, hi in BANDS]
    melfb = librosa.filters.mel(sr=SR, n_fft=NFFT, n_mels=128)
    band_parts, mel_parts = [], []
    yp = np.pad(y, (NFFT // 2, NFFT // 2))                              # librosa's centred frames: frame k at k*HOP
    nfr = 1 + (len(yp) - NFFT) // HOP
    per = int(CHUNK_S * SR) // HOP                                       # frames per chunk
    for k0 in range(0, nfr, per):
        k1 = min(nfr, k0 + per)
        seg = yp[k0 * HOP:(k1 - 1) * HOP + NFFT]                         # exactly frames k0 .. k1-1
        S = np.abs(librosa.stft(seg, n_fft=NFFT, hop_length=HOP, center=False)) ** 2
        band_parts.append(np.stack([S[m].sum(axis=0) for m in masks]))
        mel_parts.append(melfb @ S)
    E = np.concatenate(band_parts, axis=1)                               # (5, frames) at SR/HOP Hz
    mel = np.concatenate(mel_parts, axis=1)
    onset = librosa.onset.onset_strength(S=librosa.power_to_db(mel), sr=SR, hop_length=HOP)
    tempo, beats = librosa.beat.beat_track(onset_envelope=onset, sr=SR, hop_length=HOP, start_bpm=140.0, units="time")
    # 0.1 s frames: mean energy per bin, in dB
    fps = SR / HOP
    n10 = max(1, int(np.ceil(dur * 10)))
    bins = np.minimum((np.arange(E.shape[1]) / fps * 10).astype(int), n10 - 1)
    acc = np.zeros((5, n10))
    cnt = np.bincount(bins, minlength=n10).astype(float)
    for b in range(5):
        acc[b] = np.bincount(bins, weights=E[b], minlength=n10)
    acc /= np.maximum(cnt, 1)
    bands_db = (10 * np.log10(acc + 1e-12)).astype(np.float16)
    return {"bands_db": bands_db, "onset": onset.astype(np.float16), "beats": np.asarray(beats, np.float32)}, dur, \
        float(np.atleast_1d(tempo)[0])


def work(item):
    import numpy as np
    tmp = os.path.join(ROOT, "_tmp")
    os.makedirs(tmp, exist_ok=True)
    local = os.path.join(tmp, item["id"] + os.path.splitext(item["path"])[1].lower())
    t0 = time.time()
    r = adb("pull", item["path"], local)
    if r.returncode != 0 or not os.path.exists(local):
        return dict(item, status="pull failed", err=r.stderr.decode("utf-8", "replace")[-200:])
    t1 = time.time()
    try:
        arrays, dur, tempo = extract(local)
    except Exception as e:  # noqa: BLE001
        return dict(item, status="analysis failed", err=repr(e)[-300:])
    finally:
        try:
            os.remove(local)
        except OSError:
            pass
    np.savez_compressed(os.path.join(ROOT, "features", item["id"] + ".npz"), **arrays)
    return dict(item, status="ok", duration=round(dur, 2), tempo=round(tempo, 2), t_pull=round(t1 - t0, 2),
                t_analysis=round(time.time() - t1, 2))


def folder_rank(path):
    """Set / stream folders first: they're the ones the user plays out."""
    d = path.split("/")[-2].lower()
    return (0 if any(k in d for k in ("set", "stream", "twitch")) else 1, d, path)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--workers", type=int, default=3)
    ap.add_argument("--limit", type=int, default=0)
    args = ap.parse_args()
    os.makedirs(os.path.join(ROOT, "features"), exist_ok=True)
    idx_path = os.path.join(ROOT, "index.jsonl")
    done = {}
    if os.path.exists(idx_path):
        for line in open(idx_path, encoding="utf-8"):
            try:
                e = json.loads(line)
            except ValueError:
                continue
            done[e["path"]] = (e["size"], e["mtime"]) if e.get("status") == "ok" else None
    files = list_remote()
    if not files:
        print("[SCAN] no audio files found (headset connected?)", flush=True)
        return
    todo = [dict(f, id=hashlib.sha1(f["path"].encode("utf-8")).hexdigest()[:16]) for f in files
            if done.get(f["path"]) != (f["size"], f["mtime"])]
    todo.sort(key=lambda it: folder_rank(it["path"]))
    n_done = len(files) - len(todo)
    if args.limit:
        todo = todo[:args.limit]
    gb = sum(it["size"] for it in todo) / 1e9
    print(f"[SCAN] {len(files)} audio files on the headset; {n_done} already scanned; "
          f"{len(todo)} to do this run ({gb:.2f} GB), {args.workers} workers", flush=True)
    t0, ok, bad = time.time(), 0, 0
    with ProcessPoolExecutor(args.workers) as ex, open(idx_path, "a", encoding="utf-8") as idx:
        futs = [ex.submit(work, it) for it in todo]
        for k, fu in enumerate(as_completed(futs), 1):
            try:
                res = fu.result()
            except Exception as e:  # noqa: BLE001  (a crashed worker)
                res = {"path": "?", "size": 0, "mtime": 0, "status": "worker crashed", "err": repr(e)[-300:]}
            idx.write(json.dumps(res, ensure_ascii=False) + "\n")
            idx.flush()
            if res["status"] == "ok":
                ok += 1
            else:
                bad += 1
                print(f"[SCAN] FAILED {res['status']}: {res['path']} :: {res.get('err', '')}", flush=True)
            if k % 25 == 0 or k == len(todo):
                el = time.time() - t0
                eta = el / k * (len(todo) - k)
                print(f"[SCAN] {k}/{len(todo)} ({ok} ok, {bad} failed) in {el / 60:.1f} min; "
                      f"{el / k:.1f} s/track; about {eta / 60:.0f} min left", flush=True)
    print(f"[SCAN] done: {ok} ok, {bad} failed, {(time.time() - t0) / 60:.1f} min", flush=True)


if __name__ == "__main__":
    main()
