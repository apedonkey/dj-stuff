// NativeDecomp: decompile Tribe's C++ from the hook's native dump (hook/native.cpp -> scripts/native_prep.py).
// Input TSV, one function per line:  <group> \t <kind> \t <label> \t <runtime rva hex> \t <impl label>
//   kind thunk = a UFunction's exec thunk (UFunction::Func); vfunc = a vtable entry the class overrides.
// For each thunk, the native implementation is the callee that is not one of the helpers most thunks share
// (FFrame::Step and friends: callees of >= <helpers> thunks). Thunks, implementations and overrides that still
// carry Ghidra's default FUN_ name get the label (<Class>::exec<Name>, <Class>::<Name>, <Class>::vfunc<slot>), so
// the project reads better from then on; then everything is decompiled into <outdir>/<group>.c.
// Address: Ghidra = rva + 0xFF000 (NOTES' calibration: runtime = base + (ghidra - 0x100000) + 0x1000), checked on
// the first thunks against +0x100000. Args: <in.tsv> <outdir> [helpers=25]
import java.io.*; import java.util.*;
import ghidra.app.script.GhidraScript; import ghidra.app.decompiler.*;
import ghidra.program.model.address.*; import ghidra.program.model.listing.*;
import ghidra.program.model.symbol.*;
public class NativeDecomp extends GhidraScript {
  static class E { String group, kind, label, impl; long rva; Function f; List<Function> impls=new ArrayList<>(); }
  long skew=0xFF000L; DecompInterface dc;
  Function fnAt(long rva) throws Exception {
    Address a=toAddr(rva+skew); Function f=getFunctionAt(a);
    if(f==null && getInstructionAt(a)==null) disassemble(a);
    if(f==null) f=createFunction(a,null);
    return f; }
  void rename(Function f,String label){              // Ghidra's FUN_ names, and our own earlier slot-number labels
    if(f==null||!(f.getName().startsWith("FUN_")||f.getName().matches(".*__(vfunc|newvirtual)\\d+"))) return;
    try{ f.setName(label.replace(' ','_').replace("::","__"),SourceType.USER_DEFINED); }catch(Exception e){ println("rename "+label+": "+e.getMessage()); } }
  String dec(Function f){
    if(f==null) return "(no function)";
    long n=f.getBody().getNumAddresses(); if(n>0x10000) return "(too large to decompile: "+n+" bytes)";
    DecompileResults r=dc.decompileFunction(f,90,monitor);
    return (r!=null&&r.decompileCompleted())? r.getDecompiledFunction().getC() : "(decompile failed: "+(r==null?"null":r.getErrorMessage())+")"; }
  @Override public void run() throws Exception {
    String[] a=getScriptArgs(); int helperMin=a.length>2?Integer.parseInt(a[2]):25;
    List<E> es=new ArrayList<>();
    try(BufferedReader br=new BufferedReader(new FileReader(a[0]))){ String line;
      while((line=br.readLine())!=null){ String[] t=line.split("\t"); if(t.length<4) continue;
        E e=new E(); e.group=t[0]; e.kind=t[1]; e.label=t[2]; e.rva=Long.parseLong(t[3].replace("0x",""),16); e.impl=t.length>4?t[4]:""; es.add(e); } }
    // which skew lands on function starts?
    int hitA=0,hitB=0,k=0;
    for(E e:es){ if(!e.kind.equals("thunk")) continue; if(k++>=60) break;
      if(getFunctionAt(toAddr(e.rva+0xFF000L))!=null) hitA++; if(getFunctionAt(toAddr(e.rva+0x100000L))!=null) hitB++; }
    skew= hitB>hitA? 0x100000L : 0xFF000L;
    println("skew check on "+k+" thunks: +0xFF000 "+hitA+" function starts, +0x100000 "+hitB+" -> using +0x"+Long.toHexString(skew));
    // pass 1: functions and thunk callees
    Map<Function,Integer> freq=new HashMap<>();
    for(E e:es){ e.f=fnAt(e.rva); if(e.f==null||!e.kind.equals("thunk")) continue;
      for(Function c:e.f.getCalledFunctions(monitor)) freq.merge(c,1,Integer::sum); }
    Set<Function> helpers=new HashSet<>(); for(Map.Entry<Function,Integer> m:freq.entrySet()) if(m.getValue()>=helperMin) helpers.add(m.getKey());
    println(es.size()+" entries, "+helpers.size()+" shared helpers (called by >= "+helperMin+" thunks)");
    // pass 2: names
    int named=0;
    for(E e:es){ if(e.f==null) continue; String before=e.f.getName(); rename(e.f,e.label); if(!before.equals(e.f.getName())) named++;
      if(!e.kind.equals("thunk")) continue;
      List<Function> cs=new ArrayList<>(e.f.getCalledFunctions(monitor)); cs.removeIf(helpers::contains);
      cs.sort(Comparator.comparing(Function::getEntryPoint)); e.impls=cs;
      if(cs.size()==1){ String b=cs.get(0).getName(); rename(cs.get(0),e.impl); if(!b.equals(cs.get(0).getName())) named++; } }
    println("named "+named+" functions");
    // pass 3: decompile, one file per group
    dc=new DecompInterface(); dc.openProgram(currentProgram);
    Map<String,List<E>> groups=new LinkedHashMap<>(); for(E e:es) groups.computeIfAbsent(e.group,x->new ArrayList<>()).add(e);
    new File(a[1]).mkdirs(); int done=0;
    for(Map.Entry<String,List<E>> g:groups.entrySet()){
      try(PrintWriter pw=new PrintWriter(new File(a[1],g.getKey()+".c"),"UTF-8")){
        pw.println("// "+g.getKey()+": decompiled by scripts/NativeDecomp.java from libUnreal.so (Tribe XR build 2304)");
        for(E e:g.getValue()){ if(monitor.isCancelled()) return;
          String at=e.f==null?"?":e.f.getEntryPoint().toString();
          pw.println("\n// ===== "+e.label+"  ["+e.kind+", rva 0x"+Long.toHexString(e.rva)+", ghidra "+at+"]");
          pw.println(dec(e.f));
          for(Function c:e.impls){ pw.println("// ----- callee "+c.getName()+" @ "+c.getEntryPoint());
            pw.println(e.impls.size()<=3? dec(c) : "(not expanded: "+e.impls.size()+" callees)"); }
          done++; } }
      if(done%200<g.getValue().size()) println("decompiled "+done+" of "+es.size()); }
    println("DONE: "+done+" functions in "+groups.size()+" files");
  }
}
