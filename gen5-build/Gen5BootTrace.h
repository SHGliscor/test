#pragma once
#include <cstdint>

// Read-only Gen 5 timing evidence: one sample per emulated DS frame.
namespace Gen5BootTrace {
void Init();
void OnFrame();
// Called by the emulated DS hardware handlers; passive observation only.
void OnTimer0Read(std::uint16_t timer0, std::uint16_t vcount, std::uint32_t gxstat);
void OnRTCRead(const std::uint8_t* bcd, std::uint32_t length);
void DeInit();
std::uintptr_t BufferAddress();
}
