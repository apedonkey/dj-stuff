// Whole-binary hunt for UObject::ProcessEvent / ProcessInternal: the (nearly) unique function that reads
// a UFunction's ParmsSize (uint16 @ +0xB6) AND performs a dynamic stack alloca (sub sp,sp,x<reg>) to hold
// the params. Reports every function with BOTH traits. Ghidra addr - 0x100000 = runtime RVA.
import java.io.PrintWriter;
import ghidra.app.script.GhidraScript;
import ghidra.program.model.listing.*;
public class FindPE2 extends GhidraScript {
  long IB=0x100000L;
  @Override public void run() throws Exception {
    String out=getScriptArgs().length>0?getScriptArgs()[0]:"pe2.txt";
    PrintWriter fh=new PrintWriter(out);
    FunctionManager fm=currentProgram.getFunctionManager();
    int scanned=0, hits=0;
    for(Function f: fm.getFunctions(true)){
      long sz=f.getBody().getNumAddresses();
      if(sz<0x40) continue;
      boolean parms=false, dyn=false, nat=false; int cnt=0;
      for(Instruction ins=getInstructionAt(f.getEntryPoint()); ins!=null && cnt<1200; ins=ins.getNext(), cnt++){
        if(!f.getBody().contains(ins.getAddress())) break;
        String m=ins.toString().toLowerCase().replace(" ","");
        if((m.startsWith("ldrh")||m.startsWith("ldurh")) && m.contains("0xb6]")) parms=true;
        if(m.startsWith("sub") && m.contains("sp,sp,x")) dyn=true;
        if(m.contains("0x400")) nat=true;
      }
      scanned++;
      if(parms){ hits++;                             // any function reading ParmsSize@0xb6 (ProcessEvent among them)
        fh.println("PARMS rva=0x"+Long.toHexString(f.getEntryPoint().getOffset()-IB)
          +"  dynSp="+dyn+" nat0x400="+nat+"  size="+sz+"  name="+f.getName()); }
    }
    fh.println("# scanned="+scanned+" parmsHits="+hits);
    fh.close(); println("WROTE "+out+" parmsHits="+hits);
  }
}
