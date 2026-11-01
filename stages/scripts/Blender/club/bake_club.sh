#!/usr/bin/env bash
# Bake REACTOR (club_stage.py) under the shared GPU lock. The lock is Reactor's yielding one (TribeUE/Visuals/reactor/
# scripts/gpu_lock.sh): it takes the GPU only after the lock has been free for 45 s, so Halloween's renders (priority until
# 2026-10-31) go first.
#   bash bake_club.sh <out dir> <log name> [--fast]
# e.g. bash bake_club.sh out_club_fast bake_club_v4_fast --fast    /    bash bake_club.sh out_club bake_club_v4
set -u
here="$(cd "$(dirname "$0")" && pwd)"
out="$1"; logname="$2"; shift 2
source /c/Users/Chris/TribeUE/Visuals/reactor/scripts/gpu_lock.sh
B=/d/Tools/blender-4.5.14-windows-x64/blender.exe
log="$here/$logname.log"
gpu_lock_acquire "club stage bake ($logname)"
trap 'gpu_lock_release' EXIT
trap 'gpu_lock_release; exit 130' INT TERM HUP
t0=$(date +%s)
CLUB_OUT="$here/$out" "$B" -b --factory-startup --python "$here/club_stage.py" -- "$@" > "$log" 2>&1
rc=$?
if grep -q "Traceback" "$log"; then rc=1; fi                 # Blender -b exits 0 on a Python error
gpu_lock_release
trap - EXIT INT TERM HUP
echo "bake rc=$rc in $(( $(date +%s) - t0 )) s, log $log"
grep -E "Traceback|Error|crowd|people|baked SM_ClubCrowd|baked .*CrowdLight|done" "$log" | tail -12
exit $rc
