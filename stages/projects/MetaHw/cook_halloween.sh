#!/usr/bin/env bash
# cook_halloween.sh [build|cook|pack|all] -- GRAVEYARD SHIFT's Unreal half, on its own Meta-fork project copy
# (D:\TribeUE\MetaHw\TribeXR: Config/Build/Plugins copied from Meta\TribeXR, no Dino or club content, its own Saved\Cooked):
#   build  C:\Users\Chris\TribeUE\TribeXR\Scripts\build_halloween.py imports the Blender output (HW_SRC; default
#          Scripts\Blender\halloween\out_hw) into /Game/Mods/Halloween and saves Maps/Environment_Halloween (pak chunk 54)
#   cook   cooks the Halloween map for Android_ASTC with the fork (this project holds no other map)
#   pack   pack_chunk.sh 54 -> Saved/ModPak/pakchunk54-Android_ASTC_P.pak
# Logs: D:\TribeUE\MetaHw\logs. Unreal runs with -nullrhi (no GPU lock needed). Same shape as the club's cook_club.sh.
set -euo pipefail
# MSYS_NO_PATHCONV only on the Unreal commands (their -map=/Game/... must stay as is); exported for the whole script it
# also reaches pack_chunk.sh, whose repak needs MSYS to turn /d/... into D:\... (the club hit "Input is not a directory")
UE=/d/MetaUE54/Engine/Binaries/Win64
PROJ=/d/TribeUE/MetaHw/TribeXR
PROJ_W='D:\TribeUE\MetaHw\TribeXR\TribeXR.uproject'
LOGS=/d/TribeUE/MetaHw/logs
LOGS_W='D:\TribeUE\MetaHw\logs'
BUILD_PY='C:\Users\Chris\TribeUE\TribeXR\Scripts\build_halloween.py'
MAP=/Game/Mods/Halloween/Maps/Environment_Halloween
CHUNK=54
COOKED="$PROJ/Saved/Cooked/Android_ASTC/TribeXR"
mkdir -p "$LOGS"
step="${1:-all}"

if [[ $step == build || $step == all ]]; then
    t0=$(date +%s)
    MSYS_NO_PATHCONV=1 "$UE/UnrealEditor.exe" "$PROJ_W" -ExecutePythonScript="$BUILD_PY" -unattended -nosplash -nullrhi \
        -abslog="$LOGS_W\\build_halloween.log" || true
    grep -a -E "\[HW\]" "$LOGS/build_halloween.log" | sed 's/^.*\[HW\]/[HW]/' | tail -40
    grep -a -q "\[HW\] done" "$LOGS/build_halloween.log" || { echo "BUILD FAILED (see $LOGS/build_halloween.log)"; exit 1; }
    echo "build ok in $(( $(date +%s) - t0 )) s"
fi

if [[ $step == cook || $step == all ]]; then
    t0=$(date +%s)
    rm -rf "$COOKED/Content/Mods" "$COOKED/Metadata/ChunkManifest"
    MSYS_NO_PATHCONV=1 "$UE/UnrealEditor-Cmd.exe" "$PROJ_W" -run=cook -targetplatform=Android_ASTC -unversioned \
        -map=$MAP -unattended -nosplash -nullrhi -abslog="$LOGS_W\\cook_halloween.log" || true
    grep -a -E "Success - [0-9]+ error|Failure - [0-9]+ error" "$LOGS/cook_halloween.log" | tail -2
    grep -a -q "Success - 0 error" "$LOGS/cook_halloween.log" || { echo "COOK FAILED (see $LOGS/cook_halloween.log)"; exit 1; }
    echo "chunk $CHUNK manifest: $(wc -l < "$COOKED/Metadata/ChunkManifest/pakchunk$CHUNK.txt") entries; cook in $(( $(date +%s) - t0 )) s"
fi

if [[ $step == pack || $step == all ]]; then
    bash "$PROJ/Scripts/pack_chunk.sh" $CHUNK | tail -25
    ls -la "$PROJ/Saved/ModPak/pakchunk$CHUNK-Android_ASTC_P.pak"
fi
