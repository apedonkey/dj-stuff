// Name the UFunctions behind native exec thunks: for each Ghidra RVA (Ghidra addr = RVA + 0x100000), find data
// references to the thunk (UE's FNameNativePtrPair {const char* Name; FNativeFuncPtr Ptr} tables) and print the name
// string the pointer before it points at. Also prints any code callers. Args: <out file> <rva hex>...
import java.io.PrintWriter;
import ghidra.app.script.GhidraScript;
import ghidra.program.model.address.Address;
import ghidra.program.model.mem.Memory;
import ghidra.program.model.symbol.Reference;
public class ThunkNames extends GhidraScript {
  long IB=0x100000L;
  String cstr(Memory m, Address a){ try{ StringBuilder sb=new StringBuilder(); for(int i=0;i<120;i++){ byte b=m.getByte(a.add(i)); if(b==0) break; if(b<32||b>126) return null; sb.append((char)b);} return sb.toString(); }catch(Exception e){ return null; } }
  @Override public void run() throws Exception {
    String[] a=getScriptArgs(); PrintWriter fh=new PrintWriter(a[0]); Memory m=currentProgram.getMemory();
    for(int i=1;i<a.length;i++){
      long rva=Long.parseLong(a[i].replace("0x",""),16); Address t=toAddr(rva+IB);
      fh.println("THUNK rva=0x"+Long.toHexString(rva)+" ghidra="+t);
      for(Reference r: getReferencesTo(t)){
        Address f=r.getFromAddress(); String kind=r.getReferenceType().toString();
        String nm=null; try{ long p=m.getLong(f.subtract(8)); nm=cstr(m,toAddr(p)); }catch(Exception e){}
        fh.println("  ref from "+f+" ("+kind+") name-before="+nm);
      }
      // a raw scan of the data for the pointer value, in case Ghidra recorded no reference
      byte[] pat=new byte[8]; long v=t.getOffset(); for(int k=0;k<8;k++) pat[k]=(byte)(v>>>(8*k));
      Address hit=m.findBytes(currentProgram.getMinAddress(),pat,null,true,monitor); int n=0;
      while(hit!=null&&n<8){ String nm=null; try{ nm=cstr(m,toAddr(m.getLong(hit.subtract(8)))); }catch(Exception e){}
        fh.println("  raw ptr at "+hit+" name-before="+nm); n++; hit=m.findBytes(hit.add(8),pat,null,true,monitor); }
    }
    fh.println("# done"); fh.close(); println("WROTE "+a[0]);
  }
}
