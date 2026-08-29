// Copyright CraftBench. All Rights Reserved.
//
// VERIFIER-ONLY MODULE — DO NOT EDIT.
// See Source/CraftBenchTests/.AGENT_WRITE_DENY for the no-edit policy.
//
// ASanityFunctionalTest — L2 verifier fixture for task t0-sanity-log-on-beginplay.
// PIE-native: the placed actor's BeginPlay AUTO-FIRES at PIE world start, before
// AFunctionalTest::PrepareTest. To capture the BeginPlay-window log, the GLog
// listener is installed in the FWorldDelegates::OnWorldInitializedActors callback
// — which fires after PostInitializeComponents but BEFORE placed-actor BeginPlay,
// so a constructor/CDO-time log is never counted (anti-gaming case #3). At a
// checkpoint one tick past StartTest the fixture asserts the substring
// "CRAFTBENCH_SANITY_OK" appeared on LogTemp/Display exactly once.
//
// NAMING RECONCILIATION: the task spec's "FSanityFunctionalTest" is the concept;
// the C++ type is ASanityFunctionalTest (AFunctionalTest derives from AActor, so
// the "A" prefix is required).

#pragma once

#include "CoreMinimal.h"
#include "CraftBenchFunctionalTest.h"
#include "Misc/OutputDevice.h"
#include "SanityFunctionalTest.generated.h"

/**
 * Custom FOutputDevice that counts log entries whose serialized text contains
 * a configured substring on a configured category/verbosity. Anti-gaming core —
 * keep byte-identical.
 *
 * It records three things about the matches, not one. The COUNT was all this
 * device ever kept, and two of the prompt's clauses are therefore about
 * quantities it never measured (requirements table rows 1 and 5, both closed
 * 2026-08-19): "the *exact* log line" is not the same claim as "a line
 * containing it", and "on the first frame of play" is not the same claim as
 * "before the 0.1s checkpoint". Both are observations made HERE, at emission
 * time, because by the time the checkpoint reads the count the evidence of
 * WHICH line and WHEN is gone.
 */
class FSanitySubstringCounterDevice : public FOutputDevice
{
public:
	FSanitySubstringCounterDevice(const FString& InSubstring, const FName InCategory, ELogVerbosity::Type InMinVerbosity)
		: Substring(InSubstring)
		, Category(InCategory)
		, MinVerbosity(InMinVerbosity)
		, MatchCount(0)
		, ExactMatchCount(0)
		, FirstMatchFrame(0)
	{
	}

	virtual void Serialize(const TCHAR* V, ELogVerbosity::Type Verbosity, const FName& InCategory) override;

	int32 GetMatchCount() const { return MatchCount; }

	/** Of the counted matches, how many were the literal ALONE (trimmed equality). */
	int32 GetExactMatchCount() const { return ExactMatchCount; }

	/**
	 * GFrameCounter at the FIRST counted match; 0 when there was none.
	 *
	 * A frame counter, deliberately, rather than a world time. Serialize may run
	 * on any thread GLog was called from, where dereferencing a UWorld to ask it
	 * for GetTimeSeconds() is not safe — GFrameCounter is a plain global integer.
	 * It is also dt-independent, so the gate does not silently change meaning
	 * when the runner's -FPS does.
	 */
	uint64 GetFirstMatchFrame() const { return FirstMatchFrame; }

	/** The FIRST counted match verbatim, so an inexact-line failure can name it. */
	const FString& GetFirstMatchText() const { return FirstMatchText; }

private:
	FString Substring;
	FName Category;
	ELogVerbosity::Type MinVerbosity;
	int32 MatchCount;
	int32 ExactMatchCount;
	uint64 FirstMatchFrame;
	FString FirstMatchText;
};

struct FActorsInitializedParams;

UCLASS()
class CRAFTBENCHTESTS_API ASanityFunctionalTest : public ACraftBenchFunctionalTest
{
	GENERATED_BODY()

public:
	ASanityFunctionalTest(const FObjectInitializer& ObjectInitializer);

	virtual void PrepareTest() override;
	virtual void EndPlay(const EEndPlayReason::Type EndPlayReason) override;

protected:
	virtual void OnCheckpoint(int32 CheckpointIndex, double TimeSeconds) override;

private:
	/** Installs the GLog listener once, in this world, before placed-actor BeginPlay. */
	void OnWorldActorsInitialized(const FActorsInitializedParams& Params);
	void RemoveLogDevice();

	/** Owned by this actor; installed in OnWorldActorsInitialized, removed in EndPlay. */
	TUniquePtr<FSanitySubstringCounterDevice> LogCounter;
	FDelegateHandle WorldInitHandle;
	bool bDeviceInstalled = false;

	/**
	 * GFrameCounter at the instant the listener went in — i.e. after
	 * PostInitializeComponents and BEFORE any placed actor's BeginPlay. This is
	 * the ZERO of the "first frame of play" gate: the emission's frame is only
	 * meaningful as a delta from it, since GFrameCounter counts from editor
	 * startup and its absolute value says nothing about this PIE session.
	 */
	uint64 WorldInitFrame = 0;
};
