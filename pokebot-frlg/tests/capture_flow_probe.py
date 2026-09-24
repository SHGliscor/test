from __future__ import annotations
import argparse
import json
import time
from datetime import datetime, timezone
from pokebot_frlg.offsets import IN_BATTLE, BATTLE_MENU, lookup
from pokebot_frlg.wifi_botbase import WiFiBotbase

def snap(bot, off):
    return {
        "utc": datetime.now(timezone.utc).isoformat(timespec="milliseconds"),
        "monotonic": round(time.monotonic(), 6),
        "in_battle": bot.read_heap(IN_BATTLE, 1)[0],
        "battle_menu": bot.read_heap(BATTLE_MENU, 1)[0],
        "overworld": bot.read_heap(off.overworld, 1)[0],
        "current_seed": int.from_bytes(bot.read_heap(off.current_seed, 4), "little"),
        "wild_0x50": bot.read_heap(off.wild_pokemon, 0x50).hex().upper(),
        "party_0x258": bot.read_heap(off.party_start, 0x64 * 6).hex().upper(),
    }

def main():
    p=argparse.ArgumentParser(description="Read-only FRLG capture-flow RAM probe; never sends controller input.")
    p.add_argument("host")
    p.add_argument("--port",type=int,default=6000)
    p.add_argument("--interval",type=float,default=.10)
    p.add_argument("--duration",type=float,default=90)
    p.add_argument("--output",default="capture_flow_probe.jsonl")
    a=p.parse_args()
    if a.interval<=0 or a.duration<=0: p.error("interval and duration must be positive")
    bot=WiFiBotbase(a.host,a.port); bot.connect()
    try:
        title,_=bot.get_title_id(); off=lookup(title)
        if off is None: raise RuntimeError(f"Unsupported FRLG title: {title}")
        print(f"Connected: {off.language} {off.game} | {title}")
        print(f"READ ONLY | interval={a.interval}s | duration={a.duration}s")
        print("Perform exactly ONE capture during this run; do not press buttons for the probe.")
        with open(a.output,"w",encoding="utf-8") as f:
            end=time.monotonic()+a.duration; n=0
            while time.monotonic()<end:
                t=time.monotonic(); row=snap(bot,off); row["sample"]=n
                f.write(json.dumps(row,separators=(",",":"))+"\n"); f.flush()
                print(f'{n:05d} battle=0x{row["in_battle"]:02X} menu=0x{row["battle_menu"]:02X} overworld=0x{row["overworld"]:02X} seed=0x{row["current_seed"]:08X}',flush=True)
                n+=1
                wait=a.interval-(time.monotonic()-t)
                if wait>0: time.sleep(wait)
    finally: bot.close()

if __name__=="__main__": main()
