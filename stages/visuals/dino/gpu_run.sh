#!/usr/bin/env bash
# Run one GPU command (a test render, say) under the team's GPU lock; the lock is released however the command ends.
#   scripts/gpu_run.sh <your-name> <command...>
# e.g. scripts/gpu_run.sh visuals2 /d/Tools/blender-4.5.14-windows-x64/blender.exe -b --factory-startup \
#        --python scripts/raptor_run.py -- --variant cyan --frames 0,113,225 --pct 50 --out <scratch dir>
source "$(dirname "$0")/gpu_lock.sh"
who="$1"
shift
gpu_lock_acquire "$who" "$*"
trap gpu_lock_release EXIT
"$@"
