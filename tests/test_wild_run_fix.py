from pathlib import Path

SRC=(Path(__file__).resolve().parents[1]/"pokebot_frlg"/"backend.py").read_text(encoding="utf-8")
assert 'in (0x01,0x02)' in SRC
block=SRC[SRC.index('def _escape_battle'):SRC.index('def _run_wild')]
assert '_stick_tap(0x7FFF,0' in block
assert '_stick_tap(0,-0x8000' in block
assert 'click("DRIGHT")' not in block and 'click("DDOWN")' not in block
print("PASS wild Run readiness + left-stick navigation")
