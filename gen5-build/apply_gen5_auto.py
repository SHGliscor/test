#!/usr/bin/env python3
"""Expose both melonDS pointers via one static module-located descriptor."""
from pathlib import Path
import shutil
import sys

def substitute(s, old, new):
    count=s.count(old)
    if count!=1: raise RuntimeError(f'Expected one anchor {old!r}, saw {count}')
    return s.replace(old,new,1)

def patch(root:Path):
    own=Path(__file__).resolve().parent
    sw=root/'src/frontend/switch'
    for fn in ('Gen5Auto.cpp','Gen5Auto.h'):
        shutil.copy2(own/fn, sw/fn)
    target=sw/'main.cpp'
    s=target.read_text(encoding='utf8')
    s=substitute(s, '#include "Gen5BootTrace.h"\n',
                 '#include "Gen5BootTrace.h"\n#include "Gen5Auto.h"\n')
    s=substitute(s, '    Gen5BootTrace::Init();\n',
                 '    Gen5BootTrace::Init();\n    Gen5Auto::Init();\n')
    s=substitute(s, '                Gen5BootTrace::OnFrame();\n',
                 '                Gen5BootTrace::OnFrame();\n                Gen5Auto::Update();\n')
    s=substitute(s, '    Gen5BootTrace::DeInit();\n',
                 '    Gen5Auto::DeInit();\n    Gen5BootTrace::DeInit();\n')
    target.write_text(s,encoding='utf8')
    cm=sw/'CMakeLists.txt'
    cm_s=cm.read_text(encoding='utf8')
    cm_s=substitute(cm_s,'    Gen5BootTrace.cpp\n',
                    '    Gen5BootTrace.cpp\n    Gen5Auto.cpp\n')
    cm.write_text(cm_s,encoding='utf8')
    print('Added Gen5Auto descriptor to Switch main binary and per-frame update')
if __name__=='__main__':
    if len(sys.argv)!=2:raise SystemExit('Usage: apply_gen5_auto.py SOURCE')
    patch(Path(sys.argv[1]))
