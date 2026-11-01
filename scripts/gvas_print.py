#!/usr/bin/env python3
"""Tribe's .sav files (Unreal SaveGame, "GVAS") as readable text: the lesson packs' equipment states, rig layouts,
replay settings and dance maps under Content/Replays.

    python -I scripts/gvas_print.py <dir or .sav> <out dir> [--check <file.usmap-schema.json>]

Reads both property-tag layouts in these files: UE 4.26/4.27 saves (SaveGame version 2: tag = name, type, size,
array index, type-specific fields, guid flag) and UE 5.4 saves (UE5 version 1012, PROPERTY_TAG_COMPLETE_TYPE_NAME:
tag = name, type-name tree, size, flags). Every value is read inside its tag's size, so a value this reader can't
decode prints as hex without losing the rest. One <out dir>/<path>.txt per save, plus a summary on stderr.
"""
import glob
import json
import os
import struct
import sys

NATIVE4 = {"Vector": "3f", "Rotator": "3f", "Vector2D": "2f", "Vector4": "4f", "Quat": "4f", "LinearColor": "4f",
           "IntPoint": "2i", "IntVector": "3i", "Color": "4B", "Guid": "16s", "DateTime": "q", "Timespan": "q"}
NATIVE5 = dict(NATIVE4, Vector="3d", Rotator="3d", Vector2D="2d", Vector4="4d", Quat="4d")   # large world coordinates


class R:
    def __init__(self, b, pos=0, end=None):
        self.b, self.p, self.end = b, pos, len(b) if end is None else end

    def take(self, n):
        if self.p + n > self.end:
            raise EOFError(f"read {n} at {self.p} past {self.end}")
        v = self.b[self.p:self.p + n]
        self.p += n
        return v

    def un(self, fmt):
        return struct.unpack("<" + fmt, self.take(struct.calcsize("<" + fmt)))

    def i32(self):
        return self.un("i")[0]

    def u8(self):
        return self.un("B")[0]

    def fstr(self):
        n = self.i32()
        if n == 0:
            return ""
        if n < 0:
            return self.take(-2 * n).decode("utf-16-le", "replace").rstrip("\0")
        if n > 1 << 20:
            raise ValueError(f"string length {n}")
        return self.take(n).decode("utf-8", "replace").rstrip("\0")


class Save:
    def __init__(self, b):
        r = R(b)
        if r.take(4) != b"GVAS":
            raise ValueError("not a GVAS save")
        self.sgv, self.ue4 = r.un("ii")
        self.ue5 = r.i32() if self.sgv >= 3 else 0
        maj, mi, pa, cl = r.un("HHHI")
        self.engine = f"{maj}.{mi}.{pa}"
        self.branch = r.fstr()
        self.cv_format, n = r.un("ii")
        r.take(20 * n)
        self.cls = r.fstr()
        self.full = self.ue5 >= 1012            # complete type names in tags
        self.lwc = self.ue5 >= 1004             # FVector etc. as doubles
        self.native = NATIVE5 if self.lwc else NATIVE4
        self.fallbacks = 0
        if self.ue5 >= 1011:                    # UObject's serialization-control byte (PROPERTY_TAG_EXTENSION_...)
            if r.u8() & 0x02:
                r.u8()
        self.props = self.tagged(r)
        self.trailing = r.end - r.p

    # ---- tags
    def typename(self, r):
        """UE 5.4's FPropertyTypeName: pre-order (name, parameter count) pairs -> (name, [params])"""
        name, count = r.fstr(), r.i32()
        return (name, [self.typename(r) for _ in range(count)])

    def tag(self, r):
        name = r.fstr()
        if name == "None" or name == "":
            return None
        t = {"name": name, "bool": None, "native": False}
        if self.full:
            t["type"] = self.typename(r)
            t["size"] = r.i32()
            flags = r.u8()
            t["index"] = r.i32() if flags & 0x01 else 0
            if flags & 0x02:
                r.take(16)
            if flags & 0x04:
                ext = r.u8()
                if ext & 0x02:
                    r.take(2)
            t["bool"] = bool(flags & 0x10)
            t["native"] = bool(flags & 0x08)
            return t
        typ = r.fstr()
        t["size"], t["index"] = r.un("ii")
        if typ == "StructProperty":
            sname = r.fstr(); r.take(16)
            t["type"] = (typ, [(sname, [])])
        elif typ == "BoolProperty":
            t["bool"] = bool(r.u8()); t["type"] = (typ, [])
        elif typ in ("ByteProperty", "EnumProperty"):
            t["type"] = (typ, [(r.fstr(), [])])
        elif typ in ("ArrayProperty", "SetProperty"):
            t["type"] = (typ, [(r.fstr(), [])])
        elif typ == "MapProperty":
            k = r.fstr(); v = r.fstr()
            t["type"] = (typ, [(k, []), (v, [])])
        else:
            t["type"] = (typ, [])
        if r.u8():
            r.take(16)
        return t

    def tagged(self, r):
        """properties until None -> [(name, text)]"""
        out = []
        while True:
            t = self.tag(r)
            if t is None:
                return out
            name = t["name"] + (f"[{t['index']}]" if t["index"] else "")
            if t["type"][0] == "BoolProperty":
                out.append((name, "true" if t["bool"] else "false"))
                r.take(t["size"])
                continue
            sub = R(r.b, r.p, r.p + t["size"])
            try:
                v = self.value(sub, t["type"], top=t)
                if sub.p != sub.end:
                    raise ValueError(f"{sub.end - sub.p} bytes left")
            except Exception as e:  # noqa: BLE001 - keep reading the next property
                self.fallbacks += 1
                v = f"<{t['type'][0]} not decoded ({e}): {r.b[r.p:r.p + min(t['size'], 48)].hex()}...>"
            r.p += t["size"]
            out.append((name, v))

    # ---- values
    def struct_name(self, typ):
        p = typ[1]
        return p[0][0] if p else "?"

    def value(self, r, typ, top=None, elem=False):
        k = typ[0]
        if k == "IntProperty": return str(r.un("i")[0])
        if k == "Int64Property": return str(r.un("q")[0])
        if k == "Int16Property": return str(r.un("h")[0])
        if k == "Int8Property": return str(r.un("b")[0])
        if k == "UInt16Property": return str(r.un("H")[0])
        if k == "UInt32Property": return str(r.un("I")[0])
        if k == "UInt64Property": return str(r.un("Q")[0])
        if k == "FloatProperty": return f"{r.un('f')[0]:.6g}"
        if k == "DoubleProperty": return f"{r.un('d')[0]:.10g}"
        if k == "BoolProperty": return "true" if r.u8() else "false"
        if k in ("StrProperty", "NameProperty"): return json.dumps(r.fstr(), ensure_ascii=False) if k == "StrProperty" else r.fstr()
        if k == "EnumProperty": return r.fstr()
        if k == "ByteProperty":
            en = typ[1][0][0] if typ[1] else "None"
            return r.fstr() if en not in ("None", "") and (top is None or top["size"] != 1) else str(r.u8())
        if k in ("ObjectProperty", "ClassProperty", "WeakObjectProperty", "LazyObjectProperty", "InterfaceProperty"):
            return r.fstr() or "None"
        if k in ("SoftObjectProperty", "SoftClassProperty"):
            if self.ue5 >= 1007:
                pkg, asset, subp = r.fstr(), r.fstr(), r.fstr()
                return f"{pkg}.{asset}" + (f":{subp}" if subp else "") if pkg else "None"
            path, subp = r.fstr(), r.fstr()
            return (path or "None") + (f":{subp}" if subp else "")
        if k == "TextProperty": return self.text(r)
        if k == "StructProperty": return self.struct(r, self.struct_name(typ), top)
        if k == "ArrayProperty": return self.array(r, typ[1][0])
        if k == "SetProperty":
            for _ in range(r.i32()):
                self.value(r, typ[1][0], elem=True)
            return "{" + ", ".join(self.value(r, typ[1][0], elem=True) for _ in range(r.i32())) + "}"
        if k == "MapProperty":
            kt, vt = typ[1][0], typ[1][1]
            for _ in range(r.i32()):
                self.value(r, kt, elem=True)
            n = r.i32()
            return {"__map__": [(self.value(r, kt, elem=True), self.value(r, vt, elem=True)) for _ in range(n)]}
        raise ValueError(f"type {k}")

    def struct(self, r, sname, top=None):
        fmt = self.native.get(sname)
        if fmt and (top is None or not self.full or top.get("native") or top["size"] == struct.calcsize("<" + fmt)):
            v = r.un(fmt)
            if sname == "Guid":
                return v[0].hex()
            return "(" + ", ".join(f"{x:.6g}" if isinstance(x, float) else str(x) for x in v) + ")"
        props = self.tagged(r)
        return "{" + ", ".join(f"{n}={fmt_inline(v)}" for n, v in props) + "}"

    def array(self, r, inner):
        n = r.i32()
        k = inner[0]
        if k == "ByteProperty" and (not inner[1] or inner[1][0][0] in ("None", "")):
            return f"<{n} bytes: {r.take(n)[:32].hex()}{'...' if n > 32 else ''}>"
        if k == "StructProperty" and not self.full:
            t = self.tag(r)                   # UE4 writes one inner tag for an array of structs
            inner = t["type"]
        return [self.value(r, inner, elem=True) for _ in range(n)]

    def text(self, r):
        r.un("I")
        h = r.un("b")[0]
        if h == -1:
            return json.dumps(r.fstr(), ensure_ascii=False) if r.i32() else '""'
        if h == 0:
            ns, key, src = r.fstr(), r.fstr(), r.fstr()
            return json.dumps(src, ensure_ascii=False) + f"  (text {ns}:{key})"
        if h == 11:
            table, key = r.fstr(), r.fstr()
            return f"ST[{table}:{key}]"
        raise ValueError(f"text history {h}")


def fmt_inline(v):
    if isinstance(v, dict) and "__map__" in v:
        return "{" + ", ".join(f"{a}: {fmt_inline(b)}" for a, b in v["__map__"]) + "}"
    if isinstance(v, list):
        return "[" + ", ".join(fmt_inline(x) for x in v) + "]"
    return str(v)


def write(s, rel, fo):
    fo.write(f"save {s.cls.split('.')[-1]}    ({rel}; UE {s.engine} {s.branch}, save v{s.sgv}, UE4 {s.ue4}"
             + (f", UE5 {s.ue5}" if s.ue5 else "") + ")\n")
    for name, v in s.props:
        if isinstance(v, dict) and "__map__" in v:
            fo.write(f"  {name}: {len(v['__map__'])} entries\n")
            for a, b in v["__map__"]:
                fo.write(f"    {a} = {fmt_inline(b)}\n")
        elif isinstance(v, list) and len(v) > 4:
            fo.write(f"  {name}: {len(v)} items\n")
            for x in v:
                fo.write(f"    {fmt_inline(x)}\n")
        else:
            fo.write(f"  {name} = {fmt_inline(v)}\n")


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if len(args) < 2:
        print(__doc__)
        return 2
    src, out = args
    files = [src] if os.path.isfile(src) else sorted(glob.glob(os.path.join(src, "**", "*.sav"), recursive=True))
    root = os.path.dirname(src) if os.path.isfile(src) else src
    stats = {"saves": 0, "clean": 0, "with_fallbacks": 0, "unreadable": 0, "trailing_not_4": 0}
    for f in files:
        rel = os.path.relpath(f, root).replace("\\", "/")
        try:
            s = Save(open(f, "rb").read())
        except Exception as e:  # noqa: BLE001
            stats["unreadable"] += 1
            sys.stderr.write(f"  {rel}: {e}\n")
            continue
        stats["saves"] += 1
        stats["clean" if not s.fallbacks else "with_fallbacks"] += 1
        if s.trailing != 4:
            stats["trailing_not_4"] += 1
        path = os.path.join(out, os.path.splitext(rel)[0] + ".txt")
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8", newline="\n") as fo:
            write(s, rel, fo)
    sys.stderr.write(" ".join(f"{k}={v}" for k, v in stats.items()) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
