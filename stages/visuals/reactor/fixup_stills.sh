#!/usr/bin/env bash
# Approval stills the queue (queue_approval.sh) didn't make or made at the wrong frame (club session, 2026-10-09):
#   control_rods: f206 is the instant every rod has slammed in (a flat row); f240 has half the banks out, gaps glowing
#   geiger_scope: the trefoil (section B's highlight) is fully formed f309-f360; f330 is its middle
#   particle_ring magenta: fixed by its author after the queue had passed it (f206 as the queue)
#   (chain_reaction x3 is held: vj-core's brightening pass 3, 22:34; its stills come at f287, the bar-6 bloom, once it
#   reports the script final)
# Only pieces whose look-dev gate passed (renders/approval/<name>_gate.txt, or the look-dev's own gate.txt, copied first:
# lookdev.sh wipes its work folder on every run). Run after queue_approval.sh has finished.
#   bash scripts/fixup_stills.sh
set -u
here="$(cd "$(dirname "$0")" && pwd)"
root="$(dirname "$here")"
app="$root/renders/approval"
log="$app/queue_log.txt"
ITEMS=("control_rods amber 240" "control_rods cyan 240" "control_rods red 240"
       "geiger_scope green 330" "geiger_scope amber 330" "geiger_scope cyan 330"
       "particle_ring magenta 206")
echo "$(date '+%m-%d %H:%M') fix-up start: ${#ITEMS[@]} stills" >> "$log"
for it in "${ITEMS[@]}"; do
  set -- $it
  c=$1; v=$2; f=$3; name="${c}_${v}"; work="$root/_work/lookdev_${name}"; gate="$app/${name}_gate.txt"
  if [ -f "$work/gate.txt" ] && grep -q "RESULT: PASS" "$work/gate.txt"; then cp "$work/gate.txt" "$gate"; fi
  if ! grep -q "RESULT: PASS" "$gate" 2>/dev/null; then
    echo "$(date +%H:%M) $name: no passing gate, still not rendered" >> "$log"; continue
  fi
  FRAMES_ONLY="$f" bash "$here/lookdev.sh" "$c" "$v" --pct 100 --samples 16 > "$app/${name}_still.log" 2>&1
  png="$work/frames/${name}_$(printf %04d $f).png"
  if [ -f "$png" ]; then cp "$png" "$app/${name}.png"; echo "$(date +%H:%M) $name: still f$f" >> "$log"
  else echo "$(date +%H:%M) $name: still render FAILED (see ${name}_still.log)" >> "$log"; fi
done
echo "$(date '+%m-%d %H:%M') fix-up done" >> "$log"
