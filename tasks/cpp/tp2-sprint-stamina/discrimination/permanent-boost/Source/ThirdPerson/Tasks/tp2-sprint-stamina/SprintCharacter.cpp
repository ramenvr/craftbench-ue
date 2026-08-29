// GAMING VARIANT (anti-gaming note #2): permanent 1.7x boost, no stamina.

#include "SprintCharacter.h"

#include "GameFramework/CharacterMovementComponent.h"

ASprintCharacter::ASprintCharacter()
{
	Tags.Add(FName("SprintHero"));
}

void ASprintCharacter::DoSprintStart()
{
	if (UCharacterMovementComponent* Movement = GetCharacterMovement())
	{
		Movement->MaxWalkSpeed *= 1.7f;
	}
}

void ASprintCharacter::DoSprintEnd()
{
	// Nothing ever reverts the boost.
}
