#!/usr/bin/env bash
# Look-dev pass for one loop: the whole loop + its seam frame at low resolution under the GPU lock, then the gate on
# those frames (a conservative pre-check: quarter res reads 1 m2 blocks ~0.03 higher than full res) and a PNG sheet.
#   bash scripts/lookdev.sh <concept> <variant> [scene args; defaults --pct 25 --samples 4]
#   FRAMES_ONLY="0,51,103" bash scripts/lookdev.sh ...    just those frames (no gate), e.g. at --pct 50
# Output: _work/lookdev_<concept>_<variant>/ (frames, seam, sheet.png, gate.txt)
set -u
here="$(cd "$(dirname "$0")" && pwd)"
root="$(dirname "$here")"
concept="$1"; var="$2"; shift 2
B=/d/Tools/blender-4.5.14-windows-x64/blender.exe
bpm="${VJ_BPM:-140}"
bars="${VJ_BARS:-8}"
name="${concept}_${var}"
work="$root/_work/lookdev_${name}"
n=$(python -c "print(int(round($bars * 4 * 30 * 60 / $bpm)))")
rm -rf "$work"
mkdir -p "$work/frames" "$work/seam"
if [ -n "${FRAMES_ONLY:-}" ]; then sel=(--frames "$FRAMES_ONLY"); else sel=(--all --seam "$work/seam"); fi
source "$here/gpu_lock.sh"
gpu_lock_acquire "$name look-dev"
trap 'gpu_lock_release' EXIT
trap 'gpu_lock_release; exit 130' INT TERM HUP
t0=$(date +%s)
"$B" -b --factory-startup --python "$here/$concept.py" -- --variant "$var" "$@" --pct 25 --samples 4 --bpm "$bpm" \
  --bars "$bars" "${sel[@]}" --out "$work/frames" > "$work/render.log" 2>&1
t1=$(date +%s)
gpu_lock_release
trap - EXIT INT TERM HUP
if grep -qi "traceback" "$work/render.log"; then
  echo "RENDER FAILED: see $work/render.log"; grep -i -B2 -A12 "traceback" "$work/render.log" | head -40; exit 1
fi
echo "== rendered in $((t1 - t0)) s ($(grep -c 'frame .*s$' "$work/render.log") frames)"
grep "safe area" "$work/render.log"
if [ -z "${FRAMES_ONLY:-}" ]; then
  python "$here/check_loop.py" "$work/frames" "${name}_" --seam "$work/seam/${name}_$(printf %04d "$n").png" \
    --bpm "$bpm" --bars "$bars" | tee "$work/gate.txt"
fi
python "$here/png_sheet.py" "$work/frames" "${name}_" "$work/sheet.png" --bars "$bars" ${FRAMES_ONLY:+--frames "$FRAMES_ONLY"}
