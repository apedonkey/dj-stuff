// Third-touch trace: find the guaranteed-at-spawn avatar-load path and the Meta-vs-RPM decision point.
// Reverse-call tree (depth 2) + decompile of each seed and its callers. Run with -process -noanalysis.
import java.io.PrintWriter;
import java.util.*;
import ghidra.app.script.GhidraScript;
import ghidra.app.decompiler.*;
import ghidra.program.model.address.Address;
import ghidra.program.model.listing.*;
import ghidra.program.model.symbol.*;

public class SpawnTrace extends GhidraScript {
    static final String[] SEEDS = {
        "050f5a00", // RPM component invoker (reads this+0x2A8 -> FUN_050f49cc)
        "050f49cc", // RPM resolver
        "050f4548", // glTF file-load choke (Hook B target)
        "04ba868c", // Meta preset zip:// URI builder
        "050fc054", // GetAvatarTypeForId (proven off spawn path; ref only)
    };
    static final int DEPTH = 2;
    static final long MAXDEC = 0xA000;
    static final int CAP = 70;
    PrintWriter fh; FunctionManager fm; ReferenceManager rm; DecompInterface dc;
    Set<Address> decompiled = new HashSet<>();
    int count = 0;
    void emit(String s){ fh.println(s); println(s); }
    static String rep(String s,int n){StringBuilder b=new StringBuilder();for(int i=0;i<n;i++)b.append(s);return b.toString();}
    List<Function> callersOf(Function f){
        List<Function> o=new ArrayList<>(); Set<Address> seen=new HashSet<>();
        ReferenceIterator it=rm.getReferencesTo(f.getEntryPoint());
        while(it.hasNext()){ Reference r=it.next();
            Function c=fm.getFunctionContaining(r.getFromAddress());
            if(c!=null && seen.add(c.getEntryPoint())) o.add(c);
        }
        return o;
    }
    String dec(Function f){ long n=f.getBody().getNumAddresses();
        if(n>MAXDEC)return "(too large "+n+" addrs)";
        DecompileResults r=dc.decompileFunction(f,150,monitor);
        return (r!=null&&r.decompileCompleted())?r.getDecompiledFunction().getC():"(decompile fail)"; }
    void dumpFunc(Function f,String tag){
        if(f==null||count>=CAP) return;
        if(!decompiled.add(f.getEntryPoint())) return;
        count++;
        emit("\n"+rep("=",96));
        emit("FUNC "+f.getEntryPoint()+" "+f.getName()+" size="+f.getBody().getNumAddresses()+" ["+tag+"]");
        emit(rep("-",96)); emit(dec(f));
    }
    void reverse(Function f,int depth,String path){
        List<Function> cs=callersOf(f);
        StringBuilder ids=new StringBuilder();
        for(Function c:cs) ids.append(c.getEntryPoint()).append("(").append(c.getName()).append(") ");
        emit("CALLERS of "+f.getEntryPoint()+" ["+path+"]: "+(cs.isEmpty()?"(none - root or virtual-only)":ids.toString()));
        if(depth<=0) return;
        for(Function c:cs){ dumpFunc(c,"caller of "+f.getName()); reverse(c,depth-1,path+"<-"+c.getEntryPoint()); }
    }
    @Override public void run() throws Exception {
        String out=getScriptArgs().length>0?getScriptArgs()[0]:"spawn_trace.txt";
        fh=new PrintWriter(out); fm=currentProgram.getFunctionManager(); rm=currentProgram.getReferenceManager();
        dc=new DecompInterface(); dc.openProgram(currentProgram);
        for(String h:SEEDS){
            Address a=toAddr(Long.parseLong(h,16)); Function f=fm.getFunctionContaining(a);
            emit("\n"+rep("#",96)+"\n# SEED "+h+(f!=null?" ("+f.getName()+")":" (NO FUNC)")+"\n"+rep("#",96));
            if(f==null) continue;
            dumpFunc(f,"seed "+h);
            reverse(f,DEPTH,h);
        }
        emit("\n# done  (decompiled "+count+" funcs)"); fh.close(); println("WROTE "+out);
    }
}
