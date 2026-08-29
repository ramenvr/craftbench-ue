// Copyright CraftBench. All Rights Reserved.
//
// Gaming variant "sinks-while-driven" — pawn header identical to the
// reference (the defect is in the movement subclass).

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
