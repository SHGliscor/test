from pathlib import Path
from pokebot_frlg.wifi_botbase import WiFiBotbase

bot=WiFiBotbase("127.0.0.1"); sent=[]; bot.send=sent.append; bot.detach_controller(); assert sent==["detachController"]
src=(Path(__file__).resolve().parents[1]/"pokebot_frlg"/"backend.py").read_text(encoding="utf-8")
assert 'def _release_controller' in src
finally_block=src[src.index('finally:',src.index('def _hunt_loop')):src.index('def _run_starter')]
assert 'self._release_controller()' in finally_block
print("PASS controller release on hunt exit")
