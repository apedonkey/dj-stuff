#!/usr/bin/env python3
"""Catalogue Tribe XR's menus button by button, from scripts/uasset_tool's `dump` JSON of the menu widgets.

    python -I scripts/menu_catalog.py <dump root> <string table dir> <out.md> <out.json> [folder ...]

Folders default to Menus, TrackManager and MusicServices (under the dump root). For every widget Blueprint: its
controls (buttons, checkboxes, sliders, text boxes, combo boxes and Tribe's own button widgets) with their label (the
text inside them, a Tribe widget's own label property, or a string table entry), each event bound to them (in the
designer or with `+=` in the graph) and what that event does: the calls reached by following the event graph from
the event's entry through its jumps, branches and sequences, with the Blueprint's own functions expanded a level.
Cosmetic calls (visibility, text, colour, sounds, animations) and plain getters are left out. The 3D menu actors list
the widget each of their panels shows, and every widget lists the panels it embeds and the widgets it creates.
"""
import csv
import glob
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import kismet_print as kp  # noqa: E402

CONTROLS = {"Button", "CheckBox", "Slider", "SpinBox", "ComboBoxString", "ComboBoxKey", "EditableTextBox",
            "EditableText", "MultiLineEditableTextBox", "MultiLineEditableText"}
CALLS = ("LocalFinalFunction", "FinalFunction", "VirtualFunction", "LocalVirtualFunction", "CallMath")
LIBS = ("KismetMathLibrary", "KismetStringLibrary", "KismetTextLibrary", "KismetArrayLibrary", "BlueprintSetLibrary",
        "BlueprintMapLibrary", "KismetInputLibrary", "KismetNodeHelperLibrary", "KismetGuidLibrary", "SlateBlueprintLibrary",
        "WidgetLayoutLibrary", "KismetRenderingLibrary", "NetPushModelHelpers")
KEEP_SYSTEM = {"LaunchURL", "QuitGame", "ExecuteConsoleCommand", "OpenLevel", "Create"}
GETTER = re.compile(r"^(Get|Is|Has|Can|Should|Find|Make|Break|Conv_|Equal|NotEqual|Not_|Select|Array_|Map_|Set_Contains|"
                    r"Contains|Num|Length|Len|Less|Greater|Boolean|Concat|Format|Join|Split|Parse|Clamp|Lerp|"
                    r"Percent|Round|Floor|Truncate|ToString|Print|Delay|RetriggerableDelay|K2_GetComponent|IsValid)")
NOISE = {"SetVisibility", "SetText", "SetColorAndOpacity", "SetRenderOpacity", "SetBrush", "SetBrushFromTexture",
         "SetBrushFromMaterial", "SetBrushTintColor", "SetBrushColor", "SetBackgroundColor", "SetContentColorAndOpacity",
         "SetRenderTransform", "SetRenderTransformAngle", "SetRenderScale", "SetRenderTranslation", "SetPadding",
         "SetFont", "SetJustification", "SetToolTipText", "SetStyle", "SetWidgetStyle", "PlaySound2D", "PlaySound",
         "PlayAnimation", "PlayAnimationForward", "PlayAnimationReverse", "StopAnimation", "StopAllAnimations",
         "InvalidateLayoutAndVolatility", "ForceLayoutPrepass", "SetIsEnabled", "SetCursor", "SetDesiredSizeOverride",
         "SetWidthOverride", "SetHeightOverride", "SetMinDesiredWidth", "SetColorAndOpacityTo", "ApplyTheme",
         "SetHorizontalAlignment", "SetVerticalAlignment", "SetSize", "SetPosition", "SetPositionInViewport",
         "SetScalarParameterValue", "SetVectorParameterValue", "SetTextureParameterValue", "SetDynamicMaterial",
         "GetDynamicMaterial", "SetShadowColorAndOpacity", "SetOpacity", "SetFillColorAndOpacity", "SetPercent",
         "SetAutoWrapText", "SetWrapTextAt", "UpdateTheme", "RefreshTheme", "SetIsChecked", "SetCheckedState",
         "SetSelectedButton"}
NOISE |= {"RequestRender", "SetSelected", "SetHighlighted", "SetHovered", "SetIsFocusable", "SetKeyboardFocus",
          "SetUserFocus", "SetFocus"}
QUIET_EVENTS = {"OnInvalidated"}                         # redraw requests, not something the user did
COSMETIC_OWN = re.compile(r"^(Invalidate|SetSelectedButton$|UpdateVisual|RefreshVisual|Update.*Style|Refresh.*Style|"
                          r"Highlight|Unhighlight|PlayHover|PlayClick|PlayPress|Animate|Hover|Unhover)")
HOVER = re.compile(r"Hover|Unhover", re.I)


# ---------------------------------------------------------------- loading
def string_tables(folder):
    """{table name: {key: English text}} from the string table CSVs Tribe ships"""
    out = {}
    for f in glob.glob(os.path.join(folder, "*.csv")):
        with open(f, encoding="utf-8-sig", newline="") as fh:
            out[os.path.splitext(os.path.basename(f))[0]] = {r["Key"]: r["SourceString"] for r in csv.DictReader(fh) if r.get("Key")}
    return out


def text_of(p, st):
    """an FText property -> its English text"""
    if not isinstance(p, dict):
        return None
    if p.get("HistoryType") == "StringTableEntry":
        table = str(p.get("TableId") or "").split(".")[-1].split("/")[-1]
        return st.get(table, {}).get(p.get("Value")) or p.get("Value")
    for k in ("CultureInvariantString", "SourceString"):
        if isinstance(p.get(k), str) and p[k].strip():
            return p[k].strip()
    return None


def prop(data, name):
    return next((p for p in data or [] if p.get("Name") == name), None)


class Bp:
    """one dumped Blueprint: its exports, widget tree and functions"""

    def __init__(self, d, st):
        self.d, self.st = d, st
        self.asset = d["asset"][:-len(".uasset")]
        self.ex = d["exports"]
        ce = next((e for e in self.ex if e.get("type") == "ClassExport"), None)
        self.name = ce["name"] if ce else os.path.basename(self.asset)
        self.parent = kp.short(ce.get("super")) if ce else ""
        self.funcs = {e["name"]: e for e in self.ex if e.get("type") == "FunctionExport"}
        self.uber = next((f for n, f in self.funcs.items() if n.startswith("ExecuteUbergraph")), None)
        self.entry = {}                                    # event function -> ubergraph offset
        for n, f in self.funcs.items():
            for s in f.get("code") or []:
                if s.get("Inst") in ("LocalFinalFunction", "FinalFunction") and str(s.get("Function", "")).startswith("ExecuteUbergraph"):
                    ps = s.get("Parameters") or []
                    if ps and ps[0].get("Inst") == "IntConst":
                        self.entry[n] = int(kp.num(ps[0]["Value"]))
        wt = next((i for i, e in enumerate(self.ex, 1) if e.get("class") == "WidgetTree"), None)
        self.widgets = {i: e for i, e in enumerate(self.ex, 1) if wt and e.get("outer") == wt and e.get("type") == "NormalExport"}
        self.children = {}
        for e in self.ex:
            if str(e.get("class", "")).endswith("Slot"):
                par, con = prop(e.get("data"), "Parent"), prop(e.get("data"), "Content")
                if par and con and isinstance(con.get("Value"), int) and con["Value"] > 0:
                    self.children.setdefault(par.get("Value"), []).append(con["Value"])
        self.by_name = {e["name"]: i for i, e in self.widgets.items()}
        self.var_types = {p["name"]: p.get("type", "") for p in (ce.get("props") or [])} if ce else {}
        self.index = None

    def var_class(self, var):
        """the Blueprint class of a member variable (Object(BP_MiniMenu_C) -> BP_MiniMenu_C), or of a widget"""
        m = re.match(r"(?:Object|Class|SoftObject|WeakObject)\((\w+_C)\)", self.var_types.get(var, ""))
        if m:
            return m.group(1)
        i = self.by_name.get(var)
        return str(self.widgets[i].get("class")) if i else None

    def ref(self, v):
        if not isinstance(v, int) or v == 0:
            return None
        if v < 0:
            return next((kp.short(i.get("path")) for i in self.d["imports"] if i.get("i") == v), None)
        return self.ex[v - 1]["name"] if v - 1 < len(self.ex) else None

    def own_label(self, i):
        """a Tribe widget instance's own label property, or a TextBlock's text"""
        for p in self.widgets[i].get("data") or []:
            if "TextPropertyData" in str(p.get("$type")) and p.get("Name") not in ("ToolTipText",):
                t = text_of(p, self.st)
                if t:
                    return t
        return None

    def label(self, i, depth=0):
        t = self.own_label(i)
        if t or depth > 6:
            return t
        for c in self.children.get(i, []):
            if c in self.widgets:
                t = self.label(c, depth + 1)
                if t:
                    return t
        return None

    def icon(self, i, depth=0):
        """an icon-only control's picture: a Tribe widget's image property, or the texture of an Image inside it"""
        e = self.widgets[i]
        for p in e.get("data") or []:
            if p.get("Name") in ("ButtonImage", "Icon", "IconImage", "IconTexture", "Image") and isinstance(p.get("Value"), int):
                n = self.ref(p["Value"])
                if n:
                    return n
        if e.get("class") == "Image":
            br = prop(e.get("data"), "Brush")
            ro = prop(br.get("Value") if br and isinstance(br.get("Value"), list) else None, "ResourceObject")
            if ro and isinstance(ro.get("Value"), int):
                return self.ref(ro["Value"])
        for c in self.children.get(i, []) if depth < 4 else []:
            if c in self.widgets:
                n = self.icon(c, depth + 1)
                if n:
                    return n
        return None

    def style_icon(self, i):
        """a Button whose picture is its own style: the Normal brush's texture"""
        e = self.widgets[i]
        if e.get("class") != "Button":
            return None
        ws = prop(e.get("data"), "WidgetStyle")
        nb = prop(ws.get("Value") if ws and isinstance(ws.get("Value"), list) else None, "Normal")
        ro = prop(nb.get("Value") if nb and isinstance(nb.get("Value"), list) else None, "ResourceObject")
        n = self.ref(ro.get("Value")) if ro and isinstance(ro.get("Value"), int) else None
        return None if n and re.search(r"Rounded|Square|Background|Gradient|Blank|White_|Box|Panel|Border", n) else n

    def descendants(self, i, depth=0):
        out = []
        for c in self.children.get(i, []) if depth < 8 else []:
            if c in self.widgets:
                out += [c] + self.descendants(c, depth + 1)
        return out

    def nearby_label(self, i, levels=2):
        """for a checkbox or slider without text of its own: the text block beside it (same row, or the row's
        container one level up), skipping other controls' labels"""
        parent = {c: p for p, cs in self.children.items() for c in cs}
        node = i
        for _ in range(levels):
            p = parent.get(node)
            if p is None:
                return None
            for c in self.children.get(p, []):
                if c != node and c in self.widgets and self.widgets[c].get("class") == "TextBlock":
                    t = self.own_label(c)
                    if t:
                        return t
            node = p
        return None


class Index:
    """every dumped Blueprint under the root, loaded on demand, for following calls into other Blueprints"""

    def __init__(self, root, st):
        self.st, self.cache = st, {}
        self.paths = {os.path.splitext(os.path.basename(f))[0] + "_C": f
                      for f in glob.glob(os.path.join(root, "**", "*.json"), recursive=True)}

    def get(self, cls):
        if cls not in self.cache:
            p = self.paths.get(cls)
            self.cache[cls] = Bp(json.load(open(p, encoding="utf-8")), self.st) if p else None
            if self.cache[cls]:
                self.cache[cls].index = self
        return self.cache[cls]


# ---------------------------------------------------------------- following the graph
def reach(code, start):
    """the statements run from offset start: jumps followed, both sides of branches and sequences"""
    at = {s.get("StatementIndex"): k for k, s in enumerate(code)}
    seen, stack, out = set(), [start], []
    while stack:
        k = at.get(stack.pop())
        while k is not None and k < len(code):
            s = code[k]
            si = s.get("StatementIndex")
            if si in seen:
                break
            seen.add(si)
            out.append(s)
            i = s.get("Inst")
            if i == "Jump":
                k = at.get(s.get("Offset"))
                continue
            if i in ("JumpIfNot", "PushExecutionFlow"):
                stack.append(s.get("Offset"))
            elif i in ("PopExecutionFlow", "Return", "EndOfScript", "ComputedJump"):
                break
            k += 1
    return out


def call_texts(stmt):
    """(function name, rendered call) for every call in a statement, with its target"""
    out = []

    def walk(e, inside_context=False):
        if isinstance(e, dict):
            i = e.get("Inst")
            if i in ("Context", "Context_FailSilent") and isinstance(e.get("Expression"), dict) and e["Expression"].get("Inst") in CALLS:
                c = e["Expression"]
                out.append((c.get("Function") or c.get("FunctionName"), c, kp.ex(e)))
                walk(e.get("Context"))
                for p in c.get("Parameters") or []:
                    walk(p)
                return
            if i in CALLS:
                out.append((e.get("Function") or e.get("FunctionName"), e, kp.ex(e)))
                for p in e.get("Parameters") or []:
                    walk(p)
                return
            if i == "CallMulticastDelegate":
                out.append(("Broadcast", e, kp.ex(e)))
            for v in e.values():
                walk(v)
        elif isinstance(e, list):
            for v in e:
                walk(v)
    walk(stmt)
    return out


def keep(fn, node):
    fn = str(fn)
    if node.get("Inst") == "CallMath":
        lib = kp.short(node.get("ContextClass"))
        if lib in LIBS:
            return False
        if lib in ("KismetSystemLibrary", "GameplayStatics", "WidgetBlueprintLibrary") and fn not in KEEP_SYSTEM:
            return False
    if fn in NOISE or fn.startswith("ExecuteUbergraph"):
        return False
    return not GETTER.match(fn)


def short_call(text, n=110):
    text = re.sub(r"K2Node_[A-Za-z]+_|CallFunc_|_ReturnValue(_\d+)?|_ImplicitCast", "", text)
    text = text.replace("self.", "")
    return text if len(text) <= n else text[:n - 1] + "…"


def resolve_texts(e, st):
    """string-table text constants -> their English text, in place, so calls print what the user sees"""
    if isinstance(e, dict):
        if e.get("Inst") == "TextConst" and e.get("TableKey") and not e.get("SourceString"):
            e["SourceString"] = st.get(str(e.get("TableId") or "").split(".")[-1], {}).get(e["TableKey"]) or e["TableKey"]
        for v in e.values():
            resolve_texts(v, st)
    elif isinstance(e, list):
        for v in e:
            resolve_texts(v, st)


def does(bp, code, start, depth=0, seen=None):
    """what running code from start does: the calls that matter, own functions expanded a level"""
    seen = seen if seen is not None else set()
    out = []
    for s in reach(code, start):
        if s.get("Inst") in ("AddMulticastDelegate", "RemoveMulticastDelegate"):
            continue
        resolve_texts(s, bp.st)
        for fn, node, text in call_texts(s):
            if not keep(fn, node):
                continue
            if fn == "Broadcast":
                d = short_call(kp.ex(node.get("Delegate"))).split(".")[-1]
                if d not in QUIET_EVENTS:
                    out.append("fires " + d)
                continue
            own = bp.funcs.get(str(fn))
            head = text.split("(")[0]
            if own is not None and depth < 2 and (bp.name, fn) not in seen and node.get("Inst") in ("LocalFinalFunction", "LocalVirtualFunction", "FinalFunction", "VirtualFunction") \
                    and not text.startswith(("self.", "Default__")) and "." not in head:
                seen.add((bp.name, fn))
                sub = function_does(bp, str(fn), depth + 1, seen)
                if sub or not COSMETIC_OWN.match(str(fn)):
                    out.append(f"{fn}()" + (f" → {'; '.join(sub[:4])}" + ("…" if len(sub) > 4 else "") if sub else ""))
                continue
            m = re.match(r"^(?:self\.)?(\w+)\.(\w+)$", head)       # Var.Function(): another Blueprint we have
            other = bp.index.get(bp.var_class(m.group(1))) if m and bp.index and depth < 2 else None
            if other is not None and m.group(2) in other.funcs and (other.name, m.group(2)) not in seen:
                seen.add((other.name, m.group(2)))
                sub = function_does(other, m.group(2), depth + 1, seen)
                out.append(short_call(text) + (f" → {'; '.join(sub[:4])}" + ("…" if len(sub) > 4 else "") if sub else ""))
                continue
            out.append(short_call(text))
    return list(dict.fromkeys(out))


def function_does(bp, name, depth, seen):
    f = bp.funcs.get(name)
    if f is None:
        return []
    if name in bp.entry and bp.uber:                       # an event stub: its body is in the event graph
        return does(bp, bp.uber.get("code") or [], bp.entry[name], depth, seen)
    code = f.get("code") or []
    return does(bp, code, code[0].get("StatementIndex") if code else 0, depth, seen)


# ---------------------------------------------------------------- per widget
BND = re.compile(r"^BndEvt__(.+)_K2Node_ComponentBoundEvent_\d+_(.+?)__DelegateSignature$")


def bound_events(bp):
    """[(widget name, event, handler function)]: designer bindings (the class's ComponentDelegateBinding: widget,
    delegate, function), any BndEvt function that record doesn't name (widget guessed from the function name), and
    `self.X.OnY += ...` in the graph"""
    out, named = [], set()
    for e in bp.ex:
        if e.get("class") == "ComponentDelegateBinding":
            for item in (prop(e.get("data"), "ComponentDelegateBindings") or {}).get("Value") or []:
                v = {p.get("Name"): p.get("Value") for p in item.get("Value") or []}
                if v.get("ComponentPropertyName") in bp.by_name and v.get("FunctionNameToBind"):
                    out.append((v["ComponentPropertyName"], v.get("DelegatePropertyName"), v["FunctionNameToBind"]))
                    named.add(v["FunctionNameToBind"])
    names = sorted(bp.by_name, key=len, reverse=True)
    for n in bp.funcs:
        m = BND.match(n)
        if m and n not in named:
            left, ev = m.groups()
            w = next((x for x in names if left == x or left.endswith("_" + x)), None)
            if w:
                out.append((w, ev, n))
    for f in bp.funcs.values():
        local = {}
        for s in f.get("code") or []:
            if s.get("Inst") == "BindDelegate":
                local[kp.ex(s.get("Delegate"))] = s.get("FunctionName")
            if s.get("Inst") == "AddMulticastDelegate":
                md, dg = s.get("MulticastDelegate") or {}, s.get("Delegate") or {}
                if md.get("Inst") in ("Context", "Context_FailSilent"):
                    w = kp.ex(md.get("Context")).replace("self.", "")
                    ev = kp.ex(md.get("Expression"), member=True)
                    fn = dg.get("FunctionName") if dg.get("Inst") == "InstanceDelegate" else local.get(kp.ex(dg))
                    if w in bp.by_name and fn:
                        out.append((w, ev, str(fn)))
    return list(dict.fromkeys(out))


def is_control(bp, i):
    c = str(bp.widgets[i].get("class", ""))
    return c in CONTROLS or (c.endswith("_C") and bp.own_label(i) is not None) or re.search(r"(Button|CheckBox|Checkbox|Slider|Toggle|Switch)$", bp.widgets[i]["name"])


def created_widgets(bp):
    out = []
    for f in bp.funcs.values():
        for s in f.get("code") or []:
            for fn, node, _ in call_texts(s):
                if fn == "Create" and node.get("Inst") == "CallMath":
                    for p in node.get("Parameters") or []:
                        if p.get("Inst") == "ObjectConst" and str(p.get("Object", "")).endswith("_C"):
                            out.append(kp.short(p["Object"]))
    return sorted(set(out))


TEXT_SETTER = re.compile(r"^(SetText|Set\w*Text|Set\w*Label|SetHintText|AddOption)$")


def cdo_array(bp, name):
    """the default values of a member array (texts, strings or names), from the class default object"""
    cdo = next((e for e in bp.ex if e.get("name") == f"Default__{bp.name}"), None)
    p = prop(cdo.get("data") if cdo else None, name)
    vals = []
    for v in p.get("Value") if p and isinstance(p.get("Value"), list) else []:
        t = text_of(v, bp.st) if "TextPropertyData" in str(v.get("$type")) else v.get("Value")
        if isinstance(t, str) and t:
            vals.append(t)
    return vals


def runtime_texts(bp):
    """{widget variable: [(setter, text expression)]} from SetText / Set...Text / Set...Label / AddOption calls. An
    argument read from a member array (Array_Get(self.A, i, X)) shows as A[], or as the array's default values"""
    out = {}

    def walk(e, arrays):
        if isinstance(e, dict):
            if e.get("Inst") in ("Context", "Context_FailSilent"):
                ctx, c = e.get("Context") or {}, e.get("Expression") or {}
                fn = str(c.get("Function") or c.get("FunctionName") or "")
                if ctx.get("Inst") == "InstanceVariable" and c.get("Inst") in CALLS and TEXT_SETTER.match(fn) and c.get("Parameters"):
                    p = c["Parameters"][0]
                    base = p.get("StructExpression") if p.get("Inst") == "StructMemberContext" else p
                    arr = arrays.get(kp.ex(base)) if isinstance(base, dict) and base.get("Inst") == "LocalVariable" else None
                    vals = cdo_array(bp, arr) if arr and base is p else []
                    if vals:
                        out.setdefault(ctx.get("Variable Name"), []).extend((fn, v) for v in vals)
                    else:
                        t = f"{arr}[]" + (f".{p.get('Property Name')}" if base is not p else "") if arr else short_call(kp.ex(p), 70)
                        if t not in ('Text("")', '""', "None"):
                            out.setdefault(ctx.get("Variable Name"), []).append((fn, t))
            for v in e.values():
                walk(v, arrays)
        elif isinstance(e, list):
            for v in e:
                walk(v, arrays)

    def array_reads(e, arrays):
        if isinstance(e, dict):
            ps = e.get("Parameters") or []
            if str(e.get("Function")) == "Array_Get" and len(ps) >= 3 and ps[0].get("Inst") == "InstanceVariable":
                arrays[kp.ex(ps[2])] = ps[0].get("Variable Name")
            for v in e.values():
                array_reads(v, arrays)
        elif isinstance(e, list):
            for v in e:
                array_reads(v, arrays)
    for f in bp.funcs.values():
        arrays = {}
        array_reads(f.get("code") or [], arrays)
        for s in f.get("code") or []:
            resolve_texts(s, bp.st)
            walk(s, arrays)
    return out


def label_for(bp, i, rt):
    """(label, kind): kind '' = shown text, 'nearby' = text beside it, 'icon', 'list', 'runtime', 'panel'"""
    e = bp.widgets[i]
    cls = str(e.get("class", ""))
    lab = bp.label(i)
    if lab:
        return lab, ""
    if cls in ("CheckBox", "Slider", "SpinBox", "ComboBoxString", "ComboBoxKey", "TribeComboBoxText", "EditableTextBox", "W_SelectionBox_C"):
        near = bp.nearby_label(i, 3)
        if near:
            return near, "nearby"
    sets = [x for w in [i] + bp.descendants(i) for x in rt.get(bp.widgets[w]["name"], [])]
    opts = [t for fn, t in sets if fn == "AddOption"]
    if opts:
        return "options: " + ", ".join(dict.fromkeys(opts)), "runtime"
    if sets:
        return " / ".join(dict.fromkeys(t for _, t in sets[:6])), "runtime"
    if cls in ("ListView", "TileView", "TreeView"):
        ew = prop(e.get("data"), "EntryWidgetClass")
        n = bp.ref(ew.get("Value")) if ew else None
        return (f"list of {n.removesuffix('_C')}" if n else "list"), "list"
    ic = bp.icon(i) or bp.style_icon(i)
    if ic:
        return ic, "icon"
    if cls.endswith("_C"):
        return cls.removesuffix("_C"), "panel"
    words = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", " ", re.sub(r"^(W_|Button_)|(_?Button|_?Btn)$", "", e["name"])).replace("_", " ").strip()
    return (words or None), ("name" if words else "")


def catalog(bp):
    events = bound_events(bp)
    rt = runtime_texts(bp)
    rows = []
    with_events = {w for w, _, _ in events}
    for i, e in sorted(bp.widgets.items(), key=lambda kv: kv[1]["name"]):
        if not (is_control(bp, i) or e["name"] in with_events):
            continue
        evs = []
        for w, ev, fn in events:
            if w != e["name"]:
                continue
            d = function_does(bp, fn, 0, set())
            evs.append({"event": ev, "handler": fn, "does": d})
        lab, kind = label_for(bp, i, rt)
        rows.append({"widget": e["name"], "class": e.get("class"), "label": lab, "label_kind": kind, "events": evs})
    embeds = sorted({str(e.get("class")) for e in bp.widgets.values() if str(e.get("class", "")).endswith("_C")})
    panels = []
    for e in bp.ex:
        if e.get("class") == "WidgetComponent":
            wc = prop(e.get("data"), "WidgetClass")
            ds = prop(e.get("data"), "DrawSize")
            size = ds.get("Value")[0].get("Value") if ds and isinstance(ds.get("Value"), list) and ds["Value"] else None
            panels.append({"component": e["name"].replace("_GEN_VARIABLE", ""), "widget": bp.ref(wc.get("Value")) if wc else None, "size": size})
    return {"asset": bp.asset, "name": bp.name, "parent": bp.parent, "controls": rows, "embeds": embeds,
            "creates": created_widgets(bp), "panels": panels}


# ---------------------------------------------------------------- writing
def esc(t):
    return re.sub(r"\s*[\r\n]+\s*", " / ", str(t)).replace("|", "\\|") if t is not None else ""


def event_word(ev):
    return re.sub(r"(Event)?$", "", ev.replace("OnButton", "On").replace("OnClicked", "OnClick"))


def write_md(cats, path, folders):
    by_name = {c["name"]: c for c in cats}
    users = {}
    for c in cats:
        for e in c["embeds"]:
            users.setdefault(e, []).append(c["name"])
        for e in c["creates"]:
            users.setdefault(e, []).append(c["name"] + " (creates)")
    n_ctl = sum(len(c["controls"]) for c in cats)
    n_ev = sum(len(r["events"]) for c in cats for r in c["controls"])
    L = ["# Tribe XR's menus, button by button\n",
         f"Every widget Blueprint in {', '.join(f'`{f}`' for f in folders)} (build 2304): {len(cats)} Blueprints, "
         f"{n_ctl} controls, {n_ev} bound events. Generated by `scripts/menu_catalog.py` from `uasset_tool dump` JSON; "
         "pseudo-code of every Blueprint is in `D:/TribeUE/tribe_assets/catalog/code/`.\n",
         "How to read it:\n"
         "- **Label** is the text on the control: a text block inside it, a Tribe widget's own label property "
         "(`TextLabel`, `ButtonText`, `Header` ...), or a string-table entry resolved to English. Where a control has "
         "no text of its own: *italic* is the text beside a checkbox, slider or dropdown; `run time:` is the text "
         "(or the dropdown options) the Blueprint sets while the game runs; icon `T_...` is an icon-only button's "
         "texture (its picture, or its button style's); `(list of W_X)` is a list whose rows are W_X widgets; "
         "`(panel W_X)` is an embedded panel; `[..., from its name]` is only the widget's name split into words, used "
         "when nothing else names the control.\n"
         "- **Does** follows the event graph from the event's entry through its jumps, branches and sequences, and "
         "lists the calls that matter. The Blueprint's own functions are expanded a level (`Name() → ...`). Visibility, "
         "text, colour, sound and animation calls and plain getters are left out, so a control that only changes "
         "its own look shows \"-\".\n"
         "- **Embeds** are the panels placed inside a widget in the designer; **creates** are widgets it spawns at run "
         "time; **used in** is the reverse.\n"]
    roots = [c for c in cats if c["panels"]]
    if roots:
        L.append("## The 3D menu panels\n")
        L.append("| Actor | Panel | Shows | Size (px) |\n|---|---|---|---|")
        for c in sorted(roots, key=lambda c: c["name"]):
            for p in c["panels"]:
                L.append(f"| {c['name']} | {p['component']} | {esc(p['widget'])} | {'x'.join(map(str, p['size'])) if p['size'] else ''} |")
        L.append("")
    for folder in folders:
        group = sorted((c for c in cats if c["folder"] == folder), key=lambda c: c["asset"])
        if not group:
            continue
        L.append(f"## {folder}\n")
        quiet = []
        for c in group:
            if not c["controls"] and not c["panels"]:
                quiet.append(c["name"])
                continue
            L.append(f"### {c['name'].removesuffix('_C')}\n")
            meta = [f"`{c['asset']}` : `{c['parent']}`"]
            if c["embeds"]:
                meta.append("embeds " + ", ".join(f"`{e.removesuffix('_C')}`" for e in c["embeds"]))
            if c["creates"]:
                meta.append("creates " + ", ".join(f"`{e.removesuffix('_C')}`" for e in c["creates"]))
            if users.get(c["name"]):
                meta.append("used in " + ", ".join(f"`{u.removesuffix('_C')}`" for u in sorted(set(users[c['name']]))))
            L.append("; ".join(meta) + ".\n")
            if not c["controls"]:
                continue
            L.append("| Control | Label | Event | Does |\n|---|---|---|---|")
            for r in c["controls"]:
                kind = str(r["class"]).removesuffix("_C")
                evs = [e for e in r["events"] if e["does"]]
                fmt = {"nearby": "*{}*", "icon": "icon `{}`", "list": "({})", "runtime": "run time: {}", "panel": "(panel {})",
                       "name": "[{}, from its name]"}
                lab = fmt.get(r.get("label_kind"), "{}").format(esc(r["label"])) if r["label"] else ""
                if not evs:
                    quiet_evs = ", ".join(dict.fromkeys(event_word(e["event"]) for e in r["events"] if e["event"] not in QUIET_EVENTS))
                    L.append(f"| {esc(r['widget'])} ({esc(kind)}) | {lab} | {esc(quiet_evs) or '-'} | - |")
                for k, e in enumerate(evs):
                    items = [x if len(x) <= 260 else x[:259] + "…" for x in e["does"][:6]]
                    d = "; ".join(items) + ("; …" if len(e["does"]) > 6 else "")
                    first = k == 0
                    L.append(f"| {esc(r['widget']) + ' (' + esc(kind) + ')' if first else ''} | {lab if first else ''} | "
                             f"{esc(event_word(e['event']))} | {esc(d)} |")
            L.append("")
        if quiet:
            L.append(f"Display-only or list-item widgets in `{folder}` (no controls of their own): "
                     + ", ".join(f"`{q.removesuffix('_C')}`" for q in quiet) + ".\n")
    open(path, "w", encoding="utf-8", newline="\n").write("\n".join(L))


def main():
    if len(sys.argv) < 5:
        print(__doc__)
        return 2
    root, stdir, out_md, out_json = sys.argv[1:5]
    folders = sys.argv[5:] or ["Menus", "TrackManager", "MusicServices"]
    st = string_tables(stdir)
    index = Index(root, st)
    cats = []
    for folder in folders:
        for f in sorted(glob.glob(os.path.join(root, folder, "**", "*.json"), recursive=True)):
            d = json.load(open(f, encoding="utf-8"))
            if not str(d.get("class", "")).endswith("BlueprintGeneratedClass"):
                continue
            bp = Bp(d, st)
            bp.index = index
            if not bp.widgets and not any(e.get("class") == "WidgetComponent" for e in bp.ex):
                continue
            c = catalog(bp)
            c["folder"], c["asset"] = folder, f"{folder}/{c['asset']}"
            cats.append(c)
    write_md(cats, out_md, folders)
    json.dump(cats, open(out_json, "w", encoding="utf-8"), indent=1)
    n_ctl = sum(len(c["controls"]) for c in cats)
    n_lab = sum(1 for c in cats for r in c["controls"] if r["label"])
    kinds = {}
    for c in cats:
        for r in c["controls"]:
            kinds[r.get("label_kind") or ("text" if r["label"] else "none")] = kinds.get(r.get("label_kind") or ("text" if r["label"] else "none"), 0) + 1
    print("labels by source:", kinds)
    n_ev = sum(len(r["events"]) for c in cats for r in c["controls"])
    n_does = sum(1 for c in cats for r in c["controls"] for e in r["events"] if e["does"])
    print(f"{len(cats)} widget Blueprints, {n_ctl} controls ({n_lab} with a label), {n_ev} bound events ({n_does} doing "
          f"something past their own look), {sum(len(s) for s in st.values())} string-table entries -> {out_md}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
