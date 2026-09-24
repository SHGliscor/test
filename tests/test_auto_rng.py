from pokebot_frlg.rng import (
    advance_seed, rewind_seed, next_seed, find_method1_target,
    method1_pid, method1_ivs, shiny_xor, nearby_signed_distance,
    forward_distance_limited,
)


def test_jump_helpers_match_single_steps():
    for seed in (0, 1, 0x12345678, 0xDEADBEEF, 0xFFFFFFFF):
        g=seed
        for n in range(0,128):
            assert advance_seed(seed,n)==g
            assert rewind_seed(g,n)==seed
            g=next_seed(g)


def test_nearby_distances():
    seed=0x12345678
    later=advance_seed(seed,777)
    earlier=rewind_seed(seed,333)
    assert forward_distance_limited(seed,later,1000)==777
    assert nearby_signed_distance(seed,later,1000)==777
    assert nearby_signed_distance(seed,earlier,1000)==-333
    assert nearby_signed_distance(seed,advance_seed(seed,2000),1000) is None


def test_find_shiny_method1_target():
    start=0xCAFEBABE; tid=0x1234; sid=0x5678
    target=find_method1_target(start,tid,sid,shiny_only=True,min_advances=600,max_advances=200000)
    assert target is not None
    assert target.advances>=600
    assert target.generation_seed==advance_seed(start,target.advances)
    assert target.pid==method1_pid(target.generation_seed)
    assert target.shiny_xor==shiny_xor(target.pid,tid,sid)<8
    assert method1_ivs(target.generation_seed)==(
        target.iv_hp,target.iv_atk,target.iv_def,target.iv_spa,target.iv_spd,target.iv_spe
    )


def test_nature_and_iv_filters():
    start=0x10203040; tid=100; sid=200
    # Non-shiny search makes this deterministic/fast while still exercising filters.
    target=find_method1_target(start,tid,sid,shiny_only=False,nature_index=7,
                               min_ivs=(10,10,10,10,10,10),min_advances=100,max_advances=200000)
    assert target is not None
    assert target.nature_index==7
    assert min(target.iv_hp,target.iv_atk,target.iv_def,target.iv_spa,target.iv_spd,target.iv_spe)>=10


def test_backend_auto_rng_scope_is_explicit():
    from pathlib import Path
    text=(Path(__file__).resolve().parents[1]/'pokebot_frlg'/'backend.py').read_text(encoding='utf-8')
    assert 'engine in ("starter","gift","static","static_hooh")' in text
    assert 'find_method1_target' in text
    assert 'nearby_signed_distance' in text
    assert 'rng_calibration.emit' in text


if __name__=='__main__':
    test_jump_helpers_match_single_steps(); test_nearby_distances(); test_find_shiny_method1_target(); test_nature_and_iv_filters(); test_backend_auto_rng_scope_is_explicit()
    print('PASS live-seed auto RNG unit tests')
