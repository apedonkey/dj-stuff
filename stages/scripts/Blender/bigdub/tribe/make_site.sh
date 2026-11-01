#!/usr/bin/env bash
# make_site.sh -- BIG DUB (Tribe): the Main Stage's site, end to end, into tribe/out/gen (about 2 minutes):
#   1. gen/bd_site.py   the game's BIG DUB generator (a copy of D:/VRDJ/tools/bigdub, read only there) with the TRIBE
#                       changes: the Main Stage alone (no Pavilion, New Camp, bridges, path lights or festoons), its own
#                       light map, the ground and the ring's walls exported in the Tribe frame
#   2. tribe_post.py    the LED wall becomes Tribe's SM_DinoVisualScreen; the game's booth table comes out
#   3. gen/bd_blender.py every mesh to FBX (Blender 4.5, headless)
# Needs python 3.11+ with numpy, scipy, PIL, tifffile in the user site (hence -P), the geodata in D:/TribeUE/bigdub_geo.
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
OUT="$HERE/out/gen"
BLENDER="${BLENDER:-/d/Tools/blender-4.5.14-windows-x64/blender.exe}"
mkdir -p "$OUT"
echo "== 1. site (bd_site.py)"
PYTHONPATH="$HERE/gen" python -P -B "$HERE/gen/bd_site.py" > "$OUT/gen.log" 2>&1 || { tail -20 "$OUT/gen.log"; exit 1; }
grep -a "TRIBE\|budget at Main\|wrote" "$OUT/gen.log"
# the game's dancers and walking collision are not shipped (the Tribe crowd and the Tribe walking map replace them)
rm -f "$OUT"/meshes/SM_BdCrowd*.npz "$OUT"/meshes/SM_BdWalk*.npz
echo "== 2. Tribe changes (tribe_post.py)"
PYTHONPATH="$HERE/gen" python -P -B "$HERE/tribe_post.py"
echo "== 3. FBX (bd_blender.py)"
rm -rf "$OUT/fbx"
"$BLENDER" -b --factory-startup --python "$HERE/gen/bd_blender.py" > "$OUT/blender.log" 2>&1
grep -a -q "\[bigdub\] done" "$OUT/blender.log" || { echo "Blender failed: $OUT/blender.log"; exit 1; }
grep -a "\[bigdub\] done" "$OUT/blender.log"
echo "make_site.sh done: $(ls "$OUT/fbx" | wc -l) FBX in $OUT/fbx"
