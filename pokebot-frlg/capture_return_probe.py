from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from dataclasses import dataclass, asdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

from pokebot_frlg.wifi_botbase import WiFiBotbase
from pokebot_frlg.offsets import (
    BATTLE_MENU, BOX_FORMAT_SLOT_SIZE, FRLG_GAME_VERSION, IN_BATTLE,
    INITIAL_SEED, PARTY_SLOT_STRIDE, SMALL_SHIFT, lookup,
)

GBA_SAVE_BASE = 0x02020000
SAMPLE_HZ = 20.0
STABLE_POLLS = 5


@dataclass
class Snapshot:
    t: float
    in_battle: int
    battle_menu: int
    overworld: int
    current_seed: int | None
    party_hashes: list[str]
    dex_owned: bool | None
    saveblock2: int | None


def u32(raw: bytes) -> int:
    return int.from_bytes(raw, "little")


def resolve_saveblock2(bot: WiFiBotbase) -> int:
    ptr = u32(bot.read_heap(INITIAL_SEED + SMALL_SHIFT, 4))
    if ptr == 0 or ptr < GBA_SAVE_BASE:
        return 0
    return ptr - GBA_SAVE_BASE + INITIAL_SEED


def read_dex_owned(bot: WiFiBotbase, species: int | None) -> bool | None:
    if not species or not 1 <= species <= 386:
        return None
    base = resolve_saveblock2(bot)
    if not base:
        return None
    index = species - 1
    raw = bot.read_heap(base + 0x18 + 0x10 + index // 8, 1)[0]
    return bool(raw & (1 << (index % 8)))


def party_hashes(bot: WiFiBotbase, party_start: int) -> list[str]:
    out = []
    for i in range(6):
        raw = bot.read_heap(party_start + i * PARTY_SLOT_STRIDE, BOX_FORMAT_SLOT_SIZE)
        out.append(hashlib.sha256(raw).hexdigest()[:16])
    return out


def snapshot(bot: WiFiBotbase, off, species: int | None) -> Snapshot:
    return Snapshot(
        t=time.monotonic(),
        in_battle=bot.read_heap(IN_BATTLE, 1)[0],
        battle_menu=bot.read_heap(BATTLE_MENU, 1)[0],
        overworld=bot.read_heap(off.overworld, 1)[0],
        current_seed=u32(bot.read_heap(off.current_seed, 4)),
        party_hashes=party_hashes(bot, off.party_start),
        dex_owned=read_dex_owned(bot, species),
        saveblock2=resolve_saveblock2(bot),
    )


def changed(a: Snapshot, b: Snapshot) -> dict:
    d = {}
    for k in ("in_battle", "battle_menu", "overworld", "current_seed",
              "party_hashes", "dex_owned", "saveblock2"):
        av, bv = getattr(a, k), getattr(b, k)
        if av != bv:
            d[k] = {"before": av, "after": bv}
    return d


def log_snapshot(prefix: str, s: Snapshot) -> None:
    print(
        f"[RAM] {prefix} IN_BATTLE=0x{s.in_battle:02X} "
        f"BATTLE_MENU=0x{s.battle_menu:02X} "
        f"OVERWORLD=0x{s.overworld:02X} "
        f"SEED=0x{(s.current_seed or 0):08X} "
        f"DEX={s.dex_owned!r} SAVE2=0x{(s.saveblock2 or 0):X}"
    )


def run(args):
    bot = WiFiBotbase(args.host, args.port, timeout_s=5)
    result = {
        "capture": "NOT_TESTED",
        "capture_complete": "NOT_TESTED",
        "pokedex_registration": "NOT_TESTED",
        "pokedex_complete": "NOT_TESTED",
        "nickname_prompt": "NOT_TESTED",
        "nickname_decision": "NOT_TESTED",
        "nickname_screen": "N/A",
        "overworld_return": "NOT_TESTED",
        "events": [],
    }

    try:
        ident = bot.connect()
        title, _ = bot.get_title_id()
        off = lookup(title)
        if off is None:
            raise RuntimeError(f"Unsupported FRLG title ID: {title}")
        version, _ = bot.get_textish("game version")
        if version != FRLG_GAME_VERSION:
            raise RuntimeError(f"Expected FRLG {FRLG_GAME_VERSION}, got {version}")

        print("=" * 56)
        print("FRLG CAPTURE RETURN PROBE")
        print("=" * 56)
        print(f"[PROBE] Connected {off.language} {off.game} {version}")
        print(f"[PROBE] Botbase socket: {args.host}:{args.port}")
        print("[PROBE] This build is RAM-first discovery mode.")
        print("[PROBE] It never sends blind A/B input.")
        print()

        before = snapshot(bot, off, args.species)
        log_snapshot("START", before)

        if before.in_battle != 0x02:
            print("[HOLD] IN_BATTLE is not 0x02.")
            print("[HOLD] Start this probe while the capture result is still active.")
            result["events"].append({"state": "HOLD", "reason": "not_in_battle"})
            return result

        print("[STATE] CAPTURE_START")
        result["capture"] = "PASS"
        result["events"].append({"state": "CAPTURE_START", "ram": asdict(before)})

        previous = before
        deadline = time.monotonic() + args.timeout
        battle_clear_time = None
        dex_before = before.dex_owned

        while time.monotonic() < deadline:
            time.sleep(1.0 / SAMPLE_HZ)
            current = snapshot(bot, off, args.species)
            delta = changed(previous, current)

            if delta:
                print(f"[RAM] transition: {json.dumps(delta, default=str)}")
                result["events"].append({
                    "state": "RAM_CHANGE",
                    "t": current.t,
                    "delta": delta,
                    "snapshot": asdict(current),
                })

            if previous.in_battle == 0x02 and current.in_battle != 0x02:
                battle_clear_time = current.t
                result["capture_complete"] = "PASS"
                print("[STATE] CAPTURE_COMPLETE candidate: IN_BATTLE cleared")

            if dex_before is False and current.dex_owned is True:
                result["pokedex_registration"] = "PASS"
                print("[STATE] POKEDEX_REGISTRATION: owned-bit changed 0 -> 1")
                dex_before = True

            if battle_clear_time is not None and current.in_battle != 0x02:
                if current.overworld == 0xFF:
                    result["events"].append({"state": "OVERWORLD_CANDIDATE", "snapshot": asdict(current)})
                    stable = 1
                    while stable < STABLE_POLLS and time.monotonic() < deadline:
                        time.sleep(1.0 / SAMPLE_HZ)
                        check = snapshot(bot, off, args.species)
                        if check.overworld == 0xFF and check.in_battle != 0x02:
                            stable += 1
                        else:
                            stable = 0
                        previous = check
                    if stable >= STABLE_POLLS:
                        result["overworld_return"] = "PASS"
                        result["pokedex_complete"] = (
                            "PASS" if result["pokedex_registration"] == "PASS"
                            else "NOT_OBSERVED"
                        )
                        print("[STATE] OVERWORLD_CONFIRMED")
                        break

            previous = current

        print()
        print("=" * 56)
        print("RESULT")
        print("=" * 56)
        for k, v in result.items():
            if k != "events":
                print(f"{k.replace('_', ' ').title()+':':25} {v}")
        print("=" * 56)

        if result["overworld_return"] != "PASS":
            print("[SAFETY HOLD] Overworld was not positively confirmed.")
            print("[SAFETY HOLD] No controller input was sent.")

        return result

    finally:
        try:
            bot.set_stick("LEFT", 0, 0)
            bot.set_stick("RIGHT", 0, 0)
            bot.detach_controller()
        except Exception:
            pass
        bot.close()


def main():
    p = argparse.ArgumentParser(description="Standalone FRLG post-capture RAM discovery probe.")
    p.add_argument("host", help="Switch IP address")
    p.add_argument("--port", type=int, default=6000)
    p.add_argument("--species", type=int, default=None, help="Caught species ID (1-386).")
    p.add_argument("--timeout", type=float, default=45.0)
    p.add_argument("--json", dest="json_path", default=None, help="Write the complete trace to JSON.")
    args = p.parse_args()

    try:
        result = run(args)
    except KeyboardInterrupt:
        print("\n[PROBE] Interrupted. No post-capture input was issued.")
        return 130
    except Exception as exc:
        print(f"[ERROR] {type(exc).__name__}: {exc}")
        return 1

    if args.json_path:
        Path(args.json_path).write_text(json.dumps(result, indent=2, default=str), encoding="utf-8")
        print(f"[PROBE] Trace written to {args.json_path}")

    return 0 if result["overworld_return"] == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
