#!/usr/bin/env bash
# sign_apk.sh <in.apk> <out.apk> -- zipalign + sign a mod APK with tribe.keystore (alias "tribe").
# The keystore password is read from a private file OUTSIDE the repo (never stored here, never printed):
#     $TRIBE_KS_PASS  (default C:\Users\Chris\.tribe-signing\ks.pass)   -- one line, the store password.
# The key password equals the store password, so --key-pass is omitted (apksigner then reuses the store password).
# Don't pass the same file to both flags: apksigner reads them as consecutive lines of that file and hits EOF.
set -euo pipefail
cd "$(dirname "$0")/.."

[ $# -eq 2 ] || { echo "usage: $0 <in.apk> <out.apk>"; exit 2; }
IN=$1; OUT=$2
BT="C:/Users/Chris/AppData/Local/Android/Sdk/build-tools/30.0.3"
KS=tribe.keystore
PASS=${TRIBE_KS_PASS:-C:/Users/Chris/.tribe-signing/ks.pass}

[ -f "$IN" ]   || { echo "missing input apk: $IN"; exit 1; }
[ -f "$KS" ]   || { echo "missing keystore: $KS"; exit 1; }
[ -f "$PASS" ] || { echo "missing password file: $PASS (create it yourself; see NOTES.md)"; exit 1; }

TMP="${OUT%.apk}.unsigned-aligned.tmp.apk"
trap 'rm -f "$TMP"' EXIT
"$BT/zipalign.exe" -f -p 4 "$IN" "$TMP"
"$BT/apksigner.bat" sign --ks "$KS" --ks-key-alias tribe \
  --ks-pass "file:$PASS" --out "$OUT" "$TMP"
"$BT/apksigner.bat" verify "$OUT" && echo "signed + verified: $OUT"
