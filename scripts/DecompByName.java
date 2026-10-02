// Decompile functions by symbol name (args after the output file are names). For libraries whose exported API names we
// know (e.g. libOVRPlugin.so ovrp_*), this confirms parameter counts/out-pointers before hooking them.
import java.io.PrintWriter;
import java.util.List;
import ghidra.app.script.GhidraScript; import ghidra.app.decompiler.*;
import ghidra.program.model.listing.*;
public class DecompByName extends GhidraScript {
  @Override public void run() throws Exception {
    String[] a=getScriptArgs(); PrintWriter fh=new PrintWriter(a[0]);
    DecompInterface dc=new DecompInterface(); dc.openProgram(currentProgram);
    for(int i=1;i<a.length;i++){
      String nm=a[i]; fh.println("\n"+"=".repeat(96)+"\n"+nm);
      List<Function> fs=getGlobalFunctions(nm);
      if(fs==null||fs.isEmpty()){ fh.println("(not found)"); continue; }
      for(Function f:fs){
        fh.println("@ "+f.getEntryPoint()+"  params="+f.getParameterCount()+"  sig: "+f.getSignature().getPrototypeString());
        DecompileResults r=dc.decompileFunction(f,180,monitor);
        fh.println((r!=null&&r.decompileCompleted())?r.getDecompiledFunction().getC():"(decompile failed)");
      }
    }
    fh.close(); println("WROTE "+a[0]);
  }
}
