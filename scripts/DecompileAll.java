// DecompileAll: every function of the current program, decompiled into one file, in address order (for small libraries
// such as libacidsynth.so). Args: <out.c> [max bytes, default 65536] [timeout s, default 120] [function name ...]
// With names, only those functions (e.g. libacidsynth's generated call_root / create_root, 100+ KB each).
import java.io.*; import java.util.*;
import ghidra.app.script.GhidraScript; import ghidra.app.decompiler.*;
import ghidra.program.model.listing.*;
public class DecompileAll extends GhidraScript {
  @Override public void run() throws Exception {
    String[] a=getScriptArgs(); long max=a.length>1?Long.parseLong(a[1]):0x10000; int tmo=a.length>2?Integer.parseInt(a[2]):120;
    Set<String> only=new HashSet<>(); for(int i=3;i<a.length;i++) only.add(a[i]);
    DecompInterface dc=new DecompInterface();
    DecompileOptions opts=new DecompileOptions(); opts.grabFromProgram(currentProgram); opts.setMaxPayloadMBytes(1024);
    dc.setOptions(opts); dc.openProgram(currentProgram);                   // generated DSP functions overflow the default 50 MB
    int n=0, fail=0;
    try(PrintWriter pw=new PrintWriter(new File(a[0]),"UTF-8")){
      pw.println("// "+currentProgram.getName()+": "+(only.isEmpty()?"every function":String.join(", ",only))+", decompiled by scripts/DecompileAll.java (Tribe XR build 2304)");
      for(Function f:currentProgram.getFunctionManager().getFunctions(true)){
        if(monitor.isCancelled()) break;
        if(!only.isEmpty()&&!only.contains(f.getName())) continue;
        long size=f.getBody().getNumAddresses();
        pw.println("\n// ===== "+f.getName()+" @ "+f.getEntryPoint()+" ("+size+" bytes"+(f.isExternal()?", external":"")+")");
        if(f.isExternal()||f.isThunk()) { pw.println("// (thunk/external)"); continue; }
        if(size>max){ pw.println("// (too large to decompile: over "+max+" bytes)"); continue; }
        long t0=System.currentTimeMillis();
        DecompileResults r=dc.decompileFunction(f,tmo,monitor);
        if(r!=null&&r.decompileCompleted()) pw.println(r.getDecompiledFunction().getC());
        else { pw.println("// (decompile failed: "+(r==null?"null":r.getErrorMessage())+")"); fail++; }
        pw.flush(); n++;
        if(!only.isEmpty()) println(f.getName()+": "+((System.currentTimeMillis()-t0)/1000)+" s"); } }
    println("DONE: "+n+" functions decompiled, "+fail+" failed -> "+a[0]);
  }
}
