#!/usr/bin/env python3
"""Check every libUnreal 2311 address the mod2311 build relies on, against the store library (read-only).

Usage: python -P verify_2311.py <libUnreal.2311.store.so> <libUnreal.2311.patched.so>

Runtime addresses in the hook = patched vaddr; store vaddr = runtime - 0x1000 (text and data segments both shift by
one page; checked below from the program headers). Prints one PASS/FAIL line per check and exits 1 on any FAIL.
"""
import struct
import sys

import capstone

SHIFT = 0x1000


def load(path):
    d = open(path, "rb").read()
    assert d[:4] == b"\x7fELF", path
    phoff = struct.unpack_from("<Q", d, 0x20)[0]
    phentsize, phnum = struct.unpack_from("<HH", d, 0x36)
    segs = []
    for i in range(phnum):
        p_type, p_flags, p_off, p_va, _pa, p_fsz, p_msz, _al = struct.unpack_from("<IIQQQQQQ", d, phoff + i * phentsize)
        if p_type == 1:
            segs.append((p_va, p_off, p_fsz, p_msz, p_flags))
    return d, segs


def v2o(segs, va):
    for v, o, fsz, msz, fl in segs:
        if v <= va < v + fsz:
            return o + (va - v)
    return None


def read(d, segs, va, n):
    o = v2o(segs, va)
    return None if o is None else d[o:o + n]


def slot_value(d, segs, va):
    """A pointer slot's link-time value. This library packs its relocations (ANDROID_RELA / ANDROID_RELR); every
    R_AARCH64_RELATIVE that RELR encodes keeps its addend in place, so the file bytes are the target vaddr
    (cross-checked with llvm-readelf -r, which lists the slot as R_AARCH64_RELATIVE)."""
    b = read(d, segs, va, 8)
    return None if b is None else struct.unpack("<Q", b)[0]


FAILS = 0


def check(name, ok, detail):
    global FAILS
    if not ok:
        FAILS += 1
    print(f"[{'PASS' if ok else 'FAIL'}] {name}: {detail}")


def dis(d, segs, va, n):
    md = capstone.Cs(capstone.CS_ARCH_ARM64, capstone.CS_MODE_ARM)
    md.detail = False
    return list(md.disasm(read(d, segs, va, 4 * n), va))


def main():
    store, patched = sys.argv[1], sys.argv[2]
    ds, ss = load(store)
    dp, sp = load(patched)

    # 0. segment shift: every LOAD segment of the patched lib except the added one = store + 0x1000
    pairs = [(a[0], b[0]) for a, b in zip(ss, sp)]
    check("segments", all(b - a == SHIFT for a, b in pairs[1:4]), " ".join(f"{a:#x}->{b:#x}" for a, b in pairs[:4]))

    # 1. ProcessEvent: RVA_PE_GHIDRA 0x19e8eb4 (store) + PE_SKEW 0x1000 = runtime 0x19e9eb4. Prologue + the 5 words the
    #    hook overwrites (5-word form: base+0x19e9eb4+8 is not 8-byte aligned) must hold nothing PC-relative.
    pe_store = 0x19E8EB4
    w = struct.unpack("<5I", read(ds, ss, pe_store, 20))
    ins = dis(ds, ss, pe_store, 5)
    pcrel = [i for i in ins if i.mnemonic in ("adr", "adrp", "b", "bl", "cbz", "cbnz", "tbz", "tbnz") or
             (i.mnemonic.startswith("ldr") and "#0x" in i.op_str and "[" not in i.op_str) or i.mnemonic.startswith("b.")]
    check("ProcessEvent prologue (store 0x19e8eb4)", w[0] == 0xA9BA7BFD and not pcrel,
          f"w0={w[0]:#010x} ({ins[0].mnemonic} {ins[0].op_str}); first 5: " + "; ".join(f"{i.mnemonic} {i.op_str}" for i in ins))
    wp = struct.unpack("<I", read(dp, sp, pe_store + SHIFT, 4))[0]
    check("ProcessEvent in the patched lib (runtime 0x19e9eb4)", wp == w[0], f"w0={wp:#010x}")
    check("5-word hook form at ProcessEvent", ((pe_store + SHIFT + 8) & 7) != 0,
          f"(0x19e9eb4+8)&7 = {(pe_store + SHIFT + 8) & 7} -> NOP, LDR X17 #8, BR X17, .quad repl_pe")

    # 2. stream.cpp's two re-send hooks (runtime 0x5A81E7C, 0x5A82F18): their first 16 bytes
    heads = {0x5A81E7C: bytes([0xff, 0x43, 0x02, 0xd1, 0xfd, 0x7b, 0x06, 0xa9, 0xfd, 0x83, 0x01, 0x91, 0xf6, 0x57, 0x07, 0xa9]),
             0x5A82F18: bytes([0xff, 0xc3, 0x01, 0xd1, 0xfd, 0x7b, 0x05, 0xa9, 0xfd, 0x43, 0x01, 0x91, 0xf4, 0x4f, 0x06, 0xa9])}
    for rt, h in heads.items():
        got = read(ds, ss, rt - SHIFT, 16)
        ins = dis(ds, ss, rt - SHIFT, 5)
        check(f"stream re-send head (runtime {rt:#x}, store {rt - SHIFT:#x})", got == h,
              "; ".join(f"{i.mnemonic} {i.op_str}" for i in ins))

    # 3. FWeakObjectPtr::Get (store 0x1A366AC): GUObjectArray chunk table, stride 0x14, serial +0x10, flags +8, and the
    #    GOT slot whose target is UE::GC::GUnreachableObjectFlag (runtime 0x8679A30 = store 0x8678A30)
    got_slot = 0x8678A30
    tgt = slot_value(ds, ss, got_slot)
    ins = dis(ds, ss, 0x1A366AC, 40)
    txt = [f"{i.address:#x}: {i.mnemonic} {i.op_str}" for i in ins]
    adrp_got = any(i.mnemonic == "adrp" and f"#{(got_slot & ~0xFFF):#x}" in i.op_str for i in ins)
    ldr_got = any(i.mnemonic == "ldr" and f"#{(got_slot & 0xFFF):#x}]" in i.op_str for i in ins)
    stride = any(("#0x14" in i.op_str and i.mnemonic in ("mov", "umaddl", "smaddl", "madd", "mul")) or
                 (i.mnemonic in ("add", "sub") and "lsl #2" in i.op_str) for i in ins)
    serial = any(i.mnemonic == "ldr" and "#0x10]" in i.op_str for i in ins)
    flags = any(i.mnemonic == "ldr" and "#8]" in i.op_str for i in ins)
    garbage = any("#0x200000" in i.op_str for i in ins)
    check("FWeakObjectPtr::Get uses the GOT slot store 0x8678A30", adrp_got and ldr_got, f"adrp={adrp_got} ldr={ldr_got}")
    check("FWeakObjectPtr::Get tests serial(+0x10)/flags(+8)/Garbage 0x200000", serial and flags and garbage,
          f"serial={serial} flags={flags} garbage={garbage} stride-ish={stride}")
    data_segs = [s for s in ss if s[4] & 2]   # writable
    in_data = isinstance(tgt, int) and any(v <= tgt < v + msz for v, o, fsz, msz, fl in data_segs)
    check("GOT slot store 0x8678A30 -> a writable global (GUnreachableObjectFlag)", in_data,
          f"target={tgt if not isinstance(tgt, int) else hex(tgt)}")
    if isinstance(tgt, int):
        o = v2o(ss, tgt)
        init = struct.unpack_from("<I", ds, o)[0] if o is not None else None
        check("GUnreachableObjectFlag initial value is a ReachabilityFlag (1, 2 or 4) or .bss", init in (1, 2, 4, None),
              f"initial={init} (None = .bss, zero until the engine sets it)")
    print("---- FWeakObjectPtr::Get (store 0x1A366AC)")
    print("\n".join(txt))

    # 4. UTribeSkinItemWidget::NativeOnMouseButtonDown (store 0x5B4C890): the UserWidget call (raises OnMouseButtonDown
    #    through ProcessEvent) comes before the bSelected (+0x350) read and before ApplySkinToPlayer (bl 0x5B46D8C)
    ins = dis(ds, ss, 0x5B4C890, 200)
    i_uw = next((k for k, i in enumerate(ins) if i.mnemonic == "bl" and "0x3885cfc" in i.op_str), None)
    i_sel = next((k for k, i in enumerate(ins) if i.mnemonic.startswith("ldrb") and "#0x350]" in i.op_str), None)
    i_app = next((k for k, i in enumerate(ins) if i.mnemonic == "bl" and "0x5b46d8c" in i.op_str), None)
    check("box press: UserWidget::NativeOnMouseButtonDown before the bSelected read and the apply",
          i_uw is not None and i_sel is not None and i_app is not None and i_uw < i_sel < i_app,
          f"bl 0x3885cfc @{ins[i_uw].address:#x} / ldrb +0x350 @{ins[i_sel].address:#x} / bl 0x5b46d8c @{ins[i_app].address:#x}"
          if None not in (i_uw, i_sel, i_app) else f"uw={i_uw} sel={i_sel} apply={i_app}")
    print("---- NativeOnMouseButtonDown (store 0x5B4C890), first 90")
    for i in ins[:90]:
        print(f"  {i.address:#x}: {i.mnemonic} {i.op_str}")

    # 5. UTribeReadyPlayerMeAvatarSkin's vtable (store 0x8105270, stored by its InternalConstructor at 0x538FB68): slot +0x300
    #    (CanReapply, read by the press handler when the box is selected) must return false, so a selected box never applies
    vt = 0x8105270
    ctor = dis(ds, ss, 0x538FB68 - 12, 4)
    adrp = ctor[0].op_str.split('#')[-1] if ctor and ctor[0].mnemonic == 'adrp' else None
    vt_ok = adrp is not None and int(adrp, 16) + 0x260 + 0x10 == vt
    f300 = slot_value(ds, ss, vt + 0x300)
    body = dis(ds, ss, f300, 2) if f300 else []
    check("RPM skin vtable +0x300 (CanReapply) returns false",
          vt_ok and len(body) == 2 and body[0].mnemonic == "mov" and body[0].op_str in ("w0, #0", "w0, wzr") and body[1].mnemonic == "ret",
          f"slot -> {f300:#x}: " + "; ".join(f"{i.mnemonic} {i.op_str}" for i in body) +
          " | ctor: " + "; ".join(f"{i.address:#x} {i.mnemonic} {i.op_str}" for i in ctor))

    print(f"\n{FAILS} check(s) failed")
    sys.exit(1 if FAILS else 0)


if __name__ == "__main__":
    main()
