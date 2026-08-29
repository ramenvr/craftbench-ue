// Copyright CraftBench. All Rights Reserved.
//
// AChaserNpcCharacter reference implementation for task t2-npc-follows-player:
// the enemy detects and follows the player by running a chasing AI controller.
// The controller re-reads the player character every half second and
// path-follows to it over the level's navmesh (see ChaserAiController.cpp).

#include "ChaserNpcCharacter.h"

#include "ChaserAiController.h"

AChaserNpcCharacter::AChaserNpcCharacter()
{
	Tags.Add(FName("ChaserNpc"));

	// The chasing brain: auto-possess the placed instance with the AI
	// controller so the chase starts as soon as play begins.
	AIControllerClass = AChaserAiController::StaticClass();
	AutoPossessAI = EAutoPossessAI::PlacedInWorldOrSpawned;
}
