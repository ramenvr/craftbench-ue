// Copyright CraftBench. All Rights Reserved.
//
// The character you drive in the haul yard. It arrives with a visible, animated
// body, the template's keyboard lane wired up, and the template's ordinary ground
// movement -- and nothing else. No carrying, no speed change, no jump rules.
//
// This is the class the yard places and the player possesses, so this is where the
// work has to land: the yard cannot be edited, and a subclass of a placed actor is
// never instantiated.

#pragma once

#include "CoreMinimal.h"
#include "ThirdPersonCharacter.h"
#include "HaulHeroCharacter.generated.h"

UCLASS()
class THIRDPERSON_API AHaulHeroCharacter : public AThirdPersonCharacter
{
	GENERATED_BODY()

public:
	AHaulHeroCharacter();
};
