#!/usr/bin/env python3
"""Print every ASCII / UTF-16LE string (>= 4 chars) in a byte range of a file or of a stored
zip entry, in offset order. Used to read the neighbourhood of a hit from scan_strings.py.

Usage: python scripts/strings_at.py FILE [ENTRY] OFFSET RADIUS     (OFFSET/RADIUS accept 0x..)
"""
import struct
import sys
import zipfile

from scan_strings import RUN, decode


def entry_start(path, name):
    with zipfile.ZipFile(path) as zf:
        info = zf.getinfo(name)
    if info.compress_type != zipfile.ZIP_STORED:
        raise SystemExit("entry is compressed inside the zip; extract it first")
    with open(path, "rb") as f:
        f.seek(info.header_offset)
        local = f.read(30)
        name_len, extra_len = struct.unpack_from("<HH", local, 26)
    return info.header_offset + 30 + name_len + extra_len, info.file_size


def main(argv):
    if len(argv) not in (3, 4):
        sys.exit(__doc__)
    path, entry = argv[0], (argv[1] if len(argv) == 4 else None)
    offset, radius = int(argv[-2], 0), int(argv[-1], 0)
    base, size = entry_start(path, entry) if entry else (0, None)
    lo = max(0, offset - radius)
    hi = offset + radius if size is None else min(size, offset + radius)
    with open(path, "rb") as f:
        f.seek(base + lo)
        buf = f.read(hi - lo)
    runs = sorted((m.start(), enc, decode(m.group(), enc))
                  for enc, rx in RUN.items() for m in rx.finditer(buf))
    for start, enc, text in runs:
        mark = ">>" if lo + start <= offset < lo + start + len(text.encode("utf-16-le" if enc != "ascii" else "latin-1")) else "  "
        print(f"{mark} 0x{lo + start:08x} {'U' if enc != 'ascii' else 'A'} {text}")


if __name__ == "__main__":
    main(sys.argv[1:])
