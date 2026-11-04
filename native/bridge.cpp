// Build-specific dialogue hooks. Disk executables and game archives are never patched.
#define WIN32_LEAN_AND_MEAN
#define NOMINMAX
#include <windows.h>
#include <bcrypt.h>
#include <algorithm>
#include <cstdio>
#include <cstring>
#include <string>
#include "MinHook.h"

namespace {
using ExecuteLua = const char* (*)(const char*, const char*, char*);
using CallLua = void (*)(const char*, const char*, int&, bool&);
using Message = void (*)(void*, void*);
using Wait = void (*)(void*, float);
using Unary = void (*)(void*);
ExecuteLua execute_lua;
CallLua call_lua;
Message original_line, original_raw_line, original_choices;
Wait original_wait;
Unary original_advance, original_clear;
unsigned char* game;
void* active_message;
unsigned generation;
bool manual = true, permit, hold = true, initialized, enabled = true;
float auto_elapsed;

template<class T> T& field(void* object, size_t offset) {
    return *reinterpret_cast<T*>(static_cast<unsigned char*>(object) + offset);
}

bool execute(const std::string& script) {
    char error[65536]{};
    return execute_lua && execute_lua("StarlitFurigana", script.c_str(), error) == nullptr;
}

void note(const char* text) {
    execute(std::string("print('[StarlitFurigana.Native] ") + text + "\\n')");
}

bool callback(const char* function) {
    int status = 0;
    bool result = false;
    call_lua("StarlitFurigana", function, status, result);
    return status == 1 && result;
}

bool supported_game() {
    wchar_t path[32768];
    if (!GetModuleFileNameW(nullptr, path, 32768)) return false;
    HANDLE file = CreateFileW(path, GENERIC_READ, FILE_SHARE_READ, nullptr, OPEN_EXISTING, 0, nullptr);
    if (file == INVALID_HANDLE_VALUE) return false;
    BCRYPT_ALG_HANDLE algorithm{};
    BCRYPT_HASH_HANDLE hash{};
    bool ok = BCryptOpenAlgorithmProvider(&algorithm, BCRYPT_SHA256_ALGORITHM, nullptr, 0) >= 0;
    if (ok) ok = BCryptCreateHash(algorithm, &hash, nullptr, 0, nullptr, 0, 0) >= 0;
    unsigned char buffer[65536], digest[32]{};
    DWORD count = 0;
    while (ok) {
        if (!ReadFile(file, buffer, sizeof(buffer), &count, nullptr)) { ok = false; break; }
        if (!count) break;
        ok = BCryptHashData(hash, buffer, count, 0) >= 0;
    }
    if (ok) ok = BCryptFinishHash(hash, digest, sizeof(digest), 0) >= 0;
    if (hash) BCryptDestroyHash(hash);
    if (algorithm) BCryptCloseAlgorithmProvider(algorithm, 0);
    CloseHandle(file);
    const unsigned char expected[32] = {
        0x88,0x1d,0xf0,0x5d,0x33,0xa9,0xb2,0x5d,0x27,0x61,0x22,0xf0,0x10,0x16,0x9d,0x79,
        0x0e,0x6c,0xee,0x18,0x66,0x71,0x36,0x98,0x3f,0x8b,0xef,0x0c,0xaa,0x6b,0xf2,0xc2};
    return ok && std::memcmp(digest, expected, sizeof(expected)) == 0;
}

void line_ready(void* self) {
    active_message = self;
    ++generation;
    permit = false;
    hold = true;
    auto_elapsed = 0;
    // Complete the game's own reveal before its text can be drawn. The voice
    // player is independent; do not call the game's skip/stop-voice functions.
    const int unit_count = field<int>(self, 0x248);
    for (int attempt = 0; field<unsigned char>(self, 0x270) &&
         attempt < std::min(std::max(unit_count + 1, 1), 4096); ++attempt) {
        const int before = field<int>(self, 0x26c);
        field<float>(self, 0x268) = 10000.0f;
        reinterpret_cast<Wait>(game + 0xd51a00)(self, 0.0f);
        // A newline/control unit resets native elapsed time. Complete the next
        // batch before publishing the line, without spinning on an unknown unit.
        if (field<unsigned char>(self, 0x270) && field<int>(self, 0x26c) <= before) break;
    }
    if (field<unsigned char>(self, 0x270)) {
        hold = false;
        note("Native reveal did not complete; original text renderer retained.");
        return;
    }
    auto widget = field<void*>(self, field<unsigned char>(self, 0x299) ? 0x230 :
                                   (field<unsigned char>(self, 0x29a) ? 0x238 : 0x228));
    auto text = field<const wchar_t*>(self, 0x250);
    int length = field<int>(self, 0x258);
    std::string utf8;
    if (text && length > 0 && length <= 65536) {
        if (text[length - 1] == 0) --length;
        int bytes = WideCharToMultiByte(CP_UTF8, WC_ERR_INVALID_CHARS, text, length, nullptr, 0, nullptr, nullptr);
        if (bytes > 0) {
            utf8.resize(bytes);
            WideCharToMultiByte(CP_UTF8, WC_ERR_INVALID_CHARS, text, length, &utf8[0], bytes, nullptr, nullptr);
        }
    }
    char prefix[192];
    std::snprintf(prefix, sizeof(prefix), "StarlitFuriganaNativeLine(%llu,%u,'",
        reinterpret_cast<unsigned long long>(widget), generation);
    std::string script(prefix);
    for (unsigned char byte : utf8) {
        if (byte == '\\' || byte == '\'') script += '\\';
        if (byte < 32 || byte == 127) {
            char escape[5]; std::snprintf(escape, sizeof(escape), "\\%03u", byte); script += escape;
        } else script += static_cast<char>(byte);
    }
    script += "')";
    if (!execute(script)) {
        // A Lua error must not trap the player on a dialogue line.
        permit = true;
        hold = false;
        note("Dialogue callback failed; native progression restored for this line.");
    }
}

void on_line(void* self, void* row) {
    original_line(self, row);
    if (enabled) line_ready(self); else active_message = self;
}
void on_raw_line(void* self, void* command) {
    original_raw_line(self, command);
    if (enabled) line_ready(self); else active_message = self;
}

void on_wait(void* self, float delta) {
    if (enabled && self == active_message && !permit) {
        if (manual) return;
        if (hold) {
            auto_elapsed += std::max(0.0f, delta);
            if (auto_elapsed >= 0.1f) {
                char script[128];
                std::snprintf(script, sizeof(script), "StarlitFuriganaNativeAutoTick(%.6f)", auto_elapsed);
                auto_elapsed = 0;
                if (!execute(script)) hold = false;
            }
            if (hold) return;
        }
    }
    original_wait(self, delta);
}

void on_advance(void* input) {
    if (enabled && active_message && (field<unsigned char>(active_message, 0x270) ||
                           field<unsigned char>(active_message, 0x298))) {
        if (callback("StarlitFuriganaConsumeAdvance")) return;
        permit = true;
        hold = false;
    }
    original_advance(input);
}

void on_clear(void* self) {
    if (self == active_message) {
        execute("StarlitFuriganaNativeClear()");
        active_message = nullptr;
        permit = false;
        hold = false;
    }
    original_clear(self);
}

void on_choices(void* self, void* command) {
    original_choices(self, command);
    if (enabled) execute("StarlitFuriganaNativeChoices()");
}

struct Hook { size_t rva; void* handler; void** original; const char* prefix; size_t prefix_size; };
}

// These are Lua C module entry points loaded with package.loadlib. They need no
// Lua ABI import: arguments/return values are handled by UE4SS's C export bridge.
extern "C" __declspec(dllexport) int sf_initialize(void*) {
    if (initialized) return 0;
    auto loader = GetModuleHandleW(L"UE4SS.dll");
    execute_lua = reinterpret_cast<ExecuteLua>(GetProcAddress(loader, "execute_lua_in_mod"));
    call_lua = reinterpret_cast<CallLua>(GetProcAddress(loader, "call_script_function"));
    if (!execute_lua || !call_lua || !supported_game()) {
        note("Unsupported executable or loader; native hooks were not installed.");
        return 0;
    }
    game = reinterpret_cast<unsigned char*>(GetModuleHandleW(nullptr));
    Hook hooks[] = {
        {0xd4f1d0, reinterpret_cast<void*>(on_line), reinterpret_cast<void**>(&original_line), "\x48\x89\x5c\x24\x18\x48\x89\x54\x24\x10\x55\x56\x57", 13},
        {0xd50a70, reinterpret_cast<void*>(on_raw_line), reinterpret_cast<void**>(&original_raw_line), "\x40\x55\x53\x57\x41\x54\x41\x55", 8},
        {0xd52920, reinterpret_cast<void*>(on_wait), reinterpret_cast<void**>(&original_wait), "\x40\x55\x53\x48\x8b\xec\x48\x83\xec\x78", 10},
        {0xd45590, reinterpret_cast<void*>(on_advance), reinterpret_cast<void**>(&original_advance), "\x40\x53\x48\x83\xec\x30", 6},
        {0xd4da70, reinterpret_cast<void*>(on_clear), reinterpret_cast<void**>(&original_clear), "\x40\x53\x48\x83\xec\x20", 6},
        {0xd62970, reinterpret_cast<void*>(on_choices), reinterpret_cast<void**>(&original_choices), "\x48\x89\x4c\x24\x08\x55\x53\x56", 8},
    };
    for (const auto& hook : hooks) {
        if (std::memcmp(game + hook.rva, hook.prefix, hook.prefix_size) != 0) {
            note("A native signature did not match; hooks were not installed.");
            return 0;
        }
    }
    if (MH_Initialize() != MH_OK) { note("Could not initialize native hooks."); return 0; }
    for (const auto& hook : hooks) {
        if (MH_CreateHook(game + hook.rva, hook.handler, hook.original) != MH_OK) {
            MH_Uninitialize(); note("Could not prepare native hooks."); return 0;
        }
    }
    for (const auto& hook : hooks) MH_QueueEnableHook(game + hook.rva);
    if (MH_ApplyQueued() != MH_OK) {
        for (const auto& hook : hooks) MH_DisableHook(game + hook.rva);
        MH_Uninitialize(); note("Could not activate native hooks."); return 0;
    }
    initialized = true;
    execute("StarlitFuriganaNativeReady()");
    return 0;
}

extern "C" __declspec(dllexport) int sf_manual(void*) { manual = true; auto_elapsed = 0; return 0; }
extern "C" __declspec(dllexport) int sf_auto(void*) { manual = false; auto_elapsed = 0; return 0; }
extern "C" __declspec(dllexport) int sf_hold(void*) { hold = true; permit = false; return 0; }
extern "C" __declspec(dllexport) int sf_release(void*) { hold = false; return 0; }
extern "C" __declspec(dllexport) int sf_disable(void*) {
    enabled = false; permit = true; hold = false; auto_elapsed = 0; return 0;
}
extern "C" __declspec(dllexport) int sf_enable(void*) {
    const bool changed = !enabled;
    enabled = true;
    if (initialized && changed && active_message &&
        (field<unsigned char>(active_message, 0x270) || field<unsigned char>(active_message, 0x298))) {
        line_ready(active_message);
    }
    return 0;
}
