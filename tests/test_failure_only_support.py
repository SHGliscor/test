import os
import tempfile
import zipfile
from pathlib import Path


def test_normal_session_creates_no_archived_json(monkeypatch):
    root=Path(tempfile.mkdtemp())
    monkeypatch.setenv("APPDATA",str(root))
    from pokebot_frlg.appdata_store import AppDataStore
    s=AppDataStore(); s.new_session("Starter","Charmander"); s.stop_session(12.3)
    app=root/"PokebotSwitch-FRLG"
    assert (app/"stats.json").exists()
    assert (app/"session_current.json").exists()
    assert not (app/"sessions").exists()
    assert not (app/"support").exists()


def test_failure_creates_zip_only(monkeypatch):
    root=Path(tempfile.mkdtemp())
    monkeypatch.setenv("APPDATA",str(root))
    # Test environment need not install the GUI dependency; backend only needs
    # minimal QThread/Signal objects for this diagnostic-path unit test.
    import sys, types
    qtcore=types.ModuleType("PySide6.QtCore")
    class _Signal:
        def __init__(self,*a,**k): pass
        def emit(self,*a,**k): pass
    class _QThread:
        def __init__(self,*a,**k): pass
    qtcore.Signal=_Signal; qtcore.QThread=_QThread
    pyside=types.ModuleType("PySide6"); pyside.QtCore=qtcore
    monkeypatch.setitem(sys.modules,"PySide6",pyside)
    monkeypatch.setitem(sys.modules,"PySide6.QtCore",qtcore)
    from pokebot_frlg.backend import BackendWorker
    w=BackendWorker(); w.current_game="FireRed"; w.bot=None
    try:
        raise RuntimeError("diagnostic test")
    except Exception as exc:
        w._fail(exc,"test")
    support=root/"PokebotSwitch-FRLG"/"support"
    files=list(support.iterdir())
    assert len(files)==1
    assert files[0].suffix==".zip"
    assert not list(support.glob("*.json"))
    with zipfile.ZipFile(files[0]) as z:
        names=z.namelist()
        assert len(names)==1 and names[0].endswith(".json")
        assert b"diagnostic test" in z.read(names[0])
