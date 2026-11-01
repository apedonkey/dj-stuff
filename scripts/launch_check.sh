#!/usr/bin/env bash
# launch_check.sh -- does the modded Tribe load everything on every launch? (claudedocs/mod_2311_plan.md 7.1)
#
#   bash scripts/launch_check.sh [N]          N cold starts (default 10): force-stop Tribe, start it, wait up to 120 s
#                                             for "[READY] all=1" (tribemod/ready.txt, then logcat), record PASS/FAIL with
#                                             the line and the parts that were missing; stop at a crash (its lines saved)
#   bash scripts/launch_check.sh --preflight  the one-minute check before a live set: USB, Tribe up and READY, then the
#                                             Meta login (auth errors since the launch, and again while you press Go Live)
#   add --dry-run to either: print the adb commands, run none of them
#
# It starts and stops Tribe and reads logs and tribemod/ready.txt. It never installs, pushes, deletes or taps
# anything. If Meta's "unofficial app" dialog (with RESTORE) stays up, it stops and tells you: tap OPEN APP yourself,
# never RESTORE (that reinstalls the store version and wipes the mod). Results: backup/launch_checks/<date_time>/.
# Exit: 0 all PASS / GO, 1 a FAIL / NOT READY, 2 the headset (USB, asleep, Tribe not installed), 3 the dialog, 4 a crash.
set -u
export MSYS_NO_PATHCONV=1                   # Git Bash would rewrite /sdcard/... paths
cd "$(dirname "$0")/.." || exit 2

ADB=${ADB:-./tools/platform-tools/adb.exe}
SERIAL=${SERIAL:-2G0YC1ZF96072F}
PKG=com.TribeXR.TribeXR
ACTIVITY=$PKG/com.epicgames.unreal.GameActivity
D=/sdcard/Android/data/$PKG/files/tribemod
READY_WAIT=${READY_WAIT:-120}               # s per launch
STOP_WAIT=${STOP_WAIT:-10}                  # s for a force-stop to take
DIALOG_WAIT=${DIALOG_WAIT:-12}              # s the unofficial-app dialog may stay up before the check stops
START_WAIT=${START_WAIT:-20}                # s for Tribe's process to appear after the start
POLL=${POLL:-2}                             # s between reads
OUT=${OUT:-backup/launch_checks}
AUTH_ERR='Unofficial Application|Invalid OAuth|does not have permission|authenticate_application'

N=10; MODE=cold; DRY=0
for a in "$@"; do case $a in
  --preflight) MODE=preflight;; --dry-run) DRY=1;;
  ''|*[!0-9]*) echo "usage: $0 [N] [--preflight] [--dry-run]"; exit 2;;
  *) N=$a;; esac; done

RUN=$OUT/$(date +%Y%m%d_%H%M%S)_$MODE; mkdir -p "$RUN"
exec > >(tee -a "$RUN/check.log") 2>&1
exec 3>&1                                   # the dry run's command list (a call's own >/dev/null can't hide it)
say(){ echo; echo "=== $*"; }
adb(){ if [ $DRY = 1 ]; then echo "  [dry-run] adb -s $SERIAL $*" >&3; return 0; fi; "$ADB" -s "$SERIAL" "$@" < /dev/null; }
ash(){ adb shell "$@" 2>/dev/null | tr -d '\r'; }
# the [READY] line's fields: status (all=1 / all=0 / FAIL), pid, missing=...
rstatus(){ sed -nE 's/.*\[READY\] ([^ ]+) .*/\1/p' <<<"$1" | head -1; }
rpid(){ sed -nE 's/.* pid=([0-9]+) .*/\1/p' <<<"$1" | head -1; }
rmiss(){ sed -nE 's/.* missing=(.*)$/\1/p' <<<"$1" | head -1; }
dialog_up(){   # Meta's unofficial-app dialog (the one with RESTORE) on screen?
  ash "dumpsys activity activities" | grep -q UnOfficialAppDialogActivity && return 0
  ash "uiautomator dump /dev/tty" | grep -qi 'text="restore' && return 0
  return 1; }
tribe_pid(){ ash "pidof $PKG" | awk '{print $1}'; }
devtime(){ ash "date +'%m-%d %H:%M:%S.000'"; }

# ---- the headset: on USB, awake, Tribe installed (which build)
headset_ok(){
  if [ $DRY = 0 ] && ! "$ADB" devices 2>/dev/null | tr -d '\r' | grep -q "^$SERIAL[[:space:]]*device"; then
    echo "!!! The headset is not on USB (or not authorized): plug it in, then run this again."; return 1; fi
  local w; w=$(ash "dumpsys power" | sed -nE 's/.*mWakefulness=([A-Za-z]+).*/\1/p' | head -1)
  if [ $DRY = 0 ] && [ "$w" != Awake ]; then echo "!!! The headset is asleep ($w): put it on (Tribe only runs while it is awake)."; return 1; fi
  local p; p=$(ash "pm path $PKG" | sed -n 's/^package://p' | grep base.apk | head -1)
  if [ $DRY = 0 ] && [ -z "$p" ]; then echo "!!! Tribe is not installed."; return 1; fi
  APKMD5=$(ash "md5sum $p" | awk '{print $1}'); BUILD=$(build_name "$APKMD5")
  echo "    headset on USB, awake; Tribe installed: ${APKMD5:-?} ($BUILD)"; return 0; }
build_name(){  # the known builds (backup/mod2311_build/builds.txt: "md5  name" lines)
  local n; n=$(grep -i "^$1 " backup/mod2311_build/builds.txt 2>/dev/null | head -1 | cut -d' ' -f3-)
  echo "${n:-not a known build}"; }

# ---- one launch: start Tribe (it must not be running), watch for the dialog, wait for [READY] with the new pid
# sets RES (PASS / FAIL / CRASH / DIALOG / NOSTART), LINE, PID, T0
launch_once(){
  local n=$1 i=0 line="" st
  T0=$(devtime); adb shell am start -n "$ACTIVITY" >/dev/null 2>&1; PID=""; LINE=""
  if [ $DRY = 1 ]; then RES=DRY; return; fi
  local t=0 seenPid=0 dlg=0
  while [ "$t" -lt "$READY_WAIT" ]; do
    sleep "$POLL"; t=$((t+POLL))
    if [ "$t" -le "$DIALOG_WAIT" ] && dialog_up; then dlg=$t; [ "$t" -ge "$DIALOG_WAIT" ] && { RES=DIALOG; return; }; continue; fi
    local p; p=$(tribe_pid)
    if [ -n "$p" ]; then PID=$p; seenPid=1
    elif [ $seenPid = 1 ]; then RES=CRASH; return
    elif [ "$t" -ge "$START_WAIT" ]; then RES=NOSTART; return; fi
    line=$(ash "cat $D/ready.txt" | head -1)
    if [ -n "$line" ] && [ "$(rpid "$line")" = "$PID" ]; then LINE=$line; st=$(rstatus "$line")
      [ "$st" = all=1 ] && { RES=PASS; return; }
      [ "$st" = FAIL ] && { RES=FAIL; return; }; fi
  done
  [ $dlg -gt 0 ] && [ -z "$PID" ] && { RES=DIALOG; return; }
  # no all=1 in time: the newest [READY] line of this pid from logcat, if ready.txt had none
  [ -z "$LINE" ] && [ -n "$PID" ] && LINE=$(ash "logcat -d -v threadtime -T '$T0' -s TRIBEMOD:I" | grep " $PID " | grep '\[READY\]' | tail -1 | sed 's/.*\(\[READY\]\)/\1/')
  RES=FAIL; }
save_logs(){  # the mod's own lines since the launch (no tokens: the mod never logs them) + the crash buffer on a crash
  local n=$1
  ash "logcat -d -v threadtime -T '$T0' -s TRIBEMOD:I A64_HOOK:I" > "$RUN/launch_$n.log"
  if [ "$RES" = CRASH ]; then { echo "# crash buffer (logcat -b crash -d)"; ash "logcat -b crash -d"; echo; echo "# TRIBEMOD since the launch";
      cat "$RUN/launch_$n.log"; } > "$RUN/launch_${n}_crash.txt"; fi; }
stop_tribe(){
  adb shell am force-stop $PKG >/dev/null 2>&1; [ $DRY = 1 ] && return 0
  local t=0; while [ -n "$(tribe_pid)" ]; do sleep 1; t=$((t+1)); [ $t -ge "$STOP_WAIT" ] && return 1; done; return 0; }
dialog_msg(){ echo "!!! Meta's 'unofficial app' dialog is up in the headset. Put the headset on and tap OPEN APP -- never RESTORE"
  echo "    (Restore reinstalls the store version and wipes the mod). Then run this again. Nothing was tapped."; }

# ======================================================================== cold starts
if [ $MODE = cold ]; then
  say "launch check: $N cold starts of Tribe ($(date '+%Y-%m-%d %H:%M:%S'))"
  headset_ok || exit 2
  echo "    results: $RUN"
  pass=0; fail=0; : > "$RUN/summary.txt"
  for n in $(seq 1 "$N"); do
    say "launch $n of $N"
    stop_tribe || echo "    (Tribe did not stop within ${STOP_WAIT} s: launching anyway)"
    launch_once "$n"; save_logs "$n"
    miss=$(rmiss "$LINE"); tt=$(sed -nE 's/.* t=([0-9.]+)s .*/\1/p' <<<"$LINE")
    case $RES in
      PASS) pass=$((pass+1)); echo "    PASS (pid $PID, ready at ${tt:-?} s)";;
      FAIL) fail=$((fail+1)); echo "    FAIL (pid ${PID:-?}): missing ${miss:-? (no [READY] line from this launch)}";;
      CRASH) fail=$((fail+1)); echo "    CRASH: Tribe (pid $PID) died before it was ready; its lines: $RUN/launch_${n}_crash.txt";;
      NOSTART) fail=$((fail+1)); echo "    FAIL: Tribe did not start within ${START_WAIT} s";;
      DIALOG) dialog_msg;;
      DRY) echo "    (dry run: nothing was started)";;
    esac
    printf '%s\t%s\t%s\t%s\t%s\n' "$n" "$RES" "${PID:--}" "${tt:--}" "${LINE:-(no [READY] line)}" >> "$RUN/summary.txt"
    [ "$RES" = DIALOG ] && { echo "    stopped at launch $n"; exit 3; }
    [ "$RES" = CRASH ] && { echo "    stopped at launch $n (a crash: see the file above)"; break; }
  done
  say "result: $pass PASS, $fail FAIL of $(wc -l < "$RUN/summary.txt") launch(es); build ${APKMD5:-?} ($BUILD)"
  awk -F'\t' '{printf "  %2s  %-7s pid %-6s t %-6s %s\n",$1,$2,$3,$4,substr($5,1,160)}' "$RUN/summary.txt"
  common=$(grep -o 'missing=[^ ]*' "$RUN/summary.txt" | sed -E 's/missing=//; s/\(.*//' | sort | uniq -c | sort -rn | head -1)
  [ -n "$common" ] && echo "    most common missing part: $common"
  echo "    launch 1 right after an install can't read tribemod/ at first (the mod starts in pass-through): judge it apart"
  grep -q CRASH "$RUN/summary.txt" && exit 4
  [ $fail = 0 ] && exit 0 || exit 1
fi

# ======================================================================== preflight
say "preflight ($(date '+%Y-%m-%d %H:%M:%S')): the check before a live set"
problems=(); fixes=()
if ! headset_ok; then echo; echo "NOT READY: the headset (USB / awake / installed)"; exit 2; fi
PID=$(tribe_pid); started=0
if [ -z "$PID" ] && [ $DRY = 0 ]; then echo "    Tribe isn't running: starting it"; launch_once 1; started=1
  [ "$RES" = DIALOG ] && { dialog_msg; echo; echo "NOT READY: Meta's dialog is up"; exit 3; }
  [ "$RES" = CRASH ] && { save_logs 1; echo; echo "NOT READY: Tribe crashed while starting ($RUN/launch_1_crash.txt)"; exit 4; }
else T0=""; [ $DRY = 1 ] && launch_once 1
  LINE=$(ash "cat $D/ready.txt" | head -1); t=0      # running already: its own [READY] line (up to READY_WAIT for all=1)
  while [ $DRY = 0 ] && { [ "$(rpid "$LINE")" != "$PID" ] || [ "$(rstatus "$LINE")" = all=0 ]; } && [ "$t" -lt "$READY_WAIT" ]; do
    sleep "$POLL"; t=$((t+POLL)); LINE=$(ash "cat $D/ready.txt" | head -1); done
  [ "$(rpid "$LINE")" = "$PID" ] || LINE=""; fi
echo "    $([ $started = 1 ] && echo started || echo running): pid ${PID:-?}"
echo "    ${LINE:-(no [READY] line from this launch)}"
for part in hook world avatar skin stage stream menus; do
  v=$(sed -nE "s/.* $part=(\"[^\"]*\"(\([^)]*\))?|[^ (]*(\([^)]*\))?).*/\1/p" <<<"$LINE" | head -1); printf '      %-7s %s\n' "$part" "${v:-?}"; done
st=$(rstatus "$LINE")
if [ "$st" != all=1 ] && [ $DRY = 0 ]; then problems+=("parts not loaded: $(rmiss "$LINE")"); fixes+=("close Tribe, launch it again (OPEN APP, never Restore), then run this check again"); fi
# the login: auth errors since this launch, then while you press Go Live
if [ -z "${T0:-}" ] && [ -n "${PID:-}" ]; then T0=$(ash "logcat -d -v threadtime --pid=$PID" | head -1 | awk '{print $1" "$2}'); fi
a1=$(ash "logcat -d -v threadtime ${T0:+-T '$T0'}" | grep -cE "$AUTH_ERR")
echo "    login: $a1 auth error(s) in the log since this launch"
T1=$(devtime)
echo; echo ">>> In the headset: press GO LIVE now (you can end the stream right away). Then press Enter here."
[ $DRY = 1 ] || read -r _
a2=$(ash "logcat -d -v threadtime -T '$T1'" | grep -cE "$AUTH_ERR")
echo "    login: $a2 auth error(s) while you pressed Go Live"
if [ $DRY = 0 ] && [ $((a1+a2)) -gt 0 ]; then problems=("the Meta login ($a1 auth errors since the launch, $a2 at Go Live)" "${problems[@]}")
  fixes=("run \"Fix Tribe Login.exe\" on the Desktop now (about 5 minutes, one login in the headset)" "${fixes[@]}"); fi
{ echo "launch: ${LINE:-none}"; echo "auth errors: $a1 since the launch, $a2 at Go Live"; } > "$RUN/preflight.txt"
echo
if [ ${#problems[@]} = 0 ]; then echo "GO"; echo "GO" >> "$RUN/preflight.txt"; exit 0; fi
echo "NOT READY: ${problems[0]}"; echo "    fix: ${fixes[0]}"
for i in $(seq 1 $((${#problems[@]}-1))); do echo "    also: ${problems[$i]} -> ${fixes[$i]}"; done
echo "NOT READY: ${problems[0]}" >> "$RUN/preflight.txt"; exit 1
