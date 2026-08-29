// Copyright CraftBench. All Rights Reserved.
//
// VERIFIER-ONLY MODULE — DO NOT EDIT.

#include "CraftBenchTestEffects.h"

#include "GameplayEffect.h"
#include "GameplayEffectComponents/AssetTagsGameplayEffectComponent.h"
#include "ScalableFloat.h"
#include "UObject/Package.h"
#include "UObject/UObjectGlobals.h"

namespace
{
	/**
	 * One modifier, appended. Verbatim shape of Epic's private test helper
	 * GameplayEffectsTestSuite::AddModifier
	 * (GameplayAbilities/Private/Tests/GameplayEffectTests.cpp:750-759) — the
	 * SetNum-then-reference form is theirs; it matters because
	 * FGameplayModifierInfo is a USTRUCT with non-trivial members and the
	 * reference must be taken AFTER the array grows.
	 *
	 * We pass an FGameplayAttribute where Epic passes an FProperty* and calls
	 * Attribute.SetUProperty() — the substrate's attributes come from
	 * GAMEPLAYATTRIBUTE_PROPERTY_GETTER accessors that already hand back a fully
	 * built FGameplayAttribute (UCraftBenchAttributeSet::GetHealthAttribute()),
	 * so plain assignment is the same end state with one less reflection hop.
	 */
	void AddModifier(UGameplayEffect* Effect, const FGameplayAttribute& Attribute,
		EGameplayModOp::Type Op, float Magnitude)
	{
		const int32 Idx = Effect->Modifiers.Num();
		Effect->Modifiers.SetNum(Idx + 1);
		FGameplayModifierInfo& Info = Effect->Modifiers[Idx];
		// FGameplayEffectModifierMagnitude(const FScalableFloat&) — the ctor Epic
		// comments "for automation tests" (GameplayEffect.h:288-293).
		Info.ModifierMagnitude = FGameplayEffectModifierMagnitude(FScalableFloat(Magnitude));
		Info.ModifierOp = Op;
		Info.Attribute = Attribute;
	}

	/**
	 * Stamp an ASSET tag onto a runtime-built effect.
	 *
	 * ===================== THE CORRECTION THAT MATTERS =====================
	 * AddComponent<UAssetTagsGameplayEffectComponent>() ALONE STAMPS NOTHING.
	 *
	 * Verified in the 5.8 tree on disk:
	 *   - UGameplayEffect::CachedAssetTags (GameplayEffect.h:2455) is the only
	 *     thing GetAssetTags() returns, and the ONLY writer of it anywhere is
	 *     UAssetTagsGameplayEffectComponent::ApplyAssetTagChanges()
	 *     (Private/GameplayEffectComponents/AssetTagsGameplayEffectComponent.cpp:83-88,
	 *     `InheritableAssetTags.ApplyTo(Owner->CachedAssetTags)`).
	 *   - ApplyAssetTagChanges() is PRIVATE and has exactly two callers:
	 *     SetAndApplyAssetTagChanges() (:72-81) and OnGameplayEffectChanged()
	 *     (:40-57).
	 *   - The component's OnGameplayEffectChanged() is only reached from
	 *     UGameplayEffect::OnGameplayEffectChanged() (Private/GameplayEffect.cpp:391,
	 *     which forwards to each GEComponent at :411), and THAT is called from
	 *     exactly three sites: PostLoad (:379), PostCDOCompiled (:513, WITH_EDITOR)
	 *     and the component's own PostEditChangeProperty. A NewObject'd effect
	 *     runs NONE of them.
	 *   - The component's PostInitProperties (:11-38) does call
	 *     UpdateInheritedTagProperties, but never ApplyAssetTagChanges.
	 *
	 * So without the explicit SetAndApplyAssetTagChanges() call below,
	 * Effect->GetAssetTags() is EMPTY forever. Nothing errors, nothing warns:
	 * every FGameplayEffectQuery::EffectTagQuery silently misses, every
	 * immunity/blocked-by-tag gate silently never fires, and an immunity
	 * discrimination variant PASSes when it must FAIL. A broken gate that looks
	 * green is the worst defect class this repo has.
	 * ======================================================================
	 *
	 * FindOrAddComponent (not AddComponent) so a second stamp on the same effect
	 * accumulates instead of creating a second component whose ApplyTo would
	 * fight the first (GameplayEffect.h:2509, inline template body; AddComponent
	 * at :2201 "does not check for duplicates and is guaranteed to return a new
	 * instance"). We seed from GetConfiguredAssetTagChanges() for the same reason.
	 */
	void StampAssetTag(UGameplayEffect* Effect, const FGameplayTag& AssetTag)
	{
		if (!AssetTag.IsValid())
		{
			return; // deliberately not an error: an untagged verifier effect is legal
		}

		UAssetTagsGameplayEffectComponent& Component =
			Effect->FindOrAddComponent<UAssetTagsGameplayEffectComponent>();

		FInheritedTagContainer TagChanges = Component.GetConfiguredAssetTagChanges();
		TagChanges.AddTag(AssetTag); // GameplayEffect.cpp:6426-6431
		Component.SetAndApplyAssetTagChanges(TagChanges);
	}

	/**
	 * NewObject'd effect in the transient package, with a UNIQUE name.
	 *
	 * Epic's CONSTRUCT_CLASS macro (GameplayEffectTests.cpp:78) uses a fixed
	 * FName because each of their suites constructs each effect once. A CraftBench
	 * fixture builds effects across a multi-leg checkpoint schedule, and a second
	 * NewObject with a name already live in the same Outer does NOT quietly make a
	 * second object — it takes the rename/replace path. MakeUniqueObjectName
	 * (UObjectGlobals.h:1061) removes the whole question while keeping the log
	 * name readable ("CraftBenchVerifierPeriodic_3" beats "GameplayEffect_7").
	 *
	 * RF_Transient is explicit rather than implied by the transient package: it
	 * is the property that documents the intent, and the object is never saved.
	 */
	UGameplayEffect* NewVerifierEffect(const TCHAR* BaseName)
	{
		UPackage* Outer = GetTransientPackage();
		const FName UniqueName =
			MakeUniqueObjectName(Outer, UGameplayEffect::StaticClass(), FName(BaseName));
		return NewObject<UGameplayEffect>(Outer, UniqueName, RF_Transient);
	}
}

UGameplayEffect* CraftBenchTestEffects::MakePeriodicAttributeDrain(
	const FGameplayAttribute& Attribute,
	float PerTick,
	float PeriodSecs,
	float DurationSecs,
	const FGameplayTag& AssetTag)
{
	// Refuse rather than silently degrade: a non-positive period would produce a
	// NON-periodic effect (Period 0 == no period), which is a completely
	// different observable and would be measured as "the drain never ticked".
	if (!Attribute.IsValid() || !(PeriodSecs > 0.0f))
	{
		return nullptr;
	}

	UGameplayEffect* Effect = NewVerifierEffect(TEXT("CraftBenchVerifierPeriodic"));

	// AddBase (== the legacy "Additive"): a periodic execution runs as an instant
	// mod, so this moves the BASE value each period, exactly like Epic's
	// Test_PeriodicDamage.
	AddModifier(Effect, Attribute, EGameplayModOp::AddBase, PerTick);

	if (DurationSecs > 0.0f)
	{
		Effect->DurationPolicy = EGameplayEffectDurationType::HasDuration;
		Effect->DurationMagnitude = FGameplayEffectModifierMagnitude(FScalableFloat(DurationSecs));
	}
	else
	{
		// Infinite: the caller removes it by handle. Documented in the header so
		// nobody reads a <= 0 duration as "instant".
		Effect->DurationPolicy = EGameplayEffectDurationType::Infinite;
	}

	// GameplayEffectTests.cpp:294 sets Period.Value directly (FScalableFloat's
	// raw value; ScalableFloat.h:38). No curve, so Value IS the period.
	Effect->Period.Value = PeriodSecs;

	StampAssetTag(Effect, AssetTag);
	return Effect;
}

UGameplayEffect* CraftBenchTestEffects::MakeInstantAttributeDelta(
	const FGameplayAttribute& Attribute,
	float Delta,
	const FGameplayTag& AssetTag)
{
	if (!Attribute.IsValid())
	{
		return nullptr;
	}

	UGameplayEffect* Effect = NewVerifierEffect(TEXT("CraftBenchVerifierInstant"));

	// Instant is already the UGameplayEffect ctor default (GameplayEffect.cpp:186);
	// set it anyway so this file states its own contract and survives an engine
	// default change.
	Effect->DurationPolicy = EGameplayEffectDurationType::Instant;
	AddModifier(Effect, Attribute, EGameplayModOp::AddBase, Delta);

	StampAssetTag(Effect, AssetTag);
	return Effect;
}

UGameplayEffect* CraftBenchTestEffects::MakeInfiniteModifier(
	const FGameplayAttribute& Attribute,
	EGameplayModOp::Type Op,
	float Mag,
	const FGameplayTag& AssetTag)
{
	if (!Attribute.IsValid())
	{
		return nullptr;
	}

	UGameplayEffect* Effect = NewVerifierEffect(TEXT("CraftBenchVerifierInfinite"));

	Effect->DurationPolicy = EGameplayEffectDurationType::Infinite;
	// Period stays 0 (the ctor default) => non-periodic => this rides the
	// attribute AGGREGATOR and moves the CURRENT value only, leaving the BASE
	// value alone. See PawnAttribute() vs PawnAttributeBase().
	AddModifier(Effect, Attribute, Op, Mag);

	StampAssetTag(Effect, AssetTag);
	return Effect;
}

bool CraftBenchTestEffects::HasAssetTag(const UGameplayEffect* Effect, const FGameplayTag& Tag)
{
	if (Effect == nullptr || !Tag.IsValid())
	{
		return false;
	}
	// GetAssetTags() is the inline public reader of CachedAssetTags
	// (GameplayEffect.h:2173). HasTagExact, not HasTag: a probe asking "did the
	// stamp land" must not be satisfied by a parent tag.
	return Effect->GetAssetTags().HasTagExact(Tag);
}
