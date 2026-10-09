# Gen 5 SHA-1 Boot Context Audit v1.3

**Status:** Complete Nintendo Switch NRO compiled successfully by [GitHub Actions build 37980276789](https://github.com/SHGliscor/test/actions/runs/37980276789). **Not yet runtime-tested on Switch.**

## Changes from v1.2

- Retains `NDS::MainRAM` pointer export via the same Switch source.
- Retains read-only per-emulated-frame RNG, boot-delay, soft-reset-key combination and all 624-word MT19937 state checks.
- Changes frame trace ABI from `PB5EVT12` to `PB5EVT13`: header version **4**, event size **160**, ring capacity **120**.
- Adds event-frame capture of `time(nullptr)` and the Switch-local `localtime_r` RTC data (year/month/day/weekday/hour/minute/second BCD), the six emulated `Wifi::GetMAC()` register bytes, current `GPU::VCount`, `GPU3D::Read32(0x04000600)` GXSTAT and DS console type.
- These snapshot values are **context**, not proof they are the values consumed by the game's SHA-1 routine at its exact seeding instruction.

The Windows companion to this build includes a separate pure-Python Gen 5 SHA-1 seeding algorithm with a published independent test vector from [Admiral-Fish/RNGWriteups](https://github.com/Admiral-Fish/RNGWriteups/blob/master/Gen%205/Initial%20Seeding.md) and English game Nazos from [PokeFinder](https://github.com/Admiral-Fish/PokeFinder/blob/master/Core/Gen5/Nazos.cpp).

The published DS/English Pokémon White example (2000-01-01 00:00:00; 00:09:BF:12:34:56; Timer0=0x621, VCount=0x2F, VFrame=5, GXSTAT=6; none pressed; no soft reset) produces the independently documented seed `0xB082B4A755192171`, as confirmed by the Python tests. Other inputs must be calibrated against the user's running Switch game.

The matching algorithm cannot independently verify an observed initial seed until exact seed-time Timer0, VCount, VFrame, GXSTAT, keypresses, MAC, RTC second and soft-reset flag are established. A search match over guessed inputs is classified as `HAS_SHA1_MATCHES_UNDER_HYPOTHESES`, **not fully verified**.

This NRO is **read-only with respect to DS game RAM** and does not inject controller inputs or use savestates.

## Build details

Repository: `SHGliscor/test`, branch `gen5-melonds-sha1-preimage-v1p3`. Upstream: `trulymust/melonDS-switch-upscale` commit `2f2a7fbf8d439fc40f15edb2c50ac00600d6dace`. Build: `devkitpro/devkita64`, Nintendo Switch NRO toolchain.

Output: `melonDS-Gen5-SHA1BootAudit-v1p3.nro`.
