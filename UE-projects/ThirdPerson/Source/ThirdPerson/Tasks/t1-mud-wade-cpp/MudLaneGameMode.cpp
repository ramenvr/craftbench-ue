// Copyright CraftBench. All Rights Reserved.

#include "MudLaneGameMode.h"

#include "MudHeroCharacter.h"
#include "UObject/ConstructorHelpers.h"

AMudLaneGameMode::AMudLaneGameMode()
{
	DefaultPawnClass = AMudHeroCharacter::StaticClass();

	// Naming a game mode replaces GlobalDefaultGameMode, and both halves of Enhanced
	// Input live on the Blueprints it would have supplied.
	static ConstructorHelpers::FClassFinder<APlayerController> ControllerFinder(
		TEXT("/Game/ThirdPerson/Blueprints/BP_ThirdPersonPlayerController"));
	if (ControllerFinder.Succeeded())
	{
		PlayerControllerClass = ControllerFinder.Class;
	}
}
