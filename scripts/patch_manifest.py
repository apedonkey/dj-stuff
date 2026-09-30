#!/usr/bin/env python3
"""Add elements to a binary (AXML) AndroidManifest.xml by cloning existing sibling elements.

Each clone copies an existing <tag android:name="TEMPLATE" ...> element's START/END chunks byte-for-byte
(so attribute encoding, namespace refs and attribute order match what aapt produced) and re-points the
android:name value at a new string appended to the end of the string pool. Appending (never inserting)
keeps every existing string index valid, including the resource-map-bound attribute-name strings.

usage: patch_manifest.py IN OUT tag:TEMPLATE_NAME:NEW_NAME [...]
Idempotent: an element whose android:name already equals NEW_NAME is left alone.
"""
import struct
import sys

RES_STRING_POOL = 0x0001
RES_XML_START_ELEMENT = 0x0102
RES_XML_END_ELEMENT = 0x0103
ATTR_ANDROID_NAME = 0x01010003
TYPE_STRING = 0x03
UTF8_FLAG = 0x100


def u16(b, o): return struct.unpack_from("<H", b, o)[0]
def u32(b, o): return struct.unpack_from("<I", b, o)[0]


class StringPool:
    def __init__(self, data, off):
        self.off = off
        _, self.hdr, self.size = struct.unpack_from("<HHI", data, off)
        (self.count, self.style_count, self.flags,
         self.strings_start, self.styles_start) = struct.unpack_from("<IIIII", data, off + 8)
        if self.flags & UTF8_FLAG:
            raise SystemExit("UTF-8 string pool not supported (this manifest's pool is UTF-16)")
        if self.style_count:
            raise SystemExit("styled string pool not supported")
        base = off + self.hdr
        self.offsets = list(struct.unpack_from("<%dI" % self.count, data, base))
        self.blob = bytearray(data[off + self.strings_start: off + self.size])
        self.strings = [self._decode(o) for o in self.offsets]

    def _decode(self, o):
        n = u16(self.blob, o)
        p = o + 2
        if n & 0x8000:
            n = ((n & 0x7FFF) << 16) | u16(self.blob, p)
            p += 2
        return self.blob[p:p + 2 * n].decode("utf-16-le")

    def index_of(self, s):
        try:
            return self.strings.index(s)
        except ValueError:
            return -1

    def add(self, s):
        i = self.index_of(s)
        if i >= 0:
            return i
        enc = s.encode("utf-16-le")
        n = len(s)
        if n >= 0x8000:
            raise SystemExit("string too long")
        self.offsets.append(len(self.blob))
        self.blob += struct.pack("<H", n) + enc + b"\x00\x00"
        self.strings.append(s)
        return len(self.strings) - 1

    def build(self):
        blob = bytes(self.blob)
        blob += b"\x00" * ((-len(blob)) % 4)
        count = len(self.offsets)
        strings_start = self.hdr + 4 * count
        size = strings_start + len(blob)
        head = struct.pack("<HHI", RES_STRING_POOL, self.hdr, size)
        head += struct.pack("<IIIII", count, 0, self.flags, strings_start, 0)
        head += b"\x00" * (self.hdr - len(head))
        return head + struct.pack("<%dI" % count, *self.offsets) + blob


def chunks(data, start):
    off = start
    while off < len(data):
        t, h, sz = struct.unpack_from("<HHI", data, off)
        if sz < 8 or off + sz > len(data):
            raise SystemExit("corrupt chunk at %#x" % off)
        yield off, t, h, sz
        off += sz


def element_attrs(data, off):
    """(ns, name, count, attr_start_abs, attr_size) of a START_ELEMENT chunk."""
    h = u16(data, off + 2)
    ext = off + h
    ns, name, astart, asize, acount = struct.unpack_from("<IIHHH", data, ext)
    return ns, name, acount, ext + astart, asize


def android_name_value(data, off, pool, name_attr_idx):
    _, _, cnt, a0, asz = element_attrs(data, off)
    for k in range(cnt):
        a = a0 + k * asz
        if u32(data, a + 4) == name_attr_idx:
            raw = u32(data, a + 8)
            dtype = data[a + 15]
            if dtype == TYPE_STRING and raw != 0xFFFFFFFF:
                return pool.strings[raw], a
    return None, None


def main():
    if len(sys.argv) < 4:
        raise SystemExit(__doc__)
    src, dst, specs = sys.argv[1], sys.argv[2], sys.argv[3:]
    data = bytes(open(src, "rb").read())
    ftype, fhdr, fsize = struct.unpack_from("<HHI", data, 0)
    if ftype != 0x0003 or fsize != len(data):
        raise SystemExit("not a binary XML file")

    pool_off = fhdr
    if u16(data, pool_off) != RES_STRING_POOL:
        raise SystemExit("first chunk is not a string pool")
    pool = StringPool(data, pool_off)
    body_start = pool_off + pool.size

    # android:name is the pool string bound to resource id 0x01010003 by the resource map
    name_attr_idx = -1
    for off, t, h, sz in chunks(data, body_start):
        if t == 0x0180:
            ids = struct.unpack_from("<%dI" % ((sz - h) // 4), data, off + h)
            if ATTR_ANDROID_NAME in ids:
                name_attr_idx = ids.index(ATTR_ANDROID_NAME)
            break
    if name_attr_idx < 0 or pool.strings[name_attr_idx] != "name":
        raise SystemExit("could not resolve android:name attribute string")

    # Index every element: (start_off, end_off_exclusive, tag, android:name value)
    elems, stack = [], []
    for off, t, h, sz in chunks(data, body_start):
        if t == RES_XML_START_ELEMENT:
            stack.append(off)
        elif t == RES_XML_END_ELEMENT:
            s = stack.pop()
            tag = pool.strings[element_attrs(data, s)[1]]
            val, _ = android_name_value(data, s, pool, name_attr_idx)
            elems.append((s, off + sz, tag, val))
    if stack:
        raise SystemExit("unbalanced elements")

    inserts = []  # (insert_after_offset, bytes)
    for spec in specs:
        tag, template, new = spec.split(":", 2)
        if any(e[2] == tag and e[3] == new for e in elems):
            print("skip (already present): <%s android:name=%s>" % (tag, new))
            continue
        tpl = [e for e in elems if e[2] == tag and e[3] == template]
        if len(tpl) != 1:
            raise SystemExit("template <%s android:name=%s> found %d times" % (tag, template, len(tpl)))
        s, e, _, _ = tpl[0]
        clone = bytearray(data[s:e])
        # the clone must be exactly START + END (a leaf element) so no children get duplicated
        start_sz = u32(clone, 4)
        if u16(clone, start_sz) != RES_XML_END_ELEMENT or start_sz + u32(clone, start_sz + 4) != len(clone):
            raise SystemExit("template <%s %s> is not a leaf element" % (tag, template))
        new_idx = pool.add(new)
        _, a = android_name_value(data, s, pool, name_attr_idx)
        rel = a - s
        struct.pack_into("<I", clone, rel + 8, new_idx)        # rawValue
        struct.pack_into("<I", clone, rel + 16, new_idx)       # typedValue.data
        inserts.append((e, bytes(clone)))
        print("clone <%s android:name=%s> -> %s (string #%d)" % (tag, template, new, new_idx))

    if not inserts:
        open(dst, "wb").write(data)
        print("no changes")
        return

    body = bytearray()
    cur = body_start
    for at, blob in sorted(inserts):
        body += data[cur:at] + blob
        cur = at
    body += data[cur:]
    out = pool.build() + bytes(body)
    out = struct.pack("<HHI", 0x0003, fhdr, fhdr + len(out)) + data[8:fhdr] + out
    open(dst, "wb").write(out)
    print("wrote %s: %d -> %d bytes, strings %d -> %d" % (dst, len(data), len(out), pool.count, len(pool.strings)))


if __name__ == "__main__":
    main()
