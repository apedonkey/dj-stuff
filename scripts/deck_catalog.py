#!/usr/bin/env python3
"""Tribe XR's DJ gear, read from its own Blueprints: every deck, mixer and controller model, each control on it, where
the control sits and what it calls. Input: scripts/uasset_tool `dump` output for TribeXR/Content (made with
pulled/TribeXR_full.usmap). Output: a markdown catalog, a function reference, the same data as JSON, and every
equipment Blueprint as pseudo-code (scripts/kismet_print.py).

    python -I scripts/deck_catalog.py <dump dir> <catalog.md> <reference.md> <catalog.json> <code dir>

How placement is read (all of it from Tribe's code, see the catalog's first section): a model's SpawnControls /
SpawnChannel / RespawnPadButtons spawn each control class and hand it to "Setup Child Control" with a marker
component. If the model's DT_<model>_ControlInfo row for the control's unique name has a BoneName, the control sits on
that bone of the model's skeletal mesh (component space from the Skeleton asset's reference pose); otherwise it sits
at the marker. Positions are in cm in the equipment actor's space: x left(-)/right(+), y back(-)/front(+, toward the
DJ), z up.
"""
import base64
import collections
import glob
import json
import math
import os
import re
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import kismet_print as kp  # noqa: E402

SPAWNERS = ("SpawnControls", "SpawnChannel", "RespawnPadButtons")
SETUP = ("Setup Child Control", "SetupChildControl", "SetupChildDisplay", "Setup Child Display")
KINDS = [("BP_JogWheel_C", "jog wheel"), ("BP_VinylJogWheel_C", "platter"), ("BP_QuantizedKnob_C", "stepped knob"),
         ("BP_KnobBase_C", "knob"), ("BP_QuantizedSlider_C", "stepped slider"), ("BP_SliderBase_C", "fader"),
         ("BP_BaseToggleButton_C", "toggle button"), ("BP_BaseRadioButton_C", "radio button"),
         ("BP_InputButton_C", "button"), ("BP_BaseDeckControl_C", "control")]
TARGETS = ("Deck", "Console", "ChannelDevice", "Mixer", "JogWheelToAffect", "AudioPlayer", "Rig", "OwningDeck", "AcidSynth", "Apc", "OscManager", "Osc Manager",
           "ParentDeck", "SamplePad", "Synth", "DrumMachine", "Controller", "TargetDeck")


# ---------------------------------------------------------------- loading
class Dumps:
    def __init__(self, root):
        self.root = root
        self.by_asset, self.by_class = {}, {}
        for f in glob.glob(os.path.join(root, "**", "*.json"), recursive=True):
            d = json.load(open(f, encoding="utf-8"))
            rel = d["asset"][:-len(".uasset")]
            self.by_asset[rel] = d
            ce = next((e for e in d["exports"] if e.get("type") == "ClassExport"), None)
            if ce:
                d["_class"] = ce
                self.by_class[ce["name"]] = d

    def imp(self, d, idx):
        """an object reference (import < 0, export > 0) -> path or export name"""
        if not isinstance(idx, int) or idx == 0:
            return None
        if idx < 0:
            for i in d["imports"]:
                if i["i"] == idx:
                    return i["path"]
            return None
        return d["exports"][idx - 1]["name"] if idx - 1 < len(d["exports"]) else None

    def parent(self, cls):
        d = self.by_class.get(cls)
        return kp.short(d["_class"].get("super")) if d else None

    def chain(self, cls):
        out = []
        while cls and cls not in out:
            out.append(cls)
            cls = self.parent(cls)
        return out

    def cdo(self, cls):
        d = self.by_class.get(cls)
        if not d:
            return None
        return next((e for e in d["exports"] if e["name"] == f"Default__{cls}"), None)

    def cdo_prop(self, cls, name):
        """a default value, walking the class chain (child overrides parent)"""
        for c in self.chain(cls):
            e = self.cdo(c)
            if e:
                p = prop(e.get("data"), name)
                if p is not None:
                    return p, self.by_class[c]
        return None, None

    def functions(self, cls):
        d = self.by_class.get(cls)
        return [e for e in d["exports"] if e.get("type") == "FunctionExport"] if d else []


def prop(data, name):
    for p in data or []:
        if p.get("Name") == name:
            return p
    return None


def value(p):
    return p.get("Value") if isinstance(p, dict) else None


def text_of(p):
    if not isinstance(p, dict):
        return None
    for k in ("CultureInvariantString", "Value", "SourceString"):
        v = p.get(k)
        if isinstance(v, str) and v:
            return v
    return None


def vec_of(p, keys=("X", "Y", "Z")):
    """Struct(Vector/Rotator) property -> tuple"""
    v = value(p)
    if isinstance(v, list) and v:
        v = v[0].get("Value")
    if isinstance(v, dict):
        return tuple(float(kp.num(v.get(k, 0))) for k in keys)
    return None


# ---------------------------------------------------------------- math (UE: quaternions x,y,z,w; rotators in degrees)
def q_mul(a, b):
    ax, ay, az, aw = a
    bx, by, bz, bw = b
    return (aw * bx + ax * bw + ay * bz - az * by, aw * by - ax * bz + ay * bw + az * bx,
            aw * bz + ax * by - ay * bx + az * bw, aw * bw - ax * bx - ay * by - az * bz)


def q_rot(q, v):
    x, y, z, w = q
    tx, ty, tz = 2 * (y * v[2] - z * v[1]), 2 * (z * v[0] - x * v[2]), 2 * (x * v[1] - y * v[0])
    return (v[0] + w * tx + (y * tz - z * ty), v[1] + w * ty + (z * tx - x * tz), v[2] + w * tz + (x * ty - y * tx))


def rotator_q(pitch, yaw, roll):
    """FRotator::Quaternion()"""
    dr = math.pi / 360.0
    sp, cp = math.sin(pitch * dr), math.cos(pitch * dr)
    sy, cy = math.sin(yaw * dr), math.cos(yaw * dr)
    sr, cr = math.sin(roll * dr), math.cos(roll * dr)
    return (cr * sp * sy - sr * cp * cy, -cr * sp * cy - sr * cp * sy, cr * cp * sy - sr * sp * cy, cr * cp * cy + sr * sp * sy)


# ---------------------------------------------------------------- skeletons
def parse_skeleton(d):
    """bone -> component-space position (cm), from the Skeleton's reference pose (native data after its properties)"""
    main = next((e for e in d["exports"] if "extras" in e), None)
    if not main:
        return {}
    b, names = base64.b64decode(main["extras"]), main["names"]
    n = struct.unpack_from("<i", b, 0)[0]
    p, bones = 4, []
    for i in range(n):
        ni, nn, par = struct.unpack_from("<iii", b, p)
        p += 12
        if not (0 <= ni < len(names) and -1 <= par < i):
            return {}
        bones.append((names[ni] + (f"_{nn - 1}" if nn else ""), par))
    if struct.unpack_from("<i", b, p)[0] != n:
        return {}
    p += 4
    cs = []
    for i, (nm, par) in enumerate(bones):
        qx, qy, qz, qw, tx, ty, tz = struct.unpack_from("<7d", b, p)
        p += 80
        q, t = (qx, qy, qz, qw), (tx, ty, tz)
        if abs(qx * qx + qy * qy + qz * qz + qw * qw - 1) > 1e-3:
            return {}
        if par < 0:
            cs.append((q, t))
        else:
            pq, pt = cs[par]
            r = q_rot(pq, t)
            cs.append((q_mul(pq, q), (pt[0] + r[0], pt[1] + r[1], pt[2] + r[2])))
    return {nm: cs[i][1] for i, (nm, _) in enumerate(bones)}


# ---------------------------------------------------------------- components (markers) across the class chain
def components(D, cls):
    """SCS components of a class and its Blueprint parents, inherited overrides applied: name -> info"""
    comps = {}
    for c in reversed(D.chain(cls)):
        d = D.by_class.get(c)
        if not d:
            continue
        ex = d["exports"]

        def merge(name, tpl_idx, parent=None):
            if not isinstance(tpl_idx, int) or not (0 < tpl_idx <= len(ex)):
                return
            t = ex[tpl_idx - 1]
            info = comps.setdefault(name, {"name": name})
            info["class"] = t.get("class") or info.get("class")
            if parent is not None:
                info["parent"] = parent
            for p in t.get("data") or []:
                n = p.get("Name")
                if n == "RelativeLocation":
                    info["loc"] = vec_of(p)
                elif n == "RelativeRotation":
                    info["rot"] = vec_of(p, ("Pitch", "Yaw", "Roll"))
                elif n == "RelativeScale3D":
                    info["scale"] = vec_of(p)
                elif n in ("StaticMesh", "SkeletalMeshAsset", "SkeletalMesh", "SkinnedAsset"):
                    info["mesh"] = D.imp(d, value(p))
                elif n == "AttachParent":
                    pass
        for e in ex:
            if e.get("class") == "SCS_Node":
                name = value(prop(e.get("data"), "InternalVariableName"))
                if name:
                    merge(name, value(prop(e.get("data"), "ComponentTemplate")), value(prop(e.get("data"), "ParentComponentOrVariableName")))
        for e in ex:
            if e.get("class") == "InheritableComponentHandler":
                for rec in value(prop(e.get("data"), "Records")) or []:
                    rv = rec.get("Value") or []
                    key = value(prop(rv, "ComponentKey")) or []
                    name = value(prop(key, "SCSVariableName"))
                    if name:
                        merge(name, value(prop(rv, "ComponentTemplate")))
    return comps


def comp_pos(comps, name, depth=0):
    """a component's location in the actor (parents' transforms applied)"""
    c = comps.get(name)
    if not c or depth > 16:
        return None
    loc = c.get("loc") or (0.0, 0.0, 0.0)
    par = c.get("parent")
    if par and par in comps and par != name:
        pp = comp_pos(comps, par, depth + 1) or (0.0, 0.0, 0.0)
        pr = comps[par].get("rot")
        if pr:
            loc = q_rot(rotator_q(*pr), loc)
        return (pp[0] + loc[0], pp[1] + loc[1], pp[2] + loc[2])
    return loc


# ---------------------------------------------------------------- what a model spawns
def var_of(e):
    if isinstance(e, dict) and e.get("Inst") in ("LocalVariable", "LocalOutVariable", "InstanceVariable", "DefaultVariable"):
        return ("self." if e["Inst"] == "InstanceVariable" else "") + e.get("Variable Name", "")
    return None


def spawner_chain(D, cls):
    """(class, function) for each spawner the model runs: its own definition, then a parent's only if called (super)"""
    out = []
    for name in SPAWNERS:
        for c in D.chain(cls):
            f = next((f for f in D.functions(c) if f["name"] == name), None)
            if not f:
                continue
            out.append((c, f))
            if name not in kp.calls(f.get("code")):       # no super call: the parent's version never runs
                break
    return out


def spawned(D, cls):
    """[{class, props, markers, member, via}] from the spawner functions a model runs"""
    out = []
    for c, f in reversed(spawner_chain(D, cls)):
        spawn, finish, member = {}, {}, {}
        # local constants (EQBands_Highs = 4, MakeLiteralByte(3)); a local that is never assigned holds Blueprint's 0
        consts, assigned, times = {}, set(), collections.Counter()
        params = {p["name"] for p in f.get("props") or [] if int(p.get("flags", 0)) & kp.CPF_PARM}
        for s in f.get("code") or []:
            if s.get("Inst") in ("Let", "LetObj", "LetBool") and (s.get("Variable") or {}).get("Inst") == "LocalVariable":
                v, e = s["Variable"]["Variable Name"], s.get("Expression") or {}
                assigned.add(v)
                times[v] += 1
                if e.get("Inst") in ("IntConst", "ByteConst", "IntConstByte", "IntZero", "IntOne"):
                    consts[v] = kp.ex(e)
                elif e.get("Inst") == "CallMath" and e.get("Function") in ("MakeLiteralByte", "MakeLiteralInt"):
                    p0 = (e.get("Parameters") or [{}])[0]
                    if p0.get("Inst") in ("IntConst", "ByteConst", "IntConstByte"):
                        consts[v] = kp.ex(p0)

        consts = {k: v for k, v in consts.items() if times[k] == 1}   # a loop counter (reassigned) is no constant

        def val(e):
            if isinstance(e, dict) and e.get("Inst") == "LocalVariable":
                n = e.get("Variable Name")
                if n in consts:
                    return consts[n]
                if n not in assigned and n not in params:
                    return "0"
            return kp.ex(e)
        for s in f.get("code") or []:
            i = s.get("Inst")
            ex_ = s.get("Expression") if i in ("Let", "LetObj") else None
            if isinstance(ex_, dict) and ex_.get("Inst") == "CallMath":
                fn = ex_.get("Function")
                ps = ex_.get("Parameters") or []
                if fn == "BeginDeferredActorSpawnFromClass" and len(ps) > 1:
                    spawn[var_of(s["Variable"])] = {"class": kp.short(ps[1].get("Object")), "props": {}, "via": f"{c}.{f['name']}"}
                elif fn == "FinishSpawningActor" and ps:
                    finish[var_of(s["Variable"])] = var_of(ps[0])
            if i == "CallMath" and str(s.get("Function", "")).startswith("Set") and str(s.get("Function", "")).endswith("PropertyByName"):
                ps = s.get("Parameters") or []
                if len(ps) >= 3 and var_of(ps[0]) in spawn:
                    spawn[var_of(ps[0])]["props"][str(ps[1].get("Value"))] = val(ps[2])
            if i in ("Let", "LetObj") and var_of(s.get("Variable", {})) and str(var_of(s["Variable"])).startswith("self.") and var_of(s.get("Expression")) in finish:
                member[var_of(s["Variable"])] = finish[var_of(s["Expression"])]
            if i in ("LocalFinalFunction", "FinalFunction", "LocalVirtualFunction") and (s.get("Function") or s.get("FunctionName")) in SETUP:
                ps = s.get("Parameters") or []
                if len(ps) < 2:
                    continue
                ctl = var_of(ps[0])
                sv = finish.get(ctl) or member.get(ctl) or ctl
                if sv not in spawn:
                    continue
                m = ps[1]
                if m.get("Inst") == "SwitchValue":
                    markers = [var_of(cs.get("CaseResult")) for cs in m.get("Cases") or []]
                else:
                    markers = [var_of(m)]
                item = dict(spawn[sv])
                item["markers"] = [x[5:] if x and x.startswith("self.") else None for x in markers]
                item["member"] = next((k[5:] for k, v in member.items() if v == sv), None)
                out.append(item)
    return out


# ---------------------------------------------------------------- per-control facts
def kind_of(D, cls):
    ch = D.chain(cls)
    for base, k in KINDS:
        if base in ch and base != "BP_BaseDeckControl_C":
            return k
    n = nice(cls).lower()                                 # straight on BP_BaseDeckControl: name it by what it is
    for word, k in (("button", "button"), ("knob", "knob"), ("slider", "fader"), ("fader", "fader"), ("search", "touch strip"),
                    ("tonearm", "tonearm"), ("handle", "handle")):
        if word in n:
            return k
    return "control"


def label_of(D, cls):
    """GetControlLabelText's text; a formatted label shows its pattern and the texts it picks from"""
    for c in D.chain(cls):
        f = next((f for f in D.functions(c) if f["name"] == "GetControlLabelText"), None)
        if not f:
            continue
        texts, fmt = [], None

        def walk(e):
            nonlocal fmt
            if isinstance(e, dict):
                if e.get("Inst") == "CallMath" and e.get("Function") == "Format":
                    p0 = (e.get("Parameters") or [{}])[0]
                    if p0.get("Inst") == "TextConst":
                        fmt = p0.get("SourceString")
                if e.get("Inst") == "TextConst":
                    t = e.get("SourceString") or e.get("TableKey")
                    if t and t not in texts:
                        texts.append(t)
                for v in e.values():
                    walk(v)
            elif isinstance(e, list):
                for v in e:
                    walk(v)
        walk(f.get("code"))
        others = [t for t in texts if t != fmt]
        if fmt:
            label = fmt + (f" ({'/'.join(others)})" if others else "")
        else:
            label = "/".join(texts) or None
        # multi-line labels (the pitch slider's "{BPM} BPM\r\n{Tempo}...") would break a markdown table row
        return re.sub(r"\s*[\r\n]+\s*", " / ", label) if label else None
    return None


GETTER = re.compile(r"^(Get|Is|Has|Can|Should|Find|Make)[A-Z ]")


VISUAL = re.compile(r"(Mesh|Mat|Material|Primitive|Widget|Component|Light|Text|FX|Highlight)\w*$|^(GrabbingHand|MidiPawn)$")


def var_types(D, cls):
    """member name -> declared type, over the class chain"""
    out = {}
    for c in D.chain(cls):
        d = D.by_class.get(c)
        for p in (d["_class"].get("props") or []) if d else []:
            out.setdefault(p["name"], p["type"])
    return out


def target_of(ctx, vt=None):
    """who a call goes to: a member that is a game object (self.Deck, self.Console, self.Apc), the member a chain ends
    on (self.TribeGameState...ActiveTrackList), a getter's result (CallFunc_GetOwningConsole_Console_1 -> Console) or a
    cast (K2Node_DynamicCast_AsBP_Deck -> BP_Deck); None for visuals (meshes, materials, widgets) and anything else"""
    i, n = ctx.get("Inst"), ctx.get("Variable Name") or ""
    if i == "InterfaceContext":
        return target_of(ctx.get("Expression") or {}, vt)
    if i == "InstanceVariable":
        if n in TARGETS:
            return n
        t = (vt or {}).get(n, "")
        return n if re.match(r"^(Object|Interface)\((BP_|Tribe)", t) and not VISUAL.search(n) else None
    if i in ("Context", "Context_FailSilent"):
        m = (ctx.get("Expression") or {}).get("Variable Name")
        return m if m and not VISUAL.search(m) else None
    if i in ("LocalVariable", "LocalOutVariable"):
        m = re.match(r"^CallFunc_.+?_([A-Za-z]+)(?:_\d+)?$", n)
        if m and m.group(1) in TARGETS + ("OwningConsole",):
            return m.group(1)
        m = re.match(r"^K2Node_DynamicCast_As(.+?)(?:_\d+)?$", n)
        if m:
            return m.group(1).replace(" ", "")
    return None


def target_calls(D, cls):
    """('Deck', 'SetSlip') style calls, ('Deck', 'broadcast OnX') event broadcasts and ('Deck', 'OnSlipModeChanged')
    subscriptions in the class's own code"""
    calls, listens = collections.Counter(), set()
    vt = var_types(D, cls)

    def walk(e):
        if isinstance(e, dict):
            i = e.get("Inst")
            if i in ("Context", "Context_FailSilent"):
                ctx, inner = e.get("Context") or {}, e.get("Expression") or {}
                t = target_of(ctx, vt)
                fn = inner.get("Function") or inner.get("FunctionName")
                if t and fn and inner.get("Inst") in ("FinalFunction", "VirtualFunction", "LocalFinalFunction", "LocalVirtualFunction"):
                    calls[(t, fn)] += 1
            if i == "CallMulticastDelegate":
                dl = e.get("Delegate") or {}
                if dl.get("Inst") == "Context":
                    t = target_of(dl.get("Context") or {}, vt)
                    if t:
                        calls[(t, "broadcast " + str((dl.get("Expression") or {}).get("Variable Name")))] += 1
                elif dl.get("Inst") == "InstanceVariable":
                    calls[("self", "broadcast " + str(dl.get("Variable Name")))] += 1
            if i == "AddMulticastDelegate":
                md = e.get("MulticastDelegate") or {}
                if md.get("Inst") == "Context":
                    t = target_of(md.get("Context") or {}, vt)
                    if t:
                        listens.add((t, (md.get("Expression") or {}).get("Variable Name")))
            for v in e.values():
                walk(v)
        elif isinstance(e, list):
            for v in e:
                walk(v)
    for f in D.functions(cls):
        walk(f.get("code"))
    return calls, listens


GENERIC_BASES = {"BP_BaseDeckControl_C", "BP_KnobBase_C", "BP_SliderBase_C", "BP_BaseToggleButton_C", "BP_BaseRadioButton_C",
                 "BP_InputButton_C", "BP_QuantizedKnob_C", "BP_QuantizedSlider_C", "TribeNetActor"}


def actions(D, cls):
    """the non-getter calls of a class, or of its nearest Blueprint parent that has some (below the generic bases)"""
    for c in D.chain(cls):
        if c in GENERIC_BASES:
            break
        calls, listens = target_calls(D, c)
        acts = [f"{t}.{f}" for (t, f), _ in calls.most_common() if not GETTER.match(f)]
        if acts:
            return acts, sorted(f"{t}.{f}" for t, f in listens if t and f), (None if c == cls else c)
    calls, listens = target_calls(D, cls)
    return [], sorted(f"{t}.{f}" for t, f in listens if t and f), None


def fmt_pos(p):
    return "-" if not p else f"{p[0]:.1f}, {p[1]:.1f}, {p[2]:.1f}"


# ---------------------------------------------------------------- the models
def info_for(D, model_cls):
    """the *Info class whose SpawnEquipmentClass is this model"""
    for cls, d in D.by_class.items():
        e = D.cdo(cls)
        sp = prop(e.get("data"), "SpawnEquipmentClass") if e else None
        if not sp:
            continue
        v = value(sp) or {}
        ap = json.dumps(v)
        if f".{model_cls}\"" in ap or f".{model_cls}'" in ap or ap.endswith(f".{model_cls}\"}}"):
            return cls
        m = re.search(r'"AssetName":\s*"([^"]+)"', ap)
        if m and m.group(1) == model_cls:
            return cls
    return None


def control_rows(D, model_cls):
    """the model's control-info rows: name -> (ElementIndex, BoneName, bInvisible). The engine finds the table by name,
    DT_<ModelId>_ControlInfo, or DT_<ModelId>_ControlInfo_<n> when one model id spans several tables (the DDJ-FLX4:
    GetEquipmentMeshTableIndex gives 0 for its mixer and MixerChannel+1 for its decks, so deck 1 reads _1)."""
    model_id = value(D.cdo_prop(model_cls, "ModelId")[0]) or ""
    base = f"Equipment/Models/DataTables/DT_{model_id}_ControlInfo"
    is_deck = "BP_Deck_C" in D.chain(model_cls)
    picks = [base] if base in D.by_asset else [f"{base}_{1 if is_deck else 0}"]
    tables = {}
    for a in [p for p in picks if p in D.by_asset]:
        d = D.by_asset[a]
        rows = next((e["rows"] for e in d["exports"] if "rows" in e), [])
        t = {}
        for r in rows:
            rv = r.get("Value") or []
            t[r["Name"]] = (value(prop(rv, "ElementIndex")), value(prop(rv, "BoneName")), bool(value(prop(rv, "bInvisible"))))
        tables[a.split("/")[-1]] = t
    return model_id, tables


def skeleton_for(D, comps):
    """bone positions of the model's skeletal mesh (via the mesh's Skeleton reference)"""
    for c in comps.values():
        m = c.get("mesh") or ""
        if "/SkeletalMeshes/" in m or c.get("class") == "SkeletalMeshComponent":
            sm = D.by_asset.get(m.split(".")[0].replace("/Game/", "TribeXR/Content/").replace("TribeXR/Content/", ""))
            if not sm:
                continue
            main = next((e for e in sm["exports"] if e["name"] == m.split(".")[-1]), None)
            sk = D.imp(sm, value(prop(main.get("data") if main else [], "Skeleton")))
            skd = D.by_asset.get(sk.split(".")[0].replace("/Game/", "")) if sk else None
            if skd:
                return parse_skeleton(skd), c["name"], sk.split(".")[-1]
    return {}, None, None


def unique_names(D, cls, props, channel, n_rows):
    """the control-info row names this control instance looks up (GetUniqueControlName, approximated by prefix)"""
    base, _ = D.cdo_prop(cls, "ControlName")
    base = value(base) or kp.short(cls).replace("BP_", "").removesuffix("_C")
    return base


def calibrate(controls, comps):
    """Bone positions come from the Skeleton asset's reference pose. Where a control has both a bone and a marker,
    compare them: on most models they agree (median offset ~0), which checks the bone math; on the Tribe Mixer most
    sit a constant (0, -1.2, -4.4) cm apart, so its skeletal mesh is offset in the actor by a transform the Blueprints
    don't show. If at least 3 controls compare, at least 60% sit within 0.5 cm of the median offset, and that offset is
    over 0.3 cm, move every bone-placed control by it. Returns the record the catalog prints."""
    d = []
    for c in controls:
        for p in c["places"]:
            if p["bone"] and p["marker"] and p["pos"]:
                m = comp_pos(comps, p["marker"])
                if m:
                    d.append(tuple(m[i] - p["pos"][i] for i in range(3)))
    if len(d) < 3:
        return {"applied": False, "samples": len(d)}
    med = tuple(sorted(x[i] for x in d)[len(d) // 2] for i in range(3))
    inliers = sum(1 for x in d if max(abs(x[i] - med[i]) for i in range(3)) <= 0.5)
    rec = {"samples": len(d), "inliers": inliers, "shift": [round(v, 2) for v in med]}
    rec["applied"] = len(d) >= 5 and inliers >= 0.6 * len(d) and max(abs(v) for v in med) > 0.3
    if rec["applied"]:
        for c in controls:
            for p in c["places"]:
                if p["bone"] and p["pos"]:
                    p["pos"] = tuple(p["pos"][i] + med[i] for i in range(3))
                    p["shifted"] = True
    return rec


EQ_BANDS = {0: "Low", 1: "LowMid", 2: "Mid", 3: "HighMid", 4: "High"}   # BP_ChannelEQKnob.GetUniqueControlName's switch


def band_word(v):
    """an EQ band setting (4, '4', 'EQBands_Highs', 'Band_Lows') -> the word unique control names use"""
    if v is None:
        return None
    s = str(v)
    if s.lstrip("-").isdigit():
        return EQ_BANDS.get(int(s))
    for w in ("HighMid", "LowMid", "High", "Mid", "Low"):
        if w in s:
            return w
    return None


def pick_row(rows, base, word, ch, idx):
    """the control-info row a control instance reads: <ControlName><band>_<channel> and its simpler forms"""
    w = word or ""
    names = []
    if ch is not None:
        names += [f"{base}{w}_{ch}", f"{base}{w}{ch}"]
    if idx is not None and str(idx).lstrip("-").isdigit():
        names += [f"{base}{w}{idx}", f"{base}{w}_{idx}"]    # HotCueButton3, PerformancePad5 (index appended bare)
    names += [f"{base}{w}", base] if ch is None else []
    return next((n for n in names if n in rows), None)


def name_switch(D, cls):
    """GetUniqueControlName's word switch: (property, {value: word}), e.g. ('PadMode', {1: 'HotCue', 3: 'BeatJump'})
    or ('EQBand', {0: 'Low', ... 4: 'High'}); (None, {}) when the class appends no word"""
    for c in D.chain(cls):
        f = next((f for f in D.functions(c) if f["name"] == "GetUniqueControlName"), None)
        if not f:
            continue
        strs, src, sw = {}, {}, None
        for s in f.get("code") or []:
            v, e = (s.get("Variable") or {}).get("Variable Name"), s.get("Expression") or {}
            if s.get("Inst") in ("Let", "LetObj") and v:
                if e.get("Inst") in ("StringConst", "NameConst", "UnicodeStringConst"):
                    strs[v] = str(e.get("Value", ""))
                elif e.get("Inst") == "InstanceVariable":
                    src[v] = e.get("Variable Name")

        def walk(e):
            nonlocal sw
            if isinstance(e, dict):
                if e.get("Inst") == "SwitchValue" and sw is None:
                    sw = e
                for x in e.values():
                    walk(x)
            elif isinstance(e, list):
                for x in e:
                    walk(x)
        walk(f.get("code"))
        if not sw:
            return None, {}
        key = src.get((sw.get("Expression") or {}).get("Variable Name"))
        table = {}
        for cs in sw.get("Cases") or []:
            cv, cr = cs.get("CaseValue") or {}, cs.get("CaseResult") or {}
            try:
                table[int(float(kp.num(cv.get("Value"))))] = strs.get(cr.get("Variable Name"), "")
            except (TypeError, ValueError):
                pass
        return key, table
    return None, {}


def build(D):
    models = []
    for a, d in sorted(D.by_asset.items()):
        if not a.startswith("Equipment/Models/") or "_class" not in d or a.endswith("Info") or a.endswith("_Info"):
            continue
        cls = d["_class"]["name"]
        comps = components(D, cls)
        bones, skel_comp, skel = skeleton_for(D, comps)
        model_id, tables = control_rows(D, cls)
        rows = {}
        for t in tables.values():
            rows.update(t)
        info_cls = info_for(D, cls)
        ie = D.cdo(info_cls) if info_cls else None
        idata = ie.get("data") if ie else []
        info = {
            "class": info_cls,
            "display_name": text_of(prop(idata, "DisplayName")),
            "description": text_of(prop(idata, "Description")),
            "sku": value(prop(idata, "SKU")),
            "width_cm": value(prop(idata, "DeviceWidth")),
            "device_type": value(prop(idata, "DeviceType")),
            "group": value(prop(idata, "DeviceGroup")),
            "channels": value(prop(idata, "NumChannels")),
            "equipment_id": value(prop(idata, "EquipmentId")),
        }
        controls = []
        for sp in spawned(D, cls):
            ccls = sp["class"]
            base = unique_names(D, ccls, sp["props"], None, len(rows))
            mine = sorted(r for r in rows if r == base or (r.startswith(base) and re.fullmatch(r"(Low|Mid|High|Hi|Lo)?_?\d*|[A-Z]\w*", r[len(base):] or "")))
            per_channel = len(sp["markers"]) > 1 or "SpawnChannel" in sp["via"]
            key, words = name_switch(D, ccls)                # the word GetUniqueControlName appends (PadMode -> HotCue)
            kv = str(sp["props"].get(key, "")) if key else ""
            if key and key not in sp["props"]:               # not set at spawn: the class default (cooked data omits zeros)
                dv = value(D.cdo_prop(ccls, key)[0])
                m_ = re.search(r"(\d+)$", str(dv)) if dv is not None else None
                kv = m_.group(1) if m_ else ("0" if dv is None else str(dv))
            word = words.get(int(kv)) if kv.lstrip("-").isdigit() else band_word(sp["props"].get("EQBand") or sp["props"].get("Band"))
            places = []
            idx = sp["props"].get("HotCueIndex") or sp["props"].get("PadIndex") or sp["props"].get("Index")
            numbered = sorted((int(m_.group(1)), r) for r in rows for m_ in [re.fullmatch(re.escape(base) + r"_?(\d+)", r)] if m_)
            if not per_channel and idx is not None and not str(idx).lstrip("-").isdigit() and numbered:
                # spawned in a loop (the index is a counter): one instance per numbered row, e.g. the FLX4's 8 pads
                mk = sp["markers"][0] if sp["markers"] else None
                for n_, rn in numbered:
                    bone = rows[rn][1]
                    places.append({"channel": None, "index": n_, "row": rn, "bone": bone, "marker": mk,
                                   "pos": bones.get(bone) if bone else (comp_pos(comps, mk) if mk else None)})
                controls.append({"class": ccls, "props": sp["props"], "via": sp["via"], "member": sp["member"], "places": places, "loop": True})
                continue
            if per_channel:
                nch = len(sp["markers"]) if len(sp["markers"]) > 1 else (info["channels"] or 4)
                for ch in range(nch):
                    rn = pick_row(rows, base, word, ch, None)
                    if not rn:                           # other naming schemes: the prefix match, filtered by channel and band
                        cands = [r for r in mine if r.endswith(f"_{ch}") and (not word or word in r)]
                        rn = cands[0] if cands else None
                    bone = rows.get(rn, (None, None, None))[1] if rn else None
                    mk = sp["markers"][ch] if ch < len(sp["markers"]) else None
                    pos = bones.get(bone) if bone else (comp_pos(comps, mk) if mk else None)
                    places.append({"channel": ch + 1, "row": rn, "bone": bone, "marker": mk, "pos": pos})
            else:
                mk = sp["markers"][0] if sp["markers"] else None
                rn = pick_row(rows, base, word, None, idx)
                if not rn and mine:
                    rn = mine[0] if len(mine) == 1 or idx is None else next((r for r in mine if r.endswith(f"_{idx}")), mine[0])
                bone = rows.get(rn, (None, None, None))[1] if rn else None
                pos = bones.get(bone) if bone else (comp_pos(comps, mk) if mk else None)
                places.append({"channel": None, "row": rn, "bone": bone, "marker": mk, "pos": pos})
            controls.append({"class": ccls, "props": sp["props"], "via": sp["via"], "member": sp["member"], "places": places})
        shift = calibrate(controls, comps)
        models.append({"asset": a, "class": cls, "parent": D.parent(cls), "model_id": model_id, "info": info,
                       "tables": list(tables), "skeleton": skel, "skeleton_component": skel_comp, "controls": controls,
                       "bone_shift": shift,
                       "components": {k: {kk: vv for kk, vv in v.items() if kk in ("class", "loc", "rot", "mesh", "parent")} for k, v in comps.items()}})
    return models


def control_classes(D):
    out = {}
    for cls in D.by_class:
        ch = D.chain(cls)
        if "BP_BaseDeckControl_C" not in ch or cls == "BP_BaseDeckControl_C":
            continue
        acts, listens, via = actions(D, cls)
        out[cls] = {"asset": D.by_class[cls]["asset"][:-len(".uasset")], "parent": D.parent(cls), "kind": kind_of(D, cls),
                    "label": label_of(D, cls), "control_name": value(D.cdo_prop(cls, "ControlName")[0]),
                    "calls": acts, "listens": listens, "calls_from": via}
    return out


# ---------------------------------------------------------------- output
def md_table(rows, header):
    out = ["| " + " | ".join(header) + " |", "|" + "|".join("---" for _ in header) + "|"]
    for r in rows:
        out.append("| " + " | ".join(str(x).replace("|", "\\|").replace("\n", " ") for x in r) + " |")
    return "\n".join(out)


GENERIC_PROPS = {"Deck", "Console", "ControlMeshDataTable", "ControlMaterialDataTable", "EquipmentMesh", "ChannelDevice",
                 "MixerChannel", "Mixer Channel"}


def does(ci):
    """a control class's calls and subscriptions, as one short cell"""
    if not ci:
        return "-"
    parts = []
    if ci["calls"]:
        src = f" (in {nice(ci['calls_from'])})" if ci.get("calls_from") else ""
        parts.append("calls " + ", ".join(ci["calls"][:6]) + (" ..." if len(ci["calls"]) > 6 else "") + src)
    if ci["listens"]:
        parts.append("follows " + ", ".join(ci["listens"][:4]) + (" ..." if len(ci["listens"]) > 4 else ""))
    return "; ".join(parts) or "generic behaviour of its kind"


def short_label(t, n=50):
    return "-" if not t else (t if len(t) <= n else t[:n - 1] + "…")


def nice(cls):
    return kp.short(cls).removeprefix("BP_").removesuffix("_C")


def write_md(models, ctl, D, path):
    used = collections.defaultdict(set)
    for m in models:
        for c in m["controls"]:
            used[c["class"]].add(m["info"]["display_name"] or nice(m["class"]))
    L = []
    L.append("# Tribe XR gear catalog: decks, mixers and controllers\n")
    L.append("Read from the Blueprints of Tribe XR 0.12.5.1 (build 2304) itself, not from screenshots or guesses. Made by "
             "`scripts/deck_catalog.py` from `scripts/uasset_tool` dumps of `/Game/Equipment`, using the type mappings "
             "the hook dumped from the running game (`pulled/TribeXR_full.usmap`). Every Blueprint named here is also "
             "available as readable pseudo-code (see the last section).\n")
    L.append("## How Tribe builds a piece of gear\n")
    L.append("- **A model** is a small Blueprint on top of one of two engines: `BP_Deck` (decks: playback, cues, loops, "
             "sync, beat grid, track loading) or `BP_Console` (mixers: channels, EQ, filters, FX, cueing). A matching "
             "`...Info` class holds what the gear menu shows: name, store SKU, width, preview image.\n"
             "- **Controls are separate actors.** The model's `SpawnControls` (and `SpawnChannel` once per mixer "
             "channel) spawns each control class and gives it the deck or mixer it drives (`Deck` / `Console`), the "
             "model's equipment mesh, and its tables of control meshes and materials. Every control derives from "
             "`BP_BaseDeckControl`: knobs, faders, toggle, radio and plain buttons, jog wheels, touch strips.\n"
             "- **Where a control sits:** `Setup Child Control` looks the control's unique name (for example "
             "`ChannelEQKnobLow_0`) up in the model's control table, `DT_<ModelId>_ControlInfo`. If the row names a "
             "bone, the control sits on that bone of the model's skeletal mesh; otherwise it sits at the marker "
             "component the model passed (`Marker_Play`, `Marker_CueChannel1` ...). The same row's `ElementIndex` picks "
             "the control's graphic from a texture atlas.\n"
             "- **What a control does:** its press, turn or slide handler calls a function on its deck or mixer (the "
             "Slip button calls `Deck.SetSlip(on)`), and it follows the deck's events to light up "
             "(`Deck.OnSlipModeChanged`). The deck's `Multi_...` and `Server_...` functions carry those changes to "
             "everyone in the room.\n")
    L.append("**Positions** are in cm in the gear's own space: x runs left (-) to right (+), y back (-) to front (+, "
             "the side you stand at: every deck's Play/Cue and every mixer's channel faders sit at +y, its screen or "
             "trim knobs at -y), z up, from the model's origin. Marker positions are exact. Bone positions come from the "
             "skeleton's reference pose; where a control has both, the two agree on the CDJ-3000, Tribe CDJ and "
             "DJM-NXS2 (median offset under 0.2 cm), and on the Tribe Mixer every bone position is moved by the "
             "constant offset its markers show (below).\n")
    L.append("## What the engines can do\n")
    L.append("Summarised from the engines' function names (every function, with parameters, is in `deck_reference.md`; "
             "the pseudo-code shows what each does).\n")
    L.append("**Decks (`BP_Deck`, 329 functions; sync lives in its base `BP_MixerChannelDevice`).**\n"
             "- Playback: `Start Play` / `Stop Play`, reverse (`SetReversePlayback`), pitch and tempo "
             "(`Multi_SetCurrentPitch`, tempo range `CycleTempoRange`, `ResetTempo`), key lock (`SetMasterTempo`), "
             "touch/brake (`Multi_SetTouchBrake`), the jog wheel (`JogStart` / `JogTick` / `JogStop`, `SetJogMode`, "
             "vinyl mode), needle and track search (`Needle Set Position`, `SetPositionFromFraction`), time display mode.\n"
             "- Cues: the cue point (`SetCue`, `SeekToCue`, cue preview, auto-cue to the first beat), hot cues "
             "(`SetHotCue`, `SeekToHotCue`, `ClearHotCue`, colours, call/record mode `SetHotCueMode`) and memory cues "
             "(`SetMemoryCue`, `SeekToMemoryCue`, `ClearMemoryCue`).\n"
             "- Loops and jumps: loop in/out, reloop/exit, `CutLoop`, `ExtendLoop`, beat loops (`SetBeatLoop`), "
             "`JumpLoop`, beat jump (`Multi_BeatJump` with selectable intervals), slip (`SetSlip`, slip reverse).\n"
             "- Key: `SetKey`, key shift up/down, key sync. Sync: `StartSync` / `End Sync` / `ToggleSync`, sync master, "
             "`RealignBeatSync`.\n"
             "- Beat grid: set BPM, set first bar, halve/double, reset, the in-VR beat-grid editor, quantize.\n"
             "- Tracks: local files, Beatport, SoundCloud, Tidal and Dropbox (each has its login handler), shared "
             "Dropbox links, track transfer between players, instant doubles, saved player memory (cues and loops per "
             "track), performance pads with pad modes, the player screen and its button banks.\n"
             "- Multiplayer: one player's deck is the replication master (`HasRepAuthority`); its state goes out as "
             "net-sync packets (`MakeNetSyncPacket`, `Multi_UpdateNetSyncMs_...`, `PlayNetSynced`), and `Multi_...` "
             "functions mirror each action for everyone.\n")
    L.append("**Mixers (`BP_Console`, 148 functions).**\n"
             "- Channels: fader and fader curve, EQ per band (`Set Channel EQ`, EQ curves), trim, filter level and "
             "resonance, send level, headphone cue (`SetChannelCue`), crossfader assign, crossfader and its curve, "
             "master filter.\n"
             "- Color FX (`SetActiveFXButton`, `SetColorFxParameter`, centre lock, \"smart\" color FX) and Beat FX "
             "(type, channel, level, time with next/previous intervals, on/off, quantize, BPM with auto and tap tempo, "
             "X-Pad, FX EQ). Send FX master mix, size, time and tone.\n"
             "- Mic: level, EQ, mode, mic FX, talkover, and ducking the music while someone speaks.\n"
             "- Sync master handling (`AutoSwitchSyncMaster`, `ResyncDecks`), Tribe's Smart Fader (tempo matching "
             "driven by the fader: `SetSmartFaderEnabled`, `SetPitchFromSmartFader`), VU meters, headphones, room "
             "audio spatialisation, saved mixer state and control locks.\n")
    L.append("**The rig (`BP_Rig`, 70 functions)** spawns the chosen mixer and one channel device per channel, sets "
             "deck scale and the equipment skin, locks gear for lessons, checks DLC and subscriptions for paid gear "
             "and stream tracks, switches MIDI mode, saves and restores the whole setup, and knows where the DJ, "
             "teacher and spectators stand.\n")
    rows = []
    for m in models:
        i = m["info"]
        n = sum(len(c["places"]) for c in m["controls"])
        rows.append([i["display_name"] or "?", nice(m["class"]), (i["device_type"] or ("Mixer" if "BP_Console_C" in D.chain(m["class"]) else "?")),
                     i["group"] or "-", i["sku"] or "-", kp.num(i["width_cm"]) if i["width_cm"] is not None else "-",
                     i["channels"] or max((p["channel"] or 0 for c in m["controls"] for p in c["places"]), default=0) or "-",
                     n, nice(m["parent"])])
    L.append("## The gear\n")
    L.append(md_table(rows, ["Name in the menu", "Model", "Type", "Group", "Store SKU", "Width (cm)", "Channels", "Controls", "Built on"]) + "\n")
    names = collections.Counter(m["info"]["display_name"] for m in models)
    for m in models:
        i = m["info"]
        title = i["display_name"] or nice(m["class"])
        if names[i["display_name"]] > 1:                  # the DDJ-FLX4's deck and mixer share a menu name
            title += f" ({'mixer' if 'BP_Console_C' in D.chain(m['class']) else 'deck'})"
        L.append(f"## {title}\n")
        facts = [f"Model `{m['class']}` on `{m['parent']}`", f"model id `{m['model_id']}`"]
        if i["sku"]:
            facts.append(f"SKU `{i['sku']}`")
        if i["width_cm"] is not None:
            facts.append(f"{kp.num(i['width_cm'])} cm wide")
        if m["tables"]:
            facts.append("control table " + ", ".join(f"`{t}`" for t in m["tables"]))
        if m["skeleton"]:
            facts.append(f"skeleton `{m['skeleton']}`")
        L.append(". ".join(facts) + ".")
        if i["description"]:
            L.append(f"\n> {i['description']}")
        s = m["bone_shift"]
        if s.get("applied"):
            L.append(f"\nBone positions moved by ({', '.join(kp.num(v) for v in s['shift'])}) cm to match this model's "
                     f"markers ({s['inliers']} of {s['samples']} controls with both agree on that offset).")
        elif s.get("samples", 0) >= 3 and s.get("inliers", 0) < 0.6 * s["samples"]:
            L.append(f"\nThis model's markers disagree with its bones ({s['inliers']} of {s['samples']} agree); the game "
                     f"uses the bone when the control table names one, so the positions below are the bones'.")
        t = []
        n = 0
        for c in m["controls"]:
            ci = ctl.get(c["class"])
            label = short_label((ci or {}).get("label"))
            kind = (ci or {}).get("kind") or kind_of(D, c["class"])
            settings = ", ".join(f"{k}={v}" for k, v in c["props"].items() if k not in GENERIC_PROPS)
            ps = c["places"]
            if len(ps) == 1:
                p = ps[0]
                where = f"bone {p['bone']}" if p["bone"] else (f"marker {p['marker']}" if p["marker"] else "-")
                n += 1
                t.append([n, nice(c["class"]), label, kind, fmt_pos(p["pos"]), where, settings or "-", does(ci)])
            else:
                for k, p in enumerate(ps):
                    where = f"bone {p['bone']}" if p["bone"] else (f"marker {p['marker']}" if p["marker"] else "-")
                    tag = f"ch {p['channel']}" if p["channel"] else f"pad {p.get('index', k) + 1}"
                    n += 1
                    t.append([n, f"{nice(c['class'])} ({tag})", label, kind, fmt_pos(p["pos"]), where, settings or "-",
                              does(ci) if k == 0 else "as above"])
        L.append("\n" + md_table(t, ["#", "Control", "Label", "Kind", "x, y, z (cm)", "Placed by", "Settings", "What it does"]) + "\n")
    L.append("## Every control class\n")
    L.append("The calls and events each class has in its own code (inherited behaviour comes from its parent). "
             "\"On\" lists the gear that spawns it.\n")
    t = []
    for cls in sorted(ctl, key=lambda c: (ctl[c]["asset"].split("/")[1:3], c)):
        ci = ctl[cls]
        t.append([nice(cls), short_label(ci["label"]), ci["kind"], nice(ci["parent"]) if ci["parent"] else "-", does(ci),
                  ", ".join(sorted(used.get(cls, []))) or "-", ci["asset"].removeprefix("Equipment/")])
    L.append(md_table(t, ["Control", "Label", "Kind", "Parent", "What it does", "On", "Asset (under /Game/Equipment)"]) + "\n")
    L.append("## Reading further\n")
    L.append("- `claudedocs/deck_reference.md`: every function of the deck engine (`BP_Deck`), the mixer engine "
             "(`BP_Console`), their shared base (`BP_MixerChannelDevice`), the control base (`BP_BaseDeckControl`) and "
             "the rig (`BP_Rig`), with parameters and what each calls.\n"
             "- `D:/TribeUE/tribe_assets/catalog/code/`: all 280 equipment Blueprints as pseudo-code (one `.txt` per "
             "asset, `scripts/kismet_print.py` format). `deck_catalog.json` next to it has this catalog's data.\n"
             "- Rebuild: dump the hook's `TribeXR.usmap` (tribemod/usmap_now), augment it with `uasset_tool augment`, "
             "`uasset_tool dump` the Equipment folder, then run `scripts/deck_catalog.py`. NOTES.md has the commands.\n")
    L.append("## Not covered here\n")
    L.append("- How the gear looks: the meshes and textures are exported and previewed in `claudedocs/gear_models.md`. "
             "This catalog names each model's skeletal mesh and skeleton.\n"
             "- What the native code does under the Blueprints (the audio engine, the equipment mesh's table lookup, "
             "the networking): `claudedocs/native_reference.md`, with the decompiled C++ in "
             "`D:/TribeUE/tribe_native/classes/`. This catalog shows the calls into it.\n"
             "- The FLX4 deck lists deck 1 (`DT_DDJ-FLX4_ControlInfo_1`); deck 2 reads `_2`.\n")
    open(path, "w", encoding="utf-8", newline="\n").write("\n".join(L))


def write_reference(D, path):
    L = ["# Tribe XR equipment engines: function reference\n",
         "Every function of the classes that run Tribe's gear, from its Blueprints (build 2304). `[Net...]` marks "
         "replicated calls, `[Event]` engine events. \"Calls\" lists the other functions each one calls (first 8). "
         "Pseudo-code for all of them: `D:/TribeUE/tribe_assets/catalog/code/`. Made by `scripts/deck_catalog.py`.\n"]
    for cls, what in [("BP_Deck_C", "the deck engine: every player model derives from it"),
                      ("BP_Console_C", "the mixer engine: every mixer model derives from it"),
                      ("BP_MixerChannelDevice_C", "the base of anything that plugs into a mixer channel (decks, synths)"),
                      ("BP_BaseDeckControl_C", "the base of every button, knob and fader"),
                      ("BP_Rig_C", "the rig that holds the decks and mixer in front of you")]:
        d = D.by_class.get(cls)
        if not d:
            continue
        funcs = sorted(D.functions(cls), key=lambda f: f["name"].lower())
        L.append(f"## {cls}: {what}\n")
        L.append(f"Parent `{kp.short(d['_class'].get('super'))}`. {len(funcs)} functions; variables: "
                 + ", ".join(f"`{p['name']}`" for p in (d["_class"].get("props") or [])[:400] if not p["name"].startswith("K2Node")) + ".\n")
        t = []
        for f in funcs:
            if f["name"].startswith("ExecuteUbergraph"):
                continue
            flags = f.get("fflags", "")
            tags = [x for x in ("NetMulticast", "NetServer", "NetClient", "Event") if f"FUNC_{x}" in flags]
            cs = [c for c in dict.fromkeys(kp.calls(f.get("code"))) if not c.startswith("ExecuteUbergraph")][:8]
            t.append([kp.signature(f), " ".join(tags) or "-", ", ".join(cs) or "-"])
        L.append(md_table(t, ["Function", "Kind", "Calls"]) + "\n")
    open(path, "w", encoding="utf-8", newline="\n").write("\n".join(L))


def write_code(D, code_dir):
    n = 0
    for a, d in D.by_asset.items():
        if "_class" not in d:
            continue
        path = os.path.join(code_dir, a + ".txt")
        os.makedirs(os.path.dirname(path), exist_ok=True)
        eps = kp.entry_points(d)
        with open(path, "w", encoding="utf-8", newline="\n") as fo:
            ce = d["_class"]
            fo.write(f"class {ce['name']} : {kp.short(ce.get('super'))}    ({d['asset']})\n")
            for p in ce.get("props") or []:
                fo.write(f"  var {p['name']}: {p['type']}\n")
            funcs = [e for e in d["exports"] if e.get("type") == "FunctionExport"]
            for f in sorted(funcs, key=lambda f: (f["name"].startswith("ExecuteUbergraph"), f["name"])):
                kp.print_function(f, eps if f["name"].startswith("ExecuteUbergraph") else None, fo)
        n += 1
    return n


def main():
    if len(sys.argv) < 6:
        print(__doc__)
        return 2
    D = Dumps(sys.argv[1])
    models = build(D)
    ctl = control_classes(D)
    used = collections.defaultdict(list)
    for m in models:
        for c in m["controls"]:
            used[c["class"]].append(m["class"])
    json.dump({"models": models, "controls": ctl}, open(sys.argv[4], "w", encoding="utf-8"), indent=1, default=str)
    write_md(models, ctl, D, sys.argv[2])
    write_reference(D, sys.argv[3])
    n = write_code(D, sys.argv[5])
    sys.stderr.write(f"{len(models)} models, {sum(len(m['controls']) for m in models)} spawned controls, {len(ctl)} control classes, {n} code files\n")
    for m in models:
        missing = sum(1 for c in m["controls"] for p in c["places"] if not p["pos"])
        sys.stderr.write(f"  {m['class']:<24} {len(m['controls']):3} controls, {missing} without a position, skeleton {m['skeleton']}, tables {m['tables']}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
