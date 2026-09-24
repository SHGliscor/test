from __future__ import annotations
from dataclasses import dataclass

@dataclass(frozen=True)
class HuntDefinition:
    key: str
    group: str
    label: str
    engine: str
    species: int | None = None
    games: tuple[str, ...] = ("FireRed", "LeafGreen")
    setup: str = ""
    special: str = ""

HUNTS = [
    HuntDefinition("starter_bulbasaur","Starters","Bulbasaur","starter",1,setup="Save in Oak's Lab facing Bulbasaur's Poké Ball with an empty party."),
    HuntDefinition("starter_charmander","Starters","Charmander","starter",4,setup="Save in Oak's Lab facing Charmander's Poké Ball with an empty party."),
    HuntDefinition("starter_squirtle","Starters","Squirtle","starter",7,setup="Save in Oak's Lab facing Squirtle's Poké Ball with an empty party."),

    HuntDefinition("gift_magikarp","Gifts / Fossils","Magikarp — Route 4 salesman","gift",129,setup="Have at least ₽500 and save facing the Magikarp salesman before buying."),
    HuntDefinition("gift_hitmonlee","Gifts / Fossils","Hitmonlee — Fighting Dojo","gift",106,setup="Defeat the Karate Master, then save facing Hitmonlee's Poké Ball."),
    HuntDefinition("gift_hitmonchan","Gifts / Fossils","Hitmonchan — Fighting Dojo","gift",107,setup="Defeat the Karate Master, then save facing Hitmonchan's Poké Ball."),
    HuntDefinition("gift_eevee","Gifts / Fossils","Eevee — Celadon Mansion","gift",133,setup="Save facing Eevee's Poké Ball on the Celadon Mansion rooftop room."),
    HuntDefinition("gift_lapras","Gifts / Fossils","Lapras — Silph Co.","gift",131,setup="Save facing the Silph Co. employee who gives Lapras."),
    HuntDefinition("gift_togepi","Gifts / Fossils","Togepi Egg — Water Labyrinth","gift",175,setup="Save facing the old man before receiving the Togepi Egg. The bot checks the egg PK3 directly; no hatch is required."),
    HuntDefinition("fossil_omanyte","Gifts / Fossils","Omanyte — Helix Fossil revival","gift",138,setup="Give the Helix Fossil to the Cinnabar scientist, leave/re-enter, then save next to the scientist before collection."),
    HuntDefinition("fossil_kabuto","Gifts / Fossils","Kabuto — Dome Fossil revival","gift",140,setup="Give the Dome Fossil to the Cinnabar scientist, leave/re-enter, then save next to the scientist before collection."),
    HuntDefinition("fossil_aerodactyl","Gifts / Fossils","Aerodactyl — Old Amber revival","gift",142,setup="Give Old Amber to the Cinnabar scientist, leave/re-enter, then save next to the scientist before collection."),
    HuntDefinition("gift_custom","Gifts / Fossils","Custom gift (next empty party slot)","gift",None,setup="Save immediately before receiving a Pokémon into the next empty party slot."),

    HuntDefinition("gc_abra","Game Corner","Abra","game_corner",63),
    HuntDefinition("gc_clefairy","Game Corner","Clefairy","game_corner",35),
    HuntDefinition("gc_dratini","Game Corner","Dratini","game_corner",147),
    HuntDefinition("gc_scyther","Game Corner","Scyther — FireRed","game_corner",123,("FireRed",)),
    HuntDefinition("gc_pinsir","Game Corner","Pinsir — LeafGreen","game_corner",127,("LeafGreen",)),
    HuntDefinition("gc_porygon","Game Corner","Porygon","game_corner",137),

    HuntDefinition("static_snorlax","Static / Legendary","Snorlax — Route 12 / 16","static",143,setup="Save directly in front of the sleeping Snorlax before waking it."),
    HuntDefinition("static_electrode","Static / Legendary","Electrode — Power Plant","static",101,setup="Save directly in front of the Electrode disguised as an item."),
    HuntDefinition("static_hypno","Static / Legendary","Hypno — Berry Forest","static",97,setup="Save immediately before the scripted Hypno encounter with Lostelle."),
    HuntDefinition("static_articuno","Static / Legendary","Articuno — Seafoam Islands","static",144,setup="Save directly in front of Articuno."),
    HuntDefinition("static_zapdos","Static / Legendary","Zapdos — Power Plant","static",145,setup="Save directly in front of Zapdos."),
    HuntDefinition("static_moltres","Static / Legendary","Moltres — Mt. Ember","static",146,setup="Save directly in front of Moltres."),
    HuntDefinition("static_mewtwo","Static / Legendary","Mewtwo — Cerulean Cave","static",150,setup="Save directly in front of Mewtwo."),
    HuntDefinition("static_lugia","Static / Legendary","Lugia — Navel Rock","static",249,setup="Save directly in front of Lugia."),
    HuntDefinition("static_hooh","Static / Legendary","Ho-Oh — Navel Rock","static_hooh",250,setup="Stand one floor tile before Ho-Oh descends, face Up, then save. This hunt uses Up rather than A."),
    HuntDefinition("static_deoxys","Static / Legendary","Deoxys — Birth Island","static",386,setup="Complete the triangle puzzle to the final red triangle, then save before the final interaction."),
    HuntDefinition("static_custom","Static / Legendary","Custom static encounter","static",None,setup="Save facing the static Pokémon/object. The bot presses A until the wild PK3 appears."),

    HuntDefinition("roamer_raikou","Roaming Beasts","Raikou","roamer",243,setup="Save before the event that releases the roaming beast. The source routine advances the event, reads the roamer save block, and resets if not shiny."),
    HuntDefinition("roamer_entei","Roaming Beasts","Entei","roamer",244,setup="Save before the event that releases the roaming beast. The source routine advances the event, reads the roamer save block, and resets if not shiny."),
    HuntDefinition("roamer_suicune","Roaming Beasts","Suicune","roamer",245,setup="Save before the event that releases the roaming beast. The source routine advances the event, reads the roamer save block, and resets if not shiny."),

    HuntDefinition("wild_slots","Wild","Grass / Cave / Surf encounters","wild",None,setup="Stand on encounter-capable terrain facing Up/Down. The bot alternates horizontal/vertical wiggles and RAM-checks each battle."),
    HuntDefinition("auto_capture_test","Wild","AUTO CAPTURE TEST — first non-shiny","auto_capture_test",None,setup="Stand on encounter-capable terrain with at least one empty party slot and Poké Balls available. The bot catches the first non-shiny encounter, verifies it in the party, then stops."),
    HuntDefinition("oak_wild","Oak Challenge","Oak Challenge — filtered wild encounters","oak_wild",None,setup="Use the OAK CHALLENGE tab to select the current required species and block completed/unwanted species. The bot stops on a non-blocked target encounter so you can catch it; blocked encounters are escaped automatically."),
    HuntDefinition("wild_fishing","Wild","Fishing encounters","fishing",None,setup="Register the desired fishing rod to Y/Select and stand facing fishable water."),

    HuntDefinition("pickup","Utility Hunts","Pickup farming + shiny check","pickup",None,setup="Expert/source-compatible setup: lead uses Move 1 to KO; party contains Pickup Pokémon. The routine checks every wild PK3 for shiny before KO/item collection."),

    HuntDefinition("egg_breeding","Eggs / Breeding","FRLG Egg Collect → Hatch → Release","egg_breeding",None,setup="Four Island Day Care unlocked. Stand facing the Day Care Man. Leave at least one empty party slot for the egg. Use the Egg settings to control the hatch cycle and optional non-shiny release checkpoint.",special="Breeding/egg hatching is only available after the Four Island Day Care is unlocked."),
    HuntDefinition("egg_release","Eggs / Breeding","Release Non-Shiny Party Pokémon","egg_release",None,setup="Stand directly in front of a Pokémon Center PC with the non-shiny Pokémon in the selected party slot. The bot deposits it into a configured box slot and uses Release from Bill's PC."),
]

BY_KEY = {h.key: h for h in HUNTS}
GROUPS: dict[str, list[HuntDefinition]] = {}
for h in HUNTS:
    GROUPS.setdefault(h.group, []).append(h)

def available_for_game(game: str | None):
    if not game:
        return list(HUNTS)
    return [h for h in HUNTS if game in h.games]
