// Copyright CraftBench. All Rights Reserved.
//
// VERIFIER-ONLY MODULE — DO NOT EDIT.
// See Source/CraftBenchTests/.AGENT_WRITE_DENY for the no-edit policy.
//
// Editor module implementation for CraftBenchTests. Uses IMPLEMENT_MODULE
// (not IMPLEMENT_PRIMARY_GAME_MODULE — only the runtime module owns the
// primary-game-module slot). FDefaultModuleImpl is sufficient; no startup
// state is needed for the AFunctionalTest discovery surface to find
// ASanityFunctionalTest at editor load.

#include "CraftBenchTests.h"

IMPLEMENT_MODULE(FDefaultModuleImpl, CraftBenchTests);
