#!/usr/bin/env python3
"""Print the FPakInfo footer of Unreal .pak files, standalone or stored inside a zip/OBB.

The footer gives the pak format version, whether the pak index is encrypted, the AES key GUID
the pak expects, and the compression methods its entries may use. Together these decide how
much a plain-text grep over the pak can see.

Usage: python scripts/pak_footer.py FILE [FILE ...]
"""
import struct
import sys
import zipfile

MAGIC = struct.pack("<I", 0x5A6F12E1)
TAIL = 1024


def stored_entry_tail(path, info):
    """Last TAIL bytes of an uncompressed zip entry, read straight from the container."""
    if info.compress_type != zipfile.ZIP_STORED:
        raise ValueError("entry is compressed inside the zip")
    with open(path, "rb") as f:
        f.seek(info.header_offset)
        local = f.read(30)
        if local[:4] != b"PK\x03\x04":
            raise ValueError("bad local file header")
        name_len, extra_len = struct.unpack_from("<HH", local, 26)
        data_start = info.header_offset + 30 + name_len + extra_len
        n = min(TAIL, info.file_size)
        f.seek(data_start + info.file_size - n)
        return f.read(n)


def parse_footer(tail, size):
    pos = tail.rfind(MAGIC)
    if pos < 0:
        return {"error": "no pak magic in the last %d bytes" % len(tail)}
    version, index_offset, index_size = struct.unpack_from("<iqq", tail, pos + 4)
    info = {"pak_version": version, "index_offset": index_offset, "index_size": index_size}
    footer_rel = pos
    if version >= 4:
        info["encrypted_index"] = bool(tail[pos - 1])
        footer_rel = pos - 1
    if version >= 7:
        guid = tail[pos - 17:pos - 1]
        info["encryption_key_guid"] = guid.hex() + (" (all zero = default key)" if not any(guid) else "")
        footer_rel = pos - 17
    if version >= 8:
        names_at = pos + 44 + (1 if version == 9 else 0)
        names = []
        for i in range(5):
            raw = tail[names_at + 32 * i:names_at + 32 * (i + 1)]
            if len(raw) < 32:
                break
            name = raw.split(b"\0", 1)[0].decode("ascii", "replace")
            if name:
                names.append(name)
        info["compression_methods"] = names or ["(none)"]
    footer_start = size - len(tail) + footer_rel
    info["bytes_between_primary_index_and_footer"] = footer_start - (index_offset + index_size)
    return info


def report(label, tail, size):
    print(f"{label}  ({size:,} bytes)")
    for key, value in parse_footer(tail, size).items():
        print(f"    {key}: {value}")


def main(paths):
    for path in paths:
        if zipfile.is_zipfile(path):
            with zipfile.ZipFile(path) as zf:
                for info in zf.infolist():
                    if info.filename.lower().endswith(".pak"):
                        report(f"{path} :: {info.filename}", stored_entry_tail(path, info), info.file_size)
        else:
            with open(path, "rb") as f:
                f.seek(0, 2)
                size = f.tell()
                f.seek(max(0, size - TAIL))
                report(path, f.read(), size)


if __name__ == "__main__":
    main(sys.argv[1:])
