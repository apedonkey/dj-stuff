#!/usr/bin/env bash
# cook_club.sh [build|cook|pack|all] -- the REACTOR club's Unreal half, on its own Meta-fork project copy
# (D:\TribeUE\MetaClub\TribeXR: Config/Build/Plugins copied from Meta\TribeXR, no Dino content, its own Saved\Cooked):
#   build  C:\Users\Chris\TribeUE\TribeXR\Scripts\build_club.py imports the Blender output (CLUB_SRC; default
#          Scripts\Blender\club\out_club) into /Game/Mods/Club and saves Maps/Environment_Club (pak chunk 55)
#   cook   cooks the club map for Android_ASTC with the fork (this project holds no other map, so the list is short)
#   pack   pack_chunk.sh 55 -> Saved/ModPak/pakchunk55-Android_ASTC_P.pak
# Logs: D:\TribeUE\MetaClub\logs. Unreal runs with -nullrhi (no GPU lock needed).
set -euo pipefail
# MSYS_NO_PATHCONV only on the Unreal commands (their -map=/Game/... must stay as is); exported for the whole script it
# also reached pack_chunk.sh, whose repak needs MSYS to turn /d/... into D:\... (2026-10-08: "Input is not a directory")
UE=/d/MetaUE54/Engine/Binaries/Win64
PROJ=/d/TribeUE/MetaClub/TribeXR
PROJ_W='D:\TribeUE\MetaClub\TribeXR\TribeXR.uproject'
LOGS=/d/TribeUE/MetaClub/logs
LOGS_W='D:\TribeUE\MetaClub\logs'
BUILD_PY='C:\Users\Chris\TribeUE\TribeXR\Scripts\build_club.py'
COOKED="$PROJ/Saved/Cooked/Android_ASTC/TribeXR"
mkdir -p "$LOGS"
step="${1:-all}"

if [[ $step == build || $step == all ]]; then
    t0=$(date +%s)
    MSYS_NO_PATHCONV=1 "$UE/UnrealEditor.exe" "$PROJ_W" -ExecutePythonScript="$BUILD_PY" -unattended -nosplash -nullrhi \
        -abslog="$LOGS_W\\build_club.log" || true
    grep -a -E "\[CLUB\]" "$LOGS/build_club.log" | sed 's/^.*\[CLUB\]/[CLUB]/' | tail -40
    grep -a -q "\[CLUB\] done" "$LOGS/build_club.log" || { echo "BUILD FAILED (see $LOGS/build_club.log)"; exit 1; }
    echo "build ok in $(( $(date +%s) - t0 )) s"
fi

if [[ $step == cook || $step == all ]]; then
    t0=$(date +%s)
    rm -rf "$COOKED/Content/Mods" "$COOKED/Metadata/ChunkManifest"
    MSYS_NO_PATHCONV=1 "$UE/UnrealEditor-Cmd.exe" "$PROJ_W" -run=cook -targetplatform=Android_ASTC -unversioned \
        -map=/Game/Mods/Club/Maps/Environment_Club -unattended -nosplash -nullrhi -abslog="$LOGS_W\\cook_club.log" || true
    grep -a -E "Success - [0-9]+ error|Failure - [0-9]+ error" "$LOGS/cook_club.log" | tail -2
    grep -a -q "Success - 0 error" "$LOGS/cook_club.log" || { echo "COOK FAILED (see $LOGS/cook_club.log)"; exit 1; }
    echo "chunk 55 manifest: $(wc -l < "$COOKED/Metadata/ChunkManifest/pakchunk55.txt") entries; cook in $(( $(date +%s) - t0 )) s"
fi

if [[ $step == pack || $step == all ]]; then
    bash "$PROJ/Scripts/pack_chunk.sh" 55 | tail -25
    ls -la "$PROJ/Saved/ModPak/pakchunk55-Android_ASTC_P.pak"
fi
