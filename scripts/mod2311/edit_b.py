#!/usr/bin/env python3
"""Step B edit (characters) on top of step A: the avatar menu on 2311's C++ classes with the press-time block of Tribe's
apply (C4b), Tribe's own avatar hidden/shown, a "Tribe Avatar" box, no mesh on Tribe's slot (C8), the one-time
diagnostic (C11), the Ready Player Me settings left to Tribe (note 19). Exact-string edits."""
import sys

p = sys.argv[1]
s = open(p, encoding="utf-8", newline="").read()


def rep(old, new, cnt=1):
    global s
    n = s.count(old)
    assert n == cnt, (n, old[:100])
    s = s.replace(old, new)


rep('#define MOD2311_STEP "A"', '#define MOD2311_STEP "B"')

# ------------------------------------------------------------------ the RPM keys: left to Tribe (note 19)
rep('''static void ini_upsert(){
    // mod2311: when tribemod/ can't be read yet (the first launch after an install), every file reads as absent and the
    // edits below would delete keys (the RPM URL, body tracking). Leave both ini files as they are then.
    if(tribemod_state()<0){ LOGI("[INI] tribemod/ is not readable yet: both ini files left as they are this launch"); return; }
    char url[1024], etag[256]; bool hu=read_trim_file("avatar_url.txt",url,sizeof url);
    bool he=read_trim_file("avatar_etag.txt",etag,sizeof etag);
    if(hu && (url[0]=='+'||url[0]=='-'||url[0]=='.'||url[0]=='!')){ ini_status("WARN url op-char; unset"); hu=false; }
    if(hu) stage_cache(url);            // cache slot => cache HIT (local glTF load, no network)
    // UE ini truncates an UNQUOTED value at "//" -> quote the URL (matches Tribe's own DataRouterUrl="...")
    char qurl[1100]; snprintf(qurl,sizeof qurl,"\\"%s\\"",url);
    upsert_ini_key("ReadyPlayerMeAvatarUrl", hu?qurl:0);
    upsert_ini_key("ReadyPlayerMeETag",      he?etag:0);   // ETag present => FUN_050f584c takes the cache-hit branch
    char m[1400]; snprintf(m,sizeof m,"summary: url=%s etag=%s",hu?qurl:"(none)",he?etag:"(none)"); ini_status(m);''',
    '''static bool ini_flag(const char* name){ char p[600]; snprintf(p,sizeof p,"%s/%s",OUTDIR,name); int fd=open(p,O_RDONLY); if(fd>=0) close(fd); return fd>=0; }
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
        char qurl[1100]; snprintf(qurl,sizeof qurl,"\\"%s\\"",url);
        upsert_ini_key("ReadyPlayerMeAvatarUrl", hu?qurl:0);
        upsert_ini_key("ReadyPlayerMeETag",      he?etag:0);   // ETag present => FUN_050f584c takes the cache-hit branch
        if(hu) ini_url_cut(url,cut,sizeof cut); char m[400]; snprintf(m,sizeof m,"rpm_route_on: url=%s etag=%s",hu?cut:"(none)",he?"(set)":"(none)"); ini_status(m); }
    else if(read_trim_file("rpm_url_set.txt",url,sizeof url)){
        char p[600],q[620]; snprintf(p,sizeof p,"%s/rpm_url_set.txt",OUTDIR); snprintf(q,sizeof q,"%s/rpm_url_set.done",OUTDIR);
        ini_url_cut(url,cut,sizeof cut);
        if(strncmp(url,"http://",7)&&strncmp(url,"https://",8)){ char m[300]; snprintf(m,sizeof m,"rpm_url_set.txt: not an http(s) URL (%s): nothing written",cut); ini_status(m); }
        else { char qurl[1100]; snprintf(qurl,sizeof qurl,"\\"%s\\"",url);
            upsert_ini_key("ReadyPlayerMeAvatarUrl",qurl); upsert_ini_key("ReadyPlayerMeETag",0);   // no ETag: Tribe loads it fresh
            char m[300]; snprintf(m,sizeof m,"rpm_url_set.txt: Tribe's Ready Player Me URL set once to %s",cut); ini_status(m); }
        rename(p,q); }
    else if(ini_flag("rpm_url_clear")){
        char p[600]; snprintf(p,sizeof p,"%s/rpm_url_clear",OUTDIR);
        upsert_ini_key("ReadyPlayerMeAvatarUrl",0); upsert_ini_key("ReadyPlayerMeETag",0); unlink(p);
        ini_status("rpm_url_clear: Tribe's Ready Player Me URL and ETag deleted once"); }
    else ini_status("Ready Player Me keys: left as Tribe has them (no rpm_route_on, rpm_url_set.txt or rpm_url_clear)");''')
# the ini log printed the value of every key it set: cut a URL-looking value to its host
rep('''    char m[300]; snprintf(m,sizeof m,"%s: %s (%d->%d bytes)",key,have?"SET":"DELETED",n,o); ini_status(m);''',
    '''    char m[300]; snprintf(m,sizeof m,"%s: %s (%d->%d bytes)",key,have?"SET":"DELETED",n,o); ini_status(m);   // (sizes only)''')

# ------------------------------------------------------------------ do_load: not on Tribe's slot on 2311 (C8)
rep('''static void head_skin_loaded(const char* skin,uintptr_t libCDO,uintptr_t fnLoad);   // head.cpp: heads/<skin>.glb after a skin load''',
    '''static void head_skin_loaded(const char* skin,uintptr_t libCDO,uintptr_t fnLoad);   // head.cpp: heads/<skin>.glb after a skin load
// which avatar menu (mod2311 step B; set by the supervisor): 0 not known yet, 1 = 2311's C++ classes, 2 = 2304's Blueprints
static volatile sig_atomic_t g_smMode=0;''')
rep('''    if(body){ attach_mesh(body,mesh); g_body=body; g_keep=1; }''',
    '''    if(body&&g_smMode==2){ attach_mesh(body,mesh); g_body=body; g_keep=1; }   // 2304 only (mod2311 step B, characters doc C8)
    else if(body) load_status("2311: Tribe's AvatarBodyMesh left to Tribe (no copy at the world origin, no keeper); Tribe's own avatar is hidden while a mod skin is on");''')

# ------------------------------------------------------------------ menu state (declared before menu_tick)
rep('''static long g_smLastClickMs=0;''',
    '''static long g_smLastClickMs=0; static int g_smLastClickIdx=-1;
// 2311 (mod2311 step B): 0 = not known yet, 1 = Tribe 0.12.6's C++ menu (TribeReadyPlayerMeAvatarSkin exists), 2 = 2304
static volatile sig_atomic_t g_smTribeMode=0, g_smAdded=0, g_smListLive=0;
static void menu_tick_2311();''')
# sm_load: the same box within 3 s is one click (two Lampwing loads stalled Tribe on 2026-10-10)
rep('''    if(ms-g_smLastClickMs<700) return; g_smLastClickMs=ms;                    // both entry points fire for one click''',
    '''    if(ms-g_smLastClickMs<(idx==g_smLastClickIdx?3000:700)) return; g_smLastClickMs=ms; g_smLastClickIdx=idx;   // one click''')
rep('''    if(!g_skinMenuOn||tripped||(++tk%60)!=0) return;                         // ~once a second''',
    '''    if(!g_skinMenuOn||tripped||(++tk%60)!=0) return;                         // ~once a second
    if(g_smMode==1){ menu_tick_2311(); return; }                             // 2311: its own path (below)''')

# ------------------------------------------------------------------ the 2311 avatar menu + Tribe's avatar (after em_pool_scan)
BLOCK = r'''// ============ 2311: the avatar menu and Tribe's own avatar (mod2311 step B; claudedocs/mod_2311_characters.md) ============
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
static int g_smOffWSkin=-1, g_smIdentOk[SM_MAX]; static uint64_t g_smNameRpm=0;
static volatile sig_atomic_t g_smDiagReq=0, g_smKeepTribeAvatar=0; static int g_smDiagDone=0;
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
            if(!pressed) sm_pick(idx); }
        else if(pressed&&sm_is_tribe_avatar(sk)) sm_pick_tribe("Tribe applied its own avatar right after a press");
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
    if(!g_smListLive||!g_smRpmCls||!g_smFnSpawn||!g_smFnAddItem||!g_smFnIndexOf||n<=0) return;
    uintptr_t outer=(g_smTribeRpm&&obj_alive(g_smTribeRpm))?rdptr(g_smTribeRpm+OFF_Outer):list;   // fallback: the list
    int added=0;
    for(int i=0;i<n&&i<SM_MAX;i++){
        if(!obj_alive(g_smItems[i])){
            if(spawns>=3*n){ tripped=true; LOGI("[MENU] guard: %d respawns in 30 s -> stopped adding boxes (bug guard)",spawns); return; }
            g_smItems[i]=sm_spawn(g_smRpmCls,outer); spawns++; g_smIdentOk[i]=0;
            LOGI("[MENU] spawned skin object for '%s' = 0x%lx",g_smLabels[i],(unsigned long)g_smItems[i]); }
        if(g_smItems[i]&&!g_smIdentOk[i]){ g_smIdentOk[i]=sm_identity(g_smItems[i])?1:-1;
            LOGI("[MENU] '%s': identity %s",g_smLabels[i],g_smIdentOk[i]>0?"Name=ReadyPlayerMe_Custom bOwned=1":
                 "NOT set: this box is not added (a press could change your saved Tribe avatar)"); }
        if(g_smItems[i]&&g_smIdentOk[i]>0){ int ix=sm_list_index(list,g_smItems[i]);
            if(ix<0){ sm_list_add(list,g_smItems[i]); ix=sm_list_index(list,g_smItems[i]); LOGI("[MENU] added box '%s' (index %d)",g_smLabels[i],ix); }
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
'''
rep('''static void em_log_actor(const char* what,uintptr_t a){                      // world location / rotation / scale (layout reference)''',
    BLOCK + '''static void em_log_actor(const char* what,uintptr_t a){                      // world location / rotation / scale (layout reference)''')

# ------------------------------------------------------------------ poll side: list, Tribe's RPM item, lookups, boxes
rep('''static uintptr_t sm_find_avatar_list(){                 // the LIVE W_ProfileMenu AvatarList (not the /Game class template)
    char nm[96],cn[96],fp[400];''',
    '''static uintptr_t sm_find_avatar_list(){                 // the LIVE W_ProfileMenu AvatarList (not the /Game class template)
    if(g_smMode==1){                                     // 2311: the live TribeProfileMenuWidget's AvatarList (@0x398, a UListView)
        uintptr_t m=em_find_live("TribeProfileMenuWidget"); uintptr_t l=sm_obj_prop(m,"AvatarList");
        if(l&&obj_alive(l)&&em_is_a(l,"ListView")) return l; }
    char nm[96],cn[96],fp[400];''')
rep('''    bool same=(n==g_smCount); for(int i=0;same&&i<n;i++) if(strcmp(names[i],g_smFiles[i])) same=false;
    if(same) return;
    for(int i=0;i<n;i++){ strcpy(g_smFiles[i],names[i]); size_t L=strlen(names[i])-4; int k=0;
        for(size_t c=0;c<L&&k<63;c++){ char ch=names[i][c]; g_smLabels[i][k++]=(ch=='_')?' ':ch; } g_smLabels[i][k]=0;
        if(g_smLabels[i][0]>='a'&&g_smLabels[i][0]<='z') g_smLabels[i][0]-=32; }''',
    '''    bool tribeBox=g_smMode==1&&n<SM_MAX; if(tribeBox) strcpy(names[n++],"tribe");   // 2311: the last box is "Tribe Avatar"
    bool same=(n==g_smCount); for(int i=0;same&&i<n;i++) if(strcmp(names[i],g_smFiles[i])) same=false;
    if(same) return;
    for(int i=0;i<n;i++){ strcpy(g_smFiles[i],names[i]);
        if(!strcmp(names[i],"tribe")){ snprintf(g_smLabels[i],sizeof g_smLabels[i],"Tribe Avatar"); continue; }
        size_t L=strlen(names[i])-4; int k=0;
        for(size_t c=0;c<L&&k<63;c++){ char ch=names[i][c]; g_smLabels[i][k++]=(ch=='_')?' ':ch; } g_smLabels[i][k]=0;
        if(g_smLabels[i][0]>='a'&&g_smLabels[i][0]<='z') g_smLabels[i][0]-=32; }''')
rep('''static uintptr_t sm_find_live_rpm_skin(){              // any live (non-CDO) BP_ReadyPlayerMeAvatarSkin_C -> outer for ours
    char cn[96],fp[400];
    for(uint32_t i=0;i<g_numElements;i++){ uintptr_t o=obj_at(i); if(!o||sm_item_idx(o)>=0) continue;
        class_name(o,cn,sizeof cn); if(strcmp(cn,"BP_ReadyPlayerMeAvatarSkin_C")) continue;''',
    '''static uintptr_t sm_find_live_rpm_skin(){              // any live (non-CDO) RPM skin item that isn't ours -> outer + identity
    char cn[96],fp[400];
    for(uint32_t i=0;i<g_numElements;i++){ uintptr_t o=obj_at(i); if(!o||sm_item_idx(o)>=0) continue;
        class_name(o,cn,sizeof cn); if(strcmp(cn,"BP_ReadyPlayerMeAvatarSkin_C")&&strcmp(cn,"TribeReadyPlayerMeAvatarSkin")) continue;   // 2304 / 2311''')
rep('''static void skin_menu_poll(){
    bool on=file_present("skin_menu");
    if(!on){ if(g_skinMenuOn){ g_skinMenuOn=0; LOGI("[MENU] OFF"); } return; }
    if(!g_resolved) return;                              // mod2311: the lookups need the object array (all 0 before it)
    static int tick=0; tick++;
    menu_resolve_engine_fns();''',
    '''// 2311 (poll thread): the C++ menu's lookups, the live AvatarList, Tribe's RPM item, the one-time diagnostic, ON/OFF
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
    if(g_smMode==1&&file_present("skin_diag")){ char dp[600]; snprintf(dp,sizeof dp,"%s/skin_diag",OUTDIR); unlink(dp); sm_diag_poll(g_smList); }   // one-shot
    bool on=file_present("skin_menu");
    if(!on){ if(g_skinMenuOn){ g_skinMenuOn=0; LOGI("[MENU] OFF"); } return; }
    if(!g_resolved||!g_smMode) return;                   // mod2311: the lookups need the object array (all 0 before it)
    static int tick=0; tick++;
    menu_resolve_engine_fns();
    if(g_smMode==1){ sm_poll_2311(tick); return; }''')

# ------------------------------------------------------------------ repl_pe: the press / apply handler, the per-second tick
rep('''    if(g_envMenuOn && func && parms && (func==(void*)g_emFnUWDown||func==(void*)g_emFnSkinApplied))   // 2311 boxes: press / apply
        em_pe_2311((uintptr_t)self,(uintptr_t)func,parms);                  // (both 0 on 2304)''',
    '''    if(g_envMenuOn && func && parms && (func==(void*)g_emFnUWDown||func==(void*)g_emFnSkinApplied))   // 2311 boxes: press / apply
        em_pe_2311((uintptr_t)self,(uintptr_t)func,parms);                  // (both 0 on 2304)
    if(g_skinMenuOn && g_smMode==1 && func && parms && (func==(void*)g_smFnUWDown||func==(void*)g_smFnSkinApplied))   // avatar boxes (B)
        sm_pe_2311((uintptr_t)self,(uintptr_t)func,parms);''')
rep('''head_tick(pdt); menu_tick(); env_menu_tick(); perf_frame(pdt); ue_leave(); } } }''',
    '''head_tick(pdt); menu_tick(); sm_tick_2311(); env_menu_tick(); perf_frame(pdt); ue_leave(); } } }''')
rep('''        spawn_iso_actor(g_mymesh); ue_leave();''', '''        spawn_iso_actor(g_mymesh); g_smActorHid=0; ue_leave();''')

# ------------------------------------------------------------------ supervisor: the menu kind, Tribe mode, [READY] avatar boxes
rep('''    char sk[128]=""; bool haveSk=read_trim_file("active_skin.txt",sk,sizeof sk); bool tribe=haveSk&&!strcmp(sk,"tribe");
    snprintf(g_avSkin,sizeof g_avSkin,"%s",haveSk?sk:"(none)");''',
    '''    char sk[128]=""; bool haveSk=read_trim_file("active_skin.txt",sk,sizeof sk); bool tribe=haveSk&&!strcmp(sk,"tribe");
    snprintf(g_avSkin,sizeof g_avSkin,"%s",haveSk?sk:"(none)");
    if(!g_smMode){ g_smMode=find_by_path("/Script/TribeXR.TribeReadyPlayerMeAvatarSkin",1)?1:2;   // which avatar menu (step B)
        LOGI("[MENU] avatar menu kind: %s",g_smMode==1?"2311 (C++: TribeProfileMenuWidget, TribeSkinItemWidget, TribeReadyPlayerMeAvatarSkin)":"2304 (Blueprints)"); }
    g_smTribeMode=tribe?1:0;                                             // Tribe's own avatar picked last (the menu writes it)''')
rep('''    else { snprintf(menus,sizeof menus,"env%d/%d",(int)g_emAdded,(int)g_emCount); need(g_emAdded>=g_emCount,"menus",menus); }''',
    '''    else { snprintf(menus,sizeof menus,"env%d/%d",(int)g_emAdded,(int)g_emCount); need(g_emAdded>=g_emCount,"menus",menus); }
    { int k2=(int)strlen(menus); bool smOn=file_present("skin_menu");      // the avatar boxes (step B), once the list exists
      if(!smOn) snprintf(menus+k2,sizeof menus-k2,",avatar:off");
      else if(g_smMode!=1||!g_smListLive) snprintf(menus+k2,sizeof menus-k2,",avatar:list-not-open");
      else { snprintf(menus+k2,sizeof menus-k2,",avatar%d/%d",(int)g_smAdded,(int)g_smCount); need(g_smAdded>=g_smCount,"menus",menus); } }''')
open(p, "w", encoding="utf-8", newline="").write(s)
print("ok")
