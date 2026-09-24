from pathlib import Path


def test_all_shiny_paths_use_home_helper():
    src=(Path(__file__).parents[1]/"pokebot_frlg"/"backend.py").read_text(encoding="utf-8")
    assert 'def _shiny_home' in src
    assert 'self.bot.click("HOME")' in src
    assert 'inputs stopped"' not in src
    # Every hunt-path shiny decision should now route through _shiny_home.
    assert src.count("self._shiny_home(") >= 7
