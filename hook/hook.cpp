// TribeXR cosmetic mod — Option A (flip the dispatcher's decision) + Hook B (pin the file).
// Injected .so (DT_NEEDED of libUnreal.so). Uses And64InlineHook for arm64 detours with a
// trampoline so we modify args and then CALL THE ORIGINAL.
//
// ADDRESSING: Ghidra rebased the image to 0x00100000, so runtime vaddr = Ghidra addr - 0x100000.
//   Dispatcher FUN_050fc2d4 -> real 0x04FFC2D4 ; glTF choke FUN_050f4548 -> real 0x04FF4548.
//   Runtime target = <libUnreal.so load base> + real vaddr (ELF base is 0). Base recomputed each launch.

#include <android/log.h>
#include <cstdint>
#include <cstdio>
#include <cstring>
#include <cstdlib>
#include <unistd.h>
#include "vendor/And64InlineHook.hpp"

#define TAG "TRIBEMOD"
#define LOGI(...) __android_log_print(ANDROID_LOG_INFO, TAG, __VA_ARGS__)

static const uintptr_t RVA_dispatcher = 0x04FFC2D4; // FUN_050fc2d4 (apply-avatar decision)
static const uintptr_t RVA_choke      = 0x04FF4548; // FUN_050f4548 (glTF file-load choke)

// App-owned external dir: adb-writable AND app-readable, absolute + .glb (passes FUN_050f4548 gate).
static const char *TARGET_PATH = "/sdcard/Android/obb/com.TribeXR.TribeXR/rpmavatar-custom.glb";

// UE FString on Android: { TCHAR* Data; int32 Num; int32 Max; }; TCHAR = UTF-16LE, Num includes NUL.
struct FString { uint16_t *data; int32_t num; int32_t max; };

static uint16_t g_path_u16[256];
static FString  g_fstr;
static void build_target_fstring() {
    int i = 0;
    for (; TARGET_PATH[i] && i < 255; ++i) g_path_u16[i] = (uint16_t)(unsigned char)TARGET_PATH[i];
    g_path_u16[i] = 0;
    g_fstr.data = g_path_u16;
    g_fstr.num  = i + 1;   // include NUL, UE convention
    g_fstr.max  = i + 1;
}

static void decode_fstring(const FString *s, char *out, size_t outsz) {
    if (!s)                       { snprintf(out, outsz, "(null)"); return; }
    if (!s->data || s->num <= 0)  { snprintf(out, outsz, "(empty num=%d)", s->num); return; }
    size_t j = 0;
    for (int i = 0; i < s->num && j + 1 < outsz; ++i) {
        uint16_t c = s->data[i];
        if (c == 0) break;
        out[j++] = (c < 0x80) ? (char)c : '?';
    }
    out[j] = 0;
}

static uintptr_t find_lib_base(const char *name) {
    FILE *f = fopen("/proc/self/maps", "r");
    if (!f) return 0;
    char line[1024]; uintptr_t best = 0;
    while (fgets(line, sizeof(line), f)) {
        if (strstr(line, name)) {
            uintptr_t start = (uintptr_t)strtoull(line, nullptr, 16);
            if (start && (best == 0 || start < best)) best = start;
        }
    }
    fclose(f);
    return best;
}

// Hook A — dispatcher(this /*x0*/, FString* id /*x1*/, char type /*w2*/) -> bool
typedef int64_t (*disp_t)(void *, void *, int64_t);
static disp_t orig_dispatcher = nullptr;
extern "C" int64_t repl_dispatcher(void *thisptr, void *id, int64_t type) {
    char b[600]; decode_fstring((const FString *)id, b, sizeof b);
    LOGI("dispatcher FIRED: incoming type=%d id='%s'", (int)(type & 0xff), b);
    LOGI("dispatcher: forcing type=1 (RPM) url='%s' -> calling original", TARGET_PATH);
    return orig_dispatcher(thisptr, &g_fstr, 1);
}

// Hook B — choke(this /*x0*/, FString* path /*x1*/) -> byte
typedef int64_t (*choke_t)(void *, void *);
static choke_t orig_choke = nullptr;
extern "C" int64_t repl_choke(void *thisptr, void *path) {
    const FString *p = (const FString *)path;
    // GUARD: early init/reset calls pass an empty path; forcing a load there crashes
    // (uninitialized avatar-loaded callback). Pass those straight through, unchanged.
    if (!p || !p->data || p->num <= 0) {
        LOGI("choke FIRED: empty path (num=%d) -> pass-through, NOT forcing", p ? p->num : -1);
        return orig_choke(thisptr, path);
    }
    char b[600]; decode_fstring(p, b, sizeof b);
    LOGI("choke FIRED: path='%s' -> forcing '%s' -> calling original", b, TARGET_PATH);
    return orig_choke(thisptr, &g_fstr);
}

__attribute__((constructor))
static void on_load() {
    LOGI("hooks installing... (libhook.so constructor)");
    build_target_fstring();
    uintptr_t base = 0;
    for (int i = 0; i < 100 && base == 0; ++i) {
        base = find_lib_base("libUnreal.so");
        if (!base) usleep(50 * 1000);
    }
    if (!base) { LOGI("hooks installed: FAILED - libUnreal.so not in /proc/self/maps"); return; }
    void *aDisp  = (void *)(base + RVA_dispatcher);
    void *aChoke = (void *)(base + RVA_choke);
    LOGI("libUnreal.so base=%p  dispatcher=%p  choke=%p", (void *)base, aDisp, aChoke);
    A64HookFunction(aDisp,  (void *)repl_dispatcher, (void **)&orig_dispatcher);
    A64HookFunction(aChoke, (void *)repl_choke,      (void **)&orig_choke);
    LOGI("hooks installed: OK  (Hook A dispatcher @%p orig=%p ; Hook B choke @%p orig=%p)  target='%s'",
         aDisp, (void *)orig_dispatcher, aChoke, (void *)orig_choke, TARGET_PATH);
}
