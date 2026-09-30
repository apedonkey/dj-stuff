// Dump N instructions starting at each RVA arg (after the output file). Ghidra addr = RVA + 0x100000.
// Confirms a vtable target is a real function prologue (stp x29,x30 / mov x29,sp / sub sp,...).
import java.io.PrintWriter;
import ghidra.app.script.GhidraScript;
import ghidra.program.model.address.Address; import ghidra.program.model.listing.*;
public class DisasmAt extends GhidraScript {
  long IB=0x100000L;
  @Override public void run() throws Exception {
    String[] a=getScriptArgs(); String out=a[0];
    PrintWriter fh=new PrintWriter(out);
    for(int i=1;i<a.length;i++){
      long rva=Long.parseLong(a[i].replace("0x",""),16);
      Address at=toAddr(rva+IB);
      Function fe=getFunctionAt(at);
      fh.println("\n=== rva=0x"+Long.toHexString(rva)+" ghidra=0x"+Long.toHexString(rva+IB)
        +"  isFunctionEntry="+(fe!=null)+(fe!=null?(" name="+fe.getName()):"")+" ===");
      Instruction ins=getInstructionAt(at); int c=0;
      for(; ins!=null && c<32; ins=ins.getNext(), c++)
        fh.println("  "+ins.getAddress()+"  "+ins.toString());
    }
    fh.println("# done"); fh.close(); println("WROTE "+out);
  }
}
