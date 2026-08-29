// Copyright CraftBench. All Rights Reserved.
//
// VERIFIER-ONLY MODULE — DO NOT EDIT.
// See Source/CraftBenchTests/.AGENT_WRITE_DENY for the no-edit policy.
//
// ASanityFunctionalTest implementation. PIE-native (see header). The base
// (ACraftBenchFunctionalTest) owns the PIE lever, fixed-timestep, and the
// checkpoint clock; this fixture owns only the pre-BeginPlay GLog listener.

#include "SanityFunctionalTest.h"

#include "CoreGlobals.h"
#include "Engine/World.h"
#include "Kismet/GameplayStatics.h"

namespace
{
	static const FName SanityRootTag(TEXT("SanityRoot"));
	static const FName LogTempCategoryName(TEXT("LogTemp"));
	static const TCHAR* SanitySubstring = TEXT("CRAFTBENCH_SANITY_OK");

	// How many frames after the listener went in the emission may land and still
	// count as "on the first frame of play" (requirements table row 5).
	//
	// ONE, not zero, and the slack is deliberate. The listener is installed from
	// UWorld::InitializeActorsForPlay and placed-actor BeginPlay runs from
	// UWorld::BeginPlay, which PIE calls in the same StartPlayInEditorGameInstance
	// call stack — so a correct solution is expected at delta 0. The extra frame
	// costs nothing real and protects against an engine-side reordering that would
	// otherwise turn correct work into a FAIL, which is the one error this repo
	// must never make. It is still SIX times tighter than the 0.1s checkpoint the
	// row was previously bounded by (~6 frames at the runner's -FPS=60), and the
	// routes it now rejects are the deferred ones: a 0.05s BeginPlay timer lands
	// at delta ~3, a Tick-based emission later still.
	//
	// Measured on the committed reference before this was trusted: delta 0.
	constexpr uint64 MaxBeginPlayFrameDelta = 1;
}

void FSanitySubstringCounterDevice::Serialize(const TCHAR* V, ELogVerbosity::Type Verbosity, const FName& InCategory)
{
	if (V == nullptr)
	{
		return;
	}
	// Category filter: only the configured channel counts. Agents that emit
	// to a different category (e.g. LogActor) to "hide" the substring fail.
	if (InCategory != Category)
	{
		return;
	}
	// Verbosity filter: anything quieter than the configured floor is ignored.
	const ELogVerbosity::Type EffectiveVerbosity = static_cast<ELogVerbosity::Type>(Verbosity & ELogVerbosity::VerbosityMask);
	if (EffectiveVerbosity > MinVerbosity)
	{
		return;
	}
	if (FCString::Strstr(V, *Substring) != nullptr)
	{
		if (MatchCount == 0)
		{
			FirstMatchFrame = GFrameCounter;
			FirstMatchText = V;
		}
		++MatchCount;
		// "the EXACT log line" (row 1). The Strstr above is a CONTAINS test, so
		// `prefix CRAFTBENCH_SANITY_OK suffix` satisfied it and the prompt asks for
		// the literal alone. Trimmed, because leading/trailing whitespace is a
		// formatting artifact of how a line was assembled and not a different line;
		// case-sensitive, matching the Strstr it refines.
		if (FString(V).TrimStartAndEnd().Equals(Substring, ESearchCase::CaseSensitive))
		{
			++ExactMatchCount;
		}
	}
}

ASanityFunctionalTest::ASanityFunctionalTest(const FObjectInitializer& ObjectInitializer)
	: Super(ObjectInitializer)
{
	// Register the CALLBACK early; the GLog device is only installed inside it,
	// after PostInitializeComponents and before placed-actor BeginPlay — so a
	// CDO/construction-time UE_LOG is never counted (anti-gaming case #3).
	WorldInitHandle = FWorldDelegates::OnWorldInitializedActors.AddUObject(
		this, &ASanityFunctionalTest::OnWorldActorsInitialized);
}

void ASanityFunctionalTest::OnWorldActorsInitialized(const FActorsInitializedParams& Params)
{
	// Single-shot, and only for OUR PIE world (ignore other editor/PIE/sublevel worlds).
	if (bDeviceInstalled || Params.World != GetWorld())
	{
		return;
	}
	// The zero of the first-frame gate, stamped before the listener can see
	// anything — so no emission it counts can predate the reference point.
	WorldInitFrame = GFrameCounter;
	LogCounter = MakeUnique<FSanitySubstringCounterDevice>(
		FString(SanitySubstring), LogTempCategoryName, ELogVerbosity::Display);
	if (GLog != nullptr)
	{
		GLog->AddOutputDevice(LogCounter.Get());
		bDeviceInstalled = true;
	}
}

void ASanityFunctionalTest::PrepareTest()
{
	Super::PrepareTest();  // base: snapshot FApp globals + set fixed dt (1/60)

	UWorld* World = GetWorld();
	if (World == nullptr)
	{
		FinishTest(EFunctionalTestResult::Error, TEXT("PrepareTest: no UWorld available"));
		return;
	}

	TArray<AActor*> Found;
	UGameplayStatics::GetAllActorsWithTag(World, SanityRootTag, Found);
	if (Found.Num() != 1)
	{
		FinishTest(
			EFunctionalTestResult::Failed,
			FString::Printf(TEXT("Expected exactly one actor tagged 'SanityRoot' in the test level; found %d."), Found.Num()));
		return;
	}

	// One tick past StartTest; BeginPlay (and its log) has already fired by now.
	SetCheckpointSchedule({ 0.1 });
}

void ASanityFunctionalTest::OnCheckpoint(int32 /*CheckpointIndex*/, double /*TimeSeconds*/)
{
	const int32 Captured = LogCounter.IsValid() ? LogCounter->GetMatchCount() : -1;
	if (Captured == 1)
	{
		// ONE emission was counted. The three gates below refine WHICH line it was,
		// WHEN it happened, and whether the actor survived saying it — clauses the
		// count alone never constrained. They run only on the count-is-one path so
		// every previously-credited failure literal above/below is reached exactly
		// as before; a new gate must not change which message an existing
		// discrimination leg is credited at.
		const int32 ExactMatches = LogCounter->GetExactMatchCount();
		const uint64 MatchFrame = LogCounter->GetFirstMatchFrame();
		const int64 FrameDelta = static_cast<int64>(MatchFrame) - static_cast<int64>(WorldInitFrame);

		// Advisory breadcrumb: the measured frame delta on a PASS, so the slack in
		// MaxBeginPlayFrameDelta stays a measured quantity rather than a remembered
		// one. Never read by the verdict.
		UE_LOG(LogTemp, Display, TEXT("[CB-SANITY] init_frame=%llu match_frame=%llu delta=%lld exact=%d"),
			WorldInitFrame, MatchFrame, FrameDelta, ExactMatches);

		// (1) "the exact log line CRAFTBENCH_SANITY_OK" — the literal alone.
		if (ExactMatches != 1)
		{
			FinishTest(
				EFunctionalTestResult::Failed,
				FString::Printf(
					TEXT("Expected the exact log line 'CRAFTBENCH_SANITY_OK'; the one LogTemp/Display emission in the BeginPlay window merely CONTAINS it: \"%s\"."),
					*LogCounter->GetFirstMatchText()));
			return;
		}

		// (5) "on the first frame of play" — see MaxBeginPlayFrameDelta.
		if (FrameDelta < 0 || static_cast<uint64>(FrameDelta) > MaxBeginPlayFrameDelta)
		{
			FinishTest(
				EFunctionalTestResult::Failed,
				FString::Printf(
					TEXT("Expected the emission on the first frame of play; it arrived %lld frame(s) after the world initialized its actors (limit %llu) - a deferred emission, not a BeginPlay one."),
					FrameDelta, MaxBeginPlayFrameDelta));
			return;
		}

		// (7) "the actor should otherwise remain in the world" — re-resolved HERE,
		// not just at PrepareTest. The PrepareTest gate catches only a Destroy()
		// inside BeginPlay (which is why `logs-then-destroys-self/` fails there);
		// a destruction deferred by even a 0.05s timer was previously unobserved,
		// because nothing looked at the tag a second time.
		UWorld* World = GetWorld();
		TArray<AActor*> StillThere;
		if (World != nullptr)
		{
			UGameplayStatics::GetAllActorsWithTag(World, SanityRootTag, StillThere);
		}
		if (StillThere.Num() != 1)
		{
			FinishTest(
				EFunctionalTestResult::Failed,
				FString::Printf(
					TEXT("Expected the actor tagged 'SanityRoot' to still be in the world at the checkpoint; found %d. It logged correctly and then removed itself."),
					StillThere.Num()));
			return;
		}

		FinishTest(EFunctionalTestResult::Succeeded, TEXT(""));
	}
	// Message-only literal split (2026-08-17): one Failed literal per failure
	// reason. The pass predicate (Captured == 1) and every verdict are unchanged
	// - the branches below only pick which message prints.
	else if (Captured == 0)
	{
		FinishTest(
			EFunctionalTestResult::Failed,
			TEXT("Expected exactly one LogTemp/Display emission containing 'CRAFTBENCH_SANITY_OK' in the BeginPlay window; observed none."));
	}
	else if (Captured > 1)
	{
		FinishTest(
			EFunctionalTestResult::Failed,
			FString::Printf(
				TEXT("Expected exactly one LogTemp/Display emission containing 'CRAFTBENCH_SANITY_OK' in the BeginPlay window; observed %d (more than one)."),
				Captured));
	}
	else
	{
		// Captured < 0: the log listener was never installed - a verifier-side
		// fault, named verbatim so a human never credits it as an agent defect.
		// Verdict unchanged (still Failed, message-only split); routing this to
		// the Error channel would move a verdict and needs its own review.
		FinishTest(
			EFunctionalTestResult::Failed,
			TEXT("Expected exactly one LogTemp/Display emission containing 'CRAFTBENCH_SANITY_OK' in the BeginPlay window; the log listener was never installed (count unavailable) - verifier-side fault to investigate, not an agent defect."));
	}
}

void ASanityFunctionalTest::RemoveLogDevice()
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

void ASanityFunctionalTest::EndPlay(const EEndPlayReason::Type EndPlayReason)
{
	// Tear down listener + global delegate BEFORE the base restores FApp globals.
	RemoveLogDevice();
	if (WorldInitHandle.IsValid())
	{
		FWorldDelegates::OnWorldInitializedActors.Remove(WorldInitHandle);
		WorldInitHandle.Reset();
	}
	Super::EndPlay(EndPlayReason);
}
