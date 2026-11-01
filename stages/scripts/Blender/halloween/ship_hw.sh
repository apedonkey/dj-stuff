#!/usr/bin/env bash
# ship_hw.sh [--fast] [--stock] [--skip-bake] [--push]  --  GRAVEYARD SHIFT end to end (plan 9.2), stopping at the first
# failed gate:
#   1. bake          run_hw_stage.sh (GPU lock) -> out_hw (HW_OUT overrides; --fast = the 30-s pipeline check)
#   2. comfort       hw_cuecheck.py must PASS (the user's flash rules, modelled from the shipped cue table)
#   3. overdraw      hw_overdraw.py: the DJ's occluded translucent layers must stay <= 2.5 per pixel (plan budget)
#   4. drone reel    hw_dronecheck.py on claudedocs/halloween_drone_path.txt (a report: the reel is a separate file)
#   5. unreal        cook_halloween.sh build (HW_ANIM=1 unless --stock), cook, pack; no material may fail to compile
#   6. shaders       the chunk-54 manifest must list the ShaderArchive (an animated build without it shows grey)
#   7. push          push_obb.sh dry run, or the real merge push with --push (it refuses while Tribe runs)
# Logs: <out>/ship_*.log. Nothing here touches the Dino or club files.
set -u -o pipefail
HERE=/c/Users/Chris/TribeUE/TribeXR/Scripts/Blender/halloween
OUT="${HW_OUT:-$HERE/out_hw}"
COOK=/d/TribeUE/MetaHw/TribeXR/Scripts/cook_halloween.sh
PAK=/d/TribeUE/MetaHw/TribeXR/Saved/ModPak/pakchunk54-Android_ASTC_P.pak
MANI=/d/TribeUE/MetaHw/TribeXR/Saved/Cooked/Android_ASTC/TribeXR/Metadata/ChunkManifest/pakchunk54.txt
COOKLOG=/d/TribeUE/MetaHw/logs/cook_halloween.log
REPO="/c/Users/Chris/OneDrive/Desktop/tribe hack"
REEL="$REPO/claudedocs/halloween_drone_path.txt"
ENV_LINE="Graveyard Shift=/Game/Mods/Halloween/Maps/Environment_Halloween"
FAST=0; STOCK=0; BAKE=1; PUSH=0
for a in "$@"; do
    case "$a" in
        --fast) FAST=1 ;; --stock) STOCK=1 ;; --skip-bake) BAKE=0 ;; --push) PUSH=1 ;;
        *) echo "unknown option $a"; exit 2 ;;
    esac
done
step() { echo; echo "== $(date '+%H:%M:%S') $*"; }
die() { echo "SHIP STOPPED: $*"; exit 1; }
win() { cygpath -m "$1"; }

if [[ $BAKE == 1 ]]; then
    step "1 bake -> $OUT"
    HW_OUT="$(win "$OUT")" bash "$HERE/run_hw_stage.sh" $([[ $FAST == 1 ]] && echo --fast) | tail -12 \
        || die "bake failed (log $OUT/bake.log)"
    grep -a -q "\[HW.*\] done" "$OUT/bake.log" || die "the bake did not finish (log $OUT/bake.log)"
fi
grep -a -E "laser unit|lasers:|laser verification|laser PROBLEM|HIT|REJECTED|BUILD FAILED|hinged parts|module .*: lit" "$OUT/bake.log" | sed 's/^\[HW *[0-9.]*s\] /  /'
grep -a -q "laser verification .*, 0 problems; .* OK" "$OUT/bake.log" \
    || die "the laser verification found problems or did not run (v3: every beam clear over its whole sweep)"

step "2 comfort check"
python "$HERE/hw_cuecheck.py" "$(win "$OUT")" > "$OUT/ship_cuecheck.log" 2>&1
rc=$?
grep -a -E "FAIL|PASS|sky at a full" "$OUT/ship_cuecheck.log" | sed 's/^\[CUECHECK\] /  /'
[[ $rc == 0 ]] || die "comfort check failed ($OUT/ship_cuecheck.log)"

step "3 overdraw"
bash "$HERE/run_blender_locked.sh" "$(win "$OUT")/ship_overdraw.log" "$(win "$HERE")/hw_overdraw.py" "$(win "$OUT")" \
    > /dev/null || die "overdraw run failed ($OUT/ship_overdraw.log)"
grep -a "occluded, animated\|occluded, stock" "$OUT/ship_overdraw.log" | sed 's/^\[OVERDRAW\] /  /'
dj=$(grep -a "\] dj occluded, animated" "$OUT/ship_overdraw.log" | sed -E 's/.*mean ([0-9.]+) layers.*/\1/')
python -c "import sys; sys.exit(0 if float('${dj:-99}') <= 2.5 else 1)" || die "DJ overdraw ${dj:-?} > 2.5 layers/px"

step "4 drone reel (report)"
bash "$HERE/run_blender_locked.sh" "$(win "$OUT")/ship_drone.log" "$(win "$HERE")/hw_dronecheck.py" "$(win "$REEL")" \
    "$(win "$OUT")" > /dev/null
grep -a "\[DRONE\] line\|PASS\|FAIL" "$OUT/ship_drone.log" | sed 's/^\[DRONE\] /  /' | tail -16

step "5 unreal build ($([[ $STOCK == 1 ]] && echo stock || echo animated)), cook, pack"
HW_ANIM=$([[ $STOCK == 1 ]] && echo 0 || echo 1) HW_SRC="$(win "$OUT")" bash "$COOK" build | tail -6 || die "unreal build failed"
bash "$COOK" cook | tail -3 || die "cook failed"
if grep -a -q "Failed to compile\|valid ShaderMap" "$COOKLOG"; then
    grep -a "Failed to compile" -A1 "$COOKLOG" | head -8
    die "a material failed to compile for the Quest"
fi
bash "$COOK" pack | tail -3 || die "pack failed"

step "6 shader archive in chunk 54"
n=$(grep -ci shaderarchive "$MANI" || true)
echo "  manifest $(wc -l < "$MANI") entries, shader archive entries: $n"
[[ $STOCK == 1 || ${n:-0} -ge 1 ]] || die "no ShaderArchive in chunk 54: the animated materials would not load"
ls -la "$PAK"

step "7 push_obb.sh $([[ $PUSH == 1 ]] && echo PUSH || echo dry run)"
bash "$REPO/scripts/push_obb.sh" $([[ $PUSH == 1 ]] && echo --push) --env "$ENV_LINE" "$PAK" | tail -14
echo; echo "ship_hw.sh finished $(date '+%H:%M:%S')"
