# Gen5 Reset Evidence v1.2

The Switch NRO is based on the pinned [trulymust/melonDS-switch-upscale](https://github.com/trulymust/melonDS-switch-upscale) source revision `2f2a7fbf8d439fc40f15edb2c50ac00600d6dace`.

**Status:** compiled in GitHub Actions (run 37977794478), runtime validation on actual Switch pending.

The game-specific read-only frame recorder captures a ring of 128 120-byte events, format `PB5EVT12` (header version 3, header size 64). It retains the prior complete MT624 state verification and adds the emulated NDS active-low `KEYINPUT` register. If SELECT+START+R+L are all pressed together (`KEYINPUT & 0x030C == 0`), it records the rising edge of that four-button combination (flag 64), with the latest frame number attached to later initialization events.

The companion Windows script `Gen5_ResetEvidence_v1p2_Windows.zip` (provided to user in ChatGPT) matches this format and correlates input-press events with boot-delay decreases, 64-bit RNG/MT changes and the independent MT19937 initialization-array audit. No buttons are issued, guest game RAM is never written and save files are untouched.

**Important limitations:** Seeing the button combination is a distinct signal but doesn't by itself prove that the game rebooted. Full MT19937 initialization-state matching does not independently authenticate the 64-bit SHA-1-derived initial seed. This experiment tests reset-input correlation only; initial SHA-1 seed reconstruction remains outstanding.

## Real v1.1 findings motivating the change

The supplied `Gen5_MTSeed_Audit_20261009_195946.zip` completed 240 USB polls with no errors, captured 43 event entries (41 new) and 20 new MT624-corroborated, unique initialization candidates. There were 21 recorded delay drops, including a final drop at the end of the window with no corresponding next seed event captured.

## Build

The workflow at `.github/workflows/build-gen5-v1p2-nro.yml` applies the existing pointer export, on-screen trace display and this v1.2 recorder before compiling using the devkitPro Switch toolchain. Binary produced: `melonDS-Gen5-ResetEvidence-v1p2.nro`.
