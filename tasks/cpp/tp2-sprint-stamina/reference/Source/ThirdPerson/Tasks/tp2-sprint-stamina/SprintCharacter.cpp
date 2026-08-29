// Copyright CraftBench. All Rights Reserved.
//
// ASprintCharacter implementation for task tp2-sprint-stamina (reference
// solution). Sprint sets max ground speed to 1.7x the captured base; stamina
// drains while sprinting (auto-ending at 0), regenerates while not, and a
// request below the floor is ignored without being remembered.

#include "SprintCharacter.h"

#include "GameFramework/CharacterMovementComponent.h"

ASprintCharacter::ASprintCharacter()
{
	PrimaryActorTick.bCanEverTick = true;
	Tags.Add(FName("SprintHero"));
}

void ASprintCharacter::BeginPlay()
{
	Super::BeginPlay();
	if (UCharacterMovementComponent* Movement = GetCharacterMovement())
	{
		BaseMaxWalkSpeed = Movement->MaxWalkSpeed;
	}
}

void ASprintCharacter::DoSprintStart()
{
	if (bSprinting || Stamina < MinSprintStamina)
	{
		return;  // below the floor: ignored, and never remembered
	}
	if (UCharacterMovementComponent* Movement = GetCharacterMovement())
	{
		bSprinting = true;
		Movement->MaxWalkSpeed = BaseMaxWalkSpeed * SprintMultiplier;
	}
}

void ASprintCharacter::DoSprintEnd()
{
	if (!bSprinting)
	{
		return;
	}
	bSprinting = false;
	if (UCharacterMovementComponent* Movement = GetCharacterMovement())
	{
		Movement->MaxWalkSpeed = BaseMaxWalkSpeed;
	}
}

void ASprintCharacter::Tick(float DeltaSeconds)
{
	Super::Tick(DeltaSeconds);
	if (bSprinting)
	{
		Stamina = FMath::Max(0.f, Stamina - DrainPerSecond * DeltaSeconds);
		if (Stamina <= 0.f)
		{
			DoSprintEnd();
		}
	}
	else
	{
		Stamina = FMath::Min(MaxStamina, Stamina + RegenPerSecond * DeltaSeconds);
	}
}
