from pathlib import Path

SRC=(Path(__file__).resolve().parents[1]/"pokebot_frlg"/"backend.py").read_text(encoding="utf-8")
assert 'def _stick_tap' in SRC
assert 'set_stick("LEFT",int(x),int(y))' in SRC
block=SRC[SRC.index('def _wiggle_to_battle'):SRC.index('def _escape_battle')]
assert 'click("DRIGHT")' not in block
assert 'click("DLEFT")' not in block
assert '_wild_horizontal' in block
assert 'self._wild_horizontal = not self._wild_horizontal' in SRC
print("PASS wild movement uses left-stick pulses and per-battle axis alternation")
