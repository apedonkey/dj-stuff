// club.cpp: the REACTOR club's mod features (claudedocs/club_venue_plan.md section 5). The club session owns this file;
// dumper.cpp includes it just before repl_pe (so it can use dumper's helpers) and calls club_pe / club_tick / club_lookup.
// Inert unless the active environment is the club's map (/Mods/Club/). Logs [CLUB].
//
// Walking (5.2): the left stick walks where you look, the right stick turns 30 deg about your head, the right stick held
// down for 1 s takes you back to where Tribe put you. It moves TribePawnBP_C.VROrigin relative to its parent, as the giant
// lift does for Z. Collision and floors: tribemod/club_collide.txt (Scripts/Blender/club/club_collide.py; the rules are in
// hook/club_collide.h, checked on the headset by tests/club_collide_test.cpp). Settings: tribemod/club.txt (optional,
// read every 2 s), e.g. "walk=1 speed=180 deadzone=0.25 turn=30 role=auto" (role: auto | host | dj | guest).
// The gate (5.4, prototype): the airlock door lets the host or a DJ (Tribe's replicated bDJing) through; a guest is refused
// going in and can always walk out. A guest found on the stage is moved to the floor outside the door (spot guest_floor).
// Any stage can walk (the Dino session asked, 2026-10-09): its map is tribemod/<folder>_collide.txt, <folder> being the
// lowercased name under /Game/Mods/ in its path (club_collide.txt, dino_collide.txt); no file = no walking there. Spots
// and gates are optional. Another feature that moves VROrigin (the Dino giant lift) sets g_walkPause while it does.
#include "club_collide.h"

#ifndef HAVE_WALK_PAUSE                                         // the Dino session declares it next to the giant (it sets it
static volatile sig_atomic_t g_walkPause=0;                    // while the lift moves VROrigin); until then, ours (always 0)
#endif

// ---- poll thread -> game thread
static volatile sig_atomic_t g_clubOn=0;                       // a stage with a walking map is up and walking can run
static volatile sig_atomic_t g_clubOnIdx=-1;                    // ...and which one (g_emActive): club_lookup runs every 2 s
                                                                // and can miss a stage switch, so club_tick checks it too
static CCMap g_clubMap[2]; static volatile sig_atomic_t g_clubMapIdx=-1; static time_t g_clubMapMtime=0;   // double buffer
static int g_clubMapPub=-1;                                     // the buffer published last (the game thread may be in it)
static char g_clubMapName[64]="";                               // the active stage's map file under tribemod/
static volatile int g_clubWalk=1, g_clubRole=0;                // club.txt: walk on/off; role 0 auto, 1 host, 2 dj, 3 guest
static volatile double g_clubSpeed=180, g_clubDead=0.25, g_clubTurn=30;
// club.txt room= stage= crowd= rim=: the dark club's dimmers in MPC_ClubShow (build_club.py CLUB_EXTRAS holds the pak's
// defaults). -1 = not set: the pak's value stands (a key removed from club.txt keeps its last value until the stage reloads)
static const char* const CLUB_DIMS[4]={"RoomGain","StageGain","CrowdGain","CrowdRim"};
static const char* const CLUB_DIM_KEYS[4]={"room=","stage=","crowd=","rim="};
static volatile double g_clubDim[4]={-1,-1,-1,-1};
static const char* const CLUB_ROLES[4]={"auto","host","dj","guest"};
static uintptr_t g_cFnLoc=0, g_cFnRot=0, g_cFnSetRel=0, g_cGPS=0, g_cFnGetPawn=0, g_cFnGetPC=0, g_cFnKey=0, g_cKSL=0, g_cFnToName=0;
static uintptr_t g_cFnParent=0, g_cFnScale=0;
static uintptr_t g_cAxFn[4]; static int g_cAxOff[4];           // TribePawnBP_C's stick events: L X, L Y, R X, R Y (2304 only:
                                                                // 0.12.6's C++ pawn has none, club_sticks polls the keys then)
// ---- game thread
static float g_cAx[4]; static long g_cAxFrame[4]={-1000,-1000,-1000,-1000}; static uintptr_t g_cAxSelf=0; static long g_cFrame=0;

// first thing in repl_pe: the stick values Tribe's pawn receives every frame (AxisValue). Four pointer compares.
static inline void club_pe(void* self,void* func,void* parms){
    if(!g_clubOn||!func||!parms) return; uintptr_t f=(uintptr_t)func;
    for(int i=0;i<4;i++) if(f==g_cAxFn[i]){ memcpy(&g_cAx[i],(uint8_t*)parms+g_cAxOff[i],4); g_cAxFrame[i]=g_cFrame; g_cAxSelf=(uintptr_t)self; return; } }

// ---- POLL thread (every 2 s from env_menu_poll)
// one pass over the objects for the engine functions (by full path, FName number 0) and Tribe's four stick events (by name
// and owner TribePawnBP_C: a K2Node event's FName may carry a number, so find_by_path can't see it)
static void club_find_all(){
    enum { NP=11 };
    static const char* const P[NP]={"/Script/Engine.SceneComponent.K2_GetComponentLocation","/Script/Engine.SceneComponent.K2_GetComponentRotation",
        "/Script/Engine.SceneComponent.K2_SetRelativeLocationAndRotation","/Script/Engine.Default__GameplayStatics",
        "/Script/Engine.GameplayStatics.GetPlayerPawn","/Script/Engine.GameplayStatics.GetPlayerController",
        "/Script/Engine.PlayerController.GetInputAnalogKeyState","/Script/Engine.Default__KismetStringLibrary",
        "/Script/Engine.KismetStringLibrary.Conv_StringToName","/Script/Engine.SceneComponent.GetAttachParent",
        "/Script/Engine.SceneComponent.K2_GetComponentScale"};
    static const char* const AX[4]={"InpAxisEvt_MotionController L Thumbstick_X_K2Node_InputAxisEvent",
        "InpAxisEvt_MotionController L Thumbstick_Y_K2Node_InputAxisEvent","InpAxisEvt_MotionController R Thumbstick_X_K2Node_InputAxisEvent",
        "InpAxisEvt_MotionController R Thumbstick_Y_K2Node_InputAxisEvent"};
    uintptr_t out[NP]={0}, ax[4]={0}; char nm[128], fp[512], on[64];
    refresh_numelements();
    for(uint32_t i=0;i<g_numElements;i++){ uintptr_t o=obj_at(i); if(!o) continue;
        obj_name(o,nm,sizeof nm);
        if(!strncmp(nm,"InpAxisEvt_MotionController ",28)){
            obj_name(rdptr(o+OFF_Outer),on,sizeof on); if(strcmp(on,"TribePawnBP_C")) continue;
            for(int k=0;k<4;k++) if(!ax[k]&&!strcmp(nm,AX[k])) ax[k]=o;
            continue; }
        if(rd32(o+OFF_Name+4)!=0) continue;
        bool cand=false; for(int k=0;k<NP&&!cand;k++){ const char* t=strrchr(P[k],'.'); cand=!out[k]&&t&&!strcmp(t+1,nm); }
        if(!cand) continue;
        full_path(o,fp,sizeof fp); for(int k=0;k<NP;k++) if(!out[k]&&!strcmp(fp,P[k])) out[k]=o; }
    for(int k=0;k<4;k++) if(ax[k]){ int off=prop_offset(ax[k],"AxisValue",0); g_cAxOff[k]=off>=0?off:0; }
    __sync_synchronize();
    for(int k=0;k<4;k++) g_cAxFn[k]=ax[k];
    g_cFnLoc=out[0]; g_cFnRot=out[1]; g_cGPS=out[3]; g_cFnGetPawn=out[4]; g_cFnGetPC=out[5]; g_cFnKey=out[6]; g_cKSL=out[7]; g_cFnToName=out[8];
    g_cFnParent=out[9]; g_cFnScale=out[10];
    g_cFnSetRel=out[2];
    LOGI("[CLUB] engine: GetLoc 0x%lx GetRot 0x%lx SetRelLocRot 0x%lx GetAttachParent 0x%lx GetScale 0x%lx | GameplayStatics 0x%lx "
         "GetPlayerPawn 0x%lx GetPlayerController 0x%lx | GetInputAnalogKeyState 0x%lx | KismetStringLibrary 0x%lx Conv_StringToName 0x%lx",
         (unsigned long)out[0],(unsigned long)out[1],(unsigned long)out[2],(unsigned long)out[9],(unsigned long)out[10],(unsigned long)out[3],
         (unsigned long)out[4],(unsigned long)out[5],(unsigned long)out[6],(unsigned long)out[7],(unsigned long)out[8]);
    LOGI("[CLUB] stick events on TribePawnBP_C: LX 0x%lx LY 0x%lx RX 0x%lx RY 0x%lx (AxisValue at +%d)%s",(unsigned long)ax[0],
         (unsigned long)ax[1],(unsigned long)ax[2],(unsigned long)ax[3],g_cAxOff[0],
         (ax[0]&&ax[1]&&ax[2]&&ax[3])?"":" -> not all there (0.12.6 has none): the sticks come from GetInputAnalogKeyState"); }
static void club_read_cfg(){                                    // tribemod/club.txt; anything missing takes its default
    char s[600]=""; read_trim_file("club.txt",s,sizeof s);
    double v; const char* p; int walk=1, role=0; double speed=180, dead=0.25, turn=30;
    if((p=strstr(s,"walk="))&&sscanf(p+5,"%lf",&v)==1) walk=(v!=0);
    if((p=strstr(s,"speed="))&&sscanf(p+6,"%lf",&v)==1&&v>=20&&v<=600) speed=v;
    if((p=strstr(s,"deadzone="))&&sscanf(p+9,"%lf",&v)==1&&v>=0.05&&v<=0.8) dead=v;
    if((p=strstr(s,"turn="))&&sscanf(p+5,"%lf",&v)==1&&v>=5&&v<=90) turn=v;
    if((p=strstr(s,"role="))){ p+=5; role=!strncmp(p,"host",4)?1:!strncmp(p,"dj",2)?2:!strncmp(p,"guest",5)?3:0; }
    double dim[4]; bool dimch=false; char dl[96]=""; int dn=0;
    for(int i=0;i<4;i++){ dim[i]=-1; if((p=strstr(s,CLUB_DIM_KEYS[i]))&&sscanf(p+strlen(CLUB_DIM_KEYS[i]),"%lf",&v)==1&&v>=0&&v<=4) dim[i]=v;
        dimch|=dim[i]!=g_clubDim[i];
        if(dim[i]>=0) dn+=snprintf(dl+dn,sizeof dl-dn," %s%.2f",CLUB_DIM_KEYS[i],dim[i]); }
    static bool first=true;
    if(first||walk!=g_clubWalk||role!=g_clubRole||speed!=g_clubSpeed||dead!=g_clubDead||turn!=g_clubTurn||dimch)
        LOGI("[CLUB] settings: walk=%d speed=%.0f cm/s deadzone=%.2f turn=%.0f deg role=%s | dimmers:%s%s",walk,speed,dead,turn,
             CLUB_ROLES[role],dn?dl:" the pak's",s[0]?"":" (no club.txt: defaults)");
    first=false; g_clubWalk=walk; g_clubRole=role; g_clubSpeed=speed; g_clubDead=dead; g_clubTurn=turn;
    for(int i=0;i<4;i++) g_clubDim[i]=dim[i]; }
static void club_load_map(){                                    // tribemod/club_collide.txt, re-read when it changes
    char p[600]; snprintf(p,sizeof p,"%s/%s",OUTDIR,g_clubMapName); struct stat st;
    if(stat(p,&st)!=0){ static int w=0; if(g_clubMapIdx<0&&(w++%30)==0) LOGI("[CLUB] no tribemod/%s: no walking on this stage",g_clubMapName); return; }
    if(g_clubMapIdx>=0&&st.st_mtime==g_clubMapMtime) return;
    g_clubMapMtime=st.st_mtime;
    static char buf[1<<19]; FILE* f=fopen(p,"rb"); if(!f) return; size_t n=fread(buf,1,sizeof buf-1,f); fclose(f); buf[n]=0;
    if(n==sizeof buf-1){ LOGI("[CLUB] %s is over %zu bytes: not read (raise the buffer in club_load_map)",g_clubMapName,n); return; }
    int nx=(g_clubMapPub==0)?1:0; CCMap* m=&g_clubMap[nx];
    if(!cc_parse(m,buf)||m->bad){ LOGI("[CLUB] %s did not parse (%d floors, %d bad lines): %s",g_clubMapName,m->nf,m->bad,
                                       g_clubMapIdx>=0?"keeping the old map":"walking stays off"); return; }
    __sync_synchronize(); g_clubMapIdx=nx; g_clubMapPub=nx;
    LOGI("[CLUB] walking map %s: %d floors, %d boxes, %d circles, %d people, %d spots (%zu bytes); step %.0f head %.0f knee %.0f "
         "radius %.0f core %.0f cm",g_clubMapName,m->nf,m->nb,m->nc,m->np,m->ns,n,m->step,m->head,m->knee,m->radius,m->core); }
static void club_lookup(){
    int a=g_emActive; char want[64]="";
    if(g_emState==EM_ACTIVE&&a>=0&&a<EM_MAX){ const char* f=strstr(g_emPaths[a],"/Mods/");
        if(f){ f+=6; char d[32]; int n=0; while(f[n]&&f[n]!='/'&&n<31){ d[n]=(char)tolower((unsigned char)f[n]); n++; } d[n]=0;
            if(n) snprintf(want,sizeof want,"%s_collide.txt",d); } }
    if(strcmp(want,g_clubMapName)){                             // another stage (or none of ours): its own map, read afresh
        if(g_clubOn){ g_clubOn=0; g_clubOnIdx=-1; LOGI("[CLUB] off: %s",want[0]?"another stage is up":"none of our stages is up"); }
        snprintf(g_clubMapName,sizeof g_clubMapName,"%s",want); g_clubMapIdx=-1; g_clubMapMtime=0; }
    if(!want[0]) return;
    if(!g_cFnSetRel) club_find_all();
    club_read_cfg(); club_load_map();
    if(!g_clubOn&&g_clubMapIdx>=0&&g_cFnSetRel&&g_cFnLoc&&g_cFnRot&&g_cGPS&&g_cFnGetPawn){
        g_clubOnIdx=a; g_clubOn=1; LOGI("[CLUB] on: '%s' is up (walking map %s)",g_emLabels[a],g_clubMapName); } }

// ---- GAME thread
static uintptr_t g_cPawn=0, g_cPC=0, g_cVRO=0, g_cCam=0, g_cPar=0;  // g_cPar: what VROrigin hangs on (its AttachParent)
static double g_cScale=1;                                       // that parent's world scale (relative moves divide by it)
static int g_cOffVRO=-1, g_cOffCam=-1, g_cOffRole=-1, g_cOffHost=-1, g_cOffDJ=-1, g_cOffRelLoc=-1, g_cOffRelRot=-1;
static uint8_t g_cMaskHost=0xFF, g_cMaskDJ=0xFF;                     // 2311: bHost / bDJing are bitfield bools (their ByteMask)
static long g_cResolveAt=0, g_cOnFrame=0, g_cGuestMoved=-100000;
static bool g_cBased=false, g_cHaveSet=false, g_cRefloor=false, g_cTurnArmed=true, g_cIgnoreParent=false;
static double g_cBaseLoc[3], g_cBaseRot[3], g_cSetLoc[3], g_cSetRot[3], g_cParent[4];
static double g_cCur=0, g_cBaseFloor=0, g_cZ=0, g_cBackHeld=0, g_cMoved=0, g_cLogT=0, g_cRefuseT=0, g_cParentT=0;
static double g_cStage[5]; static bool g_cHaveStage=false;     // the floor rect under the decks spot (x0 y0 x1 y1 top)
static int g_cAllowed=-1, g_cParentMoves=0, g_cVroMoves=0;     // Tribe's own moves in the last 10 s (4 = it owns them)
static bool g_cGiveUp=false;                                    // Tribe keeps rewriting VROrigin: walking stands down
static bool g_cPaused=false; static long g_cHeightLogF=-100000; static int g_cHeightN=0;   // g_walkPause seen; height-only log
static uint8_t g_cKeyN[8][8]; static int g_cKeys=0, g_cOffKey=-1, g_cOffKeyRet=-1;   // g_cKeys: 0 not tried, 1 ok, -1 unavailable
static bool g_cSeenEv=false, g_cSeenKey[2]={false,false};

// GameplayStatics.GetPlayerPawn / GetPlayerController (world context, player 0): the LOCAL player's, also in a room
static uintptr_t club_gps(uintptr_t fn,uintptr_t ctx){
    static uintptr_t cf[2]={0,0}; static int cW[2],cI[2],cR[2];
    int s=(cf[0]==fn)?0:(cf[1]==fn)?1:-1;
    if(s<0){ s=cf[0]?1:0; cf[s]=fn; cW[s]=prop_offset(fn,"WorldContextObject",0); cI[s]=prop_offset(fn,"PlayerIndex",0); cR[s]=prop_offset(fn,"ReturnValue",0); }
    uint16_t psz=*(uint16_t*)(fn+0xB6); static uint8_t b[64] __attribute__((aligned(16)));
    if(cW[s]<0||cR[s]<0||psz>sizeof b) return 0;
    memset(b,0,psz); memcpy(b+cW[s],&ctx,8); if(cI[s]>=0){ int32_t z=0; memcpy(b+cI[s],&z,4); }
    call_uf(g_cGPS,fn,b); uintptr_t r; memcpy(&r,b+cR[s],8); return r; }
// VROrigin.K2_SetRelativeLocationAndRotation, teleport (no sweep)
static void club_set_rel(const double L[3],const double R[3]){
    static int oL=-2,oR=-1,oS=-1,oT=-1;
    if(oL==-2){ oL=prop_offset(g_cFnSetRel,"NewLocation",0); oR=prop_offset(g_cFnSetRel,"NewRotation",0);
        oS=prop_offset(g_cFnSetRel,"bSweep",0); oT=prop_offset(g_cFnSetRel,"bTeleport",0);
        LOGI("[CLUB] VROrigin setter: parms 0x%x, NewLocation@%d NewRotation@%d bSweep@%d bTeleport@%d",(int)*(uint16_t*)(g_cFnSetRel+0xB6),oL,oR,oS,oT); }
    uint16_t psz=*(uint16_t*)(g_cFnSetRel+0xB6); static uint8_t b[1024] __attribute__((aligned(16)));
    if(oL<0||oR<0||psz>sizeof b) return;
    memset(b,0,psz); memcpy(b+oL,L,24); memcpy(b+oR,R,24); if(oS>=0) b[oS]=0; if(oT>=0) b[oT]=1;
    call_uf(g_cVRO,g_cFnSetRel,b); memcpy(g_cSetLoc,L,24); memcpy(g_cSetRot,R,24); g_cHaveSet=true; }
static void club_restore(const char* why){                     // VROrigin back where Tribe had it
    if(g_cBased&&g_cVRO&&obj_alive(g_cVRO)&&g_cFnSetRel) club_set_rel(g_cBaseLoc,g_cBaseRot);
    if(g_cBased) LOGI("[CLUB] walking off (%s): back where Tribe put you",why);
    g_cBased=false; g_cHaveSet=false; g_cZ=0; }
// the local pawn, its VROrigin and camera (the pawn's properties by name: TribePawnBP_C on 2304, the C++ TribePawn on 2311);
// re-checked every ~2 s, objects checked every frame
static bool club_resolve(){
    bool ok=g_cPawn&&g_cVRO&&g_cCam&&obj_alive(g_cPawn)&&obj_alive(g_cVRO)&&obj_alive(g_cCam)&&(!g_cPC||obj_alive(g_cPC));
    if(ok&&g_cFrame<g_cResolveAt) return true;
    g_cResolveAt=g_cFrame+150;
    uintptr_t ctx=(g_isoActor&&obj_alive(g_isoActor))?g_isoActor:(g_pawn&&obj_alive(g_pawn))?g_pawn:0;
    if(!ctx){ g_cPC=0; return false; }
    uintptr_t pawn=club_gps(g_cFnGetPawn,ctx);
    if(!pawn||!obj_alive(pawn)){ if(g_cBased) club_restore("no local pawn"); g_cPawn=g_cVRO=g_cCam=g_cPC=0; return false; }
    if(pawn!=g_cPawn){
        if(g_cBased) club_restore("Tribe gave you another pawn");        // puts the old VROrigin back if it still exists
        uintptr_t cls=rdptr(pawn+OFF_Class); char cn[96]; obj_name(cls,cn,sizeof cn);
        g_cOffVRO=prop_offset(cls,"VROrigin",0); g_cOffCam=prop_offset(cls,"Camera",0); g_cOffRole=prop_offset(cls,"Role",0);
        g_cOffHost=prop_offset(cls,"bHost",0); g_cOffDJ=prop_offset(cls,"bDJing",0);
        { int S=calib_fprop_size(); uintptr_t f; g_cMaskHost=0xFF; g_cMaskDJ=0xFF;   // mod2311 step C (levels doc S4): as em_actor_hidden,
          if(S>0&&g_cOffHost>=0&&(f=find_prop(cls,"bHost"))){ g_cOffHost+=rd8(f+S+1); g_cMaskHost=rd8(f+S+2); }   // the byte at
          if(S>0&&g_cOffDJ>=0&&(f=find_prop(cls,"bDJing"))){ g_cOffDJ+=rd8(f+S+1); g_cMaskDJ=rd8(f+S+2); } }      // Offset+ByteOffset & ByteMask
        LOGI("[CLUB] local pawn 0x%lx (%s): VROrigin@%d Camera@%d Role@%d bHost@%d bDJing@%d",(unsigned long)pawn,cn,
             g_cOffVRO,g_cOffCam,g_cOffRole,g_cOffHost,g_cOffDJ);
        g_cPawn=pawn; g_cAllowed=-1; }
    g_cPC=g_cFnGetPC?club_gps(g_cFnGetPC,ctx):0; if(g_cPC&&!obj_alive(g_cPC)) g_cPC=0;
    uintptr_t vro=g_cOffVRO>=0?*(uintptr_t*)(pawn+g_cOffVRO):0, cam=g_cOffCam>=0?*(uintptr_t*)(pawn+g_cOffCam):0;
    if(vro!=g_cVRO&&g_cBased) club_restore("VROrigin changed");
    if(vro&&g_cOffRelLoc<0){ uintptr_t sc=rdptr(vro+OFF_Class); g_cOffRelLoc=prop_offset(sc,"RelativeLocation",0); g_cOffRelRot=prop_offset(sc,"RelativeRotation",0); }
    g_cVRO=vro; g_cCam=cam;
    uintptr_t par=0; if(vro&&g_cFnParent&&obj_alive(vro)){ uint8_t* r=call_ret(vro,g_cFnParent,0,0); if(r) memcpy(&par,r,8); }
    if(par&&!obj_alive(par)) par=0;
    if(par!=g_cPar){ char pn[96]="-", pc[96]="-"; if(par){ obj_name(par,pn,sizeof pn); class_name(par,pc,sizeof pc); }
        LOGI("[CLUB] VROrigin hangs on 0x%lx (%s, %s)",(unsigned long)par,pn,pc); }
    g_cPar=par;
    return vro&&cam&&obj_alive(vro)&&obj_alive(cam)&&g_cOffRelLoc>=0&&g_cOffRelRot>=0; }
// the gate's question: the host (or alone: the pawn has authority), Tribe's host flag, or a DJ; club.txt role= overrides
static bool club_allowed(){
    int r=g_clubRole;
    int role=g_cOffRole>=0?*(uint8_t*)(g_cPawn+g_cOffRole):-1, host=g_cOffHost>=0?(*(uint8_t*)(g_cPawn+g_cOffHost)&g_cMaskHost):-1,
        dj=g_cOffDJ>=0?(*(uint8_t*)(g_cPawn+g_cOffDJ)&g_cMaskDJ):-1;
    bool a=(r==1||r==2)?true:(r==3)?false:(role==3||host>0||dj>0);
    if((int)a!=g_cAllowed){ g_cAllowed=a; static const char* const NR[4]={"None","SimulatedProxy","AutonomousProxy","Authority"};
        LOGI("[CLUB] gate: %s (role=%s; pawn Role %d %s, bHost %d, bDJing %d)",a?"OPEN for you":"SHUT for you (guest)",CLUB_ROLES[r],
             role,(role>=0&&role<4)?NR[role]:"?",host,dj); }
    return a; }
// FNames of the eight stick keys, once, through KismetStringLibrary.Conv_StringToName (both key families: Tribe's stick
// mappings may sit on either, and the polling takes whichever moves)
static bool club_keys(){
    if(g_cKeys) return g_cKeys>0;
    static const char* const K[8]={"OculusTouch_Left_Thumbstick_X","OculusTouch_Left_Thumbstick_Y","OculusTouch_Right_Thumbstick_X",
        "OculusTouch_Right_Thumbstick_Y","MotionController_Left_Thumbstick_X","MotionController_Left_Thumbstick_Y",
        "MotionController_Right_Thumbstick_X","MotionController_Right_Thumbstick_Y"};
    int oS=g_cFnToName?prop_offset(g_cFnToName,"InString",0):-1, oR=g_cFnToName?prop_offset(g_cFnToName,"ReturnValue",0):-1;
    g_cOffKey=g_cFnKey?prop_offset(g_cFnKey,"Key",0):-1; g_cOffKeyRet=g_cFnKey?prop_offset(g_cFnKey,"ReturnValue",0):-1;
    uint16_t psz=g_cFnToName?*(uint16_t*)(g_cFnToName+0xB6):0xFFFF;
    if(!g_cKSL||oS<0||oR<0||g_cOffKey<0||g_cOffKeyRet<0||psz>64){ g_cKeys=-1;
        LOGI("[CLUB] key polling unavailable (KismetStringLibrary 0x%lx, InString@%d ReturnValue@%d; Key@%d ReturnValue@%d)",
             (unsigned long)g_cKSL,oS,oR,g_cOffKey,g_cOffKeyRet); return false; }
    static uint16_t w[64]; static uint8_t b[64] __attribute__((aligned(16))); char got[8][40];
    for(int k=0;k<8;k++){ int n=0; for(;K[k][n]&&n<63;n++) w[n]=(uint16_t)K[k][n]; w[n]=0;
        FStr s={w,n+1,n+1}; memset(b,0,psz); memcpy(b+oS,&s,sizeof s); call_uf(g_cKSL,g_cFnToName,b);
        memcpy(g_cKeyN[k],b+oR,8); uint32_t id; memcpy(&id,g_cKeyN[k],4); fname_resolve(id,got[k],sizeof got[k]); }
    g_cKeys=1;
    LOGI("[CLUB] key names: %s %s %s %s | %s %s %s %s (Key@%d ReturnValue@%d)",got[0],got[1],got[2],got[3],got[4],got[5],got[6],got[7],
         g_cOffKey,g_cOffKeyRet);
    return true; }
static float club_key(int k){                                   // PlayerController.GetInputAnalogKeyState(key k)
    uint16_t psz=*(uint16_t*)(g_cFnKey+0xB6); static uint8_t b[64] __attribute__((aligned(16))); if(psz>sizeof b) return 0;
    memset(b,0,psz); memcpy(b+g_cOffKey,g_cKeyN[k],8); call_uf(g_cPC,g_cFnKey,b); float v; memcpy(&v,b+g_cOffKeyRet,4);
    return (v==v&&v>-2.f&&v<2.f)?v:0.f; }
// L X, L Y, R X, R Y: the larger of Tribe's stick events (if they arrived this frame) and the polled keys. The first
// real movement on each source is logged once (probe P2: what carries the sticks in this build).
static void club_sticks(float v[4]){
    float e[4]={0,0,0,0}, k[4]={0,0,0,0}; bool ev=true;
    for(int i=0;i<4;i++) if(!g_cAxFn[i]||g_cFrame-g_cAxFrame[i]>3) ev=false;
    if(ev) for(int i=0;i<4;i++) e[i]=g_cAx[i];
    if(g_cPC&&g_cFnKey&&club_keys()) for(int i=0;i<4;i++){ float a=club_key(i), c=club_key(4+i); k[i]=fabsf(a)>=fabsf(c)?a:c;
        for(int f=0;f<2;f++){ float x=f?c:a; if(!g_cSeenKey[f]&&fabsf(x)>0.3f){ g_cSeenKey[f]=true;
            LOGI("[CLUB] probe P2: the %s_* keys carry the sticks (axis %d = %.2f)",f?"MotionController":"OculusTouch",i,x); } } }
    if(ev&&!g_cSeenEv&&(fabsf(e[0])>0.3f||fabsf(e[1])>0.3f||fabsf(e[2])>0.3f||fabsf(e[3])>0.3f)){ g_cSeenEv=true;
        LOGI("[CLUB] probe P2: Tribe's stick events carry the sticks (L %.2f %.2f, R %.2f %.2f) on pawn 0x%lx (%s the local pawn)",
             e[0],e[1],e[2],e[3],(unsigned long)g_cAxSelf,g_cAxSelf==g_cPawn?"=":"NOT"); }
    for(int i=0;i<4;i++) v[i]=fabsf(e[i])>=fabsf(k[i])?e[i]:k[i]; }
#ifdef HAVE_SHOW_BUS
// the crowd makes way (the club's crowd material pushes each dancer from this point): your head's XY into MPC_ClubShow
// through the Dino session's show bus (dumper.cpp show_key / show_set; keys looked up again whenever g_showGen moves)
static uint64_t g_cKeyPX=0, g_cKeyPY=0; static int g_cShowGen=-1;
static void club_show_player(const double H[3]){
    if(g_cShowGen!=g_showGen){ g_cShowGen=g_showGen; g_cKeyPX=show_key("PlayerX"); g_cKeyPY=show_key("PlayerY");
        LOGI("[CLUB] crowd make-way: PlayerX %s, PlayerY %s in the show collection",g_cKeyPX?"found":"MISSING",g_cKeyPY?"found":"MISSING"); }
    if(g_cKeyPX) show_set(g_cKeyPX,(float)H[0]);
    if(g_cKeyPY) show_set(g_cKeyPY,(float)H[1]); }
// the dark club's dimmers from club.txt, every frame while the club is up (walking or not), like the show bus's own writes
static uint64_t g_cKeyDim[4]; static int g_cDimGen=-1;
static void club_show_dims(){
    bool any=false; for(int i=0;i<4;i++) any|=g_clubDim[i]>=0.0;
    if(!any) return;
    if(g_cDimGen!=g_showGen){ g_cDimGen=g_showGen; int n=0; for(int i=0;i<4;i++){ g_cKeyDim[i]=show_key(CLUB_DIMS[i]); n+=g_cKeyDim[i]!=0; }
        LOGI("[CLUB] dimmers: %d of 4 in the show collection%s",n,n<4?" (a pak before v6 has none)":""); }
    for(int i=0;i<4;i++){ double v=g_clubDim[i]; if(v>=0.0&&g_cKeyDim[i]) show_set(g_cKeyDim[i],(float)v); } }
#endif
// move VROrigin in world space: shift by (tX, tY), then turn `turn` deg about (qx, qy); its height comes from the floor
// you stand on (g_cZ, eased). pyaw = the parent's world yaw: world deltas go into the parent's frame.
static void club_apply(const double O[3],const double RL[3],const double RR[3],double pyaw,double tX,double tY,double turn,double qx,double qy){
    double ox=O[0]+tX, oy=O[1]+tY;
    if(turn!=0.0){ double a=turn*M_PI/180.0, ca=cos(a), sa=sin(a), vx=ox-qx, vy=oy-qy; ox=qx+ca*vx-sa*vy; oy=qy+sa*vx+ca*vy; }
    double DX=ox-O[0], DY=oy-O[1], pr=-pyaw*M_PI/180.0, c=cos(pr), s=sin(pr), k=1.0/g_cScale;
    double L[3]={RL[0]+(c*DX-s*DY)*k,RL[1]+(s*DX+c*DY)*k,g_cBaseLoc[2]+g_cZ*k}, R[3]={RR[0],wrap180(RR[1]+turn),RR[2]};
    if(fabs(L[0]-RL[0])>0.001||fabs(L[1]-RL[1])>0.001||fabs(L[2]-RL[2])>0.001||R[1]!=RR[1]) club_set_rel(L,R); }

// ---- the side screens show what Tribe shows on the main screen (2026-10-16; the user: "I dont see anything on the
// screens left and right of the main screens"). Tribe draws its visuals on our SM_DinoVisualScreen (dumper's
// em_register_backdrop makes it Tribe's backdrop). SM_ClubSideScreens has the same UV0 layout (club_stage.py
// screen_quad), so the same material maps the video the same way, and MPC_VideoBackdrop's fill covers both. While Tribe
// hides its backdrop (visuals off) the side screens go back to their idle panels. Only on the club's map and MIDTOWN's
// (the Christmas session's billboards: one actor whose mesh is named SM_ClubSideScreens, UV0 in the main screen's layout).
static uintptr_t g_csSide=0, g_csComp=0, g_csMainComp=0, g_csIdle=0, g_csShown=0, g_csFnGet=0, g_csFnSet=0, g_csMain=0;
static long g_csNext=0; static int g_csSearches=0, g_csWait=0;
static uintptr_t club_mesh_comp(uintptr_t a){                     // a StaticMeshActor's StaticMeshComponent
    if(!a||!obj_alive(a)) return 0; int o=prop_offset(rdptr(a+OFF_Class),"StaticMeshComponent",0); if(o<0) return 0;
    uintptr_t c=rdptr(a+o); return (c&&obj_alive(c))?c:0; }
static uintptr_t club_get_mat(uintptr_t comp){                    // its material 0
    uint16_t psz=rd16(g_csFnGet+0xB6); static uint8_t b[32] __attribute__((aligned(8)));
    int oR=prop_offset(g_csFnGet,"ReturnValue",0); if(oR<0||psz>sizeof b) return 0;
    memset(b,0,psz); call_uf(comp,g_csFnGet,b); uintptr_t m; memcpy(&m,b+oR,8); return m; }
static void club_set_mat(uintptr_t comp,uintptr_t m){             // SetMaterial(0, m)
    uint16_t psz=rd16(g_csFnSet+0xB6); static uint8_t b[32] __attribute__((aligned(8)));
    int oM=prop_offset(g_csFnSet,"Material",0); if(oM<0||psz>sizeof b) return;
    memset(b,0,psz); memcpy(b+oM,&m,8); call_uf(comp,g_csFnSet,b); }
static void club_side_screens(){                                  // GAME thread, from club_tick while a walking stage is up
    if(g_cFrame<g_csNext) return; g_csNext=g_cFrame+30;           // ~0.4 s
    if(strcmp(g_clubMapName,"club_collide.txt")&&strcmp(g_clubMapName,"christmas_collide.txt")) return;   // the stages with
                                                                  // side screens: the club, MIDTOWN's billboards (2026-10-17)
    uintptr_t main=g_emOurScreen; if(!main||!obj_alive(main)) return;          // Tribe's backdrop isn't ours yet
    if(main!=g_csMain){ g_csMain=main; g_csSide=0; g_csSearches=0; g_csWait=0; }   // (re)loaded: look again
    if(!g_csFnGet){ g_csFnGet=find_by_path("/Script/Engine.PrimitiveComponent.GetMaterial",0);
                    g_csFnSet=find_by_path("/Script/Engine.PrimitiveComponent.SetMaterial",0); }
    if(!g_csFnGet||!g_csFnSet) return;
    if(!g_csSide||!obj_alive(g_csSide)||!obj_alive(g_csComp)||!obj_alive(g_csMainComp)){
        g_csSide=0; if(g_csSearches>=5||(g_csWait++%5)!=0) return;      // a full object walk: every ~2 s, 5 times at most
        g_csSearches++;
        uintptr_t a=em_find_mesh_actor("SM_ClubSideScreens"), c=club_mesh_comp(a), mc=club_mesh_comp(main);
        if(!c||!mc){ if(g_csSearches==5) LOGI("[CLUB] side screens: not found (a pak before v9?): left as they are"); return; }
        g_csSide=a; g_csComp=c; g_csMainComp=mc; g_csIdle=club_get_mat(c); g_csShown=g_csIdle;
        LOGI("[CLUB] side screens: found (actor 0x%lx); they mirror the main screen",(unsigned long)a); }
    uintptr_t want=g_csIdle; bool video=false;
    if(em_actor_hidden(main)!=1){ uintptr_t m=club_get_mat(g_csMainComp); if(m&&obj_alive(m)){ want=m; video=true; } }
    if(want==g_csShown||!want) return;
    club_set_mat(g_csComp,want); g_csShown=want;
    char mn[96]="?"; obj_name(want,mn,sizeof mn);
    LOGI("[CLUB] side screens: %s (%s)",video?"mirroring the main screen":"visuals off: idle panels",mn); }

static void club_tick(float dt){                                // GAME thread, every frame (our actor's tick, after giant_tick)
    g_cFrame++;
    int mi=g_clubMapIdx;
#ifdef HAVE_SHOW_BUS
    if(g_clubOn&&g_emState==EM_ACTIVE&&g_emActive==g_clubOnIdx) club_show_dims();
#endif
    if(g_clubOn&&g_emState==EM_ACTIVE&&g_emActive==g_clubOnIdx) club_side_screens();
    if(!(g_clubOn&&g_emState==EM_ACTIVE&&g_emActive==g_clubOnIdx&&mi>=0&&g_clubWalk)){   // the map's own stage only
        if(g_cBased) club_restore(g_clubWalk?"the club is not up":"walk=0 in club.txt");
        g_cGiveUp=false; g_cIgnoreParent=false; g_cParentMoves=0; g_cVroMoves=0; return; }
    if(g_cGiveUp||!(dt>0.f&&dt<0.25f)||!club_resolve()) return;
    const CCMap* m=&g_clubMap[mi];
    double H[3],HR[3],O[3],OR_[3],RL[3],RR[3];
    if(!get_vec3(g_cCam,g_cFnLoc,H)||!get_vec3(g_cCam,g_cFnRot,HR)||!get_vec3(g_cVRO,g_cFnLoc,O)||!get_vec3(g_cVRO,g_cFnRot,OR_)) return;
    memcpy(RL,(const void*)(g_cVRO+g_cOffRelLoc),24); memcpy(RR,(const void*)(g_cVRO+g_cOffRelRot),24);
#ifdef HAVE_SHOW_BUS
    club_show_player(H);
#endif
    bool allowed=club_allowed();
    double P[3], PR[3]={0,0,0}, pyaw;                            // the parent's world pose (only its yaw turns our moves)
    if(g_cPar&&get_vec3(g_cPar,g_cFnLoc,P)&&get_vec3(g_cPar,g_cFnRot,PR)) pyaw=wrap180(PR[1]);
    else { pyaw=wrap180(OR_[1]-RR[1]); double pr=pyaw*M_PI/180.0, pc=cos(pr), ps=sin(pr);       // no parent: infer it
           P[0]=O[0]-(pc*RL[0]-ps*RL[1]); P[1]=O[1]-(ps*RL[0]+pc*RL[1]); P[2]=O[2]-RL[2]; }
    if(g_walkPause){                                             // something else moves VROrigin now: follow, never write
        memcpy(g_cSetLoc,RL,24); memcpy(g_cSetRot,RR,24); g_cHaveSet=g_cBased; memcpy(g_cParent,P,24); g_cParent[3]=pyaw;
        if(!g_cPaused){ g_cPaused=true; LOGI("[CLUB] walking paused (another feature moves VROrigin)"); } return; }
    if(g_cPaused){ g_cPaused=false; if(g_cBased) g_cBaseLoc[2]=RL[2]-g_cZ/g_cScale; LOGI("[CLUB] walking resumes"); }
    if(!g_cBased){                                               // first frame: remember where Tribe put you
        memcpy(g_cBaseLoc,RL,24); memcpy(g_cBaseRot,RR,24); g_cBased=true; g_cHaveSet=false; g_cZ=0;
        double S[3]; g_cScale=1.0;
        if(g_cPar&&g_cFnScale&&get_vec3(g_cPar,g_cFnScale,S)&&S[0]>0.05&&S[0]<20.0) g_cScale=S[0];
        if(fabs(PR[0])>0.5||fabs(PR[2])>0.5||fabs(g_cScale-1.0)>0.01)
            LOGI("[CLUB] note: VROrigin's parent has pitch %.1f roll %.1f scale %.3f (walking assumes a level parent)",PR[0],PR[2],g_cScale);
        double f; g_cCur=cc_floor_at(m,H[0],H[1],0.0,&f)?f:0.0; g_cBaseFloor=g_cCur;
        memcpy(g_cParent,P,24); g_cParent[3]=pyaw; g_cTurnArmed=true; g_cBackHeld=0; g_cMoved=0; g_cLogT=0; g_cOnFrame=g_cFrame;
        const CCSpot* dk=cc_spot(m,"decks"); g_cHaveStage=false;
        if(dk) for(int i=0;i<m->nf;i++){ const CCFloor* fl=&m->f[i];
            if(dk->x>=fl->x0&&dk->x<=fl->x1&&dk->y>=fl->y0&&dk->y<=fl->y1&&fabs(fl->top-dk->z)<1.0){
                g_cStage[0]=fl->x0; g_cStage[1]=fl->y0; g_cStage[2]=fl->x1; g_cStage[3]=fl->y1; g_cStage[4]=fl->top; g_cHaveStage=true; break; } }
        LOGI("[CLUB] walking on. head (%.0f, %.0f, %.0f) yaw %.1f, floor %.0f | VROrigin rel (%.0f, %.0f, %.0f) yaw %.1f, world (%.0f, %.0f, %.0f) "
             "pitch %.1f yaw %.1f roll %.1f | parent (%.0f, %.0f, %.0f) yaw %.1f | stage rect %s",H[0],H[1],H[2],HR[1],g_cCur,RL[0],RL[1],RL[2],
             RR[1],O[0],O[1],O[2],OR_[0],OR_[1],OR_[2],P[0],P[1],P[2],pyaw,g_cHaveStage?"found":"MISSING (spot decks)");
        return; }
    // Tribe moved VROrigin itself (a recentre) or the rig it hangs on (DJ mode): start over from where it put you
    if(g_cHaveSet&&(fabs(RL[0]-g_cSetLoc[0])>1.0||fabs(RL[1]-g_cSetLoc[1])>1.0||fabs(RL[2]-g_cSetLoc[2])>1.0||fabs(wrap180(RR[1]-g_cSetRot[1]))>0.5)){
        if(fabs(RL[0]-g_cSetLoc[0])<=1.0&&fabs(RL[1]-g_cSetLoc[1])<=1.0&&fabs(wrap180(RR[1]-g_cSetRot[1]))<=0.5){
            // height only (2026-10-09 test: Tribe lowered VROrigin 17 cm as it raised the rig 17 cm): keep your place
            g_cHeightN++; if(g_cFrame-g_cHeightLogF>360){ g_cHeightLogF=g_cFrame;
                LOGI("[CLUB] Tribe set VROrigin's height (%+.0f cm; %d such in the last 5 s): kept your place",RL[2]-g_cSetLoc[2],g_cHeightN); g_cHeightN=0; }
            g_cBaseLoc[2]+=RL[2]-g_cSetLoc[2]; g_cSetLoc[2]=RL[2]; }
        else {
            LOGI("[CLUB] Tribe moved VROrigin: rel (%.0f, %.0f, %.0f) yaw %.1f, we had (%.0f, %.0f, %.0f) yaw %.1f: walking starts over from there",
                 RL[0],RL[1],RL[2],RR[1],g_cSetLoc[0],g_cSetLoc[1],g_cSetLoc[2],g_cSetRot[1]);
            memcpy(g_cBaseLoc,RL,24); memcpy(g_cBaseRot,RR,24); g_cHaveSet=false; g_cZ=0; g_cRefloor=true;
            if(++g_cVroMoves>=4){ g_cGiveUp=true; g_cBased=false;
                LOGI("[CLUB] Tribe keeps moving VROrigin itself: walking stands down until the club is loaded again"); return; } } }
    g_cParentT+=dt; if(g_cParentT>10.0){ g_cParentT=0; g_cParentMoves=0; g_cVroMoves=0; }
    if(!g_cIgnoreParent&&hypot(P[0]-g_cParent[0],P[1]-g_cParent[1])<=5.0&&fabs(wrap180(pyaw-g_cParent[3]))<=1.0&&fabs(P[2]-g_cParent[2])>5.0)
        LOGI("[CLUB] Tribe raised your rig %+.0f cm (height only): kept your place",P[2]-g_cParent[2]);
    else if(!g_cIgnoreParent&&(hypot(P[0]-g_cParent[0],P[1]-g_cParent[1])>5.0||fabs(wrap180(pyaw-g_cParent[3]))>1.0)){
        LOGI("[CLUB] Tribe moved your rig: (%.0f, %.0f, %.0f) yaw %.1f -> (%.0f, %.0f, %.0f) yaw %.1f: back where it put you",g_cParent[0],
             g_cParent[1],g_cParent[2],g_cParent[3],P[0],P[1],P[2],pyaw);
        memcpy(g_cParent,P,24); g_cParent[3]=pyaw;
        if(++g_cParentMoves>=4){ g_cIgnoreParent=true; LOGI("[CLUB] the rig keeps moving: walking stays relative to it from now on"); }
        g_cZ=0; g_cRefloor=true; club_set_rel(g_cBaseLoc,g_cBaseRot); return; }
    memcpy(g_cParent,P,24); g_cParent[3]=pyaw;
    if(g_cRefloor){ double f; g_cCur=cc_floor_at(m,H[0],H[1],g_cCur,&f)?f:cc_floor_at(m,H[0],H[1],0.0,&f)?f:0.0;   // where you now stand
        g_cBaseFloor=g_cCur; g_cRefloor=false; }
    { double f; if(cc_floor_at(m,H[0],H[1],g_cCur,&f)) g_cCur=f; }      // room-scale: the floor follows your head
    float st[4]; club_sticks(st);
    // a guest on the stage (Tribe's guest spawn, or a DJ role taken away) goes to the floor outside the door
    const CCSpot* gs=cc_spot(m,"guest_floor");
    bool onStage=g_cHaveStage&&fabs(g_cCur-g_cStage[4])<1.0&&H[0]>=g_cStage[0]&&H[0]<=g_cStage[2]&&H[1]>=g_cStage[1]&&H[1]<=g_cStage[3];
    bool back=false;
    if(st[3]<-0.8f){ g_cBackHeld+=dt; back=(g_cBackHeld>=1.0&&g_cBackHeld-dt<1.0); } else g_cBackHeld=0;
    if(gs&&!allowed&&((onStage&&g_cFrame-g_cGuestMoved>144)||back)){
        g_cGuestMoved=g_cFrame; g_cCur=gs->z; g_cZ=g_cCur-g_cBaseFloor;
        club_apply(O,RL,RR,pyaw,gs->x-H[0],gs->y-H[1],wrap180(gs->yaw-HR[1]),gs->x,gs->y);
        LOGI("[CLUB] %s: to the floor outside the airlock (%.0f, %.0f)",back?"back (guest)":"a guest on the stage",gs->x,gs->y); return; }
    if(back){ g_cZ=0; g_cCur=g_cBaseFloor; club_set_rel(g_cBaseLoc,g_cBaseRot); LOGI("[CLUB] back where Tribe put you"); return; }
    // the left stick: walk where you look; the move is checked against the walls, floors and the gate
    double tX=0,tY=0, lx=st[0], ly=st[1], mag=hypot(lx,ly);
    if(mag>g_clubDead){
        double k=fmin(1.0,(mag-g_clubDead)/(1.0-g_clubDead))/mag, v=g_clubSpeed*dt, hy=HR[1]*M_PI/180.0, fx=cos(hy), fy=sin(hy), nf; int hit;
        double dX=(fx*ly-fy*lx)*k*v, dY=(fy*ly+fx*lx)*k*v;
        // the crowd is soft (the user, 2026-10-09: "i can barely get in the crowd"): near people you slow down and drift
        // round them; head-on, you pass on the side away from the nearest one. Only their spines' cores are solid.
        double cx,cy,nx,ny, dens=cc_crowd(m,H[0],H[1],g_cCur,&cx,&cy,&nx,&ny), ml=hypot(dX,dY);
        if(dens>0.0&&ml>1e-6){
            double ux=dX/ml, uy=dY/ml, f=fmax(0.45,1.0-0.35*dens), along=cx*ux+cy*uy, sx=cx-along*ux, sy=cy-along*uy, sl=hypot(sx,sy);
            if(sl<0.15&&(nx!=0.0||ny!=0.0)){ double side=(ux*ny-uy*nx)>0?-1.0:1.0; sx=-uy*side; sy=ux*side; sl=1.0; }
            dX*=f; dY*=f;
            if(sl>1e-6){ double g=fmin(1.0,sl)*0.7*ml*f; dX+=sx/sl*g; dY+=sy/sl*g; } }
        if(cc_move(m,H[0],H[1],dX,dY,g_cCur,allowed,&tX,&tY,&nf,&hit)) g_cCur=nf;
        g_cMoved+=hypot(tX,tY);
        g_cRefuseT-=dt;
        if(cc_is_gate(m,hit)&&!allowed&&g_cRefuseT<=0){ g_cRefuseT=3.0; LOGI("[CLUB] gate: refused (guests can walk out, not in)"); } }
    // the right stick: 30 deg turns about your head, re-armed at the centre
    double turn=0;
    if(g_cTurnArmed&&fabsf(st[2])>0.7f){ turn=st[2]>0?g_clubTurn:-g_clubTurn; g_cTurnArmed=false; }
    else if(fabsf(st[2])<0.3f) g_cTurnArmed=true;
    double zt=g_cCur-g_cBaseFloor; g_cZ+=(zt-g_cZ)*(1.0-exp(-dt/0.08)); if(fabs(zt-g_cZ)<0.05) g_cZ=zt;   // stairs: eased
    club_apply(O,RL,RR,pyaw,tX,tY,turn,H[0]+tX,H[1]+tY);
    g_cLogT+=dt;
    if(g_cLogT>=10.0){ if(g_cMoved>50.0) LOGI("[CLUB] head (%.0f, %.0f, %.0f) on floor %.0f, walked %.1f m in 10 s (%s)",H[0],H[1],H[2],g_cCur,
                                                g_cMoved/100.0,allowed?"may pass the gate":"guest");
        g_cLogT=0; g_cMoved=0; } }
