#!/usr/bin/env python3
"""Print Tribe's Blueprints as readable pseudo-code, from scripts/uasset_tool's `dump` JSON (UAssetAPI's
KismetSerializer: statements carry their bytecode offsets, names come resolved).

    python -I scripts/kismet_print.py <dump.json> [function ...]      the named functions, or all of them

Reading the output: `L123:` marks a jump target (the bytecode offset). `push L` / `pop` are a Sequence node's execution
flow (run what follows, then resume at L). Event graphs compile into one ExecuteUbergraph_<Class> function; each event
is a stub that jumps into it, so its entry is labelled `// event <Name>`. `self.X` is a member variable of the class.
"""
import json
import sys

FLOW = {"PushExecutionFlow", "PopExecutionFlow", "PopExecutionFlowIfNot", "Jump", "JumpIfNot", "ComputedJump"}
SKIP = {"EndOfScript", "Tracepoint", "WireTracepoint", "Nothing", "InstrumentationEvent", "Breakpoint"}
CPF_PARM, CPF_OUTPARM, CPF_RETURNPARM, CPF_REFERENCEPARM = 0x80, 0x100, 0x400, 0x8000000


def short(path):
    """'/Game/X/BP_Y.BP_Y_C' -> 'BP_Y_C'; '/Script/Engine.KismetSystemLibrary' -> 'KismetSystemLibrary'"""
    if not path:
        return "?"
    return str(path).split(".")[-1].split(":")[-1]


def num(v):
    if isinstance(v, str) and v.startswith("+"):
        v = v[1:]
    try:
        f = float(v)
        return str(int(f)) if f == int(f) and abs(f) < 1e15 else f"{f:.6g}"
    except (TypeError, ValueError):
        return str(v)


def ex(e, member=False):
    """an expression -> text"""
    if e is None:
        return "?"
    if not isinstance(e, dict):
        return str(e)
    i = e.get("Inst", "?")
    args = lambda key="Parameters": ", ".join(ex(p) for p in e.get(key) or [])
    if i in ("LocalVariable", "LocalOutVariable", "DefaultVariable"):
        return e.get("Variable Name", "?")
    if i == "InstanceVariable":
        return e.get("Variable Name", "?") if member else "self." + e.get("Variable Name", "?")
    if i == "Self":
        return "self"
    if i in ("Context", "ClassContext", "Context_FailSilent"):
        return f"{ex(e.get('Context'))}.{ex(e.get('Expression'), member=True)}"
    if i == "InterfaceContext":
        return ex(e.get("Expression"))
    if i == "StructMemberContext":
        return f"{ex(e.get('StructExpression'))}.{e.get('Property Name', '?')}"
    if i in ("LocalFinalFunction", "FinalFunction", "VirtualFunction"):
        return f"{e.get('Function', '?')}({args()})"
    if i == "LocalVirtualFunction":
        return f"{e.get('FunctionName', e.get('Function', '?'))}({args()})"
    if i == "CallMath":
        return f"{short(e.get('ContextClass'))}.{e.get('Function', '?')}({args()})"
    if i == "CallMulticastDelegate":
        return f"{ex(e.get('Delegate'))}.Broadcast({args()})"
    if i in ("IntConst", "Int64Const", "UInt64Const", "ByteConst", "IntConstByte", "FloatConst", "DoubleConst", "SkipOffsetConst"):
        return num(e.get("Value"))
    if i in ("StringConst", "UnicodeStringConst"):
        return json.dumps(e.get("Value", ""))
    if i == "NameConst":
        return f"'{e.get('Value')}'"
    if i == "TextConst":
        s = e.get("SourceString") or e.get("TableKey") or ""
        return f'Text({json.dumps(s)})'
    if i == "ObjectConst":
        return short(e.get("Object"))
    if i == "SoftObjectConst":
        return f"soft({ex(e.get('Value'))})"
    if i in ("True", "False"):
        return i.lower()
    if i in ("NoObject", "NoInterface"):
        return "None"
    if i == "IntZero":
        return "0"
    if i == "IntOne":
        return "1"
    if i == "Nothing":
        return ""
    if i == "VectorConst":
        return f"Vector({num(e.get('X'))}, {num(e.get('Y'))}, {num(e.get('Z'))})"
    if i == "RotationConst":
        return f"Rotator(P={num(e.get('Pitch'))}, Y={num(e.get('Yaw'))}, R={num(e.get('Roll'))})"
    if i == "TransformConst":
        return f"Transform({e.get('Translation')}, {e.get('Rotation')}, {e.get('Scale')})"
    if i == "StructConst":
        return f"{short(e.get('Struct'))}{{{', '.join(ex(p) for p in e.get('Properties') or [])}}}"
    if i in ("ArrayConst", "SetConst"):
        return f"[{', '.join(ex(p) for p in e.get('Values') or [])}]"
    if i == "MapConst":
        return "{" + ", ".join(f"{ex(kv.get('Key'))}: {ex(kv.get('Value'))}" for kv in e.get("Values") or []) + "}"
    if i in ("DynamicCast", "MetaCast"):
        return f"cast<{short(e.get('Class'))}>({ex(e.get('Expression'))})"
    if i in ("ObjToInterfaceCast", "CrossInterfaceCast"):
        return f"cast<{short(e.get('InterfaceClass'))}>({ex(e.get('Expression'))})"
    if i == "InterfaceToObjCast":
        return f"cast<{short(e.get('ObjectClass'))}>({ex(e.get('Expression'))})"
    if i == "PrimitiveCast":
        return f"{e.get('CastType', 'cast')}({ex(e.get('Expression'))})"
    if i == "ArrayGetByRef":
        return f"{ex(e.get('ArrayExpression'))}[{ex(e.get('IndexExpression'))}]"
    if i == "SwitchValue":
        cases = "; ".join(f"{ex(c.get('CaseValue'))}: {ex(c.get('CaseResult'))}" for c in e.get("Cases") or [])
        return f"switch({ex(e.get('Expression'))}) {{{cases}; default: {ex(e.get('DefaultResult'))}}}"
    if i == "BindDelegate":
        return f"bind({ex(e.get('Delegate'))} -> {ex(e.get('Object'))}.{e.get('FunctionName')})"
    if i == "InstanceDelegate":
        return f"delegate({e.get('FunctionName')})"
    if i == "FieldPathConst":
        return f"field({ex(e.get('Expression'))})"
    return f"<{i} {json.dumps({k: v for k, v in e.items() if k not in ('Inst', 'StatementIndex')})[:80]}>"


def stmt(e):
    """a top-level statement -> text, or None for markers"""
    i = e.get("Inst", "?")
    if i in SKIP:
        return None
    if i in ("Let", "LetObj", "LetBool", "LetWeakObjPtr", "LetDelegate", "LetMulticastDelegate"):
        return f"{ex(e.get('Variable'))} = {ex(e.get('Expression'))}"
    if i == "LetValueOnPersistentFrame":
        return f"{e.get('Property Name', '?')} = {ex(e.get('Expression'))}"
    if i == "Jump":
        return f"goto L{e.get('Offset')}"
    if i == "JumpIfNot":
        return f"if not {ex(e.get('Condition'))}: goto L{e.get('Offset')}"
    if i == "PushExecutionFlow":
        return f"push L{e.get('Offset')}"
    if i == "PopExecutionFlow":
        return "pop"
    if i == "PopExecutionFlowIfNot":
        return f"if not {ex(e.get('Condition'))}: pop"
    if i == "ComputedJump":
        return f"goto *{ex(e.get('OffsetExpression'))}"
    if i == "Return":
        r = ex(e.get("Expression"))
        return "return" + (f" {r}" if r else "")
    if i in ("AddMulticastDelegate", "RemoveMulticastDelegate"):
        op = "+=" if i.startswith("Add") else "-="
        return f"{ex(e.get('MulticastDelegate'))} {op} {ex(e.get('Delegate'))}"
    if i == "ClearMulticastDelegate":
        return f"{ex(e.get('MulticastDelegate'))}.Clear()"
    if i in ("SetArray", "SetSet", "SetMap"):
        vals = e.get("Values") or []
        body = ", ".join(f"{ex(v.get('Key'))}: {ex(v.get('Value'))}" if isinstance(v, dict) and "Key" in v else ex(v) for v in vals)
        return f"{ex(e.get('LeftSideExpression'))} = [{body}]"
    if i == "Assert":
        return f"assert {ex(e.get('Expression'))}"
    return ex(e)


def signature(f):
    params, ret = [], None
    for p in f.get("props") or []:
        fl = int(p.get("flags", 0))
        if not fl & CPF_PARM:
            continue
        if fl & CPF_RETURNPARM:
            ret = p["type"]
        else:
            out = "out " if fl & CPF_OUTPARM and not fl & CPF_REFERENCEPARM else ("ref " if fl & CPF_REFERENCEPARM else "")
            params.append(f"{out}{p['name']}: {p['type']}")
    return f"{f['name']}({', '.join(params)})" + (f" -> {ret}" if ret else "")


def entry_points(dump):
    """ubergraph offset -> event name, from the stubs that call ExecuteUbergraph_<Class>(N)"""
    eps = {}
    for f in dump["exports"]:
        if f.get("type") != "FunctionExport" or f["name"].startswith("ExecuteUbergraph"):
            continue
        for s in f.get("code") or []:
            if s.get("Inst") in ("LocalFinalFunction", "FinalFunction") and str(s.get("Function", "")).startswith("ExecuteUbergraph"):
                ps = s.get("Parameters") or []
                if ps and ps[0].get("Inst") == "IntConst":
                    eps[int(num(ps[0]["Value"]))] = f["name"]
    return eps


def calls(code):
    """every function name called anywhere in a function's code (for summaries)"""
    out = []

    def walk(e):
        if isinstance(e, dict):
            i = e.get("Inst")
            if i in ("LocalFinalFunction", "FinalFunction", "VirtualFunction", "CallMath"):
                out.append(str(e.get("Function")))
            elif i == "LocalVirtualFunction":
                out.append(str(e.get("FunctionName", e.get("Function"))))
            for v in e.values():
                walk(v)
        elif isinstance(e, list):
            for v in e:
                walk(v)
    walk(code)
    return out


def print_function(f, eps=None, out=sys.stdout):
    flags = f.get("fflags", "")
    tags = [t for t in ("Event", "Net", "NetMulticast", "NetServer", "NetClient", "Static", "BlueprintPure") if f"FUNC_{t}," in flags + ","]
    out.write(f"\nfunction {signature(f)}" + (f"   [{' '.join(tags)}]" if tags else "") + "\n")
    code = f.get("code") or []
    if "codeError" in f:
        out.write(f"    (not decoded: {f['codeError']})\n")
        return
    targets = {int(s["Offset"]) for s in code if s.get("Inst") in ("Jump", "JumpIfNot", "PushExecutionFlow") and "Offset" in s}
    eps = eps or {}
    for s in code:
        idx = s.get("StatementIndex")
        if idx in eps:
            out.write(f"  L{idx}:   // event {eps[idx]}\n")
        elif idx in targets:
            out.write(f"  L{idx}:\n")
        t = stmt(s)
        if t is not None:
            out.write(f"    {t}\n")


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    dump = json.load(open(sys.argv[1], encoding="utf-8"))
    want = set(sys.argv[2:])
    eps = entry_points(dump)
    funcs = [e for e in dump["exports"] if e.get("type") == "FunctionExport" and (not want or e["name"] in want)]
    cls = next((e for e in dump["exports"] if e.get("type") == "ClassExport"), None)
    if cls:
        sys.stdout.write(f"class {cls['name']} : {short(cls.get('super'))}    ({dump['asset']})\n")
    for f in sorted(funcs, key=lambda f: (f["name"].startswith("ExecuteUbergraph"), f["name"])):
        print_function(f, eps if f["name"].startswith("ExecuteUbergraph") else None)
    return 0


if __name__ == "__main__":
    sys.exit(main())
