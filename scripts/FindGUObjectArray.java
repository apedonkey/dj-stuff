// Locate GUObjectArray: decompile UObjectBaseInit + the functions that reference the gc.* cvars
// (they configure GUObjectArray). The big DAT_ global they operate on / pass to the pool allocator
// is GUObjectArray. Runtime RVA = Ghidra addr - 0x100000. Run: -process libUnreal.so -noanalysis.
import java.io.PrintWriter;
import java.util.*;
import ghidra.app.script.GhidraScript;
import ghidra.app.decompiler.*;
import ghidra.program.model.address.*;
import ghidra.program.model.listing.*;
import ghidra.program.model.symbol.*;

public class FindGUObjectArray extends GhidraScript {
    static final String[] ANCHORS = {
        "gc.MaxObjectsInGame","gc.MaxObjectsNotConsideredByGC","gc.SizeOfPermanentObjectPool","gc.MaxObjectsInEditor"
    };
    static final String[] FUNCS = {"0197bbd8"}; // UObjectBaseInit (Ghidra addr; runtime -0x100000)
    PrintWriter fh; FunctionManager fm; ReferenceManager rm; DecompInterface dc; Listing lst;
    Set<Address> done=new HashSet<>();
    void emit(String s){ fh.println(s); }
    String dec(Function f){ if(f==null) return "(null func)"; long n=f.getBody().getNumAddresses();
        if(n>0x6000) return "(too large "+n+")";
        DecompileResults r=dc.decompileFunction(f,150,monitor);
        return (r!=null&&r.decompileCompleted())?r.getDecompiledFunction().getC():"(fail)"; }
    void decAddr(Address a, String label){
        Function f=fm.getFunctionContaining(a);
        emit("\n"+rep("=",90));
        if(f==null){ emit(label+" @"+a+" NO FUNC"); return; }
        if(!done.add(f.getEntryPoint())){ emit(label+" -> FUNC "+f.getEntryPoint()+" (already dumped)"); return; }
        emit(label+" -> FUNC "+f.getEntryPoint()+" size="+f.getBody().getNumAddresses());
        emit(rep("-",90)); emit(dec(f));
    }
    @Override public void run() throws Exception {
        String out=getScriptArgs().length>0?getScriptArgs()[0]:"guobj.txt";
        fh=new PrintWriter(out); fm=currentProgram.getFunctionManager(); rm=currentProgram.getReferenceManager();
        lst=currentProgram.getListing(); dc=new DecompInterface(); dc.openProgram(currentProgram);
        for(String h:FUNCS) decAddr(toAddr(Long.parseLong(h,16)), "FUNC "+h);
        Map<String,List<Address>> S=new HashMap<>();
        DataIterator di=lst.getDefinedData(true);
        while(di.hasNext()){ Data d=di.next(); Object v=null; try{v=d.getValue();}catch(Exception e){}
            if(!(v instanceof String)) continue; String s=(String)v;
            for(String a:ANCHORS) if(s.equals(a)) S.computeIfAbsent(a,k->new ArrayList<>()).add(d.getAddress()); }
        for(String a:ANCHORS){ List<Address> addrs=S.get(a);
            emit("\n### ANCHOR '"+a+"' "+(addrs==null?"(NOT FOUND)":("@"+addrs)));
            if(addrs==null) continue;
            for(Address sa:addrs){ for(ReferenceIterator it=rm.getReferencesTo(sa); it.hasNext();){
                decAddr(it.next().getFromAddress(), "ref to '"+a+"'"); } } }
        emit("\n# done"); fh.close(); println("WROTE "+out);
    }
    static String rep(String s,int n){StringBuilder b=new StringBuilder();for(int i=0;i<n;i++)b.append(s);return b.toString();}
}
