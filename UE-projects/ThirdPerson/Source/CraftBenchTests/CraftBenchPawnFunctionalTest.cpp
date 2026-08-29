// Copyright CraftBench. All Rights Reserved.
//
// Ported verbatim from the CraftBenchTemplate substrate 2026-08-05 (see the
// header for provenance); the resolved ACraftBenchCharacter scaffold now lives
// in the ThirdPerson runtime module.

#include "CraftBenchPawnFunctionalTest.h"

#include "CraftBenchCharacter.h"
#include "AbilitySystemComponent.h"
#include "Abilities/GameplayAbility.h"
#include "GameplayEffect.h"
#include "GameplayTagContainer.h"
#include "GameFramework/Character.h"
#include "GameFramework/PlayerController.h"
#include "Kismet/GameplayStatics.h"
// Explicit, not leaned on transitively via Character.h — PawnVisiblyRepresented
// casts to both concrete component types.
#include "Components/MeshComponent.h"
#include "Components/SkeletalMeshComponent.h"
#include "Components/StaticMeshComponent.h"
#include "Engine/World.h"
#include "Engine/Blueprint.h"
#include "UObject/UObjectHash.h"
#include "AssetRegistry/AssetRegistryModule.h"
#include "AssetRegistry/IAssetRegistry.h"
#include "Modules/ModuleManager.h"

ACraftBenchPawnFunctionalTest::ACraftBenchPawnFunctionalTest(const FObjectInitializer& ObjectInitializer)
	: Super(ObjectInitializer)
{
}

void ACraftBenchPawnFunctionalTest::PrepareTest()
{
	Super::PrepareTest();
	// Spawn + possess the agent pawn. A subclass calls Super::PrepareTest() first,
	// then (if Pawn.IsValid()) sets its checkpoint schedule and per-task state.
	SpawnAndPossessPawn();
}

namespace
{
	// True if PawnClass's CDO auto-grants an ability whose asset tags contain Tag.
	bool PawnClassGrantsAbilityTag(const UClass* PawnClass, const FGameplayTag& Tag)
	{
		const ACraftBenchCharacter* CDO =
			(PawnClass != nullptr) ? GetDefault<ACraftBenchCharacter>(PawnClass) : nullptr;
		if (CDO == nullptr)
		{
			return false;
		}
		for (const TSubclassOf<UGameplayAbility>& AbilityClass : CDO->GrantedAbilities)
		{
			const UClass* Resolved = AbilityClass.Get();
			if (Resolved == nullptr)
			{
				continue;
			}
			const UGameplayAbility* AbilityCDO = GetDefault<UGameplayAbility>(Resolved);
			if (AbilityCDO != nullptr && AbilityCDO->GetAssetTags().HasTag(Tag))
			{
				return true;
			}
		}
		return false;
	}
}

FGameplayTag ACraftBenchPawnFunctionalTest::PreferredAbilityTag() const
{
	return FGameplayTag(); // invalid by default — resolve purely by derivation
}

TSubclassOf<ACraftBenchCharacter> ACraftBenchPawnFunctionalTest::ResolveAgentPawnClass() const
{
	// Gather candidate pawn classes in priority order: native (C++) subclasses
	// first (existing order), then Blueprint subclasses under /Game/Tasks.
	TArray<UClass*> Candidates;

	TArray<UClass*> Derived;
	GetDerivedClasses(ACraftBenchCharacter::StaticClass(), Derived, /*bRecursive=*/true);
	for (UClass* Candidate : Derived)
	{
		if (Candidate == ACraftBenchCharacter::StaticClass())
		{
			continue;
		}
		if (Candidate->HasAnyClassFlags(CLASS_Abstract | CLASS_Deprecated | CLASS_NewerVersionExists))
		{
			continue;
		}
		// Native (C++) subclass only here; Blueprint-generated classes carry a
		// ClassGeneratedBy and are gathered via the asset registry below.
		if (Candidate->ClassGeneratedBy != nullptr)
		{
			continue;
		}
		const FString Name = Candidate->GetName();
		if (Name.StartsWith(TEXT("SKEL_")) || Name.StartsWith(TEXT("REINST_")))
		{
			continue;
		}
		Candidates.Add(Candidate);
	}

	// Blueprint subclasses — a BP/MCP agent's deliverable. BP-generated classes are
	// not loaded unless referenced, so scan the asset registry under /Game/Tasks.
	IAssetRegistry& AssetRegistry =
		FModuleManager::LoadModuleChecked<FAssetRegistryModule>(TEXT("AssetRegistry")).Get();

	FARFilter Filter;
	Filter.ClassPaths.Add(UBlueprint::StaticClass()->GetClassPathName());
	Filter.PackagePaths.Add(FName(TEXT("/Game/Tasks")));
	Filter.bRecursivePaths = true;

	TArray<FAssetData> BlueprintAssets;
	AssetRegistry.GetAssets(Filter, BlueprintAssets);

	for (const FAssetData& Data : BlueprintAssets)
	{
		const UBlueprint* Blueprint = Cast<UBlueprint>(Data.GetAsset()); // loads it
		if (Blueprint == nullptr)
		{
			continue;
		}
		UClass* GenClass = Blueprint->GeneratedClass;
		if (GenClass != nullptr
			&& GenClass->IsChildOf(ACraftBenchCharacter::StaticClass())
			&& !GenClass->HasAnyClassFlags(CLASS_Abstract))
		{
			Candidates.Add(GenClass);
		}
	}

	// Ability-aware preference: if the fixture declares a trigger tag, return the
	// first candidate that GRANTS an ability with that tag. This disambiguates when
	// more than one ACraftBenchCharacter subclass is present (e.g. another task's
	// committed pawn carrying a different ability tag) — without it, a foreign pawn
	// could be resolved purely by enumeration order.
	const FGameplayTag Preferred = PreferredAbilityTag();
	if (Preferred.IsValid())
	{
		for (UClass* Candidate : Candidates)
		{
			if (PawnClassGrantsAbilityTag(Candidate, Preferred))
			{
				return Candidate;
			}
		}
	}

	// Legacy fallback: first candidate (native, then Blueprint), else the base. The
	// base's GrantedAbilities is empty, so a GAS task resolves to "no ability
	// granted" and fails (anti-gaming for the empty stub).
	if (Candidates.Num() > 0)
	{
		return Candidates[0];
	}
	return ACraftBenchCharacter::StaticClass();
}

bool ACraftBenchPawnFunctionalTest::SpawnAndPossessPawn()
{
	UWorld* World = GetWorld();
	if (World == nullptr)
	{
		FinishTest(EFunctionalTestResult::Failed, TEXT("SpawnAndPossessPawn: no world"));
		return false;
	}

	TSubclassOf<ACraftBenchCharacter> PawnClass = ResolveAgentPawnClass();

	FActorSpawnParameters Params;
	Params.SpawnCollisionHandlingOverride = ESpawnActorCollisionHandlingMethod::AlwaysSpawn;
	ACraftBenchCharacter* Spawned = World->SpawnActor<ACraftBenchCharacter>(
		PawnClass, FTransform(PawnSpawnLocation), Params);

	if (Spawned == nullptr)
	{
		FinishTest(EFunctionalTestResult::Failed,
			FString::Printf(TEXT("SpawnAndPossessPawn: spawn of %s failed"),
				*GetNameSafe(PawnClass)));
		return false;
	}

	// MANDATORY possession — an unpossessed Character is inert (Slice-0 spike).
	//
	// POSSESSED BY THE PIE PLAYER CONTROLLER, NOT A SPAWNED AI ONE (Option C,
	// owner-authorised 2026-08-18). This line used to read
	// `Spawned->SpawnDefaultController()`, and that one call made every task in this
	// family impossible for a human to play or even watch:
	//
	//   * no `AIControllerClass` override exists on any CraftBench character, so the
	//     default controller was an `AAIController`;
	//   * `PC->IsLocalController()` is then false, so `APawn::PawnClientRestart()`
	//     never ran, so `SetupPlayerInputComponent()` was never called and no
	//     `UEnhancedInputComponent` ever existed on the graded pawn;
	//   * and the fixture's `Pawn` member and `GetPlayerController(0)->GetPawn()`
	//     were DIFFERENT ACTORS — the thing graded was never the thing a person
	//     could drive.
	//
	// Nothing in the verifier noticed, because every fixture in this family drives
	// its subject through `TriggerAbilityByTag` and movement calls rather than a
	// keypress: a pawn with no input component graded byte-identically to a wired
	// one. So "62/62 references PASS" never implied a person could try any of it.
	//
	// Possessing the PIE-supplied player controller makes the graded pawn THE player
	// pawn. `AController::Possess` calls `PawnClientRestart` for a local controller,
	// which is what finally builds the input component — so this is also the
	// prerequisite for the input-injection programme (a fixture cannot press a key
	// at a pawn that has nothing to receive it).
	//
	// Fail LOUD rather than falling back to an AI controller: a silent fallback
	// would restore the old behaviour invisibly, and the whole point is that the
	// old behaviour was undetectable.
	APlayerController* PC = UGameplayStatics::GetPlayerController(World, 0);
	if (PC == nullptr)
	{
		FinishTest(EFunctionalTestResult::Failed,
			// ASCII ONLY in a Failed message. This line shipped an em dash in the
			// Option C change and it reached main: a cp1252 read-back turns
			// it to mojibake, and because this is the SHARED pawn base it broke the
			// ascii oracle for all 18 pawn-family tasks at once.
			TEXT("SpawnAndPossessPawn: no player controller at index 0 to possess "
				 "with; PIE must supply one (do NOT fall back to an AI controller - "
				 "that is what made this family unplayable)"));
		return false;
	}
	PC->Possess(Spawned);
	if (Spawned->GetController() != PC)
	{
		FinishTest(EFunctionalTestResult::Failed,
			FString::Printf(TEXT("SpawnAndPossessPawn: possession did not take; "
				"controller is %s"), *GetNameSafe(Spawned->GetController())));
		return false;
	}

	Pawn = Spawned;
	StartLocation = Spawned->GetActorLocation();
	return true;
}

void ACraftBenchPawnFunctionalTest::RecordSample(double T)
{
	if (!Pawn.IsValid())
	{
		return;
	}
	FCraftBenchTrajectorySample S;
	S.T = T;
	S.Location = Pawn->GetActorLocation();
	S.Velocity = Pawn->GetVelocity();
	if (UCharacterMovementComponent* CMC = Pawn->GetCharacterMovement())
	{
		S.Mode = CMC->MovementMode;
	}
	Samples.Add(S);
}

double ACraftBenchPawnFunctionalTest::ApexDeltaZ() const
{
	if (Samples.Num() == 0)
	{
		return 0.0;
	}
	const double StartZ = Samples[0].Location.Z;
	double Peak = StartZ;
	for (const FCraftBenchTrajectorySample& S : Samples)
	{
		Peak = FMath::Max(Peak, S.Location.Z);
	}
	return Peak - StartZ;
}

bool ACraftBenchPawnFunctionalTest::RoseThenFell(double MinRise, double FallMargin) const
{
	if (Samples.Num() < 3)
	{
		return false;
	}
	const double StartZ = Samples[0].Location.Z;
	int32 PeakIdx = 0;
	double PeakZ = StartZ;
	for (int32 i = 0; i < Samples.Num(); ++i)
	{
		if (Samples[i].Location.Z > PeakZ)
		{
			PeakZ = Samples[i].Location.Z;
			PeakIdx = i;
		}
	}
	if (PeakZ - StartZ < MinRise)
	{
		return false; // never rose enough
	}
	if (PeakIdx >= Samples.Num() - 1)
	{
		return false; // peak is the last sample → never came back down (teleport-up)
	}
	return Samples.Last().Location.Z < PeakZ - FallMargin;
}

bool ACraftBenchPawnFunctionalTest::ReachedMovementMode(EMovementMode InMode) const
{
	for (const FCraftBenchTrajectorySample& S : Samples)
	{
		if (S.Mode == InMode)
		{
			return true;
		}
	}
	return false;
}

double ACraftBenchPawnFunctionalTest::VelocityZNear(double T) const
{
	double Best = 0.0;
	double BestT = -TNumericLimits<double>::Max();
	for (const FCraftBenchTrajectorySample& S : Samples)
	{
		if (S.T <= T && S.T > BestT)
		{
			BestT = S.T;
			Best = S.Velocity.Z;
		}
	}
	return Best;
}

double ACraftBenchPawnFunctionalTest::MaxVelocityZAfter(double T) const
{
	double Best = 0.0;
	bool bAny = false;
	for (const FCraftBenchTrajectorySample& S : Samples)
	{
		if (S.T > T)
		{
			Best = bAny ? FMath::Max(Best, S.Velocity.Z) : S.Velocity.Z;
			bAny = true;
		}
	}
	return bAny ? Best : 0.0;
}

bool ACraftBenchPawnFunctionalTest::PawnVisiblyRepresented(FString& OutWhy) const
{
	const ACraftBenchCharacter* P = Pawn.Get();
	if (P == nullptr)
	{
		OutWhy = TEXT("the character is not visibly represented: the graded pawn could not be resolved");
		return false;
	}

	TArray<UMeshComponent*> MeshComponents;
	P->GetComponents<UMeshComponent>(MeshComponents);

	// Counted separately so the FAIL can say WHICH of the three ways it went
	// wrong. "no mesh at all" and "a mesh you hid" are different mistakes and a
	// reviewer should not have to guess which one they made.
	int32 WithAsset = 0;
	int32 HiddenWithAsset = 0;
	int32 DegenerateScaleWithAsset = 0;

	for (const UMeshComponent* MeshComp : MeshComponents)
	{
		if (MeshComp == nullptr)
		{
			continue;
		}

		bool bHasAsset = false;
		if (const USkeletalMeshComponent* SkelComp = Cast<USkeletalMeshComponent>(MeshComp))
		{
			bHasAsset = SkelComp->GetSkeletalMeshAsset() != nullptr;
		}
		else if (const UStaticMeshComponent* StaticComp = Cast<UStaticMeshComponent>(MeshComp))
		{
			bHasAsset = StaticComp->GetStaticMesh() != nullptr;
		}
		if (!bHasAsset)
		{
			continue;
		}
		++WithAsset;

		// bHiddenInGame is checked alongside IsVisible() rather than trusting
		// IsVisible() alone: they are separate flags on USceneComponent and a
		// component can report visible while still being hidden in game.
		if (!MeshComp->IsVisible() || MeshComp->bHiddenInGame)
		{
			++HiddenWithAsset;
			continue;
		}
		if (MeshComp->GetComponentScale().GetAbsMin() <= 0.01)
		{
			++DegenerateScaleWithAsset;
			continue;
		}

		return true;   // a mesh, assigned, rendering, at a real size
	}

	if (WithAsset == 0)
	{
		OutWhy = TEXT("the character is not visibly represented: no mesh component with an assigned mesh on the graded pawn");
	}
	else if (HiddenWithAsset > 0 && DegenerateScaleWithAsset > 0)
	{
		OutWhy = FString::Printf(TEXT(
			"the character is not visibly represented: the pawn has %d mesh component(s) "
			"with a mesh assigned, but every one is hidden in game (%d) or scaled to "
			"nothing (%d)  -  nothing would render"),
			WithAsset, HiddenWithAsset, DegenerateScaleWithAsset);
	}
	else if (HiddenWithAsset > 0)
	{
		OutWhy = FString::Printf(TEXT(
			"the character is not visibly represented: the pawn has %d mesh component(s) "
			"with a mesh assigned, but every one is HIDDEN IN GAME  -  a reviewer "
			"watching the run would see nothing"),
			WithAsset);
	}
	else
	{
		OutWhy = FString::Printf(TEXT(
			"the character is not visibly represented: the pawn has %d mesh "
			"component(s) with a mesh assigned, but every one is scaled to ~zero  -  a "
			"reviewer watching the run would see nothing"),
			WithAsset);
	}
	return false;
}

UAbilitySystemComponent* ACraftBenchPawnFunctionalTest::PawnASC() const
{
	return Pawn.IsValid() ? Pawn->GetAbilitySystemComponent() : nullptr;
}

int32 ACraftBenchPawnFunctionalTest::NumGrantedAbilitiesWithTag(const FGameplayTag& Tag) const
{
	UAbilitySystemComponent* ASC = PawnASC();
	if (ASC == nullptr)
	{
		return 0;
	}
	int32 Count = 0;
	for (const FGameplayAbilitySpec& Spec : ASC->GetActivatableAbilities())
	{
		if (Spec.Ability != nullptr && Spec.Ability->GetAssetTags().HasTag(Tag))
		{
			++Count;
		}
	}
	return Count;
}

bool ACraftBenchPawnFunctionalTest::TriggerAbilityByTag(const FGameplayTag& Tag)
{
	UAbilitySystemComponent* ASC = PawnASC();
	if (ASC == nullptr)
	{
		return false;
	}
	const bool bActivated = ASC->TryActivateAbilitiesByTag(FGameplayTagContainer(Tag));
	if (bActivated)
	{
		bAbilityActivated = true;
	}
	return bActivated;
}

// ---------------------------------------------------------------------------
// GameplayEffect application (V1.1) + attribute dual read (V1.4), 2026-08-08.
// the g2 verifier-extensions spec §5. Additive only: nothing above this
// line changed, so no existing gate, epoch or MATRIX record is affected.
// ---------------------------------------------------------------------------

FActiveGameplayEffectHandle ACraftBenchPawnFunctionalTest::ApplyEffectToPawn(
	UGameplayEffect* Effect, float Level)
{
	if (Effect == nullptr)
	{
		// A factory in CraftBenchTestEffects.h returned nullptr (invalid attribute
		// or non-positive period). That is a VERIFIER-side argument error, not a
		// submission error, and it is named so nobody mines it as a model failure.
		FinishTest(EFunctionalTestResult::Failed, TEXT(
			"ApplyEffectToPawn: the verifier was handed a null gameplay effect. This is a fixture-side "
			"argument fault (an invalid attribute or a non-positive period passed to the effect factory), "
			"not a fault in the submission."));
		return FActiveGameplayEffectHandle();
	}

	// GC anchor FIRST, before any early return: the definition must outlive this
	// call whether or not the application succeeds, because a failed application
	// is itself an observation a later checkpoint may want to re-test.
	VerifierEffects.AddUnique(Effect);

	UAbilitySystemComponent* ASC = PawnASC();
	if (ASC == nullptr)
	{
		FinishTest(EFunctionalTestResult::Failed, TEXT(
			"ApplyEffectToPawn: the graded pawn has no ability system component, so the world cannot apply "
			"a gameplay effect to it."));
		return FActiveGameplayEffectHandle();
	}

	// ---- AUTHORITY GATE -------------------------------------------------------
	// UAbilitySystemComponent::ApplyGameplayEffectToSelf silently returns an empty
	// handle unless HasNetworkAuthorityToApplyGameplayEffect() holds
	// (AbilitySystemComponent.cpp:671), and that predicate is
	// IsOwnerActorAuthoritative() == !bCachedIsNetSimulated (:455-458, :2115-2118).
	// Epic's own suite sets ROLE_Authority + CacheIsNetSimulated() before every
	// application (GameplayEffectTests.cpp:744-745) for exactly this reason.
	//
	// Both predicates are checked, not one, because they can disagree:
	// IsNetSimulating() (ActorComponent.h:1512, `GetIsReplicated() && GetOwnerRole()
	// != ROLE_Authority`) is a LIVE read, while GAS gates on the value CACHED at the
	// last CacheIsNetSimulated() call (:355-360). A stale cache would let the live
	// read pass while GAS still refuses to apply — and that failure would look
	// exactly like "the drain did nothing", i.e. like the submission working.
	//
	// The default headless PIE lane is standalone-authority, so this never fires
	// there. It exists so that if it EVER does, it is a named harness failure
	// instead of a silent green.
	if (ASC->IsNetSimulating() || !ASC->IsOwnerActorAuthoritative())
	{
		FinishTest(EFunctionalTestResult::Failed, TEXT(
			"ApplyEffectToPawn: the pawn's ability system is not the network authority, so the gameplay "
			"effect would be silently dropped or merely predicted instead of applied. This is a harness "
			"condition, never a fault in the submission - without this named failure it would present as "
			"the submitted feature working."));
		return FActiveGameplayEffectHandle();
	}

	// AbilitySystemComponent.h:773 - takes an INSTANCE, which is the whole reason
	// a runtime-built effect works with zero Build.cs or asset change.
	//
	// The returned handle is NOT checked here on purpose. An instant effect always
	// returns IsValid() == false with WasSuccessfullyApplied() == true
	// (ActiveGameplayEffectHandle.h:40-48), and a submission that legitimately
	// blocked the application also returns an empty handle. Gate on the value.
	return ASC->ApplyGameplayEffectToSelf(Effect, Level, ASC->MakeEffectContext());
}

bool ACraftBenchPawnFunctionalTest::RemoveEffectFromPawn(FActiveGameplayEffectHandle Handle)
{
	UAbilitySystemComponent* ASC = PawnASC();
	if (ASC == nullptr || !Handle.IsValid())
	{
		return false;
	}
	// Authority pre-check, NOT redundant with the one in ApplyEffectToPawn: on a
	// non-authority ASC, UAbilitySystemComponent::RemoveActiveGameplayEffect logs
	// at Warning ("called without Authority when attempting to remove ...",
	// AbilitySystemComponent.cpp:1254-1257) before returning false. Automation
	// elevates a Warning in the test window to an ERROR
	// (FFunctionalTestBase::bElevateLogWarningsToErrors = true,
	// Developer/FunctionalTesting/Private/FunctionalTestBase.cpp:24), which zeroes
	// the ENTIRE fixture - every unrelated leg with it. Return false quietly.
	if (!ASC->IsOwnerActorAuthoritative())
	{
		return false;
	}
	return ASC->RemoveActiveGameplayEffect(Handle);
}

int32 ACraftBenchPawnFunctionalTest::PawnEffectCount(const UGameplayEffect* Def) const
{
	UAbilitySystemComponent* ASC = PawnASC();
	if (ASC == nullptr || Def == nullptr)
	{
		return 0;
	}

	// Pointer identity on Spec.Def - the same identity GAS's own stacking search
	// uses (GameplayEffect.cpp:3690, `ActiveEffect.Spec.Def == Spec.Def`).
	//
	// NOT GetGameplayEffectCount: that builds a query matching
	// `SourceGameplayEffect == CurEffect.Spec.Def->GetClass()`
	// (AbilitySystemComponent.cpp:569). Every effect these fixtures build is a
	// plain NewObject<UGameplayEffect>, so they ALL share the class
	// UGameplayEffect and a class-keyed count returns the sum of all of them.
	//
	// FGameplayEffectQuery::Matches consults CustomMatchDelegate first and then
	// falls through to Matches(Spec); every other field of the query is left
	// default so nothing else narrows the result (GameplayEffect.cpp:6072-6101).
	FGameplayEffectQuery Query;
	Query.CustomMatchDelegate.BindLambda(
		[Def](const FActiveGameplayEffect& ActiveEffect) -> bool
		{
			// .Get() rather than relying on TObjectPtr's comparison overloads:
			// the raw-pointer compare is unambiguous and the delegate's return
			// type is pinned to bool so no overload deduction is involved.
			return ActiveEffect.Spec.Def.Get() == Def;
		});

	// GetActiveEffects returns one handle per ACTIVE ENTRY (GameplayEffect.cpp:5600),
	// so a 3-stack effect counts 1. That is deliberate: the stack-summing reader,
	// GetActiveEffectCount (:5714, `Count += Spec.GetStackCount()`), also silently
	// skips inhibited effects, which would make "the submission inhibited it"
	// indistinguishable from "the submission removed it".
	return ASC->GetActiveEffects(Query).Num();
}

bool ACraftBenchPawnFunctionalTest::PawnHasAttribute(const FGameplayAttribute& Attribute) const
{
	UAbilitySystemComponent* ASC = PawnASC();
	return ASC != nullptr && ASC->HasAttributeSetForAttribute(Attribute);
}

double ACraftBenchPawnFunctionalTest::PawnAttribute(const FGameplayAttribute& Attribute) const
{
	UAbilitySystemComponent* ASC = PawnASC();
	if (ASC == nullptr || !ASC->HasAttributeSetForAttribute(Attribute))
	{
		return 0.0;
	}
	// Post-aggregator CURRENT value (AbilitySystemComponent.cpp:483-497). Reading
	// the base here instead would false-FAIL any implementation that answers with
	// an Override or a multiplicative modifier, which never touch the base.
	return static_cast<double>(ASC->GetNumericAttribute(Attribute));
}

double ACraftBenchPawnFunctionalTest::PawnAttributeBase(const FGameplayAttribute& Attribute) const
{
	UAbilitySystemComponent* ASC = PawnASC();
	// The HasAttributeSetForAttribute guard is LOAD-BEARING here, not defensive
	// symmetry with PawnAttribute: GetNumericAttributeBase reaches
	// FActiveGameplayEffectsContainer::GetAttributeBaseValue, which fires an
	// ensureMsgf when the ASC has no matching attribute set
	// (GameplayEffect.cpp:4048). An ensure inside the test window is an automation
	// error that zeroes the whole fixture, so a pawn with no health system would
	// be scored as a harness-shaped blowup instead of failing by name at the
	// gate that meant to check for it.
	if (ASC == nullptr || !ASC->HasAttributeSetForAttribute(Attribute))
	{
		return 0.0;
	}
	return static_cast<double>(ASC->GetNumericAttributeBase(Attribute));
}

// --- I1.4: dense sampling + segmented motion (2026-08-10) --------------------
//
// See the header block for why the pre-existing reductions cannot answer "rose a
// second time". Everything here is opt-in and additive: with bDenseSampling
// false (the default) Tick does exactly what the base did, so glide and poison
// are byte-identical and no committed verdict can move.

void ACraftBenchPawnFunctionalTest::Tick(float DeltaSeconds)
{
	// Base FIRST: it owns the checkpoint clock, and OnCheckpoint bodies expect
	// the samples a fixture took itself to already be in the series.
	Super::Tick(DeltaSeconds);

	if (!bDenseSampling || !Pawn.IsValid())
	{
		return;
	}
	const UWorld* World = GetWorld();
	if (World == nullptr)
	{
		return;
	}
	// World game-time, the same clock the checkpoint schedule reads (repo convention:
	// NOT AFunctionalTest::TotalTime, which is offset by the IsReady->StartTest
	// warmup). Mixing the two would put dense samples on a different timebase
	// from the checkpoint times a gate compares them against.
	RecordSample(World->GetTimeSeconds());
}

TArray<FCraftBenchMotionSegment> ACraftBenchPawnFunctionalTest::Segments(double MinDeltaZ) const
{
	TArray<FCraftBenchMotionSegment> Out;
	if (Samples.Num() < 2)
	{
		return Out;
	}

	// Walk the series accumulating a run in one direction. A direction flip only
	// CLOSES the run once the run it would start has itself moved MinDeltaZ --
	// otherwise a single noisy sample at the apex would split one jump into three
	// segments and NumRises would read 2 for a single jump. That absorption is
	// the whole reason MinDeltaZ is a parameter and not a constant.
	int32 RunStart = 0;
	bool bRising = Samples[1].Location.Z >= Samples[0].Location.Z;
	double PendingExtremeZ = Samples[0].Location.Z;
	int32 PendingExtremeIdx = 0;

	auto Emit = [&](int32 StartIdx, int32 EndIdx, bool bWasRising)
	{
		if (EndIdx <= StartIdx) { return; }
		FCraftBenchMotionSegment Seg;
		Seg.StartT = Samples[StartIdx].T;
		Seg.EndT = Samples[EndIdx].T;
		Seg.StartZ = Samples[StartIdx].Location.Z;
		Seg.EndZ = Samples[EndIdx].Location.Z;
		Seg.bRising = bWasRising;
		if (FMath::Abs(Seg.DeltaZ()) >= MinDeltaZ)
		{
			Out.Add(Seg);
		}
	};

	for (int32 i = 1; i < Samples.Num(); ++i)
	{
		const double Z = Samples[i].Location.Z;
		if (bRising)
		{
			if (Z >= PendingExtremeZ) { PendingExtremeZ = Z; PendingExtremeIdx = i; }
			else if (PendingExtremeZ - Z >= MinDeltaZ)
			{
				// A genuine reversal: close the rise at its peak, start a fall.
				Emit(RunStart, PendingExtremeIdx, /*bWasRising=*/true);
				RunStart = PendingExtremeIdx;
				bRising = false;
				PendingExtremeZ = Z; PendingExtremeIdx = i;
			}
		}
		else
		{
			if (Z <= PendingExtremeZ) { PendingExtremeZ = Z; PendingExtremeIdx = i; }
			else if (Z - PendingExtremeZ >= MinDeltaZ)
			{
				Emit(RunStart, PendingExtremeIdx, /*bWasRising=*/false);
				RunStart = PendingExtremeIdx;
				bRising = true;
				PendingExtremeZ = Z; PendingExtremeIdx = i;
			}
		}
	}
	Emit(RunStart, Samples.Num() - 1, bRising);
	return Out;
}

int32 ACraftBenchPawnFunctionalTest::NumRises(double MinRiseZ) const
{
	int32 N = 0;
	for (const FCraftBenchMotionSegment& Seg : Segments(MinRiseZ))
	{
		if (Seg.bRising && Seg.DeltaZ() >= MinRiseZ) { ++N; }
	}
	return N;
}

double ACraftBenchPawnFunctionalTest::MeanVerticalRate(double FromT, double ToT) const
{
	const FCraftBenchTrajectorySample* First = nullptr;
	const FCraftBenchTrajectorySample* Last = nullptr;
	for (const FCraftBenchTrajectorySample& S : Samples)
	{
		if (S.T > FromT && S.T <= ToT)
		{
			if (First == nullptr) { First = &S; }
			Last = &S;
		}
	}
	if (First == nullptr || Last == nullptr || Last == First) { return 0.0; }
	const double Dt = Last->T - First->T;
	return (Dt > KINDA_SMALL_NUMBER) ? (Last->Location.Z - First->Location.Z) / Dt : 0.0;
}

FString ACraftBenchPawnFunctionalTest::DescribeSegments(double MinDeltaZ) const
{
	const TArray<FCraftBenchMotionSegment> Segs = Segments(MinDeltaZ);
	FString S = FString::Printf(TEXT("samples=%d minDeltaZ=%.1f segments=%d ["),
		Samples.Num(), MinDeltaZ, Segs.Num());
	for (int32 i = 0; i < Segs.Num(); ++i)
	{
		S += FString::Printf(TEXT("%s%s t=%.2f-%.2f z=%.0f->%.0f d=%+.0f"),
			(i ? TEXT(" | ") : TEXT("")),
			Segs[i].bRising ? TEXT("RISE") : TEXT("FALL"),
			Segs[i].StartT, Segs[i].EndT, Segs[i].StartZ, Segs[i].EndZ, Segs[i].DeltaZ());
	}
	S += TEXT("]");
	return S;
}
