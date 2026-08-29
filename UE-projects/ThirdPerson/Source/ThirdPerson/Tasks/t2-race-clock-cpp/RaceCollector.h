// Copyright CraftBench. All Rights Reserved.
//
// The character you drive around the coin arena. Visible, animated, drivable, and
// carrying no task behaviour.

#pragma once

#include "CoreMinimal.h"
#include "ThirdPersonCharacter.h"
#include "RaceCollector.generated.h"

UCLASS()
class THIRDPERSON_API ARaceCollector : public AThirdPersonCharacter
{
	GENERATED_BODY()

public:
	ARaceCollector();
};
