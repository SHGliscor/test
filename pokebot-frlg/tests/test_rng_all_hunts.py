from pathlib import Path


def test_all_hunt_engines_emit_rng_fields():
    text=(Path(__file__).resolve().parents[1]/"pokebot_frlg"/"backend.py").read_text(encoding="utf-8")
    # All PK3 hunt engines pass through _encounter(), whose default context is
    # standard. Wild/fishing/Pickup explicitly request H-method labeling.
    assert 'rng_fields=self._rng_miss_fields(p,context=rng_context)' in text
    for needle in (
        'self._encounter(p,attempt,h.label,h.species)',            # starter/gift/static
        'self._encounter(p,attempt,f"Game Corner {h.label}",h.species)',
        'self._encounter(p,attempt,"Wild encounter",rng_context="wild")',
        'self._encounter(p,attempt,"Fishing",rng_context="wild")',
        'self._encounter(p,attempt,"Pickup wild encounter",rng_context="wild")',
        'd.update(self._rng_roamer_fields(d))',                    # roaming beasts
    ):
        assert needle in text, needle


if __name__=='__main__':
    test_all_hunt_engines_emit_rng_fields()
    print('PASS RNG miss wired to every FRLG hunt engine')
