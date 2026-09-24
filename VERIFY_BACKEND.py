# Run from anywhere:
#   python VERIFY_BACKEND.py
#   python VERIFY_BACKEND.py C:\Users\roger\Desktop\pokebot-frlg\pokebot_frlg\backend.py
from pathlib import Path
import sys

candidates = []
if len(sys.argv) > 1:
    candidates.append(Path(sys.argv[1]))
candidates += [
    Path("pokebot_frlg/backend.py"),
    Path("pokebot-frlg/pokebot_frlg/backend.py"),
    Path.home() / "Desktop" / "pokebot-frlg" / "pokebot_frlg" / "backend.py",
    Path.home() / "Desktop" / "test-mainq" / "pokebot-frlg" / "pokebot_frlg" / "backend.py",
]

p = next((c for c in candidates if c.is_file()), None)
if p is None:
    print("Could not find backend.py. Pass the full path:")
    print('  python VERIFY_BACKEND.py "C:\\Users\\roger\\Desktop\\pokebot-frlg\\pokebot_frlg\\backend.py"')
    raise SystemExit(1)

t = p.read_text(encoding="utf-8", errors="replace")
print("File:", p.resolve())
print("Size:", p.stat().st_size)
print("BUILD:", "v4-press-dex-20260924" if "v4-press-dex-20260924" in t else "MISSING / OLD")
print("_tap:", "YES" if "def _tap" in t else "NO")
print("press():", "YES" if "self.bot.press" in t else "NO")
print("last-resort:", "YES" if "last-resort" in t else "NO")
if "v4-press-dex-20260924" not in t:
    print("\n>>> This is NOT the v4 capture backend. Replace this file with backend_v4b.py")
else:
    print("\n>>> v4 backend is present. Delete pokebot_frlg\\__pycache__ and restart the bot.")
    print(">>> On connect you must see: Capture backend build: v4-press-dex-20260924")
