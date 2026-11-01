// Dump UE native-function tables (FNameNativePtrPair {const char* Name; void* Ptr}) around a Ghidra address.
// Args: <out file> <ghidra addr hex> [entries before/after, default 24]
import java.io.PrintWriter;
import ghidra.app.script.GhidraScript;
import ghidra.program.model.address.Address;
import ghidra.program.model.mem.Memory;
public class TableDump extends GhidraScript {
  String cstr(Memory m, long p){ try{ Address a=toAddr(p); StringBuilder sb=new StringBuilder(); for(int i=0;i<100;i++){ byte b=m.getByte(a.add(i)); if(b==0) break; if(b<32||b>126) return null; sb.append((char)b);} return sb.toString(); }catch(Exception e){ return null; } }
  @Override public void run() throws Exception {
    String[] a=getScriptArgs(); PrintWriter fh=new PrintWriter(a[0]); Memory m=currentProgram.getMemory();
    Address ptr=toAddr(Long.parseLong(a[1].replace("0x",""),16)); int n=a.length>2?Integer.parseInt(a[2]):24;
    Address entry=ptr.subtract(8);                                      // the slot holding the name pointer
    for(int k=-n;k<=n;k++){
      Address e=entry.add(16L*k); String nm=null; long fn=0;
      try{ nm=cstr(m,m.getLong(e)); fn=m.getLong(e.add(8)); }catch(Exception x){}
      fh.println(String.format("%4d %s  %-40s fn=0x%x (rva 0x%x)",k,e,nm,fn,fn-0x100000L));
    }
    fh.println("# done"); fh.close(); println("WROTE "+a[0]);
  }
}
