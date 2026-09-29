// Trace callers of the avatar-type/id/loader functions to determine whether the local avatar's
// TYPE is re-derived from [TribeAvatar] config at spawn, or set only by an explicit selection flow.
// Run with -process -noanalysis on the saved project.
import java.io.PrintWriter;
import java.util.*;
import ghidra.app.script.GhidraScript;
import ghidra.app.decompiler.*;
import ghidra.program.model.address.Address;
import ghidra.program.model.listing.*;
import ghidra.program.model.symbol.*;

public class CallersTrace extends GhidraScript {
    // seeds (impls found in prior phases)
    static final String[] SEEDS = {
        "050fc054", // GetAvatarTypeForId impl (id-format -> type)
        "0518ba70", // reads [TribeAvatar]AvatarID from config
        "050fc6e0", // GetAvatarIdForServer (reads ReadyPlayerMeAvatarUrl)
        "050f49cc", // RPM loader (reads url, builds cache path, loads)
    };
    static final long MAX = 0x8000;
    PrintWriter fh; FunctionManager fm; ReferenceManager rm; DecompInterface dc;
    Set<Address> done = new HashSet<>();
    void emit(String s){ fh.println(s); println(s); }
    static String rep(String s,int n){StringBuilder b=new StringBuilder();for(int i=0;i<n;i++)b.append(s);return b.toString();}
    List<Address> refsTo(Address a){ List<Address> o=new ArrayList<>(); ReferenceIterator it=rm.getReferencesTo(a); while(it.hasNext())o.add(it.next().getFromAddress()); return o; }
    String dec(Function f){ if(f==null)return "(none)"; if(f.getBody().getNumAddresses()>MAX)return "(too large "+f.getBody().getNumAddresses()+")";
        DecompileResults r=dc.decompileFunction(f,150,monitor); return (r!=null&&r.decompileCompleted())?r.getDecompiledFunction().getC():"(fail)"; }
    void dump(Function f,String tag){ if(f==null||!done.add(f.getEntryPoint()))return; emit("\n"+rep("=",96));
        emit("FUNC "+f.getEntryPoint()+" size="+f.getBody().getNumAddresses()+" ["+tag+"]"); emit(rep("-",96)); emit(dec(f)); }
    @Override public void run() throws Exception {
        String out=getScriptArgs().length>0?getScriptArgs()[0]:"callers.txt";
        fh=new PrintWriter(out); fm=currentProgram.getFunctionManager(); rm=currentProgram.getReferenceManager();
        dc=new DecompInterface(); dc.openProgram(currentProgram);
        for(String h: SEEDS){
            Address a=toAddr(Long.parseLong(h,16)); Function f=fm.getFunctionContaining(a);
            if(f==null){ emit("SEED "+h+" no func"); continue; }
            List<Address> callerRefs=refsTo(f.getEntryPoint());
            emit("\n"+rep("#",96)+"\n# SEED "+h+" ("+f.getName()+"): "+callerRefs.size()+" ref(s) to entry\n"+rep("#",96));
            dump(f,"seed "+h);
            for(Address r: callerRefs){ Function c=fm.getFunctionContaining(r); if(c!=null) dump(c,"caller of "+h+" @"+r); }
        }
        emit("\n# done"); fh.close(); println("WROTE "+out);
    }
}
