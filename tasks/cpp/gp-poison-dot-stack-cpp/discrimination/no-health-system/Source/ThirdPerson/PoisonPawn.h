// Copyright CraftBench. All Rights Reserved.
//
// DISCRIMINATION VARIANT no-health-system for task gp-poison-dot-stack-cpp
// (promoted 2026-08-05 from the scratchpad probe that live-validated the
// stage-1 gate). A complete, correct STAGE-2 solve (the reference ability +
// GE + MMC, verbatim) on a pawn that deliberately SKIPS STAGE 1: it derives
// from the ASC-only task base and never builds an attribute set.
// EXPECTED: FAIL at checkpoint 0 by name -- "stage 1 not built: the pawn's
// health attribute system is absent". (The pre-refactor probe presented the
// same state by detaching the then-pre-built set via RemoveSpawnedAttribute;
// post-refactor the bare lineage makes the skip the natural shape.)

#pragma once

#include "CoreMinimal.h"
#include "CraftBenchBareCharacter.h"
#include "PoisonPawn.generated.h"

UCLASS()
class APoisonPawn : public ACraftBenchBareCharacter
{
	GENERATED_BODY()

public:
	APoisonPawn();
};
