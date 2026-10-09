// Gen 5 Auto Discovery v1.5: constant-format descriptor in NRO static memory.
// Read-only to emulated DS game. Accessed externally via USB-Botbase peekAbsolute.
// No network, controller, or memory mutation of the game.
#include "Gen5Auto.h"
#include "Gen5BootTrace.h"
#include "NDS.h"
#include <cstdint>

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
void Publish(bool active) {
    auto& d = pokebot_gen5_auto_discovery;
    const auto old = __atomic_load_n(&d.sequence, __ATOMIC_RELAXED);
    __atomic_store_n(&d.sequence, old + 1, __ATOMIC_RELEASE);
    const auto* ram = active ? NDS::MainRAM : nullptr;
    const auto ram_ptr = reinterpret_cast<std::uint64_t>(ram);
    const auto trace_ptr = active ?
        static_cast<std::uint64_t>(Gen5BootTrace::BufferAddress()) : 0ULL;
    const std::uint32_t mask = active && ram ? NDS::MainRAMMask : 0;
    const std::uint32_t game = Game(ram, mask);
    d.mainram_ptr = ram_ptr;
    d.trace_ptr = trace_ptr;
    d.mainram_inverse = ~ram_ptr;
    d.trace_inverse = ~trace_ptr;
    d.mainram_copy = ram_ptr;
    d.trace_copy = trace_ptr;
    d.ram_mask = mask;
    d.game = game;
    d.header_offset = 0x003FFE00;
    d.status = (ram_ptr && trace_ptr && mask == 0x003FFFFF && game) ? 1 : 2;
    __atomic_store_n(&d.sequence, old + 2, __ATOMIC_RELEASE);
}
}
namespace Gen5Auto {
void Init() { Publish(true); }
void Update() { Publish(true); }
void DeInit() { Publish(false); }
}
