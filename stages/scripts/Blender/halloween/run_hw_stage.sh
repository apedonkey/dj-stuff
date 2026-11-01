#!/usr/bin/env bash
# run_hw_stage.sh [hw_stage.py args, e.g. --fast] -- the Halloween bake under the shared GPU lock.
# The lock is the convention every session uses for the GTX 1660S: mkdir C:\Users\Chris\TribeUE\gpu.lock.d with an
# owner.txt inside; whoever holds it bakes or renders, everyone else waits. Released on exit, also on error or Ctrl-C.
# Output: out_hw/ (HW_OUT overrides), log in <out>/bake.log.
set -u
LOCK=/c/Users/Chris/TribeUE/gpu.lock.d
BLENDER=/d/Tools/blender-4.5.14-windows-x64/blender.exe
HERE="$(cd "$(dirname "$0")" && pwd)"
OUTDIR="${HW_OUT:-$HERE/out_hw}"
mkdir -p "$OUTDIR"
waited=0
until mkdir "$LOCK" 2>/dev/null; do
    [ $((waited % 120)) -eq 0 ] && echo "GPU lock held by: $(cat "$LOCK/owner.txt" 2>/dev/null || echo '?') -- waiting"
    sleep 10; waited=$((waited + 10))
done
echo "halloween session: hw_stage.py $* (bash pid $$, since $(date '+%F %T'))" > "$LOCK/owner.txt"
trap 'rm -rf "$LOCK"' EXIT
echo "GPU lock taken; baking (log: $OUTDIR/bake.log)"
t0=$(date +%s)
"$BLENDER" -b --factory-startup --python-exit-code 1 --python "$HERE/hw_stage.py" -- "$@" > "$OUTDIR/bake.log" 2>&1
rc=$?
echo "blender exit $rc after $(( $(date +%s) - t0 )) s"
grep -a -E "^\[HW|Error|Traceback|  File \"" "$OUTDIR/bake.log" | tail -60
exit $rc
