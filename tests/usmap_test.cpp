// usmap_test.cpp: writes a made-up schema through hook/usmap_writer.h (the same writer libhook uses for TribeXR.usmap)
// and prints what a reader should get back, in scripts/uasset_tool's "usmap" format. Equal output = UAssetAPI reads the
// writer's bytes the way they were meant: every property kind, nested containers, a static array, a super chain,
// explicit enum values, an enum past 255 entries and a non-ASCII name. Names are written as UTF-8 (CUE4Parse reads
// UTF-8); UAssetAPI 1.1.0 reads usmap names as ASCII, so it shows "Größe" as "Gr????e" (one ? per byte), and the
// expected text below says so. The UTF-8 bytes themselves are checked here, in the file.
//   build:  MSVC: cl /O2 /EHsc /utf-8 /D_CRT_SECURE_NO_WARNINGS tests\usmap_test.cpp   (or the NDK clang++, -nostdlib++)
//   run:    usmap_test <out.usmap> > expected.txt
//           dotnet run --project scripts/uasset_tool -- usmap <out.usmap> ETestEnum EBigEnum TestBase TestStruct > got.txt
//           diff expected.txt got.txt
#include "../hook/usmap_writer.h"

static UNames N;
static void ty_enum(UBuf* b,uint8_t inner,const char* e){ ub_u8(b,UT_Enum); ub_u8(b,inner); ub_i32(b,un_add(&N,e)); }
static void ty_struct(UBuf* b,const char* s){ ub_u8(b,UT_Struct); ub_i32(b,un_add(&N,s)); }
static void prop(UBuf* b,uint16_t slot,uint8_t dim,const char* name){ ub_u16(b,slot); ub_u8(b,dim); ub_i32(b,un_add(&N,name)); }

int main(int argc,char** argv){
    if(argc<2){ fprintf(stderr,"usage: usmap_test <out.usmap>\n"); return 2; }
    UBuf en={}, st={};
    // ETestEnum: explicit, non-contiguous values; EBigEnum: 300 entries (needs the u16 count)
    ub_i32(&en,un_add(&N,"ETestEnum")); ub_u16(&en,4);
    const char* tn[4]={"A","B","C","ETestEnum_MAX"}; const int64_t tv[4]={0,1,5,6};
    for(int i=0;i<4;i++){ ub_i64(&en,tv[i]); ub_i32(&en,un_add(&N,tn[i])); }
    ub_i32(&en,un_add(&N,"EBigEnum")); ub_u16(&en,300);
    for(int i=0;i<300;i++){ char v[16]; snprintf(v,sizeof v,"V%d",i); ub_i64(&en,i); ub_i32(&en,un_add(&N,v)); }
    // TestBase: one property, no super
    ub_i32(&st,un_add(&N,"TestBase")); ub_i32(&st,-1); ub_u16(&st,1); ub_u16(&st,1);
    prop(&st,0,1,"Base0"); ub_u8(&st,UT_Int);
    // TestStruct : TestBase -- 15 properties, 17 slots (Fixed is int32 Fixed[3])
    ub_i32(&st,un_add(&N,"TestStruct")); ub_i32(&st,un_add(&N,"TestBase")); ub_u16(&st,17); ub_u16(&st,15);
    prop(&st,0,1,"X");      ub_u8(&st,UT_Float);
    prop(&st,1,1,"Y");      ub_u8(&st,UT_Double);
    prop(&st,2,1,"Arr");    ub_u8(&st,UT_Array); ub_u8(&st,UT_Int);
    prop(&st,3,1,"M");      ub_u8(&st,UT_Map); ub_u8(&st,UT_Name); ty_struct(&st,"TestBase");
    prop(&st,4,1,"E");      ty_enum(&st,UT_Byte,"ETestEnum");
    prop(&st,5,1,"S");      ub_u8(&st,UT_Set); ub_u8(&st,UT_Str);
    prop(&st,6,1,"O");      ub_u8(&st,UT_Optional); ub_u8(&st,UT_Int);
    prop(&st,7,3,"Fixed");  ub_u8(&st,UT_Int);
    prop(&st,10,1,"Big");   ty_enum(&st,UT_Int,"EBigEnum");
    prop(&st,11,1,"ArrS");  ub_u8(&st,UT_Array); ty_struct(&st,"TestStruct");
    prop(&st,12,1,"Obj");   ub_u8(&st,UT_Object);
    prop(&st,13,1,"Txt");   ub_u8(&st,UT_Text);
    prop(&st,14,1,"B");     ub_u8(&st,UT_Bool);
    prop(&st,15,1,"Soft");  ub_u8(&st,UT_SoftObject);
    prop(&st,16,1,"Gr\xC3\xB6\xC3\x9F" "e"); ub_u8(&st,UT_UInt16);        // "Größe": UTF-8 must survive
    if(!usmap_save(argv[1],&N,2,&en,2,&st)){ fprintf(stderr,"usmap_save failed\n"); return 1; }
    {   // the name list holds "Größe" as {u16 7, UTF-8}
        FILE* f=fopen(argv[1],"rb"); static uint8_t buf[1<<16]; size_t n=f?fread(buf,1,sizeof buf,f):0; if(f) fclose(f);
        const uint8_t want[9]={7,0,'G','r',0xC3,0xB6,0xC3,0x9F,'e'}; bool found=false;
        for(size_t i=0;i+9<=n && !found;i++) found=!memcmp(buf+i,want,9);
        if(!found){ fprintf(stderr,"UTF-8 name bytes not found in %s\n",argv[1]); return 1; } }

    printf("version=ExplicitEnumValues names=%u enums=2 schemas=2\n",N.count);
    printf("enum ETestEnum: 0=A 1=B 5=C 6=ETestEnum_MAX\n");
    printf("enum EBigEnum:"); for(int i=0;i<300;i++) printf(" %d=V%d",i,i); printf("\n");
    printf("struct TestBase : - slots=1\n  0 Base0[0/1] Int\n");
    printf("struct TestStruct : TestBase slots=17\n");
    printf("  0 X[0/1] Float\n  1 Y[0/1] Double\n  2 Arr[0/1] Array<Int>\n  3 M[0/1] Map<Name,Struct(TestBase)>\n");
    printf("  4 E[0/1] Enum(Byte,ETestEnum)\n  5 S[0/1] Set<Str>\n  6 O[0/1] Optional<Int>\n");
    printf("  7 Fixed[0/3] Int\n  8 Fixed[1/3] Int\n  9 Fixed[2/3] Int\n");
    printf("  10 Big[0/1] Enum(Int,EBigEnum)\n  11 ArrS[0/1] Array<Struct(TestStruct)>\n  12 Obj[0/1] Object\n");
    printf("  13 Txt[0/1] Text\n  14 B[0/1] Bool\n  15 Soft[0/1] SoftObject\n  16 Gr????e[0/1] UInt16\n");   // UAssetAPI: ASCII
    un_free(&N); ub_free(&en); ub_free(&st);
    return 0;
}
