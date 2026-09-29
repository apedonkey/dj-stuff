// Session-1 static locator resolution for the usmap/SDK dumper.
// For each anchor string: find it, list referencing functions, decompile the plausible ones so the
// globals (NamePoolData, GUObjectArray) and the ProcessEvent vtable slot can be read out.
// Run with -process -noanalysis on the tribexr project.
import java.io.PrintWriter;
import java.util.*;
import ghidra.app.script.GhidraScript;
import ghidra.app.decompiler.*;
import ghidra.program.model.address.*;
import ghidra.program.model.listing.*;
import ghidra.program.model.symbol.*;

public class AnchorTrace extends GhidraScript {
    // grouped anchors; decompile functions referencing these
    static final String[] ANCHORS = {
        "gc.MaxObjectsNotConsideredByGC","gc.SizeOfPermanentObjectPool","gc.MaxObjectsInGame", // L2 GUObjectArray
        "ReceiveBeginPlay","ReceiveTick",                                                       // L3 ProcessEvent slot
        "ByteProperty","IntProperty","BoolProperty",                                            // L1 name pool init
    };
    static final long DECMAX=0x1400;
    PrintWriter fh; FunctionManager fm; ReferenceManager rm; DecompInterface dc; Listing lst;
    Set<Address> decompiled=new HashSet<>();
    void emit(String s){ fh.println(s); println(s); }
    String dec(Function f){ long n=f.getBody().getNumAddresses(); if(n>DECMAX) return "(too large "+n+")";
        DecompileResults r=dc.decompileFunction(f,120,monitor);
        return (r!=null&&r.decompileCompleted())?r.getDecompiledFunction().getC():"(fail)"; }
    @Override public void run() throws Exception {
        String out=getScriptArgs().length>0?getScriptArgs()[0]:"anchor_trace.txt";
        fh=new PrintWriter(out); fm=currentProgram.getFunctionManager(); rm=currentProgram.getReferenceManager();
        lst=currentProgram.getListing(); dc=new DecompInterface(); dc.openProgram(currentProgram);
        // locate anchor strings
        Map<String,List<Address>> S=new HashMap<>();
        DataIterator di=lst.getDefinedData(true);
        while(di.hasNext()){ Data d=di.next(); Object v=null; try{v=d.getValue();}catch(Exception e){}
            if(!(v instanceof String)) continue; String s=(String)v;
            for(String a:ANCHORS) if(s.equals(a)) S.computeIfAbsent(a,k->new ArrayList<>()).add(d.getAddress()); }
        // per anchor: referencing functions
        Map<Address,Set<String>> funcAnchors=new LinkedHashMap<>();
        for(String a:ANCHORS){
            List<Address> addrs=S.get(a);
            emit("\n### ANCHOR '"+a+"' "+(addrs==null?"(NOT FOUND)":("@"+addrs)));
            if(addrs==null) continue;
            for(Address sa:addrs){ ReferenceIterator it=rm.getReferencesTo(sa);
                while(it.hasNext()){ Function c=fm.getFunctionContaining(it.next().getFromAddress());
                    if(c!=null){ funcAnchors.computeIfAbsent(c.getEntryPoint(),k->new TreeSet<>()).add(a);
                        emit("    ref from "+c.getEntryPoint()+" size="+c.getBody().getNumAddresses()); } } }
        }
        // decompile functions that reference >=1 gc.* or ReceiveBeginPlay or >=2 property names
        emit("\n\n======== DECOMPILATIONS ========");
        for(Map.Entry<Address,Set<String>> e: funcAnchors.entrySet()){
            Set<String> as=e.getValue();
            boolean gc=as.stream().anyMatch(x->x.startsWith("gc."));
            boolean rbp=as.contains("ReceiveBeginPlay")||as.contains("ReceiveTick");
            long nprop=as.stream().filter(x->x.endsWith("Property")).count();
            if(!(gc||rbp||nprop>=2)) continue;
            Function f=fm.getFunctionContaining(e.getKey());
            if(f==null||!decompiled.add(f.getEntryPoint())) continue;
            emit("\n"+"=".repeat(90));
            emit("FUNC "+f.getEntryPoint()+" size="+f.getBody().getNumAddresses()+" anchors="+as);
            emit("-".repeat(90)); emit(dec(f));
        }
        emit("\n# done"); fh.close(); println("WROTE "+out);
    }
}
