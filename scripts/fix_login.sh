#!/usr/bin/env bash
# fix_login.sh -- the one-step fix for "Go Live (or the lounges) stopped working" on the modded Tribe.
#
# Why it breaks: the mod can't renew Meta's login token, so when the token expires Go Live fails (the headset's log
# fills with "Invalid OAuth 2.0 Access Token" or "Unofficial Application" errors). The fix is the re-seed: the store
# version of Tribe logs in once (a fresh token), then the mod goes back on top of it.
#
# HOW TO RUN: double-click "Fix Tribe Login.exe" on the Desktop (or: bash scripts/fix_login.sh), headset on USB.
# You do one thing: log in, in the headset, when it asks.
#   1. SNAPSHOT  saves the installed mod APK, every tribemod file and the stages file (on the PC and on the headset),
#                so it puts back exactly what you had, not an old backup. Nothing on the headset changes in this step.
#   2. PART A    uninstalls the mod, installs the store version + the game data.
#   3. LOGIN     you log in, in the headset; the log must show a fresh token (and no auth errors) before it goes on.
#   4. PART B    uninstalls the store version; your mod goes back + game data, stages, tribemod files, permissions.
#   5. VERIFY    everything matches the snapshot (md5). Then: launch Tribe, OPEN APP (never "Restore"), Go Live.
# If it stops (USB unplugged, the headset asleep, ...), run it again: it carries on from where it stopped.
# An unfinished fix whose mod was replaced since by another build is out of date: it's retired and a fresh fix starts.
# Runs (log, snapshot) are kept in backup/reseed_runs/ (the last 3).
#   bash scripts/fix_login.sh --dry-run    snapshot + checks only: Tribe isn't touched (the headset only gets the
#                                          snapshot's copy of tribemod, in /data/local/tmp)
# For Claude (no keyboard): FIX_SIGNALS=1 makes each "press Enter" wait for a file <run>/go.<n> instead.
# Same steps as scripts/reseed.sh (the by-hand version), plus the snapshot, the checks and the carry-on.
set -u
export MSYS_NO_PATHCONV=1                   # Git Bash would rewrite /sdcard/... into C:/Program Files/Git/...
cd "$(dirname "$0")/.." || exit 1

ADB=${ADB:-./tools/platform-tools/adb.exe}
SERIAL=${SERIAL:-2G0YC1ZF96072F}
PKG=com.TribeXR.TribeXR
D=/sdcard/Android/data/$PKG/files/tribemod
OBBDIR=/sdcard/Android/obb/$PKG
MAIN_DST=$OBBDIR/main.2311.$PKG.obb
PATCH_DST=$OBBDIR/patch.2311.$PKG.obb
GENUINE=${GENUINE:-backup/tribe_2311/apk/base.apk}                        # the store version (CN=Kevin Lowe): its login mints the token
MAIN=${MAIN:-backup/tribe_2311/obb/$PKG/main.2311.$PKG.obb}                    # the 2.1 GB game data (version 2311)
MIRROR=${MIRROR:-C:/Users/Chris/TribeUE/paks_current/patch_live.obb}   # push_obb.sh's copy of the live stages file
SNAP=/data/local/tmp/reseed_snap                           # the headset's own copy of tribemod (an uninstall keeps it)
RUNS=${RUNS:-backup/reseed_runs}
WAIT_MAX=${WAIT_MAX:-300}                                  # x 2 s: how long to wait for the headset on USB
AUTH_ERR='Unofficial Application|Invalid OAuth|does not have permission'
VOLATILE='^[0-9a-f]{32}  \./load_result\.txt$'     # md5list lines of files the mod rewrites at every launch: never compared
DRY=0; [ "${1:-}" = "--dry-run" ] && DRY=1
SIG=${FIX_SIGNALS:-0}

mkdir -p "$RUNS"
exec > >(tee -a "$RUNS/fix_login.log") 2>&1
echo; echo "##### fix_login.sh $(date '+%Y-%m-%d %H:%M:%S')$([ $DRY = 1 ] && echo ' (dry run)')"

say(){  echo; echo "=== $*"; }
note(){ echo "    $*"; }
adb(){  "$ADB" -s "$SERIAL" "$@" < /dev/null; }          # never let adb eat the Enter key meant for a prompt
ash(){  adb shell "$@" 2>/dev/null | tr -d '\r'; }        # a headset shell command's output
md5list(){ tr -d '\r' | sed 's/^\([0-9a-f]\{32\}\) [ *]/\1  /' | LC_ALL=C sort -k2; }   # md5sum lines, one format
size_on(){ ash "stat -c %s '$1' 2>/dev/null"; }
setstate(){ echo "$1" > "$RUN/state"; PHASE=$1; }
die(){
  echo; echo "!!! STOPPED: $*"
  if [ -n "${RUN:-}" ] && [ $DRY = 0 ] && [ -f "$RUNS/current" ]; then
    echo "    Nothing is lost: your mod and its files are saved in $RUN (and on the headset in $SNAP)."
    echo "    Fix that (plug the headset in, wake it up), then run this again: it carries on from here."
  fi
  exit 1; }
need_device(){ local n=0
  until [ "$(adb get-state 2>/dev/null | tr -d '\r')" = device ]; do
    [ $n = 0 ] && note "waiting for the headset on USB: plug it in, put it on to wake it, allow USB debugging if it asks..."
    n=$((n+1)); [ $n -gt "$WAIT_MAX" ] && die "the headset isn't connected over USB"
    sleep 2
  done; }
PN=0
pause(){ PN=$((PN+1)); echo
  if [ "$SIG" = 1 ]; then note ">>> $*"; note "(waiting for $RUN/go.$PN)"; until [ -f "$RUN/go.$PN" ]; do sleep 2; done
  else printf '    >>> %s -- then press Enter... ' "$*"; read -r _ || die "no keyboard (run it in a terminal window)"; fi; }
ask(){  # a yes/no question: Enter = yes, n = no (FIX_SIGNALS: yes)
  [ "$SIG" = 1 ] && return 0
  local a; printf '    >>> %s [Enter = yes, n = no] ' "$1"; read -r a || die "no keyboard (run it in a terminal window)"
  case "$a" in n|N|no|No|NO) return 1;; esac; return 0; }
try3(){ local i; for i in 1 2 3; do need_device; "$@" && return 0; note "that didn't work; trying again ($i of 3)..."; sleep 3; done
  die "failed 3 times: $*"; }

get_installed(){  # INST = md5 of the installed Tribe APK, or "none"; INST_PATH = where it is
  need_device
  local out p
  out=$(ash "pm path $PKG; echo RC=\$?")
  echo "$out" | grep -q '^RC=' || die "lost the headset while checking what's installed"
  p=$(echo "$out" | grep '^package:' | sed 's/^package://')
  if [ -z "$p" ]; then INST=none; INST_PATH=; return; fi
  [ "$(echo "$p" | wc -l)" -eq 1 ] || die "unexpected: the installed Tribe has more than one APK ($p)"
  INST=$(ash "md5sum '$p'" | cut -c1-32); INST_PATH=$p
  [ ${#INST} = 32 ] || die "couldn't read the installed APK"; }
install_apk(){  # $1 = APK, $2 = its md5: install it (onto an empty slot), then check that it is what's installed
  get_installed; [ "$INST" = "$2" ] && return 0; [ "$INST" = none ] || return 1
  local out; out=$(adb install "$1" 2>&1 | tr -d '\r'); echo "$out" | tail -2 | sed 's/^/      /'
  get_installed; [ "$INST" = "$2" ]; }
uninstall(){ get_installed; [ "$INST" = none ] && return 0
  local out; out=$(adb uninstall $PKG 2>&1 | tr -d '\r'); note "uninstall: $out"
  get_installed; [ "$INST" = none ]; }
push_main(){
  local want; want=$(stat -c %s "$MAIN")
  [ "$(size_on "$MAIN_DST")" = "$want" ] && { note "game data: already there"; return 0; }
  note "game data: copying 1.9 GB (about a minute)..."
  ash "mkdir -p $OBBDIR" >/dev/null
  adb push "$MAIN" "$MAIN_DST" 2>&1 | tr -d '\r' | tail -1 | sed 's/^/      /'
  [ "$(size_on "$MAIN_DST")" = "$want" ]; }
push_patch(){
  local want src; want=$(cat "$RUN/patch.md5"); [ "$want" = none ] && return 0
  src=$(cat "$RUN/patch.src")
  [ "$(ash "md5sum '$PATCH_DST' 2>/dev/null" | cut -c1-32)" = "$want" ] && { note "stages file: already there"; return 0; }
  note "stages file: copying..."
  ash "mkdir -p $OBBDIR" >/dev/null
  adb push "$src" "$PATCH_DST" 2>&1 | tr -d '\r' | tail -1 | sed 's/^/      /'
  [ "$(ash "md5sum '$PATCH_DST' 2>/dev/null" | cut -c1-32)" = "$want" ]; }
restore_files(){
  local have
  have=$(adb shell "cd $SNAP/tribemod 2>/dev/null && find . -type f -exec md5sum {} +" 2>/dev/null | md5list)
  if [ "$have" != "$(cat "$RUN/manifest.txt")" ]; then
    note "the headset's own copy is gone or changed: sending the PC copy"
    ash "rm -rf $SNAP/tribemod; mkdir -p $SNAP" >/dev/null
    adb push "$RUN/tribemod" "$SNAP/" >/dev/null 2>&1 || return 1
  fi
  ash "mkdir -p $D && cp -r $SNAP/tribemod/. $D/ && echo CP_OK" | grep -q CP_OK || return 1
  # files 666, folders 777: Tribe has to read files that adb put there (reseed.sh's rule)
  ash "chmod 777 /sdcard/Android/data/$PKG/files; find $D -type d -exec chmod 777 {} + ; find $D -type f -exec chmod 666 {} +" >/dev/null
  note "tribemod: $(wc -l < "$RUN/manifest.txt") files back"; }
grants(){  # an install resets these: without them the 360 videos and media don't show
  local p
  for p in READ_EXTERNAL_STORAGE WRITE_EXTERNAL_STORAGE READ_MEDIA_VIDEO READ_MEDIA_AUDIO READ_MEDIA_IMAGES; do
    ash "pm grant $PKG android.permission.$p" >/dev/null; done
  for p in READ_EXTERNAL_STORAGE LEGACY_STORAGE READ_MEDIA_VIDEO; do ash "appops set $PKG $p allow" >/dev/null; done
  note "storage permissions: granted"; }

snapshot(){
  say "STEP 1 of 5: saving what's on the headset (nothing on it changes in this step)"
  local obbs; obbs=$(ash "ls $OBBDIR 2>/dev/null")
  if echo "$obbs" | grep -q '^main\.' && ! echo "$obbs" | grep -qx "main.2311.$PKG.obb"; then
    die "the headset has another Tribe version's game data ($(echo "$obbs" | grep '^main\.')): this tool needs updating for it"; fi
  # the mod APK
  adb pull "$INST_PATH" "$RUN/mod.apk" >/dev/null 2>&1 || die "couldn't copy the installed mod APK"
  [ "$(md5sum "$RUN/mod.apk" | cut -c1-32)" = "$INST" ] || die "the copied mod APK doesn't match the headset's"
  echo "$INST" > "$RUN/mod.md5"
  local f name="" sz; sz=$(stat -c %s "$RUN/mod.apk")
  for f in out/hookA/*.aligned.apk; do [ -f "$f" ] && [ "$(stat -c %s "$f")" = "$sz" ] && \
    [ "$(md5sum "$f" | cut -c1-32)" = "$INST" ] && name=" (= $f)"; done
  note "mod APK: ${INST:0:8}$name"
  # tribemod: the headset's own copy (what goes back) + a PC copy (in case the headset's goes missing)
  ash "rm -rf $SNAP; mkdir -p $SNAP; cp -r $D $SNAP/ 2>$SNAP/not_copied.txt; echo SNAP_OK" | grep -q SNAP_OK || \
    die "couldn't copy the tribemod folder on the headset"
  adb shell "cd $SNAP/tribemod && find . -type f -exec md5sum {} +" 2>/dev/null | md5list > "$RUN/manifest.txt"
  local n; n=$(wc -l < "$RUN/manifest.txt")
  [ "$n" -ge 5 ] || die "the tribemod copy looks empty ($n files): not going on"
  adb pull "$SNAP/tribemod" "$RUN/" >/dev/null 2>&1 || die "couldn't copy the tribemod folder to the PC"
  (cd "$RUN/tribemod" && find . -type f -exec md5sum {} +) | md5list | cmp -s - "$RUN/manifest.txt" || \
    die "the PC copy of tribemod doesn't match the headset's"
  note "tribemod: $n files saved"
  local skipped; skipped=$(ash "cat $SNAP/not_copied.txt")
  [ -n "$skipped" ] && note "not saved (Tribe's own files, it writes them again): $(echo "$skipped" | sed 's#.*/##; s#:.*##' | tr '\n' ' ')"
  # the stages file (patch OBB)
  local dp mm; dp=$(ash "md5sum '$PATCH_DST' 2>/dev/null" | cut -c1-32)
  if [ ${#dp} != 32 ]; then echo none > "$RUN/patch.md5"; note "stages file: none on the headset"
  else
    echo "$dp" > "$RUN/patch.md5"; mm=$(md5sum "$MIRROR" 2>/dev/null | cut -c1-32)
    if [ "$mm" = "$dp" ]; then echo "$MIRROR" > "$RUN/patch.src"; note "stages file: ${dp:0:8} (the same as the PC's copy)"
    else
      note "stages file: ${dp:0:8} isn't the PC's copy (${mm:0:8}): saving the headset's (about 470 MB)..."
      adb pull "$PATCH_DST" "$RUN/patch.obb" >/dev/null 2>&1 || die "couldn't copy the stages file"
      [ "$(md5sum "$RUN/patch.obb" | cut -c1-32)" = "$dp" ] || die "the copied stages file doesn't match"
      echo "$RUN/patch.obb" > "$RUN/patch.src"
    fi
  fi
  [ "$(size_on "$MAIN_DST")" = "$(stat -c %s "$MAIN")" ] && note "game data: the same size as the PC's copy" || \
    note "game data: missing or a different size on the headset; the PC's copy goes on"; }

part_a(){
  say "STEP 2 of 5: swapping in the store version of Tribe for the login (Tribe closes)"
  need_device
  { [ -s "$RUN/mod.apk" ] && [ "$(md5sum "$RUN/mod.apk" | cut -c1-32)" = "$(cat "$RUN/mod.md5")" ]; } || \
    die "the saved mod APK is missing or damaged: not touching the headset"
  get_installed
  if [ "$INST" != "$GEN_MD5" ]; then
    [ "$INST" != none ] && { note "uninstalling the mod..."; try3 uninstall; }
    note "installing the store version..."; try3 install_apk "$GENUINE" "$GEN_MD5"
  fi
  try3 push_main
  need_device; adb logcat -c                    # the login check counts only what comes after this
  setstate a; }

login_check(){
  say "STEP 3 of 5: log in once with the store version -- in the headset"
  note "1. Put the headset on and launch Tribe (it's the store version for a few minutes; that's expected)."
  note "2. Log in fully and wait until you're in a room, not the loading screen."
  local run bad tok L i
  while :; do
    pause "When you're in a room"
    need_device
    for i in $(seq 1 30); do                     # the token grant can trail the room by a few seconds
      run=$(ash "pidof $PKG"); L=$(adb logcat -d 2>/dev/null)
      bad=$(grep -cE "$AUTH_ERR" <<< "$L"); tok=$(grep -c 'Action succeeded: OBTAIN_TOKEN' <<< "$L")
      { [ -z "$run" ] || [ "$bad" != 0 ] || [ "$tok" -gt 0 ]; } && break
      sleep 2
    done
    note "Tribe running: $([ -n "$run" ] && echo yes || echo no) | login errors: $bad | token grants: $tok"
    if [ -n "$run" ] && [ "$bad" = 0 ] && [ "$tok" -gt 0 ]; then note "login OK: a fresh token"; break; fi
    if [ "$bad" != 0 ]; then
      adb logcat -c
      note "The login is failing. In the headset: check you're signed in to your Meta account, quit Tribe, launch it"
      note "again and log in."
      [ "$SIG" = 1 ] && die "the store version's login hit $bad auth errors (log cleared): run again once logged in"
    elif [ -z "$run" ]; then
      note "Tribe isn't running on the headset yet."
      [ "$SIG" = 1 ] && die "the store version isn't running yet: run again once you're in a room"
    else
      note "No login errors, but no token in the log yet."
      [ "$SIG" = 1 ] && die "no token in the log yet: run again once you're in a room"
      ask "Are you in a room in Tribe right now? (n = check again)" && break
    fi
  done
  setstate login; }

part_b(){
  say "STEP 4 of 5: putting your mod back on the fresh login (a few minutes; Tribe closes)"
  need_device
  local mod; mod=$(cat "$RUN/mod.md5")
  get_installed
  if [ "$INST" != "$mod" ]; then
    if [ "$INST" = "$GEN_MD5" ]; then note "uninstalling the store version..."; try3 uninstall
    elif [ "$INST" != none ]; then die "an unexpected Tribe build is installed (${INST:0:8}): not touching it"; fi
    note "installing your mod..."; try3 install_apk "$RUN/mod.apk" "$mod"
  fi
  try3 push_main
  try3 push_patch
  try3 restore_files
  grants
  setstate b; }

verify_all(){
  say "STEP 5 of 5: checking that everything came back"
  need_device
  local bad=0 want
  get_installed
  if [ "$INST" = "$(cat "$RUN/mod.md5")" ]; then note "mod: OK"; else note "mod: WRONG (${INST:0:8})"; bad=1; fi
  if [ "$(size_on "$MAIN_DST")" = "$(stat -c %s "$MAIN")" ]; then note "game data: OK"; else note "game data: WRONG"; bad=1; fi
  want=$(cat "$RUN/patch.md5")
  if [ "$want" != none ]; then
    if [ "$(ash "md5sum '$PATCH_DST'" | cut -c1-32)" = "$want" ]; then note "stages file: OK"; else note "stages file: WRONG"; bad=1; fi; fi
  adb shell "cd $D && find . -type f -exec md5sum {} +" 2>/dev/null | md5list > "$RUN/after.txt"
  local skip=""; grep -qE "$VOLATILE" "$RUN/manifest.txt" && skip=" (load_result.txt not compared: the mod rewrites it at launch)"
  if cmp -s <(grep -vE "$VOLATILE" "$RUN/manifest.txt") <(grep -vE "$VOLATILE" "$RUN/after.txt"); then
    note "tribemod: all $(grep -cvE "$VOLATILE" "$RUN/manifest.txt") files match$skip"
  else note "tribemod: differences:"
    diff <(grep -vE "$VOLATILE" "$RUN/manifest.txt") <(grep -vE "$VOLATILE" "$RUN/after.txt") | head -20 | sed 's/^/      /'; bad=1; fi
  if ash "dumpsys package $PKG" | grep -q 'READ_MEDIA_VIDEO: granted=true'; then note "storage permission: OK"
  else note "storage permission: missing"; bad=1; fi
  if [ $bad = 1 ]; then setstate login; die "something didn't come back right (above): running this again redoes step 4"; fi
  setstate done; }

finish(){
  adb logcat -c
  say "DONE. Your mod is back, on a fresh login. In the headset:"
  note "1. Launch Tribe."
  note "2. Meta warns it's an unofficial app: tap OPEN APP.  NEVER tap \"Restore\" (that puts the store version back)."
  note "3. Go Live."
  [ "$SIG" = 1 ] && return 0
  echo; printf '    >>> Press Enter once you are in a room and I will check the login (or just close this window). '
  read -r _ || return 0
  need_device
  local bad; bad=$(adb logcat -d 2>/dev/null | grep -cE "$AUTH_ERR")
  if [ -z "$(ash "pidof $PKG")" ]; then note "Tribe isn't running yet: launch it and try Go Live."
  elif [ "$bad" = 0 ]; then note "Login OK: no auth errors. Go Live should work."
  else note "The mod is still getting login errors ($bad). Run this again."; fi; }

prune(){  # keep the 3 newest runs (finished or dry); never an unfinished one
  local d
  ls -d "$RUNS"/2*/ 2>/dev/null | sort | head -n -3 | while read -r d; do d=${d%/}
    [ "$d" = "${RUN:-}" ] && continue
    case "$(cat "$d/state" 2>/dev/null)" in done|dry|stale) rm -rf "$d";; esac; done; }

# ---------------------------------------------------------------------------------------------------------------- main
for f in "$GENUINE" "$MAIN"; do [ -f "$f" ] || die "missing on the PC: $f"; done
GEN_MD5=$(md5sum "$GENUINE" | cut -c1-32)
RUN=""; PHASE=none
if [ -f "$RUNS/current" ]; then RUN=$(cat "$RUNS/current"); PHASE=$(cat "$RUN/state" 2>/dev/null || echo none); fi
if [ "$PHASE" = done ] || [ "$PHASE" = none ]; then RUN=""; PHASE=none; rm -f "$RUNS/current"; fi
need_device
get_installed

# An unfinished fix whose mod was replaced since (another mod build is installed: not that fix's mod, not the store version)
# is out of date: carrying it on would only stop at "an unexpected Tribe build". Retire it; a fresh fix starts below.
if [ "$PHASE" != none ] && [ "$INST" != none ] && [ "$INST" != "$GEN_MD5" ] && [ "$INST" != "$(cat "$RUN/mod.md5" 2>/dev/null)" ]; then
  [ $DRY = 1 ] && { say "The unfinished fix in $RUN is out of date: another mod build (${INST:0:8}) is installed now. Dry run: nothing done (a real run starts a fresh fix)."; exit 0; }
  say "The unfinished fix in $RUN is out of date: another mod build (${INST:0:8}) is installed now. Starting a fresh fix."
  echo stale > "$RUN/state"; RUN=""; PHASE=none; rm -f "$RUNS/current"
fi

if [ "$PHASE" != none ]; then
  [ $DRY = 1 ] && { say "A fix is half-way ($RUN, at: $PHASE). Dry run: nothing done."; exit 0; }
  say "Carrying on with the fix started in $RUN (it had got to: $PHASE)"
else
  case "$INST" in
    none) die "Tribe isn't installed on the headset, and there's no unfinished fix to carry on with. Install the mod (adb install out/hookA/<build>.aligned.apk) or use scripts/reseed.sh by hand.";;
    "$GEN_MD5") die "The store version of Tribe is installed (not the mod), and there's no unfinished fix to carry on with. Use scripts/reseed.sh by hand.";;
  esac
  if [ $DRY = 0 ]; then
    say "Fix the Tribe login (the re-seed)"
    run=$(ash "pidof $PKG"); bad=$(adb logcat -d 2>/dev/null | grep -cE "$AUTH_ERR")
    note "Tribe running: $([ -n "$run" ] && echo yes || echo no) | login errors in the headset's log: $bad"
    if [ -n "$run" ] && [ "$bad" = 0 ]; then
      note "Tribe is running with no login errors, so the login looks fine right now."
      ask "Fix it anyway?" || { note "OK: nothing done."; exit 0; }
    elif [ "$bad" != 0 ]; then note "That's the expired login. This fixes it."
    else note "(Tribe isn't running, so I can't see whether the login expired.)"; fi
    note "This takes about 5 minutes. Tribe closes, and you log in once in the headset when it asks."
    ask "Start?" || { note "OK: nothing done."; exit 0; }
  fi
  RUN=$RUNS/$(date +%Y%m%d_%H%M%S); mkdir -p "$RUN"
  snapshot
  if [ $DRY = 1 ]; then echo dry > "$RUN/state"; prune; say "DRY RUN finished: saved in $RUN. Tribe wasn't touched."; exit 0; fi
  echo "$RUN" > "$RUNS/current"; setstate snap
fi
rm -f "$RUN"/go.*
[ "$PHASE" = snap ]  && part_a
[ "$PHASE" = a ]     && login_check
[ "$PHASE" = login ] && part_b
[ "$PHASE" = b ]     && verify_all
prune
finish
