from __future__ import annotations
import json, os, tempfile
from copy import deepcopy
from datetime import datetime
from pathlib import Path

APPDATA_FOLDER = "PokebotSwitch-FRLG"

def appdata_root() -> Path:
    base = Path(os.environ.get("APPDATA") or (Path.home() / ".config"))
    p = base / APPDATA_FOLDER
    # Keep AppData quiet during normal operation. Diagnostic/support folders are
    # created lazily only when a real failure needs a support package.
    for sub in ("cache", "cache/sprites"):
        (p / sub).mkdir(parents=True, exist_ok=True)
    return p

def _atomic_json(path: Path, payload: dict):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=path.name, suffix=".tmp", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2)
        os.replace(tmp, path)
    finally:
        try:
            if os.path.exists(tmp): os.unlink(tmp)
        except OSError: pass

def _read(path: Path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return deepcopy(default)

class AppDataStore:
    def __init__(self):
        self.root = appdata_root(); self.stats_path=self.root/"stats.json"; self.session_path=self.root/"session_current.json"; self.settings_path=self.root/"settings.json"
        self._lifetime_default={"version":1,"total_encounters":0,"total_shinies":0}
        self.lifetime=_read(self.stats_path,self._lifetime_default)
        self.session=_read(self.session_path,{})
        self.save_lifetime()

    def save_lifetime(self): _atomic_json(self.stats_path,self.lifetime)
    def save_session(self): _atomic_json(self.session_path,self.session)

    def new_session(self, mode="Starter", target="Charmander"):
        sid=datetime.now().strftime("%Y%m%d_%H%M%S")
        self.session={
            "version":1,"session_id":sid,"started_at":datetime.now().isoformat(timespec="seconds"),"ended_at":None,"active":True,
            "mode":mode,"target":target,"encounters":0,"shinies":0,"elapsed_seconds":0.0,
            "recent_seen":[],"cycle":{"iv_sum_high":None,"iv_sum_low":None,"iv_high_spread":None,"iv_low_spread":None,"sv_high":None,"sv_low":None}
        }
        self.save_session(); return deepcopy(self.session)

    def update_elapsed(self, seconds: float):
        if self.session:
            self.session["elapsed_seconds"]=round(max(0.0,float(seconds)),3); self.save_session()

    def stop_session(self, elapsed_seconds: float):
        if not self.session: return
        self.session["elapsed_seconds"]=round(max(0.0,float(elapsed_seconds)),3); self.session["active"]=False; self.session["ended_at"]=datetime.now().isoformat(timespec="seconds")
        # session_current.json is the single persistent session snapshot.
        # Do not create timestamped JSON archives for routine successful stops.
        self.save_session()

    def record_encounter(self, pk: dict, elapsed_seconds: float):
        if not self.session: self.new_session()
        self.session["encounters"]+=1; self.lifetime["total_encounters"]+=1
        if pk.get("shiny"):
            self.session["shinies"]+=1; self.lifetime["total_shinies"]+=1
        self.session["elapsed_seconds"]=round(max(0.0,float(elapsed_seconds)),3)
        row={k:pk.get(k) for k in ("name","species","pid","nature","shiny","shiny_xor","iv_hp","iv_atk","iv_def","iv_spa","iv_spd","iv_spe","iv_sum","iv_spread","ability_slot","ability_name","pokerus","sprite_path","source","attempt","rng_method","rng_supported","rng_validated","rng_capture_seed","rng_generation_seed","rng_generation_to_capture","rng_previous_shiny","rng_next_shiny","rng_miss")}
        row["seen_at"]=datetime.now().isoformat(timespec="seconds")
        self.session.setdefault("recent_seen",[]).insert(0,row); self.session["recent_seen"]=self.session["recent_seen"][:7]
        cycle=self.session.setdefault("cycle",{})
        ivsum=pk.get("iv_sum"); sv=pk.get("shiny_xor")
        if ivsum is not None:
            if cycle.get("iv_sum_high") is None or ivsum>cycle["iv_sum_high"]: cycle["iv_sum_high"]=ivsum; cycle["iv_high_spread"]=pk.get("iv_spread")
            if cycle.get("iv_sum_low") is None or ivsum<cycle["iv_sum_low"]: cycle["iv_sum_low"]=ivsum; cycle["iv_low_spread"]=pk.get("iv_spread")
        if sv is not None:
            if cycle.get("sv_high") is None or sv>cycle["sv_high"]: cycle["sv_high"]=sv
            if cycle.get("sv_low") is None or sv<cycle["sv_low"]: cycle["sv_low"]=sv
        # Required behavior: a shiny starts a brand-new IV/SV rolling cycle, while
        # session encounter/shiny counters and lifetime totals continue unchanged.
        if pk.get("shiny"):
            self.session["cycle"]={"iv_sum_high":None,"iv_sum_low":None,"iv_high_spread":None,"iv_low_spread":None,"sv_high":None,"sv_low":None}
        self.save_lifetime(); self.save_session(); return deepcopy(self.session),deepcopy(self.lifetime)

    def load_settings(self):
        return _read(self.settings_path,{"switch_ip":"192.168.1.162","port":6000,"monitor_interval":0.75,"always_on_top":False,"last_hunt":"starter_charmander","game_corner_number":1,"discord_bot_enabled":False,"discord_bot_token":"","discord_channel_id":"","discord_notify_status":True,"discord_notify_safety":True,"discord_rich_presence_enabled":False,"discord_rpc_client_id":""})
    def save_settings(self, settings: dict): _atomic_json(self.settings_path,settings)
