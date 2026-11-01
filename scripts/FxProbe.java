// FxProbe: many read-only queries against the analyzed libUnreal.so in one headless Ghidra session (each launch costs
// ~40 s). Written for reading Tribe's mixer effects and the Superpowered DSP linked into the same binary.
//   args: <commands.txt> <log.txt>      one command per line, '#' starts a comment; addresses are Ghidra addresses (hex)
//   blocks                                  memory blocks
//   decomp <addr> <out.c> [depth] [lo] [hi] the function containing addr, then its direct callees inside [lo,hi) down to
//                                           depth (default 0), into out.c; the log gets the call tree and outside callees
//   range <lo> <hi> <out.c> [regex]         every function whose entry is in [lo,hi) (only those whose C matches regex)
//   callees <addr>                          direct callees: entry, size, name
//   callers <addr>                          who references addr (code and data), with the containing function
//   datarefs <addr>                         data references made by the function's code; a target that holds code pointers
//                                           (a vtable, also through a .got slot, +0x10 for the ABI header) lists its slots
//   vt <addr> <n> [out.c]                   n qwords at addr read as code pointers; with out.c each target is decompiled
//   str <text>                              every occurrence of the ASCII text, with references to it and pointers to it
//   ptr <addr>                              where the 8-byte value addr occurs in memory
//   f32|f64|u32|i32|u64 <addr> <n>          values
//   dis <addr> <n>                          disassembly of n instructions
import java.io.*;
import java.util.*;
import java.util.regex.Pattern;
import ghidra.app.script.GhidraScript;
import ghidra.app.decompiler.*;
import ghidra.program.model.address.*;
import ghidra.program.model.listing.*;
import ghidra.program.model.mem.*;
import ghidra.program.model.symbol.*;

public class FxProbe extends GhidraScript {
    PrintWriter log;
    DecompInterface dc;
    Memory mem;
    FunctionManager fm;
    ReferenceManager rm;

    Address A(String h) {
        h = h.trim();
        if (h.startsWith("0x") || h.startsWith("0X")) h = h.substring(2);
        if (h.startsWith("FUN_")) h = h.substring(4);
        return toAddr(Long.parseUnsignedLong(h, 16));
    }

    boolean isCode(Address a) {
        MemoryBlock b = mem.getBlock(a);
        return b != null && b.isExecute();
    }

    Function fn(Address a, boolean create) {
        Function f = fm.getFunctionContaining(a);
        if (f == null && create && isCode(a)) {
            try {
                if (getInstructionAt(a) == null) disassemble(a);
                f = createFunction(a, null);
            } catch (Exception e) { log.println("  (could not create a function at " + a + ": " + e + ")"); }
        }
        return f;
    }

    String fname(Function f) { return f == null ? "?" : f.getName() + "@" + f.getEntryPoint(); }

    String decomp(Function f) {
        DecompileResults r = dc.decompileFunction(f, 600, monitor);
        if (r != null && r.decompileCompleted() && r.getDecompiledFunction() != null) return r.getDecompiledFunction().getC();
        return "/* decompile failed: " + (r == null ? "null" : r.getErrorMessage()) + " */\n";
    }

    String header(Function f, String extra) {
        return "\n// ===== " + f.getName() + "  [ghidra " + f.getEntryPoint() + ", " + f.getBody().getNumAddresses()
            + " bytes" + (extra == null ? "" : ", " + extra) + "]\n";
    }

    long qword(Address a) throws MemoryAccessException { return mem.getLong(a); }

    void cmdBlocks() {
        for (MemoryBlock b : mem.getBlocks())
            log.printf("  %-24s %s - %s  %s%s%s init=%s%n", b.getName(), b.getStart(), b.getEnd(),
                b.isRead() ? "r" : "-", b.isWrite() ? "w" : "-", b.isExecute() ? "x" : "-", b.isInitialized());
    }

    void cmdDecomp(String[] t) throws Exception {
        Address root = A(t[1]);
        String out = t[2];
        int depth = t.length > 3 ? Integer.parseInt(t[3]) : 0;
        long lo = t.length > 4 ? A(t[4]).getOffset() : 0, hi = t.length > 5 ? A(t[5]).getOffset() : Long.MAX_VALUE;
        Function f0 = fn(root, true);
        if (f0 == null) { log.println("  no function at " + root); return; }
        PrintWriter w = new PrintWriter(new FileWriter(out));
        w.println("// FxProbe decomp root " + fname(f0) + " depth " + depth + " range [" + Long.toHexString(lo) + ","
            + (hi == Long.MAX_VALUE ? "-" : Long.toHexString(hi)) + ")");
        ArrayDeque<Object[]> q = new ArrayDeque<>();
        Set<Address> seen = new HashSet<>();
        Map<String, Integer> outside = new TreeMap<>();
        q.add(new Object[]{f0, 0, null});
        seen.add(f0.getEntryPoint());
        int n = 0;
        while (!q.isEmpty() && n < 600) {
            Object[] e = q.poll();
            Function f = (Function) e[0];
            int d = (Integer) e[1];
            n++;
            log.printf("  %s%s %d bytes%n", "  ".repeat(d), fname(f), f.getBody().getNumAddresses());
            w.print(header(f, "depth " + d + (e[2] == null ? "" : ", called from " + e[2])));
            w.println(decomp(f));
            w.flush();
            List<Function> cs = new ArrayList<>(f.getCalledFunctions(monitor));
            cs.sort(Comparator.comparing(Function::getEntryPoint));
            for (Function c : cs) {
                long o = c.getEntryPoint().getOffset();
                if (o >= lo && o < hi) {
                    if (d < depth && seen.add(c.getEntryPoint())) q.add(new Object[]{c, d + 1, f.getName()});
                } else outside.merge(fname(c) + " (" + c.getBody().getNumAddresses() + " bytes)", 1, Integer::sum);
            }
        }
        w.close();
        log.println("  wrote " + n + " functions to " + out);
        if (!outside.isEmpty()) {
            log.println("  callees outside the range:");
            for (var kv : outside.entrySet()) log.println("    " + kv.getKey() + "  x" + kv.getValue());
        }
    }

    void cmdRange(String[] t) throws Exception {
        Address lo = A(t[1]), hi = A(t[2]);
        String out = t[3];
        Pattern p = t.length > 4 ? Pattern.compile(t[4]) : null;
        PrintWriter w = new PrintWriter(new FileWriter(out));
        w.println("// FxProbe range [" + lo + "," + hi + ")" + (p == null ? "" : " matching " + p));
        int n = 0, kept = 0, failed = 0;
        for (Function f : fm.getFunctions(new AddressSet(lo, hi.subtract(1)), true)) {
            if (monitor.isCancelled()) break;
            n++;
            String c = decomp(f);
            if (c.startsWith("/* decompile failed")) failed++;
            if (p != null && !p.matcher(c).find()) continue;
            kept++;
            w.print(header(f, null));
            w.println(c);
            w.flush();
        }
        w.close();
        log.println("  " + n + " functions, " + kept + " written, " + failed + " failed -> " + out);
    }

    void cmdCallees(String[] t) throws Exception {
        Function f = fn(A(t[1]), true);
        if (f == null) { log.println("  no function"); return; }
        List<Function> cs = new ArrayList<>(f.getCalledFunctions(monitor));
        cs.sort(Comparator.comparing(Function::getEntryPoint));
        log.println("  " + fname(f) + " calls " + cs.size() + ":");
        for (Function c : cs) log.println("    " + fname(c) + " " + c.getBody().getNumAddresses() + " bytes");
    }

    void cmdCallers(String[] t) {
        Address a = A(t[1]);
        int n = 0;
        for (Reference r : rm.getReferencesTo(a)) {
            Function f = fm.getFunctionContaining(r.getFromAddress());
            log.println("    " + r.getFromAddress() + " " + r.getReferenceType() + " in " + fname(f));
            if (++n > 200) { log.println("    ..."); break; }
        }
        if (n == 0) log.println("    (no references)");
    }

    void vtableSlots(Address v, int max, String indent) throws Exception {
        for (int i = 0; i < max; i++) {
            Address s = v.add(8L * i);
            long val = qword(s);
            Address ta;
            try { ta = toAddr(val); } catch (Exception e) { break; }
            if (!isCode(ta)) { if (i == 0) log.println(indent + "(slot 0 is not code: 0x" + Long.toHexString(val) + ")"); break; }
            if (i > 0 && rm.getReferencesTo(s).iterator().hasNext()) { log.println(indent + "(slot " + i + " is referenced: next table)"); break; }
            Function f = fm.getFunctionAt(ta);
            log.println(indent + "slot " + i + " (+0x" + Integer.toHexString(8 * i) + "): " + ta + " " + (f == null ? "(no function)" : f.getName() + " " + f.getBody().getNumAddresses() + " bytes"));
        }
    }

    void cmdDatarefs(String[] t) throws Exception {
        Function f = fn(A(t[1]), true);
        if (f == null) { log.println("  no function"); return; }
        Set<Address> done = new HashSet<>();
        for (Instruction ins : currentProgram.getListing().getInstructions(f.getBody(), true)) {
            for (Reference r : ins.getReferencesFrom()) {
                Address to = r.getToAddress();
                if (!to.isMemoryAddress() || isCode(to) || !done.add(to)) continue;
                MemoryBlock b = mem.getBlock(to);
                String bn = b == null ? "?" : b.getName();
                long val = 0; boolean ok = true;
                try { val = qword(to); } catch (Exception e) { ok = false; }
                log.printf("    %s -> %s [%s] %s%n", ins.getAddress(), to, bn, ok ? "= 0x" + Long.toHexString(val) : "");
                if (!ok) continue;
                Address v = null;
                if (bn.contains("got")) {
                    try { Address pv = toAddr(val); if (mem.contains(pv) && !isCode(pv)) v = pv.add(0x10); } catch (Exception e) { }
                } else if (isCode(safe(val))) v = to;
                if (v != null) {
                    log.println("      table at " + v + ":");
                    vtableSlots(v, 40, "        ");
                }
            }
        }
    }

    Address safe(long v) { try { Address a = toAddr(v); return mem.contains(a) ? a : toAddr(0); } catch (Exception e) { return toAddr(0); } }

    void cmdVt(String[] t) throws Exception {
        Address v = A(t[1]);
        int n = Integer.parseInt(t[2]);
        PrintWriter w = t.length > 3 ? new PrintWriter(new FileWriter(t[3])) : null;
        for (int i = 0; i < n; i++) {
            long val = qword(v.add(8L * i));
            Address ta = safe(val);
            Function f = isCode(ta) ? fn(ta, true) : null;
            log.println("    [" + i + "] +0x" + Integer.toHexString(8 * i) + " 0x" + Long.toHexString(val) + " " + (f == null ? "" : fname(f) + " " + f.getBody().getNumAddresses() + " bytes"));
            if (w != null && f != null) { w.print(header(f, "slot " + i + " of " + v)); w.println(decomp(f)); w.flush(); }
        }
        if (w != null) { w.close(); log.println("  wrote " + t[3]); }
    }

    void cmdStr(String text) throws Exception {
        byte[] pat = text.getBytes("US-ASCII");
        int hits = 0;
        for (MemoryBlock b : mem.getBlocks()) {
            if (!b.isInitialized()) continue;
            Address cur = b.getStart();
            while (cur != null && cur.compareTo(b.getEnd()) <= 0) {
                Address h = mem.findBytes(cur, b.getEnd(), pat, null, true, monitor);
                if (h == null) break;
                hits++;
                log.println("    \"" + text + "\" at " + h + " [" + b.getName() + "]");
                for (Reference r : rm.getReferencesTo(h))
                    log.println("      ref " + r.getFromAddress() + " " + r.getReferenceType() + " in " + fname(fm.getFunctionContaining(r.getFromAddress())));
                ptrs(h, "      ");
                if (hits > 50) return;
                cur = h.add(1);
            }
        }
        if (hits == 0) log.println("    (not found)");
    }

    void ptrs(Address target, String indent) throws Exception {
        byte[] le = new byte[8];
        long v = target.getOffset();
        for (int i = 0; i < 8; i++) le[i] = (byte) (v >>> (8 * i));
        int n = 0;
        for (MemoryBlock b : mem.getBlocks()) {
            if (!b.isInitialized() || b.isExecute()) continue;
            Address cur = b.getStart();
            while (cur != null && cur.compareTo(b.getEnd()) <= 0) {
                Address h = mem.findBytes(cur, b.getEnd(), le, null, true, monitor);
                if (h == null) break;
                log.println(indent + "pointer at " + h + " [" + b.getName() + "]");
                for (Reference r : rm.getReferencesTo(h))
                    log.println(indent + "  ref " + r.getFromAddress() + " in " + fname(fm.getFunctionContaining(r.getFromAddress())));
                if (++n > 40) return;
                cur = h.add(1);
            }
        }
    }

    void cmdValues(String kind, Address a, int n) throws Exception {
        StringBuilder sb = new StringBuilder();
        int step = kind.equals("f64") || kind.equals("u64") ? 8 : 4;
        for (int i = 0; i < n; i++) {
            Address x = a.add((long) step * i);
            String s;
            switch (kind) {
                case "f32": s = Float.toString(Float.intBitsToFloat(mem.getInt(x))); break;
                case "f64": s = Double.toString(Double.longBitsToDouble(mem.getLong(x))); break;
                case "u32": s = "0x" + Integer.toHexString(mem.getInt(x)); break;
                case "i32": s = Integer.toString(mem.getInt(x)); break;
                default: s = "0x" + Long.toHexString(mem.getLong(x));
            }
            if (i % 8 == 0) sb.append(String.format("%n    %s:", x));
            sb.append(' ').append(s);
        }
        log.println(sb);
    }

    void cmdDis(Address a, int n) {
        Instruction ins = getInstructionAt(a);
        if (ins == null) ins = getInstructionAfter(a);
        for (int i = 0; i < n && ins != null; i++, ins = ins.getNext()) {
            StringBuilder refs = new StringBuilder();
            for (Reference r : ins.getReferencesFrom()) refs.append(" ->").append(r.getToAddress());
            log.println("    " + ins.getAddress() + "  " + ins + refs);
        }
    }

    @Override public void run() throws Exception {
        String[] a = getScriptArgs();
        log = new PrintWriter(new FileWriter(a[1]));
        mem = currentProgram.getMemory();
        fm = currentProgram.getFunctionManager();
        rm = currentProgram.getReferenceManager();
        dc = new DecompInterface();
        DecompileOptions o = new DecompileOptions();
        o.setMaxPayloadMBytes(512);
        dc.setOptions(o);
        dc.toggleCCode(true);
        dc.openProgram(currentProgram);
        try (BufferedReader r = new BufferedReader(new FileReader(a[0]))) {
            String line;
            while ((line = r.readLine()) != null) {
                line = line.trim();
                if (line.isEmpty() || line.startsWith("#")) continue;
                String[] t = line.split("\\s+");
                log.println("\n>>> " + line);
                long t0 = System.currentTimeMillis();
                try {
                    switch (t[0]) {
                        case "blocks": cmdBlocks(); break;
                        case "decomp": cmdDecomp(t); break;
                        case "range": cmdRange(t); break;
                        case "callees": cmdCallees(t); break;
                        case "callers": cmdCallers(t); break;
                        case "datarefs": cmdDatarefs(t); break;
                        case "vt": cmdVt(t); break;
                        case "str": cmdStr(line.substring(4)); break;
                        case "ptr": ptrs(A(t[1]), "    "); break;
                        case "f32": case "f64": case "u32": case "i32": case "u64": cmdValues(t[0], A(t[1]), Integer.parseInt(t[2])); break;
                        case "dis": cmdDis(A(t[1]), Integer.parseInt(t[2])); break;
                        default: log.println("  unknown command");
                    }
                } catch (Exception e) {
                    log.println("  ERROR " + e);
                    for (StackTraceElement s : e.getStackTrace()) { log.println("    at " + s); if (s.getClassName().equals("FxProbe")) break; }
                }
                log.println("  (" + (System.currentTimeMillis() - t0) + " ms)");
                log.flush();
            }
        }
        dc.dispose();
        log.println("\n# done");
        log.close();
        println("FxProbe wrote " + a[1]);
    }
}
