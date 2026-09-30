// Decompile specific functions by RVA (args after the output file are hex RVAs). Ghidra addr = RVA + 0x100000.
// Used to confirm UObject::ProcessEvent (reads Function->ParmsSize@0xb6, allocs a frame, tests FUNC_Native
// 0x400, calls Function->Func) vs ProcessInternal, and to read any native impl of interest.
import java.io.PrintWriter;
import ghidra.app.script.GhidraScript; import ghidra.app.decompiler.*;
import ghidra.program.model.address.Address; import ghidra.program.model.listing.*;
public class DecompAt extends GhidraScript {
  long IB=0x100000L;
  @Override public void run() throws Exception {
    String[] a=getScriptArgs(); String out=a[0];
    PrintWriter fh=new PrintWriter(out); DecompInterface dc=new DecompInterface(); dc.openProgram(currentProgram);
    for(int i=1;i<a.length;i++){
      long rva=Long.parseLong(a[i].replace("0x",""),16);
      Address fa=toAddr(rva+IB); Function f=getFunctionAt(fa); if(f==null) f=getFunctionContaining(fa);
      fh.println("\n"+"=".repeat(96)+"\nFUNC rva=0x"+Long.toHexString(rva)+" ghidra=0x"+Long.toHexString(rva+IB)
        +"  name="+(f!=null?f.getName():"?")+"  size="+(f!=null?f.getBody().getNumAddresses():0));
      if(f==null){ fh.println("(no function)"); continue; }
      DecompileResults r=dc.decompileFunction(f,150,monitor);
      fh.println((r!=null&&r.decompileCompleted())?r.getDecompiledFunction().getC():"(decompile fail)");
    }
    fh.println("# done"); fh.close(); println("WROTE "+out);
  }
}
