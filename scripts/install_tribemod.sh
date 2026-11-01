#!/usr/bin/env bash
# install_tribemod.sh -- install the Tribe XR mod (Tribe 0.12.6, versionCode 2311) on a Quest over adb.
#
#   scripts/install_tribemod.sh [options] <release folder>
#
# The release folder holds the files from the GitHub release, side by side:
#   tribemod-2311.apk             the mod, signed CN=Tribe Mod (--apk picks another, e.g. a copy you re-signed)
#   main.2311.com.TribeXR.TribeXR.obb    Tribe's own game data for build 2311
#   patch.2311.com.TribeXR.TribeXR.obb   the four stages (pak chunks 50, 53, 54 and 55)
#   tribemod-starter.zip                 characters, heads, stage files, light scripts and settings
#
# Options:
#   --apk <file>     install this APK instead of the one in the folder
#   --serial <id>    the headset to use when several are connected (default: $ANDROID_SERIAL, or the only one)
#   --media <dir>    also copy a folder of videos to /sdcard/Movies/<folder name>/ for the visuals wall (repeatable)
#   --yes            don't ask before uninstalling Tribe
#   ADB=<path>       environment variable: the adb to use (default: adb on PATH)
#
# Steps:
#   1. adb install -r. If Android refuses because Tribe is installed with another signing key or a newer version, it
#      asks, uninstalls Tribe (that deletes Tribe's data and OBBs on this headset) and installs again.
#   2. Pushes each OBB that is missing or different (checked by size, then md5).
#   3. Copies the starter files into tribemod/ and makes them readable for Tribe (files 666, folders 777). They are
#      staged in /data/local/tmp first, because a plain adb push into Android/data can silently vanish on Horizon OS.
#   4. Creates the feature switches and grants Tribe's storage permissions (needed for the media wall and 360 videos).
# It changes nothing outside Tribe's package, its OBB folder and /sdcard/Movies (only with --media).
#
# Then, in the headset: launch Tribe and tap OPEN APP on Meta's unofficial-app dialog (if it only offers Restore and
# Close, tap Close and launch again). Never tap Restore: it reinstalls the Store build and deletes the mod with its
# files. Put the headset on, and stand still with straight arms for a second.
set -euo pipefail

PKG=com.TribeXR.TribeXR
OBB_DIR=/sdcard/Android/obb/$PKG
TMOD=/sdcard/Android/data/$PKG/files/tribemod
STAGE=/data/local/tmp/tribemod_stage
FLAGS="executor_on auto_load auto_actor body_tracking skin_menu env_menu drone_cam"

ADB="${ADB:-adb}"; APK=""; SERIAL="${ANDROID_SERIAL:-}"; YES=0; MEDIA=()
usage(){ awk 'NR == 1 { next } /^#/ { sub(/^# ?/, ""); print; next } { exit }' "$0"; exit 2; }
while [[ $# -gt 0 ]]; do
    case "$1" in
        --apk) APK="$2"; shift 2 ;;
        --serial) SERIAL="$2"; shift 2 ;;
        --media) MEDIA+=("$2"); shift 2 ;;
        --yes|-y) YES=1; shift ;;
        -h|--help) usage ;;
        -*) echo "unknown option: $1"; usage ;;
        *) break ;;
    esac
done
[[ $# -eq 1 ]] || usage
REL="${1%/}"

# Git Bash on Windows: device paths (/sdcard/...) must reach adb.exe as typed, and local paths need converting.
adb(){ MSYS_NO_PATHCONV=1 "$ADB" ${SERIAL:+-s "$SERIAL"} "$@"; }
lp(){ if command -v cygpath >/dev/null 2>&1; then cygpath -m "$1"; else printf '%s' "$1"; fi; }
lsize(){ wc -c < "$1" | tr -d ' '; }
lmd5(){ if command -v md5sum >/dev/null 2>&1; then md5sum "$1" | cut -d' ' -f1; else md5 -q "$1"; fi; }
rsh(){ adb shell "$1" 2>/dev/null | tr -d '\r'; }

# --- preflight: adb, one headset, every file present -------------------------------------------------------------
command -v "$ADB" >/dev/null 2>&1 || { echo "adb not found: install Android platform-tools or set ADB=/path/to/adb"; exit 1; }
if [[ -z "$SERIAL" ]]; then
    n=$(MSYS_NO_PATHCONV=1 "$ADB" devices | awk 'NR>1 && $2=="device"' | wc -l | tr -d ' ')
    [[ "$n" == 1 ]] || { echo "$n headsets connected and ready; pick one with --serial"; "$ADB" devices; exit 1; }
fi
adb get-state >/dev/null 2>&1 || { echo "headset not reachable over adb (asleep? USB debugging allowed?)"; exit 1; }

[[ -n "$APK" ]] || APK=$(ls "$REL"/tribemod-*.apk 2>/dev/null | head -1 || true)
MAIN="$REL/main.2311.$PKG.obb"; PATCH="$REL/patch.2311.$PKG.obb"
START="$REL/tribemod-starter"; ZIP="$REL/tribemod-starter.zip"
for f in "$APK" "$MAIN" "$PATCH"; do [[ -n "$f" && -f "$f" ]] || { echo "missing file: ${f:-the mod APK (tribemod-*.apk)}"; exit 1; }; done
if [[ ! -d "$START" ]]; then
    [[ -f "$ZIP" ]] || { echo "missing: $ZIP"; exit 1; }
    command -v unzip >/dev/null 2>&1 || { echo "no unzip here: unzip $ZIP into $REL first"; exit 1; }
    unzip -q "$ZIP" -d "$REL"
fi
[[ -d "$START/skins" ]] || { echo "$START is not the starter folder (it has no skins/)"; exit 1; }
for m in ${MEDIA[@]+"${MEDIA[@]}"}; do [[ -d "$m" ]] || { echo "--media: not a folder: $m"; exit 1; }; done

# --- 1. the APK ----------------------------------------------------------------------------------------------------
echo "== 1/4 installing $(basename "$APK")"
out=$(adb install -r "$(lp "$APK")" 2>&1 || true)
if grep -q 'Success' <<<"$out"; then
    echo "   updated in place: Tribe's data, OBBs and login are kept"
elif grep -q -E 'INSTALL_FAILED_UPDATE_INCOMPATIBLE|INSTALL_FAILED_VERSION_DOWNGRADE|signatures do not match' <<<"$out"; then
    grep -o -E 'INSTALL_FAILED_[A-Z_]+' <<<"$out" | head -1 | sed 's/^/   Android refused the update: /'
    echo "   The Tribe on this headset has another signing key or a newer version, so it has to be uninstalled first."
    echo "   That deletes Tribe's data and OBBs on this headset."
    if [[ $YES -ne 1 ]]; then
        read -r -p "   Uninstall Tribe and install the mod? [y/N] " a
        [[ "$a" == y || "$a" == Y ]] || { echo "   stopped; nothing was changed"; exit 1; }
    fi
    adb uninstall "$PKG" >/dev/null
    out=$(adb install "$(lp "$APK")" 2>&1 || true)
    grep -q 'Success' <<<"$out" || { echo "$out"; echo "   install failed"; exit 1; }
    echo "   installed fresh"
else
    echo "$out"; echo "   install failed"; exit 1
fi

# --- 2. the OBBs ---------------------------------------------------------------------------------------------------
echo "== 2/4 OBBs"
rsh "mkdir -p $OBB_DIR" >/dev/null
for f in "$MAIN" "$PATCH"; do
    name=$(basename "$f"); size=$(lsize "$f")
    if [[ "$(rsh "stat -c %s $OBB_DIR/$name")" == "$size" ]] && \
       [[ "$(rsh "md5sum $OBB_DIR/$name" | cut -d' ' -f1)" == "$(lmd5 "$f")" ]]; then
        echo "   $name is already there"; continue
    fi
    echo "   pushing $name ($((size / 1048576)) MB)"
    adb push "$(lp "$f")" "$OBB_DIR/$name" >/dev/null
    [[ "$(rsh "stat -c %s $OBB_DIR/$name")" == "$size" ]] || { echo "   size mismatch after the push"; exit 1; }
done

# --- 3. the tribemod folder ----------------------------------------------------------------------------------------
echo "== 3/4 tribemod files"
rsh "rm -rf $STAGE" >/dev/null
adb push "$(lp "$START")" "$STAGE" >/dev/null
rsh "mkdir -p $TMOD && cp -r $STAGE/. $TMOD/ && rm -rf $STAGE" >/dev/null
rsh "cd $TMOD && touch $FLAGS" >/dev/null
rsh "chmod 777 /sdcard/Android/data/$PKG/files $TMOD; find $TMOD -type d -exec chmod 777 {} +; find $TMOD -type f -exec chmod 666 {} +" >/dev/null
for fl in $FLAGS active_skin.txt envs.txt; do
    [[ -n "$(rsh "ls $TMOD/$fl")" ]] || { echo "   $fl did not arrive in $TMOD"; exit 1; }
done
echo "   $(rsh "ls $TMOD/skins | wc -l") characters, $(rsh "ls $TMOD/songs | grep -c '\.txt$'") light scripts, switches on: $FLAGS"

# --- 4. storage permissions ----------------------------------------------------------------------------------------
echo "== 4/4 storage permissions"
for p in READ_EXTERNAL_STORAGE WRITE_EXTERNAL_STORAGE READ_MEDIA_VIDEO READ_MEDIA_AUDIO READ_MEDIA_IMAGES; do
    rsh "pm grant $PKG android.permission.$p" >/dev/null || true
done
for op in READ_EXTERNAL_STORAGE LEGACY_STORAGE READ_MEDIA_VIDEO; do rsh "appops set $PKG $op allow" >/dev/null || true; done

# --- optional: videos for the visuals wall --------------------------------------------------------------------------
for m in ${MEDIA[@]+"${MEDIA[@]}"}; do
    dest="/sdcard/Movies/$(basename "${m%/}")"
    echo "== videos: $m -> $dest"
    rsh "mkdir -p '$dest'" >/dev/null
    for v in "${m%/}"/*; do
        [[ -f "$v" ]] || continue
        adb push "$(lp "$v")" "$dest/$(basename "$v")" >/dev/null && echo "   $(basename "$v")"
    done
done

cat <<'EOF'

Done. In the headset:
  1. Launch Tribe. Meta shows a dialog about an unofficial app: tap OPEN APP. If it only offers Restore and
     Close, tap Close and launch Tribe again. Never tap Restore. Tribe may restart itself once; that's normal.
  2. Put the headset on (the mod waits for VR focus), then stand still with straight arms for a second.
     That one pose calibrates every character to you.
  3. Avatar menu: a box per character. Environment menu: Dino Stage, Dino Classic, Reactor, Graveyard Shift.
Watch the mod's log with:  adb logcat -s TRIBEMOD
Go Live and lounges need a valid Meta login, which a re-signed build can't get by itself: see the guide.
EOF
