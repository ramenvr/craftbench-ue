// Copyright CraftBench. All Rights Reserved.
//
// DISCRIMINATION VARIANT (no-mesh) for task gp-glide-stamina-cpp -- the
// reference pawn MINUS the constructor mesh assignment (the ONE delta;
// anti-gaming note 6, "Invisible deliverable"). Behaviorally this is a fully
// correct solve: the ability is granted, activates, slows the descent, drains
// Power and stops at zero -- it is invisible, and nothing else. Promotion of
// the 2026-08-06 "meshless probe" that MATRIX.md previously recorded as a
// scratchpad-only run.
// Expected verdict: FAIL, by name, at the checkpoint-0 visibility gate --
// "the character is not visibly represented: no mesh component with an
// assigned mesh on the graded pawn". See GlidePawn.cpp.

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
