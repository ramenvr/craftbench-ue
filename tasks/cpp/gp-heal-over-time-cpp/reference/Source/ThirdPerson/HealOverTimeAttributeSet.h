// Copyright CraftBench. All Rights Reserved.
//
// REFERENCE SOLUTION for task gp-heal-over-time-cpp (PIN.md section 4, "A
// PASSING solve"). The clamping attribute set.
//
// WHY A SUBCLASS AT ALL. The provided attribute set does NO clamping --
// UCraftBenchAttributeSet (Source/ThirdPerson/CraftBenchAttributeSet.h) is three
// bare FGameplayAttributeData members with the standard accessor macro and
// nothing else, and its .cpp is a single #include. So "Health must never exceed
// MaxHealth" cannot be satisfied by initialization or by sizing the effect: the
// pawn has to introduce the invariant, and PreAttributeChange /
// PreAttributeBaseChange / PostGameplayEffectExecute are UAttributeSet virtuals,
// so the only place to put it is a SUBCLASS of the contract set.
//
// The subclass keeps the contract intact. The ASC resolves an attribute to its
// set with GetAttributeSubobject(Attribute.GetAttributeSetClass()), which matches
// on IsA, so a UCraftBenchAttributeSet subclass registers and answers
// UCraftBenchAttributeSet::GetHealthAttribute() exactly like the base -- the same
// property the gp-health-attribute-ops-cpp `inert-set/` variant leans on.
//
// TWO HOOKS, NOT ONE -- this is the whole point of the task (PIN.md section 4,
// the plausible-WRONG solve):
//
//   PreAttributeChange        guards the CURRENT value. It is the recipe every
//                             GAS tutorial shows, and ON ITS OWN IT IS NOT
//                             ENOUGH: a PERIODIC effect executes into the BASE
//                             value, so a current-only clamp reads back a clean
//                             100 while the stored base has accumulated past it,
//                             and the next N points of damage do nothing at all.
//
//   PostGameplayEffectExecute runs after an instant/periodic execution has
//                             already moved the base, and writes the clamped
//                             value BACK through the base setter. This is the
//                             hook that makes the stored value honest.
//
// A third route exists and is equally correct: PreAttributeBaseChange, which
// intercepts the base write before it lands (it is what
// FActiveGameplayEffectsContainer::SetAttributeBaseValue calls, by reference).
// PIN.md section 4's passing sketch names the PreAttributeChange +
// PostGameplayEffectExecute pair, so that pair is what this reference ships; the
// choice between "clamp before the base write" and "clamp after it" is an
// implementation detail the prompt deliberately does not dictate.

#pragma once

#include "CoreMinimal.h"
#include "CraftBenchAttributeSet.h"
#include "HealOverTimeAttributeSet.generated.h"

struct FGameplayEffectModCallbackData;

UCLASS()
class UHealOverTimeAttributeSet : public UCraftBenchAttributeSet
{
	GENERATED_BODY()

public:
	/** Clamps the CURRENT value of Health to [0, MaxHealth]. Necessary, not
	 *  sufficient -- see the file header. */
	virtual void PreAttributeChange(const FGameplayAttribute& Attribute, float& NewValue) override;

	/** Clamps the BASE value of Health to [0, MaxHealth] after an instant or
	 *  periodic execution has already written it. This is the half a
	 *  PreAttributeChange-only solve is missing. */
	virtual void PostGameplayEffectExecute(const FGameplayEffectModCallbackData& Data) override;

private:
	/** Shared body of both hooks so the two clamps can never drift apart. */
	float ClampHealth(float Value) const;
};
