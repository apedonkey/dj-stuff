#!/usr/bin/env python3
"""Build an unsigned mod APK the way today's combo_* builds are laid out (read-only on its inputs).

Usage: python -P make_apk.py <base.apk> <AndroidManifest.xml> <libUnreal.patched.so> <libhook.so> <out.unsigned.apk>

Every entry of Tribe's base.apk except META-INF/ is copied in order with its own ZipInfo (compression type kept),
the manifest and libUnreal.so are taken from the given files, and lib/arm64-v8a/libhook.so is added; those three go
last, deflated, as in combo_pedriver_2311.apk. Then: bash scripts/sign_apk.sh <out.unsigned.apk> <out.apk>.
"""
import sys
import zipfile

base, manifest, unreal, hook, out = sys.argv[1:6]
REPLACED = {"AndroidManifest.xml": manifest, "lib/arm64-v8a/libUnreal.so": unreal}

with zipfile.ZipFile(base) as zin, zipfile.ZipFile(out, "w") as zout:
    n = 0
    for info in zin.infolist():
        if info.filename.startswith("META-INF/") or info.filename in REPLACED:
            continue
        zout.writestr(info, zin.read(info.filename), compress_type=info.compress_type)
        n += 1
    for name, path in list(REPLACED.items()) + [("lib/arm64-v8a/libhook.so", hook)]:
        zi = zipfile.ZipInfo(name, date_time=(2026, 10, 31, 0, 0, 0))
        zi.compress_type = zipfile.ZIP_DEFLATED
        zi.external_attr = 0o644 << 16
        zout.writestr(zi, open(path, "rb").read(), compress_type=zipfile.ZIP_DEFLATED)
        n += 1
print(f"wrote {out}: {n} entries")
