// Copyright CraftBench. All Rights Reserved.
//
// DISCRIMINATION VARIANT `inert-set/` for task gp-health-attribute-ops-cpp --
// the one file this variant ADDS. Anti-gaming note AG-2 (PIN.md section 3):
// "register an attribute set that reads its own shadow value and ignores
// writes."
//
// A SUBCLASS of the contract set, not a replacement for it: the fixture reads
// UCraftBenchAttributeSet::GetHealthAttribute(), and the ASC resolves an
// attribute to its set via GetAttributeSubobject(Attribute.GetAttributeSetClass())
// which matches on IsA -- so a subclass registers, resolves and satisfies HO-2
// exactly like the real thing. That is what makes this the AG-2 shape rather
// than a second `no-health-system/`: the health system is PRESENT and reads
// 100; it just does not accept writes.
//
// EXPECTED: FAIL at HO-4, checkpoint 0, on the named substring
//   "stage 1 incomplete: health attribute is inert, write-then-read failed (wrote"
// UNVALIDATED / NOT YET RUN -- see discrimination/MATRIX.md.

#pragma once

#include "CoreMinimal.h"
#include "CraftBenchAttributeSet.h"
#include "InertHealthAttributeSet.generated.h"

UCLASS()
class UInertHealthAttributeSet : public UCraftBenchAttributeSet
{
	GENERATED_BODY()

public:
	/** Ignore every write to the BASE value of Health.
	 *
	 *  UE 5.8 seam, verified in the engine source rather than assumed:
	 *  FActiveGameplayEffectsContainer::SetAttributeBaseValue calls
	 *  Set->PreAttributeBaseChange(Attribute, NewBaseValue) BY REFERENCE before
	 *  it writes (GameplayEffect.cpp:4001), so forcing NewValue back to the
	 *  shadow leaves the base where it was. This is the path the fixture's own
	 *  write probe takes (ASC->SetNumericAttributeBase). */
	virtual void PreAttributeBaseChange(const FGameplayAttribute& Attribute, float& NewValue) const override;

	/** Ignore every write to the CURRENT value of Health.
	 *
	 *  Same seam one layer down: FGameplayAttribute::SetNumericValueChecked
	 *  calls Dest->PreAttributeChange(*this, NewValue) by reference before
	 *  assigning (AttributeSet.cpp:82,95). The fixture READS the current value
	 *  (PawnAttribute, the V1.4 law), so this override is the one that makes the
	 *  read-back inert; the base override above is what makes the set inert in
	 *  the honest, fully-shadowed sense AG-2 describes. Either alone would trip
	 *  HO-4; both are here so the variant is the stated shape and not an
	 *  accident of which channel the fixture happens to read. */
	virtual void PreAttributeChange(const FGameplayAttribute& Attribute, float& NewValue) override;

private:
	/** The shadow value this set keeps reading no matter what is written to it.
	 *  Equal to the reference's InitHealth(100), so HO-3 (Health reads 100
	 *  BEFORE any fixture write) still PASSES and the variant reaches HO-4 --
	 *  the whole point of the write probe being at 37 and not at 100 (an
	 *  inert set that shadows 100 would pass a 100-write vacuously). */
	static constexpr float InertShadowHealth = 100.0f;
};
