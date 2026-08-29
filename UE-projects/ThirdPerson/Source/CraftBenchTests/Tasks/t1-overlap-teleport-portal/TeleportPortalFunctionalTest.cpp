// Copyright CraftBench. All Rights Reserved.
//
// VERIFIER-ONLY MODULE — DO NOT EDIT.
// See Source/CraftBenchTests/.AGENT_WRITE_DENY for the no-edit policy.
//
// ATeleportPortalFunctionalTest implementation. PIE-native (see header). The
// base (ACraftBenchFunctionalTest) owns the PIE lever, fixed-timestep, and the
// checkpoint clock; this fixture owns the marker relocation, the walker
// spawn/possession, the per-frame drive toward the portal, and the three
// distance-gated assertions. All FAIL message text is ASCII-only (the cp1252
// log read-back rule).

#include "TeleportPortalFunctionalTest.h"

#include "Engine/World.h"
#include "GameFramework/Character.h"
#include "Kismet/GameplayStatics.h"

namespace
{
	static const FName TeleportPortalTag(TEXT("TeleportPortal"));
	static const FName TeleportDestinationTag(TEXT("TeleportDestination"));

	// The fixture-chosen destination. Deliberately NOT the marker's authored
	// map placement (3200, 900, 90) — PrepareTest moves the marker here, so a
	// solution that baked in the authored coordinates fails the delivery gate.
	// Z = 90 is capsule-center height over the runway top (Z = +2): a
	// correctly delivered walker settles to ~zero 3D distance.
	const FVector KDestinationSpot(2600.0, -900.0, 90.0);

	// Walker spawn: KApproachDistance in front of the portal along -X, at
	// capsule-settle height. Contact is expected at ~1.9s world time given
	// default character ground speed (~600 uu/s) from the drive start at 0.5s.
	constexpr double KApproachDistance = 740.0;
	constexpr double KWalkerSpawnZ = 92.0;

	// Delivery = within this 3D distance of the destination spot at cp1. The
	// walker has >1.5s to settle after contact; a correct teleport measures
	// near zero. 150uu also absorbs a reference that lifts the landing by a
	// capsule half-height before gravity settles it.
	constexpr double KDeliverTolerance = 150.0;

	// Free = at least this far from the destination spot (cp0 pre-contact, the
	// continuous pre-contact guard, and cp2 after the fixture relocated the
	// walker KRelocateOffset away).
	constexpr double KFreeMinDistance = 250.0;

	const FVector KRelocateOffset(400.0, 0.0, 0.0);

	// The contact zone: the walker counts as having REACHED the portal once
	// its walked X progress is within this of the portal's X plane (box
	// extent 60 + capsule radius 34 + ~5 frames of 60Hz walk margin). The
	// continuous guard treats a delivery that happens while MaxApproachX is
	// still short of this zone as contact-free — a timed/unconditional cheat.
	constexpr double KContactZoneX = 140.0;

	// cp1 failure branching: a walker still within this 3D distance of the
	// portal center was never relocated at all (the empty-submission shape,
	// which brakes ~70uu past the plane); farther away means it was delivered
	// somewhere that is not the destination (memorized coordinates land
	// ~2,000uu from the portal).
	constexpr double KNearPortalDistance = 600.0;
}

ATeleportPortalFunctionalTest::ATeleportPortalFunctionalTest(const FObjectInitializer& ObjectInitializer)
	: Super(ObjectInitializer)
{
}

void ATeleportPortalFunctionalTest::PrepareTest()
{
	Super::PrepareTest();  // base: snapshot FApp globals + set fixed dt

	UWorld* World = GetWorld();
	if (World == nullptr)
	{
		FinishTest(EFunctionalTestResult::Error, TEXT("HARNESS-PRECONDITION: PrepareTest: no UWorld available"));
		return;
	}

	// Identity by tag, never by class: agents may subclass/rename the portal
	// (the ctor-stamped tag inherits).
	TArray<AActor*> Found;
	UGameplayStatics::GetAllActorsWithTag(World, TeleportPortalTag, Found);
	if (Found.Num() != 1)
	{
		FinishTest(
			EFunctionalTestResult::Failed,
			FString::Printf(TEXT("Expected exactly one actor tagged 'TeleportPortal' (the portal frame) in the running level; found %d."), Found.Num()));
		return;
	}
	Portal = Found[0];
	PortalSpot = Found[0]->GetActorLocation();

	Found.Reset();
	UGameplayStatics::GetAllActorsWithTag(World, TeleportDestinationTag, Found);
	if (Found.Num() != 1)
	{
		FinishTest(
			EFunctionalTestResult::Failed,
			FString::Printf(TEXT("Expected exactly one actor tagged 'TeleportDestination' (the destination marker) in the running level; found %d."), Found.Num()));
		return;
	}
	Marker = Found[0];

	// Move the marker to the fixture-chosen spot BEFORE any teleport can
	// happen. The prompt requires reading the marker's position at teleport
	// time; a solution that memorized the authored coordinates now delivers
	// to the wrong place.
	DestinationSpot = KDestinationSpot;
	if (!Marker->SetActorLocation(DestinationSpot))
	{
		FinishTest(EFunctionalTestResult::Failed,
			TEXT("HARNESS-PRECONDITION: PrepareTest: could not relocate the destination marker (marker root not movable?)"));
		return;
	}

	// The fixture supplies its own moving body: a plain engine character,
	// spawned on the approach line and possessed so its movement component
	// consumes input (an unpossessed Character is inert — Slice-0 spike).
	FActorSpawnParameters SpawnParams;
	SpawnParams.SpawnCollisionHandlingOverride = ESpawnActorCollisionHandlingMethod::AdjustIfPossibleButAlwaysSpawn;
	const FVector WalkerStart(PortalSpot.X - KApproachDistance, PortalSpot.Y, KWalkerSpawnZ);
	ACharacter* Spawned = World->SpawnActor<ACharacter>(
		ACharacter::StaticClass(), WalkerStart, FRotator::ZeroRotator, SpawnParams);
	if (Spawned == nullptr)
	{
		FinishTest(EFunctionalTestResult::Failed, TEXT("HARNESS-PRECONDITION: PrepareTest: walker character spawn failed"));
		return;
	}
	Spawned->SpawnDefaultController();
	if (Spawned->GetController() == nullptr)
	{
		FinishTest(EFunctionalTestResult::Failed, TEXT("HARNESS-PRECONDITION: PrepareTest: walker character possession failed"));
		return;
	}
	Walker = Spawned;
	MaxApproachX = WalkerStart.X;

	// cp0 at 0.5 (settled, pre-contact), cp1 at 3.5 (contact ~1.9s + settle
	// margin), cp2 at 5.0 (1.5s after the fixture relocated the walker — a
	// re-snapping solution has ~90 frames at 60Hz to pull it back). Between
	// cp0 and delivery the Tick guard watches continuously (see Tick).
	SetCheckpointSchedule({ 0.5, 3.5, 5.0 });
}

void ATeleportPortalFunctionalTest::Tick(float DeltaSeconds)
{
	Super::Tick(DeltaSeconds);  // base runs the checkpoint clock first

	// Sustain locomotion toward the portal: movement input is consumed per
	// frame, so the drive must be re-applied every tick (never tick the
	// world). The drive self-stops once the walker crosses the portal's X
	// plane so an un-teleported walker brakes just past the portal instead of
	// wandering toward the destination on its own.
	if (IsRunning() && bDriving && Walker.IsValid())
	{
		const FVector WalkerLoc = Walker->GetActorLocation();

		// CONTINUOUS pre-contact guard — a single-instant cp0 sample would
		// miss a timed unconditional teleport that fires between 0.5s and
		// contact (~1.9s). MaxApproachX only ever advanced on un-delivered
		// ticks, so it still holds the walker's true WALKED progress: a
		// delivery observed while that progress is short of the portal's
		// contact zone happened without contact.
		//
		// MESSAGE-ONLY SPLIT (2026-08-17): this gate used to print cp0's
		// exact literal, so no MATRIX row could say WHICH of the two
		// pre-contact gates fired. The reasons differ: cp0 means
		// "already at the destination on the very first sample, before the
		// drive was even armed" (an every-tick / BeginPlay snap); this one
		// means "delivered part-way along the approach, having never
		// reached the portal" (a timed snap). Predicates, gate order and
		// every verdict are unchanged - only the message text differs.
		if (FVector::Dist(WalkerLoc, DestinationSpot) < KFreeMinDistance)
		{
			if (MaxApproachX < PortalSpot.X - KContactZoneX)
			{
				FinishTest(
					EFunctionalTestResult::Failed,
					FString::Printf(TEXT("Expected the walker character to reach the portal before any delivery; observed it delivered mid-approach without ever reaching the portal (distance %.0f)."),
						FVector::Dist(WalkerLoc, DestinationSpot)));
				return;
			}
			// Legit delivery (contact was made): stop the drive; cp1 grades it.
			bDriving = false;
			return;
		}

		MaxApproachX = FMath::Max(MaxApproachX, WalkerLoc.X);
		if (WalkerLoc.X >= PortalSpot.X - 20.0)
		{
			bDriving = false;
			return;
		}
		FVector Dir = PortalSpot - WalkerLoc;
		Dir.Z = 0.0;
		if (!Dir.Normalize())
		{
			return;
		}
		Walker->AddMovementInput(Dir, 1.0f);
	}
}

bool ATeleportPortalFunctionalTest::GuardWalker(int32 CheckpointIndex)
{
	if (!Walker.IsValid())
	{
		FinishTest(
			EFunctionalTestResult::Failed,
			FString::Printf(TEXT("At checkpoint %d: the walker character is no longer valid (it must be relocated, never destroyed)."), CheckpointIndex));
		return false;
	}
	return true;
}

double ATeleportPortalFunctionalTest::DistanceToDestination() const
{
	return Walker.IsValid() ? FVector::Dist(Walker->GetActorLocation(), DestinationSpot) : TNumericLimits<double>::Max();
}

void ATeleportPortalFunctionalTest::OnCheckpoint(int32 CheckpointIndex, double TimeSeconds)
{
	if (!GuardWalker(CheckpointIndex))
	{
		return;
	}
	const double Distance = DistanceToDestination();
	UE_LOG(LogTemp, Display, TEXT("[t1-teleport calib] cp%d t=%.2f dist=%.1f walkerX=%.1f"),
		CheckpointIndex, TimeSeconds, Distance, Walker->GetActorLocation().X);

	switch (CheckpointIndex)
	{
	case 0:  // t=0.5 — settled on the approach line, BEFORE any contact.
		// Own literal, distinct from the Tick guard's (see its MESSAGE-ONLY
		// SPLIT note): reaching HERE means the walker sat at the destination
		// on the very first sample, before the drive was armed at all.
		if (Distance < KFreeMinDistance)
		{
			FinishTest(
				EFunctionalTestResult::Failed,
				FString::Printf(TEXT("Expected the walker character to be away from the marked destination at the first sample; observed it already delivered before it had walked at all (distance %.0f)."), Distance));
			return;
		}
		bDriving = true;
		break;

	case 1:  // t=3.5 — contact at ~1.9s; the walker must have been delivered.
		if (Distance > KDeliverTolerance)
		{
			// Branch the named failure on WHERE the walker actually is, so the
			// no-teleport shape and the wrong-place shape carry distinct
			// MATRIX-credited substrings.
			if (FVector::Dist(Walker->GetActorLocation(), PortalSpot) < KNearPortalDistance)
			{
				FinishTest(
					EFunctionalTestResult::Failed,
					FString::Printf(TEXT("Expected the walker character to be delivered to the marked destination after walking into the portal; observed it never left the portal area - no teleport happened (distance to destination %.0f)."), Distance));
			}
			else
			{
				FinishTest(
					EFunctionalTestResult::Failed,
					FString::Printf(TEXT("Expected the walker character to be delivered to the marked destination after walking into the portal; observed it delivered somewhere else than the marked destination (distance %.0f)."), Distance));
			}
			return;
		}
		// Delivered. Now walk it out of the destination: a solution that keeps
		// snapping the entrant back has until cp2 to reveal itself.
		bDriving = false;
		Walker->SetActorLocation(DestinationSpot + KRelocateOffset, false, nullptr, ETeleportType::TeleportPhysics);
		break;

	case 2:  // t=5.0 — 1.5s after leaving the destination.
		if (Distance < KFreeMinDistance)
		{
			FinishTest(
				EFunctionalTestResult::Failed,
				FString::Printf(TEXT("Expected the walker character to stay free after leaving the destination (no repeated snapping back); observed distance %.0f."), Distance));
			return;
		}
		FinishTest(EFunctionalTestResult::Succeeded, TEXT(""));
		break;

	default:
		break;
	}
}
