# Gen 5 v1.1: MT19937 seed-state audit

**Experimental Switch melonDS NRO** for Pokémon Black/White/Black 2/White 2, developed on an isolated branch from `trulymust/melonDS-switch-upscale` pinned to `2f2a7fbf8d439fc40f15edb2c50ac00600d6dace`.

The Switch build uses the existing Gen5 MainRAM pointer export and the FrameTrace v1.0 per-frame sampler. The new `Gen5BootTrace.cpp` implementation additionally checks all **624 words** of the MT19937 initial state on the same frame as the detected MT seed change.

At each change the emulator recomputes `MT[0]=seed`, `MT[i]=1812433253*(MT[i-1]^(MT[i-1]>>30))+i` modulo 2^32. It records match count, first mismatch, and 64-bit FNV-1a hashes of actual and expected state. The Windows v1.1 script separately recomputes the expected fingerprint. This gives independent **MT-state corroboration**, but **does not prove the original SHA-1-derived 64-bit initial seed** (which depends on emulated boot inputs) or which buttons were pressed.

**Build:** [GitHub Actions](https://github.com/SHGliscor/test/actions/workflows/build-gen5-v1p1-nro.yml), branch `gen5-melonds-seed-audit-v1p1`. The build outputs `melonDS-Gen5-MTSeedAudit-v1p1.nro` and its SHA-256 hash.

**Windows:** Use `Gen5_MTSeed_Audit_v1p1_Windows.zip` provided in the same ChatGPT conversation. It reads `PB5EVT11` header with 104-byte events and 128 ring slots, and refuses the old `PB5EVT10` v1.0 format. Launch experimental NRO, load English Pokémon Black, read current `GEN5 TRACE` address from screen, run `RUN_GEN5_MT_AUDIT_QUICK.bat`, manually soft-reset during recording, upload the generated support ZIP. After each full emulator relaunch the pointer may change.

**Safety:** instrumentation reads game memory only. No controller input, guest RAM writes, save modification or savestates. This v1.1 NRO has passed CI compilation but has not yet been validated on Switch hardware.
