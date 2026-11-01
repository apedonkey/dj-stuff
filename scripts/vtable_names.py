#!/usr/bin/env python3
"""Name the vtable slots of the engine classes Tribe's C++ derives from, from the UE 5.4 headers, and check each layout's
length against the vtable read from libUnreal.so (scripts/NativeTables.java's "context" lines).

    python -I scripts/vtable_names.py <UE Engine dir> <native_static.jsonl> <out.json> [SHIPPING|DEVELOPMENT]

Itanium C++ ABI, as clang lays it out: a class's primary vtable is its primary base's, then one slot per virtual it
declares (in declaration order) that doesn't override a primary-base virtual; overriding a secondary base's virtual
(IInterface_..., FExec) still takes a new primary slot; the first virtual destructor takes two (complete, deleting).
Preprocessor blocks are evaluated for an Android game build (WITH_EDITOR 0 ...). Writes {class: [slot names]} for every
class whose layout length matches the binary, plus the unmatched ones under "_unmatched" (lengths only).
"""
import json
import os
import re
import sys

MACROS = {"WITH_EDITOR": 0, "UE_ALLOW_EXEC_COMMANDS": 1, "WITH_EDITORONLY_DATA": 0, "WITH_ENGINE": 1, "WITH_SERVER_CODE": 1, "UE_SERVER": 0,
          "UE_EDITOR": 0, "UE_GAME": 1, "UE_BUILD_TEST": 0, "UE_BUILD_DEBUG": 0, "PLATFORM_ANDROID": 1,
          "PLATFORM_WINDOWS": 0, "PLATFORM_DESKTOP": 0, "WITH_HOT_RELOAD": 0, "WITH_RELOAD": 0, "WITH_LIVE_CODING": 0,
          "UE_WITH_IRIS": 1, "WITH_PUSH_MODEL": 1, "UE_WITH_REMOTE_OBJECT_HANDLE": 0, "WITH_ACCESSIBILITY": 1,
          "WITH_VERSE_VM": 0, "WITH_COREUOBJECT": 1, "WITH_STATE_STREAM": 0, "UE_WITH_CONSTINIT_UOBJECT": 0,
          "WITH_METADATA": 0, "WITH_TEXT_ARCHIVE_SUPPORT": 0, "WITH_EDITOR_ONLY_DATA": 0, "WITH_CHAOS": 1,
          "UE_ENABLE_INCLUDE_ORDER_DEPRECATED_IN_5_2": 0, "UE_ENABLE_INCLUDE_ORDER_DEPRECATED_IN_5_3": 0,
          "UE_ENABLE_INCLUDE_ORDER_DEPRECATED_IN_5_4": 0, "CPP": 1, "DO_CHECK": 1, "STATS": 0}
SHIPPING = {"UE_BUILD_SHIPPING": 1, "UE_BUILD_DEVELOPMENT": 0, "ENABLE_VISUAL_LOG": 0, "NO_LOGGING": 1}
DEVELOPMENT = {"UE_BUILD_SHIPPING": 0, "UE_BUILD_DEVELOPMENT": 1, "ENABLE_VISUAL_LOG": 1, "NO_LOGGING": 0}
SEARCH = ["Source/Runtime/CoreUObject", "Source/Runtime/Engine", "Source/Runtime/UMG", "Source/Runtime/Core/Public/Misc"]
unknown = set()
NEW_OVERRIDES = {}      # class -> override-marked declarations that took a new slot (secondary-base overrides, or key bugs)
# engine macros (defined outside the .generated.h) that declare virtuals in a class body, as what they declare
ENGINE_MACROS = {r"\bUE_FIELD_NOTIFICATION_DECLARE_CLASS_DESCRIPTOR(?:_BASE)?_END\s*\(\s*\)":
                 "; virtual const ::UE::FieldNotification::IClassDescriptor& GetFieldNotificationDescriptor() const;"}


def strip_comments(s):
    out, i, n = [], 0, len(s)
    while i < n:
        c = s[i]
        if c in "\"'":
            j = i + 1
            while j < n and s[j] != c:
                j += 2 if s[j] == "\\" else 1
            out.append(s[i:j + 1]); i = j + 1
        elif s.startswith("//", i):
            j = s.find("\n", i); i = n if j < 0 else j
        elif s.startswith("/*", i):
            j = s.find("*/", i + 2); out.append(" "); i = n if j < 0 else j + 2
        else:
            out.append(c); i += 1
    return "".join(out)


def cond_value(expr, mac):
    e = re.sub(r"defined\s*\(\s*(\w+)\s*\)|defined\s+(\w+)", lambda m: "1" if (m.group(1) or m.group(2)) in mac else "0", expr)

    def ident(m):
        w = m.group(0)
        if w in ("and", "or", "not"):
            return w
        if w not in mac:
            unknown.add(w)
        return str(int(mac.get(w, 0)))
    e = re.sub(r"\b[A-Za-z_]\w*\b", ident, e)
    e = e.replace("&&", " and ").replace("||", " or ").replace("!=", " __NE__ ").replace("!", " not ").replace(" __NE__ ", "!=")
    e = re.sub(r"(\d+)[uUlL]+", r"\1", e)
    try:
        return bool(eval(e, {"__builtins__": {}}))
    except Exception:
        return False


def preprocess(text, mac, defines=None):
    mac = dict(mac)
    lines = strip_comments(text.replace("\\\n", " ")).split("\n")
    out, stack = [], []          # stack of (active, taken, parent_active)
    for ln in lines:
        s = ln.strip()
        m = re.match(r"#\s*(\w+)\s*(.*)", s)
        active = all(a for a, _, _ in stack)
        if m:
            d, rest = m.group(1), m.group(2)
            if d in ("if", "ifdef", "ifndef"):
                v = cond_value(rest, mac) if d == "if" else ((rest.split()[0] in mac) if d == "ifdef" else (rest.split()[0] not in mac))
                stack.append((v and active, v, active)); continue
            if d == "elif":
                a, taken, pa = stack.pop(); v = (not taken) and cond_value(rest, mac)
                stack.append((v and pa, taken or v, pa)); continue
            if d == "else":
                a, taken, pa = stack.pop(); stack.append(((not taken) and pa, True, pa)); continue
            if d == "endif":
                if stack: stack.pop()
                continue
            if d == "define" and active:
                p = rest.split(None, 1)
                if defines is not None and p:
                    defines[p[0]] = p[1] if len(p) > 1 else ""
                if p and "(" not in p[0]:
                    try: mac[p[0]] = int(p[1].strip()) if len(p) > 1 else 1
                    except ValueError: mac[p[0]] = 1
            continue
        if active:
            out.append(ln)
    return "\n".join(out)


def find_class(engine, name, cache={}):
    if not cache:
        for sub in SEARCH:
            for root, _, files in os.walk(os.path.join(engine, sub)):
                for f in files:
                    if f.endswith(".h"):
                        p = os.path.join(root, f)
                        try: t = open(p, encoding="utf-8", errors="replace").read()
                        except OSError: continue
                        for m in re.finditer(r"\bclass\s+(?:[A-Z0-9_]+_API\s+)?(?:UE_DEPRECATED\([^)]*\)\s*)?(\w+)\s*(?:final\s*)?(?::\s*(?:public|private|protected)\s[^{;]*)?\{", t):
                            cache.setdefault(m.group(1), []).append(p)
    # every header that declares it (NoExportTypes.h fakes UObject for UHT), the one named after the class first
    return sorted(cache.get(name, []), key=lambda p: os.path.basename(p) != name[1:] + ".h")


def body_of(text, name):
    m = re.search(r"\bclass\s+(?:[A-Z0-9_]+_API\s+)?(?:UE_DEPRECATED\([^)]*\)\s*)?" + name + r"\s*(?:final\s*)?(?::([^{;]*))?\{", text)
    if not m:
        return None, []
    bases = [re.sub(r"\b(public|private|protected|virtual)\b", "", b).strip() for b in split_top(m.group(1) or "", ",")]
    i, depth = m.end(), 1
    j = i
    while j < len(text) and depth:
        depth += {"{": 1, "}": -1}.get(text[j], 0); j += 1
    return text[i:j - 1], [re.sub(r"<.*", "", b).split("::")[-1].strip() for b in bases if b]


def split_top(s, sep):
    parts, depth, cur = [], 0, []
    for c in s:
        if c in "(<[{": depth += 1
        elif c in ")>]}": depth -= 1
        if c == sep and depth == 0:
            parts.append("".join(cur)); cur = []
        else:
            cur.append(c)
    parts.append("".join(cur))
    return parts


def declarations(body):
    """top-level member declarations of a class body (inline bodies, nested types and brace initializers skipped)"""
    out, cur, i, n = [], [], 0, len(body)
    while i < n:
        c = body[i]
        if c == "{":
            j, d = i + 1, 1
            while j < n and d:
                d += {"{": 1, "}": -1}.get(body[j], 0); j += 1
            text = "".join(cur)
            if re.search(r"\)\s*(const|override|final|noexcept|\s)*$", text) and not re.match(r"\s*(class|struct|enum|union)\b", text):
                out.append(text); cur = []          # an inline function body ends the declaration
            i = j; continue
        if c == ";":
            out.append("".join(cur)); cur = []
        else:
            cur.append(c)
        i += 1
    res = []
    for d in out:
        d = re.sub(r"\b(public|protected|private)\s*:", " ", d)
        d = re.sub(r"\s+", " ", d).strip()
        if d:
            res.append(d)
    return res


TRAIL = re.compile(r"\s*(?:const|override|final|noexcept(?:\([^)]*\))?|=\s*0|=\s*default|=\s*delete|PURE_VIRTUAL\(.*\)|&|&&)\s*$")


def parse_virtual(d):
    """(name, param key, const, is_dtor) for a virtual member function declaration, else None"""
    if re.match(r"(friend|typedef|using|static)\b", d) or "operator" in d and "virtual" not in d:
        return None
    tail = d
    quals = []
    while True:
        m = TRAIL.search(tail)
        if not m or m.start() == len(tail):
            break
        quals.append(m.group(0).strip()); tail = tail[:m.start()]
    is_virtual = re.search(r"\bvirtual\b", d) is not None or any(q in ("override", "final") for q in quals)
    if not is_virtual or not tail.endswith(")"):
        return None
    depth, j = 0, len(tail) - 1
    while j >= 0:
        depth += {")": 1, "(": -1}.get(tail[j], 0)
        if depth == 0: break
        j -= 1
    params, head = tail[j + 1:-1], tail[:j].rstrip()
    m = re.search(r"(~?\w+|operator\s*\S+)$", head)
    if not m:
        return None
    name = m.group(1).replace(" ", "")
    return name, param_key(params), "const" in quals, name.startswith("~")


def param_key(params):
    keys = []
    for p in split_top(params, ","):
        p = split_top(p, "=")[0].strip()
        if not p or p == "void":
            continue
        toks = re.findall(r"::|\w+|[&*<>\[\](),]|\S", p)
        words = [t for t in toks if re.match(r"\w+$", t)]
        if len(words) >= 2 and re.match(r"\w+$", toks[-1]) and toks[-1] not in ("const", "int", "char", "long", "short", "double", "float", "bool"):
            toks = toks[:-1]
        # the same type, spelled differently: "class UCanvas*" = "UCanvas*", "FVector const&" = "const FVector&", and a
        # by-value parameter's own const isn't part of the signature
        toks = [t for t in toks if t not in ("class", "struct", "enum", "typename")]
        ind = next((i for i, t in enumerate(toks) if t in "*&"), len(toks))
        pointee_const = "const" in toks[:ind] and ind < len(toks)
        toks = (["const"] if pointee_const else []) + [t for t in toks if t != "const"]
        k = "".join(t if not re.match(r"\w+$", t) else " " + t + " " for t in toks)
        keys.append(re.sub(r"\s+", " ", k).replace(" :: ", "::").replace("< ", "<").replace(" >", ">").strip())
    return ",".join(keys)


def generated_body(engine, path, raw, name, mac):
    """UHT's GENERATED_BODY expansion for class name in header path (raw text), from <Header>.generated.h"""
    m = re.search(r"\bclass\s+(?:[A-Z0-9_]+_API\s+)?" + name + r"\b[^;{]*\{", raw)
    g = re.search(r"\b(GENERATED_BODY|GENERATED_UCLASS_BODY)\s*\(\s*\)", raw[m.end():]) if m else None
    if not g:
        return ""
    line = raw[:m.end() + g.start()].count("\n") + 1
    base = os.path.basename(path)[:-2] + ".generated.h"
    inc = os.path.join(engine, "Intermediate", "Build", "Win64", "UnrealEditor", "Inc")
    for mod in os.listdir(inc) if os.path.isdir(inc) else []:
        gp = os.path.join(inc, mod, "UHT", base)
        if not os.path.exists(gp):
            continue
        defs = {}
        preprocess(open(gp, encoding="utf-8", errors="replace").read(), mac, defs)
        want = [k for k in defs if re.search(r"_h_%d_GENERATED_BODY%s$" % (line, "_LEGACY" if g.group(1) == "GENERATED_UCLASS_BODY" else ""), k)]
        if not want:
            continue
        text = defs[want[0]]
        for _ in range(6):                       # expand the sub-macros (RPC_WRAPPERS_NO_PURE_DECLS, INCLASS ...)
            text = re.sub(r"\b[A-Za-z_]\w*\b", lambda t: " " + defs[t.group(0)] + " " if t.group(0) in defs else t.group(0), text)
        return text + ";"
    return ""


def layout(engine, name, mac, memo):
    """[(slot name, key)] for class name, recursively through its primary bases"""
    if name in memo:
        return memo[name]
    body = None
    for path in find_class(engine, name):
        raw = open(path, encoding="utf-8", errors="replace").read()
        body, bases = body_of(preprocess(raw, mac), name)
        if body is not None:
            gen = generated_body(engine, path, raw, name, mac)
            body = re.sub(r"\b(GENERATED_BODY|GENERATED_UCLASS_BODY)\s*\(\s*\)", lambda _: gen.replace("\\", " "), body, count=1)
            for pat, rep in ENGINE_MACROS.items():
                body = re.sub(pat, rep, body)
            break
    if body is None:
        memo[name] = None; return None
    base = layout(engine, bases[0], mac, memo) if bases else []
    if base is None:
        memo[name] = None; return None
    slots = list(base)
    have = {k for _, k in slots}
    has_dtor = any(k.startswith("~") for _, k in slots)
    for d in declarations(body):
        v = parse_virtual(d)
        if not v:
            continue
        fn, pk, const, dtor = v
        if dtor:
            if not has_dtor:
                slots += [(f"~{name} (complete)", "~"), (f"~{name} (deleting)", "~d")]; has_dtor = True
            continue
        key = f"{fn}({pk}){' const' if const else ''}"
        if key in have:
            continue
        if re.search(r"\boverride\b", d):
            NEW_OVERRIDES.setdefault(name, []).append(key)
        slots.append((fn, key)); have.add(key)
    memo[name] = slots
    return slots


def main():
    if len(sys.argv) < 4:
        print(__doc__); return 2
    engine, src, out = sys.argv[1], sys.argv[2], sys.argv[3]
    configs = [sys.argv[4].upper()] if len(sys.argv) > 4 else ["SHIPPING", "DEVELOPMENT"]
    recs = [json.loads(l) for l in open(src, encoding="utf-8")]
    ctx = {r["cpp"]: len(r["vtable"]) for r in recs if r.get("context")}
    obj = next((r for r in recs if r["class"] == "/Script/CoreUObject.Object"), None)
    best = None
    for cfg in configs:
        mac = dict(MACROS, **(SHIPPING if cfg == "SHIPPING" else DEVELOPMENT))
        memo, res, ok = {}, {}, 0
        for cpp, n in sorted(ctx.items()):
            lay = layout(engine, cpp, mac, memo)
            got = len(lay) if lay else None
            res[cpp] = (lay, n, got)
            ok += got == n
        print(f"{cfg}: {ok} of {len(ctx)} engine parents match the binary's vtable length")
        for cpp, (lay, n, got) in sorted(res.items()):
            print(f"  {'ok ' if got == n else 'BAD'} {cpp}: headers {got}, binary {n}")
        if best is None or ok > best[0]:
            best = (ok, cfg, res)
    ok, cfg, res = best
    names = {cpp: [s for s, _ in lay] for cpp, (lay, n, got) in res.items() if lay and got == n}
    if obj and "UObject" in names:                 # anchor: ProcessEvent (Ghidra 0x1957dd4 = rva 0x1858dd4, NOTES)
        i = names["UObject"].index("ProcessEvent") if "ProcessEvent" in names["UObject"] else -1
        print(f"anchor: ProcessEvent is slot {i}; the binary's UObject slot {i} = {obj['vtable'][i] if 0 <= i < len(obj['vtable']) else '-'} (want 0x1858dd4)")
    names["_config"] = cfg
    names["_unmatched"] = {cpp: [n, got] for cpp, (lay, n, got) in res.items() if not (lay and got == n)}
    json.dump(names, open(out, "w", encoding="utf-8"), indent=0)
    print(f"wrote {out} ({cfg}); macros the headers asked about that the table doesn't set: {sorted(unknown)[:40]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
