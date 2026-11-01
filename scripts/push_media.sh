#!/usr/bin/env bash
# push_media.sh "<Movies subfolder>" <file> [<file> ...]
# Copies videos for Tribe's media-folder visuals wall to /sdcard/Movies/<subfolder>/ on the headset (e.g.
# "Halloween Visuals"), skipping files whose md5 already matches, and verifies every copy by md5. It never deletes
# anything on the headset. Safe while Tribe runs (new files show up in the Media tab after a rescan or relaunch).
set -u -o pipefail
REPO="$(cd "$(dirname "$0")/.." && pwd)"
ADB_EXE="$REPO/tools/platform-tools/adb.exe"
SERIAL="${SERIAL:-2G0YC1ZF96072F}"
adb() { MSYS_NO_PATHCONV=1 "$ADB_EXE" -s "$SERIAL" "$@"; }
win() { cygpath -m "$1"; }
[[ $# -ge 2 ]] || { echo "usage: $0 \"<Movies subfolder>\" <file>..."; exit 2; }
SUB="$1"; shift
DEST="/sdcard/Movies/$SUB"
adb get-state >/dev/null 2>&1 || { echo "headset $SERIAL not connected over adb"; exit 1; }
adb shell "mkdir -p \"$DEST\"" || { echo "cannot create $DEST"; exit 1; }
ok=0; skipped=0; bad=0
for f in "$@"; do
    [[ -f "$f" ]] || { echo "missing: $f"; bad=$((bad + 1)); continue; }
    name="$(basename "$f")"
    lmd5=$(md5sum "$f" | cut -d' ' -f1)
    rmd5=$(adb shell "md5sum \"$DEST/$name\" 2>/dev/null" | tr -d '\r' | cut -d' ' -f1)
    if [[ "$rmd5" == "$lmd5" ]]; then
        echo "same   $name"; skipped=$((skipped + 1)); continue
    fi
    adb push "$(win "$f")" "$DEST/$name" > /dev/null || { echo "FAILED push $name"; bad=$((bad + 1)); continue; }
    rmd5=$(adb shell "md5sum \"$DEST/$name\"" | tr -d '\r' | cut -d' ' -f1)
    if [[ "$rmd5" == "$lmd5" ]]; then
        echo "pushed $name ($(stat -c %s "$f") B, md5 $lmd5)"; ok=$((ok + 1))
    else
        echo "MD5 MISMATCH $name (local $lmd5, headset $rmd5)"; bad=$((bad + 1))
    fi
done
echo "$DEST: $ok pushed, $skipped already there, $bad failed"
[[ $bad == 0 ]]
