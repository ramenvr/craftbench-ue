// Copyright CraftBench. All Rights Reserved.
//
// ALadderCharacter reference implementation for task t2-ladder-climb-volume.

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
	// A request made away from the ladder does nothing AND is not retained:
	// only a request made at the ladder arms the climb.
	if (IsAtLadder())
	{
		bClimbRequested = true;
	}
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
	const bool bAtLadder = IsAtLadder();

	if (bClimbingMode && !bAtLadder)
	{
		// Leaving the ladder's reach ends the climb AND the request — normal
		// movement resumes; a fresh request is needed to climb again.
		bClimbingMode = false;
		bClimbRequested = false;
		Movement->SetMovementMode(MOVE_Falling);
		return;
	}
	if (!bClimbingMode && bClimbRequested && bAtLadder)
	{
		bClimbingMode = true;
		Movement->StopMovementImmediately();
		Movement->SetMovementMode(MOVE_Flying);
	}
	if (bClimbingMode)
	{
		// Steady ascent while the request is live; hold in place once ended.
		Movement->Velocity = bClimbRequested ? FVector(0.0f, 0.0f, ClimbSpeed) : FVector::ZeroVector;
	}
}
