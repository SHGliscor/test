// Gen 5 Auto Discovery v1.6: mirrored pointer descriptor in NRO and heap.
// Read-only to emulated DS game. Accessed externally via USB-Botbase peekAbsolute.
// No network, controller, or memory mutation of the game.
#include "Gen5Auto.h"
#include "Gen5BootTrace.h"
#include "NDS.h"
#include <cstdint>
#include <cstdlib>
#include <cstring>

struct alignas(8) Gen5AutoDiscovery {
    std::uint8_t magic[8];       // "PB5AUTO1"
    std::uint32_t version;       // 1
    std::uint32_t size;          // 104
    std::uint64_t sequence;      // committed even; odd = writer active
    std::uint64_t mainram_ptr;
    std::uint64_t trace_ptr;
    std::uint64_t mainram_inverse;
    std::uint64_t trace_inverse;
    std::uint64_t mainram_copy;
    std::uint64_t trace_copy;
    std::uint32_t ram_mask;
    std::uint32_t game;          // 0=not ready, 1..4 English Gen5
    std::uint32_t header_offset; // 0x003FFE00
    std::uint32_t status;        // 1=ready, 2=not ready
    std::uint8_t tag[16];        // "MELONDS_GEN5_V1"
};
static_assert(sizeof(Gen5AutoDiscovery) == 104, "Auto descriptor ABI");
extern "C" {
    __attribute__((used, externally_visible, aligned(16)))
    Gen5AutoDiscovery pokebot_gen5_auto_discovery = {
        {'P','B','5','A','U','T','O','1'},
        1,104,0,
        0,0,0,0,0,0,
        0,0,0x003FFE00,2,
        {'M','E','L','O','N','D','S','_','G','E','N','5','_','V','1',0}
    };
}
namespace {
std::uint32_t Game(const std::uint8_t* ram, std::uint32_t mask) {
    if (ram == nullptr || mask != 0x003FFFFF) return 0;
    const auto* header = ram + 0x003FFE00;
    if (header[0] != 'P' || header[1] != 'O' || header[2] != 'K'
        || header[3] != 'E' || header[4] != 'M' || header[5] != 'O'
        || header[6] != 'N' || header[15] != 'O' ||
        header[16] != '0' || header[17] != '1') return 0;
    if (header[12] != 'I' || header[13] != 'R') return 0;
    if (header[14] == 'B') return 1;
    if (header[14] == 'A') return 2;
    if (header[14] == 'E') return 3;
    if (header[14] == 'D') return 4;
    return 0;
}
Gen5AutoDiscovery* g_heap_mirror = nullptr;

void PublishTo(Gen5AutoDiscovery& d, std::uint64_t ram_ptr,
               std::uint64_t trace_ptr, std::uint32_t mask,
               std::uint32_t game, std::uint32_t status) {
    // Keep the descriptor untouched on idle frames for stable USB snapshots.
    if (d.mainram_ptr == ram_ptr && d.trace_ptr == trace_ptr &&
        d.ram_mask == mask && d.game == game && d.status == status) return;
    const auto prior = __atomic_load_n(&d.sequence, __ATOMIC_RELAXED);
    __atomic_store_n(&d.sequence, prior + 1, __ATOMIC_RELEASE);
    d.mainram_ptr = ram_ptr;
    d.trace_ptr = trace_ptr;
    d.mainram_inverse = ~ram_ptr;
    d.trace_inverse = ~trace_ptr;
    d.mainram_copy = ram_ptr;
    d.trace_copy = trace_ptr;
    d.ram_mask = mask;
    d.game = game;
    d.header_offset = 0x003FFE00;
    d.status = status;
    __atomic_store_n(&d.sequence, prior + 2, __ATOMIC_RELEASE);
}

void Publish(bool active) {
    const auto* ram = active ? NDS::MainRAM : nullptr;
    const auto ram_ptr = reinterpret_cast<std::uint64_t>(ram);
    const auto trace_ptr = active ?
        static_cast<std::uint64_t>(Gen5BootTrace::BufferAddress()) : 0ULL;
    const std::uint32_t mask = active && ram ? NDS::MainRAMMask : 0;
    const std::uint32_t game = Game(ram, mask);
    const std::uint32_t status =
        (ram_ptr && trace_ptr && mask == 0x003FFFFF && game) ? 1 : 2;
    PublishTo(pokebot_gen5_auto_discovery,
              ram_ptr, trace_ptr, mask, game, status);
    if (g_heap_mirror != nullptr)
        PublishTo(*g_heap_mirror, ram_ptr, trace_ptr, mask, game, status);
}

}
namespace Gen5Auto {
void Init() {
    // The NRO's static data may not be mapped at Koi's reported main NSO
    // base. Allocate a *separate* 4 KiB heap page with an identical descriptor
    // for a bounded getHeapBase-relative USB search. Never touch guest RAM.
    if (g_heap_mirror == nullptr) {
        void* page = aligned_alloc(0x1000, 0x1000);
        if (page != nullptr) {
            std::memset(page, 0, 0x1000);
            auto* d = static_cast<Gen5AutoDiscovery*>(page);
            std::memcpy(d, &pokebot_gen5_auto_discovery, sizeof(*d));
            g_heap_mirror = d;
        }
    }
    Publish(true);
}
void Update() { Publish(true); }
void DeInit() {
    Publish(false);
    if (g_heap_mirror != nullptr) {
        std::memset(g_heap_mirror, 0, 0x1000);
        free(g_heap_mirror);
        g_heap_mirror = nullptr;
    }
}
}
