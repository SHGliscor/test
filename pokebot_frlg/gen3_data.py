from __future__ import annotations
import csv, io, json, re, urllib.request
from pathlib import Path
from .appdata_store import appdata_root

ABILITY_NAMES = {
1:"Stench",2:"Drizzle",3:"Speed Boost",4:"Battle Armor",5:"Sturdy",6:"Damp",7:"Limber",8:"Sand Veil",9:"Static",10:"Volt Absorb",11:"Water Absorb",12:"Oblivious",13:"Cloud Nine",14:"Compound Eyes",15:"Insomnia",16:"Color Change",17:"Immunity",18:"Flash Fire",19:"Shield Dust",20:"Own Tempo",21:"Suction Cups",22:"Intimidate",23:"Shadow Tag",24:"Rough Skin",25:"Wonder Guard",26:"Levitate",27:"Effect Spore",28:"Synchronize",29:"Clear Body",30:"Natural Cure",31:"Lightning Rod",32:"Serene Grace",33:"Swift Swim",34:"Chlorophyll",35:"Illuminate",36:"Trace",37:"Huge Power",38:"Poison Point",39:"Inner Focus",40:"Magma Armor",41:"Water Veil",42:"Magnet Pull",43:"Soundproof",44:"Rain Dish",45:"Sand Stream",46:"Pressure",47:"Thick Fat",48:"Early Bird",49:"Flame Body",50:"Run Away",51:"Keen Eye",52:"Hyper Cutter",53:"Pickup",54:"Truant",55:"Hustle",56:"Cute Charm",57:"Plus",58:"Minus",59:"Forecast",60:"Sticky Hold",61:"Shed Skin",62:"Guts",63:"Marvel Scale",64:"Liquid Ooze",65:"Overgrow",66:"Blaze",67:"Torrent",68:"Swarm",69:"Rock Head",70:"Drought",71:"Arena Trap",72:"Vital Spirit",73:"White Smoke",74:"Pure Power",75:"Shell Armor",76:"Air Lock",
}

# Offline fallback for the named FRLG hunts. Full Gen-3 mapping is cached from
# PokeAPI CSV data when Internet access is available.
FALLBACK = {
1:(65,None),4:(66,None),7:(67,None),35:(56,None),63:(28,39),97:(15,None),101:(43,9),106:(7,None),107:(51,None),123:(68,None),127:(52,None),129:(33,None),131:(11,75),133:(50,None),137:(36,None),138:(33,75),140:(33,4),142:(69,46),143:(17,47),144:(46,None),145:(46,None),146:(46,None),147:(61,None),150:(46,None),175:(55,32),243:(46,None),244:(46,None),245:(46,None),249:(46,None),250:(46,None),386:(46,None),
}

BASE = "https://raw.githubusercontent.com/PokeAPI/pokeapi/master/data/v2/csv/"
SPRITE_BASE = "https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/versions/generation-iii/firered-leafgreen/"

# A transient sprite download used to create a permanent *.failed marker, which
# could leave otherwise valid species (for example Staryu #120) blank forever.
# Keep failures in memory only and retry later; also clean old poison markers.
_SPRITE_FAIL_UNTIL: dict[tuple[int,bool], float] = {}
_LEGACY_FAIL_CLEANED = False

def _cleanup_legacy_sprite_fail_markers():
    global _LEGACY_FAIL_CLEANED
    if _LEGACY_FAIL_CLEANED:
        return
    d=appdata_root()/"cache"/"sprites"
    d.mkdir(parents=True,exist_ok=True)
    for f in d.glob("*.failed"):
        try: f.unlink()
        except OSError: pass
    _LEGACY_FAIL_CLEANED=True

def get_sprite_path(species:int, shiny:bool, timeout:float=3.0) -> str:
    import time as _time
    species=int(species or 0); shiny=bool(shiny)
    if species<=0 or species>386:
        return ""
    _cleanup_legacy_sprite_fail_markers()
    d=appdata_root()/"cache"/"sprites"; d.mkdir(parents=True,exist_ok=True)
    kind="shiny" if shiny else "normal"
    p=d/f"{species}_{kind}.png"
    if p.exists() and p.stat().st_size>50:
        return str(p)
    key=(species,shiny); now=_time.monotonic()
    if now < _SPRITE_FAIL_UNTIL.get(key,0):
        return ""
    rel=("shiny/" if shiny else "")+f"{species}.png"
    try:
        req=urllib.request.Request(SPRITE_BASE+rel,headers={"User-Agent":"PokebotSwitch-FRLG/0.12"})
        with urllib.request.urlopen(req,timeout=timeout) as r:
            data=r.read()
        if data.startswith(b"\x89PNG"):
            p.write_bytes(data); _SPRITE_FAIL_UNTIL.pop(key,None); return str(p)
    except Exception:
        pass
    _SPRITE_FAIL_UNTIL[key]=now+30.0
    return ""

class Gen3DataCache:
    def __init__(self):
        self.root = appdata_root()/"cache"
        self.map_path = self.root/"gen3_abilities.json"
        self.names_path = self.root/"gen3_species_names.json"
        self.sprite_dir = self.root/"sprites"
        self.sprite_dir.mkdir(parents=True, exist_ok=True)
        self._abilities: dict[str, list[int|None]] = {}
        self._names: dict[str,str] = {}
        self._load_or_build()
        self._load_names()

    def _download_text(self, name: str, timeout=1.5) -> str:
        req=urllib.request.Request(BASE+name,headers={"User-Agent":"PokebotSwitch-FRLG/0.6"})
        with urllib.request.urlopen(req,timeout=timeout) as r:
            return r.read().decode("utf-8")

    def _load_or_build(self):
        try:
            raw=json.loads(self.map_path.read_text(encoding="utf-8"))
            self._abilities={str(k):v for k,v in raw.items()}
            if self._abilities: return
        except Exception: pass
        try:
            current=self._download_text("pokemon_abilities.csv")
            past=self._download_text("pokemon_abilities_past.csv")
            abilities=self._download_text("abilities.csv")
            names={int(r["id"]): self._pretty(r["identifier"]) for r in csv.DictReader(io.StringIO(abilities)) if r.get("id") and r.get("identifier")}
            ABILITY_NAMES.update({k:v for k,v in names.items() if k<=76})
            cur: dict[tuple[int,int], int|None]={}
            for r in csv.DictReader(io.StringIO(current)):
                sp=int(r["pokemon_id"]); slot=int(r["slot"]); hidden=int(r["is_hidden"])
                if sp<=386 and slot in (1,2) and not hidden: cur[(sp,slot)]=int(r["ability_id"])
            history: dict[tuple[int,int], list[tuple[int,int|None]]]={}
            for r in csv.DictReader(io.StringIO(past)):
                sp=int(r["pokemon_id"]); gen=int(r["generation_id"]); slot=int(r["slot"]); hidden=int(r["is_hidden"])
                if sp<=386 and slot in (1,2) and not hidden and gen>=3:
                    aid=int(r["ability_id"]) if r.get("ability_id") else None
                    history.setdefault((sp,slot),[]).append((gen,aid))
            out={}
            for sp in range(1,387):
                vals=[]
                for slot in (1,2):
                    hist=history.get((sp,slot),[])
                    aid=min(hist,key=lambda x:x[0])[1] if hist else cur.get((sp,slot))
                    vals.append(aid)
                out[str(sp)]=vals
            self._abilities=out
            self.map_path.write_text(json.dumps(out,separators=(",",":")),encoding="utf-8")
        except Exception:
            self._abilities={str(k):list(v) for k,v in FALLBACK.items()}

    @staticmethod
    def _pretty(identifier: str) -> str:
        return " ".join(x.capitalize() for x in identifier.replace("-"," ").split())


    def _load_names(self):
        try:
            raw=json.loads(self.names_path.read_text(encoding="utf-8")); self._names={str(k):str(v) for k,v in raw.items()}
            if self._names: return
        except Exception: pass
        try:
            text=self._download_text("pokemon_species.csv")
            out={}
            for r in csv.DictReader(io.StringIO(text)):
                sid=int(r["id"]);
                if sid>386: continue
                ident=r["identifier"]
                special={"nidoran-f":"Nidoran♀","nidoran-m":"Nidoran♂","mr-mime":"Mr. Mime","farfetchd":"Farfetch'd","ho-oh":"Ho-Oh"}
                out[str(sid)]=special.get(ident," ".join(x.capitalize() for x in ident.split("-")))
            self._names=out; self.names_path.write_text(json.dumps(out,separators=(",",":"),ensure_ascii=False),encoding="utf-8")
        except Exception:
            self._names={}

    def species_name(self, species:int, fallback:str="") -> str:
        return self._names.get(str(int(species)), fallback or f"Species {species}")

    def ability_name(self, species: int, slot: int) -> str:
        vals=self._abilities.get(str(int(species))) or list(FALLBACK.get(int(species),(None,None)))
        idx=0 if int(slot)==1 else 1
        aid=vals[idx] if idx<len(vals) else None
        if aid is None:
            # In Gen 3, the ability bit can still be set on species with one ability.
            aid=vals[0] if vals else None
        return ABILITY_NAMES.get(aid, f"Ability slot {slot}") if aid else f"Ability slot {slot}"

    def sprite_path(self, species: int, shiny: bool) -> str:
        return get_sprite_path(species, shiny)

    def enrich(self, d: dict) -> dict:
        if not d or not d.get("valid"): return d
        d=dict(d)
        d["name"]=self.species_name(d.get("species",0),d.get("name","") or "")
        d["ability_name"]=self.ability_name(d.get("species",0),d.get("ability_slot",1))
        d["sprite_path"]=self.sprite_path(d.get("species",0),bool(d.get("shiny")))
        return d
