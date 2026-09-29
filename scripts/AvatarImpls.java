// Decompile a set of seed functions (exec thunks + direct-hit impls) and the functions they call
// (one hop), so the native implementations behind the UE exec thunks are captured.
// Run with -process -noanalysis.
import java.io.PrintWriter;
import java.util.*;
import ghidra.app.script.GhidraScript;
import ghidra.app.decompiler.*;
import ghidra.program.model.address.Address;
import ghidra.program.model.listing.*;

public class AvatarImpls extends GhidraScript {
    // seeds: exec thunks and direct impls found by AvatarXrefs2
    static final String[] SEEDS = {
        "05097618", // execGetAvatarTypeForId
        "050972d4", // execGetAvatarIdForServer
        "05097854", // execGetTribeDefaultAvatarId
        "0509793c", // execGetTribeMentorAvatarId
        "03fc4c54", // execIsMetaAvatarsSupported
        "050ce590", // execGetAvatarsPath
        "050a69dc", // execIsValidReadyPlayerMeAvatarUrl
        "050a68d4", // execIsValidReadyPlayerMeAvatarID
        "0509771c", // execGetAvatarUrlCacheFilename
        "05097b78", // execHandleReadyPlayerMeOnAvatarCached
        "050fc6e0", // ReadyPlayerMeAvatarUrl user
        "050f584c", // RPM etag/url
        "050f49cc", // RPM main load/download (large)
        "050fc808", // HandleReadyPlayerMeOnAvatarCached (wide) user
        "04ba868c", // zip://%s_quest2.glb (meta preset load)
        "050f5e58", // Replays/DefaultAvatar.glb
        "04c5d7b8", // https://readyplayer.me/api/avatar/ (static init)
    };
    static final long MAX = 0x8000;
    static final int TMO = 150;
    PrintWriter fh; FunctionManager fm; DecompInterface dc;
    Set<Address> done = new HashSet<>();

    void emit(String s){ fh.println(s); println(s); }
    String dec(Function f){
        long n=f.getBody().getNumAddresses();
        if(n>MAX) return "(too large: "+n+")";
        DecompileResults r=dc.decompileFunction(f,TMO,monitor);
        if(r==null||!r.decompileCompleted()) return "(decompile failed)";
        return r.getDecompiledFunction().getC();
    }
    void dump(Function f, String tag){
        if(f==null||!done.add(f.getEntryPoint())) return;
        emit("\n"+rep("=",96));
        emit("FUNC "+f.getEntryPoint()+"  size="+f.getBody().getNumAddresses()+"  ["+tag+"]");
        emit(rep("-",96));
        emit(dec(f));
    }
    @Override public void run() throws Exception {
        String out=getScriptArgs().length>0?getScriptArgs()[0]:"avatar_impls.txt";
        fh=new PrintWriter(out); fm=currentProgram.getFunctionManager();
        dc=new DecompInterface(); dc.openProgram(currentProgram);
        for(String h:SEEDS){
            Address a=toAddr(Long.parseLong(h,16));
            Function f=fm.getFunctionContaining(a);
            if(f==null){ emit("SEED "+h+" -> no function"); continue; }
            dump(f,"seed "+h);
            Set<Function> callees;
            try { callees=f.getCalledFunctions(monitor); } catch(Exception e){ callees=new HashSet<>(); }
            for(Function c:callees) dump(c,"callee of "+h);
        }
        emit("\n# done"); fh.close(); println("WROTE "+out);
    }
    static String rep(String s,int n){StringBuilder b=new StringBuilder();for(int i=0;i<n;i++)b.append(s);return b.toString();}
}
