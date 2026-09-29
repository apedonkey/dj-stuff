// Ghidra headless PRE-script: turn off the decompiler-driven analyzers that dominate runtime on a
// large stripped image. Function boundaries and string/ADRP references are still produced by the
// remaining analyzers; the post-script decompiles only the ~20 anchored functions on demand.
import ghidra.app.script.GhidraScript;

public class DisableHeavyAnalyzers extends GhidraScript {
    static final String[] OFF = {
        "Decompiler Parameter ID",
        "Decompiler Switch Analysis",
    };
    @Override
    public void run() throws Exception {
        for (String name : OFF) {
            try { setAnalysisOption(currentProgram, name, "false"); println("DISABLED analyzer: " + name); }
            catch (Exception e) { println("could not disable " + name + ": " + e); }
        }
    }
}
