#!/usr/bin/env python3
"""Step A edit: repl_pe (pass-through gate, game thread only, driver once the world is up, world reset) and intro's
show-bus check (exact-string edits)."""
import sys

src = sys.argv[1]
p = src + "/dumper.cpp"
s = open(p, encoding="utf-8", newline="").read()


def rep(old, new, cnt=1):
    global s
    n = s.count(old)
    assert n == cnt, (n, old[:90])
    s = s.replace(old, new)


rep('''extern "C" void repl_pe(void* self,void* func,void* parms){
    { static double lastRun=0; g_pe_n++; struct timespec pts; clock_gettime(CLOCK_MONOTONIC,&pts); double pnow=pts.tv_sec+pts.tv_nsec*1e-9;
      if(g_isoActor && (lastRun==0 || pnow-lastRun>=0.016) && ue_enter()){
          float pdt=(lastRun==0)?0.016f:(float)(pnow-lastRun); if(pdt>0.25f) pdt=0.25f; lastRun=pnow; g_pe_drv++;
          giant_tick(pdt); club_tick(pdt); intro_tick(pdt); camview_tick(pdt); stream_tick(pdt); freeze_beat(); follow_update(pdt); bt_frame(pdt); drone_update(pdt); head_tick(pdt); menu_tick(); env_menu_tick(); perf_frame(pdt); ue_leave(); } }''',
    '''// ---- the ProcessEvent hook (mod2311) ----
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
static void world_reset_game(){
    g_worldSeen=g_worldGen;
    LOGI("[WORLD] reset (gen %d): the pawn, camera, hands, menus and stage state of the old world are dropped",g_worldSeen);
    g_pawn=0; g_camComp=0; g_vrOrigin=0; g_mcL=0; g_mcR=0; g_camMgr=0;
    if(g_isoActor&&!obj_alive(g_isoActor)){ unroot_object(g_isoActor); g_isoActor=0; g_isoComp=0;   // gone with the old world
        a2_drop_meshes(); g_trackParent=0; head_drop("the world changed"); }
    if(g_emState!=EM_IDLE){ show_drop("the world changed"); g_emStream=0; g_emActive=-1; g_emState=EM_IDLE; g_emLoadGen++; g_emFailed=1; }
    g_emGameState=0; g_emScreens[0]=g_emScreens[1]=0; g_emVM=0; g_emOurScreen=0; g_emRig=0; g_emList=0; memset(g_emW,0,sizeof g_emW);
    g_smList=0; memset(g_smW,0,sizeof g_smW);
    g_cPawn=g_cVRO=g_cCam=g_cPC=g_cPar=0; g_cBased=false; g_cHaveSet=false; }   // walking: nothing is written to the old VROrigin
extern "C" void repl_pe(void* self,void* func,void* parms){
    g_pe_n++;
    if(!g_mod_on||!is_game_thread()){ orig_pe(self,func,parms); return; }
    { static double lastRun=0; double pnow=mono_now();
      if(g_worldSeen!=g_worldGen&&ue_enter()){ world_reset_game(); ue_leave(); }
      if(g_wire_req&&ue_enter()){ g_wire_req=0; world_wire(); ue_leave(); }          // the poll thread found the world
      // the per-frame work, every 16 ms at most, once the world is up (Tribe's pawn wired), with or without our avatar
      // actor (mod2311; levels doc S3, load doc 3.4): each part checks its own needs
      if(g_pawn && (lastRun==0 || pnow-lastRun>=0.016) && ue_enter()){
          if(!obj_alive(g_pawn)) ue_leave();                         // the world is going: the poll thread resets it
          else { float pdt=(lastRun==0)?0.016f:(float)(pnow-lastRun); if(pdt>0.25f) pdt=0.25f; lastRun=pnow; g_pe_drv++;
          giant_tick(pdt); club_tick(pdt); intro_tick(pdt); camview_tick(pdt); stream_tick(pdt); freeze_beat(); follow_update(pdt); bt_frame(pdt); drone_update(pdt); head_tick(pdt); menu_tick(); env_menu_tick(); perf_frame(pdt); ue_leave(); } } }''')
rep('''    // FOLLOW: our actor's ReceiveTick (TG_PostUpdateWork) drives the body each frame. AActor::Tick always routes
    // ReceiveTick through ProcessEvent even with no Blueprint implementation. Fallback: the pawn's tick, only while ours is
    // silent, or (fallback_wire) while there is no avatar actor at all.
    if((g_isoActor||g_fallbackTicker) && parms){
        uintptr_t s=(uintptr_t)self;
''', '''    // (mod2311: the 2304 ReceiveTick driver and the pawn-tick fallback are gone: on 2311 ReceiveTick never passes
    // ProcessEvent, and the driver above runs every frame once the world is up)
''')
# the two ReceiveTick lines + their closing brace
i = s.index('''        if(s==g_isoActor && func==(void*)g_fnReceiveTick && ue_enter()){ g_isoTicks++;''')
j = s.index('''    // keeper: poll thread saw a NATIVE reset -> re-attach our (rooted) mesh here on the game thread''')
blk = s[i:j]
assert blk.count("\n") == 3 and blk.rstrip().endswith("}"), repr(blk[-60:])
s = s[:i] + s[j:]
rep('''    if(g_fb_req && ue_enter()){ g_fb_req=0; fallback_wire(); ue_leave(); }   // no avatar actor: the pawn ticks for us
    if(g_report_req && g_body && ue_enter()){ g_report_req=0; g_reports++; render_report(); ue_leave(); }''',
    '''    if(g_report_req && (g_body||g_isoComp) && ue_enter()){ g_report_req=0; g_reports++; render_report(); ue_leave(); }''')
rep('''static uintptr_t g_pawn=0, g_fallbackTicker=0;''', '''static uintptr_t g_pawn=0;''')
rep('''static uintptr_t g_fnReceiveTick=0, g_fnGetRot=0, g_fnSetActorLR=0, g_camComp=0, g_vrOrigin=0, g_mcL=0, g_mcR=0;''',
    '''static uintptr_t g_fnGetRot=0, g_fnSetActorLR=0, g_camComp=0, g_vrOrigin=0, g_mcL=0, g_mcR=0;''')
rep('''static long g_isoTicks=0, g_camTicks=0; static bool g_restOK=false, g_followInit=false, g_turning=false;''',
    '''static bool g_restOK=false, g_followInit=false, g_turning=false;''')
open(p, "w", encoding="utf-8", newline="").write(s)

# intro.cpp: the show bus's own check (levels doc S1)
q = src + "/intro.cpp"
t = open(q, encoding="utf-8", newline="").read()
old = '''    bool up=ix>=0&&g_introArmed&&g_emState==EM_ACTIVE&&g_gColl&&obj_alive(g_gColl)&&g_pawn&&obj_alive(g_pawn);'''
assert t.count(old) == 1
t = t.replace(old, '''    bool up=ix>=0&&g_introArmed&&g_emState==EM_ACTIVE&&show_coll_ok()&&g_pawn&&obj_alive(g_pawn);   // mod2311: the show bus's check''')
open(q, "w", encoding="utf-8", newline="").write(t)

# stream.cpp: the diag line no longer has the two tick counters
r = src + "/stream.cpp"
u = open(r, encoding="utf-8", newline="").read()
old = '''    { static int tkn=0; if((++tkn % 10)==0) LOGI("[STREAM] diag ticks: iso %ld, cam %ld, ProcessEvent calls %ld, per-frame runs %ld", g_isoTicks, g_camTicks, g_pe_n, g_pe_drv); }'''
assert u.count(old) == 1
u = u.replace(old, '''    { static int tkn=0; if((++tkn % 60)==0) LOGI("[STREAM] diag ticks: ProcessEvent calls %ld, per-frame runs %ld", g_pe_n, g_pe_drv); }''')
open(r, "w", encoding="utf-8", newline="").write(u)
print("ok")
