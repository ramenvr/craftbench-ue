// Copyright CraftBench. All Rights Reserved.
//
// The character you drive around this level. It arrives with a visible, animated
// body and working controls, and nothing else.

#pragma once

#include "CoreMinimal.h"
#include "ThirdPersonCharacter.h"
#include "BenchCharacter.generated.h"

UCLASS()
class THIRDPERSON_API ABenchCharacter : public AThirdPersonCharacter
{
	GENERATED_BODY()

public:
	ABenchCharacter();
};
