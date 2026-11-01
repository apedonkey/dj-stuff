#!/usr/bin/env bash
# install_tribemod_test.sh -- runs scripts/install_tribemod.sh against a fake adb (no headset needed).
#
#   bash tests/install_tribemod_test.sh
#
# The fake adb maps the device's /sdcard and /data/local onto a temp folder and runs `adb shell` commands there.
# Scenario 1: Tribe is installed with another signing key, so `install -r` is refused; with --yes the installer must
# uninstall, install fresh, push both OBBs, the starter files and a --media folder, and grant the permissions.
# Scenario 2: a re-run with the same key must update in place and skip both OBBs (same size and md5).
# Not covered: Android's real permission model (chmod results on a Windows disk mean nothing) and the in-headset steps.
set -euo pipefail
REPO="$(cd "$(dirname "$0")/.." && pwd)"
T="$(mktemp -d)"; trap 'rm -rf "$T"' EXIT
mkdir -p "$T/bin" "$T/rel/tribemod-starter/skins" "$T/rel/tribemod-starter/heads" "$T/rel/tribemod-starter/songs" "$T/media/Test Visuals"

cat > "$T/bin/adb" <<'EOF'
#!/usr/bin/env bash
R="$FAKE_ROOT"; ST="$R/.state"; mkdir -p "$R/sdcard" "$R/data/local/tmp"
map(){ local p="$1"; p="${p//\/data\/local/$R/data/local}"; p="${p//\/sdcard/$R/sdcard}"; printf '%s' "$p"; }
[[ "${1:-}" == "-s" ]] && shift 2
cmd="$1"; shift
case "$cmd" in
  devices) printf 'List of devices attached\nFAKE123\tdevice\n\n' ;;
  get-state) echo device ;;
  install) r=0; [[ "$1" == "-r" ]] && { r=1; shift; }
           if [[ $r == 1 && "${FAKE_MODE:-}" == incompatible && ! -f "$ST.uninstalled" ]]; then
             echo "adb: failed to install $1: Failure [INSTALL_FAILED_UPDATE_INCOMPATIBLE: signatures do not match]"; exit 1; fi
           echo "Success"; echo "install" >> "$ST.log" ;;
  uninstall) rm -rf "$R/sdcard/Android/obb/$1" "$R/sdcard/Android/data/$1"; touch "$ST.uninstalled"; echo "uninstall" >> "$ST.log"; echo Success ;;
  push) src="$1"; dst=$(map "$2")
        if [[ -d "$src" ]]; then if [[ -d "$dst" ]]; then cp -r "$src" "$dst/"; else cp -r "$src" "$dst"; fi
        else mkdir -p "$(dirname "$dst")"; cp "$src" "$dst"; fi
        echo "push $(basename "$src")" >> "$ST.log"; echo "1 file pushed" ;;
  shell) c=$(map "$*"); pm(){ echo "pm $1 ${3##*.}" >> "$ST.log"; }; appops(){ echo "appops $1 $3" >> "$ST.log"; }; eval "$c" ;;
  *) echo "fake adb: unsupported $cmd" >&2; exit 1 ;;
esac
EOF
chmod +x "$T/bin/adb"

cd "$T/rel"
head -c 3000 /dev/urandom > tribemod-2311-test.apk
head -c 5000 /dev/urandom > main.2311.com.TribeXR.TribeXR.obb
head -c 4000 /dev/urandom > patch.2311.com.TribeXR.TribeXR.obb
echo skullbuck.glb > tribemod-starter/active_skin.txt
echo "Dino Stage=/Game/Mods/Dino/Maps/Environment_Dino" > tribemod-starter/envs.txt
head -c 100 /dev/urandom > tribemod-starter/skins/skullbuck.glb
head -c 100 /dev/urandom > tribemod-starter/heads/horseman.glb
echo "match=x" > tribemod-starter/songs/0123456789abcdef.txt
head -c 50 /dev/urandom > "$T/media/Test Visuals/loop.mp4"

export FAKE_ROOT="$T/dev" ADB="$T/bin/adb"
fail=0
check(){ if eval "$2"; then echo "  ok    $1"; else echo "  FAIL  $1"; fail=1; fi; }
D="$FAKE_ROOT/sdcard/Android/data/com.TribeXR.TribeXR/files/tribemod"
O="$FAKE_ROOT/sdcard/Android/obb/com.TribeXR.TribeXR"

echo "== scenario 1: another signing key installed, --yes, --media"
FAKE_MODE=incompatible bash "$REPO/scripts/install_tribemod.sh" --yes --media "$T/media/Test Visuals" "$T/rel" > "$T/run1.txt" 2>&1 || { cat "$T/run1.txt"; exit 1; }
check "uninstalled once, then installed"   '[[ $(grep -c uninstall "$FAKE_ROOT/.state.log") == 1 ]] && grep -q "installed fresh" "$T/run1.txt"'
check "both OBBs pushed"                   'cmp -s "$O/main.2311.com.TribeXR.TribeXR.obb" main.2311.com.TribeXR.TribeXR.obb && cmp -s "$O/patch.2311.com.TribeXR.TribeXR.obb" patch.2311.com.TribeXR.TribeXR.obb'
check "starter files copied"               '[[ -f "$D/skins/skullbuck.glb" && -f "$D/heads/horseman.glb" && -f "$D/songs/0123456789abcdef.txt" && -f "$D/envs.txt" ]]'
check "switches created"                   '( for f in executor_on auto_load auto_actor body_tracking skin_menu env_menu drone_cam; do [[ -f "$D/$f" ]] || exit 1; done )'
check "staging folder removed"             '[[ -z "$(ls "$FAKE_ROOT/data/local/tmp")" ]]'
check "storage permissions granted"        '[[ $(grep -c "^pm grant" "$FAKE_ROOT/.state.log") == 5 && $(grep -c "^appops set" "$FAKE_ROOT/.state.log") == 3 ]]'
check "videos copied to Movies"            '[[ -f "$FAKE_ROOT/sdcard/Movies/Test Visuals/loop.mp4" ]]'

echo "== scenario 2: re-run with the same key"
bash "$REPO/scripts/install_tribemod.sh" "$T/rel" > "$T/run2.txt" 2>&1 || { cat "$T/run2.txt"; exit 1; }
check "updated in place"                   'grep -q "updated in place" "$T/run2.txt"'
check "both OBBs skipped"                  '[[ $(grep -c "is already there" "$T/run2.txt") == 2 ]]'
check "no second uninstall"                '[[ $(grep -c uninstall "$FAKE_ROOT/.state.log") == 1 ]]'

echo "== scenario 3: a missing OBB stops the run before anything is installed"
rm -rf "$FAKE_ROOT"; mv "$T/rel/patch.2311.com.TribeXR.TribeXR.obb" "$T/patch.bak"
if bash "$REPO/scripts/install_tribemod.sh" "$T/rel" > "$T/run3.txt" 2>&1; then r=0; else r=$?; fi
check "exits non-zero and names the file"  '[[ $r != 0 ]] && grep -q "missing file: .*patch.2311" "$T/run3.txt"'
check "nothing was installed"              '[[ ! -f "$FAKE_ROOT/.state.log" ]] || ! grep -q install "$FAKE_ROOT/.state.log"'

[[ $fail == 0 ]] && echo "PASS" || { echo "FAILED"; exit 1; }
