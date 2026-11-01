#!/usr/bin/env bash
# Run one GPU command (a test render) under the team's GPU lock; the lock is released however the command ends.
#   bash scripts/gpu_run.sh "<what>" <command...>
source "$(dirname "$0")/gpu_lock.sh"
what="$1"
shift
gpu_lock_acquire "$what"
trap 'gpu_lock_release' EXIT
trap 'gpu_lock_release; exit 130' INT TERM HUP
"$@"
