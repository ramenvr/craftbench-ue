// Copyright CraftBench. All Rights Reserved.

#include "RaceGameMode.h"

#include "RaceCollector.h"
#include "UObject/ConstructorHelpers.h"

ARaceGameMode::ARaceGameMode()
{
	DefaultPawnClass = ARaceCollector::StaticClass();

	// Naming a game mode at all replaces GlobalDefaultGameMode, and both halves of
	// Enhanced Input live on the Blueprints it would have supplied -- so a level with
	// a game mode of its own has to re-state the controller, or pressing Play leaves
	// nothing anyone can drive.
	static ConstructorHelpers::FClassFinder<APlayerController> ControllerFinder(
		TEXT("/Game/ThirdPerson/Blueprints/BP_ThirdPersonPlayerController"));
	if (ControllerFinder.Succeeded())
	{
		PlayerControllerClass = ControllerFinder.Class;
	}
}
