// Copyright CraftBench. All Rights Reserved.
//
// GAMING VARIANT "climb-anywhere" — see header. No ladder-volume gate at all:
// any climb request flies the character upward wherever it stands.

#include "LadderCharacter.h"

#include "GameFramework/CharacterMovementComponent.h"

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

void ALadderCharacter::Tick(float DeltaSeconds)
{
	Super::Tick(DeltaSeconds);

	UCharacterMovementComponent* Movement = GetCharacterMovement();
	if (Movement == nullptr)
	{
		return;
	}
	if (bClimbRequested && !bClimbingMode)
	{
		bClimbingMode = true;
		Movement->StopMovementImmediately();
		Movement->SetMovementMode(MOVE_Flying);
	}
	else if (!bClimbRequested && bClimbingMode)
	{
		bClimbingMode = false;
		Movement->SetMovementMode(MOVE_Falling);
	}
	if (bClimbingMode)
	{
		Movement->Velocity = FVector(0.0f, 0.0f, ClimbSpeed);
	}
}
