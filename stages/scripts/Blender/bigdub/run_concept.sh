#!/usr/bin/env bash
# run_concept.sh [concept_blockout.py args] -- the Big Dub concept blockout render under the shared GPU lock
# (the convention every session uses: mkdir C:\Users\Chris\TribeUE\gpu.lock.d with an owner.txt; released on exit).
set -u
LOCK=/c/Users/Chris/TribeUE/gpu.lock.d
BLENDER=/d/Tools/blender-4.5.14-windows-x64/blender.exe
HERE="$(cd "$(dirname "$0")" && pwd)"
OUTDIR="${BD_OUT:-$HERE/concept}"
mkdir -p "$OUTDIR"
waited=0
until mkdir "$LOCK" 2>/dev/null; do
    [ $((waited % 120)) -eq 0 ] && echo "GPU lock held by: $(cat "$LOCK/owner.txt" 2>/dev/null || echo '?') -- waiting"
    sleep 10; waited=$((waited + 10))
done
echo "bigdub session: concept_blockout.py $* (bash pid $$, since $(date '+%F %T'))" > "$LOCK/owner.txt"
trap 'rm -rf "$LOCK"' EXIT
echo "GPU lock taken; rendering (log: $OUTDIR/render.log)"
t0=$(date +%s)
"$BLENDER" -b --factory-startup --python-exit-code 1 --python "$HERE/concept_blockout.py" -- --out "$OUTDIR" "$@" > "$OUTDIR/render.log" 2>&1
rc=$?
echo "blender exit $rc after $(( $(date +%s) - t0 )) s"
grep -a -E "^\[BIGDUB|Error|Traceback|  File \"" "$OUTDIR/render.log" | tail -40
exit $rc
