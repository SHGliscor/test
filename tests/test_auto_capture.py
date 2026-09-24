from pokebot_frlg.hunt_catalog import BY_KEY


def test_auto_capture_test_hunt_registered():
    h = BY_KEY["auto_capture_test"]
    assert h.engine == "auto_capture_test"
    assert h.species is None


def test_capture_navigation_uses_left_stick_for_battle_and_bag(monkeypatch):
    # This is a source-level guard against regressing to D-pad battle-menu
    # navigation, which can open the overworld START menu on the Switch wrapper.
    from pathlib import Path
    src = Path(__file__).parents[1].joinpath("pokebot_frlg", "backend.py").read_text()
    section = src[src.index("def _auto_capture"):src.index("def _shiny_action")]
    assert 'self._menu_move(0x7FFF,0,"Auto Capture: selecting BAG")' in section
    assert 'self.bot.click("DRIGHT")' not in section


def test_shiny_action_defaults_to_home():
    from pathlib import Path
    src = Path(__file__).parents[1].joinpath("pokebot_frlg", "backend.py").read_text()
    section = src[src.index("def _shiny_action"):src.index("def _hunt_loop")]
    assert 'options.get("shiny_auto_capture",False)' in section
    assert 'self._shiny_home(label,attempt,suffix)' in section


def test_battle_menu_wait_clears_encounter_text_with_b(monkeypatch):
    from pathlib import Path
    src = Path(__file__).parents[1].joinpath("pokebot_frlg", "backend.py").read_text()
    section = src[src.index("def _wait_battle_menu"):src.index("def _menu_move")]
    assert 'self.bot.click("B")' in section
    assert 'next_clear=now+.45' in section


def test_capture_flow_uses_probe_state_guards():
    from pathlib import Path
    src = Path(__file__).parents[1].joinpath("pokebot_frlg", "backend.py").read_text()
    assert "def _capture_probe_snapshot" in src
    assert "def _capture_probe_transition" in src
    section = src[src.index("def _auto_capture"):src.index("def _shiny_action")]
    assert "ball selection A" in section
    assert "ball throw confirmation A" in section
    assert "CAPTURE PROBE TIMEOUT" in src


def test_capture_flow_recognises_observed_bag_states():
    from pathlib import Path
    src = Path(__file__).parents[1].joinpath("pokebot_frlg", "backend.py").read_text()
    assert "s[\"battle_menu\"] in (0xF0, 0xF2)" in src
