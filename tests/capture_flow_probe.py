from __future__ import annotations
import os
import sys

# Allow direct execution from pokebot-frlg\tests without installing the package.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

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


def changed_bytes(previous: str | None, current: str) -> list[str]:
    if previous is None:
        return []
    before = bytes.fromhex(previous)
    after = bytes.fromhex(current)
    return [f"0x{i:02X}: {before[i]:02X}->{after[i]:02X}"
            for i in range(min(len(before), len(after)))
            if before[i] != after[i]]


def main():
    p = argparse.ArgumentParser(
        description="Read-only FRLG capture-flow RAM probe; never sends controller input."
    )
    p.add_argument("host")
    p.add_argument("--port", type=int, default=6000)
    p.add_argument("--interval", type=float, default=.05)
    p.add_argument("--duration", type=float, default=90)
    p.add_argument("--output", default="capture_flow_probe.jsonl")
    p.add_argument("--summary", default="capture_flow_summary.txt")
    a = p.parse_args()

    if a.interval <= 0 or a.duration <= 0:
        p.error("interval and duration must be positive")

    bot = WiFiBotbase(a.host, a.port)
    bot.connect()
    try:
        title, _ = bot.get_title_id()
        off = lookup(title)
        if off is None:
            raise RuntimeError(f"Unsupported FRLG title: {title}")

        print(f"Connected: {off.language} {off.game} | {title}")
        print(f"READ ONLY | interval={a.interval}s | duration={a.duration}s")
        print("Perform exactly ONE capture during this run; do not press buttons for the probe.")

        previous = None
        previous_state = None
        previous_wild = None
        previous_party = None
        transitions = []
        wild_changes = []
        party_changes = []
        sample_count = 0
        start = time.monotonic()

        with open(a.output, "w", encoding="utf-8") as f:
            end = start + a.duration
            while time.monotonic() < end:
                tick = time.monotonic()
                row = snap(bot, off)
                row["sample"] = sample_count

                f.write(json.dumps(row, separators=(",", ":")) + "\n")
                f.flush()

                state = (
                    row["in_battle"],
                    row["battle_menu"],
                    row["overworld"],
                )
                if previous_state != state:
                    transitions.append({
                        "utc": row["utc"],
                        "sample": sample_count,
                        "battle": row["in_battle"],
                        "menu": row["battle_menu"],
                        "overworld": row["overworld"],
                    })
                    previous_state = state

                wc = changed_bytes(previous_wild, row["wild_0x50"])
                if wc:
                    wild_changes.append({
                        "utc": row["utc"],
                        "sample": sample_count,
                        "changes": wc,
                    })

                pc = changed_bytes(previous_party, row["party_0x258"])
                if pc:
                    party_changes.append({
                        "utc": row["utc"],
                        "sample": sample_count,
                        "changes": pc,
                    })

                previous = row
                previous_wild = row["wild_0x50"]
                previous_party = row["party_0x258"]
                sample_count += 1

                wait = a.interval - (time.monotonic() - tick)
                if wait > 0:
                    time.sleep(wait)

        elapsed = time.monotonic() - start
        with open(a.summary, "w", encoding="utf-8") as s:
            s.write("=== FRLG CAPTURE FLOW SUMMARY ===\n")
            s.write(f"Samples: {sample_count}\n")
            s.write(f"Duration: {elapsed:.2f}s\n")
            s.write(f"Interval: {a.interval:.3f}s\n")
            s.write("\n=== STATE TRANSITIONS ===\n")
            for t in transitions:
                s.write(
                    f'{t["utc"]}  sample={t["sample"]:05d}  '
                    f'battle=0x{t["battle"]:02X} menu=0x{t["menu"]:02X} '
                    f'overworld=0x{t["overworld"]:02X}\n'
                )

            s.write("\n=== WILD DATA CHANGES ===\n")
            if not wild_changes:
                s.write("None\n")
            for c in wild_changes:
                s.write(f'{c["utc"]}  sample={c["sample"]:05d}\n')
                s.write("  " + ", ".join(c["changes"]) + "\n")

            s.write("\n=== PARTY DATA CHANGES ===\n")
            if not party_changes:
                s.write("None\n")
            for c in party_changes:
                s.write(f'{c["utc"]}  sample={c["sample"]:05d}\n')
                s.write("  " + ", ".join(c["changes"]) + "\n")

            s.write("\n=== SEED CHANGES ===\n")
            s.write("Current seed is sampled every interval; the raw JSONL contains every value.\n")
            if previous:
                s.write(f'Last seed: 0x{previous["current_seed"]:08X}\n')

            s.write("\n=== INTERPRETATION NOTES ===\n")
            s.write(
                "State transitions are raw RAM changes only; they are NOT labelled as "
                "Pokedex or nickname until those UI signatures are established.\n"
            )
            s.write(
                "Wild/party changes are included because they can identify the exact "
                "capture-completion point.\n"
            )

        print(f"Raw trace: {a.output}")
        print(f"Compact summary: {a.summary}")
        print(f"State transitions: {len(transitions)} | wild changes: {len(wild_changes)} | party changes: {len(party_changes)}")
    finally:
        bot.close()


if __name__ == "__main__":
    main()
