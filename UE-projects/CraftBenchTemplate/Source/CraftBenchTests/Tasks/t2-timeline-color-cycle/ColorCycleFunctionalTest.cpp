// Copyright CraftBench. All Rights Reserved.
//
// VERIFIER-ONLY MODULE — DO NOT EDIT.
// See Source/CraftBenchTests/.AGENT_WRITE_DENY for the no-edit policy.
//
// AColorCycleFunctionalTest implementation. PIE-native (see header). The base
// (ACraftBenchFunctionalTest) owns the PIE lever, fixed-timestep, and the
// checkpoint clock; this fixture owns actor resolution, the per-frame color
// trace, and the trace gates. All FAIL message text is ASCII-only (the
// cp1252 log read-back rule).

#include "ColorCycleFunctionalTest.h"

#include "Components/StaticMeshComponent.h"
#include "Engine/World.h"
#include "Kismet/GameplayStatics.h"
#include "Materials/MaterialInstanceDynamic.h"

namespace
{
	static const FName ColorCycleTag(TEXT("ColorCycle"));
	static const FName CycleColorParam(TEXT("CycleColor"));

	// Gate (1): the color must MOVE. Largest single-channel range across the
	// window under this floor = "never changes". The reference sweeps each
	// channel across its full 0..1 range every 6s cycle; a static color has
	// range 0.
	constexpr float KMinChannelRange = 0.2f;

	// Gate (2): smoothness cap, per fixed 60Hz frame. Blending along the
	// disclosed 6s cycle moves a channel at most 1.0 per 2s leg =
	// ~0.0083/frame; the cap is ~18x that. An instant snap between anchor
	// colors is a 1.0 jump. Derived FOR the spec's -FPS=60 leg (see notes.md
	// FPS-dependence).
	constexpr float KMaxFrameColorDelta = 0.15f;

	// Gates (3)-(5): dominant-channel classification margin. A sample is
	// "dominantly" G/B/R when that channel exceeds BOTH others by this margin;
	// blend midpoints (e.g. G=B=0.5) classify as no-dominant and are skipped,
	// so run transitions are anchor-to-anchor.
	constexpr float KDominantMargin = 0.15f;

	// Gate (4): period band on the median FULL dominant-run length. The
	// disclosed 6s cycle dominates each anchor for ~1.7s at full amplitude
	// (2.0s per anchor leg minus the 0.15-margin trim on both blend shoulders)
	// = ~102 samples at the fixed 60Hz step. Band [72, 192] samples
	// (1.2s..3.2s) keeps generous tolerance for amplitude/easing choices while
	// failing periods off by ~2x either way. Only runs fully INSIDE the
	// window count (the first and last runs are window-truncated). Derived
	// FOR the spec's -FPS=60 leg.
	constexpr int32 KMinMedianRunSamples = 72;
	constexpr int32 KMaxMedianRunSamples = 192;

	// Gate (5): minimum dominant-run transitions across the 9.0s trace
	// window. The disclosed 6s period yields a dominant run every ~2s ->
	// 4-5 transitions in 9s regardless of starting phase; a cycle that stops
	// partway leaves at most 2.
	constexpr int32 KMinTransitions = 3;

	// Dominant-channel labels.
	enum class EDominant : int8 { None = -1, Green = 0, Blue = 1, Red = 2 };

	EDominant ClassifyDominant(const FLinearColor& C)
	{
		if (C.G > C.B + KDominantMargin && C.G > C.R + KDominantMargin)
		{
			return EDominant::Green;
		}
		if (C.B > C.G + KDominantMargin && C.B > C.R + KDominantMargin)
		{
			return EDominant::Blue;
		}
		if (C.R > C.G + KDominantMargin && C.R > C.B + KDominantMargin)
		{
			return EDominant::Red;
		}
		return EDominant::None;
	}

	/** The disclosed cycle order green -> blue -> red -> green. */
	bool IsCyclicSuccessor(EDominant From, EDominant To)
	{
		return (From == EDominant::Green && To == EDominant::Blue)
			|| (From == EDominant::Blue && To == EDominant::Red)
			|| (From == EDominant::Red && To == EDominant::Green);
	}
}

AColorCycleFunctionalTest::AColorCycleFunctionalTest(const FObjectInitializer& ObjectInitializer)
	: Super(ObjectInitializer)
{
}

void AColorCycleFunctionalTest::PrepareTest()
{
	Super::PrepareTest();  // base: snapshot FApp globals + set fixed dt

	UWorld* World = GetWorld();
	if (World == nullptr)
	{
		FinishTest(EFunctionalTestResult::Error, TEXT("HARNESS-PRECONDITION: PrepareTest: no UWorld available"));
		return;
	}

	// Identity by tag, never by class — but the graded actor is a PLACED map
	// instance of the scaffold type: the agent edits that type in place; a
	// subclass never reaches the grade and a rename breaks the map reference.
	TArray<AActor*> Found;
	UGameplayStatics::GetAllActorsWithTag(World, ColorCycleTag, Found);
	if (Found.Num() != 1)
	{
		FinishTest(
			EFunctionalTestResult::Failed,
			FString::Printf(TEXT("Expected exactly one actor tagged 'ColorCycle' (the display actor) in the running level; found %d."), Found.Num()));
		return;
	}
	Display = Found[0];

	// cp0 t=1.0: the readable-parameter gate (generous for BeginPlay-time MID
	// creation); the trace window is cleared here so gates read exactly
	// cp0 -> cp1. cp1 t=10.0: the trace gates (window = 9.0s = 1.5 disclosed
	// cycles).
	SetCheckpointSchedule({ 1.0, 10.0 });
}

UMaterialInstanceDynamic* AColorCycleFunctionalTest::ResolveCycleMid() const
{
	if (!Display.IsValid())
	{
		return nullptr;
	}
	TArray<UStaticMeshComponent*> Meshes;
	Display->GetComponents<UStaticMeshComponent>(Meshes);
	for (UStaticMeshComponent* Mesh : Meshes)
	{
		for (int32 SlotIndex = 0; SlotIndex < Mesh->GetNumMaterials(); ++SlotIndex)
		{
			UMaterialInstanceDynamic* Mid = Cast<UMaterialInstanceDynamic>(Mesh->GetMaterial(SlotIndex));
			if (Mid == nullptr)
			{
				continue;
			}
			FLinearColor Value;
			if (Mid->GetVectorParameterValue(FMaterialParameterInfo(CycleColorParam), Value))
			{
				return Mid;
			}
		}
	}
	return nullptr;
}

void AColorCycleFunctionalTest::Tick(float DeltaSeconds)
{
	Super::Tick(DeltaSeconds);  // base runs the checkpoint clock first

	if (!IsRunning())
	{
		return;
	}

	// Fresh resolve every frame (no caching): the reference keeps one MID for
	// the whole run, but a solution that recreates its dynamic material
	// instance per tick still reads correctly — only the component's CURRENT
	// material matters.
	if (UMaterialInstanceDynamic* Mid = ResolveCycleMid())
	{
		FLinearColor Value;
		if (Mid->GetVectorParameterValue(FMaterialParameterInfo(CycleColorParam), Value))
		{
			Samples.Add(Value);
		}
	}
}

void AColorCycleFunctionalTest::OnCheckpoint(int32 CheckpointIndex, double TimeSeconds)
{
	if (!Display.IsValid())
	{
		FinishTest(
			EFunctionalTestResult::Failed,
			FString::Printf(TEXT("At checkpoint %d: the display actor is no longer valid (it must keep existing for the whole run)."), CheckpointIndex));
		return;
	}

	if (CheckpointIndex == 0)  // t=1.0 — the readable-parameter gate.
	{
		if (ResolveCycleMid() == nullptr)
		{
			FinishTest(
				EFunctionalTestResult::Failed,
				TEXT("Expected the display actor's current color to be readable one second into play; observed no readable CycleColor parameter on the actor's mesh material."));
			return;
		}
		// Trace window starts NOW — gates read exactly cp0 -> cp1.
		Samples.Reset();
		return;
	}

	// cp1 t=10.0 — the trace gates, evaluated readability -> movement ->
	// smoothness -> order -> period -> continuity so each gaming shape dies
	// at ITS named assertion.

	// (0) readability across the window — a trace too short to judge fails
	// cleanly instead of feeding sentinel values into the movement gate.
	if (Samples.Num() < 2)
	{
		FinishTest(
			EFunctionalTestResult::Failed,
			FString::Printf(TEXT("Expected the display color to stay readable for the whole run; observed no color samples could be read (%d samples across 9.0s)."),
				Samples.Num()));
		return;
	}

	float MaxFrameDelta = 0.f;
	FLinearColor MinC = Samples[0];
	FLinearColor MaxC = Samples[0];
	// Dominant runs with their lengths (in samples).
	TArray<EDominant> Runs;
	TArray<int32> RunLengths;
	for (int32 i = 0; i < Samples.Num(); ++i)
	{
		const FLinearColor& C = Samples[i];
		MinC.R = FMath::Min(MinC.R, C.R); MaxC.R = FMath::Max(MaxC.R, C.R);
		MinC.G = FMath::Min(MinC.G, C.G); MaxC.G = FMath::Max(MaxC.G, C.G);
		MinC.B = FMath::Min(MinC.B, C.B); MaxC.B = FMath::Max(MaxC.B, C.B);
		if (i > 0)
		{
			const FLinearColor& P = Samples[i - 1];
			const float FrameDelta = FMath::Max3(
				FMath::Abs(C.R - P.R), FMath::Abs(C.G - P.G), FMath::Abs(C.B - P.B));
			MaxFrameDelta = FMath::Max(MaxFrameDelta, FrameDelta);
		}
		const EDominant D = ClassifyDominant(C);
		if (D != EDominant::None)
		{
			if (Runs.Num() == 0 || Runs.Last() != D)
			{
				Runs.Add(D);
				RunLengths.Add(1);
			}
			else
			{
				++RunLengths.Last();
			}
		}
	}
	const float MaxChannelRange = FMath::Max3(
		MaxC.R - MinC.R, MaxC.G - MinC.G, MaxC.B - MinC.B);
	const int32 Transitions = FMath::Max(0, Runs.Num() - 1);

	// Median of the FULL (window-interior) runs — the first and last runs are
	// truncated by the window edges and carry no period information.
	int32 MedianRunSamples = -1;
	if (Runs.Num() >= 3)
	{
		TArray<int32> Interior(RunLengths.GetData() + 1, Runs.Num() - 2);
		Interior.Sort();
		MedianRunSamples = Interior[Interior.Num() / 2];
	}

	UE_LOG(LogTemp, Display,
		TEXT("[t2-colorcycle calib] cp%d t=%.2f samples=%d runs=%d transitions=%d maxdelta=%.4f range=%.3f medianrun=%d"),
		CheckpointIndex, TimeSeconds, Samples.Num(), Runs.Num(), Transitions,
		MaxFrameDelta, MaxChannelRange, MedianRunSamples);

	// (1) movement — a color that never moves fails here, not at the order
	// gates (a static green would otherwise also miss blue/red).
	if (MaxChannelRange < KMinChannelRange)
	{
		FinishTest(
			EFunctionalTestResult::Failed,
			FString::Printf(TEXT("Expected the display color to cycle continuously; observed the color never changes (largest channel range %.3f across 9.0s)."),
				MaxChannelRange));
		return;
	}

	// (2) smoothness — an instant anchor-to-anchor snap is a ~1.0 jump;
	// blending along the disclosed cycle moves ~0.008 per frame.
	if (MaxFrameDelta > KMaxFrameColorDelta)
	{
		FinishTest(
			EFunctionalTestResult::Failed,
			FString::Printf(TEXT("Expected gradual blending between colors; observed the color snaps instead of blending smoothly (a single-frame change of %.3f)."),
				MaxFrameDelta));
		return;
	}

	// (3) order — all three anchors, in the disclosed cyclic order.
	bool bSawGreen = false, bSawBlue = false, bSawRed = false;
	bool bOrderOk = true;
	for (int32 i = 0; i < Runs.Num(); ++i)
	{
		bSawGreen |= (Runs[i] == EDominant::Green);
		bSawBlue |= (Runs[i] == EDominant::Blue);
		bSawRed |= (Runs[i] == EDominant::Red);
		if (i > 0 && !IsCyclicSuccessor(Runs[i - 1], Runs[i]))
		{
			bOrderOk = false;
		}
	}
	if (!(bSawGreen && bSawBlue && bSawRed) || !bOrderOk)
	{
		FinishTest(
			EFunctionalTestResult::Failed,
			TEXT("Expected the color to visit green, then blue, then red, then green again; observed the color does not cycle through green, blue and red in order."));
		return;
	}

	// (4) period — the disclosed 6 seconds, judged from the median full
	// dominant-run length (skipped when no interior run exists; the
	// continuity gate below owns that case).
	if (MedianRunSamples >= 0
		&& (MedianRunSamples < KMinMedianRunSamples || MedianRunSamples > KMaxMedianRunSamples))
	{
		FinishTest(
			EFunctionalTestResult::Failed,
			FString::Printf(TEXT("Expected a full cycle every 6 seconds; observed the cycle period is far from the required six seconds (median dominant-run length %.2fs vs the expected ~1.7s per color)."),
				(double)MedianRunSamples / 60.0));
		return;
	}

	// (5) continuity — the cycle must keep going across the whole window.
	if (Transitions < KMinTransitions)
	{
		FinishTest(
			EFunctionalTestResult::Failed,
			FString::Printf(TEXT("Expected the cycle to continue for the whole run; observed the color stops cycling partway (%d color transitions in 9.0s, need at least %d)."),
				Transitions, KMinTransitions));
		return;
	}

	FinishTest(EFunctionalTestResult::Succeeded, TEXT(""));
}
