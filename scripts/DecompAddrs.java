// Decompile a fixed list of Ghidra addresses (for locator contract resolution).
import java.io.PrintWriter;
import ghidra.app.script.GhidraScript;
import ghidra.app.decompiler.*;
import ghidra.program.model.address.Address;
import ghidra.program.model.listing.*;

public class DecompAddrs extends GhidraScript {
    static final String[] ADDRS = {"01736088"};
    @Override public void run() throws Exception {
        String out=getScriptArgs().length>0?getScriptArgs()[0]:"decomp_addrs.txt";
        PrintWriter fh=new PrintWriter(out);
        FunctionManager fm=currentProgram.getFunctionManager();
        DecompInterface dc=new DecompInterface(); dc.openProgram(currentProgram);
        for(String h:ADDRS){
            Function f=fm.getFunctionContaining(toAddr(Long.parseLong(h,16)));
            fh.println("\n"+"=".repeat(90));
            if(f==null){ fh.println("ADDR "+h+" NO FUNC"); continue; }
            fh.println("FUNC "+f.getEntryPoint()+" size="+f.getBody().getNumAddresses());
            fh.println("-".repeat(90));
            long n=f.getBody().getNumAddresses();
            if(n>0x1800){ fh.println("(too large "+n+")"); continue; }
            DecompileResults r=dc.decompileFunction(f,120,monitor);
            fh.println((r!=null&&r.decompileCompleted())?r.getDecompiledFunction().getC():"(fail)");
        }
        fh.println("\n# done"); fh.close(); println("WROTE "+out);
    }
}
