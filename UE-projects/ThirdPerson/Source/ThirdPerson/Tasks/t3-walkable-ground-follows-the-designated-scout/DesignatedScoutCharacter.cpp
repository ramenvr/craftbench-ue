// Copyright CraftBench. All Rights Reserved.

#include "Tasks/t3-walkable-ground-follows-the-designated-scout/DesignatedScoutCharacter.h"

#include "AIController.h"
#include "GameFramework/CharacterMovementComponent.h"

ADesignatedScoutCharacter::ADesignatedScoutCharacter(
	const FObjectInitializer& ObjectInitializer)
	: Super(ObjectInitializer)
{
	PrimaryActorTick.bCanEverTick = false;
	Tags.AddUnique(TEXT("DesignatedScout"));
	AutoPossessAI = EAutoPossessAI::PlacedInWorldOrSpawned;
	AIControllerClass = AAIController::StaticClass();

	if (UCharacterMovementComponent* Movement = GetCharacterMovement())
	{
		Movement->MaxWalkSpeed = 320.0f;
		Movement->bOrientRotationToMovement = true;
	}
}
