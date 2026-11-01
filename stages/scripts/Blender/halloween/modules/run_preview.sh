#!/usr/bin/env bash
# run_preview.sh <module> [hw_preview.py options] -- render a grounds module in context under the shared GPU lock
# (mkdir C:\Users\Chris\TribeUE\gpu.lock.d + owner.txt; released on exit, also on error or Ctrl-C).
set -u
LOCK=/c/Users/Chris/TribeUE/gpu.lock.d
BLENDER=/d/Tools/blender-4.5.14-windows-x64/blender.exe
HERE="$(cd "$(dirname "$0")" && pwd)"
[ $# -ge 1 ] || { echo "usage: $0 <module> [options]"; exit 2; }
mkdir -p "$HERE/out"
waited=0
until mkdir "$LOCK" 2>/dev/null; do
    [ $((waited % 120)) -eq 0 ] && echo "GPU lock held by: $(cat "$LOCK/owner.txt" 2>/dev/null || echo '?') -- waiting"
    sleep 10; waited=$((waited + 10))
done
echo "halloween grounds preview: $* (bash pid $$, since $(date '+%F %T'))" > "$LOCK/owner.txt"
trap 'rm -rf "$LOCK"' EXIT
LOG="$HERE/out/preview_$1.log"
"$BLENDER" -b --factory-startup --python-exit-code 1 --python "$HERE/hw_preview.py" -- "$@" > "$LOG" 2>&1
rc=$?
grep -a -E "\[HWGROUNDS\]|Error|Traceback|  File \"" "$LOG" | tail -40
exit $rc
