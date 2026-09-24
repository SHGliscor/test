from __future__ import annotations
from dataclasses import dataclass, asdict

ORDERS = (
    "GAEM", "GAME", "GEAM", "GEMA", "GMAE", "GMEA",
    "AGEM", "AGME", "AEGM", "AEMG", "AMGE", "AMEG",
    "EGAM", "EGMA", "EAGM", "EAMG", "EMGA", "EMAG",
    "MGAE", "MGEA", "MAGE", "MAEG", "MEGA", "MEAG",
)
NATURES = (
    "Hardy", "Lonely", "Brave", "Adamant", "Naughty",
    "Bold", "Docile", "Relaxed", "Impish", "Lax",
    "Timid", "Hasty", "Serious", "Jolly", "Naive",
    "Modest", "Mild", "Quiet", "Bashful", "Rash",
    "Calm", "Gentle", "Sassy", "Careful", "Quirky",
)

# Complete Kanto names plus the most useful FRLG post-game/event species. Unknown
# National Dex species gracefully render as "Species #" until we add the full DB.
_KANTO = """Bulbasaur Ivysaur Venusaur Charmander Charmeleon Charizard Squirtle Wartortle Blastoise Caterpie Metapod Butterfree Weedle Kakuna Beedrill Pidgey Pidgeotto Pidgeot Rattata Raticate Spearow Fearow Ekans Arbok Pikachu Raichu Sandshrew Sandslash Nidoran♀ Nidorina Nidoqueen Nidoran♂ Nidorino Nidoking Clefairy Clefable Vulpix Ninetales Jigglypuff Wigglytuff Zubat Golbat Oddish Gloom Vileplume Paras Parasect Venonat Venomoth Diglett Dugtrio Meowth Persian Psyduck Golduck Mankey Primeape Growlithe Arcanine Poliwag Poliwhirl Poliwrath Abra Kadabra Alakazam Machop Machoke Machamp Bellsprout Weepinbell Victreebel Tentacool Tentacruel Geodude Graveler Golem Ponyta Rapidash Slowpoke Slowbro Magnemite Magneton Farfetch'd Doduo Dodrio Seel Dewgong Grimer Muk Shellder Cloyster Gastly Haunter Gengar Drowzee Hypno Krabby Kingler Voltorb Electrode Exeggcute Exeggutor Cubone Marowak Hitmonlee Hitmonchan Lickitung Koffing Weezing Rhyhorn Rhydon Chansey Tangela Kangaskhan Horsea Seadra Goldeen Seaking Staryu Starmie Mr.Mime Scyther Jynx Electabuzz Magmar Pinsir Tauros Magikarp Gyarados Lapras Ditto Eevee Vaporeon Jolteon Flareon Porygon Omanyte Omastar Kabuto Kabutops Aerodactyl Snorlax Articuno Zapdos Moltres Dratini Dragonair Dragonite Mewtwo Mew""".split()
SPECIES_NAMES = {i + 1: n for i, n in enumerate(_KANTO)}
SPECIES_NAMES.update({169:"Crobat",172:"Pichu",173:"Cleffa",174:"Igglybuff",182:"Bellossom",186:"Politoed",196:"Espeon",197:"Umbreon",199:"Slowking",208:"Steelix",212:"Scizor",230:"Kingdra",233:"Porygon2",238:"Smoochum",239:"Elekid",240:"Magby",242:"Blissey",243:"Raikou",244:"Entei",245:"Suicune",249:"Lugia",250:"Ho-Oh",251:"Celebi",252:"Treecko",255:"Torchic",258:"Mudkip",280:"Ralts",283:"Surskit",285:"Shroomish",302:"Sableye",303:"Mawile",304:"Aron",309:"Electrike",315:"Roselia",327:"Spinda",349:"Feebas",350:"Milotic",359:"Absol",371:"Bagon",374:"Beldum",377:"Regirock",378:"Regice",379:"Registeel",380:"Latias",381:"Latios",382:"Kyogre",383:"Groudon",384:"Rayquaza",385:"Jirachi",386:"Deoxys"})


def species_name(species: int) -> str:
    return SPECIES_NAMES.get(species, f"Species {species}")

@dataclass
class PK3Summary:
    valid: bool; checksum_ok: bool; pid: int; tid: int; sid: int; shiny: bool; shiny_xor: int
    species: int; held_item: int; experience: int; friendship: int; nature: str; ability_slot: int
    is_egg: bool; pokerus: int; iv_hp: int; iv_atk: int; iv_def: int; iv_spe: int; iv_spa: int; iv_spd: int
    ev_hp: int; ev_atk: int; ev_def: int; ev_spe: int; ev_spa: int; ev_spd: int
    move1: int; move2: int; move3: int; move4: int; move1_pp: int; move2_pp: int; move3_pp: int; move4_pp: int; raw_hex: str

    @property
    def iv_sum(self) -> int:
        return self.iv_hp + self.iv_atk + self.iv_def + self.iv_spa + self.iv_spd + self.iv_spe

    @property
    def iv_spread(self) -> str:
        return f"{self.iv_hp}/{self.iv_atk}/{self.iv_def}/{self.iv_spa}/{self.iv_spd}/{self.iv_spe}"

    @property
    def ev_spread(self) -> str:
        return f"{self.ev_hp}/{self.ev_atk}/{self.ev_def}/{self.ev_spa}/{self.ev_spd}/{self.ev_spe}"

    @property
    def name(self) -> str:
        return species_name(self.species)

    def to_dict(self):
        d = asdict(self); d["iv_sum"] = self.iv_sum; d["iv_spread"] = self.iv_spread; d["ev_spread"] = self.ev_spread; d["name"] = self.name
        return d

def _u16(b: bytes, o: int) -> int: return int.from_bytes(b[o:o+2], "little")
def _u32(b: bytes, o: int) -> int: return int.from_bytes(b[o:o+4], "little")

def parse_pk3(raw: bytes) -> PK3Summary:
    if len(raw) < 0x50: raise ValueError("PK3 box data must be at least 0x50 bytes")
    raw = raw[:0x50]; pid = _u32(raw,0); otid = _u32(raw,4); tid=otid&0xFFFF; sid=(otid>>16)&0xFFFF; stored=_u16(raw,0x1C)
    encrypted=raw[0x20:0x50]; key=pid^otid; dec=bytearray(0x30)
    for i in range(0,0x30,4): dec[i:i+4]=(_u32(encrypted,i)^key).to_bytes(4,"little")
    calc=sum(_u16(dec,i) for i in range(0,0x30,2))&0xFFFF; checksum_ok=stored==calc
    order=ORDERS[pid%24]; blocks={letter:bytes(dec[idx*12:(idx+1)*12]) for idx,letter in enumerate(order)}
    growth, attacks, evs, misc = blocks["G"], blocks["A"], blocks["E"], blocks["M"]
    species=_u16(growth,0); held=_u16(growth,2); exp=_u32(growth,4); friendship=growth[9]
    moves=(_u16(attacks,0),_u16(attacks,2),_u16(attacks,4),_u16(attacks,6)); pps=(attacks[8],attacks[9],attacks[10],attacks[11])
    ev_hp,ev_atk,ev_def,ev_spe,ev_spa,ev_spd=evs[:6]
    pokerus=misc[0]; iv_word=_u32(misc,4)
    iv_hp=(iv_word>>0)&31; iv_atk=(iv_word>>5)&31; iv_def=(iv_word>>10)&31; iv_spe=(iv_word>>15)&31; iv_spa=(iv_word>>20)&31; iv_spd=(iv_word>>25)&31
    is_egg=bool((iv_word>>30)&1); ability_slot=2 if ((iv_word>>31)&1) else 1
    shiny_xor=tid^sid^(pid&0xFFFF)^(pid>>16); shiny=shiny_xor<8; nature=NATURES[pid%25]
    valid=pid!=0 and species!=0 and checksum_ok
    return PK3Summary(valid,checksum_ok,pid,tid,sid,shiny,shiny_xor,species,held,exp,friendship,nature,ability_slot,is_egg,pokerus,
        iv_hp,iv_atk,iv_def,iv_spe,iv_spa,iv_spd,ev_hp,ev_atk,ev_def,ev_spe,ev_spa,ev_spd,*moves,*pps,raw.hex().upper())
