#!/usr/bin/env python3
"""Step A edit: the stage loader keeps the pick, records stock picks, uses the pawn as a world context, notices when our
level goes away, counts the boxes for [READY] (exact-string edits)."""
import sys

p = sys.argv[1]
s = open(p, encoding="utf-8", newline="").read()


def rep(old, new, cnt=1):
    global s
    n = s.count(old)
    assert n == cnt, (n, old[:90])
    s = s.replace(old, new)


# state for the supervisor / [READY]
rep('''static volatile int g_emLoadGen=0;                                          // +1 at every stage load and unload (show bus)''',
    '''static volatile int g_emLoadGen=0;                                          // +1 at every stage load and unload (show bus)
static volatile sig_atomic_t g_emAdded=0, g_emListLive=0;                   // our boxes in the live list / the list exists
static volatile sig_atomic_t g_emTribeSwitched=0;                           // Tribe left our stage by itself this session
static char g_emStockName[64]="";                                           // a stock environment you picked (game thread)''')
# em_write_active: a stock pick is recorded as "stock:<name>"; "" is no longer used by any caller
rep('''static void em_write_active(const char* label){                               // "" forgets the saved choice
    char p[600]; snprintf(p,sizeof p,"%s/active_env.txt",OUTDIR); if(!label||!*label){ unlink(p); return; }''',
    '''static void em_write_active(const char* label){       // your last pick: a mod stage's label, or "stock:<name>" (mod2311: the
    char p[600]; snprintf(p,sizeof p,"%s/active_env.txt",OUTDIR); if(!label||!*label) return;   // mod never deletes it)''')
# em_pe_2311: a stock environment picked (press + its OnSkinApplied) is recorded even when ours isn't up
rep('''        if(pressed&&g_emState!=EM_IDLE&&sk&&g_emCls&&in_range(sk,0x30)&&rdptr(sk+OFF_Class)==g_emCls){
            g_emUnloadReq=1; LOGI("[ENV] stock environment picked (press + OnSkinApplied) -> unloading ours"); }''',
    '''        if(pressed&&sk&&g_emCls&&in_range(sk,0x30)&&rdptr(sk+OFF_Class)==g_emCls){
            int on=prop_offset(g_emCls,"Name",0); char nm[64]="?"; if(on>=0) fname_resolve(rd32(sk+(uintptr_t)on),nm,sizeof nm);
            snprintf(g_emStockName,sizeof g_emStockName,"%s",nm); g_emUnloadReq=1;
            LOGI("[ENV] stock environment picked (press + OnSkinApplied): %s%s",nm,g_emState!=EM_IDLE?" -> unloading ours":""); }''')
# env_menu_tick: count our boxes in the list
rep('''    uintptr_t list=g_emList; int n=g_emCount;
    if(!tripped&&list&&obj_alive(list)&&g_emCls&&g_smFnSpawn&&g_smFnAddItem&&g_smFnIndexOf&&n>0){''',
    '''    uintptr_t list=g_emList; int n=g_emCount;
    g_emListLive=(list&&obj_alive(list))?1:0;
    if(!tripped&&list&&obj_alive(list)&&g_emCls&&g_smFnSpawn&&g_smFnAddItem&&g_smFnIndexOf&&n>0){''')
rep('''                sm_list_add(list,g_emItems[i]); LOGI("[ENV] added box '%s'%s",g_emLabels[i],g_emIdentOf[i]==g_emItems[i]?"":" (WITHOUT the Void's identity: not found)"); } }''',
    '''                sm_list_add(list,g_emItems[i]); LOGI("[ENV] added box '%s'%s",g_emLabels[i],g_emIdentOf[i]==g_emItems[i]?"":" (WITHOUT the Void's identity: not found)"); } }
        { int k=0; for(int i=0;i<n&&i<EM_MAX;i++) if(g_emItems[i]&&obj_alive(g_emItems[i])&&sm_list_index(list,g_emItems[i])>=0) k++; g_emAdded=k; }''')
# world contexts: the pawn too (the per-frame work now runs before our avatar exists)
rep('''        uintptr_t ctx[3]={g_isoActor,g_emList,g_emRig};
        for(int k=0;k<3&&!gs;k++){''', '''        uintptr_t ctx[4]={g_pawn,g_isoActor,g_emList,g_emRig};
        for(int k=0;k<4&&!gs;k++){''')
# a stock pick: recorded, ours unloaded if up
rep('''    if(g_emUnloadReq){ g_emUnloadReq=0; if(g_emState!=EM_IDLE){ em_hide_screens(false); em_unload("you picked a stock environment"); em_write_active(""); } }''',
    '''    if(g_emUnloadReq){ g_emUnloadReq=0; char w[80]; snprintf(w,sizeof w,"stock:%s",g_emStockName[0]?g_emStockName:"?"); em_write_active(w);
        g_emTribeSwitched=0; if(g_emState!=EM_IDLE){ em_hide_screens(false); em_unload("you picked a stock environment"); } }''')
# a load request: a fresh show-collection lookup for this load; our own SetEnvironment is remembered
rep('''            g_emActive=req; em_write_active(g_emLabels[req]);
            int before=em_cur_env(); if(before!=(int)g_emVoid) g_emPrevEnv=before;
            int r=call_lib1(g_emGameState,g_emFnSetEnv,(int)g_emVoid);''',
    '''            g_emLoadGen++; g_emActive=req; em_write_active(g_emLabels[req]); g_emTribeSwitched=0;
            int before=em_cur_env(); if(before!=(int)g_emVoid) g_emPrevEnv=before;
            int r=call_lib1(g_emGameState,g_emFnSetEnv,(int)g_emVoid);''')
# EM_WAIT_LOAD unchanged; EM_ACTIVE: our level still loaded? Tribe switched by itself: unload, keep the pick
rep('''    else if(st==EM_ACTIVE){
        em_hide_screens(true);                                               // Tribe re-shows its registered backdrop when visuals change''',
    '''    else if(st==EM_ACTIVE){
        if(!g_emStream||!obj_alive(g_emStream)){ LOGI("[ENV] our level '%s' went away (a world change?): unloaded, the supervisor loads it again",g_emLabels[a]);
            g_emStream=0; em_hide_screens(false); em_unload("our level went away"); g_emFailed=1; return; }
        em_hide_screens(true);                                               // Tribe re-shows its registered backdrop when visuals change''')
rep('''        if(cur>=0&&cur!=(int)g_emVoid){ if(++away>=2){ em_hide_screens(false); em_unload("Tribe switched environment"); em_write_active(""); } }''',
    '''        if(cur>=0&&cur!=(int)g_emVoid){ if(++away>=2){ em_hide_screens(false);
            bool youPicked=mono_now()-g_emPressMs/1000.0<4.0;           // a skin-box press just before: you picked a stock one
            if(youPicked){ char w[80]; snprintf(w,sizeof w,"stock:%s",em_env_name(cur)); em_write_active(w); em_unload("you picked a stock environment"); }
            else { g_emTribeSwitched=1; em_unload("Tribe switched environment; your pick stays for the next launch"); } } }''')
open(p, "w", encoding="utf-8", newline="").write(s)
print("ok")
