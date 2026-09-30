// Decompile every function that references the given GLOBAL data addresses (Ghidra addrs as args after
// the output file). Targets: the RPM base-URL global, the "AvatarRoot"/"Armature" root-node-name globals,
// and the "bodyType"/"Halfbody"/"Fullbody" metadata globals -- i.e. the metadata fetch + the node-name
// decision that likely drives the empty-mesh bug. Prints each referencing function + its string/data refs.
import java.io.PrintWriter; import java.util.*;
import ghidra.app.script.GhidraScript; import ghidra.app.decompiler.*;
import ghidra.program.model.address.*; import ghidra.program.model.listing.*;
import ghidra.program.model.mem.Memory; import ghidra.program.model.symbol.*;
public class DecompXrefs extends GhidraScript {
  PrintWriter fh; Memory mem; FunctionManager fm; ReferenceManager rm; DecompInterface dc; long IB=0x100000;
  Set<Address> done=new HashSet<>();
  String rdstr(Address a){ try{ StringBuilder b=new StringBuilder(); for(int i=0;i<160;i++){ int c=mem.getByte(a.add(i))&0xff; if(c==0)break; if(c<9||c>0x7e)return null; b.append((char)c);} return b.toString(); }catch(Exception e){return null;} }
  void decFunc(Function f,String why){ if(f==null||!done.add(f.getEntryPoint())) return;
    long n=f.getBody().getNumAddresses();
    fh.println("\n"+"=".repeat(96)+"\nFUNC "+f.getEntryPoint()+" (rva 0x"+Long.toHexString(f.getEntryPoint().getOffset()-IB)+") size="+n+"  ["+why+"]");
    if(n>0x2800){ fh.println("(too large; refs only)"); }
    else { DecompileResults r=dc.decompileFunction(f,120,monitor); fh.println((r!=null&&r.decompileCompleted())?r.getDecompiledFunction().getC():"(fail)"); }
    Set<Address> seen=new HashSet<>(); StringBuilder sb=new StringBuilder();
    for(Address ins=f.getEntryPoint(); ins!=null && f.getBody().contains(ins); ins=ins.next())
      for(Reference r:rm.getReferencesFrom(ins)){ Address t=r.getToAddress(); if(t==null||!t.isMemoryAddress()||!seen.add(t))continue;
        String s=rdstr(t); if(s==null){ try{ long p=mem.getLong(t); s=rdstr(toAddr(p)); }catch(Exception e){} }
        if(s!=null && s.length()>=3 && s.length()<120) sb.append("     \""+s+"\"\n"); }
    if(sb.length()>0){ fh.println("  -- refs --\n"+sb.toString()); }
  }
  @Override public void run() throws Exception {
    String[] a=getScriptArgs(); fh=new PrintWriter(a[0]); mem=currentProgram.getMemory();
    fm=currentProgram.getFunctionManager(); rm=currentProgram.getReferenceManager(); dc=new DecompInterface(); dc.openProgram(currentProgram);
    for(int i=1;i<a.length;i++){
      long g=Long.parseLong(a[i].replace("0x",""),16); Address ga=toAddr(g);
      fh.println("\n\n########## xrefs to global 0x"+Long.toHexString(g)+" (rva 0x"+Long.toHexString(g-IB)+") ##########");
      int cnt=0;
      for(ReferenceIterator it=rm.getReferencesTo(ga); it.hasNext() && cnt<8;){ Reference r=it.next();
        Function f=fm.getFunctionContaining(r.getFromAddress()); if(f!=null){ decFunc(f,"uses 0x"+Long.toHexString(g)); cnt++; } }
      if(cnt==0) fh.println("  (no referencing functions)");
    }
    fh.println("\n# done"); fh.close(); println("WROTE "+a[0]);
  }
}
