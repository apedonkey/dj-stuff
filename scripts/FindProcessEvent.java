// Fingerprint UObject::ProcessEvent among the RUNTIME Default__Object vtable slots (static .data.rel.ro
// in Ghidra is relocation-skewed, so we read the runtime slot RVAs from vt_rvas.txt instead). For each
// slot: Ghidra addr = RVA + 0x100000; scan the function for ParmsSize read (ldrh/ldurh [x1,#0xb6]),
// a dynamic stack alloca (sub sp,sp,x<reg> / mov x?,sp after sub), and a FUNC_Native test (0x400 / tbz #10).
import java.io.*;
import java.util.*;
import ghidra.app.script.GhidraScript;
import ghidra.program.model.address.Address;
import ghidra.program.model.listing.*;
public class FindProcessEvent extends GhidraScript {
  long IB=0x100000L;
  @Override public void run() throws Exception {
    String[] a=getScriptArgs();
    String rvaFile=a.length>0?a[0]:"vt_rvas.txt";
    String out=a.length>1?a[1]:"pe.txt";
    PrintWriter fh=new PrintWriter(out);
    BufferedReader br=new BufferedReader(new FileReader(rvaFile));
    String line; int slot=0; ArrayList<String> hits=new ArrayList<>();
    while((line=br.readLine())!=null){
      line=line.trim(); if(line.isEmpty()){ slot++; continue; }
      long rva; try{ rva=Long.parseLong(line,16); }catch(Exception e){ slot++; continue; }
      if(rva==0){ slot++; continue; }
      Address fa=toAddr(rva+IB);
      Function f=getFunctionAt(fa); if(f==null) f=getFunctionContaining(fa);
      boolean parmsSize=false, dynSp=false, nativeTest=false, callInd=false; int cnt=0;
      for(Instruction ins=getInstructionAt(fa); ins!=null && cnt<400; ins=ins.getNext(), cnt++){
        if(f!=null && !f.getBody().contains(ins.getAddress())) break;
        String m=ins.toString().toLowerCase().replace(" ","");
        if((m.startsWith("ldrh")||m.startsWith("ldurh")) && m.contains("0xb6]")) parmsSize=true; // ParmsSize, any base reg
        if(m.startsWith("sub") && m.contains("sp,sp,x")) dynSp=true;                 // alloca(ParmsSize)
        if(m.contains("0x400")) nativeTest=true;
        if(m.startsWith("tbz")||m.startsWith("tbnz")){ if(m.contains(",0xa,")||m.contains(",#0xa,")) nativeTest=true; } // bit10=0x400
        if(m.startsWith("blr")) callInd=true;
      }
      long sz=(f!=null?f.getBody().getNumAddresses():0);
      String rec="slot "+slot+"  rva=0x"+Long.toHexString(rva)+"  parmsSize@0xb6="+parmsSize+" dynSp="+dynSp
        +" native0x400="+nativeTest+" blr="+callInd+"  name="+(f!=null?f.getName():"?")+"  size="+sz;
      if(parmsSize || dynSp) { hits.add(rec); }
      fh.println(rec);
      slot++;
    }
    br.close();
    fh.println("\n### CANDIDATES (parmsSize@0xb6 or dynSp):");
    for(String h:hits) fh.println("  "+h);
    fh.println("# done"); fh.close(); println("WROTE "+out+" ; candidates="+hits.size());
  }
}
