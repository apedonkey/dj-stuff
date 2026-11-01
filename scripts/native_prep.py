#!/usr/bin/env python3
"""Turn the hook's native dump (tribemod/native_dump.jsonl, hook/native.cpp) into scripts/NativeDecomp.java's work
list, and a reference of Tribe's C++ classes.

    python -I scripts/native_prep.py <native_dump.jsonl> <work.tsv> <classes.json> [slot_names.json] [--static <s.jsonl>]

--static merges scripts/NativeTables.java's read of the binary: the hook's vtable read runs 2-3 entries past the end
for most classes (into the class registration record that follows the vtable), so a runtime vtable that starts with
the static one is cut to it, and classes only the static read has (modules the dump didn't ask for) are added.

Work list lines: <group> <kind> <label> <rva> <impl label>, tab-separated. kind thunk: every native UFunction's exec
thunk (FUNC_Native 0x400, UFunction::Func). kind vfunc: every vtable entry a class changes from its parent's
(the parent is the class above it in the dump, a Tribe class or the engine class it derives from, which the dump
carries as a vtable-only "context" record); entries past the parent's vtable are new virtuals. With slot_names.json
(scripts/vtable_names.py: the engine classes' slots, from the UE headers) an override is labelled with the engine
virtual it replaces (<Class>::BeginPlay), and a slot past the engine class's with the Tribe class that added it
(<Class>::<Parent>_NewVirtual<slot>).
"""
import json
import sys

FUNC_NATIVE, FUNC_EVENT, FUNC_NET, FUNC_DELEGATE = 0x400, 0x800, 0x40, 0x100000


def short(path):
    return path.split(".")[-1] if path else ""


def main():
    args = sys.argv[1:]
    static = None
    if "--static" in args:
        i = args.index("--static"); static = args[i + 1]; del args[i:i + 2]
    if len(args) < 3:
        print(__doc__)
        return 2
    recs = [json.loads(l) for l in open(args[0], encoding="utf-8") if l.strip()]
    if static:
        st = {r["class"]: r for r in (json.loads(l) for l in open(static, encoding="utf-8") if l.strip())}
        have, cut, odd = {r["class"] for r in recs}, 0, []
        for r in recs:
            s = st.get(r["class"])
            if s and s["vtable"] and r["vtable"][:len(s["vtable"])] == s["vtable"]:
                cut += len(r["vtable"]) != len(s["vtable"]); r["vtable"] = s["vtable"]
            elif s:
                odd.append(short(r["class"]))
        added = [s for k, s in st.items() if k not in have]
        recs += added
        print(f"static read: {cut} runtime vtables cut to the static length, {len(odd)} that don't start with it {odd[:5]}, "
              f"{len(added)} classes added from it")
    by = {r["class"]: r for r in recs}
    slots = json.load(open(args[3], encoding="utf-8")) if len(args) > 3 else {}
    by_short = {k[1:]: v for k, v in slots.items() if not k.startswith("_")}   # AActor -> Actor (the runtime dump has no prefix)

    def slot_name(r, i):
        """what vtable slot i of class r is: the engine virtual, or the Tribe class that introduced it"""
        chain, c = [], r
        while c and not c.get("context"):
            chain.append(c); c = by.get(c["super"])
        eng = by_short.get(short(c["class"])) if c else None
        if eng and i < len(eng):
            n = eng[i]
            return ("DeletingDestructor" if "deleting" in n else "Destructor") if n.startswith("~") else n
        intro = next((x for x in reversed(chain) if i < len(x["vtable"])), r)
        return f"NewVirtual{i}" if intro is r else f"{short(intro['class'])}_NewVirtual{i}"
    work, classes = [], []
    seen = set()
    for r in recs:
        if r.get("context"):
            continue
        cls = short(r["class"])
        group = r["class"].replace("/Script/", "").replace(":", ".")
        sup = by.get(r["super"])
        pvt = sup["vtable"] if sup else []
        overrides = []
        for i, e in enumerate(r["vtable"]):
            if i < len(pvt) and pvt[i] == e:
                continue
            overrides.append(i)
            if (group, e) not in seen:
                seen.add((group, e))
                label = f"{cls}::{slot_name(r, i)}" if slots else (f"{cls}::vfunc{i}" if i < len(pvt) else f"{cls}::newvirtual{i}")
                work.append((group, "vfunc", label, e, ""))
        funcs = []
        for f in r["functions"]:
            fl = int(f["flags"], 16)
            funcs.append({"name": f["name"], "flags": f["flags"], "native": bool(fl & FUNC_NATIVE), "func": f["func"],
                          "params": f["params"]})
            if fl & FUNC_NATIVE and int(f["func"], 16):
                work.append((group, "thunk", f"{cls}::exec{f['name']}", f["func"], f"{cls}::{f['name']}"))
        classes.append({"class": r["class"], "super": r["super"], "size": r["size"], "vtable_len": len(r["vtable"]),
                        "parent_vtable_len": len(pvt), "parent_in_dump": bool(sup), "overrides": overrides,
                        "override_names": [slot_name(r, i) for i in overrides] if slots else [],
                        "static": bool(r.get("static")), "functions": funcs})
    with open(args[1], "w", encoding="utf-8", newline="\n") as fo:
        for w in work:
            fo.write("\t".join(w) + "\n")
    json.dump(classes, open(args[2], "w", encoding="utf-8"), indent=1)
    nt = sum(1 for w in work if w[1] == "thunk")
    print(f"{len(classes)} classes ({sum(1 for r in recs if r.get('context'))} engine parents for comparison); "
          f"{nt} native thunks, {len(work) - nt} vtable overrides; "
          f"{sum(1 for c in classes if not c['parent_in_dump'])} classes without their parent's vtable")
    return 0


if __name__ == "__main__":
    sys.exit(main())
