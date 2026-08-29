// Copyright CraftBench. All Rights Reserved.
//
// VERIFIER-ONLY MODULE — DO NOT EDIT.
// See Source/CraftBenchTests/.AGENT_WRITE_DENY for the no-edit policy.
//
// ATagGateFunctionalTest — L2 verifier fixture for task t1-gameplay-tag-gate.
//
// The agent's actor (found by its "TagGateRoot" tag, never by class) must emit
// the exact line CRAFTBENCH_TAG_GATE_TICK on LogTemp/Display once per 0.5 s
// while the state marker CraftBench.TagGate.Active is present, stop while it is
// absent, and resume when it returns. THIS fixture drives the marker:
//
//   1. Installs a GLog listener from OnWorldInitializedActors (pre-BeginPlay,
//      so an emission in the BeginPlay window itself is counted), filtered to
//      LogTemp at Display-or-louder, substring CRAFTBENCH_TAG_GATE_TICK.
//   2. PrepareTest() resolves the host by tag, resolves the marker, validates
//      the two accessor UFUNCTIONs exist with the declared single-marker
//      signature, and schedules checkpoints at world-time { 1.8, 3.6, 5.4 }.
//   3. cp0 (t=1.8): asserts 3-4 emissions (marker present since gameplay
//      start), then REMOVES the marker via the actor's RemoveGateTag accessor
//      (reflection call by name — never the agent's class type).
//   4. cp1 (t=3.6): asserts ZERO new emissions since the removal, then re-adds
//      the marker via AddGateTag.
//   5. cp2 (t=5.4): asserts 2-4 new emissions since the re-add, then succeeds.
//
// Checkpoint times sit mid-interval (x.8 / x.6 against a 0.5 s period) so no
// legitimate implementation races a checkpoint against a scheduled emission.
// All failure strings are ASCII-only and each meaningful literal is ONE piece
// (the discrimination matrix greps them verbatim).

#pragma once

#include "CoreMinimal.h"
#include "CraftBenchFunctionalTest.h"
#include "GameplayTagContainer.h"
#include "Misc/OutputDevice.h"
#include "TagGateFunctionalTest.generated.h"

/**
 * Counts log entries whose serialized text contains a configured substring on a
 * configured category/verbosity. Mirrors FBpTokenCounterDevice; kept local so
 * this fixture is self-contained.
 */
class FTagGateTickCounterDevice : public FOutputDevice
{
public:
	FTagGateTickCounterDevice(const FString& InSubstring, const FName InCategory, ELogVerbosity::Type InMinVerbosity)
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
class CRAFTBENCHTESTS_API ATagGateFunctionalTest : public ACraftBenchFunctionalTest
{
	GENERATED_BODY()

public:
	ATagGateFunctionalTest(const FObjectInitializer& ObjectInitializer);

	virtual void PrepareTest() override;
	virtual void EndPlay(const EEndPlayReason::Type EndPlayReason) override;

protected:
	virtual void OnCheckpoint(int32 CheckpointIndex, double TimeSeconds) override;

private:
	/** Installs the GLog listener once, in this world, before any BeginPlay. */
	void OnWorldActorsInitialized(const FActorsInitializedParams& Params);
	void InstallLogDevice();
	void RemoveLogDevice();

	/** Finds the named accessor UFUNCTION on the host and validates the
	 *  declared single-marker parameter layout. On failure, FinishTest()s with
	 *  a named message and returns false. Reflection-only: this fixture never
	 *  needs (or names) the agent's class type. */
	bool ResolveAccessor(AActor* Host, const TCHAR* FunctionName, UFunction*& OutFunction);

	/** ResolveAccessor + ProcessEvent with the gate marker as the one param. */
	bool InvokeMarkerAccessor(AActor* Host, const TCHAR* FunctionName);

	TUniquePtr<FTagGateTickCounterDevice> LogCounter;
	FDelegateHandle WorldInitHandle;
	bool bDeviceInstalled = false;

	TWeakObjectPtr<AActor> HostActor;
	FGameplayTag GateTag;

	/** Match count snapshotted right after the cp0 marker removal. */
	int32 StopBaseline = 0;
	/** Match count snapshotted right after the cp1 marker re-add. */
	int32 ResumeBaseline = 0;
};
