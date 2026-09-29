#!/usr/bin/env python3
"""Verify a .glb is a valid glTF binary and print size + md5. Usage: python glb_verify.py FILE..."""
import hashlib
import struct
import sys

for path in sys.argv[1:]:
    d = open(path, "rb").read()
    ok = d[:4] == b"glTF"
    ver = length = 0
    if ok:
        ver, length = struct.unpack_from("<II", d, 4)
    md5 = hashlib.md5(d).hexdigest()
    print(f"{path}: {len(d):,} bytes  {'glTF v'+str(ver) if ok else 'NOT glTF'}  "
          f"len_match={length == len(d)}  md5={md5}")
