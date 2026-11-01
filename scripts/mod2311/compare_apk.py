#!/usr/bin/env python3
"""Compare a built APK with the live one: which entries differ (by name, CRC, size, compression type).

Usage: python -P compare_apk.py <reference.apk> <candidate.apk>
Exit 0 only if the differences are exactly lib/arm64-v8a/libhook.so and META-INF/ signature files.
"""
import sys
import zipfile

ref, cand = sys.argv[1], sys.argv[2]
with zipfile.ZipFile(ref) as a, zipfile.ZipFile(cand) as b:
    A = {i.filename: i for i in a.infolist()}
    B = {i.filename: i for i in b.infolist()}
diff = []
for n in sorted(set(A) | set(B)):
    x, y = A.get(n), B.get(n)
    if x is None or y is None:
        diff.append((n, "only in " + ("candidate" if x is None else "reference")))
    elif (x.CRC, x.file_size, x.compress_type) != (y.CRC, y.file_size, y.compress_type):
        diff.append((n, f"crc {x.CRC:08x}->{y.CRC:08x} size {x.file_size}->{y.file_size} type {x.compress_type}->{y.compress_type}"))
allowed = all(n == "lib/arm64-v8a/libhook.so" or n.startswith("META-INF/") for n, _ in diff)
for n, why in diff:
    print(f"  {n}: {why}")
print(f"{len(A)} vs {len(B)} entries; {len(diff)} differ; only libhook.so + META-INF: {'YES' if allowed else 'NO'}")
sys.exit(0 if allowed else 1)
