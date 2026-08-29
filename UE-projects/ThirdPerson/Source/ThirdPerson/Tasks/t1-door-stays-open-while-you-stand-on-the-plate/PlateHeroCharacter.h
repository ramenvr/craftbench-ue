// Copyright CraftBench. All Rights Reserved.
//
// The character you control in this level. It arrives with a visible, animated
// body and nothing else — no plate logic, no door logic.

#pragma once

#include "CoreMinimal.h"
#include "ThirdPersonCharacter.h"
#include "PlateHeroCharacter.generated.h"

UCLASS()
class THIRDPERSON_API APlateHeroCharacter : public AThirdPersonCharacter
{
	GENERATED_BODY()

public:
	APlateHeroCharacter();
};
