// Decompile the RPM avatar build path: the orchestrator's callees + the per-file loader, listing each
// function's CALL targets and string refs, to find the glTFRuntime build call, its config, HTTP request,
// and async callback. Also locate glTFRuntime's parser (functions referencing glTF-parse strings).
import java.io.PrintWriter; import java.util.*;
import ghidra.app.script.GhidraScript; import ghidra.app.decompiler.*;
import ghidra.program.model.address.*; import ghidra.program.model.listing.*;
import ghidra.program.model.mem.Memory; import ghidra.program.model.symbol.*;
public class DecompBuild extends GhidraScript {
  static final String[] ADDRS = {"04bdde7c","04be2d70","04bc0d9c","04c5ad6c","04c59ce0","04bc1b84","04bc1d2c","04bb9538"};
  static final String[] PARSE = {"KHR_draco_mesh_compression","bufferViews","accessors","LoadSkeletalMesh",
      "SkeletalMeshConfig","primitives","OnProcessRequestComplete","meshes","JOINTS_0","glTFRuntime"};
  PrintWriter fh; Memory mem; FunctionManager fm; ReferenceManager rm; DecompInterface dc; Listing lst; long IB=0x100000;
  Set<Address> done=new HashSet<>();
  void emit(String s){ fh.println(s); }
  String rdstr(Address a){ try{ StringBuilder b=new StringBuilder(); for(int i=0;i<90;i++){ int c=mem.getByte(a.add(i))&0xff; if(c==0)break; if(c<0x20||c>0x7e)return null; b.append((char)c);} return b.toString(); }catch(Exception e){return null;} }
  String rdwide(Address a){ try{ StringBuilder b=new StringBuilder(); for(int i=0;i<90;i++){ int c=mem.getShort(a.add(2L*i))&0xffff; if(c==0)break; if(c<0x20||c>0x7e)return null; b.append((char)c);} return b.length()>1?b.toString():null; }catch(Exception e){return null;} }
  void decOne(String tag,long gh){ Address a=toAddr(gh); Function f=fm.getFunctionContaining(a);
    emit("\n"+"=".repeat(92));
    if(f==null){ emit(tag+" @0x"+Long.toHexString(gh)+" NO FUNC"); return; }
    emit(tag+" -> "+f.getEntryPoint()+" (rva 0x"+Long.toHexString(f.getEntryPoint().getOffset()-IB)+") size="+f.getBody().getNumAddresses());
    long n=f.getBody().getNumAddresses();
    if(n<=0x3000){ DecompileResults r=dc.decompileFunction(f,150,monitor);
      emit((r!=null&&r.decompileCompleted())?r.getDecompiledFunction().getC():"(decompile fail)"); }
    else emit("(too large "+n+" to decompile; calls+strings below)");
    // CALL targets + string refs
    emit("  --- CALL targets ---"); Set<Address> calls=new LinkedHashSet<>(); Set<Address> seenS=new HashSet<>();
    StringBuilder strs=new StringBuilder();
    for(Address ins=f.getEntryPoint(); ins!=null && f.getBody().contains(ins); ins=ins.next()){
      for(Reference r: rm.getReferencesFrom(ins)){ Address t=r.getToAddress(); if(t==null||!t.isMemoryAddress()) continue;
        if(r.getReferenceType().isCall()){ Function c=fm.getFunctionContaining(t); if(c!=null) calls.add(c.getEntryPoint()); }
        else if(seenS.add(t)){ String s=rdstr(t); if(s==null)s=rdwide(t);
          if(s==null){ try{ long p=mem.getLong(t); String s2=rdstr(toAddr(p)); if(s2==null)s2=rdwide(toAddr(p)); if(s2!=null&&s2.length()>2) s=s2; }catch(Exception e){} }
          if(s!=null && s.length()>2) strs.append("      \""+s+"\"\n"); } } }
    for(Address c: calls){ Function cf=fm.getFunctionContaining(c); emit("    call "+c+" (rva 0x"+Long.toHexString(c.getOffset()-IB)+") size="+(cf!=null?cf.getBody().getNumAddresses():0)); }
    if(strs.length()>0){ emit("  --- string refs ---"); emit(strs.toString()); }
  }
  @Override public void run() throws Exception {
    String out=getScriptArgs().length>0?getScriptArgs()[0]:"decomp_build.txt";
    fh=new PrintWriter(out); mem=currentProgram.getMemory(); fm=currentProgram.getFunctionManager();
    rm=currentProgram.getReferenceManager(); lst=currentProgram.getListing(); dc=new DecompInterface(); dc.openProgram(currentProgram);
    for(String h:ADDRS) decOne("FUNC "+h, Long.parseLong(h,16));
    // locate glTFRuntime parser / HTTP by parse strings
    emit("\n\n"+"#".repeat(60)+"\n# functions referencing glTF-parse / HTTP strings:");
    DataIterator di=lst.getDefinedData(true); Map<Address,String> hits=new LinkedHashMap<>();
    while(di.hasNext()){ Data d=di.next(); Object v=null; try{v=d.getValue();}catch(Exception e){}
      if(!(v instanceof String)) continue; String s=(String)v;
      for(String a:PARSE){ if(s.equals(a)||s.contains(a)){ for(ReferenceIterator it=rm.getReferencesTo(d.getAddress()); it.hasNext();){
          Function c=fm.getFunctionContaining(it.next().getFromAddress()); if(c!=null) hits.putIfAbsent(c.getEntryPoint(), a); } break; } } }
    for(Map.Entry<Address,String> e:hits.entrySet()) emit("   "+e.getKey()+" (rva 0x"+Long.toHexString(e.getKey().getOffset()-IB)+")  ["+e.getValue()+"]");
    emit("\n# done"); fh.close(); println("WROTE "+out);
  }
}
