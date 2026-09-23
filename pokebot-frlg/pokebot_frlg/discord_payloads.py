from __future__ import annotations
from datetime import datetime, timezone


def safe_int(value, default=0):
    try:
        return int(value)
    except Exception:
        return default


def fmt_elapsed(seconds):
    seconds=max(0,int(float(seconds or 0)))
    h,rem=divmod(seconds,3600); m,s=divmod(rem,60)
    return f"{h:02d}:{m:02d}:{s:02d}"


def build_embed_payload(kind: str, payload: dict) -> tuple[dict, str | None]:
    p=payload or {}; now=datetime.now(timezone.utc).isoformat(); image_path=None
    if kind=="shiny":
        name=p.get("name","Pokémon"); title=f"✨ Shiny {name} found!"; desc="PokebotSwitch-FRLG has paused safely on the Switch HOME menu."; color=0xF7D154
        fields=[
            {"name":"Game","value":str(p.get("game","—")),"inline":True},
            {"name":"Hunt","value":str(p.get("hunt") or p.get("source") or "—"),"inline":True},
            {"name":"Attempt","value":str(p.get("attempt","—")),"inline":True},
            {"name":"Nature","value":str(p.get("nature","—")),"inline":True},
            {"name":"Ability","value":str(p.get("ability_name","—")),"inline":True},
            {"name":"SV","value":str(p.get("shiny_xor","—")),"inline":True},
            {"name":"IVs","value":str(p.get("iv_spread","—")),"inline":False},
            {"name":"PID","value":f"{safe_int(p.get('pid')):08X}","inline":True},
            {"name":"Session","value":f"{safe_int(p.get('session_encounters'))} encounters • {safe_int(p.get('session_shinies'))} shinies","inline":False},
            {"name":"Lifetime","value":f"{safe_int(p.get('lifetime_encounters'))} encounters • {safe_int(p.get('lifetime_shinies'))} shinies","inline":False},
        ]; image_path=p.get("sprite_path")
    elif kind=="hunt_started":
        title="▶ Hunt started"; desc=str(p.get("hunt","FRLG hunt")); color=0x4CAF7D
        fields=[{"name":"Game","value":str(p.get("game","—")),"inline":True},{"name":"Session","value":str(p.get("session_id","—")),"inline":True}]
    elif kind=="hunt_stopped":
        title="■ Hunt stopped"; desc=str(p.get("message") or p.get("hunt") or "Session stopped"); color=0x75839A
        fields=[{"name":"Game","value":str(p.get("game","—")),"inline":True},{"name":"Encounters","value":str(safe_int(p.get("session_encounters"))),"inline":True},{"name":"Shinies","value":str(safe_int(p.get("session_shinies"))),"inline":True},{"name":"Elapsed","value":fmt_elapsed(p.get("elapsed_seconds")),"inline":True}]
    elif kind=="safety_hold":
        title="⚠ FRLG safety hold"; desc=str(p.get("message","Safety hold")); color=0xE49A3A
        fields=[{"name":"Game","value":str(p.get("game","—")),"inline":True},{"name":"Hunt","value":str(p.get("hunt","—")),"inline":True}]
    elif kind=="switch_connected":
        title="✓ Switch connected"; desc=f"{p.get('game','FRLG')} • {p.get('language','—')} • Koi {p.get('botbase','—')}"; color=0x4CAF7D; fields=[]
    elif kind=="test":
        title="✓ PokebotSwitch-FRLG Discord test"; desc="Discord bot notifications are working."; color=0x4DA3FF; fields=[]
    else:
        title="PokebotSwitch-FRLG status"; desc=str(p.get("status","Idle")); color=0x4DA3FF
        fields=[{"name":"Switch","value":"Connected" if p.get("connected") else "Disconnected","inline":True},{"name":"Game","value":str(p.get("game","—")),"inline":True},{"name":"Hunt","value":str(p.get("hunt","—")),"inline":False},{"name":"Session","value":f"{safe_int(p.get('session_encounters'))} encounters • {safe_int(p.get('session_shinies'))} shinies • {fmt_elapsed(p.get('elapsed_seconds'))}","inline":False},{"name":"Lifetime","value":f"{safe_int(p.get('lifetime_encounters'))} encounters • {safe_int(p.get('lifetime_shinies'))} shinies","inline":False}]
    return {"title":title,"description":desc,"color":color,"timestamp":now,"fields":fields,"footer":{"text":"PokebotSwitch-FRLG • Discord is monitoring only"}}, image_path
