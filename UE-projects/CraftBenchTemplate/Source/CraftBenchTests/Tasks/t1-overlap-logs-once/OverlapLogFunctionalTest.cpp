// Copyright CraftBench. All Rights Reserved.
//
// VERIFIER-ONLY MODULE — DO NOT EDIT.
// See Source/CraftBenchTests/.AGENT_WRITE_DENY for the no-edit policy.
//
// AOverlapLogFunctionalTest implementation. PIE-native: no manual ticking, no
// manual DispatchBeginPlay. The base drives the checkpoint clock off the PIE
// world game-time; we install the log listener before BeginPlay, resolve the
// host by tag, and at checkpoint 0 induce an overlap by spawning a probe.

#include "OverlapLogFunctionalTest.h"

#include "Components/SphereComponent.h"
#include "Engine/World.h"
#include "GameFramework/Actor.h"
#include "Kismet/GameplayStatics.h"

namespace
{
	static const FName OverlapLogRootTag(TEXT("OverlapLogRoot"));
	static const FName LogTempCategoryName(TEXT("LogTemp"));
	static const TCHAR* OverlapSubstring = TEXT("CRAFTBENCH_OVERLAP_OK");
}

void FOverlapLogCounterDevice::Serialize(const TCHAR* V, ELogVerbosity::Type Verbosity, const FName& InCategory)
{
	if (V == nullptr)
	{
		return;
	}
	// Category filter: only the configured channel counts (hiding the marker on
	// another category fails).
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
		++MatchCount;
	}
}

AOverlapLogFunctionalTest::AOverlapLogFunctionalTest(const FObjectInitializer& ObjectInitializer)
	: Super(ObjectInitializer)
{
	// Register the callback early; the GLog device is installed inside it, after
	// PostInitializeComponents and before placed-actor BeginPlay — so a
	// construction/BeginPlay-time log is observed against the correct window.
	WorldInitHandle = FWorldDelegates::OnWorldInitializedActors.AddUObject(
		this, &AOverlapLogFunctionalTest::OnWorldActorsInitialized);
}

void AOverlapLogFunctionalTest::OnWorldActorsInitialized(const FActorsInitializedParams& Params)
{
	if (bDeviceInstalled || Params.World != GetWorld())
	{
		return;
	}
	LogCounter = MakeUnique<FOverlapLogCounterDevice>(
		FString(OverlapSubstring), LogTempCategoryName, ELogVerbosity::Display);
	if (GLog != nullptr)
	{
		GLog->AddOutputDevice(LogCounter.Get());
		bDeviceInstalled = true;
	}
}

void AOverlapLogFunctionalTest::PrepareTest()
{
	Super::PrepareTest();  // base: snapshot FApp globals + set fixed dt (1/60)

	UWorld* World = GetWorld();
	if (World == nullptr)
	{
		FinishTest(EFunctionalTestResult::Error, TEXT("PrepareTest: no UWorld available"));
		return;
	}

	// Identity by tag, not by class — the agent may subclass the host actor.
	TArray<AActor*> Found;
	UGameplayStatics::GetAllActorsWithTag(World, OverlapLogRootTag, Found);
	if (Found.Num() != 1)
	{
		FinishTest(
			EFunctionalTestResult::Failed,
			FString::Printf(TEXT("Expected exactly one actor tagged 'OverlapLogRoot' in the test level; found %d."), Found.Num()));
		return;
	}

	Host = Found[0];

	// Sample BEFORE inducing the overlap (t=0.5, well past BeginPlay so the agent's
	// overlap binding is in place), then AFTER (t=2.0).
	SetCheckpointSchedule({ 0.5, 2.0 });
}

bool AOverlapLogFunctionalTest::InduceOverlap()
{
	UWorld* World = GetWorld();
	if (World == nullptr || Host == nullptr)
	{
		return false;
	}

	const FVector Target = Host->GetActorLocation();

	FActorSpawnParameters Params;
	Params.SpawnCollisionHandlingOverride = ESpawnActorCollisionHandlingMethod::AlwaysSpawn;

	AActor* Probe = World->SpawnActor<AActor>(AActor::StaticClass(), Target, FRotator::ZeroRotator, Params);
	if (Probe == nullptr)
	{
		return false;
	}

	// Overlap-enabled sphere root so the probe overlaps the host's volume and
	// fires the host's begin-overlap event — the headless stand-in for another
	// actor walking into it.
	USphereComponent* ProbeSphere = NewObject<USphereComponent>(Probe, TEXT("ProbeSphere"));
	Probe->SetRootComponent(ProbeSphere);
	ProbeSphere->InitSphereRadius(48.0f);
	ProbeSphere->SetCollisionEnabled(ECollisionEnabled::QueryOnly);
	ProbeSphere->SetCollisionObjectType(ECC_WorldDynamic);
	ProbeSphere->SetCollisionResponseToAllChannels(ECR_Overlap);
	ProbeSphere->SetGenerateOverlapEvents(true);
	ProbeSphere->RegisterComponent();

	// Place exactly on the host and force an overlap update so begin-overlap fires
	// deterministically this frame rather than waiting on physics movement.
	Probe->SetActorLocation(Target);
	ProbeSphere->UpdateOverlaps();

	return true;
}

void AOverlapLogFunctionalTest::OnCheckpoint(int32 CheckpointIndex, double TimeSeconds)
{
	switch (CheckpointIndex)
	{
		case 0:
		{
			// (1) silent until overlapped: the marker must NOT have been logged
			// before any overlap (a BeginPlay/constructor-time log fails here).
			const int32 Before = LogCounter.IsValid() ? LogCounter->GetMatchCount() : -1;
			// VERIFIER-FAULT SENTINEL, and it belongs HERE rather than at checkpoint 1
			// (moved 2026-08-16 after an adversarial review confirmed the cp1 copy was
			// unreachable dead code): an uninstalled counter reads -1, which satisfies
			// `Before != 0` below and ENDED the test with an agent-blaming message that a
			// MATRIX row credits as `logs-on-beginplay` evidence. So the one reachable
			// manifestation of a verifier fault was being scored against the model, which
			// is exactly what the split was written to prevent. Verdict unchanged (Failed
			// either way, message-only); routing it to the Error channel is Phase 0b and
			// is blocked anyway - l2_pie has no error channel (only l2_introspect does).
			if (Before < 0)
			{
				FinishTest(
					EFunctionalTestResult::Failed,
					FString::Printf(
						TEXT("At t=%.2fs: the 'CRAFTBENCH_OVERLAP_OK' log counter device was never installed (count unavailable) - verifier-side fault to investigate, not an agent emission before overlap."),
						TimeSeconds));
				return;
			}
			if (Before != 0)
			{
				FinishTest(
					EFunctionalTestResult::Failed,
					FString::Printf(
						TEXT("At t=%.2fs: expected the 'CRAFTBENCH_OVERLAP_OK' marker to NOT be logged before any overlap; observed %d emission(s)."),
						TimeSeconds, Before));
				return;
			}
			if (!InduceOverlap())
			{
				FinishTest(
					EFunctionalTestResult::Failed,
					FString::Printf(TEXT("At t=%.2fs: failed to spawn the overlap probe to induce a begin-overlap."), TimeSeconds));
				return;
			}
			break;
		}
		case 1:
		{
			// (2) logs exactly once on overlap. Message-only literal split
			// (2026-08-17): one Failed literal per failure reason; the After != 1
			// predicate and every verdict are unchanged - the branches below only
			// pick which message prints.
			const int32 After = LogCounter.IsValid() ? LogCounter->GetMatchCount() : -1;
			if (After < 0)
			{
				// UNREACHABLE BY CONSTRUCTION, kept as a defensive backstop: checkpoint 0
				// reads the same ternary and terminates the test when the counter is
				// invalid, so control never arrives here with After < 0. The reachable
				// sentinel is the cp0 one above - do not treat this copy as the
				// protection (an adversarial review caught exactly that mistake here
				// on 2026-08-16). Verdict unchanged either way.
				FinishTest(
					EFunctionalTestResult::Failed,
					FString::Printf(
						TEXT("At t=%.2fs: the 'CRAFTBENCH_OVERLAP_OK' log counter device was never installed (count unavailable) - verifier-side fault to investigate, not an agent re-emission."),
						TimeSeconds));
				return;
			}
			if (After == 0)
			{
				FinishTest(
					EFunctionalTestResult::Failed,
					FString::Printf(
						TEXT("At t=%.2fs: expected exactly one LogTemp/Display 'CRAFTBENCH_OVERLAP_OK' emission after one overlap; observed none - the marker never reached the LogTemp/Display-or-louder counter."),
						TimeSeconds));
				return;
			}
			if (After != 1)
			{
				FinishTest(
					EFunctionalTestResult::Failed,
					FString::Printf(
						TEXT("At t=%.2fs: expected exactly one LogTemp/Display 'CRAFTBENCH_OVERLAP_OK' emission after one overlap; observed %d - the marker was re-emitted after the single induced overlap."),
						TimeSeconds, After));
				return;
			}
			// Verified — the base finishes the test as success.
			break;
		}
		default:
			break;
	}
}

void AOverlapLogFunctionalTest::RemoveLogDevice()
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

void AOverlapLogFunctionalTest::EndPlay(const EEndPlayReason::Type EndPlayReason)
{
	RemoveLogDevice();
	if (WorldInitHandle.IsValid())
	{
		FWorldDelegates::OnWorldInitializedActors.Remove(WorldInitHandle);
		WorldInitHandle.Reset();
	}
	Super::EndPlay(EndPlayReason);
}
