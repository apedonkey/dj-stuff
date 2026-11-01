#!/usr/bin/env bash
# keylock_bench.sh: builds scripts/keylock_bench.cpp for the Quest and runs it over adb.
# Measures how much CPU key lock (Signalsmith Stretch) takes for four stereo decks, per CPU core and per setting.
# Nothing is installed: the binary runs from /data/local/tmp and is deleted at the end. It refuses to run while
# Tribe is running (the test loads a core fully), unless FORCE=1. Results go to logs/keylock_bench_<time>.txt.
# Needs out/android-ndk-r26d and out/third_party/{signalsmith-stretch,signalsmith-linear} (see NOTES.md).
set -u -o pipefail
REPO="$(cd "$(dirname "$0")/.." && pwd)"
ADB_EXE="$REPO/tools/platform-tools/adb.exe"
SERIAL="${SERIAL:-2G0YC1ZF96072F}"
SECONDS_PER_RUN="${SECONDS_PER_RUN:-20}"
adb() { MSYS_NO_PATHCONV=1 "$ADB_EXE" -s "$SERIAL" "$@"; }
CXX="$REPO/out/android-ndk-r26d/toolchains/llvm/prebuilt/windows-x86_64/bin/clang++.exe"
OUT="$REPO/out/keylock_bench"
BIN=/data/local/tmp/keylock_bench
LOG="$REPO/logs/keylock_bench_$(date +%Y%m%d_%H%M%S).txt"

mkdir -p "$OUT" "$REPO/logs"
"$CXX" --target=aarch64-linux-android29 -O3 -std=c++17 -static-libstdc++ -Wall \
    -I "$REPO/out/third_party/signalsmith-stretch" -I "$REPO/out/third_party/signalsmith-linear/include" \
    -o "$OUT/keylock_bench" "$REPO/scripts/keylock_bench.cpp" || { echo "build failed"; exit 1; }
echo "built $(stat -c %s "$OUT/keylock_bench") B"

adb get-state >/dev/null 2>&1 || { echo "headset $SERIAL not connected over adb"; exit 1; }
if [[ -n "$(adb shell pidof com.TribeXR.TribeXR | tr -d '\r')" && "${FORCE:-0}" != 1 ]]; then
    echo "Tribe is running; close it first (or FORCE=1)"; exit 1
fi
adb push "$(cygpath -m "$OUT/keylock_bench")" "$BIN" >/dev/null && adb shell chmod 755 "$BIN" || { echo "push failed"; exit 1; }

{
    echo "# keylock_bench $(date '+%Y-%m-%d %H:%M:%S'), Signalsmith Stretch $(git -C "$REPO/out/third_party/signalsmith-stretch" rev-parse --short HEAD)"
    adb shell "getprop ro.product.model; dumpsys power | grep -m1 mWakefulness=; \
        for c in /sys/devices/system/cpu/cpu[0-9]*; do \
            echo \"\$(basename \$c) online=\$(cat \$c/online 2>/dev/null || echo 1) max=\$(cat \$c/cpufreq/cpuinfo_max_freq 2>/dev/null)\"; \
        done" | tr -d '\r'
} | tee "$LOG"

# Cores ranked by top frequency: fastest first.
mapfile -t CORES < <(adb shell 'for c in /sys/devices/system/cpu/cpu[0-9]*; do
    [ "$(cat $c/online 2>/dev/null || echo 1)" = 1 ] && echo "$(cat $c/cpufreq/cpuinfo_max_freq 2>/dev/null || echo 0) ${c##*cpu}"; done' \
    | tr -d '\r' | sort -rn | awk '{print $2}')
FAST="${CORES[0]}"; SLOW="${CORES[${#CORES[@]}-1]}"

run() { adb shell "$BIN --seconds $SECONDS_PER_RUN $*" | tr -d '\r' | tee -a "$LOG"; }
echo "## every core, default preset (120 ms window, 30 ms hop), four decks at +8 %" | tee -a "$LOG"
for c in "${CORES[@]}"; do run --cpu "$c"; done
for c in "$FAST" "$SLOW"; do
    echo "## settings on cpu $c" | tee -a "$LOG"
    run --cpu "$c" --split 1
    run --cpu "$c" --preset cheaper
    run --cpu "$c" --preset custom --win 60 --hop 15 --split 1
    run --cpu "$c" --preset custom --win 40 --hop 10 --split 1
    run --cpu "$c" --ratio 0.92
done
adb shell rm -f "$BIN"
echo "log: $LOG"
