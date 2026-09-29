#!/usr/bin/env bash
# Run one shell command from the project root, print its output, and append the command,
# exit code and output to NOTES.md. Outputs longer than MAX_LINES are truncated in NOTES.md
# and kept in full as logs/NNN.log.
#
# Usage: bash scripts/logrun.sh '<command>'
set -u
cd "$(dirname "$0")/.." || exit 1
export MSYS_NO_PATHCONV=1   # stop Git Bash rewriting device paths like /sdcard/... for adb.exe
export PATH="$PWD/tools/platform-tools:$PATH"

MAX_LINES=60
cmd="$1"
mkdir -p logs
out="logs/running.$$.log"
started=$(date '+%Y-%m-%d %H:%M:%S')

bash -c "$cmd" 2>&1 | tr -d '\r' >"$out"
rc=${PIPESTATUS[0]}
total=$(wc -l <"$out")
# make sure the output ends with a newline so the closing fence stays on its own line
if [ -s "$out" ] && [ -n "$(tail -c1 "$out")" ]; then echo >>"$out"; fi

cat "$out"

# number the entry when it is appended, not when it starts, so overlapping runs cannot collide
n=$(( $(grep -c '^### \[' NOTES.md 2>/dev/null || true) + 1 ))
id=$(printf '%03d' "$n")

{
  printf '\n### [%s] %s · exit %d\n\n' "$id" "$started" "$rc"
  printf '```sh\n%s\n```\n\n' "$cmd"
  printf '```text\n'
  if [ ! -s "$out" ]; then
    printf '(no output)\n'
  elif [ "$total" -le "$MAX_LINES" ]; then
    cat "$out"
  else
    head -n 40 "$out"
    printf '\n... [%d lines omitted, full output in logs/%s.log] ...\n\n' "$((total - 50))" "$id"
    tail -n 10 "$out"
  fi
  printf '```\n'
} >>NOTES.md

if [ "$total" -le "$MAX_LINES" ]; then rm -f "$out"; else mv "$out" "logs/$id.log"; fi
exit "$rc"
