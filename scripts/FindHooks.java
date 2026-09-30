// Locate the diagnostic-hook targets: callers of FUN_04bde120 (glTFRuntime LoadSkeletalMeshRecursiveAsync),
// and the functions referencing the AddError / Finalize / traversal anchor strings. Ghidra addr - 0x100000 = RVA.
import java.io.PrintWriter; import java.util.*;
import ghidra.app.script.GhidraScript; import ghidra.app.decompiler.*;
import ghidra.program.model.address.*; import ghidra.program.model.listing.*; import ghidra.program.model.symbol.*;
public class FindHooks extends GhidraScript {
  static final long TARGET=0x04bde120L;
  static final String[] ANCHORS={"CreateSkeletalMeshFromLODs","LOD_%d_Section_%d_%s","TraverseJoints",
      "GetRootBoneIndex","FinalizeSkeletalMeshWithLODs","LoadSkeletalMesh"};
  PrintWriter fh; FunctionManager fm; ReferenceManager rm; DecompInterface dc; Listing lst; long IB=0x100000;
  void emit(String s){ fh.println(s); }
  String dec(Function f){ if(f==null)return"(null)"; long n=f.getBody().getNumAddresses(); if(n>0x4000)return"(too large "+n+")";
    DecompileResults r=dc.decompileFunction(f,150,monitor); return (r!=null&&r.decompileCompleted())?r.getDecompiledFunction().getC():"(fail)"; }
  @Override public void run() throws Exception {
    String out=getScriptArgs().length>0?getScriptArgs()[0]:"find_hooks.txt";
    fh=new PrintWriter(out); fm=currentProgram.getFunctionManager(); rm=currentProgram.getReferenceManager();
    lst=currentProgram.getListing(); dc=new DecompInterface(); dc.openProgram(currentProgram);
    // callers of TARGET
    Function tf=fm.getFunctionContaining(toAddr(TARGET));
    emit("### callers of FUN_"+Long.toHexString(TARGET)+" (entry = glTFRuntime async load):");
    Set<Address> callers=new LinkedHashSet<>();
    if(tf!=null) for(ReferenceIterator it=rm.getReferencesTo(tf.getEntryPoint()); it.hasNext();){ Reference r=it.next();
      if(!r.getReferenceType().isCall()) continue; Function c=fm.getFunctionContaining(r.getFromAddress()); if(c!=null) callers.add(c.getEntryPoint()); }
    for(Address c:callers){ Function cf=fm.getFunctionContaining(c);
      emit("\n=== CALLER "+c+" (rva 0x"+Long.toHexString(c.getOffset()-IB)+") size="+cf.getBody().getNumAddresses());
      emit(dec(cf)); }
    // anchor strings -> referencing functions
    emit("\n\n### anchor-string referencing functions:");
    DataIterator di=lst.getDefinedData(true); Map<String,Set<Address>> hits=new LinkedHashMap<>();
    while(di.hasNext()){ Data d=di.next(); Object v=null; try{v=d.getValue();}catch(Exception e){} if(!(v instanceof String))continue; String s=(String)v;
      for(String a:ANCHORS) if(s.contains(a)){ for(ReferenceIterator it=rm.getReferencesTo(d.getAddress()); it.hasNext();){
        Function c=fm.getFunctionContaining(it.next().getFromAddress()); if(c!=null) hits.computeIfAbsent(a,k->new LinkedHashSet<>()).add(c.getEntryPoint()); } } }
    for(String a:ANCHORS){ Set<Address> fs=hits.get(a); emit("\n'"+a+"': "+(fs==null?"(none)":""));
      if(fs!=null) for(Address c:fs){ Function cf=fm.getFunctionContaining(c); emit("   "+c+" (rva 0x"+Long.toHexString(c.getOffset()-IB)+") size="+(cf!=null?cf.getBody().getNumAddresses():0)); } }
    emit("\n# done"); fh.close(); println("WROTE "+out);
  }
}
