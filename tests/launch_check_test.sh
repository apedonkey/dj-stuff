#!/usr/bin/env bash
# launch_check_test.sh -- runs scripts/launch_check.sh against a fake headset (a mock adb over a temp folder): cold
# starts that pass, a failed part, a crash, Meta's Restore dialog, the headset off USB, a dry run, and the preflight
# (GO, a login failure, a part not loaded, off USB, Tribe not running). No real headset is touched.
#   bash tests/launch_check_test.sh
set -u
REPO=$(cd "$(dirname "$0")/.." && pwd)
T=$(mktemp -d); trap 'rm -rf "$T"' EXIT
PASS=0; FAIL=0
ok(){  if eval "$2"; then PASS=$((PASS+1)); echo "  ok    $1"; else FAIL=$((FAIL+1)); echo "  FAIL  $1   [$2]"; fi; }

# ---- the mock adb. The fake headset is $MOCK: state/pid (Tribe's process), state/outcomes (what the next launches
# do: pass / fail / crash / dialog), tribemod/ready.txt, logcat.txt, crash.txt; every call is logged in calls.txt.
cat > "$T/adb" <<'EOF'
#!/usr/bin/env bash
M=${MOCK:?}; S=$M/state; R=$M/sdcard/Android/data/com.TribeXR.TribeXR/files/tribemod/ready.txt
if [ "${1:-}" = devices ]; then echo "List of devices attached"; [ -f "$M/offline" ] || printf '2G0YC1ZF96072F\tdevice\n'; exit 0; fi
[ "${1:-}" = -s ] && shift 2
echo "$*" >> "$M/calls.txt"
[ -f "$M/offline" ] && { echo "adb.exe: device '2G0YC1ZF96072F' not found" >&2; exit 1; }
[ "${1:-}" = shell ] || { echo "mock adb: only shell is allowed here: $*" >&2; exit 1; }
shift; c="$*"
ready(){ printf '[READY] %s step=C pid=%s t=%s hook=1 world=1 avatar=%s skin=horseman.glb stage=%s stream=1280x720 menus=env7/7,avatar7/7 paks=7/7 gen=0 skips=0%s\n' "$@" > "$R"; }
case $c in
  "dumpsys power") [ -f "$M/asleep" ] && echo "  mWakefulness=Asleep" || echo "  mWakefulness=Awake";;
  "pm path com.TribeXR.TribeXR") echo "package:/data/app/x/base.apk";;
  "md5sum /data/app/x/base.apk") echo "5b1cb617e66687070bc3f5886bb9495f  /data/app/x/base.apk";;
  "pidof com.TribeXR.TribeXR")
    if [ -f "$S/crash_after" ]; then n=$(cat "$S/crash_after"); if [ "$n" -le 0 ]; then rm -f "$S/pid" "$S/crash_after"; else echo $((n-1)) > "$S/crash_after"; fi; fi
    cat "$S/pid" 2>/dev/null;;
  "am force-stop com.TribeXR.TribeXR") rm -f "$S/pid" "$S/dialog" "$S/crash_after";;
  "am start -n com.TribeXR.TribeXR/com.epicgames.unreal.GameActivity")
    o=$(head -1 "$S/outcomes"); sed -i 1d "$S/outcomes"; p=$(( $(cat "$S/nextpid") )); echo $((p+1)) > "$S/nextpid"; echo $p > "$S/pid"
    case $o in
      pass) ready all=1 $p 41.2s 1 '"Graveyard Shift"' "";;
      fail) ready FAIL $p 180.0s 1 'gave-up("Graveyard Shift" failed 4 times)' ' missing=stage(gave-up("Graveyard Shift" failed 4 times))';;
      slow) ready all=0 $p 24.8s 1 'waiting(settle 2/4, try 1)' ' missing=stage(waiting(settle 2/4, try 1))';;
      crash) echo 1 > "$S/crash_after"; printf '10-31 13:57:37.162 24193 24243 F libc    : Fatal signal 11 (SIGSEGV), code 1 (SEGV_MAPERR), fault addr 0x3 in tid 24243 (GameThread)\n' > "$M/crash.txt";;
      dialog) touch "$S/dialog";;
    esac;;
  "cat /sdcard/Android/data/com.TribeXR.TribeXR/files/tribemod/ready.txt") cat "$R" 2>/dev/null;;
  "dumpsys activity activities") [ -f "$S/dialog" ] && echo "  * ActivityRecord{1 u0 com.oculus.vrshell/.systemdialog.launchcheck.UnOfficialAppDialogActivity t9}";;
  "uiautomator dump /dev/tty") [ -f "$S/dialog" ] && echo '<node text="Restore" /><node text="Open App" />'; echo "UI hierchary dumped to: /dev/tty";;
  date*) echo "10-31 17:00:00.000";;
  "logcat -b crash -d") cat "$M/crash.txt" 2>/dev/null;;
  logcat*) cat "$M/logcat.txt" 2>/dev/null;;
  *) echo "mock adb: unexpected shell command: $c" >&2; echo "UNEXPECTED $c" >> "$M/unexpected.txt"; exit 1;;
esac
EOF
chmod +x "$T/adb"
PKG=com.TribeXR.TribeXR
fresh(){  # a new fake headset: Tribe installed, not running; $1 = the next launches' outcomes, one per line
  M=$T/dev_$1; rm -rf "$M"; mkdir -p "$M/state" "$M/sdcard/Android/data/$PKG/files/tribemod"
  printf '%s\n' $2 > "$M/state/outcomes"; echo 17000 > "$M/state/nextpid"; : > "$M/calls.txt"; : > "$M/logcat.txt"; }
check(){  # run the tool on the fake headset; extra args pass through; stdin from $KEYS (default: one Enter)
  (cd "$REPO" && printf '\n' | env ADB="$T/adb" MOCK="$M" OUT="$M/out" READY_WAIT=4 POLL=1 DIALOG_WAIT=2 STOP_WAIT=2 START_WAIT=3 \
     bash scripts/launch_check.sh "$@") > "$M/stdout.txt" 2>&1; }
forbidden(){ grep -qE '(^| )(install|uninstall|push|input|rm |pm grant|tap)' "$M/calls.txt" || [ -s "$M/unexpected.txt" ]; }
summ(){ cat "$M"/out/*/summary.txt 2>/dev/null; }

echo "1. dry run: prints the commands, runs none"
fresh a "pass"; check 2 --dry-run; rc=$?
ok "exit 0" "[ $rc = 0 ]"; ok "printed am start" "grep -q '\[dry-run\] adb -s 2G0YC1ZF96072F shell am start -n $PKG' \"\$M/stdout.txt\""
ok "no adb call reached the headset" "[ ! -s \"\$M/calls.txt\" ]"

echo "2. three cold starts, all ready"
fresh b "pass pass pass"; check 3; rc=$?
ok "exit 0" "[ $rc = 0 ]"; ok "3 PASS" "grep -q 'result: 3 PASS, 0 FAIL of 3' \"\$M/stdout.txt\""
ok "names the build" "grep -q '5b1cb617e66687070bc3f5886bb9495f' \"\$M/stdout.txt\""
ok "force-stop + start x3" "[ \$(grep -c 'am force-stop' \"\$M/calls.txt\") = 3 ] && [ \$(grep -c 'am start' \"\$M/calls.txt\") = 3 ]"
ok "nothing forbidden (install/push/input/rm)" "! forbidden"

echo "3. a launch where the stage doesn't load: FAIL, the part named"
fresh c "pass fail pass"; check 3; rc=$?
ok "exit 1" "[ $rc = 1 ]"; ok "2 PASS 1 FAIL" "grep -q 'result: 2 PASS, 1 FAIL of 3' \"\$M/stdout.txt\""
ok "names the missing part" "grep -q 'FAIL (pid 17001): missing stage(' \"\$M/stdout.txt\""
ok "most common missing part: stage" "grep -q 'most common missing part: *1 stage' \"\$M/stdout.txt\""

echo "4. a launch that never gets to all=1 in time: FAIL with the last line's missing parts"
fresh d "slow"; check 1; rc=$?
ok "exit 1" "[ $rc = 1 ]"; ok "missing stage(waiting...)" "grep -q 'missing stage(waiting(settle 2/4' \"\$M/stdout.txt\""

echo "5. a crash on launch 2: stops there, its lines saved"
fresh e "pass crash pass"; check 3; rc=$?
ok "exit 4" "[ $rc = 4 ]"; ok "stopped after launch 2" "[ \$(summ | wc -l) = 2 ]"
ok "said CRASH" "grep -q 'CRASH: Tribe (pid 17001) died' \"\$M/stdout.txt\""
ok "crash file has the fatal signal" "grep -q 'Fatal signal 11' \"\$M\"/out/*/launch_2_crash.txt"
ok "nothing forbidden" "! forbidden"

echo "6. Meta's dialog with RESTORE stays up: stops, taps nothing"
fresh f "dialog pass"; check 2; rc=$?
ok "exit 3" "[ $rc = 3 ]"; ok "tells you: never RESTORE" "grep -q 'never RESTORE' \"\$M/stdout.txt\""
ok "only one launch" "[ \$(grep -c 'am start' \"\$M/calls.txt\") = 1 ]"; ok "no input/tap" "! forbidden"

echo "7. the headset off USB"
fresh g "pass"; touch "$M/offline"; check 1; rc=$?
ok "exit 2" "[ $rc = 2 ]"; ok "says plug it in" "grep -q 'not on USB' \"\$M/stdout.txt\""; ok "no launch" "! grep -q 'am start' \"\$M/calls.txt\""

echo "8. preflight: Tribe running and ready, no auth errors: GO"
fresh h ""; echo 17500 > "$M/state/pid"
printf '[READY] all=1 step=C pid=17500 t=41.2s hook=1 world=1 avatar=1 skin=horseman.glb stage="Graveyard Shift" stream=1280x720 menus=env7/7,avatar7/7 paks=7/7 gen=0 skips=0\n' \
  > "$M/sdcard/Android/data/$PKG/files/tribemod/ready.txt"
printf '10-31 16:59:00.000 17500 17550 I TRIBEMOD: [HOOK] ProcessEvent hooked\n' > "$M/logcat.txt"
check --preflight; rc=$?
ok "exit 0" "[ $rc = 0 ]"; ok "GO" "tail -1 \"\$M/stdout.txt\" | grep -q '^GO'"; ok "showed the stage" "grep -q 'stage   \"Graveyard Shift\"' \"\$M/stdout.txt\""
ok "asked for Go Live" "grep -q 'press GO LIVE now' \"\$M/stdout.txt\""; ok "didn't start or stop Tribe" "! grep -qE 'am (start|force-stop)' \"\$M/calls.txt\""

echo "9. preflight: auth errors in the log: NOT READY, run the login fix"
fresh i ""; echo 17500 > "$M/state/pid"
printf '[READY] all=1 step=C pid=17500 t=41.2s hook=1 world=1 avatar=1 skin=horseman.glb stage="Graveyard Shift" stream=1280x720 menus=env7/7 gen=0 skips=0\n' \
  > "$M/sdcard/Android/data/$PKG/files/tribemod/ready.txt"
printf '10-31 16:59:00.000 17500 17550 E MakeEvoRequest: code 190, message: Invalid OAuth 2.0 Access Token\n' > "$M/logcat.txt"
check --preflight; rc=$?
ok "exit 1" "[ $rc = 1 ]"; ok "NOT READY: the Meta login" "grep -q 'NOT READY: the Meta login' \"\$M/stdout.txt\""
ok "fix: Fix Tribe Login.exe" "grep -q 'Fix Tribe Login.exe' \"\$M/stdout.txt\""

echo "10. preflight: a part not loaded: NOT READY, relaunch"
fresh j ""; echo 17500 > "$M/state/pid"
printf '[READY] all=0 step=C pid=17500 t=24.8s hook=1 world=1 avatar=1 skin=horseman.glb stage=waiting(settle 2/4, try 1) stream=1280x720 menus=env7/7 gen=0 skips=0 missing=stage(waiting(settle 2/4, try 1))\n' \
  > "$M/sdcard/Android/data/$PKG/files/tribemod/ready.txt"
check --preflight; rc=$?
ok "exit 1" "[ $rc = 1 ]"; ok "NOT READY: parts not loaded: stage" "grep -q 'NOT READY: parts not loaded: stage(' \"\$M/stdout.txt\""
ok "fix: launch it again" "grep -q 'close Tribe, launch it again' \"\$M/stdout.txt\""

echo "11. preflight: the headset off USB"
fresh k ""; touch "$M/offline"; check --preflight; rc=$?
ok "exit 2" "[ $rc = 2 ]"; ok "says plug it in" "grep -q 'plug it in' \"\$M/stdout.txt\""

echo "12. preflight: Tribe not running: it starts it, then GO"
fresh l "pass"; check --preflight; rc=$?
ok "exit 0" "[ $rc = 0 ]"; ok "started Tribe" "grep -q 'am start' \"\$M/calls.txt\""; ok "GO" "tail -1 \"\$M/stdout.txt\" | grep -q '^GO'"
ok "nothing forbidden" "! forbidden"

echo; echo "passed $PASS, failed $FAIL"; [ $FAIL = 0 ]
