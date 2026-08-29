// Copyright CraftBench. All Rights Reserved.
//
// VERIFIER-ONLY MODULE — DO NOT EDIT.
// See Source/CraftBenchTests/.AGENT_WRITE_DENY for the no-edit policy.
//
// AExtractionVolumeFunctionalTest — L2 verifier fixture for task
// t1-extraction-volume-per-actor-trigger. PIE-native (see
// ACraftBenchFunctionalTest). Combines the proven GLog substring listener
// (installed in OnWorldInitializedActors, before placed-actor BeginPlay, so a
// constructor/BeginPlay-time log is caught) with TWO fixture-owned probe
// actors moved in and out of the zone — the headless stand-in for two distinct
// individuals reaching the extraction point.
//
//   checkpoint 0 (~0.5 s): assert the marker has NOT been logged yet (the zone
//                          must stay silent until something enters), then move
//                          probe A into the zone;
//   checkpoint 1 (~1.5 s): assert exactly one emission (first entrant), then
//                          move A OUT of the zone;
//   checkpoint 2 (~2.0 s): no graded assert — move A back IN. The exit and the
//                          re-entry live on separate checkpoints (~30 fixed
//                          frames apart) so the engine can never coalesce the
//                          round trip into "no overlap state change", which
//                          would silently un-test the re-entry dedupe;
//   checkpoint 3 (~2.5 s): assert STILL exactly one emission (per-individual
//                          dedupe), then move probe B into the zone;
//   checkpoint 4 (~3.5 s): assert exactly two emissions (one per distinct
//                          individual).

#pragma once

#include "CoreMinimal.h"
#include "CraftBenchFunctionalTest.h"
#include "Misc/OutputDevice.h"
#include "ExtractionVolumeFunctionalTest.generated.h"

/**
 * Counts log entries whose serialized text contains a configured substring on a
 * configured category/verbosity floor. Mirrors the t0/overlap-log counter — the
 * category + verbosity filter means emitting the marker on a different channel
 * to "hide" it still fails.
 */
class FExtractionLogCounterDevice : public FOutputDevice
{
public:
	FExtractionLogCounterDevice(const FString& InSubstring, const FName InCategory, ELogVerbosity::Type InMinVerbosity)
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
class CRAFTBENCHTESTS_API AExtractionVolumeFunctionalTest : public ACraftBenchFunctionalTest
{
	GENERATED_BODY()

public:
	AExtractionVolumeFunctionalTest(const FObjectInitializer& ObjectInitializer);

	virtual void PrepareTest() override;
	virtual void EndPlay(const EEndPlayReason::Type EndPlayReason) override;

protected:
	virtual void OnCheckpoint(int32 CheckpointIndex, double TimeSeconds) override;

private:
	/** Installs the GLog listener once, in this world, before placed-actor BeginPlay. */
	void OnWorldActorsInitialized(const FActorsInitializedParams& Params);
	void RemoveLogDevice();

	/** Spawns one probe actor (query-only overlap sphere root) at Location. */
	AActor* SpawnProbe(const TCHAR* DebugName, const FVector& Location);

	/** Teleports a probe and forces a synchronous overlap update so the zone's
	 *  begin/end-overlap events fire deterministically this frame. */
	bool MoveProbe(AActor* Probe, const FVector& Location);

	UPROPERTY()
	TObjectPtr<AActor> Host = nullptr;
	UPROPERTY()
	TObjectPtr<AActor> ProbeA = nullptr;
	UPROPERTY()
	TObjectPtr<AActor> ProbeB = nullptr;

	/** Inside-the-zone target points (slightly apart so both probes fit). */
	FVector EntryPointA = FVector::ZeroVector;
	FVector EntryPointB = FVector::ZeroVector;
	/** Well-outside-the-zone parking spots the probes start at / exit to. */
	FVector ParkingA = FVector::ZeroVector;
	FVector ParkingB = FVector::ZeroVector;

	TUniquePtr<FExtractionLogCounterDevice> LogCounter;
	FDelegateHandle WorldInitHandle;
	bool bDeviceInstalled = false;
};
