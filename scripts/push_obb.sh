#!/usr/bin/env bash
# push_obb.sh [--push] [--env "Label=/Game/Long/Package/Name"] <pak> [<pak> ...]
#
# The way to update the patch OBB on the headset now that several stages share it (Dino chunks 50/53, Halloween 54,
# club 55). It MERGES into the OBB that is live on the headset, so a push can never drop another session's stage
# (make_obb.py alone writes a fresh zip of only the paks it is given). Same design as the club session's draft
# push_obb_merge.sh (2026-10-08), plus the compare-and-swap, the --env line and the paks_current mirror.
#   1. pull the live patch OBB and list its paks (size, md5)
#   2. replace same-named paks, add new ones; build the merged OBB the way make_obb.py does (stored zip, entries
#      TribeXR/Content/Paks/<pak>, comment "      2311")
#   3. --push only: refuse while Tribe runs; refuse if the live OBB changed since step 1 (another session pushed);
#      push to patch.new.tmp, mv over the live file (a running Tribe would keep its open inode), compare md5s
#   4. after a good push: mirror it to C:\Users\Chris\TribeUE\paks_current\ (patch_live.obb, the paks, paks.txt).
#      scripts/reseed.sh's PATCH= can point at paks_current/patch_live.obb so a re-seed restores every stage.
#   --env: also add that menu-box line to tribemod/envs.txt on the headset if it is missing. The mod shows at most
#      8 boxes (EM_MAX in hook/dumper.cpp); a 9th line is refused here instead of silently ignored there.
# Without --push it is a dry run: it builds the merged OBB and prints what it would ship. Paks mount only at Tribe's
# launch, so relaunch Tribe after a push.
set -euo pipefail
REPO="$(cd "$(dirname "$0")/.." && pwd)"
ADB_EXE="$REPO/tools/platform-tools/adb.exe"
SERIAL="${SERIAL:-2G0YC1ZF96072F}"
PKG=com.TribeXR.TribeXR
OBBDIR=/sdcard/Android/obb/$PKG
LIVE=$OBBDIR/patch.2311.$PKG.obb
TMOD=/sdcard/Android/data/$PKG/files/tribemod
MIRROR=/c/Users/Chris/TribeUE/paks_current
W="${OBB_WORK:-$MIRROR/work}"
adb() { MSYS_NO_PATHCONV=1 "$ADB_EXE" -s "$SERIAL" "$@"; }   # device paths (/sdcard/...) must reach adb as typed
win() { cygpath -m "$1"; }                                     # local paths for adb.exe / python: C:/...

PUSH=0; ENVLINE=""
while [[ $# -gt 0 ]]; do
    case "$1" in
        --push) PUSH=1; shift ;;
        --env) ENVLINE="$2"; shift 2 ;;
        -*) echo "unknown option $1"; exit 2 ;;
        *) break ;;
    esac
done
[[ $# -ge 1 ]] || { echo "usage: $0 [--push] [--env 'Label=/Game/...'] <pak>..."; exit 2; }
for p in "$@"; do [[ -f "$p" ]] || { echo "no such pak: $p"; exit 2; }; done
adb get-state >/dev/null 2>&1 || { echo "headset $SERIAL not connected over adb"; exit 1; }

rm -rf "$W"; mkdir -p "$W/paks"
echo "== pulling the live patch OBB =="
adb pull "$LIVE" "$(win "$W/live.obb")" >/dev/null
LIVE_MD5=$(md5sum "$W/live.obb" | cut -d' ' -f1)
echo "live OBB md5 $LIVE_MD5"
python - "$(win "$W/live.obb")" "$(win "$W/paks")" <<'PYEOF'
import hashlib, os, sys, zipfile
z = zipfile.ZipFile(sys.argv[1])
print("  comment", repr(z.comment))
for i in z.infolist():
    data = z.read(i.filename)
    open(os.path.join(sys.argv[2], os.path.basename(i.filename)), "wb").write(data)
    print(f"  {i.filename}  {len(data)} B  md5 {hashlib.md5(data).hexdigest()}")
PYEOF
for p in "$@"; do
    b=$(basename "$p")
    if [[ -f "$W/paks/$b" ]]; then echo "replace $b"; else echo "add $b"; fi
    cp "$p" "$W/paks/$b"
done
python - "$(win "$W/merged.obb")" "$(win "$W/paks")" <<'PYEOF'
import os, sys, zipfile
obb, d = sys.argv[1], sys.argv[2]
with zipfile.ZipFile(obb, "w", compression=zipfile.ZIP_STORED) as z:
    for n in sorted(os.listdir(d)):
        if n.endswith(".pak"):
            z.write(os.path.join(d, n), "TribeXR/Content/Paks/" + n)
    z.comment = b"      2311"
z = zipfile.ZipFile(obb)
for i in z.infolist():
    print("  merged:", i.filename, "stored" if i.compress_type == 0 else i.compress_type, i.file_size)
print("  comment:", repr(z.comment))
PYEOF
MD5=$(md5sum "$W/merged.obb" | cut -d' ' -f1)
echo "merged OBB $(stat -c %s "$W/merged.obb") B md5 $MD5"
if [[ $PUSH -eq 0 ]]; then echo "(dry run: nothing pushed)"; exit 0; fi

if adb shell pidof $PKG >/dev/null 2>&1; then echo "Tribe is RUNNING on the headset: not pushing (close it first)"; exit 3; fi
NOW_MD5=$(adb shell md5sum "$LIVE" | cut -d' ' -f1)
[[ "$NOW_MD5" == "$LIVE_MD5" ]] || { echo "the live OBB changed since the pull ($NOW_MD5): someone else pushed; re-run"; exit 4; }
adb push "$(win "$W/merged.obb")" "$OBBDIR/patch.new.tmp" >/dev/null
adb shell mv "$OBBDIR/patch.new.tmp" "$LIVE"
DEV_MD5=$(adb shell md5sum "$LIVE" | cut -d' ' -f1)
echo "device md5 $DEV_MD5"
[[ "$DEV_MD5" == "$MD5" ]] || { echo "MD5 MISMATCH after push"; exit 5; }
echo "PUSHED OK"

mkdir -p "$MIRROR/paks"
rm -f "$MIRROR/paks/"*.pak
cp "$W/paks/"*.pak "$MIRROR/paks/"
cp "$W/merged.obb" "$MIRROR/patch_live.obb"
{ echo "# what is live on the headset (written by scripts/push_obb.sh after a verified push)"
  echo "pushed $(date '+%F %T')  obb md5 $MD5  previous live md5 $LIVE_MD5"
  for f in "$MIRROR/paks/"*.pak; do echo "$(basename "$f")  $(stat -c %s "$f") B  md5 $(md5sum "$f" | cut -d' ' -f1)"; done
} > "$MIRROR/paks.txt"
cat "$MIRROR/paks.txt"

if [[ -n "$ENVLINE" ]]; then
    label="${ENVLINE%%=*}"; path="${ENVLINE#*=}"
    adb shell "cat $TMOD/envs.txt 2>/dev/null" | tr -d '\r' > "$W/envs.txt" || true
    if grep -q -F "=$path" "$W/envs.txt" || grep -q -F "$label=" "$W/envs.txt"; then
        echo "envs.txt already has '$label' or its level: unchanged"
    else
        n=$(grep -c -v -e '^#' -e '^[[:space:]]*$' "$W/envs.txt" || true)
        if [[ $n -ge 8 ]]; then
            echo "envs.txt already lists $n boxes; the mod shows at most 8 (EM_MAX in hook/dumper.cpp): NOT adding '$label'"
            exit 6
        fi
        [[ -s "$W/envs.txt" && -n "$(tail -c1 "$W/envs.txt")" ]] && echo >> "$W/envs.txt"
        echo "$ENVLINE" >> "$W/envs.txt"
        adb push "$(win "$W/envs.txt")" /data/local/tmp/tribemod_put.tmp >/dev/null
        adb shell "cp /data/local/tmp/tribemod_put.tmp '$TMOD/envs.txt' && chmod 666 '$TMOD/envs.txt'; rm -f /data/local/tmp/tribemod_put.tmp"
        echo "envs.txt on the headset now:"; adb shell "cat $TMOD/envs.txt"
    fi
fi
