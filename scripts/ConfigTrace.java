// Trace how [TribeAvatar]/ReadyPlayerMeAvatarUrl is read AND written, and identify the config file.
// Run with -process -noanalysis on the saved project.
import java.io.PrintWriter;
import java.util.*;
import ghidra.app.script.GhidraScript;
import ghidra.app.decompiler.*;
import ghidra.program.model.address.Address;
import ghidra.program.model.listing.*;
import ghidra.program.model.mem.*;
import ghidra.program.model.symbol.*;

public class ConfigTrace extends GhidraScript {
    // Config section/keys + config-backend API name strings + candidate console/setter names.
    static final String[] ANCHORS = {
        "TribeAvatar", "ReadyPlayerMeAvatarUrl", "ReadyPlayerMeETag",
        "GameUserSettings", "SaveConfig", "SetString", "GetString", "SaveGameToSlot",
        "SetAvatar", "SetReadyPlayerMe", "SetAvatarUrl", "avatar.", "rpm.",
    };
    // functions already known + the GetString helper; decompile these + everything referencing anchors
    static final String[] SEEDS = { "050f584c", "016a70bc" };
    static final String[] GLOBALS = { "07ba1c58", "07ba2d90" };
    static final long MAX = 0x6000;

    PrintWriter fh; Memory mem; FunctionManager fm; ReferenceManager rm; DecompInterface dc;
    Set<Address> done = new HashSet<>();

    void emit(String s){ fh.println(s); println(s); }
    static String rep(String s,int n){StringBuilder b=new StringBuilder();for(int i=0;i<n;i++)b.append(s);return b.toString();}

    List<Address> occ(String t) throws Exception {
        List<Address> hits=new ArrayList<>();
        for (byte[] pat : new byte[][]{ t.getBytes("US-ASCII"), t.getBytes("UTF-16LE") }) {
            Address s=mem.getMinAddress(); int n=0;
            while(true){ Address a=mem.findBytes(s,pat,null,true,monitor); if(a==null)break; hits.add(a); s=a.add(1); if(++n>40)break; }
        }
        return hits;
    }
    List<Address> refsTo(Address a){ List<Address> o=new ArrayList<>(); ReferenceIterator it=rm.getReferencesTo(a); while(it.hasNext())o.add(it.next().getFromAddress()); return o; }
    List<Address> pointersTo(Address t) throws Exception {
        byte[] pat=new byte[8]; long v=t.getOffset(); for(int i=0;i<8;i++)pat[i]=(byte)((v>>>(8*i))&0xff);
        List<Address> o=new ArrayList<>(); Address s=mem.getMinAddress(); int n=0;
        while(true){ Address a=mem.findBytes(s,pat,null,true,monitor); if(a==null)break; o.add(a); s=a.add(1); if(++n>60)break; }
        return o;
    }
    boolean isExec(Address a){ MemoryBlock b=mem.getBlock(a); return b!=null&&b.isExecute(); }
    Address readPtr(Address a){ try{ long v=mem.getLong(a); return v==0?null:toAddr(v);}catch(Exception e){return null;} }
    String wideAt(Address a,int max){ StringBuilder b=new StringBuilder(); try{for(int i=0;i<max;i++){int c=mem.getShort(a.add(2L*i))&0xffff; if(c==0)break; b.append((char)c);} }catch(Exception e){return "";} return b.toString(); }

    String dec(Function f){
        if(f==null) return "(no function)";
        if(f.getBody().getNumAddresses()>MAX) return "(too large "+f.getBody().getNumAddresses()+" at "+f.getEntryPoint()+")";
        DecompileResults r=dc.decompileFunction(f,120,monitor);
        return (r!=null&&r.decompileCompleted())?r.getDecompiledFunction().getC():"(decompile failed)";
    }
    void dumpFunc(Function f, String tag){
        if(f==null||!done.add(f.getEntryPoint())) return;
        emit("\n"+rep("=",96)); emit("FUNC "+f.getEntryPoint()+"  size="+f.getBody().getNumAddresses()+"  ["+tag+"]");
        emit(rep("-",96)); emit(dec(f));
    }

    @Override public void run() throws Exception {
        String out=getScriptArgs().length>0?getScriptArgs()[0]:"config_trace.txt";
        fh=new PrintWriter(out); mem=currentProgram.getMemory(); fm=currentProgram.getFunctionManager();
        rm=currentProgram.getReferenceManager(); dc=new DecompInterface(); dc.openProgram(currentProgram);

        emit("# config trace  image_base="+currentProgram.getImageBase());
        // 1. anchors -> referring functions
        Set<Address> targets=new LinkedHashSet<>();
        for(String an: ANCHORS){
            List<Address> os=occ(an);
            emit("\nANCHOR \""+an+"\": "+os.size()+" occurrence(s)");
            for(Address s: os){
                for(Address r: refsTo(s)){ Function f=fm.getFunctionContaining(r); if(f!=null){ targets.add(f.getEntryPoint()); emit("  direct ref @"+s+" in FUNC "+f.getEntryPoint()); } }
                for(Address p: pointersTo(s)){
                    Address ex=readPtr(p.add(8));
                    if(ex!=null&&isExec(ex)){ Function f=fm.getFunctionContaining(ex); if(f==null){try{f=createFunction(ex,null);}catch(Exception e){}} if(f!=null){targets.add(f.getEntryPoint()); emit("  execThunk @P+8 -> FUNC "+f.getEntryPoint());} }
                    for(Address r: refsTo(p)){ Function f=fm.getFunctionContaining(r); if(f!=null){targets.add(f.getEntryPoint()); emit("  ptr-slot ref in FUNC "+f.getEntryPoint());} }
                }
            }
        }
        // 2. globals: writers + deref
        for(String h: GLOBALS){
            Address g=toAddr(Long.parseLong(h,16));
            emit("\nGLOBAL "+g+"  *="+readPtr(g)+(readPtr(g)!=null?("  wide@*=\""+wideAt(readPtr(g),80)+"\""):""));
            for(ReferenceIterator it=rm.getReferencesTo(g); it.hasNext();){ Reference r=it.next(); Function f=fm.getFunctionContaining(r.getFromAddress());
                if(f!=null){ emit("  "+(r.getReferenceType().isWrite()?"WRITE":"read")+" by FUNC "+f.getEntryPoint()); if(r.getReferenceType().isWrite()) targets.add(f.getEntryPoint()); } }
        }
        // 3. decompile seeds + all collected target functions
        for(String h: SEEDS){ Address a=toAddr(Long.parseLong(h,16)); dumpFunc(fm.getFunctionContaining(a),"seed "+h); }
        emit("\n"+rep("#",96)+"\n# referring functions ("+targets.size()+")\n"+rep("#",96));
        for(Address e: targets) dumpFunc(fm.getFunctionAt(e), "anchor-ref");
        emit("\n# done"); fh.close(); println("WROTE "+out);
    }
}
