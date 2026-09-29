// Ghidra headless post-script (Java GhidraScript).
// Anchors on confirmed string literals in libUnreal.so, walks references to each, maps them to
// the containing function, decompiles those functions once, and lists their callers.
// Invoked with:  -postScript AvatarXrefs.java <out_file>
import java.io.PrintWriter;
import java.util.*;
import ghidra.app.script.GhidraScript;
import ghidra.app.decompiler.*;
import ghidra.program.model.address.Address;
import ghidra.program.model.listing.*;
import ghidra.program.model.mem.Memory;
import ghidra.program.model.symbol.Reference;
import ghidra.program.model.symbol.ReferenceIterator;
import ghidra.program.model.symbol.ReferenceManager;

public class AvatarXrefs extends GhidraScript {

    static final String[] ANCHORS = {
        "GetAvatarTypeForId", "GetAvatarIdForServer", "GetTribeDefaultAvatarId",
        "GetTribeMentorAvatarId", "CurrentETribeAvatarType", "SetAvatarType", "OnAvatarTypeChanged",
        "ETribeAvatarType", "ETribeAvatarType::None", "ETribeAvatarType::MetaAvatar2",
        "ETribeAvatarType::ReadyPlayerMe",
        "IsValidReadyPlayerMeAvatarUrl", "IsValidReadyPlayerMeAvatarID", "ReadyPlayerMeAvatarUrl",
        "QueriedAvatarUrl", "GetAvatarUrlCacheFilename", "ReadyPlayerMeETag",
        "HandleReadyPlayerMeOnAvatarCached", "https://readyplayer.me/api/avatar/",
        "zip://%s_quest2.glb", "zip://99.glb", "Replays/DefaultAvatar.glb",
    };

    static final long MAX_FUNC_BYTES = 0x4000;
    static final int DECOMP_TIMEOUT = 90;

    PrintWriter fh;
    Memory mem;
    FunctionManager fm;
    ReferenceManager refmgr;
    DecompInterface decomp;

    void emit(String s) { fh.println(s); println(s); }

    List<Address> findStringAddrs(String text) throws Exception {
        byte[] pat = text.getBytes("US-ASCII");
        List<Address> hits = new ArrayList<>();
        Address start = mem.getMinAddress();
        while (true) {
            Address a = mem.findBytes(start, pat, null, true, monitor);
            if (a == null) break;
            hits.add(a);
            start = a.add(1);
            if (hits.size() > 40) break;
        }
        return hits;
    }

    List<Address> refsTo(Address addr) {
        List<Address> out = new ArrayList<>();
        ReferenceIterator it = refmgr.getReferencesTo(addr);
        while (it.hasNext()) out.add(it.next().getFromAddress());
        return out;
    }

    String decompile(Function f) {
        if (f == null) return "(no function)";
        long n = f.getBody().getNumAddresses();
        if (n > MAX_FUNC_BYTES)
            return "(function too large to decompile: " + n + " bytes at " + f.getEntryPoint() + ")";
        DecompileResults res = decomp.decompileFunction(f, DECOMP_TIMEOUT, monitor);
        if (res == null || !res.decompileCompleted()) return "(decompile failed for " + f.getEntryPoint() + ")";
        return res.getDecompiledFunction().getC();
    }

    Set<Function> callers(Function f) {
        Set<Function> out = new LinkedHashSet<>();
        for (Address a : refsTo(f.getEntryPoint())) {
            Function cf = fm.getFunctionContaining(a);
            if (cf != null) out.add(cf);
        }
        return out;
    }

    @Override
    public void run() throws Exception {
        String outPath = (getScriptArgs().length > 0) ? getScriptArgs()[0] : "avatar_xrefs.txt";
        fh = new PrintWriter(outPath);
        mem = currentProgram.getMemory();
        fm = currentProgram.getFunctionManager();
        refmgr = currentProgram.getReferenceManager();
        decomp = new DecompInterface();
        decomp.openProgram(currentProgram);

        emit("# libUnreal.so avatar-logic xref walk");
        emit("# program: " + currentProgram.getName() + "  image base: " + currentProgram.getImageBase());
        emit("");

        // func entry -> anchors that led here
        Map<Address, Set<String>> funcReason = new LinkedHashMap<>();

        for (String anchor : ANCHORS) {
            emit(repeat("=", 100));
            emit("ANCHOR: \"" + anchor + "\"");
            List<Address> saddrs = findStringAddrs(anchor);
            if (saddrs.isEmpty()) { emit("  (string not found in memory)"); continue; }
            for (Address sa : saddrs) {
                List<Address> codeRefs = refsTo(sa);
                emit("  @ " + sa + "  <- " + codeRefs.size() + " ref(s)");
                for (Address fr : codeRefs) {
                    Function f = fm.getFunctionContaining(fr);
                    if (f == null) {
                        List<Address> second = refsTo(fr);
                        emit("    ref from DATA " + fr + " (no func); " + second.size() + " ref(s) to that slot");
                        for (Address s2 : second) {
                            Function f2 = fm.getFunctionContaining(s2);
                            if (f2 != null) {
                                funcReason.computeIfAbsent(f2.getEntryPoint(), k -> new TreeSet<>()).add(anchor + " (via table)");
                                emit("      -> via table into FUNC " + f2.getEntryPoint() + " " + f2.getName());
                            }
                        }
                        continue;
                    }
                    funcReason.computeIfAbsent(f.getEntryPoint(), k -> new TreeSet<>()).add(anchor);
                    emit("    ref from FUNC " + f.getEntryPoint() + " " + f.getName()
                         + " +0x" + Long.toHexString(fr.subtract(f.getEntryPoint())));
                }
            }
        }

        emit("");
        emit(repeat("#", 100));
        emit("# DECOMPILATIONS (each function once), with callers");
        emit(repeat("#", 100));

        for (Address entry : new ArrayList<>(funcReason.keySet())) {
            Function f = fm.getFunctionAt(entry);
            if (f == null) continue;
            emit("");
            emit(repeat("=", 100));
            emit("FUNC " + entry + "  (anchored by: " + String.join(", ", funcReason.get(entry)) + ")");
            Set<Function> cs = callers(f);
            StringBuilder cb = new StringBuilder();
            for (Function c : cs) cb.append(c.getEntryPoint()).append(" ");
            emit("callers (" + cs.size() + "): " + cb.toString().trim());
            emit(repeat("-", 100));
            emit(decompile(f));
        }

        emit("");
        emit("# done");
        fh.close();
        println("WROTE " + outPath);
    }

    static String repeat(String s, int n) {
        StringBuilder b = new StringBuilder();
        for (int i = 0; i < n; i++) b.append(s);
        return b.toString();
    }
}
