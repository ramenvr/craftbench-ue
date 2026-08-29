// Copyright CraftBench. All Rights Reserved.
//
// Primary game module header for the CraftBenchTemplate substrate. This is the
// agent-writable runtime module the t0 task and every later atomic task ships
// against. Pairs with CraftBenchTemplate.cpp which provides the
// IMPLEMENT_PRIMARY_GAME_MODULE registration. Adding new headers to this module
// is permitted; agents authoring a task solution typically edit SanityActor.h /
// SanityActor.cpp (or analogous task-actor pairs) rather than this file.

#pragma once

#include "CoreMinimal.h"
#include "Modules/ModuleManager.h"
