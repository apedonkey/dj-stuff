// Decompile the Android command-line loader (anchored on "UECommandLine.txt") + callers, to see
// whether an EXTERNAL command-line override file is read on this (shipping) build.
import java.io.PrintWriter;
import java.util.*;
import ghidra.app.script.GhidraScript;
import ghidra.app.decompiler.*;
import ghidra.program.model.address.Address;
import ghidra.program.model.listing.*;
import ghidra.program.model.mem.*;
import ghidra.program.model.symbol.*;

public class CmdlineTrace extends GhidraScript {
    static final String[] ANCHORS = { "UECommandLine.txt", "/UnrealGame/", "-ExecCmds", "AllowCommandLine" };
    PrintWriter fh; Memory mem; FunctionManager fm; ReferenceManager rm; DecompInterface dc;
    Set<Address> done = new HashSet<>();
    void emit(String s){ fh.println(s); println(s); }
    static String rep(String s,int n){StringBuilder b=new StringBuilder();for(int i=0;i<n;i++)b.append(s);return b.toString();}
    List<Address> occ(String t) throws Exception { List<Address> h=new ArrayList<>();
        for(byte[] p: new byte[][]{t.getBytes("US-ASCII"),t.getBytes("UTF-16LE")}){ Address s=mem.getMinAddress(); int n=0;
            while(true){Address a=mem.findBytes(s,p,null,true,monitor); if(a==null)break; h.add(a); s=a.add(1); if(++n>40)break;}} return h; }
    List<Address> refsTo(Address a){ List<Address> o=new ArrayList<>(); ReferenceIterator it=rm.getReferencesTo(a); while(it.hasNext())o.add(it.next().getFromAddress()); return o; }
    String dec(Function f){ if(f==null)return "(none)"; if(f.getBody().getNumAddresses()>0x8000)return "(too large "+f.getBody().getNumAddresses()+")";
        DecompileResults r=dc.decompileFunction(f,150,monitor); return (r!=null&&r.decompileCompleted())?r.getDecompiledFunction().getC():"(fail)"; }
    void dump(Function f,String tag){ if(f==null||!done.add(f.getEntryPoint()))return; emit("\n"+rep("=",96));
        emit("FUNC "+f.getEntryPoint()+" size="+f.getBody().getNumAddresses()+" ["+tag+"]"); emit(rep("-",96)); emit(dec(f)); }
    @Override public void run() throws Exception {
        String out=getScriptArgs().length>0?getScriptArgs()[0]:"cmdline.txt";
        fh=new PrintWriter(out); mem=currentProgram.getMemory(); fm=currentProgram.getFunctionManager();
        rm=currentProgram.getReferenceManager(); dc=new DecompInterface(); dc.openProgram(currentProgram);
        Set<Address> funcs=new LinkedHashSet<>();
        for(String an: ANCHORS){ List<Address> os=occ(an); emit("ANCHOR \""+an+"\": "+os.size());
            for(Address s: os) for(Address r: refsTo(s)){ Function f=fm.getFunctionContaining(r); if(f!=null){ funcs.add(f.getEntryPoint()); emit("  ref @"+s+" in FUNC "+f.getEntryPoint()); } } }
        for(Address e: funcs){ Function f=fm.getFunctionAt(e); dump(f,"cmdline");
            // one level of callers
            for(Address r: refsTo(e)){ Function c=fm.getFunctionContaining(r); if(c!=null) dump(c,"caller of "+e); } }
        emit("\n# done"); fh.close(); println("WROTE "+out);
    }
}
