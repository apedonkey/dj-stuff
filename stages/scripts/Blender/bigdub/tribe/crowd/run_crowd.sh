#!/usr/bin/env bash
# run_crowd.sh [--target N] [--fast] -- BIG DUB's Tribe crowd (bd_crowd_tribe.py) in Blender, headless, after make_site.sh.
# Waits for 8 GB of free RAM (the PC's one-heavy-job rule), then takes the shared GPU lock (the colour bake is a Cycles
# render) and releases only what it took. Log: out/crowd/crowd.log.
set -u
HERE="$(cd "$(dirname "$0")" && pwd)"
OUT="$HERE/../out/crowd"
LOCK=/c/Users/Chris/TribeUE/gpu.lock.d
BLENDER="${BLENDER:-/d/Tools/blender-4.5.14-windows-x64/blender.exe}"
mkdir -p "$OUT"
have=0
trap '[[ $have == 1 ]] && rm -rf "$LOCK"' EXIT
trap 'exit 143' TERM
trap 'exit 130' INT
waited=0
while :; do
    free=$(powershell -NoProfile -Command "(Get-CimInstance Win32_OperatingSystem).FreePhysicalMemory" | tr -d '\r')
    [[ ${free:-0} -ge 8000000 ]] && break
    [[ $waited -ge 1800 ]] && { echo "gave up: free RAM ${free} KB < 8000000 KB for 30 minutes"; exit 3; }
    echo "$(date +%T) free RAM ${free} KB < 8000000 KB: waiting"; sleep 60; waited=$((waited + 60))
done
until mkdir "$LOCK" 2>/dev/null; do
    echo "GPU lock held by: $(cat "$LOCK/owner.txt" 2>/dev/null || echo unknown) -- waiting"; sleep 15
done
have=1
echo "bigdub tribe session: bd_crowd_tribe.py (bash pid $$, since $(date '+%F %T'))" > "$LOCK/owner.txt"
t0=$(date +%s)
"$BLENDER" -b --factory-startup --python-exit-code 1 --python "$HERE/bd_crowd_tribe.py" -- "$@" > "$OUT/crowd.log" 2>&1
rc=$?
echo "blender exit $rc after $(( $(date +%s) - t0 )) s (free RAM at the start ${free} KB)"
grep -a "^\[BDC" "$OUT/crowd.log" | tail -12
exit $rc
