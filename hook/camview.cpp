// camview.cpp: an extra stream camera for a stage, on a new button in Tribe's camera menu (the Halloween session,
// 2026-10-18; first use: Graveyard Shift's "Crowd" camera on the FOH mausoleum). dumper.cpp includes it after intro.cpp
// and calls camview_poll (poll thread, ~1 s), camview_tick (game thread, after intro_tick, before drone_update) and
// camview_pe (ProcessEvent, before the menu intercepts). Inert unless the stage that's up has
// tribemod/camview.<folder>.txt; tribemod/camview_off turns it all off. Logs [CAMVIEW].
//
// The user (2026-10-18): "add another camera view to the selfie camera AND another camera view entirely. well both will
// have it. its a camera in the crowd about where the middle platform is looking at the dj", then a brand-new button
// ("we've already done that with the stages in the ui"). The selfie-camera half is data: a fov= shot in the stage's
// drone_path.<folder>.txt (drone_update publishes the shot's fov in g_dShotFov; the FOV is applied here). This file:
//   - finds the camera menu (Tribe 0.12.6 / 2311: the native TribeVisualsMenuWidget, its widgets built in C++; 0.12.5.1 /
//     2304: the Blueprint W_VisualsMenu_C) and its camera buttons (SelfieCameraButton, CameraButton1..8), works out
//     their rows and cells (the widgets between a row and a button), clones one cell (GameplayStatics.SpawnObject of each
//     widget class + every style property that has a one-parameter setter of the same type: SetStyle, SetBrush, SetFont,
//     SetPadding, ...) and adds the clone to the shortest row (ties: the last one), labelled from the file. On 2311 all
//     eight buttons sit straight in one VerticalBox (VerticalBox_117, read from the menu's C++ builder), so that box is
//     the one row and the clone of its last camera button (CameraButton8 + its TextBlock) goes in below it;
//   - a press on it (Button.IsPressed, polled every frame) runs Tribe's own Selfie handler, so the stream shows the
//     selfie capture, then parks that capture at the file's view: drone_update takes g_viewP / g_viewA (a stage intro
//     still wins) and the capture's FOV is the file's while it holds;
//   - any of Tribe's camera buttons (their handlers pass ProcessEvent: 2304's BndEvt events, 2311's HandleCamera<d> /
//     HandleSelfieCamera, bound to OnClicked as dynamic delegates) gives the camera back; the reel resumes.
// Tribe marks the picked camera by restyling its cell, so ours takes the Selfie cell's look right after Tribe picked the
// Selfie, and the Selfie cell takes an unpicked cell's look. The layout and every cell's look are logged once per menu
// and after Tribe's first camera clicks ([CAMVIEW] tree / looks), so a build that guessed the layout wrong says how.
//
// camview.<folder>.txt (key=value, '#' comments):
//   label=Crowd          the button's text
//   pos=x,y,z            Tribe world cm (the DJ rig at the origin, the crowd toward -Y)
//   look=dj|x,y,z        what it aims at (dj: your head, smoothed over 1.5 s)
//   fov=40               horizontal degrees (Tribe's stream cameras use 90)
//   sway=0               cm of slow handheld drift (0: locked off)
static bool file_present(const char* name);          // dumper.cpp, further down
static void menu_resolve_engine_fns();
static int cv_unpicked(int skip);
static void cv_log_looks(const char* when);

struct CView { char label[32]; double pos[3], look[3], fov, sway; int lookDJ; };
static CView g_cvView[2]; static volatile sig_atomic_t g_cvIdx=-1, g_cvOff=0, g_cvBuiltAny=0;
static char g_cvFile[64]="";
static volatile uintptr_t g_cvMenu=0;                                // the live camera menu (poll thread): see CV_MENU_CLS
static uintptr_t g_cvFnSelfie=0, g_cvFnPressed=0, g_cvFnVis=0, g_cvFnAddChild=0, g_cvFnText2Str=0, g_cvKTL=0;
#define CV_NFN 16
static uintptr_t g_cvCamFn[CV_NFN]; static int g_cvCamBtn[CV_NFN]; static volatile int g_cvNCamFn=0;   // handler -> button
static const char* const CV_BTN[9]={"SelfieCameraButton","CameraButton1","CameraButton2","CameraButton3","CameraButton4",
                                    "CameraButton5","CameraButton6","CameraButton7","CameraButton8"};
// game thread
static uintptr_t g_cvCell=0, g_cvBtn=0, g_cvText=0, g_cvFor=0;     // our cell, its button and label, the menu it is in
static uintptr_t g_cvTribeCell[9];                                  // Tribe's cells by button (0 = Selfie)
static int g_cvTries=0, g_cvBuilds=0, g_cvVis=-1, g_cvOn=0, g_cvWasPressed=0, g_cvLastPick=-1, g_cvLooksLogged=0;
static char g_cvShownLabel[32]="";
static int g_cvOffSlot=-2, g_cvOffParent=-1, g_cvOffContent=-1, g_cvOffSlots=-1, g_cvOffWT=-1;

static bool cv_parse(CView* v,const char* text){
    memset(v,0,sizeof *v); snprintf(v->label,sizeof v->label,"Crowd"); v->lookDJ=1; bool havePos=false;
    char buf[2048]; snprintf(buf,sizeof buf,"%s",text); char* save=0;
    for(char* ln=strtok_r(buf,"\n",&save); ln; ln=strtok_r(0,"\n",&save)){
        ln[strcspn(ln,"\r#")]=0; char* eq=strchr(ln,'='); if(!eq) continue; *eq=0;
        char* k=ln; while(*k==' '||*k=='\t') k++;
        for(char* e=eq-1; e>=k&&(*e==' '||*e=='\t'); e--) *e=0;
        char* v2=eq+1; while(*v2==' '||*v2=='\t') v2++;
        size_t L=strlen(v2); while(L&&(v2[L-1]==' '||v2[L-1]=='\t')) v2[--L]=0;
        if(!strcmp(k,"label")){ if(v2[0]) snprintf(v->label,sizeof v->label,"%s",v2); }
        else if(!strcmp(k,"pos")) havePos=parse_xyz(v2,v->pos);
        else if(!strcmp(k,"look")) v->lookDJ=!strcmp(v2,"dj")?1:(parse_xyz(v2,v->look)?0:1);
        else if(!strcmp(k,"fov")) v->fov=fmin(fmax(atof(v2),10.0),120.0);
        else if(!strcmp(k,"sway")) v->sway=fmin(fmax(atof(v2),0.0),300.0); }
    return havePos; }

// ---- reflection helpers
static bool cv_is_a(uintptr_t cls,const char* name){                 // the class or one of its supers is called `name`
    char nm[96]; int d=0;
    for(uintptr_t c=cls; c&&d<16; c=rdptr(c+OFF_Super),d++){ obj_name(c,nm,sizeof nm); if(!strcmp(nm,name)) return true; }
    return false; }
static bool cv_read_bool(uintptr_t obj,uintptr_t f,int S){           // FBoolProperty {FieldSize,ByteOffset,ByteMask,FieldMask}
    uint8_t bo=rd8(f+S+1), fm=rd8(f+S+3); if(bo>7||!fm) return false;
    return (rd8(obj+rd32(f+FP_Offset)+bo)&fm)!=0; }
static bool cv_type_ok(const char* ty){
    return !strcmp(ty,"StructProperty")||!strcmp(ty,"FloatProperty")||!strcmp(ty,"DoubleProperty")||!strcmp(ty,"IntProperty")
         ||!strcmp(ty,"ByteProperty")||!strcmp(ty,"EnumProperty")||!strcmp(ty,"BoolProperty")||!strcmp(ty,"NameProperty"); }
static void cv_setter_name(const char* prop,char* out,int n){
    if(!strcmp(prop,"WidgetStyle")) snprintf(out,n,"SetStyle");             // UButton
    else if(!strcmp(prop,"Background")) snprintf(out,n,"SetBrush");         // UBorder
    else if(prop[0]=='b'&&prop[1]>='A'&&prop[1]<='Z') snprintf(out,n,"Set%s",prop+1);
    else snprintf(out,n,"Set%s",prop); }
// the class's setter `sname` when it takes exactly one parameter of the property's type (no return value): its ParmsSize
static uintptr_t cv_setter_scan(uintptr_t cls,const char* sname,uintptr_t prop,int S,int* psz){
    uintptr_t fn=em_find_child_func(cls,sname); if(!fn) return 0;
    uintptr_t par=0; int np=0;
    for(uintptr_t f=rdptr(fn+OFF_ChildProps); f; f=rdptr(f+FF_Next)){ char nm[64]; fname_resolve(rd32(f+FF_Name),nm,sizeof nm);
        if(!strcmp(nm,"ReturnValue")) return 0; np++; par=f; }
    if(np!=1||!par||rd32(par+FP_Offset)!=0) return 0;
    char t1[48], t2[48]; ffield_type(prop,t1,sizeof t1); ffield_type(par,t2,sizeof t2); if(strcmp(t1,t2)) return 0;
    if(!strcmp(t1,"StructProperty")&&rdptr(prop+S)!=rdptr(par+S)) return 0;
    int n=(int)rd16(fn+0xB6); if(n<=0||n>4096) return 0;
    *psz=n; return fn; }
// cached by (class, property), misses too: a look comparison then costs no function-name scans (no hitch on a press)
struct CvSet { uintptr_t cls, prop, fn; int psz; };
static CvSet g_cvSet[1024]; static int g_cvSetN=0;
static uintptr_t cv_setter(uintptr_t cls,const char* sname,uintptr_t prop,int S,int* psz){
    uint32_t h=(uint32_t)(((cls>>4)*2654435761u)^((prop>>3)*40503u))&1023u;
    for(int i=0;i<1024;i++){ CvSet& e=g_cvSet[(h+(uint32_t)i)&1023u];
        if(e.cls==cls&&e.prop==prop){ *psz=e.psz; return e.fn; }
        if(!e.cls){ int n=0; uintptr_t fn=cv_setter_scan(cls,sname,prop,S,&n);
            if(g_cvSetN<900){ e.cls=cls; e.prop=prop; e.fn=fn; e.psz=n; g_cvSetN++; }
            *psz=n; return fn; } }
    return cv_setter_scan(cls,sname,prop,S,psz); }
// copy (mode 0) every style property of src that dst's class can set with its own setter, or hash them (mode 1)
static int cv_props(uintptr_t dst,uintptr_t src,bool withVis,int mode,uint32_t* hash,char* names,int nn){
    int S=calib_fprop_size(); if(!src||S<0||(mode==0&&!dst)) return 0;
    uintptr_t sc=rdptr(src+OFF_Class), dc=mode==0?rdptr(dst+OFF_Class):sc; uint32_t ssz=rd32(sc+OFF_PropSize);
    static uint8_t b[4096] __attribute__((aligned(16))); int n=0, k=0; if(names&&nn>0) names[0]=0;
    for(uintptr_t c=sc; c; c=rdptr(c+OFF_Super))
        for(uintptr_t f=rdptr(c+OFF_ChildProps); f; f=rdptr(f+FF_Next)){
            char nm[96], ty[48]; fname_resolve(rd32(f+FF_Name),nm,sizeof nm); ffield_type(f,ty,sizeof ty);
            if(!cv_type_ok(ty)||!strncmp(nm,"bOverride_",10)) continue;
            if(!strcmp(nm,"Text")||!strcmp(nm,"Slot")||(!withVis&&!strcmp(nm,"Visibility"))) continue;
            char ov[112]; snprintf(ov,sizeof ov,"bOverride_%s",nm); uintptr_t fo=find_prop(sc,ov);
            if(fo&&!cv_read_bool(src,fo,S)) continue;                     // SizeBox-style overrides: only those in use
            char sn[112]; cv_setter_name(nm,sn,sizeof sn); int pn=0; uintptr_t fn=cv_setter(dc,sn,f,S,&pn); if(!fn) continue;
            bool isBool=!strcmp(ty,"BoolProperty"); uint32_t off=rd32(f+FP_Offset);
            if(!isBool&&off+(uint32_t)pn>ssz) continue;
            memset(b,0,pn);
            if(isBool) b[0]=cv_read_bool(src,f,S)?1:0; else if(!sr(src+off,b,pn)) continue;
            if(mode==0) call_uf(dst,fn,b);
            else if(hash){ uint32_t h=*hash; for(int i=0;i<(isBool?1:pn);i++) h=(h^b[i])*16777619u; *hash=h; }
            n++; if(names&&k<nn-40) k+=snprintf(names+k,nn-k," %s",nm); }
    return n; }
static void cv_offsets(uintptr_t anyWidget){
    if(g_cvOffSlot!=-2) return;
    uintptr_t wc=rdptr(anyWidget+OFF_Class); g_cvOffSlot=prop_offset(wc,"Slot",0);
    uintptr_t ps=find_by_path("/Script/UMG.PanelSlot",1), pw=find_by_path("/Script/UMG.PanelWidget",1), uw=find_by_path("/Script/UMG.UserWidget",1);
    g_cvOffParent=ps?prop_offset(ps,"Parent",0):-1; g_cvOffContent=ps?prop_offset(ps,"Content",0):-1;
    g_cvOffSlots=pw?prop_offset(pw,"Slots",0):-1; g_cvOffWT=uw?prop_offset(uw,"WidgetTree",0):-1;
    LOGI("[CAMVIEW] offsets: Widget.Slot@%d PanelSlot.Parent@%d .Content@%d PanelWidget.Slots@%d UserWidget.WidgetTree@%d",
         g_cvOffSlot,g_cvOffParent,g_cvOffContent,g_cvOffSlots,g_cvOffWT); }
static uintptr_t cv_slot(uintptr_t w){ return (w&&g_cvOffSlot>=0)?rdptr(w+g_cvOffSlot):0; }
static uintptr_t cv_parent(uintptr_t w){ uintptr_t s=cv_slot(w); return (s&&g_cvOffParent>=0)?rdptr(s+g_cvOffParent):0; }
static int cv_children(uintptr_t panel,uintptr_t* out,int cap){       // a panel's children in slot order (0: not a panel)
    if(!panel||g_cvOffSlots<0||g_cvOffContent<0||!cv_is_a(rdptr(panel+OFF_Class),"PanelWidget")) return 0;
    uintptr_t data=rdptr(panel+g_cvOffSlots); int num=(int)rd32(panel+g_cvOffSlots+8), n=0;
    if(!data||num<=0||num>64) return 0;
    for(int i=0;i<num&&n<cap;i++){ uintptr_t s=rdptr(data+8*(uintptr_t)i); uintptr_t c=s?rdptr(s+g_cvOffContent):0; if(c) out[n++]=c; }
    return n; }
static void cv_text_of(uintptr_t tb,char* out,int n){                 // TextBlock.Text -> ASCII (KismetTextLibrary.Conv_TextToString)
    snprintf(out,n,"?"); static int oT=-2, oIn=-1, oRet=-1;
    if(!tb||!g_cvFnText2Str||!g_cvKTL) return;
    if(oT==-2){ oT=prop_offset(rdptr(tb+OFF_Class),"Text",0); oIn=prop_offset(g_cvFnText2Str,"InText",0); oRet=prop_offset(g_cvFnText2Str,"ReturnValue",0); }
    uint16_t psz=rd16(g_cvFnText2Str+0xB6); static uint8_t b[96] __attribute__((aligned(16)));
    if(oT<0||oIn<0||oRet<0||psz>sizeof b||oIn+16>psz) return;
    memset(b,0,sizeof b); if(!sr(tb+oT,b+oIn,16)) return;               // the FText's bytes; the buffer is never destructed
    call_uf(g_cvKTL,g_cvFnText2Str,b); read_fstring((uintptr_t)(b+oRet),out,n); }
static uint32_t cv_look(uintptr_t w,int depth){                      // a cell's look: its widgets' style values, hashed
    uint32_t h=2166136261u; if(!w||depth>6) return h;
    cv_props(0,w,depth>0,1,&h,0,0);
    uintptr_t ch[16]; int n=cv_children(w,ch,16);
    for(int i=0;i<n;i++){ uint32_t c=cv_look(ch[i],depth+1); h=(h^c)*16777619u; }
    return h; }
static void cv_dump(uintptr_t w,int depth,int* lines){                // the camera area's widgets, once per menu
    if(!w||depth>7||*lines>=90) return; (*lines)++;
    char cn[64], nm[96], sc[48]="-", tx[64]=""; class_name(w,cn,sizeof cn); obj_name(w,nm,sizeof nm);
    uintptr_t s=cv_slot(w); if(s) class_name(s,sc,sizeof sc);
    static int oVis=-2; if(oVis==-2) oVis=prop_offset(rdptr(w+OFF_Class),"Visibility",0);
    if(cv_is_a(rdptr(w+OFF_Class),"TextBlock")){ char t[48]; cv_text_of(w,t,sizeof t); snprintf(tx,sizeof tx," '%s'",t); }
    LOGI("[CAMVIEW] tree %*s%s %s vis=%d slot=%s look=%08x%s",depth*2,"",cn,nm,oVis>=0?(int)rd8(w+oVis):-1,sc,cv_look(w,6),tx);
    uintptr_t ch[24]; int n=cv_children(w,ch,24); for(int i=0;i<n;i++) cv_dump(ch[i],depth+1,lines); }
static uintptr_t cv_add_child(uintptr_t panel,uintptr_t child){      // PanelWidget.AddChild(Content) -> its new slot
    static int oC=-2, oR=-1; if(!g_cvFnAddChild) return 0;
    if(oC==-2){ oC=prop_offset(g_cvFnAddChild,"Content",0); oR=prop_offset(g_cvFnAddChild,"ReturnValue",0); }
    uint16_t psz=rd16(g_cvFnAddChild+0xB6); uint8_t b[32] __attribute__((aligned(16))); if(oC<0||oR<0||psz>sizeof b) return 0;
    memset(b,0,sizeof b); memcpy(b+oC,&child,8); call_uf(panel,g_cvFnAddChild,b); uintptr_t s; memcpy(&s,b+oR,8); return s; }
static void cv_set_vis(uintptr_t w,int vis){                          // ESlateVisibility: 0 Visible, 1 Collapsed, 2 Hidden
    if(!w||!g_cvFnVis) return; uint8_t b[16]={0}; if(rd16(g_cvFnVis+0xB6)>sizeof b) return; b[0]=(uint8_t)vis; call_uf(w,g_cvFnVis,b); }
static void cv_set_text(uintptr_t tb,const char* label){
    static int oT=-2; if(!tb||!g_smFnSetText) return; if(oT==-2) oT=prop_offset(g_smFnSetText,"InText",0);
    uint16_t psz=rd16(g_smFnSetText+0xB6); uint8_t txt[64]; static uint8_t b[128] __attribute__((aligned(16)));
    if(oT<0||psz>sizeof b) return; int n=make_text(label,txt,sizeof txt); if(n<=0||oT+n>psz) return;
    memset(b,0,psz); memcpy(b+oT,txt,n); call_uf(tb,g_smFnSetText,b); }
static void cv_set_int(uintptr_t obj,const char* setter,int v){      // SetRow / SetColumn on a grid slot
    uintptr_t fn=obj?em_find_child_func(rdptr(obj+OFF_Class),setter):0; if(!fn) return;
    uint8_t b[16] __attribute__((aligned(16))); memset(b,0,sizeof b); if(rd16(fn+0xB6)>sizeof b) return; memcpy(b,&v,4); call_uf(obj,fn,b); }
static int cv_get_int(uintptr_t obj,const char* prop){ int o=obj?prop_offset(rdptr(obj+OFF_Class),prop,0):-1; return o>=0?(int)rd32(obj+o):-1; }
// clone a widget subtree (not UserWidgets: those need CreateWidget); records the clone of `tplBtn` and the first TextBlock
static uintptr_t cv_clone(uintptr_t src,uintptr_t outer,int depth,uintptr_t tplBtn,uintptr_t* outBtn,uintptr_t* outText){
    if(!src||depth>6) return 0;
    uintptr_t cls=rdptr(src+OFF_Class); char cn[64], nm[96]; obj_name(cls,cn,sizeof cn); obj_name(src,nm,sizeof nm);
    if(cv_is_a(cls,"UserWidget")){ LOGI("[CAMVIEW] can't clone %s %s: a UserWidget (needs CreateWidget)",cn,nm); return 0; }
    uintptr_t w=sm_spawn(cls,outer); if(!w){ LOGI("[CAMVIEW] SpawnObject(%s) failed",cn); return 0; }
    char props[700]; int n=cv_props(w,src,depth>0,0,0,props,sizeof props);
    LOGI("[CAMVIEW] clone %*s%s %s -> 0x%lx, %d setters:%s",depth*2,"",cn,nm,(unsigned long)w,n,props);
    if(src==tplBtn) *outBtn=w;
    if(!*outText&&cv_is_a(cls,"TextBlock")) *outText=w;
    if(cv_is_a(cls,"PanelWidget")&&g_cvOffSlots>=0){
        uintptr_t data=rdptr(src+g_cvOffSlots); int num=(int)rd32(src+g_cvOffSlots+8);
        for(int i=0;data&&i<num&&i<16;i++){ uintptr_t s=rdptr(data+8*(uintptr_t)i); uintptr_t c=s?rdptr(s+g_cvOffContent):0; if(!c) continue;
            uintptr_t nc=cv_clone(c,outer,depth+1,tplBtn,outBtn,outText); if(!nc) return 0;
            uintptr_t ns=cv_add_child(w,nc); if(!ns){ LOGI("[CAMVIEW] AddChild into the clone of %s failed",nm); return 0; }
            cv_props(ns,s,true,0,0,0,0); } }
    return w; }
static void cv_copy_look(uintptr_t dst,uintptr_t src,int depth){     // restyle a cell like another of the same build
    if(!dst||!src||depth>6||!obj_alive(dst)||!obj_alive(src)||rdptr(dst+OFF_Class)!=rdptr(src+OFF_Class)) return;
    cv_props(dst,src,depth>0,0,0,0,0);
    uintptr_t a[16], b2[16]; int na=cv_children(dst,a,16), nb=cv_children(src,b2,16);
    for(int i=0;i<na&&i<nb;i++) cv_copy_look(a[i],b2[i],depth+1); }

// ---- build our cell in Tribe's camera menu (game thread)
static void cv_build(uintptr_t m,const CView* v){
    uintptr_t mc=rdptr(m+OFF_Class), btn[9]={0}; int nb=0;
    for(int i=0;i<9;i++){ int o=prop_offset(mc,CV_BTN[i],0); uintptr_t b=o>=0?rdptr(m+o):0; if(b&&obj_alive(b)){ btn[i]=b; nb++; } }
    if(nb<2||!btn[0]){ LOGI("[CAMVIEW] the camera menu has %d of its buttons (Selfie %s): not adding ours",nb,btn[0]?"found":"MISSING"); return; }
    uintptr_t any=btn[0]; cv_offsets(any);
    if(g_cvOffSlot<0||g_cvOffParent<0||g_cvOffContent<0||g_cvOffSlots<0){ LOGI("[CAMVIEW] UMG layout offsets missing: not adding ours"); return; }
    uintptr_t ch[9][12]; int cl[9]={0};                                // each button's chain up the widget tree
    for(int i=0;i<9;i++) for(uintptr_t w=btn[i]; w&&cl[i]<12; w=cv_parent(w)) ch[i][cl[i]++]=w;
    uintptr_t lca=0;                                                  // the deepest panel holding every camera button
    for(int a=1;a<cl[0]&&!lca;a++){ bool all=true;
        for(int i=1;i<9&&all;i++){ if(!btn[i]) continue; bool in=false; for(int j=0;j<cl[i];j++) if(ch[i][j]==ch[0][a]) in=true; if(!in) all=false; }
        if(all) lca=ch[0][a]; }
    if(!lca){ LOGI("[CAMVIEW] the camera buttons share no panel: not adding ours"); return; }
    // under the LCA: the child each button sits in (top), and the one below that (sub)
    uintptr_t top[9]={0}, sub[9]={0};
    for(int i=0;i<9;i++){ if(!btn[i]) continue; for(int j=0;j<cl[i];j++) if(ch[i][j]==lca){ top[i]=j>=1?ch[i][j-1]:0; sub[i]=j>=2?ch[i][j-2]:0; break; } }
    // rows: a top shared by two or more buttons. A button alone under the LCA (a big Selfie button, say) is its own cell
    // and never a row; with no shared tops, the LCA is the one row and each top is a cell.
    int shared[9]={0}; bool rows=false;
    for(int i=0;i<9;i++) for(int k=0;k<9;k++) if(i!=k&&top[i]&&top[i]==top[k]){ shared[i]=1; rows=true; }
    uintptr_t rowOf[9]={0};
    for(int i=0;i<9;i++){ if(!btn[i]) continue;
        if(!rows){ rowOf[i]=lca; g_cvTribeCell[i]=top[i]?top[i]:btn[i]; }
        else if(shared[i]){ rowOf[i]=top[i]; g_cvTribeCell[i]=sub[i]?sub[i]:btn[i]; }
        else g_cvTribeCell[i]=top[i]?top[i]:btn[i]; }                  // not in a row: no target for ours
    // the target row: the fewest children, ties to the later one; the template: its last camera cell
    uintptr_t lcaKids[24]; int nl=cv_children(lca,lcaKids,24);
    uintptr_t row=0; int rowN=1<<30, rowPos=-1;
    for(int i=0;i<9;i++){ if(!rowOf[i]) continue; uintptr_t kids[24]; int n=cv_children(rowOf[i],kids,24);
        int pos=0; for(int j=0;j<nl;j++) if(lcaKids[j]==rowOf[i]) pos=j;
        if(n<rowN||(n==rowN&&pos>rowPos)){ row=rowOf[i]; rowN=n; rowPos=pos; } }
    uintptr_t tpl=0; int tplPos=-1, tplBtnIx=-1; { uintptr_t kids[24]; int n=cv_children(row,kids,24);
        for(int i=0;i<9;i++){ if(rowOf[i]!=row||!g_cvTribeCell[i]) continue; for(int j=0;j<n;j++) if(kids[j]==g_cvTribeCell[i]&&j>tplPos){ tplPos=j; tpl=g_cvTribeCell[i]; tplBtnIx=i; } } }
    if(!tpl){ LOGI("[CAMVIEW] no template cell in the target row: not adding ours"); return; }
    char lc[64], ln[96], rc[64], rn[96], tc[64], tn[96];
    class_name(lca,lc,sizeof lc); obj_name(lca,ln,sizeof ln); class_name(row,rc,sizeof rc); obj_name(row,rn,sizeof rn); class_name(tpl,tc,sizeof tc); obj_name(tpl,tn,sizeof tn);
    LOGI("[CAMVIEW] camera menu 0x%lx: %d buttons under %s %s; %s; target row %s %s (%d children), template cell %s %s (%s)",
         (unsigned long)m,nb,lc,ln,rows?"in rows":"one row",rc,rn,rowN,tc,tn,CV_BTN[tplBtnIx]);
    { int lines=0; cv_dump(lca,0,&lines); }
    uintptr_t outer=g_cvOffWT>=0?rdptr(m+g_cvOffWT):0; if(!outer) outer=m;
    uintptr_t ourBtn=0, ourText=0; g_cvBuilds++;
    uintptr_t cell=cv_clone(tpl,outer,0,btn[tplBtnIx],&ourBtn,&ourText);
    if(!cell||!ourBtn){ LOGI("[CAMVIEW] cloning the template cell failed (cell 0x%lx button 0x%lx)",(unsigned long)cell,(unsigned long)ourBtn); return; }
    uintptr_t ns=cv_add_child(row,cell);
    if(!ns){ LOGI("[CAMVIEW] AddChild into the row failed"); return; }
    uintptr_t ts=cv_slot(tpl); if(ts) cv_props(ns,ts,true,0,0,0,0);    // the template's padding / size / alignment
    char sc[48]="-"; class_name(ns,sc,sizeof sc);
    if(cv_is_a(rdptr(ns+OFF_Class),"UniformGridSlot")||cv_is_a(rdptr(ns+OFF_Class),"GridSlot")){   // grids place by row/column
        int r=cv_get_int(ts,"Row"), c=cv_get_int(ts,"Column"); cv_set_int(ns,"SetRow",r); cv_set_int(ns,"SetColumn",c+1);
        LOGI("[CAMVIEW] grid slot: row %d column %d (the template's +1 column)",r,c+1); }
    if(ourText){ cv_set_text(ourText,v->label); snprintf(g_cvShownLabel,sizeof g_cvShownLabel,"%s",v->label); }
    cv_set_vis(cell,0); g_cvVis=0;
    g_cvCell=cell; g_cvBtn=ourBtn; g_cvText=ourText; g_cvFor=m; g_cvBuiltAny=1; g_cvWasPressed=0;
    { int u=cv_unpicked(g_cvLastPick); if(u>=0) cv_copy_look(cell,g_cvTribeCell[u],0); }   // in case the template is the picked one
    { uintptr_t fe=em_find_child_func(rdptr(ourBtn+OFF_Class),"SetIsEnabled"); uint8_t b[16]={1};  // and pressable, whatever it copied
      if(fe&&rd16(fe+0xB6)<=sizeof b) call_uf(ourBtn,fe,b); }
    cv_log_looks("when ours was added");
    LOGI("[CAMVIEW] added '%s': cell 0x%lx (%s in %s), button 0x%lx, label 0x%lx; build %d",v->label,(unsigned long)cell,sc,rn,
         (unsigned long)ourBtn,(unsigned long)ourText,g_cvBuilds); }
// Tribe's cells built like ours (same root class), by look: the most common look is "not picked". A cell with it, not `skip`.
static int cv_unpicked(int skip){
    uint32_t h[9]={0}; int ok[9]={0};
    for(int i=0;i<9;i++){ uintptr_t c=g_cvTribeCell[i];
        if(i!=skip&&c&&g_cvCell&&obj_alive(c)&&rdptr(c+OFF_Class)==rdptr(g_cvCell+OFF_Class)){ h[i]=cv_look(c,0); ok[i]=1; } }
    int best=-1, bestN=0;
    for(int i=0;i<9;i++){ if(!ok[i]) continue; int c=0; for(int j=0;j<9;j++) if(ok[j]&&h[j]==h[i]) c++; if(c>bestN){ bestN=c; best=i; } }
    return best; }
static void cv_log_looks(const char* when){
    char line[400]; int k=snprintf(line,sizeof line,"[CAMVIEW] looks %s:",when);
    for(int i=0;i<9&&k<(int)sizeof line-24;i++) if(g_cvTribeCell[i]&&obj_alive(g_cvTribeCell[i]))
        k+=snprintf(line+k,sizeof line-k," %s=%08x",i?CV_BTN[i]+12:"Selfie",cv_look(g_cvTribeCell[i],0));
    if(g_cvCell&&obj_alive(g_cvCell)) snprintf(line+k,sizeof line-k," ours=%08x",cv_look(g_cvCell,0));
    LOGI("%s",line); }
static void cv_release(const char* why,int picked){                   // the camera goes back to Tribe / the reel
    if(!g_cvOn) return; g_cvOn=0; g_viewCam=0;
    int u=cv_unpicked(picked); if(u>=0&&g_cvCell) cv_copy_look(g_cvCell,g_cvTribeCell[u],0);
    LOGI("[CAMVIEW] the camera goes back (%s)",why); }
static void cv_select(int ix){                                        // a press on our button
    uintptr_t m=g_cvMenu; if(!m||!obj_alive(m)) return;
    if(g_droneTarget==1){ LOGI("[CAMVIEW] drone.txt has target=auto: the '%s' camera flies the selfie camera, so it stays off",g_cvView[ix].label); return; }
    if(!g_cvFnSelfie){ LOGI("[CAMVIEW] Tribe's Selfie handler wasn't found: can't put the stream on the selfie camera"); return; }
    uint16_t psz=rd16(g_cvFnSelfie+0xB6); static uint8_t b[256] __attribute__((aligned(16))); if(psz>sizeof b) return;
    memset(b,0,sizeof b); call_uf(m,g_cvFnSelfie,b);                  // Tribe's own Selfie press: the stream shows the selfie capture
    g_cvLastPick=0;
    if(g_cvTribeCell[0]&&g_cvCell){                                   // ours takes the picked look, the Selfie cell an unpicked one
        int u=cv_unpicked(0);                                         // (each only between cells built alike: cv_copy_look checks)
        cv_copy_look(g_cvCell,g_cvTribeCell[0],0); if(u>=0) cv_copy_look(g_cvTribeCell[0],g_cvTribeCell[u],0); }
    const CView* v=&g_cvView[ix]; g_cvOn=1;
    LOGI("[CAMVIEW] '%s' picked: the selfie camera holds at (%.0f, %.0f, %.0f), fov %.0f%s",v->label,v->pos[0],v->pos[1],v->pos[2],v->fov,
         g_droneCap?"":" (no selfie camera resolved yet)");
    if(g_cvLooksLogged<8){ g_cvLooksLogged++; cv_log_looks("after ours"); } }

// ---- the capture's FOV: the view's while it holds, else the reel shot's fov= (g_dShotFov), else Tribe's
static uintptr_t g_cvFovCap=0; static int g_cvFovOff=-2; static float g_cvFovOrig=0; static bool g_cvFovSaved=false;
static void cv_fov(double want){
    if(g_introCam) return;                                            // a stage intro owns the FOV while it runs (intro_fov)
    uintptr_t cap=g_droneCap;
    static uintptr_t fovCls=0;                                         // mod2311: raw writes only into the class we measured
    if(g_cvFovSaved&&(want<=0||cap!=g_cvFovCap)){
        if(g_cvFovCap&&obj_alive(g_cvFovCap)&&g_cvFovOff>=0&&rdptr(g_cvFovCap+OFF_Class)==fovCls) *(float*)(g_cvFovCap+g_cvFovOff)=g_cvFovOrig;
        g_cvFovSaved=false; LOGI("[CAMVIEW] the stream camera's FOV is Tribe's again (%.1f deg)",g_cvFovOrig); }
    if(want<=0||!cap||!obj_alive(cap)) return;
    if(cap!=g_cvFovCap){ g_cvFovCap=cap; fovCls=rdptr(cap+OFF_Class); uintptr_t fc=0; char ty[48]="?"; g_cvFovOff=prop_offset(fovCls,"FOVAngle",&fc);
        if(fc) fname_resolve(rd32(fc),ty,sizeof ty); if(strcmp(ty,"FloatProperty")) g_cvFovOff=-1; }
    if(g_cvFovOff<0||rdptr(cap+OFF_Class)!=fovCls) return;
    float* p=(float*)(cap+g_cvFovOff);
    if(!g_cvFovSaved){ g_cvFovOrig=*p; g_cvFovSaved=true; LOGI("[CAMVIEW] stream camera FOV %.1f -> %.1f deg",g_cvFovOrig,want); }
    if(*p!=(float)want) *p=(float)want; }

// ---- Tribe's camera menu, either build. 2311 (0.12.6) made it the native TribeVisualsMenuWidget (no native subclass is
// registered and no VisualsMenu asset ships, so its live objects have exactly that class); 2304 (0.12.5.1) had the
// Blueprint W_VisualsMenu_C.
static const char* const CV_MENU_CLS[2]={"TribeVisualsMenuWidget","W_VisualsMenu_C"};
// em_find_live for both names in one pass (no second object-array walk): the newest live one, its class name, how many
static uintptr_t cv_find_menu(char* cls,int n,int* nLive){
    refresh_numelements(); char cn[96]; uintptr_t best=0; int k=0; if(n>0) cls[0]=0;
    for(uint32_t i=0;i<g_numElements;i++){ uintptr_t o=obj_at(i); if(!o) continue;
        if(rd32(o+OFF_Flags)&(RF_ClassDefaultObject|0x20u|0x40000000u)) continue;
        class_name(o,cn,sizeof cn); if(strcmp(cn,CV_MENU_CLS[0])&&strcmp(cn,CV_MENU_CLS[1])) continue;
        best=o; k++; snprintf(cls,n,"%s",cn); }
    *nLive=k; return best; }
// the camera button a menu function picks (index into CV_BTN), -1 if none. 2304: BndEvt__*CameraButton* events (the one
// named CameraButton5 picks CameraButton6: W_VisualsMenu.txt:465-467). 2311: HandleSelfieCamera and HandleCamera<d>, each
// bound to that button's OnClicked; HandleCameraToggle (the camera on/off slider) and HandleResetSelfie are not picks.
static int cv_cam_handler(const char* nm){
    if(!strncmp(nm,"BndEvt__",8)){ if(!strstr(nm,"CameraButton")) return -1;
        if(strstr(nm,"CameraButtonSelife")||strstr(nm,"CameraButtonSelfie")||strstr(nm,"SelfieCameraButton")) return 0;
        const char* q=strstr(nm,"CameraButton"); if(!q||q[12]<'1'||q[12]>'8') return -1;
        return q[12]=='5'?6:q[12]-'0'; }
    if(!strcmp(nm,"HandleSelfieCamera")) return 0;
    if(!strncmp(nm,"HandleCamera",12)&&nm[12]>='1'&&nm[12]<='8'&&!nm[13]) return nm[12]-'0';
    return -1; }

// ---- POLL thread (~1 s): the stage's view file, Tribe's visuals menu and the functions
static void camview_poll(){
    g_cvOff=file_present("camview_off")?1:0;
    char fol[48]="", want[64]="";
    if(!g_cvOff&&em_active_folder(fol,sizeof fol)) snprintf(want,sizeof want,"camview.%s.txt",fol);
    static long lastKey=-2;
    if(strcmp(want,g_cvFile)){ snprintf(g_cvFile,sizeof g_cvFile,"%s",want); g_cvIdx=-1; lastKey=-2; }
    if(want[0]){ char p[600]; snprintf(p,sizeof p,"%s/%s",OUTDIR,want); struct stat st;
        long key=stat(p,&st)==0?(long)st.st_mtime*1000003L+(long)st.st_size:-1;
        if(key!=lastKey){ lastKey=key;
            if(key==-1) g_cvIdx=-1;
            else { char text[2048]; size_t n=0; FILE* f=fopen(p,"rb"); if(f){ n=fread(text,1,sizeof text-1,f); fclose(f); } text[n]=0;
                int nx=g_cvIdx==0?1:0;
                if(cv_parse(&g_cvView[nx],text)){ __sync_synchronize(); g_cvIdx=nx; const CView* v=&g_cvView[nx]; char lk[48];
                    if(v->lookDJ) snprintf(lk,sizeof lk,"you"); else snprintf(lk,sizeof lk,"(%.0f, %.0f, %.0f)",v->look[0],v->look[1],v->look[2]);
                    LOGI("[CAMVIEW] %s: button '%s', camera (%.0f, %.0f, %.0f) looking at %s, fov %.0f, sway %.0f cm",want,v->label,
                         v->pos[0],v->pos[1],v->pos[2],lk,v->fov,v->sway); }
                else LOGI("[CAMVIEW] %s has no pos=x,y,z: %s",want,g_cvIdx>=0?"keeping the old view":"no extra camera"); } } }
    g_viewArmed=g_cvIdx>=0?1:0;
    if(!g_viewArmed&&!g_cvBuiltAny) return;                           // nothing to show, nothing to hide
    if(!g_cvFnPressed){ menu_resolve_engine_fns();
        g_cvFnPressed=find_by_path("/Script/UMG.Button.IsPressed",0); g_cvFnVis=find_by_path("/Script/UMG.Widget.SetVisibility",0);
        g_cvFnAddChild=find_by_path("/Script/UMG.PanelWidget.AddChild",0);
        g_cvFnText2Str=find_by_path("/Script/Engine.KismetTextLibrary.Conv_TextToString",0); g_cvKTL=find_by_path("/Script/Engine.Default__KismetTextLibrary",0);
        LOGI("[CAMVIEW] UMG: IsPressed 0x%lx SetVisibility 0x%lx AddChild 0x%lx TextToString 0x%lx; SpawnObject 0x%lx SetText 0x%lx",
             (unsigned long)g_cvFnPressed,(unsigned long)g_cvFnVis,(unsigned long)g_cvFnAddChild,(unsigned long)g_cvFnText2Str,
             (unsigned long)g_smFnSpawn,(unsigned long)g_smFnSetText); }
    uintptr_t m=g_cvMenu; static int tk=0, miss=0;
    if((!m||!obj_alive(m))&&(tk++%3)==0){ char cls[96]; int nLive=0; m=cv_find_menu(cls,sizeof cls,&nLive);
        if(!m&&(miss++%20)==0) LOGI("[CAMVIEW] no live camera menu (%s / %s) yet: the extra camera button waits for it",CV_MENU_CLS[0],CV_MENU_CLS[1]);
        if(m&&m!=g_cvMenu){ uintptr_t mc=rdptr(m+OFF_Class);
            if(!g_cvNCamFn){ int n=0, d=0; char nm[200];                  // its camera-button handlers (cv_cam_handler), on its
                for(uintptr_t c=mc; c&&d<8&&n<CV_NFN; c=rdptr(c+OFF_Super),d++){   // class or a parent below UserWidget (a
                    obj_name(c,nm,sizeof nm); if(!strcmp(nm,"UserWidget")) break;    // subclass would inherit 2311's natives)
                    for(uintptr_t f=rdptr(c+OFF_Children); f&&n<CV_NFN; f=rdptr(f+0x28)){ obj_name(f,nm,sizeof nm);
                        int b=cv_cam_handler(nm); if(b<0) continue;
                        g_cvCamFn[n]=f; g_cvCamBtn[n]=b; n++; if(b==0) g_cvFnSelfie=f;
                        LOGI("[CAMVIEW] camera handler %d: %s -> %s",n,nm,CV_BTN[b]); } }
                __sync_synchronize(); g_cvNCamFn=n;
                if(!g_cvFnSelfie) LOGI("[CAMVIEW] %s: %d camera handler(s), none for the Selfie button: our button can't switch the stream",cls,n);
                uintptr_t sa=em_find_child_func(mc,"SetActiveCameraButton"); char pl[300]=""; int k=0;
                for(uintptr_t f=sa?rdptr(sa+OFF_ChildProps):0; f&&k<240; f=rdptr(f+FF_Next)){ char pn[64], ty[48];
                    fname_resolve(rd32(f+FF_Name),pn,sizeof pn); ffield_type(f,ty,sizeof ty); k+=snprintf(pl+k,sizeof pl-k," %s:%s",pn,ty); }
                LOGI("[CAMVIEW] %s.SetActiveCameraButton 0x%lx params:%s",cls,(unsigned long)sa,k?pl:" none"); }
            g_cvMenu=m; LOGI("[CAMVIEW] Tribe's visuals menu: 0x%lx (%s, %d live)",(unsigned long)m,cls,nLive); } } }

// ---- GAME thread, every frame
static void camview_tick(float dt){
    int ix=g_cvIdx; bool armed=ix>=0&&!g_cvOff&&g_emState==EM_ACTIVE;
    uintptr_t m=g_cvMenu; bool menuOk=m&&obj_alive(m);
    if(g_cvFor&&(g_cvFor!=m||!menuOk||!g_cvCell||!obj_alive(g_cvCell))){   // the menu was rebuilt: ours went with it
        if(g_cvOn) cv_release("the camera menu was rebuilt",-1);
        g_cvCell=g_cvBtn=g_cvText=g_cvFor=0; g_cvTries=0; g_cvVis=-1; memset(g_cvTribeCell,0,sizeof g_cvTribeCell); }
    // 2311 builds the menu's widgets in C++ (from its RebuildWidget override and from a second virtual that also binds the
    // buttons), so the menu object can be live before its buttons are: no try is spent until its SelfieCameraButton is
    // set, and each new menu object gets its own 3 tries
    static uintptr_t triedFor=0, selCls=0; static int selOff=-1;
    if(m!=triedFor){ triedFor=m; g_cvTries=0; }
    if(menuOk){ uintptr_t mc=rdptr(m+OFF_Class); if(mc!=selCls){ selCls=mc; selOff=prop_offset(mc,"SelfieCameraButton",0); } }
    bool notYet=menuOk&&selOff>=0&&!rdptr(m+selOff);
    if(menuOk&&armed&&!g_cvFor&&!notYet&&g_cvTries<3&&g_cvBuilds<10&&g_cvFnAddChild&&g_smFnSpawn&&g_cvFnVis){ g_cvTries++; cv_build(m,&g_cvView[ix]); }
    bool cellOk=g_cvCell!=0;
    if(cellOk){ int vis=armed?0:1; if(vis!=g_cvVis){ cv_set_vis(g_cvCell,vis); g_cvVis=vis; }
        if(armed&&g_cvText&&strcmp(g_cvShownLabel,g_cvView[ix].label)){ cv_set_text(g_cvText,g_cvView[ix].label);
            snprintf(g_cvShownLabel,sizeof g_cvShownLabel,"%s",g_cvView[ix].label); } }
    if(g_cvOn&&!armed) cv_release(g_cvOff?"tribemod/camview_off":"this stage has no extra camera",-1);
    if(cellOk&&armed&&g_cvBtn&&obj_alive(g_cvBtn)&&g_cvFnPressed){   // a press on ours (no OnClicked binding: polled)
        uint8_t* r=call_ret(g_cvBtn,g_cvFnPressed,0,0); int pr=(r&&*r)?1:0;
        if(pr&&!g_cvWasPressed&&!g_cvOn) cv_select(ix);
        g_cvWasPressed=pr; }
    if(g_cvOn&&ix>=0){ const CView* v=&g_cvView[ix]; static double H[3]={0,87,170}, t=0; static bool haveH=false;
        if(dt>0.f&&dt<0.25f) t+=dt;
        double h[3]; if(v->lookDJ&&g_camComp&&g_fnLoc&&get_vec3(g_camComp,g_fnLoc,h)){
            if(!haveH){ memcpy(H,h,24); haveH=true; } double k=(dt>0.f&&dt<0.25f)?dt/1.5:0; for(int i=0;i<3;i++) H[i]+=(h[i]-H[i])*k; }
        double P[3]={ v->pos[0]+v->sway*sin(t*0.31), v->pos[1], v->pos[2]+0.35*v->sway*sin(t*0.23) };
        memcpy(g_viewP,P,24); if(v->lookDJ) memcpy(g_viewA,H,24); else memcpy(g_viewA,v->look,24); }
    g_viewCam=g_cvOn?1:0;
    cv_fov(g_cvOn&&ix>=0?g_cvView[ix].fov:(double)g_dShotFov); }

// ---- ProcessEvent: Tribe's camera buttons (their handlers on the menu: 2304 BndEvt events, 2311 HandleCamera<d> /
// HandleSelfieCamera through OnClicked's dynamic delegate). true = handled (orig already called)
static bool camview_pe(void* self,void* func,void* parms){
    uintptr_t m=g_cvMenu; if(!m||(uintptr_t)self!=m) return false;
    int n=g_cvNCamFn, k=-1; for(int i=0;i<n;i++) if(g_cvCamFn[i]==(uintptr_t)func){ k=i; break; }
    if(k<0) return false;
    orig_pe(self,func,parms);                                         // Tribe's own camera switch first
    int b=g_cvCamBtn[k]; g_cvLastPick=b;
    if(g_cvOn){ char why[64]; snprintf(why,sizeof why,"Tribe's %s",CV_BTN[b]); cv_release(why,b); }
    if(g_cvFor&&g_cvLooksLogged<8){ g_cvLooksLogged++; char w[48]; snprintf(w,sizeof w,"after Tribe's %s",CV_BTN[b]); cv_log_looks(w); }
    return true; }
