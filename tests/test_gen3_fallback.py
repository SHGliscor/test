from pokebot_frlg.gen3_data import FALLBACK,ABILITY_NAMES

def ability(species,slot):
    vals=FALLBACK[species]; aid=vals[0 if slot==1 else 1] or vals[0]; return ABILITY_NAMES[aid]

def main():
    assert ability(4,1)=='Blaze'
    assert ability(7,1)=='Torrent'
    assert ability(143,1)=='Immunity'
    assert ability(143,2)=='Thick Fat'
    assert ability(249,1)=='Pressure'
    print('PASS Gen3 named-hunt ability fallback')
if __name__=='__main__': main()
