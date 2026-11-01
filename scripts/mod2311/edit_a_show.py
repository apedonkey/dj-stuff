#!/usr/bin/env python3
"""Step A edit: the show collection as a weak handle (levels doc S1) + keep the stage pick (exact-string edits)."""
import sys

p = sys.argv[1]
s = open(p, encoding="utf-8", newline="").read()


def rep(old, new, cnt=1):
    global s
    n = s.count(old)
    assert n == cnt, (n, old[:90])
    s = s.replace(old, new)


# 1. load generation + failure flag next to the env state
rep('''static char g_emLabels[EM_MAX][64], g_emPaths[EM_MAX][256];                  // written by the poll thread
static bool em_active_folder(''', '''static char g_emLabels[EM_MAX][64], g_emPaths[EM_MAX][256];                  // written by the poll thread
static volatile int g_emLoadGen=0;                                          // +1 at every stage load and unload (show bus)
static volatile sig_atomic_t g_emFailed=0;                                  // a load failed (the supervisor retries it)
static bool em_active_folder(''')
# 2. em_unload drops the show bus; 3. em_fail keeps the pick
rep('''static void giant_reset(const char* why);                         // giant intro (below)
static void em_unload(const char* why){''', '''static void giant_reset(const char* why);                         // giant intro (below)
static void show_drop(const char* why);                           // the show bus (below)
static void em_unload(const char* why){''')
rep('''    giant_reset("stage unloaded");
    g_emVM=0;''', '''    giant_reset("stage unloaded"); show_drop("stage unloaded"); g_emLoadGen++;
    g_emVM=0;''')
rep('''static void em_fail(const char* why){                    // undo: Void screens back, nothing loaded, don't re-apply at next launch,
    em_hide_screens(false); em_unload(why); em_write_active("");               // and put Tribe back on the environment you came from''',
    '''static void em_fail(const char* why){                    // undo: Void screens back, nothing loaded, Tribe back where you came from.
    em_hide_screens(false); em_unload(why); g_emFailed=1;                      // mod2311: the pick stays in active_env.txt (the
                                                                               // supervisor tries again; the next launch re-applies it)''')
# 4. the weak handle for the show collection
rep('''static uintptr_t g_gSpotComp=0, g_gFnTime=0, g_gGPS=0; static int g_gTimeDouble=-1;''',
    '''static uintptr_t g_gSpotComp=0, g_gFnTime=0, g_gGPS=0; static int g_gTimeDouble=-1;
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
    LOGI("[GIANT] show bus adopted: 0x%lx (slot %u, serial %d, gen %d)",(unsigned long)c,idx,(int)ser,(int)g_showGen); }''')
# 5. giant_lookup: once per load, published for the game thread
rep('''    if(g_gColl&&obj_alive(g_gColl)) return;
    if(g_emState!=EM_ACTIVE){ g_gColl=0; return; }                    // the collection only exists while our stage is up''',
    '''    int gen=g_emLoadGen;                                                // found once per stage load; show_adopt takes it (game thread)
    if(g_gPendGen==gen||g_emState!=EM_ACTIVE) return;                  // the collection only exists while our stage is up''')
rep('''    { refresh_numelements(); char cn[64], on[96]; g_gSpotComp=0;
      for(uint32_t i=0;i<g_numElements&&!g_gSpotComp;i++){ uintptr_t o=obj_at(i); if(!o) continue;''',
    '''    uintptr_t spot=0;
    { refresh_numelements(); char cn[64], on[96];
      for(uint32_t i=0;i<g_numElements&&!spot;i++){ uintptr_t o=obj_at(i); if(!o) continue;''')
rep('''        if(strstr(on,"DinoGiantSpotLight")) g_gSpotComp=o; } }
    memcpy(g_gN,n,sizeof n); g_gHasGiant=(dino||!strcmp(SHOWS[si][0],"redeye"))&&n[GP_H]; g_gColl=c; g_showGen++;   // RED EYE: the crane flight
    if(!g_gHasGiant) LOGI("[GIANT] show bus: %s 0x%lx (gen %d), %d/%d parameters: the light show runs here, no giant intro",
                          cn,(unsigned long)c,(int)g_showGen,ok,G_NP);''',
    '''        if(strstr(on,"DinoGiantSpotLight")) spot=o; } }
    bool giant=(dino||!strcmp(SHOWS[si][0],"redeye"))&&n[GP_H];       // RED EYE: the crane flight
    memcpy(g_gPendN,n,sizeof n); g_gPendGiant=giant; g_gPendSpot=spot; g_gPendGen=gen; __sync_synchronize(); g_gPend=c;
    if(!giant) LOGI("[GIANT] show bus: %s 0x%lx (load %d), %d/%d parameters: the light show runs here, no giant intro",
                          cn,(unsigned long)c,gen,ok,G_NP);''')
rep('''         (unsigned long)c,G_BTN[0],G_BTN[1],G_BTN[2],g_gCfgH,g_gCfgRise,g_gCfgDesc,g_gCfgPress,(unsigned long)g_gSpotComp,''',
    '''         (unsigned long)c,G_BTN[0],G_BTN[1],G_BTN[2],g_gCfgH,g_gCfgRise,g_gCfgDesc,g_gCfgPress,(unsigned long)spot,''')
# 6. every write checks the handle
rep('''static void giant_mpc(uintptr_t ctx,int i,float v){ if(g_gColl&&g_mpcFnSetS&&g_mpcLib&&g_gN[i]) mpc_call_on(g_gColl,g_mpcFnSetS,ctx,g_gN[i],&v,false,true); }''',
    '''static void giant_mpc(uintptr_t ctx,int i,float v){ if(g_gN[i]&&g_mpcFnSetS&&g_mpcLib&&show_coll_ok()) mpc_call_on(g_gColl,g_mpcFnSetS,ctx,g_gN[i],&v,false,true); }''')
rep('''static uint64_t show_key(const char* name){ return (g_gColl&&obj_alive(g_gColl))?mpc_param_name(g_gColl,"ScalarParameters",28,name):0; }
static void show_set(uint64_t key,float v){ if(key&&g_gColl&&g_mpcFnSetS&&g_mpcLib&&g_pawn&&obj_alive(g_pawn)) mpc_call_on(g_gColl,g_mpcFnSetS,g_pawn,key,&v,false,true); }''',
    '''static uint64_t show_key(const char* name){ return show_coll_ok()?mpc_param_name(g_gColl,"ScalarParameters",28,name):0; }
static void show_set(uint64_t key,float v){ if(key&&g_mpcFnSetS&&g_mpcLib&&g_pawn&&obj_alive(g_pawn)&&show_coll_ok()) mpc_call_on(g_gColl,g_mpcFnSetS,g_pawn,key,&v,false,true); }''')
rep('''    if(g_gColl&&obj_alive(g_gColl)&&g_pawn&&obj_alive(g_pawn)){ giant_mpc(g_pawn,GP_H,0); giant_mpc(g_pawn,GP_ROBE,0); giant_mpc(g_pawn,GP_GLOW,0);''',
    '''    if(show_coll_ok()&&g_pawn&&obj_alive(g_pawn)){ giant_mpc(g_pawn,GP_H,0); giant_mpc(g_pawn,GP_ROBE,0); giant_mpc(g_pawn,GP_GLOW,0);''')
# 7. giant_tick: adopt / drop first
rep('''static void giant_tick(float dt){                                     // game thread, every frame
    if(g_emState!=EM_ACTIVE||!g_gColl||!obj_alive(g_gColl)||!g_pawn||!obj_alive(g_pawn)||!g_camComp){''',
    '''static void giant_tick(float dt){                                     // game thread, every frame
    g_gFrame++;
    if(g_gColl&&!show_coll_ok()){ show_drop("the collection went away"); g_gPendGen=-1; }   // and look again
    if(g_gPend&&g_emState==EM_ACTIVE) show_adopt();
    if(g_emState!=EM_ACTIVE||!show_coll_ok()||!g_pawn||!obj_alive(g_pawn)||!g_camComp){''')
open(p, "w", encoding="utf-8", newline="").write(s)
print("ok")
