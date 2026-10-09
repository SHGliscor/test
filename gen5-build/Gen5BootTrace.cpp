// Gen 5 SHA1 Boot Preimage Evidence v1.3. No writes to guest DS RAM; no buttons, cheats, save states.
#include "Gen5BootTrace.h"
#include "NDS.h"
#include "Wifi.h"
#include "GPU.h"
#include "GPU3D.h"
#include <ctime>
#include <cstdint>
#include <cstdlib>
#include <cstring>

namespace Gen5BootTrace {
namespace {
constexpr std::uint32_t Capacity = 120;
constexpr std::size_t AllocationSize = 0x5000;

struct alignas(8) Header {
    char magic[8];                 // "PB5EVT13"
    std::uint32_t version;         // 4
    std::uint32_t header_size;     // 64
    std::uint32_t entry_size;      // 160
    std::uint32_t capacity;        // 120
    std::uint64_t total_events;    // committed events
    std::uint64_t frame_counter;   // NDS::RunFrame() calls observed
    std::uint64_t mainram_ptr;     // host pointer to DS RAM (may change)
    std::uint32_t ds_mask;         // 0x003FFFFF for DS
    std::uint32_t game;            // 1=Black,2=White,3=Black2,4=White2
    std::uint32_t status;          // 1 = active, 2 = DS header not ready
    std::uint32_t dropped;         // reserved
};
struct alignas(8) Event {
    std::uint64_t sequence;        // committed last; 0 means slot is being written
    std::uint64_t frame;           // frame number
    std::uint64_t rng;             // first value seen at this frame boundary
    std::uint32_t mt_seed;
    std::uint32_t mt_index;
    std::uint32_t delay;
    std::uint32_t prev_delay;
    std::uint32_t prev_mt_seed;
    std::uint32_t flags;           // 1=baseline 2=delay-drop 4=MT-change 8=0-to-seed 16=high32=MT 32=game-change
    std::uint64_t prev_rng;
    std::uint64_t reserved;
    // Independent MT19937 initialization-array verification, sampled on the
    // *same emulated frame* that the MT seed changes. This does not derive SHA-1.
    std::uint32_t mt_checked_words;   // 624 if fully checked
    std::uint32_t mt_first_bad_index; // 0xFFFFFFFF if no mismatch
    std::uint32_t mt_actual_bad;
    std::uint32_t mt_expected_bad;
    std::uint64_t mt_observed_hash;
    std::uint64_t mt_expected_hash;
    std::uint32_t mt_audit_status;    // 0=not_checked,1=match,2=mismatch,3=not_seeded
    std::uint32_t reserved2;
    std::uint32_t key_input;        // KEYINPUT low16, active-low
    std::uint32_t input_reserved;
    std::uint64_t latest_reset_combo_frame; // 0 if never observed
    // 40-byte host-side boot context: aids offline SHA1 parameter calibration.
    // RTC is sampled at this frame boundary (NOT the game's SHA1 RTC read).
    std::int64_t unix_seconds;
    std::uint8_t rtc_bcd[7];    // YY MM DD day-of-week HH MM SS (Switch localtime)
    std::uint8_t rtc_valid;
    std::uint8_t wifi_mac[6];   // WiFi::GetMAC registers; must be validated
    std::uint8_t mac_valid;
    std::uint8_t mac_reserved;
    std::uint32_t gpu_vcount;
    std::uint32_t console_type;
    std::uint32_t gxstat_at_frame;
    std::uint32_t context_reserved;
};
static_assert(sizeof(Header) == 64, "BootTrace header layout mismatch");
static_assert(sizeof(Event) == 160, "BootTrace event layout mismatch");
struct Trace {
    Header header;
    Event events[Capacity];
};
static_assert(sizeof(Trace) <= AllocationSize, "BootTrace allocation too small");

Trace* g_trace = nullptr;
std::uint32_t g_game = 0;
std::uint64_t g_rng = 0;
std::uint32_t g_mt = 0, g_index = 0, g_delay = 0;
bool g_have_previous = false;
bool g_prev_reset_combo = false;
std::uint64_t g_latest_reset_combo_frame = 0;

inline std::uint32_t Read32(const std::uint8_t* ram, std::uint32_t addr) {
    std::uint32_t value;
    std::memcpy(&value, ram + (addr & 0x003FFFFF), sizeof(value));
    return value;
}
inline std::uint64_t Read64(const std::uint8_t* ram, std::uint32_t addr) {
    std::uint64_t value;
    std::memcpy(&value, ram + (addr & 0x003FFFFF), sizeof(value));
    return value;
}

std::uint32_t Game(const std::uint8_t* ram) {
    const auto* hdr = ram + 0x003FFE00;
    if (std::memcmp(hdr, "POKEMON", 7) != 0 || hdr[15] != 'O')
        return 0;
    if (std::memcmp(hdr + 12, "IRBO", 4) == 0) return 1;
    if (std::memcmp(hdr + 12, "IRAO", 4) == 0) return 2;
    if (std::memcmp(hdr + 12, "IREO", 4) == 0) return 3;
    if (std::memcmp(hdr + 12, "IRDO", 4) == 0) return 4;
    return 0;
}

struct MTAudit {
    std::uint32_t checked = 0, first_bad = 0xFFFFFFFFu, bad_actual = 0, bad_expected = 0;
    std::uint64_t observed_hash = 14695981039346656037ULL;
    std::uint64_t expected_hash = 14695981039346656037ULL;
    std::uint32_t status = 0;
};
inline std::uint8_t BCD(unsigned val) {
    return static_cast<std::uint8_t>(((val / 10) << 4) | (val % 10));
}

inline std::uint64_t FoldWord(std::uint64_t hash, std::uint32_t word) {
    for (int i=0; i<4; ++i) {
        hash ^= static_cast<std::uint8_t>(word >> (8*i));
        hash *= 1099511628211ULL;
    }
    return hash;
}
// Verify the real 624-word MT array, not just the first word. Only index 624
// means the initial array should still be untouched by a twist/advance.
MTAudit AuditMT(const std::uint8_t* ram, std::uint32_t mt_addr,
                std::uint32_t seed, std::uint32_t index) {
    MTAudit audit;
    if (index != 624 || seed == 0) {
        audit.status = 3;
        return audit;
    }
    std::uint32_t expected = seed;
    for (std::uint32_t i=0; i<624; ++i) {
        if (i != 0)
            expected = 1812433253u * (expected ^ (expected >> 30)) + i;
        const std::uint32_t actual = Read32(ram, mt_addr + 4*i);
        ++audit.checked;
        audit.observed_hash = FoldWord(audit.observed_hash, actual);
        audit.expected_hash = FoldWord(audit.expected_hash, expected);
        if (actual != expected && audit.first_bad == 0xFFFFFFFFu) {
            audit.first_bad = i;
            audit.bad_actual = actual;
            audit.bad_expected = expected;
        }
    }
    audit.status = audit.first_bad == 0xFFFFFFFFu ? 1 : 2;
    return audit;
}
void Record(std::uint64_t rng, std::uint32_t mt, std::uint32_t index,
            std::uint32_t delay, std::uint32_t flags, const MTAudit& audit) {
    if (g_trace == nullptr) return;
    auto& h = g_trace->header;
    const std::uint64_t seq = h.total_events + 1;
    auto& e = g_trace->events[(seq - 1) % Capacity];
    __atomic_store_n(&e.sequence, 0ULL, __ATOMIC_RELEASE);
    e.frame = h.frame_counter;
    e.rng = rng;
    e.mt_seed = mt;
    e.mt_index = index;
    e.delay = delay;
    e.prev_delay = g_delay;
    e.prev_mt_seed = g_mt;
    e.flags = flags;
    e.prev_rng = g_rng;
    e.reserved = 0;
    e.mt_checked_words = audit.checked;
    e.mt_first_bad_index = audit.first_bad;
    e.mt_actual_bad = audit.bad_actual;
    e.mt_expected_bad = audit.bad_expected;
    e.mt_observed_hash = audit.observed_hash;
    e.mt_expected_hash = audit.expected_hash;
    e.mt_audit_status = audit.status;
    e.reserved2 = 0;
    e.key_input = static_cast<std::uint32_t>(NDS::KeyInput & 0xFFFF);
    e.input_reserved = 0;
    e.latest_reset_combo_frame = g_latest_reset_combo_frame;

    e.unix_seconds = static_cast<std::int64_t>(std::time(nullptr));
    std::tm local{};
    const std::time_t timestamp = static_cast<std::time_t>(e.unix_seconds);
    std::memset(e.rtc_bcd, 0, sizeof(e.rtc_bcd));
    e.rtc_valid = 0;
    if (localtime_r(&timestamp, &local) != nullptr && local.tm_year >= 100) {
        e.rtc_bcd[0] = BCD(static_cast<unsigned>((local.tm_year - 100) % 100));
        e.rtc_bcd[1] = BCD(static_cast<unsigned>(local.tm_mon + 1));
        e.rtc_bcd[2] = BCD(static_cast<unsigned>(local.tm_mday));
        e.rtc_bcd[3] = BCD(static_cast<unsigned>(local.tm_wday));
        e.rtc_bcd[4] = BCD(static_cast<unsigned>(local.tm_hour));
        e.rtc_bcd[5] = BCD(static_cast<unsigned>(local.tm_min));
        e.rtc_bcd[6] = BCD(static_cast<unsigned>(local.tm_sec));
        e.rtc_valid = 1;
    }
    // MAC comes from live emulated WiFi IO registers.
    // Whether this equals the seed's firmware MAC must be calibrated.
    const std::uint8_t* mac = Wifi::GetMAC();
    e.mac_valid = 0;
    e.mac_reserved = 0;
    std::memset(e.wifi_mac, 0, sizeof(e.wifi_mac));
    if (mac != nullptr) {
        std::memcpy(e.wifi_mac, mac, sizeof(e.wifi_mac));
        for (unsigned k=0; k<6; ++k) {
            if (e.wifi_mac[k] != 0) e.mac_valid = 1;
        }
    }
    e.gpu_vcount = static_cast<std::uint32_t>(GPU::VCount);
    e.console_type = static_cast<std::uint32_t>(NDS::ConsoleType);
    e.gxstat_at_frame = GPU3D::Read32(0x04000600);
    e.context_reserved = 0;
    __atomic_store_n(&e.sequence, seq, __ATOMIC_RELEASE);
    __atomic_store_n(&h.total_events, seq, __ATOMIC_RELEASE);
}
}

void Init() {
    if (g_trace != nullptr) return;
    void* data = aligned_alloc(0x1000, AllocationSize);
    if (data == nullptr) return;
    std::memset(data, 0, AllocationSize);
    g_trace = static_cast<Trace*>(data);
    std::memcpy(g_trace->header.magic, "PB5EVT13", 8);
    g_trace->header.version = 4;
    g_trace->header.header_size = sizeof(Header);
    g_trace->header.entry_size = sizeof(Event);
    g_trace->header.capacity = Capacity;
    g_trace->header.status = 2;
    g_have_previous = false;
    g_game = 0;
    g_prev_reset_combo = false;
    g_latest_reset_combo_frame = 0;
}

std::uintptr_t BufferAddress() {
    return reinterpret_cast<std::uintptr_t>(g_trace);
}

void OnFrame() {
    if (g_trace == nullptr || NDS::MainRAM == nullptr) return;
    auto& h = g_trace->header;
    ++h.frame_counter;
    h.mainram_ptr = reinterpret_cast<std::uintptr_t>(NDS::MainRAM);
    h.ds_mask = NDS::MainRAMMask;
    if (NDS::MainRAMMask != 0x003FFFFF) {
        h.status = 2;
        g_have_previous = false;
        return;
    }
    const auto* ram = NDS::MainRAM;
    const auto game = Game(ram);
    h.game = game;
    h.status = game ? 1 : 2;
    if (game == 0) {
        g_have_previous = false;
        g_game = 0;
        return;
    }

    const std::uint32_t rng_addr = game == 1 ? 0x02216224 :
                                   game == 2 ? 0x02216244 :
                                   game == 3 ? 0x021FFC18 : 0x021FFC58;
    const std::uint32_t mt_addr = game == 1 ? 0x02215354 :
                                  game == 2 ? 0x02215374 :
                                  game == 3 ? 0x021FED28 : 0x021FED68;
    const std::uint32_t index_addr = game == 1 ? 0x02215D14 :
                                     game == 2 ? 0x02215D34 :
                                     game == 3 ? 0x021FF6E8 : 0x021FF728;
    // Nintendo DS KEYINPUT is active-low: SELECT=bit2 START=bit3
    // R=bit8 L=bit9. Record the first emulated frame with all held.
    constexpr std::uint32_t ResetComboMask = 0x030C;
    const bool reset_combo = (NDS::KeyInput & ResetComboMask) == 0;
    const bool reset_combo_edge = reset_combo && !g_prev_reset_combo;
    g_prev_reset_combo = reset_combo;
    if (reset_combo_edge) g_latest_reset_combo_frame = h.frame_counter;

    const std::uint64_t rng = Read64(ram, rng_addr);
    const std::uint32_t mt = Read32(ram, mt_addr);
    const std::uint32_t index = Read32(ram, index_addr);
    const std::uint32_t delay = Read32(ram, 0x02FFFC3C);

    std::uint32_t flags = 0;
    if (!g_have_previous) flags |= 1;
    if (g_have_previous && delay < g_delay && g_delay - delay >= 16) flags |= 2;
    if (g_have_previous && mt != g_mt) flags |= 4;
    if (g_have_previous && g_rng == 0 && rng != 0) flags |= 8;
    if (rng != 0 && mt != 0 && (rng >> 32) == mt) flags |= 16;
    if (g_game != game) flags |= 32;
    if (reset_combo_edge) flags |= 64;

    // Only record interesting edges. Current-seed matching alone is common
    // during idle: it is evidence, not a reset trigger.
    if (flags & (1 | 2 | 4 | 8 | 32 | 64)) {
        MTAudit audit;
        // Perform this extra verification only at the potential
        // initialization edge, never on every emulated frame.
        if (flags & 4)
            audit = AuditMT(ram, mt_addr, mt, index);
        Record(rng, mt, index, delay, flags, audit);
    }

    g_game = game;
    g_have_previous = true;
    g_rng = rng;
    g_mt = mt;
    g_index = index;
    g_delay = delay;
}

void DeInit() {
    if (g_trace == nullptr) return;
    std::memset(g_trace, 0, sizeof(Trace));
    free(g_trace);
    g_trace = nullptr;
    g_have_previous = false;
    g_game = 0;
    g_prev_reset_combo = false;
    g_latest_reset_combo_frame = 0;
}
}
