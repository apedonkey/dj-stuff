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

    if(g_sc){ fprintf(g_sc,"\nTOTAL FAILS=%d\n",g_fails); fclose(g_sc); g_sc=0; }
    FILE* d=fopen(op(g_fails?"FAIL":"DONE"),"w"); if(d){ fprintf(d,"fails=%d\n",g_fails); fclose(d); }
    LOGI("dump complete, fails=%d",g_fails);
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
    for(int i=0;i<100 && !g_base;i++){ g_base=find_lib_base("libUnreal.so"); if(!g_base) usleep(50*1000); }
    if(!g_base){ LOGI("FAILED to find libUnreal.so base"); return; }
    // ensure outdir exists (app-writable external files dir)
    char mk[600]; snprintf(mk,sizeof mk,"%s",OUTDIR); mkdir(mk,0777);
    pthread_attr_t a; pthread_attr_init(&a); pthread_attr_setstacksize(&a,8*1024*1024); pthread_attr_setdetachstate(&a,PTHREAD_CREATE_DETACHED);
    pthread_t th; pthread_create(&th,&a,dump_thread,nullptr); pthread_attr_destroy(&a);
    LOGI("dumper thread spawned (base=0x%lx)",(unsigned long)g_base);
}
