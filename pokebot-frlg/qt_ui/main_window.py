from __future__ import annotations
import os,time,json,zipfile
from PySide6.QtCore import QTimer,Qt
from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import (QMainWindow,QWidget,QVBoxLayout,QHBoxLayout,QGridLayout,QFrame,QLabel,QPushButton,QTabWidget,QTableWidget,QTableWidgetItem,QHeaderView,QComboBox,QLineEdit,QSpinBox,QDoubleSpinBox,QCheckBox,QFormLayout,QMessageBox,QScrollArea)
from pokebot_frlg.appdata_store import AppDataStore,appdata_root
from pokebot_frlg.backend import BackendWorker
from pokebot_frlg.discord_support import DiscordBotWorker,RichPresenceWorker
from pokebot_frlg.hunt_catalog import HUNTS,GROUPS,BY_KEY
from pokebot_frlg.gen3_data import get_sprite_path
from pokebot_frlg.pk3 import NATURES,species_name
from pokebot_frlg.oak_challenge import OAK_STAGES,STARTER_IDS,stage_species,all_checklist_ids,evolution_info,NATIONAL_EXTRA,oak_line_for_species,oak_line_target,oak_line_required,oak_starter_line,oak_starter_available_catches
from .theme import STYLE
from .widgets import StatBox,PartyCard,SpriteLabel

def _format_rng_miss(value):
    if value is None:
        return "—"
    try:
        n=int(value)
    except (TypeError,ValueError):
        return "—"
    if n==0:
        return "HIT"
    return f"{n:+,d}"

def _rng_tooltip(p):
    if not p.get("rng_supported"):
        return "Shiny-frame miss: this encounter did not provide a supported RNG reconstruction. No RNG manipulation is performed."
    if not p.get("rng_validated"):
        return f"Shiny-frame miss: {p.get('rng_method') or 'Gen III'} reconstruction did not validate against this Pokémon's observed RNG data, so no distance is shown. No RNG manipulation is performed."
    miss=_format_rng_miss(p.get("rng_miss"))
    cap=p.get("rng_capture_seed"); gen=p.get("rng_generation_seed")
    prev=p.get("rng_previous_shiny"); nxt=p.get("rng_next_shiny")
    lines=["Read-only retrospective RNG diagnostic",f"Method: {p.get('rng_method') or 'Gen III'}",f"Nearest shiny PID-start: {miss} RNG advances"]
    if prev is not None: lines.append(f"Previous shiny PID-start: -{int(prev):,d} advances" if int(prev) else "Previous shiny PID-start: current attempt")
    if nxt is not None: lines.append(f"Next shiny PID-start: +{int(nxt):,d} advances" if int(nxt) else "Next shiny PID-start: current attempt")
    if gen is not None: lines.append(f"Generation seed: 0x{int(gen)&0xFFFFFFFF:08X}")
    if cap is not None: lines.append(f"Captured live seed: 0x{int(cap)&0xFFFFFFFF:08X}")
    if p.get("rng_generation_to_capture") is not None: lines.append(f"Generation → capture read: {int(p['rng_generation_to_capture']):,d} advances")
    lines.append("Observation only: the bot does not wait for, target, write, or manipulate RNG states.")
    return "\n".join(lines)

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__(); self.setWindowTitle("PokebotSwitch-FRLG"); self.resize(1400,900); self.setMinimumSize(1180,760); self.setStyleSheet(STYLE)
        self.store=AppDataStore(); self.settings=self.store.load_settings(); self.rng_leads=dict(self.settings.get("rng_trigger_leads",{}) or {}); self.session_started_mono=None; self.session_started_epoch=None; self.session_elapsed_frozen=float(self.store.session.get("elapsed_seconds",0) if self.store.session else 0); self.connected=False; self.connected_game=None; self.hunting=False; self.last_support=""; self.last_hunt_label="—"; self.last_status="Idle"; self.last_party=[]; self.shiny_hold=False; self.discord_worker=None; self.rpc_worker=None
        self.worker=BackendWorker(); self.worker.connection.connect(self.on_connection); self.worker.party.connect(self.on_party); self.worker.encounter.connect(self.on_encounter); self.worker.status.connect(self.on_status); self.worker.log.connect(self.on_log); self.worker.support.connect(self.on_support); self.worker.display.connect(self.on_display); self.worker.rng_calibration.connect(self.on_rng_calibration); self.worker.utilities.connect(self.on_utilities); self.worker.start()
        self._build(); self._load_settings_ui(); self._refresh_stats(); self._last_elapsed_flush=0.0; self._restart_discord_services()
        self.clock=QTimer(self); self.clock.timeout.connect(self._tick); self.clock.start(500); QTimer.singleShot(250,self.connect_switch)

    def card(self,title):
        f=QFrame(); f.setObjectName("Card"); l=QVBoxLayout(f); l.setContentsMargins(12,10,12,10); h=QLabel(title); h.setObjectName("Section"); l.addWidget(h); return f,l

    def _build(self):
        root=QWidget(); outer=QVBoxLayout(root); outer.setContentsMargins(14,12,14,12); outer.setSpacing(10); self.setCentralWidget(root)
        hdr=QHBoxLayout(); title=QLabel("PokebotSwitch-FRLG"); title.setObjectName("Title"); hdr.addWidget(title); hdr.addStretch(); self.game_badge=QLabel("Not connected"); self.game_badge.setObjectName("Warn"); hdr.addWidget(self.game_badge); self.display_btn=QPushButton("Display Off"); self.display_btn.setToolTip("Turn the Switch display panel off/on using Koi botbase. The game and bot continue running."); self.display_btn.setEnabled(False); self.display_btn.clicked.connect(self.toggle_display); hdr.addWidget(self.display_btn); self.release_btn=QPushButton("Release Controller"); self.release_btn.setToolTip("Detach Koi's virtual controller so a physical controller can reconnect. Hunts also do this automatically when they stop."); self.release_btn.setEnabled(False); self.release_btn.clicked.connect(self.release_controller); hdr.addWidget(self.release_btn); self.conn_btn=QPushButton("Connect"); self.conn_btn.clicked.connect(self.connect_switch); hdr.addWidget(self.conn_btn); outer.addLayout(hdr)
        self.tabs=QTabWidget(); outer.addWidget(self.tabs,1); self._dashboard(); self._hunts(); self._wild_movement_page(); self._oak_challenge_page(); self._rng_page(); self._statistics(); self._settings_page(); self._support_page()

    def _dashboard(self):
        w=QWidget(); main=QHBoxLayout(w); main.setContentsMargins(0,8,0,0); left=QVBoxLayout(); right=QVBoxLayout(); main.addLayout(left,7); main.addLayout(right,3)
        c,l=self.card("Hunt control")
        row=QGridLayout(); self.group_combo=QComboBox(); self.target=QComboBox(); self.group_combo.addItems(GROUPS.keys()); self.group_combo.currentTextChanged.connect(self._populate_targets); self.target.currentIndexChanged.connect(self._hunt_changed)
        row.addWidget(QLabel("Category"),0,0); row.addWidget(self.group_combo,0,1); row.addWidget(QLabel("Hunt"),1,0); row.addWidget(self.target,1,1); l.addLayout(row)
        self.mode=QLabel("—"); self.mode.setStyleSheet("font-size:12pt;font-weight:700;"); l.addWidget(self.mode); self.setup=QLabel(""); self.setup.setObjectName("Muted"); self.setup.setWordWrap(True); l.addWidget(self.setup)
        gcrow=QHBoxLayout(); self.gc_label=QLabel("Game Corner prizes per reset"); self.gc_count=QSpinBox(); self.gc_count.setRange(1,5); gcrow.addWidget(self.gc_label); gcrow.addWidget(self.gc_count); gcrow.addStretch(); l.addLayout(gcrow)
        self.hunt_state=QLabel("Idle"); self.hunt_state.setObjectName("Muted"); l.addWidget(self.hunt_state)
        br=QHBoxLayout(); self.start_btn=QPushButton("Start Hunt"); self.start_btn.setObjectName("Start"); self.start_btn.clicked.connect(self.start_hunt); self.stop_btn=QPushButton("Stop"); self.stop_btn.setObjectName("Stop"); self.stop_btn.clicked.connect(self.stop_hunt); self.stop_btn.setEnabled(False); br.addWidget(self.start_btn); br.addWidget(self.stop_btn)
        util=QHBoxLayout(); util.addWidget(QLabel("Utilities:")); self.white_flute_status=QLabel("White Flute: —"); self.white_flute_status.setObjectName("Muted"); self.illuminate_status=QLabel("Illuminate: —"); self.illuminate_status.setObjectName("Muted"); util.addWidget(self.white_flute_status); util.addSpacing(10); util.addWidget(self.illuminate_status); util.addStretch(); br.addLayout(util); l.addLayout(br); left.addWidget(c)

        party_frame,pl=self.card("Live Party — RAM refreshes while idle"); grid=QGridLayout(); self.party_cards=[]
        for i in range(6): pc=PartyCard(i+1); self.party_cards.append(pc); grid.addWidget(pc,i//3,i%3)
        pl.addLayout(grid); left.addWidget(party_frame)

        seen,sl=self.card("Recently Seen — current session, newest first")
        self.seen=QTableWidget(0,9); self.seen.setHorizontalHeaderLabels(["","Pokémon","Nature","Ability","IVs","Σ","SV","RNG Miss","Hunt"]); self.seen.verticalHeader().setVisible(False); self.seen.setSelectionMode(QTableWidget.NoSelection); self.seen.setAlternatingRowColors(True); self.seen.setIconSize(self.seen.iconSize()); self.seen.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        header=self.seen.horizontalHeader(); header.setStretchLastSection(True)
        for i in range(9): header.setSectionResizeMode(i,QHeaderView.Interactive)
        for i,width in enumerate((54,108,80,106,162,44,58,86,108)): self.seen.setColumnWidth(i,width)
        sl.addWidget(self.seen); left.addWidget(seen,1)

        current,cl=self.card("Current / Last Seen")
        crow=QHBoxLayout(); self.current_sprite=SpriteLabel(92); crow.addWidget(self.current_sprite,0,Qt.AlignTop); ct=QVBoxLayout(); self.current_name=QLabel("—"); self.current_name.setStyleSheet("font-size:19pt;font-weight:750;"); self.current_detail=QLabel("No encounter seen this session"); self.current_detail.setWordWrap(True); ct.addWidget(self.current_name); ct.addWidget(self.current_detail); ct.addStretch(); crow.addLayout(ct,1); cl.addLayout(crow); right.addWidget(current)

        stats,st=self.card("Session"); g=QGridLayout(); self.s_enc=StatBox("Encounters"); self.s_shiny=StatBox("Shinies"); self.s_time=StatBox("Elapsed","00:00:00"); self.s_rate=StatBox("Encounters / hour","0.0"); g.addWidget(self.s_enc,0,0);g.addWidget(self.s_shiny,0,1);g.addWidget(self.s_time,1,0);g.addWidget(self.s_rate,1,1); st.addLayout(g); right.addWidget(stats)
        life,ll=self.card("Lifetime — AppData"); gl=QGridLayout(); self.l_enc=StatBox("Total encounters"); self.l_shiny=StatBox("Total shinies"); gl.addWidget(self.l_enc,0,0);gl.addWidget(self.l_shiny,0,1);ll.addLayout(gl); right.addWidget(life)
        cyc,cy=self.card("IV / SV — since last shiny"); self.cycle_high=QLabel("Highest IV: —"); self.cycle_low=QLabel("Lowest IV: —"); self.sv_high=QLabel("Highest SV: —"); self.sv_low=QLabel("Lowest SV: —"); [cy.addWidget(x) for x in (self.cycle_high,self.cycle_low,self.sv_high,self.sv_low)]; note=QLabel("These rolling records reset immediately after a shiny. Session encounters/shinies continue; lifetime totals never reset automatically."); note.setObjectName("Muted"); note.setWordWrap(True); cy.addWidget(note); right.addWidget(cyc); right.addStretch(); self.tabs.addTab(w,"DASHBOARD")
        self._populate_targets(self.group_combo.currentText()); self._push_discord_snapshot()

    def _hunts(self):
        page=QWidget(); root=QVBoxLayout(page); intro=QLabel("Named FRLG shiny hunts mapped to the RAM engines. In-game NPC trades are intentionally excluded because their received Pokémon are fixed rather than rerolled shiny targets."); intro.setWordWrap(True); root.addWidget(intro)
        scroll=QScrollArea(); scroll.setWidgetResizable(True); body=QWidget(); v=QVBoxLayout(body)
        for group,defs in GROUPS.items():
            c,l=self.card(group); grid=QGridLayout()
            for idx,h in enumerate(defs):
                f=QFrame(); f.setObjectName("PartyCard"); x=QVBoxLayout(f); a=QLabel(h.label); a.setStyleSheet("font-size:11pt;font-weight:700;"); a.setWordWrap(True); eng=QLabel(h.engine.replace('_',' ').title()); eng.setObjectName("Good"); games=QLabel(" / ".join(h.games)); games.setObjectName("Muted"); setup=QLabel(h.setup or "Uses the selected FRLG RAM routine."); setup.setWordWrap(True); setup.setObjectName("Muted"); x.addWidget(a); x.addWidget(eng); x.addWidget(games); x.addWidget(setup); grid.addWidget(f,idx//3,idx%3)
            l.addLayout(grid); v.addWidget(c)
        v.addStretch(); scroll.setWidget(body); root.addWidget(scroll,1); self.tabs.addTab(page,"HUNTS")

    def _wild_movement_page(self):
        w=QWidget(); outer=QVBoxLayout(w); outer.setContentsMargins(0,0,0,0); outer.setSpacing(0)
        scroll=QScrollArea(); scroll.setWidgetResizable(True); scroll.setFrameShape(QFrame.Shape.NoFrame); scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        content=QWidget(); v=QVBoxLayout(content); v.setContentsMargins(8,8,12,12); v.setSpacing(10)

        mode_card,ml=self.card("Wild encounter movement")
        intro=QLabel("Choose how the bot moves while searching for wild encounters. These controls apply only to the Wild engine; starter, gift, static, roaming and other hunt engines are unchanged.")
        intro.setWordWrap(True); intro.setObjectName("Muted"); ml.addWidget(intro)

        form=QFormLayout()
        self.movement_mode=QComboBox()
        self.movement_mode.addItem("Wiggle — walk back and forth","wiggle")
        self.movement_mode.addItem("Spin — rotate on one tile","spin")
        self.movement_mode.currentIndexChanged.connect(self._movement_changed)
        form.addRow("Movement mode",self.movement_mode)
        self.spin_hold=QDoubleSpinBox(); self.spin_hold.setRange(.02,.20); self.spin_hold.setSingleStep(.005); self.spin_hold.setDecimals(3); self.spin_hold.setValue(.045); self.spin_hold.setSuffix(" s")
        self.spin_settle=QDoubleSpinBox(); self.spin_settle.setRange(.02,.20); self.spin_settle.setSingleStep(.005); self.spin_settle.setDecimals(3); self.spin_settle.setValue(.055); self.spin_settle.setSuffix(" s")
        form.addRow("Spin tap duration",self.spin_hold)
        form.addRow("Spin neutral gap",self.spin_settle)
        ml.addLayout(form)

        self.spin_note=QLabel("Spin sends short clockwise Up → Right → Down → Left stick taps. The intent is to turn the character on the current tile without walking away. Start with the defaults and adjust the tap/gap values only if your setup moves off the tile.")
        self.spin_note.setObjectName("Muted"); self.spin_note.setWordWrap(True); ml.addWidget(self.spin_note)
        v.addWidget(mode_card)

        help_card,hl=self.card("How it works")
        cap_card,cv=self.card("AUTO CAPTURE")
        cap_row=QHBoxLayout()
        self.auto_capture=QCheckBox("Enable Auto Capture")
        self.auto_capture.setToolTip("When enabled, a non-shiny wild encounter is sent through the Poké Ball routine automatically. Shiny encounters still use the existing safety hold.")
        cap_row.addWidget(self.auto_capture)
        cap_row.addWidget(QLabel("Ball slot"))
        self.capture_ball_slot=QSpinBox(); self.capture_ball_slot.setRange(1,6); self.capture_ball_slot.setValue(1); self.capture_ball_slot.setToolTip("Position in the Poké Balls pocket: 1 is the first listed ball.")
        cap_row.addWidget(self.capture_ball_slot)
        cap_row.addWidget(QLabel("Max throws"))
        self.capture_max_throws=QSpinBox(); self.capture_max_throws.setRange(1,99); self.capture_max_throws.setValue(10)
        cap_row.addWidget(self.capture_max_throws); cap_row.addStretch(); cv.addLayout(cap_row)
        self.capture_test_mode=QCheckBox("Test non-shiny Auto Capture (one-shot)")
        self.capture_test_mode.setToolTip("When enabled, Start Hunt runs the dedicated one-shot Auto Capture test. The first wild non-shiny is caught, verified in the party, and the bot stops. This toggle is not saved between launches.")
        cap_row2=QHBoxLayout(); cap_row2.addWidget(self.capture_test_mode)
        self.capture_test_btn=QPushButton("Start Capture Test")
        self.capture_test_btn.setToolTip("Run the dedicated first non-shiny Auto Capture hardware test immediately.")
        self.capture_test_btn.clicked.connect(self.start_capture_test)
        cap_row2.addWidget(self.capture_test_btn); cap_row2.addStretch(); cv.addLayout(cap_row2)
        cap_note=QLabel("Auto Capture is optional and bounded. It opens the battle Bag, switches to the Poké Balls pocket, selects the configured ball entry, and retries up to the limit. If the limit is reached, the bot escapes. For the test, the first non-shiny is caught and verified, then the hunt stops. A shiny follows the Settings → Shiny encounter action choice.")
        cap_note.setWordWrap(True); cap_note.setObjectName("Muted"); cv.addWidget(cap_note); v.addWidget(cap_card)

        egg_card,el=self.card("EGGS / BREEDING")
        egg_form=QFormLayout()
        self.egg_release_nonshiny=QCheckBox("Release non-shiny hatched Pokémon")
        self.egg_release_nonshiny.setChecked(True)
        self.egg_max_eggs=QSpinBox(); self.egg_max_eggs.setRange(1,99); self.egg_max_eggs.setValue(1)
        self.egg_hatch_hold=QDoubleSpinBox(); self.egg_hatch_hold.setRange(.05,2.0); self.egg_hatch_hold.setSingleStep(.05); self.egg_hatch_hold.setDecimals(2); self.egg_hatch_hold.setValue(.35); self.egg_hatch_hold.setSuffix(" s")
        self.egg_hatch_cycles=QSpinBox(); self.egg_hatch_cycles.setRange(1,5000); self.egg_hatch_cycles.setValue(900)
        egg_form.addRow("After hatching",self.egg_release_nonshiny)
        egg_form.addRow("Maximum eggs per run",self.egg_max_eggs)
        egg_form.addRow("Hatch movement hold",self.egg_hatch_hold)
        egg_form.addRow("Maximum hatch cycles",self.egg_hatch_cycles)
        el.addLayout(egg_form)
        egg_note=QLabel("Egg collection and hatching are configured here with Wild Movement because they are movement-driven. Oak Challenge breeding remains locked until the Four Island breeding checkpoint is enabled.")
        egg_note.setWordWrap(True); egg_note.setObjectName("Muted"); el.addWidget(egg_note)
        v.addWidget(egg_card)

        help_text=QLabel("Wiggle: alternates the existing horizontal/vertical search pattern.\n\nSpin: repeats a four-direction clockwise rotation and checks for the encounter after each rotation cycle.\n\nThe selected mode is saved with the app settings and is passed to the Wild engine when a hunt starts.")
        help_text.setWordWrap(True); hl.addWidget(help_text); v.addWidget(help_card)
        v.addStretch()
        scroll.setWidget(content); outer.addWidget(scroll,1); self.tabs.addTab(w,"WILD MOVEMENT")

    def _oak_challenge_page(self):
        w=QWidget(); v=QVBoxLayout(w); v.setContentsMargins(0,8,0,0); v.setSpacing(10)

        info,l=self.card("Professor Oak Challenge — Full FR/LG Checklist")
        intro=QLabel("Full Oak Challenge tracker: work through the entire checklist, not just the first three checkpoints. Evolution lines use catch-count progression: for Pidgey → Pidgeotto → Pidgeot, three Pidgey catches complete the three rows in order. The line is only blocked after the final catch.")
        intro.setWordWrap(True); intro.setObjectName("Muted"); l.addWidget(intro)
        rule=QLabel("Oak rules vary slightly between guides and players. This tracker follows the classic FRLG progression: maximise the available Pokédex before the next required badge/HM, then finish the Kanto and National-Dex post-game work. Evolution requirements are shown for reference; the bot never changes your save or evolves Pokémon automatically.")
        rule.setWordWrap(True); l.addWidget(rule); v.addWidget(info)

        cfg,cl=self.card("Oak progress")
        form=QFormLayout()
        self.oak_stage=QComboBox(); self.oak_stage.addItems(["All checkpoints"]+OAK_STAGES); self.oak_stage.currentTextChanged.connect(self._oak_stage_changed)
        form.addRow("View checkpoint",self.oak_stage)
        self.oak_starter_status=QLabel("Starter: not selected")
        self.oak_starter_status.setObjectName("Muted")
        form.addRow("Selected starter",self.oak_starter_status)
        self.oak_targets=QLineEdit(); self.oak_targets.setPlaceholderText("Leave blank to use all eligible unfinished evolution lines in the selected checkpoint")
        form.addRow("Required target override",self.oak_targets)
        self.oak_blocked=QLineEdit(); self.oak_blocked.setPlaceholderText("Extra manual block list, e.g. Pidgey, Rattata")
        form.addRow("Block list",self.oak_blocked)
        cl.addLayout(form)

        tools=QHBoxLayout()
        self.oak_breeding_unlocked=QCheckBox("Breeding / egg hatching unlocked (Four Island)")
        self.oak_breeding_unlocked.setToolTip("FRLG breeding becomes available at the Four Island Day Care after entering the Hall of Fame. Before this is enabled, the selected starter is limited to the single starter received from Oak.")
        self.oak_breeding_unlocked.stateChanged.connect(lambda _state:(self._oak_refresh_table(), self.save_settings()))
        tools.addWidget(self.oak_breeding_unlocked)
        self.oak_use_checklist=QCheckBox("Use unfinished checklist rows as targets")
        self.oak_use_checklist.setChecked(True); tools.addWidget(self.oak_use_checklist)
        mark=QPushButton("Mark visible complete"); mark.clicked.connect(lambda:self._oak_set_visible_checked(True)); tools.addWidget(mark)
        unmark=QPushButton("Uncheck visible"); unmark.clicked.connect(lambda:self._oak_set_visible_checked(False)); tools.addWidget(unmark)
        tools.addStretch(); cl.addLayout(tools)
        note=QLabel("Automatic blocking happens only when an evolution line reaches its full catch count. For example, Pidgey stays targetable at 1/3 and 2/3, then the entire Pidgey → Pidgeotto → Pidgeot line is blocked at 3/3. You can still add temporary/manual blocks in the Block list field.")
        note.setWordWrap(True); note.setObjectName("Muted"); cl.addWidget(note); v.addWidget(cfg)

        table_card,tl=self.card("Pokémon checklist")
        filter_row=QHBoxLayout(); filter_row.addWidget(QLabel("Search")); self.oak_search=QLineEdit(); self.oak_search.setPlaceholderText("Search Pokémon…"); self.oak_search.textChanged.connect(self._oak_refresh_table); filter_row.addWidget(self.oak_search,2); filter_row.addWidget(QLabel("Progress")); self.oak_progress=QLabel("0 / 0 complete"); self.oak_progress.setObjectName("Muted"); filter_row.addWidget(self.oak_progress); tl.addLayout(filter_row)
        self.oak_table=QTableWidget(0,5); self.oak_table.setHorizontalHeaderLabels(["Done","Checkpoint","Pokémon","Evolution / requirement","Source"]); self.oak_table.verticalHeader().setVisible(False); self.oak_table.setAlternatingRowColors(True); self.oak_table.setSelectionMode(QTableWidget.NoSelection); self.oak_table.setEditTriggers(QTableWidget.NoEditTriggers)
        hh=self.oak_table.horizontalHeader(); hh.setSectionResizeMode(0,QHeaderView.ResizeToContents); hh.setSectionResizeMode(1,QHeaderView.ResizeToContents); hh.setSectionResizeMode(2,QHeaderView.ResizeToContents); hh.setSectionResizeMode(3,QHeaderView.Stretch); hh.setSectionResizeMode(4,QHeaderView.ResizeToContents)
        tl.addWidget(self.oak_table,1); v.addWidget(table_card,1)

        ref,rl=self.card("Oak notes")
        self.oak_reference=QLabel(""); self.oak_reference.setWordWrap(True); self.oak_reference.setObjectName("Muted"); rl.addWidget(self.oak_reference); v.addWidget(ref)
        self.tabs.addTab(w,"OAK CHALLENGE")
        self._oak_completed=set(int(x) for x in (self.settings.get("oak_completed_ids",[]) or []) if str(x).isdigit())
        self._oak_line_counts={int(k):int(v) for k,v in (self.settings.get("oak_line_counts",{}) or {}).items() if str(k).isdigit()}
        self._oak_refresh_table()
        self._oak_stage_changed(self.oak_stage.currentText())

    def _oak_stage_for_id(self,sid):
        if sid in STARTER_IDS or sid in (2,3,5,6,8,9): return OAK_STAGES[0]
        for stage in OAK_STAGES:
            if sid in stage_species(stage,self.connected_game): return stage
        if sid in NATIONAL_EXTRA: return "Post-Game — National Dex"
        return "Post-Game — Kanto Dex"

    def _selected_starter_species(self):
        key=self.settings.get("starter_hunt_key")
        h=BY_KEY.get(key) if key else None
        if h and h.engine=="starter" and h.species in STARTER_IDS:
            return int(h.species)
        current=self.target.currentData() if hasattr(self,"target") else None
        h=BY_KEY.get(current) if current else None
        if h and h.engine=="starter" and h.species in STARTER_IDS:
            return int(h.species)
        return None

    def _oak_available_catches(self,base):
        starter=self._selected_starter_species()
        if base in STARTER_IDS:
            if base != starter: return 0
            return oak_starter_available_catches(starter, bool(self.oak_breeding_unlocked.isChecked()))
        return oak_line_required(base)

    def _oak_availability(self,sid):
        if sid in STARTER_IDS:
            starter=self._selected_starter_species()
            if sid != starter: return "Different starter — not selected"
            if self.oak_breeding_unlocked.isChecked(): return "Selected starter — breeding/eggs unlocked"
            return "Selected starter — 1 available until breeding"
        if sid==151: return "Mew / event-only"
        if sid in (65,68,75): return "Trade evolution"
        if sid in (27,28,37,38,43,44,45,52,53,69,70,71,120,121,122,126,136,139,140,141): return "Version-dependent"
        return "Track"

    def _oak_visible_ids(self):
        ids=all_checklist_ids(self.connected_game)
        # The checklist must use the starter selected on the Starter hunt.
        # Remove the hard-coded starter line and insert the selected line.
        ids=[sid for sid in ids if sid not in set(sum(([1,2,3],[4,5,6],[7,8,9]), []))]
        starter_line=oak_starter_line(self._selected_starter_species())
        if starter_line:
            ids=list(starter_line)+ids
        stage=self.oak_stage.currentText() if hasattr(self,"oak_stage") else "All checkpoints"
        if stage and stage!="All checkpoints": ids=[sid for sid in ids if self._oak_stage_for_id(sid)==stage]
        q=self.oak_search.text().strip().lower() if hasattr(self,"oak_search") else ""
        if q: ids=[sid for sid in ids if q in species_name(sid).lower() or q in str(sid)]
        return list(dict.fromkeys(ids))

    def _oak_refresh_table(self):
        if not hasattr(self,"oak_table"): return
        ids=self._oak_visible_ids(); self.oak_table.setRowCount(0)
        for sid in ids:
            r=self.oak_table.rowCount(); self.oak_table.insertRow(r)
            cb=QCheckBox(); cb.setChecked(sid in self._oak_completed)
            line=oak_line_for_species(sid); base=line[0]; count=int(self._oak_line_counts.get(base,0)); available=self._oak_available_catches(base)
            cb.setEnabled(base not in STARTER_IDS or available > count or sid in self._oak_completed)
            cb.stateChanged.connect(lambda state,s=sid:self._oak_row_changed(s,state))
            holder=QWidget(); hl=QHBoxLayout(holder); hl.setContentsMargins(0,0,0,0); hl.setAlignment(Qt.AlignCenter); hl.addWidget(cb); self.oak_table.setCellWidget(r,0,holder)
            self.oak_table.setItem(r,1,QTableWidgetItem(self._oak_stage_for_id(sid)))
            self.oak_table.setItem(r,2,QTableWidgetItem(species_name(sid)))
            line=oak_line_for_species(sid); count=int(self._oak_line_counts.get(line[0],0)); required=len(line); available=self._oak_available_catches(line[0])
            if line[0] in STARTER_IDS:
                progress=f"Catch progress {min(count,required)}/{required} • Available now {min(count,available)}/{available or 0} • "
            else:
                progress=f"Catch progress {min(count,required)}/{required} • "
            self.oak_table.setItem(r,3,QTableWidgetItem(progress+evolution_info(sid)))
            source=("National Dex" if sid in NATIONAL_EXTRA else "Kanto Dex") + " — " + self._oak_availability(sid)
            self.oak_table.setItem(r,4,QTableWidgetItem(source))
        self._oak_update_progress()

    def _oak_row_changed(self,sid,state):
        sid=int(sid); line=oak_line_for_species(sid); base=line[0]; idx=line.index(sid)
        available=self._oak_available_catches(base)
        if state:
            if available <= idx: return
            count=idx+1
            self._oak_line_counts[base]=count
            for row_sid in line[:count]: self._oak_completed.add(int(row_sid))
        else:
            count=idx
            self._oak_line_counts[base]=count
            for row_sid in line[count:]: self._oak_completed.discard(int(row_sid))
        self._oak_rebuild_blocklist(); self._oak_refresh_table(); self.save_settings()

    def _oak_set_visible_checked(self,checked):
        for sid in self._oak_visible_ids():
            if checked: self._oak_completed.add(int(sid))
            else: self._oak_completed.discard(int(sid))
        self._oak_rebuild_blocklist(); self._oak_refresh_table(); self.save_settings()

    def _oak_rebuild_blocklist(self):
        # Only fully completed evolution lines are automatically blocked.
        # A 1/3 Pidgey line therefore does NOT block Pidgey yet.
        completed_lines=[]
        for sid in all_checklist_ids(self.connected_game):
            line=oak_line_for_species(sid); base=line[0]
            if base in completed_lines: continue
            if int(self._oak_line_counts.get(base,0)) >= len(line):
                completed_lines.append(base)
        completed=[]
        for base in completed_lines:
            completed.extend(species_name(x) for x in oak_line_for_species(base))
        manual=[]
        completed_l={x.lower() for x in completed}
        for token in str(self.oak_blocked.text() or "").split(","):
            token=token.strip()
            if token and token.lower() not in completed_l: manual.append(token)
        self.oak_blocked.setText(", ".join(manual+completed))

    def _oak_update_progress(self):
        all_ids=all_checklist_ids(self.connected_game); done=sum(1 for sid in all_ids if sid in self._oak_completed)
        self.oak_progress.setText(f"{done} / {len(all_ids)} complete")

    def _oak_register_capture(self,species_id):
        """Count an auto-captured Pokémon against its Oak evolution line.

        The caught species itself is not what determines completion. The line's
        catch count advances one step, so Pidgey catches complete Pidgey, then
        Pidgeotto, then Pidgeot. The line is only blocked at 3/3.
        """
        try: sid=int(species_id)
        except (TypeError,ValueError): return
        line=oak_line_for_species(sid); base=line[0]; required=len(line)
        count=min(required,int(self._oak_line_counts.get(base,0))+1)
        self._oak_line_counts[base]=count
        # Mark the first N checklist entries in this line complete.
        for row_sid in line[:count]: self._oak_completed.add(int(row_sid))
        self._oak_rebuild_blocklist(); self._oak_refresh_table(); self.save_settings()
        names=[species_name(x) for x in line[:count]]
        if count>=required:
            self.last_status=f"Oak line complete: {species_name(base)} — {required}/{required}; entire line blocked."
        else:
            self.last_status=f"Oak progress: {species_name(base)} — {count}/{required}; next required: {species_name(line[count])}."
        self.hunt_state.setText(self.last_status)

    def _oak_stage_changed(self,stage):
        if not hasattr(self,"oak_reference"): return
        ids=self._oak_visible_ids() if hasattr(self,"oak_table") else []
        if stage=="All checkpoints":
            self.oak_reference.setText(f"Full checklist: {len(all_checklist_ids(self.connected_game))} tracked species/entries. Select a checkpoint to focus the list.")
        else:
            self.oak_reference.setText(f"{stage}: {len(ids)} tracked entries in this view. Progress is counted by evolution line; the table shows the current catch count for each row.")
        self._oak_refresh_table()

    def _oak_load_stage(self):
        ids=self._oak_visible_ids()
        self.oak_targets.setText(", ".join(species_name(i) for i in ids if i not in self._oak_completed))

    def _species_ids_from_text(self,text):
        wanted={x.strip().lower() for x in str(text or "").split(",") if x.strip()}
        if not wanted: return []
        lookup={species_name(i).strip().lower():i for i in range(1,387)}
        out=[]
        for token in wanted:
            if token.isdigit() and 1<=int(token)<=386: out.append(int(token))
            elif token in lookup: out.append(lookup[token])
        return list(dict.fromkeys(out))

    def _rng_page(self):
        w=QWidget(); v=QVBoxLayout(w); v.setContentsMargins(0,8,0,0); v.setSpacing(10)

        status,sl=self.card("Automatic RNG — live Gen III seed targeting")
        self.auto_rng=QCheckBox("Enable Automatic RNG for the selected hunt")
        self.auto_rng.setToolTip("Experimental live-seed mode. Currently enabled only for Starter, Gift and Static engines. RAM remains read-only; the bot times controller input against the observed RNG stream.")
        sl.addWidget(self.auto_rng)
        self.rng_current_hunt=QLabel("Selected hunt: —")
        self.rng_current_hunt.setStyleSheet("font-size:13pt;font-weight:700;")
        sl.addWidget(self.rng_current_hunt)
        self.rng_support=QLabel("Live-seed RNG targeting: starters / gifts / statics")
        self.rng_support.setObjectName("Muted"); self.rng_support.setWordWrap(True); sl.addWidget(self.rng_support)
        mode_note=QLabel("Choose the hunt on the Dashboard, then configure its RNG target here. Automatic RNG is opt-in; normal shiny hunting is unchanged when this is disabled.")
        mode_note.setObjectName("Muted"); mode_note.setWordWrap(True); sl.addWidget(mode_note)
        v.addWidget(status)

        target,tl=self.card("RNG target")
        top=QGridLayout()
        self.rng_shiny=QCheckBox("Shiny only"); self.rng_shiny.setChecked(True)
        self.rng_nature=QComboBox(); self.rng_nature.addItem("Any",-1)
        for i,name in enumerate(NATURES): self.rng_nature.addItem(name,i)
        self.rng_max=QSpinBox(); self.rng_max.setRange(1000,5000000); self.rng_max.setSingleStep(10000); self.rng_max.setValue(500000); self.rng_max.setSuffix(" advances")
        top.addWidget(self.rng_shiny,0,0,1,2)
        top.addWidget(QLabel("Nature"),1,0); top.addWidget(self.rng_nature,1,1)
        top.addWidget(QLabel("Maximum forward search"),2,0); top.addWidget(self.rng_max,2,1)
        top.setColumnStretch(1,1)
        tl.addLayout(top)

        iv_title=QLabel("Minimum IVs")
        iv_title.setStyleSheet("font-size:11pt;font-weight:700;"); tl.addWidget(iv_title)
        ivgrid=QGridLayout(); self.rng_iv_boxes=[]
        for col,label in enumerate(("HP","Atk","Def","SpA","SpD","Spe")):
            lab=QLabel(label); lab.setAlignment(Qt.AlignCenter)
            box=QSpinBox(); box.setRange(0,31); box.setValue(0); box.setAlignment(Qt.AlignCenter)
            self.rng_iv_boxes.append(box); ivgrid.addWidget(lab,0,col); ivgrid.addWidget(box,1,col)
        tl.addLayout(ivgrid)
        ivnote=QLabel("Leave all IV minimums at 0 during first calibration. Once timing is stable, raise only the stats you want to target.")
        ivnote.setObjectName("Muted"); ivnote.setWordWrap(True); tl.addWidget(ivnote)
        v.addWidget(target)

        cal,cl=self.card("Timing calibration")
        cf=QFormLayout()
        self.rng_lead=QSpinBox(); self.rng_lead.setRange(0,20000); self.rng_lead.setSingleStep(10); self.rng_lead.setSuffix(" advances")
        self.rng_lead.setToolTip("Estimated RNG advances from the timed trigger to PID generation. The bot adjusts this automatically after each miss and remembers it per hunt.")
        cf.addRow("Trigger lead",self.rng_lead); cl.addLayout(cf)
        self.rng_calibration_status=QLabel("No automatic calibration result yet for this run.")
        self.rng_calibration_status.setObjectName("Muted"); self.rng_calibration_status.setWordWrap(True); cl.addWidget(self.rng_calibration_status)
        calnote=QLabel("After a miss, the bot compares the generated Pokémon with the predicted frame and updates the per-hunt trigger lead automatically. This value is stored in AppData.")
        calnote.setObjectName("Muted"); calnote.setWordWrap(True); cl.addWidget(calnote)
        v.addWidget(cal)

        buttons=QHBoxLayout(); save=QPushButton("Save RNG Settings"); save.clicked.connect(self.save_settings); buttons.addWidget(save); buttons.addStretch(); v.addLayout(buttons)
        v.addStretch(); self.tabs.addTab(w,"RNG")

    def _statistics(self):
        w=QWidget(); v=QVBoxLayout(w); c,l=self.card("Statistics storage"); self.stats_path=QLabel(str(appdata_root())); self.stats_path.setWordWrap(True); l.addWidget(QLabel("All lifetime and current-session statistics are stored under:")); l.addWidget(self.stats_path); explain=QLabel("New session: resets session counters, shinies, recently seen, Current/Last, timer, rate and IV/SV records.\nShiny found: increments session/lifetime shiny totals, preserves encounter totals, then resets only the rolling IV/SV records.\nLifetime: total encounters and total shinies persist across sessions, restarts and program upgrades."); explain.setWordWrap(True); l.addWidget(explain); v.addWidget(c); v.addStretch(); self.tabs.addTab(w,"STATISTICS")

    def _settings_page(self):
        w=QWidget(); outer=QVBoxLayout(w); outer.setContentsMargins(0,0,0,0)
        scroll=QScrollArea(); scroll.setWidgetResizable(True); scroll.setFrameShape(QFrame.Shape.NoFrame); scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        content=QWidget(); content.setMinimumWidth(760); v=QVBoxLayout(content); v.setContentsMargins(8,8,12,12); v.setSpacing(10)
        c,l=self.card("Connection & UI Settings"); form=QFormLayout(); form.setRowWrapPolicy(QFormLayout.WrapLongRows); form.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow); self.ip=QLineEdit(); self.ip.setMinimumWidth(240); self.port=QSpinBox(); self.port.setRange(1,65535); self.port.setMinimumWidth(160); self.interval=QDoubleSpinBox(); self.interval.setRange(.25,5); self.interval.setSingleStep(.05); self.interval.setSuffix(" s"); self.interval.setMinimumWidth(160); self.top=QCheckBox("Keep PokebotSwitch-FRLG above other windows"); form.addRow("Switch IP",self.ip);form.addRow("Koi botbase port",self.port);form.addRow("Idle party refresh",self.interval);form.addRow("",self.top); l.addLayout(form); note=QLabel("FRLG sprites and the full Gen-3 ability table are cached under AppData on first use. Named hunt species have an offline ability fallback. The header Display Off/On toggle uses Koi botbase screenOff/screenOn and does not pause the game or hunt."); note.setWordWrap(True); note.setObjectName("Muted"); l.addWidget(note); v.addWidget(c)

        sa,sl=self.card("Shiny encounter action")
        self.shiny_auto_capture=QCheckBox("Auto-capture a shiny instead of sending the Switch to HOME")
        self.shiny_auto_capture.setToolTip("OFF preserves the original shiny safety behavior: press HOME and stop. ON sends the shiny through the configured Poké Ball routine and then stops after the capture.")
        sl.addWidget(self.shiny_auto_capture)
        sn=QLabel("This setting affects wild/fishing shiny encounters. Starter, gift, static, egg and other safety-critical routines continue to use their existing shiny protection.")
        sn.setWordWrap(True); sn.setObjectName("Muted"); sl.addWidget(sn)
        v.addWidget(sa)

        dc,dl=self.card("Discord — ORAS-style monitoring / notifications")
        self.discord_enable=QCheckBox("Enable Discord bot-account support")
        self.discord_token=QLineEdit(); self.discord_token.setEchoMode(QLineEdit.EchoMode.Password); self.discord_token.setPlaceholderText("Discord bot token")
        self.discord_channel=QLineEdit(); self.discord_channel.setPlaceholderText("Channel ID")
        self.discord_notify_status=QCheckBox("Post hunt start / stop and Switch connection status")
        self.discord_notify_safety=QCheckBox("Post safety-hold notifications")
        df=QFormLayout(); df.setRowWrapPolicy(QFormLayout.WrapLongRows); df.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow); self.discord_token.setMinimumWidth(300); self.discord_channel.setMinimumWidth(240); df.addRow("",self.discord_enable); df.addRow("Bot token",self.discord_token); df.addRow("Channel ID",self.discord_channel); df.addRow("",self.discord_notify_status); df.addRow("",self.discord_notify_safety); dl.addLayout(df)
        self.discord_state=QLabel("Discord: disabled"); self.discord_state.setObjectName("Muted"); dl.addWidget(self.discord_state)
        dn=QLabel("Discord is monitoring/presentation only. RAM and the hunt state machine remain the sole shiny/reset authority. Shiny notifications are always posted when the Discord bot is enabled."); dn.setWordWrap(True); dn.setObjectName("Muted"); dl.addWidget(dn)
        dbr=QHBoxLayout(); test=QPushButton("Send Discord Test"); test.clicked.connect(self.test_discord); dbr.addWidget(test); dbr.addStretch(); dl.addLayout(dbr); v.addWidget(dc)

        rc,rl=self.card("Discord Rich Presence")
        self.rpc_enable=QCheckBox("Enable Discord Rich Presence")
        self.rpc_client=QLineEdit(); self.rpc_client.setPlaceholderText("Discord application / client ID")
        rf=QFormLayout(); rf.setRowWrapPolicy(QFormLayout.WrapLongRows); rf.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow); self.rpc_client.setMinimumWidth(300); rf.addRow("",self.rpc_enable); rf.addRow("Application ID",self.rpc_client); rl.addLayout(rf); self.rpc_state=QLabel("Rich Presence: disabled"); self.rpc_state.setObjectName("Muted"); rl.addWidget(self.rpc_state); rpc_note=QLabel("Rich Presence large image: upload the combined FireRed / LeafGreen game logo to this Discord application as the Art Asset key  frlg-logo  (Discord lowercases asset keys). The bot references that key automatically, matching the ORAS-style game-logo presence."); rpc_note.setWordWrap(True); rpc_note.setObjectName("Muted"); rl.addWidget(rpc_note); v.addWidget(rc)

        save=QPushButton("Save Settings"); save.clicked.connect(self.save_settings); v.addWidget(save,0,Qt.AlignLeft); v.addStretch()
        scroll.setWidget(content); outer.addWidget(scroll); self.tabs.addTab(w,"SETTINGS")

    def _support_page(self):
        w=QWidget(); v=QVBoxLayout(w); c,l=self.card("Testing / Support"); self.log_label=QLabel("No support errors this run."); self.log_label.setWordWrap(True); self.support_label=QLabel("No failure support ZIP created this run."); self.support_label.setWordWrap(True); l.addWidget(self.log_label); l.addWidget(QLabel("Failure support ZIP:")); l.addWidget(self.support_label); openb=QPushButton("Open AppData Folder"); openb.clicked.connect(self.open_appdata); l.addWidget(openb,0,Qt.AlignLeft); v.addWidget(c); v.addStretch(); self.tabs.addTab(w,"TESTING / SUPPORT")

    def _load_settings_ui(self):
        self.movement_mode.setCurrentIndex(max(0,self.movement_mode.findData(self.settings.get("wild_movement_mode","wiggle"))))
        self.spin_hold.setValue(float(self.settings.get("spin_hold",.045) or .045)); self.spin_settle.setValue(float(self.settings.get("spin_settle",.055) or .055)); self.auto_capture.setChecked(bool(self.settings.get("auto_capture",False))); self.shiny_auto_capture.setChecked(bool(self.settings.get("shiny_auto_capture",False))); self.capture_ball_slot.setValue(int(self.settings.get("capture_ball_slot",1) or 1)); self.capture_max_throws.setValue(int(self.settings.get("capture_max_throws",10) or 10)); self._movement_changed()
        self.ip.setText(self.settings.get("switch_ip","192.168.1.162")); self.port.setValue(int(self.settings.get("port",6000))); self.interval.setValue(float(self.settings.get("monitor_interval",.75))); self.top.setChecked(bool(self.settings.get("always_on_top",False))); self.gc_count.setValue(int(self.settings.get("game_corner_number",1))); self.egg_release_nonshiny.setChecked(bool(self.settings.get("egg_release_nonshiny",True))); self.egg_max_eggs.setValue(int(self.settings.get("egg_max_eggs",1) or 1)); self.egg_hatch_hold.setValue(float(self.settings.get("egg_hatch_hold",.35) or .35)); self.egg_hatch_cycles.setValue(int(self.settings.get("egg_hatch_cycles",900) or 900)); self._apply_top()
        self.discord_enable.setChecked(bool(self.settings.get("discord_bot_enabled",False))); self.discord_token.setText(str(self.settings.get("discord_bot_token","") or "")); self.discord_channel.setText(str(self.settings.get("discord_channel_id","") or "")); self.discord_notify_status.setChecked(bool(self.settings.get("discord_notify_status",True))); self.discord_notify_safety.setChecked(bool(self.settings.get("discord_notify_safety",True))); self.rpc_enable.setChecked(bool(self.settings.get("discord_rich_presence_enabled",False))); self.rpc_client.setText(str(self.settings.get("discord_rpc_client_id","") or ""))
        self._oak_completed=set(int(x) for x in (self.settings.get("oak_completed_ids",[]) or []) if str(x).isdigit()); self._oak_line_counts={int(k):int(v) for k,v in (self.settings.get("oak_line_counts",{}) or {}).items() if str(k).isdigit()}; self.oak_breeding_unlocked.setChecked(bool(self.settings.get("oak_breeding_unlocked",False))); self.oak_targets.setText(str(self.settings.get("oak_targets_text","") or "")); self.oak_blocked.setText(str(self.settings.get("oak_blocked_text","") or "")); self.oak_stage.setCurrentText(str(self.settings.get("oak_stage",self.oak_stage.currentText()))); self._oak_refresh_table(); self._oak_stage_changed(self.oak_stage.currentText())
        self.auto_rng.setChecked(bool(self.settings.get("auto_rng_enabled",False))); self.rng_shiny.setChecked(bool(self.settings.get("rng_shiny_only",True))); self.rng_max.setValue(int(self.settings.get("rng_max_advances",500000) or 500000))
        ni=int(self.settings.get("rng_nature_index",-1) if self.settings.get("rng_nature_index",-1) is not None else -1); ix=self.rng_nature.findData(ni); self.rng_nature.setCurrentIndex(ix if ix>=0 else 0)
        for box,key in zip(self.rng_iv_boxes,("rng_iv_hp","rng_iv_atk","rng_iv_def","rng_iv_spa","rng_iv_spd","rng_iv_spe")): box.setValue(int(self.settings.get(key,0) or 0))
        last=self.settings.get("last_hunt","starter_charmander"); h=BY_KEY.get(last)
        if h:
            self.group_combo.setCurrentText(h.group); self._populate_targets(h.group)
            ix=self.target.findData(last)
            if ix>=0:self.target.setCurrentIndex(ix)

    def save_settings(self):
        current=self.target.currentData() if hasattr(self,'target') else self.settings.get("last_hunt","starter_charmander")
        old=self.settings or {}
        if current and hasattr(self,"rng_lead"): self.rng_leads[str(current)]=int(self.rng_lead.value())
        new_settings={"switch_ip":self.ip.text().strip(),"port":self.port.value(),"monitor_interval":self.interval.value(),"always_on_top":self.top.isChecked(),"last_hunt":current,"game_corner_number":self.gc_count.value(),"wild_movement_mode":self.movement_mode.currentData(),"spin_hold":self.spin_hold.value(),"spin_settle":self.spin_settle.value(),"auto_capture":self.auto_capture.isChecked(),"shiny_auto_capture":self.shiny_auto_capture.isChecked(),"capture_ball_slot":self.capture_ball_slot.value(),"capture_max_throws":self.capture_max_throws.value(),"egg_release_nonshiny":self.egg_release_nonshiny.isChecked(),"egg_max_eggs":self.egg_max_eggs.value(),"egg_hatch_hold":self.egg_hatch_hold.value(),"egg_hatch_cycles":self.egg_hatch_cycles.value(),"egg_breeding_unlocked":self.oak_breeding_unlocked.isChecked(),"oak_stage":self.oak_stage.currentText(),"oak_targets_text":self.oak_targets.text().strip(),"oak_blocked_text":self.oak_blocked.text().strip(),"oak_completed_ids":sorted(int(x) for x in getattr(self,"_oak_completed",set())),"oak_line_counts":{str(k):int(v) for k,v in getattr(self,"_oak_line_counts",{}).items()},"oak_breeding_unlocked":bool(self.oak_breeding_unlocked.isChecked()) if hasattr(self,"oak_breeding_unlocked") else bool(old.get("oak_breeding_unlocked",False)),"starter_hunt_key":str(old.get("starter_hunt_key", "")),"discord_bot_enabled":self.discord_enable.isChecked(),"discord_bot_token":self.discord_token.text().strip(),"discord_channel_id":self.discord_channel.text().strip(),"discord_notify_status":self.discord_notify_status.isChecked(),"discord_notify_safety":self.discord_notify_safety.isChecked(),"discord_rich_presence_enabled":self.rpc_enable.isChecked(),"discord_rpc_client_id":self.rpc_client.text().strip(),"auto_rng_enabled":self.auto_rng.isChecked(),"rng_shiny_only":self.rng_shiny.isChecked(),"rng_nature_index":int(self.rng_nature.currentData()),"rng_iv_hp":self.rng_iv_boxes[0].value(),"rng_iv_atk":self.rng_iv_boxes[1].value(),"rng_iv_def":self.rng_iv_boxes[2].value(),"rng_iv_spa":self.rng_iv_boxes[3].value(),"rng_iv_spd":self.rng_iv_boxes[4].value(),"rng_iv_spe":self.rng_iv_boxes[5].value(),"rng_max_advances":self.rng_max.value(),"rng_trigger_leads":dict(self.rng_leads)}
        keys=("discord_bot_enabled","discord_bot_token","discord_channel_id","discord_notify_status","discord_notify_safety","discord_rich_presence_enabled","discord_rpc_client_id")
        discord_changed=any(old.get(k)!=new_settings.get(k) for k in keys)
        self.settings=new_settings; self.store.save_settings(self.settings); self._apply_top(); self.log_label.setText("Settings saved to AppData.")
        if discord_changed: self._restart_discord_services()

    def _restart_discord_services(self):
        if self.discord_worker:
            self.discord_worker.request_stop(); self.discord_worker.wait(2500); self.discord_worker=None
        if self.rpc_worker:
            self.rpc_worker.request_stop(); self.rpc_worker.wait(1500); self.rpc_worker=None
        if bool(self.settings.get("discord_bot_enabled",False)):
            self.discord_worker=DiscordBotWorker(self.settings); self.discord_worker.state.connect(self.on_discord_state); self.discord_worker.log.connect(self.on_discord_log); self.discord_worker.update_snapshot(self._discord_snapshot()); self.discord_worker.start(); self.discord_state.setText("Discord: connecting…")
        else:
            if hasattr(self,'discord_state'): self.discord_state.setText("Discord: disabled")
        if bool(self.settings.get("discord_rich_presence_enabled",False)):
            self.rpc_worker=RichPresenceWorker(self.settings.get("discord_rpc_client_id","")); self.rpc_worker.state.connect(self.on_rpc_state); self.rpc_worker.log.connect(self.on_discord_log); self.rpc_worker.start(); self.rpc_worker.publish(self._discord_snapshot()); self.rpc_state.setText("Rich Presence: connecting…")
        else:
            if hasattr(self,'rpc_state'): self.rpc_state.setText("Rich Presence: disabled")

    def _discord_snapshot(self):
        s=self.store.session or {}; life=self.store.lifetime or {}
        return {"connected":self.connected,"game":self.connected_game,"hunting":self.hunting,"hunt":self.last_hunt_label,"status":self.last_status,"session_encounters":int(s.get("encounters",0) or 0),"session_shinies":int(s.get("shinies",0) or 0),"elapsed_seconds":self._elapsed() if hasattr(self,'session_elapsed_frozen') else 0,"lifetime_encounters":int(life.get("total_encounters",0) or 0),"lifetime_shinies":int(life.get("total_shinies",0) or 0),"party":self.last_party,"shiny_hold":self.shiny_hold,"last_name":getattr(self,'current_name',None).text().replace("★ ","") if getattr(self,'current_name',None) else "Pokémon","session_started_epoch":self.session_started_epoch}

    def _push_discord_snapshot(self):
        snap=self._discord_snapshot()
        if self.discord_worker: self.discord_worker.update_snapshot(snap)
        if self.rpc_worker: self.rpc_worker.publish(snap)

    def _discord_publish(self,kind,payload=None):
        if self.discord_worker: self.discord_worker.publish(kind,payload or {})

    def on_discord_state(self,d):
        if hasattr(self,'discord_state'): self.discord_state.setText("Discord: "+str(d.get("message","connected" if d.get("connected") else "disconnected")))

    def on_rpc_state(self,d):
        if hasattr(self,'rpc_state'): self.rpc_state.setText("Rich Presence: "+str(d.get("message","connected" if d.get("connected") else "disconnected")))

    def on_discord_log(self,s):
        self.log_label.setText(str(s))

    def test_discord(self):
        self.save_settings()
        if not self.discord_worker:
            QMessageBox.warning(self,"Discord disabled","Enable Discord bot-account support and enter a bot token + channel ID first."); return
        self._discord_publish("test",{})
        self.discord_state.setText("Discord: test queued")

    def _apply_top(self):
        want=self.top.isChecked() if hasattr(self,'top') else bool(self.settings.get('always_on_top',False)); self.setWindowFlag(Qt.WindowStaysOnTopHint,want); self.show()

    def _populate_targets(self,group):
        if not hasattr(self,'target'):return
        keep=self.target.currentData(); self.target.blockSignals(True); self.target.clear()
        for h in GROUPS.get(group,[]):
            if self.connected_game and self.connected_game not in h.games: continue
            self.target.addItem(h.label,h.key)
        self.target.blockSignals(False)
        if keep:
            ix=self.target.findData(keep)
            if ix>=0:self.target.setCurrentIndex(ix)
        self._hunt_changed()

    def _movement_changed(self,*_):
        spin=self.movement_mode.currentData()=="spin"
        self.spin_hold.setEnabled(spin and not self.hunting)
        self.spin_settle.setEnabled(spin and not self.hunting)
        self.movement_mode.setEnabled(not self.hunting)
        self.spin_note.setVisible(spin)

    def _hunt_changed(self,*_):
        key=self.target.currentData() if self.target.count() else None; h=BY_KEY.get(key) if key else None
        if not h: self.mode.setText("—"); self.setup.setText(""); return
        self.mode.setText(f"Engine: {h.engine.replace('_',' ').title()}" + (f" • Species #{h.species}" if h.species else "")); self.setup.setText(h.setup or "Uses the generic FRLG RAM routine.")
        if h.engine=="starter" and h.species in STARTER_IDS:
            self.settings["starter_hunt_key"]=h.key
            if hasattr(self,"oak_starter_status"):
                self.oak_starter_status.setText(f"{h.label} — only 1 starter available until breeding/egg hatching is unlocked")
                self._oak_refresh_table()
        is_gc=h.engine=="game_corner"; self.gc_label.setVisible(is_gc); self.gc_count.setVisible(is_gc)
        rng_supported=h.engine in ("starter","gift","static","static_hooh")
        if hasattr(self,"auto_rng"):
            self.rng_current_hunt.setText(f"Selected hunt: {h.label} • {h.engine.replace('_',' ').title()}")
            self.auto_rng.setEnabled(rng_supported and not self.hunting)
            if not rng_supported: self.auto_rng.setChecked(False)
            self.rng_support.setText("Live-seed RNG targeting is available for this hunt." if rng_supported else "Automatic RNG targeting is not enabled for this engine yet; use the normal hunt engine from the Dashboard.")
            default_lead={"starter":450,"gift":350,"static":80,"static_hooh":80}.get(h.engine,0)
            self.rng_lead.setValue(int(self.rng_leads.get(h.key,default_lead)))

    def connect_switch(self): self.save_settings(); self.conn_btn.setEnabled(False); self.game_badge.setText("Connecting…"); self.worker.request_connect(self.ip.text().strip(),self.port.value(),self.interval.value())

    def release_controller(self):
        if not self.connected:
            QMessageBox.warning(self,"Not connected","Connect to the Switch first."); return
        if self.hunting:
            QMessageBox.information(self,"Hunt running","Stop the hunt first. The controller is released automatically when the hunt exits."); return
        self.worker.request_release_controller(); self.log_label.setText("Releasing Koi virtual controller…")

    def toggle_display(self):
        if not self.connected:
            QMessageBox.warning(self,"Not connected","Connect to the Switch first."); return
        # Button text describes the next action.
        turn_on=self.display_btn.text()=="Display On"
        self.display_btn.setEnabled(False)
        self.display_btn.setText("Turning On…" if turn_on else "Turning Off…")
        self.worker.request_display(turn_on)

    def on_display(self,d):
        if not d.get("ok"):
            self.display_btn.setEnabled(self.connected)
            self.display_btn.setText("Display Off")
            QMessageBox.warning(self,"Display control",d.get("error","Koi botbase display command failed."))
            return
        screen_on=bool(d.get("screen_on"))
        self.display_btn.setText("Display Off" if screen_on else "Display On")
        self.display_btn.setEnabled(self.connected)
        if d.get("reason")=="shiny":
            self.log_label.setText("Shiny safety: Switch display restored before HOME.")

    def on_connection(self,d):
        self.connected=bool(d.get("connected")); self.conn_btn.setEnabled(True)
        if self.connected:
            self.display_btn.setEnabled(True); self.display_btn.setText("Display Off"); self.release_btn.setEnabled(not self.hunting)
            self.connected_game=d.get("game"); ver="✓ verified" if d.get("verified_language") else "unverified language"; self.game_badge.setText(f"{d.get('game')} • {d.get('language')} • Koi {d.get('botbase')} • {ver}"); self.game_badge.setObjectName("Good" if d.get("verified_language") else "Warn"); self.conn_btn.setText("Reconnect")
            if self.settings.get("discord_notify_status",True): self._discord_publish("switch_connected",d)
        else: self.connected_game=None; self.game_badge.setText("Not connected"); self.conn_btn.setText("Connect"); self.display_btn.setEnabled(False); self.display_btn.setText("Display Off"); self.release_btn.setEnabled(False); self.on_utilities({"white_flute":None,"illuminate":None})
        self._populate_targets(self.group_combo.currentText()); self._push_discord_snapshot()

    def _oak_target_ids_for_start(self):
        manual=self._species_ids_from_text(self.oak_targets.text())
        if manual or not self.oak_use_checklist.isChecked(): return manual
        ids=self._oak_visible_ids()
        out=[]
        for sid in ids:
            line=oak_line_for_species(sid); base=line[0]; count=int(self._oak_line_counts.get(base,0)); available=self._oak_available_catches(base)
            if available > count and count < len(line) and base not in out:
                out.append(base)
        return out

    def start_capture_test(self):
        if self.hunting:
            return
        self.capture_test_mode.setChecked(True)
        self.start_hunt()

    def start_hunt(self):
        if not self.connected: QMessageBox.warning(self,"Not connected","Connect to the Switch first."); return
        key=self.target.currentData();
        if self.capture_test_mode.isChecked():
            key="auto_capture_test"
        h=BY_KEY.get(key)
        if not h: QMessageBox.warning(self,"No hunt","Select a hunt first."); return
        if self.connected_game not in h.games: QMessageBox.warning(self,"Wrong version",f"{h.label} is not available in {self.connected_game}."); return
        self.save_settings(); self.store.new_session(h.group,h.label); self.session_started_mono=time.monotonic(); self.session_started_epoch=int(time.time()); self.session_elapsed_frozen=0; self._last_elapsed_flush=0.0; self.last_hunt_label=h.label; self.last_status=f"Hunting {h.label}"; self.shiny_hold=False; self.current_sprite.set_sprite(None); self.current_name.setText("—"); self.current_name.setStyleSheet("font-size:19pt;font-weight:750;"); self.current_detail.setText("No encounter seen this session"); self.current_detail.setToolTip(""); self.hunt_state.setText(f"New session: {h.label}"); self._refresh_stats(); self.hunting=True; self.start_btn.setEnabled(False); self.stop_btn.setEnabled(True); self.release_btn.setEnabled(False); self.group_combo.setEnabled(False); self.target.setEnabled(False); self.gc_count.setEnabled(False); self.movement_mode.setEnabled(False); self.spin_hold.setEnabled(False); self.spin_settle.setEnabled(False); self.auto_capture.setEnabled(False); self.shiny_auto_capture.setEnabled(False); self.capture_ball_slot.setEnabled(False); self.capture_max_throws.setEnabled(False); self.egg_release_nonshiny.setEnabled(False); self.egg_max_eggs.setEnabled(False); self.egg_hatch_hold.setEnabled(False); self.egg_hatch_cycles.setEnabled(False); self.oak_stage.setEnabled(False); self.oak_targets.setEnabled(False); self.oak_blocked.setEnabled(False); self.auto_rng.setEnabled(False); self.rng_shiny.setEnabled(False); self.rng_nature.setEnabled(False); self.rng_max.setEnabled(False); self.rng_lead.setEnabled(False); [b.setEnabled(False) for b in self.rng_iv_boxes]; self._push_discord_snapshot();
        if self.settings.get("discord_notify_status",True): self._discord_publish("hunt_started",{"hunt":h.label,"game":self.connected_game,"session_id":self.store.session.get("session_id","—")});
        self.worker.request_start_hunt(key,{"game_corner_number":self.gc_count.value(),"wild_movement_mode":self.movement_mode.currentData(),"spin_hold":self.spin_hold.value(),"spin_settle":self.spin_settle.value(),"auto_capture":self.auto_capture.isChecked(),"shiny_auto_capture":self.shiny_auto_capture.isChecked(),"capture_ball_slot":self.capture_ball_slot.value(),"capture_max_throws":self.capture_max_throws.value(),"egg_release_nonshiny":self.egg_release_nonshiny.isChecked(),"egg_max_eggs":self.egg_max_eggs.value(),"egg_hatch_hold":self.egg_hatch_hold.value(),"egg_hatch_cycles":self.egg_hatch_cycles.value(),"egg_breeding_unlocked":self.oak_breeding_unlocked.isChecked(),"oak_stage":self.oak_stage.currentText(),"oak_targets":self._oak_target_ids_for_start(),"oak_blocked":self._species_ids_from_text(self.oak_blocked.text()),"oak_targets_text":self.oak_targets.text().strip(),"oak_blocked_text":self.oak_blocked.text().strip(),"oak_completed_ids":sorted(int(x) for x in getattr(self,"_oak_completed",set())),"oak_line_counts":{str(k):int(v) for k,v in getattr(self,"_oak_line_counts",{}).items()},"auto_rng":self.auto_rng.isChecked(),"rng_shiny_only":self.rng_shiny.isChecked(),"rng_nature_index":int(self.rng_nature.currentData()),"rng_iv_hp":self.rng_iv_boxes[0].value(),"rng_iv_atk":self.rng_iv_boxes[1].value(),"rng_iv_def":self.rng_iv_boxes[2].value(),"rng_iv_spa":self.rng_iv_boxes[3].value(),"rng_iv_spd":self.rng_iv_boxes[4].value(),"rng_iv_spe":self.rng_iv_boxes[5].value(),"rng_max_advances":self.rng_max.value(),"rng_trigger_lead":self.rng_lead.value()})

    def stop_hunt(self):
        if not self.hunting:return
        self.worker.request_stop_hunt(); self._finish_session("Stopping…")

    def _finish_session(self,msg=None):
        was_hunting=self.hunting; elapsed=self._elapsed(); self.store.stop_session(elapsed); self.session_elapsed_frozen=elapsed; self.session_started_mono=None; self.session_started_epoch=None; self.hunting=False; self.last_status=msg or "Session stopped"; self.start_btn.setEnabled(True); self.stop_btn.setEnabled(False); self.release_btn.setEnabled(self.connected); self.group_combo.setEnabled(True); self.target.setEnabled(True); self.gc_count.setEnabled(True); self.movement_mode.setEnabled(True); self.spin_hold.setEnabled(True); self.spin_settle.setEnabled(True); self.auto_capture.setEnabled(True); self.shiny_auto_capture.setEnabled(True); self.capture_ball_slot.setEnabled(True); self.capture_max_throws.setEnabled(True); self.egg_release_nonshiny.setEnabled(True); self.egg_max_eggs.setEnabled(True); self.egg_hatch_hold.setEnabled(True); self.egg_hatch_cycles.setEnabled(True); self.oak_stage.setEnabled(True); self.oak_targets.setEnabled(True); self.oak_blocked.setEnabled(True); self.rng_shiny.setEnabled(True); self.rng_nature.setEnabled(True); self.rng_max.setEnabled(True); self.rng_lead.setEnabled(True); [b.setEnabled(True) for b in self.rng_iv_boxes]; self.hunt_state.setText(self.last_status); self._hunt_changed(); self._refresh_stats(); self._push_discord_snapshot()
        if was_hunting and self.settings.get("discord_notify_status",True) and not self.shiny_hold:
            s=self.store.session or {}; self._discord_publish("hunt_stopped",{"message":self.last_status,"hunt":self.last_hunt_label,"game":self.connected_game,"session_encounters":s.get("encounters",0),"session_shinies":s.get("shinies",0),"elapsed_seconds":elapsed})

    def _elapsed(self): return (time.monotonic()-self.session_started_mono) if self.session_started_mono is not None else self.session_elapsed_frozen

    def _tick(self):
        if self.hunting and self.store.session:
            e=self._elapsed(); self.store.session["elapsed_seconds"]=round(e,3)
            if e-self._last_elapsed_flush >= 5.0: self.store.update_elapsed(e); self._last_elapsed_flush=e; self._push_discord_snapshot()
        self._refresh_stats()

    def on_utilities(self,d):
        def set_status(label, name, value):
            if value is True:
                label.setText(f"{name}: ON")
                label.setObjectName("Good")
            elif value is False:
                label.setText(f"{name}: OFF")
                label.setObjectName("Muted")
            else:
                label.setText(f"{name}: —")
                label.setObjectName("Muted")
            label.style().unpolish(label); label.style().polish(label)
        set_status(self.white_flute_status, "White Flute", d.get("white_flute"))
        set_status(self.illuminate_status, "Illuminate", d.get("illuminate"))

    def on_party(self,vals):
        self.last_party=list(vals or [])
        for card,p in zip(self.party_cards,vals): card.update_pk(p)
        self._push_discord_snapshot()

    def on_encounter(self,p):
        if not self.hunting:return
        self.store.record_encounter(p,self._elapsed()); shiny=bool(p.get("shiny")); self.current_sprite.set_sprite(p.get("sprite_path"),shiny); self.current_name.setText(("★ " if shiny else "")+p.get("name","Pokémon")); self.current_name.setStyleSheet("font-size:19pt;font-weight:750;color:#ffe36e;" if shiny else "font-size:19pt;font-weight:750;")
        ability=p.get("ability_name") or f"Ability slot {p.get('ability_slot')}"; rng_miss=_format_rng_miss(p.get("rng_miss")); self.current_detail.setText(f"#{p.get('attempt')} • {p.get('source','Encounter')}\n{p.get('nature')} • {ability} • PID {p.get('pid',0):08X}\nIVs {p.get('iv_spread')} (Σ {p.get('iv_sum')}) • SV {p.get('shiny_xor')} • Pokérus 0x{p.get('pokerus',0):02X}\nShiny-frame miss: {rng_miss}{' RNG advances' if p.get('rng_miss') is not None and p.get('rng_miss') != 0 else ''}"); self.current_detail.setToolTip(_rng_tooltip(p))
        self._refresh_stats(); self._push_discord_snapshot()
        if shiny:
            s=self.store.session or {}; life=self.store.lifetime or {}; dp=dict(p); dp.update({"game":self.connected_game,"hunt":self.last_hunt_label,"session_encounters":s.get("encounters",0),"session_shinies":s.get("shinies",0),"lifetime_encounters":life.get("total_encounters",0),"lifetime_shinies":life.get("total_shinies",0)}); self._discord_publish("shiny",dp)

    def on_status(self,d):
        st=d.get("state",""); self.last_status=d.get("message",st); self.hunt_state.setText(self.last_status)
        if st=="SHINY_HOLD": self.shiny_hold=True; self._finish_session(self.last_status); self.hunt_state.setObjectName("Shiny"); self._push_discord_snapshot()
        elif st=="SAFETY_HOLD" and self.hunting:
            if self.settings.get("discord_notify_safety",True): self._discord_publish("safety_hold",{"message":self.last_status,"game":self.connected_game,"hunt":self.last_hunt_label})
            self._finish_session(self.last_status)
        elif st=="CAPTURED" and d.get("oak_target") and d.get("oak_captured"):
            self._oak_register_capture(d.get("species_id"))
            if self.settings.get("discord_notify_status",True): self._discord_publish("oak_capture",{"message":self.last_status,"game":self.connected_game,"hunt":self.last_hunt_label,"species_id":d.get("species_id")})
            self._finish_session(self.last_status)
        elif st=="STOPPED" and self.hunting: self._finish_session(self.last_status)
        elif d.get("oak_captured") and d.get("oak_target"):
            self._oak_register_capture(d.get("species_id"))
            self._finish_session(self.last_status)
        else: self._push_discord_snapshot()

    def on_rng_calibration(self,d):
        key=str(d.get("hunt_key") or "")
        if not key: return
        lead=max(0,int(d.get("lead",0) or 0)); self.rng_leads[key]=lead; self.settings["rng_trigger_leads"]=dict(self.rng_leads); self.store.save_settings(self.settings)
        if self.target.currentData()==key: self.rng_lead.setValue(lead)
        delta=d.get("delta")
        if delta is not None:
            msg=f"Auto RNG calibration: {int(delta):+d} advances • next trigger lead {lead}"
            self.hunt_state.setText(msg)
            if hasattr(self,"rng_calibration_status"): self.rng_calibration_status.setText(msg)

    def on_log(self,s): self.log_label.setText(s)
    def on_support(self,path):
        self.last_support=path; self.support_label.setText(path)
        try:
            safe={"discord_bot_enabled":bool(self.settings.get("discord_bot_enabled",False)),"discord_channel_id":str(self.settings.get("discord_channel_id","") or ""),"discord_notify_status":bool(self.settings.get("discord_notify_status",True)),"discord_notify_safety":bool(self.settings.get("discord_notify_safety",True)),"discord_rich_presence_enabled":bool(self.settings.get("discord_rich_presence_enabled",False)),"discord_rpc_client_id":str(self.settings.get("discord_rpc_client_id","") or ""),"bot_token_included":False,"ui_discord_state":self.discord_state.text() if hasattr(self,"discord_state") else "—","ui_rpc_state":self.rpc_state.text() if hasattr(self,"rpc_state") else "—"}
            with zipfile.ZipFile(path,"a",zipfile.ZIP_DEFLATED) as z: z.writestr("discord_state.json",json.dumps(safe,indent=2))
        except Exception as exc:
            self.log_label.setText(f"Support ZIP saved; Discord diagnostic append failed: {exc}")

    def _refresh_stats(self):
        s=self.store.session or {}; life=self.store.lifetime; e=self._elapsed() if self.hunting else float(s.get("elapsed_seconds",self.session_elapsed_frozen) or 0); enc=int(s.get("encounters",0)); rate=(enc/e*3600) if e>0 else 0
        self.s_enc.set(enc); self.s_shiny.set(s.get("shinies",0)); self.s_time.set(time.strftime("%H:%M:%S",time.gmtime(e))); self.s_rate.set(f"{rate:.1f}"); self.l_enc.set(life.get("total_encounters",0)); self.l_shiny.set(life.get("total_shinies",0))
        c=s.get("cycle",{}); hi=c.get("iv_sum_high"); lo=c.get("iv_sum_low"); self.cycle_high.setText(f"Highest IV: {'—' if hi is None else str(hi)+'  ('+str(c.get('iv_high_spread'))+')'}"); self.cycle_low.setText(f"Lowest IV: {'—' if lo is None else str(lo)+'  ('+str(c.get('iv_low_spread'))+')'}"); self.sv_high.setText(f"Highest SV: {c.get('sv_high') if c.get('sv_high') is not None else '—'}"); self.sv_low.setText(f"Lowest SV: {c.get('sv_low') if c.get('sv_low') is not None else '—'}")
        rows=s.get("recent_seen",[]); self.seen.setRowCount(len(rows))
        for r,row in enumerate(rows):
            self.seen.setRowHeight(r,54); spr=SpriteLabel(48); sprite_path=row.get("sprite_path") or get_sprite_path(row.get("species",0),bool(row.get("shiny"))); spr.set_sprite(sprite_path,bool(row.get("shiny"))); self.seen.setCellWidget(r,0,spr)
            vals=[("★ " if row.get('shiny') else "")+str(row.get('name','')),row.get('nature','—'),row.get('ability_name') or f"Ability slot {row.get('ability_slot','—')}",row.get('iv_spread') or f"{row.get('iv_hp','—')}/{row.get('iv_atk','—')}/{row.get('iv_def','—')}/{row.get('iv_spa','—')}/{row.get('iv_spd','—')}/{row.get('iv_spe','—')}",row.get('iv_sum','—'),row.get('shiny_xor','—'),_format_rng_miss(row.get('rng_miss')),row.get('source','—')]
            for cidx,val in enumerate(vals,1):
                item=QTableWidgetItem(str(val)); self.seen.setItem(r,cidx,item)
                if cidx==7: item.setToolTip(_rng_tooltip(row))

    def open_appdata(self):
        p=str(appdata_root())
        try: os.startfile(p)
        except Exception: self.log_label.setText(p)

    def closeEvent(self,e:QCloseEvent):
        if self.hunting: self._finish_session("Application closed")
        if self.discord_worker: self.discord_worker.request_stop(); self.discord_worker.wait(2500)
        if self.rpc_worker: self.rpc_worker.request_stop(); self.rpc_worker.wait(1500)
        self.worker.request_shutdown(); self.worker.wait(5000); e.accept()
