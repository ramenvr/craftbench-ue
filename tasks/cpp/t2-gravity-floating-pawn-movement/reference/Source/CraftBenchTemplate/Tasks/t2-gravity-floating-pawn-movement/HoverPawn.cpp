// Copyright CraftBench. All Rights Reserved.
//
// AHoverPawn implementation (reference solution). The subobject-class
// override swaps the pawn's inherited floating movement for the
// gravity-aware subclass at construction time — the type itself carries the
// behavior; instances need no setup.

#include "HoverPawn.h"

#include "GravityFloatingPawnMovement.h"

AHoverPawn::AHoverPawn(const FObjectInitializer& ObjectInitializer)
	: Super(ObjectInitializer.SetDefaultSubobjectClass<UGravityFloatingPawnMovement>(ADefaultPawn::MovementComponentName))
{
	Tags.Add(FName(TEXT("HoverPawn")));
}
