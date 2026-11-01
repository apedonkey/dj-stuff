#include <sys/mman.h>
// stream.cpp: Tribe's stream encoder settings (the Halloween session, 2026-10-27). dumper.cpp includes it after camview.cpp
// and calls stream_poll (poll thread, ~1 s) and stream_tick (game thread, after camview_tick). Inert unless
// tribemod/stream.txt exists. Logs [STREAM].
//
// The user (2026-10-27): the Twitch stream "dosent look crisp like it does in the headset ... the lazers ... it looks like its
// at a very low frame rate". Measured on the headset: Tribe streams through Agora (SDK 4.5.2) at 848x480, 15 fps and Agora's
// standard bitrate (~0.78 Mbit/s), and after 1-5 minutes Agora dropped the hardware encoder (QC2 c2.qti.avc.encoder released)
// for its software one; the stream then ran at 7-12 fps (agoraapi.log max_framerate_fps) until the end.
// How Tribe sets it up (decompile + files/agoraapi.log): TribeVideoCallManager::StartCallWithParameters calls
// IRtcEngine::setVideoEncoderConfiguration (vtable +0xf0 on the engine at manager+0x550; width/height from libUnreal .bss
// vaddr 0x7F02DC4 = 848, 480; frameRate 15 and bitrate 0 from .rodata) for the DEFAULT connection, then joins with
// joinChannelEx({channelId, localUid}); at the join Agora copies the default into that connection
// (setVideoEncoderConfigurationEx). So a later change to the default never reaches the live encoder (combo17's test,
// 16:11:44: accepted, no effect). This file sets both, 3 s after a call goes live: the default (+0xf0) and the live
// connection with IRtcEngineEx::setVideoEncoderConfigurationEx(config, connection) (+0x928). The connection comes from
// Agora's own API log (its joinChannelEx line). Slots from libagora-rtc-sdk.so offline (scratchpad stream/agora_slots.py:
// the API-logger strings -> their functions -> the vtable's RELATIVE relocations; queryInterface lands on +0x0 and
// setVideoEncoderConfiguration on +0xf0, as Tribe's own calls). Each call is made only if the vtable entry points into
// libagora's code AND the function's first 16 bytes are the ones in that file.
// The struct as Tribe's build lays it out (Agora 4.x; orientationMode 1 as Tribe's call logs it):
//   0 codecType  4 width  8 height  12 frameRate  16 bitrate (kbps, 0 = standard)  20 minBitrate (-1 = default)
//   24 orientationMode  28 degradationPreference (-1 auto, 0 quality, 1 framerate, 2 balanced, 3 resolution)
//   32 mirrorMode (2 = off)  36 encodingPreference (-1 auto, 0 software, 1 hardware)
//   40 compressionPreference (-1 auto, 0 low latency, 1 quality)  44 encodeAlpha
// RtcConnection: { const char* channelId; uid_t localUid; }.
//
// stream.txt (key=value, '#' comments); a change during a call is applied within ~1 s:
//   fps=30                 frames per second the encoder may send (Tribe: 15)
//   kbps=2500              target bitrate (Tribe: 0, Agora's standard for the size: ~780 at 848x480 15 fps)
//   encoder=hardware       auto | software | hardware
//   compression=auto       auto | latency | quality
//   degradation=framerate  what to keep when the connection or the encoder struggles: auto | quality | framerate |
//                          balanced | resolution
//   capture=24             how often the stream camera renders while a call is live (Tribe: 15). TribePlayerController::Tick
//                          counts a float timer at +0x914 down by DeltaTime and, below 0, calls CaptureScene on the active
//                          capture (+0x888) and resets the timer to 1/FUN_02338b14() = 1/15 while streaming (1/24 otherwise);
//                          FUN_02338b14 is "mov w0,#15; ret". So the encoder only ever got 72/5 = 14.4 frames/s (combo18,
//                          16:34: Agora's sink wanted 30 and still got 14.4). Each frame this file clamps that timer to
//                          (N - 0.75) frames, N = round(72 / capture): at 72 Hz, 24 -> every 3rd frame, 36 -> every 2nd.
//   size=1280x720          the stream's picture size (Tribe: 848x480), changed only while no call is live. Tribe keeps it in
//                          libUnreal .bss (vaddr 0x7F02DC4: width, height; FUN_051d2dcc returns it). While streaming,
//                          TribePlayerController::Tick resizes the active capture's TextureTarget (+0x300: SizeX@0x138,
//                          SizeY@0x13c, then vtable+0x340) to it and skips that tick's capture; the frame producer
//                          FUN_051ff164 converts width x height of the readback into the I420 buffer at manager+0x908;
//                          the push (FUN_051d0564) and the encoder config use it. A change mid-call could convert an
//                          old-size readback with the new size, so it waits for the call to end. Off-call Tribe sizes the
//                          capture from another pair (vaddr 0x7F02740), logged once.
// The calls are only made while Tribe says a call or a stream is live (bInVideoCallReplicated / GetIsChannelStreaming).
// Tribe's own re-send (combo21): FUN_051d3ce4 (libUnreal vaddr 0x50D4CE4) is Tribe's setVideoEncoderConfigurationEx with
// its 15 fps / standard settings for the live connection. Its only caller, the join step FUN_051fd10c, runs it right after
// a successful joinChannelEx, so it comes back at every join. A mid-stream re-join with Tribe's live flags still on would
// keep Tribe's settings for the rest of that stream. So this file hooks it (checked against its first 16 bytes): the hook
// runs it, then counts it, and the game thread puts ours back about 1 s later (re-reading the connection from the log).
// Tribe 0.12.6 (versionCode 2311; port 2026-10-31, claudedocs/mod_fix_port.md): same Agora library (md5 81b006ac) and the
// same calls; addresses moved. Addresses below are 2311's (the 2304 value in each comment). The engine pointer is at
// manager +0x570; the size pair at vaddr 0x8B092C4 (FUN_05b7ecb0 returns it; a static init still writes 848x480); the
// re-send is FUN_05b80e7c (callers: the join step FUN_05b80590 and a reconnect lambda), and 2311 adds a second re-send,
// FUN_05b81f18, run on a call role change (its caller stores the role at +0xa40, then updateChannelMediaOptionsEx): it
// sends the same 15 fps / standard settings, so it is hooked the same way. The frame producer is now inside the push
// (FUN_05b7bb5c).
struct StCfg { int v[8]; int has[8]; };              // fps, kbps, encoder, compression, degradation, capture, width, height
enum { ST_FPS, ST_KBPS, ST_ENC, ST_COMP, ST_DEGR, ST_CAP, ST_W, ST_H };
static StCfg g_stCfg[2]; static volatile sig_atomic_t g_stIdx=-1, g_stGen=0;
static volatile uintptr_t g_stMgr=0;                  // the live TribeVideoCallManager (poll thread)
static uintptr_t g_stFnStreaming=0, g_stAgoraLo=0, g_stAgoraHi=0;
static volatile int g_stInCallOff=-1; static volatile uint8_t g_stInCallMask=0;
static volatile uintptr_t g_stPC=0, g_stPCCls=0;      // Tribe's player controller (poll thread): the stream camera's timer
// the live connection, read by the poll thread from Agora's log after the game thread saw a call go live
static char g_stChan[2][72]; static volatile uint32_t g_stUid[2]; static volatile sig_atomic_t g_stConnIdx=-1;
static volatile sig_atomic_t g_stLiveSeq=0, g_stConnSeq=-1;
#define ST_ENGINE_OFF 0x570                           // TribeVideoCallManager -> IRtcEngine* (call start; 2304: 0x550)
#define ST_SETVEC_SLOT 0xf0                           // IRtcEngine::setVideoEncoderConfiguration (Tribe's own call)
#define ST_SETVECEX_SLOT 0x928                        // IRtcEngineEx::setVideoEncoderConfigurationEx (libagora 4.5.2)
#define ST_DIMS_VADDR 0x8B092C4                       // libUnreal: the capture/stream width, height (two ints; 2304: 0x7F02DC4)
#define ST_DIMS_OFFCALL_VADDR 0x8B08CF0               // libUnreal: the capture's size when no stream runs (2304: 0x7F02740)
#define ST_TRIBE_W 848
#define ST_TRIBE_H 480
#define ST_PC_CAPTURE 0x888                           // TribePlayerController: the active SceneCaptureComponent2D
#define ST_PC_TIMER 0x914                             // TribePlayerController: seconds to the stream camera's next capture
#define ST_TRIBE_SEND_VADDR 0x5A81E7C                 // libUnreal FUN_05b80e7c: Tribe's own setVideoEncoderConfigurationEx (2304: 0x50D4CE4)
#define ST_TRIBE_ROLE_VADDR 0x5A82F18                 // libUnreal FUN_05b81f18: the same, on a call role change (new in 2311)
// the first 16 bytes of the two functions in libagora-rtc-sdk.so 4.5.2 (vaddr 0x180f150 and 0x180f31c)
static const uint8_t ST_SETVEC_HEAD[16]={0xff,0x83,0x04,0xd1,0xfc,0x67,0x0d,0xa9,0xf8,0x5f,0x0e,0xa9,0xf6,0x57,0x0f,0xa9};
static const uint8_t ST_SETVECEX_HEAD[16]={0xff,0xc3,0x06,0xd1,0xfc,0x6f,0x15,0xa9,0xfa,0x67,0x16,0xa9,0xf8,0x5f,0x17,0xa9};
// ... and of Tribe's two re-sends in libUnreal.so 0.12.6 (sub sp / stp x29,x30 / add x29 / stp: nothing PC-relative)
static const uint8_t ST_TRIBE_SEND_HEAD[16]={0xff,0x43,0x02,0xd1,0xfd,0x7b,0x06,0xa9,0xfd,0x83,0x01,0x91,0xf6,0x57,0x07,0xa9};
static const uint8_t ST_TRIBE_ROLE_HEAD[16]={0xff,0xc3,0x01,0xd1,0xfd,0x7b,0x05,0xa9,0xfd,0x43,0x01,0x91,0xf4,0x4f,0x06,0xa9};
// the engine comes from Android's allocator, whose pointers carry a tag in the top byte (0xb4...): the CPU ignores it,
// but /proc/self/maps (sr's range check) has the untagged addresses. Read through the untagged address; call with the
// pointer as Tribe has it. (combo16 read 0 here and never called: 2026-10-27 16:03:36.)
#define ST_UNTAG(p) ((uintptr_t)(p) & 0x00FFFFFFFFFFFFFFull)

// Tribe's re-sends, hooked: run each, then count it for the game thread (they run on Tribe's call threads, not the game
// thread). Both take only the manager (x0) and return nothing (2311 disassembly).
static volatile sig_atomic_t g_stTribeSends=0, g_stTribeRoles=0;
static void (*st_orig_send)(void* mgr)=0;
static void (*st_orig_role)(void* mgr)=0;
static void st_repl_send(void* mgr){ st_orig_send(mgr); __sync_fetch_and_add(&g_stTribeSends,1); }
static void st_repl_role(void* mgr){ st_orig_role(mgr); __sync_fetch_and_add(&g_stTribeRoles,1); }
// mod2311: hooked from the library constructor, next to ProcessEvent, before any thread runs (they used to be patched from
// the poll thread with Tribe already running, after an mprotect and a rebuild of the shared range table there). The
// first 16 bytes are read directly once the page is known to be r-x (maps_rx); both heads checked in the 2311 store
// library by backup/mod2311_build/tools/verify_2311.py.
static void st_hook_one(uintptr_t vaddr,const uint8_t* head,void* repl,void** orig,const char* what){
    uintptr_t f=g_base+vaddr; uint8_t h[16]={0};
    if(!maps_rx(f,16)){ LOGI("[STREAM] Tribe's encoder re-send (%s) @0x%lx: its page is not r-x: NOT hooked",what,(unsigned long)f); return; }
    memcpy(h,(const void*)f,16);
    if(memcmp(h,head,16)){
        LOGI("[STREAM] Tribe's encoder re-send (%s) @0x%lx: head %02x%02x%02x%02x is not the expected one: NOT hooked (ours still follows each call's start)",
             what,(unsigned long)f,h[0],h[1],h[2],h[3]); return; }
    A64HookFunction((void*)f,repl,orig);              // patches only once its trampoline is ready
    LOGI("[STREAM] Tribe's encoder re-send (%s) @0x%lx %s",what,(unsigned long)f,
         *orig?"hooked: ours follows it about 1 s later":"NOT hooked (the hook library failed)"); }
static void st_hook_send(){                           // the constructor, once (after the ProcessEvent hook)
    static bool done=false; if(done||!g_base) return; done=true;
    st_hook_one(ST_TRIBE_SEND_VADDR,ST_TRIBE_SEND_HEAD,(void*)st_repl_send,(void**)&st_orig_send,"join");
    st_hook_one(ST_TRIBE_ROLE_VADDR,ST_TRIBE_ROLE_HEAD,(void*)st_repl_role,(void**)&st_orig_role,"role change"); }

static bool st_word(const char* v,const char* const* names,const int* vals,int n,int* out){
    for(int i=0;i<n;i++) if(!strcasecmp(v,names[i])){ *out=vals[i]; return true; }
    return false; }
static void st_parse(StCfg* c,const char* text){
    static const char* const EN[]={"auto","software","hardware"};               static const int EV[]={-1,0,1};
    static const char* const CN[]={"auto","latency","quality"};                 static const int CV[]={-1,0,1};
    static const char* const DN[]={"auto","quality","framerate","balanced","resolution"}; static const int DV[]={-1,0,1,2,3};
    memset(c,0,sizeof *c);
    for(const char* q=text; *q; ){
        const char* e=strchr(q,'\n'); size_t n=e?(size_t)(e-q):strlen(q); char ln[160]; if(n>=sizeof ln) n=sizeof ln-1;
        memcpy(ln,q,n); ln[n]=0; q=e?e+1:q+n;
        char* h=strchr(ln,'#'); if(h) *h=0;
        char k[32], v[64]; if(sscanf(ln," %31[^= ] = %63s",k,v)!=2) continue;
        if(!strcmp(k,"fps")){ int x=atoi(v); if(x>=5&&x<=60){ c->v[ST_FPS]=x; c->has[ST_FPS]=1; } }
        else if(!strcmp(k,"kbps")){ int x=atoi(v); if(x>=200&&x<=8000){ c->v[ST_KBPS]=x; c->has[ST_KBPS]=1; } }
        else if(!strcmp(k,"encoder")) c->has[ST_ENC]=st_word(v,EN,EV,3,&c->v[ST_ENC]);
        else if(!strcmp(k,"compression")) c->has[ST_COMP]=st_word(v,CN,CV,3,&c->v[ST_COMP]);
        else if(!strcmp(k,"degradation")) c->has[ST_DEGR]=st_word(v,DN,DV,5,&c->v[ST_DEGR]);
        else if(!strcmp(k,"capture")){ int x=atoi(v); if(x>=5&&x<=72){ c->v[ST_CAP]=x; c->has[ST_CAP]=1; } }
        else if(!strcmp(k,"size")){ int w=0, h=0; if(sscanf(v,"%dx%d",&w,&h)==2&&w>=320&&w<=1920&&h>=240&&h<=1088&&!(w&15)&&!(h&15)){
            c->v[ST_W]=w; c->v[ST_H]=h; c->has[ST_W]=c->has[ST_H]=1; } } } }
static void st_find_agora(){                          // libagora-rtc-sdk.so's executable mapping
    FILE* f=fopen("/proc/self/maps","r"); if(!f) return; char line[1024];
    while(fgets(line,sizeof line,f)){ uintptr_t lo,hi; char perm[8];
        if(strstr(line,"libagora-rtc-sdk.so")&&sscanf(line,"%lx-%lx %4s",&lo,&hi,perm)==3&&perm[2]=='x'){
            if(!g_stAgoraLo||lo<g_stAgoraLo) g_stAgoraLo=lo; if(hi>g_stAgoraHi) g_stAgoraHi=hi; } }
    fclose(f);
    if(g_stAgoraHi) LOGI("[STREAM] libagora-rtc-sdk.so code at 0x%lx-0x%lx",(unsigned long)g_stAgoraLo,(unsigned long)g_stAgoraHi); }
// the last joinChannelEx in one of Agora's API logs: {"connection":{"channelId":"X", "localUid":N}
static bool st_conn_from_file(const char* path,char* chan,size_t cap,uint32_t* uid){
    FILE* f=fopen(path,"rb"); if(!f) return false;
    static char buf[262145]; fseek(f,0,SEEK_END); long sz=ftell(f); fseek(f,sz>262144?sz-262144:0,SEEK_SET);
    size_t n=fread(buf,1,262144,f); fclose(f); buf[n]=0;
    char* last=0; for(char* p=buf; (p=(char*)memmem(p,(size_t)(buf+n-p),"joinChannelEx(this:",19)); p++) last=p;
    if(!last) return false;
    char* c=strstr(last,"\"channelId\":\""); char* u=strstr(last,"\"localUid\":"); if(!c||!u||u-last>400) return false;
    c+=13; size_t k=0;
    while(c[k]&&c[k]!='"'&&k<cap-1){ unsigned char ch=(unsigned char)c[k]; if(!(isalnum(ch)||ch=='_'||ch=='-')) return false; k++; }
    if(c[k]!='"'||!k) return false;
    memcpy(chan,c,k); chan[k]=0; *uid=(uint32_t)strtoul(u+11,0,10); return true; }

// one-time diagnostic: the Tribe video-call and player-controller objects in the object array (passes at ~30 s and ~120 s)
static void st_diag_objects(){
    refresh_numelements(); int shown=0, tot=0;
    for(uint32_t i=0;i<g_numElements && shown<16;i++){ uintptr_t o=obj_at(i); if(!o) continue;
        char cn[128], fp[400]; class_name(o,cn,sizeof cn);
        if(!strstr(cn,"VideoCall") && !strstr(cn,"PlayerController")) continue;
        full_path(o,fp,sizeof fp); if(strstr(fp,"Default__")) continue; tot++; shown++;
        LOGI("[STREAM] diag object %u: class %s, path %s, flags 0x%x, alive %d", (unsigned)i, cn, fp, (unsigned)rd32(o+OFF_Flags), obj_alive(o)?1:0); }
    LOGI("[STREAM] diag objects: %d matched, %u in the array", tot, (unsigned)g_numElements); }
// ---- POLL thread (~1 s): the file, the manager, the live connection
static void stream_poll(){
    char p[600]; snprintf(p,sizeof p,"%s/stream.txt",OUTDIR); struct stat st; static long lastKey=-2;
    long key=stat(p,&st)==0?(long)st.st_mtime*1000003L+(long)st.st_size:-1;
    if(key!=lastKey){
        if(key==-1){ lastKey=key; if(g_stIdx>=0) LOGI("[STREAM] tribemod/stream.txt is gone: Tribe's own encoder settings from the next call"); g_stIdx=-1; }
        else { char text[2048]; size_t n=0; FILE* f=fopen(p,"rb"); if(f){ n=fread(text,1,sizeof text-1,f); fclose(f); } text[n]=0;
          if(!f||n==0){ static int w=0; if((w++%30)==0) LOGI("[STREAM] tribemod/stream.txt could not be read yet: trying again"); }   // mod2311:
          else { lastKey=key;                                                           // remembered only once read (load doc 2e)
            int nx=g_stIdx==0?1:0; st_parse(&g_stCfg[nx],text); __sync_synchronize(); g_stIdx=nx; g_stGen=g_stGen+1;
            const StCfg* c=&g_stCfg[nx];
            LOGI("[STREAM] stream.txt: fps %d%s, kbps %d%s, encoder %d%s, compression %d%s, degradation %d%s, capture %d%s, size %dx%d%s (Tribe's for '-')",
                 c->v[ST_FPS],c->has[ST_FPS]?"":" -",c->v[ST_KBPS],c->has[ST_KBPS]?"":" -",c->v[ST_ENC],c->has[ST_ENC]?"":" -",
                 c->v[ST_COMP],c->has[ST_COMP]?"":" -",c->v[ST_DEGR],c->has[ST_DEGR]?"":" -",c->v[ST_CAP],c->has[ST_CAP]?"":" -",
                 c->v[ST_W],c->v[ST_H],c->has[ST_W]?"":" -"); } } }
    { static int tkn=0; if((++tkn % 60)==0) LOGI("[STREAM] diag ticks: ProcessEvent calls %ld, per-frame runs %ld", g_pe_n, g_pe_drv); }
    if(g_stIdx<0) return;
    { static int dpn=0; if(++dpn==30||dpn==120) st_diag_objects(); }
    if(!g_stAgoraHi){ static int tries=0; if((tries++%30)==0) st_find_agora(); }
    if(!g_stFnStreaming) g_stFnStreaming=find_by_path("/Script/TribeXR.TribeVideoCallManager.GetIsChannelStreaming",0);
    uintptr_t m=g_stMgr; static int tk=0;
    if((!m||!obj_alive(m))&&(tk++%5)==0){ refresh_numelements(); m=em_find_live_pl("TribeVideoCallManager");
        if(m&&m!=g_stMgr){ uintptr_t cls=rdptr(m+OFF_Class); int S=calib_fprop_size(); uintptr_t fb=find_field(cls,"bInVideoCallReplicated");
            int off=-1; uint8_t bo=0, bm=0;
            if(S>0&&fb){ off=(int)rd32(fb+FP_Offset); bo=rd8(fb+S+1); bm=rd8(fb+S+2); if(off<0||off>0x4000||bo>7||!bm) off=-1; }
            g_stInCallMask=bm; g_stInCallOff=off>=0?off+bo:-1;
            char cn[96]; class_name(m,cn,sizeof cn);
            LOGI("[STREAM] Tribe's video-call manager 0x%lx (%s): bInVideoCallReplicated %s, GetIsChannelStreaming 0x%lx",(unsigned long)m,cn,
                 g_stInCallOff>=0?"found":"MISSING",(unsigned long)g_stFnStreaming); }
        g_stMgr=m; }
    uintptr_t pc=g_stPC; static int pk=0;
    if((!pc||!obj_alive(pc))&&(pk++%5)==0){ refresh_numelements(); pc=em_find_live_pl("TribePlayerController");
        if(pc&&pc!=g_stPC){ char cn[96]; class_name(pc,cn,sizeof cn); LOGI("[STREAM] Tribe's player controller 0x%lx (%s)",(unsigned long)pc,cn); }
        g_stPCCls=pc?rdptr(pc+OFF_Class):0; g_stPC=pc; }
    int ls=g_stLiveSeq;                               // a call went live: which connection did Tribe join?
    if(ls>0&&ls!=g_stConnSeq){ static int miss=0; char base[600], p1[640], p2[640], ch[72]; uint32_t uid=0;
        snprintf(base,sizeof base,"%s",OUTDIR); char* sl=strrchr(base,'/'); if(sl) *sl=0;   // .../files (tribemod's parent)
        snprintf(p1,sizeof p1,"%s/agoraapi.log",base); snprintf(p2,sizeof p2,"%s/agoraapi.1.log",base);
        if(st_conn_from_file(p1,ch,sizeof ch,&uid)||st_conn_from_file(p2,ch,sizeof ch,&uid)){
            int nx=g_stConnIdx==0?1:0; snprintf(g_stChan[nx],sizeof g_stChan[nx],"%s",ch); g_stUid[nx]=uid; __sync_synchronize();
            g_stConnIdx=nx; g_stConnSeq=ls; miss=0; LOGI("[STREAM] the live connection (Agora's log): channel %s, uid %u",ch,uid); }
        else if((miss++%10)==0) LOGI("[STREAM] no joinChannelEx in Agora's log yet (%s)",p1); } }

// ---- GAME thread, while no call is live: Tribe's stream size -> stream.txt's (or back to Tribe's 848x480 without the key)
static void st_size_offcall(const StCfg* c){
    if(!g_base) return;
    static int logged=0, ourW=0, ourH=0;
    int32_t* d=(int32_t*)(g_base+ST_DIMS_VADDR); int w=d[0], h=d[1];
    if(!w&&!h) return;                                // Tribe hasn't set it yet
    if(!logged){ logged=1; int32_t* o=(int32_t*)(g_base+ST_DIMS_OFFCALL_VADDR);
        LOGI("[STREAM] Tribe's stream size %dx%d (off-call capture size %dx%d)",w,h,o[0],o[1]); }
    int wantW=c->has[ST_W]?c->v[ST_W]:ST_TRIBE_W, wantH=c->has[ST_H]?c->v[ST_H]:ST_TRIBE_H;
    if(w==wantW&&h==wantH) return;
    bool tribes=(w==ST_TRIBE_W&&h==ST_TRIBE_H), ours=(ourW&&w==ourW&&h==ourH);
    if(!tribes&&!ours){ static int warned=0; if(!warned){ warned=1;
        LOGI("[STREAM] the stream size reads %dx%d (not Tribe's 848x480 nor ours): NOT changing it",w,h); } return; }
    d[0]=wantW; d[1]=wantH; ourW=wantW; ourH=wantH;
    LOGI("[STREAM] stream size %dx%d -> %dx%d (from the next call)",w,h,wantW,wantH); }

// ---- GAME thread, every frame while live: the stream camera's next capture at most (N - 0.75) frames away
static void st_capture_clamp(int rate,float dt){
    static double fdt=1.0/72; if(dt>0.f&&dt<0.1f) fdt+=(dt-fdt)*0.05;    // the frame time, smoothed
    uintptr_t pc=g_stPC; if(!pc||!obj_alive(pc)||rdptr(pc+OFF_Class)!=g_stPCCls) return;   // (mod2311: the class too)
    static uintptr_t okComp=0, badComp=0; uintptr_t comp=rdptr(pc+ST_PC_CAPTURE);
    if(!comp||comp==badComp) return;
    if(comp!=okComp){ char cn[96]; class_name(comp,cn,sizeof cn);             // the layout check, once per camera
        if(!obj_alive(comp)||!strstr(cn,"SceneCaptureComponent")){ badComp=comp;
            LOGI("[STREAM] player controller +0x%x = 0x%lx (%s) is not a scene capture: NOT touching the capture timer",ST_PC_CAPTURE,(unsigned long)comp,cn); return; }
        okComp=comp; LOGI("[STREAM] stream camera 0x%lx (%s): capturing every %d frame(s) while live (Tribe: 1/15 s)",(unsigned long)comp,cn,
                          (int)fmax(1.0,floor(1.0/(rate*fdt)+0.5))); }
    float* tp=(float*)(pc+ST_PC_TIMER); float v=*tp;
    if(!(v>-1.f&&v<1.f)) return;                                            // not a timer: leave it
    double n=fmax(1.0,floor(1.0/(rate*fdt)+0.5)), lim=(n-0.75)*fdt;
    if(v>lim) *tp=(float)lim; }

// ---- GAME thread: 3 s after a call starts (once the live connection is known, at most 15 s), and when stream.txt changes
static volatile sig_atomic_t g_stOnPoll=0;   // 1 while stream_tick runs from stream_poll (the poll thread): no UE calls then
static void stream_tick(float dt){
    int ix=g_stIdx; if(ix<0) return;
    uintptr_t m=g_stMgr; if(!m||!obj_alive(m)) return;
    static uintptr_t lastEng=0; static bool wasLive=false, applied=false; static double t=0, chk=0, next=3.0;
    static int doneGen=-1, inCall=0, streaming=0, tries=0, seenSends=0, seenRoles=0; static const char* why="after the call started";
    if(dt>0.f&&dt<2.f){ t+=dt; chk+=dt; }
    if(chk>=0.5){ chk=0;                              // Tribe's own flags, twice a second
        int o=g_stInCallOff; inCall=(o>=0)?((rd8(m+o)&g_stInCallMask)?1:0):0;
        uint8_t* r=(!g_stOnPoll&&g_stFnStreaming)?call_ret(m,g_stFnStreaming,0,0):0; streaming=(r&&*r)?1:0; }
    bool live=inCall||streaming;
    uintptr_t eng=rdptr(m+ST_ENGINE_OFF);
    if(eng!=lastEng||(live&&!wasLive)){
        if(live&&eng){ g_stLiveSeq=g_stLiveSeq+1; LOGI("[STREAM] a call is live (in call %d, streaming %d), engine 0x%lx",inCall,streaming,(unsigned long)eng); }
        lastEng=eng; applied=false; t=0; next=3.0; tries=0; why="after the call started"; }
    if(!live&&wasLive){ LOGI("[STREAM] the call ended"); applied=false; }
    int sends=g_stTribeSends, roles=g_stTribeRoles;   // Tribe re-sent its settings (it joined, or a role change): ours again in about 1 s
    if(sends!=seenSends||roles!=seenRoles){ bool join=sends!=seenSends; seenSends=sends; seenRoles=roles;
        if(live&&eng){ g_stLiveSeq=g_stLiveSeq+1; applied=false; t=0; next=1.0; tries=0;
            why=join?"after Tribe's own re-send":"after Tribe's role-change re-send";
            LOGI("[STREAM] Tribe sent its own encoder settings (%s; #%d): ours again in about 1 s",join?"it joined":"a role change",join?sends:roles); } }
    wasLive=live;
    if(!g_stOnPoll&&live&&g_stCfg[ix].has[ST_CAP]) st_capture_clamp(g_stCfg[ix].v[ST_CAP],dt);
    if(!live) st_size_offcall(&g_stCfg[ix]);       // never during a call: an old-size readback could be in flight
    if(!live||!eng) return;
    if(applied){ if(doneGen==g_stGen) return; }      // applied: again only when stream.txt changes
    else if(t<next||tries>=20) return;
    int ci=g_stConnIdx; bool connOk=ci>=0&&g_stConnSeq==g_stLiveSeq;
    if(!applied&&!connOk&&t<15.0){ next=t+1.0; return; }          // wait for the poll thread's connection (15 s at most)
    if(!g_stAgoraHi) st_find_agora();                 // Agora's library is loaded by the call itself
    uintptr_t vt=rdptr(ST_UNTAG(eng));
    uintptr_t fn=vt?rdptr(ST_UNTAG(vt)+ST_SETVEC_SLOT):0, fnx=vt?rdptr(ST_UNTAG(vt)+ST_SETVECEX_SLOT):0;
    uint8_t h1[16]={0}, h2[16]={0};
    bool ok1=fn&&fn>=g_stAgoraLo&&fn<g_stAgoraHi&&sr(fn,h1,16)&&!memcmp(h1,ST_SETVEC_HEAD,16);
    bool ok2=fnx&&fnx>=g_stAgoraLo&&fnx<g_stAgoraHi&&sr(fnx,h2,16)&&!memcmp(h2,ST_SETVECEX_HEAD,16);
    if(!ok1){ next=t+3.0; ++tries;                    // try again in 3 s, 20 times per call
        if(tries<=2||tries==20) LOGI("[STREAM] engine 0x%lx: vtable 0x%lx, +0x%x = 0x%lx (head %02x%02x%02x%02x), agora code 0x%lx-0x%lx: NOT calling%s",
             (unsigned long)eng,(unsigned long)vt,ST_SETVEC_SLOT,(unsigned long)fn,h1[0],h1[1],h1[2],h1[3],(unsigned long)g_stAgoraLo,
             (unsigned long)g_stAgoraHi,tries==20?" (giving up for this call)":" (trying again in 3 s)");
        if(applied) doneGen=g_stGen; return; }
    int w=848, h=480;                                 // Tribe's size, as its own call used it
    if(g_base){ int a=(int)rd32(g_base+ST_DIMS_VADDR), b=(int)rd32(g_base+ST_DIMS_VADDR+4); if(a>=160&&a<=3840&&b>=120&&b<=2160){ w=a; h=b; } }
    const StCfg* c=&g_stCfg[ix];
    static int32_t cfg[16]; memset(cfg,0,sizeof cfg);
    cfg[0]=0; cfg[1]=w; cfg[2]=h;
    cfg[3]=c->has[ST_FPS]?c->v[ST_FPS]:15; cfg[4]=c->has[ST_KBPS]?c->v[ST_KBPS]:0; cfg[5]=-1;
    cfg[6]=1;                                         // orientationMode: Tribe's call has 1 (fixed landscape; agoraapi.log)
    cfg[7]=c->has[ST_DEGR]?c->v[ST_DEGR]:-1; cfg[8]=2; cfg[9]=c->has[ST_ENC]?c->v[ST_ENC]:-1; cfg[10]=c->has[ST_COMP]?c->v[ST_COMP]:-1;
    typedef int (*SetVEC)(void* self,const void* config);
    typedef int (*SetVECEx)(void* self,const void* config,const void* connection);
    int rc=((SetVEC)fn)((void*)eng,cfg), rcx=-999;
    static struct { const char* channelId; uint32_t localUid; uint32_t pad; } conn;
    if(connOk&&ok2){ conn.channelId=g_stChan[ci]; conn.localUid=g_stUid[ci]; conn.pad=0; rcx=((SetVECEx)fnx)((void*)eng,cfg,&conn); }
    LOGI("[STREAM] encoder %dx%d, %d fps, %d kbps, degradation %d, encoder %d, compression %d: default -> %d; live connection %s/%u -> %d%s (%s)",
         w,h,cfg[3],cfg[4],cfg[7],cfg[9],cfg[10],rc,connOk?g_stChan[ci]:"?",connOk?g_stUid[ci]:0,rcx,
         !connOk?" (no connection from Agora's log)":!ok2?" (setVideoEncoderConfigurationEx check FAILED: not called)":"",
         applied?"stream.txt changed":why);
    applied=true; doneGen=g_stGen; }
