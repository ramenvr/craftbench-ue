// Copyright CraftBench. All Rights Reserved.
//
// AHoverPawn — pre-existing actor for task t2-gravity-floating-pawn-movement
// (reference solution: the movement subobject class is overridden in the
// constructor, so every instance of the type is born with gravity-when-idle).

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
