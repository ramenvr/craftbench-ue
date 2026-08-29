// Copyright CraftBench. All Rights Reserved.
//
// DISCRIMINATION VARIANT `no-mesh/` for task gp-health-attribute-ops-cpp.
// Anti-gaming note AG-5 (PIN.md section 3): "a meshless pawn: conforming but
// invisible to a human reviewing the film strip" (measured 2026-08-04: 9/9
// matrix reps shipped meshless pawns).
//
// THE ONE DELTA, confined to this file: the constructor's mesh-assignment block
// is deleted. Stage 1 and stage 2 are the reference verbatim, so this variant is
// a behaviorally PERFECT solve whose only defect is that nobody can see it --
// which is what makes it the only leg that proves HO-5 discriminates on the
// visibility axis alone.
//
// EXPECTED: FAIL at HO-5, checkpoint 0, on the named substring
//   "the character is not visibly represented: no mesh component with an
//    assigned mesh on the graded pawn"
// UNVALIDATED / NOT YET RUN -- see discrimination/MATRIX.md.

#include "HealthOpsPawn.h"

#include "DamageAbility.h"
#include "HealAbility.h"
#include "CraftBenchAttributeSet.h"

AHealthOpsPawn::AHealthOpsPawn()
{
	// STAGE 1 -- the reference verbatim (HO-1 through HO-4 all pass).
	HealthAttributes = CreateDefaultSubobject<UCraftBenchAttributeSet>(TEXT("HealthAttributes"));
	HealthAttributes->InitHealth(100.0f);
	HealthAttributes->InitMaxHealth(100.0f);

	// STAGE 2 -- the reference verbatim (HO-6 through HO-11 would all pass).
	GrantedAbilities.Add(UDamageAbility::StaticClass());
	GrantedAbilities.Add(UHealAbility::StaticClass());

	// THE DELETED DELTA. The reference assigns the template mannequin here:
	//
	//   static ConstructorHelpers::FObjectFinder<USkeletalMesh> BodyFinder(
	//       TEXT("/Game/Characters/Mannequins/Meshes/SKM_Manny_Simple"));
	//   if (BodyFinder.Succeeded() && GetMesh() != nullptr) { ... }
	//
	// This variant does not. The inherited ACharacter still owns a
	// USkeletalMeshComponent, but with no skeletal mesh ASSIGNED -- which is the
	// exact state HO-5 tests for (it walks every UMeshComponent and requires one
	// with a non-null asset, not merely the presence of a component). The
	// SkeletalMeshComponent / SkeletalMesh / ConstructorHelpers includes go with
	// the block: nothing else in this file needs them.
}
