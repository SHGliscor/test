#!/usr/bin/env python3
"""Read-only MainRAM pointer export for trulymust/melonDS-switch-upscale at pinned revision."""
from __future__ import annotations
import argparse
from pathlib import Path

SIGNATURE = 'POKEBOT_GEN5_BRIDGE_V1'
INCLUDE_ANCHOR = '#include <stdlib.h>\n'
POINTER_ANCHOR = '    NDS::MainRAM = basePtr + MemBlockMainRAMOffset;\n'
DEINIT_ANCHOR = 'void DeInit()\n{\n#if defined(__SWITCH__)\n'

BRIDGE = r'''
// POKEBOT_GEN5_BRIDGE_V1 — read-only pointer discovery for Switch Koi USB-Botbase.
// An aligned 4KB descriptor is allocated in the process heap. Koi's existing
// peekAbsolute command reads this descriptor and DS RAM. No control interface.
// Retaining the pointer in an externally-visible symbol prevents LTO removal.
#if defined(__SWITCH__) && defined(JIT_ENABLED)
#include <stdint.h>
#include <string.h>

extern "C" {
__attribute__((used, externally_visible)) volatile uintptr_t pokebot_gen5_bridge_anchor = 0;
}

struct Gen5PointerDescriptor {
    uint8_t magic[8];         // 0x00 "PB5RAM01"; published last
    uint32_t version;         // 0x08 = 1
    uint32_t size;            // 0x0C = 64
    uint64_t mainram;         // 0x10: emulated DS RAM backing mapping
    uint64_t inverse;         // 0x18: mainram ^ 0xFFFFFFFFFFFFFFFF
    uint64_t mainram_copy;    // 0x20: repeat pointer
    uint32_t ds_mask;         // 0x28: 0x003FFFFF in DS mode
    uint32_t capacity;        // 0x2C: 0x01000000 allocated for DS/DSi
    uint8_t tag[16];          // 0x30: "MELONDS_SWITCH" + zero padding
};
static_assert(sizeof(Gen5PointerDescriptor) == 64, "Gen5 pointer descriptor must be 64 bytes");
static void* g_gen5_descriptor_page = nullptr;

static void gen5_export_descriptor() {
    if (g_gen5_descriptor_page != nullptr || NDS::MainRAM == nullptr)
        return;
    void* page = aligned_alloc(0x1000, 0x1000);
    if (page == nullptr)
        return;
    memset(page, 0, 0x1000);
    auto* desc = static_cast<Gen5PointerDescriptor*>(page);
    desc->version = 1;
    desc->size = 64;
    desc->mainram = static_cast<uint64_t>(reinterpret_cast<uintptr_t>(NDS::MainRAM));
    desc->inverse = ~desc->mainram;
    desc->mainram_copy = desc->mainram;
    desc->ds_mask = 0x003FFFFF;
    desc->capacity = 0x01000000;
    memcpy(desc->tag, "MELONDS_SWITCH", 14);
    memcpy(desc->magic, "PB5RAM01", 8);
    g_gen5_descriptor_page = page;
    pokebot_gen5_bridge_anchor = reinterpret_cast<uintptr_t>(page);
}

static void gen5_release_descriptor() {
    pokebot_gen5_bridge_anchor = 0;
    if (g_gen5_descriptor_page != nullptr) {
        memset(g_gen5_descriptor_page, 0, 64);
        free(g_gen5_descriptor_page);
        g_gen5_descriptor_page = nullptr;
    }
}
#endif // __SWITCH__ && JIT_ENABLED
'''

def patched_source(original: str) -> str:
    if SIGNATURE in original:
        if 'gen5_export_descriptor();' not in original or 'gen5_release_descriptor();' not in original:
            raise ValueError('Incomplete Gen5 patch exists; refusing a partial rewrite')
        return original
    for anchor in (INCLUDE_ANCHOR, POINTER_ANCHOR, DEINIT_ANCHOR):
        if original.count(anchor) != 1:
            raise ValueError(f'Expected exactly one source anchor {anchor!r}, got {original.count(anchor)}')
    updated = original.replace(INCLUDE_ANCHOR, INCLUDE_ANCHOR + BRIDGE + '\n', 1)
    updated = updated.replace(POINTER_ANCHOR,
        POINTER_ANCHOR + '#if defined(__SWITCH__) && defined(JIT_ENABLED)\n'
        '    gen5_export_descriptor();\n#endif\n', 1)
    updated = updated.replace(DEINIT_ANCHOR,
        'void DeInit()\n{\n#if defined(__SWITCH__)\n'
        '#if defined(JIT_ENABLED)\n    gen5_release_descriptor();\n#endif\n', 1)
    return updated

def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('repo_dir')
    args = parser.parse_args()
    target = Path(args.repo_dir).resolve() / 'src' / 'ARMJIT_Memory.cpp'
    if not target.is_file():
        parser.error(f'File not found: {target}')
    source = target.read_text(encoding='utf-8')
    updated = patched_source(source)
    if updated == source:
        print('Already patched.')
        return 0
    target.write_text(updated, encoding='utf-8')
    print('Patched:', target)
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
