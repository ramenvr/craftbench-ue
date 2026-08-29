// Copyright CraftBench. All Rights Reserved.
//
// VERIFIER-ONLY MODULE — DO NOT EDIT.
// See Source/CraftBenchTests/.AGENT_WRITE_DENY for the no-edit policy.
//
// AGraphMathFunctionalTest implementation. PIE-native (see header). The base
// (ACraftBenchFunctionalTest) owns the PIE lever, fixed-timestep, and the
// checkpoint clock; this fixture owns the marker GLog listener plus the
// load-by-path / spawn / pre-BeginPlay value override of the agent's Blueprint.
//
// Lifecycle law this fixture leans on (docs/pie-verification-playbook.md):
// FWorldDelegates::OnWorldInitializedActors fires BEFORE BeginPlay is
// dispatched to the world's actors, and an actor spawned at that point into a
// world that has not begun play receives its BeginPlay later, with the rest of
// the world. That window is where both editable values are overridden, so the
// agent's graph can only pass by reading the instance's actual current values.

#include "GraphMathFunctionalTest.h"

#include "Engine/World.h"
#include "GameFramework/Actor.h"
#include "Tasks/t1-blueprint-graph-on-beginplay/GraphMathActor.h"
#include "UObject/UObjectGlobals.h"

namespace
{
	// The deliverable's required path (stated in the task prompt). The "_C"
	// suffix selects the Blueprint's generated class.
	static const TCHAR* GraphMathClassPath =
		TEXT("/Game/Tasks/t1-blueprint-graph-on-beginplay/BP_GraphMath.BP_GraphMath_C");

	// Print String routes to LogBlueprintUserMessages at Log verbosity when
	// bPrintToLog=true (the Print String default). Filter exactly that channel.
	static const FName BpUserMessagesCategory(TEXT("LogBlueprintUserMessages"));

	// The marker prefix every submission line must carry, and the one exact
	// line the overridden instance must produce. Each is ONE string literal
	// (the discrimination matrix greps these substrings statically).
	static const TCHAR* MarkerPrefix = TEXT("CRAFTBENCH_GRAPH_TOTAL=");
	static const TCHAR* ExpectedLine = TEXT("CRAFTBENCH_GRAPH_TOTAL=179");

	// The pre-BeginPlay per-instance overrides. The scaffold defaults are
	// BaseValue=7, BonusValue=5 (sum 12); these values make a default-derived
	// hardcode fail the exact-line gate.
	static constexpr int32 OverrideBaseValue = 137;
	static constexpr int32 OverrideBonusValue = 42;
	static_assert(OverrideBaseValue + OverrideBonusValue == 179,
		"ExpectedLine must encode OverrideBaseValue + OverrideBonusValue");
}

void FGraphMathTokenCounterDevice::Serialize(const TCHAR* V, ELogVerbosity::Type Verbosity, const FName& InCategory)
{
	if (V == nullptr)
	{
		return;
	}
	if (InCategory != Category)
	{
		return;
	}
	const ELogVerbosity::Type EffectiveVerbosity =
		static_cast<ELogVerbosity::Type>(Verbosity & ELogVerbosity::VerbosityMask);
	if (EffectiveVerbosity > MinVerbosity)
	{
		return;
	}
	if (FCString::Strstr(V, *MarkerPrefix) != nullptr)
	{
		++PrefixCount;
		if (FCString::Strstr(V, *ExpectedLine) != nullptr)
		{
			++ExactCount;
		}
	}
}

AGraphMathFunctionalTest::AGraphMathFunctionalTest(const FObjectInitializer& ObjectInitializer)
	: Super(ObjectInitializer)
{
	// Bind the pre-BeginPlay hook: listener install + subject spawn + value
	// override all happen before any BeginPlay runs in this world.
	WorldInitHandle = FWorldDelegates::OnWorldInitializedActors.AddUObject(
		this, &AGraphMathFunctionalTest::OnWorldActorsInitialized);
}

void AGraphMathFunctionalTest::InstallLogDevice()
{
	if (bDeviceInstalled)
	{
		return;
	}
	LogCounter = MakeUnique<FGraphMathTokenCounterDevice>(
		FString(MarkerPrefix), FString(ExpectedLine), BpUserMessagesCategory, ELogVerbosity::Log);
	if (GLog != nullptr)
	{
		GLog->AddOutputDevice(LogCounter.Get());
		bDeviceInstalled = true;
	}
}

void AGraphMathFunctionalTest::OnWorldActorsInitialized(const FActorsInitializedParams& Params)
{
	if (bWorldInitHandled || Params.World != GetWorld())
	{
		return;
	}
	bWorldInitHandled = true;

	// Listener first, so even a construction-time print is observed.
	InstallLogDevice();

	// The world has initialized actors but has NOT begun play yet: an actor
	// spawned here gets its BeginPlay dispatched with the rest of the world,
	// AFTER the value overrides below.
	SetupSubject(Params.World, /*bWorldHasBegunPlay=*/false);
}

void AGraphMathFunctionalTest::SetupSubject(UWorld* World, bool bWorldHasBegunPlay)
{
	// Load by the required path. Null means no asset there (empty submission,
	// C++-only submission, or wrong path) — recorded, then FAILed by name in
	// PrepareTest (FinishTest is not legal this early).
	UClass* LoadedClass = StaticLoadClass(AActor::StaticClass(), nullptr, GraphMathClassPath);
	if (LoadedClass == nullptr)
	{
		SetupStatus = EGraphMathSetupStatus::AssetMissing;
		return;
	}

	if (!LoadedClass->IsChildOf(AGraphMathActor::StaticClass()))
	{
		SetupStatus = EGraphMathSetupStatus::WrongParent;
		return;
	}

	const FTransform SpawnTransform(FVector(0.0f, 0.0f, 120.0f));
	AGraphMathActor* Instance = nullptr;

	if (!bWorldHasBegunPlay)
	{
		// Pre-BeginPlay world: plain spawn defers BeginPlay to world start.
		FActorSpawnParameters SpawnParams;
		SpawnParams.SpawnCollisionHandlingOverride = ESpawnActorCollisionHandlingMethod::AlwaysSpawn;
		Instance = Cast<AGraphMathActor>(World->SpawnActor<AActor>(LoadedClass, SpawnTransform, SpawnParams));
		if (Instance != nullptr)
		{
			// The pre-BeginPlay override: the graph must READ these to pass.
			Instance->BaseValue = OverrideBaseValue;
			Instance->BonusValue = OverrideBonusValue;
		}
	}
	else
	{
		// Fallback (delegate never fired): deferred spawn keeps the override
		// ahead of BeginPlay even inside an already-playing world.
		Instance = World->SpawnActorDeferred<AGraphMathActor>(
			LoadedClass, SpawnTransform, nullptr, nullptr,
			ESpawnActorCollisionHandlingMethod::AlwaysSpawn);
		if (Instance != nullptr)
		{
			Instance->BaseValue = OverrideBaseValue;
			Instance->BonusValue = OverrideBonusValue;
			Instance->FinishSpawning(SpawnTransform);
		}
	}

	if (Instance == nullptr)
	{
		SetupStatus = EGraphMathSetupStatus::SpawnFailed;
		return;
	}

	Subject = Instance;
	SetupStatus = EGraphMathSetupStatus::Ok;
}

void AGraphMathFunctionalTest::PrepareTest()
{
	Super::PrepareTest();  // base: snapshot FApp globals + set fixed dt

	UWorld* World = GetWorld();
	if (World == nullptr)
	{
		FinishTest(EFunctionalTestResult::Error, TEXT("PrepareTest: no UWorld available"));
		return;
	}

	// Defensive fallback: if the world-init delegate never fired for this
	// world, install the listener and do the deferred-spawn setup now (still
	// override-before-BeginPlay via SpawnActorDeferred).
	InstallLogDevice();
	if (SetupStatus == EGraphMathSetupStatus::NotAttempted)
	{
		SetupSubject(World, /*bWorldHasBegunPlay=*/true);
	}

	switch (SetupStatus)
	{
	case EGraphMathSetupStatus::AssetMissing:
		FinishTest(
			EFunctionalTestResult::Failed,
			FString::Printf(
				TEXT("No Actor Blueprint found at the required path '%s'; the deliverable "
					 "was not authored (or was authored elsewhere / in C++ only)."),
				GraphMathClassPath));
		return;
	case EGraphMathSetupStatus::WrongParent:
		FinishTest(
			EFunctionalTestResult::Failed,
			FString::Printf(
				TEXT("The Blueprint at '%s' does not derive from the task actor type "
					 "GraphMathActor, so it does not carry the two editable task values."),
				GraphMathClassPath));
		return;
	case EGraphMathSetupStatus::SpawnFailed:
		FinishTest(
			EFunctionalTestResult::Failed,
			FString::Printf(TEXT("Failed to spawn an instance of '%s'."), GraphMathClassPath));
		return;
	case EGraphMathSetupStatus::Ok:
	default:
		break;
	}

	SetCheckpointSchedule({ 0.3 });
}

void AGraphMathFunctionalTest::OnCheckpoint(int32 /*CheckpointIndex*/, double /*TimeSeconds*/)
{
	const int32 Prefix = LogCounter.IsValid() ? LogCounter->GetPrefixCount() : -1;
	const int32 Exact = LogCounter.IsValid() ? LogCounter->GetExactCount() : -1;

	if (Exact == 1 && Prefix == 1)
	{
		FinishTest(EFunctionalTestResult::Succeeded, TEXT(""));
		return;
	}

	if (Prefix <= 0)
	{
		FinishTest(
			EFunctionalTestResult::Failed,
			FString::Printf(
				TEXT("Expected one 'CRAFTBENCH_GRAPH_TOTAL=' line from the spawned Blueprint "
					 "instance during its BeginPlay window; observed none - the graph did not "
					 "print the required line. (prefix count=%d)"),
				Prefix));
	}
	else if (Exact == 0)
	{
		FinishTest(
			EFunctionalTestResult::Failed,
			FString::Printf(
				TEXT("A 'CRAFTBENCH_GRAPH_TOTAL=' line was logged but none matched the expected "
					 "'CRAFTBENCH_GRAPH_TOTAL=179' (BaseValue 137 + BonusValue 42, set on the "
					 "instance before play began): the printed total does not reflect the "
					 "instance's current values. (prefix count=%d, exact count=%d)"),
				Prefix, Exact));
	}
	else
	{
		FinishTest(
			EFunctionalTestResult::Failed,
			FString::Printf(
				TEXT("The required line must be printed exactly once; observed %d "
					 "'CRAFTBENCH_GRAPH_TOTAL=' emissions (%d exact matches)."),
				Prefix, Exact));
	}
}

void AGraphMathFunctionalTest::RemoveLogDevice()
{
	if (LogCounter.IsValid())
	{
		if (GLog != nullptr)
		{
			GLog->RemoveOutputDevice(LogCounter.Get());
		}
		LogCounter.Reset();
	}
	bDeviceInstalled = false;
}

void AGraphMathFunctionalTest::EndPlay(const EEndPlayReason::Type EndPlayReason)
{
	RemoveLogDevice();
	if (WorldInitHandle.IsValid())
	{
		FWorldDelegates::OnWorldInitializedActors.Remove(WorldInitHandle);
		WorldInitHandle.Reset();
	}
	Super::EndPlay(EndPlayReason);
}
