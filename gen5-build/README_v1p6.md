# Gen 5 HeapAutoBridge v1.6 — automatic RAM pointers for shiny hunting

Goal: the Windows Pokémon shiny-hunting bot connects to **Koi USB-Botbase 3.3** and discovers both `GEN5 MAINRAM` and the optional `GEN5 TRACE` pointer **without manual entry**.

## Why v1.5 wasn't enough

The first user hardware report (`Gen5_AutoBridge_20261009_213324.zip`) showed a valid USB connection but an invalid descriptor signature when the PC assumed `getMainNsoBase + 0x2BF000` corresponded to the homebrew NRO's file offset. That assumption is unsafe: Botbase's main NSO is not guaranteed to map the homebrew NRO.

Closing/reopening melonDS can legitimately move process virtual addresses. The bot must discover them afresh and must never reuse stale absolute pointers.

## Changes in v1.6

The `Gen5Auto.cpp` source now duplicates a validated 104-byte `PB5AUTO1` descriptor into a dedicated, `aligned_alloc(4096, 4096)` **emulator heap page** while retaining the static NRO descriptor. Each pointer update is guarded with a monotonic even commit sequence and inverse/copy checks, and no writes are made to the guest Nintendo DS memory. It updates only when a mapping or game changes.

The matching Windows probe (`Gen5_AutoBridge_v1p5b_Windows.zip`) does read-only discovery through existing Koi commands. It checks cached heap-relative descriptor offsets first, then does a bounded scan of the reported main module and heap (up to 256 MiB by default), validates the full pointer descriptor and live cartridge header, and revalidates on subsequent connections.

`GEN5 TRACE` is optional for shiny hunting; `MAINRAM` is required. Any invalid or stale descriptor blocks input until rediscovery succeeds. **No new Koi firmware or Botbase version is required.**

## Build and hardware test

- Source branch: `SHGliscor/test`, `gen5-melonds-heap-bridge-v1p6`.
- Upstream melonDS Switch Upscale pinned at `2f2a7fbf8d439fc40f15edb2c50ac00600d6dace`.
- CI workflow: `.github/workflows/build-gen5-v1p6-nro.yml`.
- Windows read-only locator: 10 synthetic tests passed; **real Switch connection not yet validated**.

Use the new NRO when a confirmed compiled build is available; do not rename a v1.5 binary to v1.6. Run `RUN_AUTO_DISCOVER_V1P5B.bat` on Windows, then upload `Gen5_AutoBridge_v1p5b_*.zip`.

No SHA-1 seed reconstruction is involved. This is the connectivity layer required before automatic Pokémon Black starter hunting.
