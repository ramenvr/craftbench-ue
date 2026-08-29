// Copyright CraftBench. All Rights Reserved.

#include "CraftBenchPawnFunctionalTest.h"

#include "CraftBenchCharacter.h"
#include "AbilitySystemComponent.h"
#include "Abilities/GameplayAbility.h"
#include "GameplayTagContainer.h"
#include "GameFramework/Character.h"
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
	Spawned->SpawnDefaultController();

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
