// Copyright CraftBench. All Rights Reserved.
//
// AFireGameMode implementation for task t2-weapon-fire-animation-on-trigger.

#include "FireGameMode.h"

#include "GameFramework/PlayerController.h"
#include "UObject/ConstructorHelpers.h"

#include "FireCharacter.h"

AFireGameMode::AFireGameMode()
{
	DefaultPawnClass = AFireCharacter::StaticClass();

	// PLAY-LANE FIX 2026-08-17 (brief: play-lane, four maps).
	// Naming a task game mode REPLACES GlobalDefaultGameMode (BP_ThirdPersonGameMode,
	// Config/DefaultEngine.ini:9), which is where a map overriding nothing gets its player
	// controller for free. Setting DefaultPawnClass without PlayerControllerClass left the
	// player on a bare APlayerController, which has no DefaultMappingContexts property at
	// all -- so IMC_Default was never applied and no keypress reached the pawn, however well
	// bound it was. No gate could see this: every fixture drives the pawn through
	// AddMovementInput and never presses a key, so a dead keyboard graded byte-identically.
	static ConstructorHelpers::FClassFinder<APlayerController> ControllerFinder(
		TEXT("/Game/ThirdPerson/Blueprints/BP_ThirdPersonPlayerController"));
	if (ControllerFinder.Succeeded())
	{
		PlayerControllerClass = ControllerFinder.Class;
	}
}
