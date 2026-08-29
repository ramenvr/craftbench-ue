// Copyright CraftBench. All Rights Reserved.

#include "Tasks/t3-both-walkers-yield-and-still-arrive/WalkerYieldCharacter.h"

#include "Components/CapsuleComponent.h"
#include "GameFramework/CharacterMovementComponent.h"

AWalkerYieldAIController::AWalkerYieldAIController()
{
}

AWalkerYieldCharacter::AWalkerYieldCharacter()
{
	PrimaryActorTick.bCanEverTick = false;
	Tags.AddUnique(TEXT("WalkerYieldSubject"));
	AIControllerClass = AWalkerYieldAIController::StaticClass();
	AutoPossessAI = EAutoPossessAI::PlacedInWorldOrSpawned;

	GetCapsuleComponent()->SetCollisionProfileName(TEXT("Pawn"));
	GetCharacterMovement()->bOrientRotationToMovement = true;
	GetCharacterMovement()->bRequestedMoveUseAcceleration = false;
	GetCharacterMovement()->MaxWalkSpeed = 300.0f;
	GetCharacterMovement()->SetAvoidanceEnabled(false);
}
