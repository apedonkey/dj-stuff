#!/usr/bin/env python3
"""Write claudedocs/native_reference.md: Tribe's own C++ classes (TribeXR, TribeIntonal, SuperPowered) with their data
members, functions, C++ overrides and where Ghidra's decompile of each is.

    python -I scripts/native_reference.py <classes.json> <TribeXR.usmap> <decompile dir> <out.md> [summary.md]

classes.json is scripts/native_prep.py's output (from the hook's native dump, or scripts/NativeTables.java's static
read of libUnreal.so: no parameters or flags, shown as (…)); the usmap supplies each class's data
members (the runtime dump of hook/usmap.cpp, version 4); the decompile dir holds scripts/NativeDecomp.java's
<Module>.<Class>.c files. summary.md, if given, is pasted in after the introduction (hand-written findings).
"""
import json
import os
import struct
import sys

FUNC = [(0x400, "native"), (0x800, "event"), (0x2000, "static"), (0x4000, "multicast RPC"), (0x200000, "server RPC"),
        (0x1000000, "client RPC"), (0x4000000, "Blueprint-callable"), (0x10000000, "pure"), (0x8000000, "Blueprint event"),
        (0x100000, "delegate")]
CPF_PARM, CPF_OUT, CPF_RET, CPF_REF = 0x80, 0x100, 0x400, 0x8000000


def read_usmap(path):
    """{struct name: (super, [(name, type text)])} from a version 3/4 .usmap (hook/usmap_writer.h's layout)"""
    b = open(path, "rb").read()
    p = 0

    def rd(fmt):
        nonlocal p
        v = struct.unpack_from("<" + fmt, b, p)
        p += struct.calcsize("<" + fmt)
        return v if len(v) > 1 else v[0]
    assert rd("H") == 0x30C4
    ver = rd("B")
    rd("i"); rd("B"); rd("I"); rd("I")
    names = []
    for _ in range(rd("I")):
        n = rd("H")
        names.append(b[p:p + n].decode("utf-8", "replace"))
        p += n

    def nm():
        i = rd("i")
        return None if i < 0 else names[i]
    kinds = ["Byte", "Bool", "Int", "Float", "Object", "Name", "Delegate", "Double", "Array", "Struct", "Str", "Text",
             "Interface", "MulticastDelegate", "WeakObject", "LazyObject", "AssetObject", "SoftObject", "UInt64",
             "UInt32", "UInt16", "Int64", "Int16", "Int8", "Map", "Set", "Enum", "FieldPath", "Optional", "Utf8Str", "AnsiStr"]

    def ty():
        k = rd("B")
        if k == 26:
            inner = ty()
            return f"Enum({nm()})" if inner == "Byte" else f"Enum({nm()}:{inner})"
        if k == 9:
            return f"Struct({nm()})"
        if k in (8, 25, 28):
            return f"{kinds[k]}<{ty()}>"
        if k == 24:
            a = ty()
            return f"Map<{a},{ty()}>"
        return kinds[k] if k < len(kinds) else "Unknown"
    for _ in range(rd("I")):
        nm()
        n = rd("H")
        for _ in range(n):
            if ver >= 4:
                rd("q")
            nm()
    out = {}
    for _ in range(rd("I")):
        name, sup = nm(), nm()
        rd("H")
        props = []
        for _ in range(rd("H")):
            rd("H")
            dim = rd("B")
            pn = nm()
            props.append((pn + (f"[{dim}]" if dim > 1 else ""), ty()))
        out[name] = (sup, props)
    return out


def short(path):
    return path.split(".")[-1] if path else ""


def sig(f):
    if f.get("params") is None:                  # read statically: only the runtime dump has parameters
        return f"{f['name']}(…)"
    ps, ret = [], None
    for name, t, fl in f["params"]:
        fl = int(fl, 16)
        if not fl & CPF_PARM:
            continue
        if fl & CPF_RET:
            ret = t
        else:
            ps.append(("out " if fl & CPF_OUT and not fl & CPF_REF else "ref " if fl & CPF_REF else "") + f"{name}: {t}")
    return f"{f['name']}({', '.join(ps)})" + (f" -> {ret}" if ret else "")


def tags(f):
    fl = int(f["flags"], 16)
    return ", ".join(t for bit, t in FUNC if fl & bit) or "-"


def main():
    if len(sys.argv) < 5:
        print(__doc__)
        return 2
    classes = json.load(open(sys.argv[1], encoding="utf-8"))
    schemas = read_usmap(sys.argv[2])
    ddir, out = sys.argv[3], sys.argv[4]
    summary = open(sys.argv[5], encoding="utf-8").read() if len(sys.argv) > 5 else ""
    def only_static(c):                          # no parameters known for this class's functions
        return c.get("static", True) and all(f.get("params") is None for f in c["functions"])
    from_dump = sorted({c["class"].split(".")[0].replace("/Script/", "") for c in classes if not only_static(c)})
    L = ["# Tribe XR's C++: class reference\n",
         "Tribe's own native modules in `libUnreal.so` (build 2304). The classes, their native function tables and their "
         "vtables are read from the binary (`scripts/NativeTables.java`): each class's registration call gives its package, "
         "name, size, constructor and parent, `StaticRegisterNatives` gives each UFunction's exec thunk, and the "
         "constructor gives the vtable. Engine virtual names come from the UE 5.4 headers (`scripts/vtable_names.py`, "
         "checked against the binary's vtable lengths). Data members come from the runtime type dump (`TribeXR.usmap`). "
         "Ghidra decompiled each exec thunk, the implementation behind it and every vtable entry a class overrides into "
         "one `.c` file per class under `D:/TribeUE/tribe_native/classes/` (`scripts/NativeDecomp.java`).\n"]
    if from_dump:
        L.append(f"Parameters and function flags for {', '.join(f'`{m}`' for m in from_dump)} come from the hook's runtime "
                 "dump (`hook/native.cpp`), which also lists the functions the C++ declares and Blueprints implement (no "
                 "\"native\" in their kind). Classes the dump didn't cover show their functions as `(…)`.\n")
    else:
        L.append("Parameter lists and function flags need the runtime dump (`hook/native.cpp`); until then functions show "
                 "as `(…)`, and Blueprint events the C++ declares but doesn't implement aren't listed.\n")
    if summary:
        L.append(summary.rstrip() + "\n")
    mods = {}
    for c in classes:
        mods.setdefault(c["class"].split(".")[0].replace("/Script/", ""), []).append(c)
    L.append("## Modules\n")
    L.append("| Module | Classes | Functions | Native | C++ overrides |\n|---|---|---|---|---|")
    for m, cs in mods.items():
        nf = sum(len(c["functions"]) for c in cs)
        L.append(f"| {m} | {len(cs)} | {nf} | {sum(f['native'] for c in cs for f in c['functions'])} | {sum(len(c['overrides']) for c in cs)} |")
    L.append("")
    for m, cs in mods.items():
        L.append(f"## {m}\n")
        L.append("| Class | Parent | Data members | Functions | Overrides | Decompiled |\n|---|---|---|---|---|---|")
        for c in sorted(cs, key=lambda c: short(c["class"])):
            n = short(c["class"])
            props = schemas.get(n, (None, []))[1]
            f = f"{c['class'].replace('/Script/', '').replace(':', '.')}.c"
            have = os.path.exists(os.path.join(ddir, f))
            L.append(f"| [{n}](#{n.lower()}) | {short(c['super'])} | {len(props)} | {len(c['functions'])} | {len(c['overrides'])} | "
                     f"{'`' + f + '`' if have else '-'} |")
        L.append("")
        for c in sorted(cs, key=lambda c: short(c["class"])):
            n = short(c["class"])
            props = schemas.get(n, (None, []))[1]
            L.append(f"### {n}\n")
            L.append(f"`{c['class']}` : `{short(c['super'])}`, {c['size']} bytes; vtable {c['vtable_len']} entries, "
                     f"{len(c['overrides'])} overridden or new" + ("" if c["parent_in_dump"] else " (parent's vtable not in the dump)") + ".\n")
            if props:
                L.append("Data members: " + ", ".join(f"`{p}`: {t}" for p, t in props) + ".\n")
            if c["functions"] and only_static(c):
                L.append(f"Native functions ({len(c['functions'])}): "
                         + ", ".join(f"`{fn['name']}`" for fn in sorted(c["functions"], key=lambda f: f["name"].lower())) + ".\n")
            elif c["functions"]:
                L.append("| Function | Kind |\n|---|---|")
                for fn in sorted(c["functions"], key=lambda f: f["name"].lower()):
                    L.append(f"| `{sig(fn)}` | {tags(fn)} |")
                L.append("")
            if c.get("override_names"):
                L.append("C++ overrides: " + ", ".join(f"`{n}`" for n in c["override_names"]) + ".\n")
            elif c["overrides"]:
                L.append("Overridden vtable slots: " + ", ".join(str(i) for i in c["overrides"]) + ".\n")
    open(out, "w", encoding="utf-8", newline="\n").write("\n".join(L))
    print(f"wrote {out}: {len(classes)} classes in {len(mods)} modules")
    return 0


if __name__ == "__main__":
    sys.exit(main())
