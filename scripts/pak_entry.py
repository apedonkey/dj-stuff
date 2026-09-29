#!/usr/bin/env python3
"""Decode the pak entry for files matching a query, to report each one's COMPRESSION METHOD
(0 = stored/none, else an index into the pak's compression-methods list, e.g. Oodle), offset and
sizes. This says whether a file can be extracted without an Oodle decompressor. Reads only the pak
index from inside the OBB; extracts nothing.

Usage: python scripts/pak_entry.py OBB QUERY_SUBSTRING
"""
import struct
import sys
import zipfile

from pak_list import Reader, find_footer, Buf


def read_index(r, io, isz):
    b = Buf(r.at(io, isz))
    mount = b.fstring()
    b.i32()                    # NumEntries
    b.u64()                    # PathHashSeed
    if b.i32() != 0:
        b.i64(); b.i64(); b.skip(20)
    full_off = full_size = None
    if b.i32() != 0:
        full_off = b.i64(); full_size = b.i64(); b.skip(20)
    enc_size = b.i32()
    enc = b.d[b.o:b.o + enc_size]      # EncodedPakEntries blob
    return mount, full_off, full_size, enc


def read_methods(r):
    """Compression-method names live in the footer (5 * 32-byte names for pak v8+)."""
    tail = r.at(r.size - 1024, 1024)
    pos = tail.rfind(struct.pack("<I", 0x5A6F12E1))
    names = ["None"]
    names_at = pos + 44          # version>=8 layout used by these paks (v11)
    for i in range(5):
        raw = tail[names_at + 32 * i: names_at + 32 * (i + 1)]
        nm = raw.split(b"\0", 1)[0].decode("ascii", "replace")
        if nm:
            names.append(nm)
    return names


def dir_map(r, off, size):
    b = Buf(r.at(off, size))
    out = {}
    for _ in range(b.i32()):
        d = b.fstring()
        for _ in range(b.i32()):
            fn = b.fstring()
            loc = b.i32()          # FPakEntryLocation
            out[(d + fn)] = loc
    return out


def decode_entry(enc, loc):
    """Decode one encoded FPakEntry bitfield. Returns dict with the fields we need."""
    o = loc
    value = struct.unpack_from("<I", enc, o)[0]; o += 4
    if value & (1 << 31):
        offset = struct.unpack_from("<I", enc, o)[0]; o += 4
    else:
        offset = struct.unpack_from("<Q", enc, o)[0]; o += 8
    if value & (1 << 30):
        usize = struct.unpack_from("<I", enc, o)[0]; o += 4
    else:
        usize = struct.unpack_from("<Q", enc, o)[0]; o += 8
    method = (value >> 23) & 0x3f
    if method != 0:
        if value & (1 << 29):
            size = struct.unpack_from("<I", enc, o)[0]; o += 4
        else:
            size = struct.unpack_from("<Q", enc, o)[0]; o += 8
    else:
        size = usize
    encrypted = (value >> 22) & 1
    block_count = (value >> 6) & 0xffff
    return {"offset": offset, "size": size, "usize": usize, "method": method,
            "encrypted": bool(encrypted), "blocks": block_count}


def main(argv):
    if len(argv) != 2:
        sys.exit(__doc__)
    obb, query = argv
    q = query.lower()
    with zipfile.ZipFile(obb) as zf:
        for info in zf.infolist():
            if not info.filename.lower().endswith(".pak"):
                continue
            r = Reader(obb, info)
            version, io, isz = find_footer(r)
            mount, foff, fsize, enc = read_index(r, io, isz)
            if foff is None:
                continue
            methods = read_methods(r)
            dm = dir_map(r, foff, fsize)
            for path, loc in sorted(dm.items()):
                full = (mount + path)
                if q not in full.lower():
                    continue
                if loc < 0:
                    print(f"{full}\n    (non-encoded entry, list index {-(loc+1)})")
                    continue
                e = decode_entry(enc, loc)
                mname = methods[e["method"]] if e["method"] < len(methods) else f"#{e['method']}"
                print(f"{full}\n    method={e['method']} ({mname})  encrypted={e['encrypted']}  "
                      f"blocks={e['blocks']}  size={e['size']:,}  uncompressed={e['usize']:,}  "
                      f"offset={e['offset']}  pak={info.filename.split('/')[-1]}")


if __name__ == "__main__":
    main(sys.argv[1:])
