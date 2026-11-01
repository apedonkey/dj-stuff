#!/usr/bin/env bash
# render_bigdub.sh -- BIG DUB's pictures (C:\Users\Chris\TribeUE\TribeXR\Scripts\bigdub_views.py) from the kit's saved
# level, in the editor on the GPU (a small window: without one the editor stops ticking). Waits for 8 GB of free RAM (gives up after 30 minutes), then the shared GPU
# lock (released only if taken here). Log: D:\TribeUE\MetaBigDub\logs\render_bigdub.log.
set -u
UE=/d/MetaUE54/Engine/Binaries/Win64
PROJ_W='D:\TribeUE\MetaBigDub\TribeXR\TribeXR.uproject'
LOGS=/d/TribeUE/MetaBigDub/logs
LOGS_W='D:\TribeUE\MetaBigDub\logs'
PY='C:\Users\Chris\TribeUE\TribeXR\Scripts\bigdub_views.py'
LOCK=/c/Users/Chris/TribeUE/gpu.lock.d
have=0
trap '[[ $have == 1 ]] && rm -rf "$LOCK"' EXIT
trap 'exit 143' TERM
trap 'exit 130' INT
waited=0
while :; do
    free=$(powershell -NoProfile -Command "(Get-CimInstance Win32_OperatingSystem).FreePhysicalMemory" | tr -d '\r')
    [[ ${free:-0} -ge 8000000 ]] && break
    [[ $waited -ge 1800 ]] && { echo "GAVE UP: free RAM ${free} KB < 8000000 KB for 30 minutes"; exit 3; }
    echo "$(date +%T) free RAM ${free} KB < 8000000 KB: waiting"; sleep 60; waited=$((waited + 60))
done
until mkdir "$LOCK" 2>/dev/null; do
    echo "GPU lock held by: $(cat "$LOCK/owner.txt" 2>/dev/null || echo unknown) -- waiting"; sleep 15
done
have=1
echo "bigdub tribe session: render_bigdub.sh (bash pid $$, since $(date '+%F %T'))" > "$LOCK/owner.txt"
t0=$(date +%s)
# (-ExecCmds, not -ExecutePythonScript: the editor quits as soon as an -ExecutePythonScript script returns, before the
# script's tick callback can wait for the level and the shaders)
MSYS_NO_PATHCONV=1 timeout 1500 "$UE/UnrealEditor.exe" "$PROJ_W" "-ExecCmds=py $PY" -unattended -nosplash \
    -nosound -windowed -ResX=960 -ResY=540 -abslog="$LOGS_W\\render_bigdub.log"
rc=$?
echo "editor exit $rc after $(( $(date +%s) - t0 )) s (free RAM at the start ${free} KB)"
grep -a "\[BDR\]" "$LOGS/render_bigdub.log" | sed 's/^.*\[BDR\]/[BDR]/' | tail -12
grep -a -q "\[BDR\] done" "$LOGS/render_bigdub.log" || { echo "RENDER FAILED (see $LOGS/render_bigdub.log)"; exit 1; }
