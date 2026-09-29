// Ghidra post-script v2 (run with -process -noanalysis on the saved project).
// Recovers avatar logic on a stripped UE build by anchoring on string literals two ways:
//   (1) direct code refs (ADRP/ADD) to the string  -> the using function (works for FString
//       wide literals like zip://%s_quest2.glb);
//   (2) UE reflection: a 64-bit pointer to a UFUNCTION-name string is immediately followed by
//       the exec-thunk pointer in the class's native-function registrar array. So for every
//       pointer P whose value == stringAddr, read *(P+8); if it lands in executable memory it is
//       execXxx -> decompile it (the thunk calls the real native impl).
// Both ASCII and UTF-16LE occurrences are searched.
import java.io.PrintWriter;
import java.util.*;
import ghidra.app.script.GhidraScript;
import ghidra.app.decompiler.*;
import ghidra.program.model.address.Address;
import ghidra.program.model.listing.*;
import ghidra.program.model.mem.*;
import ghidra.program.model.symbol.*;

public class AvatarXrefs2 extends GhidraScript {

    static final String[] ANCHORS = {
        "GetAvatarTypeForId", "GetAvatarIdForServer", "GetTribeDefaultAvatarId",
        "GetTribeMentorAvatarId", "IsMetaAvatarsSupported", "GetAvatarsPath",
        "IsValidReadyPlayerMeAvatarUrl", "IsValidReadyPlayerMeAvatarID",
        "GetAvatarUrlCacheFilename", "HandleReadyPlayerMeOnAvatarCached",
        "ReadyPlayerMeAvatarUrl", "QueriedAvatarUrl",
        "https://readyplayer.me/api/avatar/", "zip://%s_quest2.glb", "Replays/DefaultAvatar.glb",
        "ReadyPlayerMeETag",
    };
    static final long MAX_FUNC_BYTES = 0x6000;
    static final int DECOMP_TIMEOUT = 120;

    PrintWriter fh;
    Memory mem;
    FunctionManager fm;
    ReferenceManager refmgr;
    DecompInterface decomp;

    void emit(String s) { fh.println(s); println(s); }

    List<Address> occurrences(String text) throws Exception {
        List<Address> hits = new ArrayList<>();
        for (byte[] pat : new byte[][]{ ascii(text), utf16le(text) }) {
            Address start = mem.getMinAddress();
            int n = 0;
            while (true) {
                Address a = mem.findBytes(start, pat, null, true, monitor);
                if (a == null) break;
                hits.add(a); start = a.add(1);
                if (++n > 30) break;
            }
        }
        return hits;
    }
    static byte[] ascii(String s) throws Exception { return s.getBytes("US-ASCII"); }
    static byte[] utf16le(String s) throws Exception { return s.getBytes("UTF-16LE"); }

    List<Address> refsTo(Address a) {
        List<Address> out = new ArrayList<>();
        ReferenceIterator it = refmgr.getReferencesTo(a);
        while (it.hasNext()) out.add(it.next().getFromAddress());
        return out;
    }

    // all addresses P (8-aligned) holding the little-endian 64-bit value == target.getOffset()
    List<Address> pointersTo(Address target) throws Exception {
        byte[] pat = new byte[8];
        long v = target.getOffset();
        for (int i = 0; i < 8; i++) pat[i] = (byte)((v >>> (8*i)) & 0xff);
        List<Address> out = new ArrayList<>();
        Address start = mem.getMinAddress();
        int n = 0;
        while (true) {
            Address a = mem.findBytes(start, pat, null, true, monitor);
            if (a == null) break;
            out.add(a); start = a.add(1);
            if (++n > 60) break;
        }
        return out;
    }

    boolean isExec(Address a) {
        MemoryBlock b = mem.getBlock(a);
        return b != null && b.isExecute();
    }
    Address readPtr(Address a) {
        try { long v = mem.getLong(a); return v == 0 ? null : toAddr(v); }
        catch (Exception e) { return null; }
    }

    void record(Map<Address,Set<String>> reason, Function f, String why) {
        if (f != null) reason.computeIfAbsent(f.getEntryPoint(), k -> new TreeSet<>()).add(why);
    }

    String decompile(Function f) {
        if (f == null) return "(no function)";
        long n = f.getBody().getNumAddresses();
        if (n > MAX_FUNC_BYTES) return "(too large: " + n + " bytes at " + f.getEntryPoint() + ")";
        DecompileResults r = decomp.decompileFunction(f, DECOMP_TIMEOUT, monitor);
        if (r == null || !r.decompileCompleted()) return "(decompile failed " + f.getEntryPoint() + ")";
        return r.getDecompiledFunction().getC();
    }

    @Override
    public void run() throws Exception {
        String outPath = getScriptArgs().length > 0 ? getScriptArgs()[0] : "avatar_xrefs2.txt";
        fh = new PrintWriter(outPath);
        mem = currentProgram.getMemory();
        fm = currentProgram.getFunctionManager();
        refmgr = currentProgram.getReferenceManager();
        decomp = new DecompInterface();
        decomp.openProgram(currentProgram);
        emit("# libUnreal.so avatar-logic walk v2  image_base=" + currentProgram.getImageBase());

        Map<Address,Set<String>> reason = new LinkedHashMap<>();

        for (String anchor : ANCHORS) {
            emit("\n" + rep("=",96) + "\nANCHOR: \"" + anchor + "\"");
            List<Address> occ = occurrences(anchor);
            if (occ.isEmpty()) { emit("  (not found)"); continue; }
            for (Address s : occ) {
                List<Address> direct = refsTo(s);
                List<Address> ptrs = pointersTo(s);
                emit("  @ " + s + "  direct_refs=" + direct.size() + " pointer_slots=" + ptrs.size());
                for (Address r : direct) {
                    Function f = fm.getFunctionContaining(r);
                    if (f != null) { record(reason, f, anchor+" [direct]");
                        emit("    direct ref in FUNC " + f.getEntryPoint()); }
                }
                for (Address p : ptrs) {
                    // UE native registrar: name ptr at P, exec thunk ptr at P+8
                    Address execP = readPtr(p.add(8));
                    if (execP != null && isExec(execP)) {
                        Function f = fm.getFunctionContaining(execP);
                        if (f == null) { try { f = createFunction(execP, null); } catch (Exception e) {} }
                        if (f != null) { record(reason, f, anchor+" [execThunk]");
                            emit("    exec thunk @P+8 -> FUNC " + f.getEntryPoint()); }
                    }
                    // also whoever references the pointer slot (Z_Construct / registrar code)
                    for (Address r : refsTo(p)) {
                        Function f = fm.getFunctionContaining(r);
                        if (f != null) { record(reason, f, anchor+" [viaPtr]");
                            emit("    ptr-slot ref in FUNC " + f.getEntryPoint()); }
                    }
                }
            }
        }

        emit("\n" + rep("#",96) + "\n# DECOMPILATIONS\n" + rep("#",96));
        for (Address e : new ArrayList<>(reason.keySet())) {
            Function f = fm.getFunctionAt(e);
            if (f == null) continue;
            emit("\n" + rep("=",96));
            emit("FUNC " + e + "  size=" + f.getBody().getNumAddresses()
                 + "  (anchored by: " + String.join(", ", reason.get(e)) + ")");
            StringBuilder cb = new StringBuilder();
            for (Address r : refsTo(e)) { Function c = fm.getFunctionContaining(r); if (c!=null) cb.append(c.getEntryPoint()).append(" "); }
            emit("callers: " + cb.toString().trim());
            emit(rep("-",96));
            emit(decompile(f));
        }
        emit("\n# done");
        fh.close();
        println("WROTE " + outPath);
    }
    static String rep(String s, int n){ StringBuilder b=new StringBuilder(); for(int i=0;i<n;i++) b.append(s); return b.toString(); }
}
