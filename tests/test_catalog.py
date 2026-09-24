from pokebot_frlg.hunt_catalog import HUNTS,BY_KEY

def main():
    assert len(HUNTS)==36
    assert BY_KEY['gc_scyther'].games==('FireRed',)
    assert BY_KEY['gc_pinsir'].games==('LeafGreen',)
    assert BY_KEY['static_hooh'].engine=='static_hooh'
    assert BY_KEY['gift_togepi'].species==175
    print('PASS hunt catalog')
if __name__=='__main__': main()
