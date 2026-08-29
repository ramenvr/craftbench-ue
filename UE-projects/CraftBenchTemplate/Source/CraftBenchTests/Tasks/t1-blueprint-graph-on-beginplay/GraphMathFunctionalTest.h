// Copyright CraftBench. All Rights Reserved.
//
// VERIFIER-ONLY MODULE — DO NOT EDIT.
// See Source/CraftBenchTests/.AGENT_WRITE_DENY for the no-edit policy.
//
// AGraphMathFunctionalTest — L2 verifier fixture for task
// t1-blueprint-graph-on-beginplay.
//
// The agent authors a NEW Actor Blueprint at the KNOWN path
// /Game/Tasks/t1-blueprint-graph-on-beginplay/BP_GraphMath (named in the task
// prompt), derived from AGraphMathActor, whose BeginPlay-window behavior reads
// the instance's two editable values and prints CRAFTBENCH_GRAPH_TOTAL=<sum>.
// The agent cannot place it (the verifier map is deny-listed), so THIS fixture:
//
//   1. In FWorldDelegates::OnWorldInitializedActors (the pre-BeginPlay hook):
//      installs a GLog listener filtering the marker on
//      LogBlueprintUserMessages/Log (the channel Print String uses), loads the
//      class by path, spawns one instance into the not-yet-begun world, and
//      OVERRIDES both editable values (BaseValue=137, BonusValue=42) BEFORE
//      BeginPlay is dispatched. A hardcoded print of the default-derived sum
//      (7+5=12) therefore FAILs the value gate: only a graph that actually
//      reads the instance's current values can print 179.
//   2. PrepareTest() converts any recorded setup failure (no asset at the
//      path, wrong parent class, spawn failure) into a NAMED FinishTest FAIL.
//      If the world-init delegate never fired (defensive fallback), it does
//      the same setup via SpawnActorDeferred so the value override still lands
//      before BeginPlay.
//   3. At one checkpoint the fixture asserts the exact expected line was
//      observed EXACTLY ONCE (and that no differently-valued marker lines were
//      emitted).
//
// No asset scan, no tag-based resolution — the deliverable path is fixed by
// the prompt (the t0-sanity-bp idiom).

#pragma once

#include "CoreMinimal.h"
#include "CraftBenchFunctionalTest.h"
#include "Misc/OutputDevice.h"
#include "GraphMathFunctionalTest.generated.h"

class AGraphMathActor;

/**
 * Counts log entries on a configured category/verbosity that (a) contain a
 * configured marker prefix and (b) exactly contain the full expected line.
 * Two counters so the checkpoint can distinguish "silent" from "wrong value"
 * from "printed more than once". Kept local so this fixture is self-contained.
 */
class FGraphMathTokenCounterDevice : public FOutputDevice
{
public:
	FGraphMathTokenCounterDevice(
		const FString& InMarkerPrefix,
		const FString& InExpectedLine,
		const FName InCategory,
		ELogVerbosity::Type InMinVerbosity)
		: MarkerPrefix(InMarkerPrefix)
		, ExpectedLine(InExpectedLine)
		, Category(InCategory)
		, MinVerbosity(InMinVerbosity)
		, PrefixCount(0)
		, ExactCount(0)
	{
	}

	virtual void Serialize(const TCHAR* V, ELogVerbosity::Type Verbosity, const FName& InCategory) override;

	int32 GetPrefixCount() const { return PrefixCount; }
	int32 GetExactCount() const { return ExactCount; }

private:
	FString MarkerPrefix;
	FString ExpectedLine;
	FName Category;
	ELogVerbosity::Type MinVerbosity;
	int32 PrefixCount;
	int32 ExactCount;
};

struct FActorsInitializedParams;

/** Outcome of the load/spawn/override setup, resolved pre-BeginPlay and
 *  reported as a NAMED FinishTest in PrepareTest. */
enum class EGraphMathSetupStatus : uint8
{
	NotAttempted,
	Ok,
	AssetMissing,
	WrongParent,
	SpawnFailed
};

UCLASS()
class CRAFTBENCHTESTS_API AGraphMathFunctionalTest : public ACraftBenchFunctionalTest
{
	GENERATED_BODY()

public:
	AGraphMathFunctionalTest(const FObjectInitializer& ObjectInitializer);

	virtual void PrepareTest() override;
	virtual void EndPlay(const EEndPlayReason::Type EndPlayReason) override;

protected:
	virtual void OnCheckpoint(int32 CheckpointIndex, double TimeSeconds) override;

private:
	/** Pre-BeginPlay hook: installs the GLog listener, then loads + spawns the
	 *  agent's Blueprint and overrides both editable values (world not yet
	 *  begun play, so BeginPlay dispatches later with the overrides in place). */
	void OnWorldActorsInitialized(const FActorsInitializedParams& Params);

	/** Installs the marker-counting GLog device once. */
	void InstallLogDevice();
	void RemoveLogDevice();

	/** Loads the class by its required path, spawns one instance, and sets the
	 *  two override values before BeginPlay can run on it. bWorldHasBegunPlay
	 *  selects plain spawn (pre-BeginPlay world) vs SpawnActorDeferred
	 *  (fallback inside an already-playing world). Records SetupStatus. */
	void SetupSubject(UWorld* World, bool bWorldHasBegunPlay);

	TUniquePtr<FGraphMathTokenCounterDevice> LogCounter;
	FDelegateHandle WorldInitHandle;
	bool bDeviceInstalled = false;
	bool bWorldInitHandled = false;
	EGraphMathSetupStatus SetupStatus = EGraphMathSetupStatus::NotAttempted;
	TWeakObjectPtr<AGraphMathActor> Subject;
};
