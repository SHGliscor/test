#!/usr/bin/env python3
"""Add a diagnostic readout to the Switch frontend (NOT a game-specific hook)."""
from pathlib import Path
import sys

INCLUDE_ANCHOR = '#include "NotificationSystem.h"\n'
RENDER_ANCHOR = '        g_notification.Render();\n        g_triggerNotifications.RenderAll();\n'
INCLUDE = '''// Diagnostic-only on-screen pointer readout; no network or memory writes.\nextern "C" volatile uintptr_t pokebot_gen5_bridge_anchor;\n'''
RENDER = '''        // GEN5_V0P6_POINTER_READOUT: visible after ROM loads, no heap scanning.
        if (NDS::MainRAM != nullptr) {
            char mainram_label[96];
            char descriptor_label[96];
            std::snprintf(mainram_label, sizeof(mainram_label),
                          "GEN5 MAINRAM: 0x%016llX",
                          (unsigned long long)(uintptr_t)NDS::MainRAM);
            std::snprintf(descriptor_label, sizeof(descriptor_label),
                          "GEN5 DESC: 0x%016llX",
                          (unsigned long long)pokebot_gen5_bridge_anchor);
            Gfx::DrawRectangle(Gfx::Vector2f{14.f,14.f},
                               Gfx::Vector2f{530.f,74.f}, Gfx::Color(0.f,0.f,0.f,0.90f));
            Gfx::DrawText(Gfx::SystemFontStandard, Gfx::Vector2f{26.f,28.f},
                          21.f, Gfx::Color(1.f,1.f,1.f,1.f),
                          Gfx::align_Left, Gfx::align_Center, mainram_label);
            Gfx::DrawText(Gfx::SystemFontStandard, Gfx::Vector2f{26.f,59.f},
                          21.f, Gfx::Color(1.f,1.f,1.f,1.f),
                          Gfx::align_Left, Gfx::align_Center, descriptor_label);
        }
'''

def patched_source(raw:str)->str:
    if 'GEN5_V0P6_POINTER_READOUT' in raw:
        if 'mainram_label' not in raw:
            raise ValueError('Partial existing overlay patch')
        return raw
    for anchor in (INCLUDE_ANCHOR, RENDER_ANCHOR):
        if raw.count(anchor) != 1:
            raise ValueError(f'Expected exactly one anchor {anchor!r}, got {raw.count(anchor)}')
    raw=raw.replace(INCLUDE_ANCHOR,INCLUDE_ANCHOR+'\n'+INCLUDE,1)
    return raw.replace(RENDER_ANCHOR,RENDER_ANCHOR+RENDER,1)

def main()->int:
    target=Path(sys.argv[1])/'src/frontend/switch/main.cpp'
    txt=target.read_text(encoding='utf-8')
    new=patched_source(txt)
    target.write_text(new,encoding='utf-8')
    print('Applied Gen5 v0.6 on-screen pointer readout:',target)
    return 0
if __name__=='__main__':raise SystemExit(main())
