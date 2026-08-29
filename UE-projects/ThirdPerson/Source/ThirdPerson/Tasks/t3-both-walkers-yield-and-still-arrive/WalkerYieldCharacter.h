// Copyright CraftBench. All Rights Reserved.
//
// AWalkerYieldCharacter - supplied character base for task
// t3-both-walkers-yield-and-still-arrive.

#pragma once

#include "CoreMinimal.h"
#include "AIController.h"
#include "ThirdPersonCharacter.h"
#include "WalkerYieldCharacter.generated.h"

UCLASS()
class THIRDPERSON_API AWalkerYieldAIController : public AAIController
{
	GENERATED_BODY()

public:
	AWalkerYieldAIController();
};

UCLASS(Blueprintable)
class THIRDPERSON_API AWalkerYieldCharacter : public AThirdPersonCharacter
{
	GENERATED_BODY()

public:
	AWalkerYieldCharacter();
};
