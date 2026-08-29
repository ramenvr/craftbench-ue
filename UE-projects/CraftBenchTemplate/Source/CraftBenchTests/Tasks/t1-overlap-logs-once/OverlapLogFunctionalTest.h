// Copyright CraftBench. All Rights Reserved.
//
// VERIFIER-ONLY MODULE — DO NOT EDIT.
// See Source/CraftBenchTests/.AGENT_WRITE_DENY for the no-edit policy.
//
// AOverlapLogFunctionalTest — L2 verifier fixture for task t1-overlap-logs-once.
// PIE-native (see ACraftBenchFunctionalTest). Combines two proven substrate
// patterns: the t0 GLog substring listener (installed in
// OnWorldInitializedActors, before placed-actor BeginPlay, so a
// constructor/BeginPlay-time log is caught) and the harvestable overlap probe
// (a spawned sphere forced to overlap the host, the headless stand-in for
// another actor walking into it).
//
//   checkpoint 0 (~0.5 s): assert the marker has NOT been logged yet (the actor
//                          must stay silent until something overlaps it), then
//                          spawn a probe to induce a begin-overlap on the host;
//   checkpoint 1 (~2.0 s): assert the marker was logged exactly once.

#pragma once

#include "CoreMinimal.h"
#include "CraftBenchFunctionalTest.h"
#include "Misc/OutputDevice.h"
#include "OverlapLogFunctionalTest.generated.h"

/**
 * Counts log entries whose serialized text contains a configured substring on a
 * configured category/verbosity floor. Mirrors the t0 sanity counter — the
 * category + verbosity filter means emitting the marker on a different channel
 * to "hide" it still fails.
 */
class FOverlapLogCounterDevice : public FOutputDevice
{
public:
	FOverlapLogCounterDevice(const FString& InSubstring, const FName InCategory, ELogVerbosity::Type InMinVerbosity)
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
class CRAFTBENCHTESTS_API AOverlapLogFunctionalTest : public ACraftBenchFunctionalTest
{
	GENERATED_BODY()

public:
	AOverlapLogFunctionalTest(const FObjectInitializer& ObjectInitializer);

	virtual void PrepareTest() override;
	virtual void EndPlay(const EEndPlayReason::Type EndPlayReason) override;

protected:
	virtual void OnCheckpoint(int32 CheckpointIndex, double TimeSeconds) override;

private:
	/** Installs the GLog listener once, in this world, before placed-actor BeginPlay. */
	void OnWorldActorsInitialized(const FActorsInitializedParams& Params);
	void RemoveLogDevice();

	/** Spawns a probe with an overlap sphere on the host to fire its begin-overlap. */
	bool InduceOverlap();

	UPROPERTY()
	TObjectPtr<AActor> Host = nullptr;
	TUniquePtr<FOverlapLogCounterDevice> LogCounter;
	FDelegateHandle WorldInitHandle;
	bool bDeviceInstalled = false;
};
