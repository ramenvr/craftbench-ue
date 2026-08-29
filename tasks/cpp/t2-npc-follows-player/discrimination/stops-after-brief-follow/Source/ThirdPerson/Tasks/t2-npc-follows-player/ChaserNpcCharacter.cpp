// Copyright CraftBench. All Rights Reserved.
//
// Variant copy of the reference character (tag + auto-possessed AI
// controller); the gaming delta lives in ChaserAiController.cpp.

#include "ChaserNpcCharacter.h"

#include "ChaserAiController.h"

AChaserNpcCharacter::AChaserNpcCharacter()
{
	Tags.Add(FName("ChaserNpc"));
	AIControllerClass = AChaserAiController::StaticClass();
	AutoPossessAI = EAutoPossessAI::PlacedInWorldOrSpawned;
}
