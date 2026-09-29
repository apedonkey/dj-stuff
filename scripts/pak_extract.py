#!/usr/bin/env python3
"""Extract one file from a UE5 pak inside the OBB. Parses the full FPakEntry header at the entry
offset, pulls out the Oodle-compressed blocks, and writes:
  <outdir>/<name>.oodleblocks   all compressed blocks concatenated
  <outdir>/<name>.manifest.json {block_size, uncompressed_size, method, blocks:[{comp_len,raw_len}]}
A separate step decompresses the blocks (pure-Rust Oodle) and concatenates them to the real file.
For an uncompressed (method 0) entry it writes the file directly.

Usage: python scripts/pak_extract.py OBB SUBSTR OUTDIR
"""
import json
import os
import struct
import sys
import zipfile

from pak_list import Reader, find_footer, Buf
from pak_entry import read_index, read_methods, dir_map, decode_entry


def parse_header(r, entry_off, enc_meta):
    """Parse the FPakEntry header stored at the data section; validate vs the encoded index entry."""
    hdr = r.at(entry_off, 4096)
    o = 0
    def i64():
        nonlocal o; v = struct.unpack_from("<q", hdr, o)[0]; o += 8; return v
    def u32():
        nonlocal o; v = struct.unpack_from("<I", hdr, o)[0]; o += 4; return v
    def u8():
        nonlocal o; v = hdr[o]; o += 1; return v
    _hoff = i64()
    size = i64()
    usize = i64()
    method = u32()
    o += 20                       # SHA1 hash
    blocks = []
    if method != 0:
        nblocks = struct.unpack_from("<i", hdr, o)[0]; o += 4
        for _ in range(nblocks):
            start = i64(); end = i64()
            blocks.append((start, end))
    _flags = u8()
    block_size = u32()
    header_size = o
    # validate against the encoded index entry
    assert size == enc_meta["size"], (size, enc_meta["size"])
    assert usize == enc_meta["usize"], (usize, enc_meta["usize"])
    assert method == enc_meta["method"], (method, enc_meta["method"])
    assert len(blocks) == enc_meta["blocks"], (len(blocks), enc_meta["blocks"])
    # block offsets: relative to entry_off (v9+) or absolute; detect from block[0]
    rel = True
    if blocks:
        if abs(blocks[0][0] - header_size) <= 64:
            rel = True
        elif abs(blocks[0][0] - (entry_off + header_size)) <= 64:
            rel = False
    return {"size": size, "usize": usize, "method": method, "blocks": blocks,
            "block_size": block_size, "header_size": header_size, "relative": rel}


def main(argv):
    if len(argv) != 3:
        sys.exit(__doc__)
    obb, substr, outdir = argv
    os.makedirs(outdir, exist_ok=True)
    q = substr.lower()
    with zipfile.ZipFile(obb) as zf:
        for info in zf.infolist():
            if not info.filename.lower().endswith(".pak"):
                continue
            r = Reader(obb, info)
            _v, io, isz = find_footer(r)
            mount, foff, fsize, enc = read_index(r, io, isz)
            if foff is None:
                continue
            methods = read_methods(r)
            for path, loc in dir_map(r, foff, fsize).items():
                full = mount + path
                if q not in full.lower() or loc < 0:
                    continue
                e = decode_entry(enc, loc)
                name = os.path.basename(full)
                print(f"{full}\n  pak={info.filename.split('/')[-1]} method={e['method']}"
                      f"({methods[e['method']] if e['method'] < len(methods) else '?'}) "
                      f"blocks={e['blocks']} size={e['size']:,} usize={e['usize']:,} off={e['offset']}")
                if e["method"] == 0:
                    data = r.at(e["offset"] + _hdrsize_stored(r, e["offset"]), e["size"])
                    open(os.path.join(outdir, name), "wb").write(data)
                    print(f"  -> stored, wrote {name} ({len(data)} bytes)")
                    continue
                h = parse_header(r, e["offset"], e)
                # v9+ relative offsets: block.start is relative to the entry offset (start≈header_size),
                # so absolute (within the pak data section) = entry_off + start. Absolute layout: start as-is.
                eoff = e["offset"] if h["relative"] else 0
                print(f"  header_size={h['header_size']} block0.start={h['blocks'][0][0]} relative={h['relative']}")
                comp = bytearray()
                man = {"block_size": h["block_size"], "uncompressed_size": h["usize"],
                       "method": h["method"], "method_name": methods[h["method"]], "blocks": []}
                remaining = h["usize"]
                for (start, end) in h["blocks"]:
                    cs = r.at(eoff + start, end - start)
                    raw = min(h["block_size"], remaining) if h["block_size"] else remaining
                    remaining -= raw
                    man["blocks"].append({"comp_len": len(cs), "raw_len": raw})
                    comp += cs
                with open(os.path.join(outdir, name + ".oodleblocks"), "wb") as fb:
                    fb.write(comp)
                with open(os.path.join(outdir, name + ".manifest.json"), "w") as fm:
                    json.dump(man, fm, indent=2)
                with open(os.path.join(outdir, name + ".blocks.txt"), "w", newline="\n") as fs:
                    for b in man["blocks"]:
                        fs.write(f"{b['comp_len']} {b['raw_len']}\n")
                tot = sum(b["comp_len"] for b in man["blocks"])
                print(f"  -> wrote {name}.oodleblocks ({tot:,} B, {len(man['blocks'])} blocks), "
                      f"manifest (raw total {sum(b['raw_len'] for b in man['blocks']):,} == usize {h['usize']:,}: "
                      f"{sum(b['raw_len'] for b in man['blocks']) == h['usize']}), relative_offsets={h['relative']}")


def _hdrsize_stored(r, off):
    hdr = r.at(off, 64)
    method = struct.unpack_from("<I", hdr, 24)[0]
    return 8 + 8 + 8 + 4 + 20 + 1 + 4    # no block array when stored


if __name__ == "__main__":
    main(sys.argv[1:])
