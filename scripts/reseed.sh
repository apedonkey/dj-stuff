#!/usr/bin/env bash
# reseed.sh -- restore the modded Tribe build to a fully-working state after the Meta token expires.
#
# WHEN TO RUN IT: streaming / lounges stop working again and ~1/sec "Unofficial Application" auth errors return in
# logcat. That means the cached Meta token expired. This re-mints one and puts the mod back on it.
#
# WHY IT WORKS: the re-signed mod can't mint a Meta token itself, but it RIDES one that a genuine login cached on the
# headset. So we (A) briefly install the GENUINE Tribe and log in = mint a fresh token, then (B) swap the mod back and
# restore the avatar data + permissions that a reinstall wipes. The token survives because PART B's final install is the
# mod; we never leave the headset without a freshly-seeded token.
#
# RUN IT YOURSELF in a terminal (it pauses for the two things only you can do in the headset):
#     ./scripts/reseed.sh
# Do NOT expect it to run unattended -- it waits for you to press Enter after each in-headset step.
set -u
cd "$(dirname "$0")/.." || exit 1

ADB=./tools/platform-tools/adb.exe
SERIAL=2G0YC1ZF96072F
PKG=com.TribeXR.TribeXR
D=/sdcard/Android/data/$PKG/files/tribemod
OBB_DST=/sdcard/Android/obb/$PKG/main.2304.$PKG.obb
GENUINE=pulled/base.apk                 # genuine Tribe (CN=Kevin Lowe) -- mints the token
MOD=out/hookA/cam.aligned.apk           # the mod to put back  <-- change if you rebuild to a new filename
OBB=pulled/main.2304.$PKG.obb           # ~1.9GB game data (version 2304)
BK=backup/reseed_20261001               # avatar data: custom.glb, bt_user_calib.txt, params.txt, active_skin.txt
SKINS=backup/tribemod_20261001/tribemod/skins

say(){   echo; echo ">>> $*"; }
pause(){ echo; read -r -p "    $* -- press Enter when done... " _; }
adb(){   "$ADB" -s "$SERIAL" "$@"; }

# --- preflight: make sure every file exists and the headset is connected before we uninstall anything ---
for f in "$GENUINE" "$MOD" "$OBB" "$BK/custom.glb" "$BK/bt_user_calib.txt"; do
  [ -f "$f" ] || { echo "MISSING required file: $f"; exit 1; }
done
adb get-state >/dev/null 2>&1 || { echo "headset not connected over adb -- plug in / check 'adb devices'"; exit 1; }
echo "Headset connected. This will uninstall + reinstall Tribe twice. Ctrl-C now to abort."
pause "Ready?"

# ============ PART A: seed a fresh Meta token with the GENUINE build ============
say "PART A  uninstall mod -> install GENUINE -> restore OBB"
adb uninstall "$PKG"
adb install "$GENUINE"
adb shell "mkdir -p /sdcard/Android/obb/$PKG"
adb push "$OBB" "$OBB_DST"
pause "In the headset: launch Tribe, tap OPEN APP (NEVER Restore), and LOG IN fully (get into a room)"
ERRS=$(adb logcat -d 2>/dev/null | grep -c "Unofficial Application")
echo "    'Unofficial Application' auth errors since boot: $ERRS   (want 0 = token minted OK)"

# ============ PART B: swap the MOD back onto the fresh token ============
say "PART B  uninstall genuine -> install MOD -> restore OBB + avatar data"
adb uninstall "$PKG"
adb install "$MOD"
adb shell "mkdir -p /sdcard/Android/obb/$PKG $D $D/skins"
adb push "$OBB" "$OBB_DST"
adb push "$BK/custom.glb"        "$D/custom.glb"
adb push "$BK/bt_user_calib.txt" "$D/bt_user_calib.txt"
adb push "$BK/params.txt"        "$D/params.txt"
adb push "$BK/active_skin.txt"   "$D/active_skin.txt"
adb push backup/tribemod_20261001/tribemod/avatar_url.txt "$D/avatar_url.txt"
for g in default mentor skullbuck; do
  [ -f "$SKINS/$g.glb" ] && adb push "$SKINS/$g.glb" "$D/skins/$g.glb"
done
adb shell "touch $D/executor_on $D/auto_load $D/auto_actor $D/body_tracking"

say "fix tribemod permissions (adb-pushed files are shell-owned; the app needs to read them)"
adb shell "chmod 666 $D/* 2>/dev/null; chmod 777 /sdcard/Android/data/$PKG/files $D $D/skins; chmod 666 $D/skins/* 2>/dev/null"

say "restore storage permission (else 360 videos / media won't appear)"
for p in READ_EXTERNAL_STORAGE WRITE_EXTERNAL_STORAGE READ_MEDIA_VIDEO READ_MEDIA_AUDIO READ_MEDIA_IMAGES; do
  adb shell "pm grant $PKG android.permission.$p" 2>/dev/null
done
for op in READ_EXTERNAL_STORAGE LEGACY_STORAGE READ_MEDIA_VIDEO; do
  adb shell "appops set $PKG $op allow" 2>/dev/null
done

say "DONE. In the headset: launch Tribe (OPEN APP), check your avatar + 360 videos, then Go Live."
echo "    Avatar loads + 360 videos appear + stream reaches Twitch = re-seed succeeded."
echo "    (Reminder: never 'adb uninstall' the mod outside this script; use 'adb install -r' for plain updates.)"
