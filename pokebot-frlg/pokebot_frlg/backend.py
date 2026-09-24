from __future__ import annotations
import queue, threading, time, traceback, json, zipfile, random
from datetime import datetime
from PySide6.QtCore import QThread, Signal
from .offsets import (BATTLE_MENU, BOX_FORMAT_SLOT_SIZE, FRLG_GAME_VERSION, IN_BATTLE,
                      PARTY_SLOT_STRIDE, INITIAL_SEED, LARGE_SHIFT, SMALL_SHIFT, lookup)
from .pk3 import parse_pk3, species_name, NATURES
from .wifi_botbase import WiFiBotbase
from .appdata_store import appdata_root
from .gen3_data import Gen3DataCache
from .hunt_catalog import BY_KEY
from .rng import (miss_from_capture, roamer_miss_from_capture, find_method1_target,
                  forward_distance_limited, nearby_signed_distance)

GBA_SAVE_BASE = 0x02020000

class BackendWorker(QThread):
    connection = Signal(dict)
    party = Signal(list)
    encounter = Signal(dict)
    status = Signal(dict)
    log = Signal(str)
    support = Signal(str)
    display = Signal(dict)
    rng_calibration = Signal(dict)
    utilities = Signal(dict)

    def __init__(self):
        super().__init__()
        self.actions=queue.Queue(); self.stop_hunt_event=threading.Event(); self.shutdown_event=threading.Event()
        self.bot=None; self.off=None; self.connected=False; self.hunting=False; self.interval=.75; self._next_idle=0.0
        self.data=None; self.current_game=None; self.display_is_off=False; self._display_lock=threading.Lock(); self._display_request=None; self._wild_horizontal=True
        self._last_rng_fields={}; self._rng_rate_estimate=120.0
        self._wild_movement_mode="wiggle"
        self._next_utilities=0.0
        self._oak_targets=set()
        self._oak_blocked=set()

    def request_connect(self,host,port,interval=.75): self.actions.put(("connect",host,int(port),float(interval)))
    def request_disconnect(self): self.actions.put(("disconnect",))
    def request_release_controller(self): self.actions.put(("detach_controller",))
    def request_start_hunt(self,hunt_key,options=None): self.stop_hunt_event.clear(); self.actions.put(("hunt",hunt_key,options or {}))
    def request_stop_hunt(self): self.stop_hunt_event.set()
    def request_display(self, screen_on: bool):
        # Hunt routines block the worker action queue, so store this request and
        # service it from the worker thread during normal hunt sleeps.
        with self._display_lock:
            self._display_request = bool(screen_on)
        if not self.hunting:
            self.actions.put(("display",))
    def request_shutdown(self): self.stop_hunt_event.set(); self.shutdown_event.set(); self.actions.put(("shutdown",))

    def run(self):
        while not self.shutdown_event.is_set():
            try:
                try: action=self.actions.get(timeout=.08); self._handle(action)
                except queue.Empty: pass
                self._service_display_request()
                if self.connected and not self.hunting and time.monotonic()>=self._next_idle:
                    self._emit_party(); self._emit_utilities(); self._next_idle=time.monotonic()+max(.25,self.interval)
                if self.connected and time.monotonic()>=self._next_utilities:
                    self._emit_utilities(); self._next_utilities=time.monotonic()+0.50
            except Exception as exc:
                self._fail(exc,"backend")
        self._close()

    def _handle(self,a):
        kind=a[0]
        if kind=="connect": self._connect(*a[1:])
        elif kind=="disconnect": self._close()
        elif kind=="hunt": self._hunt_loop(a[1],a[2])
        elif kind=="detach_controller": self._release_controller()
        elif kind=="display": self._service_display_request()
        elif kind=="shutdown": self._close()

    def _service_display_request(self):
        with self._display_lock:
            request=self._display_request
            self._display_request=None
        if request is None:
            return
        if not self.connected or not self.bot:
            self.display.emit({"ok":False,"screen_on":request,"error":"Not connected"})
            return
        try:
            if request:
                self.bot.screen_on(); self.display_is_off=False
            else:
                self.bot.screen_off(); self.display_is_off=True
            self.display.emit({"ok":True,"screen_on":request})
            self.log.emit("Switch display ON" if request else "Switch display OFF")
        except Exception as exc:
            self.display.emit({"ok":False,"screen_on":request,"error":str(exc)})
            raise

    def _connect(self,host,port,interval):
        self._close(); self.interval=interval; bot=WiFiBotbase(host,port); ident=bot.connect(); title,_=bot.get_title_id(); off=lookup(title)
        if off is None: bot.close(); raise RuntimeError(f"{title} is not a supported Switch FireRed/LeafGreen Title ID")
        version,_=bot.get_textish("game version")
        if version!=FRLG_GAME_VERSION: bot.close(); raise RuntimeError(f"Unsupported FRLG version {version}; expected {FRLG_GAME_VERSION}")
        bb,_=bot.get_textish("getVersion"); self.bot=bot; self.off=off; self.current_game=off.game; self.connected=True; self.display_is_off=False; self._next_idle=0
        self.connection.emit({"connected":True,"host":host,"port":port,"connect_ms":round(ident.connect_ms,2),"title_id":title,"game":off.game,"language":off.language,"game_version":version,"botbase":bb,"verified_language":off.language=="English"})
        self.log.emit(f"Connected: {off.language} {off.game} | Koi {bb} | {title}")

    def _release_controller(self):
        """Neutralize inputs and detach Koi's virtual controller without closing RAM/Wi-Fi."""
        if not self.bot:
            return
        try:
            self.bot.set_stick("LEFT",0,0); self.bot.set_stick("RIGHT",0,0)
        except Exception:
            pass
        try:
            self.bot.detach_controller()
            self.log.emit("Virtual controller released — physical controller can reconnect")
        except Exception as exc:
            self.log.emit(f"Could not release virtual controller: {exc}")
            raise

    def _close(self):
        self.hunting=False
        if self.bot:
            try: self.bot.set_stick("LEFT",0,0); self.bot.set_stick("RIGHT",0,0)
            except Exception: pass
            try: self.bot.detach_controller(); time.sleep(.05)
            except Exception: pass
            # If this UI blanked the panel, restore it before disconnect/exit.
            if self.display_is_off:
                try: self.bot.screen_on(); time.sleep(.10)
                except Exception: pass
            try: self.bot.close()
            except Exception: pass
        self.bot=None; self.off=None; self.current_game=None; self.display_is_off=False
        if self.connected: self.connection.emit({"connected":False})
        self.connected=False

    def _data_cache(self):
        if self.data is None:
            self.data=Gen3DataCache()
        return self.data

    def _enrich(self,p):
        return self._data_cache().enrich(p.to_dict() if hasattr(p,"to_dict") else p)

    def _read_party(self):
        out=[]
        for i in range(6):
            p=parse_pk3(self.bot.read_heap(self.off.party_start+i*PARTY_SLOT_STRIDE,BOX_FORMAT_SLOT_SIZE))
            out.append(self._enrich(p) if p.valid else p.to_dict())
        return out

    def _emit_party(self): self.party.emit(self._read_party())

    def _read_saveblock1_base(self):
        """Resolve the live FRLG SaveBlock1 pointer from the game's RAM.

        The FRLG Switch wrapper stores a GBA-era pointer at current-seed+0x0C.
        Convert that GBA address into the Switch heap address using the same
        mapping already used by the existing trainer/box readers.
        """
        ptr = int.from_bytes(self.bot.read_heap(self.off.current_seed + LARGE_SHIFT, 4), "little")
        if ptr == 0 or ptr < GBA_SAVE_BASE:
            return 0
        return ptr - GBA_SAVE_BASE + INITIAL_SEED

    def _read_white_flute_active(self):
        # FRLG SaveBlock1: flags[] starts at 0x0EE0.
        # FLAG_SYS_WHITE_FLUTE_ACTIVE = 0x803 => byte 0x100, bit 3.
        base = self._read_saveblock1_base()
        if not base:
            return None
        raw = self.bot.read_heap(base + 0x0EE0 + 0x100, 1)[0]
        return bool(raw & (1 << 3))

    def _read_illuminate_active(self):
        """Return whether the first party slot currently has Illuminate."""
        try:
            p = parse_pk3(self.bot.read_heap(self.off.party_start, BOX_FORMAT_SLOT_SIZE))
            if not p.valid:
                return False
            return self._enrich(p).get("ability_name") == "Illuminate"
        except Exception:
            return None

    def _emit_utilities(self):
        if not self.connected or not self.bot or not self.off:
            return
        try:
            self.utilities.emit({
                "white_flute": self._read_white_flute_active(),
                "illuminate": self._read_illuminate_active(),
            })
        except Exception as exc:
            self.utilities.emit({"white_flute": None, "illuminate": None, "error": str(exc)})

    def _sleep(self,s):
        end=time.monotonic()+s
        while time.monotonic()<end:
            if self.stop_hunt_event.is_set() or self.shutdown_event.is_set(): return False
            self._service_display_request()
            time.sleep(min(.05,max(0,end-time.monotonic())))
        self._service_display_request()
        return True

    def _is_in_battle(self): return self.bot.read_heap(IN_BATTLE,1)[0]==0x02
    def _battle_menu_ready(self):
        # GRASS/SysBot variants use different non-loading values here.
        # Accept both known ready values; 0x00 is treated as not ready.
        return self.bot.read_heap(BATTLE_MENU,1)[0] in (0x01,0x02)

    def _wait_battle_menu(self, timeout=20.0, label="Auto Capture"):
        """Wait for the FRLG command menu, actively clearing encounter text.

        The Switch FRLG wrapper can remain in the battle/text transition after
        the wild-Pokémon message. Polling BATTLE_MENU alone can leave Auto
        Capture waiting forever because no input is being sent to advance the
        remaining battle text. B is used here rather than A so it can clear
        text without selecting FIGHT if the command menu appears between polls.
        """
        deadline=time.monotonic()+float(timeout)
        next_clear=0.0
        self.status.emit({"state":"CAPTURE_WAIT","message":f"{label}: waiting for the battle command menu…"})
        while time.monotonic()<deadline and not self.stop_hunt_event.is_set():
            if self._battle_menu_ready():
                return True
            if not self._is_in_battle():
                self._sleep(.12)
                continue

            now=time.monotonic()
            if now>=next_clear:
                self.bot.click("B")
                next_clear=now+.45
                if not self._sleep(.12):
                    return False
            else:
                if not self._sleep(.08):
                    return False
        return self._battle_menu_ready()

    def _menu_move(self, x, y, label, hold=.12):
        """Move the in-battle menu with the same left-stick path used by FRLG movement."""
        self.status.emit({"state":"CAPTURE_MENU","message":label})
        return self._stick_tap(x,y,hold=hold,settle=.16)
    def _is_overworld(self): return self.bot.read_heap(self.off.overworld,1)[0]==0xFF

    def _wait_overworld(self):
        deadline=time.monotonic()+30
        while time.monotonic()<deadline and not self.stop_hunt_event.is_set():
            if self._is_overworld(): return True
            self.bot.click(random.choice(("A","X")))
            if not self._sleep(.28): return False
        return False

    def _after_soft_reset(self,clear_offset=None):
        self.bot.soft_reset_frlg()
        if not self._wait_overworld():
            if self.stop_hunt_event.is_set(): return False
            raise RuntimeError("Timed out returning to overworld after soft reset")
        for _ in range(5):
            if self.stop_hunt_event.is_set(): return False
            self.bot.click("B"); self._sleep(.18)
        if clear_offset is not None:
            deadline=time.monotonic()+6
            while time.monotonic()<deadline and not self.stop_hunt_event.is_set():
                p=parse_pk3(self.bot.read_heap(clear_offset,BOX_FORMAT_SLOT_SIZE))
                if not p.valid: return True
                self._sleep(.10)
        return not self.stop_hunt_event.is_set()

    def _party_count(self):
        vals=[]
        for i in range(6):
            p=parse_pk3(self.bot.read_heap(self.off.party_start+i*PARTY_SLOT_STRIDE,BOX_FORMAT_SLOT_SIZE))
            if p.valid: vals.append(p)
            else: break
        return len(vals)

    def _acquire_pk(self,offset,trigger="A",timeout=18,baseline_hex=None):
        deadline=time.monotonic()+timeout
        while time.monotonic()<deadline and not self.stop_hunt_event.is_set():
            self.bot.click(trigger)
            for _ in range(8):
                if not self._sleep(.05): return None
                p=parse_pk3(self.bot.read_heap(offset,BOX_FORMAT_SLOT_SIZE))
                if p.valid and (baseline_hex is None or p.raw_hex!=baseline_hex): return p
        return None

    def _rng_miss_fields(self,p,context="standard"):
        # Read-only diagnostic for every PK3-based hunt engine. It never writes
        # RNG/RAM, waits for a target frame, changes input timing, or influences
        # the shiny/reset decision. Wild/Fishing/Pickup use H-method labels.
        base={
            "rng_method":"Method H1/H2/H4" if context=="wild" else "Method 1/2/4",
            "rng_supported":True,
            "rng_validated":False,
            "rng_capture_seed":None,
            "rng_generation_seed":None,
            "rng_generation_to_capture":None,
            "rng_previous_shiny":None,
            "rng_next_shiny":None,
            "rng_miss":None,
        }
        if p.shiny:
            base.update({"rng_validated":True,"rng_method":"Gen III PID","rng_previous_shiny":0,"rng_next_shiny":0,"rng_miss":0})
            return base
        try:
            capture=int.from_bytes(self.bot.read_heap(self.off.current_seed,4),"little")
            result=miss_from_capture(
                capture,p.pid,p.tid,p.sid,context=context,
                iv_hp=p.iv_hp,iv_atk=p.iv_atk,iv_def=p.iv_def,
                iv_spa=p.iv_spa,iv_spd=p.iv_spd,iv_spe=p.iv_spe,
            )
            base.update({
                "rng_method":result.method,
                "rng_validated":bool(result.validated),
                "rng_capture_seed":result.capture_seed,
                "rng_generation_seed":result.generation_seed,
                "rng_generation_to_capture":result.generation_to_capture,
                "rng_previous_shiny":result.previous_shiny,
                "rng_next_shiny":result.next_shiny,
                "rng_miss":result.miss,
            })
        except Exception as exc:
            self.log.emit(f"RNG miss metric unavailable: {exc}")
        return base

    def _rng_roamer_fields(self,d):
        base={
            "rng_method":"Method 1 (FRLG roamer IV bug)","rng_supported":True,"rng_validated":False,
            "rng_capture_seed":None,"rng_generation_seed":None,"rng_generation_to_capture":None,
            "rng_previous_shiny":None,"rng_next_shiny":None,"rng_miss":None,
        }
        if d.get("shiny"):
            base.update({"rng_validated":True,"rng_previous_shiny":0,"rng_next_shiny":0,"rng_miss":0})
            return base
        try:
            capture=int.from_bytes(self.bot.read_heap(self.off.current_seed,4),"little")
            result=roamer_miss_from_capture(
                capture,int(d["pid"]),int(d["tid"]),int(d["sid"]),
                iv_byte=int(d.get("roamer_iv_byte",0)),
            )
            base.update({
                "rng_method":result.method,"rng_validated":bool(result.validated),
                "rng_capture_seed":result.capture_seed,"rng_generation_seed":result.generation_seed,
                "rng_generation_to_capture":result.generation_to_capture,
                "rng_previous_shiny":result.previous_shiny,"rng_next_shiny":result.next_shiny,"rng_miss":result.miss,
            })
        except Exception as exc:
            self.log.emit(f"Roamer RNG miss metric unavailable: {exc}")
        return base

    def _encounter(self,p,attempt,source,expected=None,rng_context="standard"):
        if expected is not None and p.species!=expected:
            raise RuntimeError(f"Safety HOLD: expected {species_name(expected)} (#{expected}) but read {species_name(p.species)} (#{p.species})")
        rng_fields=self._rng_miss_fields(p,context=rng_context)
        self._last_rng_fields=dict(rng_fields)
        d=self._enrich(p); d.update(rng_fields); d["attempt"]=attempt; d["source"]=source
        self.encounter.emit(d)
        return p.shiny

    def _read_rng_seed(self):
        return int.from_bytes(self.bot.read_heap(self.off.current_seed,4),"little")

    def _oak_species_allowed(self, species: int) -> bool:
        if species in self._oak_blocked:
            return False
        return not self._oak_targets or species in self._oak_targets

    def _read_pokedex_owned(self, species):
        """Read the FRLG SaveBlock2 Pokedex owned bit for one species."""
        try:
            base=self._save_ptr(SMALL_SHIFT)
            if not base or not (1 <= int(species) <= 386):
                return None
            index=int(species)-1
            raw=self.bot.read_heap(base+0x18+0x10+(index//8),1)[0]
            return bool(raw & (1 << (index%8)))
        except Exception as exc:
            self.log.emit(f"Pokedex ownership probe unavailable: {exc}")
            return None

    def _finish_caught_pokemon(self, species, baseline_party, timeout=12.0, pokedex_owned_before=None):
        """Finish FRLG's post-capture script without blind A-button spam.

        FireRed's catch script first records the catch, optionally displays the
        new-Pokédex entry, then reaches the nickname prompt.  pokebot-gen3
        handles those states from the battle script and uses B to decline the
        nickname.  On Switch we do not currently expose the GBA battle-script
        opcode, so use the party data as the capture-complete signal and only
        send B while the battle script is still active.

        This is deliberately B-only here: A can select FIGHT/BAG or advance a
        screen we have not positively identified.
        """
        deadline=time.monotonic()+float(timeout)
        caught=None

        # First wait for the caught Pokémon to be committed to the party.
        # This also prevents a false success merely because IN_BATTLE cleared.
        while time.monotonic()<deadline and not self.stop_hunt_event.is_set():
            current=self._party_slots()
            for index,p in enumerate(current):
                if not p.valid or p.is_egg:
                    continue
                before=baseline_party[index] if index<len(baseline_party) else None
                if before is None or not before.valid or before.raw_hex!=p.raw_hex:
                    if int(p.species)==int(species):
                        caught=p
                        break
            if caught is not None:
                self.status.emit({"state":"CAPTURE_RESULT","message":f"Auto Capture: {species_name(species)} confirmed in party; probing Pokedex/nickname flow…"})
                dex_after=self._read_pokedex_owned(species)
                if pokedex_owned_before is False and dex_after is True:
                    self.log.emit(f"CAPTURE PROBE: Pokedex registration YES for {species_name(species)}")
                    self.status.emit({"state":"CAPTURE_RESULT","message":f"Capture probe: Pokedex registration YES — {species_name(species)} was newly registered."})
                elif pokedex_owned_before is True:
                    self.log.emit(f"CAPTURE PROBE: Pokedex registration NO for {species_name(species)} (already registered)")
                    self.status.emit({"state":"CAPTURE_RESULT","message":f"Capture probe: Pokedex registration NO — {species_name(species)} was already registered."})
                else:
                    self.log.emit(f"CAPTURE PROBE: Pokedex ownership could not be classified (before={pokedex_owned_before!r}, after={dex_after!r})")
                # A newly registered species enters FRLG's Pokédex display
                # before the nickname prompt. That screen needs an explicit
                # advance; B alone can leave Auto Capture parked on the Dex
                # screen. If the species was already registered, A may briefly
                # open the nickname input; the following B cancels that input
                # and the subsequent B declines the nickname normally.
                # FRLG's new-species registration screen is a blocking
                # display task.  The previous press/release sequence could
                # arrive while that task was still taking control, leaving the
                # bot parked on the Pokédex.  Use the same Koi click transport
                # that is already proven throughout the rest of Auto Capture,
                # and give the registration screen a full settling interval.
                if not self._sleep(2.25):
                    return False
                self.status.emit({"state":"CAPTURE_RESULT","message":f"Auto Capture: advancing {species_name(species)} Pokédex entry…"})
                self.bot.click("A")
                if not self._sleep(1.75):
                    return False
                self.status.emit({"state":"CAPTURE_RESULT","message":"Capture probe: nickname prompt — selecting NO…"})
                self.log.emit("CAPTURE PROBE: nickname prompt YES; selecting NO with B")
                self.bot.click("B")
                if not self._sleep(1.00):
                    return False
                break
            if not self._sleep(.10):
                return False

        # A full party can send the new Pokémon to a PC, so absence from the
        # party is not by itself a failed capture.  Once the battle has ended,
        # allow the game's own post-capture script to finish.  If it is still
        # active, B is the safe non-selecting input used by pokebot-gen3 to
        # advance the catch/nickname dialogue.
        while time.monotonic()<deadline and not self.stop_hunt_event.is_set() and self._is_in_battle():
            self.bot.click("B")
            if not self._sleep(.18):
                return False

        # Do not resume Spin/Wiggle while the return-to-field script is still
        # handing control back to the player.  Keep the stick neutral and
        # require several consecutive overworld polls.
        self.bot.set_stick("LEFT",0,0)
        stable=0
        while time.monotonic()<deadline and not self.stop_hunt_event.is_set():
            if self._is_overworld():
                stable+=1
                if stable>=5:
                    break
            else:
                stable=0
            if not self._sleep(.08):
                return False
        if stable<5:
            raise RuntimeError("Auto Capture post-catch sequence did not return to a stable overworld")

        self.party.emit(self._read_party())
        self.log.emit(f"CAPTURE PROBE: stable overworld YES after capture -> Pokedex -> nickname NO for {species_name(species)}")
        if caught is not None:
            self.status.emit({"state":"CAPTURED","message":f"Auto Capture complete: {species_name(species)} — capture -> Pokedex -> nickname NO -> overworld verified."})
            return True

        # No party delta is expected when the party was already full.  The
        # successful catch has nevertheless reached the post-capture script and
        # returned cleanly to the overworld.
        self.log.emit(f"CAPTURE PROBE: stable overworld YES after full-party capture flow for {species_name(species)}")
        self.status.emit({"state":"CAPTURED","message":f"Auto Capture complete: {species_name(species)} — capture -> Pokedex -> nickname NO -> overworld verified."})
        return True

    def _auto_capture(self, options, label):
        """Capture the current non-shiny wild encounter using controller input only."""
        if not bool(options.get("auto_capture", False)):
            return False
        ball_slot=max(1,min(6,int(options.get("capture_ball_slot",1) or 1)))
        max_throws=max(1,min(99,int(options.get("capture_max_throws",10) or 10)))
        self.status.emit({"state":"CAPTURE","message":f"Auto Capture: {label} — preparing Poké Ball slot {ball_slot}…"})
        deadline=time.monotonic()+45
        baseline_party=self._party_slots()
        pokedex_owned_before=self._read_pokedex_owned(capture_species)
        if pokedex_owned_before is True:
            self.log.emit(f"CAPTURE PROBE: {label} already registered in Pokedex before capture")
        elif pokedex_owned_before is False:
            self.log.emit(f"CAPTURE PROBE: {label} not registered in Pokedex before capture")
        else:
            self.log.emit(f"CAPTURE PROBE: Pokedex state unavailable before capturing {label}")
        # The caller passes the current wild species so post-capture verification
        # never relies on the display label.
        capture_species=int(options.get("_capture_species_id",0) or 0)
        if capture_species<=0:
            raise RuntimeError("Auto Capture missing current wild species id")
        # A wild encounter first shows the "Wild <Pokémon> appeared!"
        # message. Advance it once, then let _wait_battle_menu() actively clear
        # any remaining battle text with B. This avoids the previous deadlock
        # where the code only polled RAM after the initial A press.
        if not self._battle_menu_ready():
            self.status.emit({"state":"CAPTURE_WAIT","message":"Auto Capture: dismissing encounter message…"})
            self.bot.click("A")
            if not self._sleep(.25): return False
        for throw in range(1,max_throws+1):
            if self.stop_hunt_event.is_set(): return False
            if not self._wait_battle_menu(timeout=max(1.0,deadline-time.monotonic()),label="Auto Capture"):
                raise RuntimeError("Battle menu did not become ready for Auto Capture")
            if not self._is_in_battle():
                raise RuntimeError("Auto Capture lost the battle before opening the Bag")

            self.status.emit({"state":"CAPTURE_MENU","message":"Auto Capture: opening Bag…"})
            if not self._menu_move(0x7FFF,0,"Auto Capture: selecting BAG"):
                raise RuntimeError("Could not move to BAG in the battle menu")
            self.bot.click("A"); self._sleep(.65)

            # FRLG remembers both the last Bag pocket and the last cursor
            # position. After a failed throw the cursor can therefore reopen
            # on the ball used by the previous attempt. The configured
            # capture_ball_slot is an absolute slot from the top of the
            # Poké Balls list, not "move down again from the current cursor".
            self.status.emit({"state":"CAPTURE_MENU","message":"Auto Capture: opening Poké Balls pocket…"})
            if not self._sleep(.80):
                return False
            for index in range(2):
                self.bot.click("DRIGHT")
                if not self._sleep(.65):
                    return False
            if not self._sleep(.50):
                return False

            # Normalize the Poké Balls cursor to the top before applying the
            # configured slot. DUP is safe at the top boundary and, unlike
            # repeated DDOWN, makes retries deterministic when FRLG restores
            # the previous ball cursor.
            self.status.emit({"state":"CAPTURE_MENU","message":"Auto Capture: resetting Poké Ball cursor…"})
            for index in range(6):
                self.bot.click("DUP")
                if not self._sleep(.18):
                    return False

            self.status.emit({"state":"CAPTURE_MENU","message":f"Auto Capture: selecting ball slot {ball_slot}…"})
            for index in range(ball_slot-1):
                self.bot.click("DDOWN")
                if not self._sleep(.35):
                    return False
            if not self._sleep(.35):
                return False

            # One A selects the highlighted ball and advances to the use/throw
            # confirmation. A second A confirms the throw. There is deliberately
            # no B here: B was causing the configured slot to be cancelled and
            # the cursor to return to slot 1 on hardware.
            self.status.emit({"state":"CAPTURE_MENU","message":f"Auto Capture: throwing selected ball (slot {ball_slot})…"})
            self.bot.click("A")
            if not self._sleep(.55):
                return False
            self.bot.click("A")
            if not self._sleep(.25):
                return False
            self.status.emit({"state":"CAPTURE","message":f"Auto Capture: throw {throw}/{max_throws}…"})

            wait_end=min(deadline,time.monotonic()+8.0)
            while time.monotonic()<wait_end and not self.stop_hunt_event.is_set():
                # Check the party first. A successful catch may still be inside
                # FRLG's catch/Pokédex/nickname script while IN_BATTLE is true.
                current=self._party_slots()
                for index,p in enumerate(current):
                    if not p.valid or p.is_egg:
                        continue
                    before=baseline_party[index] if index<len(baseline_party) else None
                    if before is None or not before.valid or before.raw_hex!=p.raw_hex:
                        if int(p.species)==capture_species:
                            break

                if not self._is_in_battle():
                    # Do not treat a transient battle-RAM transition as a
                    # successful catch. A failed ball can briefly clear/update
                    # battle state while FRLG is still processing the
                    # "broke free" message. Require the wild battle to stay
                    # closed, or confirm the caught species in the party.
                    caught_delta=False
                    stable_out=0
                    check_deadline=min(wait_end,time.monotonic()+1.5)
                    while time.monotonic()<check_deadline and not self.stop_hunt_event.is_set():
                        current=self._party_slots()
                        for index,p in enumerate(current):
                            if not p.valid or p.is_egg:
                                continue
                            before=baseline_party[index] if index<len(baseline_party) else None
                            if (before is None or not before.valid or before.raw_hex!=p.raw_hex) and int(p.species)==capture_species:
                                caught_delta=True
                                break
                        if caught_delta:
                            break
                        if self._is_in_battle():
                            break
                        stable_out+=1
                        if stable_out>=5:
                            break
                        if not self._sleep(.10):
                            return False

                    if caught_delta or stable_out>=5:
                        self.status.emit({"state":"CAPTURE_RESULT","message":f"Auto Capture: throw {throw} ended the battle; handling post-capture flow…"})
                        return self._finish_caught_pokemon(capture_species, baseline_party, timeout=max(2.0,deadline-time.monotonic()), pokedex_owned_before=pokedex_owned_before)

                    # Battle state came back after a transient clear: this was
                    # not a completed capture. Continue waiting for the battle
                    # command menu and retry with the configured ball.
                    self.status.emit({"state":"CAPTURE","message":f"Auto Capture: throw {throw} did not finish the battle; waiting to retry…"})
                    if not self._sleep(.20):
                        return False
                    continue

                if self._battle_menu_ready():
                    self.status.emit({"state":"CAPTURE","message":f"Auto Capture: throw {throw} failed/broke out — retrying with ball slot {ball_slot}…"})
                    if not self._sleep(.30):
                        return False
                    break
                if not self._sleep(.10):
                    return False

        self.status.emit({"state":"RUNNING","message":f"Auto Capture: could not catch {label} after {max_throws} throw(s) — escaping…"})
        return self._escape_battle()
    def _shiny_action(self, label, attempt, options, suffix=""):
        if bool(options.get("shiny_auto_capture",False)):
            self.status.emit({"state":"SHINY_CAPTURE","message":f"SHINY {label} FOUND — Auto Capture enabled." ,"attempt":attempt})
            # _auto_capture now verifies the caught species against the party
            # rather than treating the end of battle RAM as proof of capture.
            # Normal wild encounters pass this explicitly; shiny encounters
            # reach this helper, so read the live wild PK3 here as well.
            capture_options=dict(options, auto_capture=True)
            try:
                wild=parse_pk3(self.bot.read_heap(self.off.wild_pokemon,BOX_FORMAT_SLOT_SIZE))
            except Exception:
                wild=None
            if wild is None or not wild.valid:
                raise RuntimeError("Shiny Auto Capture could not read the current wild Pokémon")
            capture_options["_capture_species_id"]=int(wild.species)
            if self._auto_capture(capture_options, label):
                return True
            return False
        self._shiny_home(label,attempt,suffix)
        return True


    def _run_oak_wild(self,h,options):
        self._wild_horizontal=True
        self._wild_movement_mode=str(options.get("wild_movement_mode","wiggle") or "wiggle")
        spin_hold=max(.02,min(.20,float(options.get("spin_hold",.045) or .045)))
        spin_settle=max(.02,min(.20,float(options.get("spin_settle",.055) or .055)))
        self._oak_targets={int(x) for x in options.get("oak_targets",[]) if str(x).isdigit()}
        self._oak_blocked={int(x) for x in options.get("oak_blocked",[]) if str(x).isdigit()}
        attempt=0
        while not self.stop_hunt_event.is_set():
            movement_label="Spin" if self._wild_movement_mode=="spin" else "Wiggle"
            target_label=", ".join(species_name(x) for x in sorted(self._oak_targets)) if self._oak_targets else "any non-blocked species"
            self.status.emit({"state":"HUNTING","message":f"Oak Mode: searching for {target_label} ({movement_label})","attempt":attempt})
            if self._wild_movement_mode=="spin":
                if not self._spin_to_battle(spin_hold,spin_settle): return
            else:
                if not self._wiggle_to_battle(): return
            p=parse_pk3(self.bot.read_heap(self.off.wild_pokemon,BOX_FORMAT_SLOT_SIZE))
            if not p.valid: raise RuntimeError("Battle started but wild PK3 was invalid")
            attempt+=1

            # Every Oak encounter is a real encounter and must feed the normal
            # session/current/last-seen pipeline, even when Oak filtering later
            # rejects it. The previous implementation only emitted the signal
            # after both the species and shiny filters, so rejected Oak
            # encounters never reached the dashboard or session statistics.
            d=self._enrich(p); d["attempt"]=attempt; d["source"]="Oak Challenge"; d["oak_target"]=False
            d.update(self._rng_miss_fields(p,context="wild"))
            self.encounter.emit(d)

            if not self._oak_species_allowed(p.species):
                self.status.emit({"state":"RUNNING","message":f"Oak Mode: {species_name(p.species)} blocked/not targeted — escaping…","attempt":attempt})
                if not self._escape_battle(): return
                continue

            # Oak Challenge can explicitly require shiny or non-shiny
            # encounters. Preserve the historical non-shiny behaviour as the
            # default, while allowing a dedicated Shiny Only mode.
            oak_shiny_mode=str(options.get("oak_shiny_mode","non_shiny") or "non_shiny")
            shiny_match=(oak_shiny_mode=="shiny" and bool(p.shiny)) or (
                oak_shiny_mode!="shiny" and oak_shiny_mode!="non_shiny"
            ) or (oak_shiny_mode=="non_shiny" and not bool(p.shiny))
            if not shiny_match:
                wanted="shiny" if oak_shiny_mode=="shiny" else "non-shiny"
                actual="shiny" if p.shiny else "non-shiny"
                self.status.emit({"state":"RUNNING","message":
                    f"Oak Mode: {species_name(p.species)} is {actual}; {wanted} only — escaping…",
                    "attempt":attempt})
                if not self._escape_battle(): return
                continue

            d["oak_target"]=True
            capture_options=dict(options, _capture_species_id=int(p.species))
            if self._auto_capture(capture_options, species_name(p.species)):
                self.status.emit({"state":"CAPTURED","message":f"Oak target captured: {species_name(p.species)} — advancing Oak line progress.","attempt":attempt,"oak_target":True,"oak_captured":True,"species_id":int(p.species)})
                self.stop_hunt_event.set()
                return
            self.status.emit({"state":"HOLD","message":f"Oak target found: {species_name(p.species)} — catch it, then update the checklist/block list.","attempt":attempt,"oak_target":True})
            self.stop_hunt_event.set()
            return

    def _auto_rng_enabled(self, options, engine):
        return bool(options.get("auto_rng",False)) and engine in ("starter","gift","static","static_hooh")

    def _auto_rng_target(self, options, lead):
        tid,sid=self._trainer_ids()
        start=self._read_rng_seed()
        nature=options.get("rng_nature_index",None)
        if nature in (None,"",-1,"-1"):
            nature=None
        else:
            nature=int(nature)
        mins=tuple(int(options.get(k,0) or 0) for k in (
            "rng_iv_hp","rng_iv_atk","rng_iv_def","rng_iv_spa","rng_iv_spd","rng_iv_spe"
        ))
        # Give the trigger sequence room to run even before calibration has converged.
        minimum=max(int(lead)+300,600)
        maximum=max(minimum+1,int(options.get("rng_max_advances",500000) or 500000))
        target=find_method1_target(
            start,tid,sid,
            shiny_only=bool(options.get("rng_shiny_only",True)),
            nature_index=nature,min_ivs=mins,min_advances=minimum,max_advances=maximum,
        )
        if target is None:
            raise RuntimeError(
                f"Auto RNG: no Method-1 target matched the selected filters within {maximum:,} advances. "
                "Increase Max search advances or loosen the IV/nature filters."
            )
        return target

    def _rng_progress_since(self, previous_seed, previous_t):
        now_seed=self._read_rng_seed(); now_t=time.monotonic()
        dt=max(0.001,now_t-previous_t)
        # 120 advances/s is typical, but allow generous headroom for fast-forward-like states.
        cap=max(500,int(max(self._rng_rate_estimate,120.0)*dt*8)+500)
        dist=forward_distance_limited(previous_seed,now_seed,cap)
        if dist is None:
            raise RuntimeError("Auto RNG lost the live RNG stream while waiting for the target")
        if dist>0:
            measured=dist/dt
            if 20.0 <= measured <= 5000.0:
                self._rng_rate_estimate=self._rng_rate_estimate*0.75+measured*0.25
        return now_seed,now_t,dist

    def _wait_for_rng_trigger(self,target,lead,trigger):
        """Wait until the target PID-start is roughly `lead` calls away, then trigger.

        Reads are used only for coarse closed-loop progress. The final short segment
        is timed from the measured live RNG rate; subsequent miss calibration learns
        the fixed trigger-to-generation offset on real hardware.
        """
        # The target search itself takes PC time while the game keeps advancing.
        # Re-read once and explicitly recover that progress before starting the
        # closed-loop wait; do not infer its duration from a newly-created timer.
        now_seed=self._read_rng_seed(); now_t=time.monotonic()
        dist=forward_distance_limited(target.start_seed,now_seed,100000)
        if dist is None:
            raise RuntimeError("Auto RNG target search took too long to recover live-seed progress")
        progressed=dist; previous_seed,previous_t=now_seed,now_t
        trigger_at=max(0,int(target.advances)-int(lead))
        if progressed>trigger_at:
            raise RuntimeError("Auto RNG target became too close while preparing it; retry the hunt")
        while not self.stop_hunt_event.is_set():
            remaining=trigger_at-progressed
            if remaining<=0:
                break
            rate=max(20.0,float(self._rng_rate_estimate))
            # Leave ~90 advances for the final timed segment to avoid a late Wi-Fi peek.
            if remaining<=90:
                if not self._sleep(max(0.0,remaining/rate)):
                    return False
                break
            sleep_for=min(.50,max(.04,(remaining-70)/rate))
            if not self._sleep(sleep_for):
                return False
            now_seed,now_t,dist=self._rng_progress_since(previous_seed,previous_t)
            progressed+=dist; previous_seed,previous_t=now_seed,now_t
        if self.stop_hunt_event.is_set():
            return False
        self.bot.click(trigger)
        return True

    def _acquire_pk_after_rng_trigger(self,offset,timeout=18,baseline_hex=None):
        """Continue deterministic A presses after the one precisely timed trigger."""
        deadline=time.monotonic()+timeout
        while time.monotonic()<deadline and not self.stop_hunt_event.is_set():
            for _ in range(4):
                if not self._sleep(.06): return None
                p=parse_pk3(self.bot.read_heap(offset,BOX_FORMAT_SLOT_SIZE))
                if p.valid and (baseline_hex is None or p.raw_hex!=baseline_hex): return p
            self.bot.click("A")
        return None

    def _run_auto_rng_attempt(self,h,options,offset,trigger,attempt,timeout=18,baseline_hex=None):
        lead=max(0,int(options.get("rng_trigger_lead",0) or 0))
        target=self._auto_rng_target(options,lead)
        nature=NATURES[target.nature_index]
        spread=f"{target.iv_hp}/{target.iv_atk}/{target.iv_def}/{target.iv_spa}/{target.iv_spd}/{target.iv_spe}"
        self.status.emit({"state":"RNG_TARGET","message":
            f"Auto RNG target: +{target.advances:,} • {nature} • IVs {spread} • "
            f"SV {target.shiny_xor} • trigger lead {lead:,}","attempt":attempt})
        self.log.emit(f"Auto RNG target PID {target.pid:08X} at seed 0x{target.generation_seed:08X} (+{target.advances:,})")
        if not self._wait_for_rng_trigger(target,lead,trigger):
            return None,target,lead
        p=self._acquire_pk_after_rng_trigger(offset,timeout=timeout,baseline_hex=baseline_hex)
        return p,target,lead

    def _calibrate_auto_rng(self,h,target,lead):
        fields=self._last_rng_fields or {}
        observed=fields.get("rng_generation_seed")
        if observed is None:
            self.log.emit("Auto RNG calibration skipped: observed generation seed did not validate")
            return lead,None
        delta=nearby_signed_distance(target.generation_seed,int(observed),max_steps=20000)
        if delta is None:
            self.log.emit("Auto RNG calibration skipped: observed hit was more than 20,000 advances from target")
            return lead,None
        # +delta means generation landed late, therefore press earlier next time by increasing lead.
        new_lead=max(0,min(20000,int(lead)+int(delta)))
        self.rng_calibration.emit({"hunt_key":h.key,"lead":new_lead,"delta":int(delta),
                                   "target_seed":target.generation_seed,"observed_seed":int(observed)})
        self.log.emit(f"Auto RNG calibration: miss {delta:+,} advances; trigger lead {lead:,} -> {new_lead:,}")
        return new_lead,delta

    def _shiny_home(self,label,attempt,suffix=""):
        """Temporary pre-auto-capture shiny safety action: return to HOME and stop the hunt."""
        message=f"SHINY {label} FOUND — returning to Switch HOME"
        if suffix:
            message += f" {suffix}"
        self.status.emit({"state":"SHINY_HOLD","message":message,"attempt":attempt})
        self.log.emit(message)
        # Neutralize movement before HOME so no held direction can leak into the HOME menu.
        try:
            self.bot.set_stick("LEFT",0,0); self.bot.set_stick("RIGHT",0,0)
        except Exception:
            pass
        # Wake the panel before HOME so the shiny safety hold is visible.
        if self.display_is_off:
            try:
                self.bot.screen_on(); self.display_is_off=False
                self.display.emit({"ok":True,"screen_on":True,"reason":"shiny"})
                self._sleep(.15)
            except Exception as exc:
                self.log.emit(f"Could not wake Switch display before HOME: {exc}")
        self.bot.click("HOME")
        self._sleep(1.5)
        self.stop_hunt_event.set()

    def _hunt_loop(self,hunt_key,options):
        if not self.connected: raise RuntimeError("Connect to the Switch before starting a hunt")
        h=BY_KEY.get(hunt_key)
        if not h: raise RuntimeError(f"Unknown hunt {hunt_key}")
        if self.current_game not in h.games: raise RuntimeError(f"{h.label} is not available in {self.current_game}")
        self.hunting=True; self.stop_hunt_event.clear(); self.status.emit({"state":"STARTING","message":f"Starting {h.label}"})
        try:
            self.bot.initialize_controller()
            dispatch={
                "starter":self._run_starter,"gift":self._run_gift,"static":self._run_static,
                "static_hooh":self._run_static_hooh,"wild":self._run_wild,"oak_wild":self._run_oak_wild,"fishing":self._run_fishing,
                "game_corner":self._run_game_corner,"roamer":self._run_roamer,"pickup":self._run_pickup,
                "egg_breeding":self._run_egg_breeding,"egg_release":self._run_egg_release,
                "auto_capture_test":self._run_auto_capture_test,
            }
            fn=dispatch.get(h.engine)
            if not fn: raise RuntimeError(f"Hunt engine {h.engine} is not implemented")
            fn(h,options)
            if self.stop_hunt_event.is_set() and not self.shutdown_event.is_set():
                self.status.emit({"state":"STOPPED","message":"Hunt stopped by user"})
        except Exception as exc:
            # A deliberate Stop/Shutdown is normal control flow and must never
            # create a support package. Only genuine hunt failures do.
            if self.stop_hunt_event.is_set() or self.shutdown_event.is_set():
                if not self.shutdown_event.is_set():
                    self.status.emit({"state":"STOPPED","message":"Hunt stopped by user"})
            else:
                self._fail(exc,h.engine)
                self.status.emit({"state":"SAFETY_HOLD","message":str(exc)})
        finally:
            self.hunting=False
            # Always give the physical controller back when a hunt ends,
            # regardless of user stop, safety hold, shiny HOME, or exception.
            try: self._release_controller()
            except Exception: pass
            self._next_idle=0

    def _party_slots(self):
        return [parse_pk3(self.bot.read_heap(self.off.party_start+i*PARTY_SLOT_STRIDE,BOX_FORMAT_SLOT_SIZE)) for i in range(6)]

    def _first_empty_party_slot(self):
        for i,p in enumerate(self._party_slots()):
            if not p.valid:
                return i
        return None

    def _read_egg_slot(self, slot):
        p=parse_pk3(self.bot.read_heap(self.off.party_start+slot*PARTY_SLOT_STRIDE,BOX_FORMAT_SLOT_SIZE))
        return p if p.valid and p.is_egg else None

    def _collect_daycare_egg(self, slot, attempts=18):
        self.status.emit({"state":"EGG_COLLECT","message":"Talking to the Day Care Man for an egg…"})
        for _ in range(max(1,int(attempts))):
            self.bot.click("A")
            if not self._sleep(.30): return None
            p=self._read_egg_slot(slot)
            if p is not None:
                self.status.emit({"state":"EGG_COLLECTED","message":f"Egg collected into party slot {slot+1}."})
                self.party.emit(self._read_party())
                return p
        return None

    def _hatch_egg_slot(self, slot, options):
        offset=self.off.party_start+slot*PARTY_SLOT_STRIDE
        p=self._read_egg_slot(slot)
        if p is None:
            raise RuntimeError(f"Egg safety check failed: party slot {slot+1} is not an egg")
        direction=str(options.get("egg_hatch_direction","right") or "right").lower()
        x,y=(0x7FFF,0) if direction=="right" else ((-0x8000,0) if direction=="left" else (0,0x7FFF))
        hold=max(.05,min(2.0,float(options.get("egg_hatch_hold",.35) or .35)))
        neutral=max(.02,min(1.0,float(options.get("egg_hatch_neutral",.08) or .08)))
        max_cycles=max(1,int(options.get("egg_hatch_cycles",900) or 900))
        self.status.emit({"state":"HATCHING","message":f"Hatching egg in party slot {slot+1}…"})
        for cycle in range(max_cycles):
            if self.stop_hunt_event.is_set(): return None
            self.bot.set_stick("LEFT",int(x),int(y))
            if not self._sleep(hold):
                self.bot.set_stick("LEFT",0,0); return None
            self.bot.set_stick("LEFT",0,0)
            if not self._sleep(neutral): return None
            current=parse_pk3(self.bot.read_heap(offset,BOX_FORMAT_SLOT_SIZE))
            if current.valid and not current.is_egg:
                self.status.emit({"state":"HATCHED","message":f"Egg hatched after {cycle+1} movement cycles."})
                self.party.emit(self._read_party())
                return current
            if cycle and cycle % 50 == 0:
                self.status.emit({"state":"HATCHING","message":f"Hatching… movement cycle {cycle}/{max_cycles}"})
        raise RuntimeError("Egg did not hatch within the configured movement-cycle limit")

    def _pc_open_bill(self):
        self.bot.click("A"); self._sleep(.8)
        self.bot.click("A"); self._sleep(.8)

    def _pc_select_submenu(self, item_index):
        for _ in range(max(0,int(item_index))):
            self.bot.click("DDOWN"); self._sleep(.18)
        self.bot.click("A"); self._sleep(.8)

    def _pc_deposit_party_slot(self, slot, box_row=0, box_col=0):
        self._pc_open_bill()
        self._pc_select_submenu(1)
        for _ in range(max(0,int(slot))):
            self.bot.click("DDOWN"); self._sleep(.15)
        self.bot.click("A"); self._sleep(.6)
        for _ in range(max(0,int(box_row))):
            self.bot.click("DDOWN"); self._sleep(.12)
        for _ in range(max(0,int(box_col))):
            self.bot.click("DRIGHT"); self._sleep(.12)
        self.bot.click("A"); self._sleep(1.0)
        self.bot.click("B"); self._sleep(.5)
        return True

    def _pc_release_box_slot(self, box_row=0, box_col=0):
        self.bot.click("B"); self._sleep(.4)
        for _ in range(3):
            self.bot.click("DDOWN"); self._sleep(.18)
        self.bot.click("A"); self._sleep(.8)
        for _ in range(max(0,int(box_row))):
            self.bot.click("DDOWN"); self._sleep(.12)
        for _ in range(max(0,int(box_col))):
            self.bot.click("DRIGHT"); self._sleep(.12)
        self.bot.click("A"); self._sleep(.45)
        self.bot.click("A"); self._sleep(1.0)
        self.bot.click("B"); self._sleep(.4)
        return True

    def _run_egg_release(self,h,options):
        slot=max(0,min(5,int(options.get("egg_release_party_slot",0) or 0)))
        p=parse_pk3(self.bot.read_heap(self.off.party_start+slot*PARTY_SLOT_STRIDE,BOX_FORMAT_SLOT_SIZE))
        if not p.valid or p.is_egg:
            raise RuntimeError(f"Release safety check failed: party slot {slot+1} does not contain a hatched Pokémon")
        if p.shiny:
            self._shiny_home(species_name(p.species),1,"Release routine stopped — shiny protection")
            return
        row=max(0,min(4,int(options.get("egg_release_box_row",0) or 0)))
        col=max(0,min(5,int(options.get("egg_release_box_col",0) or 0)))
        self.status.emit({"state":"RELEASE","message":f"Depositing non-shiny {species_name(p.species)} and releasing it…"})
        self._pc_deposit_party_slot(slot,row,col)
        self._pc_release_box_slot(row,col)
        self.party.emit(self._read_party())
        self.status.emit({"state":"RELEASED","message":f"Released non-shiny {species_name(p.species)}."})

    def _run_egg_breeding(self,h,options):
        if not bool(options.get("egg_breeding_unlocked",True)):
            raise RuntimeError("Egg mode is locked until Four Island breeding/egg hatching is enabled")
        release_nonshiny=bool(options.get("egg_release_nonshiny",True))
        collect_attempts=max(1,int(options.get("egg_collect_attempts",18) or 18))
        max_eggs=max(1,min(99,int(options.get("egg_max_eggs",1) or 1)))
        processed=0
        while processed < max_eggs and not self.stop_hunt_event.is_set():
            slot=self._first_empty_party_slot()
            if slot is None:
                raise RuntimeError("Egg mode needs an empty party slot")
            egg=self._collect_daycare_egg(slot,collect_attempts)
            if egg is None:
                raise RuntimeError("No egg appeared in the selected party slot. Check the Day Care Man checkpoint and parent setup.")
            hatched=self._hatch_egg_slot(slot,options)
            if hatched is None: return
            processed += 1
            attempt=processed
            if self._encounter(hatched,attempt,"FRLG Egg Hatch"):
                self._shiny_home(species_name(hatched.species),attempt)
                return
            if release_nonshiny:
                self.status.emit({"state":"RELEASE_PENDING","message":f"Non-shiny {species_name(hatched.species)} — releasing."})
                release_options=dict(options); release_options["egg_release_party_slot"]=slot
                self._run_egg_release(h,release_options)
                # The first implementation intentionally stops after a release.
                # Returning from the Four Island Day Care to the PC and back is
                # route-dependent; that navigation layer is isolated for the next pass.
                return
            else:
                self.status.emit({"state":"KEPT","message":f"Non-shiny {species_name(hatched.species)} kept; egg cycle complete."})
                return
        self.status.emit({"state":"STOPPED","message":f"Egg cycle complete: {processed} egg(s) processed."})

    def _run_starter(self,h,options):
        first=parse_pk3(self.bot.read_heap(self.off.party_start,BOX_FORMAT_SLOT_SIZE))
        if first.valid: raise RuntimeError(f"Starter safety check: party slot 1 already contains {species_name(first.species)}. Load the pre-starter save with an empty party.")
        if not self._is_overworld(): raise RuntimeError("Starter safety check: game is not on the overworld")
        attempt=0
        while not self.stop_hunt_event.is_set():
            attempt+=1; self.status.emit({"state":"HUNTING","message":f"Attempt {attempt}: selecting {h.label}","attempt":attempt})
            target=lead=None
            if self._auto_rng_enabled(options,h.engine):
                p,target,lead=self._run_auto_rng_attempt(h,options,self.off.party_start,"A",attempt,timeout=18)
            else:
                p=self._acquire_pk(self.off.party_start,"A")
            if p is None:
                if self.stop_hunt_event.is_set(): return
                raise RuntimeError("Starter did not appear in party slot 1 within timeout")
            if self._encounter(p,attempt,h.label,h.species):
                self._shiny_home(h.label,attempt); return
            if target is not None:
                new_lead,_=self._calibrate_auto_rng(h,target,lead); options["rng_trigger_lead"]=new_lead
            self.party.emit(self._read_party()); self.status.emit({"state":"RESETTING","message":"Non-shiny — soft resetting A+B+X+Y","attempt":attempt})
            if not self._after_soft_reset(self.off.party_start): return
            self.party.emit(self._read_party())

    def _run_gift(self,h,options):
        count=self._party_count()
        if count>=6: raise RuntimeError("Gift hunt needs at least one empty party slot")
        offset=self.off.party_start+count*PARTY_SLOT_STRIDE
        if parse_pk3(self.bot.read_heap(offset,BOX_FORMAT_SLOT_SIZE)).valid: raise RuntimeError("Gift target slot is not empty")
        attempt=0
        while not self.stop_hunt_event.is_set():
            attempt+=1; self.status.emit({"state":"HUNTING","message":f"Attempt {attempt}: receiving {h.label}","attempt":attempt})
            target=lead=None
            if self._auto_rng_enabled(options,h.engine):
                p,target,lead=self._run_auto_rng_attempt(h,options,offset,"A",attempt,timeout=22)
            else:
                p=self._acquire_pk(offset,"A",timeout=22)
            if p is None:
                if self.stop_hunt_event.is_set(): return
                raise RuntimeError("Gift Pokémon did not appear in the next empty party slot within timeout")
            if self._encounter(p,attempt,h.label,h.species):
                self._shiny_home(h.label,attempt); return
            if target is not None:
                new_lead,_=self._calibrate_auto_rng(h,target,lead); options["rng_trigger_lead"]=new_lead
            self.party.emit(self._read_party()); self.status.emit({"state":"RESETTING","message":"Non-shiny — soft resetting","attempt":attempt})
            if not self._after_soft_reset(offset): return

    def _run_static_common(self,h,trigger,options=None):
        options=options or {}
        attempt=0; base=parse_pk3(self.bot.read_heap(self.off.wild_pokemon,BOX_FORMAT_SLOT_SIZE)); last_hex=base.raw_hex if base.valid else None
        while not self.stop_hunt_event.is_set():
            attempt+=1; self.status.emit({"state":"HUNTING","message":f"Attempt {attempt}: triggering {h.label}","attempt":attempt})
            target=lead=None
            if self._auto_rng_enabled(options,h.engine):
                p,target,lead=self._run_auto_rng_attempt(h,options,self.off.wild_pokemon,trigger,attempt,timeout=18,baseline_hex=last_hex)
            else:
                p=self._acquire_pk(self.off.wild_pokemon,trigger,timeout=18,baseline_hex=last_hex)
            if p is None:
                if self.stop_hunt_event.is_set(): return
                raise RuntimeError("Static encounter PK3 did not appear within timeout")
            last_hex=p.raw_hex
            if self._encounter(p,attempt,h.label,h.species):
                self._shiny_home(h.label,attempt); return
            if target is not None:
                new_lead,_=self._calibrate_auto_rng(h,target,lead); options["rng_trigger_lead"]=new_lead
            self.status.emit({"state":"RESETTING","message":"Non-shiny — soft resetting","attempt":attempt})
            if not self._after_soft_reset(): return

    def _run_static(self,h,options): self._run_static_common(h,"A",options)
    def _run_static_hooh(self,h,options): self._run_static_common(h,"DUP",options)

    def _stick_tap(self,x,y,hold=.085,settle=.105):
        # Switch FRLG standalone wrapper: use the left stick for emulated GBA
        # directional movement. This avoids the D-pad path that opened the
        # in-game START menu on hardware during the first wild-engine test.
        self.bot.set_stick("LEFT",int(x),int(y))
        if not self._sleep(hold):
            self.bot.set_stick("LEFT",0,0); return False
        self.bot.set_stick("LEFT",0,0)
        return self._sleep(settle)

    def _spin_to_battle(self, hold=.045, settle=.055):
        """Rotate in place using the same proven left-stick transport as Wiggle.

        The previous implementation used Koi clickSeq. On hardware that path
        produced no movement at all, while the setStick path used by Wiggle
        works reliably. Keep Spin on that known-good transport and use short
        pulses so the avatar can turn without being driven across a tile.
        """
        self.bot.set_stick("LEFT", 0, 0)
        magnitude=0x7FFF
        directions=(
            (0, magnitude),       # Up
            (magnitude, 0),       # Right
            (0, -magnitude),      # Down
            (-magnitude, 0),      # Left
        )
        pulse=max(.030,min(.070,float(hold)))
        gap=max(.035,min(.090,float(settle)))

        while not self.stop_hunt_event.is_set() and not self._is_in_battle():
            for x, y in directions:
                if self.stop_hunt_event.is_set() or self._is_in_battle():
                    break

                # Use the exact same controller API as the working Wiggle
                # routine. Do not use clickSeq here.
                self.bot.set_stick("LEFT", x, y)
                if not self._sleep(pulse):
                    self.bot.set_stick("LEFT", 0, 0)
                    return False
                self.bot.set_stick("LEFT", 0, 0)
                if not self._sleep(gap):
                    return False

                if self._is_in_battle():
                    break

        self.bot.set_stick("LEFT", 0, 0)
        if self._is_in_battle():
            self._sleep(1.0)
            return True
        return False

    def _wiggle_to_battle(self):
        # Match the public FRLG routine more closely: keep one axis for the
        # whole search, then alternate axis only after a completed battle.
        self.bot.set_stick("LEFT",0,0)
        while not self.stop_hunt_event.is_set() and not self._is_in_battle():
            if self._wild_horizontal:
                if not self._stick_tap(0x7FFF,0): return False
                if not self._stick_tap(-0x8000,0): return False
            else:
                if not self._stick_tap(0,0x7FFF): return False
                if not self._stick_tap(0,-0x8000): return False
        self.bot.set_stick("LEFT",0,0)
        if self._is_in_battle(): self._sleep(1.0); return True
        return False

    def _escape_battle(self):
        self.status.emit({"state":"RUNNING","message":"Non-shiny — waiting for battle menu, then running…"})
        deadline=time.monotonic()+20
        while time.monotonic()<deadline and not self.stop_hunt_event.is_set() and not self._battle_menu_ready():
            # B clears battle text without selecting a command.
            self.bot.click("B"); self._sleep(.20)
        if self.stop_hunt_event.is_set(): return False
        if not self._battle_menu_ready(): raise RuntimeError("Battle menu did not become ready for Run")
        # Battle command grid:
        #   Fight | Bag
        #   PKMN  | Run
        #
        # Hardware testing showed RIGHT -> DOWN can leave the cursor on
        # PKMN when the RIGHT click is missed.  Use the other route:
        # DOWN -> RIGHT.  If DOWN is accepted, the cursor is on PKMN;
        # RIGHT then moves directly to Run.
        self.status.emit({"state":"RUNNING","message":"Selecting Run (DOWN, RIGHT)…"})
        self.bot.click("DDOWN")
        if not self._sleep(.35): return False
        self.bot.click("DRIGHT")
        if not self._sleep(.45): return False
        deadline=time.monotonic()+15
        while time.monotonic()<deadline and not self.stop_hunt_event.is_set() and self._is_in_battle():
            self.bot.click("A"); self._sleep(.20)
        if self._is_in_battle() and not self.stop_hunt_event.is_set(): raise RuntimeError("Could not escape the wild battle")

        # Battle RAM can clear slightly before FRLG has actually returned
        # control to the overworld. Starting Spin immediately at that point
        # can leak the first stick pulse into the post-battle transition and
        # make the player walk one tile. Require the overworld state to be
        # stable for several polls, with the stick held neutral throughout,
        # before allowing the next hunt movement to start.
        self.bot.set_stick("LEFT",0,0)
        ready=0
        deadline=time.monotonic()+5.0
        while time.monotonic()<deadline and not self.stop_hunt_event.is_set():
            if self._is_overworld():
                ready+=1
                if ready>=4:
                    break
            else:
                ready=0
            if not self._sleep(.08): return False
        if ready<4:
            raise RuntimeError("Overworld did not become stable after escaping the wild battle")
        if not self._sleep(.30): return False
        self.bot.set_stick("LEFT",0,0)
        self._wild_horizontal = not self._wild_horizontal
        return not self.stop_hunt_event.is_set()

    def _run_auto_capture_test(self,h,options):
        """One-shot hardware test for a non-shiny wild capture."""
        options=dict(options); options["auto_capture"]=True
        if self._first_empty_party_slot() is None:
            raise RuntimeError("Auto Capture Test needs an empty party slot")
        self._wild_horizontal=True
        self._wild_movement_mode=str(options.get("wild_movement_mode","wiggle") or "wiggle")
        spin_hold=max(.02,min(.20,float(options.get("spin_hold",.045) or .045)))
        spin_settle=max(.02,min(.20,float(options.get("spin_settle",.055) or .055)))
        self.status.emit({"state":"TESTING","message":"Auto Capture Test: searching for the first wild encounter…"})
        if self._wild_movement_mode=="spin":
            if not self._spin_to_battle(spin_hold,spin_settle): return
        elif not self._wiggle_to_battle(): return
        self._sleep(.8)
        p=parse_pk3(self.bot.read_heap(self.off.wild_pokemon,BOX_FORMAT_SLOT_SIZE))
        if not p.valid: raise RuntimeError("Auto Capture Test: wild PK3 was invalid")
        attempt=1
        if self._encounter(p,attempt,"Auto Capture Test",rng_context="wild"):
            self._shiny_home(species_name(p.species),attempt,"Auto Capture Test stopped — shiny safety")
            return
        self.status.emit({"state":"TESTING","message":f"Non-shiny {species_name(p.species)} confirmed — starting Auto Capture."})
        before=self._party_slots()
        # _auto_capture requires the live wild species ID so a successful
        # capture can be verified independently of the display label.
        capture_options=dict(options, _capture_species_id=int(p.species))
        if not self._auto_capture(capture_options,species_name(p.species)):
            return
        after=self._party_slots()
        caught=[x for x in after if x.valid and not x.is_egg and int(x.species)==int(p.species) and not x.shiny]
        if not caught or len(after)<=len(before):
            raise RuntimeError(f"Auto Capture Test could not verify {species_name(p.species)} in the party after capture")
        self.party.emit(after)
        self.status.emit({"state":"CAPTURE_TEST_PASS","message":f"AUTO CAPTURE TEST PASSED — {species_name(p.species)} was caught and verified in the party."})
        self.stop_hunt_event.set()

    def _run_wild(self,h,options):
        self._wild_horizontal=True
        self._wild_movement_mode=str(options.get("wild_movement_mode","wiggle") or "wiggle")
        spin_hold=max(.02,min(.20,float(options.get("spin_hold",.045) or .045)))
        spin_settle=max(.02,min(.20,float(options.get("spin_settle",.055) or .055)))
        attempt=0
        while not self.stop_hunt_event.is_set():
            movement_label="Spin" if self._wild_movement_mode=="spin" else "Wiggle"
            self.status.emit({"state":"HUNTING","message":f"Searching for a wild encounter… ({movement_label})","attempt":attempt})
            if self._wild_movement_mode=="spin":
                if not self._spin_to_battle(spin_hold,spin_settle): return
            else:
                if not self._wiggle_to_battle(): return
            p=parse_pk3(self.bot.read_heap(self.off.wild_pokemon,BOX_FORMAT_SLOT_SIZE))
            if not p.valid: raise RuntimeError("Battle started but wild PK3 was invalid")
            attempt+=1
            if self._encounter(p,attempt,"Wild encounter",rng_context="wild"):
                self._shiny_action(species_name(p.species),attempt,options); return
            if bool(options.get("auto_capture", False)):
                capture_options=dict(options, _capture_species_id=int(p.species))
                if self._auto_capture(capture_options, species_name(p.species)):
                    # A successful non-shiny capture is not the end of the
                    # hunt.  Return to the top of the wild loop so Spin/Wiggle
                    # resumes from the stable overworld after the catch flow.
                    continue
            else:
                if not self._escape_battle(): return

    def _run_fishing(self,h,options):
        attempt=0
        while not self.stop_hunt_event.is_set():
            self.status.emit({"state":"HUNTING","message":"Fishing…","attempt":attempt})
            deadline=time.monotonic()+30
            while time.monotonic()<deadline and not self.stop_hunt_event.is_set() and not self._is_in_battle():
                self.bot.click("Y"); self._sleep(.10); self.bot.click("B"); self._sleep(.10)
            if self.stop_hunt_event.is_set(): return
            if not self._is_in_battle(): raise RuntimeError("Fishing did not enter a battle within timeout. Check the registered rod/start position.")
            self._sleep(1.0); p=parse_pk3(self.bot.read_heap(self.off.wild_pokemon,BOX_FORMAT_SLOT_SIZE))
            if not p.valid: raise RuntimeError("Fishing battle started but wild PK3 was invalid")
            attempt+=1
            if self._encounter(p,attempt,"Fishing",rng_context="wild"):
                self._shiny_action(species_name(p.species),attempt,options); return
            if not self._escape_battle(): return

    def _gc_displacement(self,species):
        if species==63: return 0
        if species==35: return 1
        if species==147: return 2 if self.current_game=="FireRed" else 3
        if species==123:
            if self.current_game!="FireRed": raise RuntimeError("Scyther is not a LeafGreen Game Corner prize")
            return 3
        if species==127:
            if self.current_game!="LeafGreen": raise RuntimeError("Pinsir is not a FireRed Game Corner prize")
            return 2
        if species==137: return 4
        raise RuntimeError("Unknown Game Corner prize")

    def _select_gc_prize(self,disp):
        self.bot.click("A"); self._sleep(1.15); self.bot.click("A"); self._sleep(1.15)
        if disp<=3:
            for _ in range(disp): self.bot.click("DDOWN"); self._sleep(.28)
        else:
            self.bot.click("DUP"); self._sleep(.28); self.bot.click("DUP"); self._sleep(.28)

    def _run_game_corner(self,h,options):
        count=self._party_count()
        if count>=6: raise RuntimeError("Game Corner hunt needs at least one empty party slot")
        first_offset=self.off.party_start+count*PARTY_SLOT_STRIDE
        number=max(1,min(int(options.get("game_corner_number",1)),6-count))
        disp=self._gc_displacement(h.species); attempt=0
        while not self.stop_hunt_event.is_set():
            for purchased in range(number):
                if self.stop_hunt_event.is_set(): return
                self._select_gc_prize(disp); offset=first_offset+purchased*PARTY_SLOT_STRIDE
                p=self._acquire_pk(offset,"A",timeout=18)
                if p is None: raise RuntimeError("Game Corner prize did not appear in party within timeout")
                attempt+=1
                if self._encounter(p,attempt,f"Game Corner {h.label}",h.species):
                    self._shiny_home(h.label,attempt); return
                if purchased+1<number:
                    for _ in range(15): self.bot.click("B"); self._sleep(.25)
            self.status.emit({"state":"RESETTING","message":"No shiny prizes — soft resetting","attempt":attempt})
            if not self._after_soft_reset(first_offset): return
            self._sleep(2.0)

    def _ptr_to_heap(self,ptr):
        if ptr==0 or ptr<GBA_SAVE_BASE: return 0
        return INITIAL_SEED+(ptr-GBA_SAVE_BASE)

    def _save_ptr(self,shift):
        ptr=int.from_bytes(self.bot.read_heap(self.off.current_seed+shift,4),"little")
        return self._ptr_to_heap(ptr)

    def _trainer_ids(self):
        off=self._save_ptr(SMALL_SHIFT)
        if not off: raise RuntimeError("Small save block pointer is not loaded")
        data=self.bot.read_heap(off,0x10); return int.from_bytes(data[0xA:0xC],"little"),int.from_bytes(data[0xC:0xE],"little")

    def _read_roamer(self):
        large=self._save_ptr(LARGE_SHIFT)
        if not large: return None
        raw=self.bot.read_heap(large+0x30D0,0x14)
        iv32=int.from_bytes(raw[0:4],"little"); pid=int.from_bytes(raw[4:8],"little"); species=int.from_bytes(raw[8:10],"little"); level=raw[12]; active=raw[0x13]==1
        if not active or species==0 or pid==0: return None
        tid,sid=self._trainer_ids(); xor=tid^sid^(pid&0xFFFF)^(pid>>16)
        # FRLG roamer glitch: only the low IV byte is loaded into an encounter.
        g=iv32 & 0xFF
        ivs=[(g>>0)&31,(g>>5)&31,(g>>10)&31,(g>>15)&31,(g>>20)&31,(g>>25)&31]
        d={"valid":True,"checksum_ok":True,"pid":pid,"tid":tid,"sid":sid,"shiny":xor<8,"shiny_xor":xor,"species":species,
           "held_item":0,"experience":0,"friendship":0,"nature":NATURES[pid%25],"ability_slot":1,"is_egg":False,"pokerus":0,
           "iv_hp":ivs[0],"iv_atk":ivs[1],"iv_def":ivs[2],"iv_spe":ivs[3],"iv_spa":ivs[4],"iv_spd":ivs[5],
           "ev_hp":0,"ev_atk":0,"ev_def":0,"ev_spe":0,"ev_spa":0,"ev_spd":0,"move1":0,"move2":0,"move3":0,"move4":0,
           "move1_pp":0,"move2_pp":0,"move3_pp":0,"move4_pp":0,"raw_hex":raw.hex().upper(),"level":level,"roamer_iv_byte":g}
        d["name"]=species_name(species); d["iv_sum"]=sum(ivs); d["iv_spread"]=f"{ivs[0]}/{ivs[1]}/{ivs[2]}/{ivs[4]}/{ivs[5]}/{ivs[3]}"; d["ev_spread"]="0/0/0/0/0/0"
        return self._data_cache().enrich(d)

    def _run_roamer(self,h,options):
        attempt=0
        while not self.stop_hunt_event.is_set():
            self.status.emit({"state":"HUNTING","message":f"Attempt {attempt+1}: advancing roamer release event","attempt":attempt+1})
            for _ in range(50):
                if self.stop_hunt_event.is_set(): return
                self.bot.click("A"); self._sleep(random.uniform(.05,.18))
            deadline=time.monotonic()+20; d=None
            while time.monotonic()<deadline and not self.stop_hunt_event.is_set():
                for _ in range(3): self.bot.click("B"); self._sleep(random.uniform(.05,.15))
                d=self._read_roamer()
                if d: break
            if self.stop_hunt_event.is_set(): return
            if not d: raise RuntimeError("Roamer data did not become active within timeout")
            if h.species and d["species"]!=h.species: raise RuntimeError(f"Safety HOLD: expected {h.label} but roamer block contains {d['name']}")
            attempt+=1; d.update(self._rng_roamer_fields(d)); d["attempt"]=attempt; d["source"]=h.label; self.encounter.emit(d)
            if d["shiny"]:
                self._shiny_home(h.label,attempt); return
            self.status.emit({"state":"RESETTING","message":"Non-shiny roamer — soft resetting","attempt":attempt})
            if not self._after_soft_reset(): return

    def _take_item(self):
        self.bot.click("A"); self._sleep(.20)
        self.bot.click("DUP"); self._sleep(.20); self.bot.click("DUP"); self._sleep(.20)
        self.bot.click("A"); self._sleep(.20); self.bot.click("DDOWN"); self._sleep(.20)
        self.bot.click("A"); self._sleep(.80); self.bot.click("A"); self._sleep(.90)

    def _collect_pickup_items(self,items):
        if not any(items): return
        self.log.emit("Pickup: collecting held items")
        self.bot.click("X"); self._sleep(.50); self.bot.click("A"); self._sleep(1.80)
        if items[0]: self._take_item()
        self.bot.click("DRIGHT"); self._sleep(.20)
        cursor=1
        for idx in range(1,len(items)):
            if not items[idx]: continue
            while cursor<idx:
                self.bot.click("DDOWN"); self._sleep(.20); cursor+=1
            self._take_item(); cursor=idx
        self.bot.click("B"); self._sleep(1.50); self.bot.click("B"); self._sleep(.50)

    def _run_pickup(self,h,options):
        self._wild_horizontal=True
        # Mirrors the public FRLG Pickup routine's hunt/KO/item-take loop, but stops
        # safely when the lead Move 1 PP budget is exhausted rather than assuming a
        # map-specific auto-heal tile position.
        pickup_species={52,190,216,231,263,264}
        party=self._read_party(); valid=[p for p in party if p.get("valid")]
        if not valid: raise RuntimeError("Pickup mode needs a party")
        pickup_slots=[i for i,p in enumerate(valid) if p.get("ability_name")=="Pickup" or p.get("species") in pickup_species]
        if not pickup_slots: raise RuntimeError("No party Pokémon with the Gen-3 Pickup ability was detected")
        pp=int(valid[0].get("move1_pp",0))
        if pp<=0: raise RuntimeError("Lead Pokémon Move 1 has no PP")
        attempt=0
        while not self.stop_hunt_event.is_set():
            if not self._wiggle_to_battle(): return
            p=parse_pk3(self.bot.read_heap(self.off.wild_pokemon,BOX_FORMAT_SLOT_SIZE))
            if not p.valid: raise RuntimeError("Pickup battle started but wild PK3 was invalid")
            attempt+=1
            if self._encounter(p,attempt,"Pickup wild encounter",rng_context="wild"):
                self._shiny_home(species_name(p.species),attempt,"before KO"); return
            deadline=time.monotonic()+30
            while time.monotonic()<deadline and not self.stop_hunt_event.is_set() and self._is_in_battle():
                self.bot.click("A"); self._sleep(.20)
            if self._is_in_battle() and not self.stop_hunt_event.is_set(): raise RuntimeError("Pickup mode could not finish the battle with Move 1")
            self._sleep(.8); pp-=1
            now=self._read_party(); items=[0]*len(now)
            for i,pd in enumerate(now):
                if not pd.get("valid"): continue
                if i in pickup_slots and int(pd.get("held_item",0) or 0): items[i]=int(pd.get("held_item",0))
            if any(items): self._collect_pickup_items(items); self.party.emit(self._read_party())
            else: self.party.emit(now)
            if pp<=0:
                raise RuntimeError("Pickup lead Move 1 reached the starting PP limit. Heal/reposition, then restart Pickup mode.")

    def _fail(self,exc,phase):
        """Create exactly one diagnostic ZIP for a genuine failure.

        The JSON report lives inside the ZIP; no duplicate loose JSON file is
        left in AppData. Normal stops never call this function.
        """
        self.log.emit(f"{type(exc).__name__}: {exc}")
        try:
            root=appdata_root()/"support"
            root.mkdir(parents=True,exist_ok=True)
            stamp=datetime.now().strftime("%Y%m%d_%H%M%S")
            zp=root/f"PokebotSwitch_FRLG_support_{stamp}.zip"
            rec={"app":"PokebotSwitch-FRLG UI v0.17 RNG Controls Tab","timestamp":datetime.now().isoformat(timespec="seconds"),"phase":phase,
                 "game":self.current_game,"error":{"type":type(exc).__name__,"message":str(exc),"traceback":traceback.format_exc()},"command_log":list(self.bot.command_log) if self.bot else []}
            with zipfile.ZipFile(zp,"w",zipfile.ZIP_DEFLATED) as z:
                z.writestr(f"PokebotSwitch_FRLG_UI_{stamp}.json",json.dumps(rec,indent=2))
            self.support.emit(str(zp))
        except Exception:
            pass
