// ---- the native dump (one-shot: create tribemod/native_now; writes tribemod/native_dump.jsonl + native_log.txt) ----
// For reading Tribe's C++ in Ghidra: every class in Tribe's own modules (/Script/TribeXR, /Script/TribeIntonal,
// /Script/SuperPowered, or the comma-separated packages written into native_now) as one JSON line: its parent, size,
// every UFunction with its flags, native entry (UFunction::Func: the exec thunk, or the script VM for Blueprint events)
// and parameters, and its class default object's vtable (comparing a class's vtable with its parent's gives its C++
// overrides). Addresses are RVAs from libUnreal.so's lowest mapping; Ghidra address = RVA + 0x100000, as do_dump
// prints. Poll thread only, under install_guard(); uses usmap.cpp's readers and layout check.

static const uint32_t ND_FuncFlags=0xB0, ND_Func=0xD8;  // UFunction::FunctionFlags, ::Func (dump_ufunction pinned both)
static const uint32_t UM_UFieldNext=0x28;                // UField::Next: the Children chain (UFunctions of a class)
static Range g_ndText[16]; static int g_ndNText=0;       // libUnreal.so's executable mappings
static uintptr_t* g_ndCdoc=nullptr;                     // the class of each class default object (scan scratch)

static void nd_text_ranges(){
    g_ndNText=0; FILE* f=fopen("/proc/self/maps","r"); if(!f) return; char line[1024];
    while(fgets(line,sizeof line,f) && g_ndNText<16){ uintptr_t lo,hi; char perm[8];
        if(strstr(line,"libUnreal.so") && sscanf(line,"%lx-%lx %4s",&lo,&hi,perm)==3 && perm[2]=='x') g_ndText[g_ndNText++]=(Range){lo,hi}; }
    fclose(f); }
static bool nd_is_code(uintptr_t p){ for(int i=0;i<g_ndNText;i++) if(p>=g_ndText[i].lo&&p<g_ndText[i].hi) return true; return false; }

// JSON string (names are identifiers, but may hold spaces; escape the rest anyway)
static void nd_str(FILE* fo,const char* s){ fputc('"',fo);
    for(;*s;s++){ unsigned char c=(unsigned char)*s; if(c=='"'||c=='\\') { fputc('\\',fo); fputc(c,fo); } else if(c<0x20) fprintf(fo,"\\u%04x",c); else fputc(c,fo); }
    fputc('"',fo); }
static int nd_name(uintptr_t o,char* out,int cap){ bool a=true; int n=o?um_fname(o+OFF_Name,out,cap,&a):-1; if(n<0){ snprintf(out,cap,"?"); n=1; } return n; }
static void nd_path(uintptr_t o,char* out,int cap){         // /Script/TribeXR.TribeEquipmentBase
    char parts[6][256]; int np=0; for(uintptr_t x=o; x&&np<6; x=rdptr(x+OFF_Outer)) nd_name(x,parts[np++],256);
    int j=0; out[0]=0; for(int i=np-1;i>=0&&j<cap-1;i--) j+=snprintf(out+j,cap-j,"%s%s",i==np-1?"":(i==np-2?".":":"),parts[i]); }

// a property's type, readably: Array<Struct(Vector)>, Object(Actor), Enum(EDeckState), Delegate(OnFoo__DelegateSignature)
static int nd_type(uintptr_t f,char* out,int cap,int depth){
    char ty[96]; ty[0]=0; ffield_type(f,ty,sizeof ty); int n=(int)strlen(ty);
    if(n>8&&!strcmp(ty+n-8,"Property")) ty[n-8]=0;
    char a[256], b[256]; uintptr_t p0=rdptr(f+g_umS), p8=rdptr(f+g_umS+8);
    if(depth>6) return snprintf(out,cap,"%s",ty);
    if(!strcmp(ty,"Struct")){ nd_name(p0,a,sizeof a); return snprintf(out,cap,"Struct(%s)",a); }
    if(!strcmp(ty,"Array")){ nd_type(rdptr(f+g_umArr),a,sizeof a,depth+1); return snprintf(out,cap,"Array<%s>",a); }
    if(!strcmp(ty,"Set")){ nd_type(p0,a,sizeof a,depth+1); return snprintf(out,cap,"Set<%s>",a); }
    if(!strcmp(ty,"Map")){ nd_type(p0,a,sizeof a,depth+1); nd_type(p8,b,sizeof b,depth+1); return snprintf(out,cap,"Map<%s,%s>",a,b); }
    if(!strcmp(ty,"Enum")){ nd_name(p8,a,sizeof a); return snprintf(out,cap,"Enum(%s)",a); }
    if(!strcmp(ty,"Byte")&&p0&&um_okind(p0)==UMK_ENUM){ nd_name(p0,a,sizeof a); return snprintf(out,cap,"Enum(%s)",a); }
    if(!strcmp(ty,"Class")||!strcmp(ty,"SoftClass")){ nd_name(p8,a,sizeof a); return snprintf(out,cap,"%s(%s)",ty,a); }
    if(strstr(ty,"Object")||!strcmp(ty,"Interface")){ nd_name(p0,a,sizeof a); return snprintf(out,cap,"%s(%s)",ty,a); }
    if(strstr(ty,"Delegate")){ nd_name(p0,a,sizeof a); return snprintf(out,cap,"%s(%s)",ty,a); }
    return snprintf(out,cap,"%s",ty); }

static bool nd_want(const char* pkg,char lists[][64],int nl){ for(int i=0;i<nl;i++) if(!strcmp(pkg,lists[i])) return true; return false; }

static void native_dump(){
    char lp[600]; snprintf(lp,sizeof lp,"%s/native_log.txt",OUTDIR); g_umLog=fopen(lp,"w");
    char np_[600]; snprintf(np_,sizeof np_,"%s/native_now",OUTDIR);
    static char pk[16][64]; int npk=0;                       // packages: native_now's text, or Tribe's three modules
    { FILE* f=fopen(np_,"r"); char buf[512]={0}; if(f){ size_t r=fread(buf,1,sizeof buf-1,f); buf[r]=0; fclose(f); }
      for(char* t=strtok(buf,", \r\n\t"); t&&npk<16; t=strtok(nullptr,", \r\n\t")) snprintf(pk[npk++],64,"%s",t); }
    if(!npk){ snprintf(pk[0],64,"/Script/TribeXR"); snprintf(pk[1],64,"/Script/TribeIntonal"); snprintf(pk[2],64,"/Script/SuperPowered"); npk=3; }
    unlink(np_);
    char op[600]; snprintf(op,sizeof op,"%s/native_dump.jsonl",OUTDIR); char tmp[640]; snprintf(tmp,sizeof tmp,"%s.tmp",op);
    FILE* fo=nullptr; uint32_t nclass=0, nfunc=0, nnative=0, nvt=0; uintptr_t* cdos=nullptr; uintptr_t* cls=nullptr;
    do {
        ensure_resolved(); if(!g_resolved){ um_log("FAIL: engine objects not resolved yet"); break; }
        load_maps(); refresh_numelements(); nd_text_ranges();
        g_umStruct=find_by_path("/Script/CoreUObject.Struct",1); g_umFunction=find_by_path("/Script/CoreUObject.Function",1);
        g_umEnum=find_by_path("/Script/CoreUObject.Enum",1); g_umS=calib_fprop_size();
        uintptr_t ucls=find_by_path("/Script/CoreUObject.Class",1);
        um_log("native dump: %d packages, base 0x%lx, %d code ranges, sizeof(FProperty) 0x%x",npk,(unsigned long)g_base,g_ndNText,g_umS);
        if(!g_umStruct||!g_umFunction||!g_umEnum||!ucls||g_umS<0x48||!g_ndNText){ um_log("FAIL: core classes, FProperty size or code ranges not found"); break; }
        cls=(uintptr_t*)malloc((size_t)g_numElements*8); cdos=(uintptr_t*)malloc((size_t)g_numElements*8); uint32_t ns=0,nc=0;
        uintptr_t* st=(uintptr_t*)malloc((size_t)g_numElements*8); uint32_t nst=0;
        if(!cls||!cdos||!st){ free(st); um_log("FAIL: out of memory"); break; }
        char nm[512], pkg[512];
        uintptr_t* cdoc=g_ndCdoc=(uintptr_t*)malloc((size_t)g_numElements*8);   // class of each class default object
        if(!cdoc){ free(st); um_log("FAIL: out of memory"); break; }
        for(uint32_t i=0;i<g_numElements;i++){ uintptr_t o=obj_at(i); if(!o) continue; int k=um_okind(o);
            if(k==UMK_STRUCT) st[nst++]=o;                   // every struct, for the layout check
            if(rd32(o+OFF_Flags)&RF_ClassDefaultObject){ cdoc[nc]=rdptr(o+OFF_Class); cdos[nc++]=o; continue; }
            uintptr_t outer=rdptr(o+OFF_Outer); if(!outer||rdptr(outer+OFF_Outer)) continue;   // outer must be the package
            if(rdptr(o+OFF_Class)!=ucls) continue;
            nd_name(outer,pkg,sizeof pkg); if(nd_want(pkg,pk,npk)) cls[ns++]=o; }
        // the first ancestor outside the packages (Actor, ActorComponent ...): its vtable shows what each class overrides
        uint32_t ntarget=ns;
        for(uint32_t ci=0;ci<ntarget;ci++){ uintptr_t sup=rdptr(cls[ci]+OFF_Super); bool in=false;
            for(uint32_t j=0;j<ns&&!in;j++) in=(cls[j]==sup);
            if(sup&&!in) cls[ns++]=sup; }
        bool layout=um_check(st,nst); free(st);
        if(!layout){ um_log("FAIL: property layout check failed"); break; }
        fo=fopen(tmp,"w"); if(!fo){ um_log("FAIL: can't write %s",tmp); break; }
        char path[768], a[512], tyb[512];
        for(uint32_t ci=0;ci<ns;ci++){ uintptr_t c=cls[ci];
            nd_path(c,path,sizeof path); nd_name(c,nm,sizeof nm);
            fputs("{\"class\":",fo); nd_str(fo,path);
            uintptr_t sup=rdptr(c+OFF_Super); nd_path(sup,a,sizeof a); fputs(",\"super\":",fo); nd_str(fo,sup?a:"");
            fprintf(fo,",\"size\":%u",rd32(c+OFF_PropSize));
            uintptr_t cdo=0; for(uint32_t j=0;j<nc&&!cdo;j++) if(cdoc[j]==c) cdo=cdos[j];
            if(ci>=ntarget) fputs(",\"context\":true",fo);    // an engine parent: vtable only
            fputs(",\"vtable\":[",fo);
            uintptr_t vt=cdo?rdptr(cdo):0; int nv=0;
            for(; vt&&nv<1024; nv++){ uintptr_t e=rdptr(vt+(uintptr_t)nv*8); if(!nd_is_code(e)) break; fprintf(fo,"%s\"0x%lx\"",nv?",":"",(unsigned long)(e-g_base)); }
            fprintf(fo,"],\"vtable_rva\":\"0x%lx\"",(unsigned long)(vt?vt-g_base:0)); if(nv) nvt++;
            fputs(",\"functions\":[",fo); int nf=0;
            for(uintptr_t fn=ci<ntarget?rdptr(c+OFF_Children):0; fn&&nf<2048; fn=rdptr(fn+UM_UFieldNext)){
                if(um_okind(fn)!=UMK_FUNCTION) continue;
                uint32_t ff=rd32(fn+ND_FuncFlags); uintptr_t fp=rdptr(fn+ND_Func); nd_name(fn,a,sizeof a);
                fprintf(fo,"%s{\"name\":",nf?",":""); nd_str(fo,a);
                fprintf(fo,",\"flags\":\"0x%08x\",\"func\":\"0x%lx\",\"params\":[",ff,(unsigned long)(fp&&nd_is_code(fp)?fp-g_base:0));
                int pn=0;
                for(uintptr_t f=rdptr(fn+OFF_ChildProps); f&&pn<64; f=rdptr(f+FF_Next),pn++){
                    char pnm[256]; bool asc=true; if(um_fname(f+FF_Name,pnm,sizeof pnm,&asc)<0) snprintf(pnm,sizeof pnm,"?");
                    nd_type(f,tyb,sizeof tyb,0); uint64_t pf=0; sr(f+0x38,&pf,8);
                    fprintf(fo,"%s[",pn?",":""); nd_str(fo,pnm); fputc(',',fo); nd_str(fo,tyb); fprintf(fo,",\"0x%llx\"]",(unsigned long long)pf); }
                fputs("]}",fo); nf++; nfunc++; if(ff&0x400) nnative++; }
            fputs("]}\n",fo); nclass++; }
        if(fclose(fo)!=0){ fo=nullptr; um_log("FAIL: write error"); break; } fo=nullptr;
        remove(op); if(rename(tmp,op)!=0){ um_log("FAIL: rename (errno %d)",errno); break; } chmod(op,0666);
        um_log("WROTE %s: %u classes (%u of them engine parents, vtable only), %u functions (%u native), %u vtables",op,nclass,nclass-ntarget,nfunc,nnative,nvt);
        um_log("DONE");
    } while(0);
    if(fo){ fclose(fo); remove(tmp); }
    free(cls); free(cdos); free(g_ndCdoc); g_ndCdoc=nullptr; um_free(&g_umKinds); um_free(&g_umFTypes); um_free(&g_umIsProp);
    if(g_umLog){ fclose(g_umLog); g_umLog=0; chmod(lp,0666); } }
