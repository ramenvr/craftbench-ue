// Copyright CraftBench. All Rights Reserved.
//
// GAMING VARIANT "never-releases" — see header. Volume-gated ENTRY only: once
// climbing, only DoClimbEnd pauses it, and leaving the ladder's reach is
// ignored — the climb continues forever past the top.

#include "LadderCharacter.h"

#include "GameFramework/CharacterMovementComponent.h"

namespace
{
	static const FName LadderVolumeTag(TEXT("LadderVolume"));
}

ALadderCharacter::ALadderCharacter()
{
	Tags.Add(FName("ClimbHero"));
	PrimaryActorTick.bCanEverTick = true;
}

void ALadderCharacter::DoClimbStart()
{
	bClimbRequested = true;
}

void ALadderCharacter::DoClimbEnd()
{
	bClimbRequested = false;
}

bool ALadderCharacter::IsAtLadder() const
{
	TArray<AActor*> Overlapping;
	GetOverlappingActors(Overlapping);
	for (const AActor* Actor : Overlapping)
	{
		if (Actor != nullptr && Actor->ActorHasTag(LadderVolumeTag))
		{
			return true;
		}
	}
	return false;
}

void ALadderCharacter::Tick(float DeltaSeconds)
{
	Super::Tick(DeltaSeconds);

	UCharacterMovementComponent* Movement = GetCharacterMovement();
	if (Movement == nullptr)
	{
		return;
	}
	// Entry is gated on the ladder; exit NEVER happens on leaving its reach.
	if (!bClimbingMode && bClimbRequested && IsAtLadder())
	{
		bClimbingMode = true;
		Movement->StopMovementImmediately();
		Movement->SetMovementMode(MOVE_Flying);
	}
	if (bClimbingMode)
	{
		Movement->Velocity = bClimbRequested ? FVector(0.0f, 0.0f, ClimbSpeed) : FVector::ZeroVector;
	}
}
