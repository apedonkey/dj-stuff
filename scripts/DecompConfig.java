// Decompile the native config thunks + spawn-time URL reader; deref referenced globals to find which
// G*Ini (GameUserSettings/Game/Engine) backs them. Ghidra addr = runtime RVA + 0x100000.
import java.io.PrintWriter; import java.util.*;
import ghidra.app.script.GhidraScript; import ghidra.app.decompiler.*;
import ghidra.program.model.address.*; import ghidra.program.model.listing.*;
import ghidra.program.model.mem.Memory; import ghidra.program.model.symbol.*;
public class DecompConfig extends GhidraScript {
  static final String[] ADDRS = {"050a84b4","050a9ac8","050a6574","050a79dc","050f584c"};
  PrintWriter fh; Memory mem; FunctionManager fm; ReferenceManager rm; DecompInterface dc; long IB=0x100000;
  void emit(String s){ fh.println(s); }
  String rdstr(Address a){ try{ StringBuilder b=new StringBuilder();
      for(int i=0;i<80;i++){ int c=mem.getByte(a.add(i))&0xff; if(c==0)break; if(c<0x20||c>0x7e)return null; b.append((char)c);} return b.toString(); }catch(Exception e){return null;} }
  String rdwide(Address a){ try{ StringBuilder b=new StringBuilder();
      for(int i=0;i<80;i++){ int c=mem.getShort(a.add(2L*i))&0xffff; if(c==0)break; if(c<0x20||c>0x7e)return null; b.append((char)c);} return b.length()>0?b.toString():null; }catch(Exception e){return null;} }
  @Override public void run() throws Exception {
    String out=getScriptArgs().length>0?getScriptArgs()[0]:"decomp_config.txt";
    fh=new PrintWriter(out); mem=currentProgram.getMemory(); fm=currentProgram.getFunctionManager();
    rm=currentProgram.getReferenceManager(); dc=new DecompInterface(); dc.openProgram(currentProgram);
    for(String h:ADDRS){ Address a=toAddr(Long.parseLong(h,16)); Function f=fm.getFunctionContaining(a);
      emit("\n"+"=".repeat(90)+"\nADDR 0x"+h+" (rva 0x"+Long.toHexString(Long.parseLong(h,16)-IB)+") -> "+(f==null?"NO FUNC":f.getEntryPoint()));
      if(f==null) continue;
      DecompileResults r=dc.decompileFunction(f,150,monitor);
      String c=(r!=null&&r.decompileCompleted())?r.getDecompiledFunction().getC():"(fail)"; emit(c);
      // deref every data reference from this function -> print any string it points to (catches the ini basename)
      emit("  --- referenced globals that resolve to strings ---");
      Set<Address> seen=new HashSet<>();
      for(Address ins=f.getEntryPoint(); ins!=null && f.getBody().contains(ins); ins=ins.next()){
        for(Reference ref: rm.getReferencesFrom(ins)){ Address t=ref.getToAddress();
          if(t==null||!t.isMemoryAddress()||!seen.add(t)) continue;
          String s=rdstr(t); if(s==null) s=rdwide(t);
          if(s==null){ try{ long p=mem.getLong(t); Address pp=toAddr(p); String s2=rdstr(pp); if(s2==null)s2=rdwide(pp);
                if(s2!=null) emit("    *0x"+Long.toHexString(t.getOffset())+" -> \""+s2+"\""); }catch(Exception e){} }
          else if(s.length()>=2) emit("    0x"+Long.toHexString(t.getOffset())+" = \""+s+"\""); } }
    }
    emit("\n# done"); fh.close(); println("WROTE "+out);
  }
}
