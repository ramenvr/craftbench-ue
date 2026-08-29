// Copyright CraftBench. All Rights Reserved.

#include "MeleePawn.h"

#include "MeleeAbility.h"

AMeleePawn::AMeleePawn()
{
	GrantedAbilities.Add(UMeleeAbility::StaticClass());
}
