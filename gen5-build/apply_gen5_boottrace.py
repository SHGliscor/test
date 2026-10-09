#!/usr/bin/env python3
"""Inject Gen5BootTrace into pinned melonDS Switch Upscale source tree."""
from pathlib import Path
import shutil
import sys

def patch(source:Path):
    root=Path(__file__).resolve().parent
    switch=source/'src/frontend/switch'
    main=switch/'main.cpp'
    cmake=switch/'CMakeLists.txt'
    for name in ('Gen5BootTrace.cpp','Gen5BootTrace.h'):
        shutil.copy2(root/name, switch/name)
    code=main.read_text(encoding='utf-8')
    if 'Gen5BootTrace::OnFrame();' in code:
        raise RuntimeError('Already patched')
    replacements=[
        ('#include "NotificationSystem.h"\n', '#include "NotificationSystem.h"\n#include "Gen5BootTrace.h"\n'),
        ('                NDS::RunFrame();\n', '                NDS::RunFrame();\n                Gen5BootTrace::OnFrame();\n'),
        ('    Emulation::Init();\n', '    Emulation::Init();\n    Gen5BootTrace::Init();\n'),
        ('    Emulation::DeInit();\n', '    Gen5BootTrace::DeInit();\n    Emulation::DeInit();\n'),
        ('"GEN5 DESC: 0x%016llX"', '"GEN5 TRACE: 0x%016llX"'),
        ('(unsigned long long)pokebot_gen5_bridge_anchor);', '(unsigned long long)Gen5BootTrace::BufferAddress());'),
    ]
    for old,new in replacements:
        if code.count(old)!=1:
            raise ValueError(f'Expected 1 occurrence of {old!r}, got {code.count(old)}')
        code=code.replace(old,new,1)
    main.write_text(code,encoding='utf-8')
    cm=cmake.read_text(encoding='utf-8')
    anchor='    main.cpp\n'
    if cm.count(anchor)!=1:raise ValueError('Could not locate CMake Switch main.cpp')
    cm=cm.replace(anchor,anchor+'    Gen5BootTrace.cpp\n',1)
    cmake.write_text(cm,encoding='utf-8')
    print('Injected Gen5 v1.0 per-frame trace module and on-screen TRACE pointer')

if __name__=='__main__':
    if len(sys.argv)!=2:raise SystemExit('Usage: apply_gen5_boottrace.py <melonDS-source>')
    patch(Path(sys.argv[1]))
