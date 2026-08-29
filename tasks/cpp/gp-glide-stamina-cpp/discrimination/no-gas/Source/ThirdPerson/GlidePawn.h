// Copyright CraftBench. All Rights Reserved.
//
// DISCRIMINATION VARIANT (no-gas) for task gp-glide-stamina-cpp -- the reference
// pawn with the glide ability NOT granted: the slow descent is faked with a
// permanent CharacterMovement GravityScale reduction instead of an activated,
// resource-gated ability (the ONE delta; anti-gaming note 1, "No GAS (slow the
// fall without an ability)"). The mannequin mesh is kept so the checkpoint-0
// visibility gate still passes and the FAIL lands on the intended axis.
// Expected verdict: FAIL, by name, at gate (1) -- "no activatable ability
// tagged Ability.Glide on the pawn (GAS not implemented). granted=0".
// See GlidePawn.cpp.

#pragma once

#include "CoreMinimal.h"
#include "CraftBenchCharacter.h"
#include "GlidePawn.generated.h"

UCLASS()
class AGlidePawn : public ACraftBenchCharacter
{
	GENERATED_BODY()

public:
	AGlidePawn();

protected:
	virtual void BeginPlay() override;
};
