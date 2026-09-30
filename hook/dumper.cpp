// TribeXR Session-2 READ-ONLY SDK/decision dumper (injected via DT_NEEDED libhook.so).
// No hooks, no game-state mutation: a detached thread polls tribemod/dump_now, then walks
// NamePool + GUObjectArray and writes selfcheck/objects/values(/sdk) to tribemod/.
// Real runtime vaddr = base + RVA (libUnreal.so image base is 0). Ghidra addr = RVA + 0x100000.

#include <android/log.h>
#include <cstdint>
#include <cstdio>
#include <cstring>
#include <cstdlib>
#include <unistd.h>
#include <fcntl.h>
#include <pthread.h>
#include <setjmp.h>
#include <signal.h>
#include <sys/stat.h>
#include <sys/syscall.h>
#include <sys/socket.h>
#include <netinet/in.h>
#include <arpa/inet.h>
#include <errno.h>
#include <dirent.h>
#include <cstdarg>
static inline pid_t my_tid(){ return (pid_t)syscall(SYS_gettid); }

#define TAG "TRIBEMOD"
#define LOGI(...) __android_log_print(ANDROID_LOG_INFO, TAG, __VA_ARGS__)

// ---- resolved statics (this session) ----
static const uintptr_t RVA_NamePool      = 0x07C632C0; // FNamePool (.bss) [scan-confirmed]
static const uintptr_t RVA_GUObjectArray = 0x07CBADD0; // FUObjectArray (.bss) [Ghidra AllocateObjectPool]
static const uintptr_t RVA_GUObj_GOTslot = 0x07AA59E8; // data slot holding &GUObjectArray (Ghidra 0x07ba59e8-0x100000)

static const char* OUTDIR = "/sdcard/Android/data/com.TribeXR.TribeXR/files/tribemod";

// ---- module base ----
static uintptr_t g_base = 0;
static uintptr_t find_lib_base(const char* name) {
    FILE* f = fopen("/proc/self/maps", "r"); if (!f) return 0;
    char line[1024]; uintptr_t best = 0;
    while (fgets(line, sizeof line, f)) {
        if (strstr(line, name)) { uintptr_t s = (uintptr_t)strtoull(line, nullptr, 16);
            if (s && (best==0 || s<best)) best = s; } }
    fclose(f); return best;
}

// ---- readable-range cache from /proc/self/maps + SIGSEGV guard ----
struct Range { uintptr_t lo, hi; };
static Range g_ranges[4096]; static int g_nranges=0;
static void load_maps() {
    g_nranges=0; FILE* f=fopen("/proc/self/maps","r"); if(!f) return; char line[1024];
    while (fgets(line,sizeof line,f) && g_nranges<4096){
        uintptr_t lo,hi; char perm[8];
        if (sscanf(line,"%lx-%lx %4s",&lo,&hi,perm)==3 && perm[0]=='r'){ g_ranges[g_nranges++]=(Range){lo,hi}; } }
    fclose(f);
}
// /proc/self/maps is address-sorted & non-overlapping -> binary search (O(log n) per read).
static bool in_range(uintptr_t p, size_t n){ int lo=0,hi=g_nranges-1;
    while(lo<=hi){ int mid=(lo+hi)>>1;
        if(p<g_ranges[mid].lo) hi=mid-1; else if(p>=g_ranges[mid].hi) lo=mid+1;
        else return p+n<=g_ranges[mid].hi; }
    return false; }

// SIGSEGV/SIGBUS guard. THREAD-SAFE: only longjmp when the faulting thread is the dumper thread;
// a genuine fault on any other (game) thread chains to the original handler untouched.
static sigjmp_buf g_jmp; static volatile sig_atomic_t g_guard=0; static struct sigaction g_old_segv, g_old_bus;
static volatile pid_t g_dump_tid=0;
static void segv_handler(int sig,siginfo_t* si,void* uc){ if(g_guard && my_tid()==g_dump_tid) siglongjmp(g_jmp,1);
    if(sig==SIGSEGV && g_old_segv.sa_sigaction) g_old_segv.sa_sigaction(sig,si,uc);
    else if(sig==SIGBUS && g_old_bus.sa_sigaction) g_old_bus.sa_sigaction(sig,si,uc); }
static void install_guard(){ g_dump_tid=my_tid(); struct sigaction sa; memset(&sa,0,sizeof sa); sa.sa_sigaction=segv_handler; sa.sa_flags=SA_SIGINFO;
    sigaction(SIGSEGV,&sa,&g_old_segv); sigaction(SIGBUS,&sa,&g_old_bus); }
static void remove_guard(){ sigaction(SIGSEGV,&g_old_segv,nullptr); sigaction(SIGBUS,&g_old_bus,nullptr); }

// safe typed reads (maps range-check, then guarded deref)
static bool sr(uintptr_t p, void* out, size_t n){
    if(!p || !in_range(p,n)){ if(!p) return false; load_maps(); if(!in_range(p,n)) return false; }
    g_guard=1; if(sigsetjmp(g_jmp,1)){ g_guard=0; return false; } memcpy(out,(void*)p,n); g_guard=0; return true;
}
static uintptr_t rdptr(uintptr_t p){ uintptr_t v=0; return sr(p,&v,8)?v:0; }
static uint32_t  rd32 (uintptr_t p){ uint32_t v=0; return sr(p,&v,4)?v:0; }
static uint16_t  rd16 (uintptr_t p){ uint16_t v=0; return sr(p,&v,2)?v:0; }

// ---- FName pool (R1) ----
static uintptr_t g_namepool=0; static uint32_t g_blocks_off=0x40;
static uintptr_t np_block(uint32_t blk){ return rdptr(g_namepool + g_blocks_off + (uintptr_t)blk*8); }
// resolve FNameEntryId -> ASCII (best-effort); returns len, fills buf
static int fname_resolve(uint32_t id, char* buf, int buflen){
    uint32_t blk=id>>16, off=id&0xFFFF; uintptr_t blockp=np_block(blk); if(!blockp){ buf[0]=0; return 0; }
    uintptr_t entry=blockp + (uintptr_t)off*2; uint16_t hdr=rd16(entry); int wide=hdr&1; int len=hdr>>6;
    if(len<=0||len>1024){ buf[0]=0; return 0; }
    uintptr_t chars=entry+2; int j=0;
    for(int i=0;i<len && j<buflen-1;i++){ uint16_t c; if(wide){ c=rd16(chars+(uintptr_t)i*2); } else { uint8_t b; sr(chars+i,&b,1); c=b; }
        buf[j++]=(c && c<0x80)?(char)c:'?'; }
    buf[j]=0; return j;
}
// object name (FName at obj+0x18) -> string  (offsets locked in R3, defaults here)
static uint32_t OFF_Name=0x18, OFF_Class=0x10, OFF_Outer=0x20, OFF_Flags=0x08, OFF_Index=0x0C;
static void obj_name(uintptr_t obj, char* buf, int n){ if(!obj){snprintf(buf,n,"(null)");return;} uint32_t id=rd32(obj+OFF_Name); fname_resolve(id,buf,n); }
static void class_name(uintptr_t obj, char* buf, int n){ uintptr_t cls=rdptr(obj+OFF_Class); obj_name(cls,buf,n); }

// ---- GUObjectArray (R2) ----
static uintptr_t g_objarray=0; static uint32_t g_numElements=0, g_numChunks=0; static uintptr_t g_chunks=0;
static const uint32_t OBJOBJECTS=0x10, ITEM_STRIDE=0x14; // FUObjectItem = {Object*,Flags,Cluster,Serial}=20B; Objects[k] points at item[0]
static uintptr_t obj_at(uint32_t idx){
    if(idx>=g_numElements) return 0; uintptr_t chunk=rdptr(g_chunks + (uintptr_t)(idx>>16)*8); if(!chunk) return 0;
    uintptr_t item=chunk + (uintptr_t)(idx&0xFFFF)*ITEM_STRIDE; return rdptr(item /*+0 Object*/);
}
static uint32_t item_flags(uint32_t idx){ uintptr_t chunk=rdptr(g_chunks+(uintptr_t)(idx>>16)*8); if(!chunk) return 0;
    return rd32(chunk+(uintptr_t)(idx&0xFFFF)*ITEM_STRIDE + 8); }

// R2(robust): locate GUObjectArray by a NAME-VALIDATED pointer chain (needs R1). A slot A holds
// FChunkedFixedUObjectArray.Objects (FUObjectItem**). Chain: A -> Q(chunk-ptr array) -> chunk0 ->
// item0.Object(obj0). Valid iff obj0.InternalIndex==0, obj1.InternalIndex==1, and obj0's FName is
// printable. Then NumElements sits just after Objects; NumChunks == leading non-null entries of Q.
static uint32_t g_ne_off=0x14;
static uint32_t count_chunks(uintptr_t Q){ uint32_t n=0; for(;n<4096;n++){ if(!rdptr(Q+(uintptr_t)n*8)) break; } return n; }
static bool validate_chain(uintptr_t Q){
    if(!Q||!in_range(Q,8)) return false;
    uintptr_t R=rdptr(Q); if(!R||!in_range(R,2*ITEM_STRIDE)) return false;              // chunk0
    uintptr_t o0=rdptr(R); if(!o0||!in_range(o0,0x30)||rd32(o0+OFF_Index)!=0) return false;   // obj0 idx0
    uintptr_t o1=rdptr(R+ITEM_STRIDE); if(!o1||!in_range(o1,0x30)||rd32(o1+OFF_Index)!=1) return false; // obj1 idx1
    char nm[64]; uint32_t id=rd32(o0+OFF_Name); fname_resolve(id,nm,sizeof nm);
    return nm[0]!=0 && nm[0]!='?';
}
// A candidate = address of the Objects field. NumElements is read at A+0x10..A+0x24 (slide).
static bool try_objects_field(uintptr_t A){
    uintptr_t Q=rdptr(A); if(!validate_chain(Q)) return false;
    uint32_t ncReal=count_chunks(Q); if(ncReal==0) return false;
    for(uint32_t d=0x10; d<=0x24; d+=4){ uint32_t ne=rd32(A+d);
        if(ne<10000||ne>5000000) continue;
        if(((ne+65535)/65536)!=ncReal) continue;
        g_chunks=Q; g_numElements=ne; g_numChunks=ncReal; g_ne_off=d; g_objarray=A-0x10; return true; }
    return false;
}
// try a FUObjectArray head candidate: Objects is at head+ObjObjects+0x00 (slide ObjObjects offset)
static bool try_objarray(uintptr_t head){
    static const uint32_t ooCand[]={0x10,0x00,0x08,0x18,0x20,0x28};
    for(uint32_t i=0;i<6;i++){ if(in_range(head+ooCand[i],8) && try_objects_field(head+ooCand[i])) return true; }
    return false;
}
static bool scan_objarray(){
    FILE* f=fopen("/proc/self/maps","r"); if(!f) return false; char line[1024]; bool hit=false;
    while(fgets(line,sizeof line,f)&&!hit){
        uintptr_t lo,hi; char perm[8];
        if(sscanf(line,"%lx-%lx %4s",&lo,&hi,perm)!=3) continue;
        if(perm[0]!='r'||perm[1]!='w') continue;
        if(hi<=g_base||lo>=g_base+0x08000000) continue; if(lo<g_base) lo=g_base;
        for(uintptr_t p=(lo+7)&~(uintptr_t)7; p+8<=hi; p+=8){ if(try_objects_field(p)){ hit=true; break; } }
    }
    fclose(f); return hit;
}

// ---- output helpers ----
static char PATH[512];
static const char* op(const char* f){ snprintf(PATH,sizeof PATH,"%s/%s",OUTDIR,f); return PATH; }

// tunable params (edit tribemod/params.txt + re-touch dump_now — no rebuild)
static uintptr_t P_np=0, P_ga=0, P_probe=0, P_abs=0; static int P_bo=-1; static uint32_t P_probelen=0, P_abslen=0;
static void read_params(){ char p[600]; snprintf(p,sizeof p,"%s/params.txt",OUTDIR); FILE* f=fopen(p,"r"); if(!f) return;
    char line[256]; unsigned long v,v2;
    while(fgets(line,sizeof line,f)){
        if(sscanf(line,"np=%lx",&v)==1) P_np=v;
        else if(sscanf(line,"ga=%lx",&v)==1) P_ga=v;
        else if(sscanf(line,"bo=%lx",&v)==1) P_bo=(int)v;
        else if(sscanf(line,"probe=%lx,%lx",&v,&v2)==2){ P_probe=v; P_probelen=(uint32_t)v2; }
        else if(sscanf(line,"abs=%lx,%lx",&v,&v2)==2){ P_abs=v; P_abslen=(uint32_t)v2; }
    } fclose(f);
}
static void hexdump_to(FILE* fo,const char* label,uintptr_t addr,uint32_t len){
    fprintf(fo,"%s @0x%lx:\n",label,(unsigned long)addr);
    for(uint32_t o=0;o<len;o+=16){ fprintf(fo,"  +%03x:",o);
        for(uint32_t i=0;i<16&&o+i<len;i++){ uint8_t b; if(sr(addr+o+i,&b,1))fprintf(fo," %02x",b); else fprintf(fo," ??"); }
        fprintf(fo,"  "); for(uint32_t i=0;i<16&&o+i<len;i++){ uint8_t c=0; sr(addr+o+i,&c,1); fprintf(fo,"%c",(c>=32&&c<127)?c:'.'); } fprintf(fo,"\n"); }
}

int g_fails=0; static FILE* g_sc=0;
static void ck(const char* name,bool ok,const char* fmt,...){ char m[256]; va_list ap; va_start(ap,fmt); vsnprintf(m,sizeof m,fmt,ap); va_end(ap);
    if(!ok) g_fails++; if(g_sc) fprintf(g_sc,"[%s] %s : %s\n", ok?"PASS":"FAIL", name, m); LOGI("[%s] %s : %s", ok?"PASS":"FAIL", name, m); }

static void full_path(uintptr_t obj,char* buf,int n){ char parts[8][128]; int np=0; uintptr_t o=obj;
    for(int i=0;i<8 && o;i++){ obj_name(o,parts[np++],128); o=rdptr(o+OFF_Outer); }
    int j=0; for(int i=np-1;i>=0;i--){ j+=snprintf(buf+j,n-j,"%s%s",(i==np-1)?"":".",parts[i]); if(j>=n-1)break; } if(np==0)buf[0]=0; }

// find first object with given class-name and (RF_ClassDefaultObject set/clear)
static const uint32_t RF_ClassDefaultObject=0x10;
static uintptr_t find_obj(const char* clsname, int wantCDO /*-1 any,0 non-cdo,1 cdo*/){
    char cn[128];
    for(uint32_t i=0;i<g_numElements;i++){ uintptr_t o=obj_at(i); if(!o) continue; class_name(o,cn,sizeof cn);
        if(strcmp(cn,clsname)!=0) continue; uint32_t fl=item_flags(i); bool cdo=(fl&RF_ClassDefaultObject)||(rd32(o+OFF_Flags)&RF_ClassDefaultObject);
        if(wantCDO==-1||(wantCDO==1&&cdo)||(wantCDO==0&&!cdo)) return o; }
    return 0;
}
// find a UStruct/UClass object by its own name
static uintptr_t find_struct(const char* name){ char nm[128];
    for(uint32_t i=0;i<g_numElements;i++){ uintptr_t o=obj_at(i); if(!o) continue; obj_name(o,nm,sizeof nm); if(strcmp(nm,name)==0) return o; } return 0; }

// ---- UStruct / FField offsets (R3/R4), defaults; locked/slid in self-check ----
static uint32_t OFF_Super=0x30, OFF_Children=0x38, OFF_ChildProps=0x40, OFF_PropSize=0x48;
static uint32_t FF_Class=0x08, FF_Next=0x18, FF_Name=0x20;      // FField (Owner=8B tagged FFieldVariant)
static uint32_t FP_ElemSize=0x34, FP_Offset=0x44;               // FProperty (Offset_Internal)
// property Offset_Internal by name, walking class + supers
static int prop_offset(uintptr_t cls, const char* pname, uintptr_t* outFieldClass){
    char nm[128], tn[128];
    for(uintptr_t c=cls; c; c=rdptr(c+OFF_Super)){
        for(uintptr_t f=rdptr(c+OFF_ChildProps); f; f=rdptr(f+FF_Next)){
            uint32_t id=rd32(f+FF_Name); fname_resolve(id,nm,sizeof nm);
            if(strcmp(nm,pname)==0){ if(outFieldClass){ uintptr_t fc=rdptr(f+FF_Class); *outFieldClass=fc; } return (int)rd32(f+FP_Offset); }
        }
    }
    (void)tn; return -1;
}
static void ffield_type(uintptr_t field,char* buf,int n){ uintptr_t fc=rdptr(field+FF_Class); uint32_t id=rd32(fc /*Name@0x00*/); fname_resolve(id,buf,n); }

// decode FString {TCHAR* Data, i32 Num, i32 Max} at addr -> ascii
static void read_fstring(uintptr_t p,char* buf,int n){ uintptr_t data=rdptr(p); int num=(int)rd32(p+8);
    if(!data||num<=0){ snprintf(buf,n,"(empty)"); return; } int j=0; for(int i=0;i<num-1 && j<n-1;i++){ uint16_t c=rd16(data+(uintptr_t)i*2); buf[j++]=(c&&c<0x80)?(char)c:'?'; } buf[j]=0; }

// ---- R1(C): runtime FNamePool signature scan ----
// The FName pool's Blocks[0] points at heap block 0, which begins with the hardcoded
// EName table in registration order: None(Len=4), ByteProperty(Len=12), ...
// (header: bit0=bIsWide, bits1-5=probe hash, bits6-15=Len). We scan libUnreal's writable
// mappings for a slot whose target matches that fingerprint => that slot is &Blocks[0].
// FNameEntryAllocator: FRWLock; uint32 CurrentBlock; uint32 CurrentByteCursor; uint8* Blocks[];
// so &Blocks[0] == NamePoolData + 0x40, CurrentBlock@-8, CurrentByteCursor@-4.
static uint32_t g_np_hits=0, g_cur_block=0, g_cur_cursor=0, g_lead_blocks=0;
static bool np_fingerprint(uintptr_t b0){
    if(b0<0x10000) return false; uint8_t h[20]; if(!sr(b0,h,20)) return false;
    uint16_t h0,h1; memcpy(&h0,h,2); memcpy(&h1,h+6,2);
    if((h0&1)||(h0>>6)!=4  || memcmp(h+2,"None",4))          return false;
    if((h1&1)||(h1>>6)!=12 || memcmp(h+8,"ByteProperty",12)) return false;
    return true;
}
static bool np_scan_stride(uint32_t stride){
    FILE* f=fopen("/proc/self/maps","r"); if(!f) return false; char line[1024]; bool hit=false;
    while(fgets(line,sizeof line,f)){
        uintptr_t lo,hi; char perm[8];
        if(sscanf(line,"%lx-%lx %4s",&lo,&hi,perm)!=3) continue;
        if(perm[0]!='r'||perm[1]!='w') continue;                 // writable only
        if(hi<=g_base || lo>=g_base+0x08000000) continue;        // within libUnreal image window
        if(lo<g_base) lo=g_base;
        uintptr_t p=(lo+stride-1)&~(uintptr_t)(stride-1);
        for(; p+8<=hi; p+=stride){
            uintptr_t b0; if(!sr(p,&b0,8)) continue; if(!np_fingerprint(b0)) continue;
            g_np_hits++;                                         // p == &Blocks[0]
            if(!hit){ hit=true; g_namepool=p-0x40; g_blocks_off=0x40;
                g_cur_block=rd32(p-8); g_cur_cursor=rd32(p-4);
                for(uint32_t b=0;b<8192;b++){ if(rdptr(p+(uintptr_t)b*8)) g_lead_blocks++; else break; } }
        }
    }
    fclose(f); return hit;
}
static bool scan_namepool(){ g_np_hits=0; g_lead_blocks=0; if(np_scan_stride(64)) return true; return np_scan_stride(8); }

// ---- Session-3 prep (read-only): path-resolved classes/functions, props, UFunction sdk ----
// Resolve by exact full path; for classes require Number==0 and a *GeneratedClass/Class meta-class.
static uintptr_t find_by_path(const char* path, int wantClass){
    char fp[512], cn[128];
    for(uint32_t i=0;i<g_numElements;i++){ uintptr_t o=obj_at(i); if(!o) continue;
        if(rd32(o+OFF_Name+4)!=0) continue;                     // FName Number must be 0
        full_path(o,fp,sizeof fp); if(strcmp(fp,path)!=0) continue;
        if(wantClass){ class_name(o,cn,sizeof cn);
            if(strcmp(cn,"BlueprintGeneratedClass")&&strcmp(cn,"WidgetBlueprintGeneratedClass")&&strcmp(cn,"Class")) continue; }
        return o; }
    return 0;
}
static void dump_props(FILE* fo,const char* clsPath){
    uintptr_t cls=find_by_path(clsPath,1);
    fprintf(fo,"\n==== properties of %s  (class=0x%lx) ====\n",clsPath,(unsigned long)cls);
    if(!cls){ fprintf(fo,"  (class not found)\n"); return; }
    int depth=0;
    for(uintptr_t c=cls; c && depth<14; c=rdptr(c+OFF_Super),depth++){
        char cnm[128]; obj_name(c,cnm,sizeof cnm); uint32_t ps=rd32(c+OFF_PropSize);
        fprintf(fo,"  [%s] PropertiesSize=0x%x\n",cnm,ps);
        int n=0; for(uintptr_t f=rdptr(c+OFF_ChildProps); f && n<256; f=rdptr(f+FF_Next),n++){
            char ty[64],nm[128]; ffield_type(f,ty,sizeof ty); uint32_t id=rd32(f+FF_Name); fname_resolve(id,nm,sizeof nm);
            uint32_t off=rd32(f+FP_Offset), es=rd32(f+FP_ElemSize);
            fprintf(fo,"    +0x%04x  %-26s %-40s elem=0x%x\n",off,ty,nm,es); }
    }
}
// dump a UScriptStruct layout: field offsets/types/sizes + PropertiesSize (=C++ struct size) + a raw
// hexdump of the struct object tail (to locate CppStructOps/StructFlags). Needed to build glTFRuntime
// config param blobs (glTFRuntimeConfig.TransformBaseType, SkeletalMeshConfig.MaterialsConfig.bSkipLoad,...).
static void dump_struct(FILE* fo,const char* structPath){
    uintptr_t st=find_by_path(structPath,0);
    fprintf(fo,"\n==== ScriptStruct %s  (0x%lx) ====\n",structPath,(unsigned long)st);
    if(!st){ fprintf(fo,"  (not found)\n"); return; }
    for(uintptr_t c=st; c; c=rdptr(c+OFF_Super)){
        char cnm[128]; obj_name(c,cnm,sizeof cnm); uint32_t ps=rd32(c+OFF_PropSize);
        fprintf(fo,"  [%s] PropertiesSize=0x%x (struct size)\n",cnm,ps);
        int n=0; for(uintptr_t f=rdptr(c+OFF_ChildProps); f && n<256; f=rdptr(f+FF_Next),n++){
            char ty[64],nm[128]; ffield_type(f,ty,sizeof ty); uint32_t id=rd32(f+FF_Name); fname_resolve(id,nm,sizeof nm);
            uint32_t off=rd32(f+FP_Offset), es=rd32(f+FP_ElemSize);
            fprintf(fo,"    +0x%04x  %-26s %-40s elem=0x%x\n",off,ty,nm,es); }
    }
    hexdump_to(fo,"  UScriptStruct tail[0x50..0xd0] (StructFlags/CppStructOps)",st+0x50,0x80);
}
static void dump_ufunction(FILE* fo,const char* fnPath){
    uintptr_t fn=find_by_path(fnPath,0);
    fprintf(fo,"\n==== UFunction %s  (0x%lx) ====\n",fnPath,(unsigned long)fn);
    if(!fn){ fprintf(fo,"  (not found)\n"); return; }
    hexdump_to(fo,"  raw[0..0xE0]",fn,0xE0);                     // pin FunctionFlags/ParmsSize/Func offsets
    uintptr_t scriptData=rdptr(fn+0x60); uint32_t scriptNum=rd32(fn+0x68), scriptMax=rd32(fn+0x6C);
    fprintf(fo,"  UStruct.Script @0x60: Data=0x%lx Num=%u Max=%u\n",(unsigned long)scriptData,scriptNum,scriptMax);
    fprintf(fo,"  ChildProperties (params+locals):\n"); int n=0;
    for(uintptr_t f=rdptr(fn+OFF_ChildProps); f && n<40; f=rdptr(f+FF_Next),n++){
        char ty[64],nm[128]; ffield_type(f,ty,sizeof ty); uint32_t id=rd32(f+FF_Name); fname_resolve(id,nm,sizeof nm);
        uint32_t off=rd32(f+FP_Offset), es=rd32(f+FP_ElemSize);
        fprintf(fo,"    +0x%04x %-22s %-28s elem=0x%x\n",off,ty,nm,es); }
    // pinned UFunction fields (native functions carry FUNC_Native 0x400; Func is the C++ impl RVA)
    uint32_t ff=rd32(fn+0xB0); uint32_t nparm=rd32(fn+0xB4)&0xFF; uint16_t psz=rd16(fn+0xB6);
    uintptr_t func=rdptr(fn+0xD8);
    fprintf(fo,"  FunctionFlags=0x%08x NumParms=%u ParmsSize=0x%x native=%s Func=0x%lx Func_rva=0x%lx (ghidra=0x%lx)\n",
        ff,nparm,psz,(ff&0x400)?"YES":"no",(unsigned long)func,
        (unsigned long)(func?func-g_base:0),(unsigned long)(func?func-g_base+0x100000:0));
    if(scriptData && scriptNum){ uint32_t cap=scriptNum<0x600?scriptNum:0x600; hexdump_to(fo,"  Script bytecode[0..cap]",scriptData,cap);
        uint32_t annCap=scriptNum<0x6000?scriptNum:0x6000;   // annotate the WHOLE script (ubergraph logic is past 0x600)
        // annotate every embedded pointer that resolves to an FField (property) or UObject (fn/const)
        fprintf(fo,"  --- bytecode pointer refs (property/function/object) ---\n");
        for(uint32_t k=0;k+8<=scriptNum && k<annCap;k++){ uintptr_t p; if(!sr(scriptData+k,&p,8)) continue;
            if(p<0x10000||!in_range(p,0x30)) continue;
            uintptr_t fc=rdptr(p+FF_Class); char ty[64]={0};
            if(fc&&in_range(fc,8)){ fname_resolve(rd32(fc),ty,sizeof ty);
                if(strstr(ty,"Property")){ char nm[96]; fname_resolve(rd32(p+FF_Name),nm,sizeof nm);
                    if(nm[0]&&nm[0]!='?'){ fprintf(fo,"    @%3u  FField  %-22s %s\n",k,ty,nm); k+=7; continue; } } }
            uint32_t idx=rd32(p+OFF_Index); uintptr_t cls=rdptr(p+OFF_Class);
            if(idx<g_numElements && cls && in_range(cls,0x20)){ char cn[96],on[96]; obj_name(cls,cn,sizeof cn); obj_name(p,on,sizeof on);
                if(cn[0]&&cn[0]!='?'&&on[0]&&on[0]!='?'){ fprintf(fo,"    @%3u  UObj    %-22s %s\n",k,cn,on); k+=7; } } }
        // annotate by-name virtual calls: EX_LocalVirtualFunction(0x45)/EX_VirtualFunction(0x1b)+FScriptName{cmp,disp,num}
        fprintf(fo,"  --- bytecode by-name calls (EX_[Local]VirtualFunction) ---\n");
        for(uint32_t k=0;k+13<=scriptNum && k<annCap;k++){ uint8_t op; if(!sr(scriptData+k,&op,1)) continue;
            if(op!=0x45 && op!=0x1b) continue; uint32_t cmp=rd32(scriptData+k+1); char nm[128]; fname_resolve(cmp,nm,sizeof nm);
            if(nm[0]&&nm[0]!='?'&&strlen(nm)>=3) fprintf(fo,"    @%3u  %-12s FName=0x%08x  %s\n",k,op==0x45?"LocalVirtual":"Virtual",cmp,nm); }
    }
}
// list a class's UFunctions (Children UField list, Next@0x28) with their FName ComparisonIndex, walking supers.
// Directly resolves an EX_LocalVirtualFunction target id (e.g. 0x1a1485) to a function name -- name, not vtable slot.
static void list_class_functions(FILE* fo,const char* clsPath){
    uintptr_t cls=find_by_path(clsPath,1);
    fprintf(fo,"\n==== functions of %s (class=0x%lx) [FName id -> name] ====\n",clsPath,(unsigned long)cls);
    if(!cls){ fprintf(fo,"  (class not found)\n"); return; }
    int depth=0;
    for(uintptr_t c=cls; c && depth<4; c=rdptr(c+OFF_Super),depth++){
        char cnm[128]; obj_name(c,cnm,sizeof cnm);
        int n=0; for(uintptr_t f=rdptr(c+OFF_Children); f && n<128; f=rdptr(f+0x28),n++){
            uint32_t id=rd32(f+OFF_Name); char nm[128]; fname_resolve(id,nm,sizeof nm);
            fprintf(fo,"  [%-28s] FName=0x%08x  %s\n",cnm,id,nm); }
    }
}

// ---- read-only address calibration: resolve the Ghidra-rva -> runtime skew per code region ----
// Ghidra static addresses can differ from runtime by a per-segment delta (0 or 0x1000 seen). For each
// known Ghidra rva we hexdump base+rva and base+rva+0x1000 and flag which looks like an AArch64 function
// prologue, so hook/call targets are calibrated before any inline hook. Anchor: dispatcher 0x4ffc2d4
// (an earlier inline hook fired there at +0, so that region has delta 0).
static bool looks_prologue(uintptr_t a){ uint32_t w=rd32(a); uint8_t b3=(w>>24)&0xff;
    if(w==0xD503233F) return true;                 // paciasp
    if(b3==0xD1) return true;                       // sub sp,sp,#imm
    if(b3==0xA9 && ((w>>16)&0xff)>=0x80) return true; // stp ...,[sp,#-imm]! (pre-index)
    if((w&0xFFFFFF00)==0xD53BD000) return true;     // mrs x?,tpidr_el0 (stack-guard preamble)
    if(b3==0xD1||b3==0xA9) return true; return false; }
static void calib_one(FILE* fo,const char* label,uintptr_t rva){
    uintptr_t a0=g_base+rva, a1=g_base+rva+0x1000;
    fprintf(fo,"\n%-16s ghidra_rva=0x%lx\n",label,(unsigned long)rva);
    fprintf(fo,"  +0     @0x%lx prologue=%d : ",(unsigned long)a0,looks_prologue(a0)); for(int i=0;i<20;i++){ uint8_t b; fprintf(fo,"%02x ",sr(a0+i,&b,1)?b:0); } fprintf(fo,"\n");
    fprintf(fo,"  +0x1000@0x%lx prologue=%d : ",(unsigned long)a1,looks_prologue(a1)); for(int i=0;i<20;i++){ uint8_t b; fprintf(fo,"%02x ",sr(a1+i,&b,1)?b:0); } fprintf(fo,"\n");
}
static void calib(){
    FILE* fo=fopen(op("calib.txt"),"w"); if(!fo) return;
    fprintf(fo,"base=0x%lx\n",(unsigned long)g_base);
    calib_one(fo,"dispatcher",0x4ffc2d4);   // ANCHOR: worked at +0 (delta 0 region)
    calib_one(fo,"glTF_choke",0x4ff4548);   // ANCHOR2: earlier hook target
    calib_one(fo,"ProcessEvent",0x1857dd4); // vt slot78 twin (expect prologue at +0 OR +0x1000)
    calib_one(fo,"CallFunction",0x1856bac);
    calib_one(fo,"glTF_entry",0x4ac2de0);   // caller of glTF async load (diagnostic hook target)
    calib_one(fo,"AddError_site",0x4c1b950);
    fclose(fo);
}

// ---- read-only ini probe: find & copy the game's *.ini (config lives in the internal files dir) ----
static int g_ini_ct=0, g_walk_budget=300000;
static void copy_out(const char* src,const char* base){ char dst[720]; snprintf(dst,sizeof dst,"%s/ini/%02d_%s",OUTDIR,g_ini_ct++,base);
    int in=open(src,O_RDONLY); if(in<0) return; int out=open(dst,O_WRONLY|O_CREAT|O_TRUNC,0666); if(out<0){close(in);return;}
    char b[8192]; ssize_t n; while((n=read(in,b,sizeof b))>0){ if(write(out,b,n)!=n) break; } close(in); close(out); }
static void list_dir(FILE* fo,const char* dir){ DIR* d=opendir(dir); fprintf(fo,"[%s] %s\n",d?"DIR ":"absent",dir); if(!d) return;
    struct dirent* e; while((e=readdir(d))){ if(e->d_name[0]=='.') continue; fprintf(fo,"    %s\n",e->d_name); } closedir(d); }
static bool ends_ini(const char* s){ size_t L=strlen(s); return L>4 && (strcmp(s+L-4,".ini")==0||strcmp(s+L-4,".INI")==0); }
static void walk_ini(FILE* fo,const char* dir,int depth){ if(depth>12||g_walk_budget<0) return; DIR* d=opendir(dir); if(!d) return;
    struct dirent* e; while((e=readdir(d))){ if(--g_walk_budget<0) break; if(e->d_name[0]=='.') continue;
        char p[1024]; snprintf(p,sizeof p,"%s/%s",dir,e->d_name); struct stat st; if(lstat(p,&st)!=0) continue;
        if(S_ISDIR(st.st_mode)) walk_ini(fo,p,depth+1);
        else if(ends_ini(e->d_name)){ fprintf(fo,"INI %s  (%ld bytes)\n",p,(long)st.st_size); copy_out(p,e->d_name); } }
    closedir(d); }

// ---- the dump ----
static void do_dump(){
    load_maps();
    read_params();
    g_sc=fopen(op("selfcheck.txt"),"w");
    if(g_sc) fprintf(g_sc,"base=0x%lx  params: np=0x%lx ga=0x%lx bo=0x%x probe=0x%lx,%u\n",
        (unsigned long)g_base,(unsigned long)P_np,(unsigned long)P_ga,P_bo,(unsigned long)P_probe,P_probelen);

    // generic memory probe (base + P_probe) and absolute probe (abs=)
    if(P_probe){ FILE* pf=fopen(op("probe.txt"),"w"); if(pf){ hexdump_to(pf,"probe(base+off)",g_base+P_probe,P_probelen?P_probelen:0x80); fclose(pf); } }
    if(P_abs){ FILE* pf=fopen(op("abs.txt"),"w"); if(pf){ hexdump_to(pf,"abs",P_abs,P_abslen?P_abslen:0x80); fclose(pf); } }

    // R1: NamePool via runtime signature scan (option C); params np=/bo= override the scan.
    char t[64]; bool r1=false;
    if(P_np){ g_namepool=g_base+P_np; g_blocks_off=(P_bo>=0)?(uint32_t)P_bo:0x40; }
    else { scan_namepool(); }
    uintptr_t npRva = g_namepool? (g_namepool-g_base):0;
    if(g_namepool){ int len=fname_resolve(0,t,sizeof t); r1=(len==4&&strcmp(t,"None")==0); } else t[0]=0;
    ck("R1.NamePool.scan", g_namepool!=0,
       "NamePoolData rva=0x%lx hits=%u blocks_off=0x%x CurrentBlock=%u CurrentByteCursor=%u leadBlocks=%u",
       (unsigned long)npRva,g_np_hits,g_blocks_off,g_cur_block,g_cur_cursor,g_lead_blocks);
    ck("R1.NamePool.Resolve(0)==None", r1, "resolved='%s' (rva=0x%lx)", t, (unsigned long)npRva);
    // small diagnostic to aid iteration
    FILE* nd=fopen(op("namepool_diag.txt"),"w");
    if(nd){ fprintf(nd,"NamePoolData @0x%lx (rva 0x%lx) hits=%u blocks_off=0x%x CurrentBlock=%u CurrentByteCursor=%u leadBlocks=%u\n",
            (unsigned long)g_namepool,(unsigned long)npRva,g_np_hits,g_blocks_off,g_cur_block,g_cur_cursor,g_lead_blocks);
        if(g_namepool){ hexdump_to(nd,"pool[0..0x80]",g_namepool,0x80);
            uintptr_t b0=rdptr(g_namepool+g_blocks_off); fprintf(nd,"Blocks[0]=0x%lx\n",(unsigned long)b0);
            if(b0) hexdump_to(nd,"block0[0..0x60]",b0,0x60); }
        fclose(nd); }

    // R2: GUObjectArray — validate a candidate by name-free invariants (chunk ptr, sane counts,
    //     NumChunks==ceil(NumElements/65536), obj0/obj1 InternalIndex==0/1). Try param, GOT slot,
    //     static RVA, then a signature scan; try_objarray slides the NumElements offset.
    uintptr_t candGot=rdptr(g_base+RVA_GUObj_GOTslot), candDirect=g_base+RVA_GUObjectArray;
    const char* via="none"; bool p2a=false;
    if(P_ga && try_objarray(g_base+P_ga)) { via="param";  p2a=true; }
    if(!p2a && try_objarray(candGot))     { via="got";    p2a=true; }
    if(!p2a && try_objarray(candDirect))  { via="direct"; p2a=true; }
    if(!p2a && scan_objarray())           { via="scan";   p2a=true; }
    uintptr_t gaRva = g_objarray? (g_objarray-g_base):0;
    ck("R2a.objarray", p2a, "via=%s GUObjectArray rva=0x%lx NumElements=%u NumChunks=%u neOff=0x%x (got->rva=0x%lx direct.rva=0x%lx)",
       via,(unsigned long)gaRva,g_numElements,g_numChunks,g_ne_off,
       (unsigned long)(candGot?candGot-g_base:0),(unsigned long)(candDirect-g_base));
    bool canWalk=p2a;
    if(p2a){ uintptr_t o0=obj_at(0),o1=obj_at(1); uint32_t i0=rd32(o0+OFF_Index),i1=rd32(o1+OFF_Index);
        ck("R2b.index0/1",i0==0&&i1==1,"obj0=0x%lx idx=%u obj1 idx=%u",(unsigned long)o0,i0,i1);
        if(r1){ char c0[128]; obj_name(o0,c0,sizeof c0); ck("R2c.obj0.name_printable",c0[0]!=0&&c0[0]!='?',"obj0.name='%s'",c0); } }

    // R3: lock UStruct offsets name-free. Class = self-referential ClassPrivate; Object = a UClass
    //     with SuperStruct==0 && PropertiesSize==0x28. Slide (Super,PropSize) until it resolves.
    bool r3=false; uintptr_t cClass=0, cObject=0;
    if(canWalk){
        for(uint32_t i=0;i<g_numElements && !cClass;i++){ uintptr_t o=obj_at(i); if(o && rdptr(o+OFF_Class)==o) cClass=o; }
        uint32_t sc[4]={0x30,0x38,0x40,0x28};
        for(int k=0;k<4 && !r3;k++){ uint32_t so=sc[k], po=so+0x18;
            for(uint32_t i=0;i<g_numElements;i++){ uintptr_t o=obj_at(i); if(!o) continue;
                if(rdptr(o+OFF_Class)!=cClass) continue;                         // is a UClass
                if(rdptr(o+so)==0 && rd32(o+po)==0x28){                          // Object invariant
                    cObject=o; OFF_Super=so; OFF_PropSize=po; OFF_Children=so+0x08; OFF_ChildProps=so+0x10; r3=true; break; } } }
    }
    ck("R3a.Class.self_ref", cClass!=0, "Class(ClassPrivate==self)=0x%lx",(unsigned long)cClass);
    ck("R3b.UStruct.offsets", r3, "Object=0x%lx Super=0x%x Children=0x%x ChildProps=0x%x PropSize=0x%x",
       (unsigned long)cObject,OFF_Super,OFF_Children,OFF_ChildProps,OFF_PropSize);
    // coupling: once names (R1) AND offsets (R3) are green, confirm the two anchors resolve to their names
    if(r1&&r3){ char n1[64],n2[64]; obj_name(cClass,n1,sizeof n1); obj_name(cObject,n2,sizeof n2);
        ck("R3c.coupling", strcmp(n1,"Class")==0&&strcmp(n2,"Object")==0, "Class.name='%s' Object.name='%s'",n1,n2); }
    // Actor sanity (needs names)
    if(r1&&canWalk){ uintptr_t cActor=find_struct("Actor");
        if(cActor){ char sn[128]; uintptr_t as=rdptr(cActor+OFF_Super); obj_name(as,sn,sizeof sn); uint32_t aps=rd32(cActor+OFF_PropSize);
            ck("R3d.Actor",strcmp(sn,"Object")==0&&aps>0x28,"Actor.Super='%s' PropSize=0x%x",sn,aps); } }

    // R4: FField/FProperty sanity on Actor's ChildProperties (needs names + locked offsets)
    if(r1&&r3&&canWalk){ uintptr_t cActor=find_struct("Actor");
      if(cActor){ int cnt=0; bool okChain=true; uint32_t aps=rd32(cActor+OFF_PropSize); char tbl[1024]; int tl=0;
        for(uintptr_t f=rdptr(cActor+OFF_ChildProps); f && cnt<12; f=rdptr(f+FF_Next),cnt++){
          char ty[64],nm[128]; ffield_type(f,ty,sizeof ty); uint32_t id=rd32(f+FF_Name); fname_resolve(id,nm,sizeof nm);
          uint32_t off=rd32(f+FP_Offset); if(off>=aps+0x1000) okChain=false;
          tl+=snprintf(tbl+tl,sizeof(tbl)-tl,"  +0x%03x %s %s\n",off,ty,nm); }
        ck("R4.FField.chain",cnt>0&&okChain,"props=%d\n%s",cnt,tbl); } }

    // ---- calib.txt: resolve Ghidra->runtime skew for hook/call targets (read-only) ----
    calib();

    // ---- objects.txt (full walk; needs names) ----
    FILE* fo=(r1&&canWalk)?fopen(op("objects.txt"),"w"):0;
    if(fo){ char cn[128],nm[128],fp[512];
      for(uint32_t i=0;i<g_numElements;i++){ uintptr_t o=obj_at(i); if(!o) continue; uint32_t fl=item_flags(i);
        class_name(o,cn,sizeof cn); full_path(o,fp,sizeof fp);
        fprintf(fo,"%08u 0x%016lx flags=%08x %-42s %s\n",i,(unsigned long)o,fl,cn,fp); }
      fclose(fo); }

    // ---- values.txt (the decision; needs names + locked UStruct offsets) ----
    FILE* fv=(r1&&r3&&canWalk)?fopen(op("values.txt"),"w"):0;
    if(fv){
      // residency of key classes
      const char* keys[]={"BP_ReadyPlayerMeAvatarSkin_C","BP_OculusAvatarSkin_C","W_RPMAvatarCreator_C","BP_TribeSkinBase_C"};
      for(auto k:keys){ uintptr_t c=find_struct(k); fprintf(fv,"resident %-32s : %s (0x%lx)\n",k,c?"YES":"no",(unsigned long)c); }
      // TribePawnBP_C: CDO vs live ActiveSkinClasses (CDO detected by Default__ name / RF flag)
      uintptr_t pawnCls=find_struct("TribePawnBP_C");
      int offASC = pawnCls? prop_offset(pawnCls,"ActiveSkinClasses",0):-1;
      fprintf(fv,"\nTribePawnBP_C class=0x%lx ActiveSkinClasses@0x%x\n",(unsigned long)pawnCls,offASC);
      for(uint32_t i=0;i<g_numElements;i++){ uintptr_t o=obj_at(i); if(!o) continue; char cn[128]; class_name(o,cn,sizeof cn);
        if(strcmp(cn,"TribePawnBP_C")!=0) continue;
        char onm[128],fp[512]; obj_name(o,onm,sizeof onm); full_path(o,fp,sizeof fp);
        bool cdo=(strncmp(onm,"Default__",9)==0)||(rd32(o+OFF_Flags)&RF_ClassDefaultObject);
        fprintf(fv,"  %-4s CDO=%-3s %s",cdo?"CDO":"live",cdo?"YES":"no",fp);
        if(offASC>=0){ uintptr_t arr=o+offASC; uintptr_t data=rdptr(arr); int num=(int)rd32(arr+8); fprintf(fv," ASC[%d]={",num);
          for(int e=0;e<num&&e<8;e++){ uintptr_t cls=rdptr(data+(uintptr_t)e*8); char kn[128]; obj_name(cls,kn,sizeof kn); fprintf(fv,"%s%s",e?",":"",kn); } fprintf(fv,"}"); }
        fprintf(fv,"\n"); }
      // Are any avatar-skin objects actually instantiated (and on which actor)?
      const char* skc[]={"BP_ReadyPlayerMeAvatarSkin_C","BP_OculusAvatarSkin_C","BP_EnvironmentSkin_C"};
      for(auto sc:skc){ int n=0; fprintf(fv,"\ninstances of %s:\n",sc);
        for(uint32_t i=0;i<g_numElements && n<12;i++){ uintptr_t o=obj_at(i); if(!o) continue; char cn[128]; class_name(o,cn,sizeof cn);
          if(strcmp(cn,sc)!=0) continue; char onm[128],fp[512]; obj_name(o,onm,sizeof onm); full_path(o,fp,sizeof fp);
          bool cdo=(strncmp(onm,"Default__",9)==0)||(rd32(o+OFF_Flags)&RF_ClassDefaultObject);
          fprintf(fv,"   0x%lx %s %s\n",(unsigned long)o,cdo?"[CDO] ":"[live]",fp); n++; }
        if(n==0) fprintf(fv,"   (none resident)\n"); }
      // GameInstance AvatarId + bHasCustomAvatar
      uintptr_t giCls=find_struct("TribeGameInstanceBP_C"); uintptr_t gi=find_obj("TribeGameInstanceBP_C",0);
      int offGIA=giCls?prop_offset(giCls,"AvatarId",0):-1;
      fprintf(fv,"\nTribeGameInstanceBP_C inst=0x%lx AvatarId@0x%x\n",(unsigned long)gi,offGIA);
      if(gi&&offGIA>=0){ char s[256]; read_fstring(gi+offGIA,s,sizeof s); fprintf(fv,"  AvatarId='%s'\n",s); }
      fclose(fv);
    }

    // ---- sdk.txt (Session-3 prep: vtable for L3, class props, UFunction layouts) ----
    FILE* fs=(r1&&r3&&canWalk)?fopen(op("sdk.txt"),"w"):0;
    if(fs){
      // Default__Object vtable -> RVA + slots (find ProcessEvent in Ghidra from these)
      uintptr_t objCDO=find_by_path("/Script/CoreUObject.Default__Object",0);
      if(!objCDO){ for(uint32_t i=0;i<g_numElements;i++){ uintptr_t o=obj_at(i); if(!o)continue; char cn[128]; class_name(o,cn,sizeof cn);
          if(strcmp(cn,"Object")==0 && (rd32(o+OFF_Flags)&RF_ClassDefaultObject)){ objCDO=o; break; } } }
      uintptr_t vt=objCDO?rdptr(objCDO):0;
      fprintf(fs,"Default__Object=0x%lx vtable=0x%lx vtable_rva=0x%lx (ghidra=0x%lx)\n",
        (unsigned long)objCDO,(unsigned long)vt,(unsigned long)(vt?vt-g_base:0),(unsigned long)(vt?vt-g_base+0x100000:0));
      for(int s=0;s<96 && vt;s++){ uintptr_t sl=rdptr(vt+(uintptr_t)s*8);
        fprintf(fs,"  vt[%02d] rva=0x%08lx ghidra=0x%08lx\n",s,(unsigned long)(sl?sl-g_base:0),(unsigned long)(sl?sl-g_base+0x100000:0)); }

      // full property layouts (AvatarId neighbors, cached RPM url/skin map, skin visibility fields)
      dump_props(fs,"/Game/GameModes/TribeGameInstanceBP.TribeGameInstanceBP_C");
      dump_props(fs,"/Game/Visuals/BP_TribeVisualsManager.BP_TribeVisualsManager_C");
      dump_props(fs,"/Game/Pawn/TribePawnBP.TribePawnBP_C");
      dump_props(fs,"/Game/Visuals/Skins/OculusAvatar/BP_ReadyPlayerMeAvatarSkin.BP_ReadyPlayerMeAvatarSkin_C");
      dump_props(fs,"/Game/Visuals/Skins/OculusAvatar/BP_OculusAvatarSkin.BP_OculusAvatarSkin_C");

      // the five RPM-pipeline UFunctions (params/offsets/types, Script.Num, raw layout, bytecode)
      const char* fns[]={
        "/Game/Visuals/BP_TribeVisualsManager.BP_TribeVisualsManager_C.InitMyRPMAvatarSkin",
        "/Game/Visuals/BP_TribeVisualsManager.BP_TribeVisualsManager_C.AddOrUpdateCachedRPMAvatarSkin",
        "/Game/Visuals/BP_TribeVisualsManager.BP_TribeVisualsManager_C.ApplySkinToPlayer",
        // the creator paste->load->handle chain (Blueprint bytecode; resolves post-download steps)
        "/Game/Menus/W_RPMAvatarCreator.W_RPMAvatarCreator_C.PasteAvatarUrl",
        "/Game/Menus/W_RPMAvatarCreator.W_RPMAvatarCreator_C.LoadAvatarAtUrl",
        "/Game/Menus/W_RPMAvatarCreator.W_RPMAvatarCreator_C.ReloadAvatarAtUrl",
        "/Game/Menus/W_RPMAvatarCreator.W_RPMAvatarCreator_C.HandleAvatarLoaded",
        "/Game/Menus/W_RPMAvatarCreator.W_RPMAvatarCreator_C.HandleAvatarCached",
        "/Game/Menus/W_RPMAvatarCreator.W_RPMAvatarCreator_C.GetRPMCustomSkin",
        "/Game/Menus/W_RPMAvatarCreator.W_RPMAvatarCreator_C.ClearAvatarUrl",
        "/Game/Menus/W_RPMAvatarCreator.W_RPMAvatarCreator_C.ExecuteUbergraph_W_RPMAvatarCreator",
        // native config API (Func_rva -> Ghidra to find which G*Ini backs it)
        "/Script/TribeXR.TribeBlueprintLibrary.ReadConfigString",
        "/Script/TribeXR.TribeBlueprintLibrary.WriteConfigString",
        "/Script/TribeXR.TribeBlueprintLibrary.ForceSaveConfig",
        "/Script/TribeXR.TribeBlueprintLibrary.IsValidReadyPlayerMeAvatarUrl",
        // selfie-cam / third-person visibility mechanism (why the local RPM avatar is invisible in the selfie)
        "/Game/Pawn/TribePawnBP.TribePawnBP_C.SetAvatarSceneCaptureHidden",
        "/Game/Pawn/TribePawnBP.TribePawnBP_C.SetAvatarThirdPersonVisible",
        "/Game/Visuals/BP_TribeVisualsManager.BP_TribeVisualsManager_C.FinishSkinsSetup",
        // ---- direct-glTFRuntime graft: loader + mesh-load + errors + mesh setter (param layouts) ----
        "/Script/glTFRuntime.glTFRuntimeFunctionLibrary.glTFLoadAssetFromFilename",
        "/Script/glTFRuntime.glTFRuntimeAsset.LoadSkeletalMesh",
        "/Script/glTFRuntime.glTFRuntimeAsset.GetErrors",
        "/Script/Engine.SkeletalMeshComponent.SetSkeletalMeshAsset" };
      // resolve the EX_LocalVirtualFunction target (0x1a1485) by matching FName ids to function names
      list_class_functions(fs,"/Game/Menus/W_RPMAvatarCreator.W_RPMAvatarCreator_C");
      for(auto fp:fns) dump_ufunction(fs,fp);
      // ---- glTFRuntime config struct layouts (for building the ProcessEvent param blobs) ----
      dump_struct(fs,"/Script/glTFRuntime.glTFRuntimeConfig");
      dump_struct(fs,"/Script/glTFRuntime.glTFRuntimeSkeletalMeshConfig");
      dump_struct(fs,"/Script/glTFRuntime.glTFRuntimeMaterialsConfig");
      dump_struct(fs,"/Script/glTFRuntime.glTFRuntimeSkeletonConfig");
      // ---- live component + skin props (AvatarBodyMesh offset, target skeleton, graft targets) ----
      dump_props(fs,"/Script/TribeXR.ReadyPlayerMeComponent");
      dump_props(fs,"/Script/TribeXR.TribeAvatarComponent");
      dump_props(fs,"/Game/Visuals/Skins/OculusAvatar/BP_ReadyPlayerMeAvatarSkin.BP_ReadyPlayerMeAvatarSkin_C");

      // --- glTFRuntime finalizer output: transient USkeletons. BoneTree.Num discriminates the failure:
      //     0 bones => gather failed (empty mesh finalized); ~39 (root AvatarRoot/Hips) => mesh built & dropped downstream.
      uintptr_t skelCls=find_by_path("/Script/Engine.Skeleton",1);
      int btOff = skelCls? prop_offset(skelCls,"BoneTree",0):-1;
      fprintf(fs,"\n==== USkeleton instances (glTF finalizer output)  class=0x%lx BoneTree@0x%x ====\n",(unsigned long)skelCls,btOff);
      { int n=0; for(uint32_t i=0;i<g_numElements && n<24;i++){ uintptr_t o=obj_at(i); if(!o) continue; char cn[128]; class_name(o,cn,sizeof cn);
          if(strcmp(cn,"Skeleton")!=0) continue; if(rd32(o+OFF_Flags)&RF_ClassDefaultObject) continue;
          char fp[512]; full_path(o,fp,sizeof fp); int bones = btOff>=0? (int)rd32(o+btOff+8):-1;   // TArray.Num @ +0x08
          fprintf(fs,"  0x%lx BoneTree.Num=%d  %s\n",(unsigned long)o,bones,fp);
          // FReferenceSkeleton@0x68 => RawRefBoneInfo {Data@0x68, Num@0x70}, 12B elems {FName@+0, int32 Parent@+8}
          // (wrist/forearm/tip => Meta hand skeleton; Hips/LeftHandIndex1 => glTF avatar). Fallback: scan skipping BoneTree@0x38.
          uintptr_t rri=rdptr(o+0x68); uint32_t rnum=rd32(o+0x70); uint32_t roff=0x68;
          if(!(rri && rnum>0 && rnum<4096 && in_range(rri,(size_t)rnum*12))){
              rri=0; for(uint32_t off=0x40; off<=0x220; off+=8){ if(off==btOff) continue; uintptr_t d=rdptr(o+off); uint32_t nm=rd32(o+off+8);
                  if(nm<1||nm>4096||!d||!in_range(d,(size_t)nm*12)) continue; char b0[48]; fname_resolve(rd32(d),b0,sizeof b0);
                  if(b0[0]&&b0[0]!='?'){ rri=d; rnum=nm; roff=off; break; } } }
          if(rri){ fprintf(fs,"    RawRefBoneInfo@0x%x Num=%u:",roff,rnum);
              for(uint32_t k=0;k<rnum&&k<20;k++){ char bn[64]; fname_resolve(rd32(rri+(uintptr_t)k*12),bn,sizeof bn); int par=(int)rd32(rri+(uintptr_t)k*12+8); fprintf(fs," %s(p%d)",bn,par); }
              fprintf(fs,"\n"); }
          n++; }
        if(n==0) fprintf(fs,"  (no non-CDO Skeleton instances)\n"); }
      // USkeletalMesh census: runtime (glTF) meshes lack RF_WasLoaded (0x80000); list each mesh's Skeleton.
      uintptr_t smClass=find_by_path("/Script/Engine.SkeletalMesh",1);
      int skOff = smClass? prop_offset(smClass,"Skeleton",0):-1;
      fprintf(fs,"\n==== USkeletalMesh census (Skeleton@0x%x; '*'=runtime/no RF_WasLoaded) ====\n",skOff);
      { int n=0; for(uint32_t i=0;i<g_numElements && n<40;i++){ uintptr_t o=obj_at(i); if(!o) continue; char cn[96]; class_name(o,cn,sizeof cn);
          if(strcmp(cn,"SkeletalMesh")!=0) continue; uint32_t fl=rd32(o+OFF_Flags); if(fl&RF_ClassDefaultObject) continue;
          uintptr_t sk=skOff>=0?rdptr(o+skOff):0; char skn[96]; obj_name(sk,skn,sizeof skn); char fp[512]; full_path(o,fp,sizeof fp);
          fprintf(fs,"  %c 0x%lx skel=%-24s %s\n",(fl&0x80000)?' ':'*',(unsigned long)o,skn,fp); n++; } }
      // also: is the RPM avatar's AvatarBodyMesh SkeletalMeshComponent actually holding a mesh?
      uintptr_t smcCls=find_by_path("/Script/Engine.SkeletalMeshComponent",1);
      int smaOff = smcCls? prop_offset(smcCls,"SkeletalMeshAsset",0):-1;
      if(smaOff<0 && smcCls) smaOff=prop_offset(smcCls,"SkeletalMesh",0);
      fprintf(fs,"\n==== AvatarBodyMesh SkeletalMeshAsset  (SMC class=0x%lx asset@0x%x) ====\n",(unsigned long)smcCls,smaOff);
      { int n=0; for(uint32_t i=0;i<g_numElements && n<8;i++){ uintptr_t o=obj_at(i); if(!o) continue; char nm[96]; obj_name(o,nm,sizeof nm);
          if(strcmp(nm,"AvatarBodyMesh")!=0) continue; char fp[512]; full_path(o,fp,sizeof fp);
          uintptr_t mesh = smaOff>=0? rdptr(o+smaOff):0; char mn[96]="(null)"; if(mesh) obj_name(mesh,mn,sizeof mn);
          fprintf(fs,"  0x%lx SkeletalMeshAsset=0x%lx '%s'  %s\n",(unsigned long)o,(unsigned long)mesh,mn,fp); n++; } }
      fclose(fs);
    }

    // ---- ini_report.txt (read-only): locate & copy the game's config .ini (internal files dir) ----
    FILE* fi=fopen(op("ini_report.txt"),"w");
    if(fi){ char od[600]; snprintf(od,sizeof od,"%s/ini",OUTDIR); mkdir(od,0777);
      const char* P="com.TribeXR.TribeXR"; char root[256];
      // list top-level of internal + external files dirs to see structure
      snprintf(root,sizeof root,"/data/data/%s/files",P);           list_dir(fi,root);
      snprintf(root,sizeof root,"/data/user/0/%s/files",P);          list_dir(fi,root);
      snprintf(root,sizeof root,"/sdcard/Android/data/%s/files",P);  list_dir(fi,root);
      fprintf(fi,"\n--- *.ini (recursive, copied to tribemod/ini/) ---\n");
      snprintf(root,sizeof root,"/data/data/%s/files",P);            walk_ini(fi,root,0);
      snprintf(root,sizeof root,"/sdcard/Android/data/%s/files/UnrealGame",P); walk_ini(fi,root,0);
      fprintf(fi,"\n(copied %d ini files, walk_budget_left=%d)\n",g_ini_ct,g_walk_budget);
      fclose(fi);
    }

    if(g_sc){ fprintf(g_sc,"\nTOTAL FAILS=%d\n",g_fails); fclose(g_sc); g_sc=0; }
    FILE* d=fopen(op(g_fails?"FAIL":"DONE"),"w"); if(d){ fprintf(d,"fails=%d\n",g_fails); fclose(d); }
    LOGI("dump complete, fails=%d",g_fails);
}

// ---- 3b: constructor-time config upsert (the ONE state change) ----
// Gated on tribemod/avatar_url.txt: present+nonempty => set ReadyPlayerMeAvatarUrl=<url> in [TribeAvatar];
// absent/empty => DELETE that key (kill switch, escapes a spawn crash-loop from external storage).
// Runs at dlopen, before FEngineLoop::PreInit parses any ini. Atomic (tmp+fsync+rename). ASCII only.
static const char* INI_PATH =
  "/data/data/com.TribeXR.TribeXR/files/UnrealGame/TribeXR/TribeXR/Saved/Config/Android/GameUserSettings.ini";
static void ini_status(const char* msg){ char p[600]; snprintf(p,sizeof p,"%s/ini_upsert.log",OUTDIR);
    FILE* f=fopen(p,"a"); if(f){ fprintf(f,"%s\n",msg); fclose(f);} LOGI("[INI] %s",msg); }
// Stage the avatar into the loader's cache slot so the spawn-time read is a cache HIT (local glTF load,
// no HTTP). Cache path (from Ghidra FUN_0514ec88 + FUN_050f584c): <ext files>/Documents/rpmavatar-<clean>.
// Only the app UID can write Documents/ (drwxr-s---), so this must run in the constructor. Copies from
// tribemod/custom.glb (shell-pushed). basename(url) => the clean filename the game builds.
static void stage_cache(const char* url){
    const char* base=strrchr(url,'/'); base=base?base+1:url; if(!*base) return;
    char src[700]; snprintf(src,sizeof src,"%s/custom.glb",OUTDIR);
    char dstdir[600]; snprintf(dstdir,sizeof dstdir,"/sdcard/Android/data/com.TribeXR.TribeXR/files/Documents"); mkdir(dstdir,0770);
    char dst[800]; snprintf(dst,sizeof dst,"%s/rpmavatar-%s",dstdir,base);
    struct stat ss,ds; if(stat(src,&ss)!=0){ ini_status("cache: tribemod/custom.glb missing; skip"); return; }
    if(stat(dst,&ds)==0 && ds.st_size==ss.st_size){ char m[900]; snprintf(m,sizeof m,"cache: already staged %s",dst); ini_status(m); return; }
    int in=open(src,O_RDONLY); if(in<0){ ini_status("cache: src open fail"); return; }
    int out=open(dst,O_WRONLY|O_CREAT|O_TRUNC,0644); if(out<0){ close(in); ini_status("cache: dst open fail (Documents perms?)"); return; }
    char b[65536]; ssize_t n; long tot=0; bool ok=true; while((n=read(in,b,sizeof b))>0){ if(write(out,b,n)!=n){ ok=false; break; } tot+=n; }
    close(in); close(out); char m[900]; snprintf(m,sizeof m,"cache %s: %s (%ld bytes)",ok?"staged":"PARTIAL",dst,tot); ini_status(m);
}
// read tribemod/<fname>, trim whitespace; returns true + fills out if non-empty
static bool read_trim_file(const char* fname, char* out, int cap){
    char p[600]; snprintf(p,sizeof p,"%s/%s",OUTDIR,fname);
    int fd=open(p,O_RDONLY); if(fd<0) return false; char t[1200]; ssize_t r=read(fd,t,sizeof t-1); close(fd);
    if(r<=0) return false; t[r]=0; int s=0,e=(int)r;
    while(s<e&&(t[s]==' '||t[s]=='\t'||t[s]=='\r'||t[s]=='\n'))s++;
    while(e>s&&(t[e-1]==' '||t[e-1]=='\t'||t[e-1]=='\r'||t[e-1]=='\n'))e--;
    if(e<=s) return false; int L=e-s; if(L>cap-1)L=cap-1; memcpy(out,t+s,L); out[L]=0; return true;
}
// upsert (value!=0) or delete (value==0) [TribeAvatar] <key> in GameUserSettings.ini; atomic tmp+fsync+rename.
static void upsert_ini_key(const char* key, const char* value){
    const char* SEC="[TribeAvatar]"; int kl=(int)strlen(key), sl=(int)strlen(SEC); bool have=(value!=0);
    static char buf[65536]; int n=0;
    { int fd=open(INI_PATH,O_RDONLY); if(fd<0){ ini_status("ini not readable; skip"); return; }
      ssize_t r=read(fd,buf,sizeof buf-1); close(fd); if(r<0){ ini_status("ini read error"); return; } n=(int)r; buf[n]=0; }
    if(n>=2 && (unsigned char)buf[0]==0xFF && (unsigned char)buf[1]==0xFE){ ini_status("UTF-16 BOM; bail"); return; }
    static char out[70000]; int o=0; bool inSec=false, wrote=false, sawSec=false; int i=0;
    while(i<n){ int j=i; while(j<n && buf[j]!='\n') j++; int le=(j<n)?j+1:n; int len=j-i;
        int clen=len; if(clen>0 && buf[i+clen-1]=='\r') clen--;
        bool isHdr=(clen>=2 && buf[i]=='[');
        if(isHdr){ memcpy(out+o,buf+i,le-i); o+=le-i;
            inSec=(clen==sl && strncmp(buf+i,SEC,sl)==0);
            if(inSec){ sawSec=true; if(have && !wrote){ o+=snprintf(out+o,sizeof out-o,"%s=%s\n",key,value); wrote=true; } }
        } else if(inSec && clen>=kl && strncmp(buf+i,key,kl)==0 && (buf[i+kl]=='='||buf[i+kl]==' ')){
            /* existing key line: skip (delete, or dedupe since we wrote it at the header) */
        } else { memcpy(out+o,buf+i,le-i); o+=le-i; }
        i=le; }
    if(!sawSec && have){ o+=snprintf(out+o,sizeof out-o,"%s%s\n%s=%s\n",(n>0&&buf[n-1]=='\n')?"":"\n",SEC,key,value); }
    if(o==n && memcmp(out,buf,n)==0){ char m[256]; snprintf(m,sizeof m,"%s: no change (%s)",key,have?"set":"absent"); ini_status(m); return; }
    char tmp[700]; snprintf(tmp,sizeof tmp,"%s.tribetmp",INI_PATH);
    int fd=open(tmp,O_WRONLY|O_CREAT|O_TRUNC,0644); if(fd<0){ ini_status("tmp open fail"); return; }
    ssize_t w=write(fd,out,o); fsync(fd); close(fd);
    if(w!=(ssize_t)o){ ini_status("short write"); unlink(tmp); return; }
    if(rename(tmp,INI_PATH)!=0){ ini_status("rename fail"); unlink(tmp); return; }
    char m[300]; snprintf(m,sizeof m,"%s: %s (%d->%d bytes)",key,have?"SET":"DELETED",n,o); ini_status(m);
}
static void ini_upsert(){
    char url[1024], etag[256]; bool hu=read_trim_file("avatar_url.txt",url,sizeof url);
    bool he=read_trim_file("avatar_etag.txt",etag,sizeof etag);
    if(hu && (url[0]=='+'||url[0]=='-'||url[0]=='.'||url[0]=='!')){ ini_status("WARN url op-char; unset"); hu=false; }
    if(hu) stage_cache(url);            // cache slot => cache HIT (local glTF load, no network)
    // UE ini truncates an UNQUOTED value at "//" -> quote the URL (matches Tribe's own DataRouterUrl="...")
    char qurl[1100]; snprintf(qurl,sizeof qurl,"\"%s\"",url);
    upsert_ini_key("ReadyPlayerMeAvatarUrl", hu?qurl:0);
    upsert_ini_key("ReadyPlayerMeETag",      he?etag:0);   // ETag present => FUN_050f584c takes the cache-hit branch
    char m[1400]; snprintf(m,sizeof m,"summary: url=%s etag=%s",hu?qurl:"(none)",he?etag:"(none)"); ini_status(m);
}

// ================= Phase 1: in-libhook loopback HTTP server =================
// Binds 127.0.0.1:HTTP_PORT (NOT the adb-reverse dev port 8000, which adbd holds while tethered).
// Serves tribemod/custom.glb for any *.glb path (model/gltf-binary + ETag) and a JSON metadata blob
// for any *.json path. Strips query strings; sends Content-Length/Type/ETag; supports HEAD and
// If-None-Match -> 304. Read-only w.r.t. the game; started from the constructor so it's up before load.
static const int HTTP_PORT = 8787;
static void httpd_log(const char* fmt,...){ char m[512]; va_list ap; va_start(ap,fmt); vsnprintf(m,sizeof m,fmt,ap); va_end(ap);
    LOGI("[HTTPD] %s",m); char p[600]; snprintf(p,sizeof p,"%s/httpd.log",OUTDIR); FILE* f=fopen(p,"a"); if(f){ fprintf(f,"%s\n",m); fclose(f); } }

// ---- compact MD5 (public-domain style) for the ETag (uppercase hex), matching the python server ----
struct MD5C{ uint32_t a,b,c,d; uint64_t len; uint8_t buf[64]; uint32_t n; };
static uint32_t md5_lr(uint32_t x,int c){ return (x<<c)|(x>>(32-c)); }
static void md5_block(MD5C* m,const uint8_t* p){
    static const uint32_t K[64]={
      0xd76aa478,0xe8c7b756,0x242070db,0xc1bdceee,0xf57c0faf,0x4787c62a,0xa8304613,0xfd469501,
      0x698098d8,0x8b44f7af,0xffff5bb1,0x895cd7be,0x6b901122,0xfd987193,0xa679438e,0x49b40821,
      0xf61e2562,0xc040b340,0x265e5a51,0xe9b6c7aa,0xd62f105d,0x02441453,0xd8a1e681,0xe7d3fbc8,
      0x21e1cde6,0xc33707d6,0xf4d50d87,0x455a14ed,0xa9e3e905,0xfcefa3f8,0x676f02d9,0x8d2a4c8a,
      0xfffa3942,0x8771f681,0x6d9d6122,0xfde5380c,0xa4beea44,0x4bdecfa9,0xf6bb4b60,0xbebfbc70,
      0x289b7ec6,0xeaa127fa,0xd4ef3085,0x04881d05,0xd9d4d039,0xe6db99e5,0x1fa27cf8,0xc4ac5665,
      0xf4292244,0x432aff97,0xab9423a7,0xfc93a039,0x655b59c3,0x8f0ccc92,0xffeff47d,0x85845dd1,
      0x6fa87e4f,0xfe2ce6e0,0xa3014314,0x4e0811a1,0xf7537e82,0xbd3af235,0x2ad7d2bb,0xeb86d391};
    static const int S[64]={7,12,17,22,7,12,17,22,7,12,17,22,7,12,17,22,
      5,9,14,20,5,9,14,20,5,9,14,20,5,9,14,20, 4,11,16,23,4,11,16,23,4,11,16,23,4,11,16,23,
      6,10,15,21,6,10,15,21,6,10,15,21,6,10,15,21};
    uint32_t M[16]; for(int i=0;i<16;i++) M[i]=(uint32_t)p[i*4]|((uint32_t)p[i*4+1]<<8)|((uint32_t)p[i*4+2]<<16)|((uint32_t)p[i*4+3]<<24);
    uint32_t A=m->a,B=m->b,C=m->c,D=m->d;
    for(int i=0;i<64;i++){ uint32_t F; int g;
        if(i<16){ F=(B&C)|(~B&D); g=i; } else if(i<32){ F=(D&B)|(~D&C); g=(5*i+1)&15; }
        else if(i<48){ F=B^C^D; g=(3*i+5)&15; } else { F=C^(B|~D); g=(7*i)&15; }
        F=F+A+K[i]+M[g]; A=D; D=C; C=B; B=B+md5_lr(F,S[i]); }
    m->a+=A; m->b+=B; m->c+=C; m->d+=D;
}
static void md5_init(MD5C* m){ m->a=0x67452301;m->b=0xefcdab89;m->c=0x98badcfe;m->d=0x10325476;m->len=0;m->n=0; }
static void md5_update(MD5C* m,const uint8_t* p,size_t n){ m->len+=n;
    while(n){ uint32_t take=64-m->n; if(take>n)take=(uint32_t)n; memcpy(m->buf+m->n,p,take); m->n+=take; p+=take; n-=take;
        if(m->n==64){ md5_block(m,m->buf); m->n=0; } } }
static void md5_hex_upper(MD5C* m,char out[33]){ uint64_t bits=m->len*8; uint8_t pad=0x80; md5_update(m,&pad,1);
    uint8_t z=0; while(m->n!=56) md5_update(m,&z,1); uint8_t L[8]; for(int i=0;i<8;i++) L[i]=(uint8_t)(bits>>(8*i)); md5_update(m,L,8);
    uint8_t dig[16]; uint32_t v[4]={m->a,m->b,m->c,m->d}; for(int i=0;i<4;i++) for(int j=0;j<4;j++) dig[i*4+j]=(uint8_t)(v[i]>>(8*j));
    static const char* H="0123456789ABCDEF"; for(int i=0;i<16;i++){ out[i*2]=H[dig[i]>>4]; out[i*2+1]=H[dig[i]&15]; } out[32]=0; }

static uint8_t* g_glb=0; static long g_glb_len=0; static char g_etag[40]="";
static char g_meta[400]; static int g_meta_len=0;
static bool httpd_load_asset(){
    char src[700]; snprintf(src,sizeof src,"%s/custom.glb",OUTDIR);
    int fd=open(src,O_RDONLY); if(fd<0){ httpd_log("asset open fail %s (errno %d)",src,errno); return false; }
    struct stat st; if(fstat(fd,&st)!=0||st.st_size<=0){ close(fd); httpd_log("asset stat fail"); return false; }
    g_glb=(uint8_t*)malloc(st.st_size); if(!g_glb){ close(fd); httpd_log("asset malloc fail"); return false; }
    long tot=0; ssize_t r; while(tot<st.st_size && (r=read(fd,g_glb+tot,st.st_size-tot))>0) tot+=r; close(fd);
    if(tot!=st.st_size){ httpd_log("asset short read %ld/%ld",tot,(long)st.st_size); free(g_glb); g_glb=0; return false; }
    g_glb_len=tot; MD5C m; md5_init(&m); md5_update(&m,g_glb,g_glb_len); md5_hex_upper(&m,g_etag);
    g_meta_len=snprintf(g_meta,sizeof g_meta,
        "{\"id\":\"custom\",\"bodyType\":\"halfbody\",\"outfitGender\":\"masculine\","
        "\"skinTone\":\"#cf9c7b\",\"updatedAt\":\"2026-09-30T00:00:00.000Z\","
        "\"createdAt\":\"2026-09-30T00:00:00.000Z\"}");
    httpd_log("asset loaded %ld bytes ETag=%s",g_glb_len,g_etag); return true;
}
static void httpd_send(int fd,const char* status,const char* ctype,const uint8_t* body,long blen,bool headOnly){
    char hdr[512]; int hl=snprintf(hdr,sizeof hdr,
        "HTTP/1.1 %s\r\nContent-Type: %s\r\nContent-Length: %ld\r\nETag: \"%s\"\r\n"
        "Access-Control-Allow-Origin: *\r\nCache-Control: no-cache\r\nConnection: close\r\n\r\n",
        status,ctype,blen,g_etag);
    send(fd,hdr,hl,MSG_NOSIGNAL);
    if(!headOnly && body && blen>0){ long off=0; while(off<blen){ ssize_t w=send(fd,body+off,blen-off,MSG_NOSIGNAL); if(w<=0) break; off+=w; } }
}
static void httpd_send304(int fd){ char hdr[256]; int hl=snprintf(hdr,sizeof hdr,
        "HTTP/1.1 304 Not Modified\r\nETag: \"%s\"\r\nConnection: close\r\n\r\n",g_etag); send(fd,hdr,hl,MSG_NOSIGNAL); }
static void httpd_handle(int fd){
    char req[8192]; int n=0; // read until end of headers (\r\n\r\n) or buffer full
    while(n<(int)sizeof(req)-1){ ssize_t r=recv(fd,req+n,sizeof(req)-1-n,0); if(r<=0) break; n+=r;
        req[n]=0; if(strstr(req,"\r\n\r\n")) break; }
    if(n<=0){ return; } req[n]=0;
    bool head = strncmp(req,"HEAD ",5)==0; bool get = strncmp(req,"GET ",4)==0;
    if(!head && !get){ httpd_send(fd,"405 Method Not Allowed","text/plain",(const uint8_t*)"",0,true); return; }
    // parse path
    const char* sp=strchr(req,' '); const char* path=sp?sp+1:"/"; const char* pe=strchr(path,' ');
    char pbuf[1024]; int pl=pe?(int)(pe-path):0; if(pl<=0||pl>=(int)sizeof pbuf) pl=1; memcpy(pbuf,path,pl); pbuf[pl]=0;
    char* q=strchr(pbuf,'?'); if(q)*q=0;                       // strip query string
    // If-None-Match
    char inm[64]=""; const char* h=strstr(req,"If-None-Match:"); if(!h) h=strstr(req,"if-none-match:");
    if(h){ h+=14; while(*h==' '||*h=='"') h++; int i=0; while(*h&&*h!='\r'&&*h!='"'&&i<63) inm[i++]=*h++; inm[i]=0; }
    bool isjson = (pl>=5 && strcmp(pbuf+pl-5,".json")==0);
    bool match = inm[0] && g_etag[0] && strcmp(inm,g_etag)==0;
    httpd_log("%s %s  If-None-Match=%s%s",head?"HEAD":"GET",pbuf,inm[0]?inm:"(none)",match?"  ->304":"");
    if(match){ httpd_send304(fd); return; }
    if(isjson) httpd_send(fd,"200 OK","application/json",(const uint8_t*)g_meta,g_meta_len,head);
    else       httpd_send(fd,"200 OK","model/gltf-binary",g_glb,g_glb_len,head);
}
static void* httpd_thread(void*){
    if(!httpd_load_asset()){ httpd_log("server NOT started (no asset)"); return nullptr; }
    int s=socket(AF_INET,SOCK_STREAM,0); if(s<0){ httpd_log("socket fail errno %d",errno); return nullptr; }
    int one=1; setsockopt(s,SOL_SOCKET,SO_REUSEADDR,&one,sizeof one);
    sockaddr_in a; memset(&a,0,sizeof a); a.sin_family=AF_INET; a.sin_port=htons(HTTP_PORT);
    a.sin_addr.s_addr=htonl(INADDR_LOOPBACK);                  // 127.0.0.1 only
    if(bind(s,(sockaddr*)&a,sizeof a)!=0){ httpd_log("bind 127.0.0.1:%d fail errno %d",HTTP_PORT,errno); close(s); return nullptr; }
    if(listen(s,8)!=0){ httpd_log("listen fail errno %d",errno); close(s); return nullptr; }
    httpd_log("listening on 127.0.0.1:%d (glb=%ld ETag=%s)",HTTP_PORT,g_glb_len,g_etag);
    for(;;){ int c=accept(s,nullptr,nullptr); if(c<0){ if(errno==EINTR) continue; httpd_log("accept fail errno %d",errno); break; }
        httpd_handle(c); close(c); }
    close(s); return nullptr;
}

static void* dump_thread(void*){
    LOGI("dumper thread up; base=0x%lx; poll %s/dump_now",(unsigned long)g_base,OUTDIR);
    char cmd[600]; snprintf(cmd,sizeof cmd,"%s/dump_now",OUTDIR);
    for(;;){ int fd=open(cmd,O_RDONLY); if(fd>=0){ close(fd); unlink(cmd); LOGI("dump_now seen; dumping...");
        install_guard(); do_dump(); remove_guard(); }
        usleep(500*1000); }
    return nullptr;
}

__attribute__((constructor))
static void on_load(){
    LOGI("dumper libhook constructor");
    // ensure outdir exists (app-writable external files dir), then upsert the ini BEFORE PreInit.
    mkdir(OUTDIR,0777);
    ini_upsert();                       // the one state change; synchronous; no base needed
    for(int i=0;i<100 && !g_base;i++){ g_base=find_lib_base("libUnreal.so"); if(!g_base) usleep(50*1000); }
    if(!g_base){ LOGI("FAILED to find libUnreal.so base"); return; }
    pthread_attr_t a; pthread_attr_init(&a); pthread_attr_setstacksize(&a,8*1024*1024); pthread_attr_setdetachstate(&a,PTHREAD_CREATE_DETACHED);
    pthread_t th; pthread_create(&th,&a,dump_thread,nullptr); pthread_attr_destroy(&a);
    LOGI("dumper thread spawned (base=0x%lx)",(unsigned long)g_base);
    // Phase 1: in-libhook loopback HTTP server (127.0.0.1:8787), detached.
    pthread_attr_t sa; pthread_attr_init(&sa); pthread_attr_setstacksize(&sa,256*1024); pthread_attr_setdetachstate(&sa,PTHREAD_CREATE_DETACHED);
    pthread_t sh; pthread_create(&sh,&sa,httpd_thread,nullptr); pthread_attr_destroy(&sa);
    LOGI("httpd thread spawned (127.0.0.1:%d)",HTTP_PORT);
}
