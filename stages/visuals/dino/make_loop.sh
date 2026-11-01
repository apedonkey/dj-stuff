#!/usr/bin/env bash
# The whole pipeline for one loop variant:
#   render (under the GPU lock) -> gate the frames -> encode -> gate the MP4 -> still + contact sheet.
#   scripts/make_loop.sh <your-name> <concept> <variant> [extra scene args, e.g. --samples 6; not --bpm]
# e.g. scripts/make_loop.sh visuals raptor_run green
# The scene script is scripts/<concept>.py; it takes --variant and must call vj.finish(scene, "<concept>_<variant>").
# Output: renders/<concept>/<concept>_<variant>_<bpm>bpm_8bars_1080p30.mp4 (+ _still_fNNN.png, _contact.png).
# Frames go to Visuals/_work/<your-name>_<concept>_<variant>/ and are deleted once everything passes
# (KEEP_FRAMES=1 keeps them). Tempo: VJ_BPM (default 140) and VJ_HALFTIME (default 1; 0 = straight 4-on-the-floor, as
# the 128 BPM extras were made). One Blender run renders the loop and its frame N (the seam check) under one lock hold.
# Exit code 0 only if both gates pass.
set -u
here="$(cd "$(dirname "$0")" && pwd)"
root="$(dirname "$here")"
who="$1"; concept="$2"; var="$3"; shift 3
B=/d/Tools/blender-4.5.14-windows-x64/blender.exe
bpm="${VJ_BPM:-140}"
if [ "${VJ_HALFTIME:-1}" = "1" ]; then feel=--halftime; else feel=--straight; fi
name="${concept}_${var}"
mp4="$root/renders/$concept/${name}_${bpm%.*}bpm_8bars_1080p30.mp4"
work="$root/_work/${who}_${name}"
n=$(python -c "print(int(round(32 * 30 * 60 / $bpm)))")
seam_png="$work/seam/${name}_$(printf %04d "$n").png"
rm -rf "$work"
mkdir -p "$work/frames" "$work/seam" "$root/renders/$concept"
log="$work/render.log"

source "$here/gpu_lock.sh"
gpu_lock_acquire "$who" "render $name ${bpm}bpm"
trap gpu_lock_release EXIT
t0=$(date +%s)
"$B" -b --factory-startup --python "$here/$concept.py" -- --variant "$var" "$@" --bpm "$bpm" $feel --samples 16 --mblur \
  --all --out "$work/frames" --seam "$work/seam" > "$log" 2>&1     # extra args first: vj.arg takes the first one
t1=$(date +%s)
gpu_lock_release
trap - EXIT

got=$(ls "$work/frames" | grep -c "^${name}_[0-9]*\.png$")
if [ "$got" != "$n" ] || [ ! -f "$seam_png" ] || grep -qi "traceback" "$log"; then
  echo "RENDER FAILED: $got/$n frames, seam frame $( [ -f "$seam_png" ] && echo ok || echo missing ); see $log"
  grep -i -A3 "traceback\|error" "$log" | head -20
  exit 1
fi
echo "== rendered $n frames + the seam frame in $((t1 - t0)) s"
echo "== gate: frames"
python "$here/check_loop.py" "$work/frames" "${name}_" --seam "$seam_png" --bpm "$bpm" $feel \
  || { echo "frames kept: $work"; exit 1; }
"$B" -b --factory-startup --python "$here/encode.py" -- --frames "$work/frames" --prefix "${name}_" --out "$mp4" \
  > "$work/encode.log" 2>&1 || { echo "ENCODE FAILED: see $work/encode.log"; exit 1; }
echo "== gate: $mp4"
python "$here/check_loop.py" --video "$mp4" --bpm "$bpm" $feel || { echo "frames kept: $work"; exit 1; }
python "$here/contact_sheet.py" "$mp4" --title "$(echo "$name" | tr '_' ' ' | tr '[:lower:]' '[:upper:]')" --bpm "$bpm"
ffprobe -v error -count_frames -show_entries stream=codec_name,profile,pix_fmt,width,height,r_frame_rate,nb_read_frames \
  -show_entries format=duration,size -of compact=p=0:nk=0 "$mp4"
if [ "${KEEP_FRAMES:-0}" = "1" ]; then echo "frames kept: $work"; else rm -rf "$work"; fi
echo "== DONE $name"
