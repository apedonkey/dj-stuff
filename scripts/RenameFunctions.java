// RenameFunctions: rename functions in the analyzed libUnreal.so project. Written to undo labels that
// scripts/NativeDecomp.java put on engine helpers: for a native whose real implementation is a virtual call, it took the
// first direct callee (e.g. FName's constructor) as the implementation and named that helper after the native.
//   args: <commands.txt> <log.txt>     one "<ghidra addr hex> <new name> [expected old name]" per line, '#' = comment
// Run through scripts/ghidra_probe.sh with SAVE=1 so the names are kept. A line whose function's current name isn't the
// expected one is skipped and logged, so a stale list can't rename the wrong function.
import java.io.PrintWriter;
import java.nio.file.Files;
import java.nio.file.Paths;
import ghidra.app.script.GhidraScript;
import ghidra.program.model.listing.Function;
import ghidra.program.model.symbol.SourceType;

public class RenameFunctions extends GhidraScript {
    @Override
    public void run() throws Exception {
        String[] a = getScriptArgs();
        try (PrintWriter log = new PrintWriter(a[1])) {
            int done = 0, skipped = 0;
            for (String line : Files.readAllLines(Paths.get(a[0]))) {
                line = line.trim();
                if (line.isEmpty() || line.startsWith("#")) continue;
                String[] p = line.split("\\s+");
                Function f = currentProgram.getFunctionManager().getFunctionAt(toAddr(Long.parseUnsignedLong(p[0], 16)));
                if (f == null) { log.println("no function at " + p[0]); skipped++; continue; }
                String old = f.getName();
                if (p.length > 2 && !old.equals(p[2])) { log.println("skipped " + p[0] + ": name is " + old + ", expected " + p[2]); skipped++; continue; }
                f.setName(p[1], SourceType.USER_DEFINED);
                log.println("renamed " + p[0] + ": " + old + " -> " + p[1]);
                done++;
            }
            log.println("renamed " + done + ", skipped " + skipped);
        }
        println("RenameFunctions wrote " + a[1]);
    }
}
