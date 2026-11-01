#!/usr/bin/env bash
# Reactor final renders (club session, 2026-10-10; the user approved all 40 approval stills). Every piece goes through
# make_loop.sh one at a time (render under Reactor's yielding GPU lock, so Halloween goes first; then gate, encode, gate,
# contact sheet). Each passing MP4 is copied to deliver/Loops/ ("Reactor - Cherenkov Pool (blue) 140bpm.mp4"). Once all
# 40 are done, the hour set is assembled (assemble_set.py, CPU only).
#   bash scripts/queue_finals.sh            -> log: renders/queue_finals_log.txt (+ renders/<concept>/<name>_make.log)
# Unattended. A piece whose MP4 is done (its gate ends "== DONE") is skipped, so a re-run resumes.
# A failing gate is logged and skipped; its frames stay in _work/ for the author.
# The queue stops after two render/encode failures in a row, or when C: has less than 8 GB free.
# (C: is about 98% full, and each render holds about 1 GB of frames until it passes.)
set -u
here="$(cd "$(dirname "$0")" && pwd)"
root="$(dirname "$here")"
log="$root/renders/queue_finals_log.txt"
loops="$root/deliver/Loops"
mkdir -p "$loops"
bpm="${VJ_BPM:-140}"
declare -A TITLE=([cherenkov_pool]="Cherenkov Pool" [control_rods]="Control Rods" [chain_reaction]="Chain Reaction"
  [meltdown]="Meltdown" [cooling_towers]="Cooling Towers" [turbine_hall]="Turbine Hall" [coolant_pipes]="Coolant Pipes"
  [containment]="Containment" [particle_ring]="Particle Ring" [geiger_scope]="Geiger Scope"
  [isotope_lattice]="Isotope Lattice" [hazard_type]="Hazard Type" [sting]="Reactor Sting" [cold_start]="Cold Start")
ITEMS=(                                                   # the short specials first: they prove the pipeline quickly
  "cold_start blue 8" "sting amber 4" "sting blue 4" "sting red 4"
  "cherenkov_pool blue 8" "cherenkov_pool uv 8" "cherenkov_pool deep 8"
  "control_rods amber 8" "control_rods cyan 8" "control_rods red 8"
  "chain_reaction cyan 8" "chain_reaction amber 8" "chain_reaction magenta 8"
  "meltdown ember 8" "meltdown alarm 8" "meltdown scram 8"
  "cooling_towers teal 8" "cooling_towers orange 8" "cooling_towers purple 8"
  "turbine_hall amber 8" "turbine_hall blue 8" "turbine_hall green 8"
  "coolant_pipes cyan 8" "coolant_pipes amber 8" "coolant_pipes uv 8"
  "containment red 8" "containment amber 8" "containment breach 8"
  "particle_ring magenta 8" "particle_ring cyan 8" "particle_ring green 8"
  "geiger_scope green 8" "geiger_scope amber 8" "geiger_scope cyan 8"
  "isotope_lattice uv 8" "isotope_lattice gold 8" "isotope_lattice cyan 8"
  "hazard_type amber 8" "hazard_type red 8" "hazard_type blue 8"
)
say() { echo "$(date '+%m-%d %H:%M') $*" | tee -a "$log"; }

say "queue start: ${#ITEMS[@]} pieces at $bpm BPM"
fails=0
done_n=0
for it in "${ITEMS[@]}"; do
  set -- $it
  c=$1; v=$2; bars=$3; name="${c}_${v}"
  mp4="$root/renders/$c/${name}_${bpm}bpm_${bars}bars_1080p30.mp4"
  gate="${mp4%.mp4}_gate.txt"
  dst="$loops/Reactor - ${TITLE[$c]} ($v) ${bpm}bpm.mp4"
  if [ -f "$mp4" ] && grep -q "^== DONE" "$gate" 2>/dev/null; then
    [ -f "$dst" ] || cp "$mp4" "$dst"
    say "$name: done already, skipped"
    done_n=$((done_n + 1))
    continue
  fi
  free=$(df -k /c | awk 'NR==2 {print $4}')
  if [ "$free" -lt 8388608 ]; then
    say "STOP: C: has $((free / 1048576)) GB free (less than 8 GB)"
    break
  fi
  mkdir -p "$root/renders/$c"
  mlog="$root/renders/$c/${name}_make.log"
  t0=$(date +%s)
  VJ_BARS=$bars bash "$here/make_loop.sh" "$c" "$v" > "$mlog" 2>&1
  rc=$?
  t1=$(date +%s)
  if [ "$rc" = 0 ] && [ -f "$mp4" ]; then
    cp "$mp4" "$dst"
    say "$name: PASS, $(((t1 - t0) / 60)) min with the lock wait ($(grep -m1 '^== rendered' "$gate" | sed 's/^== //')); delivered"
    fails=0
    done_n=$((done_n + 1))
  else
    say "$name: FAILED (exit $rc): $(grep -m1 -E 'RENDER FAILED|ENCODE FAILED|RESULT: FAIL' "$mlog" || tail -1 "$mlog")"
    if grep -q -E "RENDER FAILED|ENCODE FAILED" "$mlog"; then fails=$((fails + 1)); else fails=0; fi
    if [ "$fails" -ge 2 ]; then
      say "STOP: two render/encode failures in a row"
      break
    fi
  fi
done
say "renders: $done_n/${#ITEMS[@]} done"
if [ "$done_n" = "${#ITEMS[@]}" ]; then
  say "assembling the set (CPU only)"
  if python "$here/assemble_set.py" --out "$root/deliver/Reactor Visuals - Full Set.mp4" > "$root/renders/assemble_set.log" 2>&1; then
    say "set DONE: deliver/Reactor Visuals - Full Set.mp4 ($(tail -1 "$root/renders/assemble_set.log"))"
  else
    say "set FAILED: see renders/assemble_set.log"
  fi
fi
say "queue end"
