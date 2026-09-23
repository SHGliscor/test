from pokebot_frlg.rng import (
    next_seed, prev_seed, method1_pid, is_shiny_pid,
    locate_method1_generation_seed, locate_generation_seed,
    locate_roamer_generation_seed, nearest_method1_shiny,
    method1_miss_from_capture, miss_from_capture, roamer_miss_from_capture,
)


def test_roundtrip():
    for seed in (0, 1, 0x12345678, 0xFFFFFFFF, 0xDEADBEEF):
        assert prev_seed(next_seed(seed)) == seed
        assert next_seed(prev_seed(seed)) == seed


def synthetic(seed, method="Method 1"):
    vals=[]; s=seed
    for _ in range(5):
        s=next_seed(s); vals.append(s)
    pid=(vals[0]>>16)|((vals[1]>>16)<<16)
    if method=="Method 1": iv1,iv2=vals[2]>>16,vals[3]>>16; post=vals[3]
    elif method=="Method 2": iv1,iv2=vals[3]>>16,vals[4]>>16; post=vals[4]
    elif method=="Method 4": iv1,iv2=vals[2]>>16,vals[4]>>16; post=vals[4]
    else: raise ValueError(method)
    ivs={
        "iv_hp":iv1&31,"iv_atk":(iv1>>5)&31,"iv_def":(iv1>>10)&31,
        "iv_spa":(iv2>>5)&31,"iv_spd":(iv2>>10)&31,"iv_spe":iv2&31,
    }
    return pid,ivs,post


def test_reconstruct_and_miss():
    generation_seed=0x12345678
    pid,ivs,post=synthetic(generation_seed,"Method 1")
    capture=post
    for _ in range(5000): capture=next_seed(capture)
    found=locate_method1_generation_seed(capture,pid,**ivs)
    assert found == (generation_seed, 5004), found
    result=method1_miss_from_capture(capture,pid,12345,54321,**ivs)
    assert result.validated
    assert result.generation_seed == generation_seed
    assert result.generation_to_capture == 5004
    assert result.previous_shiny == 8217, result
    assert result.next_shiny == 2445, result
    assert result.miss == 2445, result


def test_all_method_families_reconstruct():
    for index,method in enumerate(("Method 1","Method 2","Method 4")):
        seed=(0x13572468 + index*0x11111111) & 0xFFFFFFFF
        pid,ivs,post=synthetic(seed,method)
        capture=post
        for _ in range(777): capture=next_seed(capture)
        found=locate_generation_seed(capture,pid,**ivs)
        assert found is not None, method
        assert found[0] == seed, (method,found)
        assert found[2] == method, (method,found)


def test_wild_context_labels_h_method():
    seed=0x24681357
    pid,ivs,post=synthetic(seed,"Method 4")
    result=miss_from_capture(post,pid,2222,3333,context="wild",max_scan=200000,**ivs)
    assert result.validated
    assert result.method == "Method H4", result
    assert result.generation_seed == seed


def test_roamer_bug_reconstruction():
    seed=0x31415926
    s1=next_seed(seed); s2=next_seed(s1); s3=next_seed(s2)
    pid=(s1>>16)|((s2>>16)<<16)
    iv_byte=(s3>>16)&0xFF
    capture=s3
    for _ in range(900): capture=next_seed(capture)
    found=locate_roamer_generation_seed(capture,pid,iv_byte)
    assert found == (seed,903), found
    result=roamer_miss_from_capture(capture,pid,1111,4444,iv_byte=iv_byte,max_scan=200000)
    assert result.validated
    assert result.method == "Method 1 (FRLG roamer IV bug)"
    assert result.generation_seed == seed


def test_pid_order_matches_method1():
    seed=0x89ABCDEF
    s1=next_seed(seed); s2=next_seed(s1)
    assert method1_pid(seed) == ((s1>>16) | ((s2>>16)<<16))


def test_shiny_hit_zero():
    seed=0xCAFEBABE; tid=0x1234; sid=0x5678
    g=seed
    for _ in range(200000):
        pid=method1_pid(g)
        if is_shiny_pid(pid,tid,sid):
            prev,nxt,miss=nearest_method1_shiny(g,tid,sid,observed_pid=pid)
            assert (prev,nxt,miss)==(0,0,0)
            return
        g=next_seed(g)
    raise AssertionError("test setup failed to locate a shiny candidate")


def test_invalid_reconstruction_is_unavailable():
    assert locate_method1_generation_seed(0xDEADBEEF,0x12345678,1,2,3,4,5,6,max_back=5000) is None


if __name__=='__main__':
    test_roundtrip(); test_reconstruct_and_miss(); test_all_method_families_reconstruct(); test_wild_context_labels_h_method(); test_roamer_bug_reconstruction(); test_pid_order_matches_method1(); test_shiny_hit_zero(); test_invalid_reconstruction_is_unavailable()
    print('PASS all-hunts read-only shiny-frame miss RNG calculations')
