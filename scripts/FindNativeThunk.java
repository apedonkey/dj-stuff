// Resolve UFunction exec thunks BY NAME through the UHT native registration tables
// (FNameNativePtrPair = { const char* NameUTF8; FNativeFuncPtr Pointer; }): find each name's string, find every
// qword pointing at it, and when the following qword points into executable memory that is the exec thunk.
// Decompiles each thunk and its direct callees up to <depth> levels (to read what the native impl does with its
// out-params, e.g. whether it resizes a TArray before indexing it). Args: <out.txt> <depth> <UFunctionName>...
// Ghidra addr - 0x100000 = RVA; runtime = base + RVA + 0x1000 (calibrated skew).
import java.io.PrintWriter; import java.util.*;
import ghidra.app.script.GhidraScript; import ghidra.app.decompiler.*;
import ghidra.program.model.address.*; import ghidra.program.model.listing.*;
import ghidra.program.model.mem.*;
public class FindNativeThunk extends GhidraScript {
  long IB=0x100000; PrintWriter fh; Memory mem; DecompInterface dc; Set<Address> done=new HashSet<>();
  boolean isExec(Address a){ MemoryBlock b=mem.getBlock(a); return b!=null && b.isExecute(); }
  byte[] le64(long v){ byte[] b=new byte[8]; for(int i=0;i<8;i++) b[i]=(byte)(v>>>(8*i)); return b; }
  void dec(Address fa,String why,int depth) throws Exception {
    Function f=getFunctionAt(fa); if(f==null) f=getFunctionContaining(fa);
    if(f==null||!done.add(f.getEntryPoint())) return;
    long n=f.getBody().getNumAddresses();
    fh.println("\n"+"=".repeat(90)+"\nFUNC ghidra="+f.getEntryPoint()+" rva=0x"+Long.toHexString(f.getEntryPoint().getOffset()-IB)+" size="+n+" ["+why+"]");
    if(n<0x3000){ DecompileResults r=dc.decompileFunction(f,120,monitor); fh.println((r!=null&&r.decompileCompleted())?r.getDecompiledFunction().getC():"(decompile fail)"); }
    else fh.println("(too large to decompile)");
    if(depth<=0) return;
    List<Address> callees=new ArrayList<>();
    InstructionIterator it=currentProgram.getListing().getInstructions(f.getBody(),true);
    while(it.hasNext()){ Instruction ins=it.next(); if(!ins.getFlowType().isCall()) continue;
      for(Address t:ins.getFlows()) if(!callees.contains(t)) callees.add(t); }
    for(Address t:callees){ Function cf=getFunctionAt(t); long cn=cf!=null?cf.getBody().getNumAddresses():0;
      if(cn>0 && cn<0x2000) dec(t,"callee of "+f.getEntryPoint(),depth-1);
      else fh.println("  (callee "+t+" size="+cn+" not expanded)"); }
  }
  @Override public void run() throws Exception {
    String[] a=getScriptArgs(); fh=new PrintWriter(a[0]); mem=currentProgram.getMemory();
    dc=new DecompInterface(); dc.openProgram(currentProgram); int depth=Integer.parseInt(a[1]);
    Address lo=currentProgram.getMinAddress();
    for(int i=2;i<a.length;i++){ String name=a[i]; byte[] pat=(name+"\0").getBytes("US-ASCII");
      fh.println("\n\n########## "+name+" ##########"); int ns=0;
      for(Address s=mem.findBytes(lo,pat,null,true,monitor); s!=null && ns<8; s=mem.findBytes(s.add(1),pat,null,true,monitor)){
        byte prev=1; try{ prev=mem.getByte(s.subtract(1)); }catch(Exception e){}
        if(prev!=0) continue;                                     // must be a whole string, not a suffix of a longer one
        ns++; fh.println("string @"+s);
        byte[] ptr=le64(s.getOffset());
        for(Address p=mem.findBytes(lo,ptr,null,true,monitor); p!=null; p=mem.findBytes(p.add(1),ptr,null,true,monitor)){
          long q=mem.getLong(p.add(8)); Address qa=toAddr(q); boolean ex=isExec(qa);
          fh.println("  ptr @"+p+" -> next qword 0x"+Long.toHexString(q)+(ex?"  [EXEC => thunk rva 0x"+Long.toHexString(q-IB)+"]":""));
          if(ex) dec(qa,"exec thunk for "+name,depth);
        }
      }
    }
    fh.println("\n# done"); fh.close(); println("WROTE "+a[0]);
  }
}
