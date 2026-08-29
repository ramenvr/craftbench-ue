// Copyright CraftBench. All Rights Reserved.
//
// DISCRIMINATION VARIANT `inert-set/` for task gp-health-attribute-ops-cpp.
// Anti-gaming note AG-2 (PIN.md section 3).
//
// THE ONE DELTA, and it is one type name: the stage-1 subobject is constructed
// as UInertHealthAttributeSet (a subclass of the contract set whose writes are
// ignored -- see InertHealthAttributeSet.h) instead of UCraftBenchAttributeSet.
// The member, the subobject NAME, InitHealth(100), both granted abilities, the
// mesh and both effects are the reference verbatim.
//
// This is the ONLY variant in the package that ADDS a file, and it is
// unavoidable: "the writes are ignored" is a property of the attribute-set TYPE
// (PreAttributeBaseChange / PreAttributeChange are UAttributeSet virtuals), so
// there is no edit to the reference's existing files that can express it. The
// added pair changes exactly one axis and nothing else -- MATRIX.md records it.
//
// EXPECTED: FAIL at HO-4, checkpoint 0, on the named substring
//   "stage 1 incomplete: health attribute is inert, write-then-read failed (wrote"
// UNVALIDATED / NOT YET RUN.

#include "HealthOpsPawn.h"

#include "DamageAbility.h"
#include "HealAbility.h"
#include "InertHealthAttributeSet.h"
#include "Components/SkeletalMeshComponent.h"
#include "Engine/SkeletalMesh.h"
#include "UObject/ConstructorHelpers.h"

AHealthOpsPawn::AHealthOpsPawn()
{
	// STAGE 1 -- present and initialized, so HO-2 and HO-3 both PASS: the ASC
	// really does carry a set exposing Health (IsA the contract class), and it
	// really does read 100 before any fixture write. The delta is the TYPE: this
	// set shadows Health at 100 and drops every write on the floor, so the
	// fixture's write probe (37, deliberately != 100) reads back 100 and HO-4
	// fires by name. The member stays TObjectPtr<UCraftBenchAttributeSet> -- the
	// upcast is what keeps this a one-line delta.
	HealthAttributes = CreateDefaultSubobject<UInertHealthAttributeSet>(TEXT("HealthAttributes"));
	HealthAttributes->InitHealth(100.0f);
	HealthAttributes->InitMaxHealth(100.0f);

	// STAGE 2 -- unchanged from the reference.
	GrantedAbilities.Add(UDamageAbility::StaticClass());
	GrantedAbilities.Add(UHealAbility::StaticClass());

	// Visible-character requirement (HO-5) -- unchanged from the reference.
	static ConstructorHelpers::FObjectFinder<USkeletalMesh> BodyFinder(
		TEXT("/Game/Characters/Mannequins/Meshes/SKM_Manny_Simple"));
	if (BodyFinder.Succeeded() && GetMesh() != nullptr)
	{
		GetMesh()->SetSkeletalMesh(BodyFinder.Object);
		GetMesh()->SetRelativeLocationAndRotation(
			FVector(0.0, 0.0, -90.0), FRotator(0.0, -90.0, 0.0));
	}
}
