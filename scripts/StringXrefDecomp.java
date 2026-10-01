// Decompile every function that references a defined string containing any of the needle substrings
// (args after the output file). Used to find the HTTP auth-header builder (needles: Bearer, nonce, Authorization) and
// the Tribe backend request path, to confirm the backend request consumes the Oculus user token/proof.
// Ghidra addr - 0x100000 = RVA. Prints each referencing function's decompile + its own string refs.
import java.io.PrintWriter; import java.util.*;
import ghidra.app.script.GhidraScript; import ghidra.app.decompiler.*;
import ghidra.program.model.address.*; import ghidra.program.model.listing.*;
import ghidra.program.model.mem.Memory; import ghidra.program.model.symbol.*;
public class StringXrefDecomp extends GhidraScript {
  PrintWriter fh; Memory mem; FunctionManager fm; ReferenceManager rm; DecompInterface dc; Listing lst; long IB=0x100000;
  Set<Address> done=new HashSet<>();
  String rd(Address a){ try{ StringBuilder b=new StringBuilder(); for(int i=0;i<220;i++){ int c=mem.getByte(a.add(i))&0xff; if(c==0)break; if(c<9||c>0x7e)return null; b.append((char)c);} return b.toString(); }catch(Exception e){return null;} }
  String rw(Address a){ try{ StringBuilder b=new StringBuilder(); for(int i=0;i<220;i++){ int c=mem.getShort(a.add(2L*i))&0xffff; if(c==0)break; if(c<9||c>0x7e)return null; b.append((char)c);} return b.length()>2?b.toString():null; }catch(Exception e){return null;} }
  void dec(Function f,String why){ if(f==null||!done.add(f.getEntryPoint())) return;
    long n=f.getBody().getNumAddresses();
    fh.println("\n"+"=".repeat(96)+"\nFUNC "+f.getEntryPoint()+" (rva 0x"+Long.toHexString(f.getEntryPoint().getOffset()-IB)+") size="+n+"  ["+why+"]");
    if(n>0x3800){ fh.println("(too large; string refs only)"); }
    else { DecompileResults r=dc.decompileFunction(f,120,monitor); fh.println((r!=null&&r.decompileCompleted())?r.getDecompiledFunction().getC():"(fail)"); }
    Set<Address> seen=new HashSet<>(); StringBuilder sb=new StringBuilder();
    for(Address ins=f.getEntryPoint(); ins!=null && f.getBody().contains(ins); ins=ins.next())
      for(Reference r:rm.getReferencesFrom(ins)){ Address t=r.getToAddress(); if(t==null||!t.isMemoryAddress()||!seen.add(t))continue;
        String s=rd(t); if(s==null)s=rw(t); if(s==null){ try{ long p=mem.getLong(t); String s2=rd(toAddr(p)); if(s2==null)s2=rw(toAddr(p)); if(s2!=null)s=s2; }catch(Exception e){} }
        if(s!=null && s.length()>=3 && s.length()<200) sb.append("     \""+s+"\"\n"); }
    if(sb.length()>0) fh.println("  -- refs --\n"+sb);
  }
  @Override public void run() throws Exception {
    String[] a=getScriptArgs(); fh=new PrintWriter(a[0]); mem=currentProgram.getMemory(); fm=currentProgram.getFunctionManager();
    rm=currentProgram.getReferenceManager(); lst=currentProgram.getListing(); dc=new DecompInterface(); dc.openProgram(currentProgram);
    List<String> needles=new ArrayList<>(); for(int i=1;i<a.length;i++) needles.add(a[i]);
    Map<Address,String> hits=new LinkedHashMap<>();
    for(DataIterator di=lst.getDefinedData(true); di.hasNext();){ Data d=di.next(); Object v=null; try{v=d.getValue();}catch(Exception e){}
      if(!(v instanceof String))continue; String s=(String)v;
      for(String nd:needles) if(s.contains(nd)){ hits.put(d.getAddress(),s); break; } }
    fh.println("### "+hits.size()+" matching strings:");
    for(Map.Entry<Address,String> e:hits.entrySet()) fh.println("  "+e.getKey()+" (rva 0x"+Long.toHexString(e.getKey().getOffset()-IB)+")  \""+(e.getValue().length()>80?e.getValue().substring(0,80):e.getValue())+"\"");
    for(Map.Entry<Address,String> e:hits.entrySet()){ int cnt=0;
      for(ReferenceIterator it=rm.getReferencesTo(e.getKey()); it.hasNext() && cnt<6;){ Function f=fm.getFunctionContaining(it.next().getFromAddress());
        if(f!=null){ dec(f,"refs \""+(e.getValue().length()>40?e.getValue().substring(0,40):e.getValue())+"\""); cnt++; } } }
    fh.println("\n# done"); fh.close(); println("WROTE "+a[0]);
  }
}
