// Resolve a few globals: dereference pointer globals to the string/FString they point at, and
// list + decompile the functions that WRITE each global (to find the runtime path setter).
// Run with -process -noanalysis.
import java.io.PrintWriter;
import java.util.*;
import ghidra.app.script.GhidraScript;
import ghidra.app.decompiler.*;
import ghidra.program.model.address.Address;
import ghidra.program.model.listing.*;
import ghidra.program.model.mem.*;
import ghidra.program.model.symbol.*;

public class GlobalsResolve extends GhidraScript {
    static final String[] GLOBALS = { "07ba1cf8", "07ba1c58", "07ba2d90", "07ba5998", "07ba2d90" };
    PrintWriter fh; Memory mem; FunctionManager fm; ReferenceManager rm; DecompInterface dc;
    void emit(String s){ fh.println(s); println(s); }

    String readWide(Address a, int max){
        StringBuilder b=new StringBuilder();
        try{ for(int i=0;i<max;i++){ int c=mem.getShort(a.add(2L*i))&0xffff; if(c==0)break; b.append((char)c);} }
        catch(Exception e){ return "(unreadable)"; }
        return b.toString();
    }
    String readAscii(Address a, int max){
        StringBuilder b=new StringBuilder();
        try{ for(int i=0;i<max;i++){ int c=mem.getByte(a.add(i))&0xff; if(c==0)break; if(c<0x20||c>0x7e){return null;} b.append((char)c);} }
        catch(Exception e){ return null; }
        return b.toString();
    }
    Address deref(Address a){ try{ long v=mem.getLong(a); return v==0?null:toAddr(v);}catch(Exception e){return null;} }

    @Override public void run() throws Exception {
        String out=getScriptArgs().length>0?getScriptArgs()[0]:"globals.txt";
        fh=new PrintWriter(out); mem=currentProgram.getMemory(); fm=currentProgram.getFunctionManager();
        rm=currentProgram.getReferenceManager(); dc=new DecompInterface(); dc.openProgram(currentProgram);
        Set<Address> dumped=new HashSet<>();
        for(String h:GLOBALS){
            Address g=toAddr(Long.parseLong(h,16));
            emit("\n"+rep("=",90)+"\nGLOBAL "+g);
            Address p=deref(g);
            emit("  *global = "+p);
            if(p!=null){
                String w=readWide(p,120); String asc=readAscii(p,120);
                if(asc!=null && asc.length()>=2) emit("  ascii@*: \""+asc+"\"");
                if(w.length()>=2) emit("  wide@* : \""+w+"\"");
                Address pp=deref(p);
                if(pp!=null){ String w2=readWide(pp,120); if(w2.length()>=2) emit("  wide@**: \""+w2+"\""); }
            }
            // who writes this global
            int nw=0;
            for(ReferenceIterator it=rm.getReferencesTo(g); it.hasNext();){
                Reference r=it.next();
                if(!r.getReferenceType().isWrite()) continue;
                Function f=fm.getFunctionContaining(r.getFromAddress());
                if(f!=null && dumped.add(f.getEntryPoint())){
                    emit("  written by FUNC "+f.getEntryPoint()+" (size "+f.getBody().getNumAddresses()+")");
                    if(nw<2 && f.getBody().getNumAddresses()<0x2000){
                        DecompileResults dr=dc.decompileFunction(f,90,monitor);
                        if(dr!=null&&dr.decompileCompleted()){ emit(rep("-",60)); emit(dr.getDecompiledFunction().getC()); }
                        nw++;
                    }
                }
            }
        }
        emit("\n# done"); fh.close(); println("WROTE "+out);
    }
    static String rep(String s,int n){StringBuilder b=new StringBuilder();for(int i=0;i<n;i++)b.append(s);return b.toString();}
}
