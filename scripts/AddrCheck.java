// Resolve Ghidra addr <-> file vaddr mapping: print image base, block source (file) offsets,
// and the first bytes of each target so they can be matched in the on-disk .so.
import ghidra.app.script.GhidraScript;
import ghidra.program.model.address.Address;
import ghidra.program.model.mem.*;
import java.util.List;

public class AddrCheck extends GhidraScript {
    static final String[] T = {"050fc054","050fc2d4","050f4548","050f49cc","04ba81a8","050fc0d4","050fcee8"};
    @Override public void run() throws Exception {
        println("IMAGE_BASE=" + currentProgram.getImageBase());
        for (MemoryBlock b : currentProgram.getMemory().getBlocks()) {
            if (!b.isExecute() && b.getSize() < 0x1000) continue;
            println("BLOCK " + b.getName() + " start=" + b.getStart() + " size=0x" + Long.toHexString(b.getSize()) + (b.isExecute()?" [X]":""));
            for (MemoryBlockSourceInfo si : b.getSourceInfos()) {
                try { println("    fileOffset=0x" + Long.toHexString(si.getFileBytesOffset()) + " len=0x" + Long.toHexString(si.getLength())); }
                catch (Exception e) { println("    (no file offset: " + e + ")"); }
            }
        }
        for (String h : T) {
            Address a = toAddr(Long.parseLong(h,16));
            byte[] buf = new byte[20];
            try { currentProgram.getMemory().getBytes(a, buf); StringBuilder sb=new StringBuilder();
                for (byte x: buf) sb.append(String.format("%02x", x));
                println("BYTES@"+h+"="+sb);
            } catch (Exception e){ println("BYTES@"+h+"=ERR "+e); }
        }
    }
}
