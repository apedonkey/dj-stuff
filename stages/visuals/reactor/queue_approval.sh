#!/usr/bin/env bash
# Reactor approval queue (club session, 2026-10-09; the authoring agents hit their usage limit mid-way). For every piece
# below: the quarter-res look-dev + gate (unless it already passed), then one full-res still for the user's approval sheet
# (renders/approval/<concept>_<variant>.png, its gate copied next to it: lookdev.sh wipes its work folder on every run).
# Unattended; every render goes through lookdev.sh, so through Reactor's yielding GPU lock (Halloween first).
#   bash scripts/queue_approval.sh            -> log: renders/approval/queue_log.txt
# Pieces with a still already are skipped; a failing gate is logged and skipped (its author fixes the script).
set -u
here="$(cd "$(dirname "$0")" && pwd)"
root="$(dirname "$here")"
app="$root/renders/approval"
mkdir -p "$app"
log="$app/queue_log.txt"
ITEMS=(
  "cherenkov_pool blue 8" "cherenkov_pool uv 8" "cherenkov_pool deep 8"
  "control_rods amber 8" "control_rods cyan 8" "control_rods red 8"
  "chain_reaction cyan 8" "chain_reaction amber 8" "chain_reaction magenta 8"
  "meltdown ember 8" "meltdown alarm 8" "meltdown scram 8"
  "turbine_hall blue 8" "turbine_hall green 8"
  "coolant_pipes cyan 8" "coolant_pipes amber 8"
  "containment red 8" "containment amber 8" "containment breach 8"
  "particle_ring cyan 8" "particle_ring green 8"
  "geiger_scope green 8" "geiger_scope amber 8" "geiger_scope cyan 8"
  "isotope_lattice uv 8" "isotope_lattice gold 8" "isotope_lattice cyan 8"
  "hazard_type amber 8" "hazard_type red 8" "hazard_type blue 8"
  "sting amber 4" "sting blue 4" "sting red 4" "cold_start blue 8"
)
echo "$(date '+%m-%d %H:%M') queue start: ${#ITEMS[@]} pieces" >> "$log"
for it in "${ITEMS[@]}"; do
  set -- $it
  c=$1; v=$2; bars=$3; name="${c}_${v}"
  still="$app/${name}.png"; gate="$app/${name}_gate.txt"; work="$root/_work/lookdev_${name}"
  if [ -f "$still" ]; then echo "$(date +%H:%M) $name: still exists, skipped" >> "$log"; continue; fi
  if [ -f "$work/gate.txt" ] && grep -q "RESULT: PASS" "$work/gate.txt"; then cp "$work/gate.txt" "$gate"; fi
  if ! { [ -f "$gate" ] && grep -q "RESULT: PASS" "$gate"; }; then
    VJ_BARS=$bars bash "$here/lookdev.sh" "$c" "$v" > "$app/${name}_lookdev.log" 2>&1
    [ -f "$work/gate.txt" ] && cp "$work/gate.txt" "$gate"
    if ! { [ -f "$gate" ] && grep -q "RESULT: PASS" "$gate"; }; then
      why=$(grep -m1 "RESULT" "$gate" 2>/dev/null || tail -2 "$app/${name}_lookdev.log" | tr '\n' ' ')
      echo "$(date +%H:%M) $name: look-dev FAILED: $why" >> "$log"
      continue
    fi
  fi
  f=206; [ "$bars" = 4 ] && f=103                     # section B's first downbeat (bar 5; the sting's bar 3)
  FRAMES_ONLY="$f" VJ_BARS=$bars bash "$here/lookdev.sh" "$c" "$v" --pct 100 --samples 16 > "$app/${name}_still.log" 2>&1
  png="$work/frames/${name}_$(printf %04d $f).png"
  if [ -f "$png" ]; then cp "$png" "$still"; echo "$(date +%H:%M) $name: PASS, still f$f" >> "$log"
  else echo "$(date +%H:%M) $name: still render FAILED (see ${name}_still.log)" >> "$log"; fi
done
echo "$(date '+%m-%d %H:%M') queue done" >> "$log"
