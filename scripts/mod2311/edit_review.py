#!/usr/bin/env python3
"""Fixes from the review of the final diff (claudedocs/mod_2311_build.md, "Review"). Each fix carries the earliest step
it belongs to; usage: python -P edit_review.py <src dir> <A|B|C>  applies every fix whose step <= the tree's step."""
import sys

src, step = sys.argv[1], sys.argv[2]
ORDER = {"A": 0, "B": 1, "C": 2}
files = {}


def rd(fn):
    if fn not in files:
        files[fn] = open(src + "/" + fn, encoding="utf-8", newline="").read()
    return files[fn]


def rep(fs, fn, old, new, cnt=1):
    if ORDER[fs] > ORDER[step]:
        return
    s = rd(fn)
    n = s.count(old)
    assert n == cnt, (fs, fn, n, old[:110])
    files[fn] = s.replace(old, new)


# R1 (A) range table: rebuild on a miss unless another thread already published a newer table since this reader's miss
#    (the 20 ms throttle could make a just-allocated object read as unmapped, so the call check would skip a real call)
rep("A", "dumper.cpp", '''// search and searches again if a rebuild touched it. Rebuilds are at most one per 20 ms.''',
    '''// search and searches again if a rebuild touched it. A miss rebuilds the table unless another thread has published a
// newer one since the miss (then the search is simply repeated on it).''')
rep("A", "dumper.cpp", '''static RangeTab g_rt[4]; static RangeTab* volatile g_rtCur=nullptr; static pthread_mutex_t g_rtLock=PTHREAD_MUTEX_INITIALIZER;
static void load_maps() {
    pthread_mutex_lock(&g_rtLock);
    static double last=-1; static int next=0; double now=mono_now();
    if(g_rtCur&&last>=0&&now-last<0.020){ pthread_mutex_unlock(&g_rtLock); return; }   // just rebuilt
    last=now;
    FILE* f=fopen("/proc/self/maps","r"); if(!f){ pthread_mutex_unlock(&g_rtLock); return; }''',
    '''static RangeTab g_rt[4]; static RangeTab* volatile g_rtCur=nullptr; static pthread_mutex_t g_rtLock=PTHREAD_MUTEX_INITIALIZER;
static volatile uint32_t g_rtGen=0;                                  // +1 per published table
static void load_maps_since(uint32_t gen) {                         // gen: g_rtGen when the caller's search missed
    pthread_mutex_lock(&g_rtLock);
    static int next=0;
    if(g_rtCur&&__atomic_load_n(&g_rtGen,__ATOMIC_ACQUIRE)!=gen){ pthread_mutex_unlock(&g_rtLock); return; }   // newer already
    FILE* f=fopen("/proc/self/maps","r"); if(!f){ pthread_mutex_unlock(&g_rtLock); return; }''')
rep("A", "dumper.cpp", '''    __atomic_store_n(&g_rtCur,t,__ATOMIC_RELEASE);
    pthread_mutex_unlock(&g_rtLock);
}''', '''    __atomic_store_n(&g_rtCur,t,__ATOMIC_RELEASE); __atomic_add_fetch(&g_rtGen,1u,__ATOMIC_ACQ_REL);
    pthread_mutex_unlock(&g_rtLock);
}
static void load_maps(){ load_maps_since(__atomic_load_n(&g_rtGen,__ATOMIC_ACQUIRE)); }   // an explicit refresh''')
rep("A", "dumper.cpp", '''    if(!p) return false;
    if(!in_range(p,n)){ load_maps(); if(!in_range(p,n)) return false; }
    GuardSlot* g=guard_slot();''', '''    if(!p) return false;
    uint32_t gen=__atomic_load_n(&g_rtGen,__ATOMIC_ACQUIRE);
    if(!in_range(p,n)){ load_maps_since(gen); if(!in_range(p,n)) return false; }
    GuardSlot* g=guard_slot();''')

# R2 (A) spawn_iso_actor / do_load: engine lookups once (they were 7 + 13 full object walks on the game thread per call;
#    now our actor is spawned again after a room change)
rep("A", "dumper.cpp", '''    uintptr_t gs   =find_by_path("/Script/Engine.Default__GameplayStatics",0);
    uintptr_t fnB  =find_by_path("/Script/Engine.GameplayStatics.BeginDeferredActorSpawnFromClass",0);
    uintptr_t fnF  =find_by_path("/Script/Engine.GameplayStatics.FinishSpawningActor",0);
    uintptr_t cls  =find_by_path("/Script/Engine.SkeletalMeshActor",1);
    uintptr_t fnRot=find_by_path("/Script/Engine.PlayerCameraManager.GetCameraRotation",0);''',
    '''    static uintptr_t gs=0, fnB=0, fnF=0, cls=0, fnRot=0, fnColl=0, fnShad=0;   // engine objects: looked up once (mod2311)
    if(!gs)    gs   =find_by_path("/Script/Engine.Default__GameplayStatics",0);
    if(!fnB)   fnB  =find_by_path("/Script/Engine.GameplayStatics.BeginDeferredActorSpawnFromClass",0);
    if(!fnF)   fnF  =find_by_path("/Script/Engine.GameplayStatics.FinishSpawningActor",0);
    if(!cls)   cls  =find_by_path("/Script/Engine.SkeletalMeshActor",1);
    if(!fnRot) fnRot=find_by_path("/Script/Engine.PlayerCameraManager.GetCameraRotation",0);''')
rep("A", "dumper.cpp", '''    uintptr_t fnColl=find_by_path("/Script/Engine.PrimitiveComponent.SetCollisionEnabled",0);
    uintptr_t fnShad=find_by_path("/Script/Engine.PrimitiveComponent.SetCastShadow",0);''',
    '''    if(!fnColl) fnColl=find_by_path("/Script/Engine.PrimitiveComponent.SetCollisionEnabled",0);
    if(!fnShad) fnShad=find_by_path("/Script/Engine.PrimitiveComponent.SetCastShadow",0);''')
rep("A", "dumper.cpp", '''    uintptr_t fnLoad=find_by_path("/Script/glTFRuntime.glTFRuntimeFunctionLibrary.glTFLoadAssetFromFilename",0);
    uintptr_t fnMesh=find_by_path("/Script/glTFRuntime.glTFRuntimeAsset.LoadSkeletalMesh",0);
    uintptr_t fnErr =find_by_path("/Script/glTFRuntime.glTFRuntimeAsset.GetErrors",0);
    uintptr_t fnSet =find_by_path("/Script/Engine.SkeletalMeshComponent.SetSkeletalMeshAsset",0);
    uintptr_t libCDO=find_by_path("/Script/glTFRuntime.Default__glTFRuntimeFunctionLibrary",0);
    if(!libCDO) libCDO=find_obj("glTFRuntimeFunctionLibrary",1);''',
    '''    static uintptr_t fnLoad=0, fnMesh=0, fnErr=0, fnSet=0, libCDO=0;     // native objects: looked up once (mod2311)
    if(!fnLoad) fnLoad=find_by_path("/Script/glTFRuntime.glTFRuntimeFunctionLibrary.glTFLoadAssetFromFilename",0);
    if(!fnMesh) fnMesh=find_by_path("/Script/glTFRuntime.glTFRuntimeAsset.LoadSkeletalMesh",0);
    if(!fnErr)  fnErr =find_by_path("/Script/glTFRuntime.glTFRuntimeAsset.GetErrors",0);
    if(!fnSet)  fnSet =find_by_path("/Script/Engine.SkeletalMeshComponent.SetSkeletalMeshAsset",0);
    if(!libCDO) libCDO=find_by_path("/Script/glTFRuntime.Default__glTFRuntimeFunctionLibrary",0);
    if(!libCDO) libCDO=find_obj("glTFRuntimeFunctionLibrary",1);''')
rep("A", "dumper.cpp", '''    g_fnOwner=find_by_path("/Script/Engine.PrimitiveComponent.SetOwnerNoSee",0);
    g_fnVis  =find_by_path("/Script/Engine.SceneComponent.SetVisibility",0);
    g_fnHid  =find_by_path("/Script/Engine.SceneComponent.SetHiddenInGame",0);
    g_fnLeader  =find_by_path("/Script/Engine.SkinnedMeshComponent.SetLeaderPoseComponent",0);
    g_fnRendered=find_by_path("/Script/Engine.PrimitiveComponent.WasRecentlyRendered",0);
    g_fnLoc     =find_by_path("/Script/Engine.SceneComponent.K2_GetComponentLocation",0);
    g_fnScale   =find_by_path("/Script/Engine.SceneComponent.K2_GetComponentScale",0);
    g_fnCamLoc  =find_by_path("/Script/Engine.PlayerCameraManager.GetCameraLocation",0);''',
    '''    if(!g_fnOwner)    g_fnOwner=find_by_path("/Script/Engine.PrimitiveComponent.SetOwnerNoSee",0);
    if(!g_fnVis)      g_fnVis  =find_by_path("/Script/Engine.SceneComponent.SetVisibility",0);
    if(!g_fnHid)      g_fnHid  =find_by_path("/Script/Engine.SceneComponent.SetHiddenInGame",0);
    if(!g_fnLeader)   g_fnLeader  =find_by_path("/Script/Engine.SkinnedMeshComponent.SetLeaderPoseComponent",0);
    if(!g_fnRendered) g_fnRendered=find_by_path("/Script/Engine.PrimitiveComponent.WasRecentlyRendered",0);
    if(!g_fnLoc)      g_fnLoc     =find_by_path("/Script/Engine.SceneComponent.K2_GetComponentLocation",0);
    if(!g_fnScale)    g_fnScale   =find_by_path("/Script/Engine.SceneComponent.K2_GetComponentScale",0);
    if(!g_fnCamLoc)   g_fnCamLoc  =find_by_path("/Script/Engine.PlayerCameraManager.GetCameraLocation",0);''')

# R4 (A) the head after a respawn: keep the head mesh (rooted), forget only the component that went with our actor
rep("A", "dumper.cpp", '''static volatile int g_worldGen=0; static int g_worldSeen=0;
static void world_reset_game(){''', '''static volatile int g_worldGen=0; static int g_worldSeen=0;
static void head_forget(const char* why){            // our actor went away: its head component with it; the head mesh stays
    if(g_hdComp) LOGI("[HEAD] the head component went with our avatar actor (%s): a new one is made on the next tick",why);
    g_hdComp=0; g_hdForA=0; g_hdState=HD_ON; }
static void world_reset_game(){''')
rep("A", "dumper.cpp", '''        a2_drop_meshes(); g_trackParent=0; head_drop("the world changed"); }''',
    '''        a2_drop_meshes(); g_trackParent=0; head_forget("the world changed"); }''')
rep("A", "dumper.cpp", '''        else { if(g_isoActor){ unroot_object(g_isoActor); g_isoActor=0; g_isoComp=0; a2_drop_meshes(); g_trackParent=0; head_drop("our actor went away"); }''',
    '''        else { if(g_isoActor){ unroot_object(g_isoActor); g_isoActor=0; g_isoComp=0; a2_drop_meshes(); g_trackParent=0; head_forget("our actor went away"); }''')
# R8 (A) world reset: the lift's base on the old VROrigin, its state, and the light list go too
rep("A", "dumper.cpp", '''    g_cPawn=g_cVRO=g_cCam=g_cPC=g_cPar=0; g_cBased=false; g_cHaveSet=false; }   // walking: nothing is written to the old VROrigin''',
    '''    g_cPawn=g_cVRO=g_cCam=g_cPC=g_cPar=0; g_cBased=false; g_cHaveSet=false;      // walking: nothing is written to the old VROrigin
    g_gBased=false; g_gState=G_DOWN; g_gH=0; g_walkPause=0; g_lN=0; }            // the lift and the light list: the old world's''')

# R5 (A) the freeze recorder's beat: every game-thread ProcessEvent (16 ms at most), not only the per-frame work, so a
#    level load isn't taken for a freeze; and a dead pawn is checked once per 16 ms, not on every call
rep("A", "dumper.cpp", '''    { static double lastRun=0; double pnow=mono_now();
      if(g_worldSeen!=g_worldGen&&ue_enter()){ world_reset_game(); ue_leave(); }''',
    '''    { static double lastRun=0, lastBeat=0; double pnow=mono_now();
      if(pnow-lastBeat>=0.016){ lastBeat=pnow; freeze_beat(); }        // the game thread is alive (also while a world loads)
      if(g_worldSeen!=g_worldGen&&ue_enter()){ world_reset_game(); ue_leave(); }''')
rep("A", "dumper.cpp", '''          if(!obj_alive(g_pawn)) ue_leave();                         // the world is going: the poll thread resets it''',
    '''          if(!obj_alive(g_pawn)){ lastRun=pnow; ue_leave(); }        // the world is going: the poll thread resets it''')
rep("A", "dumper.cpp", '''camview_tick(pdt); stream_tick(pdt); freeze_beat(); follow_update(pdt);''',
    '''camview_tick(pdt); stream_tick(pdt); follow_update(pdt);''')

# R7 (A) the stage auto-apply: tries reset only after the stage held 60 s; at most 12 auto-loads per launch
rep("A", "dumper.cpp", '''      if(g_emState==EM_ACTIVE&&g_emActive==wi&&wi>=0) g_stgTries=0;                      // in: a later loss gets fresh tries''',
    '''      { static double inSince=-1; bool in=g_emState==EM_ACTIVE&&g_emActive==wi&&wi>=0;   // held 60 s: a later loss gets fresh tries
        if(!in) inSince=-1; else if(inSince<0) inSince=mono_now(); else if(mono_now()-inSince>=60.0) g_stgTries=0; }''')
rep("A", "dumper.cpp", '''         &&settle>=4&&mono_now()>=nextAt&&g_stgTries<4){
          g_stgTries++; nextAt=mono_now()+60.0; g_emReq=wi;''',
    '''         &&settle>=4&&mono_now()>=nextAt&&g_stgTries<4){
          static int total=0; if(++total>12){ if(total==13) LOGI("[ENV] auto: 12 loads this launch: no more until the next launch"); g_stgGaveUp=true; return; }
          g_stgTries++; nextAt=mono_now()+60.0; g_emReq=wi;''')

# R3 (A) the env menu's kind: "2304" only once the world is up and the C++ class is still missing (an early resolve can
#    come before Tribe's classes are registered)
rep("A", "dumper.cpp", '''        else if(++tries>=3){ g_emMode=2; LOGI("[ENV] Blueprint menu (2304)"); } }''',
    '''        else if(g_worldUp&&++tries>=3){ g_emMode=2; LOGI("[ENV] Blueprint menu (2304)"); } }''')
rep("A", "dumper.cpp", '''    if(!g_emMode){                                       // which menu: Tribe 0.12.6's C++ one (2311) or the Blueprint one (2304)
        static int tries=0; uintptr_t c=find_by_path("/Script/TribeXR.TribeEnvironmentSkin",1);   // C++ classes exist from startup''',
    '''    if(!g_emMode){                                       // which menu: Tribe 0.12.6's C++ one (2311) or the Blueprint one (2304)
        static int tries=0; refresh_numelements(); uintptr_t c=find_by_path("/Script/TribeXR.TribeEnvironmentSkin",1);''')

# R11 (A) raw writes into Tribe's objects check the object's class first (a reused slot holding another class passes
#    obj_alive): the stream camera's capture timer, the intro's and the camera view's FOV
rep("A", "stream.cpp", '''static volatile uintptr_t g_stPC=0;                   // Tribe's player controller (poll thread): the stream camera's timer''',
    '''static volatile uintptr_t g_stPC=0, g_stPCCls=0;      // Tribe's player controller (poll thread): the stream camera's timer''')
rep("A", "stream.cpp", '''        g_stPC=pc; }''', '''        g_stPCCls=pc?rdptr(pc+OFF_Class):0; g_stPC=pc; }''')
rep("A", "stream.cpp", '''    uintptr_t pc=g_stPC; if(!pc||!obj_alive(pc)) return;''',
    '''    uintptr_t pc=g_stPC; if(!pc||!obj_alive(pc)||rdptr(pc+OFF_Class)!=g_stPCCls) return;   // (mod2311: the class too)''')
rep("A", "intro.cpp", '''    if(g_irFovSaved&&(fov<=0||cap!=g_irFovCap)){ if(g_irFovCap&&obj_alive(g_irFovCap)&&g_irFovOff>=0) *(float*)(g_irFovCap+g_irFovOff)=g_irFovOrig;''',
    '''    static uintptr_t fovCls=0;                                         // mod2311: raw writes only into the class we measured
    if(g_irFovSaved&&(fov<=0||cap!=g_irFovCap)){ if(g_irFovCap&&obj_alive(g_irFovCap)&&g_irFovOff>=0&&rdptr(g_irFovCap+OFF_Class)==fovCls) *(float*)(g_irFovCap+g_irFovOff)=g_irFovOrig;''')
rep("A", "intro.cpp", '''    if(cap!=g_irFovCap){ g_irFovCap=cap; uintptr_t fc=0; char ty[48]="?"; g_irFovOff=prop_offset(rdptr(cap+OFF_Class),"FOVAngle",&fc);''',
    '''    if(cap!=g_irFovCap){ g_irFovCap=cap; fovCls=rdptr(cap+OFF_Class); uintptr_t fc=0; char ty[48]="?"; g_irFovOff=prop_offset(fovCls,"FOVAngle",&fc);''')
rep("A", "intro.cpp", '''    if(g_irFovOff<0) return;
    float* p=(float*)(cap+g_irFovOff); if(!g_irFovSaved){ g_irFovOrig=*p; g_irFovSaved=true; }''',
    '''    if(g_irFovOff<0||rdptr(cap+OFF_Class)!=fovCls) return;
    float* p=(float*)(cap+g_irFovOff); if(!g_irFovSaved){ g_irFovOrig=*p; g_irFovSaved=true; }''')
rep("A", "camview.cpp", '''    if(g_cvFovSaved&&(want<=0||cap!=g_cvFovCap)){
        if(g_cvFovCap&&obj_alive(g_cvFovCap)&&g_cvFovOff>=0) *(float*)(g_cvFovCap+g_cvFovOff)=g_cvFovOrig;''',
    '''    static uintptr_t fovCls=0;                                         // mod2311: raw writes only into the class we measured
    if(g_cvFovSaved&&(want<=0||cap!=g_cvFovCap)){
        if(g_cvFovCap&&obj_alive(g_cvFovCap)&&g_cvFovOff>=0&&rdptr(g_cvFovCap+OFF_Class)==fovCls) *(float*)(g_cvFovCap+g_cvFovOff)=g_cvFovOrig;''')
rep("A", "camview.cpp", '''    if(cap!=g_cvFovCap){ g_cvFovCap=cap; uintptr_t fc=0; char ty[48]="?"; g_cvFovOff=prop_offset(rdptr(cap+OFF_Class),"FOVAngle",&fc);''',
    '''    if(cap!=g_cvFovCap){ g_cvFovCap=cap; fovCls=rdptr(cap+OFF_Class); uintptr_t fc=0; char ty[48]="?"; g_cvFovOff=prop_offset(fovCls,"FOVAngle",&fc);''')
rep("A", "camview.cpp", '''    if(g_cvFovOff<0) return;
    float* p=(float*)(cap+g_cvFovOff);''', '''    if(g_cvFovOff<0||rdptr(cap+OFF_Class)!=fovCls) return;
    float* p=(float*)(cap+g_cvFovOff);''')

# R10 (A) em_copy_identity: only between objects of the same class (it writes the source class's field offsets)
rep("A", "dumper.cpp", '''static int em_copy_identity(uintptr_t dst,uintptr_t src){
    int S=calib_fprop_size(); if(!dst||!src||S<0) return -1; char nm[128],ty[64]; int n=0;''',
    '''static int em_copy_identity(uintptr_t dst,uintptr_t src){
    int S=calib_fprop_size(); if(!dst||!src||S<0) return -1; char nm[128],ty[64]; int n=0;
    if(rdptr(dst+OFF_Class)!=rdptr(src+OFF_Class)){ static int w=0; if(w++<5) LOGI("[ENV] identity: not copied (the two objects' classes differ)"); return -1; }   // mod2311''')

# ---- step B fixes
# R3b (B) the avatar menu's kind: "2304" only once the world is up and the class is still missing after 3 looks
rep("B", "dumper.cpp", '''    if(!g_smMode){ g_smMode=find_by_path("/Script/TribeXR.TribeReadyPlayerMeAvatarSkin",1)?1:2;   // which avatar menu (step B)
        LOGI("[MENU] avatar menu kind: %s",g_smMode==1?"2311 (C++: TribeProfileMenuWidget, TribeSkinItemWidget, TribeReadyPlayerMeAvatarSkin)":"2304 (Blueprints)"); }''',
    '''    if(!g_smMode&&(tk%4)==1){ static int misses=0; refresh_numelements();   // which avatar menu (step B); "2304" only once the
        if(find_by_path("/Script/TribeXR.TribeReadyPlayerMeAvatarSkin",1)) g_smMode=1;   // world is up and the class is still missing
        else if(g_worldUp&&++misses>=3) g_smMode=2;
        if(g_smMode) LOGI("[MENU] avatar menu kind: %s",g_smMode==1?"2311 (C++: TribeProfileMenuWidget, TribeSkinItemWidget, TribeReadyPlayerMeAvatarSkin)":"2304 (Blueprints)"); }''')
# R6 (B) Tribe-apply branch: its engine calls inside the busy flag, like the press branch
rep("B", "dumper.cpp", '''            if(!pressed) sm_pick(idx); }
        else if(pressed&&sm_is_tribe_avatar(sk)) sm_pick_tribe("Tribe applied its own avatar right after a press");
        return; }''', '''            if(!pressed&&ue_enter()){ sm_pick(idx); ue_leave(); } }
        else if(pressed&&sm_is_tribe_avatar(sk)&&ue_enter()){ sm_pick_tribe("Tribe applied its own avatar right after a press"); ue_leave(); }
        return; }''')
# R9 (B) a box whose identity couldn't be set is tried again (5 s apart, 4 times), not left out for the session
rep("B", "dumper.cpp", '''static int g_smOffWSkin=-1, g_smIdentOk[SM_MAX]; static uint64_t g_smNameRpm=0;''',
    '''static int g_smOffWSkin=-1, g_smIdentOk[SM_MAX], g_smIdentTries[SM_MAX]; static uint64_t g_smNameRpm=0;''')
rep("B", "dumper.cpp", '''            g_smItems[i]=sm_spawn(g_smRpmCls,outer); spawns++; g_smIdentOk[i]=0;''',
    '''            g_smItems[i]=sm_spawn(g_smRpmCls,outer); spawns++; g_smIdentOk[i]=0; g_smIdentTries[i]=0;''')
rep("B", "dumper.cpp", '''        if(g_smItems[i]&&!g_smIdentOk[i]){ g_smIdentOk[i]=sm_identity(g_smItems[i])?1:-1;''',
    '''        if(g_smItems[i]&&g_smIdentOk[i]<0&&g_smIdentTries[i]<4&&(win%5)==0) g_smIdentOk[i]=0;   // try again (5 s apart)
        if(g_smItems[i]&&!g_smIdentOk[i]){ g_smIdentTries[i]++; g_smIdentOk[i]=sm_identity(g_smItems[i])?1:-1;''')
# R1b (B) the avatar boxes have their own kill switch (the review: Tribe builds its box for our near-empty item natively;
#    the characters doc flags a possible thumbnail fetch for it): tribemod/skin_boxes_off = no boxes, the rest of B stays
rep("B", "dumper.cpp", '''    uintptr_t list=g_smList; int n=g_smCount; g_smListLive=(list&&obj_alive(list))?1:0;
    if(!g_smListLive||!g_smRpmCls||!g_smFnSpawn||!g_smFnAddItem||!g_smFnIndexOf||n<=0) return;''',
    '''    uintptr_t list=g_smList; int n=g_smCount; g_smListLive=(list&&obj_alive(list))?1:0;
    if(g_smBoxesOff) return;                                                 // tribemod/skin_boxes_off (kill switch)
    if(!g_smListLive||!g_smRpmCls||!g_smFnSpawn||!g_smFnAddItem||!g_smFnIndexOf||n<=0) return;''')
rep("B", "dumper.cpp", '''static volatile sig_atomic_t g_smDiagReq=0, g_smKeepTribeAvatar=0; static int g_smDiagDone=0;''',
    '''static volatile sig_atomic_t g_smDiagReq=0, g_smKeepTribeAvatar=0, g_smBoxesOff=0; static int g_smDiagDone=0;''')
rep("B", "dumper.cpp", '''    g_smKeepTribeAvatar=file_present("tribe_avatar_shown")?1:0;              // kill switch: Tribe's avatar stays visible''',
    '''    g_smKeepTribeAvatar=file_present("tribe_avatar_shown")?1:0;              // kill switch: Tribe's avatar stays visible
    { int bo=file_present("skin_boxes_off")?1:0; if(bo!=g_smBoxesOff){ g_smBoxesOff=bo; LOGI("[MENU] avatar boxes %s (tribemod/skin_boxes_off)",bo?"OFF":"on"); } }''')
rep("B", "dumper.cpp", '''            if(ix<0){ sm_list_add(list,g_smItems[i]); ix=sm_list_index(list,g_smItems[i]); LOGI("[MENU] added box '%s' (index %d)",g_smLabels[i],ix); }''',
    '''            if(ix<0){ LOGI("[MENU] adding box '%s' (a crash right after this line: tribemod/skin_boxes_off turns the boxes off)",g_smLabels[i]);
                sm_list_add(list,g_smItems[i]); ix=sm_list_index(list,g_smItems[i]); LOGI("[MENU] added box '%s' (index %d)",g_smLabels[i],ix); }''')
rep("B", "dumper.cpp", '''      if(!smOn) snprintf(menus+k2,sizeof menus-k2,",avatar:off");''',
    '''      if(!smOn||g_smBoxesOff) snprintf(menus+k2,sizeof menus-k2,",avatar:off");''')

for fn, s in files.items():
    open(src + "/" + fn, "w", encoding="utf-8", newline="").write(s)
print("ok", step, sorted(files))
