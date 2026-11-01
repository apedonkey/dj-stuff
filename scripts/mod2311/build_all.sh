#!/usr/bin/env bash
# build_all.sh [A] [B] [C] -- one at a time: compile src_<X> with the brief's recipe, package the APK like
# combo_pedriver_2311.apk, sign it (scripts/sign_apk.sh), compare it with the live APK, print md5s and sizes.
# Run from the repo root. Writes backup/mod2311_build/{out_<X>/, mod2311_<X>.apk, mod2311_<X>_libhook.so}.
set -euo pipefail
cd "$(dirname "$0")/../../.."
B=backup/mod2311_build
CXX=out/android-ndk-r26d/toolchains/llvm/prebuilt/windows-x86_64/bin/aarch64-linux-android32-clang++
STEPS=("$@"); [ ${#STEPS[@]} -gt 0 ] || STEPS=(A B C)
for X in "${STEPS[@]}"; do
  echo "=== step $X"
  mkdir -p "$B/out_$X"
  "$CXX" -shared -fPIC -O2 -fvisibility=hidden -nostdlib++ -Wl,--no-undefined -Wall -Wformat=2 \
    -o "$B/out_$X/libhook.so" "$B/src_$X/dumper.cpp" "$B/src_$X/vendor/And64InlineHook.cpp" -llog -lm > "$B/out_$X/build.log" 2>&1
  echo "compile: exit 0, $(grep -c 'warning:' "$B/out_$X/build.log") warnings"
  grep 'warning:' "$B/out_$X/build.log" | sed -E 's/^[^:]*:[0-9]+:[0-9]+: //' | sort | uniq -c
  cp "$B/out_$X/libhook.so" "$B/mod2311_${X}_libhook.so"
  python -P "$B/tools/make_apk.py" backup/tribe_2311/apk/base.apk backup/mod_fix_stream_fallback/manifest/AndroidManifest.xml \
    backup/mod_fix_work/lib/libUnreal.2311.patched.so "$B/mod2311_${X}_libhook.so" "$B/out_$X/mod2311_$X.unsigned.apk"
  bash scripts/sign_apk.sh "$B/out_$X/mod2311_$X.unsigned.apk" "$B/mod2311_$X.apk" | tail -1
  rm -f "$B/out_$X/mod2311_$X.unsigned.apk"
  python -P "$B/tools/compare_apk.py" backup/mod_fix_stream_fix/combo_pedriver_2311.apk "$B/mod2311_$X.apk"
  md5sum "$B/mod2311_$X.apk" "$B/mod2311_${X}_libhook.so"
  stat -c '%s bytes %n' "$B/mod2311_$X.apk" "$B/mod2311_${X}_libhook.so"
done
