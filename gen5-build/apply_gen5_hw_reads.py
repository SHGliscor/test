#!/usr/bin/env python3
"""Instrument two passive emulated DS hardware I/O readers for SHA1 boot calibration."""
from pathlib import Path
import sys

def one(src: str, old: str, new: str, label: str) -> str:
    occurrences=src.count(old)
    if occurrences!=1:
        raise ValueError(f'{label}: expected one anchor, got {occurrences}')
    return src.replace(old,new,1)

def patch(root:Path):
    rtc=root/'src/RTC.cpp'
    nds=root/'src/NDS.cpp'
    text=rtc.read_text(encoding='utf-8')
    text=one(text,'#include "RTC.h"\n',
             '#include "RTC.h"\n#if defined(__SWITCH__)\n#include "frontend/switch/Gen5BootTrace.h"\n#endif\n','RTC include')
    text=one(text,'                    Output[6] = BCD(timedata.tm_sec);\n',
             '                    Output[6] = BCD(timedata.tm_sec);\n'
             '#if defined(__SWITCH__)\n'
             '                    Gen5BootTrace::OnRTCRead(Output, 7);\n'
             '#endif\n','full RTC latch')
    text=one(text,'                    Output[2] = BCD(timedata.tm_sec);\n',
             '                    Output[2] = BCD(timedata.tm_sec);\n'
             '#if defined(__SWITCH__)\n'
             '                    Gen5BootTrace::OnRTCRead(Output, 3);\n'
             '#endif\n','time-only RTC latch')
    rtc.write_text(text,encoding='utf-8')

    text=nds.read_text(encoding='utf-8')
    text=one(text,'#include "NDS.h"\n',
             '#include "NDS.h"\n#if defined(__SWITCH__)\n'
             '#include "frontend/switch/Gen5BootTrace.h"\n#endif\n','NDS include')
    text=one(text,'    case 0x04000100: return TimerGetCounter(0);\n',
             '    case 0x04000100: {\n'
             '        const u16 value = TimerGetCounter(0);\n'
             '#if defined(__SWITCH__)\n'
             '        Gen5BootTrace::OnTimer0Read(value, GPU::VCount, GPU3D::Read32(0x04000600));\n'
             '#endif\n'
             '        return value;\n'
             '    }\n','ARM9 IO halfword Timer0')
    text=one(text,'    case 0x04000100: return TimerGetCounter(0) | (Timers[0].Cnt << 16);\n',
             '    case 0x04000100: {\n'
             '        const u32 value = TimerGetCounter(0) | (Timers[0].Cnt << 16);\n'
             '#if defined(__SWITCH__)\n'
             '        Gen5BootTrace::OnTimer0Read(static_cast<u16>(value), GPU::VCount, GPU3D::Read32(0x04000600));\n'
             '#endif\n'
             '        return value;\n'
             '    }\n','ARM9 IO word Timer0')
    nds.write_text(text,encoding='utf-8')
    print('Patched passive DS RTC latches and ARM9 Timer0 register reads')

if __name__=='__main__':
    if len(sys.argv)!=2: raise SystemExit('Usage: apply_gen5_hw_reads.py <source_root>')
    patch(Path(sys.argv[1]))
