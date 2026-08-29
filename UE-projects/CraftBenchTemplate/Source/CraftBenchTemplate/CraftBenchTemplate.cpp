// Copyright CraftBench. All Rights Reserved.
//
// Primary game module implementation for the CraftBenchTemplate substrate.
// Registers CraftBenchTemplate as the primary game module via
// IMPLEMENT_PRIMARY_GAME_MODULE; UE 5.7 expects exactly one such macro per
// .uproject runtime module set. No startup or shutdown logic is needed — the
// default FDefaultGameModuleImpl is sufficient for the agent-writable module.

#include "CraftBenchTemplate.h"

IMPLEMENT_PRIMARY_GAME_MODULE(FDefaultGameModuleImpl, CraftBenchTemplate, "CraftBenchTemplate");
