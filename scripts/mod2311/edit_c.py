#!/usr/bin/env python3
"""Step C edit (stages) on top of step B: REACTOR's gate reads its two bitfield flags (levels doc S4), a stage's intro
runs only on its own stage, the soft-pointer test uses the engine's dead test (levels doc S2), and a one-time check
that every envs.txt level is in the mounted paks. Exact-string edits on dumper.cpp, club.cpp and intro.cpp."""
import sys

src = sys.argv[1]


def edit(fn, pairs):
    p = src + "/" + fn
    s = open(p, encoding="utf-8", newline="").read()
    for old, new in pairs:
        n = s.count(old)
        assert n == 1, (fn, n, old[:100])
        s = s.replace(old, new)
    open(p, "w", encoding="utf-8", newline="").write(s)


edit("club.cpp", [
    ('''static int g_cOffVRO=-1, g_cOffCam=-1, g_cOffRole=-1, g_cOffHost=-1, g_cOffDJ=-1, g_cOffRelLoc=-1, g_cOffRelRot=-1;''',
     '''static int g_cOffVRO=-1, g_cOffCam=-1, g_cOffRole=-1, g_cOffHost=-1, g_cOffDJ=-1, g_cOffRelLoc=-1, g_cOffRelRot=-1;
static uint8_t g_cMaskHost=0xFF, g_cMaskDJ=0xFF;                     // 2311: bHost / bDJing are bitfield bools (their ByteMask)'''),
    ('''        g_cOffHost=prop_offset(cls,"bHost",0); g_cOffDJ=prop_offset(cls,"bDJing",0);''',
     '''        g_cOffHost=prop_offset(cls,"bHost",0); g_cOffDJ=prop_offset(cls,"bDJing",0);
        { int S=calib_fprop_size(); uintptr_t f; g_cMaskHost=0xFF; g_cMaskDJ=0xFF;   // mod2311 step C (levels doc S4): as em_actor_hidden,
          if(S>0&&g_cOffHost>=0&&(f=find_prop(cls,"bHost"))){ g_cOffHost+=rd8(f+S+1); g_cMaskHost=rd8(f+S+2); }   // the byte at
          if(S>0&&g_cOffDJ>=0&&(f=find_prop(cls,"bDJing"))){ g_cOffDJ+=rd8(f+S+1); g_cMaskDJ=rd8(f+S+2); } }      // Offset+ByteOffset & ByteMask'''),
    ('''    int role=g_cOffRole>=0?*(uint8_t*)(g_cPawn+g_cOffRole):-1, host=g_cOffHost>=0?*(uint8_t*)(g_cPawn+g_cOffHost):-1,
        dj=g_cOffDJ>=0?*(uint8_t*)(g_cPawn+g_cOffDJ):-1;''',
     '''    int role=g_cOffRole>=0?*(uint8_t*)(g_cPawn+g_cOffRole):-1, host=g_cOffHost>=0?(*(uint8_t*)(g_cPawn+g_cOffHost)&g_cMaskHost):-1,
        dj=g_cOffDJ>=0?(*(uint8_t*)(g_cPawn+g_cOffDJ)&g_cMaskDJ):-1;'''),
])

edit("intro.cpp", [
    ('''    bool up=ix>=0&&g_introArmed&&g_emState==EM_ACTIVE&&show_coll_ok()&&g_pawn&&obj_alive(g_pawn);   // mod2311: the show bus's check''',
     '''    char ifol[48], iwant[64]=""; if(em_active_folder(ifol,sizeof ifol)) snprintf(iwant,sizeof iwant,"intro.%s.txt",ifol);
    bool up=ix>=0&&g_introArmed&&g_emState==EM_ACTIVE&&!strcmp(iwant,g_irFile)&&show_coll_ok()&&g_pawn&&obj_alive(g_pawn);   // mod2311:
    // the show bus's check (step A), and this stage's own ride (step C: after a switch the old stage's ride stays loaded
    // until intro_lookup reads the new one, up to ~8 s, and its actors and keys belong to the old stage)'''),
])

edit("dumper.cpp", [
    ('#define MOD2311_STEP "B"', '#define MOD2311_STEP "C"'),
    # S2 for the soft pointers: the engine's own dead test (FWeakObjectPtr::Get), not UE4's 1<<28
    ('''    if((int32_t)rd32(item+0x10)!=ser||(rd32(item+8)&(0x200000u|0x10000000u))) return -1;''',
     '''    if((int32_t)rd32(item+0x10)!=ser||(rd32(item+8)&gc_dead_mask())) return -1;   // step C: 5.4 rotates the unreachable flag'''),
    # the stages in the paks: once, on the game thread, as soon as the engine's file functions are known
    ('''static void env_menu_tick(){
    static int tk=0, spawns=0, win=0, away=0; static bool tripped=false;
    if(!g_envMenuOn||(++tk%60)!=0) return;''',
     '''// mod2311 step C: is every envs.txt level in the mounted paks? BlueprintPathsLibrary.FileExists goes through the pak layer
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
    em_check_paks();'''),
    ('''    char line[1200];
    int k=snprintf(line,sizeof line,"[READY] %s step=%s t=%.1fs hook=%s world=%d avatar=%s skin=%s stage=%s stream=%s menus=%s gen=%d skips=%ld",
        all?"all=1":(t>=180.0?"FAIL":"all=0"),MOD2311_STEP,t,hook,(int)g_worldUp,av,skin,stg,strm,menus,(int)g_worldGen,g_callSkips);''',
     '''    char line[1200]; char paks[24]="?"; if(g_emPaksOk>=0) snprintf(paks,sizeof paks,"%d/%d",(int)g_emPaksOk,(int)g_emPaksN);
    int k=snprintf(line,sizeof line,"[READY] %s step=%s t=%.1fs hook=%s world=%d avatar=%s skin=%s stage=%s stream=%s menus=%s paks=%s gen=%d skips=%ld",
        all?"all=1":(t>=180.0?"FAIL":"all=0"),MOD2311_STEP,t,hook,(int)g_worldUp,av,skin,stg,strm,menus,paks,(int)g_worldGen,g_callSkips);'''),
])
print("ok")
