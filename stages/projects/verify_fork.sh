#!/usr/bin/env bash
# Verify Meta's UE 5.4.4 fork build matches Tribe's engine before shipping any custom material.
#   1. reflection check: UMaterial (and the rest of the festival classes) identical to Tribe's libUnreal.so
#   2. oracle: cook /Engine/BasicShapes/BasicShapeMaterial (pulled in by the Festival map's material instances) with the
#      fork and compare it byte-for-byte with Tribe's own cooked copy.
# Usage: bash verify_fork.sh            (from anywhere; needs the finished fork editor build in D:\MetaUE54)
set -uo pipefail
export MSYS_NO_PATHCONV=1
UE=/d/MetaUE54/Engine/Binaries/Win64
REPO="/c/Users/Chris/OneDrive/Desktop/tribe hack"
LAUNCHER_PROJ=/c/Users/Chris/TribeUE/TribeXR
PROJ=/c/Users/Chris/TribeUE/Meta/TribeXR
TRIBE_BSM="${TRIBE_BSM:-/c/Users/Chris/TribeUE/Meta/tribe_ref}"   # Tribe's own cooked copy (extracted from its pak)
LOG=/c/Users/Chris/TribeUE/Meta/verify
mkdir -p "$LOG"
W(){ cygpath -w "$1"; }

[ -x "$UE/UnrealEditor-Cmd.exe" ] || { echo "fork editor not built yet: $UE/UnrealEditor-Cmd.exe"; exit 1; }

echo "== 1. reflection: Tribe libUnreal.so vs the fork's editor DLLs"
python "$(W "$REPO/scripts/ue_schemadiff.py")" "$(W "$REPO/out/alllibs/libUnreal.so")" \
    "$(W $UE/UnrealEditor-Engine.dll),$(W $UE/UnrealEditor-NavigationSystem.dll)" > "$LOG/schemadiff.txt" 2>&1
grep -E "DIFF|differing" "$LOG/schemadiff.txt"
grep -A2 "bComputeFogPerPixel" "$LOG/schemadiff.txt" | head -3

echo "== 2. content: the glTFRuntime stub parents from the launcher project (same names Tribe ships)"
mkdir -p "$PROJ/Plugins"
cp -r "$LAUNCHER_PROJ/Plugins/glTFRuntime" "$PROJ/Plugins/" 2>/dev/null

echo "== 3. build the Festival level with the fork editor (null RHI: no editor shader compile)"
"$UE/UnrealEditor.exe" "$(W $PROJ/TribeXR.uproject)" -ExecutePythonScript="$(W $PROJ/Scripts/build_festival.py)" \
    -unattended -nosplash -nullrhi -abslog="$(W $LOG/build_festival.log)" > /dev/null 2>&1
grep -E "\[FESTIVAL\] (done|FAILED)" "$LOG/build_festival.log" | tail -2

echo "== 4. cook for Android_ASTC (first run also compiles the fork's mobile global shaders)"
rm -rf "$PROJ/Saved/Cooked"
"$UE/UnrealEditor-Cmd.exe" "$(W $PROJ/TribeXR.uproject)" -run=cook -targetplatform=Android_ASTC -unversioned \
    -map=/Game/Mods/Festival/Maps/Environment_Festival -unattended -nosplash -nullrhi -abslog="$(W $LOG/cook.log)" > /dev/null 2>&1
grep -E "Success - [0-9]+ error|COOK FAILED|Error:" "$LOG/cook.log" | tail -3

echo "== 5. oracle: BasicShapeMaterial, fork cook vs Tribe's shipped copy"
OURS=$(find "$PROJ/Saved/Cooked/Android_ASTC" -path "*BasicShapes/BasicShapeMaterial.uexp" | head -1)
[ -n "$OURS" ] || { echo "no cooked BasicShapeMaterial found"; exit 1; }
python - "$(W "$OURS")" "$(W "$TRIBE_BSM/BasicShapeMaterial.uexp")" "$(W "${OURS%.uexp}.uasset")" "$(W "$TRIBE_BSM/BasicShapeMaterial.uasset")" <<'EOF'
import sys
for a, b in ((sys.argv[1], sys.argv[2]), (sys.argv[3], sys.argv[4])):
    x, y = open(a, "rb").read(), open(b, "rb").read()
    first = next((i for i in range(min(len(x), len(y))) if x[i] != y[i]), None)
    same = x == y
    print(f"{a.split('/')[-1]}: fork {len(x)} B vs Tribe {len(y)} B -> {'IDENTICAL' if same else f'differ (first at {first})'}")
EOF
