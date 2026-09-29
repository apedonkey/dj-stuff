#!/usr/bin/env python3
"""List the file paths inside UE5 .pak files WITHOUT decompressing anything.

The pak index (v11, unencrypted here) carries a Full Directory Index of plaintext paths, so the
whole virtual file list can be read without Oodle. Reads the pak bytes straight from their stored
(uncompressed) entries inside the OBB zip, so nothing is extracted to disk.

Usage: python scripts/pak_list.py OBB OUT.txt
"""
import struct
import sys
import zipfile

MAGIC = struct.pack("<I", 0x5A6F12E1)


class Reader:
    """Random-access reader over a stored (uncompressed) zip entry."""
    def __init__(self, path, info):
        if info.compress_type != zipfile.ZIP_STORED:
            raise ValueError("entry is compressed inside the zip")
        self.f = open(path, "rb")
        self.f.seek(info.header_offset)
        local = self.f.read(30)
        if local[:4] != b"PK\x03\x04":
            raise ValueError("bad local header")
        name_len, extra_len = struct.unpack_from("<HH", local, 26)
        self.base = info.header_offset + 30 + name_len + extra_len
        self.size = info.file_size

    def at(self, off, n):
        self.f.seek(self.base + off)
        return self.f.read(n)


def find_footer(r):
    tail = r.at(r.size - 1024, 1024)
    pos = tail.rfind(MAGIC)
    if pos < 0:
        raise ValueError("no pak magic")
    version, index_offset, index_size = struct.unpack_from("<iqq", tail, pos + 4)
    return version, index_offset, index_size


class Buf:
    def __init__(self, data):
        self.d = data
        self.o = 0

    def i32(self):
        v = struct.unpack_from("<i", self.d, self.o)[0]
        self.o += 4
        return v

    def u32(self):
        v = struct.unpack_from("<I", self.d, self.o)[0]
        self.o += 4
        return v

    def i64(self):
        v = struct.unpack_from("<q", self.d, self.o)[0]
        self.o += 8
        return v

    def u64(self):
        v = struct.unpack_from("<Q", self.d, self.o)[0]
        self.o += 8
        return v

    def skip(self, n):
        self.o += n

    def fstring(self):
        n = self.i32()
        if n == 0:
            return ""
        if n < 0:                       # UTF-16LE, -n uint16 code units incl. null
            raw = self.d[self.o:self.o - 2 * n]
            self.o += -2 * n
            return raw.decode("utf-16-le", "replace").rstrip("\0")
        raw = self.d[self.o:self.o + n]  # ASCII, n bytes incl. null
        self.o += n
        return raw.decode("latin-1").rstrip("\0")


def read_primary(r, index_offset, index_size):
    b = Buf(r.at(index_offset, index_size))
    mount = b.fstring()
    b.i32()          # NumEntries
    b.u64()          # PathHashSeed
    full_off = full_size = None
    if b.i32() != 0:                 # has path-hash index
        b.i64(); b.i64(); b.skip(20)
    if b.i32() != 0:                 # has full directory index
        full_off = b.i64(); full_size = b.i64(); b.skip(20)
    return mount, full_off, full_size


def read_full_dir(r, off, size):
    b = Buf(r.at(off, size))
    out = []
    ndirs = b.i32()
    for _ in range(ndirs):
        d = b.fstring()
        nfiles = b.i32()
        for _ in range(nfiles):
            fn = b.fstring()
            b.u32()                  # encoded entry location
            out.append((d, fn))
    return out


def main(argv):
    if len(argv) != 2:
        sys.exit(__doc__)
    obb, out = argv
    total = 0
    with zipfile.ZipFile(obb) as zf, open(out, "w", encoding="utf-8", newline="\n") as fh:
        paks = [i for i in zf.infolist() if i.filename.lower().endswith(".pak")]
        for info in paks:
            r = Reader(obb, info)
            version, io, isz = find_footer(r)
            mount, foff, fsize = read_primary(r, io, isz)
            fh.write(f"# PAK {info.filename}  version={version}  mount={mount}  "
                     f"index@{io}:{isz}  fulldir@{foff}:{fsize}\n")
            if foff is None:
                fh.write("#   (no full directory index)\n")
                print(f"{info.filename}: no full directory index")
                continue
            entries = read_full_dir(r, foff, fsize)
            for d, fn in sorted(entries):
                path = (mount + d + fn).replace("\\", "/").replace("//", "/")
                fh.write(path + "\n")
            total += len(entries)
            print(f"{info.filename}: {len(entries)} files  mount={mount}")
    print(f"total files listed: {total} -> {out}")


if __name__ == "__main__":
    main(sys.argv[1:])
