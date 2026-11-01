#!/usr/bin/env bash
# cook_bigdub.sh [build|cook|pack|all] -- BIG DUB's Main Stage (Tribe XR stage folder /Game/Mods/BigDub, pak chunk 56) on its
# own Meta-fork project copy (D:\TribeUE\MetaBigDub\TribeXR: uproject/Config/Build/Plugins/Binaries copied from MetaHarvest
# on 2026-11-01, no other stage's content, its own Saved\Cooked). cook_harvest.sh with BIG DUB's names:
#   build  C:\Users\Chris\TribeUE\TribeXR\Scripts\build_bigdub.py imports Scripts\Blender\bigdub\tribe\out (gen + crowd)
#          into /Game/Mods/BigDub and saves Maps/Environment_BigDub
#   cook   cooks the map for Android_ASTC with the fork (this project holds no other map); stops on a material that
#          fails to compile for the Quest
#   pack   pack_chunk.sh 56 -> Saved/ModPak/pakchunk56-Android_ASTC_P.pak
# Each Unreal step waits for 8 GB of free RAM first (the PC's one-heavy-job rule; gives up after 30 minutes).
# Logs: D:\TribeUE\MetaBigDub\logs. Unreal runs with -nullrhi.
set -euo pipefail
UE=/d/MetaUE54/Engine/Binaries/Win64
PROJ=/d/TribeUE/MetaBigDub/TribeXR
PROJ_W='D:\TribeUE\MetaBigDub\TribeXR\TribeXR.uproject'
LOGS=/d/TribeUE/MetaBigDub/logs
LOGS_W='D:\TribeUE\MetaBigDub\logs'
BUILD_PY='C:\Users\Chris\TribeUE\TribeXR\Scripts\build_bigdub.py'
MAP=/Game/Mods/BigDub/Maps/Environment_BigDub
CHUNK=56
COOKED="$PROJ/Saved/Cooked/Android_ASTC/TribeXR"
mkdir -p "$LOGS"
step="${1:-all}"

wait_ram() {
    local waited=0 free
    while :; do
        free=$(powershell -NoProfile -Command "(Get-CimInstance Win32_OperatingSystem).FreePhysicalMemory" | tr -d '\r')
        [[ ${free:-0} -ge 8000000 ]] && { echo "free RAM ${free} KB"; return 0; }
        [[ $waited -ge 1800 ]] && { echo "GAVE UP: free RAM ${free} KB < 8000000 KB for 30 minutes"; exit 3; }
        echo "$(date +%T) free RAM ${free} KB < 8000000 KB: waiting"; sleep 60; waited=$((waited + 60))
    done
}

if [[ $step == build || $step == all ]]; then
    wait_ram
    t0=$(date +%s)
    MSYS_NO_PATHCONV=1 "$UE/UnrealEditor.exe" "$PROJ_W" -ExecutePythonScript="$BUILD_PY" -unattended -nosplash -nullrhi \
        -abslog="$LOGS_W\\build_bigdub.log" || true
    grep -a -E "\[BD\]" "$LOGS/build_bigdub.log" | sed 's/^.*\[BD\]/[BD]/' | tail -60
    grep -a -q "\[BD\] done" "$LOGS/build_bigdub.log" || { echo "BUILD FAILED (see $LOGS/build_bigdub.log)"; exit 1; }
    echo "build ok in $(( $(date +%s) - t0 )) s"
fi

if [[ $step == cook || $step == all ]]; then
    wait_ram
    t0=$(date +%s)
    rm -rf "$COOKED/Content/Mods" "$COOKED/Metadata/ChunkManifest"
    MSYS_NO_PATHCONV=1 "$UE/UnrealEditor-Cmd.exe" "$PROJ_W" -run=cook -targetplatform=Android_ASTC -unversioned \
        -map=$MAP -unattended -nosplash -nullrhi -abslog="$LOGS_W\\cook_bigdub.log" || true
    grep -a -E "Success - [0-9]+ error|Failure - [0-9]+ error" "$LOGS/cook_bigdub.log" | tail -2
    grep -a -q "Success - 0 error" "$LOGS/cook_bigdub.log" || { echo "COOK FAILED (see $LOGS/cook_bigdub.log)"; exit 1; }
    if grep -a -q "Failed to compile\|valid ShaderMap" "$LOGS/cook_bigdub.log"; then
        grep -a "Failed to compile\|valid ShaderMap" -A2 "$LOGS/cook_bigdub.log" | head -20
        echo "COOK FAILED: a material failed to compile for the Quest"; exit 1
    fi
    echo "chunk $CHUNK manifest: $(wc -l < "$COOKED/Metadata/ChunkManifest/pakchunk$CHUNK.txt") entries, shader archive" \
         "entries: $(grep -ci shaderarchive "$COOKED/Metadata/ChunkManifest/pakchunk$CHUNK.txt"); cook in $(( $(date +%s) - t0 )) s"
fi

if [[ $step == pack || $step == all ]]; then
    bash "$PROJ/Scripts/pack_chunk.sh" $CHUNK | tail -40
    ls -la "$PROJ/Saved/ModPak/pakchunk$CHUNK-Android_ASTC_P.pak"
fi
