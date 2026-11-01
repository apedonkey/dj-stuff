#!/usr/bin/env python3
"""Step A edit: the supervisor (poll thread), the [READY] line + ready.txt + ready_history.txt, the constructor-time
ProcessEvent hook, the stage auto-apply state machine, ini_upsert's readability guard (exact-string edits)."""
import sys

p = sys.argv[1]
s = open(p, encoding="utf-8", newline="").read()


def rep(old, new, cnt=1):
    global s
    n = s.count(old)
    assert n == cnt, (n, old[:100])
    s = s.replace(old, new)


# ---------------------------------------------------------------- ini_upsert: nothing when tribemod isn't readable yet
rep('''static void ini_upsert(){
    char url[1024], etag[256]; bool hu=read_trim_file("avatar_url.txt",url,sizeof url);''',
    '''static int tribemod_state();                       // (with the hook install, below)
static void ini_upsert(){
    // mod2311: when tribemod/ can't be read yet (the first launch after an install), every file reads as absent and the
    // edits below would delete keys (the RPM URL, body tracking). Leave both ini files as they are then.
    if(tribemod_state()<0){ LOGI("[INI] tribemod/ is not readable yet: both ini files left as they are this launch"); return; }
    char url[1024], etag[256]; bool hu=read_trim_file("avatar_url.txt",url,sizeof url);''')

# ---------------------------------------------------------------- ensure_resolved: quieter failures
rep('''    if(!(P_ga && try_objarray(g_base+P_ga))){ if(!scan_objarray()){ load_status("resolve: objarray FAIL"); return; } }''',
    '''    if(!(P_ga && try_objarray(g_base+P_ga))){ if(!scan_objarray()){ static int nf=0; if((nf++%15)==0) load_status("resolve: objarray FAIL (try %d)",nf); return; } }''')

# ---------------------------------------------------------------- the stage auto-apply state machine (env_menu_poll)
rep('''    if(!autoDone&&g_envMenuOn&&g_emGameState&&(cur>0||g_emEnvOff<0)&&settle>=4&&g_emState==EM_IDLE){
        autoDone=true; char saved[64];
        if(read_trim_file("active_env.txt",saved,sizeof saved)){ int n=g_emCount;
            for(int i=0;i<n;i++) if(!strcmp(saved,g_emLabels[i])){ g_emReq=i; LOGI("[ENV] auto: re-applying '%s' (Tribe settled on %d %s)",saved,cur,em_env_name(cur)); break; } } }''',
    '''    // the stage you picked last (mod2311, notes 9 + 18): a mod stage's label is loaded once Tribe's own environment has
    // held still (~8 s; the world is needed, our avatar is not); "stock:<name>" is Tribe's to restore. A failed load (or
    // our level going away) is tried again 15 s later, 3 more times; nothing here deletes active_env.txt.
    { static char lastWant[64]="\\x01"; static double nextAt=0;
      char want[64]=""; bool have=read_trim_file("active_env.txt",want,sizeof want);
      int wi=-1; if(have) for(int i=0;i<g_emCount;i++) if(!strcmp(want,g_emLabels[i])){ wi=i; break; }
      if(strcmp(want,lastWant)){ snprintf(lastWant,sizeof lastWant,"%s",want); g_stgTries=0; g_stgGaveUp=false; nextAt=0; }   // a new pick
      snprintf(g_stgWant,sizeof g_stgWant,"%s",want); g_stgWantIdx=wi; g_stgSettle=settle;
      if(g_emFailed){ g_emFailed=0;
          if(g_stgTries>=4){ if(!g_stgGaveUp){ g_stgGaveUp=true; LOGI("[ENV] auto: '%s' failed %d times: giving up this launch",want,g_stgTries); } }
          else { nextAt=mono_now()+15.0; LOGI("[ENV] auto: the load did not hold; trying again in 15 s (%d of 4 tries used)",g_stgTries); } }
      if(g_emState==EM_ACTIVE&&g_emActive==wi&&wi>=0) g_stgTries=0;                      // in: a later loss gets fresh tries
      if(wi>=0&&!g_stgGaveUp&&!g_emTribeSwitched&&g_emState==EM_IDLE&&g_emReq<0&&g_envMenuOn&&g_emGameState&&(cur>0||g_emEnvOff<0)
         &&settle>=4&&mono_now()>=nextAt&&g_stgTries<4){
          g_stgTries++; nextAt=mono_now()+60.0; g_emReq=wi;
          LOGI("[ENV] auto: applying '%s' (try %d; Tribe settled on %d %s)",want,g_stgTries,cur,em_env_name(cur)); } }''')
rep('''    static int tick=0, settle=0, lastEnv=-2; static bool autoDone=false; tick++;''',
    '''    static int tick=0, settle=0, lastEnv=-2; tick++;''')
rep('''    { static int ad=0; if(++ad==200) LOGI("[ENV] auto-apply state: autoDone=%d envMenuOn=%d gameState=%d cur=%d settle=%d emState=%d envOff=%d",
        (int)autoDone,(int)g_envMenuOn,(int)g_emGameState,cur,settle,(int)g_emState,(int)g_emEnvOff); }
''', '')
rep('''static void env_menu_poll(){
    bool on=file_present("env_menu");''',
    '''static int g_stgTries=0, g_stgWantIdx=-1, g_stgSettle=0; static bool g_stgGaveUp=false; static char g_stgWant[64]="";   // [READY]
static void env_menu_poll(){
    bool on=file_present("env_menu");''')

# ---------------------------------------------------------------- skin_menu_poll: nothing before the object array
rep('''    bool on=file_present("skin_menu");
    if(!on){ if(g_skinMenuOn){ g_skinMenuOn=0; LOGI("[MENU] OFF"); } return; }
    static int tick=0; tick++;
    menu_resolve_engine_fns();''',
    '''    bool on=file_present("skin_menu");
    if(!on){ if(g_skinMenuOn){ g_skinMenuOn=0; LOGI("[MENU] OFF"); } return; }
    if(!g_resolved) return;                              // mod2311: the lookups need the object array (all 0 before it)
    static int tick=0; tick++;
    menu_resolve_engine_fns();''')

# ---------------------------------------------------------------- the supervisor + [READY], before dump_thread
SUP = r'''// ===================== the supervisor (mod2311; claudedocs/mod_2311_plan.md section 2) =====================
// Runs on the poll thread every 0.5 s: the mod switching on, the object array, the world, the character; the stage is in
// env_menu_poll. Every part waits for exactly what it needs, retries with a limit, and logs one line when it changes.
// The [READY] line sums them up (logcat, tribemod/ready.txt, one result line per launch in tribemod/ready_history.txt).
static int g_hookState=0;                            // 1 hooked + verified, 2 hooked, mod asleep until tribemod is readable,
static char g_hookWhy[120]="not tried";              // 3 safe mode (executor_on absent), -1 failed (g_hookWhy)
static double g_t0=0;                                // when the constructor ran (CLOCK_MONOTONIC)
static volatile sig_atomic_t g_worldUp=0; static double g_worldUpAt=-1;
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
    struct stat st; if(stat(p,&st)==0&&st.st_size>48*1024){ FILE* f=fopen(p,"r");
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
    char menus[80]; bool envOn=file_present("env_menu");
    if(!envOn) snprintf(menus,sizeof menus,"env:off");
    else if(!g_emListLive) snprintf(menus,sizeof menus,"env:list-not-open");
    else { snprintf(menus,sizeof menus,"env%d/%d",(int)g_emAdded,(int)g_emCount); need(g_emAdded>=g_emCount,"menus",menus); }
    char line[1200];
    int k=snprintf(line,sizeof line,"[READY] %s step=%s t=%.1fs hook=%s world=%d avatar=%s skin=%s stage=%s stream=%s menus=%s gen=%d skips=%ld",
        all?"all=1":(t>=180.0?"FAIL":"all=0"),MOD2311_STEP,t,hook,(int)g_worldUp,av,skin,stg,strm,menus,(int)g_worldGen,g_callSkips);
    if(!all&&k>0&&k<(int)sizeof line) snprintf(line+k,sizeof line-k," missing=%s",miss);
    bool changed=(int)all!=lastAll; lastAll=all;
    if(changed||now>=nextAt){ LOGI("%s",line); char l2[1210]; snprintf(l2,sizeof l2,"%s\n",line); ready_write_file("ready.txt",l2,false);
        nextAt=now+((all||t>=180.0)?60.0:2.0); }
    if(all&&!done){ done=true; char h[600]; snprintf(h,sizeof h,"READY t=%.1f skin=%s stage=%s",t,skin,stg); ready_history(h); load_status("%s",line); }
    if(!all&&!done&&!failed&&t>=180.0){ failed=true; char h[700]; snprintf(h,sizeof h,"FAIL t=%.1f missing=%s",t,miss); ready_history(h); load_status("%s",line); } }
'''
rep('''static void* dump_thread(void*){''', SUP + '''static void* dump_thread(void*){''')

# ---------------------------------------------------------------- dump_thread: the supervisor replaces the old blocks
rep('''    bool auto_done=false; int tick=0;
    for(;;){ g_log_pe = file_present("log_pe")?1:0;               // toggle the ProcessEvent diagnostic''',
    '''    for(;;){ modon_poll();                                        // mod2311: the supervisor (see above)
        { static int rk=0; if(!g_resolved&&g_mod_on&&(rk++%4)==0) ensure_resolved(); }   // the object array, every 2 s until found
        world_poll(); avatar_poll(); ready_poll();
        g_log_pe = file_present("log_pe")?1:0;                   // toggle the ProcessEvent diagnostic''')
rep('''        // AUTO-load once per launch: when tribemod/auto_load exists, wait for the live pawn body, then arm.
        // Checked every ~2s; the heavy find_live scan runs on THIS background thread, not the game thread.
        if(!auto_done && orig_pe && ((++tick & 3)==0) && file_present("auto_load")){
            ensure_resolved();
            if(g_resolved){ refresh_numelements(); uintptr_t body=find_live("AvatarBodyMesh","SkeletalMeshComponent","ReadyPlayerMeComponent");
                if(body){ g_load_req=1; auto_done=true; load_status("auto-load: pawn ready (body=0x%lx numel=%u) -> armed",(unsigned long)body,g_numElements); } } }
''', '''        // (the auto-load and the avatar actor's spawn are avatar_poll's now, with retries; mod2311)
''')
rep('''        // AUTO avatar actor: once per launch, ~2 s after the mesh loads, if tribemod/auto_actor exists -> spawn + follow.
        { static int aa=-1; if(aa==-1 && g_loaded_once && g_mymesh && !g_isoActor && file_present("auto_actor")) aa=4;
          if(aa>0 && --aa==0){ g_iso_req=1; load_status("auto_actor: spawning our following avatar"); } }
        // no avatar actor ~90 s after the engine resolved: the pawn's tick drives the per-frame work (fallback_wire);
        // tried again every 30 s until a pawn is found, and again if that pawn goes away (a level change)
        { static int fb=-1, said=0; if(fb==-1 && g_resolved && orig_pe) fb=180;
          if(!g_isoActor && g_fallbackTicker && !obj_alive(g_fallbackTicker)){ g_fallbackTicker=0; fb=2; }
          if(fb>0 && --fb==0 && !g_isoActor && !g_fallbackTicker){ g_fb_req=1; fb=60;
              if(!said++) load_status("no avatar actor 90 s after resolve: arming the pawn's tick for the stream, camera and stage"); } }
''', '')
rep('''          if(bt==-1 && orig_pe && (g_loaded_once||auto_done) && file_present("body_tracking")) bt=6;''',
    '''          if(bt==-1 && orig_pe && g_loaded_once && file_present("body_tracking")) bt=6;''')
rep('''            ensure_resolved(); if(g_resolved && orig_pe){ g_load_req=1; load_status("armed; waiting for next ProcessEvent on game thread"); }''',
    '''            ensure_resolved(); if(g_resolved && orig_pe && g_mod_on){ g_load_req=1; load_status("armed; waiting for next ProcessEvent on game thread"); }''')

# ---------------------------------------------------------------- the constructor: the hook first, verified
i = s.index('''// Phase 3 helper: one attempt to install the ProcessEvent hook (safe: only with tribemod/executor_on present).''')
s = s[:i] + r'''// ---- the ProcessEvent hook, installed once, in the library constructor (mod2311; claudedocs/mod_2311_load.md 3.1) ----
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
    for(int k=1;k<=5;k++){
        if(!maps_rx(pe,20)){ snprintf(g_hookWhy,sizeof g_hookWhy,"ProcessEvent's code @%p is not mapped r-x",(void*)pe); usleep(20*1000); continue; }
        uint32_t w0=*(const volatile uint32_t*)pe;
        if(w0!=0xA9BA7BFDu){ snprintf(g_hookWhy,sizeof g_hookWhy,"first word 0x%08x @%p is not ProcessEvent's stp x29,x30,[sp,#-0x60]!",w0,(void*)pe); break; }
        g_pe_addr=(void*)pe; A64HookFunction(g_pe_addr,(void*)repl_pe,(void**)&orig_pe);
        if(orig_pe&&pe_patch_ok(pe)){ g_hookState=(ts==1)?1:2; snprintf(g_hookWhy,sizeof g_hookWhy,"%s",ts==1?"ok":"tribemod not readable yet");
            const volatile uint32_t* w=(const volatile uint32_t*)pe;
            LOGI("[HOOK] ProcessEvent hooked @%p verified (try %d; words %08x %08x %08x; trampoline %p)%s",(void*)pe,k,w[0],w[1],w[2],(void*)orig_pe,
                 ts==1?"":": pass-through until tribemod/ can be read");
            return; }
        const volatile uint32_t* w=(const volatile uint32_t*)pe;
        snprintf(g_hookWhy,sizeof g_hookWhy,"the patch did not verify (words %08x %08x %08x, trampoline %p)",w[0],w[1],w[2],(void*)orig_pe);
        if(w[0]!=0xA9BA7BFDu) break;                                    // something was written: never patch a second time
        orig_pe=0; usleep(20*1000); }
    if(g_hookState!=1&&g_hookState!=2){ orig_pe=0; g_hookState=-1; }
    LOGI("[HOOK] FAILED: %s; the mod stays off this launch",g_hookWhy); }

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
'''
open(p, "w", encoding="utf-8", newline="").write(s)
print("ok")
