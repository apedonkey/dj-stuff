// Path-2 native trace: locate the skin/avatar BP-callable natives + confirm the config-URL read.
// For each target name string: find it, list functions referencing it (exec thunk / registration),
// and decompile small referencing functions. Plus decompile known anchor functions.
// Run with -process -noanalysis on the tribexr project.
import java.io.PrintWriter;
import java.util.*;
import ghidra.app.script.GhidraScript;
import ghidra.app.decompiler.*;
import ghidra.program.model.address.*;
import ghidra.program.model.listing.*;
import ghidra.program.model.symbol.*;
import ghidra.program.model.mem.*;

public class SkinTrace extends GhidraScript {
    static final String[] NAMES = {
        "GetTribeDefaultAvatarId","SetAvatarID","AddActiveSkin","ApplyActiveSkins",
        "ReadConfigString","GetDefaultSkinClass","GetSkinClass","ReadyPlayerMeAvatarUrl",
    };
    // known anchors (Ghidra addrs; real vaddr = ghidra - 0x100000)
    static final String[] ANCHORS = {"050f584c"};
    PrintWriter fh; FunctionManager fm; ReferenceManager rm; DecompInterface dc;
    void emit(String s){ fh.println(s); println(s); }
    String dec(Function f){ if(f==null) return "(none)"; long n=f.getBody().getNumAddresses();
        if(n>0x6000) return "(too large "+n+")";
        DecompileResults r=dc.decompileFunction(f,120,monitor);
        return (r!=null&&r.decompileCompleted())?r.getDecompiledFunction().getC():"(fail)"; }
    @Override public void run() throws Exception {
        String out=getScriptArgs().length>0?getScriptArgs()[0]:"skin_trace.txt";
        fh=new PrintWriter(out); fm=currentProgram.getFunctionManager(); rm=currentProgram.getReferenceManager();
        dc=new DecompInterface(); dc.openProgram(currentProgram);
        Listing lst=currentProgram.getListing();
        // map: name string -> addresses where that exact string is defined
        Map<String,List<Address>> found=new HashMap<>();
        DataIterator di=lst.getDefinedData(true);
        while(di.hasNext()){
            Data d=di.next(); Object v=null; try{ v=d.getValue(); }catch(Exception e){}
            if(!(v instanceof String)) continue;
            String s=(String)v;
            for(String t:NAMES) if(s.equals(t)) found.computeIfAbsent(t,k->new ArrayList<>()).add(d.getAddress());
        }
        for(String t:NAMES){
            emit("\n############ NAME '"+t+"' ############");
            List<Address> addrs=found.get(t);
            if(addrs==null){ emit("  (string not found as exact defined string)"); continue; }
            Set<Address> seenF=new HashSet<>();
            for(Address sa: addrs){
                emit("  string @"+sa);
                ReferenceIterator it=rm.getReferencesTo(sa);
                while(it.hasNext()){
                    Reference r=it.next(); Function c=fm.getFunctionContaining(r.getFromAddress());
                    if(c!=null && seenF.add(c.getEntryPoint()))
                        emit("    ref from FUNC "+c.getEntryPoint()+" size="+c.getBody().getNumAddresses());
                }
            }
        }
        for(String h:ANCHORS){
            Function f=fm.getFunctionContaining(toAddr(Long.parseLong(h,16)));
            emit("\n############ ANCHOR "+h+" ("+(f!=null?f.getName():"?")+") ############");
            emit(dec(f));
        }
        emit("\n# done"); fh.close(); println("WROTE "+out);
    }
}
