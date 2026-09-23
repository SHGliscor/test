from __future__ import annotations

from dataclasses import dataclass, asdict

# Pokémon Gen III's 32-bit linear congruential RNG (PokeRNG).
# PokéFinder: LCRNG<0x6073, 0x41C64E6D>.
MULT = 0x41C64E6D
ADD = 0x00006073
MASK32 = 0xFFFFFFFF
MOD32 = 1 << 32
INV_MULT = pow(MULT, -1, MOD32)

DEFAULT_RECONSTRUCT_BACK = 250_000
DEFAULT_SHINY_SCAN = 131_072


@dataclass(frozen=True)
class RNGMissResult:
    """Read-only retrospective RNG-distance result for one generated Pokémon."""

    method: str
    capture_seed: int | None
    generation_seed: int | None
    generation_to_capture: int | None
    previous_shiny: int | None
    next_shiny: int | None
    miss: int | None
    validated: bool

    def to_dict(self) -> dict:
        return asdict(self)


def next_seed(seed: int) -> int:
    return ((int(seed) & MASK32) * MULT + ADD) & MASK32


def prev_seed(seed: int) -> int:
    return (((int(seed) & MASK32) - ADD) * INV_MULT) & MASK32


def next_u16(seed: int) -> tuple[int, int]:
    new = next_seed(seed)
    return new, new >> 16


def method1_pid(seed_before_pid: int) -> int:
    """PID from two consecutive Gen-III PokeRNG calls, low half then high half."""
    s1 = next_seed(seed_before_pid)
    s2 = next_seed(s1)
    return (s1 >> 16) | ((s2 >> 16) << 16)


def shiny_xor(pid: int, tid: int, sid: int) -> int:
    pid = int(pid) & MASK32
    return (int(tid) & 0xFFFF) ^ (int(sid) & 0xFFFF) ^ (pid & 0xFFFF) ^ (pid >> 16)


def is_shiny_pid(pid: int, tid: int, sid: int) -> bool:
    return shiny_xor(pid, tid, sid) < 8


def _iv_words_from_spread(iv_hp: int, iv_atk: int, iv_def: int, iv_spa: int, iv_spd: int, iv_spe: int) -> tuple[int, int]:
    iv1 = (int(iv_hp) & 31) | ((int(iv_atk) & 31) << 5) | ((int(iv_def) & 31) << 10)
    iv2 = (int(iv_spe) & 31) | ((int(iv_spa) & 31) << 5) | ((int(iv_spd) & 31) << 10)
    return iv1, iv2


def _label_for(method: str, context: str) -> str:
    if context == "wild":
        return {"Method 1": "Method H1", "Method 2": "Method H2", "Method 4": "Method H4"}[method]
    return method


def locate_generation_seed(
    capture_seed: int,
    pid: int,
    iv_hp: int,
    iv_atk: int,
    iv_def: int,
    iv_spa: int,
    iv_spd: int,
    iv_spe: int,
    *,
    methods: tuple[str, ...] = ("Method 1", "Method 2", "Method 4"),
    max_back: int = DEFAULT_RECONSTRUCT_BACK,
) -> tuple[int, int, str] | None:
    """Reconstruct the PID-start state for Gen-III Method 1/2/4 families.

    PID calls are consecutive for all three families. IV placement differs:
      Method 1: PID1, PID2, IV1, IV2
      Method 2: PID1, PID2, skip, IV1, IV2
      Method 4: PID1, PID2, IV1, skip, IV2

    Wild H1/H2/H4 use the same final PID/IV spacing after their encounter/nature
    setup, so the caller can label a validated result with H terminology.
    """

    capture_seed = int(capture_seed) & MASK32
    want_low = int(pid) & 0xFFFF
    want_high = (int(pid) >> 16) & 0xFFFF
    want_iv1, want_iv2 = _iv_words_from_spread(iv_hp, iv_atk, iv_def, iv_spa, iv_spd, iv_spe)
    enabled = set(methods)

    g = capture_seed
    f1 = f2 = f3 = f4 = f5 = None
    for distance in range(1, int(max_back) + 1):
        old = g
        g = prev_seed(g)
        f5, f4, f3, f2, f1 = f4, f3, f2, f1, old
        if distance < 4:
            continue
        if (f1 >> 16) != want_low or (f2 >> 16) != want_high:
            continue

        hi3 = (f3 >> 16) & 0x7FFF
        hi4 = (f4 >> 16) & 0x7FFF
        if "Method 1" in enabled and hi3 == want_iv1 and hi4 == want_iv2:
            return g, distance, "Method 1"

        if distance < 5:
            continue
        hi5 = (f5 >> 16) & 0x7FFF
        if "Method 2" in enabled and hi4 == want_iv1 and hi5 == want_iv2:
            return g, distance, "Method 2"
        if "Method 4" in enabled and hi3 == want_iv1 and hi5 == want_iv2:
            return g, distance, "Method 4"
    return None


def locate_method1_generation_seed(
    capture_seed: int,
    pid: int,
    iv_hp: int,
    iv_atk: int,
    iv_def: int,
    iv_spa: int,
    iv_spd: int,
    iv_spe: int,
    max_back: int = DEFAULT_RECONSTRUCT_BACK,
) -> tuple[int, int] | None:
    """Backwards-compatible strict Method-1 locator used by v0.13 tests/tools."""
    result = locate_generation_seed(
        capture_seed, pid, iv_hp, iv_atk, iv_def, iv_spa, iv_spd, iv_spe,
        methods=("Method 1",), max_back=max_back,
    )
    return None if result is None else (result[0], result[1])


def locate_roamer_generation_seed(
    capture_seed: int,
    pid: int,
    iv_byte: int,
    max_back: int = DEFAULT_RECONSTRUCT_BACK,
) -> tuple[int, int] | None:
    """Reconstruct FRLG's bugged roaming-beast Method-1 generation.

    FRLG keeps the PID but only the low byte of the first IV RNG output when the
    roamer is loaded. PID (32 bits) + that surviving IV byte are validated.
    """
    capture_seed = int(capture_seed) & MASK32
    want_low = int(pid) & 0xFFFF
    want_high = (int(pid) >> 16) & 0xFFFF
    want_iv_byte = int(iv_byte) & 0xFF

    g = capture_seed
    f1 = f2 = f3 = None
    for distance in range(1, int(max_back) + 1):
        old = g
        g = prev_seed(g)
        f3, f2, f1 = f2, f1, old
        if distance < 3:
            continue
        if (f1 >> 16) != want_low or (f2 >> 16) != want_high:
            continue
        if ((f3 >> 16) & 0xFF) == want_iv_byte:
            return g, distance
    return None


def nearest_method1_shiny(
    generation_seed: int,
    tid: int,
    sid: int,
    observed_pid: int | None = None,
    max_scan: int = DEFAULT_SHINY_SCAN,
) -> tuple[int | None, int | None, int | None]:
    """Find nearest raw shiny PID-start states around the observed PID frame."""
    generation_seed = int(generation_seed) & MASK32
    if observed_pid is not None and is_shiny_pid(observed_pid, tid, sid):
        return 0, 0, 0

    previous = None
    g = generation_seed
    for distance in range(1, int(max_scan) + 1):
        g = prev_seed(g)
        if is_shiny_pid(method1_pid(g), tid, sid):
            previous = distance
            break

    nxt = None
    g = generation_seed
    for distance in range(1, int(max_scan) + 1):
        g = next_seed(g)
        if is_shiny_pid(method1_pid(g), tid, sid):
            nxt = distance
            break

    if previous is None and nxt is None:
        nearest = None
    elif previous is None:
        nearest = nxt
    elif nxt is None:
        nearest = -previous
    elif previous <= nxt:
        nearest = -previous
    else:
        nearest = nxt
    return previous, nxt, nearest


def miss_from_capture(
    capture_seed: int,
    pid: int,
    tid: int,
    sid: int,
    *,
    iv_hp: int,
    iv_atk: int,
    iv_def: int,
    iv_spa: int,
    iv_spd: int,
    iv_spe: int,
    context: str = "standard",
    max_back: int = DEFAULT_RECONSTRUCT_BACK,
    max_scan: int = DEFAULT_SHINY_SCAN,
) -> RNGMissResult:
    """Validate Method 1/2/4 (or H1/H2/H4) and report nearest shiny PID frame."""
    capture_seed = int(capture_seed) & MASK32
    if is_shiny_pid(pid, tid, sid):
        label = "Method H*" if context == "wild" else "Gen III PID"
        return RNGMissResult(label, capture_seed, None, None, 0, 0, 0, True)

    located = locate_generation_seed(
        capture_seed, pid, iv_hp, iv_atk, iv_def, iv_spa, iv_spd, iv_spe,
        max_back=max_back,
    )
    if located is None:
        label = "Method H1/H2/H4" if context == "wild" else "Method 1/2/4"
        return RNGMissResult(label, capture_seed, None, None, None, None, None, False)

    generation_seed, distance, method = located
    previous, nxt, miss = nearest_method1_shiny(generation_seed, tid, sid, observed_pid=pid, max_scan=max_scan)
    return RNGMissResult(_label_for(method, context), capture_seed, generation_seed, distance, previous, nxt, miss, True)


def method1_miss_from_capture(
    capture_seed: int,
    pid: int,
    tid: int,
    sid: int,
    *,
    iv_hp: int,
    iv_atk: int,
    iv_def: int,
    iv_spa: int,
    iv_spd: int,
    iv_spe: int,
    max_back: int = DEFAULT_RECONSTRUCT_BACK,
    max_scan: int = DEFAULT_SHINY_SCAN,
) -> RNGMissResult:
    """Backwards-compatible strict Method-1 v0.13 API."""
    capture_seed = int(capture_seed) & MASK32
    if is_shiny_pid(pid, tid, sid):
        return RNGMissResult("Method 1", capture_seed, None, None, 0, 0, 0, True)
    located = locate_generation_seed(
        capture_seed, pid, iv_hp, iv_atk, iv_def, iv_spa, iv_spd, iv_spe,
        methods=("Method 1",), max_back=max_back,
    )
    if located is None:
        return RNGMissResult("Method 1", capture_seed, None, None, None, None, None, False)
    generation_seed, distance, _ = located
    previous, nxt, miss = nearest_method1_shiny(generation_seed, tid, sid, observed_pid=pid, max_scan=max_scan)
    return RNGMissResult("Method 1", capture_seed, generation_seed, distance, previous, nxt, miss, True)


def roamer_miss_from_capture(
    capture_seed: int,
    pid: int,
    tid: int,
    sid: int,
    *,
    iv_byte: int,
    max_back: int = DEFAULT_RECONSTRUCT_BACK,
    max_scan: int = DEFAULT_SHINY_SCAN,
) -> RNGMissResult:
    """FRLG roaming-beast shiny-frame miss with bugged-IV validation."""
    capture_seed = int(capture_seed) & MASK32
    method = "Method 1 (FRLG roamer IV bug)"
    if is_shiny_pid(pid, tid, sid):
        return RNGMissResult(method, capture_seed, None, None, 0, 0, 0, True)
    located = locate_roamer_generation_seed(capture_seed, pid, iv_byte, max_back=max_back)
    if located is None:
        return RNGMissResult(method, capture_seed, None, None, None, None, None, False)
    generation_seed, distance = located
    previous, nxt, miss = nearest_method1_shiny(generation_seed, tid, sid, observed_pid=pid, max_scan=max_scan)
    return RNGMissResult(method, capture_seed, generation_seed, distance, previous, nxt, miss, True)


@dataclass(frozen=True)
class Method1Target:
    """A future PID-start state selected directly from the live Gen-III RNG."""

    start_seed: int
    generation_seed: int
    advances: int
    pid: int
    shiny_xor: int
    nature_index: int
    iv_hp: int
    iv_atk: int
    iv_def: int
    iv_spa: int
    iv_spd: int
    iv_spe: int

    @property
    def iv_sum(self) -> int:
        return self.iv_hp + self.iv_atk + self.iv_def + self.iv_spa + self.iv_spd + self.iv_spe

    def to_dict(self) -> dict:
        return asdict(self)


def advance_seed(seed: int, advances: int) -> int:
    """Advance PokeRNG by *advances* calls in O(log n)."""
    n = int(advances)
    if n < 0:
        return rewind_seed(seed, -n)
    acc_mult, acc_add = 1, 0
    cur_mult, cur_add = MULT, ADD
    while n:
        if n & 1:
            acc_mult = (acc_mult * cur_mult) & MASK32
            acc_add = (acc_add * cur_mult + cur_add) & MASK32
        cur_add = (cur_add * ((cur_mult + 1) & MASK32)) & MASK32
        cur_mult = (cur_mult * cur_mult) & MASK32
        n >>= 1
    return ((int(seed) & MASK32) * acc_mult + acc_add) & MASK32


def rewind_seed(seed: int, advances: int) -> int:
    """Rewind PokeRNG by *advances* calls in O(log n)."""
    n = int(advances)
    if n < 0:
        return advance_seed(seed, -n)
    # One reverse step is also affine: x <- INV_MULT*x - ADD*INV_MULT.
    rev_mult = INV_MULT & MASK32
    rev_add = (-ADD * INV_MULT) & MASK32
    acc_mult, acc_add = 1, 0
    cur_mult, cur_add = rev_mult, rev_add
    while n:
        if n & 1:
            acc_mult = (acc_mult * cur_mult) & MASK32
            acc_add = (acc_add * cur_mult + cur_add) & MASK32
        cur_add = (cur_add * ((cur_mult + 1) & MASK32)) & MASK32
        cur_mult = (cur_mult * cur_mult) & MASK32
        n >>= 1
    return ((int(seed) & MASK32) * acc_mult + acc_add) & MASK32


def forward_distance_limited(start_seed: int, end_seed: int, max_steps: int = 10000) -> int | None:
    """Return a nearby forward RNG distance, or None when it exceeds max_steps."""
    want = int(end_seed) & MASK32
    g = int(start_seed) & MASK32
    if g == want:
        return 0
    for distance in range(1, int(max_steps) + 1):
        g = next_seed(g)
        if g == want:
            return distance
    return None


def nearby_signed_distance(reference_seed: int, observed_seed: int, max_steps: int = 10000) -> int | None:
    """Signed local distance from reference to observed; +late, -early."""
    reference = int(reference_seed) & MASK32
    observed = int(observed_seed) & MASK32
    if reference == observed:
        return 0
    f = reference
    b = reference
    for distance in range(1, int(max_steps) + 1):
        f = next_seed(f)
        if f == observed:
            return distance
        b = prev_seed(b)
        if b == observed:
            return -distance
    return None


def method1_ivs(seed_before_pid: int) -> tuple[int, int, int, int, int, int]:
    """Return HP/Atk/Def/SpA/SpD/Spe for a Method-1 PID-start state."""
    s1 = next_seed(seed_before_pid)
    s2 = next_seed(s1)
    s3 = next_seed(s2)
    s4 = next_seed(s3)
    iv1 = (s3 >> 16) & 0x7FFF
    iv2 = (s4 >> 16) & 0x7FFF
    hp = iv1 & 31
    atk = (iv1 >> 5) & 31
    de = (iv1 >> 10) & 31
    spe = iv2 & 31
    spa = (iv2 >> 5) & 31
    spd = (iv2 >> 10) & 31
    return hp, atk, de, spa, spd, spe


def find_method1_target(
    start_seed: int,
    tid: int,
    sid: int,
    *,
    shiny_only: bool = True,
    nature_index: int | None = None,
    min_ivs: tuple[int, int, int, int, int, int] = (0, 0, 0, 0, 0, 0),
    min_advances: int = 0,
    max_advances: int = 500_000,
) -> Method1Target | None:
    """Search forward from a live RNG state for a Method-1 target.

    This searches the actual 32-bit PokeRNG stream, not a timer-derived initial
    seed. It is intended for deterministic standard PID-generation routines.
    Wild H-method encounter setup must be modeled separately.
    """
    lo = max(0, int(min_advances))
    hi = max(lo, int(max_advances))
    mins = tuple(max(0, min(31, int(v))) for v in min_ivs)
    if len(mins) != 6:
        raise ValueError("min_ivs must contain HP/Atk/Def/SpA/SpD/Spe")
    g = advance_seed(start_seed, lo)
    for distance in range(lo, hi + 1):
        pid = method1_pid(g)
        sx = shiny_xor(pid, tid, sid)
        if (not shiny_only or sx < 8) and (nature_index is None or pid % 25 == int(nature_index)):
            ivs = method1_ivs(g)
            if all(iv >= need for iv, need in zip(ivs, mins)):
                return Method1Target(
                    int(start_seed) & MASK32, g, distance, pid, sx, pid % 25,
                    ivs[0], ivs[1], ivs[2], ivs[3], ivs[4], ivs[5],
                )
        g = next_seed(g)
    return None
