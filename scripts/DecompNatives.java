// Decompile the two native functions that gate/perform the RPM load:
//  - IsValidReadyPlayerMeAvatarID (gates SetAvatarID): what does it accept? (host? 24-hex id? non-empty?)
//  - SetAvatarID / the fetch: does it use the URL literally, or rebuild https://models.readyplayer.me/<id>.glb?
// Strategy: find defined strings of interest, decompile every function that references them, and print each
// such function's own string refs (so URL-template / host literals surface). Ghidra addr - 0x100000 = RVA.
import java.io.PrintWriter; import java.util.*;
import ghidra.app.script.GhidraScript; import ghidra.app.decompiler.*;
import ghidra.program.model.address.*; import ghidra.program.model.listing.*;
import ghidra.program.model.mem.Memory; import ghidra.program.model.symbol.*;
public class DecompNatives extends GhidraScript {
  static final String[] NEEDLES={"SetAvatarID","IsValidReadyPlayerMeAvatarID","IsValidReadyPlayerMeAvatarUrl",
    "readyplayer.me","models.readyplayer","meshLod","AvatarId","avatarId","/avatars/",".glb","%s.glb","%s%s.glb"};
  PrintWriter fh; Memory mem; FunctionManager fm; ReferenceManager rm; DecompInterface dc; Listing lst; long IB=0x100000;
  Set<Address> done=new HashSet<>();
  void emit(String s){ fh.println(s); }
  String rdstr(Address a){ try{ StringBuilder b=new StringBuilder(); for(int i=0;i<200;i++){ int c=mem.getByte(a.add(i))&0xff; if(c==0)break; if(c<9||c>0x7e)return null; b.append((char)c);} return b.toString(); }catch(Exception e){return null;} }
  String rdwide(Address a){ try{ StringBuilder b=new StringBuilder(); for(int i=0;i<200;i++){ int c=mem.getShort(a.add(2L*i))&0xffff; if(c==0)break; if(c<9||c>0x7e)return null; b.append((char)c);} return b.length()>1?b.toString():null; }catch(Exception e){return null;} }
  void decFunc(Function f,String why){ if(f==null||!done.add(f.getEntryPoint())) return;
    long n=f.getBody().getNumAddresses();
    emit("\n"+"=".repeat(96)+"\nFUNC "+f.getEntryPoint()+" (rva 0x"+Long.toHexString(f.getEntryPoint().getOffset()-IB)+") size="+n+"  ["+why+"]");
    if(n>0x3000){ emit("(too large; string refs only)"); }
    else { DecompileResults r=dc.decompileFunction(f,120,monitor); emit((r!=null&&r.decompileCompleted())?r.getDecompiledFunction().getC():"(decompile fail)"); }
    Set<Address> seen=new HashSet<>(); StringBuilder sb=new StringBuilder();
    for(Address ins=f.getEntryPoint(); ins!=null && f.getBody().contains(ins); ins=ins.next())
      for(Reference r:rm.getReferencesFrom(ins)){ Address t=r.getToAddress(); if(t==null||!t.isMemoryAddress()||!seen.add(t))continue;
        String s=rdstr(t); if(s==null)s=rdwide(t);
        if(s==null){ try{ long p=mem.getLong(t); String s2=rdstr(toAddr(p)); if(s2==null)s2=rdwide(toAddr(p)); if(s2!=null)s=s2; }catch(Exception e){} }
        if(s!=null && s.length()>=3 && s.length()<200) sb.append("     \""+s+"\"\n"); }
    if(sb.length()>0){ emit("  -- string refs --"); emit(sb.toString()); }
  }
  @Override public void run() throws Exception {
    String out=getScriptArgs().length>0?getScriptArgs()[0]:"natives.txt";
    fh=new PrintWriter(out); mem=currentProgram.getMemory(); fm=currentProgram.getFunctionManager();
    rm=currentProgram.getReferenceManager(); lst=currentProgram.getListing(); dc=new DecompInterface(); dc.openProgram(currentProgram);
    Map<Address,String> strs=new LinkedHashMap<>();
    DataIterator di=lst.getDefinedData(true);
    while(di.hasNext()){ Data d=di.next(); Object v=null; try{v=d.getValue();}catch(Exception e){} if(!(v instanceof String))continue; String s=(String)v;
      for(String needle:NEEDLES){ if(s.contains(needle)){ strs.put(d.getAddress(),s); break; } } }
    emit("### strings of interest ("+strs.size()+"):");
    for(Map.Entry<Address,String> e:strs.entrySet()) emit("  "+e.getKey()+" (rva 0x"+Long.toHexString(e.getKey().getOffset()-IB)+")  \""+e.getValue()+"\"");
    emit("\n\n### referencing functions decompiled:");
    for(Map.Entry<Address,String> e:strs.entrySet()){ String s=e.getValue();
      // focus: the validator + URL-template + host strings (skip the ubiquitous ".glb" alone unless short)
      boolean key = s.contains("SetAvatarID")||s.contains("IsValidReadyPlayerMe")||s.contains("readyplayer")
        ||s.contains("meshLod")||s.contains("%s.glb")||s.contains("/avatars/")||s.length()<12;
      if(!key) continue;
      int cnt=0;
      for(ReferenceIterator it=rm.getReferencesTo(e.getKey()); it.hasNext() && cnt<6;){ Function f=fm.getFunctionContaining(it.next().getFromAddress());
        if(f!=null){ decFunc(f,"refs \""+(s.length()>44?s.substring(0,44):s)+"\""); cnt++; } } }
    emit("\n# done"); fh.close(); println("WROTE "+out);
  }
}
