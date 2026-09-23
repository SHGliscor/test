from pathlib import Path
import tempfile, os

def main():
    with tempfile.TemporaryDirectory() as td:
        os.environ['APPDATA']=td
        from pokebot_frlg import gen3_data
        d=gen3_data.appdata_root()/"cache"/"sprites"; d.mkdir(parents=True,exist_ok=True)
        stale=d/"120_normal.failed"; stale.touch()
        gen3_data._LEGACY_FAIL_CLEANED=False
        gen3_data._cleanup_legacy_sprite_fail_markers()
        assert not stale.exists()
        assert '120.png' in gen3_data.SPRITE_BASE+'120.png'
        print('PASS sprite retry clears permanent failed markers')
if __name__=='__main__': main()
