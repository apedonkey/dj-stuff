#!/usr/bin/env bash
# Run a Ghidra script (default scripts/FxProbe.java) headless against the persistent project C:/ghidra-work/tribexr
# (libUnreal.so, already analyzed: never re-analyze it).
#   scripts/ghidra_probe.sh <commands.txt> <log.txt> [Script.java]
# Read-only unless SAVE=1 (then names or functions the script creates are saved into the project). One instance at a
# time: the project is locked while Ghidra runs. Ghidra's own console output goes to <log>.ghidra.log.
# Ghidra address = runtime RVA + 0xFF000.
set -euo pipefail
[ $# -ge 2 ] || { echo "usage: $0 <commands.txt> <log.txt> [Script.java]" >&2; exit 2; }
cmds=$(cygpath -w "$1"); log=$(cygpath -w "$2"); script=${3:-FxProbe.java}
repo=$(cd "$(dirname "$0")/.." && pwd)
ro="-readOnly"; [ "${SAVE:-0}" = 1 ] && ro=""
bat=$(mktemp --suffix=.bat)
cat > "$bat" <<EOF
@echo off
cd /d C:\\ghidra\\ghidra_12.0.4_PUBLIC\\support
call C:\ghidra\ghidra_12.0.4_PUBLIC\support\launch.bat fg jdk Ghidra-Headless 8G "-XX:ParallelGCThreads=2 -XX:CICompilerCount=2" ghidra.app.util.headless.AnalyzeHeadless C:\\ghidra-work tribexr -process libUnreal.so -noanalysis $ro -scriptPath "$(cygpath -w "$repo/scripts")" -postScript $script "$cmds" "$log"
EOF
trap 'rm -f "$bat"' EXIT
cmd //c "$(cygpath -w "$bat")" > "$2.ghidra.log" 2>&1
grep -E 'ERROR|Exception|FxProbe wrote' "$2.ghidra.log" | grep -v -E 'VarnodeContext' | head -20 || true
