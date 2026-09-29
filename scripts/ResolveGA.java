// Resolve GUObjectArray: print the pointer stored at the slot(s), and decompile the pool allocator
// to confirm arg0 is an FUObjectArray. Ghidra addr -> runtime RVA = addr - 0x100000.
import java.io.PrintWriter;
import ghidra.app.script.GhidraScript;
import ghidra.app.decompiler.*;
import ghidra.program.model.address.Address;
import ghidra.program.model.listing.*;
import ghidra.program.model.mem.Memory;

public class ResolveGA extends GhidraScript {
    // data slots (Ghidra addrs) to dereference
    static final String[] SLOTS = {"07ba59e8","07ba5a90","07ba5990","07d632c0"};
    // functions (Ghidra addrs) to decompile
    static final String[] FUNCS = {"01977c90"};
    PrintWriter fh; Memory mem; FunctionManager fm; DecompInterface dc;
    void emit(String s){ fh.println(s); }
    long IB=0x100000;
    @Override public void run() throws Exception {
        String out=getScriptArgs().length>0?getScriptArgs()[0]:"resolve_ga.txt";
        fh=new PrintWriter(out); mem=currentProgram.getMemory(); fm=currentProgram.getFunctionManager();
        dc=new DecompInterface(); dc.openProgram(currentProgram);
        for(String h:SLOTS){ Address a=toAddr(Long.parseLong(h,16));
            emit("\nSLOT Ghidra 0x"+h+" (runtime rva 0x"+Long.toHexString(Long.parseLong(h,16)-IB)+")");
            try{ long v=mem.getLong(a); emit("  *slot = Ghidra 0x"+Long.toHexString(v)+
                 "  => runtime rva 0x"+Long.toHexString(v-IB));
                 // peek a few longs at the target
                 Address t=toAddr(v); StringBuilder sb=new StringBuilder("  target[0..0x30]:");
                 for(int i=0;i<6;i++){ try{ sb.append(" 0x"+Long.toHexString(mem.getLong(t.add(8L*i)))); }catch(Exception e){ sb.append(" ??"); } }
                 emit(sb.toString());
            }catch(Exception e){ emit("  (unreadable: "+e+")"); }
        }
        for(String h:FUNCS){ Address a=toAddr(Long.parseLong(h,16));
            Function f=fm.getFunctionContaining(a);
            emit("\n"+"=".repeat(80)+"\nFUNC "+h+(f==null?" NO FUNC":(" -> "+f.getEntryPoint()+" size="+f.getBody().getNumAddresses())));
            if(f!=null && f.getBody().getNumAddresses()<0x4000){ DecompileResults r=dc.decompileFunction(f,150,monitor);
                emit((r!=null&&r.decompileCompleted())?r.getDecompiledFunction().getC():"(fail)"); }
        }
        emit("\n# done"); fh.close(); println("WROTE "+out);
    }
}
