// Decompile every function whose entry lies in [start, end) (Ghidra addresses, hex) and keep the ones whose C mentions any
// of the needles (comma-separated). args: <out file> <start> <end> <needle,needle,...>
// (2026-10-27: finding the producer of TribeVideoCallManager's video frames: +0x908 buffer, +0x6b8 ready state.)
import java.io.PrintWriter;
import ghidra.app.script.GhidraScript; import ghidra.app.decompiler.*;
import ghidra.program.model.address.*; import ghidra.program.model.listing.*;
public class DecompRangeGrep extends GhidraScript {
  @Override public void run() throws Exception {
    String[] a=getScriptArgs(); PrintWriter fh=new PrintWriter(a[0]);
    Address s=toAddr(Long.parseLong(a[1].replace("0x",""),16)), e=toAddr(Long.parseLong(a[2].replace("0x",""),16));
    String[] needles=a[3].split(",");
    DecompInterface dc=new DecompInterface(); dc.openProgram(currentProgram);
    int n=0, kept=0;
    for(Function f: currentProgram.getFunctionManager().getFunctions(new AddressSet(s,e),true)){
      n++; DecompileResults r=dc.decompileFunction(f,60,monitor);
      if(r==null||!r.decompileCompleted()) continue;
      String c=r.getDecompiledFunction().getC(); boolean hit=false; StringBuilder which=new StringBuilder();
      for(String nd: needles) if(c.contains(nd)){ hit=true; which.append(nd).append(' '); }
      if(!hit) continue; kept++;
      fh.println("\n"+"=".repeat(96)+"\nFUNC "+f.getEntryPoint()+" "+f.getName()+" size="+f.getBody().getNumAddresses()+" hits: "+which);
      fh.println(c);
    }
    fh.println("# done: "+n+" functions, "+kept+" kept"); fh.close(); println("WROTE "+a[0]+" ("+n+" functions, "+kept+" kept)");
  }
}
