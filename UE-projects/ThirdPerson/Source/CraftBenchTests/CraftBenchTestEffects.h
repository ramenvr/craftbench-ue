// Copyright CraftBench. All Rights Reserved.
//
// VERIFIER-ONLY MODULE — DO NOT EDIT.
// See Source/CraftBenchTests/.AGENT_WRITE_DENY for the no-edit policy.
// Changes here require maintainer review (.github/CODEOWNERS).
//
// CraftBenchTestEffects — runtime-constructed UGameplayEffect factories for L2
// fixtures. V1.1 of the g2 verifier-extensions spec (§5, "the single
// highest-leverage extension").
//
// WHY THIS EXISTS. Every fixture in the tree today moves an attribute with
// ASC->SetNumericAttributeBase(), which NO ability, effect or attribute-set
// hook can intercept: the fixture pokes the number and the submission's feature
// never sees it. These factories let a fixture make the WORLD do something to
// the pawn — a periodic drain, a one-shot hit, a competing modifier — through
// the same GAS path a real game would use, so the submission's resistance,
// clamp, cleanse, immunity or stacking logic is actually exercised.
//
// PROVENANCE. Every construction step mirrors Epic's own shipping automation
// test, <UE_ROOT>/Engine/Plugins/Runtime/GameplayAbilities/Source/
// GameplayAbilities/Private/Tests/GameplayEffectTests.cpp:
//   :78      CONSTRUCT_CLASS  -> NewObject<UGameplayEffect>(GetTransientPackage(), Name)
//   :750-759 AddModifier      -> Modifiers.SetNum(n+1); Info.{ModifierMagnitude,ModifierOp,Attribute}
//   :290-294 periodic DoT     -> DurationPolicy=HasDuration; DurationMagnitude=FScalableFloat(d); Period.Value=p
// (The ledger's §5 cites ":79" and ":292-295"; both are off by one against the
//  5.8 tree on this box. Re-verified 2026-08-08 by grep.)
// Magnitudes go through FGameplayEffectModifierMagnitude(FScalableFloat), whose
// ctor is commented "Constructors for setting value in code (for automation
// tests)" at GameplayEffect.h:288-293.
//
// NO UCLASS ON PURPOSE. UAbilitySystemComponent::ApplyGameplayEffectToSelf
// (AbilitySystemComponent.h:773) takes a UGameplayEffect INSTANCE, not a class,
// so nothing here needs to be a type. A plain namespace also keeps a
// verifier-only UCLASS out of any cook reference graph.
//
// TWO LAWS FOR CALLERS, both learned the hard way (see the .cpp for the engine
// citations that prove them):
//
//  1. GATE ON THE VALUE, NEVER ON "THE EFFECT APPLIED". A submission that
//     grants itself immunity yields zero active effects; a submission that
//     clamps in PreAttributeChange yields one; a submission that resists via a
//     competing modifier yields one with a different magnitude. All three can
//     be correct answers to the same behavior prompt. A gate keyed on the
//     application COUNT blesses exactly one recipe and fails the others.
//
//  2. HOLD THE RETURNED POINTER IN A UPROPERTY. These are transient UObjects
//     with no other referencer until they are applied; a GC pass mid-schedule
//     would collect one out from under a running periodic effect.
//     ACraftBenchPawnFunctionalTest::ApplyEffectToPawn() does this for you.

#pragma once

#include "CoreMinimal.h"

// Brings in FGameplayAttribute (via AttributeSet.h), EGameplayModOp::Type and
// FGameplayTag (via GameplayTagContainer.h) in one include — the same header
// AbilitySystemComponent.h pulls for the identical set.
#include "GameplayEffectTypes.h"

class UGameplayEffect;

namespace CraftBenchTestEffects
{
	/**
	 * A PERIODIC effect on Attribute: PerTick is applied every PeriodSecs for
	 * DurationSecs. Modeled on Epic's Test_PeriodicDamage
	 * (GameplayEffectTests.cpp:290-294).
	 *
	 * @param Attribute     the attribute to move. Must be valid; the pawn need
	 *                      not own it (GAS logs at Log level and skips the
	 *                      modifier if the ASC has no matching attribute set —
	 *                      GameplayEffect.cpp:4146-4150 — so a missing attribute
	 *                      reads as "nothing happened", never as a crash).
	 * @param PerTick       SIGNED delta applied to the BASE value each period.
	 *                      Pass a NEGATIVE number to drain, POSITIVE to restore.
	 *                      The sign is taken verbatim (Epic passes
	 *                      -DamagePerPeriod); the function name says "Drain"
	 *                      only because that is the shape it was built for.
	 * @param PeriodSecs    seconds between executions. Must be > 0 — a
	 *                      zero/negative period is a non-periodic effect and is
	 *                      refused with nullptr rather than silently becoming one.
	 *                      NOTE: bExecutePeriodicEffectOnApplication defaults to
	 *                      true (GameplayEffect.cpp:187), so N seconds of a
	 *                      1 s period yields N+1 executions, not N. Calibrate
	 *                      against a measured control leg, not arithmetic.
	 * @param DurationSecs  > 0 gives EGameplayEffectDurationType::HasDuration;
	 *                      <= 0 gives Infinite (a permanent drain the fixture is
	 *                      then responsible for removing by handle).
	 * @param AssetTag      stamped as an ASSET tag on the effect (see the .cpp:
	 *                      this needs an explicit call, not just AddComponent).
	 *                      An invalid tag stamps nothing and is not an error.
	 *
	 * @return the effect, or nullptr on invalid arguments. NEVER logs at
	 *         Warning — FFunctionalTestBase::bElevateLogWarningsToErrors is true
	 *         (FunctionalTestBase.cpp:24), so one warning inside the test window
	 *         zeroes the WHOLE fixture, not just the leg that emitted it.
	 */
	CRAFTBENCHTESTS_API UGameplayEffect* MakePeriodicAttributeDrain(
		const FGameplayAttribute& Attribute,
		float PerTick,
		float PeriodSecs,
		float DurationSecs,
		const FGameplayTag& AssetTag);

	/**
	 * A one-shot INSTANT change of Delta to Attribute's BASE value.
	 *
	 * An instant effect EXECUTES and is never added to the active container, so
	 * ACraftBenchPawnFunctionalTest::PawnEffectCount() is always 0 for one of
	 * these and the returned handle's IsValid() is false while
	 * WasSuccessfullyApplied() is true (ActiveGameplayEffectHandle.h:40-48).
	 * Read the attribute, not the handle.
	 */
	CRAFTBENCHTESTS_API UGameplayEffect* MakeInstantAttributeDelta(
		const FGameplayAttribute& Attribute,
		float Delta,
		const FGameplayTag& AssetTag);

	/**
	 * An INFINITE, non-periodic modifier: Op/Mag applied to Attribute for as
	 * long as the effect is active.
	 *
	 * This is an AGGREGATOR modifier, so it moves the CURRENT value only and
	 * leaves the BASE value untouched. That is precisely the difference
	 * PawnAttribute() vs PawnAttributeBase() exists to expose — see the V1.4
	 * comment on ACraftBenchPawnFunctionalTest.
	 *
	 * Op names in UE 5.8 are AddBase / MultiplyAdditive / DivideAdditive /
	 * MultiplyCompound / AddFinal / Override; Additive, Multiplicitive and
	 * Division are hidden backwards-compat aliases (GameplayEffectTypes.h:112-149).
	 * Prefer the modern names.
	 */
	CRAFTBENCHTESTS_API UGameplayEffect* MakeInfiniteModifier(
		const FGameplayAttribute& Attribute,
		EGameplayModOp::Type Op,
		float Mag,
		const FGameplayTag& AssetTag);

	/**
	 * True if Effect carries Tag as an ASSET tag.
	 *
	 * Exists so a probe fixture can PROVE the stamp landed rather than assume
	 * it. Reading GetAssetTags() on a runtime-built effect that skipped the
	 * explicit stamp call returns empty (see the .cpp), and every immunity /
	 * EffectTagQuery gate built on top would then silently never match — a
	 * broken gate that passes.
	 */
	CRAFTBENCHTESTS_API bool HasAssetTag(const UGameplayEffect* Effect, const FGameplayTag& Tag);
}
