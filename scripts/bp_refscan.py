#!/usr/bin/env python3
"""Reference-scan a UAssetAPI JSON dump (RawExport bytes) for a Blueprint whose bytecode
UAssetAPI could not parse (PKG_UnversionedProperties, no usmap). For chosen function exports,
decode the raw serialized bytes and report:
  - imports referenced (FPackageIndex negatives found as aligned int32) -> external calls/classes
  - interesting NAME indices referenced (from a curated list)
This does not reconstruct full control flow, but reveals which values/among calls a function touches.

Usage: python scripts/bp_refscan.py <asset.json> <func1> [func2 ...]
"""
import json, base64, struct, sys, re

INTERESTING = [
    "bHasCustomAvatar","HasCustomAvatar","AvatarId","AvatarID","CurrentETribeAvatarType",
    "ReadConfigString","WriteConfigString","ReadyPlayerMeAvatarUrl","TribeAvatar",
    "GetTribeDefaultAvatarId","GetAvatarTypeForId","GetAvatarIdForServer",
    "GetSkinClass","ApplyActiveSkins","SetupAvatar","ApplySkin","ActiveSkinClasses",
    "ReadyPlayerMe","MetaAvatar2","OculusAvatar","GetSkin","IsValidReadyPlayerMe",
    "BP_ReadyPlayerMeAvatarSkin","BP_OculusAvatarSkin","BP_ReadyPlayerMeAvatarSkin_C",
    "BP_OculusAvatarSkin_C","SetAvatarID","DefaultSkin","GetDefaultSkinClass","SkinClass",
]

def main():
    js, funcs = sys.argv[1], sys.argv[2:]
    d = json.load(open(js))
    names = d["NameMap"]
    nidx = {n:i for i,n in enumerate(names)}
    imports = d.get("Imports",[])
    def imp_name(i):
        if 0 <= i < len(imports):
            im = imports[i]
            return f'{im.get("ClassName","?")}:{im.get("ObjectName","?")}'
        return f"<imp {i}>"
    exports = d["Exports"]
    ebyname = {}
    for e in exports:
        ebyname.setdefault(e.get("ObjectName"), e)

    for fn in funcs:
        e = ebyname.get(fn)
        print("\n" + "="*90)
        if not e:
            print(f"FUNC {fn}: NOT FOUND"); continue
        raw = base64.b64decode(e["Data"]) if e.get("Data") else b""
        print(f"FUNC {fn}  SerialSize={e.get('SerialSize')} bytes={len(raw)} ClassIndex={e.get('ClassIndex')} SuperIndex={e.get('SuperIndex')}")
        # aligned int32 scan
        ints = [struct.unpack_from("<i", raw, o)[0] for o in range(0, len(raw)-3)]
        # imports referenced (FPackageIndex negative)
        imps=set()
        for v in ints:
            if v < 0 and (-v-1) < len(imports):
                imps.add(-v-1)
        if imps:
            print("  imports referenced:")
            for i in sorted(imps):
                print("     ", imp_name(i))
        # interesting names referenced
        hits=[]
        for nm in INTERESTING:
            i = nidx.get(nm)
            if i is None: continue
            if any(v == i for v in ints):
                hits.append(nm)
        if hits:
            print("  interesting names referenced:", ", ".join(hits))
        # find EX_EndOfScript to bound bytecode
        eos=[o for o,b in enumerate(raw) if b==0x53]
        print("  EX_EndOfScript@", eos)

if __name__=="__main__":
    main()
