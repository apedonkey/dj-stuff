// Decode the RPM avatar load path: callers of FUN_050f584c (spawn-time URL/ETag/cache read),
// the cache-dir builder FUN_0514ec88, and any glTF load site — to learn HTTP-vs-file and the cache dir.
import java.io.PrintWriter; import java.util.*;
import ghidra.app.script.GhidraScript; import ghidra.app.decompiler.*;
import ghidra.program.model.address.*; import ghidra.program.model.listing.*;
import ghidra.program.model.mem.Memory; import ghidra.program.model.symbol.*;
public class DecompLoad extends GhidraScript {
  PrintWriter fh; Memory mem; FunctionManager fm; ReferenceManager rm; DecompInterface dc; Listing lst; long IB=0x100000;
  Set<Address> done=new HashSet<>();
  void emit(String s){ fh.println(s); }
  String dec(Function f){ if(f==null) return "(null)"; long n=f.getBody().getNumAddresses(); if(n>0x4000) return "(too large "+n+")";
    DecompileResults r=dc.decompileFunction(f,150,monitor); return (r!=null&&r.decompileCompleted())?r.getDecompiledFunction().getC():"(fail)"; }
  void decAt(String tag,long ghAddr){ Address a=toAddr(ghAddr); Function f=fm.getFunctionContaining(a);
    if(f==null){ emit("\n"+tag+" @0x"+Long.toHexString(ghAddr)+" NO FUNC"); return; }
    if(!done.add(f.getEntryPoint())){ emit("\n"+tag+" -> "+f.getEntryPoint()+" (dup)"); return; }
    emit("\n"+"=".repeat(90)+"\n"+tag+" -> FUNC "+f.getEntryPoint()+" (rva 0x"+Long.toHexString(f.getEntryPoint().getOffset()-IB)+") size="+f.getBody().getNumAddresses());
    emit(dec(f)); }
  @Override public void run() throws Exception {
    String out=getScriptArgs().length>0?getScriptArgs()[0]:"decomp_load.txt";
    fh=new PrintWriter(out); mem=currentProgram.getMemory(); fm=currentProgram.getFunctionManager();
    rm=currentProgram.getReferenceManager(); lst=currentProgram.getListing(); dc=new DecompInterface(); dc.openProgram(currentProgram);
    // 1) cache-dir builder + cache filename helper
    decAt("FUN_0514ec88 (cacheDir builder)",0x0514ec88L);
    // 2) callers of FUN_050f584c (spawn-time URL/ETag reader) = the load orchestrator(s)
    Address tgt=toAddr(0x050f584cL); Function tf=fm.getFunctionContaining(tgt);
    emit("\n### callers of FUN_050f584c ("+ (tf!=null?tf.getEntryPoint():"?") +"):");
    Set<Address> callers=new LinkedHashSet<>();
    if(tf!=null){ for(ReferenceIterator it=rm.getReferencesTo(tf.getEntryPoint()); it.hasNext();){ Reference r=it.next();
        Function c=fm.getFunctionContaining(r.getFromAddress()); if(c!=null) callers.add(c.getEntryPoint()); } }
    for(Address c:callers){ decAt("caller",c.getOffset()); }
    // 3) glTFRuntime load sites: functions referencing the glTFRuntime load strings
    String[] anchors={"LoadGLTFRuntimeAssetFromUrl","LoadGLTFRuntimeAssetFromFilename","glTFLoadAssetFromFilename",
                      "glTFLoadAssetFromUrl","https://","http://","file://","rpmavatar-","%srpmavatar-%s"};
    emit("\n\n### functions referencing load/url strings:");
    DataIterator di=lst.getDefinedData(true);
    Map<Address,String> hits=new LinkedHashMap<>();
    while(di.hasNext()){ Data d=di.next(); Object v=null; try{v=d.getValue();}catch(Exception e){}
      if(!(v instanceof String)) continue; String s=(String)v;
      for(String a:anchors) if(s.contains(a)){ for(ReferenceIterator it=rm.getReferencesTo(d.getAddress()); it.hasNext();){
          Function c=fm.getFunctionContaining(it.next().getFromAddress()); if(c!=null) hits.putIfAbsent(c.getEntryPoint(),a+" :: "+s); } break; } }
    for(Map.Entry<Address,String> e:hits.entrySet()){ emit("   "+e.getKey()+"  ["+e.getValue()+"]"); }
    // decompile a few of the most relevant (those hitting Url/Filename/file://)
    for(Map.Entry<Address,String> e:hits.entrySet()){ String w=e.getValue();
      if(w.contains("FromUrl")||w.contains("FromFilename")||w.contains("file://")||w.contains("rpmavatar")) decAt("loadsite "+w.substring(0,Math.min(40,w.length())), e.getKey().getOffset()); }
    emit("\n# done"); fh.close(); println("WROTE "+out);
  }
}
