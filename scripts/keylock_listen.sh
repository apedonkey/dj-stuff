#!/usr/bin/env bash
# keylock_listen.sh: a listening test for key lock. Copies one of your tracks from the headset (read only), cuts an
# excerpt, plays it through key lock (scripts/keylock_render.cpp, built with MSVC 2022) at +8 % and -8 % with several
# window sizes, and saves MP3s and 24-bit WAVs to out/keylock_listen/<track>/ for A/B listening. All files get the
# same gain, chosen so none clips. It also checks that the key stayed put (see the check below).
#   keylock_listen.sh ["/sdcard/Music/<file>"] [start seconds] [length seconds]
set -u -o pipefail
REPO="$(cd "$(dirname "$0")/.." && pwd)"
ADB_EXE="$REPO/tools/platform-tools/adb.exe"
SERIAL="${SERIAL:-2G0YC1ZF96072F}"
adb() { MSYS_NO_PATHCONV=1 "$ADB_EXE" -s "$SERIAL" "$@"; }
win() { cygpath -w "$1"; }
TRACK="${1:-/sdcard/Music/NEW MUSIC FOR OCULUS/ICETROUT-CHIMERA.wav}"
START="${2:-95.4}"
LEN="${3:-30}"
NAME="$(basename "$TRACK")"
NAME="${NAME%.*}"
OUT="$REPO/out/keylock_listen"
DIR="$OUT/$NAME"
SRC="$OUT/src/$(basename "$TRACK")"
mkdir -p "$OUT/src" "$DIR"
if [[ ! -f "$SRC" ]]; then
    adb pull "$TRACK" "$(cygpath -m "$SRC")" >/dev/null || { echo "pull failed: $TRACK"; exit 1; }
fi

VS="$("/c/Program Files (x86)/Microsoft Visual Studio/Installer/vswhere.exe" -latest -products '*' \
    -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 -property installationPath | tr -d '\r')"
cat > "$OUT/build.bat" <<EOF
@echo off
set "PATH=%ProgramFiles(x86)%\Microsoft Visual Studio\Installer;%PATH%"
call "$VS\VC\Auxiliary\Build\vcvars64.bat" >nul || exit /b 1
cd /d "$(win "$OUT")"
cl /nologo /O2 /EHsc /std:c++17 /W3 /I "$(win "$REPO/out/third_party/signalsmith-stretch")" /I "$(win "$REPO/out/third_party/signalsmith-linear/include")" /Fe:keylock_render.exe "$(win "$REPO/scripts/keylock_render.cpp")"
EOF
powershell.exe -NoProfile -Command "& '$(win "$OUT/build.bat")'; exit \$LASTEXITCODE" >/dev/null || { echo "build failed"; exit 1; }

ffmpeg -v error -y -ss "$START" -t "$LEN" -i "$(win "$SRC")" -ac 2 -af aresample=48000:resampler=soxr -f f32le \
    "$(win "$DIR/0.f32")" || { echo "excerpt failed"; exit 1; }

# tag | file name | renderer options
SETTINGS=(
    "1|1 - original|"
    "2|2 - key lock +8% - 120 ms window (60 ms delay)|--ratio 1.08"
    "3|3 - key lock +8% - 100 ms cheaper (90 ms delay)|--ratio 1.08 --preset cheaper"
    "4|4 - key lock +8% - 60 ms window (45 ms delay)|--ratio 1.08 --preset custom --win 60 --hop 15 --split 1"
    "5|5 - key lock +8% - 40 ms window (30 ms delay)|--ratio 1.08 --preset custom --win 40 --hop 10 --split 1"
    "6|6 - key lock -8% - 120 ms window (60 ms delay)|--ratio 0.92"
    "7|7 - key lock -8% - 40 ms window (30 ms delay)|--ratio 0.92 --preset custom --win 40 --hop 10 --split 1"
)
for s in "${SETTINGS[@]}"; do
    IFS='|' read -r tag file opts <<< "$s"
    if [[ "$tag" == 1 ]]; then
        cp "$DIR/0.f32" "$DIR/1.f32"
    else
        # shellcheck disable=SC2086
        "$OUT/keylock_render.exe" "$(win "$DIR/0.f32")" "$(win "$DIR/$tag.f32")" $opts | tr -d '\r' || exit 1
    fi
done

# The key check, over the same stretch of music in every file (scaled by its ratio):
# - the strongest bass frequency (one long FFT, 0.05 Hz steps);
# - "key match": how alike the energy per note name (C, C#, ... B, 100-2000 Hz) is to the original's (1 = same).
# Each is shown next to what a plain speed-up (no key lock) would give. Stretching raises peaks, so it also prints
# one gain for every file that puts the loudest peak at -0.3 dBFS. -P, not -I: numpy is in the user site-packages.
GAIN=$(python -P - "$DIR" "$LEN" <<'PY'
import sys, numpy as np
d, length = sys.argv[1], float(sys.argv[2])
rate, n, hop = 48000, 8192, 4096
ratios = {"1": 1.0, "2": 1.08, "3": 1.08, "4": 1.08, "5": 1.08, "6": 0.92, "7": 0.92}
fbin = np.fft.rfftfreq(n, 1 / rate)

def segment(x, r):
    return x[int(rate * 6 / r):int(rate * min(length - 2, 26) / r)].mean(axis=1)

def stft(m):
    w = np.hanning(n)
    return np.array([np.abs(np.fft.rfft(m[i:i + n] * w)) for i in range(0, len(m) - n, hop)])

def chroma(mag, scale=1.0):
    f = fbin * scale
    keep = (f >= 100) & (f < 2000)
    pc = np.round(12 * np.log2(f[keep] / 440) + 69).astype(int) % 12
    c = np.bincount(pc, weights=(mag[:, keep] ** 2).sum(axis=0), minlength=12)
    return c / np.linalg.norm(c)

def bass(m, scale=1.0):
    spec = np.abs(np.fft.rfft(m * np.hanning(len(m))))
    f = np.fft.rfftfreq(len(m), 1 / rate) * scale
    keep = (f >= 30) & (f < 150)
    return f[keep][np.argmax(spec[keep])]

files = {t: np.fromfile(f"{d}/{t}.f32", dtype=np.float32).reshape(-1, 2) for t in ratios}
m0 = segment(files["1"], 1.0)
mag0 = stft(m0)
c0 = chroma(mag0)
loudest = 0
for t, r in ratios.items():
    x = files[t]
    m = segment(x, r)
    peak = np.abs(x).max()
    loudest = max(loudest, peak)
    line = (f"{t}: {len(x) / rate:5.2f} s, peak {20 * np.log10(peak):+5.1f} dBFS, bass {bass(m):5.2f} Hz,"
            f" key match {float(c0 @ chroma(stft(m))):.3f}")
    if r != 1.0:
        line += f" (plain speed-up: bass {bass(m0, r):5.2f} Hz, key match {float(c0 @ chroma(mag0, r)):.3f})"
    print(line, file=sys.stderr)
print(f"{-0.3 - 20 * np.log10(loudest):.2f}")
PY
) || { echo "check failed"; exit 1; }
echo "gain for every file: ${GAIN} dB"

for s in "${SETTINGS[@]}"; do
    IFS='|' read -r tag file opts <<< "$s"
    for fmt in "mp3|-c:a libmp3lame -b:a 320k" "wav|-c:a pcm_s24le"; do
        IFS='|' read -r ext codec <<< "$fmt"
        # shellcheck disable=SC2086
        ffmpeg -v error -y -f f32le -ar 48000 -ac 2 -i "$(win "$DIR/$tag.f32")" -af "volume=${GAIN}dB" $codec \
            "$(win "$DIR/$file.$ext")" || exit 1
    done
done
rm -f "$DIR"/*.f32
echo "files: $DIR"
