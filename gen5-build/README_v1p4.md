# Gen 5 Hardware Read Trace v1.4 (experimental)

Built from pinned `trulymust/melonDS-switch-upscale` commit `2f2a7fbf8d439fc40f15edb2c50ac00600d6dace`. Source changes are on this isolated branch; existing `main` is untouched.

### Source changes

- `Gen5BootTrace.cpp` and `Gen5BootTrace.h`: retain the per-emulated-frame 64-bit RNG, MT624 audit, reset-combination edge and boot-delay correlation. Extend event ABI to **PB5EVT14 / header v5 / 208-byte events / 96 entries**.
- `apply_gen5_hw_reads.py`: instruments the emulated Nintendo DS hardware handlers `RTC::ByteIn` and ARM9's 16-bit and 32-bit `Timer0` reads (`0x04000100`). It stores the recent accessed register values and their event-frame context without touching guest game RAM or injecting inputs.
- `.github/workflows/build-gen5-v1p4-nro.yml`: reproducibly builds `melonDS-Gen5-HardwareReadTrace-v1p4.nro` using the devkitPro Docker toolchain.

[GitHub Actions build](https://github.com/SHGliscor/test/actions/runs/37982185076) completed successfully. Compilation and NRO header checks passed, but Switch **hardware runtime validation is still pending**.

### Prior v1.3 results

The latest user-provided audit completed 240 USB polls without read errors; 20 new MT624-confirmed seed candidates appeared, each associated with an earlier soft-reset button combination, and one final reset-input edge remained at the end without its next-seed follow-up. Candidate emulated MAC was stable across those events, while the event-end GPU VCount was 262 (not a proven seed VCount).

Default (130,000 hypotheses, historical candidate) and expanded (1,115,400 hypotheses, different new candidate) Python SHA-1 searches found no match under their respective bounded ranges. Those non-matches don't disprove the Gen 5 SHA-1 formula; exact seed-time Timer0/VCount/VFrame/RTC/keypress parameters are unresolved.

### v1.4 test objective

Detect actual **DS RTC command-read** and **ARM9 Timer0-read** activity near a seed-initialization event, rather than assuming frame-end clock/VCount are the boot-time SHA-1 inputs. These are observed hardware I/O accesses and cannot yet be claimed to be the exact SHA-1 preimage. The matching Windows companion probe ships separately in the ChatGPT v1.4 package.

This NRO is **read-only with respect to guest RAM**: no controller input, savestates, cheats, or game save modifications.
