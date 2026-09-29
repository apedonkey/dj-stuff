// TribeXR cosmetic mod — Phase 2 diagnostic: instrumented Hook A only.
// Question this build answers: does GetAvatarTypeForId (FUN_050fc054) fire at spawn?
// Mechanism: injected .so (added as DT_NEEDED of libUnreal.so). Constructor installs a
// minimal ARM64 absolute-jump "replace" stub over the target's entry — no trampoline,
// original is never called (Hook A is a pure classify->return, safe to fully replace).
//
// libUnreal.so image base = 0 (verified), so runtime target = <load base> + RVA.

#include <android/log.h>
#include <cstdint>
#include <cstdio>
#include <cstring>
#include <cstdlib>
#include <unistd.h>
#include <sys/mman.h>

#define TAG "TRIBEMOD"
#define LOGI(...) __android_log_print(ANDROID_LOG_INFO, TAG, __VA_ARGS__)

// RVA of GetAvatarTypeForId (FUN_050fc054) within libUnreal.so.
static const uintptr_t RVA_GetAvatarTypeForId = 0x050FC054;

// UE FString on Android: { TCHAR* Data; int32 ArrayNum; int32 ArrayMax; }; TCHAR = UTF-16LE.
struct FString { uint16_t* data; int32_t num; int32_t max; };

// Load base of a mapped library = lowest mapping start for its path in /proc/self/maps.
static uintptr_t find_lib_base(const char* name) {
    FILE* f = fopen("/proc/self/maps", "r");
    if (!f) return 0;
    char line[1024];
    uintptr_t best = 0;
    while (fgets(line, sizeof(line), f)) {
        if (strstr(line, name)) {
            uintptr_t start = (uintptr_t)strtoull(line, nullptr, 16);
            if (start && (best == 0 || start < best)) best = start;
        }
    }
    fclose(f);
    return best;
}

static void decode_fstring(const FString* s, char* out, size_t outsz) {
    if (!s)               { snprintf(out, outsz, "(null FString*)"); return; }
    if (!s->data || s->num <= 0) { snprintf(out, outsz, "(empty num=%d)", s ? s->num : -1); return; }
    size_t j = 0;
    for (int i = 0; i < s->num && j + 1 < outsz; ++i) {
        uint16_t c = s->data[i];
        if (c == 0) break;
        out[j++] = (c < 0x80) ? (char)c : '?';  // ASCII-fold for the log line
    }
    out[j] = 0;
}

// Replacement for GetAvatarTypeForId. x0 = FString* id. Returns ETribeAvatarType (w0).
extern "C" int64_t hook_GetAvatarTypeForId(void* idptr) {
    char idbuf[512];
    decode_fstring((const FString*)idptr, idbuf, sizeof(idbuf));
    LOGI("GetAvatarTypeForId FIRED  id='%s'  ptr=%p  -> forcing return 1 (ReadyPlayerMe); original NOT called",
         idbuf, idptr);
    return 1;  // ETribeAvatarType::ReadyPlayerMe
}

// Write a 16-byte absolute-jump stub at target: ldr x16,#8 ; br x16 ; .quad handler
static bool install_replace_hook(uintptr_t target, void* handler) {
    uint8_t stub[16];
    uint32_t ldr = 0x58000050;  // ldr x16, #8
    uint32_t br  = 0xD61F0200;  // br  x16
    uint64_t h   = (uint64_t)handler;
    memcpy(stub + 0, &ldr, 4);
    memcpy(stub + 4, &br,  4);
    memcpy(stub + 8, &h,   8);

    long ps = sysconf(_SC_PAGESIZE);
    uintptr_t pstart = target & ~(uintptr_t)(ps - 1);
    uintptr_t pend   = (target + sizeof(stub) + ps - 1) & ~(uintptr_t)(ps - 1);
    size_t len = pend - pstart;

    bool rwx = (mprotect((void*)pstart, len, PROT_READ | PROT_WRITE | PROT_EXEC) == 0);
    if (!rwx && mprotect((void*)pstart, len, PROT_READ | PROT_WRITE) != 0) {
        LOGI("mprotect FAILED at %p (len=%zu)", (void*)pstart, len);
        return false;
    }
    memcpy((void*)target, stub, sizeof(stub));
    __builtin___clear_cache((char*)target, (char*)(target + sizeof(stub)));
    mprotect((void*)pstart, len, PROT_READ | PROT_EXEC);  // restore executable, drop write
    return true;
}

__attribute__((constructor))
static void on_load() {
    LOGI("hooks installing... (libhook.so constructor running)");
    uintptr_t base = 0;
    for (int i = 0; i < 100 && base == 0; ++i) {
        base = find_lib_base("libUnreal.so");
        if (!base) usleep(50 * 1000);
    }
    if (!base) {
        LOGI("hooks installed: FAILED - libUnreal.so not found in /proc/self/maps");
        return;
    }
    uintptr_t target = base + RVA_GetAvatarTypeForId;
    LOGI("libUnreal.so base=%p  GetAvatarTypeForId target=%p", (void*)base, (void*)target);
    bool ok = install_replace_hook(target, (void*)hook_GetAvatarTypeForId);
    LOGI("hooks installed: %s (Hook A on GetAvatarTypeForId @ %p)", ok ? "OK" : "FAILED", (void*)target);
}
