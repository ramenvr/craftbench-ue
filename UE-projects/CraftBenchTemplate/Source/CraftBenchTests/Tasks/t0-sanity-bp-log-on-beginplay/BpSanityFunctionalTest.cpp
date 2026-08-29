// Copyright CraftBench. All Rights Reserved.
//
// VERIFIER-ONLY MODULE — DO NOT EDIT.
// See Source/CraftBenchTests/.AGENT_WRITE_DENY for the no-edit policy.
//
// ABpSanityFunctionalTest implementation. PIE-native (see header). The base
// (ACraftBenchFunctionalTest) owns the PIE lever, fixed-timestep, and the
// checkpoint clock; this fixture owns the token GLog listener + the load-by-path
// and spawn of the agent's Blueprint.

#include "BpSanityFunctionalTest.h"

#include "Engine/World.h"
#include "GameFramework/Actor.h"
#include "UObject/UObjectGlobals.h"

namespace
{
	// The deliverable's required path (stated in the task prompt). The "_C" suffix
	// selects the Blueprint's generated class.
	static const TCHAR* AnnouncerClassPath = TEXT("/Game/Tasks/t0-sanity-bp-log-on-beginplay/BP_Announcer.BP_Announcer_C");

	// Print String routes to LogBlueprintUserMessages at Log verbosity when
	// bPrintToLog=true (the Print String default). Filter exactly that channel.
	static const FName BpUserMessagesCategory(TEXT("LogBlueprintUserMessages"));
	static const TCHAR* BpToken = TEXT("CRAFTBENCH_BP_OK");
}

void FBpTokenCounterDevice::Serialize(const TCHAR* V, ELogVerbosity::Type Verbosity, const FName& InCategory)
{
	if (V == nullptr)
	{
		return;
	}
	if (InCategory != Category)
	{
		return;
	}
	const ELogVerbosity::Type EffectiveVerbosity = static_cast<ELogVerbosity::Type>(Verbosity & ELogVerbosity::VerbosityMask);
	if (EffectiveVerbosity > MinVerbosity)
	{
		return;
	}
	if (FCString::Strstr(V, *Substring) != nullptr)
	{
		++MatchCount;
	}
}

ABpSanityFunctionalTest::ABpSanityFunctionalTest(const FObjectInitializer& ObjectInitializer)
	: Super(ObjectInitializer)
{
	// Install the GLog device early — before our spawn — so the BeginPlay-window
	// emission is captured.
	WorldInitHandle = FWorldDelegates::OnWorldInitializedActors.AddUObject(
		this, &ABpSanityFunctionalTest::OnWorldActorsInitialized);
}

void ABpSanityFunctionalTest::OnWorldActorsInitialized(const FActorsInitializedParams& Params)
{
	if (bDeviceInstalled || Params.World != GetWorld())
	{
		return;
	}
	// Verbosity floor = Log (Print String's default), category = LogBlueprintUserMessages.
	LogCounter = MakeUnique<FBpTokenCounterDevice>(
		FString(BpToken), BpUserMessagesCategory, ELogVerbosity::Log);
	if (GLog != nullptr)
	{
		GLog->AddOutputDevice(LogCounter.Get());
		bDeviceInstalled = true;
	}
}

void ABpSanityFunctionalTest::PrepareTest()
{
	Super::PrepareTest();  // base: snapshot FApp globals + set fixed dt (1/60)

	UWorld* World = GetWorld();
	if (World == nullptr)
	{
		FinishTest(EFunctionalTestResult::Error, TEXT("PrepareTest: no UWorld available"));
		return;
	}

	// Ensure the listener is up even if the world-init delegate did not fire for us.
	if (!bDeviceInstalled)
	{
		LogCounter = MakeUnique<FBpTokenCounterDevice>(
			FString(BpToken), BpUserMessagesCategory, ELogVerbosity::Log);
		if (GLog != nullptr)
		{
			GLog->AddOutputDevice(LogCounter.Get());
			bDeviceInstalled = true;
		}
	}

	// Load the agent's Blueprint by its required path and spawn one instance.
	// StaticLoadClass returns null if the asset does not exist there (empty or
	// C++-only submission, or wrong path) — a named FAIL, not a crash.
	UClass* AnnouncerClass = StaticLoadClass(AActor::StaticClass(), nullptr, AnnouncerClassPath);
	if (AnnouncerClass == nullptr)
	{
		FinishTest(
			EFunctionalTestResult::Failed,
			FString::Printf(
				TEXT("No Actor Blueprint found at the required path '%s'; the deliverable "
					 "was not authored (or was authored elsewhere / in C++)."),
				AnnouncerClassPath));
		return;
	}

	FActorSpawnParameters SpawnParams;
	SpawnParams.SpawnCollisionHandlingOverride = ESpawnActorCollisionHandlingMethod::AlwaysSpawn;
	AActor* Instance = World->SpawnActor<AActor>(AnnouncerClass, FTransform::Identity, SpawnParams);
	bSpawned = (Instance != nullptr);
	SpawnedInstance = Instance;
	if (!bSpawned)
	{
		FinishTest(
			EFunctionalTestResult::Failed,
			FString::Printf(TEXT("Failed to spawn an instance of '%s'."), AnnouncerClassPath));
		return;
	}

	SetCheckpointSchedule({ 0.2 });
}

void ABpSanityFunctionalTest::OnCheckpoint(int32 /*CheckpointIndex*/, double /*TimeSeconds*/)
{
	const int32 Captured = LogCounter.IsValid() ? LogCounter->GetMatchCount() : -1;
	if (Captured == 1)
	{
		// "After that single message it should do nothing further and simply
		// remain in the world" (row 10). bSpawned only ever recorded that the
		// spawn SUCCEEDED, so a Blueprint that printed the token once and then
		// DestroyActor'd itself scored a clean PASS. Asked here, at the
		// checkpoint, through a weak pointer - so the answer is about the actor's
		// liveness and not about the fixture's own reference to it. Inside the
		// count-is-one branch, so the existing failure literal is still reached
		// on exactly the legs that were credited at it before.
		if (!SpawnedInstance.IsValid())
		{
			FinishTest(
				EFunctionalTestResult::Failed,
				TEXT("The BP_Announcer instance printed the message but did not remain in the "
					 "world; it was gone by the checkpoint (destroyed itself after announcing)."));
			return;
		}
		FinishTest(EFunctionalTestResult::Succeeded, TEXT(""));
	}
	else
	{
		FinishTest(
			EFunctionalTestResult::Failed,
			FString::Printf(
				TEXT("Expected exactly one LogBlueprintUserMessages emission containing "
					 "'CRAFTBENCH_BP_OK' during BP_Announcer's BeginPlay window; observed %d."),
				Captured));
	}
}

void ABpSanityFunctionalTest::RemoveLogDevice()
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

void ABpSanityFunctionalTest::EndPlay(const EEndPlayReason::Type EndPlayReason)
{
	RemoveLogDevice();
	if (WorldInitHandle.IsValid())
	{
		FWorldDelegates::OnWorldInitializedActors.Remove(WorldInitHandle);
		WorldInitHandle.Reset();
	}
	Super::EndPlay(EndPlayReason);
}
