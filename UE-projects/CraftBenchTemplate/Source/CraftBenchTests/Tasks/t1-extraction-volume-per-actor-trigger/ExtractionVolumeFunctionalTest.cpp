// Copyright CraftBench. All Rights Reserved.
//
// VERIFIER-ONLY MODULE — DO NOT EDIT.
// See Source/CraftBenchTests/.AGENT_WRITE_DENY for the no-edit policy.
//
// AExtractionVolumeFunctionalTest implementation. PIE-native: no manual
// ticking, no manual DispatchBeginPlay. The base drives the checkpoint clock
// off the PIE world game-time; we install the log listener before BeginPlay,
// resolve the zone by tag, and walk two probe actors through an
// enter / re-enter / second-entrant sequence via teleport + forced overlap
// updates.

#include "ExtractionVolumeFunctionalTest.h"

#include "Components/SphereComponent.h"
#include "Engine/World.h"
#include "GameFramework/Actor.h"
#include "Kismet/GameplayStatics.h"

namespace
{
	static const FName ExtractionZoneTag(TEXT("ExtractionZone"));
	static const FName LogTempCategoryName(TEXT("LogTemp"));
	static const TCHAR* ExtractionSubstring = TEXT("CRAFTBENCH_EXTRACTION_OK");
}

void FExtractionLogCounterDevice::Serialize(const TCHAR* V, ELogVerbosity::Type Verbosity, const FName& InCategory)
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

AExtractionVolumeFunctionalTest::AExtractionVolumeFunctionalTest(const FObjectInitializer& ObjectInitializer)
	: Super(ObjectInitializer)
{
	// Register the callback early; the GLog device is installed inside it, after
	// PostInitializeComponents and before placed-actor BeginPlay — so a
	// construction/BeginPlay-time log is observed against the correct window.
	WorldInitHandle = FWorldDelegates::OnWorldInitializedActors.AddUObject(
		this, &AExtractionVolumeFunctionalTest::OnWorldActorsInitialized);
}

void AExtractionVolumeFunctionalTest::OnWorldActorsInitialized(const FActorsInitializedParams& Params)
{
	if (bDeviceInstalled || Params.World != GetWorld())
	{
		return;
	}
	LogCounter = MakeUnique<FExtractionLogCounterDevice>(
		FString(ExtractionSubstring), LogTempCategoryName, ELogVerbosity::Display);
	if (GLog != nullptr)
	{
		GLog->AddOutputDevice(LogCounter.Get());
		bDeviceInstalled = true;
	}
}

void AExtractionVolumeFunctionalTest::PrepareTest()
{
	Super::PrepareTest();  // base: snapshot FApp globals + set fixed dt

	UWorld* World = GetWorld();
	if (World == nullptr)
	{
		FinishTest(EFunctionalTestResult::Error, TEXT("PrepareTest: no UWorld available"));
		return;
	}

	// Identity by tag, not by class — the agent may subclass the zone actor.
	TArray<AActor*> Found;
	UGameplayStatics::GetAllActorsWithTag(World, ExtractionZoneTag, Found);
	if (Found.Num() != 1)
	{
		FinishTest(
			EFunctionalTestResult::Failed,
			FString::Printf(TEXT("Expected exactly one actor tagged 'ExtractionZone' in the test level; found %d."), Found.Num()));
		return;
	}

	Host = Found[0];

	// Entry points sit inside the zone's detection box (authored half-extent
	// 200x200x100), offset laterally so both probes fit without stacking.
	// Parking spots are far outside on +X so no probe overlaps anything at rest.
	const FVector ZoneCenter = Host->GetActorLocation();
	EntryPointA = ZoneCenter + FVector(0.0, -60.0, 0.0);
	EntryPointB = ZoneCenter + FVector(0.0, 60.0, 0.0);
	ParkingA = ZoneCenter + FVector(5000.0, -250.0, 0.0);
	ParkingB = ZoneCenter + FVector(5000.0, 250.0, 0.0);

	ProbeA = SpawnProbe(TEXT("ExtractionProbeA"), ParkingA);
	ProbeB = SpawnProbe(TEXT("ExtractionProbeB"), ParkingB);
	if (ProbeA == nullptr || ProbeB == nullptr)
	{
		FinishTest(EFunctionalTestResult::Failed, TEXT("PrepareTest: failed to spawn the entrant probe actors"));
		return;
	}

	// cp0 pre-entry silence check; cp1 first entrant (then A exits); cp2 A
	// re-enters on its own checkpoint (separate engine frames from the exit —
	// never a same-frame out-then-in the engine could coalesce); cp3
	// same-individual dedupe gate + B enters; cp4 second distinct entrant.
	SetCheckpointSchedule({ 0.5, 1.5, 2.0, 2.5, 3.5 });
}

AActor* AExtractionVolumeFunctionalTest::SpawnProbe(const TCHAR* DebugName, const FVector& Location)
{
	UWorld* World = GetWorld();
	if (World == nullptr)
	{
		return nullptr;
	}

	FActorSpawnParameters Params;
	Params.SpawnCollisionHandlingOverride = ESpawnActorCollisionHandlingMethod::AlwaysSpawn;

	AActor* Probe = World->SpawnActor<AActor>(AActor::StaticClass(), Location, FRotator::ZeroRotator, Params);
	if (Probe == nullptr)
	{
		return nullptr;
	}

	// Overlap-enabled sphere root so moving the probe into the zone overlaps
	// the zone's volume and fires its begin-overlap event — the headless
	// stand-in for an individual walking in.
	USphereComponent* ProbeSphere = NewObject<USphereComponent>(Probe, DebugName);
	Probe->SetRootComponent(ProbeSphere);
	ProbeSphere->InitSphereRadius(48.0f);
	ProbeSphere->SetCollisionEnabled(ECollisionEnabled::QueryOnly);
	ProbeSphere->SetCollisionObjectType(ECC_WorldDynamic);
	ProbeSphere->SetCollisionResponseToAllChannels(ECR_Overlap);
	ProbeSphere->SetGenerateOverlapEvents(true);
	// Position BEFORE registration: a rootless-spawned actor discards its spawn
	// transform, so a freshly-registered root at identity would exist at the
	// WORLD ORIGIN for the registration overlap update. Setting the location
	// first means the probe never exists anywhere but its parking spot.
	ProbeSphere->SetWorldLocation(Location);
	ProbeSphere->RegisterComponent();

	return Probe;
}

bool AExtractionVolumeFunctionalTest::MoveProbe(AActor* Probe, const FVector& Location)
{
	if (Probe == nullptr)
	{
		return false;
	}
	Probe->SetActorLocation(Location);
	// Force a synchronous overlap update so begin/end-overlap fire
	// deterministically this frame rather than waiting on physics movement.
	if (UPrimitiveComponent* Root = Cast<UPrimitiveComponent>(Probe->GetRootComponent()))
	{
		Root->UpdateOverlaps();
		return true;
	}
	return false;
}

void AExtractionVolumeFunctionalTest::OnCheckpoint(int32 CheckpointIndex, double TimeSeconds)
{
	// A missing GLog listener yields the -1 sentinel, which matches NO expected
	// count, so every checkpoint below reports it through its OWN named
	// ::Failed assertion. This is the idiom the sibling log fixtures already use
	// (SanityFunctionalTest, BpSanityFunctionalTest, GraphMathFunctionalTest).
	//
	// It replaces a standalone HARNESS-PRECONDITION ::Error gate (2026-08-14).
	// That gate was mis-tagged: the listener is installed from this fixture's own
	// FWorldDelegates::OnWorldInitializedActors binding, and the agent's
	// PostInitializeComponents can clear that delegate — deliberately, or by
	// calling Clear() where it meant Remove(Handle). So the condition was
	// submission-manufacturable, and once ::Error routes a run OUT of the graded
	// denominator, an ::Error here would have been a one-line opt-out. Folding it
	// into the named assertions removes the gate rather than relabelling it.
	const int32 Count = LogCounter.IsValid() ? LogCounter->GetMatchCount() : -1;

	switch (CheckpointIndex)
	{
		case 0:
		{
			// (1) silent until entered: the marker must NOT have been logged
			// before any entry (a BeginPlay/constructor-time log fails here).
			if (Count != 0)
			{
				FinishTest(
					EFunctionalTestResult::Failed,
					FString::Printf(
						TEXT("At t=%.2fs: expected the 'CRAFTBENCH_EXTRACTION_OK' marker to NOT be logged before any entry; observed %d emission(s)."),
						TimeSeconds, Count));
				return;
			}
			if (!MoveProbe(ProbeA, EntryPointA))
			{
				FinishTest(
					EFunctionalTestResult::Failed,
					FString::Printf(TEXT("At t=%.2fs: failed to move probe A into the zone."), TimeSeconds));
				return;
			}
			break;
		}
		case 1:
		{
			// (2) exactly one emission for the first entrant.
			if (Count != 1)
			{
				FinishTest(
					EFunctionalTestResult::Failed,
					FString::Printf(
						TEXT("At t=%.2fs: expected exactly one 'CRAFTBENCH_EXTRACTION_OK' emission after the first entrant; observed %d."),
						TimeSeconds, Count));
				return;
			}
			// Walk A OUT of the zone. The matching re-entry happens on the NEXT
			// checkpoint, a separate engine frame ~0.5s later — never a
			// same-frame out-then-in the engine could coalesce into no overlap
			// state change.
			if (!MoveProbe(ProbeA, ParkingA))
			{
				FinishTest(
					EFunctionalTestResult::Failed,
					FString::Printf(TEXT("At t=%.2fs: failed to move probe A out of the zone."), TimeSeconds));
				return;
			}
			break;
		}
		case 2:
		{
			// No graded count assert here — this checkpoint only performs A's
			// re-entry (a re-entry by the SAME individual, which must not add
			// an emission; cp3 grades that).
			if (!MoveProbe(ProbeA, EntryPointA))
			{
				FinishTest(
					EFunctionalTestResult::Failed,
					FString::Printf(TEXT("At t=%.2fs: failed to re-enter probe A into the zone."), TimeSeconds));
				return;
			}
			break;
		}
		case 3:
		{
			// (3) per-individual dedupe: A's re-entry added nothing.
			if (Count != 1)
			{
				FinishTest(
					EFunctionalTestResult::Failed,
					FString::Printf(
						TEXT("At t=%.2fs: expected the same individual re-entering to add no new emission (still exactly one); observed %d."),
						TimeSeconds, Count));
				return;
			}
			if (!MoveProbe(ProbeB, EntryPointB))
			{
				FinishTest(
					EFunctionalTestResult::Failed,
					FString::Printf(TEXT("At t=%.2fs: failed to move probe B into the zone."), TimeSeconds));
				return;
			}
			break;
		}
		case 4:
		{
			// (4) one emission per distinct individual.
			if (Count != 2)
			{
				FinishTest(
					EFunctionalTestResult::Failed,
					FString::Printf(
						TEXT("At t=%.2fs: expected exactly two 'CRAFTBENCH_EXTRACTION_OK' emissions after a second distinct individual entered; observed %d."),
						TimeSeconds, Count));
				return;
			}
			// Verified — the base finishes the test as success.
			break;
		}
		default:
			break;
	}
}

void AExtractionVolumeFunctionalTest::RemoveLogDevice()
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

void AExtractionVolumeFunctionalTest::EndPlay(const EEndPlayReason::Type EndPlayReason)
{
	RemoveLogDevice();
	if (WorldInitHandle.IsValid())
	{
		FWorldDelegates::OnWorldInitializedActors.Remove(WorldInitHandle);
		WorldInitHandle.Reset();
	}
	Super::EndPlay(EndPlayReason);
}
