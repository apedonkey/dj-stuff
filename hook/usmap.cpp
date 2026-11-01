// ---- the .usmap dump (one-shot: create tribemod/usmap_now; writes tribemod/TribeXR.usmap + tribemod/usmap_log.txt) ----
// Tribe's paks are cooked unversioned: each property is stored by its index in its class's property list, with no name
// or type, so offline readers (UAssetAPI, CUE4Parse/FModel) need those lists in a .usmap, and Tribe has none (NOTES,
// Phase 3: UAssetAPI left every export raw). This writes one from the running game: every loaded class and struct (not
// functions) with its own properties in ChildProperties order -- the order Unreal's unversioned serializer numbers
// them in, own properties first, then the super's -- and every loaded enum with its values. Poll thread only: the
// reads go through sr() under install_guard(). Layout checks run first; if one fails nothing is written, and
// usmap_log.txt says which. Included by dumper.cpp (needs its readers, the FName pool and the object array).
#include "usmap_writer.h"

static const uint32_t UM_ArrayDim=0x2C;                  // FProperty::ArrayDim (NOTES 3904: ArrayDim@0x2C, ElementSize@0x30)
static const uint32_t UM_EnumNames=0x40;                 // UEnum::Names, TArray<TPair<FName,int64>> (as enum_entries)
enum { UMK_OTHER=1, UMK_STRUCT, UMK_ENUM, UMK_FUNCTION };   // um_kind() of a class; 0 = not cached yet
static uintptr_t g_umStruct=0, g_umFunction=0, g_umEnum=0;  // /Script/CoreUObject.Struct, .Function, .Enum
static int g_umS=-1, g_umArr=-1, g_umOpt=-1;             // sizeof(FProperty); FArrayProperty::Inner and
                                                         // FOptionalProperty's value: S or S+8, voted in um_check
static FILE* g_umLog=0; static UNames g_umNames;
static uint32_t g_umFailName, g_umFailType, g_umFailEnum, g_umFailDim, g_umNonAscii, g_umUnknown, g_umProps,
                g_umStructsOut, g_umEnumsOut;
__attribute__((format(printf,1,2))) static void um_log(const char* fmt,...){ char m[700]; va_list ap; va_start(ap,fmt); vsnprintf(m,sizeof m,fmt,ap); va_end(ap);
    LOGI("[USMAP] %s",m); if(g_umLog){ fprintf(g_umLog,"%s\n",m); fflush(g_umLog); } }

// pointer -> byte map (open addressing, key 0 = empty). Look up again after an insert: growing moves the slots.
struct UmMap { uintptr_t* k; uint8_t* v; uint32_t cap, n; bool oom; };
static UmMap g_umKinds, g_umFTypes, g_umDone;            // class -> kind | FFieldClass -> type | struct -> written
static uint32_t um_ph(uintptr_t p){ return (uint32_t)((((uint64_t)p)>>3)*0x9E3779B97F4A7C15ull>>32); }
static uint8_t um_get(const UmMap* m,uintptr_t key){ if(!m->cap) return 0; uint32_t h=um_ph(key)&(m->cap-1);
    for(;m->k[h];h=(h+1)&(m->cap-1)) if(m->k[h]==key) return m->v[h];
    return 0; }
static void um_set(UmMap* m,uintptr_t key,uint8_t val){
    if((m->n+1)*2>m->cap){ uint32_t nc=m->cap?m->cap*2:4096; uintptr_t* k=(uintptr_t*)calloc(nc,sizeof *k); uint8_t* v=(uint8_t*)calloc(nc,1);
        if(!k||!v){ free(k); free(v); m->oom=true; return; }
        for(uint32_t i=0;i<m->cap;i++) if(m->k[i]){ uint32_t h=um_ph(m->k[i])&(nc-1); while(k[h]) h=(h+1)&(nc-1); k[h]=m->k[i]; v[h]=m->v[i]; }
        free(m->k); free(m->v); m->k=k; m->v=v; m->cap=nc; }
    uint32_t h=um_ph(key)&(m->cap-1);
    for(;m->k[h];h=(h+1)&(m->cap-1)) if(m->k[h]==key){ m->v[h]=val; return; }
    m->k[h]=key; m->v[h]=val; m->n++; }
static void um_free(UmMap* m){ free(m->k); free(m->v); memset(m,0,sizeof *m); }

// FName {u32 ComparisonIndex, u32 Number} -> UTF-8 "Name", or "Name_<Number-1>" (fname_resolve drops the number and
// turns non-ASCII into '?'). Returns the length, or -1.
static int um_fname(uintptr_t at,char* out,int cap,bool* ascii){
    uint32_t idn[2]; if(!sr(at,idn,8)) return -1;
    uintptr_t blk=np_block(idn[0]>>16); if(!blk) return -1;
    uintptr_t e=blk+(uintptr_t)(idn[0]&0xFFFF)*2; uint16_t hdr; if(!sr(e,&hdr,2)) return -1;
    int wide=hdr&1, len=hdr>>6, j=0; if(len<=0||len>1024) return -1;
    if(!wide){ uint8_t c[1024]; if(!sr(e+2,c,(size_t)len)) return -1;
        for(int i=0;i<len;i++){ if(j+3>cap) return -1;
            if(c[i]<0x80) out[j++]=(char)c[i];
            else { *ascii=false; out[j++]=(char)(0xC0|(c[i]>>6)); out[j++]=(char)(0x80|(c[i]&0x3F)); } } }
    else { uint16_t c[1024]; if(!sr(e+2,c,(size_t)len*2)) return -1;
        for(int i=0;i<len;i++){ uint32_t u=c[i]; if(j+5>cap) return -1;
            if(u>=0xD800&&u<0xDC00&&i+1<len&&c[i+1]>=0xDC00&&c[i+1]<0xE000){ u=0x10000+((u-0xD800)<<10)+(c[i+1]-0xDC00u); i++; }
            if(u<0x80){ out[j++]=(char)u; continue; }
            *ascii=false;
            if(u<0x800) out[j++]=(char)(0xC0|(u>>6));
            else if(u<0x10000){ out[j++]=(char)(0xE0|(u>>12)); out[j++]=(char)(0x80|((u>>6)&0x3F)); }
            else { out[j++]=(char)(0xF0|(u>>18)); out[j++]=(char)(0x80|((u>>12)&0x3F)); out[j++]=(char)(0x80|((u>>6)&0x3F)); }
            out[j++]=(char)(0x80|(u&0x3F)); } }
    if(idn[1]){ int k=snprintf(out+j,(size_t)(cap-j),"_%u",idn[1]-1); if(k<0||k>=cap-j) return -1; j+=k; }
    out[j]=0; return j; }
// the name at `at` -> its index in the name list; enum entries drop their "EEnum::" (readers add it back)
static int32_t um_idx(uintptr_t at,bool enumEntry=false){
    char s[1200]; bool ascii=true; int n=um_fname(at,s,sizeof s,&ascii);
    if(n<=0){ if(g_umFailName++<8) um_log("  name at 0x%lx unreadable",(unsigned long)at); return un_add(&g_umNames,"None"); }
    const char* p=s; if(enumEntry){ const char* c=strstr(s,"::"); if(c){ p=c+2; n=(int)strlen(p); } }
    uint32_t before=g_umNames.count; int32_t i=un_add(&g_umNames,p,n);
    if(!ascii && g_umNames.count>before && g_umNonAscii++<8) um_log("  non-ASCII name '%s' (UAssetAPI 1.1.0 reads usmap names as ASCII)",p);
    return i; }

// what kind of object a class makes: a class or struct, an enum, a function, or something else (cached per class)
static int um_kind(uintptr_t cls){
    if(!cls) return UMK_OTHER; uint8_t k=um_get(&g_umKinds,cls); if(k) return k;
    int kind=UMK_OTHER; uintptr_t c=cls;
    for(int d=0;c&&d<64;d++,c=rdptr(c+OFF_Super)){
        if(c==g_umFunction){ kind=UMK_FUNCTION; break; }   // before Struct: UFunction is a UStruct too
        if(c==g_umStruct){ kind=UMK_STRUCT; break; }
        if(c==g_umEnum){ kind=UMK_ENUM; break; } }
    um_set(&g_umKinds,cls,(uint8_t)kind); return kind; }
static int um_okind(uintptr_t o){ return (o&&in_range(o,0x30))? um_kind(rdptr(o+OFF_Class)) : 0; }

// FFieldClass name -> usmap kind. Only the ones the format has; the rest are written as Unknown and logged.
static const struct { const char* n; uint8_t t; } UM_TYPES[]={
    {"ByteProperty",UT_Byte},{"BoolProperty",UT_Bool},{"IntProperty",UT_Int},{"FloatProperty",UT_Float},
    {"ObjectProperty",UT_Object},{"ObjectPtrProperty",UT_Object},{"ClassProperty",UT_Object},{"ClassPtrProperty",UT_Object},
    {"NameProperty",UT_Name},{"DelegateProperty",UT_Delegate},{"DoubleProperty",UT_Double},{"ArrayProperty",UT_Array},
    {"StructProperty",UT_Struct},{"StrProperty",UT_Str},{"TextProperty",UT_Text},{"InterfaceProperty",UT_Interface},
    {"MulticastDelegateProperty",UT_MulticastDelegate},{"MulticastInlineDelegateProperty",UT_MulticastDelegate},
    {"MulticastSparseDelegateProperty",UT_MulticastDelegate},{"WeakObjectProperty",UT_WeakObject},
    {"LazyObjectProperty",UT_LazyObject},{"SoftObjectProperty",UT_SoftObject},{"SoftClassProperty",UT_SoftObject},
    {"UInt64Property",UT_UInt64},{"UInt32Property",UT_UInt32},{"UInt16Property",UT_UInt16},{"Int64Property",UT_Int64},
    {"Int16Property",UT_Int16},{"Int8Property",UT_Int8},{"MapProperty",UT_Map},{"SetProperty",UT_Set},
    {"EnumProperty",UT_Enum},{"FieldPathProperty",UT_FieldPath},{"OptionalProperty",UT_Optional},
    {"Utf8StrProperty",UT_Utf8Str},{"AnsiStrProperty",UT_AnsiStr},{"LargeWorldCoordinatesRealProperty",UT_Double} };
static uint8_t um_ftype(uintptr_t fc){                   // cached as type+1; 0xFE = Unknown
    uint8_t c=um_get(&g_umFTypes,fc); if(c) return c==0xFE? (uint8_t)UT_Unknown : (uint8_t)(c-1);
    char ty[96]; ty[0]=0; if(fc&&in_range(fc,8)) fname_resolve(rd32(fc),ty,sizeof ty);
    uint8_t t=UT_Unknown; for(const auto& m:UM_TYPES) if(!strcmp(ty,m.n)){ t=m.t; break; }
    if(t==UT_Unknown){ g_umUnknown++; um_log("  property kind '%s' (FFieldClass 0x%lx) isn't in the usmap format: written as Unknown",ty,(unsigned long)fc); }
    um_set(&g_umFTypes,fc,t==UT_Unknown?(uint8_t)0xFE:(uint8_t)(t+1)); return t; }
static UmMap g_umIsProp;                                 // FFieldClass candidate -> 1 no, 2 yes
static bool um_isprop(uintptr_t p){                      // an FProperty? (its FFieldClass's name ends in "Property")
    if(!p||!in_range(p,0x40)) return false; uintptr_t fc=rdptr(p+FF_Class); if(!fc||!in_range(fc,8)) return false;
    uint8_t c=um_get(&g_umIsProp,fc); if(c) return c==2;
    char ty[96]; int n=fname_resolve(rd32(fc),ty,sizeof ty); bool yes=n>8 && !strcmp(ty+n-8,"Property");
    um_set(&g_umIsProp,fc,yes?2:1); return yes; }

// one property's type, recursively (containers hold their inner properties)
static void um_type(UBuf* b,uintptr_t f,int depth){
    if(!f||depth>8||!in_range(f,(size_t)g_umS+16)){ ub_u8(b,UT_Unknown); g_umFailType++; return; }
    uint8_t t=um_ftype(rdptr(f+FF_Class)); uintptr_t a=rdptr(f+g_umS), z=rdptr(f+g_umS+8);
    switch(t){
    case UT_Byte:                                        // TEnumAsByte: EnumProperty over ByteProperty, like Dumper-7
        if(a&&um_okind(a)==UMK_ENUM){ ub_u8(b,UT_Enum); ub_u8(b,UT_Byte); ub_i32(b,um_idx(a+OFF_Name)); } else ub_u8(b,UT_Byte);
        break;
    case UT_Enum:                                        // no readable UEnum: the underlying integer alone still parses
        if(um_okind(z)==UMK_ENUM){ ub_u8(b,UT_Enum); um_type(b,a,depth+1); ub_i32(b,um_idx(z+OFF_Name)); }
        else { g_umFailType++; um_type(b,a,depth+1); }
        break;
    case UT_Struct:
        ub_u8(b,UT_Struct);
        if(um_okind(a)==UMK_STRUCT) ub_i32(b,um_idx(a+OFF_Name)); else { g_umFailType++; ub_i32(b,un_add(&g_umNames,"None")); }
        break;
    case UT_Array:    ub_u8(b,UT_Array);    um_type(b,rdptr(f+g_umArr),depth+1); break;
    case UT_Optional: ub_u8(b,UT_Optional); um_type(b,rdptr(f+g_umOpt),depth+1); break;
    case UT_Set:      ub_u8(b,UT_Set);      um_type(b,a,depth+1); break;
    case UT_Map:      ub_u8(b,UT_Map);      um_type(b,a,depth+1); um_type(b,z,depth+1); break;
    default:          ub_u8(b,t);
    } }
// one class or struct: name, super, then its own properties (supers are written first)
static void um_struct(UBuf* b,uintptr_t s,int depth){
    if(um_get(&g_umDone,s)) return; um_set(&g_umDone,s,1);
    uintptr_t sup=rdptr(s+OFF_Super); bool supOk=sup&&um_okind(sup)==UMK_STRUCT;
    if(supOk&&depth<64) um_struct(b,sup,depth+1);
    static uintptr_t fs[4096]; static uint32_t dims[4096]; uint32_t n=0, slots=0;   // filled after the recursion above
    for(uintptr_t f=rdptr(s+OFF_ChildProps); f&&n<4096; f=rdptr(f+FF_Next)){
        if(!in_range(f,(size_t)g_umS+16)){ g_umFailType++; break; }
        uint32_t d=rd32(f+UM_ArrayDim); if(d<1||d>0xFFFF){ g_umFailDim++; d=1; }
        fs[n]=f; dims[n]=d; n++; slots+=d; }
    if(slots>0xFFFF){ g_umFailDim++; slots=0xFFFF; }
    ub_i32(b,um_idx(s+OFF_Name)); ub_i32(b,supOk?um_idx(sup+OFF_Name):-1); ub_u16(b,(uint16_t)slots); ub_u16(b,(uint16_t)n);
    uint32_t slot=0;
    for(uint32_t i=0;i<n;i++){                           // a dim over 255 loses its tail elements only; slots stay right
        if(dims[i]>255) g_umFailDim++;
        ub_u16(b,(uint16_t)slot); ub_u8(b,(uint8_t)(dims[i]>255?255:dims[i])); ub_i32(b,um_idx(fs[i]+FF_Name)); um_type(b,fs[i],0);
        slot+=dims[i]; }
    g_umProps+=n; g_umStructsOut++; }
static void um_enum(UBuf* b,uintptr_t e){
    uintptr_t data=rdptr(e+UM_EnumNames); int32_t n=(int32_t)rd32(e+UM_EnumNames+8);
    if(n<0||n>0xFFFF||(n&&!data)){
        if(g_umFailEnum++<8) um_log("  enum 0x%lx: Names looks wrong (data 0x%lx, n %d): written empty",(unsigned long)e,(unsigned long)data,n);
        n=0; }
    ub_i32(b,um_idx(e+OFF_Name)); ub_u16(b,(uint16_t)n);
    for(int32_t i=0;i<n;i++){ uintptr_t p=data+(uintptr_t)i*16; int64_t v=0; if(!sr(p+8,&v,8)) g_umFailEnum++;
        ub_i64(b,v); ub_i32(b,um_idx(p,true)); }
    g_umEnumsOut++; }

// Does this build's FProperty layout match what the writer reads? Sampled over up to 200k properties. Each pointer must
// be what its property kind says (an FProperty, a UScriptStruct, a UEnum); ArrayProperty and OptionalProperty vote
// between S and S+8 (the inner pointer may follow a flags field).
static bool um_rate(const char* what,uint32_t n,uint32_t good,uint32_t off){ bool ok=!n||(uint64_t)good*100>=(uint64_t)n*98;
    um_log("  %-30s @0x%02x: %6u of %6u%s",what,off,good,n,ok?"":"  <- FAIL"); return ok; }
static bool um_check(const uintptr_t* st,uint32_t ns){
    uint32_t dimN=0,dimOk=0,dimOne=0, esN=0,esOk=0, arrN=0,arrA=0,arrB=0, optN=0,optA=0,optB=0, mapN=0,mapOk=0, setN=0,setOk=0,
             enN=0,enOk=0, spN=0,spOk=0, byN=0,byOk=0, seen=0;
    for(uint32_t i=0;i<ns&&seen<200000;i++){ uint32_t k=0;
        for(uintptr_t f=rdptr(st[i]+OFF_ChildProps); f&&k<4096&&in_range(f,(size_t)g_umS+16); f=rdptr(f+FF_Next),k++,seen++){
            uint32_t d=rd32(f+UM_ArrayDim); dimN++; if(d>=1&&d<=255) dimOk++; if(d==1) dimOne++;
            uintptr_t a=rdptr(f+g_umS), z=rdptr(f+g_umS+8);
            uint8_t t=um_ftype(rdptr(f+FF_Class));
            // ElementSize (right after ArrayDim) for kinds whose size is fixed: proves the neighbourhood, not just a range
            uint32_t want= (t==UT_Int||t==UT_Float)?4 : (t==UT_Double||t==UT_Name||t==UT_Object)?8 : (t==UT_Str||t==UT_Array)?16 : 0;
            if(want){ esN++; if(rd32(f+UM_ArrayDim+4)==want) esOk++; }
            switch(t){
            case UT_Array:    arrN++; if(um_isprop(a)) arrA++; if(um_isprop(z)) arrB++; break;
            case UT_Optional: optN++; if(um_isprop(a)) optA++; if(um_isprop(z)) optB++; break;
            case UT_Map:      mapN++; if(um_isprop(a)&&um_isprop(z)) mapOk++; break;
            case UT_Set:      setN++; if(um_isprop(a)) setOk++; break;
            case UT_Enum:     enN++;  if(um_isprop(a)&&um_okind(z)==UMK_ENUM) enOk++; break;
            case UT_Struct:   spN++;  if(um_okind(a)==UMK_STRUCT) spOk++; break;
            case UT_Byte:     byN++;  if(!a||um_okind(a)==UMK_ENUM) byOk++; break;
            default: break; } } }
    g_umArr=arrB>arrA?g_umS+8:g_umS; g_umOpt=optB>optA?g_umS+8:g_umS;
    um_log("layout check over %u properties (sizeof(FProperty) 0x%x):",seen,g_umS);
    bool ok=true;
    ok&=um_rate("ArrayDim 1..255",dimN,dimOk,UM_ArrayDim);
    bool ones=!dimN||(uint64_t)dimOne*100>=(uint64_t)dimN*90;     // static arrays are rare: ArrayDim is almost always 1
    um_log("  %-30s @0x%02x: %6u of %6u%s","ArrayDim == 1 (want >= 90%)",UM_ArrayDim,dimOne,dimN,ones?"":"  <- FAIL"); ok&=ones;
    ok&=um_rate("ElementSize of Int/Float/Double..",esN,esOk,UM_ArrayDim+4);
    ok&=um_rate("ArrayProperty inner",arrN,g_umArr==g_umS?arrA:arrB,(uint32_t)g_umArr);
    ok&=um_rate("OptionalProperty value",optN,g_umOpt==g_umS?optA:optB,(uint32_t)g_umOpt);
    ok&=um_rate("MapProperty key+value",mapN,mapOk,(uint32_t)g_umS);
    ok&=um_rate("SetProperty element",setN,setOk,(uint32_t)g_umS);
    ok&=um_rate("EnumProperty underlying+UEnum",enN,enOk,(uint32_t)g_umS);
    ok&=um_rate("StructProperty UScriptStruct",spN,spOk,(uint32_t)g_umS);
    ok&=um_rate("ByteProperty UEnum or none",byN,byOk,(uint32_t)g_umS);
    if(spN<100||arrN<100||byN<100){ um_log("  too few properties seen to trust the layout"); ok=false; }
    return ok; }

// usmap_now may be created before launch: wait for the engine objects, then for Tribe's deck class (the Blueprint
// classes in use are loaded by then), or 120 s. Poll thread, every ~2 s while the file exists.
static bool usmap_ready(){
    static int waits=0; static bool saidEngine=false;
    ensure_resolved();
    if(!g_resolved){ if(!saidEngine){ LOGI("[USMAP] usmap_now: waiting for the engine objects"); saidEngine=true; } return false; }
    refresh_numelements();
    if(find_by_path("/Game/Equipment/Deck/BP_Deck.BP_Deck_C",1)) return true;
    if(++waits>=60){ LOGI("[USMAP] usmap_now: no deck class after 120 s; dumping anyway"); return true; }
    if(waits==1) LOGI("[USMAP] usmap_now: waiting for Tribe's decks to load");
    return false; }

static void usmap_dump(){
    char lp[600]; snprintf(lp,sizeof lp,"%s/usmap_log.txt",OUTDIR); g_umLog=fopen(lp,"w");
    struct timespec t0,t1; clock_gettime(CLOCK_MONOTONIC,&t0);
    g_umFailName=g_umFailType=g_umFailEnum=g_umFailDim=g_umNonAscii=g_umUnknown=g_umProps=g_umStructsOut=g_umEnumsOut=0;
    uintptr_t *st=0, *en=0; uint32_t ns=0, ne=0, nfn=0; UBuf be={}, bs={}; bool ok=false;
    char up[600]; snprintf(up,sizeof up,"%s/TribeXR.usmap",OUTDIR);
    um_log("usmap dump (hook/usmap.cpp, format version %d)",USMAP_VERSION);
    do {
        ensure_resolved();
        if(!g_resolved){ um_log("FAIL: engine objects not resolved yet: wait for Tribe's menu (headset on), then create usmap_now again"); break; }
        load_maps(); refresh_numelements();
        g_umStruct=find_by_path("/Script/CoreUObject.Struct",1); g_umFunction=find_by_path("/Script/CoreUObject.Function",1);
        g_umEnum=find_by_path("/Script/CoreUObject.Enum",1); g_umS=calib_fprop_size();
        um_log("objects %u; Struct 0x%lx, Function 0x%lx, Enum 0x%lx; sizeof(FProperty) 0x%x; UStruct Super@0x%x ChildProperties@0x%x",
            g_numElements,(unsigned long)g_umStruct,(unsigned long)g_umFunction,(unsigned long)g_umEnum,g_umS,OFF_Super,OFF_ChildProps);
        if(!g_umStruct||!g_umFunction||!g_umEnum||g_umS<0x48||g_umS>0xB0){ um_log("FAIL: core classes or sizeof(FProperty) not found"); break; }
        st=(uintptr_t*)malloc((size_t)g_numElements*sizeof *st); en=(uintptr_t*)malloc((size_t)g_numElements*sizeof *en);
        if(!st||!en){ um_log("FAIL: out of memory"); break; }
        for(uint32_t i=0;i<g_numElements;i++){ uintptr_t o=obj_at(i);
            switch(um_okind(o)){ case UMK_STRUCT: st[ns++]=o; break; case UMK_ENUM: en[ne++]=o; break; case UMK_FUNCTION: nfn++; break; default: break; } }
        um_log("found %u classes and structs, %u enums (%u functions skipped)",ns,ne,nfn);
        if(!um_check(st,ns)){ um_log("FAIL: this build's property layout isn't what usmap.cpp reads; nothing written"); break; }
        for(uint32_t i=0;i<ne;i++) um_enum(&be,en[i]);
        for(uint32_t i=0;i<ns;i++) um_struct(&bs,st[i],0);
        if(be.oom||bs.oom||g_umNames.oom||g_umDone.oom||g_umKinds.oom||g_umFTypes.oom){ um_log("FAIL: out of memory while writing"); break; }
        if(!usmap_save(up,&g_umNames,g_umEnumsOut,&be,g_umStructsOut,&bs)){ um_log("FAIL: couldn't write %s (errno %d)",up,errno); break; }
        chmod(up,0666); struct stat sb; long long sz=stat(up,&sb)==0?(long long)sb.st_size:-1;
        clock_gettime(CLOCK_MONOTONIC,&t1);
        um_log("WROTE %s: %u names, %u enums, %u classes and structs, %u properties, %lld bytes, %.1f s",up,g_umNames.count,
            g_umEnumsOut,g_umStructsOut,g_umProps,sz,(double)(t1.tv_sec-t0.tv_sec)+(t1.tv_nsec-t0.tv_nsec)/1e9);
        ok=true;
    } while(0);
    um_log("problems: unreadable names %u, unresolved types %u, unknown property kinds %u, enum reads %u, array dims %u; non-ASCII names %u",
        g_umFailName,g_umFailType,g_umUnknown,g_umFailEnum,g_umFailDim,g_umNonAscii);
    um_log("%s",ok?"DONE":"NOT WRITTEN");
    free(st); free(en); ub_free(&be); ub_free(&bs); un_free(&g_umNames); um_free(&g_umKinds); um_free(&g_umFTypes); um_free(&g_umDone); um_free(&g_umIsProp);
    if(g_umLog){ fclose(g_umLog); g_umLog=0; chmod(lp,0666); } }
