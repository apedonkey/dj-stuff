# Ghidra headless post-script (Jython 2.7).
# Anchors on confirmed string literals in libUnreal.so, walks references to each, maps them to
# the containing function, decompiles those functions, and lists their callers. Output goes to
# the path given as the first script arg (also echoed to the headless log).
#
# Invoked by analyzeHeadless with:  -postScript ghidra_avatar_xrefs.py <out_file>
import sys
from ghidra.app.decompiler import DecompInterface
from ghidra.util.task import ConsoleTaskMonitor

ANCHORS = [
    # avatar-type selection
    "GetAvatarTypeForId", "GetAvatarIdForServer", "GetTribeDefaultAvatarId",
    "GetTribeMentorAvatarId", "CurrentETribeAvatarType", "SetAvatarType", "OnAvatarTypeChanged",
    "ETribeAvatarType", "ETribeAvatarType::None", "ETribeAvatarType::MetaAvatar2",
    "ETribeAvatarType::ReadyPlayerMe",
    # RPM url / validation / cache
    "IsValidReadyPlayerMeAvatarUrl", "IsValidReadyPlayerMeAvatarID", "ReadyPlayerMeAvatarUrl",
    "QueriedAvatarUrl", "GetAvatarUrlCacheFilename", "ReadyPlayerMeETag",
    "HandleReadyPlayerMeOnAvatarCached", "https://readyplayer.me/api/avatar/",
    # meta avatar / gltfRuntime load path
    "zip://%s_quest2.glb", "zip://99.glb", "Replays/DefaultAvatar.glb",
]

MAX_FUNC_BYTES = 0x4000   # skip decompiling absurdly large functions
DECOMP_TIMEOUT = 90

out_path = getScriptArgs()[0] if getScriptArgs() else "avatar_xrefs.txt"
fh = open(out_path, "w")
mon = ConsoleTaskMonitor()
mem = currentProgram.getMemory()
fm = currentProgram.getFunctionManager()
refmgr = currentProgram.getReferenceManager()
listing = currentProgram.getListing()
af = currentProgram.getAddressFactory()

decomp = DecompInterface()
decomp.openProgram(currentProgram)


def emit(s):
    fh.write(s + "\n")
    print(s)


def find_string_addrs(text):
    """All addresses where the exact ASCII bytes of `text` occur in memory."""
    raw = bytearray(text.encode("ascii"))
    pat = bytes(raw)
    masks = None
    hits = []
    start = mem.getMinAddress()
    while True:
        a = mem.findBytes(start, pat, masks, True, mon)
        if a is None:
            break
        hits.append(a)
        start = a.add(1)
        if len(hits) > 40:
            break
    return hits


def refs_to(addr):
    out = []
    it = refmgr.getReferencesTo(addr)
    for r in it:
        out.append(r.getFromAddress())
    return out


def func_at(addr):
    f = fm.getFunctionContaining(addr)
    return f


def decompile(func):
    if func is None:
        return "(no function)"
    if func.getBody().getNumAddresses() > MAX_FUNC_BYTES:
        return "(function too large to decompile: %d bytes at %s)" % (
            func.getBody().getNumAddresses(), func.getEntryPoint())
    res = decomp.decompileFunction(func, DECOMP_TIMEOUT, mon)
    if res is None or not res.decompileCompleted():
        return "(decompile failed for %s)" % func.getEntryPoint()
    return res.getDecompiledFunction().getC()


def callers(func):
    out = set()
    for r in refs_to(func.getEntryPoint()):
        cf = func_at(r)
        if cf is not None:
            out.add(cf)
    return out


emit("# libUnreal.so avatar-logic xref walk")
emit("# program: %s  image base: %s" % (currentProgram.getName(), currentProgram.getImageBase()))
emit("")

decompiled = {}          # func entry -> C, so we print each function once
func_reason = {}         # func entry -> list of anchors that led here

for anchor in ANCHORS:
    emit("=" * 100)
    emit("ANCHOR: %r" % anchor)
    saddrs = find_string_addrs(anchor)
    if not saddrs:
        emit("  (string not found in memory)")
        continue
    for sa in saddrs:
        code_refs = refs_to(sa)
        emit("  @ %s  <- %d ref(s)" % (sa, len(code_refs)))
        for fr in code_refs:
            f = func_at(fr)
            if f is None:
                # maybe a pointer in a data table; hop once more
                second = refs_to(fr)
                emit("    ref from DATA %s (no func); %d ref(s) to that slot" % (fr, len(second)))
                for s2 in second:
                    f2 = func_at(s2)
                    if f2 is not None:
                        func_reason.setdefault(f2.getEntryPoint(), set()).add(anchor + " (via table)")
                        emit("      -> via table into FUNC %s %s" % (f2.getEntryPoint(), f2.getName()))
                continue
            func_reason.setdefault(f.getEntryPoint(), set()).add(anchor)
            emit("    ref from FUNC %s %s +0x%x" % (
                f.getEntryPoint(), f.getName(), fr.subtract(f.getEntryPoint())))

emit("")
emit("#" * 100)
emit("# DECOMPILATIONS (each function once), with callers")
emit("#" * 100)

# Decompile every function we touched, plus one level of callers for the small/important ones.
entries = list(func_reason.keys())
seen = set()
for entry in entries:
    f = fm.getFunctionAt(entry)
    if f is None or entry in seen:
        continue
    seen.add(entry)
    emit("")
    emit("=" * 100)
    emit("FUNC %s  (anchored by: %s)" % (entry, ", ".join(sorted(func_reason[entry]))))
    cs = callers(f)
    emit("callers (%d): %s" % (len(cs), ", ".join(str(c.getEntryPoint()) for c in cs)))
    emit("-" * 100)
    emit(decompile(f))

emit("")
emit("# done")
fh.close()
print("WROTE " + out_path)
