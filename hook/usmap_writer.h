// usmap_writer.h -- the .usmap file format, with no Unreal reads: hook/usmap.cpp feeds it from the running game,
// tests/usmap_test.cpp feeds it a made-up schema. C-style on purpose: libhook links no C++ library (-nostdlib++).
//
// The format as CUE4Parse (UsmapParser.cs) and UAssetAPI (Usmap.cs) read it and Dumper-7 (MappingGenerator.cpp)
// writes it; all three checked 2026-10-26. Little-endian.
//   header:  u16 magic 0x30C4 | u8 version | i32 hasVersioning (0) | u8 compression (0 = none) | u32 size | u32 size
//   payload: u32 nNames   { u16 len, len bytes of UTF-8 }
//            u32 nEnums   { i32 name, u16 n, { i64 value, i32 name } }          (the explicit values: version >= 4)
//            u32 nStructs { i32 name, i32 super (-1 = none), u16 nSlots, u16 nProps,
//                           { u16 slot, u8 arrayDim, i32 name, type } }         slot = the sum of the earlier arrayDims
//   type:    u8 kind, then  EnumProperty: type (the underlying integer) + i32 enum | StructProperty: i32 struct
//                           ArrayProperty, SetProperty, OptionalProperty: type   | MapProperty: key type + value type
// Every name is an index into the name list. Enum entries are bare ("Value", not "EEnum::Value"): CUE4Parse adds the
// "EEnum::" itself. A ByteProperty with an enum is written as EnumProperty over ByteProperty, as Dumper-7 does.
#pragma once
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>

enum : uint8_t { UT_Byte=0, UT_Bool, UT_Int, UT_Float, UT_Object, UT_Name, UT_Delegate, UT_Double, UT_Array, UT_Struct,
    UT_Str, UT_Text, UT_Interface, UT_MulticastDelegate, UT_WeakObject, UT_LazyObject, UT_AssetObject, UT_SoftObject,
    UT_UInt64, UT_UInt32, UT_UInt16, UT_Int64, UT_Int16, UT_Int8, UT_Map, UT_Set, UT_Enum, UT_FieldPath, UT_Optional,
    UT_Utf8Str, UT_AnsiStr, UT_Unknown=0xFF };
static const uint8_t USMAP_VERSION=4;                        // ExplicitEnumValues

// growable byte buffer; oom sticks, so a failed write can't silently drop bytes from the middle of the stream
struct UBuf { uint8_t* p; size_t n, cap; bool oom; };
static void ub_put(UBuf* b,const void* d,size_t len){ if(b->oom||!len) return;
    if(b->n+len>b->cap){ size_t c=b->cap?b->cap:65536; while(c<b->n+len) c*=2; uint8_t* q=(uint8_t*)realloc(b->p,c);
        if(!q){ b->oom=true; return; } b->p=q; b->cap=c; }
    memcpy(b->p+b->n,d,len); b->n+=len; }
static void ub_u8 (UBuf* b,uint8_t v){ ub_put(b,&v,1); }
static void ub_u16(UBuf* b,uint16_t v){ ub_put(b,&v,2); }
static void ub_u32(UBuf* b,uint32_t v){ ub_put(b,&v,4); }
static void ub_i32(UBuf* b,int32_t v){ ub_put(b,&v,4); }
static void ub_i64(UBuf* b,int64_t v){ ub_put(b,&v,8); }
static void ub_free(UBuf* b){ free(b->p); memset(b,0,sizeof *b); }

// the name list: unique UTF-8 strings -> their index, kept in file form ({u16 len, bytes}) as they arrive
struct UNames { UBuf table; uint32_t count, nslots, offcap; uint32_t* offs; uint32_t* slots; bool oom; };
static uint32_t un_hash(const char* s,int len){ uint32_t h=2166136261u; for(int i=0;i<len;i++){ h^=(uint8_t)s[i]; h*=16777619u; } return h; }
static bool un_grow(UNames* t){ uint32_t ns=t->nslots?t->nslots*2:(1u<<16); uint32_t* sl=(uint32_t*)calloc(ns,4); if(!sl) return false;
    for(uint32_t i=0;i<t->count;i++){ const uint8_t* e=t->table.p+t->offs[i]; uint16_t l; memcpy(&l,e,2);
        uint32_t h=un_hash((const char*)e+2,l)&(ns-1); while(sl[h]) h=(h+1)&(ns-1); sl[h]=i+1; }
    free(t->slots); t->slots=sl; t->nslots=ns; return true; }
static int32_t un_add(UNames* t,const char* s,int len){
    if(t->oom||len<0||len>0xFFFF) { t->oom=true; return -1; }
    if((t->count+1)*2>t->nslots && !un_grow(t)){ t->oom=true; return -1; }
    uint32_t h=un_hash(s,len)&(t->nslots-1);
    for(;t->slots[h];h=(h+1)&(t->nslots-1)){ uint32_t i=t->slots[h]-1; const uint8_t* e=t->table.p+t->offs[i]; uint16_t l; memcpy(&l,e,2);
        if(l==len && !memcmp(e+2,s,(size_t)len)) return (int32_t)i; }
    if(t->count==t->offcap){ uint32_t c=t->offcap?t->offcap*2:65536; uint32_t* o=(uint32_t*)realloc(t->offs,(size_t)c*4);
        if(!o){ t->oom=true; return -1; } t->offs=o; t->offcap=c; }
    t->offs[t->count]=(uint32_t)t->table.n; ub_u16(&t->table,(uint16_t)len); ub_put(&t->table,s,(size_t)len);
    if(t->table.oom){ t->oom=true; return -1; }
    t->slots[h]=t->count+1; return (int32_t)t->count++; }
static int32_t un_add(UNames* t,const char* s){ return un_add(t,s,(int)strlen(s)); }
static void un_free(UNames* t){ ub_free(&t->table); free(t->offs); free(t->slots); memset(t,0,sizeof *t); }

// header + the three sections, written to <path>.tmp and renamed, so a half-written file never has the real name
static bool usmap_save(const char* path,const UNames* nm,uint32_t nEnums,const UBuf* en,uint32_t nStructs,const UBuf* st){
    if(nm->oom||en->oom||st->oom) return false;
    uint64_t size=4ull+nm->table.n+4+en->n+4+st->n; if(size>0xFFFFFFFFull) return false;
    char tmp[640]; snprintf(tmp,sizeof tmp,"%s.tmp",path);
    FILE* f=fopen(tmp,"wb"); if(!f) return false;
    UBuf h={}; ub_u16(&h,0x30C4); ub_u8(&h,USMAP_VERSION); ub_i32(&h,0); ub_u8(&h,0);
    ub_u32(&h,(uint32_t)size); ub_u32(&h,(uint32_t)size); ub_u32(&h,nm->count);
    bool ok=!h.oom && fwrite(h.p,1,h.n,f)==h.n; ub_free(&h);
    ok=ok && fwrite(nm->table.p,1,nm->table.n,f)==nm->table.n;
    ok=ok && fwrite(&nEnums,4,1,f)==1 && fwrite(en->p,1,en->n,f)==en->n;
    ok=ok && fwrite(&nStructs,4,1,f)==1 && fwrite(st->p,1,st->n,f)==st->n;
    ok=(fclose(f)==0) && ok;
    if(!ok){ remove(tmp); return false; }
    remove(path);                                            // Windows' rename won't replace (the host test)
    return rename(tmp,path)==0; }
