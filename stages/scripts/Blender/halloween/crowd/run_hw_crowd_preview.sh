#!/usr/bin/env bash
# The Halloween crowd preview (hw_crowd_preview.py) under the shared GPU lock C:/Users/Chris/TribeUE/gpu.lock.d.
#   bash run_hw_crowd_preview.sh [--grounds hw|dino|none] [--only name,name] [--no-render]
# --no-render (checks only) runs without the lock. The log goes to previews/preview.log; the lock is freed on any exit.
set -u
HERE="$(cd "$(dirname "$0")" && pwd)"
BLENDER="D:/Tools/blender-4.5.14-windows-x64/blender.exe"
LOCK="C:/Users/Chris/TribeUE/gpu.lock.d"
LOG="$HERE/previews/preview.log"
mkdir -p "$HERE/previews"
if [[ " $* " != *" --no-render "* ]]; then
  until mkdir "$LOCK" 2>/dev/null; do sleep 10; done
  echo "halloween crowd preview" > "$LOCK/owner.txt"
  trap 'rm -rf "$LOCK"' EXIT
fi
"$BLENDER" -b --factory-startup --python "$HERE/hw_crowd_preview.py" -- "$@" > "$LOG" 2>&1
rc=$?
grep -E "\[HWPREVIEW\]|\[HWCROWD\]|Error|Traceback" "$LOG"
exit $rc
