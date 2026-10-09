#!/usr/bin/env python3
"""Minimal MAINRAM address readout patch for stock melonDS Switch Upscale v0.8.0.

Only alters on-screen rendering in src/frontend/switch/main.cpp.
NO changes to emulator timing, ARM/JIT, RTC, RNG, input, RAM allocation or save system.
"""
from pathlib import Path
import sys

ANCHOR = "        g_notification.Render();\n        g_triggerNotifications.RenderAll();\n"
NEW = '''        g_notification.Render();
        g_triggerNotifications.RenderAll();

        // POKEBOT_GEN5_MAINRAM_ONLY_V0P1:
        // Expose the current emulated DS RAM host pointer for manual entry.
        // Do not store or write the pointer, touch the guest RAM, or alter
        // any game/frame/reset functionality. Keep the original display path.
        if (Emulation::State == Emulation::emuState_Running &&
            NDS::MainRAM != nullptr) {
            char gen5_mainram_text[96];
            std::snprintf(gen5_mainram_text, sizeof(gen5_mainram_text),
                          "GEN5 MAINRAM: 0x%016llX",
                          (unsigned long long)
                          reinterpret_cast<uintptr_t>(NDS::MainRAM));
            Gfx::DrawRectangle(
                Gfx::Vector2f{14.f, 14.f},
                Gfx::Vector2f{524.f, 42.f},
                Gfx::Color(0.f, 0.f, 0.f, 0.88f));
            Gfx::DrawText(
                Gfx::SystemFontStandard,
                Gfx::Vector2f{25.f, 35.f},
                21.f,
                Gfx::Color(1.f, 1.f, 1.f, 1.f),
                Gfx::align_Left,
                Gfx::align_Center,
                gen5_mainram_text);
        }
'''

def main(root):
    f = Path(root) / 'src/frontend/switch/main.cpp'
    raw = f.read_text(encoding='utf8')
    assert raw.count(ANCHOR)==1, 'Wrong upstream version or changed rendering anchor'
    assert 'POKEBOT_GEN5_MAINRAM_ONLY_V0P1' not in raw, 'Patch already applied'
    assert '#include "NDS.h"' in raw and '#include "Gfx.h"' in raw, 'Missing stock include'
    f.write_text(raw.replace(ANCHOR,NEW,1),encoding='utf8')
    print('Applied exactly one rendering-only insertion to '+str(f))

if __name__=='__main__':
    if len(sys.argv)!=2: raise SystemExit('Usage: python patch_stock_white2_mainram.py <source_root>')
    main(sys.argv[1])
