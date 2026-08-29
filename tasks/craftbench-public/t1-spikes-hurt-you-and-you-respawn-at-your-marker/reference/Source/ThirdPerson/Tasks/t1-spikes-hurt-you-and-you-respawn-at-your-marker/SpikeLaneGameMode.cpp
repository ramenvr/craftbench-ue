// Copyright CraftBench. All Rights Reserved.

#include "SpikeLaneGameMode.h"

#include "SpikeLaneCharacter.h"
#include "UObject/ConstructorHelpers.h"

ASpikeLaneGameMode::ASpikeLaneGameMode()
{
	DefaultPawnClass = ASpikeLaneCharacter::StaticClass();

	// The keyboard lane lives on the template's Blueprint controller: it carries
	// IMC_Default in DefaultMappingContexts, and the base AThirdPersonPlayerController
	// is abstract with that array empty. Naming a game mode at all replaces
	// GlobalDefaultGameMode (BP_ThirdPersonGameMode), which is where a level that
	// overrides nothing gets this for free -- so a level with a game mode of its own
	// has to re-state it, or pressing Play leaves nothing anyone can drive.
	static ConstructorHelpers::FClassFinder<APlayerController> ControllerFinder(
		TEXT("/Game/ThirdPerson/Blueprints/BP_ThirdPersonPlayerController"));
	if (ControllerFinder.Succeeded())
	{
		PlayerControllerClass = ControllerFinder.Class;
	}
}
