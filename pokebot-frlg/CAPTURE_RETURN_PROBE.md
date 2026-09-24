# FRLG Capture Return Probe

Standalone diagnostic for Switch FireRed/LeafGreen 1.0.0.

This build is intentionally separate from the normal FRLG bot.

## RAM-first discovery

- verifies FRLG title/version;
- starts while the capture result is active;
- samples IN_BATTLE, BATTLE_MENU, overworld state, RNG seed, party-slot fingerprints and Pokédex ownership;
- records RAM transitions;
- detects the battle/capture completion transition;
- detects a new Pokédex owned-bit transition when a species ID is supplied;
- requires consecutive overworld confirmations;
- never sends blind A/B input;
- neutralizes and detaches the controller on exit;
- writes a JSON trace.

## Run

    run_capture_return_probe.bat SWITCH_IP SPECIES_ID

Example:

    run_capture_return_probe.bat 192.168.1.50 25

Or:

    python capture_return_probe.py 192.168.1.50 --species 25 --json trace.json

## First hardware run

Start the probe while the capture result is still active and IN_BATTLE is 0x02.

This first build deliberately does not automatically select the nickname answer. We need the real Switch RAM trace to identify the nickname prompt state before allowing the probe to send input.

After that RAM fingerprint is confirmed, the next build will add:

capture -> capture complete -> Pokedex -> nickname prompt -> YES/NO decision -> nickname entry -> return -> overworld confirmation.

The existing Koi botbase transport supports RAM reads and controller commands.
