// Copyright CraftBench. All Rights Reserved.
//
// DISCRIMINATION VARIANT `no-health-system/` for task gp-health-attribute-ops-cpp.
// Anti-gaming note AG-1 (PIN.md section 3), second half: a complete, correct
// STAGE 2 delivered on a pawn that never built stage 1.
//
// THE ONE DELTA: the stage-1 attribute-set subobject is never constructed. The
// pawn still parents the task base ACraftBenchBareCharacter (so HO-1 passes),
// still grants both tagged abilities, still wears the mannequin -- it simply
// owns an ability system with NO health resource, which is exactly the state
// ACraftBenchBareCharacter ships in (CraftBenchBareCharacter.cpp suppresses the
// "AttributeSet" subobject for the whole lineage).
//
// EXPECTED: FAIL at HO-2, checkpoint 0, on the named substring
//   "stage 1 not built: the pawn's health attribute system is absent"
// UNVALIDATED / NOT YET RUN -- see discrimination/MATRIX.md.
//
// Shape lifted from the already-committed
// tasks/cpp/gp-poison-dot-stack-cpp/discrimination/no-health-system/, which is
// the same delta against the same stage-1 ladder (PIN.md constraint C1).

#pragma once

#include "CoreMinimal.h"
#include "CraftBenchBareCharacter.h"
#include "HealthOpsPawn.generated.h"

UCLASS()
class AHealthOpsPawn : public ACraftBenchBareCharacter
{
	GENERATED_BODY()

public:
	AHealthOpsPawn();

	// THE DELETED DELTA (the reference has it, this variant does not):
	//
	//   UPROPERTY()
	//   TObjectPtr<UCraftBenchAttributeSet> HealthAttributes;
	//
	// With no attribute set on the ASC, PawnHasAttribute(Health) is false, every
	// read returns 0.0 and every SetNumericAttributeBase silently no-ops. HO-2
	// exists precisely so that state fails BY NAME at checkpoint 0 instead of
	// surfacing later as "the damage operation did not lower Health" (HO-7),
	// which would be a misattributed diagnosis of the same defect.
};
