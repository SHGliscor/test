PokebotSwitch-FRLG UI v0.17 — Dedicated RNG Controls Tab

Verified hardware baseline
- English LeafGreen 1.0.0: starter loop hardware PASS.
- English FireRed 1.0.0: RAM/PK3/battle state PASS.
- Koi botbase 3.33 Wi-Fi mode: PASS.
- FireRed/LeafGreen are auto-detected by Title ID.
- RAM is read-only. Automation uses controller commands only.

Install
1. Run requirements.bat once.
2. Run run_PokebotSwitch-FRLG.bat.
3. Set the Switch IP if it differs from the saved AppData value.
4. Pick a hunt category and hunt on the Dashboard. Read the setup text before Start Hunt.

Hunts included
Starters
- Bulbasaur
- Charmander
- Squirtle

Gifts / Fossils
- Magikarp — Route 4 salesman
- Hitmonlee — Fighting Dojo
- Hitmonchan — Fighting Dojo
- Eevee — Celadon Mansion
- Lapras — Silph Co.
- Togepi Egg — Water Labyrinth (egg PK3 is checked directly; hatching is not required)
- Omanyte — Helix Fossil revival
- Kabuto — Dome Fossil revival
- Aerodactyl — Old Amber revival
- Custom gift — next empty party slot

Game Corner
- Abra
- Clefairy
- Dratini
- Scyther — FireRed only
- Pinsir — LeafGreen only
- Porygon
- 1–5 prizes can be purchased per reset, limited by free party slots.

Static / Legendary
- Snorlax
- Electrode
- Hypno — Berry Forest
- Articuno
- Zapdos
- Moltres
- Mewtwo
- Lugia
- Ho-Oh (special Up trigger)
- Deoxys
- Custom static encounter

Roaming Beasts
- Raikou
- Entei
- Suicune

Wild
- Grass / Cave / Surf encounters
- Fishing encounters

Utility hunt
- Pickup farming + shiny check before KO

Not presented as shiny hunts
- FRLG in-game NPC trades are omitted because the received trade Pokémon is fixed rather than a rerolled shiny target.

Live Party / Recently Seen
- Live Party refreshes from RAM while idle.
- Each party card shows an FRLG-era normal or shiny sprite when cached/available.
- Recently Seen shows the matching normal/shiny sprite for each encounter.
- Real Gen-3 ability names are shown instead of only Ability 1 / Ability 2.
- Nature, IVs, IV sum, SV, PID and Pokérus remain visible.
- Full Gen-3 species/ability data and sprites are cached under AppData on first use.

AppData
All persistent data is under:
  %APPDATA%\PokebotSwitch-FRLG\

Lifetime stats
- total encounters
- total shinies
These survive every new session, restart and program-folder replacement.

Session stats
Every Start Hunt creates a completely new session and resets:
- encounters
- shinies
- elapsed time
- encounters/hour
- Recently Seen
- Current / Last Seen
- IV high/low
- SV high/low

When a shiny is found inside a session
- session/lifetime encounters remain
- session/lifetime shiny totals remain/increment
- only the rolling IV/SV high/low records reset for the next shiny cycle

Support ZIPs
  %APPDATA%\PokebotSwitch-FRLG\support\

Safety
- Version-exclusive Game Corner prizes are filtered automatically after FireRed/LeafGreen detection.
- Named Gift/Static/Game Corner/Roamer hunts verify the expected species from RAM.
- Safety holds generate a support ZIP instead of blindly continuing.


SHINY SAFETY (v0.7)
Until auto-capture is implemented, any shiny detected by an active hunt immediately sends the Switch HOME button and stops the hunt. No run, reset, KO, purchase, or other hunt input is sent after the shiny decision.


DISCORD SUPPORT (v0.8)
----------------------
FRLG now mirrors the ORAS project's Discord safety model:
- bot-account notifications
- /status and /party read-only remote commands
- hunt start/stop + Switch connection status notifications
- shiny embeds with FRLG sprite, nature, ability, IVs, SV, PID and stats
- safety-hold notifications
- optional Discord Rich Presence

Discord is presentation only. It can never classify a shiny, authorize a reset, or override the FRLG RAM/state machine.
Configure Discord under SETTINGS. Bot token, channel ID and Rich Presence application ID are saved under %APPDATA%\PokebotSwitch-FRLG\settings.json.
Support diagnostics never include the bot token.


DISCORD RICH PRESENCE GAME LOGO (v0.9)
----------------------------------------
Rich Presence now always requests the Discord Art Asset key:  frlg-logo

To make the FireRed / LeafGreen game logo appear as the large Rich Presence image:
1. Open the same Discord Developer Portal application whose Application ID is entered in SETTINGS.
2. Open Rich Presence -> Art Assets.
3. Upload your combined Pokémon FireRed / LeafGreen logo image. 1024x1024 is recommended.
4. Name the asset exactly: frlg-logo
5. Save it, then restart Rich Presence / the bot if Discord was already connected.

The asset is presentation-only. Missing or invalid Discord artwork cannot affect RAM shiny detection, HOME safety hold, resets, encounters, or controller decisions.


v0.10 — Koi Display Control
- Header Display Off / Display On toggle using Koi Wi-Fi commands screenOff/screenOn.
- Works during active hunts; display control is serviced by the backend worker.
- Shiny HOME safety wakes the panel before pressing HOME.
- Disconnect/exit restores the panel if this UI turned it off.


v0.11 WILD MOVEMENT FIX
- Wild/Pickup overworld encounter movement now uses LEFT STICK pulses instead of Switch D-pad click commands.
- This specifically addresses the first hardware wild test where the game START menu opened and the cursor moved toward Save even though no START/PLUS command was logged.
- Wild movement now keeps one axis for the whole encounter search and alternates axis only after a completed battle, matching the public FRLG routine more closely.
- Starter/reset timing and controller initialization are unchanged.


v0.12 WILD RUN / CONTROLLER RELEASE / UI FIX
- Accepts both documented FRLG battle-menu ready values (0x01 and 0x02); 0x00 remains loading/not-ready.
- Non-shiny Wild/Fishing now navigates to Run with the proven left-stick input path.
- Every hunt exit automatically sends detachController after neutralising both sticks.
- Added a header Release Controller button for manual physical-controller handback while idle.
- Sprite download failures are no longer permanently cached; legacy *.failed markers are cleared and species such as Staryu retry automatically.
- Recently Seen gets more dashboard width, stable column widths, and no horizontal scrollbar.


v0.13 READ-ONLY SHINY-FRAME MISS
- Starter encounters now show how many Gen-3 LCRNG advances the observed Method-1 PID-start missed the nearest shiny PID-start by.
- Signed display: -N = nearest shiny start was earlier, +N = later, HIT = the current Pokémon is shiny.
- The metric is retrospective only. It never waits for a seed, changes button timing, writes RNG/RAM, predicts an input time, or alters hunt/reset decisions.
- v0.13 enables this metric only for the starter engine. Other hunt engines show — until their exact RNG generation methods are modeled and hardware-validated.
- Method-1 reconstruction must match both the observed PID and all six IVs before a distance is shown. If validation fails, the UI shows — instead of guessing.
- Current/Last Seen shows the compact miss value; hover text includes the validated generation seed, captured live seed, previous/next shiny distances, and generation-to-capture advance count.
- Recently Seen persists the RNG diagnostic fields in the current AppData session. Older session JSON remains compatible.


v0.15 ALL-HUNTS READ-ONLY SHINY-FRAME MISS
- The RNG Miss diagnostic now runs for every active hunt engine, not only starters.
- Starters, gifts/fossils, statics/legendaries and Game Corner prizes reconstruct exact Gen-III Method 1/2/4 PID+IV spacing and report only a fully validated match.
- Grass/Cave/Surf, Fishing and Pickup wild encounters use the corresponding H1/H2/H4 labels; the final PID+IV spacing is validated against the observed wild PK3 before a value is shown.
- Raikou/Entei/Suicune use a dedicated FRLG roamer reconstruction that validates the exact PID plus the surviving low IV byte, matching the FRLG roamer IV bug.
- -N = nearest raw shiny PID-start was earlier, +N = later, HIT = current Pokémon is shiny. This is a retrospective PID-frame distance, not a prediction that a future encounter at that many advances will necessarily be shiny.
- The metric remains observation-only: no RNG writes, seed waiting, timing manipulation, reset changes, encounter targeting or controller decisions.
- If an encounter's exact PID/IV sequence cannot be reconstructed from the captured live seed, the UI shows — rather than inventing a distance.

SUPPORT / APPDATA POLICY (v0.15)
- Normal encounters, normal Start/Stop, and successful sessions do NOT create support ZIPs.
- Routine Discord activity is not written to a JSONL audit file.
- No timestamped sessions/*.json archives are created on normal stops.
- Persistent operational files remain stats.json, settings.json, and session_current.json.
- A genuine exception/safety failure creates ONE support ZIP in AppData\PokebotSwitch-FRLG\support.
- The diagnostic JSON is stored inside that ZIP; no duplicate loose support JSON is left behind.
- Existing support/session files from older builds are not automatically deleted.


v0.16 EXPERIMENTAL LIVE-SEED AUTO RNG
--------------------------------------
This build adds an opt-in Automatic RNG mode to the existing RAM shiny hunter.
It does NOT write or freeze game RAM. It reads the live 32-bit Gen-III PokeRNG
state and times normal Koi controller inputs against that observed stream.

Why this is different from traditional FRLG RNG
- Traditional FRLG manipulation normally targets a difficult 16-bit initial seed
  and then waits a calibrated number of advances.
- This bot can already read the live 32-bit PokeRNG state on Switch, so v0.16
  searches forward from the state the game is actually using right now.
- After a miss, the observed PK3 + captured live RNG state reconstruct the exact
  generation seed. The bot compares it with the selected target and automatically
  adjusts the per-hunt Trigger lead for the next reset.
- Learned Trigger lead values are stored per hunt in AppData settings.json.

v0.16 hardware-test scope
- Starter: Bulbasaur / Charmander / Squirtle
- Gift/Fossil engine
- Static / Legendary engine, including Ho-Oh's special Up trigger

Not Auto-RNG-enabled yet
- Wild grass/cave/surf
- Fishing
- Pickup
- Game Corner batch prizes
- Roaming beasts
These still use the proven normal shiny-hunting routines. Wild/Fishing need their
H-method encounter/nature/slot RNG consumption modeled before live target timing
can be considered trustworthy.

Dashboard Auto RNG controls
- Automatic RNG: enables live-seed targeting for supported hunt engines.
- Shiny only: search only PID states shiny for the save's live TID/SID.
- Nature: optional target nature.
- HP/Atk/Def/SpA/SpD/Spe >=: minimum IV filters. For the first hardware pass,
  leave these at 0; IV target spacing is currently Method 1.
- Max search: maximum forward RNG advances scanned for a matching target.
- Trigger lead: estimated number of RNG advances between the first timed input
  and Pokémon PID generation. The bot changes this automatically after a
  validated miss and remembers the value for that hunt.

FIRST HARDWARE TEST — recommended
1. Use a starter save already proven with normal hunting.
2. Start v0.16 with Automatic RNG OFF and confirm one normal reset still works.
3. Stop the hunt.
4. Enable Automatic RNG + Shiny only. Leave Nature=Any and all IV minimums at 0.
5. Start the same starter hunt.
6. Watch the Hunt control status. It will print the selected future RNG target,
   distance, target nature/IVs/SV and the current trigger lead.
7. If the first result misses, let the bot reset. It will reconstruct the exact
   observed generation seed and adjust Trigger lead automatically.
8. Do not manually press buttons during calibration.
9. A real shiny still uses the existing RAM shiny authority and HOME safety hold.

Important prototype rule
Auto RNG is an additional targeting layer only. It does not replace the existing
PK3 validation, expected-species safety checks, shiny decision, or HOME hold.


v0.17 — DEDICATED RNG CONTROLS TAB
-----------------------------------
- Automatic RNG controls have been removed from the Dashboard hunt-control card.
- Added a full RNG tab between HUNTS and STATISTICS.
- The RNG tab now contains: Auto RNG enable/disable, selected-hunt compatibility, shiny/nature target, forward-search limit, all six minimum IV filters, trigger lead, and live calibration status.
- The Dashboard is no longer compressed by the RNG controls.
- RNG settings and per-hunt trigger-lead persistence are unchanged.
- Automatic RNG remains limited to Starter, Gift and Static engines in this experimental build.

v0.20 — FRLG EGG COLLECT / HATCH / NON-SHINY RELEASE (FIRST PASS)
-------------------------------------------------------------------
- Added an Eggs / Breeding hunt category.
- Egg mode reads the live Gen-3 party PK3 data and explicitly identifies an egg via the PK3 egg flag.
- Egg collection starts from a deliberate Four Island Day Care Man checkpoint and presses A through the dialogue until the first empty party slot becomes an egg.
- Egg hatching is controller-only: the bot moves the left stick repeatedly while polling the selected party PK3 until the egg flag clears.
- A hatched Pokémon is passed through the existing read-only PK3/shiny authority. A shiny immediately uses the existing HOME safety hold.
- Added a separate Release Non-Shiny Party Pokémon engine. It is controller-only and uses the FRLG Bill's PC Deposit/Release menus.
- Egg release has an explicit shiny safety check and will never release a shiny PK3.
- The first pass intentionally stops after a non-shiny release. Automatic navigation from the Four Island Day Care back to a PC and back to the Day Care is not yet implemented because that route is map/setup dependent. This is the next refinement rather than a hidden assumption.
- Oak Challenge breeding/egg availability remains gated by the existing Four Island breeding checkbox, so the selected starter stays limited to one catch until breeding is unlocked.

FIRST-PASS EGG SETUP
1. Unlock Four Island breeding and enable "Breeding / egg hatching unlocked" in OAK CHALLENGE.
2. Put compatible parents in the Four Island Day Care and make sure an egg is available from the Day Care Man.
3. Put the player directly in front of the Day Care Man.
4. Leave at least one empty party slot.
5. For the first test, use Max eggs = 1 and Release non-shiny enabled.
6. The hatch movement settings are deliberately conservative and may need tuning to the chosen route. If the character walks into an obstacle, stop the routine and adjust the route/hold values before another unattended test.
7. For the standalone release engine, place the non-shiny Pokémon in the configured party slot and stand directly in front of a Pokémon Center PC. Keep the configured destination box slot empty.

IMPORTANT
The FRLG Day Care is the Four Island two-Pokémon breeding facility; the early Cerulean Day Care cannot perform this two-parent breeding workflow. The first pass therefore assumes the post-Hall-of-Fame Four Island setup.
