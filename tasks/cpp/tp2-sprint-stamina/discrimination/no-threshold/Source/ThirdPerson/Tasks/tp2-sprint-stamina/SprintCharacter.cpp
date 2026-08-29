// GAMING VARIANT (anti-gaming note #3): no 30-stamina floor on DoSprintStart.

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
	if (bSprinting || Stamina <= 0.f)  // MISSING: the >= 30 floor
	{
		return;
	}
	if (UCharacterMovementComponent* Movement = GetCharacterMovement())
	{
		bSprinting = true;
		Movement->MaxWalkSpeed = BaseMaxWalkSpeed * 1.7f;
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
		Stamina = FMath::Max(0.f, Stamina - 25.f * DeltaSeconds);
		if (Stamina <= 0.f)
		{
			DoSprintEnd();
		}
	}
	else
	{
		Stamina = FMath::Min(100.f, Stamina + 20.f * DeltaSeconds);
	}
}
