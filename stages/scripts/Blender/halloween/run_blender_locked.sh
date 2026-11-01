#!/usr/bin/env bash
# run_blender_locked.sh <log> <script.py> [script args] -- any Halloween Blender tool (overdraw, checks) under the shared
# GPU lock (C:\Users\Chris\TribeUE\gpu.lock.d + owner.txt, the convention every session uses; released on exit).
# Unlike run_hw_stage.sh it never touches out_hw/bake.log: the log goes where the first argument says.
set -u
LOCK=/c/Users/Chris/TribeUE/gpu.lock.d
BLENDER=/d/Tools/blender-4.5.14-windows-x64/blender.exe
LOG="$1"; SCRIPT="$2"; shift 2
waited=0
until mkdir "$LOCK" 2>/dev/null; do
    [ $((waited % 120)) -eq 0 ] && echo "GPU lock held by: $(cat "$LOCK/owner.txt" 2>/dev/null || echo unknown) -- waiting"
    sleep 10; waited=$((waited + 10))
done
echo "halloween session: $(basename "$SCRIPT") $* (bash pid $$, since $(date '+%F %T'))" > "$LOCK/owner.txt"
trap 'rm -rf "$LOCK"' EXIT
t0=$(date +%s)
"$BLENDER" -b --factory-startup --python-exit-code 1 --python "$SCRIPT" -- "$@" > "$LOG" 2>&1
rc=$?
echo "blender exit $rc after $(( $(date +%s) - t0 )) s (log: $LOG)"
exit $rc
