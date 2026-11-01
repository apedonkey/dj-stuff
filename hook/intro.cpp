// intro.cpp: a stage's stream intro, first used for the Headless Horseman's ride on Graveyard Shift (the spec and the
// files: the Halloween session, 2026-10-10; this file: the Dino session). dumper.cpp includes it after club.cpp and calls
// intro_lookup (poll thread, env_menu_poll) and intro_tick (game thread, after club_tick). Inert unless the stage that's
// up has tribemod/intro.<folder>.txt (format and ride math: hook/intro_ride.h). Logs [INTRO].
//
// The user: "a button backstage that when I press it, the venue gets dark, starts the visuals. I could load up the song on
// the deck before I go back there and before streaming. So the button is mapped to the play button on that deck."
// Three presses on the backstage button (either hand within r cm; re-armed 8 cm further out, 1.2 s apart):
//   1 the pre-show: the venue goes dark (ShowLevel 0), the door eases shut, Tribe's backdrop video rewinds and pauses,
//     the woods and the rider appear, he rides the loop and the stream camera rides with him (the drone's target: the
//     selfie stick, or the Auto cam with drone.txt target=auto)
//   2 he finishes the lap and takes the exit; the camera blends to its exit offsets over 5 s and holds still from
//     camhold; at the exit's end he is hidden
//   3 showtime (queued until the camera holds): the cut to the wide shot, the woods hidden, any other playing deck
//     stopped; 'hold' s later the deck sitting at its cue point plays (tribemod/intro_deck.txt says how), the video plays,
//     the door rises and the lights take the song. The camera goes back to its mount (or to the drone) when the user
//     reaches the decks spot, or 'back' s after the music started.
// One intro per stage load: after showtime the button does nothing until the stage loads again.
#include "intro_ride.h"

// ---- poll thread -> game thread
static IRide g_irRide[2]; static volatile sig_atomic_t g_irIdx=-1;   // double buffer: the game thread reads g_irIdx's
static char g_irFile[64]="";                                       // intro.<folder>.txt of the stage that's up
static volatile uintptr_t g_irRider=0, g_irWoods[IR_MAXN];
// screen <actor>: a backstage monitor. The game thread gives its mesh the material of the selfie stick's preview plane
// (Tribe's M_SelfiePreview: the selfie capture, which the intro flies), so the user waiting at the button sees the stream.
static volatile uintptr_t g_irScreen=0, g_irPlane=0, g_irPreviewMat=0;
static volatile uintptr_t g_irBtnActor=0;                           // HARVEST MOON: buttonactor (the cap the hand pushes down)
static uintptr_t g_irFnGetMat=0, g_irFnSetMat=0;
static uintptr_t g_irMP=0, g_irFnPlay=0, g_irFnPause=0, g_irFnRewind=0, g_irFnIsPlaying=0;   // Tribe's backdrop video
static uintptr_t g_irFnAtCue=0; static int g_irAtCueOut=-1;         // the deck class's IsAtCue (BP_Deck_C / 2311 TribeDeck)
static uintptr_t g_irBtnCls=0, g_irFnEquip=0; static int g_irEquipOut=-1;   // BP_PlayButton_C.GetTribeEquipmentBase (2304)
static int g_irBtnDeckOff=-1;                                      // 2311: TribePlayButton.Deck (that function is gone)
static uintptr_t g_irBtns[16]; static volatile int g_irNBtn=0;    // the live play buttons (for "button:" calls)
// how the intro presses Play on the cued deck and stops the others: tribemod/intro_deck.txt (re-read when it changes),
// written after the deck capture (tribemod/log_deck) shows what a real press calls:
//   play deck:<Function> [param=value ...]      BP_Deck_C.<Function> (2311: TribeDeck) on the deck sitting at its cue point
//   stop deck:<Function> [param=value ...]      ... on every other deck that is playing
// "button:<Function>" calls it on that deck's BP_PlayButton_C (2311: TribePlayButton) instead. Values: a number, true / false, or (an object)
// hand_l, hand_r, pawn, deck, none. No file: showtime leaves the decks alone and says so.
struct IDCall { int on, button, na; char fn[64], an[6][48], av[6][32]; uintptr_t f; };
static IDCall g_idc[2][2]; static volatile sig_atomic_t g_idcIdx=-1; // [buffer][0 play, 1 stop]

static int g_irMiss=0;                                             // actor lookups that came up short (backs off; a new stage resets it)
static bool ir_icontains(const char* hay,const char* nd){            // case-insensitive substring
    size_t n=strlen(nd); for(; *hay; hay++){ size_t i=0; while(i<n&&hay[i]&&tolower((unsigned char)hay[i])==tolower((unsigned char)nd[i])) i++;
        if(i==n) return true; }
    return false; }
// the stage's placed actors by object name, in one pass (the stage's build renames them; labels don't survive the cook)
static void intro_find_actors(const IRide* r,const char* folder){
    const char* want[3+IR_MAXN]; volatile uintptr_t* slot[3+IR_MAXN]; int n=0;
    if(r->rider[0]&&(!g_irRider||!obj_alive(g_irRider))){ want[n]=r->rider; slot[n++]=&g_irRider; }
    if(r->screen[0]&&(!g_irScreen||!obj_alive(g_irScreen))){ want[n]=r->screen; slot[n++]=&g_irScreen; }
    if(r->btnActor[0]&&(!g_irBtnActor||!obj_alive(g_irBtnActor))){ want[n]=r->btnActor; slot[n++]=&g_irBtnActor; }
    for(int i=0;i<r->nwoods;i++) if(!g_irWoods[i]||!obj_alive(g_irWoods[i])){ want[n]=r->woods[i]; slot[n++]=&g_irWoods[i]; }
    if(!n) return;
    int& miss=g_irMiss; if(miss>=15&&(miss++%10)) return;            // still missing after ~30 s: look every ~20 s
    char nm[96], cn[96], fp[400], in[64]; snprintf(in,sizeof in,"/Mods/%s/",folder); int found=0;
    uintptr_t alt[3+IR_MAXN]={0};                                     // same name in a level whose path lacks our folder
    refresh_numelements();
    for(uint32_t i=0;i<g_numElements&&found<n;i++){ uintptr_t o=obj_at(i); if(!o) continue;
        obj_name(o,nm,sizeof nm); int k=-1; for(int j=0;j<n;j++) if(!*slot[j]&&!strcmp(nm,want[j])) k=j;
        if(k<0) continue;
        if(rd32(o+OFF_Flags)&(RF_ClassDefaultObject|0x20u)) continue;
        class_name(o,cn,sizeof cn); size_t L=strlen(cn); if(L<5||strcmp(cn+L-5,"Actor")) continue;
        full_path(o,fp,sizeof fp); if(!strstr(fp,"PersistentLevel")) continue;
        if(!ir_icontains(fp,in)){ if(!alt[k]) alt[k]=o; continue; }
        *slot[k]=o; found++; LOGI("[INTRO] found %s: 0x%lx (%s)",want[k],(unsigned long)o,cn); }
    for(int j=0;j<n;j++) if(!*slot[j]&&alt[j]){ *slot[j]=alt[j]; found++; full_path(alt[j],fp,sizeof fp);
        LOGI("[INTRO] found %s outside %s: 0x%lx at %s (taken)",want[j],in,(unsigned long)alt[j],fp); }
    if(found<n){ if(miss<15) miss++; if(miss==1||miss==15) for(int j=0;j<n;j++) if(!*slot[j])
        LOGI("[INTRO] '%s' isn't in the stage (yet)%s",want[j],slot[j]==&g_irRider?": the camera rides the path alone":""); }
    else miss=0; }
static void intro_read_deck_cfg(){                                   // POLL thread; until its classes load, retried ~1 min
    static long lastKey=-2; static int tries=0, wasOn[2]={0,0}; static bool resolved=false;
    char p[600]; snprintf(p,sizeof p,"%s/intro_deck.txt",OUTDIR); struct stat st;
    long key=stat(p,&st)==0?(long)st.st_mtime*1000003L+(long)st.st_size:-1;
    if(key!=lastKey){ lastKey=key; tries=0; resolved=false; wasOn[0]=wasOn[1]=0; }
    else if(resolved||tries>=30||!g_sCls) return;
    tries++;
    if(!g_irBtnCls&&g_sCls){ char mc[48]; class_name(g_sCls,mc,sizeof mc);   // the decks are C++ (2311: TribePlayButton) or Blueprints (2304)
        g_irBtnCls=find_by_path(strcmp(mc,"Class")?"/Game/Equipment/Deck/PlayPause/BP_PlayButton.BP_PlayButton_C":"/Script/TribeXR.TribePlayButton",1);
        if(g_irBtnCls){ g_irFnEquip=em_find_child_func(g_irBtnCls,"GetTribeEquipmentBase"); char ty[48]="?"; g_irEquipOut=fn_out(g_irFnEquip,ty,sizeof ty);
            uintptr_t fc=0; char dt[48]="?"; g_irBtnDeckOff=g_irFnEquip?-1:prop_offset(g_irBtnCls,"Deck",&fc); if(fc) fname_resolve(rd32(fc),dt,sizeof dt);
            if(g_irBtnDeckOff>=0&&strcmp(dt,"ObjectProperty")) g_irBtnDeckOff=-1;
            char bn[64]; obj_name(g_irBtnCls,bn,sizeof bn);
            LOGI("[INTRO] play buttons: %s 0x%lx, its deck by %s",bn,(unsigned long)g_irBtnCls,g_irFnEquip?"GetTribeEquipmentBase()":
                 g_irBtnDeckOff>=0?"the Deck property":"NOTHING (button: calls can't find their button)"); } }
    int nx=g_idcIdx==0?1:0; IDCall* c=g_idc[nx]; memset(c,0,2*sizeof(IDCall));
    char s[1200]=""; if(key!=-1) read_trim_file("intro_deck.txt",s,sizeof s);
    bool all=true; char* save=0;
    for(char* ln=strtok_r(s,"\n",&save); ln; ln=strtok_r(0,"\n",&save)){
        char* h=strchr(ln,'#'); if(h) *h=0; char* tk[8]; int nt=0; char* s2=0;
        for(char* t=strtok_r(ln," \t\r",&s2); t&&nt<8; t=strtok_r(0," \t\r",&s2)) tk[nt++]=t;
        if(nt<2) continue; int w=!strcmp(tk[0],"play")?0:!strcmp(tk[0],"stop")?1:-1; char* colon=strchr(tk[1],':');
        if(w<0||!colon){ if(tries==1) LOGI("[INTRO] intro_deck.txt: '%s %s' not understood (play|stop deck:|button:<Function>)",tk[0],tk[1]); continue; }
        *colon=0; IDCall* d=&c[w]; d->button=!strcmp(tk[1],"button"); snprintf(d->fn,sizeof d->fn,"%s",colon+1);
        for(int i=2;i<nt&&d->na<6;i++){ char* eq=strchr(tk[i],'='); if(!eq) continue; *eq=0;
            snprintf(d->an[d->na],48,"%s",tk[i]); snprintf(d->av[d->na],32,"%s",eq+1); d->na++; }
        uintptr_t cls=d->button?g_irBtnCls:g_sCls; d->f=cls?em_find_child_func(cls,d->fn):0;
        d->on=d->f!=0; if(!d->on) all=false;                          // its class isn't loaded yet: look again
        if(tries==1||(d->on&&!wasOn[w])){ char pl[300]=""; int k=0;
            for(uintptr_t f=d->f?rdptr(d->f+OFF_ChildProps):0; f&&k<(int)sizeof pl-60; f=rdptr(f+FF_Next)){ char pn[64], ty[48];
                fname_resolve(rd32(f+FF_Name),pn,sizeof pn); ffield_type(f,ty,sizeof ty); k+=snprintf(pl+k,sizeof pl-k," %s:%s",pn,ty); }
            LOGI("[INTRO] intro_deck.txt: %s = %s:%s (%s) params:%s",tk[0],d->button?"button":"deck",d->fn,d->on?"found":"not found yet",k?pl:" none"); }
        wasOn[w]=d->on; }
    __sync_synchronize(); g_idcIdx=nx; resolved=all;
    if(key==-1&&tries==1) LOGI("[INTRO] no intro_deck.txt yet: showtime won't touch the decks (the deck capture, tribemod/log_deck, shows what to call)"); }
static void intro_lookup(){                                          // POLL thread (env_menu_poll), about every 2 s
    char fol[48]="", want[64]="";
    if(em_active_folder(fol,sizeof fol)) snprintf(want,sizeof want,"intro.%s.txt",fol);
    static long lastKey=-2;
    if(strcmp(want,g_irFile)){ snprintf(g_irFile,sizeof g_irFile,"%s",want); g_irIdx=-1; lastKey=-2; g_introArmed=0;
        g_irRider=0; g_irScreen=0; g_irBtnActor=0; for(int i=0;i<IR_MAXN;i++) g_irWoods[i]=0; g_irMiss=0; }
    if(!want[0]) return;
    char p[600]; snprintf(p,sizeof p,"%s/%s",OUTDIR,want); struct stat st;
    long key=stat(p,&st)==0?(long)st.st_mtime*1000003L+(long)st.st_size:-1;
    if(key!=lastKey){ lastKey=key;
        if(key==-1){ if(g_irIdx>=0) LOGI("[INTRO] tribemod/%s is gone: no intro",want); g_irIdx=-1; g_introArmed=0; }
        else { static char text[1<<17]; text[0]=0; FILE* f=fopen(p,"rb"); size_t n=0; if(f){ n=fread(text,1,sizeof text-1,f); fclose(f); } text[n]=0;
            int nx=g_irIdx==0?1:0;
            if(ir_parse(&g_irRide[nx],text)){ __sync_synchronize(); g_irIdx=nx; const IRide* r=&g_irRide[nx];
                LOGI("[INTRO] %s: %d keys, loop %.2f..%.2f s, exit to %.2f s, camera holds at %.2f s; button (%.0f,%.0f,%.0f) r %.0f cm; "
                     "rider %s, %d woods actor(s); %s / %s (door %.1f s); hold %.1f s, back %.0f s, fov ride %.0f wide %.0f%s",want,r->nk,
                     r->loop0,r->loop1,r->exit1,r->camhold,r->btn[0],r->btn[1],r->btn[2],r->btnR,r->rider,r->nwoods,r->step,r->doorName,
                     r->door,r->hold,r->back,r->fovRide,r->fovWide,r->bad?" (some lines not understood)":""); }
            else LOGI("[INTRO] %s did not parse as a ride (keys, loop, exit): %s",want,g_irIdx>=0?"keeping the old one":"no intro"); } }
    int ix=g_irIdx; if(ix<0){ g_introArmed=0; return; }
    const IRide* r=&g_irRide[ix];
    intro_find_actors(r,fol);
    if(r->screen[0]){                                                 // the monitor's source: the selfie stick's preview plane
        if(!g_irFnSetMat){ g_irFnGetMat=find_by_path("/Script/Engine.PrimitiveComponent.GetMaterial",0);
            g_irFnSetMat=find_by_path("/Script/Engine.PrimitiveComponent.SetMaterial",0); }
        if(!g_irPreviewMat) g_irPreviewMat=find_by_path("/Game/Equipment/Table/M_SelfiePreview.M_SelfiePreview",0);
        static int pt=0; uintptr_t pl=g_irPlane;
        if((!pl||!obj_alive(pl))&&(pt++%5)==0){ uintptr_t st=find_live_class_sub("SelfieStick"); pl=0;   // BP_SelfieStick_C / 2311 TribeSelfieStick
            if(st){ int o=prop_offset(rdptr(st+OFF_Class),"DisplayPlane",0); pl=o>=0?rdptr(st+o):0; }
            if(pl!=g_irPlane) LOGI("[INTRO] screen %s: the selfie stick's preview plane 0x%lx, M_SelfiePreview 0x%lx; GetMaterial 0x%lx SetMaterial 0x%lx",
                r->screen,(unsigned long)pl,(unsigned long)g_irPreviewMat,(unsigned long)g_irFnGetMat,(unsigned long)g_irFnSetMat);
            g_irPlane=pl; } }
    if(!g_irMP){ static int tries=0; g_irMP=find_by_path("/Game/Environment/BackdropMediaPlayer.BackdropMediaPlayer",0);
        g_irFnPlay=find_by_path("/Script/MediaAssets.MediaPlayer.Play",0); g_irFnPause=find_by_path("/Script/MediaAssets.MediaPlayer.Pause",0);
        g_irFnRewind=find_by_path("/Script/MediaAssets.MediaPlayer.Rewind",0); g_irFnIsPlaying=find_by_path("/Script/MediaAssets.MediaPlayer.IsPlaying",0);
        if(g_irMP||(tries++%30)==0) LOGI("[INTRO] Tribe's backdrop video: player 0x%lx, Play 0x%lx Pause 0x%lx Rewind 0x%lx IsPlaying 0x%lx",(unsigned long)g_irMP,
             (unsigned long)g_irFnPlay,(unsigned long)g_irFnPause,(unsigned long)g_irFnRewind,(unsigned long)g_irFnIsPlaying); }
    if(!g_irFnAtCue&&g_sCls){ char ty[48]="?"; g_irFnAtCue=em_find_child_func(g_sCls,"IsAtCue"); g_irAtCueOut=fn_out(g_irFnAtCue,ty,sizeof ty);
        LOGI("[INTRO] the deck's IsAtCue 0x%lx, out @%d %s",(unsigned long)g_irFnAtCue,g_irAtCueOut,ty); }
    intro_read_deck_cfg();
    int ci=g_idcIdx;                                                  // the play buttons, only if a call goes through them
    if(ci>=0&&(g_idc[ci][0].button||g_idc[ci][1].button)&&g_irBtnCls){
        bool dead=g_irNBtn==0; for(int i=0;i<g_irNBtn;i++) if(!obj_alive(g_irBtns[i])) dead=true;
        static int calls=0; if(dead||(++calls%15)==0){ refresh_numelements(); int n=0;
            for(uint32_t i=0;i<g_numElements&&n<16;i++){ uintptr_t o=obj_at(i); if(!o) continue;
                if(rd32(o+OFF_Flags)&(RF_ClassDefaultObject|0x20u|0x40000000u)) continue;
                int d=0; for(uintptr_t c=rdptr(o+OFF_Class); c&&d<12; c=rdptr(c+OFF_Super),d++) if(c==g_irBtnCls){ g_irBtns[n++]=o; break; } }
            g_irNBtn=n; } }
    g_introArmed=1; }

// ---- GAME thread
enum { IS_IDLE, IS_PRE, IS_RIDE, IS_SHOW, IS_DONE };
static const char* const IS_NAME[5]={"idle","pre-show","riding in","showtime","done"};
static int g_isState=IS_IDLE, g_isExiting=0, g_isQueued=0, g_isHeld=0, g_isRiderOn=0, g_isMusic=0, g_isDeck=-1, g_isVidPaused=0;
static double g_isTau=0, g_isShowT=0, g_isF[2]={0,1}, g_isLogT=0;
static double g_isShutT=-1; static int g_isShut=0;                 // door shut=: the clock from your arrival at the decks
static double g_isDoor=1, g_isDoorFrom=1, g_isDoorTo=1, g_isDoorT=1, g_isDoorDur=1;   // not easing
static uint64_t g_isKStep=0, g_isKDoor=0;
static uintptr_t g_irFovCap=0; static int g_irFovOff=-2; static float g_irFovOrig=0; static bool g_irFovSaved=false;

static void ir_hide(uintptr_t a,bool hide){ if(a&&obj_alive(a)&&g_emFnHidden) call_lib1(a,g_emFnHidden,hide?1:0); }
static void ir_step(int s){ show_set(g_isKStep,(float)s); }
static void ir_door_to(double to,double dur){ g_isDoorFrom=g_isDoor; g_isDoorTo=to; g_isDoorT=0; g_isDoorDur=dur; }
// the stream capture's horizontal FOV while the intro flies it; fov <= 0: give Tribe's back
static void intro_fov(double fov){
    uintptr_t cap=g_droneCap;
    static uintptr_t fovCls=0;                                         // mod2311: raw writes only into the class we measured
    if(g_irFovSaved&&(fov<=0||cap!=g_irFovCap)){ if(g_irFovCap&&obj_alive(g_irFovCap)&&g_irFovOff>=0&&rdptr(g_irFovCap+OFF_Class)==fovCls) *(float*)(g_irFovCap+g_irFovOff)=g_irFovOrig;
        g_irFovSaved=false; LOGI("[INTRO] the stream camera's FOV is Tribe's again (%.1f deg)",g_irFovOrig); }
    if(fov<=0||!cap||!obj_alive(cap)) return;
    if(cap!=g_irFovCap){ g_irFovCap=cap; fovCls=rdptr(cap+OFF_Class); uintptr_t fc=0; char ty[48]="?"; g_irFovOff=prop_offset(fovCls,"FOVAngle",&fc);
        if(fc) fname_resolve(rd32(fc),ty,sizeof ty); if(strcmp(ty,"FloatProperty")) g_irFovOff=-1;
        LOGI("[INTRO] stream camera 0x%lx: FOVAngle @%d %s",(unsigned long)cap,g_irFovOff,ty); }
    if(g_irFovOff<0||rdptr(cap+OFF_Class)!=fovCls) return;
    float* p=(float*)(cap+g_irFovOff); if(!g_irFovSaved){ g_irFovOrig=*p; g_irFovSaved=true; }
    *p=(float)fov; }
static int ir_video(uintptr_t fn){ return (g_irMP&&obj_alive(g_irMP)&&fn)?call_lib1(g_irMP,fn,-1):-2; }
// the deck sitting at its cue point: a track on it, not playing, IsAtCue; of several, the one with its fader highest
static int intro_cued_deck(){
    int best=-1; double bl=-2;
    for(int i=0;i<g_sNDeck&&i<S_MAXD;i++){ uintptr_t dk=g_sDeck[i]; if(!dk||!obj_alive(dk)) continue;
        char nm[512]; song_track_name(i,dk,nm,sizeof nm); if(!nm[0]||!strcmp(nm,"(empty)")||song_playing(dk)) continue;
        bool cue=false; if(g_irFnAtCue&&g_irAtCueOut>=0){ uint16_t psz=rd16(g_irFnAtCue+0xB6); static uint8_t b[256] __attribute__((aligned(16)));
            if(psz<=sizeof b){ memset(b,0,psz); call_uf(dk,g_irFnAtCue,b); cue=b[g_irAtCueOut]!=0; } }
        int ch=-1; double lv=mix_level(dk,&ch);
        LOGI("[INTRO] deck %d '%s': paused, %s, channel %d fader level %.2f",i,nm,cue?"AT its cue point":"not at its cue point",ch,lv);
        if(cue&&lv>bl){ bl=lv; best=i; } }
    if(best>=0&&bl>=0&&bl<0.5) LOGI("[INTRO] deck %d's fader is low (%.2f): the crowd and the stream may not hear it",best,bl);
    return best; }
static uintptr_t intro_deck_button(uintptr_t dk){                     // that deck's play button (2304: GetTribeEquipmentBase)
    if(!g_irFnEquip&&g_irBtnDeckOff>=0){                               // 2311: TribePlayButton.Deck (an ObjectProperty, by name)
        for(int j=0;j<g_irNBtn;j++){ uintptr_t bt=g_irBtns[j]; if(bt&&obj_alive(bt)&&rdptr(bt+(uintptr_t)g_irBtnDeckOff)==dk) return bt; }
        return 0; }
    if(!g_irFnEquip||g_irEquipOut<0) return 0; uint16_t psz=rd16(g_irFnEquip+0xB6); static uint8_t b[256] __attribute__((aligned(16)));
    if(psz>sizeof b) return 0;
    for(int j=0;j<g_irNBtn;j++){ uintptr_t bt=g_irBtns[j]; if(!bt||!obj_alive(bt)) continue;
        memset(b,0,psz); call_uf(bt,g_irFnEquip,b); uintptr_t eq; memcpy(&eq,b+g_irEquipOut,8); if(eq==dk) return bt; }
    return 0; }
static bool intro_deck_call(int which,int i){                         // which: 0 play, 1 stop, on deck i
    int ci=g_idcIdx; static const char* const W[2]={"play","stop"};
    if(ci<0||!g_idc[ci][which].on){ LOGI("[INTRO] deck %d: no '%s' line in intro_deck.txt: left alone",i,W[which]); return false; }
    const IDCall* c=&g_idc[ci][which]; uintptr_t dk=g_sDeck[i], target=c->button?intro_deck_button(dk):dk;
    if(!target||!obj_alive(target)){ LOGI("[INTRO] deck %d: its %s isn't found: '%s' not called",i,c->button?"play button":"deck",c->fn); return false; }
    uint16_t psz=rd16(c->f+0xB6); static uint8_t b[512] __attribute__((aligned(16))); if(psz>sizeof b) return false; memset(b,0,psz);
    char done[240]=""; int dn=0;
    for(int a=0;a<c->na;a++){ uintptr_t fc=0; int o=prop_offset(c->f,c->an[a],&fc); char ty[48]="?"; if(fc) fname_resolve(rd32(fc),ty,sizeof ty);
        if(o<0||o>=psz){ LOGI("[INTRO] %s has no parameter '%s'",c->fn,c->an[a]); continue; }
        const char* v=c->av[a];
        if(!strcmp(ty,"ObjectProperty")){ uintptr_t ob=!strcmp(v,"hand_l")?g_mcL:!strcmp(v,"hand_r")?g_mcR:!strcmp(v,"pawn")?g_pawn:!strcmp(v,"deck")?dk:0; memcpy(b+o,&ob,8); }
        else if(!strcmp(ty,"BoolProperty")||!strcmp(ty,"ByteProperty")||!strcmp(ty,"EnumProperty")) b[o]=(uint8_t)(!strcmp(v,"true")?1:!strcmp(v,"false")?0:atoi(v));
        else if(!strcmp(ty,"IntProperty")){ int32_t x=atoi(v); memcpy(b+o,&x,4); }
        else if(!strcmp(ty,"FloatProperty")){ float x=(float)atof(v); memcpy(b+o,&x,4); }
        else if(!strcmp(ty,"DoubleProperty")){ double x=atof(v); memcpy(b+o,&x,8); }
        else { LOGI("[INTRO] %s's parameter '%s' is a %s: not settable from intro_deck.txt",c->fn,c->an[a],ty); continue; }
        dn+=snprintf(done+dn,sizeof done-dn," %s=%s",c->an[a],v); }
    call_uf(target,c->f,b);
    LOGI("[INTRO] deck %d: %s -> %s:%s%s",i,W[which],c->button?"button":"deck",c->fn,done);
    return true; }
static void intro_reset(const char* why,bool ours){                   // everything back as Tribe and the pak had it; ours:
    if(g_isState!=IS_IDLE) LOGI("[INTRO] reset (%s) from %s",why,IS_NAME[g_isState]);   // the intro's stage is still up
    g_introCam=0; g_introDark=0; intro_fov(0);
    if(ours){ ir_step(0); show_set(g_isKDoor,1.f); }
    ir_hide(g_irRider,true); for(int i=0;i<IR_MAXN;i++) ir_hide(g_irWoods[i],true);
    if(g_isVidPaused){ ir_video(g_irFnPlay); g_isVidPaused=0; }
    g_isState=IS_IDLE; g_isExiting=g_isQueued=g_isHeld=g_isRiderOn=g_isMusic=0; g_isDeck=-1; g_isShutT=-1; g_isShut=0;
    g_isDoor=g_isDoorFrom=g_isDoorTo=1; g_isDoorT=g_isDoorDur=1; }
static void intro_start(const IRide* r){                              // press 1
    g_isState=IS_PRE; g_isTau=r->loop0; g_isExiting=g_isQueued=g_isHeld=0; g_isLogT=0; g_isShutT=-1; g_isShut=0;
    double P[3], V[3]; ir_pose(r,g_isTau,0,P,V); ir_forward(V,g_isF);
    ir_step(1); ir_door_to(0,r->door); g_introDark=1;
    int was=ir_video(g_irFnIsPlaying);
    if(was==1){ ir_video(g_irFnRewind); ir_video(g_irFnPause); g_isVidPaused=1; }
    for(int i=0;i<r->nwoods;i++) ir_hide(g_irWoods[i],false);
    if(g_irRider&&obj_alive(g_irRider)){ double R[3]={0,ir_actor_yaw(g_isF),0}; set_actor_lr(g_irRider,P,R); ir_hide(g_irRider,false); g_isRiderOn=1; }
    g_introCam=1;
    LOGI("[INTRO] press 1: the pre-show. Dark, the door shuts over %.1f s, the video %s, %d woods actor(s) shown, the rider %s, "
         "the stream camera %s",r->door,was==1?"rewound and paused":was==0?"wasn't playing":"isn't reachable",r->nwoods,
         g_isRiderOn?"rides":"is MISSING",g_droneCap?"rides with him":"is MISSING (take the selfie stick out, or drone.txt target=auto)"); }
static void intro_showtime(const IRide* r){                           // press 3, once the camera holds
    g_isState=IS_SHOW; g_isShowT=0; g_isMusic=0; ir_step(3);
    memcpy(g_introP,r->wide,24); memcpy(g_introA,r->wideLook,24);
    for(int i=0;i<r->nwoods;i++) ir_hide(g_irWoods[i],true);
    if(g_isRiderOn){ ir_hide(g_irRider,true); g_isRiderOn=0; }
    g_isDeck=intro_cued_deck();
    for(int i=0;i<g_sNDeck&&i<S_MAXD;i++){ uintptr_t dk=g_sDeck[i]; if(i!=g_isDeck&&dk&&obj_alive(dk)&&song_playing(dk)) intro_deck_call(1,i); }
    LOGI("[INTRO] showtime: the wide shot, %s; %.1f s dark, then the music",g_isDeck>=0?"the cued deck found":"NO deck sits at its cue point",r->hold); }
static void intro_log_deck_hint(){ static bool once=false; if(once) return; once=true;
    LOGI("[INTRO] to see what a real Play press calls: create tribemod/log_deck, press Play on a deck, then Pause ([DECK] lines)"); }

static uintptr_t ir_get_mat(uintptr_t comp){                         // PrimitiveComponent.GetMaterial(0)
    uintptr_t f=g_irFnGetMat; if(!f||!comp) return 0; uint16_t psz=rd16(f+0xB6);
    static uint8_t b[32] __attribute__((aligned(16))); if(psz>sizeof b) return 0;
    int oI=prop_offset(f,"ElementIndex",0), oR=prop_offset(f,"ReturnValue",0); if(oI<0||oR<0) return 0;
    memset(b,0,psz); call_uf(comp,f,b); return *(uintptr_t*)(b+oR); }
static void ir_screen_tick(const IRide* r,float dt){                  // about once a second: the monitor shows the preview's material
    static double t=0; static int logs=0; t+=dt; if(t<1.0) return; t=0;
    uintptr_t a=g_irScreen; if(!r->screen[0]||!a||!obj_alive(a)||!g_irFnSetMat) return;
    int oc=prop_offset(rdptr(a+OFF_Class),"StaticMeshComponent",0); uintptr_t comp=oc>=0?rdptr(a+oc):0; if(!comp||!obj_alive(comp)) return;
    uintptr_t pl=g_irPlane, src=pl&&obj_alive(pl)?ir_get_mat(pl):0;
    if(!src||!obj_alive(src)) src=g_irPreviewMat;
    if(!src||!obj_alive(src)||ir_get_mat(comp)==src) return;
    uintptr_t f=g_irFnSetMat; uint16_t psz=rd16(f+0xB6); static uint8_t b[32] __attribute__((aligned(16))); if(psz>sizeof b) return;
    int oI=prop_offset(f,"ElementIndex",0), oM=prop_offset(f,"Material",0); if(oI<0||oM<0) return;
    memset(b,0,psz); *(uintptr_t*)(b+oM)=src; call_uf(comp,f,b);
    if(logs<6){ logs++; char nm[96]; obj_name(src,nm,sizeof nm); bool ok=ir_get_mat(comp)==src;
        LOGI("[INTRO] screen %s: %s %s (0x%lx)%s",r->screen,ok?"now shows":"did NOT take",nm,(unsigned long)src,
             src==g_irPreviewMat?" by path (the preview plane isn't up: take the selfie stick out)":", the preview plane's"); } }
static void intro_tick(float dt){
    static int gen=-1;
    int ix=g_irIdx;
    bool up=ix>=0&&g_introArmed&&g_emState==EM_ACTIVE&&show_coll_ok()&&g_pawn&&obj_alive(g_pawn);   // mod2311: the show bus's check
    if(!up){ if(g_isState!=IS_IDLE||g_introCam||g_introDark) intro_reset("the intro's stage isn't up",false); gen=-1; return; }
    if(gen!=g_showGen){                                               // this stage instance (a reload starts over)
        if(g_isState!=IS_IDLE||g_introCam||g_introDark) intro_reset("the stage loaded again",false);
        const IRide* r=&g_irRide[ix]; gen=g_showGen;
        g_isKStep=show_key(r->step); g_isKDoor=show_key(r->doorName);
        LOGI("[INTRO] ready on this stage: %s %s, %s %s; press the button (%.0f, %.0f, %.0f) to start",r->step,g_isKStep?"found":"MISSING",
             r->doorName,g_isKDoor?"found":"MISSING",r->btn[0],r->btn[1],r->btn[2]);
        ir_step(0); show_set(g_isKDoor,1.f); g_isDoor=1;
        ir_hide(g_irRider,true); for(int i=0;i<IR_MAXN;i++) ir_hide(g_irWoods[i],true);
        intro_log_deck_hint(); }
    if(g_isState==IS_IDLE){                                           // the pak saves them hidden: make sure, once each
        static uintptr_t hid[1+IR_MAXN]; uintptr_t a=g_irRider; if(a&&a!=hid[0]){ ir_hide(a,true); hid[0]=a; }
        for(int i=0;i<IR_MAXN;i++){ a=g_irWoods[i]; if(a&&a!=hid[1+i]){ ir_hide(a,true); hid[1+i]=a; } } }
    if(!(dt>0.f&&dt<0.25f)) return;
    const IRide* r=&g_irRide[ix];
    ir_screen_tick(r,dt);
    // the button: either hand near it
    double d=1e9; uintptr_t hands[2]={g_mcL,g_mcR};
    for(int i=0;i<2;i++){ double P[3]; if(hands[i]&&obj_alive(hands[i])&&get_vec3(hands[i],g_fnLoc,P)){
        double e=sqrt((P[0]-r->btn[0])*(P[0]-r->btn[0])+(P[1]-r->btn[1])*(P[1]-r->btn[1])+(P[2]-r->btn[2])*(P[2]-r->btn[2])); if(e<d) d=e; } }
    static bool armed=true; static double cool=0, nearLog=0; cool-=dt; nearLog+=dt;
    if(d<40&&nearLog>=1.0){ nearLog=0; LOGI("[INTRO] hand %.0f cm from the button (press inside %.0f), %s",d,r->btnR,IS_NAME[g_isState]); }
    // HARVEST MOON 2026-10-20 (opt-in: buttonactor): the hand pushes the cap down over its last 6 cm before a press
    // (full travel at the press), and it springs back up over ~0.2 s; the actor's own placement is read once
    { static uintptr_t btnFor=0; static int have=0; static double base[3], rot[3], depth=0;
      uintptr_t b=g_irBtnActor;
      if(b!=btnFor){ btnFor=b; have=0; depth=0; }
      if(b&&obj_alive(b)&&r->btnTravel>0&&g_emFnActLoc&&g_emFnActRot){
          if(!have) have=get_vec3(b,g_emFnActLoc,base)&&get_vec3(b,g_emFnActRot,rot);
          if(have){ double want=r->btnTravel*fmin(fmax((r->btnR+6.0-d)/6.0,0.0),1.0);
              double nd=want>=depth?want:fmax(want,depth-dt*r->btnTravel*5.0);
              if(fabs(nd-depth)>0.01){ depth=nd; double P[3]={base[0],base[1],base[2]-depth}; set_actor_lr(b,P,rot); } } } }
    if(d>r->btnR+8) armed=true;
    if(armed&&d<r->btnR&&cool<=0){ armed=false; cool=1.2;
        if(g_isState==IS_IDLE) intro_start(r);
        else if(g_isState==IS_PRE){ g_isState=IS_RIDE; ir_step(2);
            if(r->autoShow) g_isQueued=1;                             // HARVEST MOON: autoshow, 2 presses in all
            LOGI("[INTRO] press 2: he finishes the lap (%.1f s to go) and takes the exit%s",r->loop1-g_isTau,
                 r->autoShow?"; showtime follows once the camera holds (autoshow)":""); }
        else if(g_isState==IS_RIDE&&!g_isQueued){ g_isQueued=1;
            LOGI("[INTRO] press 3: showtime %s",(g_isExiting&&g_isTau>=r->camhold)?"now":"as soon as the camera holds"); }
        else LOGI("[INTRO] press ignored (%s: one intro per stage load)",IS_NAME[g_isState]); }
    // the door
    if(g_isDoorT<g_isDoorDur){ g_isDoorT+=dt; g_isDoor=g_isDoorFrom+(g_isDoorTo-g_isDoorFrom)*ir_smooth(g_isDoorT/g_isDoorDur); show_set(g_isKDoor,(float)g_isDoor); }
    // the ride: the rider, and the camera's pose for drone_update
    if(g_isState==IS_PRE||g_isState==IS_RIDE){
        g_isTau+=dt;
        if(!g_isExiting&&g_isTau>=r->loop1){ if(g_isState==IS_RIDE){ g_isExiting=1; LOGI("[INTRO] the exit"); }
            else g_isTau-=r->loop1-r->loop0; }
        double P[3], V[3]; ir_pose(r,g_isTau,g_isExiting,P,V); ir_forward(V,g_isF);
        if(g_isRiderOn){ if(g_isExiting&&g_isTau>=r->exit1){ ir_hide(g_irRider,true); g_isRiderOn=0; LOGI("[INTRO] the rider is out of sight: hidden"); }
            else if(obj_alive(g_irRider)){ double R[3]={0,ir_actor_yaw(g_isF),0}; set_actor_lr(g_irRider,P,R); } }
        if(!g_isHeld){ ir_camera(r,g_isTau,g_isExiting,P,g_isF,g_introP,g_introA);
            if(g_isExiting&&g_isTau>=r->camhold){ g_isHeld=1; LOGI("[INTRO] the camera holds at (%.0f, %.0f, %.0f)",g_introP[0],g_introP[1],g_introP[2]); } }
        intro_fov(r->fovRide);
        if(g_isQueued&&g_isHeld) intro_showtime(r);
        g_isLogT+=dt;
        if(g_isLogT>=5.0){ g_isLogT=0; LOGI("[INTRO] %s t %.2f%s: rider (%.0f, %.0f, %.0f) yaw %.0f | camera (%.0f, %.0f, %.0f)%s | video %d",
            IS_NAME[g_isState],g_isTau,g_isExiting?" (exit)":"",P[0],P[1],P[2],ir_actor_yaw(g_isF),g_introP[0],g_introP[1],g_introP[2],
            g_isHeld?" held":"",ir_video(g_irFnIsPlaying)); } }
    else if(g_isState==IS_SHOW||g_isState==IS_DONE){
        if(g_isState==IS_SHOW){ g_isShowT+=dt; intro_fov(r->fovWide); }
        if(!g_isMusic&&g_isShowT>=r->hold){ g_isMusic=1; g_introDark=0; ir_door_to(1,r->door);
            bool played=g_isDeck>=0&&intro_deck_call(0,g_isDeck);
            int v=g_isVidPaused?ir_video(g_irFnPlay):-3; g_isVidPaused=0;
            LOGI("[INTRO] the music: %s; the video %s; the door rises over %.1f s; the lights take the song",
                 played?"the cued deck plays":"NO deck started",v==1?"plays":v==-3?"was left alone":"didn't start",r->door); }
        // HARVEST MOON 2026-10-20 (opt-in: a file with a descent line): while the door rises the wide shot tracks the
        // descent (the stage's materials move their ship on the same smoothstep of the door) and eases to wide2 as it settles
        if(g_isState==IS_SHOW&&g_isMusic&&r->hasDesc){
            double s=ir_smooth(g_isDoor), u=ir_smooth((s-0.85)/0.15);
            const double* P2=r->hasWide2?r->wide2:r->wide; const double* L2=r->hasWide2?r->wide2Look:r->descB;
            for(int i=0;i<3;i++){ double tr=r->descA[i]+(r->descB[i]-r->descA[i])*s;
                g_introP[i]=r->wide[i]+(P2[i]-r->wide[i])*s; g_introA[i]=tr+(L2[i]-tr)*u; } }
        double H[3], D[3]={0,90,0}; int dix=g_clubMapIdx;
        if(dix>=0){ const CCSpot* s=cc_spot(&g_clubMap[dix],"decks"); if(s){ D[0]=s->x; D[1]=s->y; D[2]=s->z; } }
        bool atDecks=g_isMusic&&g_camComp&&obj_alive(g_camComp)&&get_vec3(g_camComp,g_fnLoc,H)&&hypot(H[0]-D[0],H[1]-D[1])<120&&H[2]>D[2]+100;
        bool descending=r->hasDesc&&g_isDoorT<g_isDoorDur;              // HARVEST MOON: the decks never cut the descent
        if(g_isState==IS_SHOW&&g_isMusic&&((atDecks&&!descending)||g_isShowT>=r->hold+r->back)){ g_isState=IS_DONE; g_introCam=0; intro_fov(0);
            LOGI("[INTRO] the camera goes back (%s): done until the stage loads again",atDecks?"you're at the decks":"time"); }
        // door ... shut=s: once you're through and at the decks, the door closes behind you (it stays shut until a reload)
        if(r->shut>=0&&g_isMusic&&!g_isShut){
            if(g_isShutT<0&&atDecks){ g_isShutT=0; LOGI("[INTRO] you're at the decks: the door shuts in %.1f s",r->shut); }
            if(g_isShutT>=0&&(g_isShutT+=dt)>=r->shut){ g_isShut=1; ir_door_to(0,r->door);
                LOGI("[INTRO] the door shuts behind you over %.1f s",r->door); } } } }

// ---- the deck capture (flag tribemod/log_deck; diagnostic, logcat [DECK]): every ProcessEvent call into a function of
// Tribe's deck classes (BP_Deck_C and children, its buttons, its audio player), with the parameters, each function at most
// 12 times. One Play press and one Pause press in the headset show what intro_deck.txt should call (Blueprint-to-Blueprint
// calls never pass ProcessEvent: the entry points, the RPCs and the delegates do).
static volatile sig_atomic_t g_logDeck=0;
static uintptr_t g_dlFn[8192]; static uint8_t g_dlOk[8192]; static int g_dlN=0;    // function -> one of the deck's classes?
static uintptr_t g_dlHit[256]; static uint8_t g_dlCnt[256];                         // the deck's functions -> lines logged
static bool deck_class(uintptr_t func){ char on[96]; obj_name(rdptr(func+OFF_Outer),on,sizeof on);   // the class that owns it
    return strstr(on,"Deck")||strstr(on,"PlayButton")||strstr(on,"CueButton")||strstr(on,"PlayPause")||strstr(on,"AudioPlayer")
           ||strstr(on,"Superpowered"); }
static void deck_log_params(uintptr_t fn,const uint8_t* p,char* out,int n){
    int k=0; out[0]=0; uint16_t psz=rd16(fn+0xB6);
    for(uintptr_t f=rdptr(fn+OFF_ChildProps); f&&k<n-96; f=rdptr(f+FF_Next)){
        char pn[64], ty[48]; fname_resolve(rd32(f+FF_Name),pn,sizeof pn); ffield_type(f,ty,sizeof ty);
        uint32_t off=rd32(f+FP_Offset), sz=rd32(f+FP_ElemSize); bool outp=(rdptr(f+0x38)&(0x100ull|0x400ull))!=0;
        k+=snprintf(out+k,n-k," %s%s:%s",outp?"out ":"",pn,ty);
        if(!p||off>=psz) continue; const uint8_t* v=p+off;
        if(!strcmp(ty,"BoolProperty")||!strcmp(ty,"ByteProperty")||!strcmp(ty,"EnumProperty")) k+=snprintf(out+k,n-k,"=%u",v[0]);
        else if(!strcmp(ty,"IntProperty")){ int32_t x; memcpy(&x,v,4); k+=snprintf(out+k,n-k,"=%d",x); }
        else if(!strcmp(ty,"FloatProperty")){ float x; memcpy(&x,v,4); k+=snprintf(out+k,n-k,"=%.4f",x); }
        else if(!strcmp(ty,"DoubleProperty")){ double x; memcpy(&x,v,8); k+=snprintf(out+k,n-k,"=%.4f",x); }
        else if(!strcmp(ty,"ObjectProperty")||!strcmp(ty,"ClassProperty")){ uintptr_t o; memcpy(&o,v,8); char on[64]="null", oc[64]="";
            if(o&&in_range(o,0x30)){ obj_name(o,on,sizeof on); class_name(o,oc,sizeof oc); } k+=snprintf(out+k,n-k,"=%s(%s)",on,oc); }
        else if(!strcmp(ty,"StrProperty")){ char s[80]; read_fstring((uintptr_t)v,s,sizeof s); k+=snprintf(out+k,n-k,"='%s'",s); }
        else { k+=snprintf(out+k,n-k,"=0x"); for(uint32_t b=0;b<sz&&b<16&&k<n-4;b++) k+=snprintf(out+k,n-k,"%02x",v[b]); } } }
static void deck_log_pe(uintptr_t self,uintptr_t func,void* parms){
    if(!func) return;
    uint32_t h=(uint32_t)((func>>4)*2654435761u); int j=-1; bool ok;
    for(int i=0;i<64;i++){ uint32_t s=(h+(uint32_t)i)&8191u;
        if(g_dlFn[s]==func){ j=(int)s; break; }
        if(!g_dlFn[s]){ if(g_dlN<7000){ g_dlFn[s]=func; g_dlOk[s]=deck_class(func)?1:0; g_dlN++; j=(int)s; } break; } }
    ok=j>=0?g_dlOk[j]!=0:deck_class(func);                          // the cache is full: ask again (slower, same answer)
    if(!ok) return;
    int c=-1; for(int i=0;i<256;i++){ uint32_t s=(h+(uint32_t)i)&255u; if(g_dlHit[s]==func||!g_dlHit[s]){ g_dlHit[s]=func; c=(int)s; break; } }
    if(c<0||g_dlCnt[c]>=12) return; g_dlCnt[c]++;
    char fp[300], sn[96], sc[96], pl[700]; full_path(func,fp,sizeof fp); obj_name(self,sn,sizeof sn); class_name(self,sc,sizeof sc);
    deck_log_params(func,(const uint8_t*)parms,pl,sizeof pl);
    LOGI("[DECK] %s on %s (%s)%s%s",fp,sn,sc,pl[0]?" |":"",pl); }
