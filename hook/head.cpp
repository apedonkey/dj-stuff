// ============ Detachable head (tribemod/heads/<skin>.glb + three DH_* bones; control tribemod/head.txt) ============
// Included from dumper.cpp after the drone section. The skin's head stays part of the skinned body (A = full body,
// owner-no-see; B = owner-only, Head hidden), so while the head is ON nothing changes. This adds a STATIC copy of the head
// (heads/<skin>.glb: a plain mesh, origin at the head's centre, upright, facing the character's front) that flies while
// A's Head bone is hidden. Where the head is comes from three leaf bones under Head in the skin: DH_C (centre),
// DH_F (= C + 10 cm front), DH_U (= C + 10 cm up). Their component-space positions are taken from the FK a2_drive already
// runs every frame (the pose A renders, live whether the bone is hidden or not) and turned into world space with A's own
// transform; GetSocketTransform is only a cross-check at init. States: ON (every=600 s OF PLAY by default, +-20 % jitter; head.txt every=<seconds>, the user asked for "once every 10 minutes") -> TAKEOFF 1.2 s -> ORBIT
// (random 15-25 s: a 0.9 m ring around the hips, 8 s per lap, bobbing, facing the way it flies) with one BOO per flight
// (up to the selfie-stick lens, grin, back) -> RETURN 1.5 s -> ON. The hide/show of the skinned head and the static copy
// happen in the same tick, so the hand-off reads as one head.
// head.txt (polled ~1 s): auto | on (stay on; return now) | off (take off; orbit until changed) | boo (one camera moment
// now, then back to the mode); optional lines fwd=+y up=+z = the static mesh's local forward/up after glTFRuntime's
// conversion (glTF +Z front -> UE +Y, glTF +Y up -> UE +Z), so a wrong guess is a file edit, not a rebuild.
// boomax=12 (metres, default 12; 0 = any distance): the boo only flies when the selfie-stick lens is within that of the
// hips, otherwise it is skipped ("boo skipped" in the log). Stops the pumpkin streaking 90 m to a camera that is off in
// the woods with the stage intro's rider. A boo that is due while the lens is beyond boomax WAITS (the head keeps
// orbiting) and fires if the camera comes within range before the orbit ends; otherwise "boo skipped this flight".
// intro=hold (default) | free: with hold there is no random (auto) takeoff while a stage intro owns the stream camera
// (g_introCam in dumper.cpp, set by intro.cpp from its press 1 until the camera comes back at showtime); a flight already
// in the air finishes normally, and head.txt off/boo still work. The every= countdown restarts when the camera comes back.
// All timing runs on a PLAY clock (hd_now = the sum of the ticks' dt), not the wall clock: it stands still while Tribe is
// paused (headset asleep: our actor stops ticking), so a break never ends with the head taking off the moment the user is
// back. combo2 did exactly that (2026-10-10: a 1 h 52 min nap with 455 s left on the countdown -> TAKEOFF 1 s after the
// resume). A pause is reported once when the ticks come back ("[HEAD] Tribe was paused N s ...").
static volatile sig_atomic_t g_hdMode=0, g_hdBooReq=0;               // poll thread -> game thread: 0 auto, 1 on, 2 off
static volatile int g_hdFwdAx=2, g_hdUpAx=4;                         // static mesh local axes: 0 +x 1 -x 2 +y 3 -y 4 +z 5 -z
static volatile int g_hdBooMaxCm=1200;                               // boo only when the lens is within this many cm of the hips; 0 = always
static volatile int g_hdIntroHold=1;                                 // 1: no auto takeoff while g_introCam (the intro flies the camera)
static bool g_hdBooWaitSaid=false;                                   // "boo waiting" logged once per flight
static uintptr_t g_hdMesh=0, g_hdComp=0, g_hdForA=0; static volatile uintptr_t g_hdCap=0;
static uintptr_t g_fnLoadSM=0, g_smcCls=0, g_fnSetSM=0, g_fnSockXf=0, g_fnHdSetWorldLR=0, g_fnHdErr=0;
static int g_hdSoName=-1, g_hdSoSpace=-1, g_hdSoRet=-1;
static char g_hdSkin[256]="";
// the skin's DH bones + Hips in A's component space, copied out of a2_drive's FK every frame
static int iDHC=-1, iDHF=-1, iDHU=-1; static V3 g_hdFkT[4]; static bool g_hdFkOK=false;
enum { HD_ON, HD_TAKEOFF, HD_ORBIT, HD_BOO_TO, HD_BOO_HOLD, HD_BOO_BACK, HD_RETURN };
static const char* HD_SN[]={"ON","TAKEOFF","ORBIT","BOO-to","BOO-hold","BOO-back","RETURN"};
static int g_hdState=HD_ON; static double g_hdT0=0, g_hdDur=0, g_hdTh=0, g_hdZ=0, g_hdFlyT=0, g_hdBooAt=0, g_hdOrbT0=0;
static bool g_hdBooDone=false, g_hdBooNow=false, g_hdHipsInit=false; static V3 g_hdP0={0,0,0}, g_hdHips={0,0,0}; static Q4 g_hdQ0={0,0,0,1};
static const double HD_RING_R=90.0, HD_LAP_S=8.0, HD_TAKEOFF_S=1.2, HD_RETURN_S=1.5, HD_BOO_MOVE_S=1.5, HD_BOO_HOLD_S=2.5, HD_BOO_DIST=60.0;

static double hd_real(){ struct timespec ts; clock_gettime(CLOCK_MONOTONIC,&ts); return (double)ts.tv_sec+ts.tv_nsec*1e-9; }
// the play clock: advanced by head_tick only, by each accepted frame's dt (<= 0.25 s), so a sleeping headset adds nothing
static double g_hdClock=0, g_hdLastReal=0, g_hdPausedS=0;
static double hd_now(){ return g_hdClock; }
static double hd_rnd(double a,double b){ static bool seeded=false; if(!seeded){ seeded=true; srand((unsigned)time(0)^(unsigned)getpid()); }
    return a+(b-a)*(rand()/(double)RAND_MAX); }
static volatile int g_hdEveryS=600;                                  // head.txt every=<seconds>: the ON gap between flights (10 min by default)
static double hd_gap(){ double e=g_hdEveryS; return hd_rnd(0.8*e,1.2*e); }   // +-20 % jitter so it never feels like a timer
static double hd_ease(double u){ if(u<0) u=0; if(u>1) u=1; return u*u*(3-2*u); }
static V3 ax_vec(int a){ static const V3 t[6]={{1,0,0},{-1,0,0},{0,1,0},{0,-1,0},{0,0,1},{0,0,-1}}; return t[(a>=0&&a<6)?a:2]; }
static const char* ax_name(int a){ static const char* n[6]={"+x","-x","+y","-y","+z","-z"}; return (a>=0&&a<6)?n[a]:"?"; }
static int ax_parse(const char* s,int dflt){ int sign=0; if(*s=='+'){ s++; } else if(*s=='-'){ sign=1; s++; }
    char c=(char)tolower((unsigned char)*s); if(!c||s[1]) return dflt; return c=='x'?0+sign:c=='y'?2+sign:c=='z'?4+sign:dflt; }
// rotation taking the static mesh's local (fwd, up) axes onto world (fwd, up)
static Q4 head_frame_q(V3 fwd,V3 up){ Q4 w=frame_q(fwd,up), l=frame_q(ax_vec(g_hdFwdAx),ax_vec(g_hdUpAx)); return qnorm(qmul(w,qinv(l))); }
static void q2rot(Q4 q,double r[3]){                                 // FQuat::Rotator (UE5): Pitch, Yaw, Roll in degrees
    const double X=q.x,Y=q.y,Z=q.z,W=q.w, st=Z*X-W*Y, yy=2*(W*Z+X*Y), yx=1-2*(Y*Y+Z*Z), k=180.0/M_PI;
    if(st<-0.4999995){ r[0]=-90; r[1]=atan2(yy,yx)*k; r[2]=wrap180(-r[1]-2*atan2(X,W)*k); }
    else if(st>0.4999995){ r[0]=90; r[1]=atan2(yy,yx)*k; r[2]=wrap180(r[1]-2*atan2(X,W)*k); }
    else { r[0]=asin(2*st)*k; r[1]=atan2(yy,yx)*k; r[2]=atan2(-2*(W*X+Y*Z),1-2*(X*X+Y*Y))*k; } }
// called by a2_drive after its final FK: keep the DH bones + Hips (component space) for this frame
static void head_capture_fk(const Q4* cq,const V3* ct){ (void)cq;
    if(iDHC<0||iDHC>=g_rb_n||strcmp(g_rb_nm[iDHC],"DH_C")||iDHF<0||iDHF>=g_rb_n||iDHU<0||iDHU>=g_rb_n){
        iDHC=rb_find("DH_C"); iDHF=rb_find("DH_F"); iDHU=rb_find("DH_U"); }
    g_hdFkOK=iDHC>=0&&iDHF>=0&&iDHU>=0&&iHips>=0;
    if(!g_hdFkOK) return;
    g_hdFkT[0]=ct[iDHC]; g_hdFkT[1]=ct[iDHF]; g_hdFkT[2]=ct[iDHU]; g_hdFkT[3]=ct[iHips]; }
static bool head_A_xform(V3* loc,Q4* q,double* s){ double L[3],R[3],S[3];
    if(!g_pmA||!get_vec3(g_pmA,g_fnLoc,L)||!get_vec3(g_pmA,g_fnGetRot,R)||!get_vec3(g_pmA,g_fnScale,S)) return false;
    *loc=V(L[0],L[1],L[2]); *q=rot2q(R); *s=S[0]; return S[0]>0.05&&S[0]<20; }
static V3 head_to_world(V3 loc,Q4 q,double s,V3 c){ return vadd(loc,qrot(q,vmul(c,s))); }
// the head's live world pose (centre + orientation) from the DH bones, plus the hips
static bool head_dh_pose(V3* pos,Q4* q,V3* hips){
    V3 AL; Q4 AQ; double s; if(!g_hdFkOK||!head_A_xform(&AL,&AQ,&s)) return false;
    V3 C=head_to_world(AL,AQ,s,g_hdFkT[0]), F=head_to_world(AL,AQ,s,g_hdFkT[1]), U=head_to_world(AL,AQ,s,g_hdFkT[2]);
    V3 f=vsub(F,C), u=vsub(U,C); if(vlen(f)<2||vlen(u)<2||vlen(f)>60||vlen(u)>60) return false;
    *pos=C; *q=head_frame_q(f,u); if(hips) *hips=head_to_world(AL,AQ,s,g_hdFkT[3]); return true; }
static bool head_socket_world(uintptr_t comp,uint64_t fname,V3* out){   // GetSocketTransform(bone, RTS_World) -> translation
    if(!g_fnSockXf||!comp||g_hdSoName<0||g_hdSoRet<0) return false; uint16_t psz=rd16(g_fnSockXf+0xB6);
    static uint8_t b[256] __attribute__((aligned(16))); if(psz>sizeof b||g_hdSoRet+56>(int)psz) return false;
    memset(b,0,psz); memcpy(b+g_hdSoName,&fname,8); if(g_hdSoSpace>=0) b[g_hdSoSpace]=0;
    call_uf(comp,g_fnSockXf,b); double* t=(double*)(b+g_hdSoRet+32); *out=V(t[0],t[1],t[2]); return isfinite(t[0])&&isfinite(t[1])&&isfinite(t[2]); }
static void head_place(V3 p,Q4 q){ double L[3]={p.x,p.y,p.z}, R[3]; q2rot(q,R); set_comp_xform(g_fnHdSetWorldLR,g_hdComp,L,R); }
static void head_show(bool on){ if(g_hdComp) call_bool2(g_hdComp,g_fnVis,on?1:0,1); }
static void head_drop(const char* why){                               // game thread
    if(g_hdState!=HD_ON&&g_pmA&&g_pmA==g_hdForA) a2_unhide_bone(g_pmA,iHead);   // A gets its head back
    if(g_hdComp){ call_bool2(g_hdComp,g_fnVis,0,1); unroot_object(g_hdComp);
        if(g_fnDestroyComp){ int o=prop_offset(g_fnDestroyComp,"Object",0); static uint8_t b[16]; memset(b,0,sizeof b);
            if(o>=0){ *(uintptr_t*)(b+o)=g_hdComp; call_uf(g_hdComp,g_fnDestroyComp,b); } } }
    if(g_hdMesh) unroot_object(g_hdMesh);
    if(g_hdComp||g_hdMesh) LOGI("[HEAD] dropped the static head (%s)",why);
    g_hdComp=0; g_hdMesh=0; g_hdForA=0; g_hdState=HD_ON; g_hdSkin[0]=0; }
// after a skin load (inside do_load's guard, game thread): load heads/<skin>.glb as a UStaticMesh, or switch the feature
// off for this skin. The component is created later, on the tick, once body tracking is live.
static void head_skin_loaded(const char* skin,uintptr_t libCDO,uintptr_t fnLoad){
    head_drop("skin loaded");
    if(!skin||!*skin){ LOGI("[HEAD] no active_skin name -> no head for this load"); return; }
    char path[600]; snprintf(path,sizeof path,"%s/heads/%s",OUTDIR,skin); struct stat st;
    if(stat(path,&st)!=0){ LOGI("[HEAD] %s: no heads/%s -> feature off for this skin",skin,skin); return; }
    if(!g_fnLoadSM) g_fnLoadSM=find_by_path("/Script/glTFRuntime.glTFRuntimeAsset.LoadStaticMesh",0);
    if(!g_fnHdErr)  g_fnHdErr =find_by_path("/Script/glTFRuntime.glTFRuntimeAsset.GetErrors",0);
    if(!g_fnLoadSM||!libCDO||!fnLoad){ LOGI("[HEAD] LoadStaticMesh=0x%lx libCDO=0x%lx load=0x%lx -> can't load",(unsigned long)g_fnLoadSM,(unsigned long)libCDO,(unsigned long)fnLoad); return; }
    static uint8_t lp[0x218]; memset(lp,0,sizeof lp);                 // glTFLoadAssetFromFilename, same LoaderConfig as the skin
    FStr fs; build_fstr(&fs,path); *(FStr*)(lp+0x00)=fs; *(uint8_t*)(lp+0x10)=0;
    *(float*)(lp+0x20+0x150)=100.0f; *(uint8_t*)(lp+0x20+0x168)=1; *(uint8_t*)(lp+0x20+0x00)=0;
    call_uf(libCDO,fnLoad,lp); uintptr_t asset=*(uintptr_t*)(lp+0x210);
    if(!asset){ LOGI("[HEAD] asset NULL for %s (parse/file access)",path); return; }
    // LoadStaticMesh(MeshIndex=0, StaticMeshConfig): zeroed config, members by name; BoundsScale=(1,1,1) when it exists
    uint16_t psz=rd16(g_fnLoadSM+0xB6); int oI=prop_offset(g_fnLoadSM,"MeshIndex",0), oR=prop_offset(g_fnLoadSM,"ReturnValue",0);
    uintptr_t fCfg=find_field(g_fnLoadSM,"StaticMeshConfig"); int S=calib_fprop_size();
    int oCfg=fCfg?(int)rd32(fCfg+FP_Offset):-1; uintptr_t cfgSt=(fCfg&&S>0)?rdptr(fCfg+S):0;
    int oBounds=-1, oSkip=-1;
    if(cfgSt){ uintptr_t fB=find_field(cfgSt,"BoundsScale"); if(fB) oBounds=(int)rd32(fB+FP_Offset);
        uintptr_t fM=find_field(cfgSt,"MaterialsConfig"); uintptr_t matSt=(fM&&S>0)?rdptr(fM+S):0; uintptr_t fSk=matSt?find_field(matSt,"bSkipLoad"):0;
        if(fM&&fSk) oSkip=(int)rd32(fM+FP_Offset)+(int)rd32(fSk+FP_Offset); }
    static uint8_t b[4096] __attribute__((aligned(16)));
    LOGI("[HEAD] LoadStaticMesh psz=0x%x MeshIndex@%d Config@%d Ret@%d BoundsScale@%d MaterialsConfig.bSkipLoad@%d",psz,oI,oCfg,oR,oBounds,oSkip);
    if(psz>sizeof b||oI<0||oR<0||oCfg<0||oR+8>(int)psz){ LOGI("[HEAD] LoadStaticMesh layout bad -> not loading"); return; }
    uintptr_t mesh=0; const char* how="materials on";
    for(int attempt=0;attempt<2&&!mesh;attempt++){
        memset(b,0,psz); *(int32_t*)(b+oI)=0;
        if(oBounds>=0&&oCfg+oBounds+24<=(int)psz){ double* v=(double*)(b+oCfg+oBounds); v[0]=v[1]=v[2]=1.0; }
        if(attempt==1){ if(oSkip<0||oCfg+oSkip>=(int)psz) break; b[oCfg+oSkip]=1; how="gray fallback (materials skipped)"; }
        call_uf(asset,g_fnLoadSM,b); mesh=*(uintptr_t*)(b+oR);
        if(!mesh){ LOGI("[HEAD] LoadStaticMesh (%s) returned NULL",how); decode_errors(asset,g_fnHdErr); } }
    if(!mesh) return;
    refresh_numelements(); root_object(mesh); g_hdMesh=mesh; snprintf(g_hdSkin,sizeof g_hdSkin,"%s",skin);
    LOGI("[HEAD] loaded heads/%s -> UStaticMesh 0x%lx (%s); the copy appears once body tracking is live",skin,(unsigned long)mesh,how); }
static uintptr_t head_add_comp(){                                     // StaticMeshComponent on our avatar actor, set up like A
    uintptr_t fn=g_fnAddComp; if(!fn||!g_isoActor||!g_smcCls||!g_hdMesh||!g_trackParent||!g_fnSetSM) return 0;
    int oC=prop_offset(fn,"Class",0), oM=prop_offset(fn,"bManualAttachment",0), oX=prop_offset(fn,"RelativeTransform",0),
        oD=prop_offset(fn,"bDeferredFinish",0), oR=prop_offset(fn,"ReturnValue",0);
    uint16_t psz=rd16(fn+0xB6); static uint8_t b[512] __attribute__((aligned(16)));
    if(oC<0||oX<0||oR<0||psz>sizeof b) return 0;
    memset(b,0,sizeof b); *(uintptr_t*)(b+oC)=g_smcCls; if(oM>=0) b[oM]=1; if(oD>=0) b[oD]=0;
    double* x=(double*)(b+oX); x[3]=1; x[8]=x[9]=x[10]=1;
    call_uf(g_isoActor,fn,b); uintptr_t c=*(uintptr_t*)(b+oR); if(!c) return 0;
    refresh_numelements(); root_object(c);
    { int o=prop_offset(g_fnSetSM,"NewMesh",0); memset(b,0,sizeof b); if(o>=0){ *(uintptr_t*)(b+o)=g_hdMesh; call_uf(c,g_fnSetSM,b); } }
    { int oP=prop_offset(g_fnAttach,"Parent",0), oL=prop_offset(g_fnAttach,"LocationRule",0), oRr=prop_offset(g_fnAttach,"RotationRule",0),
          oSc=prop_offset(g_fnAttach,"ScaleRule",0), oW=prop_offset(g_fnAttach,"bWeldSimulatedBodies",0);
      memset(b,0,sizeof b); if(oP>=0){ *(uintptr_t*)(b+oP)=g_trackParent; if(oL>=0) b[oL]=(uint8_t)g_attSnap; if(oRr>=0) b[oRr]=(uint8_t)g_attSnap;
          if(oSc>=0) b[oSc]=(uint8_t)g_attKeepRel; if(oW>=0) b[oW]=0; call_uf(c,g_fnAttach,b); } }
    a2_set_scale(c,g_btScale);
    call_bool2(c,g_fnColl2,0,0); call_bool2(c,g_fnShad2,0,0);
    call_bool2(c,g_fnOwner,0,0);                                        // you see it while it flies
    call_bool2(c,g_fnVis,0,1); call_bool2(c,g_fnHid,0,1);               // hidden until takeoff
    return c; }
static void head_force_on(const char* why){
    if(g_hdState!=HD_ON){ head_show(false); if(g_pmA&&g_pmA==g_hdForA) a2_unhide_bone(g_pmA,iHead);
        LOGI("[HEAD] back ON (%s)",why); }
    g_hdState=HD_ON; g_hdT0=hd_now(); g_hdDur=hd_gap(); }
static V3 hd_ring(double th){ return V(g_hdHips.x+HD_RING_R*cos(th), g_hdHips.y+HD_RING_R*sin(th), g_hdZ+8.0*sin(2*M_PI*0.5*g_hdFlyT)); }
static Q4 hd_ring_q(double th){ V3 f=V(-sin(th),cos(th),0); Q4 q=head_frame_q(f,V(0,0,1));
    double h=0.5*(10.0*M_PI/180.0)*sin(2*M_PI*0.25*g_hdFlyT); Q4 r=Qm(f.x*sin(h),f.y*sin(h),f.z*sin(h),cos(h));   // slow roll wobble
    return qnorm(qmul(r,q)); }
static bool hd_lens(V3* L,V3* cam){ uintptr_t cap=g_hdCap; double P[3],R[3];
    if(!cap||!get_vec3(cap,g_fnLoc,P)||!get_vec3(cap,g_fnGetRot,R)) return false;
    double p=R[0]*M_PI/180.0, y=R[1]*M_PI/180.0; V3 f=V(cos(p)*cos(y),cos(p)*sin(y),sin(p));
    *cam=V(P[0],P[1],P[2]); *L=vadd(*cam,vmul(f,HD_BOO_DIST)); return true; }
static void hd_go(int s,double now){ g_hdState=s; g_hdT0=now; }
static void hd_pause_said(){                                          // one line per pause, only while a head is loaded
    if(!g_hdMesh) return; char w[96];
    if(!g_hdForA) snprintf(w,sizeof w,"nothing in flight");
    else if(g_hdState!=HD_ON) snprintf(w,sizeof w,"the %s goes on",HD_SN[g_hdState]);
    else if(g_hdMode!=0) snprintf(w,sizeof w,"mode %s",g_hdMode==1?"on":"off");
    else { double left=g_hdT0+g_hdDur-g_hdClock; snprintf(w,sizeof w,"next auto takeoff in %.0f s of play",left>0?left:0); }
    LOGI("[HEAD] Tribe was paused %.0f s (headset asleep?): the head's clock stood still; %s",g_hdPausedS,w); }
static void head_tick(float dt){                                      // game thread, our actor's tick, after bt_frame
    double real=hd_real(), gap=g_hdLastReal>0?real-g_hdLastReal:0; g_hdLastReal=real;
    if(gap>5.0) g_hdPausedS+=gap;                                       // 5 s+ without a tick: Tribe was paused (or a long hitch)
    else if(g_hdPausedS>0&&gap<1.0){ hd_pause_said(); g_hdPausedS=0; }  // ticks are back at frame rate: report it once
    bool active=g_a2Live&&g_pmA&&g_hdMesh&&g_rbOK&&g_fnHdSetWorldLR&&g_fnLoc&&g_fnGetRot&&g_fnScale;   // DH bones checked below (logged once)
    if(active&&!g_hdComp){ g_hdComp=head_add_comp();
        if(!g_hdComp){ static double w=0; if(real-w>10){ w=real; LOGI("[HEAD] can't create the static head yet (addComp=0x%lx smcCls=0x%lx parent=0x%lx setSM=0x%lx)",
            (unsigned long)g_fnAddComp,(unsigned long)g_smcCls,(unsigned long)g_trackParent,(unsigned long)g_fnSetSM); } return; }
        LOGI("[HEAD] static head component 0x%lx on our avatar actor (scale %.3f, hidden until takeoff)",(unsigned long)g_hdComp,g_btScale); }
    if(!active||!g_hdComp){ if(g_hdState!=HD_ON) head_force_on("body tracking not live"); return; }
    if(dt<=0||dt>0.25f) return;
    g_hdClock+=dt; double now=g_hdClock;                                // the play clock moves only here, by rendered frames
    V3 dh=V(0,0,0),hips=V(0,0,0); Q4 dhq=QI; bool haveDH=head_dh_pose(&dh,&dhq,&hips);
    if(g_hdForA!=g_pmA){                                                // first time for this body mesh (also after a re-rig)
        if(g_hdState!=HD_ON) head_force_on("new body mesh");
        static uintptr_t warnedA=0;
        if(!g_hdFkOK){ if(warnedA!=g_pmA){ warnedA=g_pmA; LOGI("[HEAD] rig: DH bones %d/%d/%d hips %d -> MISSING: add DH_C/DH_F/DH_U under Head (feature idle)",iDHC,iDHF,iDHU,iHips); } return; }
        if(!haveDH) return;                                             // wait for a readable pose
        g_hdForA=g_pmA; g_hdHipsInit=false; g_hdT0=now; g_hdDur=hd_gap();
        { V3 AL; Q4 AQ; double s=1; head_A_xform(&AL,&AQ,&s);
            V3 F=head_to_world(AL,AQ,s,g_hdFkT[1]), U=head_to_world(AL,AQ,s,g_hdFkT[2]), f=vsub(F,dh), u=vsub(U,dh);
            V3 sc; bool sock=head_socket_world(g_pmA,g_rb_fn[iDHC],&sc); double d=sock?vlen(vsub(sc,dh)):-1;
            LOGI("[HEAD] rig ok: DH_C/DH_F/DH_U = bones %d/%d/%d; head centre (%.0f,%.0f,%.0f) front (%.2f,%.2f,%.2f)x%.1fcm up (%.2f,%.2f,%.2f)x%.1fcm; socket read %s (%.1f cm off the FK); first takeoff in %.0f s of play (mode %s)",
                iDHC,iDHF,iDHU,dh.x,dh.y,dh.z,f.x/vlen(f),f.y/vlen(f),f.z/vlen(f),vlen(f),u.x/vlen(u),u.y/vlen(u),u.z/vlen(u),vlen(u),
                sock?"ok":"n/a",d,g_hdDur,g_hdMode==1?"on":g_hdMode==2?"off":"auto"); } }
    if(haveDH){ if(!g_hdHipsInit){ g_hdHips=hips; g_hdHipsInit=true; } else { double k=dt/0.5; if(k>1) k=1; g_hdHips=vadd(g_hdHips,vmul(vsub(hips,g_hdHips),k)); } }
    int mode=g_hdMode; bool boo=g_hdBooReq!=0;
    if(g_hdState!=HD_ON) g_hdFlyT+=dt;
    V3 P=g_hdP0; Q4 Q=g_hdQ0; bool place=false;
    switch(g_hdState){
    case HD_ON:{ const char* why=0; static bool holdSaid=false; bool held=g_hdIntroHold&&g_introCam;   // the intro owns the stream camera
        if(mode==2) why="mode off"; else if(boo) why="boo";
        else if(mode==0&&held){ g_hdT0=now; if(!holdSaid){ holdSaid=true; LOGI("[HEAD] auto takeoff held: the stage intro owns the stream camera (intro=hold in head.txt)"); } }
        else { if(holdSaid){ holdSaid=false; LOGI("[HEAD] the intro handed the camera back: next auto takeoff in %.0f s of play",g_hdDur); }
            if(mode==0&&now>=g_hdT0+g_hdDur) why="auto"; }
        if(!why||!haveDH) break;
        a2_hide_bone(g_pmA,iHead); head_place(dh,dhq); head_show(true);   // the switch frame: A loses its head, the copy appears there
        g_hdP0=dh; g_hdQ0=dhq; g_hdZ=dh.z+10.0; g_hdFlyT=0; g_hdBooDone=false; g_hdBooWaitSaid=false; g_hdBooNow=boo; if(boo) g_hdBooReq=0;
        V3 f=qrot(dhq,ax_vec(g_hdFwdAx)); g_hdTh=atan2(f.y,f.x);         // the ring starts right in front of you
        g_hdDur=hd_rnd(15,25); hd_go(HD_TAKEOFF,now);
        LOGI("[HEAD] TAKEOFF (%s) from (%.0f,%.0f,%.0f): ring r=%.0f z=%.0f around the hips (%.0f,%.0f), orbit %.0f s%s",why,dh.x,dh.y,dh.z,
            HD_RING_R,g_hdZ,g_hdHips.x,g_hdHips.y,g_hdDur,g_hdBooNow?" (boo first)":"");
        break; }
    case HD_TAKEOFF:{ double u=(now-g_hdT0)/HD_TAKEOFF_S, e=hd_ease(u); V3 R=hd_ring(g_hdTh);
        P=vadd(vadd(vmul(g_hdP0,1-e),vmul(R,e)),V(0,0,25.0*sin(M_PI*fmin(u,1.0)))); Q=qslerp(g_hdQ0,hd_ring_q(g_hdTh),e); place=true;
        if(u>=1){ g_hdOrbT0=now; g_hdBooAt=now+g_hdDur*0.5; hd_go(HD_ORBIT,now);
            LOGI("[HEAD] ORBIT %.0f s (boo at +%.0f s%s)",g_hdDur,g_hdDur*0.5,g_hdCap?"":", if the selfie stick is out"); }
        break; }
    case HD_ORBIT:{ g_hdTh+=(2*M_PI/HD_LAP_S)*dt; P=hd_ring(g_hdTh); Q=hd_ring_q(g_hdTh); place=true;
        const char* ret=0; if(mode==1) ret="mode on"; else if(mode==0&&now>=g_hdOrbT0+g_hdDur) ret="auto";
        bool askBoo=boo||g_hdBooNow||(!g_hdBooDone&&now>=g_hdBooAt);
        V3 L,cam; double far=0; int mx=g_hdBooMaxCm; bool near=true;      // near: the lens is within boomax (or boomax=0)
        if(askBoo&&g_hdCap&&hd_lens(&L,&cam)){ far=vlen(vsub(cam,g_hdHips)); near=(mx<=0)||far<=mx; }
        if(ret){ if(askBoo&&g_hdCap&&!near) LOGI("[HEAD] boo skipped this flight: the selfie-stick camera stayed %.0f m away (boomax %.0f m in head.txt)",far/100.0,mx/100.0);
            if(boo) g_hdBooReq=0; g_hdBooNow=false; g_hdP0=P; g_hdQ0=Q; hd_go(HD_RETURN,now); LOGI("[HEAD] RETURN (%s)",ret); }
        else if(askBoo&&g_hdCap&&near){ if(boo) g_hdBooReq=0; g_hdBooNow=false; g_hdBooDone=true; g_hdP0=P; g_hdQ0=Q; hd_go(HD_BOO_TO,now);
            LOGI("[HEAD] BOO: flying to the selfie-stick lens %.1f m away",far/100.0); }
        else if(askBoo&&g_hdCap){ if(!g_hdBooWaitSaid){ g_hdBooWaitSaid=true;          // keep orbiting; boo if a nearer shot comes before RETURN
            LOGI("[HEAD] boo waiting: the selfie-stick camera is %.0f m away (boomax %.0f m in head.txt); it boos if the camera comes closer before this orbit ends",far/100.0,mx/100.0); } }
        else if(askBoo){ if(boo) g_hdBooReq=0; g_hdBooNow=false; g_hdBooDone=true; LOGI("[HEAD] boo skipped: no selfie-stick camera in the room"); }
        break; }
    case HD_BOO_TO: case HD_BOO_HOLD: case HD_BOO_BACK:{ g_hdTh+=(2*M_PI/HD_LAP_S)*dt; V3 L,cam;
        if(!hd_lens(&L,&cam)){ hd_go(HD_ORBIT,now); LOGI("[HEAD] boo cut short: camera gone"); P=hd_ring(g_hdTh); Q=hd_ring_q(g_hdTh); place=true; break; }
        Q4 qL=head_frame_q(vsub(cam,L),V(0,0,1));                        // grin into the lens
        double u=(now-g_hdT0)/((g_hdState==HD_BOO_HOLD)?HD_BOO_HOLD_S:HD_BOO_MOVE_S), e=hd_ease(u);
        if(g_hdState==HD_BOO_TO){ P=vadd(vmul(g_hdP0,1-e),vmul(L,e)); Q=qslerp(g_hdQ0,qL,e); if(u>=1) hd_go(HD_BOO_HOLD,now); }
        else if(g_hdState==HD_BOO_HOLD){ P=L; Q=qL; if(u>=1){ g_hdP0=P; g_hdQ0=Q; hd_go(HD_BOO_BACK,now); LOGI("[HEAD] boo done: back to the ring"); } }
        else { V3 R=hd_ring(g_hdTh); P=vadd(vmul(g_hdP0,1-e),vmul(R,e)); Q=qslerp(g_hdQ0,hd_ring_q(g_hdTh),e); if(u>=1) hd_go(HD_ORBIT,now); }
        place=true; break; }
    case HD_RETURN:{ double u=(now-g_hdT0)/HD_RETURN_S, e=hd_ease(u);
        if(!haveDH){ place=true; break; }                                 // no pose this frame: hold still
        P=vadd(vmul(g_hdP0,1-e),vmul(dh,e)); Q=qslerp(g_hdQ0,dhq,e); place=true;
        if(u>=1){ head_place(dh,dhq); head_show(false); a2_unhide_bone(g_pmA,iHead); place=false;   // the switch frame
            g_hdDur=hd_gap(); hd_go(HD_ON,now); LOGI("[HEAD] ON: head back on the neck (next takeoff in %.0f s of play when auto)",g_hdDur); }
        break; }
    }
    if(place) head_place(P,Q);
    static double logT=0; if(g_hdState!=HD_ON){ logT+=dt; if(logT>=5.0){ logT=0;
        LOGI("[HEAD] %s t=%.1f at (%.0f,%.0f,%.0f) angle %.0f deg; head on the rig at (%.0f,%.0f,%.0f); mode %s",HD_SN[g_hdState],g_hdFlyT,P.x,P.y,P.z,
            wrap180(g_hdTh*180.0/M_PI),dh.x,dh.y,dh.z,mode==1?"on":mode==2?"off":"auto"); } } else logT=0; }
// ---- poll thread: resolve functions once, track the selfie-stick camera, read head.txt (~1 s) ----
static void head_read_cfg(){
    static char last[256]="\x01"; char t[256]; if(!read_trim_file("head.txt",t,sizeof t)) t[0]=0;
    if(!strcmp(t,last)) return; snprintf(last,sizeof last,"%s",t);
    int mode=g_hdMode, fwd=2, up=4, boo=0, hasMode=0, introHold=1, everyS=600; double boomaxM=12.0; char buf[256]; snprintf(buf,sizeof buf,"%s",t); char* save=0;
    for(char* tk=strtok_r(buf," \t\r\n",&save); tk; tk=strtok_r(0," \t\r\n",&save)){
        if(!strcasecmp(tk,"auto")){ mode=0; hasMode=1; } else if(!strcasecmp(tk,"on")){ mode=1; hasMode=1; } else if(!strcasecmp(tk,"off")){ mode=2; hasMode=1; }
        else if(!strcasecmp(tk,"boo")) boo=1;
        else if(!strncasecmp(tk,"fwd=",4)) fwd=ax_parse(tk+4,2); else if(!strncasecmp(tk,"up=",3)) up=ax_parse(tk+3,4);
        else if(!strncasecmp(tk,"boomax=",7)){ boomaxM=atof(tk+7); if(!(boomaxM>=0)||boomaxM>1000) boomaxM=12.0; }
        else if(!strncasecmp(tk,"intro=",6)) introHold=strcasecmp(tk+6,"free")!=0;
        else if(!strncasecmp(tk,"every=",6)){ double v=atof(tk+6); if(!(v>=10)) v=10; if(v>86400) v=86400; everyS=(int)(v+0.5); } }
    if(!t[0]){ mode=0; hasMode=1; }                                     // no file = auto
    if((fwd>>1)==(up>>1)){ LOGI("[HEAD] head.txt: fwd=%s up=%s can't share an axis -> keeping +y/+z",ax_name(fwd),ax_name(up)); fwd=2; up=4; }
    g_hdFwdAx=fwd; g_hdUpAx=up; g_hdMode=mode; if(boo) g_hdBooReq=1; g_hdBooMaxCm=(int)(boomaxM*100.0+0.5); g_hdIntroHold=introHold; g_hdEveryS=everyS;
    char bm[32]; if(boomaxM>0) snprintf(bm,sizeof bm,"%.0f m",boomaxM); else snprintf(bm,sizeof bm,"any distance");
    LOGI("[HEAD] head.txt: mode=%s%s%s fwd=%s up=%s boomax=%s intro=%s every=%d s (+-20 %%)",mode==1?"on":mode==2?"off":"auto",hasMode?"":" (kept)",boo?" + boo":"",
        ax_name(fwd),ax_name(up),bm,introHold?"hold":"free",everyS); }
static void head_poll(){
    if(!g_resolved||!orig_pe) return; static int n=0; n++;
    if((n%4)==1){
        if(!g_fnLoadSM) g_fnLoadSM=find_by_path("/Script/glTFRuntime.glTFRuntimeAsset.LoadStaticMesh",0);
        if(!g_smcCls)   g_smcCls  =find_by_path("/Script/Engine.StaticMeshComponent",1);
        if(!g_fnSetSM)  g_fnSetSM =find_by_path("/Script/Engine.StaticMeshComponent.SetStaticMesh",0);
        if(!g_fnHdSetWorldLR) g_fnHdSetWorldLR=find_by_path("/Script/Engine.SceneComponent.K2_SetWorldLocationAndRotation",0);
        if(!g_fnSockXf){ g_fnSockXf=find_by_path("/Script/Engine.SceneComponent.GetSocketTransform",0);
            if(g_fnSockXf){ g_hdSoName=prop_offset(g_fnSockXf,"InSocketName",0); g_hdSoSpace=prop_offset(g_fnSockXf,"TransformSpace",0); g_hdSoRet=prop_offset(g_fnSockXf,"ReturnValue",0); } }
        static bool said=false; if(!said&&g_fnLoadSM&&g_smcCls&&g_fnSetSM&&g_fnHdSetWorldLR){ said=true;
            LOGI("[HEAD] resolved: LoadStaticMesh=0x%lx StaticMeshComponent=0x%lx SetStaticMesh=0x%lx setWorld=0x%lx socketXf=0x%lx",
                (unsigned long)g_fnLoadSM,(unsigned long)g_smcCls,(unsigned long)g_fnSetSM,(unsigned long)g_fnHdSetWorldLR,(unsigned long)g_fnSockXf); } }
    uintptr_t cap=g_hdCap; if(cap&&obj_at(rd32(cap+OFF_Index))!=cap){ g_hdCap=0; LOGI("[HEAD] selfie-stick camera gone"); }
    if(!g_hdCap&&g_hdMesh&&(n%4)==3){ uintptr_t st=find_live_class_sub("SelfieStick");   // BP_SelfieStick_C / 2311 TribeSelfieStick
        if(st){ int oc=prop_offset(rdptr(st+OFF_Class),"CaptureComponent2D",0); uintptr_t c=oc>=0?rdptr(st+oc):0;
            if(c){ g_hdCap=c; LOGI("[HEAD] selfie-stick camera 0x%lx (the boo target)",(unsigned long)c); } } }
    if((n%2)==0) head_read_cfg(); }
