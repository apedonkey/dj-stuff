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
#include <time.h>
#include <math.h>
#include <cstdarg>
#include <dlfcn.h>
#include "vendor/And64InlineHook.hpp"
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
static uintptr_t g_objarray=0; static uint32_t g_numElements=0, g_numChunks=0; static uintptr_t g_chunks=0; static uintptr_t g_ne_addr=0;
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
        g_chunks=Q; g_numElements=ne; g_numChunks=ncReal; g_ne_off=d; g_objarray=A-0x10; g_ne_addr=A+d; return true; }
    return false;
}
// re-read the LIVE object count (it grows as the world/pawn spawn; find_* bound by g_numElements must track it)
static void refresh_numelements(){ if(!g_ne_addr) return; uint32_t cur=rd32(g_ne_addr);
    if(cur>=1000 && cur<=5000000){ g_numElements=cur; g_numChunks=(cur+65535)/65536; } }
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
// upsert (value!=0) or delete (value==0) SEC <key> in the ini at PATH; atomic tmp+fsync+rename.
// create: a missing file counts as empty (Engine.ini doesn't exist until something writes it).
static void upsert_ini(const char* PATH, const char* SEC, const char* key, const char* value, bool create){
    int kl=(int)strlen(key), sl=(int)strlen(SEC); bool have=(value!=0);
    static char buf[65536]; int n=0;
    { int fd=open(PATH,O_RDONLY);
      if(fd<0){ if(!(create && errno==ENOENT)){ ini_status("ini not readable; skip"); return; } buf[0]=0; }
      else { ssize_t r=read(fd,buf,sizeof buf-1); close(fd); if(r<0){ ini_status("ini read error"); return; } n=(int)r; buf[n]=0; } }
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
    char tmp[700]; snprintf(tmp,sizeof tmp,"%s.tribetmp",PATH);
    int fd=open(tmp,O_WRONLY|O_CREAT|O_TRUNC,0644); if(fd<0){ ini_status("tmp open fail"); return; }
    ssize_t w=write(fd,out,o); fsync(fd); close(fd);
    if(w!=(ssize_t)o){ ini_status("short write"); unlink(tmp); return; }
    if(rename(tmp,PATH)!=0){ ini_status("rename fail"); unlink(tmp); return; }
    char m[300]; snprintf(m,sizeof m,"%s: %s (%d->%d bytes)",key,have?"SET":"DELETED",n,o); ini_status(m);
}
static void upsert_ini_key(const char* key, const char* value){ upsert_ini(INI_PATH,"[TribeAvatar]",key,value,false); }
// Route A (body tracking): the project setting Tribe never ticked. Only an ini layer can reach settings read during
// engine/XR init, which is before any code of ours can touch the CDO. Flag tribemod/body_tracking absent -> key deleted.
static const char* ENGINE_INI_PATH =
  "/data/data/com.TribeXR.TribeXR/files/UnrealGame/TribeXR/TribeXR/Saved/Config/Android/Engine.ini";
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
    char bp[600]; snprintf(bp,sizeof bp,"%s/body_tracking",OUTDIR); int bf=open(bp,O_RDONLY); if(bf>=0) close(bf);
    upsert_ini(ENGINE_INI_PATH,"[/Script/OculusXRHMD.OculusXRHMDRuntimeSettings]","bBodyTrackingEnabled",bf>=0?"True":0,true);
    // diagnostic (flag tribemod/http_log): raise HTTP/Online log verbosity so Tribe's backend requests + status codes show
    // in logcat (Shipping compiles LogHttp Verbose out of the macro, but the category still honors ini verbosity at runtime
    // for any UE_LOG that survived). Absent -> keys deleted (clean).
    char hp[600]; snprintf(hp,sizeof hp,"%s/http_log",OUTDIR); int hf=open(hp,O_RDONLY); bool hl=(hf>=0); if(hf>=0) close(hf);
    const char* cats[]={"LogHttp","LogOnline","LogOnlineHttp","LogHttpCurl","LogInternetAddr"};
    for(unsigned i=0;i<sizeof cats/sizeof cats[0];i++) upsert_ini(ENGINE_INI_PATH,"[Core.Log]",cats[i],hl?"Verbose":0,true);
    ini_status(hl?"http_log: LogHttp/LogOnline set Verbose":"http_log: off (keys removed)");
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

// ================= Phase 3: direct-glTFRuntime executor (the fix) =================
// Loads tribemod/custom.glb via glTFRuntime's own Blueprint UFunctions (called through UObject::ProcessEvent
// on the GAME THREAD, drained from a ProcessEvent hook) and puts the USkeletalMesh on the live avatar body
// SkeletalMeshComponent -- bypassing Tribe's dead readyplayer.me metadata path. v1: MaterialsConfig.bSkipLoad
// => a gray mesh proves geometry/skeleton/placement/visibility. Gated on tribemod/load_avatar.
// ProcessEvent runtime = base + 0x1857dd4 + 0x1000 (calibrated skew) = base + 0x1858dd4 (== Default__Object vtable[78]).
static const uintptr_t RVA_PE_GHIDRA = 0x1857dd4; static const uintptr_t PE_SKEW = 0x1000;
typedef void(*pe_t)(void*,void*,void*); static pe_t orig_pe=0; static void* g_pe_addr=0;
static volatile sig_atomic_t g_load_req=0, g_in_load=0; static bool g_resolved=0;
// skin-cycle-on-menu-select: when Tribe re-applies the RPM skin (ApplySkinToPlayer), advance to the next skin.
static uintptr_t g_apply_fn=0; static volatile sig_atomic_t g_loaded_once=0; static long g_last_cycle=0;
// diagnostic (flag tribemod/log_pe): log each UNIQUE ProcessEvent func whose name looks avatar/skin/menu-ish,
// so an in-headset avatar-select reveals which event actually goes through ProcessEvent (the real cycle trigger).
static volatile sig_atomic_t g_log_pe=0;
// keeper: Tribe actively resets ReadyPlayerMeComponent.AvatarBodyMesh back to null (verified: set -> null
// within ~40s, and the orphaned mesh then gets GC'd). So: root our mesh (no GC), block BP-level resets in
// the PE hook, and have the poll thread re-attach if a native reset slips through.
static uintptr_t g_body=0, g_mymesh=0, g_fnSet=0, g_fnOwner=0, g_fnVis=0, g_fnHid=0;
static volatile sig_atomic_t g_keep=0, g_reattach_req=0; static int g_resets_bp=0, g_resets_native=0;
static const uint32_t SMC_MESH_OFF=0x550;                   // SkeletalMeshComponent.SkeletalMeshAsset
// objective render check (advisor): WasRecentlyRendered + world loc/scale vs camera, logged 3s after attach then every 10s
static uintptr_t g_fnRendered=0, g_fnLoc=0, g_fnScale=0, g_fnCamLoc=0, g_fnLeader=0, g_camMgr=0;
static volatile sig_atomic_t g_report_req=0; static int g_report_ticks=0, g_reports=0;
// isolation actor (advisor Q1): our OWN engine ASkeletalMeshActor -- not owned by the pawn (so owner-no-see can't
// apply), no Tribe logic, no AnimBP. Spawned 2 m in front of the HMD on demand (flag tribemod/iso_here).
static uintptr_t g_isoActor=0, g_isoComp=0; static volatile sig_atomic_t g_iso_req=0;
static volatile sig_atomic_t g_skin_changed=0;                  // do_load swapped our actor's mesh -> body tracking re-rigs
// FOLLOW (advisor #1/#2/#5): our actor ticks itself (PrimaryActorTick bits set via reflection before FinishSpawning,
// TG_PostUpdateWork so camera/controllers are already updated); its ReceiveTick is caught in the PE hook and drives the
// body: HMD over the floor, pushed back 10 cm; yaw smoothed with a +-35 deg dead zone, biased toward the hands' midpoint.
static uintptr_t g_fnReceiveTick=0, g_fnGetRot=0, g_fnSetActorLR=0, g_camComp=0, g_vrOrigin=0, g_mcL=0, g_mcR=0;
static int g_fpsz=-1;                                        // sizeof(FProperty) in THIS build (self-calibrated)
static long g_isoTicks=0, g_camTicks=0; static bool g_restOK=false, g_followInit=false, g_turning=false;
static double g_bodyYaw=0, g_faceOff=180.0, g_footZ=0.0;     // rest-pose facing (deg) + toe height (cm) in mesh space
static int g_restTries=0;
static const uint32_t IOF_RootSet=0x40000000;               // EInternalObjectFlags::RootSet (1<<30)
static bool root_object(uintptr_t obj){                     // == UObject::AddToRoot (sets RootSet on its FUObjectItem)
    if(!obj) return false; uint32_t idx=rd32(obj+OFF_Index); if(idx>=g_numElements) return false;
    uintptr_t chunk=rdptr(g_chunks+(uintptr_t)(idx>>16)*8); if(!chunk) return false;
    uint32_t* fl=(uint32_t*)(chunk+(uintptr_t)(idx&0xFFFF)*ITEM_STRIDE+8);
    __atomic_fetch_or(fl,IOF_RootSet,__ATOMIC_SEQ_CST); return true; }

struct FStr { uint16_t* data; int32_t num; int32_t max; };
static uint16_t g_fpath[600];
static void build_fstr(FStr* s,const char* a){ int i=0; for(;a[i]&&i<599;i++) g_fpath[i]=(uint16_t)(uint8_t)a[i]; g_fpath[i]=0; s->data=g_fpath; s->num=i+1; s->max=i+1; }
static void load_status(const char* fmt,...){ char m[512]; va_list ap; va_start(ap,fmt); vsnprintf(m,sizeof m,fmt,ap); va_end(ap);
    LOGI("[LOAD] %s",m); char p[600]; snprintf(p,sizeof p,"%s/load_result.txt",OUTDIR); FILE* f=fopen(p,"a"); if(f){ fprintf(f,"%s\n",m); fclose(f);} }

// resolve name pool + object array + UStruct offsets from params.txt (heavy scan; run off the game thread)
static void ensure_resolved(){
    if(g_resolved) return; load_maps(); read_params();
    if(P_np){ g_namepool=g_base+P_np; g_blocks_off=(P_bo>=0)?(uint32_t)P_bo:0x40; } else scan_namepool();
    if(!(P_ga && try_objarray(g_base+P_ga))){ if(!scan_objarray()){ load_status("resolve: objarray FAIL"); return; } }
    OFF_Super=0x40; OFF_Children=0x48; OFF_ChildProps=0x50; OFF_PropSize=0x58;   // R3-locked for this build
    char t[32]; fname_resolve(0,t,sizeof t);
    load_status("resolved: np=0x%lx ga=0x%lx NumElem=%u None='%s'",(unsigned long)(g_namepool-g_base),(unsigned long)(g_objarray-g_base),g_numElements,t);
    g_resolved=(g_numElements>1000);
    if(g_resolved) g_apply_fn=find_by_path("/Game/Visuals/BP_TribeVisualsManager.BP_TribeVisualsManager_C.ApplySkinToPlayer",0);
}
static void call_uf(uintptr_t obj,uintptr_t fn,void* parms){ if(orig_pe&&obj&&fn) orig_pe((void*)obj,(void*)fn,parms); }
// find a live (non-CDO) object by name + class-name whose full path contains 'inpath'
// live = in a spawned world (path has PersistentLevel), never a CDO/archetype (Default__ / GEN_VARIABLE / _GEN).
static uintptr_t find_live(const char* name,const char* cls,const char* inpath){
    char nm[96],cn[96],fp[400];
    for(uint32_t i=0;i<g_numElements;i++){ uintptr_t o=obj_at(i); if(!o) continue;
        obj_name(o,nm,sizeof nm); if(strcmp(nm,name)) continue;
        class_name(o,cn,sizeof cn); if(strcmp(cn,cls)) continue;
        if(rd32(o+OFF_Flags)&RF_ClassDefaultObject) continue;
        full_path(o,fp,sizeof fp);
        if(strstr(fp,"Default__")||strstr(fp,"GEN_VARIABLE")||strstr(fp,"_GEN")) continue;   // skip CDO/archetype
        if(!strstr(fp,"PersistentLevel")) continue;                                          // require a live world instance
        if(inpath && !strstr(fp,inpath)) continue;
        return o; }
    return 0;
}
static bool is_rpm_skin(uintptr_t skin){ if(!skin||!in_range(skin,0x30)) return false;
    char cn[96]; class_name(skin,cn,sizeof cn); return strcmp(cn,"BP_ReadyPlayerMeAvatarSkin_C")==0; }
// O(1) dedupe: open-addressing set of function pointers; when nearly full, unseen funcs are simply not logged (no spam)
static uintptr_t g_seenH[8192]; static int g_seenN=0;
static bool seen_add(uintptr_t f){ uint32_t h=(uint32_t)((f>>4)*2654435761u)&8191u;
    for(int k=0;k<64;k++){ uint32_t i=(h+k)&8191u; if(g_seenH[i]==f) return false; if(!g_seenH[i]){ if(g_seenN>=7000) return false; g_seenH[i]=f; g_seenN++; return true; } }
    return false; }
static void pe_log_func(uintptr_t func){
    if(!func||!seen_add(func)||!in_range(func,0x30)) return;   // each unique func once, O(1)
    char nm[96]; obj_name(func,nm,sizeof nm);
    if(strstr(nm,"Skin")||strstr(nm,"Avatar")||strstr(nm,"Apply")||strstr(nm,"Select")||strstr(nm,"RPM")||strstr(nm,"Clicked")||strstr(nm,"Button")
       ||strstr(nm,"Live")||strstr(nm,"Stream")||strstr(nm,"Twitch")||strstr(nm,"VideoCall")||strstr(nm,"Channel")||strstr(nm,"Rtmp")){  // + go-live path
        char fp[400]; full_path(func,fp,sizeof fp); char p[600]; snprintf(p,sizeof p,"%s/pe_funcs.txt",OUTDIR);
        struct timespec ts; clock_gettime(CLOCK_MONOTONIC,&ts);
        FILE* f=fopen(p,"a"); if(f){ fprintf(f,"%ld.%03ld %s\n",(long)ts.tv_sec,(long)(ts.tv_nsec/1000000),fp); fclose(f); } }
}
// advance active_skin.txt to the next *.glb in tribemod/skins/ (sorted, wrapping). Writes the new name.
static void advance_skin(){
    char dir[600]; snprintf(dir,sizeof dir,"%s/skins",OUTDIR);
    static char names[32][128]; int n=0; DIR* d=opendir(dir); if(!d){ load_status("skins/ not found"); return; }
    struct dirent* e; while((e=readdir(d)) && n<32){ const char* nm=e->d_name; size_t L=strlen(nm);
        if(L>4 && (strcmp(nm+L-4,".glb")==0||strcmp(nm+L-4,".GLB")==0)){ strncpy(names[n],nm,127); names[n][127]=0; n++; } }
    closedir(d); if(n==0){ load_status("no skins in skins/"); return; }
    for(int i=0;i<n;i++) for(int j=i+1;j<n;j++) if(strcmp(names[i],names[j])>0){ char t[128]; strcpy(t,names[i]); strcpy(names[i],names[j]); strcpy(names[j],t); }
    char cur[128]=""; read_trim_file("active_skin.txt",cur,sizeof cur);
    int idx=0; for(int i=0;i<n;i++) if(strcmp(names[i],cur)==0){ idx=i; break; }
    int nxt=(idx+1)%n; char p[600]; snprintf(p,sizeof p,"%s/active_skin.txt",OUTDIR);
    int fd=open(p,O_WRONLY|O_CREAT|O_TRUNC,0644); if(fd>=0){ write(fd,names[nxt],strlen(names[nxt])); close(fd); }
    load_status("skin cycle: '%s' -> '%s' (%d skins)",cur,names[nxt],n);
}
static void decode_errors(uintptr_t asset,uintptr_t fnErr){
    if(!asset||!fnErr) return; static uint8_t ep[0x10]; memset(ep,0,sizeof ep); call_uf(asset,fnErr,ep);
    uintptr_t data=*(uintptr_t*)ep; int num=*(int32_t*)(ep+8); load_status("GetErrors: Num=%d",num);
    for(int i=0;i<num&&i<20;i++){ char b[256]; read_fstring(data+(uintptr_t)i*16,b,sizeof b); load_status("  err[%d]=%s",i,b); }
}
// build the skeletal mesh from the asset; skipMaterials=1 => gray (default material), 0 => load glb materials.
static uintptr_t load_mesh(uintptr_t asset,uintptr_t fnMesh,int skipMaterials){
    static uint8_t mp[0x758]; memset(mp,0,sizeof mp);
    *(int32_t*)(mp+0x00)=0; *(int32_t*)(mp+0x04)=0;             // MeshIndex,SkinIndex
    *(uintptr_t*)(mp+0x08+0x08)=0;                             // Skeleton=null(auto-build)
    *(int32_t*)(mp+0x08+0x2c)=-1;                             // OverrideSkinIndex=-1
    *(int32_t*)(mp+0x08+0x30+0xc4)=-1;                        // SkeletonConfig.RootNodeIndex=-1
    *(int32_t*)(mp+0x08+0x30+0x1ac)=-1;                       // SkeletonConfig.MaxNodesTreeDepth=-1
    *(double*)(mp+0x08+0x640)=1.0; *(double*)(mp+0x08+0x648)=1.0; *(double*)(mp+0x08+0x650)=1.0; // BoundsScale=(1,1,1)
    *(uint8_t*)(mp+0x08+0x240+0x220)=(uint8_t)skipMaterials;   // MaterialsConfig.bSkipLoad
    *(uint8_t*)(mp+0x08+0x6ca)=1;                             // bIgnoreEmptyMorphTargets=true
    call_uf(asset,fnMesh,mp); return *(uintptr_t*)(mp+0x750);
}
// call a single-bool (or two-bool) UFunction on obj via ProcessEvent
static void call_bool2(uintptr_t obj,uintptr_t fn,uint8_t a,uint8_t b){ if(!obj||!fn) return;
    static uint8_t bp[16]; memset(bp,0,sizeof bp); bp[0]=a; bp[1]=b; call_uf(obj,fn,bp); }
static void unroot_object(uintptr_t obj){                    // == UObject::RemoveFromRoot
    if(!obj) return; uint32_t idx=rd32(obj+OFF_Index); if(idx>=g_numElements) return;
    uintptr_t chunk=rdptr(g_chunks+(uintptr_t)(idx>>16)*8); if(!chunk) return;
    uint32_t* fl=(uint32_t*)(chunk+(uintptr_t)(idx&0xFFFF)*ITEM_STRIDE+8);
    __atomic_fetch_and(fl,~IOF_RootSet,__ATOMIC_SEQ_CST); }
// set our mesh on the body + force owner-visible. Goes through orig_pe directly, so the PE-hook blocker never sees it.
static void attach_mesh(uintptr_t body,uintptr_t mesh){ if(!body||!mesh||!g_fnSet) return;
    // clear any leader-pose first: a follower whose bones don't map by name can collapse verts to the origin
    if(g_fnLeader){ static uint8_t lp[0x20]; memset(lp,0,sizeof lp); call_uf(body,g_fnLeader,lp); }   // SetLeaderPoseComponent(nullptr,false,false)
    static uint8_t sp[0x10]; memset(sp,0,sizeof sp); *(uintptr_t*)(sp+0x00)=mesh; call_uf(body,g_fnSet,sp);
    call_bool2(body,g_fnOwner,0,0); call_bool2(body,g_fnVis,1,1); call_bool2(body,g_fnHid,0,1); }
// call a UFunction with a zeroed frame (optional float first param); ParmsSize@0xB6 + ReturnValueOffset@0xB8 read at
// runtime so no layout is guessed. Returns a pointer to the return value inside a shared buffer: read it immediately.
static uint8_t g_rbuf[512];
static uint8_t* call_ret(uintptr_t obj,uintptr_t fn,int setf0,float f0){
    if(!obj||!fn) return 0; uint16_t psz=rd16(fn+0xB6); if(psz>sizeof g_rbuf) return 0;
    memset(g_rbuf,0,sizeof g_rbuf); if(setf0) *(float*)g_rbuf=f0;
    call_uf(obj,fn,g_rbuf); uint16_t rvo=rd16(fn+0xB8); if(rvo==0xFFFF||rvo>=psz) return 0; return g_rbuf+rvo; }
static uintptr_t find_live_class_sub(const char* sub){ char cn[128],fp[400];
    for(uint32_t i=0;i<g_numElements;i++){ uintptr_t o=obj_at(i); if(!o) continue;
        class_name(o,cn,sizeof cn); if(!strstr(cn,sub)) continue;
        if(rd32(o+OFF_Flags)&RF_ClassDefaultObject) continue;
        full_path(o,fp,sizeof fp); if(strstr(fp,"Default__")||!strstr(fp,"PersistentLevel")) continue;
        return o; } return 0; }
static void report_one(const char* label,uintptr_t comp){
    if(!comp) return; int rendered=-1; double L[3]={0,0,0},S[3]={0,0,0},C[3]={0,0,0};
    uint8_t* r=call_ret(comp,g_fnRendered,1,0.5f); if(r) rendered=(int)*r;
    uint8_t* l=call_ret(comp,g_fnLoc,0,0);   if(l) memcpy(L,l,24);
    uint8_t* s=call_ret(comp,g_fnScale,0,0); if(s) memcpy(S,s,24);
    if(g_camMgr){ uint8_t* c=call_ret(g_camMgr,g_fnCamLoc,0,0); if(c) memcpy(C,c,24); }
    load_status("RENDER #%d %s: WasRecentlyRendered(0.5)=%d | loc=(%.0f,%.0f,%.0f) scale=(%.3f,%.3f,%.3f) | cam=(%.0f,%.0f,%.0f) d=(%.0f,%.0f,%.0f)cm | mesh ok=%d",
        g_reports,label,rendered,L[0],L[1],L[2],S[0],S[1],S[2],C[0],C[1],C[2],L[0]-C[0],L[1]-C[1],L[2]-C[2],(int)(rdptr(comp+SMC_MESH_OFF)==g_mymesh));
}
static void render_report(){ report_one("slot",g_body); report_one("ISO",g_isoComp); }
// ---- reflection helpers for FOLLOW ----
static uintptr_t g_pawn=0, g_fallbackTicker=0;
static uintptr_t find_field(uintptr_t st,const char* name){ char nm[128];
    for(uintptr_t c=st; c; c=rdptr(c+OFF_Super)) for(uintptr_t f=rdptr(c+OFF_ChildProps); f; f=rdptr(f+FF_Next)){
        fname_resolve(rd32(f+FF_Name),nm,sizeof nm); if(!strcmp(nm,name)) return f; }
    return 0; }
// sizeof(FProperty) == offset of FObjectPropertyBase::PropertyClass. Find it on SkeletalMeshActor.SkeletalMeshComponent,
// whose PropertyClass must be the SkeletalMeshComponent UClass. (FP_ElemSize@0x34 proved wrong, so don't assume 0x70.)
static int calib_fprop_size(){
    if(g_fpsz>0) return g_fpsz;
    uintptr_t cls=find_by_path("/Script/Engine.SkeletalMeshActor",1), smc=find_by_path("/Script/Engine.SkeletalMeshComponent",1);
    uintptr_t f=cls?find_field(cls,"SkeletalMeshComponent"):0; if(!f||!smc) return -1;
    for(int o=0x48;o<=0xB0;o+=8) if(rdptr(f+o)==smc){ g_fpsz=o; break; }
    return g_fpsz; }
static uint8_t rd8(uintptr_t p){ uint8_t v=0; sr(p,&v,1); return v; }
// set a (bitfield) bool member of a struct instance at `base`. FBoolProperty = {FieldSize,ByteOffset,ByteMask,FieldMask}@S.
static bool set_struct_bool(uintptr_t base,uintptr_t st,const char* name,bool on){
    int S=calib_fprop_size(); uintptr_t f=find_field(st,name); if(S<0||!f) return false;
    int off=(int)rd32(f+FP_Offset); uint8_t fs=rd8(f+S), bo=rd8(f+S+1), bm=rd8(f+S+2), fm=rd8(f+S+3);
    // sanity: bitfield bool = FieldSize 1, ByteOffset 0..7, ByteMask==FieldMask single bit, member inside FTickFunction
    if(fs<1||fs>8||bo>7||!bm||(bm&(bm-1))||bm!=fm||off<0||off>0x80){
        load_status("  %s: FBoolProperty looks wrong (S=0x%x off=%d fs=%u bo=%u bm=0x%x fm=0x%x) -> NOT writing",name,S,off,fs,bo,bm,fm); return false; }
    uint8_t* p=(uint8_t*)(base+off+bo); if(on) *p|=bm; else *p&=(uint8_t)~bm;
    load_status("  %s: off=%d byteOff=%d mask=0x%02x -> byte now 0x%02x",name,off,bo,bm,*p); return true; }
// make a deferred (not yet finished) actor tick in the given ETickingGroup (5 = TG_PostUpdateWork)
static bool enable_actor_tick(uintptr_t actor,uintptr_t actorCls,uint8_t group){
    int S=calib_fprop_size(); uintptr_t fPAT=find_field(actorCls,"PrimaryActorTick");
    load_status("tick: sizeof(FProperty)=0x%x PrimaryActorTick field=0x%lx",S,(unsigned long)fPAT);
    if(S<0||!fPAT) return false;
    int pat=(int)rd32(fPAT+FP_Offset); uintptr_t tst=rdptr(fPAT+S);           // FStructProperty::Struct
    char sn[64]; obj_name(tst,sn,sizeof sn); load_status("tick: PrimaryActorTick@0x%x struct=%s",pat,sn);
    uintptr_t base=actor+pat;
    bool a=set_struct_bool(base,tst,"bCanEverTick",true), b=set_struct_bool(base,tst,"bStartWithTickEnabled",true);
    if(!a||!b) return false;                                     // don't touch anything else if the bools didn't resolve
    uintptr_t fg=find_field(tst,"TickGroup"), fe=find_field(tst,"EndTickGroup");
    uint32_t og=fg?rd32(fg+FP_Offset):0xFFFF, oe=fe?rd32(fe+FP_Offset):0xFFFF;
    if(og<0x40) *(uint8_t*)(base+og)=group;
    if(oe<0x40) *(uint8_t*)(base+oe)=group;
    load_status("tick: bCanEverTick=%d bStartWithTickEnabled=%d TickGroup@%d EndTickGroup@%d -> %d",
        (int)a,(int)b,fg?(int)rd32(fg+FP_Offset):-1,fe?(int)rd32(fe+FP_Offset):-1,group);
    return a&&b; }
static bool get_vec3(uintptr_t obj,uintptr_t fn,double out[3]){ uint8_t* r=call_ret(obj,fn,0,0); if(!r) return false; memcpy(out,r,24); return true; }
static double wrap180(double a){ while(a>180) a-=360; while(a<-180) a+=360; return a; }
static void set_actor_lr(uintptr_t actor,const double loc[3],const double rot[3]){      // K2_SetActorLocationAndRotation
    static int oL=-2,oR=-1,oSw=-1,oTp=-1;
    if(oL==-2){ oL=prop_offset(g_fnSetActorLR,"NewLocation",0); oR=prop_offset(g_fnSetActorLR,"NewRotation",0);
        oSw=prop_offset(g_fnSetActorLR,"bSweep",0); oTp=prop_offset(g_fnSetActorLR,"bTeleport",0);
        load_status("setLR: psz=0x%x NewLocation@%d NewRotation@%d bSweep@%d bTeleport@%d",rd16(g_fnSetActorLR+0xB6),oL,oR,oSw,oTp); }
    uint16_t psz=rd16(g_fnSetActorLR+0xB6); static uint8_t b[1024]; if(oL<0||oR<0||psz>sizeof b) return;
    memset(b,0,psz); memcpy(b+oL,loc,24); memcpy(b+oR,rot,24); if(oSw>=0) b[oSw]=0; if(oTp>=0) b[oTp]=1;
    call_uf(actor,g_fnSetActorLR,b); }
// rest pose, read lazily on the first ticks (once the component has bone transforms): model forward = horizontal
// (Toe - Foot) in component space (advisor #5, survives any export orientation); lowest toe z -> feet on the floor.
static bool capture_rest(uintptr_t comp){
    static uintptr_t fnNum=0,fnName=0,fnSock=0; static int oIdx=-1,oNRet=-1,oSName=-1,oSSpace=-1,oSRet=-1;
    if(!fnNum){ fnNum=find_by_path("/Script/Engine.SkinnedMeshComponent.GetNumBones",0);
        fnName=find_by_path("/Script/Engine.SkinnedMeshComponent.GetBoneName",0);
        fnSock=find_by_path("/Script/Engine.SceneComponent.GetSocketTransform",0);
        if(fnName){ oIdx=prop_offset(fnName,"BoneIndex",0); oNRet=prop_offset(fnName,"ReturnValue",0); }
        if(fnSock){ oSName=prop_offset(fnSock,"InSocketName",0); oSSpace=prop_offset(fnSock,"TransformSpace",0); oSRet=prop_offset(fnSock,"ReturnValue",0); } }
    if(!fnNum||!fnName||!fnSock||oIdx<0||oNRet<0||oSName<0||oSRet<0) return false;
    uint8_t* r=call_ret(comp,fnNum,0,0); int n=r?*(int32_t*)r:0; if(n<=0||n>512) return false;
    static uint8_t b[256]; uint64_t nF=0,nT=0,nRF=0,nRT=0;
    for(int i=0;i<n;i++){ uint16_t psz=rd16(fnName+0xB6); if(psz>sizeof b) return false; memset(b,0,sizeof b);
        *(int32_t*)(b+oIdx)=i; call_uf(comp,fnName,b); uint64_t nm; memcpy(&nm,b+oNRet,8); char s[64]; fname_resolve((uint32_t)nm,s,sizeof s);
        if(!strcmp(s,"LeftFoot")) nF=nm; else if(!strcmp(s,"LeftToeBase")) nT=nm; else if(!strcmp(s,"RightFoot")) nRF=nm; else if(!strcmp(s,"RightToeBase")) nRT=nm; }
    if(!nF||!nT){ load_status("rest: %d bones, no LeftFoot/LeftToeBase -> keep faceOff=%.0f footZ=%.0f",n,g_faceOff,g_footZ); return true; }
    double F[3],T[3],RF[3]={0,0,0},RT[3]={0,0,0}; uint64_t nms[4]={nF,nT,nRF,nRT}; double* outs[4]={F,T,RF,RT};
    for(int k=0;k<4;k++){ if(!nms[k]) continue; memset(b,0,sizeof b); memcpy(b+oSName,&nms[k],8); if(oSSpace>=0) b[oSSpace]=2 /*RTS_Component*/;
        call_uf(comp,fnSock,b); memcpy(outs[k],b+oSRet+32,24); }             // FTransform.Translation @+32
    double dx=T[0]-F[0], dy=T[1]-F[1]; if(fabs(dx)+fabs(dy)<0.5) return false;   // bone transforms not computed yet -> retry
    if(nRF&&nRT){ dx+=RT[0]-RF[0]; dy+=RT[1]-RF[1]; }
    g_faceOff=atan2(dy,dx)*180.0/M_PI; g_footZ=T[2]; if(nRT&&RT[2]<g_footZ) g_footZ=RT[2];
    load_status("rest: %d bones; LFoot=(%.1f,%.1f,%.1f) LToe=(%.1f,%.1f,%.1f) -> model forward=%.1f deg, toeZ=%.1f cm",
        n,F[0],F[1],F[2],T[0],T[1],T[2],g_faceOff,g_footZ);
    return true; }
// per-frame body placement (advisor #1): over the HMD, 10 cm behind the eyes, feet on the VROrigin floor, yaw smoothed
// with a +-35 deg dead zone and biased 50% toward the hands' midpoint so the torso keeps facing the decks.
static void follow_update(float dt){
    if(!g_isoActor||!g_camComp) return;
    if(!g_restOK && g_restTries<120){ g_restTries++; g_restOK=capture_rest(g_isoComp); }
    double C[3]={0,0,0},CR[3]={0,0,0},O[3]={0,0,0};
    if(!get_vec3(g_camComp,g_fnLoc,C)||!get_vec3(g_camComp,g_fnGetRot,CR)) return;
    if(g_vrOrigin) get_vec3(g_vrOrigin,g_fnLoc,O);
    double hmdYaw=CR[1], target=hmdYaw;
    if(g_mcL&&g_mcR){ double L[3],R[3]; if(get_vec3(g_mcL,g_fnLoc,L)&&get_vec3(g_mcR,g_fnLoc,R)){
        double mx=(L[0]+R[0])*0.5-C[0], my=(L[1]+R[1])*0.5-C[1], d=sqrt(mx*mx+my*my);
        if(d>15&&d<110){ double handsYaw=atan2(my,mx)*180.0/M_PI; target=wrap180(hmdYaw+0.5*wrap180(handsYaw-hmdYaw)); } } }
    if(!g_followInit){ g_bodyYaw=target; g_followInit=true; }
    double diff=wrap180(target-g_bodyYaw);
    if(fabs(diff)>35) g_turning=true;
    if(g_turning){ double k=dt*5.0; if(k>1)k=1; if(k<0)k=0; g_bodyYaw=wrap180(g_bodyYaw+diff*k); if(fabs(diff)<5) g_turning=false; }
    double hr=hmdYaw*M_PI/180.0;
    double P[3]={C[0]-cos(hr)*10.0, C[1]-sin(hr)*10.0, O[2]-g_footZ};
    double R[3]={0, wrap180(g_bodyYaw-g_faceOff), 0};                  // FRotator: Pitch, Yaw, Roll
    set_actor_lr(g_isoActor,P,R);
    long t=g_isoTicks+g_camTicks;
    if(t==1||(t%180)==0) load_status("follow: isoTicks=%ld fallbackTicks=%ld dt=%.4f hmd=(%.0f,%.0f,%.0f) hmdYaw=%.0f target=%.0f body=%.0f floorZ=%.0f -> actor=(%.0f,%.0f,%.0f) yaw=%.0f",
        g_isoTicks,g_camTicks,dt,C[0],C[1],C[2],hmdYaw,target,g_bodyYaw,O[2],P[0],P[1],P[2],R[1]); }
static bool is_receive_tick(void* func){ if(func==(void*)g_fnReceiveTick) return true;
    char nm[32]; obj_name((uintptr_t)func,nm,sizeof nm); return !strcmp(nm,"ReceiveTick"); }
// spawn our own ASkeletalMeshActor 2 m in front of the HMD, facing it, feet on the floor (skullbuck's origin is at its
// hips, 97 cm up). All param offsets are resolved BY NAME from the UFunction at runtime; FTransform (UE5 LWC, NEON) is
// 96 B = quat@0, translation@32, scale@64 -- checked against the SpawnTransform param's ElementSize before use.
static uintptr_t spawn_iso_actor(uintptr_t mesh){
    uintptr_t gs   =find_by_path("/Script/Engine.Default__GameplayStatics",0);
    uintptr_t fnB  =find_by_path("/Script/Engine.GameplayStatics.BeginDeferredActorSpawnFromClass",0);
    uintptr_t fnF  =find_by_path("/Script/Engine.GameplayStatics.FinishSpawningActor",0);
    uintptr_t cls  =find_by_path("/Script/Engine.SkeletalMeshActor",1);
    uintptr_t fnRot=find_by_path("/Script/Engine.PlayerCameraManager.GetCameraRotation",0);
    load_status("iso: gs=0x%lx begin=0x%lx finish=0x%lx cls=0x%lx cam=0x%lx mesh=0x%lx",
        (unsigned long)gs,(unsigned long)fnB,(unsigned long)fnF,(unsigned long)cls,(unsigned long)g_camMgr,(unsigned long)mesh);
    if(!gs||!fnB||!fnF||!cls||!g_camMgr||!mesh||!g_fnSet) return 0;
    uintptr_t xfProp=0; int oXf=prop_offset(fnB,"SpawnTransform",&xfProp);
    int oWC=prop_offset(fnB,"WorldContextObject",0), oCls=prop_offset(fnB,"ActorClass",0),
        oColl=prop_offset(fnB,"CollisionHandlingOverride",0), oScl=prop_offset(fnB,"TransformScaleMethod",0), oRet=prop_offset(fnB,"ReturnValue",0);
    uint16_t pszB=rd16(fnB+0xB6);
    // ElementSize of the SpawnTransform param (walk ChildProperties to the FField named SpawnTransform)
    uint32_t xfSize=0; { char nm[64]; for(uintptr_t f=rdptr(fnB+OFF_ChildProps); f; f=rdptr(f+FF_Next)){ fname_resolve(rd32(f+FF_Name),nm,sizeof nm); if(!strcmp(nm,"SpawnTransform")){ xfSize=rd32(f+FP_ElemSize); break; } } }
    // FP_ElemSize(0x34) reads 0 for every property in this build, so validate FTransform's size by the GAP to the
    // next param instead (CollisionHandlingOverride directly follows SpawnTransform): must be 96 B.
    int xfGap=(oColl>0)?(oColl-oXf):-1; (void)xfSize;
    load_status("iso: begin psz=0x%x WC@%d Cls@%d Xf@%d(gap %d) Coll@%d Scl@%d Ret@%d",pszB,oWC,oCls,oXf,xfGap,oColl,oScl,oRet);
    if(oWC<0||oCls<0||oXf<0||oRet<0||xfGap!=96||pszB>512){ load_status("iso: unexpected layout -> abort"); return 0; }
    double C[3]={0,0,0},R[3]={0,0,0};
    uint8_t* c=call_ret(g_camMgr,g_fnCamLoc,0,0); if(c) memcpy(C,c,24);
    uint8_t* r=call_ret(g_camMgr,fnRot,0,0);      if(r) memcpy(R,r,24);      // FRotator: Pitch, Yaw, Roll (deg)
    double yaw=R[1]*M_PI/180.0, fx=cos(yaw), fy=sin(yaw), face=yaw+M_PI;
    double P[3]={C[0]+fx*200.0, C[1]+fy*200.0, 97.0};
    uint8_t xf[96]; memset(xf,0,sizeof xf);
    double* q=(double*)xf;        q[0]=0; q[1]=0; q[2]=sin(face/2); q[3]=cos(face/2);
    double* t=(double*)(xf+32);   t[0]=P[0]; t[1]=P[1]; t[2]=P[2];
    double* s=(double*)(xf+64);   s[0]=1; s[1]=1; s[2]=1;
    static uint8_t pb[512]; memset(pb,0,sizeof pb);
    *(uintptr_t*)(pb+oWC)=g_camMgr; *(uintptr_t*)(pb+oCls)=cls; memcpy(pb+oXf,xf,96);
    if(oColl>=0) pb[oColl]=1;                                   // ESpawnActorCollisionHandlingMethod::AlwaysSpawn
    if(oScl>=0)  pb[oScl]=1;                                    // ESpawnActorScaleMethod::MultiplyWithRoot (default)
    call_uf(gs,fnB,pb); uintptr_t actor=*(uintptr_t*)(pb+oRet);
    load_status("iso: BeginDeferredActorSpawnFromClass -> actor=0x%lx  at (%.0f,%.0f,%.0f) camYaw=%.0f",(unsigned long)actor,P[0],P[1],P[2],R[1]);
    if(!actor) return 0;
    // make OUR actor tick at TG_PostUpdateWork (5) -- must be set before FinishSpawningActor registers its tick function
    bool ticking=enable_actor_tick(actor,cls,5);
    load_status("iso: actor tick enabled=%d",(int)ticking);
    int fA=prop_offset(fnF,"Actor",0), fXf=prop_offset(fnF,"SpawnTransform",0), fScl=prop_offset(fnF,"TransformScaleMethod",0);
    uint16_t pszF=rd16(fnF+0xB6); if(fA<0||fXf<0||pszF>512){ load_status("iso: finish layout bad"); return 0; }
    static uint8_t pf[512]; memset(pf,0,sizeof pf); *(uintptr_t*)(pf+fA)=actor; memcpy(pf+fXf,xf,96); if(fScl>=0) pf[fScl]=1;
    call_uf(gs,fnF,pf);
    int oComp=prop_offset(cls,"SkeletalMeshComponent",0); uintptr_t comp=oComp>=0?rdptr(actor+oComp):0;
    load_status("iso: FinishSpawningActor done; SkeletalMeshComponent@0x%x = 0x%lx",oComp,(unsigned long)comp);
    if(!comp) return 0;
    static uint8_t sp[0x10]; memset(sp,0,sizeof sp); *(uintptr_t*)sp=mesh; call_uf(comp,g_fnSet,sp);
    call_bool2(comp,g_fnVis,1,1); call_bool2(comp,g_fnHid,0,1);
    // advisor "now, not later": the body must not block Tribe's hand/deck traces, and shadows cost Quest frame time
    uintptr_t fnColl=find_by_path("/Script/Engine.PrimitiveComponent.SetCollisionEnabled",0);
    uintptr_t fnShad=find_by_path("/Script/Engine.PrimitiveComponent.SetCastShadow",0);
    call_bool2(comp,fnColl,0,0);                                // ECollisionEnabled::NoCollision
    call_bool2(comp,fnShad,0,0);                                // SetCastShadow(false)
    refresh_numelements(); root_object(actor);                  // keep our actor alive
    // FOLLOW wiring: the pawn's tracked components + the functions the per-frame update uses
    g_fnReceiveTick=find_by_path("/Script/Engine.Actor.ReceiveTick",0);
    g_fnGetRot     =find_by_path("/Script/Engine.SceneComponent.K2_GetComponentRotation",0);
    g_fnSetActorLR =find_by_path("/Script/Engine.Actor.K2_SetActorLocationAndRotation",0);
    g_camComp =find_live("Camera","CameraComponent","TribePawnBP_C");
    g_vrOrigin=find_live("VROrigin","SceneComponent","TribePawnBP_C");
    g_mcL     =find_live("MotionControllerL","MotionControllerComponent","TribePawnBP_C");
    g_mcR     =find_live("MotionControllerR","MotionControllerComponent","TribePawnBP_C");
    g_pawn    =find_live_class_sub("TribePawnBP_C");
    g_fallbackTicker = g_pawn? g_pawn : g_camMgr;               // used only if OUR actor never ticks
    g_isoTicks=0; g_camTicks=0; g_restOK=false; g_restTries=0; g_followInit=false; g_turning=false;
    load_status("follow: ReceiveTick=0x%lx getRot=0x%lx setLR=0x%lx cam=0x%lx vrOrigin=0x%lx mcL=0x%lx mcR=0x%lx pawn=0x%lx fallback=0x%lx",
        (unsigned long)g_fnReceiveTick,(unsigned long)g_fnGetRot,(unsigned long)g_fnSetActorLR,(unsigned long)g_camComp,
        (unsigned long)g_vrOrigin,(unsigned long)g_mcL,(unsigned long)g_mcR,(unsigned long)g_pawn,(unsigned long)g_fallbackTicker);
    g_isoActor=actor; g_isoComp=comp;
    load_status("iso: mesh set on our own actor (comp=0x%lx); following the HMD from its next tick",(unsigned long)comp);
    return comp;
}
static void do_load(){
    load_status("=== do_load (game tid=%d) ===",my_tid());
    refresh_numelements();                                       // catch objects spawned since resolve (the pawn)
    uintptr_t fnLoad=find_by_path("/Script/glTFRuntime.glTFRuntimeFunctionLibrary.glTFLoadAssetFromFilename",0);
    uintptr_t fnMesh=find_by_path("/Script/glTFRuntime.glTFRuntimeAsset.LoadSkeletalMesh",0);
    uintptr_t fnErr =find_by_path("/Script/glTFRuntime.glTFRuntimeAsset.GetErrors",0);
    uintptr_t fnSet =find_by_path("/Script/Engine.SkeletalMeshComponent.SetSkeletalMeshAsset",0);
    uintptr_t libCDO=find_by_path("/Script/glTFRuntime.Default__glTFRuntimeFunctionLibrary",0);
    if(!libCDO) libCDO=find_obj("glTFRuntimeFunctionLibrary",1);
    uintptr_t body=find_live("AvatarBodyMesh","SkeletalMeshComponent","ReadyPlayerMeComponent");
    load_status("fnLoad=0x%lx fnMesh=0x%lx fnErr=0x%lx fnSet=0x%lx libCDO=0x%lx body=0x%lx",
        (unsigned long)fnLoad,(unsigned long)fnMesh,(unsigned long)fnErr,(unsigned long)fnSet,(unsigned long)libCDO,(unsigned long)body);
    if(!fnLoad||!fnMesh||!fnSet||!libCDO){ load_status("missing UFunction/CDO; abort"); return; }
    // skin selection: active_skin.txt names a file in tribemod/skins/ ; else glb_path.txt (full path); else custom.glb
    char path[512]; char skin[256];
    if(read_trim_file("active_skin.txt",skin,sizeof skin)) snprintf(path,sizeof path,"%s/skins/%s",OUTDIR,skin);
    else if(!read_trim_file("glb_path.txt",path,sizeof path)) snprintf(path,sizeof path,"%s/custom.glb",OUTDIR);
    // 1) glTFLoadAssetFromFilename(path,false,LoaderConfig)
    static uint8_t lp[0x218]; memset(lp,0,sizeof lp);
    FStr fs; build_fstr(&fs,path); *(FStr*)(lp+0x00)=fs;          // Filename@0x00
    *(uint8_t*)(lp+0x10)=0;                                       // bPathRelativeToContent=false
    *(float*)(lp+0x20+0x150)=100.0f;                             // LoaderConfig.SceneScale=100 (glTFRuntime default: glTF m -> UE cm; 1.0 made it 100x too small)
    *(uint8_t*)(lp+0x20+0x168)=1;                                // LoaderConfig.bAllowExternalFiles=true
    *(uint8_t*)(lp+0x20+0x00)=0;                                 // LoaderConfig.TransformBaseType=Default(0)
    call_uf(libCDO,fnLoad,lp); uintptr_t asset=*(uintptr_t*)(lp+0x210);
    load_status("asset=0x%lx (path=%s)",(unsigned long)asset,path);
    if(!asset){ load_status("asset NULL -> glb parse/file-access failed (check bAllowExternalFiles/path)"); return; }
    // 2) asset.LoadSkeletalMesh(0,0) [by index -> ignores AvatarRoot/Armature]. Try materials ON;
    //    if it fails (uncooked M_glTFRuntimeBase aborts the primitive) fall back to gray so SOMETHING shows.
    uintptr_t mesh=load_mesh(asset,fnMesh,0);            // materials ON
    load_status("mesh(materials)=0x%lx",(unsigned long)mesh);
    if(!mesh){ load_status("materials-on failed -> errors:"); decode_errors(asset,fnErr);
        mesh=load_mesh(asset,fnMesh,1); load_status("mesh(gray fallback)=0x%lx",(unsigned long)mesh); }
    if(!mesh){ load_status("mesh NULL even gray:"); decode_errors(asset,fnErr); return; }
    // did the glTFRuntime base material load? (advisor's cooked-materials check)
    { uintptr_t mb=find_struct("M_glTFRuntimeBase"); load_status("M_glTFRuntimeBase resident=%s",mb?"YES":"no(maybe uncooked)"); }
    // 3) pin the mesh; our own avatar actor (+ its body-tracked meshes) takes it; Tribe's slot too if it exists (legacy)
    g_fnSet=fnSet;
    g_fnOwner=find_by_path("/Script/Engine.PrimitiveComponent.SetOwnerNoSee",0);
    g_fnVis  =find_by_path("/Script/Engine.SceneComponent.SetVisibility",0);
    g_fnHid  =find_by_path("/Script/Engine.SceneComponent.SetHiddenInGame",0);
    g_fnLeader  =find_by_path("/Script/Engine.SkinnedMeshComponent.SetLeaderPoseComponent",0);
    g_fnRendered=find_by_path("/Script/Engine.PrimitiveComponent.WasRecentlyRendered",0);
    g_fnLoc     =find_by_path("/Script/Engine.SceneComponent.K2_GetComponentLocation",0);
    g_fnScale   =find_by_path("/Script/Engine.SceneComponent.K2_GetComponentScale",0);
    g_fnCamLoc  =find_by_path("/Script/Engine.PlayerCameraManager.GetCameraLocation",0);
    refresh_numelements();                                       // the new mesh's index is past the cached count (was rooted=0)
    g_camMgr    =find_live_class_sub("CameraManager");
    bool rooted=root_object(mesh);                               // AddToRoot: survives Tribe dropping its ref
    uintptr_t prev=g_mymesh; g_keep=0;                           // pause keeper/blocker during the swap
    g_mymesh=mesh;
    if(g_isoComp){                                               // skin switch: our actor shows the new mesh; tracked meshes re-rig
        static uint8_t sp2[0x10]; memset(sp2,0,sizeof sp2); *(uintptr_t*)sp2=mesh; call_uf(g_isoComp,fnSet,sp2);
        g_restOK=false; g_restTries=0; g_skin_changed=1;
        load_status("skin: our avatar actor now shows the new mesh; body-tracking re-rig queued"); }
    if(body){ attach_mesh(body,mesh); g_body=body; g_keep=1; }
    else load_status("(no live Tribe AvatarBodyMesh slot -- not needed: our own actor shows the avatar)");
    if(prev && prev!=mesh) unroot_object(prev);                  // release the previous skin's mesh
    load_status("attached mesh=0x%lx body=0x%lx rooted=%d leader=0x%lx camMgr=0x%lx; keeper ON; render report in 3s",
        (unsigned long)mesh,(unsigned long)body,(int)rooted,(unsigned long)g_fnLeader,(unsigned long)g_camMgr);
    g_reports=0; g_report_ticks=6;                               // first RENDER report ~3s after attach (poll ticks are 0.5s)
    g_loaded_once=1;                                             // enable the menu-select skin-cycle trigger
    load_status("=== do_load done (materials on, visible, kept) ===");
}
static void run_guarded(void (*fn)(),const char* what){
    g_dump_tid=my_tid(); struct sigaction sa,os,ob; memset(&sa,0,sizeof sa); sa.sa_sigaction=segv_handler; sa.sa_flags=SA_SIGINFO;
    sigaction(SIGSEGV,&sa,&os); sigaction(SIGBUS,&sa,&ob); g_old_segv=os; g_old_bus=ob;
    if(!sigsetjmp(g_jmp,1)){ g_guard=1; fn(); } else load_status("SIGSEGV/BUS during %s; recovered",what);
    g_guard=0; sigaction(SIGSEGV,&os,0); sigaction(SIGBUS,&ob,0);
}
static void run_load_guarded(){ run_guarded(do_load,"load"); }

// ================= Route A: Meta body tracking (Movement SDK over OVRPlugin), flag tribemod/body_tracking =================
// Resolution (heavy find_by_path scans) runs on the poll thread; the UFunction calls run on the game thread (PE drain).
// Verify chain (advisor): IsBodyTrackingSupported -> StartBodyTrackingByJointSet(FullBody) + RequestBodyTrackingFidelity(High)
// -> IsBodyTrackingEnabled -> TryGetBodyState IsActive. Ghidra FUN_04b7f43c (TryGetBodyState's impl) writes Joints.Data[0..69]
// (upper body) or [0..83] (full body) at stride 0x40 WITHOUT resizing or bounds-checking, and under ProcessEvent the
// out-struct IS our parm buffer -- so Joints must already point at 84 valid slots. It points at our own static storage:
// ProcessEvent never frees or copies back an out-param, and the impl never reallocates the array.
static volatile sig_atomic_t g_bt_req=0, g_bt_poll_req=0, g_bt_started=0;
static uintptr_t g_btLib=0, g_fnBtSupported=0, g_fnBtEnabled=0, g_fnBtStartSet=0, g_fnBtStart=0, g_fnBtFid=0, g_fnBtState=0;
static uintptr_t g_permLib=0, g_fnPermCheck=0, g_hmdCfg=0, g_hmdCfgCls=0;
static int64_t g_btFullBody=1, g_btHigh=2;
static const int BT_NJ=84, BT_JSZ=0x40;                    // EOculusXRBoneID::COUNT (default ctor's Joints.SetNum) / sizeof(FOculusXRBodyJoint)
static uint8_t g_btParms[0x100] __attribute__((aligned(16)));
static uint8_t g_btJoints[BT_NJ*BT_JSZ] __attribute__((aligned(16)));
static int bt_oState=-1, bt_oW2M=-1, bt_oRet=-1, g_btPolls=0; static bool g_btLayoutOK=false, g_btDumped=false;
static char g_boneNames[BT_NJ][40];
// UEnum::Names = TArray<TPair<FName,int64>> @0x40 (UE5.4: UField 0x30 + FString CppType), 16 B per entry
static int enum_entries(uintptr_t e,uintptr_t* data){ *data=0; if(!e) return 0; *data=rdptr(e+0x40); int n=(int)rd32(e+0x48); return (*data&&n>0&&n<=1024)?n:0; }
static bool enum_entry(uintptr_t data,int i,char* nm,int cap,int64_t* v){ char full[128]; fname_resolve(rd32(data+(uintptr_t)i*16),full,sizeof full);
    const char* s=strstr(full,"::"); snprintf(nm,cap,"%s",s?s+2:full); *v=0; return sr(data+(uintptr_t)i*16+8,v,8); }
static int64_t enum_value(const char* path,const char* want,int64_t fallback){
    uintptr_t d; int n=enum_entries(find_by_path(path,0),&d); char nm[96]; int64_t v;
    for(int i=0;i<n;i++) if(enum_entry(d,i,nm,sizeof nm,&v) && !strcmp(nm,want)) return v;
    load_status("BT: %s::%s not found (n=%d) -> fallback %lld",path,want,n,(long long)fallback); return fallback; }
static void enum_label(uintptr_t e,int64_t val,char* out,int cap){ uintptr_t d; int n=enum_entries(e,&d); char nm[96]; int64_t v;
    for(int i=0;i<n;i++) if(enum_entry(d,i,nm,sizeof nm,&v) && v==val){ snprintf(out,cap,"%s",nm); return; } snprintf(out,cap,"?"); }
static bool ffield_is(uintptr_t f,const char* type){ if(!f||!in_range(f,0x30)) return false; char ty[64]; ffield_type(f,ty,sizeof ty); return !strcmp(ty,type); }
// log a (CDO) object's scalar properties: bools, bytes/enums (+enum label), ints, floats
static void log_obj_props(uintptr_t obj,uintptr_t cls){
    int S=calib_fprop_size();
    if(!obj||!cls||S<0){ load_status("BT: settings CDO/class missing (obj=0x%lx cls=0x%lx S=%d)",(unsigned long)obj,(unsigned long)cls,S); return; }
    char nm[128],ty[64],lab[96]; int n=0;
    for(uintptr_t f=rdptr(cls+OFF_ChildProps); f && n<160; f=rdptr(f+FF_Next),n++){
        fname_resolve(rd32(f+FF_Name),nm,sizeof nm); ffield_type(f,ty,sizeof ty); uint32_t off=rd32(f+FP_Offset);
        if(!strcmp(ty,"BoolProperty")){ uint8_t bo=rd8(f+S+1), bm=rd8(f+S+2); load_status("  cfg %-44s = %d",nm,(rd8(obj+off+bo)&bm)?1:0); }
        else if(!strcmp(ty,"EnumProperty")||!strcmp(ty,"ByteProperty")){             // FEnumProperty{Underlying,Enum} / FByteProperty{Enum}
            uintptr_t e=rdptr(f+S+(ty[0]=='E'?8:0)); uint8_t v=rd8(obj+off); lab[0]=0; if(e&&in_range(e,0x50)) enum_label(e,v,lab,sizeof lab);
            load_status("  cfg %-44s = %u %s",nm,v,lab); }
        else if(!strcmp(ty,"IntProperty")) load_status("  cfg %-44s = %d",nm,(int)rd32(obj+off));
        else if(!strcmp(ty,"FloatProperty")){ float x=0; sr(obj+off,&x,4); load_status("  cfg %-44s = %.3f",nm,x); } }
}
// static-library UFunction with an optional 1-byte first argument; returns the byte ReturnValue (-1 none, -2 unresolved)
static int call_lib1(uintptr_t cdo,uintptr_t fn,int arg){
    if(!cdo||!fn) return -2; uint16_t psz=rd16(fn+0xB6); static uint8_t b[64]; if(psz>sizeof b) return -3; memset(b,0,sizeof b);
    if(arg>=0) for(uintptr_t f=rdptr(fn+OFF_ChildProps); f; f=rdptr(f+FF_Next)){ char nm[64]; fname_resolve(rd32(f+FF_Name),nm,sizeof nm);
        if(strcmp(nm,"ReturnValue")){ uint32_t o=rd32(f+FP_Offset); if(o<psz) b[o]=(uint8_t)arg; break; } }
    call_uf(cdo,fn,b); uint16_t rvo=rd16(fn+0xB8); return (rvo==0xFFFF||rvo>=psz)?-1:(int)b[rvo]; }
// UAndroidPermissionFunctionLibrary::CheckPermission(const FString&) -- what the app process itself sees
static int check_permission(const char* perm){
    if(!g_permLib||!g_fnPermCheck) return -2; uint16_t psz=rd16(g_fnPermCheck+0xB6); static uint8_t b[64]; if(psz>sizeof b) return -3; memset(b,0,sizeof b);
    int oP=-1; for(uintptr_t f=rdptr(g_fnPermCheck+OFF_ChildProps); f; f=rdptr(f+FF_Next)) if(ffield_is(f,"StrProperty")){ oP=(int)rd32(f+FP_Offset); break; }
    if(oP<0||oP+16>psz) return -4; FStr s; build_fstr(&s,perm); memcpy(b+oP,&s,sizeof s);
    call_uf(g_permLib,g_fnPermCheck,b); uint16_t rvo=rd16(g_fnPermCheck+0xB8); return (rvo==0xFFFF||rvo>=psz)?-1:(int)b[rvo]; }
// poll thread: resolve everything + validate TryGetBodyState's layout against what the native impl hard-codes
static bool bt_resolve(){
    refresh_numelements();
    g_btLib=find_by_path("/Script/OculusXRMovement.Default__OculusXRMovementFunctionLibrary",0);
    uintptr_t* outs[6]={&g_fnBtSupported,&g_fnBtEnabled,&g_fnBtStartSet,&g_fnBtStart,&g_fnBtFid,&g_fnBtState};
    const char* names[6]={"IsBodyTrackingSupported","IsBodyTrackingEnabled","StartBodyTrackingByJointSet","StartBodyTracking","RequestBodyTrackingFidelity","TryGetBodyState"};
    char p[200]; for(int i=0;i<6;i++){ snprintf(p,sizeof p,"/Script/OculusXRMovement.OculusXRMovementFunctionLibrary.%s",names[i]); *outs[i]=find_by_path(p,0); }
    g_permLib   =find_by_path("/Script/AndroidPermission.Default__AndroidPermissionFunctionLibrary",0);
    g_fnPermCheck=find_by_path("/Script/AndroidPermission.AndroidPermissionFunctionLibrary.CheckPermission",0);
    g_hmdCfgCls =find_by_path("/Script/OculusXRHMD.OculusXRHMDRuntimeSettings",1);
    g_hmdCfg    =find_by_path("/Script/OculusXRHMD.Default__OculusXRHMDRuntimeSettings",0);
    g_btFullBody=enum_value("/Script/OculusXRMovement.EOculusXRBodyJointSet","FullBody",1);
    g_btHigh    =enum_value("/Script/OculusXRMovement.EOculusXRBodyTrackingFidelity","High",2);
    { uintptr_t d; int n=enum_entries(find_by_path("/Script/OculusXRMovement.EOculusXRBoneID",0),&d); char nm[96]; int64_t v;
      for(int i=0;i<n;i++) if(enum_entry(d,i,nm,sizeof nm,&v) && v>=0 && v<BT_NJ) snprintf(g_boneNames[v],sizeof g_boneNames[v],"%s",nm);
      load_status("BT: EOculusXRBoneID entries=%d ([0]=%s [1]=%s [7]=%s [69]=%s [83]=%s)",n,g_boneNames[0],g_boneNames[1],g_boneNames[7],g_boneNames[69],g_boneNames[83]); }
    int S=calib_fprop_size(); uintptr_t st=0;
    if(g_fnBtState && S>0) for(uintptr_t f=rdptr(g_fnBtState+OFF_ChildProps); f; f=rdptr(f+FF_Next)){
        char nm[64],ty[64]; fname_resolve(rd32(f+FF_Name),nm,sizeof nm); ffield_type(f,ty,sizeof ty); int o=(int)rd32(f+FP_Offset);
        if(!strcmp(nm,"ReturnValue")) bt_oRet=o; else if(!strcmp(ty,"FloatProperty")) bt_oW2M=o; else if(!strcmp(ty,"StructProperty")){ bt_oState=o; st=rdptr(f+S); } }
    uint16_t psz=g_fnBtState?rd16(g_fnBtState+0xB6):0; int ssz=st?(int)rd32(st+OFF_PropSize):-1;
    uintptr_t fJ=st?find_field(st,"Joints"):0; int oJ=fJ?(int)rd32(fJ+FP_Offset):-1;
    uintptr_t inner=0; if(fJ){ if(ffield_is(rdptr(fJ+S),"StructProperty")) inner=rdptr(fJ+S); else if(ffield_is(rdptr(fJ+S+8),"StructProperty")) inner=rdptr(fJ+S+8); }
    uintptr_t js=inner?rdptr(inner+S):0; int jsz=js?(int)rd32(js+OFF_PropSize):-1;
    char sn[64]="",jn[64]=""; if(st) obj_name(st,sn,sizeof sn); if(js) obj_name(js,jn,sizeof jn);
    for(int k=0;k<2;k++){ uintptr_t s=k?js:st; if(!s) continue;                   // field map, for the retarget work
        for(uintptr_t f=rdptr(s+OFF_ChildProps); f; f=rdptr(f+FF_Next)){ char nm[64],ty[64]; fname_resolve(rd32(f+FF_Name),nm,sizeof nm); ffield_type(f,ty,sizeof ty);
            load_status("BT:   %s.%s %s @0x%x",k?jn:sn,nm,ty,rd32(f+FP_Offset)); } }
    g_btLayoutOK = g_btLib && g_fnBtState && bt_oState>=0 && bt_oRet>=0 && psz<=sizeof g_btParms && !strcmp(sn,"OculusXRBodyState")
                && oJ==0x10 && !strcmp(jn,"OculusXRBodyJoint") && jsz==BT_JSZ && ssz>0 && bt_oState+ssz<=(int)psz;
    load_status("BT: lib=0x%lx sup=0x%lx en=0x%lx startSet=0x%lx start=0x%lx fid=0x%lx state=0x%lx perm=0x%lx cfg=0x%lx FullBody=%lld High=%lld",
        (unsigned long)g_btLib,(unsigned long)g_fnBtSupported,(unsigned long)g_fnBtEnabled,(unsigned long)g_fnBtStartSet,(unsigned long)g_fnBtStart,
        (unsigned long)g_fnBtFid,(unsigned long)g_fnBtState,(unsigned long)g_fnPermCheck,(unsigned long)g_hmdCfg,(long long)g_btFullBody,(long long)g_btHigh);
    load_status("BT: TryGetBodyState psz=0x%x state@%d (%s, 0x%x B) W2M@%d ret@%d Joints@0x%x of %s (0x%x B) -> layout %s",
        psz,bt_oState,sn,ssz,bt_oW2M,bt_oRet,oJ,jn,jsz,g_btLayoutOK?"OK":"MISMATCH (TryGetBodyState will NOT be called)");
    return g_btLib && g_fnBtStartSet && g_fnBtEnabled;
}
static void bt_dump_joints(const char* why){
    char p[600]; snprintf(p,sizeof p,"%s/bt_joints.txt",OUTDIR); FILE* f=fopen(p,"w"); if(!f) return;
    uint8_t* s=g_btParms+bt_oState;
    fprintf(f,"# %s: IsActive=%d conf=%.3f skelChanged=%d time=%.3f  (tracking space, UE axes, cm; rot = Pitch,Yaw,Roll deg)\n",
        why,s[0],*(float*)(s+4),*(int32_t*)(s+8),*(float*)(s+12));
    for(int i=0;i<BT_NJ;i++){ uint8_t* j=g_btJoints+i*BT_JSZ; double* r=(double*)(j+0x10); double* q=(double*)(j+0x28);
        fprintf(f,"%2d %-34s flags=0x%02llx valid=%d rot=(%7.1f,%7.1f,%7.1f) pos=(%7.1f,%7.1f,%7.1f)\n",
            i,g_boneNames[i],(unsigned long long)*(uint64_t*)j,j[8],r[0],r[1],r[2],q[0],q[1],q[2]); }
    fclose(f); load_status("BT: wrote bt_joints.txt (%s)",why); }
static void bt_poll(){
    g_btPolls++; int en=call_lib1(g_btLib,g_fnBtEnabled,-1);
    if(!g_btLayoutOK){ load_status("BT poll #%d: IsBodyTrackingEnabled=%d (TryGetBodyState skipped: layout unverified)",g_btPolls,en); return; }
    memset(g_btParms,0,sizeof g_btParms); memset(g_btJoints,0,sizeof g_btJoints);
    uint8_t* s=g_btParms+bt_oState;
    *(uintptr_t*)(s+0x10)=(uintptr_t)g_btJoints; *(int32_t*)(s+0x18)=BT_NJ; *(int32_t*)(s+0x1C)=BT_NJ;   // Joints -> our 84 slots
    if(bt_oW2M>=0) *(float*)(g_btParms+bt_oW2M)=100.0f;
    call_uf(g_btLib,g_fnBtState,g_btParms);
    if(*(uintptr_t*)(s+0x10)!=(uintptr_t)g_btJoints||*(int32_t*)(s+0x18)!=BT_NJ)
        load_status("BT: WARNING engine re-pointed Joints (0x%lx num=%d)",(unsigned long)*(uintptr_t*)(s+0x10),*(int32_t*)(s+0x18));
    int nv=0; for(int i=0;i<BT_NJ;i++) if(g_btJoints[i*BT_JSZ+8]) nv++;
    static const char* want[]={"Hips","Head","LeftHandWrist","RightHandWrist","LeftFootAnkle","RightFootAnkle"};
    char key[512]; int k=0; key[0]=0;
    for(int w=0;w<6;w++){ int idx=-1; for(int i=0;i<BT_NJ;i++) if(strstr(g_boneNames[i],want[w])){ idx=i; break; }
        if(idx<0) continue; double* q=(double*)(g_btJoints+idx*BT_JSZ+0x28);
        k+=snprintf(key+k,sizeof key-k," %s=(%.0f,%.0f,%.0f)%s",want[w],q[0],q[1],q[2],g_btJoints[idx*BT_JSZ+8]?"":"!invalid"); }
    load_status("BT poll #%d: IsBodyTrackingEnabled=%d TryGetBodyState=%d IsActive=%d conf=%.2f skelChanged=%d time=%.2f valid=%d/%d |%s",
        g_btPolls,en,g_btParms[bt_oRet],s[0],*(float*)(s+4),*(int32_t*)(s+8),*(float*)(s+12),nv,BT_NJ,key);
    if(!g_btDumped && (s[0] || g_btPolls==4)){ g_btDumped=(s[0]!=0); bt_dump_joints(s[0]?"first ACTIVE poll":"poll #4, not active yet"); }
}
static void bt_start(){
    load_status("=== body tracking start (game tid=%d) ===",my_tid());
    load_status("BT: OculusXRHMDRuntimeSettings CDO (did the Engine.ini override land? which XrApi?):");
    log_obj_props(g_hmdCfg,g_hmdCfgCls);
    int perm=check_permission("com.oculus.permission.BODY_TRACKING");
    int sup=call_lib1(g_btLib,g_fnBtSupported,-1);
    int ss=call_lib1(g_btLib,g_fnBtStartSet,(int)g_btFullBody);
    int s0=-9; if(ss!=1) s0=call_lib1(g_btLib,g_fnBtStart,-1);            // FullBody refused -> try the default joint set
    int fid=call_lib1(g_btLib,g_fnBtFid,(int)g_btHigh);
    int en=call_lib1(g_btLib,g_fnBtEnabled,-1);
    load_status("BT: CheckPermission(BODY_TRACKING)=%d IsBodyTrackingSupported=%d StartBodyTrackingByJointSet(%lld)=%d StartBodyTracking()=%d%s RequestBodyTrackingFidelity(%lld)=%d IsBodyTrackingEnabled=%d",
        perm,sup,(long long)g_btFullBody,ss,s0,s0==-9?"(not tried)":"",(long long)g_btHigh,fid,en);
    g_bt_started=1; bt_poll();
}

// ================= Route A2: retarget Meta body tracking onto the avatar (PoseableMesh; advisor A2 Q1-Q3) =================
// Offsets: O_b = M_j(T)^-1 * R_align * A_b(T); per frame A_b = M_j * O_b. The meshes are attached at identity to the
// Camera's own parent, so tracking-space joints ARE component-space poses; the component's uniform scale s maps avatar cm
// to your cm. A_b(T) = the avatar's T-pose, built by swinging its A-pose arm chain onto horizontal (FindBetween,
// parent-first). R_align = yaw(your facing at capture - avatar facing): the advisor's formula omits it, and without it any
// facing other than the avatar's own forward during the T-pose bakes a constant twist into every bone. Head = the HMD's
// rotation every frame; the neck takes half of the HMD-vs-Meta head disagreement. Wrists are pinned to Meta's wrist joints
// by two-bone IK (Meta elbow = pole). The T-pose is auto-detected (hold ~1 s) and saved next to the .glb -> once per rig.
// Two meshes (skullbuck's material is double-sided, so a camera inside its head would see the skull's inner faces):
// A = full body, bOwnerNoSee (selfie cam / others); B = head hidden, bOnlyOwnerSee (you, looking down). Model hands are
// hidden on both; Tribe's tracked hands stay. Flag tribemod/bt_nosplit = one mesh visible to everyone (debug).
struct V3{ double x,y,z; };
struct Q4{ double x,y,z,w; };                                   // FQuat memory order
static inline V3 V(double x,double y,double z){ V3 r={x,y,z}; return r; }
static inline V3 vadd(V3 a,V3 b){ return V(a.x+b.x,a.y+b.y,a.z+b.z); }
static inline V3 vsub(V3 a,V3 b){ return V(a.x-b.x,a.y-b.y,a.z-b.z); }
static inline V3 vmul(V3 a,double s){ return V(a.x*s,a.y*s,a.z*s); }
static inline double vdot(V3 a,V3 b){ return a.x*b.x+a.y*b.y+a.z*b.z; }
static inline V3 vcross(V3 a,V3 b){ return V(a.y*b.z-a.z*b.y,a.z*b.x-a.x*b.z,a.x*b.y-a.y*b.x); }
static inline double vlen(V3 a){ return sqrt(vdot(a,a)); }
static inline V3 vnorm(V3 a){ double l=vlen(a); return l>1e-9?vmul(a,1.0/l):V(0,0,0); }
static inline Q4 Qm(double x,double y,double z,double w){ Q4 q={x,y,z,w}; return q; }
static const Q4 QI={0,0,0,1};
static inline Q4 qmul(Q4 a,Q4 b){ return Qm(a.w*b.x+a.x*b.w+a.y*b.z-a.z*b.y, a.w*b.y-a.x*b.z+a.y*b.w+a.z*b.x,     // Hamilton: b then a
                                            a.w*b.z+a.x*b.y-a.y*b.x+a.z*b.w, a.w*b.w-a.x*b.x-a.y*b.y-a.z*b.z); }
static inline Q4 qinv(Q4 q){ return Qm(-q.x,-q.y,-q.z,q.w); }
static inline Q4 qnorm(Q4 q){ double l=sqrt(q.x*q.x+q.y*q.y+q.z*q.z+q.w*q.w); return l>1e-12?Qm(q.x/l,q.y/l,q.z/l,q.w/l):QI; }
static inline V3 qrot(Q4 q,V3 v){ V3 u=V(q.x,q.y,q.z), t=vmul(vcross(u,v),2.0); return vadd(vadd(v,vmul(t,q.w)),vcross(u,t)); }  // FQuat::RotateVector
static Q4 qbetween(V3 a,V3 b){ a=vnorm(a); b=vnorm(b); double w=1.0+vdot(a,b);              // FQuat::FindBetweenNormals
    Q4 r= w>=1e-6 ? Qm(a.y*b.z-a.z*b.y,a.z*b.x-a.x*b.z,a.x*b.y-a.y*b.x,w) : (fabs(a.x)>fabs(a.y)?Qm(-a.z,0,a.x,0):Qm(0,-a.z,a.y,0));
    return qnorm(r); }
static Q4 qslerp(Q4 a,Q4 b,double t){ double c=a.x*b.x+a.y*b.y+a.z*b.z+a.w*b.w; if(c<0){ b=Qm(-b.x,-b.y,-b.z,-b.w); c=-c; }
    if(c>0.9995) return qnorm(Qm(a.x+(b.x-a.x)*t,a.y+(b.y-a.y)*t,a.z+(b.z-a.z)*t,a.w+(b.w-a.w)*t));
    double th=acos(c), s=sin(th), k0=sin((1-t)*th)/s, k1=sin(t*th)/s; return Qm(a.x*k0+b.x*k1,a.y*k0+b.y*k1,a.z*k0+b.z*k1,a.w*k0+b.w*k1); }
static Q4 qyaw(double deg){ double h=deg*M_PI/360.0; return Qm(0,0,sin(h),cos(h)); }
static Q4 rot2q(const double* r){                                // FRotator(Pitch,Yaw,Roll)::Quaternion(), UE5
    double k=M_PI/360.0, SP=sin(fmod(r[0],360.0)*k), CP=cos(fmod(r[0],360.0)*k), SY=sin(fmod(r[1],360.0)*k), CY=cos(fmod(r[1],360.0)*k),
           SR=sin(fmod(r[2],360.0)*k), CR=cos(fmod(r[2],360.0)*k);
    return Qm(CR*SP*SY-SR*CP*CY, -CR*SP*CY-SR*CP*SY, CR*CP*SY-SR*SP*CY, CR*CP*CY+SR*SP*SY); }
static double yaw_of_left(V3 l){ return atan2(l.x,-l.y)*180.0/M_PI; }      // facing yaw whose left vector is l (UE: left=(sin y,-cos y))
static double ang_deg(V3 a,V3 b){ double c=vdot(vnorm(a),vnorm(b)); c=c>1?1:(c<-1?-1:c); return acos(c)*180.0/M_PI; }
static double elev_deg(V3 d){ double l=vlen(d); return l>1e-9?asin(d.z/l)*180.0/M_PI:0; }

// the avatar's rest skeleton (local ref pose + FK'd component space), read once from our SkeletalMeshComponent
static const int RB_MAX=160;
static int g_rb_n=0, g_rb_par[RB_MAX]; static uint64_t g_rb_fn[RB_MAX]; static char g_rb_nm[RB_MAX][40];
static Q4 g_rb_lq[RB_MAX], g_rb_cq[RB_MAX]; static V3 g_rb_lt[RB_MAX], g_rb_ct[RB_MAX];
static int rb_find(const char* n){ for(int i=0;i<g_rb_n;i++) if(!strcmp(g_rb_nm[i],n)) return i; return -1; }
static void rb_fk(const Q4* lq,Q4* cq,V3* ct){
    for(int i=0;i<g_rb_n;i++){ int p=g_rb_par[i];
        if(p<0){ cq[i]=lq[i]; ct[i]=g_rb_lt[i]; } else { cq[i]=qnorm(qmul(cq[p],lq[i])); ct[i]=vadd(ct[p],qrot(cq[p],g_rb_lt[i])); } } }
// bone -> Meta joint (EOculusXRBoneID). Meta's clavicle root is BodyLeftShoulder (8); its scapula (9) sits at the arm root.
struct BtMap{ const char* bone; int joint; int bi; Q4 off; Q4 cur; bool haveOff; };
static BtMap g_bm[]={ {"Hips",1},{"Spine",3},{"Spine1",4},{"Spine2",5},{"Neck",6},{"Head",7},
    {"LeftShoulder",8},{"LeftArm",10},{"LeftForeArm",11},{"LeftHand",19},{"RightShoulder",13},{"RightArm",15},{"RightForeArm",16},{"RightHand",45},
    {"LeftUpLeg",70},{"LeftLeg",71},{"LeftFoot",73},{"LeftToeBase",76},{"RightUpLeg",77},{"RightLeg",78},{"RightFoot",80},{"RightToeBase",83} };
static const int BM_N=(int)(sizeof(g_bm)/sizeof(g_bm[0]));
static bool g_rbOK=false, g_rbTried=false, g_calOK=false, g_a2Live=false, g_a2Fail=false, g_a2Init=false, g_smooth=false, g_noSplit=false;
static volatile sig_atomic_t g_a2Recal=0, g_a2CalNow=0;
static double g_btScale=1.0, g_thM=180.0, g_avEyeH=0, g_tposeHold=0; static Q4 g_offHeadCam={0,0,0,1}; static V3 g_hipsCur={0,0,0};
static int iHips=-1,iHead=-1,iNeck=-1,iLA=-1,iLF=-1,iLH=-1,iRA=-1,iRF=-1,iRH=-1; static bool g_ikL=false, g_ikR=false;
static uintptr_t g_pmA=0, g_pmB=0, g_trackParent=0;
static bool g_handShown[2]={false,false};                      // model hand shown (controller) vs Tribe's tracked hand
static uintptr_t g_fnNumBones=0,g_fnBoneName=0,g_fnParentBone=0,g_fnRefPose=0,g_fnHideBone=0,g_fnSetSkinned=0,g_fnAddComp=0,g_fnSetOwner=0,
                 g_fnAttach=0,g_fnRelScale=0,g_fnAttachParent=0,g_fnSetBoneXf=0,g_poseCls=0,g_fnOnlyOwnerSee=0,g_fnTickGroup=0,g_fnColl2=0,g_fnShad2=0,
                 g_fnDestroyComp=0;
static int g_offRelLoc=-1, g_offRelRot=-1; static float g_w2m=100.0f;
static int64_t g_attSnap=2, g_attKeepRel=0, g_boneCS=1;
// YOUR calibration pose (raw Meta joints, tracking space) -- captured once, applies to EVERY skin: each rig's offsets are
// derived from it when that rig loads, so a new skin needs no pose of its own. tribemod/bt_user_calib.txt
static bool g_ucal=false; static Q4 g_ucQ[BT_NJ]; static V3 g_ucP[BT_NJ]; static double g_ucEye=0, g_ucThU=0;
static char g_ucPath[600]="";
static void a2_apply_ucal();
static void a2_prep_hands();

static bool a2_load_ucal(){
    FILE* f=fopen(g_ucPath,"r"); if(!f) return false; char line[320]; int nj=0; double eye=0, th=0; bool haveTh=false;
    while(fgets(line,sizeof line,f)){ int j; double qx,qy,qz,qw,px,py,pz;
        if(sscanf(line,"eye %lf",&eye)==1) continue;
        if(sscanf(line,"facing %lf",&th)==1){ haveTh=true; continue; }
        if(sscanf(line,"joint %d %lf %lf %lf %lf %lf %lf %lf",&j,&qx,&qy,&qz,&qw,&px,&py,&pz)==8 && j>=0 && j<BT_NJ){
            g_ucQ[j]=qnorm(Qm(qx,qy,qz,qw)); g_ucP[j]=V(px,py,pz); nj++; } }
    fclose(f);
    if(nj!=BT_NJ||eye<80||eye>230||!haveTh) return false;
    g_ucEye=eye; g_ucThU=th; return true; }
static void a2_save_ucal(){
    FILE* f=fopen(g_ucPath,"w"); if(!f){ load_status("A2: cannot write %s",g_ucPath); return; }
    fprintf(f,"# tribemod body tracking: YOUR calibration pose (Meta joints, tracking space, UE axes, cm). It applies to every\n"
              "# skin -- each skin's bone offsets are derived from it at load. Delete this file (or touch tribemod/bt_recalibrate)\n"
              "# to redo it. joint = index qx qy qz qw px py pz\nversion 2\neye %.3f\nfacing %.4f\n",g_ucEye,g_ucThU);
    for(int j=0;j<BT_NJ;j++) fprintf(f,"joint %d %.9f %.9f %.9f %.9f %.3f %.3f %.3f\n",j,g_ucQ[j].x,g_ucQ[j].y,g_ucQ[j].z,g_ucQ[j].w,g_ucP[j].x,g_ucP[j].y,g_ucP[j].z);
    fclose(f); }
// avatar T-pose: swing Arm->ForeArm, ForeArm->Hand, Hand->HandMiddle1 onto horizontal-lateral, parent-first (advisor Q1);
// clavicles, spine, legs and head keep the rest pose (skullbuck's clavicles are already level: -2.7 deg).
static void a2_avatar_tpose(Q4* cq,V3* ct){
    static Q4 lq[RB_MAX]; memcpy(lq,g_rb_lq,sizeof(Q4)*g_rb_n); rb_fk(lq,cq,ct);
    V3 left=vnorm(V(g_rb_ct[iLA].x-g_rb_ct[iRA].x,g_rb_ct[iLA].y-g_rb_ct[iRA].y,0));
    const char* ch[2][4]={{"LeftArm","LeftForeArm","LeftHand","LeftHandMiddle1"},{"RightArm","RightForeArm","RightHand","RightHandMiddle1"}};
    for(int sd=0;sd<2;sd++){ V3 tgt=sd?vmul(left,-1):left;
        for(int k=0;k<3;k++){ int b=rb_find(ch[sd][k]), c=rb_find(ch[sd][k+1]); if(b<0||c<0) break;
            Q4 sw=qbetween(vsub(ct[c],ct[b]),tgt); int p=g_rb_par[b]; Q4 pq=p>=0?cq[p]:QI;
            lq[b]=qnorm(qmul(qinv(pq),qmul(sw,cq[b]))); rb_fk(lq,cq,ct); } } }
static bool a2_build_rest(){
    uintptr_t comp=g_isoComp;
    if(!comp||!g_fnNumBones||!g_fnBoneName||!g_fnParentBone||!g_fnRefPose){ load_status("A2: rest skeleton: functions missing"); return false; }
    int oBI=prop_offset(g_fnBoneName,"BoneIndex",0), oBR=prop_offset(g_fnBoneName,"ReturnValue",0);
    int oPN=prop_offset(g_fnParentBone,"BoneName",0), oPR=prop_offset(g_fnParentBone,"ReturnValue",0);
    int oRI=prop_offset(g_fnRefPose,"BoneIndex",0), oRR=prop_offset(g_fnRefPose,"ReturnValue",0);
    uint16_t p1=rd16(g_fnBoneName+0xB6), p2=rd16(g_fnParentBone+0xB6), p3=rd16(g_fnRefPose+0xB6);
    static uint8_t b[512] __attribute__((aligned(16)));
    if(oBI<0||oBR<0||oPN<0||oPR<0||oRI<0||oRR<0||p1>sizeof b||p2>sizeof b||p3>sizeof b||oRR+96>(int)p3){ load_status("A2: rest skeleton: bad layout"); return false; }
    uint8_t* r=call_ret(comp,g_fnNumBones,0,0); int n=r?*(int32_t*)r:0; if(n<=0||n>RB_MAX){ load_status("A2: rest skeleton: %d bones",n); return false; }
    for(int i=0;i<n;i++){ memset(b,0,sizeof b); *(int32_t*)(b+oBI)=i; call_uf(comp,g_fnBoneName,b); memcpy(&g_rb_fn[i],b+oBR,8);
        fname_resolve((uint32_t)g_rb_fn[i],g_rb_nm[i],sizeof g_rb_nm[i]);
        char* pfx=strrchr(g_rb_nm[i],':'); if(pfx) memmove(g_rb_nm[i],pfx+1,strlen(pfx+1)+1);   // "mixamorig:Hips" -> "Hips" (match only)
        memset(b,0,sizeof b); *(int32_t*)(b+oRI)=i; call_uf(comp,g_fnRefPose,b); double* x=(double*)(b+oRR);
        g_rb_lq[i]=qnorm(Qm(x[0],x[1],x[2],x[3])); g_rb_lt[i]=V(x[4],x[5],x[6]); }
    for(int i=0;i<n;i++){ memset(b,0,sizeof b); memcpy(b+oPN,&g_rb_fn[i],8); call_uf(comp,g_fnParentBone,b); uint64_t pn; memcpy(&pn,b+oPR,8);
        g_rb_par[i]=-1; for(int k=0;k<n;k++) if(g_rb_fn[k]==pn){ g_rb_par[i]=k; break; }
        if(g_rb_par[i]>=i){ load_status("A2: bone %d (%s) parent %d not before it",i,g_rb_nm[i],g_rb_par[i]); return false; } }
    g_rb_n=n; rb_fk(g_rb_lq,g_rb_cq,g_rb_ct);
    g_calOK=false; int mapped=0; for(int k=0;k<BM_N;k++){ g_bm[k].bi=rb_find(g_bm[k].bone); g_bm[k].haveOff=false; if(g_bm[k].bi>=0) mapped++; }
    iHips=rb_find("Hips"); iHead=rb_find("Head"); iNeck=rb_find("Neck"); iLA=rb_find("LeftArm"); iLF=rb_find("LeftForeArm"); iLH=rb_find("LeftHand");
    iRA=rb_find("RightArm"); iRF=rb_find("RightForeArm"); iRH=rb_find("RightHand");
    if(iLA<0||iRA<0||iHead<0||g_rb_par[0]>=0){ load_status("A2: rig lacks LeftArm/RightArm/Head (%d bones, %d/%d mapped) -> can't be body-tracked",n,mapped,BM_N); return false; }
    g_ikL=iLF>=0&&iLH>=0&&g_rb_par[iLF]==iLA&&g_rb_par[iLH]==iLF;      // wrist IK needs Arm > ForeArm > Hand directly
    g_ikR=iRF>=0&&iRH>=0&&g_rb_par[iRF]==iRA&&g_rb_par[iRH]==iRF;
    g_thM=yaw_of_left(V(g_rb_ct[iLA].x-g_rb_ct[iRA].x,g_rb_ct[iLA].y-g_rb_ct[iRA].y,0));
    g_offHeadCam=qnorm(qmul(qyaw(-g_thM),g_rb_cq[iHead]));        // head frame with the avatar's facing removed -> follows the HMD
    double sole=1e9; for(int i=0;i<n;i++) if(g_rb_ct[i].z<sole) sole=g_rb_ct[i].z; sole-=2.0;   // lowest joint (toe) minus ~2 cm of sole
    int le=rb_find("LeftEye"), re=rb_find("RightEye"); double eye=(le>=0&&re>=0)?0.5*(g_rb_ct[le].z+g_rb_ct[re].z):g_rb_ct[iHead].z+8.0;
    g_avEyeH=eye-sole;
    static Q4 aq[RB_MAX]; static V3 at[RB_MAX]; a2_avatar_tpose(aq,at);
    load_status("A2: rest skeleton %d bones (root %s), mapped %d/%d; avatar faces %.0f deg; eyes %.1f cm above soles; wrist IK L%d R%d",
        n,g_rb_nm[0],mapped,BM_N,g_thM,g_avEyeH,(int)g_ikL,(int)g_ikR);
    if(iLF>=0&&iLH>=0){ int m1=rb_find("LeftHandMiddle1");
        load_status("A2: rest arm elevation L %.0f/%.0f/%.0f deg -> constructed T-pose %.1f/%.1f/%.1f (want ~0)",
            elev_deg(vsub(g_rb_ct[iLF],g_rb_ct[iLA])),elev_deg(vsub(g_rb_ct[iLH],g_rb_ct[iLF])),m1>=0?elev_deg(vsub(g_rb_ct[m1],g_rb_ct[iLH])):0.0,
            elev_deg(vsub(at[iLF],at[iLA])),elev_deg(vsub(at[iLH],at[iLF])),m1>=0?elev_deg(vsub(at[m1],at[iLH])):0.0); }
    a2_prep_hands();
    if(g_ucal) a2_apply_ucal(); else load_status("A2: no calibration yet -> stand still with straight arms (T or A) once");
    return true; }
// calibration-pose detector on Meta joints (tracking space): standing still with straight arms -- T-pose OR A-pose.
// The pose itself doesn't matter: a2_avatar_calpose poses the avatar to YOUR measured limb directions before the offsets
// are taken, so nothing depends on reproducing the avatar's rest angles (the advisor's worry about A-pose capture).
static bool a2_pose_check(const V3* p,double spd,char* why,int cap){
    double bL=ang_deg(vsub(p[11],p[10]),vsub(p[19],p[11])), bR=ang_deg(vsub(p[16],p[15]),vsub(p[45],p[16]));
    double tL=elev_deg(vsub(p[19],p[10])), tR=elev_deg(vsub(p[45],p[15]));
    double kL=ang_deg(vsub(p[71],p[70]),vsub(p[73],p[71])), kR=ang_deg(vsub(p[78],p[77]),vsub(p[80],p[78]));
    const char* kind=(fabs(tL)<25&&fabs(tR)<25)?"T-pose":((tL<-40&&tR<-40)?"A-pose":"mixed");
    snprintf(why,cap,"%s | elbow bend L%.0f R%.0f (<30) | arm tilt L%.0f R%.0f | knee bend L%.0f R%.0f (<40) | head %.0f cm (>120) | motion %.0f cm/s (<12)",
        kind,bL,bR,tL,tR,kL,kR,p[7].z,spd);
    return bL<30&&bR<30&&kL<40&&kR<40&&p[7].z>120&&spd<12; }
// the avatar in YOUR calibration pose: swing each arm/leg segment (parent-first) onto your measured segment direction,
// rotated from your facing into the avatar's; clavicles, spine and head keep the rest pose (you're standing upright).
static void a2_avatar_calpose(const V3* mp,double thU,Q4* cq,V3* ct){
    static Q4 lq[RB_MAX]; memcpy(lq,g_rb_lq,sizeof(Q4)*g_rb_n); rb_fk(lq,cq,ct);
    Q4 rin=qyaw(g_thM-thU);
    static const struct { const char* b; const char* c; int j0, j1; } seg[]={
        {"LeftArm","LeftForeArm",10,11},{"LeftForeArm","LeftHand",11,19},{"LeftHand","LeftHandMiddle1",19,30},
        {"RightArm","RightForeArm",15,16},{"RightForeArm","RightHand",16,45},{"RightHand","RightHandMiddle1",45,56},
        {"LeftUpLeg","LeftLeg",70,71},{"LeftLeg","LeftFoot",71,73},{"LeftFoot","LeftToeBase",73,76},
        {"RightUpLeg","RightLeg",77,78},{"RightLeg","RightFoot",78,80},{"RightFoot","RightToeBase",80,83} };
    for(unsigned k=0;k<sizeof seg/sizeof seg[0];k++){ int b=rb_find(seg[k].b), c=rb_find(seg[k].c); if(b<0||c<0) continue;
        V3 tgt=qrot(rin,vsub(mp[seg[k].j1],mp[seg[k].j0])); if(vlen(tgt)<1e-3) continue;
        Q4 sw=qbetween(vsub(ct[c],ct[b]),tgt); int p=g_rb_par[b]; Q4 pq=p>=0?cq[p]:QI;
        lq[b]=qnorm(qmul(qinv(pq),qmul(sw,cq[b]))); rb_fk(lq,cq,ct); } }
// derive THIS rig's offsets + scale from your saved pose: pose the avatar to your measured limb directions, then
// O_b = M_j(cal)^-1 * R_z(your facing - avatar facing) * A_b(cal); scale = your eye height / the avatar's
static void a2_apply_ucal(){
    static Q4 aq[RB_MAX]; static V3 at[RB_MAX];
    a2_avatar_calpose(g_ucP,g_ucThU,aq,at);
    Q4 ral=qyaw(g_ucThU-g_thM); int nb=0;
    for(int k=0;k<BM_N;k++){ BtMap& m=g_bm[k]; m.haveOff=false; if(m.bi<0) continue;
        m.off=qnorm(qmul(qinv(g_ucQ[m.joint]),qmul(ral,aq[m.bi]))); m.haveOff=true; nb++; }
    double s=(g_avEyeH>50)?g_ucEye/g_avEyeH:1.0; if(s<0.6) s=0.6; if(s>1.4) s=1.4; g_btScale=s; g_calOK=true;
    load_status("A2: your calibration applied to this rig: %d bones, scale %.3f (your eyes %.0f / avatar eyes %.0f cm); avatar arm posed to %.0f/%.0f deg",
        nb,s,g_ucEye,g_avEyeH,iLF>=0?elev_deg(vsub(at[iLF],at[iLA])):0.0,(iLF>=0&&iLH>=0)?elev_deg(vsub(at[iLH],at[iLF])):0.0); }
static void a2_calibrate(const Q4* mq,const V3* mp,V3 camP){
    for(int j=0;j<BT_NJ;j++){ g_ucQ[j]=mq[j]; g_ucP[j]=mp[j]; }
    V3 lu=vsub(mp[10],mp[15]); g_ucThU=yaw_of_left(V(lu.x,lu.y,0)); g_ucEye=camP.z; g_ucal=true;
    a2_save_ucal();
    load_status("A2 CALIBRATED (once, for every skin): you face %.0f deg, eyes %.0f cm; arm tilt L%.0f R%.0f, knee bend L%.0f R%.0f; saved %s",
        g_ucThU,g_ucEye,elev_deg(vsub(mp[19],mp[10])),elev_deg(vsub(mp[45],mp[15])),ang_deg(vsub(mp[71],mp[70]),vsub(mp[73],mp[71])),
        ang_deg(vsub(mp[78],mp[77]),vsub(mp[80],mp[78])),g_ucPath);
    if(g_rbOK) a2_apply_ucal(); }
static void a2_hide_bone(uintptr_t c,int i){ if(!g_fnHideBone||i<0) return; int oN=prop_offset(g_fnHideBone,"BoneName",0); if(oN<0) return;
    static uint8_t b[64]; memset(b,0,sizeof b); memcpy(b+oN,&g_rb_fn[i],8); call_uf(c,g_fnHideBone,b); }
static void a2_set_scale(uintptr_t c,double s){ if(!c||!g_fnRelScale) return; int o=prop_offset(g_fnRelScale,"NewScale3D",0); if(o<0) return;
    static uint8_t b[64]; memset(b,0,sizeof b); double* v=(double*)(b+o); v[0]=v[1]=v[2]=s; call_uf(c,g_fnRelScale,b); }
static uintptr_t a2_add_mesh(bool firstPerson){
    uintptr_t fn=g_fnAddComp; if(!fn||!g_isoActor||!g_poseCls||!g_mymesh||!g_trackParent) return 0;
    int oC=prop_offset(fn,"Class",0), oM=prop_offset(fn,"bManualAttachment",0), oX=prop_offset(fn,"RelativeTransform",0),
        oD=prop_offset(fn,"bDeferredFinish",0), oR=prop_offset(fn,"ReturnValue",0);
    uint16_t psz=rd16(fn+0xB6); static uint8_t b[512] __attribute__((aligned(16)));
    if(oC<0||oX<0||oR<0||psz>sizeof b){ load_status("A2: AddComponentByClass layout bad"); return 0; }
    memset(b,0,sizeof b); *(uintptr_t*)(b+oC)=g_poseCls; if(oM>=0) b[oM]=1; if(oD>=0) b[oD]=0;
    double* x=(double*)(b+oX); x[3]=1; x[8]=x[9]=x[10]=1;             // identity FTransform (quat w=1, scale 1)
    call_uf(g_isoActor,fn,b); uintptr_t c=*(uintptr_t*)(b+oR); if(!c) return 0;
    refresh_numelements(); root_object(c);
    { int oA=-1,oB=prop_offset(g_fnSetSkinned,"bReinitPose",0);
      for(uintptr_t f=rdptr(g_fnSetSkinned+OFF_ChildProps); f; f=rdptr(f+FF_Next)) if(ffield_is(f,"ObjectProperty")){ oA=(int)rd32(f+FP_Offset); break; }
      memset(b,0,sizeof b); if(oA>=0){ *(uintptr_t*)(b+oA)=g_mymesh; if(oB>=0) b[oB]=1; call_uf(c,g_fnSetSkinned,b); } }
    { int oP=prop_offset(g_fnAttach,"Parent",0), oL=prop_offset(g_fnAttach,"LocationRule",0), oRr=prop_offset(g_fnAttach,"RotationRule",0),
          oSc=prop_offset(g_fnAttach,"ScaleRule",0), oW=prop_offset(g_fnAttach,"bWeldSimulatedBodies",0);
      memset(b,0,sizeof b); if(oP>=0){ *(uintptr_t*)(b+oP)=g_trackParent; if(oL>=0) b[oL]=(uint8_t)g_attSnap; if(oRr>=0) b[oRr]=(uint8_t)g_attSnap;
          if(oSc>=0) b[oSc]=(uint8_t)g_attKeepRel; if(oW>=0) b[oW]=0; call_uf(c,g_fnAttach,b); } }
    a2_set_scale(c,g_btScale);
    call_bool2(c,g_fnColl2,0,0); call_bool2(c,g_fnShad2,0,0);
    if(g_fnTickGroup) call_bool2(c,g_fnTickGroup,5,0);                 // refresh bones after the pawn tick that sets them
    if(!g_noSplit){ if(firstPerson){ call_bool2(c,g_fnOnlyOwnerSee,1,0); a2_hide_bone(c,iHead); } else call_bool2(c,g_fnOwner,1,0); }
    a2_hide_bone(c,iLH); a2_hide_bone(c,iRH);                          // Tribe's tracked hands take their place
    call_bool2(c,g_fnVis,1,1); call_bool2(c,g_fnHid,0,1);
    return c; }
static bool g_a2Marker=false;                                          // crash-loop guard: tribemod/a2_inflight
static void a2_marker(bool on){ char p[600]; snprintf(p,sizeof p,"%s/a2_inflight",OUTDIR);
    if(on){ int fd=open(p,O_WRONLY|O_CREAT|O_TRUNC,0644); if(fd>=0){ fsync(fd); close(fd); } } else unlink(p); g_a2Marker=on; }
static void a2_go_live(){
    if(!g_a2Marker) a2_marker(true);                                   // removed after 120 good frames (a2_drive)
    if(!g_pmA){
        if(!g_trackParent){ uint8_t* r=call_ret(g_camComp,g_fnAttachParent,0,0); g_trackParent=r?*(uintptr_t*)r:0; if(!g_trackParent) g_trackParent=g_vrOrigin; }
        char pn[64]="?"; if(g_trackParent) obj_name(g_trackParent,pn,sizeof pn);
        if(g_fnSetOwner&&g_pawn){ int o=prop_offset(g_fnSetOwner,"NewOwner",0); static uint8_t b[32]; memset(b,0,sizeof b); if(o>=0){ *(uintptr_t*)(b+o)=g_pawn; call_uf(g_isoActor,g_fnSetOwner,b); } }
        g_pmA=a2_add_mesh(false); if(!g_noSplit) g_pmB=a2_add_mesh(true); g_handShown[0]=g_handShown[1]=false;
        load_status("A2: meshes A(full, owner-no-see)=0x%lx B(headless, only-owner-see)=0x%lx attached to %s (0x%lx) scale %.3f%s",
            (unsigned long)g_pmA,(unsigned long)g_pmB,pn,(unsigned long)g_trackParent,g_btScale,g_noSplit?" [nosplit]":"");
        if(!g_pmA){ g_a2Fail=true; load_status("A2: mesh creation FAILED -> staying in follow mode"); return; } }
    else { a2_set_scale(g_pmA,g_btScale); a2_set_scale(g_pmB,g_btScale); call_bool2(g_pmA,g_fnVis,1,1); if(g_pmB) call_bool2(g_pmB,g_fnVis,1,1); }
    call_bool2(g_isoComp,g_fnVis,0,1);                                  // retire the static follow mesh
    g_a2Live=true; g_a2Init=true; }
// ---- hands. Tribe draws Meta's tracked hand meshes (TribeControllers_C.OculusXRHandComponent) only while hand tracking
// has that hand; with controllers its hands were the ReadyPlayerMe hand meshes (ReadyPlayerMeComponent.AvatarLeft/RightHand),
// which are blank now that RPM is dead -> no hands at all. So per hand: hand tracking has it -> the model's hand stays
// hidden (Tribe's shows); controller -> the model's hand is shown, posed from Meta's hand joints (body tracking reports
// them with controllers too): wrist = frame match (wrist->middle knuckle, pinky->index knuckle; twist-correct, no
// calibration), each finger segment swung onto Meta's matching segment.
struct FingerSeg{ int b, j0, j1; V3 dloc; };                      // dloc = the bone's rest direction in its own rest frame
static FingerSeg g_fseg[2][16]; static int g_nfseg[2]={0,0};
static Q4 g_handFix[2]={{0,0,0,1},{0,0,0,1}}; static bool g_handFrameOK[2]={false,false};
static uintptr_t g_inLib=0, g_fnHandValid=0, g_fnHandConf=0, g_fnUnhideBone=0; static int64_t g_handType[2]={1,2}, g_confHigh=1;
static bool g_mv[BT_NJ];                                             // Meta joint bIsValid, this frame
static const int HJ[2][4]={{19,30,25,40},{45,56,51,66}};            // Meta: wrist, middle/index/little proximal (knuckles)
static Q4 quat_axes(V3 x,V3 y,V3 z){                                 // rotation taking (1,0,0),(0,1,0),(0,0,1) to x,y,z
    double m00=x.x,m10=x.y,m20=x.z,m01=y.x,m11=y.y,m21=y.z,m02=z.x,m12=z.y,m22=z.z, tr=m00+m11+m22, S;
    if(tr>0){ S=sqrt(tr+1.0)*2; return qnorm(Qm((m21-m12)/S,(m02-m20)/S,(m10-m01)/S,0.25*S)); }
    if(m00>m11&&m00>m22){ S=sqrt(1.0+m00-m11-m22)*2; return qnorm(Qm(0.25*S,(m01+m10)/S,(m02+m20)/S,(m21-m12)/S)); }
    if(m11>m22){ S=sqrt(1.0+m11-m00-m22)*2; return qnorm(Qm((m01+m10)/S,0.25*S,(m12+m21)/S,(m02-m20)/S)); }
    S=sqrt(1.0+m22-m00-m11)*2; return qnorm(Qm((m02+m20)/S,(m12+m21)/S,0.25*S,(m10-m01)/S)); }
static Q4 frame_q(V3 fwd,V3 side){ V3 x=vnorm(fwd), y=vnorm(vsub(side,vmul(x,vdot(side,x)))); return quat_axes(x,y,vcross(x,y)); }
static void a2_prep_hands(){                                         // per rig, from the rest skeleton
    static const char* SD[2]={"Left","Right"};
    static const struct{ const char* f; int j[2][4]; } F[5]={ {"Thumb",{{20,21,22,23},{46,47,48,49}}},{"Index",{{25,26,27,28},{51,52,53,54}}},
        {"Middle",{{30,31,32,33},{56,57,58,59}}},{"Ring",{{35,36,37,38},{61,62,63,64}}},{"Pinky",{{40,41,42,43},{66,67,68,69}}} };
    for(int s=0;s<2;s++){ g_nfseg[s]=0; int h=s?iRH:iLH; char nm[48];
        snprintf(nm,sizeof nm,"%sHandMiddle1",SD[s]); int mid=rb_find(nm); snprintf(nm,sizeof nm,"%sHandIndex1",SD[s]); int idx=rb_find(nm);
        snprintf(nm,sizeof nm,"%sHandPinky1",SD[s]); int pky=rb_find(nm);
        g_handFrameOK[s]=h>=0&&mid>=0&&idx>=0&&pky>=0;
        if(g_handFrameOK[s]) g_handFix[s]=qnorm(qmul(qinv(frame_q(vsub(g_rb_ct[mid],g_rb_ct[h]),vsub(g_rb_ct[idx],g_rb_ct[pky]))),g_rb_cq[h]));
        for(int f=0;f<5;f++) for(int k=1;k<=3;k++){                  // parent-first within each finger
            snprintf(nm,sizeof nm,"%sHand%s%d",SD[s],F[f].f,k); int b=rb_find(nm); if(b<0||g_rb_par[b]<0||g_nfseg[s]>=16) continue;
            snprintf(nm,sizeof nm,"%sHand%s%d",SD[s],F[f].f,k+1); int c=rb_find(nm);
            V3 d=c>=0?vsub(g_rb_ct[c],g_rb_ct[b]):vsub(g_rb_ct[b],g_rb_ct[g_rb_par[b]]);   // last phalanx: continue the previous
            FingerSeg& fs=g_fseg[s][g_nfseg[s]++]; fs.b=b; fs.j0=F[f].j[s][k-1]; fs.j1=F[f].j[s][k]; fs.dloc=qrot(qinv(g_rb_cq[b]),vnorm(d)); } }
    load_status("A2 hands: frame L%d R%d, finger bones L%d R%d",(int)g_handFrameOK[0],(int)g_handFrameOK[1],g_nfseg[0],g_nfseg[1]); }
static void a2_unhide_bone(uintptr_t c,int i){ if(!g_fnUnhideBone||i<0) return; int oN=prop_offset(g_fnUnhideBone,"BoneName",0); if(oN<0) return;
    static uint8_t b[64]; memset(b,0,sizeof b); memcpy(b+oN,&g_rb_fn[i],8); call_uf(c,g_fnUnhideBone,b); }
static int a2_hand_call(uintptr_t fn,int64_t hand){                  // OculusXRInputFunctionLibrary fn(DeviceHand, ControllerIndex=0) -> byte
    if(!g_inLib||!fn) return -2; uint16_t psz=rd16(fn+0xB6); static uint8_t b[32]; if(psz>sizeof b) return -3; memset(b,0,sizeof b);
    int oH=prop_offset(fn,"DeviceHand",0); b[oH>=0?oH:0]=(uint8_t)hand;
    call_uf(g_inLib,fn,b); uint16_t rvo=rd16(fn+0xB8); return (rvo==0xFFFF||rvo>=psz)?-1:(int)b[rvo]; }
static void a2_update_hand_modes(){
    for(int s=0;s<2;s++){ int h=s?iRH:iLH; if(h<0) continue;
        int valid=a2_hand_call(g_fnHandValid,g_handType[s]), conf=a2_hand_call(g_fnHandConf,g_handType[s]);
        bool want=!(valid==1&&(conf<0||conf==(int)g_confHigh));    // hand tracking doesn't have this hand -> show the model's
        if(want==g_handShown[s]) continue;
        g_handShown[s]=want; uintptr_t ms[2]={g_pmA,g_pmB};
        for(int m=0;m<2;m++) if(ms[m]){ if(want) a2_unhide_bone(ms[m],h); else a2_hide_bone(ms[m],h); }
        load_status("A2 hands: %s -> %s (hand tracking valid=%d confidence=%d)",s?"right":"left",
            want?"MODEL hand shown (controller)":"Tribe's tracked hand (model hand hidden)",valid,conf); } }
// ---- space alignment (advisor: "make sure the body and HMD stay aligned after a recenter"). The camera's pose is
// base-corrected by the plugin (BaseOrientation^-1 * (P - BaseOffset)); TryGetBodyState's joints are NOT. After a UE-level
// recenter the body sits beside you (measured: eyes-vs-MetaHead 17/17 cm instead of 7.5/0). Apply the same correction to
// the joints -- self-verifying: each frame, score both raw and corrected by how far Meta's head joint is from where it
// belongs behind your eyes (EYES_FROM_HEAD, measured in an aligned session), and use the better one.
static uintptr_t g_hmdLib=0, g_fnGetBase=0; static Q4 g_baseQ={0,0,0,1}; static V3 g_baseOff={0,0,0};
static int g_align=0; static double g_errRaw=0, g_errAl=0;          // g_align 1 = use the base-corrected joints
static const V3 EYES_FROM_HEAD={7.5,0.0,8.0};                        // eyes relative to Meta's head joint, HMD frame (cm)
static void a2_read_base(){                                          // UOculusXRFunctionLibrary::GetBaseRotationAndBaseOffsetInMeters
    if(!g_hmdLib||!g_fnGetBase) return; uint16_t psz=rd16(g_fnGetBase+0xB6); static uint8_t b[128] __attribute__((aligned(16)));
    int oR=prop_offset(g_fnGetBase,"OutRotation",0), oO=prop_offset(g_fnGetBase,"OutBaseOffsetInMeters",0);
    if(psz>sizeof b||oR<0||oO<0) return; memset(b,0,sizeof b); call_uf(g_hmdLib,g_fnGetBase,b);
    Q4 q=rot2q((double*)(b+oR)); double* o=(double*)(b+oO); V3 off=V(o[0]*g_w2m,o[1]*g_w2m,o[2]*g_w2m);
    if(fabs(q.x-g_baseQ.x)+fabs(q.y-g_baseQ.y)+fabs(q.z-g_baseQ.z)+fabs(q.w-g_baseQ.w)>1e-4||vlen(vsub(off,g_baseOff))>0.5){
        double* r=(double*)(b+oR); load_status("A2 align: plugin base rotation (P%.1f Y%.1f R%.1f) offset (%.1f,%.1f,%.1f) cm",r[0],r[1],r[2],off.x,off.y,off.z); }
    g_baseQ=q; g_baseOff=off; }
static double a2_head_err(V3 head,Q4 camQ,V3 camP){ V3 d=vsub(qrot(qinv(camQ),vsub(camP,head)),EYES_FROM_HEAD); return sqrt(d.x*d.x+d.y*d.y); }
// two-bone IK (advisor): bend Arm/ForeArm so the wrist lands on W, elbow in the plane of pole P; keeps bone lengths
static void a2_ik_arm(int a,int f,int h,V3 W,V3 P,Q4* tq,const Q4* cq,const V3* ct,double* err){
    V3 S=ct[a]; double l1=vlen(g_rb_lt[f]), l2=vlen(g_rb_lt[h]); V3 dv=vsub(W,S); double d=vlen(dv); if(d<1e-3||l1<1||l2<1) return;
    V3 dir=vmul(dv,1.0/d); *err=vlen(vsub(ct[h],W));
    double dmin=fabs(l1-l2)+0.5, dmax=l1+l2-0.5; if(d>dmax) d=dmax; if(d<dmin) d=dmin;
    double x=(l1*l1-l2*l2+d*d)/(2*d), hh=sqrt(fmax(0.0,l1*l1-x*x));
    V3 pv=vsub(P,S), pp=vsub(pv,vmul(dir,vdot(pv,dir))); if(vlen(pp)<1e-3){ pv=vsub(ct[f],S); pp=vsub(pv,vmul(dir,vdot(pv,dir))); }
    V3 E=vadd(S,vadd(vmul(dir,x),vmul(vnorm(pp),hh))), Wc=vadd(S,vmul(dir,d));
    tq[a]=qnorm(qmul(qbetween(vsub(ct[f],S),vsub(E,S)),cq[a]));
    tq[f]=qnorm(qmul(qbetween(qrot(tq[f],g_rb_lt[h]),vsub(Wc,E)),tq[f])); }
static void a2_fk(const Q4* tq,const bool* dv,Q4* cq,V3* ct){          // Hips takes Meta's hip position even if it isn't the root
    for(int i=0;i<g_rb_n;i++){ int p=g_rb_par[i];
        cq[i]=dv[i]?tq[i]:(p<0?g_rb_lq[i]:qnorm(qmul(cq[p],g_rb_lq[i])));
        ct[i]=(i==iHips&&dv[i])?g_hipsCur:(p<0?g_rb_lt[i]:vadd(ct[p],qrot(cq[p],g_rb_lt[i]))); } }
static void a2_set_bone(uintptr_t comp,int i,Q4 q,V3 t){
    static int oN=-2,oX=-1,oS=-1; static uint16_t psz=0;
    if(oN==-2){ oN=prop_offset(g_fnSetBoneXf,"BoneName",0); oX=prop_offset(g_fnSetBoneXf,"InTransform",0); oS=prop_offset(g_fnSetBoneXf,"BoneSpace",0); psz=rd16(g_fnSetBoneXf+0xB6);
        load_status("A2: SetBoneTransformByName psz=0x%x BoneName@%d InTransform@%d BoneSpace@%d (ComponentSpace=%lld)",psz,oN,oX,oS,(long long)g_boneCS); }
    static uint8_t b[256] __attribute__((aligned(16))); if(oN<0||oX<0||psz>sizeof b) return;
    memset(b,0,psz); memcpy(b+oN,&g_rb_fn[i],8); double* x=(double*)(b+oX);
    x[0]=q.x; x[1]=q.y; x[2]=q.z; x[3]=q.w; x[4]=t.x; x[5]=t.y; x[6]=t.z; x[8]=x[9]=x[10]=1; if(oS>=0) b[oS]=(uint8_t)g_boneCS;
    call_uf(comp,g_fnSetBoneXf,b); }
static void a2_drive(const Q4* mq,const V3* mp,Q4 camQ,V3 camP,float dt){
    static Q4 tq[RB_MAX], cq[RB_MAX]; static V3 ct[RB_MAX]; static bool dv[RB_MAX]; static double logT=0, usSum=0; static int usN=0;
    struct timespec t0,t1; clock_gettime(CLOCK_MONOTONIC,&t0);
    double a=g_smooth?1.0-exp(-dt/0.030):1.0, is=1.0/g_btScale; bool init=g_a2Init; g_a2Init=false;
    for(int i=0;i<g_rb_n;i++) dv[i]=false;
    for(int k=0;k<BM_N;k++){ BtMap& m=g_bm[k]; if(m.bi<0||!m.haveOff) continue;
        Q4 t=qnorm(qmul(mq[m.joint],m.off)); m.cur=init?t:qslerp(m.cur,t,a); tq[m.bi]=m.cur; dv[m.bi]=true; }
    V3 hipT=vmul(mp[1],is); g_hipsCur=init?hipT:vadd(g_hipsCur,vmul(vsub(hipT,g_hipsCur),a));
    if(iHead>=0){ Q4 hc=qnorm(qmul(camQ,g_offHeadCam)); Q4 dH=dv[iHead]?qmul(hc,qinv(tq[iHead])):QI;       // head = HMD
        tq[iHead]=hc; dv[iHead]=true; if(iNeck>=0&&dv[iNeck]) tq[iNeck]=qnorm(qmul(qslerp(QI,dH,0.5),tq[iNeck])); }   // neck: half the seam
    a2_fk(tq,dv,cq,ct);
    double eL=-1,eR=-1;
    if(g_ikL&&dv[iLA]&&dv[iLF]) a2_ik_arm(iLA,iLF,iLH,vmul(mp[19],is),vmul(mp[11],is),tq,cq,ct,&eL);
    if(g_ikR&&dv[iRA]&&dv[iRF]) a2_ik_arm(iRA,iRF,iRH,vmul(mp[45],is),vmul(mp[16],is),tq,cq,ct,&eR);
    a2_fk(tq,dv,cq,ct);
    { static int hc=0; if(++hc>=8){ hc=0; a2_update_hand_modes(); } }      // hand tracking vs controller, per hand
    bool hands=false;
    for(int s=0;s<2;s++){ int h=s?iRH:iLH; const int* j=HJ[s];
        if(!g_handShown[s]||h<0||!g_handFrameOK[s]||!(g_mv[j[0]]&&g_mv[j[1]]&&g_mv[j[2]]&&g_mv[j[3]])) continue;
        tq[h]=qnorm(qmul(frame_q(vsub(mp[j[1]],mp[j[0]]),vsub(mp[j[2]],mp[j[3]])),g_handFix[s])); dv[h]=true; hands=true; }
    if(hands){ a2_fk(tq,dv,cq,ct);                                   // fingers hang off the posed hands, parent-first
        for(int s=0;s<2;s++){ if(!g_handShown[s]) continue;
            for(int k=0;k<g_nfseg[s];k++){ FingerSeg& f=g_fseg[s][k]; int b=f.b, p=g_rb_par[b];
                if(!g_mv[f.j0]||!g_mv[f.j1]) continue; V3 tgt=vsub(mp[f.j1],mp[f.j0]); if(vlen(tgt)<1e-3) continue;
                Q4 prov=qnorm(qmul(cq[p],g_rb_lq[b])); Q4 q=qnorm(qmul(qbetween(qrot(prov,f.dloc),tgt),prov));
                tq[b]=q; dv[b]=true; cq[b]=q; ct[b]=vadd(ct[p],qrot(cq[p],g_rb_lt[b])); } }
        a2_fk(tq,dv,cq,ct); }
    for(int i=0;i<g_rb_n;i++) if(dv[i]){ a2_set_bone(g_pmA,i,cq[i],ct[i]); if(g_pmB) a2_set_bone(g_pmB,i,cq[i],ct[i]); }
    { static int good=0; if(g_a2Marker && ++good>=120){ a2_marker(false); load_status("A2: 120 frames driven OK (crash guard cleared)"); } }
    clock_gettime(CLOCK_MONOTONIC,&t1); usSum+=(t1.tv_sec-t0.tv_sec)*1e6+(t1.tv_nsec-t0.tv_nsec)/1e3; usN++;
    int nset=0; for(int i=0;i<g_rb_n;i++) nset+=dv[i];
    logT+=dt; if(logT>=2.0||init){ logT=0;
        V3 d=qrot(qinv(camQ),vsub(camP,mp[7]));                         // eyes relative to Meta's head joint, in the HMD's frame
        int rA=-1,rB=-1; uint8_t* r=call_ret(g_pmA,g_fnRendered,1,0.5f); if(r) rA=*r; if(g_pmB){ r=call_ret(g_pmB,g_fnRendered,1,0.5f); if(r) rB=*r; }
        double wc[2]={-1,-1}; uintptr_t mc[2]={g_mcL,g_mcR}; int wj[2]={19,45};
        for(int s2=0;s2<2;s2++){ double l[3]; if(mc[s2]&&sr(mc[s2]+g_offRelLoc,l,24)) wc[s2]=vlen(vsub(V(l[0],l[1],l[2]),mp[wj[s2]])); }
        load_status("A2 live: dt=%.4f drive=%.0f us (%d bones/mesh) hands L%s R%s | align=%s (head err raw %.1f / corrected %.1f) eyes-vs-MetaHead fwd/right/up=(%.1f,%.1f,%.1f) | Meta wrist-to-controller L%.0f R%.0f cm | wristIK L%.1f R%.1f | rendered A=%d B=%d",
            dt,usN?usSum/usN:0.0,nset,g_handShown[0]?"=model":"=tribe",g_handShown[1]?"=model":"=tribe",
            g_align?"base":"raw",g_errRaw,g_errAl,d.x,d.y,d.z,wc[0],wc[1],eL*g_btScale,eR*g_btScale,rA,rB); usSum=0; usN=0; } }
// skin changed (do_load put the new mesh on our actor's component): drop the old tracked meshes and rebuild for the new
// rig. Fresh components (not an asset swap) because a same-bone-count asset swap keeps the old rig's hidden-bone indices.
static void a2_drop_meshes(){
    uintptr_t cs[2]={g_pmA,g_pmB};
    for(int k=0;k<2;k++){ uintptr_t c=cs[k]; if(!c) continue; call_bool2(c,g_fnVis,0,1); unroot_object(c);
        if(g_fnDestroyComp){ int o=prop_offset(g_fnDestroyComp,"Object",0); static uint8_t b[16]; memset(b,0,sizeof b); if(o>=0){ *(uintptr_t*)(b+o)=c; call_uf(c,g_fnDestroyComp,b); } } }
    g_pmA=g_pmB=0; g_a2Live=false; }
static void a2_rerig(){
    a2_drop_meshes();
    g_rbTried=true; g_rbOK=a2_build_rest();                            // reads the NEW rig; applies your calibration to it
    if(!g_rbOK){ call_bool2(g_isoComp,g_fnVis,1,1); load_status("A2: new skin can't be body-tracked -> it follows you, stiff"); return; }
    if(!g_calOK) call_bool2(g_isoComp,g_fnVis,1,1);                    // until you've calibrated once, show the follow body
    load_status("A2: re-rigged for the new skin (%d bones)%s",g_rb_n,g_calOK?" -> live on the next frame":" -- waiting for your calibration pose"); }
// per frame (pawn tick): fetch body state, then calibrate or drive
static void bt_frame(float dt){
    if(!g_bt_started||!g_btLayoutOK||!g_isoComp||!g_camComp||g_a2Fail) return;
    if(g_a2Recal){ g_a2Recal=0; g_ucal=false; g_calOK=false; g_a2Live=false; g_tposeHold=0;
        if(g_pmA) call_bool2(g_pmA,g_fnVis,0,1); if(g_pmB) call_bool2(g_pmB,g_fnVis,0,1); call_bool2(g_isoComp,g_fnVis,1,1);
        load_status("A2: recalibrating -> follow mode until your next calibration pose"); }
    if(g_skin_changed){ g_skin_changed=0; a2_rerig(); }
    memset(g_btParms,0,sizeof g_btParms); uint8_t* s=g_btParms+bt_oState;
    *(uintptr_t*)(s+0x10)=(uintptr_t)g_btJoints; *(int32_t*)(s+0x18)=BT_NJ; *(int32_t*)(s+0x1C)=BT_NJ;
    if(bt_oW2M>=0) *(float*)(g_btParms+bt_oW2M)=g_w2m;
    call_uf(g_btLib,g_fnBtState,g_btParms);
    if(!g_btParms[bt_oRet]||!s[0]) return;                            // tracking inactive: hold the last pose
    static Q4 mq[BT_NJ]; static V3 mp[BT_NJ];
    for(int i=0;i<BT_NJ;i++){ uint8_t* j=g_btJoints+i*BT_JSZ; mq[i]=rot2q((double*)(j+0x10)); double* p=(double*)(j+0x28); mp[i]=V(p[0],p[1],p[2]); g_mv[i]=j[8]!=0; }
    double cr[3]={0,0,0}, cl[3]={0,0,0}; if(g_offRelRot<0||g_offRelLoc<0||!sr(g_camComp+g_offRelRot,cr,24)||!sr(g_camComp+g_offRelLoc,cl,24)) return;
    Q4 camQ=rot2q(cr); V3 camP=V(cl[0],cl[1],cl[2]);
    { static int bc=0; if(bc++%30==0) a2_read_base();
      Q4 bi=qinv(g_baseQ); V3 hAl=qrot(bi,vsub(mp[7],g_baseOff));
      double k=dt/0.5; if(k>1) k=1; g_errRaw+=(a2_head_err(mp[7],camQ,camP)-g_errRaw)*k; g_errAl+=(a2_head_err(hAl,camQ,camP)-g_errAl)*k;
      int want=g_align; if(g_errAl<g_errRaw-3.0) want=1; else if(g_errRaw<g_errAl-3.0) want=0;
      if(want!=g_align){ g_align=want; load_status("A2 align: using %s joints (head error raw %.1f cm vs base-corrected %.1f cm)",want?"BASE-CORRECTED":"raw",g_errRaw,g_errAl); }
      if(g_align) for(int i=0;i<BT_NJ;i++){ mp[i]=qrot(bi,vsub(mp[i],g_baseOff)); mq[i]=qnorm(qmul(bi,mq[i])); } }
    { static int fr=0,nw=0; static float lt=-1; float tm=*(float*)(s+12);  // advisor Q2: fresh every frame, or 30 Hz steps?
      if(fr<150){ fr++; if(tm!=lt){ nw++; lt=tm; }
        if(fr==150){ g_smooth=(nw<105); load_status("A2 rate: %d frames, %d new samples -> %s",fr,nw,g_smooth?"stepping: smoothing ON (tau 30 ms)":"fresh every frame: no smoothing"); } } }
    if(!g_rbTried){ g_rbTried=true; g_rbOK=a2_build_rest(); }          // a rig that can't be tracked keeps following, stiff
    if(!g_ucal){                                                       // your pose is captured once, whatever skin is on
        static V3 pWL,pWR,pH; static double spd=100; static bool have=false;          // motion: fastest of wrists/head, smoothed 0.3 s
        double inst=(have&&dt>1e-4)?fmax(vlen(vsub(mp[19],pWL)),fmax(vlen(vsub(mp[45],pWR)),vlen(vsub(mp[7],pH))))/dt:100;
        pWL=mp[19]; pWR=mp[45]; pH=mp[7]; have=true; double k=dt/0.3; if(k>1) k=1; spd+=(inst-spd)*k;
        char why[260]; bool ok=a2_pose_check(mp,spd,why,sizeof why);
        if(g_a2CalNow){ g_a2CalNow=0; ok=true; g_tposeHold=1.0; load_status("A2: bt_calibrate_now -> capturing the current pose"); }
        g_tposeHold=ok?g_tposeHold+dt:0;
        static double logT=0; logT+=dt; if(logT>=3.0){ logT=0; load_status("A2 waiting for a still calibration pose (stand; arms straight, T or A; ~1 s): %s -> %s",why,ok?"GOOD, hold":"not yet"); }
        if(g_tposeHold<1.0) return;
        a2_calibrate(mq,mp,camP); }
    if(!g_rbOK||!g_calOK) return;
    if(!g_a2Live){ a2_go_live(); if(!g_a2Live) return; }
    a2_drive(mq,mp,camQ,camP,dt); }
// ============ Drone camera (flag tribemod/drone_cam, params tribemod/drone.txt) ============
// Flies a Tribe stream camera in a smooth orbit around you. Default target = the SELFIE STICK's camera (the one you stream
// with): place the stick by hand, turn the drone on, and it takes off from exactly there -- same distance, height and
// angle -- then orbits. Turning it off lands the camera back on the stick (its mount pose is saved at takeoff and
// restored). "target=auto" in drone.txt flies Tribe's Auto cam instead. The poll thread resolves the camera + reads params
// (drone_poll); this game-thread tick moves it. Orbit center = your head through a 1.5 s low-pass (head-bobbing to the
// beat doesn't shake the shot).
static volatile sig_atomic_t g_droneOn=0, g_droneTarget=0, g_dRset=0, g_dHset=0;    // target 0 = selfie stick, 1 = Auto cam
static uintptr_t g_droneCap=0, g_fnSetWorldLR=0, g_fnSetRelLR=0, g_dronePC=0;
// Tribe's Auto cam is a beat-synced CUT camera (decompiled TribePlayerController, NOTES 3i): +0x97c BPM, +0x978 beats
// per cut, +0x980 AutoCamMode (1 = Slow, doubles the beats), +0x970 cut interval s, +0x974 SECONDS UNTIL THE NEXT CUT
// (counts down; each cut resets it to the interval). Holding +0x974 huge while we fly it stops Tribe yanking the camera.
static const uint32_t PC_AUTOCAM_NEXTCUT=0x974;
static volatile double g_dR=300, g_dH=80, g_dSpeed=12, g_dLook=-40, g_dBob=20;   // cm, cm vs head, deg/s, aim vs eyes cm, cm
// SceneComponent.K2_Set{World,Relative}LocationAndRotation share params (NewLocation, NewRotation, bSweep, SweepHitResult,
// bTeleport); offsets resolved by name per function, cached in two slots.
static void set_comp_xform(uintptr_t fn,uintptr_t comp,const double loc[3],const double rot[3]){
    static uintptr_t cf[2]={0,0}; static int cL[2],cR[2],cS[2],cT[2];
    if(!fn||!comp) return; int s=(cf[0]==fn)?0:(cf[1]==fn)?1:-1;
    if(s<0){ s=cf[0]?1:0; cf[s]=fn; cL[s]=prop_offset(fn,"NewLocation",0); cR[s]=prop_offset(fn,"NewRotation",0);
        cS[s]=prop_offset(fn,"bSweep",0); cT[s]=prop_offset(fn,"bTeleport",0);
        LOGI("[DRONE] xform fn psz=0x%x NewLocation@%d NewRotation@%d bSweep@%d bTeleport@%d",rd16(fn+0xB6),cL[s],cR[s],cS[s],cT[s]); }
    uint16_t psz=rd16(fn+0xB6); static uint8_t b[1024]; if(cL[s]<0||cR[s]<0||psz>sizeof b) return;
    memset(b,0,psz); memcpy(b+cL[s],loc,24); memcpy(b+cR[s],rot,24); if(cS[s]>=0) b[cS[s]]=0; if(cT[s]>=0) b[cT[s]]=1;
    call_uf(comp,fn,b); }
static void drone_update(float dt){
    static bool flying=false, parked=false, haveRel=false, haveLast=false;
    static uintptr_t flyCap=0; static int flyTgt=0;
    static double relL[3], relR[3], C[3], th=0, t=0, rS=300, hS=80, lastP[3], logT=0;
    uintptr_t pc=g_dronePC, cap=g_droneCap;
    bool active=g_droneOn && cap && g_fnSetWorldLR && g_camComp && g_fnLoc;
    if(flying && (!active || cap!=flyCap)){                        // landing: drone off, or the camera/target changed
        if(haveRel && g_fnSetRelLR){ set_comp_xform(g_fnSetRelLR,flyCap,relL,relR);
            LOGI("[DRONE] landed: camera back on its %s mount",flyTgt?"Auto-cam":"selfie-stick"); }
        if(parked && pc){ float* cd=(float*)(pc+PC_AUTOCAM_NEXTCUT); if(*cd>1e8f) *cd=0.5f; LOGI("[DRONE] released Tribe's Auto-cam cuts"); }
        flying=false; parked=false; haveRel=false; haveLast=false; }
    if(!active||dt<=0||dt>0.25f) return;
    double H[3]; if(!get_vec3(g_camComp,g_fnLoc,H)) return;        // your head (HMD) in world space
    if(!flying){                                                    // takeoff from wherever the camera is right now
        double P0[3]; if(!get_vec3(cap,g_fnLoc,P0)) return;
        int tgt=g_droneTarget;
        haveRel=g_offRelLoc>=0&&g_offRelRot>=0&&sr(cap+g_offRelLoc,relL,24)&&sr(cap+g_offRelRot,relR,24);
        if(tgt==0&&(!haveRel||!g_fnSetRelLR)){ static int w=0; if((w++%300)==0)
            LOGI("[DRONE] not taking off: can't save the selfie camera's mount pose (relLoc@%d relRot@%d setRel=0x%lx)",
                g_offRelLoc,g_offRelRot,(unsigned long)g_fnSetRelLR); return; }
        memcpy(C,H,24); double dx=P0[0]-H[0], dy=P0[1]-H[1];
        rS=sqrt(dx*dx+dy*dy); if(rS<50) rS=50; if(rS>2000) rS=2000;
        hS=P0[2]-H[2]; if(hS<-200) hS=-200; if(hS>600) hS=600;
        th=atan2(dy,dx)*180.0/M_PI; t=0; logT=0; flying=true; flyCap=cap; flyTgt=tgt;
        LOGI("[DRONE] takeoff (%s) from (%.0f,%.0f,%.0f): %.0f cm out, %.0f cm vs your head, angle %.0f deg",
            tgt?"Auto cam":"selfie stick",P0[0],P0[1],P0[2],rS,hS,th); }
    if(flyTgt==1&&pc){ float* cd=(float*)(pc+PC_AUTOCAM_NEXTCUT); float v=*cd;   // Auto cam only: park its cut timer
        if((v>0.0f&&v<600.0f)||v>1e8f){ if(!parked) LOGI("[DRONE] parking Tribe's Auto-cam cuts (next-cut timer was %.2fs)",v);
            *cd=1e9f; parked=true; } }
    double k=dt/1.5; if(k>1) k=1; for(int i=0;i<3;i++) C[i]+=(H[i]-C[i])*k;  // smoothed orbit center
    double r=g_dRset?(double)g_dR:rS, h=g_dHset?(double)g_dH:hS;              // drone.txt overrides the stick's start pose
    th=fmod(th+g_dSpeed*dt,360.0); t+=dt; double a=th*M_PI/180.0;
    double P[3]={ C[0]+r*cos(a), C[1]+r*sin(a), C[2]+h+g_dBob*sin(t*0.6) };
    double A[3]={ C[0], C[1], C[2]+g_dLook };                               // aim point: a bit below your eyes
    double dx=A[0]-P[0], dy=A[1]-P[1], dz=A[2]-P[2], hz=sqrt(dx*dx+dy*dy);
    double R[3]={ atan2(dz,hz)*180.0/M_PI, atan2(dy,dx)*180.0/M_PI, 0 };    // FRotator: Pitch, Yaw, Roll
    logT+=dt;
    if(logT>=5.0){ logT=0; double Q[3]; bool got=get_vec3(cap,g_fnLoc,Q);
        // drift = how far the camera moved since OUR last write. ~0 = we're the only writer; large = something fights us.
        double d=(got&&haveLast)?sqrt((Q[0]-lastP[0])*(Q[0]-lastP[0])+(Q[1]-lastP[1])*(Q[1]-lastP[1])+(Q[2]-lastP[2])*(Q[2]-lastP[2])):-1;
        LOGI("[DRONE] %s center=(%.0f,%.0f,%.0f) cam=(%.0f,%.0f,%.0f) pitch=%.0f yaw=%.0f orbit=%.0fdeg r=%.0f h=%.0f spd=%.0f drift=%.1fcm cutsParked=%d",
            flyTgt?"auto":"selfie",C[0],C[1],C[2],P[0],P[1],P[2],R[0],R[1],th,r,h,(double)g_dSpeed,d,(int)parked); }
    set_comp_xform(g_fnSetWorldLR,cap,P,R); memcpy(lastP,P,24); haveLast=true; }
extern "C" void repl_pe(void* self,void* func,void* parms){
    // BLOCK Blueprint-level resets of our body while the keeper is on (Tribe setting AvatarBodyMesh to null/other).
    if(g_keep && !g_in_load && g_fnSet && func==(void*)g_fnSet && (uintptr_t)self==g_body && parms && *(uintptr_t*)parms!=g_mymesh){
        g_resets_bp++; if(g_resets_bp<=20||(g_resets_bp%100)==0) load_status("BLOCKED BP reset of body -> 0x%lx (#%d)",(unsigned long)*(uintptr_t*)parms,g_resets_bp);
        return;                                                    // swallow it
    }
    // FOLLOW: our actor's ReceiveTick (TG_PostUpdateWork) drives the body each frame. AActor::Tick always routes
    // ReceiveTick through ProcessEvent even with no Blueprint implementation. Fallback: the pawn's tick, only while ours is silent.
    if(g_isoActor && !g_in_load && parms){
        uintptr_t s=(uintptr_t)self;
        if(s==g_isoActor && func==(void*)g_fnReceiveTick){ g_isoTicks++; g_in_load=1; follow_update(*(float*)parms); bt_frame(*(float*)parms); drone_update(*(float*)parms); g_in_load=0; }
        else if(g_isoTicks==0 && s && s==g_fallbackTicker && is_receive_tick(func)){ g_camTicks++; g_in_load=1; follow_update(*(float*)parms); bt_frame(*(float*)parms); drone_update(*(float*)parms); g_in_load=0; }
    }
    // keeper: poll thread saw a NATIVE reset -> re-attach our (rooted) mesh here on the game thread
    if(g_reattach_req && g_keep && !g_in_load){ g_reattach_req=0; g_in_load=1; attach_mesh(g_body,g_mymesh); g_in_load=0; }
    if(g_iso_req && !g_in_load){ g_iso_req=0; g_in_load=1; spawn_iso_actor(g_mymesh); g_in_load=0;
        g_reports=0; g_report_ticks=2; }                        // fresh RENDER reports ~1s after the spawn, then every 10s
    if(g_report_req && g_body && !g_in_load){ g_report_req=0; g_in_load=1; g_reports++; render_report(); g_in_load=0; }
    if(g_log_pe && g_resolved) pe_log_func((uintptr_t)func);     // diagnostic: capture avatar/skin/menu events
    // skin-cycle: after the first load, when Tribe (re)applies the RPM skin from the avatar menu, advance
    // to the next skin + arm a reload. Debounced 2s so init-time / repeated applies don't spin the cycle.
    if(g_loaded_once && !g_in_load && g_apply_fn && func==(void*)g_apply_fn && parms){
        long now=(long)time(0);
        if(now-g_last_cycle>=2){ uintptr_t skin=*(uintptr_t*)parms;
            if(is_rpm_skin(skin)){ g_last_cycle=now; advance_skin(); g_load_req=1; } } }
    if(g_load_req && !g_in_load){ g_in_load=1; g_load_req=0; run_load_guarded(); g_in_load=0; }
    if(g_bt_req && !g_in_load){ g_bt_req=0; g_in_load=1; run_guarded(bt_start,"body-tracking start"); g_in_load=0; }
    if(g_bt_poll_req && !g_in_load){ g_bt_poll_req=0; g_in_load=1; run_guarded(bt_poll,"body-tracking poll"); g_in_load=0; }
    orig_pe(self,func,parms);
}

static bool file_present(const char* name){ char p[600]; snprintf(p,sizeof p,"%s/%s",OUTDIR,name); int fd=open(p,O_RDONLY); if(fd>=0){ close(fd); return true; } return false; }

// ================= GLES capture probe (advisor milestone; flags tribemod/capture_probe + capture_now) =================
// DISABLED by default. Purpose: find out what eglSwapBuffers actually sees on this Quest build -- the avatar/spectator
// view, an eye image, a mirror, or nothing -- BEFORE any encoder/audio/network work. On Quest the real frames go to XR
// swapchain textures submitted to the compositor, so the swap surface may NOT hold the avatar view; the probe measures
// rather than assumes. One-shot burst: logs the GL context (surface dims, viewport, draw/read FBO), reads back the bound
// READ framebuffer BEFORE forwarding the original swap, into an owned heap buffer written off the render thread. Restores
// pixel-pack state; forwards orig exactly once. No encoder, no audio, no networking.
typedef void* EGLDisplay_; typedef void* EGLSurface_; typedef unsigned int EGLBoolean_; typedef int EGLint_;
typedef unsigned int GLenum_; typedef int GLint_; typedef int GLsizei_;
static EGLBoolean_ (*orig_eglSwap)(EGLDisplay_,EGLSurface_)=0;
static EGLBoolean_ (*p_eglQuerySurface)(EGLDisplay_,EGLSurface_,EGLint_,EGLint_*)=0;
static void (*p_glGetIntegerv)(GLenum_,GLint_*)=0;
static void (*p_glReadPixels)(GLint_,GLint_,GLsizei_,GLsizei_,GLenum_,GLenum_,void*)=0;
static void (*p_glPixelStorei)(GLenum_,GLint_)=0;
static GLenum_ (*p_glGetError)(void)=0;
static const EGLint_ EGL_WIDTH_=0x3057, EGL_HEIGHT_=0x3056;
static const GLenum_ GL_VIEWPORT_=0x0BA2, GL_FRAMEBUFFER_BINDING_=0x8CA6, GL_READ_FRAMEBUFFER_BINDING_=0x8CAA,
    GL_PACK_ALIGNMENT_=0x0D05, GL_RGBA_=0x1908, GL_UNSIGNED_BYTE_=0x1401;
static volatile sig_atomic_t g_probe_armed=0; static int g_probe_left=0, g_probe_seq=0; static bool g_probe_hooked=false;
static double g_probe_lastT=0, g_probe_dtSum=0; static int g_probe_dtN=0; static bool g_probe_baselined=false;
static void probe_log(const char* fmt,...){ char m[512]; va_list ap; va_start(ap,fmt); vsnprintf(m,sizeof m,fmt,ap); va_end(ap);
    LOGI("[PROBE] %s",m); char p[600]; snprintf(p,sizeof p,"%s/probe/probe.log",OUTDIR); FILE* f=fopen(p,"a"); if(f){ fprintf(f,"%s\n",m); fclose(f);} }
struct FrameJob{ uint8_t* buf; int w,h,fbo,seq; };
static void* probe_writer(void* arg){ FrameJob* j=(FrameJob*)arg; char p[700];       // write off the render thread
    snprintf(p,sizeof p,"%s/probe/frame_%d_%dx%d_fbo%d.rgba",OUTDIR,j->seq,j->w,j->h,j->fbo);
    FILE* f=fopen(p,"wb"); if(f){ fwrite(j->buf,1,(size_t)j->w*j->h*4,f); fclose(f);} free(j->buf); free(j); return 0; }
static void probe_capture(EGLDisplay_ dpy, EGLSurface_ surf){
    int sw=0,sh=0; if(p_eglQuerySurface){ p_eglQuerySurface(dpy,surf,EGL_WIDTH_,&sw); p_eglQuerySurface(dpy,surf,EGL_HEIGHT_,&sh); }
    GLint_ vp[4]={0,0,0,0}, fbo=0, rfbo=0;
    if(p_glGetIntegerv){ p_glGetIntegerv(GL_VIEWPORT_,vp); p_glGetIntegerv(GL_FRAMEBUFFER_BINDING_,&fbo); p_glGetIntegerv(GL_READ_FRAMEBUFFER_BINDING_,&rfbo); }
    int w=sw>0?sw:vp[2], h=sh>0?sh:vp[3];
    if(w<=0||h<=0||w>4096||h>4096){ probe_log("seq%d: surf=%dx%d viewport=(%d,%d,%d,%d) drawFBO=%d readFBO=%d -> unusable dims, no readback",
        g_probe_seq,sw,sh,vp[0],vp[1],vp[2],vp[3],fbo,rfbo); g_probe_seq++; g_probe_left--; return; }
    probe_log("seq%d: surf=%dx%d viewport=(%d,%d,%d,%d) drawFBO=%d readFBO=%d -> reading %dx%d RGBA from readFBO",
        g_probe_seq,sw,sh,vp[0],vp[1],vp[2],vp[3],fbo,rfbo,w,h);
    uint8_t* buf=(uint8_t*)malloc((size_t)w*h*4); if(!buf){ g_probe_seq++; g_probe_left--; return; }
    GLint_ oldAlign=4; if(p_glGetIntegerv) p_glGetIntegerv(GL_PACK_ALIGNMENT_,&oldAlign);
    if(p_glPixelStorei) p_glPixelStorei(GL_PACK_ALIGNMENT_,1);
    if(p_glGetError) p_glGetError();                                               // clear prior error
    if(p_glReadPixels) p_glReadPixels(0,0,w,h,GL_RGBA_,GL_UNSIGNED_BYTE_,buf);
    GLenum_ err=p_glGetError?p_glGetError():0;
    if(p_glPixelStorei) p_glPixelStorei(GL_PACK_ALIGNMENT_,oldAlign);              // restore state we touched
    if(err){ probe_log("seq%d: glReadPixels GL error 0x%x (readFBO=%d may be unreadable)",g_probe_seq,err,rfbo); free(buf); g_probe_seq++; g_probe_left--; return; }
    FrameJob* j=(FrameJob*)malloc(sizeof(FrameJob)); if(!j){ free(buf); g_probe_seq++; g_probe_left--; return; }
    j->buf=buf; j->w=w; j->h=h; j->fbo=rfbo; j->seq=g_probe_seq;
    pthread_t th; pthread_attr_t a; pthread_attr_init(&a); pthread_attr_setdetachstate(&a,PTHREAD_CREATE_DETACHED);
    pthread_create(&th,&a,probe_writer,j); pthread_attr_destroy(&a);
    g_probe_seq++; g_probe_left--;
    if(g_probe_left<=0){ g_probe_armed=0; probe_log("burst done: %d frames captured; probe disarmed",g_probe_seq); }
}
static EGLBoolean_ repl_eglSwap(EGLDisplay_ dpy, EGLSurface_ surf){
    struct timespec ts; clock_gettime(CLOCK_MONOTONIC,&ts); double now=ts.tv_sec*1000.0+ts.tv_nsec/1e6;
    if(g_probe_lastT>0 && !g_probe_baselined && !(g_probe_armed&&g_probe_left>0)){ g_probe_dtSum+=now-g_probe_lastT; g_probe_dtN++;
        if(g_probe_dtN==120){ g_probe_baselined=true; probe_log("baseline: %.2f ms/swap (%.1f fps) over 120 swaps",g_probe_dtSum/120.0,1000.0/(g_probe_dtSum/120.0)); } }
    g_probe_lastT=now;
    if(g_probe_armed && g_probe_left>0){ probe_capture(dpy,surf);
        clock_gettime(CLOCK_MONOTONIC,&ts); double t1=ts.tv_sec*1000.0+ts.tv_nsec/1e6;
        probe_log("seq%d: capture cost %.2f ms on the render thread (CPU readback; NOT the eventual GPU->encoder path)",g_probe_seq-1,t1-now); }
    return orig_eglSwap(dpy,surf);
}
static void probe_try_install(){
    if(g_probe_hooked) return;
    void* f=dlsym(RTLD_DEFAULT,"eglSwapBuffers"); if(!f){ probe_log("eglSwapBuffers not resolvable yet; will retry"); return; }
    p_eglQuerySurface=(EGLBoolean_(*)(EGLDisplay_,EGLSurface_,EGLint_,EGLint_*))dlsym(RTLD_DEFAULT,"eglQuerySurface");
    p_glGetIntegerv=(void(*)(GLenum_,GLint_*))dlsym(RTLD_DEFAULT,"glGetIntegerv");
    p_glReadPixels=(void(*)(GLint_,GLint_,GLsizei_,GLsizei_,GLenum_,GLenum_,void*))dlsym(RTLD_DEFAULT,"glReadPixels");
    p_glPixelStorei=(void(*)(GLenum_,GLint_))dlsym(RTLD_DEFAULT,"glPixelStorei");
    p_glGetError=(GLenum_(*)(void))dlsym(RTLD_DEFAULT,"glGetError");
    char dir[600]; snprintf(dir,sizeof dir,"%s/probe",OUTDIR); mkdir(dir,0777);
    A64HookFunction(f,(void*)repl_eglSwap,(void**)&orig_eglSwap); g_probe_hooked=true;
    probe_log("eglSwapBuffers hooked @%p (orig=%p); gl: query=%p getiv=%p read=%p store=%p err=%p -- touch tribemod/capture_now to grab 4 frames",
        f,(void*)orig_eglSwap,(void*)p_eglQuerySurface,(void*)p_glGetIntegerv,(void*)p_glReadPixels,(void*)p_glPixelStorei,(void*)p_glGetError);
}
// ============ GL FBO/viewport locator probe (flag tribemod/fbo_probe) -- READ-ONLY, logcat only ============
// eglSwapBuffers carries nothing (frames go to the OpenXR swapchain), so locate the eye render targets directly:
// hook glBindFramebuffer + glViewport and log DISTINCT fbo ids and render sizes with counts. No GL state change,
// no texture binding, no readback -- only records the args. The eye target is the fbo that gets eye-res viewports.
static void (*orig_glBindFramebuffer)(GLenum_,GLenum_)=0;
static void (*orig_glViewport)(GLint_,GLint_,GLsizei_,GLsizei_)=0;
static bool g_fbo_hooked=false;
static int  g_fboIds[48], g_fboCnt[48], g_fboN=0;
static int  g_vpW[48], g_vpH[48], g_vpFbo[48], g_vpCnt[48], g_vpN=0;
static int  g_fboLast=0; static long g_fboBinds=0;
static void fbo_dump(){
    char b[900]; size_t n=0;
    n+=snprintf(b+n,sizeof b-n,"FBOs(bind#%ld):",g_fboBinds);
    for(int i=0;i<g_fboN && n<sizeof b-24;i++) n+=snprintf(b+n,sizeof b-n," id%d:%d",g_fboIds[i],g_fboCnt[i]);
    LOGI("[FBO] %s",b);
    n=0; n+=snprintf(b+n,sizeof b-n,"viewports:");
    for(int i=0;i<g_vpN && n<sizeof b-32;i++) n+=snprintf(b+n,sizeof b-n," %dx%d@fbo%d:%d",g_vpW[i],g_vpH[i],g_vpFbo[i],g_vpCnt[i]);
    LOGI("[FBO] %s",b);
}
static void repl_glBindFramebuffer(GLenum_ target, GLenum_ fb){
    orig_glBindFramebuffer(target,fb);
    g_fboBinds++; int f=(int)fb; int i;
    for(i=0;i<g_fboN;i++) if(g_fboIds[i]==f){ g_fboCnt[i]++; break; }
    if(i==g_fboN && g_fboN<48){ g_fboIds[g_fboN]=f; g_fboCnt[g_fboN]=1; g_fboN++; LOGI("[FBO] new FBO id=%d (bind#%ld)",f,g_fboBinds); }
    g_fboLast=f;
    if((g_fboBinds % 1800)==0) fbo_dump();
}
static void repl_glViewport(GLint_ x,GLint_ y,GLsizei_ w,GLsizei_ h){
    orig_glViewport(x,y,w,h); int i;
    for(i=0;i<g_vpN;i++) if(g_vpW[i]==(int)w && g_vpH[i]==(int)h && g_vpFbo[i]==g_fboLast){ g_vpCnt[i]++; break; }
    if(i==g_vpN && g_vpN<48){ g_vpW[g_vpN]=(int)w; g_vpH[g_vpN]=(int)h; g_vpFbo[g_vpN]=g_fboLast; g_vpCnt[g_vpN]=1; g_vpN++;
        LOGI("[FBO] new viewport %dx%d @fbo%d (bind#%ld)",(int)w,(int)h,g_fboLast,g_fboBinds); }
}
static void fbo_try_install(){
    if(g_fbo_hooked) return;
    void* b=dlsym(RTLD_DEFAULT,"glBindFramebuffer"); void* v=dlsym(RTLD_DEFAULT,"glViewport");
    if(!b||!v){ LOGI("[FBO] glBindFramebuffer/glViewport not resolvable yet (b=%p v=%p)",b,v); return; }
    A64HookFunction(b,(void*)repl_glBindFramebuffer,(void**)&orig_glBindFramebuffer);
    A64HookFunction(v,(void*)repl_glViewport,(void**)&orig_glViewport);
    g_fbo_hooked=true;
    LOGI("[FBO] hooked glBindFramebuffer=%p glViewport=%p -- logging distinct FBOs + render sizes",b,v);
}
// ============ Stream-camera probe (flag tribemod/cam_probe) -- READ-ONLY, poll thread ============
// Go Live streams Tribe's SELECTED camera (user: usually the selfie stick) = a SceneCaptureComponent2D drawing into a
// UTextureRenderTarget2D. Resolve BP_SelfieStick_C -> CaptureComponent2D -> TextureTarget by reflection and log the RT's
// path/size/format + capture settings, plus /Game/Environment/SpectatorRenderTarget. Names resolve at runtime, so a wrong
// name logs -1 instead of misreading. Logs only on change.
static void cam_log_rt(const char* label, uintptr_t rt){
    if(!rt){ LOGI("[CAM] %s: TextureTarget=(null)",label); return; }
    char fp[400], cn[128]; full_path(rt,fp,sizeof fp); class_name(rt,cn,sizeof cn);
    uintptr_t cls=rdptr(rt+OFF_Class);
    int oX=prop_offset(cls,"SizeX",0), oY=prop_offset(cls,"SizeY",0), oF=prop_offset(cls,"RenderTargetFormat",0);
    LOGI("[CAM] %s: RT=%s (%s) @0x%lx size=%dx%d fmt=%d",label,fp,cn,(unsigned long)rt,
        oX>=0?(int)rd32(rt+oX):-1, oY>=0?(int)rd32(rt+oY):-1, oF>=0?(int)(rd32(rt+oF)&0xff):-1);
}
static void cam_probe_tick(){
    static uintptr_t lastStick=1, lastRT=1; static bool specDone=false;
    uintptr_t st=find_live_class_sub("BP_SelfieStick_C"), cap=0, rt=0;
    if(st){ uintptr_t scls=rdptr(st+OFF_Class); int oc=prop_offset(scls,"CaptureComponent2D",0); cap=oc>=0?rdptr(st+oc):0;
        if(cap){ uintptr_t ccls=rdptr(cap+OFF_Class); int ot=prop_offset(ccls,"TextureTarget",0); rt=ot>=0?rdptr(cap+ot):0; } }
    if(st!=lastStick || rt!=lastRT){
        if(!st) LOGI("[CAM] selfie stick: not in level yet (take it out / open the camera to spawn it)");
        else if(!cap) LOGI("[CAM] selfie stick @0x%lx: CaptureComponent2D unresolved",(unsigned long)st);
        else { uintptr_t ccls=rdptr(cap+OFF_Class); char cn[128]; class_name(cap,cn,sizeof cn);
            int ob=prop_offset(ccls,"bCaptureEveryFrame",0), om=prop_offset(ccls,"bCaptureOnMovement",0), os=prop_offset(ccls,"CaptureSource",0);
            LOGI("[CAM] selfie stick @0x%lx comp=%s @0x%lx everyFrameByte=0x%02x onMoveByte=0x%02x CaptureSource=%d",
                (unsigned long)st,cn,(unsigned long)cap, ob>=0?(rd32(cap+ob)&0xff):0xff, om>=0?(rd32(cap+om)&0xff):0xff,
                os>=0?(int)(rd32(cap+os)&0xff):-1);
            cam_log_rt("selfie",rt); }
        lastStick=st; lastRT=rt; }
    if(!specDone){ uintptr_t sp=find_by_path("/Game/Environment/SpectatorRenderTarget.SpectatorRenderTarget",0);
        if(sp){ cam_log_rt("SpectatorRenderTarget",sp); specDone=true; } }
}
// ---- drone camera: poll-thread side (resolve Tribe's auto-cam, liveness, params, one-time enum dump) ----
static void drone_dump_enum_once(){
    static bool done=false; if(done) return;
    uintptr_t e=find_by_path("/Script/TribeXR.EAutoCamMode",0); if(!e) return;
    uintptr_t d; int n=enum_entries(e,&d); char nm[96]; int64_t v;
    for(int i=0;i<n;i++) if(enum_entry(d,i,nm,sizeof nm,&v)) LOGI("[DRONE] EAutoCamMode %s = %lld",nm,(long long)v);
    done=true; }
static void drone_read_params(){       // tribemod/drone.txt: key=value, e.g. "target=selfie radius=300 speed=12"
    char p[600]; snprintf(p,sizeof p,"%s/drone.txt",OUTDIR); FILE* f=fopen(p,"r");
    double r=g_dR,h=g_dH,s=g_dSpeed,l=g_dLook,b=g_dBob; int tgt=0, rset=0, hset=0; char k[32], v[32];
    if(f){ while(fscanf(f," %31[^= \t\r\n]=%31s",k,v)==2){ double x=strtod(v,0);
            if(!strcmp(k,"radius")){ r=x; rset=1; } else if(!strcmp(k,"height")){ h=x; hset=1; } else if(!strcmp(k,"speed")) s=x;
            else if(!strcmp(k,"look")) l=x; else if(!strcmp(k,"bob")) b=x; else if(!strcmp(k,"target")) tgt=!strcmp(v,"auto")?1:0; }
        fclose(f); }
    if(r<50) r=50; if(r>2000) r=2000; if(h<-200) h=-200; if(h>600) h=600; if(s<-90) s=-90; if(s>90) s=90;
    if(l<-300) l=-300; if(l>300) l=300; if(b<0) b=0; if(b>200) b=200;
    if(r!=g_dR||h!=g_dH||s!=g_dSpeed||l!=g_dLook||b!=g_dBob||tgt!=g_droneTarget||rset!=g_dRset||hset!=g_dHset){
        g_dR=r; g_dH=h; g_dSpeed=s; g_dLook=l; g_dBob=b; g_droneTarget=tgt; g_dRset=rset; g_dHset=hset;
        LOGI("[DRONE] params target=%s radius=%s height=%s speed=%.1f look=%.0f bob=%.0f",tgt?"auto":"selfie",
            rset?"set":"from stick",hset?"set":"from stick",s,l,b); } }
// one-time: log the live controller's reflected auto-cam/spectator/beat properties + the raw decompiled block 0x970..0x980,
// so a headset run confirms the layout the drone's cut-park relies on.
static void drone_dump_pc_once(uintptr_t pc){
    static bool done=false; if(done||!pc) return; done=true;
    static const char* keys[]={"autocam","spectator","beat","bpm","tempo"};
    char nm[128],lo[128],ty[64],cn[96]; int n=0;
    for(uintptr_t c=rdptr(pc+OFF_Class); c && n<4000; c=rdptr(c+OFF_Super)){ obj_name(c,cn,sizeof cn);
        for(uintptr_t f=rdptr(c+OFF_ChildProps); f && n<4000; f=rdptr(f+FF_Next),n++){
            uint32_t off=rd32(f+FP_Offset); fname_resolve(rd32(f+FF_Name),nm,sizeof nm);
            int i=0; for(;nm[i]&&i<127;i++){ char ch=nm[i]; lo[i]=(ch>='A'&&ch<='Z')?(char)(ch+32):ch; } lo[i]=0;
            bool hit=(off>=0x960&&off<=0x990)||off==0x2d0;
            for(unsigned k=0;!hit&&k<sizeof keys/sizeof keys[0];k++) if(strstr(lo,keys[k])) hit=true;
            if(!hit) continue;
            ffield_type(f,ty,sizeof ty); uint32_t r=rd32(pc+off); float fv; memcpy(&fv,&r,4);
            LOGI("[DRONE] pc %s.%s (%s) @0x%x raw=0x%08x float=%.3f",cn,nm,ty,off,r,fv); } }
    for(uint32_t o=0x970;o<=0x980;o+=4){ uint32_t r=rd32(pc+o); float fv; memcpy(&fv,&r,4);
        LOGI("[DRONE] pc raw +0x%x = 0x%08x (float %.3f)",o,r,fv); } }
static void drone_poll(){
    static int capTgt=-1;
    bool on=file_present("drone_cam");
    if(on) drone_read_params();
    int tgt=g_droneTarget;
    if(g_droneCap && (obj_at(rd32(g_droneCap+OFF_Index))!=g_droneCap || capTgt!=tgt)){   // gone (room change) or target switched
        g_droneOn=0; g_droneCap=0; LOGI("[DRONE] camera changed (gone or new target); re-resolving"); }
    if(g_dronePC && obj_at(rd32(g_dronePC+OFF_Index))!=g_dronePC) g_dronePC=0;
    if(on){
        if(!g_fnSetWorldLR) g_fnSetWorldLR=find_by_path("/Script/Engine.SceneComponent.K2_SetWorldLocationAndRotation",0);
        if(!g_fnSetRelLR)   g_fnSetRelLR  =find_by_path("/Script/Engine.SceneComponent.K2_SetRelativeLocationAndRotation",0);
        if(g_offRelLoc<0||g_offRelRot<0){ uintptr_t sc=find_by_path("/Script/Engine.SceneComponent",1);   // mount pose (also set by a2)
            if(sc){ g_offRelLoc=prop_offset(sc,"RelativeLocation",0); g_offRelRot=prop_offset(sc,"RelativeRotation",0); } }
        if(!g_droneCap){
            if(tgt==0){ uintptr_t st=find_live_class_sub("BP_SelfieStick_C");
                if(st){ int oc=prop_offset(rdptr(st+OFF_Class),"CaptureComponent2D",0); g_droneCap=oc>=0?rdptr(st+oc):0; } }
            else g_droneCap=find_live("NewSceneCaptureComponent2D","SceneCaptureComponent2D","SpectatorCameraAutoCam");
            capTgt=tgt;
            LOGI("[DRONE] resolve (%s): capture=0x%lx setWorld=0x%lx setRel=0x%lx relLoc@%d relRot@%d%s",tgt?"Auto cam":"selfie stick",
                (unsigned long)g_droneCap,(unsigned long)g_fnSetWorldLR,(unsigned long)g_fnSetRelLR,g_offRelLoc,g_offRelRot,
                g_droneCap?"":(tgt?"  (Auto cam not found)":"  (take the selfie stick out)"));
            drone_dump_enum_once(); }
        if(tgt==1 && !g_dronePC){ g_dronePC=find_live_class_sub("TribePlayerControllerBP_C");
            LOGI("[DRONE] player controller=0x%lx",(unsigned long)g_dronePC); drone_dump_pc_once(g_dronePC); } }
    int want=(on&&g_droneCap&&g_fnSetWorldLR)?1:0;
    if(want!=g_droneOn){ g_droneOn=want; LOGI("[DRONE] %s",want?(tgt?"ON: flying the Auto cam (select the Auto angle)":
        "ON: flying the selfie-stick camera"):"OFF"); } }
// poll thread: resolve A2 (retarget) functions/offsets/enums + load this rig's saved calibration
static void a2_resolve(){
    g_fnNumBones  =find_by_path("/Script/Engine.SkinnedMeshComponent.GetNumBones",0);
    g_fnBoneName  =find_by_path("/Script/Engine.SkinnedMeshComponent.GetBoneName",0);
    g_fnParentBone=find_by_path("/Script/Engine.SkinnedMeshComponent.GetParentBone",0);
    g_fnRefPose   =find_by_path("/Script/Engine.SkinnedMeshComponent.GetRefPoseTransform",0);
    g_fnHideBone  =find_by_path("/Script/Engine.SkinnedMeshComponent.HideBoneByName",0);
    g_fnSetSkinned=find_by_path("/Script/Engine.SkinnedMeshComponent.SetSkinnedAssetAndUpdate",0);
    g_fnAddComp   =find_by_path("/Script/Engine.Actor.AddComponentByClass",0);
    g_fnSetOwner  =find_by_path("/Script/Engine.Actor.SetOwner",0);
    g_fnAttach    =find_by_path("/Script/Engine.SceneComponent.K2_AttachToComponent",0);
    g_fnRelScale  =find_by_path("/Script/Engine.SceneComponent.SetRelativeScale3D",0);
    g_fnAttachParent=find_by_path("/Script/Engine.SceneComponent.GetAttachParent",0);
    g_fnSetBoneXf =find_by_path("/Script/Engine.PoseableMeshComponent.SetBoneTransformByName",0);
    g_fnOnlyOwnerSee=find_by_path("/Script/Engine.PrimitiveComponent.SetOnlyOwnerSee",0);
    g_fnTickGroup =find_by_path("/Script/Engine.ActorComponent.SetTickGroup",0);
    g_fnColl2     =find_by_path("/Script/Engine.PrimitiveComponent.SetCollisionEnabled",0);
    g_fnShad2     =find_by_path("/Script/Engine.PrimitiveComponent.SetCastShadow",0);
    g_poseCls     =find_by_path("/Script/Engine.PoseableMeshComponent",1);
    uintptr_t sc=find_by_path("/Script/Engine.SceneComponent",1);
    g_offRelLoc=sc?prop_offset(sc,"RelativeLocation",0):-1; g_offRelRot=sc?prop_offset(sc,"RelativeRotation",0):-1;
    g_attSnap   =enum_value("/Script/Engine.EAttachmentRule","SnapToTarget",2);
    g_attKeepRel=enum_value("/Script/Engine.EAttachmentRule","KeepRelative",0);
    g_boneCS    =enum_value("/Script/Engine.EBoneSpaces","ComponentSpace",1);
    uintptr_t ws=find_live_class_sub("WorldSettings"); float w2m=-1;               // advisor: pass the world's WorldToMeters
    if(ws){ int o=prop_offset(rdptr(ws+OFF_Class),"WorldToMeters",0); if(o>=0) sr(ws+o,&w2m,4); if(w2m>=10&&w2m<=1000) g_w2m=w2m; }
    g_noSplit=file_present("bt_nosplit");
    if(file_present("a2_inflight")){ char p[600]; snprintf(p,sizeof p,"%s/a2_inflight",OUTDIR); unlink(p); g_a2Fail=true;
        load_status("A2: the previous launch died while going live -> retarget DISABLED this launch (auto-retries next launch)"); }
    g_fnDestroyComp=find_by_path("/Script/Engine.ActorComponent.K2_DestroyComponent",0);
    g_fnUnhideBone=find_by_path("/Script/Engine.SkinnedMeshComponent.UnHideBoneByName",0);
    g_hmdLib    =find_by_path("/Script/OculusXRHMD.Default__OculusXRFunctionLibrary",0);
    g_fnGetBase =find_by_path("/Script/OculusXRHMD.OculusXRFunctionLibrary.GetBaseRotationAndBaseOffsetInMeters",0);
    load_status("A2 resolve: align hmdLib=0x%lx getBase=0x%lx",(unsigned long)g_hmdLib,(unsigned long)g_fnGetBase);
    g_inLib     =find_by_path("/Script/OculusXRInput.Default__OculusXRInputFunctionLibrary",0);
    g_fnHandValid=find_by_path("/Script/OculusXRInput.OculusXRInputFunctionLibrary.IsHandPositionValid",0);
    g_fnHandConf =find_by_path("/Script/OculusXRInput.OculusXRInputFunctionLibrary.GetTrackingConfidence",0);
    g_handType[0]=enum_value("/Script/OculusXRInput.EOculusXRHandType","HandLeft",1);
    g_handType[1]=enum_value("/Script/OculusXRInput.EOculusXRHandType","HandRight",2);
    g_confHigh   =enum_value("/Script/OculusXRInput.EOculusXRTrackingConfidence","High",1);
    load_status("A2 resolve: hands unhide=0x%lx inputLib=0x%lx handValid=0x%lx handConf=0x%lx HandLeft=%lld HandRight=%lld High=%lld",
        (unsigned long)g_fnUnhideBone,(unsigned long)g_inLib,(unsigned long)g_fnHandValid,(unsigned long)g_fnHandConf,
        (long long)g_handType[0],(long long)g_handType[1],(long long)g_confHigh);
    snprintf(g_ucPath,sizeof g_ucPath,"%s/bt_user_calib.txt",OUTDIR);
    g_ucal=a2_load_ucal();
    load_status("A2 resolve: bones(num=0x%lx name=0x%lx parent=0x%lx refpose=0x%lx hide=0x%lx) setSkinned=0x%lx addComp=0x%lx setOwner=0x%lx attach=0x%lx relScale=0x%lx attachParent=0x%lx",
        (unsigned long)g_fnNumBones,(unsigned long)g_fnBoneName,(unsigned long)g_fnParentBone,(unsigned long)g_fnRefPose,(unsigned long)g_fnHideBone,
        (unsigned long)g_fnSetSkinned,(unsigned long)g_fnAddComp,(unsigned long)g_fnSetOwner,(unsigned long)g_fnAttach,(unsigned long)g_fnRelScale,(unsigned long)g_fnAttachParent);
    load_status("A2 resolve: setBoneXf=0x%lx poseCls=0x%lx onlyOwnerSee=0x%lx tickGroup=0x%lx coll=0x%lx shadow=0x%lx RelLoc@0x%x RelRot@0x%x Snap=%lld KeepRel=%lld CompSpace=%lld WorldToMeters=%.1f (using %.1f) nosplit=%d",
        (unsigned long)g_fnSetBoneXf,(unsigned long)g_poseCls,(unsigned long)g_fnOnlyOwnerSee,(unsigned long)g_fnTickGroup,(unsigned long)g_fnColl2,(unsigned long)g_fnShad2,
        g_offRelLoc,g_offRelRot,(long long)g_attSnap,(long long)g_attKeepRel,(long long)g_boneCS,w2m,g_w2m,(int)g_noSplit);
    load_status("A2 resolve: destroyComp=0x%lx; your calibration %s -> %s",(unsigned long)g_fnDestroyComp,g_ucPath,
        g_ucal?"LOADED (every skin works without a pose)":"none yet (stand still once with straight arms, T or A)");
}
static void* dump_thread(void*){
    LOGI("dumper thread up; base=0x%lx; poll %s/dump_now",(unsigned long)g_base,OUTDIR);
    char cmd[600]; snprintf(cmd,sizeof cmd,"%s/dump_now",OUTDIR);
    char lcmd[600]; snprintf(lcmd,sizeof lcmd,"%s/load_avatar",OUTDIR);
    bool auto_done=false; int tick=0;
    for(;;){ g_log_pe = file_present("log_pe")?1:0;               // toggle the ProcessEvent diagnostic
        int fd=open(cmd,O_RDONLY); if(fd>=0){ close(fd); unlink(cmd); LOGI("dump_now seen; dumping...");
        install_guard(); do_dump(); remove_guard(); }
        // manual load_avatar trigger: resolve globals here (heavy scan, off the game thread), then arm the PE-drain.
        int lf=open(lcmd,O_RDONLY); if(lf>=0){ close(lf); unlink(lcmd); LOGI("load_avatar seen; arming executor...");
            ensure_resolved(); if(g_resolved && orig_pe){ g_load_req=1; load_status("armed; waiting for next ProcessEvent on game thread"); }
            else load_status("NOT armed (resolved=%d pe=%p)",(int)g_resolved,g_pe_addr); }
        // AUTO-load once per launch: when tribemod/auto_load exists, wait for the live pawn body, then arm.
        // Checked every ~2s; the heavy find_live scan runs on THIS background thread, not the game thread.
        if(!auto_done && orig_pe && ((++tick & 3)==0) && file_present("auto_load")){
            ensure_resolved();
            if(g_resolved){ refresh_numelements(); uintptr_t body=find_live("AvatarBodyMesh","SkeletalMeshComponent","ReadyPlayerMeComponent");
                if(body){ g_load_req=1; auto_done=true; load_status("auto-load: pawn ready (body=0x%lx numel=%u) -> armed",(unsigned long)body,g_numElements); } } }
        // ISO trigger: tribemod/iso_here (one-shot) -> spawn our own actor in front of the HMD on the game thread.
        { char ip[600]; snprintf(ip,sizeof ip,"%s/iso_here",OUTDIR); int fi=open(ip,O_RDONLY);
          if(fi>=0){ close(fi); unlink(ip); if(g_mymesh){ g_iso_req=1; load_status("iso_here seen -> spawning our actor"); } else load_status("iso_here: no mesh loaded yet"); } }
        // AUTO avatar actor: once per launch, ~2 s after the mesh loads, if tribemod/auto_actor exists -> spawn + follow.
        { static int aa=-1; if(aa==-1 && g_loaded_once && g_mymesh && !g_isoActor && file_present("auto_actor")) aa=4;
          if(aa>0 && --aa==0){ g_iso_req=1; load_status("auto_actor: spawning our following avatar"); } }
        // ROUTE A body tracking (flag tribemod/body_tracking): ~3 s after the world is up, resolve HERE (heavy scans stay off
        // the game thread), then start + poll on the game thread: +1 s, +3 s, +10 s, then every 30 s (24 polls max).
        { static int bt=-1, pt=0;
          if(bt==-1 && orig_pe && (g_loaded_once||auto_done) && file_present("body_tracking")) bt=6;
          if(bt>0 && --bt==0){ if(bt_resolve()){ a2_resolve(); g_bt_req=1; load_status("BT: armed; starting on the game thread"); } else load_status("BT: resolve failed; not started"); }
          { char rp[600]; snprintf(rp,sizeof rp,"%s/bt_recalibrate",OUTDIR); int fr=open(rp,O_RDONLY);     // one-shot: redo the T-pose
            if(fr>=0){ close(fr); unlink(rp); if(g_ucPath[0]) unlink(g_ucPath); g_a2Recal=1; load_status("A2: bt_recalibrate seen -> your calibration deleted; stand still with straight arms once"); } }
          if(file_present("bt_calibrate_now")){ char cp[600]; snprintf(cp,sizeof cp,"%s/bt_calibrate_now",OUTDIR); unlink(cp); g_a2CalNow=1; }  // manual capture
          if(file_present("next_skin")){ char np2[600]; snprintf(np2,sizeof np2,"%s/next_skin",OUTDIR); unlink(np2);            // remote skin switch
            if(g_loaded_once&&orig_pe){ advance_skin(); g_load_req=1; } else load_status("next_skin: no skin loaded yet"); }
          if(g_bt_started && g_btPolls<24){ pt++; if(pt==2||pt==6||pt==20||(pt>=60&&pt%60==0)) g_bt_poll_req=1; } }
        // GLES capture probe: install the eglSwapBuffers hook when tribemod/capture_probe exists; one-shot 4-frame burst
        // when tribemod/capture_now appears (so you can first open the selfie/spectator cam to show the avatar).
        if(file_present("capture_probe") && !g_probe_hooked) probe_try_install();
        if(g_probe_hooked && file_present("capture_now")){ char cn[600]; snprintf(cn,sizeof cn,"%s/capture_now",OUTDIR); unlink(cn);
            g_probe_seq=0; g_probe_left=4; g_probe_armed=1; probe_log("capture_now -> arming a 4-frame burst"); }
        // GL FBO/viewport locator: install when tribemod/fbo_probe exists (finds eye render targets; eglSwapBuffers is empty)
        if(file_present("fbo_probe") && !g_fbo_hooked) fbo_try_install();
        // Stream-camera probe: resolve the selfie stick's capture render target (what Go Live streams). Every ~10 ticks
        // because each pass scans the object array.
        { static int ctk=0; if(file_present("cam_probe") && (++ctk % 10)==0) cam_probe_tick(); }
        // Drone cam: resolve/validate Tribe's auto-cam + read drone.txt every ~4 ticks; the game-thread tick flies it.
        { static int dtk=0; if((++dtk % 4)==0) drone_poll(); }
        // RENDER report schedule: first at ~3s after attach, then every ~10s, up to 8 reports (drained on the game thread).
        if(g_report_ticks>0 && --g_report_ticks==0){ if(g_reports<8){ g_report_req=1; g_report_ticks=20; } }
        // KEEPER (~1s): if Tribe reset our body natively (bypassing the PE blocker), request a re-attach on the game thread.
        static int ktick=0;
        if(g_keep && g_body && g_mymesh && ((++ktick & 1)==0)){
            char cn[64]; class_name(g_body,cn,sizeof cn);
            if(strcmp(cn,"SkeletalMeshComponent")!=0){ g_keep=0; load_status("keeper: body gone (class='%s') -> keeper OFF",cn); }
            else { uintptr_t cur=rdptr(g_body+SMC_MESH_OFF);
                if(cur!=g_mymesh){ g_resets_native++;
                    if(g_resets_native<=20||(g_resets_native%50)==0) load_status("NATIVE reset of body (cur=0x%lx) #%d -> re-attach",(unsigned long)cur,g_resets_native);
                    g_reattach_req=1; } } }
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
    // Phase 3: install the ProcessEvent hook (game-thread drain point for the direct-load executor).
    // Runtime PE = base + Ghidra_rva + skew (calibrated 0x1000). Installed but INERT until load_avatar arms g_load_req.
    // SAFETY: only install if tribemod/executor_on exists (PE is a hot path); remove the flag + relaunch = clean/no-hook.
    { char ef[600]; snprintf(ef,sizeof ef,"%s/executor_on",OUTDIR); int e=open(ef,O_RDONLY);
      if(e>=0){ close(e); uintptr_t pe=g_base+RVA_PE_GHIDRA+PE_SKEW; uint32_t w0;
        bool prol=sr(pe,&w0,4) && ((w0&0xFF000000)==0xA9000000 || (w0&0xFFC00000)==0xD1000000); // stp/sub-sp prologue guard
        if(prol){ g_pe_addr=(void*)pe; A64HookFunction(g_pe_addr,(void*)repl_pe,(void**)&orig_pe);
            LOGI("ProcessEvent hook installed @%p (orig=%p)",g_pe_addr,(void*)orig_pe); }
        else LOGI("ProcessEvent @%p NOT a prologue (w=0x%08x); hook SKIPPED",(void*)pe,w0); }
      else LOGI("executor_on absent; PE hook not installed (safe mode)"); }
}
