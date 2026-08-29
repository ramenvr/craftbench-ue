// Copyright CraftBench. All Rights Reserved.
//
// AHoverPawn implementation for task t2-gravity-floating-pawn-movement.

#include "HoverPawn.h"

AHoverPawn::AHoverPawn(const FObjectInitializer& ObjectInitializer)
	: Super(ObjectInitializer)
{
	Tags.Add(FName(TEXT("HoverPawn")));
}
