#!/usr/bin/env bash
# fix_login_test.sh -- runs scripts/fix_login.sh against a fake headset (a mock adb over a temp folder): the whole
# re-seed, a failure + carry-on, a failed login, a dry run, the stages-file fallback, refusals, and the keyboard path
# the Desktop .exe uses. No real headset is touched.   bash tests/fix_login_test.sh
set -u
REPO=$(cd "$(dirname "$0")/.." && pwd)
T=$(mktemp -d); trap 'rm -rf "$T"' EXIT
PASS=0; FAIL=0
ok(){  if eval "$2"; then PASS=$((PASS+1)); echo "  ok    $1"; else FAIL=$((FAIL+1)); echo "  FAIL  $1   [$2]"; fi; }

# ---- the mock adb: a "headset" in $MOCK (sdcard/, data/local/tmp/, data/app/pkg/), logcat in $MOCK/logcat.txt
cat > "$T/adb" <<'EOF'
#!/usr/bin/env bash
M=${MOCK:?}
[ "${1:-}" = -s ] && shift 2
echo "$*" >> "$M/calls.txt"
map(){ sed -e "s#/sdcard/#$M/sdcard/#g" -e "s#/data/local/tmp#$M/data/local/tmp#g" -e "s#/data/app/#$M/data/app/#g"; }
dec(){ local n; [ -f "$M/fail.$1" ] || return 1; n=$(cat "$M/fail.$1"); [ "$n" -le 0 ] && return 1; echo $((n-1)) > "$M/fail.$1"; }
cmd=$1; shift
[ -f "$M/offline" ] && { echo "adb.exe: device '2G0YC1ZF96072F' not found" >&2; exit 1; }
case $cmd in
  get-state) echo device;;
  shell) c=$(printf '%s ' "$@" | map); PATH="$M/bin:$PATH" bash -c "$c" | sed 's/$/\r/'; exit "${PIPESTATUS[0]}";;
  install) dec install && { echo "adb: failed to install $1: Failure [INSTALL_FAILED_INTERNAL_ERROR]"; exit 1; }
    [ -f "$M/data/app/pkg/base.apk" ] && { echo "Failure [INSTALL_FAILED_UPDATE_INCOMPATIBLE]"; exit 1; }
    mkdir -p "$M/data/app/pkg"; cp "$1" "$M/data/app/pkg/base.apk"; echo "Performing Streamed Install"; echo Success;;
  uninstall) [ -f "$M/data/app/pkg/base.apk" ] || { echo "Failure [DELETE_FAILED_INTERNAL_ERROR]"; exit 1; }
    rm -rf "$M/data/app/pkg" "$M/sdcard/Android/data/$1" "$M/sdcard/Android/obb/$1" "$M/running"; echo Success;;
  push) dec push && { echo "adb: error: failed to copy '$1'"; exit 1; }
    dst=$(printf '%s' "$2" | map); if [ -d "$dst" ]; then cp -r "$1" "$dst/"; else mkdir -p "$(dirname "$dst")"; cp -r "$1" "$dst"; fi
    echo "$1: 1 file pushed, 0 skipped.";;
  pull) src=$(printf '%s' "$1" | map); [ -e "$src" ] || { echo "adb: error: remote object '$1' does not exist"; exit 1; }
    if [ -d "$2" ]; then cp -r "$src" "$2/"; else cp -r "$src" "$2"; fi; echo "$1: 1 file pulled.";;
  logcat) case "${1:-}" in -c) : > "$M/logcat.txt";; -d) cat "$M/logcat.txt" 2>/dev/null;; esac;;
  *) echo "mock adb: unknown $cmd" >&2; exit 1;;
esac
EOF
mkdir -p "$T/bin"
cat > "$T/bin/pm" <<'EOF'
#!/usr/bin/env bash
case $1 in
  path) [ -f "$MOCK/data/app/pkg/base.apk" ] || exit 1; echo "package:/data/app/pkg/base.apk";;
  grant) touch "$MOCK/grant.$3";;
esac
EOF
printf '#!/usr/bin/env bash\n[ -f "$MOCK/running" ] && echo 4242\n' > "$T/bin/pidof"
printf '#!/usr/bin/env bash\nexit 0\n' > "$T/bin/appops"
cat > "$T/bin/dumpsys" <<'EOF'
#!/usr/bin/env bash
[ "$1" = package ] && [ -f "$MOCK/grant.android.permission.READ_MEDIA_VIDEO" ] && echo "      android.permission.READ_MEDIA_VIDEO: granted=true, flags=[ ]"
exit 0
EOF
chmod +x "$T/adb" "$T"/bin/*

# ---- the PC side
mkdir -p "$T/pc"
printf 'GENUINE TRIBE 2304' > "$T/pc/genuine.apk"; printf 'MOD combo3' > "$T/pc/mod.apk"
head -c 300000 /dev/urandom > "$T/pc/main.obb"; head -c 50000 /dev/urandom > "$T/pc/mirror.obb"
PKG=com.TribeXR.TribeXR

fresh(){  # a new fake headset in $M: the mod installed, an expired login, Tribe running
  M=$T/dev_$1; rm -rf "$M"; mkdir -p "$M/bin" "$M/data/local/tmp" "$M/data/app/pkg"; cp "$T"/bin/* "$M/bin/"
  cp "$T/pc/mod.apk" "$M/data/app/pkg/base.apk"
  local O=$M/sdcard/Android/obb/$PKG D=$M/sdcard/Android/data/$PKG/files/tribemod
  mkdir -p "$O" "$D/skins" "$D/heads" "$D/songs"
  cp "$T/pc/main.obb" "$O/main.2311.$PKG.obb"; cp "${2:-$T/pc/mirror.obb}" "$O/patch.2311.$PKG.obb"
  printf 'Reactor' > "$D/active_env.txt"; printf 'lampwing.glb' > "$D/active_skin.txt"; echo 'Reactor|/Game/Mods/Club' > "$D/envs.txt"
  echo 'crowd=0.1 rim=0.15' > "$D/club.txt"; : > "$D/executor_on"; : > "$D/auto_load"
  head -c 20000 /dev/urandom > "$D/skins/lampwing.glb"; head -c 9000 /dev/urandom > "$D/heads/horseman.glb"
  echo cues > "$D/songs/Artist - Song One.txt"; echo more > "$D/songs/Ünïcode – Tëst (VIP).txt"
  cp -r "$D" "$M/original_tribemod"
  echo "E MakeEvoRequest: Original error: code 190, message: Invalid OAuth 2.0 Access Token" > "$M/logcat.txt"
  touch "$M/running"; : > "$M/calls.txt"; RUNS=$T/runs_$1; rm -rf "$RUNS"; }
run_bg(){ : > "$M/out.txt"; fix "$@" & P=$!; }   # fix in the background, on a fresh out.txt
fix(){  # run the tool on the fake headset (signal mode unless $KEYS); extra args pass through
  (cd "$REPO" && env ADB="$T/adb" MOCK="$M" GENUINE="$T/pc/genuine.apk" MAIN="$T/pc/main.obb" MIRROR="$T/pc/mirror.obb" \
     RUNS="$RUNS" WAIT_MAX=2 FIX_SIGNALS="${SIGS:-1}" bash "${FIX:-scripts/fix_login.sh}" "$@") > "$M/out.txt" 2>&1; }
login(){  # $1 good|bad: what the store version's login puts in the log once fix waits at the login step
  local i; for i in $(seq 1 300); do grep -q "(waiting for .*go\.1)" "$M/out.txt" 2>/dev/null && break; sleep 0.2; done
  touch "$M/running"
  if [ "$1" = good ]; then echo "I AuthLogger: Action succeeded: OBTAIN_TOKEN, callingPackage: com.oculus.horizon" >> "$M/logcat.txt"
  else echo "E MakeEvoRequest: code 190, message: Invalid OAuth 2.0 Access Token" >> "$M/logcat.txt"; fi
  touch "$(cat "$RUNS/current")/go.1"; }
restored(){  # the fake headset is back to how it started (mod, game data, stages file, every tribemod file, grants)
  local O=$M/sdcard/Android/obb/$PKG
  cmp -s "$M/data/app/pkg/base.apk" "$T/pc/mod.apk" && cmp -s "$O/main.2311.$PKG.obb" "$T/pc/main.obb" && \
  cmp -s "$O/patch.2311.$PKG.obb" "${1:-$T/pc/mirror.obb}" && \
  diff -r "$M/original_tribemod" "$M/sdcard/Android/data/$PKG/files/tribemod" >/dev/null && [ -f "$M/grant.android.permission.READ_MEDIA_VIDEO" ]; }
state(){ cat "$(cat "$RUNS/current" 2>/dev/null || ls -d "$RUNS"/2*/ | tail -1)/state" 2>/dev/null; }

echo "1. the whole re-seed"
fresh a; run_bg; login good; wait $P; rc=$?
ok "exit 0" "[ $rc = 0 ]"; ok "state done" "[ \"\$(state)\" = done ]"; ok "headset restored" "restored"
ok "store version installed + removed once" "[ \$(grep -c '^uninstall' \"\$M/calls.txt\") = 2 ] && [ \$(grep -c '^install' \"\$M/calls.txt\") = 2 ]"
ok "it saw the expired login" "grep -q \"That's the expired login\" \"\$M/out.txt\""
ok "login checked OK" "grep -q 'login OK: a fresh token' \"\$M/out.txt\""
ok "every file verified" "grep -q 'tribemod: all 10 files match' \"\$M/out.txt\""
ok "the PC copy holds the snapshot" "[ -f \"\$(ls -d \"\$RUNS\"/2*/ | tail -1)tribemod/songs/Artist - Song One.txt\" ]"

echo "2. the mod's install fails 3 times (after the login), then a re-run carries on"
fresh b; run_bg; for i in $(seq 1 300); do grep -q "(waiting for .*go\.1)" "$M/out.txt" 2>/dev/null && break; sleep 0.2; done
echo 3 > "$M/fail.install"; login good; wait $P; rc=$?
ok "stops (exit 1)" "[ $rc = 1 ]"; ok "stopped after the login" "[ \"\$(state)\" = login ]"
ok "says how to carry on" "grep -q 'run this again: it carries on' \"\$M/out.txt\""
ok "nothing installed at that point" "[ ! -f \"\$M/data/app/pkg/base.apk\" ]"
fix; rc=$?
ok "re-run: exit 0" "[ $rc = 0 ]"; ok "re-run: carried on" "grep -q 'it had got to: login' \"\$M/out.txt\""
ok "re-run: headset restored" "restored"; ok "re-run: no second login" "[ \$(grep -c '^uninstall' \"\$M/calls.txt\") = 2 ]"

echo "3. the store version's login fails, then succeeds on a re-run"
fresh c; run_bg; login bad; wait $P; rc=$?
ok "stops (exit 1)" "[ $rc = 1 ]"; ok "state a (before the login)" "[ \"\$(state)\" = a ]"
ok "mod NOT put back on a bad login" "cmp -s \"\$M/data/app/pkg/base.apk\" \"\$T/pc/genuine.apk\""
run_bg; login good; wait $P; rc=$?
ok "re-run: exit 0" "[ $rc = 0 ]"; ok "re-run: headset restored" "restored"

echo "4. dry run"
fresh d; fix --dry-run; rc=$?
ok "exit 0" "[ $rc = 0 ]"; ok "no install/uninstall/push" "! grep -qE '^(install|uninstall|push)' \"\$M/calls.txt\""
ok "Tribe untouched" "restored_dry(){ diff -r \"\$M/original_tribemod\" \"\$M/sdcard/Android/data/\$PKG/files/tribemod\" >/dev/null && cmp -s \"\$M/data/app/pkg/base.apk\" \"\$T/pc/mod.apk\"; }; restored_dry"
ok "no unfinished run left" "[ ! -f \"\$RUNS/current\" ]"; ok "snapshot saved" "[ -s \"\$(ls -d \"\$RUNS\"/2*/ | tail -1)manifest.txt\" ]"

echo "5. the headset's stages file isn't the PC's copy: the headset's own comes back"
head -c 40000 /dev/urandom > "$T/pc/other_patch.obb"
fresh e "$T/pc/other_patch.obb"; run_bg; login good; wait $P; rc=$?
ok "exit 0" "[ $rc = 0 ]"; ok "saved the headset's stages file" "grep -q \"isn't the PC's copy\" \"\$M/out.txt\""
ok "headset restored with ITS stages file" "restored \"\$T/pc/other_patch.obb\""

echo "6. refusals: the store version installed with no run to carry on; the headset off USB"
fresh f; cp "$T/pc/genuine.apk" "$M/data/app/pkg/base.apk"; fix; rc=$?
ok "store version: exit 1" "[ $rc = 1 ]"; ok "store version: nothing touched" "! grep -qE '^(install|uninstall|push)' \"\$M/calls.txt\""
fresh g; touch "$M/offline"; fix; rc=$?
ok "off USB: exit 1, waited" "[ $rc = 1 ] && grep -q 'waiting for the headset on USB' \"\$M/out.txt\""

echo "7. the keyboard path (the Desktop .exe): Enter at Start, at the login, at the final check"
fresh h; mkfifo "$T/keys"
( for i in $(seq 1 300); do grep -q 'Start?' "$M/out.txt" 2>/dev/null && break; sleep 0.2; done; echo
  for i in $(seq 1 300); do grep -q "When you're in a room -- then press Enter" "$M/out.txt" 2>/dev/null && break; sleep 0.2; done
  touch "$M/running"; echo "I AuthLogger: Action succeeded: OBTAIN_TOKEN" >> "$M/logcat.txt"; echo
  for i in $(seq 1 300); do grep -q 'Press Enter once you are in a room' "$M/out.txt" 2>/dev/null && break; sleep 0.2; done
  touch "$M/running"; echo ) > "$T/keys" &
SIGS=0 fix < "$T/keys"; rc=$?
ok "exit 0" "[ $rc = 0 ]"; ok "headset restored" "restored"; ok "final check: login OK" "grep -q 'Login OK: no auth errors' \"\$M/out.txt\""

echo "8. the mod rewrites load_result.txt between the restore and the check (2026-10-31): still OK"
fresh i; printf 'loaded 1' > "$M/sdcard/Android/data/$PKG/files/tribemod/load_result.txt"
cat > "$M/bin/pm" <<'EOF'
#!/usr/bin/env bash
case $1 in
  path) [ -f "$MOCK/data/app/pkg/base.apk" ] || exit 1; echo "package:/data/app/pkg/base.apk";;
  grant) touch "$MOCK/grant.$3"; printf 'loaded 2' > "$MOCK/sdcard/Android/data/com.TribeXR.TribeXR/files/tribemod/load_result.txt";;
esac
EOF
chmod +x "$M/bin/pm"
run_bg; login good; wait $P; rc=$?
ok "exit 0" "[ $rc = 0 ]"; ok "state done" "[ \"\$(state)\" = done ]"
ok "the other 10 files verified, load_result.txt skipped" "grep -q 'tribemod: all 10 files match (load_result.txt not compared' \"\$M/out.txt\""

echo "9. an unfinished fix whose mod was replaced since (2026-10-31): a fresh fix starts instead of stopping"
fresh j; OLD=$RUNS/20200101_000000; mkdir -p "$OLD"; echo login > "$OLD/state"
echo 0123456789abcdef0123456789abcdef > "$OLD/mod.md5"; echo "$OLD" > "$RUNS/current"
fix --dry-run; rc=$?
ok "dry run: exit 0, says out of date, old fix untouched" "[ $rc = 0 ] && grep -q 'is out of date' \"\$M/out.txt\" && [ \"\$(cat \"\$OLD/state\")\" = login ]"
run_bg; login good; wait $P; rc=$?
ok "exit 0" "[ $rc = 0 ]"; ok "said the old fix is out of date" "grep -q 'is out of date' \"\$M/out.txt\""
ok "old fix retired" "[ \"\$(cat \"\$OLD/state\")\" = stale ]"; ok "headset restored" "restored"

echo; echo "passed $PASS, failed $FAIL"; [ $FAIL = 0 ]
