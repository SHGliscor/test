from __future__ import annotations

# Professor Oak Challenge data for FireRed / LeafGreen.
# The checklist is deliberately broader than the three early checkpoints:
# it covers the whole Kanto Dex plus the post-game National-Dex species that
# the classic FRLG Oak guide can obtain in a solo run.

STARTER_IDS = (1, 4, 7)

OAK_STAGES = [
    "Pre-Badge 1 — Brock",
    "Pre-Badge 2 — Misty",
    "Pre-Badge 3 — Koga",
    "Pre-Badge 4 — Blaine",
    "Pre-Badge 5 — Erika",
    "Post-Game — Kanto Dex",
    "Post-Game — National Dex",
]

# Exact early sections from the FRLG Oak guide. Later Kanto entries are shown
# in the full checklist and can be manually checked as they are completed.
STAGE_ADDITIONS = {
    OAK_STAGES[0]: [4,5,6,16,17,18,19,20,56,57,21,22,10,11,12,13,14,15,25],
    OAK_STAGES[1]: [29,30,31,32,33,34,39,40,129,130,41,42,74,75,46,47,35,36,23,24,63,64,43,44,52,53,83,96,97,50,51,122],
    OAK_STAGES[2]: [100,101,66,67,95,58,59,133,134,135,136,137,26,84,85,92,93,104,105,143,90,91,116,117,54,55,60,61,62,118,119,98,99,88,89,124,108,132,48,49,147,148,149,111,112,113,123,127,128,115,106,107,131],
    OAK_STAGES[3]: [77,78],
    OAK_STAGES[4]: [144,146],
    OAK_STAGES[5]: [150],
}

# Post-game National-Dex entries obtainable in the classic solo FRLG Oak run.
# The final roaming entry is represented as the version-independent species
# choice 243/244/245 and is displayed as a special row by the UI.
NATIONAL_EXTRA = [
    161,162,165,166,167,168,169,172,173,174,175,176,177,178,
    187,188,189,193,201,360,202,206,214,218,219,220,221,231,232,
    236,237,238,242,246,247,248,182,194,195,198,211,225,227,239,
]

FIRERED_ONLY = {23,24,37,38,52,53,58,59,77,78,83,123,125,127}
LEAFGREEN_ONLY = {27,28,43,44,45,69,70,71,120,121,122,126,136,139,140,141}

# Human-readable evolution requirements. Where an evolution is not relevant
# to the Oak target, the row says Final. This is intentionally descriptive;
# the bot does not automatically level or evolve Pokémon.
EVOLUTION_INFO = {
 1:"Lv.16 → Ivysaur → Lv.32 → Venusaur",2:"Lv.32 → Venusaur",3:"Final",
 4:"Lv.16 → Charmeleon → Lv.36 → Charizard",5:"Lv.36 → Charizard",6:"Final",
 7:"Lv.16 → Wartortle → Lv.36 → Blastoise",8:"Lv.36 → Blastoise",9:"Final",
 10:"Lv.7 → Metapod",11:"Lv.10 → Butterfree",12:"Final",13:"Lv.7 → Kakuna",14:"Lv.10 → Beedrill",15:"Final",
 16:"Lv.18 → Pidgeotto",17:"Lv.36 → Pidgeot",18:"Final",19:"Lv.20 → Raticate",20:"Final",
 21:"Lv.20 → Fearow",22:"Final",23:"Lv.22 → Arbok",24:"Final",25:"Thunder Stone → Raichu",26:"Final",
 27:"Lv.22 → Sandslash",28:"Final",29:"Lv.16 → Nidorina → Moon Stone → Nidoqueen",30:"Moon Stone → Nidoqueen",31:"Final",
 32:"Lv.16 → Nidorino → Moon Stone → Nidoking",33:"Moon Stone → Nidoking",34:"Final",35:"Moon Stone → Clefable",36:"Final",
 37:"Fire Stone → Ninetales",38:"Final",39:"Moon Stone → Wigglytuff",40:"Final",41:"Lv.22 → Golbat",42:"National Dex + happiness → Crobat",
 43:"Lv.21 → Gloom",44:"Leaf Stone → Vileplume / Sun Stone → Bellossom",45:"Leaf Stone → Victreebel",46:"Lv.24 → Parasect",47:"Final",
 48:"Lv.31 → Venomoth",49:"Final",50:"Lv.26 → Dugtrio",51:"Final",52:"Lv.28 → Persian",53:"Final",
 54:"Lv.33 → Golduck",55:"Final",56:"Lv.28 → Primeape",57:"Final",58:"Fire Stone → Arcanine",59:"Final",
 60:"Lv.25 → Poliwhirl",61:"Water Stone → Poliwrath",62:"Final",63:"Lv.16 → Kadabra",64:"Trade → Alakazam",65:"Final",
 66:"Lv.28 → Machoke",67:"Trade → Machamp",68:"Final",69:"Lv.21 → Weepinbell",70:"Leaf Stone → Victreebel",71:"Final",
 72:"Lv.30 → Tentacruel",73:"Final",74:"Lv.25 → Graveler",75:"Trade → Golem",76:"Final",77:"Lv.40 → Rapidash",78:"Final",
 79:"Lv.37 → Slowbro",80:"Final",81:"Lv.30 → Magneton",82:"Final",83:"In-game trade → Farfetch'd",84:"Lv.31 → Dodrio",85:"Final",
 86:"Lv.34 → Dewgong",87:"Final",88:"Lv.35 → Weezing",89:"Final",90:"Water Stone → Cloyster",91:"Final",
 92:"Lv.25 → Haunter",93:"Trade → Gengar",94:"Final",95:"Lv.42 → Rhydon",96:"Final",97:"Final",98:"Lv.30 → Magneton",99:"Final",
 100:"Lv.30 → Electrode",101:"Final",102:"Leaf Stone → Exeggutor",103:"Final",104:"Lv.28 → Marowak",105:"Final",106:"Final",107:"Final",
 108:"Final",109:"Lv.35 → Weezing",110:"Final",111:"Lv.42 → Rhydon",112:"Final",113:"Final",114:"Final",115:"Final",
 116:"Lv.32 → Seadra",117:"Final",118:"Lv.33 → Seaking",119:"Final",120:"Final",121:"Final",122:"Final",123:"Final",
 124:"Final",125:"Final",126:"Final",127:"Final",128:"Final",129:"Lv.20 → Gyarados",130:"Final",131:"Final",
 132:"Variable / catch-and-complete",133:"Fire / Thunder / Water Stone → Flareon / Jolteon / Vaporeon",134:"Final",135:"Final",136:"Final",
 137:"Game Corner prize",138:"Lv.40 → Omastar",139:"Lv.40 → Kabutops",140:"Final",141:"Final",142:"Final",143:"Final",144:"Final",145:"Final",146:"Final",
 147:"Lv.30 → Dragonair → Lv.55 → Dragonite",148:"Lv.55 → Dragonite",149:"Final",150:"Final",151:"Event / not part of solo FRLG PoC",
 161:"Lv.15 → Furret",162:"Final",165:"Lv.18 → Ledian",166:"Final",167:"Lv.22 → Ariados",168:"Final",169:"Final",
 172:"Breed Pikachu/Raichu",173:"Breed Clefairy/Clefable",174:"Breed Jigglypuff/Wigglytuff",175:"Happiness → Togetic",176:"Final",
 177:"Lv.25 → Xatu",178:"Final",182:"Sun Stone → Bellossom",187:"Lv.18 → Skiploom",188:"Lv.27 → Jumpluff",189:"Final",
 193:"Final",194:"Lv.20 → Quagsire",195:"Final",198:"Final",201:"Final",202:"Breed with Lax Incense → Wynaut",206:"Final",
 211:"Final",214:"Final",218:"Lv.38 → Magcargo",219:"Final",220:"Lv.33 → Piloswine",221:"Final",225:"Final",227:"Final",
 231:"Lv.25 → Donphan",232:"Final",236:"Lv.20 → Hitmonlee/Hitmonchan/Hitmontop depending stats",237:"Final",238:"Final",239:"Final",242:"Happiness → Blissey",
 246:"Lv.30 → Pupitar",247:"Lv.55 → Tyranitar",248:"Final",360:"Breed Wobbuffet holding Lax Incense",
}



# Oak catch-count lines. The challenge counts repeated catches of the
# available/base-stage Pokémon toward the later evolution entries. For example,
# Pidgey -> Pidgeotto -> Pidgeot is a 3-catch line: catch #1 completes Pidgey,
# catch #2 completes Pidgeotto, and catch #3 completes Pidgeot. Only then is
# the whole line blocked. The first member is the species the bot should hunt
# when the line is selected automatically.
OAK_EVOLUTION_LINES = [
    (1,2,3), (4,5,6), (7,8,9), (16,17,18), (19,20), (21,22), (23,24), (25,26,172),
    (10,11,12), (13,14,15), (29,30,31), (32,33,34), (35,36,173),
    (37,38), (39,40,174), (41,42,169), (43,44,45,182), (46,47),
    (48,49), (50,51), (52,53), (54,55), (56,57), (58,59),
    (60,61,62), (63,64,65), (66,67,68), (69,70,71), (72,73),
    (74,75,76), (77,78), (79,80), (81,82), (83,), (84,85), (86,87),
    (88,89), (90,91), (92,93,94), (95,96), (97,98), (99,100),
    (101,102), (103,104), (105,), (106,), (107,), (108,109),
    (110,111), (112,), (113,), (114,), (115,116), (117,118),
    (119,120), (121,), (122,), (123,), (124,), (125,), (126,), (127,),
    (128,129), (130,), (131,), (132,133,134,135), (136,), (137,138),
    (139,140), (141,), (142,), (143,), (144,), (145,), (146,147,148),
    (149,), (150,), (161,162), (165,166), (167,168), (175,176),
    (177,178), (187,188,189), (193,), (194,195), (198,), (201,),
    (202,360), (206,), (211,), (214,), (218,219), (220,221),
    (225,), (227,), (231,232), (236,237), (238,), (239,), (242,),
    (246,247,248),
]

OAK_LINE_BY_SPECIES = {sid: line for line in OAK_EVOLUTION_LINES for sid in line}

def oak_line_for_species(species_id: int) -> tuple[int, ...]:
    return OAK_LINE_BY_SPECIES.get(int(species_id), (int(species_id),))

def oak_line_target(species_id: int) -> int:
    return oak_line_for_species(species_id)[0]

def oak_line_required(species_id: int) -> int:
    return len(oak_line_for_species(species_id))


def stage_species(stage: str, game: str | None = None) -> list[int]:
    ids = list(dict.fromkeys(STAGE_ADDITIONS.get(stage, [])))
    if game == "FireRed":
        ids = [x for x in ids if x not in LEAFGREEN_ONLY]
    elif game == "LeafGreen":
        ids = [x for x in ids if x not in FIRERED_ONLY]
    return ids


def oak_starter_line(starter_species: int | None) -> tuple[int, ...]:
    """Return the selected starter evolution line, or an empty tuple."""
    try:
        sid = int(starter_species)
    except (TypeError, ValueError):
        return ()
    if sid not in STARTER_IDS:
        return ()
    return OAK_LINE_BY_SPECIES.get(sid, (sid,))


def oak_starter_available_catches(starter_species: int | None, breeding_unlocked: bool) -> int:
    """Before Four Island breeding is unlocked, only the original starter exists.

    Once breeding/egg hatching is unlocked, the selected starter line can use its
    normal evolution-line catch count.
    """
    line = oak_starter_line(starter_species)
    if not line:
        return 0
    return len(line) if breeding_unlocked else 1


def all_checklist_ids(game: str | None = None) -> list[int]:
    out=[]
    for stage in OAK_STAGES:
        for sid in stage_species(stage, game):
            if sid not in out: out.append(sid)
    for sid in NATIONAL_EXTRA:
        if sid not in out and not ((game == "FireRed" and sid in LEAFGREEN_ONLY) or (game == "LeafGreen" and sid in FIRERED_ONLY)):
            out.append(sid)
    return out


def evolution_info(species_id: int) -> str:
    return EVOLUTION_INFO.get(int(species_id), "Final / no further evolution in this checklist")
