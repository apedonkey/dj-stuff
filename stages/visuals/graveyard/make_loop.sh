#!/usr/bin/env bash
# The whole pipeline for one Halloween loop:
#   render (under the GPU lock) -> gate the frames -> encode (~16 Mbps) -> gate the MP4 -> still + contact sheet.
#   bash scripts/make_loop.sh <concept> <variant> [extra scene args, e.g. --samples 24; not --bpm/--bars]
# The scene script is scripts/<concept>.py; it takes --variant and calls vj.finish(scene, "<concept>_<variant>").
# Output: renders/<concept>/<concept>_<variant>_<bpm>bpm_<bars>bars_1080p30.mp4 (+ _still_fNNN.png, _contact.png,
# _gate.txt with both gate reports). Frames go to _work/<concept>_<variant>/ and are deleted once everything passes
# (KEEP_FRAMES=1 keeps them). Tempo/length: VJ_BPM (140), VJ_HALFTIME (1), VJ_BARS (8; the sting is 4). One Blender
# run renders the loop and its frame N (the seam check) under one lock hold. Exit code 0 only if both gates pass.
set -u
here="$(cd "$(dirname "$0")" && pwd)"
root="$(dirname "$here")"
concept="$1"; var="$2"; shift 2
B=/d/Tools/blender-4.5.14-windows-x64/blender.exe
bpm="${VJ_BPM:-140}"
bars="${VJ_BARS:-8}"
if [ "${VJ_HALFTIME:-1}" = "1" ]; then feel=--halftime; else feel=--straight; fi
name="${concept}_${var}"
mp4="$root/renders/$concept/${name}_${bpm%.*}bpm_${bars}bars_1080p30.mp4"
gate="${mp4%.mp4}_gate.txt"
work="$root/_work/${name}"
n=$(python -c "print(int(round($bars * 4 * 30 * 60 / $bpm)))")
seam_png="$work/seam/${name}_$(printf %04d "$n").png"
rm -rf "$work"
mkdir -p "$work/frames" "$work/seam" "$root/renders/$concept"
log="$work/render.log"

source "$here/gpu_lock.sh"
gpu_lock_acquire "$name final render"
trap 'gpu_lock_release' EXIT
trap 'gpu_lock_release; exit 130' INT TERM HUP
t0=$(date +%s)
"$B" -b --factory-startup --python "$here/$concept.py" -- --variant "$var" "$@" --bpm "$bpm" --bars "$bars" $feel \
  --samples 16 --mblur --all --out "$work/frames" --seam "$work/seam" > "$log" 2>&1   # extra args first: vj.arg
t1=$(date +%s)                                                                           # takes the first one
gpu_lock_release
trap - EXIT INT TERM HUP

got=$(ls "$work/frames" | grep -c "^${name}_[0-9]*\.png$")
if [ "$got" != "$n" ] || [ ! -f "$seam_png" ] || grep -qi "traceback" "$log"; then
  echo "RENDER FAILED: $got/$n frames, seam frame $( [ -f "$seam_png" ] && echo ok || echo missing ); see $log"
  grep -i -A3 "traceback\|error" "$log" | head -20
  exit 1
fi
echo "== rendered $n frames + the seam frame in $((t1 - t0)) s" | tee "$gate"
echo "== gate: frames" | tee -a "$gate"
python "$here/check_loop.py" "$work/frames" "${name}_" --seam "$seam_png" --bpm "$bpm" --bars "$bars" $feel \
  | tee -a "$gate"
[ "${PIPESTATUS[0]}" = "0" ] || { echo "frames kept: $work"; exit 1; }
python "$here/encode.py" "$work/frames" "${name}_" "$mp4" --frames "$n" > "$work/encode.log" 2>&1 \
  || { echo "ENCODE FAILED: see $work/encode.log"; cat "$work/encode.log" | tail -5; exit 1; }
echo "== gate: $(basename "$mp4")" | tee -a "$gate"
python "$here/check_loop.py" --video "$mp4" --bpm "$bpm" --bars "$bars" $feel | tee -a "$gate"
[ "${PIPESTATUS[0]}" = "0" ] || { echo "frames kept: $work"; exit 1; }
title=$(echo "$concept" | tr '_' ' ' | tr '[:lower:]' '[:upper:]')
python "$here/contact_sheet.py" "$mp4" --title "$title" --bpm "$bpm" --bars "$bars" | tee -a "$gate"
ffprobe -v error -count_frames -show_entries stream=codec_name,profile,pix_fmt,width,height,r_frame_rate,nb_read_frames,bit_rate \
  -show_entries format=duration,size,bit_rate -of compact=p=0:nk=0 "$mp4" | tee -a "$gate"
if [ "${KEEP_FRAMES:-0}" = "1" ]; then echo "frames kept: $work"; else rm -rf "$work"; fi
echo "== DONE $name" | tee -a "$gate"
