"""Diff reflected (UPROPERTY) layouts between Tribe's libUnreal.so and an editor build's Win64 DLLs.

Cooked packages are unversioned: a property is stored by its INDEX in the class's property list. If Tribe's engine
has a property our editor lacks (or vice versa), every later index shifts and Tribe misreads the asset (seen as the
~2 GB allocation / OOM kill when loading our own UMaterial). So before shipping a class in a mod pak, its list must
match. Run this against a new engine build (e.g. Meta's fork) to check it before cooking.

How: UHT emits PropPointers[] -> FPropertyParamsBase{ const char* NameUTF8; ...; EPropertyFlags at +16 }. The .so
uses RELR relocations and the DLLs hold absolute VAs, so pointer slots hold the target address in the file. For each
anchor name we find every PropPointers[] containing it, drop container inner params and (editor side) CPF_EditorOnly
params, pair arrays by name overlap and print SAME/DIFF.

Usage: python scripts/ue_schemadiff.py <libUnreal.so> <UnrealEditor-X.dll>[,<dll>...] [anchor ...]
With no anchors it checks the classes the festival environment uses (World, Level, actors, mesh components,
material + material instance, texture, navigation config).
"""
import difflib
import struct
import sys

import numpy as np

CPF_EditorOnly = 0x0000000800000000
META_KEYS = {'ModuleRelativePath', 'Comment', 'ToolTip', 'Category', 'DisplayName', 'IncludePath', 'BlueprintType',
             'EditCondition', 'DeprecatedProperty', 'DeprecationMessage'}
# one distinctive property per class/struct we ship (owner in the comment)
DEFAULT_ANCHORS = [
    'bComputeFogPerPixel',            # UMaterial
    'bIncludedInBaseGame',            # UMaterialInterface
    'BasePropertyOverrides',          # UMaterialInstance
    'PhysMaterialMask',               # UMaterialInstanceConstant (+ UMaterial)
    'bOverride_OpacityMaskClipValue', # FMaterialInstanceBasePropertyOverrides
    'StaticSwitchParameters',         # static parameter sets
    'ParameterValue',                 # FScalar/FVector/FTextureParameterValue
    'Association',                    # FMaterialParameterInfo
    'CompressionSettings',            # UTexture
    'AddressX',                       # UTexture2D
    'NumCinematicMipLevels',          # UStreamableRenderAsset
    'bOverrideLightMapRes',           # UStaticMeshComponent
    'OverrideMaterials',              # UMeshComponent
    'TranslucencySortPriority',       # UPrimitiveComponent
    'CollisionProfileName',           # FBodyInstance
    'RelativeLocation',               # USceneComponent
    'ComponentTags',                  # UActorComponent
    'InitialLifeSpan',                # AActor
    'bStaticMeshReplicateMovement',   # AStaticMeshActor
    'bEnableWorldBoundsChecks',       # AWorldSettings
    'StreamingLevels',                # UWorld
    'LevelScriptActor',               # ULevel
    'TickGroup',                      # FTickFunction
    'bStrictlyStatic',                # UNavigationSystemModuleConfig
]


class Bin:
    def __init__(self, path):
        d = self.d = open(path, 'rb').read()
        self.secs = []  # (name, vaddr, fileoff, size)
        if d[:4] == b'\x7fELF':
            shoff = struct.unpack_from('<Q', d, 0x28)[0]
            shentsize, shnum, shstrndx = struct.unpack_from('<HHH', d, 0x3a)
            raw = [struct.unpack_from('<IIQQQQ', d, shoff + i * shentsize) for i in range(shnum)]
            stro = raw[shstrndx][4]
            for name, typ, _flags, addr, off, size in raw:
                if addr and typ != 8:  # skip NOBITS (.bss)
                    self.secs.append((d[stro + name:d.index(b'\x00', stro + name)].decode(), addr, off, size))
            ptrsecs = ('.data.rel.ro', '.data')
        else:
            pe = struct.unpack_from('<I', d, 0x3c)[0]
            nsec = struct.unpack_from('<H', d, pe + 6)[0]
            optsz = struct.unpack_from('<H', d, pe + 20)[0]
            base = struct.unpack_from('<Q', d, pe + 24 + 24)[0]
            sh = pe + 24 + optsz
            for i in range(nsec):
                o = sh + i * 40
                vsize, rva, rawsize, rawptr = struct.unpack_from('<IIII', d, o + 8)
                self.secs.append((d[o:o + 8].rstrip(b'\x00').decode(), base + rva, rawptr, min(vsize, rawsize)))
            ptrsecs = ('.rdata', '.data')
        self.slots = [(a, np.frombuffer(d, dtype='<u8', count=s // 8, offset=o))
                      for n, a, o, s in self.secs if n in ptrsecs]

    def v2o(self, v):
        for _n, a, o, s in self.secs:
            if a <= v < a + s:
                return v - a + o
        return None

    def o2v(self, off):
        for _n, a, o, s in self.secs:
            if o <= off < o + s:
                return off - o + a
        return None

    def u64(self, v):
        o = self.v2o(v) if v else None
        return None if o is None else struct.unpack_from('<Q', self.d, o)[0]

    def ident(self, v):
        o = self.v2o(v) if v else None
        if o is None:
            return None
        e = self.d.find(b'\x00', o, o + 128)
        s = self.d[o:e] if e > o else b''
        return s.decode() if s and all(48 <= c < 123 or c == 95 for c in s) else None

    def refs(self, target):
        return [a + int(i) * 8 for a, arr in self.slots for i in np.nonzero(arr == target)[0]]

    def param(self, slot):
        pv = self.u64(slot)
        name = self.ident(self.u64(pv)) if pv else None
        return (name, self.u64(pv + 16) or 0) if name else None

    def prop_arrays(self, anchor):
        out, pos = {}, 0
        while (i := self.d.find(anchor.encode() + b'\x00', pos)) >= 0:  # may be the tail of a linker-merged string
            pos = i + 1
            sv = self.o2v(i)
            for p in (self.refs(sv) if sv else []):
                for a in self.refs(p):
                    lo, hi = a, a
                    while self.param(lo - 8):
                        lo -= 8
                    while self.param(hi + 8):
                        hi += 8
                    out[lo] = [self.param(s) for s in range(lo, hi + 8, 8)]
        return list(out.values())


def schema(params, editor):
    """Names that occupy an unversioned property index, in order."""
    params = [(n, f) for n, f in params if n not in META_KEYS and n != 'UnderlyingType' and not n.endswith('_Key')]
    out = []
    for k, (n, f) in enumerate(params):
        if k + 1 < len(params) and params[k + 1][0] == n:
            continue  # a container's inner param precedes its outer and has the same name
        if editor and f & CPF_EditorOnly:
            continue
        out.append(n)
    return out


def jaccard(a, b):
    return len(set(a) & set(b)) / max(1, len(set(a) | set(b)))


def main():
    if len(sys.argv) < 3:
        sys.exit(__doc__)
    tribe = Bin(sys.argv[1])
    editors = [Bin(p) for p in sys.argv[2].split(',')]
    n_diff = 0
    for anchor in sys.argv[3:] or DEFAULT_ANCHORS:
        t_lists = [schema(L, False) for L in tribe.prop_arrays(anchor)]
        e_lists = [schema(L, True) for b in editors for L in b.prop_arrays(anchor)]
        print(f'== {anchor}: tribe arrays {len(t_lists)}, editor arrays {len(e_lists)}')
        for tl in t_lists:
            best = max(range(len(e_lists)), key=lambda k: jaccard(tl, e_lists[k]), default=None)
            if best is None or jaccard(tl, e_lists[best]) < 0.5:
                continue  # Tribe/plugin-only class that happens to share the anchor name
            el = e_lists[best]
            if tl == el:
                print(f'   SAME ({len(tl)} props) {tl[0]} .. {tl[-1]}')
                continue
            n_diff += 1
            print(f'   DIFF tribe {len(tl)} vs editor {len(el)} props ({tl[0]} ..)')
            for op, i1, i2, j1, j2 in difflib.SequenceMatcher(a=el, b=tl, autojunk=False).get_opcodes():
                if op != 'equal':
                    print(f'     {op}: editor{el[i1:i2]} -> tribe{tl[j1:j2]}  (after {el[i1 - 1] if i1 else "start"})')
    print(f'\n{n_diff} differing propert{"y list" if n_diff == 1 else "y lists"}')


if __name__ == '__main__':
    main()
