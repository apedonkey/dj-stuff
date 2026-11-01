#!/usr/bin/env python3
"""Every dumped Tribe package as readable text, from scripts/uasset_tool's `dump` JSON: Blueprint classes as
pseudo-code (the same format scripts/deck_catalog.py writes for the equipment), plus user structs, user enums, data
table rows, and each level's placed actors with their positions.

    python -I scripts/code_print.py <dump dir> <code dir> [--keep]

One <code dir>/<path under the dump dir>.txt per package. --keep leaves files that already exist untouched (to add
the tables, structs and enums beside pseudo-code written earlier without rewriting it). Positions are the root
component's relative location in cm (x, y, z), rotation as (pitch, yaw, roll) degrees.
"""
import glob
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import kismet_print as kp  # noqa: E402

GUID_TAIL = re.compile(r"_\d+_[0-9A-F]{32}$")


def clean(name):
    """a user struct's member 'SkinInfo_37_D88F...' -> 'SkinInfo'"""
    return GUID_TAIL.sub("", str(name))


def ref(d, idx):
    """an object reference (import < 0, export > 0) -> its path or export name"""
    if not isinstance(idx, int) or idx == 0:
        return "None"
    if idx < 0:
        return next((i["path"] for i in d["imports"] if i["i"] == idx), f"import{idx}")
    return d["exports"][idx - 1]["name"] if idx - 1 < len(d["exports"]) else f"export{idx}"


def kind(p):
    t = p.get("$type", "") if isinstance(p, dict) else ""
    return t.split(",")[0].split(".")[-1].replace("PropertyData", "")


def val(d, p, depth=0):
    """a UAssetAPI property (as JSON) -> short text"""
    if depth > 12:
        return "..."
    if not isinstance(p, dict):
        return json.dumps(p, default=str) if not isinstance(p, str) else p
    k, v = kind(p), p.get("Value")
    if k == "Struct":
        if isinstance(v, list) and len(v) == 1 and kind(v[0]) not in ("Struct", ""):
            inner = v[0]
            if kind(inner) in ("Vector", "Rotator", "Vector2D", "Vector4", "Quat", "LinearColor", "Color", "IntPoint"):
                return val(d, inner, depth + 1)
        if isinstance(v, list):
            return "{" + ", ".join(f"{clean(x.get('Name'))}={val(d, x, depth + 1)}" for x in v if isinstance(x, dict)) + "}"
    if k in ("Array", "Set"):
        return "[" + ", ".join(val(d, x, depth + 1) for x in (v or [])) + "]"
    if k == "Map":
        if isinstance(v, list):
            return "{" + ", ".join(f"{val(d, kv[0], depth + 1)}: {val(d, kv[1], depth + 1)}" for kv in v
                                   if isinstance(kv, list) and len(kv) == 2) + "}"
        return json.dumps(v, default=str)[:200]
    if k in ("Object", "WeakObject", "LazyObject", "Interface"):
        return ref(d, v)
    if k in ("SoftObject", "SoftClass", "SoftObjectPath", "SoftClassPath"):
        ap = (v or {}).get("AssetPath", {}) if isinstance(v, dict) else {}
        pkg, asset = ap.get("PackageName"), ap.get("AssetName")
        return f"{pkg}.{asset}" if pkg else "None"
    if k == "Text":
        if p.get("HistoryType") == "StringTableEntry":
            return f"ST[{p.get('TableId')}:{v}]"
        return json.dumps(v if v is not None else p.get("CultureInvariantString"), default=str)
    if k in ("Vector", "Vector2D", "Vector4", "Rotator", "Quat", "IntPoint"):
        if isinstance(v, dict):
            keys = [c for c in ("X", "Y", "Z", "W", "Pitch", "Yaw", "Roll") if c in v]
            return "(" + ", ".join(kp.num(v[c]) for c in keys) + ")"
    if k in ("LinearColor", "Color"):
        if isinstance(v, dict):
            return "rgba(" + ", ".join(kp.num(v.get(c)) for c in ("R", "G", "B", "A")) + ")"
    if k in ("Str", "Name", "Enum", "Byte"):
        return json.dumps(v, default=str) if k == "Str" else str(v)
    if k in ("Float", "Double", "Int", "Int8", "Int16", "Int64", "UInt16", "UInt32", "UInt64"):
        return kp.num(v)
    if k == "Bool":
        return "true" if v else "false"
    s = json.dumps(v, default=str)
    return s if len(s) <= 200 else s[:200] + "..."


def props(e):
    return {x.get("Name"): x for x in (e.get("data") or []) if isinstance(x, dict)}


def write_class(d, ce, fo):
    eps = kp.entry_points(d)
    fo.write(f"class {ce['name']} : {kp.short(ce.get('super'))}    ({d['asset']})\n")
    for p in ce.get("props") or []:
        fo.write(f"  var {p['name']}: {p['type']}\n")
    funcs = [e for e in d["exports"] if e.get("type") == "FunctionExport"]
    for f in sorted(funcs, key=lambda f: (f["name"].startswith("ExecuteUbergraph"), f["name"])):
        kp.print_function(f, eps if f["name"].startswith("ExecuteUbergraph") else None, fo)
    return len(funcs)


def write_actors(d, fo):
    """a level's placed actors (outer = the PersistentLevel export), with the root component's transform"""
    lvl = next((e for e in d["exports"] if e.get("class") == "Level"), None)
    if not lvl:
        return 0
    actors = [e for e in d["exports"] if e.get("outer") == lvl["i"]]
    fo.write(f"\nlevel {d['asset']}: {len(actors)} placed actors\n")
    for a in actors:
        line = f"  actor {a['name']}: {a['class']}"
        rc = props(a).get("RootComponent")
        if rc and isinstance(rc.get("Value"), int) and rc["Value"] > 0:
            c = props(d["exports"][rc["Value"] - 1])
            for key, label in (("RelativeLocation", "at"), ("RelativeRotation", "rot"), ("RelativeScale3D", "scale")):
                if key in c:
                    line += f"  {label} {val(d, c[key])}"
        fo.write(line + "\n")
    return len(actors)


def write_struct(d, e, fo):
    fo.write(f"struct {e['name']}    ({d['asset']})\n")
    for p in e.get("props") or []:
        fo.write(f"  {clean(p['name'])}: {p['type']}" + (f"    // {p['name']}" if clean(p['name']) != p['name'] else "") + "\n")


def write_enum(d, e, fo):
    shown = {}
    dn = props(e).get("DisplayNameMap")
    if dn and isinstance(dn.get("Value"), list):
        for kv in dn["Value"]:
            if isinstance(kv, list) and len(kv) == 2:
                shown[str(kv[0].get("Value"))] = val(d, kv[1])
    fo.write(f"enum {e['name']}    ({d['asset']})\n")
    for n, v in e.get("enum") or []:
        short_n = str(n).split("::")[-1]
        label = shown.get(short_n) or shown.get(str(n))
        fo.write(f"  {short_n} = {v}" + (f"    // {label}" if label else "") + "\n")


def write_table(d, e, fo):
    rows = e.get("rows") or []
    st = rows[0].get("StructType") if rows and isinstance(rows[0], dict) else "?"
    fo.write(f"table {e['name']}: {len(rows)} rows of {st}    ({d['asset']})\n")
    for r in rows:
        if isinstance(r, dict):
            fields = ", ".join(f"{clean(x.get('Name'))}={val(d, x)}" for x in (r.get("Value") or []) if isinstance(x, dict))
            fo.write(f"  row {r.get('Name')}: {fields}\n")


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    keep = "--keep" in sys.argv
    if len(args) < 2:
        print(__doc__)
        return 2
    root, out = args
    counts = {"class": 0, "functions": 0, "level": 0, "struct": 0, "enum": 0, "table": 0, "kept": 0, "skipped": 0}
    for f in sorted(glob.glob(os.path.join(root, "**", "*.json"), recursive=True)):
        d = json.load(open(f, encoding="utf-8"))
        rel = os.path.splitext(d["asset"])[0]
        path = os.path.join(out, rel + ".txt")
        if keep and os.path.exists(path):
            counts["kept"] += 1
            continue
        ce = next((e for e in d["exports"] if e.get("type") == "ClassExport"), None)
        main_e = next((e for e in d["exports"] if e["name"] == os.path.basename(rel)), None)
        is_level = any(e.get("class") == "Level" for e in d["exports"])
        if not ce and not is_level and (main_e is None or d["class"] not in ("UserDefinedStruct", "UserDefinedEnum", "DataTable")):
            counts["skipped"] += 1          # skeletons and skeletal meshes: data for scripts/deck_catalog.py
            continue
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8", newline="\n") as fo:
            if ce:
                counts["functions"] += write_class(d, ce, fo)
                counts["class"] += 1
            if is_level:
                write_actors(d, fo)
                counts["level"] += 1
            if not ce and not is_level:
                if d["class"] == "UserDefinedStruct":
                    write_struct(d, main_e, fo); counts["struct"] += 1
                elif d["class"] == "UserDefinedEnum":
                    write_enum(d, main_e, fo); counts["enum"] += 1
                else:
                    write_table(d, main_e, fo); counts["table"] += 1
    sys.stderr.write(" ".join(f"{k}={v}" for k, v in counts.items()) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
