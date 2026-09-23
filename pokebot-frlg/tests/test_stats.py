import os,tempfile
from pathlib import Path

def test_store():
    with tempfile.TemporaryDirectory() as td:
        os.environ['APPDATA']=td
        from pokebot_frlg.appdata_store import AppDataStore
        s=AppDataStore(); s.new_session('Starter','Charmander')
        base={"name":"Charmander","species":4,"pid":1,"nature":"Hardy","shiny":False,"shiny_xor":500,"iv_hp":1,"iv_atk":2,"iv_def":3,"iv_spa":4,"iv_spd":5,"iv_spe":6,"iv_sum":21,"iv_spread":"1/2/3/4/5/6","ability_slot":1,"pokerus":0,"rng_method":"Method 1","rng_supported":True,"rng_validated":True,"rng_capture_seed":0x12345678,"rng_generation_seed":0x11111111,"rng_generation_to_capture":444,"rng_previous_shiny":12,"rng_next_shiny":34,"rng_miss":-12}
        s.record_encounter(base,1.0); assert s.session['encounters']==1 and s.lifetime['total_encounters']==1; assert s.session['cycle']['iv_sum_high']==21; assert s.session['recent_seen'][0]['rng_miss']==-12 and s.session['recent_seen'][0]['rng_generation_seed']==0x11111111
        shiny=dict(base,shiny=True,shiny_xor=3,iv_sum=100,iv_spread='31/31/1/1/5/31')
        s.record_encounter(shiny,2.0); assert s.session['encounters']==2 and s.session['shinies']==1; assert s.lifetime['total_encounters']==2 and s.lifetime['total_shinies']==1
        assert all(v is None for v in s.session['cycle'].values())
        s.new_session('Starter','Bulbasaur'); assert s.session['encounters']==0 and s.session['shinies']==0 and s.session['recent_seen']==[]; assert s.lifetime['total_encounters']==2 and s.lifetime['total_shinies']==1
        print('PASS stats semantics')
if __name__=='__main__':test_store()
