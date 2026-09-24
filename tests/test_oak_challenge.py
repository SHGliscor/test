from pokebot_frlg.oak_challenge import stage_species
from pokebot_frlg.hunt_catalog import BY_KEY

def test_oak_hunt_exists():
    assert BY_KEY["oak_wild"].engine == "oak_wild"

def test_oak_prebadge_one_contains_expected_species():
    ids = stage_species("Pre-Badge 1 — Brock", "FireRed")
    for species in (16,19,21,22,10,13,25):
        assert species in ids

def test_oak_version_exclusives_are_filtered():
    assert 23 not in stage_species("Pre-Badge 2 — Misty", "LeafGreen")
    assert 27 not in stage_species("Pre-Badge 2 — Misty", "FireRed")

from pokebot_frlg.oak_challenge import oak_line_for_species, oak_line_target, oak_line_required

def test_oak_evolution_line_progression_pidgey():
    assert oak_line_for_species(16) == (16,17,18)
    assert oak_line_for_species(17) == (16,17,18)
    assert oak_line_target(18) == 16
    assert oak_line_required(16) == 3

def test_oak_two_stage_line_magikarp():
    assert oak_line_for_species(128) == (128,129)
    assert oak_line_required(129) == 2


def test_oak_four_stage_eevee_line():
    assert oak_line_for_species(132) == (132,133,134,135)
    assert oak_line_required(135) == 4

def test_selected_starter_line_and_prebreeding_limit():
    from pokebot_frlg.oak_challenge import oak_starter_line, oak_starter_available_catches
    assert oak_starter_line(4) == (4,5,6)
    assert oak_starter_line(1) == (1,2,3)
    assert oak_starter_line(7) == (7,8,9)
    assert oak_starter_available_catches(4, False) == 1
    assert oak_starter_available_catches(4, True) == 3
    assert oak_starter_available_catches(999, False) == 0
