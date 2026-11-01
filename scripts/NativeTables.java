// NativeTables: Tribe's C++ entry points read straight out of libUnreal.so, no headset needed. Every UHT class's
// GetPrivateStaticClass() calls GetPrivateStaticClassBody(PackageName, Name, ReturnClass, RegisterNativeFunc, Size,
// Alignment, ClassFlags, CastFlags, then on the stack ConfigName, InternalConstructor<T>, VTableHelperCtorCaller,
// CppClassStaticFunctions, Super::StaticClass, WithinClass::StaticClass) with UTF-16 literals (Name skips the U/A
// prefix). RegisterNativeFunc (StaticRegisterNatives<Class>) hands its FNameNativePtrPair table {const char* Name;
// FNativeFuncPtr Ptr} to FNativeFunctionRegistrar::RegisterFunctions(Class, Table, Count), and InternalConstructor<T>
// (or the T::T it calls) stores T's vtable into the new object. For the packages asked for, writes one JSON line per
// class in the hook's native-dump format (hook/native.cpp) for scripts/native_prep.py: parent, size, vtable and each
// native function's exec thunk, plus each first parent outside the packages as a vtable-only "context" line. No
// parameters, and no flags beyond FUNC_Native: only the runtime dump has those. Also <out>.packages.txt: every package
// in the binary with its class count. Address: runtime rva = Ghidra - 0xFF000 (NOTES' calibration).
// Args: <out.jsonl> [package ...]
import java.io.*; import java.util.*;
import ghidra.app.script.GhidraScript; import ghidra.app.decompiler.*;
import ghidra.app.plugin.core.analysis.ConstantPropagationContextEvaluator;
import ghidra.program.model.address.*; import ghidra.program.model.lang.Register;
import ghidra.program.model.listing.*; import ghidra.program.model.mem.*;
import ghidra.program.model.pcode.*; import ghidra.program.model.symbol.*;
import ghidra.program.util.*; import ghidra.util.task.TaskMonitor;
public class NativeTables extends GhidraScript {
  static final long SKEW=0xFF000L, UNK=Long.MIN_VALUE;
  static final int CTOR=5+1, SUPERFN=5+4;          // indexes into a call's values: x0..x4, then the stack arguments
  Memory mem; Register[] X=new Register[5]; Register SP; DecompInterface dc;
  // at every direct call in a function (to one of want, or to anything when want is null): x0..x4, then nstack
  // 8-byte stack arguments
  static class Grab extends ConstantPropagationContextEvaluator {
    Set<Address> want; Register[] regs; Register sp; int nstack; List<Object[]> hits=new ArrayList<>();   // {call site, target, long[]}
    Grab(TaskMonitor m,Set<Address> w,Register[] r,Register s,int ns){ super(m,true); want=w; regs=r; sp=s; nstack=ns; }
    @Override public boolean evaluateContextBefore(VarnodeContext c,Instruction in){
      if(in.getFlowType().isCall()){ Address[] fl=in.getFlows();
        if(fl.length==1&&(want==null||want.contains(fl[0]))){ long[] v=new long[regs.length+nstack];
          for(int i=0;i<regs.length;i++){ Varnode vn=c.getRegisterVarnodeValue(regs[i]); v[i]=(vn!=null&&c.isConstant(vn))?vn.getOffset():UNK; }
          Varnode s=nstack>0?c.getRegisterVarnodeValue(sp):null;
          for(int k=0;k<nstack;k++){ v[regs.length+k]=UNK;
            if(s!=null&&!c.isConstant(s)) try{ Varnode val=c.getValue(c.getVarnode(s.getSpace(),s.getOffset()+8L*k,8),this);
              if(val!=null&&c.isConstant(val)) v[regs.length+k]=val.getOffset(); }catch(Exception e){} }
          hits.add(new Object[]{in.getAddress(),fl[0],v}); } }
      return super.evaluateContextBefore(c,in); }
  }
  List<Object[]> calls(Function f,Set<Address> want,int nstack) throws Exception {
    Grab g=new Grab(monitor,want,X,SP,nstack); new SymbolicPropogator(currentProgram).flowConstants(f.getEntryPoint(),f.getBody(),g,false,monitor);
    return g.hits; }
  // FlatProgramAPI.getReferencesTo stops at 4096 (MAX_REFERENCES_TO); the class registrar has more callers than that
  List<Reference> refsTo(Address t){ List<Reference> l=new ArrayList<>(); for(Reference r:currentProgram.getReferenceManager().getReferencesTo(t)) l.add(r); return l; }
  MemoryBlock blk(long p){ try{ return mem.getBlock(toAddr(p)); }catch(Exception e){ return null; } }
  boolean isCode(long p){ MemoryBlock b=blk(p); return b!=null&&b.isExecute(); }
  boolean isData(long p){ MemoryBlock b=blk(p); return b!=null&&b.isInitialized()&&!b.isExecute(); }
  long q(long p){ try{ return mem.getLong(toAddr(p)); }catch(Exception e){ return UNK; } }
  String ascii(long p){ if(p==UNK||!isData(p)) return null; StringBuilder sb=new StringBuilder();
    try{ for(int i=0;i<256;i++){ int b=mem.getByte(toAddr(p+i))&0xff; if(b==0) return sb.length()>0?sb.toString():null;
      if(b<0x20||b>0x7e) return null; sb.append((char)b); } }catch(Exception e){} return null; }
  String utf16(long p){ if(p==UNK||!isData(p)) return null; StringBuilder sb=new StringBuilder();
    try{ for(int i=0;i<256;i++){ int c=mem.getShort(toAddr(p+2L*i))&0xffff; if(c==0) return sb.length()>0?sb.toString():null;
      if(c<0x20||c>0x7e) return null; sb.append((char)c); } }catch(Exception e){} return null; }
  byte[] utf16z(String s){ byte[] b=new byte[2*s.length()+2]; for(int i=0;i<s.length();i++){ b[2*i]=(byte)s.charAt(i); } return b; }
  String js(String s){ return "\""+s.replace("\\","\\\\").replace("\"","\\\"")+"\""; }
  String hx(long v){ return "\"0x"+Long.toHexString(v)+"\""; }
  Function fnAt(long p) throws Exception { Address a=toAddr(p); Function f=getFunctionAt(a);
    if(f==null&&getInstructionAt(a)==null) disassemble(a); if(f==null) f=createFunction(a,null); return f; }
  // ---- vtables ----
  long cval(Varnode v,int d){ if(v==null||d>6) return UNK; if(v.isConstant()) return v.getOffset(); PcodeOp o=v.getDef(); if(o==null) return UNK;
    switch(o.getOpcode()){
      case PcodeOp.COPY: case PcodeOp.CAST: return cval(o.getInput(0),d+1);
      case PcodeOp.PTRSUB: case PcodeOp.INT_ADD: { long x=cval(o.getInput(0),d+1), y=cval(o.getInput(1),d+1); return x==UNK||y==UNK?UNK:x+y; }
      case PcodeOp.LOAD: { long ad=cval(o.getInput(1),d+1); return ad==UNK||!isData(ad)?UNK:q(ad); }   // through the GOT
      default: return UNK; } }
  Varnode strip(Varnode v){ for(int i=0;i<8&&v!=null;i++){ PcodeOp o=v.getDef(); if(o==null) break; int oc=o.getOpcode();
      if(oc==PcodeOp.CAST||oc==PcodeOp.COPY) v=o.getInput(0); else if((oc==PcodeOp.PTRSUB||oc==PcodeOp.INT_ADD)&&cval(o.getInput(1),0)==0) v=o.getInput(0); else break; }
    return v; }
  boolean isParam0(Varnode v){ v=strip(v); return v!=null&&v.isInput()&&v.isRegister()&&v.getAddress().equals(X[0].getAddress()); }
  // the object a constructor builds: its first parameter (T::T(this, ...)), or what that points at (InternalConstructor<T>
  // gets the FObjectInitializer, whose first member is the object)
  boolean isObj(Varnode v){ if(isParam0(v)) return true; v=strip(v); PcodeOp o=v==null?null:v.getDef(); return o!=null&&o.getOpcode()==PcodeOp.LOAD&&isParam0(o.getInput(1)); }
  boolean vtLike(long p){ return p!=UNK&&isData(p)&&isCode(q(p))&&isCode(q(p+8)); }
  Map<String,String> why=new HashMap<>(); String cur;
  // T's vtable: the last vtable-looking constant the function stores at offset 0 of the object it constructs; failing that,
  // through a call that gets the object first (InternalConstructor<T> -> T::T), or a short forwarder's call after that
  long vtableOf(Function f,int depth,Set<Function> seen){
    if(f==null||depth>2||!seen.add(f)) return 0;
    DecompileResults r=dc.decompileFunction(f,60,monitor); if(r==null||!r.decompileCompleted()) return 0;
    long last=0; List<Address> callees=new ArrayList<>();
    for(Iterator<PcodeOpAST> it=r.getHighFunction().getPcodeOps(); it.hasNext();){ PcodeOpAST o=it.next();
      if(o.getOpcode()==PcodeOp.STORE){ long v=cval(o.getInput(2),0); if(vtLike(v)&&isObj(o.getInput(1))) last=v; }
      else if(o.getOpcode()==PcodeOp.CALL&&o.getInput(0).isAddress()&&o.getNumInputs()>1&&isObj(o.getInput(1))) callees.add(o.getInput(0).getAddress()); }
    if(last!=0){ why.put(cur,f.getName()+" @ "+f.getEntryPoint()+" depth "+depth); return last; }
    if(depth>=1&&f.getBody().getNumAddresses()>64) return 0;   // a constructor whose store we can't read: unknown, not its parent's
    for(Address c:callees){ long v=vtableOf(getFunctionAt(c),depth+1,seen); if(v!=0) return v; }
    return 0; }
  // A vtable's entries run to the first non-code qword, or to the first slot that something points at: the linker puts
  // other tables right after a vtable, e.g. a class's FClassRegisterCompiledInInfo {Z_Construct_UClass_X, X::StaticClass,
  // TEXT("UX"), &Z_Registration_Info, ...}, whose first two members are code pointers too.
  Set<Long> dataPtrs=new HashSet<>(); int stopPtr=0, stopRef=0;
  void scanDataPtrs() throws Exception { MemoryBlock rr=null; for(MemoryBlock b:mem.getBlocks()) if(b.getName().equals(".data.rel.ro")) rr=b;
    if(rr==null){ println("no .data.rel.ro block"); return; } long lo=rr.getStart().getOffset(), hi=rr.getEnd().getOffset(); byte[] buf=new byte[1<<20];
    for(MemoryBlock b:mem.getBlocks()){ String n=b.getName(); if(!b.isInitialized()||b.isExecute()||!(n.startsWith(".data")||n.startsWith(".got"))) continue;
      long s=b.getStart().getOffset(), e=b.getEnd().getOffset()+1;
      for(long p=s;p<e;p+=buf.length){ int len=(int)Math.min(buf.length,e-p); len-=len%8; b.getBytes(toAddr(p),buf,0,len);
        for(int i=0;i<len;i+=8){ long v=0; for(int j=7;j>=0;j--) v=(v<<8)|(buf[i+j]&0xff); if(v>=lo&&v<=hi) dataPtrs.add(v); } } }
    println(dataPtrs.size()+" pointers into .data.rel.ro"); }
  boolean codeAddrRef(long s){ for(Reference r:currentProgram.getReferenceManager().getReferencesTo(toAddr(s))){ RefType t=r.getReferenceType();
      if((t==RefType.DATA||t==RefType.PARAM)&&isCode(r.getFromAddress().getOffset())) return true; } return false; }
  List<Long> entries(long vt){ List<Long> e=new ArrayList<>();
    for(int i=0;vt!=0&&i<1024;i++){ long s=vt+8L*i, p=q(s); if(!isCode(p)) break;
      if(i>0&&dataPtrs.contains(s)){ stopPtr++; break; } if(i>0&&codeAddrRef(s)){ stopRef++; break; } e.add(p); }
    return e; }
  String vtJson(List<Long> e){ StringBuilder sb=new StringBuilder(); for(Long p:e) sb.append(sb.length()>0?",":"").append(hx(p-SKEW)); return sb.toString(); }
  // the class whose StaticClass a function pointer is: a function holding that class's registrar call, or a jump/call to one
  String classOfFn(long p,Map<Address,Set<String>> fc){ if(p==UNK) return null; Address a=toAddr(p); Set<String> k=fc.get(a);
    if(k==null){ Instruction in=getInstructionAt(a);
      if(in!=null&&in.getFlowType().isJump()&&!in.getFlowType().isConditional()&&in.getFlows().length==1) k=fc.get(in.getFlows()[0]); }
    if(k==null){ Function f=getFunctionAt(a); if(f!=null) for(Function c:f.getCalledFunctions(monitor)) if((k=fc.get(c.getEntryPoint()))!=null) break; }
    return k!=null&&k.size()==1?k.iterator().next():null; }
  @Override public void run() throws Exception {
    String[] a=getScriptArgs(); mem=currentProgram.getMemory(); long t0=System.currentTimeMillis();
    for(int i=0;i<5;i++) X[i]=currentProgram.getRegister("x"+i); SP=currentProgram.getRegister("sp");
    List<String> pk=new ArrayList<>(); for(int i=1;i<a.length;i++) pk.add(a[i]);
    if(pk.isEmpty()) pk=List.of("/Script/TribeXR","/Script/TribeIntonal","/Script/SuperPowered");
    // 1. GetPrivateStaticClassBody: the callee most often given a Tribe package literal in x0
    Map<Address,Integer> votes=new HashMap<>(); Set<Function> seen=new HashSet<>();
    for(String p:pk){ byte[] pat=utf16z(p);
      for(Address s=mem.findBytes(currentProgram.getMinAddress(),pat,null,true,monitor); s!=null; s=mem.findBytes(s.add(2),pat,null,true,monitor)){
        int nref=0;
        for(Reference r:refsTo(s)){ nref++; Function f=getFunctionContaining(r.getFromAddress());
          if(f==null||seen.size()>300||!seen.add(f)) continue;
          for(Object[] h:calls(f,null,0)) if(((long[])h[2])[0]==s.getOffset()) votes.merge((Address)h[1],1,Integer::sum); }
        println(p+" literal at "+s+": "+nref+" references"); } }
    List<Map.Entry<Address,Integer>> vs=new ArrayList<>(votes.entrySet()); vs.sort((x,y)->y.getValue()-x.getValue());
    for(int i=0;i<Math.min(3,vs.size());i++) println("  callee "+vs.get(i).getKey()+" gets a Tribe package in x0 from "+vs.get(i).getValue()+" functions");
    if(vs.isEmpty()){ println("FAIL: no call takes a package literal in x0"); return; }
    Address body=vs.get(0).getKey(); Set<Address> want=Set.of(body);
    // 2. every caller: package, class name, StaticRegisterNatives, size, constructor, parent's StaticClass
    Set<Function> callers=new LinkedHashSet<>();
    for(Reference r:refsTo(body)) if(r.getReferenceType().isCall()){ Function f=getFunctionContaining(r.getFromAddress()); if(f!=null) callers.add(f); }
    Map<String,Object[]> uniq=new LinkedHashMap<>(); Map<Address,Set<String>> fnClass=new HashMap<>(); int unk=0, dup=0;
    for(Function f:callers){ if(monitor.isCancelled()) return;
      for(Object[] h:calls(f,want,6)){ long[] v=(long[])h[2]; String p=utf16(v[0]), n=utf16(v[1]);
        if(p==null||n==null){ unk++; continue; }
        fnClass.computeIfAbsent(f.getEntryPoint(),x->new HashSet<>()).add(p+"."+n);
        // StaticRegisterNatives<Class> inlines its own StaticClass(): the same class again, from inside the register function
        boolean inReg=f.getEntryPoint().getOffset()==v[3]; Object[] old=uniq.get(p+"."+n);
        if(old!=null){ dup++; if(inReg||!(Boolean)old[6]) continue; }
        String pre=utf16(v[1]-2);
        uniq.put(p+"."+n,new Object[]{p,n,(pre!=null&&pre.length()>n.length())?pre.substring(0,1):"",v[3],v[4]&0xffffffffL,f.getEntryPoint(),inReg,v}); } }
    Map<String,Integer> perPkg=new TreeMap<>(); List<Object[]> mine=new ArrayList<>();
    for(Object[] m:uniq.values()){ perPkg.merge((String)m[0],1,Integer::sum); if(pk.contains(m[0])) mine.add(m); }
    println("GetPrivateStaticClassBody = "+body+": "+callers.size()+" callers, "+uniq.size()+" classes in "+perPkg.size()+" packages ("
      +dup+" repeat calls, "+unk+" unresolved); "+mine.size()+" in "+pk);
    try(PrintWriter pw=new PrintWriter(new File(a[0]+".packages.txt"),"UTF-8")){ for(Map.Entry<String,Integer> e:perPkg.entrySet()) pw.println(e.getValue()+"\t"+e.getKey()); }
    for(int i=0;i<Math.min(3,mine.size());i++){ long[] v=(long[])mine.get(i)[7]; StringBuilder sb=new StringBuilder();
      for(int k=5;k<v.length;k++) sb.append(" ").append(v[k]==UNK?"?":Long.toHexString(v[k])); println("  stack args of "+mine.get(i)[1]+":"+sb); }
    // 3. parents, vtables (the classes', and each first parent outside the packages)
    dc=new DecompInterface(); DecompileOptions o=new DecompileOptions(); o.grabFromProgram(currentProgram); dc.setOptions(o); dc.openProgram(currentProgram);
    Map<String,String> sup=new HashMap<>(); Map<String,List<Long>> vt=new HashMap<>(); Map<String,Long> vtAt=new HashMap<>();
    List<String> context=new ArrayList<>(); Set<String> mineKeys=new HashSet<>(); for(Object[] m:mine) mineKeys.add(m[0]+"."+m[1]);
    int nsup=0;
    for(Object[] m:mine){ String k=m[0]+"."+m[1]; String s=classOfFn(((long[])m[7])[SUPERFN],fnClass); if(s!=null){ sup.put(k,s); nsup++; }
      if(s!=null&&!mineKeys.contains(s)&&!context.contains(s)) context.add(s); }
    List<String> todo=new ArrayList<>(mineKeys); todo.addAll(context); int nvt=0; scanDataPtrs();
    for(String k:todo){ if(monitor.isCancelled()) return; long c=((long[])uniq.get(k)[7])[CTOR]; cur=k;
      long v=isCode(c)?vtableOf(fnAt(c),0,new HashSet<>()):0; if(v!=0){ vt.put(k,entries(v)); vtAt.put(k,v); nvt++; } else println("  no vtable: "+k+" ctor "+Long.toHexString(c)); }
    int same=0, low=0;
    for(String k:mineKeys){ List<Long> e=vt.get(k), pe=vt.get(sup.get(k)); if(e==null||pe==null) continue; int n=Math.min(e.size(),pe.size()), eq=0;
      for(int i=0;i<n;i++) if(e.get(i).equals(pe.get(i))) eq++;
      if(e.size()<pe.size()||eq*2<n){ low++; println("  check vtable: "+k+" "+e.size()+" entries at "+Long.toHexString(vtAt.get(k))+" ("+why.get(k)+"), parent "
          +sup.get(k)+" "+pe.size()+" at "+Long.toHexString(vtAt.get(sup.get(k)))+" ("+why.get(sup.get(k))+"), "+eq+" shared"); } else same++; }
    for(String k:context) println("  parent "+k+": vtable "+vt.getOrDefault(k,List.of()).size()+" entries ("+why.get(k)+")");
    println("parents found for "+nsup+" of "+mine.size()+" ("+context.size()+" outside the packages); vtables for "+nvt+" of "+todo.size()
      +" ("+stopPtr+" ended at a slot data points at, "+stopRef+" at one code points at); "+same+" vtables extend their parent's, "+low+" don't");
    // 4. each class's native table, through the call in StaticRegisterNatives that passes a table and its count
    int nf=0, nt=0, short_=0;
    try(PrintWriter pw=new PrintWriter(new File(a[0]),"UTF-8")){
      for(String k:todo){ Object[] m=uniq.get(k); boolean ctx=!mineKeys.contains(k); long reg=(Long)m[3]; List<String> fns=new ArrayList<>(); long tab=0, want_=0;
        Function rf=ctx||reg==UNK||!isCode(reg)?null:fnAt(reg);
        if(rf!=null) for(Object[] h:calls(rf,null,0)){ long[] v=(long[])h[2]; if(v[1]==UNK||v[2]==UNK) continue;
          long cnt=v[2]&0xffffffffL; if(cnt<1||cnt>4096||ascii(q(v[1]))==null||!isCode(q(v[1]+8))) continue;
          tab=v[1]; want_=cnt;
          for(long i=0;i<cnt;i++){ String nm=ascii(q(tab+16*i)); long fp=q(tab+16*i+8); if(nm==null||!isCode(fp)) break;
            fns.add("{\"name\":"+js(nm)+",\"flags\":\"0x400\",\"func\":"+hx(fp-SKEW)+",\"params\":null}"); }
          break; }
        if(fns.size()<want_){ short_++; println("  short table: "+k+" "+fns.size()+" of "+want_+" at "+Long.toHexString(tab)); }
        if(tab!=0) nt++; nf+=fns.size(); List<Long> e=vt.getOrDefault(k,List.of());
        pw.println("{\"class\":"+js(k)+",\"cpp\":"+js(m[2]+""+m[1])+",\"super\":"+js(sup.getOrDefault(k,""))+",\"size\":"+m[4]+(ctx?",\"context\":true":"")
          +",\"vtable\":["+vtJson(e)+"],\"vtable_ghidra\":"+hx(vtAt.getOrDefault(k,0L))+",\"static\":true,\"gpsc\":"+hx(((Address)m[5]).getOffset()-SKEW)
          +",\"register\":"+(reg==UNK?"\"0x0\"":hx(reg-SKEW))+",\"ctor\":"+hx(((long[])m[7])[CTOR]==UNK?0:((long[])m[7])[CTOR]-SKEW)+",\"table\":"+hx(tab)
          +",\"functions\":["+String.join(",",fns)+"]}"); } }
    println("DONE: "+mine.size()+" classes (+"+context.size()+" parents), "+nt+" with a native table, "+nf+" native functions ("+short_
      +" tables cut short) in "+((System.currentTimeMillis()-t0)/1000)+" s -> "+a[0]);
  }
}
