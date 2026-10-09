#pragma once
#include <cstdint>

// Read-only Gen 5 timing evidence: one sample per emulated DS frame.
namespace Gen5BootTrace {
void Init();
void OnFrame();
void DeInit();
std::uintptr_t BufferAddress();
}
