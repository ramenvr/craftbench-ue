// Copyright CraftBench. All Rights Reserved.
//
// Gaming variant "no-resume-after-input" — pawn ctor identical to the
// reference.

#include "HoverPawn.h"

#include "GravityFloatingPawnMovement.h"

AHoverPawn::AHoverPawn(const FObjectInitializer& ObjectInitializer)
	: Super(ObjectInitializer.SetDefaultSubobjectClass<UGravityFloatingPawnMovement>(ADefaultPawn::MovementComponentName))
{
	Tags.Add(FName(TEXT("HoverPawn")));
}
