// Read the RPM URL validator statically: find strings containing "readyplayer.me" /
// "IsValidReadyPlayerMe" / url-regex-ish, list + decompile referencing functions, and print each
// function's string refs so we can see EXACTLY what the validator checks (substring vs strict host/https).
import java.io.PrintWriter; import java.util.*;
import ghidra.app.script.GhidraScript; import ghidra.app.decompiler.*;
import ghidra.program.model.address.*; import ghidra.program.model.listing.*;
import ghidra.program.model.mem.Memory; import ghidra.program.model.symbol.*;
public class FindValidator extends GhidraScript {
  static final String[] NEEDLES={"readyplayer.me","IsValidReadyPlayerMe","ReadyPlayerMeAvatarUrl",
      ".glb",".readyplayer","models.readyplayer","/avatars/","https","http","://","[a-z]","\\.","regex","rpm"};
  PrintWriter fh; Memory mem; FunctionManager fm; ReferenceManager rm; DecompInterface dc; Listing lst; long IB=0x100000;
  Set<Address> done=new HashSet<>();
  void emit(String s){ fh.println(s); }
  String rdstr(Address a){ try{ StringBuilder b=new StringBuilder(); for(int i=0;i<160;i++){ int c=mem.getByte(a.add(i))&0xff; if(c==0)break; if(c<9||c>0x7e)return null; b.append((char)c);} return b.toString(); }catch(Exception e){return null;} }
  String rdwide(Address a){ try{ StringBuilder b=new StringBuilder(); for(int i=0;i<160;i++){ int c=mem.getShort(a.add(2L*i))&0xffff; if(c==0)break; if(c<9||c>0x7e)return null; b.append((char)c);} return b.length()>1?b.toString():null; }catch(Exception e){return null;} }
  void decFunc(Function f,String why){ if(f==null||!done.add(f.getEntryPoint())) return;
    long n=f.getBody().getNumAddresses();
    emit("\n"+"=".repeat(92)+"\nFUNC "+f.getEntryPoint()+" (rva 0x"+Long.toHexString(f.getEntryPoint().getOffset()-IB)+") size="+n+"  ["+why+"]");
    if(n>0x2800){ emit("(too large; string refs only)"); }
    else { DecompileResults r=dc.decompileFunction(f,150,monitor); emit((r!=null&&r.decompileCompleted())?r.getDecompiledFunction().getC():"(fail)"); }
    // string refs
    Set<Address> seen=new HashSet<>(); StringBuilder sb=new StringBuilder();
    for(Address ins=f.getEntryPoint(); ins!=null && f.getBody().contains(ins); ins=ins.next())
      for(Reference r:rm.getReferencesFrom(ins)){ Address t=r.getToAddress(); if(t==null||!t.isMemoryAddress()||!seen.add(t))continue;
        String s=rdstr(t); if(s==null)s=rdwide(t);
        if(s==null){ try{ long p=mem.getLong(t); String s2=rdstr(toAddr(p)); if(s2==null)s2=rdwide(toAddr(p)); if(s2!=null)s=s2; }catch(Exception e){} }
        if(s!=null && s.length()>=3 && s.length()<160) sb.append("     \""+s+"\"\n"); }
    if(sb.length()>0){ emit("  -- string refs --"); emit(sb.toString()); }
  }
  @Override public void run() throws Exception {
    String out=getScriptArgs().length>0?getScriptArgs()[0]:"validator.txt";
    fh=new PrintWriter(out); mem=currentProgram.getMemory(); fm=currentProgram.getFunctionManager();
    rm=currentProgram.getReferenceManager(); lst=currentProgram.getListing(); dc=new DecompInterface(); dc.openProgram(currentProgram);
    // collect string addresses of interest
    Map<Address,String> strs=new LinkedHashMap<>();
    DataIterator di=lst.getDefinedData(true);
    while(di.hasNext()){ Data d=di.next(); Object v=null; try{v=d.getValue();}catch(Exception e){} if(!(v instanceof String))continue; String s=(String)v;
      if(s.contains("readyplayer")||s.contains("ReadyPlayerMe")||(s.contains("://")&&s.length()<80)||s.contains("\\.")||(s.contains(".glb"))) strs.put(d.getAddress(),s); }
    emit("### strings of interest ("+strs.size()+"):");
    for(Map.Entry<Address,String> e:strs.entrySet()) emit("  "+e.getKey()+"  \""+e.getValue()+"\"");
    // decompile functions referencing "readyplayer.me" / "IsValidReadyPlayerMe" / regex-ish strings
    emit("\n\n### functions referencing validator-relevant strings:");
    for(Map.Entry<Address,String> e:strs.entrySet()){ String s=e.getValue();
      boolean key = s.contains("readyplayer.me")||s.contains("IsValidReadyPlayerMe")||s.contains("\\.")||s.contains("://")||s.equals("readyplayer");
      if(!key) continue;
      for(ReferenceIterator it=rm.getReferencesTo(e.getKey()); it.hasNext();){ Function f=fm.getFunctionContaining(it.next().getFromAddress()); if(f!=null) decFunc(f,"refs \""+ (s.length()>40?s.substring(0,40):s) +"\""); } }
    emit("\n# done"); fh.close(); println("WROTE "+out);
  }
}
