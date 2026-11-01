#include <time.h>
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
#include <cctype>
#include <dlfcn.h>
#include <sys/prctl.h>
#include "vendor/And64InlineHook.hpp"
static inline pid_t my_tid(){ return (pid_t)syscall(SYS_gettid); }

#define TAG "TRIBEMOD"
#define LOGI(...) __android_log_print(ANDROID_LOG_INFO, TAG, __VA_ARGS__)
// which build this is (claudedocs/mod_2311_plan.md): A = startup + crash fixes, B = A + characters, C = B + stages.
// Shown in the [READY] line and in ready_history.txt.
#define MOD2311_STEP "C"
static double mono_now(){ struct timespec ts; clock_gettime(CLOCK_MONOTONIC,&ts); return ts.tv_sec+ts.tv_nsec*1e-9; }

// ---- resolved statics (this session) ----
// Tribe 0.12.6 (2311; port 2026-10-31): runtime RVAs = the store lib's vaddr + 0x1000 (add_needed.py shifts every segment
// by one page; checked on the patched lib). 2304 had 0x07C632C0 / store 0x07CBADD0 / store 0x07AA59E8.
static const uintptr_t RVA_NamePool      = 0x0884D640; // FNamePool (.bss; store 0x0884C640)
static const uintptr_t RVA_GUObjectArray = 0x088A6150; // FUObjectArray (.bss; store 0x088A5150)
static const uintptr_t RVA_GUObj_GOTslot = 0x08679738; // data slot holding &GUObjectArray (store 0x08678738)

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

// [a, a+n) inside one readable + executable mapping, from a fresh read of /proc/self/maps into locals (mod2311: the
// constructor's hook checks use this, never the shared range table below)
static bool maps_rx(uintptr_t a,size_t n){
    FILE* f=fopen("/proc/self/maps","r"); if(!f) return false; char line[1024]; bool ok=false;
    while(fgets(line,sizeof line,f)){ uintptr_t lo,hi; char pm[8];
        if(sscanf(line,"%lx-%lx %4s",&lo,&hi,pm)!=3) continue;
        if(a>=lo&&a<hi){ ok=(pm[0]=='r'&&pm[2]=='x'&&a+n<=hi); break; } }
    fclose(f); return ok; }

// ---- readable-range cache from /proc/self/maps + SIGSEGV guard ----
// mod2311: several threads read through sr() at once (the poll thread, the game thread, the HTTP and freeze threads).
// The one shared table used to be emptied and refilled in place while others searched it, so a valid address could
// read as unmapped (claudedocs/mod_2311_load.md 2a: the likely cause of the 14:26 launch without a ProcessEvent hook).
// Now each rebuild fills one of four tables and publishes it; a reader checks the table's sequence number around its
// search and searches again if a rebuild touched it. A miss rebuilds the table unless another thread has published a
// newer one since the miss (then the search is simply repeated on it).
struct Range { uintptr_t lo, hi; };
struct RangeTab { volatile uint32_t seq; int n; Range r[4096]; };
static RangeTab g_rt[4]; static RangeTab* volatile g_rtCur=nullptr; static pthread_mutex_t g_rtLock=PTHREAD_MUTEX_INITIALIZER;
static volatile uint32_t g_rtGen=0;                                  // +1 per published table
static void load_maps_since(uint32_t gen) {                         // gen: g_rtGen when the caller's search missed
    pthread_mutex_lock(&g_rtLock);
    static int next=0;
    if(g_rtCur&&__atomic_load_n(&g_rtGen,__ATOMIC_ACQUIRE)!=gen){ pthread_mutex_unlock(&g_rtLock); return; }   // newer already
    FILE* f=fopen("/proc/self/maps","r"); if(!f){ pthread_mutex_unlock(&g_rtLock); return; }
    RangeTab* t=&g_rt[next]; next=(next+1)&3;                        // never the published one (that is next-1)
    __atomic_add_fetch(&t->seq,1u,__ATOMIC_ACQ_REL);                  // odd: being written
    int n=0; char line[1024];
    while (fgets(line,sizeof line,f) && n<4096){
        uintptr_t lo,hi; char perm[8];
        if (sscanf(line,"%lx-%lx %4s",&lo,&hi,perm)==3 && perm[0]=='r'){ t->r[n].lo=lo; t->r[n].hi=hi; n++; } }
    fclose(f); t->n=n;
    __atomic_add_fetch(&t->seq,1u,__ATOMIC_ACQ_REL);                  // even: complete
    __atomic_store_n(&g_rtCur,t,__ATOMIC_RELEASE); __atomic_add_fetch(&g_rtGen,1u,__ATOMIC_ACQ_REL);
    pthread_mutex_unlock(&g_rtLock);
}
static void load_maps(){ load_maps_since(__atomic_load_n(&g_rtGen,__ATOMIC_ACQUIRE)); }   // an explicit refresh
// /proc/self/maps is address-sorted & non-overlapping -> binary search (O(log n) per read).
static bool in_range(uintptr_t p, size_t n){
    for(int tries=0;tries<4;tries++){
        RangeTab* t=__atomic_load_n(&g_rtCur,__ATOMIC_ACQUIRE); if(!t) return false;
        uint32_t s0=__atomic_load_n(&t->seq,__ATOMIC_ACQUIRE); if(s0&1u) continue;
        int lo=0,hi=t->n-1; bool ok=false;
        while(lo<=hi){ int mid=(lo+hi)>>1; uintptr_t a=t->r[mid].lo, b=t->r[mid].hi;
            if(p<a) hi=mid-1; else if(p>=b) lo=mid+1; else { ok=(p+n<=b); break; } }
        __atomic_thread_fence(__ATOMIC_ACQUIRE);
        if(__atomic_load_n(&t->seq,__ATOMIC_ACQUIRE)==s0) return ok; }
    return false; }

// SIGSEGV/SIGBUS guard, one slot per thread (mod2311). The old guard had one jump buffer and one flag for every thread:
// a read on one thread could overwrite another thread's jump target or switch its guard off mid-read (levels doc 7). Now
// a fault inside sr()'s copy jumps back to that same thread's sr(); any other fault goes to the handler that was there
// before (Android's crash reporter). The handler is installed only while something asks for it (the dumps and the game
// thread's loads), counted, so two of them overlapping can't leave it installed or chain it to itself.
struct GuardSlot { volatile uintptr_t owner; volatile sig_atomic_t on; sigjmp_buf jb; };
#define GUARD_SLOTS 16
static GuardSlot g_gslot[GUARD_SLOTS];
static struct sigaction g_old_segv, g_old_bus; static int g_guardRefs=0; static pthread_mutex_t g_guardLock=PTHREAD_MUTEX_INITIALIZER;
static GuardSlot* guard_slot(){                     // this thread's slot (pthread_self: no system call)
    uintptr_t me=(uintptr_t)pthread_self();
    for(int i=0;i<GUARD_SLOTS;i++) if(g_gslot[i].owner==me) return &g_gslot[i];
    for(int i=0;i<GUARD_SLOTS;i++){ uintptr_t z=0;
        if(__atomic_compare_exchange_n(&g_gslot[i].owner,&z,me,false,__ATOMIC_ACQ_REL,__ATOMIC_ACQUIRE)) return &g_gslot[i]; }
    return nullptr; }
static void segv_chain(int sig,siginfo_t* si,void* uc){
    struct sigaction* o=(sig==SIGBUS)?&g_old_bus:&g_old_segv;
    if((o->sa_flags&SA_SIGINFO)&&o->sa_sigaction){ o->sa_sigaction(sig,si,uc); return; }
    if(o->sa_handler!=SIG_DFL&&o->sa_handler!=SIG_IGN&&o->sa_handler){ o->sa_handler(sig); return; }
    sigaction(sig,o,nullptr); }                      // no handler before ours: the default action, on the re-run fault
static void segv_handler(int sig,siginfo_t* si,void* uc){
    uintptr_t me=(uintptr_t)pthread_self();
    for(int i=0;i<GUARD_SLOTS;i++) if(g_gslot[i].owner==me&&g_gslot[i].on){ g_gslot[i].on=0; siglongjmp(g_gslot[i].jb,1); }
    segv_chain(sig,si,uc); }
static void install_guard(){ pthread_mutex_lock(&g_guardLock);
    if(g_guardRefs++==0){ struct sigaction sa,os,ob; memset(&sa,0,sizeof sa); sa.sa_sigaction=segv_handler; sa.sa_flags=SA_SIGINFO|SA_ONSTACK;
        sigaction(SIGSEGV,&sa,&os); sigaction(SIGBUS,&sa,&ob);
        if(os.sa_sigaction!=segv_handler) g_old_segv=os;
        if(ob.sa_sigaction!=segv_handler) g_old_bus=ob; }
    pthread_mutex_unlock(&g_guardLock); }
static void remove_guard(){ pthread_mutex_lock(&g_guardLock);
    if(g_guardRefs>0&&--g_guardRefs==0){ sigaction(SIGSEGV,&g_old_segv,nullptr); sigaction(SIGBUS,&g_old_bus,nullptr); }
    pthread_mutex_unlock(&g_guardLock); }

// safe typed reads (maps range-check, then a guarded copy; a recovered fault unblocks the signals the handler blocked)
static bool sr(uintptr_t p, void* out, size_t n){
    if(!p) return false;
    uint32_t gen=__atomic_load_n(&g_rtGen,__ATOMIC_ACQUIRE);
    if(!in_range(p,n)){ load_maps_since(gen); if(!in_range(p,n)) return false; }
    GuardSlot* g=guard_slot();
    if(!g||g->on){ memcpy(out,(void*)p,n); return true; }             // no free slot: the range check alone
    if(sigsetjmp(g->jb,0)){ sigset_t s; sigemptyset(&s); sigaddset(&s,SIGSEGV); sigaddset(&s,SIGBUS);
        pthread_sigmask(SIG_UNBLOCK,&s,nullptr); return false; }
    g->on=1; __atomic_signal_fence(__ATOMIC_SEQ_CST);
    memcpy(out,(void*)p,n);
    __atomic_signal_fence(__ATOMIC_SEQ_CST); g->on=0; return true;
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
// The engine's own "is this object dead" test (mod2311), as FWeakObjectPtr::Get does it in the 2311 library (store
// 0x1A366AC, disassembled: item flags (+8) & (*GUnreachableObjectFlag | Garbage 1<<21); item stride 0x14, serial +0x10).
// The flag's address is in the GOT slot store 0x8678A30 = runtime 0x8679A30 (its link-time target, store 0x87C9C00,
// holds 2 = ReachabilityFlag1, UE 5.4's starting value; it rotates among 1, 2 and 4 per GC). Checked by
// backup/mod2311_build/tools/verify_2311.py. Anything else read there -> Garbage alone.
static const uintptr_t RVA_GOT_GUnreachableFlag = 0x08679A30;
static uint32_t gc_dead_mask(){
    static uintptr_t p=0; static bool said=false;
    if(!p&&g_base){ uintptr_t v=0; memcpy(&v,(const void*)(g_base+RVA_GOT_GUnreachableFlag),8);   // libUnreal's own GOT: always mapped
        if(v>=g_base&&v<g_base+0x0C000000) p=v;
        if(!said){ said=true; LOGI("[OBJ] GUnreachableObjectFlag @ base+0x%lx%s",(unsigned long)(v-g_base),p?"":" (outside libUnreal: Garbage only)"); } }
    uint32_t f=p?*(volatile uint32_t*)p:0; return ((f==1||f==2||f==4)?f:0)|0x200000u; }

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
    // UE 5.4 FChunkedFixedUObjectArray: Objects@0, PreAllocatedObjects@8, MaxElements@0x10, NumElements@0x14,
    // MaxChunks@0x18, NumChunks@0x1C. Take NumElements at +0x14 first (even early, when it's still small): the old slide
    // could skip it and lock onto a constant 16384 further on (2026-10-06: nothing past 16384 objects was ever found).
    { uint32_t ne=rd32(A+0x14), nc=rd32(A+0x1C);
      if(ne>=1000&&ne<=5000000&&((ne+65535)/65536)==ncReal&&(nc==0||nc==ncReal)){
          g_chunks=Q; g_numElements=ne; g_numChunks=ncReal; g_ne_off=0x14; g_objarray=A-0x10; g_ne_addr=A+0x14; return true; } }
    for(uint32_t d=0x10; d<=0x1C; d+=4){ uint32_t ne=rd32(A+d);           // fallback slide, never past NumChunks
        if(ne<10000||ne>5000000) continue;
        if(((ne+65535)/65536)!=ncReal) continue;
        g_chunks=Q; g_numElements=ne; g_numChunks=ncReal; g_ne_off=d; g_objarray=A-0x10; g_ne_addr=A+d; return true; }
    return false;
}
// re-read the LIVE object count (it grows as the world/pawn spawn; find_* bound by g_numElements must track it)
static uintptr_t raw_item_obj(uint32_t idx){                         // the item's Object, NOT bounded by g_numElements
    uintptr_t chunk=rdptr(g_chunks+(uintptr_t)(idx>>16)*8); if(!chunk) return 0;
    return rdptr(chunk+(uintptr_t)(idx&0xFFFF)*ITEM_STRIDE); }
static void refresh_numelements(){ if(!g_ne_addr) return; uint32_t cur=rd32(g_ne_addr);
    if(cur>=1000 && cur<=5000000){ g_numElements=cur; g_numChunks=(cur+65535)/65536; }
    // self-heal: if a live object sits right past the count, the counter address is stale (see try_objects_field).
    // Re-read +0x14 from the array head; failing that, count the items directly.
    uintptr_t nx=raw_item_obj(g_numElements); if(!nx||!in_range(nx,0x30)||rd32(nx+OFF_Index)!=g_numElements) return;
    static int healed=0;
    uintptr_t A=g_objarray+0x10; uint32_t ne=rd32(A+0x14);
    if(ne>g_numElements&&ne<=5000000&&g_ne_off!=0x14){ g_ne_addr=A+0x14; g_ne_off=0x14; g_numElements=ne; g_numChunks=(ne+65535)/65536;
        if(healed++<5) LOGI("[R2] object count was stale: switched to NumElements@+0x14 = %u",ne); return; }
    uint32_t n=g_numElements; while(n<5000000){ uintptr_t o=raw_item_obj(n); if(!o||!in_range(o,0x30)) break; n++; }
    if(n>g_numElements){ if(healed++<5) LOGI("[R2] object count was stale (%u): counted %u live items",g_numElements,n);
        g_numElements=n; g_numChunks=(n+65535)/65536; } }
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
        if(hi<=g_base||lo>=g_base+0x0C000000) continue; if(lo<g_base) lo=g_base;   // 2311's .bss ends near +0x8BBB000
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
        if(hi<=g_base || lo>=g_base+0x0C000000) continue;        // within libUnreal image window (2311's pool: +0x884D640)
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
    FILE* f=fopen(p,"a"); if(f){ fprintf(f,"%s\n",msg); fclose(f); chmod(p,0666);} LOGI("[INI] %s",msg); }
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
    char m[300]; snprintf(m,sizeof m,"%s: %s (%d->%d bytes)",key,have?"SET":"DELETED",n,o); ini_status(m);   // (sizes only)
}
static void upsert_ini_key(const char* key, const char* value){ upsert_ini(INI_PATH,"[TribeAvatar]",key,value,false); }
// Route A (body tracking): the project setting Tribe never ticked. Only an ini layer can reach settings read during
// engine/XR init, which is before any code of ours can touch the CDO. Flag tribemod/body_tracking absent -> key deleted.
static const char* ENGINE_INI_PATH =
  "/data/data/com.TribeXR.TribeXR/files/UnrealGame/TribeXR/TribeXR/Saved/Config/Android/Engine.ini";
static int tribemod_state();                       // (with the hook install, below)
static bool ini_flag(const char* name){ char p[600]; snprintf(p,sizeof p,"%s/%s",OUTDIR,name); int fd=open(p,O_RDONLY); if(fd>=0) close(fd); return fd>=0; }
static void ini_url_cut(const char* url,char* out,int n){   // "https://host/<cut>": no avatar id or token in any log
    const char* s=strstr(url,"://"); const char* h=s?s+3:url; const char* e=strchr(h,'/');
    snprintf(out,n,"%.*s%.*s%s",s?(int)(s+3-url):0,url,e?(int)(e-h):(int)strlen(h),h,e?"/<cut>":""); }
static void ini_upsert(){
    // mod2311: when tribemod/ can't be read yet (the first launch after an install), every file reads as absent and the
    // edits below would delete keys (the RPM URL, body tracking). Leave both ini files as they are then.
    if(tribemod_state()<0){ LOGI("[INI] tribemod/ is not readable yet: both ini files left as they are this launch"); return; }
    // Tribe's Ready Player Me keys (mod2311 step B, claudedocs/mod_2311_plan.md 5): left as Tribe has them. The old route
    // wrote avatar_url.txt's URL (a dead http://127.0.0.1:8000 address) at every launch and deleted both keys without the
    // file. Now: tribemod/rpm_route_on = the old route exactly; rpm_url_set.txt (one line) = write that URL once, then the
    // file becomes rpm_url_set.done; rpm_url_clear = delete both keys once. URLs are logged cut to their host.
    char url[1024], etag[256], cut[200];
    if(ini_flag("rpm_route_on")){
        bool hu=read_trim_file("avatar_url.txt",url,sizeof url);
        bool he=read_trim_file("avatar_etag.txt",etag,sizeof etag);
        if(hu && (url[0]=='+'||url[0]=='-'||url[0]=='.'||url[0]=='!')){ ini_status("WARN url op-char; unset"); hu=false; }
        if(hu) stage_cache(url);            // cache slot => cache HIT (local glTF load, no network)
        // UE ini truncates an UNQUOTED value at "//" -> quote the URL (matches Tribe's own DataRouterUrl="...")
        char qurl[1100]; snprintf(qurl,sizeof qurl,"\"%s\"",url);
        upsert_ini_key("ReadyPlayerMeAvatarUrl", hu?qurl:0);
        upsert_ini_key("ReadyPlayerMeETag",      he?etag:0);   // ETag present => FUN_050f584c takes the cache-hit branch
        if(hu) ini_url_cut(url,cut,sizeof cut); char m[400]; snprintf(m,sizeof m,"rpm_route_on: url=%s etag=%s",hu?cut:"(none)",he?"(set)":"(none)"); ini_status(m); }
    else if(read_trim_file("rpm_url_set.txt",url,sizeof url)){
        char p[600],q[620]; snprintf(p,sizeof p,"%s/rpm_url_set.txt",OUTDIR); snprintf(q,sizeof q,"%s/rpm_url_set.done",OUTDIR);
        ini_url_cut(url,cut,sizeof cut);
        if(strncmp(url,"http://",7)&&strncmp(url,"https://",8)){ char m[300]; snprintf(m,sizeof m,"rpm_url_set.txt: not an http(s) URL (%s): nothing written",cut); ini_status(m); }
        else { char qurl[1100]; snprintf(qurl,sizeof qurl,"\"%s\"",url);
            upsert_ini_key("ReadyPlayerMeAvatarUrl",qurl); upsert_ini_key("ReadyPlayerMeETag",0);   // no ETag: Tribe loads it fresh
            char m[300]; snprintf(m,sizeof m,"rpm_url_set.txt: Tribe's Ready Player Me URL set once to %s",cut); ini_status(m); }
        rename(p,q); }
    else if(ini_flag("rpm_url_clear")){
        char p[600]; snprintf(p,sizeof p,"%s/rpm_url_clear",OUTDIR);
        upsert_ini_key("ReadyPlayerMeAvatarUrl",0); upsert_ini_key("ReadyPlayerMeETag",0); unlink(p);
        ini_status("rpm_url_clear: Tribe's Ready Player Me URL and ETag deleted once"); }
    else ini_status("Ready Player Me keys: left as Tribe has them (no rpm_route_on, rpm_url_set.txt or rpm_url_clear)");
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
    LOGI("[HTTPD] %s",m); char p[600]; snprintf(p,sizeof p,"%s/httpd.log",OUTDIR); FILE* f=fopen(p,"a"); if(f){ fprintf(f,"%s\n",m); fclose(f); chmod(p,0666); } }

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
// Tribe 0.12.6 (2311): the store lib's vaddr 0x19e8eb4 (same prologue a9ba7bfd), + the same 0x1000 skew = base + 0x19e9eb4.
static const uintptr_t RVA_PE_GHIDRA = 0x19e8eb4; static const uintptr_t PE_SKEW = 0x1000;
typedef void(*pe_t)(void*,void*,void*); static pe_t orig_pe=0; static void* g_pe_addr=0;
static volatile sig_atomic_t g_load_req=0, g_in_load=0; static bool g_resolved=0;
// busy flag: enter only if it was free (atomic test-and-set), so two threads cannot both pass the check
static inline bool ue_enter(){ int z=0; return __atomic_compare_exchange_n(&g_in_load,&z,1,0,__ATOMIC_ACQ_REL,__ATOMIC_ACQUIRE); }
static inline void ue_leave(){ __atomic_store_n(&g_in_load,0,__ATOMIC_RELEASE); }
static inline bool ue_busy(){ return __atomic_load_n(&g_in_load,__ATOMIC_ACQUIRE)!=0; }
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
static uintptr_t g_fnGetRot=0, g_fnSetActorLR=0, g_camComp=0, g_vrOrigin=0, g_mcL=0, g_mcR=0;
static int g_fpsz=-1;                                        // sizeof(FProperty) in THIS build (self-calibrated)
static long g_pe_n=0, g_pe_drv=0;                  // ProcessEvent calls seen; per-frame runs done from repl_pe
static bool g_restOK=false, g_followInit=false, g_turning=false;
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
// load_result.txt rotates at 1 MB to load_result.1.txt (mod2311: on 2311 a line per frame had grown it to 33.6 MB)
static pthread_mutex_t g_lsLock=PTHREAD_MUTEX_INITIALIZER;
static void load_status(const char* fmt,...){ char m[512]; va_list ap; va_start(ap,fmt); vsnprintf(m,sizeof m,fmt,ap); va_end(ap);
    LOGI("[LOAD] %s",m); char p[600]; snprintf(p,sizeof p,"%s/load_result.txt",OUTDIR);
    pthread_mutex_lock(&g_lsLock);
    struct stat st; if(stat(p,&st)==0&&st.st_size>1024*1024){ char q[620]; snprintf(q,sizeof q,"%s/load_result.1.txt",OUTDIR); rename(p,q); }
    FILE* f=fopen(p,"a"); if(f){ fprintf(f,"%s\n",m); fclose(f); chmod(p,0666);}   // readable over adb
    pthread_mutex_unlock(&g_lsLock); }

// resolve name pool + object array + UStruct offsets from params.txt (heavy scan; run off the game thread)
static void ensure_resolved(){
    if(g_resolved) return; load_maps(); read_params();
    if(P_np){ g_namepool=g_base+P_np; g_blocks_off=(P_bo>=0)?(uint32_t)P_bo:0x40;
        char t0[8]; if(fname_resolve(0,t0,sizeof t0)!=4||strcmp(t0,"None")){   // e.g. a params.txt from another Tribe build
            load_status("resolve: params.txt np=0x%lx doesn't name FName 0 'None': scanning for the pool",(unsigned long)P_np); scan_namepool(); } }
    else scan_namepool();
    if(!(P_ga && try_objarray(g_base+P_ga))){ if(!scan_objarray()){ static int nf=0; if((nf++%15)==0) load_status("resolve: objarray FAIL (try %d)",nf); return; } }
    OFF_Super=0x40; OFF_Children=0x48; OFF_ChildProps=0x50; OFF_PropSize=0x58;   // R3-locked for this build
    char t[32]; fname_resolve(0,t,sizeof t);
    load_status("resolved: np=0x%lx ga=0x%lx NumElem=%u None='%s'",(unsigned long)(g_namepool-g_base),(unsigned long)(g_objarray-g_base),g_numElements,t);
    g_resolved=(g_numElements>1000);
    if(g_resolved) g_apply_fn=find_by_path("/Game/Visuals/BP_TribeVisualsManager.BP_TribeVisualsManager_C.ApplySkinToPlayer",0);
}
// ---- every call the mod makes into Tribe goes through call_uf, and call_uf checks it first (mod2311) ----
// The 13:57:37 crash was a stale object handed to the engine (claudedocs/mod_2311_load.md 2b, mod_2311_levels.md 4): the
// mod kept a pointer past its object's life, and the engine trusted it. So before every call: (1) the game thread only
// (once it is known); (2) the object called is alive in the object array: its slot holds it and the engine's own dead
// test (gc_dead_mask) passes; (3) it is of the class that declares the function (a freed slot reused by another kind of
// object fails here); (4) every object parameter that isn't null passes (2) and is of its parameter's class. A call
// that fails is skipped (its parms stay zeroed, as for a missing function) and logged once per function.
static bool obj_live(uintptr_t o){                   // slot + the engine's dead test; new objects past the count: refresh
    uint32_t idx=0; if(!o||!g_chunks||!sr(o+OFF_Index,&idx,4)) return false;
    if(idx>=g_numElements) refresh_numelements(); if(idx>=g_numElements) return false;
    uintptr_t chunk=rdptr(g_chunks+(uintptr_t)(idx>>16)*8); if(!chunk) return false;
    uintptr_t item=chunk+(uintptr_t)(idx&0xFFFF)*ITEM_STRIDE;
    return rdptr(item)==o&&!(rd32(item+8)&gc_dead_mask()); }
static int calib_fprop_size();
static volatile uintptr_t g_gtSelf=0;               // the game thread (pthread_self), learned in repl_pe
static long g_callSkips=0;                            // calls the check refused (shown in the [READY] line)
// is-a with a small cache: class pointers of loaded classes don't move, so a checked pair stays checked
static uintptr_t g_isaK[512][2]; static uint8_t g_isaV[512];
static bool cls_is(uintptr_t cls,uintptr_t want){
    if(!cls||!want) return false; if(cls==want) return true;
    uint32_t h=(uint32_t)(((cls>>4)^(want>>3))*2654435761u)>>23;     // 9 bits
    if(g_isaK[h][0]==cls&&g_isaK[h][1]==want) return g_isaV[h]!=0;
    bool r=false; int d=0; for(uintptr_t c=rdptr(cls+OFF_Super); c&&d<40; c=rdptr(c+OFF_Super),d++) if(c==want){ r=true; break; }
    g_isaK[h][0]=cls; g_isaK[h][1]=want; g_isaV[h]=r?1:0; return r; }
struct FnSig { uintptr_t fn, owner; bool iface, logged; int n; int off[8]; uintptr_t pcls[8]; };
static FnSig g_fnSig[384]; static int g_fnSigN=0;
static const FnSig* fn_sig(uintptr_t fn){            // the function's class and its object parameters, read once
    uint32_t h=(uint32_t)((fn>>4)*2654435761u)%384u;
    for(int k=0;k<384;k++){ FnSig* s=&g_fnSig[(h+k)%384u]; if(s->fn==fn) return s;
        if(!s->fn){ if(g_fnSigN>=360) return nullptr; g_fnSigN++;
            s->owner=rdptr(fn+OFF_Outer); s->iface=false; s->logged=false; s->n=0;
            char nm[64]; int d=0;                                          // an interface's function: its owner is a UInterface
            for(uintptr_t c=s->owner; c&&d<12; c=rdptr(c+OFF_Super),d++){ obj_name(c,nm,sizeof nm); if(!strcmp(nm,"Interface")){ s->iface=true; break; } }
            int S=calib_fprop_size(); uint16_t psz=rd16(fn+0xB6);
            for(uintptr_t f=rdptr(fn+OFF_ChildProps); f&&S>0&&s->n<8; f=rdptr(f+FF_Next)){ char ty[48]; ffield_type(f,ty,sizeof ty);
                if(strcmp(ty,"ObjectProperty")&&strcmp(ty,"ObjectPtrProperty")) continue;
                uint32_t o=rd32(f+FP_Offset); uintptr_t pc=rdptr(f+(uintptr_t)S); if(o+8>psz||!pc) continue;
                s->off[s->n]=(int)o; s->pcls[s->n]=pc; s->n++; }
            __atomic_store_n(&s->fn,fn,__ATOMIC_RELEASE); return s; } }
    return nullptr; }
static void call_skip(FnSig* s,uintptr_t fn,uintptr_t o,const char* why){
    g_callSkips++;
    if(s&&s->logged) return; if(s) s->logged=true;
    char fp[300], cn[96]="(gone)"; full_path(fn,fp,sizeof fp); if(o&&in_range(o,0x30)&&in_range(rdptr(o+OFF_Class),0x30)) class_name(o,cn,sizeof cn);
    LOGI("[CALL] skipped %s: %s (object 0x%lx, class %s); logged once per function",fp,why,(unsigned long)o,cn); }
static void call_uf(uintptr_t obj,uintptr_t fn,void* parms){
    if(!orig_pe||!obj||!fn) return;
    uintptr_t gt=g_gtSelf; if(gt&&(uintptr_t)pthread_self()!=gt){ static int w=0; if(w++<5) LOGI("[CALL] refused a call from a thread other than the game thread"); return; }
    FnSig* s=(FnSig*)fn_sig(fn);
    if(!obj_live(obj)){ call_skip(s,fn,obj,"the object is gone or being collected"); return; }
    if(s&&s->owner&&!s->iface&&!cls_is(rdptr(obj+OFF_Class),s->owner)){ call_skip(s,fn,obj,"the object is not of the function's class"); return; }
    if(s&&parms) for(int k=0;k<s->n;k++){ uintptr_t v=*(uintptr_t*)((uint8_t*)parms+s->off[k]); if(!v) continue;
        if(!obj_live(v)){ call_skip(s,fn,v,"an object parameter is gone or being collected"); return; }
        if(!cls_is(rdptr(v+OFF_Class),s->pcls[k])){ call_skip(s,fn,v,"an object parameter is not of its class"); return; } }
    orig_pe((void*)obj,(void*)fn,parms); }
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
static uintptr_t g_pawn=0;
static uintptr_t find_field(uintptr_t st,const char* name){ char nm[128];
    for(uintptr_t c=st; c; c=rdptr(c+OFF_Super)) for(uintptr_t f=rdptr(c+OFF_ChildProps); f; f=rdptr(f+FF_Next)){
        fname_resolve(rd32(f+FF_Name),nm,sizeof nm); if(!strcmp(nm,name)) return f; }
    return 0; }
// sizeof(FProperty) == offset of FObjectPropertyBase::PropertyClass. Find it on SkeletalMeshActor.SkeletalMeshComponent,
// whose PropertyClass must be the SkeletalMeshComponent UClass. (FP_ElemSize@0x34 proved wrong, so don't assume 0x70.)
static int calib_fprop_size(){
    if(g_fpsz>0) return g_fpsz;
    static int fails=0; if(fails>=3||!g_resolved) return -1;            // mod2311: a full object walk per try, so 3 tries
    uintptr_t cls=find_by_path("/Script/Engine.SkeletalMeshActor",1), smc=find_by_path("/Script/Engine.SkeletalMeshComponent",1);
    uintptr_t f=cls?find_field(cls,"SkeletalMeshComponent"):0; if(!f||!smc){ fails++; return -1; }
    for(int o=0x48;o<=0xB0;o+=8) if(rdptr(f+o)==smc){ g_fpsz=o; break; }
    if(g_fpsz<=0) fails++;
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
    // mod2311: its own run counter. On 2311 the two tick counters never move (the driver is repl_pe's), so t stayed 0 and
    // this logged every frame: 250,256 lines, 32.6 MB of load_result.txt, and a flooded logcat (claudedocs/mod_2311_load.md 2f).
    static long runs=0; long t=++runs;
    if(t==1||(t%3600)==0) load_status("follow: run %ld dt=%.4f hmd=(%.0f,%.0f,%.0f) hmdYaw=%.0f target=%.0f body=%.0f floorZ=%.0f -> actor=(%.0f,%.0f,%.0f) yaw=%.0f",
        t,dt,C[0],C[1],C[2],hmdYaw,target,g_bodyYaw,O[2],P[0],P[1],P[2],R[1]); }
// the pawn: 2304's Blueprint TribePawnBP_C; Tribe 0.12.6 (2311) has only the native TribePawn, whose C++ now declares the
// tracked components as properties (VROrigin, Camera, MotionControllerL/R). The local one first (camera manager ->
// PCOwner -> Pawn, engine properties), else the first live one of either class (exact: other 2311 names contain
// "TribePawn"); then the components from the pawn's properties, else by name under it. Game thread.
static volatile uintptr_t g_worldCamMgr=0, g_worldPawnHint=0;   // the poll thread's finds (world_poll), for the game thread
static uintptr_t pawn_of_cam_mgr(uintptr_t cm){                    // camera manager -> PCOwner -> Pawn, if it is Tribe's pawn
    int o1=cm?prop_offset(rdptr(cm+OFF_Class),"PCOwner",0):-1; uintptr_t pco=o1>=0?rdptr(cm+o1):0;
    int o2=pco?prop_offset(rdptr(pco+OFF_Class),"Pawn",0):-1; uintptr_t p=o2>=0?rdptr(pco+o2):0; char cn[128];
    if(!p||!obj_live(p)) return 0; class_name(p,cn,sizeof cn); return (!strcmp(cn,"TribePawn")||!strcmp(cn,"TribePawnBP_C"))?p:0; }
static void follow_wire(){
    g_pawn=0; auto alive=[](uintptr_t o){ return obj_live(o); };
    { char cn[128], fp[400];
      g_pawn=pawn_of_cam_mgr(g_camMgr);
      if(!g_pawn){ uintptr_t h=g_worldPawnHint; if(h&&alive(h)){ class_name(h,cn,sizeof cn); if(!strcmp(cn,"TribePawn")||!strcmp(cn,"TribePawnBP_C")) g_pawn=h; } }
      for(uint32_t i=0;i<g_numElements&&!g_pawn;i++){ uintptr_t o=obj_at(i); if(!o) continue; class_name(o,cn,sizeof cn);
        if(strcmp(cn,"TribePawn")&&strcmp(cn,"TribePawnBP_C")) continue; if(rd32(o+OFF_Flags)&RF_ClassDefaultObject) continue;
        full_path(o,fp,sizeof fp); if(strstr(fp,"Default__")||!strstr(fp,"PersistentLevel")) continue; g_pawn=o; } }
    uintptr_t pc=g_pawn?rdptr(g_pawn+OFF_Class):0;
    auto comp=[&](const char* prop,const char* cls)->uintptr_t{ int o=pc?prop_offset(pc,prop,0):-1; uintptr_t c=o>=0?rdptr(g_pawn+o):0;
        char cn[96]; if(c){ class_name(c,cn,sizeof cn); if(!alive(c)||!strstr(cn,cls)) c=0; }
        return c?c:find_live(prop,cls,"TribePawn"); };
    g_camComp =comp("Camera","CameraComponent");
    g_vrOrigin=comp("VROrigin","SceneComponent");
    g_mcL     =comp("MotionControllerL","MotionControllerComponent");
    g_mcR     =comp("MotionControllerR","MotionControllerComponent"); }
// The world (mod2311; replaces the 90 s pawn-tick fallback, which on 2311 never ticked: ReceiveTick doesn't pass
// ProcessEvent there). Once the poll thread has found the camera manager and Tribe's local pawn (world_poll), the game
// thread wires the pawn's camera, VROrigin and hands here, with or without our avatar actor. The per-frame work (stage,
// lights, menus, stream, drone) runs from then on; what needs our avatar checks for it itself.
static volatile sig_atomic_t g_wire_req=0;
static void world_wire(){
    uintptr_t cm=g_worldCamMgr; if(cm&&obj_live(cm)) g_camMgr=cm;
    follow_wire();
    load_status("world: wired pawn=0x%lx camera=0x%lx vrOrigin=0x%lx hands=0x%lx/0x%lx (camera manager 0x%lx)",(unsigned long)g_pawn,
        (unsigned long)g_camComp,(unsigned long)g_vrOrigin,(unsigned long)g_mcL,(unsigned long)g_mcR,(unsigned long)g_camMgr); }
// spawn our own ASkeletalMeshActor 2 m in front of the HMD, facing it, feet on the floor (skullbuck's origin is at its
// hips, 97 cm up). All param offsets are resolved BY NAME from the UFunction at runtime; FTransform (UE5 LWC, NEON) is
// 96 B = quat@0, translation@32, scale@64 -- checked against the SpawnTransform param's ElementSize before use.
static uintptr_t spawn_iso_actor(uintptr_t mesh){
    static uintptr_t gs=0, fnB=0, fnF=0, cls=0, fnRot=0, fnColl=0, fnShad=0;   // engine objects: looked up once (mod2311)
    if(!gs)    gs   =find_by_path("/Script/Engine.Default__GameplayStatics",0);
    if(!fnB)   fnB  =find_by_path("/Script/Engine.GameplayStatics.BeginDeferredActorSpawnFromClass",0);
    if(!fnF)   fnF  =find_by_path("/Script/Engine.GameplayStatics.FinishSpawningActor",0);
    if(!cls)   cls  =find_by_path("/Script/Engine.SkeletalMeshActor",1);
    if(!fnRot) fnRot=find_by_path("/Script/Engine.PlayerCameraManager.GetCameraRotation",0);
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
    if(!fnColl) fnColl=find_by_path("/Script/Engine.PrimitiveComponent.SetCollisionEnabled",0);
    if(!fnShad) fnShad=find_by_path("/Script/Engine.PrimitiveComponent.SetCastShadow",0);
    call_bool2(comp,fnColl,0,0);                                // ECollisionEnabled::NoCollision
    call_bool2(comp,fnShad,0,0);                                // SetCastShadow(false)
    refresh_numelements(); root_object(actor);                  // keep our actor alive
    // FOLLOW wiring: the pawn's tracked components + the functions the per-frame update uses (the poll thread looked
    // them up already, world_poll; only a missing one is looked up here)
    if(!g_fnGetRot)     g_fnGetRot     =find_by_path("/Script/Engine.SceneComponent.K2_GetComponentRotation",0);
    if(!g_fnSetActorLR) g_fnSetActorLR =find_by_path("/Script/Engine.Actor.K2_SetActorLocationAndRotation",0);
    follow_wire();                                              // g_pawn, g_camComp, g_vrOrigin, g_mcL, g_mcR (2304 + 2311)
    g_restOK=false; g_restTries=0; g_followInit=false; g_turning=false;
    load_status("follow: getRot=0x%lx setLR=0x%lx cam=0x%lx vrOrigin=0x%lx mcL=0x%lx mcR=0x%lx pawn=0x%lx",
        (unsigned long)g_fnGetRot,(unsigned long)g_fnSetActorLR,(unsigned long)g_camComp,
        (unsigned long)g_vrOrigin,(unsigned long)g_mcL,(unsigned long)g_mcR,(unsigned long)g_pawn);
    g_isoActor=actor; g_isoComp=comp;
    load_status("iso: mesh set on our own actor (comp=0x%lx); following the HMD from its next tick",(unsigned long)comp);
    return comp;
}
static void head_skin_loaded(const char* skin,uintptr_t libCDO,uintptr_t fnLoad);   // head.cpp: heads/<skin>.glb after a skin load
// which avatar menu (mod2311 step B; set by the supervisor): 0 not known yet, 1 = 2311's C++ classes, 2 = 2304's Blueprints
static volatile sig_atomic_t g_smMode=0;
// the last load's outcome, for the supervisor (mod2311): 1 loaded, -1 failed (g_loadWhy), 0 never ran; g_loadSeq counts runs
static volatile sig_atomic_t g_loadOk=0, g_loadSeq=0; static char g_loadWhy[96]="", g_skinLoaded[128]="";
static void do_load_inner();
static void do_load(){
    g_loadOk=0; snprintf(g_loadWhy,sizeof g_loadWhy,"%s","stopped early");
    do_load_inner();
    if(g_loadOk!=1) g_loadOk=-1;
    __sync_synchronize(); g_loadSeq=g_loadSeq+1; }
static void do_load_inner(){
    load_status("=== do_load (game tid=%d) ===",my_tid());
    refresh_numelements();                                       // catch objects spawned since resolve (the pawn)
    static uintptr_t fnLoad=0, fnMesh=0, fnErr=0, fnSet=0, libCDO=0;     // native objects: looked up once (mod2311)
    if(!fnLoad) fnLoad=find_by_path("/Script/glTFRuntime.glTFRuntimeFunctionLibrary.glTFLoadAssetFromFilename",0);
    if(!fnMesh) fnMesh=find_by_path("/Script/glTFRuntime.glTFRuntimeAsset.LoadSkeletalMesh",0);
    if(!fnErr)  fnErr =find_by_path("/Script/glTFRuntime.glTFRuntimeAsset.GetErrors",0);
    if(!fnSet)  fnSet =find_by_path("/Script/Engine.SkeletalMeshComponent.SetSkeletalMeshAsset",0);
    if(!libCDO) libCDO=find_by_path("/Script/glTFRuntime.Default__glTFRuntimeFunctionLibrary",0);
    if(!libCDO) libCDO=find_obj("glTFRuntimeFunctionLibrary",1);
    uintptr_t body=find_live("AvatarBodyMesh","SkeletalMeshComponent","ReadyPlayerMeComponent");
    load_status("fnLoad=0x%lx fnMesh=0x%lx fnErr=0x%lx fnSet=0x%lx libCDO=0x%lx body=0x%lx",
        (unsigned long)fnLoad,(unsigned long)fnMesh,(unsigned long)fnErr,(unsigned long)fnSet,(unsigned long)libCDO,(unsigned long)body);
    if(!fnLoad||!fnMesh||!fnSet||!libCDO){ load_status("missing UFunction/CDO; abort"); snprintf(g_loadWhy,sizeof g_loadWhy,"glTFRuntime functions not found"); return; }
    // skin selection: active_skin.txt names a file in tribemod/skins/ ; else glb_path.txt (full path); else custom.glb.
    // "tribe" = Tribe's own avatar was picked last (mod2311): nothing of ours loads.
    char path[512]; char skin[256]="";
    if(read_trim_file("active_skin.txt",skin,sizeof skin)&&!strcmp(skin,"tribe")){ load_status("active_skin.txt = tribe: Tribe's own avatar, no mod skin");
        snprintf(g_loadWhy,sizeof g_loadWhy,"Tribe's own avatar is picked"); return; }
    if(skin[0]) snprintf(path,sizeof path,"%s/skins/%s",OUTDIR,skin);
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
    if(!asset){ load_status("asset NULL -> glb parse/file-access failed (check bAllowExternalFiles/path)"); snprintf(g_loadWhy,sizeof g_loadWhy,"glb not loaded (%.60s)",skin[0]?skin:path); return; }
    // 2) asset.LoadSkeletalMesh(0,0) [by index -> ignores AvatarRoot/Armature]. Try materials ON;
    //    if it fails (uncooked M_glTFRuntimeBase aborts the primitive) fall back to gray so SOMETHING shows.
    uintptr_t mesh=load_mesh(asset,fnMesh,0);            // materials ON
    load_status("mesh(materials)=0x%lx",(unsigned long)mesh);
    if(!mesh){ load_status("materials-on failed -> errors:"); decode_errors(asset,fnErr);
        mesh=load_mesh(asset,fnMesh,1); load_status("mesh(gray fallback)=0x%lx",(unsigned long)mesh); }
    if(!mesh){ load_status("mesh NULL even gray:"); decode_errors(asset,fnErr); snprintf(g_loadWhy,sizeof g_loadWhy,"no mesh from %.60s",skin[0]?skin:path); return; }
    // did the glTFRuntime base material load? (advisor's cooked-materials check)
    { uintptr_t mb=find_struct("M_glTFRuntimeBase"); load_status("M_glTFRuntimeBase resident=%s",mb?"YES":"no(maybe uncooked)"); }
    // 3) pin the mesh; our own avatar actor (+ its body-tracked meshes) takes it; Tribe's slot too if it exists (legacy)
    g_fnSet=fnSet;
    if(!g_fnOwner)    g_fnOwner=find_by_path("/Script/Engine.PrimitiveComponent.SetOwnerNoSee",0);
    if(!g_fnVis)      g_fnVis  =find_by_path("/Script/Engine.SceneComponent.SetVisibility",0);
    if(!g_fnHid)      g_fnHid  =find_by_path("/Script/Engine.SceneComponent.SetHiddenInGame",0);
    if(!g_fnLeader)   g_fnLeader  =find_by_path("/Script/Engine.SkinnedMeshComponent.SetLeaderPoseComponent",0);
    if(!g_fnRendered) g_fnRendered=find_by_path("/Script/Engine.PrimitiveComponent.WasRecentlyRendered",0);
    if(!g_fnLoc)      g_fnLoc     =find_by_path("/Script/Engine.SceneComponent.K2_GetComponentLocation",0);
    if(!g_fnScale)    g_fnScale   =find_by_path("/Script/Engine.SceneComponent.K2_GetComponentScale",0);
    if(!g_fnCamLoc)   g_fnCamLoc  =find_by_path("/Script/Engine.PlayerCameraManager.GetCameraLocation",0);
    refresh_numelements();                                       // the new mesh's index is past the cached count (was rooted=0)
    if(!g_camMgr||!obj_live(g_camMgr)) g_camMgr=find_live_class_sub("CameraManager");   // (world_wire normally set it)
    bool rooted=root_object(mesh);                               // AddToRoot: survives Tribe dropping its ref
    uintptr_t prev=g_mymesh; g_keep=0;                           // pause keeper/blocker during the swap
    g_mymesh=mesh;
    if(g_isoComp){                                               // skin switch: our actor shows the new mesh; tracked meshes re-rig
        static uint8_t sp2[0x10]; memset(sp2,0,sizeof sp2); *(uintptr_t*)sp2=mesh; call_uf(g_isoComp,fnSet,sp2);
        g_restOK=false; g_restTries=0; g_skin_changed=1;
        load_status("skin: our avatar actor now shows the new mesh; body-tracking re-rig queued"); }
    if(body&&g_smMode==2){ attach_mesh(body,mesh); g_body=body; g_keep=1; }   // 2304 only (mod2311 step B, characters doc C8)
    else if(body) load_status("2311: Tribe's AvatarBodyMesh left to Tribe (no copy at the world origin, no keeper); Tribe's own avatar is hidden while a mod skin is on");
    else load_status("(no live Tribe AvatarBodyMesh slot -- not needed: our own actor shows the avatar)");
    if(prev && prev!=mesh) unroot_object(prev);                  // release the previous skin's mesh
    load_status("attached mesh=0x%lx body=0x%lx rooted=%d leader=0x%lx camMgr=0x%lx; keeper ON; render report in 3s",
        (unsigned long)mesh,(unsigned long)body,(int)rooted,(unsigned long)g_fnLeader,(unsigned long)g_camMgr);
    g_reports=0; g_report_ticks=6;                               // first RENDER report ~3s after attach (poll ticks are 0.5s)
    g_loaded_once=1;                                             // enable the menu-select skin-cycle trigger
    head_skin_loaded(skin,libCDO,fnLoad);                        // detachable head: heads/<skin>.glb, if there is one
    snprintf(g_skinLoaded,sizeof g_skinLoaded,"%s",skin[0]?skin:(strrchr(path,'/')?strrchr(path,'/')+1:path)); g_loadOk=1;
    load_status("=== do_load done (materials on, visible, kept) ===");
}
// The fault guard is up while fn runs (mod2311): a bad read inside it fails that read instead of crashing. As before, a
// fault anywhere else (inside the engine) is not caught: the old version's outer jump target was overwritten by the
// first read inside fn, and on another thread it could send the game thread onto the poll thread's stack.
static void run_guarded(void (*fn)(),const char* what){ (void)what; install_guard(); fn(); remove_guard(); }
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
#include "gait.h"                                                    // the walk cycle on the tracked legs (a2_gait)
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
static int g_gaitBone[8]={-1,-1,-1,-1,-1,-1,-1,-1}; static double g_gaitLeg=0;   // Left/Right UpLeg, Leg, Foot, ToeBase; hip-ankle cm
static Gait g_gait; static V3 g_gaitHipOff={0,0,0};                // the walk cycle's state; the hips' dip this frame
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
    { static const char* const GB[8]={"LeftUpLeg","LeftLeg","LeftFoot","LeftToeBase","RightUpLeg","RightLeg","RightFoot","RightToeBase"};
      for(int k=0;k<8;k++) g_gaitBone[k]=rb_find(GB[k]);
      g_gaitLeg=(g_gaitBone[1]>=0&&g_gaitBone[2]>=0)?vlen(g_rb_lt[g_gaitBone[1]])+vlen(g_rb_lt[g_gaitBone[2]]):0; }
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
// Which hand Tribe actually draws decides, not the Quest's signal: IsHandPositionValid can stay valid=1/High while you hold
// a controller (observed 2026-10-05: wrist 12 cm from the controller, valid=1). By then Tribe has hidden its tracked hand,
// so the model's stayed hidden too -> no hands. The model hand is now shown exactly when Tribe's
// TribeControllers_C.OculusXRHandComponent for that side is not visible (the Quest signal is only a fallback).
static uintptr_t g_fnCompVisible=0, g_ohCls=0, g_ctlCls=0; static int g_offSkelType=-1, g_offOwningPawn=-2;
static volatile uintptr_t g_tribeHand[2]={0,0};                      // set by the poll thread, read on the game thread
static volatile bool g_tribeHandSeen=false;                          // found at least once -> never fall back to the Quest signal
static const uint32_t RF_MirroredGarbage=0x40000000;                 // destroyed, awaiting GC (UE 5.4 ObjectMacros.h)
static bool obj_alive(uintptr_t o);
// Tribe destroys and respawns TribeControllers_C at every hands<->controllers switch (seen: 6 hand meshes at once, old + new),
// so a cached mesh goes stale right when it matters: skip garbage, prefer the newest, re-find twice a second.
static bool th_ok(uintptr_t c){ if(!c||!obj_alive(c)||(rd32(c+OFF_Flags)&RF_MirroredGarbage)) return false;
    uintptr_t owner=rdptr(c+OFF_Outer); return owner&&!(rd32(owner+OFF_Flags)&RF_MirroredGarbage); }
static void a2_find_tribe_hands(){                                   // poll thread: the local player's two tracked-hand meshes
    if(!g_ohCls){ g_ohCls=find_by_path("/Script/OculusXRInput.OculusXRHandComponent",1); if(!g_ohCls) return;
        g_offSkelType=prop_offset(g_ohCls,"SkeletonType",0); g_fnCompVisible=find_by_path("/Script/Engine.SceneComponent.IsVisible",0); }
    if(g_offOwningPawn==-2){ g_ctlCls=find_by_path("/Game/Pawn/TribeControllers.TribeControllers_C",1);
        if(g_ctlCls) g_offOwningPawn=prop_offset(g_ctlCls,"OwningPawn",0); }
    if(th_ok(g_tribeHand[0])&&th_ok(g_tribeHand[1])) return;
    refresh_numelements(); char cn[96]; uintptr_t found[2]={0,0}, any[2]={0,0}; int seen=0;
    for(uint32_t i=0;i<g_numElements;i++){ uintptr_t o=obj_at(i); if(!o||rdptr(o+OFF_Class)!=g_ohCls) continue;
        if(rd32(o+OFF_Flags)&(RF_ClassDefaultObject|RF_MirroredGarbage)) continue;
        uintptr_t owner=rdptr(o+OFF_Outer); if(!owner||(rd32(owner+OFF_Flags)&RF_MirroredGarbage)) continue;   // outer = its actor
        class_name(owner,cn,sizeof cn); if(strcmp(cn,"TribeControllers_C")) continue;
        uint8_t t=0; if(g_offSkelType>=0) sr(o+g_offSkelType,&t,1);
        int s=(t==(uint8_t)g_handType[0])?0:(t==(uint8_t)g_handType[1])?1:-1; if(s<0) continue;
        seen++; any[s]=o;                                                // last = newest
        if(g_offOwningPawn<0||!g_pawn||rdptr(owner+g_offOwningPawn)==g_pawn) found[s]=o; }   // not another player's hand
    if(!found[0]&&!found[1]){ found[0]=any[0]; found[1]=any[1]; }    // our pawn pointer went stale (respawned pawn): solo = ours
    if(found[0]&&found[1]) g_tribeHandSeen=true;
    if(found[0]!=g_tribeHand[0]||found[1]!=g_tribeHand[1]){ g_tribeHand[0]=found[0]; g_tribeHand[1]=found[1];
        load_status("A2 hands: Tribe's tracked-hand meshes L=0x%lx R=0x%lx (%d live on controllers; SkeletonType@%d OwningPawn@%d IsVisible=0x%lx)",
            (unsigned long)found[0],(unsigned long)found[1],seen,g_offSkelType,g_offOwningPawn,(unsigned long)g_fnCompVisible); } }
static int a2_tribe_hand_visible(int s){                             // game thread: 1 visible, 0 hidden, -1 unknown
    uintptr_t c=g_tribeHand[s]; if(!g_fnCompVisible||!th_ok(c)) return -1;
    uint8_t* r=call_ret(c,g_fnCompVisible,0,0); return r?(*r?1:0):-1; }
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
        int tv=a2_tribe_hand_visible(s);                             // mirror what Tribe draws; Quest signal only as a fallback
        if(tv<0&&g_tribeHandSeen) continue;                          // Tribe is respawning its controllers: hold, re-found soon
        bool want=tv>=0?tv==0:!(valid==1&&(conf<0||conf==(int)g_confHigh));
        if(want==g_handShown[s]) continue;
        g_handShown[s]=want; uintptr_t ms[2]={g_pmA,g_pmB};
        for(int m=0;m<2;m++) if(ms[m]){ if(want) a2_unhide_bone(ms[m],h); else a2_hide_bone(ms[m],h); }
        load_status("A2 hands: %s -> %s (Tribe's tracked hand %s; Quest hand tracking valid=%d confidence=%d)",s?"right":"left",
            want?"MODEL hand shown":"Tribe's tracked hand (model hand hidden)",tv<0?"unknown":tv?"visible":"hidden",valid,conf); } }
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
        ct[i]=(i==iHips&&dv[i])?vadd(g_hipsCur,g_gaitHipOff):(p<0?g_rb_lt[i]:vadd(ct[p],qrot(cq[p],g_rb_lt[i]))); } }
// the walk cycle (gait.h, the user 2026-10-10): while the mod's walking carries VROrigin (the meshes' parent), swing the
// tracked legs about the body's left-right axis and dip the hips; the arms and the rest stay tracked. Component space =
// VROrigin's frame (the meshes hang on it unrotated); the walking is measured in the world from VROrigin's motion.
static void a2_gait(Q4* tq,const bool* dv,float dt){
    g_gaitHipOff=V(0,0,0);
    double P[3], R[3]; if(g_gaitLeg<1||!g_trackParent||!obj_alive(g_trackParent)||!get_vec3(g_trackParent,g_fnLoc,P)||!get_vec3(g_trackParent,g_fnGetRot,R)) return;
    V3 f=V(cos(g_thM*M_PI/180.0),sin(g_thM*M_PI/180.0),0);           // the avatar's rest facing, turned as the tracked hips are
    if(iHips>=0&&dv[iHips]){ V3 h=qrot(qmul(tq[iHips],qinv(g_rb_cq[iHips])),f); h.z=0; if(vlen(h)>0.2) f=vnorm(h); }
    double w=gait_update(&g_gait,V(P[0],P[1],P[2]),R[1],qrot(qyaw(R[1]),f),g_gaitLeg*g_btScale,dt);
    if(w<=0) return;
    V3 k=gait_lateral(f); const int* b=g_gaitBone;
    #define GB_(i) ((b[i]>=0&&dv[b[i]])?&tq[b[i]]:(Q4*)0)
    gait_leg(GB_(0),GB_(1),GB_(2),GB_(3),k,g_gait.phase,w);
    gait_leg(GB_(4),GB_(5),GB_(6),GB_(7),k,g_gait.phase+0.5,w);
    #undef GB_
    g_gaitHipOff=V(0,0,gait_dip(&g_gait,g_gaitLeg)); }
static void a2_set_bone(uintptr_t comp,int i,Q4 q,V3 t){
    static int oN=-2,oX=-1,oS=-1; static uint16_t psz=0;
    if(oN==-2){ oN=prop_offset(g_fnSetBoneXf,"BoneName",0); oX=prop_offset(g_fnSetBoneXf,"InTransform",0); oS=prop_offset(g_fnSetBoneXf,"BoneSpace",0); psz=rd16(g_fnSetBoneXf+0xB6);
        load_status("A2: SetBoneTransformByName psz=0x%x BoneName@%d InTransform@%d BoneSpace@%d (ComponentSpace=%lld)",psz,oN,oX,oS,(long long)g_boneCS); }
    static uint8_t b[256] __attribute__((aligned(16))); if(oN<0||oX<0||psz>sizeof b) return;
    memset(b,0,psz); memcpy(b+oN,&g_rb_fn[i],8); double* x=(double*)(b+oX);
    x[0]=q.x; x[1]=q.y; x[2]=q.z; x[3]=q.w; x[4]=t.x; x[5]=t.y; x[6]=t.z; x[8]=x[9]=x[10]=1; if(oS>=0) b[oS]=(uint8_t)g_boneCS;
    call_uf(comp,g_fnSetBoneXf,b); }
static void head_capture_fk(const Q4* cq,const V3* ct);               // head.cpp: the DH bones' pose, every frame
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
    a2_gait(tq,dv,dt);                                               // the stick's walk on the legs (before any FK)
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
    head_capture_fk(cq,ct);                                          // the pose A renders this frame, DH bones included
    for(int i=0;i<g_rb_n;i++) if(dv[i]){ a2_set_bone(g_pmA,i,cq[i],ct[i]); if(g_pmB) a2_set_bone(g_pmB,i,cq[i],ct[i]); }
    { static int good=0; if(g_a2Marker && ++good>=120){ a2_marker(false); load_status("A2: 120 frames driven OK (crash guard cleared)"); } }
    clock_gettime(CLOCK_MONOTONIC,&t1); usSum+=(t1.tv_sec-t0.tv_sec)*1e6+(t1.tv_nsec-t0.tv_nsec)/1e3; usN++;
    int nset=0; for(int i=0;i<g_rb_n;i++) nset+=dv[i];
    logT+=dt; if(logT>=2.0||init){ logT=0;
        V3 d=qrot(qinv(camQ),vsub(camP,mp[7]));                         // eyes relative to Meta's head joint, in the HMD's frame
        int rA=-1,rB=-1; uint8_t* r=call_ret(g_pmA,g_fnRendered,1,0.5f); if(r) rA=*r; if(g_pmB){ r=call_ret(g_pmB,g_fnRendered,1,0.5f); if(r) rB=*r; }
        double wc[2]={-1,-1}; uintptr_t mc[2]={g_mcL,g_mcR}; int wj[2]={19,45};
        for(int s2=0;s2<2;s2++){ double l[3]; if(mc[s2]&&sr(mc[s2]+g_offRelLoc,l,24)) wc[s2]=vlen(vsub(V(l[0],l[1],l[2]),mp[wj[s2]])); }
        load_status("A2 live: dt=%.4f drive=%.0f us (%d bones/mesh) hands L%s R%s | align=%s (head err raw %.1f / corrected %.1f) eyes-vs-MetaHead fwd/right/up=(%.1f,%.1f,%.1f) | Meta wrist-to-controller L%.0f R%.0f cm | wristIK L%.1f R%.1f | rendered A=%d B=%d | gait w %.2f %.0f cm/s %s leg %.0f cm",
            dt,usN?usSum/usN:0.0,nset,g_handShown[0]?"=model":"=tribe",g_handShown[1]?"=model":"=tribe",
            g_align?"base":"raw",g_errRaw,g_errAl,d.x,d.y,d.z,wc[0],wc[1],eL*g_btScale,eR*g_btScale,rA,rB,
            g_gait.w,g_gait.speed,g_gait.sign<0?"back":"fwd",g_gaitLeg); usSum=0; usN=0; } }
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
// The giant intro (giant_tick, further down) runs while g_gState != G_DOWN; the drone then holds the crowd's view of it
// (the user: "when i press that button, the camera goes into the crowd in the middle and watches from there while im
// up and down. this camera angle only happens when i press that button"). World cm, mid-crowd just above the heads.
enum { G_DOWN, G_RISING, G_UP, G_DESC };
static int g_gState=G_DOWN;
static const double G_CAM[3]={0.0,-1200.0,240.0};   // v2: 12 m out, low (the user: "a little too far back. i cant see my face")
static uintptr_t g_droneCap=0, g_fnSetWorldLR=0, g_fnSetRelLR=0, g_dronePC=0;
// a stage's stream intro (hook/intro.cpp) flies the same camera through the drone's takeoff and landing: while g_introCam
// is 1, drone_update takes its pose from g_introP / g_introA (world cm). g_introArmed (an intro file is up) has drone_poll
// resolve the camera before the first press; g_introDark holds the show at ShowLevel 0 (giant_tick).
// head.cpp reads g_introCam too (head.txt intro=hold: no auto takeoff while the intro owns the camera), so this stays
// declared above #include "head.cpp".
static volatile sig_atomic_t g_introCam=0, g_introArmed=0, g_introDark=0;
static double g_introP[3], g_introA[3];
// a stage's extra camera on a new camera-menu button (hook/camview.cpp, the Halloween session): while g_viewCam is 1,
// drone_update takes its pose from g_viewP / g_viewA (world cm; a stage intro still wins, the reel waits); g_viewArmed (the
// stage that's up has camview.<folder>.txt) has drone_poll resolve the camera. g_dShotFov: the playing reel shot's fov=
// (0: Tribe's), which camview.cpp applies to the capture.
static volatile sig_atomic_t g_viewCam=0, g_viewArmed=0;
static double g_viewP[3], g_viewA[3];
static volatile float g_dShotFov=0;
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
// ---- path mode (drone.txt "mode=path"): a looping reel of shots, cut broadcast-style. Source: tribemod/drone_path.txt
// (re-read when it changes) or the built-in festival reel. World cm: Tribe's DJ rig sits at the origin and the crowd is
// toward -Y (the stage behind you, +Y). One shot per line:
//   fly   <secs> <x,y,z> <x,y,z> [look=dj|x,y,z]          ease from A to B, aiming at you or at a fixed point
//   orbit <secs> [r=cm] [h=cm vs head] [deg=sweep] [start=deg]   circle your (smoothed) head; start -90 = crowd side
// either may end with fov=<deg>: the capture's horizontal FOV during that shot (camview.cpp applies it; none = Tribe's)
struct DShot{ int orbit, lookDJ; float secs; double a[3], b[3], look[3], r, h, deg, start; float fov; };
#define DSHOT_MAX 40
static DShot g_dShots[2][DSHOT_MAX]; static volatile sig_atomic_t g_dShotN[2]={0,0}, g_dShotCur=0, g_dPathGen=0, g_dMode=0;
static const char* DRONE_REEL =
    "# overview: high above the back of the crowd, pushing in on the stage\n"
    "fly 12 0,-5200,1800 0,-3000,1100 look=0,600,900\n"
    "# low pass across the crowd, the stage in view\n"
    "fly 10 -3500,-2600,450 3500,-1800,450 look=0,400,700\n"
    "# over the crowd toward you\n"
    "fly 8 0,-2200,700 0,-700,330 look=dj\n"
    "# close orbit around you\n"
    "orbit 15 r=260 h=30 deg=360 start=-90\n"
    "# over your shoulder: the crowd ahead\n"
    "fly 8 -250,380,260 250,380,260 look=0,-3000,200\n"
    "# low hero angle from the stage lip, looking up past you\n"
    "fly 8 -400,-380,60 400,-380,60 look=0,300,900\n"
    "# tighter arc the other way\n"
    "orbit 10 r=170 h=10 deg=-140 start=-20\n"
    "# crane up from the pit\n"
    "fly 10 0,-900,150 0,-900,2200 look=0,300,900\n";
static bool parse_xyz(const char* s,double o[3]){ return sscanf(s,"%lf,%lf,%lf",&o[0],&o[1],&o[2])==3
    && fabs(o[0])<200000 && fabs(o[1])<200000 && fabs(o[2])<200000; }
static bool em_active_folder(char* out,size_t n);   // the active stage's folder under /Game/Mods/, lowercase (env menu)
static void drone_load_path(){                       // poll thread: parse into the idle buffer, then flip
    // the reel follows the stage (the club's walls are where the festival reel flies): drone_path.<folder>.txt while one
    // of our stages is up, else drone_path.txt, else the built-in festival reel
    static long lastKey=-2; char p[600], name[96]="drone_path.txt", fol[48]; struct stat st;
    if(em_active_folder(fol,sizeof fol)){ char nm[96]; snprintf(nm,sizeof nm,"drone_path.%s.txt",fol);
        snprintf(p,sizeof p,"%s/%s",OUTDIR,nm); if(stat(p,&st)==0) snprintf(name,sizeof name,"%s",nm); }
    snprintf(p,sizeof p,"%s/%s",OUTDIR,name);
    long key=stat(p,&st)==0?(long)st.st_mtime*1000003L+(long)st.st_size:-1;
    { uint32_t h=2166136261u; for(const char* q=name; *q; q++) h=(h^(uint8_t)*q)*16777619u; key=key*31L+(long)(h&0xffffu); }
    if(key==lastKey) return; lastKey=key;
    static char text[8192]; text[0]=0;
    if(key!=-1){ FILE* f=fopen(p,"r"); if(f){ size_t n=fread(text,1,sizeof text-1,f); text[n]=0; fclose(f); } }
    const char* src=text[0]?text:DRONE_REEL; int idle=1-g_dShotCur, n=0, bad=0; double total=0;
    char buf[8192]; snprintf(buf,sizeof buf,"%s",src); char* save=0;
    for(char* line=strtok_r(buf,"\n",&save); line&&n<DSHOT_MAX; line=strtok_r(0,"\n",&save)){
        line[strcspn(line,"\r#")]=0; char* tk[12]; int nt=0; char* s2=0;
        for(char* t=strtok_r(line," \t",&s2); t&&nt<12; t=strtok_r(0," \t",&s2)) tk[nt++]=t;
        if(nt<2) continue;
        DShot sh; memset(&sh,0,sizeof sh); sh.secs=(float)atof(tk[1]); sh.lookDJ=1; sh.r=260; sh.h=30; sh.deg=360; sh.start=-90;
        if(sh.secs<1) sh.secs=1; if(sh.secs>120) sh.secs=120;
        int i=2;
        if(!strcmp(tk[0],"orbit")) sh.orbit=1;
        else if(!strcmp(tk[0],"fly")&&nt>=4&&parse_xyz(tk[2],sh.a)&&parse_xyz(tk[3],sh.b)) i=4;
        else { bad++; continue; }
        for(;i<nt;i++){ char* eq=strchr(tk[i],'='); if(!eq) continue; *eq=0; const char* v=eq+1;
            if(!strcmp(tk[i],"look")) sh.lookDJ=!strcmp(v,"dj")?1:(parse_xyz(v,sh.look)?0:1);
            else if(!strcmp(tk[i],"r")) sh.r=fmin(fmax(atof(v),50),3000);
            else if(!strcmp(tk[i],"h")) sh.h=fmin(fmax(atof(v),-200),2000);
            else if(!strcmp(tk[i],"deg")) sh.deg=fmin(fmax(atof(v),-1080),1080);
            else if(!strcmp(tk[i],"start")) sh.start=atof(v);
            else if(!strcmp(tk[i],"fov")) sh.fov=(float)fmin(fmax(atof(v),10),120); }
        g_dShots[idle][n++]=sh; total+=sh.secs; }
    g_dShotN[idle]=n; g_dShotCur=idle; g_dPathGen++;
    LOGI("[DRONE] path: %d shot(s), %.0f s loop, from %s%s",n,total,text[0]?name:"the built-in festival reel",
        bad?" (some lines not understood: use fly/orbit)":""); }
static void drone_update(float dt){
    static bool flying=false, parked=false, haveRel=false, haveLast=false;
    static uintptr_t flyCap=0; static int flyTgt=0;
    static double relL[3], relR[3], C[3], th=0, t=0, rS=300, hS=80, lastP[3], logT=0;
    static bool pathReset=true; static int pathGen=-1, si=0; static double st=0;        // path-mode playhead
    uintptr_t pc=g_dronePC, cap=g_droneCap;
    bool intro=g_introCam!=0;                                        // a stage's stream intro flies it too (intro.cpp)
    bool view=g_viewCam!=0&&!intro;                                  // a camera-menu view holds it (camview.cpp)
    bool active=(g_droneOn||intro||view) && cap && g_fnSetWorldLR && g_camComp && g_fnLoc;
    g_dShotFov=0;                                                    // set again below while a reel shot with fov= plays
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
        th=atan2(dy,dx)*180.0/M_PI; t=0; logT=0; flying=true; flyCap=cap; flyTgt=tgt; pathReset=true;
        LOGI("[DRONE] takeoff (%s) from (%.0f,%.0f,%.0f): %.0f cm out, %.0f cm vs your head, angle %.0f deg",
            tgt?"Auto cam":"selfie stick",P0[0],P0[1],P0[2],rS,hS,th); }
    if(flyTgt==1&&pc){ float* cd=(float*)(pc+PC_AUTOCAM_NEXTCUT); float v=*cd;   // Auto cam only: park its cut timer
        if((v>0.0f&&v<600.0f)||v>1e8f){ if(!parked) LOGI("[DRONE] parking Tribe's Auto-cam cuts (next-cut timer was %.2fs)",v);
            *cd=1e9f; parked=true; } }
    double k=dt/1.5; if(k>1) k=1; for(int i=0;i<3;i++) C[i]+=(H[i]-C[i])*k;  // smoothed orbit center
    double P[3], A[3]={ C[0], C[1], C[2]+g_dLook };                         // default aim: a bit below your eyes
    int cur=g_dShotCur, ns=g_dShotN[cur];
    if(g_dMode==1&&ns>0){                                                   // path mode: the shot reel, looping
        const DShot* S=g_dShots[cur];
        if(pathReset||pathGen!=g_dPathGen){ pathReset=false; pathGen=g_dPathGen; si=0; st=0;
            LOGI("[DRONE] reel start: shot 1/%d (%s, %.0f s)",ns,S[0].orbit?"orbit":"fly",(double)S[0].secs); }
        if(g_gState==G_DOWN&&!intro&&!view) st+=dt;                        // the reel waits during the giant shot, an intro, a view
        while(st>=S[si].secs){ st-=S[si].secs; si=(si+1)%ns;
            LOGI("[DRONE] shot %d/%d (%s, %.0f s)",si+1,ns,S[si].orbit?"orbit":"fly",(double)S[si].secs); }
        const DShot& sh=S[si]; double u=st/sh.secs, e=u*u*(3-2*u);           // smoothstep: eases in and out
        g_dShotFov=sh.fov;                                                  // its fov= (camview.cpp's cv_fov applies it)
        if(sh.orbit){ double an=(sh.start+sh.deg*u)*M_PI/180.0;
            P[0]=C[0]+sh.r*cos(an); P[1]=C[1]+sh.r*sin(an); P[2]=C[2]+sh.h; }
        else { for(int i=0;i<3;i++) P[i]=sh.a[i]+(sh.b[i]-sh.a[i])*e;
            if(!sh.lookDJ) memcpy(A,sh.look,24); }
        t+=dt; th=atan2(P[1]-C[1],P[0]-C[0])*180.0/M_PI;                   // orbit mode resumes from here if switched
    } else {                                                                // orbit mode
        double r=g_dRset?(double)g_dR:rS, h=g_dHset?(double)g_dH:hS;          // drone.txt overrides the stick's start pose
        th=fmod(th+g_dSpeed*dt,360.0); t+=dt; double a=th*M_PI/180.0;
        P[0]=C[0]+r*cos(a); P[1]=C[1]+r*sin(a); P[2]=C[2]+h+g_dBob*sin(t*0.6); }
    static bool giantShot=false; static double gT=0, gAimZ=0;
    if(g_gState!=G_DOWN){                                                   // giant intro: mid-crowd, watching you rise
        if(!giantShot){ giantShot=true; gT=0; gAimZ=H[2]-120.0; LOGI("[DRONE] giant shot: cut to the crowd (%.0f,%.0f,%.0f)",G_CAM[0],G_CAM[1],G_CAM[2]); }
        gT+=dt; double ka=dt/0.8; if(ka>1) ka=1; gAimZ+=((H[2]-120.0)-gAimZ)*ka;   // aim 1.2 m under the eyes: face upper third
        P[0]=G_CAM[0]+60.0*sin(gT*0.35); P[1]=G_CAM[1]; P[2]=G_CAM[2]+15.0*sin(gT*0.23);   // a slow handheld sway
        A[0]=H[0]; A[1]=H[1]; A[2]=gAimZ; }
    else if(giantShot){ giantShot=false; LOGI("[DRONE] giant shot over: back to the reel"); }
    if(view){ memcpy(P,g_viewP,24); memcpy(A,g_viewA,24); }                  // a camera-menu view (camview.cpp)
    if(intro){ memcpy(P,g_introP,24); memcpy(A,g_introA,24); }                // the intro's camera (intro.cpp)
    double dx=A[0]-P[0], dy=A[1]-P[1], dz=A[2]-P[2], hz=sqrt(dx*dx+dy*dy);
    double R[3]={ atan2(dz,hz)*180.0/M_PI, atan2(dy,dx)*180.0/M_PI, 0 };    // FRotator: Pitch, Yaw, Roll
    logT+=dt;
    if(logT>=5.0){ logT=0; double Q[3]; bool got=get_vec3(cap,g_fnLoc,Q);
        // drift = how far the camera moved since OUR last write. ~0 = we're the only writer; large = something fights us.
        double d=(got&&haveLast)?sqrt((Q[0]-lastP[0])*(Q[0]-lastP[0])+(Q[1]-lastP[1])*(Q[1]-lastP[1])+(Q[2]-lastP[2])*(Q[2]-lastP[2])):-1;
        double rr=sqrt((P[0]-C[0])*(P[0]-C[0])+(P[1]-C[1])*(P[1]-C[1])), hh=P[2]-C[2];
        LOGI("[DRONE] %s %s center=(%.0f,%.0f,%.0f) cam=(%.0f,%.0f,%.0f) pitch=%.0f yaw=%.0f angle=%.0fdeg r=%.0f h=%.0f drift=%.1fcm cutsParked=%d",
            flyTgt?"auto":"selfie",intro?"intro":view?"view":(g_dMode==1&&ns>0)?"path":"orbit",C[0],C[1],C[2],P[0],P[1],P[2],R[0],R[1],th,rr,hh,d,(int)parked); }
    set_comp_xform(g_fnSetWorldLR,cap,P,R); memcpy(lastP,P,24); haveLast=true; }
#include "head.cpp"                                                  // detachable head: heads/<skin>.glb flies while A's Head is hidden
// ============ Skin-menu trace (flag tribemod/skin_trace; diagnostic, logcat [SKIN]) ============
// Logs every ProcessEvent call into the avatar menu's item widgets (W_SkinItem_C), the skin objects (BP_*Skin*_C) and the
// visuals manager, with self + first param. Blueprint->Blueprint calls never pass ProcessEvent, so this shows which entry
// points of a menu click our hook can actually see (the old cycle hook listened on ApplySkinToPlayer, a BP-internal call).
static volatile sig_atomic_t g_skinTrace=0;
static uintptr_t g_stFn[2048]; static uint8_t g_stCls[2048], g_stCnt[2048];  // func -> 1 menu/skin / 2 other; per-func log cap
static int skin_trace_slot(uintptr_t func){
    uint32_t h=(uint32_t)((func>>4)*2654435761u)&2047;
    for(int i=0;i<2048;i++){ uint32_t j=(h+i)&2047;
        if(g_stFn[j]==func) return (int)j;
        if(!g_stFn[j]){ char cn[96], fn[64]; obj_name(rdptr(func+OFF_Outer),cn,sizeof cn); obj_name(func,fn,sizeof fn);
            g_stCls[j]=(strstr(cn,"W_SkinItem")||(strstr(cn,"BP_")&&strstr(cn,"Skin"))||strstr(cn,"TribeVisualsManager")
                        ||strstr(cn,"SkinItemWidget")||(strstr(cn,"Tribe")&&strstr(cn,"Skin"))||strstr(cn,"VisualsMenu")   // 2311: native menus
                        ||!strcmp(cn,"UserObjectListEntry")||(!strcmp(cn,"UserWidget")&&strstr(fn,"Mouse")))?1:2;         // + a box's press
            g_stFn[j]=func; return (int)j; } }
    return -1; }
static void skin_trace_hit(uintptr_t self,uintptr_t func,void* parms){
    int j=skin_trace_slot(func); if(j<0||g_stCls[j]!=1||g_stCnt[j]>=40) return; g_stCnt[j]++;
    char fp[300], sc[96], sn[96], pc[96]="-", pn[96]="-";
    full_path(func,fp,sizeof fp); class_name(self,sc,sizeof sc); obj_name(self,sn,sizeof sn);
    uintptr_t p0=parms?rdptr((uintptr_t)parms):0;                 // first param, if it is a UObject
    if(p0&&in_range(p0,0x30)&&in_range(rdptr(p0+OFF_Class),0x30)){ class_name(p0,pc,sizeof pc); obj_name(p0,pn,sizeof pn); }
    LOGI("[SKIN] %s  self=%s:%s  p0=%s:%s",fp,sc,sn,pc,pn); }
// ============ Extra avatar-menu boxes (flag tribemod/skin_menu) ============
// One box per .glb in tribemod/skins/ is added to Tribe's avatar list (W_ProfileMenu's "AvatarList", a UListView): we
// SpawnObject a fresh BP_ReadyPlayerMeAvatarSkin_C per character, ListView.AddItem() it (Tribe then builds a W_SkinItem
// box for it), and relabel the box's NameText with the file name. Clicking one of OUR boxes is swallowed at both entry
// points Tribe uses (the box's OnMouseButtonDown and the menu's AvatarList item handler) so Tribe never tries to apply an
// RPM skin, and the mod loads that .glb instead. Blueprint-internal calls are invisible to ProcessEvent; these two are not.
#define SM_MAX 8
static volatile sig_atomic_t g_skinMenuOn=0, g_smCount=0;
static char g_smFiles[SM_MAX][128], g_smLabels[SM_MAX][64];               // written by the poll thread
static uintptr_t g_smItems[SM_MAX];                                          // our skin objects (game thread)
static uintptr_t g_smList=0, g_smTribeRpm=0, g_smRpmCls=0;
static uintptr_t g_smFnAddItem=0, g_smFnIndexOf=0, g_smFnSpawn=0, g_smGS=0, g_smFnStr2Txt=0, g_smKTL=0, g_smFnSetText=0;
static uintptr_t g_smFnObjSet=0, g_smFnMouseDown=0, g_smFnListEvt=0;
static uintptr_t g_smW[32]; static int g_smWi[32];                            // W_SkinItem box -> index of our item
static long g_smLastClickMs=0; static int g_smLastClickIdx=-1;
// 2311 (mod2311 step B): 0 = not known yet, 1 = Tribe 0.12.6's C++ menu (TribeReadyPlayerMeAvatarSkin exists), 2 = 2304
static volatile sig_atomic_t g_smTribeMode=0, g_smAdded=0, g_smListLive=0;
static void menu_tick_2311();
static uintptr_t find_prop(uintptr_t cls,const char* pname){                 // FProperty* by name (class + supers)
    char nm[128];
    for(uintptr_t c=cls; c; c=rdptr(c+OFF_Super)){
        for(uintptr_t f=rdptr(c+OFF_ChildProps); f; f=rdptr(f+FF_Next)){
            fname_resolve(rd32(f+FF_Name),nm,sizeof nm); if(!strcmp(nm,pname)) return f; } }
    return 0; }
static bool obj_alive(uintptr_t o){ return obj_live(o); }   // (defined with the call check, near call_uf)
static int sm_item_idx(uintptr_t o){ if(!o) return -1; int n=g_smCount; for(int i=0;i<n&&i<SM_MAX;i++) if(g_smItems[i]==o) return i; return -1; }
static int sm_widget_idx(uintptr_t w){ for(int i=0;i<32;i++) if(g_smW[i]==w) return g_smWi[i]; return -1; }
static void sm_map_widget(uintptr_t w,int idx){
    int free=-1; for(int i=0;i<32;i++){ if(g_smW[i]==w){ if(idx<0) g_smW[i]=0; else g_smWi[i]=idx; return; } if(!g_smW[i]&&free<0) free=i; }
    if(idx>=0&&free>=0){ g_smW[free]=w; g_smWi[free]=idx; } }
// FText from ASCII via KismetTextLibrary.Conv_StringToText. The FText bytes are copied out without touching the refcount;
// the param buffer is never destructed, so the text data just stays alive (a few bytes, never freed twice).
static int make_text(const char* s,uint8_t* out,int cap){
    static int oIn=-2,oRet=-1,sz=0; if(!g_smFnStr2Txt||!g_smKTL) return 0;
    if(oIn==-2){ oIn=prop_offset(g_smFnStr2Txt,"InString",0); uintptr_t f=find_prop(g_smFnStr2Txt,"ReturnValue");
        oRet=f?(int)rd32(f+FP_Offset):-1; sz=f?(int)rd32(f+FP_ElemSize):0;
        int fb=(oRet>=0)?(int)rd16(g_smFnStr2Txt+0xB6)-oRet:0;               // ReturnValue is the last param
        LOGI("[MENU] Conv_StringToText InString@%d ReturnValue@%d elemSize=%d (raw +0x30=%u +0x34=%u +0x38=%u) psz=0x%x -> using %d",
            oIn,oRet,sz,f?rd32(f+0x30):0,f?rd32(f+0x34):0,f?rd32(f+0x38):0,rd16(g_smFnStr2Txt+0xB6),(sz>=8&&sz<=32)?sz:fb);
        if(!(sz>=8&&sz<=32)) sz=fb; }
    uint16_t psz=rd16(g_smFnStr2Txt+0xB6); static uint8_t b[256]; static uint16_t buf[128];
    if(oIn<0||oRet<0||sz<=0||sz>cap||psz>sizeof b) return 0;
    int i=0; for(;s[i]&&i<127;i++) buf[i]=(uint16_t)(uint8_t)s[i]; buf[i]=0;
    FStr fs={buf,i+1,i+1}; memset(b,0,psz); memcpy(b+oIn,&fs,sizeof fs);
    call_uf(g_smKTL,g_smFnStr2Txt,b); memcpy(out,b+oRet,sz); return sz; }
static void box_set_label(uintptr_t box,const char* label){                  // box.NameText.SetText(label) -- avatar + environment boxes
    static int oName=-2,oT=-1; if(!g_smFnSetText||!box||!label) return;
    if(oName==-2){ oName=prop_offset(rdptr(box+OFF_Class),"NameText",0); oT=prop_offset(g_smFnSetText,"InText",0);
        LOGI("[MENU] W_SkinItem.NameText@%d SetText.InText@%d psz=0x%x",oName,oT,rd16(g_smFnSetText+0xB6)); }
    uintptr_t tb=oName>=0?rdptr(box+oName):0; uint16_t psz=rd16(g_smFnSetText+0xB6); uint8_t txt[64]; static uint8_t b[128];
    if(!tb||oT<0||psz>sizeof b) return; int n=make_text(label,txt,sizeof txt); if(n<=0||oT+n>psz) return;
    memset(b,0,psz); memcpy(b+oT,txt,n); call_uf(tb,g_smFnSetText,b); }
static void sm_label_box(uintptr_t box,int idx){ if(idx>=0&&idx<SM_MAX) box_set_label(box,g_smLabels[idx]); }
static uintptr_t sm_spawn(uintptr_t cls,uintptr_t outer){                    // GameplayStatics.SpawnObject(Class, Outer)
    static int oC=-2,oO=-1,oR=-1;
    if(oC==-2){ oC=prop_offset(g_smFnSpawn,"ObjectClass",0); oO=prop_offset(g_smFnSpawn,"Outer",0); oR=prop_offset(g_smFnSpawn,"ReturnValue",0);
        LOGI("[MENU] SpawnObject ObjectClass@%d Outer@%d ReturnValue@%d psz=0x%x",oC,oO,oR,rd16(g_smFnSpawn+0xB6)); }
    uint16_t psz=rd16(g_smFnSpawn+0xB6); uint8_t b[64]; if(oC<0||oO<0||oR<0||psz>sizeof b) return 0;
    memset(b,0,psz); *(uintptr_t*)(b+oC)=cls; *(uintptr_t*)(b+oO)=outer; call_uf(g_smGS,g_smFnSpawn,b); return *(uintptr_t*)(b+oR); }
static int sm_list_index(uintptr_t list,uintptr_t item){                     // ListView.GetIndexForItem (-1 = absent)
    static int oI=-2,oR=-1; if(oI==-2){ oI=prop_offset(g_smFnIndexOf,"Item",0); oR=prop_offset(g_smFnIndexOf,"ReturnValue",0); }
    uint16_t psz=rd16(g_smFnIndexOf+0xB6); uint8_t b[32]; if(oI<0||oR<0||psz>sizeof b) return -2;
    memset(b,0,psz); *(uintptr_t*)(b+oI)=item; call_uf(list,g_smFnIndexOf,b); return *(int32_t*)(b+oR); }
static void sm_list_add(uintptr_t list,uintptr_t item){
    static int o=-2; if(o==-2) o=prop_offset(g_smFnAddItem,"Item",0);
    uint16_t psz=rd16(g_smFnAddItem+0xB6); uint8_t b[32]; if(o<0||psz>sizeof b) return;
    memset(b,0,psz); *(uintptr_t*)(b+o)=item; call_uf(list,g_smFnAddItem,b); }
static void sm_load(int idx){                                                // switch character to our box's .glb
    struct timespec ts; clock_gettime(CLOCK_MONOTONIC,&ts); long ms=ts.tv_sec*1000L+ts.tv_nsec/1000000L;
    if(ms-g_smLastClickMs<(idx==g_smLastClickIdx?3000:700)) return; g_smLastClickMs=ms; g_smLastClickIdx=idx;   // one click
    char p[600]; snprintf(p,sizeof p,"%s/active_skin.txt",OUTDIR);
    int fd=open(p,O_WRONLY|O_CREAT|O_TRUNC,0666); if(fd>=0){ write(fd,g_smFiles[idx],strlen(g_smFiles[idx])); close(fd); }
    g_load_req=1; LOGI("[MENU] clicked '%s' -> loading %s",g_smLabels[idx],g_smFiles[idx]); }
// game thread, every frame from our actor's tick: keep our boxes in the live AvatarList (re-adds after Tribe rebuilds it)
static void menu_tick(){
    static int tk=0, spawns=0, win=0; static bool tripped=false;
    if(!g_skinMenuOn||tripped||(++tk%60)!=0) return;                         // ~once a second
    if(g_smMode==1){ menu_tick_2311(); return; }                             // 2311: its own path (below)
    if(++win>=30){ win=0; spawns=0; }                                        // 30 s window for the respawn guard
    uintptr_t list=g_smList; int n=g_smCount;
    if(!list||!obj_alive(list)||!g_smRpmCls||!g_smFnSpawn||!g_smFnAddItem||!g_smFnIndexOf||n<=0) return;
    uintptr_t outer=(g_smTribeRpm&&obj_alive(g_smTribeRpm))?rdptr(g_smTribeRpm+OFF_Outer):list;   // fallback: the list
    for(int i=0;i<n&&i<SM_MAX;i++){
        if(!obj_alive(g_smItems[i])){
            if(spawns>=3*n){ tripped=true; LOGI("[MENU] guard: %d respawns in 30 s -> stopped adding boxes (bug guard)",spawns); return; }
            g_smItems[i]=sm_spawn(g_smRpmCls,outer); spawns++;
            LOGI("[MENU] spawned skin object for '%s' = 0x%lx",g_smLabels[i],(unsigned long)g_smItems[i]); }
        if(g_smItems[i]){ int ix=sm_list_index(list,g_smItems[i]);
            if(ix<0){ sm_list_add(list,g_smItems[i]); LOGI("[MENU] added box '%s' (index was %d)",g_smLabels[i],ix); } } }
    for(int w=0;w<32;w++) if(g_smW[w]){                                      // keep our labels (Tribe may rewrite NameText)
        if(!obj_alive(g_smW[w])){ g_smW[w]=0; continue; } sm_label_box(g_smW[w],g_smWi[w]); } }
// ============ Custom environments (flag tribemod/env_menu) ============
// Our own boxes in Tribe's environment list (W_VisualsMenu's "EnvironmentList": the same UListView + W_SkinItem boxes as
// the avatar list), one per line of tribemod/envs.txt ("Label=/Game/Long/Package/Name"; no file = one "Festival" box).
// Tribe's environments are a fixed native enum (ETribeEnvironmentType -> /Game/Maps/Environments/<Name>, NOTES Session
// 3m), so a new one can't be added as data. Clicking our box instead (1) switches Tribe to The Void (its lights + screens,
// no scenery), (2) hides the Void's two screens, (3) streams OUR level in from a mod pak (patch OBB) with
// LevelStreamingDynamic.LoadLevelInstance and (4) waits until it is visible. Picking a stock environment unloads ours.
// The choice persists in tribemod/active_env.txt and is re-applied once Tribe's own saved environment has settled after
// launch. Every stage logs [ENV], so a failure shows where it stopped (box / base switch / level found / visible).
#define EM_MAX 8
enum { EM_IDLE=0, EM_WAIT_BASE, EM_WAIT_LOAD, EM_ACTIVE };
static volatile sig_atomic_t g_envMenuOn=0, g_emCount=0, g_emReq=-1, g_emUnloadReq=0, g_emState=EM_IDLE, g_emActive=-1;
static char g_emLabels[EM_MAX][64], g_emPaths[EM_MAX][256];                  // written by the poll thread
static volatile int g_emLoadGen=0;                                          // +1 at every stage load and unload (show bus)
static volatile sig_atomic_t g_emAdded=0, g_emListLive=0;                   // our boxes in the live list / the list exists
static volatile sig_atomic_t g_emTribeSwitched=0;                           // Tribe left our stage by itself this session
static char g_emStockName[64]="";                                           // a stock environment you picked (game thread)
static volatile sig_atomic_t g_emFailed=0;                                  // a load failed (the supervisor retries it)
static bool em_active_folder(char* out,size_t n){      // "/Game/Mods/Club/Maps/X.X" -> "club"; false if none of ours is up
    int a=g_emActive; if(g_emState!=EM_ACTIVE||a<0||a>=EM_MAX||n<2) return false;
    const char* q=strstr(g_emPaths[a],"/Game/Mods/"); if(!q) return false; q+=11;
    size_t k=0; for(; q[k]&&q[k]!='/'&&q[k]!='.'&&k+1<n; k++){ char c=q[k]; out[k]=(c>='A'&&c<='Z')?(char)(c+32):c; }
    out[k]=0; return k>0; }
static uintptr_t g_emItems[EM_MAX];                                          // our environment objects (game thread)
static uintptr_t g_emList=0, g_emTribeItem=0, g_emCls=0, g_emGameState=0, g_emRig=0, g_emStream=0, g_emScreens[2];
static uintptr_t g_emFnObjSet=0, g_emFnMouseDown=0, g_emFnListEvt=0, g_emFnSetEnv=0, g_emLSD=0, g_emFnBounds=0;
static uintptr_t g_emFnIsLoaded=0, g_emFnIsVisible=0, g_emFnSetLoaded=0, g_emFnSetVisible=0, g_emFnHidden=0;
static uintptr_t g_emFnActLoc=0, g_emFnActRot=0, g_emFnActScale=0, g_emEnum=0, g_emFnGetGS=0, g_emActorCls=0;
static uintptr_t g_emFnFileExists=0, g_emFnContentDir=0, g_emBPL=0;          // diagnostics: what the engine's file system can see
static uintptr_t g_emFnCurLevel=0, g_emFnMakeSOP=0, g_emFnSOP2Ref=0, g_emKSL=0, g_emFnLoadLvlSoft=0;
static uintptr_t g_emVoidItem=0; static uintptr_t g_emIdentOf[EM_MAX];        // Tribe's "The Void" list item; which of ours carry its identity
static int64_t g_emVoid=-1; static int g_emEnvOff=-1, g_emT=0, g_emPrevEnv=-1; static long g_emLastClickMs=0;
static uintptr_t g_emW[32]; static int g_emWi[32];                            // W_SkinItem box -> index of our item
// 0.12.6 (2311): the menus are C++ (TribeVisualsMenuWidget, TribeSkinItemWidget, TribeEnvironmentSkin) and the Blueprint
// events above are gone. Read from the 2311 library: a box's native NativeOnMouseButtonDown calls the engine's first (which
// raises UserWidget.OnMouseButtonDown through ProcessEvent), then VisualsManager.ApplySkinToPlayer(Skin); ApplySkin sets the
// environment and broadcasts the skin's OnApplied, which InitSkinItem bound to the box's OnSkinApplied (ProcessEvent too).
// g_emMode: 0 = not known yet, 1 = native menu (2311), 2 = Blueprint menu (2304).
static volatile sig_atomic_t g_emMode=0;
static uintptr_t g_emWCls=0, g_emFnUWDown=0, g_emFnSkinApplied=0; static int g_emOffWSkin=-1;
static int em_item_idx(uintptr_t o){ if(!o) return -1; int n=g_emCount; for(int i=0;i<n&&i<EM_MAX;i++) if(g_emItems[i]==o) return i; return -1; }
static int em_widget_idx(uintptr_t w){ for(int i=0;i<32;i++) if(g_emW[i]==w) return g_emWi[i]; return -1; }
static void em_map_widget(uintptr_t w,int idx){
    int free=-1; for(int i=0;i<32;i++){ if(g_emW[i]==w){ if(idx<0) g_emW[i]=0; else g_emWi[i]=idx; return; } if(!g_emW[i]&&free<0) free=i; }
    if(idx>=0&&free>=0){ g_emW[free]=w; g_emWi[free]=idx; } }
// Give our freshly spawned list item the identity of Tribe's own "The Void" item: copy its simple fields (Name = the
// environment-table row, EnvironmentType, the owned/subscribed/hidden flags, ints). A default item has Name=None and
// bIsOwned=false, so Tribe showed a "Load" button and applying it set environment None (dark decks, 2026-10-04).
// Only plain-old-data properties are copied (no text/strings/objects/structs: no refcounts to break).
static int em_copy_identity(uintptr_t dst,uintptr_t src){
    int S=calib_fprop_size(); if(!dst||!src||S<0) return -1; char nm[128],ty[64]; int n=0;
    if(rdptr(dst+OFF_Class)!=rdptr(src+OFF_Class)){ static int w=0; if(w++<5) LOGI("[ENV] identity: not copied (the two objects' classes differ)"); return -1; }   // mod2311
    for(uintptr_t c=rdptr(src+OFF_Class); c; c=rdptr(c+OFF_Super))
        for(uintptr_t f=rdptr(c+OFF_ChildProps); f; f=rdptr(f+FF_Next)){
            ffield_type(f,ty,sizeof ty); uint32_t off=rd32(f+FP_Offset); int sz=0;
            if(!strcmp(ty,"BoolProperty")){ uint8_t bo=rd8(f+S+1), bm=rd8(f+S+2);
                uint8_t v=(rd8(dst+off+bo)&~bm)|(rd8(src+off+bo)&bm); *(volatile uint8_t*)(dst+off+bo)=v; n++; continue; }
            if(!strcmp(ty,"NameProperty")) sz=8; else if(!strcmp(ty,"IntProperty")) sz=4;
            else if(!strcmp(ty,"EnumProperty")||!strcmp(ty,"ByteProperty")) sz=1;
            if(!sz) continue;
            memcpy((void*)(dst+off),(const void*)(src+off),sz); n++;
            if(!strcmp(ty,"NameProperty")){ fname_resolve(rd32(f+FF_Name),nm,sizeof nm); char v[96]; fname_resolve(rd32(dst+off),v,sizeof v);
                LOGI("[ENV] identity: %s = %s",nm,v); } }
    return n; }
static int em_cur_env(){ return (g_emEnvOff>=0&&g_emGameState&&obj_alive(g_emGameState))?(int)rd8(g_emGameState+g_emEnvOff):-1; }
static const char* em_env_name(int v){ static char lab[64]; snprintf(lab,sizeof lab,"?"); if(g_emEnum&&v>=0) enum_label(g_emEnum,v,lab,sizeof lab); return lab; }
static int em_find_env_prop(uintptr_t gs){              // offset of the game state's ETribeEnvironmentType property (-1: not reflected)
    int S=calib_fprop_size(); if(!gs||S<0) return -1; char nm[128],ty[64],en[96];
    for(uintptr_t c=rdptr(gs+OFF_Class); c; c=rdptr(c+OFF_Super))
        for(uintptr_t f=rdptr(c+OFF_ChildProps); f; f=rdptr(f+FF_Next)){
            ffield_type(f,ty,sizeof ty); bool isEnum=!strcmp(ty,"EnumProperty"); if(!isEnum&&strcmp(ty,"ByteProperty")) continue;
            uintptr_t e=rdptr(f+S+(isEnum?8:0)); if(!e||!in_range(e,0x50)) continue;
            obj_name(e,en,sizeof en); if(strcmp(en,"ETribeEnvironmentType")) continue;
            fname_resolve(rd32(f+FF_Name),nm,sizeof nm); g_emEnum=e;
            LOGI("[ENV] game state's environment property: %s (%s) @0x%x",nm,ty,rd32(f+FP_Offset)); return (int)rd32(f+FP_Offset); }
    return -1; }
// Fallback when GameplayStatics.GetGameState comes back null for every world context we try (2026-10-05 16:58: a whole
// session of "click ignored, not ready: gs=0x0" while our actor, the menu and the rig all existed): find Tribe's game state
// by its class in the object array, the way the gear scan sees it. Newest live, non-template instance wins.
// The class: TribeMainGameState on 0.12.6 (2311, C++), TribeMainGS_C on 2304 (Blueprint).
static uintptr_t em_find_gs_by_class(){
    refresh_numelements(); char cn[64]; uintptr_t best=0;
    for(uint32_t i=0;i<g_numElements;i++){ uintptr_t o=obj_at(i); if(!o) continue;
        if(rd32(o+OFF_Flags)&(RF_ClassDefaultObject|0x20u|0x40000000u)) continue;
        class_name(o,cn,sizeof cn); if(!strcmp(cn,"TribeMainGameState")||!strcmp(cn,"TribeMainGS_C")) best=o; }
    return best; }
// ---- Tribe's visuals on our screen (2026-10-06). Every stock environment's level BP calls
// BP_TribeVisualsManager_C.SetupEnvironmentBackdrop(BackdropMesh, ChromaKeyBackdropMesh) in BeginPlay (2311: the C++
// TribeVisualsManager.SetupEnvironmentBackdrop(BackdropMesh, InBoothSpotlight, InBackdropSpotlight, InRoomSkyLight,
// InLightDimFactor), see em_backdrop_2311); Tribe then draws its
// visuals (videos, GIFs, text, images, NDI) onto that actor's mesh and shows/hides it with the visuals mode. Our level has
// no level BP, so after it is visible we make the same call with our SM_DinoVisualScreen actor.
static uintptr_t em_find_child_func(uintptr_t cls,const char* name){
    char nm[128]; int d=0;
    for(uintptr_t c=cls; c&&d<12; c=rdptr(c+OFF_Super),d++)
        for(uintptr_t f=rdptr(c+OFF_Children); f; f=rdptr(f+0x28)){ obj_name(f,nm,sizeof nm); if(!strcmp(nm,name)) return f; }
    return 0; }
static uintptr_t em_find_live(const char* clsName){                 // newest live, non-template object of a class
    refresh_numelements(); char cn[96]; uintptr_t best=0;
    for(uint32_t i=0;i<g_numElements;i++){ uintptr_t o=obj_at(i); if(!o) continue;
        if(rd32(o+OFF_Flags)&(RF_ClassDefaultObject|0x20u|0x40000000u)) continue;
        class_name(o,cn,sizeof cn); if(!strcmp(cn,clsName)) best=o; }
    return best; }
static uintptr_t em_find_live_pl(const char* clsName){             // first live object of EXACTLY this class in a world level
    refresh_numelements(); char cn[128],fp[400];                    // (find_live_class_sub, but "TribeRig" must not hit TribeRigSkin)
    for(uint32_t i=0;i<g_numElements;i++){ uintptr_t o=obj_at(i); if(!o) continue;
        class_name(o,cn,sizeof cn); if(strcmp(cn,clsName)) continue;
        if(rd32(o+OFF_Flags)&RF_ClassDefaultObject) continue;
        full_path(o,fp,sizeof fp); if(strstr(fp,"Default__")||!strstr(fp,"PersistentLevel")) continue;
        return o; } return 0; }
static bool em_is_a(uintptr_t o,const char* clsName){                // o's class, or one of its supers, is named clsName
    char cn[96]; int d=0;
    for(uintptr_t c=o?rdptr(o+OFF_Class):0; c&&d<16; c=rdptr(c+OFF_Super),d++){ obj_name(c,cn,sizeof cn); if(!strcmp(cn,clsName)) return true; }
    return false; }
// The weak half of a TSoftObjectPtr (FWeakObjectPtr {int32 ObjectIndex, int32 SerialNumber} at its start), resolved as
// FWeakObjectPtr::Get does in the 2311 library (store 0x1A366AC): serial != 0, index < NumElements, the item's SerialNumber
// (+0x10) matches, and its flags (+8) carry neither Garbage (1<<21) nor Unreachable (1<<28). Reads only.
// 1 = a live object (*out), 0 = an empty soft pointer (*out = 0), -1 = set but not resolvable (a path only, stale, garbage).
static int em_soft_get(uintptr_t sp,uintptr_t* out){
    *out=0; int32_t idx=(int32_t)rd32(sp), ser=(int32_t)rd32(sp+4);
    if(!ser){ uint64_t p0=0,p1=0; sr(sp+8,&p0,8); sr(sp+16,&p1,8); return (p0||p1||rd32(sp+0x20))?-1:0; }   // path FNames, SubPathString.Num
    refresh_numelements(); if(idx<0||(uint32_t)idx>=g_numElements) return -1;
    uintptr_t chunk=rdptr(g_chunks+(uintptr_t)(idx>>16)*8); if(!chunk) return -1;
    uintptr_t item=chunk+(uintptr_t)(idx&0xFFFF)*ITEM_STRIDE;
    if((int32_t)rd32(item+0x10)!=ser||(rd32(item+8)&gc_dead_mask())) return -1;   // step C: 5.4 rotates the unreachable flag
    uintptr_t o=rdptr(item); if(!o||!in_range(o,0x30)||rd32(o+OFF_Index)!=(uint32_t)idx) return -1;
    *out=o; return 1; }
static uintptr_t em_find_mesh_actor(const char* meshName){          // the actor whose StaticMeshComponent shows that mesh
    static int offSM=-2; refresh_numelements(); char cn[64], nm[96];
    for(uint32_t i=0;i<g_numElements;i++){ uintptr_t o=obj_at(i); if(!o) continue;
        if(rd32(o+OFF_Flags)&(RF_ClassDefaultObject|0x20u|0x40000000u)) continue;
        class_name(o,cn,sizeof cn); if(strcmp(cn,"StaticMeshComponent")) continue;
        if(offSM==-2) offSM=prop_offset(rdptr(o+OFF_Class),"StaticMesh",0);
        if(offSM<0) return 0;
        uintptr_t sm=rdptr(o+offSM); if(!sm) continue; obj_name(sm,nm,sizeof nm); if(strcmp(nm,meshName)) continue;
        uintptr_t owner=rdptr(o+OFF_Outer); if(owner&&obj_alive(owner)) return owner; }
    return 0; }
static int em_actor_hidden(uintptr_t a){                             // AActor.bHidden (1/0), -1 = unreadable
    int S=calib_fprop_size(); if(!a||!obj_alive(a)||S<0) return -1;
    uintptr_t f=find_prop(rdptr(a+OFF_Class),"bHidden"); if(!f) return -1;
    uint32_t off=rd32(f+FP_Offset); uint8_t bo=rd8(f+S+1), bm=rd8(f+S+2); return (rd8(a+off+bo)&bm)?1:0; }
static void em_actor_material(uintptr_t a,char* out,int n){           // the name of its StaticMeshComponent's material 0
    snprintf(out,n,"?"); static uintptr_t fnGetMat=0; if(!fnGetMat) fnGetMat=find_by_path("/Script/Engine.PrimitiveComponent.GetMaterial",0);
    if(!a||!obj_alive(a)||!fnGetMat) return; int oC=prop_offset(rdptr(a+OFF_Class),"StaticMeshComponent",0); if(oC<0) return;
    uintptr_t comp=rdptr(a+oC); if(!comp) return; int oI=prop_offset(fnGetMat,"ElementIndex",0), oR=prop_offset(fnGetMat,"ReturnValue",0);
    uint16_t psz=rd16(fnGetMat+0xB6); static uint8_t b[32] __attribute__((aligned(8))); if(oI<0||oR<0||psz>sizeof b) return;
    memset(b,0,psz); call_uf(comp,fnGetMat,b); uintptr_t m=*(uintptr_t*)(b+oR); if(m) obj_name(m,out,n); else snprintf(out,n,"(none)"); }
// ---- Tribe's video mapping on our screen (2026-10-06, decoded from Tribe's M_VideoBackdrop shader + MPC_VideoBackdrop
// asset). The shader samples the video at (1-U, 2V-1) of the screen's UV0 (our SM_DinoVisualScreen copies that layout) and
// then applies the collection: scalars Aspect, Tile, Mirror and the vector StretchMode. StretchMode.z > 0.5 fills the
// screen; otherwise it crops/pillarboxes for Tribe's own ~2.5:1 back wall, and Tile >= 0.5 draws two copies side by side.
// On our 16:9 screen we fill it with one copy while the Dino Stage is up, and give Tribe its values back when it unloads.
static uintptr_t g_mpcColl=0, g_mpcFnSetS=0, g_mpcFnSetV=0, g_mpcFnGetS=0, g_mpcFnGetV=0, g_mpcLib=0;
static uint64_t g_mpcStretch=0, g_mpcTile=0;                          // the parameters' FNames {ComparisonIndex, Number}
static bool g_mpcSaved=false; static float g_mpcTribeStretch[4], g_mpcTribeTile=0;
static uint64_t mpc_param_name(uintptr_t coll,const char* arr,int stride,const char* want){
    int o=prop_offset(rdptr(coll+OFF_Class),arr,0); if(o<0) return 0;
    uintptr_t data=rdptr(coll+o); int n=(int)rd32(coll+o+8); char nm[64];
    for(int i=0;i<n&&i<64;i++){ uintptr_t e=data+(uintptr_t)i*stride; fname_resolve(rd32(e),nm,sizeof nm);
        if(!strcmp(nm,want)){ uint64_t v=0; sr(e,&v,8); return v; } }
    return 0; }
static void mpc_lookup(){                                             // POLL thread (walks every object): until all found
    static int tries=0; if(g_mpcStretch&&g_mpcTile&&g_mpcLib&&g_mpcFnGetV) return; if(tries>=30) return; tries++;
    if(!g_mpcLib){ g_mpcLib=find_by_path("/Script/Engine.Default__KismetMaterialLibrary",0);
        g_mpcFnSetS=find_by_path("/Script/Engine.KismetMaterialLibrary.SetScalarParameterValue",0);
        g_mpcFnSetV=find_by_path("/Script/Engine.KismetMaterialLibrary.SetVectorParameterValue",0);
        g_mpcFnGetS=find_by_path("/Script/Engine.KismetMaterialLibrary.GetScalarParameterValue",0);
        g_mpcFnGetV=find_by_path("/Script/Engine.KismetMaterialLibrary.GetVectorParameterValue",0); }
    if(!g_mpcColl) g_mpcColl=find_by_path("/Game/Environment/Materials/MPC_VideoBackdrop.MPC_VideoBackdrop",0);
    if(g_mpcColl){ g_mpcStretch=mpc_param_name(g_mpcColl,"VectorParameters",40,"StretchMode");   // FName+FGuid+FLinearColor
                   g_mpcTile=mpc_param_name(g_mpcColl,"ScalarParameters",28,"Tile"); }          // FName+FGuid+float
    bool ok=g_mpcColl&&g_mpcLib&&g_mpcFnSetS&&g_mpcFnSetV&&g_mpcFnGetS&&g_mpcFnGetV&&g_mpcStretch&&g_mpcTile;
    LOGI("[ENV] video mapping lookups: collection=0x%lx lib=0x%lx set=%d/%d get=%d/%d StretchMode=%d Tile=%d%s",(unsigned long)g_mpcColl,
         (unsigned long)g_mpcLib,!!g_mpcFnSetS,!!g_mpcFnSetV,!!g_mpcFnGetS,!!g_mpcFnGetV,!!g_mpcStretch,!!g_mpcTile,ok?"":" (not all found yet)"); }
static bool mpc_resolve(){                                            // game thread: only the cached lookups
    return g_mpcColl&&obj_alive(g_mpcColl)&&g_mpcStretch&&g_mpcTile&&g_mpcFnSetS&&g_mpcFnSetV&&g_mpcFnGetS&&g_mpcFnGetV&&g_mpcLib; }
// one KismetMaterialLibrary call on the collection: get (val out) or set (val in); vec = FLinearColor, else float
static bool mpc_call_on(uintptr_t coll,uintptr_t fn,uintptr_t ctx,uint64_t name,float* val,bool vec,bool set);
static bool mpc_call(uintptr_t fn,uintptr_t ctx,uint64_t name,float* val,bool vec,bool set){ return mpc_call_on(g_mpcColl,fn,ctx,name,val,vec,set); }
static bool mpc_call_on(uintptr_t coll,uintptr_t fn,uintptr_t ctx,uint64_t name,float* val,bool vec,bool set){
    uint16_t psz=rd16(fn+0xB6); static uint8_t b[64] __attribute__((aligned(16))); if(psz>sizeof b) return false;
    int oW=prop_offset(fn,"WorldContextObject",0), oC=prop_offset(fn,"Collection",0), oN=prop_offset(fn,"ParameterName",0);
    int oV=prop_offset(fn,set?"ParameterValue":"ReturnValue",0); if(oW<0||oC<0||oN<0||oV<0) return false;
    memset(b,0,psz); *(uintptr_t*)(b+oW)=ctx; *(uintptr_t*)(b+oC)=coll; memcpy(b+oN,&name,8);
    if(set) memcpy(b+oV,val,vec?16:4);
    call_uf(g_mpcLib,fn,b);
    if(!set) memcpy(val,b+oV,vec?16:4);
    return true; }
static void em_video_fill(bool on,uintptr_t ctx){                     // on: fill + one copy (remember Tribe's); off: restore
    if(!ctx||!mpc_resolve()) return;
    if(!on){ if(!g_mpcSaved) return; g_mpcSaved=false;
        mpc_call(g_mpcFnSetV,ctx,g_mpcStretch,g_mpcTribeStretch,true,true); mpc_call(g_mpcFnSetS,ctx,g_mpcTile,&g_mpcTribeTile,false,true);
        LOGI("[ENV] video mapping: Tribe's restored (StretchMode=(%.0f,%.0f,%.0f) Tile=%.0f)",g_mpcTribeStretch[0],g_mpcTribeStretch[1],
             g_mpcTribeStretch[2],g_mpcTribeTile); return; }
    float st[4]={0,0,0,0}, tile=0;
    if(!mpc_call(g_mpcFnGetV,ctx,g_mpcStretch,st,true,false)||!mpc_call(g_mpcFnGetS,ctx,g_mpcTile,&tile,false,false)) return;
    if(st[0]<0.5f&&st[1]<0.5f&&st[2]>0.5f&&tile<0.5f) return;      // already ours
    memcpy(g_mpcTribeStretch,st,sizeof st); g_mpcTribeTile=tile; g_mpcSaved=true;   // Tribe (re)applied its own: keep it for later
    float fill[4]={0,0,1,0}, one=0;
    mpc_call(g_mpcFnSetV,ctx,g_mpcStretch,fill,true,true); mpc_call(g_mpcFnSetS,ctx,g_mpcTile,&one,false,true);
    LOGI("[ENV] video mapping: Tribe had StretchMode=(%.0f,%.0f,%.0f) Tile=%.0f -> fill the big screen, one copy",st[0],st[1],st[2],tile); }
static uintptr_t g_emOurScreen=0, g_emVM=0;
// 2311: SetupEnvironmentBackdrop(BackdropMesh, InBoothSpotlight, InBackdropSpotlight, InRoomSkyLight, InLightDimFactor).
// Tribe's C++ body (store 0x5B58958) stores BackdropMesh and reads its StaticMeshComponent at +0x290 with no class check,
// null-checks the three lights and keeps each as a soft pointer (plus the booth and sky intensities), and stores the dim
// factor. We hand back what the Void's own call left in the manager, so its lighting stays as Tribe set it. Anything we
// can't read or resolve -> no call (logged; em_register_backdrop is retried).
static bool em_backdrop_2311(uintptr_t vm,uintptr_t scr,uint8_t* b,const int* oL,int oD){
    static const char* const SP[3]={"BoothSpotlight","BackdropSpotlight","RoomSkyLight"};
    static const char* const LC[3]={"SpotLight","SpotLight","SkyLight"};
    uintptr_t cls=rdptr(vm+OFF_Class), L[3]={0,0,0}; char ty[64], cn[96];
    if(!em_is_a(scr,"StaticMeshActor")){ class_name(scr,cn,sizeof cn);
        LOGI("[ENV] visuals: our screen is a %s, not a StaticMeshActor (Tribe reads +0x290 of it) -> SetupEnvironmentBackdrop NOT called",cn); return false; }
    for(int i=0;i<3;i++){ uintptr_t fc=0; int o=prop_offset(cls,SP[i],&fc); ty[0]=0; if(fc) fname_resolve(rd32(fc),ty,sizeof ty);
        if(o<0||strcmp(ty,"SoftObjectProperty")){ LOGI("[ENV] visuals: manager %s is %s@%d, not a soft pointer -> SetupEnvironmentBackdrop NOT called",
                                                       SP[i],ty[0]?ty:"missing",o); return false; }
        if(em_soft_get(vm+(uintptr_t)o,&L[i])<0){ LOGI("[ENV] visuals: manager %s is set but doesn't resolve (index %d serial %d) -> SetupEnvironmentBackdrop NOT called yet",
                                                      SP[i],(int)rd32(vm+(uintptr_t)o),(int)rd32(vm+(uintptr_t)o+4)); return false; }
        if(L[i]&&!em_is_a(L[i],LC[i])){ class_name(L[i],cn,sizeof cn);
            LOGI("[ENV] visuals: manager %s resolves to a %s, not a %s -> SetupEnvironmentBackdrop NOT called",SP[i],cn,LC[i]); return false; } }
    uintptr_t fd=0; int od=prop_offset(cls,"LightDimFactor",&fd); ty[0]=0; if(fd) fname_resolve(rd32(fd),ty,sizeof ty); double dim=0;
    if(od<0||strcmp(ty,"DoubleProperty")||!sr(vm+(uintptr_t)od,&dim,8)||!(dim==dim)||fabs(dim)>1e6){
        LOGI("[ENV] visuals: manager LightDimFactor unreadable (%s@%d) -> SetupEnvironmentBackdrop NOT called",ty[0]?ty:"missing",od); return false; }
    for(int i=0;i<3;i++) memcpy(b+oL[i],&L[i],8);
    memcpy(b+oD,&dim,8);
    LOGI("[ENV] visuals: 2311 signature, handing back the manager's booth spot 0x%lx, backdrop spot 0x%lx, room sky light 0x%lx, dim factor %.3f",
         (unsigned long)L[0],(unsigned long)L[1],(unsigned long)L[2],dim);
    return true; }
static bool em_register_backdrop(){
    uintptr_t vm=em_find_live("TribeVisualsManager"); if(!vm) vm=em_find_live("BP_TribeVisualsManager_C");   // 2311 C++ / 2304 Blueprint
    uintptr_t fn=vm?em_find_child_func(rdptr(vm+OFF_Class),"SetupEnvironmentBackdrop"):0;
    uintptr_t scr=em_find_mesh_actor("SM_DinoVisualScreen");
    if(!vm||!fn||!scr){ LOGI("[ENV] visuals: not ready (manager=0x%lx SetupEnvironmentBackdrop=0x%lx our screen=0x%lx)",
                             (unsigned long)vm,(unsigned long)fn,(unsigned long)scr); return false; }
    int oB=prop_offset(fn,"BackdropMesh",0), oC=prop_offset(fn,"ChromaKeyBackdropMesh",0); uint16_t psz=rd16(fn+0xB6);
    int oL[3]={prop_offset(fn,"InBoothSpotlight",0),prop_offset(fn,"InBackdropSpotlight",0),prop_offset(fn,"InRoomSkyLight",0)}, oD=prop_offset(fn,"InLightDimFactor",0);
    bool v2311=oL[0]>=0||oL[1]>=0||oL[2]>=0||oD>=0, bad2311=false;
    if(v2311){ static const char* const PN[4]={"InBoothSpotlight","InBackdropSpotlight","InRoomSkyLight","InLightDimFactor"};
        for(int i=0;i<4;i++){ int o=i<3?oL[i]:oD; uintptr_t pf=find_prop(fn,PN[i]); char ty[64]="";
            if(pf) ffield_type(pf,ty,sizeof ty);
            if(o<0||o+8>psz||strcmp(ty,i<3?"ObjectProperty":"DoubleProperty")) bad2311=true; } }
    static uint8_t b[128] __attribute__((aligned(16)));
    if(oB<0||psz>sizeof b||bad2311){ char pn[96],ty[64]; LOGI("[ENV] visuals: SetupEnvironmentBackdrop params not as expected (BackdropMesh@%d psz=%u):",oB,psz);
        for(uintptr_t f=rdptr(fn+OFF_ChildProps); f; f=rdptr(f+FF_Next)){ fname_resolve(rd32(f+FF_Name),pn,sizeof pn); ffield_type(f,ty,sizeof ty);
            LOGI("[ENV] visuals:   param %s (%s) @%u",pn,ty,rd32(f+FP_Offset)); }
        return false; }
    // The user's "keywall" turned out to be Tribe's visuals back wall (the user: "they run from the media folder inside
    // tribe"), so our big screen is the BackdropMesh. Tribe's Key Backwall (green wall for the stream cameras only) keeps
    // the Void's own chroma screen (2304; the 2311 function has no chroma parameter).
    memset(b,0,psz); *(uintptr_t*)(b+oB)=scr;
    if(v2311){ if(!em_backdrop_2311(vm,scr,b,oL,oD)) return false; }
    else if(oC>=0) *(uintptr_t*)(b+oC)=(g_emScreens[1]&&obj_alive(g_emScreens[1]))?g_emScreens[1]:0;
    call_uf(vm,fn,b); g_emOurScreen=scr; g_emVM=vm;
    em_video_fill(true,vm);
    char mn[96]; em_actor_material(scr,mn,sizeof mn);
    LOGI("[ENV] visuals: our screen 0x%lx is Tribe's backdrop now (manager 0x%lx); hidden=%d material=%s",
         (unsigned long)scr,(unsigned long)vm,em_actor_hidden(scr),mn);
    return true; }
// ---- Tribe's own lights: log them at environment load; tribemod/lights.txt lines "<name part>=<multiplier>" scale the
// matching light components (by component or owner name), e.g. "Booth=2.5". Originals come back when ours unloads.
#define EM_LMAX 24
static uintptr_t g_lComp[EM_LMAX]; static float g_lOrig[EM_LMAX]; static int g_lN=0;
static uintptr_t g_lFnSet=0;
static void em_lights(bool apply){
    char want[8][64]; float mul[8]; int nw=0;
    if(apply){ char pth[600]; snprintf(pth,sizeof pth,"%s/lights.txt",OUTDIR); FILE* f=fopen(pth,"r");
        if(f){ char line[160]; while(nw<8&&fgets(line,sizeof line,f)){ char* eq=strchr(line,'='); if(!eq) continue; *eq=0;
                float m=strtof(eq+1,0); if(m<=0||m>20) continue; snprintf(want[nw],64,"%s",line); mul[nw++]=m; } fclose(f); } }
    if(!g_lFnSet) g_lFnSet=find_by_path("/Script/Engine.LightComponent.SetIntensity",0);
    refresh_numelements(); char cn[64], nm[96], on[96]; int offI=-2, logged=0;
    for(uint32_t i=0;i<g_numElements;i++){ uintptr_t o=obj_at(i); if(!o) continue;
        if(rd32(o+OFF_Flags)&(RF_ClassDefaultObject|0x20u|0x40000000u)) continue;
        class_name(o,cn,sizeof cn); size_t L=strlen(cn); if(L<14||strcmp(cn+L-14,"LightComponent")) continue;
        if(offI==-2) offI=prop_offset(rdptr(o+OFF_Class),"Intensity",0);
        obj_name(o,nm,sizeof nm); uintptr_t ow=rdptr(o+OFF_Outer); if(ow) obj_name(ow,on,sizeof on); else on[0]=0;
        float I=offI>=0?*(float*)(o+offI):-1.f;
        int oU=prop_offset(rdptr(o+OFF_Class),"IntensityUnits",0); int units=oU>=0?(int)rd8(o+oU):-1;   // 0 unitless 1 cd 2 lm 3 EV
        if(logged++<40) LOGI("[ENV] light %s / %s (%s) intensity=%.2f units=%d",on,nm,cn,I,units);
        for(int k=0;k<nw&&apply&&g_lFnSet&&offI>=0;k++){ if(!strstr(on,want[k])&&!strstr(nm,want[k])) continue;
            int j=0; for(;j<g_lN;j++) if(g_lComp[j]==o) break;
            if(j==g_lN){ if(g_lN>=EM_LMAX) break; g_lComp[g_lN]=o; g_lOrig[g_lN++]=I; }
            float target=g_lOrig[j]*mul[k]; static uint8_t b[16] __attribute__((aligned(8))); memset(b,0,sizeof b);
            memcpy(b,&target,4); call_uf(o,g_lFnSet,b);
            LOGI("[ENV] light %s / %s: intensity %.2f -> %.2f (x%.2f from lights.txt)",on,nm,g_lOrig[j],target,mul[k]); break; } } }
static void em_lights_restore(){
    if(!g_lFnSet) return;
    for(int j=0;j<g_lN;j++){ if(!g_lComp[j]||!obj_alive(g_lComp[j])) continue;
        static uint8_t b[16] __attribute__((aligned(8))); memset(b,0,sizeof b); memcpy(b,&g_lOrig[j],4); call_uf(g_lComp[j],g_lFnSet,b); }
    if(g_lN) LOGI("[ENV] lights: %d restored",g_lN); }
static void em_write_active(const char* label){       // your last pick: a mod stage's label, or "stock:<name>" (mod2311: the
    char p[600]; snprintf(p,sizeof p,"%s/active_env.txt",OUTDIR); if(!label||!*label) return;   // mod never deletes it)
    int fd=open(p,O_WRONLY|O_CREAT|O_TRUNC,0666); if(fd>=0){ write(fd,label,strlen(label)); close(fd); } }
static void em_click(int idx){
    struct timespec ts; clock_gettime(CLOCK_MONOTONIC,&ts); long ms=ts.tv_sec*1000L+ts.tv_nsec/1000000L;
    if(ms-g_emLastClickMs<700) return; g_emLastClickMs=ms;                    // both entry points fire for one click
    g_emReq=idx; LOGI("[ENV] clicked '%s' -> %s",g_emLabels[idx],g_emPaths[idx]); }
// 2311, from repl_pe (game thread). func = UserWidget.OnMouseButtonDown (self: any user widget; on a skin box it comes before
// Tribe applies the box's skin) or TribeSkinItemWidget.OnSkinApplied (self: a box bound to the applied skin, parms
// {AppliedSkin, Pawn}). A press on one of OUR boxes, or Tribe applying one of our skin objects, loads that stage; Tribe has
// already switched to The Void then (our objects carry its identity) or kept it (a box that is selected may not re-apply).
// Nothing is swallowed: Tribe's apply is native and runs anyway. A stock environment skin applied while ours is up -> unload.
// OnSkinApplied fires for every apply, also ones Tribe makes by itself, so it counts only right after a press on a skin box
// (press and apply run in the same call), or, for our objects, while no press has been seen at all (then it is the only route).
static long g_emPressMs=-100000; static bool g_emPressSeen=false;          // the last press on any skin box (ours or Tribe's)
static void em_pe_2311(uintptr_t self,uintptr_t func,void* parms){
    struct timespec ts; clock_gettime(CLOCK_MONOTONIC,&ts); long ms=ts.tv_sec*1000L+ts.tv_nsec/1000000L;
    if(func==g_emFnSkinApplied){ uintptr_t sk=*(uintptr_t*)parms; int idx=em_item_idx(sk); bool pressed=ms-g_emPressMs<1000;
        if(idx>=0){ if(self) em_map_widget(self,idx);
            if((idx==g_emActive&&g_emState!=EM_IDLE)||(g_emPressSeen&&!pressed)) return;   // Tribe re-applied it by itself
            LOGI("[ENV] Tribe applied our skin object for '%s' (OnSkinApplied)",g_emLabels[idx]); em_click(idx); return; }
        if(pressed&&sk&&g_emCls&&in_range(sk,0x30)&&rdptr(sk+OFF_Class)==g_emCls&&sk!=g_emVoidItem){   // (the Void is our stages' base)
            int on=prop_offset(g_emCls,"Name",0); char nm[64]="?"; if(on>=0) fname_resolve(rd32(sk+(uintptr_t)on),nm,sizeof nm);
            if(!strcmp(nm,"Environment_Void")) return;
            snprintf(g_emStockName,sizeof g_emStockName,"%s",nm); g_emUnloadReq=1;
            LOGI("[ENV] stock environment picked (press + OnSkinApplied): %s%s",nm,g_emState!=EM_IDLE?" -> unloading ours":""); }
        return; }
    if(!self||!g_emWCls||g_emOffWSkin<0) return;                            // UserWidget.OnMouseButtonDown: on a skin box?
    int d=0; uintptr_t c=rdptr(self+OFF_Class); while(c&&c!=g_emWCls&&d<8){ c=rdptr(c+OFF_Super); d++; }
    if(c!=g_emWCls) return;
    g_emPressMs=ms; g_emPressSeen=true;
    int idx=em_item_idx(rdptr(self+(uintptr_t)g_emOffWSkin)); if(idx<0) return;
    em_map_widget(self,idx); LOGI("[ENV] press on our box '%s' (UserWidget.OnMouseButtonDown)",g_emLabels[idx]); em_click(idx); }
// 2311, game thread (env_menu_tick): the boxes the list shows now (UListViewBase.EntryWidgetPool.ActiveWidgets, both
// reflected), mapped to our items by their Skin. Tribe fills a box natively (NativeOnListItemObjectSet -> InitSkinItem, no
// ProcessEvent), so this replaces the 2304 OnListItemObjectSet hook for the labels.
static void em_pool_scan(uintptr_t list){
    static uintptr_t lcls=0; static int oPool=-1, oAct=-1;
    if(!list||!g_emWCls||g_emOffWSkin<0) return;
    uintptr_t cls=rdptr(list+OFF_Class);
    if(cls!=lcls){ lcls=cls; int S=calib_fprop_size(); uintptr_t f=find_prop(cls,"EntryWidgetPool"), st=(f&&S>0)?rdptr(f+S):0;   // FStructProperty::Struct
        oPool=f?(int)rd32(f+FP_Offset):-1; oAct=st?prop_offset(st,"ActiveWidgets",0):-1;
        LOGI("[ENV] the list's boxes: EntryWidgetPool@%d ActiveWidgets@%d%s",oPool,oAct,(oPool<0||oAct<0)?" -> our labels can't be set":""); }
    if(oPool<0||oAct<0) return;
    uintptr_t arr=list+(uintptr_t)oPool+(uintptr_t)oAct, data=rdptr(arr); int num=(int)rd32(arr+8);
    if(!data||num<=0||num>256) return;
    for(int i=0;i<num;i++){ uintptr_t w=rdptr(data+(uintptr_t)i*8); if(!w||!in_range(w,0x30)) continue;
        int d=0; uintptr_t c=rdptr(w+OFF_Class); while(c&&c!=g_emWCls&&d<8){ c=rdptr(c+OFF_Super); d++; } if(c!=g_emWCls) continue;
        int idx=em_item_idx(rdptr(w+(uintptr_t)g_emOffWSkin)); if(idx>=0||em_widget_idx(w)>=0) em_map_widget(w,idx); } }
// ============ 2311: the avatar menu and Tribe's own avatar (mod2311 step B; claudedocs/mod_2311_characters.md) ============
// Our boxes are TribeReadyPlayerMeAvatarSkin objects named ReadyPlayerMe_Custom and owned, in the live
// TribeProfileMenuWidget.AvatarList. A press on one runs Tribe's UTribeSkinItemWidget::NativeOnMouseButtonDown (store
// 0x5B4C890): it raises UserWidget.OnMouseButtonDown through ProcessEvent first (the hook sees it), then checks the box's
// bSelected (+0x350) and applies the box's skin only if it isn't selected, or if the skin's CanReapply (vtable +0x300)
// says yes; for TribeReadyPlayerMeAvatarSkin that is "mov w0, wzr; ret" (all read in the 2311 library,
// tools/verify_2311.py). So the hook marks our box selected inside the press (SetSelected only stores the flag and
// refreshes the box's look, decoded at 0x5B4BA58) and loads our skin: Tribe applies nothing and saves nothing, and your
// saved Tribe avatar stays as it is (the user's note 19). The list's OnAvatarClicked doesn't apply anything (decoded at
// 0x594A574: it only reports a "CustomizeAvatar" step). If Tribe applies one of our boxes anyway (some other route), the
// log says WARNING. A "Tribe Avatar" box (and any of Tribe's own avatar boxes) hides our character and shows Tribe's
// avatar again; active_skin.txt then says "tribe" and the next launch starts that way too.
static uintptr_t g_smWCls=0, g_smFnUWDown=0, g_smFnSkinApplied=0, g_smFnSetSelected=0, g_smFnToName=0, g_smKSL=0, g_smFnActHid=0;
static int g_smOffWSkin=-1, g_smIdentOk[SM_MAX], g_smIdentTries[SM_MAX]; static uint64_t g_smNameRpm=0;
static volatile sig_atomic_t g_smDiagReq=0, g_smKeepTribeAvatar=0, g_smBoxesOff=0; static int g_smDiagDone=0;
static uintptr_t g_smDiagComp[12]; static int g_smDiagN=0;                   // poll thread fills, game thread reads after g_smDiagReq
static int sm_bool_prop(uintptr_t o,const char* name){                        // a reflected bool (bitfield-safe), -1 = unreadable
    int S=calib_fprop_size(); uintptr_t f=(o&&in_range(o,0x30))?find_prop(rdptr(o+OFF_Class),name):0; if(!f||S<0) return -1;
    uint32_t off=rd32(f+FP_Offset); uint8_t bo=rd8(f+S+1), bm=rd8(f+S+2); return (rd8(o+off+bo)&bm)?1:0; }
static uintptr_t sm_obj_prop(uintptr_t o,const char* name){                   // an object property by name, 0 = none
    int off=(o&&in_range(o,0x30))?prop_offset(rdptr(o+OFF_Class),name,0):-1; return off>=0?rdptr(o+(uintptr_t)off):0; }
static uint64_t sm_name(const char* s){                                       // game thread: an FName (KismetStringLibrary)
    if(!g_smFnToName||!g_smKSL) return 0; static uint16_t w[64]; static uint8_t b[64] __attribute__((aligned(16)));
    int oS=prop_offset(g_smFnToName,"InString",0), oR=prop_offset(g_smFnToName,"ReturnValue",0); uint16_t psz=rd16(g_smFnToName+0xB6);
    if(oS<0||oR<0||psz>sizeof b) return 0; int n=0; for(;s[n]&&n<63;n++) w[n]=(uint16_t)(uint8_t)s[n]; w[n]=0;
    FStr fs={w,n+1,n+1}; memset(b,0,psz); memcpy(b+oS,&fs,sizeof fs); call_uf(g_smKSL,g_smFnToName,b); uint64_t v; memcpy(&v,b+oR,8);
    char chk[64]; fname_resolve((uint32_t)v,chk,sizeof chk); return strcmp(chk,s)?0:v; }
// our item's identity (game thread): Tribe's own RPM item's plain fields if there is one, then always Name =
// ReadyPlayerMe_Custom and bOwned = 1 (an unowned box makes a press ask to buy it). Read back; false = not added.
static bool sm_identity(uintptr_t it){
    if(!it||!obj_alive(it)) return false;
    if(g_smTribeRpm&&obj_alive(g_smTribeRpm)) em_copy_identity(it,g_smTribeRpm);
    if(!g_smNameRpm) g_smNameRpm=sm_name("ReadyPlayerMe_Custom");
    uintptr_t cls=rdptr(it+OFF_Class); int oN=prop_offset(cls,"Name",0); uintptr_t fo=find_prop(cls,"bOwned"); int S=calib_fprop_size();
    if(!g_smNameRpm||oN<0||!fo||S<0) return false;
    uint32_t off=rd32(fo+FP_Offset); uint8_t bo=rd8(fo+S+1), bm=rd8(fo+S+2); if(!bm||bo>7) return false;
    memcpy((void*)(it+(uintptr_t)oN),&g_smNameRpm,8); *(volatile uint8_t*)(it+off+bo)|=bm;
    uint64_t nm=0; memcpy(&nm,(const void*)(it+(uintptr_t)oN),8); return nm==g_smNameRpm&&(rd8(it+off+bo)&bm); }
static bool sm_is_tribe_avatar(uintptr_t sk){                                 // one of Tribe's own avatar items (not a prop, not ours)
    return sk&&sm_item_idx(sk)<0&&in_range(sk,0x30)&&em_is_a(sk,"TribeOculusAvatarSkin"); }
static bool g_smWeHid=false; static int g_smActorHid=0;                      // the hidden flags that are ours
static void sm_tribe_avatar_hide(bool hide){                                  // game thread: SetHiddenInGame(hide, propagate) on TribeAvatar
    if(!hide&&!g_smWeHid) return;                                             // show only undoes our own hide
    if(!g_fnHid||!g_pawn||!obj_alive(g_pawn)) return;
    uintptr_t ta=sm_obj_prop(g_pawn,"TribeAvatar"); if(!ta||!obj_alive(ta)||!em_is_a(ta,"TribeAvatarComponent")) return;
    int h=sm_bool_prop(ta,"bHiddenInGame"); if(h<0) return;
    if(h==(hide?1:0)){ if(!hide) g_smWeHid=false; return; }
    call_bool2(ta,g_fnHid,hide?1:0,1); g_smWeHid=hide;
    static int flips=0; flips++;
    if(flips<=5||(flips%50)==0) LOGI("[MENU] Tribe's avatar %s (TribeAvatar 0x%lx SetHiddenInGame(%d, propagate) -> bHiddenInGame=%d; flip #%d)",
        hide?"hidden":"shown",(unsigned long)ta,hide?1:0,sm_bool_prop(ta,"bHiddenInGame"),flips); }
static void sm_actor_hide(int hide){                                          // game thread: our avatar actor (body, tracked meshes, head)
    if(!g_isoActor||!obj_alive(g_isoActor)||!g_smFnActHid||hide==g_smActorHid) return;
    call_lib1(g_isoActor,g_smFnActHid,hide); g_smActorHid=hide;
    LOGI("[MENU] our character %s",hide?"hidden (Tribe's own avatar is picked)":"shown"); }
static void sm_write_skin(const char* v){ char p[600]; snprintf(p,sizeof p,"%s/active_skin.txt",OUTDIR);
    int fd=open(p,O_WRONLY|O_CREAT|O_TRUNC,0666); if(fd>=0){ write(fd,v,strlen(v)); close(fd); } }
static void sm_pick_tribe(const char* why){                                   // game thread: Tribe's own avatar from now on
    if(g_smTribeMode) return; g_smTribeMode=1; sm_write_skin("tribe");
    sm_actor_hide(1); sm_tribe_avatar_hide(false);
    LOGI("[MENU] Tribe avatar picked (%s): our character off, Tribe's avatar shown; active_skin.txt = tribe",why); }
static void sm_pick(int idx){                                                 // game thread: one of our boxes
    if(idx<0||idx>=SM_MAX) return;
    if(!strcmp(g_smFiles[idx],"tribe")){ sm_pick_tribe("our 'Tribe Avatar' box"); return; }
    g_smTribeMode=0; sm_load(idx); sm_actor_hide(0); }
static void sm_select_box(uintptr_t box){                                     // TribeSkinItemWidget.SetSelected(true)
    if(!g_smFnSetSelected||!box) return; static uint8_t b[16]; uint16_t psz=rd16(g_smFnSetSelected+0xB6); if(psz>sizeof b) return;
    int o=prop_offset(g_smFnSetSelected,"bInSelected",0); memset(b,0,sizeof b); b[o>=0?o:0]=1; call_uf(box,g_smFnSetSelected,b); }
static long g_smPressMs=-100000;
static void sm_pe_2311(uintptr_t self,uintptr_t func,void* parms){            // repl_pe, game thread
    struct timespec ts; clock_gettime(CLOCK_MONOTONIC,&ts); long ms=ts.tv_sec*1000L+ts.tv_nsec/1000000L;
    if(func==g_smFnSkinApplied){ uintptr_t sk=*(uintptr_t*)parms; int idx=sm_item_idx(sk); bool pressed=ms-g_smPressMs<1000;
        if(idx>=0){ static int warned=0; if(warned++<10) LOGI("[MENU] WARNING Tribe applied our box '%s' (it re-applies its Ready Player Me avatar and saves"
                " [TribeSkins] OculusAvatar=ReadyPlayerMe_Custom)%s",g_smLabels[idx],pressed?"":"; no press seen just before it");
            if(!pressed&&ue_enter()){ sm_pick(idx); ue_leave(); } }
        else if(pressed&&sm_is_tribe_avatar(sk)&&ue_enter()){ sm_pick_tribe("Tribe applied its own avatar right after a press"); ue_leave(); }
        return; }
    if(!self||!g_smWCls||g_smOffWSkin<0) return;                              // UserWidget.OnMouseButtonDown: on a skin box?
    int d=0; uintptr_t c=rdptr(self+OFF_Class); while(c&&c!=g_smWCls&&d<8){ c=rdptr(c+OFF_Super); d++; }
    if(c!=g_smWCls) return;
    uintptr_t sk=rdptr(self+(uintptr_t)g_smOffWSkin); int idx=sm_item_idx(sk);
    if(idx>=0){ g_smPressMs=ms; sm_map_widget(self,idx);
        int sel=-1; if(ue_enter()){ sm_select_box(self); sel=sm_bool_prop(self,"bSelected"); ue_leave(); }
        LOGI("[MENU] press on our box '%s'%s",g_smLabels[idx],sel==1?": selected before Tribe's check (Tribe won't apply it)":
             ": NOT selected (Tribe may apply it: watch for WARNING)");
        if(ue_enter()){ sm_pick(idx); ue_leave(); }
        return; }
    if(sm_is_tribe_avatar(sk)){ g_smPressMs=ms; char nm[64]="?"; int on=prop_offset(rdptr(sk+OFF_Class),"Name",0); if(on>=0) fname_resolve(rd32(sk+(uintptr_t)on),nm,sizeof nm);
        if(ue_enter()){ char w[96]; snprintf(w,sizeof w,"a press on Tribe's '%s' box",nm); sm_pick_tribe(w); ue_leave(); } } }
// the boxes the list shows now (its EntryWidgetPool), mapped to our items by their Skin (as em_pool_scan)
static void sm_pool_scan(uintptr_t list){
    static uintptr_t lcls=0; static int oPool=-1, oAct=-1;
    if(!list||!g_smWCls||g_smOffWSkin<0) return;
    uintptr_t cls=rdptr(list+OFF_Class);
    if(cls!=lcls){ lcls=cls; int S=calib_fprop_size(); uintptr_t f=find_prop(cls,"EntryWidgetPool"), st=(f&&S>0)?rdptr(f+S):0;
        oPool=f?(int)rd32(f+FP_Offset):-1; oAct=st?prop_offset(st,"ActiveWidgets",0):-1;
        LOGI("[MENU] the avatar list's boxes: EntryWidgetPool@%d ActiveWidgets@%d%s",oPool,oAct,(oPool<0||oAct<0)?" -> our labels can't be set":""); }
    if(oPool<0||oAct<0) return;
    uintptr_t arr=list+(uintptr_t)oPool+(uintptr_t)oAct, data=rdptr(arr); int num=(int)rd32(arr+8);
    if(!data||num<=0||num>256) return;
    for(int i=0;i<num;i++){ uintptr_t w=rdptr(data+(uintptr_t)i*8); if(!w||!in_range(w,0x30)) continue;
        int d=0; uintptr_t c=rdptr(w+OFF_Class); while(c&&c!=g_smWCls&&d<8){ c=rdptr(c+OFF_Super); d++; } if(c!=g_smWCls) continue;
        int idx=sm_item_idx(rdptr(w+(uintptr_t)g_smOffWSkin)); if(idx>=0||sm_widget_idx(w)>=0) sm_map_widget(w,idx); } }
static void menu_tick_2311(){                                                 // game thread, ~once a second (menu_tick)
    static int spawns=0, win=0; static bool tripped=false;
    if(tripped) return; if(++win>=30){ win=0; spawns=0; }
    uintptr_t list=g_smList; int n=g_smCount; g_smListLive=(list&&obj_alive(list))?1:0;
    if(g_smBoxesOff) return;                                                 // tribemod/skin_boxes_off (kill switch)
    if(!g_smListLive||!g_smRpmCls||!g_smFnSpawn||!g_smFnAddItem||!g_smFnIndexOf||n<=0) return;
    uintptr_t outer=(g_smTribeRpm&&obj_alive(g_smTribeRpm))?rdptr(g_smTribeRpm+OFF_Outer):list;   // fallback: the list
    int added=0;
    for(int i=0;i<n&&i<SM_MAX;i++){
        if(!obj_alive(g_smItems[i])){
            if(spawns>=3*n){ tripped=true; LOGI("[MENU] guard: %d respawns in 30 s -> stopped adding boxes (bug guard)",spawns); return; }
            g_smItems[i]=sm_spawn(g_smRpmCls,outer); spawns++; g_smIdentOk[i]=0; g_smIdentTries[i]=0;
            LOGI("[MENU] spawned skin object for '%s' = 0x%lx",g_smLabels[i],(unsigned long)g_smItems[i]); }
        if(g_smItems[i]&&g_smIdentOk[i]<0&&g_smIdentTries[i]<4&&(win%5)==0) g_smIdentOk[i]=0;   // try again (5 s apart)
        if(g_smItems[i]&&!g_smIdentOk[i]){ g_smIdentTries[i]++; g_smIdentOk[i]=sm_identity(g_smItems[i])?1:-1;
            LOGI("[MENU] '%s': identity %s",g_smLabels[i],g_smIdentOk[i]>0?"Name=ReadyPlayerMe_Custom bOwned=1":
                 "NOT set: this box is not added (a press could change your saved Tribe avatar)"); }
        if(g_smItems[i]&&g_smIdentOk[i]>0){ int ix=sm_list_index(list,g_smItems[i]);
            if(ix<0){ LOGI("[MENU] adding box '%s' (a crash right after this line: tribemod/skin_boxes_off turns the boxes off)",g_smLabels[i]);
                sm_list_add(list,g_smItems[i]); ix=sm_list_index(list,g_smItems[i]); LOGI("[MENU] added box '%s' (index %d)",g_smLabels[i],ix); }
            if(ix>=0) added++; } }
    g_smAdded=added;
    sm_pool_scan(list);
    for(int w=0;w<32;w++) if(g_smW[w]){                                      // keep our labels (Tribe may rewrite NameText)
        if(!obj_alive(g_smW[w])){ g_smW[w]=0; continue; } int ix=g_smWi[w];
        if(g_smOffWSkin>=0&&sm_item_idx(rdptr(g_smW[w]+(uintptr_t)g_smOffWSkin))!=ix){ g_smW[w]=0; continue; }   // recycled
        sm_label_box(g_smW[w],ix); } }
// the one-time diagnostic (characters doc C11): what the avatar list holds and where every avatar mesh is. Poll thread
// lists (reads only; never ids or URLs), the game thread adds the render state. Again on tribemod/skin_diag (one-shot).
static void sm_diag_mesh(const char* what,uintptr_t c){
    if(!c||!obj_alive(c)){ LOGI("[MENU] diag %s: none",what); return; }
    char cn[96],mn[96]="(none)",pn[96]="(none)",fp[400]; class_name(c,cn,sizeof cn);
    uintptr_t m=sm_obj_prop(c,"SkeletalMeshAsset"); if(m&&in_range(m,0x30)) obj_name(m,mn,sizeof mn);
    uintptr_t par=sm_obj_prop(c,"AttachParent"); if(par&&in_range(par,0x30)) obj_name(par,pn,sizeof pn); full_path(c,fp,sizeof fp);
    LOGI("[MENU] diag %s: %s 0x%lx mesh=%s parent=%s visible=%d hiddenInGame=%d path=%s",what,cn,(unsigned long)c,mn,pn,
         sm_bool_prop(c,"bVisible"),sm_bool_prop(c,"bHiddenInGame"),fp);
    if(g_smDiagN<12) g_smDiagComp[g_smDiagN++]=c; }
static void sm_diag_poll(uintptr_t list){
    if(g_smDiagReq){ LOGI("[MENU] diag: the previous one still waits for the game thread"); return; } g_smDiagN=0; refresh_numelements(); char cn[96];
    if(list&&obj_alive(list)){ uintptr_t ec=sm_obj_prop(list,"EntryWidgetClass"); char en[96]="(none)"; if(ec&&in_range(ec,0x30)) obj_name(ec,en,sizeof en);
        int o=prop_offset(rdptr(list+OFF_Class),"ListItems",0); uintptr_t d=o>=0?rdptr(list+(uintptr_t)o):0; int n=o>=0?(int)rd32(list+(uintptr_t)o+8):0;
        LOGI("[MENU] diag: avatar list 0x%lx EntryWidgetClass=%s ListItems@%d n=%d",(unsigned long)list,en,o,n);
        for(int i=0;d&&i<n&&i<24;i++){ uintptr_t it=rdptr(d+(uintptr_t)i*8); if(!it||!in_range(it,0x30)) continue; class_name(it,cn,sizeof cn);
            int on=prop_offset(rdptr(it+OFF_Class),"Name",0); char nm[96]="?"; if(on>=0) fname_resolve(rd32(it+(uintptr_t)on),nm,sizeof nm);
            int oa=prop_offset(rdptr(it+OFF_Class),"AvatarID",0); int an=oa>=0?(int)rd32(it+(uintptr_t)oa+8):0;
            LOGI("[MENU] diag: item %d %s Name=%s bOwned=%d AvatarID length=%d%s",i,cn,nm,sm_bool_prop(it,"bOwned"),an>0?an-1:0,sm_item_idx(it)>=0?" (ours)":""); } }
    else LOGI("[MENU] diag: no live avatar list (open Profile > Avatars, then touch tribemod/skin_diag)");
    uintptr_t p=g_pawn, ta=(p&&obj_alive(p))?sm_obj_prop(p,"TribeAvatar"):0, rpm=0, pawnBody=0;
    if(!ta) LOGI("[MENU] diag: pawn 0x%lx: no TribeAvatar component (yet)",(unsigned long)p);
    else { int ot=prop_offset(rdptr(ta+OFF_Class),"CurrentETribeAvatarType",0); int typ=ot>=0?(int)rd8(ta+(uintptr_t)ot):-1;
        uintptr_t act=sm_obj_prop(ta,"ActiveAvatarComponent"), meta=sm_obj_prop(ta,"MetaAvatar2Component"); rpm=sm_obj_prop(ta,"ReadyPlayerMeComponent");
        char an[96]="(none)"; if(act&&in_range(act,0x30)) class_name(act,an,sizeof an);
        LOGI("[MENU] diag: pawn 0x%lx TribeAvatar 0x%lx type=%d (1 RPM, 2 Meta Avatar 2) active=%s rpm=0x%lx meta=0x%lx hiddenInGame=%d",
             (unsigned long)p,(unsigned long)ta,typ,an,(unsigned long)rpm,(unsigned long)meta,sm_bool_prop(ta,"bHiddenInGame"));
        if(rpm){ pawnBody=sm_obj_prop(rpm,"AvatarMeshComponent"); sm_diag_mesh("RPM body",pawnBody);
            sm_diag_mesh("RPM right hand",sm_obj_prop(rpm,"RightHandMeshComponent")); sm_diag_mesh("RPM left hand",sm_obj_prop(rpm,"LeftHandMeshComponent")); }
        if(meta){ sm_diag_mesh("Meta third person",sm_obj_prop(meta,"ThirdPersonMeshComponent")); sm_diag_mesh("Meta first person",sm_obj_prop(meta,"FirstPersonMeshComponent")); } }
    char nm2[96],fp[400]; int k=0;                                            // every live AvatarBodyMesh: is the one find_live takes the pawn's?
    for(uint32_t i=0;i<g_numElements&&k<8;i++){ uintptr_t o=obj_at(i); if(!o) continue; obj_name(o,nm2,sizeof nm2); if(strcmp(nm2,"AvatarBodyMesh")) continue;
        class_name(o,cn,sizeof cn); if(strcmp(cn,"SkeletalMeshComponent")||(rd32(o+OFF_Flags)&RF_ClassDefaultObject)) continue;
        full_path(o,fp,sizeof fp); if(strstr(fp,"Default__")) continue; k++;
        LOGI("[MENU] diag: AvatarBodyMesh #%d 0x%lx %s%s",k,(unsigned long)o,o==pawnBody?"(the pawn's) ":"(another actor's) ",fp);
        if(g_smDiagN<12&&o!=pawnBody) g_smDiagComp[g_smDiagN++]=o; }
    LOGI("[MENU] diag: %d AvatarBodyMesh component(s)",k); g_smDiagReq=1; }
static void sm_diag_game(){
    int n=g_smDiagN; for(int i=0;i<n&&i<12;i++){ uintptr_t c=g_smDiagComp[i]; if(!c||!obj_alive(c)) continue; int r=-1; double L[3]={0,0,0};
        uint8_t* rr=g_fnRendered?call_ret(c,g_fnRendered,1,0.5f):0; if(rr) r=(int)*rr;
        uint8_t* l=g_fnLoc?call_ret(c,g_fnLoc,0,0):0; if(l) memcpy(L,l,24);
        LOGI("[MENU] diag render: 0x%lx WasRecentlyRendered(0.5)=%d loc=(%.0f,%.0f,%.0f)",(unsigned long)c,r,L[0],L[1],L[2]); } }
// game thread, every frame from the driver, ~once a second: who is visible. While one of our characters is up, Tribe's
// avatar is hidden (also from the selfie and stream cameras; tribemod/tribe_avatar_shown keeps it visible); while
// Tribe's own avatar is picked, ours is hidden and Tribe's shown.
static void sm_tick_2311(){
    static int tk=0; if(g_smMode!=1||(++tk%60)!=0) return;
    if(g_smDiagReq){ sm_diag_game(); g_smDiagReq=0; }
    bool actorUp=g_isoActor&&obj_alive(g_isoActor);
    if(actorUp) sm_actor_hide(g_smTribeMode?1:0);
    if(g_smKeepTribeAvatar||g_smTribeMode||!actorUp) sm_tribe_avatar_hide(false);
    else sm_tribe_avatar_hide(true); }
static void em_log_actor(const char* what,uintptr_t a){                      // world location / rotation / scale (layout reference)
    if(!a||!obj_alive(a)||!g_emFnActLoc||!g_emFnActRot) return; double L[3]={0,0,0},R[3]={0,0,0},S[3]={0,0,0};
    uint8_t* r=call_ret(a,g_emFnActLoc,0,0); if(r) memcpy(L,r,24);
    r=call_ret(a,g_emFnActRot,0,0); if(r) memcpy(R,r,24);
    r=g_emFnActScale?call_ret(a,g_emFnActScale,0,0):0; if(r) memcpy(S,r,24);
    LOGI("[ENV] %s: loc=(%.0f,%.0f,%.0f) rot(p,y,r)=(%.1f,%.1f,%.1f) scale=(%.2f,%.2f,%.2f)",what,L[0],L[1],L[2],R[0],R[1],R[2],S[0],S[1],S[2]);
    uintptr_t fb=g_emFnBounds; if(!fb) return;                               // world box: what our stage set must fit around
    int oC=prop_offset(fb,"bOnlyCollidingComponents",0), oO=prop_offset(fb,"Origin",0), oE=prop_offset(fb,"BoxExtent",0),
        oI=prop_offset(fb,"bIncludeFromChildActors",0); uint16_t psz=rd16(fb+0xB6);
    static uint8_t b[256] __attribute__((aligned(16))); if(oO<0||oE<0||psz>sizeof b) return;
    for(int inc=0;inc<2;inc++){ memset(b,0,psz); if(oC>=0) b[oC]=0; if(oI>=0) b[oI]=(uint8_t)inc; call_uf(a,fb,b);
        double* O=(double*)(b+oO); double* E=(double*)(b+oE);
        LOGI("[ENV] %s bounds%s: min=(%.0f,%.0f,%.0f) max=(%.0f,%.0f,%.0f)",what,inc?" incl. child actors":"",
            O[0]-E[0],O[1]-E[1],O[2]-E[2],O[0]+E[0],O[1]+E[1],O[2]+E[2]); } }
static bool em_actor_box(uintptr_t a,double O[3],double E[3]){                // GetActorBounds(all components, no child actors)
    uintptr_t fb=g_emFnBounds; if(!fb||!a) return false;
    int oC=prop_offset(fb,"bOnlyCollidingComponents",0), oO=prop_offset(fb,"Origin",0), oE=prop_offset(fb,"BoxExtent",0),
        oI=prop_offset(fb,"bIncludeFromChildActors",0); uint16_t psz=rd16(fb+0xB6);
    static uint8_t b[256] __attribute__((aligned(16))); if(oO<0||oE<0||psz>sizeof b) return false;
    memset(b,0,psz); if(oC>=0) b[oC]=0; if(oI>=0) b[oI]=0; call_uf(a,fb,b);
    memcpy(O,b+oO,24); memcpy(E,b+oE,24); return true; }
static bool em_is_actor(uintptr_t o){ int d=0; for(uintptr_t c=rdptr(o+OFF_Class); c&&d<32; c=rdptr(c+OFF_Super),d++) if(c==g_emActorCls) return true; return false; }
// game thread, once per load: the DJ gear that's out, so our stage set can be sized around the real table. The gear's class
// names aren't known on this build (2026-10-05: BP_Deck_C, BP_Console_C & co. matched nothing), so this logs every actor
// whose class name sounds like gear plus every actor within 2.5 m of the DJ rig that has a real box (not the managers,
// cameras and player starts that sit at the world origin: those filled the 48-entry cap before the gear, 2026-10-05).
static void em_log_equipment(){
    if(!g_emActorCls||!g_emFnActLoc){ LOGI("[ENV] gear: Actor class / GetActorLocation not resolved"); return; }
    static const char* kw[]={"deck","cdj","mixer","console","turntable","vinyl","flx","drum","synth","equip","booth","sampler"};
    double R[3]={0,0,0}; bool haveRig=false;
    if(g_emRig&&obj_alive(g_emRig)){ uint8_t* r=call_ret(g_emRig,g_emFnActLoc,0,0); if(r){ memcpy(R,r,24); haveRig=true; } }
    refresh_numelements(); char cn[96], lc[96], nm[96], what[220]; int n=0, near=0;
    for(uint32_t i=0;i<g_numElements&&n<48;i++){ uintptr_t o=obj_at(i); if(!o||o==g_emRig) continue;
        if(rd32(o+OFF_Flags)&(RF_ClassDefaultObject|0x20u|0x40000000u)) continue;        // CDOs, archetypes, destroyed objects
        if(!em_is_actor(o)) continue;
        class_name(o,cn,sizeof cn); int k=0; for(;cn[k]&&k<95;k++) lc[k]=(char)tolower((unsigned char)cn[k]); lc[k]=0;
        bool hit=false; for(unsigned j=0;j<sizeof kw/sizeof kw[0]&&!hit;j++) if(strstr(lc,kw[j])) hit=true;
        if(!hit&&haveRig){ uint8_t* r=call_ret(o,g_emFnActLoc,0,0); if(r){ double L[3]; memcpy(L,r,24);
            double dx=L[0]-R[0], dy=L[1]-R[1], dz=L[2]-R[2], O[3], E[3];
            if(dx*dx+dy*dy+dz*dz<250.0*250.0&&em_actor_box(o,O,E)){ double m=E[0]>E[1]?E[0]:E[1]; m=m>E[2]?m:E[2];
                if(m>1.0&&m<2000.0){ hit=true; near++; } } } }
        if(!hit) continue;
        obj_name(o,nm,sizeof nm); snprintf(what,sizeof what,"gear %s (%s)",nm,cn); em_log_actor(what,o); n++; }
    LOGI("[ENV] gear: %d actor(s) measured (%d of them only by distance to the rig)",n,near); }
// Not the by-name LevelStreamingDynamic.LoadLevelInstance: in UE 5.4 it only accepts packages listed in the game's
// asset registry (LevelStreaming.cpp: AssetRegistry.GetFirstPackageByName), and ours ship outside Tribe's registry.
static int em_file_exists(const char* path){            // BlueprintPathsLibrary.FileExists: goes through the pak layer. 1/0, -1 = n/a
    static int oIn=-2,oRet=-1; if(!g_emFnFileExists||!g_emBPL) return -1;
    if(oIn==-2){ oIn=prop_offset(g_emFnFileExists,"InPath",0); oRet=prop_offset(g_emFnFileExists,"ReturnValue",0); }
    uint16_t psz=rd16(g_emFnFileExists+0xB6); static uint8_t b[64]; if(oIn<0||oRet<0||psz>sizeof b) return -1;
    memset(b,0,psz); FStr fs; build_fstr(&fs,path); memcpy(b+oIn,&fs,sizeof fs); call_uf(g_emBPL,g_emFnFileExists,b); return b[oRet]?1:0; }
// TSoftObjectPtr bytes for an object path, built by the engine itself: KismetSystemLibrary.MakeSoftObjectPath(PathString)
// -> FSoftObjectPath -> Conv_SoftObjPathToSoftObjRef -> TSoftObjectPtr<UObject>. Returns its size (0 = failed).
static int em_soft_ptr(const char* objpath,uint8_t* out,int cap){
    if(!g_emFnMakeSOP||!g_emFnSOP2Ref||!g_emKSL) return 0;
    static uint8_t b1[128], b2[192];
    int oIn=prop_offset(g_emFnMakeSOP,"PathString",0), oR1=prop_offset(g_emFnMakeSOP,"ReturnValue",0); uint16_t p1=rd16(g_emFnMakeSOP+0xB6);
    int oS=prop_offset(g_emFnSOP2Ref,"SoftObjectPath",0), oR2=prop_offset(g_emFnSOP2Ref,"ReturnValue",0); uint16_t p2=rd16(g_emFnSOP2Ref+0xB6);
    int sop=p1-oR1, n=p2-oR2;                                                 // ReturnValue is the last param in both
    if(oIn<0||oR1<0||oS<0||oR2<0||p1>sizeof b1||p2>sizeof b2||sop<=0||oS+sop>oR2||n<=0||n>cap){
        LOGI("[ENV] soft ptr: layout not usable (PathString@%d Ret@%d psz=%u | SoftObjectPath@%d Ret@%d psz=%u)",oIn,oR1,p1,oS,oR2,p2); return 0; }
    memset(b1,0,p1); FStr fs; build_fstr(&fs,objpath); memcpy(b1+oIn,&fs,sizeof fs); call_uf(g_emKSL,g_emFnMakeSOP,b1);
    memset(b2,0,p2); memcpy(b2+oS,b1+oR1,sop); call_uf(g_emKSL,g_emFnSOP2Ref,b2); memcpy(out,b2+oR2,n); return n; }
// LevelStreamingDynamic.LoadLevelInstanceBySoftObjectPtr: the typed-reference loader. It goes straight to streaming the
// package (no asset-registry check), so it works for levels that ship in a mod pak.
static uintptr_t em_load_level_soft(const char* pkg,bool* ok){
    *ok=false; if(!g_emFnLoadLvlSoft||!g_emLSD||!g_emGameState) return 0;
    char objpath[400]; const char* sn=strrchr(pkg,'/'); snprintf(objpath,sizeof objpath,"%s.%s",pkg,sn?sn+1:pkg);
    uint8_t sp[96]; int n=em_soft_ptr(objpath,sp,sizeof sp); if(n<=0) return 0;
    int oWC=prop_offset(g_emFnLoadLvlSoft,"WorldContextObject",0), oL=prop_offset(g_emFnLoadLvlSoft,"Level",0), oLoc=prop_offset(g_emFnLoadLvlSoft,"Location",0);
    int oOk=prop_offset(g_emFnLoadLvlSoft,"bOutSuccess",0), oR=prop_offset(g_emFnLoadLvlSoft,"ReturnValue",0); uint16_t psz=rd16(g_emFnLoadLvlSoft+0xB6);
    LOGI("[ENV] LoadLevelInstanceBySoftObjectPtr(%s) WC@%d Level@%d Location@%d bOutSuccess@%d ReturnValue@%d psz=0x%x softptr=%dB",objpath,oWC,oL,oLoc,oOk,oR,psz,n);
    static uint8_t b[256]; if(oWC<0||oL<0||oLoc<=oL||oOk<0||oR<0||psz>sizeof b) return 0;
    memset(b,0,psz); *(uintptr_t*)(b+oWC)=g_emGameState; memcpy(b+oL,sp,(n<oLoc-oL)?n:oLoc-oL);
    call_uf(g_emLSD,g_emFnLoadLvlSoft,b); *ok=b[oOk]!=0; return *(uintptr_t*)(b+oR); }
static void em_diagnose(const char* pkg){                // why couldn't the level load: patch OBB in? our pak mounted? path right?
    char dir[300]; snprintf(dir,sizeof dir,"?");
    if(g_emFnContentDir&&g_emBPL){ uint8_t* r=call_ret(g_emBPL,g_emFnContentDir,0,0); if(r) read_fstring((uintptr_t)r,dir,sizeof dir); }
    const char* sub=strncmp(pkg,"/Game/",6)?pkg:pkg+6; char p[400];
    LOGI("[ENV] diagnose: ProjectContentDir='%s'",dir);
    snprintf(p,sizeof p,"%sPaks/pakchunk50-Android_ASTC_P.pak",dir);  LOGI("[ENV] diagnose: FileExists(pak inside the patch OBB)=%d  %s",em_file_exists(p),p);
    snprintf(p,sizeof p,"%s%s.umap",dir,sub);                          LOGI("[ENV] diagnose: FileExists(our level, inside the pak)=%d  %s",em_file_exists(p),p);
    snprintf(p,sizeof p,"%sShaderArchive-TribeXR_Chunk50-SF_VULKAN_ES31_ANDROID-VULKAN_ES3_1_ANDROID.ushaderbytecode",dir);
    LOGI("[ENV] diagnose: FileExists(our shader library)=%d",em_file_exists(p));
    snprintf(p,sizeof p,"%sMaps/Environments/Environment_Void.umap",dir); LOGI("[ENV] diagnose: FileExists(stock Void level, control)=%d",em_file_exists(p));
    if(g_emFnCurLevel&&g_smGS){                                               // is the world context good? (GetCurrentLevelName)
        int oW=prop_offset(g_emFnCurLevel,"WorldContextObject",0), oB=prop_offset(g_emFnCurLevel,"bRemovePrefixString",0), oR=prop_offset(g_emFnCurLevel,"ReturnValue",0);
        uint16_t psz=rd16(g_emFnCurLevel+0xB6); static uint8_t b[64]; char nm[128]; snprintf(nm,sizeof nm,"?");
        if(oW>=0&&oR>=0&&psz<=sizeof b){ memset(b,0,psz); *(uintptr_t*)(b+oW)=g_emGameState; if(oB>=0) b[oB]=1; call_uf(g_smGS,g_emFnCurLevel,b); read_fstring((uintptr_t)(b+oR),nm,sizeof nm); }
        LOGI("[ENV] diagnose: GetCurrentLevelName(game state)='%s'",nm); } }
    // (No synchronous LoadAsset_Blocking test here: on 2026-10-04 loading our cooked material that way ran Tribe out of memory.)
static void em_hide_screens(bool hide){ for(int i=0;i<2;i++) if(g_emScreens[i]&&obj_alive(g_emScreens[i])) call_lib1(g_emScreens[i],g_emFnHidden,hide?1:0); }
static bool g_emBackdropOK=false; static int g_emBackdropTries=0, g_emReReg=0;   // g_emReReg: 2311 re-registrations this load
static void em_lights_restore();
static void giant_reset(const char* why);                         // giant intro (below)
static void show_drop(const char* why);                           // the show bus (below)
static void em_unload(const char* why){
    em_lights_restore(); g_emBackdropOK=false; g_emOurScreen=0;
    if(g_emVM&&obj_alive(g_emVM)) em_video_fill(false,g_emVM);        // Tribe's own video mapping back
    giant_reset("stage unloaded"); show_drop("stage unloaded"); g_emLoadGen++;
    g_emVM=0;
    if(g_emStream&&obj_alive(g_emStream)){ call_lib1(g_emStream,g_emFnSetVisible,0); call_lib1(g_emStream,g_emFnSetLoaded,0); }
    LOGI("[ENV] unloaded our environment (%s)",why); g_emStream=0; g_emActive=-1; g_emState=EM_IDLE; }
static void em_fail(const char* why){                    // undo: Void screens back, nothing loaded, Tribe back where you came from.
    em_hide_screens(false); em_unload(why); g_emFailed=1;                      // mod2311: the pick stays in active_env.txt (the
                                                                               // supervisor tries again; the next launch re-applies it)
    int prev=g_emPrevEnv; g_emPrevEnv=-1;
    if(prev>0&&prev!=(int)g_emVoid&&g_emGameState&&obj_alive(g_emGameState)){ call_lib1(g_emGameState,g_emFnSetEnv,prev);
        LOGI("[ENV] back to the environment you had: %d (%s)",prev,em_env_name(prev)); } }
// [PERF] frame rate, from our actor's tick (once per game frame, DeltaSeconds): every 10 s the average FPS, the worst
// frame and how many frames took over 20 ms (a dropped frame at 72-120 Hz), tagged with the environment that is up.
// A heavier environment shows up as numbers in logcat instead of a feeling.
static void perf_frame(float dt){
    static double acc=0, worst=0; static int n=0, hitch=0;
    if(!(dt>0.f&&dt<1.f)) return;
    acc+=dt; n++; if(dt>worst) worst=dt; if(dt>0.020f) hitch++;
    if(acc>=10.0){ int a=g_emActive;
        LOGI("[PERF] %.1f fps avg over %.0f s, worst frame %.1f ms, %d frame(s) over 20 ms (env: %s)",n/acc,acc,worst*1000.0,hitch,
             (a>=0&&a<EM_MAX)?g_emLabels[a]:"stock");
        acc=0; worst=0; n=0; hitch=0; } }
// ---- Giant intro (the user, 2026-10-06): "a moving platform where i start very high up in the air with a cape that
// drapes to the floor", "the platform im standing on, has a button ... press the button and the platform raises up
// ... press the button again and the platform will slowly come down and im right at the decks", "when im on the ground
// no cape". The height test passed (VROrigin relative Z holds frame to frame; the avatar's feet follow the VROrigin);
// the user picked a 545 cm platform (eyes ~7 m).
// Our level carries SM_DinoGiantLift/Glow/Robe (Blender/giant.py), moved by MPC_DinoGiant through WPO. Here: press
// the button on the pedestal behind the DJ (either hand within press_cm of the cap) -> DOWN, RISING (smoothstep over
// rise_s), UP; press again -> DESCENDING (descend_s) -> DOWN. While off the floor, every frame: VROrigin relative Z =
// base + height, and the collection gets Height, RobeTop (under the HMD: the shoulders) and RobeOn. A press is
// re-armed only after the hand moves away. tribemod/giant.txt (optional): "height=545 rise=8 descend=60 press=14".
// Leaving the stage (em_unload) puts the DJ down at once. Lookups run on the poll thread.
static double g_gH=0, g_gT=0, g_gGlow=0, g_gCool=0;
static double g_gCfgH=545, g_gCfgRise=8, g_gCfgDesc=60, g_gCfgPress=14;
static const double G_BTN[3]={0.0,152.0,106.0};                      // giant.py BUTTON (0, 1.52, 1.06) m -> world cm
static bool g_gArmed=true, g_gBased=false; static double g_gBaseRel[3];
static uintptr_t g_gColl=0, g_gFnSetRel=0; static int g_gOffRel=-2;
static bool g_gHasGiant=false;                                       // the show collection is the Dino Stage's (giant intro)
static volatile int g_showGen=0;                                     // +1 whenever a show collection is (re)found
// walking (club.cpp) and the lift both move VROrigin: walking writes nothing while this is 1 (lift start to fully landed)
static volatile sig_atomic_t g_walkPause=0;
#define HAVE_WALK_PAUSE 1
#define G_NP 19
static uint64_t g_gN[G_NP];
static const char* G_PARAMS[G_NP]={"Height","RobeTopX","RobeTopY","RobeTopZ","RobeOn","ButtonGlow","ShowLevel","ShowOffset","SpotOn",
                                   "TopLasers","LaserVariant","HitMajor","HitMinor","HitCount","DropBoom","HitsOn","Bass",
                                   "ShowPrevBar","ShowNextBar"};          // v14b: the bars around this one as the song plays them
enum { GP_H, GP_TX, GP_TY, GP_TZ, GP_ROBE, GP_GLOW, GP_SHOW, GP_OFFS, GP_SPOT, GP_TOP, GP_LVAR, GP_HMAJ, GP_HMIN, GP_HCNT,
       GP_BOOM, GP_HON, GP_BASS, GP_PREV, GP_NEXT };
// the blackout + follow spot: levels fade toward their targets; the light show restarts at its drop on landing
static double g_gShow=1, g_gSpot=0, g_gTop=0;
static bool g_gJustLanded=false;                                      // giant_reset("landed") -> the grid's drop restart
static double g_gDescFrom=545, g_gDescT=60;                           // a descent: from this height, over this long
static uintptr_t g_gSpotComp=0, g_gFnTime=0, g_gGPS=0; static int g_gTimeDouble=-1;
// The show collection as a weak handle (the 13:57:37 crash, 2026-10-31: claudedocs/mod_2311_levels.md 4 + S1). g_gColl
// outlived its stage's unload; the old check passed for whatever took its slot, and KismetMaterialLibrary's
// SetScalarParameterValue then built a world instance for that object and read 3 as its parameter data. Now the
// collection is found once per stage load (g_emLoadGen) by the poll thread, adopted and dropped on the game thread, and
// checked before every write as FWeakObjectPtr::Get does (same slot, same serial: the world's collection instance holds
// a weak pointer to it, so a loaded MPC has one; not being collected), plus its class and name.
static uint32_t g_gCollIdx=0, g_gCollNm=0; static int32_t g_gCollSer=0; static uintptr_t g_gCollCls=0;
static volatile uintptr_t g_gPend=0, g_gPendSpot=0; static volatile int g_gPendGen=-1; static volatile bool g_gPendGiant=false;
static uint64_t g_gPendN[G_NP];
static long g_gFrame=0, g_gOkAt=-1; static bool g_gOk=false;          // one check per frame (giant_tick counts the frames)
static bool show_coll_ok(){
    if(g_gOkAt==g_gFrame) return g_gOk; g_gOkAt=g_gFrame; g_gOk=false;
    uintptr_t c=g_gColl; uint32_t idx=g_gCollIdx; if(!c||!g_gCollSer) return false;
    if(idx>=g_numElements) refresh_numelements(); if(idx>=g_numElements) return false;
    uintptr_t chunk=rdptr(g_chunks+(uintptr_t)(idx>>16)*8); if(!chunk) return false;
    uintptr_t item=chunk+(uintptr_t)(idx&0xFFFF)*ITEM_STRIDE;
    return g_gOk=rdptr(item)==c&&(int32_t)rd32(item+0x10)==g_gCollSer&&!(rd32(item+8)&gc_dead_mask())
        &&rdptr(c+OFF_Class)==g_gCollCls&&rd32(c+OFF_Name)==g_gCollNm; }
static void show_drop(const char* why){                              // game thread: forget it (club.cpp / intro.cpp look up again)
    g_gOkAt=-1; if(!g_gColl) return; g_gColl=0; g_gCollSer=0; memset(g_gN,0,sizeof g_gN); g_gHasGiant=false; g_gSpotComp=0; g_showGen++;
    LOGI("[GIANT] show bus released (%s)",why); }
static void show_adopt(){                                            // game thread: take the poll thread's find for this load
    uintptr_t c=g_gPend; if(!c) return; __sync_synchronize(); int pg=g_gPendGen; g_gPend=0;   // (the poll thread writes the gen, then c)
    if(pg!=g_emLoadGen||!in_range(c,0x30)) return;                     // an older load's find: the poll thread looks again
    uint32_t idx=rd32(c+OFF_Index); if(idx>=g_numElements) refresh_numelements();
    char cn[64]; class_name(c,cn,sizeof cn);
    if(obj_at(idx)!=c||strcmp(cn,"MaterialParameterCollection")||(item_flags(idx)&gc_dead_mask())){ g_gPendGen=-1;
        LOGI("[GIANT] show collection 0x%lx is gone or not a collection (%s): looking again",(unsigned long)c,cn); return; }
    uintptr_t chunk=rdptr(g_chunks+(uintptr_t)(idx>>16)*8); int32_t ser=chunk?(int32_t)rd32(chunk+(uintptr_t)(idx&0xFFFF)*ITEM_STRIDE+0x10):0;
    if(!ser){ g_gPendGen=-1; LOGI("[GIANT] show collection 0x%lx has no world instance yet (no weak serial): looking again",(unsigned long)c); return; }
    __sync_synchronize();
    g_gCollIdx=idx; g_gCollSer=ser; g_gCollCls=rdptr(c+OFF_Class); g_gCollNm=rd32(c+OFF_Name);
    memcpy(g_gN,g_gPendN,sizeof g_gN); g_gHasGiant=g_gPendGiant; g_gSpotComp=g_gPendSpot; g_gColl=c; g_showGen++; g_gOkAt=-1;
    LOGI("[GIANT] show bus adopted: 0x%lx (slot %u, serial %d, gen %d)",(unsigned long)c,idx,(int)ser,(int)g_showGen); }
static const double G_SPOT_CD=6000.0;                                 // candelas at full: the FOH spot is 32 m away
static const double G_SHOW_LOOP=32*4/(140.0/60.0), G_SHOW_DROP=16*4/(140.0/60.0);   // dino_materials SHOW_LOOP_S, bar 17
static void giant_lookup(){                                           // POLL thread
    if(!g_gFnSetRel) g_gFnSetRel=find_by_path("/Script/Engine.SceneComponent.K2_SetRelativeLocation",0);
    int gen=g_emLoadGen;                                                // found once per stage load; show_adopt takes it (game thread)
    if(g_gPendGen==gen||g_emState!=EM_ACTIVE) return;                  // the collection only exists while our stage is up
    // the show collection of the stage that's up: the Dino Stage's (with the giant intro) or the REACTOR club's (show only)
    // by the active stage's folder under /Game/Mods/ (song14: + Graveyard Shift's MPC_HwShow, the Halloween session's)
    static const char* const SHOWS[][3]={{"dino","/Game/Mods/Dino/MaterialInstances/MPC_DinoGiant.MPC_DinoGiant","MPC_DinoGiant"},
        {"club","/Game/Mods/Club/MaterialInstances/MPC_ClubShow.MPC_ClubShow","MPC_ClubShow"},
        {"halloween","/Game/Mods/Halloween/MaterialInstances/MPC_HwShow.MPC_HwShow","MPC_HwShow"},
        {"christmas","/Game/Mods/Christmas/MaterialInstances/MPC_XmShow.MPC_XmShow","MPC_XmShow"},
        {"harvest","/Game/Mods/Harvest/MaterialInstances/MPC_HmShow.MPC_HmShow","MPC_HmShow"},    // HARVEST MOON (Thanksgiving)
        {"redeye","/Game/Mods/RedEye/MaterialInstances/MPC_ReShow.MPC_ReShow","MPC_ReShow"},      // RED EYE (hangar)
        {"bigdub","/Game/Mods/BigDub/MaterialInstances/MPC_BdShow.MPC_BdShow","MPC_BdShow"}};     // BIG DUB (Main Stage), C3
    char fol[48]=""; int si=-1;
    if(em_active_folder(fol,sizeof fol)) for(int i=0;i<(int)(sizeof SHOWS/sizeof SHOWS[0]);i++) if(!strcmp(fol,SHOWS[i][0])) si=i;
    static int miss=0; uintptr_t c=si>=0?find_by_path(SHOWS[si][1],0):0;
    bool dino=si==0; const char* cn=si>=0?SHOWS[si][2]:"-";
    if(!c){ if((miss++%15)==0) LOGI("[GIANT] no show collection for stage folder '%s' (%s): no light show",fol,cn); return; }
    uint64_t n[G_NP]; int ok=0;
    for(int i=0;i<G_NP;i++){ n[i]=mpc_param_name(c,"ScalarParameters",28,G_PARAMS[i]); ok+=n[i]?1:0; }
    if(ok<6){ LOGI("[GIANT] %s 0x%lx: only %d/%d parameters found",cn,(unsigned long)c,ok,G_NP); return; }
    if(ok<G_NP){ char lack[200]=""; for(int i=0;i<G_NP;i++) if(!n[i]&&strlen(lack)+strlen(G_PARAMS[i])+2<sizeof lack){ strcat(lack," "); strcat(lack,G_PARAMS[i]); }
        LOGI("[GIANT] %s: %d/%d parameters (missing:%s)",cn,ok,G_NP,lack); }
    if(!g_gFnTime){ g_gFnTime=find_by_path("/Script/Engine.GameplayStatics.GetTimeSeconds",0);
        g_gGPS=find_by_path("/Script/Engine.Default__GameplayStatics",0); }
    if(g_gFnTime&&g_gTimeDouble<0){ char ty[64]="?"; for(uintptr_t f=rdptr(g_gFnTime+OFF_ChildProps); f; f=rdptr(f+FF_Next)){
            char pn[64]; fname_resolve(rd32(f+FF_Name),pn,sizeof pn); if(!strcmp(pn,"ReturnValue")){ ffield_type(f,ty,sizeof ty); break; } }
        g_gTimeDouble=!strcmp(ty,"DoubleProperty")?1:0; }
    // the follow spot's light: the SpotLightComponent on our "DinoGiantSpotLight" actor
    uintptr_t spot=0;
    { refresh_numelements(); char cn[64], on[96];
      for(uint32_t i=0;i<g_numElements&&!spot;i++){ uintptr_t o=obj_at(i); if(!o) continue;
        if(rd32(o+OFF_Flags)&(RF_ClassDefaultObject|0x20u|0x40000000u)) continue;
        class_name(o,cn,sizeof cn); if(strcmp(cn,"SpotLightComponent")) continue;
        uintptr_t ow=rdptr(o+OFF_Outer); if(!ow) continue; obj_name(ow,on,sizeof on);
        if(strstr(on,"DinoGiantSpotLight")) spot=o; } }
    bool giant=(dino||!strcmp(SHOWS[si][0],"redeye"))&&n[GP_H];       // RED EYE: the crane flight
    memcpy(g_gPendN,n,sizeof n); g_gPendGiant=giant; g_gPendSpot=spot; g_gPendGen=gen; __sync_synchronize(); g_gPend=c;
    if(!giant) LOGI("[GIANT] show bus: %s 0x%lx (load %d), %d/%d parameters: the light show runs here, no giant intro",
                          cn,(unsigned long)c,gen,ok,G_NP);
    else LOGI("[GIANT] ready: MPC_DinoGiant 0x%lx, button at (%.0f,%.0f,%.0f), lift %.0f cm, rise %.0f s, down %.0f s, press %.0f cm; "
         "spot light 0x%lx, show clock %s",
         (unsigned long)c,G_BTN[0],G_BTN[1],G_BTN[2],g_gCfgH,g_gCfgRise,g_gCfgDesc,g_gCfgPress,(unsigned long)spot,
         g_gFnTime?(g_gTimeDouble?"double":"float"):"missing"); }
static void giant_read_cfg(){
    char s[160]; if(!read_trim_file("giant.txt",s,sizeof s)) return;
    double v; const char* p;
    if((p=strstr(s,"height="))&&sscanf(p+7,"%lf",&v)==1&&v>=50&&v<=1200) g_gCfgH=v;
    if((p=strstr(s,"rise="))&&sscanf(p+5,"%lf",&v)==1&&v>=1&&v<=120) g_gCfgRise=v;
    if((p=strstr(s,"descend="))&&sscanf(p+8,"%lf",&v)==1&&v>=1&&v<=600) g_gCfgDesc=v;
    if((p=strstr(s,"press="))&&sscanf(p+6,"%lf",&v)==1&&v>=5&&v<=40) g_gCfgPress=v; }
static void giant_mpc(uintptr_t ctx,int i,float v){ if(g_gN[i]&&g_mpcFnSetS&&g_mpcLib&&show_coll_ok()) mpc_call_on(g_gColl,g_mpcFnSetS,ctx,g_gN[i],&v,false,true); }
// the show bus for the other stage code (club.cpp): a scalar's key on the live show collection (0 = missing; look it up
// again whenever g_showGen changes) and a write through the same KismetMaterialLibrary call (game thread)
static uint64_t show_key(const char* name){ return show_coll_ok()?mpc_param_name(g_gColl,"ScalarParameters",28,name):0; }
static void show_set(uint64_t key,float v){ if(key&&g_mpcFnSetS&&g_mpcLib&&g_pawn&&obj_alive(g_pawn)&&show_coll_ok()) mpc_call_on(g_gColl,g_mpcFnSetS,g_pawn,key,&v,false,true); }
#define HAVE_SHOW_BUS 1
static void giant_spot_light(double cd){                              // g_lFnSet: LightComponent.SetIntensity (em_lights)
    if(!g_gSpotComp||!obj_alive(g_gSpotComp)||!g_lFnSet) return;
    static uint8_t b[16] __attribute__((aligned(8))); memset(b,0,sizeof b); float f=(float)cd; memcpy(b,&f,4); call_uf(g_gSpotComp,g_lFnSet,b); }
static double giant_world_time(){                                    // GameplayStatics.GetTimeSeconds: the materials' Time
    if(!g_gFnTime||!g_gGPS||!g_pawn) return -1;
    uint16_t psz=rd16(g_gFnTime+0xB6); static uint8_t b[64] __attribute__((aligned(16))); if(psz>sizeof b) return -1;
    int oW=prop_offset(g_gFnTime,"WorldContextObject",0), oR=prop_offset(g_gFnTime,"ReturnValue",0); if(oW<0||oR<0) return -1;
    memset(b,0,psz); *(uintptr_t*)(b+oW)=g_pawn; call_uf(g_gGPS,g_gFnTime,b);
    if(g_gTimeDouble==1){ double d; memcpy(&d,b+oR,8); return d; } float f; memcpy(&f,b+oR,4); return f; }
static void giant_set_rel(double h){                                  // VROrigin relative Z = base + h
    if(!g_vrOrigin||!g_gFnSetRel||!obj_alive(g_vrOrigin)) return;
    if(g_gOffRel==-2) g_gOffRel=prop_offset(rdptr(g_vrOrigin+OFF_Class),"RelativeLocation",0);
    if(!g_gBased){ if(g_gOffRel<0) return; sr(g_vrOrigin+g_gOffRel,g_gBaseRel,24); g_gBased=true;
        LOGI("[GIANT] base VROrigin rel=(%.0f,%.0f,%.0f)",g_gBaseRel[0],g_gBaseRel[1],g_gBaseRel[2]); }
    double t[3]={g_gBaseRel[0],g_gBaseRel[1],g_gBaseRel[2]+h};
    uint16_t psz=rd16(g_gFnSetRel+0xB6); static uint8_t b[512] __attribute__((aligned(16))); if(psz>sizeof b) return;
    static int oL=-2,oT=-1,oS=-1;
    if(oL==-2){ oL=prop_offset(g_gFnSetRel,"NewLocation",0); oT=prop_offset(g_gFnSetRel,"bTeleport",0); oS=prop_offset(g_gFnSetRel,"bSweep",0); }
    if(oL<0) return;
    memset(b,0,psz); memcpy(b+oL,t,24); if(oT>=0) b[oT]=1; if(oS>=0) b[oS]=0; call_uf(g_vrOrigin,g_gFnSetRel,b); }
static void giant_reset(const char* why){                             // back on the floor right now
    if(g_gState==G_DOWN&&!g_gBased) return;
    if(g_gBased){ giant_set_rel(0); g_gBased=false; }
    if(show_coll_ok()&&g_pawn&&obj_alive(g_pawn)){ giant_mpc(g_pawn,GP_H,0); giant_mpc(g_pawn,GP_ROBE,0); giant_mpc(g_pawn,GP_GLOW,0);
        if(strcmp(why,"landed")&&strcmp(why,"song")){ g_gShow=1; g_gSpot=0; g_gTop=0; giant_mpc(g_pawn,GP_SHOW,1); giant_mpc(g_pawn,GP_SPOT,0);
            giant_mpc(g_pawn,GP_TOP,0); giant_spot_light(0); } }
    if(!strcmp(why,"landed")){                                          // the show comes back at its drop (bar 17)
        g_gJustLanded=true;
        double T=giant_world_time();
        if(T>=0&&g_pawn){ double off=fmod(G_SHOW_DROP-fmod(T,G_SHOW_LOOP)+2*G_SHOW_LOOP,G_SHOW_LOOP);
            giant_mpc(g_pawn,GP_OFFS,(float)off); LOGI("[GIANT] show restarts at the drop (clock %.1f s, offset %.2f s)",T,off); } }
    g_gState=G_DOWN; g_gH=0; g_walkPause=0; LOGI("[GIANT] down (%s)",why); }
static double smooth01(double x){ if(x<=0) return 0; if(x>=1) return 1; return x*x*(3-2*x); }
// ---- song mode (the user, 2026-10-06, the set's opener "SVDDEN DEATH - PRELUDE I": "when i play this song, no lights
// should be happening. at 1:09 is when the platform should raise. at 1:52 is when the lasers from the top of the stage
// start going. at 2:20 i am coming down with the platform. by 2:46 im down at the decks for sure").
// tribemod/song.txt (re-read every 5 s; absent = off), one setting per line:
//   match=PRELUDE I                part of the track's name on Tribe's deck (case-insensitive, whole word at its end)
//   bpm=140                        the song's tempo: the show's bars follow it
//   lift=69.0 139.7 166.0          song seconds: start rising, start coming down, down (rise takes giant.txt rise=)
//   cues=0:dark 113.1:top 166:drop ...   song seconds:look; looks: dark top intro build drop breakdown outro show
// While a deck plays the matching track, its playhead (BP_Deck_C.GetPlaybackSeconds: track time, so cue jumps and pitch
// changes stay in sync) drives the lift instead of the button, and the lights: dark = blackout; top = only the horn-tip
// lasers (MPC TopLasers); a show look = that part of the 32-bar show looping in step with the song; show = the
// free-running show again. The decks are found on the poll thread and read on the game thread.
#define S_MAXD 8
#define S_MAXC 48
enum { SL_DARK, SL_TOP, SL_INTRO, SL_BUILD, SL_DROP, SL_BREAK, SL_OUTRO, SL_SHOW, SL_N };
static const char* SL_NAME[SL_N]={"dark","top","intro","build","drop","breakdown","outro","show"};
static const int SL_BAR0[SL_N]={0,16,0,8,16,24,28,0}, SL_BARS[SL_N]={0,8,8,7,8,4,4,0};  // show.py: the parts' bars (top: the drop's laser patterns)
struct SongScript { bool ok; char match[200]; double bpm, lift[3], gbpm, gt0; int nc; double ct[S_MAXC]; int cl[S_MAXC]; };
// gbpm / gt0: the song's own beat grid ("grid=<bpm> <first drop's beat, s>", make_cues); gbpm 0 = none
static SongScript g_sGlobal;                                          // tribemod/song.txt (the track its match= names)
static SongScript g_sScr[S_MAXD];                                     // each deck's current track: songs/<key>.txt
static const SongScript* g_sAct=nullptr;                              // the script in force while song mode is on
static uintptr_t g_sCls=0, g_sFnPlaying=0, g_sFnSecs=0, g_sFnName=0, g_sDeck[S_MAXD], g_sDeckOn=0;
static int g_sNDeck=0, g_sOffName=-2, g_sPlayOut=-1, g_sSecsOut=-1, g_sNameOut=-1, g_sSecsDouble=0;
static double g_sT=0;
static bool g_sOn=false;
static bool song_match(const char* hay,const char* nd){              // nd in hay, case-insensitive, not inside a word at
    if(!nd||!nd[0]) return false;                                      // its end ("PRELUDE I" must not match "PRELUDE II")
    for(const char* h=hay; *h; h++){ const char *x=h,*y=nd;
        while(*x&&*y&&tolower((unsigned char)*x)==tolower((unsigned char)*y)){ x++; y++; }
        if(!*y&&!isalnum((unsigned char)*x)) return true; }
    return false; }
static int fn_out(uintptr_t fn,char* ty,int tyn){                     // a function's first output (BP outputs: CPF_OutParm)
    if(!fn) return -1;
    for(uintptr_t f=rdptr(fn+OFF_ChildProps); f; f=rdptr(f+FF_Next)){
        uint64_t fl=rdptr(f+0x38);                                       // FProperty::PropertyFlags (ElementSize@0x34, Offset@0x44)
        if(fl&(0x100ull|0x400ull)){ if(ty) ffield_type(f,ty,tyn); return (int)rd32(f+FP_Offset); } }
    return -1; }
static void song_key(const char* name,char* out){                     // FNV-1a 64, ASCII lower-cased (make_cues.song_key)
    uint64_t h=0xcbf29ce484222325ull;
    for(const unsigned char* q=(const unsigned char*)name; *q; q++){ unsigned c=*q; if(c>=65&&c<=90) c+=32; h=(h^c)*0x100000001b3ull; }
    snprintf(out,17,"%016llx",(unsigned long long)h); }
static bool song_parse(const char* s,SongScript* sc){                 // song.txt format -> sc (ok: a match= and cues)
    memset(sc,0,sizeof *sc); sc->bpm=140; sc->lift[0]=sc->lift[1]=sc->lift[2]=-1;
    const char* q;
    if((q=strstr(s,"match="))){ q+=6; int j=0; while(*q&&*q!='\n'&&*q!='\r'&&j<(int)sizeof sc->match-1) sc->match[j++]=*q++;
        while(j>0&&sc->match[j-1]==' ') j--; sc->match[j]=0; }
    double v; if((q=strstr(s,"bpm="))&&sscanf(q+4,"%lf",&v)==1&&v>=60&&v<=200) sc->bpm=v;
    double a,b,c; if((q=strstr(s,"lift="))&&sscanf(q+5,"%lf %lf %lf",&a,&b,&c)==3&&a>=0&&b>=a+g_gCfgRise&&c>b){ sc->lift[0]=a; sc->lift[1]=b; sc->lift[2]=c; }
    double gb,g0; if((q=strstr(s,"grid="))&&sscanf(q+5,"%lf %lf",&gb,&g0)==2&&gb>=60&&gb<=200&&g0>-60&&g0<3600){ sc->gbpm=gb; sc->gt0=g0; }
    if((q=strstr(s,"cues="))){ q+=5;
        while(*q&&*q!='\n'&&*q!='\r'&&sc->nc<S_MAXC){ while(*q==' '||*q=='\t') q++;
            double t; char lk[16]; int used=0; if(sscanf(q,"%lf:%15[a-z]%n",&t,lk,&used)<2||used<=0) break; q+=used;
            int k=-1; for(int z=0;z<SL_N;z++) if(!strcmp(lk,SL_NAME[z])) k=z;
            if(k<0||(sc->nc&&t<=sc->ct[sc->nc-1])) continue;
            sc->ct[sc->nc]=t; sc->cl[sc->nc]=k; sc->nc++; } }
    sc->ok=sc->match[0]&&sc->nc>0; return sc->ok; }
static double g_mxSign=1;                                              // tribemod/mix.txt "fader_sign=-1" if the top reads -2.2
static void mix_read_cfg(){                                           // game thread, every 5 s: tribemod/mix.txt (optional)
    char s[200]; double v=1; const char* q;
    if(read_trim_file("mix.txt",s,sizeof s)&&(q=strstr(s,"fader_sign="))&&sscanf(q+11,"%lf",&v)==1) v=v<0?-1:1; else v=1;
    if(v!=g_mxSign){ g_mxSign=v; LOGI("[MIX] fader direction: %s",v>0?"+2.2 = top":"-2.2 = top (mix.txt)"); } }
static void song_read_cfg(){                                          // game thread, every 5 s: tribemod/song.txt
    char s[1150]; SongScript sc;
    if(!(read_trim_file("song.txt",s,sizeof s)&&song_parse(s,&sc))) memset(&sc,0,sizeof sc);
    if(!memcmp(&sc,&g_sGlobal,sizeof sc)) return;
    g_sGlobal=sc;
    if(!sc.ok){ LOGI("[SONG] song.txt: none (the per-track scripts in songs/ still apply)"); return; }
    LOGI("[SONG] song.txt: match '%s', %.1f BPM, lift %.2f / %.2f / %.2f s, %d cues",sc.match,sc.bpm,sc.lift[0],sc.lift[1],sc.lift[2],sc.nc); }
// ---- which deck the crowd hears (the user cues the next song "with the volume down with the headphone on so the crowd
// cant hear", and mixes with "the filters and the regular channel faders", never the crossfader). From probe v2 on
// Tribe's DJM Nexus 2 (2026-10-07):
//   channel fader: BP_ChannelVolumeSlider_C, BP_SliderBase_C.CurrentSliderOffset, -2.2 bottom .. +2.2 top; "Mixer Channel"
//   filter:        BP_ChannelColorKnob_C, BP_KnobBase_C.CurrentKnobRotationYaw, 0 centre, about +-150 at the ends; "Mixer Channel"
//   deck channel:  BP_MixerChannelDevice_C.MixerChannel (BP_Deck_C's parent)
// 0.12.6 (2311), C++: TribeChannelVolumeSlider (-> TribeMixerSliderBase; MixerChannel, TribeSliderBase.CurrentSliderOffset),
// TribeChannelColorKnob (-> TribeChannelKnobBase.MixerChannel -> TribeMixerKnobBase; TribeKnobBase.CurrentKnobRotationYaw),
// TribeDeck -> TribeMixerChannelDevice.MixerChannel (super chains and types read from the 2311 library)
// heard level = fader x filter openness (an open filter counts fully, a filter swept past ~80% of its travel fades out)
#define MX_CH 8
static uintptr_t g_mxFader[MX_CH], g_mxFilter[MX_CH];
static int g_mxOffFader=-1, g_mxSzFader=4, g_mxOffYaw=-1, g_mxSzYaw=4, g_mxOffDeckCh=-2, g_mxSzDeckCh=1;
static bool g_mxReady=false;
static int mx_size(uintptr_t fc){ char ty[32]="?"; if(fc) fname_resolve(rd32(fc),ty,sizeof ty);
    if(!strcmp(ty,"DoubleProperty")) return 8; if(!strcmp(ty,"FloatProperty")||!strcmp(ty,"IntProperty")) return 4; return 1; }
static double mx_read(uintptr_t a,int sz,bool real){                  // a numeric variable of that size
    if(sz==8){ double d=0; sr(a,&d,8); return d; }
    if(sz==4){ if(real){ float f=0; sr(a,&f,4); return f; } int32_t i=0; sr(a,&i,4); return i; }
    uint8_t b=0; sr(a,&b,1); return b; }
static void mix_lookup(){                                             // POLL thread: the mixer's channel faders and filters
    static uintptr_t clsS=0, clsK=0; static int tries=0;
    if(!g_sCls) return;
    char mc[48]; class_name(g_sCls,mc,sizeof mc); bool nat=!strcmp(mc,"Class");   // the decks' class is C++ (2311) or a Blueprint (2304)
    if(!clsS) clsS=find_by_path(nat?"/Script/TribeXR.TribeMixerSliderBase":"/Game/Equipment/Mixer/BP_MixerSliderBase.BP_MixerSliderBase_C",1);
    if(!clsK) clsK=find_by_path(nat?"/Script/TribeXR.TribeMixerKnobBase":"/Game/Equipment/Mixer/BP_MixerKnobBase.BP_MixerKnobBase_C",1);
    if(!clsS||!clsK){ if((tries++%30)==0) LOGI("[MIX] mixer classes not loaded yet"); return; }
    if(g_mxOffDeckCh==-2){ uintptr_t fc=0; g_mxOffDeckCh=prop_offset(g_sCls,"MixerChannel",&fc); g_mxSzDeckCh=mx_size(fc); }
    uintptr_t fad[MX_CH]={0}, fil[MX_CH]={0}; int nf=0, nk=0; char cn[96];
    refresh_numelements();
    for(uint32_t i=0;i<g_numElements;i++){ uintptr_t o=obj_at(i); if(!o) continue;
        if(rd32(o+OFF_Flags)&(RF_ClassDefaultObject|0x20u|0x40000000u)) continue;
        int kind=0, depth=0;
        for(uintptr_t c=rdptr(o+OFF_Class); c&&depth<12&&!kind; c=rdptr(c+OFF_Super),depth++) kind=c==clsS?1:c==clsK?2:0;
        if(!kind) continue;
        class_name(o,cn,sizeof cn);
        bool fader=kind==1&&(!strcmp(cn,"BP_ChannelVolumeSlider_C")||em_is_a(o,"TribeChannelVolumeSlider")),   // 2304 BP / 2311 C++
             filt=kind==2&&(!strcmp(cn,"BP_ChannelColorKnob_C")||em_is_a(o,"TribeChannelColorKnob"));
        if(!fader&&!filt) continue;
        uintptr_t cls=rdptr(o+OFF_Class), fc=0; int oc=-1;
        static const char* CHN[]={"Mixer Channel","MixerChannel","Channel","ChannelIndex","Channel Index","Mixer Channel Index","Deck Channel"};
        for(const char* nm_: CHN){ fc=0; oc=prop_offset(cls,nm_,&fc); if(oc>=0) break; }
        if(oc<0){ static bool told=false;                            // tell which variables the class has (once)
            if(!told){ told=true; char nm[64], ty[32], line[700]; int k=0;
                for(uintptr_t f=rdptr(cls+OFF_ChildProps); f; f=rdptr(f+FF_Next)){ ffield_type(f,ty,sizeof ty);
                    fname_resolve(rd32(f+FF_Name),nm,sizeof nm);
                    if(k<(int)sizeof line-80) k+=snprintf(line+k,sizeof line-k,"%s(%s)@%d ",nm,ty,(int)rd32(f+FP_Offset)); }
                LOGI("[MIX] %s has no channel variable I know; its own variables: %s",cn,line); }
            continue; }
        int ch=(int)mx_read(o+(uintptr_t)oc,mx_size(fc),false); if(ch<0||ch>=MX_CH) continue;
        if(fader){ fad[ch]=o; nf++;
            if(g_mxOffFader<0){ uintptr_t f2=0; g_mxOffFader=prop_offset(cls,"CurrentSliderOffset",&f2); g_mxSzFader=mx_size(f2); } }
        else { fil[ch]=o; nk++;
            if(g_mxOffYaw<0){ uintptr_t f2=0; g_mxOffYaw=prop_offset(cls,"CurrentKnobRotationYaw",&f2); g_mxSzYaw=mx_size(f2); } } }
    bool chg=false; for(int c=0;c<MX_CH;c++) if(fad[c]!=g_mxFader[c]||fil[c]!=g_mxFilter[c]) chg=true;
    if(!chg) return;
    memcpy(g_mxFilter,fil,sizeof fil); memcpy(g_mxFader,fad,sizeof fad);
    g_mxReady=nf>0&&g_mxOffFader>=0&&g_mxOffDeckCh>=0;
    LOGI("[MIX] %d channel faders (CurrentSliderOffset @%d, %dB), %d filters (CurrentKnobRotationYaw @%d, %dB), deck MixerChannel @%d %dB -> %s",
         nf,g_mxOffFader,g_mxSzFader,nk,g_mxOffYaw,g_mxSzYaw,g_mxOffDeckCh,g_mxSzDeckCh,g_mxReady?"following the faders":"NOT usable");
    for(int c=0;c<MX_CH;c++) if(fad[c]||fil[c]) LOGI("[MIX]   channel %d: fader 0x%lx filter 0x%lx",c,(unsigned long)fad[c],(unsigned long)fil[c]); }
static double mix_level(uintptr_t dk,int* chOut){                    // game thread: 0..1 of this deck the crowd hears; -1 unknown
    if(!g_mxReady) return -1;
    int ch=(int)mx_read(dk+(uintptr_t)g_mxOffDeckCh,g_mxSzDeckCh,false); if(chOut) *chOut=ch;
    if(ch<0||ch>=MX_CH||!g_mxFader[ch]||!obj_alive(g_mxFader[ch])) return -1;
    double off=mx_read(g_mxFader[ch]+(uintptr_t)g_mxOffFader,g_mxSzFader,true);
    double fader=(g_mxSign*off+2.2)/4.4; if(fader<0) fader=0; if(fader>1) fader=1;
    double open=1.0;
    if(g_mxFilter[ch]&&g_mxOffYaw>=0&&obj_alive(g_mxFilter[ch])){
        double yaw=fabs(mx_read(g_mxFilter[ch]+(uintptr_t)g_mxOffYaw,g_mxSzYaw,true))/150.0;
        open=1.0-smooth01((yaw-0.55)/0.4); }                           // centre..55% open; 95% swept: gone
    return fader*open; }
// ---- Tribe's beat grid (the user wants the lights on the ACTUAL beats, 2026-10-07). Each deck carries its track's grid,
// BP_Deck_C.BeatgridBpm / BeatgridStartMs, the one Tribe's sync and quantize use. The lights' bar + beat clock follows
// the grid of the track the crowd hears: grid bars = ((t - start) * bpm / 60 - phase) / 4, where phase = which grid beat
// is beat 1 (the light script's first drop lands on a downbeat; no script: the grid start).
static int g_gdOffBpm=-2, g_gdSzBpm=8, g_gdOffStart=-1, g_gdSzStart=8;
static double g_gdBpm[S_MAXD], g_gdStartS[S_MAXD];                    // per deck; bpm 0 = no usable grid
static int g_gdLoud=-1;                                               // the deck out loud (song_tick)
static double g_gdLoudT=-1, g_gdShift=0;                              // its playhead this frame; free-show bar shift
static double grid_bars(double t,double bpm,double startS,const struct SongScript* sc){
    double ph=0;
    if(sc) for(int i=0;i<sc->nc;i++) if(sc->cl[i]==SL_DROP||sc->cl[i]==SL_TOP){
        double bd=floor((sc->ct[i]-startS)*bpm/60.0+0.5); ph=fmod(fmod(bd,4.0)+4.0,4.0); break; }
    return ((t-startS)*bpm/60.0-ph)/4.0; }
static double grid_snap(double c,double bpm,double startS){           // a cue onto the grid's nearest beat (within 0.15 s)
    if(bpm<=0) return c;
    double spb=60.0/bpm, b=floor((c-startS)/spb+0.5), cs=startS+b*spb;
    return fabs(cs-c)<=0.15?cs:c; }
// ---- hit maps (stage v10; the user: the lasers should "hit with the music"). songs/<key>.hits = the drum accents of a
// track (make_cues.hit_map: at most one per beat; major = the bar's main hits), little-endian uint32 per hit:
// (ms << 8) | (major << 7) | intensity 0..127. Replayed against the song clock into MPC HitMajor / HitMinor (decaying
// envelopes), HitCount (+1 per major hit) and HitsOn; DropBoom when a drop (or the top look) starts. The free show on
// a grid: beats 1 and 3 major, 2 and 4 minor. tribemod/hits.txt "offset_ms=N" delays the hits (N > 0: later).
#define H_MAX 4096
static uint32_t g_hit[S_MAXD][H_MAX]; static int g_hitN[S_MAXD];
static double g_hitOffset=0;
static void hits_load(int i,const char* key){                       // game thread, with the deck's script
    g_hitN[i]=0; char p[640]; snprintf(p,sizeof p,"%s/songs/%s.hits",OUTDIR,key);
    int fd=open(p,O_RDONLY); if(fd<0) return;
    ssize_t r=read(fd,g_hit[i],sizeof g_hit[i]); close(fd);
    if(r>0) g_hitN[i]=(int)(r/4); }
static void hits_read_cfg(){                                          // every 5 s: tribemod/hits.txt (optional)
    char s[80]; double v=0; const char* q;
    if(!(read_trim_file("hits.txt",s,sizeof s)&&(q=strstr(s,"offset_ms="))&&sscanf(q+10,"%lf",&v)==1&&v>-500&&v<500)) v=0;
    if(v/1000.0!=g_hitOffset){ g_hitOffset=v/1000.0; LOGI("[HITS] offset %.0f ms",v); } }
static void hits_tick(double dt,int deck,double t,int look,bool freeGrid,double freeBars){
    // deck: song mode's deck (its script's hits) or -1; t: the song clock; look: the cue in force (-1 none);
    // freeGrid: the free show runs on a grid, freeBars = its bar position
    static double hMaj=0,hMin=0,boom=0,cnt=0,lastT=-1e9,lastBeats=-1e9; static int idx=0,lastDeck=-1,lastLook=-2;
    static float wMaj=-1,wMin=-1,wBoom=-1,wCnt=-1,wOn=-1;
    double k=exp(-dt/0.15); hMaj*=k; hMin*=k; boom=fmax(0.0,boom-dt/1.2);
    bool on=false;
    if(deck>=0&&deck<S_MAXD&&g_hitN[deck]>0){
        on=true; const uint32_t* H=g_hit[deck]; int n=g_hitN[deck];
        double tt=t-g_hitOffset; uint32_t ms=(uint32_t)fmax(0.0,tt*1000.0);
        if(deck!=lastDeck||tt<lastT-0.05||tt>lastT+1.0){              // new track, seek or loop: find our place quietly
            int lo=0,hi=n; while(lo<hi){ int mid=(lo+hi)/2; if((H[mid]>>8)<=ms) lo=mid+1; else hi=mid; } idx=lo; }
        else while(idx<n&&(H[idx]>>8)<=ms){ double it=(H[idx]&127)/127.0;
                if(H[idx]&128){ hMaj=fmax(hMaj,0.4+0.6*it); cnt+=1; } else hMin=fmax(hMin,0.3+0.7*it);
                idx++; }
        lastT=tt; lastDeck=deck; }
    else{ lastDeck=-1;
        if(freeGrid){ on=true; double beats=freeBars*4.0;
            if(beats>lastBeats&&beats-lastBeats<1.0&&floor(beats)!=floor(lastBeats)){
                int b=((int)floor(beats))%4; if(b<0) b+=4;
                if(b==0||b==2){ hMaj=fmax(hMaj,0.8); cnt+=1; } else hMin=fmax(hMin,0.6); }
            lastBeats=beats; } }
    bool dropNow=(look==SL_DROP||look==SL_TOP), dropWas=(lastLook==SL_DROP||lastLook==SL_TOP);
    if(dropNow&&!dropWas&&lastLook!=-2){ boom=1.0; LOGI("[HITS] drop boom"); }
    lastLook=look;
    float vMaj=(float)hMaj, vMin=(float)hMin, vBoom=(float)boom, vCnt=(float)fmod(cnt,1000.0), vOn=on?1.f:0.f;
    if(fabsf(vMaj-wMaj)>0.004f){ wMaj=vMaj; giant_mpc(g_pawn,GP_HMAJ,vMaj); }
    if(fabsf(vMin-wMin)>0.004f){ wMin=vMin; giant_mpc(g_pawn,GP_HMIN,vMin); }
    if(vCnt!=wCnt){ wCnt=vCnt; giant_mpc(g_pawn,GP_HCNT,vCnt); }
    if(fabsf(vBoom-wBoom)>0.004f){ wBoom=vBoom; giant_mpc(g_pawn,GP_BOOM,vBoom); }
    if(vOn!=wOn){ wOn=vOn; giant_mpc(g_pawn,GP_HON,vOn);
        LOGI("[HITS] %s",on?(deck>=0?"song hit map":"grid beats (free show)"):"off"); } }
// ---- bass maps (stage v11; the user: "some songs, it just the bass that plays and the lazers need to be going").
// songs/<key>.bass = the track's bass level (sub + low bands, scaled per song) as one byte per 100 ms, replayed against
// the song clock (with the hits' offset) into MPC Bass: 30 ms attack, 150 ms release.
#define B_MAX 24000
static uint8_t g_bass[S_MAXD][B_MAX]; static int g_bassN[S_MAXD];
static void bass_load(int i,const char* key){                       // game thread, with the deck's script
    g_bassN[i]=0; char p[640]; snprintf(p,sizeof p,"%s/songs/%s.bass",OUTDIR,key);
    int fd=open(p,O_RDONLY); if(fd<0) return;
    ssize_t r=read(fd,g_bass[i],sizeof g_bass[i]); close(fd);
    if(r>0) g_bassN[i]=(int)r; }
static void bass_tick(double dt,int deck,double t){
    static double v=0; static float w=-1; static bool wasOn=false;
    double target=0; bool on=deck>=0&&deck<S_MAXD&&g_bassN[deck]>1;
    if(on){ double f=(t-g_hitOffset)*10.0-0.5; if(f<0) f=0; int i=(int)f; double fr=f-i; const uint8_t* B=g_bass[deck];
        target=(i>=g_bassN[deck]-1)?B[g_bassN[deck]-1]/255.0:(B[i]*(1.0-fr)+B[i+1]*fr)/255.0; }
    double tau=target>v?0.03:0.15; v+=(target-v)*(1.0-exp(-dt/tau));
    float vf=(float)v; if(fabsf(vf-w)>0.004f){ w=vf; giant_mpc(g_pawn,GP_BASS,vf); }
    if(on!=wasOn){ wasOn=on; LOGI("[BASS] %s",on?"song bass map":"off"); } }
static void song_lookup(){                                            // POLL thread: Tribe's decks (TribeDeck / BP_Deck_C, children)
    if(!g_sCls){
        static int miss=0, natTry=0; uintptr_t c=0;
        if(natTry<3&&!(c=find_by_path("/Script/TribeXR.TribeDeck",1))) natTry++;               // 0.12.6 (2311): C++, always loaded
        if(!c) c=find_by_path("/Game/Equipment/Deck/BP_Deck.BP_Deck_C",1);                      // 2304: Blueprint, loads with the rig
        if(!c){ if((miss++%30)==0) LOGI("[SONG] Tribe's deck class (TribeDeck / BP_Deck_C) not loaded yet"); return; }
        g_sFnPlaying=em_find_child_func(c,"GetIsPlaying");             // the class's own functions (BP: the same as the old paths)
        g_sFnSecs=em_find_child_func(c,"GetPlaybackSeconds");
        g_sFnName=em_find_child_func(c,"GetCurrentTrackDisplayName");
        char tp[64]="?", ts[64]="?", tn[64]="?", td[64]="?", dn[64]; uintptr_t fc=0; obj_name(c,dn,sizeof dn);
        g_sPlayOut=fn_out(g_sFnPlaying,tp,sizeof tp); g_sSecsOut=fn_out(g_sFnSecs,ts,sizeof ts); g_sNameOut=fn_out(g_sFnName,td,sizeof td);
        g_sOffName=prop_offset(c,"CurrentTrackFileName",&fc); if(fc) fname_resolve(rd32(fc),tn,sizeof tn);
        LOGI("[SONG] %s 0x%lx: GetIsPlaying out @%d %s, GetPlaybackSeconds out @%d %s, GetCurrentTrackDisplayName out @%d %s, "
             "CurrentTrackFileName @%d %s",dn,(unsigned long)c,g_sPlayOut,tp,g_sSecsOut,ts,g_sNameOut,td,g_sOffName,tn);
        g_sSecsDouble=!strcmp(ts,"DoubleProperty");
        if(strcmp(tn,"StrProperty")) g_sOffName=-1;
        if(strcmp(td,"StrProperty")) g_sNameOut=-1;
        if(strcmp(ts,"DoubleProperty")&&strcmp(ts,"FloatProperty")) g_sSecsOut=-1;
        if(strcmp(tp,"BoolProperty")) g_sPlayOut=-1;
        if(g_gdOffBpm==-2){ uintptr_t f1=0, f2=0; g_gdOffBpm=prop_offset(c,"BeatgridBpm",&f1); g_gdSzBpm=mx_size(f1);
            g_gdOffStart=prop_offset(c,"BeatgridStartMs",&f2); g_gdSzStart=mx_size(f2);
            LOGI("[GRID] BeatgridBpm @%d %dB, BeatgridStartMs @%d %dB",g_gdOffBpm,g_gdSzBpm,g_gdOffStart,g_gdSzStart); }
        g_sCls=c; }
    static int calls=0; calls++; bool dead=false;
    for(int i=0;i<g_sNDeck;i++) if(!obj_alive(g_sDeck[i])) dead=true;
    if(g_sNDeck&&!dead&&(calls%15)) return;                            // re-scan every ~30 s, or when a deck went away
    if(!g_sNDeck&&(calls%5)!=1) return;                                // none yet: every ~10 s
    refresh_numelements(); uintptr_t f[S_MAXD]; int n=0;
    for(uint32_t i=0;i<g_numElements&&n<S_MAXD;i++){ uintptr_t o=obj_at(i); if(!o) continue;
        if(rd32(o+OFF_Flags)&(RF_ClassDefaultObject|0x20u|0x40000000u)) continue;
        int depth=0; for(uintptr_t c=rdptr(o+OFF_Class); c&&depth<12; c=rdptr(c+OFF_Super),depth++) if(c==g_sCls){ f[n++]=o; break; } }
    bool chg=(n!=g_sNDeck); for(int i=0;i<n&&!chg;i++) if(f[i]!=g_sDeck[i]) chg=true;
    if(calls%15==1||!g_mxReady) mix_lookup();                        // the faders + filters, alongside the decks
    if(!chg) return;
    for(int i=0;i<n;i++) g_sDeck[i]=f[i];
    g_sNDeck=n;
    char cn[96]; LOGI("[SONG] %d deck(s)",n);
    for(int i=0;i<n;i++){ class_name(f[i],cn,sizeof cn); LOGI("[SONG]   deck %d: 0x%lx (%s)",i,(unsigned long)f[i],cn); } }
static bool song_playing(uintptr_t dk){
    static uint8_t b[512] __attribute__((aligned(16))); uint16_t psz=rd16(g_sFnPlaying+0xB6); if(psz>sizeof b||g_sPlayOut<0) return false;
    memset(b,0,psz); call_uf(dk,g_sFnPlaying,b); return b[g_sPlayOut]!=0; }
static double song_secs(uintptr_t dk){
    static uint8_t b[512] __attribute__((aligned(16))); uint16_t psz=rd16(g_sFnSecs+0xB6); if(psz>sizeof b||g_sSecsOut<0) return -1;
    memset(b,0,psz); call_uf(dk,g_sFnSecs,b);
    if(g_sSecsDouble){ double d; memcpy(&d,b+g_sSecsOut,8); return d; } float f; memcpy(&f,b+g_sSecsOut,4); return f; }
static void song_track_name(int i,uintptr_t dk,char* out,int n){      // the property; else the display name, every 2 s
    if(g_sOffName>=0){ read_fstring(dk+g_sOffName,out,n); if(strcmp(out,"(empty)")) return; }   // empty: try the display name
    static char cache[S_MAXD][512]; static float age[S_MAXD]={9,9,9,9,9,9,9,9};
    if(g_sFnName&&g_sNameOut>=0&&(age[i]+=0.25f)>=2.0f){ age[i]=0;   // (the returned FString is not freed: ~1 small leak / 2 s)
        static uint8_t b[512] __attribute__((aligned(16))); uint16_t psz=rd16(g_sFnName+0xB6);
        if(psz<=sizeof b){ memset(b,0,psz); call_uf(dk,g_sFnName,b); read_fstring((uintptr_t)(b+g_sNameOut),cache[i],sizeof cache[i]); } }
    snprintf(out,n,"%s",cache[i]); }
static void song_load_deck(int i,const char* nm){                     // the light script for the track now on deck i
    SongScript* sc=&g_sScr[i]; memset(sc,0,sizeof *sc); g_hitN[i]=0; g_bassN[i]=0;
    if(!nm[0]||!strcmp(nm,"(empty)")) return;
    char key[17], f[64], s[1150]; song_key(nm,key); snprintf(f,sizeof f,"songs/%s.txt",key);
    if(read_trim_file(f,s,sizeof s)&&song_parse(s,sc)&&song_match(nm,sc->match)){
        char gi[64]=""; if(sc->gbpm>0) snprintf(gi,sizeof gi,", grid %.3f BPM from %.3f s",sc->gbpm,sc->gt0);
        hits_load(i,key); bass_load(i,key);
        LOGI("[SONG] deck %d: '%s' -> songs/%s.txt (%d cues, %.1f BPM%s%s, %d hits, %.0f s of bass)",i,nm,key,sc->nc,
             sc->bpm,gi,sc->lift[0]>=0?", with the lift":"",g_hitN[i],g_bassN[i]/10.0);
        return; }
    memset(sc,0,sizeof *sc); g_hitN[i]=0; g_bassN[i]=0;
    if(g_sGlobal.ok&&song_match(nm,g_sGlobal.match)){ *sc=g_sGlobal; hits_load(i,key); bass_load(i,key);
        LOGI("[SONG] deck %d: '%s' -> song.txt (%d hits)",i,nm,g_hitN[i]); return; }
    LOGI("[SONG] deck %d: '%s' has no light script (key %s): the show runs free",i,nm,key); }
static void song_tick(float dt){                                      // game thread: which scripted song is out, and where
    static double clk=0, lastPlay=-1e9; static float scanT=1; clk+=dt; scanT+=dt;
    bool ready=g_sCls&&g_sFnSecs&&g_sFnPlaying&&g_sPlayOut>=0&&g_sSecsOut>=0&&(g_sOffName>=0||g_sNameOut>=0);
    if(!ready){ if(g_sOn){ g_sOn=false; g_sDeckOn=0; g_sAct=nullptr; LOGI("[SONG] off (the decks are gone)"); } return; }
    if(scanT>=0.25f){ scanT=0;
        static uint32_t seen[S_MAXD]; static bool was[S_MAXD]; static double since[S_MAXD]; static int curDeck=-1;
        double lvl[S_MAXD]; int chOf[S_MAXD]; bool mixKnown=true;
        for(int i=0;i<S_MAXD;i++){ lvl[i]=-2; chOf[i]=-1; }               // -2: not playing / not seen
        int pick=-1;
        for(int i=0;i<g_sNDeck&&i<S_MAXD;i++){ uintptr_t dk=g_sDeck[i]; if(!dk||!obj_alive(dk)){ was[i]=false; continue; }
            char nm[512]; song_track_name(i,dk,nm,sizeof nm);
            uint32_t h=2166136261u; for(const char* c=nm; *c; c++) h=(h^(uint8_t)*c)*16777619u;
            if(h!=seen[i]){ seen[i]=h; was[i]=false; LOGI("[SONG] deck %d track: '%s'",i,nm); song_load_deck(i,nm); }
            if(g_gdOffBpm>=0&&g_gdOffStart>=0){                            // the track's grid (Tribe's analysis or the DJ's edit)
                double b=mx_read(dk+(uintptr_t)g_gdOffBpm,g_gdSzBpm,true), st=mx_read(dk+(uintptr_t)g_gdOffStart,g_gdSzStart,true);
                double nb=(b>=60&&b<=200&&st>-60000&&st<3600000)?b:0, ns=st/1000.0;
                if(fabs(nb-g_gdBpm[i])>1e-6||fabs(ns-g_gdStartS[i])>1e-4){ g_gdBpm[i]=nb; g_gdStartS[i]=ns;
                    if(strcmp(nm,"(empty)")) LOGI("[GRID] deck %d: %.3f BPM, first beat at %.3f s",i,nb,ns); } }
            bool pl=strcmp(nm,"(empty)")&&song_playing(dk);
            if(pl&&!was[i]) since[i]=clk;
            was[i]=pl;
            lvl[i]=-2;                                                     // not playing
            if(!pl) continue;
            int ch=-1; lvl[i]=mix_level(dk,&chOf[i]); (void)ch;
            if(lvl[i]<0) mixKnown=false; }
        // the deck out loud: by the faders + filters (the loudest, kept unless another is 0.15 louder or it drops under
        // 0.1), else the song playing longest. A loud track without a light script = the free-running show.
        int loud=-1;
        for(int i=0;i<g_sNDeck&&i<S_MAXD;i++){ if(lvl[i]==-2) continue;
            if(mixKnown){ if(loud<0||lvl[i]>lvl[loud]) loud=i; }
            else if(loud<0||since[i]<since[loud]) loud=i; }
        if(mixKnown&&loud>=0&&curDeck>=0&&curDeck!=loud&&lvl[curDeck]!=-2&&lvl[curDeck]>=0.1&&lvl[loud]<lvl[curDeck]+0.15)
            loud=curDeck;                                                  // hysteresis: no flip-flop while blending
        if(mixKnown&&loud>=0&&lvl[loud]<0.02) loud=curDeck>=0&&lvl[curDeck]!=-2?curDeck:-1;   // everything faded out
        g_gdLoud=loud;
        if(loud!=curDeck){ curDeck=loud;
            if(loud>=0) LOGI("[MIX] out loud: deck %d (channel %d, level %.2f)%s",loud,chOf[loud],mixKnown?lvl[loud]:-1.0,
                             mixKnown?"":" (mixer unknown: longest playing)"); }
        static float mlog=0; mlog+=0.25f;
        if(mixKnown&&mlog>=2.0f){ mlog=0; char b[160]; int k=0;
            for(int i=0;i<g_sNDeck&&i<S_MAXD;i++) if(lvl[i]!=-2) k+=snprintf(b+k,sizeof b-k,"d%d=%.2f ",i,lvl[i]);
            if(k) LOGI("[MIX] levels %s",b); }
        if(loud>=0&&g_sScr[loud].ok) pick=loud;
        if(pick>=0){ lastPlay=clk;
            if(g_sDeck[pick]!=g_sDeckOn||g_sAct!=&g_sScr[pick]){ g_sDeckOn=g_sDeck[pick]; g_sAct=&g_sScr[pick];
                LOGI("[SONG] the lights follow deck %d ('%s')",pick,g_sScr[pick].match); } }
        else if(loud>=0&&g_sOn) lastPlay=-1e9; }                          // the loud track has no script: the show runs free
    bool on=g_sDeckOn&&g_sAct&&clk-lastPlay<1.5&&obj_alive(g_sDeckOn);  // 1.5 s of grace: a scan miss doesn't drop out
    // the loud track's playhead every frame (the free show follows its grid; song mode uses the smoothed g_sT)
    g_gdLoudT=(g_gdLoud>=0&&g_gdLoud<g_sNDeck&&g_gdBpm[g_gdLoud]>0&&obj_alive(g_sDeck[g_gdLoud]))?song_secs(g_sDeck[g_gdLoud]):-1;
    // the song clock: the deck's playhead can repeat a value for a frame (seen mid-rise, 2026-10-06), and the lift moves
    // the DJ's whole view, so it runs smooth: +dt every frame while the playhead moves, pulled 8%/frame toward it; a
    // difference over 0.3 s (start, cue jump, another deck) snaps
    static double lastRaw=-1, stall=0;
    if(on){ double raw=song_secs(g_sDeckOn);
        if(raw>=0&&raw<36000){ if(raw!=lastRaw){ lastRaw=raw; stall=0; } else stall+=dt;
            if(!g_sOn||fabs(raw-g_sT)>0.3) g_sT=raw;
            else { if(stall<0.1) g_sT+=dt; g_sT+=(raw-g_sT)*0.08; } } }
    if(on!=g_sOn){ g_sOn=on; if(!on){ g_sDeckOn=0; g_sAct=nullptr; }
        LOGI(on?"[SONG] ON at %.2f s: the song's light script runs":"[SONG] off at %.2f s: back to the free-running show",g_sT); }
    static float logT=0; logT+=dt; if(g_sOn&&logT>=2.0f){ logT=0; LOGI("[SONG] t=%.2f s, lift %.0f cm",g_sT,g_gH); } }
static bool song_has_lift(){ return g_sOn&&g_sAct&&g_sAct->lift[0]>=0; }
static double song_lift_h(double t){                                  // the lift's height (cm) at song time t
    if(!g_sAct) return 0;
    const double a=g_sAct->lift[0], b=g_sAct->lift[1], c=g_sAct->lift[2];
    if(a<0||t<a||t>=c) return 0;
    if(t<a+g_gCfgRise) return g_gCfgH*smooth01((t-a)/g_gCfgRise);
    if(t<b) return g_gCfgH;
    return g_gCfgH*(1-smooth01((t-b)/(c-b))); }
static int song_lift_state(double t){                                 // where the lift program is at song time t
    if(!g_sAct) return G_DOWN;
    const double a=g_sAct->lift[0], b=g_sAct->lift[1], c=g_sAct->lift[2];
    if(a<0||t<a||t>=c) return G_DOWN;
    if(t<a+g_gCfgRise) return G_RISING;
    return t<b?G_UP:G_DESC; }
static int song_look(double t,double* seg,double bpm=0,double startS=0){   // the cue in force at song time t (-1: none);
    if(!g_sAct) return -1;                                             // with a grid, cues sit on its nearest beat
    int L=-1; for(int i=0;i<g_sAct->nc;i++){ double c=grid_snap(g_sAct->ct[i],bpm,startS); if(c<=t){ L=g_sAct->cl[i]; if(seg) *seg=c; } }
    return L; }
// the show bar the song plays at song time t (-1: no scripted part there): the same mapping as the clock in giant_tick
static double song_show_bar(double t,double gBpm,double gStart){
    double seg=0; int lk=song_look(t,&seg,gBpm,gStart); if(lk<0||SL_BARS[lk]<=0||!g_sAct) return -1;
    double n=(double)SL_BARS[lk];
    if(gBpm>0){ double gb=grid_bars(t,gBpm,gStart,g_sAct), b0=floor(grid_bars(seg,gBpm,gStart,g_sAct)+0.5);
        return SL_BAR0[lk]+fmod(fmod(gb-b0,n)+n,n); }
    return SL_BAR0[lk]+fmod((t-seg)*g_sAct->bpm/240.0,n); }
// ShowPrevBar / ShowNextBar (v14b, asked for by the Halloween session; the Dino's lasers blend toward the next bar too):
// in song mode the bar shown before this one and the one that plays after it (a section loops: the drop's bar 23 is
// followed by 16, not 24), -1 elsewhere (the materials then use the clock's neighbours). Written when they change.
static void show_bars(int cur,int nxt){
    static int lastCur=-2, prev=-1, lastNext=-2, gen=-1;
    if(gen!=g_showGen){ gen=g_showGen; lastCur=-2; lastNext=-2; prev=-1; }      // a new stage's collection: send again
    if(cur!=lastCur){ prev=(cur>=0&&lastCur>=0)?lastCur:-1; lastCur=cur; giant_mpc(g_pawn,GP_PREV,(float)prev); }
    if(nxt!=lastNext){ lastNext=nxt; giant_mpc(g_pawn,GP_NEXT,(float)nxt); } }
static void giant_tick(float dt){                                     // game thread, every frame
    g_gFrame++;
    if(g_gColl&&!show_coll_ok()){ show_drop("the collection went away"); g_gPendGen=-1; }   // and look again
    if(g_gPend&&g_emState==EM_ACTIVE) show_adopt();
    if(g_emState!=EM_ACTIVE||!show_coll_ok()||!g_pawn||!obj_alive(g_pawn)||!g_camComp){
        if(g_gState!=G_DOWN) giant_reset("stage not active");
        if(g_sOn){ g_sOn=false; g_sDeckOn=0; g_sAct=nullptr; LOGI("[SONG] off (our stage is not up)"); }
        return; }
    static float cfgT=10; cfgT+=dt; if(cfgT>=5){ cfgT=0; giant_read_cfg(); song_read_cfg(); mix_read_cfg(); hits_read_cfg(); }
    static bool wasSongLift=false; song_tick(dt); bool songLift=g_gHasGiant&&song_has_lift();   // a lift= needs the giant
    bool lostLift=wasSongLift&&!songLift; wasSongLift=songLift;
    if(lostLift&&g_gState!=G_DOWN){ g_gState=G_DESC; g_gT=0; g_gDescFrom=g_gH; g_gDescT=fmax(8.0,g_gCfgDesc*g_gH/g_gCfgH);
        LOGI("[GIANT] the song stopped with you up: coming down over %.0f s",g_gDescT); }
    // the button: either hand close to the cap (which rides up with the lift)
    double B[3]={G_BTN[0],G_BTN[1],G_BTN[2]+g_gH}, d=1e9;
    uintptr_t hands[2]={g_mcL,g_mcR};
    for(int i=0;i<2&&g_gHasGiant;i++){ double P[3]; if(hands[i]&&get_vec3(hands[i],g_fnLoc,P)){   // the button: Dino only
        double dx=P[0]-B[0],dy=P[1]-B[1],dz=P[2]-B[2]; double e=sqrt(dx*dx+dy*dy+dz*dz); if(e<d) d=e; } }
    static float nearLog=0; nearLog+=dt;
    if(d<40&&nearLog>=1.0f){ nearLog=0; LOGI("[GIANT] hand %.0f cm from the button (press inside %.0f)",d,g_gCfgPress); }
    g_gCool-=dt; if(d>g_gCfgPress+8) g_gArmed=true;
    if(g_gArmed&&d<g_gCfgPress&&g_gCool<=0){ g_gArmed=false; g_gCool=1.2; g_gGlow=1.0;
        if(songLift) LOGI("[GIANT] button: the song drives the lift (press ignored)");
        else if(g_gState==G_DOWN){ g_gState=G_RISING; g_gT=0; LOGI("[GIANT] button: going up to %.0f cm over %.0f s",g_gCfgH,g_gCfgRise); }
        else if(g_gState==G_UP){ g_gState=G_DESC; g_gT=0; g_gDescFrom=g_gCfgH; g_gDescT=g_gCfgDesc;
            LOGI("[GIANT] button: coming down over %.0f s",g_gCfgDesc); }
        else LOGI("[GIANT] button: ignored while moving"); }
    // the lift
    g_gT+=dt;
    if(songLift){ double tgt=song_lift_h(g_sT), mv=150.0*dt;               // the song drives it (a seek glides at <= 1.5 m/s)
        g_gH=tgt>g_gH?fmin(tgt,g_gH+mv):fmax(tgt,g_gH-mv);
        int st=song_lift_state(g_sT);
        if(fabs(g_gH-tgt)>0.5) st=g_gH<tgt?(int)G_RISING:(int)G_DESC;   // gliding to where a cue jump put the song
        else if(st==G_DOWN&&g_gH>0.5) st=G_DESC;
        if(st!=g_gState){ static const char* SN[4]={"down","rising","up","coming down"};
            LOGI("[SONG] %.2f s: lift %s (%.0f cm)",g_sT,SN[st],g_gH);
            if(st==G_DOWN) giant_reset("song"); else g_gState=st; } }
    else if(g_gState==G_RISING){ g_gH=g_gCfgH*smooth01(g_gT/g_gCfgRise);
        if(g_gT>=g_gCfgRise){ g_gH=g_gCfgH; g_gState=G_UP; LOGI("[GIANT] up (%.0f cm)",g_gH); } }
    else if(g_gState==G_DESC){ g_gH=g_gDescFrom*(1-smooth01(g_gT/g_gDescT)); if(g_gT>=g_gDescT) giant_reset("landed"); }
    else if(g_gState==G_UP) g_gH=g_gCfgH;
    g_walkPause=(g_gState!=G_DOWN)?1:0;
    if(g_gState!=G_DOWN) giant_set_rel(g_gH);
    // blackout + follow spot: the show fades out after the press (1.5 s) and snaps back on landing (0.3 s, at the drop);
    // the spot fades in (1 s) and out after landing (1.2 s)
    // song mode: its cue sets the levels (fast fades) and the show clock; TopLasers = the horn-tip lasers alone
    bool giant=(g_gState!=G_DOWN);
    int gd=-1; for(int i=0;i<g_sNDeck&&i<S_MAXD;i++) if(g_sOn&&g_sDeck[i]==g_sDeckOn) gd=i;
    // the song's own grid first (make_cues fits it to the track's hits). Tribe's can be off: 142.38 BPM for a 140 track,
    // or a first beat at 0.000 s that sits 40-70 ms before the hits (2026-10-08)
    bool gOwn=gd>=0&&g_sAct&&g_sAct->gbpm>0;
    double gBpm=gOwn?g_sAct->gbpm:gd>=0?g_gdBpm[gd]:0, gStart=gOwn?g_sAct->gt0:gd>=0?g_gdStartS[gd]:0;
    static int gridLog=-2; int gridNow=gBpm>0?gd+(gOwn?200:0):(g_gdLoud>=0&&g_gdLoudT>=0?100+g_gdLoud:-1);
    if(gridNow!=gridLog){ gridLog=gridNow;
        if(gridNow>=200) LOGI("[GRID] song mode locked to deck %d's own grid (%.3f BPM from %.3f s; Tribe's: %.3f BPM from %.3f s)",
            gd,gBpm,gStart,g_gdBpm[gd],g_gdStartS[gd]);
        else if(gridNow>=100) LOGI("[GRID] free show locked to deck %d's grid (%.2f BPM)",gridNow-100,g_gdBpm[gridNow-100]);
        else if(gridNow>=0) LOGI("[GRID] song mode locked to deck %d's grid (%.2f BPM)",gridNow,gBpm);
        else LOGI("[GRID] no grid: the clock runs free"); }
    double seg=0; int look=(g_sOn&&(songLift||!giant))?song_look(g_sT,&seg,gBpm,gStart):-1;   // a button giant keeps its blackout
    static int lastLook=-2; if(look!=lastLook){ if(look>=0) LOGI("[SONG] %.2f s: lights '%s'",g_sT,SL_NAME[look]); lastLook=look; }
    double showT=giant?0.0:1.0, topT=0.0, spotT=giant?1.0:0.0;
    if(look>=0){ showT=(look==SL_DARK||look==SL_TOP)?0.0:1.0; topT=(look==SL_TOP)?1.0:0.0; }
    if(g_introDark){ showT=0.0; topT=0.0; }                           // a stage's stream intro holds the venue dark (intro.cpp)
    double sh0=g_gShow, sp0=g_gSpot, tp0=g_gTop, upS=look>=0?0.15:0.3, dnS=look>=0?0.3:1.5;
    g_gShow+=(showT>g_gShow? dt/upS : -dt/dnS); if((showT-sh0)*(showT-g_gShow)<=0) g_gShow=showT;
    g_gSpot+=(spotT>g_gSpot? dt/1.0 : -dt/1.2); if((spotT-sp0)*(spotT-g_gSpot)<=0) g_gSpot=spotT;
    g_gTop+=(topT>g_gTop? dt/0.1 : -dt/0.5); if((topT-tp0)*(topT-g_gTop)<=0) g_gTop=topT;
    bool ramping=(g_gShow!=sh0)||(g_gSpot!=sp0)||(g_gTop!=tp0);
    if(ramping){ giant_mpc(g_pawn,GP_SHOW,(float)g_gShow); giant_mpc(g_pawn,GP_SPOT,(float)g_gSpot); giant_mpc(g_pawn,GP_TOP,(float)g_gTop);
        giant_spot_light(G_SPOT_CD*g_gSpot); }
    if(look>=0&&SL_BARS[look]>0){                                      // that part of the show, in step with the song
        double T=giant_world_time();
        if(T>=0){ double bar, n=(double)SL_BARS[look];
            if(gBpm>0){ double gb=grid_bars(g_sT,gBpm,gStart,g_sAct), b0=floor(grid_bars(seg,gBpm,gStart,g_sAct)+0.5);
                bar=SL_BAR0[look]+fmod(fmod(gb-b0,n)+n,n); }             // the section's bars on the track's bars
            else bar=SL_BAR0[look]+fmod((g_sT-seg)*g_sAct->bpm/240.0,n);
            giant_mpc(g_pawn,GP_OFFS,(float)(bar*G_SHOW_LOOP/32.0-T));
            double barS=gBpm>0?240.0/gBpm:240.0/g_sAct->bpm;              // what plays right after this bar ends
            double nb=song_show_bar(g_sT+(1.0-(bar-floor(bar)))*barS+0.01,gBpm,gStart);
            show_bars((int)floor(bar)%32,nb>=0?(int)floor(nb)%32:-1); } }
    else if(look<0&&!giant&&g_gdLoud>=0&&g_gdLoudT>=0){                // the free show, on the loud track's grid
        if(g_gJustLanded){ double gl=grid_bars(g_gdLoudT,g_gdBpm[g_gdLoud],g_gdStartS[g_gdLoud],nullptr);
            g_gdShift=16.0-floor(gl); LOGI("[GRID] landing: the show restarts at its drop on grid bar %.0f",floor(gl)); }
        double T=giant_world_time();
        if(T>=0){ double gb=grid_bars(g_gdLoudT,g_gdBpm[g_gdLoud],g_gdStartS[g_gdLoud],nullptr);
            double bar=fmod(fmod(gb+g_gdShift,32.0)+32.0,32.0);
            giant_mpc(g_pawn,GP_OFFS,(float)(bar*G_SHOW_LOOP/32.0-T)); }
        show_bars(-1,-1); }                                              // the free show plays its bars in order
    else show_bars(-1,-1);
    g_gJustLanded=false;
    // the song's hits (stage v10): song mode replays its hit map, the free show on a grid its beats
    { bool fg=look<0&&!giant&&g_gdLoud>=0&&g_gdLoudT>=0;
      double fb=fg?grid_bars(g_gdLoudT,g_gdBpm[g_gdLoud],g_gdStartS[g_gdLoud],nullptr)+g_gdShift:0;
      hits_tick(dt,(look>=0&&g_sAct)?gd:-1,g_sT,look,fg,fb);
      bass_tick(dt,(look>=0&&g_sAct)?gd:-1,g_sT); }
    // the laser program's variant (stage v9): one per song (its script's match name, hashed), or the next one every 32
    // bars of the free show's grid; written only when it changes
    { static int lvLast=-1; int lv=-1;
      if(look>=0&&g_sAct){ uint32_t h=2166136261u; for(const char* q=g_sAct->match; *q; q++) h=(h^(uint8_t)*q)*16777619u;
          lv=(int)(h%8u); }
      else if(look<0&&!giant&&g_gdLoud>=0&&g_gdLoudT>=0){
          double gb=grid_bars(g_gdLoudT,g_gdBpm[g_gdLoud],g_gdStartS[g_gdLoud],nullptr)+g_gdShift;
          lv=(int)fmod(fmod(floor(gb/32.0),8.0)+8.0,8.0); }
      if(lv>=0&&lv!=lvLast){ lvLast=lv; giant_mpc(g_pawn,GP_LVAR,(float)lv);
          LOGI("[LASER] variant %d (%s)",lv,look>=0?g_sAct->match:"free show"); } }
    // the collection: lift height, robe top under the HMD (shoulders ~27 cm below the eyes, 8 cm behind), button glow
    if(g_gGlow>0){ g_gGlow-=dt/0.8; if(g_gGlow<0) g_gGlow=0; }
    static bool wasDown=true; bool down=(g_gState==G_DOWN);
    if(!down||!wasDown||g_gGlow>0){
        double C[3]={0,0,0},CR[3]={0,0,0}; get_vec3(g_camComp,g_fnLoc,C); get_vec3(g_camComp,g_fnGetRot,CR);
        double yr=CR[1]*M_PI/180.0;
        giant_mpc(g_pawn,GP_H,(float)g_gH);
        giant_mpc(g_pawn,GP_TX,(float)(C[0]-cos(yr)*8.0)); giant_mpc(g_pawn,GP_TY,(float)(C[1]-sin(yr)*8.0));
        giant_mpc(g_pawn,GP_TZ,(float)(C[2]-27.0));
        giant_mpc(g_pawn,GP_ROBE,g_gH>25?1.f:0.f); giant_mpc(g_pawn,GP_GLOW,(float)g_gGlow); }
    wasDown=down; }
// game thread, ~once a second from our actor's tick: keep our boxes in the live EnvironmentList, then run the load steps
// mod2311 step C: is every envs.txt level in the mounted paks? BlueprintPathsLibrary.FileExists goes through the pak layer
// (em_diagnose uses the same check after a failed load). Once, logged as one line; shown in [READY] as paks=N/M.
static volatile sig_atomic_t g_emPaksOk=-1, g_emPaksN=0;
static void em_check_paks(){
    static bool done=false; if(done||!g_emFnFileExists||!g_emBPL||!g_emFnContentDir||g_emCount<=0) return; done=true;
    char dir[300]=""; uint8_t* r=call_ret(g_emBPL,g_emFnContentDir,0,0); if(r) read_fstring((uintptr_t)r,dir,sizeof dir);
    if(!dir[0]||!strcmp(dir,"(empty)")){ LOGI("[ENV] stages in the paks: ProjectContentDir unreadable: not checked"); return; }
    int ok=0, n=g_emCount; char miss[300]=""; int ml=0;
    for(int i=0;i<n&&i<EM_MAX;i++){ const char* pk=g_emPaths[i]; const char* sub=strncmp(pk,"/Game/",6)?pk:pk+6; char p[500];
        snprintf(p,sizeof p,"%s%s.umap",dir,sub); int e=em_file_exists(p);
        if(e==1) ok++; else if(ml<(int)sizeof miss-70) ml+=snprintf(miss+ml,sizeof miss-ml,"%s'%s'%s",ml?", ":"",g_emLabels[i],e<0?" (n/a)":""); }
    g_emPaksN=n; g_emPaksOk=ok;
    LOGI("[ENV] stages in the paks: %d/%d levels found%s%s",ok,n,ok<n?"; missing: ":"",ok<n?miss:""); }
static void env_menu_tick(){
    static int tk=0, spawns=0, win=0, away=0; static bool tripped=false;
    if(!g_envMenuOn||(++tk%60)!=0) return;
    em_check_paks();
    if(++win>=30){ win=0; spawns=0; }                                        // same respawn guard as the avatar boxes
    uintptr_t list=g_emList; int n=g_emCount;
    g_emListLive=(list&&obj_alive(list))?1:0;
    if(!tripped&&list&&obj_alive(list)&&g_emCls&&g_smFnSpawn&&g_smFnAddItem&&g_smFnIndexOf&&n>0){
        uintptr_t outer=(g_emTribeItem&&obj_alive(g_emTribeItem))?rdptr(g_emTribeItem+OFF_Outer):list;
        for(int i=0;i<n&&i<EM_MAX&&!tripped;i++){
            if(!obj_alive(g_emItems[i])){
                if(spawns>=3*n){ tripped=true; LOGI("[ENV] guard: %d respawns in 30 s -> stopped adding boxes (bug guard)",spawns); break; }
                g_emItems[i]=sm_spawn(g_emCls,outer); spawns++;
                LOGI("[ENV] spawned environment object for '%s' = 0x%lx",g_emLabels[i],(unsigned long)g_emItems[i]); }
            if(g_emItems[i]&&g_emIdentOf[i]!=g_emItems[i]&&g_emVoidItem&&obj_alive(g_emVoidItem)){   // before Tribe builds its box
                int k=em_copy_identity(g_emItems[i],g_emVoidItem); g_emIdentOf[i]=g_emItems[i];
                LOGI("[ENV] box '%s' now carries The Void's identity (%d fields copied)",g_emLabels[i],k); }
            static int waited=0;                                              // add the box once it carries the Void's identity
            if(g_emItems[i]&&sm_list_index(list,g_emItems[i])<0&&(g_emIdentOf[i]==g_emItems[i]||++waited>15)){
                sm_list_add(list,g_emItems[i]); LOGI("[ENV] added box '%s'%s",g_emLabels[i],g_emIdentOf[i]==g_emItems[i]?"":" (WITHOUT the Void's identity: not found)"); } }
        { int k=0; for(int i=0;i<n&&i<EM_MAX;i++) if(g_emItems[i]&&obj_alive(g_emItems[i])&&sm_list_index(list,g_emItems[i])>=0) k++; g_emAdded=k; }
        if(g_emMode==1) em_pool_scan(list);                                  // 2311: find our boxes in the list's own pool
        for(int w=0;w<32;w++) if(g_emW[w]){                                  // keep our labels (Tribe may rewrite NameText)
            if(!obj_alive(g_emW[w])){ g_emW[w]=0; continue; } int ix=g_emWi[w];
            if(g_emMode==1&&g_emOffWSkin>=0&&em_item_idx(rdptr(g_emW[w]+(uintptr_t)g_emOffWSkin))!=ix){ g_emW[w]=0; continue; }   // 2311: recycled
            if(ix>=0&&ix<n) box_set_label(g_emW[w],g_emLabels[ix]); } }
    // the game state, straight from the engine (GameplayStatics.GetGameState): a name/path search never finds it on this build
    // World context: our own avatar actor first (spawned into the game world), then the menu list (a UMG widget asks its
    // owning player's world), then the rig. The first BP_Rig_C found can live in a preview world with no game state
    // (2026-10-04: every GetGameState returned null -> "click ignored, not ready: gs=0x0").
    if((!g_emGameState||!obj_alive(g_emGameState))&&g_emFnGetGS&&g_smGS){
        static int oWC=-2; if(oWC==-2) oWC=prop_offset(g_emFnGetGS,"WorldContextObject",0);
        uint16_t psz=rd16(g_emFnGetGS+0xB6), rvo=rd16(g_emFnGetGS+0xB8); static uint8_t b[32]; uintptr_t gs=0;
        uintptr_t ctx[4]={g_pawn,g_isoActor,g_emList,g_emRig};
        for(int k=0;k<4&&!gs;k++){ uintptr_t wc=ctx[k]; if(!wc||!obj_alive(wc)||oWC<0||psz>sizeof b||rvo>=psz) continue;
            memset(b,0,psz); *(uintptr_t*)(b+oWC)=wc; call_uf(g_smGS,g_emFnGetGS,b); gs=*(uintptr_t*)(b+rvo); }
        static int scanTk=0;
        if(!gs&&++scanTk%3==0){ gs=em_find_gs_by_class(); if(gs) LOGI("[ENV] GetGameState gave nothing for every context; found the game state by class instead"); }
        if(gs){ g_emGameState=gs; g_emEnvOff=em_find_env_prop(gs);
            if(g_emEnvOff<0&&rd8(gs+0x308)<=10){ g_emEnvOff=0x308; LOGI("[ENV] environment property not reflected -> native +0x308 (Ghidra, SetEnvironment impl)"); }
            char cn[96],fp[300]; class_name(gs,cn,sizeof cn); full_path(gs,fp,sizeof fp);
            int cur=em_cur_env(); LOGI("[ENV] game state = 0x%lx class=%s path=%s environment@%d = %d (%s)",(unsigned long)gs,cn,fp,g_emEnvOff,cur,em_env_name(cur)); } }
    if(g_emUnloadReq){ g_emUnloadReq=0; char w[80]; snprintf(w,sizeof w,"stock:%s",g_emStockName[0]?g_emStockName:"?"); em_write_active(w);
        g_emTribeSwitched=0; if(g_emState!=EM_IDLE){ em_hide_screens(false); em_unload("you picked a stock environment"); } }
    int req=g_emReq;
    if(req>=0){ g_emReq=-1;
        if(req<n&&g_emGameState&&obj_alive(g_emGameState)&&g_emFnSetEnv&&g_emVoid>=0&&g_emFnLoadLvlSoft&&g_emLSD){
            if(g_emState!=EM_IDLE) em_unload("switching");
            g_emLoadGen++; g_emActive=req; em_write_active(g_emLabels[req]); g_emTribeSwitched=0;
            int before=em_cur_env(); if(before!=(int)g_emVoid) g_emPrevEnv=before;
            int r=call_lib1(g_emGameState,g_emFnSetEnv,(int)g_emVoid);
            LOGI("[ENV] step 1/4: SetEnvironment(Void=%lld) from %d (%s) -> %d",(long long)g_emVoid,before,em_env_name(before),r);
            g_emState=EM_WAIT_BASE; g_emT=0; }
        else LOGI("[ENV] click ignored, not ready: gs=0x%lx SetEnvironment=0x%lx Void=%lld LoadLevelInstanceBySoftObjectPtr=0x%lx",
            (unsigned long)g_emGameState,(unsigned long)g_emFnSetEnv,(long long)g_emVoid,(unsigned long)g_emFnLoadLvlSoft); }
    int st=g_emState, a=g_emActive; if(a<0||a>=n){ if(st!=EM_IDLE) em_unload("box list changed"); return; }
    if(st==EM_WAIT_BASE){
        int cur=em_cur_env(); g_emT++;
        if(g_emT>=3&&(cur==(int)g_emVoid||g_emT>=8)){                        // the Void is in (or 8 s passed without a readable value)
            { char m0[96],m1[96]; em_actor_material(g_emScreens[0],m0,sizeof m0); em_actor_material(g_emScreens[1],m1,sizeof m1);
              LOGI("[ENV] Void screens before hiding: backdrop hidden=%d (%s), chroma hidden=%d (%s)",
                   em_actor_hidden(g_emScreens[0]),m0,em_actor_hidden(g_emScreens[1]),m1); }
            em_hide_screens(true);
            LOGI("[ENV] step 2/4: environment now %d (%s); hid %d Void screen(s)",cur,em_env_name(cur),(g_emScreens[0]?1:0)+(g_emScreens[1]?1:0));
            em_log_actor("Void SM_BackdropScreen",g_emScreens[0]); em_log_actor("DJ rig",g_emRig); em_log_equipment();
            bool ok=false; g_emStream=em_load_level_soft(g_emPaths[a],&ok);
            LOGI("[ENV] step 3/4: LoadLevelInstanceBySoftObjectPtr(%s) -> success=%d stream=0x%lx",g_emPaths[a],ok?1:0,(unsigned long)g_emStream);
            if(!ok||!g_emStream){ g_emStream=0; em_diagnose(g_emPaths[a]); em_fail("level not loadable"); } else { g_emState=EM_WAIT_LOAD; g_emT=0; } } }
    else if(st==EM_WAIT_LOAD){
        if(!obj_alive(g_emStream)){ g_emStream=0; em_fail("streaming object went away"); return; }
        int ld=call_lib1(g_emStream,g_emFnIsLoaded,-1), vis=call_lib1(g_emStream,g_emFnIsVisible,-1); g_emT++;
        if(g_emT<=10||g_emT%5==0||vis==1) LOGI("[ENV] step 4/4: t=%ds loaded=%d visible=%d",g_emT,ld,vis);
        if(vis==1){ LOGI("[ENV] *** '%s' is IN (visible after %d s) ***",g_emLabels[a],g_emT); g_emState=EM_ACTIVE; away=0;
            g_emBackdropOK=em_register_backdrop(); g_emBackdropTries=1; g_emReReg=0; em_lights(true); }
        else if(g_emT>=40){ LOGI("[ENV] gave up after 40 s (loaded=%d visible=%d)",ld,vis); em_fail("timeout"); } }
    else if(st==EM_ACTIVE){
        if(!g_emStream||!obj_alive(g_emStream)){ LOGI("[ENV] our level '%s' went away (a world change?): unloaded, the supervisor loads it again",g_emLabels[a]);
            g_emStream=0; em_hide_screens(false); em_unload("our level went away"); g_emFailed=1; return; }
        em_hide_screens(true);                                               // Tribe re-shows its registered backdrop when visuals change
        if(!g_emBackdropOK&&g_emBackdropTries<20&&(++g_emBackdropTries%3)==0) g_emBackdropOK=em_register_backdrop();
        { static int rc=0; static int oBA=-2;                                // 2311: did the Void register its own backdrop after ours
          if(g_emMode==1&&g_emBackdropOK&&g_emReReg<6&&g_emVM&&obj_alive(g_emVM)&&(++rc%5)==0){   // (a slow load)? ~5 s, 6 at most
              if(oBA==-2) oBA=prop_offset(rdptr(g_emVM+OFF_Class),"BackdropStaticMeshActor",0);
              uintptr_t ba=oBA>=0?rdptr(g_emVM+(uintptr_t)oBA):0;
              if(oBA>=0&&ba!=g_emOurScreen){ g_emReReg++; g_emBackdropOK=false; g_emBackdropTries=0; char fp[300]="(null)"; if(ba&&obj_alive(ba)) full_path(ba,fp,sizeof fp);
                  LOGI("[ENV] visuals: Tribe's backdrop is now 0x%lx (%s), not our screen -> registering ours again (%d of 6)",(unsigned long)ba,fp,g_emReReg); } } }
        if(g_emOurScreen&&obj_alive(g_emOurScreen)){ static int lastH=-2; static char lastM[96]; char mn[96];
            int h=em_actor_hidden(g_emOurScreen); em_actor_material(g_emOurScreen,mn,sizeof mn);
            if(h!=lastH||strcmp(mn,lastM)){ LOGI("[ENV] visuals screen: hidden=%d material=%s",h,mn); lastH=h; snprintf(lastM,sizeof lastM,"%s",mn); }
            if(g_emVM&&obj_alive(g_emVM)) em_video_fill(true,g_emVM); }   // Tribe re-applies its mapping when a video opens
        int cur=em_cur_env();                                                // Tribe left the Void by some other route -> ours goes too
        if(cur>=0&&cur!=(int)g_emVoid){ if(++away>=2){ em_hide_screens(false);
            bool youPicked=mono_now()-g_emPressMs/1000.0<4.0;           // a skin-box press just before: you picked a stock one
            if(youPicked){ char w[80]; snprintf(w,sizeof w,"stock:%s",em_env_name(cur)); em_write_active(w); em_unload("you picked a stock environment"); }
            else { g_emTribeSwitched=1; em_unload("Tribe switched environment; your pick stays for the next launch"); } } }
        else away=0; }
}
#include "club.cpp"                                                  // the REACTOR club (club session): walking + gate
#include "intro.cpp"                                                 // a stage's stream intro (Graveyard Shift's Horseman)
#include "camview.cpp"                                               // a stage's extra camera button (Graveyard Shift's Crowd)
#include "stream.cpp"                                                // Tribe's stream encoder settings (tribemod/stream.txt)
#include "freeze.cpp"                                                // the freeze recorder (tribemod/freeze_log.txt)
// ---- the ProcessEvent hook (mod2311) ----
// Pass-through (just Tribe's own call) until the mod is on (g_mod_on: tribemod readable and executor_on in it), and on
// every thread but the game thread: the per-frame work, the menu handlers and the loads used to run on whichever thread
// called ProcessEvent next. The game thread is the one named "GameThread" (the 13:57:37 tombstone: tid 24243, name
// GameThread); it is learned from its own calls, one name check per 64 calls until found.
static volatile sig_atomic_t g_mod_on=0;
static volatile sig_atomic_t g_gtProbe=0;
static inline bool is_game_thread(){
    uintptr_t me=(uintptr_t)pthread_self(), gt=g_gtSelf;
    if(gt) return me==gt;
    if(((g_gtProbe=g_gtProbe+1)&63)!=0) return false;
    char nm[17]; memset(nm,0,sizeof nm); if(prctl(PR_GET_NAME,(unsigned long)nm,0,0,0)!=0||strcmp(nm,"GameThread")) return false;
    g_gtSelf=me; LOGI("[HOOK] the game thread: tid %d (named GameThread); the mod works on it only",my_tid()); return true; }
// A world change (mod2311): the poll thread saw Tribe's pawn go away (a room join or leave, a level change) and moved
// g_worldGen on. Everything bound to the old world is dropped here, on the game thread, without calling into it; the poll
// thread finds the new pawn and this thread wires it (world_wire); a stage you had loaded is loaded again by the
// supervisor, and our avatar actor is spawned again if it went with the old world.
static volatile int g_worldGen=0; static int g_worldSeen=0;
static volatile sig_atomic_t g_worldUp=0; static double g_worldUpAt=-1;   // the supervisor's (world_poll)
static void head_forget(const char* why){            // our actor went away: its head component with it; the head mesh stays
    if(g_hdComp) LOGI("[HEAD] the head component went with our avatar actor (%s): a new one is made on the next tick",why);
    g_hdComp=0; g_hdForA=0; g_hdState=HD_ON; }
static void world_reset_game(){
    g_worldSeen=g_worldGen;
    LOGI("[WORLD] reset (gen %d): the pawn, camera, hands, menus and stage state of the old world are dropped",g_worldSeen);
    g_pawn=0; g_camComp=0; g_vrOrigin=0; g_mcL=0; g_mcR=0; g_camMgr=0;
    if(g_isoActor&&!obj_alive(g_isoActor)){ unroot_object(g_isoActor); g_isoActor=0; g_isoComp=0;   // gone with the old world
        a2_drop_meshes(); g_trackParent=0; head_forget("the world changed"); }
    if(g_emState!=EM_IDLE){ show_drop("the world changed"); g_emStream=0; g_emActive=-1; g_emState=EM_IDLE; g_emLoadGen++; g_emFailed=1; }
    g_emGameState=0; g_emScreens[0]=g_emScreens[1]=0; g_emVM=0; g_emOurScreen=0; g_emRig=0; g_emList=0; memset(g_emW,0,sizeof g_emW);
    g_smList=0; memset(g_smW,0,sizeof g_smW);
    g_cPawn=g_cVRO=g_cCam=g_cPC=g_cPar=0; g_cBased=false; g_cHaveSet=false;      // walking: nothing is written to the old VROrigin
    g_gBased=false; g_gState=G_DOWN; g_gH=0; g_walkPause=0; g_lN=0; }            // the lift and the light list: the old world's
extern "C" void repl_pe(void* self,void* func,void* parms){
    g_pe_n++;
    if(!g_mod_on||!is_game_thread()){ orig_pe(self,func,parms); return; }
    { static double lastRun=0, lastBeat=0; double pnow=mono_now();
      if(pnow-lastBeat>=0.016){ lastBeat=pnow; freeze_beat(); }        // the game thread is alive (also while a world loads)
      if(g_worldSeen!=g_worldGen&&ue_enter()){ world_reset_game(); ue_leave(); }
      if(g_wire_req&&ue_enter()){ g_wire_req=0; world_wire(); ue_leave(); }          // the poll thread found the world
      // the per-frame work, every 16 ms at most, once the world is up (Tribe's pawn wired), with or without our avatar
      // actor (mod2311; levels doc S3, load doc 3.4): each part checks its own needs
      if(g_pawn && (lastRun==0 || pnow-lastRun>=0.016) && ue_enter()){
          if(!obj_alive(g_pawn)){ lastRun=pnow; ue_leave(); }        // the world is going: the poll thread resets it
          else { float pdt=(lastRun==0)?0.016f:(float)(pnow-lastRun); if(pdt>0.25f) pdt=0.25f; lastRun=pnow; g_pe_drv++;
          giant_tick(pdt); club_tick(pdt); intro_tick(pdt); camview_tick(pdt); stream_tick(pdt); follow_update(pdt); bt_frame(pdt); drone_update(pdt); head_tick(pdt); menu_tick(); sm_tick_2311(); env_menu_tick(); perf_frame(pdt); ue_leave(); } } }
    club_pe(self,func,parms);                                        // the club's stick events (inert off its map)
    if(camview_pe(self,func,parms)) return;                          // Tribe's camera buttons give our camera back (camview.cpp)
    if(g_skinTrace) skin_trace_hit((uintptr_t)self,(uintptr_t)func,parms);
    if(g_envMenuOn && func && (func==(void*)g_emFnObjSet||func==(void*)g_emFnMouseDown||func==(void*)g_emFnListEvt)){
        uintptr_t p0=parms?*(uintptr_t*)parms:0;
        if(func==(void*)g_emFnListEvt){ int idx=em_item_idx(p0); if(idx>=0){ em_click(idx); return; }      // swallow ours
            if(g_emState!=EM_IDLE){ g_emUnloadReq=1; LOGI("[ENV] stock environment picked -> unloading ours"); } }   // Tribe carries on
        else if(func==(void*)g_emFnMouseDown){ int idx=em_widget_idx((uintptr_t)self); if(idx>=0){ em_click(idx); return; } }
        else { int idx=em_item_idx(p0);                                       // OnListItemObjectSet: label ours after Tribe fills the box
            if(idx>=0){ orig_pe(self,func,parms); em_map_widget((uintptr_t)self,idx); box_set_label((uintptr_t)self,g_emLabels[idx]); return; }
            em_map_widget((uintptr_t)self,-1); } }                           // a recycled box now shows someone else's item
    if(g_envMenuOn && func && parms && (func==(void*)g_emFnUWDown||func==(void*)g_emFnSkinApplied))   // 2311 boxes: press / apply
        em_pe_2311((uintptr_t)self,(uintptr_t)func,parms);                  // (both 0 on 2304)
    if(g_skinMenuOn && g_smMode==1 && func && parms && (func==(void*)g_smFnUWDown||func==(void*)g_smFnSkinApplied))   // avatar boxes (B)
        sm_pe_2311((uintptr_t)self,(uintptr_t)func,parms);
    if(g_skinMenuOn && func && (func==(void*)g_smFnObjSet||func==(void*)g_smFnMouseDown||func==(void*)g_smFnListEvt)){
        uintptr_t p0=parms?*(uintptr_t*)parms:0;
        if(func==(void*)g_smFnObjSet){                                       // a box was given an item: label ours after Tribe
            if(p0&&!g_smTribeRpm){ char cn[96]; class_name(p0,cn,sizeof cn); if(!strcmp(cn,"BP_ReadyPlayerMeAvatarSkin_C")&&sm_item_idx(p0)<0) g_smTribeRpm=p0; }
            orig_pe(self,func,parms); int idx=sm_item_idx(p0); sm_map_widget((uintptr_t)self,idx);
            if(idx>=0) sm_label_box((uintptr_t)self,idx); return; }
        if(func==(void*)g_smFnMouseDown){ int idx=sm_widget_idx((uintptr_t)self); if(idx>=0){ sm_load(idx); return; } }   // swallow ours
        if(func==(void*)g_smFnListEvt){ int idx=sm_item_idx(p0); if(idx>=0){ sm_load(idx); return; } } }                  // swallow ours
    // BLOCK Blueprint-level resets of our body while the keeper is on (Tribe setting AvatarBodyMesh to null/other).
    if(g_keep && !ue_busy() && g_fnSet && func==(void*)g_fnSet && (uintptr_t)self==g_body && parms && *(uintptr_t*)parms!=g_mymesh){
        g_resets_bp++; if(g_resets_bp<=20||(g_resets_bp%100)==0) load_status("BLOCKED BP reset of body -> 0x%lx (#%d)",(unsigned long)*(uintptr_t*)parms,g_resets_bp);
        return;                                                    // swallow it
    }
    // (mod2311: the 2304 ReceiveTick driver and the pawn-tick fallback are gone: on 2311 ReceiveTick never passes
    // ProcessEvent, and the driver above runs every frame once the world is up)
    // keeper: poll thread saw a NATIVE reset -> re-attach our (rooted) mesh here on the game thread
    if(g_reattach_req && g_keep && ue_enter()){ g_reattach_req=0; attach_mesh(g_body,g_mymesh); ue_leave(); }
    if(g_iso_req && ue_enter()){ g_iso_req=0;
        if(g_isoActor&&obj_alive(g_isoActor)){ ue_leave(); }                // already up (a late request): nothing to do
        else { if(g_isoActor){ unroot_object(g_isoActor); g_isoActor=0; g_isoComp=0; a2_drop_meshes(); g_trackParent=0; head_forget("our actor went away"); }
        spawn_iso_actor(g_mymesh); g_smActorHid=0; ue_leave();
        g_reports=0; g_report_ticks=2; } }                      // fresh RENDER reports ~1s after the spawn, then every 10s
    if(g_report_req && (g_body||g_isoComp) && ue_enter()){ g_report_req=0; g_reports++; render_report(); ue_leave(); }
    if(g_log_pe && g_resolved) pe_log_func((uintptr_t)func);     // diagnostic: capture avatar/skin/menu events
    if(g_logDeck && g_resolved) deck_log_pe((uintptr_t)self,(uintptr_t)func,parms);   // diagnostic: the deck capture (intro.cpp)
    // skin-cycle: after the first load, when Tribe (re)applies the RPM skin from the avatar menu, advance
    // to the next skin + arm a reload. Debounced 2s so init-time / repeated applies don't spin the cycle.
    if(g_loaded_once && !ue_busy() && g_apply_fn && func==(void*)g_apply_fn && parms){
        long now=(long)time(0);
        if(now-g_last_cycle>=2){ uintptr_t skin=*(uintptr_t*)parms;
            if(is_rpm_skin(skin)){ g_last_cycle=now; advance_skin(); g_load_req=1; } } }
    if(g_load_req && ue_enter()){ g_load_req=0; run_load_guarded(); ue_leave(); }
    if(g_bt_req && ue_enter()){ g_bt_req=0; run_guarded(bt_start,"body-tracking start"); ue_leave(); }
    if(g_bt_poll_req && ue_enter()){ g_bt_poll_req=0; run_guarded(bt_poll,"body-tracking poll"); ue_leave(); }
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
    uintptr_t st=find_live_class_sub("SelfieStick"), cap=0, rt=0;          // BP_SelfieStick_C (2304), TribeSelfieStick (2311)
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
    double r=g_dR,h=g_dH,s=g_dSpeed,l=g_dLook,b=g_dBob; int tgt=0, rset=0, hset=0, mode=0; char k[32], v[32];
    if(f){ while(fscanf(f," %31[^= \t\r\n]=%31s",k,v)==2){ double x=strtod(v,0);
            if(!strcmp(k,"radius")){ r=x; rset=1; } else if(!strcmp(k,"height")){ h=x; hset=1; } else if(!strcmp(k,"speed")) s=x;
            else if(!strcmp(k,"look")) l=x; else if(!strcmp(k,"bob")) b=x; else if(!strcmp(k,"target")) tgt=!strcmp(v,"auto")?1:0;
            else if(!strcmp(k,"mode")) mode=!strcmp(v,"path")?1:0; }
        fclose(f); }
    if(r<50) r=50; if(r>2000) r=2000; if(h<-200) h=-200; if(h>600) h=600; if(s<-90) s=-90; if(s>90) s=90;
    if(l<-300) l=-300; if(l>300) l=300; if(b<0) b=0; if(b>200) b=200;
    if(mode!=g_dMode){ g_dMode=mode; LOGI("[DRONE] mode=%s",mode?"path (shot reel: drone_path.txt or the built-in festival reel)":"orbit"); }
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
    bool on=file_present("drone_cam"), need=on||g_introArmed||g_viewArmed;   // a stage's intro (intro.cpp) and a camera-menu
                                                                     // view (camview.cpp) fly the drone's target too
    if(on){ drone_read_params(); drone_load_path(); } else if(need) drone_read_params();
    int tgt=g_droneTarget;
    if(g_droneCap && (obj_at(rd32(g_droneCap+OFF_Index))!=g_droneCap || capTgt!=tgt)){   // gone (room change) or target switched
        g_droneOn=0; g_droneCap=0; LOGI("[DRONE] camera changed (gone or new target); re-resolving"); }
    if(g_dronePC && obj_at(rd32(g_dronePC+OFF_Index))!=g_dronePC) g_dronePC=0;
    if(need){
        if(!g_fnSetWorldLR) g_fnSetWorldLR=find_by_path("/Script/Engine.SceneComponent.K2_SetWorldLocationAndRotation",0);
        if(!g_fnSetRelLR)   g_fnSetRelLR  =find_by_path("/Script/Engine.SceneComponent.K2_SetRelativeLocationAndRotation",0);
        if(g_offRelLoc<0||g_offRelRot<0){ uintptr_t sc=find_by_path("/Script/Engine.SceneComponent",1);   // mount pose (also set by a2)
            if(sc){ g_offRelLoc=prop_offset(sc,"RelativeLocation",0); g_offRelRot=prop_offset(sc,"RelativeRotation",0); } }
        if(!g_droneCap){
            if(tgt==0){ uintptr_t st=find_live_class_sub("SelfieStick");   // BP_SelfieStick_C (2304), TribeSelfieStick (2311)
                if(st){ int oc=prop_offset(rdptr(st+OFF_Class),"CaptureComponent2D",0); g_droneCap=oc>=0?rdptr(st+oc):0; } }
            else g_droneCap=find_live("NewSceneCaptureComponent2D","SceneCaptureComponent2D","SpectatorCameraAutoCam");
            capTgt=tgt; static int quiet=0;                               // armed by an intro alone: a miss is said once a minute
            if(g_droneCap||(quiet++%30)==0) LOGI("[DRONE] resolve (%s): capture=0x%lx setWorld=0x%lx setRel=0x%lx relLoc@%d relRot@%d%s",tgt?"Auto cam":"selfie stick",
                (unsigned long)g_droneCap,(unsigned long)g_fnSetWorldLR,(unsigned long)g_fnSetRelLR,g_offRelLoc,g_offRelRot,
                g_droneCap?"":(tgt?"  (Auto cam not found)":"  (take the selfie stick out)"));
            drone_dump_enum_once(); }
        if(tgt==1 && !g_dronePC){ g_dronePC=find_live_class_sub("TribePlayerControllerBP_C");   // 2304 only on purpose: on 2311 the
            // native controller's raw +0x974 (PC_AUTOCAM_NEXTCUT) is unverified, so target=auto there flies without parking the cuts
            LOGI("[DRONE] player controller=0x%lx",(unsigned long)g_dronePC); drone_dump_pc_once(g_dronePC); } }
    int want=(on&&g_droneCap&&g_fnSetWorldLR)?1:0;
    if(want!=g_droneOn){ g_droneOn=want; LOGI("[DRONE] %s",want?(tgt?"ON: flying the Auto cam (select the Auto angle)":
        "ON: flying the selfie-stick camera"):"OFF"); } }
// ---- extra avatar-menu boxes: poll-thread side (resolve functions, read skins/, find the live AvatarList) ----
static uintptr_t sm_find_avatar_list(){                 // the LIVE W_ProfileMenu AvatarList (not the /Game class template)
    if(g_smMode==1){                                     // 2311: the live TribeProfileMenuWidget's AvatarList (@0x398, a UListView)
        uintptr_t m=em_find_live("TribeProfileMenuWidget"); uintptr_t l=sm_obj_prop(m,"AvatarList");
        if(l&&obj_alive(l)&&em_is_a(l,"ListView")) return l; }
    char nm[96],cn[96],fp[400];
    for(uint32_t i=0;i<g_numElements;i++){ uintptr_t o=obj_at(i); if(!o) continue;
        obj_name(o,nm,sizeof nm); if(strcmp(nm,"AvatarList")) continue;
        class_name(o,cn,sizeof cn); if(strcmp(cn,"ListView")) continue;
        full_path(o,fp,sizeof fp); if(!strncmp(fp,"/Game/",6)||strstr(fp,"Default__")) continue;
        return o; }
    return 0; }
static void sm_read_skins(){                            // one box per tribemod/skins/*.glb, label = file name ("lampwing.glb" -> "Lampwing")
    char dir[600]; snprintf(dir,sizeof dir,"%s/skins",OUTDIR); DIR* d=opendir(dir); if(!d) return;
    char names[SM_MAX][128]; int n=0; struct dirent* e;
    while((e=readdir(d))&&n<SM_MAX){ size_t L=strlen(e->d_name); if(L>4&&L<120&&!strcasecmp(e->d_name+L-4,".glb")){ strcpy(names[n],e->d_name); n++; } }
    closedir(d);
    for(int i=0;i<n;i++) for(int j=i+1;j<n;j++) if(strcmp(names[i],names[j])>0){ char t[128]; strcpy(t,names[i]); strcpy(names[i],names[j]); strcpy(names[j],t); }
    bool tribeBox=g_smMode==1&&n<SM_MAX; if(tribeBox) strcpy(names[n++],"tribe");   // 2311: the last box is "Tribe Avatar"
    bool same=(n==g_smCount); for(int i=0;same&&i<n;i++) if(strcmp(names[i],g_smFiles[i])) same=false;
    if(same) return;
    for(int i=0;i<n;i++){ strcpy(g_smFiles[i],names[i]);
        if(!strcmp(names[i],"tribe")){ snprintf(g_smLabels[i],sizeof g_smLabels[i],"Tribe Avatar"); continue; }
        size_t L=strlen(names[i])-4; int k=0;
        for(size_t c=0;c<L&&k<63;c++){ char ch=names[i][c]; g_smLabels[i][k++]=(ch=='_')?' ':ch; } g_smLabels[i][k]=0;
        if(g_smLabels[i][0]>='a'&&g_smLabels[i][0]<='z') g_smLabels[i][0]-=32; }
    g_smCount=n; for(int i=0;i<n;i++) LOGI("[MENU] box %d: '%s' -> skins/%s",i,g_smLabels[i],g_smFiles[i]); }
// cheap lookup: object named `name` whose Outer is named `outerName` (no full-path building, unlike find_by_path)
static uintptr_t find_in_outer(const char* name,const char* outerName){
    char nm[200],on[96];
    for(uint32_t i=0;i<g_numElements;i++){ uintptr_t o=obj_at(i); if(!o) continue;
        obj_name(o,nm,sizeof nm); if(strcmp(nm,name)) continue;
        obj_name(rdptr(o+OFF_Outer),on,sizeof on); if(!strcmp(on,outerName)) return o; }
    return 0; }
static uintptr_t sm_find_live_rpm_skin(){              // any live (non-CDO) RPM skin item that isn't ours -> outer + identity
    char cn[96],fp[400];
    for(uint32_t i=0;i<g_numElements;i++){ uintptr_t o=obj_at(i); if(!o||sm_item_idx(o)>=0) continue;
        class_name(o,cn,sizeof cn); if(strcmp(cn,"BP_ReadyPlayerMeAvatarSkin_C")&&strcmp(cn,"TribeReadyPlayerMeAvatarSkin")) continue;   // 2304 / 2311
        if(rd32(o+OFF_Flags)&RF_ClassDefaultObject) continue; full_path(o,fp,sizeof fp); if(strstr(fp,"Default__")) continue;
        return o; }
    return 0; }
static void menu_resolve_engine_fns(){                  // shared by the avatar + environment boxes; engine functions are always loaded
    if(g_smFnAddItem&&g_smFnIndexOf&&g_smFnSpawn&&g_smGS&&g_smFnStr2Txt&&g_smKTL&&g_smFnSetText) return;
    if(!g_resolved) return;                              // mod2311: nothing to find before the object array (13:40: all 0)
    if(!g_smFnAddItem) g_smFnAddItem =find_by_path("/Script/UMG.ListView.AddItem",0);      // each missing one is retried
    if(!g_smFnIndexOf) g_smFnIndexOf =find_by_path("/Script/UMG.ListView.GetIndexForItem",0);
    if(!g_smFnSpawn)   g_smFnSpawn   =find_by_path("/Script/Engine.GameplayStatics.SpawnObject",0);
    if(!g_smGS)        g_smGS        =find_by_path("/Script/Engine.Default__GameplayStatics",0);
    if(!g_smFnStr2Txt) g_smFnStr2Txt =find_by_path("/Script/Engine.KismetTextLibrary.Conv_StringToText",0);
    if(!g_smKTL)       g_smKTL       =find_by_path("/Script/Engine.Default__KismetTextLibrary",0);
    if(!g_smFnSetText) g_smFnSetText =find_by_path("/Script/UMG.TextBlock.SetText",0);
    static int lastN=-1; int n=!!g_smFnAddItem+!!g_smFnIndexOf+!!g_smFnSpawn+!!g_smGS+!!g_smFnStr2Txt+!!g_smKTL+!!g_smFnSetText;
    if(n!=lastN){ lastN=n;                               // logged when the count changes (it was every 2 s while missing)
    LOGI("[MENU] engine fns (%d/7): AddItem=0x%lx GetIndexForItem=0x%lx SpawnObject=0x%lx GS=0x%lx Str2Text=0x%lx KTL=0x%lx SetText=0x%lx",n,
        (unsigned long)g_smFnAddItem,(unsigned long)g_smFnIndexOf,(unsigned long)g_smFnSpawn,(unsigned long)g_smGS,
        (unsigned long)g_smFnStr2Txt,(unsigned long)g_smKTL,(unsigned long)g_smFnSetText); } }
// 2311 (poll thread): the C++ menu's lookups, the live AvatarList, Tribe's RPM item, the one-time diagnostic, ON/OFF
static void sm_poll_2311(int tick){
    if(!g_smRpmCls) g_smRpmCls=find_by_path("/Script/TribeXR.TribeReadyPlayerMeAvatarSkin",1);
    if(!g_smWCls){ g_smWCls=find_by_path("/Script/TribeXR.TribeSkinItemWidget",1); g_smOffWSkin=g_smWCls?prop_offset(g_smWCls,"Skin",0):-1; }
    if(!g_smFnUWDown) g_smFnUWDown=find_by_path("/Script/UMG.UserWidget.OnMouseButtonDown",0);
    if(!g_smFnSkinApplied&&g_smWCls) g_smFnSkinApplied=em_find_child_func(g_smWCls,"OnSkinApplied");
    if(!g_smFnSetSelected&&g_smWCls) g_smFnSetSelected=em_find_child_func(g_smWCls,"SetSelected");
    if(!g_smFnToName) g_smFnToName=find_by_path("/Script/Engine.KismetStringLibrary.Conv_StringToName",0);
    if(!g_smKSL)      g_smKSL=find_by_path("/Script/Engine.Default__KismetStringLibrary",0);
    if(!g_smFnActHid) g_smFnActHid=find_by_path("/Script/Engine.Actor.SetActorHiddenInGame",0);
    if(!g_fnHid)      g_fnHid=find_by_path("/Script/Engine.SceneComponent.SetHiddenInGame",0);
    if(!g_fnRendered) g_fnRendered=find_by_path("/Script/Engine.PrimitiveComponent.WasRecentlyRendered",0);
    sm_read_skins();
    if(g_smList&&!obj_alive(g_smList)){ g_smList=0; LOGI("[MENU] avatar list went away"); }
    if(!g_smList&&(tick%3)==2){ static bool told=false; g_smList=sm_find_avatar_list();
        if(g_smList||!told){ told=!g_smList; LOGI("[MENU] live avatar list = 0x%lx%s",(unsigned long)g_smList,g_smList?" (TribeProfileMenuWidget.AvatarList)":" (open Profile > Avatars)"); } }
    if((!g_smTribeRpm||!obj_alive(g_smTribeRpm))&&g_smList&&(tick%3)==0){ uintptr_t r=sm_find_live_rpm_skin();
        if(r!=g_smTribeRpm){ g_smTribeRpm=r; LOGI("[MENU] Tribe's RPM skin object = 0x%lx",(unsigned long)r); } }
    if(g_smList&&!g_smDiagDone&&g_pawn){ g_smDiagDone=1; sm_diag_poll(g_smList); }
    int want=(g_smFnAddItem&&g_smFnIndexOf&&g_smFnSpawn&&g_smGS&&g_smRpmCls&&g_smWCls&&g_smOffWSkin>=0&&g_smFnUWDown&&g_smFnSetSelected
              &&g_smFnToName&&g_smKSL&&g_smFnActHid)?1:0;
    if(want!=g_skinMenuOn){ g_skinMenuOn=want;
        LOGI("[MENU] 2311 menu (C++) %s: TribeReadyPlayerMeAvatarSkin=0x%lx TribeSkinItemWidget=0x%lx Skin@%d press=0x%lx apply=0x%lx SetSelected=0x%lx ToName=0x%lx",
             want?"ON":"waiting for lookups",(unsigned long)g_smRpmCls,(unsigned long)g_smWCls,g_smOffWSkin,(unsigned long)g_smFnUWDown,
             (unsigned long)g_smFnSkinApplied,(unsigned long)g_smFnSetSelected,(unsigned long)g_smFnToName); } }
static void skin_menu_poll(){
    g_smKeepTribeAvatar=file_present("tribe_avatar_shown")?1:0;              // kill switch: Tribe's avatar stays visible
    { int bo=file_present("skin_boxes_off")?1:0; if(bo!=g_smBoxesOff){ g_smBoxesOff=bo; LOGI("[MENU] avatar boxes %s (tribemod/skin_boxes_off)",bo?"OFF":"on"); } }
    if(g_smMode==1&&file_present("skin_diag")){ char dp[600]; snprintf(dp,sizeof dp,"%s/skin_diag",OUTDIR); unlink(dp); sm_diag_poll(g_smList); }   // one-shot
    bool on=file_present("skin_menu");
    if(!on){ if(g_skinMenuOn){ g_skinMenuOn=0; LOGI("[MENU] OFF"); } return; }
    if(!g_resolved||!g_smMode) return;                   // mod2311: the lookups need the object array (all 0 before it)
    static int tick=0; tick++;
    menu_resolve_engine_fns();
    if(g_smMode==1){ sm_poll_2311(tick); return; }
    bool missing=!g_smRpmCls||!g_smFnObjSet||!g_smFnMouseDown||!g_smFnListEvt;
    if(missing&&(tick%3)==1){                            // Blueprint classes load lazily (menus: when first opened) -> retry
        if(!g_smRpmCls)     g_smRpmCls=find_by_path("/Game/Visuals/Skins/OculusAvatar/BP_ReadyPlayerMeAvatarSkin.BP_ReadyPlayerMeAvatarSkin_C",1);
        if(!g_smFnObjSet)   g_smFnObjSet=find_in_outer("OnListItemObjectSet","W_SkinItem_C");
        if(!g_smFnMouseDown)g_smFnMouseDown=find_in_outer("OnMouseButtonDown","W_SkinItem_C");
        if(!g_smFnListEvt)  g_smFnListEvt=find_in_outer("BndEvt__W_AchievementMenu_AvatarList_K2Node_ComponentBoundEvent_2_SimpleListItemEventDynamic__DelegateSignature","W_ProfileMenu_C");
        LOGI("[MENU] blueprint lookups: RpmSkinClass=0x%lx box.OnListItemObjectSet=0x%lx box.OnMouseButtonDown=0x%lx menu.AvatarListEvent=0x%lx",
            (unsigned long)g_smRpmCls,(unsigned long)g_smFnObjSet,(unsigned long)g_smFnMouseDown,(unsigned long)g_smFnListEvt); }
    sm_read_skins();
    if(g_smList&&!obj_alive(g_smList)){ g_smList=0; LOGI("[MENU] avatar list went away"); }
    if(!g_smList&&(tick%3)==2){ g_smList=sm_find_avatar_list(); LOGI("[MENU] live avatar list = 0x%lx%s",(unsigned long)g_smList,g_smList?"":" (open your avatar menu)"); }
    if((!g_smTribeRpm||!obj_alive(g_smTribeRpm))&&g_smList&&(tick%3)==0){ g_smTribeRpm=sm_find_live_rpm_skin();
        LOGI("[MENU] Tribe's RPM skin object = 0x%lx",(unsigned long)g_smTribeRpm); }
    int want=(g_smFnAddItem&&g_smFnIndexOf&&g_smFnSpawn&&g_smGS&&g_smRpmCls&&g_smFnObjSet&&g_smFnMouseDown)?1:0;
    if(want!=g_skinMenuOn){ g_skinMenuOn=want; LOGI("[MENU] %s",want?"ON":"waiting for lookups"); } }
// ---- custom environments: poll-thread side (resolve, read envs.txt, find the live list / game state / Void screens) ----
static uintptr_t em_find_env_list(){                    // the LIVE W_VisualsMenu EnvironmentList (not the /Game class template)
    if(g_emMode==1){                                     // 2311: the live TribeVisualsMenuWidget's EnvironmentList (a C++ property)
        uintptr_t m=em_find_live("TribeVisualsMenuWidget"); int o=m?prop_offset(rdptr(m+OFF_Class),"EnvironmentList",0):-1;
        uintptr_t l=o>=0?rdptr(m+(uintptr_t)o):0;
        if(l&&obj_alive(l)&&em_is_a(l,"ListView")) return l;
        static int told=0; if(m&&(told++%30)==0){ char cn[96]="-"; if(l&&in_range(l,0x30)) class_name(l,cn,sizeof cn);
            LOGI("[ENV] TribeVisualsMenuWidget 0x%lx: EnvironmentList@%d = 0x%lx (%s), not a live ListView yet",(unsigned long)m,o,(unsigned long)l,cn); } }
    char nm[96],cn[96],fp[400];
    for(uint32_t i=0;i<g_numElements;i++){ uintptr_t o=obj_at(i); if(!o) continue;
        obj_name(o,nm,sizeof nm); if(strcmp(nm,"EnvironmentList")) continue;
        class_name(o,cn,sizeof cn); if(strcmp(cn,"ListView")) continue;
        full_path(o,fp,sizeof fp); if(!strncmp(fp,"/Game/",6)||strstr(fp,"Default__")) continue;
        return o; }
    return 0; }
static uintptr_t em_find_live_env_item(){              // any live (non-CDO) BP_EnvironmentSkin_C that isn't ours -> outer for ours
    char cn[96],fp[400];                                 // (2311: TribeEnvironmentSkin)
    for(uint32_t i=0;i<g_numElements;i++){ uintptr_t o=obj_at(i); if(!o||em_item_idx(o)>=0) continue;
        class_name(o,cn,sizeof cn); if(strcmp(cn,"TribeEnvironmentSkin")&&strcmp(cn,"BP_EnvironmentSkin_C")) continue;
        if(rd32(o+OFF_Flags)&RF_ClassDefaultObject) continue; full_path(o,fp,sizeof fp); if(strstr(fp,"Default__")) continue;
        return o; }
    return 0; }
static void em_read_envs(){                             // tribemod/envs.txt: "Label=/Game/Long/Package/Name" per line ('#' = comment)
    char p[600]; snprintf(p,sizeof p,"%s/envs.txt",OUTDIR); FILE* f=fopen(p,"r");
    char labels[EM_MAX][64], paths[EM_MAX][256]; int n=0;
    if(f){ char line[400];
        while(n<EM_MAX&&fgets(line,sizeof line,f)){ line[strcspn(line,"\r\n")]=0; char* eq=strchr(line,'=');
            if(line[0]=='#'||!eq||eq==line||eq[1]!='/') continue; *eq=0;
            snprintf(labels[n],sizeof labels[n],"%s",line); snprintf(paths[n],sizeof paths[n],"%s",eq+1); n++; }
        fclose(f); }
    else { snprintf(labels[0],sizeof labels[0],"Festival"); snprintf(paths[0],sizeof paths[0],"/Game/Mods/Festival/Maps/Environment_Festival"); n=1; }
    bool same=(n==g_emCount); for(int i=0;same&&i<n;i++) if(strcmp(labels[i],g_emLabels[i])||strcmp(paths[i],g_emPaths[i])) same=false;
    if(same) return;
    for(int i=0;i<n;i++){ strcpy(g_emLabels[i],labels[i]); strcpy(g_emPaths[i],paths[i]); }
    g_emCount=n; for(int i=0;i<n;i++) LOGI("[ENV] box %d: '%s' -> %s",i,g_emLabels[i],g_emPaths[i]); }
static uintptr_t em_find_void_item(){                    // Tribe's own list item whose Name (environment-table row) is Environment_Void
    static int oName=-2; if(oName==-2) oName=g_emCls?prop_offset(g_emCls,"Name",0):-2; if(oName<0) return 0;
    static int oType=-2; if(oType==-2) oType=(g_emMode==1&&g_emCls)?prop_offset(g_emCls,"EnvironmentType",0):-1;   // 2311: also by its enum
    char cn[96],nm[128]; refresh_numelements(); uintptr_t byType=0;
    for(uint32_t i=0;i<g_numElements;i++){ uintptr_t o=obj_at(i); if(!o||em_item_idx(o)>=0) continue;
        class_name(o,cn,sizeof cn); if(strcmp(cn,"TribeEnvironmentSkin")&&strcmp(cn,"BP_EnvironmentSkin_C")) continue;   // 2311 / 2304
        if(rd32(o+OFF_Flags)&RF_ClassDefaultObject) continue;
        fname_resolve(rd32(o+(uintptr_t)oName),nm,sizeof nm); if(!strcmp(nm,"Environment_Void")) return o;
        if(oType>=0&&g_emVoid>=0&&!byType&&rd8(o+(uintptr_t)oType)==(uint8_t)g_emVoid) byType=o; }
    if(byType){ fname_resolve(rd32(byType+(uintptr_t)oName),nm,sizeof nm); LOGI("[ENV] no item named Environment_Void; the one with EnvironmentType=Void is '%s'",nm); }
    return byType; }
// ---- mixer probe v2 (read-only; only while tribemod/probe_on exists). Which Blueprint variables hold the channel
// faders, the crossfader and the headphone cues? (The user cues the next song "with the volume down with the headphone
// on so the crowd cant hear", so the lights must follow the channel the crowd hears.) Probe v1 filled its 48 slots with
// the CDJ's Marker_* button objects. This one logs every numeric variable of these classes' live instances, from each
// instance's class down to the engine base classes, then every change. Poll thread, every 0.5 s.
#define PR_C 5
#define PR_I 40
#define PR_P 160
struct ProbeCls { const char* path; uintptr_t cls; int np; int po[PR_P]; uint8_t pt[PR_P]; char pn[PR_P][48]; int ni;
                  uintptr_t in[PR_I]; double last[PR_I][PR_P]; float quiet[PR_I][PR_P]; uint8_t moves[PR_I][PR_P]; bool seen[PR_I]; };
static const char* PR_PATH[PR_C]={"/Script/TribeXR.TribeDeck","/Script/TribeXR.TribeConsole","/Script/TribeXR.TribeMixerChannelDevice",
                                  "/Script/TribeXR.TribeMixerSliderBase","/Script/TribeXR.TribeMixerKnobBase"};   // 0.12.6 (2311): C++
static const char* PR_PATH_BP[PR_C]={"/Game/Equipment/Deck/BP_Deck.BP_Deck_C","/Game/Equipment/Mixer/BP_Console.BP_Console_C",
                                  "/Game/Equipment/BP_MixerChannelDevice.BP_MixerChannelDevice_C",
                                  "/Game/Equipment/Mixer/BP_MixerSliderBase.BP_MixerSliderBase_C",
                                  "/Game/Equipment/Mixer/BP_MixerKnobBase.BP_MixerKnobBase_C"};   // 2304; knobs: the user's filters
static ProbeCls g_pr[PR_C];                                           // zero-initialised (.bss); paths set on first use
static bool probe_engine_base(const char* cn){
    static const char* stop[]={"Actor","Pawn","Character","Object","ActorComponent","SceneComponent","PrimitiveComponent",
                               "MeshComponent","StaticMeshComponent","SkeletalMeshComponent","UserWidget","Widget"};
    for(const char* x: stop) if(!strcmp(cn,x)) return true;
    return false; }
static void probe_vars(ProbeCls* pc,uintptr_t inst){                  // the numeric variables of inst's class chain
    char cn[96], nm[64], ty[32]; int n=0;
    for(uintptr_t c=rdptr(inst+OFF_Class); c&&n<PR_P; c=rdptr(c+OFF_Super)){
        obj_name(c,cn,sizeof cn); if(probe_engine_base(cn)) break;
        for(uintptr_t f=rdptr(c+OFF_ChildProps); f&&n<PR_P; f=rdptr(f+FF_Next)){
            ffield_type(f,ty,sizeof ty); uint8_t t=0;
            if(!strcmp(ty,"FloatProperty")) t=1; else if(!strcmp(ty,"DoubleProperty")) t=2;
            else if(!strcmp(ty,"BoolProperty")||!strcmp(ty,"ByteProperty")||!strcmp(ty,"EnumProperty")) t=3;
            else if(!strcmp(ty,"IntProperty")) t=4;
            if(!t) continue;
            fname_resolve(rd32(f+FF_Name),nm,sizeof nm);
            snprintf(pc->pn[n],sizeof pc->pn[n],"%s.%s",cn,nm); pc->po[n]=(int)rd32(f+FP_Offset); pc->pt[n]=t; n++; } }
    pc->np=n;
    LOGI("[PROBE] %s: %d numeric variables",pc->path,n);
    for(int i=0;i<n;i+=6){ char line[600]; int k=0;
        for(int j=i;j<n&&j<i+6;j++) k+=snprintf(line+k,sizeof line-k,"%s@%d ",pc->pn[j],pc->po[j]);
        LOGI("[PROBE]   %s",line); } }
static void probe_poll(){                                             // POLL thread, every 0.5 s while probe_on exists
    static bool on=false; bool want=file_present("probe_on");
    if(want!=on){ on=want; LOGI("[PROBE] %s",on?"ON (tribemod/probe_on)":"off"); }
    if(!on) return;
    static int tick=0, lines=0; tick++;
    for(int k=0;k<PR_C;k++) if(!g_pr[k].path) g_pr[k].path=PR_PATH[k];
    if((tick%20)==1){                                                  // every 10 s: find the classes and their instances
        for(int k=0;k<PR_C;k++) if(!g_pr[k].cls){ g_pr[k].cls=find_by_path(PR_PATH[k],1); g_pr[k].path=PR_PATH[k];
            if(!g_pr[k].cls){ g_pr[k].cls=find_by_path(PR_PATH_BP[k],1); g_pr[k].path=PR_PATH_BP[k]; } }   // 2311 C++, else the 2304 BP
        refresh_numelements(); int cnt[PR_C]={0}; uintptr_t got[PR_C][PR_I];
        for(uint32_t i=0;i<g_numElements;i++){ uintptr_t o=obj_at(i); if(!o) continue;
            if(rd32(o+OFF_Flags)&(RF_ClassDefaultObject|0x20u|0x40000000u)) continue;
            int depth=0; for(uintptr_t c=rdptr(o+OFF_Class); c&&depth<12; c=rdptr(c+OFF_Super),depth++)
                for(int k=0;k<PR_C;k++) if(c==g_pr[k].cls&&cnt[k]<PR_I){ got[k][cnt[k]++]=o; depth=99; break; } }
        for(int k=0;k<PR_C;k++){ ProbeCls* pc=&g_pr[k];
            bool chg=cnt[k]!=pc->ni; for(int j=0;j<cnt[k]&&!chg;j++) if(got[k][j]!=pc->in[j]) chg=true;
            if(!chg) continue;
            for(int j=0;j<cnt[k];j++){ pc->in[j]=got[k][j]; pc->seen[j]=false; }
            pc->ni=cnt[k];
            if(cnt[k]&&!pc->np) probe_vars(pc,got[k][0]);
            char on_[96], ou[96];
            for(int j=0;j<cnt[k];j++){ obj_name(got[k][j],on_,sizeof on_); uintptr_t ow=rdptr(got[k][j]+OFF_Outer); if(ow) obj_name(ow,ou,sizeof ou); else snprintf(ou,sizeof ou,"-");
                LOGI("[PROBE] %s #%d = %s (in %s)",pc->path+(strrchr(pc->path,'.')?strrchr(pc->path,'.')-pc->path+1:0),j,on_,ou); } } }
    for(int k=0;k<PR_C;k++){ ProbeCls* pc=&g_pr[k];
        for(int j=0;j<pc->ni;j++){ uintptr_t o=pc->in[j]; if(!o||!in_range(o,0x30)) continue;
            for(int v=0;v<pc->np;v++){ uintptr_t a=o+(uintptr_t)pc->po[v]; double x=0;
                if(pc->pt[v]==1){ float f=0; sr(a,&f,4); x=f; } else if(pc->pt[v]==2){ sr(a,&x,8); }
                else if(pc->pt[v]==4){ int32_t q=0; sr(a,&q,4); x=q; } else { uint8_t q=0; sr(a,&q,1); x=q; }
                pc->quiet[j][v]+=0.5f;
                if(pc->seen[j]&&fabs(x-pc->last[j][v])<1e-4) continue;
                bool first=!pc->seen[j];
                if(!first&&pc->moves[j][v]>=3&&pc->quiet[j][v]<2.0f){ continue; }   // always moving: at most every 2 s
                if(!first&&pc->moves[j][v]<255) pc->moves[j][v]++;
                if(!first&&lines++<6000) LOGI("[PROBE] %s #%d %s = %.4f",strrchr(pc->path,'.')+1,j,pc->pn[v],x);
                pc->last[j][v]=x; pc->quiet[j][v]=0; }
            pc->seen[j]=true; } } }
static int g_stgTries=0, g_stgWantIdx=-1, g_stgSettle=0; static bool g_stgGaveUp=false; static char g_stgWant[64]="";   // [READY]
static void env_menu_poll(){
    bool on=file_present("env_menu");
    if(!on){ if(g_envMenuOn){ g_envMenuOn=0; LOGI("[ENV] OFF"); } return; }
    if(!g_resolved) return;                              // engine objects not up yet (Tribe waits for the headset to be worn)
    static int tick=0, settle=0, lastEnv=-2; tick++;
    menu_resolve_engine_fns();
    if((tick%4)==1) mpc_lookup();                        // Tribe's video mapping collection (for our big screen)
    if((tick%4)==3) giant_lookup();                      // giant intro: MPC_DinoGiant + the VROrigin setter
    if((tick%4)==2) song_lookup();                       // song mode: Tribe's decks (only while song.txt names a song)
    if((tick%4)==0) club_lookup();                       // the club: walking (hook/club.cpp)
    if((tick%4)==1) intro_lookup();                      // a stage's stream intro (hook/intro.cpp)
    probe_poll();                                        // mixer probe v2 (only while tribemod/probe_on exists)
    if(!g_emLSD){                                        // engine + native Tribe functions: always loaded
        g_emLSD         =find_by_path("/Script/Engine.Default__LevelStreamingDynamic",0);
        g_emFnIsLoaded  =find_by_path("/Script/Engine.LevelStreaming.IsLevelLoaded",0);
        g_emFnIsVisible =find_by_path("/Script/Engine.LevelStreaming.IsLevelVisible",0);
        g_emFnSetLoaded =find_by_path("/Script/Engine.LevelStreaming.SetShouldBeLoaded",0);
        g_emFnSetVisible=find_by_path("/Script/Engine.LevelStreaming.SetShouldBeVisible",0);
        g_emFnHidden    =find_by_path("/Script/Engine.Actor.SetActorHiddenInGame",0);
        g_emFnActLoc    =find_by_path("/Script/Engine.Actor.K2_GetActorLocation",0);
        g_emFnActRot    =find_by_path("/Script/Engine.Actor.K2_GetActorRotation",0);
        g_emFnActScale  =find_by_path("/Script/Engine.Actor.GetActorScale3D",0);
        g_emFnBounds    =find_by_path("/Script/Engine.Actor.GetActorBounds",0);
        g_emActorCls    =find_by_path("/Script/Engine.Actor",0);
        g_emFnSetEnv    =find_by_path("/Script/TribeXR.TribeGameState.SetEnvironment",0);
        g_emFnGetGS     =find_by_path("/Script/Engine.GameplayStatics.GetGameState",0);
        g_emFnFileExists=find_by_path("/Script/Engine.BlueprintPathsLibrary.FileExists",0);
        g_emFnContentDir=find_by_path("/Script/Engine.BlueprintPathsLibrary.ProjectContentDir",0);
        g_emBPL         =find_by_path("/Script/Engine.Default__BlueprintPathsLibrary",0);
        g_emFnCurLevel  =find_by_path("/Script/Engine.GameplayStatics.GetCurrentLevelName",0);
        g_emFnMakeSOP   =find_by_path("/Script/Engine.KismetSystemLibrary.MakeSoftObjectPath",0);
        g_emFnSOP2Ref   =find_by_path("/Script/Engine.KismetSystemLibrary.Conv_SoftObjPathToSoftObjRef",0);
        g_emKSL         =find_by_path("/Script/Engine.Default__KismetSystemLibrary",0);
        g_emFnLoadLvlSoft=find_by_path("/Script/Engine.LevelStreamingDynamic.LoadLevelInstanceBySoftObjectPtr",0);
        uintptr_t e=find_by_path("/Script/TribeXR.ETribeEnvironmentType",0), d=0; int ne=enum_entries(e,&d); char nm[96]; int64_t v;
        if(e) g_emEnum=e;
        for(int i=0;i<ne;i++) if(enum_entry(d,i,nm,sizeof nm,&v)){ LOGI("[ENV] ETribeEnvironmentType %s = %lld",nm,(long long)v); if(!strcmp(nm,"Void")) g_emVoid=v; }
        LOGI("[ENV] fns: LoadLevelInstanceBySoftObjectPtr=0x%lx LSD=0x%lx IsLoaded=0x%lx IsVisible=0x%lx SetLoaded=0x%lx SetVisible=0x%lx Hidden=0x%lx SetEnvironment=0x%lx Void=%lld",
            (unsigned long)g_emFnLoadLvlSoft,(unsigned long)g_emLSD,(unsigned long)g_emFnIsLoaded,(unsigned long)g_emFnIsVisible,(unsigned long)g_emFnSetLoaded,
            (unsigned long)g_emFnSetVisible,(unsigned long)g_emFnHidden,(unsigned long)g_emFnSetEnv,(long long)g_emVoid); }
    if(!g_emMode){                                       // which menu: Tribe 0.12.6's C++ one (2311) or the Blueprint one (2304)
        static int tries=0; refresh_numelements(); uintptr_t c=find_by_path("/Script/TribeXR.TribeEnvironmentSkin",1);
        if(c){ g_emWCls=find_by_path("/Script/TribeXR.TribeSkinItemWidget",1); g_emOffWSkin=g_emWCls?prop_offset(g_emWCls,"Skin",0):-1;
            g_emFnUWDown=find_by_path("/Script/UMG.UserWidget.OnMouseButtonDown",0);
            g_emFnSkinApplied=g_emWCls?em_find_child_func(g_emWCls,"OnSkinApplied"):0;
            g_emCls=c; g_emMode=1;
            LOGI("[ENV] 2311 menu (C++): TribeEnvironmentSkin=0x%lx TribeSkinItemWidget=0x%lx Skin@%d | press UserWidget.OnMouseButtonDown=0x%lx"
                 " | apply TribeSkinItemWidget.OnSkinApplied=0x%lx%s",(unsigned long)c,(unsigned long)g_emWCls,g_emOffWSkin,(unsigned long)g_emFnUWDown,
                 (unsigned long)g_emFnSkinApplied,(g_emWCls&&g_emOffWSkin>=0&&(g_emFnUWDown||g_emFnSkinApplied))?"":
                 " -> our boxes can't see a press: load a stage with active_env.txt or env_autotest"); }
        else if(g_worldUp&&++tries>=3){ g_emMode=2; LOGI("[ENV] Blueprint menu (2304)"); } }
    bool missing=g_emMode==2&&(!g_emCls||!g_emFnObjSet||!g_emFnMouseDown||!g_emFnListEvt);   // 2311: none of these exist
    if(missing&&(tick%3)==1){                            // Blueprint classes load lazily (the visuals menu: when first opened) -> retry
        if(!g_emCls)         g_emCls=find_by_path("/Game/Visuals/Skins/Environment/BP_EnvironmentSkin.BP_EnvironmentSkin_C",1);
        if(!g_emFnObjSet)    g_emFnObjSet=find_in_outer("OnListItemObjectSet","W_SkinItem_C");
        if(!g_emFnMouseDown) g_emFnMouseDown=find_in_outer("OnMouseButtonDown","W_SkinItem_C");
        if(!g_emFnListEvt)   g_emFnListEvt=find_in_outer("BndEvt__W_VisualsMenu_EnvironmentList_K2Node_ComponentBoundEvent_2_SimpleListItemEventDynamic__DelegateSignature","W_VisualsMenu_C");
        static int found=-1; int nf=(g_emCls?1:0)+(g_emFnObjSet?1:0)+(g_emFnMouseDown?1:0)+(g_emFnListEvt?1:0);
        if(nf!=found){ found=nf;                         // log on change only (the logcat ring buffer is small)
            LOGI("[ENV] blueprint lookups: EnvironmentSkinClass=0x%lx box.OnListItemObjectSet=0x%lx box.OnMouseButtonDown=0x%lx menu.EnvironmentListEvent=0x%lx%s",
                (unsigned long)g_emCls,(unsigned long)g_emFnObjSet,(unsigned long)g_emFnMouseDown,(unsigned long)g_emFnListEvt,nf<4?" (open Visuals > Environments)":""); } }
    em_read_envs();
    if(g_emList&&!obj_alive(g_emList)){ g_emList=0; LOGI("[ENV] environment list went away"); }
    if(!g_emList&&(tick%3)==2){ static bool told=false; g_emList=em_find_env_list();
        if(g_emList||!told){ told=!g_emList; LOGI("[ENV] live environment list = 0x%lx%s",(unsigned long)g_emList,g_emList?"":" (open Visuals > Environments)"); } }
    if((!g_emTribeItem||!obj_alive(g_emTribeItem))&&g_emList&&(tick%3)==0){ g_emTribeItem=em_find_live_env_item();
        LOGI("[ENV] Tribe's environment object = 0x%lx",(unsigned long)g_emTribeItem); }
    if((!g_emVoidItem||!obj_alive(g_emVoidItem))&&g_emCls&&g_emList&&(tick%3)==0){ uintptr_t v=em_find_void_item();
        if(v!=g_emVoidItem){ g_emVoidItem=v; LOGI("[ENV] Tribe's 'The Void' list item = 0x%lx%s",(unsigned long)v,v?"":" (not found yet)"); } }
    if(!g_emRig&&(tick%5)==0&&g_emMode){                 // 2311: exactly TribeRig (TribeRigSkin / TribeRigSaveGame contain it)
        g_emRig=g_emMode==1?em_find_live_pl("TribeRig"):find_live_class_sub("BP_Rig_C"); if(g_emRig) LOGI("[ENV] DJ rig actor = 0x%lx",(unsigned long)g_emRig); }
    if(g_emState!=EM_IDLE){                              // the Void's two screens (only while we switch to / sit on the Void)
        static const char* scr[2]={"SM_BackdropScreen","SM_BackdropScreen_ChromaKey"};
        refresh_numelements();                           // the Void's actors were just created: past the cached object count
        for(int i=0;i<2;i++) if(!g_emScreens[i]||!obj_alive(g_emScreens[i])){ g_emScreens[i]=find_live(scr[i],"StaticMeshActor","Environment_Void");
            if(g_emScreens[i]) LOGI("[ENV] Void %s = 0x%lx",scr[i],(unsigned long)g_emScreens[i]); }
        // 2311 (Environment_Void.umap changed): if the backdrop isn't found by name, take what the Void registered as Tribe's
        // backdrop (TribeVisualsManager.BackdropStaticMeshActor), only if it sits in the Void's level (never ours, never the
        // environment we came from)
        if(g_emMode==1&&(!g_emScreens[0]||!obj_alive(g_emScreens[0]))){
            static uintptr_t vmc=0; if(!vmc||!obj_alive(vmc)) vmc=em_find_live("TribeVisualsManager");
            int o=vmc?prop_offset(rdptr(vmc+OFF_Class),"BackdropStaticMeshActor",0):-1; uintptr_t a=o>=0?rdptr(vmc+(uintptr_t)o):0;
            if(a&&a!=g_emOurScreen&&obj_alive(a)){ char fp[400]; full_path(a,fp,sizeof fp);
                if(strstr(fp,"Environment_Void")&&!strstr(fp,"/Mods/")){ g_emScreens[0]=a;
                    LOGI("[ENV] Void backdrop (not found by name): the visuals manager's BackdropStaticMeshActor 0x%lx (%s)",(unsigned long)a,fp); } } }
        static int chromaMiss=0; if(g_emMode==1&&!g_emScreens[1]&&++chromaMiss==10)
            LOGI("[ENV] Void SM_BackdropScreen_ChromaKey not found by name (2311 map changed?): it stays as Tribe has it"); }
    // re-apply the saved choice once per launch, after Tribe's own saved environment has settled (same value for ~8 s)
    int cur=em_cur_env(); if(cur!=lastEnv){ lastEnv=cur; settle=0; } else settle++;
    { static int sk=0; if(++sk==400){ int shown=0; refresh_numelements();
        for(uint32_t i=0;i<g_numElements && shown<40;i++){ uintptr_t o=obj_at(i); if(!o) continue;
            char cn[128], fp[400]; class_name(o,cn,sizeof cn);
            if(!(strstr(cn,"Skin")||strstr(cn,"Rpm")||strstr(cn,"ReadyPlayer")||strstr(cn,"AvatarList")||strstr(cn,"AvatarItem"))) continue;
            if(rd32(o+OFF_Flags)&RF_ClassDefaultObject) continue;
            full_path(o,fp,sizeof fp); if(strstr(fp,"Default__")) continue;
            shown++; LOGI("[SKIN] diag %d: class %s, path %s", shown, cn, fp); }
        LOGI("[SKIN] diag: %d skin-like objects listed", shown); } }
    // the stage you picked last (mod2311, notes 9 + 18): a mod stage's label is loaded once Tribe's own environment has
    // held still (~8 s; the world is needed, our avatar is not); "stock:<name>" is Tribe's to restore. A failed load (or
    // our level going away) is tried again 15 s later, 3 more times; nothing here deletes active_env.txt.
    { static char lastWant[64]="\x01"; static double nextAt=0;
      char want[64]=""; bool have=read_trim_file("active_env.txt",want,sizeof want);
      int wi=-1; if(have) for(int i=0;i<g_emCount;i++) if(!strcmp(want,g_emLabels[i])){ wi=i; break; }
      if(strcmp(want,lastWant)){ snprintf(lastWant,sizeof lastWant,"%s",want); g_stgTries=0; g_stgGaveUp=false; nextAt=0; }   // a new pick
      snprintf(g_stgWant,sizeof g_stgWant,"%s",want); g_stgWantIdx=wi; g_stgSettle=settle;
      if(g_emFailed){ g_emFailed=0;
          if(g_stgTries>=4){ if(!g_stgGaveUp){ g_stgGaveUp=true; LOGI("[ENV] auto: '%s' failed %d times: giving up this launch",want,g_stgTries); } }
          else { nextAt=mono_now()+15.0; LOGI("[ENV] auto: the load did not hold; trying again in 15 s (%d of 4 tries used)",g_stgTries); } }
      { static double inSince=-1; bool in=g_emState==EM_ACTIVE&&g_emActive==wi&&wi>=0;   // held 60 s: a later loss gets fresh tries
        if(!in) inSince=-1; else if(inSince<0) inSince=mono_now(); else if(mono_now()-inSince>=60.0) g_stgTries=0; }
      if(wi>=0&&!g_stgGaveUp&&!g_emTribeSwitched&&g_emState==EM_IDLE&&g_emReq<0&&g_envMenuOn&&g_emGameState&&(cur>0||g_emEnvOff<0)
         &&settle>=4&&mono_now()>=nextAt&&g_stgTries<4){
          static int total=0; if(++total>12){ if(total==13) LOGI("[ENV] auto: 12 loads this launch: no more until the next launch"); g_stgGaveUp=true; return; }
          g_stgTries++; nextAt=mono_now()+60.0; g_emReq=wi;
          LOGI("[ENV] auto: applying '%s' (try %d; Tribe settled on %d %s)",want,g_stgTries,cur,em_env_name(cur)); } }
    // tribemod/env_autotest (one-shot): load the first environment without a click, once Tribe has settled (unattended tests)
    if(file_present("env_autotest")&&g_envMenuOn&&g_emGameState&&settle>=3&&g_emState==EM_IDLE&&g_emCount>0){
        char ap[600]; snprintf(ap,sizeof ap,"%s/env_autotest",OUTDIR); unlink(ap); g_emReq=0;
        LOGI("[ENV] autotest: loading '%s' without a click (Tribe settled on %d %s)",g_emLabels[0],cur,em_env_name(cur)); }
    { static int lk=0; if(++lk==200) LOGI("[ENV] lookups: AddItem=0x%lx IndexOf=0x%lx Spawn=0x%lx GS=0x%lx LoadLvlSoft=0x%lx LSD=0x%lx envMenu=%d",
        (unsigned long)g_smFnAddItem,(unsigned long)g_smFnIndexOf,(unsigned long)g_smFnSpawn,(unsigned long)g_smGS,(unsigned long)g_emFnLoadLvlSoft,(unsigned long)g_emLSD,(int)g_envMenuOn); }
    int want=(g_smFnAddItem&&g_smFnIndexOf&&g_smFnSpawn&&g_smGS&&g_emFnLoadLvlSoft&&g_emLSD)?1:0;     // boxes also need the lazy BP lookups
    if(want!=g_envMenuOn){ g_envMenuOn=want; LOGI("[ENV] %s",want?"ON":"waiting for lookups"); } }
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
#include "usmap.cpp"                                                 // the .usmap dump: Tribe's type mappings, for reading its assets offline
#include "native.cpp"                                                // the native dump: Tribe's C++ classes, functions and vtables, for Ghidra
// ===================== the supervisor (mod2311; claudedocs/mod_2311_plan.md section 2) =====================
// Runs on the poll thread every 0.5 s: the mod switching on, the object array, the world, the character; the stage is in
// env_menu_poll. Every part waits for exactly what it needs, retries with a limit, and logs one line when it changes.
// The [READY] line sums them up (logcat, tribemod/ready.txt, one result line per launch in tribemod/ready_history.txt).
static int g_hookState=0;                            // 1 hooked + verified, 2 hooked, mod asleep until tribemod is readable,
static char g_hookWhy[120]="not tried";              // 3 safe mode (executor_on absent), -1 failed (g_hookWhy)
static double g_t0=0;                                // when the constructor ran (CLOCK_MONOTONIC)
// ---- the mod switching on: in pass-through until tribemod/executor_on can be read (the first launch after an install)
static void modon_poll(){
    if(g_mod_on||g_hookState!=2) return;
    static int tk=0; if((tk++%2)!=0) return;
    int st=tribemod_state();
    if(st==1){ g_mod_on=1; g_hookState=1; snprintf(g_hookWhy,sizeof g_hookWhy,"%s","ok");
        LOGI("[HOOK] tribemod/ is readable now (%.1f s after the library loaded): the mod is on",mono_now()-g_t0); }
    else if(st==0){ static bool said=false; if(!said){ said=true; LOGI("[HOOK] tribemod/ is readable but executor_on is absent: the mod stays off (safe mode)"); }
        g_hookState=3; snprintf(g_hookWhy,sizeof g_hookWhy,"%s","executor_on absent"); } }
// ---- the world: Tribe's local pawn (via the camera manager), found here, wired on the game thread (world_wire)
static void world_poll(){
    if(!g_resolved||!g_mod_on) return;
    static int tk=0; tk++;
    uintptr_t p=g_pawn;
    if(p){
        char cn[64]="?"; bool ok=obj_alive(p); if(ok){ class_name(p,cn,sizeof cn); ok=!strcmp(cn,"TribePawn")||!strcmp(cn,"TribePawnBP_C"); }
        if(!ok){ if(g_worldSeen==g_worldGen){ g_worldUp=0; g_worldCamMgr=0; g_worldPawnHint=0; g_worldGen=g_worldGen+1;
                LOGI("[WORLD] Tribe's pawn 0x%lx went away (a level or room change): everything world-bound is dropped and wired again (gen %d)",(unsigned long)p,(int)g_worldGen); }
            return; }
        if(!g_worldUp){ g_worldUp=1; g_worldUpAt=mono_now(); LOGI("[WORLD] up: pawn 0x%lx (%s), %.1f s after the library loaded (gen %d)",(unsigned long)p,cn,g_worldUpAt-g_t0,(int)g_worldGen); }
        return; }
    if(g_worldSeen!=g_worldGen||g_wire_req||(tk%4)!=1) return;          // every 2 s until there is a pawn
    if(g_fpsz<0) calib_fprop_size();                                    // here, so the game thread's first call doesn't scan
    if(!g_fnLoc)        g_fnLoc       =find_by_path("/Script/Engine.SceneComponent.K2_GetComponentLocation",0);
    if(!g_fnGetRot)     g_fnGetRot    =find_by_path("/Script/Engine.SceneComponent.K2_GetComponentRotation",0);
    if(!g_fnSetActorLR) g_fnSetActorLR=find_by_path("/Script/Engine.Actor.K2_SetActorLocationAndRotation",0);
    if(!g_fnCamLoc)     g_fnCamLoc    =find_by_path("/Script/Engine.PlayerCameraManager.GetCameraLocation",0);
    refresh_numelements();
    uintptr_t cm=g_worldCamMgr; if(!cm||!obj_alive(cm)) cm=find_live_class_sub("CameraManager");
    uintptr_t pawn=cm?pawn_of_cam_mgr(cm):0;
    g_worldCamMgr=cm; g_worldPawnHint=pawn;
    if(pawn){ g_wire_req=1; LOGI("[WORLD] found Tribe's pawn 0x%lx (camera manager 0x%lx): wiring it on the game thread",(unsigned long)pawn,(unsigned long)cm); }
    else { static int said=0; if((said++%15)==0) LOGI("[WORLD] waiting for Tribe's pawn (camera manager 0x%lx)",(unsigned long)cm); } }
// ---- the character: active_skin.txt says what to show; a mod file is loaded once Tribe's avatar body is there (or 30 s
// after the world is up without it), a failed load is tried 3 more times 10 s apart, our avatar actor is spawned 2 s
// later and again (5 tries, 5 s apart) if it is missing; "tribe" = Tribe's own avatar, nothing of ours loads
static int g_avTries=0, g_avReqSeq=-1, g_avSeenSeq=0, g_avSpawnTries=0; static double g_avNextAt=0, g_avSpawnAt=0;
static bool g_avGaveUp=false; static char g_avWhy[120]="waiting for the world", g_avSkin[128]="";
static void avatar_poll(){
    if(!g_resolved||!g_mod_on) return;
    static int tk=0; tk++;
    double now=mono_now();
    char sk[128]=""; bool haveSk=read_trim_file("active_skin.txt",sk,sizeof sk); bool tribe=haveSk&&!strcmp(sk,"tribe");
    snprintf(g_avSkin,sizeof g_avSkin,"%s",haveSk?sk:"(none)");
    if(!g_smMode&&(tk%4)==1){ static int misses=0; refresh_numelements();   // which avatar menu (step B); "2304" only once the
        if(find_by_path("/Script/TribeXR.TribeReadyPlayerMeAvatarSkin",1)) g_smMode=1;   // world is up and the class is still missing
        else if(g_worldUp&&++misses>=3) g_smMode=2;
        if(g_smMode) LOGI("[MENU] avatar menu kind: %s",g_smMode==1?"2311 (C++: TribeProfileMenuWidget, TribeSkinItemWidget, TribeReadyPlayerMeAvatarSkin)":"2304 (Blueprints)"); }
    g_smTribeMode=tribe?1:0;                                             // Tribe's own avatar picked last (the menu writes it)
    if(g_loadSeq!=g_avSeenSeq){ g_avSeenSeq=g_loadSeq;                   // a load finished (ours or a pick's)
        bool mine=g_avReqSeq>=0; g_avReqSeq=-1;
        if(g_loadOk==1){ g_avTries=0; g_avGaveUp=false; g_avSpawnTries=0; g_avSpawnAt=now+2.0; snprintf(g_avWhy,sizeof g_avWhy,"loaded %s",g_skinLoaded);
            LOGI("[AVATAR] %s loaded (%.1f s after the library loaded)",g_skinLoaded,now-g_t0); }
        else if(mine){ if(g_avTries>=4){ g_avGaveUp=true; snprintf(g_avWhy,sizeof g_avWhy,"gave up: %s",g_loadWhy); LOGI("[AVATAR] gave up after %d tries: %s",g_avTries,g_loadWhy); }
            else { g_avNextAt=now+10.0; snprintf(g_avWhy,sizeof g_avWhy,"retry in 10 s: %s",g_loadWhy); LOGI("[AVATAR] the load failed (%s): trying again in 10 s",g_loadWhy); } } }
    if(tribe){ snprintf(g_avWhy,sizeof g_avWhy,"%s","Tribe's own avatar"); return; }
    if(!file_present("auto_load")){ snprintf(g_avWhy,sizeof g_avWhy,"%s","off (no auto_load)"); return; }
    if(!g_worldUp){ if(!g_loaded_once) snprintf(g_avWhy,sizeof g_avWhy,"%s","waiting for the world"); return; }
    if(g_avReqSeq>=0) return;                                            // a load is on its way
    if(!g_loaded_once&&!g_avGaveUp&&g_avTries<4&&now>=g_avNextAt&&!g_load_req&&(tk%4)==0){
        refresh_numelements(); uintptr_t body=find_live("AvatarBodyMesh","SkeletalMeshComponent","ReadyPlayerMeComponent");
        bool late=g_worldUpAt>0&&now-g_worldUpAt>=30.0;
        if(body||late){ g_avTries++; g_avReqSeq=g_loadSeq; g_load_req=1; snprintf(g_avWhy,sizeof g_avWhy,"loading %s (try %d)",sk,g_avTries);
            LOGI("[AVATAR] loading %s (try %d)%s",haveSk?sk:"(glb_path.txt / custom.glb)",g_avTries,body?"":": Tribe's avatar body never appeared, 30 s after the world"); }
        else snprintf(g_avWhy,sizeof g_avWhy,"%s","waiting for Tribe's avatar body (30 s at most)"); }
    if(g_loaded_once&&g_mymesh&&file_present("auto_actor")){
        bool alive=g_isoActor&&obj_alive(g_isoActor);
        if(alive){ g_avSpawnTries=0; return; }
        if(!g_iso_req&&now>=g_avSpawnAt&&g_avSpawnTries<5){ g_avSpawnTries++; g_avSpawnAt=now+5.0; g_iso_req=1;
            LOGI("[AVATAR] spawning our avatar actor (try %d)",g_avSpawnTries); }
        else if(g_avSpawnTries>=5){ snprintf(g_avWhy,sizeof g_avWhy,"%s","our avatar actor could not be spawned (5 tries)"); } } }
// ---- [READY]
static void ready_write_file(const char* name,const char* text,bool append){
    char p[600], t[640]; snprintf(p,sizeof p,"%s/%s",OUTDIR,name);
    if(append){ FILE* f=fopen(p,"a"); if(f){ fputs(text,f); fclose(f); chmod(p,0666); } return; }
    snprintf(t,sizeof t,"%s.tmp",p); FILE* f=fopen(t,"w"); if(!f) return; fputs(text,f); fclose(f); chmod(t,0666); rename(t,p); }
static void ready_history(const char* what){        // one line per event, the file capped at 200 lines (the last 150 kept)
    char p[600]; snprintf(p,sizeof p,"%s/ready_history.txt",OUTDIR);
    struct stat st; if(stat(p,&st)==0&&st.st_size>16*1024){ FILE* f=fopen(p,"r");
        if(f){ static char buf[64*1024]; size_t n=fread(buf,1,sizeof buf-1,f); fclose(f); buf[n]=0; int lines=0; for(size_t i=0;i<n;i++) if(buf[i]=='\n') lines++;
            if(lines>200){ int skip=lines-150; size_t i=0; for(;i<n&&skip>0;i++) if(buf[i]=='\n') skip--; ready_write_file("ready_history.txt",buf+i,false); } } }
    time_t now=time(0); struct tm tmv; localtime_r(&now,&tmv); char ts[32]; strftime(ts,sizeof ts,"%Y-%m-%d %H:%M:%S",&tmv);
    char line[700]; snprintf(line,sizeof line,"%s pid=%d step=%s %s\n",ts,(int)getpid(),MOD2311_STEP,what); ready_write_file("ready_history.txt",line,true); }
static void ready_poll(){
    static double nextAt=0; static bool wroteStart=false, done=false, failed=false; static int lastAll=-1;
    double now=mono_now(), t=now-g_t0;
    if(!wroteStart&&tribemod_state()>=0){ wroteStart=true; ready_history("start"); }
    char miss[400]=""; int nm=0; bool all=true;
    auto need=[&](bool ok,const char* part,const char* why){ if(ok) return; all=false;
        if(nm<6){ int k=(int)strlen(miss); snprintf(miss+k,sizeof miss-k,"%s%s(%s)",nm?",":"",part,why); } nm++; };
    // hook
    char hook[140]; bool hookOk=g_hookState==1&&g_mod_on&&g_gtSelf;
    if(hookOk) snprintf(hook,sizeof hook,"1");
    else if(g_hookState==1||g_hookState==2) snprintf(hook,sizeof hook,"%s",g_mod_on?"1(no game thread yet)":"wait(tribemod not readable yet)");
    else if(g_hookState==3) snprintf(hook,sizeof hook,"off(executor_on absent)");
    else snprintf(hook,sizeof hook,"0(%s)",g_hookWhy);
    need(hookOk,"hook",hook);
    need(g_worldUp,"world",g_resolved?"no pawn yet":"objects not resolved");
    // character
    char sk[128]=""; bool haveSk=read_trim_file("active_skin.txt",sk,sizeof sk); bool tribe=haveSk&&!strcmp(sk,"tribe");
    bool wantAv=!tribe&&file_present("auto_load"), wantActor=file_present("auto_actor");
    bool avOk=g_loaded_once&&(!wantActor||(g_isoActor&&obj_alive(g_isoActor)));
    char av[160]; if(tribe) snprintf(av,sizeof av,"tribe"); else if(!wantAv) snprintf(av,sizeof av,"off"); else if(avOk) snprintf(av,sizeof av,"1");
    else snprintf(av,sizeof av,"0(%s)",g_avWhy);
    if(wantAv) need(avOk,"avatar",g_avWhy);
    const char* skin=tribe?"tribe":(g_skinLoaded[0]?g_skinLoaded:(haveSk?sk:"-"));
    // stage
    char stg[160]; bool wantStage=g_stgWantIdx>=0, stgOk=wantStage&&g_emState==EM_ACTIVE&&g_emActive==g_stgWantIdx;
    if(!g_stgWant[0]) snprintf(stg,sizeof stg,"none");
    else if(!strncmp(g_stgWant,"stock:",6)) snprintf(stg,sizeof stg,"%s",g_stgWant);
    else if(!wantStage) snprintf(stg,sizeof stg,"\"%s\"(not in envs.txt)",g_stgWant);
    else if(stgOk) snprintf(stg,sizeof stg,"\"%s\"",g_stgWant);
    else if(g_stgGaveUp) snprintf(stg,sizeof stg,"gave-up(\"%s\" failed %d times)",g_stgWant,g_stgTries);
    else if(g_emTribeSwitched) snprintf(stg,sizeof stg,"off(Tribe switched environment)");
    else if(g_emState!=EM_IDLE) snprintf(stg,sizeof stg,"loading(\"%s\" step %d, try %d)",g_stgWant,(int)g_emState,g_stgTries);
    else if(!g_envMenuOn) snprintf(stg,sizeof stg,"waiting(lookups)");
    else if(!g_emGameState) snprintf(stg,sizeof stg,"waiting(game state)");
    else snprintf(stg,sizeof stg,"waiting(settle %d/4, try %d)",g_stgSettle,g_stgTries);
    if(g_stgWant[0]&&strncmp(g_stgWant,"stock:",6)) need(stgOk,"stage",stg);
    // stream: Tribe's size pair = stream.txt's size
    char strm[80]="off"; int ix=g_stIdx;
    if(ix>=0&&g_stCfg[ix].has[ST_W]){ int w=0,h=0; if(g_base){ w=(int)rd32(g_base+ST_DIMS_VADDR); h=(int)rd32(g_base+ST_DIMS_VADDR+4); }
        bool ok=w==g_stCfg[ix].v[ST_W]&&h==g_stCfg[ix].v[ST_H];
        if(ok) snprintf(strm,sizeof strm,"%dx%d",w,h); else snprintf(strm,sizeof strm,"pending(%dx%d, want %dx%d%s)",w,h,g_stCfg[ix].v[ST_W],g_stCfg[ix].v[ST_H],g_stMgr?"":", no manager");
        need(ok,"stream",strm); }
    // menus: the stage boxes, once Tribe's environment list exists (it may need Visuals > Environments opened once)
    char menus[128]; bool envOn=file_present("env_menu");
    if(!envOn) snprintf(menus,sizeof menus,"env:off");
    else if(!g_emListLive) snprintf(menus,sizeof menus,"env:list-not-open");
    else { snprintf(menus,sizeof menus,"env%d/%d",(int)g_emAdded,(int)g_emCount); need(g_emAdded>=g_emCount,"menus",menus); }
    { int k2=(int)strlen(menus); bool smOn=file_present("skin_menu");      // the avatar boxes (step B), once the list exists
      if(!smOn||g_smBoxesOff) snprintf(menus+k2,sizeof menus-k2,",avatar:off");
      else if(g_smMode!=1||!g_smListLive) snprintf(menus+k2,sizeof menus-k2,",avatar:list-not-open");
      else { snprintf(menus+k2,sizeof menus-k2,",avatar%d/%d",(int)g_smAdded,(int)g_smCount); need(g_smAdded>=g_smCount,"menus",menus); } }
    char line[1200]; char paks[24]="?"; if(g_emPaksOk>=0) snprintf(paks,sizeof paks,"%d/%d",(int)g_emPaksOk,(int)g_emPaksN);
    int k=snprintf(line,sizeof line,"[READY] %s step=%s pid=%d t=%.1fs hook=%s world=%d avatar=%s skin=%s stage=%s stream=%s menus=%s paks=%s gen=%d skips=%ld",
        all?"all=1":(t>=180.0?"FAIL":"all=0"),MOD2311_STEP,(int)getpid(),t,hook,(int)g_worldUp,av,skin,stg,strm,menus,paks,(int)g_worldGen,g_callSkips);
    if(!all&&k>0&&k<(int)sizeof line) snprintf(line+k,sizeof line-k," missing=%s",miss);
    bool changed=(int)all!=lastAll; lastAll=all;
    if(changed||now>=nextAt){ LOGI("%s",line); char l2[1210]; snprintf(l2,sizeof l2,"%s\n",line); ready_write_file("ready.txt",l2,false);
        nextAt=now+((all||t>=180.0)?60.0:2.0); }
    if(all&&!done){ done=true; char h[600]; snprintf(h,sizeof h,"READY t=%.1f skin=%s stage=%s",t,skin,stg); ready_history(h); load_status("%s",line); }
    if(!all&&!done&&!failed&&t>=180.0){ failed=true; char h[700]; snprintf(h,sizeof h,"FAIL t=%.1f missing=%s",t,miss); ready_history(h); load_status("%s",line); } }
static void* dump_thread(void*){
    LOGI("dumper thread up; base=0x%lx; poll %s/dump_now",(unsigned long)g_base,OUTDIR);
    char cmd[600]; snprintf(cmd,sizeof cmd,"%s/dump_now",OUTDIR);
    char lcmd[600]; snprintf(lcmd,sizeof lcmd,"%s/load_avatar",OUTDIR);
    for(;;){ modon_poll();                                        // mod2311: the supervisor (see above)
        { static int rk=0; if(!g_resolved&&g_mod_on&&(rk++%4)==0) run_guarded(ensure_resolved,"resolve"); }   // guarded: the scan can hit a SIGBUS page (C2)   // the object array, every 2 s until found
        world_poll(); avatar_poll(); ready_poll();
        g_log_pe = file_present("log_pe")?1:0;                   // toggle the ProcessEvent diagnostic
        g_logDeck = file_present("log_deck")?1:0;                // the deck capture (intro.cpp)
        int fd=open(cmd,O_RDONLY); if(fd>=0){ close(fd); unlink(cmd); LOGI("dump_now seen; dumping...");
        install_guard(); do_dump(); remove_guard(); }
        // .usmap dump (hook/usmap.cpp): tribemod/usmap_now (one-shot) -> tribemod/TribeXR.usmap + usmap_log.txt, once the
        // decks are loaded (usmap_ready, ~2 s checks), so the file can be created before launch
        { static int umk=0; if((++umk % 4)==1 && file_present("usmap_now") && usmap_ready()){
            char up[600]; snprintf(up,sizeof up,"%s/usmap_now",OUTDIR); unlink(up); LOGI("usmap_now: dumping...");
            install_guard(); usmap_dump(); remove_guard(); } }
        // native dump (hook/native.cpp): tribemod/native_now (one-shot; its text may list packages) -> native_dump.jsonl,
        // once the engine objects are resolved (native classes are loaded at startup)
        { static int ndk=0; if((++ndk % 4)==3 && file_present("native_now")){ run_guarded(ensure_resolved,"resolve");
            if(g_resolved){ LOGI("native_now: dumping..."); install_guard(); native_dump(); remove_guard(); } } }
        // manual load_avatar trigger: resolve globals here (heavy scan, off the game thread), then arm the PE-drain.
        int lf=open(lcmd,O_RDONLY); if(lf>=0){ close(lf); unlink(lcmd); LOGI("load_avatar seen; arming executor...");
            run_guarded(ensure_resolved,"resolve"); if(g_resolved && orig_pe && g_mod_on){ g_load_req=1; load_status("armed; waiting for next ProcessEvent on game thread"); }
            else load_status("NOT armed (resolved=%d pe=%p)",(int)g_resolved,g_pe_addr); }
        // (the auto-load and the avatar actor's spawn are avatar_poll's now, with retries; mod2311)
        // ISO trigger: tribemod/iso_here (one-shot) -> spawn our own actor in front of the HMD on the game thread.
        { char ip[600]; snprintf(ip,sizeof ip,"%s/iso_here",OUTDIR); int fi=open(ip,O_RDONLY);
          if(fi>=0){ close(fi); unlink(ip); if(g_mymesh){ g_iso_req=1; load_status("iso_here seen -> spawning our actor"); } else load_status("iso_here: no mesh loaded yet"); } }
        // ROUTE A body tracking (flag tribemod/body_tracking): ~3 s after the world is up, resolve HERE (heavy scans stay off
        // the game thread), then start + poll on the game thread: +1 s, +3 s, +10 s, then every 30 s (24 polls max).
        { static int bt=-1, pt=0;
          if(bt==-1 && orig_pe && g_loaded_once && file_present("body_tracking")) bt=6;
          if(bt>0 && --bt==0){ if(bt_resolve()){ a2_resolve(); g_bt_req=1; load_status("BT: armed; starting on the game thread"); } else load_status("BT: resolve failed; not started"); }
          { char rp[600]; snprintf(rp,sizeof rp,"%s/bt_recalibrate",OUTDIR); int fr=open(rp,O_RDONLY);     // one-shot: redo the T-pose
            if(fr>=0){ close(fr); unlink(rp); if(g_ucPath[0]) unlink(g_ucPath); g_a2Recal=1; load_status("A2: bt_recalibrate seen -> your calibration deleted; stand still with straight arms once"); } }
          if(file_present("bt_calibrate_now")){ char cp[600]; snprintf(cp,sizeof cp,"%s/bt_calibrate_now",OUTDIR); unlink(cp); g_a2CalNow=1; }  // manual capture
          if(file_present("next_skin")){ char np2[600]; snprintf(np2,sizeof np2,"%s/next_skin",OUTDIR); unlink(np2);            // remote skin switch
            if(g_loaded_once&&orig_pe){ advance_skin(); g_load_req=1; } else load_status("next_skin: no skin loaded yet"); }
          if(g_bt_started && g_btPolls<24){ pt++; if(pt==2||pt==6||pt==20||(pt>=60&&pt%60==0)) g_bt_poll_req=1; }
          if(g_a2Live) a2_find_tribe_hands(); }                       // Tribe's tracked-hand meshes: cheap check, scans only when stale
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
        { static int hdk=0; if((++hdk % 2)==1) head_poll(); }              // detachable head: functions, selfie camera, head.txt (~1 s)
        { static int cvk=0; if((++cvk % 2)==0) camview_poll(); }           // a stage's camera button: its file, Tribe's visuals menu (~1 s)
        { static int stk=0; if((++stk % 2)==1){ stream_poll(); g_stOnPoll=1; stream_tick(1.0f); g_stOnPoll=0; } }            // the stream encoder: stream.txt, Tribe's video-call manager (~1 s)
        freeze_poll();                                                     // the freeze recorder: starts once, after the game thread's first tick
        // Skin-menu trace switch (checked here, not per ProcessEvent call)
        { int st=file_present("skin_trace")?1:0; if(st!=g_skinTrace){ g_skinTrace=st; LOGI("[SKIN] trace %s",st?"ON":"OFF"); } }
        // Extra avatar-menu boxes: resolve + track the live AvatarList (~2 s); the game-thread tick adds the boxes.
        { static int smk=0; if((++smk % 4)==0) skin_menu_poll(); }
        { static int emk=0; if((++emk % 4)==2) env_menu_poll(); }           // offset from the avatar poll: spreads the object scans
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

// ---- the ProcessEvent hook, installed once, in the library constructor (mod2311; claudedocs/mod_2311_load.md 3.1) ----
// libhook is a DT_NEEDED of libUnreal, so this runs while libUnreal is being loaded, before its own initializers and
// before any thread of ours or Tribe's exists: nothing can be running ProcessEvent while it is patched. Never patched
// again later (combo_peretry's retry thread re-patched it under a running game thread). The checks read the code
// directly once maps_rx has found it r-x, not through the shared range table (whose rebuild raced this read on 14:26).
// tribemod/ state: 1 readable with executor_on, 0 readable without it (safe mode: no hook), -1 not readable yet (the
// first launch after an install: hooked anyway, in pass-through until the poll thread can read executor_on).
static int tribemod_state(){
    char ef[600]; snprintf(ef,sizeof ef,"%s/executor_on",OUTDIR); int e=open(ef,O_RDONLY);
    if(e>=0){ close(e); return 1; }
    int err=errno; DIR* d=opendir(OUTDIR); int n=0;
    if(d){ struct dirent* x; while((x=readdir(d))) if(x->d_name[0]!='.'){ n++; break; } closedir(d); }
    return (err==ENOENT&&d&&n>0)?0:-1; }
static bool pe_patch_ok(uintptr_t pe){               // And64InlineHook's three forms, each pointing at repl_pe
    const volatile uint32_t* w=(const volatile uint32_t*)pe; uintptr_t rp=(uintptr_t)repl_pe; uint64_t tgt=0;
    if(w[0]==0xD503201Fu&&w[1]==0x58000051u&&w[2]==0xD61F0220u){ memcpy(&tgt,(const void*)(pe+12),8); return tgt==rp; }   // NOP; LDR X17,#8; BR X17
    if(w[0]==0x58000051u&&w[1]==0xD61F0220u){ memcpy(&tgt,(const void*)(pe+8),8); return tgt==rp; }                      // LDR X17,#8; BR X17
    if((w[0]&0xFC000000u)==0x14000000u){ int64_t off=(int64_t)(w[0]&0x03FFFFFFu); if(off&0x02000000) off-=0x04000000; return pe+(uintptr_t)(off*4)==rp; }   // B
    return false; }
static void pe_hook_ctor(int ts){
    uintptr_t pe=g_base+RVA_PE_GHIDRA+PE_SKEW;
    if(ts==0){ g_hookState=3; snprintf(g_hookWhy,sizeof g_hookWhy,"%s","executor_on absent");
        LOGI("[HOOK] tribemod/executor_on is absent: safe mode, ProcessEvent left alone"); return; }
    bool written=false;                               // once ProcessEvent jumps to repl_pe, orig_pe must stay valid
    for(int k=1;k<=5;k++){
        if(!maps_rx(pe,20)){ snprintf(g_hookWhy,sizeof g_hookWhy,"ProcessEvent's code @%p is not mapped r-x",(void*)pe); usleep(20*1000); continue; }
        uint32_t w0=*(const volatile uint32_t*)pe;
        if(w0!=0xA9BA7BFDu){ snprintf(g_hookWhy,sizeof g_hookWhy,"first word 0x%08x @%p is not ProcessEvent's stp x29,x30,[sp,#-0x60]!",w0,(void*)pe); break; }
        g_pe_addr=(void*)pe; A64HookFunction(g_pe_addr,(void*)repl_pe,(void**)&orig_pe);
        written=*(const volatile uint32_t*)pe!=0xA9BA7BFDu;   // (And64InlineHook leaves orig_pe NULL only when it wrote nothing)
        if(orig_pe&&pe_patch_ok(pe)){ g_hookState=(ts==1)?1:2; snprintf(g_hookWhy,sizeof g_hookWhy,"%s",ts==1?"ok":"tribemod not readable yet");
            const volatile uint32_t* w=(const volatile uint32_t*)pe;
            LOGI("[HOOK] ProcessEvent hooked @%p verified (try %d; words %08x %08x %08x; trampoline %p)%s",(void*)pe,k,w[0],w[1],w[2],(void*)orig_pe,
                 ts==1?"":": pass-through until tribemod/ can be read");
            return; }
        const volatile uint32_t* w=(const volatile uint32_t*)pe;
        snprintf(g_hookWhy,sizeof g_hookWhy,"the patch did not verify (words %08x %08x %08x, trampoline %p)",w[0],w[1],w[2],(void*)orig_pe);
        if(written) break;                                              // something was written: never patch a second time
        orig_pe=0; usleep(20*1000); }
    g_hookState=-1; if(!written) orig_pe=0;                             // written: repl_pe passes every call straight through
    LOGI("[HOOK] FAILED: %s%s; the mod stays off this launch",g_hookWhy,written?" (patched: every call passes straight through)":""); }

__attribute__((constructor))
static void on_load(){
    g_t0=mono_now();
    LOGI("dumper libhook constructor (mod2311 step %s)",MOD2311_STEP);
    // ensure outdir exists (app-writable external files dir), then upsert the ini BEFORE PreInit (skipped while unreadable)
    mkdir(OUTDIR,0777);
    int ts=tribemod_state();
    ini_upsert();
    for(int i=0;i<100 && !g_base;i++){ g_base=find_lib_base("libUnreal.so"); if(!g_base) usleep(50*1000); }
    if(!g_base){ g_hookState=-1; snprintf(g_hookWhy,sizeof g_hookWhy,"%s","libUnreal.so not found"); LOGI("FAILED to find libUnreal.so base"); return; }
    pe_hook_ctor(ts);                    // first, while no thread can be inside ProcessEvent
    if(g_hookState==1||g_hookState==2) st_hook_send();   // Tribe's two encoder re-sends (stream.cpp), same moment, same checks
    g_mod_on=(g_hookState==1)?1:0;
    pthread_attr_t a; pthread_attr_init(&a); pthread_attr_setstacksize(&a,8*1024*1024); pthread_attr_setdetachstate(&a,PTHREAD_CREATE_DETACHED);
    pthread_t th; pthread_create(&th,&a,dump_thread,nullptr); pthread_attr_destroy(&a);
    LOGI("dumper thread spawned (base=0x%lx)",(unsigned long)g_base);
    // Phase 1: in-libhook loopback HTTP server (127.0.0.1:8787), detached.
    pthread_attr_t sa; pthread_attr_init(&sa); pthread_attr_setstacksize(&sa,256*1024); pthread_attr_setdetachstate(&sa,PTHREAD_CREATE_DETACHED);
    pthread_t sh; pthread_create(&sh,&sa,httpd_thread,nullptr); pthread_attr_destroy(&sa);
    LOGI("httpd thread spawned (127.0.0.1:%d)",HTTP_PORT);
}
