// Copyright CraftBench. All Rights Reserved.
//
// VERIFIER-ONLY MODULE — DO NOT EDIT.
// See Source/CraftBenchTests/.AGENT_WRITE_DENY for the no-edit policy.
//
// ABpSanityFunctionalTest — L2 verifier fixture for task t0-sanity-bp-log-on-beginplay.
//
// This is the Blueprint-authoring counterpart to ASanityFunctionalTest. The agent
// authors a NEW Actor Blueprint at the KNOWN path /Game/Tasks/t0-sanity-bp-log-on-beginplay/BP_Announcer
// (named in the task prompt) whose BeginPlay prints "CRAFTBENCH_BP_OK". The agent
// cannot place it (the verifier map is deny-listed), so THIS fixture:
//
//   1. Installs a GLog listener in the ctor/world-init, filtering the exact token
//      on LogBlueprintUserMessages/Log (the channel Print String logs to).
//   2. PrepareTest() loads the class by path via StaticLoadClass and SpawnActor()s
//      one instance. Spawning a HasBegunPlay world dispatches BeginPlay immediately,
//      so the token (if any) is captured. If no asset exists at the path (empty or
//      C++-only submission), it FAILs with a named message.
//   3. At a checkpoint the fixture asserts the token was observed EXACTLY ONCE.
//
// No asset scan, no tags — the deliverable path is fixed by the prompt.

#pragma once

#include "CoreMinimal.h"
#include "CraftBenchFunctionalTest.h"
#include "Misc/OutputDevice.h"
#include "BpSanityFunctionalTest.generated.h"

/**
 * Counts log entries whose serialized text contains a configured substring on a
 * configured category/verbosity. Mirrors FSanitySubstringCounterDevice; kept local
 * so this fixture is self-contained for hash-pinning.
 */
class FBpTokenCounterDevice : public FOutputDevice
{
public:
	FBpTokenCounterDevice(const FString& InSubstring, const FName InCategory, ELogVerbosity::Type InMinVerbosity)
		: Substring(InSubstring)
		, Category(InCategory)
		, MinVerbosity(InMinVerbosity)
		, MatchCount(0)
	{
	}

	virtual void Serialize(const TCHAR* V, ELogVerbosity::Type Verbosity, const FName& InCategory) override;

	int32 GetMatchCount() const { return MatchCount; }

private:
	FString Substring;
	FName Category;
	ELogVerbosity::Type MinVerbosity;
	int32 MatchCount;
};

struct FActorsInitializedParams;

UCLASS()
class CRAFTBENCHTESTS_API ABpSanityFunctionalTest : public ACraftBenchFunctionalTest
{
	GENERATED_BODY()

public:
	ABpSanityFunctionalTest(const FObjectInitializer& ObjectInitializer);

	virtual void PrepareTest() override;
	virtual void EndPlay(const EEndPlayReason::Type EndPlayReason) override;

protected:
	virtual void OnCheckpoint(int32 CheckpointIndex, double TimeSeconds) override;

private:
	/** Installs the GLog listener once, in this world, before any spawn/BeginPlay. */
	void OnWorldActorsInitialized(const FActorsInitializedParams& Params);
	void RemoveLogDevice();

	TUniquePtr<FBpTokenCounterDevice> LogCounter;
	FDelegateHandle WorldInitHandle;
	bool bDeviceInstalled = false;
	bool bSpawned = false;

	/**
	 * The spawned BP_Announcer instance, held WEAKLY so the fixture can ask at
	 * the checkpoint whether it is still there (requirements table row 10, "it
	 * should simply remain in the world", closed 2026-08-19).
	 *
	 * Weak is the whole point: a raw pointer would keep the actor reachable and
	 * a Destroy()ed actor would still look present, which is exactly the
	 * observation this is meant to make.
	 */
	TWeakObjectPtr<AActor> SpawnedInstance;
};
