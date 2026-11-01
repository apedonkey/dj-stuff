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
export MSYS_NO_PATHCONV=1   # Git Bash would rewrite device paths like /sdcard/... into C:/Program Files/Git/...
cd "$(dirname "$0")/.." || exit 1

ADB=./tools/platform-tools/adb.exe
SERIAL=2G0YC1ZF96072F
PKG=com.TribeXR.TribeXR
D=/sdcard/Android/data/$PKG/files/tribemod
OBB_DST=/sdcard/Android/obb/$PKG/main.2311.$PKG.obb
GENUINE=backup/tribe_2311/apk/base.apk                 # genuine Tribe (CN=Kevin Lowe) -- mints the token
MOD=backup/mod_fix_stream_fallback/combo_fallback_2311.apk           # the mod to put back  <-- change if you rebuild to a new filename (combo20 = combo15 + hook/stream.cpp, the Twitch stream fix: Agora's encoder for the live connection (hardware, 5 Mbit/s), the stream camera every 3rd frame (24 fps) and Tribe's stream size 1280x720, per tribemod/stream.txt; md5 2a538da5, lib e7632a12; installed 2026-10-27 17:13 by the Halloween chat; first stream 17:16-17:23: Twitch Video Stats 1280x720 24 fps 5.5 Mbit/s, hardware encoder held, headset 70-72 fps with dips (2.2x the long frames of 848x480; the user: "felt fine"). combo19 = the 848x480 fallback)
# combo13 (c5f6c308, lib 1f2391dc; combo12 + the .usmap dump: dumper.cpp f00f778c + usmap.cpp b0ffd1de + usmap_writer.h 5d7cdc36, one-shot on tribemod/usmap_now; installed 2026-10-26 22:20, first launch 22:20:44 checked: dump DONE in 0.3 s, Tribe still up, avatar follow running) is the fallback.
# combo12 (46babf9f, lib 4744f53f; combo10 + intro.cpp 9a9aef05/intro_ride.h 828bc46a: Harvest's opt-in descent camera, moving button (buttonactor) and autoshow; installed 2026-10-20 17:29 by the Harvest chat, first launch 17:37 checked: 7 boxes, press 2 -> showtime on its own, no crash) is the fallback.
# combo11 (66edc6cb; combo10 + the descent line only, 2026-10-20 11:30) never had a checked launch.
# out/hookA/combo10.aligned.apk (combo10 = combo9 + intro.cpp/intro_ride.h: door shut= (Graveyard's crypt doors close 2 s after you reach the decks) + screen <actor> (the crypt monitor shows the stream camera); md5 c48a2e38, lib e791ccf7, installed 2026-10-19 11:35 by the Halloween chat; switched here at the user's "just do it now" before its first launch was checked. combo9 = 2c747dd9, the fallback)
# The builds before it: out/hookA/combo8.aligned.apk (7d6a9051; dumper.cpp 3476d016 + club.cpp fc5a5dfe: the RED EYE, Harvest Moon and Midtown show rows, 2026-10-17 19:03),
# out/hookA/combo3.aligned.apk (a156adfc; combo2 + head.cpp 6bfa9ead, the head's play clock -- first takeoff after N s of ACTUAL play, 2026-10-11 16:37),
# out/hookA/combo2.aligned.apk (8e72019b; combo1 + head.cpp fbde3601, the head flies every 8-12 min, 2026-10-10 16:43),
# out/hookA/combo1.aligned.apk (8903d10b; song14 + the club + intro + gait + head.cpp, 2026-10-10 08:43),
# out/hookA/club3.aligned.apk (2d2ad182; song13 + the club, 2026-10-09 19:16).
OBB=backup/tribe_2311/obb/$PKG/main.2311.$PKG.obb           # ~2.1GB game data (version 2311)
BK=backup/reseed_20261001               # avatar data: custom.glb, bt_user_calib.txt, params.txt, active_skin.txt
# Custom environments (Dino Stage, Festival): the patch OBB with our paks + the environment menu's files. An uninstall
# wipes both, so PART B puts them back.
PATCH=C:/Users/Chris/TribeUE/paks_current/patch_live.obb   # <-- what is live: scripts/push_obb.sh mirrors every verified push here (2026-10-08: Dino 50 v9 + 53, Halloween 54, club 55)
PATCH_DST=/sdcard/Android/obb/$PKG/patch.2311.$PKG.obb
ENVBK=backup/tribemod_20261006          # envs.txt (menu list), active_env.txt, drone.txt, drone_path.txt, song.txt (the opener), giant.txt
SKINS=skins                             # your characters on the PC (lampwing.glb, skullbuck.glb, ...)
KEEP_SKINS="lampwing skullbuck horseman santa majortom gremlin" # which ones go on the headset (one menu box each)
HEADS=heads                             # detachable heads, paired by name: heads/<skin>.glb flies off skins/<skin>.glb

say(){   echo; echo ">>> $*"; }
pause(){ echo; read -r -p "    $* -- press Enter when done... " _; }
adb(){   "$ADB" -s "$SERIAL" "$@"; }
# A plain `adb push` into Android/data/<pkg> now silently vanishes on this headset (found 2026-10-03; Android/obb and
# /sdcard/Download still work). So files for tribemod/ are staged in /data/local/tmp, copied in with a shell command, and
# made readable for Tribe.
put(){ adb push "$1" /data/local/tmp/tribemod_put.tmp >/dev/null &&        adb shell "cp /data/local/tmp/tribemod_put.tmp '$2' && chmod 666 '$2'; rm -f /data/local/tmp/tribemod_put.tmp" &&        echo "    put $(basename "$1") -> $2"; }

# --- preflight: make sure every file exists and the headset is connected before we uninstall anything ---
for f in "$GENUINE" "$MOD" "$OBB" "$PATCH" "$BK/custom.glb" "$BK/bt_user_calib.txt" "$ENVBK/envs.txt" "$ENVBK/active_env.txt" \
         $(for g in $KEEP_SKINS; do echo "$SKINS/$g.glb"; done); do
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
adb logcat -c                           # count only this login's errors below (older failed attempts stay out)
pause "In the headset: launch Tribe, tap OPEN APP (NEVER Restore), and LOG IN fully (get into a room)"
ERRS=$(adb logcat -d 2>/dev/null | grep -c "Unofficial Application")
echo "    'Unofficial Application' auth errors during this login: $ERRS   (want 0 = token minted OK)"

# ============ PART B: swap the MOD back onto the fresh token ============
say "PART B  uninstall genuine -> install MOD -> restore OBB + avatar data"
adb uninstall "$PKG"
adb install "$MOD"
adb shell "mkdir -p /sdcard/Android/obb/$PKG $D $D/skins"
adb push "$OBB" "$OBB_DST"
put "$BK/custom.glb"        "$D/custom.glb"
put "$BK/bt_user_calib.txt" "$D/bt_user_calib.txt"
put backup/mod_fix_stream_fallback/tribemod/params.txt "$D/params.txt"
put "$BK/active_skin.txt"   "$D/active_skin.txt"
put backup/tribemod_20261001/tribemod/avatar_url.txt "$D/avatar_url.txt"
for g in $KEEP_SKINS; do put "$SKINS/$g.glb" "$D/skins/$g.glb"; done
say "detachable heads (skullbuck's skull, the horseman's pumpkin) + head.txt = auto"
adb shell "mkdir -p $D/heads; chmod 777 $D/heads; echo auto > $D/head.txt; chmod 666 $D/head.txt"
for g in $KEEP_SKINS; do [ -f "$HEADS/$g.glb" ] && put "$HEADS/$g.glb" "$D/heads/$g.glb"; done
say "custom environments: the patch OBB (Dino Stage, Festival) + the environment menu's files"
adb push "$PATCH" "$PATCH_DST"
# + the walking maps (club, Dino, Graveyard, Midtown, RED EYE, Harvest Moon), the stream intros + drone paths
# (Graveyard, Midtown, RED EYE, Harvest Moon), Graveyard's camera view (camview.halloween.txt, 2026-10-18) and the
# club's dimmers (club.txt, 2026-10-10). Whoever changes one of these on the headset copies it into $ENVBK too, or a
# re-seed puts the old one back.
for f in envs.txt active_env.txt drone.txt drone_path.txt song.txt giant.txt club_collide.txt drone_path.club.txt \
         dino_collide.txt halloween_collide.txt intro.halloween.txt drone_path.halloween.txt club.txt \
         camview.halloween.txt christmas_collide.txt intro.christmas.txt drone_path.christmas.txt \
         redeye_collide.txt intro.redeye.txt drone_path.redeye.txt \
         harvest_collide.txt intro.harvest.txt drone_path.harvest.txt \
         stream.txt; do [ -f "$ENVBK/$f" ] && put "$ENVBK/$f" "$D/$f"; done   # stream.txt: the stream encoder (hook/stream.cpp, 2026-10-27)
say "light scripts for every song (TribeUE/Songs/cues, from scripts songs/scan_library.py + make_cues.py)"
SONGS=C:/Users/Chris/TribeUE/Songs/cues
[ -d "$SONGS" ] && adb push "$SONGS" /data/local/tmp/songs_stage >/dev/null &&   adb shell "mkdir -p $D/songs && cp -r /data/local/tmp/songs_stage/. $D/songs/ && rm -f $D/songs/_names.json; chmod 777 $D/songs; find $D/songs -type f -exec chmod 666 {} +; rm -rf /data/local/tmp/songs_stage" &&   echo "    put $(ls "$SONGS" | grep -c txt) light scripts -> $D/songs"
adb shell "touch $D/executor_on $D/auto_load $D/auto_actor $D/body_tracking $D/skin_menu $D/env_menu $D/drone_cam $D/lights.txt"

say "fix tribemod permissions (adb-pushed files are shell-owned; the app needs to read them)"
# files 666, folders 777 (a blanket "chmod 666 $D/*" once stripped the songs folder's x bit: no light script could open)
adb shell "find $D -maxdepth 1 -type f -exec chmod 666 {} + ; chmod 777 /sdcard/Android/data/$PKG/files $D $D/skins $D/heads $D/songs 2>/dev/null; chmod 666 $D/skins/* $D/heads/* 2>/dev/null; find $D/songs -type f -exec chmod 666 {} + 2>/dev/null"

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
