// Copyright CraftBench. All Rights Reserved.
//
// AHoverPawn — pre-existing pawn for task t2-gravity-floating-pawn-movement.
// A concrete spectator-style pawn (spherical collision + floating movement,
// inherited stock) stamped with the "HoverPawn" identity tag. It hovers in
// place and translates under movement input; nothing else is provided. The
// required behavior is specified in the task prompt and is the agent's to
// implement: edit this pawn type in place (or swap its movement component
// class); do not rename the class — a placed instance of it is graded.

#pragma once

#include "CoreMinimal.h"
#include "GameFramework/DefaultPawn.h"
#include "HoverPawn.generated.h"

UCLASS()
class CRAFTBENCHTEMPLATE_API AHoverPawn : public ADefaultPawn
{
	GENERATED_BODY()

public:
	AHoverPawn(const FObjectInitializer& ObjectInitializer);
};
