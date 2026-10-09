# melonDS Gen 5 AutoBridge v1.5

**Goal:** eliminate manually copying the two process-specific Switch pointers shown by the emulator.

The NRO now keeps a static 104-byte `PB5AUTO1` descriptor containing the live `NDS::MainRAM` host pointer and the diagnostic FrameTrace pointer. The descriptor is stored in the NRO's regular data segment, not in a randomly positioned heap allocation. The recorded pointer values include duplicate and inverted copies and a commit sequence, allowing the PC bot to validate integrity.

The Windows `gen5_auto_bridge.py` companion (distributed as a ZIP in the ChatGPT project) requests the application module base through Koi's `getMainNsoBase`, uses an NRO-static descriptor-address hint (derived from the compiled binary), and falls back to an **8 MiB bounded scan of the main module**, not a heap-wide RAM sweep. It independently verifies the Nintendo DS ROM header before accepting `MAINRAM`. The `TRACE` pointer is validated separately and remains optional for shiny hunting.

The client helper `BridgeSession.ensure_connected()` revalidates pointers and triggers rediscovery when the emulator process or ROM mapping changes. It never sends input or writes DS memory. Future unattended-hunt code must pause game inputs whenever that validation fails.

**Build:** [GitHub Actions run 37986254679](https://github.com/SHGliscor/test/actions/runs/37986254679), successfully compiled and verified as an NRO. Static descriptor signature `PB5AUTO1` appears at NRO file offset `0x2BF000`. The Windows synthetic tests passed (10), including forced pointer relocation and corrupted pointer detection.

**Hardware confirmation pending.** This mechanism has not yet been demonstrated to read both pointers on the user's physical Switch through USB. The relevant next artifact to collect is `Gen5_AutoBridge_*.zip` from `RUN_GEN5_AUTO_DISCOVER.bat`. Keep the existing working v1.4 NRO as a fallback.

Based on `trulymust/melonDS-switch-upscale` at commit `2f2a7fbf8d439fc40f15edb2c50ac00600d6dace`.
