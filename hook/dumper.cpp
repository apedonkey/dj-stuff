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
#include <cstdarg>

#define TAG "TRIBEMOD"
#define LOGI(...) __android_log_print(ANDROID_LOG_INFO, TAG, __VA_ARGS__)

// ---- resolved statics (this session) ----
static const uintptr_t RVA_NamePool      = 0x07C622C0; // FNamePool (.bss)
static const uintptr_t RVA_GUObjectArray = 0x07D0EAB8; // FUObjectArray (.bss)
static const uintptr_t RVA_GUObj_GOTslot = 0x07AB59E8; // RELR slot holding &GUObjectArray (cross-check)

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
static bool in_range(uintptr_t p, size_t n){ for(int i=0;i<g_nranges;i++) if(p>=g_ranges[i].lo && p+n<=g_ranges[i].hi) return true; return false; }

static sigjmp_buf g_jmp; static volatile sig_atomic_t g_guard=0; static struct sigaction g_old_segv, g_old_bus;
static void segv_handler(int sig,siginfo_t* si,void* uc){ if(g_guard) siglongjmp(g_jmp,1);
    if(sig==SIGSEGV && g_old_segv.sa_sigaction) g_old_segv.sa_sigaction(sig,si,uc);
    else if(sig==SIGBUS && g_old_bus.sa_sigaction) g_old_bus.sa_sigaction(sig,si,uc); }
static void install_guard(){ struct sigaction sa; memset(&sa,0,sizeof sa); sa.sa_sigaction=segv_handler; sa.sa_flags=SA_SIGINFO;
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
static const uint32_t OBJOBJECTS=0x10, ITEM_STRIDE=0x18; // FUObjectItem stride
static uintptr_t obj_at(uint32_t idx){
    if(idx>=g_numElements) return 0; uintptr_t chunk=rdptr(g_chunks + (uintptr_t)(idx>>16)*8); if(!chunk) return 0;
    uintptr_t item=chunk + (uintptr_t)(idx&0xFFFF)*ITEM_STRIDE; return rdptr(item /*+0 Object*/);
}
static uint32_t item_flags(uint32_t idx){ uintptr_t chunk=rdptr(g_chunks+(uintptr_t)(idx>>16)*8); if(!chunk) return 0;
    return rd32(chunk+(uintptr_t)(idx&0xFFFF)*ITEM_STRIDE + 8); }

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
static uint32_t FF_Class=0x08, FF_Next=0x20, FF_Name=0x28;      // FField
static uint32_t FP_ElemSize=0x3C, FP_Offset=0x4C;               // FProperty
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

    // R1: NamePool — params override + wide auto-scan + layout diagnostic
    uintptr_t npRva = P_np? P_np : RVA_NamePool; g_namepool=g_base+npRva; char t[64]; bool r1=false;
    FILE* nd=fopen(op("namepool_diag.txt"),"w");
    if(nd){ fprintf(nd,"namepool @0x%lx (rva 0x%lx); *(pool)=0x%lx\n",(unsigned long)g_namepool,(unsigned long)npRva,(unsigned long)rdptr(g_namepool));
        hexdump_to(nd,"pool[0..0x300]",g_namepool,0x300);
        // for each aligned slot in pool[0..0x120], if it looks like a heap ptr, dump the target buffer
        for(uint32_t off=0x00; off<=0x120; off+=8){ uintptr_t bp=rdptr(g_namepool+off);
            if(bp>=0x1000 && in_range(bp,0x10)){ char lbl[48]; snprintf(lbl,sizeof lbl,"  [pool+0x%02x]->",off);
                fprintf(nd,"%s 0x%lx\n",lbl,(unsigned long)bp); hexdump_to(nd,"     target",bp,0x60); } }
        // also chase the shards global (DAT_07d72300 -> real 0x07C72300) head, in case entries live there
        uintptr_t shards=g_base+0x07C72300; fprintf(nd,"\nshards @0x%lx:\n",(unsigned long)shards); hexdump_to(nd,"shards[0..0x80]",shards,0x80);
        // absolute probe via params (abs=hex,len)
        fclose(nd); }
    if(P_probe){ /* abs handled in P_probe path below when np-style; add absolute */ }
    if(P_bo>=0){ g_blocks_off=(uint32_t)P_bo; int len=fname_resolve(0,t,sizeof t); r1=(len==4&&strcmp(t,"None")==0); }
    else { for(uint32_t off=0x08; off<=0x80; off+=8){ g_blocks_off=off; int len=fname_resolve(0,t,sizeof t); if(len==4&&strcmp(t,"None")==0){r1=true;break;} } }
    ck("R1.NamePool.Resolve(0)==None",r1,"blocks_off=0x%x resolved='%s' (see namepool_diag.txt)",g_blocks_off,t);
    if(!r1){ ck("ABORT",false,"R1 failed"); if(g_sc)fclose(g_sc); return; }

    // R2: GUObjectArray direct + GOT cross-check
    g_objarray=g_base+(P_ga?P_ga:RVA_GUObjectArray); uintptr_t viaGot=rdptr(g_base+RVA_GUObj_GOTslot);
    ck("R2.GOT_crosscheck",viaGot==g_objarray,"direct=0x%lx got=0x%lx",(unsigned long)g_objarray,(unsigned long)viaGot);
    uintptr_t objobj=g_objarray+OBJOBJECTS; g_chunks=rdptr(objobj+0x00);
    g_numElements=rd32(objobj+0x18); g_numChunks=rd32(objobj+0x1C); uint32_t maxEl=rd32(objobj+0x10);
    bool p2a=(g_numElements>=10000&&g_numElements<=5000000)&&(g_numChunks==((g_numElements+65535)/65536));
    ck("R2a.counts",p2a,"NumElements=%u NumChunks=%u MaxElements=%u",g_numElements,g_numChunks,maxEl);
    uintptr_t o0=obj_at(0),o1=obj_at(1); uint32_t i0=rd32(o0+OFF_Index),i1=rd32(o1+OFF_Index);
    ck("R2b.index0/1",i0==0&&i1==1,"obj0=0x%lx idx=%u obj1 idx=%u",(unsigned long)o0,i0,i1);
    char c0[128]; obj_name(o0,c0,sizeof c0); ck("R2c.obj0.name_printable",c0[0]!=0&&c0[0]!='?',"obj0.name='%s'",c0);
    if(!p2a){ ck("ABORT",false,"R2 counts bad"); if(g_sc)fclose(g_sc); return; }

    // R3: lock UStruct offsets on Object/Class/Actor invariants (slide Super/PropSize)
    uintptr_t cObject=find_struct("Object"), cClass=find_struct("Class"), cActor=find_struct("Actor");
    bool r3=false; uint32_t sc[3]={0x30,0x38,0x40};
    for(int k=0;k<3;k++){ uint32_t so=sc[k], po=so+0x18;
        uint32_t objSuper=(uint32_t)rdptr(cObject+so); uint32_t objPS=rd32(cObject+po);
        if(rdptr(cObject+so)==0 && objPS==0x28 && rdptr(cClass+OFF_Class)==cClass){ OFF_Super=so; OFF_PropSize=po; OFF_ChildProps=so+0x10; OFF_Children=so+0x08; r3=true; (void)objSuper; break; } }
    ck("R3.UStruct.offsets",r3,"Super=0x%x PropSize=0x%x ChildProps=0x%x (Object.Super==0 && PS==0x28 && Class.Class==self)",OFF_Super,OFF_PropSize,OFF_ChildProps);
    { char sn[128]; uintptr_t as=rdptr(cActor+OFF_Super); obj_name(as,sn,sizeof sn); uint32_t aps=rd32(cActor+OFF_PropSize);
      ck("R3d.Actor",strcmp(sn,"Object")==0&&aps>0x28,"Actor.Super='%s' PropSize=0x%x",sn,aps); }

    // R4: FField/FProperty sanity on Actor's ChildProperties
    { int cnt=0; bool okChain=true; uint32_t aps=rd32(cActor+OFF_PropSize); char tbl[1024]; int tl=0;
      for(uintptr_t f=rdptr(cActor+OFF_ChildProps); f && cnt<12; f=rdptr(f+FF_Next),cnt++){
        char ty[64],nm[128]; ffield_type(f,ty,sizeof ty); uint32_t id=rd32(f+FF_Name); fname_resolve(id,nm,sizeof nm);
        uint32_t off=rd32(f+FP_Offset); if(off>=aps+0x1000) okChain=false;
        tl+=snprintf(tbl+tl,sizeof(tbl)-tl,"  +0x%03x %s %s\n",off,ty,nm); }
      ck("R4.FField.chain",cnt>0&&okChain,"props=%d\n%s",cnt,tbl); }

    // ---- objects.txt (full walk) ----
    FILE* fo=fopen(op("objects.txt"),"w");
    if(fo){ char cn[128],nm[128],fp[512];
      for(uint32_t i=0;i<g_numElements;i++){ uintptr_t o=obj_at(i); if(!o) continue; uint32_t fl=item_flags(i);
        class_name(o,cn,sizeof cn); full_path(o,fp,sizeof fp);
        fprintf(fo,"%08u 0x%016lx flags=%08x %-42s %s\n",i,(unsigned long)o,fl,cn,fp); }
      fclose(fo); }

    // ---- values.txt (the decision) ----
    FILE* fv=fopen(op("values.txt"),"w");
    if(fv){
      // residency of key classes
      const char* keys[]={"BP_ReadyPlayerMeAvatarSkin_C","BP_OculusAvatarSkin_C","W_RPMAvatarCreator_C","BP_TribeSkinBase_C"};
      for(auto k:keys){ uintptr_t c=find_struct(k); fprintf(fv,"resident %-32s : %s (0x%lx)\n",k,c?"YES":"no",(unsigned long)c); }
      // TribePawnBP_C: CDO vs live ActiveSkinClasses + AvatarID
      uintptr_t pawnCls=find_struct("TribePawnBP_C");
      int offASC = pawnCls? prop_offset(pawnCls,"ActiveSkinClasses",0):-1;
      int offAID = pawnCls? prop_offset(pawnCls,"AvatarID",0):-1;
      fprintf(fv,"\nTribePawnBP_C class=0x%lx ActiveSkinClasses@0x%x AvatarID@0x%x\n",(unsigned long)pawnCls,offASC,offAID);
      for(uint32_t i=0;i<g_numElements;i++){ uintptr_t o=obj_at(i); if(!o) continue; char cn[128]; class_name(o,cn,sizeof cn);
        if(strcmp(cn,"TribePawnBP_C")!=0) continue; uint32_t fl=item_flags(i); bool cdo=fl&RF_ClassDefaultObject;
        fprintf(fv,"  pawn 0x%lx CDO=%s",(unsigned long)o,cdo?"YES":"no");
        if(offAID>=0){ char s[256]; read_fstring(o+offAID,s,sizeof s); fprintf(fv," AvatarID='%s'",s); }
        if(offASC>=0){ uintptr_t arr=o+offASC; uintptr_t data=rdptr(arr); int num=(int)rd32(arr+8); fprintf(fv," ActiveSkinClasses[%d]={",num);
          for(int e=0;e<num&&e<8;e++){ uintptr_t cls=rdptr(data+(uintptr_t)e*8); char kn[128]; obj_name(cls,kn,sizeof kn); fprintf(fv,"%s%s",e?",":"",kn); } fprintf(fv,"}"); }
        fprintf(fv,"\n"); }
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
