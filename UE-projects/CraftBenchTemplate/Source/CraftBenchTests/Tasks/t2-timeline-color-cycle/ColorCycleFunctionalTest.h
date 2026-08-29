// Copyright CraftBench. All Rights Reserved.
//
// VERIFIER-ONLY MODULE — DO NOT EDIT.
// See Source/CraftBenchTests/.AGENT_WRITE_DENY for the no-edit policy.
//
// AColorCycleFunctionalTest — L2 verifier fixture for task
// t2-timeline-color-cycle. Lives at
// Source/CraftBenchTests/Tasks/t2-timeline-color-cycle/. Placed in
// Content/Maps/t2-timeline-color-cycle/L_ColorCycle.umap alongside the
// "ColorCycle"-tagged display actor.
//
// PIE-native: the engine ticks this fixture. The fixture resolves the placed
// display actor by tag and reads its color through the prompt-disclosed
// contract: a vector parameter named "CycleColor" on a dynamic material
// instance of one of the actor's static-mesh components. Parameter
// ENUMERATION cannot discover an override-added name (spiked 2026-07-30:
// GetAllVectorParameterInfo does not surface overrides), so the disclosed
// name is the only read route — exactly why the prompt pins it. The MID is
// re-resolved EVERY frame, never cached: a solution that recreates its
// dynamic material instance per tick (visually fine) must not leave the
// fixture reading a stale, orphaned instance.
//
// The judge is a per-frame color TRACE, not spot checks: every simulated
// frame between cp0 (t=1.0) and cp1 (t=10.0) appends the current CycleColor
// value to a sample array (~540 samples at the fixed 60Hz step). At cp1 the
// gates read the trace, in order:
//   (0) readability — a zero/one-sample trace fails cleanly;
//   (1) movement    — the color must actually change over the window;
//   (2) smoothness  — max single-frame component delta stays under a cap
//                     (~18x the reference's real rate; an instant snap is 1.0);
//   (3) order       — collapsing samples to dominant-channel runs (with a
//                     no-dominant dead zone for blend midpoints) must visit
//                     all three anchors and every transition must follow the
//                     cyclic order G->B, B->R, R->G;
//   (4) period      — the median FULL (window-interior) dominant-run length
//                     must sit in a band around the disclosed period's
//                     per-anchor share (a 6s cycle dominates each anchor for
//                     ~1.7s after the dominance-margin trim);
//   (5) continuity  — at least 3 dominant-run transitions across the 9s
//                     window (a 6s period yields 4-5), so a cycle that stops
//                     partway fails.
// All gates are phase-agnostic (no dependence on where in the cycle BeginPlay
// happened to land). All FAIL text is ASCII-only (cp1252 log read-back rule).
// The FinishTest(Error) precondition path carries "HARNESS-PRECONDITION: " —
// today it still GRADES as FAIL; the prefix is the future routing hook.

#pragma once

#include "CoreMinimal.h"
#include "CraftBenchFunctionalTest.h"
#include "ColorCycleFunctionalTest.generated.h"

class UMaterialInstanceDynamic;
class UStaticMeshComponent;

UCLASS()
class CRAFTBENCHTESTS_API AColorCycleFunctionalTest : public ACraftBenchFunctionalTest
{
	GENERATED_BODY()

public:
	AColorCycleFunctionalTest(const FObjectInitializer& ObjectInitializer);

	virtual void PrepareTest() override;

	/** Chains the base checkpoint clock, then samples CycleColor once per
	 *  simulated frame (the readable MID is re-resolved every frame — never
	 *  cached — so per-tick MID recreation by the solution still reads).
	 *  Never ticks the world. */
	virtual void Tick(float DeltaSeconds) override;

protected:
	virtual void OnCheckpoint(int32 CheckpointIndex, double TimeSeconds) override;

private:
	/** Walk the display actor's static-mesh components for the first one
	 *  whose material carries a READABLE "CycleColor" vector parameter on a
	 *  dynamic material instance. Fresh walk every call — no caching. */
	UMaterialInstanceDynamic* ResolveCycleMid() const;

	TWeakObjectPtr<AActor> Display;

	/** Per-frame CycleColor trace across the cp0->cp1 window. */
	TArray<FLinearColor> Samples;
};
